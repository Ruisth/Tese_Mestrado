#!/bin/sh
# probe-acl.sh — prove the Mosquitto ACL in both directions with known traffic
# (CONTRACTS.md §1; runbook test 9(d)/(e)). POSIX sh / BusyBox ash; runs ON THE
# GUEST, drives mosquitto_pub/mosquitto_sub INSIDE the broker container.
#
# Usage:  sh scripts/probe-acl.sh <tag>        tag: [A-Za-z0-9_-]+, unique per attempt
# Env:    EGW_DEPLOY_DIR   (default /opt/egw/deployment)
#         EGW_COMPOSE_ENV  (default images.lock.env; second --env-file)
#         ACL_PROBE_OUT    (default /opt/egw/evidence/itest-acl-<tag>)
#         ACL_PROBE_WINDOW (default 90; subscriber lifetime in seconds, -W)
#         ACL_PROBE_READY  (default 40; max polls for both SUBSCRIBE log lines)
# Exit:   0 PASS, 1 FAIL (ACL or anonymous refusal not enforced), 3 INCONCLUSIVE
#         (the positive control, the execution of a probe or the collection of
#         the evidence failed: nothing is proven either way), 2 usage or
#         precondition (bad tag or settings, no .env or one that the shell
#         cannot read to its end with status 0, a password missing,
#         evidence directory exists or cannot be written): NOTHING was run and
#         there is no verdict.txt.
#
# Verdict discipline: PASS needs POSITIVE evidence for every claim. A command
# that did not run, or ended in any way other than the one expected, is never
# read as a refusal, and its output is never read as a delivery: it makes the
# verdict INCONCLUSIVE.
#   - A DELIVERY is a line of a subscriber's stdout that starts with "c2dt/":
#     every subscriber uses -v on c2dt/#, so each delivered message is printed
#     as "<topic> <payload>". Any other byte on stdout is not a delivery (the
#     Docker engine writes exec start-up errors to the exec's STDOUT stream:
#     moby v25.0.9 api/server/router/container/exec.go) and not silence either:
#     "nothing received" needs a 0-byte stdout, anything else is INCONCLUSIVE.
#   - LIVENESS of both subscribers over P1..P4 is bounded in time, not assumed:
#     rc 27 means SIGALRM fired, i.e. WINDOW seconds after an alarm() that
#     mosquitto_sub cannot have set before it was started (client/sub_client.c),
#     so the session lasted at least until sub_start + WINDOW. P4 must have
#     returned GUARD seconds before that, and each subscriber's exec must be
#     seen to return after P4 did.
#   - A COUNT taken from the broker log (subscription lines per subscriber, the
#     accepted-session line of the anonymous client) is evidence only when the
#     collection is known to cover the run: a zero from a failed or partial
#     collection is absence of evidence. The collection counts as complete only
#     when all of this was observed: docker compose logs returned 0; its output
#     is not empty; the last broker log line that existed BEFORE the first
#     subscriber was started (the anchor, with the engine's per-line timestamp)
#     occurs exactly once in the last $TAIL lines collected after the run, so
#     the --tail window still starts before the run; grep did not fail; and
#     broker.txt has as many lines as a recount of the collection. Anything
#     else is INCONCLUSIVE, unless a security failure is positively shown
#     (a delivery, an accepted anonymous session): FAIL keeps precedence.
#     UNVERIFIED: docker compose logs --timestamps on the guest (Compose 2.26);
#     if it is refused the collection fails and the verdict is INCONCLUSIVE;
#     what the two calls wrote to stderr is kept in broker_logs.err (recorded
#     for the operator, not evaluated).
#   - The evidence directory is written to and read back before the run (exit
#     2 when that fails) and after the collection (INCONCLUSIVE when that
#     fails). This is necessary, not sufficient: a write lost while the run was
#     in progress (disk full for a moment) to a file whose expected content is
#     0 bytes cannot be told from silence afterwards.
#
# The probe topic c2dt/acl-probe/<tag> is inside the ACL rule c2dt/# but has
# three levels, so it never matches the controller's filter c2dt/+/+/telemetry:
# the controller receives none of the probe messages. No message is retained.
set -u

TAG=${1:-}
case "$TAG" in ''|*[!A-Za-z0-9_-]*) echo "usage: $0 <tag>   (tag: [A-Za-z0-9_-]+)" >&2; exit 2;; esac

DEPLOY=${EGW_DEPLOY_DIR:-/opt/egw/deployment}
ENV2=${EGW_COMPOSE_ENV:-images.lock.env}
OUT=${ACL_PROBE_OUT:-/opt/egw/evidence/itest-acl-$TAG}
WINDOW=${ACL_PROBE_WINDOW:-90}
READY_MAX=${ACL_PROBE_READY:-40}
GUARD=2     # seconds that must remain of the subscribers' window when P4 has returned
TAIL=400    # broker log lines read per collection (docker compose logs --tail)
is_num() { case "$1" in ''|*[!0-9]*) return 1;; esac; }
is_num "$WINDOW" && [ "$WINDOW" -gt "$GUARD" ] && is_num "$READY_MAX" ||
    { echo "ACL_PROBE_WINDOW (> $GUARD) and ACL_PROBE_READY must be whole numbers" >&2; exit 2; }
TOPIC="c2dt/acl-probe/$TAG"
CAFILE=/mosquitto/config/certs/ca.crt
# Exactly what mosquitto_sub 2.0.22 prints for an MQTT 3.1.1 CONNACK with return
# code 5 (client/sub_client.c my_connect_callback + lib/strings_mosq.c
# mosquitto_connack_string); main() then returns the CONNACK code, so rc is 5.
ANON_REFUSAL='Connection error: Connection Refused: not authorised.'

cd "$DEPLOY" || exit 2
[ -f .env ] || { echo "missing $DEPLOY/.env" >&2; exit 2; }
# .env is shell text read under set -u. If reading it ENDS the shell (a reference to an unset variable,
# a syntax error, an "exit"), the status would be the shell's own (bash 1 = this script's FAIL code) or
# the file's (exit 0 = PASS) although nothing was run: the trap turns every such end into exit 2. A
# syntax error that plain bash survives shows as a non-zero status of "." instead.
# UNVERIFIED: BusyBox ash (the trap on an aborting error; without it ash's own status, 2, is expected).
trap 'echo "reading $DEPLOY/.env ended the shell: nothing was run" >&2; exit 2' 0
set -a; . ./.env; ENV_RC=$?; set +a
trap - 0
[ "$ENV_RC" -eq 0 ] || { echo "reading $DEPLOY/.env returned $ENV_RC: nothing was run" >&2; exit 2; }
# Explicit test: the exit status of ${VAR:?} is the shell's own (dash 2, bash 1 = this script's FAIL code).
[ -n "${MOSQUITTO_SIMULATOR_PASSWORD:-}" ] && [ -n "${MOSQUITTO_CONTROLLER_PASSWORD:-}" ] ||
    { echo "MOSQUITTO_SIMULATOR_PASSWORD / MOSQUITTO_CONTROLLER_PASSWORD not set in $DEPLOY/.env" >&2; exit 2; }
[ -e "$OUT" ] && { echo "refusing to overwrite $OUT (use a new tag)" >&2; exit 2; }
mkdir -p "$OUT" || exit 2

# wcheck — a known line can be written to $OUT and read back (see header: necessary, not sufficient).
CANARY="acl-probe $TAG evidence write check"
wcheck() {
    _w=1
    if echo "$CANARY" 2>/dev/null >"$OUT/write_check.tmp" &&
       [ "$(cat "$OUT/write_check.tmp" 2>/dev/null)" = "$CANARY" ]; then _w=0; fi
    rm -f "$OUT/write_check.tmp" 2>/dev/null
    return "$_w"
}
wcheck || { rmdir "$OUT" 2>/dev/null; echo "evidence directory $OUT cannot be written and read back" >&2; exit 2; }

dc() { docker compose --env-file .env --env-file "$ENV2" "$@"; }

# now — whole seconds on a clock that a wall-clock step does not move (/proc/uptime;
# alarm() in mosquitto_sub is not moved by one either); epoch seconds where /proc is absent.
if [ -r /proc/uptime ]; then CLOCK=uptime; else CLOCK=epoch; fi
now() {
    if [ "$CLOCK" = uptime ]; then read -r _up _rest </proc/uptime; echo "${_up%%.*}"; else date +%s; fi
}

# sub LABEL USER PASSWORD — subscribes to c2dt/# for $WINDOW seconds (MQTT 3.1.1, QoS 1).
# <label>.end = when the exec RETURNED (an upper bound of the session's end: necessary, not sufficient).
sub() {
    dc exec -T -e MQTT_PW="$3" mosquitto sh -c \
        'exec mosquitto_sub -h localhost -p 8883 --cafile "$3" -V mqttv311 -i "$0" -u "$1" -P "$MQTT_PW" -t "c2dt/#" -q 1 -v -W "$2"' \
        "egw-acl-$TAG-$1" "$2" "$WINDOW" "$CAFILE" </dev/null >"$OUT/$1.out" 2>"$OUT/$1.err"
    echo $? >"$OUT/$1.rc"
    now >"$OUT/$1.end"
}

# pub LABEL USER PASSWORD PROTOCOL PAYLOAD — one QoS 1, non-retained message on $TOPIC.
pub() {
    dc exec -T -e MQTT_PW="$3" mosquitto sh -c \
        'exec mosquitto_pub -h localhost -p 8883 --cafile "$5" -V "$2" -i "$0" -u "$1" -P "$MQTT_PW" -t "$3" -q 1 -m "$4" -d' \
        "egw-acl-$TAG-$1" "$2" "$4" "$TOPIC" "$5" "$CAFILE" </dev/null >"$OUT/$1.txt" 2>&1
    echo $? >"$OUT/$1.rc"
}

count() { n=$(grep -c -F -- "$1" "$2" 2>/dev/null); echo "${n:-0}"; }
rc_of() { cat "$OUT/$1.rc" 2>/dev/null || echo missing; }
bytes_of() { if [ -f "$1" ]; then wc -c <"$1" | tr -d ' '; else echo missing; fi; }
# deliveries FILE — messages printed by mosquitto_sub -v on c2dt/#: lines that start with the namespace.
deliveries() { if [ -f "$1" ]; then n=$(grep -c '^c2dt/' "$1" 2>/dev/null); echo "${n:-0}"; else echo missing; fi; }
end_of() { e=$(cat "$OUT/$1.end" 2>/dev/null); if is_num "$e"; then echo "$e"; else echo missing; fi; }
# sub_logged LABEL — SUBSCRIBE lines of that probe client in the broker log (log_type subscribe).
sub_logged() {
    n=$(dc logs --no-color --tail "$TAIL" mosquitto 2>/dev/null | grep -c -F "egw-acl-$TAG-$1 1 c2dt/#")
    echo "${n:-0}"
}
both_subscribed() { [ "$(sub_logged ctl-sub)" -ge 1 ] && [ "$(sub_logged sim-sub)" -ge 1 ]; }

date -u +%Y-%m-%dT%H:%M:%SZ >"$OUT/started_utc.txt"

# 0. Anchor: the last broker log line that exists before any probe client does.
#    The collection after the run must still contain it (see header).
dc logs --no-color --timestamps --tail 1 mosquitto >"$OUT/broker_anchor.txt" 2>"$OUT/broker_logs.err"
ANCHOR_RC=$?
ANCHOR=$(tail -n 1 "$OUT/broker_anchor.txt" 2>/dev/null)

# 1. Two concurrent subscribers on c2dt/#: authorised (egw-controller: read) and
#    unauthorised (egw-simulator: write only). Client ids differ from the real
#    controller's, so its session is not taken over.
T_SUB0=$(now)   # no subscriber exists before this instant: a -W timeout (rc 27) cannot fire before T_SUB0 + WINDOW
sub ctl-sub egw-controller "$MOSQUITTO_CONTROLLER_PASSWORD" &
sub sim-sub egw-simulator  "$MOSQUITTO_SIMULATOR_PASSWORD" &

# 2. Wait until the broker has logged the subscription of EACH subscriber
#    (counted separately: two lines of one client must not stand in for the other).
i=0
while ! both_subscribed && [ "$i" -lt "$READY_MAX" ]; do sleep 1; i=$((i + 1)); done
READY_CTL=$(sub_logged ctl-sub)
READY_SIM=$(sub_logged sim-sub)

# 3. Known traffic, in this order. P1/P4 bracket the denied publishes so that
#    their absence cannot be explained by a subscriber that was not listening.
T_P1=missing; T_P4=missing
if [ "$READY_CTL" -ge 1 ] && [ "$READY_SIM" -ge 1 ]; then
    T_P1=$(now)
    pub p1-sim-pub    egw-simulator  "$MOSQUITTO_SIMULATOR_PASSWORD"  mqttv311 "acl-probe $TAG P1 user=egw-simulator"
    pub p2-ctl-pub    egw-controller "$MOSQUITTO_CONTROLLER_PASSWORD" mqttv311 "acl-probe $TAG P2 user=egw-controller"
    pub p3-ctl-pub-v5 egw-controller "$MOSQUITTO_CONTROLLER_PASSWORD" mqttv5   "acl-probe $TAG P3 user=egw-controller"
    pub p4-sim-pub    egw-simulator  "$MOSQUITTO_SIMULATOR_PASSWORD"  mqttv311 "acl-probe $TAG P4 user=egw-simulator"
    T_P4=$(now)
fi

# 4. Anonymous connection (allow_anonymous false): no credentials at all. MQTT
#    3.1.1 is pinned so that the refusal has one known form (CONNACK 5); -v so
#    that a delivery can be told from any other output.
dc exec -T mosquitto mosquitto_sub -h localhost -p 8883 --cafile "$CAFILE" -V mqttv311 \
    -i "egw-acl-$TAG-anon" -t 'c2dt/#' -v -W 10 </dev/null >"$OUT/anon.out" 2>"$OUT/anon.err"
echo $? >"$OUT/anon.rc"

wait    # both subscribers end by themselves after $WINDOW seconds
date -u +%Y-%m-%dT%H:%M:%SZ >"$OUT/finished_utc.txt"
dc logs --no-color --timestamps --tail "$TAIL" mosquitto >"$OUT/broker_tail.tmp" 2>>"$OUT/broker_logs.err"
LOGS_RC=$?
grep -F "egw-acl-$TAG" "$OUT/broker_tail.tmp" >"$OUT/broker.txt"
GREP_RC=$?      # 0 lines found, 1 none; anything else is an error (a failed redirect is 1 or 2: hence the recount below)

# Is the collection complete (see header)? Every reason is recorded in verdict.txt.
LOGS=complete; LOGS_WHY=
incomplete() { LOGS=incomplete; LOGS_WHY="$LOGS_WHY${LOGS_WHY:+; }$1"; }
LOG_LINES=missing; TAGGED_TMP=missing; TAGGED_TXT=missing; ANCHOR_N=0
if [ -f "$OUT/broker_tail.tmp" ]; then
    LOG_LINES=$(wc -l <"$OUT/broker_tail.tmp" | tr -d ' ')
    TAGGED_TMP=$(count "egw-acl-$TAG" "$OUT/broker_tail.tmp")
    if [ -n "$ANCHOR" ]; then n=$(grep -c -F -x -e "$ANCHOR" "$OUT/broker_tail.tmp" 2>/dev/null); ANCHOR_N=${n:-0}; fi
fi
[ -f "$OUT/broker.txt" ] && TAGGED_TXT=$(wc -l <"$OUT/broker.txt" | tr -d ' ')
if [ "$ANCHOR_RC" -ne 0 ] || [ -z "$ANCHOR" ]; then
    incomplete "no anchor line was read before the run (rc=$ANCHOR_RC)"
elif [ "$LOG_LINES" != missing ] && [ "$ANCHOR_N" != 1 ]; then
    incomplete "the anchor line occurs $ANCHOR_N times in the collection (must be 1: the last $TAIL lines do not provably cover the run)"
fi
[ "$LOGS_RC" -eq 0 ] || incomplete "docker compose logs returned $LOGS_RC"
case "$LOG_LINES" in
    missing) incomplete "the temporary file of the collection is missing";;
    0) incomplete "the collection is empty";;
esac
case "$GREP_RC" in 0|1) ;; *) incomplete "grep returned $GREP_RC";; esac
if [ "$TAGGED_TXT" = missing ]; then
    incomplete "broker.txt is missing"
elif [ "$TAGGED_TXT" != "$TAGGED_TMP" ]; then
    incomplete "broker.txt has $TAGGED_TXT lines, the collection has $TAGGED_TMP for this tag"
fi
rm -f "$OUT/broker_tail.tmp"
WRITE_END=ok; wcheck || WRITE_END=failed

# 5. Verdict.
A1=$(count "$TOPIC acl-probe $TAG P1 " "$OUT/ctl-sub.out")
A2=$(count "acl-probe $TAG P2 " "$OUT/ctl-sub.out")
A3=$(count "acl-probe $TAG P3 " "$OUT/ctl-sub.out")
A4=$(count "$TOPIC acl-probe $TAG P4 " "$OUT/ctl-sub.out")
U_BYTES=$(bytes_of "$OUT/sim-sub.out")
U_DELIV=$(deliveries "$OUT/sim-sub.out")
V5_DENIED=$(count "Not authorized" "$OUT/p3-ctl-pub-v5.txt")
# Subscribe lines over the whole run: more than one per subscriber means it
# reconnected, i.e. there was a gap in which a message could have been missed.
END_CTL=$(count "egw-acl-$TAG-ctl-sub 1 c2dt/#" "$OUT/broker.txt")
END_SIM=$(count "egw-acl-$TAG-sim-sub 1 c2dt/#" "$OUT/broker.txt")
ANON_RC=$(rc_of anon)
ANON_BYTES=$(bytes_of "$OUT/anon.out")
ANON_DELIV=$(deliveries "$OUT/anon.out")
ANON_REFUSED=$(count "$ANON_REFUSAL" "$OUT/anon.err")
# "New client connected from <ip>:<port> as <id> (p2, c1, k60)." is logged only for an ACCEPTED session.
ANON_ACCEPTED_LOG=$(count " as egw-acl-$TAG-anon (" "$OUT/broker.txt")
# Corroboration only (the client id on this line is UNVERIFIED for a refused CONNECT): not a criterion.
ANON_BROKER_LINES=$(count "egw-acl-$TAG-anon" "$OUT/broker.txt")

# Anonymous case: refused | accepted | inconclusive.
#   refused      = rc 5 AND the exact CONNACK-5 text on stderr AND nothing received AND no accepted session logged
#                  in a COMPLETE broker log collection (in an incomplete one "no line" is absence of evidence);
#   accepted     = the session was (or may have been) established: rc 0, rc 27 (alive when -W expired),
#                  a delivery (a "c2dt/..." line), or the broker's "New client connected ... as <anon id>" line;
#   inconclusive = everything else (docker/compose exec error 1/125/126/127/137, TLS or socket error,
#                  lookup error, unknown rc, empty stderr, missing files, stdout that is neither empty
#                  nor a delivery, e.g. an exec start-up error): the client never got a CONNACK 5.
ANON=inconclusive
if [ "$ANON_RC" = 5 ] && [ "$ANON_REFUSED" -ge 1 ] && [ "$ANON_BYTES" = 0 ] && [ "$ANON_ACCEPTED_LOG" -eq 0 ] &&
   [ "$LOGS" = complete ]; then
    ANON=refused
fi
if [ "$ANON_RC" = 0 ] || [ "$ANON_RC" = 27 ] || [ "$ANON_ACCEPTED_LOG" -ne 0 ]; then ANON=accepted; fi
case "$ANON_DELIV" in 0|missing) ;; *) ANON=accepted;; esac

# Liveness of both subscribers over P1..P4 (see header). All three must hold:
#   P4 returned at least GUARD seconds before T_SUB0 + WINDOW, the earliest instant at which a
#   subscriber that ended with rc 27 can have disconnected (whole-second readings: T_SUB0 is
#   rounded down and T_P4 + 1 is after the real return of P4, so GUARD 2 leaves a full second);
#   and the exec of EACH subscriber was seen to return after P4 did.
is_num "$T_SUB0" || T_SUB0=0      # unreadable clock: the bound below cannot hold, so INCONCLUSIVE
DEADLINE=$((T_SUB0 + WINDOW))
CTL_END=$(end_of ctl-sub)
SIM_END=$(end_of sim-sub)
LIVE=no
if [ "$T_SUB0" -gt 0 ] && is_num "$T_P4" && is_num "$CTL_END" && is_num "$SIM_END" &&
   [ $((T_P4 + GUARD)) -le "$DEADLINE" ] && [ "$CTL_END" -gt "$T_P4" ] && [ "$SIM_END" -gt "$T_P4" ]; then
    LIVE=yes
fi

report() {
    echo "tag=$TAG topic=$TOPIC window_s=$WINDOW subscribe_lines_before_publish: ctl-sub=$READY_CTL sim-sub=$READY_SIM; whole run: ctl-sub=$END_CTL sim-sub=$END_SIM (broker log rc=$LOGS_RC)"
    echo "authorised subscriber (egw-controller):   P1=$A1 P2=$A2 P3=$A3 P4=$A4 rc=$(rc_of ctl-sub)"
    echo "unauthorised subscriber (egw-simulator):  deliveries=$U_DELIV stdout_bytes=$U_BYTES rc=$(rc_of sim-sub)"
    echo "liveness: covered=$LIVE clock=$CLOCK sub_start=$T_SUB0 p1_start=$T_P1 p4_end=$T_P4 earliest_timeout=$DEADLINE (sub_start+window; p4_end+$GUARD must not exceed it) exec_end: ctl-sub=$CTL_END sim-sub=$SIM_END (each must exceed p4_end)"
    echo "publishers rc: P1=$(rc_of p1-sim-pub) P2=$(rc_of p2-ctl-pub) P3=$(rc_of p3-ctl-pub-v5) P4=$(rc_of p4-sim-pub); v5 'Not authorized' lines=$V5_DENIED"
    echo "anonymous: $ANON rc=$ANON_RC refusal_lines=$ANON_REFUSED deliveries=$ANON_DELIV stdout_bytes=$ANON_BYTES accepted_in_broker_log=$ANON_ACCEPTED_LOG broker_lines=$ANON_BROKER_LINES stderr=$(tr '\n' ' ' <"$OUT/anon.err" 2>/dev/null)"
    echo "evidence: broker_log=$LOGS${LOGS_WHY:+ ($LOGS_WHY)} checked: anchor_rc=$ANCHOR_RC collection_rc=$LOGS_RC collection_lines=$LOG_LINES tail=$TAIL anchor_found=$ANCHOR_N (must be 1) grep_rc=$GREP_RC tagged_lines: collection=$TAGGED_TMP broker.txt=$TAGGED_TXT; write_check (write and read back in the evidence directory): before_run=ok after_collection=$WRITE_END"
}
BODY=$(report)

VERDICT=PASS; CODE=0
# Positive control: the authorised path must demonstrably work, and both
# subscribers must have lived through the whole publish sequence: subscribed
# before P1, exactly one subscription each over the run (no reconnect), rc 27 =
# MOSQ_ERR_TIMEOUT (ended by -W and not by an error) and the time bounds above.
# "Nothing received" by the write-only user needs a 0-byte stdout: bytes that
# are not a delivery (an exec error) prove neither silence nor a delivery.
if [ "$READY_CTL" -lt 1 ] || [ "$READY_SIM" -lt 1 ] || [ "$END_CTL" -ne 1 ] || [ "$END_SIM" -ne 1 ] ||
   [ "$A1" -ne 1 ] || [ "$A4" -ne 1 ] || [ "$U_BYTES" != 0 ] || [ "$LIVE" != yes ] ||
   [ "$(rc_of ctl-sub)" != 27 ] || [ "$(rc_of sim-sub)" != 27 ] ||
   [ "$(rc_of p1-sim-pub)" != 0 ] || [ "$(rc_of p2-ctl-pub)" != 0 ] ||
   [ "$(rc_of p3-ctl-pub-v5)" != 0 ] || [ "$(rc_of p4-sim-pub)" != 0 ]; then
    VERDICT=INCONCLUSIVE; CODE=3
fi
# The anonymous refusal counts only when it was positively observed.
[ "$ANON" = refused ] || { VERDICT=INCONCLUSIVE; CODE=3; }
# Evidence: counts from an incomplete broker log collection, or files in a
# directory that can no longer be written, are absence of evidence, not a pass.
[ "$LOGS" = complete ] && [ "$WRITE_END" = ok ] || { VERDICT=INCONCLUSIVE; CODE=3; }
# Restriction: any delivery to the write-only user, or of a message published
# by the read-only user, or an accepted anonymous session, is a FAIL whatever
# the state of the positive control.
case "$U_DELIV" in 0|missing) ;; *) VERDICT=FAIL; CODE=1;; esac
if [ "$A2" -ne 0 ] || [ "$A3" -ne 0 ] || [ "$ANON" = accepted ]; then
    VERDICT=FAIL; CODE=1
fi
# verdict.txt must hold exactly what is printed; a PASS that could not be recorded is not reported as one.
printf '%s\n' "$BODY" "verdict=$VERDICT" 2>/dev/null >"$OUT/verdict.txt"
if [ "$(cat "$OUT/verdict.txt" 2>/dev/null)" != "$(printf '%s\n' "$BODY" "verdict=$VERDICT")" ]; then
    [ "$CODE" -ne 0 ] || { VERDICT=INCONCLUSIVE; CODE=3; }
    echo "probe-acl: $OUT/verdict.txt could NOT be written completely: the verdict below exists on this terminal only" >&2
fi
printf '%s\n' "$BODY" "verdict=$VERDICT"
exit "$CODE"
