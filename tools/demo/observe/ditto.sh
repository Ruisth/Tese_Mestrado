#!/bin/bash
# tools/demo/observe/ditto.sh <yocto|debian13|yoctoWrynose> [interval_s=5] [once] - Terminal 3: PERIODIC
# QUERIES of the demonstration's twins in Ditto (a poll of the twin STATE every interval; not a
# real-time event stream). The devices are discovered from the current demonstration run's own record
# ($DEMO_RUNS/<run>/sent_events.jsonl, written by the simulator): no UUID is typed by hand. Each line:
# time, device type, twin id, last_seq, accepted_count, last_ts and the measured values the twin
# holds, whatever the device type: vitals and location (smartwatch), thermo and oximetry (smart ring),
# motion and respiration (smart clothing). "UPDATED BY THIS RUN" = last_run_id equals the current run.
# The query is the twin's REST read through the local Ditto gateway inside the guest, with the
# controller's pre-authenticated identity (Ditto pre-authentication: an identity, not a credential).
# Ditto keeps the twins in MongoDB; this reads them through Ditto. Ctrl+C ends only this observer.
set -u
. "$(dirname "$0")/../lib.sh"
scenario_check "${1:-}" || exit 2
s=$(scenario_canon "$1")
interval=${2:-5}
once=${3:-}
guest_running "$s" || { echo "STOP: the $s guest is not running"; exit 2; }
say "Ditto observer on $s: twin STATE polled every $interval s (not an event stream). Ctrl+C to stop."
while :; do
    run=$(current_run)
    # only a demonstration run made on THIS scenario's guest (simulate.sh records the scenario)
    [ "$(cat "$DEMO_STATE/current_scenario" 2> /dev/null)" = "$s" ] || run=
    f=$DEMO_RUNS/$run/sent_events.jsonl
    if [ -z "$run" ] || [ ! -s "$f" ]; then
        echo "$(date -u +%H:%M:%S)  waiting for a demonstration run (none recorded yet, or nothing published)"
    else
        uuids=$(python3 - "$f" << 'PY'
import json, sys
seen = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    u = d.get("device_uuid")
    if u and u not in seen:
        seen.append(u)
print(" ".join(seen))
PY
        )
        # all features: the measured ones differ per device type (see the header), plus ingestion
        remote="for u in $uuids; do curl -s --max-time 10 -H 'x-ditto-pre-authenticated: pre:egw-controller' \"http://127.0.0.1:8080/api/2/things/org.c2dta:\$u?fields=thingId,attributes/device_type,features\"; echo; done"
        tmp=$(mktemp)
        dssh "$s" "$remote" > "$tmp" 2> /dev/null
        python3 - "$run" "$(date -u +%H:%M:%S)" "$tmp" << 'PY'
import json, sys
run, now, path = sys.argv[1], sys.argv[2], sys.argv[3]
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        t = json.loads(line)
    except ValueError:
        print(f"{now}  unreadable twin answer: {line[:80]}")
        continue
    if "thingId" not in t:
        print(f"{now}  twin not found yet: {t.get('message', line[:80])}")
        continue
    feats = t.get("features", {}) or {}
    ing = (feats.get("ingestion") or {}).get("properties", {}) or {}
    # a twin just created holds ingestion fields set to null until its first update: show "-", not a traceback
    val = {k: ("-" if ing.get(k) is None else ing.get(k)) for k in ("last_run_id", "last_seq", "accepted_count", "last_ts")}
    if ing.get("last_run_id") is None:
        mark = "CREATED, waiting for its first update"
    else:
        mark = "UPDATED BY THIS RUN" if ing.get("last_run_id") == run else f"last run {val['last_run_id']}"
    print(f"{now}  {(t.get('attributes') or {}).get('device_type', '?'):15} {t['thingId']}  seq {val['last_seq']!s:<5} accepted {val['accepted_count']!s:<5} last_ts {val['last_ts']}  {mark}")
    values = [f"{name} {json.dumps((body or {}).get('properties', {}) or {})}"
              for name, body in feats.items() if name != "ingestion"]
    if values:
        print("           values: " + " ".join(values))
PY
        rm -f "$tmp"
    fi
    [ "$once" = once ] && break
    sleep "$interval"
done
