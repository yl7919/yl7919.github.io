"""JMP exhibit: cost sensitivity of a fixed allocation rule.

Source: Characteristic Libraries and Portfolio Decisions (SSRN v2, September 2026),
Figure 3 and Table IV. Data: results package r3, holdings/summary.csv (152 models x 8
scenarios). The figure shows 4 methods x 3 representations (original, theme balanced,
five copies of every value characteristic) at the exact one-way cost points 0, 10, 25,
50 and 100 bp per traded dollar. Only mean returns are published: net Sharpe ratios
at 10, 50 and 100 bp are not printed in the paper, so they are not carried. The page slider interpolates linearly between those
points and says so; no value between the points is taken from the source.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from common import provenance

RELEASE_NAME = "Characteristic Libraries and Portfolio Decisions, results package r3 (2026-09-16)"
F_SUMMARY = "holdings/summary.csv"

METHODS = [
    ("blocked_ridge", "Blocked ridge"),
    ("SR_weighted_ridge_adaptation", "SR-weighted"),
    ("author_LOO_ridge", "LOO ridge"),
    ("author_UPSA", "UPSA"),
]
REPS = [
    ("original", "Original"),
    ("theme_balanced", "Balanced"),
    ("copies5_Value", "Value copies"),
]
SCENARIOS = [("gross", 0), ("cost10", 10), ("cost25", 25), ("cost50", 50), ("cost100", 100)]
EXPECTED_MONTHS = 179

# Verbatim from the paper's Figure 3 note (SSRN v2, p. 33).
NOTE = (
    "The sample contains 179 monthly formation decisions from January 2011 through November 2025, "
    "with returns realized from February 2011 through December 2025. SR-weighted denotes the "
    "training-Sharpe-weighted ridge adaptation; LOO ridge is leave-one-out-selected ridge; UPSA is "
    "Universal Portfolio Shrinkage. Each panel varies one-way costs per traded dollar for the original "
    "representation, theme balancing and fivefold value replication. The vertical axis is annual "
    "arithmetic mean excess return in percent. Each rate has a separate self-financing cash and "
    "return-drift account; target-weight rules remain fixed. The stock gross cap is two and primary "
    "missing outcomes receive zero vendor excess return. The curves do not include optimized trade "
    "scheduling, borrow fees or market impact."
)


def build(sources) -> dict:
    p = sources.path("jmp_results", F_SUMMARY)
    df = pd.read_csv(p)
    series = []
    for mid, mlabel in METHODS:
        for rid, rlabel in REPS:
            model = f"{mid}__{rid}"
            mean, to = [], None
            for scen, _bp in SCENARIOS:
                row = df[(df["model"] == model) & (df["scenario"] == scen)]
                if len(row) != 1:
                    raise ValueError(f"{p.name}: expected one row for {model}/{scen}, found {len(row)}")
                r = row.iloc[0]
                if int(r["months"]) != EXPECTED_MONTHS:
                    raise ValueError(f"{p.name}: {model}/{scen} has {r['months']} months, expected {EXPECTED_MONTHS}")
                mean.append(round(float(r["mean_annual_percent"]), 3))
                if scen == "gross":
                    to = round(float(r["mean_full_turnover"]), 3)
            series.append({"method": mlabel, "rep": rlabel, "mean": mean, "turnover": to})
    return {
        "meta": {**provenance([p], RELEASE_NAME), "note": NOTE,
                 "exhibit": "Figure 3 and Table IV of the September 2026 working paper"},
        "bp": [bp for _s, bp in SCENARIOS],
        "methods": [m for _i, m in METHODS],
        "reps": [r for _i, r in REPS],
        "series": series,
    }


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback: 2 x 2 panels, mean annual excess return against one-way cost."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"Original": "#18557f", "Balanced": "#8a6a1a", "Value copies": "#7a7a7a"}
    styles = {"Original": "-", "Balanced": "--", "Value copies": ":"}
    fig, axes = plt.subplots(2, 2, figsize=(8, 5.6), dpi=150, sharex=True, sharey=True)
    for ax, method in zip(axes.flat, payload["methods"]):
        for s in payload["series"]:
            if s["method"] != method:
                continue
            ax.plot(payload["bp"], s["mean"], styles[s["rep"]], marker="o", ms=3, lw=1.5,
                    color=colors[s["rep"]], label=s["rep"])
        ax.axhline(0, color="#999999", lw=0.8)
        ax.set_title(method, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axes[1]:
        ax.set_xlabel("One-way cost per traded dollar (bp)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Annual mean excess return (%)")
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.text(0.01, 0.005, "Exact points at 0, 10, 25, 50, 100 bp. Source: Characteristic Libraries and "
             "Portfolio Decisions, Figure 3; holdings/summary.csv.", fontsize=7, color="#6f6a60")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)
