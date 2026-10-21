"""ruler_holdings: The Ruler Matters, Table IA.2 (p. 63), Figure IA.3 (p. 64), Table IA.41 (p. 112).

Pins the JSON to the paper's CSVs (exact floats) and to the printed tables (rounded strings). Skipped when
sources.toml or its `ruler_matters` root is missing.
"""
import csv
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from exhibits import ruler_holdings as rh
from sources import load_sources

from private_guards import banned_names

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"
FORBIDDEN = ("/Volumes", "/Users", "owner_package", "Claude") + banned_names()

# Table IA.2 (p. 63) as printed: loading-projection share, mean, volatility, turnover.
TABLE_IA2 = {
    ("bm", "plain"): ("46.10", "24.49", "181.03", "13.05"),
    ("bm", "characteristic"): ("0.00", "12.93", "83.09", "18.40"),
    ("mom", "plain"): ("53.51", "42.99", "251.31", "23.81"),
    ("mom", "characteristic"): ("0.00", "21.91", "93.30", "35.71"),
    ("size", "plain"): ("65.13", "9.23", "205.45", "9.87"),
    ("size", "characteristic"): ("0.00", "−8.54", "79.99", "26.52"),
}
# Table IA.41 (p. 112), "Unrestricted, 153" rows: mean gross, 95th gross, volatility, variance reduction, sign reversals.
TABLE_IA41 = {
    "bm": ("1.27", "1.42", "107.09", "65.00", 0),
    "mom": ("1.54", "1.73", "144.18", "67.09", 0),
    "size": ("1.86", "2.14", "147.65", "48.36", 0),
}


def _sources():
    if not CONFIG.exists():
        pytest.skip("sources.toml not configured on this machine")
    s = load_sources(CONFIG)
    if "ruler_matters" not in s.extra:
        pytest.skip("ruler_matters root not configured")
    return s


@pytest.fixture(scope="module")
def sources():
    return _sources()


@pytest.fixture(scope="module")
def payload(sources):
    return rh.build(sources)


def test_table_ia2_as_printed(payload):
    got = {(r["target"], r["ruler"]): tuple(r["printed"][k] for k in ("loading_share_pct", "mean_bp", "vol_bp", "turnover_pct"))
           for r in payload["unit_gross"]}
    assert got == TABLE_IA2


def test_headline_46_10_53_51_65_13(payload):
    # Section V.A, p. 24; pp. 5-6: the plain-ruler hedge leaves 46.10 / 53.51 / 65.13% in the loading space.
    assert payload["headline"]["plain_loading_share_pct"] == {"bm": "46.10", "mom": "53.51", "size": "65.13"}
    assert payload["headline"]["characteristic_loading_share_pct"] == {"bm": "0.00", "mom": "0.00", "size": "0.00"}
    for r in payload["unit_gross"]:
        if r["ruler"] == "characteristic":
            assert 0 <= r["loading_share_pct"] < 1e-20          # imposed restriction; the CSV carries ~1e-26


def test_matched_tilt_as_printed(payload):
    got = {r["target"]: (r["printed"]["mean_gross"], r["printed"]["gross_p95"], r["printed"]["vol_bp"],
                         r["printed"]["variance_reduction_pct"], r["sign_flips"]) for r in payload["matched_tilt"]}
    assert got == TABLE_IA41


def test_values_are_the_csv_floats(payload, sources):
    with open(sources.path("ruler_matters", rh.F_HOLD), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    tmap = {c: t for t, c, *_ in rh.TARGETS}
    rmap = {c: r for r, c, *_ in rh.RULERS}
    by = {(r["target"], r["ruler"]): r for r in payload["unit_gross"]}
    for row in rows:
        r = by[(tmap[row["Target"]], rmap[row["Projection"]])]
        assert r["loading_share_pct"] == float(row["Loading share"])
        assert r["mean_bp"] == float(row["Mean (bp)"]) and r["vol_bp"] == float(row["Vol. (bp)"])
        assert r["turnover_pct"] == float(row["Turnover"])


def test_shape_and_labels(payload):
    assert [t["id"] for t in payload["targets"]] == ["bm", "mom", "size"]
    assert [r["id"] for r in payload["rulers"]] == ["plain", "characteristic"]
    assert {r["palette_key"] for r in payload["rulers"]} == {"ipca", "qz_ipca"}
    assert len(payload["unit_gross"]) == 6 and len(payload["matched_tilt"]) == 3
    assert payload["targets"][2]["label"] == "Larger-firm size"      # p. 9: larger-firm size, not SMB


def test_provenance_and_locators(payload):
    meta = payload["meta"]
    assert meta["source_files"] == ["holdings.csv", "matched_holdings.csv"]
    assert meta["source_release"].startswith("The Ruler Matters: Factor Exposures, Attribution, and Portfolio Risk")
    assert meta["locators"]["unit_gross"] == "Table IA.2, p. 63"
    assert "Table IA.41, p. 112" in meta["locators"]["matched_tilt"]
    text = json.dumps(payload, ensure_ascii=False)
    assert not any(f in text for f in FORBIDDEN)


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", head[16:24])


def test_build_check_and_png(tmp_path, payload):
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "ruler_holdings",
            "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img")]
    res = subprocess.run(base, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out_json, out_png = tmp_path / "data" / "ruler_holdings.json", tmp_path / "img" / "ruler_holdings.png"
    assert out_json.stat().st_size <= 20_000
    assert _png_size(out_png) == (1200, 630) and out_png.stat().st_size <= 150_000
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0 and "ruler_holdings: unchanged" in res.stdout


def test_shipped_json_matches_fresh_build(payload):
    shipped = json.loads((WEB / "site" / "data" / "ruler_holdings.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(payload))
    for p in (shipped, fresh):
        p["meta"].pop("built_at", None)
    assert shipped == fresh
