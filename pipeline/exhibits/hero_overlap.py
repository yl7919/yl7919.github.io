"""Hero exhibit — signed overlap among eight related characteristics under the rolling characteristic ruler.
Source: the author's dynamic-geometry tables (optional root `dynamic_geometry`).

Data behind the home-page Figure 1 (`site/assets/js/hero_overlap.js`) and its static PNG fallback:
for each of 510 twenty-year windows (ends 1983-06..2025-11) the 8×8 block of the characteristic
ruler for eight characteristics that tend to pick out the same firms, rescaled to unit diagonals
(approximately correlations, 2 dp), the average size of the 28 overlaps with the sign ignored,
and three diagnostics of the full 153×153 window matrix (participation dimension, condition
number, dim90). No recession data enter this exhibit.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

from common import provenance

ROOT = "dynamic_geometry"
F_METRICS = "tables/T_DYNAMIC_GEOMETRY_METRICS.csv"
F_PAIRS = "tables/T_DYNAMIC_GEOMETRY_PAIR_CORRELATIONS.csv"
F_VARMAP = "tables/T_DYNAMIC_GEOMETRY_VARIABLE_MAP.csv"
SOURCE_NAME = "Author's dynamic-geometry tables (JKP153, 20-year windows; 2026-06-12)"
EXPECTED_N, FIRST, LAST, WINDOW = 510, "1983-06", "2025-11", 240
LIBRARY, N_CHARACTERISTICS = "JKP153", 153
PNG_INDEX = 309                                   # 2009-03
AXES = {"avg_abs": (0.20, 0.35), "pd": (20.0, 24.0)}   # fixed display axes of the timeline (F6)
VAR_IDS = ["size", "illiq", "turnover", "ivol", "distress", "leverage", "profit", "age"]
EN = ["Small size", "Illiquidity", "Low turnover", "Idiosyncratic volatility",
      "Distress", "Leverage", "Low profitability", "Young firms"]
ZH = {"Small size": "小市值", "Illiquidity": "低流动性", "Low turnover": "低换手率", "Idiosyncratic volatility": "特质波动率",
      "Distress": "财务困境", "Leverage": "杠杆", "Low profitability": "低盈利", "Young firms": "年轻公司"}
# Neutral trait wording (each characteristic is signed so that the named trait scores high).
SIGN_EN = {"Small size": "smaller firms score higher",
           "Illiquidity": "higher Amihud illiquidity scores higher",
           "Low turnover": "lower turnover scores higher",
           "Idiosyncratic volatility": "higher idiosyncratic volatility scores higher",
           "Distress": "higher Ohlson O-score scores higher",
           "Leverage": "higher debt to market equity scores higher",
           "Low profitability": "lower operating profitability scores higher",
           "Young firms": "younger firms score higher"}
SIGN_ZH = {"Small size": "市值越小得分越高",
           "Illiquidity": "Amihud 非流动性越高得分越高",
           "Low turnover": "换手率越低得分越高",
           "Idiosyncratic volatility": "特质波动率越高得分越高",
           "Distress": "Ohlson O 值越高得分越高",
           "Leverage": "债务与市值之比越高得分越高",
           "Low profitability": "经营盈利越低得分越高",
           "Young firms": "公司越年轻得分越高"}
VAR_KEYS = ("id", "source", "sign", "en", "zh", "sign_en", "sign_zh")   # the only fields copied into the JSON
PAIRS = [[i, j] for i in range(8) for j in range(i + 1, 8)]           # upper-triangular order, as in the pairs CSV

PNG_W, PNG_H, PNG_DPI = 1600, 620, 100            # same box as hero_geometry.png so the <img width/height> stay
HEAT_AXES = (0.17, 0.05, 0.30, 0.80)              # figure-fraction box of the 8×8 cells (row labels sit to its left, from x = 0.01)
STRIP_AXES = (0.565, 0.12, 0.355, 0.54)           # timeline strip inside the right box 0.50–0.99

# Palette: the page's tokens. Positive cells tint with the site ink, negative cells with the second hue
# (hero heatmap negatives only); text stays rgba(0,0,0,.8) as on the page.
C_INK = "#111111"
C_TEXT = (0.2, 0.2, 0.2)
C_MUTED = "#6f6a60"
C_RULE = "#b9b3a6"
RGB_POS = (24, 89, 139)                           # hsl(206, 70%, 32%), the site's $ink
RGB_NEG = (166, 95, 48)                           # hsl(24, 55%, 42%), --hero-neg
RGB_DIAG = (204, 204, 204)                        # rgba(0,0,0,.2) over white, --rule


def _round2(x: float) -> float:
    """2 dp; `-0.0` is normalised to `0.0` so the JSON text never contains "-0.0"."""
    v = round(float(x), 2)
    return 0.0 if v == 0 else v


def _months_between(a: int, b: int) -> int:
    """Months from yyyymm `a` to yyyymm `b`."""
    return (b // 100 - a // 100) * 12 + (b % 100 - a % 100)


def tint_rgb(v: float) -> tuple[int, int, int]:
    """Cell colour composited over white: rgba(hue, 0.08 + 0.50·|v|), ink for v ≥ 0, warm for v < 0."""
    base = RGB_POS if v >= 0 else RGB_NEG
    a = 0.08 + 0.50 * min(1.0, abs(float(v)))
    return tuple(int(round(255 * (1 - a) + c * a)) for c in base)


def _read_varmap(p: Path) -> list[dict]:
    vm = pd.read_csv(p)
    used = vm[vm["used_in_fragility_score"].astype(bool)]        # internal column name; never copied out
    if len(used) != 8:
        raise ValueError(f"{p.name}: expected 8 used rows, found {len(used)}")
    labels = used["display_label"].astype(str).tolist()
    if labels != EN:
        raise ValueError(f"{p.name}: display labels {labels} differ from the expected order {EN}")
    out = []
    for vid, (_, r) in zip(VAR_IDS, used.iterrows()):
        sign = float(r["sign_multiplier"])
        if sign not in (-1.0, 1.0):
            raise ValueError(f"{p.name}: sign_multiplier {sign!r} for {r['display_label']}")
        lab = str(r["display_label"])
        out.append({"id": vid, "source": str(r["exact_variable_name"]), "sign": int(sign),
                    "en": lab, "zh": ZH[lab], "sign_en": SIGN_EN[lab], "sign_zh": SIGN_ZH[lab]})
    return out


def _read_metrics(p: Path) -> pd.DataFrame:
    m = pd.read_csv(p)
    if len(m) != EXPECTED_N:
        raise ValueError(f"{p.name}: expected {EXPECTED_N} rows, found {len(m)}")
    labels = m["date_label"].astype(str).tolist()
    if labels[0] != FIRST or labels[-1] != LAST:
        raise ValueError(f"{p.name}: window ends run {labels[0]}..{labels[-1]}, expected {FIRST}..{LAST}")
    dates = m["date"].astype(int).to_numpy()
    if not all(_months_between(int(dates[i]), int(dates[i + 1])) == 1 for i in range(len(dates) - 1)):
        raise ValueError(f"{p.name}: date is not strictly increasing by one month")
    span = [_months_between(int(a), int(b)) for a, b in zip(m["window_start"], m["window_end"])]
    if any(s != WINDOW - 1 for s in span):
        raise ValueError(f"{p.name}: window_end - window_start must be {WINDOW - 1} months everywhere")
    for col in ("avg_abs_correlation", "condition_number", "participation_rank", "dim90"):
        if not np.isfinite(m[col].to_numpy(float)).all():
            raise ValueError(f"{p.name}: non-finite values in {col}")
    return m


def _read_pairs(p: Path, dates: np.ndarray) -> np.ndarray:
    long = pd.read_csv(p)
    wide = long.pivot(index="date", columns="pair", values="correlation")
    expected = [f"{EN[i]} | {EN[j]}" for i, j in PAIRS]
    missing = [c for c in expected if c not in wide.columns]
    if missing or len(wide.columns) != 28:
        raise ValueError(f"{p.name}: pair columns differ from the 28 upper-triangular pairs (missing {missing})")
    wide = wide.reindex(index=dates, columns=expected)
    if wide.isna().any().any():
        raise ValueError(f"{p.name}: missing pair correlations after the pivot")
    return wide.to_numpy(float)


def build(sources) -> dict:
    p_metrics = sources.path(ROOT, F_METRICS)
    p_pairs = sources.path(ROOT, F_PAIRS)
    p_varmap = sources.path(ROOT, F_VARMAP)

    variables = _read_varmap(p_varmap)
    m = _read_metrics(p_metrics)
    months = m["date_label"].astype(str).tolist()
    C = _read_pairs(p_pairs, m["date"].astype(int).to_numpy())          # 510 × 28, unrounded

    corr = [[_round2(v) for v in row] for row in C]
    avg_abs = [round(float(x), 3) for x in m["avg_abs_correlation"]]
    pd_ = [round(float(x), 2) for x in m["participation_rank"]]
    cond = [int(round(float(x))) for x in m["condition_number"]]
    dim90 = [int(x) for x in m["dim90"]]

    # The caption names small size and illiquidity as the largest overlap in every window: assert it
    # from the unrounded data, from the rounded rows the JS sees, and from the metrics file's own column.
    top_u = np.abs(C).argmax(axis=1)
    top_r = np.abs(np.asarray(corr)).argmax(axis=1)
    if not (top_u == top_r).all():
        raise ValueError("rounding to 2 dp changes the largest-overlap pair in some window")
    top_idx = int(top_u[0])
    if not (top_u == top_idx).all():
        raise ValueError("the largest-overlap pair is not the same in every window; revisit the caption")
    csv_pairs = m["max_abs_pair"].astype(str).tolist()
    if any(s != f"{EN[PAIRS[top_idx][0]]} | {EN[PAIRS[top_idx][1]]}" for s in csv_pairs):
        raise ValueError("metrics max_abs_pair disagrees with the argmax of the pair matrix")
    if not np.allclose(np.abs(C).mean(axis=1), m["avg_abs_correlation"].to_numpy(float), atol=1e-9):
        raise ValueError("avg_abs_correlation is not the mean of |cell| over the 28 pairs")

    ranges = {"avg_abs": [min(avg_abs), max(avg_abs)], "pd": [min(pd_), max(pd_)],
              "cond": [min(cond), max(cond)], "dim90": [min(dim90), max(dim90)],
              "top_abs": [min(r[top_idx] for r in corr), max(r[top_idx] for r in corr)]}
    for key in ("avg_abs", "pd"):
        lo, hi = AXES[key]
        if not (lo <= ranges[key][0] and ranges[key][1] <= hi):
            raise ValueError(f"{key} range {ranges[key]} leaves the fixed axis {AXES[key]}")
    medians = {"avg_abs": round(float(np.median(avg_abs)), 3), "pd": round(float(np.median(pd_)), 2)}

    meta = {**provenance([p_metrics, p_pairs, p_varmap], SOURCE_NAME),
            "library": LIBRARY, "n_characteristics": N_CHARACTERISTICS, "window_months": WINDOW,
            "n_windows": len(months), "first": months[0], "last": months[-1],
            "ranges": ranges, "axes": {k: [float(a), float(b)] for k, (a, b) in AXES.items()},
            "medians": medians, "top_vars": list(PAIRS[top_idx]), "top_pair_index": top_idx,
            "png_index": PNG_INDEX}
    return {"meta": meta, "months": months, "vars": variables, "pairs": PAIRS,
            "corr": corr, "avg_abs": avg_abs, "pd": pd_, "cond": cond, "dim90": dim90}


def _cell_matrix(payload: dict, t: int) -> np.ndarray:
    """Full 8×8 signed matrix at window t from the 28 pair values (unit diagonal)."""
    M = np.eye(8)
    for k, (i, j) in enumerate(payload["pairs"]):
        M[i, j] = M[j, i] = payload["corr"][t][k]
    return M


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback: the 8×8 table at PNG_INDEX, the readout for that window and the timeline strip."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.text

    t = PNG_INDEX
    months = payload["months"]
    variables = payload["vars"]
    M = _cell_matrix(payload, t)
    top = payload["meta"]["top_vars"]
    top_k = payload["meta"]["top_pair_index"]

    fig = plt.figure(figsize=(PNG_W / PNG_DPI, PNG_H / PNG_DPI), dpi=PNG_DPI)
    fig.patch.set_facecolor("white")

    # Left: the heatmap (real numbers at 2 dp, the page's tints composited over white).
    rgb = np.zeros((8, 8, 3))
    for i in range(8):
        for j in range(8):
            rgb[i, j] = np.array(RGB_DIAG if i == j else tint_rgb(M[i, j])) / 255.0
    ax = fig.add_axes(HEAT_AXES)
    ax.imshow(rgb, interpolation="nearest", aspect="equal")
    for i in range(8):
        for j in range(8):
            txt = "1.00" if i == j else f"{M[i, j]:.2f}".replace("-", "−")
            ax.text(j, i, txt, ha="center", va="center", fontsize=12,
                    color=C_MUTED if i == j else C_TEXT)
    ax.set_xticks(range(8))
    ax.set_xticklabels([str(k + 1) for k in range(8)], fontsize=12, color=C_MUTED)
    ax.xaxis.tick_top()
    ax.set_yticks(range(8))
    ax.set_yticklabels([f"{k + 1} {v['en']}" for k, v in enumerate(variables)], fontsize=12, color=C_TEXT)
    ax.tick_params(length=0, pad=6)
    for side in ax.spines.values():
        side.set_visible(False)
    fig.text(0.01, 0.935, f"Signed overlap among eight characteristics, window ending {_long_month(months[t])}",
             fontsize=13.5, color=C_INK)

    # Right: the readout for PNG_INDEX (from the payload, never literals) and the timeline strip. The figure
    # title, the cursor note and the source line are in the always-visible figcaption, so the image leaves them
    # out and spends the room on legible type (the PNG is shown at about half its width, and in print).
    a, b = variables[top[0]]["en"].lower(), variables[top[1]]["en"].lower()
    fig.text(0.50, 0.90, f"Average overlap size {payload['avg_abs'][t]:.2f}, sign ignored", fontsize=15, color=C_INK)
    fig.text(0.50, 0.83, f"· largest overlap: {a} and {b}, {payload['corr'][t][top_k]:.2f}", fontsize=15, color=C_INK)
    fig.text(0.50, 0.76, f"· participation dimension of all {payload['meta']['n_characteristics']} characteristics "
             f"{payload['pd'][t]:.1f}", fontsize=15, color=C_INK)

    sx = fig.add_axes(STRIP_AXES)
    x = np.arange(len(months))
    lo, hi = payload["meta"]["axes"]["avg_abs"]
    sx.plot(x, payload["avg_abs"], color=f"#{RGB_POS[0]:02x}{RGB_POS[1]:02x}{RGB_POS[2]:02x}", lw=1.4)
    sx.axvline(t, color=C_INK, lw=1.4)
    sx.plot([t], [payload["avg_abs"][t]], "o", ms=4, color=C_INK)
    sx.set_xlim(0, len(x) - 1)
    sx.set_ylim(lo, hi)
    ticks = [i for i, mm in enumerate(months) if mm.endswith("-01") and int(mm[:4]) % 10 == 0]
    sx.set_xticks(ticks)
    sx.set_xticklabels([months[i][:4] for i in ticks], fontsize=13, color=C_MUTED)
    sx.set_yticks([lo, hi])
    sx.set_yticklabels([f"{lo:.2f}", f"{hi:.2f}"], fontsize=13, color=C_MUTED)
    sx.tick_params(length=0)
    for side in ("top", "right", "left"):
        sx.spines[side].set_visible(False)
    sx.spines["bottom"].set_color(C_RULE)
    sx.set_ylabel("average overlap size\n(eight characteristics, sign ignored)", fontsize=11.5, color=C_MUTED)

    px = sx.twinx()
    plo, phi = payload["meta"]["axes"]["pd"]
    px.plot(x, payload["pd"], color=(0, 0, 0, 0.45), lw=1.0)
    px.plot([t], [payload["pd"][t]], "o", ms=4, color=(0, 0, 0, 0.6))
    px.set_ylim(plo, phi)
    px.set_yticks([plo, phi])
    px.set_yticklabels([f"{plo:.0f}", f"{phi:.0f}"], fontsize=13, color=C_MUTED)
    px.tick_params(length=0)
    for side in ("top", "right", "left"):
        px.spines[side].set_visible(False)
    px.set_ylabel("participation dimension\n(153 characteristics)", fontsize=11.5, color=C_MUTED, rotation=270, labelpad=30)

    # Every text must lie inside the canvas (a clipped footer shipped once on the old hero; never again).
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for txt in fig.findobj(matplotlib.text.Text):
        if not txt.get_text():
            continue
        bb = txt.get_window_extent(renderer)
        if bb.x0 < 0 or bb.y0 < 0 or bb.x1 > PNG_W or bb.y1 > PNG_H:
            raise ValueError(f"hero_overlap.png: text runs outside the canvas: {txt.get_text()!r} {bb}")

    out_png.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=PNG_DPI, facecolor="white")
    plt.close(fig)
    # Few hues on white: an 8-bit palette is visually lossless and keeps the file under budget.
    from PIL import Image  # Pillow ships with matplotlib
    buf.seek(0)
    with Image.open(buf) as im:
        im.convert("RGB").quantize(colors=256).save(out_png, format="PNG", optimize=True)


def _long_month(ym: str) -> str:
    names = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
    return f"{names[int(ym[5:7]) - 1]} {ym[:4]}"
