"""Shared helpers for the October 2026 paper exhibits (ruler_* and sf_* modules).

Not an exhibit: the leading underscore keeps build_data.py from discovering it.

* `read_rows` reads a CSV with the csv module, so every number is Python's float() of the text the paper's
  code wrote (no pandas parser rounding): "numbers exactly as the CSV gives them".
* `Package` reads members of the Same Forecasts replication-package zip by their path under the package's
  top folder (e.g. "data/core/10_sharpe_by_lambda_594.csv"); the top folder's name is never written to
  tracked code or to the public JSON, and provenance carries basenames only.
* `fixed` / `sci` format a value the way the papers print it (fixed decimals, or a one-decimal mantissa
  times a power of ten), with the site's typographic minus (U+2212) and no negative zero.
"""
from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from pathlib import Path, PurePosixPath

MINUS = "−"
_SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def num(text: str, label: str = "") -> float:
    """float() of a CSV cell; empty or non-finite cells are an error, never a silent NaN."""
    if text is None or str(text).strip() == "":
        raise ValueError(f"{label}: empty cell where a number is required")
    x = float(text)
    if not math.isfinite(x):
        raise ValueError(f"{label}: non-finite value {text!r}")
    return x


def fixed(x: float, d: int) -> str:
    """Fixed decimals as printed; U+2212 for negatives; a value that rounds to zero prints without a sign."""
    s = f"{float(x):.{d}f}"
    if s.startswith("-"):
        return s[1:] if float(s[1:]) == 0 else MINUS + s[1:]
    return s


def sci(x: float, d: int = 1) -> str:
    """Mantissa with d decimals times a power of ten, e.g. 1.0 × 10⁻¹¹ (Table II, Panel A style)."""
    mant, exp = f"{float(x):.{d}e}".split("e")
    sign = MINUS if mant.startswith("-") else ""
    return f"{sign}{mant.lstrip('-')} × 10{str(int(exp)).translate(_SUP)}"


def read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def one(rows: list[dict], label: str, **match) -> dict:
    """The single row whose fields equal `match` (string comparison on the CSV text)."""
    hit = [r for r in rows if all(r.get(k) == v for k, v in match.items())]
    if len(hit) != 1:
        raise ValueError(f"{label}: expected one row for {match}, found {len(hit)}")
    return hit[0]


class Package:
    """Read-only view of the replication-package zip; members are addressed below the zip's single top folder."""

    def __init__(self, zip_path: Path):
        self.path = Path(zip_path)
        self._zip = zipfile.ZipFile(self.path)
        tops = {PurePosixPath(n).parts[0] for n in self._zip.namelist() if n.strip("/")}
        if len(tops) != 1:
            raise ValueError(f"{self.path.name}: expected one top-level folder, found {len(tops)}")
        self._top = tops.pop()

    def _member(self, relative: str) -> str:
        name = f"{self._top}/{relative}"
        if name not in self._zip.namelist():
            raise FileNotFoundError(f"{self.path.name}: no member {relative!r} under the package's top folder")
        return name

    def read_bytes(self, relative: str) -> bytes:
        return self._zip.read(self._member(relative))

    def rows(self, relative: str) -> list[dict[str, str]]:
        text = self.read_bytes(relative).decode("utf-8")
        return list(csv.DictReader(io.StringIO(text, newline="")))

    def json(self, relative: str):
        return json.loads(self.read_bytes(relative).decode("utf-8"))

    def close(self) -> None:
        self._zip.close()


def basename(relative: str) -> str:
    return PurePosixPath(relative).name


def assert_text_inside(fig, name: str, dpi: int = 150) -> None:
    """Every text of the figure must lie inside the canvas (a clipped footer shipped once on the site)."""
    import matplotlib.text

    fig.set_dpi(dpi)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    w, h = fig.get_size_inches() * dpi
    # Tick labels are placed by matplotlib along the axes (and those outside the view limits are never drawn
    # although their Text objects linger), so the guard covers titles, axis labels, legends and annotations.
    ticks = {id(lab) for ax in fig.axes for axis in (ax.xaxis, ax.yaxis)
             for tk in axis.majorTicks + axis.minorTicks for lab in (tk.label1, tk.label2)}
    for txt in fig.findobj(matplotlib.text.Text):
        if id(txt) in ticks or not txt.get_visible() or not txt.get_text():
            continue
        bb = txt.get_window_extent(renderer)
        if bb.x0 < 0 or bb.y0 < 0 or bb.x1 > w or bb.y1 > h:
            raise ValueError(f"{name}: text runs outside the canvas: {txt.get_text()!r}")


def save_png(fig, out_png: Path, dpi: int = 150) -> None:
    assert_text_inside(fig, out_png.name, dpi)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, facecolor="white")
