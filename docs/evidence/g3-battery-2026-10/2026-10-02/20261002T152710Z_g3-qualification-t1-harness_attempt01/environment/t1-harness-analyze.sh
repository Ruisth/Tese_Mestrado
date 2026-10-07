# G3 battery, row t1-harness, step 2 of 2: PROSE-ONLY step. No fenced runbook line exists for it.
# Written by g3_extract_rows.py from a constant of that script; nothing is extracted and no id is substituted.
# It derives from docs/setup/qemu_integrated_gateway.md at 80e833f (sha256 c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae), line 1320, which says:
#   "The harness applies the confirmation deadline itself (manifest `confirmation_deadline_clock_domain: "controller"`), so no `pre`/`post` is used here; read the result with `python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json` and the columns `confirmation_deadline_source`, `sent_valid`, `delivered_unique`, `lost`, `late_confirmations`, `double_accepted` of `~/egw-tcg/pilot/results/processed/per_run.csv`"
# Decision packet of 2026-10-01 (revision 2), execution choice "Prose-only steps": T1's analyze read (line 1320)
# is run and recorded. The plan entry is nominal-r02 (decision 1b; packet section 2, row 2). The analyze command
# is, character for character, the runbook's own fenced line 1427 (test 6). The second command prints the six
# columns line 1320 names from this run's row of per_run.csv. Both print; neither judges.
python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json; echo "analyze exit=$?"
python3 - ~/egw-tcg/pilot/results/processed/per_run.csv nominal-r02 <<'EOF'
import csv, sys
path, rid = sys.argv[1], sys.argv[2]
cols = ("confirmation_deadline_source", "sent_valid", "delivered_unique", "lost", "late_confirmations", "double_accepted")
with open(path, newline="", encoding="utf-8") as fh:
    rows = [r for r in csv.DictReader(fh) if r.get("run_id") == rid]
print("per_run.csv:", path, "- rows of", rid + ":", len(rows))
for r in rows:
    print(rid, " ".join("%s=%s" % (c, r.get(c)) for c in cols))
sys.exit(0 if len(rows) == 1 else 1)
EOF
echo "per_run read exit=$? (0: exactly one row of nominal-r02 was printed; anything else: none, several, or the file was not read)"
