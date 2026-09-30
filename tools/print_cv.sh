#!/usr/bin/env bash
# tools/print_cv.sh — print the CV pages to A4 PDF with headless Chrome (spec Part B §3).
#
#   tools/print_cv.sh en                   render the EN CV, print -> site/assets/pdfs/Mingyang_Liu_CV.pdf
#   tools/print_cv.sh zh                   render the held ZH CV, print -> _held/site/assets/pdfs/Mingyang_Liu_CV_ZH.pdf
#   tools/print_cv.sh all                  both
#   tools/print_cv.sh check <pdf> [en|zh]  run only the acceptance checks (§3.4) on an existing PDF
#
# Environment: PWS_VENV (default $HOME/.local/venvs/pws-web), QUARTO, CHROME (default the Google Chrome app),
#   SCRATCH (default the session scratchpad's print_cv/ when that folder exists, else $TMPDIR/print_cv),
#   PRINT_CV_OUT (a directory: when set, the finished PDFs and previews go THERE instead of site/ and _held/,
#   for a review print that must not touch the served folder), CHECK_CV_FLAGS (extra flags for check_cv.py,
#   e.g. --no-sync for a review print before the ZH commit exists; never used by the real print).
#
# Rule for every mode: rendering, printing, metadata writing and checking all happen under $SCRATCH/<lang>/.
# Nothing is written under site/ or _held/ until every check in §3.4 has passed; then ONE mv replaces the target.
# On failure the script leaves $SCRATCH/<lang>/Mingyang_Liu_CV[_ZH].failed.pdf, prints its path and exits 1.
# No tracked file is ever removed (only overwritten by the mv).
#
# Both languages are rendered from a scratch rsync copy of site/ (the held ZH page is copied into that copy;
# the EN page is rendered the same way so that the shared site/_site is never touched by a print), then the
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
  if [ -n "$pages" ] && [ "$pages" -le 3 ]; then echo "check 1: $pages pages"; else echo "check 1 FAILED: $pages pages (limit 3)"; bad=1; fi
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
         "Characteristic_Geometry_and_Portfolio_Choice_Slides.pdf", "Interpreting_Estimated_Pricing_Errors.pdf"]
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
print(f"check 5: {len(uris)} URI annotations; all 13 required present; no file:// URI")
PYEOF
  n="$(pdftotext "$pdf" - | grep -ciE "Nankai|Michigan China Forum|Executive Committee|南开|密歇根中国论坛|执行委员会|Qube|QRT" || true)"
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
  return "$bad"
}

# check 8: served-folder hygiene (also check_cv.py item 9).
check_folder() {
  local f name bad=0
  for f in site/assets/pdfs/*; do
    name="$(basename "$f")"
    case "$name" in ._*) continue ;; esac
    case "$name" in *.tmp*|*.failed*|print.pdf) echo "check 8: intermediate file $name in site/assets/pdfs/"; bad=1 ;; esac
    case "$name" in
      Characteristic_Libraries_and_Portfolio_Decisions_SSRN_v2.pdf|Characteristic_Space_Metrics_Main.pdf|\
      Characteristic_Space_Metrics_Online_Supplement.pdf|Geometric_Framework_SSRN_7013178.pdf|\
      Characteristic_Geometry_and_Portfolio_Choice_Slides.pdf|Interpreting_Estimated_Pricing_Errors.pdf|\
      Characteristic_Space_Metrics_Slides.pdf|Mingyang_Liu_CV.pdf) ;;
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

set_meta() {  # set_meta <in.pdf> <out.pdf> <en|zh>
  "$PY" - "$1" "$2" "$3" <<'PYEOF'
import sys
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject
src, dst, lang = sys.argv[1:4]
w = PdfWriter(clone_from=PdfReader(src))
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

render_project() {  # render_project <en|zh>: scratch copy of site/, held page copied in for zh, single-page render
  local lang="$1" proj
  proj="$SCRATCH/$lang-project"
  say "render ($lang) in $proj"
  mkdir -p "$proj"
  rsync -a --delete --exclude _site --exclude .quarto --exclude '._*' site/ "$proj/"
  if [ "$lang" = zh ]; then
    cp _held/site/zh/cv.qmd "$proj/zh/cv.qmd"
    [ -f _held/site/assets/pdfs/Mingyang_Liu_CV_ZH.pdf ] && cp _held/site/assets/pdfs/Mingyang_Liu_CV_ZH.pdf "$proj/assets/pdfs/"
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
  else page="zh/cv.html"; base="$BASE_ZH"; name="Mingyang_Liu_CV_ZH.pdf"; target="_held/site/assets/pdfs/$name"; fi
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
    echo "review print: $final (PRINT_CV_OUT set; site/ and _held/ untouched)"
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
