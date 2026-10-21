"""The Ruler Matters: measure exposure on today's stocks or on March's? Current-Q against annual-origin Q.

With annual coefficients fixed, the current version of the characteristic ruler (today's stocks, Q_t) and the
annual-origin version (the March cross section, held until the next fit) give two complete portfolio
policies. Each estimate is 100 x [1 - Var(current) / Var(origin)] over 216 common return months, with
simultaneous 95% intervals within a twelve-comparison family (19,999 calendar-block draws).

Sources: the paper's evidence/stage3 files
  CURRENT_ORIGIN_12_VARIANCE_FWER.csv     original positive target: Figure 6 (p. 35), Table IA.31 (p. 97);
                                          26.62% to 69.39% lower variance, nine of twelve intervals exclude zero
  CURRENT_ORIGIN_12_DESCRIPTIVE_LEVELS.csv the same twelve pairs' levels: Table IA.32 (p. 99)
  family_E2_signed_12.csv                 the training rule's signed target: Figure IA.5 (p. 77), Table IA.13 (p. 78);
                                          eight of twelve intervals exclude zero
(tables/ruler_updating.csv is a different comparison, training-average against current Q at unit gross,
Table IA.3 on p. 65; it does not print the 26.62-69.39% range.)
"""
from __future__ import annotations

from pathlib import Path

from common import provenance
from exhibits._paper_data import fixed, num, one, read_rows, save_png
from sources import Sources

ROOT = "ruler_matters"
F_POSITIVE = "evidence/stage3/CURRENT_ORIGIN_12_VARIANCE_FWER.csv"
F_LEVELS = "evidence/stage3/CURRENT_ORIGIN_12_DESCRIPTIVE_LEVELS.csv"
F_SIGNED = "evidence/stage3/family_E2_signed_12.csv"
RELEASE = "The Ruler Matters: Factor Exposures, Attribution, and Portfolio Risk (October 2026), paper evidence files"

# Table order: source intercept, then library, then characteristic.
INTERCEPTS = [("free", "Unrestricted", "Free", "无约束截距"), ("zero", "Zero", "Zero", "零截距")]
LIBRARIES = [36, 153]
TARGETS = [
    ("bm", "be_me", "Book-to-market", "账面市值比"),
    ("mom", "ret_12_1", "Momentum", "动量"),
    ("size", "market_equity", "Larger-firm size", "市值（大公司方向）"),
]
FAMILIES = {
    "positive": {
        "file": F_POSITIVE, "n": 12, "n_exclude": 9,
        "label": "Same original positive tilt", "label_zh": "相同的原始正向倾向",
        "exhibit": "Figure 6 (p. 35) and Table IA.31 (p. 97)",
        "note": "Specified after the training-reference feasibility outcome; conditions on the fitted models (Figure 6 note, p. 35).",
    },
    "signed": {
        "file": F_SIGNED, "n": 12, "n_exclude": 8,
        "label": "The training rule's signed tilt", "label_zh": "训练期规则的带符号倾向",
        "exhibit": "Figure IA.5 (p. 77) and Table IA.13 (p. 78)",
        "note": "Matches the training-reference portfolio's signed tilt, which can be negative; a separate inference family (Table IA.13 note, p. 78).",
    },
}
# Table IA.32 columns: JSON key, CSV column suffix, printed decimals
LEVEL_COLS = [
    ("mean_bp", "mean_return_bp_month", 2),
    ("vol_bp", "volatility_bp_month", 2),
    ("gross_median", "gross_median", 3),
    ("gross_max", "gross_max", 3),
    ("turnover_frac", "turnover_oneway_mean", 5),
]
LOCATORS = {
    "positive": "Section VI.B, pp. 32-34; Figure 6, p. 35; Table IA.31, p. 97",
    "levels": "Table IA.32, p. 99",
    "signed": "Section VI.A, pp. 31-32; Figure IA.5, p. 77; Table IA.13, p. 78",
}
NOTES = {
    "not_causal": "Complete policies with different current loading restrictions, not the causal effect of changing only the reference date (p. 6).",
    "above_100": "Upper endpoints above 100% come from the untransformed symmetric approximation; they are not feasible variance reductions (Figure 6 note, p. 35).",
    "levels": "Levels are descriptive; the lower-risk rule does not uniformly improve mean returns, gross holdings or turnover (Table IA.32 note, p. 99).",
    "turnover": "Turnover in the levels is a fraction of NAV per month, not a percentage (Table IA.32 note, p. 99).",
}


def _family_rows(path: Path, rows: list[dict]) -> list[dict]:
    out = []
    for iid, icsv, _l, _z in INTERCEPTS:
        for lib in LIBRARIES:
            for tid, anchor, _tl, _tz in TARGETS:
                r = one(rows, path.name, source_intercept=icsv, library=str(lib), anchor=anchor)
                lab = f"{path.name}:{icsv}/{lib}/{anchor}"
                v = {"estimate": num(r["estimate"], lab), "lo": num(r["familywise_ci_low"], lab),
                     "hi": num(r["familywise_ci_high"], lab), "p_adj": num(r["single_step_adjusted_p"], lab)}
                excl = r["familywise_excludes_zero"] == "True"
                if excl != (v["lo"] > 0 or v["hi"] < 0):
                    raise ValueError(f"{lab}: familywise_excludes_zero disagrees with the interval")
                out.append({"intercept": iid, "library": lib, "target": tid, **v, "excludes_zero": excl,
                            "printed": {"estimate": fixed(v["estimate"], 2), "lo": fixed(v["lo"], 2),
                                        "hi": fixed(v["hi"], 2), "p_adj": fixed(v["p_adj"], 5)}})
    return out


def build(sources: Sources) -> dict:
    families, paths = {}, []
    for fid, spec in FAMILIES.items():
        p = sources.path(ROOT, spec["file"])
        paths.append(p)
        rows = read_rows(p)
        if len(rows) != spec["n"]:
            raise ValueError(f"{p.name}: expected {spec['n']} comparisons, found {len(rows)}")
        fam = _family_rows(p, rows)
        n_ex = sum(r["excludes_zero"] for r in fam)
        if n_ex != spec["n_exclude"]:
            raise ValueError(f"{p.name}: {n_ex} intervals exclude zero, the paper reports {spec['n_exclude']}")
        lo = min(fam, key=lambda r: r["estimate"])
        hi = max(fam, key=lambda r: r["estimate"])
        families[fid] = {
            "label": spec["label"], "label_zh": spec["label_zh"], "exhibit": spec["exhibit"],
            "locator": LOCATORS[fid], "note": spec["note"],
            "n": len(fam), "n_exclude_zero": n_ex,
            "range": {"min": lo["estimate"], "max": hi["estimate"],
                      "printed": [lo["printed"]["estimate"], hi["printed"]["estimate"]]},
            "rows": fam,
        }

    p_lev = sources.path(ROOT, F_LEVELS)
    paths.insert(1, p_lev)
    lev_rows = read_rows(p_lev)
    levels = []
    for iid, icsv, _l, _z in INTERCEPTS:
        for lib in LIBRARIES:
            for tid, anchor, _tl, _tz in TARGETS:
                r = one(lev_rows, p_lev.name, source_intercept=icsv, library=str(lib), anchor=anchor)
                entry = {"intercept": iid, "library": lib, "target": tid}
                for rule in ("origin", "current"):
                    lab = f"{p_lev.name}:{icsv}/{lib}/{anchor}/{rule}"
                    vals = {key: num(r[f"{rule}_{col}"], lab) for key, col, _ in LEVEL_COLS}
                    entry[rule] = {**vals, "printed": {key: fixed(vals[key], d) for key, _c, d in LEVEL_COLS}}
                levels.append(entry)

    return {
        "meta": {
            **provenance(paths, RELEASE),
            "exhibit": "Figure 6 (p. 35), Tables IA.31 (p. 97) and IA.32 (p. 99); Figure IA.5 (p. 77) and Table IA.13 (p. 78)",
            "model": "FFC6 plus three latent factors; annual coefficients fixed from March; source intercept unrestricted or zero; 36 or 153 characteristics",
            "statistic": "100 x [1 - Var(current) / Var(origin)], % of origin variance; positive values favour the current ruler",
            "intervals": "simultaneous (familywise) 95% intervals within each twelve-comparison family; 19,999 twelve-month circular calendar-block draws",
            "sample": {"formation_months": 225, "return_months": 216, "turnover_months": 219},
            "units": {"mean_bp": "mean excess return, bp per month", "vol_bp": "volatility, bp per month",
                      "gross_median": "median gross holdings / NAV", "gross_max": "maximum gross holdings / NAV",
                      "turnover_frac": "mean one-way turnover, fraction of NAV per month"},
            "locators": LOCATORS,
            "notes": NOTES,
        },
        "rulers": [
            {"id": "current", "label": "Current ruler (today's stocks)", "label_zh": "特征尺子的当月版本（当月股票）", "palette_key": "complete"},
            {"id": "origin", "label": "Annual-origin ruler (the March cross section)", "label_zh": "特征尺子的年初（3 月）版本", "palette_key": "beta_only"},
        ],
        "intercepts": [{"id": i, "label": lab, "label_zh": zh} for i, _c, lab, zh in INTERCEPTS],
        "libraries": LIBRARIES,
        "targets": [{"id": t, "label": lab, "label_zh": zh} for t, _a, lab, zh in TARGETS],
        "families": families,
        "levels": levels,
    }


C_IN, C_OUT, C_MUTED = "#18557f", "#9a9a9a", "#6f6a60"


def render_png(payload: dict, out_png: Path) -> None:
    """Static fallback (1200 x 630) of Figure 6: estimate and simultaneous interval for the twelve comparisons."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fam = payload["families"]["positive"]
    tl = {t["id"]: t["label"] for t in payload["targets"]}
    il = {i["id"]: i["label"] for i in payload["intercepts"]}
    fig, axes = plt.subplots(1, 2, figsize=(8, 4.2), sharex=True)
    for ax, iid in zip(axes, ("free", "zero")):
        rows = [r for r in fam["rows"] if r["intercept"] == iid]
        ys = list(range(len(rows)))[::-1]
        for y, r in zip(ys, rows):
            col = C_IN if r["excludes_zero"] else C_OUT
            ax.hlines(y, r["lo"], r["hi"], color=col, lw=1.6)
            ax.plot(r["estimate"], y, "o", color=col, ms=5)
            ax.annotate(r["printed"]["estimate"], (r["estimate"], y), textcoords="offset points", xytext=(0, 5),
                        ha="center", fontsize=6.5, color=col)
        ax.axvline(0, color="0.35", lw=0.9)
        ax.set_yticks(ys, [f"{r['library']}: {tl[r['target']]}" for r in rows], fontsize=7.5)
        ax.set_title(f"{il[iid]} source intercept", fontsize=9)
        ax.set_xlabel("Lower variance than under origin (%)", fontsize=7.5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.5)
        ax.set_xlim(-30, 135)
    fig.text(0.01, 0.012, f"Bars: simultaneous 95% intervals; grey bars include zero ({fam['n_exclude_zero']} of {fam['n']} exclude it). "
             "216 return months. Source: The Ruler Matters, Figure 6 (p. 35), Table IA.31 (p. 97).", fontsize=6.5, color=C_MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save_png(fig, out_png)
    plt.close(fig)
