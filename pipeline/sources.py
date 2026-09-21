"""Locate research-release source directories from sources.toml."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / "sources.toml"


@dataclass(frozen=True)
class Sources:
    geometry_release: Path

    def geo(self, relative: str) -> Path:
        p = self.geometry_release / relative
        if not p.exists():
            raise FileNotFoundError(f"geometry_release file not found: {relative} (under {self.geometry_release})")
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
    for key in ("geometry_release",):
        if key not in roots:
            raise KeyError(f"sources.toml [roots] is missing '{key}'")
        p = Path(roots[key]).expanduser()
        if not p.is_dir():
            raise FileNotFoundError(f"{key} directory does not exist: {p}")
        resolved[key] = p
    return Sources(**resolved)
