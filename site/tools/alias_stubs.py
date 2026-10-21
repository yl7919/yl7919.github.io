#!/usr/bin/env python3
"""Post-render: make Quarto's alias redirect stubs work without JavaScript.

Quarto writes each `aliases:` entry as a stub whose only content is a script calling window.location.replace():
the old /blog/ and /zh/blog/ URLs of the Projects pages, and the old /research/ and /zh/research/ URLs of the two
renamed papers (characteristic-geometry.html -> same-forecasts-different-portfolios.html, characteristic-libraries.html
-> the-ruler-matters.html). With JavaScript off, or for link-preview bots, that is a blank page titled "Redirect".
For every stub under _site/blog/, _site/zh/blog/, _site/research/ and _site/zh/research/ this script adds, without
touching the script itself:
  - <html lang>, <meta charset>, <meta name="robots" content="noindex">
  - <link rel="canonical"> to the new page on https://mingyangliu.org
  - <noscript><meta http-equiv="refresh"></noscript> to the new page
  - a visible link: "This page has moved to Projects." / 本页已移至“项目”。 for a blog stub; for a paper stub
    "This paper has a new title and page: <title>." / 本文已更名，新页面：<title>。 (MOVED_PAPERS), or
    "This page has moved." / 本页已移动。 for any other target.
Only Quarto's own redirect stubs are touched (target_of), so the research pages themselves are never changed. It does
nothing while no stub has been written and is idempotent.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

SITE_URL = "https://mingyangliu.org"
OUT = Path(os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", "_site"))
MARK = "<!-- alias-stub-fallback -->"
STUB_DIRS = ("blog", "zh/blog", "research", "zh/research")
# New page of a renamed paper -> (EN title, ZH title), for the visible link on its old URL's stub.
MOVED_PAPERS = {
    "same-forecasts-different-portfolios.html": ("Same Forecasts, Different Portfolios", "《预测相同，组合不同》"),
    "the-ruler-matters.html": ("The Ruler Matters", "《尺子很重要》"),
}


def target_of(html: str) -> str | None:
    """The default redirect target of a Quarto alias stub (the value used when no #hash matches)."""
    # Only Quarto's own stubs: <title>Redirect</title> plus `var redirects = {"": "target", ...}`.
    if "<title>Redirect</title>" not in html or "var redirects" not in html:
        return None
    m = re.search(r'var redirects = \{[^}]*?"":\s*"([^"]+)"', html)
    return m.group(1) if m else None


def absolute(stub: Path, target: str) -> str:
    """Resolve a relative target against the stub's own URL path."""
    if target.startswith(("http://", "https://")):
        return target
    if target.startswith("/"):
        return target
    base = "/" + stub.parent.relative_to(OUT).as_posix()
    parts = [p for p in (base.rstrip("/") + "/" + target).split("/")]
    out: list[str] = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == "..":
            if out:
                out.pop()
            continue
        out.append(p)
    return "/" + "/".join(out)


def message(rel: str, url: str, zh: bool) -> str:
    """The visible line of a stub: Projects for the old blog URLs, the new title for a renamed paper."""
    if rel.startswith(("blog/", "zh/blog/")):
        return "本页已移至“项目”。" if zh else "This page has moved to Projects."
    titles = MOVED_PAPERS.get(url.rsplit("/", 1)[-1])
    if titles:
        return f"本文已更名，新页面：{titles[1]}。" if zh else f"This paper has a new title and page: {titles[0]}."
    return "本页已移动。" if zh else "This page has moved."


def patch(stub: Path) -> bool:
    html = stub.read_text(encoding="utf-8")
    if MARK in html:
        return False
    t = target_of(html)
    if not t:
        return False
    url = absolute(stub, t.split("#")[0])
    rel = stub.relative_to(OUT).as_posix()
    zh = rel.startswith("zh/")
    lang = "zh-Hans" if zh else "en"
    msg = message(rel, url, zh)
    head = (f'{MARK}<meta charset="utf-8"><meta name="robots" content="noindex">'
            f'<link rel="canonical" href="{SITE_URL}{url}">'
            f'<noscript><meta http-equiv="refresh" content="0; url={url}"></noscript>')
    body = f'<p><a href="{url}">{msg}</a></p>'
    if re.search(r"<html[^>]*\blang=", html) is None:
        html = re.sub(r"<html(\s|>)", lambda m: f'<html lang="{lang}"{m.group(1)}', html, count=1)
    elif zh:
        # Quarto writes lang="en" on every stub; a zh stub's visible line is Chinese.
        html = re.sub(r'(<html[^>]*\blang=")en(")', rf"\g<1>{lang}\g<2>", html, count=1)
    if "<head>" in html:
        html = html.replace("<head>", "<head>" + head, 1)
    else:
        html = head + html
    if "</body>" in html:
        html = html.replace("</body>", body + "</body>", 1)
    else:
        html = html + body
    stub.write_text(html, encoding="utf-8")
    return True


def main() -> None:
    n = 0
    for d in (OUT / s for s in STUB_DIRS):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.html")):
            if f.name.startswith("._"):
                continue
            n += patch(f)
    if n:
        print(f"alias_stubs: added no-JS fallbacks to {n} redirect stub(s)")


if __name__ == "__main__":
    main()
