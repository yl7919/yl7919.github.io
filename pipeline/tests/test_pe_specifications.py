from pathlib import Path

import pytest

from sources import load_sources
from exhibits import pe_specifications as pe

CONFIG = Path(__file__).resolve().parents[1] / "sources.toml"
pytestmark = pytest.mark.skipif(not CONFIG.exists(), reason="sources.toml not configured on this machine")


@pytest.fixture(scope="module")
def payload():
    sources = load_sources(CONFIG)
    if "pricing_errors" not in sources.extra:
        pytest.skip("pricing_errors root not configured")
    return pe.build(sources)


def _spec(payload, window, k, train, ev):
    return next(s for s in payload["specs"] if (s["window"], s["k"], s["train"], s["eval"]) == (window, k, train, ev))


def test_twenty_four_specifications(payload):
    assert payload["n_specs"] == 24 and len(payload["specs"]) == 24
    assert payload["target_months"] == 93
    keys = {(s["window"], s["k"], s["train"], s["eval"]) for s in payload["specs"]}
    assert len(keys) == 24


def test_published_win_counts(payload):
    # Abstract and Section 6.3: 20 of 24 over the complete forecast, 8 over averaging, 6 over PC; 20 over whole-mean scaling.
    assert payload["wins"] == {"full": 20, "average": 8, "pc": 6, "whole": 20}


def test_selected_cells_match_table_g1(payload):
    s = _spec(payload, "Expanding", 3, "VW", "VW")
    assert s["gains"] == {"full": 0.1272, "whole": 1.2127, "pc": 0.0853, "average": 0.2086}
    s = _spec(payload, "Rolling 240", 1, "EW", "VW")
    assert s["gains"]["full"] == -0.4134 and s["gains"]["pc"] == -0.5973
    s = _spec(payload, "Expanding", 3, "VW", "EW")
    assert s["gains"]["full"] == -0.0001


def test_vw_vw_window_reversal(payload):
    # Section 6.3 / Figure 3: VW/VW gains over averaging 0.1513..0.2086 expanding, -0.1554..-0.0739 rolling.
    exp = [_spec(payload, "Expanding", k, "VW", "VW")["gains"] for k in (1, 3, 5)]
    rol = [_spec(payload, "Rolling 240", k, "VW", "VW")["gains"] for k in (1, 3, 5)]
    assert min(g["average"] for g in exp) == 0.1513 and max(g["average"] for g in exp) == 0.2086
    assert min(g["average"] for g in rol) == -0.1554 and max(g["average"] for g in rol) == -0.0739
    assert all(g["pc"] > 0 for g in exp) and all(g["pc"] < 0 for g in rol)


def test_meta_uses_basenames(payload):
    assert payload["meta"]["source_files"] == ["challenge_grid.tex", "challenge_numbers.tex"]
