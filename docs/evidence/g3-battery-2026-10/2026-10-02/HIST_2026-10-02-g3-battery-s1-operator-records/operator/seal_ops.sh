#!/bin/bash
# Seal the operator records of one G3 battery session (WSL): a copy of the
# steps script's state directory as it stands, the operator's launcher, waiter
# and classification notes. Sweeps for the values of the secret variables of
# ~/egw-tcg/.env (names only are printed). Never overwrites a package.
# Usage: seal_ops.sh <S1|S2> <ops dir> <package dir>
set -u
LABEL=${1:?} OPS=${2:?} PKG=${3:?}
STATE=${EGW_G3_STATE:-$HOME/egw-exec/g3-battery}
[ ! -e "$PKG" ] || { echo "STOP: $PKG exists - never overwritten"; exit 2; }
mkdir -p "$PKG/state" "$PKG/operator" || exit 2
cp -r "$STATE"/. "$PKG/state/" || exit 1
rm -f "$PKG/state/turn.lock"
cp "$OPS"/g3_go.sh "$OPS"/g3_wait.sh "$OPS"/seal_ops.sh "$PKG/operator/" || exit 1
cp -r "$OPS/notes" "$PKG/operator/classification-notes" || exit 1
hits=0
while IFS='=' read -r name value; do
    case "$name" in *PASS*|*SECRET*|*TOKEN*|*KEY*|*CREDENTIAL*) ;; *) continue ;; esac
    value=${value%\"}; value=${value#\"}; value=${value%\'}; value=${value#\'}
    [ "${#value}" -ge 4 ] || continue
    n=$(grep -rlF -- "$value" "$PKG" 2> /dev/null | wc -l)
    echo "secret sweep: $name -> $n file(s)"
    hits=$((hits + n))
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$HOME/egw-tcg/.env")
pem=$(grep -rl -- '-----BEGIN .*PRIVATE KEY-----' "$PKG" 2> /dev/null | wc -l)
echo "secret sweep: PEM private keys -> $pem file(s)"
[ "$hits" -eq 0 ] && [ "$pem" -eq 0 ] || { echo "STOP: a secret value is in the package - NOT sealed"; exit 1; }
{
echo "# G3 qualifying battery, session $LABEL: operator records"
echo
echo "state/: the steps script's state directory as it stood when this package was sealed (session and row state"
echo "files, one console per invocation, the frozen drivers' consoles, the environment copy record, the script and"
echo "manifest as opened). operator/: the operator's launcher and waiter (read-only helpers that start one"
echo "subcommand detached and wait for it), this sealing script, and the classification notes given to 'classify'"
echo "(one reason and one next-action file per row). The row, session, preflight and gate packages are beside this"
echo "one under the same date; the steps script, the row files and their verification are in"
echo "HIST_2026-10-02-g3-battery-host-preparation."
} > "$PKG/README.md"
( cd "$PKG" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "sealed $(wc -l < "$PKG/SHA256SUMS") files; seal $(sha256sum "$PKG/SHA256SUMS" | cut -c1-12)"
