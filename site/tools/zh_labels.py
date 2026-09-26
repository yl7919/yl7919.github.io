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
# Footer text: the Privacy link label and the "Built with Quarto" phrase.
FOOTER_LABELS = {
    "Privacy": "隐私",
    "Built with Quarto": "使用 Quarto 构建",
}


def project_dir() -> Path:
    env = os.environ.get("QUARTO_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


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


def is_zh_output(p: Path) -> bool:
    if p.suffix.lower() != ".html" or p.name.startswith("._"):
        return False
    parts = p.parts
    return "zh" in parts and parts.index("zh") < len(parts) - 1 and parts[parts.index("zh") - 1] == "_site"


def rewrite(html: str) -> str:
    for en, zh in NAV_LABELS.items():
        html = re.sub(
            r'(<span class="menu-text">)\s*' + re.escape(en) + r'\s*(</span>)',
            lambda m, zh=zh: f"{m.group(1)}{zh}{m.group(2)}",
            html,
        )
    # Footer: <a href="...">Privacy</a> inside the nav-footer, and the plain phrase.
    def footer_sub(m: re.Match) -> str:
        block = m.group(0)
        block = re.sub(r"(>)\s*Privacy\s*(</a>)", lambda mm: f"{mm.group(1)}{FOOTER_LABELS['Privacy']}{mm.group(2)}", block)
        block = block.replace("Built with Quarto", FOOTER_LABELS["Built with Quarto"])
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
        except UnicodeDecodeError:
            continue
        new = rewrite(html)
        if new != html:
            p.write_text(new, encoding="utf-8")
            changed += 1
    print(f"zh_labels: {len(targets)} zh page(s) scanned, {changed} rewritten", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
