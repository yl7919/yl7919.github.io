"""Tests of the return_state exhibit (Return-State Behavior Profile capability page).

Skipped when pipeline/sources.toml is missing or its [roots] has no existing `return_state` directory.
"""
import copy
import html
import json
import math
import re
import shutil
import subprocess
import sys
import tomllib
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sources import load_sources
from exhibits import return_state as rs

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"


def _root() -> Path | None:
    if not CONFIG.exists():
        return None
    with open(CONFIG, "rb") as fh:
        raw = tomllib.load(fh).get("roots", {}).get("return_state")
    return Path(raw) if raw and Path(raw).is_dir() else None


pytestmark = pytest.mark.skipif(_root() is None, reason="sources.toml has no return_state root on this machine")

# Source audit anchors: default state counts and the stored radar table's raw values.
ANCHOR_N = {"normal": 178, "rally": 23, "recovery": 50, "downside": 23, "tail": 12}
ANCHOR_STREAM = [0.01255312, 0.02462544, 0.01554381, 0.20026449, 0.02280973, 17 / 23, 0.02723764, 0.75]
ANCHOR_BENCH = [0.01216236, 0.08386087, 0.05179600, 1.0, -0.08266957, 0.0, -0.09850833, 0.0]
FORBIDDEN = ("/Volumes", "/Users", "Sprint", "5A5", ".zip", "Claude", "P12", "T_P12")
STREAM_IDS = ["strategy_net", "strategy_gross", "proxy_60_40", "proxy_plus_5", "proxy_cash_5",
              "proxy_plus_10", "proxy_cash_10"]


@pytest.fixture(scope="module")
def sources():
    return load_sources(CONFIG)


@pytest.fixture(scope="module")
def payload(sources):
    return rs.build(sources)


@pytest.fixture(scope="module")
def frame():
    return rs.load_and_validate(_root() / rs.F_STREAM)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("return_state")
    data, img, site = out / "data", out / "img", out / "site"
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "return_state",
            "--data-dir", str(data), "--img-dir", str(img), "--site-dir", str(site)]
    res = subprocess.run(base, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return base, data / "return_state.json", img / "return_state.png", site


def _key(stream="strategy_net", definition="d10", window="full"):
    return f"{stream}|{definition}|{window}"


# ------------------------------------------------------------------------------------- ingest/validate

def test_sample_and_validation(frame, payload):
    assert len(frame) == 224
    assert frame["month"].iloc[0] == "2007-04" and frame["month"].iloc[-1] == "2025-11"
    assert frame["month"].is_unique and frame["month"].is_monotonic_increasing
    meta = payload["meta"]
    assert (meta["sample_start"], meta["sample_end"], meta["n_months"]) == ("2007-04", "2025-11", 224)
    assert set(meta["source_sha256"]) == {"archived monthly return table", "archived radar table"}
    assert meta["source_files"] == ["archived monthly return table", "archived radar table"]
    assert all(len(h) == 64 for h in meta["source_sha256"].values())
    # Every copy of the results that travels without the page says what kind of record it is.
    assert meta["record_type"] == {"en": "Archived backtest: not actual trading, not audited",
                                   "zh": "存档回测：不是实际交易，未经审计"}
    assert "not a privacy guarantee" in meta["disclosure"]["en"] and "并非隐私保证" in meta["disclosure"]["zh"]


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.assign(strategy_ret=d["strategy_ret"] * 100), "decimals"),
    (lambda d: pd.concat([d.iloc[:5], d.iloc[4:5], d.iloc[5:]]).reset_index(drop=True), "rows|sorted"),
    (lambda d: d.assign(gross_ret=d["gross_ret"].where(d.index != 7)), "missing values"),
    (lambda d: d.iloc[::-1].reset_index(drop=True), "sorted"),
])
def test_validation_rejects_bad_input(tmp_path, mutate, message):
    src = pd.read_csv(_root() / rs.F_STREAM)
    bad = mutate(src)
    p = tmp_path / "bad.csv"
    bad.to_csv(p, index=False)
    with pytest.raises(ValueError, match=message):
        rs.load_and_validate(p)


# ------------------------------------------------------------------------------------- archive parity

def test_archive_parity_to_1e8(payload):
    stored = pd.read_csv(_root() / rs.F_RADAR)
    assert len(stored) == 16
    res = payload["results"][_key()]
    bench = payload["states"]["d10|full"]["bench"]
    for who, prof in (("Regime-Aware Alpha Strategy", res), ("U.S. equity market", bench)):
        for i, dim in enumerate(rs.ARCHIVE_DIMENSIONS):
            row = stored[(stored["series"] == who) & (stored["dimension"] == dim)].iloc[0]
            assert abs(prof["raw"][i] - row["raw_value"]) < 1e-8, (who, dim)
            assert abs(prof["score"][i] - row["score"]) < 1e-8, (who, dim)
    parity = payload["meta"]["parity"]
    assert parity["rows"] == 16 and parity["max_raw_delta"] < 1e-8 and parity["max_score_delta"] < 1e-8


def test_state_counts_default(payload):
    st = payload["states"]["d10|full"]
    assert st["n"] == ANCHOR_N
    assert st["n_months"] == 224


def test_eight_raw_values(payload):
    res = payload["results"][_key()]
    bench = payload["states"]["d10|full"]["bench"]
    assert np.allclose(res["raw"], ANCHOR_STREAM, atol=5e-9)
    assert np.allclose(bench["raw"], ANCHOR_BENCH, atol=5e-9)
    assert res["pos"] == {"downside": 17, "tail": 9}
    assert bench["pos"] == {"downside": 0, "tail": 0}


def test_normalisation_formulas():
    assert rs.score("ret", 0.0) == 0.5 and rs.score("ret", -0.06) == 0.0 and rs.score("ret", 0.07) == 1.0
    assert rs.score("beta", 1.0) == 0.25 and rs.score("beta", -0.5) == 1.0 and rs.score("beta", 2.0) == 0.0
    assert rs.score("freq", 0.75) == 0.75
    assert rs.score("ret", None) is None


# ------------------------------------------------------------------------------------- variants

def test_variant_counts(payload):
    s = payload["states"]
    assert s["q20|full"]["n"] == {"normal": 134, "rally": 45, "recovery": 50, "downside": 45, "tail": 23}
    assert s["dd10|full"]["n"] == {"normal": 178, "rally": 23, "recovery": 33, "downside": 23, "tail": 12}
    # Full sample only (half windows failed the disclosure test): 3 state tables, 7 x 3 = 21 profiles.
    assert len(s) == 3 and len(payload["results"]) == 21
    assert [w["id"] for w in payload["windows"]] == ["full"]
    assert not any(k.endswith(("|first", "|second")) for k in list(s) + list(payload["results"]))


def test_variants_change_results(payload):
    """Each control selects a genuinely different computed result (no relabelled numbers)."""
    r = payload["results"]
    base = r[_key()]["raw"]
    for other in [_key(stream=i) for i in STREAM_IDS[1:]] + [_key(definition="q20"), _key(definition="dd10")]:
        assert r[other]["raw"] != base, other
    # All 21 results are distinct.
    assert len({json.dumps(v["raw"]) for v in r.values()}) == 21
    # The recovery-threshold variant changes only the recovery spoke for the same months and percentiles.
    dd = r[_key(definition="dd10")]["raw"]
    assert dd[2] != base[2] and [v for i, v in enumerate(dd) if i != 2] == [v for i, v in enumerate(base) if i != 2]


def test_states_defined_by_benchmark_not_stream(payload, frame):
    """Masks come from the benchmark only: a stream's tail mean equals a direct recomputation on benchmark tail months."""
    m = frame[rs.BENCH_COLUMN]
    tail = m <= m.quantile(0.05)
    for s in rs.STREAMS:
        direct = float(frame.loc[tail, s["column"]].mean())
        assert abs(payload["results"][_key(stream=s["id"])]["raw"][6] - direct) < 1e-9, s["id"]


def test_sixty_forty_proxy_downside_beta(payload):
    """Built-in check: 60% equity + 40% cash has a downside beta of about 0.6 by construction."""
    beta = payload["results"][_key(stream="proxy_60_40")]["raw"][3]
    assert abs(beta - 0.6) < 0.01


def test_small_n_flag(payload):
    assert payload["meta"]["small_n"] == 15
    assert payload["states"]["d10|full"]["n"]["tail"] < payload["meta"]["small_n"]


def test_streams_offered_exclude_unmatched_factors(payload):
    ids = [s["id"] for s in payload["streams"]]
    assert ids == STREAM_IDS
    text = json.dumps(payload)
    for col in rs.EXCLUDED_COLUMNS:
        assert f'"{col}"' not in text


# ------------------------------------------------------------------------------------- publication guards

def _numbers(obj):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield float(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _numbers(v)


def _lists(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _lists(v)
    elif isinstance(obj, list):
        yield obj
        for v in obj:
            yield from _lists(v)


def test_json_holds_aggregates_only(built, frame):
    """No monthly series: no array longer than the eight metrics, no date list, and no monthly value of any stream."""
    _, out_json, _, _ = built
    payload = json.loads(out_json.read_text())
    assert max(len(x) for x in _lists(payload)) <= 8
    text = out_json.read_text()
    for key in ('"months"', '"dates"', '"series"', '"returns"', '"strategy_ret"', '"gross_ret"', "target_yyyymm"):
        assert key not in text, key
    published = {round(x, 8) for x in _numbers(payload)}
    # The restricted columns are those that contain the archived strategy. The benchmark and the 60/40
    # equity-cash proxy are built from public Fama-French data; a percentile threshold may legitimately
    # equal one benchmark month (and once, by coincidence, a 60/40 proxy month).
    for col in ("strategy_ret", "gross_ret", "proxy_plus_5_strategy", "proxy_plus_10_strategy"):
        monthly = {round(float(v), 8) for v in frame[col] if abs(v) > 1e-6}
        leaked = monthly & published
        assert not leaked, (col, sorted(leaked)[:5])


def test_no_local_paths_or_internal_names(built):
    _, out_json, _, site = built
    texts = [out_json.read_text()] + [p.read_text() for p in (site / "projects").glob("_tbl-return-state*.md")]
    for text in texts:
        for s in FORBIDDEN:
            assert s not in text, s


def test_determinism(sources):
    from build_data import _stable
    a, b = rs.build(sources), rs.build(sources)
    assert _stable(a) == _stable(b)


def test_committed_json_and_tables_current(payload):
    """The committed site files match a fresh build (build_data --check covers the EN table; this covers ZH too)."""
    from build_data import _stable
    committed = WEB / "site" / "data" / "return_state.json"
    assert committed.exists()
    assert _stable(json.loads(committed.read_text())) == _stable(payload)
    assert (WEB / "site" / rs.TABLE_PATH).read_text(encoding="utf-8") == rs.table_markdown(payload)
    assert (WEB / "site" / rs.TABLE_PATH_ZH).read_text(encoding="utf-8") == rs.table_markdown_zh(payload)


def test_tables_content(payload):
    en, zh = rs.table_markdown(payload), rs.table_markdown_zh(payload)
    assert "| Upside Participation | Strong rally (23) | 2.46% | −0.57% to 5.50% | 8.39% | 0.75 / 1.00‡ |" in en
    assert "| Downside Beta | Downside (23) | 0.20 | −0.47 to 0.87 | 1.00§ | 0.65 / 0.25 |" in en
    assert "| Tail Reliability | Tail (12)† | 9/12 (75.0%) | 42.8% to 94.5% | 0/12 (0.0%)§ | 0.75 / 0.00 |" in en
    assert "| 尾部期正收益频率 | 尾部（12）† | 9/12（75.0%） | 42.8% 至 94.5% | 0/12（0.0%）§ | 0.75 / 0.00 |" in zh
    assert "| *All months: mean return* | All months (224) | 1.48% | 0.94% to 2.03% | 0.98% | — |" in en
    assert "4 of the 16 scores" in en and "16 个得分中有 4 个" in zh
    assert "Apr 2007 – Nov 2025" in en and "2007 年 4 月至 2025 年 11 月" in zh
    assert "Data: archived backtest (not actual trading, not audited), monthly" in en
    assert "数据：存档回测（不是实际交易，未经审计）" in zh
    # EN and ZH carry the same numbers.
    num = lambda s: sorted(__import__("re").findall(r"−?\d+\.\d+%?", s))
    assert num(en) == num(zh)


def test_build_check_png_and_size(built):
    base, out_json, out_png, site = built
    assert out_json.stat().st_size <= 60_000
    assert out_png.exists() and out_png.stat().st_size <= 200_000
    assert (site / rs.TABLE_PATH).exists() and (site / rs.TABLE_PATH_ZH).exists()
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "return_state: unchanged" in res.stdout and "return_state: table unchanged" in res.stdout


# ------------------------------------------------------------------------------------- intervals, flags, disclosure

def test_t_and_clopper_pearson_reference_values():
    """Reference values (scipy.stats.t.ppf / beta.ppf), so the numpy-only implementation is checked."""
    assert abs(rs.t_ppf(0.975, 22) - 2.073873068) < 1e-7
    assert abs(rs.t_ppf(0.975, 11) - 2.200985160) < 1e-7
    assert abs(rs.t_ppf(0.975, 223) - 1.970658961) < 1e-7
    lo, hi = rs.clopper_pearson(9, 12)
    assert abs(lo - 0.428138) < 1e-5 and abs(hi - 0.945139) < 1e-5
    lo, hi = rs.clopper_pearson(17, 23)
    assert abs(lo - 0.515948) < 1e-5 and abs(hi - 0.897714) < 1e-5
    assert rs.clopper_pearson(0, 12)[0] == 0.0 and rs.clopper_pearson(12, 12)[1] == 1.0


def test_default_intervals(payload, frame):
    """Sampling intervals of the default view: SE s/sqrt(n) and t-intervals for means, the OLS slope SE for
    downside beta, Clopper-Pearson for hit frequencies (values recomputed directly here)."""
    res = payload["results"][_key()]
    m, x = frame[rs.BENCH_COLUMN].to_numpy(float), frame["strategy_ret"].to_numpy(float)
    dn = m <= np.quantile(m, 0.10)
    tl = m <= np.quantile(m, 0.05)
    # Downside beta 0.20: SE about 0.32, 95% interval about -0.47 to 0.87 (n = 23).
    X = np.column_stack([np.ones(dn.sum()), m[dn]])
    coef, rss = np.linalg.lstsq(X, x[dn], rcond=None)[:2]
    se = math.sqrt(rss[0] / (dn.sum() - 2) / ((m[dn] - m[dn].mean()) ** 2).sum())
    assert abs(res["raw"][3] - coef[1]) < 1e-9 and abs(res["se"][3] - se) < 1e-9
    assert abs(res["ci"][3][0] - (-0.4654)) < 1e-4 and abs(res["ci"][3][1] - 0.8659) < 1e-4
    # Tail mean 2.72% a month: SE 1.28%.
    assert abs(res["se"][6] - x[tl].std(ddof=1) / math.sqrt(tl.sum())) < 1e-9
    assert abs(res["se"][6] - 0.0128) < 5e-5
    # Hit frequencies: 17/23 and 9/12.
    assert np.allclose(res["ci"][5], [0.515948, 0.897714], atol=1e-5)
    assert np.allclose(res["ci"][7], [0.428138, 0.945139], atol=1e-5)
    for i, (lo, hi) in enumerate(res["ci"]):
        assert lo <= res["raw"][i] <= hi
    assert res["se"][5] is None and res["se"][7] is None


def test_reference_row(payload, frame):
    """All-months reference: unconditional mean, full-window beta on the benchmark, share positive."""
    a = payload["results"][_key()]["all"]
    x, m = frame["strategy_ret"].to_numpy(float), frame[rs.BENCH_COLUMN].to_numpy(float)
    assert a["n"] == 224 and a["pos"] == int((x > 0).sum())
    assert abs(a["raw"][0] - x.mean()) < 1e-9
    assert abs(a["raw"][1] - np.cov(x, m, ddof=1)[0, 1] / np.var(m, ddof=1)) < 1e-9
    assert abs(a["raw"][1]) < 0.01      # the long-short stream has about zero full-sample beta
    b = payload["states"]["d10|full"]["bench"]["all"]
    assert b["raw"][1] == 1.0


def test_clip_flags(payload):
    """A score is flagged as clipped exactly when the unclipped transform falls outside [0, 1]."""
    count = 0
    for prof in list(payload["results"].values()) + [s["bench"] for s in payload["states"].values()]:
        for m, raw, sc, clip in zip(rs.METRICS, prof["raw"], prof["score"], prof["clipped"]):
            u = rs.score_unclipped(m[5], raw)
            assert clip == (u < 0 or u > 1)
            if clip:
                assert sc in (0.0, 1.0)
                count += 1
    assert count > 0
    bench = payload["states"]["d10|full"]["bench"]
    assert bench["clipped"] == [False, True, True, False, True, False, True, False]
    assert payload["results"][_key()]["clipped"] == [False] * 8


def test_benchmark_by_construction(payload):
    """On the five downside/tail spokes the benchmark's values are set by the state definition."""
    flagged = [m["id"] for m in payload["metrics"] if m["bench_by_construction"]]
    assert flagged == ["downside_beta", "downside_reactivity", "downside_reliability", "tail_reactivity",
                       "tail_reliability"]
    for key, st in payload["states"].items():
        b, thr = st["bench"], st["thresholds"]
        assert abs(b["raw"][3] - 1.0) < 1e-12
        assert b["raw"][4] <= thr["lower"] < 0 and b["raw"][6] <= thr["tail"] < 0
        assert b["raw"][5] == 0.0 and b["raw"][7] == 0.0


def test_dilution_references(payload, frame):
    """The dilution-only references are public blends (proxy + cash, no strategy): a sleeve's change in
    downside beta can be split into dilution and strategy effects."""
    r = payload["results"]
    for w, sleeve, ref in ((0.05, "proxy_plus_5", "proxy_cash_5"), (0.10, "proxy_plus_10", "proxy_cash_10")):
        proxy_beta = r[_key(stream="proxy_60_40")]["raw"][3]
        # Equity weight falls to 0.6 (1 - w); the cash leg co-moves a little with the market, hence 1e-3.
        assert abs(r[_key(stream=ref)]["raw"][3] - (1 - w) * proxy_beta) < 1e-3
        y = (1 - w) * frame["equity_cash_60_40_proxy"] + w * frame["cash"]
        m = frame[rs.BENCH_COLUMN]
        dn = m <= m.quantile(0.10)
        assert abs(r[_key(stream=ref)]["raw"][3] - np.cov(y[dn], m[dn], ddof=1)[0, 1] / np.var(m[dn], ddof=1)) < 1e-9
        # Strategy effect = sleeve minus dilution reference: positive here (the sleeve adds downside beta).
        assert r[_key(stream=sleeve)]["raw"][3] > r[_key(stream=ref)]["raw"][3]
    kinds = {s["id"]: s["kind"] for s in payload["streams"]}
    assert kinds["proxy_cash_5"] == kinds["proxy_cash_10"] == kinds["proxy_60_40"] == "public"


def _leverage(rows):
    A = np.array(rows)
    return float(np.diag(np.linalg.pinv(A) @ A).max())


def test_no_month_recoverable(payload, frame):
    """Differencing attack: stack every published linear functional of a restricted stream x (n x mean per
    state, the downside-beta numerator sum((m - mean m) x) on downside months, the all-months sum and beta
    numerator) for every published (definition, window), with masks rebuilt independently by rs.state_masks
    from the public benchmark; then also the sums of squares implied by the standard errors. No month may
    have projector leverage diag(pinv(A) A) at or above LEVERAGE_MAX. Adding half-sample windows drives the
    leverage to 1 (a month exactly solvable); the full sample alone stays below the limit."""
    m = frame[rs.BENCH_COLUMN].astype(float).reset_index(drop=True)
    dd = rs.benchmark_drawdown(m)
    months = frame["month"].reset_index(drop=True)
    T = len(m)
    lin, sq = [], []
    for key in payload["states"]:
        did, wid = key.split("|")
        d = next(x for x in rs.DEFINITIONS if x["id"] == did)
        w = next(x for x in payload["windows"] if x["id"] == wid)
        sel = ((months >= w["start"]) & (months <= w["end"])).to_numpy()
        masks, _ = rs.state_masks(m[sel], dd[sel], dd.shift(1)[sel], d)
        idx = np.where(sel)[0]
        for state in rs.STATES:
            ind = np.zeros(T)
            ind[idx[masks[state].to_numpy()]] = 1
            lin.append(ind); sq.append(ind)
        mv = m.to_numpy()
        dn = idx[masks["downside"].to_numpy()]
        r = np.zeros(T); r[dn] = mv[dn] - mv[dn].mean(); lin.append(r)
        a = np.zeros(T); a[idx] = 1; lin.append(a); sq.append(a)
        r = np.zeros(T); r[idx] = mv[idx] - mv[idx].mean(); lin.append(r)
    lev_lin, lev_sq = _leverage(lin), _leverage(sq)
    assert lev_lin < rs.LEVERAGE_MAX and lev_sq < rs.LEVERAGE_MAX, (lev_lin, lev_sq)
    assert payload["meta"]["disclosure"]["max_leverage"] == {"linear": round(lev_lin, 4), "squared": round(lev_sq, 4)}
    # The test has teeth: the half windows that were removed would fail it.
    extra = []
    for wid, (a, b) in {"first": ("2007-04", "2016-07"), "second": ("2016-08", "2025-11")}.items():
        sel = ((months >= a) & (months <= b)).to_numpy()
        for d in rs.DEFINITIONS:
            masks, _ = rs.state_masks(m[sel], dd[sel], dd.shift(1)[sel], d)
            idx = np.where(sel)[0]
            for state in rs.STATES:
                ind = np.zeros(T); ind[idx[masks[state].to_numpy()]] = 1; extra.append(ind)
    assert _leverage(lin + extra) > 0.999


def test_cost_proxy_aggregates(payload, frame):
    cp = payload["meta"]["cost_proxy"]
    drag = (frame["gross_ret"] - frame["strategy_ret"]).astype(float)
    assert abs(cp["mean_drag_month"] - drag.mean()) < 1e-9
    assert 0.3 < cp["share_months_charged"] < 0.37      # rebalancing months: about one in three


def test_page_numbers_match_json(payload):
    """Numbers quoted in the page prose (EN and ZH) come from the JSON."""
    res = payload["results"][_key()]
    gross = payload["results"][_key(stream="strategy_gross")]
    drag = f"{payload['meta']['cost_proxy']['mean_drag_month'] * 100:.2f}"
    carry_g, carry_n = f"{gross['raw'][0] * 100:.2f}%", f"{res['raw'][0] * 100:.2f}%"
    ci = res["ci"][7]
    tail_ci = f"{ci[0] * 100:.1f}%", f"{ci[1] * 100:.1f}%"
    lev = payload["meta"]["disclosure"]
    lev_txt = f"{lev['max_leverage']['linear']:.2f}", f"{lev['threshold']:.2f}"
    for page in ("projects/return-state-diagnostics.qmd", "zh/projects/return-state-diagnostics.qmd"):
        text = (WEB / "site" / page).read_text(encoding="utf-8")
        for s in (drag, carry_g, carry_n, *tail_ci, *lev_txt, "21"):
            assert s in text, (page, s)
        for s in ("owner", "first half", "second half", "45 results"):
            assert s not in text, (page, s)


NUM = re.compile(r"−?\d+(?:\.\d+)?%?")
PAGES = {"en": "projects/return-state-diagnostics.qmd", "zh": "zh/projects/return-state-diagnostics.qmd"}


def _page(lang: str) -> str:
    return (WEB / "site" / PAGES[lang]).read_text(encoding="utf-8")


def _definition_row(text: str, label: str) -> str:
    """One row of the hero's definition list: the label line, then ':   ' and the row's text."""
    m = re.search(rf"^{label}\n:   (.+)$", text, re.M)
    assert m, label
    return m.group(1)


def test_example_result_row_matches_json(payload):
    """The hero's Result row (EN and ZH) quotes the default view's downside and tail numbers, and only those,
    from return_state.json: n, the downside cut-off, downside beta, downside and tail means with intervals,
    and the count of positive tail months."""
    res = payload["results"][_key()]
    st = payload["states"]["d10|full"]
    ids = [m["id"] for m in payload["metrics"]]
    ib, idr, itr = ids.index("downside_beta"), ids.index("downside_reactivity"), ids.index("tail_reactivity")
    pct = lambda v: f"{v * 100:.2f}%".replace("-", "−")
    num = lambda v: f"{v:.2f}".replace("-", "−")
    expected = sorted([
        str(st["n"]["downside"]), pct(st["thresholds"]["lower"]),
        num(res["raw"][ib]), "95%", num(res["ci"][ib][0]), num(res["ci"][ib][1]),
        pct(res["raw"][idr]), pct(res["ci"][idr][0]), pct(res["ci"][idr][1]),
        str(st["n"]["tail"]), pct(res["raw"][itr]), pct(res["ci"][itr][0]), pct(res["ci"][itr][1]),
        str(res["pos"]["tail"]),
    ])
    assert expected == sorted(["23", "−5.88%", "0.20", "95%", "−0.47", "0.87", "2.28%", "0.62%", "3.94%",
                               "12", "2.72%", "−0.09%", "5.53%", "9"])
    for lang, label in (("en", "Result"), ("zh", "结果")):
        row = _definition_row(_page(lang), label)
        assert sorted(NUM.findall(row)) == expected, (lang, sorted(NUM.findall(row)))
    # The row carries its caveats: selection, the unstable downside profile, no hedge claim.
    en, zh = _definition_row(_page("en"), "Result"), _definition_row(_page("zh"), "结果")
    assert "selection of the configuration" in en and "two halves of the sample" in en and "not a hedge" in en
    assert "配置筛选" in zh and "前后两个半样本" in zh and "不能当作可以依赖的对冲" in zh


def test_page_copy_tied_to_json(payload):
    """Counts quoted in the prose (EN and ZH) follow the JSON; the hero promises only what the tool outputs;
    the disclosure screen is described as a heuristic, never as a guarantee."""
    st = payload["states"]["d10|full"]
    res = payload["results"][_key()]
    nd, nt, nm, k = st["n"]["downside"], st["n"]["tail"], st["n_months"], res["pos"]["tail"]
    share = round(100 * res["raw"][7])
    en, zh = _page("en"), _page("zh")
    # Shared base of spokes 4-8 (figure note) and the tail hit frequency.
    assert f"the same {nd} downside months (the {nt} tail months are among them)" in en
    assert f"rest on {nd} of the {nm} months" in en
    assert f"同样的 {nd} 个下行月份计算（{nt} 个尾部月份也在其中）" in zh and f"{nm} 个月中的 {nd} 个月" in zh
    assert f"positive in {k} of them ({share}%)" in en and f"其中 {k} 个月收益为正（{share}%）" in zh
    # Outputs card: per-state rules, cut-offs and counts; no per-month state labels are published.
    assert "Each state's rule, cut-offs and month count" in en and "各市场状态的划分规则、阈值与月数" in zh
    for s in ("Each month's state", "each month's state"):
        assert s not in en, s
    assert "每个月所属的市场状态" not in zh
    # Disclosure screen: author-set limit, heuristic, not a guarantee.
    assert "a heuristic safeguard, not a privacy guarantee" in en and "并非隐私保证" in zh
    assert "a limit the author set" in en and "作者自定的上限" in zh
    for s in ("no month recoverable", "checks that no single month can be reconstructed"):
        assert s not in en, s
    for s in ("无法从公开汇总统计反推任何月份", "披露检验确认"):
        assert s not in zh, s
    # Every return result is labelled as an archived backtest, not an audited record.
    assert "Archived backtest (not actual trading, not audited)" in en
    assert "存档回测（不是实际交易，未经审计）" in zh


def test_demo_warnings_and_csv_labels():
    """The interactive demo carries the stability caveat and the record type for archived streams."""
    fig = (WEB / "site" / "projects" / "_fig-return-state.qmd").read_text(encoding="utf-8")
    assert "warnStable: \"Stability: the archived strategy's downside profile differs markedly" in fig
    assert "warnStable: \"稳定性：存档策略在前后两个半样本中的下行表现明显不同" in fig
    assert "items.push(T.warnStable)" in fig
    assert "\"archived backtest: not actual trading, not audited\"" in fig
    assert "data: \"Data: archived backtest (not actual trading, not audited)" in fig
    assert "data: \"数据：存档回测（不是实际交易，未经审计）" in fig
    for s in ("first half", "second half"):
        assert s not in fig, s


# ------------------------------------------------------------------------------------- metric panel (Figure 1)
# The panel shown when a spoke is selected: the metric's name, the question it answers for a portfolio
# manager, one plain reading of the selected stream's history and one trust line; everything else sits in a
# collapsed <details>. Its wording is data (PANEL, valid JSON inside the partial); the checks below are
# JS-free (they read PANEL and rebuild every reading from return_state.json with a Python mirror of the
# panel's rules). test_panel_js_matches_mirror then runs the partial's own block under JavaScriptCore,
# where available, and requires the browser code to produce exactly the mirror's strings.

FIG = WEB / "site" / "projects" / "_fig-return-state.qmd"
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
PANEL_NUM = re.compile(r"[+−]?\d+(?:\.\d+)?%?")
PANEL_FORBIDDEN_EN = re.compile(r"\b(we|our|hedges?|hedging|protects?|protection|guarantee[sd]?|outperform\w*|beats?|"
                                r"superior|proven|always|will|live|real-time|production|deployed|audited|best)\b", re.I)
PANEL_FORBIDDEN_ZH = ("对冲", "保护", "保证", "跑赢", "战胜", "必然", "一定会", "最佳", "实盘", "已审计", "我们")
DEFAULT_PANEL = {
    "en": [
        ("In ordinary months, away from the market's biggest moves, what did this stream earn?",
         "In ordinary months (the market's middle 80%), the stream averaged +1.26% a month and the market +1.22%: "
         "it earned about as much as the market.",
         "Based on 178 months. The 95% interval (0.71% to 1.80% a month) lies entirely above zero."),
        ("When the market rallied hard, how much of the gain did this stream capture?",
         "In the market's strongest months (top 10%), the stream averaged +2.46% a month and the market +8.39%: "
         "it captured less than half of the market's gain.",
         "Based on 23 months. The 95% interval (−0.57% to 5.50% a month) spans zero, so even the sign is uncertain."),
        ("When the market rebounded from a drawdown, how much of the rebound did this stream capture?",
         "In recovery months (the market climbing back from a drawdown deeper than 5%), the stream averaged +1.55% "
         "a month and the market +5.18%: it captured less than half of the market's rebound.",
         "Based on 50 months. The 95% interval (0.02% to 3.09% a month) lies entirely above zero."),
        ("When the market fell, how closely did this stream move with it?",
         "In the market's worst months (bottom 10%), the stream's downside beta was 0.20 (the market's own is 1.00): "
         "it moved little with the market.",
         "Based on 23 months. The 95% interval (−0.47 to 0.87) includes 0 but not 1: consistent with no link to the "
         "market, not with a one-for-one move."),
        ("When the market sold off, did this stream make or lose money?",
         "In the market's worst months (bottom 10%), the stream averaged +2.28% a month and the market −8.27%: "
         "it made money on average while the market fell.",
         "Based on 23 months. The 95% interval (0.62% to 3.94% a month) lies entirely above zero."),
        ("In the market's sell-off months, how often did this stream still finish positive?",
         "In the market's worst months (bottom 10%), the stream still finished positive in 17 of the 23 months "
         "(73.9%); the market, by definition, in none.",
         "Based on 23 months. The 95% interval (51.6% to 89.8%) lies entirely above 50%: more often positive than "
         "not, even at its low end."),
        ("In the market's very worst months, did this stream make or lose money?",
         "In the market's very worst months (bottom 5%), the stream averaged +2.72% a month and the market −9.85%: "
         "it made money on average while the market fell.",
         "Only 12 months (fewer than 15): a small sample, too few to treat as a dependable trait. The 95% interval "
         "(−0.09% to 5.53% a month) spans zero, so even the sign is uncertain."),
        ("In the market's very worst months, how often did this stream still finish positive?",
         "In the market's very worst months (bottom 5%), the stream still finished positive in 9 of the 12 months "
         "(75.0%); the market, by definition, in none.",
         "Only 12 months (fewer than 15): a small sample, too few to treat as a dependable trait. The 95% interval "
         "(42.8% to 94.5%) includes 50%, so a coin flip cannot be ruled out."),
    ],
    "zh": [
        ("在没有大涨大跌的普通月份，这条收益序列平均赚多少？",
         "在普通月份（市场收益居中的 80%），该序列的平均月收益为 +1.26%，市场为 +1.22%：收益与市场大致相当。",
         "基于 178 个月。95% 区间（每月 0.71% 至 1.80%）全部高于零。"),
        ("市场大涨时，这条收益序列跟上了多少涨幅？",
         "在市场涨幅最大的月份（收益最高的 10%），该序列的平均月收益为 +2.46%，市场为 +8.39%：只跟上了市场涨幅的不到一半。",
         "基于 23 个月。95% 区间（每月 −0.57% 至 5.50%）跨越零，连正负都无法确定。"),
        ("市场从回撤中反弹时，这条收益序列跟上了多少反弹？",
         "在修复月份（市场从超过 5% 的回撤中回升），该序列的平均月收益为 +1.55%，市场为 +5.18%：只跟上了市场反弹幅度的不到一半。",
         "基于 50 个月。95% 区间（每月 0.02% 至 3.09%）全部高于零。"),
        ("市场下跌时，这条收益序列在多大程度上随市场同步变动？",
         "在市场跌幅最大的月份（收益最低的 10%），该序列的下行贝塔为 0.20（市场自身为 1.00）：它随市场变动的幅度很小。",
         "基于 23 个月。95% 区间（−0.47 至 0.87）包含 0 但不包含 1：与“和市场无关”相符，与“和市场一比一同步”不符。"),
        ("市场下跌时，这条收益序列是赚钱还是亏钱？",
         "在市场跌幅最大的月份（收益最低的 10%），该序列的平均月收益为 +2.28%，市场为 −8.27%：市场下跌时它平均仍然赚钱。",
         "基于 23 个月。95% 区间（每月 0.62% 至 3.94%）全部高于零。"),
        ("市场下跌的月份里，这条收益序列有多少个月仍为正收益？",
         "在市场跌幅最大的月份（收益最低的 10%），该序列 23 个月中仍有 17 个月为正收益（73.9%），市场按定义一个月也没有。",
         "基于 23 个月。95% 区间（51.6% 至 89.8%）全部高于 50%：即使取下限，正收益月份也多于一半。"),
        ("市场跌幅最极端的月份里，这条收益序列是赚钱还是亏钱？",
         "在市场跌幅最极端的月份（收益最低的 5%），该序列的平均月收益为 +2.72%，市场为 −9.85%：市场下跌时它平均仍然赚钱。",
         "只有 12 个月（少于 15 个月）：样本太小，不能当作稳定特征。95% 区间（每月 −0.09% 至 5.53%）跨越零，连正负都无法确定。"),
        ("市场跌幅最极端的月份里，这条收益序列有多少个月仍为正收益？",
         "在市场跌幅最极端的月份（收益最低的 5%），该序列 12 个月中仍有 9 个月为正收益（75.0%），市场按定义一个月也没有。",
         "只有 12 个月（少于 15 个月）：样本太小，不能当作稳定特征。95% 区间（42.8% 至 94.5%）包含 50%，无法排除五五开的可能。"),
    ],
}


@pytest.fixture(scope="module")
def site_json():
    """The committed JSON the page fetches (test_committed_json_and_tables_current ties it to a fresh build)."""
    return json.loads((WEB / "site" / "data" / "return_state.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def panel():
    text = FIG.read_text(encoding="utf-8")
    m = re.search(r"/\* rs-panel-text:begin \*/(.*?)/\* rs-panel-text:end \*/", text, re.S)
    assert m, "PANEL markers missing"
    return json.loads(m.group(1))


def _js_fixed(x: float, dp: int) -> str:
    """Number.prototype.toFixed (exact binary value, ties away from zero), with "-0.00" shown as "0.00"."""
    q = Decimal(abs(x)).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)
    t = ("-" if x < 0 else "") + f"{q:.{dp}f}"
    return t[1:] if re.fullmatch(r"-0(\.0+)?", t) else t


def _pfill(t: str, **o) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: m.group(0) if o.get(m.group(1)) is None else str(o[m.group(1)]), t)


def _pview(D, stream, definition, window="full", ov=None, i=None):
    """rsView in Python, with optional overrides of metric i (synthetic cases)."""
    k = f"{definition}|{window}"
    st = D["states"][k]
    v = copy.deepcopy({"key": f"{stream}|{k}", "st": st, "res": D["results"][f"{stream}|{k}"], "bench": st["bench"],
                       "stream": next(s for s in D["streams"] if s["id"] == stream),
                       "def": next(d for d in D["definitions"] if d["id"] == definition),
                       "win": next(w for w in D["windows"] if w["id"] == window)})
    if ov:
        state = D["metrics"][i]["state"]
        if "s" in ov: v["res"]["raw"][i] = ov["s"]
        if "b" in ov: v["bench"]["raw"][i] = ov["b"]
        if "ci" in ov: v["res"]["ci"][i] = ov["ci"]
        if "k" in ov: v["res"]["pos"][state] = ov["k"]
        if "n" in ov: v["st"]["n"][state] = ov["n"]
    return v


def _mirror(L, D, v, i, P):
    """Python mirror of rsPanel's text (question, reading, trust line, verdict and interval codes)."""
    B, T, m = P["bands"], P[L], D["metrics"][i]
    st, u, d = m["state"], m["units"], v["def"]
    n, lim = v["st"]["n"][st], D["meta"]["small_n"]
    small, lvl = n < lim, str(math.floor(D["meta"]["ci_level"] * 100 + 0.5))
    s, b = v["res"]["raw"][i], v["bench"]["raw"][i]
    ci = v["res"]["ci"][i] or [None, None]
    k = v["res"]["pos"][st] if u == "freq" else None
    kb = v["bench"]["pos"][st] if u == "freq" else None
    mn = lambda t: t.replace("-", "−")
    pc = lambda x, dp=2: T["na"] if x is None else mn(_js_fixed(x * 100, dp) + "%")
    sp = lambda x: "+" + pc(x) if x is not None and x > 0 and pc(x) != "0.00%" else pc(x)
    bt = lambda x: T["na"] if x is None else mn(_js_fixed(x, 2))
    f = lambda x: bt(x) if u == "beta" else pc(x, 1 if u == "freq" else 2)
    share = {"normal": lambda: d["upper"] - d["lower"], "rally": lambda: 1 - d["upper"],
             "recovery": lambda: -d["recovery_dd"], "tail": lambda: d["tail"], "downside": lambda: d["lower"]}[st]()
    where = _pfill(T["where"][st], p=math.floor(100 * share + 0.5))
    if u == "freq":
        code = "na" if k is None else "none" if k == 0 else "all" if k == n else "some"
        mk = ("con0" if m["bench_by_construction"] else "none") if kb == 0 else "some"
        read = T["noval"] if code == "na" else _pfill(T["freq"][code], where=where, k=k, n=n, share=pc(s, 1),
                                                       mk=_pfill(T["mk"][mk], kb=kb))
    elif u == "beta":
        c = B["beta"]
        code = ("na" if s is None else "against" if s <= c[0] else "little" if s < c[1] else "partial" if s < c[2]
                else "one" if s <= c[3] else "more")
        read = T["noval"] if code == "na" else _pfill(T["beta"], where=where, s=bt(s), b=bt(b), verdict=T["verdict"]["beta"][code])
    else:
        grp = m["id"] if m["id"] in ("carry", "upside", "recovery") else "down"
        r = s / b if s is not None and b else None
        fl, half, (n0, n1) = B["flat"], B["half"], B["near"]
        if s is None:
            code = "na"
        elif grp == "down":
            code = ("gain" if s >= fl else "flat" if s > -fl else "loss" if not (b is not None and b < 0) else
                    "lt_half" if r < half else "less" if r < n0 else "same" if r <= n1 else "more")
        else:
            code = ("loss" if s <= -fl else "flat" if s < fl else "gain" if not (b is not None and b > 0) else
                    ("below" if r < n0 else "same" if r <= n1 else "above") if grp == "carry" else
                    ("lt_half" if r < half else "gt_half" if r < n0 else "same" if r <= n1 else "more"))
        read = T["noval"] if code == "na" else _pfill(T["ret"], where=where, s=sp(s), b=sp(b), verdict=T["verdict"][grp][code])
    lo, hi = ci
    if lo is None or hi is None:
        ic = "na"
    elif u == "pct_month":
        ic = "above0" if lo > 0 else "below0" if hi < 0 else "spans0"
    elif u == "freq":
        ic = "aboveHalf" if lo > B["half"] else "belowHalf" if hi < B["half"] else "spansHalf"
    else:
        c0, c1 = lo <= 0 <= hi, lo <= 1 <= hi
        ic = "both" if c0 and c1 else "has0" if c0 else "has1" if c1 else "neg" if hi < 0 else "gt1" if lo > 1 else "mid"
    lead = _pfill(T["lead"]["small" if small else "based"], n=n, lim=lim)
    rng = T["na"] if ic == "na" else _pfill(T["range"][u], lo=f(lo), hi=f(hi))
    rest = T["noiv"] if ic == "na" else _pfill(T["iv"], lvl=lvl, range=rng, it=_pfill(T["it"][ic], half=pc(B["half"], 0)))
    return {"q": T["q"][m["id"]], "read": read, "trust": lead + T["sep"] + rest, "lead": lead,
            "verdict": code, "interp": ic, "small": small}


def _all_views(D):
    return [(s["id"], d["id"]) for s in D["streams"] for d in D["definitions"]]


def _strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}" if path else k)


def _synthetic(D):
    """Positive, negative, near-zero and boundary values on every metric (overrides of the default view)."""
    cases = []
    for i, m in enumerate(D["metrics"]):
        b = D["states"]["d10|full"]["bench"]["raw"][i]
        if m["units"] == "pct_month":
            for s in (-0.03, -0.0009, 0.0, 0.0004, 0.0009, 0.004, 0.02, 0.3 * b, 0.7 * b, b, 1.5 * b, -0.3 * b, -b, -1.5 * b):
                for ci in ([s - 0.004, s + 0.004], [s - 0.03, s + 0.03]):
                    cases.append((i, {"s": s, "ci": ci}))
            cases.append((i, {"s": 0.01, "b": 0.0, "ci": [0.0, 0.02]}))     # market flat: no ratio to quote
            cases.append((i, {"s": -0.01, "b": 0.0, "ci": [-0.02, 0.0]}))
        elif m["units"] == "beta":
            for s, ci in ((-0.6, [-0.9, -0.3]), (-0.1, [-0.8, 0.6]), (0.1, [-0.1, 0.3]), (0.5, [0.2, 0.8]),
                          (0.5, [-0.2, 1.2]), (1.0, [0.6, 1.4]), (1.6, [1.2, 2.0]), (0.9, [0.4, 1.1]), (-0.25, [-0.5, 0.0])):
                cases.append((i, {"s": s, "ci": ci}))
        else:
            for k, n, ci in ((0, 23, [0.0, 0.148]), (11, 23, [0.27, 0.69]), (20, 23, [0.66, 0.97]), (23, 23, [0.85, 1.0]),
                             (3, 10, [0.07, 0.65]), (10, 10, [0.69, 1.0]), (8, 15, [0.27, 0.77]), (7, 14, [0.23, 0.77])):
                cases.append((i, {"k": k, "n": n, "s": k / n, "ci": ci}))
        cases.append((i, {"ci": None}))
    return cases


def test_panel_text_complete_and_parallel(panel, site_json):
    """Both languages carry the same keys: a question per metric, a place per state, a verdict per code."""
    assert set(panel) == {"bands", "en", "zh"}
    paths = {L: {p for p, _ in _strings(panel[L])} for L in ("en", "zh")}
    assert paths["en"] == paths["zh"]
    ids = [m["id"] for m in site_json["metrics"]]
    for L in ("en", "zh"):
        T = panel[L]
        assert list(T["q"]) == ids and all(T["q"][i].endswith(("?", "？")) for i in ids)
        assert set(T["where"]) == {m["state"] for m in site_json["metrics"]}
        assert set(T["verdict"]) == {"carry", "upside", "recovery", "down", "beta"}
        assert set(T["it"]) == {"above0", "below0", "spans0", "aboveHalf", "belowHalf", "spansHalf",
                                "both", "has0", "has1", "mid", "neg", "gt1"}
        assert set(T["range"]) == {m["units"] for m in site_json["metrics"]}
    assert panel["en"]["more"] == "Definition and calculation" and panel["zh"]["more"] == "定义与计算"


def test_panel_templates_take_numbers_only_from_data(panel):
    """No number is typed into the wording: every digit comes from a {placeholder} filled from
    return_state.json or PANEL.bands. The only literal digits are 0 and 1 in the beta interval phrases
    (no link / one for one) and ddof = 1 in the beta calculation."""
    literal = {f"it.{c}": {"0", "1"} for c in ("both", "has0", "has1", "mid", "neg", "gt1")} | {"calc.beta": {"1"}}
    for L in ("en", "zh"):
        for path, s in _strings(panel[L]):
            digits = set(re.findall(r"\d", re.sub(r"\{\w+\}", "", s)))
            assert digits <= literal.get(path, set()), (L, path, s)
    # The wording bands quote the verdicts they produce.
    for L in ("en", "zh"):
        verdicts = " ".join(s for _, s in _strings(panel[L]["verdict"]))
        quoted = re.findall(r"“([^”]+)”", panel[L]["bandsText"])
        assert len(quoted) == 12, quoted
        for q in quoted:
            assert q in verdicts, (L, q)
        assert set(re.findall(r"\{(\w+)\}", panel[L]["bandsText"])) == {"flat", "half", "near_lo", "near_hi", "b1", "b2", "b3", "b4"}
    assert panel["bands"] == {"flat": 0.001, "half": 0.5, "near": [0.9, 1.1], "beta": [-0.25, 0.25, 0.75, 1.25]}


def test_panel_wording_rules(panel):
    """Plain, sole-author, no promise: no "we", no hedge/protection/guarantee/outperformance language."""
    fig = FIG.read_text(encoding="utf-8")
    hints = re.findall(r'hint: "([^"]+)"', fig)
    assert len(hints) == 2
    for path, s in list(_strings(panel["en"])) + [("hint", hints[0])]:
        assert not PANEL_FORBIDDEN_EN.search(s), (path, s)
    for path, s in list(_strings(panel["zh"])) + [("hint", hints[1])]:
        assert not any(w in s for w in PANEL_FORBIDDEN_ZH), (path, s)
        assert not re.search(r"[A-Za-z]{4,}", re.sub(r"\{\w+\}|OLS|cov|var|ddof|score|clip|frequency", "", s)), (path, s)


def test_panel_default_view(panel, site_json):
    """The default view's eight panels, EN and ZH, word for word."""
    v = _pview(site_json, "strategy_net", "d10")
    for L in ("en", "zh"):
        for i, (q, read, trust) in enumerate(DEFAULT_PANEL[L]):
            out = _mirror(L, site_json, v, i, panel)
            assert (out["q"], out["read"], out["trust"]) == (q, read, trust), (L, i + 1)


def test_panel_readings_tied_to_json(panel, site_json):
    """Every reading and trust line of the 21 results x 8 metrics x 2 languages: each number in it is one of
    that view's values in return_state.json (stream and benchmark value, counts, state share, interval ends,
    interval level, small-sample limit); the values a reader needs are all there; EN and ZH quote the same
    numbers; the small-sample warning appears exactly when n < meta.small_n."""
    D, B = site_json, panel["bands"]
    lim, lvl = D["meta"]["small_n"], round(D["meta"]["ci_level"] * 100)
    pc = lambda x, dp=2: (_js_fixed(x * 100, dp) + "%").replace("-", "−")
    sg = lambda x: ("+" if x > 0 and pc(x) != "0.00%" else "") + pc(x)
    bt = lambda x: _js_fixed(x, 2).replace("-", "−")
    seen = set()
    for stream, definition in _all_views(D):
        v = _pview(D, stream, definition)
        d = v["def"]
        shares = {"normal": d["upper"] - d["lower"], "rally": 1 - d["upper"], "recovery": -d["recovery_dd"],
                  "downside": d["lower"], "tail": d["tail"]}
        for i, m in enumerate(D["metrics"]):
            st, u = m["state"], m["units"]
            n, s, b = v["st"]["n"][st], v["res"]["raw"][i], v["bench"]["raw"][i]
            lo, hi = v["res"]["ci"][i]
            p = f"{math.floor(100 * shares[st] + 0.5)}%"
            if u == "pct_month":
                vals, ends = [sg(s), sg(b)], [pc(lo), pc(hi)]
            elif u == "beta":
                vals, ends = [bt(s), bt(b)], [bt(lo), bt(hi)]
            else:
                k = v["res"]["pos"][st]
                vals, ends = ([str(k), str(n), pc(s, 1)] if 0 < k < n else [str(n)]), [pc(lo, 1), pc(hi, 1)]
                assert v["bench"]["pos"][st] == 0 and m["bench_by_construction"]
            allowed = set(vals) | set(ends) | {p, str(n), f"{lvl}%", str(lim), pc(B["half"], 0), "0", "1"}
            nums = {}
            for L in ("en", "zh"):
                out = _mirror(L, D, v, i, panel)
                text = out["read"] + " " + out["trust"]
                assert "{" not in text and "}" not in text, text
                found = PANEL_NUM.findall(text)
                for x in found:
                    assert x in allowed, (stream, definition, m["id"], L, x, text)
                nums[L] = sorted(found)
                for x in vals + [p]:
                    assert x in out["read"], (stream, definition, m["id"], L, x)
                for x in ends + [str(n)]:
                    assert x in out["trust"], (stream, definition, m["id"], L, x)
                assert out["small"] == (n < lim) and (str(lim) in out["trust"]) == (n < lim)
                assert out["trust"].startswith(out["lead"])
                seen.add((m["id"], out["verdict"], out["interp"]))
            assert nums["en"] == nums["zh"], (stream, definition, m["id"])
    # The real data already exercise both signs on the return spokes and both sides of 50% on reliability.
    codes = {c for _, c, _ in seen}
    assert {"gain", "less", "lt_half", "gt_half", "below", "same", "above", "little", "partial", "some", "none"} <= codes


def test_panel_verdicts_never_contradict_the_numbers(panel, site_json):
    """Synthetic positive, negative, near-zero and boundary values on every spoke: each verdict agrees with the
    sign and size of the values it describes, every verdict and interval code is reachable, and the reading
    never says more than the numbers (no sign claim inside ±flat, no 'more than' without a larger value)."""
    D, B = site_json, panel["bands"]
    reached = set()
    for i, ov in _synthetic(D):
        v = _pview(D, "strategy_net", "d10", ov=ov, i=i)
        m = D["metrics"][i]
        s, b = v["res"]["raw"][i], v["bench"]["raw"][i]
        out = _mirror("en", D, v, i, panel)
        zh = _mirror("zh", D, v, i, panel)
        assert (out["verdict"], out["interp"]) == (zh["verdict"], zh["interp"])
        c, ic = out["verdict"], out["interp"]
        assert out["small"] == zh["small"] == (v["st"]["n"][m["state"]] < D["meta"]["small_n"])
        grp = (m["id"] if m["id"] in ("carry", "upside", "recovery") else "down") if m["units"] == "pct_month" else m["units"]
        reached.add((grp, c, ic))
        if m["units"] == "pct_month":
            if c == "flat":
                assert abs(s) < B["flat"]
            if c in ("gain", "loss"):
                assert (s >= B["flat"]) if c == "gain" else (s <= -B["flat"])
            if c in ("lt_half", "gt_half", "less", "same", "more", "below", "above"):
                assert s * b > 0
                r = s / b
                assert {"lt_half": r < .5, "gt_half": .5 <= r < .9, "less": .5 <= r < .9, "below": r < .9,
                        "same": .9 <= r <= 1.1, "more": r > 1.1, "above": r > 1.1}[c]
        elif m["units"] == "beta":
            assert {"against": s <= -.25, "little": -.25 < s < .25, "partial": .25 <= s < .75,
                    "one": .75 <= s <= 1.25, "more": s > 1.25}[c]
        else:
            k, n = v["res"]["pos"][m["state"]], v["st"]["n"][m["state"]]
            assert {"none": k == 0, "all": k == n, "some": 0 < k < n}[c]
        if ic != "na":
            lo, hi = v["res"]["ci"][i]
            ref = .5 if m["units"] == "freq" else 0
            if ic in ("spans0", "spansHalf"):
                assert lo <= ref <= hi
            if ic in ("above0", "aboveHalf"):
                assert lo > ref
        else:
            assert out["trust"].endswith(panel["en"]["noiv"]) and zh["trust"].endswith(panel["zh"]["noiv"])
    for grp, words in panel["en"]["verdict"].items():
        got = {c for g, c, _ in reached if g == grp}
        assert set(words) <= got, (grp, set(words) - got)
    assert {"none", "some", "all"} <= {c for g, c, _ in reached if g == "freq"}
    assert {ic for *_, ic in reached} == set(panel["en"]["it"]) | {"na"}


def _run_panel_js(cases, D):
    jsc = shutil.which("jsc") or (JSC if Path(JSC).exists() else None)
    if not jsc:
        pytest.skip("no JavaScriptCore shell (jsc) on this machine")
    fig = FIG.read_text(encoding="utf-8")
    block = re.search(r"  /\* rs-panel:begin.*?/\* rs-panel:end \*/", fig, re.S).group(0)
    js = ("var D = " + json.dumps(D) + ";\n" + block + "\nvar cases = " + json.dumps(cases) + ";\n" + """
print(JSON.stringify(cases.map(function (c) {
  var v = JSON.parse(JSON.stringify(rsView(D, c.stream, c.def, "full"))), ov = c.ov || {}, st = D.metrics[c.i].state;
  if ("s" in ov) v.res.raw[c.i] = ov.s;
  if ("b" in ov) v.bench.raw[c.i] = ov.b;
  if ("ci" in ov) v.res.ci[c.i] = ov.ci;
  if ("k" in ov) v.res.pos[st] = ov.k;
  if ("n" in ov) v.st.n[st] = ov.n;
  var r = rsPanel(c.L, D, v, c.i, !!c.open);
  return [r.q, r.read, r.trust, r.lead, r.verdict, r.interp, r.small, r.html];
})));""")
    res = subprocess.run([jsc, "-e", js], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0 and res.stdout.strip(), res.stderr
    return json.loads(res.stdout)


def test_panel_js_matches_mirror(panel, site_json):
    """The partial's own rsPanel, run under JavaScriptCore, produces exactly the mirror's strings for all 21
    results x 8 metrics x 2 languages and every synthetic case."""
    D = site_json
    cases = [{"stream": s, "def": d, "i": i, "L": L} for s, d in _all_views(D) for i in range(8) for L in ("en", "zh")]
    cases += [{"stream": "strategy_net", "def": "d10", "i": i, "L": L, "ov": ov} for i, ov in _synthetic(D) for L in ("en", "zh")]
    out = _run_panel_js(cases, D)
    assert len(out) == len(cases)
    for c, r in zip(cases, out):
        v = _pview(D, c["stream"], c["def"], ov=c.get("ov"), i=c["i"])
        py = _mirror(c["L"], D, v, c["i"], panel)
        assert r[:7] == [py["q"], py["read"], py["trust"], py["lead"], py["verdict"], py["interp"], py["small"]], (c, r[:7])


def test_panel_html_structure(panel, site_json):
    """Visible: name, question, reading, trust line (four short blocks). Collapsed: everything else, complete.
    The <details> is closed unless the reader opened it; the visible part carries no definition material."""
    D = site_json
    cases = [{"stream": s, "def": d, "i": i, "L": L} for s, d in _all_views(D) for i in range(8) for L in ("en", "zh")]
    cases.append({"stream": "strategy_net", "def": "d10", "i": 0, "L": "en", "open": True})
    out = _run_panel_js(cases, D)
    shape = re.compile(r'<h4>(\d+)\. ([^<]+)</h4><p class="rs-q">([^<]+)</p><p class="rs-read">([^<]+)</p>'
                       r'<p class="rs-trust">(.+?)</p><details class="rs-more"( open)?><summary>([^<]+)</summary>'
                       r"<dl>(.*)</dl>(.*)</details>", re.S)
    for c, r in zip(cases, out):
        L, i = c["L"], c["i"]
        T, m = panel[L], D["metrics"][i]
        v = _pview(D, c["stream"], c["def"])
        g = shape.fullmatch(r[7])
        assert g, r[7][:300]
        num, name, q, read, trust, opened, summary, dl, notes = g.groups()
        assert (int(num), name, q, read) == (i + 1, m[L], r[0], r[1])
        assert html.unescape(re.sub(r"</?strong>", "", trust)) == r[2]
        assert trust.startswith("<strong>") == r[6]
        assert bool(opened) == bool(c.get("open")) and summary == T["more"]
        visible = r[7].split("<details", 1)[0]
        norm = D["normalisation"][m["norm"]]
        rule = v["def"]["rules"][m["state"]][L]
        for s in (norm["formula"], norm[L], rule, T["se"], T["calc"][m["norm"]], "clip", "OLS", T["ciNote"], T["conNote"]):
            assert s not in visible, (c, s)
        if m["wp_name"]:
            assert m["wp_name"] not in visible
        # The block is complete: rule, observations, calculation, interval and standard error, scores and formula.
        for s in (rule, f"n = {v['st']['n'][m['state']]}", T["calc"][m["norm"]], norm["formula"], norm[L], T["ciNote"]):
            assert s in dl, (c, s)
        se = v["res"]["se"][i]
        assert (T["se"] in dl) == (se is not None)
        assert (T["conNote"] in dl) == m["bench_by_construction"]
        assert (T["clipNote"] in notes) == (v["res"]["clipped"][i] or v["bench"]["clipped"][i])
        if m["wp_name"]:
            assert _pfill(T["wpName"], name=m["wp_name"]) in notes
        else:
            assert "white paper" not in notes and "白皮书" not in notes
        assert _pfill(T["bandsText"], flat="0.10%", half="50%", near_lo="90%", near_hi="110%",
                      b1="−0.25", b2="0.25", b3="0.75", b4="1.25") in notes


def test_panel_wiring_unchanged():
    """The panel stays a polite live region; spokes and table rows still select on hover, focus, click and
    keys; the <details> state survives a metric switch and keyboard focus is not dropped on re-render."""
    fig = FIG.read_text(encoding="utf-8")
    assert '<div class="rs-detail" id="rs-detail" aria-live="polite"></div>' in fig
    assert 'box.innerHTML = rsPanel(LANG, D, v, cur.active, cur.more).html;' in fig
    assert 'more.addEventListener("toggle", function () { cur.more = more.open; });' in fig
    assert 'if (refocus) more.querySelector("summary").focus();' in fig
    for ev in ("mouseenter", "focus", "click", "keydown"):
        assert f'node.addEventListener("{ev}"' in fig, ev
    assert 'function view() { return rsView(D, cur.stream, cur.def, cur.win); }' in fig
    assert 'el("rs-hintline").textContent = T.hint;' in fig
    assert "detailHint" not in fig
