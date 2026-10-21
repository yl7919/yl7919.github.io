from pathlib import Path

import pytest

from sources import OPTIONAL_ROOTS, Sources, load_sources


def test_optional_root_listed():
    assert "dynamic_geometry" in OPTIONAL_ROOTS


def test_round11_paper_roots_listed():
    for root in ("ruler_matters", "same_forecasts", "same_forecasts_package"):
        assert root in OPTIONAL_ROOTS
    example = (Path(__file__).resolve().parents[1] / "sources.example.toml").read_text(encoding="utf-8")
    for root in ("ruler_matters", "same_forecasts", "same_forecasts_package"):
        assert f"\n{root} = \"/absolute/path/" in example


def test_optional_root_is_loaded(tmp_path: Path):
    geo, rm = tmp_path / "geo", tmp_path / "rm"
    geo.mkdir()
    rm.mkdir()
    cfg = tmp_path / "sources.toml"
    cfg.write_text(f'[roots]\ngeometry_release = "{geo}"\nruler_matters = "{rm}"\n', encoding="utf-8")
    s = load_sources(cfg)
    assert s.extra["ruler_matters"] == rm
    (rm / "tables").mkdir()
    (rm / "tables" / "x.csv").write_text("a\n")
    assert s.path("ruler_matters", "tables/x.csv") == rm / "tables" / "x.csv"
    with pytest.raises(FileNotFoundError, match="ruler_matters file not found"):
        s.path("ruler_matters", "tables/missing.csv")


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
