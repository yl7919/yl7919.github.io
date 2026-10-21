"""sf_penalty_curves: Same Forecasts, Different Portfolios, Figure 1 (p. 4), Table I Panel A (p. 19),
Table II Panels A-B (p. 24).

Every printed string in the JSON is checked against the paper's own exhibit map (exhibits/map.csv in the
replication package: one row per printed table cell with its source file, row, column and format), and the
headline numbers are pinned to the values printed in the paper. Skipped when sources.toml or its
`same_forecasts_package` root is missing.
"""
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from exhibits import sf_penalty_curves as sp
from exhibits._paper_data import MINUS, Package, sci
from sources import load_sources

from private_guards import banned_names

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"
FORBIDDEN = ("/Volumes", "/Users", "Final_Polished", "factor-penalties", "intercept-portfolios-replication",
             "Replication_Package", "Claude") + banned_names()
LADDER_ROW = {"euclid": "IPCA, Euclidean units", "gram": "IPCA, Gram units", "rppca": "RP-PCA",
              "ff5": "FF5 (characteristic-instrumented)"}


def map_printed(text: str) -> str:
    """The map's LaTeX cell text in the JSON's display form."""
    text = text.replace("$-$", MINUS)
    m = re.fullmatch(r"(-?[\d.]+)\\times10\^\{(-?\d+)\}", text)
    return sci(float(m.group(1)) * 10 ** int(m.group(2))) if m else text


@pytest.fixture(scope="module")
def sources():
    if not CONFIG.exists():
        pytest.skip("sources.toml not configured on this machine")
    s = load_sources(CONFIG)
    if "same_forecasts_package" not in s.extra:
        pytest.skip("same_forecasts_package root not configured")
    return s


@pytest.fixture(scope="module")
def payload(sources):
    return sp.build(sources)


@pytest.fixture(scope="module")
def pkg(sources):
    p = Package(sources.path("same_forecasts_package", sp.ZIP))
    yield p
    p.close()


def _map(pkg, exhibit, source):
    return [r for r in pkg.rows("exhibits/map.csv") if r["exhibit"] == exhibit and r["source_file"] == source]


def test_headline_numbers_as_printed(payload):
    h = payload["headline"]
    # Table I, p. 19; Table II, Panel B, p. 24; abstract and Section IV.C, p. 22.
    assert (h["euclid_ref"], h["gram_ref"], h["unpenalised"], h["unpenalised_gram"]) == ("0.69", "1.07", "1.62", "1.62")
    assert (h["diff_ref"], h["diff_ref_ci"]) == ("0.38", ["0.09", "0.64"])
    assert h["unit_consistent_ref"] == "0.69"
    assert h["weights_own_units_median"] == "0.17" and h["weights_one_set_median"] == "1.0 × 10⁻¹¹"


def test_grid_and_series(payload):
    assert payload["lambdas"] == [0.0, 0.001, 0.003, 0.01, 0.03, 0.1] and payload["reference_lambda"] == 0.01
    by = {s["id"]: s for s in payload["series"]}
    assert by["euclid"]["printed"] == ["1.62", "1.31", "1.04", "0.69", "0.45", "0.30"]
    assert by["gram"]["printed"] == ["1.62", "1.30", "1.17", "1.07", "1.02", "1.00"]
    for s in payload["series"]:
        for b in ("12", "24", "60"):
            lo, hi = s["band"][b]["lo"], s["band"][b]["hi"]
            assert len(lo) == len(hi) == 6 and all(l < x < h for l, x, h in zip(lo, s["sharpe"], hi))


def test_series_match_table_i_panel_a(payload, pkg):
    cells = {}
    for r in _map(pkg, "Table I", "data/core/13_ladder_594.csv"):
        m = re.search(r"\(panel=A gross, row=(?P<row>.+), lambda=(?P<lam>[^)]+)\)", r["row_or_summary"])
        if m and r["column"] == "sharpe":
            cells[(m["row"], m["lam"])] = map_printed(r["printed"])
    by = {s["id"]: s for s in payload["series"]}
    n = 0
    for sid, row in LADDER_ROW.items():
        for lam, txt in zip(payload["lambdas"], payload["lambda_labels"]):
            want = cells.get((row, txt))
            if want is not None:
                assert by[sid]["printed"][payload["lambdas"].index(lam)] == want, (sid, txt)
                n += 1
    assert n == 24
    assert cells[("IPCA, unit-consistent penalty", "0.01")] == payload["units"]["one_set"]["check"]["printed"] == "0.69"


def test_diffs_match_table_ii_panel_b(payload, pkg):
    rows = pkg.rows(sp.F_CONTRASTS)
    by = {d["id"]: d for d in payload["diffs"]}
    kind_to_id = {k: i for i, k, *_ in sp.DIFFS}
    n = 0
    for r in _map(pkg, "Table II", "data/core/10_contrasts_594.csv"):
        src = rows[int(re.match(r"row (\d+)", r["row_or_summary"]).group(1))]
        assert src["block"] == "12"
        if src["kind"] not in kind_to_id:
            continue                                       # Panel C: tested in test_penalty_removal_matches_panel_c
        d = by[kind_to_id[src["kind"]]]
        i = sp.LAMBDAS.index(float(src["lambda_F"]))
        got = {"sharpe_diff": d["printed"][i], "sharpe_ci_lo": d["printed_ci"][i][0], "sharpe_ci_hi": d["printed_ci"][i][1]}
        if r["column"] in got:
            assert got[r["column"]] == map_printed(r["printed"]), (src["kind"], src["lambda_F"], r["column"])
            n += 1
    assert n == 36


def test_penalty_removal_matches_panel_c(payload, pkg):
    rows = pkg.rows(sp.F_CONTRASTS)
    fam_to_id = {fam: sid for sid, fam, *_ in sp.SERIES}
    by = {r["series"]: r for r in payload["penalty_removal"]}
    col = {"sharpe_diff": "diff", "sharpe_ci_lo": "lo", "sharpe_ci_hi": "hi",
           "ann_mean_diff_pp": "mean_diff_pp", "ann_mean_ci_pp_lo": "mean_lo", "ann_mean_ci_pp_hi": "mean_hi"}
    n = 0
    for r in _map(pkg, "Table II", "data/core/10_contrasts_594.csv"):
        src = rows[int(re.match(r"row (\d+)", r["row_or_summary"]).group(1))]
        if src["kind"] == "lam0_minus_lam0.01" and r["column"] in col:
            assert by[fam_to_id[src["family"]]]["printed"][col[r["column"]]] == map_printed(r["printed"])
            n += 1
    assert n == 24
    # Section IV.C (pp. 23-24): removing the reference penalty raises the Euclidean fit by 0.93 [0.61, 1.25]
    # and the Gram fit by 0.55 [0.35, 0.77].
    assert [by["euclid"]["printed"][k] for k in ("diff", "lo", "hi")] == ["0.93", "0.61", "1.25"]
    assert [by["gram"]["printed"][k] for k in ("diff", "lo", "hi")] == ["0.55", "0.35", "0.77"]


def test_weights_match_table_ii_panel_a(payload, pkg):
    wid = {k: i for k, i, _ in sp.WEIGHT_ROWS}
    stat = {"one_minus_cosine": "one_minus_cosine", "unit_gross_L1_distance": "l1_distance"}
    n = 0
    for r in _map(pkg, "Table II", "data/core/13_holdings_594.json"):
        path = r["row_or_summary"].removeprefix("key ").split("/")
        if path[0] == "forecast_gap":
            got = payload["weights"]["forecast_gap"]["printed"][path[1]]
        elif path[0] in wid and path[1] in stat:
            got = payload["weights"][wid[path[0]]][stat[path[1]]]["printed"][path[2]]
        else:
            continue
        assert got == map_printed(r["printed"]), r["row_or_summary"]
        n += 1
    assert n == 18


def test_one_set_of_units(payload):
    u = payload["units"]
    assert u["default"] == "own" and u["own"]["curves"] == ["euclid", "gram"]
    assert u["one_set"]["curve"] == "euclid" and u["one_set"]["check"]["fit"] == "gram"
    assert u["one_set"]["status"] == ["computed", "by_identity", "by_identity", "computed", "by_identity", "by_identity"]
    assert u["one_set"]["check"]["sharpe"] == 0.6857844737 and u["one_set"]["check"]["abs_diff_from_curve"] < 1e-5
    assert u["one_set_gram"]["curve"] == "gram" and u["one_set_gram"]["check"]["printed"] == "1.07"
    assert u["one_set_gram"]["check"]["abs_diff_from_curve"] < 1e-5


def test_round18_twin_is_byte_identical(sources):
    """The package's Figure 1 data equal the experiment output it was released from (when that root is configured)."""
    if "same_forecasts" not in sources.extra:
        pytest.skip("same_forecasts root not configured")
    p = Package(sources.path("same_forecasts_package", sp.ZIP))
    try:
        assert p.read_bytes(sp.F_LEVELS) == sources.path("same_forecasts", "add12_sharpe_by_lambda_594.csv").read_bytes()
        assert p.read_bytes(sp.F_CONTRASTS) == sources.path("same_forecasts", "add12_contrasts_594.csv").read_bytes()
    finally:
        p.close()


def test_provenance_has_basenames_and_no_private_strings(payload):
    meta = payload["meta"]
    assert meta["source_files"] == ["10_sharpe_by_lambda_594.csv", "10_contrasts_594.csv", "13_ladder_594.csv", "13_holdings_594.json"]
    assert meta["source_release"].startswith("Same Forecasts, Different Portfolios: Factor Normalization and Regularization")
    assert meta["sample"]["months"] == 594
    assert not any(f in json.dumps(payload, ensure_ascii=False) for f in FORBIDDEN)
    assert not any(f in (PIPELINE / "exhibits" / "sf_penalty_curves.py").read_text(encoding="utf-8")
                   for f in ("factor-penalties", "intercept-portfolios-replication", "/Volumes"))


def test_build_check_and_png(tmp_path, payload):
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "sf_penalty_curves",
            "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img")]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
    png = tmp_path / "img" / "sf_penalty_curves.png"
    assert struct.unpack(">II", png.read_bytes()[16:24]) == (1200, 630) and png.stat().st_size <= 150_000
    assert (tmp_path / "data" / "sf_penalty_curves.json").stat().st_size <= 30_000
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0 and "sf_penalty_curves: unchanged" in res.stdout


def test_shipped_json_matches_fresh_build(payload):
    shipped = json.loads((WEB / "site" / "data" / "sf_penalty_curves.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(payload))
    for p in (shipped, fresh):
        p["meta"].pop("built_at", None)
    assert shipped == fresh
