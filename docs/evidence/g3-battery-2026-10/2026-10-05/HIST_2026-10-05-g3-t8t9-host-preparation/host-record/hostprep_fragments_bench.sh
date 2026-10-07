#!/bin/bash
# Bench of FRAGMENTS of g3_hostprep.sh (S3), in a throw-away tree
# /tmp/g3-s3-hostfrag-XXXXXX. g3_hostprep.sh itself is NOT run (it writes on
# the host). What runs here is the text of four of its passages, cut out of the
# file by line patterns and run with its variables (C, PKG, TOOLS, TREE,
# BATTERY, REVIEWED, IMAGE, ATT, OT, T8_ADMITTED, ROOTFS, ROOTFS_SHA, IDS, id)
# pointing at throw-away git repositories, directories and ext4 images:
#   clone    : the gate on the clone, the fetch, the ancestor rule, the checkout
#              and the comparisons that follow it (up to the "no rebuild" line);
#   names    : the search by name for one identifier (attempts and output_test);
#   attempts : the earlier attempts of rows t8 and t9;
#   guest    : the offline debugfs listing of the guest's event directories.
# No passage that holds a /home/ruisth path is run. No guest, no docker, no ssh.
# The numbering expected for the new attempts is checked with the export tool of
# the merged tree (read-only use of the venv's python, no bytecode written).
# Usage (WSL): hostprep_fragments_bench.sh
set -u
S=$(cd "$(dirname "$0")/../../.." && pwd)     # the scratchpad: this script is in g3/s3prep/host-record/
P=$S/g3/s3prep
SCRIPT=$P/g3_hostprep.sh
REALPY=/home/ruisth/egw-exec/venv/bin/python
B=$(mktemp -d /tmp/g3-s3-hostfrag-XXXXXX) || exit 2
for v in $(compgen -e | grep '^EGW_'); do unset "$v"; done
export HOME=$B/home; mkdir -p "$HOME" "$B/frag" "$B/consoles"
export GIT_AUTHOR_NAME=bench GIT_AUTHOR_EMAIL=bench@example.invalid GIT_COMMITTER_NAME=bench GIT_COMMITTER_EMAIL=bench@example.invalid
export GIT_CONFIG_NOSYSTEM=1 PYTHONDONTWRITEBYTECODE=1
echo "bench tree: $B; script the fragments are cut from:"; (cd "$P" && sha256sum g3_hostprep.sh)

sed -n '/^now() {/,/^}$/p' "$SCRIPT" > "$B/frag/funcs.sh"
sed -n '/^step "tools clone/,/^echo "controller, simulator/p' "$SCRIPT" > "$B/frag/clone.sh"
sed -n '/^    HIT=\$(find/,/^    \[ -z "\$HIT" \]/p' "$SCRIPT" > "$B/frag/names.sh"
sed -n '/^step "earlier attempts of rows/,/^echo "row t9: /p' "$SCRIPT" > "$B/frag/attempts.sh"
sed -n '/^step "the -q2 identifiers unused on the guest/,/^want rootfs-ext4-after-listing/p' "$SCRIPT" > "$B/frag/guest.sh"
for f in funcs clone names attempts guest; do
    echo "fragment $f: $(wc -l < "$B/frag/$f.sh") lines, sha256 $(sha256sum "$B/frag/$f.sh" | cut -c1-16), lines naming /home/ruisth: $(grep -c '/home/ruisth' "$B/frag/$f.sh")"
    { echo 'set -u'; cat "$B/frag/funcs.sh"; [ "$f" = funcs ] || cat "$B/frag/$f.sh"; echo 'echo "FRAGMENT END REACHED"'; } > "$B/frag/run-$f.sh"
    bash -n "$B/frag/run-$f.sh" || echo "FAIL: fragment $f does not parse"
done
[ "$(cat "$B"/frag/{clone,names,attempts,guest}.sh | grep -c '/home/ruisth')" -eq 0 ] || { echo "a fragment names /home/ruisth: not run"; exit 2; }

pass=0; failn=0
ok() { echo "PASS: $*"; pass=$((pass + 1)); }
ko() { echo "FAIL: $*"; failn=$((failn + 1)); }
is() { if [ "$1" = "$2" ]; then ok "$3 ($1)"; else ko "$3 (got '$1', expected '$2')"; fi; }
run() {   # run <console name> <fragment>: runs the fragment with the exported variables; RC, CON
    CON=$B/consoles/$1.txt
    bash "$B/frag/run-$2.sh" > "$CON" 2>&1; RC=$?
    sed 's/^/    | /' "$CON" | cut -c1-250
    echo "    exit=$RC"
}
reached() { grep -q '^FRAGMENT END REACHED$' "$CON"; }
stopped() { grep -q "^STOP: .*$1" "$CON" && grep -q '^outcome=failed' "$CON" && ! reached; }

echo; echo "===== clone: the gate, the fetch, the ancestor rule, the checkout ====="
# gh.git stands for the remote; win for the Windows repository (the clone's origin), whose
# refs/remotes/origin/dev is what the script fetches; A is the battery's commit and the image
# commit, R the reviewed head, M the merge (the tree of R), L a later commit on dev.
mkuniverse() {   # mkuniverse <dir> <path the reviewed head changes besides docs/ and src/tests/>
    local u=$1 extra=$2
    mkdir -p "$u"; git init -q --bare "$u/gh.git"; git clone -q "$u/gh.git" "$u/seed" 2> /dev/null
    (cd "$u/seed" && git checkout -q -b dev && mkdir -p src/egw_controller src/tests tools/session docs \
        && echo c > src/egw_controller/main.py && echo t > src/tests/test_x.py && echo d > tools/session/x.sh && echo r > docs/runbook.md \
        && git add -A && git commit -q -m A && git push -q origin dev) || return 1
    git clone -q -b dev "$u/gh.git" "$u/win"
    (cd "$u/seed" && git checkout -q -b fix && echo r2 > docs/runbook.md && echo t2 > src/tests/test_x.py \
        && { [ -z "$extra" ] || echo changed > "$extra"; } && git add -A && git commit -q -m R \
        && git checkout -q dev && git merge -q --no-ff -m M fix && git push -q origin dev) || return 1
    (cd "$u/win" && git fetch -q origin)
    A=$(git -C "$u/seed" rev-parse dev^1); R=$(git -C "$u/seed" rev-parse fix); M=$(git -C "$u/seed" rev-parse dev)
}
# --no-local: only what the origin's branches reach is copied, as over a real transport (a plain
# local clone would link every object of the origin, the merge included).
newclone() { git clone -q --no-local "$1/win" "$2" && git -C "$2" -c advice.detachedHead=false checkout -q --detach "$3"; }
U=$B/u1; mkuniverse "$U" "" || { echo "the bench repositories could not be made"; exit 2; }
A1=$A R1=$R M1=$M
export BATTERY=$A IMAGE=$A REVIEWED=$R TOOLS=$M TREE; TREE=$(git -C "$U/seed" rev-parse "$M^{tree}")
echo "bench commits: A(battery, image)=$A R(reviewed)=$R M(merge)=$M tree=$TREE"
is "$(git -C "$U/win" rev-parse refs/remotes/origin/dev) $(git -C "$U/win" rev-parse refs/heads/dev)" "$M $A" "the stand-in Windows repository: origin/dev at the merge, its own dev still at A"

echo "--- F1 clean clone at the battery's commit, fetched tip = the commit: moved"
export C=$B/c1 PKG=$B/rec-f1; newclone "$U" "$C" "$A"; mkdir -p "$PKG"
git -C "$C" cat-file -e "$M^{commit}" 2> /dev/null && ko "F1 precondition: the merge is already in the clone" || ok "F1 precondition: the merge is not in the clone before the fetch"
run F1 clone
reached && is "$RC" 0 "F1 exit" || ko "F1 did not reach the end"
is "$(git -C "$C" rev-parse HEAD)" "$M" "F1 HEAD after"
git -C "$C" symbolic-ref -q HEAD > /dev/null && ko "F1 HEAD is on a branch" || ok "F1 HEAD is detached"
cmp -s "$PKG/branches-before.txt" "$PKG/branches-after.txt" && ok "F1 branches unchanged" || ko "F1 branches"
echo "--- F2 the same clone again (HEAD already at the commit): passes, nothing moves"
export PKG=$B/rec-f2; mkdir -p "$PKG"; run F2 clone
reached && grep -q 'HEAD is already' "$CON" && is "$(git -C "$C" rev-parse HEAD)" "$M" "F2 HEAD still at the commit" || ko "F2"

echo "--- F3 the fetched tip is a DESCENDANT of the commit: accepted, the clone goes to the commit, not to the tip"
(cd "$U/seed" && echo later > docs/later.md && git add -A && git commit -q -m L && git push -q origin dev); (cd "$U/win" && git fetch -q origin)
L=$(git -C "$U/seed" rev-parse dev)
export C=$B/c3 PKG=$B/rec-f3; newclone "$U" "$C" "$A"; mkdir -p "$PKG"; run F3 clone
reached && grep -q "the fetched tip $L is a descendant" "$CON" && is "$(git -C "$C" rev-parse HEAD)" "$M" "F3 HEAD is the commit, the tip was $L" || ko "F3"

unchanged() {   # unchanged <label> <clone> <head expected>: nothing was fetched or moved
    is "$(git -C "$2" rev-parse HEAD)" "$3" "$1 HEAD unchanged"
    [ ! -e "$2/.git/FETCH_HEAD" ] && ok "$1 no FETCH_HEAD: nothing was fetched" || ko "$1 a FETCH_HEAD exists"
    git -C "$2" cat-file -e "$M^{commit}" 2> /dev/null && ko "$1 the merge commit is in the clone" || ok "$1 the merge commit is not in the clone"
}
echo "--- F4 a modified tracked file: STOP before the fetch, nothing discarded"
export C=$B/c4 PKG=$B/rec-f4; newclone "$U" "$C" "$A"; mkdir -p "$PKG"; echo "local work" >> "$C/docs/runbook.md"; SUM=$(sha256sum "$C/docs/runbook.md")
run F4 clone
stopped 'has local changes' && is "$RC" 1 "F4 exit" || ko "F4 not stopped"
unchanged F4 "$C" "$A"; is "$(sha256sum "$C/docs/runbook.md")" "$SUM" "F4 the local modification is intact"
echo "--- F5 an untracked file: STOP before the fetch"
export C=$B/c5 PKG=$B/rec-f5; newclone "$U" "$C" "$A"; mkdir -p "$PKG"; echo "note" > "$C/untracked.txt"
run F5 clone
stopped 'has local changes' && [ -f "$C/untracked.txt" ] && ok "F5 stopped, the untracked file is still there" || ko "F5"
unchanged F5 "$C" "$A"
echo "--- F6 a clean clone at another commit: STOP before the fetch"
export C=$B/c6 PKG=$B/rec-f6; newclone "$U" "$C" "$A"; mkdir -p "$PKG"
(cd "$C" && echo x > docs/x.md && git add -A && git commit -q -m X); X=$(git -C "$C" rev-parse HEAD)
run F6 clone
stopped 'neither' && ok "F6 stopped: neither of the two commits" || ko "F6"
unchanged F6 "$C" "$X"

echo "--- F7 the commit is in the clone but is NOT an ancestor of the fetched tip: STOP, HEAD stays"
Z=$(cd "$U/win" && git commit-tree -m Z -p "$A" "$A^{tree}"); git -C "$U/win" update-ref refs/remotes/origin/dev "$Z"
export C=$B/c1 PKG=$B/rec-f7; mkdir -p "$PKG"; run F7 clone
stopped 'neither the fetched tip' && is "$(git -C "$C" rev-parse HEAD)" "$M" "F7 HEAD unchanged" || ko "F7"
echo "--- F8 the commit is not in what the origin gives: STOP, the clone is still at the battery's commit"
export C=$B/c8 PKG=$B/rec-f8; newclone "$U" "$C" "$A"; mkdir -p "$PKG"; run F8 clone
stopped 'is not in the clone after the fetch' && is "$(git -C "$C" rev-parse HEAD)" "$A" "F8 HEAD unchanged" || ko "F8"

echo "--- F9 a merge whose reviewed head changes a file under tools/: STOP after the checkout"
U2=$B/u2; mkuniverse "$U2" tools/session/x.sh || exit 2
export BATTERY=$A IMAGE=$A REVIEWED=$R TOOLS=$M; TREE=$(git -C "$U2/seed" rev-parse "$M^{tree}")
export C=$B/c9 PKG=$B/rec-f9; newclone "$U2" "$C" "$A"; mkdir -p "$PKG"; run F9 clone
stopped 'a file under tools/' && ok "F9 stopped on the file under tools/" || ko "F9"
echo "--- F10 a merge whose reviewed head changes the controller: STOP (tools/src rule; the 'no rebuild' loop is behind it)"
U3=$B/u3; mkuniverse "$U3" src/egw_controller/main.py || exit 2
export BATTERY=$A IMAGE=$A REVIEWED=$R TOOLS=$M; TREE=$(git -C "$U3/seed" rev-parse "$M^{tree}")
export C=$B/c10 PKG=$B/rec-f10; newclone "$U3" "$C" "$A"; mkdir -p "$PKG"; run F10 clone
stopped 'under src/ outside src/tests' && ok "F10 stopped on the file under src/" || ko "F10"
echo "--- F11 the first repositories again, with an expected tree that is not the merge's: STOP"
export BATTERY=$A1 IMAGE=$A1 REVIEWED=$R1 TOOLS=$M1; TREE=$(git -C "$U/seed" rev-parse "$A1^{tree}")
git -C "$U/win" update-ref refs/remotes/origin/dev "$L"
export C=$B/c11 PKG=$B/rec-f11; newclone "$U" "$C" "$A1"; mkdir -p "$PKG"; run F11 clone
stopped 'is not at' && is "$(git -C "$C" rev-parse HEAD)" "$M1" "F11 stopped after the checkout: the tree differs" || ko "F11"

echo; echo "===== names: one identifier searched by name under the attempts directory and output_test ====="
export ATT=$B/n/attempts OT=$B/n/out id=itest-reboot-q2
mkdir -p "$ATT/20261003T142310Z_g3-qualification-t8_attempt01/console" "$OT/runs/2026-10-03/x/y" "$OT/decisions" "$OT/incomplete"
echo q1 > "$OT/runs/2026-10-03/x/y/itest-reboot-q1.boot_id.pre"
echo "--- N1 no name holds the identifier"
run N1 names; reached && is "$RC" 0 "N1 exit" || ko "N1"
echo "--- N2 the name only inside a sealed S3 preparation package (also with the suffix -attemptNN): not searched"
mkdir -p "$OT/runs/2026-10-04/HIST_2026-10-04-g3-t8t9-host-preparation/bench/record" "$OT/runs/2026-10-04/HIST_2026-10-04-g3-t8t9-host-preparation-attempt02/bench"
: > "$OT/runs/2026-10-04/HIST_2026-10-04-g3-t8t9-host-preparation/bench/record/itest-reboot-q2.boot_id.pre"
: > "$OT/runs/2026-10-04/HIST_2026-10-04-g3-t8t9-host-preparation-attempt02/bench/itest-reboot-q2.x"
run N2 names; reached && ok "N2 still fresh" || ko "N2"
echo "--- N3 a file of that name deep under output_test: STOP"
: > "$OT/runs/2026-10-03/x/y/itest-reboot-q2.boot_id.pre"
run N3 names; stopped 'a name holding itest-reboot-q2 exists' && grep -q 'x/y/itest-reboot-q2.boot_id.pre' "$CON" && ok "N3 stopped, the path is shown" || ko "N3"
rm "$OT/runs/2026-10-03/x/y/itest-reboot-q2.boot_id.pre"
echo "--- N4 a directory whose name holds it under the attempts directory: STOP"
mkdir "$ATT/20261003T142310Z_g3-qualification-t8_attempt01/console/007-itest-reboot-q2-step"
run N4 names; stopped 'a name holding itest-reboot-q2 exists' && ok "N4 stopped" || ko "N4"
rmdir "$ATT/20261003T142310Z_g3-qualification-t8_attempt01/console/007-itest-reboot-q2-step"
echo "--- N5 a root that cannot be searched: STOP (never read as fresh)"
ATT=$B/n/no-such-dir run N5 names; stopped 'could not be searched' && ok "N5 stopped" || ko "N5"

echo; echo "===== attempts: the earlier attempts of rows t8 and t9 ====="
export T8_ADMITTED=20261003T142310Z_g3-qualification-t8_attempt01
mkatt() {   # the battery's layout, reduced: three rows in the attempts directory and in output_test/runs
    export ATT=$1/attempts OT=$1/out PKG=$1/rec; mkdir -p "$PKG" "$OT/incomplete"
    for a in 2026-10-02/20261002T154427Z_g3-qualification-t2_attempt01 2026-10-03/20261003T140639Z_g3-qualification-t7-ditto_attempt01 2026-10-03/$T8_ADMITTED; do
        mkdir -p "$ATT/${a#*/}" "$OT/runs/$a"
    done
}
tool_number() {  # the name the export tool of the merged tree gives a new attempt of a row in this layout (in the bench tree)
    (cd "$S/pb/src" && "$REALPY" -m egw_experiments.local_export new --attempts-root "$ATT" --scenario "G3 qualification $1" --purpose official --dest-root "$OT") 2>&1 | tail -n 1
}
echo "--- G1 the battery's layout: admitted; the export tool then numbers t8 as attempt02 and t9 as attempt01"
mkatt "$B/g1"; run G1 attempts
reached && grep -q "row t8: $T8_ADMITTED found 2 time(s)" "$CON" && is "$RC" 0 "G1 exit" || ko "G1"
if [ -x "$REALPY" ]; then
    N8=$(tool_number t8); N9=$(tool_number t9)
    case $N8 in *_g3-qualification-t8_attempt02) ok "G1 the export tool numbered the new t8 attempt: ${N8##*/}" ;; *) ko "G1 export tool, t8: $N8" ;; esac
    case $N9 in *_g3-qualification-t9_attempt01) ok "G1 the export tool numbered the new t9 attempt: ${N9##*/}" ;; *) ko "G1 export tool, t9: $N9" ;; esac
    echo "--- G1b after those two attempts exist the same check refuses (a second preparation after a session started)"
    export PKG=$B/g1/rec2; mkdir -p "$PKG"; run G1b attempts
    stopped 'an attempt of row t8 other than' && [ "$(grep -c '^NOT ADMITTED' "$CON")" -eq 2 ] && ok "G1b both new attempts are named NOT ADMITTED" || ko "G1b"
else echo "NOT RUN: the export tool's numbering ($REALPY is not there)"; fi
echo "--- G2 an attempt02 of t8 in output_test/runs: STOP"
mkatt "$B/g2"; mkdir -p "$OT/runs/2026-10-05/20261005T100000Z_g3-qualification-t8_attempt02"; run G2 attempts
stopped 'an attempt of row t8 other than' && grep -q '^NOT ADMITTED (row t8): .*attempt02' "$CON" && ok "G2 stopped" || ko "G2"
echo "--- G3 an attempt of t9 in the attempts directory: STOP"
mkatt "$B/g3"; mkdir -p "$ATT/20261005T100000Z_g3-qualification-t9_attempt01"; run G3 attempts
stopped 'an attempt of row t8 other than' && grep -q '^NOT ADMITTED (row t9)' "$CON" && ok "G3 stopped" || ko "G3"
echo "--- G4 another attempt01 of t8 (another stamp) under output_test/incomplete: STOP"
mkatt "$B/g4"; mkdir -p "$OT/incomplete/20261004T090000Z_g3-qualification-t8_attempt01"; run G4 attempts
stopped 'an attempt of row t8 other than' && ok "G4 stopped" || ko "G4"
echo "--- G5 the admitted attempt is nowhere: STOP (the new one would not be attempt02)"
mkatt "$B/g5"; rmdir "$ATT/$T8_ADMITTED" "$OT/runs/2026-10-03/$T8_ADMITTED"; run G5 attempts
stopped 'would not be numbered attempt02' && ok "G5 stopped" || ko "G5"
echo "--- G6 no output_test/incomplete: said, and the check still passes"
mkatt "$B/g6"; rmdir "$OT/incomplete"; run G6 attempts
reached && grep -q 'incomplete (the export tool skips' "$CON" && ok "G6 passed" || ko "G6"

echo; echo "===== guest: the offline, read-only listing of the event directories (debugfs -c on a throw-away ext4 image) ====="
export IDS="itest-reboot-q2 itest-post-reboot-01-q2 itest-tls-wrongca-q2 itest-auth-wrongpw-q2 itest-notls-q2"
mkimg() {   # mkimg <name> <event directory names...>: an ext4 image holding /opt/egw/deployment/data/events/<names>
    local n=$1 d; shift
    rm -rf "$B/img-src"; mkdir -p "$B/img-src/opt/egw/deployment/data/events"
    for d in "$@"; do mkdir -p "$B/img-src/opt/egw/deployment/data/events/$d"; done
    /usr/sbin/mke2fs -q -t ext4 -d "$B/img-src" "$B/$n.ext4" 16M > /dev/null 2>&1 || return 1
    export ROOTFS=$B/$n.ext4 ROOTFS_SHA PKG=$B/rec-$n; ROOTFS_SHA=$(sha256sum "$ROOTFS" | cut -d' ' -f1); mkdir -p "$PKG"
}
if mkimg e1 itest-smoke-01-q1 itest-post-reboot-01 itest-reboot-q1; then
    echo "--- E1 earlier directories only: the five identifiers are fresh; the image is unchanged by the listing"
    run E1 guest
    reached && is "$(grep -c '^fresh on the guest: ' "$CON")" 5 "E1 identifiers reported fresh" || ko "E1"
    grep -q "^rootfs-ext4-after-listing: $ROOTFS_SHA " "$CON" && ok "E1 the image's sha256 after the listing is the one before" || ko "E1 image hash"
    grep -qx 'itest-smoke-01-q1' "$PKG/guest-events-names.txt" && ok "E1 the names file holds the directories of the image" || ko "E1 names"
    echo "--- E2 the smoke's directory exists: STOP"
    mkimg e2 itest-smoke-01-q1 itest-post-reboot-01-q2; run E2 guest
    stopped 'the guest holds data/events/itest-post-reboot-01-q2' && ok "E2 stopped" || ko "E2"
    echo "--- E3 a directory that starts with the prefix: STOP"
    mkimg e3 itest-reboot-q2-extra; run E3 guest
    stopped 'the guest holds an itest-reboot-q2' && ok "E3 stopped" || ko "E3"
    echo "--- E4 an image without the events directory: STOP (an empty listing is never read as fresh)"
    rm -rf "$B/img-src"; mkdir -p "$B/img-src/opt/egw"; /usr/sbin/mke2fs -q -t ext4 -d "$B/img-src" "$B/e4.ext4" 16M > /dev/null 2>&1
    export ROOTFS=$B/e4.ext4 PKG=$B/rec-e4; ROOTFS_SHA=$(sha256sum "$ROOTFS" | cut -d' ' -f1); mkdir -p "$PKG"; run E4 guest
    stopped "holds no '.' and '..' entries" && ok "E4 stopped" || ko "E4"
    echo "--- E5 no image at that path: STOP"
    export ROOTFS=$B/no-such.ext4 PKG=$B/rec-e5; mkdir -p "$PKG"; run E5 guest
    grep -q '^STOP: ' "$CON" && ! reached && ok "E5 stopped" || ko "E5"
else echo "NOT RUN: the guest fragment (mke2fs -d could not make an image)"; fi

echo; echo "===== summary: $pass PASS, $failn FAIL ====="
case $B in /tmp/g3-s3-hostfrag-*) rm -rf "$B"; echo "bench tree $B removed" ;; esac
[ "$failn" -eq 0 ]
