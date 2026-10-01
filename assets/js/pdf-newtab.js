// Link policy (owner round 5, A3): documents open in a new tab, in-site navigation stays in the
// same tab. Quarto's link-external-newwindow already covers off-site links; this covers same-site
// PDFs (e.g. /assets/pdfs/*.pdf), which Quarto treats as internal. rel="noopener" keeps the new
// tab from reaching back into this page. It runs on window load, after Quarto's own
// DOMContentLoaded pass, so it can also add noopener to every link Quarto sent to a new tab
// (e.g. the licence link, which carries rel="license").
(function () {
  function addNoopener(a) {
    var rel = (a.getAttribute("rel") || "").split(/\s+/).filter(Boolean);
    if (rel.indexOf("noopener") < 0) { rel.push("noopener"); a.setAttribute("rel", rel.join(" ")); }
  }
  function run() {
    var links = document.querySelectorAll("a[href]");
    for (var i = 0; i < links.length; i++) {
      var a = links[i], url;
      try { url = new URL(a.getAttribute("href"), location.href); } catch (e) { continue; }
      if (url.origin === location.origin && /\.pdf$/i.test(url.pathname)) a.setAttribute("target", "_blank");
      if (a.getAttribute("target") === "_blank") addNoopener(a);
    }
  }
  if (document.readyState === "complete") run();
  else window.addEventListener("load", run);
})();
