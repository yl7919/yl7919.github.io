"""Shared math and I/O for the data pipeline.

Conventions replicate the Characteristic Geometry research release
(modules/alpha_aware_iab/src/build_tables.py): annualised Sharpe with
ddof=1, net return = gross - cost_bp/1e4 * turnover, break-even as the
first integer bp in 0..500 with non-positive net Sharpe.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PIPELINE_VERSION = "1.0.0"


def sharpe(r: np.ndarray) -> float:
    r = np.asarray(r, dtype=float)
    vol = np.std(r, ddof=1) * math.sqrt(12)
    return float(np.mean(r) * 12 / vol) if vol > 1e-12 else float("nan")


def annual_return(r: np.ndarray) -> float:
    return float(np.mean(np.asarray(r, dtype=float)) * 12)


def annual_vol(r: np.ndarray) -> float:
    return float(np.std(np.asarray(r, dtype=float), ddof=1) * math.sqrt(12))


def net_returns(r: np.ndarray, turnover: np.ndarray, cost_bp: float) -> np.ndarray:
    return np.asarray(r, dtype=float) - np.asarray(turnover, dtype=float) * cost_bp / 1e4


def max_drawdown(r: np.ndarray) -> float:
    wealth = np.cumprod(1.0 + np.asarray(r, dtype=float))
    high = np.maximum.accumulate(wealth)
    dd = np.divide(wealth, high, out=np.full_like(wealth, np.nan), where=high != 0) - 1.0
    return float(np.nanmin(dd))


def break_even_bp(r: np.ndarray, turnover: np.ndarray) -> float:
    for bp in range(501):
        if sharpe(net_returns(r, turnover, bp)) <= 0:
            return float(bp)
    return float("nan")


def round_sig(x: float, digits: int = 6) -> float:
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, digits - int(math.floor(math.log10(abs(x)))) - 1)


def round_list(xs) -> list[float]:
    return [round_sig(float(x)) for x in xs]


def provenance(source_files: list[Path], source_release: str) -> dict:
    return {
        "source_release": source_release,
        "source_files": [str(p) for p in source_files],
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pipeline_version": PIPELINE_VERSION,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, separators=(",", ":"), allow_nan=False)
        fh.write("\n")
