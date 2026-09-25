#!/bin/bash
# proof.sh - the finite proof of ADR 0011 ("The finite proof"): one bounded
# engineering diagnostic of the controller's restart recovery on the emulated
# guest, driven from the WSL2 host and exported as one attempt.
#
# AN ENGINEERING DIAGNOSTIC, NOT A G3 RUN. It is not a qualifying run, not a
# repetition of any pilot run, not a campaign, soak or pilot; it changes no
# threshold, deadline, load or rule. One run supports the property for that
# run only; it does not prove it in general (ADR 0011, "What the proof
# cannot show").
#
# WHAT IT DOES. After the prerequisites and 'pre' (ready, drained, the
# /metrics reading and the configuration identity captured on the guest), it
# runs ONE harness run of a one-entry diagnostic plan (proof_plan.py: the
# controller_restart condition's load - the nominal scenario at 11.2 msg/s,
# three wearables, no warm-up - for 300 s of publication), with the fault
# issued by the harness restart hook at t+150 s: SIGKILL of the controller's
# container followed by a start (proof_restart_controller.sh). The harness
# takes the twin snapshot before the run and after the drain
# (proof_hook_twins.sh), the drain (proof_hook_drained.sh: the runbook's
# 'drained' with the values recorded below), the post-drain copy of the
# events and the three SUT logs (proof_fetch_sut_log.sh), and seals the run
# directory under EGW_PROOF_BASE. The driver then shows the restart from its
# own records, takes the /metrics reading after, runs the runbook's 'delta'
# on the post-drain copy, packages the prefix snapshots, writes the session
# facts (proof_session.py), evaluates the run with the proof's evaluator
# (egw_experiments.proof_evaluator: S1-S6, R1-R4 and the inconclusive rule,
# by identity), records the guest's container state after the run against
# the state before it, and waits for the stack to be running and healthy
# again, which is the restoration.
#
# THREE VERDICTS, NEVER MERGED.
#   instrumentation validity  'valid' only when every mandatory record was
#     made AND the proof's evidence is complete (the evaluator's
#     instrumentation.proof_evidence.complete: both twin snapshots, a verified
#     drain, the post-drain copy, the three SUT logs, the configuration
#     identity, a readable pre-kill reading, the seal). The harness's OWN
#     validity is quoted verbatim in the reason and does NOT decide the
#     proof: an invalid run under MAX_SAMPLE_GAP_S is expected, and that
#     verdict "belongs to the campaign rules and is kept as recorded" (ADR
#     0011, "What the proof cannot show"; design flag P-8, a deviation from
#     nominal.sh, which makes the manifest's validity mandatory).
#   system outcome  the evaluator's exit code - 0 supports -> pass, 1
#     refutes -> fail (a valid negative result, "recorded and preserved,
#     never re-run away"), 3 inconclusive -> inconclusive, 2 (not evaluated)
#     -> inconclusive and a mandatory record missing - and, beside it, any
#     fault of the guest state the run positively showed (an OOM kill, a
#     replacement, another container's restart: guest_state_delta.py, which
#     reads the controller's one in-place restart as expected), which makes
#     the outcome fail as nominal.sh reads such a fault.
#   restoration outcome  the field 'restoration=stack=<healthy|not-healthy|
#     unknown> restart_shown=<yes|no|unknown>': a pass is never reported
#     when the stack is not running and healthy again, and every reason ends
#     with the state the guest was left in.
#
# STOP RULES, IMPOSED BY DESIGN AND NOT MEASURED DURATIONS (ADR 0011, "The
# finite proof", ceiling): the stack with the candidate healthy within
# EGW_HEALTH_LIMIT_S (1200 s, the 20-minute rule) of its start, on the same
# records as the broker measurement (the shared healthy_wait); the attempt
# stopped EGW_PROOF_ATTEMPT_LIMIT_S (3000 s, the 50-minute rule) after its
# first 'drained' starts, measured on /proc/uptime (the host's wall clock is
# stepped backwards on this host) and enforced on the harness step with
# 'timeout'. If a stop rule is reached the session stops and the proof is
# recorded inconclusive; the restoration is never cut short to keep a total
# duration. The values used are recorded before anything starts - on the
# attempt (workload.values) and in analysis/proof_session.json - and the
# student may set other values before the session.
#
# WHAT IT NEVER DOES WITHOUT AUTHORISATION. It never boots or powers off the
# guest (guest_session_open.sh / guest_session_close.sh); never builds,
# pulls, loads or retags an image; never edits the pilot plan or writes
# under ~/egw-tcg/pilot/ (the plan is read only to refuse a run id it
# holds); never repeats C3; never runs the optional extension of ADR 0011
# item 4 section 9 unless EGW_PROOF_EXTENSION=yes is set by the student;
# never runs a second attempt by itself (a repeat is the student's
# decision); never lowers DRAIN_QUIET_S below 130 s ("Never lower it",
# runbook 6.1); never changes a clock, a criterion or a validator; and
# refuses to start without an open, separately authorised session.
#
# Usage: proof.sh RUN_ID EXPECTED_SOURCE_COMMIT
#   RUN_ID                  a fresh run id never used on the guest
#   EXPECTED_SOURCE_COMMIT  the commit (7 to 40 hex) the candidate controller
#                           image on the guest must carry (config_identity's
#                           controller_source_commit); a prefix match
# Environment (the defaults are the ADR's figures; each is read as a whole
# number or the driver stops before anything starts):
#   DRAIN_QUIET_S (130, never below 130) DRAIN_STEP_S (5) DRAIN_LIMIT_S (900)
#   EGW_HEALTH_LIMIT_S (1200) EGW_HEALTH_STEP_S (15) EGW_READY_LIMIT_S (300)
#   EGW_PROOF_ATTEMPT_LIMIT_S (3000) EGW_PROOF_RESTART_AT_S (150)
#   EGW_PROOF_DURATION_S (300) EGW_PROOF_RATE (11.2) - the load is fixed by
#   proof_plan.py; a different value stops the driver, it never changes it
#   EGW_PROOF_MASTER_SEED (no default: the student's decision)
#   EGW_PROOF_EXTENSION (no; 'yes' runs the optional extension)
#   EGW_PROOF_EXTENSION_LIMIT_S (1790: the 130 s stop_grace_period recorded
#   under C6 plus 1,660 s, ADR 0011)
#   EGW_PROOF_BASE (~/egw-tcg/proof/results) EGW_PROOF_PLAN
#   (~/egw-tcg/proof/plan-RUN_ID.json) EGW_PROOF_RUNBOOK (the clone's
#   docs/setup/qemu_integrated_gateway.md, whose 6.1 heredoc the deployed
#   helper file must equal)
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
# A missing argument is a prerequisite (2), never the 1 of a valid negative
# result: '${1:?...}' would end the shell with 1 before any check could run.
[ "$#" -eq 2 ] || driver_stop "$EXIT_PREREQUISITE" "usage: proof.sh RUN_ID EXPECTED_SOURCE_COMMIT (a run id never used on the guest; the commit the candidate image must carry)"
RID=$1
EXPECTED_COMMIT=$2
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
case "$RID" in
    '' | *[!A-Za-z0-9._-]* | . | ..) driver_stop "$EXIT_PREREQUISITE" "RUN_ID '$RID' is not a plain run id (letters, digits, '.', '_' and '-'); nothing was started" ;;
esac
[[ $EXPECTED_COMMIT =~ ^[0-9a-f]{7,40}$ ]] \
    || driver_stop "$EXIT_PREREQUISITE" "EXPECTED_SOURCE_COMMIT '$EXPECTED_COMMIT' is not 7 to 40 hex characters; nothing was started"
command -v timeout > /dev/null || driver_stop "$EXIT_PREREQUISITE" "'timeout' is not installed on the host; nothing was started"

# --- the values (recorded before anything starts) -----------------------------
DRAIN_QUIET_S=${DRAIN_QUIET_S:-130}
DRAIN_STEP_S=${DRAIN_STEP_S:-5}
DRAIN_LIMIT_S=${DRAIN_LIMIT_S:-900}
for v in DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S; do
    case "${!v}" in
        '' | *[!0-9]*) driver_stop "$EXIT_PREREQUISITE" "$v='${!v}' is not a whole number of seconds; nothing was started" ;;
    esac
done
[ "$DRAIN_QUIET_S" -ge 130 ] \
    || driver_stop "$EXIT_PREREQUISITE" "DRAIN_QUIET_S=$DRAIN_QUIET_S is below the runbook's 130 s ('Never lower it', 6.1); nothing was started"
# The hooks the harness runs read the three from the environment.
export DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S
LIMIT=$(healthy_seconds EGW_HEALTH_LIMIT_S 1200) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_LIMIT_S is not a whole number of seconds; nothing was started"
STEP=$(healthy_seconds EGW_HEALTH_STEP_S 15) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_STEP_S is not a whole number of seconds; nothing was started"
READY_LIMIT=$(healthy_seconds EGW_READY_LIMIT_S 300) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_READY_LIMIT_S is not a whole number of seconds; nothing was started"
ATTEMPT_LIMIT=$(healthy_seconds EGW_PROOF_ATTEMPT_LIMIT_S 3000) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_ATTEMPT_LIMIT_S is not a whole number of seconds; nothing was started"
RESTART_AT=$(healthy_seconds EGW_PROOF_RESTART_AT_S 150) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_RESTART_AT_S is not a whole number of seconds; nothing was started"
DURATION=$(healthy_seconds EGW_PROOF_DURATION_S 300) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_DURATION_S is not a whole number of seconds; nothing was started"
EXTENSION_LIMIT=$(healthy_seconds EGW_PROOF_EXTENSION_LIMIT_S 1790) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_EXTENSION_LIMIT_S is not a whole number of seconds; nothing was started"
RATE=${EGW_PROOF_RATE:-11.2}
case "$RATE" in
    '' | *[!0-9.]* | .* | *.) driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_RATE='$RATE' is not a number; nothing was started" ;;
esac
MASTER_SEED=${EGW_PROOF_MASTER_SEED:-}
case "$MASTER_SEED" in
    '' | *[!0-9]*) driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_MASTER_SEED='$MASTER_SEED' is not a whole number (the master seed is the student's decision, and it has no default); nothing was started" ;;
esac
EXTENSION=${EGW_PROOF_EXTENSION:-no}
case "$EXTENSION" in
    yes | no) ;;
    *) driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_EXTENSION='$EXTENSION' is neither 'yes' nor 'no'; nothing was started" ;;
esac
BASE=${EGW_PROOF_BASE:-$HOME/egw-tcg/proof/results}
PLAN=${EGW_PROOF_PLAN:-$HOME/egw-tcg/proof/plan-$RID.json}
RUNBOOK=${EGW_PROOF_RUNBOOK:-$REPO/docs/setup/qemu_integrated_gateway.md}
PILOT_PLAN=$HOME/egw-tcg/pilot/campaign_plan.json
HELPERS=$HOME/egw-tcg/itest-helpers.sh
DEPLOYED=${EGW_DEPLOYED_DIR:-/opt/egw/deployment}
P=$HOME/egw-tcg/itest
RAWD=$BASE/raw/$RID
CONTROLLER=egw-controller-1
# Every value written into a guest command or into the harness step's shell
# text is checked ONCE, before anything starts, to be the literal it is.
for value in "$RID" "$EXPECT_SERVICES" "$DEPLOYED" "$DC" "$BASE" "$PLAN" "$P" "$DRIVERS" "$REPO" "$HOME"; do
    guest_literal "$value" \
        || driver_stop "$EXIT_PREREQUISITE" "'$value' cannot be written into a command as the literal it is; nothing was started"
done

# --- write-once: a run id is used once, on the guest and on the host ------------
[ ! -e "$RAWD" ] || driver_stop "$EXIT_PREREQUISITE" "$RAWD exists; use another run id (the run directory is write-once); nothing was started"
[ ! -e "$PLAN" ] || driver_stop "$EXIT_PREREQUISITE" "$PLAN exists; use another run id (the plan is write-once); nothing was started"
if compgen -G "$P/$RID.*" > /dev/null || [ -e "$P/$RID" ]; then
    driver_stop "$EXIT_PREREQUISITE" "$P/$RID.* exists: this run id was already used and its artefacts are write-once; use another run id; nothing was started"
fi

A=$(new_attempt "finite proof (ADR 0011)" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
trap 'driver_interrupt "$A"' INT TERM
guest_literal "$A" || driver_stop "$EXIT_PREREQUISITE" "the attempt directory '$A' cannot be written into a command as the literal it is; nothing was started"
ENVD=$A/environment
ANALYSIS=$A/analysis
SNAPS=$ANALYSIS/snapshots
FACTS=$ANALYSIS/proof_session.json
VERDICT=$ANALYSIS/proof_verdict.json
mkdir -p "$ENVD" "$ANALYSIS" || driver_stop "$EXIT_PREREQUISITE" "$ENVD could not be created"

# --- the state this driver knows the guest to be in -----------------------------
STACK_STATE=untouched    # untouched | healthy | not-healthy | unknown
RESTART_SHOWN=unknown    # unknown | yes | no
HARNESS_STARTED=0        # once the harness step was dispatched the outcome is never 'not-run'
RESTORED=0               # the restoration wait was run
RESTORE_NOTE=""          # what the restoration found when the stack did not come back
mandatory=()             # evidence missing or unreadable: the instrumentation is invalid
observed=()              # faults the run positively showed: the system outcome fails
incomplete=()            # post-window observations that could not be made
stoprules=()             # stop rules reached
FIRST=""
h_rc=none
v_rc=none
delta_rc=none
EVALUATOR_RESULT=not-computed
EXTENSION_RESULT=not-chosen

first_note() { [ -n "$FIRST" ] || FIRST=$1; }
missed() { mandatory+=("$1"); first_note "$1"; }
now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
uptime_s() { local up; read -r up _ < /proc/uptime; printf '%s' "${up%.*}"; }
set_field() { (cd "$REPO/src" && $LE set --attempt "$A" "$1") > /dev/null 2>&1 || true; }
guest_state_text() { printf 'stack=%s restart_shown=%s' "$STACK_STATE" "$RESTART_SHOWN"; }
# said NAME PREFIX: the lines of NAME's console record that start with PREFIX,
# without it, on one line (broker_measure.sh).
said() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    [ -n "$f" ] && [ -f "$f" ] || return 0
    sed -n "s/^$2//p" "$f" | tr '\n' ' '
}
# last_line NAME: the last line of NAME's console record (one /metrics reading
# of _mline is the last line the step printed), or nothing.
last_line() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    [ -n "$f" ] && [ -f "$f" ] || return 0
    tail -n 1 "$f"
}
# keep_record NAME FILE WHAT: the console record of NAME kept as environment/FILE.
keep_record() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    if [ -n "$f" ] && [ -f "$f" ] && cp "$f" "$ENVD/$2"; then
        return 0
    fi
    missed "$3 was not kept in environment/$2"
    return 1
}
# session_update KEY=VALUE...: the session facts, merged into the record the
# evaluator reads (proof_session.py keeps it a whole document at every step).
session_update() {
    [ -f "$FACTS" ] || return 0
    "$PY" "$DRIVERS/proof_session.py" update "$FACTS" "$@" > /dev/null \
        || missed "the session facts could not be updated ($*)"
}
# stoprule RULE_ID TEXT: a stop rule reached, recorded in the session facts
# (the evaluator reads 'reached' and records the proof inconclusive) and in
# the reason.
stoprule() {
    local at
    at=$(now_utc)
    stoprules+=("$2")
    first_note "$2"
    if [ -f "$FACTS" ]; then
        "$PY" "$DRIVERS/proof_session.py" reach "$FACTS" "$1" "$at" > /dev/null \
            || missed "the stop rule reached ($1) could not be recorded in the session facts"
    fi
}
# left: what remains of the attempt's allowance, in whole seconds, on the
# host's monotonic clock (/proc/uptime), never below 0.
left() {
    local now rest
    now=$(uptime_s)
    rest=$((ATTEMPT_LIMIT - (now - T0)))
    [ "$rest" -gt 0 ] || rest=0
    printf '%s' "$rest"
}

# --- identities and the record of the values ----------------------------------
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
VALUES=$(printf '{"DRAIN_QUIET_S": %s, "DRAIN_STEP_S": %s, "DRAIN_LIMIT_S": %s, "EGW_HEALTH_LIMIT_S": %s, "EGW_HEALTH_STEP_S": %s, "EGW_READY_LIMIT_S": %s, "EGW_PROOF_ATTEMPT_LIMIT_S": %s, "EGW_PROOF_RESTART_AT_S": %s, "EGW_PROOF_DURATION_S": %s, "EGW_PROOF_RATE": %s, "EGW_PROOF_MASTER_SEED": %s, "EGW_PROOF_EXTENSION": "%s", "EGW_PROOF_EXTENSION_LIMIT_S": %s, "EGW_PROOF_BASE": "%s", "EGW_PROOF_PLAN": "%s", "expected_source_commit": "%s"}' \
    "$DRAIN_QUIET_S" "$DRAIN_STEP_S" "$DRAIN_LIMIT_S" "$LIMIT" "$STEP" "$READY_LIMIT" "$ATTEMPT_LIMIT" "$RESTART_AT" "$DURATION" "$RATE" "$MASTER_SEED" "$EXTENSION" "$EXTENSION_LIMIT" "$BASE" "$PLAN" "$EXPECTED_COMMIT")
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$IDENTITIES" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"proof\": \"the finite proof (ADR 0011)\", \"engineering_diagnostic_not_a_g3_run\": true, \"harness_run_id\": \"$RID\", \"condition\": \"controller_restart\", \"scenario\": \"nominal\", \"warmup_s\": 0, \"duration_s\": $DURATION, \"rate_msg_s\": $RATE, \"restart_at_s\": $RESTART_AT, \"fault\": \"SIGKILL of the controller's container followed by a start (proof_restart_controller.sh)\", \"devices\": \"smartwatch, smart ring, smart clothing (nominal mix)\", \"values\": $VALUES}" \
    "proof_verdict=not-computed" "restoration=not-started" "restart_shown=unknown" "extension=$EXTENSION_RESULT" \
    'expected_artefacts=["raw/*/manifest.json", "raw/*/sent_events.jsonl", "raw/*/events.jsonl", "raw/*/events.post-drain.jsonl", "raw/*/twins.before.json", "raw/*/twins.after.json", "raw/*/configuration_identity.json", "raw/*/controller_metrics.csv", "raw/*/resources.csv", "raw/*/logs/sut/broker.log", "raw/*/logs/sut/controller.log", "raw/*/logs/sut/docker-events.log", "raw/*/SHA256SUMS", "analysis/proof_session.json", "analysis/proof_verdict.json", "analysis/snapshots/*.config_identity.json", "analysis/snapshots/*.metrics.before.json", "analysis/snapshots/*.metrics.after.json", "analysis/snapshots/*.twins.before.json", "analysis/snapshots/*.twins.after.json", "analysis/snapshots/*.restart.txt", "environment/proof_plan.json", "environment/sut_environment.json", "environment/clocks.txt", "environment/containers.before.txt", "environment/containers.after.txt", "environment/helpers-check.txt"]') \
    || PREREQ="the attempt fields could not be recorded"
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || PREREQ=${PREREQ:-"the identity of the clean clone could not be read (see identities.identity_error)"}

# not_run REASON: a prerequisite failed, so the harness was never started.
not_run() {
    headline "$A" "$1: the harness was NOT started" || true
    set_field "restoration=$(guest_state_text)"
    session_update "restoration=$(guest_state_text)" "instants.ended_utc=$(now_utc)"
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "$1; the harness was NOT started; the guest was left with $(guest_state_text)" \
        --next-action "read console/; the harness was NOT started and nothing was published under $RID")
    driver_exit "$A"
}
[ -z "${PREREQ:-}" ] || not_run "$PREREQ"
(cd "$REPO/src" && $LE add-source --attempt "$A" --kind raw --path "$RAWD" \
    --role "harness raw run directory of the finite proof (sealed by the harness if complete)") \
    || not_run "the raw capsule could not be registered as a source"
(cd "$REPO/src" && $LE add-source --attempt "$A" --kind simulator --path "$P/$RID.config_identity.json" --siblings-glob "$RID.*" \
    --role "the prefix files of runbook 6.1 (configuration identity, /metrics readings, twin snapshots, restart record)") \
    || not_run "the prefix siblings could not be registered as a source"

# --- restoration: what every ending after the harness does ----------------------
# The proof mutates only the controller container (kill + start). The
# restoration is the six services running and healthy again, through the
# wait shared with gate_health.sh and persistence.sh, bounded by the same
# EGW_HEALTH_LIMIT_S; it is never cut short by the attempt's allowance.
restore() {
    [ "$HARNESS_STARTED" -eq 1 ] || return 0
    [ "$RESTORED" -eq 0 ] || return 0
    RESTORED=1
    local rc
    healthy_wait "$A" services-healthy-after "$LIMIT" "$STEP"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        STACK_STATE=healthy
    elif [ "$rc" -eq 1 ] || [ "$rc" -eq 4 ]; then
        # The restoration's own outcome, kept apart from the proof's result:
        # a pass is never reported on it (design 2.9), and the reason says so.
        STACK_STATE=not-healthy
        RESTORE_NOTE="the stack was not running and healthy again within ${LIMIT} s after the run:$(said services-healthy-after 'NOT HEALTHY[^:]*:')"
        first_note "$RESTORE_NOTE"
    elif [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        STACK_STATE=unknown
        mandatory+=("$(capture_note services-healthy-after)")
    else
        STACK_STATE=unknown
        missed "$(step_note services-healthy-after "$rc" "whether the stack is healthy again could not be determined (services-healthy-after exit $rc)")"
    fi
    set_field "restoration=$(guest_state_text)"
    session_update "restoration=$(guest_state_text)"
}
on_interrupt() {
    trap - INT TERM
    local at
    at=$(now_utc)
    session_update "instants.interrupted_utc=$at"
    if [ "$HARNESS_STARTED" -eq 1 ]; then
        restore
    fi
    set_field "restoration=$(guest_state_text)"
    session_update "restoration=$(guest_state_text)"
    headline "$A" "interrupted; the guest was left with $(guest_state_text)" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status interrupted --outcome interrupted \
        --reason "driver interrupted at $at; the guest was left with $(guest_state_text)" \
        --next-action "if the stack is not healthy, resolve it before any other guest session; the run directory $RAWD, sealed or not, is preserved as incomplete and is never replaced" 2> /dev/null)
    driver_exit "$A"
}
trap on_interrupt INT TERM

# --- 1. the deployed helper file is the runbook's 6.1 heredoc -------------------
# The hooks and 'pre' run the deployed 'drained', '_mline', 'metrics', 'keep'
# and 'config_identity': a file that differs from the reviewed heredoc would
# drain and identify the run with functions nobody reviewed.
ex "$A" helpers-check "$PY" "$DRIVERS/proof_helpers_check.py" "$RUNBOOK" "$HELPERS"
rc=$?
if [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" helpers-check "the harness was NOT started"
fi
keep_record helpers-check helpers-check.txt "the helper file check" || true
[ "$rc" -eq 0 ] || not_run "the deployed helper file $HELPERS is not the runbook's section 6.1 heredoc, so the 'drained', '_mline' and 'config_identity' in use are not the reviewed ones (helpers-check exit $rc: regenerate it with regen_helpers.py)"

# --- 2. the deployed collector is the clean clone's (nominal.sh) ----------------
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

# --- 3. the clocks: guest and host, and their offset (informational) --------------
# The guest epoch is also what the three SUT log fetches are bounded from
# (proof_fetch_sut_log.sh SINCE_GUEST_EPOCH), so it must be a whole number.
gx "$A" guest-clock "date +%s; date -u +%Y-%m-%dT%H:%M:%SZ; timedatectl show 2>&1 || echo 'timedatectl: not read'"
clock_rc=$?
[ "$clock_rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" guest-clock "the harness was NOT started"
HOST_EPOCH=$(date +%s)
HOST_UTC=$(now_utc)
HOST_UPTIME=$(uptime_s)
GUEST_EPOCH=$(said guest-clock '' | cut -d' ' -f1)
GUEST_UTC=$(said guest-clock '' | cut -d' ' -f2)
case "$GUEST_EPOCH" in
    '' | *[!0-9]*) not_run "the guest clock could not be read (guest-clock exit $clock_rc)" ;;
esac
OFFSET=$((GUEST_EPOCH - HOST_EPOCH))
{
    echo "host_utc=$HOST_UTC"
    echo "host_epoch=$HOST_EPOCH"
    echo "host_uptime_s=$HOST_UPTIME"
    echo "guest_epoch=$GUEST_EPOCH"
    echo "guest_utc=$GUEST_UTC"
    echo "offset_s=$OFFSET"
    echo "note=the offset is informational: no criterion of the proof involves timing, and the host wall clock is stepped on this host; the driver's budget runs on /proc/uptime"
    said guest-clock '' | tr ' ' '\n' | sed -n '3,$p' | sed 's/^/guest_timedatectl=/'
} > "$ENVD/clocks.txt" || not_run "environment/clocks.txt could not be written"

# --- 4. the session facts: the values and the stop rules, before anything starts ----
ex "$A" session-facts "$PY" "$DRIVERS/proof_session.py" write "$FACTS" \
    --healthy-limit-s "$LIMIT" --attempt-limit-s "$ATTEMPT_LIMIT" \
    "values=$VALUES" "clocks.host_utc=$HOST_UTC" "clocks.host_epoch=$HOST_EPOCH" "clocks.host_uptime_s=$HOST_UPTIME" \
    "clocks.guest_epoch=$GUEST_EPOCH" "clocks.guest_utc=$GUEST_UTC" "clocks.offset_s=$OFFSET" \
    "run_id=$RID" "attempt=$(basename "$A")" "session=$(basename "$SESSION")"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" session-facts "the harness was NOT started"
[ "$rc" -eq 0 ] && [ -s "$FACTS" ] || not_run "the session facts (analysis/proof_session.json) could not be written (session-facts exit $rc)"

# --- 5. the stack healthy: the first stop rule --------------------------------------
healthy_wait "$A" services-healthy "$LIMIT" "$STEP"
rc=$?
if [ "$rc" -eq 0 ]; then
    STACK_STATE=healthy
elif [ "$rc" -eq 1 ] || [ "$rc" -eq 4 ]; then
    STACK_STATE=not-healthy
    stoprule healthy "stop rule reached: the stack was not running and healthy within ${LIMIT} s:$(said services-healthy 'NOT HEALTHY[^:]*:')"
    not_run "stop rule reached: the stack with the candidate was not running and healthy within ${LIMIT} s (services-healthy exit $rc); the proof is recorded inconclusive by that rule"
elif [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" services-healthy "the harness was NOT started"
else
    STACK_STATE=unknown
    not_run "$(step_note services-healthy "$rc" "whether the stack is running and healthy could not be determined (services-healthy exit $rc)")"
fi

# --- 6. the SUT environment with the emulation label (preflight.sh) --------------
gx "$A" sut-environment "cd /opt/egw/deployment && EGW_PROVIDER='QEMU 8.2.7 TCG (qemu-system-native) on WSL2 Ubuntu-24.04, Windows 11 x86-64' EGW_REGION='local-workstation' EGW_INSTANCE_TYPE='qemu -machine virt -cpu cortex-a76 -smp 4 -m 8192; ARM64 EMULATED' EGW_SHARED_VCPU_NOTE='TCG emulation on a shared x86-64 host; load generator co-located; never native ARM64' sh scripts/capture-sut-environment.sh /opt/egw/evidence/sut_environment.json && cat /opt/egw/evidence/sut_environment.json"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" sut-environment "the harness was NOT started"
[ "$rc" -eq 0 ] || not_run "the SUT environment capture failed (sut-environment exit $rc)"
gcp "$A" sut-environment-fetch egw@127.0.0.1:/opt/egw/evidence/sut_environment.json "$ENVD/sut_environment.json"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" sut-environment-fetch "the harness was NOT started"
[ "$rc" -eq 0 ] && [ -s "$ENVD/sut_environment.json" ] || not_run "the SUT environment capture was not fetched (sut-environment-fetch exit $rc)"

# --- 7. the guest's container state and the controller process, before -----------
# The guest's container state in the identical form before and after the run
# (nominal.sh): OOM kills and restarts are read from the pair, never from the
# 'after' alone. The container id, RestartCount and StartedAt go into the
# record because the proof's own kill + start keeps the container object
# (same id, later StartedAt, RestartCount untouched), which is exactly what
# guest_state_delta.py --expect-restarted reads as the expected restart.
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
    not_run "the guest state before the run was not recorded (exit $before_rc)"
fi
BEFORE=$(ls "$A"/console/*-guest-state-before.stdout.txt 2> /dev/null | tail -n 1)
[ -n "$BEFORE" ] || not_run "the record of the guest state before the run was not kept"

# containers_script: the id and the start instant of each expected container
# (persistence.sh), in the identical form before and after the run; the
# restart-shown step reads the controller's pair from the two records.
containers_script() {
    printf "EXPECT='%s'\nDEPLOYED='%s'\n" "$EXPECT_SERVICES" "$DEPLOYED"
    cat << 'GUEST_CONTAINERS'
cd "$DEPLOYED" || { echo "STOP: $DEPLOYED could not be entered"; exit 1; }
rc=0
IFS=,
set -- $EXPECT
unset IFS
for s in "$@"; do
    cid=$(docker inspect -f '{{.Id}}' "$s" 2> /dev/null) || rc=1
    sat=$(docker inspect -f '{{.State.StartedAt}}' "$s" 2> /dev/null) || rc=1
    echo "container $s id=${cid:-unknown} started=${sat:-unknown}"
    [ -n "$cid" ] && [ -n "$sat" ] || rc=1
done
exit $rc
GUEST_CONTAINERS
}
gx "$A" containers-before "$(containers_script)"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" containers-before "the harness was NOT started"
[ "$rc" -eq 0 ] || not_run "the containers' ids and start instants were not recorded before the run (containers-before exit $rc)"
keep_record containers-before containers.before.txt "the containers before the run" \
    || not_run "the record of the containers before the run was not kept"
# The controller PROCESS before the run: one /metrics reading through the
# runbook's _mline (thirteen fields; started_at is the fifth). Status 3 is a
# reading whose accounting identity does not hold - still a reading of the
# process, kept as such - and anything else is no reading at all.
hx "$A" controller-process-before "_mline"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" controller-process-before "the harness was NOT started"
[ "$rc" -eq 0 ] || [ "$rc" -eq 3 ] || not_run "$(step_note controller-process-before "$rc" "the controller process could not be read before the run (_mline exit $rc)")"
STARTED_BEFORE=$(last_line controller-process-before | cut -d' ' -f5)
[ -n "$STARTED_BEFORE" ] || not_run "the controller's started_at was not read before the run"

# --- 8. the one-entry diagnostic plan --------------------------------------------
# proof_plan.py refuses a run id the pilot plan holds (read only, never
# edited) and one the campaign plan enumerates; the plan is write-once.
pilot_args=()
[ ! -f "$PILOT_PLAN" ] || pilot_args=(--pilot-plan "$PILOT_PLAN")
ex "$A" proof-plan env PYTHONPATH="$REPO/src" "$PY" "$DRIVERS/proof_plan.py" write --run-id "$RID" --master-seed "$MASTER_SEED" --out "$PLAN" "${pilot_args[@]}"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" proof-plan "the harness was NOT started"
[ "$rc" -eq 0 ] && [ -s "$PLAN" ] || not_run "the diagnostic plan was not written (proof-plan exit $rc: $(said proof-plan ''))"
PLAN_LINE=$(said proof-plan 'wrote ')
plan_value() { printf '%s' "$PLAN_LINE" | tr ' ' '\n' | sed -n "s/^$1=//p" | head -n 1; }
SEED=$(plan_value seed)
PLAN_SHA=$(plan_value sha256)
PLAN_DURATION=$(plan_value duration_s)
PLAN_RATE=$(plan_value rate_msg_s)
case "$SEED" in
    '' | *[!0-9]*) not_run "the plan's derived seed could not be read from proof-plan's line" ;;
esac
[[ $PLAN_SHA =~ ^[0-9a-f]{64}$ ]] || not_run "the plan's sha256 could not be read from proof-plan's line"
# The load is the ADR's and proof_plan.py fixes it: this driver never changes
# a load, so a value that differs from the plan's stops it here.
[ "$PLAN_DURATION" = "$DURATION" ] && [ "$PLAN_RATE" = "$RATE" ] \
    || not_run "EGW_PROOF_DURATION_S=$DURATION / EGW_PROOF_RATE=$RATE differ from the plan's duration_s=$PLAN_DURATION / rate_msg_s=$PLAN_RATE, which proof_plan.py fixes at the ADR's figures; the driver changes no load"
cp "$PLAN" "$ENVD/proof_plan.json" || not_run "the plan could not be kept in environment/"
printf '%s  proof_plan.json\n' "$PLAN_SHA" > "$ENVD/proof_plan.sha256" || not_run "the plan's sha256 could not be kept"
set_field "seed=$SEED"
session_update "plan.path=$PLAN" "plan.sha256=$PLAN_SHA" "plan.seed=$SEED" "plan.master_seed=$MASTER_SEED" "plan.duration_s=$PLAN_DURATION" "plan.rate_msg_s=$PLAN_RATE"

# --- 9. pre: the first 'drained' starts here, and so does the attempt's clock ----
T0=$(uptime_s)
T0_UTC=$(now_utc)
session_update "instants.first_drained_started_utc=$T0_UTC" "instants.first_drained_started_host_uptime_s=$T0"
hx "$A" pre "wait_ready $READY_LIMIT && drained && metrics $RID before && config_identity \"\$P/$RID.config_identity.json\""
pre_rc=$?
if [ "$pre_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" pre "the harness was NOT started"
elif [ "$pre_rc" -ne 0 ]; then
    not_run "precondition failed (ready/drained/metrics/identity: pre exit $pre_rc)"
fi
# The candidate on the guest must be the identified image: the configuration
# identity captured on the guest names its source commit, and a broker that
# reloaded its configuration is not the recorded one.
ex "$A" identity-check "$PY" -c '
import json, sys
path, expected = sys.argv[1], sys.argv[2]
doc = json.load(open(path, encoding="utf-8"))
commit = str(doc.get("controller_source_commit") or "")
reloaded = doc.get("broker_reloaded")
values = doc.get("broker_conf_values") if isinstance(doc.get("broker_conf_values"), dict) else {}
w = values.get("max_inflight_messages")
problems = []
if not (commit.startswith(expected) or expected.startswith(commit)) or len(commit) < 7:
    problems.append("controller_source_commit %r is not the expected %r" % (commit, expected))
if reloaded is not False:
    problems.append("broker_reloaded is %r, not false" % (reloaded,))
if not isinstance(w, int) or isinstance(w, bool) or w < 1:
    problems.append("broker_conf_values.max_inflight_messages (W) is %r, not a positive whole number" % (w,))
print("configuration identity: controller_source_commit=%s broker_reloaded=%s W=%s controller_image_id=%s stop_grace_period=%s paho=%s"
      % (commit, reloaded, w, doc.get("controller_image_id"), doc.get("stop_grace_period"), doc.get("paho_version")))
for p in problems:
    print("STOP: identity-check: " + p, file=sys.stderr)
sys.exit(1 if problems else 0)
' "$P/$RID.config_identity.json" "$EXPECTED_COMMIT"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" identity-check "the harness was NOT started"
[ "$rc" -eq 0 ] || not_run "the candidate on the guest is not the identified image (identity-check exit $rc: expected source commit $EXPECTED_COMMIT and broker_reloaded false)"
W=$(said identity-check '' | tr ' ' '\n' | sed -n 's/^W=//p' | head -n 1)
session_update "values.W=$W" "identity.controller_source_commit=$(said identity-check '' | tr ' ' '\n' | sed -n 's/^controller_source_commit=//p' | head -n 1)"

# --- post-window bookkeeping (nominal.sh) ----------------------------------------
# post_window NAME RC TEXT: a step AFTER the measured window the harness
# sealed. Its own failure leaves an observation incomplete and neither
# verdict of that window touched; only a lost console capture is an evidence
# failure of the attempt itself (mandatory).
post_window() {
    [ "$2" -eq 0 ] && return 0
    if [ "$2" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note "$1")")
    else
        incomplete+=("$3 (exit $2)")
    fi
    return 1
}
delta_faults() {
    [ -n "${1:-}" ] && [ -f "$1" ] || return 0
    sed -n 's/^FAULT: /; /p' "$1" | tr -d '\n'
}
delta_counts() {
    [ -n "${1:-}" ] && [ -f "$1" ] || return 0
    tail -n 1 "$1" \
        | sed -n 's/^guest-state-delta: faults=\([0-9][0-9]*\) problems=\([0-9][0-9]*\)$/\1 \2/p'
}

# --- proof_harness_args RUN_ID PLAN BASE SUT_ENV --------------------------------
# The FIXED arguments of the runbook's harness_cmd (6.1), verbatim, with the
# proof's own plan, results base and SUT environment capture in the place of
# the pilot's, into the array HARNESS_ARGS. It runs inside the host step,
# after the 6.1 preamble, where $MQTT_PORT, $CTRL, $MOSQUITTO_SIMULATOR_PASSWORD
# and EGW_CLONE are what the helper file and hx set; a test pins it to the
# runbook's function line by line. The proof's own hooks are appended by the
# step below, never here.
proof_harness_args() {
    # shellcheck disable=SC2034,SC2054  # used by the step's shell; the service list is one comma-separated argument
    HARNESS_ARGS=(--run-id "$1" --plan "$2" --base-dir "$3"
        --broker 127.0.0.1 --port "$MQTT_PORT" --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert ~/egw-tcg/ca.crt
        --controller-url "$CTRL" --sut-env-from "$4"
        --fetch-events-cmd 'scp egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl "{dest}"'
        --expect-services egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1
        --collector-start-cmd "ssh egw-tcg 'sudo systemd-run --unit egw-resources-{run_id} --collect sh /opt/egw/deployment/scripts/collect-resources.sh /tmp/resources-{run_id}.csv --duration {duration_s} --expect-services {expect_services}'"
        --collector-stop-cmd "ssh egw-tcg 'sudo systemctl stop egw-resources-{run_id}'"
        --collector-fetch-cmd "sh \"${EGW_CLONE:-$HOME/yocto/egw}/src/deployment/scripts/fetch-collector-output.sh\" egw-tcg /tmp/resources-{run_id}.csv \"{dest}\"")
}

# --- 10. the harness run, under the attempt's allowance ---------------------------
# 'timeout' bounds the step by what is left of the 50-minute rule (a spent
# allowance is never 'timeout 0', which would disable the bound); 124 (or 137,
# when the kill after the grace was needed) is the stop rule reached. The
# harness's exit 1 is read from the manifest afterwards: a run invalid under
# MAX_SAMPLE_GAP_S is expected and does not decide the proof.
HARNESS_STARTED=1
# The fault mutates the stack from here on: its state is unknown until the
# restoration reads it back.
STACK_STATE=unknown
LEFT=$(left)
HARNESS_STARTED_UTC=$(now_utc)
if [ "$LEFT" -le 0 ]; then
    stoprule attempt "stop rule reached: the attempt's allowance of ${ATTEMPT_LIMIT} s was spent before the harness could start"
    h_rc=124
    echo "STOP: no time left in the attempt's allowance: the harness was NOT started" >&2
else
    hx "$A" harness-run "$(declare -f proof_harness_args)
proof_harness_args '$RID' '$PLAN' '$BASE' '$ENVD/sut_environment.json'
timeout -k 30 $LEFT python -m egw_experiments run \"\${HARNESS_ARGS[@]}\" --restart-cmd 'bash $DRIVERS/proof_restart_controller.sh {run_id}' --restart-at-s $RESTART_AT --config-identity-from '$P/$RID.config_identity.json' --twin-snapshot-cmd 'bash $DRIVERS/proof_hook_twins.sh {run_id} {dest} $SEED' --drain-cmd 'bash $DRIVERS/proof_hook_drained.sh {run_id}' --post-drain-fetch-cmd 'scp -q egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl {dest}' --fetch-broker-log-cmd 'bash $DRIVERS/proof_fetch_sut_log.sh broker {dest} $GUEST_EPOCH' --fetch-controller-log-cmd 'bash $DRIVERS/proof_fetch_sut_log.sh controller {dest} $GUEST_EPOCH' --fetch-docker-events-cmd 'bash $DRIVERS/proof_fetch_sut_log.sh docker-events {dest} $GUEST_EPOCH'"
    h_rc=$?
fi
HARNESS_ENDED_UTC=$(now_utc)
session_update "instants.harness_started_utc=$HARNESS_STARTED_UTC" "instants.harness_ended_utc=$HARNESS_ENDED_UTC" "instants.harness_exit=$h_rc" "instants.harness_allowance_s=$LEFT"
case "$h_rc" in
    0 | 1) ;;
    124 | 137)
        stoprule attempt "stop rule reached: the attempt was stopped ${ATTEMPT_LIMIT} s after its first 'drained' started (the harness step was ended by 'timeout', exit $h_rc); the run directory, sealed or not, is preserved as incomplete"
        ;;
    "$EXIT_CAPTURE_LOST") mandatory+=("$(capture_note harness-run)") ;;
    *) missed "$(step_note harness-run "$h_rc" "the harness run exited $h_rc (2 is a refusal: usage, plan or identity)")" ;;
esac

# --- 11. the restart shown, from this driver's own records ---------------------------
# An issued command is not a restart: the controller PROCESS must be new
# (started_at differs) and the container OBJECT the same, started later (a
# kill + start keeps the object; a new id is a replacement, not the fault the
# proof issued). Not shown -> the fault was not applied: mandatory.
if [ "${#stoprules[@]}" -eq 0 ]; then
    hx "$A" controller-process-after "_mline"
    rc=$?
    STARTED_AFTER=""
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
        STARTED_AFTER=$(last_line controller-process-after | cut -d' ' -f5)
    elif [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note controller-process-after)")
    else
        missed "$(step_note controller-process-after "$rc" "the controller process could not be read after the run (_mline exit $rc)")"
    fi
    gx "$A" containers-after "$(containers_script)"
    rc=$?
    if [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note containers-after)")
    elif [ "$rc" -ne 0 ]; then
        missed "$(step_note containers-after "$rc" "the containers' ids and start instants were not recorded after the run (containers-after exit $rc)")"
    fi
    keep_record containers-after containers.after.txt "the containers after the run" || true
    ex "$A" restart-shown "$PY" -c '
import re, sys
before_started, after_started, before_file, after_file, name = sys.argv[1:6]

def container(path):
    for line in open(path, encoding="utf-8"):
        m = re.match(r"container (\S+) id=(\S+) started=(\S+)$", line.strip())
        if m and m.group(1) == name:
            return m.group(2), m.group(3)
    return None, None

def instant(text):
    m = re.fullmatch(r"(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", text or "")
    if not m:
        return None
    return (m.group(1), m.group(2), (m.group(3) or "").ljust(9, "0"))

old_id, old_started = container(before_file)
new_id, new_started = container(after_file)
print("controller process started_at: %s -> %s" % (before_started or "(not read)", after_started or "(not read)"))
print("%s: id %s -> %s, started %s -> %s" % (name, (old_id or "unknown")[:12], (new_id or "unknown")[:12], old_started, new_started))
unjudged = []
if not before_started or not after_started:
    unjudged.append("the controller process was not read on one side")
if old_id in (None, "unknown") or new_id in (None, "unknown") or instant(old_started) is None or instant(new_started) is None:
    unjudged.append("the container records do not name %s with a usable id and start instant on both sides" % name)
if unjudged:
    for what in unjudged:
        print("NOT JUDGED: " + what)
    sys.exit(2)
not_shown = []
if after_started == before_started:
    not_shown.append("the controller started_at did not change (%s): the process is the one that ran before the fault" % before_started)
if new_id != old_id:
    not_shown.append("the container id of %s changed (%s -> %s): the object was replaced, not killed and started" % (name, old_id[:12], new_id[:12]))
elif not instant(new_started) > instant(old_started):
    not_shown.append("%s did not start later than before the fault (%s, then %s)" % (name, old_started, new_started))
if not_shown:
    for what in not_shown:
        print("NOT SHOWN: " + what)
    sys.exit(1)
print("RESTART SHOWN: the controller process is new (%s, then %s) and its container is the same object (%s), started later (%s, then %s)"
      % (before_started, after_started, old_id[:12], old_started, new_started))
' "$STARTED_BEFORE" "$STARTED_AFTER" "$ENVD/containers.before.txt" "$ENVD/containers.after.txt" "$CONTROLLER"
    shown_rc=$?
    case "$shown_rc" in
        0) RESTART_SHOWN=yes ;;
        1)
            RESTART_SHOWN=no
            missed "the restart was not shown - the fault was not applied:$(said restart-shown 'NOT SHOWN:')"
            ;;
        "$EXIT_CAPTURE_LOST") mandatory+=("$(capture_note restart-shown)") ;;
        *) missed "the restart was not shown: it could not be judged from the records (restart-shown exit $shown_rc):$(said restart-shown 'NOT JUDGED:')" ;;
    esac
else
    incomplete+=("the restart-shown check, the /metrics reading after and the delta were not run: a stop rule was reached")
fi
set_field "restart_shown=$RESTART_SHOWN"
RESTART_SHOWN_JSON=null
[ "$RESTART_SHOWN" != yes ] || RESTART_SHOWN_JSON=true
[ "$RESTART_SHOWN" != no ] || RESTART_SHOWN_JSON=false
session_update "restart_shown=$RESTART_SHOWN_JSON" "restart_shown_detail=$(said restart-shown 'RESTART SHOWN: ')$(said restart-shown 'NOT SHOWN: ')$(said restart-shown 'NOT JUDGED: ')"

# --- 12. the /metrics reading after, and the runbook's delta on the post-drain copy ---
if [ "${#stoprules[@]}" -eq 0 ]; then
    hx "$A" metrics-after "metrics $RID after"
    post_window metrics-after $? "the /metrics reading after the run was not taken"
    # 'delta' compares the twins with the post-drain copy sealed in the run
    # directory (runbook test 6): 0 and 4 are both RESULTS (a named N1 case
    # gives 4 by exactly one; the evaluator applies S5's tolerance, design
    # flag P-9); anything else is no comparison.
    hx "$A" delta "\$REC delta '$RAWD' --prefix \"\$P/$RID\" --events '$RAWD/events.post-drain.jsonl'"
    delta_rc=$?
    if [ "$delta_rc" -ne 0 ] && [ "$delta_rc" -ne 4 ]; then
        post_window delta "$delta_rc" "the runbook's delta over the post-drain copy did not run" || true
    fi
fi

# --- 13. the prefix snapshots into the package -------------------------------------
# The ONLY path by which the configuration identity, the two /metrics
# readings, the two twin snapshots and the restart record reach the package
# under analysis/ (they are also registered as simulator siblings).
if mkdir -p "$SNAPS" && cp "$P/$RID".* "$SNAPS/"; then
    ls -l "$SNAPS/"
else
    missed "the prefix snapshots ($RID.*) were not copied into the package"
fi

# --- 14. the session facts so far, then the evaluator ---------------------------------
session_update "instants.delta_exit=$delta_rc" "restoration=$(guest_state_text)"
ex "$A" evaluate "$PY" -m egw_experiments.proof_evaluator --run-dir "$RAWD" --session "$FACTS" --out "$VERDICT"
v_rc=$?
case "$v_rc" in
    0) EVALUATOR_RESULT=supports ;;
    1) EVALUATOR_RESULT=refutes ;;
    3) EVALUATOR_RESULT=inconclusive ;;
    "$EXIT_CAPTURE_LOST")
        EVALUATOR_RESULT=not-computed
        mandatory+=("$(capture_note evaluate)")
        ;;
    *)
        EVALUATOR_RESULT=not-computed
        missed "the proof was not evaluated (evaluate exit $v_rc): $(sed -n 's/^error: //p' "$(ls "$A"/console/*-evaluate.stderr.txt 2> /dev/null | tail -n 1)" 2> /dev/null | tr '\n' ' ')"
        ;;
esac
set_field "proof_verdict=$EVALUATOR_RESULT"
# What the verdict document says: whether the proof's evidence is complete
# (the attempt's validity rests on it), the harness's own validity quoted as
# recorded, and the criteria that failed, the refutations and the inconclusive
# reasons for the reason text. A document that cannot be read leaves the
# evidence NOT complete.
V=$("$PY" - "$VERDICT" 2> /dev/null <<'PYEOF' || echo "false|the verdict document analysis/proof_verdict.json could not be read|"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
inst = d.get("instrumentation") or {}
ev = inst.get("proof_evidence") or {}
complete = ev.get("complete") is True
reasons = inst.get("harness_validity_reasons") or []
harness = "manifest validity %s%s kept as recorded, not decisive for the proof (ADR 0011)" % (
    inst.get("harness_validity"), (" (" + "; ".join(str(r) for r in reasons) + ")") if reasons else "")
out = d.get("system_outcome") or {}
crit = out.get("criteria") or {}
failing = [k for k, c in sorted(crit.items()) if isinstance(c, dict)
           and (c.get("holds") is False or c.get("observed") is True)]
unshown = [k for k, c in sorted(crit.items()) if isinstance(c, dict)
           and k.startswith("S") and c.get("holds") is None]
parts = ["the proof's evaluator: %s" % out.get("result")]
if failing:
    parts.append("criteria not held or observed: " + ", ".join(failing))
if unshown:
    parts.append("criteria that cannot be shown: " + ", ".join(unshown))
if out.get("refutations"):
    parts.append("refutations: " + " | ".join(str(r) for r in out["refutations"]))
if out.get("inconclusive_reasons"):
    parts.append("inconclusive: " + " | ".join(str(r) for r in out["inconclusive_reasons"]))
if not complete:
    parts.append("proof evidence incomplete: missing %s; fetch failures %s" % (
        ", ".join(ev.get("missing") or []) or "none", ", ".join(ev.get("fetch_failures") or []) or "none"))
print(("true" if complete else "false") + "|" + harness + "|" + "; ".join(parts))
PYEOF
)
EVIDENCE_COMPLETE=${V%%|*}
rest=${V#*|}
HARNESS_NOTE=${rest%%|*}
PROOF_NOTE=${rest#*|}
[ -n "$PROOF_NOTE" ] || PROOF_NOTE="the proof's evaluator: $EVALUATOR_RESULT (evaluate exit $v_rc)"

# --- 15. the guest state after, against the state before (nominal.sh) ---------------
gx "$A" guest-state-after "$GUEST_STATE"
after_rc=$?
after_trusted=1
[ "$after_rc" -eq "$EXIT_CAPTURE_LOST" ] && after_trusted=0
[ "$after_rc" -eq 0 ] || mandatory+=("$(step_note guest-state-after "$after_rc" "the guest state after the run was not recorded")")
AFTER=$(ls "$A"/console/*-guest-state-after.stdout.txt 2> /dev/null | tail -n 1)
if [ -n "$AFTER" ]; then
    # The controller's one in-place restart is the fault this proof issued:
    # named as expected, it is not a fault; an OOM kill, a replacement, a
    # restart count that moved or any other container's restart stays one,
    # and an expected restart the pair does not show is a problem (exit 2).
    ex "$A" guest-state-delta "$PY" "$DRIVERS/guest_state_delta.py" --expect "$EXPECT_SERVICES" --expect-restarted "$CONTROLLER" "$BEFORE" "$AFTER"
    gsd_rc=$?
    DELTA_OUT=$(ls "$A"/console/*-guest-state-delta.stdout.txt 2> /dev/null | tail -n 1)
    seen_faults=$(delta_faults "$DELTA_OUT")
    counts=$(delta_counts "$DELTA_OUT")
    delta_seen=0
    delta_trusted=0
    if [ -n "$counts" ]; then
        delta_seen=${counts%% *}
        delta_problems=${counts##* }
        case "$gsd_rc" in
            0) [ "$delta_seen" -eq 0 ] && [ "$delta_problems" -eq 0 ] && delta_trusted=1 ;;
            1) [ "$delta_seen" -gt 0 ] && [ "$delta_problems" -eq 0 ] && delta_trusted=1 ;;
            2) [ "$delta_problems" -gt 0 ] && delta_trusted=1 ;;
        esac
    fi
    if [ "$gsd_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note guest-state-delta)")
    elif [ "$delta_trusted" -eq 0 ]; then
        missed "the two guest states could not be compared (guest-state-delta exit $gsd_rc: the comparison itself failed, printing no 'guest-state-delta: faults=N problems=M' line that agrees with that status)"
    else
        [ "$gsd_rc" -le 1 ] \
            || missed "the two guest states could not be compared, or the expected restart of $CONTROLLER is not shown by the pair (guest-state-delta exit $gsd_rc)"
        if [ "$delta_seen" -gt 0 ] && [ "$after_trusted" -eq 1 ]; then
            observed+=("a container was OOM-killed, replaced or gone, or a container other than the controller restarted during the run (guest-state-delta exit $gsd_rc; see console/)$seen_faults")
            first_note "the guest state shows a fault beside the proof's own restart$seen_faults"
        elif [ "$delta_seen" -gt 0 ]; then
            missed "the comparison read the guest state after the run out of a record the driver already knows is incomplete (the console capture of that step failed), so what it reports about the containers was not established:$seen_faults"
        fi
    fi
else
    missed "the record of the guest state after the run was not kept"
fi

# --- 16. the restoration: the stack running and healthy again ------------------------
restore

# --- 17. the optional extension (ADR 0011 item 4 section 9), only when asked ------------
# One more kill + start under the same client id and persistent session, then
# 'wait_ready', one /metrics reading and 'drained' with nothing published, and a
# second post-drain fetch. It changes the proof's plan, so it is the student's
# decision (EGW_PROOF_EXTENSION=yes); its result is recorded APART, in
# proof_session.json.extension and on the attempt, and never changes the
# proof's three verdicts. Refutes the assumption if the new process received
# anything (received > 0) or an identity gained its first outcome line after
# the first quiet window; inconclusive if the restart is not shown, /ready is
# not reached, 'drained' reaches its limit, a fetch fails or its own ceiling
# (EGW_PROOF_EXTENSION_LIMIT_S) is reached.
if [ "$EXTENSION" = yes ] && [ "${#stoprules[@]}" -eq 0 ] && [ "$STACK_STATE" = healthy ] && [ -s "$RAWD/events.post-drain.jsonl" ]; then
    EXTENSION_RESULT=inconclusive
    ext_reasons=()
    EXT_T0=$(uptime_s)
    ext_left() {
        local rest
        rest=$((EXTENSION_LIMIT - ($(uptime_s) - EXT_T0)))
        [ "$rest" -gt 0 ] || rest=0
        printf '%s' "$rest"
    }
    ext_spent() {
        [ "$(ext_left)" -gt 0 ] && return 1
        ext_reasons+=("the extension's ceiling of ${EXTENSION_LIMIT} s was reached before '$1'")
        return 0
    }
    session_update "extension.chosen=true" "extension.started_utc=$(now_utc)" "extension.limit_s=$EXTENSION_LIMIT" "extension.result=$EXTENSION_RESULT"
    ext_ok=1
    rc=124
    if ext_spent ext-restart; then
        ext_ok=0
    else
        hx "$A" ext-restart "timeout -k 15 $(ext_left) bash '$DRIVERS/proof_restart_controller.sh' '$RID.extension'"
        rc=$?
    fi
    if [ "$ext_ok" -eq 0 ]; then
        :
    elif [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        ext_ok=0
        ext_reasons+=("the extension's ceiling was reached during the second kill + start (exit $rc)")
    elif [ "$rc" -ne 0 ]; then
        ext_ok=0
        ext_reasons+=("the second kill + start was not issued cleanly (ext-restart exit $rc)")
    fi
    if [ "$ext_ok" -eq 1 ] && ! ext_spent ext-ready; then
        hx "$A" ext-ready "wait_ready $READY_LIMIT && _mline"
        rc=$?
        if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
            EXT_LINE=$(last_line ext-ready)
            EXT_STARTED=$(printf '%s' "$EXT_LINE" | cut -d' ' -f5)
            EXT_RECEIVED=$(printf '%s' "$EXT_LINE" | cut -d' ' -f7)
            if [ -z "$EXT_STARTED" ] || [ "$EXT_STARTED" = "${STARTED_AFTER:-}" ]; then
                ext_ok=0
                ext_reasons+=("the extension's restart is not shown (started_at '$EXT_STARTED' after, '${STARTED_AFTER:-}' before it)")
            fi
            session_update "extension.started_at_after=$EXT_STARTED" "extension.received_after_ready=${EXT_RECEIVED:-null}"
        else
            ext_ok=0
            ext_reasons+=("/ready was not reached, or the controller process was not read, after the second kill + start (ext-ready exit $rc)")
        fi
    fi
    if [ "$ext_ok" -eq 1 ] && ! ext_spent ext-drained; then
        hx "$A" ext-drained "drained"
        rc=$?
        [ "$rc" -eq 0 ] || { ext_ok=0; ext_reasons+=("the extension's 'drained' did not report a quiet window (ext-drained exit $rc)"); }
    fi
    if [ "$ext_ok" -eq 1 ] && ! ext_spent ext-fetch; then
        hx "$A" ext-fetch "scp -q 'egw-tcg:/opt/egw/deployment/data/events/$RID/events.jsonl' '$ANALYSIS/events.post-extension.jsonl' && wc -l '$ANALYSIS/events.post-extension.jsonl'"
        rc=$?
        [ "$rc" -eq 0 ] && [ -s "$ANALYSIS/events.post-extension.jsonl" ] \
            || { ext_ok=0; ext_reasons+=("the post-extension copy of the events was not fetched (ext-fetch exit $rc)"); }
    fi
    if [ "$ext_ok" -eq 1 ]; then
        EXT_NEW=$("$PY" - "$RAWD/events.post-drain.jsonl" "$ANALYSIS/events.post-extension.jsonl" "$RID" 2> /dev/null <<'PYEOF' || echo unreadable
import json, sys
def ids(path):
    out = set()
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("run_id") == sys.argv[3] and isinstance(r.get("message_id"), str):
            out.add(r["message_id"])
    return out
print(len(ids(sys.argv[2]) - ids(sys.argv[1])))
PYEOF
)
        case "$EXT_NEW$EXT_RECEIVED" in
            *[!0-9]*)
                ext_reasons+=("the extension's readings could not be compared (new outcome lines '$EXT_NEW', received '$EXT_RECEIVED')")
                ;;
            *)
                if [ "$EXT_RECEIVED" -gt 0 ] || [ "$EXT_NEW" -gt 0 ]; then
                    EXTENSION_RESULT=refutes
                    ext_reasons+=("the new process received $EXT_RECEIVED delivery(ies) with nothing published, and $EXT_NEW identity(ies) gained a first outcome line after the first quiet window")
                else
                    EXTENSION_RESULT=not-refuted
                    ext_reasons+=("the new process received nothing and no identity gained a first outcome line after the first quiet window")
                fi
                ;;
        esac
        session_update "extension.new_outcome_lines=${EXT_NEW}"
    fi
    session_update "extension.result=$EXTENSION_RESULT" "extension.ended_utc=$(now_utc)" "extension.reasons=$(printf '%s; ' "${ext_reasons[@]}")"
    # The stack must be running and healthy again after the second restart too.
    RESTORED=0
    STACK_STATE=unknown
    restore
fi
set_field "extension=$EXTENSION_RESULT"

# --- 18. the three verdicts, never merged ----------------------------------------------
# Instrumentation validity: no mandatory record missing AND the proof's
# evidence complete (P-8: the harness's own validity is quoted, not decisive).
validity=valid
[ "$EVIDENCE_COMPLETE" = true ] || missed "the proof's evidence is not complete (analysis/proof_verdict.json instrumentation.proof_evidence.complete is not true)"
# System outcome: the evaluator's result, and beside it any fault the guest
# state showed.
case "$EVALUATOR_RESULT" in
    supports) outcome=pass ;;
    refutes) outcome=fail ;;
    *) outcome=inconclusive ;;
esac
status=finished
case "$h_rc" in 0 | 1) ;; *) status=failed ;; esac
if [ "${#observed[@]}" -ne 0 ]; then
    outcome=fail
    status=failed
elif [ "${#incomplete[@]}" -ne 0 ] && [ "$outcome" = pass ]; then
    outcome=inconclusive
fi
if [ "${#stoprules[@]}" -ne 0 ] && [ "$outcome" = pass ]; then
    outcome=inconclusive
fi
if [ "${#mandatory[@]}" -ne 0 ]; then
    status=failed
    validity=invalid
    [ "$outcome" != pass ] || outcome=inconclusive
fi
# Restoration outcome: a pass is never reported when the guest is not restored.
restored_note=""
if [ "$STACK_STATE" != healthy ]; then
    [ "$outcome" != pass ] || outcome=inconclusive
    restored_note="; the guest was NOT fully restored${RESTORE_NOTE:+: $RESTORE_NOTE}"
fi
reason=""
[ "${#observed[@]}" -eq 0 ] || reason="observed system fault(s): $(printf '%s; ' "${observed[@]}")"
[ "${#mandatory[@]}" -eq 0 ] || reason="${reason}evidence requirement(s) not met: $(printf '%s; ' "${mandatory[@]}")"
if [ "${#incomplete[@]}" -ne 0 ]; then
    reason="${reason}post-window observation(s) incomplete: $(printf '%s; ' "${incomplete[@]}")"
    set_field "post_window_observations=incomplete: $(printf '%s; ' "${incomplete[@]}")"
fi
[ "${#stoprules[@]}" -eq 0 ] || reason="${reason}stop rule(s) reached: $(printf '%s; ' "${stoprules[@]}")"
reason="${reason}${PROOF_NOTE} (evaluate exit $v_rc); ${HARNESS_NOTE} (harness exit $h_rc; restart shown: $RESTART_SHOWN; delta exit $delta_rc)"
[ "$EXTENSION_RESULT" = not-chosen ] || reason="${reason}; optional extension: $EXTENSION_RESULT (recorded apart, it decides nothing of the proof)"
reason="${reason}${restored_note}; the guest was left with $(guest_state_text)"
case "$EVALUATOR_RESULT" in
    supports) next="the result stands for this run only: one run supports the property for that run and does not prove it in general; the candidate freeze and any resumption of G3 runs are separate decisions" ;;
    refutes) next="a refutation is a result: record it, never re-run it away; the option is re-decided by the student (option 4 next best, never automatic)" ;;
    inconclusive) next="an inconclusive run is not passing: the student decides whether to repeat it with the same design (recorded as a repeat, this run kept) or to re-decide the option" ;;
    *) next="read console/ and analysis/; the records are kept as they are, and the student decides whether to repeat (recorded as a repeat, this run kept) or to re-decide the option" ;;
esac
[ -n "$FIRST" ] || FIRST="$PROOF_NOTE"
headline "$A" "$FIRST" || true
set_field "restoration=$(guest_state_text)"
session_update "restoration=$(guest_state_text)" "instants.ended_utc=$(now_utc)" "verdicts.instrumentation_validity=$validity" "verdicts.system_outcome=$outcome" "verdicts.evaluator=$EVALUATOR_RESULT"
(cd "$REPO/src" && $LE finish --attempt "$A" --status "$status" --validity "$validity" --outcome "$outcome" \
    --reason "$reason" --next-action "$next")
echo "PROOF $RID: validity=$validity outcome=$outcome evaluator=$EVALUATOR_RESULT (exit $v_rc) harness_exit=$h_rc restart_shown=$RESTART_SHOWN $(guest_state_text) observed=${#observed[@]} mandatory=${#mandatory[@]} incomplete=${#incomplete[@]} stop_rules=${#stoprules[@]} extension=$EXTENSION_RESULT"
driver_exit "$A"
