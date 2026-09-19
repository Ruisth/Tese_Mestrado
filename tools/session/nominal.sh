#!/bin/bash
# Work order 2.C step 3: the existing nominal instrumentation entry of the
# pilot plan (120 s warm-up + 600 s measured, workload unchanged), with the
# collector's six expected services and companions fetched before the seal.
# Instrumentation validity and system outcome are reported separately: valid
# measurements with late or lost messages are a system failure.
# Usage: nominal.sh RUN_ID   (a plan entry never used on the guest, e.g. nominal-r01)
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
RID=${1:?plan run id}
[ -n "$SESSION" ] || { echo "STOP: no open session" >&2; exit 1; }
PLAN=$HOME/egw-tcg/pilot/campaign_plan.json
RAWD=$HOME/egw-tcg/pilot/results/raw/$RID
SEED=$("$PY" -c "import json,sys;p=json.load(open('$PLAN'));print(next(r['seed'] for r in p['runs'] if r['run_id']=='$RID'))") || exit 1
[ -e "$RAWD" ] && { echo "STOP: $RAWD exists; use another plan entry" >&2; exit 1; }
A=$(new_attempt "nominal instrumentation 120+600" engineering) || exit 1
trap '(cd "$REPO/src" && $LE finish --attempt "$A" --status interrupted --outcome interrupted --reason "driver interrupted" 2>/dev/null); export_attempt "$A"' INT TERM
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "seed=$SEED" "identities=$(repo_identity)" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"harness_run_id\": \"$RID\", \"condition\": \"nominal\", \"warmup_s\": 120, \"duration_s\": 600, \"rate_msg_s\": 11.2, \"devices\": \"smartwatch, smart ring, smart clothing (nominal mix)\", \"confirmation_window_s\": 60}" \
    'expected_artefacts=["raw/*/manifest.json", "raw/*/sent_events.jsonl", "raw/*/events.jsonl", "raw/*/controller_metrics.csv", "raw/*/resources.csv", "raw/*/logs/collector/resources-*.csv", "raw/*/logs/collector/resources-*.csv.diagnostics.log", "raw/*/logs/collector/resources-*.csv.lifecycle.csv", "raw/*/SHA256SUMS"]')
(cd "$REPO/src" && $LE add-source --attempt "$A" --kind raw --path "$RAWD" --role "harness raw run directory (sealed by the harness if complete)")
P=$HOME/egw-tcg/itest
mkdir -p "$A/analysis/snapshots"

# The deployed collector must be the clean clone's (identity of the run).
NEW=$REPO/src/deployment/scripts/collect-resources.sh
gcp "$A" collector-copy "$NEW" egw@127.0.0.1:/tmp/collect-resources.new.sh
gx "$A" collector-sync "set -e; OLDSHA=\$(sha256sum /opt/egw/deployment/scripts/collect-resources.sh | cut -d' ' -f1); NEWSHA=\$(sha256sum /tmp/collect-resources.new.sh | cut -d' ' -f1); if [ \"\$OLDSHA\" != \"\$NEWSHA\" ]; then sudo mkdir -p /opt/egw/evidence/collector-previous; sudo cp /opt/egw/deployment/scripts/collect-resources.sh /opt/egw/evidence/collector-previous/collect-resources.\$OLDSHA.sh; sudo cp /tmp/collect-resources.new.sh /opt/egw/deployment/scripts/collect-resources.sh; sudo chmod 0755 /opt/egw/deployment/scripts/collect-resources.sh; echo \"replaced \$OLDSHA\"; fi; sha256sum /opt/egw/deployment/scripts/collect-resources.sh"
echo "clean clone collector: $(sha256sum "$NEW")"

hx "$A" pre "wait_ready 300 && drained && metrics $RID before && \$REC snap --prefix \$P/$RID --label before --seed $SEED"
pre_rc=$?
h_rc=9
if [ "$pre_rc" -eq 0 ]; then
    hx "$A" harness-run "harness_run $RID"
    h_rc=$?
    DRAIN_LIMIT_S=1500 hx "$A" post-drain "DRAIN_LIMIT_S=1500 drained"
    d_rc=$?
    hx "$A" fetch-post-drain-events "scp -q egw-tcg:/opt/egw/deployment/data/events/$RID/events.jsonl '$A/analysis/events.post-drain.jsonl' && wc -l '$A/analysis/events.post-drain.jsonl'"
    hx "$A" fetch-warmup-events "scp -q egw-tcg:/opt/egw/deployment/data/events/$RID.warmup/events.jsonl '$A/analysis/warmup.events.jsonl' && wc -l '$A/analysis/warmup.events.jsonl'"
    hx "$A" after-snapshots "metrics $RID after && \$REC snap --prefix \$P/$RID --label after --like before"
    cp "$P/$RID".* "$A/analysis/snapshots/" 2> /dev/null
    ex "$A" identity-accounting "$PY" "$DRIVERS/nominal_account.py" "$RAWD" "$A/analysis/events.post-drain.jsonl" "$A/analysis"
fi
gx "$A" guest-state-after "cd /opt/egw/deployment && docker ps --format '{{.Names}} {{.Status}}'; for c in \$(docker ps -a --format '{{.Names}}'); do echo \"\$c OOMKilled=\$(docker inspect -f '{{.State.OOMKilled}}' \$c) restarts=\$(docker inspect -f '{{.RestartCount}}' \$c)\"; done; sudo -n dmesg | grep -ci 'memory cgroup out of memory' || true; free -m; df -h / /var/lib/docker /tmp"

# Verdicts: instrumentation from the harness manifest; outcome from the harness row.
V=$("$PY" - "$RAWD" "$A/analysis/accounting.json" 2>/dev/null <<'PYEOF' || echo "invalid|not-run|no manifest or accounting"
import json, sys
m = json.load(open(sys.argv[1] + "/manifest.json"))
a = json.load(open(sys.argv[2]))
row = a["harness_row"]
validity = "valid" if m.get("validity") == "valid" else "invalid"
if row.get("lost") == 0 and row.get("late_confirmations") == 0 and row.get("delivered_unique") == row.get("sent_valid"):
    outcome = "pass"
else:
    outcome = "fail"
reason = (f"manifest validity {m.get('validity')}" + (f" ({'; '.join(m.get('validity_reasons') or [])})" if m.get("validity_reasons") else "")
          + f"; delivery at the harness fetch: sent_valid {row.get('sent_valid')}, delivered {row.get('delivered_unique')}, "
          f"lost {row.get('lost')}, late {row.get('late_confirmations')}; after the drain: {a.get('after_drain')}")
print(f"{validity}|{outcome}|{reason}")
PYEOF
)
validity=${V%%|*}; rest=${V#*|}; outcome=${rest%%|*}; reason=${rest#*|}
[ "$pre_rc" -ne 0 ] && { validity=invalid; outcome=not-run; reason="precondition failed (ready/drained/snapshot); the harness was NOT started"; }
status=finished; [ "$h_rc" -eq 0 ] || status=failed
(cd "$REPO/src" && $LE finish --attempt "$A" --status "$status" --validity "$validity" --outcome "$outcome" \
    --reason "$reason (harness exit $h_rc)" --next-action "see analysis/accounting.json; delivery and instrumentation are separate verdicts")
export_attempt "$A"
echo "NOMINAL $RID: validity=$validity outcome=$outcome harness_exit=$h_rc"
