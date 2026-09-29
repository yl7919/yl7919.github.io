#!/usr/bin/env python3
"""Rewrite the <a href> targets of one rendered HTML page to absolute URLs (spec Part B 3.2, EN step 3).

    tools/cv_abs_links.py <rendered.html> <base-url>

Quarto rewrites root-relative hrefs to relative ones in _site (`./research/x.html`, `../assets/pdfs/y.pdf`).
Printing such a page from a file:// URL would embed file:// link annotations that resolve on nobody's
machine, so `print_cv.sh` runs this on a scratch COPY of the rendered page before Chrome prints it.

Rules: only `<a ... href="...">` is touched (regex `<a\\b[^>]*\\shref="([^"]+)"`); hrefs beginning with
`mailto:`, `#` or a URL scheme (`^[a-z][a-z0-9+.-]*:`) are skipped; every other href becomes
`urllib.parse.urljoin(base, href)`. <link>, <script>, <img> are left alone so local CSS, fonts and images
still load from the copy. The file is rewritten in place and the number of rewritten hrefs is printed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

A_HREF = re.compile(r'(<a\b[^>]*\shref=")([^"]+)(")')
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def rewrite(html: str, base: str) -> tuple[str, int]:
    count = 0

    def sub(m: re.Match) -> str:
        nonlocal count
        href = m.group(2)
        if href.startswith("#") or href.startswith("mailto:") or SCHEME.match(href):
            return m.group(0)
        count += 1
        return m.group(1) + urljoin(base, href) + m.group(3)

    return A_HREF.sub(sub, html), count


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    path, base = Path(argv[1]), argv[2]
    html = path.read_text(encoding="utf-8")
    out, n = rewrite(html, base)
    path.write_text(out, encoding="utf-8")
    print(f"cv_abs_links: {n} hrefs rewritten against {base} in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
