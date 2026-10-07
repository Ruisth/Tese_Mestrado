#!/bin/bash
# Proofs about the row files of G3 session S3, made apart from g3_extract_rows.py and from
# g3_check_rows.sh (other tools: sed line addresses and python slicing instead of awk). It
# READS only (the row files, the first preparation's row files, the runbook blob) and writes
# nothing.
#   1. Each fenced test 9 step file equals the first preparation's file (runbook 80e833f,
#      ids '-q1') with every '-q1' replaced by '-q2'. t9-exposure.sh differs from the first
#      preparation's file in exactly one line, its line 3, and only by the commit, the sha256
#      and the line number named there.
#   2. Each test 8 step file, with every '-q2' removed, is the runbook blob's lines of its
#      range, the 'host$ ' prompt removed, byte for byte.
# Usage (WSL): bash rows-proofs.sh <rows directory> <first preparation's rows directory> <runbook blob file>
set -u
ROWS=${1:?usage: rows-proofs.sh <rows directory> <first preparation rows directory> <runbook blob file>}
OLD=${2:?usage: rows-proofs.sh <rows directory> <first preparation rows directory> <runbook blob file>}
BLOB=${3:?usage: rows-proofs.sh <rows directory> <first preparation rows directory> <runbook blob file>}
bad=0
sha() { sha256sum | cut -d' ' -f1; }
n_of() { grep -oF -- "$1" "$2" | wc -l; }

echo "## inputs"
echo "runbook blob: sha256 $(sha < "$BLOB"), $(wc -l < "$BLOB") lines"
echo "first preparation's rows: $OLD"
echo "  its manifest names the runbook commit $(python3 -c 'import json,sys; m=json.load(open(sys.argv[1], encoding="utf-8")); print(m["runbook"]["commit"], "and the suffix", m["substitution_rule"]["suffix"])' "$OLD/rows.manifest.json")"

echo
echo "## 1. test 9: each fenced step file = the first preparation's file with '-q1' replaced by '-q2'"
for f in t9-a.sh t9-b.sh t9-c.sh t9-de.sh; do
    o=$(sha < "$OLD/$f"); r=$(sed 's/-q1/-q2/g' "$OLD/$f" | sha); n=$(sha < "$ROWS/$f")
    if sed 's/-q1/-q2/g' "$OLD/$f" | cmp -s - "$ROWS/$f"; then v=IDENTICAL; else v=DIFFERENT; bad=$((bad + 1)); fi
    echo "$v  $f: first preparation $o ('-q1' x$(n_of '-q1' "$OLD/$f"), '-q2' x$(n_of '-q2' "$OLD/$f")); with '-q1' replaced by '-q2' $r; S3 file $n ('-q2' x$(n_of '-q2' "$ROWS/$f"), '-q1' x$(n_of '-q1' "$ROWS/$f")); $(wc -c < "$OLD/$f") and $(wc -c < "$ROWS/$f") bytes"
done
echo
echo "## 1b. t9-exposure.sh: the diff against the first preparation's file (first preparation '<', S3 '>')"
diff "$OLD/t9-exposure.sh" "$ROWS/t9-exposure.sh"
echo "diff exit=$? (1: the files differ)"
changed=$(diff "$OLD/t9-exposure.sh" "$ROWS/t9-exposure.sh" | grep -c '^[<>]')
where=$(diff "$OLD/t9-exposure.sh" "$ROWS/t9-exposure.sh" | grep -v '^[<>-]' | tr '\n' ' ')
expect=$(sed -n '3p' "$OLD/t9-exposure.sh" | sed 's/ at 80e833f / at 8e49261 /; s/(sha256 c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae)/(sha256 4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db)/; s/, line 1529 /, line 1537 /')
if [ "$changed" = 2 ] && [ "$where" = "3c3 " ] && [ "$expect" = "$(sed -n '3p' "$ROWS/t9-exposure.sh")" ] && [ "$expect" != "$(sed -n '3p' "$OLD/t9-exposure.sh")" ] \
    && [ "$(wc -l < "$OLD/t9-exposure.sh")" = "$(wc -l < "$ROWS/t9-exposure.sh")" ]; then
    echo "ONE LINE  t9-exposure.sh: only line 3 differs ($(wc -l < "$ROWS/t9-exposure.sh") lines each); the first preparation's line 3 with '80e833f' -> '8e49261', the sha256 c55a2d3b... -> 4acf8de6... and 'line 1529' -> 'line 1537' is the S3 line 3; first preparation $(sha < "$OLD/t9-exposure.sh"), S3 file $(sha < "$ROWS/t9-exposure.sh")"
else
    echo "DIFFERENT  t9-exposure.sh: more than the commit, the sha256 and the line number of its line 3 differ"; bad=$((bad + 1))
fi
echo "the body (the lines that are not comments: the three commands): first preparation $(grep -v '^#' "$OLD/t9-exposure.sh" | sha), S3 file $(grep -v '^#' "$ROWS/t9-exposure.sh" | sha)"

echo
echo "## 2. test 8: each step file with every '-q2' removed = the blob's lines, the prompt removed (python slicing; sha256 of both sides)"
python3 - "$ROWS" "$BLOB" <<'EOF' || bad=$((bad + 1))
import hashlib, os, sys
rows, blob = sys.argv[1], sys.argv[2]
lines = open(blob, "rb").read().split(b"\n")
table = [("t8-a-reboot.sh", 1486, 1495), ("t8-b-wait-boot-id.sh", 1496, 1496), ("t8-c-unaided.sh", 1497, 1497),
         ("t8-d-tunnel.sh", 1498, 1498), ("t8-e-state.sh", 1499, 1499), ("t8-f-smoke.sh", 1500, 1500)]
bad = 0
for name, a, b in table:
    src = lines[a - 1:b]
    prompts = sum(1 for ln in src if ln.startswith(b"host$ "))
    want = b"\n".join(ln[len(b"host$ "):] if ln.startswith(b"host$ ") else ln for ln in src) + b"\n"
    data = open(os.path.join(rows, name), "rb").read()
    got = data.replace(b"-q2", b"")
    same = got == want
    bad += not same
    print("%s  %s: runbook lines %d-%d (%d line(s), %d with the prompt), prompt removed: sha256 %s, %d bytes; the file without '-q2': sha256 %s, %d bytes; the file: sha256 %s, '-q2' x%d"
          % ("IDENTICAL" if same else "DIFFERENT", name, a, b, len(src), prompts, hashlib.sha256(want).hexdigest(), len(want),
             hashlib.sha256(got).hexdigest(), len(got), hashlib.sha256(data).hexdigest(), data.count(b"-q2")))
whole = b"".join(open(os.path.join(rows, n), "rb").read() for n, _, _ in table).replace(b"-q2", b"")
fam = b"\n".join(ln[len(b"host$ "):] if ln.startswith(b"host$ ") else ln for ln in lines[1485:1500]) + b"\n"
print("%s  the six files in order, without '-q2' = runbook lines 1486-1500, prompt removed: sha256 %s (test 8's whole fenced block: line 1485 opens the fence, line 1501 closes it: %r, %r)"
      % ("IDENTICAL" if whole == fam else "DIFFERENT", hashlib.sha256(fam).hexdigest(), lines[1484].decode(), lines[1500].decode()))
bad += whole != fam
sys.exit(1 if bad else 0)
EOF

echo
echo "## 2b. the same for test 9's four fenced files (they are also the blob's lines)"
python3 - "$ROWS" "$BLOB" <<'EOF' || bad=$((bad + 1))
import hashlib, os, sys
rows, blob = sys.argv[1], sys.argv[2]
lines = open(blob, "rb").read().split(b"\n")
table = [("t9-a.sh", 1509, 1510), ("t9-b.sh", 1511, 1524), ("t9-c.sh", 1525, 1527), ("t9-de.sh", 1528, 1534)]
bad = 0
for name, a, b in table:
    src = lines[a - 1:b]
    want = b"\n".join(ln[len(b"host$ "):] if ln.startswith(b"host$ ") else ln for ln in src) + b"\n"
    data = open(os.path.join(rows, name), "rb").read()
    same = data.replace(b"-q2", b"") == want
    bad += not same
    print("%s  %s: runbook lines %d-%d, prompt removed: sha256 %s; the file: sha256 %s, '-q2' x%d"
          % ("IDENTICAL" if same else "DIFFERENT", name, a, b, hashlib.sha256(want).hexdigest(),
             hashlib.sha256(data).hexdigest(), data.count(b"-q2")))
sys.exit(1 if bad else 0)
EOF

echo
[ "$bad" = 0 ] && echo "PROOFS HOLD (0 differences)" || echo "PROOFS DO NOT HOLD ($bad)"
[ "$bad" = 0 ]
