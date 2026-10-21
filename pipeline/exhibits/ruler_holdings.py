"""The Ruler Matters: which ruler hedges? Plain ruler (coefficient orthogonality) against the characteristic
ruler (stock-loading neutrality measured on the current stocks, Q_t), same model, same stocks, same target.

Source: the paper's tables/holdings.csv (Table IA.2, p. 63; Section V.A, p. 24; pp. 5-6) and
tables/matched_holdings.csv (Table IA.41, p. 112; Figure IA.3, p. 64). Unrestricted characteristic
intercept, 153 characteristics, FFC6 plus three latent factors; unit gross holdings at formation.
Under the plain ruler the hedge leaves 46.10% (book-to-market), 53.51% (momentum) and 65.13% (larger-firm
size) of the squared stock-weight norm in the loading space; under the characteristic ruler 0.00.
The matched rows scale the loading-neutral holdings to the plain-ruler hedge's signed tilt each month.
"""
from __future__ import annotations

from pathlib import Path

from common import provenance
from exhibits._paper_data import fixed, num, one, read_rows, save_png
from sources import Sources

ROOT = "ruler_matters"
F_HOLD = "tables/holdings.csv"
F_MATCH = "tables/matched_holdings.csv"
RELEASE = "The Ruler Matters: Factor Exposures, Attribution, and Portfolio Risk (October 2026), paper tables"
MODEL = "Unrestricted, 153"

# id, CSV label, page label, ZH label
TARGETS = [
    ("bm", "Book-to-market", "Book-to-market", "账面市值比"),
    ("mom", "Momentum", "Momentum", "动量"),
    ("size", "Firm size", "Larger-firm size", "市值（大公司方向）"),
]
# id, CSV projection, label, ZH label, rule, ZH rule, palette key of the site's OJS helpers
RULERS = [
    ("plain", "Coefficient", "Plain ruler", "普通尺子", "coefficient orthogonality", "系数正交", "ipca"),
    ("characteristic", "Stock exposure", "Characteristic ruler", "特征尺子",
     "stock-loading neutrality on the current stocks", "以当月股票衡量的股票载荷中性", "qz_ipca"),
]
# JSON key, CSV column, printed decimals (Table IA.2)
UNIT_GROSS_COLS = [
    ("loading_share_pct", "Loading share", 2),
    ("mean_bp", "Mean (bp)", 2),
    ("vol_bp", "Vol. (bp)", 2),
    ("turnover_pct", "Turnover", 2),
]
# JSON key, CSV column, printed decimals (Table IA.41)
MATCHED_COLS = [
    ("mean_gross", "Mean gross", 2),
    ("gross_p95", "95th gross", 2),
    ("vol_bp", "Vol. bp", 2),
    ("variance_reduction_pct", "Variance reduction", 2),
]

LOCATORS = {
    "unit_gross": "Table IA.2, p. 63",
    "matched_tilt": "Table IA.41, p. 112; Figure IA.3, p. 64",
    "headline": "Section V.A, p. 24; Section I.B, pp. 5-6; Table IA.2, p. 63",
}
NOTES = {
    "zero": "A displayed 0.00 reflects the imposed stock-loading restriction and rounding, not zero future return risk (Table IA.2 note, p. 63).",
    "equal_gross": "Equal gross does not hold the desired characteristic exposure fixed (Table IA.2 note, p. 63).",
    "share": "The loading-projection share is a share of the squared stock-weight norm, not of return variance (pp. 5-6).",
    "matched": "The matched rows scale the loading-neutral holdings each month to the plain-ruler hedge's signed tilt; gross holdings may then differ from one (Figure IA.3, p. 64; Table IA.41, p. 112).",
}


def build(sources: Sources) -> dict:
    p_hold = sources.path(ROOT, F_HOLD)
    p_match = sources.path(ROOT, F_MATCH)
    hold = read_rows(p_hold)
    match = read_rows(p_match)
    if len(hold) != len(TARGETS) * len(RULERS):
        raise ValueError(f"{p_hold.name}: expected {len(TARGETS) * len(RULERS)} rows, found {len(hold)}")

    unit_gross = []
    for tid, tcsv, _l, _z in TARGETS:
        for rid, rcsv, *_ in RULERS:
            r = one(hold, p_hold.name, Target=tcsv, Projection=rcsv)
            vals = {key: num(r[col], f"{p_hold.name}:{tcsv}/{rcsv}/{col}") for key, col, _ in UNIT_GROSS_COLS}
            unit_gross.append({"target": tid, "ruler": rid, **vals,
                               "printed": {key: fixed(vals[key], d) for key, _c, d in UNIT_GROSS_COLS}})

    matched = []
    for tid, tcsv, _l, _z in TARGETS:
        r = one(match, p_match.name, Model=MODEL, Target=tcsv)
        vals = {key: num(r[col], f"{p_match.name}:{tcsv}/{col}") for key, col, _ in MATCHED_COLS}
        matched.append({"target": tid, **vals, "sign_flips": int(r["Sign flips"]),
                        "printed": {key: fixed(vals[key], d) for key, _c, d in MATCHED_COLS}})

    def share(tid: str, rid: str) -> str:
        return next(r for r in unit_gross if r["target"] == tid and r["ruler"] == rid)["printed"]["loading_share_pct"]

    return {
        "meta": {
            **provenance([p_hold, p_match], RELEASE),
            "exhibit": "Table IA.2 (p. 63), Figure IA.3 (p. 64) and Table IA.41 (p. 112)",
            "model": "Unrestricted characteristic intercept, 153 characteristics, FFC6 plus three latent factors",
            "sample": {"formation_months": 225, "return_months": 216, "turnover_months": 219},
            "units": {"loading_share_pct": "% of the squared stock-weight norm in the joint loading space",
                      "mean_bp": "mean excess return, bp per month", "vol_bp": "volatility, bp per month",
                      "turnover_pct": "one-way turnover, % of NAV per month",
                      "mean_gross": "mean gross holdings / NAV", "gross_p95": "95th-percentile gross / NAV",
                      "variance_reduction_pct": "% lower variance than the plain-ruler hedge"},
            "locators": LOCATORS,
            "notes": NOTES,
        },
        "targets": [{"id": t, "label": lab, "label_zh": zh} for t, _c, lab, zh in TARGETS],
        "rulers": [{"id": r, "label": lab, "label_zh": zh, "rule": rule, "rule_zh": rule_zh, "palette_key": pk}
                   for r, _c, lab, zh, rule, rule_zh, pk in RULERS],
        "unit_gross": unit_gross,
        "matched_tilt": matched,
        "headline": {
            "plain_loading_share_pct": {t: share(t, "plain") for t, *_ in TARGETS},
            "characteristic_loading_share_pct": {t: share(t, "characteristic") for t, *_ in TARGETS},
            "locator": LOCATORS["headline"],
        },
    }


C_PLAIN, C_CHAR, C_MUTED = "#6f9cc0", "#8a6a1a", "#6f6a60"


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback (1200 x 630): loading share left in the loading space, and subsequent volatility."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    targets = payload["targets"]
    labels = [t["label"] for t in targets]
    row = {(r["target"], r["ruler"]): r for r in payload["unit_gross"]}
    mt = {r["target"]: r for r in payload["matched_tilt"]}
    x = np.arange(len(targets))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4.2), gridspec_kw={"width_ratios": [1, 1.25]})
    w = 0.36
    for k, (rid, col) in enumerate((("plain", C_PLAIN), ("characteristic", C_CHAR))):
        vals = [row[(t["id"], rid)]["loading_share_pct"] for t in targets]
        bars = ax1.bar(x + (k - 0.5) * w, vals, w, color=col,
                       label=next(r["label"] for r in payload["rulers"] if r["id"] == rid))
        for b, t in zip(bars, targets):
            ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2, row[(t["id"], rid)]["printed"]["loading_share_pct"],
                     ha="center", va="bottom", fontsize=7.5)
    ax1.set_xticks(x, labels, fontsize=8)
    ax1.set_ylim(0, 80)
    ax1.set_ylabel("Left in the loading space (% of squared weights)", fontsize=8)
    ax1.set_title("After the hedge, unit gross", fontsize=9)
    ax1.legend(frameon=False, fontsize=7.5, loc="upper left")

    w = 0.27
    series = [("Plain ruler, unit gross", C_PLAIN, [row[(t["id"], "plain")]["vol_bp"] for t in targets], None),
              ("Characteristic ruler, unit gross", C_CHAR, [row[(t["id"], "characteristic")]["vol_bp"] for t in targets], None),
              ("Characteristic ruler at the plain hedge's tilt", "#c9b98f", [mt[t["id"]]["vol_bp"] for t in targets],
               [mt[t["id"]]["printed"]["mean_gross"] for t in targets])]
    for k, (lab, col, vals, gross) in enumerate(series):
        bars = ax2.bar(x + (k - 1) * w, vals, w, color=col, label=lab)
        if gross:
            for b, g in zip(bars, gross):
                ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 3, f"gross {g}", ha="center", va="bottom", fontsize=6.5)
    ax2.set_xticks(x, labels, fontsize=8)
    ax2.set_ylim(0, 300)
    ax2.set_ylabel("Subsequent volatility (bp per month)", fontsize=8)
    ax2.set_title("Risk that followed", fontsize=9)
    ax2.legend(frameon=False, fontsize=7, loc="upper left")
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7.5)
    fig.text(0.01, 0.012, "Unrestricted intercept, 153 characteristics; 216 return months. "
             "Source: The Ruler Matters, Tables IA.2 (p. 63) and IA.41 (p. 112).", fontsize=6.5, color=C_MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save_png(fig, out_png)
    plt.close(fig)
