#!/bin/bash
# Stream BENCH: one isolated bench for g3_battery.sh (session S3) on the REAL step files of
# rows/ (brief, hard rule 2). Everything lives under /tmp/g3-s3-bench/<scenario>:
#   repo/     a COPY of tools/ and src/egw_experiments of the read-only worktree (the merged
#             tree 2f05148) and the runbook blob as the clone's runbook; in the copy only,
#             the four session drivers are stubs (no QEMU, no guest) and
#             proof_fetch_sut_log.sh is the test module's stub of it;
#   home/     HOME: egw-tcg/itest-helpers.sh and tunnel.sh written by the runbook's own
#             heredocs (sha256 compared with the recorded values), a bench .env;
#   mod/      the stubs, the stub guest state and the stub clone of the repository's own
#             test module (bs3_stubs.py imports it: STUB_SSH, STUB_CURL, STUB_PYTHON,
#             STUB_SCP, STUB_SS, STUB_SLEEP, STUB_TIMEOUT, Bench, t8_prepare);
#   stubs/    what the module does not hold: git, sha256sum, pgrep, ps (the keepalive
#             client the steps script looks for: a synthetic one) and openssl stubs, and
#             wrappers of ssh and scp that answer the steps script's OWN guest reads (the
#             gate, the close, the open's listing, test 9's probe and exposure reads) and
#             hand every other call to the module's stub unchanged;
#   venv/     EGW_EXEC_VENV: 'activate' and a 'python' that hands '-m egw_simulator' and
#             '-m egw_experiments.itest_reconcile' to the module's STUB_PYTHON and everything
#             else to the execution venv's real python (read-only, no bytecode written).
# A fake process stands for QEMU (a bash loop with a real /proc/PID/cmdline). No guest, no
# QEMU, no docker, no real ssh. Nothing is written under ~/egw-exec, ~/egw-tcg, ~/yocto or
# output_test; one sealed file of output_test is READ (S2's gate record).
# Usage (WSL): bs3_setup.sh /tmp/g3-s3-bench/<scenario>
set -u
B=${1:?usage: bs3_setup.sh /tmp/g3-s3-bench/<scenario>}
case $B in /tmp/g3-s3-bench/?*) ;; *) echo "refused: the bench must be /tmp/g3-s3-bench/<scenario>"; exit 2 ;; esac
[ ! -e "$B" ] || { echo "refused: $B exists"; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
S=$(cd "$HERE/../../.." && pwd)       # the scratchpad: this file is S/g3/s3prep/bench/bs3_setup.sh
PB=$S/pb
PREP=$S/g3/s3prep
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
TOOLS=8e492613d36490a560ae56beabd6d5c2c01a8696
TREE=2f0514837f267d8975f7071041aad14a5c18dcab
DRIVERS_SHA=4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5
ADMITTED=20261003T142310Z_g3-qualification-t8_attempt01

mkdir -p "$B"/home/egw-tcg/pilot/results/raw "$B"/home/.ssh "$B/egw-exec/attempts/$ADMITTED" \
    "$B/out/runs/2026-10-03/$ADMITTED" "$B"/out/incomplete "$B"/repo/src "$B"/repo/docs/setup "$B"/stubs \
    "$B"/venv/bin "$B"/hooks || exit 1
cp -r "$PB/tools" "$B/repo/tools" || exit 1
cp -r "$PB/src/egw_experiments" "$B/repo/src/egw_experiments" || exit 1
find "$B/repo" -name __pycache__ -prune -exec rm -rf {} +
cp "$PREP/runbook.8e49261.md" "$B/repo/docs/setup/qemu_integrated_gateway.md" || exit 1

# The drivers of the copy BEFORE the four stubs replace the session drivers: hashed the
# way common.sh's repo_identity hashes them. In the bench the sha256sum stub answers the
# recorded value for that stream, because the copy's drivers are then stubs.
got=$(cat "$B"/repo/tools/session/*.sh "$B"/repo/tools/session/*.py "$B"/repo/tools/session/guest/*.sh | /usr/bin/sha256sum | cut -d' ' -f1)
echo "drivers of the copy before the stubs: $got ($([ "$got" = "$DRIVERS_SHA" ] && echo 'the recorded drivers_sha256' || echo "NOT the recorded $DRIVERS_SHA"))"
[ "$got" = "$DRIVERS_SHA" ] || exit 1

# --- the module's stubs and state; the helper file and tunnel.sh from the runbook ----------
PYTHONDONTWRITEBYTECODE=1 "$REAL_PY" "$HERE/bs3_stubs.py" "$PB" "$B" || { echo "bs3_stubs.py failed"; exit 1; }
# A second stub directory without the module's sleep and timeout: the default PATH of a
# bench uses the host's own sleep and timeout; a scenario that needs the runbook's 10 s
# pauses shortened puts mod/stubs (with STUB_SLEEP and STUB_TIMEOUT) on PATH instead.
mkdir "$B/mod/stubs-realtime" || exit 1
for f in "$B"/mod/stubs/*; do
    case ${f##*/} in sleep | timeout) ;; *) ln -s "$f" "$B/mod/stubs-realtime/${f##*/}" ;; esac
done
cp "$B/mod/clone/tools/session/proof_fetch_sut_log.sh" "$B/repo/tools/session/proof_fetch_sut_log.sh" || exit 1

printf 'bench placeholder for ca.crt (its recorded sha256 is answered by the sha256sum stub)\n' > "$B/home/egw-tcg/ca.crt"
printf 'MOSQUITTO_SIMULATOR_PASSWORD=bench-value-0000\n' > "$B/home/egw-tcg/.env"
printf '{"role": "sut", "provider": "", "region": "", "instance_type": "", "shared_vcpu_note": ""}\n' > "$B/home/egw-tcg/sut_environment.json"
printf 'bench data disk\n' > "$B/data.img"
printf 'bench rootfs disk (the fake process names it)\n' > "$B/rootfs.ext4"
# The gate's record: S2's sealed file with other container ids and start instants.
sed 's/container_id=[0-9a-f]*/container_id=1111111111111111111111111111111111111111111111111111111111111111/; s/started=.*$/started=2026-10-05T10:00:00.000000001Z/' \
    "$OT/runs/2026-10-03/20261003T132836Z_g2-gate-preconditions_attempt06/environment/container_identities.txt" > "$B/gate.identities" || exit 1

# The Yocto tree: fake files at the paths guest_common.sh derives from EGW_YOCTO_CHECKOUT.
Y=$B/yocto/egw
DEPD=$Y/src/yocto/build-integrated/tmp/deploy/images/qemuarm64
QD=$Y/src/yocto/build-integrated/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin
mkdir -p "$DEPD" "$QD" || exit 1
printf 'bench kernel\n' > "$DEPD/Image-qemuarm64.bin"
printf 'bench rootfs\n' > "$DEPD/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4"
printf 'bench qemuboot\n' > "$DEPD/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf"
printf 'bench qemu binary\n' > "$QD/qemu-system-aarch64"

# --- the bench venv -------------------------------------------------------------------------
cat > "$B/venv/bin/activate" << 'EOS'
# BENCH venv (sourced by the host preamble of runbook 6.1 in every step shell): puts the
# bench's 'python' first, as the real venv's activate does.
VIRTUAL_ENV=$BENCH/venv
export VIRTUAL_ENV
PATH=$VIRTUAL_ENV/bin:$PATH
export PATH
# BENCH DEVICE (off unless BENCH_FAST_DRAIN=1): the helper's 'drained' needs a quiet window
# of 130 s of /proc/uptime when DRAIN_QUIET_S is unset, and the steps script unsets it in
# every step shell. With this device the two carriers are read-only at 0 (the values the
# repository's own tests give them), so the unset of the step shell fails for these two
# names and prints so, and 'drained' returns after two readings. The success scenario and
# the 900 s expiry run WITHOUT it.
if [ "${BENCH_FAST_DRAIN:-0}" = 1 ]; then readonly DRAIN_QUIET_S=0 DRAIN_STEP_S=0; fi
EOS
cat > "$B/venv/bin/python" << 'EOS'
#!/bin/bash
# BENCH: the venv's python. The simulator and the reconcile helper ($SIM and $REC of the
# helper file; the harness is not used by tests 8 and 9) are the test module's STUB_PYTHON;
# everything else - the steps script's own $PY, the export tool, driver_status.py,
# guest_state_delta.py, the row files' python3 - is the execution venv's real python.
# Bench hooks, before the module's stub runs: $EGW_STUB_STATE/bench_hook.sim.<run id> (a
# shell fragment, sourced) for one simulator call; $EGW_STUB_STATE/bench_rec_check_text
# (printed before the stub's own line) for 'itest_reconcile check', which in the real
# helper prints the row with "lost" and "late_confirmations"; and, before the real export
# tool runs, $EGW_STUB_STATE/bench_hook.exec.<step> (sourced once) for one recorded step.
if [ "${1:-}" = -m ]; then
    case ${2:-} in
        egw_simulator)
            rid=; prev=
            for a in "$@"; do [ "$prev" != --run-id ] || rid=$a; prev=$a; done
            # shellcheck source=/dev/null
            [ ! -r "$EGW_STUB_STATE/bench_hook.sim.$rid" ] || . "$EGW_STUB_STATE/bench_hook.sim.$rid"
            exec "$BENCH/mod/stubs/python" "$@" ;;
        egw_experiments.itest_reconcile)
            [ "${3:-}" != check ] || [ ! -r "$EGW_STUB_STATE/bench_rec_check_text" ] || cat "$EGW_STUB_STATE/bench_rec_check_text"
            exec "$BENCH/mod/stubs/python" "$@" ;;
        egw_experiments.local_export)
            # Bench hook, off unless $EGW_STUB_STATE/bench_hook.exec.<name> exists: a shell
            # fragment sourced ONCE, just before the export tool records the step <name>
            # ('exec --name <name>'), so that something happens between two recorded steps
            # (s14 to s17: the host's tunnel master ends there). The fragment is renamed
            # bench_hook.exec.<name>.done before it runs, and the moment is logged in
            # $BENCH/hooks.log.
            if [ "${3:-}" = exec ]; then
                name=; prev=
                for a in "$@"; do [ "$a" != -- ] || break; [ "$prev" != --name ] || name=$a; prev=$a; done
                if [ -n "$name" ] && [ -r "$EGW_STUB_STATE/bench_hook.exec.$name" ]; then
                    mv "$EGW_STUB_STATE/bench_hook.exec.$name" "$EGW_STUB_STATE/bench_hook.exec.$name.done"
                    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) the bench hook ran before the step $name was recorded" >> "$BENCH/hooks.log"
                    # shellcheck source=/dev/null
                    . "$EGW_STUB_STATE/bench_hook.exec.$name.done"
                fi
            fi
            # Bench hook, off unless $EGW_STUB_STATE/bench_capture_lost_poll holds a number N:
            # the N-th recorded poll of test 8's wait ('exec --name t8-wait-ssh') runs through
            # the real export tool as it is, and its status is then replaced by 74, the status
            # that tool answers when a console capture was lost. Every other call is untouched.
            if [ "${3:-}" = exec ] && [ -s "$EGW_STUB_STATE/bench_capture_lost_poll" ]; then
                case " $* " in
                    *" --name t8-wait-ssh "*)
                        n=$(($(cat "$EGW_STUB_STATE/bench_poll.calls" 2> /dev/null || echo 0) + 1))
                        echo "$n" > "$EGW_STUB_STATE/bench_poll.calls"
                        if [ "$n" = "$(cat "$EGW_STUB_STATE/bench_capture_lost_poll")" ]; then
                            /home/ruisth/egw-exec/venv/bin/python "$@"
                            echo "bench: the status of this poll ($?) is replaced by 74 (a lost console capture, as the export tool answers it)" >&2
                            exit 74
                        fi ;;
                esac
            fi ;;
    esac
fi
exec /home/ruisth/egw-exec/venv/bin/python "$@"
EOS
cat > "$B/venv/bin/python3" << 'EOS'
#!/bin/bash
# BENCH: python3 stays the execution venv's real python (read-only).
exec /home/ruisth/egw-exec/venv/bin/python "$@"
EOS

# --- stubs the module does not hold, first on PATH ------------------------------------------
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
cat > "$B/stubs/sha256sum" << EOS
#!/bin/bash
# BENCH STUB: the fake build artefacts and the placeholder ca.crt answer the recorded
# values (or the content of \$BENCH/sha.<kind> when that file exists); a stream on stdin
# answers the recorded drivers_sha256 (the session drivers of the copy are stubs: the
# copy's drivers were hashed for real by bs3_setup.sh before they were replaced); every
# other file is hashed for real.
files=()
for a in "\$@"; do case \$a in -*) ;; *) files+=("\$a") ;; esac; done
if [ "\${#files[@]}" -eq 0 ]; then cat > /dev/null; echo "$DRIVERS_SHA  -"; exit 0; fi
rc=0
for f in "\${files[@]}"; do
    case \$f in
        */Image-qemuarm64.bin) echo "\$(cat "\$BENCH/sha.kernel" 2> /dev/null || echo 4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037)  \$f" ;;
        *.qemuboot.conf) echo "\$(cat "\$BENCH/sha.qemuboot" 2> /dev/null || echo 7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4)  \$f" ;;
        */qemu-system-aarch64) echo "\$(cat "\$BENCH/sha.qemu" 2> /dev/null || echo 5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061)  \$f" ;;
        *.rootfs-*.ext4) echo "\$(cat "\$BENCH/sha.rootfs" 2> /dev/null || echo 22e9da8533541582a2e4549f4c37f2b80f0f6a9bd3a5f0dd5e13605d7269efcd)  \$f" ;;
        */egw-tcg/ca.crt) echo "556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff  \$f" ;;
        *) /usr/bin/sha256sum "\$f" || rc=1 ;;
    esac
done
exit \$rc
EOS
cat > "$B/stubs/pgrep" << 'EOS'
#!/bin/bash
# BENCH STUB: the question about qemu-system-aarch64 is answered from the recorded pid of
# the bench's fake process (a real process: /proc/PID/stat and /proc/PID/cmdline exist).
# Every other question goes to the real pgrep.
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
cat > "$B/stubs/ps" << 'EOS'
#!/bin/bash
# BENCH STUB of ps (added 2026-10-05). The steps script's keepalive_check ('open', 'row',
# 'close') looks for the keepalive client of wsl.exe: an 'exec sleep <seconds>' whose
# parent is a WSL relay. On 2026-10-05 no such client ran on the host (the one the first
# pass of this bench found had ended), and the bench neither starts nor ends one. So, for
# that one question ('ps -eo pid=,ppid=,args='), a SYNTHETIC client is ADDED to the real
# listing - pid 4194301, parent 4194300, 'sleep 43200' - and its two follow-up reads are
# answered here: its elapsed time (counted from the bench's setup, plus 60 s) and its
# parent's name ('Relay(bench)'). No process is started, and nothing outside the bench
# (its PATH) sees the line. If a process with either pid exists, nothing is added and the
# real ps answers. Every other call is the real ps, unchanged.
K=4194301; KP=4194300
case "$*" in
    "-eo pid=,ppid=,args=")
        /usr/bin/ps "$@"; rc=$?
        [ -e "/proc/$K" ] || [ -e "/proc/$KP" ] || echo "$K $KP sleep 43200"
        exit "$rc" ;;
    "-o etimes= -p $K")
        [ ! -e "/proc/$K" ] || exec /usr/bin/ps "$@"
        now=$(cut -d. -f1 /proc/uptime)
        echo "$((now - $(cat "$BENCH/keepalive.up0" 2> /dev/null || echo "$now") + 60))" ;;
    "-o comm= -p $KP")
        [ ! -e "/proc/$KP" ] || exec /usr/bin/ps "$@"
        echo "Relay(bench)" ;;
    *) exec /usr/bin/ps "$@" ;;
esac
EOS
cut -d. -f1 /proc/uptime > "$B/keepalive.up0"
cat > "$B/stubs/fake_qemu_start.sh" << 'EOS'
#!/bin/bash
# BENCH: starts the fake qemu-system-aarch64 process (a bash loop in a session of its own)
# whose argv carries two -drive file= entries and whatever extra arguments are given, and
# records its pid (qemu.pid: the current one; qemu.pids.all: every one ever started).
B=${BENCH:?}
setsid bash -c 'while :; do /usr/bin/sleep 5; done' qemu-system-aarch64 -machine virt \
    -drive "id=disk0,file=$B/rootfs.ext4,if=none,format=raw" -device virtio-blk-pci,drive=disk0 \
    -drive "id=disk1,file=$B/data.img,if=none,format=raw" -device virtio-blk-pci,drive=disk1 "$@" \
    > /dev/null 2>&1 < /dev/null &
echo $! > "$B/qemu.pid"
echo $! >> "$B/qemu.pids.all"
EOS
cat > "$B/stubs/openssl" << 'EOS'
#!/bin/bash
# BENCH STUB of openssl (test 9(a) writes a throw-away key and certificate at fixed paths
# under /tmp, outside the bench): the call is logged and NOTHING is written. With
# $EGW_STUB_STATE/bench_openssl_stop it prints a line starting with STOP: on stdout - the
# real line (a) holds no helper call that can print one - so that the steps script's rule
# for a STOP: in (a) can be exercised.
echo "openssl $*" >> "$BENCH/openssl.log"
[ ! -e "$EGW_STUB_STATE/bench_openssl_stop" ] || echo "STOP: bench: a line starting with STOP: in the console of (a) (printed by the stub openssl)"
exit 0
EOS
cat > "$B/stubs/ssh" << 'EOS'
#!/bin/bash
# BENCH WRAPPER of ssh: there is no guest. The runbook's own lines are answered by the
# test module's STUB_SSH (mod/stubs/ssh), to which every call not named below is handed
# unchanged. Named below, and answered here from canned text, are the guest reads of the
# STEPS SCRIPT itself and of the stub drivers (the module's stub does not know them): the
# open's listing of the event directories, the gate's guest state, the healthy wait, the
# unit listing, the close's stop, the previous boot's journal, and test 9's probe and its
# two exposure reads. They answer only while the stub guest is up: after the reboot
# command they are refused (255) when the case says the guest never answers, when it died
# (guest_dies_after_calls reached) or when the bench flag guest.down exists.
# A bench hook: $BENCH/hooks/reboot.sh runs (detached) when the reboot command is seen.
S=$EGW_STUB_STATE
cmd="${@: -1}"
ctl=0; root=0
for a in "$@"; do
    case $a in -O | -M) ctl=1 ;; root@*) root=1 ;; esac
done
[ "$ctl" -eq 0 ] || exec "$BENCH/mod/stubs/ssh" "$@"
logit() { { printf 'ssh'; for a in "$@"; do printf ' [%s]' "$a"; done; echo; } >> "$S/ssh.log"; }
up() {
    [ ! -e "$BENCH/guest.down" ] || return 1
    [ -e "$S/rebooted_at" ] || return 0
    [ ! -e "$S/guest_never_answers" ] || return 1
    if [ -s "$S/guest_dies_after_calls" ] && [ "$(cat "$S/after_reboot.calls" 2> /dev/null || echo 0)" -ge "$(cat "$S/guest_dies_after_calls")" ]; then return 1; fi
    return 0
}
refused() { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
names="mosquitto mongodb ditto-policies ditto-things ditto-gateway controller"
if [ "$root" -eq 1 ]; then      # test 9, exposure (1): root over ssh is refused by the guest
    logit "$@"; up || refused
    echo "root@127.0.0.1: Permission denied (publickey)." >&2; exit 255
fi
case $cmd in
    "ls -1 /opt/egw/deployment/data/events")
        logit "$@"; up || refused
        cat "$S/events.pre"; cat "$BENCH/guest.events.extra" 2> /dev/null; exit 0 ;;
    *State.OOMKilled*)
        logit "$@"; up || refused
        if [ -e "$S/rebooted_at" ]; then st=2026-10-05T10:30:00.000000001Z; else st=2026-10-05T10:00:00.000000001Z; fi
        for s in $names; do echo "egw-$s-1 Up 5 minutes (healthy)"; done
        for s in $names; do
            echo "container egw-$s-1 oomkilled=false restarts=0 id=$(printf '%s' "$s" | /usr/bin/sha256sum | cut -d' ' -f1) started=$st"
        done
        echo "memory-cgroup OOM lines: 0"; echo "bench: free -m and df -h are not reproduced"; exit 0 ;;
    *"ALL HEALTHY"*)
        logit "$@"; up || refused
        echo "2026-10-05T10:00:00Z sample 1: bench"; echo "2026-10-05T10:00:01Z completed (sample 1)"
        echo "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)"; exit 0 ;;
    *"systemctl list-units"*)
        logit "$@"; up || refused
        echo "no egw-events-* and no egw-resources-* unit is active"; exit 0 ;;
    *"stop -t 130"* | *"stop -t 60"*)
        logit "$@"; up || refused
        echo "bench compose stub: ${cmd#*&& }" | cut -c1-120; echo "stop exit=0"; exit 0 ;;
    "sudo -n journalctl -b -1 --no-pager" | "sudo -n journalctl -b -1 -k --no-pager"*)
        logit "$@"; up || refused
        echo "bench: the previous boot's journal is not reproduced"; exit 0 ;;
    "sh /opt/egw/deployment/scripts/probe-acl.sh "*)
        logit "$@"; up || refused
        rc=$(cat "$S/bench_probe_rc" 2> /dev/null || echo 0)
        echo "bench probe-acl stub: tag ${cmd##* } verdict=$([ "$rc" = 0 ] && echo PASS || echo FAIL)"; exit "$rc" ;;
    'docker ps --format "{{.Names}} {{.Ports}}"')
        logit "$@"; up || refused
        echo "egw-controller-1 127.0.0.1:8000->8000/tcp"; echo "egw-ditto-gateway-1 127.0.0.1:8080->8080/tcp"
        echo "egw-mosquitto-1 0.0.0.0:8883->8883/tcp"; echo "egw-mongodb-1 "; exit 0 ;;
    *"sudo systemctl reboot"*)
        [ ! -x "$BENCH/hooks/reboot.sh" ] || setsid "$BENCH/hooks/reboot.sh" > /dev/null 2>&1 < /dev/null &
        ;;
esac
exec "$BENCH/mod/stubs/ssh" "$@"
EOS
cat > "$B/stubs/scp" << 'EOS'
#!/bin/bash
# BENCH WRAPPER of scp: test 9 (d)+(e) copies the probe's evidence directory from the
# guest ('scp -r egw-tcg:/opt/egw/evidence/itest-acl-<stamp> <dir>/'), which the test
# module's STUB_SCP does not know: it is made here, with the five files the line reads.
# Every other call is handed to the module's stub unchanged.
src=""; dest="${@: -1}"
for a in "$@"; do case $a in egw-tcg:/opt/egw/evidence/itest-acl-*) src=$a ;; esac; done
if [ -n "$src" ]; then
    echo "scp $*" >> "$EGW_STUB_STATE/calls.log"
    [ ! -e "$EGW_STUB_STATE/bench_scp_acl_fails" ] || { echo "scp: bench: the copy failed" >&2; exit 1; }
    d=${dest%/}/${src##*/}
    mkdir -p "$d" || exit 1
    echo "verdict=PASS (bench)" > "$d/verdict.txt"; echo "bench ctl-sub" > "$d/ctl-sub.out"
    : > "$d/sim-sub.out"; : > "$d/anon.out"; echo "bench broker lines" > "$d/broker.txt"
    exit 0
fi
exec "$BENCH/mod/stubs/scp" "$@"
EOS
chmod +x "$B"/stubs/* "$B"/venv/bin/python "$B"/venv/bin/python3

# --- stub session drivers, in the COPY only ----------------------------------------------
D=$B/repo/tools/session
cat > "$D/guest_session_open.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of guest_session_open.sh: no QEMU, no guest (a fake process stands for QEMU;
# $BENCH/qemu.extra holds extra arguments for its command line, one per line).
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -z "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "a session is already open: $SESSION"
S=$(new_attempt "guest session" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
SESSION=$S
echo "$S" > "$EXEC/current_session"
mkdir -p "$S/scripts" "$S/boot" "$S/guest" "$S/host"
cp "$DRIVERS/guest/session_common.sh" "$S/scripts/"
echo s1 > "$S/.current_run"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/boot/s1.started"
extra=()
[ ! -s "$BENCH/qemu.extra" ] || mapfile -t extra < "$BENCH/qemu.extra"
bash "$BENCH/stubs/fake_qemu_start.sh" "${extra[@]}"
(cd "$REPO/src" && $LE set --attempt "$S" "identities=$(repo_identity)" "pid=4242")
ex "$S" boot bash -c 'echo "bench stub boot"'
echo "session open: $S (bench stub)"
driver_exit_open "$S"
EOS
cat > "$D/preflight.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of preflight.sh (the frozen driver's stack start is not run in the bench).
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "live preflight" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
ex "$A" stack-start-interlock bash -c 'echo "bench stub: the prescribed stack start of the frozen preflight is NOT run in the bench"'
printf '{"role": "sut", "captured_utc": "2026-10-05T00:00:00Z", "node": "bench", "provider": "QEMU 8.2.7 TCG (bench stub)", "region": "local-workstation", "instance_type": "qemu -machine virt; ARM64 EMULATED", "shared_vcpu_note": "bench"}\n' > "$A/environment/sut_environment.json"
(cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass --reason "bench stub preflight" --next-action "none")
driver_exit "$A"
EOS
cat > "$D/gate_health.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of gate_health.sh: the real healthy wait against the stub guest, one hx step
# (its preamble opens the tunnel, as the frozen driver's first hx step does), and a record
# of the running images in the frozen driver's place and form
# (environment/container_identities.txt).
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "G2 gate preconditions" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
healthy_wait "$A" services-healthy 30 1
hx "$A" controller-endpoints 'tunnel_check && echo "bench: the tunnel is up"'
cp "$BENCH/gate.identities" "$A/environment/container_identities.txt"
(cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass --reason "bench stub gate" --next-action "none")
driver_exit "$A"
EOS
cat > "$D/guest_session_close.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of guest_session_close.sh. The fake process that stands for QEMU is the
# bench's own and is ended here, as the power-off ends the real one.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
S=$SESSION
[ -n "$S" ] && [ -d "$S" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
gx "$S" stack-stop "cd /opt/egw/deployment && $DC stop -t 60; echo \"stop exit=\$?\""
pid=$(cat "$BENCH/qemu.pid" 2> /dev/null)
[ -z "$pid" ] || kill -- "-$pid" 2> /dev/null
rm -f "$BENCH/qemu.pid"
ex "$S" artefacts-after-poweroff bash -c 'sha256sum "$1"; echo "no qemu process left"' _ "$ROOTFS_EXT4"
rm -f "$EXEC/current_session"
(cd "$REPO/src" && $LE finish --attempt "$S" --status finished --validity not-applicable --outcome pass --reason "bench stub close" --next-action "none")
driver_exit "$S"
EOS
echo "bench ready: $B"
