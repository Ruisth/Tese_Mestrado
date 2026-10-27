#!/bin/bash
# Proofs about the row file of G3 session S4, made apart from g3_extract_rows.py and from
# g3_check_rows.sh (other tools: python slicing of the blob's bytes and sed line addresses,
# instead of the checker's awk). It READS only (the row files, the battery's t6.sh, its
# sealed copies, the runbook blob) and writes nothing.
#   1. t6.sh is the runbook blob's lines 1421-1428 with the 'host$ ' prompt removed, byte for
#      byte, and those eight lines are the whole fenced block of test 6 (1420 opens it, 1429
#      closes it); t6.sh.diff is empty.
#   2. The battery's t6.sh (80e833f, seven lines) against the new t6.sh: the diff is exactly
#      the changed RID line, the changed harness line and the added exactly-once line (new
#      lines 1, 5 and 7); every other line is unchanged; the changed spans of lines 1 and 5,
#      in the command and in its trailing comment.
#   3. The battery's t6.sh is the file the first preparation sealed and the file session S2
#      ran (its attempt's environment copy).
# Usage (WSL): bash rows-proofs.sh <rows directory> <the battery's t6.sh> <runbook blob file> <sealed copy>...
set -u
USAGE='usage: rows-proofs.sh <rows directory> <the battery t6.sh> <runbook blob file> <sealed copy>...'
ROWS=${1:?$USAGE}
OLD=${2:?$USAGE}
BLOB=${3:?$USAGE}
shift 3
bad=0
sha() { sha256sum | cut -d' ' -f1; }

echo "## inputs"
echo "runbook blob: sha256 $(sha < "$BLOB"), $(wc -l < "$BLOB") lines"
echo "S4 t6.sh: sha256 $(sha < "$ROWS/t6.sh"), $(wc -l < "$ROWS/t6.sh") lines, $(wc -c < "$ROWS/t6.sh") bytes"
echo "the battery's t6.sh ($OLD): sha256 $(sha < "$OLD"), $(wc -l < "$OLD") lines, $(wc -c < "$OLD") bytes"

echo
echo "## 1. t6.sh = runbook lines 1421-1428, the prompt removed, byte for byte"
python3 - "$ROWS" "$BLOB" <<'EOF' || bad=$((bad + 1))
import hashlib, os, sys
rows, blob = sys.argv[1], sys.argv[2]
lines = open(blob, "rb").read().split(b"\n")
src = lines[1420:1428]
prompts = sum(1 for ln in src if ln.startswith(b"host$ "))
want = b"\n".join(ln[len(b"host$ "):] for ln in src) + b"\n"
data = open(os.path.join(rows, "t6.sh"), "rb").read()
bad = 0
same = data == want and prompts == 8
bad += not same
print("%s  t6.sh: runbook lines 1421-1428 (8 lines, %d with the prompt), prompt removed: sha256 %s, %d bytes; t6.sh: sha256 %s, %d bytes"
      % ("IDENTICAL" if same else "DIFFERENT", prompts, hashlib.sha256(want).hexdigest(), len(want), hashlib.sha256(data).hexdigest(), len(data)))
fence = lines[1419] == b"```bash" and lines[1428] == b"```" and lines[1415].startswith(b"### Test 6 ")
bad += not fence
print("%s  the fence: line 1420 %r, line 1429 %r, heading on line 1416 %r" % ("WHOLE BLOCK" if fence else "NOT THE BLOCK", lines[1419].decode(), lines[1428].decode(), lines[1415].decode()))
d = os.path.getsize(os.path.join(rows, "t6.sh.diff"))
bad += d != 0
print("%s  t6.sh.diff: %d bytes" % ("EMPTY" if d == 0 else "NOT EMPTY", d))
sys.exit(1 if bad else 0)
EOF
if sed -n '1421,1428p' "$BLOB" | sed 's/^host\$ //' | cmp -s - "$ROWS/t6.sh"; then echo "IDENTICAL  the same with sed: sed -n '1421,1428p' | sed 's/^host\\\$ //' | cmp - t6.sh: no difference"; else echo "DIFFERENT  sed and cmp"; bad=$((bad + 1)); fi

echo
echo "## 2. the battery's t6.sh (80e833f, seven lines) against S4's t6.sh: diff (battery '<', S4 '>'), each line cut at 200 characters"
diff "$OLD" "$ROWS/t6.sh" | cut -c1-200
echo "diff exit=${PIPESTATUS[0]} (1: the files differ)"
hunks=$(diff "$OLD" "$ROWS/t6.sh" | grep -v '^[<>-]' | tr '\n' ' ')
echo "hunk headers: $hunks"
if [ "$hunks" = "1c1 5c5 6a7 " ]; then echo "EXACTLY THREE  the changed RID line (1c1), the changed harness line (5c5) and the added line 7 (6a7)"; else echo "NOT THE THREE EXPECTED HUNKS"; bad=$((bad + 1)); fi
echo "unified hunk header: $(diff -u "$OLD" "$ROWS/t6.sh" | grep '^@@')"
python3 - "$OLD" "$ROWS/t6.sh" <<'EOF' || bad=$((bad + 1))
import difflib, hashlib, sys
old = open(sys.argv[1], "rb").read().decode("utf-8").split("\n")[:-1]
new = open(sys.argv[2], "rb").read().decode("utf-8").split("\n")[:-1]
bad = 0
pairs = [(2, 2), (3, 3), (4, 4), (6, 6), (7, 8)]
for a, b in pairs:
    same = old[a - 1] == new[b - 1]
    bad += not same
    print("%s  battery line %d = S4 line %d (%d characters, sha256 %s)" % ("UNCHANGED" if same else "CHANGED", a, b, len(new[b - 1]),
          hashlib.sha256(new[b - 1].encode()).hexdigest()[:16]))
added = new[6]
ok7 = added.startswith('[ "$T6" = ok ] && $REC acceptance $RAW6/logs/simulator/$RID --events $RAW6/events.post-drain.jsonl --exactly-once || stop ')
bad += not ok7
print("%s  S4 line 7 (added, %d characters) opens with the exactly-once check, run only when T6=ok" % ("ADDED" if ok7 else "NOT AS EXPECTED", len(added)))
# where each line's trailing comment starts: the first '    #' (four spaces and a hash) after the command
for a, b, label in ((1, 1, "the RID line"), (5, 5, "the harness line")):
    o, n = old[a - 1], new[b - 1]
    oc, nc = o.find("    #"), n.find("    #")
    print("line %d (%s): battery %d characters (the command its first %d, then the comment), S4 %d characters (the command its first %d, then the comment)"
          % (b, label, len(o), oc, len(n), nc))
    sm = difflib.SequenceMatcher(None, o[:oc], n[:nc], autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    for tag, i1, i2, j1, j2 in ops:
        print("    in the command: %s battery[%d:%d] %r -> S4[%d:%d] %r" % (tag, i1, i2, o[i1:i2][:160], j1, j2, n[j1:j2][:160]))
    print("    in the comment: battery %d characters -> S4 %d characters (%s)" % (len(o) - oc, len(n) - nc, "the same" if o[oc:] == n[nc:] else "changed"))
    if b == 1:
        good = [(t, o[i1:i2], n[j1:j2]) for t, i1, i2, j1, j2 in ops] == [("replace", "3", "4")]
    else:
        good = (len(ops) == 2 and all(t == "insert" for t, *_ in ops)
                and n[ops[0][3]:ops[0][4]] == " --restart-transition-rule 1a-option-a-2026-10-05"
                and "resources_transition_rows" in n[ops[1][3]:ops[1][4]])
    bad += not good
    print("    %s" % ("AS EXPECTED: " + ("the command differs only by r03 -> r04" if b == 1 else
                                         "the command gains only the flag --restart-transition-rule 1a-option-a-2026-10-05 and a read-only print of the manifest's resources_transition_rows")
                       if good else "NOT AS EXPECTED"))
sys.exit(1 if bad else 0)
EOF

echo
echo "## 3. the battery's t6.sh is the first preparation's sealed file and the file session S2 ran"
for c in "$@"; do
    if cmp -s "$OLD" "$c"; then echo "IDENTICAL  $c ($(sha < "$c"))"; else echo "DIFFERENT  $c"; bad=$((bad + 1)); fi
done

echo
[ "$bad" = 0 ] && echo "PROOFS HOLD (0 differences)" || echo "PROOFS DO NOT HOLD ($bad)"
[ "$bad" = 0 ]
