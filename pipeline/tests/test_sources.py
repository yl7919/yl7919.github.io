from pathlib import Path

import pytest

from sources import Sources, load_sources


def test_load_sources_reads_toml(tmp_path: Path):
    geo = tmp_path / "geo"
    geo.mkdir()
    cfg = tmp_path / "sources.toml"
    cfg.write_text(f'[roots]\ngeometry_release = "{geo}"\n', encoding="utf-8")
    s = load_sources(cfg)
    assert isinstance(s, Sources)
    assert s.geometry_release == geo


def test_missing_root_raises(tmp_path: Path):
    cfg = tmp_path / "sources.toml"
    cfg.write_text('[roots]\ngeometry_release = "/nonexistent/path"\n', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="geometry_release"):
        load_sources(cfg)


def test_require_file_reports_relative_path(tmp_path: Path):
    geo = tmp_path / "geo"
    geo.mkdir()
    s = Sources(geometry_release=geo)
    with pytest.raises(FileNotFoundError, match="missing.csv"):
        s.geo("missing.csv")
    (geo / "ok.csv").write_text("a\n")
    assert s.geo("ok.csv") == geo / "ok.csv"
