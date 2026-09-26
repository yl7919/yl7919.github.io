"""site/tools/check_translations.py — translated-from staleness (spec "Bilingual mechanism", Staleness)."""
import importlib.util
import subprocess
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "site" / "tools"
SPEC = importlib.util.spec_from_file_location("check_translations", TOOLS / "check_translations.py")
ct = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ct)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def commit_all(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "--short", "HEAD")


def project(tmp_path):
    repo = tmp_path / "web"
    site = repo / "site"
    (site / "zh" / "research").mkdir(parents=True)
    git(tmp_path, "init", "-q", str(repo))
    (site / "research").mkdir()
    (site / "research" / "index.qmd").write_text("---\ntitle: Research\n---\nv1\n")
    (site / "cv.qmd").write_text("---\ntitle: CV\n---\nv1\n")
    sha1 = commit_all(repo, "en v1")
    (site / "zh" / "research" / "index.qmd").write_text(
        f"---\ntitle: 研究\ntranslation: /research/index.html\ntranslated-from: {sha1}\n---\n译\n")
    (site / "zh" / "cv.qmd").write_text("---\ntitle: 简历\ntranslation: /cv.html\n---\n译\n")      # no translated-from
    commit_all(repo, "zh")
    return repo, site, sha1


def by_page(site):
    return {r["zh"]: r for r in ct.rows(site)}


def test_current_missing_and_later_unrelated_commit(tmp_path):
    repo, site, sha1 = project(tmp_path)
    rows = by_page(site)
    assert rows["zh/research/index.qmd"]["status"] == "current"
    assert rows["zh/research/index.qmd"]["en"] == "research/index.qmd"
    assert rows["zh/cv.qmd"]["status"] == "MISSING"
    # translated-from = a later HEAD that did not touch the English source (the OWNER.md workflow) is current
    (site / "other.qmd").write_text("x\n")
    head = commit_all(repo, "unrelated")
    p = site / "zh" / "research" / "index.qmd"
    p.write_text(p.read_text().replace(sha1, head))
    commit_all(repo, "zh bump")
    assert by_page(site)["zh/research/index.qmd"]["status"] == "current"


def test_english_change_makes_it_stale_and_strict_fails(tmp_path, monkeypatch, capsys):
    repo, site, sha1 = project(tmp_path)
    (site / "research" / "index.qmd").write_text("---\ntitle: Research\n---\nv2\n")
    assert by_page(site)["zh/research/index.qmd"]["status"] == "STALE"          # uncommitted edit
    commit_all(repo, "en v2")
    row = by_page(site)["zh/research/index.qmd"]
    assert row["status"] == "STALE" and "1 commit(s)" in row["note"]
    monkeypatch.setattr(ct, "PROJECT", site)
    assert ct.main([]) == 0                  # warn by default
    assert ct.main(["--strict"]) == 1
    assert "STALE" in capsys.readouterr().err


def test_unknown_sha_is_missing(tmp_path):
    repo, site, sha1 = project(tmp_path)
    p = site / "zh" / "research" / "index.qmd"
    p.write_text(p.read_text().replace(sha1, "deadbee"))
    assert by_page(site)["zh/research/index.qmd"]["status"] == "MISSING"
