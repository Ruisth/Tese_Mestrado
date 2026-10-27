#!/bin/bash
# reviewer: read-only: attempt.json of the pass row (purpose, workload), the export package listing, and the term leftovers
B=/tmp/g3-s4-bench/pass
A=$(ls -d $B/egw-exec/attempts/*_g3-qualification-t6_attempt02 | head -n 1)
/home/ruisth/egw-exec/venv/bin/python - "$A/attempt.json" << 'EOF'
import json, sys
a = json.load(open(sys.argv[1]))
for k in ("purpose", "status", "instrumentation_validity", "system_outcome", "kind", "name", "title"):
    print(k, "=", a.get(k))
print("keys:", sorted(a.keys()))
EOF
echo "--- commands.jsonl of the pass row (names and exit)"
/home/ruisth/egw-exec/venv/bin/python - "$A/commands.jsonl" << 'EOF'
import json, sys
for line in open(sys.argv[1]):
    d = json.loads(line)
    print(d.get("seq"), d.get("name"), d.get("exit_code", d.get("returncode")), (" ".join(d.get("argv", []) if isinstance(d.get("argv"), list) else [str(d.get("argv"))]))[:160])
EOF
echo "--- package listing (pass)"
P=$(ls -d $B/out/runs/*/$(basename "$A"))
(cd "$P" && find . -maxdepth 3 | sort | head -n 80)
echo "--- term leftovers"
T=/tmp/g3-s4-bench/term
cat $T/egw-exec/g3-t6-s4/row-t6.env 2>/dev/null | cut -c1-200
cat $T/mod/state/capture.log
for f in $T/mod/state/unit-*; do echo "$f: $(cat "$f")"; done
