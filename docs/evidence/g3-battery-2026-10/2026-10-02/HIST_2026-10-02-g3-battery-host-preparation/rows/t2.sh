R=itest-3dev-01-q1; run_test $R 7 --scenario smoke --duration 60; RT=$?
if [ "$RT" = 0 ]; then for U in $(python3 -c "import json;print(' '.join(sorted({json.loads(l)['device_uuid'] for l in open('$HOME/egw-tcg/itest/$R/sent_events.jsonl')})))"); do twin $R $U || { RT=twin; break; }; done; else stop "test 2: run_test did not complete (RT='$RT') - the twins were NOT read"; fi     # a twin that could not be saved sets RT=twin, so the evaluation line below refuses instead of judging two twins out of three
[ "$RT" = 0 ] && python3 - ~/egw-tcg/itest/$R.twin.*.json <<'EOF' || stop "test 2: not evaluated (RT='$RT') or the evaluation script failed"
import json, sys
want = {"smartwatch": {"vitals": ["heart_rate_bpm"], "location": ["lat", "lon"]},
        "smart_ring": {"thermo": ["skin_temp_c"], "oximetry": ["spo2_pct"]},
        "smart_clothing": {"motion": ["accel_x", "accel_y", "accel_z"], "respiration": ["breathing_rpm"]}}
for f in sys.argv[1:]:
    t = json.load(open(f)); dt = t["attributes"]["device_type"]; feats = t["features"]
    missing = [(fe, p) for fe, props in want[dt].items() for p in props if p not in feats.get(fe, {}).get("properties", {})]
    ing = feats["ingestion"]["properties"]
    print(f, dt, "policyId" , t.get("policyId"), "missing:", missing, "ingestion:", {k: ing.get(k) for k in ("last_run_id", "last_seq", "accepted_count")})
EOF
