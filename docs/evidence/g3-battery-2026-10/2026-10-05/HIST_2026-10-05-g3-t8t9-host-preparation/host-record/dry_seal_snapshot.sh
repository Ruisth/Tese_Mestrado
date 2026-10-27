#!/bin/bash
# Dry seal of a SNAPSHOT of the preparation folder as it stands now, into a
# throw-away tree /tmp/g3-s3-seal-XXXXXX (fake HOME, fake .env, fake
# "output_test"): does seal_prep.sh accept the folder's real layout and content
# (names, CR bytes, private-key headers)? What the other streams or the host
# preparation have not delivered yet is replaced by a placeholder, and named.
# Nothing is written outside the throw-away tree.
# Usage (WSL): dry_seal_snapshot.sh
set -u
P=$(cd "$(dirname "$0")/.." && pwd)
B=$(mktemp -d /tmp/g3-s3-seal-XXXXXX) || exit 2
for v in $(compgen -e | grep '^EGW_'); do unset "$v"; done
export HOME=$B/home; mkdir -p "$HOME/egw-tcg"
printf '%s\n' 'EGW_MQTT_PASSWORD=dry-seal-fake-va''lue-0003' > "$HOME/egw-tcg/.env"
D=$(date -u +%F)
echo "snapshot of the preparation folder at $(date -u +%FT%TZ); seal_prep.sh sha256 $(sha256sum "$P/seal_prep.sh" | cut -d' ' -f1)"
cp -r "$P" "$B/prep" || exit 2
for f in rows-notes.md operator-notes.md host-notes.md bench-notes.md operator-procedure.md; do
    [ -e "$B/prep/$f" ] || { echo "placeholder (not delivered yet): $f"; echo "placeholder of the dry seal" > "$B/prep/$f"; }
done
[ -d "$B/prep/bench/record" ] || { echo "placeholder (not delivered yet): bench/record/"; mkdir -p "$B/prep/bench/record"; }
[ -f "$B/prep/record/console.txt" ] || { echo "placeholder (the host preparation has not run): record/console.txt"; mkdir -p "$B/prep/record"
    printf '%s\n' 'placeholder record of the dry seal' 'outcome=prepared (at 2026-01-01T00:00:00.000Z)' > "$B/prep/record/console.txt"; }
PKG=$B/out/runs/$D/HIST_$D-g3-t8t9-host-preparation
bash "$B/prep/seal_prep.sh" "$B/prep" "$B/prep/operator-procedure.md" "$PKG"; RC=$?
echo "seal_prep.sh exit=$RC"
if [ -f "$PKG/SHA256SUMS" ]; then
    (cd "$PKG" && sha256sum -c --quiet SHA256SUMS) && echo "sha256sum -c: verified ($(wc -l < "$PKG/SHA256SUMS") files)"
    echo "top level of the package:"; ls "$PKG" | sed 's/^/    /'
    echo "verification/:"; ls "$PKG/verification" | sed 's/^/    /'
fi
case $B in /tmp/g3-s3-seal-*) rm -rf "$B"; echo "throw-away tree removed" ;; esac
exit "$RC"
