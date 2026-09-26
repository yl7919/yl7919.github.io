#!/usr/bin/env bash
# tools/precommit.sh — run every local check before a commit (spec "Data pipeline and CI changes", D19).
#
#   tools/precommit.sh               full run; FAILS if /Volumes/Extreme P2 (the research sources) is absent
#   tools/precommit.sh --no-sources  skip build_data.py --check (the only step that reads the external volume)
#
# Steps, in order; the script stops at the first failure:
#   1. pytest pipeline/tests -q
#   2. pipeline/build_data.py --check          (committed JSON/Markdown/PNG match the sources)
#   3. quarto render site
#   4. site/tools/check_links.py               (links and rules (a)-(k))
#   5. site/tools/check_translations.py --strict
#   6. exhibit-4 migration diff: the OJS cells of site/_includes/_fig-portfolio-formation.qmd, normalised,
#      must equal the cells of the pre-migration site/explore/_exhibit4-block.qmd taken from git history.
#
# Python comes from $PWS_VENV (default $HOME/.local/venvs/pws-web), outside the exFAT volume.
set -euo pipefail

VOLUME="${PWS_VOLUME:-/Volumes/Extreme P2}"   # override only to test the absent-volume path
NO_SOURCES=0
for arg in "$@"; do
  case "$arg" in
    --no-sources) NO_SOURCES=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "precommit: unknown argument $arg" >&2; exit 2 ;;
  esac
done

WEB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PWS_VENV:-$HOME/.local/venvs/pws-web}"
PY="$VENV/bin/python"
PYTEST="$VENV/bin/pytest"
QUARTO="${QUARTO:-$(command -v quarto || echo /opt/homebrew/bin/quarto)}"
cd "$WEB"

step() { printf '\n== %s\n' "$*"; }
fail() { printf '\nprecommit: FAILED at: %s\n' "$*" >&2; exit 1; }

[ -x "$PY" ] || fail "no Python at $PY (set PWS_VENV)"
[ -x "$QUARTO" ] || fail "quarto not found"

if [ "$NO_SOURCES" -eq 0 ] && [ ! -d "$VOLUME" ]; then
  fail "$VOLUME is not mounted; plug in the drive, or pass --no-sources to skip build_data.py --check (D19: never skipped silently)"
fi

step "1/6 pytest pipeline/tests"
"$PYTEST" pipeline/tests -q || fail "pytest"

if [ "$NO_SOURCES" -eq 0 ]; then
  step "2/6 build_data.py --check"
  "$PY" pipeline/build_data.py --check || fail "build_data.py --check"
else
  step "2/6 build_data.py --check SKIPPED (--no-sources given)"
fi

step "3/6 quarto render site"
(cd site && "$QUARTO" render) || fail "quarto render"

step "4/6 check_links.py"
"$PY" site/tools/check_links.py || fail "check_links.py"

step "5/6 check_translations.py --strict"
"$PY" site/tools/check_translations.py --strict || fail "check_translations.py --strict"

step "6/6 exhibit-4 migration diff"
OLD_PATH="site/explore/_exhibit4-block.qmd"
NEW_PATH="site/_includes/_fig-portfolio-formation.qmd"
BASE="$(git log -1 --format=%H --diff-filter=AM -- "$OLD_PATH")"
[ -n "$BASE" ] || fail "exhibit-4 diff: no commit in history adds or modifies $OLD_PATH"

# Keep only the ```{ojs} cells, then normalise what the migration was allowed to change (spec "Migration",
# item 1): the pf_ prefix (and the old cell `pf`, renamed pf_data), the FileAttachment path, every label
# string (Inputs labels, <th> headers), palette keys, font family and size, the added aria lines, and the
# failed-load notice. Also allowed: the ablation view's initial sample (618 -> 594 months, owner-approved page
# design, commit 1a48378). Finally strip whitespace and put one comma-separated token per line, so a
# reflowed argument list does not count as a change. Anything else is a change to the computing cells.
ojs_cells() { awk '/^```\{ojs\}/{on=1; next} on && /^```/{on=0; next} on'; }
normalise() {
  perl -pe '
    s/\bpf_//g; s/\bpf\b/data/g;
    s{FileAttachment\("(\.\./|/)data/}{FileAttachment("DATA/}g;
    s/label: (t\("[a-z_]+"\)|"[^"]*")/label: L/g;
    s{<th>[^<]*</th>}{<th>H</th>}g;
    s/palette\.[a-z_]+/palette.K/g;
    s/fontFamily: "[^"]*"/fontFamily: F/g; s/, fontSize: 12//g;
    s/style: \{ fontFamily: F \},?//g;
    $_ = "" if /^\s*aria(Label|Description):/;
    s/^(loadFailed = data === null \? html`).*(` : html``)$/$1NOTICE$2/;
    s/(Inputs\.radio\(\[618, 594, 206\].*\?\? )(618|594)\b/$1SAMPLE/;
  ' | tr -d ' \t' | tr ',' '\n' | grep -v '^$'
}
OLD_N="$(mktemp)"; NEW_N="$(mktemp)"
trap 'rm -f "$OLD_N" "$NEW_N"' EXIT
git show "$BASE:$OLD_PATH" | ojs_cells | normalise > "$OLD_N"
ojs_cells < "$NEW_PATH" | normalise > "$NEW_N"
[ -s "$NEW_N" ] || fail "exhibit-4 diff: no OJS cells found in $NEW_PATH"
if ! diff -u "$OLD_N" "$NEW_N"; then
  fail "exhibit-4 diff: computing cells differ from $OLD_PATH at ${BASE:0:7} (see diff above)"
fi
echo "exhibit-4 cells match ${OLD_PATH} at ${BASE:0:7} after normalisation ($(wc -l < "$NEW_N" | tr -d ' ') tokens)"

printf '\nprecommit: all checks passed%s\n' "$([ "$NO_SOURCES" -eq 1 ] && echo ' (build_data.py --check skipped: --no-sources)')"
