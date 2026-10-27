#!/bin/bash
# Independent check of the G3 battery's row files (written by g3_extract_rows.py).
# It restates the line ranges and the ids on its own (it does not take them from the
# manifest) and compares every row file with the lines of the frozen runbook blob,
# read with 'git show' from the clean clone. It READS only: the clone, the row files
# and the manifest; it writes no file anywhere, starts nothing and contacts nothing.
# Usage (WSL): bash g3_check_rows.sh <rows directory>
set -u
ROWS=${1:?usage: g3_check_rows.sh <rows directory>}
C=${EGW_EXEC_REPO:-$HOME/egw-exec/repo}
COMMIT=80e833f44f647fe9cd8f5e99d3abf3c444de95aa
RB=docs/setup/qemu_integrated_gateway.md
RB_SHA=c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae
bad=0
ok() { echo "ok    $*"; }
no() { echo "FAIL  $*"; bad=$((bad + 1)); }
blob() { git -C "$C" show "$COMMIT:$RB"; }
# orig <awk condition>: the blob's lines of that condition, the "host$ " prompt removed.
orig() { blob | awk "$1" | sed 's/^host\$ //'; }
count() { grep -oF -- "$1" "$2" | wc -l; }

echo "## the blob"
[ "$(git -C "$C" rev-parse HEAD)" = "$COMMIT" ] && ok "clone HEAD is $COMMIT" || no "clone HEAD"
[ "$(blob | sha256sum | cut -d' ' -f1)" = "$RB_SHA" ] && ok "runbook blob sha256 $RB_SHA" || no "runbook blob sha256"
[ "$(blob | wc -l)" = 1614 ] && ok "1614 lines" || no "line count"
[ "$(blob | awk 'NR>=1297&&NR<=1527' | grep -c -- '-q1')" = 0 ] && ok "no '-q1' in lines 1297-1527 of the blob" || no "the blob holds '-q1'"

# file | awk condition on the blob's line number | new id=count ... (the ids of the packet's section 2).
# '|' separates the fields, so t7-ditto's two ranges are joined with '+' (the sum of two truth values), not '||'.
TABLE='t1-smokes.sh|NR==1300|itest-smoke-$i-q1=2
t1-harness.sh|NR>=1310&&NR<=1313|
t2.sh|NR>=1325&&NR<=1337|itest-3dev-01-q1=1
t3.sh|NR>=1345&&NR<=1373|itest-invalid-01-q1=1
t4-replay.sh|NR>=1383&&NR<=1391|itest-dup-01-q1=1
t4-reset.sh|NR==1399|itest-dup-02-q1=1
t5.sh|NR>=1407&&NR<=1409|itest-dropout-01-q1=1
t6.sh|NR>=1421&&NR<=1427|
t7-mongo.sh|NR>=1439&&NR<=1461|itest-mongo-fault-01-q1=1
t7-ditto.sh|(NR>=1440&&NR<=1458)+(NR>=1477&&NR<=1480)|itest-ditto-fault-01-q1=1
t8-a-reboot.sh|NR>=1486&&NR<=1488|itest-reboot-q1=3
t8-b-return.sh|NR>=1489&&NR<=1490|
t8-c-snapshot.sh|NR==1491|itest-reboot-q1=5
t8-d-smoke.sh|NR==1492|itest-post-reboot-01-q1=1
t9-a.sh|NR>=1501&&NR<=1502|itest-tls-wrongca-q1=1
t9-b.sh|NR>=1503&&NR<=1516|itest-auth-wrongpw-q1=4
t9-c.sh|NR>=1517&&NR<=1519|itest-notls-q1=3
t9-de.sh|NR>=1520&&NR<=1526|'
OLD='itest-smoke-$i
itest-3dev-01
itest-invalid-01
itest-dup-01
itest-dup-02
itest-dropout-01
itest-mongo-fault-01
itest-ditto-fault-01
itest-reboot
itest-post-reboot-01
itest-tls-wrongca
itest-auth-wrongpw
itest-notls'
PROSE='t1-harness-analyze.sh|1320
t9-exposure.sh|1529'

echo "## the directory"
want=$( { echo "$TABLE" | cut -d'|' -f1 | sed 'p;s/$/.diff/'; echo "$PROSE" | cut -d'|' -f1; echo rows.manifest.json; } | sort)
have=$(ls -A "$ROWS" | sort)
[ "$want" = "$have" ] && ok "exactly the 39 expected files (20 steps, 18 diffs, the manifest)" || { no "directory listing"; diff <(echo "$want") <(echo "$have"); }

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
    # byte identity: with every '-q1' removed the file is the blob's lines, prompt removed
    if sed 's/-q1//g' "$f" | cmp -s - <(orig "$cond"); then ok "$name: without '-q1' it is byte-identical to the blob's lines ($cond)"; else no "$name: differs from the blob's lines"; fi
    total=0
    for pair in $ids; do
        new=${pair%=*}; n=${pair##*=}; total=$((total + n))
        [ "$(count "$new" "$f")" = "$n" ] && ok "$name: $new stands $n time(s)" || no "$name: $new stands $(count "$new" "$f") time(s), expected $n"
    done
    [ "$(count '-q1' "$f")" = "$total" ] && ok "$name: $total '-q1' in all, each one an id's" || no "$name: $(count '-q1' "$f") '-q1', expected $total"
    # the ids-only diff: its '-' lines are its '+' lines without '-q1'; its '+' lines are the file's lines that hold '-q1'
    d=$f.diff
    if [ "$total" = 0 ]; then
        [ ! -s "$d" ] && cmp -s "$f" <(orig "$cond") && ok "$name: no substitution, empty diff, the file is the blob's lines" || no "$name: diff of a file without substitution"
    else
        minus=$(tail -n +3 "$d" | grep '^-' | cut -c2-); plus=$(tail -n +3 "$d" | grep '^+' | cut -c2-)
        [ "$minus" = "$(printf '%s\n' "$plus" | sed 's/-q1//g')" ] && [ "$plus" = "$(grep -- '-q1' "$f")" ] \
            && [ "$minus" = "$(orig "$cond" | grep -F -f <(printf '%s\n' "$minus") -x)" ] \
            && ok "$name: the diff is ids-only ($(printf '%s\n' "$plus" | wc -l) line(s) changed)" || no "$name: the diff is not ids-only"
    fi
done <<< "$TABLE"

echo "## no old literal left without its '-q1' (all step files)"
while IFS= read -r old; do
    # as a token (word boundaries) and, stricter, as a plain string
    if grep -nP "(?<![A-Za-z0-9_])\\Q$old\\E(?![A-Za-z0-9_])(?!-q1(?![A-Za-z0-9_-]))" "$ROWS"/*.sh > /dev/null; then no "$old stands as a token without '-q1'"; fi
    if grep -nP "\\Q$old\\E(?!-q1(?![A-Za-z0-9_-]))" "$ROWS"/*.sh > /dev/null; then no "$old stands as a string without '-q1'"; else ok "$old: every occurrence is followed by '-q1' ($(cat "$ROWS"/*.sh | grep -oF -- "$old-q1" | wc -l) in all, t7's shared definitions hold none)"; fi
done <<< "$OLD"
pre=$bad
for lit in 'nominal-r02-q1' 'controller_restart-r03-q1' 'itest-acl-$T-q1' 'itest-replay-q1'; do
    grep -qF -- "$lit" "$ROWS"/*.sh && no "$lit: an id that must not change was changed"
done
[ "$bad" = "$pre" ] && ok "unchanged: nominal-r02 x$(cat "$ROWS"/t1-harness.sh | grep -oF 'nominal-r02' | wc -l) (t1-harness.sh), controller_restart-r03 x$(grep -oF 'controller_restart-r03' "$ROWS"/t6.sh | wc -l) (t6.sh), itest-acl-\$T x$(grep -oF 'itest-acl-$T' "$ROWS"/t9-de.sh | wc -l) (t9-de.sh), itest-replay x$(grep -oF 'itest-replay' "$ROWS"/t4-replay.sh | wc -l) (t4-replay.sh)"

echo "## t7-ditto.sh: its first 19 lines only define (traced in a bash with an empty PATH and no environment)"
trace=$(head -n 19 "$ROWS/t7-ditto.sh" | env -i PATH=/nonexistent "$(command -v bash)" --norc --noprofile -c 'set -T; trap '\''echo "TRACE: $BASH_COMMAND"'\'' DEBUG; . /dev/stdin; trap - DEBUG; set +T; declare -F; echo "R=[${R-}] SVC=[${SVC-}]"' 2>&1)
expect='TRACE: . /dev/stdin
TRACE: DC="cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env"
TRACE: trap - DEBUG
declare -f fault
declare -f fault_recover
declare -f readyp
declare -f svc_state
R=[] SVC=[]'
[ "$trace" = "$expect" ] && ok "one assignment (DC) and four function definitions (fault, fault_recover, readyp, svc_state); no other command ran" || { no "t7-ditto.sh definitions"; echo "$trace"; }
[ "$(sed -n '20p' "$ROWS/t7-ditto.sh")" = 'R=itest-ditto-fault-01-q1; SVC=ditto-things' ] && ok "line 20 is the Ditto repeat's first line" || no "t7-ditto.sh line 20"
cmp -s <(head -n 19 "$ROWS/t7-ditto.sh") <(sed -n '2,20p' "$ROWS/t7-mongo.sh") && ok "the 19 definition lines are lines 2-20 of t7-mongo.sh" || no "t7 definitions differ between the two files"

echo "## the prose-only step files"
while IFS='|' read -r name line; do
    f=$ROWS/$name
    if bash -n "$f" 2> /dev/null; then ok "$name: bash -n"; else no "$name: bash -n"; fi
    q=$(sed -n '4p' "$f" | sed 's/^#   "//; s/"$//')
    [ -n "$q" ] && [ "$(blob | awk "NR==$line" | grep -cF -- "$q")" = 1 ] && ok "$name: the sentence quoted on its line 4 stands on runbook line $line" || no "$name: quoted sentence"
    grep -qF -- '-q1' "$f" && no "$name holds '-q1'"
    grep -qE '^[^#]*(rm |mv |cp |tee |>[^&]|sudo|kill|systemctl|compose)' "$f" && no "$name: a command that is not a plain read"
done <<< "$PROSE"
[ "$(grep -v '^#' "$ROWS/t1-harness-analyze.sh" | head -n 1)" = "$(orig 'NR==1427'); echo \"analyze exit=\$?\"" ] && ok "t1-harness-analyze.sh: its analyze command is the runbook's fenced line 1427" || no "t1-harness-analyze.sh analyze command"
grep -v '^#' "$ROWS/t9-exposure.sh" | cut -d' ' -f1 | tr '\n' ' ' | grep -qx 'ssh ss ssh ' && ok "t9-exposure.sh: three commands (ssh, ss, ssh)" || no "t9-exposure.sh commands"

echo "## the manifest"
python3 - "$ROWS" <<'EOF' || bad=$((bad + 1))
import hashlib, json, os, sys
d = sys.argv[1]
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
if steps != list(m["files"]) or len(m["rows"]) != 12:
    bad += 1; print("FAIL  the rows table and the files disagree")
print("%s  manifest: %d files in %d rows, every sha256_after and diff_sha256 is the file's; rule checked against the frozen functions: %s"
      % ("ok   " if not bad else "FAIL ", len(m["files"]), len(m["rows"]), m["extraction_rule"]["checked_against_the_frozen_functions"]))
sys.exit(1 if bad else 0)
EOF
pre=$bad
while IFS='|' read -r name cond ids; do
    b=$(orig "$cond" | sha256sum | cut -d' ' -f1)
    m=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["files"][sys.argv[2]]["sha256_before"])' "$ROWS/rows.manifest.json" "$name")
    [ "$b" = "$m" ] || no "$name: sha256_before is not the sha256 of the blob's lines"
done <<< "$TABLE"
[ "$bad" = "$pre" ] && ok "manifest sha256_before of the 18 runbook files recomputed from the blob with awk and sed"

echo "## the clone, after"
[ "$(git -C "$C" --no-optional-locks status --porcelain | wc -l)" = 0 ] && [ "$(git -C "$C" rev-parse HEAD)" = "$COMMIT" ] && ok "clone clean at $COMMIT" || no "clone state"
echo
[ "$bad" = 0 ] && echo "ROW FILES OK (0 failures)" || echo "ROW FILES NOT OK ($bad failure(s))"
[ "$bad" = 0 ]
