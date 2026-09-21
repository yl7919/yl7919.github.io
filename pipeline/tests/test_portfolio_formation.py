import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from common import break_even_bp, net_returns, sharpe
from sources import load_sources
from exhibits import portfolio_formation as pf

CONFIG = Path(__file__).resolve().parents[1] / "sources.toml"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="sources.toml not configured on this machine")


@pytest.fixture(scope="module")
def sources():
    return load_sources(CONFIG)


@pytest.fixture(scope="module")
def payload(sources):
    return pf.build(sources)


def test_months_span_618(payload):
    assert len(payload["months"]) == 618
    assert payload["months"][0] == "1973-06" and payload["months"][-1] == "2024-11"


def test_cross_model_series_reproduce_canonical_table(payload, sources):
    canon = pd.read_csv(sources.geo("03_Replication/modules/current_figures/data/core_model_performance_618.csv"))
    canon = canon[canon.status == "OK"].set_index("model")
    for m in payload["cross_model"]["models"]:
        if m["status"] != "OK":
            continue
        r = np.array(payload["cross_model"]["r"][m["id"]])
        to = np.array(payload["cross_model"]["turnover"][m["id"]])
        row = canon.loc[m["label"]]
        assert sharpe(r) == pytest.approx(row.gross_sharpe, abs=5e-4), m["label"]
        assert sharpe(net_returns(r, to, 10)) == pytest.approx(row.net_sharpe_10bp, abs=5e-4), m["label"]
        assert sharpe(net_returns(r, to, 50)) == pytest.approx(row.net_sharpe_50bp, abs=5e-4), m["label"]
        assert break_even_bp(r, to) == pytest.approx(row.break_even_cost_bp, abs=1.0), m["label"]


def test_cross_model_table_has_six_investable_models(payload):
    ids = {m["id"] for m in payload["cross_model"]["models"]}
    assert ids == {"ff5", "pca", "rp_pca", "ipca", "qz_ipca", "naipca_beta_only", "naipca_iab"}
    ok = [m for m in payload["cross_model"]["models"] if m["status"] == "OK"]
    assert len(ok) == 6
    pca = next(m for m in payload["cross_model"]["models"] if m["id"] == "pca")
    assert pca["status"] == "DEGENERATE_NEAR_ZERO_GROSS"
    assert "pca" not in payload["cross_model"]["r"]


def test_iab_strict24_reproduces_release_table(payload, sources):
    tab = pd.read_csv(sources.geo("03_Replication/modules/alpha_aware_iab/outputs/tables/Strict24_Main_Performance.csv"))
    start = payload["iab"]["strict24_start_index"]
    assert start == 24
    for _, row in tab.iterrows():
        leg = "beta_only" if row.portfolio == "NA-IPCA beta-only" else "complete"
        r = np.array(payload["iab"]["r"][row.universe][leg])[start:]
        to = np.array(payload["iab"]["turnover"][row.universe][leg])[start:]
        assert len(r) == 594
        assert sharpe(r) == pytest.approx(row.sharpe_gross, abs=5e-4), (row.universe, leg)
        assert sharpe(net_returns(r, to, 10)) == pytest.approx(row.net_sharpe_10bp, abs=5e-4), (row.universe, leg)


def test_iab_table_and_paired_rows_carried_through(payload):
    assert len(payload["iab"]["table"]) == 8
    assert {r["universe"] for r in payload["iab"]["paired"]} == {"CORE", "MEGA", "LARGE", "SMALL"}
    assert {r["sample"] for r in payload["iab"]["paired"]} == {"STRICT24_FULL", "STRICT24_RECENT_2007_10"}
    core = next(r for r in payload["iab"]["paired"] if r["universe"] == "CORE" and r["sample"] == "STRICT24_FULL")
    assert core["mean_diff_monthly"] == pytest.approx(0.004877, abs=1e-6)


def test_ablation_rows(payload):
    assert len(payload["ablation"]) == 9
    row = next(r for r in payload["ablation"] if r["sample_months"] == 618 and r["model"] == "complete_iab")
    assert row["gross_sharpe"] == pytest.approx(2.4926, abs=1e-4)


def test_nber_bands_parsed(payload):
    assert payload["nber"][0] == {"start": "1973-11", "end": "1975-03"}
    assert all(b["start"] < b["end"] for b in payload["nber"])


def test_no_nan_in_series(payload):
    for block in (payload["cross_model"]["r"], payload["cross_model"]["turnover"]):
        for k, xs in block.items():
            assert all(math.isfinite(x) for x in xs), k
    for u, legs in payload["iab"]["r"].items():
        for leg, xs in legs.items():
            assert all(math.isfinite(x) for x in xs), (u, leg)


def test_provenance_present(payload):
    meta = payload["meta"]
    assert meta["source_release"].startswith("Characteristic_Geometry_and_Portfolio_Choice_Research_Release")
    assert any(f.endswith("core_monthly_unitgross_returns_source.csv") for f in meta["source_files"])


def test_check_months_rejects_interior_gap():
    bad = list(pf.EXPECTED_MONTHS)
    bad[100] = bad[99]  # duplicate masks a missing month; length and ends unchanged
    with pytest.raises(ValueError, match="position 100"):
        pf._check_months(bad, "x")


def test_finite_row_rejects_nan():
    with pytest.raises(ValueError, match="p_holm"):
        pf._finite_row({"universe": "CORE", "n_months": 594, "p_holm": float("nan")}, "paired")
    assert pf._finite_row({"a": 1.5, "b": "s", "c": 3}, "ok") == {"a": 1.5, "b": "s", "c": 3}
