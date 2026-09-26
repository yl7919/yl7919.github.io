// assets/js/lang-toggle.js — points the navbar language item at this page's translation
// (spec "Bilingual mechanism: Toggle"). Without JS the static link goes to /zh/ (or, on zh
// pages, its label is already rewritten to "English" by tools/zh_labels.py).
(function () {
  var link = document.querySelector('a.nav-link[href$="/zh/"], a.nav-link[href$="/zh/index.html"], a.nav-link[href="/zh"]');
  if (!link) return;
  link.classList.add("lang-toggle");
  link.setAttribute("aria-label", "Switch language");   // Quarto drops aria-label from nav items (verified)
  var isZh = (document.documentElement.lang || "en").toLowerCase().indexOf("zh") === 0;
  function alternate(code) {
    // hreflang alternates are absolute (site-url); strip the origin so a local preview stays local.
    var el = document.querySelector('link[rel="alternate"][hreflang="' + code + '"]');
    if (!el) return null;
    var u = el.getAttribute("href") || "";
    u = u.replace(/^https?:\/\/[^/]+/, "");
    return u || "/";
  }
  var path = location.pathname || "/";
  if (isZh) {
    var en = alternate("en");
    link.setAttribute("href", en || "/");
  } else {
    var zh = alternate("zh-Hans") || alternate("zh");
    if (zh) {
      link.setAttribute("href", zh);
    } else {
      link.setAttribute("href", "/zh/?from=" + encodeURIComponent(path));
      link.classList.add("lang-missing");
      link.setAttribute("title", "Chinese version not available for this page; opens the Chinese home page");
    }
  }
})();
