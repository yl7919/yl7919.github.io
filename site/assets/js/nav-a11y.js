// assets/js/nav-a11y.js — keyboard semantics of the navbar menus.
// Quarto renders each menu toggle as <a href="#" role="link" data-bs-toggle="dropdown">. Bootstrap opens it
// on click and Enter, but Space on a link scrolls the page (and the headroom bar slides away with the focus).
// Here every toggle is announced as the button it behaves like, and Space opens or closes its menu as on a
// native button, by the same click that Enter sends; Enter, Escape, Tab and the arrow keys stay with
// Bootstrap. Quarto also gives the hamburger <button> role="menu" although it holds no menu items; without
// the role it is announced as a button again (its aria-expanded and aria-controls stay).
(function () {
  var toggles = document.querySelectorAll('.navbar .nav-link.dropdown-toggle[data-bs-toggle="dropdown"]');
  for (var i = 0; i < toggles.length; i++) {
    toggles[i].setAttribute("role", "button");
    toggles[i].addEventListener("keydown", function (e) {
      if ((e.key !== " " && e.key !== "Spacebar") || e.altKey || e.ctrlKey || e.metaKey) return;
      e.preventDefault();                 // no page scroll
      this.click();                       // Bootstrap's own toggle handler, as for Enter
    });
  }
  var burger = document.querySelector('.navbar-toggler[role="menu"]');
  if (burger) burger.removeAttribute("role");
})();
