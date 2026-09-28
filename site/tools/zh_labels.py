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

# Navbar menu text (Quarto wraps it in <span class="menu-text">...</span>).
NAV_LABELS = {
    "Research": "研究",
    "CV": "简历",
    "Software": "软件",
    "Photography": "摄影",
    "中文": "English",
}
# Footer text: the Privacy link label, the "Built with Quarto" phrase and the provenance sentence.
# The provenance sentence is drafted by the builder for owner review (O7); pandoc smartens the
# apostrophe in "author's", so the pattern accepts both ' and ’.
FOOTER_LABELS = {
    "Privacy": "隐私",
    "Built with Quarto": "使用 Quarto 构建",
    "Exhibit data are generated from the author's research materials; see each figure's provenance line.":
        "展示数据由作者的研究资料生成；出处见各图的来源说明。",
    "Campus photographs courtesy of the University of Michigan, Columbia University and Imperial College London.":
        "校园照片由密歇根大学、哥伦比亚大学和帝国理工学院提供。",
}
FOOTER_PATTERNS = [
    (re.compile(re.escape(en).replace("'", "['’]")), zh)
    for en, zh in FOOTER_LABELS.items() if en != "Privacy"
]


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
    # Footer: <a href="...">Privacy</a> inside the nav-footer, and the plain phrases.
    def footer_sub(m: re.Match) -> str:
        block = m.group(0)
        block = re.sub(r"(>)\s*Privacy\s*(</a>)", lambda mm: f"{mm.group(1)}{FOOTER_LABELS['Privacy']}{mm.group(2)}", block)
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
        if new != html:
            p.write_text(new, encoding="utf-8")
            changed += 1
    print(f"zh_labels: {len(targets)} page(s) scanned, {changed} rewritten", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
