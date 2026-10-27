#!/bin/bash
# Finish sealing an operator-records package of session S3 that seal_ops.sh
# left unsealed (it stopped, or was interrupted, after its copy began and
# before SHA256SUMS was written). Nothing is copied again: the files
# seal_ops.sh copies are checked to be there, the whole sweep is repeated on
# the package as it stands, and README.md and SHA256SUMS are written. A sweep
# that finds a secret value or a private-key header stops this script too: it
# is not a way round the sweep.
# Usage: seal_ops_finish.sh S3 <package dir> <sealed host-preparation package dir>
# Exit: 0 sealed; 1 a STOP (still unsealed); 2 refused, nothing was written.
set -u
LABEL=${1:?} PKG=${2:?} PREP=${3:?}
ENVF=$HOME/egw-tcg/.env
refuse() { echo "STOP: $* - nothing was written"; exit 2; }
[ "$LABEL" = S3 ] || refuse "the label must be S3 (the records of S1 and S2 are sealed), not $LABEL"
case $(basename "$PKG") in
    HIST_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-g3-t8t9-s3-operator-records) ;;
    HIST_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-g3-t8t9-s3-operator-records-attempt[0-9][0-9]) ;;
    *) refuse "$PKG is not named HIST_<UTC date>-g3-t8t9-s3-operator-records[-attemptNN]" ;;
esac
[ -d "$PKG/state" ] && [ -d "$PKG/operator" ] || refuse "$PKG is not an unsealed operator-records package"
[ ! -e "$PKG/SHA256SUMS" ] || refuse "$PKG is already sealed"
[ -n "$(ls -A "$PKG/state")" ] || refuse "$PKG/state is empty: the copy of the state directory did not happen"
for f in g3_go.sh g3_wait.sh seal_ops.sh; do [ -f "$PKG/operator/$f" ] || refuse "$PKG/operator/$f is missing: the copy did not finish"; done
case $(basename "$PREP") in HIST_*-g3-t8t9-host-preparation*) ;; *) refuse "$PREP is not a host-preparation package of S3" ;; esac
[ -f "$PREP/SHA256SUMS" ] && [ -f "$PREP/g3_battery.sh" ] || refuse "$PREP is not a sealed host-preparation package (no SHA256SUMS or no g3_battery.sh)"
[ -r "$ENVF" ] || refuse "$ENVF could not be read: the secret sweep cannot be made"
NSEC=$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENVF" | cut -d= -f1 | grep -cE 'PASS|SECRET|TOKEN|KEY|CREDENTIAL')
[ "$NSEC" -gt 0 ] || refuse "$ENVF names no secret variable: the sweep would be empty"

# The same sweep as seal_ops.sh: a value reaches grep through a file descriptor,
# never through its command line; the header pattern does not match its own text.
hits=0 swept=0
while IFS='=' read -r name value; do
    case "$name" in *PASS*|*SECRET*|*TOKEN*|*KEY*|*CREDENTIAL*) ;; *) continue ;; esac
    value=${value%\"}; value=${value#\"}; value=${value%\'}; value=${value#\'}
    [ "${#value}" -ge 4 ] || continue
    n=$(grep -rlF -f <(printf '%s\n' "$value") -- "$PKG" 2> /dev/null | wc -l)
    echo "secret sweep: $name -> $n file(s)"
    hits=$((hits + n)); swept=$((swept + 1))
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENVF")
[ "$swept" -gt 0 ] || { echo "STOP: no secret-named variable was read from $ENVF: the sweep would be empty - NOT sealed"; exit 1; }
PAT='-----BEGIN [A-Z ]*PRIVATE KEY''-----'
pem=$(grep -rlE -- "$PAT" "$PKG" 2> /dev/null | wc -l)
echo "secret sweep: PEM private-key headers -> $pem file(s)"
[ "$hits" -eq 0 ] && [ "$pem" -eq 0 ] || { echo "STOP: a secret value is in the package - NOT sealed"; exit 1; }

same() {   # same <file as opened> <file of the preparation package>: one sentence
    local a b
    [ -f "$1" ] || { echo "not recorded in the state directory"; return; }
    a=$(sha256sum "$1" | cut -d' ' -f1); b=$(sha256sum "$2" 2> /dev/null | cut -d' ' -f1)
    if [ "$a" = "$b" ]; then echo "sha256 $a, equal to the preparation package's"
    else echo "sha256 $a, DIFFERENT from the preparation package's (${b:-unreadable})"; fi
}
if [ -e "$PKG/README.md" ]; then EARLIER="a README.md that seal_ops.sh had left was replaced by this one; no other file was replaced"
else EARLIER="nothing was copied again or replaced"; fi
if [ -e "$PKG/state/turn.lock" ]; then
    rm -f "$PKG/state/turn.lock"; EARLIER="$EARLIER; the copy of the turn lock (state/turn.lock) was removed, as seal_ops.sh does"
fi
# Is the copy complete? It is compared, by content, with the state directory as it stands now.
STATE=${EGW_G3_STATE:-$HOME/egw-exec/g3-t8t9-s3-attempt02}   # S3, second opening: a fresh state directory
if [ -d "$STATE" ]; then
    DIFF=$(diff -rq -x turn.lock "$STATE" "$PKG/state" 2>&1)
    if [ $? -eq 0 ]; then CMP="state/ is identical to the state directory as it stood at finishing (diff -rq, the turn lock aside)"
    else
        printf '%s\n' "$DIFF" > "$PKG/operator/state-compare-at-finish.txt"
        CMP="state/ DIFFERS from the state directory as it stood at finishing ($(printf '%s\n' "$DIFF" | grep -c .) line(s) of diff -rq, kept in operator/state-compare-at-finish.txt): the copy was incomplete, or the state directory changed after it"
        echo "NOTE: $CMP"
    fi
else CMP="the state directory was not there at finishing: whether the copy in state/ is complete could not be checked"; echo "NOTE: $CMP"; fi
{
echo "# G3, session S3 (tests 8 and 9): operator records (sealed $(date -u +%FT%TZ))"
echo
echo "state/: the steps script's state directory as it stood when seal_ops.sh copied it (session and row state"
echo "files, one console per invocation, the frozen drivers' consoles, the environment copy record, the script and"
echo "manifest as opened). operator/: the operator's launcher and waiter (read-only helpers that start one"
echo "subcommand detached and wait for it), the sealing scripts, and the classification notes given to 'classify'"
if [ -d "$PKG/operator/classification-notes" ]; then echo "(one reason and one next-action file per classified row)."
else echo "(none here: the package holds no classification notes)."; fi
echo "The session, preflight, gate and row packages are under output_test/runs/, each under its own UTC date;"
echo "state/session-S3.env and state/row-*.env name them. Nothing here is a G3 result."
echo
echo "The steps script, the row files and their verification are in $(basename "$PREP")"
echo "(its SHA256SUMS: sha256 $(sha256sum "$PREP/SHA256SUMS" | cut -d' ' -f1))."
echo "- steps script as opened (state/S3-g3_battery.sh): $(same "$PKG/state/S3-g3_battery.sh" "$PREP/g3_battery.sh")"
echo "- manifest as opened (state/S3-rows.manifest.json): $(same "$PKG/state/S3-rows.manifest.json" "$PREP/rows/rows.manifest.json")"
echo
echo "Sealing note: seal_ops.sh did not seal this package (it stopped, or was interrupted, after its copy began; the"
echo "operator's result note says why). seal_ops_finish.sh found the files seal_ops.sh copies, repeated the whole"
echo "sweep on the package as it stood ($swept secret-named variable(s): 0 files with a value; 0 files with a"
echo "private-key header) and wrote this README and SHA256SUMS in place; $EARLIER."
echo "Completeness of the copy: $CMP."
echo "Whether the classification notes are complete is not something this script can tell."
} > "$PKG/README.md"
cp "$0" "$PKG/operator/seal_ops_finish.sh" || exit 1
( cd "$PKG" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "sealed $(wc -l < "$PKG/SHA256SUMS") files; seal $(sha256sum "$PKG/SHA256SUMS" | cut -c1-12)"
