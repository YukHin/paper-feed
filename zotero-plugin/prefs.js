/* Paper-Feed preferences pane bindings.
 *
 * Loaded via Zotero.PreferencePanes.register({ scripts: [...] }) — inline
 * <script> in the pane XHTML is blocked by CSP and never runs, which is why
 * values previously neither loaded nor saved. This runs in the pane's window
 * scope, where `Zotero`, `document` and `window` are available.
 */
(function () {
  var PREF = "extensions.paperfeed.";

  function init() {
    var Z = (typeof Zotero !== "undefined" && Zotero) ||
            (typeof window !== "undefined" && window.Zotero) || null;
    if (!Z || !Z.Prefs) { setTimeout(init, 50); return; }

    var get = function (k) { return Z.Prefs.get(PREF + k, true); };
    var set = function (k, v) { Z.Prefs.set(PREF + k, v, true); };

    function bindText(id, key, transform, restart) {
      var el = document.getElementById(id);
      if (!el) return;
      var v = get(key);
      el.value = (v === undefined || v === null) ? "" : String(v);
      var save = function () {
        var val = transform ? transform(el.value) : el.value;
        set(key, val);
        // reflect the normalized value back into the field
        el.value = (val === undefined || val === null) ? "" : String(val);
        if (restart && Z.PaperFeed && Z.PaperFeed.restartTimer) {
          try { Z.PaperFeed.restartTimer(); } catch (e) {}
        }
      };
      el.addEventListener("change", save);
      el.addEventListener("blur", save);
    }

    function bindCheck(id, key) {
      var el = document.getElementById(id);
      if (!el) return;
      el.checked = get(key) === true;
      var save = function () { set(key, !!el.checked); };
      el.addEventListener("command", save);
      el.addEventListener("change", save);
    }

    bindText("pf-baseUrl", "baseUrl", function (s) {
      return (s || "").trim().replace(/\/+$/, "");
    });
    bindText("pf-intervalHours", "intervalHours", function (s) {
      var n = parseFloat(s); return (n > 0) ? n : 6;
    }, true);
    bindText("pf-parentCollection", "parentCollection", function (s) {
      return (s || "").trim() || "Paper-Feed";
    });
    bindText("pf-blockWords", "blockWords", null);
    bindCheck("pf-cleanup", "cleanup");
    bindCheck("pf-autoFetchPdf", "autoFetchPdf");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
