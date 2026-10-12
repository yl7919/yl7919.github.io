"""Macro forecast evaluation: UK services inflation, archived research example (February 2026).

Source: the author's own replication folder for a February 2026 UK services-inflation study
(optional root `uk_inflation`). Two archived output versions are evaluated from their per-origin
pseudo-out-of-sample records (table T09: date, horizon, model_key, model_label, y, yhat, error):

- `summary` run of 23 Feb 2026, sample 2005-2025, models M0-M5: the version behind the author's
            February 2026 research summary (its common-window RMSE changes of 0.68% and 3.09% for M4
            against M2).
- `latest`  run of 24 Feb 2026, sample 2001-2025, models M0-M6 (M6 = "M4v2", regime-gated).

A third version, `observed`, is re-estimated here at build time from the archived processed inputs of
the latest run with one change: at each forecast origin the training sample keeps only rows whose
h-month-ahead outcome had already been observed at that origin (the archived protocol also used the
last h-1 rows, whose outcomes fall after the origin). Nothing else changes: the smoothed state, the
full-sample z-scores and the latest data vintage remain, so this version is NOT free of look-ahead.
With that restriction switched off the same code reproduces the latest run's stored forecasts (tested
to 1e-10). It is a new variant, not an archived result.

Everything below the forecasts is computed here and is what the page shows: n, RMSE, MAE and
directional accuracy per model on each model's own window and on the common window of the archived
tables; RMSE relative to the fixed-specification baseline M2; Diebold-Mariano tests of equal
squared-error loss with the original DM long-run variance (equal weights on autocovariances 1..h-1,
Bartlett weights only if that estimate is not positive) and the Harvey-Leybourne-Newbold small-sample
correction (Student t, T-1 degrees of freedom), plus the p-value with a Bartlett (Newey-West) variance
as a sensitivity; the cumulative squared-error differential by origin; errors split by the lagged
durable-signal state. The cumulative series is the running sum of d_t, so it rises when the model's
squared error exceeds M2's. The signal comes from the SMOOTHED state-space estimate, which uses the whole
sample: it is a retrospective classification, not known at the origin.

M0 (zero forecast change) and M1 are nested in M2, and M2 in M6; for nested pairs under recursive
estimation the DM reference distribution is not exact (Clark-McCracken), so those p-values are
indicative only.

Public JSON carries aggregates, per-origin cumulative differentials and monthly persistence/CPI series
(ONS data under the Open Government Licence; the author's own model outputs), plus a recomputation record
in meta: SHA-256 hashes of the source files (keyed by descriptive labels), the parity of the unrounded
metrics with the archived model-comparison tables (tolerance 1e-9) and of the re-estimated forecasts with
the latest run's stored forecasts (tolerance 1e-10), the exhibit version and the SHA-256 of this module.
A build fails if either parity check fails. No local paths and no archive file names.
"""
from __future__ import annotations

import hashlib
import math
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from common import provenance, round_sig

ROOT = "uk_inflation"
LAYOUT = "uk_inflation_layout"
LAYOUT_KEYS = ("summary_dir", "latest_dir", "t06", "t08", "t09", "t10", "panel", "state", "rolling")


def _private_layout() -> dict:
    """Folder and file names of the archive, read from the git-ignored sources.toml [uk_inflation_layout];
    they are never stored in this tracked file."""
    try:
        from sources import DEFAULT_CONFIG
        with open(DEFAULT_CONFIG, "rb") as fh:
            return dict(tomllib.load(fh).get(LAYOUT, {}))
    except (ImportError, FileNotFoundError):
        return {}


_L = _private_layout()
VERSIONS = {
    "summary": {
        "dir": _L.get("summary_dir", ""),
        "tag": "2005-2025",
        "run_date": "2026-02-23",
        "sample": ["2005-01", "2025-12"],
        "models": ["M0", "M1", "M2", "M3", "M4", "M5"],
        "common_set": ["M1", "M2", "M3", "M4", "M5"],
    },
    "latest": {
        "dir": _L.get("latest_dir", ""),
        "tag": "2001-2025",
        "run_date": "2026-02-24",
        "sample": ["2001-01", "2025-12"],
        "models": ["M0", "M1", "M2", "M3", "M4", "M5", "M6"],
        "common_set": ["M1", "M2", "M3", "M4", "M5", "M6"],
    },
}
OBSERVED = {"run_date": None, "sample": ["2001-01", "2025-12"],
          "models": ["M0", "M1", "M2", "M3", "M4", "M5", "M6"],
          "common_set": ["M1", "M2", "M3", "M4", "M5", "M6"]}
VERSION_ORDER = ["latest", "summary", "observed"]
SENS_MODELS = ("M4", "M5", "M3", "M6", "M1", "M0")   # every model compared with M2 in the selector
NESTED = {"M0", "M1", "M6"}           # M0 (zero forecast) and M1 are nested in M2, M2 in M6: DM reference not exact (Clark-McCracken)
HORIZONS = [3, 6]
BASELINE = "M2"
MIN_TRAIN = 60
F_T06, F_T08, F_T09, F_T10 = (_L.get(k, "") for k in ("t06", "t08", "t09", "t10"))
F_PANEL, F_STATE, F_ROLL = (_L.get(k, "") for k in ("panel", "state", "rolling"))
# Descriptive labels published in meta.source_files and meta.source_sha256 instead of the archive's file names.
SOURCE_LABELS = ["per-origin forecasts, research-summary run (23 Feb 2026)",
                 "per-origin forecasts, latest run (24 Feb 2026)",
                 "processed monthly panel", "state-space persistence estimates", "rolling persistence estimates",
                 "ONS MM23 CPI release (18 Feb 2026)",
                 "model-comparison table, own windows, research-summary run (23 Feb 2026)",
                 "pairwise RMSE comparison table, research-summary run (23 Feb 2026)",
                 "model-comparison table, common window, research-summary run (23 Feb 2026)",
                 "model-comparison table, own windows, latest run (24 Feb 2026)",
                 "pairwise RMSE comparison table, latest run (24 Feb 2026)",
                 "model-comparison table, common window, latest run (24 Feb 2026)"]
EXHIBIT_VERSION = "2026.10.12"     # bump when the computation or the payload layout changes
PARITY_TOL_TABLES = 1e-9           # unrounded metrics against the archived model-comparison tables
PARITY_TOL_FORECASTS = 1e-10       # re-estimated forecasts against the latest run's stored forecasts
F_MM23 = "data/raw/ons/cpi_mm23_20260224.csv"
MM23_GOODS = "CPI ANNUAL RATE: Goods 2015=100"
MM23_SERVICES = "CPI ANNUAL RATE: Services 2015=100"
CPI_START = "2001-01"
TABLE_PATH = "projects/_tbl-forecast-eval.md"          # relative to --site-dir; the zh twin sits beside it
TABLE_PATH_ZH = "projects/_tbl-forecast-eval-zh.md"
DEFAULT_VIEW = {"version": "latest", "horizon": "3m", "model": "M4", "window": "common"}

# Predictors (exactly those in the archived model code; *_l1 = value of the previous month).
SPECS = {
    "M1": ("pi_services_yoy",),
    "M2": ("pi_services_yoy", "wage_z", "slack_z"),
    "M3": ("pi_services_yoy", "wage_z", "rho_smoothed_l1"),
    "M4": ("pi_services_yoy", "wage_z", "signal_on_l1"),
    "M5": ("pi_services_yoy", "wage_z", "rho_rolling_l1"),
    "M6": ("pi_services_yoy", "wage_z", "slack_z", "signal_on_l1", "signal_pi_l1", "signal_wage_l1"),
}
MODELS = {
    "M0": {"en": "No change", "zh": "不变预测",
           "pred_en": "forecast change set to zero", "pred_zh": "预测变化设为零"},
    "M1": {"en": "AR(1)-style", "zh": "AR(1) 式模型",
           "pred_en": "services inflation at the origin", "pred_zh": "预测起点的服务业通胀"},
    "M2": {"en": "Fixed-specification Phillips-style baseline", "zh": "设定固定的菲利普斯式基准",
           "pred_en": "services inflation, wage growth, labour-market slack",
           "pred_zh": "服务业通胀、工资增速、劳动力市场松紧度"},
    "M3": {"en": "Slack replaced by smoothed persistence", "zh": "以平滑持续性替代松紧度",
           "pred_en": "services inflation, wage growth, smoothed persistence estimate (previous month)",
           "pred_zh": "服务业通胀、工资增速、平滑持续性估计（上月）"},
    "M4": {"en": "Slack replaced by durable signal", "zh": "以持久信号替代松紧度",
           "pred_en": "services inflation, wage growth, durable signal from the smoothed estimate (previous month)",
           "pred_zh": "服务业通胀、工资增速、由平滑估计得到的持久信号（上月）"},
    "M5": {"en": "Slack replaced by rolling persistence", "zh": "以滚动持续性替代松紧度",
           "pred_en": "services inflation, wage growth, rolling 120-month persistence estimate (previous month)",
           "pred_zh": "服务业通胀、工资增速、滚动 120 个月持续性估计（上月）"},
    "M6": {"en": "Regime-gated Phillips (M4v2)", "zh": "信号分段菲利普斯（M4v2）",
           "pred_en": "M2's predictors plus the signal (previous month) and its interactions with inflation and wages",
           "pred_zh": "M2 的预测变量，加上信号（上月）及其与通胀、工资的交互项"},
}
VERSION_LABELS = {
    "summary": {"en": "Research-summary run (23 Feb 2026; sample from 2005)",
                "zh": "研究摘要版本（2026 年 2 月 23 日运行；样本始于 2005 年）"},
    "latest": {"en": "Latest archived run (24 Feb 2026; sample from 2001)",
               "zh": "最新存档版本（2026 年 2 月 24 日运行；样本始于 2001 年）"},
    "observed": {"en": "Latest inputs, trained only on outcomes observed by the origin (computed at build time)",
                 "zh": "最新输入、仅用起点前已观测结果训练（构建时计算）"},
}
EVAL_WINDOW_ROW = "latest_on_summary_window"     # sensitivity row: latest run scored on the summary run's common window
EVAL_WINDOW_LABELS = {"en": "Latest run, scored on the research-summary run's common window",
                      "zh": "最新版本，按研究摘要版本的共同窗口计分"}


# ------------------------------------------------------------------------------------------- statistics

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularised incomplete beta function (modified Lentz)."""
    tiny, eps = 1e-300, 1e-15
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b) for a, b > 0 and 0 <= x <= 1."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    """Two-sided p-value of a Student t statistic: P(|T| >= |t|) = I_{df/(df+t^2)}(df/2, 1/2)."""
    if not math.isfinite(t):
        return 0.0
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def newey_west_lrv(d: np.ndarray, lag: int) -> float:
    """Long-run variance of d: gamma_0 + 2 sum_{k=1..lag} (1 - k/(lag+1)) gamma_k, gamma_k = (1/T) sum (d_t - mean)(d_{t-k} - mean)."""
    d = np.asarray(d, dtype=float)
    T = d.size
    u = d - d.mean()
    lrv = float(u @ u) / T
    for k in range(1, min(lag, T - 1) + 1):
        lrv += 2.0 * (1.0 - k / (lag + 1.0)) * float(u[k:] @ u[:-k]) / T
    return lrv


def rectangular_lrv(d: np.ndarray, lag: int) -> float:
    """Original DM long-run variance: gamma_0 + 2 sum_{k=1..lag} gamma_k (equal weights, truncated at lag)."""
    d = np.asarray(d, dtype=float)
    T = d.size
    u = d - d.mean()
    lrv = float(u @ u) / T
    for k in range(1, min(lag, T - 1) + 1):
        lrv += 2.0 * float(u[k:] @ u[:-k]) / T
    return lrv


def _hln_p(d: np.ndarray, lrv: float, h: int) -> tuple[float, float, float]:
    T = d.size
    dm = float(d.mean() / math.sqrt(lrv / T)) if lrv > 0 else float("nan")
    k = math.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)
    hln = dm * k
    return dm, hln, t_two_sided_p(hln, T - 1)


def diebold_mariano(e_model: np.ndarray, e_base: np.ndarray, h: int) -> dict:
    """DM test of equal mean squared error, d_t = e_model^2 - e_base^2 (positive = model has larger loss).

    Long-run variance as in Diebold and Mariano (1995) and Harvey, Leybourne and Newbold (1997): equal
    weights on the autocovariances up to lag h-1 ("rectangular"); if that estimate is not positive, the
    Newey-West (Bartlett) estimate is used instead. HLN correction:
    DM* = DM * sqrt((T + 1 - 2h + h(h-1)/T) / T), compared with Student t on T-1 degrees of freedom.
    `p_bartlett` is the same statistic with the Bartlett variance, reported as a sensitivity.
    """
    e1, e0 = np.asarray(e_model, float), np.asarray(e_base, float)
    if e1.shape != e0.shape:
        raise ValueError("diebold_mariano: error vectors must be aligned")
    d = e1 ** 2 - e0 ** 2
    T = d.size
    if T < 3:
        raise ValueError("diebold_mariano: need at least 3 paired errors")
    lrv_b = newey_west_lrv(d, h - 1)
    lrv_r = rectangular_lrv(d, h - 1)
    kernel = "rectangular" if lrv_r > 0 else "bartlett"
    dm, hln, p = _hln_p(d, lrv_r if kernel == "rectangular" else lrv_b, h)
    _, hln_b, p_b = _hln_p(d, lrv_b, h)
    return {"n": int(T), "mean_d": float(d.mean()), "dm": dm, "hln": hln, "p": p, "lag": int(h - 1),
            "kernel": kernel, "hln_bartlett": hln_b, "p_bartlett": p_b}


def metrics(y: np.ndarray, yhat: np.ndarray) -> dict:
    """Archived definitions: RMSE, MAE, directional accuracy = share with sign(y) == sign(yhat)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    e = y - yhat
    return {"n": int(y.size), "rmse": float(np.sqrt(np.mean(e ** 2))), "mae": float(np.mean(np.abs(e))),
            "dir": float(np.mean(np.sign(y) == np.sign(yhat)))}


# ------------------------------------------------------------------------------------------- forecasts

def forecast_frame(panel: pd.DataFrame, state: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    """The archived forecast frame: monthly panel plus lagged persistence predictors."""
    f = panel[["date", "pi_services_yoy", "wage_z", "slack_z"]].merge(
        state[["date", "rho_smoothed", "signal_on"]], on="date", how="left").merge(
        rolling[["date", "rho_hat"]], on="date", how="left").sort_values("date").reset_index(drop=True)
    f["rho_smoothed_l1"] = f["rho_smoothed"].shift(1)
    f["rho_rolling_l1"] = f["rho_hat"].shift(1)
    f["signal_on_l1"] = f["signal_on"].shift(1)
    f["signal_pi_l1"] = f["signal_on_l1"] * f["pi_services_yoy"]
    f["signal_wage_l1"] = f["signal_on_l1"] * f["wage_z"]
    return f


def expanding_ols_forecasts(frame: pd.DataFrame, h: int, predictors: tuple[str, ...], *,
                            min_train: int = MIN_TRAIN, observed_only: bool = False) -> np.ndarray:
    """Direct h-month forecasts of y_t = pi_{t+h} - pi_t by expanding-window OLS with an intercept.

    At origin i the training rows are j < i with complete data (the archived rule) or, with
    observed_only=True, j <= i - h, so that every training outcome pi_{j+h} is observed by the origin.
    At least `min_train` usable rows are required.
    """
    pi = frame["pi_services_yoy"].to_numpy(float)
    y = np.full(pi.size, np.nan)
    y[:-h] = pi[h:] - pi[:-h]
    X = frame[list(predictors)].to_numpy(float)
    ok_rows = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    pred = np.full(pi.size, np.nan)
    for i in range(min_train, pi.size):
        if np.isnan(X[i]).any():
            continue
        end = i - h + 1 if observed_only else i
        if end <= 0:
            continue
        tr = ok_rows[:end]
        if tr.sum() < min_train:
            continue
        A = np.column_stack([np.ones(int(tr.sum())), X[:end][tr]])
        beta = np.linalg.lstsq(A, y[:end][tr], rcond=None)[0]
        pred[i] = beta[0] + X[i] @ beta[1:]
    return pred


# ------------------------------------------------------------------------------------------- inputs

def _root(sources) -> Path:
    """The uk_inflation root: from Sources when registered there, else from the same sources.toml."""
    base = getattr(sources, "extra", {}).get(ROOT)
    if base is not None:
        return Path(base)
    from sources import DEFAULT_CONFIG
    with open(DEFAULT_CONFIG, "rb") as fh:
        roots = tomllib.load(fh).get("roots", {})
    if ROOT not in roots:
        raise KeyError(f"sources.toml [roots] has no '{ROOT}'; add it to use this exhibit")
    p = Path(roots[ROOT]).expanduser()
    if not p.is_dir():
        raise FileNotFoundError(f"{ROOT} directory does not exist: {p}")
    return p


def _file(root: Path, rel: str) -> Path:
    p = root / rel
    if not p.exists():
        raise FileNotFoundError(f"{ROOT} file not found: {rel}")
    return p


def _month(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m")


def _read_t09(path: Path, models: list[str]) -> dict:
    """{horizon: DataFrame indexed by origin date with columns y, <model>...} from a T09 file."""
    t = pd.read_csv(path, parse_dates=["date"])
    got = sorted(t["model_key"].unique())
    if got != sorted(models):
        raise ValueError(f"{path.name}: models {got}, expected {models}")
    out = {}
    for h in HORIZONS:
        s = t[t["horizon"] == f"{h}m"]
        wide = s.pivot(index="date", columns="model_key", values="yhat").sort_index()
        ys = s.drop_duplicates("date").set_index("date")["y"].sort_index()
        if (s.groupby("date")["y"].nunique(dropna=False) > 1).any():
            raise ValueError(f"{path.name}: y differs across models at some origin ({h}m)")
        err = (s["y"] - s["yhat"]) - s["error"]
        if np.nanmax(np.abs(err.to_numpy(float))) > 1e-9:
            raise ValueError(f"{path.name}: error column is not y - yhat ({h}m)")
        wide["y"] = ys
        out[f"{h}m"] = wide
    return out


def _observed_version(frame: pd.DataFrame) -> dict:
    dates = pd.DatetimeIndex(frame["date"])
    pi = frame["pi_services_yoy"].to_numpy(float)
    out = {}
    for h in HORIZONS:
        y = np.full(pi.size, np.nan)
        y[:-h] = pi[h:] - pi[:-h]
        wide = pd.DataFrame(index=dates)
        wide["M0"] = np.where(np.isnan(y), np.nan, 0.0)
        for k, p in SPECS.items():
            wide[k] = expanding_ols_forecasts(frame, h, p, observed_only=True)
        wide["y"] = y
        out[f"{h}m"] = wide
    return out


def _mm23(path: Path) -> dict:
    df = pd.read_csv(path, dtype=str, low_memory=False)
    first = df.columns[0]
    for col in (MM23_GOODS, MM23_SERVICES):
        if col not in df.columns:
            raise ValueError(f"{path.name}: column {col!r} missing")
    meta = df.set_index(first)
    cdid = (meta.loc["CDID", MM23_GOODS], meta.loc["CDID", MM23_SERVICES])
    if cdid != ("D7NM", "D7NN"):
        raise ValueError(f"{path.name}: unexpected CDIDs {cdid}")
    release = meta.loc["Release Date", MM23_SERVICES]
    rows = df[df[first].str.match(r"^\d{4} [A-Z]{3}$", na=False)].copy()
    rows["date"] = pd.to_datetime(rows[first], format="%Y %b")
    rows = rows[rows["date"] >= pd.Timestamp(CPI_START + "-01")].sort_values("date")
    months = rows["date"].dt.strftime("%Y-%m").tolist()
    _assert_monthly(months, path.name)
    return {"start": months[0], "end": months[-1], "release_date": pd.to_datetime(release, dayfirst=True).strftime("%Y-%m-%d"),
            "goods": [float(v) for v in rows[MM23_GOODS]], "services": [float(v) for v in rows[MM23_SERVICES]],
            "cdid": {"goods": "D7NM", "services": "D7NN"}}


def _assert_monthly(months: list[str], what: str) -> None:
    idx = pd.PeriodIndex(months, freq="M")
    if len(idx) > 1 and not (np.diff(idx.asi8) == 1).all():
        raise ValueError(f"{what}: months are not consecutive")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------- parity

def table_parity(raw: dict, t06: pd.DataFrame, t08: pd.DataFrame, t10: pd.DataFrame) -> dict:
    """Unrounded metrics of one archived run (evaluate_version(...)[h]["_raw"]) against its archived tables.

    Own windows (T06): n, RMSE, MAE, directional accuracy. Pairwise table (T08): the model's, M1's and M2's
    own-window RMSE and the RMSE improvements against M1 and M2 (%). Common window (T10): n, RMSE, MAE,
    directional accuracy, M2's RMSE and the improvement against M2 (%). Counts must match exactly; returns the
    largest absolute difference over the real-valued cells and the number of cells compared.
    """
    deltas: list[float] = []
    counts = 0
    for _, r in t06.iterrows():
        mine = raw[r["horizon"]]["_raw"]["own"][r["model_key"]]
        if mine["n"] != int(r["n_oos"]):
            raise ValueError(f"parity: own-window n {mine['n']} != {r['n_oos']} ({r['horizon']}, {r['model_key']})")
        counts += 1
        deltas += [abs(mine["rmse"] - r["rmse"]), abs(mine["mae"] - r["mae"]), abs(mine["dir"] - r["directional_acc"])]
    for _, r in t08.iterrows():
        o = raw[r["horizon"]]["_raw"]["own"]
        k = r["model_key"]
        vs_m1 = (o["M1"]["rmse"] - o[k]["rmse"]) / o["M1"]["rmse"] * 100.0
        deltas += [abs(o[k]["rmse"] - r["rmse_model"]), abs(o["M1"]["rmse"] - r["rmse_M1"]),
                   abs(o[BASELINE]["rmse"] - r["rmse_M2"]), abs(-o[k]["rel_pct"] - r["rmse_impr_vs_M2_pct"]),
                   abs(vs_m1 - r["rmse_impr_vs_M1_pct"])]
    for _, r in t10.iterrows():
        c = raw[r["horizon"]]["_raw"]["common"]
        mine = c[r["model_key"]]
        if mine["n"] != int(r["common_n_oos"]):
            raise ValueError(f"parity: common-window n {mine['n']} != {r['common_n_oos']} ({r['horizon']}, {r['model_key']})")
        counts += 1
        deltas += [abs(mine["rmse"] - r["common_rmse"]), abs(mine["mae"] - r["common_mae"]),
                   abs(mine["dir"] - r["common_directional_acc"]), abs(c[BASELINE]["rmse"] - r["common_rmse_M2"]),
                   abs(-mine["rel_pct"] - r["common_rmse_impr_vs_M2_pct"])]
    if not deltas or not all(math.isfinite(d) for d in deltas):
        raise ValueError("parity: missing or non-finite values in the archived tables")
    return {"max_abs_delta": max(deltas), "values": len(deltas), "counts": counts}


def forecast_parity(frame: pd.DataFrame, stored: dict) -> dict:
    """Forecasts of M1-M6 re-estimated by expanding_ols_forecasts (archived training rule) against the stored
    per-origin forecasts of the same run ({horizon: wide frame} from _read_t09)."""
    dates = pd.DatetimeIndex(frame["date"])
    worst, n = 0.0, 0
    for h in HORIZONS:
        wide = stored[f"{h}m"]
        if not wide.index.isin(dates).all():
            raise ValueError(f"parity: stored {h}m forecasts on origins outside the processed panel")
        wide = wide.reindex(dates)
        for k, p in SPECS.items():
            mine = expanding_ols_forecasts(frame, h, p)
            ref = wide[k].to_numpy(float)
            if not np.array_equal(np.isnan(mine), np.isnan(ref)):
                raise ValueError(f"parity: re-estimated {k} {h}m forecasts cover different origins")
            ok = ~np.isnan(ref)
            worst = max(worst, float(np.max(np.abs(mine[ok] - ref[ok]))))
            n += int(ok.sum())
    return {"max_abs_delta": worst, "n": n}


# ------------------------------------------------------------------------------------------- evaluation

def _r(x: float, digits: int = 6) -> float | None:
    if x is None or not math.isfinite(x):
        return None
    return round_sig(float(x), digits)


def _segment(dates: pd.DatetimeIndex) -> tuple[str, str]:
    months = [_month(d) for d in dates]
    _assert_monthly(months, "evaluation window")
    return months[0], months[-1]


def _pair_block(wide: pd.DataFrame, model: str, mask: np.ndarray, h: int, signal: pd.Series | None) -> dict:
    sub = wide.loc[mask]
    e_m = (sub["y"] - sub[model]).to_numpy(float)
    e_b = (sub["y"] - sub[BASELINE]).to_numpy(float)
    first, last = _segment(sub.index)
    dm = diebold_mariano(e_m, e_b, h)
    cum = np.cumsum(e_m ** 2 - e_b ** 2)          # cumulative d_t, the DM loss differential
    rm, rb = math.sqrt(np.mean(e_m ** 2)), math.sqrt(np.mean(e_b ** 2))
    block = {"n": dm["n"], "first": first, "last": last, "rmse": _r(rm), "rmse_base": _r(rb),
             "rel_pct": _r(100.0 * (rm / rb - 1.0)), "mean_d": _r(dm["mean_d"]), "dm": _r(dm["dm"], 4),
             "hln": _r(dm["hln"], 4), "p": _r(dm["p"], 4), "kernel": dm["kernel"],
             "hln_bartlett": _r(dm["hln_bartlett"], 4), "p_bartlett": _r(dm["p_bartlett"], 4),
             "nested": model in NESTED,
             "cum": {"start": first, "v": [round(float(v), 4) for v in cum]}}
    if signal is not None:
        s = signal.reindex(sub.index).to_numpy(float)
        states = []
        for st in (0, 1):
            m = s == st
            if m.sum() == 0:
                states.append({"state": st, "n": 0})
                continue
            a, b = math.sqrt(np.mean(e_m[m] ** 2)), math.sqrt(np.mean(e_b[m] ** 2))
            states.append({"state": st, "n": int(m.sum()), "rmse": _r(a), "rmse_base": _r(b),
                           "rel_pct": _r(100.0 * (a / b - 1.0))})
        if int(np.isnan(s).sum()):
            raise ValueError("signal missing on an evaluation origin")
        block["by_state"] = states
    return block


def evaluate_version(preds: dict, models: list[str], common_set: list[str], signal: pd.Series | None) -> dict:
    out = {}
    h_map = {f"{h}m": h for h in HORIZONS}
    for hk, wide in preds.items():
        h = h_map[hk]
        y_ok = wide["y"].notna().to_numpy()
        own = {}
        for m in models:
            mask = y_ok & wide[m].notna().to_numpy()
            met = metrics(wide.loc[mask, "y"], wide.loc[mask, m])
            first, last = _month(wide.index[mask][0]), _month(wide.index[mask][-1])
            own[m] = {**met, "first": first, "last": last}
        common_mask = y_ok & wide[common_set].notna().all(axis=1).to_numpy()
        c_first, c_last = _segment(wide.index[common_mask])
        common = {m: metrics(wide.loc[common_mask, "y"], wide.loc[common_mask, m]) for m in models}
        for block in (own, common):
            for m in models:
                block[m]["rel_pct"] = 100.0 * (block[m]["rmse"] / block[BASELINE]["rmse"] - 1.0)
        pairs = {}
        for m in models:
            if m == BASELINE:
                continue
            pair_mask = y_ok & wide[m].notna().to_numpy() & wide[BASELINE].notna().to_numpy()
            pairs[m] = {"own": _pair_block(wide, m, pair_mask, h, signal),
                        "common": _pair_block(wide, m, common_mask, h, signal)}
        out[hk] = {
            "own": {m: {k: (_r(v) if isinstance(v, float) else v) for k, v in own[m].items()} for m in models},
            "common": {"n": int(common_mask.sum()), "first": c_first, "last": c_last,
                       "models": {m: {k: (_r(v) if isinstance(v, float) else v) for k, v in common[m].items()} for m in models}},
            "pairs": pairs,
            "_raw": {"own": own, "common": common},       # unrounded, for the parity tests; dropped from the payload
        }
    return out


# ------------------------------------------------------------------------------------------- build

def build(sources) -> dict:
    missing = [k for k in LAYOUT_KEYS if not _L.get(k)]
    if missing:
        raise KeyError(f"sources.toml [{LAYOUT}] lacks {missing}; see pipeline/sources.example.toml")
    root = _root(sources)
    files: list[Path] = []
    preds, specs = {}, {}
    for vid, v in VERSIONS.items():
        p = _file(root, f"{v['dir']}/{F_T09.format(tag=v['tag'])}")
        files.append(p)
        preds[vid] = _read_t09(p, v["models"])
        specs[vid] = v
    p_panel, p_state, p_roll = _file(root, F_PANEL), _file(root, F_STATE), _file(root, F_ROLL)
    p_mm23 = _file(root, F_MM23)
    files += [p_panel, p_state, p_roll, p_mm23]
    tables = {}
    for vid, v in VERSIONS.items():
        tables[vid] = [_file(root, f"{v['dir']}/{f.format(tag=v['tag'])}") for f in (F_T06, F_T08, F_T10)]
        files += tables[vid]
    panel = pd.read_csv(p_panel, parse_dates=["date"])
    state = pd.read_csv(p_state, parse_dates=["date"])
    rolling = pd.read_csv(p_roll, parse_dates=["date"])
    frame = forecast_frame(panel, state, rolling)
    preds["observed"] = _observed_version(frame)
    specs["observed"] = OBSERVED
    signal = frame.set_index("date")["signal_on_l1"]

    evals, t_parity = {}, []
    for vid in VERSION_ORDER:
        sig = None if vid == "summary" else signal       # the summary run's state inputs were overwritten on 24 Feb
        ev = evaluate_version(preds[vid], specs[vid]["models"], specs[vid]["common_set"], sig)
        if vid in tables:
            t_parity.append(table_parity(ev, *(pd.read_csv(t) for t in tables[vid])))
        for hk in ev:
            ev[hk].pop("_raw")
        evals[vid] = ev
    f_parity = forecast_parity(frame, preds["latest"])
    t_worst = max(t["max_abs_delta"] for t in t_parity)
    if t_worst >= PARITY_TOL_TABLES or f_parity["max_abs_delta"] >= PARITY_TOL_FORECASTS:
        raise ValueError(f"archive parity fails: tables {t_worst:.3g} (tolerance {PARITY_TOL_TABLES:g}), "
                         f"forecasts {f_parity['max_abs_delta']:.3g} (tolerance {PARITY_TOL_FORECASTS:g})")
    parity = {
        "archived_tables": {"runs": list(VERSIONS), "tolerance": PARITY_TOL_TABLES,
                            "max_abs_delta": float(f"{t_worst:.2g}"),
                            "values": sum(t["values"] for t in t_parity), "counts": sum(t["counts"] for t in t_parity)},
        "stored_forecasts": {"run": "latest", "models": list(SPECS), "tolerance": PARITY_TOL_FORECASTS,
                             "max_abs_delta": float(f"{f_parity['max_abs_delta']:.2g}"), "n": f_parity["n"]},
    }

    versions = []
    for vid in VERSION_ORDER:
        s = specs[vid]
        versions.append({"id": vid, "en": VERSION_LABELS[vid]["en"], "zh": VERSION_LABELS[vid]["zh"],
                         "run_date": s["run_date"], "sample": s["sample"], "models": s["models"],
                         "common_set": s["common_set"], "state_split": vid != "summary",
                         "archived": vid != "observed",
                         "status": {"summary": "ARCHIVED_EMPIRICAL", "latest": "RUNNABLE_REPRODUCED",
                                    "observed": "COMPUTED_VARIANT"}[vid]})

    # Evaluation-window check: the latest run's own forecasts scored on the summary run's common window, which
    # isolates the evaluation-period part of the difference between the two runs.
    window_rows = {}
    for hk in ("3m", "6m"):
        h = int(hk[:-1])
        sw = preds["summary"][hk]
        s_mask = sw["y"].notna().to_numpy() & sw[specs["summary"]["common_set"]].notna().all(axis=1).to_numpy()
        s_first = sw.index[s_mask][0]
        lw = preds["latest"][hk]
        l_mask = lw["y"].notna().to_numpy() & lw[specs["latest"]["common_set"]].notna().all(axis=1).to_numpy()
        mask = l_mask & (lw.index >= s_first)
        window_rows[hk] = {m: _pair_block(lw, m, mask, h, None) for m in SENS_MODELS}

    sensitivity = []
    for m in SENS_MODELS:
        for vid in VERSION_ORDER + [EVAL_WINDOW_ROW]:
            if vid != EVAL_WINDOW_ROW and m not in specs[vid]["models"]:
                continue
            for hk in ("3m", "6m"):
                for w in ("own", "common"):
                    if vid == EVAL_WINDOW_ROW:
                        if w == "own":
                            continue
                        pb = window_rows[hk][m]
                        sensitivity.append({"model": m, "version": vid, "horizon": hk, "window": w,
                                            "rel_pct": pb["rel_pct"], "n": pb["n"], "n_base": pb["n"],
                                            "pair_n": pb["n"], "pair_rel_pct": pb["rel_pct"], "p": pb["p"],
                                            "p_bartlett": pb["p_bartlett"], "first": pb["first"], "last": pb["last"]})
                        continue
                    pb = evals[vid][hk]["pairs"][m][w]
                    # Every column shows the RMSE ratio, n and p-value on the same matched origins; the
                    # archived own-window ratio (different periods for model and M2) is kept separately.
                    sensitivity.append({"model": m, "version": vid, "horizon": hk, "window": w,
                                        "rel_pct": pb["rel_pct"],
                                        "rel_pct_archived": evals[vid][hk]["own"][m]["rel_pct"] if w == "own" else None,
                                        "n": pb["n"], "n_base": pb["n"],
                                        "pair_n": pb["n"], "pair_rel_pct": pb["rel_pct"], "p": pb["p"],
                                        "p_bartlett": pb["p_bartlett"], "first": pb["first"], "last": pb["last"]})

    smooth = state.dropna(subset=["rho_smoothed"]).sort_values("date")
    roll = rolling.dropna(subset=["rho_hat"]).sort_values("date")
    s_months = [_month(d) for d in smooth["date"]]
    r_months = [_month(d) for d in roll["date"]]
    _assert_monthly(s_months, F_STATE)
    _assert_monthly(r_months, F_ROLL)
    thresholds = smooth["threshold"].unique()
    if thresholds.size != 1:
        raise ValueError(f"{F_STATE}: threshold is not constant")
    persistence = {
        "smoothed": {"start": s_months[0], "end": s_months[-1],
                     "rho": [round(float(v), 4) for v in smooth["rho_smoothed"]],
                     "lo": [round(float(v), 4) for v in smooth["rho_low68"]],
                     "hi": [round(float(v), 4) for v in smooth["rho_high68"]],
                     "signal": [int(v) for v in smooth["signal_on"]]},
        "threshold": round(float(thresholds[0]), 4),
        "rolling": {"start": r_months[0], "end": r_months[-1], "window": 120,
                    "rho": [round(float(v), 4) for v in roll["rho_hat"]],
                    "se": [round(float(v), 4) for v in roll["rho_se"]]},
        "cpi": _mm23(p_mm23),
    }

    last_y = {hk: _month(preds["latest"][hk]["y"].dropna().index[-1]) for hk in preds["latest"]}
    summary_ref = {hk: evals["summary"][hk]["common"]["models"]["M4"]["rel_pct"] for hk in ("3m", "6m")}
    blocks = [pb[w] for ev in evals.values() for hv in ev.values() for pb in hv["pairs"].values() for w in ("own", "common")]
    blocks += [b for hv in window_rows.values() for b in hv.values()]     # every distinct DM test the page can show
    meta = provenance(files, "Author's UK services-inflation replication folder, February 2026 runs")
    if len(files) != len(SOURCE_LABELS):
        raise ValueError("one descriptive label per source file")
    meta["source_files"] = list(SOURCE_LABELS)      # descriptive labels only in the public JSON
    meta.update({
        "source_sha256": {label: sha256(f) for label, f in zip(SOURCE_LABELS, files)},
        "parity": parity,
        "exhibit_version": EXHIBIT_VERSION,
        "code_sha256": {"pipeline/exhibits/forecast_eval.py": sha256(Path(__file__))},
        "title": "Macro forecast evaluation: UK services inflation, archived research example (February 2026)",
        "data_through": _month(panel["date"].max()),
        "downloads": ["2026-02-22", "2026-02-24"],
        "mm23_release": persistence["cpi"]["release_date"],
        "last_outcome_origin": last_y,
        "target": "y(t,h) = services CPI 12-month rate (ONS D7NN) at t+h minus at t, percentage points",
        "estimation": f"expanding-window OLS with intercept, at least {MIN_TRAIN} training months, one regression per horizon",
        "baseline": BASELINE,
        "dm": ("d_t = e_model^2 - e_M2^2; long-run variance with equal weights on autocovariances 1..h-1 (Diebold-Mariano 1995; "
               "Bartlett weights if not positive); Harvey-Leybourne-Newbold correction; Student t, T-1 df; two-sided. "
               "p_bartlett: same with a Newey-West (Bartlett) variance, as a sensitivity. Nested pairs (M0 and M1 in M2, M2 in M6): "
               "the DM reference distribution is not exact under recursive estimation; indicative only"),
        "p_values": {"count": len(blocks), "below_5pct": sum(1 for b in blocks if b["p"] < 0.05),
                     "below_5pct_bartlett": sum(1 for b in blocks if b["p_bartlett"] < 0.05),
                     "min_p": min(b["p"] for b in blocks)},
        "summary_reference": {"m4_common_rel_pct": summary_ref,
                              "reported": {"3m": "0.68% lower RMSE", "6m": "3.09% lower RMSE"}},
        "default_view": DEFAULT_VIEW,
    })
    return {"meta": meta, "models": [{"key": k, **MODELS[k], "nested_with_baseline": k in NESTED}
                                     for k in ["M0", "M1", "M2", "M3", "M4", "M5", "M6"]],
            "versions": versions, "eval_window_check": {"id": EVAL_WINDOW_ROW, **EVAL_WINDOW_LABELS},
            "eval": evals, "sensitivity": sensitivity, "persistence": persistence}


# ------------------------------------------------------------------------------------------- outputs

def _fmt(x, d=3):
    if x is None:
        return "n/a"
    s = f"{abs(x):.{d}f}"
    return ("−" if x < 0 and float(s) != 0 else "") + s


def _fmt_pct(x):
    if x is None:
        return "n/a"
    s = f"{abs(x):.2f}"
    if float(s) == 0:
        return "0.00%"
    return ("−" if x < 0 else "+") + s + "%"


SHORT = {"en": {"M0": "no change", "M1": "AR(1)", "M2": "baseline", "M3": "slack → smoothed persistence",
                "M4": "slack → durable signal", "M5": "slack → rolling persistence", "M6": "M4v2"},
         "zh": {"M0": "不变预测", "M1": "AR(1)", "M2": "基准", "M3": "松紧度 → 平滑持续性", "M4": "松紧度 → 持久信号",
                "M5": "松紧度 → 滚动持续性", "M6": "M4v2"}}
VERSION_SHORT = {"en": {"latest": "Latest run, 24 Feb 2026 (sample from 2001)",
                        "summary": "Research-summary run, 23 Feb 2026 (sample from 2005)",
                        "observed": "Latest inputs, trained only on observed outcomes",
                        EVAL_WINDOW_ROW: "Latest run on the research-summary run's common window (from 2020-01)"},
                 "zh": {"latest": "最新版本，2026 年 2 月 24 日（样本始于 2001 年）",
                        "summary": "研究摘要版本，2026 年 2 月 23 日（样本始于 2005 年）",
                        "observed": "最新输入、仅用起点前已观测结果训练",
                        EVAL_WINDOW_ROW: "最新版本，按研究摘要版本的共同窗口计分（2020-01 起）"}}


def table_markdown(payload: dict, lang: str = "en") -> str:
    """Static (no-JS) default view: errors per model, DM vs M2, and the version-sensitivity table."""
    dv = payload["meta"]["default_view"]
    vid, hk, win = dv["version"], dv["horizon"], dv["window"]
    ev = payload["eval"][vid][hk]
    ver = next(v for v in payload["versions"] if v["id"] == vid)
    zh = lang == "zh"
    short, vshort = SHORT[lang], VERSION_SHORT[lang]
    c = ev["common"]
    lines = ["::: {.column-body-outset .fe-static}"]
    if zh:
        head = (f"静态表（无需 JavaScript）：默认视图。{ver['zh']}；预测期 3 个月；共同窗口（{c['first']} 至 {c['last']} 的预测起点，"
                f"n = {c['n']}）。相对 RMSE 为 100 ×（模型 RMSE ÷ M2 RMSE − 1），负值表示误差小于 M2。DM 检验为 HLN 修正后的统计量及双侧 p 值"
                "（长期方差对前 h − 1 阶自协方差取相等权重）；M0、M1、M6 与 M2 为嵌套关系，其 p 值仅供参考。")
        lines += [f"<div class=\"tbl-note\">{head}</div>", "", "::: {.table-scroll .tbl-num}",
                  "| 模型 | 相对 M2 的 RMSE | n | RMSE | MAE | 方向命中率 | DM（HLN） | p 值 |", "|:--|--:|--:|--:|--:|--:|--:|--:|"]
    else:
        head = (f"Static table (no JavaScript needed): the default view. {ver['en']}; 3-month horizon; common window "
                f"(forecast origins {c['first']} to {c['last']}, n = {c['n']}). Relative RMSE = 100 × (model RMSE ÷ M2 RMSE − 1); "
                "negative means smaller errors than M2. DM = HLN-corrected statistic with its two-sided p-value (long-run variance "
                "with equal weights on the first h − 1 autocovariances); M0, M1 and M6 are nested with M2, so their p-values are indicative only.")
        lines += [f"<div class=\"tbl-note\">{head}</div>", "", "::: {.table-scroll .tbl-num}",
                  "| Model | RMSE vs M2 | n | RMSE | MAE | Direction hit rate | DM (HLN) | p-value |", "|:--|--:|--:|--:|--:|--:|--:|--:|"]
    for m in ver["models"]:
        r = c["models"][m]
        if m == BASELINE:
            dm, p = "—", "—"
        else:
            pb = ev["pairs"][m][win]
            dm, p = _fmt(pb["hln"], 2), _fmt(pb["p"], 2)
        lines.append(f"| {m} {short[m]} | {'—' if m == BASELINE else _fmt_pct(r['rel_pct'])} | {r['n']} | {_fmt(r['rmse'])} | "
                     f"{_fmt(r['mae'])} | {_fmt(r['dir'], 2)} | {dm} | {p} |")
    lines += [":::", ""]
    if zh:
        lines += ["<div class=\"tbl-note\">版本敏感性：M4 相对 M2 的 RMSE（%），按版本、预测期和比较窗口列出；括号内为配对起点数 n 与 DM 检验 p 值。"
                  "自身窗口一栏：RMSE 比值、n 与 p 值均取 M4 与 M2 的重叠起点。最后一行把最新版本自己的存档预测放到研究摘要版本的共同窗口上计分，"
                  "用来分离评估窗口的影响。</div>", "",
                  "::: {.table-scroll .tbl-num}", "| 版本 | 3 个月，自身窗口 | 3 个月，共同窗口 | 6 个月，自身窗口 | 6 个月，共同窗口 |", "|:--|--:|--:|--:|--:|"]
    else:
        lines += ["<div class=\"tbl-note\">Version sensitivity: M4's RMSE relative to M2 (%), by output version, horizon and comparison window; "
                  "in brackets the matched origins n and the DM p-value. Own-window columns: RMSE ratio, n and p-value all on the origins "
                  "where M4 and M2 overlap. The last row scores the latest run's own archived forecasts on the research-summary run's "
                  "common window, which isolates the effect of the evaluation window.</div>", "",
                  "::: {.table-scroll .tbl-num}", "| Version | 3m, own window | 3m, common window | 6m, own window | 6m, common window |", "|:--|--:|--:|--:|--:|"]
    for v in VERSION_ORDER + [EVAL_WINDOW_ROW]:
        cells = []
        for hk2 in ("3m", "6m"):
            for w in ("own", "common"):
                row = next((s for s in payload["sensitivity"] if s["model"] == "M4" and s["version"] == v
                            and s["horizon"] == hk2 and s["window"] == w), None)
                cells.append("—" if row is None else f"{_fmt_pct(row['rel_pct'])}<br>({row['pair_n']}; p = {_fmt(row['p'], 2)})")
        lines.append(f"| {vshort[v]} | " + " | ".join(cells) + " |")
    lines += [":::", ":::", ""]
    return "\n".join(lines)


def write_markdown(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(table_markdown(payload, "en"), encoding="utf-8")
    zh_path = path.parent / Path(TABLE_PATH_ZH).name
    zh_path.write_text(table_markdown(payload, "zh"), encoding="utf-8")


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback: smoothed persistence (68% band) with the rolling estimate, and the default
    view's cumulative loss differential (M4 minus M2 squared errors, latest run, 3m, common window)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    per = payload["persistence"]
    sm = per["smoothed"]
    xs = pd.period_range(sm["start"], periods=len(sm["rho"]), freq="M").to_timestamp()
    ro = per["rolling"]
    xr = pd.period_range(ro["start"], periods=len(ro["rho"]), freq="M").to_timestamp()
    dv = payload["meta"]["default_view"]
    pb = payload["eval"][dv["version"]][dv["horizon"]]["pairs"][dv["model"]][dv["window"]]
    xc = pd.period_range(pb["cum"]["start"], periods=len(pb["cum"]["v"]), freq="M").to_timestamp()

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8), dpi=150)
    a1.fill_between(xs, sm["lo"], sm["hi"], color="#18557f", alpha=0.15, lw=0, label="68% band (smoothed)")
    a1.plot(xs, sm["rho"], color="#18557f", lw=1.6, label="Smoothed state-space estimate (uses full sample)")
    a1.plot(xr, ro["rho"], color="#8a6a1a", lw=1.3, ls="--", label="Rolling 120-month estimate (backward-looking)")
    a1.axhline(per["threshold"], color="#6f6a60", lw=0.8, ls=":")
    a1.set_title("Services inflation persistence", fontsize=10)
    a1.legend(frameon=False, fontsize=7, loc="upper left")
    a1.spines[["top", "right"]].set_visible(False)
    a2.plot(xc, pb["cum"]["v"], color="#18557f", lw=1.6)
    a2.axhline(0, color="#6f6a60", lw=0.8)
    a2.set_title("Cumulative loss differential, M4 minus M2 (squared errors)\n(latest run, 3m, common window; above 0 = M4 has larger cumulative loss)", fontsize=9)
    a2.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, "UK services inflation, archived research example (February 2026). Sources: ONS (Open Government Licence); author's model outputs.",
             fontsize=7, color="#6f6a60")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out_png)
    plt.close(fig)
