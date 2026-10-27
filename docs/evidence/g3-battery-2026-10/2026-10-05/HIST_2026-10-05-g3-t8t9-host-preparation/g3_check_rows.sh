#!/bin/bash
# Independent check of the row files of G3 session S3 (tests 8 and 9; written by
# g3_extract_rows.py). It restates the line ranges and the ids on its own (it does not
# take them from the manifest) and compares every row file with the lines of the runbook
# blob of the merged commit 8e49261. It READS only: the blob, the row files and the
# manifest; it writes no file anywhere, starts nothing and contacts nothing.
#
# Two modes, by where the blob is read from. Which mode proves what:
#   clone mode (no --blob): the blob is read with 'git show <commit>:<runbook>' from the
#       clean clone ($EGW_EXEC_REPO, default ~/egw-exec/repo), whose HEAD must be the
#       commit before the checks and which must be clean at the commit after them. It
#       proves that the row files are the lines of the runbook THE EXECUTION CLONE HOLDS at
#       its checked-out commit, and that this clone is at 8e49261 and clean. It cannot pass
#       before the clone has moved to 8e49261.
#   blob mode (--blob <file>, or EGW_G3_RUNBOOK_BLOB=<file>): the blob is read from that
#       file, whose sha256 is asserted. It proves that the row files are the lines of A
#       FILE WITH THE PINNED SHA256 of the runbook at 8e49261, and nothing about any clone
#       (neither its HEAD nor its state): git is never called. For the preparation before
#       the clone moves; the clone-mode check is then still to be made, after the move.
# Usage (WSL): bash g3_check_rows.sh [--blob <runbook blob file>] <rows directory>
set -u
usage() {
    echo "usage: g3_check_rows.sh [--blob <runbook blob file>] <rows directory>" >&2
    echo "  without --blob (clone mode): the blob is read with git show from the clean clone, which must be at 8e49261 and clean;" >&2
    echo "      proves that the row files are the lines of the runbook the execution clone holds at its checked-out commit" >&2
    echo "  with --blob, or EGW_G3_RUNBOOK_BLOB (blob mode): the blob is that file, its sha256 asserted;" >&2
    echo "      proves that the row files are the lines of a file with the pinned sha256, and nothing about any clone" >&2
    exit 2
}
BLOB=${EGW_G3_RUNBOOK_BLOB:-}
ROWS=
while [ $# -gt 0 ]; do
    case $1 in
        --blob) [ $# -ge 2 ] && [ -n "$2" ] || usage; BLOB=$2; shift 2 ;;
        --blob=?*) BLOB=${1#--blob=}; shift ;;
        -*) usage ;;
        *) [ -z "$ROWS" ] || usage; ROWS=$1; shift ;;
    esac
done
[ -n "$ROWS" ] || usage
C=${EGW_EXEC_REPO:-$HOME/egw-exec/repo}
COMMIT=8e492613d36490a560ae56beabd6d5c2c01a8696
RB=docs/setup/qemu_integrated_gateway.md
RB_SHA=4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db
bad=0
ok() { echo "ok    $*"; }
no() { echo "FAIL  $*"; bad=$((bad + 1)); }
if [ -n "$BLOB" ]; then
    blob() { cat -- "$BLOB"; }
else
    blob() { git -C "$C" show "$COMMIT:$RB"; }
fi
# orig <awk condition>: the blob's lines of that condition, the "host$ " prompt removed.
orig() { blob | awk "$1" | sed 's/^host\$ //'; }
count() { grep -oF -- "$1" "$2" | wc -l; }

echo "## the blob"
if [ -n "$BLOB" ]; then
    echo "blob mode: the blob is the file $BLOB; no clone is read, so nothing below shows a clone's HEAD or state"
    [ -f "$BLOB" ] && [ -r "$BLOB" ] && ok "the blob file is a readable regular file" || { no "the blob file is not a readable regular file"; echo; echo "ROW FILES NOT OK ($bad failure(s); blob mode: nothing was compared)"; exit 1; }
else
    echo "clone mode: the blob is read with git show from the clone $C"
    [ "$(git -C "$C" rev-parse HEAD)" = "$COMMIT" ] && ok "clone HEAD is $COMMIT" || no "clone HEAD"
fi
[ "$(blob | sha256sum | cut -d' ' -f1)" = "$RB_SHA" ] && ok "runbook blob sha256 $RB_SHA" || no "runbook blob sha256"
[ "$(blob | wc -l)" = 1623 ] && ok "1623 lines" || no "line count"
[ "$(blob | grep -c -- '-q2')" = 0 ] && ok "no '-q2' in the blob" || no "the blob holds '-q2'"
[ "$(blob | awk '(NR>=1486&&NR<=1500)+(NR>=1509&&NR<=1534)' | grep -c -- '-q1')" = 0 ] && ok "no '-q1' in lines 1486-1500 and 1509-1534 of the blob (the lines of the step files)" || no "the blob's lines of the step files hold '-q1'"

# file | awk condition on the blob's line number | new id=count ... (the ids of the request's section 3).
TABLE='t8-a-reboot.sh|NR>=1486&&NR<=1495|itest-reboot-q2=15
t8-b-wait-boot-id.sh|NR==1496|itest-reboot-q2=8
t8-c-unaided.sh|NR==1497|itest-reboot-q2=32
t8-d-tunnel.sh|NR==1498|
t8-e-state.sh|NR==1499|itest-reboot-q2=5
t8-f-smoke.sh|NR==1500|itest-post-reboot-01-q2=1
t9-a.sh|NR>=1509&&NR<=1510|itest-tls-wrongca-q2=1
t9-b.sh|NR>=1511&&NR<=1524|itest-auth-wrongpw-q2=4
t9-c.sh|NR>=1525&&NR<=1527|itest-notls-q2=3
t9-de.sh|NR>=1528&&NR<=1534|'
OLD='itest-reboot
itest-post-reboot-01
itest-tls-wrongca
itest-auth-wrongpw
itest-notls'
PROSE='t9-exposure.sh|1537'

echo "## the directory"
want=$( { echo "$TABLE" | cut -d'|' -f1 | sed 'p;s/$/.diff/'; echo "$PROSE" | cut -d'|' -f1; echo rows.manifest.json; } | sort)
have=$(ls -A "$ROWS" | sort)
[ "$want" = "$have" ] && ok "exactly the 22 expected files (11 steps, 10 diffs, the manifest)" || { no "directory listing"; diff <(echo "$want") <(echo "$have"); }

echo "## every file: LF only, one final newline, UTF-8"
pre=$bad
for f in "$ROWS"/*; do
    n=$(basename "$f")
    grep -q $'\r' "$f" && no "$n holds a carriage return"
    [ -s "$f" ] || { case $n in *.diff) continue ;; *) no "$n is empty" ;; esac; }
    [ "$(tail -c 1 "$f" | od -An -tx1 | tr -d ' ')" = 0a ] || no "$n does not end with a newline"
    iconv -f UTF-8 -t UTF-8 "$f" > /dev/null 2>&1 || no "$n is not UTF-8"
done
[ "$bad" = "$pre" ] && ok "no CR, final newline, UTF-8 in $(ls -A "$ROWS" | wc -l) files (the empty diffs are those of the files without a substitution)"

echo "## the runbook step files"
while IFS='|' read -r name cond ids; do
    f=$ROWS/$name
    if bash -n "$f" 2> /dev/null; then ok "$name: bash -n"; else no "$name: bash -n"; fi
    # byte identity: with every '-q2' removed the file is the blob's lines, prompt removed
    if sed 's/-q2//g' "$f" | cmp -s - <(orig "$cond"); then ok "$name: without '-q2' it is byte-identical to the blob's lines ($cond)"; else no "$name: differs from the blob's lines"; fi
    total=0
    for pair in $ids; do
        new=${pair%=*}; n=${pair##*=}; total=$((total + n))
        [ "$(count "$new" "$f")" = "$n" ] && ok "$name: $new stands $n time(s)" || no "$name: $new stands $(count "$new" "$f") time(s), expected $n"
    done
    [ "$(count '-q2' "$f")" = "$total" ] && ok "$name: $total '-q2' in all, each one an id's" || no "$name: $(count '-q2' "$f") '-q2', expected $total"
    # the ids-only diff: its '-' lines are its '+' lines without '-q2'; its '+' lines are the file's lines that hold '-q2'
    d=$f.diff
    if [ "$total" = 0 ]; then
        [ ! -s "$d" ] && cmp -s "$f" <(orig "$cond") && ok "$name: no substitution, empty diff, the file is the blob's lines" || no "$name: diff of a file without substitution"
    else
        minus=$(tail -n +3 "$d" | grep '^-' | cut -c2-); plus=$(tail -n +3 "$d" | grep '^+' | cut -c2-)
        [ "$minus" = "$(printf '%s\n' "$plus" | sed 's/-q2//g')" ] && [ "$plus" = "$(grep -- '-q2' "$f")" ] \
            && [ "$minus" = "$(orig "$cond" | grep -F -f <(printf '%s\n' "$minus") -x)" ] \
            && ok "$name: the diff is ids-only ($(printf '%s\n' "$plus" | wc -l) line(s) changed)" || no "$name: the diff is not ids-only"
    fi
done <<< "$TABLE"

echo "## no old literal left without its '-q2' (all step files)"
while IFS= read -r old; do
    # as a token (word boundaries) and, stricter, as a plain string
    if grep -nP "(?<![A-Za-z0-9_])\\Q$old\\E(?![A-Za-z0-9_])(?!-q2(?![A-Za-z0-9_-]))" "$ROWS"/*.sh > /dev/null; then no "$old stands as a token without '-q2'"; fi
    if grep -nP "\\Q$old\\E(?!-q2(?![A-Za-z0-9_-]))" "$ROWS"/*.sh > /dev/null; then no "$old stands as a string without '-q2'"; else ok "$old: every occurrence is followed by '-q2' ($(cat "$ROWS"/*.sh | grep -oF -- "$old-q2" | wc -l) in all)"; fi
done <<< "$OLD"
# S3: no id of the battery (sessions S1 and S2, suffix '-q1') may stand in a step file.
if grep -qF -- '-q1' "$ROWS"/*.sh; then no "a step file holds '-q1', the suffix of the battery's ids: $(grep -lF -- '-q1' "$ROWS"/*.sh | xargs -n 1 basename | tr '\n' ' ')"; else ok "no '-q1' (the suffix of the battery's ids) in any step file"; fi
pre=$bad
for lit in 'itest-acl-$T-q2'; do
    grep -qF -- "$lit" "$ROWS"/*.sh && no "$lit: an id that must not change was changed"
done
[ "$(grep -oF 'itest-acl-$T' "$ROWS"/t9-de.sh | wc -l)" = 11 ] || no "itest-acl-\$T does not stand 11 times in t9-de.sh"
[ "$bad" = "$pre" ] && ok "unchanged: itest-acl-\$T x$(grep -oF 'itest-acl-$T' "$ROWS"/t9-de.sh | wc -l) (t9-de.sh)"

echo "## the prose-only step file"
while IFS='|' read -r name line; do
    f=$ROWS/$name
    if bash -n "$f" 2> /dev/null; then ok "$name: bash -n"; else no "$name: bash -n"; fi
    # S3: its header names the merged commit, the blob's sha256 and the sentence's line.
    sed -n '3p' "$f" | grep -qF -- "# It derives from $RB at ${COMMIT:0:7} (sha256 $RB_SHA), line $line (" && ok "$name: its line 3 names $RB at ${COMMIT:0:7}, sha256 $RB_SHA, line $line" || no "$name: line 3 does not name the commit, the sha256 and line $line"
    q=$(sed -n '4p' "$f" | sed 's/^#   "//; s/"$//')
    [ -n "$q" ] && [ "$(blob | awk "NR==$line" | grep -cF -- "$q")" = 1 ] && ok "$name: the sentence quoted on its line 4 stands on runbook line $line" || no "$name: quoted sentence"
    grep -qF -- '-q2' "$f" && no "$name holds '-q2'"
    grep -qE '^[^#]*(rm |mv |cp |tee |>[^&]|sudo|kill|systemctl|compose)' "$f" && no "$name: a command that is not a plain read"
done <<< "$PROSE"
grep -v '^#' "$ROWS/t9-exposure.sh" | cut -d' ' -f1 | tr '\n' ' ' | grep -qx 'ssh ss ssh ' && ok "t9-exposure.sh: three commands (ssh, ss, ssh)" || no "t9-exposure.sh commands"

echo "## the manifest"
python3 - "$ROWS" "$COMMIT" "$RB" "$RB_SHA" <<'EOF' || bad=$((bad + 1))
import hashlib, json, os, sys
d, commit, rb, rb_sha = sys.argv[1:5]
m = json.load(open(os.path.join(d, "rows.manifest.json"), encoding="utf-8"))
sha = lambda p: hashlib.sha256(open(os.path.join(d, p), "rb").read()).hexdigest()
bad = 0
for name, e in m["files"].items():
    if sha(name) != e["sha256_after"]:
        bad += 1; print("FAIL  %s: sha256_after" % name)
    if e["diff"] is not None and sha(e["diff"]) != e["diff_sha256"]:
        bad += 1; print("FAIL  %s: diff_sha256" % name)
    if e["kind"] == "runbook" and (e["sha256_before"] == e["sha256_after"]) != (not e["substitutions"]):
        bad += 1; print("FAIL  %s: before/after hashes and the substitution map disagree" % name)
steps = [f for r in m["rows"] for f in r["steps"]]
if steps != list(m["files"]) or len(m["rows"]) != 2:
    bad += 1; print("FAIL  the rows table and the files disagree")
# S3: the runbook identity, the suffix and the session label the steps script will require.
if m["runbook"] != {"commit": commit, "path": rb, "sha256": rb_sha, "lines": 1623}:
    bad += 1; print("FAIL  the manifest's runbook identity is not %s, %s, 1623 lines" % (commit, rb_sha))
if m["substitution_rule"]["suffix"] != "-q2":
    bad += 1; print("FAIL  the manifest's suffix is not '-q2'")
if [(r["row"], r["session"]) for r in m["rows"]] != [("t8", "S3"), ("t9", "S3")] or any(e["session"] != "S3" for e in m["files"].values()):
    bad += 1; print("FAIL  the manifest's rows are not t8 and t9 of session S3")
print("%s  manifest: %d files in %d rows (%s; session S3), runbook %s, suffix %s; every sha256_after and diff_sha256 is the file's; rule checked against the frozen functions: %s"
      % ("ok   " if not bad else "FAIL ", len(m["files"]), len(m["rows"]), ", ".join(r["row"] for r in m["rows"]), m["runbook"]["commit"][:7],
         m["substitution_rule"]["suffix"], m["extraction_rule"]["checked_against_the_frozen_functions"]))
sys.exit(1 if bad else 0)
EOF
pre=$bad
while IFS='|' read -r name cond ids; do
    b=$(orig "$cond" | sha256sum | cut -d' ' -f1)
    m=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["files"][sys.argv[2]]["sha256_before"])' "$ROWS/rows.manifest.json" "$name")
    [ "$b" = "$m" ] || no "$name: sha256_before is not the sha256 of the blob's lines"
done <<< "$TABLE"
[ "$bad" = "$pre" ] && ok "manifest sha256_before of the 10 runbook files recomputed from the blob with awk and sed"

if [ -n "$BLOB" ]; then
    echo "## the clone: NOT read (blob mode)"
    echo "note  the row files were compared with a file of the pinned sha256, not with the execution clone: repeat without --blob once the clone is at $COMMIT"
    mode="blob mode: against a file with the pinned sha256; no clone was read"
else
    echo "## the clone, after"
    [ "$(git -C "$C" --no-optional-locks status --porcelain | wc -l)" = 0 ] && [ "$(git -C "$C" rev-parse HEAD)" = "$COMMIT" ] && ok "clone clean at $COMMIT" || no "clone state"
    mode="clone mode: against the clone $C"
fi
echo
[ "$bad" = 0 ] && echo "ROW FILES OK (0 failures; $mode)" || echo "ROW FILES NOT OK ($bad failure(s); $mode)"
[ "$bad" = 0 ]
