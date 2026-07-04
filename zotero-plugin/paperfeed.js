/* Paper-Feed Sync — main logic.
 *
 * Reads feeds.json from a configurable base URL, ensures a collection per
 * journal under a parent collection, fetches each per-journal RSS feed, and
 * saves new papers as journalArticle items into the matching collection
 * (deduped by URL). Runs on startup and on a repeating timer.
 */

var PaperFeed = {
  PREF: "extensions.paperfeed.",
  _timer: null,
  _startupTimer: null,
  _windows: [],

  // ---- lifecycle ----

  init({ rootURI }) {
    this.rootURI = rootURI;
    this._setDefault("baseUrl", "");
    this._setDefault("intervalHours", 6);
    this._setDefault("parentCollection", "Paper-Feed");
    this._setDefault("enabled", true);
    this._setDefault("cleanup", true);
    this._setDefault("lookupDoi", true);
    this._setDefault("autoFetchPdf", false);  // fetch OA PDF during auto-sync
    this._setDefault("blockWords", "");       // 屏蔽词（清理用；空=不执行）

    // Expose the singleton so the preferences pane can call back into it
    // (e.g. restart the timer after the interval changes).
    Zotero.PaperFeed = this;

    // Register custom "Find Available PDF" resolvers (open-access publishers).
    this._registerPdfResolvers();

    for (const win of Zotero.getMainWindows()) this.addToWindow(win);
    this.restartTimer();

    // Kick off a first sync shortly after startup, if configured.
    if (this._getPref("enabled") !== false && this._getPref("baseUrl")) {
      this._startupTimer = this._oneShot(20 * 1000, () => this.syncNow());
    }
  },

  uninit() {
    this.stopTimer();
    if (this._startupTimer) { this._startupTimer.cancel(); this._startupTimer = null; }
    if (Zotero.PaperFeed === this) delete Zotero.PaperFeed;
    for (const win of Zotero.getMainWindows()) this.removeFromWindow(win);
  },

  // ---- prefs ----

  _getPref(key) { return Zotero.Prefs.get(this.PREF + key, true); },
  _setPref(key, value) { Zotero.Prefs.set(this.PREF + key, value, true); },
  _setDefault(key, value) {
    if (this._getPref(key) === undefined) this._setPref(key, value);
  },

  // ---- UI (Tools menu) ----

  addToWindow(window) {
    const doc = window.document;
    const popup = doc.getElementById("menu_ToolsPopup");
    if (!popup || doc.getElementById("paperfeed-sync-now")) return;

    const mkItem = (id, label, handler) => {
      const item = doc.createXULElement("menuitem");
      item.id = id;
      item.setAttribute("label", label);
      item.addEventListener("command", handler);
      popup.appendChild(item);
      return item;
    };

    mkItem("paperfeed-sync-now", "Paper-Feed：立即同步", () => {
      this.syncNow().catch((e) => this._log("sync error: " + e));
    });
    mkItem("paperfeed-stop", "Paper-Feed：停止同步", () => this.stopSync());
    mkItem("paperfeed-rebuild", "Paper-Feed：重建（清空后重新同步）", () => {
      this.rebuild(window).catch((e) => this._log("rebuild error: " + e));
    });
    mkItem("paperfeed-cleanup-kw", "Paper-Feed：按屏蔽词清理题录", () => {
      this.cleanupByBlockWords(window).catch((e) => this._log("cleanup error: " + e));
    });
    this._toggleItem = mkItem("paperfeed-toggle", this._autoLabel(), () => {
      this.toggleAuto();
    });

    // Right-click context menu on selected items: fetch open-access PDF.
    this.addItemMenu(window);
  },

  removeFromWindow(window) {
    const doc = window.document;
    for (const id of ["paperfeed-sync-now", "paperfeed-stop", "paperfeed-rebuild", "paperfeed-cleanup-kw", "paperfeed-toggle"]) {
      const el = doc.getElementById(id);
      if (el) el.remove();
    }
    this.removeItemMenu(window);
  },

  // Add a "抓取 PDF" entry to the item list's right-click menu (zotero-itemmenu).
  addItemMenu(window) {
    const doc = window.document;
    const popup = doc.getElementById("zotero-itemmenu");
    if (!popup || doc.getElementById("paperfeed-fetch-pdf")) return;
    const item = doc.createXULElement("menuitem");
    item.id = "paperfeed-fetch-pdf";
    item.setAttribute("label", "Paper-Feed：抓取 PDF（开放获取）");
    item.addEventListener("command", () => {
      this.fetchPdfForSelected(window).catch((e) => this._log("fetch pdf error: " + e));
    });
    popup.appendChild(item);
  },

  removeItemMenu(window) {
    const el = window.document.getElementById("paperfeed-fetch-pdf");
    if (el) el.remove();
  },

  _autoLabel() {
    return this._getPref("enabled") === false
      ? "Paper-Feed：启用自动同步"
      : "Paper-Feed：禁用自动同步";
  },

  _refreshToggleLabels() {
    for (const win of Zotero.getMainWindows()) {
      const el = win.document.getElementById("paperfeed-toggle");
      if (el) el.setAttribute("label", this._autoLabel());
    }
  },

  // Delete the whole Paper-Feed parent collection (and its subtree), then
  // re-sync from scratch. Items are NOT deleted — erasing a collection only
  // removes the grouping. Asks for confirmation first.
  async rebuild(window) {
    if (this._syncing) { this._notify("正在同步中，请先停止再重建"); return; }
    const parentName = this._getPref("parentCollection") || "Paper-Feed";
    const ok = Services.prompt.confirm(
      window, "Paper-Feed 重建",
      "将删除分类 “" + parentName + "” 及其下所有子分类，然后重新同步。\n" +
      "（不会删除任何文献，只是取消其在这些分类中的归类；你添加的笔记/标签也会保留。）\n\n确定继续？"
    );
    if (!ok) return;

    const libraryID = Zotero.Libraries.userLibraryID;
    const parent = this._findCollection(libraryID, parentName, null);
    if (parent) {
      try {
        await parent.eraseTx();  // recursively erases subcollections too
        this._log("rebuild: erased parent collection " + parentName);
      } catch (e) {
        this._notify("删除父分类失败：" + (e && e.message ? e.message : e));
        return;
      }
    }
    this._abort = false;
    await this.syncNow();
  },

  // Trash every feed-synced item under the parent collection whose title +
  // abstract contains any user-defined block word (设置 → 屏蔽词). Scope is
  // strictly the parent subtree, so items you filed elsewhere (Survey /
  // Papers / …) are never touched. Items go to Zotero's Trash (recoverable),
  // not erased. If no block words are set, the action does nothing (by design).
  async cleanupByBlockWords(window) {
    if (this._syncing) { this._notify("正在同步中，请先停止再清理"); return; }

    const blocks = this._parseKeywords(this._getPref("blockWords") || "");
    if (!blocks.length) {
      this._notify("未设置屏蔽词：请在 设置 → Paper-Feed 里填写后再执行（未设置不清理）");
      return;
    }

    const libraryID = Zotero.Libraries.userLibraryID;
    const parentName = this._getPref("parentCollection") || "Paper-Feed";
    const parent = this._findCollection(libraryID, parentName, null);
    if (!parent) { this._notify("未找到父分类 “" + parentName + "”"); return; }

    // Gather unique regular items across the whole parent subtree.
    const items = new Map();
    this._collectItems(parent, items);

    const toTrash = [];
    for (const it of items.values()) {
      let text = "";
      try {
        text = (it.getField("title") || "") + " " + (it.getField("abstractNote") || "");
      } catch (e) {}
      if (this._matchKeywords(text, blocks)) toTrash.push(it.id);  // hits a block word
    }

    if (!toTrash.length) {
      this._notify("没有命中屏蔽词的题录，无需清理");
      return;
    }
    const ok = Services.prompt.confirm(
      window, "Paper-Feed 按屏蔽词清理",
      "将把 “" + parentName + "” 下 " + toTrash.length + " 条命中屏蔽词的题录移入" +
      "回收站（可在 Zotero 回收站恢复）。\n共扫描 " + items.size + " 条，屏蔽词 " +
      blocks.length + " 条。\n\n确定继续？"
    );
    if (!ok) return;

    try {
      if (Zotero.Items.trashTx) {
        await Zotero.Items.trashTx(toTrash);
      } else {
        for (const id of toTrash) {
          const it = Zotero.Items.get(id);
          if (it) { it.deleted = true; await it.saveTx(); }
        }
      }
      this._log("cleanup: trashed " + toTrash.length + " items by block words");
      this._notify("已移入回收站 " + toTrash.length + " 条命中屏蔽词的题录");
    } catch (e) {
      this._notify("清理失败：" + (e && e.message ? e.message : e));
    }
  },

  // Recursively collect regular items in a collection subtree into `acc`
  // (Map id -> item), so an item filed in multiple subcollections counts once.
  _collectItems(coll, acc) {
    try {
      for (const it of coll.getChildItems(false, false)) {
        if (it.isRegularItem && it.isRegularItem()) acc.set(it.id, it);
      }
    } catch (e) {}
    const children = coll.getChildCollections ? coll.getChildCollections() : [];
    for (const child of children) this._collectItems(child, acc);
  },

  // Parse a textarea/word list: one term per non-comment line; "AND" splits a
  // line into substrings that must all be present. Mirrors the backend matcher.
  _parseKeywords(text) {
    return String(text || "")
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && l[0] !== "#");
  },

  _matchKeywords(text, queries) {
    text = (text || "").toLowerCase();
    for (const q of queries) {
      const parts = q.split("AND").map((s) => s.trim().toLowerCase()).filter(Boolean);
      if (parts.length && parts.every((p) => text.indexOf(p) !== -1)) return true;
    }
    return false;
  },

  // Abort an in-progress sync and cancel the pending startup sync.
  stopSync() {
    this._abort = true;
    if (this._startupTimer) { this._startupTimer.cancel(); this._startupTimer = null; }
    this._notify("已请求停止：当前同步将在处理完当前条目后中止");
  },

  // Toggle the repeating auto-sync on/off (persisted).
  toggleAuto() {
    const nowEnabled = this._getPref("enabled") !== false;
    this._setPref("enabled", !nowEnabled);
    if (nowEnabled) {
      this.stopTimer();
      this._abort = true;
      this._notify("已禁用自动同步（不再定时拉取）");
    } else {
      this.restartTimer();
      this._notify("已启用自动同步，每 " + (this._getPref("intervalHours") || 6) + " 小时一次");
    }
    this._refreshToggleLabels();
  },

  // ---- timer ----

  restartTimer() {
    this.stopTimer();
    if (this._getPref("enabled") === false) return;
    const hours = parseFloat(this._getPref("intervalHours")) || 6;
    this._timer = Components.classes["@mozilla.org/timer;1"]
      .createInstance(Components.interfaces.nsITimer);
    this._timer.initWithCallback(
      { notify: () => this.syncNow().catch((e) => this._log("sync error: " + e)) },
      Math.round(hours * 3600 * 1000),
      Components.interfaces.nsITimer.TYPE_REPEATING_SLACK
    );
  },

  stopTimer() {
    if (this._timer) { this._timer.cancel(); this._timer = null; }
  },

  _oneShot(ms, fn) {
    const t = Components.classes["@mozilla.org/timer;1"]
      .createInstance(Components.interfaces.nsITimer);
    t.initWithCallback({ notify: () => fn().catch((e) => this._log("error: " + e)) },
      ms, Components.interfaces.nsITimer.TYPE_ONE_SHOT);
    return t;
  },

  // ---- core sync ----

  async syncNow() {
    if (this._syncing) { this._notify("已有同步在进行中"); return; }
    const base = (this._getPref("baseUrl") || "").replace(/\/+$/, "");
    if (!base) { this._notify("请先在 工具 → Paper-Feed：设置 里填写站点基址"); return; }

    this._syncing = true;
    this._abort = false;
    try {
    const libraryID = Zotero.Libraries.userLibraryID;
    const parentName = this._getPref("parentCollection") || "Paper-Feed";
    this._notify("开始同步…");

    const parent = await this._ensureCollection(libraryID, parentName, null);
    const index = await this._fetchJSON(base + "/feeds.json");
    const feeds = (index && index.feeds) || [];

    const existing = await this._getExisting(libraryID);
    let added = 0;
    const pubCache = {};  // publisher name -> collection, so we make each once

    for (const f of feeds) {
      if (this._abort) { this._log("sync aborted by user"); break; }
      let coll;
      try {
        // Nest as: <parent> / <publisher> / <journal>. Journals with no known
        // publisher (or older feeds.json without the field) fall back to being
        // a direct child of <parent>.
        let journalParent = parent;
        const publisher = f.publisher;
        if (publisher) {
          if (!pubCache[publisher]) {
            pubCache[publisher] = await this._ensureCollection(libraryID, publisher, parent);
          }
          journalParent = pubCache[publisher];
        }
        coll = await this._ensureCollection(libraryID, f.name, journalParent);
        const xml = await this._fetchText(this._joinUrl(base, f.file));
        const papers = this._parseRss(xml);
        let feedAdded = 0;
        for (const p of papers) {
          if (this._abort) break;
          if (p.url && existing.urls.has(p.url)) continue;  // already have this URL
          // DOI from the feed/URL; if none, look it up on Crossref by title
          // (AIP, ScienceDirect… don't expose a DOI in the RSS or URL).
          let doi = p.doi ? this._normDoi(p.doi) : "";
          if (!doi && p.title && this._getPref("lookupDoi") !== false) {
            doi = this._normDoi(await this._fetchDoiFromCrossref(p.title, p.journal));
            if (doi) p.doi = doi;
          }
          if (!p.url && !doi) continue;
          if (doi && existing.dois.has(doi)) continue;  // same DOI = same paper
          const created = await this._createItem(libraryID, coll.id, p);
          // Optionally fetch the open-access PDF right after creating the item.
          if (created && this._getPref("autoFetchPdf") === true) {
            try { await this._resolvePdf(created); }
            catch (e) { this._log("auto pdf fetch failed: " + (e && e.message ? e.message : e)); }
          }
          if (p.url) existing.urls.add(p.url);
          if (doi) existing.dois.add(doi);
          added++;
          feedAdded++;
        }
        this._log("feed " + f.name + ": parsed " + papers.length + ", added " + feedAdded);
      } catch (e) {
        this._log("feed failed (" + (f && f.name) + "): " + (e && e.message ? e.message : e));
      }
    }

    let cleaned = 0;
    if (!this._abort && this._getPref("cleanup") !== false) {
      cleaned = await this._cleanupEmpty(parent);
    }

    this._notify(
      (this._abort ? "同步已停止，" : "同步完成，") + "新增 " + added + " 条文献" +
      (cleaned ? "，清理空分类 " + cleaned + " 个" : "")
    );
    this._log("sync done, added " + added + ", cleaned " + cleaned);
    } finally {
      this._syncing = false;
    }
  },

  // Recursively delete collections under `parent` whose entire subtree has no
  // items. Scope is strictly inside the Paper-Feed parent; the parent itself is
  // never deleted. Deleting an (empty) collection never removes any item.
  async _cleanupEmpty(parent) {
    let removed = 0;
    const prune = async (coll) => {
      let hasItems = false;
      try {
        hasItems = coll.getChildItems(false, false).length > 0;
      } catch (e) {
        hasItems = true;  // be conservative: unknown => keep
      }
      const children = coll.getChildCollections ? coll.getChildCollections() : [];
      for (const child of children) {
        if (await prune(child)) hasItems = true;
      }
      if (!hasItems) {
        try {
          await coll.eraseTx();
          removed++;
          this._log("removed empty collection: " + coll.name);
        } catch (e) {
          this._log("failed to remove collection " + coll.name + ": " + e);
          return true;  // couldn't delete => treat as non-empty so ancestor stays
        }
      }
      return hasItems;
    };
    // Prune each child of the parent; never delete the parent itself.
    const topChildren = parent.getChildCollections ? parent.getChildCollections() : [];
    for (const child of topChildren) {
      await prune(child);
    }
    return removed;
  },

  // ---- Zotero data helpers ----

  // Find a collection named `name` directly under `parentColl` (a Collection
  // object), or among top-level collections when parentColl is null. Looking
  // only at the specific parent's direct children (getChildCollections) avoids
  // relying on getByLibrary's recursive flag and makes duplicates impossible.
  _findCollection(libraryID, name, parentColl) {
    const siblings = parentColl
      ? parentColl.getChildCollections()
      : Zotero.Collections.getByLibrary(libraryID).filter((c) => !c.parentID);
    for (const c of siblings) {
      if (c.name === name) return c;
    }
    return null;
  },

  async _ensureCollection(libraryID, name, parentColl) {
    const existing = this._findCollection(libraryID, name, parentColl);
    if (existing) return existing;
    const c = new Zotero.Collection();
    c.libraryID = libraryID;
    c.name = name;
    if (parentColl) c.parentID = parentColl.id;
    await c.saveTx();
    return c;
  },

  // Collect existing identifiers so we can skip papers already in the library:
  // both by URL and by DOI (same DOI = same article, even if the URL differs).
  async _getExisting(libraryID) {
    const urls = new Set();
    const dois = new Set();
    const s = new Zotero.Search();
    s.libraryID = libraryID;
    s.addCondition("itemType", "isNot", "attachment");
    s.addCondition("itemType", "isNot", "note");
    const ids = await s.search();
    const items = await Zotero.Items.getAsync(ids);
    for (const it of items) {
      try { const u = it.getField("url"); if (u) urls.add(u); } catch (e) {}
      try { const d = it.getField("DOI"); if (d) dois.add(this._normDoi(d)); } catch (e) {}
    }
    return { urls, dois };
  },

  _normDoi(doi) {
    return String(doi || "")
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\/(dx\.)?doi\.org\//, "")
      .replace(/^doi:/, "");
  },

  async _createItem(libraryID, collectionID, p) {
    const item = new Zotero.Item("journalArticle");
    item.libraryID = libraryID;
    if (p.title) item.setField("title", p.title);
    if (p.abstract) item.setField("abstractNote", p.abstract);
    if (p.url) item.setField("url", p.url);
    if (p.journal) item.setField("publicationTitle", p.journal);
    if (p.date) item.setField("date", p.date);
    if (p.doi) item.setField("DOI", p.doi);
    item.setCollections([collectionID]);
    item.addTag("unread");  // mark freshly pulled papers as unread
    await item.saveTx();
    return item;
  },

  // ---- fetch + parse ----

  async _fetchText(url) {
    const xhr = await Zotero.HTTP.request("GET", url, { responseType: "text" });
    return xhr.responseText;
  },

  async _fetchJSON(url) {
    return JSON.parse(await this._fetchText(url));
  },

  _joinUrl(base, file) {
    return base.replace(/\/+$/, "") + "/" + String(file).replace(/^\/+/, "");
  },

  _parseRss(xml) {
    // nsIDOMParser (XPCOM) was removed in modern Gecko (Zotero 9), so build a
    // DOMParser from the main window instead.
    const win = Zotero.getMainWindow();
    let parser;
    if (win && win.DOMParser) {
      parser = new win.DOMParser();
    } else {
      parser = Components.classes["@mozilla.org/xmlextras/domparser;1"].createInstance();
    }
    const doc = parser.parseFromString(xml, "text/xml");
    if (doc.documentElement && doc.documentElement.nodeName === "parsererror") {
      throw new Error("XML parse error");
    }
    const nodes = doc.getElementsByTagName("item");
    const out = [];
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const get = (tag) => {
        const el = node.getElementsByTagName(tag)[0];
        return el && el.textContent ? el.textContent.trim() : "";
      };
      const link = get("link");
      const guid = get("guid") || link;
      out.push({
        title: get("title"),
        url: link,
        guid: guid,
        abstract: this._stripHtml(get("description")),
        journal: this._normalizeJournal(get("dc:source") || get("source") || get("author")),
        date: this._normalizeDate(get("pubDate")),
        doi: get("prism:doi") || get("dc:identifier") || this._extractDoi(guid, link),
      });
    }
    return out;
  },

  // Guard against raw feed-channel titles leaking into publicationTitle, e.g.
  // arXiv API feeds titled "arXiv Query: search_query=...".
  _normalizeJournal(name) {
    if (/^arxiv\b/i.test((name || "").trim())) return "arXiv";
    return name;
  },

  // Derive a DOI from the item's guid/link. Most publishers embed it directly
  // (JACS dx.doi.org/…, Wiley guid = bare DOI, APS link.aps.org/doi/…); Nature
  // article URLs let us reconstruct it as 10.1038/<article-id>. ScienceDirect
  // PII links carry no DOI, so those return "".
  _extractDoi(guid, link) {
    for (const s of [guid, link]) {
      if (!s) continue;
      const m = s.match(/\b(10\.\d{4,9}\/[^\s"'<>?#&]+)/);
      if (m) return m[1].replace(/[.,;)]+$/, "");
    }
    const nature = (link || "").match(/nature\.com\/articles\/([^/?#]+)/);
    if (nature) return "10.1038/" + nature[1];
    return "";
  },

  // Fallback: look the DOI up on Crossref by title. Pure JSON API (not blocked
  // by Cloudflare). The top candidates are validated against our title so we
  // never attach a wrong DOI. Returns "" on any failure/no confident match.
  async _fetchDoiFromCrossref(title, journal) {
    const q = this._normTitle(title);
    if (q.length < 12) return "";  // too short to match confidently
    const url = "https://api.crossref.org/works?rows=5&select=DOI,title,container-title"
      + "&query.bibliographic=" + encodeURIComponent(title)
      + "&mailto=paper-feed-sync@users.noreply.github.com";
    try {
      const xhr = await Zotero.HTTP.request("GET", url, {
        responseType: "text",
        timeout: 20000,
        headers: { "User-Agent": "paper-feed-sync (Zotero plugin)" },
      });
      const data = JSON.parse(xhr.responseText || "{}");
      const items = (data.message && data.message.items) || [];
      for (const it of items) {
        const cand = this._normTitle((it.title && it.title[0]) || "");
        if (!cand) continue;
        // Accept only a strong title match (equal, or one contains the other
        // with >=90% length overlap) so we don't attach a wrong DOI.
        const shorter = cand.length < q.length ? cand : q;
        const longer = cand.length < q.length ? q : cand;
        if (cand === q || (longer.indexOf(shorter) !== -1 &&
            shorter.length / longer.length >= 0.9)) {
          if (it.DOI && /10\.\d{4,9}\//.test(it.DOI)) return it.DOI;
        }
      }
    } catch (e) {
      this._log("Crossref lookup failed for \"" + (title || "").slice(0, 40) +
        "\": " + (e && e.message ? e.message : e));
    }
    return "";
  },

  _normTitle(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/&[a-z]+;/g, " ")   // strip html entities
      .replace(/[^a-z0-9]+/g, "")  // keep only alphanumerics
      .trim();
  },

  _stripHtml(s) {
    if (!s) return "";
    return s
      .replace(/<[^>]*>/g, " ")
      .replace(/&nbsp;/g, " ")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/\s+/g, " ")
      .trim();
  },

  _normalizeDate(s) {
    if (!s) return "";
    const d = new Date(s);
    return isNaN(d.getTime()) ? s : d.toISOString().slice(0, 10);
  },

  // ---- PDF fetch (right-click + custom resolvers) ----

  // Merge our custom "Find Available PDF" resolvers into Zotero's global pref
  // (extensions.zotero.findPDFs.resolvers), deduped by name so we never
  // clobber the user's own resolvers and never pile up duplicates on restart.
  // One generic resolver scrapes the DOI landing page's <meta
  // name="citation_pdf_url"> tag — the standard Highwire/Google-Scholar meta
  // that Nature (incl. Nature Sensors), PNAS, Science, AAAS, etc. all emit,
  // pointing straight at the article PDF.
  _registerPdfResolvers() {
    const KEY = "findPDFs.resolvers";  // -> extensions.zotero.findPDFs.resolvers
    let arr = [];
    try {
      const raw = Zotero.Prefs.get(KEY);
      if (raw) arr = JSON.parse(raw);
      if (!Array.isArray(arr)) arr = [];
    } catch (e) { arr = []; }

    const ours = [
      {
        name: "Paper-Feed: citation_pdf_url",
        method: "GET",
        url: "https://doi.org/{doi}",
        mode: "html",
        selector: "meta[name='citation_pdf_url']",
        attribute: "content",
        automatic: false,
      },
    ];
    const ourNames = new Set(ours.map((r) => r.name));
    const kept = arr.filter((r) => r && !ourNames.has(r.name));
    try {
      Zotero.Prefs.set(KEY, JSON.stringify(kept.concat(ours)));
      this._log("registered PDF resolvers (" + ours.length + ")");
    } catch (e) {
      this._log("resolver register failed: " + (e && e.message ? e.message : e));
    }
  },

  // Fetch a PDF for each selected regular item and attach it. Uses Zotero's
  // native resolver engine first (built-in OA/DOI + our custom resolver),
  // then falls back to publisher-direct URLs for Nature Portfolio and PNAS.
  async fetchPdfForSelected(window) {
    const pane = window.ZoteroPane ||
      (Zotero.getActiveZoteroPane && Zotero.getActiveZoteroPane());
    let items = (pane && pane.getSelectedItems) ? pane.getSelectedItems() : [];
    items = items.filter((it) => it.isRegularItem && it.isRegularItem());
    if (!items.length) { this._notify("请先选中至少一条文献"); return; }

    this._notify("开始抓取 " + items.length + " 条的 PDF…");
    let ok = 0, have = 0, fail = 0;
    for (const item of items) {
      try {
        if (this._hasPdf(item)) { have++; continue; }
        const got = await this._resolvePdf(item);
        if (got) ok++; else fail++;
      } catch (e) {
        fail++;
        this._log("fetch pdf failed for item " + item.id + ": " +
          (e && e.message ? e.message : e));
      }
    }
    this._notify("抓取完成：成功 " + ok + "，已有 " + have + "，未找到 " + fail);
  },

  _hasPdf(item) {
    try {
      for (const id of item.getAttachments()) {
        const att = Zotero.Items.get(id);
        if (att && att.attachmentContentType === "application/pdf") return true;
      }
    } catch (e) {}
    return false;
  },

  async _resolvePdf(item) {
    // 1) Zotero's native engine: built-in OA (Unpaywall/DOI) + our resolver.
    try {
      if (Zotero.Attachments.addAvailablePDF) {
        const att = await Zotero.Attachments.addAvailablePDF(item);
        if (att) return att;
      }
    } catch (e) {
      this._log("native addAvailablePDF: " + (e && e.message ? e.message : e));
    }

    // 2) Publisher-direct fallback (open resources: Nature Portfolio, PNAS).
    const doi = this._normDoi(item.getField("DOI"));
    const url = item.getField("url") || "";
    const journal = (item.getField("publicationTitle") || "").toLowerCase();
    for (const c of this._pdfCandidates(doi, url, journal)) {
      const att = await this._downloadAndAttach(item, c.url, c.referer);
      if (att) return att;
    }

    // 3) PMC / EuropePMC (open access) — covers PNAS and other PMC-deposited
    // papers whose publisher site blocks direct PDF downloads.
    const pmc = await this._tryPmc(item, doi);
    if (pmc) return pmc;

    return null;
  },

  // Build candidate direct-PDF URLs from the item's DOI/URL/journal.
  _pdfCandidates(doi, url, journal) {
    const out = [];
    // arXiv (always OA): https://arxiv.org/pdf/<id>.pdf  — handles new ids
    // (2401.12345v2) and legacy ids (cond-mat/0611292), from the abs/pdf URL
    // or a 10.48550/arXiv.<id> DOI.
    let axId = "";
    const ax = url.match(/arxiv\.org\/(?:abs|pdf)\/([^?#]+)/i);
    if (ax) axId = ax[1].replace(/\.pdf$/i, "");
    else if (doi.indexOf("10.48550/arxiv.") === 0) axId = doi.slice("10.48550/arxiv.".length);
    if (axId) {
      out.push({
        url: "https://arxiv.org/pdf/" + axId + ".pdf",
        referer: "https://arxiv.org/",
      });
    }
    // Nature Portfolio: https://www.nature.com/articles/<id>.pdf
    const nm = url.match(/nature\.com\/articles\/([^/?#]+)/);
    const natId = nm ? nm[1]
      : (doi.indexOf("10.1038/") === 0 ? doi.slice("10.1038/".length) : "");
    if (natId) {
      out.push({
        url: "https://www.nature.com/articles/" + natId + ".pdf",
        referer: "https://www.nature.com/",
      });
    }
    // Science / AAAS family (Science, Sci. Adv., Sci. Robot., Sci. Transl.
    // Med., Sci. Immunol., Sci. Signal.): all live on science.org, which is
    // Cloudflare-gated and hands HTML to anonymous bots. We still try the
    // direct PDF because Zotero's request carries the user's cookies — so it
    // succeeds when they have entitlement (campus/login) or the article is
    // free; otherwise the %PDF check discards the HTML and we fall through to
    // the PMC/EuropePMC route (which covers Sci. Adv. and NIH-deposited work).
    if (doi.indexOf("10.1126/") === 0) {
      out.push({
        url: "https://www.science.org/doi/pdf/" + doi + "?download=true",
        referer: "https://www.science.org/",
      });
    }
    // Note: PNAS' own site (pnas.org) is likewise Cloudflare-gated, so we don't
    // hit it directly — PNAS is deposited in PMC and handled by the
    // PMC/EuropePMC fallback in _resolvePdf instead.
    return out;
  },

  // DOI -> PMCID (NCBI ID converter) -> EuropePMC "render" PDF endpoint, which
  // (unlike pnas.org / ncbi.nlm.nih.gov) serves the raw PDF to plain requests.
  // Covers PNAS and the many other papers deposited in PubMed Central.
  async _tryPmc(item, doi) {
    if (!doi) return null;
    let pmcid = "";
    try {
      const u = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?format=json" +
        "&tool=paper-feed-sync&email=paper-feed-sync@users.noreply.github.com" +
        "&ids=" + encodeURIComponent(doi);
      const xhr = await Zotero.HTTP.request("GET", u, { responseType: "text", timeout: 20000 });
      const data = JSON.parse(xhr.responseText || "{}");
      const rec = (data.records || [])[0] || {};
      pmcid = rec.pmcid || "";
    } catch (e) {
      this._log("PMCID lookup failed: " + (e && e.message ? e.message : e));
      return null;
    }
    if (!pmcid) return null;
    return await this._downloadAndAttach(
      item, "https://europepmc.org/articles/" + pmcid + "?pdf=render",
      "https://europepmc.org/");
  },

  // Download bytes, verify the %PDF magic (paywalls hand back HTML), write to a
  // temp file and import as a child attachment. Returns the attachment or null.
  async _downloadAndAttach(item, pdfUrl, referer) {
    let buf;
    try {
      const xhr = await Zotero.HTTP.request("GET", pdfUrl, {
        responseType: "arraybuffer",
        timeout: 60000,
        headers: referer ? { Referer: referer } : {},
      });
      buf = xhr.response;
    } catch (e) {
      this._log("pdf GET failed " + pdfUrl + ": " + (e && e.message ? e.message : e));
      return null;
    }
    const bytes = new Uint8Array(buf);
    if (bytes.length < 5 || bytes[0] !== 0x25 || bytes[1] !== 0x50 ||
        bytes[2] !== 0x44 || bytes[3] !== 0x46) {  // "%PDF"
      this._log("not a PDF (likely paywall/HTML): " + pdfUrl);
      return null;
    }
    let path;
    try {
      const dir = Zotero.getTempDirectory().path;
      path = PathUtils.join(dir, "paperfeed-" + item.id + "-" + Date.now() + ".pdf");
      await IOUtils.write(path, bytes);
      const att = await Zotero.Attachments.importFromFile({
        file: path,
        parentItemID: item.id,
        contentType: "application/pdf",
        title: "Full Text PDF",
      });
      this._log("attached PDF from " + pdfUrl);
      return att;
    } catch (e) {
      this._log("attach failed " + pdfUrl + ": " + (e && e.message ? e.message : e));
      return null;
    } finally {
      if (path) { try { await IOUtils.remove(path); } catch (e) {} }
    }
  },

  // ---- misc ----

  _notify(msg) {
    try {
      const pw = new Zotero.ProgressWindow();
      pw.changeHeadline("Paper-Feed");
      pw.addDescription(msg);
      pw.show();
      pw.startCloseTimer(4000);
    } catch (e) {
      this._log(msg);
    }
  },

  _log(msg) {
    Zotero.debug("[Paper-Feed] " + msg);
  },
};
