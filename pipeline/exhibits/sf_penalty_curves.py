"""Same Forecasts, Different Portfolios: the Sharpe ratio along the factor penalty, with the penalty written in
each normalisation's own units or in one set of units.

Two normalisations of one IPCA fit, the Euclidean (plain ruler) and the Gram (characteristic ruler), forecast
the same returns. A constant lambda added to each fit's factor covariance is a penalty written in that fit's
own units, so one number gives two portfolios: 0.69 and 1.07 at the reference penalty 0.01, 1.62 for both
without the penalty. Written in one set of units (Proposition 1, p. 12) the two fits hold one portfolio; the
paper computes that row at lambda = 0.01 (0.69, Table I) and states it equals the Euclidean row at every lambda.

Source: the replication package's data/core files (read inside the package zip; basenames only in the JSON)
  10_sharpe_by_lambda_594.csv  Figure 1 (p. 4), Table I Panel A (p. 19), Figure 3 (p. 26)
  10_contrasts_594.csv         Table II Panel B (p. 24), Figure 1 Panel B
  13_ladder_594.csv            Table I (p. 19): the unit-consistent rows
  13_holdings_594.json         Table II Panel A (p. 24): how far apart the two fits' stock weights are
594 months, June 1975 to November 2024; gross returns at unit gross exposure.
"""
from __future__ import annotations

from pathlib import Path

from common import provenance, round_sig
from exhibits._paper_data import Package, basename, fixed, num, one, save_png, sci
from sources import Sources

ROOT = "same_forecasts_package"
ZIP = "Replication_Package.zip"
F_LEVELS = "data/core/10_sharpe_by_lambda_594.csv"
F_CONTRASTS = "data/core/10_contrasts_594.csv"
F_LADDER = "data/core/13_ladder_594.csv"
F_HOLDINGS = "data/core/13_holdings_594.json"
RELEASE = "Same Forecasts, Different Portfolios: Factor Normalization and Regularization (October 2026), replication data"

LAMBDAS = [0.0, 0.001, 0.003, 0.01, 0.03, 0.1]
LAMBDA_TEXT = ["0", "0.001", "0.003", "0.01", "0.03", "0.1"]
REFERENCE = 0.01
BLOCKS = [12, 24, 60]
MONTHS = 594

# id, CSV family, label, ZH label, palette key of the site's OJS helpers
SERIES = [
    ("euclid", "IPCA Euclidean", "IPCA, Euclidean units (plain ruler)", "IPCA，欧氏单位（普通尺子）", "ipca"),
    ("gram", "IPCA Gram", "IPCA, Gram units (characteristic ruler)", "IPCA，格拉姆单位（特征尺子）", "qz_ipca"),
    ("rppca", "RP-PCA", "RP-PCA", "风险溢价主成分分析（RP-PCA）", "rp_pca"),
    ("ff5", "FF5", "FF5 (characteristic-instrumented)", "FF5（以特征为工具）", "ff5"),
]
# id, CSV kind, label, ZH label
DIFFS = [
    ("gram_minus_euclid", "gram_minus_euclid", "Gram minus Euclidean fit", "格拉姆拟合减欧氏拟合"),
    ("rppca_minus_euclid", "rppca_minus_ipca_euclid", "RP-PCA minus Euclidean fit", "RP-PCA 减欧氏拟合"),
]
# 13_holdings_594.json key, JSON id, label (Table II Panel A rows)
WEIGHT_ROWS = [
    ("prod_Q_vs_I", "own_units", "Reference penalty, own units"),
    ("transp_Q_vs_I", "one_set_euclidean", "Gram fit, penalty in Euclidean units"),
    ("qzridge_I_vs_prodQ", "one_set_gram", "Euclidean fit, penalty in Gram units"),
    ("free_Q_vs_free_I", "unpenalised", "Both unpenalised (lambda = 0)"),
]
LOCATORS = {
    "figure": "Figure 1, p. 4",
    "levels": "Table I, Panel A, p. 19",
    "diff": "Table II, Panel B, p. 24",
    "weights": "Table II, Panel A, p. 24",
    "penalty_removal": "Table II, Panel C, p. 24; Section IV.C, pp. 23-24",
    "families": "Figure 3, p. 26",
    "identity": "Proposition 1, p. 12; Section IV.B, p. 22",
}
NOTES = {
    "gross": "Gross returns at unit gross exposure, before trading costs; 594 months, June 1975 to November 2024.",
    "bands": "Pointwise 95% intervals from a moving-block bootstrap (12-month blocks in the paper's figures) that holds the fitted models fixed.",
    "lambda_axis": "lambda = 0 is a categorical tick on a logarithmic axis (Figure 1, p. 4).",
    "one_set": "Written in one set of units, the Gram fit with the penalty in Euclidean units holds the Euclidean fit's portfolio; the paper computes this row at lambda = 0.01 only and, by Proposition 1, it equals the Euclidean row at every lambda (Table I caption, p. 19).",
    "same_forecasts": "The two fits' stock forecasts differ by a median relative gap of 4.8 x 10^-6 (Table II, Panel A, p. 24).",
}


def _ix(rows_lambda: list[str]) -> list[int]:
    got = [float(x) for x in rows_lambda]
    if got != LAMBDAS:
        raise ValueError(f"penalty grid {got} differs from {LAMBDAS}")
    return list(range(len(LAMBDAS)))


def build(sources: Sources) -> dict:
    p_zip = sources.path(ROOT, ZIP)
    pkg = Package(p_zip)
    try:
        lev = pkg.rows(F_LEVELS)
        con = pkg.rows(F_CONTRASTS)
        lad = pkg.rows(F_LADDER)
        hold = pkg.json(F_HOLDINGS)
    finally:
        pkg.close()
    f_lev = basename(F_LEVELS)

    series = []
    for sid, fam, label, label_zh, pk in SERIES:
        rows = sorted([r for r in lev if r["family"] == fam], key=lambda r: float(r["lambda_F"]))
        _ix([r["lambda_F"] for r in rows])
        for r in rows:
            if int(r["months"]) != MONTHS:
                raise ValueError(f"{f_lev}: {fam} at {r['lambda_F']} has {r['months']} months")
        lab = f"{f_lev}:{fam}"
        sharpe = [num(r["sharpe"], lab) for r in rows]
        series.append({
            "id": sid, "label": label, "label_zh": label_zh, "palette_key": pk,
            "sharpe": sharpe, "printed": [fixed(x, 2) for x in sharpe],
            "ann_mean_pct": [num(r["ann_mean_pct"], lab) for r in rows],
            "ann_vol_pct": [num(r["ann_vol_pct"], lab) for r in rows],
            "band": {str(b): {"lo": [num(r[f"sharpe_lo_b{b}"], lab) for r in rows],
                              "hi": [num(r[f"sharpe_hi_b{b}"], lab) for r in rows]} for b in BLOCKS},
        })

    diffs = []
    for did, kind, label, label_zh in DIFFS:
        out = {"id": did, "label": label, "label_zh": label_zh, "diff": [], "band": {}}
        for b in BLOCKS:
            rows = sorted([r for r in con if r["kind"] == kind and r["block"] == str(b)], key=lambda r: float(r["lambda_F"]))
            _ix([r["lambda_F"] for r in rows])
            lab = f"{basename(F_CONTRASTS)}:{kind}/b{b}"
            d = [num(r["sharpe_diff"], lab) for r in rows]
            if out["diff"] and d != out["diff"]:
                raise ValueError(f"{lab}: point estimates differ across blocks")
            out["diff"] = d
            out["band"][str(b)] = {"lo": [num(r["sharpe_ci_lo"], lab) for r in rows],
                                   "hi": [num(r["sharpe_ci_hi"], lab) for r in rows]}
        out["printed"] = [fixed(x, 2) for x in out["diff"]]
        out["printed_ci"] = [[fixed(lo, 2), fixed(hi, 2)] for lo, hi in zip(out["band"]["12"]["lo"], out["band"]["12"]["hi"])]
        diffs.append(out)

    # Table II, Panel C: removing the reference penalty (lambda = 0 minus lambda = 0.01), 12-month blocks.
    removal = []
    for sid, fam, *_ in SERIES:
        r = one(con, basename(F_CONTRASTS), kind="lam0_minus_lam0.01", family=fam, block="12")
        lab = f"{basename(F_CONTRASTS)}:lam0_minus_lam0.01/{fam}"
        v = {"diff": num(r["sharpe_diff"], lab), "lo": num(r["sharpe_ci_lo"], lab), "hi": num(r["sharpe_ci_hi"], lab),
             "mean_diff_pp": num(r["ann_mean_diff_pp"], lab), "mean_lo": num(r["ann_mean_ci_pp_lo"], lab),
             "mean_hi": num(r["ann_mean_ci_pp_hi"], lab)}
        removal.append({"series": sid, **v, "printed": {k: fixed(x, 2) for k, x in v.items()}})

    # Table I: the unit-consistent rows (computed at the reference penalty only).
    f_lad = basename(F_LADDER)
    uc_e = one(lad, f_lad, **{"panel": "A gross", "row": "IPCA, unit-consistent penalty", "lambda": "0.01"})
    uc_g = one(lad, f_lad, **{"panel": "A gross", "row": "IPCA, unit-consistent penalty (variant F)", "lambda": "0.01"})
    for r in (uc_e, uc_g):
        if r["status"] != "computed":
            raise ValueError(f"{f_lad}: unit-consistent row at 0.01 is not computed")
    ref = LAMBDAS.index(REFERENCE)
    by_id = {s["id"]: s for s in series}
    uc_e_v, uc_g_v = num(uc_e["sharpe"], f_lad), num(uc_g["sharpe"], f_lad)

    def one_set(curve: str, fit: str, value: float, row_label: str) -> dict:
        status = ["computed" if i in (0, ref) else "by_identity" for i in range(len(LAMBDAS))]
        return {
            "curve": curve,
            "sharpe": by_id[curve]["sharpe"], "printed": by_id[curve]["printed"],
            "status": status,
            "check": {"lambda": REFERENCE, "fit": fit, "sharpe": value, "printed": fixed(value, 2),
                      "abs_diff_from_curve": round_sig(abs(value - by_id[curve]["sharpe"][ref]), 3),
                      "source": f"Table I, Panel A, row '{row_label}' (p. 19)"},
        }

    units = {
        "default": "own",
        "own": {"label": "Each normalisation's own units", "label_zh": "各自的单位",
                "curves": ["euclid", "gram"]},
        "one_set": {"label": "One set of units (Euclidean)", "label_zh": "统一单位（欧氏）",
                    **one_set("euclid", "gram", uc_e_v, "IPCA, unit-consistent penalty")},
        "one_set_gram": {"label": "One set of units (Gram)", "label_zh": "统一单位（格拉姆）",
                         **one_set("gram", "euclid", uc_g_v, "IPCA, unit-consistent penalty (variant F): table note only")},
    }

    weights = {}
    for key, wid, label in WEIGHT_ROWS:
        block = hold[key]
        omc, l1 = block["one_minus_cosine"], block["unit_gross_L1_distance"]
        fmt = (lambda x: fixed(x, 2)) if wid == "own_units" else sci
        weights[wid] = {"label": label,
                        "one_minus_cosine": {"median": omc["median"], "max": omc["max"],
                                             "printed": {"median": fmt(omc["median"]), "max": fmt(omc["max"])}},
                        "l1_distance": {"median": l1["median"], "max": l1["max"],
                                        "printed": {"median": fmt(l1["median"]), "max": fmt(l1["max"])}}}
    gap = hold["forecast_gap"]
    weights["forecast_gap"] = {"median": gap["median"], "max": gap["max"],
                               "printed": {"median": sci(gap["median"]), "max": sci(gap["max"])}}

    e, g = by_id["euclid"], by_id["gram"]
    gm = next(d for d in diffs if d["id"] == "gram_minus_euclid")
    return {
        "meta": {
            **provenance([basename(f) for f in (F_LEVELS, F_CONTRASTS, F_LADDER, F_HOLDINGS)], RELEASE),
            "exhibit": "Figure 1 (p. 4); Table I, Panel A (p. 19); Table II, Panels A-B (p. 24); Figure 3 (p. 26)",
            "sample": {"months": MONTHS, "first": "1975-06", "last": "2024-11", "label": "594 months, June 1975 to November 2024"},
            "statistic": "annualised gross Sharpe ratio at unit gross exposure",
            "locators": LOCATORS,
            "notes": NOTES,
        },
        "lambdas": LAMBDAS,
        "lambda_labels": LAMBDA_TEXT,
        "reference_lambda": REFERENCE,
        "blocks": BLOCKS,
        "default_block": 12,
        "series": series,
        "units": units,
        "diffs": diffs,
        "penalty_removal": removal,
        "weights": weights,
        "headline": {
            "euclid_ref": e["printed"][ref], "gram_ref": g["printed"][ref],
            "diff_ref": gm["printed"][ref], "diff_ref_ci": gm["printed_ci"][ref],
            "unpenalised": e["printed"][0], "unpenalised_gram": g["printed"][0],
            "unit_consistent_ref": fixed(uc_e_v, 2),
            "weights_own_units_median": weights["own_units"]["one_minus_cosine"]["printed"]["median"],
            "weights_one_set_median": weights["one_set_euclidean"]["one_minus_cosine"]["printed"]["median"],
            "locator": "Table I, p. 19; Table II, p. 24; Figure 1, p. 4",
        },
    }


C_E, C_G, C_MUTED = "#6f9cc0", "#8a6a1a", "#6f6a60"


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback (1200 x 630, also fit for a card thumbnail): Figure 1's two panels."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import NullLocator

    lams = payload["lambdas"]
    x0 = 0.001 / 10 ** 0.5
    xs = [x0 if v == 0 else v for v in lams]
    ref = lams.index(payload["reference_lambda"])
    by_id = {s["id"]: s for s in payload["series"]}
    gm = next(d for d in payload["diffs"] if d["id"] == "gram_minus_euclid")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 4.2))
    for sid, col, ls, mk in (("euclid", C_E, "-", "o"), ("gram", C_G, "--", "s")):
        s = by_id[sid]
        a1.fill_between(xs, s["band"]["12"]["lo"], s["band"]["12"]["hi"], color=col, alpha=0.16, lw=0)
        a1.plot(xs, s["sharpe"], ls, color=col, marker=mk, ms=4, lw=1.6, label=s["label"])
    a1.annotate(by_id["euclid"]["printed"][ref], (xs[ref], by_id["euclid"]["sharpe"][ref]), textcoords="offset points",
                xytext=(-8, -12), ha="right", fontsize=7.5, color=C_E)
    a1.annotate(by_id["gram"]["printed"][ref], (xs[ref], by_id["gram"]["sharpe"][ref]), textcoords="offset points",
                xytext=(0, 9), ha="center", fontsize=7.5, color=C_G)
    a1.annotate(by_id["euclid"]["printed"][0], (xs[0], by_id["euclid"]["sharpe"][0]), textcoords="offset points",
                xytext=(6, 6), ha="left", fontsize=7.5, color="0.25")
    a1.set_ylabel("Gross Sharpe ratio, annualised", fontsize=8)
    a1.set_title("Penalty written in each fit's own units", fontsize=9)
    a1.legend(frameon=False, fontsize=7, loc="lower left")

    a2.fill_between(xs, gm["band"]["12"]["lo"], gm["band"]["12"]["hi"], color=C_G, alpha=0.16, lw=0)
    a2.axhline(0, color="0.2", lw=1.2)
    a2.plot(xs, gm["diff"], "-", color=C_G, marker="D", ms=3.6, lw=1.5, label=gm["label"])
    check = payload["units"]["one_set"]["check"]
    a2.plot([xs[ref]], [check["sharpe"] - by_id["euclid"]["sharpe"][ref]], "o", ms=7, mfc="white", mec="k", mew=1.2, zorder=5)
    a2.annotate("one set of units", (xs[ref], 0), textcoords="offset points", xytext=(10, -16), fontsize=7.5)
    a2.set_ylabel("Difference in Sharpe ratio", fontsize=8)
    a2.set_title("Gram minus Euclidean fit", fontsize=9)

    for ax in (a1, a2):
        ax.set_xscale("log")
        ax.set_xlim(x0 / 1.7, 0.16)
        ax.set_xticks(xs, payload["lambda_labels"])
        ax.xaxis.set_minor_locator(NullLocator())
        ax.axvline(payload["reference_lambda"], color="0.6", lw=0.8, ls=":")
        ax.set_xlabel("Factor penalty λ (log scale; 0 categorical)", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7.5)
        ax.set_ylim(-0.5, 2.15)
    fig.text(0.01, 0.012, "Pointwise 95% bands. 594 months, 1975\u20132024; before trading costs. "
             "Source: Same Forecasts, Different Portfolios, Figure 1 (p. 4).", fontsize=6.5, color=C_MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save_png(fig, out_png)
    plt.close(fig)
