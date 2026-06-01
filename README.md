# Paper-Feed: 自动化文献精准筛选与推送系统

[![GitHub Actions](https://img.shields.io/badge/Actions-Automated-blue.svg)](https://github.com/features/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
*   `journals.dat`：填入期刊 RSS 链接，一行一个。
*   `keywords.dat`：填入筛选关键词，一行一个。
    *   示例：`Perovskite AND Stability`

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

AI 总结会生成：

*   `ai_summary_feed.xml`：AI 总结订阅源。
*   `ai_summary.html`：最新一期 AI 总结 HTML 页面。
*   `ai_summary_state.json`：已总结文献和上次成功时间，用于避免重复提交给 AI。

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

1.  **获取订阅链接**：
    `https://{你的GitHub用户名}.github.io/{仓库名}/filtered_feed.xml`
    若启用了 AI 总结，AI 订阅链接为：
    `https://{你的GitHub用户名}.github.io/{仓库名}/ai_summary_feed.xml`
    当然你也可以直接在浏览器访问：
    `https://{你的GitHub用户名}.github.io/{仓库名}/ai_summary.html`
2.  **添加订阅**：
    *   Zotero 菜单栏：`文件` -> `新建文献库` -> `新建订阅` -> `从网址`。
    *   粘贴上述链接。
3.  **设置同步频率**：
    *   建议在 Zotero 订阅设置中将更新时间设为与 `fetch_interval_hours` 相同或更短，以匹配后端的更新频率。

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
