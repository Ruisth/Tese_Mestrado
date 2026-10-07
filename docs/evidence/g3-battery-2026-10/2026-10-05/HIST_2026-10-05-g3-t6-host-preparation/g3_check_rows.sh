#!/bin/bash
# Independent check of the row files of G3 session S4 (test 6 only; written by
# g3_extract_rows.py). It restates the line range and the literals on its own (it does not
# take them from the manifest) and compares the row file with the lines of the runbook
# blob of the merged commit 1fd9792. It READS only: the blob, the row files and the
# manifest; it writes no file anywhere, starts nothing and contacts nothing.
#
# Two modes, by where the blob is read from. Which mode proves what:
#   clone mode (no --blob): the blob is read with 'git show <commit>:<runbook>' from the
#       clean clone ($EGW_EXEC_REPO, default ~/egw-exec/repo), whose HEAD must be the
#       commit before the checks and which must be clean at the commit after them. It
#       proves that the row files are the lines of the runbook THE EXECUTION CLONE HOLDS at
#       its checked-out commit, and that this clone is at 1fd9792 and clean. It cannot pass
#       before the clone has moved to 1fd9792.
#   blob mode (--blob <file>, or EGW_G3_RUNBOOK_BLOB=<file>): the blob is read from that
#       file, whose sha256 is asserted. It proves that the row files are the lines of A
#       FILE WITH THE PINNED SHA256 of the runbook at 1fd9792, and nothing about any clone
#       (neither its HEAD nor its state): git is never called. For the preparation before
#       the clone moves; the clone-mode check is then still to be made, after the move.
# Usage (WSL): bash g3_check_rows.sh [--blob <runbook blob file>] <rows directory>
set -u
usage() {
    echo "usage: g3_check_rows.sh [--blob <runbook blob file>] <rows directory>" >&2
    echo "  without --blob (clone mode): the blob is read with git show from the clean clone, which must be at 1fd9792 and clean;" >&2
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
# S4 (brief, stream ROWS, checker: "commit, hash, line table, file list"): the merged commit, its
# runbook blob (1,624 lines, asserted below) and, further down, the one-file table.
COMMIT=1fd9792bb76f02c6948f33887207dba4837202db
RB=docs/setup/qemu_integrated_gateway.md
RB_SHA=317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f
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
[ "$(blob | wc -l)" = 1624 ] && ok "1624 lines" || no "line count"
[ "$(blob | grep -c -- '-q2')" = 0 ] && ok "no '-q2' in the blob" || no "the blob holds '-q2'"
# S4: neither earlier session's suffix ('-q1': S1 and S2; '-q2': S3) in the lines of the step file.
[ "$(blob | awk 'NR>=1421&&NR<=1428' | grep -c -- '-q[12]')" = 0 ] && ok "no '-q1' and no '-q2' in lines 1421-1428 of the blob (the lines of the step file)" || no "the blob's lines of the step file hold '-q1' or '-q2'"
# S4: lines 1421-1428 are test 6's whole fenced block: its heading on 1416, the fence opened on
# 1420 and closed on 1429 (no other fence before test 7's heading on 1437), eight host$ lines.
[ "$(blob | awk 'NR==1416' | grep -c '^### Test 6 ')" = 1 ] && [ "$(blob | awk 'NR==1437' | grep -c '^### Test 7 ')" = 1 ] \
    && [ "$(blob | awk 'NR>=1417&&NR<=1436' | grep -n '^```' | cut -d: -f1 | tr '\n' ' ')" = '4 13 ' ] \
    && [ "$(blob | awk 'NR>=1421&&NR<=1428' | grep -c '^host\$ ')" = 8 ] \
    && ok "test 6's heading on line 1416, its one fence opened on 1420 and closed on 1429 (test 7's heading on 1437), eight host\$ lines 1421-1428" \
    || no "test 6's heading, fence or host\$ lines are not on lines 1416, 1420, 1429 and 1421-1428"

# file | awk condition on the blob's line number | new id=count ... (S4: none; nothing is substituted).
TABLE='t6.sh|NR>=1421&&NR<=1428|'

echo "## the directory"
want=$( { echo "$TABLE" | cut -d'|' -f1 | sed 'p;s/$/.diff/'; echo rows.manifest.json; } | sort)
have=$(ls -A "$ROWS" | sort)
[ "$want" = "$have" ] && ok "exactly the 3 expected files (1 step, 1 diff, the manifest)" || { no "directory listing"; diff <(echo "$want") <(echo "$have"); }

echo "## every file: LF only, one final newline, UTF-8"
pre=$bad
for f in "$ROWS"/*; do
    n=$(basename "$f")
    grep -q $'\r' "$f" && no "$n holds a carriage return"
    [ -s "$f" ] || { case $n in *.diff) continue ;; *) no "$n is empty" ;; esac; }
    [ "$(tail -c 1 "$f" | od -An -tx1 | tr -d ' ')" = 0a ] || no "$n does not end with a newline"
    iconv -f UTF-8 -t UTF-8 "$f" > /dev/null 2>&1 || no "$n is not UTF-8"
done
[ "$bad" = "$pre" ] && ok "no CR, final newline, UTF-8 in $(ls -A "$ROWS" | wc -l) files (the empty diff is that of the file without a substitution)"

echo "## the runbook step files"
while IFS='|' read -r name cond ids; do
    f=$ROWS/$name
    if bash -n "$f" 2> /dev/null; then ok "$name: bash -n"; else no "$name: bash -n"; fi
    # byte identity. S4 (no substitution): the file itself is the blob's lines, prompt removed
    if cmp -s "$f" <(orig "$cond"); then ok "$name: byte-identical to the blob's lines ($cond), the prompt removed"; else no "$name: differs from the blob's lines"; fi
    total=0
    for pair in $ids; do
        new=${pair%=*}; n=${pair##*=}; total=$((total + n))
        [ "$(count "$new" "$f")" = "$n" ] && ok "$name: $new stands $n time(s)" || no "$name: $new stands $(count "$new" "$f") time(s), expected $n"
    done
    [ "$(count '-q2' "$f")" = "$total" ] && ok "$name: $total '-q2' in all, each one an id's" || no "$name: $(count '-q2' "$f") '-q2', expected $total"
    # the ids-only diff: its '-' lines are its '+' lines without '-q2'; its '+' lines are the file's lines that hold '-q2'
    # (S4: the table names no id, so total is 0 and the second branch is not reached)
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

# S4 (brief, stream ROWS): no identifier substitution - controller_restart-r04 is the runbook's
# own literal; the three changes of the merged block against the battery's are restated by line.
echo "## the run id, the literals and the three changes of the merged block (t6.sh; nothing substituted)"
f=$ROWS/t6.sh
l1=$(sed -n '1p' "$f"); l5=$(sed -n '5p' "$f"); l7=$(sed -n '7p' "$f")
[ "$(wc -l < "$f")" = 8 ] && ok "t6.sh: 8 lines" || no "t6.sh: $(wc -l < "$f") lines, 8 expected"
case $l1 in
    'RID=controller_restart-r04; F6=used; '*) [ "$(count 'controller_restart-r04' "$f")" = 1 ] && ok "t6.sh: controller_restart-r04 stands once, opening line 1 ('RID=controller_restart-r04; F6=used; ...')" || no "t6.sh: controller_restart-r04 stands $(count 'controller_restart-r04' "$f") time(s), 1 expected" ;;
    *) no "t6.sh: line 1 does not open with 'RID=controller_restart-r04; F6=used; '" ;;
esac
[ "$(grep -oE '(nominal|controller_restart|smoke_sequence)-r[0-9][0-9]' "$f" | sort | tr '\n' ' ')" = 'controller_restart-r01 controller_restart-r04 ' ] \
    && ok "t6.sh: the plan-entry literals are controller_restart-r01 (line 1's comment) and controller_restart-r04, once each" \
    || no "t6.sh: the plan-entry literals are $(grep -oE '(nominal|controller_restart|smoke_sequence)-r[0-9][0-9]' "$f" | sort | tr '\n' ' ')"
[ "$(grep -cE 'itest-[A-Za-z0-9$-]*[A-Za-z0-9$]' "$f")" = 0 ] && ok "t6.sh: no itest id" || no "t6.sh holds an itest id"
if grep -qE -- '-q[12]' "$ROWS"/*.sh; then no "a step file holds '-q1' or '-q2', the suffix of an earlier session's ids: $(grep -lE -- '-q[12]' "$ROWS"/*.sh | xargs -n 1 basename | tr '\n' ' ')"; else ok "no '-q1' (sessions S1 and S2) and no '-q2' (session S3) in any step file"; fi
case $l5 in
    *' --restart-transition-rule 1a-option-a-2026-10-05; HR=$?; '*) [ "$(grep -c -- '--restart-transition-rule' "$f")" = 1 ] && ok "t6.sh: line 5, and no other line, hands the harness '--restart-transition-rule 1a-option-a-2026-10-05'" || no "t6.sh: --restart-transition-rule stands on more than line 5" ;;
    *) no "t6.sh: line 5 does not hand the harness '--restart-transition-rule 1a-option-a-2026-10-05'" ;;
esac
case $l7 in
    '[ "$T6" = ok ] && $REC acceptance $RAW6/logs/simulator/$RID --events $RAW6/events.post-drain.jsonl --exactly-once || stop '*) [ "$(grep -c -- 'acceptance \$RAW6' "$f")" = 1 ] && ok "t6.sh: line 7, and no other line, is the exactly-once check of the post-drain copy, run only when T6=ok" || no "t6.sh: the acceptance check stands on more than line 7" ;;
    *) no "t6.sh: line 7 is not '[ \"\$T6\" = ok ] && \$REC acceptance ... --exactly-once || stop ...'" ;;
esac
[ "$(grep -c 'STOP:' "$f")" = 0 ] && ok "t6.sh holds no 'STOP:' text (a line of its console that opens with 'STOP:' is the helpers' stop)" || no "t6.sh holds 'STOP:' text"

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
if steps != list(m["files"]) or len(m["rows"]) != 1:
    bad += 1; print("FAIL  the rows table and the files disagree")
# S4: the runbook identity, no substitution and the session label the steps script will require.
if m["runbook"] != {"commit": commit, "path": rb, "sha256": rb_sha, "lines": 1624}:
    bad += 1; print("FAIL  the manifest's runbook identity is not %s, %s, 1624 lines" % (commit, rb_sha))
if m["substitution_rule"]["suffix"] is not None or m["substitution_rule"]["ids"] != []:
    bad += 1; print("FAIL  the manifest's substitution rule is not 'none' (no suffix, no id)")
for name, e in m["files"].items():
    if e["sha256_before"] != e["sha256_after"] or e["substitutions"] or e["diff_bytes"] != 0:
        bad += 1; print("FAIL  %s: the manifest records a substitution or a non-empty diff" % name)
if [(r["row"], r["session"]) for r in m["rows"]] != [("t6", "S4")] or any(e["session"] != "S4" for e in m["files"].values()):
    bad += 1; print("FAIL  the manifest's rows are not t6 of session S4")
print("%s  manifest: %d file(s) in %d row(s) (%s; session S4), runbook %s, substitution: %s; every sha256_after and diff_sha256 is the file's; rule checked against the frozen functions: %s"
      % ("ok   " if not bad else "FAIL ", len(m["files"]), len(m["rows"]), ", ".join(r["row"] for r in m["rows"]), m["runbook"]["commit"][:7],
         "none" if m["substitution_rule"]["suffix"] is None else m["substitution_rule"]["suffix"], m["extraction_rule"]["checked_against_the_frozen_functions"]))
sys.exit(1 if bad else 0)
EOF
pre=$bad
while IFS='|' read -r name cond ids; do
    b=$(orig "$cond" | sha256sum | cut -d' ' -f1)
    m=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["files"][sys.argv[2]]["sha256_before"])' "$ROWS/rows.manifest.json" "$name")
    [ "$b" = "$m" ] || no "$name: sha256_before is not the sha256 of the blob's lines"
done <<< "$TABLE"
[ "$bad" = "$pre" ] && ok "manifest sha256_before of the 1 runbook file recomputed from the blob with awk and sed"

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
