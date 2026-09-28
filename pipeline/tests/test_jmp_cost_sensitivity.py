"""Published numbers for the JMP cost-sensitivity exhibit (SSRN v2 Figure 3, Table IV)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sources import load_sources
from exhibits import jmp_cost_sensitivity as ex

PIPELINE = Path(__file__).resolve().parents[1]
CONFIG = PIPELINE / "sources.toml"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="sources.toml not configured on this machine")


@pytest.fixture(scope="module")
def payload():
    return ex.build(load_sources(CONFIG))


def _series(payload, method, rep):
    (s,) = [s for s in payload["series"] if s["method"] == method and s["rep"] == rep]
    return s


def test_shape(payload):
    assert payload["bp"] == [0, 10, 25, 50, 100]
    assert payload["methods"] == ["Blocked ridge", "SR-weighted", "LOO ridge", "UPSA"]
    assert payload["reps"] == ["Original", "Balanced", "Value copies"]
    assert len(payload["series"]) == 12
    for s in payload["series"]:
        assert len(s["mean"]) == 5
        # only paper-plotted quantities are published (no net Sharpe ratios)
        assert "sharpe" not in s
        # costs only lower the mean
        assert all(a > b for a, b in zip(s["mean"], s["mean"][1:]))


@pytest.mark.parametrize("method,rep,gross_mean,mean25", [
    # Table IV, served PDF p. 27 (two decimals)
    ("Blocked ridge", "Original", 2.77, -0.63),
    ("Blocked ridge", "Balanced", 2.63, -0.95),
    ("Blocked ridge", "Value copies", 2.00, -1.28),
    ("SR-weighted", "Original", 3.66, 0.01),
    ("SR-weighted", "Balanced", 3.07, -0.67),
    ("SR-weighted", "Value copies", 2.91, -0.81),
    ("LOO ridge", "Original", 4.53, 0.68),
    ("LOO ridge", "Balanced", 4.78, 0.82),
    ("LOO ridge", "Value copies", 4.80, 1.06),
    ("UPSA", "Original", 4.79, 1.10),
    ("UPSA", "Balanced", 4.75, 0.92),
    ("UPSA", "Value copies", 5.07, 1.47),
])
def test_table_iv(payload, method, rep, gross_mean, mean25):
    s = _series(payload, method, rep)
    # The payload keeps 3 dp; the paper prints 2 dp rounded from 3 dp (e.g. 0.915 -> 0.92),
    # so a half-unit tolerance plus float slack is used.
    assert s["mean"][0] == pytest.approx(gross_mean, abs=0.0051)
    assert s["mean"][2] == pytest.approx(mean25, abs=0.0051)


def test_upsa_turnover(payload):
    # Table V, SSRN v2 p. 28: original UPSA trades 1.23 per dollar of NAV
    assert _series(payload, "UPSA", "Original")["turnover"] == pytest.approx(1.23, abs=0.005)


def test_meta_and_note(payload):
    meta = payload["meta"]
    assert meta["source_files"] == ["summary.csv"]
    assert "/" not in "".join(meta["source_files"])
    assert "SSRN" not in meta["exhibit"]
    assert meta["note"].startswith("The sample contains 179 monthly formation decisions")
    assert "borrow fees or market impact." in meta["note"]


def test_build_writes_json_and_png(tmp_path):
    cmd = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "jmp_cost_sensitivity",
           "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = tmp_path / "data" / "jmp_cost_sensitivity.json"
    assert out.stat().st_size < 20_000
    assert json.loads(out.read_text())["bp"] == [0, 10, 25, 50, 100]
    assert (tmp_path / "img" / "jmp_cost_sensitivity.png").exists()
