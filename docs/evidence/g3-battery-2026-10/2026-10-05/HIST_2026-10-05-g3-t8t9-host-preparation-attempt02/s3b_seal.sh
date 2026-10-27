#!/bin/bash
# Seal the minimal preparation of S3's second opening (authorisation of 2026-10-05) as a package of
# its own beside the first preparation, which is not touched. Never overwrites; copies, sweeps for
# secret values (names only are printed, values never reach a command line) and PEM private-key
# headers, then writes README.md and SHA256SUMS.
# Usage (WSL): s3b_seal.sh <s3bprep folder> <package dir: .../<UTC date>/HIST_<UTC date>-g3-t8t9-host-preparation-attempt02>
set -u
SRC=${1:?usage: s3b_seal.sh <s3bprep folder> <package dir>}
PKG=${2:?usage: s3b_seal.sh <s3bprep folder> <package dir>}
ENVF=$HOME/egw-tcg/.env
refuse() { echo "STOP: $* - nothing was created"; exit 2; }
[ ! -e "$PKG" ] || { echo "STOP: $PKG exists - never overwritten"; exit 2; }
B=$(basename "$PKG"); D=$(basename "$(dirname "$PKG")")
[ "$B" = "HIST_$D-g3-t8t9-host-preparation-attempt02" ] || refuse "the package must be named HIST_<its date folder>-g3-t8t9-host-preparation-attempt02, not $B under $D"
for f in g3_battery.sh g3_battery.README.md operator-procedure.md s3b_preflight_exception.py s3b_recheck.sh s3b_seal.sh \
         rows/rows.manifest.json record/console.txt bench-notes.md ops/g3_go.sh ops/g3_wait.sh ops/seal_ops.sh ops/seal_ops_finish.sh; do
    [ -f "$SRC/$f" ] || refuse "$SRC/$f is missing"
done
[ -d "$SRC/bench/record" ] || refuse "$SRC/bench/record is missing"
grep -q '^outcome=checked ' "$SRC/record/console.txt" || refuse "the recheck's record does not end outcome=checked"
[ -r "$ENVF" ] || refuse "$ENVF could not be read: the secret sweep cannot be made"

mkdir -p "$PKG/verification/diffs" "$PKG/ops" || exit 2
cp "$SRC/g3_battery.sh" "$SRC/g3_battery.README.md" "$SRC/operator-procedure.md" "$SRC/s3b_preflight_exception.py" \
   "$SRC/s3b_recheck.sh" "$SRC/s3b_seal.sh" "$PKG/" || exit 1
cp -r "$SRC/rows" "$PKG/rows" && cp -r "$SRC/record" "$PKG/recheck-record" && cp -r "$SRC/bench" "$PKG/bench" || exit 1
cp "$SRC/ops/g3_go.sh" "$SRC/ops/g3_wait.sh" "$SRC/ops/seal_ops.sh" "$SRC/ops/seal_ops_finish.sh" "$PKG/ops/" || exit 1
cp "$SRC/bench-notes.md" "$PKG/verification/" || exit 1
for f in g3_battery.sh g3_battery.README.md operator-procedure.md ops/g3_wait.sh ops/seal_ops.sh ops/seal_ops_finish.sh; do
    diff -u --label "first-preparation/$f" --label "$f" "$SRC/base/$f" "$SRC/$f" > "$PKG/verification/diffs/$(echo "$f" | tr / _).diff"
    [ $? -le 1 ] || { echo "STOP: diff failed on $f"; exit 1; }
done

# the sweep: each secret-named variable's value, given to grep through a file descriptor
bad=0
while IFS= read -r line; do
    name=${line%%=*}; val=${line#*=}; val=${val%\"}; val=${val#\"}
    case $name in *PASS* | *SECRET* | *TOKEN* | *KEY* | *CREDENTIAL*) ;; *) continue ;; esac
    [ "${#val}" -ge 8 ] || continue
    n=$(grep -rlF -f <(printf '%s\n' "$val") "$PKG" 2> /dev/null | wc -l)
    echo "secret sweep: $name -> $n file(s)"
    [ "$n" -eq 0 ] || bad=1
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENVF")
hdr='-----BEGIN ''[A-Z ]*PRIVATE KEY-----'
n=$(grep -rlE -- "$hdr" "$PKG" 2> /dev/null | wc -l)
echo "secret sweep: PEM private-key headers -> $n file(s)"
[ "$n" -eq 0 ] || bad=1
[ "$bad" -eq 0 ] || { echo "STOP: a secret value or a private-key header is in the copy: $PKG is left UNSEALED; delete nothing, report"; exit 1; }

{
    echo "# G3, session S3 second opening (tests 8 and 9): minimal preparation (sealed $(date -u +%Y-%m-%dT%H:%M:%SZ))"
    echo
    echo "Authority: output_test/decisions/2026-10-05_g3-s3b-exception-authorisation.md. This package authorises nothing"
    echo "and is not a G3 result: the session starts only on Rui's «estou presente». The first preparation,"
    echo "HIST_2026-10-05-g3-t8t9-host-preparation, is unchanged; its step files and manifest are reused (rows/, same bytes)."
    echo
    echo "- g3_battery.sh sha256 $(sha256sum "$PKG/g3_battery.sh" | cut -d' ' -f1) (the sealed S3 script with three changes:"
    echo "  the expected root file system b48b010d..., a fresh state directory, the authorised exception for collector-duration;"
    echo "  verification/diffs/)."
    echo "- s3b_preflight_exception.py sha256 $(sha256sum "$PKG/s3b_preflight_exception.py" | cut -d' ' -f1) (read-only checker)."
    echo "- rows/rows.manifest.json sha256 $(sha256sum "$PKG/rows/rows.manifest.json" | cut -d' ' -f1)."
    echo "- recheck-record/console.txt: $(grep '^outcome=' "$PKG/recheck-record/console.txt" | tail -n 1) - the clone, the helper, the root file system and the"
    echo "  -q2 identifiers re-read (read-only)."
    echo "- bench/ and verification/bench-notes.md: the focused cases of the exception against stubs."
} > "$PKG/README.md"
(cd "$PKG" && find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS) || exit 1
echo "sealed $(wc -l < "$PKG/SHA256SUMS") files; seal $(sha256sum "$PKG/SHA256SUMS" | cut -c1-12)"
