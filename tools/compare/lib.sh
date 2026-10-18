# shellcheck shell=bash
# tools/compare/lib.sh - settings and helpers shared by the comparison-environment scripts.
# Sourced, never executed. Everything here is host-side (WSL2 Ubuntu-24.04, GNU userland).
#
# Two scenarios share ONE machine profile (the recorded pilot profile of 2026-10-09) and differ only
# in the operating system booted: `yocto` (the project's egw-gateway-image) and `debian13` (Debian 13
# genericcloud arm64, provisioned once for the same application stack). Only one guest runs at a time.
#
# Overridable settings (environment):
#   EGW_COMPARE_ROOT          state root OUTSIDE the clone (default $HOME/egw-compare)
#   EGW_COMPARE_SCENARIOS_DIR directory of the <scenario>.env files (default tools/compare/scenarios)
#   EGW_COMPARE_QEMU          qemu-system-aarch64 to use (default: poky's qemu-helper-native 8.2.7)
#   EGW_COMPARE_QEMU_IMG      qemu-img to use (default: the sibling of EGW_COMPARE_QEMU)
#   EGW_COMPARE_SSH_KEY       private key of the guest user egw (default ~/.ssh/egw_campaign)
#   EGW_COMPARE_STOP_WAIT_S   seconds to wait for QEMU to end after poweroff (default 180)
#   EGW_COMPARE_SEED_PORT     host loopback port of the transient cloud-init seed server (default 8099)
#   EGW_EXEC                  the session tooling's root; its current_session marker blocks a start
set -u

COMPARE_HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
COMPARE_REPO=${EGW_COMPARE_REPO:-$(cd "$COMPARE_HERE/../.." && pwd)}
COMPARE_ROOT=${EGW_COMPARE_ROOT:-$HOME/egw-compare}
COMPARE_SCENARIOS_DIR=${EGW_COMPARE_SCENARIOS_DIR:-$COMPARE_HERE/scenarios}
COMPARE_EXEC=${EGW_EXEC:-$HOME/egw-exec}
COMPARE_YOCTO_NATIVE_BIN=${EGW_COMPARE_YOCTO_NATIVE_BIN:-$HOME/yocto/egw/src/yocto/build-integrated/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin}
COMPARE_QEMU=${EGW_COMPARE_QEMU:-$COMPARE_YOCTO_NATIVE_BIN/qemu-system-aarch64}
COMPARE_QEMU_IMG=${EGW_COMPARE_QEMU_IMG:-$(dirname "$COMPARE_QEMU")/qemu-img}
COMPARE_SSH_KEY=${EGW_COMPARE_SSH_KEY:-$HOME/.ssh/egw_campaign}
COMPARE_SSH_PORT=2222
COMPARE_MQTT_PORT=8883
COMPARE_HOST_PORTS="2222 8883"
COMPARE_MAC=52:54:00:12:35:02
COMPARE_DATA_DISK_SIZE=${EGW_COMPARE_DATA_DISK_SIZE:-32G}
COMPARE_DATA_DISK_LABEL=egw-data
COMPARE_SEED_PORT=${EGW_COMPARE_SEED_PORT:-8099}
COMPARE_STOP_WAIT_S=${EGW_COMPARE_STOP_WAIT_S:-180}
COMPARE_FIRSTBOOT_LIMIT_S=${EGW_COMPARE_FIRSTBOOT_LIMIT_S:-1800}
COMPARE_SCENARIO_NAMES="yocto debian13"
# The machine profile is the same for both scenarios and is never read from the scenario file.
COMPARE_MACHINE_ARGS=(-machine virt -accel tcg -cpu cortex-a76 -smp 4 -m 8192)
# The regex the session tooling uses to see QEMU processes (tools/session/guest_common.sh).
COMPARE_QEMU_EXE_RE='^(\S*/)?qemu-system-aarch64( |$)'

utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
stamp() { date -u +%Y%m%dT%H%M%SZ; }
# Host monotonic seconds (CLOCK_BOOTTIME): durations are measured on this, never on UTC.
uptime_s() { cut -d' ' -f1 /proc/uptime; }
sha256_of() { sha256sum "$1" | cut -d' ' -f1; }
log_line() { printf '%s %s\n' "$(utc_now)" "$2" >> "$1"; }
die() { echo "STOP: $*" >&2; exit "${DIE_CODE:-2}"; }

# scenario_load NAME: source <scenarios dir>/NAME.env and set the scenario's directories.
scenario_load() {
    local name=$1 f
    case " $COMPARE_SCENARIO_NAMES " in
        *" $name "*) ;;
        *) die "unknown scenario '$name' (known: $COMPARE_SCENARIO_NAMES)" ;;
    esac
    f=$COMPARE_SCENARIOS_DIR/$name.env
    [ -r "$f" ] || die "scenario file missing: $f"
    # shellcheck disable=SC1090
    . "$f"
    [ "${SCENARIO:-}" = "$name" ] || die "$f declares SCENARIO='${SCENARIO:-}', expected '$name'"
    S_DIR=$COMPARE_ROOT/scenarios/$name
    B_DIR=$COMPARE_ROOT/base/$name
    # The root overlay is named after the base image, <image>.rootfs.qcow2: the harness identifies
    # the rootfs drive of the hypervisor it records by '.rootfs' in the drive's file name.
    IMAGE_NAME=$(basename "${BASE_IMAGE_FILE:-${BASE_ROOTFS_SRC:-root}}")
    IMAGE_NAME=${IMAGE_NAME%.qcow2}; IMAGE_NAME=${IMAGE_NAME%.ext4}; IMAGE_NAME=${IMAGE_NAME%.rootfs}
    S_ROOT_DISK=$S_DIR/disks/$IMAGE_NAME.rootfs.qcow2
    S_DATA_DISK=$S_DIR/disks/data.img
    S_PIDFILE=$S_DIR/state/qemu.pid
    S_MONITOR=$S_DIR/state/monitor.sock
    S_KNOWN_HOSTS=$S_DIR/state/known_hosts
    S_MANIFEST=$S_DIR/manifest.json
    S_LOG=$S_DIR/logs/lifecycle.log
}

scenario_dirs() { mkdir -p "$S_DIR/disks" "$S_DIR/state" "$S_DIR/logs" "$S_DIR/results" "$B_DIR" "$COMPARE_ROOT/lock"; }

# pid_alive PID: 0 when the process exists and is neither a zombie (Z) nor dead (X) - a QEMU that
# exited but was not reaped yet is gone for every purpose here; 1 otherwise.
pid_alive() {
    local st
    st=$(sed 's/.*) //' "/proc/$1/stat" 2> /dev/null | cut -d' ' -f1)
    [ -n "$st" ] || return 1
    case $st in Z | X) return 1 ;; esac
    return 0
}

# own_pid: print the pid of THIS scenario's live QEMU: pid file present, process alive (not a
# zombie), its command line a qemu-system-aarch64 that carries this scenario's pid-file path as
# one of its arguments (QEMU keeps its argv when it daemonises), so that a pid reused by another
# QEMU after an unexpected exit is never claimed. Prints nothing and returns 1 otherwise.
own_pid() {
    local p
    [ -s "$S_PIDFILE" ] || return 1
    p=$(tr -dc '0-9' < "$S_PIDFILE")
    [ -n "$p" ] || return 1
    pid_alive "$p" || return 1
    tr '\0' ' ' < "/proc/$p/cmdline" 2> /dev/null | grep -qE "$COMPARE_QEMU_EXE_RE" || return 1
    grep -qzFx -- "$S_PIDFILE" "/proc/$p/cmdline" 2> /dev/null || return 1
    printf '%s\n' "$p"
}

# qemu_others: list every qemu-system-aarch64 process that is NOT this scenario's own guest.
# Returns 0 when at least one exists (printed as 'pid command'), 1 when none, 2 when pgrep could
# not answer (never read as 'none'). This tool never stops any of them.
qemu_others() {
    local out rc mine
    out=$(pgrep -af "$COMPARE_QEMU_EXE_RE")
    rc=$?
    case $rc in
        0) ;;
        1) return 1 ;;
        *) return 2 ;;
    esac
    mine=$(own_pid 2> /dev/null || true)
    if [ -n "$mine" ]; then
        out=$(printf '%s\n' "$out" | awk -v m="$mine" '$1 != m')
        [ -n "$out" ] || return 1
    fi
    printf '%s\n' "$out"
    return 0
}

pilot_session_open() { [ -e "$COMPARE_EXEC/current_session" ]; }

# ports_busy: print the host loopback ports of this profile that already have a listener.
ports_busy() {
    local p busy=
    for p in $COMPARE_HOST_PORTS; do
        if ss -ltn 2> /dev/null | grep -qE "[:.]$p "; then busy="$busy $p"; fi
    done
    [ -n "$busy" ] || return 1
    echo "$busy"
}

# One guest at a time: a directory lock naming the scenario that holds the profile's ports.
lock_holder() { cat "$COMPARE_ROOT/lock/active/holder" 2> /dev/null || true; }
lock_acquire() {
    local holder
    if mkdir "$COMPARE_ROOT/lock/active" 2> /dev/null; then
        printf '%s\n' "$SCENARIO" > "$COMPARE_ROOT/lock/active/holder"
        return 0
    fi
    holder=$(lock_holder)
    if [ "$holder" = "$SCENARIO" ]; then return 0; fi
    # Held by another scenario: stale only if that scenario has no live guest.
    if [ -n "$holder" ] && [ ! -s "$COMPARE_ROOT/scenarios/$holder/state/qemu.pid" ]; then
        rm -rf "$COMPARE_ROOT/lock/active"
        mkdir "$COMPARE_ROOT/lock/active" && printf '%s\n' "$SCENARIO" > "$COMPARE_ROOT/lock/active/holder"
        return 0
    fi
    return 1
}
lock_release() { [ "$(lock_holder)" = "$SCENARIO" ] && rm -rf "$COMPARE_ROOT/lock/active"; return 0; }

# gssh [ssh args...] COMMAND: ssh to the running guest of this scenario with ITS pinned host key file.
gssh() {
    ssh -i "$COMPARE_SSH_KEY" -p "$COMPARE_SSH_PORT" -o IdentitiesOnly=yes -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$S_KNOWN_HOSTS" \
        -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR egw@127.0.0.1 "$@"
}
gscp() {
    scp -i "$COMPARE_SSH_KEY" -P "$COMPARE_SSH_PORT" -o IdentitiesOnly=yes -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$S_KNOWN_HOSTS" \
        -o ConnectTimeout=10 -o LogLevel=ERROR "$@"
}

# monitor_cmd TEXT: send one HMP command to the guest's monitor socket (system_powerdown, info status).
monitor_cmd() {
    python3 - "$S_MONITOR" "$1" << 'PY'
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(5)
s.connect(sys.argv[1])
try:
    s.recv(4096)
except OSError:
    pass
s.sendall((sys.argv[2] + "\n").encode())
try:
    sys.stdout.write(s.recv(4096).decode(errors="replace"))
except OSError:
    pass
PY
}

# wait_gone PID LIMIT_S: wait on the host monotonic clock until PID is gone (exited, or a zombie
# not reaped yet); 0 gone, 1 still alive.
wait_gone() {
    local pid=$1 limit=$2 t0 now
    t0=$(uptime_s)
    while pid_alive "$pid"; do
        now=$(uptime_s)
        if awk -v a="$t0" -v b="$now" -v l="$limit" 'BEGIN { exit !(b - a >= l) }'; then return 1; fi
        sleep 1
    done
    return 0
}
