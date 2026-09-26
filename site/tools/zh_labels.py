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
        for pattern, zh in FOOTER_PATTERNS:
            block = pattern.sub(zh, block)
        return block
    html = re.sub(r"<footer\b.*?</footer>", footer_sub, html, flags=re.S)
    return html


def main() -> int:
    targets = [p for p in output_files() if is_zh_output(p)]
    changed = 0
    for p in targets:
        if not p.exists():
            continue
        try:
            html = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            print(f"zh_labels: WARNING skipped {p} (not UTF-8: {exc})", file=sys.stderr)
            continue
        new = rewrite(html)
        if new != html:
            p.write_text(new, encoding="utf-8")
            changed += 1
    print(f"zh_labels: {len(targets)} zh page(s) scanned, {changed} rewritten", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
