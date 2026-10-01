#!/usr/bin/env bash
# tools/print_cv.sh — print the CV pages to A4 PDF with headless Chrome (spec Part B §3).
#
#   tools/print_cv.sh en                   render the EN CV, print -> site/assets/pdfs/Mingyang_Liu_CV.pdf
#   tools/print_cv.sh zh                   render the ZH CV, print -> site/assets/pdfs/Mingyang_Liu_CV_ZH.pdf (public since 2026-09-30)
#   tools/print_cv.sh all                  both
#   tools/print_cv.sh check <pdf> [en|zh]  run only the acceptance checks (§3.4) on an existing PDF
#
# Environment: PWS_VENV (default $HOME/.local/venvs/pws-web), QUARTO, CHROME (default the Google Chrome app),
#   SCRATCH (default the session scratchpad's print_cv/ when that folder exists, else $TMPDIR/print_cv),
#   PRINT_CV_OUT (a directory: when set, the finished PDFs and previews go THERE instead of site/,
#   for a review print that must not touch the served folder), CHECK_CV_FLAGS (extra flags for check_cv.py,
#   e.g. --no-network, or --no-sync before the controller commits site/cv.qmd and sets the ZH translated-from).
#
# Rule for every mode: rendering, printing, metadata writing and checking all happen under $SCRATCH/<lang>/.
# Nothing is written under site/ until every check in §3.4 has passed; then ONE mv replaces the target.
# On failure the script leaves $SCRATCH/<lang>/Mingyang_Liu_CV[_ZH].failed.pdf, prints its path and exits 1.
# No tracked file is ever removed (only overwritten by the mv).
#
# Both languages are rendered from a scratch rsync copy of site/ (site/cv.qmd and site/zh/cv.qmd; the shared
# site/_site is never touched by a print), then the
# rendered page's <a href> targets are made absolute (tools/cv_abs_links.py) so the PDF's link annotations
# point at https://mingyangliu.org/... and never at file://.
set -euo pipefail

usage() { sed -n '2,20p' "$0"; exit 2; }
MODE="${1:-}"
[ -n "$MODE" ] || usage

WEB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PWS_VENV:-$HOME/.local/venvs/pws-web}"
PY="$VENV/bin/python"
QUARTO="${QUARTO:-$(command -v quarto || echo /opt/homebrew/bin/quarto)}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
SESSION_SCRATCH="/private/tmp/claude-501/-Volumes-Extreme-P2-Claude-Project-PWS/c3ef5738-a615-44f5-9bdb-c34ee1da2f90/scratchpad"
if [ -z "${SCRATCH:-}" ]; then
  if [ -d "$SESSION_SCRATCH" ]; then SCRATCH="$SESSION_SCRATCH/print_cv"; else SCRATCH="${TMPDIR:-/tmp}/print_cv"; fi
fi
BASE_EN="https://mingyangliu.org/cv.html"
BASE_ZH="https://mingyangliu.org/zh/cv.html"
OUT_DIR="${PRINT_CV_OUT:-}"
export PATH="/opt/homebrew/bin:$PATH"
cd "$WEB"

say()  { printf '\n== %s\n' "$*"; }
die()  { printf '\nprint_cv: FAILED: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 not found"; }

[ -x "$PY" ] || die "no Python at $PY (set PWS_VENV)"
for t in pdfinfo pdffonts pdftotext pdftoppm rsync; do need "$t"; done
"$PY" -c "import pypdf" 2>/dev/null || die "pypdf missing in $VENV"

# ------------------------------------------------------------------------------------------ §3.4 checks
# check_pdf <pdf> <en|zh>: every check runs and reports; returns 1 if any failed.
check_pdf() {
  local pdf="$1" lang="$2" pages n bad=0 i text t
  say "checks on $pdf ($lang)"
  pages="$(pdfinfo "$pdf" | awk '/^Pages:/{print $2}')"
  # 2026-09-30 (research-first CV with Service and References): 3 pages preferred, 4 accepted provided no page
  # ends on a section heading (check 1b).
  if [ -n "$pages" ] && [ "$pages" -le 4 ]; then echo "check 1: $pages pages (limit 4; 3 preferred)"; else echo "check 1 FAILED: $pages pages (limit 4)"; bad=1; fi
  local heads last orphan=0
  if [ "$lang" = en ]; then
    heads="Research Fields|Education|Research|Working Papers|PhD Thesis|Positions|Research Experience|Teaching|Scholarships and Honours|Service|Skills and Languages|References"
  else
    heads="研究方向.*|教育背景.*|学术论文.*|工作论文.*|博士学位论文.*|工作经历.*|科研经历.*|教学经历.*|奖学金与荣誉.*|校内外服务.*|专业技能与语言.*|推荐人.*"
  fi
  for i in $(seq 1 $(( ${pages:-1} - 1 ))); do
    last="$(pdftotext -layout -f "$i" -l "$i" "$pdf" - | grep -vE "Page\s*[0-9]+\s*of|第\s*[0-9]+\s*页" | grep -v '^[[:space:]]*$' | tail -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    if printf '%s\n' "$last" | grep -qxE "$heads"; then echo "check 1b FAILED: page $i ends on the heading '$last'"; orphan=1; fi
  done
  if [ "$orphan" -eq 0 ]; then echo "check 1b: no page ends on a section heading"; else bad=1; fi
  n="$(pdffonts "$pdf" | grep -ci italic || true)"
  if [ "$n" -eq 0 ]; then echo "check 2: no italic font"; else echo "check 2 FAILED: $n italic/oblique font subset(s) embedded"; pdffonts "$pdf" | grep -i italic | head -3; bad=1; fi
  if [ "$lang" = en ]; then
    # pdftotext breaks the large heading into one word per line; collapse whitespace before matching.
    if pdftotext -l 1 "$pdf" - | tr -s '[:space:]' ' ' | grep -q "Mingyang (Yang) Liu"; then echo "check 3: name on page 1"; else echo "check 3 FAILED: page 1 lacks 'Mingyang (Yang) Liu'"; bad=1; fi
  else
    if pdftotext -l 1 "$pdf" - | tr -s '[:space:]' ' ' | grep -q "刘明杨"; then echo "check 3: name on page 1"; else echo "check 3 FAILED: page 1 lacks 刘明杨"; bad=1; fi
  fi
  local footer_ok=1
  for i in $(seq 1 "${pages:-0}"); do
    if [ "$lang" = en ]; then
      pdftotext -f "$i" -l "$i" "$pdf" - | grep -qE "Page\s*$i\s*of\s*[0-9]+" || { echo "check 4 FAILED: footer 'Page $i of N' not found on page $i"; footer_ok=0; }
    else
      pdftotext -f "$i" -l "$i" "$pdf" - | grep -qE "第\s*$i\s*页\s*/\s*共\s*[0-9]+\s*页" || { echo "check 4 FAILED: footer '第 $i 页 / 共 N 页' not found on page $i"; footer_ok=0; }
    fi
  done
  if [ "$footer_ok" -eq 1 ]; then echo "check 4: footer on every page"; else bad=1; fi
  "$PY" - "$pdf" "$lang" <<'PYEOF' || bad=1
import sys
from pypdf import PdfReader
pdf, lang = sys.argv[1], sys.argv[2]
uris = set()
for page in PdfReader(pdf).pages:
    for a in page.get("/Annots") or []:
        a = a.get_object()
        act = a.get("/A")
        if act is not None and "/URI" in act:
            uris.add(str(act["/URI"]))
base = "https://mingyangliu.org"
files = ["Characteristic_Libraries_and_Portfolio_Decisions_SSRN_v2.pdf", "Characteristic_Space_Metrics_Main.pdf",
         "Characteristic_Space_Metrics_Online_Supplement.pdf", "Geometric_Framework_SSRN_7013178.pdf",
         "Characteristic_Geometry_and_Portfolio_Choice.pdf", "Characteristic_Geometry_and_Portfolio_Choice_Slides.pdf",
         "Interpreting_Estimated_Pricing_Errors.pdf"]
slugs = ["characteristic-libraries", "characteristic-space-metrics", "geometric-framework",
         "characteristic-geometry", "interpreting-pricing-errors"]
pre = "/zh/research/" if lang == "zh" else "/research/"
required = [f"{base}/assets/pdfs/{f}" for f in files] + [f"{base}{pre}{s}.html" for s in slugs] + \
           ["https://doi.org/10.2139/ssrn.7013178", "https://doi.org/10.2139/ssrn.7445120"]
missing = [u for u in required if u not in uris]
local = sorted(u for u in uris if u.startswith("file:"))
bad = [u for u in uris if not (u.startswith("https://") or u.startswith("http://") or u.startswith("mailto:"))]
if missing or local or bad:
    for u in missing: print(f"check 5 FAILED: missing link annotation {u}")
    for u in local: print(f"check 5 FAILED: file:// annotation {u}")
    for u in bad: print(f"check 5 FAILED: unexpected URI scheme {u}")
    sys.exit(1)
print(f"check 5: {len(uris)} URI annotations; all {len(required)} required present; no file:// URI")
PYEOF
  # Withheld since 2026-09-30: only the Nankai–Columbia exchange and Michigan China Forum items (the SIF chair
  # block, with its QRT and LSEG names, is public again at the owner's request).
  n="$(pdftotext "$pdf" - | grep -ciE "Nankai|Michigan China Forum|南开|密歇根中国论坛" || true)"
  if [ "$n" -eq 0 ]; then echo "check 6: no withheld strings"; else echo "check 6 FAILED: $n line(s) with withheld Service strings"; bad=1; fi
  n="$(pdftotext "$pdf" - | grep -ciE "\+44|1992|SW7|Princes Gate|汉族|出生" || true)"
  if [ "$n" -eq 0 ]; then echo "check 7: no private data"; else echo "check 7 FAILED: $n line(s) with private data"; bad=1; fi
  # 4.3: the five paper titles extract verbatim (whitespace collapsed; the ZH page prints them in parentheses).
  text="$(pdftotext "$pdf" - | tr '\n' ' ' | tr -s ' ')"
  local titles_ok=1
  for t in "Characteristic Libraries and Portfolio Decisions" \
           "Characteristic-Space Metrics in Factor Models: Identification and Inference" \
           "A Geometric Framework for Identification in Characteristic-Based Factor Models" \
           "Characteristic Geometry and Portfolio Choice" \
           "Interpreting Estimated Pricing Errors: Evidence from Characteristic-Based Return Forecasts"; do
    case "$text" in *"$t"*) ;; *) echo "check titles FAILED: '$t' not extracted verbatim"; titles_ok=0 ;; esac
  done
  if [ "$titles_ok" -eq 1 ]; then echo "check titles: five paper titles extract verbatim"; else bad=1; fi
  # check 9: the text layer as a non-normalising extractor (pypdf; also PDFBox, pdfminer) reads it has no CJK radical
  # code points (U+2E80-U+2FDF); set_meta's ToUnicode remap removes the ones Skia writes for PingFang glyphs.
  "$PY" - "$pdf" <<'PYEOF' || bad=1
import sys
from pypdf import PdfReader
text = "".join(p.extract_text() or "" for p in PdfReader(sys.argv[1]).pages)
n = sum(0x2E80 <= ord(c) <= 0x2FDF for c in text)
if n:
    print(f"check 9 FAILED: {n} CJK radical code point(s) in the text layer (pypdf), e.g. {sorted({c for c in text if 0x2E80 <= ord(c) <= 0x2FDF})[:8]}")
    sys.exit(1)
print("check 9: no CJK radical code points in the text layer (pypdf extraction)")
PYEOF
  return "$bad"
}

# check 8: served-folder hygiene (also check_cv.py item 9).
check_folder() {
  local f name bad=0
  for f in site/assets/pdfs/*; do
    [ -d "$f" ] && continue   # subfolders (e.g. pdfs/blog/) belong to other units
    name="$(basename "$f")"
    case "$name" in ._*) continue ;; esac
    case "$name" in *.tmp*|*.failed*|print.pdf) echo "check 8: intermediate file $name in site/assets/pdfs/"; bad=1 ;; esac
    case "$name" in
      Characteristic_Libraries_and_Portfolio_Decisions_SSRN_v2.pdf|Characteristic_Space_Metrics_Main.pdf|\
      Characteristic_Space_Metrics_Online_Supplement.pdf|Geometric_Framework_SSRN_7013178.pdf|\
      Characteristic_Geometry_and_Portfolio_Choice.pdf|Characteristic_Geometry_and_Portfolio_Choice_Slides.pdf|\
      Interpreting_Estimated_Pricing_Errors.pdf|Characteristic_Space_Metrics_Slides.pdf|Mingyang_Liu_CV.pdf|\
      Mingyang_Liu_CV_ZH.pdf) ;;
      *) grep -rqF --include='*.qmd' "$name" site || { echo "check 8: $name is neither a served PDF nor referenced from a .qmd"; bad=1; } ;;
    esac
  done
  [ "$bad" -eq 0 ] || return 1
  echo "check 8: site/assets/pdfs/ hygiene ok"
}

# ------------------------------------------------------------------------------------------- printing
print_pdf() {  # print_pdf <file-url> <out.pdf>
  local url="$1" out="$2" prof pid i
  prof="$SCRATCH/chrome-profile"
  mkdir -p "$prof"; rm -f "$out"
  [ -x "$CHROME" ] || die "Chrome not found at $CHROME (set CHROME)"
  "$CHROME" --headless=new --disable-gpu --user-data-dir="$prof" --no-first-run \
    --no-pdf-header-footer --run-all-compositor-stages-before-draw \
    --virtual-time-budget=4000 --print-to-pdf="$out" "$url" >"$SCRATCH/chrome.log" 2>&1 &
  pid=$!
  for i in $(seq 1 60); do
    sleep 1
    [ -s "$out" ] && { sleep 2; break; }
  done
  kill "$pid" 2>/dev/null || true
  pkill -f "user-data-dir=$prof" 2>/dev/null || true
  [ -s "$out" ] || die "Chrome wrote no PDF for $url (see $SCRATCH/chrome.log)"
}

set_meta() {  # set_meta <in.pdf> <out.pdf> <en|zh>: ToUnicode remap (check 9), then metadata
  "$PY" - "$1" "$2" "$3" <<'PYEOF'
import re, sys, unicodedata
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject
src, dst, lang = sys.argv[1:4]
w = PdfWriter(clone_from=PdfReader(src))

# Text layer. Skia names a glyph that PingFang SC shares between a CJK radical and a unified ideograph by the
# radical's code point (金 -> U+2FA6, 页 -> U+2EDA). The page looks right and poppler/PDFKit normalise on
# extraction, but pypdf, PDFBox/Tika and pdfminer (ATS parsers, copy and search in some viewers) return the radical.
# Rewrite the destination strings of every ToUnicode CMap reachable from the pages (their fonts, Form XObjects,
# patterns and Type 3 glyph resources) to the unified ideographs. Source codes are never touched. check 9 verifies.
SUPP = {0x2E9F: 0x6BCD, 0x2EA0: 0x6C11, 0x2EC4: 0x897F, 0x2EC5: 0x89C1, 0x2EC6: 0x89D2, 0x2EC9: 0x8D1D, 0x2ECB: 0x8F66,
        0x2ED3: 0x957F, 0x2ED4: 0x95E8, 0x2ED8: 0x9752, 0x2ED9: 0x97E6, 0x2EDA: 0x9875, 0x2EDB: 0x98CE, 0x2EDC: 0x98DE,
        0x2EDD: 0x98DF, 0x2EE2: 0x9A6C, 0x2EE3: 0x9AA8, 0x2EE4: 0x9B3C, 0x2EE5: 0x9C7C, 0x2EE6: 0x9E1F, 0x2EE8: 0x9EA6,
        0x2EE9: 0x9EC4, 0x2EEC: 0x9F50, 0x2EEE: 0x9F7F, 0x2EF0: 0x9F99, 0x2EF3: 0x9F9F}   # CJK Radicals Supplement
TOK = re.compile(r"<([0-9A-Fa-f]*)>")
RANGE = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])")
remapped = 0

def fix_cp(cp):
    if 0x2F00 <= cp <= 0x2FD5:                     # Kangxi radicals: NFKC gives the unified ideograph
        return ord(unicodedata.normalize("NFKC", chr(cp)))
    return SUPP.get(cp, cp)

def fix_dst(h):  # a destination string (UTF-16BE code units, hex); unchanged unless a unit is a radical
    global remapped
    if not h or len(h) % 4:
        return h
    units = [int(h[i:i + 4], 16) for i in range(0, len(h), 4)]
    new = [fix_cp(u) for u in units]
    if new == units:
        return h
    remapped += 1
    return "".join(f"{u:04X}" for u in new)

def fix_bfchar(body):  # tokens alternate: source code, destination string
    k = -1
    def sub(m):
        nonlocal k
        k += 1
        return m.group(0) if k % 2 == 0 else f"<{fix_dst(m.group(1))}>"
    return TOK.sub(sub, body)

def fix_bfrange(body):  # <lo> <hi> <dst> (dst incremented per code) or <lo> <hi> [<dst> ...]
    def sub(m):
        global remapped
        lo, hi, d = int(m.group(1), 16), int(m.group(2), 16), m.group(3)
        if d.startswith("["):
            return f"<{m.group(1)}> <{m.group(2)}> " + TOK.sub(lambda t: f"<{fix_dst(t.group(1))}>", d)
        h = d[1:-1]
        if len(h) != 4:
            return m.group(0)
        vals = [int(h, 16) + i for i in range(hi - lo + 1)]
        if all(fix_cp(v) == v for v in vals):
            return m.group(0)
        remapped += sum(fix_cp(v) != v for v in vals)
        return f"<{m.group(1)}> <{m.group(2)}> [" + " ".join(f"<{fix_cp(v):04X}>" for v in vals) + "]"
    return RANGE.sub(sub, body)

def fonts_of(res, seen):
    res = res.get_object() if res is not None else None
    if not res or id(res) in seen:
        return
    seen.add(id(res))
    for f in (res.get("/Font") or {}).values():
        f = f.get_object()
        yield f
        if f.get("/Subtype") == "/Type3":
            yield from fonts_of(f.get("/Resources"), seen)
    for kind in ("/XObject", "/Pattern"):
        for x in (res.get(kind) or {}).values():
            yield from fonts_of(x.get_object().get("/Resources"), seen)

done, seen, cmaps = set(), set(), 0
for page in w.pages:
    for font in fonts_of(page.get("/Resources"), seen):
        tu = font.get("/ToUnicode")
        if tu is None or id(tu.get_object()) in done:
            continue
        s = tu.get_object()
        done.add(id(s))
        old = s.get_data().decode("latin-1")
        new = re.sub(r"(beginbfchar)(.*?)(endbfchar)", lambda m: m.group(1) + fix_bfchar(m.group(2)) + m.group(3),
                     old, flags=re.S)
        new = re.sub(r"(beginbfrange)(.*?)(endbfrange)", lambda m: m.group(1) + fix_bfrange(m.group(2)) + m.group(3),
                     new, flags=re.S)
        cmaps += 1
        if new != old:
            s.set_data(new.encode("latin-1"))
print(f"ToUnicode: {cmaps} CMaps read, {remapped} radical destination(s) remapped to unified ideographs")

if lang == "en":
    meta = {"/Title": "Mingyang Liu, Curriculum Vitae", "/Author": "Mingyang Liu", "/Subject": "Curriculum vitae"}
    code = "en-GB"
else:
    meta = {"/Title": "刘明杨 简历 / Mingyang Liu, Curriculum Vitae (Chinese)", "/Author": "Mingyang Liu",
            "/Subject": "Curriculum vitae"}
    code = "zh-CN"
w.add_metadata(meta)
w._root_object[NameObject("/Lang")] = TextStringObject(code)
with open(dst, "wb") as f:
    w.write(f)
print(f"metadata: Title={meta['/Title']!r} Lang={code}")
PYEOF
}

render_project() {  # render_project <en|zh>: scratch copy of site/, single-page render
  local lang="$1" proj
  proj="$SCRATCH/$lang-project"
  say "render ($lang) in $proj"
  mkdir -p "$proj"
  rsync -a --delete --exclude _site --exclude .quarto --exclude '._*' site/ "$proj/"
  if [ "$lang" = zh ]; then
    [ -f site/zh/cv.qmd ] || die "site/zh/cv.qmd missing"
    (cd "$proj" && "$QUARTO" render zh/cv.qmd 2>&1 | tail -5) || die "quarto render zh/cv.qmd"
    [ -f "$proj/_site/zh/cv.html" ] || die "render produced no _site/zh/cv.html"
  else
    (cd "$proj" && "$QUARTO" render cv.qmd 2>&1 | tail -5) || die "quarto render cv.qmd"
    [ -f "$proj/_site/cv.html" ] || die "render produced no _site/cv.html"
  fi
}

do_lang() {  # do_lang <en|zh>
  local lang="$1" proj work page base name target final
  proj="$SCRATCH/$lang-project"; work="$SCRATCH/$lang"
  if [ "$lang" = en ]; then page="cv.html"; base="$BASE_EN"; name="Mingyang_Liu_CV.pdf"; target="site/assets/pdfs/$name"
  else page="zh/cv.html"; base="$BASE_ZH"; name="Mingyang_Liu_CV_ZH.pdf"; target="site/assets/pdfs/$name"; fi
  mkdir -p "$work"
  render_project "$lang"

  say "check_cv.py before printing"
  if [ "$lang" = en ]; then
    # shellcheck disable=SC2086
    "$PY" tools/check_cv.py --en-only --rendered "$proj/_site" ${CHECK_CV_FLAGS:-} || die "check_cv.py"
  else
    # shellcheck disable=SC2086
    "$PY" tools/check_cv.py --rendered "$SCRATCH/en-project/_site" --rendered-zh "$proj/_site/zh/cv.html" ${CHECK_CV_FLAGS:-} || die "check_cv.py"
  fi

  say "absolute links and print ($lang)"
  rsync -a --delete "$proj/_site/" "$work/_site/"
  "$PY" tools/cv_abs_links.py "$work/_site/$page" "$base"
  print_pdf "file://$work/_site/$page" "$work/print.pdf"
  set_meta "$work/print.pdf" "$work/$name" "$lang"
  rm -f "$work/print.pdf"

  if ! check_pdf "$work/$name" "$lang"; then
    mv "$work/$name" "$work/${name%.pdf}.failed.pdf"
    die "checks failed; the PDF is kept at $work/${name%.pdf}.failed.pdf"
  fi
  rm -f "$work"/page-*.png
  pdftoppm -r 90 -png "$work/$name" "$work/page"
  if [ -n "$OUT_DIR" ]; then
    mkdir -p "$OUT_DIR"; final="$OUT_DIR/$name"
    mv "$work/$name" "$final"; for f in "$work"/page-*.png; do cp "$f" "$OUT_DIR/$lang-$(basename "$f")"; done
    echo "review print: $final (PRINT_CV_OUT set; site/ untouched)"
  else
    final="$target"
    mv "$work/$name" "$final"
    check_folder || die "folder hygiene after the move"
    echo "printed: $final"
  fi
  echo "previews: $work/page-*.png"
}

case "$MODE" in
  en)  do_lang en ;;
  zh)  do_lang zh ;;
  all) do_lang en; do_lang zh ;;
  check)
    PDF="${2:-}"; LANG_="${3:-en}"
    [ -f "$PDF" ] || usage
    check_pdf "$PDF" "$LANG_" && check_folder && echo "print_cv check: all passed" ;;
  *) usage ;;
esac
