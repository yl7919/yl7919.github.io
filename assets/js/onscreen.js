// assets/js/onscreen.js — marks interactive figure units with data-onscreen so CSS can apply
// `content-visibility: auto` to off-screen figures (spec "The interactive-figure unit").
(function () {
  if (typeof IntersectionObserver === "undefined") return;   // no attribute -> always visible
  var figures = document.querySelectorAll(".dfigure");
  if (!figures.length) return;
  var io = new IntersectionObserver(function (entries) {
    for (var i = 0; i < entries.length; i++) {
      entries[i].target.setAttribute("data-onscreen", entries[i].isIntersecting ? "true" : "false");
    }
  }, { rootMargin: "100%" });
  for (var j = 0; j < figures.length; j++) io.observe(figures[j]);
})();
