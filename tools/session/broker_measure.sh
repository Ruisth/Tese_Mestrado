#!/bin/bash
# broker_measure.sh - the broker-hold measurement of ADR 0011, condition C3
# (package D, gate item 1, section 7): can the pinned Mosquitto 2.0.22, alone,
# accept and honour an in-flight window W = 4,999, hold 4,999 and then 4,999
# plus a queue of real-sized QoS 1 messages for a non-acknowledging persistent
# session within 128 MiB, show where a full queue drops, and keep and redeliver
# the held messages, in per-device order, after the subscriber is killed?
#
# AN ENGINEERING DIAGNOSTIC, NOT A G3 RUN. It changes no threshold, load,
# deadline or rule, needs no controller change, no image rebuild and no Ditto.
# The values it uses (W, Q, the expiry, A = 4,999, B = 1,100) are PROBE
# settings, not adopted production or campaign settings. One run supports the
# broker-side premise for that run only.
#
# WHAT IT DOES TO THE GUEST, AND WHAT IT NEVER TOUCHES. The deployed stack is
# STOPPED for the measurement ('compose stop', containers kept, volumes kept)
# and STARTED again at the end, then waited for until every one of the six
# services is running and healthy. The probe broker is a throwaway container
# of the pinned image on its own fresh named volume, LABELLED with this
# attempt's id, reading the deployed certificates and password file read-only
# and MEASUREMENT COPIES of mosquitto.conf and acl (the deployed files plus the
# added lines, hashed into the record). It never mounts 'mosquitto-data',
# never writes into /opt/egw/deployment, refuses to start if a container or a
# volume of its names already exists (it removes only what it created, read
# back by its label), and removes its container and its volume at the end. The
# client ids are the probe's own (egw-probe-hold, egw-probe-sys,
# egw-probe-pub), never the controller's.
#
# THE PHASES (gate item 1, section 7): P0 baseline with the $SYS reader only;
# P1 the holding subscriber connects; P2 A = 4,999 published while it holds
# and acknowledges nothing; P3 a hold of HOLD1 s; P4 SIGKILL of the subscriber,
# then the broker's disconnection line; P5 B = 1,100 published while it is
# away; P6 a hold of HOLD2 s; P7 the subscriber resumes its session and
# acknowledges each redelivery after its record is on file; P8 final readings,
# the session discarded, the probe's state read, the probe removed, the stack
# started.
#
# TWO OUTPUTS, KEPT APART. (1) The broker observation: broker_hold.py verdict
# applies the design's rules to the records and writes verdict.json - it
# supports option 5 only if every one of S1-S5 holds; any of R1-R6, each
# resting on something observed, refutes option 5 as configured (a refutation
# is a result, recorded and never re-run away); everything else is
# inconclusive, which is NOT passing. That verdict is recorded on the attempt
# as 'broker_verdict' whatever else happened. (2) The session: whether every
# mandatory record was made and whether the guest was restored (the stack
# running and healthy again, the probe gone) - recorded as 'restoration'. The
# attempt's own outcome, and so the exit status, is a pass ONLY when the
# broker observation supports AND every mandatory record was made AND the
# restoration is healthy; a refutation with a complete record is a valid
# negative (1); anything with a missing record or an unfinished restoration
# is 3, and its reason says which of the two outputs is affected.
#
# STOP RULES, IMPOSED BY DESIGN AND NOT MEASURED DURATIONS (ADR 0011, "The
# broker measurement"): the stack stopped and the probe broker started within
# EGW_PROBE_SETUP_LIMIT_S (300 s, and each guest command of that stage is
# itself bounded by 'timeout'); the phases at their own limits (P4 at P4_S,
# P7 at P7_LIMIT plus a grace); the stack healthy again within
# EGW_HEALTH_LIMIT_S (1200 s) of its restart. Reaching one ends the
# measurement as inconclusive, unless a refuting result was already observed,
# which stands. The restoration is never cut short to keep a total duration.
#
# THE WINDOW IN WHICH THE GUEST HAS NO STACK IS THIS DRIVER'S OWN. The intent
# of every mutation (stopping the stack, creating the probe, starting the
# recorder) is recorded BEFORE the command is dispatched, so that an
# interruption between the dispatch and its return is treated as "it may have
# taken effect": every ending - the interrupt handler included - then reads
# the guest back (the stack's state, the labelled probe, the recorder unit)
# and restores what it finds, and says on its final line which state it left
# the guest in.
#
# Usage: broker_measure.sh            (needs an open session: guest_session_open.sh)
# Parameters (environment): EGW_PROBE_W (4999) EGW_PROBE_Q (1000)
#   EGW_PROBE_EXPIRY (1h) EGW_PROBE_A (4999) EGW_PROBE_B (1100)
#   EGW_PROBE_RATE (11.2) EGW_PROBE_HOLD1_S (130) EGW_PROBE_HOLD2_S (70)
#   EGW_PROBE_P0_S (60) EGW_PROBE_P1_S (10) EGW_PROBE_P4_S (10)
#   EGW_PROBE_P7_LIMIT_S (300) EGW_PROBE_P8_S (30) EGW_PROBE_SETUP_LIMIT_S (300)
#   EGW_PROBE_STEP_TIMEOUT_S (300, the bound on each guest command)
#   EGW_HEALTH_LIMIT_S (1200) EGW_HEALTH_STEP_S (15) EGW_PROBE_SEED (42)
#   EGW_PROBE_RUN_ID (brkhold-r01) EGW_PROBE_MEMORY (128m)
#   EGW_PROBE_TOOL (the probe module; defaults to the clone's)
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ "$#" -eq 0 ] || driver_stop "$EXIT_PREREQUISITE" "usage: broker_measure.sh (parameters are read from the environment)"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"

PROBE=${EGW_PROBE_TOOL:-$REPO/tools/probe/broker_hold.py}
RECORDER=$REPO/tools/probe/guest/probe_recorder.sh
for f in "$PROBE" "$RECORDER"; do
    [ -f "$f" ] || driver_stop "$EXIT_PREREQUISITE" "$f is not a readable file; nothing was started"
done
CA=$HOME/egw-tcg/ca.crt
[ -f "$CA" ] || driver_stop "$EXIT_PREREQUISITE" "$CA (the broker's CA, runbook 5.3) is missing; nothing was started"
command -v timeout > /dev/null || driver_stop "$EXIT_PREREQUISITE" "'timeout' is not installed on the host; nothing was started"

# --- the probe settings (recorded before anything starts) --------------------
W=${EGW_PROBE_W:-4999}
Q=${EGW_PROBE_Q:-1000}
EXPIRY=${EGW_PROBE_EXPIRY:-1h}
A_COUNT=${EGW_PROBE_A:-4999}
B_COUNT=${EGW_PROBE_B:-1100}
RATE=${EGW_PROBE_RATE:-11.2}
HOLD1=${EGW_PROBE_HOLD1_S:-130}
HOLD2=${EGW_PROBE_HOLD2_S:-70}
P0_S=${EGW_PROBE_P0_S:-60}
P1_S=${EGW_PROBE_P1_S:-10}
P4_S=${EGW_PROBE_P4_S:-10}
P7_LIMIT=${EGW_PROBE_P7_LIMIT_S:-300}
P7_GRACE=${EGW_PROBE_P7_GRACE_S:-60}
P8_S=${EGW_PROBE_P8_S:-30}
SETUP_LIMIT=${EGW_PROBE_SETUP_LIMIT_S:-300}
STEP_TIMEOUT=${EGW_PROBE_STEP_TIMEOUT_S:-300}
CLIENT_START_S=${EGW_PROBE_CLIENT_START_S:-30}
SEED=${EGW_PROBE_SEED:-42}
RUN_ID=${EGW_PROBE_RUN_ID:-brkhold-r01}
MEMORY=${EGW_PROBE_MEMORY:-128m}
MEMORY_MAX=${EGW_PROBE_MEMORY_MAX:-134217728}
BROKER_HOST=${EGW_PROBE_HOST:-127.0.0.1}
BROKER_PORT=${EGW_PROBE_PORT:-8883}
DEPLOYED=${EGW_DEPLOYED_DIR:-/opt/egw/deployment}
for v in W Q A_COUNT B_COUNT HOLD1 HOLD2 P0_S P1_S P4_S P7_LIMIT P7_GRACE P8_S SETUP_LIMIT STEP_TIMEOUT CLIENT_START_S SEED BROKER_PORT MEMORY_MAX; do
    case "${!v}" in
        '' | *[!0-9]*) driver_stop "$EXIT_PREREQUISITE" "$v='${!v}' is not a whole number; nothing was started" ;;
    esac
done
case "$RATE" in
    '' | *[!0-9.]*) driver_stop "$EXIT_PREREQUISITE" "EGW_PROBE_RATE='$RATE' is not a number; nothing was started" ;;
esac
[ "$W" -ge 1 ] && [ "$W" -le 65535 ] || driver_stop "$EXIT_PREREQUISITE" "W=$W is outside 1..65535; nothing was started"
LIMIT=$(healthy_seconds EGW_HEALTH_LIMIT_S 1200) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_LIMIT_S is not a whole number of seconds; nothing was started"
STEP=$(healthy_seconds EGW_HEALTH_STEP_S 15) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_STEP_S is not a whole number of seconds; nothing was started"
for value in "$DEPLOYED" "$DC" "$EXPIRY" "$MEMORY" "$RUN_ID" "$EXPECT_SERVICES"; do
    guest_literal "$value" \
        || driver_stop "$EXIT_PREREQUISITE" "'$value' cannot be written into a guest command as the literal it is; nothing was started"
done
case "$EXPIRY" in
    *[!0-9hdwmy]*) driver_stop "$EXIT_PREREQUISITE" "EGW_PROBE_EXPIRY='$EXPIRY' is not a Mosquitto 2.0 duration (digits and one of h d w m y); nothing was started" ;;
esac

A=$(new_attempt "broker hold measurement (C3)" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
ENVD=$A/environment
PR=$ENVD/probe
mkdir -p "$PR" || driver_stop "$EXIT_PREREQUISITE" "$PR could not be created"
TAG=$(basename "$A")
PNAME=egw-probe-broker
PVOL="egw-probe-data-$TAG"
PDIR="/opt/egw/probe/$TAG"
UNIT="egw-probe-rec-$TAG"
LABEL="egw.probe.attempt=$TAG"
for value in "$PVOL" "$PDIR" "$UNIT" "$LABEL"; do
    guest_literal "$value" || driver_stop "$EXIT_PREREQUISITE" "'$value' cannot be a guest literal"
done
PHASES=$PR/phases.jsonl
PARAMS=$PR/params.json

# --- the state this driver knows the guest to be in ----------------------------
# Each is set to its INTENT before the command that changes it is dispatched,
# and to what the command reported when it returns; every ending then reads
# the guest back rather than trusting these alone.
STACK_STATE=untouched   # untouched | stopping | stopped | starting | started | healthy | not-healthy | unknown
PROBE_STATE=none        # none | creating | running | removing | removed | unknown
REC_STATE=none          # none | starting | running | stopping | stopped | unknown
HOLD_PID=
SYS_PID=
mandatory=()            # records this measurement is made of that could not be made
stoprules=()            # stop rules reached
FIRST=""

first_note() { [ -n "$FIRST" ] || FIRST=$1; }
missed() { mandatory+=("$1"); first_note "$1"; }
# stoprule TEXT PHASE: a stop rule of the MEASUREMENT, written into the phases
# the verdict reads. restore_rule TEXT: a stop rule of the RESTORATION, which
# belongs to the session's outcome and never to the broker observation.
stoprule() { stoprules+=("$1"); first_note "$1"; phase_note "$2" stop_rule_reached "\"$1\""; }
restore_rule() { stoprules+=("$1"); first_note "$1"; }
now_utc() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }
phase_mark() { printf '{"phase":"%s","%s_utc":"%s","%s_epoch":%s}\n' "$1" "$2" "$(now_utc)" "$2" "$(date +%s)" >> "$PHASES"; }
phase_note() { printf '{"phase":"%s","%s":%s}\n' "$1" "$2" "$3" >> "$PHASES"; }
said() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    [ -n "$f" ] && [ -f "$f" ] || return 0
    sed -n "s/^$2//p" "$f" | tr '\n' ' '
}
keep_record() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    if [ -n "$f" ] && [ -f "$f" ] && cp "$f" "$PR/$2"; then
        return 0
    fi
    missed "$3 was not kept in environment/probe/$2"
    return 1
}
set_field() { (cd "$REPO/src" && $LE set --attempt "$A" "$1") > /dev/null 2>&1 || true; }

# gxt LIMIT ATTEMPT NAME GUEST-COMMAND: gx with a bound. A guest command that
# does not return within LIMIT seconds is ended by 'timeout' (124), so that a
# setup or a restoration step never waits without end; the driver reads 124 as
# "did not return", never as the guest's answer. A LIMIT that is not a
# positive number of seconds is an allowance already spent: the command is
# NOT invoked at all ('timeout 0' would disable the bound, never enforce it)
# and the same 124 is answered, with the reason on stderr.
budget_spent() {
    case "$1" in
        '' | *[!0-9]* | 0) return 0 ;;
    esac
    return 1
}
gxt() {
    local limit=$1 a=$2 name=$3 rc
    shift 3
    if budget_spent "$limit"; then
        echo "STOP: no time left in the allowance: '$name' was NOT started" >&2
        return 124
    fi
    ex "$a" "$name" timeout -k 15 "$limit" env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" || { echo "STOP: the session ssh helpers ($E/scripts/session_common.sh) could not be loaded: NOTHING was run on the guest" >&2; exit 97; }
gssh "$1"' _ "$1"
    rc=$?
    [ "$rc" -ne 255 ] || rc=$EXIT_NOT_REACHED
    return "$rc"
}
# gcpt LIMIT ATTEMPT NAME SRC DEST: gcp with the same bound and the same
# refusal of a spent allowance, so that a transfer never runs outside the
# budget its stage has.
gcpt() {
    local limit=$1 a=$2 name=$3 rc
    shift 3
    if budget_spent "$limit"; then
        echo "STOP: no time left in the allowance: '$name' was NOT started" >&2
        return 124
    fi
    ex "$a" "$name" timeout -k 15 "$limit" env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" || { echo "STOP: the session ssh helpers ($E/scripts/session_common.sh) could not be loaded: NOTHING was copied" >&2; exit 97; }
gscp "$1" "$2"' _ "$1" "$2"
    rc=$?
    [ "$rc" -ne 255 ] || rc=$EXIT_NOT_REACHED
    return "$rc"
}

# The host preamble this driver needs: the venv and the secrets. The tunnels of
# runbook 5.7 are not needed (the broker is reached on the hostfwd port), so a
# tunnel that is down never stops the measurement.
HOST_LITE=". $VENV/bin/activate && set -a && . \$HOME/egw-tcg/.env && set +a"
hl() {
    local a=$1 name=$2
    shift 2
    ex "$a" "$name" bash -c "{ $HOST_LITE ; } || { echo 'STOP: the host preamble (the venv and the secrets) could not be loaded: the step never ran' >&2; exit 97; }
$1"
}
# bg NAME ARGS...: one probe client in the background, a CHILD OF THIS SHELL
# (never started inside a command substitution, whose subshell would own it),
# its output kept under environment/probe/NAME.stdout.txt; the pid is left in
# BG_PID so that 'wait' reaps it and reports its status.
BG_PID=
bg() {
    local name=$1
    shift
    bash -c "{ $HOST_LITE ; } || exit 97
exec \"$PY\" \"$PROBE\" $*" > "$PR/$name.stdout.txt" 2> "$PR/$name.stderr.txt" &
    BG_PID=$!
}
# wait_line FILE PATTERN LIMIT_S: poll FILE until a line matches PATTERN.
wait_line() {
    local f=$1 pat=$2 limit=$3 t0
    t0=$(date +%s)
    while :; do
        grep -q -- "$pat" "$f" 2> /dev/null && return 0
        [ $(( $(date +%s) - t0 )) -lt "$limit" ] || return 1
        sleep 1
    done
}
alive() { [ -n "$1" ] && kill -0 "$1" 2> /dev/null; }
# reap PID: end a client this driver owns and wait for it, so that its files
# are complete and no process of this attempt outlives it.
reap() {
    local p=$1
    alive "$p" || { wait "$p" 2> /dev/null; return 0; }
    kill -TERM "$p" 2> /dev/null
    local i=0
    while alive "$p" && [ "$i" -lt 10 ]; do sleep 0.5; i=$((i + 1)); done
    alive "$p" && kill -KILL "$p" 2> /dev/null
    wait "$p" 2> /dev/null
    return 0
}
# wait_bounded PID LIMIT_S: wait for a client this driver owns for at most
# LIMIT_S seconds. It runs in THIS shell (never in a command substitution,
# whose subshell could not wait for the child): it leaves the client's exit
# status in WB_STATUS and returns 0 when the client ended by itself, or 1 when
# the bound was reached and the client was ended by this driver.
WB_STATUS=
wait_bounded() {
    local p=$1 limit=$2 t0
    t0=$(date +%s)
    while alive "$p"; do
        if [ $(( $(date +%s) - t0 )) -ge "$limit" ]; then
            reap "$p"
            WB_STATUS=ended-by-driver
            return 1
        fi
        sleep 0.5
    done
    wait "$p" 2> /dev/null
    WB_STATUS=$?
    return 0
}
# sys_last TOPIC: the last recorded value of a $SYS topic, or nothing.
sys_last() {
    "$PY" - "$PR/sys.jsonl" "$1" << 'PYEOF'
import json, sys
path, topic = sys.argv[1], sys.argv[2]
last = None
try:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("event") == "sys" and r.get("topic") == topic:
                last = r.get("value")
except OSError:
    pass
if last is not None:
    print(last)
PYEOF
}

# --- identities and the record of the settings ------------------------------
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
printf '{"W": %s, "Q": %s, "expiry": "%s", "A": %s, "B": %s, "rate_hz": %s, "hold1_s": %s, "hold2_s": %s, "p0_s": %s, "p4_s": %s, "p7_limit_s": %s, "setup_limit_s": %s, "step_timeout_s": %s, "health_limit_s": %s, "memory": "%s", "memory_max": %s, "seed": %s, "run_id": "%s", "broker": "%s:%s", "container": "%s", "volume": "%s", "guest_dir": "%s", "label": "%s", "recorder_gap_limit_s": 5}\n' \
    "$W" "$Q" "$EXPIRY" "$A_COUNT" "$B_COUNT" "$RATE" "$HOLD1" "$HOLD2" "$P0_S" "$P4_S" "$P7_LIMIT" "$SETUP_LIMIT" "$STEP_TIMEOUT" "$LIMIT" "$MEMORY" "$MEMORY_MAX" "$SEED" "$RUN_ID" "$BROKER_HOST" "$BROKER_PORT" "$PNAME" "$PVOL" "$PDIR" "$LABEL" > "$PARAMS"
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$IDENTITIES" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"measurement\": \"broker hold (ADR 0011 C3)\", \"engineering_diagnostic_not_a_g3_run\": true, \"W\": $W, \"Q\": $Q, \"expiry\": \"$EXPIRY\", \"A\": $A_COUNT, \"B\": $B_COUNT, \"rate_hz\": $RATE, \"memory\": \"$MEMORY\", \"seed\": $SEED, \"run_id\": \"$RUN_ID\", \"stack\": \"stopped for the measurement and started again at the end\"}" \
    "broker_verdict=not-computed" "restoration=not-started" \
    'expected_artefacts=["environment/probe/params.json", "environment/probe/phases.jsonl", "environment/probe/messages.jsonl", "environment/probe/sys.jsonl", "environment/probe/hold_p1.jsonl", "environment/probe/hold_p7.jsonl", "environment/probe/publish_p2.jsonl", "environment/probe/publish_p5.jsonl", "environment/probe/recorder.csv", "environment/probe/broker.log", "environment/probe/probe_state.json", "environment/probe/mosquitto.measure.conf", "environment/probe/acl.measure", "environment/probe/verdict.json"]') \
    || PREREQ="the attempt fields could not be recorded"
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || PREREQ=${PREREQ:-"the identity of the clean clone could not be read (see identities.identity_error)"}

not_run() {
    headline "$A" "$1: the measurement was NOT run" || true
    set_field "restoration=untouched"
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "$1; the measurement was NOT run" \
        --next-action "read console/; the stack was not touched: $STACK_STATE")
    driver_exit "$A"
}
[ -z "${PREREQ:-}" ] || not_run "$PREREQ"

# --- the guest read back: what is actually there ------------------------------
# probe_owned: 0 when a container named PNAME exists AND carries this attempt's
# label; 1 when no such container exists; 2 when one exists that is NOT ours;
# 3 when the daemon did not answer.
probe_owned() {
    local out
    if out=$(gxt "$STEP_TIMEOUT" "$A" "$1" "docker inspect -f '{{index .Config.Labels \"egw.probe.attempt\"}}' '$PNAME' 2>&1" > /dev/null; said "$1" ''); then
        out=$(printf '%s' "$out" | tr -d ' \n\r')
        # ownership is the label being EXACTLY this attempt's id
        if [ "$out" = "$TAG" ]; then
            return 0
        fi
        case "$out" in
            *"Nosuchobject"* | *"Nosuchcontainer"* | *"nosuchobject"* | *"nosuchcontainer"*) return 1 ;;
            *"Cannotconnect"* | *"errorduringconnect"* | '') return 3 ;;
            *) return 2 ;;
        esac
    fi
    return 3
}
# volume_owned NAME: 0 when the probe volume exists with EXACTLY this attempt's
# label; 1 when it does not exist; 2 when it exists with another label; 3
# when the daemon did not answer.
volume_owned() {
    local out
    if out=$(gxt "$STEP_TIMEOUT" "$A" "$1" "docker volume inspect -f '{{index .Labels \"egw.probe.attempt\"}}' '$PVOL' 2>&1" > /dev/null; said "$1" ''); then
        out=$(printf '%s' "$out" | tr -d ' \n\r')
        if [ "$out" = "$TAG" ]; then
            return 0
        fi
        case "$out" in
            *"Nosuchvolume"* | *"nosuchvolume"* | *"Nosuchobject"*) return 1 ;;
            *"Cannotconnect"* | *"errorduringconnect"* | '') return 3 ;;
            *) return 2 ;;
        esac
    fi
    return 3
}
stack_read() {
    gxt "$STEP_TIMEOUT" "$A" "$1" "cd '$DEPLOYED' && $DC ps -a --format '{{.Name}} {{.State}} {{.Health}}'" > /dev/null
    said "$1" ''
}

# --- restoration: what every ending does -----------------------------------
restore() {
    # the host clients first: nothing may keep publishing or holding, and
    # their files are complete only once they are reaped
    for p in "$HOLD_PID" "$SYS_PID"; do
        [ -z "$p" ] || reap "$p"
    done
    HOLD_PID=
    SYS_PID=
    : > "$PR/sys.stop" 2> /dev/null
    case "$REC_STATE" in
        starting | running | stopping | unknown)
            # The unit's REAL state is read first: a start whose confirmation
            # failed may still have left it running. Stopping and fetching are
            # two steps, so that a CSV that could be read never stands for a
            # stop that did not happen: the recorder is 'stopped' only when
            # 'systemctl is-active' says it is inactive after the stop.
            REC_STATE=stopping
            if gxt "$STEP_TIMEOUT" "$A" recorder-stop "if systemctl is-active '$UNIT' > /dev/null 2>&1; then sudo systemctl stop '$UNIT' || echo 'STOP: systemctl stop failed'; fi; sleep 1; st=\$(systemctl is-active '$UNIT' 2>&1); echo \"unit-state=\$st\"; case \"\$st\" in inactive | failed) echo 'RECORDER STOPPED'; exit 0 ;; esac; echo 'STOP: the recorder unit is still active'; exit 1"; then
                REC_STATE=stopped
            else
                REC_STATE=unknown
                missed "the guest recorder unit is not verified stopped ($UNIT): $(said recorder-stop 'STOP: ')"
            fi
            gxt "$STEP_TIMEOUT" "$A" recorder-readable "sudo chmod 0644 '$PDIR/recorder.csv' 2> /dev/null; wc -l '$PDIR/recorder.csv'; tail -n 1 '$PDIR/recorder.csv'" || true
            gcp "$A" recorder-fetch "egw@127.0.0.1:$PDIR/recorder.csv" "$PR/recorder.csv" \
                || missed "the guest recorder's CSV was not fetched"
            ;;
    esac
    case "$PROBE_STATE" in
        creating | running | removing | unknown)
            # only what this attempt created is removed: the container is read
            # back by its label, the volume by its attempt-specific name
            probe_owned probe-owned
            case "$?" in
                0)
                    PROBE_STATE=removing
                    gxt "$STEP_TIMEOUT" "$A" probe-state "docker inspect -f '{\"status\":\"{{.State.Status}}\",\"oom_killed\":{{.State.OOMKilled}},\"restart_count\":{{.RestartCount}},\"exit_code\":{{.State.ExitCode}},\"id\":\"{{.Id}}\",\"image\":\"{{.Image}}\",\"label\":\"{{index .Config.Labels \"egw.probe.attempt\"}}\"}' '$PNAME'"
                    keep_record probe-state probe_state.json "the probe container's state before removal" || true
                    gxt "$STEP_TIMEOUT" "$A" broker-log "docker logs -t '$PNAME' 2>&1"
                    keep_record broker-log broker.log "the probe broker's log" || true
                    if gxt "$STEP_TIMEOUT" "$A" probe-remove "docker rm -f '$PNAME' && echo 'PROBE CONTAINER REMOVED'"; then
                        PROBE_STATE=removed
                    else
                        PROBE_STATE=unknown
                        missed "the probe container may still be on the guest ($PNAME)"
                    fi
                    ;;
                1) PROBE_STATE=removed ;;
                2)
                    PROBE_STATE=unknown
                    missed "a container named $PNAME exists on the guest that this attempt did NOT create; it was left alone"
                    ;;
                *)
                    PROBE_STATE=unknown
                    missed "whether the probe container is still on the guest could not be determined"
                    ;;
            esac
            if [ "$PROBE_STATE" = removed ]; then
                volume_owned volume-owned
                case "$?" in
                    0)
                        gxt "$STEP_TIMEOUT" "$A" volume-remove "docker volume rm '$PVOL' && echo 'PROBE VOLUME REMOVED'" \
                            || { PROBE_STATE=unknown; missed "the probe volume may still be on the guest ($PVOL)"; }
                        ;;
                    1) ;;
                    2)
                        PROBE_STATE=unknown
                        missed "a volume named $PVOL exists on the guest that does not carry this attempt's label; it was left alone"
                        ;;
                    *)
                        PROBE_STATE=unknown
                        missed "whether the probe volume is still on the guest could not be determined"
                        ;;
                esac
            fi
            ;;
    esac
    case "$STACK_STATE" in
        stopping | stopped | starting | unknown)
            STACK_STATE=starting
            if gxt "$STEP_TIMEOUT" "$A" stack-start "cd '$DEPLOYED' && $DC start && $DC ps --format '{{.Name}} {{.State}} {{.Health}}'"; then
                STACK_STATE=started
            else
                STACK_STATE=unknown
            fi
            local rc
            healthy_wait "$A" services-healthy-again "$LIMIT" "$STEP"
            rc=$?
            if [ "$rc" -eq 0 ]; then
                STACK_STATE=healthy
            elif [ "$rc" -eq 1 ] || [ "$rc" -eq 4 ]; then
                STACK_STATE=not-healthy
                restore_rule "the stack was not running and healthy again within ${LIMIT} s of its restart:$(said services-healthy-again 'NOT HEALTHY[^:]*:')"
            else
                STACK_STATE=unknown
                missed "whether the stack is healthy again could not be determined (services-healthy-again exit $rc)"
            fi
            ;;
    esac
    set_field "restoration=$(guest_state_text)"
}
guest_state_text() {
    printf 'stack=%s probe=%s recorder=%s' "$STACK_STATE" "$PROBE_STATE" "$REC_STATE"
}
on_interrupt() {
    trap - INT TERM
    phase_note interrupt at "\"$(now_utc)\""
    restore
    headline "$A" "interrupted; the guest was left with $(guest_state_text)" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status interrupted --outcome interrupted \
        --reason "driver interrupted; the guest was left with $(guest_state_text)" \
        --next-action "if the stack is not healthy or the probe is not removed, resolve it before any other guest session" 2> /dev/null)
    driver_exit "$A"
}
trap on_interrupt INT TERM

# finish_measurement VALIDITY OUTCOME REASON NEXT STATUS: restore, close, export.
finish_measurement() {
    restore
    local validity=$1 outcome=$2 reason=$3 next=$4 status=$5
    if [ "${#stoprules[@]}" -gt 0 ]; then
        reason="$reason; stop rule(s) reached: $(printf '%s; ' "${stoprules[@]}")"
    fi
    if [ "${#mandatory[@]}" -gt 0 ]; then
        reason="$reason; not recorded: $(printf '%s; ' "${mandatory[@]}")"
        # a record that was not made leaves the measurement's instrumentation
        # incomplete: never 'valid', and never a pass, whatever the broker showed
        validity=invalid
        [ "$outcome" != pass ] || outcome=inconclusive
    fi
    if [ "$STACK_STATE" != healthy ] || [ "$PROBE_STATE" != removed ] \
        || { [ "$REC_STATE" != stopped ] && [ "$REC_STATE" != none ]; }; then
        # the session did not end with the guest restored - the stack healthy,
        # the probe gone AND the recorder verified stopped: a pass is never
        # reported, and the broker observation stays in broker_verdict
        [ "$outcome" != pass ] || outcome=inconclusive
        reason="$reason; the guest was NOT fully restored"
    fi
    reason="$reason; the guest was left with $(guest_state_text)"
    headline "$A" "$FIRST" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status "$status" --validity "$validity" --outcome "$outcome" \
        --reason "$reason" --next-action "$next")
    driver_exit "$A"
}
# abort REASON: a prerequisite of the measurement failed after something was
# started: everything is restored and the measurement is recorded as not run.
abort() {
    first_note "$1"
    set_field "broker_verdict=not-computed"
    finish_measurement invalid not-run "$1; the measurement did NOT run to its end" \
        "read console/ for the step that stopped it; nothing about the broker's behaviour is concluded" failed
}

# --- 0. the messages, the clock offset, the ownership guard --------------------
hl "$A" generate "\"$PY\" \"$PROBE\" generate --seed $SEED --run-id '$RUN_ID' --count $((A_COUNT + B_COUNT)) --rate $RATE --work-dir \"$ENVD/generate\" --out \"$PR/messages.jsonl\"" \
    || not_run "the messages could not be generated (generate exit $?): $(said generate 'STOP: ')"
gxt "$STEP_TIMEOUT" "$A" guest-clock "date +%s; date -u +%Y-%m-%dT%H:%M:%SZ"
HOST_EPOCH=$(date +%s)
GUEST_EPOCH=$(said guest-clock '' | cut -d' ' -f1)
case "$GUEST_EPOCH" in
    '' | *[!0-9]*) not_run "the guest clock could not be read" ;;
esac
OFFSET=$((GUEST_EPOCH - HOST_EPOCH))
"$PY" - "$PARAMS" "$OFFSET" << 'PYEOF'
import json, sys
p, off = sys.argv[1], int(sys.argv[2])
d = json.load(open(p, encoding="utf-8"))
d["guest_offset_s"] = off
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, sort_keys=True)
PYEOF
# Nothing of the probe's names may already exist: a container or a volume that
# is there was created by something else, and this attempt never removes what
# it did not create.
gxt "$STEP_TIMEOUT" "$A" ownership-guard "c=0; docker inspect '$PNAME' > /dev/null 2>&1 && { echo 'STOP: a container named $PNAME already exists'; c=1; }; docker volume inspect '$PVOL' > /dev/null 2>&1 && { echo 'STOP: a volume named $PVOL already exists'; c=1; }; [ -e '$PDIR' ] && { echo 'STOP: $PDIR already exists'; c=1; }; systemctl is-active '$UNIT' > /dev/null 2>&1 && { echo 'STOP: the unit $UNIT is active'; c=1; }; [ \$c -eq 0 ] && echo 'OWNERSHIP GUARD: nothing of this attempt exists yet'; exit \$c"
rc=$?
[ "$rc" -eq 0 ] || not_run "the ownership guard refused to start (exit $rc): $(said ownership-guard 'STOP: ')"

# --- 1. the deployed stack stopped, the probe broker started (stop rule) -----
# The setup's limit is ONE budget over every step of this stage, read from one
# clock: each guest command gets the smaller of its own bound and what is left
# of the budget, and a step is not started at all once the budget is spent.
T_SETUP=$(date +%s)
setup_left() {
    local left=$((SETUP_LIMIT - ($(date +%s) - T_SETUP)))
    [ "$left" -gt 0 ] || left=0
    [ "$left" -le "$STEP_TIMEOUT" ] || left=$STEP_TIMEOUT
    printf '%s' "$left"
}
# setup_step NAME: non-zero, with the stop rule recorded, when the setup budget
# is spent before NAME could start.
setup_step() {
    if [ "$(setup_left)" -le 0 ]; then
        stoprule "the setup budget of ${SETUP_LIMIT} s was spent before '$1' could start" setup
        return 1
    fi
    return 0
}
phase_mark setup start
STACK_STATE=stopping
gxt "$(setup_left)" "$A" stack-stop "cd '$DEPLOYED' && $DC stop -t 60 && $DC ps -a --format '{{.Name}} {{.State}}'"
rc=$?
if [ "$rc" -ne 0 ]; then
    STACK_STATE=unknown
    abort "the deployed stack could not be stopped, or the stop did not return within the setup budget (stack-stop exit $rc)"
fi
STACK_STATE=stopped
setup_step probe-config || abort "the setup budget was spent after the stack was stopped; nothing else was started"

probe_config_script() {
    printf "DEPLOYED='%s'\nPDIR='%s'\nW='%s'\nQ='%s'\nEXPIRY='%s'\n" "$DEPLOYED" "$PDIR" "$W" "$Q" "$EXPIRY"
    cat << 'GUEST_PROBE_CONFIG'
set -e
sudo mkdir -p "$PDIR"
sudo chown "$(id -u):$(id -g)" "$PDIR"
{
    sudo cat "$DEPLOYED/mosquitto/config/mosquitto.conf"
    printf '\n# --- broker-hold measurement (ADR 0011, condition C3): probe settings, not production values ---\n'
    printf 'max_inflight_messages %s\nmax_inflight_bytes 0\nmax_queued_messages %s\nmax_queued_bytes 0\npersistent_client_expiration %s\n' "$W" "$Q" "$EXPIRY"
} > "$PDIR/mosquitto.measure.conf"
sudo cat "$DEPLOYED/mosquitto/config/acl" \
    | awk '{ print } /^user egw-controller/ { print "topic read $SYS/#" }' \
    > "$PDIR/acl.measure"
chmod 0644 "$PDIR/mosquitto.measure.conf" "$PDIR/acl.measure"
grep -q '^topic read \$SYS/#' "$PDIR/acl.measure" || { echo 'STOP: the $SYS read grant was not added to the measurement acl'; exit 1; }
n=$(grep -c "^max_inflight_messages $W\$" "$PDIR/mosquitto.measure.conf")
[ "$n" -eq 1 ] || { echo "STOP: max_inflight_messages $W is not in the measurement conf exactly once"; exit 1; }
. "$DEPLOYED/images.lock.env"
echo "IMAGE=$IMAGE_MOSQUITTO"
echo '## mosquitto.measure.conf'
cat "$PDIR/mosquitto.measure.conf"
echo '## acl.measure'
cat "$PDIR/acl.measure"
echo '## sha256'
sha256sum "$PDIR/mosquitto.measure.conf" "$PDIR/acl.measure" "$DEPLOYED/mosquitto/config/mosquitto.conf" "$DEPLOYED/mosquitto/config/acl"
GUEST_PROBE_CONFIG
}
gxt "$(setup_left)" "$A" probe-config "$(probe_config_script)"
rc=$?
[ "$rc" -eq 0 ] || abort "the measurement copies of mosquitto.conf and acl could not be made (probe-config exit $rc): $(said probe-config 'STOP: ')"
IMAGE=$(said probe-config 'IMAGE=' | tr -d ' ')
[ -n "$IMAGE" ] || abort "the pinned broker image could not be read from $DEPLOYED/images.lock.env"
guest_literal "$IMAGE" || abort "the image reference is not a guest literal"
# The transfers of the setup are inside its budget like its commands: each is
# guarded, bounded by what is left, and a transfer that the budget ends is
# the setup ending (nothing after it is started).
setup_step probe-config-fetch || abort "the setup budget was spent before the measurement copies could be fetched; nothing else was started"
gcpt "$(setup_left)" "$A" probe-config-fetch "egw@127.0.0.1:$PDIR/mosquitto.measure.conf" "$PR/mosquitto.measure.conf"
rc=$?
if [ "$rc" -eq 124 ]; then
    stoprule "the setup budget of ${SETUP_LIMIT} s was spent while the measurement mosquitto.conf was being fetched" setup
    abort "the setup budget was spent during a transfer; nothing else was started"
fi
[ "$rc" -eq 0 ] || missed "the measurement mosquitto.conf was not fetched"
setup_step probe-acl-fetch || abort "the setup budget was spent before the measurement acl could be fetched; nothing else was started"
gcpt "$(setup_left)" "$A" probe-acl-fetch "egw@127.0.0.1:$PDIR/acl.measure" "$PR/acl.measure"
rc=$?
if [ "$rc" -eq 124 ]; then
    stoprule "the setup budget of ${SETUP_LIMIT} s was spent while the measurement acl was being fetched" setup
    abort "the setup budget was spent during a transfer; nothing else was started"
fi
[ "$rc" -eq 0 ] || missed "the measurement acl was not fetched"

probe_start_script() {
    printf "PNAME='%s'\nPVOL='%s'\nPDIR='%s'\nDEPLOYED='%s'\nIMAGE='%s'\nMEMORY='%s'\nPORT='%s'\nLABEL='%s'\n" \
        "$PNAME" "$PVOL" "$PDIR" "$DEPLOYED" "$IMAGE" "$MEMORY" "$BROKER_PORT" "$LABEL"
    cat << 'GUEST_PROBE_START'
docker volume create --label "$LABEL" "$PVOL" || { echo 'STOP: the probe volume could not be created'; exit 1; }
docker run -d --name "$PNAME" --label "$LABEL" --memory "$MEMORY" -p "$PORT:8883" \
    -v "$DEPLOYED/mosquitto/config/certs:/mosquitto/config/certs:ro" \
    -v "$DEPLOYED/mosquitto/config/passwd:/mosquitto/config/passwd:ro" \
    -v "$PDIR/mosquitto.measure.conf:/mosquitto/config/mosquitto.conf:ro" \
    -v "$PDIR/acl.measure:/mosquitto/config/acl:ro" \
    -v "$PVOL:/mosquitto/data" \
    "$IMAGE" || { echo 'STOP: docker run failed for the probe broker'; exit 1; }
i=0
while [ $i -lt 60 ]; do
    if docker logs "$PNAME" 2>&1 | grep -q 'listen socket on port 8883'; then break; fi
    st=$(docker inspect -f '{{.State.Status}}' "$PNAME" 2> /dev/null)
    [ "$st" = running ] || { echo "PROBE NOT RUNNING: state=$st"; break; }
    sleep 1
    i=$((i + 1))
done
echo "## inspect"
docker inspect -f 'id={{.Id}} image={{.Image}} state={{.State.Status}} started={{.State.StartedAt}} label={{index .Config.Labels "egw.probe.attempt"}}' "$PNAME"
ID=$(docker inspect -f '{{.Id}}' "$PNAME")
CGROOT=${PROBE_CGROUP_ROOT:-/sys/fs/cgroup}
for d in "$CGROOT/system.slice/docker-$ID.scope" "$CGROOT/docker/$ID"; do
    [ -f "$d/memory.max" ] && { echo "memory.max=$(cat "$d/memory.max") cgroup=$d"; break; }
done
echo "## log so far"
docker logs -t "$PNAME" 2>&1
docker inspect -f '{{.State.Status}}' "$PNAME" | grep -q running || { echo 'STOP: the probe broker is not running'; exit 1; }
docker logs "$PNAME" 2>&1 | grep -q 'listen socket on port 8883' || { echo 'STOP: the probe broker did not open its listener within 60 s'; exit 1; }
GUEST_PROBE_START
}
setup_step probe-start || abort "the setup budget was spent before the probe broker was started; nothing else was started"
PROBE_STATE=creating
gxt "$(setup_left)" "$A" probe-start "$(probe_start_script)"
rc=$?
if [ "$rc" -ne 0 ]; then
    # A broker that refuses its configuration is R1: the system's answer, not
    # a prerequisite. The container may or may not exist: restore reads it
    # back by its label. The log is kept and the verdict reads it.
    PROBE_STATE=unknown
    if said probe-start '' | grep -qE 'Error|Unknown configuration|not running|NOT RUNNING'; then
        first_note "the probe broker did not start with the measurement configuration (R1): $(said probe-start 'STOP: ')"
        phase_note P0 broker_refused true
    else
        abort "the probe broker could not be started (probe-start exit $rc): $(said probe-start 'STOP: ')"
    fi
else
    PROBE_STATE=running
fi
MEMMAX=$(said probe-start 'memory.max=' | cut -d' ' -f1)
[ "$MEMMAX" = "$MEMORY_MAX" ] || missed "the probe broker's memory.max reads '$MEMMAX', not $MEMORY_MAX"

setup_step recorder-copy || abort "the setup budget was spent before the recorder could be copied; nothing else was started"
gcpt "$(setup_left)" "$A" recorder-copy "$RECORDER" "egw@127.0.0.1:$PDIR/probe_recorder.sh"
rc=$?
if [ "$rc" -eq 124 ]; then
    stoprule "the setup budget of ${SETUP_LIMIT} s was spent while the recorder was being copied" setup
    abort "the setup budget was spent during a transfer; the recorder was NOT started"
fi
[ "$rc" -eq 0 ] || abort "the guest recorder could not be copied (recorder-copy exit $rc)"
setup_step recorder-start || abort "the setup budget was spent before the recorder was started; nothing else was started"
REC_STATE=starting
gxt "$(setup_left)" "$A" recorder-start "sudo systemd-run --unit '$UNIT' --collect sh '$PDIR/probe_recorder.sh' '$PNAME' '$PDIR/recorder.csv' '$PVOL' 1 10 && sleep 3 && systemctl is-active '$UNIT' && head -n 3 '$PDIR/recorder.csv'"
rc=$?
if [ "$rc" -ne 0 ]; then
    # the unit may be running although its confirmation failed: restore reads
    # its real state and stops it
    REC_STATE=unknown
    abort "the guest recorder did not start, or its start was not confirmed (recorder-start exit $rc)"
fi
REC_STATE=running
phase_mark setup end
if [ $(( $(date +%s) - T_SETUP )) -gt "$SETUP_LIMIT" ]; then
    stoprule "the stack was not stopped and the probe broker started within ${SETUP_LIMIT} s" setup
fi

# --- P0: the $SYS reader alone -------------------------------------------------
phase_mark P0 start
bg sysreader sysreader --host "$BROKER_HOST" --port "$BROKER_PORT" --ca-cert "$CA" --stop-file "$PR/sys.stop" --limit 7200 --record "$PR/sys.jsonl"
SYS_PID=$BG_PID
if ! wait_line "$PR/sysreader.stdout.txt" '^SUBSCRIBED:' "$CLIENT_START_S"; then
    missed "the \$SYS reader did not subscribe within ${CLIENT_START_S} s: $(cat "$PR/sysreader.stderr.txt" 2> /dev/null | tr '\n' ' ')"
    phase_note P0 sys_unreadable true
fi
if [ "${#stoprules[@]}" -eq 0 ] && [ "$PROBE_STATE" = running ] && [ "${#mandatory[@]}" -eq 0 ]; then
    sleep "$P0_S"
fi
wait_line "$PR/sysreader.stdout.txt" '^SYS: \$SYS/broker/version' 5 || phase_note P0 version_missing true
phase_mark P0 end

if [ "${#stoprules[@]}" -gt 0 ] || [ "$PROBE_STATE" != running ] || [ "${#mandatory[@]}" -gt 0 ]; then
    # Nothing more can be measured: a stop rule, a broker that refused its
    # configuration (R1, the verdict reads the log) or a $SYS that cannot be
    # read (inconclusive). The verdict decides between them from the records.
    :
else
    # --- P1: the holding subscriber ------------------------------------------
    phase_mark P1 start
    bg hold_p1 hold --host "$BROKER_HOST" --port "$BROKER_PORT" --ca-cert "$CA" --stop-file "$PR/hold_p1.stop" --limit 7200 --record "$PR/hold_p1.jsonl"
    HOLD_PID=$BG_PID
    if ! wait_line "$PR/hold_p1.stdout.txt" '^SUBSCRIBED:' "$CLIENT_START_S"; then
        missed "the holding subscriber did not subscribe within ${CLIENT_START_S} s: $(cat "$PR/hold_p1.stderr.txt" 2> /dev/null | tr '\n' ' ')"
    fi
    sleep "$P1_S"
    STORE_BASE=$(sys_last '$SYS/broker/store/messages/count')
    phase_note P1 store_baseline "\"$STORE_BASE\""
    phase_mark P1 end

    # --- P2: A published while the subscriber holds --------------------------
    phase_mark P2 start
    hl "$A" p2-publish "\"$PY\" \"$PROBE\" publish --messages \"$PR/messages.jsonl\" --first 0 --count $A_COUNT --rate $RATE --host $BROKER_HOST --port $BROKER_PORT --ca-cert \"$CA\" --record \"$PR/publish_p2.jsonl\""
    rc=$?
    phase_mark P2 end
    [ "$rc" -ne 2 ] || abort "the publisher could not connect in P2: $(said p2-publish 'STOP: ')"
    [ "$rc" -eq 0 ] || missed "the publisher did not publish and get acknowledged exactly A=$A_COUNT in P2 (exit $rc): $(said p2-publish 'NOT EXACT: ')$(said p2-publish 'STOP: ')"

    # --- P3: hold ---------------------------------------------------------------
    phase_mark P3 start
    sleep "$HOLD1"
    phase_note P3 store_end "\"$(sys_last '$SYS/broker/store/messages/count')\""
    phase_note P3 inflight_end "\"$(sys_last '$SYS/broker/messages/inflight')\""
    phase_mark P3 end

    # --- P4: SIGKILL, no DISCONNECT; the broker's disconnection line ----------
    phase_mark P4 start
    if alive "$HOLD_PID"; then
        kill -9 "$HOLD_PID" 2> /dev/null
        phase_note P4 sigkill_at "\"$(now_utc)\""
        wait "$HOLD_PID" 2> /dev/null
        phase_note P4 hold_p1_exit "\"$?\""
    else
        wait "$HOLD_PID" 2> /dev/null
        phase_note P4 hold_p1_exit "\"$?\""
        missed "the holding subscriber was no longer running at P4 (it ended by itself: read hold_p1.stdout.txt)"
    fi
    HOLD_PID=
    if gxt "$((P4_S + 30))" "$A" p4-disconnection "i=0; while [ \$i -lt $P4_S ]; do if docker logs '$PNAME' 2>&1 | grep -E 'egw-probe-hold' | grep -qE 'closed its connection|disconnect|Socket error'; then echo SEEN; docker logs -t '$PNAME' 2>&1 | grep -E 'egw-probe-hold' | tail -n 3; exit 0; fi; sleep 1; i=\$((i + 1)); done; echo 'NOT SEEN'; exit 1"; then
        phase_note P4 disconnection_seen true
    else
        phase_note P4 disconnection_seen false
        phase_note P4 limit_reached true
        stoprule "the broker's disconnection line for egw-probe-hold did not appear within ${P4_S} s of the kill" P4
    fi
    phase_mark P4 end
fi

# A stop rule reached ends the measurement: no later phase starts (nothing
# more is published and the session is not resumed), what was observed is
# kept, and the guest is restored. Only the final readings and the discard of
# the probe's own session follow.
if [ "${#stoprules[@]}" -eq 0 ] && [ "$PROBE_STATE" = running ] && [ "${#mandatory[@]}" -eq 0 ]; then
    # --- P5: B published while the subscriber is away -----------------------
    phase_mark P5 start
    hl "$A" p5-publish "\"$PY\" \"$PROBE\" publish --messages \"$PR/messages.jsonl\" --first $A_COUNT --count $B_COUNT --rate $RATE --host $BROKER_HOST --port $BROKER_PORT --ca-cert \"$CA\" --record \"$PR/publish_p5.jsonl\""
    rc=$?
    phase_mark P5 end
    [ "$rc" -ne 2 ] || abort "the publisher could not connect in P5: $(said p5-publish 'STOP: ')"
    [ "$rc" -eq 0 ] || missed "the publisher did not publish and get acknowledged exactly B=$B_COUNT in P5 (exit $rc): $(said p5-publish 'NOT EXACT: ')$(said p5-publish 'STOP: ')"

    # --- P6: hold, subscriber away ----------------------------------------------
    phase_mark P6 start
    sleep "$HOLD2"
    STORE_P6=$(sys_last '$SYS/broker/store/messages/count')
    phase_note P6 store_end "\"$STORE_P6\""
    phase_note P6 dropped_end "\"$(sys_last '$SYS/broker/publish/messages/dropped')\""
    phase_mark P6 end

    # --- P7: the session resumed, every redelivery acknowledged ---------------
    # The client is waited for, with a bound, until it ENDS: P7 ends after the
    # client's own end record, never before, and its exit status is recorded.
    phase_mark P7 start
    # The store count includes the broker's own retained messages (the $SYS
    # topics among them): what the subscriber has to receive back is the count
    # ABOVE the baseline read before P2 started, never the absolute count.
    EXPECT=$A_COUNT
    case "$STORE_P6$STORE_BASE" in
        *[!0-9]* | '') ;;
        *) [ "$STORE_P6" -ge "$STORE_BASE" ] && EXPECT=$((STORE_P6 - STORE_BASE)) ;;
    esac
    [ "$EXPECT" -ge 1 ] || EXPECT=$A_COUNT
    phase_note P7 expect "\"$EXPECT\""
    bg hold_p7 hold --ack --host "$BROKER_HOST" --port "$BROKER_PORT" --ca-cert "$CA" --stop-file "$PR/hold_p7.stop" --expect "$EXPECT" --idle 30 --limit "$P7_LIMIT" --record "$PR/hold_p7.jsonl"
    HOLD_PID=$BG_PID
    wait_line "$PR/hold_p7.stdout.txt" '^SUBSCRIBED:' "$CLIENT_START_S" \
        || missed "the holding subscriber did not resume within ${CLIENT_START_S} s in P7: $(cat "$PR/hold_p7.stderr.txt" 2> /dev/null | tr '\n' ' ')"
    wait_bounded "$HOLD_PID" "$((P7_LIMIT + P7_GRACE))"
    P7_BOUNDED=$?
    P7_STATUS=$WB_STATUS
    HOLD_PID=
    phase_note P7 hold_p7_exit "\"$P7_STATUS\""
    if [ "$P7_BOUNDED" -ne 0 ]; then
        phase_note P7 limit_reached true
        stoprule "the holding subscriber did not end within ${P7_LIMIT} s plus ${P7_GRACE} s in P7 and was ended by the driver" P7
    elif grep -q 'why=limit' "$PR/hold_p7.stdout.txt" 2> /dev/null; then
        phase_note P7 limit_reached true
        stoprule "P7 reached its limit of ${P7_LIMIT} s before the store returned to its baseline" P7
    elif [ "$P7_STATUS" != 0 ]; then
        missed "the holding subscriber ended $P7_STATUS in P7: $(cat "$PR/hold_p7.stderr.txt" 2> /dev/null | tr '\n' ' ')"
    fi
    phase_note P7 store_end "\"$(sys_last '$SYS/broker/store/messages/count')\""
    phase_mark P7 end
fi

# --- P8: final readings, the probe's own session discarded ------------------
# Run whenever the probe broker is up, so that a measurement ended by a stop
# rule still leaves its last readings and no persistent session behind.
if [ "$PROBE_STATE" = running ] && [ -f "$PR/hold_p1.jsonl" ]; then
    phase_mark P8 start
    sleep "$P8_S"
    hl "$A" discard "\"$PY\" \"$PROBE\" discard --host $BROKER_HOST --port $BROKER_PORT --ca-cert \"$CA\" --record \"$PR/discard.jsonl\"" \
        || missed "the persistent session of egw-probe-hold was not discarded: $(said discard 'STOP: ')"
    phase_mark P8 end
fi

# --- the records, the probe's state, the probe removed, the stack started -----
: > "$PR/sys.stop"
if [ -n "$SYS_PID" ]; then
    wait_bounded "$SYS_PID" 30 \
        || missed "the \$SYS reader did not end within 30 s of its stop file and was ended by the driver"
    phase_note P8 sysreader_exit "\"$WB_STATUS\""
    SYS_PID=
fi
restore
[ -f "$PR/recorder.csv" ] || missed "environment/probe/recorder.csv is missing"
[ -f "$PR/broker.log" ] || missed "environment/probe/broker.log is missing"
[ -f "$PR/probe_state.json" ] || missed "environment/probe/probe_state.json is missing"
for f in hold_p1 hold_p7 publish_p2 publish_p5 sys; do
    [ -f "$PR/$f.jsonl" ] || : > "$PR/$f.jsonl"
done

# --- the broker observation, then the session's own outcome -----------------
ex "$A" verdict "$PY" "$PROBE" verdict --params "$PARAMS" --phases "$PHASES" --broker-log "$PR/broker.log" \
    --publish-p2 "$PR/publish_p2.jsonl" --publish-p5 "$PR/publish_p5.jsonl" \
    --hold-p1 "$PR/hold_p1.jsonl" --hold-p7 "$PR/hold_p7.jsonl" --sys "$PR/sys.jsonl" \
    --recorder "$PR/recorder.csv" --probe-state "$PR/probe_state.json" --out "$PR/verdict.json"
vrc=$?
FIGS=$(said verdict 'figures: ')
case "$vrc" in
    0)
        set_field "broker_verdict=supports"
        first_note "supports: every one of S1-S5 holds for this run (W=$W, Q=$Q, A=$A_COUNT, B=$B_COUNT); $FIGS"
        finish_measurement valid pass \
            "the broker measurement SUPPORTS option 5 on the broker side for this run: S1-S5 all hold ($FIGS)" \
            "the result stands for this run only; the decision on option 5 and its implementation is the student's" finished
        ;;
    1)
        set_field "broker_verdict=refutes"
        first_note "refutes: $(said verdict 'refutes: ') - option 5 as configured is refuted and goes back to the student; $FIGS"
        finish_measurement valid fail \
            "the broker measurement REFUTES option 5 as configured (W=$W, Q=$Q): $(said verdict 'refutes: '); $FIGS" \
            "a refutation is a result: record it, never re-run it away; option 5 is re-decided by the student, option 4 next best" finished
        ;;
    3)
        set_field "broker_verdict=inconclusive"
        reasons=$(said verdict 'inconclusive: ')
        first_note "inconclusive: $reasons"
        validity=valid
        case "$reasons" in
            *recorder* | *'$SYS'* | *publisher* | *tunnel* | *'not observed'* | *'record'*) validity=invalid ;;
        esac
        finish_measurement "$validity" inconclusive \
            "the broker measurement is INCONCLUSIVE, which is not passing: $reasons; $FIGS" \
            "the student decides whether to repeat it with the same design (recorded as a repeat, this run kept) or to re-decide the option" failed
        ;;
    *)
        set_field "broker_verdict=not-computed"
        first_note "the verdict could not be computed (verdict exit $vrc)"
        finish_measurement invalid inconclusive \
            "the verdict could not be computed from the records (verdict exit $vrc): $(said verdict 'STOP: ')" \
            "read console/ and environment/probe/; the records are kept as they are" failed
        ;;
esac
