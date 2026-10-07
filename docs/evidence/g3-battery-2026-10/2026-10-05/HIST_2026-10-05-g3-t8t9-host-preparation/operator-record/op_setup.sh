#!/bin/bash
# Stream OPERATOR: an isolated tree for exercising, one at a time, the functions of
# g3_battery.sh that changed for S3 (brief, hard rule 2). Everything lives under
# /tmp/g3-s3-op-<name>: a COPY of tools/ and src/egw_experiments of the worktree S/pb (the
# merged tree 2f05148), the runbook blob as the clone's runbook, HOME and every EGW_*
# inside the bench, stub git, sha256sum, pgrep and ssh first on PATH. No guest, no QEMU,
# no docker, no real ssh; nothing is written under ~/egw-exec, ~/egw-tcg, ~/yocto or
# output_test. Three real files are READ and copied (itest-helpers.sh, tunnel.sh, ca.crt),
# as the first preparation's bench did; the real venv's python is used read-only.
# Usage (WSL): op_setup.sh /tmp/g3-s3-op-<name>
set -u
B=${1:?usage: op_setup.sh /tmp/g3-s3-op-<name>}
case $B in /tmp/g3-s3-op-?*) ;; *) echo "refused: the bench must be /tmp/g3-s3-op-<name>"; exit 2 ;; esac
[ ! -e "$B" ] || { echo "refused: $B exists"; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
S=$(cd "$HERE/../../.." && pwd)       # the scratchpad: this file is S/g3/s3prep/operator-record/op_setup.sh
PB=$S/pb
REAL_TCG=/home/ruisth/egw-tcg
TOOLS=8e492613d36490a560ae56beabd6d5c2c01a8696
TREE=2f0514837f267d8975f7071041aad14a5c18dcab

mkdir -p "$B"/home/egw-tcg/itest "$B"/home/egw-tcg/itest-replay "$B"/home/egw-tcg/pilot/results/raw \
    "$B"/home/.ssh "$B"/egw-exec/attempts "$B"/out/runs/2026-10-03 "$B"/out/incomplete "$B"/repo/src \
    "$B"/repo/docs/setup "$B"/stubs "$B"/guest "$B"/fix || exit 1
cp -r "$PB/tools" "$B/repo/tools" || exit 1
cp -r "$PB/src/egw_experiments" "$B/repo/src/egw_experiments" || exit 1
find "$B/repo" -name __pycache__ -prune -exec rm -rf {} +
cp "$S/g3/s3prep/runbook.8e49261.md" "$B/repo/docs/setup/qemu_integrated_gateway.md" || exit 1
cp "$REAL_TCG/itest-helpers.sh" "$REAL_TCG/tunnel.sh" "$REAL_TCG/ca.crt" "$B/home/egw-tcg/" || exit 1
printf 'MOSQUITTO_SIMULATOR_PASSWORD=bench-value-0000\n' > "$B/home/egw-tcg/.env"

# The Yocto tree: fake files at the paths guest_common.sh derives from EGW_YOCTO_CHECKOUT.
Y=$B/yocto/egw
DEPD=$Y/src/yocto/build-integrated/tmp/deploy/images/qemuarm64
QD=$Y/src/yocto/build-integrated/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin
mkdir -p "$DEPD" "$QD" || exit 1
printf 'bench kernel\n' > "$DEPD/Image-qemuarm64.bin"
printf 'bench rootfs\n' > "$DEPD/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4"
printf 'bench qemuboot\n' > "$DEPD/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf"
printf 'bench qemu binary\n' > "$QD/qemu-system-aarch64"

# --- stubs, first on PATH ---------------------------------------------------------------
cat > "$B/stubs/git" << EOS
#!/bin/bash
# BENCH STUB: neither tree of the bench is a git checkout. The identity reads answer the
# recorded values, or what a flag file of the bench says instead.
dir=""
[ "\$1" != -C ] || dir=\$2
case "\$dir" in
    */yocto/egw)
        case "\$*" in
            *"rev-parse HEAD"*) cat "\$BENCH/git.yocto.head" 2> /dev/null || echo 489bc9e5b5b0660026ea2630b8d1d124049ba2ce ;;
            *"status --porcelain"*) [ ! -e "\$BENCH/git.yocto.dirty" ] || echo " M bench" ;;
            *) echo "bench git stub: not answered: \$*" >&2; exit 1 ;;
        esac ;;
    *)
        case "\$*" in
            *"rev-parse HEAD^{tree}"*) echo $TREE ;;
            *"rev-parse HEAD"*) echo $TOOLS ;;
            *"status --porcelain"*) [ ! -e "\$BENCH/git.dirty" ] || echo " M bench" ;;
            *) echo "bench git stub: not answered: \$*" >&2; exit 1 ;;
        esac ;;
esac
EOS
cat > "$B/stubs/sha256sum" << 'EOS'
#!/bin/bash
# BENCH STUB: the four fake build artefacts answer the recorded values (or the content of
# $BENCH/sha.<kind> when that file exists); everything else, stdin included, is hashed
# for real.
files=()
for a in "$@"; do case $a in -*) ;; *) files+=("$a") ;; esac; done
[ "${#files[@]}" -gt 0 ] || exec /usr/bin/sha256sum "$@"
rc=0
for f in "${files[@]}"; do
    case $f in
        */Image-qemuarm64.bin) echo "$(cat "$BENCH/sha.kernel" 2> /dev/null || echo 4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037)  $f" ;;
        *.qemuboot.conf) echo "$(cat "$BENCH/sha.qemuboot" 2> /dev/null || echo 7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4)  $f" ;;
        */qemu-system-aarch64) echo "$(cat "$BENCH/sha.qemu" 2> /dev/null || echo 5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061)  $f" ;;
        *.rootfs-*.ext4) echo "$(cat "$BENCH/sha.rootfs" 2> /dev/null || echo 22e9da8533541582a2e4549f4c37f2b80f0f6a9bd3a5f0dd5e13605d7269efcd)  $f" ;;
        *) /usr/bin/sha256sum "$f" || rc=1 ;;
    esac
done
exit $rc
EOS
cat > "$B/stubs/pgrep" << 'EOS'
#!/bin/bash
# BENCH STUB: the question about qemu-system-aarch64 is answered from the recorded pid of
# the bench's fake process (a real process: /proc/PID/stat and /proc/PID/cmdline exist).
case "$*" in
    *qemu-system-aarch64*)
        pid=$(cat "$BENCH/qemu.pid" 2> /dev/null)
        [ -n "$pid" ] && [ -d "/proc/$pid" ] || exit 1
        case "$1" in
            -a*) echo "$pid qemu-system-aarch64 $(tr '\0' ' ' < "/proc/$pid/cmdline" | cut -c1-200) (bench stub)" ;;
            *) echo "$pid" ;;
        esac
        exit 0 ;;
esac
exec /usr/bin/pgrep "$@"
EOS
cat > "$B/stubs/fake_qemu_start.sh" << 'EOS'
#!/bin/bash
# BENCH: starts the fake qemu-system-aarch64 process (a bash loop) whose argv carries two
# -drive file= entries and whatever extra arguments are given, and records its pid.
B=${BENCH:?}
setsid bash -c 'while :; do sleep 5; done' qemu-system-aarch64 -machine virt \
    -drive "id=disk0,file=$B/rootfs.ext4,if=none,format=raw" -device virtio-blk-pci,drive=disk0 \
    -drive "id=disk1,file=$B/data.img,if=none,format=raw" -device virtio-blk-pci,drive=disk1 "$@" \
    > /dev/null 2>&1 < /dev/null &
echo $! > "$B/qemu.pid"
EOS
cat > "$B/stubs/ssh" << 'EOS'
#!/bin/bash
# BENCH STUB of ssh: there is no guest. What a call does is taken from the first line of
# $BENCH/ssh.seq (which is then removed from that file), or from $BENCH/ssh.mode:
#   ok              answer the guest command, exit 0
#   refuse          'Connection refused', exit 255
#   print-then-hang answer, then stall for 300 s (a read the timeout must end)
#   print-then-255  answer, then exit 255
#   hang            stall for 300 s without an answer
#   banner          print a line that is not the answer, exit 0
#   two-lines       print a banner line and the answer, exit 0
# The guest's files are files of the bench ($BENCH/guest/...). The tunnel's control
# commands (-O check, -O exit, -M) answer as a master that is up.
printf '%s ssh %s\n' "$(cut -d' ' -f1 /proc/uptime)" "$*" >> "$BENCH/ssh.log"
op=""; args=("$@"); i=0; cmd=()
while [ "$i" -lt "${#args[@]}" ]; do
    a=${args[$i]}
    case $a in
        -O) i=$((i + 1)); op=${args[$i]} ;;
        -S | -i | -p | -o | -L | -l) i=$((i + 1)) ;;
        -M) op=master ;;
        -*) ;;
        *) cmd=("${args[@]:$((i + 1))}"); break ;;
    esac
    i=$((i + 1))
done
case $op in
    check) [ ! -e "$BENCH/tunnel.down" ] && exit 0; echo "Control socket connect: Connection refused" >&2; exit 255 ;;
    exit) echo "Exit request sent."; exit 0 ;;
    master) exit 0 ;;
esac
mode=""
if [ -s "$BENCH/ssh.seq" ]; then
    mode=$(head -n 1 "$BENCH/ssh.seq")
    sed -i 1d "$BENCH/ssh.seq"
fi
[ -n "$mode" ] || mode=$(cat "$BENCH/ssh.mode" 2> /dev/null || echo ok)
answer() {
    case "${cmd[*]}" in
        *boot_id*) cat "$BENCH/guest/boot_id" ;;
        *"docker ps -q"*) cat "$BENCH/guest/containers" ;;
        *"ls -1 /opt/egw/deployment/data/events"*) cat "$BENCH/guest/events" ;;
        *findmnt*) cat "$BENCH/guest/mount" ;;
        *) echo "bench ssh stub: ${cmd[*]}" | cut -c1-160 ;;
    esac
}
case $mode in
    ok) answer; exit 0 ;;
    refuse) echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255 ;;
    print-then-hang) answer; sleep 300; exit 0 ;;
    print-then-255) answer; echo "Connection to 127.0.0.1 closed by remote host." >&2; exit 255 ;;
    hang) sleep 300; exit 0 ;;
    banner) echo "Welcome to the bench (not a boot id)"; exit 0 ;;
    two-lines) echo "Welcome to the bench"; answer; exit 0 ;;
    *) echo "bench ssh stub: unknown mode $mode" >&2; exit 1 ;;
esac
EOS
chmod +x "$B"/stubs/*
printf 'ok\n' > "$B/ssh.mode"
printf '11111111-1111-4111-8111-111111111111\n' > "$B/guest/boot_id"
echo "bench ready: $B"
