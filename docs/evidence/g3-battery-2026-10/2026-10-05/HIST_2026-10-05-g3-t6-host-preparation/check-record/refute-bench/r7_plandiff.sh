#!/bin/bash
# reviewer: read-only: the byte diff of the plan snapshots of the pass row (claim O1: only r04's four lines change)
A=$(ls -d /tmp/g3-s4-bench/pass/egw-exec/attempts/*_g3-qualification-t6_attempt02 | head -n 1)
diff "$A/other/campaign_plan.before.json" "$A/other/campaign_plan.after.json"
echo "diff exit $?"
echo "--- the transition/proved_down values in the stand-in manifest are constants of bs4_harness.py:"
grep -c 'bench_stand_in' /tmp/g3-s4-bench/pass/home/egw-tcg/pilot/results/raw/controller_restart-r04/manifest.json
