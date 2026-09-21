import math
import numpy as np
import pytest

from common import (
    PIPELINE_VERSION,
    annual_return,
    annual_vol,
    break_even_bp,
    max_drawdown,
    net_returns,
    provenance,
    round_list,
    round_sig,
    sharpe,
    write_json,
)


def test_sharpe_matches_release_definition():
    r = np.array([0.01, -0.02, 0.03, 0.00, 0.015])
    expected = r.mean() * 12 / (r.std(ddof=1) * math.sqrt(12))
    assert sharpe(r) == pytest.approx(expected)


def test_sharpe_zero_vol_is_nan():
    assert math.isnan(sharpe(np.array([0.01, 0.01, 0.01])))


def test_net_returns_subtracts_cost_per_traded_dollar():
    r = np.array([0.01, 0.02])
    to = np.array([0.5, 0.25])
    np.testing.assert_allclose(net_returns(r, to, 10), [0.01 - 0.0005, 0.02 - 0.00025])


def test_max_drawdown_from_wealth_path():
    r = np.array([0.10, -0.50, 0.20])  # wealth 1.1, 0.55, 0.66 -> dd = 0.55/1.1 - 1
    assert max_drawdown(r) == pytest.approx(-0.5)


def test_break_even_is_first_bp_with_nonpositive_sharpe():
    r = np.array([0.001, 0.002, 0.0015, 0.001, 0.002, 0.0015])
    to = np.ones(6)  # 1 dollar traded each month
    # mean r = 0.0015; sharpe <= 0 once bp/1e4 >= 0.0015 -> bp = 15
    assert break_even_bp(r, to) == 15


def test_break_even_returns_nan_when_never_crossing():
    r = np.array([0.5, 0.6, 0.55])
    to = np.zeros(3)
    assert math.isnan(break_even_bp(r, to))


def test_annual_return_and_vol():
    r = np.array([0.01, 0.02, 0.03])
    assert annual_return(r) == pytest.approx(0.02 * 12)
    assert annual_vol(r) == pytest.approx(r.std(ddof=1) * math.sqrt(12))


def test_round_sig_six_digits():
    assert round_sig(0.123456789) == 0.123457
    assert round_sig(-1234.56789) == -1234.57
    assert round_sig(0.0) == 0.0


def test_empty_inputs_return_nan():
    assert math.isnan(max_drawdown(np.array([])))
    assert math.isnan(sharpe(np.array([])))


def test_round_list_rounds_each_element():
    assert round_list([0.123456789, 2.0, -0.000123456789]) == [0.123457, 2.0, -0.000123457]


def test_provenance_fields(tmp_path):
    p = provenance([tmp_path / "a.csv"], "release-x")
    assert p["source_release"] == "release-x"
    assert p["source_files"] == ["a.csv"]
    assert p["pipeline_version"] == PIPELINE_VERSION
    assert p["built_at"].endswith("Z") and len(p["built_at"]) == 20


def test_write_json_round_trip_and_rejects_nan(tmp_path):
    out = tmp_path / "nested" / "x.json"
    write_json(out, {"b": [1, 2], "a": 1.5})
    text = out.read_text(encoding="utf-8")
    assert text == '{"a":1.5,"b":[1,2]}\n'
    with pytest.raises(ValueError):
        write_json(tmp_path / "bad.json", {"x": float("nan")})
