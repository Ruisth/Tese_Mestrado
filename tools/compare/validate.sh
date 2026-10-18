#!/bin/bash
# tools/compare/validate.sh <scenario> - the functional validation of ONE comparison scenario, in the
# authorised sequence and nothing more: guards, prepare and start through Terraform, guest facts,
# provisioning of the same application stack, ONE synthetic event from one test device to its twin,
# final state, controlled stop through Terraform, proof that QEMU ended, results sealed.
#
# It is not a measurement: no load generator campaign, no repetition, no benchmark. One attempt;
# a failure is recorded and the close is still attempted (never a kill). Results and every log go
# to $EGW_COMPARE_ROOT/scenarios/<scenario>/results/validate-<stamp>/ with a SHA256SUMS.
#
# Exit: 0 every phase passed; 1 a validation phase failed (recorded; the guest was closed);
#       2 a prerequisite was missing (nothing started); 5 the controlled stop failed (guest left as is).
#
# validate.sh --resume <scenario> continues on a guest that is ALREADY running (its boot phase was
# recorded by an earlier run of this script that did not reach the close): the prerequisites then
# require the running guest instead of its absence, the apply is skipped, and every later phase
# runs and is recorded as usual. It never boots a second time.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"
RESUME=0
if [ "${1:-}" = --resume ]; then RESUME=1; shift; fi
[ $# -eq 1 ] || { echo "usage: validate.sh [--resume] <scenario>" >&2; exit 2; }
scenario=$1
scenario_load "$scenario"
scenario_dirs

VENV=${EGW_EXEC_VENV:-$COMPARE_EXEC/venv}
SECRETS=${EGW_COMPARE_SECRETS_ENV:-$HOME/egw-tcg/.env}
IMAGES_DIR=${EGW_IMAGES_DIR:-$HOME/egw-images}
OUT=$S_DIR/results/validate-$(stamp)
mkdir -p "$OUT"
STEPS=$OUT/steps.tsv
printf 'n\tphase\tstep\trc\tseconds\tfile\n' > "$STEPS"
N=0
FAILED=0
CLOSE_RC=0
T_START=$(uptime_s)

# step PHASE NAME CMD...: run one command, keep its output, record rc and duration (host monotonic).
step() {
    local phase=$1 name=$2 f t0 t1 rc
    shift 2
    N=$((N + 1))
    f=$OUT/$(printf '%02d' "$N")-$phase-$name.txt
    t0=$(uptime_s)
    "$@" > "$f" 2>&1
    rc=$?
    t1=$(uptime_s)
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$N" "$phase" "$name" "$rc" "$(awk -v a="$t0" -v b="$t1" 'BEGIN { printf "%.1f", b - a }')" "$(basename "$f")" >> "$STEPS"
    echo "[$(utc_now)] $phase/$name rc=$rc ($(basename "$f"))"
    return $rc
}
# must PHASE NAME CMD...: a step whose failure marks the validation failed (the close still runs).
must() { step "$@" || { FAILED=1; echo "  -> FAILED: see $OUT"; return 1; }; }

wait_ssh() {   # up to 450 s for `gssh true`, then up to 240 s for systemd to settle (recorded, not fatal)
    local i state
    for i in $(seq 1 90); do
        if gssh true 2> /dev/null; then
            echo "ssh answered after about $((i * 5)) s"
            for i in $(seq 1 40); do
                state=$(gssh systemctl is-system-running 2> /dev/null || true)
                case $state in running | degraded) echo "systemd: $state after about $((i * 6)) s more"; return 0 ;; esac
                sleep 6
            done
            echo "systemd did not reach running/degraded within 240 s (last: $state)"
            return 0
        fi
        sleep 5
    done
    echo "STOP: no ssh answer within 450 s"
    return 1
}

guest_facts() {
    gssh 'echo "== hostname"; hostname; echo "== uname"; uname -a; echo "== os-release"; cat /etc/os-release;
echo "== is-system-running"; systemctl is-system-running; echo "== failed units"; systemctl --failed --no-legend;
echo "== cmdline"; cat /proc/cmdline; echo "== nproc"; nproc; echo "== cpu"; grep -m1 -E "CPU part|model name" /proc/cpuinfo;
echo "== free -m"; free -m; echo "== df"; df -h / /var/lib/docker /tmp 2>&1; echo "== findmnt docker"; findmnt -no SOURCE,FSTYPE,SIZE,LABEL,OPTIONS /var/lib/docker;
echo "== lsblk"; lsblk 2>&1; echo "== addresses"; ip -o addr show 2>/dev/null || ifconfig -a; echo "== resolv.conf"; cat /etc/resolv.conf;
echo "== timedatectl"; timedatectl 2>&1; echo "== id egw"; id egw; echo "== /opt/egw"; ls -ld /opt/egw /opt/egw/deployment /opt/egw/deployment/data/events 2>&1;
echo "== docker"; docker --version; docker compose version; docker info 2>/dev/null | grep -E "Server Version|Storage Driver|Cgroup|Operating System|Total Memory|CPUs|Live Restore|Docker Root Dir";
echo "== buildinfo"; cat /etc/buildinfo /etc/egw-buildinfo 2>/dev/null; echo "== package count"; { dpkg-query -W 2>/dev/null | wc -l; } || true;
echo "== oom lines"; sudo -n dmesg 2>/dev/null | grep -ci "out of memory"; echo "== timers"; systemctl list-timers --all --no-legend 2>&1 | head -n 30'
}

final_state() {
    gssh 'cd /opt/egw/deployment 2>/dev/null && docker compose --env-file .env --env-file images.lock.env ps -a; docker ps -a; docker images --digests; df -h / /var/lib/docker; du -sh /var/lib/docker 2>/dev/null; docker system df 2>/dev/null;
sudo -n dmesg 2>/dev/null | grep -i "out of memory" | head; echo "== cloud-init"; ls -l /var/log/cloud-init.log 2>/dev/null && tail -n 5 /var/log/cloud-init.log; cat /etc/cloud/cloud-init.disabled 2>/dev/null; echo "== packages"; cat /etc/egw-buildinfo.packages 2>/dev/null | wc -l'
}

sut_environment() {
    gssh "cd /opt/egw/deployment && EGW_PROVIDER='QEMU 8.2.7 TCG (qemu-system-native) on WSL2 Ubuntu-24.04, Windows 11 x86-64' EGW_REGION='local-workstation' EGW_INSTANCE_TYPE='qemu -machine virt -cpu cortex-a76 -smp 4 -m 8192; ARM64 EMULATED; scenario $SCENARIO' EGW_SHARED_VCPU_NOTE='TCG emulation on a shared x86-64 host; comparison guest; never native ARM64' sh scripts/capture-sut-environment.sh /opt/egw/evidence/sut_environment.json && cat /opt/egw/evidence/sut_environment.json"
}

controlled_close() {
    echo "== controlled close"
    step close tf-stop env EGW_COMPARE_AUTO_APPROVE=1 bash "$HERE/tf.sh" "$scenario" stop
    CLOSE_RC=$?
    step close status bash "$HERE/compare_env.sh" status "$scenario"
    if own_pid > /dev/null 2>&1; then
        echo "STOP: the guest of $scenario is still running after the controlled stop; it was not killed"
        CLOSE_RC=5
    fi
    step close qemu-others bash -c '. "$1/lib.sh"; scenario_load "$2"; if o=$(qemu_others); then echo "other QEMU processes present:"; echo "$o"; exit 1; else echo "no qemu-system-aarch64 process left (pgrep rc $?)"; fi' _ "$HERE" "$scenario" || true
}

seal() {
    local f
    for f in "$S_MANIFEST" "$S_DIR/state/argv.txt" "$S_DIR/state/provision.json" "$S_DIR/state/started_utc"; do
        [ -e "$f" ] && cp -p "$f" "$OUT/"
    done
    [ -s "$S_DIR/state/console" ] && cp -p "$(cat "$S_DIR/state/console")" "$OUT/" 2> /dev/null
    cp -p "$S_DIR"/logs/provision-*.log "$S_DIR"/logs/stop-*.log "$S_DIR"/logs/start-*.log "$OUT/" 2> /dev/null
    [ -n "${FUNC_DIR:-}" ] && [ -d "$FUNC_DIR" ] && cp -rp "$FUNC_DIR" "$OUT/functional"
    cp -p "$S_LOG" "$OUT/lifecycle.log" 2> /dev/null
    (cd "$OUT" && find . -type f ! -name SHA256SUMS | LC_ALL=C sort | sed 's#^\./##' | xargs -d '\n' sha256sum > SHA256SUMS)
}

echo "VALIDATE $scenario: results in $OUT"
# --- 0. prerequisites (nothing starts if any is missing) --------------------------------------------
pre_ok=1
check() { if "$@" > /dev/null 2>&1; then echo "ok:   $*"; else echo "MISSING: $*"; pre_ok=0; fi; }
{
    check test -x "$COMPARE_QEMU"
    check test -x "$COMPARE_QEMU_IMG"
    check test -r "$COMPARE_SSH_KEY"
    check test -r "$SECRETS"
    check test -s "$IMAGES_DIR/egw-controller-0.1.0-arm64.tar"
    check test -s "$IMAGES_DIR/egw-controller-0.1.0-arm64.identity.txt"
    check "$VENV/bin/python" -c 'import egw_simulator'
    # Placeholders outside comments; fail-closed (an unreadable file is not "no placeholder").
    check bash -c 'n=$(grep -v "^[[:space:]]*#" "$1" | grep -c CHANGE_ME); [ "$n" = 0 ]' _ "$SECRETS"
    if pilot_session_open; then echo "MISSING: no pilot session must be open ($COMPARE_EXEC/current_session exists)"; pre_ok=0; else echo "ok:   no pilot session open"; fi
    if o=$(qemu_others); then echo "MISSING: no other QEMU must run:"; echo "$o"; pre_ok=0; elif [ $? -eq 2 ]; then echo "MISSING: pgrep could not answer"; pre_ok=0; else echo "ok:   no other qemu-system-aarch64 running"; fi
    if [ "$RESUME" = 1 ]; then
        if p=$(own_pid); then echo "ok:   resume: this scenario's guest is running (pid $p)"; else echo "MISSING: resume needs this scenario's guest running"; pre_ok=0; fi
    else
        if b=$(ports_busy); then echo "MISSING: host ports free (busy:$b)"; pre_ok=0; else echo "ok:   host ports 2222/8883 free"; fi
        if own_pid > /dev/null 2>&1; then echo "MISSING: this scenario must not be running already"; pre_ok=0; fi
    fi
} > "$OUT/00-prerequisites.txt" 2>&1
cat "$OUT/00-prerequisites.txt"
[ "$pre_ok" = 1 ] || { echo "VALIDATE $scenario: result=not-started (prerequisites) out=$OUT"; exit 2; }

# --- 1. boot through Terraform (prepare is idempotent; start refuses if anything else runs) ---------
if [ "$RESUME" = 1 ]; then
    echo "resume: the guest was booted by an earlier run; the apply is not repeated" | tee "$OUT/01-boot-resumed.txt"
elif ! must boot tf-apply env EGW_COMPARE_AUTO_APPROVE=1 bash "$HERE/tf.sh" "$scenario" apply; then
    seal
    echo "VALIDATE $scenario: result=fail phase=boot out=$OUT"
    exit 1
fi
step boot status bash "$HERE/compare_env.sh" status "$scenario"
if ! must boot wait-ssh wait_ssh; then
    controlled_close
    seal
    echo "VALIDATE $scenario: result=fail phase=boot out=$OUT"
    [ "$CLOSE_RC" = 0 ] && exit 1 || exit 5
fi

# --- 2. configuration facts ---------------------------------------------------------------------
must config guest-facts guest_facts

# --- 3. the same application stack ----------------------------------------------------------------
if must stack provision bash "$HERE/provision_stack.sh" "$scenario"; then
    step stack sut-environment sut_environment
    # --- 4. one synthetic event from one test device to its twin ------------------------------------
    RUN_ID=cmpval-$scenario-$(stamp)
    SEED=$(( $(date -u +%s) % 2000000000 ))
    must functional one-event bash "$HERE/functional_check.sh" "$scenario" "$RUN_ID" "$SEED"
    FUNC_DIR=$(ls -d "$S_DIR"/results/functional-*-"$RUN_ID" 2> /dev/null | tail -n 1)
else
    echo "stack not provisioned: the functional check is not attempted"
fi

# --- 5. final state -------------------------------------------------------------------------------
step final guest-final-state final_state
step final journal gssh 'sudo -n journalctl -b --no-pager'

# --- 6. controlled close, 7. seal -----------------------------------------------------------------
controlled_close
seal
T_END=$(uptime_s)
echo "== phases"
awk -F'\t' 'NR > 1 { r[$2] = (r[$2] == "" ? "" : r[$2] " ") $3 "=" $4 } END { for (p in r) print p ": " r[p] }' "$STEPS" | sort
echo "total $(awk -v a="$T_START" -v b="$T_END" 'BEGIN { printf "%.0f", b - a }') s (host monotonic)"
if [ "$CLOSE_RC" != 0 ]; then echo "VALIDATE $scenario: result=close-failed out=$OUT"; exit 5; fi
if [ "$FAILED" != 0 ]; then echo "VALIDATE $scenario: result=fail out=$OUT"; exit 1; fi
echo "VALIDATE $scenario: result=pass out=$OUT"
