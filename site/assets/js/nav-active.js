// Current-section cue for the navbar menus. Quarto marks neither a menu's toggle nor its items as current.
// Research: on paper pages the toggle gets .active (the white highlight) and aria-current="true", and the open
// paper's own item gets aria-current="page". Static HTML stays correct without this script.
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
  if (/^\/(zh\/)?research\//.test(here)) {
    var toggle = document.getElementById("nav-menu-research") ||
                 document.querySelector(".navbar .nav-item.dropdown > .nav-link.dropdown-toggle");
    if (toggle) { toggle.classList.add("active"); toggle.setAttribute("aria-current", "true"); }
    markItems(document.querySelectorAll(".navbar ul.dropdown-menu a.dropdown-item"));
  }
  // Research Toolkit: every page its menu lists (each tool and the overview) belongs to this section, wherever
  // its URL lives. tools/zh_labels.py writes the same marks into the static HTML; this repeats them for URL
  // forms the post-render pass did not see. A tool page under /projects/ must not leave Projects marked.
  var tk = document.getElementById("nav-menu-research-toolkit");
  var tkMenu = tk && tk.parentElement.querySelector(".dropdown-menu");
  if (tkMenu && markItems(tkMenu.querySelectorAll("a.dropdown-item"))) {
    tk.classList.add("active"); tk.setAttribute("aria-current", "true");
    var tops = document.querySelectorAll(".navbar .navbar-nav > .nav-item > a.nav-link.active:not(.dropdown-toggle)");
    for (var j = 0; j < tops.length; j++) { tops[j].classList.remove("active"); tops[j].removeAttribute("aria-current"); }
  }
})();
