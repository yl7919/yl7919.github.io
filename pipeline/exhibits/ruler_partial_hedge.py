"""The Ruler Matters: how much of the loading to remove? Partial loading hedges at 0, 50 and 100%.

Source: the paper's tables/partial_hedging.csv (Table VII, p. 46; Figure 9, p. 45; Section IX.A, pp. 43-44)
and tables/partial_intervals.csv (Table IA.48, p. 118). Unrestricted characteristic intercept, 153
characteristics. Under unit gross the hedge keeps less of the original tilt and lowers subsequent risk;
restoring the original positive tilt instead raises gross holdings. The paper's Figure 9 also plots 25%
and 75%; those two policies are not in the paper's data tables, so the exhibit carries the three
CSV-backed stops only.
"""
from __future__ import annotations

from pathlib import Path

from common import provenance
from exhibits._paper_data import fixed, num, one, read_rows, save_png
from sources import Sources

ROOT = "ruler_matters"
F_PARTIAL = "tables/partial_hedging.csv"
F_INTERVALS = "tables/partial_intervals.csv"
RELEASE = "The Ruler Matters: Factor Exposures, Attribution, and Portfolio Risk (October 2026), paper tables"
FRACTIONS = [0, 50, 100]

TARGETS = [
    ("bm", "Book-to-market", "Book-to-market", "账面市值比"),
    ("mom", "Momentum", "Momentum", "动量"),
    ("size", "Firm size", "Larger-firm size", "市值（大公司方向）"),
]
# JSON key, CSV column, printed decimals (Table VII)
COLS = [
    ("exposure_retained_pct", "Exposure (\\%)", 2),
    ("vol_bp", "Vol. (bp)", 2),
    ("turnover_pct", "Turnover (\\%)", 2),
    ("matched_gross", "Matched gross", 2),
    ("matched_vol_bp", "Matched vol.", 2),
]
LOCATORS = {
    "table": "Table VII, p. 46",
    "figure": "Figure 9, p. 45",
    "text": "Section IX.A, pp. 43-44",
    "full_hedge_change": "Table IA.48, p. 118",
}
NOTES = {
    "fixed_policies": "The fractions are fixed policies, not an optimised frontier; no fraction is selected using evaluation returns (Figure 9 note, p. 45).",
    "two_costs": "Two possible costs of hedging: under unit gross, less of the original tilt may remain; at the fixed original tilt, gross holdings may have to increase (p. 46).",
    "turnover": "Turnover refers to the unit-gross holdings only (Table VII note, p. 46).",
    "missing_stops": "The paper's five-fraction experiment also includes 25% and 75% (Figure 9, p. 45); those two policies are not in the paper's data tables.",
    "intervals": "The full-hedge changes at the original tilt carry pointwise 95% intervals (1,999 paired twelve-month calendar-block draws); they are not members of the paper's simultaneous-inference families (Table IA.48, p. 118).",
}


def build(sources: Sources) -> dict:
    p_part = sources.path(ROOT, F_PARTIAL)
    p_int = sources.path(ROOT, F_INTERVALS)
    part = read_rows(p_part)
    ints = read_rows(p_int)
    if len(part) != len(TARGETS) * len(FRACTIONS):
        raise ValueError(f"{p_part.name}: expected {len(TARGETS) * len(FRACTIONS)} rows, found {len(part)}")

    rows = []
    for tid, tcsv, _l, _z in TARGETS:
        for f in FRACTIONS:
            r = one(part, p_part.name, Target=tcsv, **{"Hedge (\\%)": f"{float(f):.1f}"})
            vals = {key: num(r[col], f"{p_part.name}:{tcsv}/{f}/{col}") for key, col, _ in COLS}
            rows.append({"target": tid, "hedge_pct": f, **vals,
                         "printed": {key: fixed(vals[key], d) for key, _c, d in COLS}})

    full = []
    for tid, tcsv, _l, _z in TARGETS:
        r = one(ints, p_int.name, Target=tcsv)
        vals = {"change_bp": num(r["Change (bp)"], f"{p_int.name}:{tcsv}"),
                "lo": num(r["Lower"], f"{p_int.name}:{tcsv}"), "hi": num(r["Upper"], f"{p_int.name}:{tcsv}")}
        full.append({"target": tid, **vals, "printed": {k: fixed(v, 2) for k, v in vals.items()}})

    return {
        "meta": {
            **provenance([p_part, p_int], RELEASE),
            "exhibit": "Table VII (p. 46), Figure 9 (p. 45) and Table IA.48 (p. 118)",
            "model": "Unrestricted characteristic intercept, 153 characteristics, FFC6 plus three latent factors",
            "sample": {"formation_months": 225, "return_months": 216, "turnover_months": 219},
            "units": {"hedge_pct": "% of the loading-space projection removed before unit-gross normalisation",
                      "exposure_retained_pct": "signed tilt as % of the unhedged unit-gross portfolio's tilt",
                      "vol_bp": "volatility at unit gross, bp per month",
                      "turnover_pct": "one-way turnover of the unit-gross holdings, % of NAV per month",
                      "matched_gross": "gross holdings / NAV after restoring the original positive tilt",
                      "matched_vol_bp": "volatility after restoring the original positive tilt, bp per month",
                      "change_bp": "full hedge at the original tilt minus the unhedged portfolio, volatility in bp per month"},
            "locators": LOCATORS,
            "notes": NOTES,
            "missing_fractions": [25, 75],
        },
        "fractions": FRACTIONS,
        "targets": [{"id": t, "label": lab, "label_zh": zh} for t, _c, lab, zh in TARGETS],
        "rows": rows,
        "full_hedge_change": full,
    }


C_LINE, C_MATCH, C_MUTED = "#8a6a1a", "#18557f", "#6f6a60"


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback (1200 x 630): volatility against tilt retained at unit gross, three stops per target,
    with the restore-the-tilt policies as open markers at 100% retained."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(8, 4.2), sharey=True)
    for ax, t in zip(axes, payload["targets"]):
        rs = [r for r in payload["rows"] if r["target"] == t["id"]]
        xs = [r["exposure_retained_pct"] for r in rs]
        ys = [r["vol_bp"] for r in rs]
        ax.plot(xs, ys, "-o", color=C_LINE, ms=4.5, lw=1.6, label="Unit gross")
        for r in rs:
            ax.annotate(f"{r['hedge_pct']}%", (r["exposure_retained_pct"], r["vol_bp"]), textcoords="offset points",
                        xytext=(-4, -12), ha="right", fontsize=7, color=C_LINE)
        for r in rs[1:]:
            ax.plot([100], [r["matched_vol_bp"]], "o", mfc="white", mec=C_MATCH, mew=1.4, ms=5.5)
            ax.annotate(f"gross {r['printed']['matched_gross']}", (100, r["matched_vol_bp"]), textcoords="offset points",
                        xytext=(-8, 0), ha="right", va="center", fontsize=6.5, color=C_MATCH)
        ax.set_title(t["label"], fontsize=9)
        ax.set_xlim(45, 106)
        ax.set_ylim(50, 290)
        ax.set_xlabel("Original tilt retained (%)", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7.5)
    axes[0].set_ylabel("Subsequent volatility (bp per month)", fontsize=8)
    axes[0].plot([], [], "o", mfc="white", mec=C_MATCH, mew=1.4, label="Original tilt restored")
    axes[0].legend(frameon=False, fontsize=7, loc="upper left")
    fig.text(0.01, 0.012, "Labels: share of the loading projection removed (0, 50, 100%). Unrestricted intercept, 153 characteristics. "
             "Source: The Ruler Matters, Table VII (p. 46).", fontsize=6.5, color=C_MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save_png(fig, out_png)
    plt.close(fig)
