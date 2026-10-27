#!/bin/bash
# Bench of the S3 sealing scripts (seal_prep.sh, ops/seal_ops.sh,
# ops/seal_ops_finish.sh) and of the launcher and waiter (ops/g3_go.sh,
# ops/g3_wait.sh), in a throw-away tree /tmp/g3-s3-seal-XXXXXX: HOME, the state
# directory, the ".env" and "output_test" are all inside it. The .env is a FAKE
# with fake values; the real one is never read. No guest, no docker, no ssh.
# 'grep' is wrapped by a stub that logs its command line and then runs the real
# grep, to show whether a secret value ever reaches a command line.
# Usage (WSL): seal_bench.sh        (prints PASS/FAIL lines; exit 0 only when no FAIL)
set -u
P=$(cd "$(dirname "$0")/.." && pwd)     # the preparation folder: this script is in its host-record/
B=$(mktemp -d /tmp/g3-s3-seal-XXXXXX) || exit 2
for v in $(compgen -e | grep '^EGW_'); do unset "$v"; done
export HOME=$B/home
export EGW_EXEC=$HOME/egw-exec EGW_EXEC_REPO=$HOME/egw-exec/repo EGW_ATTEMPTS=$HOME/egw-exec/attempts EGW_OUTPUT_TEST=$B/out
D=$(date -u +%F)
RUNS=$B/out/runs/$D
FAKE1="bench-fake-pass""word-0001"   # written in two pieces: this file, which the sealed package holds, does not hold the fake values
FAKE2="bench-fake-to""ken-0002"
mkdir -p "$HOME/egw-tcg" "$B/bin" "$B/consoles" "$B/out/runs"
printf '%s\n' 'EGW_MQTT_USERNAME=simulator' "EGW_MQTT_PASSWORD=$FAKE1" "EGW_DITTO_TOKEN=\"$FAKE2\"" 'EGW_TINY_KEY=abc' 'EGW_PLAIN=bench-not-secret-value' > "$HOME/egw-tcg/.env"
export G3_BENCH_ARGV_LOG=$B/grep-argv.log
printf '%s\n' '#!/bin/bash' 'printf "%s\n" "$*" >> "$G3_BENCH_ARGV_LOG"' 'exec /usr/bin/grep "$@"' > "$B/bin/grep"
chmod +x "$B/bin/grep"
export PATH=$B/bin:$PATH
echo "bench tree: $B (HOME=$HOME); UTC date $D; grep on PATH: $(command -v grep)"
echo "scripts under test:"
(cd "$P" && sha256sum seal_prep.sh ops/seal_ops.sh ops/seal_ops_finish.sh ops/g3_go.sh ops/g3_wait.sh base/ops/seal_ops.sh)

pass=0; failn=0
ok() { echo "PASS: $*"; pass=$((pass + 1)); }
ko() { echo "FAIL: $*"; failn=$((failn + 1)); }
is() { if [ "$1" = "$2" ]; then ok "$3 ($1)"; else ko "$3 (got '$1', expected '$2')"; fi; }
run() {   # run <console name> <command...>: the console is shown indented; RC is the exit status
    CON=$B/consoles/$1.txt; shift
    : > "$G3_BENCH_ARGV_LOG"
    "$@" > "$CON" 2>&1; RC=$?
    sed 's/^/    | /' "$CON"
    echo "    exit=$RC"
}
argv_hits() { /usr/bin/grep -cF -e "$FAKE1" -e "$FAKE2" "$G3_BENCH_ARGV_LOG"; }   # the real grep: the stub would log this very call
tree_sig() { (cd "$B/out" && find . | sort | sha256sum | cut -c1-16); }
pem_header() { local h='-----BEGIN RSA PRIVATE'; printf '%s KEY-----\n' "$h"; }   # built in two pieces: this file holds no header

mkprep() {   # mkprep <dir>: a fake preparation folder with the real scripts of P as they stand now
    local d=$1 f
    mkdir -p "$d/record" "$d/rows" "$d/rows-record" "$d/bench/record" "$d/ops" "$d/host-record"
    for f in g3_hostprep.sh g3_extract_rows.py g3_check_rows.sh g3_rows_dryrun.sh g3_battery.sh g3_battery.README.md seal_prep.sh brief.md runbook.8e49261.md operator-procedure.battery.md; do cp "$P/$f" "$d/"; done
    cp "$P"/ops/*.sh "$d/ops/"; cp -r "$P/base" "$d/base"; cp "$P"/host-record/*.sh "$d/host-record/"
    printf '%s\n' '## fake record of g3_hostprep.sh (bench)' 'HEAD=80e833f44f647fe9cd8f5e99d3abf3c444de95aa branch=(detached)' \
        'HEAD=8e492613d36490a560ae56beabd6d5c2c01a8696 tree=2f0514837f267d8975f7071041aad14a5c18dcab' \
        'rootfs-ext4: 22e9da8533541582a2e4549f4c37f2b80f0f6a9bd3a5f0dd5e13605d7269efcd  /fake/rootfs.ext4' \
        'fresh on the host: itest-reboot-q2' 'fresh on the guest: itest-reboot-q2' '' 'outcome=prepared (at 2026-10-04T00:00:00.000Z)' > "$d/record/console.txt"
    echo '{"fake": "manifest of the bench"}' > "$d/rows/rows.manifest.json"
    printf '%s\n' '#!/bin/bash' 'echo fake step a' > "$d/rows/t8-a-reboot.sh"
    printf '%s\n' '#!/bin/bash' 'echo fake step' > "$d/rows/t9-a.sh"
    echo 'fake extraction console' > "$d/rows-record/rows-extract.console.txt"
    echo 'fake bench console' > "$d/bench/record/01-success.console.txt"
    for f in rows-notes.md operator-notes.md host-notes.md bench-notes.md extra-review.md operator-procedure.md; do echo "fake $f of the bench" > "$d/$f"; done
    mkdir -p "$d/operator-record" "$d/stray-dir"; echo 'fake console of another stream' > "$d/operator-record/x.console.txt"; echo stray > "$d/scratch.tmp"
}
mkstate() {  # mkstate <state dir> <prep dir>: a fake state directory of the steps script
    mkdir -p "$1/console"
    printf '%s\n' 'label=S3' 'state=closed' > "$1/session-S3.env"
    echo 'row=t8' > "$1/row-t8.env"; echo 'turn=none' > "$1/turn.env"; : > "$1/turn.lock"
    echo 'fake console of open S3' > "$1/console/001-open-S3.txt"
    cp "$2/g3_battery.sh" "$1/S3-g3_battery.sh"; cp "$2/rows/rows.manifest.json" "$1/S3-rows.manifest.json"
}

echo; echo "===== A. seal_prep.sh ====="
mkprep "$B/prep"
PKG=$RUNS/HIST_$D-g3-t8t9-host-preparation
echo "--- A1 a complete preparation folder is sealed"
run A1 bash "$B/prep/seal_prep.sh" "$B/prep" "$B/prep/operator-procedure.md" "$PKG"
is "$RC" 0 "A1 exit"
(cd "$PKG" && sha256sum -c --quiet SHA256SUMS) && ok "A1 sha256sum -c of the sealed package" || ko "A1 sha256sum -c"
is "$(find "$PKG" -type f ! -name SHA256SUMS | wc -l)" "$(wc -l < "$PKG/SHA256SUMS")" "A1 every file is in SHA256SUMS"
n=$(/usr/bin/grep -rl 'PRIVATE KEY' "$PKG" | wc -l)
[ "$n" -ge 4 ] && ok "A1 $n files of the package hold the sweep's pattern text (the sealing scripts, their diffs, this bench) and the sweep counted 0" || ko "A1 only $n files hold the pattern text"
/usr/bin/grep -q 'PEM private-key headers -> 0 file' "$CON" && ok "A1 the private-key sweep does not match its own pattern line" || ko "A1 private-key sweep"
is "$(/usr/bin/grep -c 'secret sweep: EGW_' "$CON")" 2 "A1 secret-named variables swept (the 3-character one is skipped, the plain ones are not secrets)"
is "$(argv_hits)" 0 "A1 fake secret values on a grep command line"
is "$(/usr/bin/grep -cF -e "$FAKE1" -e "$FAKE2" "$CON")" 0 "A1 fake secret values in the sealing console"
[ -f "$PKG/verification/extra-review.md" ] && [ -f "$PKG/verification/host-notes.md" ] && [ ! -e "$PKG/verification/brief.md" ] && [ -f "$PKG/prep_brief.md" ] \
    && [ ! -e "$PKG/operator-procedure.battery.md" ] && [ ! -e "$PKG/verification/operator-procedure.battery.md" ] && [ -f "$PKG/operator-procedure.md" ] \
    && ok "A1 notes in verification/, brief as prep_brief.md, the battery's procedure not copied" || ko "A1 layout of the notes"
is "$(ls "$PKG/verification/diffs" | wc -l)" 11 "A1 diffs against base/"
[ -f "$PKG/ops/seal_ops.sh" ] && [ -f "$PKG/seal_prep.sh" ] && [ -f "$PKG/part1-record/console.txt" ] && [ -f "$PKG/bench/record/01-success.console.txt" ] && [ -f "$PKG/host-record/seal_bench.sh" ] && [ ! -e "$PKG/base" ] \
    && ok "A1 scripts, ops/, part1-record/, bench/, host-record/ present; base/ not copied" || ko "A1 layout"
[ -f "$PKG/operator-record/x.console.txt" ] && [ -f "$PKG/rows-record/rows-extract.console.txt" ] && [ ! -e "$PKG/scratch.tmp" ] && [ ! -e "$PKG/stray-dir" ] \
    && /usr/bin/grep -q 'not copied: operator-procedure.battery.md base scratch.tmp stray-dir;' "$CON" && /usr/bin/grep -q 'not copied: operator-procedure.battery.md base scratch.tmp stray-dir (' "$PKG/README.md" \
    && ok "A1 every *-record folder is copied; what is outside the file set is named in the console and in the README, and not copied" || ko "A1 record folders / entries left out"
echo "    README (first 14 lines):"; head -n 14 "$PKG/README.md" | sed 's/^/    | /'
SEAL1=$(sha256sum "$PKG/SHA256SUMS" | cut -d' ' -f1)

echo "--- A2 a second sealing on the same name is refused and changes nothing"
run A2 bash "$B/prep/seal_prep.sh" "$B/prep" "$B/prep/operator-procedure.md" "$PKG"
is "$RC" 2 "A2 exit"
/usr/bin/grep -q 'exists - never overwritten' "$CON" && ok "A2 says the package is never overwritten" || ko "A2 text"
is "$(sha256sum "$PKG/SHA256SUMS" | cut -d' ' -f1)" "$SEAL1" "A2 SHA256SUMS unchanged"
(cd "$PKG" && sha256sum -c --quiet SHA256SUMS) && ok "A2 the package still verifies" || ko "A2 sha256sum -c"

SIG=$(tree_sig)
echo "--- A3 a wrong package name, a wrong date folder, a missing input, a record with no outcome, no .env, an .env with no secret name: refused, nothing created"
run A3a bash "$B/prep/seal_prep.sh" "$B/prep" "$B/prep/operator-procedure.md" "$RUNS/HIST_$D-g3-battery-host-preparation"; is "$RC" 2 "A3a wrong name"
run A3b bash "$B/prep/seal_prep.sh" "$B/prep" "$B/prep/operator-procedure.md" "$B/out/runs/2026-01-01/HIST_$D-g3-t8t9-host-preparation-attempt02"; is "$RC" 2 "A3b date folder that is not the name's date"
mkprep "$B/prep-missing"; rm "$B/prep-missing/bench-notes.md"
run A3c bash "$B/prep-missing/seal_prep.sh" "$B/prep-missing" "$B/prep-missing/operator-procedure.md" "$RUNS/HIST_$D-g3-t8t9-host-preparation-attempt02"; is "$RC" 2 "A3c missing bench-notes.md"
mkprep "$B/prep-noend"; sed -i '/^outcome=/d' "$B/prep-noend/record/console.txt"
run A3d bash "$B/prep-noend/seal_prep.sh" "$B/prep-noend" "$B/prep-noend/operator-procedure.md" "$RUNS/HIST_$D-g3-t8t9-host-preparation-attempt02"; is "$RC" 2 "A3d record without an outcome line"
mv "$HOME/egw-tcg/.env" "$HOME/egw-tcg/.env.aside"
run A3e bash "$B/prep/seal_prep.sh" "$B/prep" "$B/prep/operator-procedure.md" "$RUNS/HIST_$D-g3-t8t9-host-preparation-attempt02"; is "$RC" 2 "A3e no .env"
printf '%s\n' 'EGW_PLAIN=bench-not-secret-value' > "$HOME/egw-tcg/.env"
run A3f bash "$B/prep/seal_prep.sh" "$B/prep" "$B/prep/operator-procedure.md" "$RUNS/HIST_$D-g3-t8t9-host-preparation-attempt02"; is "$RC" 2 "A3f .env without a secret-named variable"
mv "$HOME/egw-tcg/.env.aside" "$HOME/egw-tcg/.env"
is "$(tree_sig)" "$SIG" "A3 nothing was created under the bench output_test by the six refusals"

echo "--- A4 a secret value in a record: STOP, not sealed, the value not printed"
mkprep "$B/prep-secret"; echo "password seen in a console: $FAKE1" >> "$B/prep-secret/rows-record/rows-extract.console.txt"
PK4=$RUNS/HIST_$D-g3-t8t9-host-preparation-attempt02
run A4 bash "$B/prep-secret/seal_prep.sh" "$B/prep-secret" "$B/prep-secret/operator-procedure.md" "$PK4"
is "$RC" 1 "A4 exit"
/usr/bin/grep -q 'EGW_MQTT_PASSWORD -> 1 file' "$CON" && /usr/bin/grep -q 'NOT sealed' "$CON" && [ ! -e "$PK4/SHA256SUMS" ] && ok "A4 the variable is named, the package is left without SHA256SUMS" || ko "A4"
is "$(/usr/bin/grep -cF "$FAKE1" "$CON")" 0 "A4 the value in the sealing console"
is "$(argv_hits)" 0 "A4 the value on a grep command line"

echo "--- A5 a private-key header in a record: STOP, not sealed"
mkprep "$B/prep-pem"; pem_header >> "$B/prep-pem/bench/record/01-success.console.txt"
PK5=$RUNS/HIST_$D-g3-t8t9-host-preparation-attempt03
run A5 bash "$B/prep-pem/seal_prep.sh" "$B/prep-pem" "$B/prep-pem/operator-procedure.md" "$PK5"
is "$RC" 1 "A5 exit"
/usr/bin/grep -q 'PEM private-key headers -> 1 file' "$CON" && [ ! -e "$PK5/SHA256SUMS" ] && ok "A5 one file with a header, not sealed" || ko "A5"

echo "--- A6 a record whose outcome is not 'prepared': sealed, exit 3, the README's title says so; the suffix -attemptNN and a record directory given as the fourth argument"
mkprep "$B/prep-failed"; mv "$B/prep-failed/record" "$B/prep-failed/record-2"
sed -i 's/^outcome=prepared.*/STOP: rootfs-ext4 is 0000, S3 expects 22e9\noutcome=failed (at 2026-10-04T00:00:01.000Z)/' "$B/prep-failed/record-2/console.txt"
PK6=$RUNS/HIST_$D-g3-t8t9-host-preparation-attempt04
run A6 bash "$B/prep-failed/seal_prep.sh" "$B/prep-failed" "$B/prep-failed/operator-procedure.md" "$PK6" "$B/prep-failed/record-2"
is "$RC" 3 "A6 exit"
head -n 1 "$PK6/README.md" | /usr/bin/grep -q "did NOT end 'prepared'" && /usr/bin/grep -q 'STOP lines in the record: 1' "$PK6/README.md" && (cd "$PK6" && sha256sum -c --quiet SHA256SUMS) \
    && ok "A6 sealed and verifiable, title and STOP count say it was not prepared" || ko "A6"

echo; echo "===== B. ops/seal_ops.sh ====="
OPSD=$B/prep/ops
mkdir -p "$OPSD/notes"; echo 'fake reason' > "$OPSD/notes/t8.reason.txt"; echo 'fake next' > "$OPSD/notes/t8.next.txt"
mkstate "$HOME/egw-exec/g3-t8t9-s3" "$B/prep"
echo "--- B0 (red) the FIRST preparation's seal_ops.sh on the same kind of input: the known false alarm, and the value on a command line"
mkdir -p "$B/baseops"; cp "$P"/base/ops/*.sh "$B/baseops/"; cp -r "$OPSD/notes" "$B/baseops/notes"
EGW_G3_STATE=$HOME/egw-exec/g3-t8t9-s3 run B0 bash "$B/baseops/seal_ops.sh" S2 "$B/baseops" "$B/out/base-red-package"
is "$RC" 1 "B0 exit of the first preparation's script"
/usr/bin/grep -q 'PEM private keys -> 1 file' "$CON" && /usr/bin/grep -q 'NOT sealed' "$CON" && ok "B0 false alarm reproduced: its own pattern line is the one file" || ko "B0 false alarm not reproduced"
n=$(argv_hits); [ "$n" -ge 1 ] && ok "B0 the first preparation's sweep put a secret value on grep's command line ($n logged command lines)" || ko "B0 argv log"

PKO=$RUNS/HIST_$D-g3-t8t9-s3-operator-records
echo "--- B1 (green) the S3 script: sealed, state directory by default under HOME"
run B1 bash "$OPSD/seal_ops.sh" S3 "$OPSD" "$PKO" "$PKG"
is "$RC" 0 "B1 exit"
(cd "$PKO" && sha256sum -c --quiet SHA256SUMS) && ok "B1 sha256sum -c of the sealed package" || ko "B1 sha256sum -c"
/usr/bin/grep -q 'PEM private-key headers -> 0 file' "$CON" && /usr/bin/grep -q 'PRIVATE KEY' "$PKO/operator/seal_ops.sh" && ok "B1 the copy of seal_ops.sh holds the pattern text and the sweep counted 0" || ko "B1 sweep"
is "$(argv_hits)" 0 "B1 fake secret values on a grep command line"
[ ! -e "$PKO/state/turn.lock" ] && [ -f "$PKO/state/turn.env" ] && [ -f "$PKO/state/console/001-open-S3.txt" ] && [ -f "$PKO/operator/classification-notes/t8.reason.txt" ] && [ ! -e "$PKO/operator/seal_ops_finish.sh" ] \
    && ok "B1 state copied without the turn lock, notes copied, finish script not copied" || ko "B1 layout"
is "$(/usr/bin/grep -c 'equal to the preparation package' "$PKO/README.md")" 2 "B1 README: steps script and manifest as opened equal the preparation package's"
echo "    README:"; sed 's/^/    | /' "$PKO/README.md"
SEAL2=$(sha256sum "$PKO/SHA256SUMS" | cut -d' ' -f1)

echo "--- B2 refusals: the same name again, label S2, a wrong name, an unsealed preparation package, a state directory that is missing"
SIG=$(tree_sig)
run B2a bash "$OPSD/seal_ops.sh" S3 "$OPSD" "$PKO" "$PKG"; is "$RC" 2 "B2a same name"
is "$(sha256sum "$PKO/SHA256SUMS" | cut -d' ' -f1)" "$SEAL2" "B2a SHA256SUMS unchanged"
run B2b bash "$OPSD/seal_ops.sh" S2 "$OPSD" "$RUNS/HIST_$D-g3-t8t9-s2-operator-records" "$PKG"; is "$RC" 2 "B2b label S2"
run B2c bash "$OPSD/seal_ops.sh" S3 "$OPSD" "$RUNS/HIST_$D-g3-battery-s3-operator-records" "$PKG"; is "$RC" 2 "B2c wrong name"
run B2d bash "$OPSD/seal_ops.sh" S3 "$OPSD" "$B/out/runs/2026-01-02/HIST_2026-01-02-g3-t8t9-s3-operator-records" "$PK4"; is "$RC" 2 "B2d preparation package without SHA256SUMS"
EGW_G3_STATE=$B/no-such-state run B2e bash "$OPSD/seal_ops.sh" S3 "$OPSD" "$B/out/runs/2026-01-02/HIST_2026-01-02-g3-t8t9-s3-operator-records" "$PKG"; is "$RC" 2 "B2e missing state directory"
is "$(tree_sig)" "$SIG" "B2 nothing was created by the five refusals"

echo "--- B3 a secret value in a state console: STOP, unsealed; seal_ops_finish.sh is not a way round"
mkstate "$B/state-secret" "$B/prep"; echo "sim --password $FAKE1" >> "$B/state-secret/console/001-open-S3.txt"
PK3=$B/out/runs/2026-01-03/HIST_2026-01-03-g3-t8t9-s3-operator-records
EGW_G3_STATE=$B/state-secret run B3 bash "$OPSD/seal_ops.sh" S3 "$OPSD" "$PK3" "$PKG"
is "$RC" 1 "B3 exit (state directory from EGW_G3_STATE)"
/usr/bin/grep -q 'EGW_MQTT_PASSWORD -> 1 file' "$CON" && [ ! -e "$PK3/SHA256SUMS" ] && ok "B3 not sealed" || ko "B3"
is "$(/usr/bin/grep -cF "$FAKE1" "$CON")" 0 "B3 the value in the sealing console"
EGW_G3_STATE=$B/state-secret run B3f bash "$OPSD/seal_ops_finish.sh" S3 "$PK3" "$PKG"
is "$RC" 1 "B3f finish exit"
[ ! -e "$PK3/SHA256SUMS" ] && [ ! -e "$PK3/README.md" ] && ok "B3f still unsealed, no README written" || ko "B3f"

echo "--- B4 a private-key header in a state file: STOP; no notes directory: sealed, the README says there are none"
mkstate "$B/state-pem" "$B/prep"; pem_header > "$B/state-pem/console/002-row-t9.txt"
PK4O=$B/out/runs/2026-01-04/HIST_2026-01-04-g3-t8t9-s3-operator-records
EGW_G3_STATE=$B/state-pem run B4a bash "$OPSD/seal_ops.sh" S3 "$OPSD" "$PK4O" "$PKG"
is "$RC" 1 "B4a exit"; /usr/bin/grep -q 'PEM private-key headers -> 1 file' "$CON" && ok "B4a one file with a header" || ko "B4a"
mkdir -p "$B/ops-nonotes"; cp "$P"/ops/*.sh "$B/ops-nonotes/"
PK4N=$B/out/runs/2026-01-05/HIST_2026-01-05-g3-t8t9-s3-operator-records
run B4b bash "$B/ops-nonotes/seal_ops.sh" S3 "$B/ops-nonotes" "$PK4N" "$PKG"
is "$RC" 0 "B4b exit"; /usr/bin/grep -q 'none here' "$PK4N/README.md" && [ ! -e "$PK4N/operator/classification-notes" ] && ok "B4b sealed without notes, said so" || ko "B4b"

echo; echo "===== C. ops/seal_ops_finish.sh ====="
mkint() {    # mkint <package dir> <state dir>: what seal_ops.sh leaves when it is interrupted after its copy
    mkdir -p "$1/state" "$1/operator"; cp -r "$2"/. "$1/state/"
    cp "$OPSD"/g3_go.sh "$OPSD"/g3_wait.sh "$OPSD"/seal_ops.sh "$1/operator/"; cp -r "$OPSD/notes" "$1/operator/classification-notes"
}
echo "--- C1 an interrupted package (copy done, turn lock still in the copy, no README, no SHA256SUMS) is finished in place"
PC1=$B/out/runs/2026-01-06/HIST_2026-01-06-g3-t8t9-s3-operator-records
mkint "$PC1" "$HOME/egw-exec/g3-t8t9-s3"
BEFORE=$(cd "$PC1" && find . -type f ! -name turn.lock | sort | xargs sha256sum | sha256sum | cut -c1-16)
run C1 bash "$OPSD/seal_ops_finish.sh" S3 "$PC1" "$PKG"
is "$RC" 0 "C1 exit"
(cd "$PC1" && sha256sum -c --quiet SHA256SUMS) && ok "C1 sha256sum -c of the finished package" || ko "C1 sha256sum -c"
AFTER=$(cd "$PC1" && find . -type f ! -name SHA256SUMS ! -name README.md ! -name seal_ops_finish.sh | sort | xargs sha256sum | sha256sum | cut -c1-16)
is "$AFTER" "$BEFORE" "C1 the files that were there are unchanged"
/usr/bin/grep -q 'Sealing note' "$PC1/README.md" && /usr/bin/grep -q 'identical to the state directory' "$PC1/README.md" && /usr/bin/grep -q 'turn lock (state/turn.lock) was removed' "$PC1/README.md" \
    && [ -f "$PC1/operator/seal_ops_finish.sh" ] && [ ! -e "$PC1/state/turn.lock" ] && ok "C1 sealing note, completeness and the lock's removal stated; the finish script kept in operator/" || ko "C1 README"
is "$(argv_hits)" 0 "C1 fake secret values on a grep command line"
echo "    README (from the sealing note):"; sed -n '/^Sealing note/,$p' "$PC1/README.md" | sed 's/^/    | /'
echo "--- C2 refusals: already sealed; an incomplete copy; label S1"
run C2a bash "$OPSD/seal_ops_finish.sh" S3 "$PC1" "$PKG"; is "$RC" 2 "C2a already sealed"
PC2=$B/out/runs/2026-01-07/HIST_2026-01-07-g3-t8t9-s3-operator-records
mkint "$PC2" "$HOME/egw-exec/g3-t8t9-s3"; rm "$PC2/operator/seal_ops.sh"
run C2b bash "$OPSD/seal_ops_finish.sh" S3 "$PC2" "$PKG"; is "$RC" 2 "C2b operator/seal_ops.sh missing"
[ ! -e "$PC2/README.md" ] && [ ! -e "$PC2/SHA256SUMS" ] && ok "C2b nothing written" || ko "C2b"
run C2c bash "$OPSD/seal_ops_finish.sh" S1 "$PC2" "$PKG"; is "$RC" 2 "C2c label S1"
echo "--- C3 the state directory changed after the copy: sealed, and the README says the copy differs"
PC3=$B/out/runs/2026-01-08/HIST_2026-01-08-g3-t8t9-s3-operator-records
mkstate "$B/state-moved" "$B/prep"; mkint "$PC3" "$B/state-moved"; echo 'a later console' > "$B/state-moved/console/002-status.txt"
EGW_G3_STATE=$B/state-moved run C3 bash "$OPSD/seal_ops_finish.sh" S3 "$PC3" "$PKG"
is "$RC" 0 "C3 exit"
/usr/bin/grep -q 'DIFFERS from the state directory' "$PC3/README.md" && /usr/bin/grep -q '002-status.txt' "$PC3/operator/state-compare-at-finish.txt" && (cd "$PC3" && sha256sum -c --quiet SHA256SUMS) \
    && ok "C3 the difference is stated and listed; the package verifies" || ko "C3"

echo; echo "===== D. ops/g3_go.sh and ops/g3_wait.sh ====="
[ -f "$(cd "$P/ops/.." && pwd)/g3_battery.sh" ] && ok "D0 the folder that holds ops/ (where the launcher and the waiter look for the steps script) holds g3_battery.sh" || ko "D0 no g3_battery.sh beside ops/"
/usr/bin/grep -q 'g3-t8t9-s3' "$P/ops/g3_wait.sh" && ! /usr/bin/grep -q -e 'g3-battery' -e 'battery/prep' -e '/mnt/c/' "$P/ops/g3_wait.sh" "$P/ops/g3_go.sh" && ok "D0 no path of the first preparation, and no fixed path, is left in the launcher or the waiter" || ko "D0 old path left"
mkdir -p "$B/go/ops"; cp "$P/ops/g3_go.sh" "$P/ops/g3_wait.sh" "$B/go/ops/"     # the two scripts as they are, beside a stub steps script
export G3_BENCH_LOG=$B/go/stub.log
printf '%s\n' '#!/bin/bash' '# stub steps script of the bench: records how it was started' \
    'echo "stub: args=[$*] EGW_EXEC_REPO=${EGW_EXEC_REPO:-unset} sid=$(ps -o sid= -p $$ | tr -d " ") pid=$$ tty=$(ps -o tty= -p $$ | tr -d " ")" >> "$G3_BENCH_LOG"' \
    'case ${1:-} in status) echo "stub status: no session"; exit 0 ;; esac' \
    'mkdir -p "$HOME/egw-exec/g3-t8t9-s3/console"; echo "stub console of [$*]" > "$HOME/egw-exec/g3-t8t9-s3/console/900-$1-${2:-}.txt"' \
    'sleep 3' > "$B/go/g3_battery.sh"
echo "--- D1 'open S3' is launched detached with the clone named, waited for, and its console (S3 state directory) and the status are shown"
G3_TAIL=5 run D1 bash "$B/go/ops/g3_go.sh" open S3 1
is "$RC" 0 "D1 exit"
/usr/bin/grep -q "args=\[open S3\] EGW_EXEC_REPO=$HOME/egw-exec/repo" "$G3_BENCH_LOG" && ok "D1 the stub was started with 'open S3' and EGW_EXEC_REPO=\$HOME/egw-exec/repo" || ko "D1 stub log: $(cat "$G3_BENCH_LOG" 2> /dev/null)"
SID=$(sed -n 's/.*args=\[open S3\].* sid=\([0-9]*\) pid=\([0-9]*\) .*/\1 \2/p' "$G3_BENCH_LOG")
[ -n "$SID" ] && [ "${SID% *}" = "${SID#* }" ] && ok "D1 the stub led its own session (sid = pid: setsid)" || ko "D1 sid/pid '$SID'"
/usr/bin/grep -q "last console: $HOME/egw-exec/g3-t8t9-s3/console/900-open-S3.txt" "$CON" && /usr/bin/grep -q 'stub status: no session' "$CON" && ok "D1 the waiter read the S3 state directory and ran 'status'" || ko "D1 waiter"
echo "--- D2 usage"
run D2 bash "$B/go/ops/g3_go.sh" row; is "$RC" 2 "D2 'row' without a slug"
/usr/bin/grep -q 'open S3|row <t8|t9>|close' "$CON" && ok "D2 the usage names S3, t8 and t9" || ko "D2 usage"
sleep 4
pgrep -f "$B/go/g3_battery.sh" > /dev/null && ko "a stub process of the bench is still running" || ok "no stub process of the bench is left"

echo; echo "===== summary: $pass PASS, $failn FAIL ====="
case $B in /tmp/g3-s3-seal-*) rm -rf "$B"; echo "bench tree $B removed" ;; esac
[ "$failn" -eq 0 ]
