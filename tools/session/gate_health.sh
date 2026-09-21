#!/bin/bash
# G2 closure, section 4.B of the work order of 2026-09-20: the gate's
# PRECONDITION SNAPSHOT, and nothing else. This driver starts nothing, changes
# nothing and publishes nothing; it only records what the stack answers.
# Usage: gate_health.sh   (no arguments; run it after preflight.sh)
#
# The engineering preflight passes with the controller's health check still
# 'starting', because there a container whose check has not concluded is judged
# by its state alone. G2 is stricter: all six expected services must be RUNNING
# and HEALTHY. The stricter wait lives in guest_common.sh and is shared with
# persistence.sh, so the gate and the check after the restart are the same one.
#
# Five steps, all mandatory and each recorded:
#   1 the six expected services running and healthy, polled about every
#     EGW_HEALTH_STEP_S seconds until EGW_HEALTH_LIMIT_S has passed, with every
#     sample and its instant kept, so the transition is visible;
#   2 /health answers 200 with {"status":"ok"} and /ready answers 200; both
#     bodies are kept in environment/;
#   3 /metrics: accepted, rejected, duplicate, failed, dropped and queue_depth
#     are 0, beside the started_at of the controller PROCESS that baseline
#     belongs to (the counters are per process, never cumulative across two);
#   4 the identities actually running: for each of the six containers its image
#     reference, image id, repo digest, container id and start instant, and the
#     controller build identity recorded on the guest, kept in environment/;
#   5 the publishing path's TLS material as CONFIGURATION, never as secrets:
#     the broker's listener and certificate paths, the CA's own fingerprint and
#     the modes of the private material - never a byte of it.
#
# Observing the system fail is a result; failing to observe is an invalid
# measurement. A service that never becomes healthy, an endpoint that answers
# something else, a counter that is not 0 and a broker that is not configured
# for TLS are the stack ANSWERING, and the answer is not the gate's state:
# instrumentation valid, system outcome fail, exit 1. Only a record that could
# not be made at all - a guest that cannot be reached, a body that cannot be
# read, an identity or a file mode that could not be recorded - leaves the
# snapshot invalid (exit 3). The reason names the FIRST thing that was not as
# G2 requires, and a counter that is not 0 is answered with the documented
# controlled lifecycle, never with deleted data or an edited counter.
#
# THREE READINGS THAT WERE NEVER MADE ARE NOT THREE ANSWERS. curl prints the
# code 000 and writes an empty body when it never reached the controller (its
# own exit 7 for a refused connection, 28 for a timeout), so each of the three
# endpoint readings keeps curl's status beside the code, and a reading that
# was not made is invalid instrumentation, never "the controller answered
# 000".
# The same rule holds of the identities: a repo digest an inspect could not
# read, and an empty controller build identity, record no identity, so neither
# passes this gate as one. What the final line carries, beside the code, is the
# FIRST such thing, so the operator reads on the one line whether the
# controller was stuck starting or was never reached at all.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
# A stray argument is a prerequisite (2), never the 1 of a valid negative
# result: this driver takes none, and one passed by mistake means the caller
# meant something else.
[ "$#" -eq 0 ] || driver_stop "$EXIT_PREREQUISITE" "usage: gate_health.sh (no arguments)"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
LIMIT=$(healthy_seconds EGW_HEALTH_LIMIT_S 1800) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_LIMIT_S is not a whole number of seconds; nothing was recorded"
STEP=$(healthy_seconds EGW_HEALTH_STEP_S 15) \
    || driver_stop "$EXIT_PREREQUISITE" "EGW_HEALTH_STEP_S is not a whole number of seconds; nothing was recorded"
# The guest's record of the controller image that was built, beside the six
# container identities (runbook 4.5 / 5.5 interlock).
CTRL_IDENTITY=${EGW_CONTROLLER_IDENTITY:-/opt/egw/images/egw-controller-0.1.0-arm64.identity.txt}
DEPLOYED=${EGW_DEPLOYED_DIR:-/opt/egw/deployment}
# The port the smartwatch publishes on: the gate's TLS claim is about THAT
# listener, not about any listener the broker happens to carry.
TLS_PORT=${EGW_MQTT_TLS_PORT:-8883}
case $TLS_PORT in
    '' | *[!0-9]*) driver_stop "$EXIT_PREREQUISITE" "EGW_MQTT_TLS_PORT is not a port number; nothing was read" ;;
esac
# Every parameter that is written into a guest script is checked ONCE, here,
# before anything is read: a value that could not be written as the literal it
# is would make the guest run something other than what this driver says.
for value in "$DEPLOYED" "$CTRL_IDENTITY" "$EXPECT_SERVICES"; do
    guest_literal "$value" \
        || driver_stop "$EXIT_PREREQUISITE" "'$value' cannot be written into a guest command as the literal it is; nothing was read"
done
A=$(new_attempt "G2 gate preconditions" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
trap 'driver_interrupt "$A"' INT TERM
ENVD=$A/environment

observed=()      # the stack answered, and the answer is not the gate's state
mandatory=()     # a record of this gate could not be made
FIRST=""         # the first thing that was not as G2 requires
NEXT=""          # the next action the first such thing calls for

# first_note TEXT: the reason names the FIRST thing that was not as G2
# requires; later ones are kept in their own group and printed after it.
first_note() {
    [ -n "$FIRST" ] || FIRST=$1
}

# saw TEXT [NEXT-ACTION]: the stack answered and the answer is not the gate's.
saw() {
    observed+=("$1")
    first_note "$1"
    [ -n "$NEXT" ] || [ "$#" -lt 2 ] || NEXT=$2
}

# missed TEXT: a record this gate is made of could not be made.
missed() {
    mandatory+=("$1")
    first_note "$1"
}

# said NAME PREFIX: what the step NAME itself printed after PREFIX, read from
# its console record and joined onto one line, or nothing at all. A reason
# names what a step reported, never a status alone.
said() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    [ -n "$f" ] && [ -f "$f" ] || return 0
    sed -n "s/^$2//p" "$f" | tr '\n' ' '
}

# keep_record NAME FILE WHAT: copy the console record of NAME into
# environment/ under FILE, so the package holds it as evidence and not only as
# a console file. A record that was not kept is a record that was not made.
keep_record() {
    local f
    f=$(ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1)
    if [ -n "$f" ] && [ -f "$f" ] && cp "$f" "$ENVD/$2"; then
        return 0
    fi
    missed "$3 was not kept in environment/$2"
    return 1
}

# The identity of the clean clone is part of the snapshot: a git that cannot be
# read is recorded as such (identity_error) and stops the driver.
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$IDENTITIES" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"gate\": \"G2\", \"expected_services\": \"$EXPECT_SERVICES\", \"healthy_limit_s\": $LIMIT, \"healthy_step_s\": $STEP, \"publishes\": \"nothing: this driver only reads\"}" \
    'expected_artefacts=["environment/health.json", "environment/ready.json", "environment/metrics.json", "environment/container_identities.txt", "environment/egw-controller-build-identity.txt", "environment/tls_configuration.txt"]') \
    || PREREQ="the attempt fields could not be recorded"
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || PREREQ=${PREREQ:-"the identity of the clean clone could not be read (see identities.identity_error)"}

# not_run REASON: a prerequisite of the snapshot itself failed, so no gate was
# recorded. Nothing was started or changed either way: this driver never does.
not_run() {
    headline "$A" "$1: the gate's precondition snapshot was NOT recorded" || true
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "$1; the gate's precondition snapshot was NOT recorded" \
        --next-action "read console/; nothing was started, changed or published")
    driver_exit "$A"
}
[ -z "${PREREQ:-}" ] || not_run "$PREREQ"

# --- 1. the six expected services running and healthy ----------------------
healthy_wait "$A" services-healthy "$LIMIT" "$STEP"
health_rc=$?
if [ "$health_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    missed "$(capture_note services-healthy)"
elif [ "$health_rc" -eq "$EXIT_NOT_REACHED" ]; then
    # The wait never ran on the guest: the readiness wait did not answer, and
    # that is not the six services failing to be healthy - nothing at all was
    # observed about them.
    missed "the readiness wait did not answer because it never reached the guest (services-healthy exit $health_rc): the state of the six expected services was NOT observed"
elif [ "$health_rc" -eq 1 ] || [ "$health_rc" -eq 4 ]; then
    saw "not every expected service reached 'running' and 'healthy' within ${LIMIT} s:$(said services-healthy 'NOT HEALTHY[^:]*:')" \
        "STOP: read console/ for every sample; G2 needs all six services healthy before the flow is run"
fi
if [ "$health_rc" -eq 2 ] || [ "$health_rc" -eq 4 ]; then
    missed "the state of an expected service could not be determined at all:$(said services-healthy 'NOT DETERMINED[^:]*:')"
elif [ "$health_rc" -ne 0 ] && [ "$health_rc" -ne 1 ] && [ "$health_rc" -ne 4 ] \
    && [ "$health_rc" -ne "$EXIT_CAPTURE_LOST" ] && [ "$health_rc" -ne "$EXIT_NOT_REACHED" ]; then
    missed "the readiness wait did not answer (services-healthy exit $health_rc): the state of the six services was not observed"
fi

# --- 2 and 3. the controller's own answers ---------------------------------
# One reading of the three endpoints, each body kept beside its HTTP code AND
# beside curl's own exit status, and then two verdicts over what was kept: what
# the endpoints answered, and what the counter baseline is. A 503 is the
# system's answer; a 200 whose body cannot be read is a reading that was not
# made; and a request that never reached the controller at all - curl's 7 (a
# connection that was refused) or 28 (a request that timed out), which write an
# empty body and print the code 000 - is not an answer of any kind. The curl
# status is recorded beside the code for each of the three readings, because
# '000' alone cannot be told from a controller that answered.
endpoints_script() {
    printf "ENVD='%s'\n" "$ENVD"
    cat << 'HOST_ENDPOINTS'
: > "$ENVD/http_codes.txt" || { echo "STOP: $ENVD/http_codes.txt could not be written"; exit 1; }
for p in health ready metrics; do
    c=$(curl -s -m 30 -o "$ENVD/$p.json" -w '%{http_code}' "$CTRL/$p")
    rc=$?
    [ -n "$c" ] || c=000
    printf '%s %s %s\n' "$p" "$c" "$rc" >> "$ENVD/http_codes.txt"
    printf -- '--- %s (http %s, curl exit %s) ---\n' "$p" "$c" "$rc"
    cat "$ENVD/$p.json" 2> /dev/null
    printf '\n'
done
HOST_ENDPOINTS
}
hx "$A" controller-endpoints "$(endpoints_script)"
endpoints_rc=$?
if [ "$endpoints_rc" -ne 0 ]; then
    missed "$(step_note controller-endpoints "$endpoints_rc" "the controller's endpoints were not read (controller-endpoints exit $endpoints_rc)")"
fi

# The two verdicts are steps of their own, so their stdout, stderr and exit
# code reach console/ and commands.jsonl even when the reading was never made.
# Each exits 0 (as G2 requires), 1 (the system answered otherwise) or 2 (there
# is nothing to judge), and 2 is never read as the 1 of a system failure.
ex "$A" endpoints-verdict "$PY" -c '
import json, os, sys
env = sys.argv[1]
codes, exits = {}, {}
try:
    with open(os.path.join(env, "http_codes.txt"), encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 3:
                codes[parts[0]], exits[parts[0]] = parts[1], parts[2]
    health_code, ready_code = codes["health"], codes["ready"]
except (KeyError, OSError) as exc:
    print("the answer of /health or /ready was not recorded: %s" % exc)
    sys.exit(2)
print("http codes: %s" % codes)
print("curl exit statuses: %s" % exits)
# A request that never reached the controller is not an answer of the
# controller: curl could not connect (7), gave up (28) or failed some other
# way, and the 000 it printed is the absence of a code, not a code. Nothing is
# concluded about the gate from a reading that was not made.
unread = ["/%s was not read (curl exit %s, HTTP code %s)" % (name, exits[name], codes[name])
          for name in ("health", "ready") if exits[name] != "0" or codes[name] == "000"]
if unread:
    print("NOT READ: " + "; ".join(unread)
          + ": the controller was not reached, so it answered nothing")
    sys.exit(2)
bad = []
if health_code != "200":
    bad.append("/health answered %s, not 200" % health_code)
if ready_code != "200":
    bad.append("/ready answered %s, not 200" % ready_code)
if health_code == "200":
    try:
        with open(os.path.join(env, "health.json"), encoding="utf-8") as fh:
            body = json.load(fh)
        status = body.get("status") if isinstance(body, dict) else None
    except (OSError, ValueError) as exc:
        print("/health answered 200 and its body could not be read: %s" % exc)
        sys.exit(2)
    print("/health body status: %s" % (status,))
    if status != "ok":
        bad.append("/health answered 200 with status %s, not ok" % (status,))
if bad:
    print("NOT THE GATE: " + "; ".join(bad))
    sys.exit(1)
print("ENDPOINTS AT THE GATE: /health 200 with status ok, /ready 200")
' "$ENVD"
ep_rc=$?
if [ "$ep_rc" -eq 1 ]; then
    saw "the controller's endpoints are not at the gate:$(said endpoints-verdict 'NOT THE GATE:')" \
        "STOP: /health and /ready are the gate's readiness; diagnose before the flow is run"
elif [ "$ep_rc" -ne 0 ]; then
    missed "$(step_note endpoints-verdict "$ep_rc" "what /health and /ready answered was not judged (endpoints-verdict exit $ep_rc): there is nothing to conclude from:$(said endpoints-verdict 'NOT READ:')")"
fi

ex "$A" counters-verdict "$PY" -c '
import json, os, sys
env = sys.argv[1]
names = ("accepted", "rejected", "duplicate", "failed", "dropped", "queue_depth")
try:
    codes, exits = {}, {}
    with open(os.path.join(env, "http_codes.txt"), encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 3:
                codes[parts[0]], exits[parts[0]] = parts[1], parts[2]
    code, status = codes["metrics"], exits["metrics"]
except (KeyError, OSError) as exc:
    print("the /metrics reading was not recorded: %s" % exc)
    sys.exit(2)
# As for /health and /ready: a request that never reached the controller
# answered nothing, and its 000 is the absence of a code.
if status != "0" or code == "000":
    print("NOT READ: /metrics was not read (curl exit %s, HTTP code %s): the controller was "
          "not reached, so there is no counter baseline to judge" % (status, code))
    sys.exit(2)
# A code the controller itself answered is its own answer, whatever body came
# with it.
if code != "200":
    print("NOT THE GATE: /metrics answered %s, not 200" % code)
    sys.exit(1)
try:
    with open(os.path.join(env, "metrics.json"), encoding="utf-8") as fh:
        body = json.load(fh)
    if not isinstance(body, dict):
        raise ValueError("the /metrics body is not an object")
except (OSError, ValueError) as exc:
    print("the /metrics reading was not recorded: %s" % exc)
    sys.exit(2)
values = {}
for key in names:
    value = body.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        print("the /metrics reading carries no usable %s: nothing is concluded from it" % key)
        sys.exit(2)
    values[key] = value
started = body.get("started_at")
if not isinstance(started, str) or not started.strip():
    print("the /metrics reading carries no started_at: this baseline belongs to no identified controller process")
    sys.exit(2)
print("controller process started_at: %s" % started)
print(json.dumps(values, indent=2))
moved = ["%s=%d" % (key, values[key]) for key in names if values[key] != 0]
if moved:
    print("NOT THE GATE: the counter baseline of this process is not zero (" + ", ".join(moved) + ")")
    sys.exit(1)
print("COUNTER BASELINE AT ZERO: every counter and queue_depth is 0 for the process started at %s" % started)
' "$ENVD"
ct_rc=$?
if [ "$ct_rc" -eq 1 ]; then
    saw "the controller's counter baseline is not the gate's:$(said counters-verdict 'NOT THE GATE:')" \
        "with the queue empty, restart the controller through the documented lifecycle (docs/setup/qemu_integrated_gateway.md 6.5) so that the baseline is a fresh process; never delete data and never edit a counter"
elif [ "$ct_rc" -ne 0 ]; then
    missed "$(step_note counters-verdict "$ct_rc" "the counter baseline was not judged (counters-verdict exit $ct_rc): there is nothing to conclude from:$(said counters-verdict 'NOT READ:')")"
fi

# --- 4. the identities actually running ------------------------------------
# identities_script: what is running, read from the containers themselves. The
# parameters are written as plain assignments in front of a QUOTED
# here-document, so the guest text is never expanded twice; it runs under
# BusyBox ash and holds no bashism.
identities_script() {
    printf "EXPECT='%s'\nIDFILE='%s'\nDEPLOYED='%s'\n" "$EXPECT_SERVICES" "$CTRL_IDENTITY" "$DEPLOYED"
    cat << 'GUEST_IDENTITIES'
cd "$DEPLOYED" || { echo "STOP: $DEPLOYED could not be entered"; exit 1; }
rc=0
IFS=,
set -- $EXPECT
unset IFS
for s in "$@"; do
    cid=$(docker inspect -f '{{.Id}}' "$s" 2> /dev/null) || rc=1
    img=$(docker inspect -f '{{.Config.Image}}' "$s" 2> /dev/null) || rc=1
    iid=$(docker inspect -f '{{.Image}}' "$s" 2> /dev/null) || rc=1
    sat=$(docker inspect -f '{{.State.StartedAt}}' "$s" 2> /dev/null) || rc=1
    # An image BUILT on this guest carries no repo digest at all, and that is
    # a fact about the image ('none'), read from an inspect that answered. An
    # inspect that did NOT answer read no identity, which is not the same
    # thing and is never recorded as one.
    if dig=$(docker image inspect -f '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}none{{end}}' "$iid" 2> /dev/null); then
        [ -n "$dig" ] || dig=none
    else
        dig=NOT-READ
        rc=1
    fi
    echo "identity $s image=${img:-unknown} image_id=${iid:-unknown} repo_digest=$dig container_id=${cid:-unknown} started=${sat:-unknown}"
    [ -n "$cid" ] && [ -n "$img" ] && [ -n "$iid" ] && [ -n "$sat" ] || rc=1
done
echo '## the controller build identity recorded on the guest'
# An identity file that is empty is an identity that was not read: the gate
# records the controller image that was built, not the existence of a file.
[ -s "$IDFILE" ] || { echo "STOP: $IDFILE holds no controller build identity"; exit 1; }
cat "$IDFILE" || rc=1
exit $rc
GUEST_IDENTITIES
}
gx "$A" container-identities "$(identities_script)"
id_rc=$?
if [ "$id_rc" -ne 0 ]; then
    missed "$(step_note container-identities "$id_rc" "the identities of the six running containers were not recorded (container-identities exit $id_rc)")"
fi
keep_record container-identities container_identities.txt "the identities of the running containers" || true
gcp "$A" controller-build-identity "egw@127.0.0.1:$CTRL_IDENTITY" "$ENVD/egw-controller-build-identity.txt"
build_rc=$?
if [ "$build_rc" -ne 0 ]; then
    missed "$(step_note controller-build-identity "$build_rc" "the controller build identity recorded on the guest was not fetched into environment/ (controller-build-identity exit $build_rc)")"
elif [ ! -s "$ENVD/egw-controller-build-identity.txt" ]; then
    # A file that arrived empty records no identity: the gate is a snapshot of
    # what is running, and an identity that was not read is not an identity.
    missed "the controller build identity fetched from $CTRL_IDENTITY into environment/egw-controller-build-identity.txt is EMPTY: no build identity of the controller was recorded"
fi

# --- 5. the publishing path's TLS material, as configuration ---------------
# tls_script: the broker's own configuration, the CA's fingerprint and the
# modes of the private material. It reads no private byte: the key files are
# named and their modes recorded, never their contents. What it JUDGES is the
# gate's own claim: a TLS listener on the port the flow publishes on, with a
# certificate authority, a certificate and a key named, a negotiated version
# stated, and anonymous access refused. What the certificate paths point at is
# the deployed tree's content, which preflight.sh compares with the clean clone
# file by file. It answers 0 (the configuration is that), 1 (it is not: the
# system answering) or 2 (the record could not be made).
tls_script() {
    printf "DEPLOYED='%s'\n" "$DEPLOYED"
    printf "TLS_PORT='%s'\n" "$TLS_PORT"
    cat << 'GUEST_TLS'
cd "$DEPLOYED" || { echo "STOP: $DEPLOYED could not be entered"; exit 2; }
CONF=mosquitto/config/mosquitto.conf
[ -r "$CONF" ] || { echo "STOP: $CONF could not be read"; exit 2; }
setting() {
    sed -n "s/^[[:space:]]*$1[[:space:]][[:space:]]*//p" "$CONF" | tail -n 1
}
bad=
echo '## broker listener and TLS material, from mosquitto.conf (configuration, never secrets)'
grep -E '^[[:space:]]*(listener|protocol|cafile|certfile|keyfile|require_certificate|tls_version|allow_anonymous|password_file|acl_file)[[:space:]]' "$CONF" \
    || { echo "STOP: $CONF names no listener and no TLS material"; exit 2; }
for k in listener cafile certfile keyfile; do
    v=$(setting "$k")
    [ -n "$v" ] || bad="$bad $k(absent)"
done
# The gate's claim is about the path the flow publishes on, so the listener
# must be THAT port, and the version the broker will negotiate must be stated
# rather than left to a default nobody recorded. What the certificate paths
# point at is the deployed tree's own content, which the preflight compares
# with the clean clone file by file; this step judges the listener, the
# material's presence, the version and the refusal of anonymous access.
port=$(setting listener | cut -d' ' -f1)
[ "$port" = "$TLS_PORT" ] || bad="$bad listener=${port:-absent}(expected $TLS_PORT)"
tlsv=$(setting tls_version)
[ -n "$tlsv" ] || bad="$bad tls_version(absent)"
an=$(setting allow_anonymous)
[ "$an" = false ] || bad="$bad allow_anonymous=${an:-absent}"
# The certificate and the key this gate records must be the ones the BROKER
# reads, not paths this script decided on: a configuration naming other files
# would otherwise be recorded with the metadata of files nobody uses. Each
# configured path is a path inside the broker's own container, whose
# /mosquitto is this deployed tree's mosquitto/, so each is translated back
# into the tree and refused if it does not live there.
deployed_path() {
    case "$1" in
        /mosquitto/*) printf '%s' "mosquitto/${1#/mosquitto/}" ;;
        mosquitto/*) printf '%s' "$1" ;;
        *) return 1 ;;
    esac
}
echo '## the files the broker itself names, translated into the deployed tree'
for k in cafile certfile keyfile password_file acl_file; do
    v=$(setting "$k")
    [ -n "$v" ] || continue
    if d=$(deployed_path "$v"); then
        echo "$k $v -> $d"
        [ -e "$d" ] || { echo "STOP: $d, the broker's $k, is not in the deployed tree"; exit 2; }
    else
        echo "STOP: the broker's $k is $v, which is not under /mosquitto: this record cannot say what the broker reads"
        exit 2
    fi
done
CA=$(deployed_path "$(setting cafile)") || {
    echo 'STOP: the broker names no usable cafile, so the certificate authority of the publishing path cannot be recorded'
    exit 2
}
echo '## the certificate authority the broker itself names (never its private material)'
openssl x509 -in "$CA" -noout -subject -enddate -fingerprint -sha256 \
    || { echo "STOP: the fingerprint of $CA could not be read"; exit 2; }
echo '## modes and ownership of the material the broker names (never a byte of it)'
for k in cafile certfile keyfile password_file acl_file; do
    v=$(setting "$k")
    [ -n "$v" ] || continue
    f=$(deployed_path "$v") || continue
    [ -e "$f" ] || { echo "STOP: $f is not there, so its mode could not be recorded"; exit 2; }
    stat -c '%a %U:%G %s %n' "$f" || { echo "STOP: the mode of $f could not be read"; exit 2; }
done
[ -z "$bad" ] || { echo "NOT THE GATE: the publishing path is not TLS with anonymous access refused:$bad"; exit 1; }
echo "TLS AT THE GATE: the broker listens on $TLS_PORT with $tlsv and names a certificate authority, a certificate and a key that are in the deployed tree; allow_anonymous is false, which is the configuration and not an exercised refusal"
exit 0
GUEST_TLS
}
gx "$A" tls-configuration "$(tls_script)"
tls_rc=$?
if [ "$tls_rc" -eq 1 ]; then
    saw "the publishing path's configuration is not the gate's:$(said tls-configuration 'NOT THE GATE:')" \
        "STOP: G2 requires the publishing path to be TLS with anonymous access refused"
elif [ "$tls_rc" -ne 0 ]; then
    missed "$(step_note tls-configuration "$tls_rc" "the publishing path's TLS material was not recorded (tls-configuration exit $tls_rc)")"
fi
keep_record tls-configuration tls_configuration.txt "the publishing path's TLS configuration" || true

# --- the verdicts ----------------------------------------------------------
# A record that could not be made leaves the snapshot INVALID; a stack that
# answered something other than the gate's state is a valid negative result. A
# fault that was positively observed is never erased by a record that is
# missing: both are recorded, each in its own group, and the outcome stays
# 'fail' rather than becoming 'inconclusive'.
seen=""
[ "${#observed[@]}" -eq 0 ] || seen="not as G2 requires: $(printf '%s; ' "${observed[@]}")"
# The one line the operator reads names WHICH thing it was: a controller stuck
# 'starting' and a controller that was never reached are both non-zero and
# call for different actions.
if [ -n "$FIRST" ]; then
    headline "$A" "$FIRST" || true
else
    headline "$A" "the gate's preconditions hold: the six expected services are running and healthy and the controller is at the gate" || true
fi
if [ "${#mandatory[@]}" -ne 0 ]; then
    outcome=inconclusive
    [ "${#observed[@]}" -eq 0 ] || outcome=fail
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome "$outcome" \
        --reason "the first thing that was not as G2 requires: $FIRST. ${seen}the gate's snapshot is incomplete: $(printf '%s; ' "${mandatory[@]}")" \
        --next-action "${NEXT:-STOP: read console/ and environment/; this precondition snapshot was not recorded and cannot admit G2}")
elif [ "${#observed[@]}" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome fail \
        --reason "the first thing that was not as G2 requires: $FIRST. ${seen}every step of this snapshot was recorded: this is the stack's state as it was observed, and it is not the gate's precondition" \
        --next-action "${NEXT:-STOP: fix the stack before the G2 flow; this is a measured system state, not invalid instrumentation}")
else
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "the six expected services are running and healthy, /health answers 200 with status ok, /ready answers 200, every counter and queue_depth is 0 for the identified controller process, the six container identities and the controller build identity are recorded, and the publishing path is TLS with anonymous access refused" \
        --next-action "run the G2 flow on this gate: slice.sh <fresh run id> <a seed never used on this MongoDB volume>")
fi
driver_exit "$A"
