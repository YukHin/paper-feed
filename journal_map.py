# =============================================================================
# journal_map.py  —  期刊 RSS 前缀 → 标准缩写 映射表
# =============================================================================
#
# 格式说明
# --------
# 每条记录是一个字典，包含两个键：
#   "prefix"  : RSS 条目标题中方括号内的完整原始字符串（支持精确匹配 & 模糊匹配）
#   "abbr"    : 在 Zotero「创建者」列中显示的期刊标准缩写
#
# 匹配优先级
# ----------
# 1. 精确匹配（strip 后完全相同）
# 2. 包含匹配（prefix 是 journal 字段的子串，大小写不敏感）
# 若两者均无命中，则回退到原始 journal 字段（不做任何修改）。
#
# 如何新增期刊
# ------------
# 在 JOURNAL_MAP 列表末尾追加一条字典即可，例如：
#   {"prefix": "ACS Catalysis: Latest Articles (ACS Publications)", "abbr": "ACS Catal."},
# 提交 PR 或直接推送到你的 fork 后，下次 GitHub Actions 运行时生效。
#
# =============================================================================

JOURNAL_MAP = [

    # ── arXiv ────────────────────────────────────────────────────────────────
    {"prefix": "cond-mat updates on arXiv.org",             "abbr": "arXiv"},
    {"prefix": "AI for Science - latest papers",            "abbr": "arXiv"},
    # arXiv API 检索源的频道标题是整串 "arXiv Query: search_query=..."，
    # 必须归一成 arXiv，否则查询串会被写进 dc:source（Zotero 的出版物字段）
    {"prefix": "arXiv Query",                               "abbr": "arXiv"},
    {"prefix": "ChemRxiv",                                  "abbr": "ChemRxiv"},

    # ── APS (American Physical Society) ──────────────────────────────────────
    {"prefix": "Recent Articles in Phys. Rev. B",           "abbr": "PRB"},
    {"prefix": "Recent Articles in Phys. Rev. Lett.",       "abbr": "PRL"},
    {"prefix": "Recent Articles in PRX Energy",             "abbr": "PRX Energy"},
    # 以下 APS 前缀来自按栏目分类的 RSS，前缀完全相同，统一映射
    # （如有需要，可拆分为更细粒度的条目）

    # ── Nature Portfolio ─────────────────────────────────────────────────────
    {"prefix": "Nature",                                    "abbr": "Nature"},
    {"prefix": "Nature Communications",                     "abbr": "Nat. Commun."},
    {"prefix": "Nature Energy",                             "abbr": "Nat. Energy"},
    {"prefix": "Nature Materials",                          "abbr": "Nat. Mater."},
    {"prefix": "Nature Nanotechnology",                     "abbr": "Nat. Nanotechnol."},
    {"prefix": "Nature Sensors",                            "abbr": "Nat. Sens."},
    {"prefix": "Nature Physics",                            "abbr": "Nat. Phys."},
    {"prefix": "Nature Reviews Materials",                  "abbr": "Nat. Rev. Mater."},
    {"prefix": "Nature Reviews Physics",                    "abbr": "Nat. Rev. Phys."},
    {"prefix": "Nature Chemical Engineering",               "abbr": "Nat. Chem. Eng."},
    {"prefix": "Nature Machine Intelligence",               "abbr": "Nat. Mach. Intell."},
    {"prefix": "npj Computational Materials",               "abbr": "npj Comput. Mater."},
    {"prefix": "Communications Materials",                  "abbr": "Commun. Mater."},
    {"prefix": "Communications Physics",                    "abbr": "Commun. Phys."},

    # ── Science / AAAS ────────────────────────────────────────────────────────
    {"prefix": "AAAS: Science: Table of Contents",          "abbr": "Science"},

    # ── ACS (American Chemical Society) ──────────────────────────────────────
    {"prefix": "Journal of the American Chemical Society: Latest Articles (ACS Publications)",
                                                            "abbr": "JACS"},
    {"prefix": "JACS Au: Latest Articles (ACS Publications)",
                                                            "abbr": "JACS Au"},
    {"prefix": "ACS Nano: Latest Articles (ACS Publications)",
                                                            "abbr": "ACS Nano"},
    {"prefix": "ACS Energy Letters: Latest Articles (ACS Publications)",
                                                            "abbr": "ACS Energy Lett."},
    {"prefix": "ACS Materials Letters: Latest Articles (ACS Publications)",
                                                            "abbr": "ACS Mater. Lett."},
    {"prefix": "Accounts of Materials Research: Latest Articles (ACS Publications)",
                                                            "abbr": "Acc. Mater. Res."},
    {"prefix": "Journal of Chemical Theory and Computation: Latest Articles (ACS Publications)",
                                                            "abbr": "JCTC"},
    {"prefix": "The Journal of Physical Chemistry Letters: Latest Articles (ACS Publications)",
                                                            "abbr": "J. Phys. Chem. Lett."},
    {"prefix": "The Journal of Physical Chemistry C: Latest Articles (ACS Publications)",
                                                            "abbr": "J. Phys. Chem. C"},

    # ── Wiley ─────────────────────────────────────────────────────────────────
    # 注意：Wiley 的 RSS 频道标题前缀既出现过 "Wiley:" 也出现过
    # "Wiley-Online-Library:"。get_abbr 用“包含”匹配，故这里去掉平台前缀，
    # 只保留 "<刊名>: Table of Contents"，两种平台写法都能命中，避免同刊被拆成两个源。
    {"prefix": "Advanced Materials: Table of Contents",     "abbr": "Adv. Mater."},
    {"prefix": "Advanced Energy Materials: Table of Contents",
                                                            "abbr": "Adv. Energy Mater."},
    {"prefix": "Advanced Functional Materials: Table of Contents",
                                                            "abbr": "Adv. Funct. Mater."},
    {"prefix": "Advanced Science: Table of Contents",       "abbr": "Adv. Sci."},
    {"prefix": "Advanced Intelligent Discovery: Table of Contents",
                                                            "abbr": "Adv. Intell. Discov."},
    {"prefix": "Angewandte Chemie International Edition: Table of Contents",
                                                            "abbr": "Angew. Chem. Int. Ed."},
    {"prefix": "Small Methods: Table of Contents",          "abbr": "Small Methods"},
    {"prefix": "Small Structures: Table of Contents",       "abbr": "Small Struct."},
    {"prefix": "Small: Table of Contents",                  "abbr": "Small"},
    {"prefix": "InfoMat: Table of Contents",                "abbr": "InfoMat"},
    {"prefix": "Carbon Energy: Table of Contents",          "abbr": "Carbon Energy"},
    {"prefix": "ENERGY &amp; ENVIRONMENTAL MATERIALS: Table of Contents",
                                                            "abbr": "Energy Environ. Mater."},
    {"prefix": "ENERGY & ENVIRONMENTAL MATERIALS: Table of Contents",
                                                            "abbr": "Energy Environ. Mater."},
    {"prefix": "Chinese Journal of Chemistry: Table of Contents",
                                                            "abbr": "Chin. J. Chem."},

    # ── AAAS (Science family) ──────────────────────────────────────────────────
    {"prefix": "Science Advances: Table of Contents",       "abbr": "Sci. Adv."},
    {"prefix": "Science Robotics: Table of Contents",       "abbr": "Sci. Robot."},

    # ── Taylor & Francis ───────────────────────────────────────────────────────
    {"prefix": "Materials Research Letters: Table of Contents",
                                                            "abbr": "Mater. Res. Lett."},

    # ── Elsevier / ScienceDirect ──────────────────────────────────────────────
    {"prefix": "ScienceDirect Publication: Joule",          "abbr": "Joule"},
    {"prefix": "ScienceDirect Publication: Matter",         "abbr": "Matter"},
    {"prefix": "ScienceDirect Publication: Acta Materialia","abbr": "Acta Mater."},
    {"prefix": "ScienceDirect Publication: Nano Energy",    "abbr": "Nano Energy"},
    {"prefix": "ScienceDirect Publication: Materials Today","abbr": "Mater. Today"},
    {"prefix": "ScienceDirect Publication: Materials Today Physics",
                                                            "abbr": "Mater. Today Phys."},
    {"prefix": "ScienceDirect Publication: Progress in Materials Science",
                                                            "abbr": "Prog. Mater. Sci."},
    {"prefix": "ScienceDirect Publication: Computational Materials Science",
                                                            "abbr": "Comput. Mater. Sci."},
    {"prefix": "ScienceDirect Publication: Journal of Energy Storage",
                                                            "abbr": "J. Energy Storage"},
    {"prefix": "ScienceDirect Publication: Journal of Catalysis",
                                                            "abbr": "J. Catal."},
    {"prefix": "ScienceDirect Publication: Journal of Materiomics",
                                                            "abbr": "J. Materiomics"},
    {"prefix": "ScienceDirect Publication: Current Opinion in Solid State and Materials Science",
                                                            "abbr": "Curr. Opin. Solid State Mater. Sci."},
    {"prefix": "ScienceDirect Publication: Solid State Ionics",
                                                            "abbr": "Solid State Ionics"},
    {"prefix": "ScienceDirect Publication: Science Bulletin","abbr": "Sci. Bull."},
    {"prefix": "ScienceDirect Publication: eScience",       "abbr": "eScience"},
    {"prefix": "ScienceDirect Publication: Artificial Intelligence Chemistry",
                                                            "abbr": "AI Chem."},
    {"prefix": "ScienceDirect Publication: Review of Materials Research",
                                                            "abbr": "Rev. Mater. Res."},

    # ── Cell Press ────────────────────────────────────────────────────────────
    {"prefix": "Joule",                                     "abbr": "Joule"},
    {"prefix": "Matter",                                    "abbr": "Matter"},
    {"prefix": "Chem",                                      "abbr": "Chem"},
    {"prefix": "Chem Catalysis",                            "abbr": "Chem Catal."},
    {"prefix": "iScience",                                  "abbr": "iScience"},
    {"prefix": "Newton",                                    "abbr": "Newton"},
    {"prefix": "Cell Reports Physical Science",             "abbr": "Cell Rep. Phys. Sci."},

    # ── Chinese Chemical Society ──────────────────────────────────────────────
    {"prefix": "Chinese Chemical Society: CCS Chemistry: Table of Contents",             
                                                            "abbr": "CCS Chemistry"},

    # ── AIP (American Institute of Physics) ───────────────────────────────────
    {"prefix": "APL Materials Current Issue",               "abbr": "APL Mater."},
    {"prefix": "APL Machine Learning Current Issue",        "abbr": "APL Mach. Learn."},
    {"prefix": "Applied Physics Letters Current Issue",     "abbr": "Appl. Phys. Lett."},
    {"prefix": "Applied Physics Reviews Current Issue",     "abbr": "Appl. Phys. Rev."},

    # ── RSC (Royal Society of Chemistry) ─────────────────────────────────────
    {"prefix": "RSC - Chem. Sci. latest articles",          "abbr": "Chem. Sci."},
    {"prefix": "RSC - Digital Discovery latest articles",   "abbr": "Digital Discovery"},

    # ── PNAS ─────────────────────────────────────────────────────────────────
    {"prefix": "Proceedings of the National Academy of Sciences: Physical Sciences",
                                                            "abbr": "PNAS"},
    {"prefix": "Proceedings of the National Academy of Sciences: Proceedings of the National Academy of Sciences: Table of Contents",
                                                            "abbr": "PNAS"},

    # ── Annual Reviews ────────────────────────────────────────────────────────
    # （如需添加，格式示例：）
    # {"prefix": "Annual Review of Condensed Matter Physics", "abbr": "Annu. Rev. Condens. Matter Phys."},
    # {"prefix": "Annual Review of Materials Science",        "abbr": "Annu. Rev. Mater. Sci."},
]


# =============================================================================
# 以下为内部工具函数，供 get_RSS.py 调用，无需手动修改
# =============================================================================

def _build_lookup():
    """构建两个查找表：精确匹配字典 & 有序子串列表。"""
    exact = {}
    contains = []
    for entry in JOURNAL_MAP:
        p = entry["prefix"]
        a = entry["abbr"]
        exact[p.strip()] = a              # 精确匹配（大小写敏感，与 RSS 原文保持一致）
        contains.append((p.lower(), a))   # 包含匹配（大小写不敏感）
    return exact, contains


_EXACT_LOOKUP, _CONTAINS_LOOKUP = _build_lookup()


def get_abbr(journal_raw: str) -> str:
    """
    根据 journal_raw（RSS 的 feed.title 字段）查找对应缩写。

    Parameters
    ----------
    journal_raw : str
        从 RSS 频道标题中获取的原始字符串，例如
        "Journal of the American Chemical Society: Latest Articles (ACS Publications)"

    Returns
    -------
    str
        命中时返回对应缩写（如 "JACS"）；未命中时返回原始 journal_raw。
    """
    stripped = journal_raw.strip()

    # 1. 精确匹配
    if stripped in _EXACT_LOOKUP:
        return _EXACT_LOOKUP[stripped]

    # 2. 包含匹配：prefix 是 journal_raw 的子串
    lower = stripped.lower()
    for prefix_lower, abbr in _CONTAINS_LOOKUP:
        if prefix_lower in lower:
            return abbr

    # 3. 未命中，返回原始值
    return journal_raw


# =============================================================================
# 出版社归属：把期刊缩写归到出版社，供“出版社 → 期刊”两层分类使用。
# key 用 get_abbr 得到的标准缩写；未列出的归入 "Other"。
# 新增期刊时在对应出版社的集合里补一个缩写即可。
# =============================================================================
PUBLISHER_MAP = {
    "Preprints": {"arXiv", "ChemRxiv"},
    "Nature Portfolio": {
        "Nature", "Nat. Commun.", "Nat. Energy", "Nat. Mater.", "Nat. Nanotechnol.",
        "Nat. Sens.", "Nat. Phys.", "Nat. Rev. Mater.", "Nat. Rev. Phys.",
        "Nat. Chem. Eng.", "Nat. Mach. Intell.", "npj Comput. Mater.",
        "Commun. Mater.", "Commun. Phys.", "Light: Science & Applications",
    },
    "Science/AAAS": {"Science", "Sci. Adv.", "Sci. Robot."},
    "ACS": {"JACS", "JACS Au", "ACS Nano", "JCTC", "J. Phys. Chem. C", "ACS Catal."},
    "Wiley": {
        "Adv. Mater.", "Adv. Energy Mater.", "Adv. Funct. Mater.", "Adv. Sci.",
        "Adv. Intell. Discov.", "Angew. Chem. Int. Ed.", "Small", "Small Methods",
        "Small Struct.", "InfoMat", "Carbon Energy", "Energy Environ. Mater.",
        "Chin. J. Chem.",
    },
    "APS": {"PRB", "PRL", "PRX", "PRX Energy", "Phys. Rev. Applied", "Phys. Rev. X"},
    "AIP": {"Appl. Phys. Lett.", "Appl. Phys. Rev.", "APL Energy Current Issue",
            "APL Mach. Learn."},
    "Cell Press": {"Chem", "Joule", "Matter", "Cell Rep. Phys. Sci.", "iScience"},
    "Elsevier": {
        "Nano Energy", "J. Catal.", "J. Energy Storage", "Mater. Today",
        "Mater. Today Phys.", "Comput. Mater. Sci.", "Solid State Ionics",
        "Sensors and Actuators A: Physical", "Prog. Mater. Sci.", "Acta Mater.",
        "J. Materiomics", "eScience", "Sci. Bull.", "Chinese Journal of Catalysis",
    },
    "RSC": {"Digital Discovery"},
    "Taylor & Francis": {"Mater. Res. Lett."},
    "PNAS": {"PNAS"},
}

# 反向索引：缩写 -> 出版社
_ABBR_TO_PUBLISHER = {abbr: pub for pub, abbrs in PUBLISHER_MAP.items() for abbr in abbrs}


def get_publisher(abbr: str) -> str:
    """根据标准缩写返回出版社名；未收录的归入 'Other'。"""
    return _ABBR_TO_PUBLISHER.get((abbr or "").strip(), "Other")


# 标题中保持小写的介词/冠词/并列连词（首词、末词除外，见 to_title_case）
_TITLE_MINOR_WORDS = {
    "a", "an", "the",
    "and", "but", "or", "nor", "for", "so", "yet",
    "as", "at", "by", "in", "of", "off", "on", "to", "up", "via",
    "per", "vs", "with", "from", "into", "onto", "over", "than", "that",
}


def _titlecase_word(word: str, force_lower: bool = False) -> str:
    """把单个词首字母大写，但保留缩略词/含大写或数字的原样（DNA、GaN、6G、FRET）。

    force_lower=True 时把普通小词整体小写（用于介词/冠词等，缩略词仍保留原样）。
    """
    if not word:
        return word
    # 已含内部大写（GaN、pH、DNA）或含数字（6G、Eu³⁺）→ 视为专有写法，保持原样
    if any(c.isupper() for c in word[1:]) or any(c.isdigit() for c in word):
        return word
    if force_lower:
        return word.lower()
    # 普通全小写/首字母词：首个字母大写，其余小写
    return word[:1].upper() + word[1:].lower() if word[:1].isalpha() else word


def to_title_case(title: str) -> str:
    """把标题规范成 Title Case：实词首字母大写，介词/冠词/并列连词小写；
    但首词与末词始终大写。保留缩略词与连字符结构。"""
    if not title:
        return title
    tokens = title.split()
    last = len(tokens) - 1
    out_words = []
    for i, token in enumerate(tokens):
        # 冒号/问号/句号等结束的前一个词之后，视作新句开头，强制大写
        after_break = i > 0 and tokens[i - 1].endswith((":", "?", "!", "."))
        # 仅当整个词是小词、且不在首/末位置、且不是新句开头时才小写
        minor = token.strip(".,;:!?()[]").lower() in _TITLE_MINOR_WORDS
        force_lower = minor and i != 0 and i != last and not after_break
        # 连字符片段分别处理（Machine-Learning）；小词判断按整词
        parts = token.split("-")
        out_words.append("-".join(_titlecase_word(p, force_lower) for p in parts))
    return " ".join(out_words)


def strip_bracket_tags(title: str) -> str:
    """移除标题开头残留的方括号标签，如 '[ASAP] '、'[Early View] '。"""
    import re
    return re.sub(r'^\s*(?:\[[^\]]*\]\s*)+', '', title).strip()


def clean_title(title: str, journal_raw: str) -> str:
    """
    移除 RSS 标题中形如 "[<journal_prefix>] " 或 "[<journal_prefix>] [ASAP] " 的前缀。

    同时处理：
    - ACS 的 [ASAP] 标签
    - 其他可能出现的方括号前缀（只移除与 journal_raw 相关的那个）

    Parameters
    ----------
    title      : str  RSS 条目原始标题
    journal_raw: str  该条目所属 feed 的频道标题

    Returns
    -------
    str  清理后的标题
    """
    import re

    # 把 journal_raw 中的正则特殊字符转义，以便安全地用于 re.escape
    escaped = re.escape(journal_raw.strip())

    # 模式：[<journal>] 或 [<journal>] [ASAP] 或 [<journal>] [任意标签]
    # 贪婪地移除所有位于论文真实标题之前的 [...] 块
    pattern = rf'^\[{escaped}\]\s*(?:\[[^\]]*\]\s*)*'
    cleaned = re.sub(pattern, '', title, flags=re.IGNORECASE).strip()

    # 若替换后为空（极端情况），回退原始标题
    return cleaned if cleaned else title
