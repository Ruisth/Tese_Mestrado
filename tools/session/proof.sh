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
# WHAT IT DOES. After the prerequisites, the 'ready' step (the /ready wait,
# before the attempt's clock starts) and 'pre' (drained, the /metrics reading
# and the configuration identity captured on the guest), it
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
# on the post-drain copy, packages the prefix snapshots, records the guest's
# container state after the run against the state before it, waits for the
# stack to be running and healthy again, which is the restoration, writes
# the session facts (proof_session.py) with the restoration observed, and
# only then evaluates the run with the proof's evaluator
# (egw_experiments.proof_evaluator: S1-S6, R1-R4 and the inconclusive rule,
# by identity), so that the write-once verdict document echoes the
# restoration the driver observed and not a state not yet read.
#
# THREE VERDICTS, NEVER MERGED.
#   instrumentation validity  'valid' only when every mandatory record was
#     made AND the proof's evidence is complete (the evaluator's
#     instrumentation.proof_evidence.complete: both twin snapshots, a verified
#     drain, the post-drain copy, the three SUT logs, the configuration
#     identity, a readable pre-kill reading, the seal). The harness's OWN
#     validity is quoted verbatim in the reason and kept as recorded, and it
#     is admitted for the proof only as E-12 states, through the one
#     function the evaluator applies too
#     (egw_experiments.proof_evaluator.harness_admission): 'valid', or the
#     campaign's MAX_SAMPLE_GAP_S deviation in the one form the harness
#     records it (its ingest rejected the collector file, which it keeps at
#     logs/collector/resources-RUN_ID.csv; ADR 0011, "What the proof cannot
#     show": that verdict "belongs to the campaign rules and is kept as
#     recorded"). Any other invalidity is not admitted (P-16; the blanket
#     reading of design flag P-8, the harness validity never decisive, was
#     not confirmed and is withdrawn).
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
# EGW_HEALTH_LIMIT_S (1200 s, the 20-minute rule) OF ITS START - the
# candidate's start is the earliest StartedAt of the six expected services,
# read from the containers before the wait; the wait (the shared
# healthy_wait_script, on the same records as the broker measurement) is
# bounded by what is left of that allowance from that start, on the guest
# and, for its acquisition as a whole, on the host ('bounded': an
# inspection that blocks is ended there), so time already spent counts and
# a late poll never resets it; the first healthy observation is judged by
# when it COMPLETED - the instant the wait reads after the healthy sample's
# last inspection, never the sample's start - and one completed past start
# + EGW_HEALTH_LIMIT_S is not accepted; a healthy transition of this same
# start demonstrated earlier in the session may be named
# (EGW_PROOF_HEALTHY_RECORD, P-15) and is reused only when it began after
# the latest start of the six and completed by start + EGW_HEALTH_LIMIT_S
# (a record that does not say when it completed proves nothing); an
# unknown start - docker's zero StartedAt of a container created but never
# started among them - cannot establish the rule (not-run, stated). The
# rule REACHED - the allowance from that start spent before the wait, the
# stack not healthy within its remainder (or the acquisition ended by it),
# a first healthy observation completed past start + EGW_HEALTH_LIMIT_S,
# or a named earlier transition completed past it - ends the attempt
# inconclusive (exit 3), never not-run, and the harness is not started.
# The attempt stopped EGW_PROOF_ATTEMPT_LIMIT_S (3000 s, the
# 50-minute rule) after its first 'drained' starts, measured on
# /proc/uptime (the host's wall clock is stepped backwards on this host)
# from the instant taken immediately before 'pre', and enforced as ONE
# monotonic deadline on 'pre'
# itself and on every live proof step after it (tunnel-ready, harness-run,
# the controller process and the containers after, metrics-after, delta,
# the guest state after): the remainder is checked before each is
# dispatched, each runs under 'timeout' of the positive remainder (a spent
# allowance means the step is not started, never 'timeout 0'; the live
# host steps load the 6.1 preamble inside that bound; 'tunnel-ready', just
# before the harness, is such a step with a trivial body; the harness step
# loads its own preamble - the one that actually precedes the harness -
# inside the same bound too, so a tunnel that drops after 'tunnel-ready'
# and whose reopening blocks is ended by the allowance and the harness is
# never started; the harness step is also handed the absolute deadline, so
# the harness's own bound is computed AFTER that preamble and the harness is
# not started when nothing is left then), and the expiry is recorded once -
# in the driver's own shell, never
# in a subshell - with its instant and the step, whether it fell before,
# during or after a step. After it no further proof or fault step starts
# (the optional extension included); the partial records and the stop
# reason are kept; the restoration and the shutdown still run and are never
# force-killed; the two comparisons of records already taken
# (restart-shown, the guest-state delta) still run when their input records
# were taken whole, and are not run when the rule kept an input from being
# taken; the packaging, the hashing and the evaluation may finish
# afterwards but acquire no new live observation and never hide that the
# rule was reached (the outcome is inconclusive with the rule named,
# whenever it is reached: before 'pre' is dispatched, during it or after
# it). If a stop rule is reached the session stops and the proof is
# recorded inconclusive (ADR 0011: "If a stop rule is reached, the session
# stops and the proof is recorded inconclusive"), the 20-minute rule and the
# 50-minute rule alike; only a prerequisite that is not a stop rule leaves
# the attempt not-run, and only before the 50-minute rule is reached: one
# that fails after it (say 'pre' ended at the deadline, then the identity
# check failed) is recorded inconclusive with the rule named beside it.
# The restoration is never cut short to keep a total duration. The values
# used are recorded before anything starts - on the
# attempt (workload.values) and in analysis/proof_session.json - and the
# student may set other values before the session.
#
# ELIGIBILITY (P-16). The harness's validity is admitted only as E-12
# states, read by the function the evaluator applies to the same run
# directory (egw_experiments.proof_evaluator.harness_admission), so the two
# parts cannot disagree on it: 'valid', or the campaign's MAX_SAMPLE_GAP_S
# deviation in the one form the harness records it. After the harness step
# the manifest is read ('eligibility'): a simulator that did not exit 0
# (the prescribed publication did not complete), a missing or failed
# harness copy of the events (the first of the two copies the ADR keeps
# apart), a missing collector file (resources.csv, or in the sampling-gap
# form the file the ingest rejected, where the admission names it), a
# missing or failed post-drain copy, twin snapshot, SUT-log fetch or fault
# record, or a harness validity not admitted (or whose admission cannot be
# read), is the proof's evidence or execution incomplete: mandatory, the
# attempt invalid, never a pass. The reading, the admission's form and
# reasons with it, is written into the session facts (eligibility,
# harness_exit) before the evaluator runs.
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
#   EGW_HEALTH_LIMIT_S (1200) EGW_HEALTH_STEP_S (15) EGW_READY_LIMIT_S (300:
#   the driver's own choice; the ADR gives no /ready figure and the runbook's
#   wait_ready defaults to 60 s) EGW_PROOF_ATTEMPT_LIMIT_S (3000)
#   EGW_PROOF_RESTART_AT_S (150, the ADR's 't+150 s', which the evaluator
#   requires of the run (E-11): any other value stops the driver before
#   anything starts, as a load that differs from the plan does; it must
#   also lie strictly between 0 and the duration, or the fault would never
#   fire: the harness cancels its restart timer when the measured run ends)
#   EGW_PROOF_DURATION_S (300) EGW_PROOF_RATE (11.2) - the load is fixed by
#   proof_plan.py; a different value stops the driver, it never changes it
#   EGW_PROOF_MASTER_SEED (no default: the student's decision)
#   EGW_PROOF_HEALTHY_RECORD (no default: the path of a console record of
#   the shared healthy wait made earlier in this session - gate_health.sh's
#   'services-healthy' - whose ALL HEALTHY transition is reused for the
#   20-minute rule when it is of this same start and completed within the
#   allowance, P-15; unreadable, not of this start, or a record that does
#   not say when its healthy sample completed (one made before the wait
#   recorded that), it is refused: nothing is guessed)
#   EGW_PROOF_EXTENSION (no; 'yes' runs the optional extension)
#   EGW_PROOF_EXTENSION_LIMIT_S (1790: the 130 s stop_grace_period recorded
#   under C6 plus 1,660 s, ADR 0011; inside it the extension's restart
#   command is bounded by the stop_grace_period the configuration identity
#   reports plus 300 s and its second fetch by 300 s, the ADR's two per-step
#   stop rules)
#   EGW_PROOF_BASE (~/egw-tcg/proof/results) EGW_PROOF_PLAN
#   (~/egw-tcg/proof/plan-RUN_ID.json) - neither may lie under
#   ~/egw-tcg/pilot/, where this driver never writes - EGW_PROOF_RUNBOOK (the
#   clone's docs/setup/qemu_integrated_gateway.md, whose 6.1 heredoc the
#   deployed helper file must equal)
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
# Every whole number is written into the record as a JSON number and read by
# the shell's arithmetic: a leading zero is neither ('0600' is octal to
# '$((...))' and not a JSON number), so it is refused, as is a rate that is
# not one plain decimal number.
for pair in "EGW_HEALTH_LIMIT_S=$LIMIT" "EGW_HEALTH_STEP_S=$STEP" "EGW_READY_LIMIT_S=$READY_LIMIT" \
    "EGW_PROOF_ATTEMPT_LIMIT_S=$ATTEMPT_LIMIT" "EGW_PROOF_RESTART_AT_S=$RESTART_AT" "EGW_PROOF_DURATION_S=$DURATION" \
    "EGW_PROOF_EXTENSION_LIMIT_S=$EXTENSION_LIMIT" "DRAIN_QUIET_S=$DRAIN_QUIET_S" "DRAIN_STEP_S=$DRAIN_STEP_S" "DRAIN_LIMIT_S=$DRAIN_LIMIT_S"; do
    [[ ${pair#*=} =~ ^(0|[1-9][0-9]*)$ ]] \
        || driver_stop "$EXIT_PREREQUISITE" "${pair%%=*}='${pair#*=}' is not a plain whole number of seconds (no leading zero); nothing was started"
done
# The fault must fall inside the measured window: the harness cancels its
# restart timer when the measured run ends, so an instant at or beyond the
# duration would never fire (and 0 is no instant into the run at all). The
# driver would learn it only from the restart not shown, after the whole
# run, so it is refused here, before anything starts.
[ "$RESTART_AT" -gt 0 ] && [ "$RESTART_AT" -lt "$DURATION" ] \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_RESTART_AT_S=$RESTART_AT is not strictly between 0 and EGW_PROOF_DURATION_S=$DURATION (the harness cancels its restart timer when the measured run ends, so the fault would never fire); nothing was started"
# The fault instant is the ADR's ("fault | at t+150 s"), and the evaluator
# requires it of the run it reads (E-11: the manifest's restart.requested_at_s
# must be egw_experiments.proof_evaluator.PROOF_RESTART_AT_S, 150; a test pins
# the two equal): a run with the fault at any other instant can never support
# the proof, so a session is never started for one. The driver changes no
# fault instant, as it changes no load (P-13).
PROOF_RESTART_AT_S=150
[ "$RESTART_AT" -eq "$PROOF_RESTART_AT_S" ] \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_RESTART_AT_S=$RESTART_AT is not the ADR's fault instant of $PROOF_RESTART_AT_S s ('fault | at t+$PROOF_RESTART_AT_S s'), which the evaluator requires of the run (E-11: restart.requested_at_s must be $PROOF_RESTART_AT_S), so the run could never support the proof; the driver changes no fault instant; nothing was started"
RATE=${EGW_PROOF_RATE:-11.2}
[[ $RATE =~ ^(0|[1-9][0-9]*)(\.[0-9]+)?$ ]] \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_RATE='$RATE' is not a number; nothing was started"
MASTER_SEED=${EGW_PROOF_MASTER_SEED:-}
[[ $MASTER_SEED =~ ^(0|[1-9][0-9]*)$ ]] \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_MASTER_SEED='$MASTER_SEED' is not a whole number (the master seed is the student's decision, and it has no default); nothing was started"
EXTENSION=${EGW_PROOF_EXTENSION:-no}
case "$EXTENSION" in
    yes | no) ;;
    *) driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_EXTENSION='$EXTENSION' is neither 'yes' nor 'no'; nothing was started" ;;
esac
# An earlier healthy transition of this session, named by the student (P-15):
# a file that cannot be read is refused before anything starts, and whether
# it is of this same start is judged against the containers' start instants
# by the healthy-rule step (never assumed).
HEALTHY_RECORD=${EGW_PROOF_HEALTHY_RECORD:-}
if [ -n "$HEALTHY_RECORD" ]; then
    [ -f "$HEALTHY_RECORD" ] && [ -r "$HEALTHY_RECORD" ] \
        || driver_stop "$EXIT_PREREQUISITE" "EGW_PROOF_HEALTHY_RECORD='$HEALTHY_RECORD' is not a readable file (the console record of an earlier healthy wait of this session); nothing was started"
fi
BASE=${EGW_PROOF_BASE:-$HOME/egw-tcg/proof/results}
PLAN=${EGW_PROOF_PLAN:-$HOME/egw-tcg/proof/plan-$RID.json}
RUNBOOK=${EGW_PROOF_RUNBOOK:-$REPO/docs/setup/qemu_integrated_gateway.md}
PILOT_DIR=$HOME/egw-tcg/pilot
PILOT_PLAN=$PILOT_DIR/campaign_plan.json
# This driver never writes under ~/egw-tcg/pilot/ (the pilot plan is read
# only to refuse a run id it holds): a results base or a plan that lies
# there, as given or as it resolves ('..', a symbolic link), is refused
# before anything starts.
under_pilot() {
    local given=$1 canon pilot
    canon=$(realpath -m -- "$given" 2> /dev/null) || canon=$given
    pilot=$(realpath -m -- "$PILOT_DIR" 2> /dev/null) || pilot=$PILOT_DIR
    case "$given" in "$PILOT_DIR" | "$PILOT_DIR/"*) return 0 ;; esac
    case "$canon" in "$pilot" | "$pilot/"*) return 0 ;; esac
    return 1
}
for pair in "EGW_PROOF_BASE=$BASE" "EGW_PROOF_PLAN=$PLAN"; do
    ! under_pilot "${pair#*=}" \
        || driver_stop "$EXIT_PREREQUISITE" "${pair%%=*}='${pair#*=}' lies under $PILOT_DIR/, where this driver never writes; nothing was started"
done
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
# The hook templates handed to the harness are split without a shell
# (shlex.split), so the hook paths and "{dest}" are double-quoted in them
# as the runbook's harness_cmd quotes its own: the drivers' path and the
# results base (every "{dest}" the harness renders lies under it) must then
# hold no double quote or backslash, which that splitting would consume.
for quoted in "drivers' path=$DRIVERS" "results base=$BASE"; do
    case "${quoted#*=}" in
        *[\"\\]*) driver_stop "$EXIT_PREREQUISITE" "the ${quoted%%=*} '${quoted#*=}' holds a double quote or a backslash and cannot be written double-quoted into the harness's hook templates; nothing was started" ;;
    esac
done
# json_text VALUE: VALUE as a JSON string literal (quotes and backslashes
# escaped); non-zero for a control character, which the record could not
# hold as the text it is.
json_text() {
    local v=$1
    case "$v" in *[[:cntrl:]]*) return 1 ;; esac
    v=${v//\\/\\\\}
    v=${v//\"/\\\"}
    printf '"%s"' "$v"
}
# The texts the record of the values holds, checked ONCE likewise: a path
# the record cannot hold as it is would leave the values unrecorded.
for value in "$BASE" "$PLAN" "$RUNBOOK" "$HEALTHY_RECORD" "$(basename "$SESSION")"; do
    json_text "$value" > /dev/null \
        || driver_stop "$EXIT_PREREQUISITE" "'$value' cannot be written into the record of the values as the text it is (a control character); nothing was started"
done
HEALTHY_RECORD_JSON=null
[ -z "$HEALTHY_RECORD" ] || HEALTHY_RECORD_JSON=$(json_text "$HEALTHY_RECORD")

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
STARTED_AFTER=""         # the controller's started_at read after the run: the extension's baseline
HARNESS_STARTED=0        # once the harness block is entered (tunnel-ready, then the harness step) the outcome is never 'not-run'
RESTORED=0               # the restoration wait was run
RESTORE_NOTE=""          # what the restoration found when the stack did not come back
EXT_RESTORE=0            # the restoration being waited for is the extension's own (recorded apart)
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
# record_file NAME: the path of NAME's console record (its stdout), or
# non-zero with nothing printed when the step left none.
record_file() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    [ -n "$f" ] && [ -f "$f" ] || return 1
    printf '%s' "$f"
}
# said NAME PREFIX: the lines of NAME's console record that start with PREFIX,
# without it, on one line (broker_measure.sh).
said() {
    local f
    f=$(record_file "$1") || return 0
    sed -n "s/^$2//p" "$f" | tr '\n' ' '
}
# last_line NAME: the last line of NAME's console record (one /metrics reading
# of _mline is the last line the step printed), or nothing.
last_line() {
    local f
    f=$(record_file "$1") || return 0
    tail -n 1 "$f"
}
# keep_record NAME FILE WHAT: the console record of NAME kept as environment/FILE.
keep_record() {
    local f
    if f=$(record_file "$1") && cp "$f" "$ENVD/$2"; then
        return 0
    fi
    missed "$3 was not kept in environment/$2"
    return 1
}
# bounded LIMIT CMD...: CMD under 'timeout -k 30 LIMIT', run so that an
# interrupt of the driver reaches it. 'timeout' moves itself and CMD into a
# process group of their own (so that a limit reached ends CMD's whole tree),
# which the terminal's Ctrl-C - sent to the driver's group - never reaches:
# the step's shell therefore keeps them as a job, forwards INT and TERM to
# 'timeout' (which passes them on to CMD and to that group) and answers with
# CMD's own status once it has ended. Its text is written into a host step
# with 'declare -f', as proof_harness_args is; LIMIT is never 0, which
# would disable the bound instead of enforcing it.
bounded() {
    local limit=$1 pid rc
    shift
    [ "$limit" -gt 0 ] 2> /dev/null || limit=1
    timeout -k 30 "$limit" "$@" &
    pid=$!
    trap 'kill -INT "$pid" 2> /dev/null' INT
    trap 'kill -TERM "$pid" 2> /dev/null' TERM
    wait "$pid"
    rc=$?
    # A trapped signal returns 'wait' at once, above 128: wait again until the
    # job has really ended, then answer with its status.
    while [ "$rc" -gt 128 ] && kill -0 "$pid" 2> /dev/null; do
        wait "$pid"
        rc=$?
    done
    trap - INT TERM
    return "$rc"
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

# --- the attempt's allowance as ONE monotonic deadline (F2, P-10) --------------
# Every live proof step after the first 'drained' - 'pre' itself, the 6.1
# preamble loaded just before the harness (tunnel-ready), the harness run,
# the controller process and the containers after, the /metrics reading
# after, the delta, the guest state after - is dispatched
# only while something of the allowance is left, runs under 'timeout' of
# the positive remainder (a spent allowance means the step is not started:
# never 'timeout 0', which would disable the bound), and the expiry is
# recorded ONCE with its instant and the step it fell before, during or
# after. A live step that was not started answers STEP_NOT_STARTED, a
# status of this driver's own (no command answers it: local_export's 74 and
# the wrappers' 97 are the others; the harness step answers it too when
# the allowance is found spent after its preamble), and is listed among the
# observations not made. The restoration (restore), the shutdown and the
# offline work (the eligibility reading, the two comparisons of records
# already taken - restart-shown and the guest-state delta - the snapshots
# copied, the evaluator) never run under this bound; a comparison is not
# run when the rule kept one of its input records from being taken whole
# (cut_by_rule), and is then listed with the observations not made.
STEP_NOT_STARTED=98
ATTEMPT_REACHED=0        # the 50-minute rule recorded (once)
ATTEMPT_TEXT=""          # ... and the reason text it was recorded with
not_started=()           # live steps not dispatched after the rule was reached
# attempt_reached WHEN NAME [RC]: the 50-minute rule reached before, during
# or after NAME, recorded once in the session facts (the rule, the instant,
# the step and when) and in the reason.
attempt_reached() {
    local when=$1 name=$2 rc=${3:-} text
    [ "$ATTEMPT_REACHED" -eq 0 ] || return 0
    ATTEMPT_REACHED=1
    case "$when:$name" in
        before:harness-run)
            text="stop rule reached: the attempt's allowance of ${ATTEMPT_LIMIT} s was spent before the harness could start (the harness was NOT started; the run directory was never created)" ;;
        during:harness-run)
            # Ended before the step printed the harness's start (its 6.1
            # preamble, loaded under the same bound, had not finished): the
            # harness, and with it the fault, was never started.
            if [ -z "${HARNESS_STARTED_UTC:-}" ]; then
                text="stop rule reached: the attempt was stopped ${ATTEMPT_LIMIT} s after its first 'drained' started (the harness step, the host preamble of runbook 6.1 it loads under the same bound included, was ended by 'timeout', exit $rc, before the harness started): the harness was NOT started; the run directory was never created"
            else
                text="stop rule reached: the attempt was stopped ${ATTEMPT_LIMIT} s after its first 'drained' started (the harness step was ended by 'timeout', exit $rc); the run directory, sealed or not, is preserved as incomplete"
            fi
            ;;
        during:tunnel-ready)
            text="stop rule reached: the attempt was stopped ${ATTEMPT_LIMIT} s after its first 'drained' started ('tunnel-ready', the host preamble of runbook 6.1 loaded under the bound just before the harness, was ended by 'timeout', exit $rc; a tunnel that did not open in time): the harness was NOT started; the run directory was never created" ;;
        before:*)
            text="stop rule reached: the attempt's allowance of ${ATTEMPT_LIMIT} s from its first 'drained' was spent before '$name' could start ('$name' was NOT started); no further proof step was started" ;;
        during:*)
            text="stop rule reached: the attempt was stopped ${ATTEMPT_LIMIT} s after its first 'drained' started ('$name' was ended by 'timeout', exit $rc; its record is kept as partial); no further proof step was started" ;;
        *)
            text="stop rule reached: the attempt's allowance of ${ATTEMPT_LIMIT} s from its first 'drained' was spent when '$name' ended; no further proof step was started" ;;
    esac
    ATTEMPT_TEXT=$text
    stoprule attempt "$text"
    session_update "instants.attempt_limit_reached_step=$name" "instants.attempt_limit_reached_when=$when" \
        "instants.attempt_limit_reached_host_uptime_s=$(uptime_s)"
}
# live_start NAME: what is left of the allowance for NAME, in LIVE_REST
# (whole seconds, positive), or non-zero when NAME must not start (the rule
# already reached, or reached now, before NAME, and recorded as such). It
# answers in a variable and is called in the driver's own shell, NEVER in a
# command substitution: run in a subshell, the latch (ATTEMPT_REACHED), the
# stop rule and the headline it sets would be lost with the subshell - every
# later live step would record the rule again (the facts naming the last
# step skipped, not the first), the reason would carry no stop rule, and
# the extension's blocker would not fire after the expiry.
LIVE_REST=0
live_start() {
    LIVE_REST=0
    [ "$ATTEMPT_REACHED" -eq 0 ] || return 1
    LIVE_REST=$(left)
    if [ "$LIVE_REST" -le 0 ]; then
        attempt_reached before "$1"
        return 1
    fi
    return 0
}
# live_end NAME RC: after NAME ran under the bound: 124 or 137 is the rule
# reached during it (its observation is incomplete and its record partial);
# nothing left afterwards is the rule reached when it ended. Answers RC.
live_end() {
    local name=$1 rc=$2
    if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        attempt_reached during "$name" "$rc"
        incomplete+=("'$name' was ended by 'timeout' when the attempt's allowance ran out (exit $rc): its observation was not completed")
    elif [ "$(left)" -le 0 ]; then
        attempt_reached after "$name"
    fi
    return "$rc"
}
# hx_bounded NAME REST SCRIPT [ARG...]: a host step of runbook 6.1 under
# 'bounded REST', the 6.1 preamble included. hx loads the preamble before
# and outside any bound, so a preamble that blocks (a 'tunnel_up' whose ssh
# never completes its banner) would run on across the expiry; here the
# whole step runs inside 'bounded': the preamble is handed to the bounded
# shell as the value of EGW_HOST_PRE, never as code text, and loaded there
# with 'eval', and a preamble that fails is 97 as hx answers it (the step
# never ran). The helpers thus run in a shell of their own, which 'timeout'
# can end; SCRIPT reads its ARGs as $1, $2... and holds no single quote;
# each ARG is written single-quoted (checked to be the literal it is). REST
# is the remainder live_start left in LIVE_REST: this function reads nothing
# of the allowance itself (live_hx, and the tunnel-ready step, which shares
# the check made before the harness is dispatched, call it).
hx_bounded() {
    local name=$1 rest=$2 script=$3 args="" arg
    shift 3
    for arg in "$@"; do
        guest_literal "$arg" || { missed "'$arg' cannot be written into the step '$name' as the literal it is"; return 1; }
        args="$args '$arg'"
    done
    ex "$A" "$name" env EGW_HOST_PRE="$HOST_PRE" bash -c "$(declare -f bounded)
bounded $rest bash -c '{ eval \"\$EGW_HOST_PRE\" ; } || { echo \"STOP: the host preamble of runbook 6.1 (the venv, the secrets, the helpers and the tunnels) could not be loaded: the step never ran\" >&2; exit 97; }
$script' _$args"
}
# live_hx NAME SCRIPT [ARG...]: hx_bounded under the attempt's allowance:
# NAME is dispatched only while something of it is left (live_start), under
# that remainder, and the rule reached during or after it is recorded
# (live_end).
live_hx() {
    local name=$1 script=$2 arg
    shift 2
    for arg in "$@"; do
        guest_literal "$arg" || { missed "'$arg' cannot be written into the step '$name' as the literal it is"; return 1; }
    done
    live_start "$name" || { not_started+=("$name"); return "$STEP_NOT_STARTED"; }
    hx_bounded "$name" "$LIVE_REST" "$script" "$@"
    live_end "$name" $?
}
# live_gx NAME GUEST-COMMAND: one guest command over ssh under the bound: the
# session's ssh helpers loaded as gx loads them (97 when they cannot be, or
# when ssh itself answers 255), inside 'bounded'.
live_gx() {
    local name=$1 rc rest
    live_start "$name" || { not_started+=("$name"); return "$STEP_NOT_STARTED"; }
    rest=$LIVE_REST
    ex "$A" "$name" bash -c "$(declare -f bounded)
bounded $rest env E=\"\$2\" bash -c '. \"\$E/scripts/session_common.sh\" || { echo \"STOP: the session ssh helpers (\$E/scripts/session_common.sh) could not be loaded: NOTHING was run on the guest\" >&2; exit 97; }
gssh \"\$1\"' _ \"\$1\"" _ "$2" "$SESSION"
    rc=$?
    [ "$rc" -ne 255 ] || rc=$EXIT_NOT_REACHED
    live_end "$name" "$rc"
}
# live_ex NAME CMD...: a host command under the bound.
live_ex() {
    local name=$1 rest
    shift
    live_start "$name" || { not_started+=("$name"); return "$STEP_NOT_STARTED"; }
    rest=$LIVE_REST
    ex "$A" "$name" bash -c "$(declare -f bounded)
bounded $rest \"\$@\"" _ "$@"
    live_end "$name" $?
}
# cut_by_rule RC: true when a live step's status says the attempt's stop rule
# kept it from being taken whole - not started (STEP_NOT_STARTED) or ended
# by 'timeout' of the remainder (124, or 137 after the grace) - so that a
# comparison that reads its record is not run on it.
cut_by_rule() {
    [ "$1" -eq "$STEP_NOT_STARTED" ] || [ "$1" -eq 124 ] || [ "$1" -eq 137 ]
}
# json_scalar VALUE: a whole number as a JSON number, anything else as a JSON
# string (the harness exit is one or the other: 0, or 'not-started').
json_scalar() {
    case "$1" in
        '' | *[!0-9]*) json_text "$1" ;;
        *) printf '%s' "$1" ;;
    esac
}

# --- the first stop rule from the candidate's start (F2, P-15) ------------------
# The 20-minute rule is measured from the candidate stack's actual start,
# never from the first poll: the candidate's start is the earliest StartedAt
# of the six expected services in the containers record taken BEFORE the
# wait (their latest StartedAt is kept beside it), and the guest clock read
# in that same record says how much of the allowance is already spent. In
# mode 'bound' the wait's own limit is the positive remainder of the
# allowance from that start (never more than the limit: a late poll never
# resets it), or the rule is reached before the wait can start (1); a
# healthy transition demonstrated earlier in the session and named by the
# student (a console record of the shared wait) establishes the rule
# instead when its healthy sample began after the latest start of the six -
# it is then of this same start - and COMPLETED by start + limit, and is
# refused otherwise (a healthy guest's later idle time is never charged as
# boot delay, and a transition of another start never counts); the wait
# then runs under the full limit as the precondition of a healthy stack
# before the run, which is no longer the rule's remainder. In mode 'check'
# the wait's first ALL HEALTHY observation is judged against start + limit
# unless the rule was established by the earlier record. The instant of a
# sample is read at its START, before its inspections of the six services,
# so it does not show when the observation was made: the shared wait
# follows the healthy sample with '<instant> completed (sample N)', read
# after its last inspection, and the observation had completed by then -
# in whole seconds, so before that instant + COMPLETION_RESOLUTION_S. That
# upper bound, never the sample's start, is what is compared with start +
# limit: a sample that began before the deadline and completed after it
# has not shown the stack healthy in time (the rule reached, 1), and a
# record without the completion line (a record of the wait made before it
# recorded it) cannot place the observation at all (2). The span from the
# sample before it is still recorded, as information. Anything that cannot
# be read is 2:
# an unknown start or transition cannot establish the rule - docker's zero
# StartedAt (0001-01-01T00:00:00Z, which it reports for a container created
# but never started) included, which is no start at all and never read as
# one two thousand years ago. Every instant
# compared here is read on the guest wall clock (docker StartedAt and the
# wait samples alike), which on this host is stepped backwards by 2-3 s
# about every 30 s (LOG.md; the evaluator applies the same band,
# HOST_CLOCK_STEP_BAND_S, to host instants): an instant that precedes
# another by no more than that band is read as simultaneous, and recorded
# as such, while a larger regression is a clock that is not consistent (2).
# A backwards step only makes an instant read earlier, so the deadline is
# judged on the instant as read. The text holds no single quote: it is
# handed to the interpreter as one argument.
HEALTHY_RULE_PY='
import json, math, re, sys
from datetime import datetime, timezone

INSTANT = re.compile(r"(\d{4}-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,9}))?Z$")
# The StartedAt docker reports for a container created but never started:
# its zero time, which is no start (an unknown start, never year 1).
DOCKER_ZERO_START = re.compile(r"0001-01-01T00:00:00(?:\.0{1,9})?Z$")
CLOCK_STEP_BAND_S = 3.0
# The completion instant is read in whole seconds (the guest date has no
# finer field): the inspections had completed before it + this.
COMPLETION_RESOLUTION_S = 1.0


def epoch(text):
    """A guest instant (a StartedAt of docker, or a sample line of the shared
    wait) as seconds since the epoch, or None when it is not of that form."""
    m = INSTANT.match(str(text or "").strip())
    if not m:
        return None
    base = datetime.strptime("%sT%s%s%s" % m.groups()[:4], "%Y-%m-%dT%H%M%S").replace(tzinfo=timezone.utc)
    fraction = int(m.group(5).ljust(9, "0")) / 1e9 if m.group(5) else 0.0
    return base.timestamp() + fraction


def containers(path):
    starts, guest_epoch, problems, named = {}, None, [], set()
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m = re.match(r"container (\S+) id=(\S+) started=(\S+)$", line)
        if m:
            named.add(m.group(1))
            if DOCKER_ZERO_START.match(m.group(3)):
                problems.append("%s: its start instant %r is the zero StartedAt docker reports for a container created but never started, which is no start" % (m.group(1), m.group(3)))
                continue
            at = epoch(m.group(3))
            if at is None:
                problems.append("%s: its start instant %r is not readable" % (m.group(1), m.group(3)))
            else:
                starts[m.group(1)] = (at, m.group(3))
            continue
        m = re.match(r"clock epoch=(\d+) utc=(\S+)$", line)
        if m:
            guest_epoch = int(m.group(1))
    return starts, guest_epoch, problems, named


def transition(path):
    """The first ALL HEALTHY line of a record of the shared wait, with the
    instant of the sample that saw it (its start), the instant of the sample
    before it and the instant read after the last inspection of that sample:
    (epoch or None, text, sample, previous text or None, completed text or
    None), or None when the record holds no such line. A record of the wait
    made before it recorded the completion has none (None)."""
    samples, completed = {}, {}
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = re.match(r"(\S+) sample (\d+):", line)
        if m:
            samples[int(m.group(2))] = m.group(1)
            continue
        m = re.match(r"(\S+) completed \(sample (\d+)\)$", line)
        if m:
            completed[int(m.group(2))] = m.group(1)
            continue
        m = re.match(r"ALL HEALTHY: .*\(sample (\d+)\)$", line)
        if m:
            n = int(m.group(1))
            return epoch(samples.get(n)), samples.get(n), n, samples.get(n - 1), completed.get(n)
    return None


def completed_by(at, completed):
    """The upper bound of the healthy observation: the completion instant
    read after its last inspection, plus its resolution (never earlier than
    the sample start as read), or None when the record does not say."""
    done = epoch(completed)
    if done is None:
        return None
    return max(at, done) + COMPLETION_RESOLUTION_S


def stop(code, text, facts):
    print(("CANNOT BE ESTABLISHED: " if code == 2 else "HEALTHY RULE REACHED: ") + text)
    print("healthy_rule=" + json.dumps(facts))
    sys.exit(code)


mode, expected, containers_path, limit = sys.argv[1], sys.argv[2].split(","), sys.argv[3], int(sys.argv[4])
facts = {"limit_s": limit, "clock_step_band_s": CLOCK_STEP_BAND_S,
         "candidate_start_note": "the earliest StartedAt of the expected services, read before the wait (P-15)"}
try:
    starts, guest_epoch, problems, named = containers(containers_path)
except OSError as exc:
    stop(2, "the containers record could not be read: %s" % exc, facts)
problems += ["%s: not named in the containers record" % s for s in expected if s not in named]
if problems:
    stop(2, "the candidate start is unknown: " + "; ".join(problems), facts)
earliest = min(starts.values())
latest = max(starts.values())
deadline = earliest[0] + limit
facts.update({"candidate_start_utc": earliest[1], "latest_start_utc": latest[1]})
if mode == "bound":
    earlier = sys.argv[5] if len(sys.argv) > 5 else ""
    if guest_epoch is None:
        stop(2, "the containers record carries no guest clock line, so what is left of the allowance from the candidate start cannot be computed", facts)
    facts.update({"guest_epoch_at_record": guest_epoch, "earlier_record": None})
    if guest_epoch - earliest[0] < -CLOCK_STEP_BAND_S:
        stop(2, "the guest clock at the containers record (%d) precedes the candidate start (%s) by more than the clock step band of %g s: the guest clock is not consistent" % (guest_epoch, earliest[1], CLOCK_STEP_BAND_S), facts)
    spent = max(0, int(guest_epoch - earliest[0]))
    facts["spent_before_wait_s"] = spent
    if earlier:
        try:
            seen = transition(earlier)
        except OSError as exc:
            stop(2, "the named earlier record could not be read: %s" % exc, facts)
        if seen is None or seen[0] is None:
            stop(2, "the named earlier record %s holds no ALL HEALTHY transition with a readable instant" % earlier, facts)
        at, text, n, _, completed = seen
        facts.update({"earlier_record": earlier, "earlier_transition_utc": text, "earlier_transition_sample": n,
                      "earlier_elapsed_s": max(0, int(at - earliest[0])), "earlier_transition_completed_utc": completed})
        if at < latest[0] - CLOCK_STEP_BAND_S:
            stop(2, "the named earlier record transition (%s, sample %d) precedes the latest start of the six services (%s) by more than the clock step band of %g s: it is not a healthy transition of this same start" % (text, n, latest[1], CLOCK_STEP_BAND_S), facts)
        upper = completed_by(at, completed)
        if upper is None:
            stop(2, "the named earlier record %s says when its first healthy sample (sample %d) began (%s) but not when its inspections completed (a record of the shared wait made before it recorded that instant): a sample start alone does not show that the observation was made within the allowance, so it cannot establish the rule; nothing is guessed" % (earlier, n, text), facts)
        facts["earlier_completed_upper_elapsed_s"] = int(math.ceil(upper - earliest[0]))
        if upper > deadline:
            facts["established_by"] = None
            stop(1, "the named earlier record transition (%s) lies %d s after the candidate start %s and its inspections completed by %s (%d s after it), beyond the %d s allowance: the stack with the candidate was not shown healthy within it" % (text, at - earliest[0], earliest[1], completed, math.ceil(upper - earliest[0]), limit), facts)
        facts["established_by"] = "earlier-record"
        bound = limit
        print("HEALTHY RULE: established by the earlier record %s (transition %s, %d s after the candidate start %s, completed by %s, within %d s); the wait runs under %d s" % (earlier, text, at - earliest[0], earliest[1], completed, limit, bound))
    else:
        rest = int(deadline - guest_epoch)
        facts["established_by"] = "own-observation"
        if rest <= 0:
            facts["established_by"] = None
            stop(1, "the candidate start %s (the earliest StartedAt of the six services) lies %d s in the past, beyond the %d s allowance, and no earlier healthy transition of this start is named: the wait was NOT started" % (earliest[1], spent, limit), facts)
        bound = min(limit, rest)
        print("HEALTHY RULE: %d s of the %d s allowance from the candidate start %s already spent; the wait runs under the %d s left" % (spent, limit, earliest[1], bound))
    facts["poll_bound_s"] = bound
    print("healthy_rule=" + json.dumps(facts))
    print("established=" + str(facts["established_by"]))
    print("bound=%d" % bound)
    sys.exit(0)
if mode == "check":
    record, established = sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else ""
    try:
        seen = transition(record) if record else None
    except OSError as exc:
        stop(2, "the record of the wait could not be read: %s" % exc, facts)
    if seen is None or seen[0] is None:
        stop(2, "the record of the wait holds no ALL HEALTHY transition with a readable instant: the first healthy observation is unknown", facts)
    at, text, n, previous, completed = seen
    elapsed = at - earliest[0]
    # The instant of the sample is read at its START, before its inspections
    # of the six services: it does not show when the observation was made.
    # The shared wait reads one more instant after the last inspection of
    # its healthy sample (the completion line), and the observation had
    # completed by then; that upper bound is judged against the deadline.
    # The span from the instant of the sample before it is kept as
    # information.
    previous_at = epoch(previous)
    span = None if previous_at is None else round(at - previous_at, 3)
    print("first_healthy_utc=%s" % text)
    print("first_healthy_sample=%d" % n)
    print("first_healthy_completed_utc=%s" % (completed if epoch(completed) is not None else "null"))
    print("first_healthy_instant_note=the instant of the sample that saw ALL HEALTHY is read at the sample start, before its inspections of the services; the observation had completed by the instant the wait read after its last inspection (first_healthy_completed_utc, whole seconds: before that instant + %g s), and that upper bound is what the deadline is judged on" % COMPLETION_RESOLUTION_S)
    print("previous_sample_utc=%s" % (previous if previous_at is not None else "null"))
    print("previous_sample_span_s=%s" % ("null" if span is None else json.dumps(span)))
    if elapsed < -CLOCK_STEP_BAND_S:
        print("elapsed_s=%d" % int(elapsed))
        stop(2, "the first healthy observation (%s) precedes the candidate start (%s) by more than the clock step band of %g s: the guest clock is not consistent" % (text, earliest[1], CLOCK_STEP_BAND_S), facts)
    if elapsed < 0:
        print("clock_step_note=the first healthy sample (%s) reads %.3f s before the candidate start (%s), within the clock step band of %g s: read as simultaneous" % (text, -elapsed, earliest[1], CLOCK_STEP_BAND_S))
        elapsed = 0.0
    print("elapsed_s=%d" % int(elapsed))
    if established == "earlier-record":
        print("HEALTHY RULE MET: first observed healthy %d s after the candidate start %s (sample %d at %s; allowance %d s, established by the earlier record)"
              % (elapsed, earliest[1], n, text, limit))
        sys.exit(0)
    upper = completed_by(at, completed)
    if upper is None:
        stop(2, "the record of the wait does not say when the inspections of its first healthy sample (sample %d, begun %s) completed: a sample start alone does not show that the observation was made within the allowance, so the first healthy observation cannot be placed" % (n, text), facts)
    upper_elapsed = int(math.ceil(upper - earliest[0]))
    print("completed_upper_elapsed_s=%d" % upper_elapsed)
    if upper > deadline:
        stop(1, "the stack was first observed healthy by sample %d, which began %d s after the candidate start %s (%s) and whose inspections completed by %s (%d s after it), beyond the %d s allowance: timely health cannot be established (a late poll never resets it)" % (n, elapsed, earliest[1], text, completed, upper_elapsed, limit), facts)
    print("HEALTHY RULE MET: first observed healthy by sample %d, which began %d s after the candidate start %s (%s) and whose inspections completed by %s (%d s after it), within the %d s allowance"
          % (n, elapsed, earliest[1], text, completed, upper_elapsed, limit))
    sys.exit(0)
print("CANNOT BE ESTABLISHED: unknown mode %r" % mode)
sys.exit(2)
'

# --- the eligibility of the run (F1, P-16) --------------------------------------
# After the harness step the manifest is read: the run is eligible only
# when the prescribed publication completed (simulator_returncode 0), the
# harness copy of the events was fetched (events_fetch ok, the first of the
# two copies the ADR keeps apart, its file present), the collector file is
# present, the post-drain copy was fetched and verified, both twin
# snapshots were verified, the three SUT logs were fetched with their
# files, the fault command was executed and exited 0, and the harness
# validity is admitted as E-12 states - read by the very function the
# evaluator applies (egw_experiments.proof_evaluator.harness_admission,
# imported from the clean clone), never by a match of the reason texts:
# 'valid', or the campaign sampling-gap deviation in the one form the
# harness records it ('sampling-gap-only'), in which the collector file is
# the one the ingest rejected, where the admission names it
# (logs/collector/resources-RUN_ID.csv), instead of resources.csv at the
# top of the run directory. Anything else is NOT ELIGIBLE (1), an evidence
# requirement not met; a manifest that cannot be read, or an admission that
# cannot be established and nothing else amiss, is 2. The reading, with
# the admission as the function returns it, is printed as one JSON line for
# the session facts. The text holds no single quote (one interpreter
# argument).
ELIGIBILITY_PY='
import json, sys
from pathlib import Path

run_dir, harness_exit = Path(sys.argv[1]), sys.argv[2]
SUT_LOGS = {"broker_log": "broker.log", "controller_log": "controller.log", "docker_events": "docker-events.log"}
TWINS = ("twins.before.json", "twins.after.json")
facts = {"complete": False, "harness_exit": int(harness_exit) if harness_exit.isdigit() else harness_exit,
         "rule": "P-16: the harness validity is admitted only as E-12 states, by the function the evaluator applies (egw_experiments.proof_evaluator.harness_admission)",
         "problems": [], "harness_admission": None}
problems = facts["problems"]


def present(rel):
    path = run_dir / rel
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def stop(text):
    problems.append(text)
    print("NOT ELIGIBLE: " + text)
    print("eligibility=" + json.dumps(facts))
    sys.exit(2)


try:
    from egw_experiments.proof_evaluator import ADMISSION_SAMPLING_GAP_ONLY, harness_admission
except Exception as exc:  # the shared admission is the rule itself: without it nothing is admitted
    stop("the shared admission (egw_experiments.proof_evaluator.harness_admission) could not be loaded (%s: %s)" % (type(exc).__name__, exc))
try:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("not a JSON object")
except (OSError, ValueError) as exc:
    stop("manifest.json: could not be read (%s: %s)" % (type(exc).__name__, exc))

# E-12, as the evaluator reads it on the same run directory.
admission = harness_admission(manifest, run_dir)
facts["harness_admission"] = admission
gap_form = admission.get("admitted") is True and admission.get("form") == ADMISSION_SAMPLING_GAP_ONLY
sim = manifest.get("simulator_returncode")
facts["simulator_returncode"] = sim
if sim != 0 or isinstance(sim, bool):
    problems.append("simulator_returncode is %r, not 0: the prescribed publication did not complete (a run shorter than prescribed is not the proof)" % (sim,))
fetch = manifest.get("events_fetch")
facts["events_fetch_ok"] = fetch.get("ok") if isinstance(fetch, dict) else None
if not isinstance(fetch, dict):
    problems.append("events_fetch: no record of the harness copy of the events (--fetch-events-cmd), the first of the two copies the ADR keeps apart")
elif fetch.get("ok") is not True:
    problems.append("events_fetch: the harness copy of the events failed after %d attempt(s)" % len(fetch.get("attempts") or []))
elif not present("events.jsonl"):
    problems.append("events.jsonl: the harness copy of the events is absent or empty")
facts["resources_csv_present"] = present("resources.csv")
if gap_form:
    # The collector file the harness ingest rejected, kept where the
    # admission names it (E-12), in the place of resources.csv, which the
    # harness never writes in this form.
    collector = admission.get("collector_file")
    facts["collector_file"] = collector
    facts["collector_file_present"] = isinstance(collector, str) and bool(collector) and present(collector)
    if not facts["collector_file_present"]:
        problems.append("%s: the collector file the harness ingest rejected (the sampling-gap form, E-12) is absent or empty" % (collector,))
else:
    facts["collector_file"] = "resources.csv"
    facts["collector_file_present"] = facts["resources_csv_present"]
    if not facts["resources_csv_present"]:
        problems.append("resources.csv: the collector file is absent or empty")
post = manifest.get("events_post_drain_fetch")
if not isinstance(post, dict):
    problems.append("events_post_drain_fetch: no record of the post-drain copy (--post-drain-fetch-cmd)")
elif post.get("source") != "ingested" and post.get("ok") is not True:
    problems.append("events_post_drain_fetch: the post-drain copy failed after %d attempt(s)" % len(post.get("attempts") or []))
elif post.get("verified") is not True:
    problems.append("events_post_drain_fetch: the post-drain copy is not verified as this run: " + "; ".join(post.get("problems") or []))
elif not present("events.post-drain.jsonl"):
    problems.append("events.post-drain.jsonl: recorded as fetched but absent or empty")
snapshots = manifest.get("twin_snapshots")
by_file = {r.get("file"): r for r in (snapshots if isinstance(snapshots, list) else []) if isinstance(r, dict)}
for name in TWINS:
    record = by_file.get(name)
    if record is None:
        problems.append("%s: no twin snapshot record (--twin-snapshot-cmd)" % name)
    elif record.get("verified") is not True:
        problems.append("%s: the twin snapshot is not verified (exit %r)" % (name, record.get("returncode")))
    elif not present(name):
        problems.append("%s: recorded as verified but absent or empty" % name)
fetches = manifest.get("sut_log_fetches")
by_hook = {r.get("hook"): r for r in (fetches if isinstance(fetches, list) else []) if isinstance(r, dict)}
for hook, name in SUT_LOGS.items():
    rel = "logs/sut/" + name
    record = by_hook.get(hook)
    if record is None:
        problems.append("%s: no fetch record (%s)" % (rel, hook))
    elif record.get("returncode") != 0 or not record.get("dest_exists"):
        problems.append("%s: the fetch exited %r and %s" % (rel, record.get("returncode"), "wrote its file" if record.get("dest_exists") else "wrote no file"))
    elif not present(rel):
        problems.append("%s: recorded as fetched but absent or empty" % rel)
restart = manifest.get("restart")
if not isinstance(restart, dict):
    problems.append("restart: no record of the fault (--restart-cmd)")
elif restart.get("executed") is not True or restart.get("returncode") != 0:
    problems.append("restart: the fault command was not executed cleanly (executed=%r, exit %r)" % (restart.get("executed"), restart.get("returncode")))
validity = manifest.get("validity")
reasons = manifest.get("validity_reasons")
facts["harness_validity"] = validity
facts["harness_validity_reasons"] = [str(r) for r in reasons] if isinstance(reasons, list) else reasons
# Whether the invalidity is the sampling-gap form alone: null when the run
# is not invalid or the admission cannot be read (never false for unknown).
facts["sampling_gap_only"] = gap_form if validity == "invalid" and admission.get("admitted") is not None else None
unknown = admission.get("admitted") is None
if admission.get("admitted") is True:
    if admission.get("form") != ADMISSION_SAMPLING_GAP_ONLY and facts["harness_exit"] != 0:
        problems.append("the harness exited %s although the manifest calls the run valid: a failure the manifest does not record" % harness_exit)
elif admission.get("admitted") is False:
    problems.append("harness validity not admitted for the proof (E-12, form %r, egw_experiments.proof_evaluator.harness_admission): %s"
                    % (admission.get("form"), " | ".join(str(r) for r in admission.get("reasons") or [])))
else:
    problems.append("harness validity: its admission for the proof cannot be established (E-12, form %r): %s"
                    % (admission.get("form"), " | ".join(str(r) for r in admission.get("reasons") or [])))
facts["complete"] = not problems
for problem in problems:
    print("NOT ELIGIBLE: " + problem)
if not problems:
    print("ELIGIBLE: the prescribed publication completed, both copies of the events, the collector file, both twin snapshots, the three SUT logs and the fault record are present, and the harness validity is admitted as E-12 states (form %r)%s"
          % (admission.get("form"), (" - the campaign MAX_SAMPLE_GAP_S deviation alone, kept as recorded: the collector file the ingest rejected is kept at %s%s"
                                     % (admission.get("collector_file"), "; SHA256SUMS withheld for " + admission["seal_withheld_for"] if admission.get("seal_withheld_for") else "")) if gap_form else ""))
if gap_form:
    # For the package: its declared artefacts follow the same inventory in
    # this form (amend_expected_artefacts).
    print("sampling_gap_collector_file=%s" % admission.get("collector_file"))
    print("sampling_gap_seal_withheld=%s" % ("yes" if admission.get("seal_withheld_for") else "no"))
print("eligibility=" + json.dumps(facts))
sys.exit(0 if not problems else (2 if unknown and len(problems) == 1 else 1))
'

# --- the extension's bounds (ADR 0011, item 4 section 9) ----------------------
# Every step of the optional extension runs under what is left of its ceiling
# (EGW_PROOF_EXTENSION_LIMIT_S, from EXT_T0) and two of them, besides, under
# the ADR's per-step stop rules "imposed by design, not measured durations":
# the restart command within the grace period plus 5 minutes, and the second
# fetch within 5 minutes. The grace period is the stop_grace_period the
# configuration identity captured at 'pre' reports (the value the guest
# reported), read as whole seconds (GRACE_S). These functions are defined
# here, at the top level, so that a test can run them on their own.
EXT_RULE_RESTART='the restart command within the grace period plus 5 minutes'
EXT_RULE_FETCH='the second fetch within 5 minutes'
EXT_FETCH_LIMIT=300
EXT_STEP_RULE=""         # the stop rule the last ext_step ran under, or '' for the ceiling alone
EXT_STEP_LIMIT=""        # the bound, in seconds, the last ext_step ran under
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
# ext_step NAME BOUND RULE CMD...: one host step of the extension under the
# smaller of what is left of its ceiling and BOUND (the limit, in seconds,
# of the per-step stop rule RULE; both '' for a step without one), through
# 'bounded' (an interrupt reaches it). The helpers of runbook 6.1 run in a
# shell of their own that loads the deployed helper file, as the hook
# wrappers do, so that 'timeout' can end them; a bound reached during the
# step is 124 or 137, and ext_cut names what was reached.
ext_step() {
    local name=$1 bound=$2 rule=$3 limit
    shift 3
    limit=$(ext_left)
    EXT_STEP_RULE=""
    if [ -n "$bound" ] && [ "$bound" -le "$limit" ]; then
        limit=$bound
        EXT_STEP_RULE=$rule
    fi
    EXT_STEP_LIMIT=$limit
    hx "$A" "$name" "$(declare -f bounded)
bounded $limit $*"
}
# ext_cut NAME RC: non-zero, with the reason recorded, when the step was
# ended by 'timeout': by the per-step stop rule it ran under, which is
# named, or by the ceiling.
ext_cut() {
    [ "$2" -eq 124 ] || [ "$2" -eq 137 ] || return 1
    if [ -n "$EXT_STEP_RULE" ]; then
        ext_reasons+=("the extension's stop rule reached: $EXT_STEP_RULE (${EXT_STEP_LIMIT} s; '$1' was ended by 'timeout', exit $2)")
        session_update "extension.stop_rule_reached=$EXT_STEP_RULE"
    else
        ext_reasons+=("the extension's ceiling of ${EXTENSION_LIMIT} s was reached during '$1' (exit $2)")
    fi
    return 0
}

# --- identities and the record of the values ----------------------------------
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
VALUES=$(printf '{"DRAIN_QUIET_S": %s, "DRAIN_STEP_S": %s, "DRAIN_LIMIT_S": %s, "EGW_HEALTH_LIMIT_S": %s, "EGW_HEALTH_STEP_S": %s, "EGW_READY_LIMIT_S": %s, "EGW_PROOF_ATTEMPT_LIMIT_S": %s, "EGW_PROOF_RESTART_AT_S": %s, "EGW_PROOF_DURATION_S": %s, "EGW_PROOF_RATE": %s, "EGW_PROOF_MASTER_SEED": %s, "EGW_PROOF_EXTENSION": "%s", "EGW_PROOF_EXTENSION_LIMIT_S": %s, "extension_restart_limit_after_grace_s": 300, "extension_fetch_limit_s": 300, "EGW_PROOF_BASE": %s, "EGW_PROOF_PLAN": %s, "EGW_PROOF_RUNBOOK": %s, "EGW_PROOF_HEALTHY_RECORD": %s, "expected_source_commit": "%s"}' \
    "$DRAIN_QUIET_S" "$DRAIN_STEP_S" "$DRAIN_LIMIT_S" "$LIMIT" "$STEP" "$READY_LIMIT" "$ATTEMPT_LIMIT" "$RESTART_AT" "$DURATION" "$RATE" "$MASTER_SEED" "$EXTENSION" "$EXTENSION_LIMIT" "$(json_text "$BASE")" "$(json_text "$PLAN")" "$(json_text "$RUNBOOK")" "$HEALTHY_RECORD_JSON" "$EXPECTED_COMMIT")
# The artefacts the package must hold, declared before anything starts. In
# the sampling-gap form E-12 admits, the harness never writes resources.csv
# and withholds SHA256SUMS for it; that declaration is then amended once,
# after the eligibility reading and with the reason on the attempt
# (amend_expected_artefacts below), never silently.
EXPECTED_ARTEFACTS='["raw/*/manifest.json", "raw/*/sent_events.jsonl", "raw/*/events.jsonl", "raw/*/events.post-drain.jsonl", "raw/*/twins.before.json", "raw/*/twins.after.json", "raw/*/configuration_identity.json", "raw/*/controller_metrics.csv", "raw/*/resources.csv", "raw/*/logs/sut/broker.log", "raw/*/logs/sut/controller.log", "raw/*/logs/sut/docker-events.log", "raw/*/SHA256SUMS", "analysis/proof_session.json", "analysis/proof_verdict.json", "analysis/snapshots/*.config_identity.json", "analysis/snapshots/*.metrics.before.json", "analysis/snapshots/*.metrics.after.json", "analysis/snapshots/*.twins.before.json", "analysis/snapshots/*.twins.after.json", "analysis/snapshots/*.restart.txt", "environment/proof_plan.json", "environment/sut_environment.json", "environment/clocks.txt", "environment/containers.before.txt", "environment/containers.after.txt", "environment/helpers-check.txt"]'
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$IDENTITIES" \
    "workload={\"session\": $(json_text "$(basename "$SESSION")"), \"proof\": \"the finite proof (ADR 0011)\", \"engineering_diagnostic_not_a_g3_run\": true, \"harness_run_id\": \"$RID\", \"condition\": \"controller_restart\", \"scenario\": \"nominal\", \"warmup_s\": 0, \"duration_s\": $DURATION, \"rate_msg_s\": $RATE, \"restart_at_s\": $RESTART_AT, \"fault\": \"SIGKILL of the controller's container followed by a start (proof_restart_controller.sh)\", \"devices\": \"smartwatch, smart ring, smart clothing (nominal mix)\", \"values\": $VALUES}" \
    "proof_verdict=not-computed" "restoration=not-started" "restart_shown=unknown" "extension=$EXTENSION_RESULT" \
    "expected_artefacts=$EXPECTED_ARTEFACTS") \
    || PREREQ="the attempt fields could not be recorded"
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || PREREQ=${PREREQ:-"the identity of the clean clone could not be read (see identities.identity_error)"}

# not_run REASON: a prerequisite failed, so the harness was never started. A
# stop rule reached is never a prerequisite failed (stopped_before_harness).
# Once the 50-minute rule has been reached (the latch, ATTEMPT_REACHED: say
# 'pre' ended at the deadline, whatever its exit), a prerequisite that
# fails afterwards - 'pre' itself, the identity check, a mandatory record -
# does not make the attempt not-run: the rule was reached, so the proof is
# recorded inconclusive with the rule named beside the prerequisite that
# failed (the outcome is inconclusive whenever the rule is reached). Before
# the latch nothing changes.
not_run() {
    if [ "${ATTEMPT_REACHED:-0}" -eq 1 ]; then
        stopped_before_harness "the 50-minute rule was reached before the harness, and a prerequisite then failed ($1)" \
            "${ATTEMPT_TEXT}; after it a prerequisite failed as well: $1; the proof is recorded inconclusive by that rule, never not-run"
    fi
    headline "$A" "$1: the harness was NOT started" || true
    set_field "restoration=$(guest_state_text)"
    session_update "restoration=$(guest_state_text)" "instants.ended_utc=$(now_utc)"
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "$1; the harness was NOT started; the guest was left with $(guest_state_text)" \
        --next-action "read console/; the harness was NOT started and nothing was published under $RID")
    driver_exit "$A"
}
# stopped_before_harness WHERE REASON: a stop rule reached before the
# harness - the 20-minute rule (the stack with the candidate not healthy
# within EGW_HEALTH_LIMIT_S of its start), or the 50-minute rule once the
# attempt's clock runs (from T0, recorded as the instant its first 'drained'
# starts: before 'pre' could be dispatched, during it, or before the
# harness could start): "If a stop rule is reached, the session stops and
# the proof is recorded inconclusive" (ADR 0011, the finite proof's
# ceiling), never not-run, which is a prerequisite failed. WHERE says which
# rule was reached and when, for the next action; the rule itself is
# recorded (stoprule, attempt_reached) before this is called. The harness
# was not started and the stack was not touched by the proof; the
# instrumentation is invalid (no run, no evidence), exit 3.
stopped_before_harness() {
    local next="the attempt is inconclusive, not passing: $1 (read console/); the student decides whether to repeat it with the same design (recorded as a repeat, this run kept) or to re-decide the option"
    [ "$STACK_STATE" != not-healthy ] || next="$next; the stack was left not-healthy: resolve it before any other guest session"
    headline "$A" "$2: the harness was NOT started" || true
    set_field "restoration=$(guest_state_text)"
    session_update "restoration=$(guest_state_text)" "instants.ended_utc=$(now_utc)"
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome inconclusive \
        --reason "$2; the harness was NOT started and nothing was published under $RID; the guest was left with $(guest_state_text)" \
        --next-action "$next")
    driver_exit "$A"
}
# rule_capture_stop NAME: capture_stop for a step after the attempt's clock
# started ('pre', the identity check). Once the 50-minute rule has been
# reached (the latch, ATTEMPT_REACHED) the final reason names it beside the
# capture that was lost, as not_run names it beside a prerequisite: the rule
# is in the session facts already, and the reason does not omit it.
rule_capture_stop() {
    local note="the harness was NOT started"
    [ "${ATTEMPT_REACHED:-0}" -eq 0 ] || note="$note; ${ATTEMPT_TEXT}; the proof is recorded inconclusive by that rule"
    capture_stop "$A" "$1" "$note"
}
# The rule the 20-minute stop rule is, for the next action.
HEALTHY_WHERE="the 20-minute rule (the stack with the candidate healthy within ${LIMIT} s of its start) was reached before the harness"
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
    # The extension's own restoration (after its second kill + start) is
    # recorded apart from the proof's, which the verdict document echoes.
    [ "$EXT_RESTORE" -eq 0 ] || session_update "extension.restoration=$(guest_state_text)"
}
# evaluator_said: why the evaluator did not evaluate, from its stderr: its
# 'error: ' lines, else its '[proof] ' summary line (the not-evaluated
# document of a seal that does not verify prints only that line), else the
# fact that it printed no reason - so that the note never ends with nothing
# after the colon.
evaluator_said() {
    local f why=""
    f=$(ls "$A"/console/*-evaluate.stderr.txt 2> /dev/null | tail -n 1)
    if [ -n "$f" ] && [ -f "$f" ]; then
        why=$(sed -n 's/^error: //p' "$f" | tr '\n' ' ')
        [ -n "${why// /}" ] || why=$(sed -n 's/^\[proof\] //p' "$f" | tr '\n' ' ')
    fi
    why=${why% }
    [ -n "$why" ] || why="no reason printed on stderr"
    printf '%s' "$why"
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
# The record is kept whatever the check said (a difference is read from it);
# before the harness every failure is a prerequisite (design 2.2), so a
# record that could not be kept stops the driver here, never after the fault.
kept=1
keep_record helpers-check helpers-check.txt "the helper file check" || kept=0
[ "$rc" -eq 0 ] || not_run "the deployed helper file $HELPERS is not the runbook's section 6.1 heredoc, so the 'drained', '_mline' and 'config_identity' in use are not the reviewed ones (helpers-check exit $rc: regenerate it with regen_helpers.py)"
[ "$kept" -eq 1 ] || not_run "the record of the helper file check was not kept in environment/helpers-check.txt"

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
    # timedatectl's lines, each as it was printed (a value holds spaces).
    if clock_record=$(record_file guest-clock); then
        sed -n '3,$p' "$clock_record" | sed 's/^/guest_timedatectl=/'
    fi
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

# --- 5. the containers before, then the stack healthy: the first stop rule -------
# containers_script: the guest clock, then the id and the start instant of
# each expected container (persistence.sh), in the identical form before and
# after the run; the restart-shown step reads the controller's pair from the
# two records, and the healthy-rule step reads the candidate's start (the
# earliest StartedAt of the six) and the clock from the record before.
containers_script() {
    printf "EXPECT='%s'\nDEPLOYED='%s'\n" "$EXPECT_SERVICES" "$DEPLOYED"
    cat << 'GUEST_CONTAINERS'
cd "$DEPLOYED" || { echo "STOP: $DEPLOYED could not be entered"; exit 1; }
rc=0
echo "clock epoch=$(date +%s) utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
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
# The containers BEFORE the wait: the candidate's start is read from them
# (P-15), and they are the 'before' side of the restart shown. The host's
# monotonic instant just before them is the anchor from which the host
# bounds the acquisition of the healthy observation below: the guest clock
# the remainder is computed from is read after it.
HEALTHY_ANCHOR_UP=$(uptime_s)
gx "$A" containers-before "$(containers_script)"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" containers-before "the harness was NOT started"
[ "$rc" -eq 0 ] || not_run "the containers' ids and start instants were not recorded before the run (containers-before exit $rc)"
keep_record containers-before containers.before.txt "the containers before the run" \
    || not_run "the record of the containers before the run was not kept"
# The allowance from the candidate's start: what is left of it bounds the
# wait; spent, the rule is reached before the wait can start; an earlier
# transition of this same start, when named, establishes it instead.
ex "$A" healthy-rule "$PY" -c "$HEALTHY_RULE_PY" bound "$EXPECT_SERVICES" "$ENVD/containers.before.txt" "$LIMIT" "$HEALTHY_RECORD"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" healthy-rule "the harness was NOT started"
HEALTHY_FACTS=$(said healthy-rule 'healthy_rule=')
[ -z "${HEALTHY_FACTS// /}" ] || session_update "healthy_rule=$HEALTHY_FACTS"
case "$rc" in
    0) ;;
    1)
        # The 20-minute rule reached: a stop rule, so the proof is recorded
        # inconclusive (exit 3), never not-run (the allowance from the
        # candidate's start spent before the wait, or the named earlier
        # transition of this start beyond it).
        STACK_STATE=unknown
        stoprule healthy "stop rule reached: the stack with the candidate was not healthy within ${LIMIT} s of its start:$(said healthy-rule 'HEALTHY RULE REACHED: ')"
        stopped_before_harness "$HEALTHY_WHERE" "stop rule reached: the stack with the candidate was not healthy within ${LIMIT} s of its start (healthy-rule exit 1: the allowance from the candidate's start, the earliest StartedAt of the six services, was spent before the wait could start, or the earlier transition named lies beyond it; the wait was NOT started); the proof is recorded inconclusive by that rule"
        ;;
    *)
        not_run "the first stop rule cannot be established (healthy-rule exit $rc):$(said healthy-rule 'CANNOT BE ESTABLISHED: ')"
        ;;
esac
HEALTHY_BOUND=$(said healthy-rule 'bound=' | tr -d ' ')
HEALTHY_ESTABLISHED=$(said healthy-rule 'established=' | tr -d ' ')
case "$HEALTHY_BOUND" in
    '' | *[!0-9]*) not_run "the bound of the healthy wait could not be read from healthy-rule's line" ;;
esac
[ "$HEALTHY_BOUND" -gt 0 ] && [ "$HEALTHY_BOUND" -le "$LIMIT" ] \
    || not_run "the bound of the healthy wait ($HEALTHY_BOUND s) is not a positive remainder of EGW_HEALTH_LIMIT_S=$LIMIT"
if [ -n "$HEALTHY_RECORD" ]; then
    cp "$HEALTHY_RECORD" "$ENVD/healthy-record.txt" || not_run "the earlier healthy record named could not be kept in environment/healthy-record.txt"
fi
# The acquisition of the healthy observation is bounded as a whole (F2b):
# the shared wait checks its limit only between samples, so an inspection
# that blocks would hold it - and the driver - past the allowance. When the
# driver's own observation is to establish the rule, the wait runs as one
# guest command under 'bounded' of what is left of the allowance on the
# host's monotonic clock from the anchor (HEALTHY_BOUND, the remainder at
# the containers record, less the time since): ended by it (124, 137), no
# sample completed healthy within the allowance, which is the rule reached.
# With the rule established by an earlier record the poll is the
# precondition of a healthy stack under the full limit and runs as before.
HEALTHY_REST=""
if [ "$HEALTHY_ESTABLISHED" = earlier-record ]; then
    healthy_wait "$A" services-healthy "$HEALTHY_BOUND" "$STEP"
    rc=$?
else
    HEALTHY_REST=$((HEALTHY_BOUND - ($(uptime_s) - HEALTHY_ANCHOR_UP)))
    if [ "$HEALTHY_REST" -le 0 ]; then
        STACK_STATE=unknown
        stoprule healthy "stop rule reached: the stack with the candidate was not healthy within ${LIMIT} s of its start: the ${HEALTHY_BOUND} s left of the allowance at the containers record were spent before the wait could start"
        stopped_before_harness "$HEALTHY_WHERE" "stop rule reached: the stack with the candidate was not healthy within ${LIMIT} s of its start (what was left of the allowance from the candidate's start was spent before the wait could start; the wait was NOT started); the proof is recorded inconclusive by that rule"
    fi
    session_update "healthy_rule.acquisition_bound_s=$HEALTHY_REST"
    ex "$A" services-healthy bash -c "$(declare -f bounded)
bounded $HEALTHY_REST env E=\"\$2\" bash -c '. \"\$E/scripts/session_common.sh\" || { echo \"STOP: the session ssh helpers (\$E/scripts/session_common.sh) could not be loaded: NOTHING was run on the guest\" >&2; exit 97; }
gssh \"\$1\"' _ \"\$1\"" _ "$(healthy_wait_script "$HEALTHY_BOUND" "$STEP")" "$SESSION"
    rc=$?
    [ "$rc" -ne 255 ] || rc=$EXIT_NOT_REACHED
fi
if [ "$rc" -eq 0 ]; then
    # The first healthy observation - when it COMPLETED, never the sample's
    # start - is judged against start + limit (a late poll never resets the
    # allowance) unless the earlier record established it.
    ex "$A" healthy-rule-check "$PY" -c "$HEALTHY_RULE_PY" check "$EXPECT_SERVICES" "$ENVD/containers.before.txt" "$LIMIT" \
        "$(record_file services-healthy || true)" "$HEALTHY_ESTABLISHED"
    rc=$?
    [ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || capture_stop "$A" healthy-rule-check "the harness was NOT started"
    completed_upper=$(said healthy-rule-check 'completed_upper_elapsed_s=' | tr -d ' ')
    session_update "healthy_rule.first_healthy_utc=$(said healthy-rule-check 'first_healthy_utc=' | tr -d ' ')" \
        "healthy_rule.first_healthy_sample=$(said healthy-rule-check 'first_healthy_sample=' | tr -d ' ')" \
        "healthy_rule.first_healthy_completed_utc=$(said healthy-rule-check 'first_healthy_completed_utc=' | tr -d ' ')" \
        "healthy_rule.completed_upper_elapsed_s=${completed_upper:-null}" \
        "healthy_rule.elapsed_s=$(said healthy-rule-check 'elapsed_s=' | tr -d ' ')" \
        "healthy_rule.previous_sample_utc=$(said healthy-rule-check 'previous_sample_utc=' | tr -d ' ')" \
        "healthy_rule.previous_sample_span_s=$(said healthy-rule-check 'previous_sample_span_s=' | tr -d ' ')"
    instant_note_text=$(said healthy-rule-check 'first_healthy_instant_note=')
    [ -z "${instant_note_text// /}" ] || session_update "healthy_rule.first_healthy_instant_note=${instant_note_text% }"
    step_note_text=$(said healthy-rule-check 'clock_step_note=')
    [ -z "${step_note_text// /}" ] || session_update "healthy_rule.clock_step_note=${step_note_text% }"
    case "$rc" in
        0) STACK_STATE=healthy ;;
        1)
            # The 20-minute rule reached (a first healthy observation past
            # start + limit): a stop rule, so inconclusive, never not-run.
            STACK_STATE=healthy
            stoprule healthy "stop rule reached: the stack with the candidate was not healthy within ${LIMIT} s of its start:$(said healthy-rule-check 'HEALTHY RULE REACHED: ')"
            stopped_before_harness "$HEALTHY_WHERE" "stop rule reached: the stack with the candidate was first observed healthy beyond ${LIMIT} s of its start (healthy-rule-check exit 1); the proof is recorded inconclusive by that rule"
            ;;
        *)
            STACK_STATE=healthy
            not_run "the first stop rule cannot be established (healthy-rule-check exit $rc):$(said healthy-rule-check 'CANNOT BE ESTABLISHED: ')"
            ;;
    esac
elif [ "$rc" -eq 1 ] || [ "$rc" -eq 4 ]; then
    STACK_STATE=not-healthy
    if [ "$HEALTHY_ESTABLISHED" = earlier-record ]; then
        # The rule was established by the earlier record: this poll ran under
        # the full limit (as the restoration's does) as the precondition of a
        # healthy stack before the run, not as the allowance's remainder. A
        # stack no longer healthy fails that precondition; the rule is not
        # recorded reached by a poll that did not measure it (P-15).
        not_run "precondition failed: the stack with the candidate was not running and healthy when polled before the run (services-healthy exit $rc under the full ${LIMIT} s); the 20-minute rule was established by the earlier record named and this poll does not reach it, but the proof cannot start on a stack that is not healthy:$(said services-healthy 'NOT HEALTHY[^:]*:')"
    fi
    # The 20-minute rule reached (the stack not healthy within what was left
    # of the allowance from the candidate's start): a stop rule, so the
    # proof is recorded inconclusive, never not-run.
    stoprule healthy "stop rule reached: the stack was not running and healthy within the ${HEALTHY_BOUND} s left of ${LIMIT} s from the candidate's start:$(said services-healthy 'NOT HEALTHY[^:]*:')"
    stopped_before_harness "$HEALTHY_WHERE" "stop rule reached: the stack with the candidate was not running and healthy within ${LIMIT} s of its start (services-healthy exit $rc under the ${HEALTHY_BOUND} s left of that allowance); the proof is recorded inconclusive by that rule"
elif [ -n "$HEALTHY_REST" ] && { [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; }; then
    # The acquisition was ended by what was left of the allowance (F2b): no
    # sample had completed healthy within it - one still inspecting then,
    # an inspection that blocks included, observed nothing in time. The
    # 20-minute rule reached: inconclusive, never a pass, never not-run.
    # The state the guest was left in is what the last completed sample saw:
    # a service it positively saw not healthy (as the wait's own exit 1 or 4
    # reads it) leaves the stack not-healthy; no completed sample, or only
    # states that could not be read, leave it unknown.
    STACK_STATE=unknown
    last_sample=""
    if wait_record=$(record_file services-healthy); then
        last_sample=$(grep ' sample [0-9][0-9]*:' "$wait_record" | tail -n 1)
    fi
    for observed_state in ${last_sample#*:}; do
        case "$observed_state" in
            *=running/starting | *=running/unhealthy | *=running/none | *=absent/*) STACK_STATE=not-healthy ;;
            *=running/* | *=indeterminate/*) ;;
            *=*) STACK_STATE=not-healthy ;;
        esac
    done
    stoprule healthy "stop rule reached: the stack was not observed running and healthy within the ${HEALTHY_REST} s left of ${LIMIT} s from the candidate's start: the acquisition was ended by that remaining allowance (services-healthy exit $rc)${last_sample:+; the last sample completed: $last_sample}"
    stopped_before_harness "$HEALTHY_WHERE" "stop rule reached: the stack with the candidate was not running and healthy within ${LIMIT} s of its start (services-healthy was ended by the ${HEALTHY_REST} s left of that allowance, exit $rc: an inspection that had not answered by then observed nothing in time); the proof is recorded inconclusive by that rule"
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

# --- 9. ready, then pre: the first 'drained' starts here, and so does the attempt's clock ----
# A mandatory record that could not be made before the harness (the session
# facts not updated) is a prerequisite failed: the harness is not started
# for an attempt already known to be invalid (design 2.2).
[ "${#mandatory[@]}" -eq 0 ] || not_run "a mandatory record was not made before the harness: ${mandatory[0]}"
# /ready is waited for in a step of its own, BEFORE the attempt's clock
# starts: the 50-minute rule runs "after its first 'drained' starts" (ADR
# 0011), and the /ready wait (EGW_READY_LIMIT_S) is no part of it.
hx "$A" ready "wait_ready $READY_LIMIT"
ready_rc=$?
if [ "$ready_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" ready "the harness was NOT started"
elif [ "$ready_rc" -ne 0 ]; then
    not_run "$(step_note ready "$ready_rc" "precondition failed (/ready did not answer 200 within ${READY_LIMIT} s: ready exit $ready_rc)")"
fi
# T0 is taken immediately before the step whose first command is 'drained',
# and recorded as the instant the allowance runs from before that step runs.
# 'pre' itself runs under that allowance (live_hx: the whole of it, from
# T0): a spent allowance leaves it unstarted, and a 'pre' ended by
# 'timeout' is the rule reached during it (as the driver records it:
# whether 'drained' itself had begun inside the step is not what its status
# says). Either way a stop rule was reached, so the proof is recorded
# inconclusive, as the ADR's stop-rule text says ("If a stop rule is
# reached, the session stops and the proof is recorded inconclusive"); the
# harness is NOT started and the rule is recorded once, with the step.
# (Until these corrections the rule reached during 'pre', and then the rule
# reached before 'pre' could be dispatched, ended the attempt not-run,
# which contradicts that text: not-run is a prerequisite failed.)
T0=$(uptime_s)
T0_UTC=$(now_utc)
# The absolute deadline of the allowance on /proc/uptime, handed to the
# harness step, which computes its own bound from it after its preamble.
DEADLINE=$((T0 + ATTEMPT_LIMIT))
session_update "instants.first_drained_started_utc=$T0_UTC" "instants.first_drained_started_host_uptime_s=$T0"
[ "${#mandatory[@]}" -eq 0 ] || not_run "a mandatory record was not made before the harness: ${mandatory[0]}"
live_hx pre 'drained && metrics "$1" before && config_identity "$P/$1.config_identity.json"' "$RID"
pre_rc=$?
if [ "$pre_rc" -eq "$STEP_NOT_STARTED" ]; then
    stopped_before_harness "the 50-minute rule was reached before 'pre' could be dispatched" \
        "stop rule reached: the attempt's allowance of ${ATTEMPT_LIMIT} s was spent before 'pre' could start ('pre' was NOT started, so no 'drained' ran); the proof is recorded inconclusive by that rule"
elif [ "$pre_rc" -eq 124 ] || [ "$pre_rc" -eq 137 ]; then
    stopped_before_harness "the 50-minute rule was reached after the first 'drained' started and before the harness" \
        "stop rule reached: the attempt was stopped ${ATTEMPT_LIMIT} s after its first 'drained' started ('pre' was ended by 'timeout', exit $pre_rc); the proof is recorded inconclusive by that rule"
elif [ "$pre_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    rule_capture_stop pre
elif [ "$pre_rc" -ne 0 ]; then
    not_run "precondition failed (drained/metrics/identity: pre exit $pre_rc)"
fi
# The candidate on the guest must be the identified image: the configuration
# identity captured on the guest names its source commit, and a broker that
# reloaded its configuration is not the recorded one.
ex "$A" identity-check "$PY" -c '
import json, re, sys
path, expected = sys.argv[1], sys.argv[2]
doc = json.load(open(path, encoding="utf-8"))
commit = str(doc.get("controller_source_commit") or "")
reloaded = doc.get("broker_reloaded")
values = doc.get("broker_conf_values") if isinstance(doc.get("broker_conf_values"), dict) else {}
w = values.get("max_inflight_messages")
grace = doc.get("stop_grace_period")

def whole_seconds(text):
    """The compose duration the guest reported (130s, 2m10s, 1h) as whole
    seconds, or None when it is not that form: nothing is guessed."""
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", str(text or "").strip())
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + s

grace_s = whole_seconds(grace)
problems = []
if not (commit.startswith(expected) or expected.startswith(commit)) or len(commit) < 7:
    problems.append("controller_source_commit %r is not the expected %r" % (commit, expected))
if reloaded is not False:
    problems.append("broker_reloaded is %r, not false" % (reloaded,))
if not isinstance(w, int) or isinstance(w, bool) or w < 1:
    problems.append("broker_conf_values.max_inflight_messages (W) is %r, not a positive whole number" % (w,))
print("configuration identity: controller_source_commit=%s broker_reloaded=%s W=%s controller_image_id=%s stop_grace_period=%s stop_grace_period_s=%s paho=%s"
      % (commit, reloaded, w, doc.get("controller_image_id"), grace, "" if grace_s is None else grace_s, doc.get("paho_version")))
for p in problems:
    print("STOP: identity-check: " + p, file=sys.stderr)
sys.exit(1 if problems else 0)
' "$P/$RID.config_identity.json" "$EXPECTED_COMMIT"
rc=$?
[ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || rule_capture_stop identity-check
[ "$rc" -eq 0 ] || not_run "the candidate on the guest is not the identified image (identity-check exit $rc: expected source commit $EXPECTED_COMMIT and broker_reloaded false)"
identity_value() { said identity-check '' | tr ' ' '\n' | sed -n "s/^$1=//p" | head -n 1; }
W=$(identity_value W)
# The controller's stop_grace_period, the value the guest reported, as whole
# seconds: the extension's first per-step stop rule ("the restart command
# within the grace period plus 5 minutes") is bounded from it. Not readable
# as seconds, it is recorded null and only the extension is kept from running.
GRACE_S=$(identity_value stop_grace_period_s)
session_update "values.W=$W" "values.stop_grace_period_s=${GRACE_S:-null}" \
    "identity.controller_source_commit=$(identity_value controller_source_commit)" "identity.stop_grace_period=$(identity_value stop_grace_period)"

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
# The remainder is checked before the step is dispatched, as for every live
# step, and it is preceded by 'tunnel-ready' (10a below), a live step that
# loads the 6.1 preamble under the bound with a trivial body. The harness
# step itself - its OWN 6.1 preamble, the one that actually precedes the
# harness, and its body together - runs under 'bounded' of the positive
# remainder checked just before it is dispatched (F2a): the preamble is
# handed to the bounded shell as the value of EGW_HOST_PRE and loaded there
# with 'eval', as hx_bounded loads it, and the body - its text pinned to the
# runbook's harness_cmd, with single quotes that hx_bounded's text cannot
# hold - as the shell's first argument, run with 'eval' after it. A tunnel
# that drops after 'tunnel-ready' and whose reopening blocks is therefore
# ended by the allowance (124, or 137 after the grace) before the harness
# starts: the rule is recorded as reached during 'harness-run', and neither
# the harness nor its fault is started. The harness step is dispatched
# only when 'tunnel-ready' ended 0 and something of the allowance is still
# left; and only AFTER its own preamble it computes the harness's own bound
# from the absolute deadline handed to it (T0 + EGW_PROOF_ATTEMPT_LIMIT_S
# on /proc/uptime), so that a preamble that took its time is charged to the
# allowance and never followed by a harness under a stale remainder: with
# nothing left then the harness (and its fault hook) is NOT started, the
# step answers STEP_NOT_STARTED and the rule is recorded as reached before
# 'harness-run'. The step prints the harness's own start instant, taken on
# both clocks immediately before it starts, and the bound it runs under,
# which are what the session facts record (not the dispatch instant); a
# step ended before it printed that start never started the harness.
# 'timeout' bounds the harness by that remainder (a spent allowance is never
# 'timeout 0', which would disable the bound); 124 (or 137, when the kill
# after the grace was needed) is the stop rule reached. The harness's
# exit 1 is read from the manifest afterwards, where the eligibility step
# admits it only as E-12 states. The step runs the harness through
# 'bounded', inside the step's own 'bounded', so that the driver's
# interrupt reaches it (each 'bounded' forwards INT and TERM to its
# 'timeout', which passes them on to its command and that command's group;
# the harness has no handler of its own: the interrupt ends it where it is,
# its restart timer - a daemon thread - with it; a hook already running in a
# session of its own, run.py execute_collector_hook, ends on its own). The
# hook templates are split by the harness without a shell (shlex.split), so
# the hook path and "{dest}" are double-quoted in each of them, as the
# runbook's harness_cmd quotes its own "{dest}": a results base with a space
# in its path would otherwise break every hook.
[ "${#mandatory[@]}" -eq 0 ] || not_run "a mandatory record was not made before the harness: ${mandatory[0]}"
HARNESS_STARTED=1
# The fault mutates the stack from here on: its state is unknown until the
# restoration reads it back.
STACK_STATE=unknown
# --- 10a. tunnel-ready: the 6.1 preamble under the bound, just before the harness ---
# It shares the check made before the harness is dispatched (one remainder,
# LIVE_REST) and runs under it through hx_bounded, as the live host steps
# do. Ended by 'timeout' (124, 137), the rule is reached during it: the
# harness is not dispatched, and the attempt goes on as for an allowance
# spent before the harness (no harness, no fault; the restoration and the
# offline work still run; inconclusive). Ended 0, the remainder is checked
# again before the harness step is dispatched. Any other ending - the
# preamble could not be loaded (97), or the step's console capture was lost
# (74) - leaves the tunnel not known to be up, so the harness step is NOT
# dispatched either: an evidence requirement not met (the harness not
# started), never not-run once the harness block is entered, as a harness
# step whose own preamble failed never was. The step is not an observation
# of the system, so it is not listed with the observations not made.
HARNESS_GO=0
TUNNEL_READY_RC=not-started
TUNNEL_READY_BOUND=null
if live_start harness-run; then
    TUNNEL_READY_BOUND=$LIVE_REST
    hx_bounded tunnel-ready "$LIVE_REST" 'echo "tunnel-ready: the host preamble of runbook 6.1 (the venv, the secrets, the helpers and the tunnels) is loaded within the allowance"'
    TUNNEL_READY_RC=$?
    case "$TUNNEL_READY_RC" in
        0)
            # Checked again: the preamble took its share of the allowance.
            live_start harness-run && HARNESS_GO=1
            ;;
        124 | 137)
            attempt_reached during tunnel-ready "$TUNNEL_READY_RC"
            echo "STOP: the host preamble of runbook 6.1 did not load within the attempt's allowance (tunnel-ready exit $TUNNEL_READY_RC): the harness was NOT started" >&2
            ;;
        "$EXIT_CAPTURE_LOST")
            mandatory+=("$(capture_note tunnel-ready); whether the tunnels answered just before the harness is not known, so the harness was NOT started")
            ;;
        *)
            missed "$(step_note tunnel-ready "$TUNNEL_READY_RC" "the host preamble of runbook 6.1 could not be loaded just before the harness (tunnel-ready exit $TUNNEL_READY_RC), so the harness step was NOT dispatched: the harness was NOT started")"
            ;;
    esac
fi
session_update "instants.tunnel_ready_exit=$(json_scalar "$TUNNEL_READY_RC")" "instants.tunnel_ready_allowance_s=$TUNNEL_READY_BOUND"
if [ "$HARNESS_GO" -eq 1 ]; then
    HARNESS_DISPATCHED_UTC=$(now_utc)
    HARNESS_STEP_BOUND=$LIVE_REST
    HARNESS_STARTED_UTC=""
    ex "$A" harness-run env EGW_HOST_PRE="$HOST_PRE" bash -c "$(declare -f bounded)
bounded $HARNESS_STEP_BOUND bash -c '{ eval \"\$EGW_HOST_PRE\" ; } || { echo \"STOP: the host preamble of runbook 6.1 (the venv, the secrets, the helpers and the tunnels) could not be loaded: the step never ran\" >&2; exit 97; }
eval \"\$1\"' _ \"\$1\"" _ "$(declare -f proof_harness_args)
$(declare -f bounded)
proof_harness_args '$RID' '$PLAN' '$BASE' '$ENVD/sut_environment.json'
read -r HARNESS_UP _ < /proc/uptime
HARNESS_UP=\${HARNESS_UP%.*}
HARNESS_LEFT=\$(($DEADLINE - HARNESS_UP))
if [ \"\$HARNESS_LEFT\" -le 0 ]; then
    echo \"STOP: the attempt's allowance of $ATTEMPT_LIMIT s from its first 'drained' was spent when the host preamble of this step had loaded (deadline $DEADLINE s on /proc/uptime, now \$HARNESS_UP s): the harness was NOT started\" >&2
    exit $STEP_NOT_STARTED
fi
echo \"harness_started_utc=\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
echo \"harness_started_host_uptime_s=\$HARNESS_UP\"
echo \"harness_allowance_s=\$HARNESS_LEFT\"
bounded \"\$HARNESS_LEFT\" python -m egw_experiments run \"\${HARNESS_ARGS[@]}\" --restart-cmd 'bash \"$DRIVERS/proof_restart_controller.sh\" {run_id}' --restart-at-s $RESTART_AT --config-identity-from '$P/$RID.config_identity.json' --twin-snapshot-cmd 'bash \"$DRIVERS/proof_hook_twins.sh\" {run_id} \"{dest}\" $SEED' --drain-cmd 'bash \"$DRIVERS/proof_hook_drained.sh\" {run_id}' --post-drain-fetch-cmd 'scp -q egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl \"{dest}\"' --fetch-broker-log-cmd 'bash \"$DRIVERS/proof_fetch_sut_log.sh\" broker \"{dest}\" $GUEST_EPOCH' --fetch-controller-log-cmd 'bash \"$DRIVERS/proof_fetch_sut_log.sh\" controller \"{dest}\" $GUEST_EPOCH' --fetch-docker-events-cmd 'bash \"$DRIVERS/proof_fetch_sut_log.sh\" docker-events \"{dest}\" $GUEST_EPOCH'"
    h_rc=$?
    HARNESS_ENDED_UTC=$(now_utc)
    # What the step itself printed immediately before the harness started:
    # nothing when it did not start (the preamble failed, it was ended by
    # the bound, or the allowance was spent after it).
    HARNESS_STARTED_UTC=$(said harness-run 'harness_started_utc=' | tr -d ' ')
    HARNESS_STARTED_UP=$(said harness-run 'harness_started_host_uptime_s=' | tr -d ' ')
    HARNESS_LEFT=$(said harness-run 'harness_allowance_s=' | tr -d ' ')
    case "$HARNESS_STARTED_UP$HARNESS_LEFT" in '' | *[!0-9]*) HARNESS_STARTED_UP="" HARNESS_LEFT="" ;; esac
    if [ -z "$HARNESS_STARTED_UTC" ] && { [ "$h_rc" -eq "$STEP_NOT_STARTED" ] || [ "$h_rc" -eq 124 ] || [ "$h_rc" -eq 137 ]; }; then
        # The harness, and with it the fault, was NOT started: the allowance
        # was spent when the step's preamble had loaded (98: the rule
        # reached before 'harness-run'), or the step's bound ended it before
        # the harness started - its preamble included (124, 137: the rule
        # reached during 'harness-run'). Recorded once, either way.
        if [ "$h_rc" -eq "$STEP_NOT_STARTED" ]; then
            attempt_reached before harness-run
            echo "STOP: no time left in the attempt's allowance after the harness step's preamble: the harness was NOT started" >&2
        else
            attempt_reached during harness-run "$h_rc"
            echo "STOP: the harness step, its host preamble of runbook 6.1 included, was ended by the attempt's allowance (exit $h_rc) before the harness started: the harness was NOT started" >&2
        fi
        session_update "instants.harness_step_dispatched_utc=$HARNESS_DISPATCHED_UTC" "instants.harness_step_allowance_s=$HARNESS_STEP_BOUND" \
            "instants.harness_step_exit=$h_rc" "instants.harness_started_utc=null" \
            "instants.harness_ended_utc=null" "instants.harness_exit=null" "instants.harness_allowance_s=0"
        h_rc=not-started
    else
        session_update "instants.harness_step_dispatched_utc=$HARNESS_DISPATCHED_UTC" "instants.harness_step_allowance_s=$HARNESS_STEP_BOUND" \
            "instants.harness_step_exit=$h_rc" \
            "instants.harness_started_utc=${HARNESS_STARTED_UTC:-null}" "instants.harness_started_host_uptime_s=${HARNESS_STARTED_UP:-null}" \
            "instants.harness_ended_utc=$HARNESS_ENDED_UTC" "instants.harness_exit=$h_rc" "instants.harness_allowance_s=${HARNESS_LEFT:-null}"
        # 124 or 137 is the rule reached during the harness step; an
        # allowance spent when it ended is the rule reached then: either way
        # no further proof step starts, and the run directory is kept as it
        # is.
        live_end harness-run "$h_rc" || true
    fi
else
    # No harness step ran, so no step is recorded: the one stop rule
    # reached (recorded by live_start, or during 'tunnel-ready'), or the
    # preamble not loaded just before it (recorded above).
    h_rc=not-started
    harness_allowance=null
    if [ "$ATTEMPT_REACHED" -eq 1 ]; then
        harness_allowance=0
        echo "STOP: no time left in the attempt's allowance: the harness was NOT started" >&2
    else
        echo "STOP: the host preamble of runbook 6.1 was not known to be loaded just before the harness (tunnel-ready exit $TUNNEL_READY_RC): the harness was NOT started" >&2
    fi
    session_update "instants.harness_started_utc=null" "instants.harness_ended_utc=null" "instants.harness_exit=null" "instants.harness_allowance_s=$harness_allowance"
fi
case "$h_rc" in
    0 | 1 | not-started | 124 | 137) ;;
    "$EXIT_CAPTURE_LOST") mandatory+=("$(capture_note harness-run)") ;;
    *) missed "$(step_note harness-run "$h_rc" "the harness run exited $h_rc (2 is a refusal: usage, plan or identity)")" ;;
esac

# --- 10b. the eligibility of the run, from the manifest (F1, P-16) -----------------
# Offline (the manifest and the files the harness wrote), so not under the
# bound; run only for a harness that ended 0 or 1. The harness validity is
# read by the evaluator's own harness_admission (E-12), imported from the
# clean clone. The reading goes into the session facts before the
# evaluator runs, beside the harness exit.
#
# amend_expected_artefacts COLLECTOR SEAL_WITHHELD: in the sampling-gap form
# E-12 admits (the eligibility step names the collector file the ingest
# rejected), the package's declared artefacts follow the inventory the
# evaluator applies to that form: the collector file where the admission
# names it in the place of resources.csv, which the harness never writes in
# it, and no SHA256SUMS when the harness withheld it for that alone
# (SEAL_WITHHELD 'yes'). The declaration is amended on the attempt with what
# was changed and why (expected_artefacts_amended); one that cannot be
# amended is a record not made (mandatory).
amend_expected_artefacts() {
    local pairs=()
    mapfile -t pairs < <("$PY" - "$EXPECTED_ARTEFACTS" "$1" "$2" 2> /dev/null <<'PYEOF'
import json, sys
declared, collector, withheld = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3] == "yes"
amended = ["raw/*/" + collector if entry == "raw/*/resources.csv" else entry
           for entry in declared if not (withheld and entry == "raw/*/SHA256SUMS")]
note = {
    "rule": "E-12 (egw_experiments.proof_evaluator.harness_admission, form sampling-gap-only)",
    "replaced": {"raw/*/resources.csv": "raw/*/" + collector},
    "dropped": ["raw/*/SHA256SUMS"] if withheld else [],
    "reason": "the harness never writes resources.csv when its ingest rejects the collector file, which it keeps at %s%s;"
              " the evaluator's inventory takes the same file in that form (E-11, E-12)"
              % (collector, ", and it withholds SHA256SUMS while that mandatory artefact is missing" if withheld else ""),
}
print("expected_artefacts=" + json.dumps(amended))
print("expected_artefacts_amended=" + json.dumps(note))
PYEOF
)
    [ "${#pairs[@]}" -eq 2 ] && (cd "$REPO/src" && $LE set --attempt "$A" "${pairs[@]}") > /dev/null 2>&1 \
        || missed "the declared artefacts could not be amended for the sampling-gap form (E-12): the package would be read against resources.csv and SHA256SUMS, which the harness never writes in it"
}
session_update "harness_exit=$(json_scalar "$h_rc")"
case "$h_rc" in
    0 | 1)
        ex "$A" eligibility env PYTHONPATH="$REPO/src" "$PY" -c "$ELIGIBILITY_PY" "$RAWD" "$h_rc"
        elig_rc=$?
        ELIG_FACTS=$(said eligibility 'eligibility=')
        [ -z "${ELIG_FACTS// /}" ] || session_update "eligibility=$ELIG_FACTS"
        GAP_COLLECTOR=$(said eligibility 'sampling_gap_collector_file=' | tr -d ' ')
        [ -z "$GAP_COLLECTOR" ] \
            || amend_expected_artefacts "$GAP_COLLECTOR" "$(said eligibility 'sampling_gap_seal_withheld=' | tr -d ' ')"
        case "$elig_rc" in
            0) ;;
            "$EXIT_CAPTURE_LOST") mandatory+=("$(capture_note eligibility)") ;;
            *) missed "the proof's execution or evidence is incomplete (eligibility exit $elig_rc, P-16):$(said eligibility 'NOT ELIGIBLE: ')" ;;
        esac
        ;;
    *)
        session_update "eligibility={\"complete\": false, \"harness_exit\": $(json_scalar "$h_rc"), \"problems\": [\"the harness run did not complete (exit $h_rc), so the manifest was not read for the eligibility of the run\"]}"
        ;;
esac

# --- 11. the restart shown, from this driver's own records ---------------------------
# An issued command is not a restart: the controller PROCESS must be new
# (started_at differs) and the container OBJECT the same, started later (a
# kill + start keeps the object; a new id is a replacement, not the fault the
# proof issued). Not shown -> the fault was not applied: mandatory. The two
# readings it rests on are live observations under the attempt's allowance
# (live_*): after the rule was reached none is started (STEP_NOT_STARTED,
# listed among the observations not made), and one ended by 'timeout' is
# the rule reached during it, never an instrument failure of its own. The
# check itself is an offline comparison of those records (restart-shown:
# it acquires no live observation), so it runs whenever both were taken
# whole - after an expiry too, since offline analysis may finish then and
# a replacement the complete records show must be judged - and is not run
# (listed with the observations not made) when the rule kept one of them
# from being taken whole.
live_hx controller-process-after '_mline'
cpa_rc=$?
STARTED_AFTER=""
if [ "$cpa_rc" -eq 0 ] || [ "$cpa_rc" -eq 3 ]; then
    STARTED_AFTER=$(last_line controller-process-after | cut -d' ' -f5)
elif cut_by_rule "$cpa_rc"; then
    :
elif [ "$cpa_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    mandatory+=("$(capture_note controller-process-after)")
else
    missed "$(step_note controller-process-after "$cpa_rc" "the controller process could not be read after the run (_mline exit $cpa_rc)")"
fi
live_gx containers-after "$(containers_script)"
ca_rc=$?
if cut_by_rule "$ca_rc"; then
    :
elif [ "$ca_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    mandatory+=("$(capture_note containers-after)")
elif [ "$ca_rc" -ne 0 ]; then
    missed "$(step_note containers-after "$ca_rc" "the containers' ids and start instants were not recorded after the run (containers-after exit $ca_rc)")"
fi
[ "$ca_rc" -eq "$STEP_NOT_STARTED" ] || keep_record containers-after containers.after.txt "the containers after the run" || true
# Exit 1 is NOT SHOWN only with the line that says so; a record that
# could not be read, or a failure of the check itself, is NOT JUDGED (2),
# as guest_state_delta.py keeps its own crash apart from a fault.
if cut_by_rule "$cpa_rc" || cut_by_rule "$ca_rc"; then
    # A reading it compares was not taken, or only in part, because the
    # attempt's stop rule was reached: nothing is compared.
    not_started+=(restart-shown)
    shown_rc=$STEP_NOT_STARTED
else
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

def judge():
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
        return 2
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
        return 1
    print("RESTART SHOWN: the controller process is new (%s, then %s) and its container is the same object (%s), started later (%s, then %s)"
          % (before_started, after_started, old_id[:12], old_started, new_started))
    return 0

try:
    sys.exit(judge())
except SystemExit:
    raise
except Exception as exc:  # a record that could not be read is no judgement
    print("NOT JUDGED: the records could not be read or compared: %s: %s" % (type(exc).__name__, exc))
    sys.exit(2)
' "$STARTED_BEFORE" "$STARTED_AFTER" "$ENVD/containers.before.txt" "$ENVD/containers.after.txt" "$CONTROLLER"
    shown_rc=$?
fi
case "$shown_rc" in
    0) RESTART_SHOWN=yes ;;
    1)
        if [ -n "$(said restart-shown 'NOT SHOWN:')" ]; then
            RESTART_SHOWN=no
            missed "the restart was not shown - the fault was not applied:$(said restart-shown 'NOT SHOWN:')"
        else
            missed "the restart was not shown: the check ended 1 without saying what was not shown (restart-shown exit 1), so it could not be judged from the records"
        fi
        ;;
    "$STEP_NOT_STARTED") ;;
    "$EXIT_CAPTURE_LOST") mandatory+=("$(capture_note restart-shown)") ;;
    *) missed "the restart was not shown: it could not be judged from the records (restart-shown exit $shown_rc):$(said restart-shown 'NOT JUDGED:')" ;;
esac
set_field "restart_shown=$RESTART_SHOWN"
RESTART_SHOWN_JSON=null
[ "$RESTART_SHOWN" != yes ] || RESTART_SHOWN_JSON=true
[ "$RESTART_SHOWN" != no ] || RESTART_SHOWN_JSON=false
session_update "restart_shown=$RESTART_SHOWN_JSON" "restart_shown_detail=$(said restart-shown 'RESTART SHOWN: ')$(said restart-shown 'NOT SHOWN: ')$(said restart-shown 'NOT JUDGED: ')"

# --- 12. the /metrics reading after, and the runbook's delta on the post-drain copy ---
live_hx metrics-after 'metrics "$1" after' "$RID"
rc=$?
case "$rc" in
    0 | "$STEP_NOT_STARTED" | 124 | 137) ;;
    *) post_window metrics-after "$rc" "the /metrics reading after the run was not taken" || true ;;
esac
# 'delta' compares the twins with the post-drain copy sealed in the run
# directory (runbook test 6): 0 and 4 are both RESULTS (a named N1 case
# gives 4 by exactly one; the evaluator applies S5's tolerance, design
# flag P-9); anything else is no comparison. The helper's $REC and $P are
# the inner shell's, after it loads the helper file; the run directory and
# the run id are its arguments.
live_hx delta '$REC delta "$1" --prefix "$P/$2" --events "$1/events.post-drain.jsonl"' "$RAWD" "$RID"
delta_rc=$?
case "$delta_rc" in
    0 | 4 | 124 | 137) ;;
    "$STEP_NOT_STARTED") delta_rc=not-started ;;
    *) post_window delta "$delta_rc" "the runbook's delta over the post-drain copy did not run" || true ;;
esac

# --- 13. the prefix snapshots into the package -------------------------------------
# The ONLY path by which the configuration identity, the two /metrics
# readings, the two twin snapshots and the restart record reach the package
# under analysis/ (they are also registered as simulator siblings).
if mkdir -p "$SNAPS" && cp "$P/$RID".* "$SNAPS/"; then
    ls -l "$SNAPS/"
else
    missed "the prefix snapshots ($RID.*) were not copied into the package"
fi

# --- 14. the guest state after, against the state before (nominal.sh) ---------------
# The record after is a live observation under the allowance; the delta is
# an offline comparison of the two records already taken
# (guest_state_delta.py reads two files and acquires nothing live): it runs
# whenever the record after was taken whole - after an expiry too, since an
# OOM kill or a replacement the complete record shows must be judged - and
# is not run (listed with the observations not made) when the rule kept
# that record from being taken, or cut it short.
live_gx guest-state-after "$GUEST_STATE"
after_rc=$?
after_trusted=1
[ "$after_rc" -eq "$EXIT_CAPTURE_LOST" ] && after_trusted=0
if cut_by_rule "$after_rc"; then
    # The stop rule (recorded): not started, or a partial record nothing is
    # read from.
    after_trusted=0
elif [ "$after_rc" -ne 0 ]; then
    mandatory+=("$(step_note guest-state-after "$after_rc" "the guest state after the run was not recorded")")
fi
AFTER=""
cut_by_rule "$after_rc" || AFTER=$(ls "$A"/console/*-guest-state-after.stdout.txt 2> /dev/null | tail -n 1)
if cut_by_rule "$after_rc"; then
    not_started+=(guest-state-delta)
elif [ -n "$AFTER" ]; then
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

# --- 15. the restoration: the stack running and healthy again ------------------------
restore

# --- 16. the session facts with the restoration observed, then the evaluator ----------
# The evaluator runs only after the restoration: the verdict document is
# write-once and its restoration section is the echo of what the driver
# observed (it decides nothing there), so an evaluation before the wait
# would leave 'stack=unknown' in every session's record.
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
        missed "the proof was not evaluated (evaluate exit $v_rc): $(evaluator_said)"
        ;;
esac
set_field "proof_verdict=$EVALUATOR_RESULT"
# What the verdict document says: whether the proof's evidence is complete
# (the attempt's validity rests on it), the harness's own validity quoted as
# recorded with the form E-12 admitted it in, and the criteria that failed,
# the refutations and the inconclusive reasons for the reason text. A
# document that cannot be read leaves the evidence NOT complete.
V=$("$PY" - "$VERDICT" 2> /dev/null <<'PYEOF' || echo "false|the verdict document analysis/proof_verdict.json could not be read|"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
inst = d.get("instrumentation") or {}
ev = inst.get("proof_evidence") or {}
complete = ev.get("complete") is True
reasons = inst.get("harness_validity_reasons") or []
admission = inst.get("harness_admission") if isinstance(inst.get("harness_admission"), dict) else {}
harness = "manifest validity %s%s kept as recorded, admitted for the proof only as E-12 states (harness_admission form %s)" % (
    inst.get("harness_validity"), (" (" + "; ".join(str(r) for r in reasons) + ")") if reasons else "",
    repr(admission["form"]) if "form" in admission else "not recorded")
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

# --- 17. the optional extension (ADR 0011 item 4 section 9), only when asked ------------
# One more kill + start under the same client id and persistent session, then
# 'wait_ready' and one /metrics reading (the restart shown against the
# started_at the driver read after the run), 'drained' with nothing
# published, one more /metrics reading after it and a second post-drain
# fetch. It changes the proof's plan, so it is the student's decision
# (EGW_PROOF_EXTENSION=yes); its result is recorded APART, in
# proof_session.json.extension and on the attempt, and never changes the
# proof's three verdicts. Refutes the assumption if the new process received
# anything with nothing published (received > 0 in the reading after its
# 'drained') or an identity gained its first outcome line after the first
# quiet window; inconclusive if the restart is not shown, /ready is not
# reached, 'drained' reaches its limit, a fetch fails, its own ceiling
# (EGW_PROOF_EXTENSION_LIMIT_S) or one of the ADR's two per-step stop rules
# is reached (ext_step above: the restart command within the grace period
# plus 5 minutes, the second fetch within 5 minutes), or it could not be run
# at all (a stop rule of the proof reached, the attempt's allowance spent
# before it could start, the stack not healthy again, no post-drain copy to
# compare with, no baseline started_at read after the run to show its
# restart against, no grace period read to bound its restart by): chosen,
# it is never recorded as not chosen.
ext_blockers=()
if [ "$EXTENSION" = yes ]; then
    EXTENSION_RESULT=inconclusive
    ext_reasons=()
    EXT_RESTART_LIMIT=null
    [ -z "${GRACE_S:-}" ] || EXT_RESTART_LIMIT=$((GRACE_S + 300))
    if [ "${#stoprules[@]}" -ne 0 ]; then
        ext_blockers+=("a stop rule of the proof was reached")
    elif [ "$(left)" -le 0 ]; then
        # The attempt's allowance ran out after the proof's last live
        # observation - during the restoration or the evaluation, which are
        # never bounded - so no live step recorded it: the extension's kill
        # + start (a fault step) and its live readings must still not start
        # after it (P-10). It is the extension's reason, not a stop rule of
        # the proof, whose live observations all ended in time.
        ext_blockers+=("the attempt's allowance of ${ATTEMPT_LIMIT} s from its first 'drained' was spent before the extension could start (after the proof's live observations had ended in time, during the restoration or the evaluation), and no fault step or live reading starts after it")
    fi
    [ "$STACK_STATE" = healthy ] || ext_blockers+=("the stack was not running and healthy again after the run (stack=$STACK_STATE)")
    [ -s "$RAWD/events.post-drain.jsonl" ] || ext_blockers+=("the run directory holds no post-drain copy of the events to compare with")
    # The restart cannot be shown without its baseline: the started_at read
    # after the run (controller-process-after), a mandatory record of the
    # proof whose absence does not stop the driver but leaves the extension
    # nothing to compare its own reading with - any reading would differ
    # from an empty one.
    [ -n "$STARTED_AFTER" ] || ext_blockers+=("the restart cannot be shown: no baseline started_at was read after the run (controller-process-after)")
    [ "$EXT_RESTART_LIMIT" != null ] || ext_blockers+=("the stop rule '$EXT_RULE_RESTART' cannot be bounded: the configuration identity's stop_grace_period was not read as whole seconds")
    session_update "extension.chosen=true" "extension.limit_s=$EXTENSION_LIMIT" "extension.result=$EXTENSION_RESULT" \
        "extension.stop_rules=[{\"id\": \"ext-restart\", \"rule\": \"$EXT_RULE_RESTART\", \"limit_s\": $EXT_RESTART_LIMIT, \"grace_period_s\": ${GRACE_S:-null}}, {\"id\": \"ext-fetch\", \"rule\": \"$EXT_RULE_FETCH\", \"limit_s\": $EXT_FETCH_LIMIT}]"
    if [ "${#ext_blockers[@]}" -ne 0 ]; then
        ext_reasons+=("the extension was not run: $(printf '%s; ' "${ext_blockers[@]}")")
        session_update "extension.ran=false" "extension.reasons=$(printf '%s; ' "${ext_reasons[@]}")"
    fi
fi
if [ "$EXTENSION" = yes ] && [ "${#ext_blockers[@]}" -eq 0 ]; then
    EXT_T0=$(uptime_s)
    session_update "extension.ran=true" "extension.started_utc=$(now_utc)"
    ext_ok=1
    if ext_spent ext-restart; then
        ext_ok=0
    else
        # The second kill + start mutates the stack again: its state is
        # unknown until the restoration reads it back, and an interrupt from
        # here on runs that reading before the ending names the state; that
        # restoration is the extension's own, recorded apart (EXT_RESTORE).
        RESTORED=0
        STACK_STATE=unknown
        EXT_RESTORE=1
        ext_step ext-restart "$EXT_RESTART_LIMIT" "$EXT_RULE_RESTART" "bash '$DRIVERS/proof_restart_controller.sh' '$RID.extension'"
        rc=$?
        if ext_cut ext-restart "$rc"; then
            ext_ok=0
        elif [ "$rc" -ne 0 ]; then
            ext_ok=0
            ext_reasons+=("the second kill + start was not issued cleanly (ext-restart exit $rc)")
        fi
    fi
    EXT_RECEIVED=""
    if [ "$ext_ok" -eq 1 ] && ! ext_spent ext-ready; then
        ext_step ext-ready "" "" "bash -c '. \"\$HOME/egw-tcg/itest-helpers.sh\" && wait_ready $READY_LIMIT && _mline'"
        rc=$?
        if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
            EXT_LINE=$(last_line ext-ready)
            EXT_STARTED=$(printf '%s' "$EXT_LINE" | cut -d' ' -f5)
            EXT_RECEIVED_READY=$(printf '%s' "$EXT_LINE" | cut -d' ' -f7)
            # Shown only against the recorded baseline (the started_at read
            # after the run), never against an empty one.
            if [ -z "$STARTED_AFTER" ]; then
                ext_ok=0
                ext_reasons+=("the extension's restart cannot be shown: no baseline started_at was read after the run")
            elif [ -z "$EXT_STARTED" ] || [ "$EXT_STARTED" = "$STARTED_AFTER" ]; then
                ext_ok=0
                ext_reasons+=("the extension's restart is not shown (started_at '$EXT_STARTED' after, '$STARTED_AFTER' before it)")
            fi
            session_update "extension.started_at_after=$EXT_STARTED" "extension.received_after_ready=${EXT_RECEIVED_READY:-null}"
        elif ext_cut ext-ready "$rc"; then
            ext_ok=0
        else
            ext_ok=0
            ext_reasons+=("/ready was not reached, or the controller process was not read, after the second kill + start (ext-ready exit $rc)")
        fi
    fi
    if [ "$ext_ok" -eq 1 ] && ! ext_spent ext-drained; then
        ext_step ext-drained "" "" "bash '$DRIVERS/proof_hook_drained.sh' '$RID'"
        rc=$?
        if ext_cut ext-drained "$rc"; then
            ext_ok=0
        elif [ "$rc" -ne 0 ]; then
            ext_ok=0
            ext_reasons+=("the extension's 'drained' did not report a quiet window (ext-drained exit $rc)")
        fi
    fi
    # The reading that decides 'received': after the extension's 'drained'
    # (ADR 0011: one more 'drained' with nothing published, then one /metrics
    # reading), so that a redelivery arriving during the quiet window counts.
    if [ "$ext_ok" -eq 1 ] && ! ext_spent ext-metrics; then
        ext_step ext-metrics "" "" "bash -c '. \"\$HOME/egw-tcg/itest-helpers.sh\" && _mline'"
        rc=$?
        if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
            EXT_RECEIVED=$(last_line ext-metrics | cut -d' ' -f7)
            session_update "extension.received_after_drained=${EXT_RECEIVED:-null}"
        elif ext_cut ext-metrics "$rc"; then
            ext_ok=0
        else
            ext_ok=0
            ext_reasons+=("the controller process was not read after the extension's 'drained' (ext-metrics exit $rc)")
        fi
    fi
    if [ "$ext_ok" -eq 1 ] && ! ext_spent ext-fetch; then
        ext_step ext-fetch "$EXT_FETCH_LIMIT" "$EXT_RULE_FETCH" "scp -q 'egw-tcg:/opt/egw/deployment/data/events/$RID/events.jsonl' '$ANALYSIS/events.post-extension.jsonl' && wc -l '$ANALYSIS/events.post-extension.jsonl'"
        rc=$?
        if ext_cut ext-fetch "$rc"; then
            ext_ok=0
        elif [ "$rc" -ne 0 ] || [ ! -s "$ANALYSIS/events.post-extension.jsonl" ]; then
            ext_ok=0
            ext_reasons+=("the post-extension copy of the events was not fetched (ext-fetch exit $rc)")
        fi
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
            '' | *[!0-9]*)
                ext_reasons+=("the extension's readings could not be compared (new outcome lines '$EXT_NEW', received '$EXT_RECEIVED')")
                ;;
            *)
                if [ "$EXT_RECEIVED" -gt 0 ] || [ "$EXT_NEW" -gt 0 ]; then
                    EXTENSION_RESULT=refutes
                    ext_reasons+=("the new process received $EXT_RECEIVED delivery(ies) with nothing published (the /metrics reading after its 'drained'), and $EXT_NEW identity(ies) gained a first outcome line after the first quiet window")
                else
                    EXTENSION_RESULT=not-refuted
                    ext_reasons+=("the new process received nothing (the /metrics reading after its 'drained') and no identity gained a first outcome line after the first quiet window")
                fi
                ;;
        esac
        session_update "extension.new_outcome_lines=${EXT_NEW}"
    fi
    # The extension's own restart record (write-once, $RID.extension.restart.txt)
    # into the package beside the proof's snapshots; it is also a simulator
    # sibling. Not reaching it is noted with the extension, never with the proof.
    if compgen -G "$P/$RID.extension.*" > /dev/null; then
        cp "$P/$RID.extension".* "$SNAPS/" 2> /dev/null \
            || ext_reasons+=("the extension's restart record ($RID.extension.restart.txt) was not copied into analysis/snapshots/")
    fi
    session_update "extension.result=$EXTENSION_RESULT" "extension.ended_utc=$(now_utc)" "extension.reasons=$(printf '%s; ' "${ext_reasons[@]}")"
    # The stack must be running and healthy again after the second restart
    # too (RESTORED was reset when the kill + start was dispatched).
    restore
fi
set_field "extension=$EXTENSION_RESULT"

# --- 18. the three verdicts, never merged ----------------------------------------------
# The live observations not made after the attempt's stop rule was reached
# are recorded as incomplete, by name, in the order they would have run.
if [ "${#not_started[@]}" -ne 0 ]; then
    skipped=""
    for name in "${not_started[@]}"; do
        skipped="${skipped:+$skipped, }$name"
    done
    incomplete+=("not run after the attempt's stop rule was reached (no further proof step starts): $skipped")
    session_update "instants.not_started_after_stop_rule=$skipped"
fi
# Instrumentation validity: no mandatory record missing AND the proof's
# evidence complete (the harness's own validity is quoted as recorded and
# admitted only as E-12 states; P-16: the eligibility of the run is a
# mandatory reading of its own).
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
# The next action follows the attempt's FINAL verdicts - the validity, the
# outcome and the restoration, after every downgrade above - never the
# evaluator's raw result, which stays visible in the reason as the
# component it is (R1, P-17): a supporting component result downgraded by
# an unshown restart, an incomplete restoration, a stop rule, a missing
# record or an observed fault never reads "the result stands".
downgrade=""
if [ "$EVALUATOR_RESULT" = supports ] && [ "$outcome" != pass ]; then
    if [ "${#observed[@]}" -ne 0 ]; then downgrade="a fault the guest state showed"
    elif [ "${#stoprules[@]}" -ne 0 ]; then downgrade="a stop rule reached"
    elif [ "${#mandatory[@]}" -ne 0 ]; then downgrade="an evidence requirement not met (${mandatory[0]})"
    elif [ "${#incomplete[@]}" -ne 0 ]; then downgrade="a post-window observation not made"
    elif [ "$STACK_STATE" != healthy ]; then downgrade="the guest not fully restored (stack=$STACK_STATE)"
    else downgrade="the attempt's final verdicts"
    fi
fi
case "$outcome" in
    pass)
        next="the result stands for this run only: one run supports the property for that run and does not prove it in general; the candidate freeze and any resumption of G3 runs are separate decisions" ;;
    fail)
        if [ "$EVALUATOR_RESULT" = refutes ]; then
            next="a refutation is a result: record it, never re-run it away; the option is re-decided by the student (option 4 next best, never automatic)"
        else
            next="a fault the guest state showed beside the proof's own restart is a valid negative result: record it, never re-run it away; the evaluator's component result ($EVALUATOR_RESULT) does not stand for the attempt; the option is re-decided by the student (option 4 next best, never automatic)"
        fi
        ;;
    *)
        next="the attempt is inconclusive, not passing"
        [ -z "$downgrade" ] || next="$next (the evaluator's component result, supports, does not stand for the attempt: $downgrade)"
        [ "$EVALUATOR_RESULT" != not-computed ] || next="$next (the proof was not evaluated: read console/ and analysis/)"
        next="$next: the student decides whether to repeat it with the same design (recorded as a repeat, this run kept) or to re-decide the option"
        ;;
esac
[ "$validity" = valid ] || next="$next; the attempt's instrumentation is invalid: the evidence requirement(s) not met are in the reason and in console/"
[ "$STACK_STATE" = healthy ] || next="$next; the stack was left $STACK_STATE: resolve it before any other guest session"
[ -n "$FIRST" ] || FIRST="$PROOF_NOTE"
headline "$A" "$FIRST" || true
set_field "restoration=$(guest_state_text)"
session_update "restoration=$(guest_state_text)" "instants.ended_utc=$(now_utc)" "verdicts.instrumentation_validity=$validity" "verdicts.system_outcome=$outcome" "verdicts.evaluator=$EVALUATOR_RESULT"
(cd "$REPO/src" && $LE finish --attempt "$A" --status "$status" --validity "$validity" --outcome "$outcome" \
    --reason "$reason" --next-action "$next")
echo "PROOF $RID: validity=$validity outcome=$outcome evaluator=$EVALUATOR_RESULT (exit $v_rc) harness_exit=$h_rc restart_shown=$RESTART_SHOWN $(guest_state_text) observed=${#observed[@]} mandatory=${#mandatory[@]} incomplete=${#incomplete[@]} stop_rules=${#stoprules[@]} extension=$EXTENSION_RESULT"
driver_exit "$A"
