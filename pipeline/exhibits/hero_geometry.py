"""Hero exhibit — rolling characteristic geometry (Characteristic Geometry release).

Data behind the home-page "characteristic ruler" animation (`site/assets/js/hero.js`)
and its static PNG fallback. Only two monthly statistics are encoded in the ruler:
the top-eigenvalue share (concentration, `share`) and the participation dimension
(effective breadth, `pd`). `drift`, `cond` and `trace` are carried for the research
page's rolling-geometry figure.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
import pandas as pd

from common import provenance
from exhibits.portfolio_formation import EXPECTED_MONTHS, RELEASE_NAME, _check_months

F_GEOMETRY = "02_Presentation/Source/data/rolling_geometry.csv"
F_NBER = "03_Replication/modules/business_cycles/nber_monthly.csv"

# Encoding constants (spec "Hero animation — Encoding"); the JSON ranges must equal these.
SHARE_RANGE = (0.1176, 0.1521)
PD_RANGE = (17.36, 22.63)
RATIO_MIN, RATIO_SPAN = 1.4, 2.6      # lam1/lam2 in [1.4, 4.0]
SIZE_MIN, SIZE_SPAN = 0.85, 0.30      # in [0.85, 1.15]
N_SPOKES = 24
STRIP_INDEX = 429                     # 2009-03: trough of the 2007-12..2009-06 recession band

PNG_W, PNG_H, PNG_DPI = 1600, 620, 100

# Palette from the spec's hero.js frame description.
C_INK = "#111111"
C_CIRCLE = "#b9b3a6"
C_ELLIPSE = "#18557f"
C_SPOKE = (0, 0, 0, 0.35)
C_BAND = (0, 0, 0, 0.06)
C_PD = (0, 0, 0, 0.5)
C_MUTED = "#6f6a60"


def _round(xs: np.ndarray, dp: int) -> list[float]:
    out = [round(float(x), dp) for x in xs]
    if dp == 0:
        return [float(int(x)) for x in out]
    return out


def _nber_pairs(p_nber: Path, months: list[str]) -> list[list[int]]:
    idx = {m: i for i, m in enumerate(months)}
    pairs = []
    for r in pd.read_csv(p_nber).itertuples():
        if r.peak_month not in idx or r.trough_month not in idx:
            raise ValueError(f"{p_nber.name}: recession {r.peak_month}..{r.trough_month} outside the month axis")
        a, b = idx[r.peak_month], idx[r.trough_month]
        if not a < b:
            raise ValueError(f"{p_nber.name}: peak {r.peak_month} not before trough {r.trough_month}")
        pairs.append([a, b])
    return pairs


def build(sources) -> dict:
    p_geo, p_nber = sources.geo(F_GEOMETRY), sources.geo(F_NBER)
    g = pd.read_csv(p_geo)
    months = g["date"].astype(str).tolist()
    _check_months(months, p_geo.name)

    pd_ = g["participation_dimension"].to_numpy(float)
    share = g["top_eigenvalue_share"].to_numpy(float)
    drift = g["spectral_drift"].to_numpy(float)
    cond = g["condition_number"].to_numpy(float)
    trace = g["trace"].to_numpy(float)

    if not (np.isnan(drift[0]) and np.isfinite(drift[1:]).all()):
        raise ValueError(f"{p_geo.name}: spectral_drift must be empty in the first row and finite afterwards")
    drift = drift.copy()
    drift[0] = 0.0
    for name, xs in (("participation_dimension", pd_), ("top_eigenvalue_share", share),
                     ("condition_number", cond), ("trace", trace)):
        if not np.isfinite(xs).all():
            raise ValueError(f"{p_geo.name}: non-finite values in {name}")

    ranges = {"pd": [round(float(pd_.min()), 2), round(float(pd_.max()), 2)],
              "share": [round(float(share.min()), 4), round(float(share.max()), 4)]}
    medians = {"pd": round(float(np.median(pd_)), 2), "share": round(float(np.median(share)), 4)}

    return {
        "meta": {**provenance([p_geo, p_nber], RELEASE_NAME), "ranges": ranges, "medians": medians},
        "months": months,
        "pd": _round(pd_, 2),
        "share": _round(share, 4),
        "drift": _round(drift, 5),
        "cond": _round(cond, 0),
        "trace": _round(trace, 1),
        "nber": _nber_pairs(p_nber, months),
    }


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def metric(pd_t: float, share_t: float, ranges: dict) -> tuple[float, float]:
    """Return (lam1, lam2) for one month per the spec encoding."""
    s0, s1 = ranges["share"]
    p0, p1 = ranges["pd"]
    u = _clamp01((share_t - s0) / (s1 - s0))
    v = _clamp01((pd_t - p0) / (p1 - p0))
    ratio = RATIO_MIN + RATIO_SPAN * u
    size = SIZE_MIN + SIZE_SPAN * v
    return size * math.sqrt(ratio), size / math.sqrt(ratio)


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback: characteristic ruler at STRIP_INDEX plus the participation-dimension strip."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Ellipse

    t = STRIP_INDEX
    month = payload["months"][t]
    lam1, lam2 = metric(payload["pd"][t], payload["share"][t], payload["meta"]["ranges"])

    fig = plt.figure(figsize=(PNG_W / PNG_DPI, PNG_H / PNG_DPI), dpi=PNG_DPI)
    fig.patch.set_facecolor("white")

    # Ruler panel (left): unit circle (identity ruler), unit ball of M(t), 24 spokes.
    ax = fig.add_axes([0.03, 0.10, 0.30, 0.86])
    ax.set_aspect("equal")
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.35, 1.35)
    ax.axis("off")
    for k in range(N_SPOKES):
        phi = 2 * math.pi * k / N_SPOKES
        length = math.sqrt(lam1 ** 2 * math.cos(phi) ** 2 + lam2 ** 2 * math.sin(phi) ** 2)
        axis_spoke = k % (N_SPOKES // 4) == 0
        ax.plot([0, length * math.cos(phi)], [0, length * math.sin(phi)],
                color=C_INK if axis_spoke else C_SPOKE, lw=1.6 if axis_spoke else 1.0, solid_capstyle="round")
    ax.add_patch(Ellipse((0, 0), 2.0, 2.0, fill=False, ls=(0, (4, 4)), lw=1.2, ec=C_CIRCLE))
    ax.add_patch(Ellipse((0, 0), 2.0 / lam1, 2.0 / lam2, fill=False, lw=2.2, ec=C_ELLIPSE))
    ax.text(0, -1.27, f"Characteristic ruler, {month}", ha="center", va="center", fontsize=11, color=C_INK)

    # Text block (right of the ruler): the two encoded statistics.
    fig.text(0.36, 0.86, "How much of the characteristic space is really in play", fontsize=18, color=C_INK, weight="medium")
    fig.text(0.36, 0.77,
             f"Top-eigenvalue share {payload['share'][t]:.4f}  (concentration; range "
             f"{payload['meta']['ranges']['share'][0]:.4f}–{payload['meta']['ranges']['share'][1]:.4f})",
             fontsize=12, color=C_INK)
    fig.text(0.36, 0.71,
             f"Participation dimension {payload['pd'][t]:.2f}  (effective breadth; range "
             f"{payload['meta']['ranges']['pd'][0]:.2f}–{payload['meta']['ranges']['pd'][1]:.2f})",
             fontsize=12, color=C_INK)
    fig.text(0.36, 0.65, "Dashed circle: identity ruler. Solid ellipse: unit ball of the characteristic metric; "
             "spokes measure unit coefficients.", fontsize=10.5, color=C_MUTED)

    # Strip: participation dimension over 1973-06..2024-11 with NBER bands and the cursor at t.
    sx = fig.add_axes([0.36, 0.14, 0.61, 0.40])
    x = np.arange(len(payload["months"]))
    for a, b in payload["nber"]:
        sx.axvspan(a, b, color=C_BAND, lw=0)
    sx.plot(x, payload["pd"], color=C_PD, lw=1.0)
    sx.axvline(t, color=C_INK, lw=1.4)
    sx.set_xlim(0, len(x) - 1)
    lo, hi = payload["meta"]["ranges"]["pd"]
    sx.set_ylim(lo - 0.3, hi + 0.3)
    ticks = [i for i, m in enumerate(payload["months"]) if m.endswith("-01") and int(m[:4]) % 10 == 0]
    sx.set_xticks(ticks)
    sx.set_xticklabels([payload["months"][i][:4] for i in ticks], fontsize=10, color=C_MUTED)
    sx.set_yticks([lo, hi])
    sx.set_yticklabels([f"{lo:.1f}", f"{hi:.1f}"], fontsize=10, color=C_MUTED)
    sx.tick_params(length=0)
    for side in ("top", "right", "left"):
        sx.spines[side].set_visible(False)
    sx.spines["bottom"].set_color(C_CIRCLE)
    sx.set_ylabel("Participation dimension", fontsize=10, color=C_MUTED)

    fig.text(0.36, 0.04, "Rolling characteristic-covariance spectrum, 132 characteristics, formation dates 1973-06 to 2024-11. "
             "NBER recessions shaded. Source: Characteristic Geometry research release (2026-09-09).", fontsize=9, color=C_MUTED)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=PNG_DPI, facecolor="white")
    plt.close(fig)
    # Few hues on white: an 8-bit palette is visually lossless and keeps the file under budget.
    from PIL import Image  # Pillow ships with matplotlib
    buf.seek(0)
    with Image.open(buf) as im:
        im.convert("RGB").quantize(colors=256).save(out_png, format="PNG", optimize=True)
