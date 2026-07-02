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
    this._toggleItem = mkItem("paperfeed-toggle", this._autoLabel(), () => {
      this.toggleAuto();
    });
    mkItem("paperfeed-settings", "Paper-Feed：设置…", () => this.openSettings(window));
  },

  removeFromWindow(window) {
    const doc = window.document;
    for (const id of ["paperfeed-sync-now", "paperfeed-stop", "paperfeed-toggle", "paperfeed-settings"]) {
      const el = doc.getElementById(id);
      if (el) el.remove();
    }
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

  openSettings(window) {
    const ps = Services.prompt;
    const base = { value: this._getPref("baseUrl") || "" };
    if (!ps.prompt(window, "Paper-Feed 设置",
      "站点基址（例如 https://yukhin.github.io/paper-feed）", base, null, {})) return;
    this._setPref("baseUrl", (base.value || "").trim().replace(/\/+$/, ""));

    const iv = { value: String(this._getPref("intervalHours") || 6) };
    if (ps.prompt(window, "Paper-Feed 设置", "自动更新间隔（小时）", iv, null, {})) {
      const n = parseFloat(iv.value);
      if (n > 0) this._setPref("intervalHours", n);
    }

    const parent = { value: this._getPref("parentCollection") || "Paper-Feed" };
    if (ps.prompt(window, "Paper-Feed 设置", "父分类名称", parent, null, {})) {
      if (parent.value.trim()) this._setPref("parentCollection", parent.value.trim());
    }

    this.restartTimer();
    this._notify("设置已保存");
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

    const existingUrls = await this._getExistingUrls(libraryID);
    let added = 0;
    const pubCache = {};  // publisher name -> collection, so we make each once

    for (const f of feeds) {
      if (this._abort) { this._log("sync aborted by user"); break; }
      let coll;
      try {
        // Nest as: <parent> / <publisher> / <journal>. Journals with no known
        // publisher (or older feeds.json without the field) fall back to being
        // a direct child of <parent>.
        let journalParentID = parent.id;
        const publisher = f.publisher;
        if (publisher) {
          if (!pubCache[publisher]) {
            pubCache[publisher] = await this._ensureCollection(libraryID, publisher, parent.id);
          }
          journalParentID = pubCache[publisher].id;
        }
        coll = await this._ensureCollection(libraryID, f.name, journalParentID);
        const xml = await this._fetchText(this._joinUrl(base, f.file));
        const papers = this._parseRss(xml);
        let feedAdded = 0;
        for (const p of papers) {
          if (this._abort) break;
          if (!p.url || existingUrls.has(p.url)) continue;
          await this._createItem(libraryID, coll.id, p);
          existingUrls.add(p.url);
          added++;
          feedAdded++;
        }
        this._log("feed " + f.name + ": parsed " + papers.length + ", added " + feedAdded);
      } catch (e) {
        this._log("feed failed (" + (f && f.name) + "): " + (e && e.message ? e.message : e));
      }
    }

    this._notify((this._abort ? "同步已停止，" : "同步完成，") + "新增 " + added + " 条文献");
    this._log("sync done, added " + added);
    } finally {
      this._syncing = false;
    }
  },

  // ---- Zotero data helpers ----

  async _ensureCollection(libraryID, name, parentID) {
    const all = Zotero.Collections.getByLibrary(libraryID, true);
    for (const c of all) {
      const sameParent = parentID ? c.parentID === parentID : !c.parentID;
      if (c.name === name && sameParent) return c;
    }
    const c = new Zotero.Collection();
    c.libraryID = libraryID;
    c.name = name;
    if (parentID) c.parentID = parentID;
    await c.saveTx();
    return c;
  },

  async _getExistingUrls(libraryID) {
    const urls = new Set();
    const s = new Zotero.Search();
    s.libraryID = libraryID;
    s.addCondition("itemType", "isNot", "attachment");
    s.addCondition("itemType", "isNot", "note");
    const ids = await s.search();
    const items = await Zotero.Items.getAsync(ids);
    for (const it of items) {
      let u = "";
      try { u = it.getField("url"); } catch (e) {}
      if (u) urls.add(u);
    }
    return urls;
  },

  async _createItem(libraryID, collectionID, p) {
    const item = new Zotero.Item("journalArticle");
    item.libraryID = libraryID;
    if (p.title) item.setField("title", p.title);
    if (p.abstract) item.setField("abstractNote", p.abstract);
    if (p.url) item.setField("url", p.url);
    if (p.journal) item.setField("publicationTitle", p.journal);
    if (p.date) item.setField("date", p.date);
    item.setCollections([collectionID]);
    item.addTag("unread");  // mark freshly pulled papers as unread
    await item.saveTx();
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
      out.push({
        title: get("title"),
        url: link,
        guid: get("guid") || link,
        abstract: this._stripHtml(get("description")),
        journal: get("dc:source") || get("source") || get("author"),
        date: this._normalizeDate(get("pubDate")),
      });
    }
    return out;
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
