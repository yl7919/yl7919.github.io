import json
import subprocess
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="sources.toml not configured on this machine")


def test_build_writes_json_and_png(tmp_path: Path):
    out_json = tmp_path / "data" / "portfolio_formation.json"
    out_png = tmp_path / "img" / "portfolio_formation.png"
    cmd = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "portfolio_formation",
           "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert out_json.exists() and out_png.exists()
    assert out_json.stat().st_size <= 300_000
    payload = json.loads(out_json.read_text())
    assert "meta" in payload and "cross_model" in payload


def test_check_mode_passes_when_unchanged(tmp_path: Path):
    data = tmp_path / "data"
    img = tmp_path / "img"
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "portfolio_formation",
            "--data-dir", str(data), "--img-dir", str(img)]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_check_mode_fails_when_json_differs(tmp_path: Path):
    data = tmp_path / "data"
    img = tmp_path / "img"
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "portfolio_formation",
            "--data-dir", str(data), "--img-dir", str(img)]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
    (data / "portfolio_formation.json").write_text("{}")
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 1
    assert "differs" in res.stderr
