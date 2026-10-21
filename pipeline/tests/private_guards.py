"""Names that generated files must never contain, kept out of the public repository.

The list lives in the git-ignored pipeline/sources.toml ([private_guards] banned_names), as tools/check_cv.py
does for the CV. On a clean clone without that file the list is empty and the tests check only the generic
patterns they spell out themselves.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "sources.toml"


def banned_names() -> tuple[str, ...]:
    try:
        with open(CONFIG, "rb") as fh:
            names = tomllib.load(fh).get("private_guards", {}).get("banned_names", [])
    except FileNotFoundError:
        return ()
    return tuple(str(n) for n in names if str(n))
