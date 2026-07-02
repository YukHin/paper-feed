# Paper-Feed Sync（Zotero 7 插件）

把 paper-feed 生成的分期刊 RSS 源自动同步进 Zotero 文献库：

- 读取站点的 `feeds.json`，得到全部期刊列表（后端新增期刊后自动跟进）。
- 在 **My Library** 下建一个父分类（默认 `Paper-Feed`），并为每本期刊建一个子分类。
- 定时抓取每个 `feeds/filtered_feed.<slug>.xml`，把**新**文献作为 `journalArticle` 存进对应分类，按 URL 去重。

> ⚠️ v0.1：功能已按 Zotero 7 插件规范实现，但尚未在真实 Zotero 上充分测试，装上后可能需要一起调。

## 安装（开发/本地）

1. 把本目录下的三个文件 **`manifest.json`、`bootstrap.js`、`paperfeed.js`** 打包成一个 zip（注意这三个文件要在 zip 的**根目录**，不要多套一层文件夹），扩展名改为 `.xpi`：

   ```bash
   cd zotero-plugin
   zip -j paper-feed-sync.xpi manifest.json bootstrap.js paperfeed.js
   ```

2. Zotero → `工具` → `插件`（Add-ons）→ 右上角齿轮 → **Install Add-on From File…** → 选择 `paper-feed-sync.xpi`。

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

- **去重**按条目的 `url` 字段判断；paper-feed 的 RSS 里 `link` 即文献链接，作为唯一标识。
- 条目类型统一为 `journalArticle`，字段映射：标题→title、摘要（description 去标签）→abstractNote、期刊（dc:source）→publicationTitle、日期→date、链接→url。
- 不抓取 PDF 全文，只建题录（符合 RSS 源本身的内容）。
- 手动删除某条后，只要它仍在 RSS 源里且 URL 相同，就不会被重复拉回（因为按 URL 去重会命中你库里……被删后就不在库里了——如需“不再拉回”可后续加忽略名单，告诉我）。
- `manifest.json` 里的 `update_url` 是自动更新占位地址，本地安装可忽略。

## 后续可加（按需）

- 已读/忽略名单，避免删除后又被拉回。
- 也同步 AI 总结源（`feeds/ai_summary.<slug>.xml`）。
- 设置面板（目前用简单弹窗代替）。
