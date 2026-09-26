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
    var el = document.querySelector('link[rel="alternate"][hreflang="' + code + '"]');
    return el ? el.getAttribute("href") : null;
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
