#!/bin/bash
# SUPPLEMENT COPY (2026-10-07) of the sealed bench's bs4_setup.sh, made by make_bsupp_setup.py: the paths and
# the plan's source changed, nothing else.
# Bench of the S4 operator script (test 6 only), stream BENCH of the S4 preparation
# (2026-10-05). Adapted from S3b's bench/bs3b_setup.sh: what changed is marked 'S4'. One
# isolated bench for <P>/g3_battery.sh (session S4) on the REAL step file <P>/rows/t6.sh.
# Everything lives under /tmp/g3-s4-bench/<scenario>:
#   repo/     a COPY of /tmp/g3-s4-bench/_src (bs4_src.sh: tools/ and src/ of the read-only
#             worktree <S>/t6m, the merged tree 14f89c4; the runbook blob as the clone's
#             runbook). In the copy only, six files are stubs: the four session drivers
#             (no QEMU, no guest) and - S4 - events_capture.sh and proof_fetch_sut_log.sh,
#             which are the test module's STUB_EVENTS_CAPTURE and STUB_FETCH_SUT_LOG (the
#             Docker events recorder and the bounded SUT reads that harness_cmd and the
#             harness's hooks run from $EGW_CLONE/tools/session);
#   home/     HOME: egw-tcg/itest-helpers.sh and tunnel.sh written by the runbook's own
#             heredocs (sha256 compared with the recorded values), a bench .env, the pilot
#             plan (S4: a COPY of the real plan, read once, with r04 added by the merged
#             plan-supplement: 61d55940..., 96 entries);
#   mod/      the test module's stubs and stub guest state (bs4_stubs.py imports it);
#   stubs/    what the module does not hold: git, sha256sum, pgrep, ps (a synthetic
#             keepalive client), and a wrapper of ssh that answers the steps script's OWN
#             guest reads (the gate, the close, the open's listing) and - S4 - test 6's
#             own restart of the controller, and hands every other call to the module's
#             stub unchanged;
#   venv/     EGW_EXEC_VENV: 'activate' and a 'python' that hands '-m egw_experiments run'
#             and '-m egw_experiments analyze' to the bench's stand-in (harness.py, a copy
#             of bs4_harness.py), '-m egw_experiments.itest_reconcile' and '-m
#             egw_simulator' to the module's STUB_PYTHON, and everything else to the
#             execution venv's real python (read-only, no bytecode written).
# A fake process stands for QEMU (a bash loop with a real /proc/PID/cmdline). No guest, no
# QEMU, no docker, no real ssh. Nothing is written under ~/egw-exec, ~/egw-tcg, ~/yocto or
# output_test; two files are READ: the real plan (copied) and S3's sealed gate record.
# Usage (WSL): bs4_setup.sh /tmp/g3-s4-bench/<scenario>
set -u
B=${1:?usage: bs4_setup.sh /tmp/g3-s4-bench/<scenario>}
case $B in /tmp/g3-s4-bench/_* | /tmp/g3-s4-bench/*/*) echo "refused: the bench must be /tmp/g3-s4-bench/<scenario>"; exit 2 ;; esac
case $B in /tmp/g3-s4-bench/?*) ;; *) echo "refused: the bench must be /tmp/g3-s4-bench/<scenario>"; exit 2 ;; esac
[ ! -e "$B" ] || { echo "refused: $B exists"; exit 2; }
SUPPB=$(cd "$(dirname "$0")" && pwd)      # <S>/g3/t6supp/bench (the supplement)
SCR=$(cd "$SUPPB/../../.." && pwd)        # <S>
PREP=$SCR/g3/t6prep                       # <P>
HERE=$PREP/bench                          # the sealed bench folder: bs4_stubs.py, bs4_harness.py
SRC=/tmp/g3-s4-bench/_src
WT=$SCR/t6m
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
# SUPPLEMENT (2026-10-07): the plan before r04, as the sealed preparation package kept it (read-only).
REAL_PLAN="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation/part1-record/campaign_plan.predecessor.json"
TOOLS=1fd9792bb76f02c6948f33887207dba4837202db
TREE=14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec
DRIVERS_SHA=2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed
ROOTFS=6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4
PLAN_SHA=c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60
PLAN_R04_SHA=61d55940fcccdb942ff508ab6fc920b0fa163837ef7459438d789a1879b1eaac
ADMITTED=20261003T132936Z_g3-qualification-t6_attempt01
GATE3=$OT/runs/2026-10-05/20261005T115022Z_g2-gate-preconditions_attempt07/environment/container_identities.txt
[ -d "$SRC/tools/session" ] && [ ! -w "$SRC" ] || { echo "refused: $SRC is not the read-only source of bs4_src.sh"; exit 2; }

mkdir -p "$B"/home/egw-tcg/pilot/results/raw "$B"/home/.ssh "$B/egw-exec/attempts/$ADMITTED" \
    "$B/out/runs/2026-10-03/$ADMITTED" "$B"/out/incomplete "$B"/stubs "$B"/venv/bin "$B"/hold || exit 1
printf 'bench placeholder of S2s sealed attempt (admitted)\n' > "$B/egw-exec/attempts/$ADMITTED/bench-placeholder.txt"
printf 'bench placeholder of S2s sealed package (admitted)\n' > "$B/out/runs/2026-10-03/$ADMITTED/bench-placeholder.txt"
cp -r "$SRC" "$B/repo" && chmod -R u+w "$B/repo" || exit 1

# The drivers of the copy BEFORE six files are replaced by stubs, hashed the way common.sh's
# repo_identity hashes them. In the bench the sha256sum stub answers the recorded value for
# that stream (or $BENCH/sha.drivers), because six files of the copy are then stubs.
got=$(cd "$B/repo/tools/session" && cat ./*.sh ./*.py ./guest/*.sh | /usr/bin/sha256sum | cut -d' ' -f1)
echo "drivers of the copy before the stubs: $got ($([ "$got" = "$DRIVERS_SHA" ] && echo 'the recorded drivers_sha256' || echo "NOT the recorded $DRIVERS_SHA"))"
[ "$got" = "$DRIVERS_SHA" ] || exit 1
echo "collector of the copy: $(/usr/bin/sha256sum < "$B/repo/src/deployment/scripts/collect-resources.sh" | cut -d' ' -f1)"

# --- the module's stubs and state; the helper file and tunnel.sh from the runbook ----------
PYTHONDONTWRITEBYTECODE=1 "$REAL_PY" "$HERE/bs4_stubs.py" "$WT" "$SRC" "$B" || { echo "bs4_stubs.py failed"; exit 1; }
# The default PATH of a bench uses the host's own sleep and timeout (the helper's 130 s
# quiet window is timed on /proc/uptime in any case); mod/stubs-realtime is the module's
# stubs without its sleep and timeout.
mkdir "$B/mod/stubs-realtime" || exit 1
for f in "$B"/mod/stubs/*; do
    case ${f##*/} in sleep | timeout) ;; *) ln -s "$f" "$B/mod/stubs-realtime/${f##*/}" ;; esac
done
# S4: the recorder and the bounded reads of the checkout are the module's stubs (copy only).
cp "$B/mod/clone/tools/session/events_capture.sh" "$B/repo/tools/session/events_capture.sh" || exit 1
cp "$B/mod/clone/tools/session/proof_fetch_sut_log.sh" "$B/repo/tools/session/proof_fetch_sut_log.sh" || exit 1
cp "$HERE/bs4_harness.py" "$B/harness.py" || exit 1

printf 'bench placeholder for ca.crt (its recorded sha256 is answered by the sha256sum stub)\n' > "$B/home/egw-tcg/ca.crt"
printf 'MOSQUITTO_SIMULATOR_PASSWORD=bench-value-0000\n' > "$B/home/egw-tcg/.env"
printf '{"role": "sut", "provider": "", "region": "", "instance_type": "", "shared_vcpu_note": ""}\n' > "$B/home/egw-tcg/sut_environment.json"
printf 'bench data disk\n' > "$B/data.img"
printf 'bench rootfs disk (the fake process names it)\n' > "$B/rootfs.ext4"
# S4: the gate's record is S3's sealed one (read-only), as the gate driver wrote it at S3's open.
cp "$GATE3" "$B/gate.identities" || exit 1
echo "gate record: S3's sealed container_identities.txt, sha256 $(/usr/bin/sha256sum < "$B/gate.identities" | cut -d' ' -f1)"

# S4: the pilot plan - a copy of the real one (read once), then r04 added by the merged code.
cp "$REAL_PLAN" "$B/plan.c195.json" || exit 1
got=$(/usr/bin/sha256sum < "$B/plan.c195.json" | cut -d' ' -f1)
echo "real plan copied: sha256 $got ($([ "$got" = "$PLAN_SHA" ] && echo 'the value of the brief' || echo "NOT $PLAN_SHA"))"
[ "$got" = "$PLAN_SHA" ] || exit 1
cp "$B/plan.c195.json" "$B/home/egw-tcg/pilot/campaign_plan.json" || exit 1
(cd "$B/repo/src" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$B/repo/src" "$REAL_PY" -m egw_experiments plan-supplement \
    --plan "$B/home/egw-tcg/pilot/campaign_plan.json" --entry g3-t6) > "$B/plan-supplement.txt" 2>&1 || { echo "plan-supplement failed:"; cat "$B/plan-supplement.txt"; exit 1; }
got=$(/usr/bin/sha256sum < "$B/home/egw-tcg/pilot/campaign_plan.json" | cut -d' ' -f1)
echo "bench plan after plan-supplement --entry g3-t6 (merged code): sha256 $got ($([ "$got" = "$PLAN_R04_SHA" ] && echo 'the value of the brief, 61d55940...' || echo "NOT $PLAN_R04_SHA")), $("$REAL_PY" -c 'import json,sys; p=json.load(open(sys.argv[1])); r=p["runs"][-1]; print(len(p["runs"]), "entries; the last:", r["run_id"], r["status"], r["seed"])' "$B/home/egw-tcg/pilot/campaign_plan.json")"
[ "$got" = "$PLAN_R04_SHA" ] || exit 1
cp "$B/home/egw-tcg/pilot/campaign_plan.json" "$B/plan.r04.json" || exit 1

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
# bench's 'python' first, as the real venv's activate does. S4: no device of S3b's bench
# (its read-only DRAIN_* would make line 1425's prefix assignments fail): the helper's
# 'drained' runs its real 130 s quiet window.
VIRTUAL_ENV=$BENCH/venv
export VIRTUAL_ENV
PATH=$VIRTUAL_ENV/bin:$PATH
export PATH
EOS
cat > "$B/venv/bin/python" << 'EOS'
#!/bin/bash
# BENCH: the venv's python. S4: the harness ('-m egw_experiments run') and analyze ('-m
# egw_experiments analyze') are the bench's stand-in ($BENCH/harness.py); 'plan-supplement'
# is never called by the row (logged and refused, 99); $REC (egw_experiments.itest_reconcile)
# and the simulator are the test module's STUB_PYTHON; everything else - the steps script's
# own $PY, the export tool, driver_status.py, guest_state_delta.py - is the execution venv's
# real python, with the bench's copy of the merged src first on PYTHONPATH.
if [ "${1:-}" = -m ]; then
    case ${2:-} in
        egw_experiments)
            case ${3:-} in
                run | analyze) exec /home/ruisth/egw-exec/venv/bin/python "$BENCH/harness.py" "$@" ;;
                plan-supplement)
                    echo "BENCH: python -m egw_experiments plan-supplement was called ($*)" >> "$EGW_STUB_STATE/calls.log"
                    echo "BENCH: plan-supplement is never called by the row: refused" >&2
                    exit 99 ;;
            esac ;;
        egw_experiments.itest_reconcile | egw_simulator) exec "$BENCH/mod/stubs/python" "$@" ;;
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
            *"rev-parse HEAD"*) cat "\$BENCH/git.head" 2> /dev/null || echo $TOOLS ;;
            *"status --porcelain"*) [ ! -e "\$BENCH/git.dirty" ] || echo " M bench" ;;
            *) echo "bench git stub: not answered: \$*" >&2; exit 1 ;;
        esac ;;
esac
EOS
cat > "$B/stubs/sha256sum" << EOS
#!/bin/bash
# BENCH STUB: the fake build artefacts and the placeholder ca.crt answer the recorded
# values (S4: the root file system answers 6fce1688..., the value the close of S3's second
# opening recorded, or the content of \$BENCH/sha.rootfs); a stream on stdin answers the
# recorded drivers_sha256 (or \$BENCH/sha.drivers; six files of the copy are stubs: the
# copy's drivers were hashed for real by bs4_setup.sh before they were replaced); every
# other file is hashed for real (the collector of the copy among them).
files=()
for a in "\$@"; do case \$a in -*) ;; *) files+=("\$a") ;; esac; done
if [ "\${#files[@]}" -eq 0 ]; then cat > /dev/null; echo "\$(cat "\$BENCH/sha.drivers" 2> /dev/null || echo $DRIVERS_SHA)  -"; exit 0; fi
rc=0
for f in "\${files[@]}"; do
    case \$f in
        */Image-qemuarm64.bin) echo "4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037  \$f" ;;
        *.qemuboot.conf) echo "7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4  \$f" ;;
        */qemu-system-aarch64) echo "5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061  \$f" ;;
        *.rootfs-*.ext4) echo "\$(cat "\$BENCH/sha.rootfs" 2> /dev/null || echo $ROOTFS)  \$f" ;;
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
# BENCH STUB of ps (S3b's, unchanged). The steps script's keepalive_check looks for the
# keepalive client of wsl.exe: an 'exec sleep <seconds>' whose parent is a WSL relay. For
# that one question ('ps -eo pid=,ppid=,args=') a SYNTHETIC client is ADDED to the real
# listing - pid 4194301, parent 4194300, 'sleep 43200' - and its two follow-up reads are
# answered here. No process is started. If a process with either pid exists, nothing is
# added and the real ps answers. Every other call is the real ps, unchanged.
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
# whose argv carries two -drive file= entries, and records its pid (qemu.pid: the current
# one; qemu.pids.all: every one ever started).
B=${BENCH:?}
setsid bash -c 'while :; do /usr/bin/sleep 5; done' qemu-system-aarch64 -machine virt \
    -drive "id=disk0,file=$B/rootfs.ext4,if=none,format=raw" -device virtio-blk-pci,drive=disk0 \
    -drive "id=disk1,file=$B/data.img,if=none,format=raw" -device virtio-blk-pci,drive=disk1 \
    > /dev/null 2>&1 < /dev/null &
echo $! > "$B/qemu.pid"
echo $! >> "$B/qemu.pids.all"
EOS
cat > "$B/stubs/ssh" << 'EOS'
#!/bin/bash
# BENCH WRAPPER of ssh: there is no guest. The runbook's own lines are answered by the
# test module's STUB_SSH (mod/stubs/ssh: the tunnel's control-socket operations, the guest
# clock, config_identity's capture), to which every call not named below is handed
# unchanged. Named below, and answered here from canned text, are the guest reads of the
# STEPS SCRIPT itself and of the stub drivers (the module's stub does not know them): the
# open's listing of the event directories, the gate's guest state, the healthy wait, the
# unit listing (S4: a recorder unit the module's STUB_EVENTS_CAPTURE left 'active' is
# listed as active, exit 3), the close's stop; and - S4 - test 6's own controller restart
# (the harness's --restart-cmd): recorded, after which the guest state shows the
# controller's same container with a later start instant. They answer only while the bench
# flag guest.down does not exist.
S=$EGW_STUB_STATE
cmd="${@: -1}"
ctl=0
for a in "$@"; do
    case $a in -O | -M) ctl=1 ;; esac
done
[ "$ctl" -eq 0 ] || exec "$BENCH/mod/stubs/ssh" "$@"
logit() { { printf 'ssh'; for a in "$@"; do printf ' [%s]' "$a"; done; echo; } >> "$S/ssh.log"; }
up() { [ ! -e "$BENCH/guest.down" ]; }
refused() { echo "ssh: connect to host 127.0.0.1 port 2222: Connection refused" >&2; exit 255; }
names="mosquitto mongodb ditto-policies ditto-things ditto-gateway controller"
case $cmd in
    "ls -1 /opt/egw/deployment/data/events")
        logit "$@"; up || refused
        printf '%s\n' controller_restart-r01 controller_restart-r02 controller_restart-r03 itest-post-reboot-01-q2 nominal-r01 nominal-r02
        cat "$BENCH/guest.events.extra" 2> /dev/null; exit 0 ;;
    *State.OOMKilled*)
        logit "$@"; up || refused
        for s in $names; do echo "egw-$s-1 Up 5 minutes (healthy)"; done
        for s in $names; do
            st=2026-10-05T20:00:00.000000001Z
            [ "$s" != controller ] || [ ! -s "$S/controller.restarted" ] || st=2026-10-05T20:05:06.300000001Z
            echo "container egw-$s-1 oomkilled=false restarts=0 id=$(printf '%s' "$s" | /usr/bin/sha256sum | cut -d' ' -f1) started=$st"
        done
        echo "memory-cgroup OOM lines: 0"; echo "bench: free -m and df -h are not reproduced"; exit 0 ;;
    *"ALL HEALTHY"*)
        logit "$@"; up || refused
        echo "2026-10-05T20:00:00Z sample 1: bench"; echo "2026-10-05T20:00:01Z completed (sample 1)"
        echo "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)"; exit 0 ;;
    *"systemctl list-units"*)
        logit "$@"; up || refused
        act=""
        for f in "$S"/unit-*; do [ -f "$f" ] && [ "$(cat "$f")" = active ] && act="$act ${f##*/unit-}"; done
        if [ -n "$act" ]; then
            for u in $act; do echo "egw-events-$u.service loaded active running bench recorder unit"; done
            echo 'ACTIVE UNIT: a recorder (egw-events-*) or collector (egw-resources-*) unit is still active'; exit 3
        fi
        echo "no egw-events-* and no egw-resources-* unit is active"; exit 0 ;;
    *"stop -t 130"* | *"stop -t 60"*)
        logit "$@"; up || refused
        echo "bench compose stub: ${cmd#*&& }" | cut -c1-120; echo "stop exit=0"; exit 0 ;;
    *"docker compose"*" restart controller")
        logit "$@"; up || refused
        date -u +%Y-%m-%dT%H:%M:%SZ >> "$S/controller.restarted"
        echo "bench: the stub guest records the controller's restart (test 6's own fault)"; exit 0 ;;
esac
exec "$BENCH/mod/stubs/ssh" "$@"
EOS
chmod +x "$B"/stubs/* "$B"/venv/bin/python "$B"/venv/bin/python3

# --- stub session drivers, in the COPY only ----------------------------------------------
D=$B/repo/tools/session
cat > "$D/guest_session_open.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of guest_session_open.sh: no QEMU, no guest (a fake process stands for QEMU).
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
bash "$BENCH/stubs/fake_qemu_start.sh"
(cd "$REPO/src" && $LE set --attempt "$S" "identities=$(repo_identity)" "pid=4242")
ex "$S" boot bash -c 'echo "bench stub boot"'
echo "session open: $S (bench stub)"
driver_exit_open "$S"
EOS
cat > "$D/preflight.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of preflight.sh (the frozen driver's stack start, collector install and
# collector-duration judgement are not run in the bench). S4: $BENCH/preflight.mode says how
# its attempt ends: 'pass' (default; valid pass, exit 0), 'fail' (a valid negative result:
# collector-duration ended 1 and the attempt is finished valid/fail, which the frozen
# driver_status derives as 1) or 'invalid' (finished failed/invalid, derived as 3).
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "live preflight" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
ex "$A" stack-start-interlock bash -c 'echo "bench stub: the prescribed stack start of the frozen preflight is NOT run in the bench"'
printf '{"role": "sut", "captured_utc": "2026-10-05T00:00:00Z", "node": "bench", "provider": "QEMU 8.2.7 TCG (bench stub)", "region": "local-workstation", "instance_type": "qemu -machine virt; ARM64 EMULATED", "shared_vcpu_note": "bench"}\n' > "$A/environment/sut_environment.json"
case $(cat "$BENCH/preflight.mode" 2> /dev/null || echo pass) in
    fail)
        ex "$A" collector-duration bash -c 'echo "bench stub: collector-duration: the uptime bounds do not cover the declared 45 s"; exit 1'
        (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome fail --reason "bench stub preflight: collector-duration failed (valid negative)" --next-action "none") ;;
    invalid)
        ex "$A" collector-duration bash -c 'echo "bench stub: collector-duration: the record could not be read"; exit 1'
        (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome unknown --reason "bench stub preflight: a mandatory step failed" --next-action "none") ;;
    *)
        (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass --reason "bench stub preflight" --next-action "none") ;;
esac
driver_exit "$A"
EOS
cat > "$D/gate_health.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of gate_health.sh: the real healthy wait against the stub guest, one hx step
# (its preamble opens the tunnel, as the frozen driver's first hx step does), and a record
# of the running images in the frozen driver's place and form
# (environment/container_identities.txt: S4, S3's sealed record, or a changed copy).
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
