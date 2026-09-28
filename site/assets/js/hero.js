// assets/js/hero.js — home-page Figure 1, the characteristic ruler (spec "Hero animation").
// Dependency-free ES module, Canvas 2D. Everything drawn comes from /data/hero_geometry.json:
// the two monthly summary statistics of the 132×132 EWMA version of the characteristic ruler
// (Gram metric; top-eigenvalue share, participation dimension), the participation-dimension series in the strip
// and the NBER recession months. Nothing on the canvas is synthetic and the canvas draws no words.
// Until the first frame (and whenever the fetch fails, JS is off, or frame() throws) the figure
// lacks `is-live`, so theme.scss shows the fallback PNG and the static caption only.

const RULER_H = 200, STRIP_H = 48, H = RULER_H + STRIP_H;      // fixed 248 px, all breakpoints
const SPOKES = 24, PAD = 8;
const RATE = 60, HOLD = 2000, MODE_MS = 600, IDLE = 1500;       // months/s, ms, ms, ms
const INK = "#18557f", CIRCLE = "#b9b3a6", SPOKE = "rgba(0,0,0,.35)";
const BAND = "rgba(0,0,0,.06)", PD_LINE = "rgba(0,0,0,.5)", RULE = "rgba(0,0,0,.1)";
const TXT = {
  en: { play: "Play", pause: "Pause", nber: " Shaded: NBER recession, retrospective context." },
  zh: { play: "播放", pause: "暂停", nber: "阴影：NBER 衰退期，仅作事后参考。" },
};

// ---- Encoding (stated in the caption and footnote 1) -------------------------------------
export const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
export const ease = (a) => (a < 0.5 ? 4 * a * a * a : 1 - Math.pow(-2 * a + 2, 3) / 2);

// Month statistics -> [lam1, lam2] of M(t) = diag(lam1², lam2²); det M = size².
export function encode(share, pd) {
  const u = clamp((share - 0.1176) / (0.1521 - 0.1176), 0, 1);   // concentration
  const v = clamp((pd - 17.36) / (22.63 - 17.36), 0, 1);          // effective breadth
  const ratio = 1.4 + 2.6 * u, size = 0.85 + 0.30 * v;
  return [size * Math.sqrt(ratio), size / Math.sqrt(ratio)];
}
// Log-interpolation of the eigenvalues: every intermediate frame is a valid metric.
export const mix = (a, b, alpha) =>
  [0, 1].map((i) => Math.exp((1 - alpha) * Math.log(a[i]) + alpha * Math.log(b[i])));
// Measured length of the unit coefficient e_phi: ||e_phi||_M = sqrt(lam1² cos² + lam2² sin²).
export const spokeLen = (m, phi) => Math.hypot(m[0] * Math.cos(phi), m[1] * Math.sin(phi));
export function metricFor(data, t) {
  const i = clamp(Math.floor(t), 0, data.pd.length - 1), j = Math.min(i + 1, data.pd.length - 1);
  const a = encode(data.share[i], data.pd[i]);
  return j === i || t === i ? a : mix(a, encode(data.share[j], data.pd[j]), ease(t - i));
}
export const inRecession = (nber, i) => nber.some(([a, b]) => i >= a && i <= b);
export const fill = (tpl, vals) => tpl.replace(/\{(\w+)\}/g, (m, k) => (k in vals ? vals[k] : m));
export function validate(d) {
  const n = d && Array.isArray(d.pd) ? d.pd.length : 0;
  const ok = n > 1 && [d.share, d.months].every((a) => Array.isArray(a) && a.length === n)
    && Array.isArray(d.nber) && d.pd.concat(d.share).every(Number.isFinite);
  if (!ok) throw new Error("hero: malformed hero_geometry.json");
  return d;
}

// ---- Figure -------------------------------------------------------------------------------
async function init(fig) {
  const $ = (s) => fig.querySelector(s);
  const canvas = $("canvas"), ctx = canvas.getContext("2d"), range = $("input[type=range]");
  const playBtn = $(".hero-play"), dateEl = $(".hero-date"), group = $("[role=radiogroup]");
  const live = $(".hero-caption .live"), resolved = $(".hero-caption .resolved");
  const radios = [...fig.querySelectorAll("[role=radio]")];
  const docLang = document.documentElement.lang || "en", lang = docLang.startsWith("zh") ? "zh" : "en";
  const T = TXT[lang];

  let data;
  try {
    const r = await fetch(fig.dataset.src);
    if (!r.ok) throw new Error(`hero: HTTP ${r.status}`);
    data = validate(await r.json());
  } catch (e) {
    console.warn(e);        // keep the PNG; controls and live captions stay hidden (no is-live)
    return;
  }

  const last = data.pd.length - 1;
  const fm = new Intl.DateTimeFormat(docLang, { month: "short", year: "numeric", timeZone: "UTC" });
  const labels = data.months.map((s) => fm.format(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, 1)));
  const nf = new Intl.NumberFormat(docLang, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const tpl = live.dataset[lang] || live.dataset.en || "";
  resolved.textContent = resolved.dataset[lang] || resolved.dataset.en || "";
  range.max = String(last);
  // Fixed scale for the whole series: the longest spoke or semi-axis of any month fits the panel.
  const ext = Math.max(1, ...data.pd.map((p, i) => { const m = encode(data.share[i], p); return Math.max(m[0], 1 / m[1]); }));
  const pdLo = Math.min(...data.pd), pdHi = Math.max(...data.pd);

  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const checked = radios.find((b) => b.getAttribute("aria-checked") === "true");
  const S = {
    t: reduce ? last : 0, playing: false, userPaused: reduce, mode: checked ? checked.dataset.mode : "char",
    modeMix: 1, idleSince: -Infinity, holdSince: null, onscreen: true, visible: !document.hidden,
    dead: false, prev: null, raf: 0, shown: -1, res: null, timer: 0, w: 0, dpr: 1, strip: null,
  };
  S.modeMix = S.mode === "char" ? 1 : 0;

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
    if (p !== S.playing) { S.playing = p; S.holdSince = null; }
    playBtn.textContent = S.userPaused ? T.play : T.pause;
    kick();
  }
  function touch() {                  // an interaction: .live for IDLE ms, then .resolved
    S.idleSince = performance.now();
    clearTimeout(S.timer);
    S.timer = setTimeout(kick, IDLE + 20);
  }
  function seek(i) {
    S.t = clamp(Math.round(i), 0, last);
    S.userPaused = true;
    touch(); sync();
  }
  function setMode(mode, focus) {
    S.mode = mode;
    for (const b of radios) {
      const on = b.dataset.mode === mode;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
      if (on && focus) b.focus();
    }
    kick();
  }

  function frame(now) {
    const dt = S.prev == null ? 0 : Math.min(now - S.prev, 100);
    S.prev = now;
    if (S.playing) {
      if (S.t >= last) {
        if (S.holdSince == null) S.holdSince = now;
        else if (now - S.holdSince >= HOLD) { S.t = 0; S.holdSince = null; }
      } else S.t = Math.min(last, S.t + (RATE * dt) / 1000);
    }
    const target = S.mode === "char" ? 1 : 0;
    if (reduce) S.modeMix = target;
    else if (S.modeMix !== target) {
      const step = dt / MODE_MS;
      S.modeMix = target > S.modeMix ? Math.min(target, S.modeMix + step) : Math.max(target, S.modeMix - step);
    }
    const drawn = draw();
    text(now);
    if (S.playing || S.modeMix !== target) S.raf = requestAnimationFrame(tick);
    else S.prev = null;
    if (drawn && !fig.classList.contains("is-live")) fig.classList.add("is-live");
  }

  function draw() {
    const w = S.w;
    if (!w) return false;
    ctx.setTransform(S.dpr, 0, 0, S.dpr, 0, 0);
    ctx.clearRect(0, 0, w, H);
    const cx = w / 2, cy = RULER_H / 2;
    const R = Math.min(cy - PAD, cx - PAD) / (ext * 1.04);        // px per coefficient unit
    const m = mix([1, 1], metricFor(data, S.t), ease(S.modeMix)); // plain ruler at modeMix 0
    // Plain ruler: dashed unit circle.
    ctx.lineWidth = 1; ctx.strokeStyle = CIRCLE; ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, 2 * Math.PI); ctx.stroke(); ctx.setLineDash([]);
    // 24 spokes: measured length of one coefficient unit; the two axes (±e_1, ±e_2) in ink, as in the PNG.
    const spoke = (k) => {
      const phi = (2 * Math.PI * k) / SPOKES, L = spokeLen(m, phi) * R;
      ctx.moveTo(cx, cy); ctx.lineTo(cx + L * Math.cos(phi), cy - L * Math.sin(phi));
    };
    ctx.strokeStyle = SPOKE; ctx.beginPath();
    for (let k = 0; k < SPOKES; k++) if (k % (SPOKES / 4)) spoke(k);
    ctx.stroke();
    ctx.strokeStyle = INK; ctx.lineWidth = 1.5; ctx.beginPath();
    for (let k = 0; k < SPOKES; k += SPOKES / 4) spoke(k);
    ctx.stroke();
    // Characteristic ruler: unit ball of M, semi-axes 1/lam1 (horizontal) and 1/lam2.
    ctx.lineWidth = 1.75; ctx.beginPath();
    ctx.ellipse(cx, cy, R / m[0], R / m[1], 0, 0, 2 * Math.PI); ctx.stroke();
    // Strip: NBER bands, participation-dimension hairline, cursor.
    const x0 = PAD, sw = w - 2 * PAD, xOf = (i) => x0 + (sw * i) / last;
    if (!S.strip) {
      const p = new Path2D(), yOf = (v) => RULER_H + STRIP_H - 6 - ((v - pdLo) / (pdHi - pdLo || 1)) * (STRIP_H - 12);
      data.pd.forEach((v, i) => (i ? p.lineTo(xOf(i), yOf(v)) : p.moveTo(xOf(i), yOf(v))));
      S.strip = p;
    }
    ctx.fillStyle = BAND;
    for (const [a, b] of data.nber) ctx.fillRect(xOf(a), RULER_H, Math.max(1, xOf(b) - xOf(a)), STRIP_H);
    ctx.lineWidth = 1; ctx.strokeStyle = RULE;
    ctx.beginPath(); ctx.moveTo(0, RULER_H + 0.5); ctx.lineTo(w, RULER_H + 0.5); ctx.stroke();
    ctx.strokeStyle = PD_LINE; ctx.stroke(S.strip);
    const x = Math.round(xOf(S.t)) + 0.5;
    ctx.strokeStyle = INK; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x, RULER_H); ctx.lineTo(x, H); ctx.stroke();
    return true;
  }

  function text(now) {
    const i = clamp(Math.round(S.t), 0, last);
    if (i !== S.shown) {
      S.shown = i;
      dateEl.textContent = labels[i];
      range.value = String(i);
      range.setAttribute("aria-valuetext", labels[i]);
      live.textContent = fill(tpl, {
        month: labels[i], pd: nf.format(data.pd[i]), share: nf.format(data.share[i] * 100),
        nber: inRecession(data.nber, i) ? T.nber : "",
      });
    }
    const res = i >= last || (!S.playing && now - S.idleSince >= IDLE);
    if (res !== S.res) {
      S.res = res;
      fig.classList.toggle("hero-resolved", res);
      live.setAttribute("aria-hidden", String(res));
      resolved.setAttribute("aria-hidden", String(!res));
    }
  }

  // ---- Controls ---------------------------------------------------------------------------
  range.addEventListener("input", () => seek(+range.value));
  playBtn.addEventListener("click", () => {
    S.userPaused = !S.userPaused;
    if (!S.userPaused && S.t >= last) S.t = 0;
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
      seek(Math.round(S.t) + (e.shiftKey ? 12 : 1) * (e.key === "ArrowLeft" ? -1 : 1));
    }
  });
  // Strip scrubbing: pointer in the bottom 48 px.
  let dragging = false;
  const scrub = (e) => {
    const r = canvas.getBoundingClientRect();
    seek(((e.clientX - r.left - PAD) / Math.max(1, r.width - 2 * PAD)) * last);
  };
  canvas.addEventListener("pointerdown", (e) => {
    if (e.clientY - canvas.getBoundingClientRect().top < RULER_H) return;
    dragging = true;
    canvas.setPointerCapture(e.pointerId);
    scrub(e);
  });
  canvas.addEventListener("pointermove", (e) => { if (dragging) scrub(e); });
  const stop = () => { dragging = false; };
  canvas.addEventListener("pointerup", stop);
  canvas.addEventListener("pointercancel", stop);

  // ---- Observers --------------------------------------------------------------------------
  new ResizeObserver(() => {
    S.w = canvas.clientWidth;
    S.dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(S.w * S.dpr);
    canvas.height = Math.round(H * S.dpr);
    S.strip = null;
    kick();
  }).observe(canvas);
  new IntersectionObserver(([en]) => { S.onscreen = en.isIntersecting; sync(); }, { threshold: 0.1 }).observe(fig);
  document.addEventListener("visibilitychange", () => { S.visible = !document.hidden; sync(); });
  sync();
}

if (typeof document !== "undefined") {
  const fig = document.getElementById("hero");
  if (fig && fig.dataset.src) init(fig).catch((e) => { fig.classList.remove("is-live"); console.warn(e); });
}
