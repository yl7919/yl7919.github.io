"""The csm_coverage payload reproduces the numbers printed in the paper
(Characteristic-Space Metrics, Table II p. 34, Section 8.2 p. 33, Figure 2 p. 35)."""
import json
from pathlib import Path

import pytest

from sources import load_sources
from exhibits import csm_coverage as ex

CONFIG = Path(__file__).resolve().parents[1] / "sources.toml"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="sources.toml not configured on this machine")

# (T, report, method) -> (SE/SD, coverage %) as printed in Table II
TABLE_II = {
    (240, "moderate", "mc_oracle_scale"): (1.000, 94.90),
    (240, "moderate", "oracle_complete_hac"): (0.985, 94.15),
    (240, "moderate", "feasible_fixed_metric_hac"): (0.820, 88.20),
    (240, "moderate", "feasible_no_cross"): (0.978, 93.95),
    (240, "moderate", "feasible_complete_hac"): (0.976, 93.75),
    (960, "moderate", "mc_oracle_scale"): (1.000, 94.75),
    (960, "moderate", "oracle_complete_hac"): (1.004, 94.90),
    (960, "moderate", "feasible_fixed_metric_hac"): (0.838, 89.05),
    (960, "moderate", "feasible_no_cross"): (0.997, 94.65),
    (960, "moderate", "feasible_complete_hac"): (0.996, 94.25),
    (240, "high", "mc_oracle_scale"): (1.000, 95.25),
    (240, "high", "oracle_complete_hac"): (0.957, 93.60),
    (240, "high", "feasible_fixed_metric_hac"): (0.829, 88.15),
    (240, "high", "feasible_no_cross"): (0.948, 93.40),
    (240, "high", "feasible_complete_hac"): (0.942, 93.20),
    (960, "high", "mc_oracle_scale"): (1.000, 95.10),
    (960, "high", "oracle_complete_hac"): (1.037, 95.20),
    (960, "high", "feasible_fixed_metric_hac"): (0.891, 91.75),
    (960, "high", "feasible_no_cross"): (1.017, 95.05),
    (960, "high", "feasible_complete_hac"): (1.016, 94.85),
}


@pytest.fixture(scope="module")
def payload():
    return ex.build(load_sources(CONFIG))


def test_table_ii_reproduced(payload):
    got = {(r["T"], r["report"], r["method"]): (r["se_sd"], r["coverage95"]) for r in payload["rows"]}
    assert set(got) == set(TABLE_II)
    for key, (se_sd, cov) in TABLE_II.items():
        assert got[key][0] == pytest.approx(se_sd, abs=5e-4), key
        assert got[key][1] == pytest.approx(cov, abs=1e-6), key


def test_headline_numbers_on_page(payload):
    rows = {(r["T"], r["report"], r["method"]): r for r in payload["rows"]}
    assert rows[(960, "moderate", "feasible_fixed_metric_hac")]["coverage95"] == 89.05
    assert rows[(960, "moderate", "feasible_complete_hac")]["coverage95"] == 94.25
    assert rows[(960, "high", "feasible_fixed_metric_hac")]["coverage95"] == 91.75
    assert rows[(960, "high", "feasible_complete_hac")]["coverage95"] == 94.85


def test_paired_gains_section_8_2(payload):
    g = {(x["T"], x["report"]): x for x in payload["gains"]}
    assert g[(960, "moderate")]["gain_pp"] == pytest.approx(5.20, abs=1e-6)
    assert g[(960, "high")]["gain_pp"] == pytest.approx(3.10, abs=1e-6)
    assert g[(960, "moderate")]["mcse_pp"] == pytest.approx(0.50, abs=1e-6)
    assert g[(960, "high")]["mcse_pp"] == pytest.approx(0.39, abs=1e-6)
    # the gain equals the coverage difference in Table II
    rows = {(r["T"], r["report"], r["method"]): r["coverage95"] for r in payload["rows"]}
    for rep in ("moderate", "high"):
        diff = rows[(960, rep, "feasible_complete_hac")] - rows[(960, rep, "feasible_fixed_metric_hac")]
        assert diff == pytest.approx(g[(960, rep)]["gain_pp"], abs=1e-6)


def test_figure_2_quantiles(payload):
    q = payload["quantiles"]
    assert len(q) == 4 * 99
    ps = sorted({x["p"] for x in q})
    assert ps[0] == 0.01 and ps[-1] == 0.99
    # fixed-metric tails lie farther from zero than the complete-score tails (Figure 2)
    for rep in ("moderate", "high"):
        lo = {x["method"]: x["studentized"] for x in q if x["report"] == rep and x["p"] == 0.01}
        hi = {x["method"]: x["studentized"] for x in q if x["report"] == rep and x["p"] == 0.99}
        assert lo["feasible_fixed_metric_hac"] < lo["feasible_complete_hac"]
        assert hi["feasible_fixed_metric_hac"] > hi["feasible_complete_hac"]


def test_meta_basenames_only(payload):
    files = payload["meta"]["source_files"]
    assert files == ["rebuilt_interior_coverage.csv", "paired_coverage_gains.csv", "studentized_quantiles.csv"]
    assert "/" not in json.dumps(files)
