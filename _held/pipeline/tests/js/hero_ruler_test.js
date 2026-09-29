// Headless smoke test for site/assets/js/hero.js (spec "Hero animation").
// Run: deno test --allow-read pipeline/tests/js/hero_test.js   (from the web/ checkout)
// Quarto bundles deno at ~/.local/opt/quarto-*/bin/tools/<arch>/deno; test_hero_js.py runs this.
// The pure encoding is tested directly; the figure is driven through a minimal stubbed DOM
// (fake canvas context, manual requestAnimationFrame clock) against the shipped JSON.

const HERE = new URL(".", import.meta.url);
const HERO = new URL("../../../site/assets/js/hero.js", HERE);
const DATA = JSON.parse(await Deno.readTextFile(new URL("../../../site/data/hero_geometry.json", HERE)));
const assert = (c, msg) => { if (!c) throw new Error(msg); };
const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

Deno.test("encoding follows the spec formulas", async () => {
  const m = await import(HERO.href);
  const [l1, l2] = m.encode(0.1521, 22.63);                   // u = v = 1
  assert(near(l1, 1.15 * 2) && near(l2, 1.15 / 2), `extreme: ${l1} ${l2}`);
  const [a1, a2] = m.encode(0.1176, 17.36);                   // u = v = 0
  assert(near(a1, 0.85 * Math.sqrt(1.4)) && near(a2, 0.85 / Math.sqrt(1.4)), "floor");
  const [c1, c2] = m.encode(1, 100);                          // clamped
  assert(near(c1, l1) && near(c2, l2), "clamp");
  assert(near(a1 * a2, 0.85 * 0.85), "det = size²");
  assert(m.ease(0) === 0 && m.ease(1) === 1 && near(m.ease(0.5), 0.5) && near(m.ease(0.25), 4 * 0.25 ** 3), "ease");
  const mid = m.mix([1, 1], [4, 0.25], 0.5);                  // log-midpoint
  assert(near(mid[0], 2) && near(mid[1], 0.5), `mix ${mid}`);
  assert(near(m.spokeLen([2, 0.5], 0), 2) && near(m.spokeLen([2, 0.5], Math.PI / 2), 0.5), "spokes");
  assert(near(m.spokeLen([1, 1], 1.234), 1), "identity spokes have length 1");
  const t0 = m.metricFor(DATA, 3), e0 = m.encode(DATA.share[3], DATA.pd[3]);
  assert(near(t0[0], e0[0]) && near(t0[1], e0[1]), "integer month = that month");
  assert(m.inRecession(DATA.nber, 5) && m.inRecession(DATA.nber, 21) && !m.inRecession(DATA.nber, 22), "nber");
  assert(m.fill("{month} {x}", { month: "M" }) === "M {x}", "fill");
  let threw = false; try { m.validate({ pd: [1] }); } catch { threw = true; }
  assert(threw, "validate rejects malformed data");
});

// ---- stubbed DOM -------------------------------------------------------------------------
function el(props = {}) {
  const cls = new Set(props.cls || []), attrs = { ...(props.attrs || {}) }, on = {};
  return {
    dataset: props.dataset || {}, textContent: "", value: "0", max: "617", tabIndex: 0, clientWidth: 900,
    classList: { add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c),
      toggle: (c, f) => (f ? cls.add(c) : cls.delete(c)) },
    setAttribute: (k, v) => { attrs[k] = String(v); }, getAttribute: (k) => attrs[k] ?? null,
    addEventListener: (t, f) => { (on[t] ||= []).push(f); },
    fire(t, ev = {}) { const e = { target: this, preventDefault() { e.prevented = true; }, ...ev }; (on[t] || []).forEach((f) => f(e)); return e; },
    focus() { this.focused = true; }, click() { this.fire("click"); },
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 900, height: 248 }), setPointerCapture() {},
    getContext: () => new Proxy({ calls: 0 }, { get: (o, k) => (k in o ? o[k] : () => { o.calls++; }), set: (o, k, v) => ((o[k] = v), true) }),
  };
}
function setup({ lang = "en", reduce = false, fail = false } = {}) {
  const radios = [el({ dataset: { mode: "id" }, attrs: { "aria-checked": "false" } }),
                  el({ dataset: { mode: "char" }, attrs: { "aria-checked": "true" } })];
  const parts = {
    canvas: el(), "input[type=range]": el(), ".hero-play": el(), ".hero-date": el(), "[role=radiogroup]": el(),
    ".hero-caption .live": el({ dataset: { en: "{month} — {pd} of 132; {share}%.{nber}", zh: "{month}——{pd}；{share}%。{nber}" } }),
    ".hero-caption .resolved": el({ dataset: { en: "A different ruler.", zh: "换一把尺子。" } }),
  };
  const fig = el({ dataset: { src: "/data/hero_geometry.json" } });
  fig.querySelector = (s) => parts[s];
  fig.querySelectorAll = () => radios;
  const raf = [];
  globalThis.document = { documentElement: { lang }, hidden: false, getElementById: () => fig, addEventListener() {} };
  globalThis.window = { devicePixelRatio: 3 };
  globalThis.requestAnimationFrame = (f) => raf.push(f);
  globalThis.matchMedia = () => ({ matches: reduce });
  globalThis.fetch = async () => (fail ? new Response("", { status: 404 }) : new Response(JSON.stringify(DATA)));
  globalThis.Path2D = class { moveTo() {} lineTo() {} };
  globalThis.ResizeObserver = class { constructor(f) { this.f = f; } observe() { this.f([]); } };
  globalThis.IntersectionObserver = class { constructor(f) { this.f = f; } observe() { this.f([{ isIntersecting: true }]); } };
  let clock = 0;
  globalThis.performance = { now: () => clock };                   // rAF and performance.now share one timeline
  const timers = new Map();                                        // fake setTimeout on the same clock
  let tid = 0;
  globalThis.setTimeout = (f, ms) => { timers.set(++tid, [clock + ms, f]); return tid; };
  globalThis.clearTimeout = (id) => timers.delete(id);
  const run = (ms, step = 16) => {
    for (const end = clock + ms; clock < end;) {
      clock += step;
      for (const [id, [at, f]] of timers) if (at <= clock) { timers.delete(id); f(); }
      if (raf.length) raf.shift()(clock);
    }
  };
  return { fig, parts, radios, raf, run };
}
const realTimeout = setTimeout;
const settle = () => new Promise((r) => realTimeout(r, 30));
let n = 0;
const load = async (opts) => { const s = setup(opts); await import(`${HERO.href}?v=${++n}`); await settle(); return s; };

Deno.test("plays, holds at the last month, wraps, and is keyboard driven", async () => {
  const { fig, parts, radios, raf, run } = await load();
  assert(raf.length === 1, "one frame scheduled after load");
  run(16);
  assert(fig.classList.contains("is-live"), "is-live after first frame");
  assert(parts[".hero-date"].textContent === "Jun 1973", parts[".hero-date"].textContent);
  assert(parts.canvas.width === 1800 && parts.canvas.height === 496, "dpr capped at 2, 248 px height");
  assert(parts[".hero-play"].textContent === "Pause", "playing");
  assert(parts[".hero-caption .live"].textContent.startsWith("Jun 1973 — "), parts[".hero-caption .live"].textContent);
  run(10400);                                                        // 60 months/s → 617 in ≈10.3 s
  assert(parts["input[type=range]"].value === "617", `at end: ${parts["input[type=range]"].value}`);
  assert(fig.classList.contains("hero-resolved"), "resolved at t = 617");
  run(1500);
  assert(parts["input[type=range]"].value === "617", "holding");
  run(700);
  assert(+parts["input[type=range]"].value < 20, `wrapped: ${parts["input[type=range]"].value}`);
  // Space on the figure pauses; arrows step; Shift steps 12; other keys untouched.
  const sp = fig.fire("keydown", { key: " " });
  assert(sp.prevented && parts[".hero-play"].textContent === "Play", "space pauses");
  run(32);
  const v = +parts["input[type=range]"].value;
  fig.fire("keydown", { key: "ArrowRight", shiftKey: true }); run(32);
  assert(+parts["input[type=range]"].value === v + 12, "shift+right = +12");
  fig.fire("keydown", { key: "ArrowLeft" }); run(32);
  assert(+parts["input[type=range]"].value === v + 11, "left = -1");
  assert(!fig.fire("keydown", { key: "Tab" }).prevented, "unhandled keys keep their default");
  assert(!fig.classList.contains("hero-resolved"), "live within 1.5 s of scrubbing");
  run(1600);
  assert(fig.classList.contains("hero-resolved") && raf.length === 0, "resolved after 1.5 s idle; loop idle");
  // Radiogroup: roving tabindex, arrows move and check, mode transition then the loop stops.
  const g = parts["[role=radiogroup]"].fire("keydown", { key: "ArrowRight" });
  assert(g.prevented && radios[0].getAttribute("aria-checked") === "true" && radios[0].tabIndex === 0 && radios[1].tabIndex === -1 && radios[0].focused, "roving");
  run(700);
  assert(raf.length === 0, "rAF stops when paused and the transition is done");
  parts["input[type=range]"].value = "429"; parts["input[type=range]"].fire("input"); run(16);
  assert(parts["input[type=range]"].getAttribute("aria-valuetext") === "Mar 2009", "aria-valuetext");
});

Deno.test("reduced motion starts paused at the last month; zh strings", async () => {
  const { fig, parts, run } = await load({ lang: "zh-Hans", reduce: true });
  run(16);
  assert(fig.classList.contains("is-live"), "live");
  assert(parts["input[type=range]"].value === "617" && parts[".hero-play"].textContent === "播放", "paused at 617");
  assert(fig.classList.contains("hero-resolved") && parts[".hero-caption .resolved"].textContent === "换一把尺子。", "zh resolved");
  assert(parts[".hero-caption .live"].textContent.includes("——"), "zh live template");
});

Deno.test("an exception inside frame() removes is-live and stops the loop", async () => {
  const { fig, parts, raf, run } = await load();
  run(16);
  assert(fig.classList.contains("is-live"), "live first");
  Object.defineProperty(parts[".hero-date"], "textContent", { set() { throw new Error("boom"); } });
  const warn = console.warn; console.warn = () => {};
  try { run(200); } finally { console.warn = warn; }
  assert(!fig.classList.contains("is-live") && raf.length === 0, "PNG returns, loop stopped");
});

Deno.test("fetch failure leaves the PNG (no is-live)", async () => {
  const warn = console.warn; console.warn = () => {};
  const { fig, raf } = await load({ fail: true }).finally(() => { console.warn = warn; });
  assert(!fig.classList.contains("is-live") && raf.length === 0, "static fallback");
});
