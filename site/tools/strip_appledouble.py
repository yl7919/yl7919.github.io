#!/usr/bin/env python3
"""Post-render: remove macOS AppleDouble ("._*") side files from the render output directory.

On an exFAT volume macOS writes a "._name" companion next to files it touches, so a local
`quarto render` litters _site/ with them (they even appear under site_libs/). They are
build artefacts of the output directory only — never source files — and check_links.py
rule (i) requires that no "._*" file ships in _site. CI renders on Linux and is unaffected.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def output_dir() -> Path:
    env = os.environ.get("QUARTO_PROJECT_OUTPUT_DIR")
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = Path(os.environ.get("QUARTO_PROJECT_DIR", Path(__file__).resolve().parents[1])) / p
        return p
    return Path(__file__).resolve().parents[1] / "_site"


def main() -> int:
    out = output_dir()
    if not out.is_dir():
        return 0
    removed = 0
    for p in out.rglob("._*"):
        if p.is_file() or p.is_symlink():
            try:
                p.unlink()
                removed += 1
            except OSError as e:  # never fail the render over a stray side file
                print(f"strip_appledouble: could not remove {p}: {e}", file=sys.stderr)
    print(f"strip_appledouble: removed {removed} AppleDouble file(s) from {out.name}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
