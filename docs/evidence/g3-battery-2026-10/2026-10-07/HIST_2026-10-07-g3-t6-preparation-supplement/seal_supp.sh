#!/bin/bash
# Seal the supplement of 2026-10-07 to the S4 preparation (WSL): the recorder's emergency cleanup with its partial
# capture kept inside the session's package. The sealed preparation package is only READ (its SHA256SUMS verified
# before and after). Copies the supplement's files, sweeps them for the values of the secret variables of
# ~/egw-tcg/.env (names only are printed) and for private-key headers, writes SHA256SUMS. Never overwrites a package.
# Usage: seal_supp.sh <supplement dir> <package dir> <README file>
# Exit: 0 sealed; 1 a STOP after the copy began (left unsealed); 2 refused, nothing created.
set -u
SRC=${1:?} PKG=${2:?} README=${3:?}
PREP_PKG="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation"
PREP_SEAL=34715555f87e7ad3e8f48fe7cc847425b08c65276c82994dd4ea2dd065baafd4
ENVF=$HOME/egw-tcg/.env
refuse() { echo "STOP: $* - nothing was created"; exit 2; }
[ ! -e "$PKG" ] || refuse "$PKG exists - never overwritten"
case $(basename "$PKG") in HIST_2026-10-07-g3-t6-preparation-supplement | HIST_2026-10-07-g3-t6-preparation-supplement-attempt[0-9][0-9]) ;;
    *) refuse "the package must be named HIST_2026-10-07-g3-t6-preparation-supplement[-attemptNN]" ;; esac
for f in ops/g3_recorder_cleanup.sh g3_battery.README.md operator-procedure.md base/g3_battery.README.md \
    base/operator-procedure.md bench/bsupp_run.sh bench/bsupp_setup.sh bench/make_bsupp.py bench/make_bsupp_setup.py \
    bench/record fixes-record/fix_docs_supp.py seal_supp.sh; do
    [ -e "$SRC/$f" ] || refuse "$SRC/$f is missing"
done
[ -f "$README" ] || refuse "$README is missing"
cmp -s "$0" "$SRC/seal_supp.sh" || refuse "the sealing script being run is not $SRC/seal_supp.sh"
got=$(sha256sum "$PREP_PKG/SHA256SUMS" | cut -d' ' -f1)
[ "$got" = "$PREP_SEAL" ] || refuse "the sealed preparation's SHA256SUMS is $got, not $PREP_SEAL"
(cd "$PREP_PKG" && sha256sum -c --quiet SHA256SUMS) || refuse "the sealed preparation package does not verify"
echo "the sealed preparation package verifies ($(wc -l < "$PREP_PKG/SHA256SUMS") files, seal ${PREP_SEAL:0:12}): it is not changed"
[ -r "$ENVF" ] || refuse "$ENVF could not be read: the secret sweep cannot be made"
bad=$(find "$SRC/bench/record" -regextype posix-extended -regex '.*/[0-9]{8}T[0-9]{6}Z_[A-Za-z0-9-]+(_[A-Za-z0-9-]+)*_attempt[0-9]{2,}' -print)
[ -z "$bad" ] || refuse "the supplement holds names the export tool numbers attempts by: $bad"

mkdir -p "$PKG/ops" "$PKG/bench" "$PKG/verification/diffs" || exit 2
cp "$SRC/ops/g3_recorder_cleanup.sh" "$PKG/ops/" || exit 1
cp "$SRC/g3_battery.README.md" "$SRC/operator-procedure.md" "$PKG/" || exit 1
cp "$SRC"/bench/bsupp_run.sh "$SRC"/bench/bsupp_setup.sh "$SRC"/bench/make_bsupp.py "$SRC"/bench/make_bsupp_setup.py "$PKG/bench/" || exit 1
cp -r "$SRC/bench/record" "$PKG/bench/record" || exit 1
cp -r "$SRC/fixes-record" "$PKG/fixes-record" || exit 1
cp "$SRC/seal_supp.sh" "$PKG/" || exit 1
cp "$README" "$PKG/README.md" || exit 1
for f in g3_battery.README.md operator-procedure.md; do
    diff -u "$SRC/base/$f" "$SRC/$f" > "$PKG/verification/diffs/$f.diff"
    [ $? -le 1 ] || exit 1
done
# the secret sweep: the VALUES of the secret variables (never printed), and private-key headers
while IFS= read -r line; do
    name=${line%%=*}; value=${line#*=}; value=${value%\"}; value=${value#\"}
    case $name in *PASS* | *SECRET* | *TOKEN* | *KEY* | *CREDENTIAL*) ;; *) continue ;; esac
    [ -n "$value" ] || continue
    n=$(grep -rlF -- "$value" "$PKG" | wc -l)
    echo "secret sweep: $name -> $n file(s)"
    [ "$n" -eq 0 ] || { echo "STOP: a secret value was found in the supplement: left unsealed"; exit 1; }
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENVF")
n=$(grep -rlE -- '-----BEGIN [A-Z ]*PRIVATE KEY-----' "$PKG" | grep -vc '/seal_supp\.sh$')
echo "secret sweep: PEM private-key headers -> $n file(s)"
[ "$n" -eq 0 ] || { echo "STOP: a private-key header was found: left unsealed"; exit 1; }
( cd "$PKG" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS ) || exit 1
(cd "$PREP_PKG" && sha256sum -c --quiet SHA256SUMS) || { echo "STOP: the sealed preparation package no longer verifies"; exit 1; }
echo "sealed $(wc -l < "$PKG/SHA256SUMS") files; seal $(sha256sum "$PKG/SHA256SUMS" | cut -c1-12); the preparation package still verifies"
