"""Exhibit 4 — portfolio-formation comparison (Characteristic Geometry release)."""
from __future__ import annotations

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

EXPECTED_MONTHS = pd.period_range(FIRST, LAST, freq="M").strftime("%Y-%m").tolist()
if len(EXPECTED_MONTHS) != N_MONTHS:
    raise RuntimeError(f"EXPECTED_MONTHS: expected {N_MONTHS} months, built {len(EXPECTED_MONTHS)}")

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
    if months != EXPECTED_MONTHS:
        n = min(len(months), len(EXPECTED_MONTHS))
        pos = next((i for i in range(n) if months[i] != EXPECTED_MONTHS[i]), n)
        raise ValueError(f"{label}: month axis mismatch at position {pos}")


def _finite(xs: np.ndarray, label: str) -> np.ndarray:
    if not np.isfinite(xs).all():
        raise ValueError(f"{label}: non-finite values")
    return xs


def _finite_row(row: dict, label: str) -> dict:
    for key, val in row.items():
        if isinstance(val, float) and not np.isfinite(val):
            raise ValueError(f"{label}: non-finite value in {key}")
    return row


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


def _cross_model_view(monthly: pd.DataFrame, canon: pd.DataFrame, iab: dict, beta: dict) -> dict:
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
    return {"universe": "CORE", "models": models_out, "r": r_out, "turnover": to_out, "table": table}


def _iab_view(p_strict: Path, p_paired: Path, iab: dict, beta: dict) -> dict:
    iab_r = {u: {"beta_only": round_list(beta[u]["r"]), "complete": round_list(iab[u]["r"])} for u in UNIVERSES}
    iab_to = {u: {"beta_only": round_list(beta[u]["turnover"]), "complete": round_list(iab[u]["turnover"])} for u in UNIVERSES}
    strict = pd.read_csv(p_strict)
    iab_table = [
        _finite_row({
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
        }, "iab_table")
        for r in strict.itertuples()
    ]
    paired = [
        _finite_row({
            "sample": r.sample, "universe": r.universe, "n_months": int(r.n_months),
            "mean_diff_monthly": round_sig(r.mean_diff_monthly),
            "ci_low": round_sig(r.ci_low_2p5), "ci_high": round_sig(r.ci_high_97p5),
            "p_two_sided": round_sig(r.p_two_sided), "p_holm": round_sig(r.p_holm),
            "delta_sharpe": round_sig(r.delta_sharpe_descriptive),
        }, "paired")
        for r in pd.read_csv(p_paired).itertuples()
    ]
    return {"universes": UNIVERSES, "strict24_start_index": STRICT24_START, "r": iab_r, "turnover": iab_to,
            "table": iab_table, "paired": paired}


def _ablation_ladder(p_abl: Path) -> list[dict]:
    return [
        _finite_row({
            "sample_months": int(r.sample_months), "model": r.model,
            "gross_sharpe": round_sig(r.gross_sharpe), "annual_return_pct": round_sig(r.ann_mean_pct),
            "annual_vol_pct": round_sig(r.ann_vol_pct), "max_drawdown_pct": round_sig(r.maxdd_pct),
        }, "ablation")
        for r in pd.read_csv(p_abl).itertuples()
    ]


def _nber_bands(p_nber: Path) -> list[dict]:
    return [{"start": r.peak_month, "end": r.trough_month} for r in pd.read_csv(p_nber).itertuples()]


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

    cross_model = _cross_model_view(monthly, canon, iab, beta)
    iab_view = _iab_view(p_strict, p_paired, iab, beta)
    ablation = _ablation_ladder(p_abl)
    nber = _nber_bands(p_nber)

    return {
        "meta": provenance([p_monthly, p_canon, p_iab, p_beta, p_strict, p_paired, p_abl, p_nber], RELEASE_NAME),
        "months": months,
        "nber": nber,
        "cross_model": cross_model,
        "iab": iab_view,
        "ablation": ablation,
    }


PALETTE = {"naipca_iab": "#b0492c", "qz_ipca": "#1f3a5f", "ipca": "#4d6a8f", "rp_pca": "#7a7a7a",
           "ff5": "#a8a8a8", "naipca_beta_only": "#c9a27e"}
BAND = "#eee9dc"


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback: cumulative unit-gross wealth (log scale), CORE, no cost."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import dates as mdates

    x = pd.to_datetime(payload["months"], format="%Y-%m")
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    for b in payload["nber"]:
        ax.axvspan(pd.to_datetime(b["start"]), pd.to_datetime(b["end"]), color=BAND, lw=0)
    for m in payload["cross_model"]["models"]:
        if m["id"] not in payload["cross_model"]["r"]:
            continue
        wealth = np.cumprod(1.0 + np.array(payload["cross_model"]["r"][m["id"]]))
        ax.plot(x, wealth, lw=1.4 if m["id"] != "naipca_iab" else 2.0, color=PALETTE[m["id"]], label=m["label"])
    ax.set_yscale("log")
    ax.set_ylabel("Cumulative unit-gross wealth (log)")
    ax.xaxis.set_major_locator(mdates.YearLocator(10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.set_title("Portfolio formation under alternative factor models, CORE universe, 1973-06 to 2024-11", fontsize=9)
    fig.text(0.01, 0.005, "Gross of costs. NBER recessions shaded. Source: Characteristic Geometry research release (2026-09-09).", fontsize=7, color="#6f6a60")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
