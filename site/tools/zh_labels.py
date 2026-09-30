#!/usr/bin/env python3
"""Post-render: rewrite static navbar/footer labels in _site/zh/**/*.html (spec "Bilingual mechanism").

Quarto passes the rendered output list in QUARTO_PROJECT_OUTPUT_FILES (newline-separated,
relative to the project directory). Only files under the zh/ output tree are touched, so the
Chinese labels are static HTML: correct with JavaScript off and in crawler snapshots.
The script never fails when there are no zh files (partial renders, EN-only builds).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

# Navbar menu text (Quarto wraps it in <span class="menu-text">...</span>).
NAV_LABELS = {
    "Research": "研究",
    "Data &amp; Code": "数据与代码",
    "Data & Code": "数据与代码",
    "CV": "简历",
    "Blog": "博客",
    "Software": "软件",
    "Photography": "摄影",
    "中文": "English",
}
# Footer text: the Privacy link label, the "Built with Quarto" phrase and the provenance sentence.
# The provenance sentence is drafted by the builder for owner review (O7); pandoc smartens the
# apostrophe in "author's", so the pattern accepts both ' and ’.
FOOTER_LABELS = {
    "Privacy": "隐私",
    "Photography (Pexels)": "摄影作品（Pexels）",
    "© 2026 Mingyang Liu": "© 2026 刘明杨",
    "Built with Quarto": "使用 Quarto 构建",
    "Exhibit data are generated from the author's research materials; see each figure's provenance line.":
        "展示数据由作者的研究资料生成；出处见各图的来源说明。",
    "Campus photographs courtesy of the University of Michigan, Columbia University and Imperial College London.":
        "校园照片由密歇根大学、哥伦比亚大学和帝国理工学院提供。",
}
FOOTER_PATTERNS = [
    (re.compile(re.escape(en).replace("'", "['’]")), zh)
    for en, zh in FOOTER_LABELS.items() if en not in ("Privacy", "Photography (Pexels)")
]


# Research dropdown (spec-nav.md). Keys are hrefs relative to the site root as Quarto writes them
# minus the ./ or ../ prefix; values give the Chinese href and the Chinese inner HTML of
# <span class="dropdown-text">…</span>. Keep the EN HTML in _quarto.yml and this table in step.
def _rq(n: str, q: str, do: str, jmp: bool = False) -> str:
    pill = ' <span class="jmp">求职论文</span>' if jmp else ""
    cls = "rq rq-jmp" if jmp else "rq"
    return (f'<span class="{cls}"><span class="n">{n}</span> <span class="q">{q}{pill}</span> '
            f'<span class="do">{do}</span></span>')


MENU_ITEMS = {
    "research/geometric-framework.html#gf-example": (
        "/zh/research/geometric-framework.html#gf-example",
        _rq("1", "用哪把尺子？", "拖动重叠度：普通尺子下两块合计声称解释 190%")),
    "research/characteristic-space-metrics.html#a-simple-example": (
        "/zh/research/characteristic-space-metrics.html#a-simple-example",
        _rq("2", "尺子决定了什么，又有多可靠？", "拖动重叠度：拆分在变，拟合始终不变")),
    "research/interpreting-pricing-errors.html#a-simple-example": (
        "/zh/research/interpreting-pricing-errors.html#a-simple-example",
        _rq("3", "更小的阿尔法意味着什么？", "交叉搭配两个模型的估计与因子：阿尔法从 117 个基点降到 75 个基点")),
    "research/characteristic-geometry.html#a-simple-example": (
        "/zh/research/characteristic-geometry.html#a-simple-example",
        _rq("4", "预测相同，组合为何不同？", "只换尺子的单位：预测不变，股票 1 的占比在 20%–54% 之间摆动")),
    "research/characteristic-libraries.html#example": (
        "/zh/research/characteristic-libraries.html#example",
        _rq("5", "信息相同，持仓为何不同？", "改写特征库，不加信息：目标持仓相差平均多空头寸总规模的 19%–28%", jmp=True)),
    "research/index.html": ("/zh/research/index.html", "全部研究"),
}
MENU_HEADERS = {"Five questions, each with a live example": "五个问题，每个都有一个可以动手试的例子"}

ITEM = re.compile(
    r'(<a class="dropdown-item" href=")([^"]*)("[^>]*>\s*<span class="dropdown-text">)(.*?)(</span>\s*</a>)',
    re.S)
HEADER = re.compile(r'(<li class="dropdown-header">)\s*(.*?)\s*(</li>)', re.S)


def rewrite_menu(html: str) -> str:
    """zh pages only: Chinese text and /zh/ hrefs for the Research dropdown."""
    def item(m: re.Match) -> str:
        key = re.sub(r"^(?:\.\./|\./)+", "", m.group(2))
        if key not in MENU_ITEMS:
            return m.group(0)
        href, text = MENU_ITEMS[key]
        return f"{m.group(1)}{href}{m.group(3)}{text}{m.group(5)}"
    html = ITEM.sub(item, html)
    html = HEADER.sub(lambda m: f"{m.group(1)}{MENU_HEADERS.get(m.group(2), m.group(2))}{m.group(3)}", html)
    return html


def project_dir() -> Path:
    env = os.environ.get("QUARTO_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    env = os.environ.get("QUARTO_PROJECT_OUTPUT_DIR")
    if env:
        p = Path(env)
        return p if p.is_absolute() else project_dir() / p
    return project_dir() / "_site"


def output_files() -> list[Path]:
    raw = os.environ.get("QUARTO_PROJECT_OUTPUT_FILES", "")
    base = project_dir()
    files = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        p = Path(line)
        if not p.is_absolute():
            p = base / p
        files.append(p)
    return files


def is_zh_output(p: Path, out: Path | None = None) -> bool:
    """True for an .html file inside <output dir>/zh/, judged relative to the output dir
    (an absolute checkout path that itself contains a `zh` directory must not match)."""
    if p.suffix.lower() != ".html" or p.name.startswith("._"):
        return False
    out = (out or output_dir()).resolve()
    try:
        rel = p.resolve().relative_to(out)
    except ValueError:
        return False
    return len(rel.parts) > 1 and rel.parts[0] == "zh"


def rewrite(html: str) -> str:
    for en, zh in NAV_LABELS.items():
        html = re.sub(
            r'(<span class="menu-text">)\s*' + re.escape(en) + r'\s*(</span>)',
            lambda m, zh=zh: f"{m.group(1)}{zh}{m.group(2)}",
            html,
        )
    html = rewrite_menu(html)
    # Navbar brand (the site name): on zh pages it leads to the Chinese home, like every other nav item.
    html = re.sub(r'(<a class="navbar-brand[^"]*" href=")(?:\.\./|\./)*index\.html(")', r'\1/zh/\2', html)
    # Top-level Data & Code item: on zh pages open the Chinese page.
    html = re.sub(r'(<a class="nav-link[^"]*" href=")(?:\.\./|\./)*data-code\.html(")', r'\1/zh/data-code.html\2', html)
    # Top-level Blog and CV items: the Chinese blog and the Chinese CV are public, so zh pages open them.
    html = re.sub(r'(<a class="nav-link[^"]*" href=")(?:\.\./|\./)*blog/(?:index\.html)?(")', r'\1/zh/blog/index.html\2', html)
    html = re.sub(r'(<a class="nav-link[^"]*" href=")(?:\.\./|\./)*cv\.html(")', r'\1/zh/cv.html\2', html)
    # Footer: <a href="...">Privacy</a> inside the nav-footer, and the plain phrases.
    def footer_sub(m: re.Match) -> str:
        block = m.group(0)
        block = re.sub(r"(>)\s*Privacy\s*(</a>)", lambda mm: f"{mm.group(1)}{FOOTER_LABELS['Privacy']}{mm.group(2)}", block)
        block = re.sub(r"(>)\s*Photography \(Pexels\)\s*(</a>)", lambda mm: f"{mm.group(1)}{FOOTER_LABELS['Photography (Pexels)']}{mm.group(2)}", block)
        # The footer's Privacy link points at the English page; on zh pages send it to the Chinese one.
        block = re.sub(r'href="(?:\.\./)*privacy\.html"', 'href="/zh/privacy.html"', block)
        for pattern, zh in FOOTER_PATTERNS:
            block = pattern.sub(zh, block)
        return block
    html = re.sub(r"<footer\b.*?</footer>", footer_sub, html, flags=re.S)
    # Licence appendix: Quarto's zh label keeps ASCII parentheses around "查看许可协议".
    html = html.replace(">(查看许可协议)</a>", ">（查看许可协议）</a>")
    return html


ALT = re.compile(r'<link rel="alternate" hreflang="(en|zh-Hans)" href="([^"]+)"\s*/?>')
TOGGLE = re.compile(r'<a class="nav-link([^"]*)" href="[^"]*"(\s*[^>]*)>(\s*<span class="menu-text">(?:中文|English)</span>)')


def set_toggle(html: str) -> str:
    """Point the navbar language toggle at this page's counterpart in the static HTML.

    The counterpart comes from the page's own hreflang alternates (written by filters/hreflang.lua),
    so the toggle works without JavaScript and for crawlers; assets/js/lang-toggle.js still runs as
    a fallback. Pages without alternates keep Quarto's /zh/ link."""
    alts = dict(ALT.findall(html))
    if "en" not in alts or "zh-Hans" not in alts:
        return html
    m = re.search(r'<html[^>]*\blang="([^"]+)"', html)
    is_zh = bool(m and m.group(1).lower().startswith("zh"))
    target = alts["en"] if is_zh else alts["zh-Hans"]
    target = re.sub(r"^https?://[^/]+", "", target) or "/"

    def sub(mm: re.Match) -> str:
        classes = mm.group(1)
        if "lang-toggle" not in classes:
            classes += " lang-toggle"
        return f'<a class="nav-link{classes}" href="{target}"{mm.group(2)}>{mm.group(3)}'
    return TOGGLE.sub(sub, html, count=1)


NAV_LINK = re.compile(r'<a class="nav-link([^"]*)" href="([^"]*)"([^>]*)>')


def _fold(path: str) -> str:
    """/x/index.html -> /x/ and /x/y.html -> /x/y (GitHub Pages serves both forms)."""
    path = re.sub(r"index\.html$", "", path)
    return re.sub(r"\.html$", "", path)


def mark_active(html: str, page: str) -> str:
    """Highlight the top-level navbar item for this page (class active + aria-current).

    Quarto marks the current item at render time against the EN hrefs, so on zh pages the items
    rewritten above (数据与代码, 博客, 简历) lose it, and no blog post highlights Blog. `page` is the
    page's site path (e.g. /zh/blog/index.html). An item whose href is this page gets
    aria-current="page"; a section index (…/) other than the two home pages also covers the pages
    below it (aria-current="true"). The Research dropdown is left to assets/js/nav-active.js, and
    the language toggle is never marked."""
    here = _fold(page)

    def sub(m: re.Match) -> str:
        cls, href, rest = m.groups()
        words = cls.split()
        if "active" in words or "dropdown-toggle" in words or "lang-toggle" in words:
            return m.group(0)
        if not href or href.startswith("#") or re.match(r"[a-z][a-z0-9+.-]*:", href):
            return m.group(0)
        target = _fold(urljoin(page, href).split("#")[0].split("?")[0])
        if target == here:
            current = "page"
        elif target.endswith("/") and target not in ("/", "/zh/") and here.startswith(target):
            current = "true"
        else:
            return m.group(0)
        if "aria-current" not in rest:
            rest += f' aria-current="{current}"'
        return f'<a class="nav-link{cls} active" href="{href}"{rest}>'
    return NAV_LINK.sub(sub, html)


def site_path(p: Path, out: Path | None = None) -> str | None:
    out = (out or output_dir()).resolve()
    try:
        return "/" + p.resolve().relative_to(out).as_posix()
    except ValueError:
        return None


def main() -> int:
    targets = [p for p in output_files() if p.suffix.lower() == ".html" and not p.name.startswith("._")]
    changed = 0
    for p in targets:
        if not p.exists():
            continue
        try:
            html = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            print(f"zh_labels: WARNING skipped {p} (not UTF-8: {exc})", file=sys.stderr)
            continue
        new = rewrite(html) if is_zh_output(p) else html
        new = set_toggle(new)
        page = site_path(p)
        if page:
            new = mark_active(new, page)
        if new != html:
            p.write_text(new, encoding="utf-8")
            changed += 1
    print(f"zh_labels: {len(targets)} page(s) scanned, {changed} rewritten", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
