#!/usr/bin/env bash
# run-qemu.sh — boot egw-image in QEMU (qemuarm64) with the serial console
# recorded to a log file. FUNCTIONAL VALIDATION ONLY: QEMU results support
# build/boot/systemd/network/OCI-runtime claims and never performance claims
# (plan section 3.1).
#
# The current G1 acceptance campaign requires five strict boots, each reaching
# systemd multi-user with zero failed units, bringing networking up and
# executing one container. Use distinct names so every boot leaves its own
# complete console log, for example qemu-boot-01 through qemu-boot-05.
#
# Everything on the serial console — kernel messages, systemd output, your
# interactive commands and their output — goes through tee into
# $EGW_LOG_DIR/<name>.log. That single file is the G1 boot evidence; run the
# in-guest checks below while recording:
#   systemctl is-system-running        # expect exactly "running"
#   ip addr                            # slirp NIC up with a 10.0.2.x lease
#   ping -c 3 10.0.2.2                 # host-side gateway reachable
#   egw-container-smoke.sh             # gate-G1 container evidence, also
#                                      # appends PASS/FAIL to /var/log/egw-smoke.log
# Exit QEMU with: Ctrl+A, then x.
#
# Notes:
# - 'nographic' keeps the serial console on this terminal; 'slirp' is
#   user-mode networking (no root/TAP setup needed inside WSL2).
# - If your terminal multiplexer garbles the tee'd session, the util-linux
#   'script' command is an equivalent alternative:
#     script -c "kas shell kas/egw-qemuarm64.yml -c 'runqemu qemuarm64 nographic slirp'" boot1.log
#
# Bash is intentional: pipefail is required so a failed `kas shell` can never
# be hidden by a successful tee process.

set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
YOCTO_DIR=$(dirname -- "$SCRIPT_DIR")
KAS_FILE="kas/egw-qemuarm64.yml"
LOG_DIR="${EGW_LOG_DIR:-$HOME/yocto/logs}"

BOOT_NAME="${1:-boot-$(date -u +%Y%m%dT%H%M%SZ)}"
LOG_FILE="$LOG_DIR/$BOOT_NAME.log"

run_qemu_logged() {
    # Interactive stdin stays attached to the terminal; stdout/stderr are
    # teed so the full session lands in the evidence log. `pipefail` makes
    # this function return kas's non-zero status even when tee succeeds.
    kas shell "$KAS_FILE" -c "runqemu qemuarm64 nographic slirp" 2>&1 | tee "$LOG_FILE"
}

main() {
    cd "$YOCTO_DIR"
    KAS_WORK_DIR="$YOCTO_DIR"
    export KAS_WORK_DIR

    command -v kas >/dev/null 2>&1 || {
        echo "ERROR: 'kas' not found (see docs/setup/wsl2_ubuntu_yocto.md)." >&2
        exit 1
    }

    if [[ ! -d "$YOCTO_DIR/build/tmp/deploy/images/qemuarm64" ]]; then
        echo "ERROR: no deployed image found — run scripts/build.sh first." >&2
        exit 1
    fi

    mkdir -p "$LOG_DIR"
    echo "== booting egw-image in QEMU; console recorded to $LOG_FILE =="
    echo "== exit with Ctrl+A then x =="

    run_qemu_logged

    echo "== QEMU session ended; console log: $LOG_FILE =="
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main
fi
