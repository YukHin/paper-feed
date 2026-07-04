/* Paper-Feed Sync — Zotero 7 bootstrapped plugin entry point.
 * Loads the main logic (paperfeed.js) into the global `PaperFeed` object and
 * wires it to the plugin lifecycle. Real work lives in paperfeed.js.
 */

var PaperFeed;

function log(msg) {
  Zotero.debug("[Paper-Feed] " + msg);
}

async function startup({ id, version, rootURI }) {
  // Wait until Zotero is fully ready before touching its data layer.
  await Zotero.initializationPromise;

  Services.scriptloader.loadSubScript(rootURI + "paperfeed.js");
  PaperFeed.init({ id, version, rootURI });

  // Settings live in Zotero's preferences (Settings) window, not the Tools menu.
  try {
    Zotero.PreferencePanes.register({
      pluginID: id,
      src: rootURI + "prefs.xhtml",
      label: "Paper-Feed",
      image: rootURI + "icon@48.png",
    });
  } catch (e) {
    log("preference pane register failed: " + e);
  }

  log("started " + version);
}

function shutdown() {
  if (PaperFeed) {
    PaperFeed.uninit();
    PaperFeed = undefined;
  }
  log("shut down");
}

function install() {}

function uninstall() {}

// Zotero 7 calls onMainWindowLoad/Unload so plugins can (re)attach UI per window.
function onMainWindowLoad({ window }) {
  if (PaperFeed) PaperFeed.addToWindow(window);
}

function onMainWindowUnload({ window }) {
  if (PaperFeed) PaperFeed.removeFromWindow(window);
}
