#!/usr/bin/env bash
# Golden tests: diff mytools against real bedtools on the fixtures in data/.
#
# Usage: ./tests/run_golden.sh
#        MYTOOLS=/path/to/build ./tests/run_golden.sh
#
# bedtools is the oracle. If we differ from it, we are wrong -- see tests/README.md.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
DATA=$ROOT/data

# Default to the mytools in the repo root so the suite runs before any install;
# override with MYTOOLS= to test a different build.
MYTOOLS=${MYTOOLS:-$ROOT/mytools}

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
pass=0; fail=0

if ! command -v bedtools >/dev/null 2>&1; then
  echo "bedtools not found -- these tests need the oracle installed" >&2
  exit 2
fi
if [[ ! -x $MYTOOLS ]]; then
  echo "mytools not found or not executable: $MYTOOLS" >&2
  echo "build it, or set MYTOOLS=/path/to/mytools" >&2
  exit 2
fi

# merge requires sorted input, and a.bed/b.bed are deliberately unsorted.
bedtools sort -i "$DATA/a.bed" > "$tmp/a.sorted.bed"
bedtools sort -i "$DATA/b.bed" > "$tmp/b.sorted.bed"

report() {   # report <name> <got_rc> <want_rc>
  local name=$1 got_rc=$2 want_rc=$3
  if [[ $got_rc -ne $want_rc ]]; then
    echo "FAIL $name (exit $got_rc, bedtools gave $want_rc)"
    sed 's/^/      /' "$tmp/got.err" | head -3
    fail=$((fail + 1)); return
  fi
  if diff -q "$tmp/want" "$tmp/got" >/dev/null; then
    echo "ok   $name"; pass=$((pass + 1))
  else
    echo "FAIL $name"
    diff -u "$tmp/want" "$tmp/got" | sed 's/^/      /' | head -20
    fail=$((fail + 1))
  fi
}

# check <name> -- <args...>
#   runs "$MYTOOLS <args>" and "bedtools <args>", diffs stdout and exit codes.
check() {
  local name=$1; shift; shift        # drop the literal --
  "$MYTOOLS" "$@" > "$tmp/got"  2>"$tmp/got.err"; local got_rc=$?
  bedtools    "$@" > "$tmp/want" 2>/dev/null;     local want_rc=$?
  report "$name" "$got_rc" "$want_rc"
}

# check_stdin <name> <file> -- <args...>
#   same, with <file> piped in on stdin (the args should name "-" for that input).
check_stdin() {
  local name=$1 infile=$2; shift 3   # drop the literal --
  "$MYTOOLS" "$@" < "$infile" > "$tmp/got"  2>"$tmp/got.err"; local got_rc=$?
  bedtools    "$@" < "$infile" > "$tmp/want" 2>/dev/null;     local want_rc=$?
  report "$name" "$got_rc" "$want_rc"
}

# stderr is not part of the contract -- bedtools' wording is its own, so we never
# diff it. Exit codes and stdout are the contract.
#
# --version is not testable here: "bedtools --version" prints bedtools' own version.
# That one belongs in the unit tests.

# --- sort ------------------------------------------------------------------
# a.bed and b.bed are unsorted on purpose; genes.bed adds a third, larger file.
# chr17 sorting before chr7 (lexicographic) is the case to watch.
check       "sort a.bed"          -- sort -i "$DATA/a.bed"
check       "sort b.bed"          -- sort -i "$DATA/b.bed"
check       "sort genes.bed"      -- sort -i "$DATA/genes.bed"
check_stdin "sort stdin"          "$DATA/a.bed" -- sort -i -

# --- merge -----------------------------------------------------------------
# Input must be sorted. -d 0 is the default: bookended features DO merge at d=0
# even though they do not overlap, because the gap between them is 0.
# On sorted a.bed the oracle reports chr1 499 600 -- it expands the zero-length
# feature at 500 leftwards. That is bedtools' answer, so it is ours.
check       "merge a"             -- merge -i "$tmp/a.sorted.bed"
check       "merge a -d 0"        -- merge -d 0 -i "$tmp/a.sorted.bed"
check       "merge a -d 10"       -- merge -d 10 -i "$tmp/a.sorted.bed"
check       "merge a -d 100"      -- merge -d 100 -i "$tmp/a.sorted.bed"
check       "merge b"             -- merge -i "$tmp/b.sorted.bed"
check_stdin "merge stdin"         "$tmp/a.sorted.bed" -- merge -i -

# --- intersect -------------------------------------------------------------
# -u, -v and -wa are mutually exclusive. Swapping -a and -b is not symmetric,
# so both directions are worth pinning.
check       "intersect a b"       -- intersect -a "$DATA/a.bed" -b "$DATA/b.bed"
check       "intersect a b -u"    -- intersect -u  -a "$DATA/a.bed" -b "$DATA/b.bed"
check       "intersect a b -v"    -- intersect -v  -a "$DATA/a.bed" -b "$DATA/b.bed"
check       "intersect a b -wa"   -- intersect -wa -a "$DATA/a.bed" -b "$DATA/b.bed"
check       "intersect b a"       -- intersect -a "$DATA/b.bed" -b "$DATA/a.bed"
check       "intersect b a -v"    -- intersect -v -a "$DATA/b.bed" -b "$DATA/a.bed"
check_stdin "intersect stdin"     "$DATA/a.bed" -- intersect -a - -b "$DATA/b.bed"

# --- subtract --------------------------------------------------------------
# One -a feature can become two rows when a -b feature splits it. The oracle
# turns a01 (chr1 0-100) into chr1 50 99, not chr1 50 100 -- do not "fix" that.
check       "subtract a b"        -- subtract -a "$DATA/a.bed" -b "$DATA/b.bed"
check       "subtract b a"        -- subtract -a "$DATA/b.bed" -b "$DATA/a.bed"
check_stdin "subtract stdin"      "$DATA/a.bed" -- subtract -a - -b "$DATA/b.bed"

echo "---"
echo "$pass passed, $fail failed"
[[ $fail -eq 0 ]]
