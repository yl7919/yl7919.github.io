"""Locate research-source directories from sources.toml.

`geometry_release` is required. Further roots are optional and are listed in
OPTIONAL_ROOTS; an exhibit asks for one with `sources.path(root, relative)`, which
raises a clear error when the root is not configured or the file is missing.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / "sources.toml"
REQUIRED_ROOTS = ("geometry_release",)
OPTIONAL_ROOTS = (
    "jmp_results",            # Codex project_JobMarket/04_results/r3
    "csm_presentation",       # extracted Characteristic_Space_Metrics_Presentation.zip
    "geometric_framework",    # extracted A_Geometric_Framework ... .zip
    "pricing_errors",         # extracted Interpreting Estimated Pricing Errors Overleaf.zip
)


@dataclass(frozen=True)
class Sources:
    geometry_release: Path
    extra: dict = field(default_factory=dict)

    def geo(self, relative: str) -> Path:
        p = self.geometry_release / relative
        if not p.exists():
            raise FileNotFoundError(f"geometry_release file not found: {relative} (under {self.geometry_release})")
        return p

    def path(self, root: str, relative: str) -> Path:
        if root == "geometry_release":
            return self.geo(relative)
        base = self.extra.get(root)
        if base is None:
            raise KeyError(f"sources.toml [roots] has no '{root}'; add it to use this exhibit")
        p = base / relative
        if not p.exists():
            raise FileNotFoundError(f"{root} file not found: {relative} (under {base})")
        return p


def load_sources(config_path: Path = DEFAULT_CONFIG) -> Sources:
    if not config_path.exists():
        raise FileNotFoundError(
            f"{config_path} not found. Copy sources.example.toml to sources.toml and set absolute paths."
        )
    with open(config_path, "rb") as fh:
        data = tomllib.load(fh)
    roots = data.get("roots", {})
    resolved = {}
    for key in REQUIRED_ROOTS:
        if key not in roots:
            raise KeyError(f"sources.toml [roots] is missing '{key}'")
        p = Path(roots[key]).expanduser()
        if not p.is_dir():
            raise FileNotFoundError(f"{key} directory does not exist: {p}")
        resolved[key] = p
    extra = {}
    for key in OPTIONAL_ROOTS:
        if key in roots:
            p = Path(roots[key]).expanduser()
            if not p.is_dir():
                raise FileNotFoundError(f"{key} directory does not exist: {p}")
            extra[key] = p
    return Sources(extra=extra, **resolved)
