#!/bin/bash
# Bench of the S4 operator script (stream OPERATOR of the S4 preparation, 2026-10-05).
# One scenario per call, in a bench of its own, /tmp/g3-s4-op/<scenario>: HOME and every
# EGW_* point inside the bench, the bench's stubs are first on PATH, and the execution
# venv's python is used read-only (no bytecode is written). No guest, no QEMU, no docker,
# no real ssh: a fake process stands for QEMU, a stub ssh answers the guest reads, and four
# stub session drivers stand in for the frozen ones in a COPY of the merged tree.
# The bench's row file t6.sh is NOT the runbook's block (that needs the guest, the broker
# and the harness): it writes on the bench host what the block leaves there, at the paths
# the steps script registers (the run directory, the configuration identity, the twin
# siblings, the .sut directory, the plan entry rewritten as run.py does, processed/), and it
# issues test 6's own controller restart through ssh, as the harness's --restart-cmd does.
# Read-only inputs: the merged tree 1fd9792 extracted from git into /tmp/g3-s4-op-src
# (tools/, src/egw_experiments/, the collector, the runbook) and S3's sealed gate record in
# output_test. The script under test is run in place, with its own default state directory
# (<bench>/egw-exec/g3-t6-s4). The output masks the bench and the scratchpad paths.
# Usage (WSL): bs4_op.sh <scenario>
#   labels      open S1|S2|S3|S5|<none>, row t8|t9|t1-harness, classify t8, term t9 and no
#               subcommand: each refused (exit 2) and nothing created
#   pass        open S4, row t6, classify t6 (valid/pass), close
#   preflight3  the stub preflight ends 3: HALT at open, no exception examined, no
#               environment copy, no gate; row t6 refused; close
#   collector   the clone's collector changed: HALT at open, nothing started
#   rootfs      the root file system not at 6fce1688...: HALT at open, nothing started
#   fresh       open S4 halts on each of: another t6 attempt; the admitted attempt in
#               another place; r04 not 'planned'; <P>/<r04>.sut; the raw directory; then,
#               all restored, open passes (the control) and the session is closed
#   suffix      the admitted attempt absent from both places: open passes, row t6 halts
#               before any step (the new attempt is attempt01); classify not started; close
#   gate        the gate record differs from S2's in one image id: row t6 halts before the
#               attempt is created; close
set -u
SC=${1:?usage: bs4_op.sh labels|pass|preflight3|collector|rootfs|fresh|suffix|gate}
case $SC in labels | pass | preflight3 | collector | rootfs | fresh | suffix | gate) ;; *) echo "usage: bs4_op.sh labels|pass|preflight3|collector|rootfs|fresh|suffix|gate"; exit 2 ;; esac
HERE=$(cd "$(dirname "$0")" && pwd)
PREP=$(cd "$HERE/.." && pwd)                  # the preparation folder (this file is <P>/operator-record/bs4_op.sh)
SCR=$(cd "$PREP/../.." && pwd)                # the scratchpad
SRC=/tmp/g3-s4-op-src
ROOT=/tmp/g3-s4-op
B=$ROOT/$SC
G=$PREP/g3_battery.sh
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
GATE3=$OT/runs/2026-10-05/20261005T115022Z_g2-gate-preconditions_attempt07/environment/container_identities.txt
TOOLS=1fd9792bb76f02c6948f33887207dba4837202db
TREE=14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec
DRIVERS_SHA=2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed
COLLECTOR_SHA=9e678b024bde66bacc65fea936d05ca226a82e73c86d1cc23a9cf9f8fe8d9b97
ROOTFS=6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4
ADMITTED=20261003T132936Z_g3-qualification-t6_attempt01
RID=controller_restart-r04
AUTH='G3 qualification, session S4: test 6 only (controller_restart-r04; request of 2026-10-05, output_test/decisions/2026-10-05_g3-t6-session-request.md; criterion amended on 2026-10-05, LOG #C052; transition rule 1a-option-a-2026-10-05, LOG #C053)'
BASE_PATH=$PATH
CHECKS=0
FAILS=0
RC=0

[ ! -e "$B" ] || { echo "refused: the bench of $SC exists"; exit 2; }
[ -d "$SRC/tools/session" ] && [ -f "$SRC/docs/setup/qemu_integrated_gateway.md" ] \
    || { echo "refused: $SRC is not the extracted merged tree"; exit 2; }
mkdir -p "$B" || exit 1
# Everything printed from here on is masked: the bench and the scratchpad are shown by name.
exec > >(sed -u "s#$B#<bench>#g; s#$SCR#<S>#g") 2>&1
MASK_PID=$!

say() { echo; echo "=== $*"; }
ok() { CHECKS=$((CHECKS + 1)); echo "CHECK ok: $*"; }
bad() { CHECKS=$((CHECKS + 1)); FAILS=$((FAILS + 1)); echo "CHECK FAILED: $*"; }
check() {   # check TEXT COMMAND...: ok when the command succeeds
    local text=$1
    shift
    if "$@"; then ok "$text"; else bad "$text"; fi
}
has() { grep -q -- "$1" "$B/last.out"; }
hasE() { grep -Eq -- "$1" "$B/last.out"; }
lacks() { ! grep -qi -- "$1" "$B/last.out"; }
sget() { [ -f "$1" ] && sed -n "s/^$2=//p" "$1" | tail -n 1; }
# run SUBCOMMAND...: one subcommand in a session of its own, as the launcher starts it.
run() {
    say "g3_battery.sh $*"
    setsid bash "$G" "$@" < /dev/null > "$B/last.out" 2>&1
    RC=$?
    echo "-> exit $RC"
    grep -E '^(## [0-9]{4}-|HALT|REFUSED|NOT STARTED|GATE|NOTE|Next|STOP|admitted|NOT FRESH|fresh on|plan entry|gate record|collector:|runbook:|rootfs ext4:|expected: |keepalive|session S4|  HALT|  row |    attempt|[a-z_]+\.sh exit=|row t6:|attempt: |usage:|classify|DRIVER RESULT|PROCEEDED|EXCEPTION|rows.manifest|row file|labels:|harness input now)' "$B/last.out" | cut -c1-330
}
want_rc() { if [ "$RC" = "$1" ]; then ok "exit status $RC: $2"; else bad "exit status $RC, expected $1: $2"; fi; }
cleanup() {
    local pid
    pid=$(cat "$B/qemu.pid" 2> /dev/null)
    [ -z "$pid" ] || ! kill -0 "$pid" 2> /dev/null || { kill -- "-$pid" 2> /dev/null; echo "bench: the fake QEMU process left by the scenario was ended"; }
}

# --- the bench ------------------------------------------------------------------------------
setup() {
    local got h t R
    mkdir -p "$B"/home/egw-tcg/pilot/results/raw "$B"/home/.ssh "$B/egw-exec/attempts/$ADMITTED" \
        "$B/out/runs/2026-10-03/$ADMITTED" "$B"/out/incomplete "$B"/stubs "$B"/venv/bin "$B"/rows "$B"/hold || exit 1
    cp -r "$SRC" "$B/repo" || exit 1
    # The drivers of the copy before four of them are replaced by stubs, hashed as
    # common.sh's repo_identity hashes them (C collation of the three globs).
    got=$(cd "$B/repo/tools/session" && LC_ALL=C && cat ./*.sh ./*.py ./guest/*.sh | /usr/bin/sha256sum | cut -d' ' -f1)
    echo "drivers of the copy before the stubs: $got"
    [ "$got" = "$DRIVERS_SHA" ] || { echo "the copy's drivers are not $DRIVERS_SHA"; exit 1; }
    # The helper file and tunnel.sh from the runbook's own heredocs (lines 610-1154, 524-561).
    R=$B/repo/docs/setup/qemu_integrated_gateway.md
    sed -n '610,1154p' "$R" > "$B/home/egw-tcg/itest-helpers.sh"
    sed -n '524,561p' "$R" > "$B/home/egw-tcg/tunnel.sh"
    h=$(/usr/bin/sha256sum < "$B/home/egw-tcg/itest-helpers.sh" | cut -c1-64)
    t=$(/usr/bin/sha256sum < "$B/home/egw-tcg/tunnel.sh" | cut -c1-64)
    echo "helpers $h, tunnel.sh $t (from the runbook blob $(/usr/bin/sha256sum < "$R" | cut -c1-12)...)"
    printf 'bench placeholder for ca.crt (its recorded sha256 is answered by the sha256sum stub)\n' > "$B/home/egw-tcg/ca.crt"
    printf 'MOSQUITTO_SIMULATOR_PASSWORD=bench-value-0000\n' > "$B/home/egw-tcg/.env"
    printf '{"role": "sut", "provider": "", "region": "", "instance_type": "", "shared_vcpu_note": ""}\n' > "$B/home/egw-tcg/sut_environment.json"
    printf 'bench data disk\n' > "$B/data.img"
    cat > "$B/home/egw-tcg/pilot/campaign_plan.json" << 'EOS'
{
  "master_seed": 42,
  "runs": [
    {"condition_id": "controller_restart", "duration_s": 600, "run_id": "controller_restart-r03", "seed": 2189910495, "status": "failed", "validity": "invalid", "warmup_s": 0},
    {"condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 96, "rate_msg_s": 11.2, "repetition": 4, "run_id": "controller_restart-r04", "runner": "simulator", "scenario": "nominal", "seed": 1715385812, "status": "planned", "supplement": "g3-t6", "warmup_s": 0}
  ]
}
EOS
    cp "$B/home/egw-tcg/pilot/campaign_plan.json" "$B/plan.orig.json"
    cp "$GATE3" "$B/gate.identities" || exit 1
    local Y=$B/yocto/egw DEPD QD
    DEPD=$Y/src/yocto/build-integrated/tmp/deploy/images/qemuarm64
    QD=$Y/src/yocto/build-integrated/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin
    mkdir -p "$DEPD" "$QD" || exit 1
    printf 'bench kernel\n' > "$DEPD/Image-qemuarm64.bin"
    printf 'bench rootfs\n' > "$DEPD/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4"
    printf 'bench qemuboot\n' > "$DEPD/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf"
    printf 'bench qemu binary\n' > "$QD/qemu-system-aarch64"
    cut -d. -f1 /proc/uptime > "$B/keepalive.up0"

    # The bench venv: 'activate' puts the bench's python first; python is the execution
    # venv's real one (read-only; PYTHONDONTWRITEBYTECODE is set by the environment).
    cat > "$B/venv/bin/activate" << 'EOS'
# BENCH venv (sourced by the host preamble of runbook 6.1 in every step shell).
VIRTUAL_ENV=$BENCH/venv
export VIRTUAL_ENV
PATH=$VIRTUAL_ENV/bin:$PATH
export PATH
EOS
    printf '#!/bin/bash\nexec /home/ruisth/egw-exec/venv/bin/python "$@"\n' > "$B/venv/bin/python"
    printf '#!/bin/bash\nexec /home/ruisth/egw-exec/venv/bin/python "$@"\n' > "$B/venv/bin/python3"

    # --- stubs, first on PATH ------------------------------------------------------------------
    cat > "$B/stubs/git" << EOS
#!/bin/bash
# BENCH STUB: neither tree of the bench is a git checkout; the identity reads answer the
# recorded values.
dir=""
[ "\$1" != -C ] || dir=\$2
case "\$dir" in
    */yocto/egw)
        case "\$*" in
            *"rev-parse HEAD"*) echo 489bc9e5b5b0660026ea2630b8d1d124049ba2ce ;;
            *"status --porcelain"*) ;;
            *) echo "bench git stub: not answered: \$*" >&2; exit 1 ;;
        esac ;;
    *)
        case "\$*" in
            *"rev-parse HEAD^{tree}"*) echo $TREE ;;
            *"rev-parse HEAD"*) echo $TOOLS ;;
            *"status --porcelain"*) ;;
            *) echo "bench git stub: not answered: \$*" >&2; exit 1 ;;
        esac ;;
esac
EOS
    cat > "$B/stubs/sha256sum" << EOS
#!/bin/bash
# BENCH STUB: the fake build artefacts and the placeholder ca.crt answer the recorded values
# (the root file system: the content of \$BENCH/sha.rootfs when it exists); a stream on stdin
# answers the recorded drivers_sha256 (four session drivers of the copy are stubs: the copy's
# drivers were hashed for real before they were replaced); every other file is hashed for real.
files=()
for a in "\$@"; do case \$a in -*) ;; *) files+=("\$a") ;; esac; done
if [ "\${#files[@]}" -eq 0 ]; then cat > /dev/null; echo "$DRIVERS_SHA  -"; exit 0; fi
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
# BENCH STUB: the question about qemu-system-aarch64 is answered from the bench's fake
# process (a real process); every other question goes to the real pgrep.
case "$*" in
    *qemu-system-aarch64*)
        pid=$(cat "$BENCH/qemu.pid" 2> /dev/null)
        [ -n "$pid" ] && [ -d "/proc/$pid" ] || exit 1
        case "$1" in
            -a*) echo "$pid qemu-system-aarch64 (bench fake process)" ;;
            *) echo "$pid" ;;
        esac
        exit 0 ;;
esac
exec /usr/bin/pgrep "$@"
EOS
    cat > "$B/stubs/ps" << 'EOS'
#!/bin/bash
# BENCH STUB of ps: for the keepalive question ('ps -eo pid=,ppid=,args=') a SYNTHETIC
# client is added to the real listing (pid 4194301, parent 4194300, 'sleep 43200'), and its
# two follow-up reads are answered here; no process is started. Every other call is the
# real ps. If a process with either pid exists, nothing is added.
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
    cat > "$B/stubs/ssh" << 'EOS'
#!/bin/bash
# BENCH STUB of ssh: there is no guest and no tunnel. Every call is logged ($BENCH/ssh.log).
# 'ssh -S <socket> -O check egw-tcg' (tunnel_check) answers 0. The guest reads of the steps
# script and of the stub drivers are answered from canned text; the test's own restart
# ('docker compose ... restart controller' through 'ssh egw-tcg', as the harness's
# --restart-cmd issues it) is recorded, and the controller's start instant is later after
# it. Anything else is refused (exit 1) and named on stderr.
{ printf 'ssh'; for a in "$@"; do printf ' [%s]' "$a"; done; echo; } >> "$BENCH/ssh.log"
cmd="${*: -1}"
case " $* " in
    *" -O check "*) exit 0 ;;
    *" -O "* | *" -M "*) echo "bench ssh stub: only the tunnel check is answered" >&2; exit 255 ;;
esac
names="mosquitto mongodb ditto-policies ditto-things ditto-gateway controller"
case $cmd in
    "ls -1 /opt/egw/deployment/data/events")
        printf '%s\n' controller_restart-r01 controller_restart-r02 controller_restart-r03 itest-post-reboot-01-q2 nominal-r02
        exit 0 ;;
    *State.OOMKilled*)
        for s in $names; do echo "egw-$s-1 Up 5 minutes (healthy)"; done
        for s in $names; do
            st=2026-10-05T20:00:00.000000001Z
            [ "$s" != controller ] || [ ! -e "$BENCH/guest.controller-restarted" ] || st=2026-10-05T20:05:00.000000001Z
            echo "container egw-$s-1 oomkilled=false restarts=0 id=$(printf '%s' "$s" | /usr/bin/sha256sum | cut -d' ' -f1) started=$st"
        done
        echo "memory-cgroup OOM lines: 0"
        exit 0 ;;
    *"ALL HEALTHY"*)
        echo "2026-10-05T20:00:00Z sample 1: bench"; echo "2026-10-05T20:00:01Z completed (sample 1)"
        echo "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)"
        exit 0 ;;
    *"systemctl list-units"*)
        echo "no egw-events-* and no egw-resources-* unit is active"
        exit 0 ;;
    *"stop -t 130"* | *"stop -t 60"*)
        echo "bench compose stub: stop"; echo "stop exit=0"
        exit 0 ;;
    *"docker compose"*" restart controller")
        touch "$BENCH/guest.controller-restarted"
        echo "bench: the stub guest records the controller's restart"
        exit 0 ;;
esac
echo "bench ssh stub: not answered: $cmd" | cut -c1-200 >&2
exit 1
EOS
    cat > "$B/stubs/fake_qemu_start.sh" << 'EOS'
#!/bin/bash
# BENCH: starts the fake qemu-system-aarch64 process (a bash loop in a session of its own)
# and records its pid.
setsid bash -c 'while :; do /usr/bin/sleep 5; done' qemu-system-aarch64 > /dev/null 2>&1 < /dev/null &
echo $! > "$BENCH/qemu.pid"
EOS
    chmod +x "$B"/stubs/* "$B"/venv/bin/python "$B"/venv/bin/python3

    # --- stub session drivers, in the COPY only ------------------------------------------------
    local D=$B/repo/tools/session
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
# BENCH STUB of preflight.sh (no stack start, no collector). With $BENCH/preflight.exit
# holding 3 its attempt records a failed collector-duration step and is finished invalid,
# as the frozen driver finishes a failed mandatory step; otherwise it is finished valid pass.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "live preflight" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
ex "$A" stack-start-interlock bash -c 'echo "bench stub: the prescribed stack start of the frozen preflight is NOT run in the bench"'
printf '{"role": "sut", "captured_utc": "2026-10-05T00:00:00Z", "node": "bench", "provider": "QEMU 8.2.7 TCG (bench stub)", "region": "local-workstation", "instance_type": "qemu -machine virt; ARM64 EMULATED", "shared_vcpu_note": "bench"}\n' > "$A/environment/sut_environment.json"
if [ "$(cat "$BENCH/preflight.exit" 2> /dev/null || echo 0)" = 3 ]; then
    ex "$A" collector-duration bash -c 'echo "bench stub: the collector did not hold the duration it declares"; exit 1'
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome unknown --reason "bench stub preflight: collector-duration failed" --next-action "none")
else
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass --reason "bench stub preflight" --next-action "none")
fi
driver_exit "$A"
EOS
    cat > "$D/gate_health.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of gate_health.sh: the shared healthy wait against the stub guest, one hx step,
# and the record of the running images in the frozen driver's place and form (S3's sealed
# record, or the bench's changed copy).
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "G2 gate preconditions" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
healthy_wait "$A" services-healthy 30 1
hx "$A" controller-endpoints 'tunnel_check && echo "bench: the tunnel check answers"'
cp "$BENCH/gate.identities" "$A/environment/container_identities.txt"
(cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass --reason "bench stub gate" --next-action "none")
driver_exit "$A"
EOS
    cat > "$D/guest_session_close.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of guest_session_close.sh: the bench's fake QEMU process is ended here, as the
# power-off ends the real one.
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

    # --- the bench's row file and its manifest -------------------------------------------------
    cat > "$B/rows/t6.sh" << 'EOS'
RID=controller_restart-r04; RAW6=~/egw-tcg/pilot/results/raw/$RID; echo "bench t6.sh: NOT the runbook's block - it writes on the bench host what the block leaves there, and issues the test's own restart through the stub ssh"
mkdir -p $RAW6/logs/simulator/$RID $P/$RID.sut && echo '{"drain": {"outcome": "quiet"}}' > $RAW6/manifest.json && echo bench > $RAW6/SHA256SUMS && echo '{"bench": "configuration identity"}' > $P/$RID.config_identity.json && echo '{}' > $P/$RID.twins.before.json && echo '{}' > $P/$RID.twins.after.json && echo bench > $P/$RID.sut/docker-events.log && echo "bench: the run directory, the configuration identity, the twin siblings and the .sut directory written"
ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env restart controller'
python3 -c "import json,sys; f=sys.argv[1]; p=json.load(open(f)); [r.update(status='completed', validity='valid', result_dir='bench') for r in p['runs'] if r.get('run_id')=='controller_restart-r04']; open(f,'w').write(json.dumps(p, indent=2)+'\n')" ~/egw-tcg/pilot/campaign_plan.json && echo "bench: the plan entry r04 rewritten as run.py update_plan_status does"
mkdir -p ~/egw-tcg/pilot/results/processed && printf 'run_id,lost,late_confirmations,double_accepted\ncontroller_restart-r04,0,0,0\n' > ~/egw-tcg/pilot/results/processed/per_run.csv && echo "bench: processed/per_run.csv written as analyze writes it"
EOS
    "$REAL_PY" - "$B/rows" << 'EOS'
import hashlib, json, os, sys
d = sys.argv[1]
data = open(os.path.join(d, "t6.sh"), "rb").read()
doc = {
    "schema": "g3-battery-rows-manifest/1",
    "generated_by": "bs4_op.sh (a bench stand-in, NOT the extraction)",
    "generator_sha256": None,
    "runbook": {"commit": "1fd9792bb76f02c6948f33887207dba4837202db",
                "path": "docs/setup/qemu_integrated_gateway.md",
                "sha256": "317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f",
                "lines": 1624},
    "extraction_rule": None,
    "substitution_rule": None,
    "files": {"t6.sh": {"row": "t6", "session": "S4", "step_order": 1,
                        "sha256_after": hashlib.sha256(data).hexdigest(),
                        "kind": "bench stand-in for runbook lines 1421-1428"}},
    "rows": [{"row": "t6", "session": "S4", "steps": ["t6.sh"], "note": "bench stand-in"}],
}
with open(os.path.join(d, "rows.manifest.json"), "w", newline="\n") as f:
    f.write(json.dumps(doc, indent=2) + "\n")
EOS
    printf 'bench: the row ran to its end on the bench (stand-in row file)\n' > "$B/reason.txt"
    printf 'bench: none\n' > "$B/next.txt"
}

benv() {
    unset CTRL DITTO MQTT_PORT P TUNNEL_SOCK ACCEPT_UNACCOUNTED DEVICES EVENTS_EXPECTED BASH_ENV ENV \
        DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S READY_LIMIT_S EGW_G3_RUI_GO EGW_CLONE EGW_G3_STATE EGW_SCHEMA_DIR
    export BENCH=$B
    export HOME=$B/home
    export EGW_EXEC=$B/egw-exec EGW_ATTEMPTS=$B/egw-exec/attempts EGW_OUTPUT_TEST=$B/out
    export EGW_SECRETS_ENV=$B/home/egw-tcg/.env EGW_EXEC_REPO=$B/repo EGW_EXEC_VENV=$B/venv
    export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$B/repo/src
    export EGW_YOCTO_CHECKOUT=$B/yocto/egw EGW_DATA_DISK=$B/data.img EGW_IMAGES_DIR=$B/images EGW_EVIDENCE_CANDIDATES=$B/ec
    export EGW_G3_ROWS=$B/rows
    export PATH=$B/stubs:$BASE_PATH
    BSTATE=$EGW_EXEC/g3-t6-s4
}

say "bench $SC: script under test $(/usr/bin/sha256sum "$G" | cut -c1-64) (g3_battery.sh of the preparation, run in place)"
setup
benv
trap cleanup EXIT

case $SC in
labels)
    for args in "open S1" "open S2" "open S3" "open S5" "open" "row t8" "row t9" "row t1-harness" "term t9"; do
        # shellcheck disable=SC2086
        run $args
        want_rc 2 "'$args' refused"
    done
    run open S1
    check "open S1: the battery's authority is consumed, S4 only" has "whose authority is consumed: nothing of S1 or S2 is re-run or replaced. This script opens S4 only"
    run open S3
    want_rc 2 "open S3 refused"
    check "open S3: its authority is consumed, S4 only" has "session S3 (tests 8 and 9, 2026-10-05) is closed and its authority is consumed"
    run open S2
    check "open S2: the battery's authority is consumed, S4 only" has "whose authority is consumed: nothing of S1 or S2 is re-run or replaced. This script opens S4 only"
    run row t8
    check "row t8: unknown row (S4: t6 only)" has "REFUSED: unknown row 't8' (S4: t6 only"
    run classify t8 finished valid pass x y
    want_rc 2 "classify t8 refused"
    run
    want_rc 2 "no subcommand: the usage"
    check "the usage names open S4 and row t6" has "open S4 | row t6 |"
    check "no state directory was created by any refusal" test ! -e "$BSTATE"
    check "no session was opened" test ! -e "$EGW_EXEC/current_session"
    ;;
pass)
    run open S4
    want_rc 0 "open S4"
    check "the collector of the clone is compared ($COLLECTOR_SHA)" has "collector: $COLLECTOR_SHA"
    check "the runbook is the merged blob" has "runbook: 317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f"
    check "S2's t6 attempt is admitted in the WSL attempts directory" has "admitted: the one earlier attempt of row t6 (S2's invalid one, plan entry controller_restart-r03, kept as sealed): $B/egw-exec/attempts/$ADMITTED"
    check "and under output_test/runs/2026-10-03/" has "admitted: the one earlier attempt of row t6 (S2's invalid one, plan entry controller_restart-r03, kept as sealed): $B/out/runs/2026-10-03/$ADMITTED"
    check "r04 is planned and fresh on the host" has "fresh on the host: $RID (planned, no raw directory"
    check "r04 is fresh on the guest" has "fresh on the guest: $RID"
    check "the root file system is 6fce1688..." has "rootfs ext4: $ROOTFS"
    check "nothing of S3's exception is examined" lacks "exception"
    check "the session is open" has "session S4 is open"
    check "the next step is row t6" has "Next: 'row t6'"
    check "session-S4.env: state open" test "$(sget "$BSTATE/session-S4.env" state)" = open
    check "the default state directory is <EXEC>/g3-t6-s4" test -f "$BSTATE/session-S4.env"
    run row t6
    want_rc 0 "row t6"
    check "the gate record is compared before row t6 and equals S2's (S3's sealed record)" has "gate record: the image reference, the image id and the repo digest of the six containers equal S2's"
    A=$(sget "$BSTATE/row-t6.env" attempt)
    echo "attempt: $A"
    case $(basename "$A") in *_g3-qualification-t6_attempt02) ok "the new attempt is attempt02 ($(basename "$A"))" ;; *) bad "the new attempt is $(basename "$A")" ;; esac
    check "the row awaits classification" test "$(sget "$BSTATE/row-t6.env" state)" = awaiting-classification
    check "the gate passed" test "$(sget "$BSTATE/row-t6.env" gate)" = pass
    check "the plan before the row: r04 planned" "$REAL_PY" -c "import json,sys; p=json.load(open(sys.argv[1])); sys.exit(0 if [r['status'] for r in p['runs'] if r['run_id']=='$RID']==['planned'] else 1)" "$A/other/campaign_plan.before.json"
    check "the plan after the row: r04 completed (the harness's rewrite is captured)" "$REAL_PY" -c "import json,sys; p=json.load(open(sys.argv[1])); sys.exit(0 if [r['status'] for r in p['runs'] if r['run_id']=='$RID']==['completed'] else 1)" "$A/other/campaign_plan.after.json"
    check "processed/ after the row is captured" test -f "$A/other/processed.after/per_run.csv"
    check "the step shell unset and printed the carriers" grep -q '^carriers after the unset: DEVICES=<unset>' "$(ls "$A"/console/*-t6.stdout.txt)"
    check "the step shell echoes the row file's lines (set -v)" grep -q '^RID=controller_restart-r04; RAW6=' "$(ls "$A"/console/*-t6.stdout.txt)"
    check "the guest-state pair shows the controller's expected restart" grep -q 'EXPECTED-RESTART' "$(ls "$A"/console/*-guest-state-delta.stdout.txt)"
    check "guest-state-delta: faults=0 problems=0" grep -q '^guest-state-delta: faults=0 problems=0$' "$(ls "$A"/console/*-guest-state-delta.stdout.txt)"
    check "guest-state-delta was given --expect-restarted egw-controller-1" grep -q '"--expect-restarted", "egw-controller-1"' "$A/commands.jsonl"
    check "the workload field names S4's authority, r04 and no itest id" "$REAL_PY" -c "import json,sys; w=json.load(open(sys.argv[1]))['workload']; w=json.loads(w) if isinstance(w,str) else w; sys.exit(0 if w['battery']==sys.argv[2] and w['harness_run_id']=='$RID' and w['itest_run_ids']==[] and w['session_label']=='S4' else 1)" "$A/attempt.json" "$AUTH"
    check "the raw directory is a registered source" grep -q "pilot/results/raw/$RID\"" "$A/sources.json"
    check "the configuration identity and its siblings are a registered source" grep -q "\"siblings_glob\": \"$RID.\*\"" "$A/sources.json"
    run classify t6 finished valid pass "@$B/reason.txt" "@$B/next.txt"
    want_rc 0 "classify t6 valid/pass (a bench classification)"
    PKG=$(ls -d "$B"/out/runs/*/"$(basename "$A")" 2> /dev/null | head -n 1)
    echo "package: $PKG"
    check "the package holds the run directory" test -f "$PKG/raw/$RID/manifest.json"
    check "the package holds the configuration identity" test -f "$PKG/simulator/$RID.config_identity.json"
    check "the package holds the .sut directory and the twin siblings" test -f "$PKG/simulator/$RID.sut/docker-events.log" -a -f "$PKG/simulator/$RID.twins.after.json"
    check "the package holds the plan snapshots" test -f "$PKG/other/campaign_plan.after.json"
    check "the package's SHA256SUMS verifies" bash -c "cd '$PKG' && /usr/bin/sha256sum -c --quiet SHA256SUMS"
    run close
    want_rc 0 "close"
    check "session-S4.env: state closed" test "$(sget "$BSTATE/session-S4.env" state)" = closed
    check "the post-close root file system value is recorded" test "$(sget "$BSTATE/session-S4.env" rootfs_after_close)" = "$ROOTFS"
    n=$(grep -c 'restart controller' "$B/ssh.log")
    check "exactly one controller restart reached the guest, the row's own (ssh.log: $n)" test "$n" = 1
    check "the restart came from the row's step, not from the script (it precedes the after-state read)" bash -c "grep -n 'restart controller\|State.OOMKilled' '$B/ssh.log' | tail -n 2 | head -n 1 | grep -q 'restart controller'"
    check "no 'compose up', 'start' or 'docker start' reached the guest" bash -c "! grep -Eq 'compose[^]]* up|docker start|compose[^]]* start' '$B/ssh.log'"
    ;;
preflight3)
    echo 3 > "$B/preflight.exit"
    run open S4
    want_rc 1 "open S4 halts"
    check "HALT: preflight.sh exited 3" has "HALT: preflight.sh exited 3; see"
    check "no exception is examined or applied" lacks "exception"
    check "no environment copy" test ! -e "$BSTATE/S4-environment-copy.txt"
    check "no gate driver" test ! -e "$BSTATE/S4-gate_health.console.txt"
    check "session-S4.env: state halted" test "$(sget "$BSTATE/session-S4.env" state)" = halted
    check "session-S4.env: preflight_exit=3" test "$(sget "$BSTATE/session-S4.env" preflight_exit)" = 3
    run row t6
    want_rc 2 "row t6 refused"
    check "row t6: the session is recorded halted, not open" has "REFUSED: session S4 is recorded 'halted', not open"
    check "no t6 attempt was created" bash -c "! ls -d '$EGW_ATTEMPTS'/*_g3-qualification-t6_attempt02 2> /dev/null | grep -q ."
    run close
    want_rc 0 "close"
    check "session-S4.env: state closed" test "$(sget "$BSTATE/session-S4.env" state)" = closed
    ;;
collector)
    echo "# bench: one line appended to the copy's collector" >> "$B/repo/src/deployment/scripts/collect-resources.sh"
    run open S4
    want_rc 1 "open S4 halts"
    hasE "^HALT: collector \(.*collect-resources.sh\) is [0-9a-f]{64}, the recorded identity is $COLLECTOR_SHA \(packet section 4, halt 6\); nothing was started$" \
        && ok "HALT names the collector and its recorded identity" || bad "no HALT naming the collector"
    check "nothing was started: no session" test ! -e "$EGW_EXEC/current_session"
    check "no session state file" test ! -e "$BSTATE/session-S4.env"
    ;;
rootfs)
    echo 1111111111111111111111111111111111111111111111111111111111111111 > "$B/sha.rootfs"
    run open S4
    want_rc 1 "open S4 halts"
    check "HALT: the root file system is not the expected one" has "HALT: the guest root file system is not the expected one"
    check "expected value printed: 6fce1688... (S3's second opening)" has "expected:    $ROOTFS (the value the close of S3's second opening recorded)"
    check "nothing was started" test ! -e "$EGW_EXEC/current_session" -a ! -e "$BSTATE/session-S4.env"
    ;;
fresh)
    X=$B/out/runs/2026-10-06/20261006T000000Z_g3-qualification-t6_attempt02
    mkdir -p "$X"
    run open S4
    want_rc 1 "another t6 attempt: open halts"
    check "NOT FRESH names the other attempt" has "NOT FRESH: an earlier attempt of row t6 exists: $X"
    check "HALT: an id of S4 is not fresh" has "HALT: an id of S4 is not fresh on the host; nothing was started"
    mv "$X" "$B/hold/x1"
    mkdir -p "$B/out/runs/2026-10-04/$ADMITTED"
    run open S4
    want_rc 1 "the admitted attempt found in another place: open halts"
    check "NOT FRESH names it" has "NOT FRESH: an earlier attempt of row t6 exists: $B/out/runs/2026-10-04/$ADMITTED"
    mv "$B/out/runs/2026-10-04/$ADMITTED" "$B/hold/x2"
    "$REAL_PY" -c "import json,sys; f=sys.argv[1]; p=json.load(open(f)); [r.update(status='running') for r in p['runs'] if r['run_id']=='$RID']; open(f,'w').write(json.dumps(p, indent=2)+'\n')" "$HOME/egw-tcg/pilot/campaign_plan.json"
    run open S4
    want_rc 1 "r04 not planned: open halts"
    check "the plan entry is shown with status running" has "plan entry $RID: status=running"
    cp "$B/plan.orig.json" "$HOME/egw-tcg/pilot/campaign_plan.json"
    mkdir -p "$HOME/egw-tcg/itest/$RID.sut"
    run open S4
    want_rc 1 "<P>/<r04>.sut exists: open halts"
    check "NOT FRESH names the .sut directory" has "NOT FRESH: $HOME/egw-tcg/itest/$RID.sut exists ($RID)"
    mv "$HOME/egw-tcg/itest/$RID.sut" "$B/hold/x3"
    mkdir -p "$HOME/egw-tcg/pilot/results/raw/$RID"
    run open S4
    want_rc 1 "the raw directory exists: open halts"
    check "NOT FRESH names the raw directory" has "NOT FRESH: $HOME/egw-tcg/pilot/results/raw/$RID exists ($RID)"
    mv "$HOME/egw-tcg/pilot/results/raw/$RID" "$B/hold/x4"
    check "no session state file after five halts" test ! -e "$BSTATE/session-S4.env"
    run open S4
    want_rc 0 "the control: everything restored, open S4 passes"
    run close
    want_rc 0 "close"
    ;;
suffix)
    mv "$B/egw-exec/attempts/$ADMITTED" "$B/hold/a1"
    mv "$B/out/runs/2026-10-03/$ADMITTED" "$B/hold/a2"
    run open S4
    want_rc 0 "open S4 (no earlier t6 attempt anywhere: fresh)"
    run row t6
    want_rc 1 "row t6 halts"
    check "HALT: the new attempt is attempt01, not attempt02" hasE "HALT: row t6: the new attempt is named [0-9TZ]+_g3-qualification-t6_attempt01, which does not end '_g3-qualification-t6_attempt02'"
    A=$(sget "$BSTATE/row-t6.env" attempt)
    check "no step of the row ran (no t6 console, no snapshot)" bash -c "! ls '$A'/console/ 2> /dev/null | grep -Eq -- '-(t6|snapshot-before)\.stdout\.txt$'"
    check "the plan was not touched" cmp -s "$B/plan.orig.json" "$HOME/egw-tcg/pilot/campaign_plan.json"
    check "no restart reached the guest" bash -c "! grep -q 'restart controller' '$B/ssh.log'"
    run classify t6 failed not-applicable not-run "@$B/reason.txt" "@$B/next.txt"
    want_rc 1 "classify t6 not started: a halt"
    check "the halt of a row not started" has "HALT: row t6 is classified not started"
    run close
    want_rc 0 "close"
    ;;
gate)
    sed -i 's/^\(identity egw-controller-1 .* image_id=sha256:\)9a293fe1/\100000000/' "$B/gate.identities"
    run open S4
    want_rc 0 "open S4 (the gate driver itself compares nothing)"
    run row t6
    want_rc 1 "row t6 halts"
    check "HALT: the record differs from S2's; row t6 NOT started" hasE "^HALT: the gate package's record of the running images \(.*\) differs from S2's .*: row t6 was NOT started and no attempt was created"
    check "no row state file, no attempt" test ! -e "$BSTATE/row-t6.env"
    check "no new t6 attempt" bash -c "! ls -d '$EGW_ATTEMPTS'/*_g3-qualification-t6_attempt02 2> /dev/null | grep -q ."
    run close
    want_rc 0 "close"
    ;;
esac

say "bench $SC: $CHECKS checks, $FAILS failed"
cleanup
trap - EXIT
[ "$FAILS" -eq 0 ] && echo "RESULT $SC: PASS" || echo "RESULT $SC: FAIL"
exec >&- 2>&-
wait "$MASK_PID" 2> /dev/null
[ "$FAILS" -eq 0 ]
