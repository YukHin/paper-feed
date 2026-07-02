import feedparser
import re
import os
import glob
import json
import html
import datetime
import time
from rfeed import Item, Feed, Guid, Serializable
from email.utils import parsedate_to_datetime
from journal_map import get_abbr, clean_title


class DcSource(Serializable):
    """
    rfeed extension that writes <dc:source>value</dc:source> into an RSS item.
    Zotero reads this as the publicationTitle (出版物) field.
    The dc namespace (xmlns:dc=...) is already declared by rfeed's Feed._get_attributes().
    """

    def __init__(self, source):
        Serializable.__init__(self)
        self.source = source

    def publish(self, handler):
        Serializable.publish(self, handler)
        self._write_element("dc:source", self.source)

# --- 配置区域 ---
OUTPUT_DIR = "feeds"                     # 所有分期刊订阅源统一放到这个文件夹
FEED_PREFIX = "filtered_feed"            # 每本期刊输出 feeds/filtered_feed.<slug>.xml
LEGACY_FEED_FILE = "filtered_feed.xml"   # 旧的合并订阅源，迁移后删除
FEEDS_INDEX_JSON = "feeds.json"          # 机器可读的订阅索引（仍放在根目录）
FEEDS_INDEX_HTML = "feeds.html"          # 人可读的订阅索引页（仍放在根目录）
MAX_ITEMS = 1000                         # 每本期刊最多保留的条目数
# ----------------


def slugify(value):
    """把期刊缩写转成文件名/URL 安全的 slug，例如 'Nat. Commun.' -> 'nat-commun'。"""
    value = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return value.strip("-") or "unknown"


# --- 分组维度（预留接口）---
# 每个 grouper 接收一条文献，返回若干 (slug, 显示名)；一条文献可进入多个订阅。
# 以后要按别的维度分条（关键词专题、作者、年份……），只需新增一个同签名的
# 函数并把 ACTIVE_GROUPER 指过去，下面的主流程完全不用改。
# RSS 频道标题里常见的“平台/出版商”前缀与“栏目”后缀，都不是期刊名本身，需剔除。
# 形如 "ScienceDirect Publication: <期刊>: <栏目>" / "AAAS: <期刊>: Table of Contents"。
_TITLE_NOISE = {
    "sciencedirect publication", "aaas", "wiley-online-library",
    "wiley online library", "wiley", "tandf", "acs publications",
    "table of contents", "latest articles", "most recent", "current issue",
}


def display_name(journal_raw):
    """得到规范的期刊订阅名。

    命中 journal_map 时返回标准缩写（如 'JACS'）。未命中时，RSS 频道标题通常是
    '<平台>: <期刊名>: <栏目>' 结构，这里剥掉平台前缀与栏目后缀，只保留期刊名，
    避免订阅名出现 'ScienceDirect Publication: ...: Table of Contents' 这类冗长字样。
    """
    name = (get_abbr(journal_raw or "") or "").strip()
    if name.lower().startswith("arxiv"):          # arXiv / "arXiv Query: ..." 统一
        return "arXiv"
    name = re.sub(r"^\s*Recent Articles in\s+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)  # 去掉末尾的 (出版商)

    segments = [s.strip() for s in re.split(r"[:：]", name) if s.strip()]
    meaningful = [s for s in segments if s.lower() not in _TITLE_NOISE]
    # 期刊名可能自带冒号（如 'Sensors and Actuators A: Physical'），用 ': ' 重新拼回
    name = ": ".join(meaningful) if meaningful else (": ".join(segments) if segments else name)
    return name.strip() or (journal_raw or "").strip() or "Unknown"


def group_by_journal(entry):
    """按期刊标准缩写（journal_map）分组。"""
    name = display_name(entry.get("journal", ""))
    return [(slugify(name), name)]


ACTIVE_GROUPER = group_by_journal


def feed_path(slug):
    return os.path.join(OUTPUT_DIR, f"{FEED_PREFIX}.{slug}.xml")

def load_config(filename, env_var_name=None):
    """(保持你之前的 load_config 代码不变)"""
    # ... 请保留你之前为了隐私修改过的 load_config 函数 ...
    # 这里为了篇幅省略，请直接复用你现在的 load_config
    if env_var_name and os.environ.get(env_var_name):
        print(f"Loading config from environment variable: {env_var_name}")
        content = os.environ[env_var_name]
        if '\n' in content:
            return [line.strip() for line in content.split('\n') if line.strip()]
        else:
            return [line.strip() for line in content.split(';') if line.strip()]
            
    if os.path.exists(filename):
        print(f"Loading config from local file: {filename}")
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
    return []

# --- 新增：XML 非法字符清洗函数 ---
def remove_illegal_xml_chars(text):
    """
    移除 XML 1.0 不支持的 ASCII 控制字符 (Char value 0-8, 11-12, 14-31)
    """
    if not text:
        return ""
    # 正则表达式：匹配 ASCII 0-8, 11, 12, 14-31 这些控制字符
    # \x09是tab, \x0a是换行, \x0d是回车，这些是合法的，所以不删
    illegal_chars = r'[\x00-\x08\x0b\x0c\x0e-\x1f]'
    return re.sub(illegal_chars, '', text)

def convert_struct_time_to_datetime(struct_time):
    if not struct_time:
        return datetime.datetime.now()
    return datetime.datetime.fromtimestamp(time.mktime(struct_time))

def parse_rss(rss_url, retries=3):
    # (保持不变)
    print(f"Fetching: {rss_url}...")
    for attempt in range(retries):
        try:
            feed = feedparser.parse(rss_url)
            entries = []
            journal_title = feed.feed.get('title', 'Unknown Journal')
            
            for entry in feed.entries:
                pub_struct = entry.get('published_parsed', entry.get('updated_parsed'))
                pub_date = convert_struct_time_to_datetime(pub_struct)
                
                entries.append({
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'pub_date': pub_date,
                    'summary': entry.get('summary', entry.get('description', '')),
                    'journal': journal_title,
                    'id': entry.get('id', entry.get('link', ''))
                })
            return entries
        except Exception as e:
            print(f"Error parsing {rss_url}: {e}")
            time.sleep(2)
    return []

def _parse_feed_file(path):
    """读取单个本地订阅源文件，返回条目列表（读不了则返回空）。"""
    entries = []
    try:
        feed = feedparser.parse(path)
        if getattr(feed, 'bozo', 0) == 1:
            print(f"Warning: {path} might be corrupted; reading what we can.")
        for entry in feed.entries:
            pub_struct = entry.get('published_parsed')
            pub_date = convert_struct_time_to_datetime(pub_struct)
            entries.append({
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'pub_date': pub_date,
                'summary': entry.get('summary', ''),
                'journal': entry.get('dc_source', '') or entry.get('author', ''),
                'id': entry.get('id', entry.get('link', '')),
                'is_old': True
            })
    except Exception as e:
        print(f"Error reading {path}: {e}")
    return entries


def get_existing_items():
    """读取已有的所有分期刊订阅源（含旧的合并源，用于平滑迁移），按 id 去重。"""
    # 当前位置：feeds/ 下的分期刊源；外加根目录下的旧文件（合并源、上一版分期刊源）用于迁移
    paths = sorted(glob.glob(os.path.join(OUTPUT_DIR, f"{FEED_PREFIX}.*.xml")))
    paths += sorted(glob.glob(f"{FEED_PREFIX}.*.xml"))
    if os.path.exists(LEGACY_FEED_FILE) and LEGACY_FEED_FILE not in paths:
        paths.append(LEGACY_FEED_FILE)

    seen = set()
    entries = []
    for path in paths:
        print(f"Loading existing items from {path}...")
        for entry in _parse_feed_file(path):
            if entry['id'] in seen:
                continue
            seen.add(entry['id'])
            entries.append(entry)
    return entries

def match_entry(entry, queries):
    # (保持不变)
    text_to_search = (entry['title'] + " " + entry['summary']).lower()
    for query in queries:
        keywords = [k.strip().lower() for k in query.split('AND')]
        match = True
        for keyword in keywords:
            if keyword not in text_to_search:
                match = False
                break
        if match:
            return True
    return False

def _build_feed_xml(title, items):
    """把一组文献渲染成 RSS 2.0 XML 字符串 (已加入非法字符清洗)。返回 (xml, 条目数)。"""
    items.sort(key=lambda x: x['pub_date'], reverse=True)
    items = items[:MAX_ITEMS]

    rss_items = []
    for item in items:
        raw_journal = item['journal']
        # 新旧条目一致处理：清理标题前缀，并把 journal 映射为标准缩写
        item_title   = remove_illegal_xml_chars(clean_title(item['title'], raw_journal))
        clean_summary = remove_illegal_xml_chars(item['summary'])
        item_author  = remove_illegal_xml_chars(get_abbr(raw_journal))

        rss_items.append(Item(
            title = item_title,
            link = item['link'],
            description = clean_summary,
            guid = Guid(item['id']),
            pubDate = item['pub_date'],
            extensions = [DcSource(item_author)]
        ))

    feed = Feed(
        # 频道标题 = 期刊标准缩写，Zotero/阅读器会直接用它作为订阅名，保持规范
        title = title,
        link = "https://github.com/your_username/your_repo",
        description = f"Filtered papers from {title}",
        language = "en-US",
        lastBuildDate = datetime.datetime.now(),
        items = rss_items
    )
    return feed.rss(), len(rss_items)


def write_index(index):
    """生成 feeds.json 与 feeds.html 两个订阅索引。"""
    payload = {
        'generated': datetime.datetime.now().isoformat(timespec='seconds'),
        'feeds': index,
    }
    with open(FEEDS_INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    rows = "\n".join(
        f'    <li><a href="{html.escape(f["file"])}">{html.escape(f["name"])}</a>'
        f' <span class="count">({f["count"]})</span></li>'
        for f in index
    )
    page = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paper-Feed 订阅列表</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.6}}
h1{{font-size:1.4rem}}
ul{{list-style:none;padding:0}}
li{{padding:.4rem 0;border-bottom:1px solid #eee}}
a{{text-decoration:none;color:#0b62d6}}
.count{{color:#999;font-size:.9em}}
.meta{{color:#999;font-size:.85em}}
</style>
</head>
<body>
<h1>Paper-Feed 分期刊订阅</h1>
<p class="meta">共 {len(index)} 本期刊 · 更新于 {payload['generated']}</p>
<p>把下面任意链接作为 RSS 地址加入 Zotero / 阅读器，即可单独订阅该期刊。</p>
<ul>
{rows}
</ul>
</body>
</html>
"""
    with open(FEEDS_INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(page)


def generate_feeds(items):
    """按当前分组维度（ACTIVE_GROUPER）把命中文献拆成多个订阅源，并生成索引。"""
    groups = {}  # slug -> {'name': 显示名, 'items': [...]}
    for item in items:
        for slug, display in ACTIVE_GROUPER(item):
            bucket = groups.setdefault(slug, {'name': display, 'items': []})
            bucket['items'].append(item)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    index = []
    for slug, bucket in sorted(groups.items()):
        xml, count = _build_feed_xml(bucket['name'], bucket['items'])
        path = feed_path(slug)
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        index.append({'slug': slug, 'name': bucket['name'], 'file': path, 'count': count})
        print(f"  {path}: {count} items ({bucket['name']})")

    write_index(index)

    # 迁移：删除根目录下的旧订阅源（合并源 filtered_feed.xml 与上一版位于根目录的
    # 分期刊源），它们现已移动到 OUTPUT_DIR/，避免继续对外服务过期/重复数据
    for stale in glob.glob(f"{FEED_PREFIX}*.xml"):
        os.remove(stale)
        print(f"Removed stale root feed {stale}.")

    print(f"Successfully generated {len(index)} per-journal feeds in {OUTPUT_DIR}/.")

def main():
    # 请确保这里的调用参数与你目前的 secrets 配置一致
    rss_urls = load_config('journals.dat', 'RSS_JOURNALS')
    queries = load_config('keywords.dat', 'RSS_KEYWORDS')
    
    if not rss_urls or not queries:
        print("Error: Configuration files are empty or missing.")
        return

    existing_entries = get_existing_items()
    seen_ids = set(entry['id'] for entry in existing_entries)
    
    all_entries = existing_entries.copy()
    new_count = 0

    print("Starting RSS fetch from remote...")
    for url in rss_urls:
        fetched_entries = parse_rss(url)
        for entry in fetched_entries:
            if entry['id'] in seen_ids:
                continue
            
            if match_entry(entry, queries):
                all_entries.append(entry)
                seen_ids.add(entry['id'])
                new_count += 1
                print(f"Match found: {entry['title'][:50]}...")

    print(f"Added {new_count} new entries.")
    generate_feeds(all_entries)

if __name__ == '__main__':
    main()