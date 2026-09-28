#!/usr/bin/env python3
"""Site checks over the rendered _site and the .qmd sources. Exit 1 on any failure.

Run after `quarto render` (from the repo root: `python site/tools/check_links.py`).

Link check (always):
- internal references (a/href, img/src, srcset, link/href, script/src, source/src) must resolve inside _site.

Rules (a)-(k) from the spec ("Data pipeline and CI changes"):
(a) DOWNLOAD      every `downloads:` href in a page's front matter resolves in _site. `{{< var k >}}` is
                  expanded from _variables.yml; entries whose href is then empty or `?var:` are skipped,
                  because filters/paperhead.lua drops them; fragment-only (`#...`), mailto: and external
                  URLs are skipped; text-only entries ({text: ...}) have no href.
(b) GALLERY       every page whose source contains `{{< gallery` sets `lightbox:` with `match: auto`.
(c) TRANSLATION   every `translation:` target exists in _site.
(d) INCLUDE-PATH  no .qmd under site/ contains `../data` or `{{< include ../`.
(e) CITY-BAND     no element with class `city-band` outside _site/photography/** and _site/zh/photography/**.
(f) DFIGURE       every `.dfigure` contains a `.dfigure-title` and a `.figcaption`.
(g) DUPLICATE-CELL no OJS cell name is defined twice on one page (spec D22). Quarto embeds every page's OJS
                  source, includes already expanded, as base64 JSON in <script type="ojs-module-contents">;
                  the runtime raises "<name> is defined more than once" for duplicates, so the build fails first.
(h) BYLINE        for every research page (site/research/*.qmd, not `_`-prefixed), `pdftotext -l 1` of each
                  served download whose label names a Paper or Slides and whose href is a .pdf contains
                  every `author[].name`, and `byline_ok:` is present in the front matter.
(i) APPLEDOUBLE   no `._*` file in _site, and no page references a `._*` path.
(j) PROVENANCE    every `.dfigure .figcaption` contains a `.provenance` span naming a manuscript or release.
(k) IMG-ALT       every <img> in _site has an `alt` attribute (an empty alt is allowed for decorative images).

Deviations from the spec's wording, where the rule cannot be checked literally:
- (h) `byline_ok:` is required only on research pages that serve at least one Paper/Slides PDF: a page
  with no PDF (the thesis page, the research index) has no printed byline to confirm. Author names are
  matched after collapsing whitespace, so a name broken across lines by pdftotext still matches;
  footnote marks after a name (e.g. "Mingyang Liu*") do not matter. When pdftotext is not installed the
  rule fails (it never silently passes).
- (i) On macOS, writing _site to a non-native volume (the project lives on exFAT) makes the OS create an
  AppleDouble companion `._name` beside every file it writes. Those are tolerated only when running on
  macOS, when the file starts with the AppleDouble magic 00 05 16 07 and its sibling `name` exists;
  they are counted and reported, never published (CI renders from a git checkout, and `._*` is
  gitignored, so on Linux every `._*` file fails). Any other `._*` file, and any reference to a
  `._*` path from a page, fails everywhere.
- (j) "naming a manuscript or release" is checked as: the provenance text matches
  release|manuscript|working paper|thesis (case-insensitive).
  Changed 2026-09-28 (five-paper site): the rule assumed English captions of release-based exhibits only.
  It now also accepts "paper", "preprint" and "illustrative" (toy figures computed in the browser from a
  paper's formulas, which have no data release), their Chinese equivalents on zh pages
  (论文, 预印本, 发布包, 示意, 示例), and any caption naming one of the five paper titles verbatim.
- (f)/(j)/(k) inspect the static HTML; elements that OJS cells create at run time (for example the
  failed-load notice) are not visible to this check.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - reported at run time
    yaml = None

PROJECT = Path(__file__).resolve().parents[1]
SITE = PROJECT / "_site"
ATTRS = {("a", "href"), ("img", "src"), ("link", "href"), ("script", "src"), ("source", "src")}
OJS_MODULE = re.compile(r'<script type="ojs-module-contents">\s*(.*?)\s*</script>', re.S)
# A top-level OJS definition starts at column 0: `name = ...`, `viewof name = ...`, `mutable name = ...`.
# Statements inside a cell body (`{ ... }`) are indented in this project, so they do not match;
# `==`/`===`/`=>` are excluded by the lookahead.
OJS_DEF = re.compile(r"^(?:viewof\s+|mutable\s+)?([A-Za-z_$][\w$]*)\s*=(?![=>])", re.M)
VAR = re.compile(r"\{\{<\s*var\s+([\w.-]+)\s*>\}\}")
PAPER_OR_SLIDES = re.compile(r"\b(paper|slides)\b", re.I)
PROVENANCE_NAMES = re.compile(
    r"release|manuscript|working paper|thesis|paper|preprint|illustrative"
    r"|论文|预印本|发布包|示意|示例"
    r"|Characteristic Libraries and Portfolio Decisions|Characteristic-Space Metrics"
    r"|Geometric Framework for Identification|Characteristic Geometry and Portfolio Choice"
    r"|Interpreting Estimated Pricing Errors",
    re.I,
)
APPLEDOUBLE_MAGIC = b"\x00\x05\x16\x07"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
        "track", "wbr"}
SKIP_DIRS = {"_site", ".quarto", "site_libs"}


# --------------------------------------------------------------------------------------------- links

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


def is_local(ref: str) -> bool:
    u = urlparse(ref)
    return not (u.scheme or ref.startswith("#") or ref.startswith("mailto:") or ref.startswith("//"))


def resolve(page: Path, ref: str, site: Path | None = None) -> Path | None:
    site = SITE if site is None else site
    if not is_local(ref):
        return None
    path = unquote(urlparse(ref).path)
    target = (site / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
    target = target.resolve()
    if site.resolve() not in target.parents and target != site.resolve():
        return site / "__escapes_site__" / path.lstrip("/")  # guaranteed missing -> reported as BROKEN
    if target.is_dir():
        target = target / "index.html"
    return target


# ------------------------------------------------------------------------------------- OJS, rule (g)

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


# ----------------------------------------------------------------------------- a small element tree

class Node:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag: str, attrs: dict[str, str | None]):
        self.tag, self.attrs, self.children, self.text = tag, attrs, [], []

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def iter(self):
        yield self
        for c in self.children:
            yield from c.iter()

    def find_class(self, cls: str) -> list["Node"]:
        """Descendants (not self) carrying class `cls`."""
        return [n for c in self.children for n in c.iter() if cls in n.classes]

    def all_text(self) -> str:
        return "".join(self.text) + "".join(c.all_text() for c in self.children)


class TreeBuilder(HTMLParser):
    """Tolerant tree builder: void elements never open; an end tag closes up to its nearest open match."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].text.append(data)


def parse(html: str) -> Node:
    b = TreeBuilder()
    b.feed(html)
    b.close()
    return b.root


def dfigure_problems(root: Node) -> list[str]:
    """Rules (f) and (j) for one page -> list of 'RULE message'."""
    out = []
    for i, fig in enumerate(n for n in root.iter() if "dfigure" in n.classes):
        name = fig.attrs.get("id") or f"#{i + 1}"
        if not fig.find_class("dfigure-title"):
            out.append(f"DFIGURE .dfigure {name} has no .dfigure-title")
        caps = fig.find_class("figcaption")
        if not caps:
            out.append(f"DFIGURE .dfigure {name} has no .figcaption")
        for j, cap in enumerate(caps, 1):
            spans = [s for s in cap.find_class("provenance") if s.tag == "span"]
            if not spans:
                out.append(f"PROVENANCE .dfigure {name} .figcaption {j} has no span.provenance")
            elif not any(PROVENANCE_NAMES.search(s.all_text()) for s in spans):
                out.append(f"PROVENANCE .dfigure {name} .figcaption {j} provenance names no manuscript or release")
    return out


def city_band_count(root: Node) -> int:
    return sum(1 for n in root.iter() if "city-band" in n.classes)


def imgs_without_alt(root: Node) -> list[str]:
    return [n.attrs.get("src") or "(no src)" for n in root.iter() if n.tag == "img" and "alt" not in n.attrs]


def city_band_allowed(rel: Path) -> bool:
    parts = rel.parts
    return parts[:1] == ("photography",) or parts[:2] == ("zh", "photography")


# ------------------------------------------------------------------------------ sources, front matter

def source_files(project: Path, pattern: str = "*.qmd") -> list[Path]:
    out = []
    for p in project.rglob(pattern):
        rel = p.relative_to(project)
        if p.name.startswith("._") or any(part in SKIP_DIRS for part in rel.parts):
            continue
        out.append(p)
    return sorted(out)


def load_variables(project: Path) -> dict:
    f = project / "_variables.yml"
    if yaml is None or not f.exists():
        return {}
    return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


def expand_vars(value: str, variables: dict) -> str:
    def sub(m):
        v = variables.get(m.group(1))
        return f"?var:{m.group(1)}" if v is None else str(v)
    return VAR.sub(sub, value)


def front_matter(qmd: Path) -> dict:
    text = qmd.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = re.search(r"^---\s*$", text[3:], re.M)
    if end is None:
        return {}
    return yaml.safe_load(text[3:3 + end.start()]) or {}


def output_html(project: Path, qmd: Path, site: Path) -> Path:
    return site / qmd.relative_to(project).with_suffix(".html")


def is_page(project: Path, qmd: Path) -> bool:
    """A .qmd Quarto renders as a page (not an include or partial)."""
    rel = qmd.relative_to(project)
    return not any(part.startswith("_") for part in rel.parts)


def usable_href(href: str) -> bool:
    return href != "" and not href.startswith("?var:")


def download_entries(meta: dict, variables: dict) -> list[tuple[str, str]]:
    """(label, href) for every downloads: entry that the page actually links (paperhead.lua's rule)."""
    out = []
    for entry in meta.get("downloads") or []:
        if not isinstance(entry, dict) or entry.get("href") is None:
            continue
        href = expand_vars(str(entry["href"]).strip(), variables)
        if usable_href(href):
            out.append((str(entry.get("label") or ""), href))
    return out


def author_names(meta: dict) -> list[str]:
    authors = meta.get("author")
    if authors is None:
        return []
    if isinstance(authors, (str, dict)):
        authors = [authors]
    names = []
    for a in authors:
        name = a.get("name") if isinstance(a, dict) else a
        if isinstance(name, dict):  # {given, family}
            name = " ".join(str(name.get(k, "")) for k in ("given", "family")).strip()
        if name:
            names.append(str(name))
    return names


def squash(s: str) -> str:
    return " ".join(s.split())


def pdf_first_page_text(pdf: Path) -> str:
    exe = shutil.which("pdftotext")
    if exe is None:
        raise FileNotFoundError("pdftotext not found (install poppler)")
    res = subprocess.run([exe, "-l", "1", str(pdf), "-"], capture_output=True, text=True, check=True)
    return res.stdout


def byline_problems(rel: str, meta: dict, served: list[tuple[str, Path]], text_of=pdf_first_page_text) -> list[str]:
    """Rule (h) for one research page. `served` = [(label, local pdf path)] of Paper/Slides downloads."""
    out = []
    names = author_names(meta)
    if served and not names:
        out.append(f"BYLINE {rel}: serves {len(served)} Paper/Slides PDF(s) but has no author[].name")
    if served and "byline_ok" not in meta:
        out.append(f"BYLINE {rel}: serves Paper/Slides PDFs but has no byline_ok: (set it after reading each page-1 byline)")
    for label, pdf in served:
        try:
            text = squash(text_of(pdf))
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            out.append(f"BYLINE {rel}: cannot read page 1 of {pdf.name} ({exc})")
            continue
        for name in names:
            if squash(name) not in text:
                out.append(f"BYLINE {rel}: '{name}' not on page 1 of {pdf.name} ({label})")
    return out


def appledouble_problems(site: Path, platform: str = sys.platform) -> tuple[list[str], int]:
    """Rule (i) files -> (failures, tolerated macOS companions)."""
    failures, tolerated = [], 0
    for p in site.rglob("._*"):
        companion = p.with_name(p.name[2:])
        is_os_companion = False
        if platform == "darwin" and p.is_file() and companion.exists():
            with open(p, "rb") as fh:
                is_os_companion = fh.read(4) == APPLEDOUBLE_MAGIC
        if is_os_companion:
            tolerated += 1
        else:
            failures.append(f"APPLEDOUBLE {p.relative_to(site)} is in _site")
    return failures, tolerated


# ---------------------------------------------------------------------------------------------- main

def check(project: Path = PROJECT, site: Path | None = None) -> tuple[list[str], int, int]:
    """Run every check -> (failures, pages checked, tolerated AppleDouble companions)."""
    site = project / "_site" if site is None else site
    failures: list[str] = []
    pages = [p for p in site.rglob("*.html") if not p.name.startswith("._")]
    for page in pages:
        rel = page.relative_to(site)
        html = page.read_text(encoding="utf-8", errors="ignore")
        c = Collector()
        c.feed(html)
        for ref in c.refs:
            t = resolve(page, ref, site)
            if t is not None and not t.exists():
                failures.append(f"BROKEN {rel} -> {ref}")
            if is_local(ref) and any(part.startswith("._") for part in Path(unquote(urlparse(ref).path)).parts):
                failures.append(f"APPLEDOUBLE {rel} references {ref}")
        for name, n in sorted(duplicate_cells(html).items()):
            failures.append(f"DUPLICATE-CELL {rel} -> {name} defined {n} times")
        root = parse(html)
        failures += [f"{m.split(' ', 1)[0]} {rel}: {m.split(' ', 1)[1]}" for m in dfigure_problems(root)]
        if city_band_count(root) and not city_band_allowed(rel):
            failures.append(f"CITY-BAND {rel}: .city-band outside photography/")
        failures += [f"IMG-ALT {rel}: <img src={src}> has no alt attribute" for src in imgs_without_alt(root)]

    ad_failures, tolerated = appledouble_problems(site)
    failures += ad_failures

    if yaml is None:
        failures.append("SETUP pyyaml is not installed; rules (a), (b), (c), (h) need it (pip install pyyaml)")
        return failures, len(pages), tolerated
    variables = load_variables(project)
    for qmd in source_files(project):
        rel = qmd.relative_to(project).as_posix()
        text = qmd.read_text(encoding="utf-8")
        if "../data" in text or "{{< include ../" in text:
            failures.append(f"INCLUDE-PATH {rel}: contains '../data' or '{{{{< include ../'")
        if not is_page(project, qmd):
            continue
        try:
            meta = front_matter(qmd)
        except yaml.YAMLError as exc:
            failures.append(f"FRONT-MATTER {rel}: YAML does not parse ({exc.__class__.__name__})")
            continue
        out = output_html(project, qmd, site)
        if "{{< gallery" in text:
            lb = meta.get("lightbox")
            if not (isinstance(lb, dict) and lb.get("match") == "auto"):
                failures.append(f"GALLERY {rel}: uses {{{{< gallery >}}}} without lightbox: {{match: auto}}")
        tr = meta.get("translation")
        if tr:
            t = resolve(out, str(tr), site)
            if t is not None and not t.exists():
                failures.append(f"TRANSLATION {rel}: translation target {tr} is not in _site")
        served = []
        for label, href in download_entries(meta, variables):
            t = resolve(out, href, site)
            if t is None:
                continue
            if not t.exists():
                failures.append(f"DOWNLOAD {rel}: downloads href {href} does not resolve in _site")
            elif PAPER_OR_SLIDES.search(label) and t.suffix.lower() == ".pdf":
                served.append((label, t))
        if rel.startswith("research/"):
            failures += byline_problems(rel, meta, served)
    return failures, len(pages), tolerated


def main() -> int:
    if not SITE.exists():
        print(f"{SITE} missing; run `quarto render` first", file=sys.stderr)
        return 2
    failures, n_pages, tolerated = check()
    for f in failures:
        print(f)
    broken = sum(1 for f in failures if f.startswith("BROKEN "))
    print(f"checked {n_pages} pages, {broken} broken references, "
          f"{len(failures) - broken} rule (a)-(k) failures")
    if tolerated:
        print(f"note: {tolerated} macOS AppleDouble companions in _site tolerated (rule (i); not published)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
