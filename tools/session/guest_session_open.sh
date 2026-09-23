#!/bin/bash
# Open a guest session as its own attempt: record the identities of what is
# about to run, boot the integrated guest with the existing session scripts,
# record the guest's state, and leave it up. guest_session_close.sh stops the
# stack, powers the guest off and exports the session.
#
# Prerequisites (failure: outcome not-run, exit 2) are: no session already
# open, no qemu-system-aarch64 running, the attempt itself, the record of the
# open session in $EXEC/current_session, the session's directories and the
# scripts copied into them, the identities read before the boot (every one of
# them, not only the last) and the boot. Nothing is started before all of them
# hold. The guest state after the boot is a MANDATORY record (failure: exit
# 3), and so is the writing of that record: a verdict about a guest that is up
# and could not be written to the attempt also ends the driver with 3, because
# a verdict that was not written must never be read as a healthy session. On
# success the session attempt stays OPEN and is exported by
# guest_session_close.sh, not here.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
if [ -n "$SESSION" ] && [ -d "$SESSION" ]; then
    driver_stop "$EXIT_PREREQUISITE" "a session is already open: $SESSION"
fi
# By the process NAME: a match on command lines would take the shell that
# invoked this driver for a running guest when its command line holds the
# pattern (guest_session_close.sh, the same check).
if pgrep -x qemu-system-aarch64 > /dev/null; then
    driver_stop "$EXIT_PREREQUISITE" "a qemu-system-aarch64 process is already running"
fi
S=$(new_attempt "guest session" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
SESSION=$S
RUN=s1
trap 'driver_interrupt "$S"' INT TERM

# not_run REASON: a prerequisite failed, so the session was not opened.
not_run() {
    (cd "$REPO/src" && $LE finish --attempt "$S" --status failed --validity invalid --outcome not-run \
        --reason "$1" --next-action "read boot/ and console/; no session is open")
    rm -f "$EXEC/current_session" 2> /dev/null
    driver_exit "$S"
}

# capture_lost_stop NAME: the step's own command ran, but its mandatory console
# capture failed (exit 74). The record is incomplete, so the attempt is invalid
# and the session is not opened; the step itself is never recorded as failed.
capture_lost_stop() {
    (cd "$REPO/src" && $LE finish --attempt "$S" --status failed --validity invalid --outcome inconclusive \
        --reason "$(capture_note "$1"); the guest was NOT booted" \
        --next-action "read commands.jsonl for the step's own exit code; no session is open")
    rm -f "$EXEC/current_session"
    driver_exit "$S"
}

# open_stop NOTE: the guest IS up and something this driver established could
# not be written to the attempt. The code is then NOT derived from an
# attempt.json that does not carry the verdict (which would read as a healthy
# open session, exit 0): the driver ends with EXIT_INVALID and says what is
# missing. The session is left OPEN and $EXEC/current_session kept, because the
# guest still has to be powered off and exported by guest_session_close.sh.
open_stop() {
    driver_stop "$EXIT_INVALID" \
        "$1; attempt.json could not be updated, so $S does not record it; the guest session is OPEN (close it with guest_session_close.sh)"
}

# The record of the open session is the ONLY link between the booted guest and
# every later driver (guest_common.sh reads $SESSION from it), so it is written
# BEFORE the boot and read back: a session that could not be recorded would
# leave the guest up with no driver able to stop it or to export its evidence.
echo "$S" > "$EXEC/current_session" \
    || not_run "the open session could not be recorded in $EXEC/current_session; the guest was NOT booted"
[ "$(cat "$EXEC/current_session" 2> /dev/null)" = "$S" ] \
    || not_run "$EXEC/current_session does not hold the open session after it was written; the guest was NOT booted"

mkdir -p "$S/scripts" "$S/boot" "$S/guest" "$S/host" \
    || not_run "the session's own directories could not be created; the guest was NOT booted"
cp "$DRIVERS/guest/"{session_common.sh,session_open.sh,boot_driver.sh,session_close.sh,session_run.sh,gssh.sh} "$S/scripts/" \
    || not_run "the guest session scripts could not be copied into the session; the guest was NOT booted"
# The copy kept with the session is every file the drivers are made of, the
# same set repo_identity hashes: the shell drivers, their Python helpers and
# the guest scripts.
mkdir -p "$S/scripts/drivers/guest" \
    && cp "$DRIVERS"/*.sh "$DRIVERS"/*.py "$S/scripts/drivers/" \
    && cp "$DRIVERS"/guest/*.sh "$S/scripts/drivers/guest/" \
    || not_run "the driver copies could not be kept with the session; the guest was NOT booted"
# The identity of the clean clone is read before anything is booted.
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
(cd "$REPO/src" && $LE set --attempt "$S" "identities=$IDENTITIES" \
    'workload={"kind": "guest session: boot, stack start, the attempts that reference this session, controlled stop and power-off"}') \
    || not_run "the attempt fields could not be recorded; the guest was NOT booted"
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || not_run "the identity of the clean clone could not be read (see identities.identity_error); the guest was NOT booted"

# Identities, read before the boot (the rootfs ext4 is booted in place and
# changes; the immutable identity of the built rootfs is its tar.bz2). Every
# identity this step claims to read accumulates into rc, as nominal.sh's
# guest-state does: the step's status is not that of its last command, so an
# artefact, a binary or a checkout that could not be read stops the boot
# instead of leaving an identity unread behind a zero. The host observations
# (uname, ports, free, df, dumpe2fs) are diagnostics and are not counted.
ex "$S" identities-before-boot bash -c '
set -u
rc=0
echo "## host"; uname -a; cat /proc/version; nproc; free -m; df -h / /mnt/c
echo "## ports (2222 8883 8000 8080 must be free)"; ss -ltn | grep -E ":(2222|8883|8000|8080) " || echo "none listening"
echo "## OS build artefacts ('"$DEP"')"
cd "'"$DEP"'" && sha256sum Image-qemuarm64.bin egw-gateway-image-qemuarm64.rootfs-20260918120819.tar.bz2 \
  egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4 egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf \
  egw-gateway-image-qemuarm64.rootfs-20260918120819.manifest || rc=1
echo "## data disk"; ls -l "'"$DATA_DISK"'" || rc=1; /usr/sbin/dumpe2fs -h "'"$DATA_DISK"'" 2>/dev/null | grep -E "state|features|mount count|Last mount"
echo "## rootfs ext4 state"; /usr/sbin/dumpe2fs -h "'"$ROOTFS_EXT4"'" 2>/dev/null | grep -E "state|features|mount count|Last mount"
echo "## QEMU"; Q="'"$BUILD"'/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64"; sha256sum "$Q" || rc=1
if V=$("$Q" --version 2>&1); then printf "%s\n" "$V" | head -n 1; else printf "%s\n" "$V"; rc=1; fi
echo "## OS build source (Yocto checkout, launcher and kas)"; git -C "'"$OLD"'" rev-parse HEAD || rc=1; git -C "'"$OLD"'" status --porcelain | wc -l
cd "'"$OLD"'/src/yocto" && sha256sum scripts/run-qemu-integrated.sh kas/egw-qemuarm64-integrated.yml kas/egw-qemuarm64-integrated.lock.yml || rc=1
echo "## execution clone"; git -C "'"$REPO"'" rev-parse HEAD || rc=1; git -C "'"$REPO"'" status --porcelain | wc -l
cd "'"$REPO"'/src" && sha256sum deployment/scripts/collect-resources.sh deployment/images.lock.env deployment/compose.yaml || rc=1
echo "## host helpers"; sha256sum "$HOME/egw-tcg/itest-helpers.sh" "$HOME/egw-tcg/tunnel.sh" "$HOME/egw-tcg/ca.crt" || rc=1
echo "## controller image record"; I="${EGW_IMAGES_DIR:-/home/ruisth/egw-images}"; sha256sum "$I/egw-controller-0.1.0-arm64.tar" || rc=1; cat "$I/egw-controller-0.1.0-arm64.identity.txt" || rc=1
exit $rc
'
ident_rc=$?
if [ "$ident_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_lost_stop identities-before-boot
elif [ "$ident_rc" -ne 0 ]; then
    not_run "the identities of what was about to run were not read; the guest was NOT booted"
fi
cp "$EXEC/venv-freeze.txt" "$S/environment/venv-freeze.txt"
"$PY" -m pip freeze > "$S/environment/venv-freeze-now.txt" 2>&1

ex "$S" boot bash "$S/scripts/session_open.sh" "$S" "$RUN"
rc=$?
QPID=$(pgrep -x qemu-system-aarch64 | head -n 1)
(cd "$REPO/src" && $LE set --attempt "$S" "pid=${QPID:-0}") || PID_UNRECORDED=1
# A guest that is up and whose pid the attempt does not hold is judged here;
# when the boot left no guest at all, the branch below records that instead.
if [ -n "$QPID" ] && [ "${PID_UNRECORDED:-0}" -ne 0 ]; then
    open_stop "the guest booted (qemu pid $QPID) but its pid was not recorded"
fi
if [ -n "$QPID" ] && [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    # The guest IS up, so the session stays OPEN (guest_session_close.sh must
    # still power it off) although the boot's own console record is incomplete.
    (cd "$REPO/src" && $LE set --attempt "$S" "instrumentation_validity=invalid" \
        "reason=$(capture_note boot); the guest booted (qemu pid $QPID)" \
        "next_action=read commands.jsonl; close the session with guest_session_close.sh before any test") \
        || open_stop "the console record of the boot is incomplete (qemu pid $QPID)"
    echo "session open but its boot record is incomplete: $S (qemu pid $QPID)"
    driver_exit_open "$S"
fi
if [ "$rc" -ne 0 ] || [ -z "$QPID" ]; then
    not_run "boot failed (session_open exit $rc; qemu pid '${QPID:-none}')"
fi
# The mandatory record of the guest state after the boot. It is a LIST of guest
# commands, so every command that this record is MADE of accumulates into rc,
# as the identity group above and nominal.sh's GUEST_STATE do: the step's status
# is not that of its last command, so a systemd that is not running, a Docker
# daemon that cannot be reached (the six-container stack is the point of the
# session) or a filesystem that cannot be read leaves the session open and the
# attempt invalid instead of passing behind the dmesg test at the end. The
# purely informational reads (uptime, free, the journal grep, timedatectl) are
# not counted.
gx "$S" guest-state-after-boot 'set -u; rc=0; systemctl is-system-running || rc=1; uptime; free -m; df -h / /var/lib/docker /tmp || rc=1;
  echo "## journal replay / fsck"; sudo -n journalctl -b --no-pager | grep -iE "recover|EXT4-fs" | head -n 40;
  echo "## docker"; docker ps -a --format "{{.Names}} {{.Status}} {{.Image}}" || rc=1;
  echo "## clock"; timedatectl show; date -u +%Y-%m-%dT%H:%M:%SZ;
  echo "## OOM so far this boot";
  if KMSG=$(sudo -n dmesg 2>/dev/null); then printf "%s\n" "$KMSG" | grep -ci "memory cgroup out of memory" || true;
  else echo "dmesg could not be read: the OOM state of this boot is UNKNOWN, which is not \"no OOM\""; rc=1; fi
  exit $rc'
state_rc=$?
if [ "$state_rc" -ne 0 ]; then
    # The guest is up, so the session stays OPEN (guest_session_close.sh must
    # still power it off); the attempt records that its state was not read.
    (cd "$REPO/src" && $LE set --attempt "$S" "instrumentation_validity=invalid" \
        "reason=the guest booted (qemu pid $QPID) but $(step_note guest-state-after-boot "$state_rc" "its state after the boot was not recorded (exit $state_rc)")" \
        "next_action=read console/; close the session with guest_session_close.sh before any test") \
        || open_stop "the guest booted (qemu pid $QPID) but its state after the boot was not recorded (exit $state_rc)"
    echo "session open but NOT characterised: $S (qemu pid $QPID)"
    driver_exit_open "$S"
fi
echo "session open: $S (qemu pid $QPID)"
driver_exit_open "$S"
