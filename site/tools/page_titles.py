#!/usr/bin/env python3
"""Post-render: set the exact <title> of the two home pages (SEO plan 2026-10-01, item 1).

Quarto writes "<page title> – <site title>" for every page whose title differs from the site title. For the home
pages that would print the name twice, so the rendered <title> is replaced by the exact string below; nothing else
in the file changes. Idempotent; runs on every render (full or partial) and only touches files that exist.
"""
import html
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", "_site"))
TITLES = {
    "index.html": "Mingyang Liu (刘明杨, also Yang Liu) · PhD in Finance, Imperial College London",
    "zh/index.html": "刘明杨（Mingyang Liu，又名 Yang Liu）· 帝国理工学院金融学博士",
}

for rel, title in TITLES.items():
    f = OUT / rel
    if not f.exists():
        continue
    s = f.read_text(encoding="utf-8")
    t = re.sub(r"<title>.*?</title>", "<title>" + html.escape(title, quote=False) + "</title>", s, count=1, flags=re.S)
    if t != s:
        f.write_text(t, encoding="utf-8")
        print(f"page_titles: {rel}: <title> set")
