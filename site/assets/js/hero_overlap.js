// assets/js/hero_overlap.js — home-page Figure 1: signed overlap among eight related characteristics
// under the rolling characteristic ruler (spec "interactive dynamic-geometry hero", revision 2).
// Dependency-free ES module. Everything shown comes from /data/hero_overlap.json: the 8×8 block of the
// 20-year characteristic ruler per window (28 signed values, 2 dp), the average size of the overlaps with
// the sign ignored, and the participation dimension of the full 153-characteristic window matrix.
// The table body and the timeline SVG are built once from pure model builders (rowsModel, timelineModel)
// with createElement/createElementNS and textContent; no markup string is ever assigned to the DOM, so a
// tampered JSON can only change numbers and labels as text. Until the first frame (and whenever the fetch
// fails, JS is off, or frame() throws) the figure lacks `is-live`, so theme.scss shows the fallback PNG.

const RATE = 90;                 // months per second during the one automatic sweep (≈ 5.7 s for 510 windows)
const IDLE = 1500;               // ms of no interaction before the resolved sentence
const HOVER_OFF = 300;           // ms before a mouse leaving the table clears the cell readout
const REDUCE_STEP = 12, REDUCE_MS = 250;   // reduced motion: Play steps 12 months every 250 ms
const INK = [24, 89, 139];       // hsl(206,70%,32%), the site's $ink (--hero-pos)
const NEG = [166, 95, 48];       // hsl(24,55%,42%), second hue for negative cells only (--hero-neg)
const DIAG = "var(--rule)";
const SVG = "http://www.w3.org/2000/svg";
const MAX_LABEL = 40;
const TXT = { en: { play: "Play", pause: "Pause" }, zh: { play: "播放", pause: "暂停" } };
const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// Timeline geometry (px): margins around the plot area inside the SVG.
export const TL = { left: 40, right: 32, top: 10, bottom: 18, labelMinWidth: 600 };

// ---- Pure helpers (exported for the deno test) ---------------------------------------------
export const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
export const lc = (s) => (s ? s.charAt(0).toLowerCase() + s.slice(1) : s);
export const fill = (tpl, vals) => tpl.replace(/\{(\w+)\}/g, (m, k) => (k in vals ? vals[k] : m));
export function fmt2(v) {
  const s = Math.abs(v).toFixed(2);
  return v < 0 && s !== "0.00" ? `−${s}` : s;           // −0.07; 0 and −0 read "0.00"
}
export function fmt1(v) {
  const s = Math.abs(v).toFixed(1);
  return v < 0 && s !== "0.0" ? `−${s}` : s;
}
export function argmaxAbs(row) {
  let k = 0;
  for (let i = 1; i < row.length; i++) if (Math.abs(row[i]) > Math.abs(row[k])) k = i;
  return k;
}
// Cell tint: rgba(hue, 0.08 + 0.50·|v|); ink for v ≥ 0, the warm hue for v < 0 (set on --tint directly).
export function tint(v) {
  const [r, g, b] = v < 0 ? NEG : INK;
  const a = 0.08 + 0.50 * Math.min(1, Math.abs(v));
  return `rgba(${r},${g},${b},${a.toFixed(3)})`;
}
export function labelFor(months, i, lang) {
  const s = months[i], y = +s.slice(0, 4), m = +s.slice(5, 7);
  return lang === "zh" ? `${y} 年 ${m} 月` : `${MONTHS_EN[m - 1]} ${y}`;    // zh spaced like the page text
}
// Numerals per sentence under the spec's definition (acceptance 9): a digit run [0-9][0-9.,%]* that is not
// attached to letters, "×" or "-by-", not a label/page reference (Figure 1, Table I, 图 1, p. 31, 第 31 页),
// page lists included, with a month-year date ("March 2009", "Mar 2009", "2009 年 3 月") and a year range
// ("1983–2025") counting as one.
export function countNumerals(sentence) {
  let s = ` ${sentence} `;
  const one = " D ";
  s = s.replace(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{4}\b/g, one);
  s = s.replace(/[0-9]{4}\s*年\s*[0-9]{1,2}\s*月/g, one);
  s = s.replace(/[0-9]{4}[–-][0-9]{4}(?:\s*年)?/g, one);
  s = s.replace(/(?:pp?\.|第)\s?[0-9]+(?:\s?[,、–-]\s?[0-9]+)*(?:\s*页)?/g, " ");     // p. 31, pp. 7, 23, 第 7、23 页
  s = s.replace(/(?:Figure|Table|Fig\.|图)\s?[0-9][0-9.,%]*/g, " ");
  s = s.replace(/[0-9]+(?:×|-by-)[0-9]+/g, " ");
  s = s.replace(/[A-Za-z]+[0-9][0-9.,%]*|[0-9][0-9.,%]*[A-Za-z]+/g, " ");
  const runs = s.match(/[0-9][0-9.,%]*/g) || [];
  return runs.length + (s.match(/ D /g) || []).length;
}
export function validate(d) {
  const n = d && Array.isArray(d.months) ? d.months.length : 0;
  const v = d && Array.isArray(d.vars) ? d.vars : [];
  const pairs = d && Array.isArray(d.pairs) ? d.pairs : [];
  const ok = n > 1 && v.length === 8 && pairs.length === (v.length * (v.length - 1)) / 2
    && [d.corr, d.avg_abs, d.pd].every((a) => Array.isArray(a) && a.length === n)
    && d.corr.every((row) => Array.isArray(row) && row.length === pairs.length && row.every(Number.isFinite))
    && d.avg_abs.every(Number.isFinite) && d.pd.every(Number.isFinite)
    && d.meta && d.meta.axes && ["avg_abs", "pd"].every((k) => Array.isArray(d.meta.axes[k])
      && d.meta.axes[k].length === 2 && d.meta.axes[k].every(Number.isFinite))
    && v.every((x) => ["en", "zh"].every((k) => typeof x[k] === "string" && x[k].length > 0 && x[k].length <= MAX_LABEL))
    && pairs.every(([i, j]) => Number.isInteger(i) && Number.isInteger(j) && i >= 0 && i < j && j < v.length)
    && d.months.every((m) => typeof m === "string" && /^[0-9]{4}-[0-9]{2}$/.test(m));
  if (!ok) throw new Error("hero: malformed hero_overlap.json");
  return d;
}

// ---- Model builders (pure; init() turns them into nodes) -------------------------------------
function pairIndex(data) {
  const idx = new Map();
  data.pairs.forEach(([i, j], k) => idx.set(`${i},${j}`, k));
  return (i, j) => (i < j ? idx.get(`${i},${j}`) : idx.get(`${j},${i}`));
}
export function rowsModel(data, t, mode, lang) {
  const k = pairIndex(data), row = data.corr[t], n = data.vars.length;
  return data.vars.map((v, i) => ({
    header: `${i + 1} ${v[lang] || v.en}`,
    cells: Array.from({ length: n }, (_, j) => {
      if (i === j) return { text: mode === "plain" ? "1" : "1.00", tint: DIAG, diagonal: true };
      if (mode === "plain") return { text: "0", tint: null, diagonal: false };
      const val = row[k(i, j)];
      return { text: fmt2(val), tint: tint(val), diagonal: false };
    }),
  }));
}
export function timelineModel(data, w, h, t = 0) {
  const x0 = TL.left, x1 = Math.max(x0 + 1, w - TL.right), y0 = TL.top, y1 = Math.max(y0 + 1, h - TL.bottom);
  const last = data.months.length - 1, pw = x1 - x0, ph = y1 - y0;
  const xOf = (i) => x0 + (pw * i) / last;
  const [aLo, aHi] = data.meta.axes.avg_abs, [pLo, pHi] = data.meta.axes.pd;
  const yA = (v) => y1 - ((v - aLo) / (aHi - aLo)) * ph;
  const yP = (v) => y1 - ((v - pLo) / (pHi - pLo)) * ph;
  const path = (arr, yOf) => arr.map((v, i) => `${i ? "L" : "M"}${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`).join("");
  const decades = [];
  data.months.forEach((m, i) => {
    const y = +m.slice(0, 4);
    if (m.endsWith("-01") && y % 10 === 0) decades.push({ x: xOf(i), label: String(y) });
  });
  // End years sit inside the plot (anchored start/end) so they clear the axis tick labels beside them.
  const ends = [{ x: x0, label: pw >= 500 ? data.months[0].slice(0, 4) : "", anchor: "start" },
                { x: x1, label: pw >= 500 ? data.months[last].slice(0, 4) : "", anchor: "end" }];
  // Full series labels from labelMinWidth; below it short labels, the second one moved to the empty bottom
  // right of the plot (both series stay above the lowest fifth of their fixed axes) only when both short labels
  // (about 88 + 130 px) do not fit on one line. The cursor starts below the top label row (see buildTimeline).
  const short = w < TL.labelMinWidth, stack = pw < 240;
  const labels = [
    { x: x0 + 6, y: y0 + 12, cls: "hero-tl-label hero-tl-label-avg", key: "avg", short },
    { x: x1 - 6, y: stack ? y1 - 5 : y0 + 12, cls: "hero-tl-label hero-tl-label-pd", key: "pd", short },
  ];
  return {
    plot: { x0, x1, y0, y1 },
    axes: [
      { side: "left", ticks: [{ y: yA(aLo), label: aLo.toFixed(2) }, { y: yA(aHi), label: aHi.toFixed(2) }], key: "avg" },
      { side: "right", ticks: [{ y: yP(pLo), label: String(pLo) }, { y: yP(pHi), label: String(pHi) }], key: "pd" },
    ],
    paths: [{ cls: "hero-tl-avg", d: path(data.avg_abs, yA) }, { cls: "hero-tl-pd", d: path(data.pd, yP) }],
    decades: ends.concat(decades),
    labels,
    cursor: { x: xOf(t) },
    dots: [{ x: xOf(t), y: yA(data.avg_abs[t]), cls: "hero-tl-dot" }, { x: xOf(t), y: yP(data.pd[t]), cls: "hero-tl-dot hero-tl-dot-pd" }],
  };
}

// ---- Figure ---------------------------------------------------------------------------------
async function init(fig) {
  const $ = (s) => fig.querySelector(s);
  const range = $("input[type=range]"), playBtn = $(".hero-play"), dateEl = $(".hero-date"), hint = $(".hero-hint");
  const group = $("[role=radiogroup]"), radios = [...fig.querySelectorAll("[role=radio]")];
  const table = $(".hero-heat"), cap = table.querySelector("caption"), tbody = table.querySelector("tbody");
  const cellOut = $(".hero-cell"), live = $(".hero-readout.live"), plain = $(".hero-readout.plain");
  const resolved = $(".hero-readout.resolved"), svg = $(".hero-timeline"), status = $(".hero-status");
  const howto = $(".hero-howto"), wrap = $(".hero-heat-wrap");
  const docLang = document.documentElement.lang || "en", lang = docLang.startsWith("zh") ? "zh" : "en";
  const T = TXT[lang];
  const ds = (el, key) => (el && el.dataset ? (el.dataset[key] || "") : "");

  let data;
  try {
    const r = await fetch(fig.dataset.src);
    if (!r.ok) throw new Error(`hero: HTTP ${r.status}`);
    data = validate(await r.json());
  } catch (e) {
    console.warn(e);        // keep the PNG; controls and readouts stay hidden (no is-live)
    return;
  }

  const last = data.months.length - 1;
  const labels = data.months.map((_, i) => labelFor(data.months, i, lang));
  const nf1 = new Intl.NumberFormat(docLang, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat(docLang, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const tplLive = ds(live, lang) || ds(live, "en"), tplCell = ds(cellOut, lang) || ds(cellOut, "en");
  const tplCellPlain = ds(cellOut, lang === "zh" ? "plainZh" : "plainEn") || ds(cellOut, "plainEn");
  plain.textContent = ds(plain, lang) || ds(plain, "en");
  resolved.textContent = ds(resolved, lang) || ds(resolved, "en");
  if (hint) hint.textContent = ds(hint, lang) || ds(hint, "en");
  range.max = String(last);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const checked = radios.find((b) => b.getAttribute("aria-checked") === "true");
  const S = {
    pos: reduce ? last : 0, t: -1, mode: checked ? checked.dataset.mode : "char", playing: false,
    userPaused: reduce, dragging: false, onscreen: true, visible: !document.hidden, res: null,
    idleSince: -Infinity, dead: false, prev: null, raf: 0, timer: 0, hoverTimer: 0, stepAcc: 0,
    w: 0, h: 0, cellShown: null, shownMode: null, announced: "", acted: false, idleDone: false, down: null,
  };

  // Table body from rowsModel: 8 rows × (row header + 8 cells); numbers are refreshed per frame.
  const cells = [], rowHeads = [], colHeads = [...table.querySelectorAll("thead th")].slice(1);
  rowsModel(data, 0, S.mode, lang).forEach((r, i) => {
    const tr = document.createElement("tr"), th = document.createElement("th");
    th.setAttribute("scope", "row");
    th.textContent = r.header;
    tr.appendChild(th);
    rowHeads.push(th);
    const rowCells = r.cells.map((c, j) => {
      const td = document.createElement("td");
      if (c.diagonal) td.classList.add("diag");
      td.dataset.i = String(i); td.dataset.j = String(j);
      tr.appendChild(td);
      return td;
    });
    cells.push(rowCells);
    tbody.appendChild(tr);
  });

  // Timeline SVG from timelineModel: static parts rebuilt on resize, cursor and dots moved per frame.
  const svgEl = (tag, attrs) => {
    const el = document.createElementNS(SVG, tag);
    for (const k in attrs) el.setAttribute(k, String(attrs[k]));
    return el;
  };
  const g = svgEl("g", {}), cursor = svgEl("line", { class: "hero-tl-cursor" });
  const dots = [svgEl("circle", { r: 3.5, class: "hero-tl-dot" }), svgEl("circle", { r: 3, class: "hero-tl-dot hero-tl-dot-pd" })];
  const gLab = svgEl("g", {});      // series labels drawn over the cursor and dots (haloed in theme.scss)
  svg.appendChild(g); svg.appendChild(cursor); dots.forEach((d) => svg.appendChild(d)); svg.appendChild(gLab);
  const tlLabel = (key, short) => {
    const k = `${key}${short ? "Short" : ""}${lang === "zh" ? "Zh" : "En"}`;
    return ds(svg, k) || ds(svg, `${key}${lang === "zh" ? "Zh" : "En"}`);
  };
  let plot = null;
  function buildTimeline() {
    const model = timelineModel(data, S.w, S.h, Math.max(0, S.t));
    plot = model.plot;
    svg.setAttribute("viewBox", `0 0 ${S.w} ${S.h}`);
    g.replaceChildren(); gLab.replaceChildren();
    g.appendChild(svgEl("line", { class: "hero-tl-axis", x1: plot.x0, x2: plot.x1, y1: plot.y1, y2: plot.y1 }));
    for (const ax of model.axes) {
      for (const tk of ax.ticks) {
        const x = ax.side === "left" ? plot.x0 : plot.x1;
        g.appendChild(svgEl("line", { class: "hero-tl-axis", x1: x - (ax.side === "left" ? 4 : 0), x2: x + (ax.side === "left" ? 0 : 4), y1: tk.y, y2: tk.y }));
        const txt = svgEl("text", { x: ax.side === "left" ? x - 6 : x + 6, y: tk.y + 3.5, "text-anchor": ax.side === "left" ? "end" : "start", class: `hero-tl-tick hero-tl-tick-${ax.key}` });
        txt.textContent = tk.label;
        g.appendChild(txt);
      }
    }
    for (const d of model.decades) {
      g.appendChild(svgEl("line", { class: "hero-tl-axis", x1: d.x, x2: d.x, y1: plot.y1, y2: plot.y1 + 4 }));
      if (d.label) {
        const txt = svgEl("text", { x: d.x, y: plot.y1 + 14, "text-anchor": d.anchor || "middle", class: "hero-tl-year" });
        txt.textContent = d.label;
        g.appendChild(txt);
      }
    }
    for (const p of model.paths) g.appendChild(svgEl("path", { class: p.cls, d: p.d }));
    for (const l of model.labels) {
      const txt = svgEl("text", { x: l.x, y: l.y, class: l.cls, "text-anchor": l.key === "avg" ? "start" : "end" });
      txt.textContent = tlLabel(l.key, l.short);
      gLab.appendChild(txt);
    }
    // No series point enters the top 16 px (peaks: 0.293 on 0.20–0.35, 22.91 on 20–24), so the cursor starts below the label row.
    cursor.setAttribute("y1", String(plot.y0 + 16)); cursor.setAttribute("y2", String(plot.y1));
  }

  const kick = () => { if (!S.raf && !S.dead) S.raf = requestAnimationFrame(tick); };
  function tick(now) {
    S.raf = 0;
    try { frame(now); } catch (e) {
      S.dead = true;                  // stop the loop; the PNG and static caption return
      fig.classList.remove("is-live");
      console.warn(e);
    }
  }
  function sync() {
    const p = !S.userPaused && S.onscreen && S.visible;
    if (p !== S.playing) { S.playing = p; S.prev = null; S.stepAcc = 0; }
    playBtn.textContent = S.userPaused ? T.play : T.pause;
    kick();
  }
  function touch() {                  // an interaction: live (or plain) readout for IDLE ms, then resolved
    S.idleSince = performance.now();
    S.res = null; S.idleDone = false; S.acted = true;
    clearTimeout(S.timer);
    S.timer = setTimeout(kick, IDLE + 20);
  }
  function seek(i) {
    S.pos = clamp(Math.round(i), 0, last);
    S.userPaused = true;
    touch(); sync();
  }
  function currentSentence() {
    return S.mode === "plain" ? plain.textContent : live.textContent;
  }
  function announce() {               // the one live region; written only at idle, on Pause and at the end
    if (S.playing || S.dragging) return;
    const s = currentSentence();
    if (s && s !== S.announced) { S.announced = s; status.textContent = s; }
  }
  function showCell(td) {
    S.cellShown = td;
    for (const row of cells) for (const c of row) c.classList.toggle("is-on", c === td);
    rowHeads.forEach((h, i) => h.classList.toggle("is-on", !!td && +td.dataset.i === i));
    colHeads.forEach((h, j) => h.classList.toggle("is-on", !!td && +td.dataset.j === j));
    cellText();
  }
  function cellText() {
    const td = S.cellShown;
    if (!td) { cellOut.textContent = ""; return; }
    const i = +td.dataset.i, j = +td.dataset.j, t = Math.max(0, S.t);
    const a = data.vars[i][lang] || data.vars[i].en, bRaw = data.vars[j][lang] || data.vars[j].en;
    const b = lang === "en" ? lc(bRaw) : bRaw;     // the first label opens the sentence; the second is mid-sentence
    if (S.mode === "plain") cellOut.textContent = fill(tplCellPlain, { a, b });
    else cellOut.textContent = fill(tplCell, { a, b, v: fmt2(data.corr[t][pairOf(i, j)]), month: labels[t] });
  }
  const pairOf = pairIndex(data);
  function setMode(mode, focus) {
    S.mode = mode;
    for (const b of radios) {
      const on = b.dataset.mode === mode;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
      if (on && focus) b.focus();
    }
    S.userPaused = true;
    touch(); sync();
  }

  function frame(now) {
    const dt = S.prev == null ? 0 : Math.min(now - S.prev, 100);
    S.prev = now;
    if (S.playing) {
      if (S.pos >= last) {                              // one sweep: hold at the last window and stop
        S.userPaused = true; S.playing = false; S.idleSince = -Infinity; S.acted = true;
        playBtn.textContent = T.play;
      } else if (reduce) {
        S.stepAcc += dt;
        if (S.stepAcc >= REDUCE_MS) { S.stepAcc -= REDUCE_MS; S.pos = Math.min(last, S.pos + REDUCE_STEP); }
      } else S.pos = Math.min(last, S.pos + (RATE * dt) / 1000);
    }
    const t = clamp(Math.round(S.pos), 0, last);
    const modeChanged = S.mode !== S.shownMode;
    if (t !== S.t || modeChanged) {
      S.t = t; S.shownMode = S.mode;
      draw(t);
    }
    // Idle once the sweep has ended (idleSince = -Infinity) or IDLE ms after the reader's last action; while
    // the one automatic sweep is still pending (figure below the fold, tab hidden) the live readout stays.
    // The resolved sentence reports characteristic-ruler numbers, so it replaces only the live readout: under
    // the plain ruler the plain readout stays. The live region is written once per idle period, and only
    // after an action or the end of the sweep (nothing at load under reduced motion).
    const idle = !S.playing && !S.dragging && S.userPaused && now - S.idleSince >= IDLE;
    const res = idle && S.mode === "char";
    if (res !== S.res) {
      S.res = res;
      fig.classList.toggle("hero-resolved", res);
      live.hidden = res || S.mode !== "char";
      plain.hidden = res || S.mode !== "plain";
      resolved.hidden = !res;
    }
    if (idle && !S.idleDone) { S.idleDone = true; if (S.acted) announce(); }
    if (S.playing) S.raf = requestAnimationFrame(tick);
    else S.prev = null;
    if (S.w && !fig.classList.contains("is-live")) {
      fig.classList.add("is-live");
      fig.tabIndex = 0;                // a tab stop, with the how-to sentence, only once the controls exist
      if (howto) fig.setAttribute("aria-describedby", `${fig.getAttribute("aria-describedby") || "hero-sr"} ${howto.id}`);
    }
  }

  function draw(t) {
    const model = rowsModel(data, t, S.mode, lang), plainMode = S.mode === "plain";
    table.classList.toggle("is-plain", plainMode);
    model.forEach((r, i) => r.cells.forEach((c, j) => {
      const td = cells[i][j];
      td.textContent = c.text;
      td.style.setProperty("--tint", c.tint || "transparent");
    }));
    if (cap) cap.textContent = plainMode ? (ds(cap, lang === "zh" ? "plainZh" : "plainEn") || ds(cap, "plainEn"))
      : fill(ds(cap, lang) || ds(cap, "en"), { month: labels[t] });
    dateEl.textContent = labels[t];
    if (range.value !== String(t)) range.value = String(t);
    range.setAttribute("aria-valuetext", labels[t]);
    if (plot) {
      const tl = timelineModel(data, S.w, S.h, t);
      cursor.setAttribute("x1", tl.cursor.x.toFixed(1)); cursor.setAttribute("x2", tl.cursor.x.toFixed(1));
      tl.dots.forEach((d, k) => { dots[k].setAttribute("cx", d.x.toFixed(1)); dots[k].setAttribute("cy", d.y.toFixed(1)); });
    }
    const k = argmaxAbs(data.corr[t]), [ia, ib] = data.pairs[k];
    const a = data.vars[ia][lang] || data.vars[ia].en, b = data.vars[ib][lang] || data.vars[ib].en;
    live.textContent = fill(tplLive, {
      month: labels[t], avg: nf2.format(data.avg_abs[t]), top: fmt2(data.corr[t][k]),
      a: lang === "en" ? lc(a) : a, b: lang === "en" ? lc(b) : b, pd: nf1.format(data.pd[t]),
    });
    if (!S.res) { live.hidden = plainMode; plain.hidden = !plainMode; }
    if (S.cellShown) cellText();
  }

  // ---- Controls -----------------------------------------------------------------------------
  range.addEventListener("input", () => seek(+range.value));
  playBtn.addEventListener("click", () => {
    S.userPaused = !S.userPaused;
    if (!S.userPaused && S.pos >= last) S.pos = 0;
    S.res = null;
    if (S.userPaused) { S.idleSince = performance.now(); S.playing = false; announce(); }
    touch(); sync();
  });
  for (const b of radios) b.addEventListener("click", () => setMode(b.dataset.mode));
  const KEYS = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 };
  group.addEventListener("keydown", (e) => {
    if (!(e.key in KEYS) || e.altKey || e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    const n = radios.length, i = radios.findIndex((b) => b.dataset.mode === S.mode);
    setMode(radios[(i + KEYS[e.key] + n) % n].dataset.mode, true);
  });
  fig.addEventListener("keydown", (e) => {        // figure itself focused (tabindex=0)
    if (e.target !== fig || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === " ") { e.preventDefault(); playBtn.click(); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      seek(Math.round(S.pos) + (e.shiftKey ? 12 : 1) * (e.key === "ArrowLeft" ? -1 : 1));
    } else if (e.key === "Home") { e.preventDefault(); seek(0); }
    else if (e.key === "End") { e.preventDefault(); seek(last); }
  });
  // Timeline scrubbing: pointer anywhere on the SVG.
  const scrub = (e) => {
    const r = svg.getBoundingClientRect(), pw = plot ? plot.x1 - plot.x0 : Math.max(1, r.width - TL.left - TL.right);
    const x0 = plot ? plot.x0 : TL.left, scale = r.width && S.w ? r.width / S.w : 1;
    seek(((e.clientX - r.left) / scale - x0) / pw * last);
  };
  // A mouse scrubs from pointerdown. Touch and pen scrub only once horizontal travel wins (a vertical swipe
  // is a page scroll: the browser takes it and sends pointercancel, which leaves the figure untouched); a
  // tap seeks once. Only the primary button scrubs.
  const TAP = 8;
  const startDrag = (e) => { S.dragging = true; if (svg.setPointerCapture) svg.setPointerCapture(e.pointerId); };
  svg.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    S.down = { x: e.clientX, y: e.clientY, id: e.pointerId };
    if (e.pointerType === "mouse") { startDrag(e); scrub(e); }
  });
  svg.addEventListener("pointermove", (e) => {
    if (!S.dragging && S.down && e.pointerId === S.down.id) {
      const dx = Math.abs(e.clientX - S.down.x), dy = Math.abs(e.clientY - S.down.y);
      if (dx > TAP && dx > dy) startDrag(e);
    }
    if (S.dragging) scrub(e);
  });
  const stop = () => { S.down = null; if (S.dragging) { S.dragging = false; touch(); kick(); } };
  svg.addEventListener("pointerup", (e) => {
    const d = S.down;
    if (!S.dragging && d && e.pointerId === d.id && Math.abs(e.clientX - d.x) < TAP && Math.abs(e.clientY - d.y) < TAP) scrub(e);
    stop();
  });
  svg.addEventListener("pointercancel", stop);
  svg.addEventListener("lostpointercapture", stop);
  // Cell readout: mouse hover shows, leaving the table clears after HOVER_OFF; click toggles (all pointers).
  for (const row of cells) for (const td of row) {
    if (td.classList.contains("diag")) continue;
    td.addEventListener("pointerover", (e) => {
      if (e.pointerType !== "mouse") return;
      clearTimeout(S.hoverTimer);
      showCell(td);
    });
    td.addEventListener("click", (e) => {     // a mouse click keeps what hover showed; touch and pen toggle
      clearTimeout(S.hoverTimer);
      if (e.pointerType === "mouse") { showCell(td); return; }
      showCell(S.cellShown === (e.currentTarget || td) ? null : td);
    });
  }
  table.addEventListener("pointerleave", (e) => {
    if (e.pointerType !== "mouse") return;
    clearTimeout(S.hoverTimer);
    S.hoverTimer = setTimeout(() => showCell(null), HOVER_OFF);
  });

  // Narrow widths: the table scrolls inside its wrapper; theme.scss fades the right edge until the end.
  const edge = () => { if (wrap && wrap.classList) wrap.classList.toggle("at-end", wrap.scrollLeft + wrap.clientWidth >= wrap.scrollWidth - 1); };
  if (wrap && wrap.addEventListener) wrap.addEventListener("scroll", edge, { passive: true });

  // ---- Observers ----------------------------------------------------------------------------
  new ResizeObserver(() => {
    const w = svg.clientWidth || (svg.getBoundingClientRect && svg.getBoundingClientRect().width) || 0;
    const h = svg.clientHeight || (svg.getBoundingClientRect && svg.getBoundingClientRect().height) || 0;
    if (!w || !h) return;
    S.w = Math.round(w); S.h = Math.round(h);
    buildTimeline();
    S.t = -1;                          // force a redraw at the new size
    edge();
    kick();
  }).observe(svg);
  new IntersectionObserver(([en]) => { S.onscreen = en.isIntersecting; sync(); }, { threshold: 0.1 }).observe(fig);
  document.addEventListener("visibilitychange", () => { S.visible = !document.hidden; sync(); });
  sync();
}

if (typeof document !== "undefined") {
  const fig = document.getElementById("hero");
  if (fig && fig.dataset.src) init(fig).catch((e) => { fig.classList.remove("is-live"); console.warn(e); });
}
