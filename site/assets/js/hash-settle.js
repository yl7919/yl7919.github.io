// Re-align a URL #fragment after late layout. On a cold load with a hash the browser jumps to the target at once;
// interactive figures above it render afterwards and push it down. While the page settles (at most 8 s), keep the
// target at the top whenever the page height changes; stop as soon as the reader scrolls, taps or types.
(function () {
  "use strict";
  var id = location.hash && decodeURIComponent(location.hash.slice(1));
  if (!id || !window.ResizeObserver) return;
  var stop = false, t0 = Date.now(), LIMIT = 8000, frame = 0, ro;
  ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (e) {
    window.addEventListener(e, function () { stop = true; }, { once: true, passive: true });
  });
  function align() {
    if (stop || Date.now() - t0 > LIMIT) { if (ro) ro.disconnect(); return; }
    var el = document.getElementById(id);
    if (el) el.scrollIntoView({ block: "start" });
  }
  ro = new ResizeObserver(function () { cancelAnimationFrame(frame); frame = requestAnimationFrame(align); });
  ro.observe(document.body);
  window.addEventListener("load", align);
  setTimeout(function () { if (ro) ro.disconnect(); }, LIMIT + 100);
})();
