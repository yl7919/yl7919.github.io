"""Runs the headless deno smoke test of site/assets/js/hero.js (tests/js/hero_test.js).

Uses a deno on PATH, else the one bundled with Quarto (resolved from the `quarto` executable);
skips when neither exists.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2]
TEST = Path(__file__).resolve().parent / "js" / "hero_test.js"


def find_deno() -> str | None:
    if found := shutil.which("deno"):
        return found
    quarto = shutil.which("quarto")
    if quarto:
        tools = Path(os.path.realpath(quarto)).parent / "tools"
        for cand in sorted(tools.glob("*/deno")) + [tools / "deno"]:
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand)
    return None


def test_hero_js_smoke():
    deno = find_deno()
    if deno is None:
        pytest.skip("deno not available (install Quarto or deno)")
    env = {**os.environ, "NO_COLOR": "1", "DENO_NO_UPDATE_CHECK": "1"}
    r = subprocess.run([deno, "test", "--allow-read", str(TEST)], cwd=WEB, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
