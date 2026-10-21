"""sf_mean_input: Same Forecasts, Different Portfolios, Table III (p. 30), Figure 4 (p. 29), Table I (p. 19).

Every printed string is checked against the paper's exhibit map (exhibits/map.csv in the replication package),
and the headline numbers are pinned to the printed values: 2.51 against the best zero-intercept 1.62, gain 0.89
[0.59, 1.26]; net of 25 bp 1.60 against 1.03, gain 0.57 [0.29, 0.89]. Skipped when sources.toml or its
`same_forecasts_package` root is missing.
"""
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from exhibits import sf_mean_input as mi
from exhibits._paper_data import MINUS, Package
from sources import load_sources

from private_guards import banned_names

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"
FORBIDDEN = ("/Volumes", "/Users", "Final_Polished", "factor-penalties", "intercept-portfolios-replication",
             "Replication_Package", "Claude") + banned_names()
ROW_TO_INPUT = {"ip": "full_mean", "fm": "factor_means"}


def map_printed(text: str) -> str:
    return text.replace("$-$", MINUS)


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
    return mi.build(sources)


@pytest.fixture(scope="module")
def pkg(sources):
    p = Package(sources.path("same_forecasts_package", mi.ZIP))
    yield p
    p.close()


def _map(pkg, exhibit, source):
    return [r for r in pkg.rows("exhibits/map.csv") if r["exhibit"] == exhibit and r["source_file"] == source]


def _idx(r):
    return int(re.match(r"row (\d+)", r["row_or_summary"]).group(1))


def test_headline_numbers_as_printed(payload):
    h = payload["headline"]
    assert (h["ip_ref"], h["zp"], h["gain_vs_zp"], h["gain_vs_zp_ci"]) == ("2.51", "1.62", "0.89", ["0.59", "1.26"])
    assert (h["ip_net25_ref"], h["zp_net25"], h["gain_vs_zp_net25"], h["gain_vs_zp_net25_ci"]) == ("1.60", "1.03", "0.57", ["0.29", "0.89"])
    assert (h["fm_ref"], h["fm_unpenalised"], h["ip_unpenalised"]) == ("0.39", "0.56", "2.50")
    assert (h["gain_vs_fm_ref"], h["gain_vs_fm_ref_ci"]) == ("2.12", ["1.64", "2.68"])


def test_panel_a_matches_the_map(payload, pkg):
    t3 = pkg.rows(mi.F_TABLE3)
    net = pkg.rows(mi.F_NET)
    by = {i["id"]: i for i in payload["inputs"]}
    n = 0
    for r in _map(pkg, "Table III", "data/core/14_table3_594.csv"):
        src = t3[_idx(r)]
        if src["panel"] != "A":
            continue
        inp = by[ROW_TO_INPUT[src["row"]]]
        i = mi.LAMBDAS.index(float(src["lambda"]))
        got = {"sharpe": inp["gross"]["printed"][i], "ann_mean_pct": inp["gross"]["printed_mean"][i],
               "ann_vol_pct": inp["gross"]["printed_vol"][i], "net25_sharpe": inp["net25"]["printed"][i]}[r["column"]]
        assert got == map_printed(r["printed"]), (src["row"], src["lambda"], r["column"])
        n += 1
    for r in _map(pkg, "Table III", "data/core/15_net_by_lambda_594.csv"):
        src = net[_idx(r)]
        inp = by["full_mean" if src["portfolio"] == "intercept portfolio" else "factor_means"]
        assert inp["net25"]["printed"][mi.LAMBDAS.index(float(src["lambda"]))] == map_printed(r["printed"])
        n += 1
    assert n == 48                                          # 2 portfolios x 6 penalties x 4 columns


def test_panel_b_matches_the_map(payload, pkg):
    t3 = pkg.rows(mi.F_TABLE3)
    netcon = pkg.rows(mi.F_NETCON)
    fm = payload["contrasts"]["full_minus_factor"]
    zp = {z["ip_lambda"]: z for z in payload["contrasts"]["full_minus_best_zp"]["rows"]}
    key = {"sharpe_diff": "diff", "sharpe_ci_lo": "lo", "sharpe_ci_hi": "hi"}
    n = 0
    for r in _map(pkg, "Table III", "data/core/14_table3_594.csv"):
        src = t3[_idx(r)]
        if src["panel"] != "B" or src["row"] not in ("ip_minus_fm", "ip_minus_zp"):
            continue
        kind, stat = r["column"].split("_", 1)                  # gross_sharpe_lo_b12 -> ("gross", "sharpe_lo_b12")
        stat = {"sharpe_diff": "diff", "sharpe_lo_b12": "lo", "sharpe_hi_b12": "hi"}[stat]
        lam = float(src["lambda"])
        if src["row"] == "ip_minus_fm":
            got = fm["gross" if kind == "gross" else "net25"][mi.LAMBDAS.index(lam)]["printed"][stat]
        else:
            got = zp[lam]["gross" if kind == "gross" else "net25"]["printed"][stat]
        assert got == map_printed(r["printed"]), (src["row"], lam, r["column"])
        n += 1
    for r in _map(pkg, "Table III", "data/core/15_contrasts_594.csv"):
        src = netcon[_idx(r)]
        assert src["block"] == "12" and src["cost_bp"] == "25"
        assert fm["net25"][mi.LAMBDAS.index(float(src["lambda"]))]["printed"][key[r["column"]]] == map_printed(r["printed"])
        n += 1
    assert n == 6 * 3 + 2 * 3 + 2 * 6 + 12                  # IP-fm gross; IP-fm net at 0 and 0.01; IP-ZP; IP-fm net elsewhere


def test_benchmark_matches_table_i(payload, pkg):
    lad = pkg.rows(mi.F_LADDER)
    seen = set()
    for r in _map(pkg, "Table I", "data/core/13_ladder_594.csv"):
        src = lad[_idx(r)]
        if src["row"] == "IPCA, Euclidean units" and src["lambda"] == "0" and r["column"] == "sharpe":
            want = map_printed(r["printed"])
            got = payload["benchmark"]["gross" if src["panel"] == "A gross" else "net25"]["printed"]
            assert got == want
            seen.add(src["panel"])
    assert seen == {"A gross", "B net25"}
    assert payload["benchmark"]["gross"]["printed_mean"] == "6.6" and payload["benchmark"]["gross"]["printed_vol"] == "4.1"


def test_bands_hold_the_point_estimates(payload):
    for inp in payload["inputs"]:
        for b in ("12", "24", "60"):
            band = inp["gross"]["band"][b]
            assert all(lo < x < hi for lo, x, hi in zip(band["lo"], inp["gross"]["sharpe"], band["hi"]))
    assert [i["palette_key"] for i in payload["inputs"]] == ["beta_only", "complete"]
    assert payload["benchmark"]["palette_key"] == "ipca"


def test_provenance_has_basenames_and_no_private_strings(payload):
    meta = payload["meta"]
    assert meta["source_files"] == ["14_table3_594.csv", "14_intercept_curve_594.csv", "15_net_by_lambda_594.csv",
                                    "15_contrasts_594.csv", "13_ladder_594.csv"]
    assert meta["locators"]["levels"] == "Table III, Panel A, p. 30" and meta["locators"]["figure"] == "Figure 4, p. 29"
    assert not any(f in json.dumps(payload, ensure_ascii=False) for f in FORBIDDEN)


def test_round18_twin_is_byte_identical(sources):
    if "same_forecasts" not in sources.extra:
        pytest.skip("same_forecasts root not configured")
    p = Package(sources.path("same_forecasts_package", mi.ZIP))
    try:
        assert p.read_bytes(mi.F_CURVE) == sources.path("same_forecasts", "add16_intercept_curve_594.csv").read_bytes()
        assert p.read_bytes(mi.F_NETCON) == sources.path("same_forecasts", "add17_contrasts_594.csv").read_bytes()
    finally:
        p.close()


def test_build_check_and_png(tmp_path, payload):
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "sf_mean_input",
            "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img")]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
    png = tmp_path / "img" / "sf_mean_input.png"
    assert struct.unpack(">II", png.read_bytes()[16:24]) == (1200, 630) and png.stat().st_size <= 150_000
    assert (tmp_path / "data" / "sf_mean_input.json").stat().st_size <= 30_000
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0 and "sf_mean_input: unchanged" in res.stdout


def test_shipped_json_matches_fresh_build(payload):
    shipped = json.loads((WEB / "site" / "data" / "sf_mean_input.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(payload))
    for p in (shipped, fresh):
        p["meta"].pop("built_at", None)
    assert shipped == fresh
