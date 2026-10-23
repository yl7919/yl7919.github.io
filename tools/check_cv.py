#!/usr/bin/env python3
"""CV checks over site/cv.qmd and site/zh/cv.qmd (spec Part B 4.2). Exit 1 on any failure.

Since 2026-09-30 (owner round 5) the Chinese CV is public again: site/zh/cv.qmd and
site/assets/pdfs/Mingyang_Liu_CV_ZH.pdf. The held Service files (cv-service.qmd, zh/cv-service.qmd) stay private
and untracked; they are looked up in web/_held/site/ and, when that copy is absent, in the sibling
held_private/web_held/site/ (override with PWS_HELD=<dir holding site/>).

    tools/check_cv.py                       all ten items (precommit.sh step 7/7)
    tools/check_cv.py --en-only             items 1, 4, 5, 6, 8, 9 and the EN halves of 2, 7 and 10; item 3 skipped [ME-16]
    tools/check_cv.py --rendered DIR        rendered site for the aria-label half of item 2 (default site/_site)
    tools/check_cv.py --rendered-zh FILE    rendered ZH page (print_cv.sh scratch) for the same check
    tools/check_cv.py --no-network          skip the curl probes of item 8 (printed as SKIPPED, never silent)
    tools/check_cv.py --no-sync             skip item 3 only (before the controller commits site/cv.qmd and sets translated-from)
    tools/check_cv.py --no-git              accepted for compatibility; item 5 always checks that held files are untracked

Items (numbering as in the spec):
 1. Word budget (EN): each `.cv-sum` in site/cv.qmd is at most 55 words after `[label](url){attrs}` -> label
    and stripping `*`; hyphenated compounds count as one word (five papers, the research-in-progress entry and
    the thesis: seven summaries).
 2. Link completeness and titles: every non-thesis `.cv-paper` has a `.cv-ptitle` link to /research/<slug>.html
    (ZH: /zh/research/) and a `.cv-plinks` row with an /assets/pdfs/*.pdf link; the two SSRN entries link
    https://doi.org/10.2139/ssrn.<id>; no `.cv-plinks` contains a /research/ link; every link in a `.cv-plinks`
    row carries a non-empty aria-label (checked in the source, and in the rendered HTML when it exists);
    five paper blocks and one thesis block per file; each paper title appears verbatim in its `.cv-ptitle`
    (TITLES; the ZH page prints it in parentheses after the Chinese title); no link to a retired manuscript
    (RETIRED_PDFS) or retired paper page (RETIRED_SLUGS). Round 11 (2026-10-16): one research-in-progress block
    (`::: {.cv-paper .cv-progress}`) carries the corporate-bond title verbatim and, in its `.cv-pmeta` (printed on
    the title line), "with Paolo Zaffaroni" and the "in preparation" status; no draft exists (owner, 2026-10-16), so
    no "on request"/"draft"/备索/初稿 wording; no link.
 3. Sync EN/ZH: ordered DOIs, the set of /assets/pdfs/*.pdf hrefs, the ordered paper-page slugs, the status
    months per paper block and the "Updated"/更新于 month are identical; every hedge pair of 2.5.8 is present;
    the ZH `translated-from` sha is a commit, an ancestor-or-equal of HEAD and the last commit that touched
    site/cv.qmd (which must itself be committed); the ZH page names /cv.html as its translation and the EN page
    /zh/cv.html.
 4. Banned strings in the two CV files and the two home `.bio` blocks (including, since 2026-09-30, any job-market
    line in the CVs and any name in the local, untracked guard list); the "Job market paper"/求职论文 label
    appears exactly once per CV, as the `.cv-tag` of the first working paper (D11-2, 2026-10-16), and never in
    the home bios; no private-repository reference anywhere under site/.
 5. Withheld Service strings (since 2026-09-30 only the Nankai–Columbia exchange and the Michigan China Forum
    items; the Imperial Student Investment Fund chair block is public again) absent from public files
    (site/**, which now includes the public ZH CV), present in both held service files, and neither held file
    tracked by git (private material stays local).
 6. Private data absent from site/** (the public ZH CV included; its 证件姓名 line is allowed; since round 11 the
    placement office number on the job-market pages, PLACEMENT_PHONE, is allowed and every other +44 is not).
 7. Numbers: every numeric token in each `.cv-sum` and in the doctoral-research bullets is in the whitelist
    derived from 2.5.7 and 2.6 (Part 0 D2: 36, 12,813, 1964-2014; round 11: the two renamed papers' summaries);
    the thesis and research-in-progress blocks have no numeric token.
 8. External URLs answer (not 404/410/connection error); SIF reachability gate for the SIF link.
 9. site/assets/pdfs/ hygiene: no *.tmp*, *.failed*, print.pdf; every file is a served PDF or referenced from a
    .qmd under site/; `._*` AppleDouble companions are ignored as check_links rule (i) tolerates them; a retired
    manuscript still in the folder is reported as such (the controller relocates it, D11-3).
10. Structure (research-first order; job market paper labelled, D11-2): the `##`
    sections appear exactly in SECTIONS order (References last; Research Projects after Research
    Experience, round 11); Research holds the Working Papers, Research in Progress and PhD Thesis subsections;
    the first working paper is The Ruler Matters, whose block opens with the one `.cv-tag` reading JMP_TAG
    (no `.cv-jmp` wrapper); no other job-market `.cv-tag`; the job market paper block carries one `.cv-talks` line (JMP_TALKS: the
    EPFL seminar with its event link and the scheduled Cambridge talk; never "brown bag"); Research Projects carries
    the research-collaboration entry (PROJECT) with its date column, the EPFL event link, no replication-audit
    clause and no coauthor wording (owner, 2026-10-16 21:10); Positions carries the independent-consultant entry (CONSULTANT); Education carries
    the owner-specified Columbia and Michigan dates (EDU_DATES; the superseded May end months absent) and the consultant entry's date column reads CONSULTANT_WHEN (no dates); Teaching links the teaching notes
    (the 96-page public edition /assets/pdfs/projects/Mingyang_Liu_Teaching_Notes_RMFE_public.pdf, with an
    aria-label) labelled "shared for academic use"
    (ZH 仅供学术用途; owner D1, 2026-10-01); Service carries the SIF chair
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
ZH_CV = SITE / "zh/cv.qmd"
EN_HOME = SITE / "index.qmd"
ZH_HOME = SITE / "zh/index.qmd"


def _held_root() -> Path:
    import os
    if os.environ.get("PWS_HELD"):
        return Path(os.environ["PWS_HELD"])
    # web/_held, else a held copy beside the repository or beside a worktree one level further down
    for cand in (WEB / "_held", WEB.parent / "held_private/web_held", WEB.parent.parent / "held_private/web_held"):
        if (cand / "site/cv-service.qmd").exists():
            return cand
    return WEB / "_held"


HELD = _held_root()
HELD_SERVICE = [HELD / "site/cv-service.qmd", HELD / "site/zh/cv-service.qmd"]
PDF_DIR = SITE / "assets/pdfs"

# Round 11 (2026-10-15/16, D11-1, D11-3): The Ruler Matters replaces Characteristic Libraries (first, the job market
# paper) and Same Forecasts, Different Portfolios replaces Characteristic Geometry (same position); new slugs and PDFs.
SLUGS = ["the-ruler-matters", "characteristic-space-metrics", "geometric-framework",
         "same-forecasts-different-portfolios", "interpreting-pricing-errors"]
SSRN_SLUGS = {"characteristic-space-metrics", "geometric-framework"}
# Exact titles (title pages of the served PDFs); the CV prints each verbatim in its `.cv-ptitle` (item 2) and the
# printed CV PDFs must extract them verbatim (tools/print_cv.sh, check titles).
TITLES = {
    "the-ruler-matters": "The Ruler Matters: Factor Exposures, Attribution, and Portfolio Risk",
    "characteristic-space-metrics": "Characteristic-Space Metrics in Factor Models: Identification and Inference",
    "geometric-framework": "A Geometric Framework for Identification in Characteristic-Based Factor Models",
    "same-forecasts-different-portfolios": "Same Forecasts, Different Portfolios: Factor Normalization and Regularization",
    "interpreting-pricing-errors": "Interpreting Estimated Pricing Errors: Evidence from Characteristic-Based Return Forecasts",
}
# Research in progress (D11-4): the corporate-bond working paper with Paolo Zaffaroni, no page, no PDF, no link.
PROGRESS_TITLE = "Exposure or Intercept? Identifying Corporate Bond Premia with No-Arbitrage IPCA"
PROGRESS_META = {"en": ["with Paolo Zaffaroni", "in preparation"], "zh": ["与 Paolo Zaffaroni 合著", "撰写中"]}
# Owner, 2026-10-16: Paolo Zaffaroni agreed to coauthor, but no draft exists yet, so nothing may offer one.
PROGRESS_NO_DRAFT = re.compile(r"on request|draft|备索|初稿", re.I)
PAPER_PDFS = ["The_Ruler_Matters.pdf", "Characteristic_Space_Metrics_Main.pdf",
              "Characteristic_Space_Metrics_Online_Supplement.pdf", "Geometric_Framework_SSRN_7013178.pdf",
              "Same_Forecasts_Different_Portfolios.pdf", "Interpreting_Estimated_Pricing_Errors.pdf"]
# Superseded manuscripts and slides (D11-3): no CV may link them; the controller relocates the files to
# held_private/web_held/superseded_pdfs_2026-10-15/ with a manifest. Old paper-page slugs live on only as aliases.
RETIRED_PDFS = ["Characteristic_Libraries_and_Portfolio_Decisions_SSRN_v2.pdf",
                "Characteristic_Geometry_and_Portfolio_Choice.pdf", "Characteristic_Geometry_and_Portfolio_Choice_Slides.pdf"]
RETIRED_SLUGS = ["characteristic-libraries", "characteristic-geometry"]
# The academic CVs (D11-7), linked from /jobmarket/ (EN and ZH), are served PDFs of the CV unit.
ACADEMIC_CV_PDFS = {"Mingyang_Liu_Academic_CV.pdf", "Mingyang_Liu_Academic_CV_ZH.pdf"}
# Teaching notes: shared for academic use since 2026-10-01 (owner D1); both CVs link the 96-page public edition
# (no dedication, cohort photograph or cohort-only notice), the same file the Projects and job-market pages link (item 10).
TEACHING_PDF = "projects/Mingyang_Liu_Teaching_Notes_RMFE_public.pdf"
TEACHING_LABEL = {"en": "shared for academic use", "zh": "仅供学术用途"}
# The original 99-page teaching-notes edition left site/ on 2026-10-01 (held_private/pending/); only the 96-page
# public edition under assets/pdfs/projects/ is served.
SERVED_PDFS = set(PAPER_PDFS) | {"Characteristic_Space_Metrics_Slides.pdf", "Mingyang_Liu_CV.pdf",
                                 "Mingyang_Liu_CV_ZH.pdf"} | ACADEMIC_CV_PDFS

# 2.5.8 hedge pairs (EN string in the EN file, ZH string in the ZH file).
# Round 5 (2026-09-30): pairs follow the professor committee's final summary wording.
# Round 11 (2026-10-16): the Characteristic Libraries pairs retire with that paper; The Ruler Matters keeps the
# abstract's "can" and both "with coefficients fixed" and "joint fitted returns" qualifiers; Same Forecasts keeps
# the gross qualifier and the imprecise post-October-2007 net advantage (p. 6).
HEDGES = [
    ("nearly identical forecasts", "几乎相同"),
    ("gross Sharpe ratio", "未计交易成本"),
    ("net advantage since October 2007 is imprecise", "扣除交易成本后的优势估计并不精确"),
    ("can raise in-sample fit", "样本内拟合可能提高"),
    ("not joint fitted returns", "联合拟合收益不变"),
    ("With coefficients fixed", "在系数固定时"),
    ("identical fit", "拟合完全相同"),
    ("exploratory evidence", "属探索性证据"),
    ("near-identical fit coexisting with different identified pricing directions", "拟合几乎相同的模型可对应不同的已识别定价方向"),
    ("does not isolate the metric", "并未把度量的作用单独分离出来"),
]

# 2.5.7 / 2.6 number whitelist, per block and language. The Ruler Matters: 36 and 153 characteristics (abstract,
# title page). Same Forecasts: October 2007 (p. 6; the ZH month is a separate token). The research-in-progress
# entry carries no number.
NUMBERS = {
    "the-ruler-matters": {"en": {"36", "153"}, "zh": {"36", "153"}},
    "characteristic-space-metrics": {"en": set(), "zh": set()},
    "geometric-framework": {"en": set(), "zh": set()},
    "same-forecasts-different-portfolios": {"en": {"2007"}, "zh": {"2007", "10"}},
    "interpreting-pricing-errors": {"en": {"153"}, "zh": {"153"}},
    "progress": {"en": set(), "zh": set()},
    "thesis": {"en": set(), "zh": set()},
    "doctoral": {"en": {"120", "1973–2024", "153", "1962–2025", "36", "12,813", "1964–2014"},
                 "zh": {"120", "1973–2024", "153", "1962–2025", "36", "12,813", "1964–2014"}},
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
    "https://econ.columbia.edu/econpeople/jushan-bai/",
    "https://doi.org/10.2139/ssrn.7013178",
    "https://doi.org/10.2139/ssrn.7445120",
    "https://www.qube-rt.com/",
]

# Item 10: section order (EN headings; ZH headings without their [English]{.h2-en} tag), research subsections,
# referees (profile slug, e-mail) in order, and the double-major wording.
SECTIONS = {
    "en": ["Research Fields", "Education", "Research", "Positions", "Research Experience", "Research Projects",
           "Teaching and Mentoring", "Scholarships and Honours", "Skills and Languages", "References"],
    "zh": ["研究方向", "教育背景", "学术论文", "学术任职", "科研经历", "研究项目", "教学与指导", "奖学金与荣誉",
           "专业技能与语言", "推荐人"],
}
# Section bodies are looked up by name (SEC[lang][key]), so a new section cannot shift the checks.
SEC = {lang: dict(zip(["fields", "education", "research", "positions", "experience", "projects", "teaching",
                       "honours", "skills", "references"], names)) for lang, names in SECTIONS.items()}
# A short capability synopsis precedes the research-first sections.
LEAD = {"en": "Research Summary", "zh": "研究概要"}
SUBSECTIONS = {"en": ["Working Papers", "Research in Progress", "PhD Thesis"],
               "zh": ["工作论文（Working Papers）", "进行中的研究（Research in Progress）", "博士学位论文（PhD Thesis）"]}
# D11-2 (owner, 2026-10-16, reversing the round-7 rule): The Ruler Matters is the job market paper; the site CV
# marks it, and only it, with this `.cv-tag` on the title line of the first working paper (no `.cv-jmp` wrapper).
JMP_LABEL = re.compile(r"job market paper|求职论文|就业市场论文", re.I)
JMP_TAG = {"en": "Job market paper", "zh": "求职论文"}
JMP_SLUG = "the-ruler-matters"
# D11-5 as finally decided by the owner (2026-10-16 21:10): an ongoing research collaboration with Prof. Semyon
# Malamud that began after the invited EPFL seminar of 16 June 2026 (event link required); never a coauthored paper,
# no replication-audit clause; dates Jul 2026–present. ZH bylines use 合著 for coauthorship, so 合著 is banned here.
EPFL_EVENT = "https://memento.epfl.ch/event/no-arbitrage-factor-geometry-identification-in-hig/"
PROJECT = {"en": {"when": "Jul 2026–present", "text": "Ongoing research collaboration"},
           "zh": {"when": "2026.07–至今", "text": "合作研究（进行中）"}}
PROJECT_BANNED = re.compile(r"replication audit|复制核对|coauthor|co-author|joint paper|合作者|联合作者|合著", re.I)
# Invited talks under the job market paper (owner, 2026-10-16): EPFL seminar (linked) and the scheduled Cambridge talk.
JMP_TALKS = {"en": ["EPFL", "Cambridge", "scheduled", EPFL_EVENT], "zh": ["EPFL", "剑桥", "即将举行", EPFL_EVENT]}
BROWN_BAG = re.compile(r"brown[ -]?bag|布朗袋", re.I)
# Consulting entry; fixed education dates.
CONSULTANT = {"en": "Independent Quantitative Research & AI/ML Consultant", "zh": "独立量化研究与人工智能/机器学习顾问"}
# Degrees conferred Feb 2019 (Columbia M.A.) and Apr 2017 (Michigan B.S.);
# the earlier May end months (conventional graduation season) must not come back.
EDU_DATES = {"en": ["Aug 2017–Feb 2019", "Aug 2014–Apr 2017"], "zh": ["2017.08–2019.02", "2014.08–2017.04"]}
STALE_EDU_DATES = {"en": ["Aug 2017–May 2019", "Aug 2014–May 2017"], "zh": ["2017.08–2019.05", "2014.08–2017.05"]}
# The consultant entry carries no dates.
CONSULTANT_WHEN = {"en": "Selected engagements", "zh": "部分项目"}
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


def progress_blocks(text: str) -> list[str]:
    """Research-in-progress entries (`::: {.cv-paper .cv-progress}`): not paper blocks, no page, no PDF."""
    return re.findall(r"^::: \{\.cv-paper \.cv-progress\}\n(.*?)\n:::$", text, re.M | re.S)


def flat(md: str) -> str:
    """Visible text of a Markdown fragment: links and bracketed spans reduced to their labels, `*` removed."""
    prev = None
    while prev != md:
        prev = md
        md = re.sub(r"\[([^\[\]]*)\]\([^)]*\)(\{[^}]*\})?", r"\1", md)
        md = re.sub(r"\[([^\[\]]*)\]\{[^}]*\}", r"\1", md)
    return md.replace("*", "")


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


def rel(p: Path) -> str:
    """Path for messages: relative to web/ when inside it (the held files may live outside the repository)."""
    try:
        return str(p.relative_to(WEB))
    except ValueError:
        return str(p)


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
    if len(sums) != 7:   # five papers, the research-in-progress entry, the thesis (round 11)
        rep.fail(1, f"expected 7 .cv-sum spans in site/cv.qmd, found {len(sums)}")
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
    # Titles verbatim (round 11): EN prints the title as the link label, ZH in parentheses after the Chinese title.
    for b, slug in zip(papers, slugs):
        t = TITLES.get(slug or "")
        shown = " ".join(flat(s) for s in spans(b, "cv-ptitle"))
        if t and t not in shown:
            rep.fail(2, f"{label} {slug}: .cv-ptitle does not carry the title verbatim: '{t}'")
    # Retired manuscripts and paper pages (D11-1, D11-3): no link anywhere in the CV.
    for name in RETIRED_PDFS:
        if name in text:
            rep.fail(2, f"{label}: links the retired manuscript {name}")
    for s in RETIRED_SLUGS:
        if re.search(re.escape(pre) + re.escape(s) + r"\.html", text):
            rep.fail(2, f"{label}: links the retired paper page {pre}{s}.html (use the new slug)")
    # Research in progress (D11-4): one block, bond title verbatim, coauthor and status line, no link, no PDF.
    prog = progress_blocks(text)
    lang = "zh" if zh else "en"
    if len(prog) != 1:
        rep.fail(2, f"{label}: {len(prog)} research-in-progress blocks (want 1)")
    for b in prog:
        if PROGRESS_TITLE not in " ".join(flat(s) for s in spans(b, "cv-ptitle")):
            rep.fail(2, f"{label} progress: .cv-ptitle does not carry '{PROGRESS_TITLE}' verbatim")
        meta = " ".join(spans(b, "cv-pmeta"))
        for m in PROGRESS_META[lang]:
            if m not in meta:
                rep.fail(2, f"{label} progress: .cv-pmeta lacks '{m}'")
        nd = PROGRESS_NO_DRAFT.search(b)
        if nd:
            rep.fail(2, f"{label} progress: says '{nd.group(0)}' but no draft exists yet")
        if "](" in b or spans(b, "cv-plinks"):
            rep.fail(2, f"{label} progress: the research-in-progress entry must carry no link")
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
        rep.ok(2, f"{label}: 5 paper blocks in order with verbatim titles, PDF rows, DOIs and aria-labels present, "
                  f"no retired link, research-in-progress entry unlinked, thesis unlinked")


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
    cmp("research-in-progress entries", [PROGRESS_TITLE in flat(b) for b in progress_blocks(en)],
        [PROGRESS_TITLE in flat(b) for b in progress_blocks(zh)])
    cmp("job-market tags", len(re.findall(r"\]\{\.cv-tag\}", en)), len(re.findall(r"\]\{\.cv-tag\}", zh)))
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
        rep.fail(3, "ZH CV has no translated-from key")
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
                rep.fail(3, "site/cv.qmd has uncommitted changes; the ZH translated-from must name its committed state")
            elif last != full:
                fails += 1
                rep.fail(3, f"translated-from {sha} is not the last commit touching site/cv.qmd ({last[:7]})")
    if not re.search(r"^translation:\s*/cv\.html\s*$", zh, re.M):
        fails += 1
        rep.fail(3, "site/zh/cv.qmd lacks `translation: /cv.html`")
    if not re.search(r"^translation:\s*/zh/cv\.html\s*$", en, re.M):
        fails += 1
        rep.fail(3, "site/cv.qmd lacks `translation: /zh/cv.html`")
    if not fails:
        rep.ok(3, f"EN/ZH sync: DOIs, PDFs, slugs, months, hedges agree; translated-from {sha} is the last cv.qmd commit")


def private_banned_names() -> list[str]:
    """Names that must never appear in the CVs or home bios. They are kept in the git-ignored
    pipeline/sources.toml ([private_guards] banned_names) so that the public repository does not carry them;
    an empty list when that file or table is absent (e.g. a fresh clone)."""
    cfg = WEB / "pipeline" / "sources.toml"
    if not cfg.exists():
        return []
    import tomllib
    with open(cfg, "rb") as fh:
        return [str(n) for n in tomllib.load(fh).get("private_guards", {}).get("banned_names", []) if str(n)]


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
            hits.append(f"{rel(p)}:{line}: {m.group(0)}")
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
    # Owner round 5 (A1, A5 v, A6): no job-market line on the CVs.
    fails += grep_files(en_files + zh_files, re.compile(r"academic job market|job-market candidate|学术求职|求职中"))
    # No locally banned name in the CVs or the home bios.
    names = private_banned_names()
    if names:
        r7 = re.compile("|".join(re.escape(n) for n in names), re.I)
        fails += grep_files(en_files + zh_files, r7)
        fails += grep_files([EN_HOME] + ([] if en_only else [ZH_HOME]), r7, bio_block)
    # D11-2 (2026-10-16): the job-market-paper label appears exactly once per CV, as the `.cv-tag` of the first
    # working paper (item 10 checks its position); the home bios carry no such label.
    for p, lang in [(EN_CV, "en")] + ([] if en_only else [(ZH_CV, "zh")]):
        t = read(p)
        hits = JMP_LABEL.findall(t)
        tag = f"[{JMP_TAG[lang]}]{{.cv-tag}}"
        if len(hits) != 1 or t.count(tag) != 1:
            fails.append(f"{rel(p)}: job-market label occurs {len(hits)} time(s); want exactly one, as '{tag}'")
    fails += grep_files([EN_HOME] + ([] if en_only else [ZH_HOME]), JMP_LABEL, bio_block)
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
            rep.fail(5, f"{rel(p)} is missing (held root {HELD}; set PWS_HELD)")
        elif not pat.search(read(p)):
            rep.fail(5, f"{rel(p)} does not contain the withheld Service block")
        elif rel(p) != str(p):
            # _held/ is private material: it must stay OUT of the public repository (never git add -f).
            # A held file outside web/ (held_private/) cannot be tracked by this repository.
            rc, out = git("ls-files", "--error-unmatch", rel(p))
            if rc == 0 and out:
                rep.fail(5, f"{rel(p)} is tracked by git: held material must not be in the public repository (git rm --cached)")
    if not hits and not any(f.startswith("item 5") for f in rep.failures):
        rep.ok(5, f"withheld Service strings absent from site/** (public ZH CV included); held service file(s) present in {HELD} and not tracked by git")


# Round 11 (D11-6, owner 2026-10-15): the job-market pages and the academic CVs print the department's placement
# contact, whose office number is public and owner-supplied; every other +44 (the owner's own phone) stays banned.
PLACEMENT_PHONE = re.compile(r"\+44 20 7594 6449|\+442075946449")


def item6_private(rep: Report, en_only: bool) -> None:
    pat = re.compile(r"\+44(?! 20 7594 6449)(?!2075946449)|1992\.10|出生|民族|SW7|Princes Gate")
    files = site_text_files()          # includes site/zh/cv.qmd, public since 2026-09-30
    hits = grep_files(files, pat)
    for h in hits:
        rep.fail(6, f"private data: {h}")
    if not hits:
        rep.ok(6, "no phone (other than the placement office number), birth date, ethnicity or address strings under "
                  "site/ (both CVs included)")


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
            bad = [t for t in toks if t not in NUMBERS.get(slug, {}).get(lang, set())]
            if bad:
                fails += 1
                rep.fail(7, f"{label} {slug}: tokens {bad} not in whitelist {sorted(NUMBERS.get(slug, {}).get(lang, set()))}")
    for b in progress_blocks(text):
        bad = [t for s in spans(b, "cv-sum") for t in numeric_tokens(s) if t not in NUMBERS["progress"][lang]]
        if bad:
            fails += 1
            rep.fail(7, f"{label} research-in-progress summary carries numeric tokens {bad} (none allowed)")
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
        if p.name.startswith("._") or p.is_dir():   # subfolders (e.g. pdfs/blog/) belong to other units
            continue
        low = p.name.lower()
        if ".tmp" in low or ".failed" in low or p.name == "print.pdf":
            fails += 1
            rep.fail(9, f"intermediate file in site/assets/pdfs/: {p.name}")
        elif p.name in RETIRED_PDFS:
            fails += 1
            rep.fail(9, f"retired manuscript still in site/assets/pdfs/: {p.name} (controller relocates it, D11-3)")
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
    if names[:1] != [LEAD[lang]]:
        bad(f"the first section is not '{LEAD[lang]}'")
    names = names[1:]
    if names != SECTIONS[lang]:
        bad(f"section order {names} differs from {SECTIONS[lang]}")
    body = dict(secs)
    sec = SEC[lang]
    research = body.get(sec["research"], "")
    subs = re.findall(r"^### (.+)$", research, re.M)
    if subs != SUBSECTIONS[lang]:
        bad(f"Research subsections {subs} differ from {SUBSECTIONS[lang]}")
    # D11-2: the first working paper is the job market paper, and its block opens with the one job-market tag
    # (on the title line; no `.cv-jmp` wrapper, which cost the Chinese print a line).
    wp = re.split(r"^### .+$", research, flags=re.M)
    wp = wp[1] if len(wp) > 1 else ""
    first = paper_blocks(wp)[:1]
    if not wp.strip().startswith("::: {.cv-paper}\n") or not first:
        bad("the working papers do not open with a paper block")
    elif not first[0].startswith(f"[{JMP_TAG[lang]}]{{.cv-tag}} ") or slug_of(first[0], zh) != JMP_SLUG:
        bad(f"the first working paper is not the {JMP_SLUG} block opening with '[{JMP_TAG[lang]}]{{.cv-tag}}'")
    if ".cv-jmp" in research:
        bad("Research carries a `.cv-jmp` wrapper (the tag on the title line marks the job market paper)")
    tags = spans(research, "cv-tag")
    if [t for t in tags if JMP_LABEL.search(t)] != [JMP_TAG[lang]]:
        bad(f"Research job-market `.cv-tag` labels {tags} differ from ['{JMP_TAG[lang]}']")
    blocks = paper_blocks(research)
    if not blocks or slug_of(blocks[0], zh) != SLUGS[0]:
        bad(f"the first working paper is not {SLUGS[0]}")
    # D11-5 (final, 2026-10-16 21:10): the collaboration sits in Research Projects, dated, linked, no coauthor wording.
    proj = body.get(sec["projects"], "")
    cm = re.search(r"::: \{\.cv-when\}\n([^\n]*)\n:::\n::: \{\.cv-what\}\n([^\n]*)", proj)
    if not cm or cm.group(1).strip() != PROJECT[lang]["when"] or PROJECT[lang]["text"] not in cm.group(2):
        bad(f"Research Projects lacks the entry dated '{PROJECT[lang]['when']}' ('{PROJECT[lang]['text']}')")
    elif f"]({EPFL_EVENT})" not in cm.group(2):
        bad("the research-collaboration entry lacks the EPFL event link")
    m = PROJECT_BANNED.search(proj)
    if m:
        bad(f"Research Projects says '{m.group(0)}' (a research collaboration, never coauthorship; no audit clause)")
    m = BROWN_BAG.search(text)
    if m:
        bad(f"the CV says '{m.group(0)}' (owner: the EPFL talk is an invited seminar)")
    talks = spans(blocks[0], "cv-talks") if blocks else []
    if len(talks) != 1:
        bad(f"the job market paper block carries {len(talks)} `.cv-talks` lines (want 1)")
    else:
        for need in JMP_TALKS[lang]:
            if need not in talks[0]:
                bad(f"the job market paper's presentations line lacks '{need}'")
    positions = body.get(sec["positions"], "")
    # Round 12 (owner, 2026-10-23): academic positioning; the consultant entry and the advisory link must not return.
    for needle in (CONSULTANT[lang], CONSULTANT_WHEN[lang], "advisory.html"):
        if needle in text:
            bad(f"the CV still carries '{needle}' (removed in round 12)")
    for d in EDU_DATES[lang]:
        if d not in body.get(sec["education"], ""):
            bad(f"Education lacks the owner-specified dates '{d}'")
    for d in STALE_EDU_DATES[lang]:
        if d in body.get(sec["education"], ""):
            bad(f"Education still carries the superseded dates '{d}'")
    teaching = body.get(sec["teaching"], "")
    tl = re.search(r"\]\(/assets/pdfs/" + re.escape(TEACHING_PDF) + r"\)(\{[^}]*\})?", teaching)
    if not tl:
        bad(f"Teaching lacks the link /assets/pdfs/{TEACHING_PDF}")
    else:
        if not re.search(r'aria-label="[^"]+"', tl.group(1) or ""):
            bad("the teaching-notes link lacks a non-empty aria-label")
        if TEACHING_LABEL[lang] not in teaching:
            bad(f"Teaching lacks the label '{TEACHING_LABEL[lang]}' next to the teaching-notes link")
    # Round 12: the fund is presented under Teaching and Mentoring as a student finance lab, with its QRT and LSEG links.
    if SIF_TEXT[lang] not in teaching:
        bad(f"Teaching and Mentoring lacks '{SIF_TEXT[lang]}'")
    for u in SERVICE_LINKS:
        if f"]({u})" not in teaching:
            bad(f"Teaching and Mentoring lacks the link {u}")
    refs = body.get(sec["references"], "")
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
    if DOUBLE_MAJOR[lang] not in body.get(sec["education"], ""):
        bad(f"Education lacks '{DOUBLE_MAJOR[lang]}'")
    if DOUBLE_MAJOR[lang] not in bio_block(home):
        bad("home .bio block lacks the double-major wording")
    for where, t in (("CV", text), ("home .bio", bio_block(home))):
        m = NOT_DUAL.search(t)
        if m:
            bad(f"{where} says '{m.group(0)}' (the Michigan record is one B.S. with two majors)")
    if not fails:
        rep.ok(10, f"{label}: {len(names)} sections in research-first order, job market paper first and labelled once, "
                   f"presentations line, research-collaboration entry, no consultant entry, owner dates, teaching-notes link "
                   f"labelled, Teaching and Mentoring with SIF/QRT/LSEG links, {len(cards)} referees with e-mail and profile, "
                   f"double-major wording in CV and bio")
    # The item-10 home check reads only the `.bio` block; the Path panel wording is reviewed by eye.


# -------------------------------------------------------------------------------------------------- main
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="CV checks (spec Part B 4.2)")
    ap.add_argument("--en-only", action="store_true")
    ap.add_argument("--rendered", type=Path, default=SITE / "_site", help="rendered site dir (item 2 aria-labels)")
    ap.add_argument("--rendered-zh", type=Path, default=None, help="rendered ZH cv.html (print_cv.sh scratch)")
    ap.add_argument("--no-network", action="store_true")
    ap.add_argument("--no-sync", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)

    rep = Report()
    en = read(EN_CV)
    zh = read(ZH_CV) if ZH_CV.exists() else ""
    if not a.en_only and not zh:
        rep.fail(2, f"{ZH_CV.relative_to(WEB)} is missing")
    print(f"check_cv: site/cv.qmd" + ("" if a.en_only else " and site/zh/cv.qmd") +
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
