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
# started the outcome is never 'not-run' again, and what happens after it is
# sorted into three groups, because observing the system fail is a RESULT while
# failing to observe is an invalid measurement:
#   MANDATORY  evidence that is missing or unreadable (the harness run, the
#              guest state after the run, the copy of the two snapshot records
#              into the package, a comparison that could not be made, and any
#              step whose console capture was lost) -> instrumentation invalid
#              (exit 3), naming the requirement that failed.
#   OBSERVED   faults the run positively showed (an OOM kill, a restart, a
#              replaced or vanished container, a drain that GAVE UP without a
#              quiet window - read from what each step reported, never from a
#              status alone)
#              -> the SYSTEM outcome fails while the measurement stays as valid
#              as the evidence says: a complete measurement of a failure is a
#              valid negative result (exit 1), not broken instrumentation.
#   INCOMPLETE post-window observations that could not be made (the two event
#              fetches, the after-snapshots, the identity accounting and the
#              drain) -> recorded in the reason and in post_window_observations;
#              they leave the sealed window's own validity untouched, and
#              nothing then claims eventual delivery or a complete tail. A
#              clean PASS is the one verdict that needs complete evidence: with
#              any of them incomplete the outcome is inconclusive (exit 3),
#              while a system that failed keeps its failure (exit 1).
# A step whose console capture was lost (exit 74) is recorded as that capture
# having failed, never as the step itself having failed.
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

mandatory=()      # evidence missing or unreadable: the measurement is invalid
observed=()       # faults the run positively showed: the system outcome fails
incomplete=()     # post-window observations that could not be made

# post_window NAME RC TEXT: a step AFTER the measured window the harness
# sealed. Its own failure leaves an observation incomplete and neither verdict
# of that window touched; only a lost console capture is an evidence failure of
# the attempt itself (mandatory), as it is everywhere else.
post_window() {
    [ "$2" -eq 0 ] && return 0
    if [ "$2" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note "$1")")
    else
        incomplete+=("$3 (exit $2)")
    fi
    return 1
}

# delta_faults FILE: the fault sentences guest_state_delta.py printed, each
# introduced by '; ', or nothing at all. The comparison prints one 'FAULT: ...'
# line per fault whatever its exit status is, so a pair it could not compare
# (exit 2) still says what it positively saw, and the package's own index can
# be searched for what happened instead of only for the generic sentence.
delta_faults() {
    [ -n "${1:-}" ] && [ -f "$1" ] || return 0
    sed -n 's/^FAULT: /; /p' "$1" | tr -d '\n'
}

# delta_counts FILE: 'N M' from the summary line the comparison prints LAST
# ('guest-state-delta: faults=N problems=M'), or nothing at all when that line
# is not there. Python ends 1 for an unhandled exception as much as for a fault
# the pair SHOWED, so that line is what tells a status the helper itself
# reached from one Python left behind after it crashed.
delta_counts() {
    [ -n "${1:-}" ] && [ -f "$1" ] || return 0
    tail -n 1 "$1" \
        | sed -n 's/^guest-state-delta: faults=\([0-9][0-9]*\) problems=\([0-9][0-9]*\)$/\1 \2/p'
}

# drain_gave_up: whether the drain step itself REPORTED that the queue never
# went quiet, read from its console record as the guest-state comparison is
# read. The runbook's 'drained' gives up with
#   STOP: drained: no quiet window of <quiet> s within <limit> s (last reading: ...)
# and that sentence is the one observation of the queue this step can make. Its
# other STOP (a /metrics that is unreachable or not valid JSON) and every
# failure of the step around it - a tunnel that dropped, a refused connection,
# a guest that is not answering - observed NOTHING about the queue.
drain_gave_up() {
    local f
    for f in "$A"/console/*-post-drain.stderr.txt "$A"/console/*-post-drain.stdout.txt; do
        [ -f "$f" ] || continue
        grep -q '^STOP: drained: no quiet window of [0-9][0-9]* s within [0-9][0-9]* s' "$f" \
            && return 0
    done
    return 1
}

hx "$A" harness-run "harness_run $RID"
h_rc=$?
[ "$h_rc" -eq 0 ] || mandatory+=("$(step_note harness-run "$h_rc" "the harness run exited $h_rc")")
DRAIN_LIMIT_S=1500 hx "$A" post-drain "DRAIN_LIMIT_S=1500 drained"
drain_rc=$?
# The drain runs AFTER the measured window: it is an extra observation, never a
# reason to discard the window, and never mandatory. A status of its own says
# nothing about the queue, because the step reaches the controller through the
# tunnel: only the drain's own give-up - the STOP its console record carries
# when no quiet window was reached within the limit - is a fault the run
# SHOWED. Anything else that ended it leaves the tail simply unobserved, which
# is what an incomplete post-window observation is.
if ! post_window post-drain "$drain_rc" "the drain after the run did not complete, so no eventual delivery and no complete tail is claimed"; then
    if [ "$drain_rc" -ne "$EXIT_CAPTURE_LOST" ] && drain_gave_up; then
        observed+=("the drain after the run did not report a quiet window (post-drain exit $drain_rc)")
    fi
fi
hx "$A" fetch-post-drain-events "scp -q egw-tcg:/opt/egw/deployment/data/events/$RID/events.jsonl '$A/analysis/events.post-drain.jsonl' && wc -l '$A/analysis/events.post-drain.jsonl'"
post_rc=$?
post_window fetch-post-drain-events "$post_rc" "the post-drain event log was not fetched"
# Whether that tail was fetched is what THIS driver knows, and it is passed to
# the accounting below: the log being on disk is not that fact, because a
# transfer that died mid-way leaves a partial file that would be read as a
# complete tail. A lost console capture (74) leaves the step's own result
# unread here, so nothing is established either way.
post_status=not-fetched
if [ "$post_rc" -eq 0 ]; then
    post_status=fetched
elif [ "$post_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    post_status=unknown
fi
hx "$A" fetch-warmup-events "scp -q egw-tcg:/opt/egw/deployment/data/events/$RID.warmup/events.jsonl '$A/analysis/warmup.events.jsonl' && wc -l '$A/analysis/warmup.events.jsonl'"
warmup_rc=$?
post_window fetch-warmup-events "$warmup_rc" "the warm-up event log was not fetched"
hx "$A" after-snapshots "metrics $RID after && \$REC snap --prefix \$P/$RID --label after --like before"
snap_rc=$?
post_window after-snapshots "$snap_rc" "the 'after' snapshots were not taken"
# The four snapshots are the counter and twin baseline of the run, and this
# copy is the ONLY path by which the mandatory 'pre' and 'after-snapshots'
# evidence reaches the package: both calls are checked and the copy's own
# diagnostics are kept.
if mkdir -p "$A/analysis/snapshots" && cp "$P/$RID".* "$A/analysis/snapshots/"; then
    ls -l "$A/analysis/snapshots/"
else
    mandatory+=("the before/after snapshots were not copied into the package")
fi
# The accounting is the post-window ANALYSIS of the sealed window: one that
# could not be produced leaves the delivery unjudged (the outcome is then
# inconclusive), and never makes the measured window itself invalid.
ex "$A" identity-accounting "$PY" "$DRIVERS/nominal_account.py" "$RAWD" "$A/analysis/events.post-drain.jsonl" "$A/analysis" "$post_status"
account_rc=$?
post_window identity-accounting "$account_rc" "the identity accounting could not be produced"
gx "$A" guest-state-after "$GUEST_STATE"
after_rc=$?
# A LOST CONSOLE CAPTURE leaves a record that may hold part of what the guest
# answered, so what such a record does not hold was not observed and nothing
# read out of it is a fault the run showed: the comparison still runs and is
# kept, and what it reports is named as evidence that failed. Any other
# non-zero status is a step that ran and wrote its record: the readings it
# could not make are named inside it and the comparison turns them into
# problems of its own, while a fault the record positively holds stands.
after_trusted=1
[ "$after_rc" -eq "$EXIT_CAPTURE_LOST" ] && after_trusted=0
[ "$after_rc" -eq 0 ] || mandatory+=("$(step_note guest-state-after "$after_rc" "the guest state after the run was not recorded")")
AFTER=$(ls "$A"/console/*-guest-state-after.stdout.txt 2> /dev/null | tail -n 1)
if [ -n "$AFTER" ]; then
    # An OOM-killed, restarted, replaced or vanished container is a fact about
    # the run, not a note, and the six expected services must be in both
    # records: a state the pair does not name is not a state that was 'normal'.
    # The comparison separates the two: exit 1 is a fault the run SHOWED (a
    # result), exit 2 is a pair that could not be compared (no measurement).
    ex "$A" guest-state-delta "$PY" "$DRIVERS/guest_state_delta.py" --expect "$EXPECT_SERVICES" "$BEFORE" "$AFTER"
    delta_rc=$?
    DELTA_OUT=$(ls "$A"/console/*-guest-state-delta.stdout.txt 2> /dev/null | tail -n 1)
    seen_faults=$(delta_faults "$DELTA_OUT")
    # The status is read only when the comparison's own summary line is there
    # and says the same thing, because Python's 1 is also what an unhandled
    # exception leaves: a verdict that cannot be trusted is a pair that WAS NOT
    # COMPARED, never a fault that was observed.
    counts=$(delta_counts "$DELTA_OUT")
    delta_seen=0
    delta_trusted=0
    if [ -n "$counts" ]; then
        delta_seen=${counts%% *}
        delta_problems=${counts##* }
        case "$delta_rc" in
            0) [ "$delta_seen" -eq 0 ] && [ "$delta_problems" -eq 0 ] && delta_trusted=1 ;;
            1) [ "$delta_seen" -gt 0 ] && [ "$delta_problems" -eq 0 ] && delta_trusted=1 ;;
            2) [ "$delta_problems" -gt 0 ] && delta_trusted=1 ;;
        esac
    fi
    if [ "$delta_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note guest-state-delta)")
    elif [ "$delta_trusted" -eq 0 ]; then
        # No summary line, or one that does not agree with the status: what the
        # comparison left is not a verdict it reached, so nothing is read out of
        # it - not a fault, and not a clean pair either.
        mandatory+=("the two guest states could not be compared (guest-state-delta exit $delta_rc: the comparison itself failed, printing no 'guest-state-delta: faults=N problems=M' line that agrees with that status)")
    else
        # A pair that could not be compared is an evidence requirement that
        # failed, and a fault the same comparison positively SAW is a fact of
        # its own: both are recorded, in their own groups. A fault that was
        # observed never disappears because something else was indeterminate.
        [ "$delta_rc" -le 1 ] \
            || mandatory+=("the two guest states could not be compared (guest-state-delta exit $delta_rc)")
        if [ "$delta_seen" -gt 0 ] && [ "$after_trusted" -eq 1 ]; then
            observed+=("a container was OOM-killed or restarted during the run, or was replaced or is gone since it started (guest-state-delta exit $delta_rc; see console/)$seen_faults")
        elif [ "$delta_seen" -gt 0 ]; then
            mandatory+=("the comparison read the guest state after the run out of a record the driver already knows is incomplete (the console capture of that step failed), so what it reports about the containers was not established:$seen_faults")
        fi
    fi
else
    mandatory+=("the record of the guest state after the run was not kept")
fi

# Verdicts. The measured window's own record is the harness manifest, and it is
# read ON ITS OWN, so that a post-window analysis that could not be produced
# cannot invalidate a window the harness already sealed.
M=$("$PY" - "$RAWD" 2> /dev/null <<'PYEOF' || echo "invalid|the harness manifest could not be read"
import json, sys
m = json.load(open(sys.argv[1] + "/manifest.json"))
validity = "valid" if m.get("validity") == "valid" else "invalid"
reasons = "; ".join(m.get("validity_reasons") or [])
note = "manifest validity " + str(m.get("validity")) + ((" (" + reasons + ")") if reasons else "")
print(validity + "|" + note)
PYEOF
)
validity=${M%%|*}; manifest_note=${M#*|}
# Named as the requirement it is; what the manifest says ends the reason below.
[ "$validity" = valid ] || mandatory+=("the measured window's own record does not establish a valid run")

# The delivery row and the clock domain the 60 s confirmation deadline rests
# on, from the post-window accounting, read separately from the manifest. An
# accounting that cannot be read leaves the delivery UNJUDGED (outcome
# inconclusive) and is an incomplete observation, not invalid instrumentation.
# A verdict is never derived from the output of a step that FAILED: when the
# accounting did not complete, the delivery row and the clock domain are
# unknown and are not read at all, whatever bytes the file beside it holds.
if [ "$account_rc" -ne 0 ]; then
    D="inconclusive||the identity accounting did not complete, so the delivery row and the clock domain were not read"
else
D=$("$PY" - "$A/analysis/accounting.json" 2> /dev/null <<'PYEOF' || echo "inconclusive||the delivery row could not be read from analysis/accounting.json"
import json, sys
a = json.load(open(sys.argv[1]))
row = a["harness_row"]
FIGURES = ("sent_valid", "delivered_unique", "lost", "late_confirmations")
# A pass needs the four figures as whole numbers: 'delivered == sent' is true
# of two counts that are both ABSENT as well, and a row that does not carry
# them judges no delivery at all.
missing = [f for f in FIGURES
           if not isinstance(row.get(f), int) or isinstance(row.get(f), bool)]
if missing:
    outcome = "inconclusive"
elif row["lost"] == 0 and row["late_confirmations"] == 0 and row["delivered_unique"] == row["sent_valid"]:
    outcome = "pass"
else:
    outcome = "fail"
marker = a.get("controller_marker")
source = row.get("confirmation_deadline_source")
if not (isinstance(marker, dict) and marker.get("ok") is True):
    state = marker.get("ok") if isinstance(marker, dict) else marker
    clock = ("the clock domain the confirmation deadline rests on is not intact: "
             "controller_marker.ok is " + str(state))
elif source != "controller-marker":
    clock = ("the clock domain the confirmation deadline rests on is not intact: "
             "confirmation_deadline_source is " + str(source) + ", not controller-marker")
else:
    clock = ""
# A tail that was not fetched is named as such, never printed as a count of
# identities nobody observed after the drain.
tail = a.get("after_drain")
if tail is None:
    tail = a.get("after_drain_note") or "the post-drain event log was not read"
reason = ("delivery at the harness fetch: sent_valid " + str(row.get("sent_valid"))
          + ", delivered " + str(row.get("delivered_unique")) + ", lost " + str(row.get("lost"))
          + ", late " + str(row.get("late_confirmations"))
          + "; after the drain: " + str(tail))
if missing:
    reason += ("; the row does not carry " + ", ".join(missing)
               + " as whole numbers, so the delivery was not judged")
print(outcome + "|" + clock + "|" + reason)
PYEOF
)
fi
outcome=${D%%|*}; rest=${D#*|}; clock=${rest%%|*}; delivery=${rest#*|}
# Named once: what the delivery row itself says ends the reason below, so the
# group here carries the consequence and not a second copy of that sentence.
[ "$outcome" != inconclusive ] || incomplete+=("the delivery of the measured window was not judged")
# A fault that also breaks a stated evidence requirement is that specific
# invalidity, named as the requirement and not as the fault.
[ -z "$clock" ] || mandatory+=("$clock")

status=finished
[ "$h_rc" -eq 0 ] || status=failed
if [ "${#observed[@]}" -ne 0 ]; then
    # Observing the system fail is a RESULT: the system outcome fails and the
    # measurement stays as valid as the evidence says. A fault that was
    # observed is the outcome even when the delivery row could not be read,
    # and the reason then says that those figures were not read.
    outcome=fail
    status=failed
elif [ "${#incomplete[@]}" -ne 0 ] && [ "$outcome" = pass ]; then
    # A clean pass is the one verdict that needs COMPLETE evidence: a
    # post-window observation that could not be made leaves the run
    # inconclusive (exit 3, so nothing dependent proceeds), with the sealed
    # window's own validity untouched and the reason naming what is missing.
    outcome=inconclusive
fi
if [ "${#mandatory[@]}" -ne 0 ]; then
    # Evidence that is missing, unreadable or does not meet a stated
    # requirement: the instrumentation is invalid, and every fault the run
    # showed is kept as a fact beside it. A PASS is the one verdict that cannot
    # be asserted on evidence known to be incomplete; a failure is kept.
    status=failed
    validity=invalid
    [ "$outcome" != pass ] || outcome=inconclusive
fi
# The three groups stay distinct, in this order: what the system did, which
# evidence requirements failed, which post-window observations are incomplete.
reason=""
[ "${#observed[@]}" -eq 0 ] || reason="observed system fault(s): $(printf '%s; ' "${observed[@]}")"
[ "${#mandatory[@]}" -eq 0 ] || reason="${reason}evidence requirement(s) not met: $(printf '%s; ' "${mandatory[@]}")"
if [ "${#incomplete[@]}" -ne 0 ]; then
    reason="${reason}post-window observation(s) incomplete: $(printf '%s; ' "${incomplete[@]}")"
    (cd "$REPO/src" && $LE set --attempt "$A" \
        "post_window_observations=incomplete: $(printf '%s; ' "${incomplete[@]}")") \
        || echo "the incomplete post-window observations could not be recorded as a field" >&2
fi
reason="${reason}${manifest_note}; ${delivery}"
(cd "$REPO/src" && $LE finish --attempt "$A" --status "$status" --validity "$validity" --outcome "$outcome" \
    --reason "$reason (harness exit $h_rc)" --next-action "see analysis/accounting.json; delivery and instrumentation are separate verdicts")
echo "NOMINAL $RID: validity=$validity outcome=$outcome harness_exit=$h_rc observed=${#observed[@]} mandatory=${#mandatory[@]} incomplete=${#incomplete[@]}"
driver_exit "$A"
