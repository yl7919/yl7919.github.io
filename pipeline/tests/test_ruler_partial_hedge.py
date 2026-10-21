"""ruler_partial_hedge: The Ruler Matters, Table VII (p. 46), Figure 9 (p. 45), Table IA.48 (p. 118).

Skipped when sources.toml or its `ruler_matters` root is missing.
"""
import csv
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from exhibits import ruler_partial_hedge as rp
from sources import load_sources

from private_guards import banned_names

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"
FORBIDDEN = ("/Volumes", "/Users", "owner_package", "Claude") + banned_names()

# Table VII (p. 46) as printed: exposure retained, volatility, turnover, matched gross, matched volatility.
TABLE_VII = {
    ("bm", 0): ("100.00", "191.98", "10.92", "1.00", "191.98"),
    ("bm", 50): ("94.62", "143.32", "12.95", "1.06", "152.47"),
    ("bm", 100): ("75.80", "83.09", "18.40", "1.32", "112.47"),
    ("mom", 0): ("100.00", "262.05", "21.04", "1.00", "262.05"),
    ("mom", 50): ("93.54", "205.60", "25.74", "1.07", "218.64"),
    ("mom", 100): ("62.05", "93.30", "35.71", "1.62", "151.25"),
    ("size", 0): ("100.00", "231.41", "7.73", "1.00", "231.41"),
    ("size", 50): ("95.61", "186.43", "12.28", "1.05", "195.34"),
    ("size", 100): ("52.34", "79.99", "26.52", "1.92", "152.12"),
}
# Table IA.48 (p. 118): full hedge at the original tilt minus unhedged volatility, with pointwise 95% intervals.
TABLE_IA48 = {
    "bm": ("−79.52", "−129.40", "−36.63"),
    "size": ("−79.29", "−116.35", "−34.56"),
    "mom": ("−110.80", "−174.68", "−45.02"),
}
KEYS = ("exposure_retained_pct", "vol_bp", "turnover_pct", "matched_gross", "matched_vol_bp")


@pytest.fixture(scope="module")
def sources():
    if not CONFIG.exists():
        pytest.skip("sources.toml not configured on this machine")
    s = load_sources(CONFIG)
    if "ruler_matters" not in s.extra:
        pytest.skip("ruler_matters root not configured")
    return s


@pytest.fixture(scope="module")
def payload(sources):
    return rp.build(sources)


def test_three_csv_backed_stops(payload):
    assert payload["fractions"] == [0, 50, 100]
    assert payload["meta"]["missing_fractions"] == [25, 75]     # Figure 9 plots them; no data table carries them
    assert len(payload["rows"]) == 9


def test_table_vii_as_printed(payload):
    got = {(r["target"], r["hedge_pct"]): tuple(r["printed"][k] for k in KEYS) for r in payload["rows"]}
    assert got == TABLE_VII


def test_headline_tilt_and_risk(payload):
    # Section IX.A (pp. 43-44): book-to-market keeps 94.62% at 50% and 75.80% at 100%, volatility 191.98 -> 143.32 -> 83.09 bp;
    # restoring the tilt under full hedging needs gross 1.32 / 1.62 / 1.92.
    full = {r["target"]: r["printed"] for r in payload["rows"] if r["hedge_pct"] == 100}
    assert [full[t]["matched_gross"] for t in ("bm", "mom", "size")] == ["1.32", "1.62", "1.92"]
    assert [full[t]["exposure_retained_pct"] for t in ("bm", "mom", "size")] == ["75.80", "62.05", "52.34"]


def test_full_hedge_change_as_printed(payload):
    got = {r["target"]: (r["printed"]["change_bp"], r["printed"]["lo"], r["printed"]["hi"]) for r in payload["full_hedge_change"]}
    assert got == TABLE_IA48
    assert all(r["hi"] < 0 for r in payload["full_hedge_change"])          # p. 44: the three intervals exclude zero


def test_values_are_the_csv_floats(payload, sources):
    with open(sources.path("ruler_matters", rp.F_PARTIAL), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    tmap = {c: t for t, c, *_ in rp.TARGETS}
    by = {(r["target"], r["hedge_pct"]): r for r in payload["rows"]}
    for row in rows:
        r = by[(tmap[row["Target"]], int(float(row["Hedge (\\%)"])))]
        assert r["vol_bp"] == float(row["Vol. (bp)"]) and r["matched_gross"] == float(row["Matched gross"])
        assert r["exposure_retained_pct"] == float(row["Exposure (\\%)"])


def test_provenance(payload):
    meta = payload["meta"]
    assert meta["source_files"] == ["partial_hedging.csv", "partial_intervals.csv"]
    assert meta["locators"]["table"] == "Table VII, p. 46" and meta["locators"]["figure"] == "Figure 9, p. 45"
    assert meta["locators"]["full_hedge_change"] == "Table IA.48, p. 118"
    assert not any(f in json.dumps(payload, ensure_ascii=False) for f in FORBIDDEN)


def test_build_check_and_png(tmp_path, payload):
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "ruler_partial_hedge",
            "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img")]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
    png = tmp_path / "img" / "ruler_partial_hedge.png"
    assert struct.unpack(">II", png.read_bytes()[16:24]) == (1200, 630) and png.stat().st_size <= 150_000
    assert (tmp_path / "data" / "ruler_partial_hedge.json").stat().st_size <= 20_000
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0 and "ruler_partial_hedge: unchanged" in res.stdout


def test_shipped_json_matches_fresh_build(payload):
    shipped = json.loads((WEB / "site" / "data" / "ruler_partial_hedge.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(payload))
    for p in (shipped, fresh):
        p["meta"].pop("built_at", None)
    assert shipped == fresh
