#!/usr/bin/env python3
"""Walk _site and report internal links/assets that do not resolve. Exit 1 on any failure.

Rules implemented here:
- internal references (a/href, img/src, srcset, link/href, script/src, source/src) must resolve inside _site;
- rule (g), spec D22: no OJS cell name may be defined twice on one page. Quarto embeds every page's
  OJS source as base64 JSON in <script type="ojs-module-contents">; the runtime raises
  "<name> is defined more than once" for duplicates, so the build fails first.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

SITE = Path(__file__).resolve().parents[1] / "_site"
ATTRS = {("a", "href"), ("img", "src"), ("link", "href"), ("script", "src"), ("source", "src")}
OJS_MODULE = re.compile(r'<script type="ojs-module-contents">\s*(.*?)\s*</script>', re.S)
# A top-level OJS definition starts at column 0: `name = ...`, `viewof name = ...`, `mutable name = ...`.
# Statements inside a cell body (`{ ... }`) are indented in this project, so they do not match;
# `==`/`===`/`=>` are excluded by the lookahead.
OJS_DEF = re.compile(r"^(?:viewof\s+|mutable\s+)?([A-Za-z_$][\w$]*)\s*=(?![=>])", re.M)


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if (tag, k) in ATTRS and v:
                self.refs.append(v)
            elif (tag, k) in {("img", "srcset"), ("source", "srcset")} and v:
                for candidate in v.split(","):
                    token = candidate.strip().split()
                    if token:
                        self.refs.append(token[0])


def resolve(page: Path, ref: str) -> Path | None:
    u = urlparse(ref)
    if u.scheme or ref.startswith("#") or ref.startswith("mailto:") or ref.startswith("//"):
        return None
    path = unquote(u.path)
    target = (SITE / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
    target = target.resolve()
    if SITE.resolve() not in target.parents and target != SITE.resolve():
        return SITE / "__escapes_site__" / path.lstrip("/")  # guaranteed missing -> reported as BROKEN
    if target.is_dir():
        target = target / "index.html"
    return target


def ojs_definitions(source: str) -> list[str]:
    """Names defined at the top level of one OJS cell source (a `viewof x` defines `x`)."""
    return [m.group(1) for m in OJS_DEF.finditer(source)]


def ojs_cell_sources(html: str) -> list[str]:
    """Every OJS cell source embedded in a rendered page, in document order."""
    sources: list[str] = []
    for blob in OJS_MODULE.findall(html):
        module = json.loads(base64.b64decode(blob))
        cells = module.get("contents", module) if isinstance(module, dict) else module
        for cell in cells:
            src = cell.get("source") if isinstance(cell, dict) else None
            if isinstance(src, str):
                sources.append(src)
    return sources


def duplicate_cells(html: str) -> dict[str, int]:
    """Rule (g): OJS cell names defined more than once on one page -> {name: count}."""
    counts = Counter(name for src in ojs_cell_sources(html) for name in ojs_definitions(src))
    return {name: n for name, n in counts.items() if n > 1}


def main() -> int:
    if not SITE.exists():
        print(f"{SITE} missing; run `quarto render` first", file=sys.stderr)
        return 2
    failures = []
    pages = [p for p in SITE.rglob("*.html") if not p.name.startswith("._")]
    for page in pages:
        html = page.read_text(encoding="utf-8", errors="ignore")
        c = Collector()
        c.feed(html)
        for ref in c.refs:
            t = resolve(page, ref)
            if t is not None and not t.exists():
                failures.append(f"BROKEN {page.relative_to(SITE)} -> {ref}")
        for name, n in sorted(duplicate_cells(html).items()):
            failures.append(f"DUPLICATE-CELL {page.relative_to(SITE)} -> {name} defined {n} times")
    for f in failures:
        print(f)
    print(f"checked {len(pages)} pages, {len(failures)} broken references")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
