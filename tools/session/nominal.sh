#!/bin/bash
# Work order 2.C step 3: the existing nominal instrumentation entry of the
# pilot plan (120 s warm-up + 600 s measured, workload unchanged), with the
# collector's six expected services and companions fetched before the seal.
# Instrumentation validity and system outcome are reported separately: valid
# measurements with late or lost messages are a system failure.
# Usage: nominal.sh RUN_ID   (a plan entry never used on the guest, e.g. nominal-r01)
#
# Prerequisites (failure: outcome not-run, exit 2) are the open session, the
# plan's seed, a fresh raw directory, the attempt's own fields and identities,
# the collector copy and sync (the deployed collector must be the clean
# clone's), the guest state before the run and 'pre'. Once the harness has
# started the outcome is never 'not-run' again: the harness run, the
# post-drain, the two event fetches, the after-snapshots, their copy into the
# package, the identity accounting, the guest state after and its comparison
# with the state before are MANDATORY, and any of them failing leaves the run
# invalid (exit 3). A step whose console capture was lost (exit 74) is recorded
# as that capture having failed, never as the step itself having failed.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
# A missing argument is a prerequisite (2), never the 1 of a valid negative
# result: '${1:?...}' would end the shell with 1 before any check could run.
[ "$#" -eq 1 ] || driver_stop "$EXIT_PREREQUISITE" "usage: nominal.sh RUN_ID (a plan entry never used on the guest)"
RID=$1
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
PLAN=$HOME/egw-tcg/pilot/campaign_plan.json
RAWD=$HOME/egw-tcg/pilot/results/raw/$RID
SEED=$("$PY" -c "import json,sys;p=json.load(open('$PLAN'));print(next(r['seed'] for r in p['runs'] if r['run_id']=='$RID'))") \
    || driver_stop "$EXIT_PREREQUISITE" "$RID has no seed in $PLAN"
[ -e "$RAWD" ] && driver_stop "$EXIT_PREREQUISITE" "$RAWD exists; use another plan entry"
A=$(new_attempt "nominal instrumentation 120+600" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
trap 'driver_interrupt "$A"' INT TERM

# not_run REASON: a prerequisite failed, so the harness was never started.
not_run() {
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "$1" --next-action "read console/; the harness was NOT started")
    driver_exit "$A"
}

# The identity of the clean clone is part of the result: a git that cannot be
# read is recorded as such (identity_error) and stops the run.
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "seed=$SEED" "identities=$IDENTITIES" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"harness_run_id\": \"$RID\", \"condition\": \"nominal\", \"warmup_s\": 120, \"duration_s\": 600, \"rate_msg_s\": 11.2, \"devices\": \"smartwatch, smart ring, smart clothing (nominal mix)\", \"confirmation_window_s\": 60}" \
    'expected_artefacts=["raw/*/manifest.json", "raw/*/sent_events.jsonl", "raw/*/events.jsonl", "raw/*/controller_metrics.csv", "raw/*/resources.csv", "raw/*/logs/collector/resources-*.csv", "raw/*/logs/collector/resources-*.csv.diagnostics.log", "raw/*/logs/collector/resources-*.csv.lifecycle.csv", "raw/*/SHA256SUMS"]') \
    || not_run "the attempt fields could not be recorded"
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || not_run "the identity of the clean clone could not be read (see identities.identity_error); the harness was NOT started"
(cd "$REPO/src" && $LE add-source --attempt "$A" --kind raw --path "$RAWD" \
    --role "harness raw run directory (sealed by the harness if complete)") \
    || not_run "the raw capsule could not be registered as a source"
P=$HOME/egw-tcg/itest

# The deployed collector must be the clean clone's (identity of the run): the
# copy and the deployed file are both compared with the clone's sha256.
NEW=$REPO/src/deployment/scripts/collect-resources.sh
NEWSHA=$(sha256sum "$NEW" | cut -d' ' -f1)
echo "clean clone collector: $NEWSHA  $NEW"
gcp "$A" collector-copy "$NEW" egw@127.0.0.1:/tmp/collect-resources.new.sh
copy_rc=$?
if [ "$copy_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" collector-copy "the harness was NOT started"
elif [ "$copy_rc" -ne 0 ]; then
    not_run "the clean clone's collector could not be copied to the guest"
fi
gx "$A" collector-sync "set -e
OLDSHA=\$(sha256sum /opt/egw/deployment/scripts/collect-resources.sh | cut -d' ' -f1)
COPYSHA=\$(sha256sum /tmp/collect-resources.new.sh | cut -d' ' -f1)
[ \"\$COPYSHA\" = \"$NEWSHA\" ] || { echo \"STOP: the copied collector is not the clone's (\$COPYSHA, expected $NEWSHA)\"; exit 1; }
if [ \"\$OLDSHA\" != \"\$COPYSHA\" ]; then
    sudo mkdir -p /opt/egw/evidence/collector-previous
    sudo cp /opt/egw/deployment/scripts/collect-resources.sh /opt/egw/evidence/collector-previous/collect-resources.\$OLDSHA.sh
    sudo cp /tmp/collect-resources.new.sh /opt/egw/deployment/scripts/collect-resources.sh
    sudo chmod 0755 /opt/egw/deployment/scripts/collect-resources.sh
    echo \"replaced \$OLDSHA\"
fi
sha256sum /opt/egw/deployment/scripts/collect-resources.sh
GOTSHA=\$(sha256sum /opt/egw/deployment/scripts/collect-resources.sh | cut -d' ' -f1)
[ \"\$GOTSHA\" = \"$NEWSHA\" ] || { echo \"STOP: the deployed collector is not the clone's (\$GOTSHA, expected $NEWSHA)\"; exit 1; }"
sync_rc=$?
if [ "$sync_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" collector-sync "the harness was NOT started"
elif [ "$sync_rc" -ne 0 ]; then
    not_run "the deployed collector is not the clean clone's"
fi

# The guest's container state, in the identical form before and after the
# measured window: OOM kills and restarts are read from the pair, never from
# the 'after' alone (preflight.sh judges the same facts at the session's start).
# The container id goes into the record because OOMKilled and RestartCount
# belong to the container OBJECT: a recreated container answers 'false' and '0'
# with a new id, and that is how the replacement is seen. The instant it last
# started goes in beside it because an in-place restart ('docker restart', a
# 'compose restart') keeps the object and does not touch RestartCount, which
# Docker increments from the restart POLICY: without StartedAt the two records
# of such a run are identical. An inspect that answers nothing leaves the field
# 'unknown' and makes this step fail (rc=1), so no container is silently
# dropped from either side of the comparison.
GUEST_STATE="cd /opt/egw/deployment || exit 1
rc=0
docker ps --format '{{.Names}} {{.Status}}'
for c in \$(docker ps -a --format '{{.Names}}'); do
    oom=\$(docker inspect -f '{{.State.OOMKilled}}' \"\$c\") || rc=1
    res=\$(docker inspect -f '{{.RestartCount}}' \"\$c\") || rc=1
    cid=\$(docker inspect -f '{{.Id}}' \"\$c\") || rc=1
    sat=\$(docker inspect -f '{{.State.StartedAt}}' \"\$c\") || rc=1
    echo \"container \$c oomkilled=\${oom:-unknown} restarts=\${res:-unknown} id=\${cid:-unknown} started=\${sat:-unknown}\"
    [ -n \"\$oom\" ] && [ -n \"\$res\" ] && [ -n \"\$cid\" ] && [ -n \"\$sat\" ] || rc=1
done
if KMSG=\$(sudo -n dmesg 2>/dev/null); then
    echo \"memory-cgroup OOM lines: \$(printf '%s\n' \"\$KMSG\" | grep -ci 'memory cgroup out of memory' || true)\"
else
    echo 'dmesg could not be read: the OOM state of this boot is UNKNOWN, which is not \"no OOM\"'
    rc=1
fi
free -m
df -h / /var/lib/docker /tmp
exit \$rc"
gx "$A" guest-state-before "$GUEST_STATE"
before_rc=$?
if [ "$before_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" guest-state-before "the harness was NOT started"
elif [ "$before_rc" -ne 0 ]; then
    not_run "the guest state before the run was not recorded (exit $before_rc); the harness was NOT started"
fi
BEFORE=$(ls "$A"/console/*-guest-state-before.stdout.txt 2> /dev/null | tail -n 1)
[ -n "$BEFORE" ] || not_run "the record of the guest state before the run was not kept; the harness was NOT started"

hx "$A" pre "wait_ready 300 && drained && metrics $RID before && \$REC snap --prefix \$P/$RID --label before --seed $SEED"
pre_rc=$?
if [ "$pre_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" pre "the harness was NOT started"
elif [ "$pre_rc" -ne 0 ]; then
    not_run "precondition failed (ready/drained/snapshot); the harness was NOT started"
fi

mandatory=()      # failed mandatory steps: the measurements are not usable
hx "$A" harness-run "harness_run $RID"
h_rc=$?
[ "$h_rc" -eq 0 ] || mandatory+=("$(step_note harness-run "$h_rc" "the harness run exited $h_rc")")
DRAIN_LIMIT_S=1500 hx "$A" post-drain "DRAIN_LIMIT_S=1500 drained"
drain_rc=$?
[ "$drain_rc" -eq 0 ] || mandatory+=("$(step_note post-drain "$drain_rc" "no quiet window after the run (post-drain)")")
hx "$A" fetch-post-drain-events "scp -q egw-tcg:/opt/egw/deployment/data/events/$RID/events.jsonl '$A/analysis/events.post-drain.jsonl' && wc -l '$A/analysis/events.post-drain.jsonl'"
post_rc=$?
[ "$post_rc" -eq 0 ] || mandatory+=("$(step_note fetch-post-drain-events "$post_rc" "the post-drain event log was not fetched")")
hx "$A" fetch-warmup-events "scp -q egw-tcg:/opt/egw/deployment/data/events/$RID.warmup/events.jsonl '$A/analysis/warmup.events.jsonl' && wc -l '$A/analysis/warmup.events.jsonl'"
warmup_rc=$?
[ "$warmup_rc" -eq 0 ] || mandatory+=("$(step_note fetch-warmup-events "$warmup_rc" "the warm-up event log was not fetched")")
hx "$A" after-snapshots "metrics $RID after && \$REC snap --prefix \$P/$RID --label after --like before"
snap_rc=$?
[ "$snap_rc" -eq 0 ] || mandatory+=("$(step_note after-snapshots "$snap_rc" "the 'after' snapshots were not taken")")
# The four snapshots are the counter and twin baseline of the run, and this
# copy is the ONLY path by which the mandatory 'pre' and 'after-snapshots'
# evidence reaches the package: both calls are checked and the copy's own
# diagnostics are kept.
if mkdir -p "$A/analysis/snapshots" && cp "$P/$RID".* "$A/analysis/snapshots/"; then
    ls -l "$A/analysis/snapshots/"
else
    mandatory+=("the before/after snapshots were not copied into the package")
fi
ex "$A" identity-accounting "$PY" "$DRIVERS/nominal_account.py" "$RAWD" "$A/analysis/events.post-drain.jsonl" "$A/analysis"
account_rc=$?
[ "$account_rc" -eq 0 ] || mandatory+=("$(step_note identity-accounting "$account_rc" "the identity accounting could not be produced")")
gx "$A" guest-state-after "$GUEST_STATE"
after_rc=$?
[ "$after_rc" -eq 0 ] || mandatory+=("$(step_note guest-state-after "$after_rc" "the guest state after the run was not recorded")")
AFTER=$(ls "$A"/console/*-guest-state-after.stdout.txt 2> /dev/null | tail -n 1)
if [ -n "$AFTER" ]; then
    # An OOM-killed, restarted, replaced or vanished container is a fact about
    # the run, not a note, and the six expected services must be in both
    # records: a state the pair does not name is not a state that was 'normal'.
    ex "$A" guest-state-delta "$PY" "$DRIVERS/guest_state_delta.py" --expect "$EXPECT_SERVICES" "$BEFORE" "$AFTER"
    delta_rc=$?
    [ "$delta_rc" -eq 0 ] || mandatory+=("$(step_note guest-state-delta "$delta_rc" "a container was OOM-killed or restarted during the run, or was replaced or is gone since it started, or the two guest states could not be compared")")
else
    mandatory+=("the record of the guest state after the run was not kept")
fi

# Verdicts: instrumentation from the harness manifest; outcome from the harness
# row. The harness ran, so the outcome is never 'not-run': a manifest or an
# accounting that cannot be read leaves it inconclusive.
V=$("$PY" - "$RAWD" "$A/analysis/accounting.json" 2> /dev/null <<'PYEOF' || echo "invalid|inconclusive|the harness manifest or the accounting could not be read"
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
status=finished
[ "$h_rc" -eq 0 ] || status=failed
if [ "${#mandatory[@]}" -ne 0 ]; then
    # The measured outcome is kept as it was read; the instrumentation is not.
    status=failed
    validity=invalid
    reason="mandatory step(s) failed: $(printf '%s; ' "${mandatory[@]}")$reason"
fi
(cd "$REPO/src" && $LE finish --attempt "$A" --status "$status" --validity "$validity" --outcome "$outcome" \
    --reason "$reason (harness exit $h_rc)" --next-action "see analysis/accounting.json; delivery and instrumentation are separate verdicts")
echo "NOMINAL $RID: validity=$validity outcome=$outcome harness_exit=$h_rc"
driver_exit "$A"
