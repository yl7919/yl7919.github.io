#!/usr/bin/env python3
"""Post-render: rewrite static navbar/footer labels in _site/zh/**/*.html, and mark the current navbar item.

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
    "Research Toolkit": "研究工具",   # the Toolkit menu
    "Data &amp; Code": "数据与代码",
    "Data & Code": "数据与代码",
    "CV": "简历",
    "Projects": "项目",
    "Advisory": "咨询",
    "Blog": "博客",          # kept while old pages may still carry the label
    "Software": "软件",
    "Photography": "摄影",
    "中文": "English",
}
# Footer text: the Privacy link label, the "Built with Quarto" phrase and the provenance sentence.
# Pandoc smartens the apostrophe in "author's", so the pattern accepts both ' and ’.
FOOTER_LABELS = {
    "Privacy": "隐私",
    "Independent advisory": "独立咨询",     # the Advisory page is linked from the footer
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
    for en, zh in FOOTER_LABELS.items() if en not in ("Privacy", "Independent advisory", "Photography (Pexels)")
]


# Research dropdown. Keys are hrefs relative to the site root as Quarto writes them
# minus the ./ or ../ prefix; values give the Chinese href and the Chinese inner HTML of
# <span class="dropdown-text">…</span>. Keep the EN HTML in _quarto.yml and this table in step.
# Owner, 2026-10-16: the menu mirrors the research page (papers, job market paper first; research in progress).
def _rp(q: str, do: str, jmp: bool = False) -> str:
    pill = ' <span class="jmp">求职论文</span>' if jmp else ""
    cls = "rq rq-paper rq-jmp" if jmp else "rq rq-paper"
    return (f'<span class="{cls}"><span class="q">{q}{pill}</span><span class="visually-hidden">：</span> '
            f'<span class="do">{do}</span></span>')


MENU_ITEMS = {
    # The job market paper: the 求职论文 pill and the rq-jmp accent rule, as on the EN item in _quarto.yml.
    "research/the-ruler-matters.html#example": (
        "/zh/research/the-ruler-matters.html#example",
        _rp("尺子很重要", "目标相同，持仓为何不同？用普通尺子对冲：46.10% 的头寸仍留在载荷上", jmp=True)),
    "research/geometric-framework.html#gf-example": (
        "/zh/research/geometric-framework.html#gf-example",
        _rp("识别问题的几何框架", "用哪把尺子？拖动重叠度：普通尺子下两块合计声称解释 190%")),
    "research/characteristic-space-metrics.html#a-simple-example": (
        "/zh/research/characteristic-space-metrics.html#a-simple-example",
        _rp("特征空间度量", "尺子决定了什么，又有多可靠？拖动重叠度：拆分在变，拟合始终不变")),
    "research/interpreting-pricing-errors.html#a-simple-example": (
        "/zh/research/interpreting-pricing-errors.html#a-simple-example",
        _rp("如何解读估计的定价误差", "更小的阿尔法意味着什么？交叉搭配两个模型的估计与因子：阿尔法从 117 个基点降到 75 个基点")),
    "research/same-forecasts-different-portfolios.html#a-simple-example": (
        "/zh/research/same-forecasts-different-portfolios.html#a-simple-example",
        _rp("预测相同，组合不同", "只换尺子的单位：预测不变，股票 1 的占比在 20%–54% 之间摆动")),
    "research/index.html#bond-premia": (
        "/zh/research/index.html#bond-premia",
        _rp("因子暴露还是截距？公司债券预期收益识别", "与 Paolo Zaffaroni 合著 · 撰写中")),
    "research/index.html#linear-forecasts": (
        "/zh/research/index.html#linear-forecasts",
        _rp("基于线性预测的投资组合构建", "与 Semyon Malamud 教授（EPFL）的合作研究")),
    "research/index.html": ("/zh/research/index.html", "全部研究"),
}
MENU_HEADERS = {"Papers, each with an interactive example": "论文：每篇都有一个可以动手试的例子",
                "Research in progress": "进行中的研究"}


# Research Toolkit dropdown: same mechanism as MENU_ITEMS, kept as its own table so that a tool's entry is added or
# removed together with its _quarto.yml item (pipeline/tests/test_zh_labels.py checks both directions). A visually
# hidden full-width colon separates the tool's name from its one-line description, so a screen reader does not run
# the two together (the EN menu uses ":" in the same place). demo=True gives the item under each tool that jumps to
# its "Interactive demonstration" section (owner request 2026-10-13): same spans, plus class rq-demo for its look.
def _tk(name: str, do: str, demo: bool = False) -> str:
    cls = "rq rq-tool rq-demo" if demo else "rq rq-tool"
    return (f'<span class="{cls}"><span class="q">{name}</span><span class="visually-hidden">：</span>'
            f'<span class="do">{do}</span></span>')


TOOLKIT_ITEMS = {
    "projects/return-state-diagnostics.html": (
        "/zh/projects/return-state-diagnostics.html",
        _tk("投资组合风险诊断", "收益序列在不同市场环境下的历史表现")),
    "projects/return-state-diagnostics.html#demo": (
        "/zh/projects/return-state-diagnostics.html#demo",
        _tk("交互演示", "打开交互演示", demo=True)),
    "projects/forecast-evaluation.html": (
        "/zh/projects/forecast-evaluation.html",
        _tk("宏观预测评估", "在可比样本窗口中比较预测模型")),
    "projects/forecast-evaluation.html#demo": (
        "/zh/projects/forecast-evaluation.html#demo",
        _tk("交互演示", "打开交互演示", demo=True)),
    "research-toolkit/index.html": ("/zh/research-toolkit/index.html", "工具概览"),
}


# Projects dropdown (owner request 2026-10-13): the three areas of the Projects page, each with the one-line lead of
# its section, and "All projects". Same span structure as the Toolkit items (class rq-area: name, hidden colon, one
# plain line); the keys carry the section fragments as Quarto writes them. pipeline/tests/test_zh_labels.py checks
# this table against _quarto.yml and against the section ids and leads of projects/index.qmd in both languages.
def _pj(name: str, do: str) -> str:
    return (f'<span class="rq rq-area"><span class="q">{name}</span><span class="visually-hidden">：</span>'
            f'<span class="do">{do}</span></span>')


PROJECTS_ITEMS = {
    "projects/index.html#machine-learning-and-portfolios": (
        "/zh/projects/index.html#machine-learning-and-portfolios",
        _pj("机器学习与投资组合", "因子模型预测、美国股票滚动回测与对照比较，并逐层追踪到持仓、风险与交易成本")),
    "projects/index.html#estimation-tools": (
        "/zh/projects/index.html#estimation-tools",
        _pj("估计工具", "别人可以重跑、可以审计的代码")),
    "projects/index.html#text-and-ai": (
        "/zh/projects/index.html#text-and-ai",
        _pj("研究中的人工智能", "一套让学生与 AI 编程助手在人工审核下协作研究的流程")),
    "projects/index.html": ("/zh/projects/index.html", "全部项目"),
}
PROJECTS_HEADERS = {"Three areas, each with its projects": "三个方向，各有若干项目"}

ITEM = re.compile(
    r'(<a class="dropdown-item" href=")([^"]*)("[^>]*>\s*<span class="dropdown-text">)(.*?)(</span>\s*</a>)',
    re.S)
HEADER = re.compile(r'(<li class="dropdown-header">)\s*(.*?)\s*(</li>)', re.S)


def menu_tables() -> list[dict[str, tuple[str, str]]]:
    """Every navbar menu table (EN href -> (ZH href, ZH inner HTML)); keys are disjoint across tables."""
    return [MENU_ITEMS, TOOLKIT_ITEMS, PROJECTS_ITEMS]


def rewrite_menu(html: str) -> str:
    """zh pages only: Chinese text and /zh/ hrefs for the navbar dropdowns (MENU_ITEMS, TOOLKIT_ITEMS,
    PROJECTS_ITEMS) and their header lines (MENU_HEADERS, PROJECTS_HEADERS)."""
    headers = {**MENU_HEADERS, **PROJECTS_HEADERS}

    def item(m: re.Match) -> str:
        key = re.sub(r"^(?:\.\./|\./)+", "", m.group(2))
        table = next((t for t in menu_tables() if key in t), None)
        if table is None:
            return m.group(0)
        href, text = table[key]
        return f"{m.group(1)}{href}{m.group(3)}{text}{m.group(5)}"
    html = ITEM.sub(item, html)
    html = HEADER.sub(lambda m: f"{m.group(1)}{headers.get(m.group(2), m.group(2))}{m.group(3)}", html)
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
    # Top-level Projects (formerly Blog) and CV items: the Chinese pages are public, so zh pages open them.
    html = re.sub(r'(<a class="nav-link[^"]*" href=")(?:\.\./|\./)*projects/(?:index\.html)?(")', r'\1/zh/projects/index.html\2', html)
    html = re.sub(r'(<a class="nav-link[^"]*" href=")(?:\.\./|\./)*blog/(?:index\.html)?(")', r'\1/zh/blog/index.html\2', html)
    html = re.sub(r'(<a class="nav-link[^"]*" href=")(?:\.\./|\./)*cv\.html(")', r'\1/zh/cv.html\2', html)
    # Top-level Advisory item (kept for pages that still carry it): zh pages open the Chinese advisory page.
    html = re.sub(r'(<a class="nav-link[^"]*" href=")(?:\.\./|\./)*advisory\.html(")', r'\1/zh/advisory.html\2', html)
    # Footer: <a href="...">Privacy</a> inside the nav-footer, and the plain phrases.
    def footer_sub(m: re.Match) -> str:
        block = m.group(0)
        block = re.sub(r"(>)\s*Privacy\s*(</a>)", lambda mm: f"{mm.group(1)}{FOOTER_LABELS['Privacy']}{mm.group(2)}", block)
        block = re.sub(r"(>)\s*Photography \(Pexels\)\s*(</a>)", lambda mm: f"{mm.group(1)}{FOOTER_LABELS['Photography (Pexels)']}{mm.group(2)}", block)
        # The footer's Independent advisory link (EN page) becomes 独立咨询 -> the Chinese advisory page.
        block = re.sub(r"(>)\s*Independent advisory\s*(</a>)", lambda mm: f"{mm.group(1)}{FOOTER_LABELS['Independent advisory']}{mm.group(2)}", block)
        block = re.sub(r'href="(?:\.\./|\./|/)*advisory\.html"', 'href="/zh/advisory.html"', block)
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


LANG_LINK = re.compile(r'<a class="nav-link([^"]*)" href="([^"]*)"([^>]*)>(\s*<span class="menu-text">(中文|English)</span>)')


def label_toggle(html: str) -> str:
    """Give the navbar language toggle lang and hreflang for its label and its target (中文 -> zh-Hans,
    English -> en). The visible endonym stays the accessible name (no aria-label), and a screen reader reads
    it in its own language. assets/js/lang-toggle.js sets the same attributes at run time."""
    def sub(m: re.Match) -> str:
        cls, href, rest, label = m.group(1), m.group(2), m.group(3), m.group(4)
        if re.search(r'\blang="', rest):
            return m.group(0)
        code = "zh-Hans" if m.group(5) == "中文" else "en"
        return f'<a class="nav-link{cls}" href="{href}"{rest} lang="{code}" hreflang="{code}">{label}'
    return LANG_LINK.sub(sub, html, count=1)


NAV_LINK = re.compile(r'<a class="nav-link([^"]*)" href="([^"]*)"([^>]*)>')


def _fold(path: str) -> str:
    """/x/index.html -> /x/ and /x/y.html -> /x/y (GitHub Pages serves both forms)."""
    path = re.sub(r"index\.html$", "", path)
    return re.sub(r"\.html$", "", path)


def menu_sections() -> dict[str, set[str]]:
    """Navbar menus that form a section of their own: toggle id -> folded site paths (EN and ZH) of the pages
    the menu lists (an item's #fragment names a part of a page, not a page, so it is dropped). Such a page belongs
    to that menu's section even when its URL sits under another section's index (a page under /projects/ that such
    a menu lists is not marked as Projects)."""
    sections: dict[str, set[str]] = {}
    sections["nav-menu-research-toolkit"] = {
        _fold(p.split("#")[0]) for href, (zh_href, _text) in TOOLKIT_ITEMS.items() for p in ("/" + href, zh_href)}
    return sections


# Navbar menus whose section is a URL prefix: toggle id -> folded site-path prefixes (EN and ZH). A page under one of
# them belongs to that menu unless a menu that lists pages (menu_sections) claims it first; a page whose navbar has no
# such toggle (an older render, a test fixture with a plain link) keeps the plain-link rule in mark_active.
PREFIX_SECTIONS = {"nav-menu-projects": ("/projects/", "/zh/projects/")}

DROPDOWN_ITEM = re.compile(r'<a class="dropdown-item([^"]*)" href="([^"]*)"([^>]*)>')


def mark_menu(html: str, toggle_id: str, page: str) -> str:
    """Mark a section menu as current: its toggle gets class active + aria-current="true", and the item that
    opens this page gets class active + aria-current="page" (assets/js/nav-active.js does the same at run time).
    An item whose href carries a #fragment opens a part of a page, never the page, so it is never aria-current."""
    here = _fold(page)

    def toggle(m: re.Match) -> str:
        cls, rest = m.groups()
        if "active" in cls.split():
            return m.group(0)
        if "aria-current" not in rest:
            rest += ' aria-current="true"'
        return f'<a class="nav-link{cls} active"{rest}>'

    def item(m: re.Match) -> str:
        cls, href, rest = m.groups()
        if "active" in cls.split() or "#" in href or _fold(urljoin(page, href).split("?")[0]) != here:
            return m.group(0)
        if "aria-current" not in rest:
            rest += ' aria-current="page"'
        return f'<a class="dropdown-item{cls} active" href="{href}"{rest}>'

    tid = re.escape(toggle_id)
    html = re.sub(r'<a class="nav-link([^"]*)"([^>]*\bid="' + tid + r'"[^>]*)>', toggle, html, count=1)
    return re.sub(r'<ul class="dropdown-menu"[^>]*\baria-labelledby="' + tid + r'"[^>]*>.*?</ul>',
                  lambda m: DROPDOWN_ITEM.sub(item, m.group(0)), html, count=1, flags=re.S)


def mark_active(html: str, page: str) -> str:
    """Highlight the top-level navbar item for this page (class active + aria-current).

    Quarto marks the current item at render time against the EN hrefs, so on zh pages the items
    rewritten above (项目, 数据与代码, 简历) lose it, and no project page highlights Projects. `page` is the
    page's site path (e.g. /zh/projects/index.html). An item whose href is this page gets
    aria-current="page"; a section index (…/) other than the two home pages also covers the pages
    below it (aria-current="true"), except a page that a section menu lists (menu_sections) or that sits
    under a section menu's URL prefix (PREFIX_SECTIONS, when its toggle is in the navbar): there the
    menu's toggle and item are marked instead (mark_menu). The Research dropdown is left to
    assets/js/nav-active.js, and the language toggle is never marked."""
    here = _fold(page)
    section = next((tid for tid, pages in menu_sections().items() if here in pages), None)
    if section is None:
        section = next((tid for tid, prefixes in PREFIX_SECTIONS.items()
                        if here.startswith(prefixes) and re.search(r'\bid="' + re.escape(tid) + '"', html)), None)

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
        elif section is None and target.endswith("/") and target not in ("/", "/zh/") and here.startswith(target):
            current = "true"
        else:
            return m.group(0)
        if "aria-current" not in rest:
            rest += f' aria-current="{current}"'
        return f'<a class="nav-link{cls} active" href="{href}"{rest}>'
    html = NAV_LINK.sub(sub, html)
    return mark_menu(html, section, page) if section else html


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
        new = label_toggle(set_toggle(new))
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
