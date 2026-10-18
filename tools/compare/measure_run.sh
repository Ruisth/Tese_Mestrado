#!/bin/bash
# tools/compare/measure_run.sh <scenario> <run-id> <plan.json> - ONE measured execution of the minimal
# Yocto / Debian 13 comparison (order of 2026-10-18), with the existing tools and nothing more:
#
#   1. work disks restored from the measured base (measure_base.sh), sha256 verified;
#   2. `tf.sh <scenario> apply` - the host-monotonic instants it records: launch (immediately before
#      the QEMU exec), first ssh success, six healthy, first /ready 200;
#   3. functional_check.sh: one event from one test device to its twin (its own run id <run-id>.func
#      and a seed derived from the run's seed) - the instant of the confirmed twin;
#   4. REST: 120 s with no publication, memory of the whole guest sampled at 1 Hz; then df -P -k of
#      / and /var/lib/docker, and the SUT environment record;
#   5. LOAD: the harness run of the plan entry (the frozen nominal condition: 120 s warm-up, 600 s at
#      11.2 msg/s, 60 s confirmation window), the per-container collector, memory sampled at 1 Hz;
#   6. DRAIN by the runbook helper through tools/session/proof_hook_drained.sh (130 s quiet, cap
#      900 s; reaching the cap is a result, not a reason to wait longer); the events file after it;
#   7. final /metrics and guest state; `tf.sh <scenario> stop`; QEMU confirmed ended.
#
# Everything is written under $EGW_COMPARE_ROOT/measure/runs/<run-id>/ (timeline.json with every
# instant on the host monotonic clock, the two memory CSVs, df, the drain transcript, the post-drain
# events, the lifecycle records, SHA256SUMS) and the harness's own raw directory under
# $EGW_COMPARE_ROOT/measure/harness/raw/<run-id>/ (sealed by the harness). One execution, never a
# repetition: a failed step is recorded, the guest is closed in a controlled way and the run exits
# non-zero; a result of the system under test (a drain that reached its cap, late or lost
# confirmations) is a result, recorded, and never a driver failure. No QEMU process is ever killed.
#
# Exit: 0 the execution ran end to end and the guest is closed (whatever the system's results);
#       1 an instrumentation step failed (data preserved, close attempted); 2 a prerequisite or
#       guard refused (nothing started); 5 the controlled stop failed (guest left as it is).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"
[ $# -eq 3 ] || { echo "usage: measure_run.sh <scenario> <run-id> <plan.json>" >&2; exit 2; }
scenario=$1
RID=$2
PLAN=$3
scenario_load "$scenario"
scenario_dirs
printf '%s' "$RID" | grep -Eq '^[A-Za-z0-9._-]{1,64}$' || die "run-id '$RID' is not ^[A-Za-z0-9._-]{1,64}$"

REPO=$(cd "$HERE/../.." && pwd)
MEASURE=$COMPARE_ROOT/measure
BASE=$MEASURE/base/$scenario
HARNESS=$MEASURE/harness
RUN=$MEASURE/runs/$RID
BIN=$MEASURE/bin
VENV=${EGW_EXEC_VENV:-$COMPARE_EXEC/venv}
PY=$VENV/bin/python
SECRETS=${EGW_COMPARE_SECRETS_ENV:-$HOME/egw-tcg/.env}
HELPERS=${EGW_COMPARE_RUNBOOK_HELPERS:-$HOME/egw-tcg/itest-helpers.sh}
CA=$S_DIR/state/ca.crt
TUNNEL_CTL=$S_DIR/state/tunnel.ctl
CTRL=http://127.0.0.1:8000
REST_S=${EGW_COMPARE_REST_S:-120}
HEALTH_STEP_S=${EGW_COMPARE_HEALTH_STEP_S:-5}
SSH_STEP_S=${EGW_COMPARE_SSH_STEP_S:-5}
ACCEPT_STEP_S=${EGW_COMPARE_ACCEPT_STEP_S:-3}
DRAIN_QUIET_S=${DRAIN_QUIET_S:-130}
DRAIN_STEP_S=${DRAIN_STEP_S:-5}
DRAIN_LIMIT_S=${DRAIN_LIMIT_S:-900}
EXPECT_SERVICES=egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1

# --- the plan entry ---------------------------------------------------------------------------------
[ -r "$PLAN" ] || die "plan not readable: $PLAN"
ENTRY=$(python3 - "$PLAN" "$RID" << 'PY'
import json, sys
plan = json.load(open(sys.argv[1], encoding="utf-8"))
rid = sys.argv[2]
entry = next((r for r in plan.get("runs", []) if r.get("run_id") == rid), None)
if entry is None:
    print("missing"); sys.exit(0)
comp = plan.get("comparison", {}).get("runs", {}).get(rid) or entry.get("comparison") or {}
print(entry.get("status", ""), entry.get("seed", ""), comp.get("scenario", ""), comp.get("pair", ""), comp.get("order_in_pair", ""),
      entry.get("condition_id", ""), entry.get("duration_s", ""), entry.get("warmup_s", ""), entry.get("rate_msg_s", ""))
PY
) || die "the plan could not be read as JSON: $PLAN"
[ "$ENTRY" != missing ] || die "run id '$RID' is not in the plan $PLAN"
read -r P_STATUS SEED P_SCENARIO PAIR ORDER P_COND P_DUR P_WARM P_RATE <<< "$ENTRY"
[ "$P_STATUS" = planned ] || die "plan entry '$RID' is '$P_STATUS', not planned (one execution per entry, never a repetition)"
[ -z "$P_SCENARIO" ] || [ "$P_SCENARIO" = "$SCENARIO" ] || die "plan entry '$RID' belongs to scenario '$P_SCENARIO', not '$SCENARIO'"
printf '%s' "$SEED" | grep -Eq '^[0-9]{1,10}$' || die "plan entry '$RID' carries no integer seed"
[ "$P_COND" = nominal ] || die "plan entry '$RID' is condition '$P_COND', not nominal"

# --- prerequisites (nothing starts if any is missing) -----------------------------------------------
for tool in ssh scp curl ss python3 sha256sum cp git; do command -v "$tool" > /dev/null 2>&1 || die "host tool missing: $tool"; done
[ -x "$PY" ] || die "venv python missing: $PY (EGW_EXEC_VENV)"
"$PY" -c 'import egw_experiments, egw_simulator' > /dev/null 2>&1 || die "egw_experiments/egw_simulator are not importable from $PY"
[ -r "$SECRETS" ] || die "secrets file missing or unreadable: $SECRETS"
n=$(grep -v "^[[:space:]]*#" "$SECRETS" | grep -c CHANGE_ME); [ "$n" = 0 ] || die "placeholders remain in $SECRETS"
[ -r "$HELPERS" ] || die "the runbook helper file is not readable: $HELPERS (the drain helper lives there)"
[ -s "$BASE/SHA256SUMS" ] && [ -s "$BASE/root.qcow2" ] && [ -s "$BASE/data.img" ] || die "no measured base for $SCENARIO: run measure_base.sh $SCENARIO first ($BASE)"
[ -s "$HERE/guest_meminfo_sampler.sh" ] || die "guest_meminfo_sampler.sh missing beside this script"
[ -s "$REPO/tools/session/proof_hook_drained.sh" ] || die "tools/session/proof_hook_drained.sh missing in $REPO"
[ -s "$REPO/src/deployment/scripts/fetch-collector-output.sh" ] || die "fetch-collector-output.sh missing in $REPO"
[ ! -e "$RUN" ] || die "run directory exists: $RUN (never replaced)"
[ ! -e "$HARNESS/raw/$RID" ] || die "harness raw directory exists: $HARNESS/raw/$RID (never replaced)"
pilot_session_open && die "a pilot session is open ($COMPARE_EXEC/current_session)"
if o=$(qemu_others); then echo "$o" >&2; die "another qemu-system-aarch64 is running"; elif [ $? -eq 2 ]; then die "pgrep could not answer"; fi
own_pid > /dev/null 2>&1 && die "the $SCENARIO guest is running already: close it first"
busy=$(ss -ltn 2> /dev/null | grep -E "[:.](${COMPARE_SSH_PORT}|${COMPARE_MQTT_PORT}|8000|8080) " || true)
[ -z "$busy" ] || { echo "$busy" >&2; die "a host port of the profile or of the tunnel is busy"; }
[ "$DRAIN_QUIET_S" -ge 130 ] 2> /dev/null || die "DRAIN_QUIET_S=$DRAIN_QUIET_S is below the runbook's 130 s"

mkdir -p "$RUN" "$BIN" "$HARNESS" "$MEASURE/logs" || die "cannot create $RUN"
LOG=$RUN/measure.log
STEPS=$RUN/steps.tsv
printf 'n\tstep\trc\tseconds\n' > "$STEPS"
exec > >(tee -a "$LOG") 2>&1
echo "MEASURE $SCENARIO $RID: $(utc_now) run dir $RUN"
COMMIT=$(git -C "$REPO" rev-parse HEAD 2> /dev/null || echo unknown)
DIRTY=$(git -C "$REPO" status --porcelain 2> /dev/null | wc -l)
FUNC_RID=$RID.func
FUNC_SEED=$("$PY" -c 'import sys; from egw_experiments.plan_gen import derive_run_seed; print(derive_run_seed(int(sys.argv[1]), sys.argv[2]))' "$SEED" "$FUNC_RID")
echo "commit $COMMIT (dirty lines $DIRTY) seed $SEED functional run $FUNC_RID seed $FUNC_SEED pair ${PAIR:-?} order ${ORDER:-?}"

# ssh/scp wrappers with this scenario's settings: single executables, as the harness hooks and the
# collector fetch helper need (they are run as one argv, without a shell).
GSSH=$BIN/gssh-$SCENARIO
GSCP=$BIN/gscp-$SCENARIO
cat > "$GSSH" << EOF
#!/bin/sh
exec ssh -i '$COMPARE_SSH_KEY' -p '$COMPARE_SSH_PORT' -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile='$S_KNOWN_HOSTS' -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR "\$@"
EOF
cat > "$GSCP" << EOF
#!/bin/sh
exec scp -i '$COMPARE_SSH_KEY' -P '$COMPARE_SSH_PORT' -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile='$S_KNOWN_HOSTS' -o ConnectTimeout=10 -o LogLevel=ERROR "\$@"
EOF
chmod 0755 "$GSSH" "$GSCP"

# --- bookkeeping ------------------------------------------------------------------------------------
N=0
FAILED=0
STOP_RC=0
declare -A T=()   # host-monotonic instants, by name
mark() { T[$1]=$(uptime_s); }
step() {   # step NAME CMD...: run, keep rc and duration; a non-zero rc marks the run's instrumentation failed
    local name=$1 t0 t1 rc
    shift
    N=$((N + 1))
    t0=$(uptime_s)
    "$@"
    rc=$?
    t1=$(uptime_s)
    printf '%s\t%s\t%s\t%s\n' "$N" "$name" "$rc" "$(awk -v a="$t0" -v b="$t1" 'BEGIN { printf "%.1f", b - a }')" >> "$STEPS"
    echo "[$(utc_now)] $name rc=$rc"
    return $rc
}
must() { step "$@" || { FAILED=1; echo "  -> instrumentation step failed: $1"; return 1; }; }
jnum() { [ -n "${1:-}" ] && [ "$1" != null ] && printf '%s' "$1" || printf 'null'; }
fetch_file() {   # fetch_file REMOTE LOCAL: copy a guest file and verify its sha256 against the guest's
    local remote=$1 local=$2 rsum lsum
    rsum=$("$GSSH" egw@127.0.0.1 "sha256sum '$remote'" 2> /dev/null | cut -d' ' -f1) || return 1
    "$GSCP" -q "egw@127.0.0.1:$remote" "$local" || return 1
    lsum=$(sha256sum "$local" | cut -d' ' -f1)
    [ -n "$rsum" ] && [ "$rsum" = "$lsum" ] || { echo "fetch_file: sha256 differs for $remote"; return 1; }
    return 0
}

# --- the tunnel to the guest's loopback APIs (controller 8000, Ditto 8080), as functional_check.sh ----
TUNNEL_OPEN=0
tunnel_ssh() { ssh -S "$TUNNEL_CTL" -O "$1" -o LogLevel=ERROR egw@127.0.0.1; }
tunnel_close() {
    [ "$TUNNEL_OPEN" -eq 1 ] || return 0
    TUNNEL_OPEN=0
    tunnel_ssh exit > /dev/null 2>&1 || echo "WARNING: the tunnel master did not answer 'exit' ($TUNNEL_CTL)"
}
tunnel_open() {
    tunnel_ssh check > /dev/null 2>&1 && { echo "a tunnel master already answers on $TUNNEL_CTL"; return 1; }
    ssh -f -N -M -S "$TUNNEL_CTL" -o ExitOnForwardFailure=yes -i "$COMPARE_SSH_KEY" -p "$COMPARE_SSH_PORT" \
        -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$S_KNOWN_HOSTS" \
        -o ConnectTimeout=10 -o LogLevel=ERROR -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 egw@127.0.0.1 || return 1
    TUNNEL_OPEN=1
    tunnel_ssh check > /dev/null 2>&1
}
trap tunnel_close EXIT

# --- the record, written whatever happened ------------------------------------------------------------
HARNESS_RC=null
DRAIN_RC=null
DRAIN_RESULT=not-run
FUNC_RESULT=not-run
write_timeline() {
    python3 - "$RUN/timeline.json" << PY
import json
null = None
rec = {
    "scenario": "$SCENARIO", "run_id": "$RID", "pair": $(jnum "$PAIR"), "order_in_pair": $(jnum "$ORDER"), "seed": $SEED,
    "commit": "$COMMIT", "repo_dirty_lines": $DIRTY, "plan": "$PLAN", "utc_written": "$(utc_now)",
    "condition": {"id": "$P_COND", "duration_s": $(jnum "$P_DUR"), "warmup_s": $(jnum "$P_WARM"), "rate_msg_s": $(jnum "$P_RATE"), "rest_s": $REST_S},
    "probe_cadence_s": {"ssh": $SSH_STEP_S, "ready": $HEALTH_STEP_S, "accept": $ACCEPT_STEP_S, "drain": $DRAIN_STEP_S},
    "uptime_s": {
        "launch": $(jnum "${T[launch]:-}"), "ssh_ok": $(jnum "${T[ssh_ok]:-}"), "healthy": $(jnum "${T[healthy]:-}"), "ready": $(jnum "${T[ready]:-}"),
        "func_accepted": $(jnum "${T[func_accepted]:-}"), "func_twin": $(jnum "${T[func_twin]:-}"),
        "rest_start": $(jnum "${T[rest_start]:-}"), "rest_end": $(jnum "${T[rest_end]:-}"),
        "load_start": $(jnum "${T[load_start]:-}"), "load_end": $(jnum "${T[load_end]:-}"),
        "drain_start": $(jnum "${T[drain_start]:-}"), "drain_end": $(jnum "${T[drain_end]:-}"),
        "stop_requested": $(jnum "${T[stop_requested]:-}"), "qemu_gone": $(jnum "${T[qemu_gone]:-}")
    },
    "functional": {"run_id": "$FUNC_RID", "seed": $FUNC_SEED, "result": "$FUNC_RESULT"},
    "harness": {"run_id": "$RID", "exit": $HARNESS_RC, "base_dir": "$HARNESS", "raw_dir": "$HARNESS/raw/$RID"},
    "drain": {"result": "$DRAIN_RESULT", "exit": $DRAIN_RC, "quiet_s": $DRAIN_QUIET_S, "limit_s": $DRAIN_LIMIT_S},
    "stop_exit": $STOP_RC, "instrumentation_failed": $FAILED
}
json.dump(rec, open("$RUN/timeline.json", "w", encoding="utf-8"), indent=2)
open("$RUN/timeline.json", "a", encoding="utf-8").write("\n")
PY
}
seal() {
    local f
    for f in "$S_MANIFEST" "$S_DIR/state/argv.txt" "$S_DIR/state/provision.json" "$S_DIR/state/launch" "$S_DIR/state/ssh_ok" "$S_DIR/state/started_utc"; do
        [ -e "$f" ] && cp -p "$f" "$RUN/" 2> /dev/null
    done
    cp -p "$S_DIR"/logs/up-*.log "$S_DIR"/logs/provision-*.log "$S_DIR"/logs/stop-*.log "$RUN/" 2> /dev/null
    [ -s "$S_DIR/state/console" ] && cp -p "$(cat "$S_DIR/state/console")" "$RUN/" 2> /dev/null
    write_timeline
    (cd "$RUN" && find . -type f ! -name SHA256SUMS | LC_ALL=C sort | sed 's#^\./##' | xargs -d '\n' sha256sum > SHA256SUMS)
}
close_guest() {
    tunnel_close
    mark stop_requested
    step tf-stop bash "$HERE/tf.sh" "$SCENARIO" stop
    STOP_RC=$?
    if own_pid > /dev/null 2>&1; then STOP_RC=5; echo "STOP: the guest is still running after the controlled stop; it was not killed"; else mark qemu_gone; fi
    step qemu-others bash -c '. "$1/lib.sh"; scenario_load "$2"; o=$(qemu_others); rc=$?; case $rc in 0) echo "other QEMU present:"; echo "$o"; exit 1 ;; 1) echo "no qemu-system-aarch64 left"; exit 0 ;; *) echo "pgrep could not answer"; exit 2 ;; esac' _ "$HERE" "$SCENARIO" || FAILED=1
}
finish() {   # finish RESULT: seal and end with the exit code the record implies
    seal
    echo "== steps"; cat "$STEPS"
    echo "MEASURE $SCENARIO $RID: result=$1 harness_exit=$HARNESS_RC drain=$DRAIN_RESULT stop_exit=$STOP_RC out=$RUN"
    [ "$STOP_RC" = 0 ] || exit 5
    [ "$FAILED" = 0 ] || exit 1
    exit 0
}

# --- 1. disks from the measured base ---------------------------------------------------------------------
restore_disks() {
    rm -f "$S_DIR/state/launch" "$S_DIR/state/ssh_ok" "$S_DIR/state/provision.json"
    cp --sparse=always "$BASE/root.qcow2" "$S_ROOT_DISK" && cp --sparse=always "$BASE/data.img" "$S_DATA_DISK" || return 1
    (cd "$S_DIR/disks" && sha256sum -c --quiet "$BASE/SHA256SUMS") || { echo "restored disks do not match the measured base"; return 1; }
    cp -p "$BASE/base.json" "$RUN/base.json" 2> /dev/null
    return 0
}
must restore-disks restore_disks || { echo "nothing started"; FAILED=1; write_timeline; exit 2; }

# --- 2. boot and stack by the final command ----------------------------------------------------------------
if ! must tf-apply env EGW_COMPARE_HEALTH_STEP_S="$HEALTH_STEP_S" EGW_COMPARE_SSH_STEP_S="$SSH_STEP_S" bash "$HERE/tf.sh" "$SCENARIO" apply; then
    close_guest
    finish apply-failed
fi
T[launch]=$(cat "$S_DIR/state/launch" 2> /dev/null || true)
T[ssh_ok]=$(cat "$S_DIR/state/ssh_ok" 2> /dev/null || true)
read -r T[healthy] T[ready] <<< "$(python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); print(d.get("uptime_healthy_s"), d.get("uptime_ready_s"))' "$S_DIR/state/provision.json" 2> /dev/null | sed 's/None/null/g')"
echo "instants: launch ${T[launch]:-?} ssh_ok ${T[ssh_ok]:-?} healthy ${T[healthy]:-?} ready ${T[ready]:-?}"

# --- 3. one event to its twin ----------------------------------------------------------------------------
mkdir -p "$RUN/functional"
if step functional env EGW_COMPARE_ACCEPT_STEP_S="$ACCEPT_STEP_S" bash "$HERE/functional_check.sh" "$SCENARIO" "$FUNC_RID" "$FUNC_SEED"; then FUNC_RESULT=pass; else FUNC_RESULT=fail; fi
FUNC_DIR=$(ls -d "$S_DIR"/results/functional-*-"$FUNC_RID" 2> /dev/null | tail -n 1)
if [ -n "$FUNC_DIR" ] && [ -s "$FUNC_DIR/check.json" ]; then
    cp -rp "$FUNC_DIR"/. "$RUN/functional/"
    read -r T[func_accepted] T[func_twin] <<< "$(python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); print(d.get("uptime_accepted_s"), d.get("uptime_twin_s"))' "$FUNC_DIR/check.json" | sed 's/None/null/g')"
fi
if [ "$FUNC_RESULT" != pass ]; then
    echo "the gateway is not functional on this boot: a result of the system, recorded; no load is applied to a gateway that did not pass its event"
    close_guest
    finish functional-failed
fi

# --- 4. rest: memory of the whole guest at 1 Hz, then df and the SUT record ----------------------------------
must tunnel-open tunnel_open || { close_guest; finish tunnel-failed; }
must sampler-copy "$GSCP" -q "$HERE/guest_meminfo_sampler.sh" "egw@127.0.0.1:/tmp/guest_meminfo_sampler.sh" || { close_guest; finish sampler-copy-failed; }
mark rest_start
must rest "$GSSH" egw@127.0.0.1 "sh /tmp/guest_meminfo_sampler.sh /tmp/meminfo-$RID-rest.csv --duration $REST_S --interval 1"
mark rest_end
must rest-fetch fetch_file "/tmp/meminfo-$RID-rest.csv" "$RUN/meminfo-rest.csv"
df_before_load() { "$GSSH" egw@127.0.0.1 'df -P -k / /var/lib/docker' > "$RUN/df-before-load.txt"; }
host_disks() { bash "$HERE/compare_env.sh" disks "$SCENARIO" > "$RUN/host-disks-before-load.txt"; }
sut_capture() {   # the same labels validate.sh records: an emulated ARM64 comparison guest, never native
    "$GSSH" egw@127.0.0.1 "cd /opt/egw/deployment && EGW_PROVIDER='QEMU 8.2.7 TCG (qemu-system-native) on WSL2 Ubuntu-24.04, Windows 11 x86-64' EGW_REGION='local-workstation' EGW_INSTANCE_TYPE='qemu -machine virt -cpu cortex-a76 -smp 4 -m 8192; ARM64 EMULATED; scenario $SCENARIO' EGW_SHARED_VCPU_NOTE='TCG emulation on a shared x86-64 host; comparison guest; never native ARM64' sh scripts/capture-sut-environment.sh /opt/egw/evidence/sut_environment.json" > /dev/null \
        && "$GSCP" -q egw@127.0.0.1:/opt/egw/evidence/sut_environment.json "$RUN/sut_environment.json"
}
must df-before-load df_before_load
step host-disks-before-load host_disks
must sut-environment sut_capture
[ "$FAILED" = 0 ] || { close_guest; finish rest-failed; }

# --- 5. load: the harness run of the plan entry, memory sampled meanwhile ------------------------------------
must load-sampler-start "$GSSH" egw@127.0.0.1 "sudo -n systemd-run --unit egw-meminfo-$RID --collect sh /tmp/guest_meminfo_sampler.sh /tmp/meminfo-$RID-load.csv --interval 1" || { close_guest; finish sampler-start-failed; }
mark load_start
export EGW_FETCH_SSH=$GSSH EGW_FETCH_SCP=$GSCP
(
    # The simulator password reaches the harness from the .env sourced in this subshell only.
    # shellcheck disable=SC1090
    . "$SECRETS" > /dev/null 2>&1 || exit 97
    [ -n "${MOSQUITTO_SIMULATOR_PASSWORD:-}" ] || exit 98
    exec "$PY" -m egw_experiments run --run-id "$RID" --plan "$PLAN" --base-dir "$HARNESS" \
        --broker 127.0.0.1 --port "$COMPARE_MQTT_PORT" --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert "$CA" \
        --controller-url "$CTRL" --sut-env-from "$RUN/sut_environment.json" --execution-mode tcg-emulated \
        --fetch-events-cmd "$GSCP -q egw@127.0.0.1:/opt/egw/deployment/data/events/{run_id}/events.jsonl {dest}" \
        --expect-services "$EXPECT_SERVICES" \
        --collector-start-cmd "$GSSH egw@127.0.0.1 sudo -n systemd-run --unit egw-resources-{run_id} --collect sh /opt/egw/deployment/scripts/collect-resources.sh /tmp/resources-{run_id}.csv --duration {duration_s} --expect-services {expect_services}" \
        --collector-stop-cmd "$GSSH egw@127.0.0.1 sudo -n systemctl stop egw-resources-{run_id}" \
        --collector-fetch-cmd "sh $REPO/src/deployment/scripts/fetch-collector-output.sh egw@127.0.0.1 /tmp/resources-{run_id}.csv {dest}"
) > "$RUN/harness.stdout.txt" 2> "$RUN/harness.stderr.txt"
HARNESS_RC=$?
mark load_end
printf '%s\tharness\t%s\t%s\n' "$((N + 1))" "$HARNESS_RC" "$(awk -v a="${T[load_start]}" -v b="${T[load_end]}" 'BEGIN { printf "%.1f", b - a }')" >> "$STEPS"; N=$((N + 1))
echo "[$(utc_now)] harness exit=$HARNESS_RC (a non-zero exit is the harness's verdict on the run, recorded; see harness.stderr.txt)"

# --- 6. drain by the runbook helper, then the events after it -------------------------------------------------
mark drain_start
DRAIN_QUIET_S=$DRAIN_QUIET_S DRAIN_STEP_S=$DRAIN_STEP_S DRAIN_LIMIT_S=$DRAIN_LIMIT_S CTRL=$CTRL EGW_CLONE=$REPO \
    bash "$REPO/tools/session/proof_hook_drained.sh" "$RID" > "$RUN/drain.txt" 2>&1
DRAIN_RC=$?
mark drain_end
if [ "$DRAIN_RC" -eq 0 ] && grep -q '^drained: queue_depth 0' "$RUN/drain.txt"; then DRAIN_RESULT=quiet
elif grep -q '^STOP: drained: no quiet window' "$RUN/drain.txt"; then DRAIN_RESULT=gave-up
else DRAIN_RESULT=error; FAILED=1; fi
printf '%s\tdrain\t%s\t%s\n' "$((N + 1))" "$DRAIN_RC" "$(awk -v a="${T[drain_start]}" -v b="${T[drain_end]}" 'BEGIN { printf "%.1f", b - a }')" >> "$STEPS"; N=$((N + 1))
echo "[$(utc_now)] drain $DRAIN_RESULT (exit $DRAIN_RC)"
step post-drain-events fetch_file "/opt/egw/deployment/data/events/$RID/events.jsonl" "$RUN/events.post-drain.jsonl" || FAILED=1
step warmup-events fetch_file "/opt/egw/deployment/data/events/$RID.warmup/events.jsonl" "$RUN/events.warmup.jsonl" || true

# --- 7. final state, close ---------------------------------------------------------------------------------
step load-sampler-stop "$GSSH" egw@127.0.0.1 "sudo -n systemctl stop egw-meminfo-$RID" || FAILED=1
step load-fetch fetch_file "/tmp/meminfo-$RID-load.csv" "$RUN/meminfo-load.csv" || FAILED=1
metrics_final() { curl -fsS --max-time 30 "$CTRL/metrics" > "$RUN/metrics.final.json"; }
guest_final() {
    "$GSSH" egw@127.0.0.1 'df -P -k / /var/lib/docker; echo; free -k; echo; docker ps -a --format "{{.Names}} {{.Status}}"; echo; echo oom_lines=$(sudo -n dmesg 2>/dev/null | grep -ci "out of memory")' > "$RUN/guest-final.txt"
}
step metrics-final metrics_final || FAILED=1
step guest-final guest_final || FAILED=1
close_guest
finish done
