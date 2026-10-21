// Current-section cue for the navbar menus. Quarto marks neither a menu's toggle nor its items as current.
// Research: on paper pages the toggle gets .active (the white highlight) and aria-current="true", and the open
// paper's own item gets aria-current="page". Projects: on every page under /projects/ that no other menu claims
// (a tool page belongs to its own menu), the toggle is current and "All projects" is the page on the index. An
// item whose href carries a #fragment opens a part of a page, never the page, so the menu blocks skip such items.
// Static HTML stays correct without this script (tools/zh_labels.py writes the same marks post-render).
(function () {
  // Also folds GitHub Pages' extensionless URLs (/research/x serves x.html; /research/index serves /research/).
  var strip = function (p) { return p.replace(/\.html$/, "").replace(/\/index$/, "/"); };
  var here = strip(location.pathname);
  var pathOf = function (a) {
    try { return strip(new URL(a.getAttribute("href"), location.href).pathname); } catch (e) { return null; }
  };
  var markItems = function (items) {        // aria-current="page" on the items that open this page
    var hit = false;
    for (var i = 0; i < items.length; i++) {
      if (pathOf(items[i]) === here) {
        items[i].classList.add("active"); items[i].setAttribute("aria-current", "page"); hit = true;
      }
    }
    return hit;
  };
  var PAGE_ITEMS = "a.dropdown-item:not([href*='#'])";   // items that open a page, not a section of one
  var inToolkit = false;                                  // set below when this page belongs to the Toolkit menu
  if (/^\/(zh\/)?research\//.test(here)) {
    var toggle = document.getElementById("nav-menu-research") ||
                 document.querySelector(".navbar .nav-item.dropdown > .nav-link.dropdown-toggle");
    if (toggle) { toggle.classList.add("active"); toggle.setAttribute("aria-current", "true"); }
    // A paper's own item (…/paper.html#example) marks that paper page; an item that jumps into the research
    // index (…/research/index.html#bond-premia) is a part of that page, so only "All research" marks the index.
    markItems(Array.prototype.filter.call(document.querySelectorAll(".navbar ul.dropdown-menu a.dropdown-item"),
      function (a) { return !((a.getAttribute("href") || "").indexOf("#") >= 0 && /\/research\/$/.test(pathOf(a) || "")); }));
  }
  // Research Toolkit: every page its menu lists (each tool and the overview) belongs to this section, wherever
  // its URL lives. tools/zh_labels.py writes the same marks into the static HTML; this repeats them for URL
  // forms the post-render pass did not see. A tool page under /projects/ must not leave Projects marked, and the
  // demo jump under each tool (href …#demo) is never the current page.
  var tk = document.getElementById("nav-menu-research-toolkit");
  var tkMenu = tk && tk.parentElement.querySelector(".dropdown-menu");
  if (tkMenu && markItems(tkMenu.querySelectorAll(PAGE_ITEMS))) {
    inToolkit = true;
    tk.classList.add("active"); tk.setAttribute("aria-current", "true");
    var tops = document.querySelectorAll(".navbar .navbar-nav > .nav-item > a.nav-link.active:not(.dropdown-toggle)");
    for (var j = 0; j < tops.length; j++) { tops[j].classList.remove("active"); tops[j].removeAttribute("aria-current"); }
  }
  // Projects: the section is the /projects/ URL prefix (EN and ZH), minus the pages the Toolkit menu claims.
  var pj = document.getElementById("nav-menu-projects");
  var pjMenu = pj && pj.parentElement.querySelector(".dropdown-menu");
  if (pjMenu && !inToolkit && /^\/(zh\/)?projects\//.test(here)) {
    pj.classList.add("active"); pj.setAttribute("aria-current", "true");
    markItems(pjMenu.querySelectorAll(PAGE_ITEMS));
  }
})();
