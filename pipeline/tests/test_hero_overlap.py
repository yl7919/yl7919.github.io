"""Tests of the hero_overlap exhibit (home Figure 1), mirroring test_hero_geometry.py.

Skipped when sources.toml is missing or its [roots] lacks `dynamic_geometry`.
"""
import inspect
import json
import re
import struct
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from sources import load_sources
from exhibits import hero_overlap as ho

PIPELINE = Path(__file__).resolve().parents[1]
CONFIG = PIPELINE / "sources.toml"


def _configured() -> bool:
    if not CONFIG.exists():
        return False
    with open(CONFIG, "rb") as fh:
        return "dynamic_geometry" in tomllib.load(fh).get("roots", {})


pytestmark = pytest.mark.skipif(not _configured(), reason="sources.toml has no dynamic_geometry root on this machine")

EN = ["Small size", "Illiquidity", "Low turnover", "Idiosyncratic volatility",
      "Distress", "Leverage", "Low profitability", "Young firms"]
ZH = ["小市值", "低流动性", "低换手率", "特质波动率", "财务困境", "杠杆", "低盈利", "年轻公司"]
IDS = ["size", "illiq", "turnover", "ivol", "distress", "leverage", "profit", "age"]
SIGNS = [-1, 1, -1, 1, 1, 1, -1, -1]
UPPER = [[i, j] for i in range(8) for j in range(i + 1, 8)]
FORBIDDEN = ("/Volumes", "Claude", "Sprint", "5A5", "bronze", "fragil", ".mat")


@pytest.fixture(scope="module")
def sources():
    return load_sources(CONFIG)


@pytest.fixture(scope="module")
def payload(sources):
    return ho.build(sources)


@pytest.fixture(scope="module")
def built(tmp_path_factory, payload):
    out = tmp_path_factory.mktemp("hero_overlap")
    data, img = out / "data", out / "img"
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "hero_overlap",
            "--data-dir", str(data), "--img-dir", str(img)]
    res = subprocess.run(base, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return base, data / "hero_overlap.json", img / "hero_overlap.png"


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", head[16:24])


def test_510_rows_and_axis(payload):
    months = payload["months"]
    assert len(months) == 510
    assert months[0] == "1983-06" and months[-1] == "2025-11" and months[309] == "2009-03"
    for key in ("corr", "avg_abs", "pd", "cond", "dim90"):
        assert len(payload[key]) == 510, key
    assert all(len(row) == 28 for row in payload["corr"])


def test_vars_and_pairs(payload):
    v = payload["vars"]
    assert [x["id"] for x in v] == IDS
    assert [x["en"] for x in v] == EN
    assert [x["zh"] for x in v] == ZH
    assert [x["sign"] for x in v] == SIGNS
    assert all(set(x) == set(ho.VAR_KEYS) for x in v), "vars[] carry only the seven named fields"
    assert all(isinstance(x["source"], str) and "/" not in x["source"] for x in v)
    assert payload["pairs"] == UPPER


def test_ranges_axes_and_medians(payload):
    meta = payload["meta"]
    assert meta["ranges"]["avg_abs"] == [0.238, 0.293]
    assert meta["ranges"]["pd"] == [21.66, 22.91]
    assert meta["ranges"]["cond"] == [2605, 7808]
    assert meta["ranges"]["dim90"] == [63, 66]
    assert meta["ranges"]["top_abs"] == [0.61, 0.93]
    assert meta["medians"]["pd"] == 22.55
    assert meta["medians"]["avg_abs"] == 0.283
    assert meta["axes"] == {"avg_abs": [0.20, 0.35], "pd": [20, 24]}
    for key in ("avg_abs", "pd"):
        lo, hi = meta["axes"][key]
        assert all(lo <= x <= hi for x in payload[key]), key


def test_top_pair_is_size_illiquidity_everywhere(payload):
    meta = payload["meta"]
    assert meta["top_vars"] == [0, 1] and meta["top_pair_index"] == 0
    for row in payload["corr"]:
        assert max(range(28), key=lambda k: abs(row[k])) == 0


def test_png_index_values(payload):
    assert payload["meta"]["png_index"] == 309
    assert round(payload["avg_abs"][309], 2) == 0.29
    assert payload["corr"][309][0] == 0.86
    assert round(payload["pd"][309], 1) == 22.5


def test_rounding_contract(payload, built):
    for row in payload["corr"]:
        assert all(round(x, 2) == x for x in row)
        assert all(not (x == 0 and str(x).startswith("-")) for x in row), "no -0.0 cell"
    assert all(round(x, 3) == x for x in payload["avg_abs"])
    assert all(round(x, 2) == x for x in payload["pd"])
    assert all(isinstance(x, int) for x in payload["cond"])
    assert all(isinstance(x, int) for x in payload["dim90"])
    _, out_json, _ = built
    text = out_json.read_text()
    # "-0.0" as a whole value (not the prefix of -0.07 and friends).
    assert not re.search(r"-0\.0(?![0-9])", text)
    for key in ("cond", "dim90"):
        block = re.search(rf'"{key}":\s*\[([^\]]*)\]', text).group(1)
        assert re.fullmatch(r"[0-9,\s]+", block), f"{key} must be written without decimal points"


def test_no_nber(payload):
    assert "nber" not in payload
    src = inspect.getsource(ho)
    assert "sources.geo(" not in src and "nber" not in src.lower()


def test_provenance(payload):
    meta = payload["meta"]
    assert meta["source_release"] == ho.SOURCE_NAME
    assert meta["source_files"] == ["T_DYNAMIC_GEOMETRY_METRICS.csv", "T_DYNAMIC_GEOMETRY_PAIR_CORRELATIONS.csv",
                                    "T_DYNAMIC_GEOMETRY_VARIABLE_MAP.csv"]
    assert all("/" not in f for f in meta["source_files"])
    assert "built_at" in meta
    assert meta["library"] == "JKP153" and meta["n_characteristics"] == 153
    assert meta["n_windows"] == 510 and meta["window_months"] == 240
    assert meta["first"] == "1983-06" and meta["last"] == "2025-11"


def test_no_local_paths_or_internal_names(built):
    _, out_json, _ = built
    text = out_json.read_text()
    for s in FORBIDDEN:
        assert s not in text, s


def test_json_budget_and_png(built):
    _, out_json, out_png = built
    assert out_json.stat().st_size <= 150_000
    assert out_png.stat().st_size <= 160_000
    assert _png_size(out_png) == (1600, 620)


def test_png_nothing_clipped_at_the_edges(built):
    """No ink may touch the outer 4 px on any side (a clipped footer once shipped on the old hero)."""
    from PIL import Image
    import numpy as np
    _, _, out_png = built
    with Image.open(out_png) as im:
        a = np.asarray(im.convert("L"))
    assert a.shape == (620, 1600)
    assert (a[:, -4:] == 255).all(), "ink in the last 4 columns"
    assert (a[:, :4] == 255).all(), "ink in the first 4 columns"
    assert (a[:4, :] == 255).all() and (a[-4:, :] == 255).all(), "ink in the top/bottom 4 rows"


def test_png_text_extents_inside_canvas(payload, tmp_path):
    """render_png itself must refuse a text that leaves the 1600x620 canvas."""
    ho.render_png(payload, tmp_path / "ok.png")
    import matplotlib.pyplot as plt
    orig = plt.figure

    def figure_with_overflow(*args, **kwargs):
        fig = orig(*args, **kwargs)
        fig.text(0.9, 0.5, "x" * 200, fontsize=9)
        return fig

    plt.figure = figure_with_overflow
    try:
        with pytest.raises(ValueError, match="outside the canvas"):
            ho.render_png(payload, tmp_path / "bad.png")
    finally:
        plt.figure = orig


def test_check_idempotent(built):
    base, _, _ = built
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "hero_overlap: unchanged" in res.stdout
