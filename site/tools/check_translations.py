#!/usr/bin/env python3
"""Translation staleness report (spec "Bilingual mechanism", Staleness).

For every Chinese page site/zh/**/*.qmd, compare its `translated-from:` commit with the last commit
that changed the English source (`git log -1 --format=%h -- <en path>`), and print a table.

The English source is the page named by the zh file's `translation:` key (e.g. /research/index.html
-> site/research/index.qmd); without that key it is the same path with the leading zh/ removed.

Status per page:
  current   translated-from is the last commit that changed the English source, or a later commit that
            contains it (the OWNER.md workflow sets translated-from to HEAD right after committing the English
            change; the spec compares the two shas for equality, which would flag such a page as stale)
  STALE     the English source changed after translated-from
  MISSING   no translated-from key, the English source does not exist, or the sha is unknown to git
Uncommitted edits to an English source also mark its page STALE.

Default: print the table, exit 0 (warnings only). --strict: exit 1 when any page is STALE or MISSING
(used by tools/precommit.sh). Shallow clones cannot answer this; CI checks out with fetch-depth: 0.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]      # web/site
FIELD = re.compile(r"^(translation|translated-from):\s*(.*?)\s*(?:#.*)?$", re.M)


def git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else ""


def front_matter_fields(qmd: Path) -> dict[str, str]:
    text = qmd.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = re.search(r"^---\s*$", text[3:], re.M)
    head = text[3:3 + end.start()] if end else ""
    return {k: v.strip("\"'") for k, v in FIELD.findall(head)}


def english_source(project: Path, zh_qmd: Path, translation: str | None) -> Path:
    if translation:
        path = translation.split("#")[0].lstrip("/")
        if path == "" or path.endswith("/"):
            path += "index.html"
        return project / Path(path).with_suffix(".qmd")
    return project / zh_qmd.relative_to(project / "zh")


def rows(project: Path | None = None) -> list[dict]:
    project = PROJECT if project is None else project
    repo = Path(git(project, "rev-parse", "--show-toplevel") or project)
    out = []
    zh_pages = sorted(p for p in (project / "zh").rglob("*.qmd")
                      if not p.name.startswith("._") and not p.name.startswith("_"))
    for zh in zh_pages:
        f = front_matter_fields(zh)
        en = english_source(project, zh, f.get("translation"))
        sha = f.get("translated-from", "")
        row = {"zh": zh.relative_to(project).as_posix(), "en": en.relative_to(project).as_posix()
               if en.is_relative_to(project) else str(en), "translated_from": sha or "-", "en_last": "-",
               "status": "current", "note": ""}
        if not en.exists():
            row.update(status="MISSING", note="English source not found")
        elif not sha:
            row.update(status="MISSING", note="no translated-from key")
        else:
            rel = en.relative_to(repo).as_posix()
            last_full = git(repo, "log", "-1", "--format=%H", "--", rel)
            row["en_last"] = git(repo, "log", "-1", "--format=%h", "--", rel) or "-"
            sha_full = git(repo, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
            if not sha_full:
                row.update(status="MISSING", note=f"{sha} is not a commit in this repository")
            elif not last_full:
                row.update(status="STALE", note="English source is not committed")
            elif sha_full != last_full:
                # translated-from older than the last English change -> stale; newer (a later commit that
                # did not touch the source) is fine: that commit already contains the latest English.
                is_ancestor = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                                              last_full, sha_full]).returncode == 0
                if not is_ancestor:
                    n = git(repo, "rev-list", "--count", f"{sha_full}..{last_full}", "--", rel)
                    row.update(status="STALE", note=f"English changed in {n or '?'} commit(s) since {sha}")
            if row["status"] == "current" and git(repo, "status", "--porcelain", "--", rel):
                row.update(status="STALE", note="English source has uncommitted changes")
        out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--strict", action="store_true", help="exit 1 when any translation is stale or missing")
    args = ap.parse_args(argv)
    table = rows()
    head = ("zh page", "English source", "translated-from", "EN last change", "status")
    data = [(r["zh"], r["en"], r["translated_from"], r["en_last"], r["status"]) for r in table]
    widths = [max(len(x) for x in col) for col in zip(head, *data)]
    for line in (head, tuple("-" * w for w in widths), *data):
        print("  ".join(x.ljust(w) for x, w in zip(line, widths)).rstrip())
    bad = [r for r in table if r["status"] != "current"]
    for r in bad:
        print(f"{'ERROR' if args.strict else 'WARNING'}: {r['zh']} is {r['status']}: {r['note']}", file=sys.stderr)
    print(f"{len(table)} translations, {len(bad)} stale or missing")
    return 1 if (bad and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
