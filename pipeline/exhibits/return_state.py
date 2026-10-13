"""Return-State Behavior Profile: portfolio behaviour and risk diagnostics on archived monthly returns.

Source (optional root `return_state`): the extracted archive of the author's white paper on an NA-IPCA
characteristic long-short U.S. equity backtest (2026; titled "Regime-Aware Alpha Strategy", although the
portfolio rule itself has no regime switch): the monthly return table (224 months, 2007-04..2025-11) and
the stored radar table (parity check only).

Function (Layer 2 of the page's dependency diagram): dated return stream + dated benchmark return ->
validate -> benchmark market states (defined by the BENCHMARK, never by the stream) -> eight raw
state-conditional metrics with descriptive 95% intervals -> custom normalised radar scores (clipping
flagged) -> per-state n, thresholds, an all-months reference row and warnings.

The default view (net strategy stream, deciles 10/90 with a 5% tail and a -5% recovery drawdown, full
sample) must equal the stored radar table to 1e-8; build() refuses to publish otherwise.

The committed JSON holds AGGREGATES ONLY. Aggregates can still reveal single months when enough
overlapping ones are published (differencing): half-sample windows, whose re-estimated percentiles give
slightly different state sets, let a month be solved exactly. So only the full sample is published, and
build() computes the disclosure leverage of every published linear functional of each restricted stream
(state sums, downside-beta numerators, all-months sums) and of the squared stream (state sums of squares,
implied by the standard errors); it refuses to publish if any month's leverage reaches LEVERAGE_MAX, a
limit set by the author. This is a heuristic screen, not a privacy guarantee: it rules out exact recovery
of a month from these linear aggregates, but it does not model the published counts of positive months,
nonlinear combinations of the statistics, outside information or approximate inference about a month.

Streams offered: the archive's own return columns plus two public-data dilution references (the 60/40
proxy blended with 5% or 10% cash, no strategy), so a sleeve's effect can be separated from simply
holding less equity. The archive's Fama-French long-short columns (smb, hml, rmw, cma, mom) differ from
the Kenneth R. French Data Library monthly files retrieved on 2026-10-11 (maximum absolute differences
0.20 to 1.67 percentage points a month; correlations above 0.9996; most likely later revisions of the
library), so they are not offered (EXCLUDED_COLUMNS). mkt_rf and rf match exactly; the benchmark
`equity_market` equals mkt_rf + rf.
"""
from __future__ import annotations

import hashlib
import io
import math
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from common import provenance
from sources import DEFAULT_CONFIG

ROOT = "return_state"
F_STREAM = "tables/T_P12_strategy_return_stream_verified.csv"
F_RADAR = "tables/T_P12_radar_characteristics_verified.csv"
SOURCE_NAME = ("Author's archived white paper (2026) on an NA-IPCA characteristic long-short U.S. equity "
               "backtest: monthly backtest tables")
# Generic labels for the two private source files (their internal file names stay out of the public JSON).
SOURCE_LABELS = {F_STREAM: "archived monthly return table", F_RADAR: "archived radar table"}
TABLE_PATH = "projects/_tbl-return-state.md"          # relative to --site-dir; checked by build_data --check
TABLE_PATH_ZH = "projects/_tbl-return-state-zh.md"    # written with it; checked by tests/test_return_state.py

EXPECTED_N, FIRST, LAST = 224, "2007-04", "2025-11"
SMALL_N = 15                 # n below this is flagged as a small sample next to the chart
PARITY_TOL = 1e-8
LEVERAGE_MAX = 0.75          # disclosure screen: max projector leverage of any month (limit set by the author)
CI_LEVEL = 0.95
BENCH_COLUMN = "equity_market"

# kind: "archived" streams contain (or blend in) the restricted strategy returns; "public" streams are built
# from public Fama-French market and risk-free returns only.
STREAMS = [
    {"id": "strategy_net", "column": "strategy_ret", "kind": "archived",
     "en": "Archived long–short strategy backtest, net of bid-ask cost proxy",
     "zh": "存档多空策略回测（扣除买卖价差成本代理）",
     "short_en": "Strategy (net of cost proxy)", "short_zh": "策略（扣除成本代理）"},
    {"id": "strategy_gross", "column": "gross_ret", "kind": "archived",
     "en": "Same backtest before the cost proxy (gross)",
     "zh": "同一回测，未扣成本代理（毛收益）",
     "short_en": "Strategy (gross)", "short_zh": "策略（毛收益）"},
    {"id": "proxy_60_40", "column": "equity_cash_60_40_proxy", "kind": "public",
     "en": "60% U.S. equity + 40% cash proxy",
     "zh": "60% 美国股票 + 40% 现金代理组合",
     "short_en": "60/40 equity–cash proxy", "short_zh": "60/40 股票–现金代理"},
    {"id": "proxy_plus_5", "column": "proxy_plus_5_strategy", "kind": "archived",
     "en": "95% equity–cash proxy + 5% strategy (net)",
     "zh": "95% 股票–现金代理 + 5% 策略（净）",
     "short_en": "Proxy + 5% strategy", "short_zh": "代理 + 5% 策略"},
    {"id": "proxy_cash_5", "column": "proxy_plus_5_cash", "kind": "public", "derived": 0.05,
     "en": "95% equity–cash proxy + 5% cash: dilution only, no strategy (57% equity)",
     "zh": "95% 股票–现金代理 + 5% 现金：只稀释、不含策略（股票 57%）",
     "short_en": "Proxy + 5% cash (reference)", "short_zh": "代理 + 5% 现金（参照）"},
    {"id": "proxy_plus_10", "column": "proxy_plus_10_strategy", "kind": "archived",
     "en": "90% equity–cash proxy + 10% strategy (net)",
     "zh": "90% 股票–现金代理 + 10% 策略（净）",
     "short_en": "Proxy + 10% strategy", "short_zh": "代理 + 10% 策略"},
    {"id": "proxy_cash_10", "column": "proxy_plus_10_cash", "kind": "public", "derived": 0.10,
     "en": "90% equity–cash proxy + 10% cash: dilution only, no strategy (54% equity)",
     "zh": "90% 股票–现金代理 + 10% 现金：只稀释、不含策略（股票 54%）",
     "short_en": "Proxy + 10% cash (reference)", "short_zh": "代理 + 10% 现金（参照）"},
]
RESTRICTED_COLUMNS = ("strategy_ret", "gross_ret")   # the private streams; the sleeves are linear blends of strategy_ret
# Archive columns deliberately not offered (reason recorded in the module docstring).
EXCLUDED_COLUMNS = ("smb", "hml", "rmw", "cma", "mom")

DEFINITIONS = [
    {"id": "d10", "lower": 0.10, "upper": 0.90, "tail": 0.05, "recovery_dd": -0.05,
     "en": "Deciles, 5% tail, −5% recovery (default)",
     "zh": "十分位，尾部 5%，修复 −5%（默认）"},
    {"id": "q20", "lower": 0.20, "upper": 0.80, "tail": 0.10, "recovery_dd": -0.05,
     "en": "Quintiles, 10% tail, −5% recovery",
     "zh": "五分位，尾部 10%，修复 −5%"},
    {"id": "dd10", "lower": 0.10, "upper": 0.90, "tail": 0.05, "recovery_dd": -0.10,
     "en": "Deciles, 5% tail, −10% recovery",
     "zh": "十分位，尾部 5%，修复 −10%"},
]
# Only the full sample is published: half-sample windows failed the disclosure test (see the docstring).
WINDOWS = [
    {"id": "full", "start": FIRST, "end": LAST, "en": "Full sample, Apr 2007 – Nov 2025",
     "zh": "全样本，2007 年 4 月至 2025 年 11 月"},
]
DEFAULT = {"stream": "strategy_net", "definition": "d10", "window": "full"}

STATES = ["normal", "rally", "recovery", "downside", "tail"]
STATE_NAMES = {"normal": ("Normal", "常态"), "rally": ("Strong rally", "强势上涨"),
               "recovery": ("Recovery", "修复"), "downside": ("Downside", "下行"), "tail": ("Tail", "尾部"),
               "all": ("All months", "全部月份")}
# id, EN label, ZH label, conditioning state, units, normalisation, white-paper name (where it differs)
METRICS = [
    ("carry", "Carry", "常态期收益", "normal", "pct_month", "ret", None),
    ("upside", "Upside Participation", "上行参与", "rally", "pct_month", "ret", "Positive Convexity"),
    ("recovery", "Recovery", "修复期收益", "recovery", "pct_month", "ret", None),
    ("downside_beta", "Downside Beta", "下行贝塔", "downside", "beta", "beta", None),
    ("downside_reactivity", "Downside Reactivity", "下行期收益", "downside", "pct_month", "ret", None),
    ("downside_reliability", "Downside Reliability", "下行期正收益频率", "downside", "freq", "freq", None),
    ("tail_reactivity", "Tail Reactivity", "尾部期收益", "tail", "pct_month", "ret", None),
    ("tail_reliability", "Tail Reliability", "尾部期正收益频率", "tail", "freq", "freq", None),
]
METRIC_IDS = [m[0] for m in METRICS]
# Benchmark values on these spokes are fixed or bounded by the state definition, because the benchmark
# defines the states: beta on itself is 1; its downside/tail returns are at or below a negative cut-off, so
# the mean is below the cut-off and no month is positive. build() checks the premise (negative cut-offs).
BENCH_BY_CONSTRUCTION = ("downside_beta", "downside_reactivity", "downside_reliability",
                         "tail_reactivity", "tail_reliability")
# The all-months reference row: unconditional mean, full-window beta on the benchmark, share positive.
REFERENCE = [
    ("all_mean", "All months: mean return", "全部月份：平均月收益", "pct_month"),
    ("all_beta", "All months: beta on the benchmark", "全部月份：对基准的贝塔", "beta"),
    ("all_freq", "All months: share of months positive", "全部月份：正收益月份占比", "freq"),
]
# The stored radar table uses the white paper's names.
ARCHIVE_DIMENSIONS = ["Carry", "Positive Convexity", "Recovery", "Downside Beta", "Downside Reactivity",
                      "Downside Reliability", "Tail Reactivity", "Tail Reliability"]
ARCHIVE_SERIES = {"stream": "Regime-Aware Alpha Strategy", "bench": "U.S. equity market"}
NORMALISATION = {
    "ret": {"formula": "score = clip((raw + 0.05) / 0.10, 0, 1)",
            "en": "−5% a month maps to 0 and +5% to 1; values outside are clipped.",
            "zh": "月收益 −5% 对应 0，+5% 对应 1；超出部分截断。"},
    "beta": {"formula": "score = clip(1 − (β + 0.5) / 2, 0, 1)",
             "en": "Inverted: β = −0.5 maps to 1 and β = 1.5 to 0; the benchmark's own β = 1 scores 0.25.",
             "zh": "方向反转：β = −0.5 对应 1，β = 1.5 对应 0；基准自身的 β = 1 得 0.25。"},
    "freq": {"formula": "score = clip(frequency, 0, 1)",
             "en": "The observed share of months with a positive return, unchanged.",
             "zh": "即正收益月份的观测占比，不作变换。"},
}
INTERVALS = {
    "en": "95% intervals treat months as independent and are descriptive: t-intervals for means and for "
          "betas (OLS standard error), Clopper–Pearson intervals for hit frequencies. Overlapping states and "
          "the selection of the configuration are not accounted for. A wide interval means the history "
          "cannot pin the value down.",
    "zh": "95% 区间假定各月相互独立，只作描述：均值和贝塔用 t 区间（贝塔用 OLS 标准误），正收益频率用 "
          "Clopper–Pearson 区间。状态之间的重叠和这一配置的筛选过程都未计入。区间很宽，说明历史数据无法把这个值确定下来。",
}


# ----------------------------------------------------------------------------------- source access

def _root(sources) -> Path:
    """The `return_state` root: from sources.extra when sources.py lists it among OPTIONAL_ROOTS,
    otherwise from [roots] in pipeline/sources.toml."""
    base = getattr(sources, "extra", {}).get(ROOT)
    if base is None and DEFAULT_CONFIG.exists():
        with open(DEFAULT_CONFIG, "rb") as fh:
            raw = tomllib.load(fh).get("roots", {}).get(ROOT)
        base = Path(raw).expanduser() if raw else None
    if base is None:
        raise KeyError(f"sources.toml [roots] has no '{ROOT}'; add it to use this exhibit")
    if not Path(base).is_dir():
        raise FileNotFoundError(f"{ROOT} directory does not exist: {base}")
    return Path(base)


def _file(sources, relative: str) -> Path:
    p = _root(sources) / relative
    if not p.exists():
        raise FileNotFoundError(f"{ROOT} file not found: {relative} (under {_root(sources)})")
    return p


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------- validation

def load_and_validate(p: Path) -> pd.DataFrame:
    """Ingest + Validate: sorted unique consecutive months, no missing values, decimal units, identities.
    Archive-specific: the column names, the 224-month sample and the audit anchors belong to this example;
    a generic loader for another stream is a Planned extension."""
    df = pd.read_csv(p)
    archive_cols = [s["column"] for s in STREAMS if "derived" not in s]
    cols = ["date", "target_yyyymm", BENCH_COLUMN, "cash", "mkt_rf", "rf"] + archive_cols
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{p.name}: missing columns {missing}")
    if df[cols].isna().any().any():
        raise ValueError(f"{p.name}: missing values in {[c for c in cols if df[c].isna().any()]}")
    if len(df) != EXPECTED_N:
        raise ValueError(f"{p.name}: expected {EXPECTED_N} rows, found {len(df)}")
    dt = pd.to_datetime(df["date"])
    if not (dt.is_monotonic_increasing and dt.is_unique):
        raise ValueError(f"{p.name}: dates are not sorted and unique")
    months = dt.dt.strftime("%Y-%m")
    if months.iloc[0] != FIRST or months.iloc[-1] != LAST:
        raise ValueError(f"{p.name}: sample runs {months.iloc[0]}..{months.iloc[-1]}, expected {FIRST}..{LAST}")
    per = dt.dt.to_period("M")
    if not ((per.diff().iloc[1:].apply(lambda x: x.n)) == 1).all():
        raise ValueError(f"{p.name}: months are not consecutive")
    if not (months.str.replace("-", "").astype(int) == df["target_yyyymm"].astype(int)).all():
        raise ValueError(f"{p.name}: date and target_yyyymm disagree")
    for c in [BENCH_COLUMN, "cash"] + archive_cols:
        x = df[c].to_numpy(float)
        if not np.isfinite(x).all():
            raise ValueError(f"{p.name}: non-finite values in {c}")
        # Decimal units: a monthly return of 50% or more would mean percent units (or a data error).
        if np.abs(x).max() >= 0.5:
            raise ValueError(f"{p.name}: {c} has |value| >= 0.5; returns must be decimals, not percent")
    m, cash = df[BENCH_COLUMN].to_numpy(float), df["cash"].to_numpy(float)
    s = df["strategy_ret"].to_numpy(float)
    checks = {
        "equity_market = mkt_rf + rf": m - (df["mkt_rf"].to_numpy(float) + df["rf"].to_numpy(float)),
        "60/40 proxy = 0.6 equity + 0.4 cash": df["equity_cash_60_40_proxy"].to_numpy(float) - (0.6 * m + 0.4 * cash),
        "proxy + 5% = 0.95 proxy + 0.05 strategy": df["proxy_plus_5_strategy"].to_numpy(float)
        - (0.95 * df["equity_cash_60_40_proxy"].to_numpy(float) + 0.05 * s),
        "proxy + 10% = 0.90 proxy + 0.10 strategy": df["proxy_plus_10_strategy"].to_numpy(float)
        - (0.90 * df["equity_cash_60_40_proxy"].to_numpy(float) + 0.10 * s),
    }
    for name, d in checks.items():
        if np.abs(d).max() > 1e-10:
            raise ValueError(f"{p.name}: identity fails: {name} (max |diff| {np.abs(d).max():.3g})")
    if (df["gross_ret"] < df["strategy_ret"] - 1e-12).any():
        raise ValueError(f"{p.name}: net return above gross in some month; the cost proxy cannot be negative")
    out = df.copy()
    out["month"] = months
    # Public dilution references: the 60/40 proxy funded pro rata into cash instead of into the strategy.
    for st in STREAMS:
        if "derived" in st:
            w = st["derived"]
            out[st["column"]] = (1 - w) * out["equity_cash_60_40_proxy"].astype(float) + w * out["cash"].astype(float)
    return out


# ------------------------------------------------------------------------- small-sample statistics

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularised incomplete beta function (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
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
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def _bisect(f, lo: float, hi: float, target: float) -> float:
    """Root of the increasing function f(x) = target on [lo, hi]."""
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def t_cdf(t: float, nu: float) -> float:
    p = 0.5 * betainc(nu / 2.0, 0.5, nu / (nu + t * t))
    return 1.0 - p if t > 0 else p


def t_ppf(q: float, nu: float) -> float:
    """Student-t quantile for q in (0.5, 1)."""
    return _bisect(lambda t: t_cdf(t, nu), 0.0, 1e3, q)


def clopper_pearson(k: int, n: int, level: float = CI_LEVEL) -> tuple[float, float]:
    a = (1 - level) / 2
    lo = 0.0 if k == 0 else _bisect(lambda p: betainc(k, n - k + 1, p), 0.0, 1.0, a)
    hi = 1.0 if k == n else _bisect(lambda p: betainc(k + 1, n - k, p), 0.0, 1.0, 1 - a)
    return lo, hi


def mean_ci(x: np.ndarray, level: float = CI_LEVEL) -> tuple[float | None, float | None, float | None]:
    """Mean, standard error s / sqrt(n) and the t-interval (None where n < 2)."""
    n = len(x)
    if n < 2:
        return None, None, None
    mu, se = float(np.mean(x)), float(np.std(x, ddof=1) / math.sqrt(n))
    t = t_ppf(0.5 + level / 2, n - 1)
    return se, mu - t * se, mu + t * se


def ols_beta(y: np.ndarray, m: np.ndarray, level: float = CI_LEVEL) -> tuple:
    """OLS slope of y on m with intercept: (beta, se, lo, hi); None where n < 3 or var(m) = 0."""
    n = len(y)
    if n < 3 or float(np.var(m, ddof=1)) <= 0:
        return None, None, None, None
    # Same expression as the package's recompute script: cov(x, m) / var(m), ddof = 1.
    beta = float(np.cov(y, m, ddof=1)[0, 1] / np.var(m, ddof=1))
    resid = (y - y.mean()) - beta * (m - m.mean())
    sxx = float(((m - m.mean()) ** 2).sum())
    se = float(math.sqrt(max(float((resid ** 2).sum()), 0.0) / (n - 2) / sxx))
    t = t_ppf(0.5 + level / 2, n - 2)
    return beta, se, beta - t * se, beta + t * se


# ------------------------------------------------------------------------------------ computation

def benchmark_drawdown(market: pd.Series) -> pd.Series:
    """Drawdown of the benchmark's cumulative wealth path, measured from Apr 2007 on the full history."""
    wealth = (1 + market).cumprod()
    return wealth / wealth.cummax() - 1


def state_masks(market: pd.Series, drawdown: pd.Series, prev_drawdown: pd.Series, d: dict) -> tuple[dict, dict]:
    """Benchmark-defined states inside one window. Percentiles are estimated on the window's months;
    the drawdown and the previous month's drawdown come from the full benchmark history (from Apr 2007)."""
    q_tail, q_low, q_high = market.quantile([d["tail"], d["lower"], d["upper"]])
    masks = {
        "normal": (market > q_low) & (market < q_high),
        "rally": market >= q_high,
        "recovery": (prev_drawdown < d["recovery_dd"]) & (drawdown > prev_drawdown) & (market > 0),
        "downside": market <= q_low,
        "tail": market <= q_tail,
    }
    return masks, {"tail": float(q_tail), "lower": float(q_low), "upper": float(q_high)}


def score_unclipped(norm: str, raw: float | None) -> float | None:
    if raw is None:
        return None
    if norm == "freq":
        return raw
    if norm == "beta":
        return 1 - (raw + 0.5) / 2
    return (raw + 0.05) / 0.10


def score(norm: str, raw: float | None) -> float | None:
    v = score_unclipped(norm, raw)
    return None if v is None else max(0.0, min(1.0, v))


def raw_metrics(x: pd.Series, market: pd.Series, masks: dict) -> tuple[list, dict, list, list]:
    """The eight raw values for one stream (None where a state is empty or beta is undefined), the positive
    counts, the standard errors (None for hit frequencies) and the 95% intervals."""
    raw, se, ci, pos = [], [], [], {}
    for mid, _, _, state, units, norm, _ in METRICS:
        sel = x[masks[state]].to_numpy(float)
        if norm == "beta":
            b, s, lo, hi = ols_beta(sel, market[masks[state]].to_numpy(float))
            raw.append(b); se.append(s); ci.append([lo, hi])
        elif norm == "freq":
            k, n = int((sel > 0).sum()), len(sel)
            pos[state] = k
            raw.append(k / n if n else None); se.append(None)
            ci.append(list(clopper_pearson(k, n)) if n else [None, None])
        else:
            raw.append(float(sel.mean()) if len(sel) else None)
            s, lo, hi = mean_ci(sel)
            se.append(s); ci.append([lo, hi])
    return raw, pos, se, ci


def reference_metrics(x: pd.Series, market: pd.Series) -> dict:
    """All months of the window: unconditional mean, full-window beta on the benchmark, share positive."""
    xv, mv = x.to_numpy(float), market.to_numpy(float)
    s, lo, hi = mean_ci(xv)
    b, bse, blo, bhi = ols_beta(xv, mv)
    k, n = int((xv > 0).sum()), len(xv)
    flo, fhi = clopper_pearson(k, n)
    return {"n": n, "raw": [_r(float(xv.mean())), _r(b), _r(k / n)], "se": [_r(s), _r(bse), None],
            "ci": [[_r(lo), _r(hi)], [_r(blo), _r(bhi)], [_r(flo), _r(fhi)]], "pos": k}


def _r(x: float | None, nd: int = 10) -> float | None:
    if x is None:
        return None
    v = round(float(x), nd)
    return 0.0 if v == 0 else v


def _profile(raw: list, pos: dict, se: list, ci: list, ref: dict) -> dict:
    scores = [score(m[5], v) for m, v in zip(METRICS, raw)]
    unc = [score_unclipped(m[5], v) for m, v in zip(METRICS, raw)]
    clipped = [bool(u is not None and (u < 0 or u > 1)) for u in unc]
    return {"raw": [_r(v) for v in raw], "score": [_r(v) for v in scores], "clipped": clipped,
            "se": [_r(v) for v in se], "ci": [[_r(a), _r(b)] for a, b in ci], "pos": pos, "all": ref}


def state_rules(d: dict) -> dict:
    lo, hi, tl = round(d["lower"] * 100), round(d["upper"] * 100), round(d["tail"] * 100)
    dd = round(-d["recovery_dd"] * 100)
    return {
        "normal": {"en": f"Benchmark monthly return strictly between its {lo}th and {hi}th percentiles",
                   "zh": f"基准月收益严格介于第 {lo} 与第 {hi} 百分位之间"},
        "rally": {"en": f"Benchmark monthly return at or above its {hi}th percentile",
                  "zh": f"基准月收益不低于第 {hi} 百分位"},
        "recovery": {"en": f"Benchmark drawdown below −{dd}% at the previous month-end, drawdown narrowing "
                           f"and benchmark return positive this month",
                     "zh": f"基准上月末回撤深于 −{dd}%，本月回撤收窄且基准收益为正"},
        "downside": {"en": f"Benchmark monthly return at or below its {lo}th percentile",
                     "zh": f"基准月收益不高于第 {lo} 百分位"},
        "tail": {"en": f"Benchmark monthly return at or below its {tl}th percentile",
                 "zh": f"基准月收益不高于第 {tl} 百分位"},
        "all": {"en": "Every month of the window", "zh": "窗口内的全部月份"},
    }


def compute_all(df: pd.DataFrame) -> tuple[dict, dict, dict, dict]:
    """Every (definition, window) state table and every (stream, definition, window) profile, unrounded;
    plus the masks used, for the disclosure check."""
    market_full = df[BENCH_COLUMN].astype(float).reset_index(drop=True)
    dd_full = benchmark_drawdown(market_full)
    months = df["month"].reset_index(drop=True)
    states, results, unrounded, used_masks = {}, {}, {}, {}
    for d in DEFINITIONS:
        for w in WINDOWS:
            sel = (months >= w["start"]) & (months <= w["end"])
            market = market_full[sel]
            masks, thr = state_masks(market, dd_full[sel], dd_full.shift(1)[sel], d)
            if not (thr["lower"] < 0 and thr["tail"] < 0):
                raise ValueError(f"{d['id']}|{w['id']}: a downside cut-off is not negative; the "
                                 "'set by construction' wording for the benchmark would not hold")
            n = {k: int(v.sum()) for k, v in masks.items()}
            braw, bpos, bse, bci = raw_metrics(market, market, masks)
            key = f"{d['id']}|{w['id']}"
            used_masks[key] = (sel, masks)
            states[key] = {
                "n_months": int(sel.sum()),
                "n": n,
                "thresholds": {k: _r(v, 8) for k, v in thr.items()},
                "overlap": {"rally_recovery": int((masks["rally"] & masks["recovery"]).sum()),
                            "normal_recovery": int((masks["normal"] & masks["recovery"]).sum()),
                            "downside_recovery": int((masks["downside"] & masks["recovery"]).sum())},
                "bench": _profile(braw, bpos, bse, bci, reference_metrics(market, market)),
            }
            unrounded[("bench", d["id"], w["id"])] = braw
            for s in STREAMS:
                x = df[s["column"]].astype(float).reset_index(drop=True)[sel]
                raw, pos, se, ci = raw_metrics(x, market, masks)
                results[f"{s['id']}|{key}"] = _profile(raw, pos, se, ci, reference_metrics(x, market))
                unrounded[(s["id"], d["id"], w["id"])] = raw
    return states, results, unrounded, used_masks


def disclosure_leverage(df: pd.DataFrame, used_masks: dict) -> dict:
    """Max projector leverage diag(pinv(A) A) over months, for (a) every published linear functional of a
    restricted stream x: n x mean on each state, the downside-beta numerator sum((m - mean m) x) on downside
    months, the all-months sum and the all-months beta numerator; and (b) the functionals of x squared that
    the published standard errors imply (state and all-months sums of squares). A leverage of 1 means a
    month is exactly recoverable from the published aggregates and public market returns."""
    m = df[BENCH_COLUMN].to_numpy(float)
    T = len(m)
    lin, sq = [], []
    for sel, masks in used_masks.values():
        idx = np.where(sel.to_numpy())[0]
        for state in STATES:
            ind = np.zeros(T)
            ind[idx[masks[state].to_numpy()]] = 1.0
            lin.append(ind)
            sq.append(ind)
        dn = idx[masks["downside"].to_numpy()]
        r = np.zeros(T)
        r[dn] = m[dn] - m[dn].mean()
        lin.append(r)
        allr = np.zeros(T)
        allr[idx] = 1.0
        lin.append(allr)
        sq.append(allr)
        r = np.zeros(T)
        r[idx] = m[idx] - m[idx].mean()
        lin.append(r)
    out = {}
    for name, rows in (("linear", lin), ("squared", sq)):
        A = np.array(rows)
        h = np.diag(np.linalg.pinv(A) @ A)
        out[name] = float(f"{h.max():.4f}")
    return out


def archive_parity(unrounded: dict, radar_csv: Path) -> dict:
    """Default view against the stored radar table: max |raw| and |score| deltas over all 16 rows."""
    stored = pd.read_csv(radar_csv)
    got = {"stream": unrounded[("strategy_net", "d10", "full")], "bench": unrounded[("bench", "d10", "full")]}
    raw_d, score_d, rows = 0.0, 0.0, 0
    for who, series in ARCHIVE_SERIES.items():
        for i, dim in enumerate(ARCHIVE_DIMENSIONS):
            row = stored[(stored["series"] == series) & (stored["dimension"] == dim)]
            if len(row) != 1:
                raise ValueError(f"{radar_csv.name}: expected one row for {series} / {dim}")
            raw_d = max(raw_d, abs(got[who][i] - float(row["raw_value"].iloc[0])))
            score_d = max(score_d, abs(score(METRICS[i][5], got[who][i]) - float(row["score"].iloc[0])))
            rows += 1
    if rows != len(stored) or raw_d >= PARITY_TOL or score_d >= PARITY_TOL:
        raise ValueError(f"archive parity fails: {rows} rows, max raw delta {raw_d:.3g}, max score delta {score_d:.3g}")
    return {"rows": rows, "max_raw_delta": float(f"{raw_d:.3g}"), "max_score_delta": float(f"{score_d:.3g}"),
            "tolerance": PARITY_TOL}


def build(sources) -> dict:
    p_stream = _file(sources, F_STREAM)
    p_radar = _file(sources, F_RADAR)
    df = load_and_validate(p_stream)
    states, results, unrounded, used_masks = compute_all(df)
    parity = archive_parity(unrounded, p_radar)
    expected = {"normal": 178, "rally": 23, "recovery": 50, "downside": 23, "tail": 12}
    if states["d10|full"]["n"] != expected:
        raise ValueError(f"default state counts {states['d10|full']['n']} differ from the audit anchors {expected}")
    leverage = disclosure_leverage(df, used_masks)
    if max(leverage.values()) >= LEVERAGE_MAX:
        raise ValueError(f"disclosure check fails: max leverage {leverage} reaches {LEVERAGE_MAX}; "
                         "a month of a restricted stream could be (nearly) recovered from the published aggregates")
    net, gross = df["strategy_ret"].astype(float), df["gross_ret"].astype(float)

    prov = provenance([p_stream, p_radar], SOURCE_NAME)
    prov["source_files"] = [SOURCE_LABELS[F_STREAM], SOURCE_LABELS[F_RADAR]]
    meta = {**prov,
            "source_sha256": {SOURCE_LABELS[F_STREAM]: sha256(p_stream), SOURCE_LABELS[F_RADAR]: sha256(p_radar)},
            "sample_start": FIRST, "sample_end": LAST, "n_months": EXPECTED_N,
            "small_n": SMALL_N, "default": DEFAULT, "benchmark_column": BENCH_COLUMN,
            "parity": parity, "status": "computed at build time from the archived records",
            "record_type": {"en": "Archived backtest: not actual trading, not audited",
                            "zh": "存档回测：不是实际交易，未经审计"},
            "ci_level": CI_LEVEL, "intervals": INTERVALS,
            "disclosure": {"max_leverage": leverage, "threshold": LEVERAGE_MAX,
                           "en": "Only the full sample is published; half-sample results would let single "
                                 "months of the restricted stream be reconstructed. The leverage screen (limit "
                                 "set by the author) rules out exact recovery of a month from the published "
                                 "linear aggregates; it is a heuristic, not a privacy guarantee.",
                           "zh": "只公开全样本结果；若公开半样本结果，可反推出受限收益序列的个别月份。杠杆值筛查"
                                 "（上限由作者设定）排除了由公开的线性汇总统计精确还原某个月份的可能；它只是启发式"
                                 "检查，并非隐私保证。"},
            "cost_proxy": {"mean_drag_month": _r(float((gross - net).mean())),
                           "share_months_charged": _r(float(((gross - net) > 1e-12).mean()))}}
    metrics = [{"id": i, "en": en, "zh": zh, "state": st, "units": u, "norm": nm, "wp_name": wp,
                "bench_by_construction": i in BENCH_BY_CONSTRUCTION}
               for i, en, zh, st, u, nm, wp in METRICS]
    reference = [{"id": i, "en": en, "zh": zh, "units": u} for i, en, zh, u in REFERENCE]
    streams = [{k: s[k] for k in ("id", "kind", "en", "zh", "short_en", "short_zh")} for s in STREAMS]
    definitions = [{**{k: d[k] for k in ("id", "en", "zh", "lower", "upper", "tail", "recovery_dd")},
                    "rules": state_rules(d)} for d in DEFINITIONS]
    windows = [{k: w[k] for k in ("id", "start", "end", "en", "zh")} for w in WINDOWS]
    state_names = {k: {"en": v[0], "zh": v[1]} for k, v in STATE_NAMES.items()}
    return {"meta": meta, "metrics": metrics, "reference": reference, "normalisation": NORMALISATION,
            "streams": streams,
            "benchmark": {"en": "U.S. equity market return (CRSP value-weighted; Fama–French Mkt-RF plus RF)",
                          "zh": "美国股票市场收益（CRSP 市值加权；Fama–French Mkt-RF 加 RF）"},
            "definitions": definitions, "windows": windows, "state_names": state_names,
            "states": states, "results": results}


# ----------------------------------------------------------------------------- generated tables

def _minus(s: str) -> str:
    return s.replace("-", "−")


def fmt_value(units: str, v: float | None, pos: int | None = None, n: int | None = None, zh: bool = False) -> str:
    if v is None:
        return "n/a"
    if units == "pct_month":
        return _minus(f"{v * 100:.2f}%")
    if units == "beta":
        return _minus(f"{v:.2f}")
    if pos is not None and n is not None:
        return f"{pos}/{n}（{v * 100:.1f}%）" if zh else f"{pos}/{n} ({v * 100:.1f}%)"
    return f"{v * 100:.1f}%"


def _pos_for(metric_id: str, prof: dict) -> int | None:
    return prof["pos"]["downside"] if metric_id == "downside_reliability" else \
        prof["pos"]["tail"] if metric_id == "tail_reliability" else None


def fmt_interval(units: str, ci: list, zh: bool = False) -> str:
    lo, hi = ci
    if lo is None or hi is None:
        return "n/a"
    sep = " 至 " if zh else " to "
    if units == "pct_month":
        return _minus(f"{lo * 100:.2f}%") + sep + _minus(f"{hi * 100:.2f}%")
    if units == "beta":
        return _minus(f"{lo:.2f}") + sep + _minus(f"{hi:.2f}")
    return f"{lo * 100:.1f}%" + sep + f"{hi * 100:.1f}%"


def _table(payload: dict, zh: bool) -> str:
    d = DEFAULT
    key = f"{d['definition']}|{d['window']}"
    st = payload["states"][key]
    res = payload["results"][f"{d['stream']}|{key}"]
    bench = st["bench"]
    defn = next(x for x in payload["definitions"] if x["id"] == d["definition"])
    lang = "zh" if zh else "en"
    small = SMALL_N
    lines = ["<!-- generated by pipeline/exhibits/return_state.py; do not edit by hand -->", "",
             "::: {.table-scroll .tbl-num}"]
    if zh:
        lines += ["| 指标 | 市场状态（月数） | 策略（扣除成本代理） | 95% 区间 | 美国股票基准 | 标准化得分：策略 / 基准 |",
                  "|:--|:--|--:|--:|--:|--:|"]
    else:
        lines += ["| Metric | Market state (n months) | Strategy, net of cost proxy | 95% interval | U.S. equity benchmark "
                  "| Normalised score: strategy / benchmark |",
                  "|:--|:--|--:|--:|--:|--:|"]
    by_con = set(BENCH_BY_CONSTRUCTION)
    sc = lambda v, c: f"{v:.2f}" + ("‡" if c else "")
    for i, (mid, en, zh_name, state, units, norm, wp) in enumerate(METRICS):
        n = st["n"][state]
        mark = "†" if n < small else ""
        sname = payload["state_names"][state][lang]
        label = zh_name if zh else en
        sv = fmt_value(units, res["raw"][i], _pos_for(mid, res), n, zh)
        iv = fmt_interval(units, res["ci"][i], zh)
        bv = fmt_value(units, bench["raw"][i], _pos_for(mid, bench), n, zh) + ("§" if mid in by_con else "")
        scores = f"{sc(res['score'][i], res['clipped'][i])} / {sc(bench['score'][i], bench['clipped'][i])}"
        state_cell = f"{sname}（{n}）{mark}" if zh else f"{sname} ({n}){mark}"
        lines.append(f"| {label} | {state_cell} | {sv} | {iv} | {bv} | {scores} |")
    ra, ba = res["all"], bench["all"]
    aname = payload["state_names"]["all"][lang]
    for j, (rid, en, zh_name, units) in enumerate(REFERENCE):
        k_s = ra["pos"] if units == "freq" else None
        k_b = ba["pos"] if units == "freq" else None
        sv = fmt_value(units, ra["raw"][j], k_s, ra["n"], zh)
        bv = fmt_value(units, ba["raw"][j], k_b, ba["n"], zh)
        iv = fmt_interval(units, ra["ci"][j], zh)
        state_cell = f"{aname}（{ra['n']}）" if zh else f"{aname} ({ra['n']})"
        lines.append(f"| *{zh_name if zh else en}* | {state_cell} | {sv} | {iv} | {bv} | — |")
    lines += [":::", ""]
    thr = st["thresholds"]
    if zh:
        lines += ["::: {.table-scroll}",
                  "| 市场状态 | 判定规则（由基准收益决定） | 月数 | 阈值 |",
                  "|:--|:--|--:|:--|"]
    else:
        lines += ["::: {.table-scroll}",
                  "| Market state | Rule (set by the benchmark's returns) | n months | Threshold |",
                  "|:--|:--|--:|:--|"]
    thr_txt = {"normal": f"{_minus(f'{thr['lower'] * 100:.2f}')}% … {_minus(f'{thr['upper'] * 100:.2f}')}%",
               "rally": f"≥ {_minus(f'{thr['upper'] * 100:.2f}')}%",
               "recovery": f"{_minus(f'{defn['recovery_dd'] * 100:.0f}')}% " + ("回撤" if zh else "drawdown"),
               "downside": f"≤ {_minus(f'{thr['lower'] * 100:.2f}')}%",
               "tail": f"≤ {_minus(f'{thr['tail'] * 100:.2f}')}%"}
    for state in STATES:
        n = st["n"][state]
        mark = "†" if n < small else ""
        lines.append(f"| {payload['state_names'][state][lang]} | {defn['rules'][state][lang]} | {n}{mark} | {thr_txt[state]} |")
    lines += [":::", ""]
    ov = st["overlap"]
    n_clip = sum(res["clipped"]) + sum(bench["clipped"])
    if zh:
        lines.append(f"† 月数少于 {small}：样本很小，只作描述，不作推断。‡ 得分被截断为 0 或 1（本视图 16 个得分中有 {n_clip} 个），"
                     "请比较原始数值。§ 由状态定义决定或限定：市场状态由基准定义，所以在这几行中基准的贝塔为 1，收益不高于（为负的）阈值，"
                     "且没有正收益月份；这些只是参照点，不是比较输赢。示例策略为多空组合，基准为纯多头。")
        lines.append("")
        lines.append(INTERVALS["zh"] + "斜体行是全部月份的参照值，用来对照各状态的条件值。")
        lines.append("")
        lines.append(f"状态可以重叠：尾部月份都属于下行月份；{ov['rally_recovery']} 个强势上涨月份同时是修复月份。百分位按全部 "
                     f"{st['n_months']} 个月的基准收益计算（事后划分，并非事前可交易的信号）。数据：存档回测（不是实际交易，未经"
                     "审计），2007 年 4 月至 2025 年 11 月的月度数据；此表在构建网站时由数据管线生成。")
    else:
        lines.append(f"† n below {small}: a small sample, descriptive only. ‡ Score clipped at 0 or 1 ({n_clip} of the 16 "
                     "scores in this view): compare the raw values. § Set or bounded by the state definition: the "
                     "benchmark defines the states, so on these rows its beta is 1, its returns are at or below a "
                     "negative cut-off and no month is positive; read them as reference points, not as a contest. "
                     "The example strategy is long–short; the benchmark is long-only.")
        lines.append("")
        lines.append(INTERVALS["en"] + " Rows in italics are the all-months reference values, against which the "
                     "state-conditional values can be read.")
        lines.append("")
        lines.append(f"States can overlap: every tail month is a downside month, and {ov['rally_recovery']} "
                     f"strong-rally months are also recovery months. Percentiles use all {st['n_months']} benchmark "
                     "months (a retrospective classification, not an ex-ante trading signal). Data: archived "
                     "backtest (not actual trading, not audited), monthly, Apr 2007 – Nov 2025; this table is "
                     "generated by the site's data pipeline at build time.")
    lines.append("")
    return "\n".join(lines)


def table_markdown(payload: dict) -> str:
    return _table(payload, zh=False)


def table_markdown_zh(payload: dict) -> str:
    return _table(payload, zh=True)


def write_markdown(payload: dict, out_md: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(table_markdown(payload), encoding="utf-8")
    zh = out_md.with_name(Path(TABLE_PATH_ZH).name)
    zh.write_text(table_markdown_zh(payload), encoding="utf-8")


# ----------------------------------------------------------------------------------------- PNG

PNG_W, PNG_H, PNG_DPI = 1200, 1000, 100
C_STREAM = "#18557f"
C_BENCH = "#6f6a60"
C_GREY = "#9a9a9a"


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback for no-JS readers: the default view's normalised radar, both outlines, n per spoke."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.text

    d = DEFAULT
    key = f"{d['definition']}|{d['window']}"
    st = payload["states"][key]
    res = payload["results"][f"{d['stream']}|{key}"]
    bench = st["bench"]
    k = len(METRICS)
    ang = [math.pi / 2 - 2 * math.pi * i / k for i in range(k)]

    fig = plt.figure(figsize=(PNG_W / PNG_DPI, PNG_H / PNG_DPI), dpi=PNG_DPI)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes((0.2, 0.19, 0.6, 0.6), polar=True)
    ax.set_theta_offset(0)
    ax.set_theta_direction(1)
    for r in (0.25, 0.5, 0.75, 1.0):
        ax.plot(ang + [ang[0]], [r] * (k + 1), color="#cccccc", lw=0.8)
    for a in ang:
        ax.plot([a, a], [0, 1], color="#cccccc", lw=0.8)
    by_con = [m[0] in BENCH_BY_CONSTRUCTION for m in METRICS]
    for vals, clip, col, ls, lab, who in ((res["score"], res["clipped"], C_STREAM, "-",
                                           "Strategy (long–short), net of cost proxy (solid)", "s"),
                                          (bench["score"], bench["clipped"], C_BENCH, "--",
                                           "U.S. equity benchmark, long-only (dashed)", "b")):
        ax.plot(ang + [ang[0]], list(vals) + [vals[0]], color=col, lw=2.2, ls=ls, label=lab)
        for i, (a, v) in enumerate(zip(ang, vals)):
            if who == "b" and by_con[i]:
                ax.plot([a], [v], "D", color=C_GREY, mfc="white", ms=7, mew=1.6, clip_on=False, zorder=5)
            elif clip[i]:
                ax.plot([a], [v], "s", color=col, mfc="white", ms=7, mew=1.6, clip_on=False, zorder=5)
            else:
                ax.plot([a], [v], "o", color=col, ms=4, clip_on=False, zorder=4)
    ax.plot([], [], "s", color="#444444", mfc="white", ms=7, mew=1.6, ls="", label="score clipped at 0 or 1")
    ax.plot([], [], "D", color=C_GREY, mfc="white", ms=7, mew=1.6, ls="",
            label="benchmark value set by the state definition")
    ax.set_ylim(0, 1.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["polar"].set_visible(False)
    for i, (mid, en, _, state, units, norm, wp) in enumerate(METRICS):
        a = ang[i]
        ha = "center" if abs(math.cos(a)) < 0.2 else ("left" if math.cos(a) > 0 else "right")
        va = "bottom" if math.sin(a) > 0.3 else ("top" if math.sin(a) < -0.3 else "center")
        n = st["n"][state]
        ax.text(a, 1.13, f"{en}\n{payload['state_names'][state]['en']}, n = {n}" + (" (small)" if n < SMALL_N else ""),
                ha=ha, va=va, fontsize=11.5, color="#222222")
    fig.text(0.02, 0.955, "Return-State Behavior Profile: default view, normalised scores (0 to 1)", fontsize=15,
             color="#111111")
    fig.text(0.02, 0.92, "Archived backtest (not actual trading, not audited), monthly, Apr 2007 – Nov 2025;",
             fontsize=11.5, color="#555555")
    fig.text(0.02, 0.897, "states set by the benchmark; custom scale, not a probability or rating", fontsize=11.5,
             color="#555555")
    leg = fig.legend(loc="lower center", ncol=2, frameon=False, fontsize=11)
    leg.set_bbox_to_anchor((0.5, 0.015))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for txt in fig.findobj(matplotlib.text.Text):
        if not txt.get_text():
            continue
        bb = txt.get_window_extent(renderer)
        if bb.x0 < 0 or bb.y0 < 0 or bb.x1 > PNG_W or bb.y1 > PNG_H:
            raise ValueError(f"return_state.png: text runs outside the canvas: {txt.get_text()!r}")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=PNG_DPI, facecolor="white")
    plt.close(fig)
    from PIL import Image
    buf.seek(0)
    with Image.open(buf) as im:
        im.convert("RGB").quantize(colors=128).save(out_png, format="PNG", optimize=True)
