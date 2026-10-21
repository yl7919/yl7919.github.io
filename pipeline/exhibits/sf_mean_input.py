"""Same Forecasts, Different Portfolios: the mean-input switch.

One rolling IPCA fit with an intercept, one risk matrix, two expected-return inputs: the factor means only (the
factor-mean portfolio of the same fit) or the complete fitted mean including the intercept (the intercept
portfolio, IP). The benchmark is the best zero-intercept portfolio (IPCA without the factor penalty, 1.62).
At the reference penalty the IP earns 2.51 against 1.62, a gain of 0.89 [0.59, 1.26]; net of 25 basis points
per dollar traded (purchases plus sales) 1.60 against 1.03, a gain of 0.57 [0.29, 0.89] (Table III, p. 30).

Source: the replication package's data/core files (read inside the package zip; basenames only in the JSON)
  14_table3_594.csv           Table III Panels A-B (p. 30): levels and paired differences
  14_intercept_curve_594.csv  Figure 4 (p. 29): bands along the penalty
  15_net_by_lambda_594.csv    Table III Panel A, net of 25 bp at every penalty
  15_contrasts_594.csv        Table III Panel B, net differences at the penalties 14_table3 leaves empty
  13_ladder_594.csv           Table I (p. 19): the best zero-intercept portfolio, gross and net of 25 bp
594 months, June 1975 to November 2024; unit gross exposure.
"""
from __future__ import annotations

from pathlib import Path

from common import provenance
from exhibits._paper_data import Package, basename, fixed, num, one, save_png
from sources import Sources

ROOT = "same_forecasts_package"
ZIP = "Replication_Package.zip"
F_TABLE3 = "data/core/14_table3_594.csv"
F_CURVE = "data/core/14_intercept_curve_594.csv"
F_NET = "data/core/15_net_by_lambda_594.csv"
F_NETCON = "data/core/15_contrasts_594.csv"
F_LADDER = "data/core/13_ladder_594.csv"
RELEASE = "Same Forecasts, Different Portfolios: Factor Normalization and Regularization (October 2026), replication data"

LAMBDAS = [0.0, 0.001, 0.003, 0.01, 0.03, 0.1]
LAMBDA_TEXT = ["0", "0.001", "0.003", "0.01", "0.03", "0.1"]
REFERENCE = 0.01
BLOCKS = [12, 24, 60]
NETCON_FAMILY = "IP minus factor-mean (same lambda)"

# id, Table III row key, curve prefix, 15_net portfolio, label, sub-label, ZH label, ZH sub-label, palette key
INPUTS = [
    ("factor_means", "fm", "fm", "factor-mean portfolio", "Factor means only", "factor-mean portfolio of the same fit",
     "仅用因子均值", "同一拟合的因子均值组合", "beta_only"),
    ("full_mean", "ip", "ip", "intercept portfolio", "Complete fitted mean, including the intercept", "intercept portfolio (IP)",
     "完整拟合均值（含截距）", "截距组合（IP）", "complete"),
]
LOCATORS = {
    "levels": "Table III, Panel A, p. 30",
    "differences": "Table III, Panel B, p. 30",
    "figure": "Figure 4, p. 29",
    "benchmark": "Table I, Panels A-B, p. 19",
    "text": "Section V.B, pp. 28-29",
}
NOTES = {
    "gross": "Unit gross exposure; gross Sharpe ratios are before trading costs; 594 months, June 1975 to November 2024.",
    "net25": "Net of 25 basis points per dollar traded, charged on purchases plus sales (Table III caption, p. 30); a proportional cost model, not an implementable net return (footnote 23, p. 40).",
    "intervals": "Pointwise 95% intervals, 12-month moving-block bootstrap, fitted models held fixed (Table III caption, p. 30).",
    "benchmark": "The best zero-intercept portfolio is IPCA with the factor penalty removed (lambda = 0); without the penalty both normalisations give this one portfolio (Proposition 1, p. 12; Table I, p. 19).",
    "volatility": "The gain over the best zero-intercept portfolio arrives mainly through lower volatility per dollar of gross position; the mean difference is within sampling error (Section VI.A, p. 33; p. 42).",
}


def _by_lambda(rows: list[dict], label: str) -> list[dict]:
    rows = sorted(rows, key=lambda r: float(r["lambda"]))
    got = [float(r["lambda"]) for r in rows]
    if got != LAMBDAS:
        raise ValueError(f"{label}: penalty grid {got} differs from {LAMBDAS}")
    return rows


def _pair(d: float, lo: float, hi: float) -> dict:
    return {"diff": d, "lo": lo, "hi": hi, "printed": {"diff": fixed(d, 2), "lo": fixed(lo, 2), "hi": fixed(hi, 2)}}


def build(sources: Sources) -> dict:
    p_zip = sources.path(ROOT, ZIP)
    pkg = Package(p_zip)
    try:
        t3 = pkg.rows(F_TABLE3)
        curve = pkg.rows(F_CURVE)
        net = pkg.rows(F_NET)
        netcon = pkg.rows(F_NETCON)
        lad = pkg.rows(F_LADDER)
    finally:
        pkg.close()
    f_t3, f_curve, f_net, f_netcon, f_lad = (basename(f) for f in (F_TABLE3, F_CURVE, F_NET, F_NETCON, F_LADDER))
    curve = _by_lambda(curve, f_curve)
    ref = LAMBDAS.index(REFERENCE)

    inputs = []
    for iid, key, cp, nport, label, sub, label_zh, sub_zh, pk in INPUTS:
        a = _by_lambda([r for r in t3 if r["panel"] == "A" and r["row"] == key], f"{f_t3}:A/{key}")
        n = _by_lambda([r for r in net if r["portfolio"] == nport], f"{f_net}:{nport}")
        lab = f"{f_t3}:{key}"
        sharpe = [num(r["sharpe"], lab) for r in a]
        for i, r in enumerate(curve):          # Table III and Figure 4 must carry the same levels
            if num(r[f"{cp}_sharpe"], f_curve) != sharpe[i]:
                raise ValueError(f"{f_curve}: {cp}_sharpe at {LAMBDAS[i]} differs from {f_t3}")
        net25 = [num(r["net25_sharpe"], f"{f_net}:{nport}") for r in n]
        for i, r in enumerate(a):              # where Table III's own file has a net value, it must agree
            if r["net25_sharpe"] and num(r["net25_sharpe"], lab) != net25[i]:
                raise ValueError(f"{f_t3}: net25_sharpe at {LAMBDAS[i]} differs from {f_net}")
        mean = [num(r["ann_mean_pct"], lab) for r in a]
        vol = [num(r["ann_vol_pct"], lab) for r in a]
        inputs.append({
            "id": iid, "label": label, "sub": sub, "label_zh": label_zh, "sub_zh": sub_zh, "palette_key": pk,
            "gross": {
                "sharpe": sharpe, "printed": [fixed(x, 2) for x in sharpe],
                "band": {str(b): {"lo": [num(r[f"{cp}_sharpe_lo_b{b}"], f_curve) for r in curve],
                                  "hi": [num(r[f"{cp}_sharpe_hi_b{b}"], f_curve) for r in curve]} for b in BLOCKS},
                "ann_mean_pct": mean, "ann_vol_pct": vol,
                "printed_mean": [fixed(x, 1) for x in mean], "printed_vol": [fixed(x, 1) for x in vol],
            },
            "net25": {"sharpe": net25, "printed": [fixed(x, 2) for x in net25]},
        })

    # Panel B: IP minus the factor-mean portfolio at the same penalty.
    b_fm = _by_lambda([r for r in t3 if r["panel"] == "B" and r["row"] == "ip_minus_fm"], f"{f_t3}:B/ip_minus_fm")
    gross_fm = [_pair(num(r["gross_sharpe_diff"], f_t3), num(r["gross_sharpe_lo_b12"], f_t3), num(r["gross_sharpe_hi_b12"], f_t3))
                for r in b_fm]
    net_fm = []
    for lam_txt, r in zip(LAMBDA_TEXT, b_fm):
        c = one(netcon, f_netcon, family=NETCON_FAMILY, cost_bp="25", block="12", **{"lambda": lam_txt})
        pair = _pair(num(c["sharpe_diff"], f_netcon), num(c["sharpe_ci_lo"], f_netcon), num(c["sharpe_ci_hi"], f_netcon))
        if r["net25_sharpe_diff"]:
            own = _pair(num(r["net25_sharpe_diff"], f_t3), num(r["net25_sharpe_lo_b12"], f_t3), num(r["net25_sharpe_hi_b12"], f_t3))
            if own["printed"] != pair["printed"]:
                raise ValueError(f"{f_t3} and {f_netcon} disagree on the net difference at {lam_txt}")
            pair = own
        net_fm.append(pair)

    # Panel B: IP minus the best zero-intercept portfolio (IP at lambda = 0 and at the reference penalty).
    zp = []
    for r in sorted([r for r in t3 if r["panel"] == "B" and r["row"] == "ip_minus_zp"], key=lambda r: float(r["lambda"])):
        zp.append({"ip_lambda": float(r["lambda"]),
                   "gross": _pair(num(r["gross_sharpe_diff"], f_t3), num(r["gross_sharpe_lo_b12"], f_t3), num(r["gross_sharpe_hi_b12"], f_t3)),
                   "net25": _pair(num(r["net25_sharpe_diff"], f_t3), num(r["net25_sharpe_lo_b12"], f_t3), num(r["net25_sharpe_hi_b12"], f_t3))})
    if [z["ip_lambda"] for z in zp] != [0.0, REFERENCE]:
        raise ValueError(f"{f_t3}: expected IP-minus-ZP rows at 0 and {REFERENCE}")

    zg = one(lad, f_lad, **{"panel": "A gross", "row": "IPCA, Euclidean units", "lambda": "0"})
    zn = one(lad, f_lad, **{"panel": "B net25", "row": "IPCA, Euclidean units", "lambda": "0"})
    zp_sharpe = num(zg["sharpe"], f_lad)
    if any(num(r["zp_reference_sharpe"], f_curve) != zp_sharpe for r in curve):
        raise ValueError(f"{f_curve}: zp_reference_sharpe differs from {f_lad}")
    benchmark = {
        "id": "best_zp", "label": "Best zero-intercept portfolio", "sub": "IPCA without the factor penalty (lambda = 0)",
        "label_zh": "最佳零截距组合", "sub_zh": "去掉因子惩罚的 IPCA（λ = 0）", "palette_key": "ipca", "lambda": 0.0,
        "gross": {"sharpe": zp_sharpe, "printed": fixed(zp_sharpe, 2),
                  "ann_mean_pct": num(zg["ann_mean_pct"], f_lad), "ann_vol_pct": num(zg["ann_vol_pct"], f_lad),
                  "printed_mean": fixed(num(zg["ann_mean_pct"], f_lad), 1), "printed_vol": fixed(num(zg["ann_vol_pct"], f_lad), 1)},
        "net25": {"sharpe": num(zn["sharpe"], f_lad), "printed": fixed(num(zn["sharpe"], f_lad), 2)},
    }

    ip = next(i for i in inputs if i["id"] == "full_mean")
    fm = next(i for i in inputs if i["id"] == "factor_means")
    zref = zp[1]
    return {
        "meta": {
            **provenance([f_t3, f_curve, f_net, f_netcon, f_lad], RELEASE),
            "exhibit": "Table III (p. 30), Figure 4 (p. 29) and Table I (p. 19)",
            "sample": {"months": 594, "first": "1975-06", "last": "2024-11", "label": "594 months, June 1975 to November 2024"},
            "statistic": "annualised Sharpe ratio at unit gross exposure; means and volatilities annualised, in percent",
            "cost": "25 basis points per dollar traded (purchases plus sales)",
            "locators": LOCATORS,
            "notes": NOTES,
        },
        "lambdas": LAMBDAS,
        "lambda_labels": LAMBDA_TEXT,
        "reference_lambda": REFERENCE,
        "blocks": BLOCKS,
        "default_block": 12,
        "inputs": inputs,
        "benchmark": benchmark,
        "contrasts": {
            "full_minus_factor": {"label": "IP minus the factor-mean portfolio, same penalty",
                                  "label_zh": "截距组合减同一惩罚下的因子均值组合", "gross": gross_fm, "net25": net_fm},
            "full_minus_best_zp": {"label": "IP minus the best zero-intercept portfolio",
                                   "label_zh": "截距组合减最佳零截距组合", "rows": zp},
        },
        "headline": {
            "ip_ref": ip["gross"]["printed"][ref], "ip_unpenalised": ip["gross"]["printed"][0],
            "fm_ref": fm["gross"]["printed"][ref], "fm_unpenalised": fm["gross"]["printed"][0],
            "zp": benchmark["gross"]["printed"],
            "gain_vs_zp": zref["gross"]["printed"]["diff"], "gain_vs_zp_ci": [zref["gross"]["printed"]["lo"], zref["gross"]["printed"]["hi"]],
            "ip_net25_ref": ip["net25"]["printed"][ref], "zp_net25": benchmark["net25"]["printed"],
            "gain_vs_zp_net25": zref["net25"]["printed"]["diff"],
            "gain_vs_zp_net25_ci": [zref["net25"]["printed"]["lo"], zref["net25"]["printed"]["hi"]],
            "gain_vs_fm_ref": gross_fm[ref]["printed"]["diff"],
            "gain_vs_fm_ref_ci": [gross_fm[ref]["printed"]["lo"], gross_fm[ref]["printed"]["hi"]],
            "locator": "Table III, p. 30; Table I, p. 19",
        },
    }


C_IP, C_FM, C_ZP, C_MUTED = "#18557f", "#8a8378", "#6f9cc0", "#6f6a60"


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback (1200 x 630): Figure 4 Panel A with the benchmark line, and the reference-penalty readout."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Patch
    from matplotlib.ticker import NullLocator

    lams = payload["lambdas"]
    x0 = 0.001 / 10 ** 0.5
    xs = [x0 if v == 0 else v for v in lams]
    ref = lams.index(payload["reference_lambda"])
    by_id = {i["id"]: i for i in payload["inputs"]}
    zp = payload["benchmark"]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 4.2), gridspec_kw={"width_ratios": [1.25, 1]})
    for iid, col, ls in (("full_mean", C_IP, "-"), ("factor_means", C_FM, "--")):
        g = by_id[iid]["gross"]
        a1.fill_between(xs, g["band"]["12"]["lo"], g["band"]["12"]["hi"], color=col, alpha=0.15, lw=0)
        a1.plot(xs, g["sharpe"], ls, color=col, lw=1.7, marker="o", ms=3.5, label=by_id[iid]["label"])
    a1.axhline(zp["gross"]["sharpe"], color=C_ZP, lw=1.3, ls=":", label=f"{zp['label']} ({zp['gross']['printed']})")
    a1.set_xscale("log")
    a1.set_xlim(x0 / 1.7, 0.16)
    a1.set_xticks(xs, payload["lambda_labels"])
    a1.xaxis.set_minor_locator(NullLocator())
    a1.axvline(payload["reference_lambda"], color="0.6", lw=0.8, ls=":")
    a1.set_ylim(0, 3.6)
    a1.set_xlabel("Factor penalty λ (log scale; 0 categorical)", fontsize=8)
    a1.set_ylabel("Gross Sharpe ratio, annualised", fontsize=8)
    a1.set_title("Same fit, two mean inputs", fontsize=9)
    a1.legend(frameon=False, fontsize=6.8, loc="upper left")

    names = ["Factor means\nonly", "Best zero-\nintercept", "Complete\nfitted mean"]
    gross = [by_id["factor_means"]["gross"]["sharpe"][ref], zp["gross"]["sharpe"], by_id["full_mean"]["gross"]["sharpe"][ref]]
    gtxt = [by_id["factor_means"]["gross"]["printed"][ref], zp["gross"]["printed"], by_id["full_mean"]["gross"]["printed"][ref]]
    net = [by_id["factor_means"]["net25"]["sharpe"][ref], zp["net25"]["sharpe"], by_id["full_mean"]["net25"]["sharpe"][ref]]
    ntxt = [by_id["factor_means"]["net25"]["printed"][ref], zp["net25"]["printed"], by_id["full_mean"]["net25"]["printed"][ref]]
    cols = [C_FM, C_ZP, C_IP]
    x = np.arange(3)
    w = 0.38
    bg = a2.bar(x - w / 2, gross, w, color=cols)
    bn = a2.bar(x + w / 2, net, w, color=cols, alpha=0.45, hatch="///", edgecolor="white")
    for b, t in zip(bg, gtxt):
        a2.text(b.get_x() + b.get_width() / 2, max(b.get_height(), 0) + 0.06, t, ha="center", fontsize=7.5)
    for b, t in zip(bn, ntxt):
        a2.text(b.get_x() + b.get_width() / 2, max(b.get_height(), 0) + 0.06, t, ha="center", fontsize=7.5)
    a2.axhline(0, color="0.3", lw=0.8)
    a2.set_xticks(x, names, fontsize=7.5)
    a2.set_ylim(-0.3, 3.6)
    a2.set_title("At the reference penalty (λ = 0.01)", fontsize=9)
    a2.legend(handles=[Patch(facecolor="0.45", label="Gross"),
                       Patch(facecolor="0.45", alpha=0.45, hatch="///", edgecolor="white", label="Net of 25 bp")],
              frameon=False, fontsize=7, loc="upper left")
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7.5)
    fig.text(0.01, 0.012, "Bands: pointwise 95% intervals. 594 months, 1975–2024; unit gross. "
             "Source: Same Forecasts, Different Portfolios, Table III (p. 30), Figure 4 (p. 29).", fontsize=6.5, color=C_MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save_png(fig, out_png)
    plt.close(fig)
