"""Check one live collector output (CSV + companions) against the six expected services.

Usage: collector_check.py <dir> <run> <expected,services> <wanted sha256> <sut_environment.json>
Exit 0 only when: the deployed collector hash is the wanted one, the inventory
reports no missing service, every expected service has rows, and the CSV passes
validate_resources_csv with the collector's own start..stop as the window.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from egw_experiments.resources import validate_resources_csv

d, rid, expect, want_sha, sut = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(","), sys.argv[4], sys.argv[5]
csv_path = d / f"resources-{rid}.csv"
problems = []
diag_path = d / f"resources-{rid}.csv.diagnostics.log"
diag = diag_path.read_text(encoding="utf-8").splitlines() if diag_path.is_file() else []
if not diag:
    problems.append("no diagnostics companion")
start = next((ln for ln in diag if " start: collector_sha256=" in ln), None)
stop = next((ln for ln in reversed(diag) if " stop: " in ln), None)
inv = next((ln for ln in reversed(diag) if " inventory: " in ln), None)
sha = re.search(r"collector_sha256=([0-9a-f]{64})", start or "")
if not sha or sha.group(1) != want_sha:
    problems.append(f"deployed collector hash {sha.group(1) if sha else None} is not the clean clone's {want_sha}")
if not inv:
    problems.append("no inventory line (the collector did not stop cleanly)")
elif "missing=none" not in inv:
    problems.append(f"inventory reports missing services: {inv}")
if not (d / f"resources-{rid}.csv.lifecycle.csv").is_file():
    problems.append("no lifecycle companion")
rows = Counter()
instants = set()
if csv_path.is_file():
    with open(csv_path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows[r["container"]] += 1
            instants.add(r["ts_utc"])
else:
    problems.append("no CSV")
for s in expect:
    if rows.get(s, 0) == 0:
        problems.append(f"expected service {s} has no rows")
extra = sorted(set(rows) - set(expect))
window = [start[:20] if start else None, stop[:20] if stop else None]
if csv_path.is_file() and all(window):
    node = json.load(open(sut))["node"]
    problems += [f"validate_resources_csv: {p}" for p in validate_resources_csv(
        str(csv_path), expected_host=node, expected_window_start_utc=window[0], expected_window_end_utc=window[1])]
report = {"run": rid, "deployed_sha256": sha.group(1) if sha else None, "rows_per_service": dict(rows),
          "unexpected_names": extra, "distinct_instants": len(instants), "window": window,
          "start_line": start, "stop_line": stop, "inventory": inv, "problems": problems}
(d / "collector-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
sys.exit(1 if problems else 0)
