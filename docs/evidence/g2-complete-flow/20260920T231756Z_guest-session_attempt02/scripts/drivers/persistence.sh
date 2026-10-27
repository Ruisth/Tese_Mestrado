#!/bin/bash
# G2 closure, section 4.D of the work order of 2026-09-20: runbook 6.5
# (docs/setup/qemu_integrated_gateway.md, "Restart the services and verify twin
# persistence") carried out on the run the G2 slice produced.
# Usage: persistence.sh RUN   (the run id slice.sh used, whose 'after'
#        snapshots already exist beside $HOME/egw-tcg/itest/RUN)
#
# WHICH SERVICES THIS RESTARTS, AND WHY A CACHE CANNOT EXPLAIN THE READBACK.
# The restart is the runbook's own: 'docker compose down' followed by 'docker
# compose up -d' in the deployment directory, which destroys and creates again
# EVERY container of the stack - the broker, MongoDB, the three Ditto services
# and the controller. It is never 'down -v'; no volume is removed, nothing is
# republished and no twin is written, so 'mongodb-data' and 'mosquitto-data'
# survive untouched. Because every container OBJECT is new - a new container
# id, a new controller process with a new started_at, a new JVM in each Ditto
# service and a new MongoDB process - no process memory, no connection and no
# in-process cache from before the restart exists any more: what the API
# answers afterwards was read back from the volumes.
#
# The steps, in the runbook's order:
#   1 QUIESCE: 'drained' must return 0. Nothing is published from here to the
#     end of the driver - the simulator is never started - and the driver
#     RECORDS that nothing was: the twin's accepted_count and the run's event
#     log record count are read before and after and must not move.
#   2 BEFORE: the controller's started_at, the six containers' ids and start
#     instants, an independent read of the twin through the API, the event log
#     record count, and the 'persist-before' snapshot taken like 'after'.
#   3 RESTART with the volumes preserved.
#   4 SHOW THE RESTART: an issued command is not a restart. The controller's
#     started_at must differ and every container id must differ with a later
#     start instant; otherwise the persistence was NOT demonstrated.
#   5 READY AGAIN: 'wait_ready' within EGW_READY_LIMIT_S, then the six services
#     running and healthy again through the wait shared with gate_health.sh.
#   6 AFTER, before anything is published: the 'post-restart' snapshot, '$REC
#     same' over the two snapshots, and an independent read of the same twin
#     with its contract fields.
#   7 WHAT THE RESTART RESETS: /metrics is per PROCESS, so every counter is 0
#     again and started_at is new. That is expected and is recorded as such -
#     never as loss. The twin's STORED state is what must be unchanged.
#
# Observing the system fail is a result; failing to observe is an invalid
# measurement. A twin whose stored state did not survive and a stack that does
# not come back are the system answering: valid, fail, exit 1, and the attempt
# keeps that result. A restart that was not shown, a record that could not be
# made and a publication between the two snapshots leave the demonstration
# invalid (exit 3) with the reason naming what did not change or what moved. A
# 'drained' that does not return 0 means the check did not run as a protocol
# check: outcome not-run, exit 2, and NOTHING is restarted.
#
# A TWIN THAT IS GONE IS THE RESULT; A TWIN THAT WAS NOT READ IS NOT.
# The defect this driver exists to find looks like this: the restart is shown,
# the stack comes back, and the API answers 404 for the thing because the
# volume did not hold it. That is the system failing in front of the check -
# valid, fail, exit 1 - and so is a thing that comes back without the state
# this run stored in it. Only a reading that was NOT MADE - the API not
# reached at all (curl's 7 or 28, which print the code 000), another code, a
# body that is not JSON - leaves the demonstration invalid. In the same way, a
# step that never reached the guest (EXIT_NOT_REACHED, common.sh) observed
# nothing about it, and is never read as the guest reporting a fault.
#
# THE WINDOW IN WHICH THE GUEST HAS NO STACK IS THIS DRIVER'S OWN.
# Between 'down' and 'up -d' every container of the stack is gone. Every
# ending - the interrupt handler included - reads from what the restart step
# itself reported which state the guest is in, and says it in the reason, in
# the next action and on the one final line, so that a run that stopped in
# that window never leaves an operator believing the stack is up.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
# A missing argument is a prerequisite (2), never the 1 of a valid negative
# result: '${1:?...}' would end the shell with 1 before any check could run.
[ "$#" -eq 1 ] || driver_stop "$EXIT_PREREQUISITE" "usage: persistence.sh RUN (the run id the G2 slice used)"
RUN=$1
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
LIMIT=$(healthy_seconds EGW_HEALTH_LIMIT_S 1800) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_LIMIT_S is not a whole number of seconds; nothing was restarted"
STEP=$(healthy_seconds EGW_HEALTH_STEP_S 15) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_STEP_S is not a whole number of seconds; nothing was restarted"
# One hour is the runbook's upper bound for the JVM start-up under TCG (6.5).
READY=$(healthy_seconds EGW_READY_LIMIT_S 3600) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_READY_LIMIT_S is not a whole number of seconds; nothing was restarted"
DEPLOYED=${EGW_DEPLOYED_DIR:-/opt/egw/deployment}
# Every parameter that is written into a guest script is checked ONCE, here,
# before anything is read or restarted: a value that could not be written as
# the literal it is would make the guest run something other than what this
# driver says it runs.
for value in "$DEPLOYED" "$DC" "$RUN" "$EXPECT_SERVICES"; do
    guest_literal "$value" \
        || driver_stop "$EXIT_PREREQUISITE" "'$value' cannot be written into a guest command as the literal it is; nothing was restarted"
done
P=$HOME/egw-tcg/itest
# This driver runs on a COMPLETED slice: its 'after' pair is the state the
# 'persist-before' snapshot is taken like, and its published identities name
# the device to read back. Without them there is nothing to demonstrate.
for f in "$P/$RUN.twins.after.json" "$P/$RUN.metrics.after.json" "$P/$RUN/sent_events.jsonl"; do
    [ -s "$f" ] \
        || driver_stop "$EXIT_PREREQUISITE" "$f is missing or empty: persistence.sh runs on a run the slice completed; nothing was restarted"
done
# The snapshots of this check are write-once, like every other record of a run:
# a run id already used for a persistence check is never overwritten.
for f in "$P/$RUN.twins.persist-before.json" "$P/$RUN.twins.post-restart.json"; do
    [ ! -e "$f" ] \
        || driver_stop "$EXIT_PREREQUISITE" "$f exists: this run id was already used for a persistence check and its records are write-once; nothing was restarted"
done
A=$(new_attempt "G2 twin persistence restart" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
ENVD=$A/environment
RESTARTED=no    # whether the restart command was issued at all

# THE WINDOW IN WHICH THIS DRIVER LEAVES THE GUEST WITHOUT ITS STACK.
# Between 'compose down' and a 'compose up -d' that came back, every container
# of the stack is gone. That window belongs to this driver alone, and it is the
# one state in which ending without saying so would leave the operator with a
# guest they believe is up. stack_state reads how far the restart step itself
# got, from what it printed, and every ending - the interrupt handler included
# - names the state the guest is in.
#   not-restarted  nothing was restarted: the stack was never touched
#   refused        'down' itself ended non-zero: the stack was not taken down
#                  cleanly and may be partly down
#   down           'down' came back 0 and no 'up -d' did: the stack is DOWN
#   up             'up -d' came back 0: the stack is up again
#   unknown        the step was cut short before it reported even its 'down'
stack_state() {
    local f down up
    if [ "$RESTARTED" = no ]; then
        printf 'not-restarted'
        return 0
    fi
    f=$(ls "$A"/console/*-restart-down-up.stdout.txt 2> /dev/null | tail -n 1)
    if [ -n "$f" ] && [ -f "$f" ]; then
        down=$(sed -n 's/^down exit=\([0-9][0-9]*\)$/\1/p' "$f" | tail -n 1)
        up=$(sed -n 's/^up exit=\([0-9][0-9]*\)$/\1/p' "$f" | tail -n 1)
        if [ -n "$down" ] && [ "$down" != 0 ]; then
            printf 'refused'
            return 0
        fi
        if [ "${down:-}" = 0 ]; then
            if [ "${up:-}" = 0 ]; then
                printf 'up'
            else
                printf 'down'
            fi
            return 0
        fi
    fi
    printf 'unknown'
}

# stack_note: the state of the guest's stack, in the words the reason and the
# final line carry.
stack_note() {
    case "$(stack_state)" in
        not-restarted) printf 'NOTHING was restarted: the stack on the guest was not touched' ;;
        up) printf 'the restart was issued and the stack was brought back up' ;;
        refused) printf 'the restart was issued and "%s down" ended non-zero: the stack was NOT taken down cleanly and may be partly down' "$DC" ;;
        down) printf 'THE STACK IS DOWN: this driver took it down with "%s down" and did NOT bring it back up; no volume was removed, so the stored state is intact' "$DC" ;;
        *) printf 'THE STACK MAY BE DOWN: the restart step was cut short before it reported even its "%s down", so the guest may be left without its stack' "$DC" ;;
    esac
}

# stack_next: what the operator does about that state, first of all.
stack_next() {
    case "$(stack_state)" in
        down | unknown)
            printf 'FIRST bring the stack back: on the guest, in %s, run "%s ps" and then "%s up -d" (runbook 6.5); no volume was removed and no twin was republished, so the stored state is intact and this check can be repeated under a new attempt with a new run id' \
                "$DEPLOYED" "$DC" "$DC"
            ;;
        refused)
            printf 'FIRST read the state of the stack: on the guest, in %s, run "%s ps"; "down" ended non-zero, so part of the stack may be gone; no volume was removed and no twin was republished' \
                "$DEPLOYED" "$DC"
            ;;
        *)
            printf 'read console/ and environment/; no volume was removed and no twin was republished, so the check can be repeated under a new attempt'
            ;;
    esac
}

# The interrupt of THIS driver: the attempt is marked interrupted, as
# driver_interrupt marks it, and it also records the state the guest was left
# in - an interruption between 'down' and 'up -d' leaves the stack down, and
# that must be in the reason, in the next action and on the final line.
persistence_interrupt() {
    headline "$A" "interrupted: $(stack_note)" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status interrupted --outcome interrupted \
        --reason "driver interrupted; $(stack_note)" \
        --next-action "$(stack_next)" 2> /dev/null)
    driver_exit "$A"
}
trap 'persistence_interrupt' INT TERM

STEPS=(quiesce metrics-before containers-before twin-before events-before snapshot-before
       restart-down-up ready-again services-healthy-again metrics-after containers-after
       restart-shown snapshot-after twin-state-same twin-after events-after stored-state)
prerequisite=()   # the check did not run as a protocol check
mandatory=()      # a record could not be made, or the restart was not shown
observed=()       # what the system did: the system outcome fails
skipped=()        # steps not run after the sequence stopped

# stop_after NAME: record every step after NAME as not run.
stop_after() {
    local seen=0 s
    for s in "${STEPS[@]}"; do
        [ "$seen" -eq 1 ] && skipped+=("$s")
        [ "$s" = "$1" ] && seen=1
    done
}

# need NAME RC TEXT: a mandatory record. Non-zero when it failed, with the
# failure recorded and the steps after it named as not run; a lost console
# capture is named as the capture failing, never as the step failing.
need() {
    [ "$2" -eq 0 ] && return 0
    mandatory+=("$(step_note "$1" "$2" "$3")")
    stop_after "$1"
    return 1
}

# said NAME PREFIX: what the step NAME itself printed after PREFIX, read from
# its console record and joined onto one line. A reason names what a step
# reported, never a status alone.
said() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    [ -n "$f" ] && [ -f "$f" ] || return 0
    sed -n "s/^$2//p" "$f" | tr '\n' ' '
}

# events_records NAME: the record count the step NAME printed, or nothing at
# all when it printed none. A count that was not read is never taken as 0.
events_records() {
    local f n
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    [ -n "$f" ] && [ -f "$f" ] || return 1
    n=$(sed -n 's/^events_records=[ ]*\([0-9][0-9]*\)$/\1/p' "$f" | tail -n 1)
    [ -n "$n" ] || return 1
    printf '%s' "$n"
}

# The readiness step's own report, read from its console record as the shared
# wait's lines are read. The runbook's 'wait_ready' gives up with
#   STOP: wait_ready: /ready answered '<code>', not 200, for <limit> s ...
# and that sentence is the one observation of readiness this step can make.
# Any other way the step ended - a preamble that failed, a shell that died, a
# transport that dropped before the helper ran - observed NOTHING about the
# stack, and a status alone is never read as the stack failing to come back.
# ready_code: the code 'wait_ready' reported, printed on stdout, or nothing
# when the step made no such report. '000' is curl's code for a request that
# was never answered - the tunnel of 5.7 down, the host unable to connect - so
# it is NOT an answer of the controller and the caller must not read it as one.
ready_code() {
    local f code
    for f in "$A"/console/*-ready-again.stderr.txt "$A"/console/*-ready-again.stdout.txt; do
        [ -f "$f" ] || continue
        code=$(sed -n "s/^STOP: wait_ready: \/ready answered '\([^']*\)'.*/\1/p" "$f" | tail -n 1)
        [ -n "$code" ] && { printf '%s' "$code"; return 0; }
    done
    return 1
}

# keep_record NAME FILE WHAT: copy the console record of NAME into
# environment/ under FILE. A record that was not kept is a record that was not
# made, and the step that depends on it is not run.
keep_record() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    if [ -n "$f" ] && [ -f "$f" ] && cp "$f" "$ENVD/$2"; then
        return 0
    fi
    mandatory+=("$3 was not kept in environment/$2")
    stop_after "$1"
    return 1
}

# containers_script: the id and the start instant of each expected container,
# in the identical form before and after the restart. The parameters are
# written as plain assignments in front of a QUOTED here-document, so the guest
# text is never expanded twice; it runs under BusyBox ash and holds no bashism.
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

# restart_script: runbook 6.5, with the volumes preserved. 'down' is never
# given -v and no volume is named anywhere: the two named volumes are what the
# readback rests on. Both statuses are printed, because 'up -d' after a
# successful 'down' leaving the stack half up is not the same as a 'down' that
# refused.
restart_script() {
    printf "DEPLOYED='%s'\nDC='%s'\n" "$DEPLOYED" "$DC"
    cat << 'GUEST_RESTART'
cd "$DEPLOYED" || { echo "STOP: $DEPLOYED could not be entered"; exit 1; }
$DC down
d=$?
echo "down exit=$d"
[ "$d" = 0 ] || { echo 'STOP: compose down ended non-zero: the stack was NOT taken down cleanly'; exit "$d"; }
$DC up -d
u=$?
echo "up exit=$u"
[ "$u" = 0 ] || { echo 'STOP: compose up -d ended non-zero after the stack was taken down'; exit "$u"; }
echo 'RESTART ISSUED: every container object of the stack was destroyed and created again; no volume was removed'
GUEST_RESTART
}

# twin_script FILE WHEN: the independent read of this run's twin through the
# API, in the identical form before and after the restart. It is what tells a
# twin that did NOT come back from one that could not be READ, which is the
# difference between the result this driver exists to find and a measurement
# that was not made:
#   0  the API answered 200 and the body is JSON: the twin was read
#   4  the API answered 404: the thing is NOT THERE (after the restart, that
#      is the persistence defect itself - the volume did not hold it)
#   1  no reading was made at all: the API was not reached (curl's own 7 or
#      28, which print the code 000), it answered some other code, or the body
#      it answered is not JSON
# The parameters are written as plain assignments in front of a QUOTED
# here-document, so nothing in the script is expanded twice; $P and $DITTO come
# from the host preamble of runbook 6.1.
twin_script() {
    printf "RUN='%s'\nOUT='%s'\nWHEN='%s'\n" "$RUN" "$1" "$2"
    cat << 'HOST_TWIN'
UUID=$(python3 -c "import json;print(json.loads(open('$P/$RUN/sent_events.jsonl').readline())['device_uuid'])") \
    || { echo "STOP: the device identity published by $RUN could not be read"; exit 1; }
[ -n "$UUID" ] || { echo "STOP: $RUN published no device identity"; exit 1; }
printf 'device %s\n' "$UUID"
code=$(curl -s -m 30 -H 'x-ditto-pre-authenticated: pre:egw-controller' -o "$OUT" -w '%{http_code}' "$DITTO/api/2/things/org.c2dta:$UUID")
rc=$?
[ -n "$code" ] || code=000
printf 'twin_http=%s curl_exit=%s\n' "$code" "$rc"
cat "$OUT" 2> /dev/null
printf '\n'
if [ "$rc" -ne 0 ] || [ "$code" = 000 ]; then
    echo "STOP: the twin org.c2dta:$UUID was not read $WHEN the restart: the API was not reached (curl exit $rc, HTTP code $code)"
    exit 1
fi
if [ "$code" = 404 ]; then
    echo "TWIN ABSENT: the API answered 404 for org.c2dta:$UUID $WHEN the restart: the thing is not there"
    exit 4
fi
[ "$code" = 200 ] || { echo "STOP: the API answered $code for org.c2dta:$UUID $WHEN the restart: no twin state was read"; exit 1; }
python3 -m json.tool "$OUT" || { echo "STOP: the body the API answered for org.c2dta:$UUID is not JSON: no twin state was read"; exit 1; }
HOST_TWIN
}

# events_script LABEL: how many records the controller has logged for this run
# on the guest. It is read before and after the restart and must not move.
events_script() {
    printf "RUN='%s'\nDEPLOYED='%s'\n" "$RUN" "$DEPLOYED"
    cat << 'GUEST_EVENTS'
f=$DEPLOYED/data/events/$RUN/events.jsonl
[ -f "$f" ] || { echo "STOP: $f is not there: the record count of this run could not be read"; exit 1; }
n=$(wc -l < "$f") || { echo "STOP: $f could not be counted"; exit 1; }
echo "events_records=$n"
GUEST_EVENTS
}

# The identity of the clean clone is part of the result: a git that cannot be
# read is recorded as such (identity_error) and stops the driver.
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$IDENTITIES" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"gate\": \"G2\", \"itest_run_id\": \"$RUN\", \"procedure\": \"runbook 6.5: compose down then up -d, volumes preserved\", \"restarts\": \"$EXPECT_SERVICES\", \"publishes\": \"nothing: the simulator is never started\"}" \
    'expected_artefacts=["environment/metrics.persist-before.json", "environment/containers.persist-before.txt", "environment/twin.persist-before.json"]') \
    || prerequisite+=("the attempt fields could not be recorded")
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || prerequisite+=("the identity of the clean clone could not be read (see identities.identity_error)")
(cd "$REPO/src" && $LE add-source --attempt "$A" --kind simulator --path "$P/$RUN" --siblings-glob "$RUN.*" \
    --role "the slice run directory and its sibling snapshots (runbook 6.1 helpers)") \
    || prerequisite+=("the simulator source could not be registered")
[ "${#prerequisite[@]}" -eq 0 ] || skipped=("${STEPS[@]}")

steps() {
    # --- 1. quiesce: the queue is empty and the counters are steady --------
    hx "$A" quiesce "drained"
    local rc=$?
    if [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        capture_stop "$A" quiesce "NOTHING was restarted"
    elif [ "$rc" -ne 0 ]; then
        prerequisite+=("the queue was not observed quiet before the restart (quiesce exit $rc)")
        stop_after quiesce
        return
    fi

    # --- 2. the state before the restart -----------------------------------
    hx "$A" metrics-before "c=\$(curl -s -m 30 -o \"$ENVD/metrics.persist-before.json\" -w '%{http_code}' \"\$CTRL/metrics\"); printf 'metrics %s\n' \"\$c\"; cat \"$ENVD/metrics.persist-before.json\" 2> /dev/null; printf '\n'; [ \"\$c\" = 200 ]"
    need metrics-before $? "the controller process the counters belong to was not read before the restart; nothing was restarted" || return
    gx "$A" containers-before "$(containers_script)"
    need containers-before $? "the containers' ids and start instants were not recorded before the restart; nothing was restarted" || return
    keep_record containers-before containers.persist-before.txt "the containers before the restart" || return
    hx "$A" twin-before "$(twin_script "$ENVD/twin.persist-before.json" before)"
    local twin_before_rc=$?
    if [ "$twin_before_rc" -eq 4 ]; then
        # The thing is not there BEFORE anything is restarted: there is no
        # stored state whose survival could be demonstrated, so this check does
        # not run as a protocol check and NOTHING is restarted.
        prerequisite+=("the twin of $RUN is not there before the restart:$(said twin-before 'TWIN ABSENT:') - there is no stored state whose survival a restart could demonstrate")
        stop_after twin-before
        return
    fi
    need twin-before "$twin_before_rc" "the twin was not read through the API before the restart:$(said twin-before 'STOP:') nothing was restarted" || return
    gx "$A" events-before "$(events_script)"
    need events-before $? "the event log record count of this run was not read before the restart; nothing was restarted" || return
    hx "$A" snapshot-before "\$REC snap --prefix \$P/$RUN --label persist-before --like after --ditto-url \"\$DITTO\""
    need snapshot-before $? "the 'persist-before' twin snapshot was not taken; nothing was restarted" || return

    # --- 3. the restart, with the volumes preserved ------------------------
    # From HERE the guest may be without its stack: the flag is set BEFORE the
    # command is issued, because an interruption during it is exactly the
    # window in which nothing else would say so. What actually happened is
    # then read from what the step itself reported (stack_state).
    RESTARTED=yes
    gx "$A" restart-down-up "$(restart_script)"
    local restart_rc=$?
    if [ "$restart_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note restart-down-up)")
        stop_after restart-down-up
        return
    elif [ "$restart_rc" -ne 0 ]; then
        # 'down' that succeeded and 'up -d' that did not leaves the guest
        # without its stack: the state is read from what the step reported and
        # is carried into the reason, the next action and the final line.
        mandatory+=("$(step_note restart-down-up "$restart_rc" "the restart was not shown: compose down/up -d ended non-zero (restart-down-up exit $restart_rc)")")
        stop_after restart-down-up
        return
    fi

    # --- 5. ready again (the runbook takes this before the snapshot) -------
    hx "$A" ready-again "wait_ready $READY"
    local ready_rc=$?
    if [ "$ready_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note ready-again)")
        stop_after ready-again
        return
    elif [ "$ready_rc" -ne 0 ]; then
        # The code the step reported decides what was observed: a code the
        # controller itself answered is its answer, while '000' (curl reached
        # nobody: the tunnel of 5.7 down, the host unable to connect) and no
        # report at all observed nothing about the stack coming back. The six
        # services are then still asked DIRECTLY over ssh, because that second
        # channel is the only thing that can say what the guest is doing.
        local code
        code=$(ready_code) || code=""
        if [ -n "$code" ] && [ "$code" != 000 ]; then
            observed+=("the controller answered /ready $code, not 200, for ${READY} s after the restart (ready-again exit $ready_rc)")
        elif [ "$code" = 000 ]; then
            mandatory+=("the controller was NOT REACHED after the restart (/ready answered no code at all for ${READY} s: curl connected to nobody), so nothing was observed about the stack coming back (ready-again exit $ready_rc)")
        else
            mandatory+=("$(step_note ready-again "$ready_rc" "the stack's readiness after the restart was NOT observed (ready-again exit $ready_rc): the step did not report what /ready answered, so nothing is concluded about the stack coming back")")
        fi
        healthy_wait "$A" services-healthy-again "$LIMIT" "$STEP"
        local after_ready_rc=$?
        case "$after_ready_rc" in
            0) ;;
            "$EXIT_CAPTURE_LOST") mandatory+=("$(capture_note services-healthy-again)") ;;
            "$EXIT_NOT_REACHED") mandatory+=("the state of the six services after the restart was not observed because the wait never reached the guest (services-healthy-again exit $after_ready_rc)") ;;
            1 | 4) observed+=("not every expected service came back to 'running' and 'healthy' within ${LIMIT} s:$(said services-healthy-again 'NOT HEALTHY[^:]*:')") ;;
            *) mandatory+=("the state of the six services after the restart was not observed (services-healthy-again exit $after_ready_rc)") ;;
        esac
        stop_after ready-again
        return
    fi
    healthy_wait "$A" services-healthy-again "$LIMIT" "$STEP"
    local health_rc=$?
    if [ "$health_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note services-healthy-again)")
        stop_after services-healthy-again
        return
    elif [ "$health_rc" -eq "$EXIT_NOT_REACHED" ]; then
        # The wait never ran on the guest: nothing was observed about the six
        # services, which is not the same as their not coming back healthy.
        mandatory+=("the state of the six services after the restart was not observed because the wait never reached the guest (services-healthy-again exit $health_rc)")
        stop_after services-healthy-again
        return
    elif [ "$health_rc" -eq 1 ] || [ "$health_rc" -eq 4 ]; then
        observed+=("not every expected service came back to 'running' and 'healthy' within ${LIMIT} s:$(said services-healthy-again 'NOT HEALTHY[^:]*:')")
        [ "$health_rc" -ne 4 ] \
            || mandatory+=("the state of an expected service could not be determined at all after the restart:$(said services-healthy-again 'NOT DETERMINED[^:]*:')")
        stop_after services-healthy-again
        return
    elif [ "$health_rc" -ne 0 ]; then
        mandatory+=("the state of the six services after the restart was not observed (services-healthy-again exit $health_rc)")
        stop_after services-healthy-again
        return
    fi

    # --- 4. show the restart: an issued command is not a restart -----------
    hx "$A" metrics-after "c=\$(curl -s -m 30 -o \"$ENVD/metrics.post-restart.json\" -w '%{http_code}' \"\$CTRL/metrics\"); printf 'metrics %s\n' \"\$c\"; cat \"$ENVD/metrics.post-restart.json\" 2> /dev/null; printf '\n'; [ \"\$c\" = 200 ]"
    need metrics-after $? "the controller process after the restart was not read" || return
    gx "$A" containers-after "$(containers_script)"
    need containers-after $? "the containers' ids and start instants were not recorded after the restart" || return
    keep_record containers-after containers.post-restart.txt "the containers after the restart" || return
    # 0 the restart was shown, 1 it was not (naming what did not change), 2
    # there is nothing to judge. Neither 1 nor 2 demonstrates persistence.
    ex "$A" restart-shown "$PY" -c '
import json, os, sys
env, expected = sys.argv[1], [s for s in sys.argv[2].split(",") if s]


def containers(path):
    found = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 4 and parts[0] == "container":
                found[parts[1]] = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
    return found


def instant(value):
    """A docker start instant as a comparable key, or None when it is not one."""
    if not isinstance(value, str) or not value.endswith("Z") or "T" not in value:
        return None
    head, _, fraction = value[:-1].partition(".")
    if len(head) != 19 or head[10] != "T" or not head[:4].isdigit():
        return None
    if fraction and not fraction.isdigit():
        return None
    return (head, fraction.ljust(9, "0")[:9])


def started_at(path):
    with open(path, encoding="utf-8") as fh:
        value = json.load(fh)["started_at"]
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s carries no started_at" % path)
    return value


try:
    before = containers(os.path.join(env, "containers.persist-before.txt"))
    after = containers(os.path.join(env, "containers.post-restart.txt"))
    was = started_at(os.path.join(env, "metrics.persist-before.json"))
    now = started_at(os.path.join(env, "metrics.post-restart.json"))
except (KeyError, OSError, ValueError) as exc:
    print("the records of the restart could not be read: %s" % exc)
    sys.exit(2)
print("controller started_at: %s -> %s" % (was, now))
unreadable = []
for name in expected:
    for label, record in (("before", before), ("after", after)):
        fields = record.get(name)
        if not fields or instant(fields.get("started")) is None or not fields.get("id") \
                or fields.get("id") == "unknown":
            unreadable.append("%s %s the restart" % (name, label))
if unreadable:
    print("the container records do not name every expected service with a usable id and "
          "start instant: " + ", ".join(unreadable))
    sys.exit(2)
not_shown = []
if now == was:
    not_shown.append("the controller started_at did not change (%s)" % was)
for name in expected:
    old, new = before[name], after[name]
    print("%s: id %s -> %s, started %s -> %s"
          % (name, old["id"][:12], new["id"][:12], old["started"], new["started"]))
    if old["id"] == new["id"]:
        not_shown.append("the container id of %s did not change (%s)" % (name, old["id"][:12]))
    elif instant(new["started"]) <= instant(old["started"]):
        not_shown.append("%s did not start later than before the restart (%s, then %s)"
                         % (name, old["started"], new["started"]))
if not_shown:
    for what in not_shown:
        print("NOT SHOWN: %s" % what)
    sys.exit(1)
print("RESTART SHOWN: the controller process is new (%s, then %s) and every one of the %d "
      "expected containers is a new object that started later" % (was, now, len(expected)))
' "$ENVD" "$EXPECT_SERVICES"
    local shown_rc=$?
    if [ "$shown_rc" -eq 1 ]; then
        mandatory+=("the restart was not shown:$(said restart-shown 'NOT SHOWN:')")
        stop_after restart-shown
        return
    elif [ "$shown_rc" -ne 0 ]; then
        mandatory+=("$(step_note restart-shown "$shown_rc" "the restart was not shown: it could not be judged from the records (restart-shown exit $shown_rc)")")
        stop_after restart-shown
        return
    fi

    # --- 6. after, before anything is published ----------------------------
    hx "$A" snapshot-after "\$REC snap --prefix \$P/$RUN --label post-restart --like persist-before --ditto-url \"\$DITTO\""
    need snapshot-after $? "the 'post-restart' twin snapshot was not taken" || return
    # 'same' exits 0 when every device is identical and 4 when one is
    # DIFFERENT: 4 is the system answering, anything else is no comparison.
    hx "$A" twin-state-same "\$REC same --prefix \$P/$RUN persist-before post-restart"
    local same_rc=$?
    if [ "$same_rc" -eq 4 ]; then
        observed+=("the twin state stored before the restart is not the state that came back ('same' reported DIFFERENT)")
    elif [ "$same_rc" -ne 0 ]; then
        # The comparison of the two snapshots is one of the mandatory records
        # of this demonstration: when it was not made, the steps after it
        # cannot be trusted to say anything about the state that came back, so
        # the sequence stops here as it does for every other mandatory step.
        mandatory+=("$(step_note twin-state-same "$same_rc" "the two twin snapshots were not compared (twin-state-same exit $same_rc)")")
        stop_after twin-state-same
        return
    fi
    hx "$A" twin-after "$(twin_script "$ENVD/twin.post-restart.json" after)"
    local twin_after_rc=$?
    if [ "$twin_after_rc" -eq 4 ]; then
        # THE defect this driver exists to find: the stack came back and the
        # thing is gone, because the volume did not hold it. That is the system
        # answering - a valid negative RESULT - and never a reading that failed.
        observed+=("the twin's stored state did not survive the restart:$(said twin-after 'TWIN ABSENT:')")
        stop_after twin-after
        return
    fi
    need twin-after "$twin_after_rc" "the twin was not read through the API after the restart:$(said twin-after 'STOP:')" || return
    gx "$A" events-after "$(events_script)"
    need events-after $? "the event log record count of this run was not read after the restart" || return

    # --- 1 and 7. the stored state, and what the restart may reset ---------
    local before_records after_records
    before_records=$(events_records events-before) || before_records=""
    after_records=$(events_records events-after) || after_records=""
    if [ -z "$before_records" ] || [ -z "$after_records" ]; then
        mandatory+=("the event log record count was not read on both sides of the restart, so nothing shows that nothing was published between the two snapshots")
        stop_after events-after
        return
    fi
    # 0 the stored state came back unchanged and nothing was published,
    # 1 the stored state changed (the system answering), 2 there is nothing to
    # judge, 3 something WAS published between the two snapshots, so this is
    # not the quiet restart the demonstration requires.
    ex "$A" stored-state "$PY" -c '
import json, os, sys
env, run, read_before, read_after = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
KEYS = ("last_run_id", "last_seq", "accepted_count")
COUNTERS = ("accepted", "rejected", "duplicate", "failed", "dropped", "queue_depth")


class StateGone(Exception):
    """The twin came back and the state this run stored in it did not.

    A body that could not be READ at all (no file, no JSON, not an object) is
    a reading that was not made; a twin that IS there and whose stored fields
    are not is the system answering, and after the restart that is the
    persistence defect this driver exists to find.
    """


def whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def ingestion(path):
    with open(path, encoding="utf-8") as fh:
        twin = json.load(fh)
    if not isinstance(twin, dict):
        raise ValueError("%s is not a JSON object" % path)
    thing = twin.get("thingId")
    if not isinstance(thing, str) or not thing:
        raise StateGone("%s carries no thingId" % path)
    feature = ((twin.get("features") or {}).get("ingestion") or {}).get("properties") or {}
    fields = {key: feature.get(key) for key in KEYS}
    if not isinstance(fields["last_run_id"], str) or not whole(fields["last_seq"]) \
            or not whole(fields["accepted_count"]):
        raise StateGone("%s carries no usable ingestion feature (%s)" % (path, ", ".join(KEYS)))
    return thing, fields


try:
    thing_before, before = ingestion(os.path.join(env, "twin.persist-before.json"))
except StateGone as exc:
    # BEFORE the restart there is nothing to compare with: the demonstration
    # has no stored state to start from, which is not a result about survival.
    print("the twin read before the restart does not carry the state of this run: %s" % exc)
    sys.exit(2)
except (OSError, ValueError) as exc:
    print("the stored state could not be read on both sides of the restart: %s" % exc)
    sys.exit(2)
try:
    thing_after, after = ingestion(os.path.join(env, "twin.post-restart.json"))
except StateGone as exc:
    # AFTER it, the same absence is the system answering: the thing came back
    # from the volumes without the state that was stored in it.
    print("NOT PERSISTED: the stored state did not come back: %s" % exc)
    sys.exit(1)
except (OSError, ValueError) as exc:
    print("the stored state could not be read on both sides of the restart: %s" % exc)
    sys.exit(2)
try:
    with open(os.path.join(env, "metrics.post-restart.json"), encoding="utf-8") as fh:
        reading = json.load(fh)
    counters = {key: reading[key] for key in COUNTERS}
    if not all(whole(value) for value in counters.values()):
        raise ValueError("the /metrics reading after the restart carries no whole counters")
    records_before, records_after = int(read_before), int(read_after)
except (KeyError, OSError, TypeError, ValueError) as exc:
    print("the stored state could not be read on both sides of the restart: %s" % exc)
    sys.exit(2)
print("twin before the restart: %s %s" % (thing_before, before))
print("twin after the restart:  %s %s" % (thing_after, after))
print("event log records of %s: %d before, %d after" % (run, records_before, records_after))
print("/metrics after the restart (per PROCESS, never persisted, so 0 again is expected "
      "and is not loss): %s" % counters)
if before["last_run_id"] != run:
    print("the twin read before the restart carries last_run_id %s, not %s: it does not hold "
          "the state of this run and nothing is concluded from it" % (before["last_run_id"], run))
    sys.exit(2)
# Only MORE is a publication: a count that GREW means records were ingested
# between the two snapshots, which is the quiet this demonstration rests on
# being broken. A count that FELL is the opposite - stored state that did not
# come back - and is judged below, as the result it is.
published = []
if records_after > records_before:
    print("NOT QUIET: the event log of %s grew from %d to %d records" % (run, records_before, records_after))
    published.append("the event log grew")
if after["accepted_count"] > before["accepted_count"]:
    print("NOT QUIET: the twin accepted_count rose from %s to %s"
          % (before["accepted_count"], after["accepted_count"]))
    published.append("the twin accepted_count rose")
moved = ["%s=%s" % (key, counters[key]) for key in COUNTERS if counters[key] != 0]
if moved:
    print("NOT QUIET: the new controller process has already counted " + ", ".join(moved))
    published.append("the new process already counted")
if published:
    print("the requirement that nothing is published between the two snapshots was not held")
    sys.exit(3)
changed = ["%s (%s, then %s)" % (key, before[key], after[key])
           for key in KEYS if before[key] != after[key]]
if thing_after != thing_before:
    changed.append("thingId (%s, then %s)" % (thing_before, thing_after))
if records_after < records_before:
    changed.append("the event log record count (%d, then %d)" % (records_before, records_after))
if changed:
    print("NOT PERSISTED: the stored state did not come back unchanged: " + ", ".join(changed))
    sys.exit(1)
print("STATE PERSISTED: %s came back from the volumes with last_run_id %s, last_seq %s and "
      "accepted_count %s, and nothing was published between the two reads"
      % (thing_after, after["last_run_id"], after["last_seq"], after["accepted_count"]))
' "$ENVD" "$RUN" "$before_records" "$after_records"
    local stored_rc=$?
    case "$stored_rc" in
        0) ;;
        1) observed+=("the twin's stored state did not survive the restart:$(said stored-state 'NOT PERSISTED:')") ;;
        3) mandatory+=("the requirement that nothing is published between the two snapshots was not held:$(said stored-state 'NOT QUIET:')") ;;
        *) mandatory+=("$(step_note stored-state "$stored_rc" "the stored state was not judged (stored-state exit $stored_rc): there is nothing to conclude from")") ;;
    esac
}

[ "${#prerequisite[@]}" -eq 0 ] && steps

# --- the verdicts ----------------------------------------------------------
# What the check SAW is stated first and never disappears behind a verdict
# about the check itself. An observation that stopped the steps after it says
# which they were, rather than calling the record complete.
seen=""
[ "${#observed[@]}" -eq 0 ] || seen="observed: $(printf '%s; ' "${observed[@]}")"
# The state the guest is left in is part of every ending of this driver, not
# only of the happy one: it is read from what the restart step itself
# reported, and it decides what the operator does first.
restarted=$(stack_note)
next_first=$(stack_next)
if [ "${#prerequisite[@]}" -ne 0 ]; then
    headline "$A" "the check did not run: $(printf '%s ' "${prerequisite[@]}")($restarted)" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "${seen}prerequisite failed: $(printf '%s; ' "${prerequisite[@]}")$restarted; not run: ${skipped[*]}" \
        --next-action "STOP: the persistence check did not run as a protocol check; $next_first; fix the cause and repeat it under a new attempt")
elif [ "${#mandatory[@]}" -ne 0 ]; then
    outcome=inconclusive
    [ "${#observed[@]}" -eq 0 ] || outcome=fail
    headline "$A" "the persistence was NOT demonstrated: ${mandatory[0]} ($restarted)" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome "$outcome" \
        --reason "${seen}the persistence across a restart was NOT demonstrated: $(printf '%s; ' "${mandatory[@]}")$restarted${skipped[*]:+; not run: ${skipped[*]}}" \
        --next-action "STOP: $next_first; read console/ and environment/")
elif [ "${#observed[@]}" -ne 0 ]; then
    headline "$A" "${observed[0]} ($restarted)" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome fail \
        --reason "${seen}$restarted, and this is what the system did${skipped[*]:+; not run: ${skipped[*]}}" \
        --next-action "STOP: $next_first; preserve this attempt and fix only that blocking issue before G2 is presented again under a new attempt")
else
    headline "$A" "the twin's stored state survived the restart and the stack came back" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "the restart was shown (a new controller process and six new container objects, each started later), the stack came back ready and healthy, and the twin's stored state is the same on both sides of it with nothing published between the two snapshots" \
        --next-action "publish the G2 evidence capsule and present the gate for the decision; the acceptance itself stays with Rui")
fi
driver_exit "$A"
