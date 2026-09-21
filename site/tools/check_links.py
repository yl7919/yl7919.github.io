#!/usr/bin/env python3
"""Walk _site and report internal links/assets that do not resolve. Exit 1 on any failure."""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

SITE = Path(__file__).resolve().parents[1] / "_site"
ATTRS = {("a", "href"), ("img", "src"), ("link", "href"), ("script", "src"), ("source", "src")}


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if (tag, k) in ATTRS and v:
                self.refs.append(v)


def resolve(page: Path, ref: str) -> Path | None:
    u = urlparse(ref)
    if u.scheme or ref.startswith("#") or ref.startswith("mailto:") or ref.startswith("//"):
        return None
    path = unquote(u.path)
    target = (SITE / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
    target = target.resolve()
    if target.is_dir():
        target = target / "index.html"
    return target


def main() -> int:
    if not SITE.exists():
        print(f"{SITE} missing; run `quarto render` first", file=sys.stderr)
        return 2
    failures = []
    pages = [p for p in SITE.rglob("*.html") if not p.name.startswith("._")]
    for page in pages:
        c = Collector()
        c.feed(page.read_text(encoding="utf-8", errors="ignore"))
        for ref in c.refs:
            t = resolve(page, ref)
            if t is not None and not t.exists():
                failures.append(f"{page.relative_to(SITE)} -> {ref}")
    for f in failures:
        print("BROKEN", f)
    print(f"checked {len(pages)} pages, {len(failures)} broken references")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
