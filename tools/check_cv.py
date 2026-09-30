#!/usr/bin/env python3
"""CV checks over site/cv.qmd and the held _held/site/zh/cv.qmd (spec Part B 4.2). Exit 1 on any failure.

    tools/check_cv.py                       all ten items (precommit.sh step 7/7)
    tools/check_cv.py --en-only             items 1, 4, 5, 6, 8, 9 and the EN halves of 2, 7 and 10; item 3 skipped [ME-16]
    tools/check_cv.py --rendered DIR        rendered site for the aria-label half of item 2 (default site/_site)
    tools/check_cv.py --rendered-zh FILE    rendered held ZH page (print_cv.sh scratch) for the same check
    tools/check_cv.py --no-network          skip the curl probes of item 8 (printed as SKIPPED, never silent)
    tools/check_cv.py --no-sync             skip item 3 only (for a review print before the ZH commit exists)
    tools/check_cv.py --no-git              accepted for compatibility; item 5 always checks that held files are untracked

Items (numbering as in the spec):
 1. Word budget (EN): each `.cv-sum` in site/cv.qmd is at most 55 words after `[label](url){attrs}` -> label
    and stripping `*`; hyphenated compounds count as one word.
 2. Link completeness: every non-thesis `.cv-paper` has a `.cv-ptitle` link to /research/<slug>.html (ZH:
    /zh/research/) and a `.cv-plinks` row with an /assets/pdfs/*.pdf link; the two SSRN entries link
    https://doi.org/10.2139/ssrn.<id>; no `.cv-plinks` contains a /research/ link; every link in a `.cv-plinks`
    row carries a non-empty aria-label (checked in the source, and in the rendered HTML when it exists);
    five paper blocks and one thesis block per file.
 3. Sync EN/ZH: ordered DOIs, the set of /assets/pdfs/*.pdf hrefs, the ordered paper-page slugs, the status
    months per paper block and the "Updated"/更新于 month are identical; every hedge pair of 2.5.8 is present;
    the ZH `translated-from` sha is a commit, an ancestor-or-equal of HEAD and the last commit that touched
    site/cv.qmd (which must itself be committed).
 4. Banned strings in the two CV files and the two home `.bio` blocks; no private-repository reference anywhere
    under site/.
 5. Withheld Service strings (since 2026-09-30 only the Nankai–Columbia exchange and the Michigan China Forum
    items; the Imperial Student Investment Fund chair block is public again) absent from public files
    (site/**), present in both held service files, and neither held file tracked by git (private material stays local).
 6. Private data absent from site/** and from the held ZH CV (its 证件姓名 line is allowed).
 7. Numbers: every numeric token in each `.cv-sum` and in the doctoral-research bullets is in the whitelist
    derived from 2.5.7 and 2.6 (Part 0 D2: 36, 12,813, 1964-2014); the thesis block has no numeric token.
 8. External URLs answer (not 404/410/connection error); SIF reachability gate for the SIF link.
 9. site/assets/pdfs/ hygiene: no *.tmp*, *.failed*, print.pdf; every file is a served PDF or referenced from a
    .qmd under site/; `._*` AppleDouble companions are ignored as check_links rule (i) tolerates them.
10. Structure (2026-09-30, research-first job-market order): the `##` sections appear exactly in SECTIONS order
    (References last); in Research, the first paper block is the job market paper, wrapped in `.cv-jmp` with a
    `.cv-tag` label, followed by the Working Papers and PhD Thesis subsections; Service carries the SIF chair
    block with its SIF, QRT and LSEG links; References lists the three referees (REFEREES) in order, each with
    a mailto: e-mail and a profile link, and no "on request" line; the Michigan degree reads as a double major
    (and never "dual degree"/"双学位") in the CV and in the home `.bio` block.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
SITE = WEB / "site"
EN_CV = SITE / "cv.qmd"
ZH_CV = WEB / "_held/site/zh/cv.qmd"
EN_HOME = SITE / "index.qmd"
ZH_HOME = SITE / "zh/index.qmd"
HELD_SERVICE = [WEB / "_held/site/cv-service.qmd", WEB / "_held/site/zh/cv-service.qmd"]
PDF_DIR = SITE / "assets/pdfs"

SLUGS = ["characteristic-libraries", "characteristic-space-metrics", "geometric-framework",
         "characteristic-geometry", "interpreting-pricing-errors"]
SSRN_SLUGS = {"characteristic-space-metrics", "geometric-framework"}
PAPER_PDFS = ["Characteristic_Libraries_and_Portfolio_Decisions_SSRN_v2.pdf", "Characteristic_Space_Metrics_Main.pdf",
              "Characteristic_Space_Metrics_Online_Supplement.pdf", "Geometric_Framework_SSRN_7013178.pdf",
              "Characteristic_Geometry_and_Portfolio_Choice_Slides.pdf", "Interpreting_Estimated_Pricing_Errors.pdf"]
SERVED_PDFS = set(PAPER_PDFS) | {"Characteristic_Space_Metrics_Slides.pdf", "Mingyang_Liu_CV.pdf"}

# 2.5.8 hedge pairs (EN string in the EN file, ZH string in the ZH file).
HEDGES = [
    ("nearly identical forecasts", "几乎相同"),
    ("gross performance", "未计交易成本"),
    ("post-2007 mean-return gain is imprecisely estimated", "2007 年 10 月以后的平均收益增益估计并不精确"),
    ("identical fit", "拟合完全相同"),
    ("small, imprecise predictive effects under the evaluated procedures", "在所评估的方法下对预测的影响小，估计也不精确"),
    ("exploratory evidence", "属探索性证据"),
    ("similar fit can hide different pricing directions", "拟合相近的模型可隐含不同的已识别定价方向"),
]

# 2.5.7 / 2.6 number whitelist, per block and language. The ZH JMP summary writes 19%–28% as two tokens.
NUMBERS = {
    "characteristic-libraries": {"en": {"153", "19–28%", "39"}, "zh": {"153", "19%", "28%", "39"}},
    "characteristic-space-metrics": {"en": set(), "zh": set()},
    "geometric-framework": {"en": set(), "zh": set()},
    "characteristic-geometry": {"en": {"132", "0.01%", "2007"}, "zh": {"132", "0.01%", "2007", "10"}},
    "interpreting-pricing-errors": {"en": {"153"}, "zh": {"153"}},
    "thesis": {"en": set(), "zh": set()},
    "doctoral": {"en": {"120", "1973–2024", "39", "153", "1962–2025", "36", "12,813", "1964–2014"},
                 "zh": {"120", "1973–2024", "39", "153", "1962–2025", "36", "12,813", "1964–2014"}},
}
NUM_TOKEN = re.compile(r"\d[\d,.–]*%?")

# 4.2.8: section 0 table URLs that the CV or bio carries, plus the four named extras.
EXTERNAL_URLS = [
    "https://www.imperial.ac.uk/quantitative-finance-centre/",
    "https://profiles.imperial.ac.uk/r.kosowski",
    "https://profiles.imperial.ac.uk/p.zaffaroni",
    "https://profiles.imperial.ac.uk/p.dellacorte",
    "https://ibconnect.imperial.ac.uk/sif/home/",
    "https://jkpfactors.com/",
    "https://www.lseg.com/en",
    "https://mingyangliu.org",
    "https://kpmg.com/uk/en.html",
    "https://www.columbia.edu/~jb3064/",
    "https://doi.org/10.2139/ssrn.7013178",
    "https://doi.org/10.2139/ssrn.7445120",
    "https://www.qube-rt.com/",
]

# Item 10: section order (EN headings; ZH headings without their [English]{.h2-en} tag), research subsections,
# referees (profile slug, e-mail) in order, and the double-major wording.
SECTIONS = {
    "en": ["Research Fields", "Education", "Research", "Positions", "Research Experience", "Teaching",
           "Scholarships and Honours", "Service", "Skills and Languages", "References"],
    "zh": ["研究方向", "教育背景", "学术论文", "工作经历", "科研经历", "教学经历", "奖学金与荣誉", "校内外服务",
           "专业技能与语言", "推荐人"],
}
SUBSECTIONS = {"en": ["Working Papers", "PhD Thesis"], "zh": ["工作论文（Working Papers）", "博士学位论文（PhD Thesis）"]}
JMP_TAG = {"en": "Job Market Paper", "zh": "求职论文"}
REFEREES = [("p.zaffaroni", "p.zaffaroni@imperial.ac.uk"), ("p.dellacorte", "p.dellacorte@imperial.ac.uk"),
            ("r.kosowski", "r.kosowski@imperial.ac.uk")]
SERVICE_LINKS = ["https://ibconnect.imperial.ac.uk/sif/home/", "https://www.qube-rt.com/", "https://www.lseg.com/en"]
DOUBLE_MAJOR = {"en": "double major in Economics and Mathematics", "zh": "经济学、数学双专业"}
NOT_DUAL = re.compile(r"dual degree|double degree|双学位", re.I)
SIF_URL = "https://ibconnect.imperial.ac.uk/sif/home/"
SIF_TEXT = {"en": "Imperial Student Investment Fund", "zh": "帝国理工学院学生投资基金"}
LOGIN_TOKENS = ("login", "sso", "shibboleth", "microsoftonline")

SKIP_DIRS = {"_site", ".quarto", "site_libs", "__pycache__"}
TEXT_EXT = {".qmd", ".md", ".yml", ".yaml", ".html", ".js", ".scss", ".css", ".lua", ".py", ".json", ".txt", ".toml"}


# ----------------------------------------------------------------------------------------------- helpers
def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def spans(text: str, cls: str) -> list[str]:
    """Inner text of every Pandoc bracketed span `[...]{.cls}` (bracket-aware, so nested links are fine)."""
    out = []
    for m in re.finditer(r"\]\{\." + re.escape(cls) + r"\}", text):
        end = m.start()
        depth, i = 1, end - 1
        while i >= 0 and depth:
            if text[i] == "]":
                depth += 1
            elif text[i] == "[":
                depth -= 1
            i -= 1
        if depth == 0:
            out.append(text[i + 2:end])
    return out


def paper_blocks(text: str) -> list[str]:
    return re.findall(r"^::: \{\.cv-paper\}\n(.*?)\n:::$", text, re.M | re.S)


def doctoral_block(text: str, marker: str) -> str | None:
    for m in re.finditer(r"^::: \{\.cv-what\}\n(.*?)\n:::$", text, re.M | re.S):
        if marker in m.group(1):
            return m.group(1)
    return None


def bio_block(text: str) -> str:
    m = re.search(r"^::: \{\.bio\}\n(.*?)\n:::$", text, re.M | re.S)
    return m.group(1) if m else ""


def plain(md: str) -> str:
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)(\{[^}]*\})?", r"\1", md)
    return md.replace("*", "").replace("`", "")


def words(md: str) -> int:
    return len(plain(md).split())


def numeric_tokens(md: str) -> list[str]:
    toks = []
    for t in NUM_TOKEN.findall(plain(md)):
        t = t.rstrip("-–,.;)")
        if t:
            toks.append(t)
    return toks


def slug_of(block: str, zh: bool) -> str | None:
    pre = "/zh/research/" if zh else "/research/"
    for title in spans(block, "cv-ptitle"):
        m = re.search(re.escape(pre) + r"([a-z-]+)\.html", title)
        if m:
            return m.group(1)
    return None


def site_text_files() -> list[Path]:
    out = []
    for p in SITE.rglob("*"):
        if not p.is_file() or p.name.startswith("._") or p.suffix not in TEXT_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(SITE).parts):
            continue
        out.append(p)
    return out


def git(*args: str) -> tuple[int, str]:
    res = subprocess.run(["git", "-C", str(WEB), *args], capture_output=True, text=True)
    return res.returncode, res.stdout.strip()


class PlinkAnchors(HTMLParser):
    """Anchors inside <span class="cv-plinks">: (text, aria-label or None)."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.anchors: list[tuple[str, str | None]] = []
        self._cur: list[str] | None = None
        self._label: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "span" and "cv-plinks" in (a.get("class") or "").split():
            self.depth = 1
        elif self.depth:
            self.depth += 1
            if tag == "a":
                self._cur, self._label = [], a.get("aria-label")

    def handle_endtag(self, tag):
        if self.depth:
            if tag == "a" and self._cur is not None:
                self.anchors.append(("".join(self._cur).strip(), self._label))
                self._cur = None
            self.depth -= 1

    def handle_data(self, data):
        if self._cur is not None:
            self._cur.append(data)


# ------------------------------------------------------------------------------------------------- items
class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def fail(self, item: int, msg: str) -> None:
        self.failures.append(f"item {item}: {msg}")
        print(f"  FAIL item {item}: {msg}")

    def ok(self, item: int, msg: str) -> None:
        print(f"  ok   item {item}: {msg}")

    def skip(self, item: int, msg: str) -> None:
        print(f"  SKIP item {item}: {msg}")


def item1_words(rep: Report, en: str) -> None:
    sums = spans(en, "cv-sum")
    if len(sums) != 6:
        rep.fail(1, f"expected 6 .cv-sum spans in site/cv.qmd, found {len(sums)}")
    over = [(i + 1, words(s)) for i, s in enumerate(sums) if words(s) > 55]
    for i, n in over:
        rep.fail(1, f".cv-sum #{i} has {n} words (limit 55)")
    if not over:
        rep.ok(1, "word budget: " + ", ".join(str(words(s)) for s in sums) + " words (limit 55)")


def item2_links(rep: Report, text: str, zh: bool, label: str, rendered: Path | None) -> None:
    pre = "/zh/research/" if zh else "/research/"
    blocks = paper_blocks(text)
    papers = [b for b in blocks if slug_of(b, zh)]
    thesis = [b for b in blocks if not slug_of(b, zh)]
    if len(papers) != 5 or len(thesis) != 1:
        rep.fail(2, f"{label}: {len(papers)} paper blocks and {len(thesis)} thesis blocks (want 5 + 1)")
    slugs = [slug_of(b, zh) for b in papers]
    if slugs != SLUGS:
        rep.fail(2, f"{label}: paper order {slugs} differs from {SLUGS}")
    for b, slug in zip(papers, slugs):
        rows = spans(b, "cv-plinks")
        if len(rows) != 1:
            rep.fail(2, f"{label} {slug}: {len(rows)} .cv-plinks rows (want 1)")
            continue
        row = rows[0]
        if not re.search(r"\]\(/assets/pdfs/[A-Za-z0-9_]+\.pdf\)", row):
            rep.fail(2, f"{label} {slug}: .cv-plinks has no /assets/pdfs/*.pdf link")
        if "/research/" in row:
            rep.fail(2, f"{label} {slug}: .cv-plinks contains a /research/ link (the title is the one paper-page link)")
        has_doi = "https://doi.org/10.2139/ssrn." in b
        if (slug in SSRN_SLUGS) != has_doi:
            rep.fail(2, f"{label} {slug}: DOI link {'missing' if slug in SSRN_SLUGS else 'unexpected'}")
        for m in re.finditer(r"\[([^\]]*)\]\(([^)]*)\)(\{[^}]*\})?", row):
            attrs = m.group(3) or ""
            if not re.search(r'aria-label="[^"]+"', attrs):
                rep.fail(2, f"{label} {slug}: link '{m.group(1)}' in .cv-plinks lacks a non-empty aria-label")
    for b in thesis:
        if spans(b, "cv-plinks") or "](/" in b:
            rep.fail(2, f"{label}: the thesis block must carry no link")
    n_src = sum(len(re.findall(r"\]\(", row)) for b in papers for row in spans(b, "cv-plinks"))
    if rendered is not None:
        if rendered.exists():
            p = PlinkAnchors()
            p.feed(read(rendered))
            bad = [t for t, lab in p.anchors if not lab]
            if len(p.anchors) != n_src:
                rep.fail(2, f"{label}: rendered {rendered.name} has {len(p.anchors)} .cv-plinks anchors, source has {n_src}")
            elif bad:
                rep.fail(2, f"{label}: rendered anchors without aria-label: {bad}")
            else:
                rep.ok(2, f"{label}: {len(p.anchors)} rendered .cv-plinks anchors all carry aria-label ({rendered})")
        else:
            print(f"  note item 2: rendered page {rendered} not found; source-level aria-label check only")
    if not any(f.startswith("item 2") and label in f for f in rep.failures):
        rep.ok(2, f"{label}: 5 paper blocks in order, PDF rows, DOIs and aria-labels present, thesis unlinked")


def months_en(s: str) -> list[tuple[int, int]]:
    names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December"]
    return [(int(y), names.index(m) + 1) for m, y in re.findall(r"\b(" + "|".join(names) + r") (20\d\d)\b", s)]


def months_zh(s: str) -> list[tuple[int, int]]:
    return [(int(y), int(m)) for y, m in re.findall(r"(20\d\d) 年 (\d{1,2}) 月", s)]


def item3_sync(rep: Report, en: str, zh: str) -> None:
    fails = 0

    def cmp(name, a, b):
        nonlocal fails
        if a != b:
            fails += 1
            rep.fail(3, f"{name} differ: EN {a} vs ZH {b}")

    doi = re.compile(r"https://doi\.org/10\.2139/ssrn\.\d+")
    cmp("ordered DOIs", doi.findall(en), doi.findall(zh))
    pdf = re.compile(r"\]\((/assets/pdfs/[A-Za-z0-9_]+\.pdf)\)")
    cmp("PDF hrefs", set(pdf.findall(en)), set(pdf.findall(zh)))
    cmp("paper slugs", [slug_of(b, False) for b in paper_blocks(en)], [slug_of(b, True) for b in paper_blocks(zh)])
    en_meta = [months_en(" ".join(spans(b, "cv-pmeta"))) for b in paper_blocks(en)]
    zh_meta = [months_zh(" ".join(spans(b, "cv-pmeta"))) for b in paper_blocks(zh)]
    cmp("status months per paper block", en_meta, zh_meta)
    cmp("Updated month", months_en(" ".join(spans(en, "cv-updated"))), months_zh(" ".join(spans(zh, "cv-updated"))))
    for e, z in HEDGES:
        if e not in en:
            fails += 1
            rep.fail(3, f"EN hedge missing: '{e}'")
        if z not in zh:
            fails += 1
            rep.fail(3, f"ZH hedge missing: '{z}'")
    m = re.search(r"^translated-from:\s*([0-9a-f]+)", zh, re.M)
    sha = m.group(1) if m else ""
    if not sha:
        fails += 1
        rep.fail(3, "held ZH CV has no translated-from key")
    else:
        rc, full = git("rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
        if rc != 0 or not full:
            fails += 1
            rep.fail(3, f"translated-from {sha} is not a commit in this repository")
        else:
            if git("merge-base", "--is-ancestor", full, "HEAD")[0] != 0:
                fails += 1
                rep.fail(3, f"translated-from {sha} is not an ancestor of HEAD")
            _, dirty = git("status", "--porcelain", "--", "site/cv.qmd")
            _, last = git("log", "-1", "--format=%H", "--", "site/cv.qmd")
            if dirty:
                fails += 1
                rep.fail(3, "site/cv.qmd has uncommitted changes; the held ZH translated-from must name its committed state")
            elif last != full:
                fails += 1
                rep.fail(3, f"translated-from {sha} is not the last commit touching site/cv.qmd ({last[:7]})")
    if not fails:
        rep.ok(3, f"EN/ZH sync: DOIs, PDFs, slugs, months, hedges agree; translated-from {sha} is the last cv.qmd commit")


def grep_files(paths: list[Path], pattern: re.Pattern, extract=None) -> list[str]:
    hits = []
    for p in paths:
        try:
            text = read(p)
        except UnicodeDecodeError:
            continue
        if extract:
            text = extract(text)
        for m in pattern.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{p.relative_to(WEB)}:{line}: {m.group(0)}")
    return hits


def item4_banned(rep: Report, en_only: bool) -> None:
    fails = []
    en_files = [EN_CV]
    zh_files = [] if en_only else [ZH_CV]
    status = re.compile(r"\b(forthcoming|under review|submitted to|target journal)\b", re.I)
    fails += grep_files(en_files + zh_files, status)
    fails += grep_files([EN_HOME] + ([] if en_only else [ZH_HOME]), status, bio_block)
    fails += grep_files(zh_files + ([] if en_only else [ZH_HOME]), re.compile(r"拟投|在审"))
    we = re.compile(r"\b(we|our)\b", re.I)
    fails += grep_files(en_files, we)
    fails += grep_files([EN_HOME], we, bio_block)
    women = re.compile(r"我们|笔者")
    fails += grep_files(zh_files, women)
    fails += grep_files([] if en_only else [ZH_HOME], women, bio_block)
    claims = re.compile(r"novel|first to|fills a gap|mispricing", re.I)
    fails += grep_files(en_files + zh_files, claims)
    fails += grep_files([EN_HOME] + ([] if en_only else [ZH_HOME]), claims, bio_block)
    fails += grep_files(en_files + zh_files, re.compile(r"\bserved\b|Paper page|2\.51|0\.39"))
    fails += grep_files(site_text_files(), re.compile(r"github\.com/yl7919/naipca|EPFL-Rolling"))
    for h in fails:
        rep.fail(4, f"banned string: {h}")
    if not fails:
        rep.ok(4, "no banned strings in the CV files and bio blocks; no private-repository reference under site/")


def item5_withheld(rep: Report, en_only: bool, no_git: bool = False) -> None:
    pat = re.compile(r"Nankai|Michigan China Forum|南开|密歇根中国论坛")
    hits = grep_files(site_text_files(), pat)
    for h in hits:
        rep.fail(5, f"withheld string in a public file: {h}")
    held = HELD_SERVICE if not en_only else HELD_SERVICE[:1]
    for p in held:
        if not p.exists():
            rep.fail(5, f"{p.relative_to(WEB)} is missing")
        elif not pat.search(read(p)):
            rep.fail(5, f"{p.relative_to(WEB)} does not contain the withheld Service block")
        else:
            # _held/ is private material: it must stay OUT of the public repository (never git add -f).
            rc, out = git("ls-files", "--error-unmatch", str(p.relative_to(WEB)))
            if rc == 0 and out:
                rep.fail(5, f"{p.relative_to(WEB)} is tracked by git: held material must not be in the public repository (git rm --cached)")
    if not hits and not any(f.startswith("item 5") for f in rep.failures):
        rep.ok(5, "withheld Service strings absent from site/**; held service file(s) present on disk and not tracked by git")


def item6_private(rep: Report, en_only: bool) -> None:
    pat = re.compile(r"\+44|1992\.10|出生|民族|SW7|Princes Gate")
    files = site_text_files() + ([] if en_only else [ZH_CV])
    hits = grep_files(files, pat)
    for h in hits:
        rep.fail(6, f"private data: {h}")
    if not hits:
        rep.ok(6, "no phone, birth date, ethnicity or address strings under site/" + ("" if en_only else " or in the held ZH CV"))


def item7_numbers(rep: Report, text: str, zh: bool, label: str) -> None:
    lang = "zh" if zh else "en"
    fails = 0
    for b in paper_blocks(text):
        slug = slug_of(b, zh) or "thesis"
        for s in spans(b, "cv-sum"):
            toks = numeric_tokens(s)
            if slug == "thesis" and toks:
                fails += 1
                rep.fail(7, f"{label} thesis summary carries numeric tokens {toks} (R10: none allowed)")
                continue
            bad = [t for t in toks if t not in NUMBERS[slug][lang]]
            if bad:
                fails += 1
                rep.fail(7, f"{label} {slug}: tokens {bad} not in whitelist {sorted(NUMBERS[slug][lang])}")
    doc = doctoral_block(text, "博士阶段研究" if zh else "**Doctoral research**")
    if doc is None:
        fails += 1
        rep.fail(7, f"{label}: doctoral-research block not found")
    else:
        bad = [t for t in numeric_tokens(doc) if t not in NUMBERS["doctoral"][lang]]
        if bad:
            fails += 1
            rep.fail(7, f"{label} doctoral block: tokens {bad} not in whitelist {sorted(NUMBERS['doctoral'][lang])}")
    if not fails:
        rep.ok(7, f"{label}: every numeric token in the summaries and the doctoral block is whitelisted; thesis has none")


def probe(url: str) -> tuple[str, str]:
    if not shutil.which("curl"):
        return "000", "curl not installed"
    res = subprocess.run(["curl", "-sIL", "-o", "/dev/null", "-w", "%{http_code} %{url_effective}", "--max-time", "20",
                          url], capture_output=True, text=True)
    parts = res.stdout.strip().split(" ", 1)
    code = parts[0] if parts and parts[0] else "000"
    return code, (parts[1] if len(parts) > 1 else "")


def item8_urls(rep: Report, texts: dict[str, str], network: bool) -> None:
    if not network:
        rep.skip(8, "external URL probes skipped (--no-network); the SIF link gate is not re-evaluated")
        return
    fails = 0
    results = {}
    for url in EXTERNAL_URLS:
        code, eff = probe(url)
        results[url] = (code, eff)
        if code in ("000", "404", "410"):
            fails += 1
            rep.fail(8, f"{url} -> {code} {eff}".rstrip())
        else:
            print(f"       {code} {url}" + (f" -> {eff}" if eff and eff.rstrip('/') != url.rstrip('/') else ""))
    code, eff = results[SIF_URL]
    linked_ok = code == "200" and not any(t in eff.lower() for t in LOGIN_TOKENS)
    for lang, text in texts.items():
        has_link = f"]({SIF_URL})" in text
        has_text = SIF_TEXT[lang] in text
        if linked_ok and not has_link:
            fails += 1
            rep.fail(8, f"{lang}: SIF page reachable ({code} {eff}) but the CV does not link it")
        if not linked_ok and has_link:
            fails += 1
            rep.fail(8, f"{lang}: SIF probe {code} {eff}: the link must be dropped to plain text (report the redirect target)")
        if not has_text:
            fails += 1
            rep.fail(8, f"{lang}: '{SIF_TEXT[lang]}' missing from the visiting-researcher bullet")
    if not fails:
        rep.ok(8, f"{len(EXTERNAL_URLS)} external URLs answer; SIF gate: {code} {eff} -> link {'kept' if linked_ok else 'plain text'}")


def item9_hygiene(rep: Report) -> None:
    fails = 0
    qmd_text = "\n".join(read(p) for p in SITE.rglob("*.qmd")
                         if not p.name.startswith("._") and "_site" not in p.parts)
    for p in sorted(PDF_DIR.iterdir()):
        if p.name.startswith("._"):
            continue
        low = p.name.lower()
        if ".tmp" in low or ".failed" in low or p.name == "print.pdf":
            fails += 1
            rep.fail(9, f"intermediate file in site/assets/pdfs/: {p.name}")
        elif p.name not in SERVED_PDFS and p.name not in qmd_text:
            fails += 1
            rep.fail(9, f"unexpected file in site/assets/pdfs/ (not a served PDF, not referenced from a .qmd): {p.name}")
    if not fails:
        rep.ok(9, "site/assets/pdfs/ holds only served or referenced PDFs (AppleDouble companions ignored)")


def sections(text: str) -> list[tuple[str, str]]:
    """(heading without its `[English]{.h2-en}` tag, body up to the next `## `) for every level-2 heading."""
    heads = list(re.finditer(r"^## (.+)$", text, re.M))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append((re.sub(r"\s*\[[^\]]*\]\{\.h2-en\}\s*$", "", m.group(1)).strip(), text[m.end():end]))
    return out


def item10_structure(rep: Report, text: str, zh: bool, label: str, home: str) -> None:
    lang = "zh" if zh else "en"
    fails = 0

    def bad(msg: str) -> None:
        nonlocal fails
        fails += 1
        rep.fail(10, f"{label}: {msg}")

    secs = sections(text)
    names = [n for n, _ in secs]
    if names != SECTIONS[lang]:
        bad(f"section order {names} differs from {SECTIONS[lang]}")
    body = dict(secs)
    research = body.get(SECTIONS[lang][2], "")
    subs = re.findall(r"^### (.+)$", research, re.M)
    if subs != SUBSECTIONS[lang]:
        bad(f"Research subsections {subs} differ from {SUBSECTIONS[lang]}")
    jmp = re.search(r"^:::: \{\.cv-jmp\}\n(.*?)\n::::$", research, re.M | re.S)
    if not jmp:
        bad("no `.cv-jmp` block in Research")
    else:
        if research.find(":::: {.cv-jmp}") > research.find("::: {.cv-paper}"):
            bad("the `.cv-jmp` block is not the first paper in Research")
        if not any(JMP_TAG[lang] in t for t in spans(jmp.group(1), "cv-tag")):
            bad(f"the job market paper has no `.cv-tag` label containing '{JMP_TAG[lang]}'")
        blocks = paper_blocks(jmp.group(1))
        if len(blocks) != 1 or slug_of(blocks[0], zh) != SLUGS[0]:
            bad(f"the `.cv-jmp` block must hold exactly the {SLUGS[0]} paper")
    service = body.get(SECTIONS[lang][7], "")
    if SIF_TEXT[lang] not in service:
        bad(f"Service lacks '{SIF_TEXT[lang]}'")
    for u in SERVICE_LINKS:
        if f"]({u})" not in service:
            bad(f"Service lacks the link {u}")
    refs = body.get(SECTIONS[lang][-1], "")
    cards = re.findall(r"^::: \{\.cv-ref\}\n(.*?)\n:::$", refs, re.M | re.S)
    if len(cards) != len(REFEREES):
        bad(f"References has {len(cards)} `.cv-ref` cards (want {len(REFEREES)})")
    for card, (slug, mail) in zip(cards, REFEREES):
        if f"](mailto:{mail})" not in card:
            bad(f"referee {slug}: no mailto:{mail} link")
        if f"](https://profiles.imperial.ac.uk/{slug})" not in card:
            bad(f"referee {slug}: no profile link https://profiles.imperial.ac.uk/{slug}")
    if re.search(r"on request|备索", refs, re.I):
        bad("References still carries an 'on request' line")
    if DOUBLE_MAJOR[lang] not in body.get(SECTIONS[lang][1], ""):
        bad(f"Education lacks '{DOUBLE_MAJOR[lang]}'")
    if DOUBLE_MAJOR[lang] not in bio_block(home):
        bad("home .bio block lacks the double-major wording")
    for where, t in (("CV", text), ("home .bio", bio_block(home))):
        m = NOT_DUAL.search(t)
        if m:
            bad(f"{where} says '{m.group(0)}' (the Michigan record is one B.S. with two majors)")
    if not fails:
        rep.ok(10, f"{label}: {len(names)} sections in job-market order, JMP tagged first, Service with SIF/QRT/LSEG "
                   f"links, {len(cards)} referees with e-mail and profile, double-major wording in CV and bio")
    # The item-10 home check reads only the `.bio` block; the Path panel wording is reviewed by eye.


# -------------------------------------------------------------------------------------------------- main
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="CV checks (spec Part B 4.2)")
    ap.add_argument("--en-only", action="store_true")
    ap.add_argument("--rendered", type=Path, default=SITE / "_site", help="rendered site dir (item 2 aria-labels)")
    ap.add_argument("--rendered-zh", type=Path, default=None, help="rendered held ZH cv.html (print_cv.sh scratch)")
    ap.add_argument("--no-network", action="store_true")
    ap.add_argument("--no-sync", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)

    rep = Report()
    en = read(EN_CV)
    zh = read(ZH_CV) if ZH_CV.exists() else ""
    if not a.en_only and not zh:
        rep.fail(2, f"{ZH_CV.relative_to(WEB)} is missing")
    print(f"check_cv: site/cv.qmd" + ("" if a.en_only else " and _held/site/zh/cv.qmd") +
          (" (--en-only)" if a.en_only else ""))

    item1_words(rep, en)
    item2_links(rep, en, False, "EN", a.rendered / "cv.html")
    if not a.en_only and zh:
        rz = a.rendered_zh if a.rendered_zh else (a.rendered / "zh/cv.html" if (a.rendered / "zh/cv.html").exists() else None)
        item2_links(rep, zh, True, "ZH", rz)
    if a.en_only:
        rep.skip(3, "EN/ZH sync skipped (--en-only)")
    elif a.no_sync:
        rep.skip(3, "EN/ZH sync skipped (--no-sync)")
    elif zh:
        item3_sync(rep, en, zh)
    item4_banned(rep, a.en_only)
    item5_withheld(rep, a.en_only, a.no_git)
    item6_private(rep, a.en_only)
    item7_numbers(rep, en, False, "EN")
    if not a.en_only and zh:
        item7_numbers(rep, zh, True, "ZH")
    texts = {"en": en}
    if not a.en_only and zh:
        texts["zh"] = zh
    item8_urls(rep, texts, not a.no_network)
    item9_hygiene(rep)
    item10_structure(rep, en, False, "EN", read(EN_HOME))
    if not a.en_only and zh:
        item10_structure(rep, zh, True, "ZH", read(ZH_HOME))

    if rep.failures:
        print(f"check_cv: {len(rep.failures)} failure(s)")
        return 1
    print("check_cv: all items passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
