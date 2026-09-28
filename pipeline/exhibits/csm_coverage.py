"""Characteristic-Space Metrics, Table II and Figure 2: what is missed when an
estimated Gram metric is treated as known.

Reads the recorded simulation summaries shipped with the paper's presentation
package (no estimation is rerun here):
  data/rebuilt_interior_coverage.csv   Table II rows (coverage95, se_to_mc_sd)
  data/paired_coverage_gains.csv       paired coverage gains and their MC s.e.
  data/studentized_quantiles.csv       Figure 2 (T = 960 studentized quantiles)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from common import provenance, round_sig
from sources import Sources

ROOT = "csm_presentation"
F_COV = "data/rebuilt_interior_coverage.csv"
F_GAIN = "data/paired_coverage_gains.csv"
F_QQ = "data/studentized_quantiles.csv"
RELEASE = "Characteristic-Space Metrics in Factor Models: Identification and Inference (September 2026), recorded simulation evidence"

# Table II row order and labels (paper, p. 34)
METHODS = [
    ("mc_oracle_scale", "Monte Carlo scale"),
    ("oracle_complete_hac", "Oracle-influence HAC"),
    ("feasible_fixed_metric_hac", "Metric treated as known"),
    ("feasible_no_cross", "Metric, no cross term"),
    ("feasible_complete_hac", "Complete-score HAC"),
]
REPORTS = [("moderate", "Moderate-sensitivity report"), ("high", "High-sensitivity report")]
HORIZONS = [240, 960]
QQ_METHODS = ["feasible_fixed_metric_hac", "feasible_complete_hac"]


def build(sources: Sources) -> dict:
    p_cov = sources.path(ROOT, F_COV)
    p_gain = sources.path(ROOT, F_GAIN)
    p_qq = sources.path(ROOT, F_QQ)
    cov = pd.read_csv(p_cov)
    gain = pd.read_csv(p_gain)
    qq = pd.read_csv(p_qq)

    rows = []
    for T in HORIZONS:
        for rid, _ in REPORTS:
            for mid, label in METHODS:
                d = cov[(cov["T"] == T) & (cov["target"] == rid) & (cov["method"] == mid)]
                if len(d) != 1:
                    raise ValueError(f"{F_COV}: expected one row for T={T}, {rid}, {mid}; found {len(d)}")
                r = d.iloc[0]
                if int(r["n"]) != 2000:
                    raise ValueError(f"{F_COV}: unexpected replication count {r['n']}")
                rows.append({
                    "T": T, "report": rid, "method": mid, "label": label,
                    # rounded as printed in Table II: coverage to 0.05 pp grid (2 dp), SE/SD to 3 dp
                    "coverage95": round(float(r["coverage95"]) * 100, 2),
                    "se_sd": round(float(r["se_to_mc_sd"]), 3),
                })

    gains = []
    for T in HORIZONS:
        for rid, _ in REPORTS:
            d = gain[(gain["T"] == T) & (gain["target"] == rid)]
            if len(d) != 1:
                raise ValueError(f"{F_GAIN}: expected one row for T={T}, {rid}")
            r = d.iloc[0]
            gains.append({"T": T, "report": rid,
                          "gain_pp": round(float(r["coverage_gain_pp"]), 2),
                          "mcse_pp": round(float(r["paired_mcse_pp"]), 2)})

    quant = []
    for rid, _ in REPORTS:
        for mid in QQ_METHODS:
            d = qq[(qq["target"] == rid) & (qq["method"] == mid) & (qq["T"] == 960)].sort_values("probability")
            if len(d) != 99:
                raise ValueError(f"{F_QQ}: expected 99 quantiles for {rid}, {mid}; found {len(d)}")
            vals = d[["normal_quantile", "studentized_quantile"]].to_numpy(float)
            if not np.isfinite(vals).all():
                raise ValueError(f"{F_QQ}: non-finite values for {rid}, {mid}")
            for p, z, s in zip(d["probability"], vals[:, 0], vals[:, 1]):
                quant.append({"report": rid, "method": mid, "p": round(float(p), 2),
                              "normal": round_sig(float(z), 5), "studentized": round_sig(float(s), 5)})

    return {
        "meta": {
            **provenance([p_cov, p_gain, p_qq], RELEASE),
            "replications": 2000,
            "design": "L = 12, K = 2, Ko = 1, N = 100; both reports have population value 0.5",
            "locators": {"rows": "Table II (p. 34)", "quantiles": "Figure 2 (p. 35)", "gains": "Section 8.2 (p. 33)"},
        },
        "methods": [{"id": m, "label": l} for m, l in METHODS],
        "reports": [{"id": r, "label": l} for r, l in REPORTS],
        "rows": rows,
        "gains": gains,
        "quantiles": quant,
    }


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback: 95% coverage by method, T = 960, both reports."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [m["label"] for m in payload["methods"]]
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    colors = {"moderate": "#18557f", "high": "#8a6a1a"}
    marker = {"moderate": "o", "high": "s"}
    for rep in payload["reports"]:
        xs = [next(r["coverage95"] for r in payload["rows"] if r["T"] == 960 and r["report"] == rep["id"] and r["method"] == m["id"])
              for m in payload["methods"]]
        ax.scatter(xs, range(len(labels)), color=colors[rep["id"]], marker=marker[rep["id"]], label=rep["label"], zorder=3)
    ax.axvline(95, color="#6f6a60", ls="--", lw=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Coverage of nominal 95% intervals (%), T = 960")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.text(0.01, 0.005, "2,000 replications per horizon. Source: Characteristic-Space Metrics, Table II.", fontsize=7, color="#6f6a60")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
