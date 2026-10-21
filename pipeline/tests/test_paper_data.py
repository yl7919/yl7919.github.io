"""Helpers shared by the October 2026 paper exhibits (exhibits/_paper_data.py); no research sources needed."""
import zipfile
from pathlib import Path

import pytest

from exhibits import _paper_data as pdx


def test_fixed_as_the_papers_print():
    assert pdx.fixed(46.10034864032723, 2) == "46.10"
    assert pdx.fixed(-8.542169861325236, 2) == "−8.54"           # typographic minus
    assert pdx.fixed(-0.00419246979, 2) == "0.00"                       # Table III prints 0.00, not -0.00
    assert pdx.fixed(4.9519424300669514e-27, 2) == "0.00"
    assert pdx.fixed(99.99999999999996, 2) == "100.00"
    assert pdx.fixed(7.590655204, 1) == "7.6" and pdx.fixed(12.380379, 3) == "12.380"


def test_sci_as_table_ii_prints():
    assert pdx.sci(1.013683581518876e-11) == "1.0 × 10⁻¹¹"
    assert pdx.sci(4.848806729060372e-06) == "4.8 × 10⁻⁶"
    assert pdx.sci(0.0001360969311771) == "1.4 × 10⁻⁴"
    assert pdx.sci(-2.5e-9) == "−2.5 × 10⁻⁹"


def test_num_rejects_empty_and_non_finite():
    assert pdx.num("1.5", "x") == 1.5
    for bad in ("", "nan", "inf"):
        with pytest.raises(ValueError):
            pdx.num(bad, "x")


def test_one_requires_a_unique_match():
    rows = [{"a": "1", "b": "x"}, {"a": "1", "b": "y"}]
    assert pdx.one(rows, "t", a="1", b="y") == {"a": "1", "b": "y"}
    with pytest.raises(ValueError, match="found 2"):
        pdx.one(rows, "t", a="1")
    with pytest.raises(ValueError, match="found 0"):
        pdx.one(rows, "t", a="2")


def test_package_reads_below_the_single_top_folder(tmp_path: Path):
    z = tmp_path / "pkg.zip"
    with zipfile.ZipFile(z, "w") as fh:
        fh.writestr("some-top-folder/data/core/x.csv", "a,b\n1,2\n")
        fh.writestr("some-top-folder/data/core/y.json", '{"k": 3}')
    p = pdx.Package(z)
    try:
        assert p.rows("data/core/x.csv") == [{"a": "1", "b": "2"}]
        assert p.json("data/core/y.json") == {"k": 3}
        with pytest.raises(FileNotFoundError, match="data/core/z.csv"):
            p.read_bytes("data/core/z.csv")
    finally:
        p.close()
    assert pdx.basename("data/core/x.csv") == "x.csv"


def test_package_refuses_several_top_folders(tmp_path: Path):
    z = tmp_path / "two.zip"
    with zipfile.ZipFile(z, "w") as fh:
        fh.writestr("a/x.csv", "a\n")
        fh.writestr("b/x.csv", "a\n")
    with pytest.raises(ValueError, match="one top-level folder"):
        pdx.Package(z)


def test_text_guard_catches_a_clipped_footer(tmp_path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.5, 1.5])                                      # an out-of-range tick is never drawn: ignored
    fig.text(0.01, 0.01, "short footer", fontsize=7)
    pdx.save_png(fig, tmp_path / "ok.png")
    fig.text(0.9, 0.01, "x" * 120, fontsize=7)
    with pytest.raises(ValueError, match="outside the canvas"):
        pdx.save_png(fig, tmp_path / "bad.png")
    plt.close(fig)
