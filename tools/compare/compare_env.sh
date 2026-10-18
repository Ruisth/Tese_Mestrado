#!/bin/bash
# tools/compare/compare_env.sh - lifecycle of ONE comparison guest (scenario `yocto` or `debian13`)
# under the shared QEMU/TCG machine profile. Called by the Terraform module (tools/compare/terraform)
# and usable by hand. It never starts a second guest, never stops a QEMU it did not start, never
# kills a QEMU process, and never writes into the clone or into the pilot's directories.
#
#   compare_env.sh prepare  <scenario>   immutable base copies (checksummed), fresh work disks, manifest
#   compare_env.sh start    <scenario>   boot the guest (daemonised QEMU with a pid file); refuses if
#                                        another QEMU runs, the pilot has a session open, or the
#                                        profile's host ports are busy
#   compare_env.sh status   <scenario>   one JSON object of strings with the LIVE state (always exit 0)
#   compare_env.sh stop     <scenario>   controlled stop: stack stop, poweroff over ssh (or the monitor's
#                                        system_powerdown), wait; exit 5 if QEMU is still running
#   compare_env.sh destroy  <scenario>   remove ONLY the work disks and the state directory; keeps
#                                        bases, logs and results; exit 5 while the guest runs
#   compare_env.sh manifest <scenario>   print the manifest path
#   compare_env.sh disks    <scenario>   virtual size, host allocation and apparent size of each disk file
#
# Exit codes: 0 done (or already in the asked state); 2 prerequisite or guard; 3 integrity or
# verification failure; 5 start failed, controlled stop failed, or destroy refused while running.
# Settings and helpers: tools/compare/lib.sh. Layout: $EGW_COMPARE_ROOT (default ~/egw-compare).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -eq 2 ] || usage
cmd=$1
scenario=$2
scenario_load "$scenario"

# --- bases ---------------------------------------------------------------------------------------

# resolve_base: the base files this scenario boots (no side effects).
resolve_base() {
    case $BASE_KIND in
        yocto-deploy)
            BASE_ROOT=$B_DIR/rootfs.ext4
            BASE_KERNEL=$B_DIR/Image
            BASE_INITRD=
            ROOT_UUID=
            ;;
        debian-cloud)
            BASE_ROOT=$B_DIR/prepared.qcow2
            BASE_KERNEL=$B_DIR/vmlinuz
            BASE_INITRD=$B_DIR/initrd.img
            ROOT_UUID=$(cat "$B_DIR/root-uuid.txt" 2> /dev/null || true)
            ;;
        *) die "scenario $SCENARIO: unknown BASE_KIND '$BASE_KIND'" ;;
    esac
}

# base_copy SRC DST: copy a base artefact once (sparse), then make it read-only.
base_copy() {
    [ -s "$2" ] && return 0
    cp --sparse=always "$1" "$2.part" || die "could not copy $1"
    mv "$2.part" "$2"
    chmod 0444 "$2"
    log_line "$S_LOG" "base copied: $1 -> $2"
}

# base_seal FILE...: record each base file's sha256 once in base/<scenario>/SHA256SUMS, then verify
# every recorded file. A base that changed under the record is an integrity failure (exit 3).
base_seal() {
    local f
    (
        cd "$B_DIR" || exit 1
        touch SHA256SUMS
        for f in "$@"; do
            [ -s "$f" ] || continue
            grep -q "  $f\$" SHA256SUMS || sha256sum "$f" >> SHA256SUMS
        done
        sha256sum -c --quiet SHA256SUMS
    ) || { DIE_CODE=3 die "base integrity check failed in $B_DIR (SHA256SUMS)"; }
}

prepare_base_yocto() {
    [ -s "$BASE_ROOTFS_SRC" ] || die "base rootfs missing: $BASE_ROOTFS_SRC"
    [ -s "$BASE_KERNEL_SRC" ] || die "base kernel missing: $BASE_KERNEL_SRC"
    base_copy "$BASE_KERNEL_SRC" "$B_DIR/Image"
    base_copy "$BASE_ROOTFS_SRC" "$B_DIR/rootfs.ext4"
    base_seal Image rootfs.ext4
}

prepare_base_debian() {
    local img=$B_DIR/$BASE_IMAGE_FILE
    if [ ! -s "$img" ]; then
        [ "${EGW_COMPARE_ALLOW_DOWNLOAD:-0}" = 1 ] \
            || die "base image absent: $img. Its download ($BASE_IMAGE_URL) runs only with EGW_COMPARE_ALLOW_DOWNLOAD=1 (an authorised download)"
        log_line "$S_LOG" "downloading $BASE_IMAGE_URL"
        curl -fL --retry 3 --retry-delay 5 -o "$img.part" "$BASE_IMAGE_URL" || die "download failed"
        echo "$BASE_IMAGE_SHA512  $img.part" | sha512sum -c --quiet \
            || { rm -f "$img.part"; DIE_CODE=3 die "SHA512 of the downloaded image differs from the published value"; }
        mv "$img.part" "$img"
        chmod 0444 "$img"
        log_line "$S_LOG" "downloaded and verified: $img"
    else
        echo "$BASE_IMAGE_SHA512  $img" | sha512sum -c --quiet || { DIE_CODE=3 die "base image $img no longer matches its published SHA512"; }
    fi
    if [ ! -s "$B_DIR/vmlinuz" ] || [ ! -s "$B_DIR/initrd.img" ] || [ ! -s "$B_DIR/root-uuid.txt" ]; then
        bash "$HERE/debian/extract_boot.sh" "$img" "$B_DIR" || { DIE_CODE=3 die "kernel/initrd extraction from $img failed"; }
        log_line "$S_LOG" "boot files extracted from $img"
    fi
    [ -s "$B_DIR/prepared.qcow2" ] || debian_firstboot "$img"
    base_seal "$BASE_IMAGE_FILE" vmlinuz initrd.img root-uuid.txt prepared.qcow2
}

# qemu_argv ROOT_DISK ROOT_FMT CONSOLE APPEND [daemon|foreground]: the ONE machine profile, into the
# array QEMU_ARGV. Device set as recorded for the pilot; only the serial/monitor back ends differ
# (files and a socket instead of stdio), identically for both scenarios.
qemu_argv() {
    local root=$1 fmt=$2 console=$3 append=$4 mode=$5
    QEMU_ARGV=("$COMPARE_QEMU" "${COMPARE_MACHINE_ARGS[@]}"
        -device "virtio-net-pci,netdev=net0,mac=$COMPARE_MAC"
        -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:$COMPARE_SSH_PORT-:22,hostfwd=tcp:127.0.0.1:$COMPARE_MQTT_PORT-:8883"
        -object rng-random,filename=/dev/urandom,id=rng0 -device virtio-rng-pci,rng=rng0
        -drive "id=disk0,file=$root,if=none,format=$fmt" -device virtio-blk-pci,drive=disk0
        -drive "id=disk1,file=$S_DATA_DISK,if=none,format=raw" -device virtio-blk-pci,drive=disk1
        -device virtio-gpu-pci -display none
        -serial "file:$console" -serial null
        -monitor "unix:$S_MONITOR,server,nowait"
        -no-reboot
        -kernel "$BASE_KERNEL")
    [ -n "$BASE_INITRD" ] && QEMU_ARGV+=(-initrd "$BASE_INITRD")
    QEMU_ARGV+=(-append "$append")
    [ "$mode" = daemon ] && QEMU_ARGV+=(-daemonize -pidfile "$S_PIDFILE")
    return 0
}

start_guards() {
    if pilot_session_open; then
        die "the session tooling has a session open ($COMPARE_EXEC/current_session): no comparison guest starts while it exists"
    fi
    local others rc
    others=$(qemu_others)
    rc=$?
    case $rc in
        0) die "another qemu-system-aarch64 is running and is never stopped by this tool:
$others" ;;
        2) die "could not determine whether a QEMU process is running (pgrep); refusing to start" ;;
    esac
    local busy
    if busy=$(ports_busy); then die "host port(s) of the profile already have a listener:$busy"; fi
    lock_acquire || die "the profile's lock is held by scenario '$(lock_holder)'"
}

# debian_firstboot IMAGE: the one provisioning boot of the pristine image (cloud-init NoCloud seed
# served from the host loopback), in the foreground under a time limit; on a clean power-down the
# overlay is flattened into the immutable prepared base.
debian_firstboot() {
    local img=$1 ovl=$S_DIR/disks/firstboot.qcow2 seed=$S_DIR/state/seed s t0 t1 rc
    s=$(stamp)
    local console=$S_DIR/logs/firstboot-console-$s.log
    [ -s "$COMPARE_SSH_KEY.pub" ] || die "public key missing: $COMPARE_SSH_KEY.pub"
    resolve_base
    [ -n "$ROOT_UUID" ] || die "root UUID unknown ($B_DIR/root-uuid.txt)"
    start_guards
    prepare_data_disk
    rm -rf "$seed"
    mkdir -p "$seed"
    python3 "$HERE/debian/render_seed.py" --pubkey "$COMPARE_SSH_KEY.pub" --hostname "$GUEST_HOSTNAME" \
        --repo "$COMPARE_REPO" --out "$seed" --mask-timers || die "seed rendering failed"
    rm -f "$ovl"
    "$COMPARE_QEMU_IMG" create -q -f qcow2 -b "$img" -F qcow2 "$ovl" || die "first-boot overlay"
    local append fb
    append=${KERNEL_APPEND//@ROOT_UUID@/$ROOT_UUID}
    fb=${FIRSTBOOT_APPEND//@SEED_PORT@/$COMPARE_SEED_PORT}
    qemu_argv "$ovl" qcow2 "$console" "$append $fb" foreground
    printf '%q ' "${QEMU_ARGV[@]}" > "$S_DIR/logs/firstboot-argv-$s.txt"
    python3 -m http.server --bind 127.0.0.1 "$COMPARE_SEED_PORT" --directory "$seed" \
        > "$S_DIR/logs/firstboot-seed-http-$s.log" 2>&1 &
    local seed_pid=$!
    log_line "$S_LOG" "first boot of $SCENARIO started (seed server pid $seed_pid, limit ${COMPARE_FIRSTBOOT_LIMIT_S}s)"
    t0=$(uptime_s)
    timeout "$COMPARE_FIRSTBOOT_LIMIT_S" "${QEMU_ARGV[@]}" > "$S_DIR/logs/firstboot-qemu-$s.log" 2>&1
    rc=$?
    t1=$(uptime_s)
    kill "$seed_pid" 2> /dev/null || true
    rm -f "$S_MONITOR"
    lock_release
    log_line "$S_LOG" "first boot ended: qemu rc=$rc, $(awk -v a="$t0" -v b="$t1" 'BEGIN { printf "%.1f", b - a }') s"
    python3 "$HERE/debian/firstboot_check.py" "$console" || { DIE_CODE=3 die "the first boot did not complete cleanly (rc=$rc); see $console; no prepared base was written"; }
    "$COMPARE_QEMU_IMG" convert -O qcow2 "$ovl" "$B_DIR/prepared.qcow2.part" || die "flattening the prepared base failed"
    mv "$B_DIR/prepared.qcow2.part" "$B_DIR/prepared.qcow2"
    chmod 0444 "$B_DIR/prepared.qcow2"
    rm -f "$ovl"
    log_line "$S_LOG" "prepared base written: $B_DIR/prepared.qcow2"
}

# --- work disks and manifest ---------------------------------------------------------------------

prepare_data_disk() {
    [ -s "$S_DATA_DISK" ] && return 0
    truncate -s "$COMPARE_DATA_DISK_SIZE" "$S_DATA_DISK" || die "data disk"
    mkfs.ext4 -q -F -L "$COMPARE_DATA_DISK_LABEL" "$S_DATA_DISK" || die "mkfs.ext4 on the data disk"
    [ "$(blkid -o value -s LABEL "$S_DATA_DISK")" = "$COMPARE_DATA_DISK_LABEL" ] || die "data disk label"
    log_line "$S_LOG" "data disk created: $S_DATA_DISK ($COMPARE_DATA_DISK_SIZE, ext4, label $COMPARE_DATA_DISK_LABEL)"
}

prepare_work_disks() {
    resolve_base
    [ -s "$BASE_ROOT" ] || die "base root missing: $BASE_ROOT"
    if [ ! -s "$S_ROOT_DISK" ]; then
        "$COMPARE_QEMU_IMG" create -q -f qcow2 -b "$BASE_ROOT" -F "$ROOT_FORMAT" "$S_ROOT_DISK" || die "root overlay"
        log_line "$S_LOG" "root overlay created: $S_ROOT_DISK on $BASE_ROOT ($ROOT_FORMAT)"
    fi
    prepare_data_disk
}

base_sha() { awk -v f="$1" '$2 == f { print $1 }' "$B_DIR/SHA256SUMS" 2> /dev/null | head -n 1; }

write_manifest() {
    [ -s "$S_MANIFEST" ] && return 0
    resolve_base
    local qv repo_commit dirty
    qv=$("$COMPARE_QEMU" --version 2> /dev/null | head -n 1)
    repo_commit=$(git -C "$COMPARE_REPO" rev-parse HEAD 2> /dev/null || echo unknown)
    dirty=$(git -C "$COMPARE_REPO" status --porcelain 2> /dev/null | wc -l | tr -d ' ')
    python3 - "$S_MANIFEST" \
        scenario="$SCENARIO" distro_label="$DISTRO_LABEL" guest_hostname="$GUEST_HOSTNAME" base_kind="$BASE_KIND" \
        base_root="$BASE_ROOT" base_root_sha256="$(base_sha "$(basename "$BASE_ROOT")")" \
        base_kernel="$BASE_KERNEL" base_kernel_sha256="$(base_sha "$(basename "$BASE_KERNEL")")" \
        base_initrd="$BASE_INITRD" base_initrd_sha256="$([ -n "$BASE_INITRD" ] && base_sha "$(basename "$BASE_INITRD")")" \
        base_source_rootfs="$BASE_ROOTFS_SRC" base_source_kernel="$BASE_KERNEL_SRC" \
        base_image_url="$BASE_IMAGE_URL" base_image_sha512="$BASE_IMAGE_SHA512" root_uuid="$ROOT_UUID" \
        root_format="$ROOT_FORMAT" kernel_append="${KERNEL_APPEND//@ROOT_UUID@/$ROOT_UUID}" \
        qemu_path="$COMPARE_QEMU" qemu_version="$qv" qemu_sha256="$(sha256_of "$COMPARE_QEMU")" \
        qemu_img_version="$("$COMPARE_QEMU_IMG" --version 2> /dev/null | head -n 1)" \
        machine_args="${COMPARE_MACHINE_ARGS[*]}" mac="$COMPARE_MAC" host_ports="$COMPARE_HOST_PORTS" \
        root_disk="$S_ROOT_DISK" data_disk="$S_DATA_DISK" data_disk_size="$COMPARE_DATA_DISK_SIZE" data_disk_label="$COMPARE_DATA_DISK_LABEL" \
        host_node="$(uname -n)" host_kernel="$(uname -r)" host_nproc="$(nproc)" \
        host_cpu="$(awk -F': ' '/model name/ { print $2; exit }' /proc/cpuinfo)" host_mem_total_kb="$(awk '/MemTotal/ { print $2 }' /proc/meminfo)" \
        repo="$COMPARE_REPO" repo_commit="$repo_commit" repo_dirty_lines="$dirty" \
        script_sha256="$(sha256_of "$HERE/compare_env.sh")" lib_sha256="$(sha256_of "$HERE/lib.sh")" \
        scenario_env_sha256="$(sha256_of "$COMPARE_SCENARIOS_DIR/$SCENARIO.env")" created_utc="$(utc_now)" \
        known_differences="${KNOWN_DIFFERENCES:-}" << 'PY'
import json, sys
out = sys.argv[1]
d = {}
for kv in sys.argv[2:]:
    k, _, v = kv.partition("=")
    d[k] = v
m = {
    "scenario": d["scenario"], "distro_label": d["distro_label"], "guest_hostname": d["guest_hostname"],
    "base_kind": d["base_kind"], "created_utc": d["created_utc"],
    "base": {k[5:]: v for k, v in d.items() if k.startswith("base_")},
    "root_uuid": d["root_uuid"], "root_format": d["root_format"], "kernel_append": d["kernel_append"],
    "qemu": {"path": d["qemu_path"], "version": d["qemu_version"], "sha256": d["qemu_sha256"],
             "qemu_img_version": d["qemu_img_version"], "accelerator": "tcg"},
    "machine_args": d["machine_args"], "netdev": {"mac": d["mac"], "hostfwd_host_ports": d["host_ports"],
                                                   "mode": "user (slirp), 127.0.0.1 only"},
    "disks": {"root": {"path": d["root_disk"], "kind": "qcow2 overlay on the immutable base"},
              "data": {"path": d["data_disk"], "size": d["data_disk_size"], "fs": "ext4",
                       "label": d["data_disk_label"], "mount": "/var/lib/docker"}},
    "host": {"node": d["host_node"], "kernel": d["host_kernel"], "nproc": d["host_nproc"],
             "cpu": d["host_cpu"], "mem_total_kb": d["host_mem_total_kb"]},
    "tools": {"repo": d["repo"], "repo_commit": d["repo_commit"], "repo_dirty_lines": d["repo_dirty_lines"],
              "compare_env_sha256": d["script_sha256"], "lib_sha256": d["lib_sha256"],
              "scenario_env_sha256": d["scenario_env_sha256"]},
    "known_differences": [x for x in d["known_differences"].split("|") if x],
    "notes": "Equal machine profile for both scenarios; the differences table is in tools/compare/README.md.",
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(m, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
    log_line "$S_LOG" "manifest written: $S_MANIFEST"
}

# --- commands ------------------------------------------------------------------------------------

cmd_prepare() {
    scenario_dirs
    [ -x "$COMPARE_QEMU" ] || die "QEMU not found or not executable: $COMPARE_QEMU"
    [ -x "$COMPARE_QEMU_IMG" ] || die "qemu-img not found or not executable: $COMPARE_QEMU_IMG"
    case $BASE_KIND in
        yocto-deploy) prepare_base_yocto ;;
        debian-cloud) prepare_base_debian ;;
        *) die "unknown BASE_KIND '$BASE_KIND'" ;;
    esac
    prepare_work_disks
    write_manifest
    echo "PREPARED $SCENARIO: root=$S_ROOT_DISK data=$S_DATA_DISK manifest=$S_MANIFEST"
}

cmd_start() {
    local pid s console
    scenario_dirs
    if pid=$(own_pid); then
        echo "already running: $SCENARIO pid $pid"
        return 0
    fi
    if [ -e "$S_PIDFILE" ]; then
        log_line "$S_LOG" "stale pid file removed: $(cat "$S_PIDFILE" 2> /dev/null)"
        rm -f "$S_PIDFILE"
    fi
    [ -s "$S_ROOT_DISK" ] && [ -s "$S_DATA_DISK" ] || die "scenario $SCENARIO is not prepared (run: compare_env.sh prepare $SCENARIO)"
    resolve_base
    [ -s "$BASE_KERNEL" ] || die "kernel missing: $BASE_KERNEL"
    base_seal "$(basename "$BASE_ROOT")" "$(basename "$BASE_KERNEL")"
    start_guards
    s=$(stamp)
    console=$S_DIR/logs/console-$s.log
    rm -f "$S_MONITOR"
    qemu_argv "$S_ROOT_DISK" qcow2 "$console" "${KERNEL_APPEND//@ROOT_UUID@/$ROOT_UUID}" daemon
    printf '%q ' "${QEMU_ARGV[@]}" > "$S_DIR/state/argv.txt"
    echo >> "$S_DIR/state/argv.txt"
    if ! "${QEMU_ARGV[@]}" > "$S_DIR/logs/start-$s.log" 2>&1; then
        lock_release
        log_line "$S_LOG" "start FAILED: see logs/start-$s.log"
        DIE_CODE=5 die "QEMU did not start; see $S_DIR/logs/start-$s.log"
    fi
    # The daemonised QEMU writes its pid file before the parent returns; allow a short settling
    # window anyway before reading the live pid back.
    local i
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
        pid=$(own_pid) && break
        sleep 0.25
    done
    if [ -z "${pid:-}" ]; then
        lock_release
        DIE_CODE=5 die "QEMU returned but left no live pid in $S_PIDFILE; see $S_DIR/logs/start-$s.log"
    fi
    uptime_s > "$S_DIR/state/started"
    utc_now > "$S_DIR/state/started_utc"
    printf '%s\n' "$console" > "$S_DIR/state/console"
    log_line "$S_LOG" "started: pid $pid console $console argv-sha256 $(sha256_of "$S_DIR/state/argv.txt")"
    echo "STARTED $SCENARIO: pid $pid console $console"
}

cmd_status() {
    local pid running=false prepared=false started="" root_sha="" base
    pid=$(own_pid 2> /dev/null || true)
    [ -n "$pid" ] && running=true
    [ -s "$S_ROOT_DISK" ] && [ -s "$S_DATA_DISK" ] && [ -s "$S_MANIFEST" ] && prepared=true
    [ -s "$S_DIR/state/started" ] && started=$(cat "$S_DIR/state/started")
    resolve_base 2> /dev/null || true
    base=${BASE_ROOT:-}
    [ -n "$base" ] && root_sha=$(base_sha "$(basename "$base")")
    python3 - "$SCENARIO" "$prepared" "$running" "$pid" "$(lock_holder)" "$started" \
        "$S_ROOT_DISK" "$S_DATA_DISK" "$root_sha" "$S_MANIFEST" "$(cat "$S_DIR/state/console" 2> /dev/null || true)" << 'PY'
import json, sys
keys = ["scenario", "prepared", "running", "pid", "lock_holder", "started_uptime_s",
        "root_disk", "data_disk", "base_sha256", "manifest", "console"]
print(json.dumps({k: str(v) for k, v in zip(keys, sys.argv[1:])}))
PY
    return 0
}

cmd_stop() {
    local pid log method t0 t1
    if ! pid=$(own_pid); then
        [ -e "$S_PIDFILE" ] && { log_line "$S_LOG" "stale pid file removed at stop"; rm -f "$S_PIDFILE"; }
        lock_release
        echo "not running: $SCENARIO"
        return 0
    fi
    log=$S_DIR/logs/stop-$(stamp).log
    t0=$(uptime_s)
    log_line "$log" "stop requested: pid $pid"
    # Recorded stack stop first (the controller's own grace period), only where a deployment exists.
    gssh 'if [ -f /opt/egw/deployment/.env ]; then cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env stop -t 60; echo "stack stop exit=$?"; docker ps -a --format "{{.Names}} {{.Status}}"; else echo "no deployment on the guest"; fi' >> "$log" 2>&1 \
        || log_line "$log" "stack stop over ssh failed or unreachable; continuing to the power-off"
    if gssh 'sync; sudo -n poweroff' >> "$log" 2>&1; then
        method=ssh-poweroff
    else
        method=monitor-system_powerdown
        log_line "$log" "ssh poweroff failed; sending system_powerdown through the monitor"
        monitor_cmd system_powerdown >> "$log" 2>&1 || log_line "$log" "monitor command failed"
    fi
    if wait_gone "$pid" "$COMPARE_STOP_WAIT_S"; then
        t1=$(uptime_s)
        rm -f "$S_PIDFILE" "$S_MONITOR"
        lock_release
        log_line "$log" "ended: pid $pid gone after $(awk -v a="$t0" -v b="$t1" 'BEGIN { printf "%.1f", b - a }') s ($method)"
        log_line "$S_LOG" "stopped: pid $pid ($method)"
        echo "STOPPED $SCENARIO: pid $pid ended ($method)"
        return 0
    fi
    log_line "$log" "STILL RUNNING after ${COMPARE_STOP_WAIT_S}s ($method); not killed"
    echo "STOP: QEMU pid $pid of scenario $SCENARIO is still running ${COMPARE_STOP_WAIT_S} s after $method; it was NOT killed. Inspect $log and the console, then decide." >&2
    exit 5
}

cmd_destroy() {
    local pid keep
    if pid=$(own_pid); then
        echo "STOP: scenario $SCENARIO is running (pid $pid); stop it first - nothing was removed" >&2
        exit 5
    fi
    [ -d "$S_DIR" ] || { echo "nothing to destroy: $SCENARIO"; return 0; }
    keep=$S_DIR/results/destroy-$(stamp)
    mkdir -p "$keep"
    local f
    for f in "$S_DIR/state/argv.txt" "$S_DIR/state/started" "$S_DIR/state/started_utc" "$S_DIR/state/provision.json" "$S_MANIFEST"; do
        [ -e "$f" ] && cp -p "$f" "$keep/"
    done
    rm -f "$S_ROOT_DISK" "$S_DATA_DISK" "$S_DIR/disks/firstboot.qcow2"
    rm -rf "$S_DIR/state"
    lock_release
    log_line "$S_LOG" "destroyed: work disks and state removed; bases, logs, results kept (copies in $keep)"
    echo "DESTROYED $SCENARIO: work disks and state removed; bases, logs and results kept"
}

# disks: capacity (virtual size), host allocation and apparent size of each disk file, kept apart;
# the space USED inside the guest is read by validate.sh (df) and never from these figures.
cmd_disks() {
    python3 - "$COMPARE_QEMU_IMG" "$S_ROOT_DISK" "$S_DATA_DISK" "${BASE_ROOT:-}" << 'PY'
import json, os, subprocess, sys
qemu_img = sys.argv[1]
out = {}
for path in sys.argv[2:]:
    if not path or not os.path.exists(path):
        continue
    st = os.stat(path)
    rec = {"apparent_bytes": st.st_size, "host_allocated_bytes": st.st_blocks * 512}
    try:
        info = json.loads(subprocess.run([qemu_img, "info", "--output=json", "--force-share", path],
                                         capture_output=True, text=True, check=True).stdout)
        rec.update({"format": info.get("format"), "virtual_size_bytes": info.get("virtual-size"),
                    "backing_file": info.get("backing-filename")})
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        rec["qemu_img_info"] = f"unavailable: {exc}"
    out[path] = rec
print(json.dumps(out, indent=2, sort_keys=True))
PY
}

case $cmd in
    disks) resolve_base 2> /dev/null; cmd_disks ;;
    prepare) cmd_prepare ;;
    start) cmd_start ;;
    status) cmd_status ;;
    stop) cmd_stop ;;
    destroy) cmd_destroy ;;
    manifest) printf '%s\n' "$S_MANIFEST" ;;
    *) usage ;;
esac
