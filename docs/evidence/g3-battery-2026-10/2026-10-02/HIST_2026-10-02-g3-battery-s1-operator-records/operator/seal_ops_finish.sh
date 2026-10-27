#!/bin/bash
# Finish sealing an operator-records package that seal_ops.sh left unsealed
# because its private-key sweep matched the sweep's own pattern text inside the
# copy of seal_ops.sh (operator/seal_ops.sh). Nothing is copied or replaced:
# the sweep is repeated with that one file's own pattern line set aside, and
# README.md and SHA256SUMS are written.
# Usage: seal_ops_finish.sh <S1|S2> <package dir>
set -u
LABEL=${1:?} PKG=${2:?}
[ -d "$PKG/state" ] && [ -d "$PKG/operator" ] || { echo "STOP: $PKG is not an unsealed operator-records package"; exit 2; }
[ ! -e "$PKG/SHA256SUMS" ] || { echo "STOP: $PKG is already sealed"; exit 2; }
hits=0
while IFS='=' read -r name value; do
    case "$name" in *PASS*|*SECRET*|*TOKEN*|*KEY*|*CREDENTIAL*) ;; *) continue ;; esac
    value=${value%\"}; value=${value#\"}; value=${value%\'}; value=${value#\'}
    [ "${#value}" -ge 4 ] || continue
    n=$(grep -rlF -- "$value" "$PKG" 2> /dev/null | wc -l)
    echo "secret sweep: $name -> $n file(s)"
    hits=$((hits + n))
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$HOME/egw-tcg/.env")
PAT='-----BEGIN [A-Z ]*PRIVATE KEY''-----'
others=$(grep -rlE -- "$PAT" "$PKG" 2> /dev/null | grep -v '/operator/seal_ops.sh$' | wc -l)
own=$(grep -cE -- "$PAT" "$PKG/operator/seal_ops.sh" 2> /dev/null)
echo "secret sweep: PEM private-key headers -> $others file(s); operator/seal_ops.sh holds $own such header line(s) (its own pattern uses '.*', which this stricter pattern does not match)"
[ "$hits" -eq 0 ] && [ "$others" -eq 0 ] && [ "${own:-1}" -eq 0 ] || { echo "STOP: a secret value is in the package - NOT sealed"; exit 1; }
{
echo "# G3 qualifying battery, session $LABEL: operator records"
echo
echo "state/: the steps script's state directory as it stood when this package was sealed (session and row state"
echo "files, one console per invocation, the frozen drivers' consoles, the environment copy record, the script and"
echo "manifest as opened). operator/: the operator's launcher and waiter (read-only helpers that start one"
echo "subcommand detached and wait for it), the sealing scripts, and the classification notes given to 'classify'"
echo "(one reason and one next-action file per row). The row, session, preflight and gate packages are beside this"
echo "one under the same date; the steps script, the row files and their verification are in"
echo "HIST_2026-10-02-g3-battery-host-preparation."
echo
echo "Sealing note: seal_ops.sh stopped before sealing, because its private-key sweep matched its own pattern text"
echo "in the copy of itself (operator/seal_ops.sh, line 25); no key is in the package. seal_ops_finish.sh repeated the"
echo "sweep with a pattern that does not match that text (0 files with a secret value, 0 with a private-key header)"
echo "and wrote this README and SHA256SUMS in place; nothing was copied again or replaced."
} > "$PKG/README.md"
cp "$0" "$PKG/operator/seal_ops_finish.sh" || exit 1
( cd "$PKG" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "sealed $(wc -l < "$PKG/SHA256SUMS") files; seal $(sha256sum "$PKG/SHA256SUMS" | cut -c1-12)"
