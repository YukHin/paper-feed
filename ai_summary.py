import datetime
import glob
import html
import json
import os
import re
import smtplib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.utils import formataddr, parsedate_to_datetime
from xml.etree import ElementTree

FEED_DIR = "feeds"                        # per-journal RSS + AI files live here
INPUT_FEED_FILE = "filtered_feed.xml"  # legacy combined feed (fallback only)
INPUT_FEED_GLOB = os.path.join(FEED_DIR, "filtered_feed.*.xml")  # per-journal feeds
OUTPUT_FEED_FILE = "ai_summary_feed.xml"  # legacy combined AI feed, removed after split
OUTPUT_HTML_FILE = "ai_summary.html"      # AI summary index landing page (root)
OUTPUT_OPML_FILE = "ai_summary.opml"      # one-click bulk import of AI feeds (root)
AI_OUTPUT_PREFIX = "ai_summary"           # per-journal: ai_summary.<slug>.html / .xml
EMAIL_BODY_FILE = "email_body.html"       # transient: written only when new summaries exist
STATE_FILE = "ai_summary_state.json"
CONFIG_FILE = "paper_feed_config.json"

DEFAULT_INTERVAL_HOURS = 24
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_SCREENING_BATCH_SIZE = 10
MAX_SELECTED_PAPERS = 40
DEFAULT_MAX_CANDIDATES = 100
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_MAX_PROMPT_TITLE_CHARS = 240
DEFAULT_MAX_PROMPT_ABSTRACT_CHARS = 1200
DEFAULT_RETRY_ATTEMPTS_PER_ROUND = 3
DEFAULT_RETRY_ROUNDS = 2
DEFAULT_RETRY_SLEEP_SECONDS = 10 * 60
DEFAULT_REQUESTS_PER_MINUTE = 5

BATCH_INSIGHT_SYSTEM_PROMPT = (
    "You are a world-class scientific literature screening and summarization assistant. "
    "For each batch, select only papers strictly related to the user's research interests. "
    "For selected papers, classify them by matched research direction and write a dense "
    "2-3 sentence Chinese summary. Return only a valid JSON array. Do not include "
    "markdown fences or conversational text."
)

FINAL_HTML_SYSTEM_PROMPT = (
    "You are an expert scientific editor and HTML formatter. Create a clean, modern "
    "HTML literature digest from classified paper summaries. Group papers by the "
    "user's research directions in importance order. Return only the HTML snippet "
    "inside body tags. Do not include markdown fences."
)


@dataclass
class AiSummaryConfig:
    base_url: str
    api_key: str
    model: str
    prompt: str
    interval_hours: int
    max_candidates: int
    max_output_tokens: int
    screening_batch_size: int
    requests_per_minute: int
    max_prompt_title_chars: int
    max_prompt_abstract_chars: int
    retry_attempts_per_round: int
    retry_rounds: int
    retry_sleep_seconds: int


class ChatCompletionClient:
    def __init__(self, config):
        self.config = config

    def complete(self, messages):
        url = get_completions_url(self.config.base_url)
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if self.config.max_output_tokens > 0:
            payload["max_tokens"] = self.config.max_output_tokens
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            ) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"AI request failed with HTTP {error.code}: {body[:240]}"
            ) from error

        parsed = json.loads(body)
        choices = parsed.get("choices") or []
        if not choices:
            raise RuntimeError("AI response did not include choices")

        first = choices[0]
        content = (first.get("message") or {}).get("content") or first.get("text")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("AI response did not include message content")

        return content.strip()


def get_env_bool(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def get_env_int(name, default):
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def load_public_config():
    if not os.path.exists(CONFIG_FILE):
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    return loaded if isinstance(loaded, dict) else {}


def get_config_int(section, key, default, env_name=None):
    if env_name and os.environ.get(env_name, "").strip():
        return get_env_int(env_name, default)

    return positive_int(section.get(key), default)


def get_non_negative_config_int(section, key, default, env_name=None):
    if env_name and os.environ.get(env_name, "").strip():
        return non_negative_int(os.environ.get(env_name), default)

    return non_negative_int(section.get(key), default)


def positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def non_negative_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def load_api_config():
    raw = os.environ.get("AI_API_CONFIG", "").strip()
    if raw:
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return None

            if isinstance(parsed, dict):
                return {
                    "base_url": str(parsed.get("base_url", "")).strip(),
                    "api_key": str(parsed.get("api_key", "")).strip(),
                    "model": str(parsed.get("model", "")).strip(),
                }

            return None

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(lines) < 3:
            return None

        return {
            "base_url": lines[0],
            "api_key": lines[1],
            "model": lines[2],
        }

    return {
        "base_url": os.environ.get("AI_BASE_URL", "").strip(),
        "api_key": os.environ.get("AI_API_KEY", "").strip(),
        "model": os.environ.get("AI_MODEL", "").strip(),
    }


def load_ai_config():
    public_config = load_public_config()
    ai_public_config = public_config.get("ai_summary", {})
    if not isinstance(ai_public_config, dict):
        ai_public_config = {}

    enabled_default = bool(ai_public_config.get("enabled", True))
    if not get_env_bool("AI_SUMMARY_ENABLED", enabled_default):
        return None

    api_config = load_api_config() or {}
    base_url = api_config.get("base_url", "")
    api_key = api_config.get("api_key", "")
    model = api_config.get("model", "")
    prompt = os.environ.get("AI_SUMMARY_PROMPT", "").strip()

    if not all([base_url, api_key, model, prompt]):
        print(
            "AI summary skipped: AI_API_CONFIG (or legacy AI_BASE_URL/AI_API_KEY/AI_MODEL) "
            "and AI_SUMMARY_PROMPT are required."
        )
        return None

    return AiSummaryConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        prompt=prompt,
        interval_hours=get_config_int(
            ai_public_config,
            "interval_hours",
            DEFAULT_INTERVAL_HOURS,
            "AI_SUMMARY_INTERVAL_HOURS",
        ),
        max_candidates=get_config_int(
            ai_public_config,
            "max_candidates",
            DEFAULT_MAX_CANDIDATES,
            "AI_SUMMARY_MAX_CANDIDATES",
        ),
        max_output_tokens=get_non_negative_config_int(
            ai_public_config,
            "max_output_tokens",
            DEFAULT_MAX_OUTPUT_TOKENS,
            "AI_SUMMARY_MAX_OUTPUT_TOKENS",
        ),
        screening_batch_size=get_config_int(
            ai_public_config,
            "screening_batch_size",
            DEFAULT_SCREENING_BATCH_SIZE,
        ),
        requests_per_minute=get_config_int(
            ai_public_config,
            "requests_per_minute",
            DEFAULT_REQUESTS_PER_MINUTE,
        ),
        max_prompt_title_chars=get_non_negative_config_int(
            ai_public_config,
            "max_prompt_title_chars",
            DEFAULT_MAX_PROMPT_TITLE_CHARS,
        ),
        max_prompt_abstract_chars=get_non_negative_config_int(
            ai_public_config,
            "max_prompt_abstract_chars",
            DEFAULT_MAX_PROMPT_ABSTRACT_CHARS,
        ),
        retry_attempts_per_round=get_config_int(
            ai_public_config,
            "retry_attempts_per_round",
            DEFAULT_RETRY_ATTEMPTS_PER_ROUND,
        ),
        retry_rounds=get_config_int(
            ai_public_config,
            "retry_rounds",
            DEFAULT_RETRY_ROUNDS,
        ),
        retry_sleep_seconds=get_config_int(
            ai_public_config,
            "retry_sleep_seconds",
            DEFAULT_RETRY_SLEEP_SECONDS,
        ),
    )


def get_completions_url(base_url):
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_state():
    if not os.path.exists(STATE_FILE):
        return {"last_success_at": None, "submitted_ids": []}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"last_success_at": None, "submitted_ids": []}

    submitted_ids = state.get("submitted_ids")
    if not isinstance(submitted_ids, list):
        submitted_ids = []

    return {
        "last_success_at": state.get("last_success_at"),
        "submitted_ids": [str(item) for item in submitted_ids],
    }


def write_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def is_summary_due(state, interval_hours, now):
    last_success = parse_timestamp(state.get("last_success_at"))
    if last_success is None:
        return True

    if last_success.tzinfo is None:
        last_success = last_success.replace(tzinfo=datetime.timezone.utc)
    return now - last_success >= datetime.timedelta(hours=interval_hours)


def strip_html(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def load_feed_entries(filename):
    if not os.path.exists(filename):
        print(f"AI summary skipped: {filename} does not exist.")
        return []

    root = ElementTree.parse(filename).getroot()
    dc_namespace = "{http://purl.org/dc/elements/1.1/}"
    entries = []

    for item in root.findall(".//item"):
        title = child_text(item, "title")
        link = child_text(item, "link")
        summary = child_text(item, "description")
        guid = child_text(item, "guid") or link
        journal = child_text(item, f"{dc_namespace}source") or child_text(item, "author")
        entries.append(
            {
                "id": guid,
                "title": strip_html(title),
                "abstract": strip_html(summary),
                "journal": strip_html(journal),
                "url": link,
                "pubDate": parse_rss_datetime(child_text(item, "pubDate")).isoformat(),
            }
        )

    entries.sort(key=lambda item: item["pubDate"], reverse=True)
    return entries


def slug_from_feed_path(path):
    """filtered_feed.<slug>.xml -> <slug>; legacy filtered_feed.xml -> 'all'."""
    base = os.path.basename(path)
    match = re.match(r"filtered_feed\.(.+)\.xml$", base)
    return match.group(1) if match else "all"


def feed_channel_title(path):
    try:
        root = ElementTree.parse(path).getroot()
        node = root.find(".//channel/title")
        return node.text.strip() if node is not None and node.text else ""
    except Exception:
        return ""


def ai_html_path(slug):
    return os.path.join(FEED_DIR, f"{AI_OUTPUT_PREFIX}.{slug}.html")


def ai_feed_path(slug):
    return os.path.join(FEED_DIR, f"{AI_OUTPUT_PREFIX}.{slug}.xml")


def load_all_feed_entries():
    """Load candidates from every per-journal feed, deduped by id.

    Each entry is tagged with its source journal (`feed_slug`, `feed_name`) so
    the summary can be produced per journal. Falls back to the legacy combined
    filtered_feed.xml if no per-journal feeds are present.
    """
    paths = sorted(glob.glob(INPUT_FEED_GLOB))
    if not paths:
        paths = sorted(glob.glob("filtered_feed.*.xml"))  # legacy: root-level per-journal feeds
    if not paths and os.path.exists(INPUT_FEED_FILE):
        paths = [INPUT_FEED_FILE]

    if not paths:
        print("AI summary skipped: no feed files found.")
        return []

    seen = set()
    entries = []
    for path in paths:
        slug = slug_from_feed_path(path)
        name = feed_channel_title(path) or slug
        for entry in load_feed_entries(path):
            if entry["id"] in seen:
                continue
            seen.add(entry["id"])
            entry["feed_slug"] = slug
            entry["feed_name"] = name
            entries.append(entry)

    entries.sort(key=lambda item: item["pubDate"], reverse=True)
    return entries


def child_text(parent, tag):
    child = parent.find(tag)
    return child.text if child is not None and child.text else ""


def parse_rss_datetime(value):
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
        except (TypeError, ValueError):
            pass

    return datetime.datetime.now(datetime.timezone.utc)


def chunked(items, size):
    for offset in range(0, len(items), size):
        yield offset, items[offset : offset + size]


def strip_code_fence(value):
    stripped = value.strip()
    stripped = re.sub(r"^```(?:html|json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def parse_json_array(value):
    stripped = strip_code_fence(value)
    match = re.search(r"\[[\s\S]*\]", stripped)
    parsed = json.loads(match.group(0) if match else stripped)
    return parsed if isinstance(parsed, list) else []


def parse_paper_insights(value):
    insights = []
    for item in parse_json_array(value):
        if not isinstance(item, dict):
            continue
        try:
            insight_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        matched_direction = str(item.get("matched_direction", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not matched_direction or not summary:
            continue

        insights.append(
            {
                "id": insight_id,
                "matched_direction": matched_direction,
                "importance": str(item.get("importance", "")).strip(),
                "summary": summary,
            }
        )
    return insights


class RequestRateLimiter:
    def __init__(self, requests_per_minute, time_fn=time.monotonic, sleep_fn=time.sleep):
        self.min_interval_seconds = 60 / max(1, requests_per_minute)
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self.last_request_at = None

    def wait(self):
        now = self.time_fn()
        if self.last_request_at is not None:
            elapsed = now - self.last_request_at
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                self.sleep_fn(remaining)
                now = self.time_fn()
        self.last_request_at = now


def limit_prompt_text(value, max_chars):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if max_chars == 0:
        return text
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def paper_for_prompt(entry, index, config):
    return {
        "id": index + 1,
        "title": limit_prompt_text(entry["title"], config.max_prompt_title_chars),
        "abstract": limit_prompt_text(entry["abstract"], config.max_prompt_abstract_chars),
        "journal": entry["journal"],
        "url": entry["url"],
        "pubDate": entry["pubDate"],
    }


def create_batch_prompt(config, papers, offset):
    prompt_papers = [
        paper_for_prompt(paper, offset + index, config)
        for index, paper in enumerate(papers)
    ]
    return "\n".join(
        [
            "User Interests & Importance Order:",
            config.prompt,
            "",
            "Paper Batch:",
            json.dumps(prompt_papers, ensure_ascii=False, indent=2),
            "",
            "Instructions:",
            "1. Compare each paper against the user's interests and importance order.",
            "2. Discard unrelated papers completely; do not mention them.",
            "3. For every related paper, classify it by the most relevant user-defined direction.",
            "4. Write a 2-3 sentence Chinese summary focusing on problem, method/tool, and key finding.",
            "5. Return only a JSON array in this format:",
            '[{"id":1,"matched_direction":"用户方向关键词","importance":"high|medium|low","summary":"中文总结"}]',
        ]
    )


def create_final_html_prompt(config, papers, insights, generated_at):
    paper_map = {
        index + 1: paper_for_prompt(paper, index, config)
        for index, paper in enumerate(papers)
    }
    selected = []
    for insight in insights:
        paper = paper_map.get(insight["id"])
        if not paper:
            continue
        selected.append(
            {
                **paper,
                "matched_direction": insight["matched_direction"],
                "importance": insight["importance"],
                "summary": insight["summary"],
            }
        )

    return "\n".join(
        [
            "User Interests & Importance Order:",
            config.prompt,
            "",
            f"Generated At: {generated_at}",
            f"Candidate Paper Count: {len(papers)}",
            f"Selected Paper Count: {len(selected)}",
            "",
            "Classified Paper Summaries:",
            json.dumps(selected, ensure_ascii=False, indent=2),
            "",
            "HTML Requirements:",
            "1. Generate one complete HTML snippet suitable for an RSS item description.",
            "2. Use inline styles only.",
            "3. Include the title Daily AI Literature Insights, generation time, candidate count, and selected count.",
            "4. Group papers by the user's research directions, ordered by the user's importance order.",
            "5. For each paper, include linked title, journal, matched direction, and the provided Chinese summary.",
            "6. Highlight key materials, chemical formulas, tools, or algorithms with <strong> tags when appropriate.",
            "7. Return only HTML content; no markdown fences.",
        ]
    )


def extract_body_html(value):
    stripped = strip_code_fence(value)
    match = re.search(r"<body[^>]*>([\s\S]*?)</body>", stripped, flags=re.IGNORECASE)
    return (match.group(1) if match else stripped).strip()


def create_empty_report_html(generated_at, total_count):
    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif;'
        'max-width:800px;margin:0 auto;padding:20px;line-height:1.6;color:#2d3748;">'
        '<div style="border-bottom:2px solid #4A90E2;padding-bottom:10px;margin-bottom:20px;">'
        '<h2 style="margin:0;color:#1A365D;font-size:22px;">Daily AI Literature Insights</h2>'
        f'<p style="margin:6px 0 0;color:#718096;font-size:13px;">生成时间: {html.escape(generated_at)} | '
        f"候选文献: {total_count} 篇 | AI 选中: 0 篇</p>"
        "</div>"
        '<div style="text-align:center;color:#718096;padding:36px 0;border:1px solid #E2E8F0;'
        'border-radius:8px;background:#F7FAFC;">本次暂无与订阅方向高度相关的文献更新。</div>'
        "</div>"
    )


def wrap_ai_html(ai_html, generated_at, total_count, matched_count):
    body = extract_body_html(ai_html)
    if re.search(r"Daily AI Literature Insights", body, flags=re.IGNORECASE):
        return body

    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif;'
        'max-width:800px;margin:0 auto;padding:20px;line-height:1.6;color:#2d3748;">'
        '<div style="border-bottom:2px solid #4A90E2;padding-bottom:10px;margin-bottom:20px;">'
        '<h2 style="margin:0;color:#1A365D;font-size:22px;">Daily AI Literature Insights</h2>'
        f'<p style="margin:6px 0 0;color:#718096;font-size:13px;">生成时间: {html.escape(generated_at)} | '
        f"候选文献: {total_count} 篇 | AI 选中: {matched_count} 篇</p>"
        "</div>"
        f"{body}"
        "</div>"
    )


def complete_with_retries(client, messages, label, config, rate_limiter, sleep_fn=time.sleep):
    last_error = None
    total_attempts = config.retry_attempts_per_round * config.retry_rounds

    for round_index in range(config.retry_rounds):
        for attempt_index in range(config.retry_attempts_per_round):
            attempt_number = round_index * config.retry_attempts_per_round + attempt_index + 1
            try:
                rate_limiter.wait()
                return client.complete(messages)
            except Exception as error:
                last_error = error
                print(f"AI {label} attempt {attempt_number}/{total_attempts} failed: {error}")

        if round_index < config.retry_rounds - 1:
            print(
                f"AI {label} failed after {config.retry_attempts_per_round} attempts; "
                f"sleeping {config.retry_sleep_seconds} seconds before the next retry round."
            )
            sleep_fn(config.retry_sleep_seconds)

    raise RuntimeError(f"AI {label} failed after {total_attempts} attempts: {last_error}")


def generate_ai_summary_report(config, papers, client, now, sleep_fn=time.sleep):
    generated_at = now.isoformat().replace("+00:00", "Z")
    all_insights = []
    rate_limiter = RequestRateLimiter(
        config.requests_per_minute,
        sleep_fn=sleep_fn,
    )

    for offset, batch in chunked(papers, config.screening_batch_size):
        result = complete_with_retries(
            client,
            [
                {"role": "system", "content": BATCH_INSIGHT_SYSTEM_PROMPT},
                {"role": "user", "content": create_batch_prompt(config, batch, offset)},
            ],
            f"batch {offset // config.screening_batch_size + 1}",
            config,
            rate_limiter,
            sleep_fn,
        )
        all_insights.extend(parse_paper_insights(result))

    seen_ids = set()
    insights = []
    for insight in all_insights:
        if insight["id"] < 1 or insight["id"] > len(papers) or insight["id"] in seen_ids:
            continue
        seen_ids.add(insight["id"])
        insights.append(insight)
        if len(insights) >= MAX_SELECTED_PAPERS:
            break

    if insights:
        final_html = complete_with_retries(
            client,
            [
                {"role": "system", "content": FINAL_HTML_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": create_final_html_prompt(
                        config,
                        papers,
                        insights,
                        generated_at,
                    ),
                },
            ],
            "final HTML",
            config,
            rate_limiter,
            sleep_fn,
        )
        report_html = wrap_ai_html(final_html, generated_at, len(papers), len(insights))
    else:
        report_html = create_empty_report_html(generated_at, len(papers))

    return {
        "generated_at": generated_at,
        "matched_count": len(insights),
        "html": report_html,
        "title": f"AI Literature Summary - {generated_at[:16].replace('T', ' ')}",
        "id": f"paper-feed-ai-summary-{generated_at.replace(':', '-').replace('+', '-')}",
    }


def write_ai_html(report, html_file, journal_name):
    document = "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>Daily AI Literature Insights - {html.escape(journal_name)}</title>",
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "</head>",
            "<body>",
            report["html"],
            "</body>",
            "</html>",
            "",
        ]
    )
    with open(html_file, "w", encoding="utf-8") as handle:
        handle.write(document)


def write_ai_feed(report, feed_file, html_file, journal_name):
    pub_date = to_rfc822(parse_timestamp(report["generated_at"]))
    html_url = get_public_file_url(html_file)
    xml = "".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0">',
            "<channel>",
            f"<title>{escape_xml(journal_name)} — AI Summary</title>",
            f"<link>{escape_xml(html_url)}</link>",
            f"<description>AI-generated literature digest for {escape_xml(journal_name)}</description>",
            "<language>zh-CN</language>",
            f"<lastBuildDate>{escape_xml(pub_date)}</lastBuildDate>",
            "<item>",
            f"<title>{escape_xml(report['title'])}</title>",
            f"<link>{escape_xml(html_url)}</link>",
            f"<description>{escape_xml(report['html'])}</description>",
            f"<guid isPermaLink=\"false\">{escape_xml(report['id'])}</guid>",
            f"<pubDate>{escape_xml(pub_date)}</pubDate>",
            "</item>",
            "</channel>",
            "</rss>",
        ]
    )

    with open(feed_file, "w", encoding="utf-8") as handle:
        handle.write(xml)


def write_email_body(sections, generated_at):
    """Write email_body.html: this run's per-journal digests inlined for the push."""
    blocks = "\n".join(
        f'<section style="margin:0 0 2rem"><h2 style="font-size:1.15rem;border-bottom:2px solid #0b62d6;'
        f'padding-bottom:.2rem">{html.escape(s["name"])} '
        f'<span style="color:#999;font-size:.8em">({s["selected"]}/{s["candidates"]})</span></h2>\n'
        f'{s["html"]}\n</section>'
        for s in sections
    )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:auto;line-height:1.6">
<h1 style="font-size:1.4rem">Paper-Feed AI 总结</h1>
<p style="color:#999;font-size:.85em">{escape_xml(generated_at[:16].replace('T', ' '))} · 本次更新 {len(sections)} 本期刊</p>
{blocks}
</body>
</html>
"""
    with open(EMAIL_BODY_FILE, "w", encoding="utf-8") as handle:
        handle.write(document)


def build_ai_index(run_info):
    """List every per-journal AI page on disk, merging this run's counts.

    Scans ai_summary.<slug>.html so the landing page stays cumulative across
    runs (journals not updated this run keep their previous page and link).
    """
    index = []
    for html_path in sorted(glob.glob(os.path.join(FEED_DIR, f"{AI_OUTPUT_PREFIX}.*.html"))):
        base = os.path.basename(html_path)
        slug = base[len(AI_OUTPUT_PREFIX) + 1:-len(".html")]
        feed_path = ai_feed_path(slug)
        name = feed_channel_title(feed_path) if os.path.exists(feed_path) else slug
        name = name.replace(" — AI Summary", "").strip() or slug
        info = run_info.get(slug, {})
        index.append({
            "slug": slug,
            "name": name,
            "html": html_path,
            "feed": feed_path if os.path.exists(feed_path) else html_path,
            "selected": info.get("selected", "·"),
            "candidates": info.get("candidates", "·"),
        })
    return index


def write_ai_index(index, generated_at):
    """Write the ai_summary.html landing page linking every per-journal digest."""
    rows = "\n".join(
        f'    <li><a href="{html.escape(item["html"])}">{html.escape(item["name"])}</a>'
        f' <span class="count">({item["selected"]}/{item["candidates"]})</span>'
        f' <a class="rss" href="{html.escape(item["feed"])}">RSS</a></li>'
        for item in index
    )
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paper-Feed AI 总结</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.6}}
h1{{font-size:1.4rem}}
ul{{list-style:none;padding:0}}
li{{padding:.4rem 0;border-bottom:1px solid #eee}}
a{{text-decoration:none;color:#0b62d6}}
.count{{color:#999;font-size:.9em}}
.rss{{font-size:.8em;color:#e8850c;margin-left:.4rem}}
.meta{{color:#999;font-size:.85em}}
</style>
</head>
<body>
<h1>Paper-Feed 分期刊 AI 总结</h1>
<p class="meta">本次更新 {len(index)} 本期刊 · {escape_xml(generated_at[:16].replace('T', ' '))}</p>
<p>每本期刊都有独立的 AI 总结页面和 RSS 订阅。括号内为本次「入选 / 候选」文献数。</p>
<ul>
{rows}
</ul>
</body>
</html>
"""
    with open(OUTPUT_HTML_FILE, "w", encoding="utf-8") as handle:
        handle.write(page)

    # OPML for one-click bulk import of the per-journal AI feeds into Zotero.
    outlines = "\n".join(
        '    <outline text="{n}" title="{n}" type="rss" xmlUrl="{u}"/>'.format(
            n=escape_xml(f"{item['name']} · AI"),
            u=escape_xml(get_public_file_url(item["feed"])),
        )
        for item in index
    )
    opml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Paper-Feed 分期刊 AI 总结</title></head>
  <body>
{outlines}
  </body>
</opml>
"""
    with open(OUTPUT_OPML_FILE, "w", encoding="utf-8") as handle:
        handle.write(opml)


def get_public_file_url(filename):
    base_url = get_public_base_url()
    if not base_url:
        return filename
    return f"{base_url}/{filename.lstrip('/')}"


def get_public_base_url():
    configured = os.environ.get("PAPER_FEED_PUBLIC_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository or "/" not in repository:
        return ""

    owner, repo = repository.split("/", 1)
    if repo.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner}.github.io"
    return f"https://{owner}.github.io/{repo}"


def escape_xml(value):
    return html.escape(str(value), quote=True)


def to_rfc822(value):
    date = value or datetime.datetime.now(datetime.timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    return date.astimezone(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def load_email_config():
    """Load email push config, private-first, mirroring load_config in get_RSS.py.

    Reads the ``EMAIL_CONFIG`` env var (GitHub Secret) if set, otherwise the
    local ``email.dat`` file (keep it out of git). Expected lines, in order:

        recipient@example.com[, another@example.com]   # 1: to (comma/semicolon separated)
        yourgmail@gmail.com                              # 2: SMTP username / from
        app-password                                     # 3: SMTP password
        smtp.gmail.com:465                               # 4: host:port (optional)

    Returns a dict, or None if unconfigured/incomplete (email is then skipped).
    """
    raw = os.environ.get("EMAIL_CONFIG", "").strip()
    if raw:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
    elif os.path.exists("email.dat"):
        with open("email.dat", "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    else:
        return None

    if len(lines) < 3:
        print("Email push skipped: EMAIL_CONFIG/email.dat needs at least 3 lines (to, user, password).")
        return None

    recipients = [addr.strip() for addr in re.split(r"[;,]", lines[0]) if addr.strip()]
    host, _, port = (lines[3] if len(lines) > 3 else "smtp.gmail.com:465").partition(":")
    return {
        "to": recipients,
        "user": lines[1],
        "password": lines[2],
        "host": host or "smtp.gmail.com",
        "port": int(port) if port.isdigit() else 465,
    }


def send_email_digest(generated_at):
    """Email the freshly written digest (EMAIL_BODY_FILE) via SMTP over SSL.

    Silently no-ops when there is no new digest this run or when email is not
    configured, so it never breaks the RSS/AI pipeline.
    """
    if not os.path.exists(EMAIL_BODY_FILE):
        return

    cfg = load_email_config()
    if not cfg:
        return

    with open(EMAIL_BODY_FILE, "r", encoding="utf-8") as handle:
        body = handle.read()

    message = MIMEText(body, "html", "utf-8")
    message["Subject"] = f"Paper-Feed AI 总结 · {generated_at[:10]}"
    message["From"] = formataddr(("Paper-Feed", cfg["user"]))
    message["To"] = ", ".join(cfg["to"])

    try:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=60) as server:
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], cfg["to"], message.as_string())
        print(f"Email digest sent to {', '.join(cfg['to'])}.")
    except Exception as error:
        print(f"Email push failed (pipeline continues): {error}")


def run_ai_summary(config=None, client=None, now=None, sleep_fn=time.sleep):
    config = config or load_ai_config()
    if config is None:
        return False

    now = now or datetime.datetime.now(datetime.timezone.utc)
    state = read_state()
    if not is_summary_due(state, config.interval_hours, now):
        print("AI summary skipped: schedule is not due yet.")
        return False

    submitted_ids = set(state["submitted_ids"])
    feed_entries = load_all_feed_entries()
    candidates = [
        entry for entry in feed_entries if entry["id"] and entry["id"] not in submitted_ids
    ][: config.max_candidates]

    if not candidates:
        print("AI summary skipped: no new candidate papers.")
        return False

    # Group the (globally capped) candidates by their source journal so total
    # API cost stays bounded by max_candidates while output is per-journal.
    groups = {}
    for entry in candidates:
        slug = entry.get("feed_slug", "all")
        bucket = groups.setdefault(slug, {"name": entry.get("feed_name", slug), "entries": []})
        bucket["entries"].append(entry)

    print(
        f"Starting AI summary for {len(candidates)} candidate papers "
        f"across {len(groups)} journals..."
    )
    client = client or ChatCompletionClient(config)

    os.makedirs(FEED_DIR, exist_ok=True)
    run_info = {}
    processed_ids = set()
    email_sections = []
    generated_at = now.isoformat().replace("+00:00", "Z")
    try:
        for slug, bucket in sorted(groups.items()):
            report = generate_ai_summary_report(config, bucket["entries"], client, now, sleep_fn)
            html_file = ai_html_path(slug)
            feed_file = ai_feed_path(slug)
            write_ai_html(report, html_file, bucket["name"])
            write_ai_feed(report, feed_file, html_file, bucket["name"])
            run_info[slug] = {
                "name": bucket["name"],
                "selected": report["matched_count"],
                "candidates": len(bucket["entries"]),
            }
            email_sections.append({
                "name": bucket["name"],
                "selected": report["matched_count"],
                "candidates": len(bucket["entries"]),
                "html": report["html"],
            })
            processed_ids.update(entry["id"] for entry in bucket["entries"])
            print(f"  {html_file}: {report['matched_count']}/{len(bucket['entries'])} ({bucket['name']})")

        write_ai_index(build_ai_index(run_info), generated_at)
        write_email_body(email_sections, generated_at)
        send_email_digest(generated_at)
    except Exception as error:
        print(f"AI summary failed: {error}")
        return False

    # Migration: drop the legacy combined AI feed once per-journal feeds exist.
    if os.path.exists(OUTPUT_FEED_FILE):
        os.remove(OUTPUT_FEED_FILE)
        print(f"Removed legacy {OUTPUT_FEED_FILE}.")

    submitted_ids.update(processed_ids)
    write_state(
        {
            "last_success_at": now.isoformat().replace("+00:00", "Z"),
            "submitted_ids": sorted(submitted_ids),
        }
    )
    print(
        f"AI summary generated for {len(run_info)} journals "
        f"({len(processed_ids)} papers): index at {OUTPUT_HTML_FILE}"
    )
    return True


if __name__ == "__main__":
    run_ai_summary()
