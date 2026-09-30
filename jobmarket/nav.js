// Marks the nav pill for the section in view. The page works fully without it:
// with JavaScript off, no pill claims to be the current location.
(() => {
  const links = [...document.querySelectorAll('.nav a[href^="#"]')];
  const secs = [...document.querySelectorAll('main section[data-nav]')];
  if (!links.length || !secs.length) return;
  const set = (id) => {
    const a = links.find((l) => l.hash === '#' + id);
    if (!a || a.getAttribute('aria-current')) return;
    links.forEach((l) => { l.removeAttribute('aria-current'); l.classList.remove('is-active'); });
    a.setAttribute('aria-current', 'location'); a.classList.add('is-active');
    const bar = a.closest('ul');
    if (bar.scrollWidth > bar.clientWidth) bar.scrollLeft = a.offsetLeft - (bar.clientWidth - a.offsetWidth) / 2;
  };
  const update = () => {
    let cur = secs[0];
    for (const s of secs) if (s.getBoundingClientRect().top <= innerHeight * 0.35) cur = s;
    if (innerHeight + scrollY >= document.documentElement.scrollHeight - 2) cur = secs[secs.length - 1];
    set(cur.dataset.nav);
  };
  let raf = 0;
  const queue = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; update(); }); };
  addEventListener('scroll', queue, { passive: true });
  addEventListener('resize', queue);
  update();
})();
