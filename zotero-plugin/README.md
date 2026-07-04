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
d
## 安装

仓库里已内置打包好的 **`paper-feed-sync.xpi`**，直接用即可：

1. 下载本目录下的 `paper-feed-sync.xpi`。
2. Zotero → `工具` → `插件`（Add-ons）→ 右上角齿轮 → **Install Add-on From File…** → 选择 `paper-feed-sync.xpi`。

改过源码后重新打包（所有文件须在 zip 根目录）：

```bash
cd zotero-plugin
zip -j paper-feed-sync.xpi manifest.json bootstrap.js paperfeed.js prefs.xhtml prefs.js icon@48.png icon@96.png
```

## 配置

设置在 **Zotero 的 设置（Settings/偏好设置）→ Paper-Feed** 面板里（不再放工具菜单）：

- **站点基址**：例如 `https://yukhin.github.io/paper-feed`（就是 `feeds.json` / `feeds/…` 所在的根地址）。
- **自动更新间隔（小时）**：默认 `6`。
- **父分类名称**：默认 `Paper-Feed`。
- **同步后自动清理空分类** / **同步时自动抓取开放获取 PDF**（开关）。
- **屏蔽词**：手动输入，供「按屏蔽词清理题录」使用；**留空则不执行清理**。

## 使用

- 配置好基址后，插件会在启动约 20 秒后同步一次，并按设定的间隔重复。
- 手动操作在 `工具` 菜单：**立即同步 / 停止 / 重建 / 按屏蔽词清理题录 / 启停自动同步**。
- 同步日志见 Zotero 的 `帮助` → `Debug Output Logging`，过滤 `[Paper-Feed]`。

### 按屏蔽词清理题录

在 设置 → Paper-Feed 的**屏蔽词**里每行填一个词（同一行用 `AND` 表示需同时包含），然后 `工具` → **Paper-Feed：按屏蔽词清理题录**。插件会把**父分类子树内**标题或摘要命中屏蔽词的题录**移入回收站**（可恢复，删前弹窗确认数量）；只在 Feed Inbox 范围内操作，不碰你自己的分类。**未设置屏蔽词则不执行。**

### 手动添加论文（feed 没抓到的）

**右键任意分类** → **Paper-Feed：添加论文（DOI/链接）**，输入 **DOI**（推荐，自动从 Crossref 补全标题/作者/期刊/日期/摘要）或文章**链接**，然后选择归入哪里：

- **① 直接加到当前分类**；
- **📡 feed 订阅期刊**：列出 `feeds.json` 里的所有订阅期刊（即使还没拉到论文、分类尚未创建），选中会按 `父分类 / 出版社 / 期刊` 建好并放入 —— 正好用于「订阅关注、但 feed 暂时没抓到」的论文；
- **＋ 自定义预设子分类**（设置里可配）。

新条目按 URL/DOI 去重，打 `manual` 标签（不会被屏蔽词清理误删）。

### 抓取开放获取 PDF（右键）

在条目列表里**选中一条或多条**文献 → **右键** → **Paper-Feed：抓取 PDF（开放获取）**。插件会：

1. 先走 Zotero 原生「查找可用 PDF」引擎（内置开放获取 / Unpaywall + 下述自定义解析器）；
2. 再走出版商 / 开放获取直链兜底，下载后校验 `%PDF` 魔数（防止把付费墙 HTML 存成假 PDF），通过才作为子附件挂到条目上：
   - **arXiv**：`arxiv.org/pdf/<id>.pdf`（纯 OA，最稳）；
   - **Nature Portfolio（正刊 + 子刊，含 Nature Sensors / Nature Communications）**：`nature.com/articles/<id>.pdf`（OA 直接抓；付费文章需你有访问权限）；
   - **Science / AAAS（正刊 + Sci. Adv. / Sci. Robot. / Sci. Transl. Med. 等子刊）**：`science.org/doi/pdf/<doi>`。science.org 有 Cloudflare 反爬，**匿名抓不到**（魔数校验会丢弃 HTML）；但 Zotero 请求带你的 cookie，**校园网/已登录时可下**，OA 的则靠下面的 PMC 兜底；
   - **PMC / EuropePMC**：DOI →（NCBI）PMCID → `europepmc.org/articles/<PMCID>?pdf=render`。**PNAS、Science Advances 等走这条**（这些站点本身反爬、直链拿不到，但都存进 PMC），同时覆盖大量 NIH 资助、已进 PubMed Central 的文章；
3. 已有 PDF 附件的条目自动跳过，最后弹窗汇报「成功 / 已有 / 未找到」。

插件启动时会向 Zotero 的 `extensions.zotero.findPDFs.resolvers` 注册一条通用解析器（抓 DOI 落地页的 `<meta name="citation_pdf_url">`，覆盖 Nature、PNAS、Science 等多数出版商），按名字去重、不覆盖你已有的解析器。因此 Zotero 自带的**右键 →「查找可用的 PDF」**也会一并受益。

> 仅解析**开放获取 / 合法公开**资源，不含 Sci-Hub 等；付费且无 OA 版本的文章仍抓不到（会计入「未找到」）。

## 说明与已知限制

- **去重**同时看 `url` 与 `DOI`，与"库里当前的条目"比对。因此手动删掉、但仍在源里的文献，下次同步会被**重新拉回**。若要"删了不再拉"，需加忽略名单（记录已删 URL/DOI）——要的话告诉我。
- 条目类型统一为 `journalArticle`，字段映射：标题→title、摘要（description 去标签）→abstractNote、期刊（dc:source）→publicationTitle、日期→date、链接→url、DOI→DOI。
- **自动同步只建题录、不抓 PDF**（符合 RSS 源本身的内容）；PDF 需**手动右键抓取**（见上）。
- Crossref 反查每篇最多一次网络请求，仅对链接推不出 DOI 的条目触发；可用 `lookupDoi` 关闭。

## 后续可加（按需）

- 已读/忽略名单，避免删除后又被拉回。
- 也同步 AI 总结源（`feeds/ai_summary.<slug>.xml`）。
- 图形化设置面板（目前用简单弹窗代替）。

## 更新历史（Changelog）

- **0.7.0** — 同步时显示**进度条**：读取索引 → 逐个期刊（第 n/总数、当前刊名、累计新增）→ 清理空分类 → 完成，进度实时更新。
- **0.6.2** — 手动添加论文的目标可从 **feed 订阅期刊列表**（`feeds.json`）里选：即使该期刊还没拉到论文、分类尚未创建，选中也会按 `父分类/出版社/期刊` 建好并放入。仍可选「直接加到当前分类」或自定义预设。
- **0.6.1** — 手动添加论文时，目标分类可从**预设子分类名**里选（设置 → Paper-Feed 可自定义，默认「手动收藏/待读/重点关注」），选中的名字若不存在会自动在当前分类下创建；也可选「直接加到当前分类」。
- **0.6.0** — 新增**手动添加论文**：右键左侧分类 → `Paper-Feed：添加论文（DOI/链接）到此分类`，输入 DOI（Crossref 补全标题/作者/期刊/日期/摘要）或链接，建到该分类下，按 URL/DOI 去重、打 `manual` 标签。用于补 feed 没抓到、但你想收的论文。
- **0.5.1** — 修复设置面板不保存/不回显：绑定脚本改为外部 `prefs.js`（面板内联 `<script>` 被 CSP 拦截而未运行），经 `PreferencePanes.register({scripts})` 加载。
- **0.5.0** — 设置移入 **Zotero 设置面板**（不再用工具菜单弹窗）；清理改为**按手动输入的屏蔽词**（命中标题/摘要即移入回收站，**未设置不执行**）；新增插件**图标**（液态玻璃风）。
- **0.4.0** — 新增按关键词清理题录：把**父分类子树内**不匹配的题录**移入回收站**（可恢复，删前弹窗确认）；仅在 Feed Inbox 范围内操作，不碰你自己的分类。（0.5.0 起改为按屏蔽词。）
- **0.3.0** — 新增**右键抓取开放获取 PDF**：注册 `citation_pdf_url` 自定义解析器到 Zotero「查找可用 PDF」，条目右键「Paper-Feed：抓取 PDF」调用原生引擎，直链兜底覆盖 **arXiv / Nature Portfolio（含 Nature Sensors）/ PMC·EuropePMC（PNAS 等）**，`%PDF` 魔数校验后挂附件；可选**同步时自动抓取**（`autoFetchPdf`，默认关）。
- **0.2.1** — 出版物字段兜底归一：`dc:source` 若是 arXiv API 频道原始标题（`arXiv Query: search_query=...`），统一写成 `arXiv`。
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
