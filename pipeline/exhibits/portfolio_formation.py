"""Exhibit 4 — portfolio-formation comparison (Characteristic Geometry release)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from common import (
    annual_return,
    annual_vol,
    break_even_bp,
    max_drawdown,
    net_returns,
    provenance,
    round_list,
    round_sig,
    sharpe,
)
from sources import Sources

RELEASE_NAME = "Characteristic_Geometry_and_Portfolio_Choice_Research_Release_2026-09-09"
MOD = "03_Replication/modules/"
F_MONTHLY = MOD + "current_figures/data/core_monthly_unitgross_returns_source.csv"
F_CANON = MOD + "current_figures/data/core_model_performance_618.csv"
F_IAB = MOD + "alpha_aware_iab/data/derived/iab_ra_monthly.csv"
F_BETA = MOD + "alpha_aware_iab/data/derived/beta_only_monthly.csv"
F_STRICT = MOD + "alpha_aware_iab/outputs/tables/Strict24_Main_Performance.csv"
F_PAIRED = MOD + "alpha_aware_iab/outputs/tables/Strict24_Paired_Inference.csv"
F_ABL = "02_Presentation/Source/data/ablation_summary.csv"
F_NBER = MOD + "business_cycles/nber_monthly.csv"

N_MONTHS = 618
FIRST, LAST = "1973-06", "2024-11"
STRICT24_START = 24

# id, canonical-table label, source-file model key (None = from IAB module files)
MODELS = [
    ("ff5", "FF5", "FF5"),
    ("pca", "PCA", "PCA"),
    ("rp_pca", "RP-PCA", "RP-PCA"),
    ("ipca", "IPCA", "IPCA"),
    ("qz_ipca", "QZ-IPCA (rolling mean)", "QZ-IPCA rolling_mean"),
    ("naipca_beta_only", "NA-IPCA beta-only", None),
    ("naipca_iab", "NA-IPCA IAB-RA", None),
]
UNIVERSES = ["CORE", "MEGA", "LARGE", "SMALL"]


def _month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.strftime("%Y-%m")


def _check_months(months: list[str], label: str) -> None:
    if len(months) != N_MONTHS or months[0] != FIRST or months[-1] != LAST:
        raise ValueError(f"{label}: expected {N_MONTHS} months {FIRST}..{LAST}, got {len(months)} {months[:1]}..{months[-1:]}")


def _finite(xs: np.ndarray, label: str) -> np.ndarray:
    if not np.isfinite(xs).all():
        raise ValueError(f"{label}: non-finite values")
    return xs


def _load_iab_leg(path: Path, signal: str) -> dict[str, dict[str, np.ndarray]]:
    df = pd.read_csv(path)
    if set(df.signal.unique()) != {signal}:
        raise ValueError(f"{path.name}: unexpected signal values {df.signal.unique()}")
    out: dict[str, dict[str, np.ndarray]] = {}
    for u in UNIVERSES:
        d = df[df.universe == u].sort_values("test_date")
        months = _month(d.test_date).tolist()
        _check_months(months, f"{path.name}:{u}")
        out[u] = {
            "months": months,
            "r": _finite(d.r_unitgross.to_numpy(float), f"{path.name}:{u}:r"),
            "turnover": _finite(d.turnover_unitgross.to_numpy(float), f"{path.name}:{u}:turnover"),
        }
    return out


def _metrics(r: np.ndarray, to: np.ndarray) -> dict:
    return {
        "gross_sharpe": round_sig(sharpe(r)),
        "net_sharpe_10bp": round_sig(sharpe(net_returns(r, to, 10))),
        "net_sharpe_50bp": round_sig(sharpe(net_returns(r, to, 50))),
        "annual_return_pct": round_sig(annual_return(r) * 100),
        "annual_vol_pct": round_sig(annual_vol(r) * 100),
        "max_drawdown_pct": round_sig(max_drawdown(r) * 100),
        "turnover": round_sig(float(np.mean(to))),
        "break_even_cost_bp": break_even_bp(r, to),
    }


def build(sources: Sources) -> dict:
    p_monthly, p_canon = sources.geo(F_MONTHLY), sources.geo(F_CANON)
    p_iab, p_beta = sources.geo(F_IAB), sources.geo(F_BETA)
    p_strict, p_paired = sources.geo(F_STRICT), sources.geo(F_PAIRED)
    p_abl, p_nber = sources.geo(F_ABL), sources.geo(F_NBER)

    monthly = pd.read_csv(p_monthly)
    canon = pd.read_csv(p_canon).set_index("model")
    iab = _load_iab_leg(p_iab, "NA-IPCA IAB-RA")
    beta = _load_iab_leg(p_beta, "NA-IPCA beta-only")
    months = iab["CORE"]["months"]

    # ---- cross-model view (CORE universe) ----
    models_out, r_out, to_out, table = [], {}, {}, []
    for mid, label, src_key in MODELS:
        row = canon.loc[label]
        entry = {"id": mid, "label": label, "status": str(row.status), "risk_matrix": str(row.risk_matrix)}
        models_out.append(entry)
        if row.status != "OK":
            continue
        if src_key is None:
            leg = iab if mid == "naipca_iab" else beta
            r, to = leg["CORE"]["r"], leg["CORE"]["turnover"]
        else:
            d = monthly[monthly.model == src_key].sort_values("date")
            _check_months(_month(d.date).tolist(), f"monthly:{src_key}")
            g = _finite(d.raw_gross_exposure.to_numpy(float), f"monthly:{src_key}:gross")
            if (g <= 0).any():
                raise ValueError(f"monthly:{src_key}: non-positive gross exposure")
            r = _finite(d.unit_gross_return.to_numpy(float) / g, f"monthly:{src_key}:r")
            to = _finite(d.one_way_turnover.to_numpy(float) / g, f"monthly:{src_key}:turnover")
        r_out[mid], to_out[mid] = round_list(r), round_list(to)
        table.append({"id": mid, "label": label, **_metrics(r, to)})

    # ---- IAB view by universe ----
    iab_r = {u: {"beta_only": round_list(beta[u]["r"]), "complete": round_list(iab[u]["r"])} for u in UNIVERSES}
    iab_to = {u: {"beta_only": round_list(beta[u]["turnover"]), "complete": round_list(iab[u]["turnover"])} for u in UNIVERSES}
    strict = pd.read_csv(p_strict)
    iab_table = [
        {
            "universe": r.universe,
            "leg": "beta_only" if r.portfolio == "NA-IPCA beta-only" else "complete",
            "label": r.portfolio,
            "n_months": int(r.n_months),
            "gross_sharpe": round_sig(r.sharpe_gross),
            "net_sharpe_10bp": round_sig(r.net_sharpe_10bp),
            "net_sharpe_50bp": round_sig(r.net_sharpe_50bp),
            "annual_return_pct": round_sig(r.ann_return * 100),
            "annual_vol_pct": round_sig(r.ann_vol * 100),
            "max_drawdown_pct": round_sig(r.max_drawdown * 100),
            "turnover": round_sig(r.one_way_turnover),
            "hit_ratio": round_sig(r.hit_ratio),
            "break_even_cost_bp": float(r.break_even_cost_bp),
        }
        for r in strict.itertuples()
    ]
    paired = [
        {
            "sample": r.sample, "universe": r.universe, "n_months": int(r.n_months),
            "mean_diff_monthly": round_sig(r.mean_diff_monthly),
            "ci_low": round_sig(r.ci_low_2p5), "ci_high": round_sig(r.ci_high_97p5),
            "p_two_sided": round_sig(r.p_two_sided), "p_holm": round_sig(r.p_holm),
            "delta_sharpe": round_sig(r.delta_sharpe_descriptive),
        }
        for r in pd.read_csv(p_paired).itertuples()
    ]

    # ---- ablation ladder ----
    ablation = [
        {
            "sample_months": int(r.sample_months), "model": r.model,
            "gross_sharpe": round_sig(r.gross_sharpe), "annual_return_pct": round_sig(r.ann_mean_pct),
            "annual_vol_pct": round_sig(r.ann_vol_pct), "max_drawdown_pct": round_sig(r.maxdd_pct),
        }
        for r in pd.read_csv(p_abl).itertuples()
    ]

    nber = [{"start": r.peak_month, "end": r.trough_month} for r in pd.read_csv(p_nber).itertuples()]

    return {
        "meta": provenance([p_monthly, p_canon, p_iab, p_beta, p_strict, p_paired, p_abl, p_nber], RELEASE_NAME),
        "months": months,
        "nber": nber,
        "cross_model": {"universe": "CORE", "models": models_out, "r": r_out, "turnover": to_out, "table": table},
        "iab": {"universes": UNIVERSES, "strict24_start_index": STRICT24_START, "r": iab_r, "turnover": iab_to,
                "table": iab_table, "paired": paired},
        "ablation": ablation,
    }
