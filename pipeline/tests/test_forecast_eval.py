"""Tests of the forecast_eval exhibit (Projects: Macro Forecast Evaluation & Regime Diagnostics).

Three groups. The statistics and input-validation tests use synthetic data and run everywhere. The
committed-file tests check the committed JSON against the committed tables, the page text and the
committed code; they also need no archive, so they run on a clean clone of the public repository. The
source tests recompute everything from the archived records and are skipped when sources.toml is missing
or its [roots] lacks `uk_inflation`.
"""
import hashlib
import json
import math
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from exhibits import forecast_eval as fe

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"
COMMITTED = WEB / "site" / "data" / "forecast_eval.json"
# Generic guards only. Private folder and file names are read at run time from the git-ignored sources.toml,
# so they never appear in this tracked file.
FORBIDDEN = ("/Volumes", "/Users", "PycharmProjects", "Claude")
GENERIC_PARTS = {"Volumes", "Users", "Projects"}
PUBLIC_FILES = [WEB / "site" / "projects" / "forecast-evaluation.qmd", WEB / "site" / "zh" / "projects" / "forecast-evaluation.qmd",
                WEB / "site" / "projects" / "_fig-forecast-eval.qmd", WEB / "site" / "projects" / "_tbl-forecast-eval.md",
                WEB / "site" / "projects" / "_tbl-forecast-eval-zh.md", Path(fe.__file__), Path(__file__)]


def _configured() -> bool:
    if not CONFIG.exists():
        return False
    with open(CONFIG, "rb") as fh:
        cfg = tomllib.load(fh)
    return fe.ROOT in cfg.get("roots", {}) and all(cfg.get(fe.LAYOUT, {}).get(k) for k in fe.LAYOUT_KEYS)


def _private_tokens() -> tuple[list[str], list[re.Pattern]]:
    """Folder and file names of the configured root and layout, plus spacing- and case-insensitive variants of each."""
    with open(CONFIG, "rb") as fh:
        root = Path(tomllib.load(fh)["roots"][fe.ROOT]).expanduser()
    parts = [p for p in root.parts if len(p) > 3 and p not in GENERIC_PARTS]
    # folder and file stems of the configured layout
    for k in fe.LAYOUT_KEYS:
        for piece in re.split(r"[/{}]", fe._L.get(k, "")):
            stem = piece.split(".")[0].rstrip("_")
            if len(stem) > 6 and stem not in ("tables", "processed", "data", "tag"):
                parts.append(stem)
    runs = [re.findall(r"[A-Za-z]+|\d+", p) for p in parts]
    pats = [re.compile(r"\s*".join(map(re.escape, r)), re.IGNORECASE) for r in runs if r]
    return parts, pats


needs_root = pytest.mark.skipif(not _configured(), reason="sources.toml has no uk_inflation root/layout on this machine")


# ------------------------------------------------------------------------------ statistics (always run)

def test_t_distribution_reference_values():
    assert fe.t_two_sided_p(0.0, 10) == pytest.approx(1.0, abs=1e-12)
    assert fe.t_two_sided_p(2.228138851986, 10) == pytest.approx(0.05, abs=1e-9)        # t(0.975, 10)
    assert fe.t_two_sided_p(-1.812461122811, 10) == pytest.approx(0.10, abs=1e-9)       # t(0.95, 10)
    assert fe.t_two_sided_p(2.570581835636, 5) == pytest.approx(0.05, abs=1e-9)         # t(0.975, 5)
    for t in (0.3, 1.0, 4.0, 25.0):                                                    # Cauchy: exact
        assert fe.t_two_sided_p(t, 1) == pytest.approx(1 - 2 / math.pi * math.atan(t), abs=1e-12)
    assert fe.t_two_sided_p(1.959963985, 1e7) == pytest.approx(0.05, abs=1e-6)          # normal limit


def _lrv_bruteforce(d, lag, kernel="bartlett"):
    T = len(d)
    m = sum(d) / T
    g = [sum((d[t] - m) * (d[t - k] - m) for t in range(k, T)) / T for k in range(lag + 1)]
    w = (lambda k: 1 - k / (lag + 1)) if kernel == "bartlett" else (lambda k: 1.0)
    return g[0] + 2 * sum(w(k) * g[k] for k in range(1, lag + 1))


def test_newey_west_matches_bruteforce():
    rng = np.random.default_rng(7)
    d = rng.normal(size=57).tolist()
    for lag in (0, 1, 2, 5):
        assert fe.newey_west_lrv(np.array(d), lag) == pytest.approx(_lrv_bruteforce(d, lag), rel=1e-12)
        assert fe.rectangular_lrv(np.array(d), lag) == pytest.approx(_lrv_bruteforce(d, lag, "rectangular"), rel=1e-12)


def test_diebold_mariano_synthetic_case():
    """Hand-checkable case: the model's loss exceeds the baseline's by a known differential."""
    rng = np.random.default_rng(11)
    T, h = 80, 3
    e0 = rng.normal(size=T)
    e1 = rng.normal(size=T) * 1.4
    d = e1 ** 2 - e0 ** 2
    lrv = _lrv_bruteforce(d.tolist(), h - 1, "rectangular")
    assert lrv > 0
    dm = d.mean() / math.sqrt(lrv / T)
    hln = dm * math.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)
    out = fe.diebold_mariano(e1, e0, h)
    assert out["n"] == T and out["lag"] == h - 1 and out["kernel"] == "rectangular"
    assert out["mean_d"] == pytest.approx(d.mean(), rel=1e-12)
    assert out["dm"] == pytest.approx(dm, rel=1e-12)
    assert out["hln"] == pytest.approx(hln, rel=1e-12)
    assert out["p"] == pytest.approx(fe.t_two_sided_p(hln, T - 1), rel=1e-12)
    assert out["dm"] > 0                                      # larger model errors -> positive statistic
    swapped = fe.diebold_mariano(e0, e1, h)
    assert swapped["dm"] == pytest.approx(-out["dm"], rel=1e-12) and swapped["p"] == pytest.approx(out["p"], rel=1e-12)
    hln_b = d.mean() / math.sqrt(_lrv_bruteforce(d.tolist(), h - 1) / T) * math.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)
    assert out["hln_bartlett"] == pytest.approx(hln_b, rel=1e-12)
    assert out["p_bartlett"] == pytest.approx(fe.t_two_sided_p(hln_b, T - 1), rel=1e-12)


E1_PIN = [-0.962, -1.589, -0.298, 0.505, 1.363, 0.132, -0.663, -0.942, 0.898, 1.962, 0.327, -1.48, -1.15, 1.92, 0.243, -2.079,
          -0.1, -1.396, -0.755, -0.586, -0.856, 0.664, -0.076, -0.707, 0.492, 0.996, -1.972, -0.308, -1.177, -0.208, -1.547, 0.025,
          -0.045, -0.365, -1.258, -0.475, -1.31, -1.626, 0.27, -1.331]
E0_PIN = [1.053, 1.776, -2.553, -0.138, 1.014, 1.352, 0.654, 1.497, 0.29, 0.551, 0.179, -1.074, -0.847, 0.38, -0.58, 1.272,
          1.292, 1.799, -0.026, 1.384, -0.906, -0.816, 0.081, 0.281, -1.599, -1.731, 0.355, -0.862, 1.208, 0.395, 0.307, 0.208,
          0.895, -0.153, 1.086, -0.526, -0.225, -0.681, 0.598, 0.036]


def test_diebold_mariano_pinned_kernel_choice():
    """Pins the variance estimator: equal weights (original DM/HLN) for p, Bartlett for p_bartlett, fixed inputs."""
    out = fe.diebold_mariano(np.array(E1_PIN), np.array(E0_PIN), 3)
    assert out["kernel"] == "rectangular"
    assert out["dm"] == pytest.approx(0.4186212039336277, rel=1e-10)
    assert out["hln"] == pytest.approx(0.3924224920368614, rel=1e-10)
    assert out["p"] == pytest.approx(0.6968826223042579, rel=1e-10)
    assert out["p_bartlett"] == pytest.approx(0.6989551490336465, rel=1e-10)


def test_diebold_mariano_falls_back_to_bartlett_when_variance_not_positive():
    d = np.array([2.0, -1.0] * 10) + 0.1                    # strong negative lag-1 autocorrelation
    assert fe.rectangular_lrv(d, 1) <= 0 < fe.newey_west_lrv(d, 1)
    e_model, e_base = np.sqrt(np.maximum(d, 0) + 1.5), np.sqrt(np.maximum(-d, 0) + 1.5)
    assert np.allclose(e_model ** 2 - e_base ** 2, d)         # the loss differential is exactly d
    out = fe.diebold_mariano(e_model, e_base, 2)
    assert out["kernel"] == "bartlett" and out["p"] == pytest.approx(out["p_bartlett"], rel=1e-12)


def test_diebold_mariano_size_under_the_null():
    """Equal-accuracy MA(h-1) forecast errors: rejection at 5% stays near 5% (HLN keeps the size honest)."""
    rng = np.random.default_rng(2026)
    h, T, reps = 3, 120, 1500
    theta = np.ones(h) / math.sqrt(h)
    rej = 0
    for _ in range(reps):
        u = rng.normal(size=(2, T + h - 1))
        e = np.stack([np.convolve(u[i], theta, mode="valid") for i in range(2)])
        rej += fe.diebold_mariano(e[0], e[1], h)["p"] < 0.05
    assert 0.025 <= rej / reps <= 0.085


def test_metrics_definitions():
    y = np.array([1.0, -1.0, 0.5, 0.0])
    yhat = np.array([0.5, 0.5, -0.5, 0.0])
    m = fe.metrics(y, yhat)
    assert m["n"] == 4
    assert m["rmse"] == pytest.approx(math.sqrt((0.25 + 2.25 + 1.0 + 0.0) / 4))
    assert m["mae"] == pytest.approx((0.5 + 1.5 + 1.0) / 4)
    assert m["dir"] == pytest.approx(2 / 4)                     # sign(0) == sign(0) counts, as in the archive


# ------------------------------------------------------------------------------ input validation (always run)

def _t09_records(models=("M0", "M1", "M2"), months=("2020-01", "2020-02", "2020-03", "2020-04")) -> pd.DataFrame:
    """A small, valid per-origin record table in the archived layout (date, horizon, model_key, model_label,
    y, yhat, error): the same outcome y for every model at an origin, error = y - yhat."""
    rows = []
    for i, d in enumerate(months):
        for h in fe.HORIZONS:
            y = 0.1 * (i + 1) - 0.05 * h
            for j, m in enumerate(models):
                yhat = 0.02 * j - 0.01 * i
                rows.append({"date": f"{d}-01", "horizon": f"{h}m", "model_key": m, "model_label": m,
                             "y": y, "yhat": yhat, "error": y - yhat})
    return pd.DataFrame(rows)


def _write(df: pd.DataFrame, path: Path) -> Path:
    df.to_csv(path, index=False)
    return path


def test_read_t09_accepts_valid_records(tmp_path):
    out = fe._read_t09(_write(_t09_records(), tmp_path / "ok.csv"), ["M0", "M1", "M2"])
    assert set(out) == {"3m", "6m"}
    for wide in out.values():
        assert list(wide.columns) == ["M0", "M1", "M2", "y"] and len(wide) == 4


def test_read_t09_rejects_missing_model(tmp_path):
    t = _t09_records()
    t = t[t["model_key"] != "M1"]
    with pytest.raises(ValueError, match="models"):
        fe._read_t09(_write(t, tmp_path / "missing_model.csv"), ["M0", "M1", "M2"])


def test_read_t09_rejects_unexpected_model(tmp_path):
    t = _t09_records(models=("M0", "M1", "M2", "M9"))
    with pytest.raises(ValueError, match="models"):
        fe._read_t09(_write(t, tmp_path / "extra_model.csv"), ["M0", "M1", "M2"])


def test_read_t09_rejects_outcome_mismatch(tmp_path):
    t = _t09_records()
    i = t.index[(t["model_key"] == "M2") & (t["horizon"] == "3m")][1]
    t.loc[i, "y"] += 0.25
    t.loc[i, "error"] = t.loc[i, "y"] - t.loc[i, "yhat"]           # the error column stays consistent
    with pytest.raises(ValueError, match="y differs across models"):
        fe._read_t09(_write(t, tmp_path / "y_mismatch.csv"), ["M0", "M1", "M2"])


def test_read_t09_rejects_error_not_y_minus_yhat(tmp_path):
    t = _t09_records()
    i = t.index[(t["model_key"] == "M1") & (t["horizon"] == "6m")][2]
    t.loc[i, "error"] += 1e-6
    with pytest.raises(ValueError, match="error column is not y - yhat"):
        fe._read_t09(_write(t, tmp_path / "bad_error.csv"), ["M0", "M1", "M2"])


def test_months_must_be_consecutive():
    fe._assert_monthly(["2019-11", "2019-12", "2020-01"], "ok")              # a year boundary is fine
    for bad in (["2020-01", "2020-03"], ["2020-01", "2020-02", "2020-02"], ["2020-02", "2020-01"]):
        with pytest.raises(ValueError, match="not consecutive"):
            fe._assert_monthly(bad, "synthetic")
    with pytest.raises(ValueError, match="not consecutive"):
        fe._segment(pd.DatetimeIndex(["2020-01-01", "2020-02-01", "2020-04-01"]))


def test_table_parity_flags_a_changed_archive_cell():
    """The build's parity check against the archived tables: zero on a self-consistent table, the size of the
    change when one archived cell is altered, and an error when a count differs."""
    rng = np.random.default_rng(5)
    idx = pd.date_range("2015-01-01", periods=40, freq="MS")
    out = {}
    for h in fe.HORIZONS:
        y = rng.normal(size=40)
        wide = pd.DataFrame({m: y + rng.normal(scale=0.5 + 0.1 * j, size=40) for j, m in enumerate(("M1", "M2", "M4"))}, index=idx)
        wide.loc[idx[:3], "M4"] = np.nan                       # M4 starts later: own and common windows differ
        wide["y"] = y
        out[f"{h}m"] = wide
    ev = fe.evaluate_version(out, ["M1", "M2", "M4"], ["M1", "M2", "M4"], None)
    t06 = pd.DataFrame([{"horizon": hk, "model_key": m, "n_oos": r["n"], "rmse": r["rmse"], "mae": r["mae"],
                         "directional_acc": r["dir"]} for hk in ev for m, r in ev[hk]["_raw"]["own"].items()])
    t08 = pd.DataFrame([{"horizon": hk, "model_key": m, "rmse_model": o[m]["rmse"], "rmse_M1": o["M1"]["rmse"],
                         "rmse_M2": o["M2"]["rmse"], "rmse_impr_vs_M1_pct": (o["M1"]["rmse"] - o[m]["rmse"]) / o["M1"]["rmse"] * 100,
                         "rmse_impr_vs_M2_pct": -o[m]["rel_pct"]} for hk in ev for o in [ev[hk]["_raw"]["own"]] for m in o])
    t10 = pd.DataFrame([{"horizon": hk, "model_key": m, "common_n_oos": r["n"], "common_rmse": r["rmse"],
                         "common_mae": r["mae"], "common_directional_acc": r["dir"],
                         "common_rmse_M2": ev[hk]["_raw"]["common"]["M2"]["rmse"], "common_rmse_impr_vs_M2_pct": -r["rel_pct"]}
                        for hk in ev for m, r in ev[hk]["_raw"]["common"].items()])
    ok = fe.table_parity(ev, t06, t08, t10)
    assert ok["max_abs_delta"] == 0.0 and ok["counts"] == len(t06) + len(t10)
    assert ok["values"] == 3 * len(t06) + 5 * len(t08) + 5 * len(t10)
    t10.loc[2, "common_rmse"] += 2e-9
    assert fe.table_parity(ev, t06, t08, t10)["max_abs_delta"] == pytest.approx(2e-9, rel=1e-3)
    t06.loc[0, "n_oos"] += 1
    with pytest.raises(ValueError, match="own-window n"):
        fe.table_parity(ev, t06, t08, t10)


# ------------------------------------------------------------------------------ committed files (no archive needed)

@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


EN_PAGE = WEB / "site" / "projects" / "forecast-evaluation.qmd"
ZH_PAGE = WEB / "site" / "zh" / "projects" / "forecast-evaluation.qmd"
FIG_PARTIAL = WEB / "site" / "projects" / "_fig-forecast-eval.qmd"


def test_committed_tables_match_committed_json(committed):
    """The static tables on the page are generated from the committed JSON (EN and ZH)."""
    for rel, lang in ((fe.TABLE_PATH, "en"), (fe.TABLE_PATH_ZH, "zh")):
        assert (WEB / "site" / rel).read_text(encoding="utf-8") == fe.table_markdown(committed, lang), rel


def test_committed_json_records_its_code_sources_and_parity(committed):
    """The recomputation record: the committed JSON names the code that produced it (SHA-256 of this
    repository's forecast_eval.py), one hash per labelled source file, and parity within the tolerances."""
    meta = committed["meta"]
    assert meta["code_sha256"] == {"pipeline/exhibits/forecast_eval.py": hashlib.sha256(Path(fe.__file__).read_bytes()).hexdigest()}
    assert meta["exhibit_version"] == fe.EXHIBIT_VERSION
    assert meta["source_files"] == fe.SOURCE_LABELS and set(meta["source_sha256"]) == set(fe.SOURCE_LABELS)   # JSON keys are sorted
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in meta["source_sha256"].values())
    assert len(set(meta["source_sha256"].values())) == len(fe.SOURCE_LABELS)
    tab, fc = meta["parity"]["archived_tables"], meta["parity"]["stored_forecasts"]
    assert tab["tolerance"] == fe.PARITY_TOL_TABLES and 0 <= tab["max_abs_delta"] < tab["tolerance"]
    assert tab["runs"] == ["summary", "latest"] and tab["values"] > 0 and tab["counts"] > 0
    assert fc["tolerance"] == fe.PARITY_TOL_FORECASTS and 0 <= fc["max_abs_delta"] < fc["tolerance"]
    assert fc["run"] == "latest" and fc["models"] == list(fe.SPECS) and fc["n"] > 0


def test_nested_pairs_are_flagged(committed):
    """M0 (zero forecast) and M1 are nested in M2, and M2 in M6: their DM p-values are flagged as indicative."""
    assert {m["key"] for m in committed["models"] if m["nested_with_baseline"]} == {"M0", "M1", "M6"} == fe.NESTED
    for vid in fe.VERSION_ORDER:
        for hk in ("3m", "6m"):
            for m, pair in committed["eval"][vid][hk]["pairs"].items():
                assert pair["own"]["nested"] == pair["common"]["nested"] == (m in fe.NESTED)
    for text in (EN_PAGE.read_text(encoding="utf-8"), (WEB / "site" / fe.TABLE_PATH).read_text(encoding="utf-8")):
        assert "M0 and M1 inside M2" in text or "M0, M1 and M6 are nested with M2" in text
    assert "M0 与 M1 嵌套于 M2" in ZH_PAGE.read_text(encoding="utf-8")
    assert "M0、M1、M6 与 M2 为嵌套关系" in (WEB / "site" / fe.TABLE_PATH_ZH).read_text(encoding="utf-8")


def test_own_window_table_uses_matched_origins(committed):
    """Table 1 in own-window mode leads with the matched-origin ratio and keeps the archived ratio apart.
    The caption says the archived ratio flips sign for M5: true in every version and horizon."""
    fig = FIG_PARTIAL.read_text(encoding="utf-8")
    assert "fe_ev.pairs[k].own.rel_pct" in fig and "fe_ev.own[k].rel_pct" in fig
    for vid in fe.VERSION_ORDER:
        for hk in ("3m", "6m"):
            ev = committed["eval"][vid][hk]
            assert ev["own"]["M5"]["rel_pct"] * ev["pairs"]["M5"]["own"]["rel_pct"] < 0, (vid, hk)
    assert "for M5 it even changes sign" in EN_PAGE.read_text(encoding="utf-8")
    assert "M5 的比值符号甚至因此相反" in ZH_PAGE.read_text(encoding="utf-8")


def test_page_numbers_match_payload(committed):
    """Numbers quoted in the EN and ZH page text are the committed payload's, rounded as printed."""
    payload = committed
    ev, srows = payload["eval"], payload["sensitivity"]
    pct = lambda x: f"{abs(x):.2f}%"
    win = {s["horizon"]: s for s in srows if s["model"] == "M4" and s["version"] == fe.EVAL_WINDOW_ROW}
    expected = [pct(ev["summary"][h]["pairs"]["M4"]["common"]["rel_pct"]) for h in ("3m", "6m")]
    expected += [pct(ev["latest"][h]["pairs"]["M4"]["common"]["rel_pct"]) for h in ("3m", "6m")]
    expected += [pct(ev["observed"][h]["pairs"]["M4"]["common"]["rel_pct"]) for h in ("3m", "6m")]
    expected += ["+" + pct(win["3m"]["rel_pct"]), "−" + pct(win["6m"]["rel_pct"])]
    expected += [f"p = {ev['summary']['3m']['pairs']['M4']['common']['p']:.2f} 和 {ev['summary']['6m']['pairs']['M4']['common']['p']:.2f}"]
    expected += [f"p = {win['3m']['p']:.2f}", f"p = {win['6m']['p']:.2f}", str(payload["meta"]["p_values"]["count"]),
                 pct(ev["observed"]["6m"]["pairs"]["M6"]["common"]["rel_pct"])]
    en = EN_PAGE.read_text(encoding="utf-8")
    zh = ZH_PAGE.read_text(encoding="utf-8")
    for e in expected:
        assert e in zh, e
        assert e.replace(" 和 ", " and ") in en, e
    lp = ev["latest"]
    assert f"p = {lp['3m']['pairs']['M4']['common']['p']:.2f} and {lp['6m']['pairs']['M4']['common']['p']:.2f}" in en
    assert f"0.0{round(payload['meta']['p_values']['min_p'] * 100)}" in en          # "0.07"
    # The observed-outcomes comparison: both runs' common-window ratios, and the later start of its windows.
    obs = [pct(ev["observed"][h]["pairs"]["M4"]["common"]["rel_pct"]) for h in ("3m", "6m")]
    lat = [pct(ev["latest"][h]["pairs"]["M4"]["common"]["rel_pct"]) for h in ("3m", "6m")]
    assert f"+{obs[0]} and +{obs[1]}, against +{lat[0]} and +{lat[1]}" in en
    assert f"+{obs[0]} 和 +{obs[1]}，最新版本为 +{lat[0]} 和 +{lat[1]}" in zh
    starts = [ev["observed"][h]["common"]["first"] for h in ("3m", "6m")]
    assert starts == ["2016-03", "2016-06"] and [ev["latest"][h]["common"]["first"] for h in ("3m", "6m")] == ["2016-01"] * 2
    assert "in March and June 2016" in en and "即 2016 年 3 月和 6 月" in zh


# ------------------------------------------------------------------------------ against the archived outputs

@pytest.fixture(scope="module")
def root():
    from sources import load_sources
    return fe._root(load_sources(CONFIG))


@pytest.fixture(scope="module")
def raw_evals(root):
    out = {}
    for vid, v in fe.VERSIONS.items():
        preds = fe._read_t09(root / v["dir"] / fe.F_T09.format(tag=v["tag"]), v["models"])
        out[vid] = fe.evaluate_version(preds, v["models"], v["common_set"], None)
    return out


@pytest.fixture(scope="module")
def payload():
    from sources import load_sources
    return fe.build(load_sources(CONFIG))


def _ladder_deltas(root, raw_evals, vid) -> tuple[list[float], int]:
    """|this module - archived table| for every real-valued cell of the run's T06, T08 and T10 tables, written
    out here independently of fe.table_parity; integer counts are asserted equal and counted."""
    v = fe.VERSIONS[vid]
    t06 = pd.read_csv(root / v["dir"] / fe.F_T06.format(tag=v["tag"]))
    t08 = pd.read_csv(root / v["dir"] / fe.F_T08.format(tag=v["tag"]))
    t10 = pd.read_csv(root / v["dir"] / fe.F_T10.format(tag=v["tag"]))
    deltas, counts = [], 0
    for _, r in t06.iterrows():
        mine = raw_evals[vid][r["horizon"]]["_raw"]["own"][r["model_key"]]
        assert mine["n"] == r["n_oos"]
        counts += 1
        deltas += [abs(mine[a] - r[b]) for a, b in (("rmse", "rmse"), ("mae", "mae"), ("dir", "directional_acc"))]
    for _, r in t10.iterrows():
        common = raw_evals[vid][r["horizon"]]["_raw"]["common"]
        mine = common[r["model_key"]]
        assert mine["n"] == r["common_n_oos"]
        counts += 1
        deltas += [abs(mine[a] - r[b]) for a, b in (("rmse", "common_rmse"), ("mae", "common_mae"), ("dir", "common_directional_acc"))]
        deltas += [abs(common["M2"]["rmse"] - r["common_rmse_M2"]), abs(-mine["rel_pct"] - r["common_rmse_impr_vs_M2_pct"])]
    for _, r in t08.iterrows():
        own = raw_evals[vid][r["horizon"]]["_raw"]["own"]
        m1 = (own["M1"]["rmse"] - own[r["model_key"]]["rmse"]) / own["M1"]["rmse"] * 100
        deltas += [abs(own[r["model_key"]]["rmse"] - r["rmse_model"]), abs(own["M1"]["rmse"] - r["rmse_M1"]),
                   abs(own["M2"]["rmse"] - r["rmse_M2"]), abs(-own[r["model_key"]]["rel_pct"] - r["rmse_impr_vs_M2_pct"]),
                   abs(m1 - r["rmse_impr_vs_M1_pct"])]
    return deltas, counts


@needs_root
@pytest.mark.parametrize("vid", ["summary", "latest"])
def test_parity_with_archived_ladders(root, raw_evals, vid):
    deltas, counts = _ladder_deltas(root, raw_evals, vid)
    assert counts > 0 and len(deltas) > counts
    assert max(deltas) < 1e-9


def _forecast_deltas(root) -> tuple[float, int]:
    v = fe.VERSIONS["latest"]
    stored = fe._read_t09(root / v["dir"] / fe.F_T09.format(tag=v["tag"]), v["models"])
    frame = fe.forecast_frame(pd.read_csv(root / fe.F_PANEL, parse_dates=["date"]),
                              pd.read_csv(root / fe.F_STATE, parse_dates=["date"]),
                              pd.read_csv(root / fe.F_ROLL, parse_dates=["date"]))
    worst, n = 0.0, 0
    for h in fe.HORIZONS:
        wide = stored[f"{h}m"].reindex(pd.DatetimeIndex(frame["date"]))
        for k, p in fe.SPECS.items():
            ref = wide[k].to_numpy(float)
            mine = fe.expanding_ols_forecasts(frame, h, p)
            worst = max(worst, float(np.nanmax(np.abs(mine - ref))))
            n += int((~np.isnan(ref)).sum())
    return worst, n


@needs_root
def test_meta_parity_equals_the_parity_tests(root, raw_evals, payload):
    """meta.parity in the published JSON is what the parity tests compute; meta.source_sha256 hashes the files."""
    deltas, counts = [], 0
    for vid in ("summary", "latest"):
        d, c = _ladder_deltas(root, raw_evals, vid)
        deltas += d
        counts += c
    tab = payload["meta"]["parity"]["archived_tables"]
    assert (tab["values"], tab["counts"]) == (len(deltas), counts)
    assert tab["max_abs_delta"] == float(f"{max(deltas):.2g}")
    worst, n = _forecast_deltas(root)
    fc = payload["meta"]["parity"]["stored_forecasts"]
    assert fc["n"] == n and fc["max_abs_delta"] == float(f"{worst:.2g}")
    sha = payload["meta"]["source_sha256"]
    v = fe.VERSIONS
    by_label = dict(zip(fe.SOURCE_LABELS, [root / v["summary"]["dir"] / fe.F_T09.format(tag=v["summary"]["tag"]),
                                           root / v["latest"]["dir"] / fe.F_T09.format(tag=v["latest"]["tag"]),
                                           root / fe.F_PANEL, root / fe.F_STATE, root / fe.F_ROLL, root / fe.F_MM23]))
    for label, path in by_label.items():
        assert sha[label] == hashlib.sha256(path.read_bytes()).hexdigest(), label


@needs_root
def test_summary_figures_reproduced_and_not_significant(payload):
    for hk, reported in (("3m", 0.68), ("6m", 3.09)):
        pb = payload["eval"]["summary"][hk]["pairs"]["M4"]["common"]
        assert round(-pb["rel_pct"], 2) == reported
        assert pb["n"] == {"3m": 69, "6m": 66}[hk]
        assert pb["p"] > 0.10 and pb["p_bartlett"] > 0.10       # DM/HLN: not statistically significant
    assert payload["meta"]["summary_reference"]["m4_common_rel_pct"]["3m"] == pytest.approx(-0.6794185, abs=1e-6)


@needs_root
def test_latest_run_on_the_summary_window_isolates_the_evaluation_window(payload):
    """Scoring the latest run's archived forecasts on the summary run's common window (from 2020-01)."""
    rows = {s["horizon"]: s for s in payload["sensitivity"] if s["model"] == "M4" and s["version"] == fe.EVAL_WINDOW_ROW}
    assert set(rows) == {"3m", "6m"} and all(r["window"] == "common" for r in rows.values())
    assert rows["3m"]["first"] == rows["6m"]["first"] == payload["eval"]["summary"]["3m"]["common"]["first"] == "2020-01"
    assert (rows["3m"]["pair_n"], rows["6m"]["pair_n"]) == (69, 66)
    assert round(rows["3m"]["rel_pct"], 2) == 0.51 and round(rows["6m"]["rel_pct"], 2) == -4.04
    assert round(rows["3m"]["p_bartlett"], 2) == 0.89 and round(rows["6m"]["p_bartlett"], 2) == 0.55
    assert round(rows["3m"]["p"], 2) == 0.91 and round(rows["6m"]["p"], 2) == 0.61


@needs_root
def test_sensitivity_columns_report_matched_origins(payload):
    """Every sensitivity cell shows the ratio, n and p on the same origins; the archived own ratio is kept apart."""
    for s in payload["sensitivity"]:
        assert s["rel_pct"] == s["pair_rel_pct"] and s["n"] == s["pair_n"]
        if s["version"] == fe.EVAL_WINDOW_ROW:
            continue
        pb = payload["eval"][s["version"]][s["horizon"]]["pairs"][s["model"]][s["window"]]
        assert s["p"] == pb["p"] and s["pair_n"] == pb["n"]
        if s["window"] == "own":
            assert s["rel_pct_archived"] == payload["eval"][s["version"]][s["horizon"]]["own"][s["model"]]["rel_pct"]
    row = next(s for s in payload["sensitivity"] if (s["model"], s["version"], s["horizon"], s["window"]) == ("M4", "summary", "3m", "own"))
    assert round(row["rel_pct"], 2) == -3.15 and round(row["rel_pct_archived"], 2) == -2.77 and row["pair_n"] == 184


@needs_root
def test_p_value_inventory_and_nested_flags(payload):
    pv = payload["meta"]["p_values"]
    assert pv == {"count": 80, "below_5pct": 0, "below_5pct_bartlett": 1, "min_p": pytest.approx(0.06857, abs=1e-5)}
    m6 = payload["eval"]["observed"]["6m"]["pairs"]["M6"]["common"]
    assert round(m6["rel_pct"], 2) == 6.81 and round(m6["p"], 2) == 0.07 and round(m6["p_bartlett"], 2) == 0.02
    assert {m["key"] for m in payload["models"] if m["nested_with_baseline"]} == {"M0", "M1", "M6"}
    for vid in fe.VERSION_ORDER:
        for hk in ("3m", "6m"):
            for m, pair in payload["eval"][vid][hk]["pairs"].items():
                assert pair["common"]["nested"] == (m in {"M0", "M1", "M6"})
    assert next(v for v in payload["versions"] if v["id"] == "observed")["status"] == "COMPUTED_VARIANT"


@needs_root
def test_cumulative_gap_builds_2018_to_2020_and_partly_reverses(payload):
    """Backs the takeaway: year-by-year increments of the latest run's M4-M2 running loss difference (common window)."""
    sm = payload["persistence"]["smoothed"]
    on = [str(p) for p, v in zip(pd.period_range(sm["start"], periods=len(sm["signal"]), freq="M"), sm["signal"]) if v]
    assert (on[0], on[-1]) == ("2013-09", "2018-02")
    inc = {}
    for hk in ("3m", "6m"):
        pb = payload["eval"]["latest"][hk]["pairs"]["M4"]["common"]
        s = pd.Series(pb["cum"]["v"], index=pd.period_range(pb["cum"]["start"], periods=len(pb["cum"]["v"]), freq="M"))
        ye = s.groupby(s.index.year).last()
        inc[hk] = (ye - ye.shift(1).fillna(0.0)).to_dict()
        assert all(inc[hk][y] > 0 for y in (2018, 2019, 2020)), (hk, inc[hk])
        assert inc[hk][2021] < 0 and inc[hk][2016] < 0 and inc[hk][2017] < 0
    assert inc["6m"][2022] < 0
    assert inc["6m"][2020] < inc["6m"][2019]                   # 2020 is not where most of the 6m gap arose


@needs_root
def test_version_difference_is_reported(payload):
    summary = payload["eval"]["summary"]["3m"]["pairs"]["M4"]["common"]
    latest = payload["eval"]["latest"]["3m"]["pairs"]["M4"]["common"]
    assert summary["rel_pct"] < 0 < latest["rel_pct"]            # the sign of the comparison flips across versions
    assert latest["rel_pct"] == pytest.approx(2.987168553929492, abs=1e-4)
    rows = [s for s in payload["sensitivity"] if s["model"] == "M4"]
    assert {(s["version"], s["horizon"], s["window"]) for s in rows} == {
        (v, h, w) for v in fe.VERSION_ORDER for h in ("3m", "6m") for w in ("own", "common")} | {
        (fe.EVAL_WINDOW_ROW, h, "common") for h in ("3m", "6m")}
    dv = payload["meta"]["default_view"]
    assert payload["eval"][dv["version"]][dv["horizon"]]["pairs"][dv["model"]][dv["window"]]["rel_pct"] > 0   # default view does not lead with a gain


@needs_root
def test_forecasts_reproduced_from_processed_inputs(root):
    """The archived latest run's forecasts are re-estimated here to 1e-10; observed-outcomes training differs."""
    v = fe.VERSIONS["latest"]
    stored = fe._read_t09(root / v["dir"] / fe.F_T09.format(tag=v["tag"]), v["models"])
    frame = fe.forecast_frame(pd.read_csv(root / fe.F_PANEL, parse_dates=["date"]),
                              pd.read_csv(root / fe.F_STATE, parse_dates=["date"]),
                              pd.read_csv(root / fe.F_ROLL, parse_dates=["date"]))
    for h in fe.HORIZONS:
        wide = stored[f"{h}m"].reindex(pd.DatetimeIndex(frame["date"]))
        for k, p in fe.SPECS.items():
            mine = fe.expanding_ols_forecasts(frame, h, p)
            ref = wide[k].to_numpy(float)
            assert np.array_equal(np.isnan(mine), np.isnan(ref)), (h, k)
            assert np.nanmax(np.abs(mine - ref)) < 1e-10, (h, k)
            safe = fe.expanding_ols_forecasts(frame, h, p, observed_only=True)
            first = lambda a: int(np.flatnonzero(~np.isnan(a))[0])
            assert first(safe) == first(ref) + h - 1, (h, k)        # h-1 fewer usable training rows at the start
            both = ~np.isnan(safe) & ~np.isnan(ref)
            assert np.nanmax(np.abs(safe[both] - ref[both])) > 1e-6, (h, k)


@needs_root
def test_state_split_only_where_the_state_inputs_exist(payload):
    for vid in fe.VERSION_ORDER:
        for hk in ("3m", "6m"):
            for m, pair in payload["eval"][vid][hk]["pairs"].items():
                for w in ("own", "common"):
                    pb = pair[w]
                    assert len(pb["cum"]["v"]) == pb["n"]
                    # the cumulative series is the running sum of d_t = e_model^2 - e_M2^2
                    assert pb["cum"]["v"][-1] == pytest.approx(pb["n"] * pb["mean_d"], rel=1e-3, abs=1e-3)
                    if vid == "summary":
                        assert "by_state" not in pb
                    else:
                        assert sum(s["n"] for s in pb["by_state"]) == pb["n"]


@needs_root
def test_payload_is_public_safe_and_lean(payload):
    text = json.dumps(payload, allow_nan=False)
    parts, pats = _private_tokens()
    assert parts and pats, "expected at least one configured private name to guard against"
    for bad in FORBIDDEN + tuple(parts):
        assert bad not in text, bad
    for pat in pats:
        assert not pat.search(text), pat.pattern
    assert len(text.encode()) < 200_000
    assert payload["meta"]["data_through"] == "2025-12"
    assert payload["persistence"]["cpi"]["cdid"] == {"goods": "D7NM", "services": "D7NN"}
    assert payload["persistence"]["cpi"]["release_date"] == "2026-02-18"
    assert "deck" not in text.lower()


@needs_root
def test_public_files_carry_no_private_tokens():
    """Pages, partial, generated tables, this module and this test: no private paths or folder names."""
    parts, pats = _private_tokens()
    for f in PUBLIC_FILES:
        text = f.read_text(encoding="utf-8")
        generic = () if f == Path(__file__) else ("/Volumes", "/Users", "PycharmProjects")   # this file lists them
        for bad in generic + tuple(parts):
            assert bad not in text, (f.name, bad)
        for pat in pats:
            assert not pat.search(text), (f.name, pat.pattern)


@needs_root
def test_build_is_deterministic_and_committed_files_match(tmp_path, payload):
    import build_data
    from sources import load_sources
    again = fe.build(load_sources(CONFIG))
    assert build_data._stable(again) == build_data._stable(payload)
    if COMMITTED.exists():
        assert build_data._stable(json.loads(COMMITTED.read_text(encoding="utf-8"))) == build_data._stable(payload)
        for rel, lang in ((fe.TABLE_PATH, "en"), (fe.TABLE_PATH_ZH, "zh")):
            assert (WEB / "site" / rel).read_text(encoding="utf-8") == fe.table_markdown(payload, lang)
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "forecast_eval",
            "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img"), "--site-dir", str(tmp_path / "site")]
    res = subprocess.run(base, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert (tmp_path / "img" / "forecast_eval.png").exists()
    assert (tmp_path / "site" / fe.TABLE_PATH_ZH).exists()
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
