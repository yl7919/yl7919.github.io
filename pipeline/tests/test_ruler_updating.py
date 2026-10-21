"""ruler_updating: The Ruler Matters, Current against annual-origin Q.

Figure 6 (p. 35) / Table IA.31 (p. 97): 26.62% to 69.39% lower variance, nine of twelve simultaneous intervals
exclude zero; Table IA.32 (p. 99) levels; Figure IA.5 (p. 77) / Table IA.13 (p. 78): eight of twelve.
Skipped when sources.toml or its `ruler_matters` root is missing.
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from exhibits import ruler_updating as ru
from sources import load_sources

from private_guards import banned_names

PIPELINE = Path(__file__).resolve().parents[1]
WEB = PIPELINE.parent
CONFIG = PIPELINE / "sources.toml"
FORBIDDEN = ("/Volumes", "/Users", "owner_package", "Claude") + banned_names()
M = "−"

# Table IA.31 (p. 97): estimate, familywise CI, adjusted p, in table order.
TABLE_IA31 = [
    ("free", 36, "bm", "28.34", "5.28", "51.40", "0.01460"),
    ("free", 36, "mom", "57.22", "10.96", "103.49", "0.01395"),
    ("free", 36, "size", "55.81", "11.68", "99.93", "0.01205"),
    ("free", 153, "bm", "35.74", M + "1.64", "73.11", "0.06255"),
    ("free", 153, "mom", "40.29", "9.78", "70.81", "0.00920"),
    ("free", 153, "size", "32.17", M + "1.58", "65.91", "0.06345"),
    ("zero", 36, "bm", "26.62", "6.42", "46.83", "0.00920"),
    ("zero", 36, "mom", "69.39", "11.91", "126.87", "0.01600"),
    ("zero", 36, "size", "57.94", "9.79", "106.09", "0.01635"),
    ("zero", 153, "bm", "35.67", "2.33", "69.01", "0.03450"),
    ("zero", 153, "mom", "41.69", "15.72", "67.66", "0.00250"),
    ("zero", 153, "size", "36.48", M + "2.68", "75.64", "0.07125"),
]
# Table IA.13 (p. 78).
TABLE_IA13 = [
    ("free", 36, "bm", "27.18", "9.08", "45.27", "0.00445"),
    ("free", 36, "mom", "44.45", "12.98", "75.93", "0.00650"),
    ("free", 36, "size", "28.36", M + "19.68", "76.40", "0.33500"),
    ("free", 153, "bm", "32.40", "4.91", "59.89", "0.02105"),
    ("free", 153, "mom", "41.97", "16.58", "67.35", "0.00225"),
    ("free", 153, "size", "18.61", M + "8.38", "45.59", "0.21555"),
    ("zero", 36, "bm", "25.80", "9.47", "42.14", "0.00310"),
    ("zero", 36, "mom", "45.44", "18.45", "72.42", "0.00200"),
    ("zero", 36, "size", "33.01", M + "10.75", "76.77", "0.16060"),
    ("zero", 153, "bm", "33.81", "7.80", "59.82", "0.01150"),
    ("zero", 153, "mom", "42.37", "20.54", "64.20", "0.00075"),
    ("zero", 153, "size", "22.80", M + "3.77", "49.38", "0.09945"),
]
# Table IA.32 (p. 99): (origin, current) x (mean, vol, median gross, max gross, turnover fraction), selected rows.
TABLE_IA32 = {
    ("free", 36, "mom"): (("25.30", "312.30", "2.244", "8.861", "0.87293"), ("18.30", "204.26", "2.306", "3.031", "0.81404")),
    ("free", 153, "mom"): (("32.76", "195.75", "1.579", "2.742", "0.57536"), ("34.42", "151.25", "1.587", "2.242", "0.57838")),
    ("zero", 36, "mom"): ((M + "15.58", "385.57", "2.314", "12.380", "0.92294"), (M + "24.74", "213.32", "2.394", "3.137", "0.83174")),
    ("zero", 36, "size"): ((M + "0.29", "421.43", "3.447", "11.679", "1.08863"), ("31.60", "273.32", "3.404", "4.094", "0.91687")),
    ("free", 153, "size"): ((M + "20.61", "184.70", "1.929", "3.276", "0.54506"), (M + "15.66", "152.12", "1.921", "2.286", "0.51285")),
}
LEVEL_KEYS = ("mean_bp", "vol_bp", "gross_median", "gross_max", "turnover_frac")


@pytest.fixture(scope="module")
def sources():
    if not CONFIG.exists():
        pytest.skip("sources.toml not configured on this machine")
    s = load_sources(CONFIG)
    if "ruler_matters" not in s.extra:
        pytest.skip("ruler_matters root not configured")
    return s


@pytest.fixture(scope="module")
def payload(sources):
    return ru.build(sources)


def _rows(fam):
    return [(r["intercept"], r["library"], r["target"], r["printed"]["estimate"], r["printed"]["lo"],
             r["printed"]["hi"], r["printed"]["p_adj"]) for r in fam["rows"]]


def test_positive_family_as_printed(payload):
    fam = payload["families"]["positive"]
    assert _rows(fam) == TABLE_IA31
    assert fam["n"] == 12 and fam["n_exclude_zero"] == 9                      # "Nine of twelve" (p. 34; Figure 6, p. 35)
    assert fam["range"]["printed"] == ["26.62", "69.39"]                      # Section VI.B; Section XI, p. 47


def test_the_three_positive_intervals_that_include_zero(payload):
    inc = {(r["intercept"], r["library"], r["target"]) for r in payload["families"]["positive"]["rows"] if not r["excludes_zero"]}
    assert inc == {("free", 153, "bm"), ("free", 153, "size"), ("zero", 153, "size")}
    above = [r for r in payload["families"]["positive"]["rows"] if r["hi"] > 100]
    assert len(above) == 3                                                      # three upper endpoints above 100% (p. 97)


def test_signed_family_as_printed(payload):
    fam = payload["families"]["signed"]
    assert _rows(fam) == TABLE_IA13
    assert fam["n_exclude_zero"] == 8
    assert all(not r["excludes_zero"] for r in fam["rows"] if r["target"] == "size")


def test_levels_as_printed(payload):
    got = {(r["intercept"], r["library"], r["target"]):
           (tuple(r["origin"]["printed"][k] for k in LEVEL_KEYS), tuple(r["current"]["printed"][k] for k in LEVEL_KEYS))
           for r in payload["levels"]}
    assert len(got) == 12
    for key, want in TABLE_IA32.items():
        assert got[key] == want, key
    assert max(r["origin"]["gross_max"] for r in payload["levels"]) == pytest.approx(12.3804, abs=5e-5)   # p. 98
    assert max(r["current"]["gross_max"] for r in payload["levels"]) == pytest.approx(4.0945, abs=5e-5)


def test_provenance(payload):
    meta = payload["meta"]
    assert meta["source_files"] == ["CURRENT_ORIGIN_12_VARIANCE_FWER.csv", "CURRENT_ORIGIN_12_DESCRIPTIVE_LEVELS.csv",
                                    "family_E2_signed_12.csv"]
    assert all("/" not in f for f in meta["source_files"])
    assert "Figure 6, p. 35" in meta["locators"]["positive"] and "Table IA.31, p. 97" in meta["locators"]["positive"]
    assert meta["locators"]["levels"] == "Table IA.32, p. 99"
    assert not any(f in json.dumps(payload, ensure_ascii=False) for f in FORBIDDEN)


def test_interval_flag_guard_rejects_inconsistent_rows(sources, tmp_path, monkeypatch):
    """A CSV whose familywise_excludes_zero contradicts its own interval must stop the build."""
    src = sources.path("ruler_matters", ru.F_POSITIVE)
    text = src.read_text(encoding="utf-8").replace(",False,", ",True,", 1)
    bad = tmp_path / "bad.csv"
    bad.write_text(text, encoding="utf-8")
    real = sources.path
    monkeypatch.setattr(type(sources), "path", lambda self, root, rel: bad if rel == ru.F_POSITIVE else real(root, rel))
    with pytest.raises(ValueError, match="disagrees"):
        ru.build(sources)


def test_build_check_and_png(tmp_path, payload):
    base = [sys.executable, str(PIPELINE / "build_data.py"), "--exhibit", "ruler_updating",
            "--data-dir", str(tmp_path / "data"), "--img-dir", str(tmp_path / "img")]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
    png = tmp_path / "img" / "ruler_updating.png"
    assert struct.unpack(">II", png.read_bytes()[16:24]) == (1200, 630) and png.stat().st_size <= 150_000
    assert (tmp_path / "data" / "ruler_updating.json").stat().st_size <= 40_000
    res = subprocess.run(base + ["--check"], capture_output=True, text=True)
    assert res.returncode == 0 and "ruler_updating: unchanged" in res.stdout


def test_shipped_json_matches_fresh_build(payload):
    shipped = json.loads((WEB / "site" / "data" / "ruler_updating.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(payload))
    for p in (shipped, fresh):
        p["meta"].pop("built_at", None)
    assert shipped == fresh
