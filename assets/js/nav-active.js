// Research dropdown: mark the toggle active on paper pages and the open paper's own menu item.
// Quarto gives neither .active when the parent has a menu (spec-nav.md §0). Static HTML stays
// correct without this; it only restores the white "Research" highlight and an aria-current cue.
(function () {
  // Also folds GitHub Pages' extensionless URLs (/research/x serves x.html; /research/index serves /research/).
  var strip = function (p) { return p.replace(/\.html$/, "").replace(/\/index$/, "/"); };
  var here = strip(location.pathname);
  if (!/^\/(zh\/)?research\//.test(here)) return;
  var toggle = document.getElementById("nav-menu-research") ||
               document.querySelector(".navbar .nav-item.dropdown > .nav-link.dropdown-toggle");
  if (toggle) toggle.classList.add("active");
  var items = document.querySelectorAll(".navbar ul.dropdown-menu a.dropdown-item");
  for (var i = 0; i < items.length; i++) {
    var p;
    try { p = strip(new URL(items[i].getAttribute("href"), location.href).pathname); } catch (e) { continue; }
    if (p === here) { items[i].classList.add("active"); items[i].setAttribute("aria-current", "page"); }
  }
})();
