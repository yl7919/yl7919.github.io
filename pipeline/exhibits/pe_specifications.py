"""Interpreting Estimated Pricing Errors: the 24-specification calibration grid.

Source: the paper's Table G.1 ("Residual-calibration gains across factor counts and
training windows", tables/challenge_grid.tex in the Overleaf source) and the
automatically generated counts in challenge_numbers.tex. Each entry is residual
calibration's prediction-R^2 gain (percentage points) over a named baseline, on the
same 93 target months, April 2018 to December 2025.
"""
from __future__ import annotations

import re
from pathlib import Path

from common import provenance
from sources import Sources

RELEASE_NAME = "Interpreting Estimated Pricing Errors, working paper, 27 September 2026 (Table G.1)"
F_GRID = "tables/challenge_grid.tex"
F_COUNTS = "challenge_numbers.tex"

# Column order in Table G.1: Full, Whole, PC, Average.
BASELINES = [
    {"id": "full", "label": "Complete forecast (full retention)", "label_zh": "完整预测（全部保留）", "macro": "ChallengeFullWins"},
    {"id": "average", "label": "Equal forecast average", "label_zh": "等权预测平均", "macro": "ChallengeAverageWins"},
    {"id": "pc", "label": "Characteristic-PC calibration", "label_zh": "特征主成分校准", "macro": "ChallengePCWins"},
    {"id": "whole", "label": "Whole-forecast scaling", "label_zh": "整体预测缩放", "macro": "ChallengeWholeWins"},
]
GRID_COLS = ["full", "whole", "pc", "average"]
N_SPECS = 24
TARGET_MONTHS = 93

_NUM = r"(-?\d+\.\d+)"
_ROW = re.compile(
    r"^\s*(?P<block>(?:Expanding|Rolling 240) / \d)?\s*&\s*(?P<train>EW|VW)\s*&\s*(?P<eval>EW|VW)\s*&\s*"
    + r"\s*&\s*".join([_NUM] * 4) + r"\s*\\\\"
)


def parse_grid(text: str) -> list[dict]:
    specs, window, k = [], None, None
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        if m.group("block"):
            w, kk = m.group("block").split(" / ")
            window = "Expanding" if w == "Expanding" else "Rolling 240"
            k = int(kk)
        if window is None:
            raise ValueError("challenge_grid.tex: data row before the first window/K label")
        vals = [float(m.group(i)) for i in range(4, 8)]
        specs.append({
            "window": window, "k": k, "train": m.group("train"), "eval": m.group("eval"),
            "gains": dict(zip(GRID_COLS, vals)),
        })
    return specs


def parse_counts(text: str) -> dict[str, int]:
    return {name: int(val) for name, val in re.findall(r"\\newcommand\{\\(\w+)\}\{(\d+)\}", text)}


def build(sources: Sources) -> dict:
    f_grid = sources.path("pricing_errors", F_GRID)
    f_counts = sources.path("pricing_errors", F_COUNTS)
    specs = parse_grid(f_grid.read_text(encoding="utf-8"))
    if len(specs) != N_SPECS:
        raise ValueError(f"challenge_grid.tex: expected {N_SPECS} specifications, parsed {len(specs)}")
    counts = parse_counts(f_counts.read_text(encoding="utf-8"))
    if counts.get("ChallengeCells") != N_SPECS:
        raise ValueError("challenge_numbers.tex: ChallengeCells is not 24")
    wins = {}
    for b in BASELINES:
        n = sum(1 for s in specs if s["gains"][b["id"]] > 0)
        if counts.get(b["macro"]) != n:
            raise ValueError(f"{b['id']}: grid gives {n} wins, challenge_numbers.tex gives {counts.get(b['macro'])}")
        wins[b["id"]] = n
    return {
        "meta": provenance([f_grid, f_counts], RELEASE_NAME),
        "n_specs": N_SPECS,
        "target_months": TARGET_MONTHS,
        "horizon": "April 2018 to December 2025",
        "baselines": [{k: v for k, v in b.items() if k != "macro"} for b in BASELINES],
        "wins": wins,
        "specs": specs,
    }


def render_png(payload: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    specs = payload["specs"]
    labels = [f"{'Exp.' if s['window'] == 'Expanding' else 'Roll.'} K={s['k']} · {s['train']} train · {s['eval']} eval" for s in specs]
    shown = [b for b in payload["baselines"] if b["id"] in ("full", "average", "pc")]
    fig, axes = plt.subplots(1, 3, figsize=(10, 6.2), sharey=True)
    ys = list(range(len(specs)))[::-1]
    for ax, b in zip(axes, shown):
        g = [s["gains"][b["id"]] for s in specs]
        cols = ["#18557f" if v > 0 else "#b4541e" for v in g]
        ax.axvline(0, color="0.4", lw=0.8)
        ax.hlines(ys, 0, g, color=cols, lw=1.2)
        ax.scatter(g, ys, c=cols, s=18, zorder=3)
        ax.set_title(f"vs {b['label']}\nwins {payload['wins'][b['id']]} of {payload['n_specs']}", fontsize=9)
        ax.set_xlabel("Gain in prediction R² (pp)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(axis="x", alpha=0.2)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels(labels, fontsize=7)
    fig.suptitle("Residual calibration against three baselines, 24 specifications, 93 months", fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
