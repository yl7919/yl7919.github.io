import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from sources import load_sources
from exhibits import hero_geometry as hg
from exhibits.portfolio_formation import EXPECTED_MONTHS

PIPELINE = Path(__file__).resolve().parents[1]
CONFIG = PIPELINE / "sources.toml"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="sources.toml not configured on this machine")

NBER_PAIRS = [[5, 21], [79, 85], [97, 113], [205, 213], [333, 341], [414, 432], [560, 562]]


@pytest.fixture(scope="module")
def sources():
    return load_sources(CONFIG)


@pytest.fixture(scope="module")
def payload(sources):
    return hg.build(sources)


@pytest.fixture(scope="module")
def built(tmp_path_factory, payload):
    out = tmp_path_factory.mktemp("hero")
    data, img = out / "data", out / "img"
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "hero_geometry",
            "--data-dir", str(data), "--img-dir", str(img)]
    res = subprocess.run(base, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return base, data / "hero_geometry.json", img / "hero_geometry.png"


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", head[16:24])


def test_618_rows_and_months(payload):
    assert payload["months"] == EXPECTED_MONTHS
    for key in ("pd", "share", "drift", "cond", "trace"):
        assert len(payload[key]) == 618, key


def test_ranges_and_medians(payload):
    meta = payload["meta"]
    assert meta["ranges"]["pd"] == [17.36, 22.63]
    assert meta["ranges"]["share"] == [0.1176, 0.1521]
    assert meta["medians"] == {"pd": 19.83, "share": 0.1424}
    assert min(payload["pd"]) == pytest.approx(17.36, abs=0.005)
    assert max(payload["pd"]) == pytest.approx(22.63, abs=0.005)


def test_rounding_contract(payload):
    assert payload["drift"][0] == 0.0
    assert all(x > 0 for x in payload["drift"][1:])
    assert all(round(x, 2) == x for x in payload["pd"])
    assert all(round(x, 4) == x for x in payload["share"])
    assert all(round(x, 5) == x for x in payload["drift"])
    assert all(float(x).is_integer() for x in payload["cond"])
    assert all(round(x, 1) == x for x in payload["trace"])


def test_seven_nber_bands(payload):
    assert payload["nber"] == NBER_PAIRS
    assert payload["months"][414] == "2007-12" and payload["months"][432] == "2009-06"
    assert payload["months"][hg.STRIP_INDEX] == "2009-03"


def test_provenance(payload):
    meta = payload["meta"]
    assert meta["source_release"] == "Characteristic_Geometry_and_Portfolio_Choice_Research_Release_2026-09-09"
    assert set(meta["source_files"]) == {"rolling_geometry.csv", "nber_monthly.csv"}
    assert all("/" not in f for f in meta["source_files"])
    assert "built_at" in meta


def test_metric_encoding_bounds(payload):
    r = payload["meta"]["ranges"]
    lam1, lam2 = hg.metric(r["pd"][0], r["share"][0], r)
    assert lam1 / lam2 == pytest.approx(1.4) and lam1 * lam2 == pytest.approx(0.85 ** 2)
    lam1, lam2 = hg.metric(r["pd"][1], r["share"][1], r)
    assert lam1 / lam2 == pytest.approx(4.0) and lam1 * lam2 == pytest.approx(1.15 ** 2)
    lam1, lam2 = hg.metric(-1e9, 1e9, r)
    assert lam1 / lam2 == pytest.approx(4.0) and lam1 * lam2 == pytest.approx(0.85 ** 2)


def test_json_budget_and_png(built):
    _, out_json, out_png = built
    assert out_json.stat().st_size <= 40_000
    assert out_png.stat().st_size <= 120_000
    assert _png_size(out_png) == (1600, 620)
    assert json.loads(out_json.read_text())["nber"] == NBER_PAIRS


def test_check_idempotent(built):
    base, _, _ = built
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "hero_geometry: unchanged" in res.stdout
