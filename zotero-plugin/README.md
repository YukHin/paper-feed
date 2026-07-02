# Paper-Feed Sync（Zotero 7/8/9 插件）

把 paper-feed 生成的分期刊 RSS 源自动同步进 Zotero 文献库：

- 读取站点的 `feeds.json`，得到全部期刊列表（后端新增期刊后自动跟进）。
- 在 **My Library** 下建立 **`Paper-Feed / 出版社 / 期刊`** 三层分类（如 `Paper-Feed / Wiley / Adv. Mater.`）。
- 定时抓取每个 `feeds/filtered_feed.<slug>.xml`，把**新**文献作为 `journalArticle` 存进对应分类。
- **去重**同时按 `url` 与 `DOI`（同一 DOI 视为同一篇，即使链接不同）。
- 尽力补全 **DOI**：先从链接/guid 提取（JACS/Wiley/Nature/APS），拿不到再用 **Crossref 按标题反查**（AIP/ScienceDirect），标题不匹配则留空不乱贴。
- 新拉取的文献自动打 **`unread`** 标签。
- 同步后自动清理父分类下**完全没有文献**的空分类（可关）。

> 已在 Zotero 9.0.4 实测可安装运行。当前为快速迭代版本，遇到问题请看 `帮助 → Debug Output Logging` 里 `[Paper-Feed]` 日志。

## 安装

仓库里已内置打包好的 **`paper-feed-sync.xpi`**，直接用即可：

1. 下载本目录下的 `paper-feed-sync.xpi`。
2. Zotero → `工具` → `插件`（Add-ons）→ 右上角齿轮 → **Install Add-on From File…** → 选择 `paper-feed-sync.xpi`。

改过源码后重新打包（三个文件须在 zip 根目录）：

```bash
cd zotero-plugin
zip -j paper-feed-sync.xpi manifest.json bootstrap.js paperfeed.js
```

## 配置

Zotero 菜单：`工具` → **Paper-Feed：设置…**，依次填写：

- **站点基址**：例如 `https://yukhin.github.io/paper-feed`（就是 `feeds.json` / `feeds/…` 所在的根地址）。
- **自动更新间隔（小时）**：默认 `6`。
- **父分类名称**：默认 `Paper-Feed`。

## 使用

- 配置好基址后，插件会在启动约 20 秒后同步一次，并按设定的间隔重复。
- 也可随时手动触发：`工具` → **Paper-Feed：立即同步**。
- 同步日志见 Zotero 的 `帮助` → `Debug Output Logging`，过滤 `[Paper-Feed]`。

## 说明与已知限制

- **去重**同时看 `url` 与 `DOI`，与"库里当前的条目"比对。因此手动删掉、但仍在源里的文献，下次同步会被**重新拉回**。若要"删了不再拉"，需加忽略名单（记录已删 URL/DOI）——要的话告诉我。
- 条目类型统一为 `journalArticle`，字段映射：标题→title、摘要（description 去标签）→abstractNote、期刊（dc:source）→publicationTitle、日期→date、链接→url、DOI→DOI。
- 不抓取 PDF 全文，只建题录（符合 RSS 源本身的内容）。
- Crossref 反查每篇最多一次网络请求，仅对链接推不出 DOI 的条目触发；可用 `lookupDoi` 关闭。

## 后续可加（按需）

- 已读/忽略名单，避免删除后又被拉回。
- 也同步 AI 总结源（`feeds/ai_summary.<slug>.xml`）。
- 图形化设置面板（目前用简单弹窗代替）。

## 更新历史（Changelog）

- **0.2.0** — 查重改用「父分类的直接子级」定位，彻底杜绝多次同步重复建分类。
- **0.1.9** — 缺失 DOI 时改用 **Crossref 按标题反查**（不受 Cloudflare 影响），带标题匹配校验防误贴。
- **0.1.8** — （已被 0.1.9 取代）尝试抓取文章页 `citation_doi` 元标签补 DOI。
- **0.1.7** — 去重**加入 DOI**（同 DOI 视为同一篇）。
- **0.1.6** — 从链接/guid **提取 DOI** 并写入条目（JACS/Wiley/Nature/APS）。
- **0.1.5** — 新增 **重建** 菜单（清空父分类后重新同步）。
- **0.1.4** — 同步后**自动清理空分类**（可关）。
- **0.1.3** — 分类改为 **`Paper-Feed / 出版社 / 期刊`** 三层。
- **0.1.2** — 新增 **停止同步 / 启停自动同步** 菜单；新条目打 **`unread`** 标签。
- **0.1.1** — 修复 Zotero 9 下 RSS 解析（改用 `DOMParser`），加同步诊断日志。
- **0.1.0** — 首个版本：读 `feeds.json`、按期刊建分类、定时同步、按 URL 去重、工具菜单。修复 Zotero 9 安装兼容（manifest 需 `update_url` 与 `strict_max_version`、去版本上限、合规 add-on id）。

> 相关后端改动（不影响插件版本）：期刊映射修正合并重复刊、标题统一 Title Case（介词小词不大写、保留缩略词）。
