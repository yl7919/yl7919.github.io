// Headless test of site/assets/js/hero_overlap.js (spec "interactive dynamic-geometry hero", revision 2).
// Run: deno test --allow-read pipeline/tests/js/hero_overlap_test.js   (from the web/ checkout)
// Quarto bundles deno at ~/.local/opt/quarto-*/bin/tools/<arch>/deno; test_hero_js.py runs this.
// The pure helpers and the model builders are tested directly; the figure is driven through a minimal
// stubbed DOM (fake nodes, manual requestAnimationFrame clock) against the shipped JSON and the
// data-en/data-zh templates of site/index.qmd.

const HERE = new URL(".", import.meta.url);
const HERO = new URL("../../../site/assets/js/hero_overlap.js", HERE);
const DATA = JSON.parse(await Deno.readTextFile(new URL("../../../site/data/hero_overlap.json", HERE)));
const PAGE = await Deno.readTextFile(new URL("../../../site/index.qmd", HERE));
const PAGE_ZH = await Deno.readTextFile(new URL("../../../site/zh/index.qmd", HERE));
const CG = await Deno.readTextFile(new URL("../../../site/research/characteristic-geometry.qmd", HERE));
const CG_ZH = await Deno.readTextFile(new URL("../../../site/zh/research/characteristic-geometry.qmd", HERE));
const assert = (c, msg) => { if (!c) throw new Error(msg); };
const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;
const M = await import(HERO.href);

// Templates from the page source (both languages are carried as data-en/data-zh on every page).
function templates(src) {
  const out = [];
  for (const m of src.matchAll(/data-(en|zh|plain-en|plain-zh|avg-en|avg-zh|pd-en|pd-zh|avg-short-en|avg-short-zh|pd-short-en|pd-short-zh)="([^"]*)"/g)) out.push([m[1], m[2]]);
  return out;
}
const attr = (src, sel, key) => { const m = src.match(new RegExp(`${sel}[^>]*data-${key}="([^"]*)"`)); return m ? m[1] : ""; };
const EN = {
  live: attr(PAGE, 'class="hero-readout live"', "en"), plain: attr(PAGE, 'class="hero-readout plain"', "en"),
  resolved: attr(PAGE, 'class="hero-readout resolved"', "en"), cell: attr(PAGE, 'class="hero-cell"', "en"),
  cellPlain: attr(PAGE, 'class="hero-cell"', "plain-en"), cap: attr(PAGE, '<caption class="hero-sr"', "en"),
  capPlain: attr(PAGE, '<caption class="hero-sr"', "plain-en"), hint: attr(PAGE, 'class="hero-hint"', "en"),
};
const ZH = {
  live: attr(PAGE_ZH, 'class="hero-readout live"', "zh"), plain: attr(PAGE_ZH, 'class="hero-readout plain"', "zh"),
  resolved: attr(PAGE_ZH, 'class="hero-readout resolved"', "zh"), cell: attr(PAGE_ZH, 'class="hero-cell"', "zh"),
  cellPlain: attr(PAGE_ZH, 'class="hero-cell"', "plain-zh"), cap: attr(PAGE_ZH, '<caption class="hero-sr"', "zh"),
  capPlain: attr(PAGE_ZH, '<caption class="hero-sr"', "plain-zh"), hint: attr(PAGE_ZH, 'class="hero-hint"', "zh"),
};
for (const [k, v] of Object.entries(EN)) assert(v, `EN template ${k} found in index.qmd`);
for (const [k, v] of Object.entries(ZH)) assert(v, `ZH template ${k} found in zh/index.qmd`);

// WCAG relative luminance / contrast of the cell text (rgba(0,0,0,.8)) over a tint composited on white.
function parseRgba(s) { const m = s.match(/rgba\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)/); return m.slice(1).map(Number); }
function over(bg, rgb, a) { return bg.map((c, i) => c * (1 - a) + rgb[i] * a); }
function lum([r, g, b]) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function contrast(fg, bg) { const [a, b] = [lum(fg), lum(bg)]; return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); }

Deno.test("pure helpers", () => {
  assert(M.argmaxAbs([0.1, -0.7, 0.5]) === 1 && M.argmaxAbs(DATA.corr[309]) === 0, "argmaxAbs");
  assert(M.fmt2(-0.07) === "−0.07" && M.fmt2(0) === "0.00" && M.fmt2(-0) === "0.00" && M.fmt2(0.856) === "0.86", "fmt2");
  assert(M.fmt1(22.53) === "22.5" && (M.fmt1(-1.25) === "−1.3" || M.fmt1(-1.25) === "−1.2"), "fmt1");
  assert(M.lc("Small size") === "small size" && M.lc("") === "", "lc");
  assert(M.fill("{a} and {b}: {v}", { a: "X", b: "Y" }) === "X and Y: {v}", "fill");
  assert(M.labelFor(DATA.months, 0, "en") === "Jun 1983" && M.labelFor(DATA.months, 309, "zh") === "2009 年 3 月", "labelFor");
  // validate: the shipped JSON passes; a 27-pair row and a payload without meta.axes are rejected.
  M.validate(DATA);
  const bad = JSON.parse(JSON.stringify(DATA)); bad.corr[5] = bad.corr[5].slice(0, 27);
  let threw = 0; try { M.validate(bad); } catch { threw++; }
  const noAxes = JSON.parse(JSON.stringify(DATA)); delete noAxes.meta.axes;
  try { M.validate(noAxes); } catch { threw++; }
  assert(threw === 2, "validate rejects a 27-pair row and a payload without meta.axes");
  // Tint contrast at |v| = 1 for both hues: rgba(0,0,0,.8) text over the tint over white ≥ 4.5:1.
  for (const v of [1, -1]) {
    const [r, g, b, a] = parseRgba(M.tint(v));
    const bg = over([255, 255, 255], [r, g, b], a), fg = over(bg, [0, 0, 0], 0.8);
    assert(contrast(fg, bg) >= 4.5, `contrast at v=${v}: ${contrast(fg, bg).toFixed(2)}`);
  }
  // countNumerals under the spec definition.
  assert(M.countNumerals("Figure 1: How eight related characteristics overlap, 1983–2025.") === 1, "title counts 1");
  assert(M.countNumerals("The 8-by-8 table for the window ending March 2009 (p. 31), JKP153 and 153×153.") === 1, "labels are not numerals");
  assert(M.countNumerals("runs from 21.7 to 22.9") === 2 && M.countNumerals("全部 153 个特征大致相当于 22.5 个") === 2, "plain counts");
  assert(M.countNumerals("2009 年 3 月。截至 2009 年 3 月的窗口内为 0.86。") === 3, "zh dates count one each");
  assert(M.countNumerals("runs from 11.76% to 15.21% (slides, pp. 7, 23)") === 2 && M.countNumerals("介于 11.76% 至 15.21%（幻灯片第 7、23 页）") === 2, "page lists are labels");
  assert(M.countNumerals("Table I (p. 31) and Figure 1 (p. 32) for all 153 characteristics") === 1, "page references are labels");
});

// Every template in both pages, instantiated with sample values, has ≤ 2 numerals per sentence.
Deno.test("templates: at most two numerals per sentence (EN and ZH page source)", () => {
  const vals = { month: "March 2009", avg: "0.29", a: "small size", b: "illiquidity", top: "0.86", pd: "22.5", v: "0.86" };
  const valsZh = { ...vals, month: "2009 年 3 月", a: "小市值", b: "低流动性" };
  const strings = [];
  for (const [src, lang] of [[PAGE, "en"], [PAGE_ZH, "zh"]]) {
    for (const [k, tpl] of templates(src)) strings.push([k, M.fill(tpl, k.endsWith("zh") ? valsZh : vals)]);
    const stat = src.match(/<p id="hero-sr" class="hero-sr">([^<]*)<\/p>/);
    assert(stat, `${lang}: #hero-sr present`); strings.push(["sr", stat[1]]);
    const cap = src.match(/<span class="static" id="hero-static">([\s\S]*?)<a href="#fn1"/);
    assert(cap, `${lang}: static caption present`); strings.push(["caption", cap[1].replace(/<[^>]+>/g, "")]);
    const scale = src.match(/<p id="hero-scale" class="hero-scale">([^<]*)<\/p>/);
    assert(scale, `${lang}: scale line present`); strings.push(["scale", scale[1]]);
    const title = src.match(/<title id="hero-tl-title">([^<]*)<\/title>/);
    assert(title, `${lang}: timeline title present`); strings.push(["title", title[1]]);
    const alt = src.match(/class="hero-fallback"[^>]*alt="([^"]*)"/);
    assert(alt, `${lang}: fallback alt present`); strings.push(["alt", alt[1]]);
    const lead = src.match(/\n((?:Figure 1 shows|图 1 展示)[^\n]*)/);
    assert(lead, `${lang}: lead line present`); strings.push(["lead", lead[1].replace(/\[\^hero\]|\[([^\]]*)\]\([^)]*\)/g, "$1")]);
    const fn = src.match(/\n\[\^hero\]: ([^\n]*)/);
    assert(fn, `${lang}: footnote present`); strings.push(["footnote", fn[1]]);
  }
  // The Characteristic Geometry #ruler-statistics notes (acceptance 9 names them too).
  for (const [src, lang] of [[CG, "en"], [CG_ZH, "zh"]]) {
    const note = src.match(/::: \{#ruler-statistics \.figcaption\}\n([\s\S]*?)\n:::/);
    assert(note, `${lang}: CG #ruler-statistics note present`);
    strings.push([`cg-${lang}`, note[1].replace(/<[^>]+>/g, "").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/\*\*/g, "")]);
  }
  assert(strings.length > 30, `collected ${strings.length} strings`);
  for (const src of [PAGE, PAGE_ZH]) assert(!/<figure class="hero"[^>]*tabindex/.test(src), "the figure becomes a tab stop only in JS");
  for (const [k, s] of strings) {
    // An EN sentence ends at a period followed by whitespace and a capital (so decimals, "p. 31" and "U.S."
    // do not split); a ZH sentence ends at 。.
    for (const sent of s.split(/(?<=\.)\s+(?=[A-Z])|(?<=。)/)) {
      if (!sent.trim()) continue;
      const n = M.countNumerals(sent);
      assert(n <= 2, `${k}: ${n} numerals in "${sent}"`);
    }
  }
});

Deno.test("model builders", () => {
  const rows = M.rowsModel(DATA, 309, "char", "en");
  assert(rows.length === 8 && rows.every((r) => r.cells.length === 8), "8 × 8");
  assert(rows[0].header === "1 Small size" && rows[7].header === "8 Young firms", rows[0].header);
  assert(rows[0].cells[1].text === M.fmt2(DATA.corr[309][0]), "first-row second cell is corr[309][0]");
  assert(rows[0].cells[1].text === "0.86", "reads 0.86 at 2009-03");
  let diag = 0;
  for (const r of rows) for (const c of r.cells) {
    assert(/^[−]?[0-9]\.[0-9]{2}$/.test(c.text), `2 dp: ${c.text}`);
    if (c.diagonal) diag++; else assert(typeof c.tint === "string" && c.tint.startsWith("rgba("), "tint on off-diagonal");
  }
  assert(diag === 8, "8 diagonal cells");
  const plain = M.rowsModel(DATA, 309, "plain", "en");
  let zeros = 0, ones = 0;
  for (const r of plain) for (const c of r.cells) {
    if (c.text === "0" && c.tint === null) zeros++;
    if (c.text === "1") ones++;
  }
  assert(zeros === 56 && ones === 8, `plain: ${zeros} zeros, ${ones} ones`);
  assert(M.rowsModel(DATA, 309, "char", "zh")[0].header === "1 小市值", "zh header");
  const tl = M.timelineModel(DATA, 1000, 120, 309);
  assert(tl.paths.length === 2, "two paths");
  const ticks = tl.axes.flatMap((a) => a.ticks.map((t) => t.label));
  assert(JSON.stringify(ticks) === JSON.stringify(["0.20", "0.35", "20", "24"]), ticks.join(","));
  assert(!("bands" in tl) && !("nber" in tl), "no band entries");
  const pw = tl.plot.x1 - tl.plot.x0;
  assert(near(tl.cursor.x - tl.plot.x0, (309 / 509) * pw, 0.5), `cursor.x ${tl.cursor.x}`);
  assert(tl.dots.length === 2 && tl.labels.length === 2 && tl.labels.every((l) => !l.short), "dots and full series labels at 1000 px");
  const narrow = M.timelineModel(DATA, 326, 96, 0).labels;
  assert(narrow.length === 2 && narrow.every((l) => l.short), "short series labels at 326 px");
  assert(tl.decades.some((d) => d.label === "1990") && tl.decades.some((d) => d.label === "2020"), "decade ticks");
});

// ---- stubbed DOM -------------------------------------------------------------------------
function el(tag = "div", props = {}) {
  const cls = new Set(props.cls || []), attrs = { ...(props.attrs || {}) }, on = {}, kids = [];
  const style = { props: {}, setProperty(k, v) { this.props[k] = v; } };
  const node = {
    tagName: tag, dataset: props.dataset || {}, textContent: "", value: "0", max: "", tabIndex: 0, hidden: !!props.hidden,
    clientWidth: props.w || 0, clientHeight: props.h || 0, children: kids, style,
    classList: { add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c),
      toggle: (c, f) => { const on_ = f === undefined ? !cls.has(c) : !!f; on_ ? cls.add(c) : cls.delete(c); return on_; } },
    setAttribute: (k, v) => { attrs[k] = String(v); }, getAttribute: (k) => attrs[k] ?? null, removeAttribute: (k) => { delete attrs[k]; },
    appendChild(c) { kids.push(c); c.parentNode = node; return c; }, append(...cs) { cs.forEach((c) => node.appendChild(c)); },
    replaceChildren() { kids.length = 0; },
    addEventListener: (t, f) => { (on[t] ||= []).push(f); },
    fire(t, ev = {}) { const e = { target: node, currentTarget: node, preventDefault() { e.prevented = true; }, ...ev }; (on[t] || []).forEach((f) => f(e)); return e; },
    focus() { node.focused = true; }, click() { node.fire("click"); },
    getBoundingClientRect: () => ({ left: 0, top: 0, width: props.w || 0, height: props.h || 0 }), setPointerCapture() {},
    querySelector: (s) => (props.q || {})[s] || null, querySelectorAll: (s) => (props.qa || {})[s] || [],
  };
  return node;
}
function setup({ lang = "en", reduce = false, fail = false, noCaption = false } = {}) {
  const radios = [el("button", { dataset: { mode: "plain" }, attrs: { "aria-checked": "false" } }),
                  el("button", { dataset: { mode: "char" }, attrs: { "aria-checked": "true" } })];
  const T = lang === "en" ? EN : ZH, k = lang;
  const caption = noCaption ? null : el("caption", { dataset: { en: EN.cap, zh: ZH.cap, plainEn: EN.capPlain, plainZh: ZH.capPlain } });
  const tbody = el("tbody"), heads = Array.from({ length: 9 }, () => el("th"));
  const table = el("table", { q: { caption, tbody }, qa: { "thead th": heads } });
  const svg = el("svg", { w: 900, h: 120, dataset: { avgEn: "Average overlap size", avgZh: "重叠大小的平均", pdEn: "Participation dimension", pdZh: "参与维数" } });
  const parts = {
    "input[type=range]": el("input"), ".hero-play": el("button"), ".hero-date": el("span"), ".hero-hint": el("span", { dataset: { en: EN.hint, zh: ZH.hint } }),
    "[role=radiogroup]": el("div"), ".hero-heat": table,
    ".hero-cell": el("p", { dataset: { en: EN.cell, zh: ZH.cell, plainEn: EN.cellPlain, plainZh: ZH.cellPlain } }),
    ".hero-readout.live": el("p", { dataset: { en: EN.live, zh: ZH.live } }),
    ".hero-readout.plain": el("p", { hidden: true, dataset: { en: EN.plain, zh: ZH.plain } }),
    ".hero-readout.resolved": el("p", { hidden: true, dataset: { en: EN.resolved, zh: ZH.resolved } }),
    ".hero-timeline": svg, ".hero-status": el("p"), ".hero-howto": Object.assign(el("p"), { id: "hero-howto" }),
  };
  const fig = el("figure", { dataset: { src: "/data/hero_overlap.json" }, attrs: { "aria-describedby": "hero-sr" } });
  fig.querySelector = (s) => parts[s];
  fig.querySelectorAll = () => radios;
  const raf = [];
  const created = [];
  globalThis.document = {
    documentElement: { lang }, hidden: false, getElementById: () => fig, addEventListener() {},
    createElement: (t) => { const n = el(t); created.push(n); return n; }, createElementNS: (_, t) => el(t),
  };
  globalThis.window = { devicePixelRatio: 2 };
  globalThis.requestAnimationFrame = (f) => raf.push(f);
  globalThis.matchMedia = () => ({ matches: reduce });
  globalThis.fetch = async () => (fail ? new Response("", { status: 404 }) : new Response(JSON.stringify(DATA)));
  globalThis.ResizeObserver = class { constructor(f) { this.f = f; } observe() { this.f([]); } };
  globalThis.IntersectionObserver = class { constructor(f) { this.f = f; } observe() { this.f([{ isIntersecting: true }]); } };
  let clock = 0;
  globalThis.performance = { now: () => clock };
  const timers = new Map();
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
  const tds = () => created.filter((n) => n.tagName === "td");
  const status = parts[".hero-status"];
  let writes = 0;
  let statusText = "";
  Object.defineProperty(status, "textContent", { get: () => statusText, set(v) { statusText = v; writes++; } });
  return { fig, parts, radios, raf, run, tds, table, tbody, svg, writesOf: () => writes, T, k };
}
const realTimeout = setTimeout;
const settle = () => new Promise((r) => realTimeout(r, 30));
let n = 0;
const load = async (opts) => { const s = setup(opts); await import(`${HERO.href}?v=${++n}`); await settle(); return s; };

Deno.test("plays once, holds at the last window, keyboard and radiogroup", async () => {
  const { fig, parts, radios, raf, run, tds, writesOf } = await load();
  assert(raf.length === 1, "one frame scheduled after load");
  run(16);
  assert(fig.classList.contains("is-live"), "is-live after first frame");
  assert(parts[".hero-date"].textContent === "Jun 1983", parts[".hero-date"].textContent);
  assert(parts["input[type=range]"].max === "509", "range.max from data");
  assert(parts[".hero-play"].textContent === "Pause", "playing");
  assert(tds().length === 64, "64 cells built");
  assert(parts[".hero-readout.live"].textContent.startsWith("Jun 1983. Measured"), parts[".hero-readout.live"].textContent);
  assert(!parts[".hero-readout.live"].hidden && parts[".hero-readout.resolved"].hidden, "live shown during the sweep");
  run(3000);
  assert(writesOf() === 0, "no live-region write during the sweep");
  run(3200);                                                        // 90 months/s → 509 in ≈ 5.7 s
  assert(parts["input[type=range]"].value === "509", `at end: ${parts["input[type=range]"].value}`);
  assert(fig.classList.contains("hero-resolved"), "resolved at the last window");
  assert(parts[".hero-play"].textContent === "Play", "stopped");
  assert(!parts[".hero-readout.resolved"].hidden && parts[".hero-readout.live"].hidden, "resolved shown, live hidden");
  assert(writesOf() === 1 && parts[".hero-status"].textContent.startsWith("Nov 2025."), "status written once at the end");
  run(2000);
  assert(parts["input[type=range]"].value === "509" && raf.length === 0, "no wrap after 8 s");
  assert(fig.tabIndex === 0 && fig.getAttribute("aria-describedby") === "hero-sr hero-howto", "tab stop and how-to only once live");
  // After the sweep, an action returns to the live/plain readout: Plain ruler shows (and keeps) the plain
  // readout; back to the characteristic ruler the live readout shows for 1.5 s, then the resolved sentence.
  radios[0].click(); run(16);
  assert(!parts[".hero-readout.plain"].hidden && parts[".hero-readout.resolved"].hidden, "plain readout after the sweep");
  run(1600);
  assert(!parts[".hero-readout.plain"].hidden && parts[".hero-readout.resolved"].hidden && !fig.classList.contains("hero-resolved"), "plain readout kept at idle");
  assert(parts[".hero-status"].textContent === parts[".hero-readout.plain"].textContent, "plain sentence announced at idle");
  radios[1].click(); run(16);
  assert(!parts[".hero-readout.live"].hidden && parts[".hero-readout.resolved"].hidden, "live readout at the last window after an action");
  run(1600);
  assert(fig.classList.contains("hero-resolved") && !parts[".hero-readout.resolved"].hidden, "resolved again after 1.5 s");
  // Space on the figure restarts from 0; a second Space pauses.
  const sp = fig.fire("keydown", { key: " " });
  assert(sp.prevented && parts[".hero-play"].textContent === "Pause", "space plays from the end");
  run(48);
  assert(+parts["input[type=range]"].value < 20, "restarted from 0");
  fig.fire("keydown", { key: " " }); run(16);
  assert(parts[".hero-play"].textContent === "Play", "space pauses");
  const v = +parts["input[type=range]"].value;
  fig.fire("keydown", { key: "ArrowRight", shiftKey: true }); run(32);
  assert(+parts["input[type=range]"].value === v + 12, "shift+right = +12");
  fig.fire("keydown", { key: "ArrowLeft" }); run(32);
  assert(+parts["input[type=range]"].value === v + 11, "left = -1");
  fig.fire("keydown", { key: "End" }); run(32);
  assert(parts["input[type=range]"].value === "509", "End");
  fig.fire("keydown", { key: "Home" }); run(32);
  assert(parts["input[type=range]"].value === "0", "Home");
  assert(!fig.fire("keydown", { key: "Tab" }).prevented, "unhandled keys keep their default");
  parts["input[type=range]"].value = "309"; parts["input[type=range]"].fire("input"); run(16);
  assert(parts["input[type=range]"].getAttribute("aria-valuetext") === "Mar 2009", "aria-valuetext");
  assert(!fig.classList.contains("hero-resolved"), "live within 1.5 s of scrubbing");
  run(1600);
  assert(fig.classList.contains("hero-resolved") && raf.length === 0, "resolved after 1.5 s idle; loop idle");
  const g = parts["[role=radiogroup]"].fire("keydown", { key: "ArrowRight" });
  assert(g.prevented && radios[0].getAttribute("aria-checked") === "true" && radios[0].tabIndex === 0 && radios[1].tabIndex === -1 && radios[0].focused, "roving");
  run(16);
  assert(!parts[".hero-readout.plain"].hidden && parts[".hero-readout.live"].hidden, "plain readout after the arrow");
});

Deno.test("plain mode: 56 muted zeros, plain readout and caption; char restores", async () => {
  const { fig, parts, radios, run, tds, table } = await load();
  run(16);
  parts["input[type=range]"].value = "309"; parts["input[type=range]"].fire("input"); run(16);
  radios[0].click(); run(16);
  const cells = tds();
  const zeros = cells.filter((c) => c.textContent === "0" && c.style.props["--tint"] === "transparent");
  assert(zeros.length === 56, `${zeros.length} zeros`);
  assert(cells.filter((c) => c.textContent === "1").length === 8, "8 ones");
  assert(table.classList.contains("is-plain"), "is-plain on the table");
  assert(!parts[".hero-readout.plain"].hidden && parts[".hero-readout.live"].hidden, "plain readout shown");
  assert(table.querySelector("caption").textContent === EN.capPlain, "plain caption");
  run(1600);
  assert(!parts[".hero-readout.plain"].hidden && parts[".hero-readout.resolved"].hidden, "plain readout not replaced at idle");
  radios[1].click(); run(16);
  assert(cells[1].textContent === M.fmt2(DATA.corr[309][0]) && cells[1].style.props["--tint"].startsWith("rgba("), "values restored");
  assert(table.querySelector("caption").textContent === M.fill(EN.cap, { month: "Mar 2009" }), "char caption");
  assert(!parts[".hero-readout.live"].hidden && parts[".hero-readout.plain"].hidden, "live readout back");
  assert(parts[".hero-readout.live"].textContent.includes("small size and illiquidity"), "lc() pair names mid-sentence");
});

Deno.test("cell readout: mouse hover, touch ignored, click toggles", async () => {
  const { parts, run, tds } = await load();
  run(16);
  parts["input[type=range]"].value = "309"; parts["input[type=range]"].fire("input"); run(16);
  const cells = tds(), c01 = cells[1];
  const expected = M.fill(EN.cell, { a: "Small size", b: "illiquidity", v: M.fmt2(DATA.corr[309][0]), month: "Mar 2009" });
  c01.fire("pointerover", { pointerType: "mouse" });
  assert(parts[".hero-cell"].textContent === expected, parts[".hero-cell"].textContent);
  assert(parts[".hero-cell"].textContent === "Small size and illiquidity: 0.86 in the window ending Mar 2009.", "literal check");
  c01.fire("click", { pointerType: "mouse" });
  assert(parts[".hero-cell"].textContent === expected, "a mouse click after hover keeps the readout");
  assert(c01.classList.contains("is-on"), "cell highlighted");
  parts[".hero-heat"].fire("pointerleave", { pointerType: "mouse" }); run(400);
  assert(parts[".hero-cell"].textContent === "", "cleared 300 ms after the mouse leaves");
  cells[2].fire("pointerover", { pointerType: "touch" });
  assert(parts[".hero-cell"].textContent === "", "touch pointerover does nothing");
  cells[2].fire("click", { pointerType: "touch" });
  assert(parts[".hero-cell"].textContent.startsWith("Small size and low turnover: "), "tap shows");
  cells[2].fire("click", { pointerType: "touch" });
  assert(parts[".hero-cell"].textContent === "", "second tap on the same cell clears");
});

Deno.test("live region: written at idle after a seek, never while dragging", async () => {
  const { parts, run, svg, writesOf } = await load();
  run(16);
  parts["input[type=range]"].value = "100"; parts["input[type=range]"].fire("input"); run(16);
  assert(parts[".hero-status"].textContent === "", "empty after the seek");
  run(1000);
  assert(parts[".hero-status"].textContent === "" && writesOf() === 0, "still empty before 1.5 s");
  run(600);
  assert(parts[".hero-status"].textContent === parts[".hero-readout.live"].textContent && writesOf() === 1, "equals the live readout at idle");
  svg.fire("pointerdown", { clientX: 200, pointerId: 1, button: 0, pointerType: "mouse" });
  svg.fire("pointermove", { clientX: 300, pointerId: 1, pointerType: "mouse" });
  run(2000);
  assert(writesOf() === 1, "no write while dragging");
  svg.fire("pointerup", { pointerId: 1 });
  run(1600);
  assert(writesOf() === 2 && parts[".hero-status"].textContent === parts[".hero-readout.live"].textContent, "written once after the drag ends");
  assert(+parts["input[type=range]"].value > 100, `timeline drag moved the cursor: ${parts["input[type=range]"].value}`);
});

Deno.test("timeline pointers: a page scroll or a right-click leaves the sweep alone; touch drags and taps seek", async () => {
  const { parts, run, svg } = await load();
  run(16); run(1000);
  const before = +parts["input[type=range]"].value;
  assert(before > 0 && parts[".hero-play"].textContent === "Pause", "sweeping");
  svg.fire("pointerdown", { clientX: 400, clientY: 50, pointerId: 2, button: 0, pointerType: "touch" });
  svg.fire("pointermove", { clientX: 402, clientY: 90, pointerId: 2, pointerType: "touch" });
  svg.fire("pointercancel", { pointerId: 2, pointerType: "touch" });
  run(16);
  assert(parts[".hero-play"].textContent === "Pause" && +parts["input[type=range]"].value >= before, "vertical swipe: still playing, no seek");
  svg.fire("pointerdown", { clientX: 100, pointerId: 3, button: 2, pointerType: "mouse" });
  run(16);
  assert(parts[".hero-play"].textContent === "Pause", "right button does not scrub");
  svg.fire("pointerdown", { clientX: 450, clientY: 50, pointerId: 4, button: 0, pointerType: "touch" });
  svg.fire("pointermove", { clientX: 520, clientY: 52, pointerId: 4, pointerType: "touch" });
  svg.fire("pointerup", { clientX: 520, clientY: 52, pointerId: 4, pointerType: "touch" });
  run(16);
  const dragged = +parts["input[type=range]"].value;
  assert(parts[".hero-play"].textContent === "Play" && Math.abs(dragged - Math.round(((520 - 40) / (900 - 72)) * 509)) <= 1, `horizontal touch drag seeks: ${dragged}`);
  svg.fire("pointerdown", { clientX: 40, clientY: 50, pointerId: 5, button: 0, pointerType: "touch" });
  svg.fire("pointerup", { clientX: 42, clientY: 51, pointerId: 5, pointerType: "touch" });
  run(16);
  assert(+parts["input[type=range]"].value <= 2, `tap seeks once: ${parts["input[type=range]"].value}`);
});

Deno.test("reduced motion starts at the last window, paused and resolved; zh strings", async () => {
  const { fig, parts, run, writesOf } = await load({ lang: "zh-Hans", reduce: true });
  run(16);
  assert(fig.classList.contains("is-live"), "live");
  run(100);
  assert(writesOf() === 0, "nothing announced at load under reduced motion");
  assert(parts["input[type=range]"].value === "509" && parts[".hero-play"].textContent === "播放", "paused at 509");
  assert(fig.classList.contains("hero-resolved") && !parts[".hero-readout.resolved"].hidden, "resolved at once");
  assert(parts[".hero-readout.resolved"].textContent === ZH.resolved, "zh resolved text");
  assert(parts[".hero-date"].textContent === "2025 年 11 月", parts[".hero-date"].textContent);
  assert(parts[".hero-readout.live"].textContent.includes("不计正负") && parts[".hero-readout.live"].textContent.startsWith("2025 年 11 月。"), "zh readout");
  assert(parts[".hero-hint"].textContent === ZH.hint, "zh hint");
  parts[".hero-play"].click(); run(260);
  assert(+parts["input[type=range]"].value === 12, `reduced Play steps 12 months per 250 ms: ${parts["input[type=range]"].value}`);
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

Deno.test("fetch failure leaves the PNG; a missing <caption> does not throw", async () => {
  const warn = console.warn; console.warn = () => {};
  const { fig, raf } = await load({ fail: true }).finally(() => { console.warn = warn; });
  assert(!fig.classList.contains("is-live") && raf.length === 0, "static fallback");
  const s = await load({ noCaption: true });
  s.run(64);
  assert(s.fig.classList.contains("is-live"), "live without a caption");
});
