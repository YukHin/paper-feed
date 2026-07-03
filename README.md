# Paper-Feed: 自动化文献精准筛选与推送系统

[![GitHub Actions](https://img.shields.io/badge/Actions-Automated-blue.svg)](https://github.com/features/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zotero Plugin](https://img.shields.io/badge/Zotero-Plugin-CC2936.svg?logo=zotero&logoColor=white)](zotero-plugin/)

### 系统概述
本工具是一个基于 GitHub Actions 的全自动文献监测系统。它旨在解决科研工作中的信息筛选效率问题，功能逻辑如下：
1.  **抓取**：定时从指定的期刊 RSS 源获取最新发表的论文。
2.  **筛选**：根据预设的关键词逻辑（支持 `AND` 组合）对标题和摘要进行匹配。
3.  **AI总结**：借助AI减轻手动翻阅订阅的负担，现在只需打开汇总网页扫一眼。
4.  **分发**：将命中的论文重组为标准化的 RSS 订阅源，供 Zotero 等阅读器订阅，如果你是Zotero用户，可能会对[插件版](https://github.com/Jarvis-Towne/paper-feed-zotero)感兴趣。

---

## 🛠 功能特性

*   **全自动运行**：无需服务器，利用 GitHub Actions 每 8 小时自动执行一次检索。
*   **多维度检索**：支持简单的关键词匹配及 `Keyword A AND Keyword B` 的组合逻辑检索。
*   **数据清洗**：内置 XML 字符清洗程序，自动移除非法字符，确保订阅源的兼容性与稳定性。
*   **隐私保护**：支持通过 GitHub Secrets 注入配置，隐藏用户的研究领域与关注列表。
*   **AI 总结（可选）**：支持调用 OpenAI 兼容接口，对新增命中文献生成中文 HTML 总结，并输出独立 RSS。

---

## 🚀 部署流程

### 1. 初始化项目
1.  点击本页面右上角的 **Fork**，将仓库复制到你的账号下。
2.  在你的仓库中，删除根目录下的 `filtered_feed.xml ai_summary_feed.xml ai_summary.html ai_summary_state.json` 文件（清除示例数据，可选）。

### 2. 配置参数

提供两种配置方式，**涉及未发表 Idea 或敏感方向建议使用方式 B**。

#### 方式 A：文件配置（公开可见）
直接编辑仓库中的以下文件：
*   `sources.dat`：填入期刊 RSS 链接（总抓取源清单），一行一个。
*   `keywords.dat`：填入筛选关键词，一行一个。
    *   示例：`Perovskite AND Stability`
*   `allowlist.dat`：直通名单，列出的期刊所有文章跳过关键词筛选、直接推送（优先级高于 keywords），一行一个期刊名或缩写。

#### 方式 B：环境变量配置（私密不可见）
1.  进入仓库 **Settings** -> **Secrets and variables** -> **Actions**。
2.  点击 **New repository secret** 添加以下两个变量：
    *   **Name**: `RSS_JOURNALS` | **Secret**: 填入期刊链接（换行分隔）。
    *   **Name**: `RSS_KEYWORDS` | **Secret**: 填入关键词（换行分隔）。

#### 可选：AI 总结配置

AI 总结默认不强制启用。只有当以下必需 Secrets 都存在时，`ai_summary.py` 才会在 GitHub Actions 中运行；否则会跳过，不影响普通 RSS。

*   **Name**: `AI_API_CONFIG` | **Secret**: 按顺序填写三行，分别是 Base URL、API Key、模型名：

    ```text
    https://api.openai.com/v1
    sk-***
    gpt-4.1-mini
    ```

*   **Name**: `AI_SUMMARY_PROMPT` | **Secret**: 你的研究方向，建议按重要性排序分行填写，可以是关键词、短句或者一句话。

#### 可选：邮件推送

在**生成了新的 AI 总结时**，把本次各期刊摘要全文邮件推送给你。邮件配置采用与期刊/关键词相同的私密方式（环境变量优先，其次本地文件 `email.dat`，`email.dat` 已在 `.gitignore` 中）。未配置时自动跳过，不影响其余流程。

推送节奏由 workflow 定时（默认每 6 小时）与 AI 总结的 `interval_hours` 共同决定：只有 AI 实际产出新总结时才发信。**若想每 6 小时都收到新内容，请把 `interval_hours` 也设为 6。**

*   **Name**: `EMAIL_CONFIG` | **Secret**: 按顺序填写，第 4 行可省略（默认 Gmail）：

    ```text
    收件人@example.com          # 可用逗号/分号分隔多个收件人
    你的Gmail地址@gmail.com      # 发件账号（SMTP 用户名）
    应用专用密码                 # Gmail 的 App Password（非登录密码）
    smtp.gmail.com:465          # 可选，SMTP 主机:端口，默认即此
    ```

    > Gmail 需在账号开启两步验证后，于「应用专用密码」页面生成一个 16 位密码填在第 3 行。其它邮箱（QQ/网易/Outlook 等）把第 2、3、4 行换成对应的账号、授权码与 `SMTP:端口` 即可。

非敏感参数在 `paper_feed_config.json` 中修改，无需删除或新增 GitHub Actions 变量：

```json
{
  "rss": {
    "fetch_interval_hours": 8
  },
  "ai_summary": {
    "enabled": true,
    "interval_hours": 24,
    "max_candidates": 100,
    "screening_batch_size": 10,
    "requests_per_minute": 5,
    "max_output_tokens": 0,
    "max_prompt_title_chars": 0,
    "max_prompt_abstract_chars": 0,
    "retry_attempts_per_round": 3,
    "retry_rounds": 2,
    "retry_sleep_seconds": 600
  }
}
```

其中：

`max_candidates` 每次生成html文件使用多少篇未使用的文献，没有总结过的会留到下次；

`screening_batch_size` 单次发送多少篇文献给AI总结，太多了考验AI上下文，可能会丢文献，太少了请求次数过多；

`requests_per_minute` 是 AI API 请求速率限制，默认 `5`，即相邻两次请求至少间隔约 12 秒；

`max_output_tokens`、`max_prompt_title_chars`、`max_prompt_abstract_chars` 用于避免输入输出过长、生成时间过久导致网关超时，默认为0，表示不限制。

AI 总结**同样按期刊分条**，每本期刊各自生成一份摘要，会生成：

*   `feeds/ai_summary.<slug>.html`：某本期刊最新一期的 AI 总结页面。
*   `feeds/ai_summary.<slug>.xml`：该期刊的 AI 总结订阅源。
*   `ai_summary.html`：AI 总结**索引页**（根目录），列出所有期刊的摘要页与订阅链接。
*   `ai_summary_state.json`：已总结文献和上次成功时间，用于避免重复提交给 AI。

> 为控制 API 成本，每次运行的候选文献总数仍受 `max_candidates` 限制，再按期刊拆分；因此只有本次有新文献的期刊会重新生成摘要，其余期刊保留上一期页面。

### 3. 启动服务
1.  **配置 Pages**：
    *   进入 **Settings** -> **Pages**。
    *   **Build and deployment** 下，Source 选择 `Deploy from a branch`。
    *   Branch 选择 `main` 分支的 `/(root)` 目录。
    *   点击 **Save**。
2.  **激活 Workflow**：
    *   进入 **Actions** 页面。
    *   若提示 "Workflows aren't being run..."，点击绿色按钮 **I understand my workflows, go ahead and enable them**。
    *   选中左侧 **Auto RSS Fetch** -> **Run workflow** 手动触发首次运行。

---

## 📈 客户端接入 (以 Zotero 为例)

命中的文献**按期刊分条输出**，所有分期刊订阅源都放在 `feeds/` 文件夹里（如 `feeds/filtered_feed.jacs.xml`）；索引页 `feeds.html`、`ai_summary.html` 仍在根目录。你可以只订阅关心的期刊，互不干扰。

1.  **查看订阅列表**：
    浏览器打开索引页，里面列出了每本期刊的订阅链接与命中数量：
    `https://{你的GitHub用户名}.github.io/{仓库名}/feeds.html`
    （机器可读版本为 `feeds.json`。）
2.  **获取单本期刊的订阅链接**：
    `https://{你的GitHub用户名}.github.io/{仓库名}/feeds/filtered_feed.<slug>.xml`
    例如 `feeds/filtered_feed.jacs.xml`、`feeds/filtered_feed.nat-commun.xml`。`slug` 由期刊标准缩写规范化而来，可在 `feeds.html`/`feeds.json` 里直接复制。
    若启用了 AI 总结，AI 也是**按期刊分条**的。索引页列出每本期刊的 AI 摘要页与订阅链接：
    `https://{你的GitHub用户名}.github.io/{仓库名}/ai_summary.html`
    单本期刊的 AI 订阅链接为 `.../feeds/ai_summary.<slug>.xml`，AI 摘要页为 `.../feeds/ai_summary.<slug>.html`。
    AI 总结同样提供一键批量订阅的 OPML（订阅名带 `· AI` 后缀以便区分），导入方式同下：
    `https://{你的GitHub用户名}.github.io/{仓库名}/ai_summary.opml`
3.  **添加订阅（单条）**：
    *   Zotero 菜单栏：`文件` -> `新建文献库` -> `新建订阅` -> `从网址`。
    *   粘贴某本期刊的订阅链接。订阅名会自动使用该期刊的规范名称（如 `JACS`、`Nat. Commun.`）。
4.  **一键批量订阅（推荐，OPML）**：
    *   本项目会自动生成 `feeds.opml`，里面包含**所有**分期刊源的绝对链接：
        `https://{你的GitHub用户名}.github.io/{仓库名}/feeds.opml`
    *   先把它下载到本地，然后在 Zotero 中：`文件` -> `导入…` -> 选择 `A file (BibTeX, RIS, Zotero RDF, etc.)` -> 选中下载的 `feeds.opml`。Zotero 会识别 OPML 并**一次性把所有期刊都加为订阅**。
    *   以后新增了期刊，重新导入一次 `feeds.opml` 即可补上新订阅。
    *   OPML 里的链接为绝对地址，由 GitHub Actions 自动按你的 Pages 地址生成；如果你的站点地址特殊，可在仓库 `Settings -> Secrets and variables -> Actions -> Variables` 里设置变量 `PAPER_FEED_PUBLIC_BASE_URL`（例如 `https://yourname.github.io/paper-feed`）来覆盖。
5.  **设置同步频率**：
    *   建议在 Zotero 订阅设置中将更新时间设为与 `fetch_interval_hours` 相同或更短，以匹配后端的更新频率。

> **迁移说明**：旧的合并订阅源 `filtered_feed.xml` 已停用，运行后会被自动拆分成上述分期刊源并删除。原来订阅了 `filtered_feed.xml` 的客户端需改订对应的分期刊链接。

### 🔌 预留接口：更换分条维度

分条逻辑集中在 `get_RSS.py` 顶部的 **grouper** 函数。默认按期刊分条（`group_by_journal`）。若以后想按别的维度分条（关键词专题、作者、年份……），只需新增一个同签名的函数——接收一条文献、返回若干 `(slug, 显示名)`（一条文献可进入多个订阅）——并把 `ACTIVE_GROUPER` 指过去即可，其余流程无需改动：

```python
def group_by_topic(entry):
    text = (entry["title"] + " " + entry["summary"]).lower()
    hits = []
    if "perovskite" in text:
        hits.append(("perovskite", "Perovskite"))
    if "catalysis" in text:
        hits.append(("catalysis", "Catalysis"))
    return hits or [("misc", "Misc")]

ACTIVE_GROUPER = group_by_topic
```

---

## 🧩 Zotero 插件：Paper-Feed Sync

除了手动订阅 / 导入 OPML，本仓库还内置了一个 Zotero 7/8/9 插件（目录 [`zotero-plugin/`](zotero-plugin/)），可以**自动**把分期刊源同步进你的文献库并按出版社归类。

**能做什么：**

*   读取站点的 `feeds.json`，得到全部期刊（后端新增期刊后自动跟进）。
*   在文献库里建立 **`Paper-Feed / 出版社 / 期刊`** 三层分类（如 `Paper-Feed / Wiley / Adv. Mater.`）。
*   定时（默认每 6 小时）抓取每个 `feeds/filtered_feed.<slug>.xml`，把**新**文献作为 `journalArticle` 存进对应分类，按 URL 去重（已存在的、以及你已加笔记的文献不会被覆盖）。
*   新拉取的文献自动打 **`unread`** 标签，便于筛未读。
*   同步后自动清理父分类下**完全没有文献**的空分类（安全，不删任何文献；可在设置中关闭）。

**安装：**

1.  下载 [`zotero-plugin/paper-feed-sync.xpi`](zotero-plugin/paper-feed-sync.xpi)。
2.  Zotero → `工具` → `插件` → 右上角齿轮 → **Install Add-on From File…** → 选择该 `.xpi`。

**配置与使用（`工具` 菜单）：**

*   **Paper-Feed：设置…** — 填写站点基址（如 `https://yukhin.github.io/paper-feed`，只填根地址）、更新间隔、父分类名、是否自动清理空分类。
*   **Paper-Feed：立即同步** — 手动触发一次。
*   **Paper-Feed：停止同步** — 中止正在进行的同步。
*   **Paper-Feed：禁用/启用自动同步** — 开关定时拉取。
*   **Paper-Feed：重建（清空后重新同步）** — 删掉整个父分类后按最新结构重建（不会删除文献与笔记）。

> 详细说明与常见问题见 [`zotero-plugin/README.md`](zotero-plugin/README.md)。去重是与「库里当前的文献」比对，因此手动删除且仍在源里的文献，下次同步会被重新拉回。

---

## 📖 期刊显示名称映射

Zotero 列表中的「出版物」列默认显示期刊的正式缩写（如 `JACS`、`PRB`、`Nat. Commun.`），标题列也会自动去除来源标注前缀（如 `[Journal of the American Chemical Society: Latest Articles (ACS Publications)] [ASAP]`）。

此功能由 `journal_map.py` 实现，**无需修改主程序**即可扩展。

### 新增期刊映射

在 `journal_map.py` 的 `JOURNAL_MAP` 列表末尾添加一条记录：

```python
{"prefix": "RSS 标题中方括号内的原始文字", "abbr": "期刊标准缩写"},
```

**如何获取 prefix？**

运行一次后，在生成的 `filtered_feed.xml` 中找任意一条该期刊的条目，`<author>` 标签内的文字即为对应的 prefix（在映射生效前，author 字段存储的就是 RSS 频道标题原文）。

**示例：**

```python
# 在 JOURNAL_MAP 列表末尾追加：
{"prefix": "ACS Catalysis: Latest Articles (ACS Publications)", "abbr": "ACS Catal."},
{"prefix": "Wiley: Chemistry of Materials: Table of Contents",  "abbr": "Chem. Mater."},
```

提交更改后，下次 GitHub Actions 运行时自动生效。

---

## ⚠️ 维护说明

1.  **关键词优化**：若订阅源中无关论文过多，请检查 `keywords.dat` 是否过于宽泛；若漏掉重要论文，请检查是否拼写错误或逻辑过严。
2.  **活跃度维持**：GitHub 可能会暂停长期无代码提交仓库的 Actions 定时任务。若发现停止更新，请进入 Actions 页面手动启用或提交一次空的 Commit。(真的吗，AI说的我也不知道)
3.  **解析失败**：部分期刊 RSS 格式不规范。若遇到特定期刊抓取失败，请检查其 RSS XML 结构的合法性。

## 友情链接

`https://linux.do/`
