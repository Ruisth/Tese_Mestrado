#!/bin/bash
# G3 qualification, session S4 (test 6 only) - the operator's steps script.
# S4 (2026-10-05): a copy of the script that S3's second opening ran, finished for ONE
# further session, S4, which runs row t6 once, on plan entry controller_restart-r04. Each
# change of behaviour made for S4 stands under a comment that names S4 and the point of the
# preparation's brief it answers. The marks 'S3 (...)' and 'S3, second opening' are kept
# where the code they explain is unchanged; S3's authorised exception for collector-duration
# is removed (S4, point 3).
#
# S3: this is the battery's steps script (sessions S1 and S2 of 2026-10-02/03) finished
# for ONE further session. Each change of behaviour made for S3 stands under a comment
# that names S3 and the point of the preparation's brief it answers.
#
# Authority (S4, point 7): the request of 2026-10-05
# (output_test/decisions/2026-10-05_g3-t6-session-request.md) and Rui's authorisation of
# one attempt. The session itself starts only on Rui's explicit authorisation and his go
# in the attended window. The authorities of S1, S2 and S3 are consumed: 'open' accepts S4
# only. Test 6 is judged under the criterion amended on 2026-10-05 (LOG #C052) with the
# transition rule 1a-option-a-2026-10-05 (LOG #C053). Procedure and tools: the merged
# commit 1fd9792 (tree 14f89c4). The candidate (controller image, pinned images,
# deployment, guest OS) is unchanged and this script edits nothing of it; the frozen
# preflight installs the merged collector at 'open'. It sources the frozen
# tools/session/common.sh and guest_common.sh and records ONLY through their functions
# (new_attempt, ex, gx, gcp, hx, healthy_wait, headline, driver_code, driver_interrupt)
# and through local_export (set, add-source, finish). One place does not use gx: the
# polls of test 8's wait run gx's own recorded command behind the host's 'timeout'
# (t8_wait_ssh), because a shell function cannot be bounded by 'timeout' (S4, point 9:
# test 8's and test 9's code is left as it was and is reached by nothing in S4).
#
# The operator runs ONE subcommand per invocation and classifies between rows:
#   open S4        checks, UP0, then the frozen drivers guest_session_open.sh,
#                  preflight.sh, the environment copy (PM condition 2), gate_health.sh
#   row t6         S4's one row: one attempt (purpose official), the row's step file
#                  through hx, the gate before and after; the attempt is left OPEN
#   classify <slug> <status> <validity> <outcome> <reason> <next-action>
#   term <slug>    TERM (never KILL) to the recorded process group of a row
#   close          no unit active, the recorded 'compose stop -t 130', then the
#                  frozen guest_session_close.sh (with no QEMU process left there is
#                  nothing to read or stop: a HALT, then that driver alone, which
#                  finishes and exports the session attempt as it stands)
#   status         the session, the clock, the rows
#
# Nothing in it kills QEMU, deletes anything, repeats a row, retries a failed
# step, or uses ACCEPT_UNACCOUNTED, --force or 'local_export set run_id=...'.
# S3 (point 12): it never runs 'compose up', 'start' or 'restart', nor 'docker start',
# never re-launches QEMU and never signals it. The one stack start of S3 is the frozen
# preflight driver's, at 'open' (decision summary, condition B); after test 8's reboot
# nothing on the guest is started, restarted or recreated by this script.
# S4 (point 10): the same holds in S4. The one stack start of S4 is the frozen preflight
# driver's, at 'open'. The controller restart at +300 s is test 6's own fault, issued by
# the harness's --restart-cmd inside the runbook's line that t6.sh holds, never by this
# script and never a restoration; nothing else on the guest is started or restarted.
# Every halt prints 'HALT: ...' and leaves the decision to the operator.
#
# Usage (WSL, login shell; ONE subcommand per wsl.exe invocation, so that a row's
# process group is its own; g3_battery.README.md has the launch lines):
#   EGW_EXEC_REPO=$HOME/egw-exec/repo bash g3_battery.sh <subcommand> [arguments]
# Exit: 0 done; 1 a HALT; 2 refused (nothing was started or changed); 130 (or the
# code driver_status.py derives) after an interrupt.
# State: ${EGW_G3_STATE:-$EXEC/g3-t6-s4} (session-S4.env, row-t6.env, the
# consoles of every invocation and of the four drivers); the battery's own state
# directory, $EXEC/g3-battery, and S3's two ($EXEC/g3-t8t9-s3, $EXEC/g3-t8t9-s3-attempt02)
# are never written. Row files: the rows/ folder
# beside this script, checked against rows/rows.manifest.json before anything runs.
# The script is never edited while a session is open (a row refuses a changed script).
# One changing subcommand at a time: open, row, classify and close each take the turn
# (take_turn) and are refused while another of them is still running; 'status' and
# 'term' take none. A listing of processes is printed and kept only with the value
# after every '--password' hidden (mask_argv).
set -u
SELF=$(readlink -f "$0")
SELF_DIR=$(dirname "$SELF")
if [ -z "${EGW_EXEC_REPO:-}" ] || [ ! -r "$EGW_EXEC_REPO/tools/session/common.sh" ] \
    || [ ! -r "$EGW_EXEC_REPO/tools/session/guest_common.sh" ]; then
    echo "REFUSED: EGW_EXEC_REPO must name the frozen clean clone (\$HOME/egw-exec/repo): its tools/session/common.sh and guest_common.sh are sourced" >&2
    exit 2
fi
export EGW_EXEC_REPO
# shellcheck source=/dev/null
. "$EGW_EXEC_REPO/tools/session/common.sh"
# shellcheck source=/dev/null
. "$EGW_EXEC_REPO/tools/session/guest_common.sh"
DRIVERS=$REPO/tools/session     # common.sh derives DRIVERS from $0, which is this script
S=$SESSION                      # the open session's attempt directory, or empty

# --- the procedure and tools, and the unchanged candidate (request of 2026-10-05, section 2) ---
# S4 (point 2): TOOLS and TREE are the merged commit 1fd9792 and its tree, DRIVERS_SHA the
# 38 driver files at that commit (was 4a6a572d...: collector_check.py, collector_shortfall.py
# and a comment of preflight.sh changed), RUNBOOK_SHA the runbook blob at that commit (1,624
# lines). The export tool, the helper heredoc, tunnel.sh and ca.crt did not change against
# 8e49261 (nor against 80e833f): their values are the battery's.
TOOLS=1fd9792bb76f02c6948f33887207dba4837202db
TREE=14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec
DRIVERS_SHA=2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed
EXPORT_TOOL_SHA=544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b
RUNBOOK_SHA=317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f
HELPER_SHA=e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb
HELPER_LINES=545
TUNNEL_SHA=38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1
CA_SHA=556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff
# S4 (point 2): the collector of the clone, src/deployment/scripts/collect-resources.sh at
# 1fd9792 (was 11444c0a... at 8e49261: its start: and stop: records now carry uptime_s= and
# boot_id=). The frozen preflight copies THIS file to the guest and installs it at 'open';
# verify_candidate compares it at 'open' and before the row.
COLLECTOR_SHA=9e678b024bde66bacc65fea936d05ca226a82e73c86d1cc23a9cf9f8fe8d9b97
# S4 (point 1): the guest root file system expected before S4's boot is the value the close
# of S3's second opening recorded (rootfs_after_close of session-S3.env, in the sealed
# operator records output_test/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02/state/).
ROOTFS_BEFORE_S4=6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4
# S4 (point 3): S3's prospective exception for collector-duration (its checker and that
# checker's sha256) is removed: in S4 a preflight that ends non-zero is a halt at 'open'.
# S3 (point 3): four identities the frozen open driver only records (guest_session_open.sh
# lines 112-119), compared here with what S2's open recorded (console
# 001-identities-before-boot of 20261003T132249Z_guest-session_attempt09): the kernel,
# qemuboot.conf, the QEMU binary and the commit of the Yocto checkout (clean status).
KERNEL_SHA=4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037
QEMUBOOT_SHA=7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4
QEMU_BIN_SHA=5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061
YOCTO_COMMIT=489bc9e5b5b0660026ea2630b8d1d124049ba2ce
CUTOFF_S=10800                  # PM condition 3: no row STARTS after 3 h of session time
GATE_HEALTHY_S=900              # the gate: six services healthy within 900 s
T8_SSH_WAIT_S=900               # T8: at most 15 min for the rebooted guest to answer over ssh
T8_SSH_POLL_S=10                # T8: one read-only poll every 10 s during that wait
T8_SSH_READ_S=20                # S3 (point 6): every poll ends within 20 s, or within what is left of the wait
KEEPALIVE_OPEN_S=21600          # a keepalive client with at least 6 h left at the open
KEEPALIVE_MARGIN_S=1800         # and, before a row, the row's ceiling plus 30 min

# --- paths ----------------------------------------------------------------------------
# S3 (point 1): a state directory of its own; the battery's ($EXEC/g3-battery) is never written.
# S4 (point 2): S4's own state directory; S3's two ($EXEC/g3-t8t9-s3 and
# $EXEC/g3-t8t9-s3-attempt02) and the battery's are kept as they are and never written.
STATE=${EGW_G3_STATE:-$EXEC/g3-t6-s4}
ROWS_DIR=${EGW_G3_ROWS:-$SELF_DIR/rows}
MANIFEST=$ROWS_DIR/rows.manifest.json
HELPER=$HOME/egw-tcg/itest-helpers.sh
P=$HOME/egw-tcg/itest
REPLAY=$HOME/egw-tcg/itest-replay
PLAN=$HOME/egw-tcg/pilot/campaign_plan.json
RAWD=$HOME/egw-tcg/pilot/results/raw
PROCESSED=$HOME/egw-tcg/pilot/results/processed
SUT_ENV=$HOME/egw-tcg/sut_environment.json
# S3 (point 3): where the frozen open driver reads the three files (DEP, BUILD and
# ROOTFS_EXT4 are guest_common.sh's; the Yocto checkout is its OLD).
KERNEL=$DEP/Image-qemuarm64.bin
QEMUBOOT=${ROOTFS_EXT4%.ext4}.qemuboot.conf
QEMU_BIN=$BUILD/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64

# --- the rows (request of 2026-10-05, sections 3 and 4) ---------------------------------
# S4 (point 1): the one session is S4 and its one row is t6. Every other row (t1-smokes to
# t7-ditto, and S3's t8 and t9) belongs to no session of this script: 'row', 'classify' and
# 'term' refuse them as unknown. Their entries in the tables below, and test 8's and test
# 9's functions (S4, point 9), are left as they were and reached by nothing.
ROWS_S4="t6"

session_rows() { case $1 in S4) echo "$ROWS_S4" ;; esac; }

row_session() {
    case " $ROWS_S4 " in *" $1 "*) echo S4; return 0 ;; esac
    return 1
}

row_files() {
    case $1 in
        t1-smokes) echo "t1-smokes.sh" ;;
        t1-harness) echo "t1-harness.sh t1-harness-analyze.sh" ;;
        t2) echo "t2.sh" ;;
        t3) echo "t3.sh" ;;
        t4-replay) echo "t4-replay.sh" ;;
        t4-reset) echo "t4-reset.sh" ;;
        t5) echo "t5.sh" ;;
        t6) echo "t6.sh" ;;
        t7-mongo) echo "t7-mongo.sh" ;;
        t7-ditto) echo "t7-ditto.sh" ;;
        t8) echo "t8-a-reboot.sh t8-b-wait-boot-id.sh t8-c-unaided.sh t8-d-tunnel.sh t8-e-state.sh t8-f-smoke.sh" ;;
        t9) echo "t9-a.sh t9-b.sh t9-c.sh t9-de.sh t9-exposure.sh" ;;
    esac
}

# Row ceilings in minutes (packet section 4): recorded, never enforced by a timer.
# The operator enforces them with 'term'.
row_ceiling_min() {
    case $1 in
        t1-smokes) echo 105 ;; t1-harness) echo 35 ;; t2) echo 36 ;; t3) echo 37 ;;
        t4-replay) echo 67 ;; t4-reset) echo 35 ;; t5) echo 38 ;; t6) echo 47 ;;
        t7-mongo | t7-ditto) echo 41 ;; t8) echo 135 ;; t9) echo 25 ;;
    esac
}

# The itest run ids a row publishes under, registered as 'simulator' sources BEFORE the
# row runs (T9's three are registered after it: a refused connection writes nothing).
row_itest_ids() {
    case $1 in
        t1-smokes) echo "itest-smoke-01-q1 itest-smoke-02-q1 itest-smoke-03-q1" ;;
        t2) echo "itest-3dev-01-q1" ;;
        t3) echo "itest-invalid-01-q1" ;;
        t4-replay) echo "itest-dup-01-q1" ;;
        t4-reset) echo "itest-dup-02-q1" ;;
        t5) echo "itest-dropout-01-q1" ;;
        t7-mongo) echo "itest-mongo-fault-01-q1" ;;
        t7-ditto) echo "itest-ditto-fault-01-q1" ;;
        t8) echo "itest-post-reboot-01-q2" ;;      # S3 (point 2): the fresh smoke run id
    esac
}
# S3 (point 2): the fresh -q2 identifiers of the request's section 3 (itest-acl-<UTC stamp>
# is taken by the row itself and is never changed). No -q1 identifier is used by S3.
T8_PREFIX=itest-reboot-q2
T9_IDS="itest-tls-wrongca-q2 itest-auth-wrongpw-q2 itest-notls-q2"
# S3 (point 9): the one earlier attempt of row t8 that is admitted (S2's halted one, kept
# as sealed), and the name the export tool is expected to give each row's new attempt (it
# numbers by scenario slug: the next number after the highest one found).
T8_ADMITTED=20261003T142310Z_g3-qualification-t8_attempt01
# S4 (point 5): the one earlier attempt of row t6 that is admitted, S2's invalid one (plan
# entry controller_restart-r03), kept as sealed in the WSL attempts directory and under
# output_test/runs/2026-10-03/; S4's attempt of t6 must therefore be attempt02.
T6_ADMITTED=20261003T132936Z_g3-qualification-t6_attempt01
row_attempt_suffix() { case $1 in t6) echo _g3-qualification-t6_attempt02 ;; t8) echo _g3-qualification-t8_attempt02 ;; t9) echo _g3-qualification-t9_attempt01 ;; esac; }

# S4 (point 4): t6 runs the runbook's own literal, the supplementary plan entry r04.
row_harness_id() { case $1 in t1-harness) echo nominal-r02 ;; t6) echo controller_restart-r04 ;; esac; }

# The container the row itself restarts in place (guest_state_delta.py --expect-restarted).
row_restarted() {
    case $1 in
        t6) echo egw-controller-1 ;;
        t7-mongo) echo egw-mongodb-1 ;;
        t7-ditto) echo egw-ditto-things-1 ;;
    esac
}

# Every id of a row that must be unused on the host before the row starts.
row_fresh_ids() {
    case $1 in
        t8) echo "$T8_PREFIX $(row_itest_ids t8)" ;;
        t9) echo "$T9_IDS" ;;
        *) row_itest_ids "$1" ;;
    esac
}

# The run ids named in the attempt's workload field (never 'run_id'), and a note for
# the two names that are not run ids.
row_workload_ids() { case $1 in t9) echo "$T9_IDS" ;; *) row_itest_ids "$1" ;; esac; }
row_id_note() {
    case $1 in
        t8) echo "$T8_PREFIX is the prefix of the reboot snapshots, of the boot id file and of the pre-reboot container set, not a run id" ;;
        t9) echo "(d)+(e) use itest-acl-<UTC stamp>, taken by the row itself (see its console)" ;;
    esac
}

# --- the gate's guest-state read: nominal.sh's GUEST_STATE, verbatim -------------------
# It is compared with the frozen driver's own text before it is used (check_guest_state).
GUEST_STATE="cd /opt/egw/deployment || exit 1
rc=0
docker ps --format '{{.Names}} {{.Status}}'
for c in \$(docker ps -a --format '{{.Names}}'); do
    oom=\$(docker inspect -f '{{.State.OOMKilled}}' \"\$c\") || rc=1
    res=\$(docker inspect -f '{{.RestartCount}}' \"\$c\") || rc=1
    cid=\$(docker inspect -f '{{.Id}}' \"\$c\") || rc=1
    sat=\$(docker inspect -f '{{.State.StartedAt}}' \"\$c\") || rc=1
    echo \"container \$c oomkilled=\${oom:-unknown} restarts=\${res:-unknown} id=\${cid:-unknown} started=\${sat:-unknown}\"
    [ -n \"\$oom\" ] && [ -n \"\$res\" ] && [ -n \"\$cid\" ] && [ -n \"\$sat\" ] || rc=1
done
if KMSG=\$(sudo -n dmesg 2>/dev/null); then
    echo \"memory-cgroup OOM lines: \$(printf '%s\n' \"\$KMSG\" | grep -ci 'memory cgroup out of memory' || true)\"
else
    echo 'dmesg could not be read: the OOM state of this boot is UNKNOWN, which is not \"no OOM\"'
    rc=1
fi
free -m
df -h / /var/lib/docker /tmp
exit \$rc"

# What every step's shell does before the row file is sourced (operator procedure,
# "Running the runbook lines"): one ordered transcript, the carriers unset and printed,
# 'set -v' (never 'set -x': the simulator password is on its argv), no 'set -e'.
STEP_PRE='exec 2>&1; unset DEVICES ACCEPT_UNACCOUNTED EVENTS_EXPECTED DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S READY_LIMIT_S; echo "carriers after the unset: DEVICES=${DEVICES-<unset>} ACCEPT_UNACCOUNTED=${ACCEPT_UNACCOUNTED-<unset>} EVENTS_EXPECTED=${EVENTS_EXPECTED-<unset>} DRAIN_QUIET_S=${DRAIN_QUIET_S-<unset>} DRAIN_STEP_S=${DRAIN_STEP_S-<unset>} DRAIN_LIMIT_S=${DRAIN_LIMIT_S-<unset>} READY_LIMIT_S=${READY_LIMIT_S-<unset>}; EGW_CLONE=$EGW_CLONE CTRL=$CTRL DITTO=$DITTO MQTT_PORT=$MQTT_PORT"; set -v'

# The read-only guest check of the gate and of the close: no egw-events-* (the Docker
# events recorder) and no egw-resources-* (the collector) unit active. 0 none; 3 at
# least one active; 1 the units could not be listed.
units_script() {
    cat << 'GUEST_UNITS'
U=$(systemctl list-units --no-legend --plain --type=service --state=active,activating,reloading,deactivating 'egw-events-*' 'egw-resources-*') \
    || { echo 'STOP: systemctl could not list the units: whether a recorder or collector unit is active is UNKNOWN'; exit 1; }
if [ -n "$U" ]; then
    printf '%s\n' "$U"
    echo 'ACTIVE UNIT: a recorder (egw-events-*) or collector (egw-resources-*) unit is still active'
    exit 3
fi
echo 'no egw-events-* and no egw-resources-* unit is active'
systemctl list-units --all --no-legend --plain --type=service 'egw-events-*' 'egw-resources-*' || true
exit 0
GUEST_UNITS
}

# T8: the one qemu-system-aarch64 process of this host, named by its pid, its start
# instant (clock ticks since the WSL boot, field 22 of /proc/PID/stat: a pid can be
# given again, a pid with its start instant names one process) and the disk files on
# its command line ('file=' of each -drive). The launcher (3.3, run-qemu-integrated.sh)
# runs QEMU WITHOUT -no-reboot, so the guest reboots INSIDE the same process: 'before'
# records the process (before step a), 'after' records it again (after the wait for the
# rebooted guest) and compares with the recorded values. Read-only; QEMU is never
# signalled. A different process, none, or several, is a STOP: a QEMU exit followed by
# another launcher is not this procedure, and a re-launch through 3.3 is a recorded
# operator decision, never automatic. Arguments: before|after, the executable pattern
# of guest_common.sh, then (after) the recorded pid, start instant and disks.
# S3 (point 5): 'before' also reads the whole command line of that process for
# -no-reboot (QEMU accepts --no-reboot as well, and documents the option as a shortcut
# for '-action reboot=shutdown': the three spellings of the one setting are looked for,
# each as a whole argument). With it QEMU EXITS at a guest reboot instead of rebooting
# inside the process, which is not the procedure of test 8: exit 3, and the caller halts
# before the reboot is issued (step a is not run). A command line that cannot be read
# is a STOP too (exit 1): the absence of the option was not shown.
T8_QEMU_IDENT='
mode=$1; re=$2; pid0=${3:-}; start0=${4:-}; disks0=${5:-}
listing=$(pgrep -af "$re"); q=$?
printf "%s\n" "$listing" | cut -c1-160
case $q in
    0) ;;
    1) echo "STOP: no qemu-system-aarch64 process (pgrep exit 1): the guest is lost, or the first QEMU exited - nothing is re-launched by this script"; exit 1 ;;
    *) echo "STOP: whether a qemu-system-aarch64 process runs could not be determined (pgrep exit $q)"; exit 1 ;;
esac
n=$(printf "%s\n" "$listing" | grep -c .)
[ "$n" -eq 1 ] || { echo "STOP: $n qemu-system-aarch64 processes, not one: the session guest cannot be told apart"; exit 1; }
pid=${listing%% *}
s=$(cat "/proc/$pid/stat" 2> /dev/null) || { echo "STOP: /proc/$pid/stat could not be read: the QEMU process cannot be named"; exit 1; }
s=${s##*) }
set -- $s
start=${20:-}
[ -n "$start" ] || { echo "STOP: the start instant of pid $pid could not be read from /proc/$pid/stat"; exit 1; }
disks=$(tr "\0" "\n" < "/proc/$pid/cmdline" 2> /dev/null | grep -o "file=[^,]*" | paste -sd ";" -)
echo "QEMU PROCESS: pid=$pid start=$start disks=$disks"
if [ "$mode" != after ]; then
    args=$(tr "\0" "\n" < "/proc/$pid/cmdline" 2> /dev/null)
    [ -n "$args" ] || { echo "STOP: the command line of pid $pid (/proc/$pid/cmdline) could not be read: whether -no-reboot is on it is UNKNOWN - the reboot is NOT issued"; exit 1; }
    found=$(printf "%s\n" "$args" | grep -n -x -E -e "--?no-reboot" -e "(.*,)?reboot=shutdown(,.*)?")
    if [ -n "$found" ]; then
        echo "STOP: -no-reboot (or its equivalent) is on the command line of the QEMU process $pid, as argument number:text $(printf "%s" "$found" | tr "\n" " "): this QEMU exits at a guest reboot instead of rebooting inside the same process - the reboot is NOT issued, and nothing was signalled"
        exit 3
    fi
    echo "QEMU COMMAND LINE: no -no-reboot, no --no-reboot and no reboot=shutdown among the $(printf "%s\n" "$args" | grep -c "") arguments of pid $pid"
    exit 0
fi
if [ "$pid" = "$pid0" ] && [ "$start" = "$start0" ] && [ "$disks" = "$disks0" ]; then
    echo "QEMU PROCESS UNCHANGED: the same process as before step a (pid $pid, started at tick $start) with the same disks ($disks); whether the guest rebooted inside it is what step b shows"
    exit 0
fi
echo "STOP: the qemu-system-aarch64 process is not the one recorded before step a (before: pid=$pid0 start=$start0 disks=$disks0; now: pid=$pid start=$start disks=$disks): the guest did not reboot inside the same QEMU process, or another launcher ran - nothing was signalled and nothing is re-launched"
exit 1'

# The mutable harness inputs and outputs, copied into the attempt at this moment
# (other/): the pilot plan, and with 'both' the processed/ tree analyze rewrites.
SNAPSHOT='
rc=0; d=$1/other; label=$2; what=$3; plan=$4; proc=$5
mkdir -p "$d" || exit 1
if [ ! -e "$d/campaign_plan.$label.json" ] && cp -p "$plan" "$d/campaign_plan.$label.json"; then
    sha256sum "$plan" "$d/campaign_plan.$label.json" || rc=1
else
    echo "STOP: the plan $plan was not copied to $d/campaign_plan.$label.json (or that copy exists: never overwritten)"; rc=1
fi
if [ "$what" = both ]; then
    if [ ! -d "$proc" ]; then
        echo "no processed/ tree at this moment ($proc): nothing to copy"
    elif [ ! -e "$d/processed.$label" ] && cp -a "$proc" "$d/processed.$label"; then
        (cd "$d/processed.$label" && find . -type f -exec sha256sum {} + | sort -k2) || rc=1
    else
        echo "STOP: $proc was not copied to $d/processed.$label (or that copy exists: never overwritten)"; rc=1
    fi
fi
exit $rc'

# rows.manifest.json (g3_extract_rows.py): "files" maps each step file to its row,
# session, step_order and sha256_after; "rows" lists each row's steps in order.
MANIFEST_PY='
import hashlib, json, os, sys
mode, manifest_path, rows_dir = sys.argv[1], sys.argv[2], sys.argv[3]
def fail(msg):
    print("STOP: " + msg)
    sys.exit(1)
try:
    raw = open(manifest_path, "rb").read()
    doc = json.loads(raw.decode("utf-8"))
except (OSError, ValueError) as exc:
    fail("the manifest %s could not be read: %s" % (manifest_path, exc))
files = doc.get("files") if isinstance(doc, dict) else None
if not isinstance(files, dict):
    fail("the manifest %s holds no \"files\" object" % manifest_path)
rows = {}
for r in doc.get("rows") or []:
    if isinstance(r, dict):
        rows[r.get("row")] = r
if mode == "verify":
    session, slug, names = sys.argv[4], sys.argv[5], sys.argv[6:]
    row = rows.get(slug) or {}
    if row.get("steps") != names or row.get("session") != session:
        fail("row %s: the manifest names session %r and steps %r, the steps script %r and %r"
             % (slug, row.get("session"), row.get("steps"), session, names))
    for order, name in enumerate(names, 1):
        e = files.get(name)
        if not isinstance(e, dict):
            fail("%s is not in the manifest" % name)
        if e.get("row") != slug or e.get("session") != session or e.get("step_order") != order:
            fail("%s: the manifest says row %r session %r step %r, the steps script row %r session %r step %d"
                 % (name, e.get("row"), e.get("session"), e.get("step_order"), slug, session, order))
        want = e.get("sha256_after")
        try:
            data = open(os.path.join(rows_dir, name), "rb").read()
        except OSError as exc:
            fail("%s could not be read in %s: %s" % (name, rows_dir, exc))
        got = hashlib.sha256(data).hexdigest()
        if b"\r" in data:
            fail("%s holds a carriage return" % name)
        if not isinstance(want, str) or got != want:
            fail("%s: sha256 %s is not the manifest sha256_after %s" % (name, got, want))
        print("row file %s: sha256 %s = sha256_after of the manifest (row %s, step %d, %d bytes)"
              % (name, got, slug, order, len(data)))
    sys.exit(0)
if mode == "sha":
    print(hashlib.sha256(raw).hexdigest())
    sys.exit(0)
if mode == "entries":
    slug, names = sys.argv[4], sys.argv[5:]
    out = {"rows_manifest_sha256": hashlib.sha256(raw).hexdigest(), "schema": doc.get("schema"),
           "generated_by": doc.get("generated_by"), "generator_sha256": doc.get("generator_sha256"),
           "runbook": doc.get("runbook"), "extraction_rule": doc.get("extraction_rule"),
           "substitution_rule": doc.get("substitution_rule"), "row": rows.get(slug),
           "files": dict((n, files.get(n)) for n in names)}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    sys.exit(0)
if mode == "workload":
    # slug session-basename label ceiling up0 now steps-sha helper-sha clone itest-ids harness-id id-note file...
    (slug, session, label, ceiling, up0, now, steps_sha, helper_sha, clone, ids, harness, note) = sys.argv[4:16]
    names = sys.argv[16:]
    # S3 (point 2): the authority of this session, in the field that named the battery (the key is kept).
    # S4 (point 7): the authority of S4 in that field.
    w = {"battery": "G3 qualification, session S4: test 6 only (controller_restart-r04; request of 2026-10-05, output_test/decisions/2026-10-05_g3-t6-session-request.md; criterion amended on 2026-10-05, LOG #C052; transition rule 1a-option-a-2026-10-05, LOG #C053)",
         "row": slug, "session": session, "session_label": label,
         "itest_run_ids": [i for i in ids.split(",") if i], "harness_run_id": harness or None,
         "ids_note": note or None,
         "runbook": doc.get("runbook"), "rows_manifest_sha256": hashlib.sha256(raw).hexdigest(),
         "step_files": dict((n, (files.get(n) or {}).get("sha256_after")) for n in names),
         "step_source_lines": dict((n, (files.get(n) or {}).get("source_line_ranges")
                                    or (files.get(n) or {}).get("kind")) for n in names),
         "steps_script_sha256": steps_sha, "helper_sha256": helper_sha, "egw_clone": clone,
         "row_ceiling_min": int(ceiling), "host_uptime_baseline_s": int(up0),
         "host_uptime_at_row_start_s": int(now), "session_elapsed_at_row_start_s": int(now) - int(up0)}
    print(json.dumps(w, ensure_ascii=False))
    sys.exit(0)
fail("unknown mode %r" % mode)
'

manifest_tool() { "$PY" -c "$MANIFEST_PY" "$@"; }

# --- small helpers --------------------------------------------------------------------
up_now() {
    local u _r
    read -r u _r < /proc/uptime
    printf '%s' "${u%.*}"
}
stamp() { printf '%s up=%s' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(up_now)"; }
say() { echo "## $(stamp) $*"; }
one_line() { printf '%s' "$1" | tr '\n\r\t' '   '; }
sha_of() {
    local h
    h=$(sha256sum "$1" 2> /dev/null) || return 1
    printf '%s' "${h%% *}"
}
wsl_boot_id() { cat /proc/sys/kernel/random/boot_id 2> /dev/null; }
own_pgid() { ps -o pgid= -p "$$" 2> /dev/null | tr -d ' '; }    # (ps complains of the pty's size on stderr)

# mask_argv: a 'pid command line' listing with the value after every --password hidden.
# The simulator, the replay, the harness and T9's probes carry the broker password on
# their argv (the reason for 'set -v', never 'set -x'): a listing of a row's processes
# is printed, or written to the state directory, only through this filter, and cut at
# 90 columns besides. The state directory is sealed as the operator records, which the
# frozen export's secret scan never reads.
mask_argv() { sed -E 's/(--password)([= ]+)[^ ]+/\1\2<hidden>/g'; }

# proc_start PID: when that process started (clock ticks since the boot, field 22 of
# /proc/PID/stat), or nothing. A pid is a number that can be given again; a pid with
# its start instant names one process.
proc_start() {
    local s
    s=$(cat "/proc/$1/stat" 2> /dev/null) || return 1
    s=${s##*) }
    # shellcheck disable=SC2086
    set -- $s
    printf '%s' "${20:-}"
}

# row_alive ROW_FILE: 0 when the process that ran the row is still running.
row_alive() {
    local pid start
    [ "$(state_get "$1" wsl_boot_id)" = "$(wsl_boot_id)" ] || return 1
    pid=$(state_get "$1" pid)
    start=$(state_get "$1" pid_start)
    case $pid in '' | *[!0-9]*) return 1 ;; esac
    [ -n "$start" ] && [ "$(proc_start "$pid")" = "$start" ]
}

# row_group ROW_FILE: the processes still in the row's own process group, one 'pid
# command line' per line; non-zero when none is left or when the recorded number now
# names another group (another WSL boot, or a leader that started at another instant).
row_group() {
    local pgid start
    [ "$(state_get "$1" wsl_boot_id)" = "$(wsl_boot_id)" ] || return 1
    pgid=$(state_get "$1" pgid)
    start=$(state_get "$1" pgid_start)
    case $pgid in '' | *[!0-9]*) return 1 ;; esac
    [ "$pgid" != "$(own_pgid)" ] || return 1      # this invocation's own group: not a leftover
    if [ -e "/proc/$pgid" ]; then
        [ -n "$start" ] && [ "$(proc_start "$pgid")" = "$start" ] || return 1
    fi
    pgrep -g "$pgid" -a
}

# The state files are 'key=value' lines, one value per line. They are read with
# state_get, never sourced. state_add keeps every line (halts, steps, clock readings).
state_set() {
    local f=$1 k=$2 v tmp
    v=$(one_line "$3")
    tmp=$f.tmp.$$
    {
        [ ! -f "$f" ] || grep -v "^$k=" "$f"
        printf '%s=%s\n' "$k" "$v"
    } > "$tmp" && mv "$tmp" "$f"
}
state_get() {
    [ -f "$1" ] || return 1
    sed -n "s/^$2=//p" "$1" | tail -n 1
}
state_add() { printf '%s=%s\n' "$2" "$(one_line "$3")" >> "$1"; }
row_set() { state_set "$ROW_FILE" "$1" "$2"; }

refuse() {
    echo "REFUSED: $*"
    exit 2
}

# halt TEXT: the one line the operator acts on. It is kept in the session's state file
# (and the row's), so that no later row starts without Rui's direction.
SESSION_FILE=""
ROW_FILE=""
ROW_SLUG=""
HALTED=0
halt() {
    HALTED=1
    echo "HALT: $*"
    [ -z "$SESSION_FILE" ] || state_add "$SESSION_FILE" halt "up=$(up_now) ${ROW_SLUG:+row=$ROW_SLUG }$*"
    [ -z "$ROW_FILE" ] || [ ! -e "$ROW_FILE" ] || state_add "$ROW_FILE" halt "up=$(up_now) $*"
}

# tee_safe FILE: tee that outlives a TERM sent to the process group (the drivers' and
# this script's own interrupt handlers still have a reader for what they print).
tee_safe() { (trap '' INT TERM HUP; exec tee -p -a "$1"); }

# start_log NAME: this invocation's own console, kept in the state directory (the
# operator records). Never overwritten: a new number for every invocation.
start_log() {
    local n
    mkdir -p "$STATE/console" || refuse "the state directory $STATE/console could not be created"
    n=$(find "$STATE/console" -maxdepth 1 -type f -name '[0-9][0-9][0-9]-*.txt' | wc -l)
    # The file is claimed as it is named (noclobber: created only if absent), so two
    # invocations started at the same moment never write one console.
    while :; do
        n=$((n + 1))
        LOG=$STATE/console/$(printf '%03d' "$n")-$1.txt
        (set -o noclobber && : > "$LOG") 2> /dev/null && break
        [ "$n" -lt 5000 ] || refuse "no console file could be created in $STATE/console"
    done
    exec > >(trap '' INT TERM HUP; exec tee -p -a "$LOG") 2>&1
    TEE_PID=$!
    trap 'finish_log' EXIT
}
TEE_PID=""
# finish_log (EXIT): let the console's tee write its last lines before the script ends,
# so that what the caller prints next does not overtake them.
finish_log() {
    local n=0
    exec >&- 2>&-
    [ -n "$TEE_PID" ] || return 0
    # at most 5 s: a process that kept this console's pipe open must not hold the exit
    while kill -0 "$TEE_PID" 2> /dev/null && [ "$n" -lt 50 ]; do
        sleep 0.1
        n=$((n + 1))
    done
}

# take_turn WHAT: one changing subcommand (open, row, classify, close) at a time. A
# check followed, seconds later, by the write it tests for is not a guard: two 'row
# <slug>' started together both passed "this row was not started yet" and both ran the
# row; a 'close' issued while 'open' was still in its preflight powered the guest off
# under it. The turn is a record in the state directory of who holds it (the pid, its
# start instant, the WSL boot), read and rewritten under a short flock; its holder is
# the process that record names for as long as that process lives. The lock itself is
# released before anything else runs, so no child inherits it (QEMU and a row's own
# jobs outlive this script); nothing is deleted: the turn of a holder that is gone is
# simply taken. A refusal here is exit 2: nothing was started or changed. 'status'
# (read-only) and 'term' (which must reach a running row) take no turn.
take_turn() {
    local f=$STATE/turn.env pid start boot what tmp
    mkdir -p "$STATE" || refuse "the state directory $STATE could not be created"
    command -v flock > /dev/null 2>&1 \
        || refuse "flock is not on PATH: one changing subcommand at a time cannot be guaranteed, so nothing was started"
    # shellcheck disable=SC2093
    exec 9>> "$STATE/turn.lock" || refuse "the turn lock $STATE/turn.lock could not be opened: nothing was started"
    if ! flock -w 20 9; then
        exec 9>&-
        refuse "the turn lock $STATE/turn.lock was not obtained within 20 s (another invocation is taking its turn): nothing was started"
    fi
    pid=$(state_get "$f" pid)
    start=$(state_get "$f" pid_start)
    boot=$(state_get "$f" wsl_boot_id)
    what=$(state_get "$f" what)
    case $pid in *[!0-9]*) pid="" ;; esac
    if [ -n "$pid" ] && [ "$pid" != "$$" ] && [ -n "$start" ] && [ "$boot" = "$(wsl_boot_id)" ] \
        && [ "$(proc_start "$pid")" = "$start" ]; then
        exec 9>&-
        refuse "another invocation of this script is still running: '$what' (pid $pid, since $(state_get "$f" taken_wall)). One changing subcommand at a time: nothing was started or changed. 'status' reads the state; 'term <slug>' sends TERM, never KILL, to a running row"
    fi
    tmp=$f.tmp.$$
    if ! { printf 'what=%s\npid=%s\npid_start=%s\nwsl_boot_id=%s\ntaken_wall=%s\ntaken_up=%s\n' "$(one_line "$1")" "$$" \
        "$(proc_start "$$")" "$(wsl_boot_id)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(up_now)" > "$tmp" && mv "$tmp" "$f"; }; then
        exec 9>&-
        refuse "the turn could not be recorded in $f: nothing was started"
    fi
    exec 9>&-
}

# open_label: the label (S4; point 1) of the session whose state file names the session
# that is open now, or nothing.
open_label() {
    local l f
    [ -n "$SESSION" ] || return 1
    # S3 (point 1): one label; the battery's loop over its labels is kept in its form.
    # S4 (point 1): the one label is S4.
    # shellcheck disable=SC2043
    for l in S4; do
        f=$STATE/session-$l.env
        [ -f "$f" ] || continue
        if [ "$(state_get "$f" session_attempt)" = "$SESSION" ]; then
            echo "$l"
            return 0
        fi
    done
    return 1
}

# check_guest_state: the GUEST_STATE text above must be nominal.sh's own, byte for byte.
check_guest_state() {
    local frozen value
    frozen=$(sed -n '/^GUEST_STATE="cd \/opt\/egw\/deployment || exit 1$/,/^exit \\\$rc"$/p' "$DRIVERS/nominal.sh")
    [ -n "$frozen" ] || { WHY="the GUEST_STATE text was not found in $DRIVERS/nominal.sh"; return 1; }
    value=$(unset GUEST_STATE; eval "$frozen"; printf '%s' "${GUEST_STATE-}")
    [ -n "$value" ] && [ "$value" = "$GUEST_STATE" ] \
        || { WHY="this script's guest-state command is not the frozen nominal.sh's GUEST_STATE"; return 1; }
    echo "guest-state command: identical to GUEST_STATE of $DRIVERS/nominal.sh ($(printf '%s' "$GUEST_STATE" | sha256sum | cut -d' ' -f1))"
}

want_sha() {   # want_sha LABEL EXPECTED FILE
    local got
    got=$(sha_of "$3") || got=unreadable
    echo "$1: $got  $3"
    [ "$got" = "$2" ] || { WHY="$1 ($3) is $got, the recorded identity is $2"; return 1; }
}

# verify_candidate: the identities this host holds (request of 2026-10-05, section 2: the
# merged procedure and tools, and the unchanged candidate). Non-zero, with WHY, at the
# first that differs.
WHY=""
verify_candidate() {
    local head tree porcelain ids n yhead yporcelain
    head=$(git -C "$REPO" rev-parse HEAD 2> /dev/null) || head=unreadable
    tree=$(git -C "$REPO" rev-parse 'HEAD^{tree}' 2> /dev/null) || tree=unreadable
    echo "clone $REPO: HEAD=$head tree=$tree"
    [ "$head" = "$TOOLS" ] && [ "$tree" = "$TREE" ] || { WHY="the clone $REPO is not at $TOOLS / $TREE"; return 1; }
    porcelain=$(git -C "$REPO" status --porcelain 2> /dev/null) || { WHY="git status failed in $REPO"; return 1; }
    [ -z "$porcelain" ] || { WHY="the clone $REPO is not clean ($(printf '%s\n' "$porcelain" | wc -l) porcelain line(s))"; return 1; }
    echo "clone: clean (0 porcelain lines)"
    ids=$(repo_identity) || { WHY="repo_identity failed: $ids"; return 1; }
    echo "repo_identity: $ids"
    case $ids in *"\"drivers_sha256\": \"$DRIVERS_SHA\""*) ;; *) WHY="drivers_sha256 is not $DRIVERS_SHA"; return 1 ;; esac
    case $ids in *"\"export_tool_sha256\": \"$EXPORT_TOOL_SHA\""*) ;; *) WHY="export_tool_sha256 is not $EXPORT_TOOL_SHA"; return 1 ;; esac
    want_sha runbook "$RUNBOOK_SHA" "$REPO/docs/setup/qemu_integrated_gateway.md" || return 1
    # S4 (point 2): the clone's collector, the one the frozen preflight installs on the guest.
    want_sha collector "$COLLECTOR_SHA" "$REPO/src/deployment/scripts/collect-resources.sh" || return 1
    want_sha helpers "$HELPER_SHA" "$HELPER" || return 1
    n=$(wc -l < "$HELPER") || n=unreadable
    [ "$n" = "$HELPER_LINES" ] || { WHY="the helper file has $n lines, not $HELPER_LINES"; return 1; }
    bash -n "$HELPER" || { WHY="the helper file does not parse (bash -n)"; return 1; }
    echo "helpers: $HELPER_LINES lines, bash -n clean"
    want_sha tunnel.sh "$TUNNEL_SHA" "$HOME/egw-tcg/tunnel.sh" || return 1
    want_sha ca.crt "$CA_SHA" "$HOME/egw-tcg/ca.crt" || return 1
    # S3 (point 3): the kernel, qemuboot.conf, the QEMU binary and the Yocto checkout
    # (commit and clean status), which the frozen open driver records and compares with
    # nothing. A difference is a halt of the same kind as the identities above.
    want_sha kernel "$KERNEL_SHA" "$KERNEL" || return 1
    want_sha qemuboot.conf "$QEMUBOOT_SHA" "$QEMUBOOT" || return 1
    want_sha qemu-system-aarch64 "$QEMU_BIN_SHA" "$QEMU_BIN" || return 1
    yhead=$(git -C "$OLD" rev-parse HEAD 2> /dev/null) || yhead=unreadable
    echo "Yocto checkout $OLD: HEAD=$yhead"
    [ "$yhead" = "$YOCTO_COMMIT" ] || { WHY="the Yocto checkout $OLD is at $yhead, the recorded identity is $YOCTO_COMMIT"; return 1; }
    yporcelain=$(git -C "$OLD" status --porcelain 2> /dev/null) || { WHY="git status failed in the Yocto checkout $OLD"; return 1; }
    [ -z "$yporcelain" ] || { WHY="the Yocto checkout $OLD is not clean ($(printf '%s\n' "$yporcelain" | wc -l) porcelain line(s))"; return 1; }
    echo "Yocto checkout: clean (0 porcelain lines)"
    check_guest_state || return 1
}

# S3 (point 4): the images the gate driver found running, against S2's record. The frozen
# gate_health.sh writes environment/container_identities.txt in its attempt (one line
# 'identity <container> image=... image_id=... repo_digest=... container_id=... started=...'
# for each of the six containers, then the controller build identity copied from the
# guest) and compares it with nothing. What identifies the running images, for each
# container, is the image reference, the image id and the repo digest: those three are
# compared. The container id names a container object, not an image, and the start
# instant changes at every boot: neither is compared (S1's and S2's gate records hold the
# same six container ids and different start instants; in the three compared fields they
# are equal). The six lines below are those of S2's gate package, file
# output_test/runs/2026-10-03/20261003T132836Z_g2-gate-preconditions_attempt06/environment/container_identities.txt
# (sha256 60f7e99b604bc78a7e176cae7dcefef2ffb2ba549e33cdbf05ad1313bb7073d1), lines 1 to 6,
# each cut before ' container_id='. The build-identity lines that follow them in that
# file are not compared here: the frozen preflight compares the controller image id with
# the guest's record.
# S4 (point 6): the constant and its comparison are kept; the comparison now runs before
# row t6. S3's gate package matched these six lines in the three compared fields (read on
# 2026-10-05: output_test/runs/2026-10-05/20261005T115022Z_g2-gate-preconditions_attempt07/
# environment/container_identities.txt, sha256
# a713c8ba15548631b4e2576ff30c7636c79565c7d3d82bcad3a2cdb6978cac86, six identity lines).
GATE_IDENTITIES_S2='identity egw-mosquitto-1 image=docker.io/library/eclipse-mosquitto:2.0.22@sha256:212f89e1eaeb2c322d6441b64396e3346026674db8fa9c27beac293405c32b3c image_id=sha256:5fef2509a20f85341b1e5c4dd7864e1a4a15fba155b88afa025cbcd5b5611ce9 repo_digest=eclipse-mosquitto@sha256:212f89e1eaeb2c322d6441b64396e3346026674db8fa9c27beac293405c32b3c
identity egw-mongodb-1 image=docker.io/library/mongo:7.0.39@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d image_id=sha256:d58a07b4b2ecaff800c05ed786685d18dcbb5b31a801fdc57bdfb819a9f46c8f repo_digest=mongo@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d
identity egw-ditto-policies-1 image=docker.io/eclipse/ditto-policies:3.9.4@sha256:652f75b9accfc1da8cbc228bcede0f7778e732b9625225dafad4a2930903d4bb image_id=sha256:0e93f53bed2734b7ef83a59054b61077612cc40bbe47c4b6753d12eaefa3e99c repo_digest=eclipse/ditto-policies@sha256:652f75b9accfc1da8cbc228bcede0f7778e732b9625225dafad4a2930903d4bb
identity egw-ditto-things-1 image=docker.io/eclipse/ditto-things:3.9.4@sha256:a1cc8a12d167ae5a22a31c9163913736ca14dcef4b544e6270265965089247b0 image_id=sha256:38fef6b7598be0513532c227271c124437a54eb759c2a05f34305832d91b7122 repo_digest=eclipse/ditto-things@sha256:a1cc8a12d167ae5a22a31c9163913736ca14dcef4b544e6270265965089247b0
identity egw-ditto-gateway-1 image=docker.io/eclipse/ditto-gateway:3.9.4@sha256:fc9102b5ed18e5ee402fd5a1a023c5d93c215dce6fd3f24d7efb4a9f6e08682b image_id=sha256:aeb24de31e2de444e767afe7bfbb8a70928c0527d8e6736bcb4813a5407fec7a repo_digest=eclipse/ditto-gateway@sha256:fc9102b5ed18e5ee402fd5a1a023c5d93c215dce6fd3f24d7efb4a9f6e08682b
identity egw-controller-1 image=egw-controller:0.1.0 image_id=sha256:9a293fe13b1a020560d43fee328632a9ef8d91dec830899f18d3e2d964aa5f46 repo_digest=none'

# gate_images_check: 0 only when the gate package of this session's open holds exactly six
# 'identity' lines and they equal S2's in the three compared fields. Non-zero, with WHY,
# otherwise - also when the package or its file cannot be read (a record that was not
# read is not a record that matches). Read-only.
gate_images_check() {
    local g f n got want
    g=$(state_get "$SESSION_FILE" gate_attempt)
    f=$g/environment/container_identities.txt
    [ -n "$g" ] && [ -s "$f" ] \
        || { WHY="the gate package's record of the running images could not be read (gate attempt '${g:-not recorded at open}', file environment/container_identities.txt)"; return 1; }
    echo "gate record: $f (sha256 $(sha_of "$f"))"
    n=$(grep -c '^identity ' "$f")
    got=$(sed -n 's/^\(identity [^ ]* image=[^ ]* image_id=[^ ]* repo_digest=[^ ]*\) container_id=[^ ]* started=[^ ]*$/\1/p' "$f" | LC_ALL=C sort)
    want=$(printf '%s\n' "$GATE_IDENTITIES_S2" | LC_ALL=C sort)
    printf '%s\n' "$got" | sed 's/^/  now: /'
    if [ "$n" != 6 ] || [ "$got" != "$want" ]; then
        printf '%s\n' "$want" | sed 's/^/  S2:  /'
        WHY="the gate package's record of the running images ($f: $n identity line(s)) differs from S2's in an image reference, an image id or a repo digest, or is not six lines of the recorded form"
        return 1
    fi
    echo "gate record: the image reference, the image id and the repo digest of the six containers equal S2's (container ids and start instants are not compared)"
}

# verify_row_files LABEL SLUG: the row's step files against rows.manifest.json.
verify_row_files() {
    local files
    files=$(row_files "$2")
    # shellcheck disable=SC2086
    manifest_tool verify "$MANIFEST" "$ROWS_DIR" "$1" "$2" $files
}

# plan_entry RUN_ID: prints the entry; 0 only when its status is 'planned'.
plan_entry() {
    "$PY" -c '
import json, sys
try:
    plan = json.load(open(sys.argv[1]))
except (OSError, ValueError) as exc:
    print("plan %s could not be read: %s" % (sys.argv[1], exc))
    sys.exit(1)
for r in plan.get("runs", []):
    if r.get("run_id") == sys.argv[2]:
        print("plan entry %s: status=%s seed=%s condition=%s duration_s=%s warmup_s=%s"
              % (sys.argv[2], r.get("status"), r.get("seed"), r.get("condition_id"), r.get("duration_s"), r.get("warmup_s")))
        sys.exit(0 if r.get("status") == "planned" else 1)
print("plan entry %s: NOT in the plan" % sys.argv[2])
sys.exit(1)' "$PLAN" "$1"
}

# fresh_itest ID...: none of the ids has a host artefact (the checks of g3_hostprep.sh).
fresh_itest() {
    local id f bad=0 this
    for id in "$@"; do
        this=0
        for f in "$P/$id" "$P/$id".* "$REPLAY/$id" "$RAWD/$id"; do
            [ ! -e "$f" ] || { echo "NOT FRESH: $f exists ($id)"; this=1; bad=1; }
        done
        [ "$this" -ne 0 ] || echo "fresh on the host: $id"
    done
    return "$bad"
}

# fresh_plan ID: the plan entry is 'planned' and left nothing on the host.
fresh_plan() {
    local id=$1 f bad=0
    plan_entry "$id" || bad=1
    for f in "$RAWD/$id" "$P/$id" "$P/$id".*; do
        [ ! -e "$f" ] || { echo "NOT FRESH: $f exists ($id)"; bad=1; }
    done
    [ "$bad" -ne 0 ] || echo "fresh on the host: $id (planned, no raw directory, no $P/$id.*)"
    return "$bad"
}

# fresh_row SLUG: every id of the row, and no earlier attempt of the row.
# S3 (point 9): for t8 exactly ONE earlier attempt is admitted, S2's halted one
# (T8_ADMITTED), where it is kept: in the WSL attempts directory and under
# output_test/runs/2026-10-03/. Any other earlier attempt of t8, that one found anywhere
# else, and any earlier attempt of t9, is NOT FRESH.
# S4 (point 5): the same rule for t6, S4's one row: exactly ONE earlier attempt is
# admitted, S2's invalid one (T6_ADMITTED), in the same two places; any other earlier
# attempt of t6, or that one found anywhere else, is NOT FRESH.
fresh_row() {
    local slug=$1 bad=0 h f
    # shellcheck disable=SC2046
    [ -z "$(row_fresh_ids "$slug")" ] || fresh_itest $(row_fresh_ids "$slug") || bad=1
    h=$(row_harness_id "$slug")
    [ -z "$h" ] || fresh_plan "$h" || bad=1
    for f in "$ATTEMPTS"/*_g3-qualification-"$slug"_attempt* "$OUT"/runs/*/*_g3-qualification-"$slug"_attempt* \
        "$OUT"/incomplete/*_g3-qualification-"$slug"_attempt*; do
        [ -e "$f" ] || continue
        if [ "$slug" = t6 ] && { [ "$f" = "$ATTEMPTS/$T6_ADMITTED" ] || [ "$f" = "$OUT/runs/2026-10-03/$T6_ADMITTED" ]; }; then
            echo "admitted: the one earlier attempt of row t6 (S2's invalid one, plan entry controller_restart-r03, kept as sealed): $f"
            continue
        fi
        if [ "$slug" = t8 ] && { [ "$f" = "$ATTEMPTS/$T8_ADMITTED" ] || [ "$f" = "$OUT/runs/2026-10-03/$T8_ADMITTED" ]; }; then
            echo "admitted: the one earlier attempt of row t8 (S2's halted one, kept as sealed): $f"
            continue
        fi
        echo "NOT FRESH: an earlier attempt of row $slug exists: $f"
        bad=1
    done
    return "$bad"
}

# keepalive_check NEED_S: a dedicated 'exec sleep <seconds>' client of wsl.exe (its
# parent is a WSL relay) with at least NEED_S left. The Windows side (the wsl.exe client
# itself, the keep-awake) cannot be seen from here and stays the operator's own check.
keepalive_check() {
    local need=$1 pid ppid secs et pcomm rem best=-1
    while read -r pid ppid secs; do
        case $secs in '' | *[!0-9]*) continue ;; esac
        [ "$secs" -ge 3600 ] || continue
        et=$(ps -o etimes= -p "$pid" 2> /dev/null | tr -d ' ')
        case $et in '' | *[!0-9]*) continue ;; esac
        pcomm=$(ps -o comm= -p "$ppid" 2> /dev/null)
        rem=$((secs - et))
        case $pcomm in
            Relay*) echo "keepalive: pid $pid 'sleep $secs', parent $ppid ($pcomm), running for $et s, about $rem s left" ;;
            *)
                echo "not a keepalive: pid $pid 'sleep $secs' has parent $ppid (${pcomm:-gone}), not a WSL relay"
                continue
                ;;
        esac
        [ "$rem" -le "$best" ] || best=$rem
    done < <(ps -eo pid=,ppid=,args= 2> /dev/null | awk '$3 == "sleep" && NF == 4 { print $1, $2, $4 }')
    if [ "$best" -lt "$need" ]; then
        echo "KEEPALIVE: no 'exec sleep' client of wsl.exe with at least $need s left (best: $best s; -1 = none)."
        echo "  Start one from Windows and leave it running (the stop-keepalive sentinel is not touched):"
        echo "    MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'exec sleep 43200'"
        return 1
    fi
    echo "keepalive: attached, about $best s left (needed: $need s). The Windows keep-awake stays the operator's own check."
}

# tunnel_now: 0 when the project's ssh master answers (runbook 5.7), read without the
# preamble of hx, which would reopen a tunnel that is down.
tunnel_now() {
    # shellcheck source=/dev/null
    (. "$HOME/egw-tcg/tunnel.sh" && tunnel_check)
}

# run_driver LABEL NAME: one frozen driver as a child bash, its console teed into the
# state directory. Returns the driver's own exit status.
DRIVER_CONSOLE=""
run_driver() {
    local label=$1 name=$2 out rc n=1
    out=$STATE/$label-$name.console.txt
    while [ -e "$out" ]; do      # a console is never overwritten: a later run gets its own
        n=$((n + 1))
        out=$STATE/$label-$name.console.$n.txt
    done
    DRIVER_CONSOLE=$out
    say "$name.sh (frozen driver, $REPO/tools/session/$name.sh; console $out)"
    bash "$REPO/tools/session/$name.sh" < /dev/null 2>&1 | tee_safe "$out"
    rc=${PIPESTATUS[0]}
    echo "$name.sh exit=$rc" | tee_safe "$out"
    state_set "$SESSION_FILE" "${name}_exit" "$rc"
    return "$rc"
}

# driver_run_id FILE: the run id on the driver's final 'DRIVER RESULT <run id>:' line.
driver_run_id() { sed -n 's/^DRIVER RESULT \([^: ]*\):.*/\1/p' "$1" | tail -n 1; }

# --- open -----------------------------------------------------------------------------
# environment_copy PREFLIGHT_ATTEMPT: PM condition 2 (operator procedure, "Environment
# input"). The old harness input is kept beside itself under its sha256, the preflight's
# labelled capture is copied in, and both hashes are printed. Non-zero: nothing usable.
environment_copy() {
    local new=$1/environment/sut_environment.json old_sha new_sha keep
    echo "## environment input (PM condition 2 of 2026-10-01)"
    [ -s "$new" ] || { echo "STOP: the preflight left no capture at $new"; return 1; }
    "$PY" -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except (OSError, ValueError) as exc:
    print("STOP: the capture could not be read: %s" % exc)
    sys.exit(1)
p, i = str(d.get("provider") or ""), str(d.get("instance_type") or "")
for k in ("captured_utc", "node", "provider", "region", "instance_type", "shared_vcpu_note"):
    print("  %s: %s" % (k, d.get(k)))
ok = "QEMU" in p and "TCG" in p and "ARM64 EMULATED" in i
print("labels: %s" % ("QEMU/TCG and ARM64 EMULATED are present" if ok
                      else "STOP: the capture does not carry the QEMU/TCG and ARM64 EMULATED labels"))
sys.exit(0 if ok else 1)' "$new" || return 1
    [ -f "$SUT_ENV" ] || { echo "STOP: the harness input $SUT_ENV does not exist: there is nothing to keep, and that is not the state the packet describes"; return 1; }
    old_sha=$(sha_of "$SUT_ENV") || { echo "STOP: $SUT_ENV could not be hashed"; return 1; }
    keep=$SUT_ENV.${old_sha:0:12}
    if [ -e "$keep" ]; then
        cmp -s "$SUT_ENV" "$keep" || { echo "STOP: $keep exists and differs from $SUT_ENV: never overwritten"; return 1; }
        echo "previous input already kept: $keep ($old_sha)"
    else
        cp -p "$SUT_ENV" "$keep" && cmp -s "$SUT_ENV" "$keep" || { echo "STOP: the previous input could not be kept as $keep"; return 1; }
        echo "previous input kept: $keep ($old_sha)"
    fi
    cp "$new" "$SUT_ENV" && cmp -s "$new" "$SUT_ENV" || { echo "STOP: the capture was not copied to $SUT_ENV"; return 1; }
    new_sha=$(sha_of "$SUT_ENV") || return 1
    echo "harness input now: $SUT_ENV sha256 $new_sha"
    echo "source: $new (preflight package $(basename "$1"))"
    state_set "$SESSION_FILE" sut_environment_previous_sha256 "$old_sha"
    state_set "$SESSION_FILE" sut_environment_previous_kept_as "$keep"
    state_set "$SESSION_FILE" sut_environment_sha256 "$new_sha"
    state_set "$SESSION_FILE" sut_environment_source "$new"
}

open_interrupted() {
    trap '' INT TERM HUP
    halt "open $LABEL was interrupted by a signal ($1); the driver that was running handled its own attempt. The session may be OPEN: read '$EXEC/current_session' and run 'status'"
    state_set "$SESSION_FILE" state halted
    exit 130
}

open_halt() {   # the session is used from here on: the state file stays
    halt "$*"
    state_set "$SESSION_FILE" state halted
    echo "The session state is 'halted' and nothing was closed. If '$EXEC/current_session' exists the guest is UP: decide, then run 'close'."
    exit 1
}

cmd_open() {
    local slug l f st expect rootfs listing id pre_id pre gate_id rc bad
    [ "$#" -eq 1 ] || refuse "usage: g3_battery.sh open S4"
    LABEL=$1
    # S3 (point 1): S3 only. S1 and S2 are the battery's sessions: nothing of them is re-run.
    # S4 (point 1): S4 only. S1, S2 (the battery's) and S3 (tests 8 and 9) are refused: their
    # authority is consumed and nothing of them is re-run.
    case $LABEL in
        S4) ;;
        S1 | S2) refuse "session $LABEL is a session of the battery of 2026-10-02/03, whose authority is consumed: nothing of S1 or S2 is re-run or replaced. This script opens S4 only: g3_battery.sh open S4" ;;
        S3) refuse "session S3 (tests 8 and 9, 2026-10-05) is closed and its authority is consumed: nothing of S3 is re-run or replaced. This script opens S4 only: g3_battery.sh open S4" ;;
        *) refuse "usage: g3_battery.sh open S4" ;;
    esac
    start_log "open-$LABEL"
    take_turn "open $LABEL"
    say "open $LABEL: steps script $SELF sha256 $(sha_of "$SELF")"
    echo "EGW_EXEC_REPO=$EGW_EXEC_REPO EXEC=$EXEC SESSION=${SESSION:-<none>} (the three values of the operator procedure); STATE=$STATE ROWS=$ROWS_DIR OUT=$OUT"

    # Refusals: nothing has been started and nothing is recorded.
    # S3 (point 1): the preconditions of S3 are no open session and no QEMU process (the two
    # refusals here) and the root file system at the expected value (a HALT of the checks
    # below). The battery's S2-only precondition (S1 ended without a halt) is gone with S2.
    # S4 (point 1): the same three preconditions for S4 (the root file system: ROOTFS_BEFORE_S4).
    [ ! -e "$EXEC/current_session" ] || refuse "a session is open ($EXEC/current_session names '${SESSION}')"
    [ ! -e "$STATE/session-$LABEL.env" ] || refuse "$STATE/session-$LABEL.env exists: session $LABEL was already opened (a session is opened once; after a halt Rui directs what happens next)"
    # shellcheck disable=SC2043
    for l in S4; do
        f=$STATE/session-$l.env
        [ -f "$f" ] || continue
        st=$(state_get "$f" state)
        [ "$st" = closed ] || refuse "session $l is recorded '$st', not closed ($f)"
    done
    qemu_procs > /dev/null
    case $? in
        1) ;;
        0) refuse "a qemu-system-aarch64 process is already running" ;;
        *) refuse "whether a qemu-system-aarch64 process is running could not be determined" ;;
    esac

    # Checks (request of 2026-10-05, section 5 item 1: S4 starts only if every identity matches).
    say "candidate identities"
    verify_candidate || { echo "HALT: $WHY (packet section 4, halt 6); nothing was started"; exit 1; }
    say "row files of $LABEL against $MANIFEST"
    for slug in $(session_rows "$LABEL"); do
        verify_row_files "$LABEL" "$slug" || { echo "HALT: the row files of $slug are not the manifest's; nothing was started"; exit 1; }
    done
    echo "rows.manifest.json sha256: $(manifest_tool sha "$MANIFEST" "$ROWS_DIR")"
    say "run ids of $LABEL unused on the host"
    bad=0
    for slug in $(session_rows "$LABEL"); do
        fresh_row "$slug" || bad=1
    done
    [ "$bad" -eq 0 ] || { echo "HALT: an id of $LABEL is not fresh on the host; nothing was started"; exit 1; }
    say "guest root file system before the boot"
    # S4 (point 1): the expected value is the one the close of S3's second opening recorded.
    expect=$ROOTFS_BEFORE_S4
    rootfs=$(sha_of "$ROOTFS_EXT4") || rootfs=unreadable
    echo "rootfs ext4: $rootfs  $ROOTFS_EXT4"
    echo "expected:    ${expect:-<not recorded>} (the value the close of S3's second opening recorded)"
    [ -n "$expect" ] && [ "$rootfs" = "$expect" ] || { echo "HALT: the guest root file system is not the expected one, or the expected value is not recorded (packet section 4, halt 6); nothing was started"; exit 1; }
    say "keepalive"
    keepalive_check "$KEEPALIVE_OPEN_S" || refuse "the keepalive client is not attached (see above); nothing was started"

    # From here on the session is used: the state file stays whatever happens.
    SESSION_FILE=$STATE/session-$LABEL.env
    read -r UP0 _ < /proc/uptime
    UP0=${UP0%.*}
    state_set "$SESSION_FILE" label "$LABEL"
    state_set "$SESSION_FILE" state opening
    state_set "$SESSION_FILE" up0 "$UP0"
    state_set "$SESSION_FILE" wsl_boot_id "$(wsl_boot_id)"
    state_set "$SESSION_FILE" opened_wall "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    state_set "$SESSION_FILE" exec_repo "$EGW_EXEC_REPO"
    state_set "$SESSION_FILE" exec "$EXEC"
    state_set "$SESSION_FILE" steps_script_sha256 "$(sha_of "$SELF")"
    state_set "$SESSION_FILE" rows_manifest_sha256 "$(manifest_tool sha "$MANIFEST" "$ROWS_DIR")"
    state_set "$SESSION_FILE" rootfs_before_boot "$rootfs"
    [ -z "${EGW_G3_RUI_GO:-}" ] || state_set "$SESSION_FILE" rui_go "$EGW_G3_RUI_GO"
    [ -e "$STATE/$LABEL-g3_battery.sh" ] || cp -p "$SELF" "$STATE/$LABEL-g3_battery.sh"
    [ -e "$STATE/$LABEL-rows.manifest.json" ] || cp -p "$MANIFEST" "$STATE/$LABEL-rows.manifest.json"
    say "UP0=$UP0 (whole seconds of /proc/uptime: the session clock of PM condition 3; no row starts at or after UP0 + $CUTOFF_S)"
    trap 'open_interrupted INT' INT
    trap 'open_interrupted TERM' TERM
    trap 'open_interrupted HUP' HUP

    run_driver "$LABEL" guest_session_open
    rc=$?
    SESSION=$(cat "$EXEC/current_session" 2> /dev/null || true)
    S=$SESSION
    [ -z "$SESSION" ] || state_set "$SESSION_FILE" session_attempt "$SESSION"
    [ "$rc" -eq 0 ] || open_halt "guest_session_open.sh exited $rc (0 is the only status that opens the session for the battery); see $DRIVER_CONSOLE"
    [ -n "$SESSION" ] && [ -d "$SESSION" ] || open_halt "guest_session_open.sh ended 0 but $EXEC/current_session names no session directory"

    run_driver "$LABEL" preflight
    rc=$?
    pre_id=$(driver_run_id "$DRIVER_CONSOLE")
    pre=$ATTEMPTS/$pre_id
    state_set "$SESSION_FILE" preflight_attempt "$pre"
    # S4 (point 3): no exception. The frozen preflight at 1fd9792 judges collector-duration on
    # the uptime bounds of the merged collector's own start: and stop: records; a preflight that
    # ends non-zero (collector-duration included) is a halt here, in the form of S3's first
    # opening, and test 6 is not run (request of 2026-10-05, section 5 item 1).
    [ "$rc" -eq 0 ] || open_halt "preflight.sh exited $rc; see $DRIVER_CONSOLE"
    [ -n "$pre_id" ] && [ -d "$pre" ] || open_halt "the preflight's attempt could not be named from its DRIVER RESULT line"

    environment_copy "$pre" 2>&1 | tee_safe "$STATE/$LABEL-environment-copy.txt"
    rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || open_halt "the environment copy of PM condition 2 failed (see $STATE/$LABEL-environment-copy.txt): the harness rows would not read the labelled capture"

    run_driver "$LABEL" gate_health
    rc=$?
    # S3 (point 4): the gate package is named in the session's state file, as the
    # preflight's is: 'row t8' compares its record of the running images with S2's.
    # S4 (point 6): in S4 it is 'row t6' that compares it.
    gate_id=$(driver_run_id "$DRIVER_CONSOLE")
    [ -z "$gate_id" ] || state_set "$SESSION_FILE" gate_attempt "$ATTEMPTS/$gate_id"
    [ "$rc" -eq 0 ] || open_halt "gate_health.sh exited $rc; see $DRIVER_CONSOLE"

    # One read-only listing of the guest's event directories (a step of the session
    # attempt): every id of this session must be unused on the guest as well.
    say "run ids of $LABEL unused on the guest (read-only listing)"
    gx "$S" g3-guest-events-listing "ls -1 /opt/egw/deployment/data/events"
    rc=$?
    listing=$(ls "$S"/console/*-g3-guest-events-listing.stdout.txt 2> /dev/null | tail -n 1)
    [ "$rc" -eq 0 ] && [ -n "$listing" ] || open_halt "the guest's event directories could not be listed (exit $rc)"
    bad=0
    for slug in $(session_rows "$LABEL"); do
        for id in $(row_fresh_ids "$slug") $(row_harness_id "$slug"); do
            if grep -qxF -- "$id" "$listing" || grep -qxF -- "$id.warmup" "$listing"; then
                echo "NOT FRESH on the guest: data/events/$id"
                bad=1
            else
                echo "fresh on the guest: $id"
            fi
        done
    done
    [ "$bad" -eq 0 ] || open_halt "an id of $LABEL has an event directory on the guest: it is not fresh (packet section 2)"

    trap - INT TERM HUP
    state_set "$SESSION_FILE" state open
    state_set "$SESSION_FILE" open_done_up "$(up_now)"
    say "session $LABEL is open: $SESSION"
    echo "Next: 'row $(session_rows "$LABEL" | cut -d' ' -f1)'. Keepalive and keep-awake stay attached for the whole session."
}

# --- row ------------------------------------------------------------------------------
console_of() { ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1; }

# no_stop STEP: 0 only when the step's console exists and holds no STOP: line. The row
# files of the chained rows hold no 'STOP:' text themselves, so the line 'set -v' echoes
# is never taken for one; where a file does hold it, only a line that STARTS with STOP:
# counts.
no_stop() {
    local f pattern='STOP:'
    f=$(console_of "$1")
    [ -n "$f" ] && [ -f "$f" ] || return 1
    ! grep -q 'STOP:' "$A/environment/$1.sh" || pattern='^STOP:'
    ! grep -q -- "$pattern" "$f"
}

add_src() {   # add_src KIND PATH GLOB ROLE
    if [ -n "$3" ]; then
        (cd "$REPO/src" && $LE add-source --attempt "$A" --kind "$1" --path "$2" --siblings-glob "$3" --role "$4")
    else
        (cd "$REPO/src" && $LE add-source --attempt "$A" --kind "$1" --path "$2" --role "$4")
    fi
}

# register_sources: what the row writes outside its attempt (host.md 4.3 item 3; the
# (e) sections of fam-A, fam-B and fam-C), registered BEFORE the row runs, so that an
# interrupted row is exported with whatever exists. A path never written is listed by
# the export as missing: that is a fact about the row, not an error of the export.
register_sources() {
    local id h
    for id in $(row_itest_ids "$ROW_SLUG"); do
        add_src simulator "$P/$id" "$id.*" "itest run $id: the simulator's directory with the fetched events.jsonl, and every $id.* sibling the helpers write (transcript, marker, metrics, twins, reconcile, copies, .sut/)" || return 1
    done
    h=$(row_harness_id "$ROW_SLUG")
    case $ROW_SLUG in
        t1-harness)
            add_src raw "$RAWD/$h" "" "harness run directory of the plan entry $h (sealed by the harness when valid)" || return 1
            add_src other "$P/$h.sut" "" "the Docker events recorder's start record of $h (and events-partial/ if the fetch did not keep the capture)" || return 1
            ;;
        t6)
            add_src raw "$RAWD/$h" "" "harness run directory of the plan entry $h (sealed by the harness when valid)" || return 1
            add_src simulator "$P/$h.config_identity.json" "$h.*" "the configuration identity read before the harness, the twin hook's write-once siblings and $h.sut/" || return 1
            ;;
        t4-replay)
            add_src other "$REPLAY/itest-dup-01-q1" "" "the replay's own output directory (sent_events.jsonl, manifest.json): replay-check reads it, no helper copies it" || return 1
            ;;
        t8)
            add_src other "$P/$T8_PREFIX.boot_id.pre" "$T8_PREFIX.*" "T8's prefix files: the boot id before the reboot, the running container ids before the reboot (containers.pre), the pre-reboot and post-reboot twin snapshots and every other $T8_PREFIX.* sibling the row writes" || return 1
            ;;
    esac
    return 0
}

# register_late: T9's artefacts, known only after the row. A refused connection writes
# no simulator directory, so only what exists is registered; the ACL probe's tag is a
# UTC stamp taken by the row itself.
LATE_DONE=0
register_late() {
    local id f sib now
    [ "$ROW_SLUG" = t9 ] && [ "$LATE_DONE" -eq 0 ] || return 0
    LATE_DONE=1
    for id in $T9_IDS; do
        if [ -e "$P/$id" ]; then
            add_src simulator "$P/$id" "$id.*" "T9: $id left a simulator directory - a connection was ACCEPTED" \
                || echo "WARNING: $P/$id could not be registered"
        else
            for sib in "$P/$id".*; do
                [ -e "$sib" ] || continue
                add_src simulator "$sib" "" "T9: the bounded broker log of $id and its fetch record (no simulator directory exists: the connection was refused)" \
                    || echo "WARNING: $sib could not be registered"
            done
        fi
    done
    for f in "$P"/itest-acl-*; do
        [ -e "$f" ] || continue
        grep -qxF -- "$f" "$STATE/row-t9.acl-before.txt" 2> /dev/null && continue
        add_src other "$f" "" "T9 (d)+(e): the ACL probe's evidence copied from the guest, or its /metrics reading before or after the probe" \
            || echo "WARNING: $f could not be registered"
    done
    if [ -f /tmp/wrong.crt ]; then
        now=$(sha_of /tmp/wrong.crt) || now=""
        if [ -n "$now" ] && [ "$now" != "$(cat "$STATE/row-t9.wrongcrt-before.txt" 2> /dev/null)" ]; then
            add_src other /tmp/wrong.crt "" "T9 (a): the throwaway wrong CA certificate this row generated (its private key /tmp/wrong.key is NOT exported)" \
                || echo "WARNING: /tmp/wrong.crt could not be registered"
        fi
    fi
}

# run_step STEP [CARRIER]: one hx exec whose shell sources $A/environment/STEP.sh. 0 when
# the step ran (whatever the status of its last line: never a verdict); 1 after a HALT
# (97: the preamble or the tunnel never loaded, nothing ran; 74: its console capture was
# lost). CARRIER (T8 only): the assignment, such as T8=rebooted, that the runbook's lines
# leave in ONE shell for the next line to read (test 8's chain: a leaves rebooting, b
# rebooted, c returned, d reconnected, e ok; each line advances it only on success); the
# row files are one host$ line each, each sourced in its own shell, so the steps script
# sets it to the value the step before LEFT, from that step's record (no STOP:, the line
# the runbook names), as the runbook's own comment on T8 says a driver must, and prints
# that it did.
run_step() {
    local step=$1 carrier=${2:-} rc
    row_set state running
    row_set step "$step"
    row_set pgid "$(own_pgid)"
    row_set pgid_start "$(proc_start "$(own_pgid)")"
    row_set step_started_up "$(up_now)"
    say "row $ROW_SLUG: step $step (hx: one shell, the row file is sourced${carrier:+; carrier set from the record of the step before: $carrier})"
    hx "$A" "$step" "$STEP_PRE; ${carrier:+$carrier; echo \"carrier set by the steps script from the record of the step before: $carrier\"; }. '$A/environment/$step.sh'"
    rc=$?
    state_add "$ROW_FILE" step_done "$step exit=$rc up=$(up_now)"
    say "row $ROW_SLUG: step $step ended; hx status $rc (the status of its last line; never a verdict)"
    case $rc in
        "$EXIT_NOT_REACHED")
            halt "row $ROW_SLUG: step $step answered 97: the host preamble of runbook 6.1 (venv, secrets, helpers, tunnel) did not load, the step never ran (packet section 4, halt 2)"
            return 1
            ;;
        "$EXIT_CAPTURE_LOST")
            halt "row $ROW_SLUG: step $step answered 74: its console capture was lost (packet section 4, halt 2); the step's own status is in commands.jsonl"
            return 1
            ;;
    esac
    return 0
}

# recorded NAME CMD...: one extra recorded step (ex); prints and returns its status.
snapshot() {   # snapshot LABEL plan|both
    row_set step "snapshot-$1"
    ex "$A" "snapshot-$1" bash -c "$SNAPSHOT" _ "$A" "$1" "$2" "$PLAN" "$PROCESSED"
}

# --- T8: the in-process reboot (procedure corrected after S2 of 2026-10-03) -------------
# The launcher runs QEMU without -no-reboot: 'sudo systemctl reboot' (step a) reboots the
# guest INSIDE the same qemu-system-aarch64 process, which never exits and is never
# re-launched. Between step a and step b this script only WAITS, read-only, for the
# rebooted guest to answer over ssh (t8_wait_ssh, on the row's attempt: every poll is a
# recorded step, bounded by the host's 'timeout'; nothing is signalled; a QEMU exit,
# another process or none is a STOP of t8-qemu-after, and a re-launch through 3.3 is a
# recorded operator decision, never automatic). Steps b to f are hx steps, each only if
# the one before printed no STOP: and showed what the runbook line names; a STOP in b, c,
# d or e is a halt (T9 is not started). S3 (point 8): step f, the fresh timed smoke, is a
# halt as well unless its console shows the helper's 'TEST STATUS <id>: ... PROCEDURE
# COMPLETE' line and no STOP:; with that line and no STOP: the values the smoke printed
# (lost, late_confirmations) are the operator's classification, never a halt.
# S3 (condition B of the decision summary): after the reboot this script starts,
# restarts and recreates nothing on the guest - it holds no 'compose up', 'start' or
# 'restart' and no 'docker start' - so that the containers' return (line c) is unaided.
# Line d's tunnel step and the close's stop are the prescribed ones, and are not a
# recovery of the containers.
T8_ANSWERED=0
T8_WAIT_WHY=""

# S3 (point 6): the command of ONE poll of the wait. gx (guest_common.sh) is a shell
# function, which the host's 'timeout' cannot run. What gx records through ex is
# 'env E=<session> bash -c <text> _ <guest command>'; the wait records the same command,
# through the same ex, with 'timeout <seconds>' in front of it. The text below is gx's
# own, character for character (guest_common.sh, lines 49-50): the session's ssh helpers
# are loaded (97 when they cannot be) and gssh runs the guest command.
T8_POLL_SH='. "$E/scripts/session_common.sh" || { echo "STOP: the session ssh helpers ($E/scripts/session_common.sh) could not be loaded: NOTHING was run on the guest" >&2; exit 97; }
gssh "$1"'
# The kernel's form of a boot id (/proc/sys/kernel/random/boot_id): a UUID in lower case.
T8_BOOT_ID_RE='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

# t8_wait_ssh PRE_ID T0: the wait before line b (S3, point 6; decision summary, condition
# A). It polls 'cat /proc/sys/kernel/random/boot_id' on the guest, one poll every
# T8_SSH_POLL_S s, for at most T8_SSH_WAIT_S s measured on /proc/uptime (whole seconds,
# as the whole session is) from T0, the instant step a ended.
#   - EVERY poll is one recorded step of the row's attempt (ex, name t8-wait-ssh) and is
#     run by the host's 'timeout' with a duration of min(T8_SSH_READ_S, what is left of
#     the budget) seconds: never 0, never without 'timeout'. With less than 1 s left no
#     further poll is made: the wait has expired.
#   - A poll COUNTS only when it ended with exit status 0 AND its whole answer is one
#     boot id of the kernel's form AND that id is not PRE_ID, the one step a saved. A poll
#     that printed such an id and then ended 124 (the timeout), 255 (ssh) or any other
#     non-zero status is no answer whatever it printed: it is said so, its console stays
#     in the attempt as the recorded step it is, and the wait goes on. This is the rule of
#     the merged line b, not a weaker one.
#   - 0 as soon as a poll counts: the hx preamble of step b (tunnel_check || tunnel_up)
#     then reaches the REBOOTED guest's sshd, not the one that is going down. An answer
#     with the saved id is printed and the wait goes on (the guest has not gone down yet,
#     or did not reboot); step b, the runbook's own line, judges and records REBOOT SHOWN.
#   - 1 when the budget is spent: T8_WAIT_WHY says 'reboot not shown' within the wait
#     (inconclusive / not demonstrated: an operational cut-off, not by itself a failure
#     of the system), and line b is not run.
#   - 74 at once when a poll's console capture was lost: a halt of its own.
#   - 3, before any poll, when PRE_ID is not a boot id: nothing could be compared with it.
# Nothing here writes the row's start instant or its ceiling: the wait, what ran before
# it and the steps after it share the row's ceiling, counted from the row's start.
t8_wait_ssh() {
    local pre=$1 t0=$2 now left d s n=0 n_none=0 n_same=0 n_other=0 last="no poll was made" rc id f prev="" start ceiling
    row_set step t8-wait-ssh
    now=$(up_now)
    if ! [[ $pre =~ $T8_BOOT_ID_RE ]]; then
        T8_WAIT_WHY="the boot id step a saved ($P/$T8_PREFIX.boot_id.pre) is not a boot id of the kernel's form ('$pre'), although step a printed no STOP: - no answer of the guest can be compared with it, so no poll was made (invalid instrumentation; packet section 4, halt 2)"
        return 3
    fi
    # Read, never written: the row's start instant and its ceiling stay what 'row' recorded.
    start=$(state_get "$ROW_FILE" start_up)
    ceiling=$(state_get "$ROW_FILE" ceiling_min)
    state_add "$ROW_FILE" t8_wait "started up=$now, $((now - t0)) s after step a ended (up=$t0); budget $T8_SSH_WAIT_S s from that instant; the row's start (up=$start) and its ceiling ($ceiling min) are not reset"
    say "row t8: waiting at most $T8_SSH_WAIT_S s from the end of step a (up=$t0) for the guest to answer over ssh with a boot id other than the saved one $pre (read-only polls every $T8_SSH_POLL_S s, each a recorded step bounded by 'timeout' to $T8_SSH_READ_S s or to what is left; QEMU is never signalled; nothing is re-launched or started). The row's ceiling of $ceiling min keeps counting from the row's start (up=$start): $(((now - ${start:-$now}) / 60)) min of it are used"
    while :; do
        now=$(up_now)
        left=$((T8_SSH_WAIT_S - (now - t0)))
        if [ "$left" -lt 1 ]; then
            T8_WAIT_WHY="reboot not shown within the wait: in the $T8_SSH_WAIT_S s after step a ended, none of the $n poll(s) both ended with exit status 0 and answered a boot id of the kernel's form other than the saved pre-reboot id $pre ($n_none ended with another status - no answer, whatever they printed; $n_same answered the saved id; $n_other ended 0 without one boot id as the answer); the last poll: $last. An operational cut-off: inconclusive / not demonstrated, not by itself a failure of the system (decision summary, choice 3; packet section 4, halt 5)"
            return 1
        fi
        d=$T8_SSH_READ_S
        [ "$left" -ge "$d" ] || d=$left
        n=$((n + 1))
        ex "$A" t8-wait-ssh timeout "$d" env E="$SESSION" bash -c "$T8_POLL_SH" _ "cat /proc/sys/kernel/random/boot_id"
        rc=$?
        now=$(up_now)
        if [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
            T8_WAIT_WHY="poll $n of the wait answered 74: its console capture was lost, so what the guest answered is not on record (invalid instrumentation; packet section 4, halt 2)"
            return "$EXIT_CAPTURE_LOST"
        fi
        # The poll's own console: a new file for every poll (a file already read belongs
        # to an earlier poll and is never read again as this one's answer).
        f=$(console_of t8-wait-ssh)
        id=""
        [ -z "$f" ] || [ "$f" = "$prev" ] || id=$(cat "$f" 2> /dev/null)
        prev=$f
        [[ $id =~ $T8_BOOT_ID_RE ]] || id=""
        if [ "$rc" -eq 0 ] && [ -n "$id" ] && [ "$id" != "$pre" ]; then
            echo "poll $n at +$((now - t0)) s (bounded to $d s): exit status 0 and the answer is the boot id $id, not the saved pre-reboot id $pre: the guest answers from another boot (step b judges and records the reboot)"
            state_add "$ROW_FILE" t8_ssh_answered "poll=$n at=+$((now - t0))s up=$now boot_id=$id"
            return 0
        fi
        if [ "$rc" -ne 0 ]; then
            n_none=$((n_none + 1))
            last="exit status $rc (124: ended by its timeout of $d s; 255: ssh did not connect or lost its connection; 97: the session's ssh helpers were not loaded)"
            if [ -n "$id" ] && [ "$id" != "$pre" ]; then
                last="$last after printing the boot id $id, which is NOT counted"
                echo "poll $n at +$((now - t0)) s (bounded to $d s): NOT counted - it printed the boot id $id, other than the saved one, and then ended with exit status $rc: a read that does not end with exit status 0 is no answer whatever it printed (kept as a diagnostic: $f) - waiting on"
            else
                echo "poll $n at +$((now - t0)) s (bounded to $d s): no answer (exit status $rc; 124: ended by its timeout; 255: ssh did not connect or lost its connection) - waiting on"
            fi
        elif [ -n "$id" ]; then
            n_same=$((n_same + 1))
            last="answered the saved id (reboot not shown)"
            echo "poll $n at +$((now - t0)) s (bounded to $d s): the guest answers with the boot id $id, the saved pre-reboot id: it has not gone down yet, or did not reboot - waiting on"
        else
            n_other=$((n_other + 1))
            last="exit status 0, but the answer is not one boot id of the kernel's form"
            echo "poll $n at +$((now - t0)) s (bounded to $d s): exit status 0, but the answer is not one boot id of the kernel's form (see the step's console: $f) - NOT counted, waiting on"
        fi
        left=$((T8_SSH_WAIT_S - (now - t0)))
        [ "$left" -ge 1 ] || continue
        s=$T8_SSH_POLL_S
        [ "$left" -ge "$s" ] || s=$left
        sleep "$s"
    done
}

# t8_qemu before|after: the recorded QEMU process reading (T8_QEMU_IDENT); 'before' keeps
# the pid, start instant and disks in T8_QEMU_* for 'after' to compare with.
# S3 (point 5): 'before' returns 3 when the reading found -no-reboot on the command line.
T8_QEMU_PID=""
T8_QEMU_START=""
T8_QEMU_DISKS=""
t8_qemu() {
    local rc line
    row_set step "t8-qemu-$1"
    if [ "$1" = before ]; then
        ex "$A" t8-qemu-before bash -c "$T8_QEMU_IDENT" _ before "$QEMU_EXE_RE"
        rc=$?
        if [ "$rc" -eq 3 ]; then
            row_set t8_qemu_before "exit=3: -no-reboot (or its equivalent) is on the command line of the QEMU process"
            return 3
        fi
        line=$(sed -n 's/^QEMU PROCESS: pid=\([0-9][0-9]*\) start=\([0-9][0-9]*\) disks=\(.*\)$/\1 \2 \3/p' "$(console_of t8-qemu-before)" 2> /dev/null | tail -n 1)
        [ "$rc" -eq 0 ] && [ -n "$line" ] || return 1
        read -r T8_QEMU_PID T8_QEMU_START T8_QEMU_DISKS <<< "$line"
        row_set t8_qemu_before "pid=$T8_QEMU_PID start=$T8_QEMU_START disks=$T8_QEMU_DISKS"
        return 0
    fi
    ex "$A" t8-qemu-after bash -c "$T8_QEMU_IDENT" _ after "$QEMU_EXE_RE" "$T8_QEMU_PID" "$T8_QEMU_START" "$T8_QEMU_DISKS"
    rc=$?
    row_set t8_qemu_after "exit=$rc (0: the same process and disks as before step a)"
    return "$rc"
}

# t8_shown STEP PATTERN: 0 when the step's console holds no STOP: and a line matching
# PATTERN (anchored at the line start, so that the line 'set -v' echoes - the row file's
# own text, which holds the echo of that marker - is never taken for the marker).
t8_shown() {
    no_stop "$1" && grep -Eq "$2" "$(console_of "$1")"
}

steps_t8() {
    local run1 rc qrc pre_id a_end missing smoke f
    run1=$(cat "$SESSION/.current_run" 2> /dev/null)
    row_set t8_run "$run1"
    if [ -z "$run1" ] || [ -e "$SESSION/boot/$run1.status" ]; then
        halt "row t8: the session's boot records are not those of a boot still running (.current_run='$run1'; boot/$run1.status exists: that QEMU exited): step a was NOT run"
        return
    fi
    # S3 (point 6): the wait after step a, and the runbook's lines b and c, bound every
    # read with the host's 'timeout'. Without it the reboot is not issued.
    if ! command -v timeout > /dev/null 2>&1; then
        halt "row t8: the host's 'timeout' is not on PATH: the wait after step a and lines b and c bound every read with it. Step a was NOT run: the reboot was NOT issued (class: not started)"
        return
    fi
    say "row t8: the QEMU process before step a (recorded: pid, start instant, disks; its command line read for -no-reboot)"
    t8_qemu before
    case $? in
        0) ;;
        3)
            # S3 (point 5): halt before the reboot is issued; line a is not run.
            halt "row t8: -no-reboot (or its equivalent) is on the command line of the running QEMU process (step t8-qemu-before): with it QEMU exits at a guest reboot instead of rebooting inside the same process, which is not the procedure of test 8. Step a was NOT run: the reboot was NOT issued (class: not started; request of 2026-10-04, section 5 item 4). Nothing was signalled, and T9 is not run"
            return
            ;;
        *)
            halt "row t8: one qemu-system-aarch64 process could not be recorded before step a, or its command line could not be read (t8-qemu-before; packet section 4, halt 6): step a was NOT run"
            return
            ;;
    esac
    run_step t8-a-reboot || return
    a_end=$(up_now)     # S3 (point 6): the instant step a ended, from which the wait's budget counts
    if ! no_stop t8-a-reboot; then
        halt "row t8: step a printed STOP: (no pre-reboot /metrics reading or snapshot, no boot id, not six running containers, no event directory or no mount source) - the guest was NOT rebooted, and nothing further of T8 was run"
        return
    fi
    pre_id=$(cat "$P/$T8_PREFIX.boot_id.pre" 2> /dev/null)
    t8_wait_ssh "$pre_id" "$a_end"
    rc=$?
    # The QEMU process after the wait, whatever the wait answered: a reading for the
    # record in either case, and the comparison with the process recorded before step a.
    say "row t8: the QEMU process after the wait (recorded and compared with the reading before step a)"
    t8_qemu after
    qrc=$?
    if [ "$rc" -ne 0 ]; then
        # S3 (point 6): the wait expired ("reboot not shown" within the wait), a poll's
        # capture was lost (74), or the saved id could not be compared: T8_WAIT_WHY says
        # which. Line b is not run in any of them.
        halt "row t8: $T8_WAIT_WHY. Line b was NOT run, nor steps c to f, and T9 is not run. QEMU was NOT signalled and is NOT killed, and nothing is re-launched, started or restarted (a re-launch through 3.3 is a recorded operator decision, never automatic: the data disk is at stake); its reading after the wait is the step t8-qemu-after (exit $qrc)"
        return
    fi
    if [ "$qrc" -ne 0 ]; then
        halt "row t8: the qemu-system-aarch64 process after the wait is not the one recorded before step a, or none could be shown (t8-qemu-after exit $qrc; packet section 4, halt 5): the guest did not reboot inside the same QEMU process, or another launcher ran. Nothing was signalled and nothing is re-launched; steps b to f were NOT run, and T9 is not run"
        return
    fi
    T8_ANSWERED=1
    run_step t8-b-wait-boot-id T8=rebooting || return
    if ! t8_shown t8-b-wait-boot-id '^REBOOT SHOWN: boot id [0-9a-f-]+ -> [0-9a-f-]+'; then
        halt "row t8: step b does not show REBOOT SHOWN with no STOP: (the guest never answered within its bound, or kept answering the saved boot id; packet section 4, halt 5): steps c to f were NOT run, and T9 is not run"
        return
    fi
    run_step t8-c-unaided T8=rebooted || return
    # S3 (point 7): the merged line c prints TWO markers, each at the start of a line, and
    # sets T8=returned only after both: the container set, then the event directories and
    # the mount source of /var/lib/docker. Both are required, with no STOP:; the halt
    # names what is missing.
    f=$(console_of t8-c-unaided)
    missing=""
    no_stop t8-c-unaided || missing="a STOP: line was printed (or the step left no console)"
    grep -q '^CONTAINERS RETURNED UNAIDED' "$f" 2> /dev/null || missing="${missing:+$missing; }no line CONTAINERS RETURNED UNAIDED"
    grep -q '^PERSISTENCE SHOWN' "$f" 2> /dev/null || missing="${missing:+$missing; }no line PERSISTENCE SHOWN"
    if [ -n "$missing" ]; then
        halt "row t8: step c does not show both CONTAINERS RETURNED UNAIDED and PERSISTENCE SHOWN with no STOP: - $missing (the six container objects running before the reboot are not all running again by themselves, an event directory or the mount source of /var/lib/docker is not as before the reboot, or a judged read did not end with exit status 0; packet section 4, halt 5). This script runs no 'compose up' and no 'start': steps d to f were NOT run, and T9 is not run"
        return
    fi
    run_step t8-d-tunnel T8=returned || return
    if ! no_stop t8-d-tunnel; then
        halt "row t8: step d printed STOP: (tunnel NOT reopened; packet section 4, halt 6): steps e and f were NOT run, and T9 is not run"
        return
    fi
    row_set step t8-tunnel-check
    ex "$A" t8-tunnel-check bash -c '. "$HOME/egw-tcg/tunnel.sh" && tunnel_check && echo "TUNNEL CHECK: the master answers on $TUNNEL_SOCK"'
    rc=$?
    if [ "$rc" -ne 0 ]; then
        halt "row t8: the tunnel is not up after step d (tunnel_check exit $rc): step e (its wait_ready 3600 would poll a dead port) and step f were NOT run, and T9 is not run"
        return
    fi
    run_step t8-e-state T8=reconnected || return
    # S3 (bounded check of 2026-10-05, O2): after line d only the preamble of hx can print
    # 'TUNNEL UP' (no later step line calls tunnel_up): the tunnel line d reopened and the
    # check above confirmed was lost and restored - a halt (request, section 5, items 7, 9).
    if grep -q '^TUNNEL UP$' "$(console_of t8-e-state)" 2> /dev/null; then
        halt "row t8: the preamble of hx reopened a lost tunnel before step e (TUNNEL UP in its console; request, section 5, items 7 and 9): step f was NOT run, and T9 is not run"
        return
    fi
    if ! no_stop t8-e-state; then
        halt "row t8: step e printed STOP: (stack not ready, the post-reboot snapshot, 'same' or the controller's new process not shown; packet section 4, halt 5): step f, the post-reboot smoke, was NOT run, and T9 is not run"
        return
    fi
    run_step t8-f-smoke T8=ok || return
    # The key keeps its meaning: step f, the smoke line, was reached and ran.
    row_set t8_reached_smoke "yes (step f, the post-reboot smoke, was reached; whether T9 may start: the smoke's halt rule below, this row's gate and its classification)"
    # S3 (point 8; request of 2026-10-04, section 5 item 5): a halt unless the smoke's
    # console shows the helper's status line of a completed procedure - sim_post's
    # 'TEST STATUS <id>: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE
    # COMPLETE. ...' (runbook line 881), at the start of a line - and no STOP:. With that
    # line and no STOP: nothing is halted here, whatever lost and late_confirmations read:
    # a value above 0 is a failure of T8 that the operator classifies, after which T9 may
    # start with this row's gate passed.
    smoke=$(row_itest_ids t8)
    f=$(console_of t8-f-smoke)
    if grep -q '^TUNNEL UP$' "$f" 2> /dev/null; then   # S3 (O2), as after step e
        row_set t8_smoke "halt: the preamble of hx reopened a lost tunnel before the smoke"
        halt "row t8: the preamble of hx reopened a lost tunnel before step f (TUNNEL UP in its console; request, section 5, items 7 and 9): T9 is not run; the row is classified by what its consoles show"
        return
    fi
    if ! no_stop t8-f-smoke; then
        row_set t8_smoke "halt: a STOP: line in the smoke's console"
        halt "row t8: step f, the post-reboot smoke $smoke, printed STOP: (or left no console): its procedure did not complete (request of 2026-10-04, section 5 item 5). T9 is not run; the row is classified by the cause its console shows"
        return
    fi
    if ! grep -Eq "^TEST STATUS $smoke: .* -> PROCEDURE COMPLETE\." "$f" 2> /dev/null; then
        row_set t8_smoke "halt: no 'TEST STATUS $smoke: ... -> PROCEDURE COMPLETE' line in the smoke's console"
        halt "row t8: step f printed no STOP: but its console does not show the line 'TEST STATUS $smoke: ... -> PROCEDURE COMPLETE': the smoke is not shown to have completed its procedure (request of 2026-10-04, section 5 item 5). T9 is not run; the row is classified by the cause its console shows"
        return
    fi
    row_set t8_smoke "procedure complete: 'TEST STATUS $smoke: ... -> PROCEDURE COMPLETE' and no STOP: (not a verdict)"
    echo "row t8: step f shows 'TEST STATUS $smoke: ... -> PROCEDURE COMPLETE' and no STOP: - this script records no halt for the smoke. That is NOT a verdict: lost and late_confirmations are read by the operator, and a value above 0 is a classified FAILURE of T8, not a halt (T9 may then start, with this row's gate passed)"
}

# The evidence-only reads of the packet's execution choices for T8: the previous boot's
# journal and its kernel OOM lines. Read-only, after the row's own steps.
# S3 (point 10): unchanged, as is the gate's rule for T8 in gate_after (the guest state
# after the row is recorded and compared with nothing across the reboot). The operator
# reads both before T8 is classified: an OOM kill found in either, or a restart after the
# reboot, is a halt of the operator's own (this script records none for it).
t8_evidence() {
    row_set step t8-previous-boot-journal
    gx "$A" t8-previous-boot-journal "sudo -n journalctl -b -1 --no-pager" \
        || echo "the previous boot's journal was not read (evidence only)"
    gx "$A" t8-previous-boot-oom "sudo -n journalctl -b -1 -k --no-pager | grep -i -E 'oom|killed process' || echo 'no oom or killed-process line in the previous boot kernel journal'" \
        || echo "the previous boot's kernel journal was not read (evidence only)"
}

steps_t9() {
    local st prev=""
    for st in t9-a t9-b t9-c t9-de t9-exposure; do
        if [ -n "$prev" ] && ! no_stop "$prev"; then
            say "row t9: step $prev printed STOP: (or left no console): $st and every later step were NOT run (runbook line 15)"
            state_add "$ROW_FILE" step_not_run "$st and later: $prev printed STOP:"
            return
        fi
        run_step "$st" || return
        # S3 (bounded check of 2026-10-05, O2): no line of test 9 calls tunnel_up, so a
        # 'TUNNEL UP' is the preamble of hx restoring a lost tunnel - a halt (request,
        # section 5, items 7 and 9); no later step of T9 is run.
        if grep -q '^TUNNEL UP$' "$(console_of "$st")" 2> /dev/null; then
            halt "row t9: the preamble of hx reopened a lost tunnel before step $st (TUNNEL UP in its console; request, section 5, items 7 and 9): every later step of T9 was NOT run"
            return
        fi
        prev=$st
    done
}

run_row_steps() {
    case $ROW_SLUG in
        t1-harness)
            snapshot before both || { halt "row t1-harness: the plan and processed/ could not be copied before the harness (snapshot exit $?): the harness step was NOT run"; return; }
            run_step t1-harness || return
            snapshot after-harness plan || halt "row t1-harness: the plan could not be copied after the harness step"
            if no_stop t1-harness; then
                run_step t1-harness-analyze || return
            else
                say "row t1-harness: the harness step printed STOP: - the analyze step was NOT run (runbook line 15)"
                state_add "$ROW_FILE" step_not_run "t1-harness-analyze: t1-harness printed STOP:"
            fi
            snapshot after both || halt "row t1-harness: the plan and processed/ could not be copied after the row"
            ;;
        t6)
            # S4 (point 8): the battery's t6 path, unchanged. The one step sources t6.sh (the
            # eight lines 1421-1428 of the runbook at 1fd9792); the snapshots before and after
            # show the plan entry's status as the harness rewrites it (run.py update_plan_status:
            # 'running', then 'completed' or 'failed' with result_dir, finished_utc and
            # validity) and processed/ as line 1428's analyze rewrites it.
            snapshot before both || { halt "row t6: the plan and processed/ could not be copied before the harness (snapshot exit $?): the row's step was NOT run"; return; }
            run_step t6 || return
            snapshot after both || halt "row t6: the plan and processed/ could not be copied after the row"
            ;;
        t8) steps_t8 ;;
        t9) steps_t9 ;;
        *) run_step "$ROW_SLUG" || return ;;
    esac
}

# delta_counts FILE: 'N M' from the summary line guest_state_delta.py prints last.
delta_counts() {
    [ -n "${1:-}" ] && [ -f "$1" ] || return 0
    tail -n 1 "$1" | sed -n 's/^guest-state-delta: faults=\([0-9][0-9]*\) problems=\([0-9][0-9]*\)$/\1 \2/p'
}

# gate_after: the gate inside each attempt (operator procedure). Fills GATE_BAD with
# every part that did not pass; an empty list is a passed gate.
GATE_BAD=()
BEFORE=""
gate_after() {
    local rc after restarted counts args
    row_set state gate
    row_set step gate
    say "row $ROW_SLUG: the gate after the row"
    gx "$A" guest-state-after "$GUEST_STATE"
    rc=$?
    [ "$rc" -eq 0 ] || GATE_BAD+=("the guest state after the row was not recorded (guest-state-after exit $rc)")
    after=$(console_of guest-state-after)
    if [ "$ROW_SLUG" = t8 ]; then
        echo "gate: no guest-state comparison for T8 (the reboot replaces every start instant; packet section 3)"
    elif [ -n "$BEFORE" ] && [ -n "$after" ]; then
        args=(--expect "$EXPECT_SERVICES")
        restarted=$(row_restarted "$ROW_SLUG")
        [ -z "$restarted" ] || args+=(--expect-restarted "$restarted")
        ex "$A" guest-state-delta "$PY" "$DRIVERS/guest_state_delta.py" "${args[@]}" "$BEFORE" "$after"
        rc=$?
        counts=$(delta_counts "$(console_of guest-state-delta)")
        case "$rc:$counts" in
            "0:0 0") ;;
            0:* | 1:* | 2:*) GATE_BAD+=("guest-state-delta exit $rc (faults and problems: ${counts:-no summary line}): an OOM kill, an unexpected restart or replacement, an expected restart the pair does not show, or a pair that could not be compared") ;;
            *) GATE_BAD+=("guest-state-delta exit $rc: the comparison itself was not made") ;;
        esac
    else
        GATE_BAD+=("no pair of guest states to compare")
    fi
    healthy_wait "$A" gate-healthy "$GATE_HEALTHY_S" 15
    rc=$?
    [ "$rc" -eq 0 ] || GATE_BAD+=("the six services were not all running and healthy within $GATE_HEALTHY_S s (gate-healthy exit $rc: 1 not healthy, 2 not determined, 4 both, 97 the guest did not answer)")
    gx "$A" gate-units "$(units_script)"
    rc=$?
    case $rc in
        0) ;;
        3) GATE_BAD+=("a recorder or collector unit is still active (gate-units exit 3): a restoration is needed (the runbook's own cleanup, by the operator)") ;;
        *) GATE_BAD+=("whether a recorder or collector unit is active was not determined (gate-units exit $rc)") ;;
    esac
    hx "$A" gate-tunnel-check 'tunnel_check && echo "TUNNEL CHECK: the master answers on $TUNNEL_SOCK"'
    rc=$?
    [ "$rc" -eq 0 ] || GATE_BAD+=("tunnel_check through hx ended $rc")
    # The preamble of hx reopens a tunnel that is down before the check runs: say so.
    # S3 (bounded check of 2026-10-05, O2): that reopening is a restoration of a lost tunnel
    # (request, section 5, items 7 and 9): the gate fails, so a halt is recorded and no
    # further row starts. S4 (point 1): the same in S4; only the label in the note changed.
    if grep -q '^TUNNEL UP$' "$(console_of gate-tunnel-check)" 2> /dev/null; then
        echo "NOTE: the tunnel was DOWN after the row and the preamble of hx reopened it (TUNNEL UP in the gate's console): a restoration, and a halt (S4 as S3)"
        row_set gate_tunnel "found down after the row and reopened by the preamble of hx"
        GATE_BAD+=("the tunnel was found down after the row and reopened by the preamble of hx (request, section 5, items 7 and 9)")
    fi
}

# wait_group SECONDS: after a TERM, let what is left of the row's process group end by
# itself (T7's fault job restores its service from its trap). Nothing is signalled. The
# last reading of the group is kept beside the row's state file.
wait_group() {
    local limit=$1 t0 pgid list=$STATE/row-$ROW_SLUG.group-after-signal.txt left pids
    pgid=$(own_pgid)
    t0=$(up_now)
    while :; do
        # The reading itself is pgrep alone, pids only (a filter in the same pipeline would
        # be a member of this very group); the command lines are then read for those pids
        # and kept only with the password hidden (mask_argv).
        pgrep -g "$pgid" > "$list" 2> /dev/null
        mapfile -t pids < "$list"
        [ "${#pids[@]}" -eq 0 ] \
            || ps -o pid=,args= -p "$(IFS=,; echo "${pids[*]}")" 2> /dev/null | sed 's/^ *//' | mask_argv > "$list"
        left=$(grep -v -e "^$$ " -e "^${TEE_PID:-none} " "$list" | cut -c1-90 | tr '\n' ';')
        [ -n "$left" ] || break
        if [ $(($(up_now) - t0)) -ge "$limit" ]; then
            echo "still in the row's process group after $limit s (left as they are, NOT signalled): $left"
            break
        fi
        echo "waiting for the row's processes to end by themselves: $left"
        sleep 5
    done
}

# on_signal NAME: INT, TERM or HUP during a row. The frozen driver_interrupt behaviour:
# the attempt is finished 'interrupted' and exported, and the row ends here.
A=""
on_signal() {
    local rc
    trap '' INT TERM HUP
    # A TERM sent to the whole group also ends the session's leader, which hangs the
    # session up: the signal named here is the first one bash delivered, often HUP.
    say "row $ROW_SLUG: interrupted by a signal ($1)"
    if [ -z "$A" ]; then
        echo "no attempt existed yet: nothing to export"
        exit 130
    fi
    row_set state interrupted
    row_set interrupted_up "$(up_now)"
    halt "row $ROW_SLUG was interrupted by a signal ($1) during '$(state_get "$ROW_FILE" step)' (packet section 4, halt 7). Check that no service was left stopped and no recorder or collector unit is active before the close"
    wait_group 180
    gx "$A" guest-state-after-interrupt "$GUEST_STATE" || echo "the guest state after the interrupt was not recorded (evidence only)"
    register_late
    (driver_interrupt "$A")
    rc=$?
    row_set driver_code "$rc"
    row_set export "$(receipt_state)"
    if [ "$rc" -eq "$EXIT_EXPORT" ]; then
        echo "row $ROW_SLUG: attempt finished 'interrupted', but its export FAILED (driver code $rc; receipt: $(state_get "$ROW_FILE" export)): the attempt is kept in WSL for 'local_export recover'. It is NOT classified again: its class is written in the result note."
    else
        echo "row $ROW_SLUG: attempt finished 'interrupted'; driver code $rc; export: $(state_get "$ROW_FILE" export). It is NOT classified again: its class is written in the result note."
    fi
    exit "$rc"
}

receipt_state() {
    "$PY" -c '
import json, sys
try:
    r = json.load(open(sys.argv[1]))
    print("%s -> %s" % (r.get("package_state"), r.get("package")))
except (OSError, ValueError) as exc:
    print("no export receipt: %s" % exc)' "$A/export/receipt.json" 2> /dev/null
}

cmd_row() {
    local prev slug f sf st files now elapsed ceiling need ids json rc go=""
    [ "$#" -eq 1 ] || refuse "usage: g3_battery.sh row <slug>"
    ROW_SLUG=$1
    # S3 (point 1): the rows of S3 only; the battery's other rows are not rows of this script.
    # S4 (point 1): the one row of S4; the rows of S1, S2 and S3 are not rows of this script.
    LABEL=$(row_session "$ROW_SLUG") || refuse "unknown row '$ROW_SLUG' (S4: $ROWS_S4 only; the rows of S1, S2 and S3 are not run again)"
    start_log "row-$ROW_SLUG"
    # The turn comes before the first check: "this row was not started yet" is tested
    # below and made true only when the attempt exists, seconds later.
    take_turn "row $ROW_SLUG"
    say "row $ROW_SLUG (session $LABEL): steps script sha256 $(sha_of "$SELF")"
    # Refusals: nothing is started, nothing is recorded as a halt (SESSION_FILE stays empty).
    f=$STATE/session-$LABEL.env
    [ -f "$f" ] || refuse "session $LABEL was not opened by this script ($f is absent)"
    [ "$(state_get "$f" state)" = open ] || refuse "session $LABEL is recorded '$(state_get "$f" state)', not open"
    [ -n "$SESSION" ] && [ -d "$SESSION" ] && [ "$(state_get "$f" session_attempt)" = "$SESSION" ] \
        || refuse "the open session ('${SESSION:-none}') is not the one session $LABEL recorded ($(state_get "$f" session_attempt))"
    [ ! -e "$STATE/row-$ROW_SLUG.env" ] || refuse "row $ROW_SLUG was already started ($STATE/row-$ROW_SLUG.env): a row is run once, never repeated"
    prev=""
    for slug in $(session_rows "$LABEL"); do
        [ "$slug" != "$ROW_SLUG" ] || break
        prev=$slug
    done
    if [ -n "$prev" ]; then
        # An interrupted row is finished and exported too; the halt its interrupt
        # recorded is what then stops this row, unless Rui directs otherwise (below).
        st=$(state_get "$STATE/row-$prev.env" state)
        case $st in
            classified | interrupted) ;;
            *) refuse "the previous row $prev is '${st:-not started}', not classified: the next row starts only when this one is classified and its gate passed" ;;
        esac
    fi
    [ "$(sha_of "$SELF")" = "$(state_get "$f" steps_script_sha256)" ] \
        || refuse "this steps script is not the one session $LABEL was opened with (sha256 $(state_get "$f" steps_script_sha256))"
    [ "$(manifest_tool sha "$MANIFEST" "$ROWS_DIR")" = "$(state_get "$f" rows_manifest_sha256)" ] \
        || refuse "rows.manifest.json is not the one session $LABEL was opened with"
    # S3 (bounded check of 2026-10-05, O1): a recorded halt ends the session. No variable
    # lets a further row start after it (decision summary, choice 2: a procedural,
    # instrumentation or safe-state halt does not permit continuation; request, section 5:
    # "Test 9 is then not run"). EGW_G3_RUI_GO is read by 'close' outside the script only.
    # S4 (point 1): the same rule; the text names S4's request.
    if [ -n "$(state_get "$f" halt)" ]; then
        refuse "NOT STARTED: session $LABEL has a recorded halt ($(state_get "$f" halt)). A halt ends the session (request of 2026-10-05, section 5): classify the row if it awaits classification, then 'close', then hand back to Rui"
    fi
    ceiling=$(row_ceiling_min "$ROW_SLUG")
    need=$((ceiling * 60 + KEEPALIVE_MARGIN_S))
    keepalive_check "$need" || refuse "the keepalive client is not attached with $need s left (the row's ceiling of $ceiling min plus a margin); row $ROW_SLUG was NOT started"

    # From here on a failed check is a halt of the session (packet section 4).
    SESSION_FILE=$f
    UP0=$(state_get "$SESSION_FILE" up0)
    if ! verify_candidate; then
        halt "$WHY: row $ROW_SLUG was NOT started and no attempt was created (packet section 4, halt 6: an identity differing from section 1)"
        exit 1
    fi
    if ! verify_row_files "$LABEL" "$ROW_SLUG"; then
        halt "the row files of $ROW_SLUG are not the manifest's: the row was NOT started and no attempt was created"
        exit 1
    fi
    if [ "$(state_get "$SESSION_FILE" wsl_boot_id)" != "$(wsl_boot_id)" ]; then
        halt "WSL was restarted since session $LABEL was opened (its /proc/uptime baseline is gone, and so is the guest): row $ROW_SLUG was NOT started (packet section 4, halt 6)"
        exit 1
    fi
    now=$(up_now)
    elapsed=$((now - UP0))
    state_add "$SESSION_FILE" row_clock "row=$ROW_SLUG now=$now up0=$UP0 elapsed=$elapsed"
    echo "session clock: NOW=$now UP0=$UP0 elapsed=$elapsed s (cutoff $CUTOFF_S s)"
    if [ "$elapsed" -ge "$CUTOFF_S" ]; then
        echo "NOT STARTED: the 3 h cutoff (row $ROW_SLUG: $elapsed s of session time; no row starts at or after $CUTOFF_S s)"
        state_add "$SESSION_FILE" halt "up=$now row=$ROW_SLUG NOT STARTED: the 3 h cutoff ($elapsed s; packet section 4, halt 7)"
        exit 1
    fi
    qemu_procs > /dev/null
    rc=$?
    if [ "$rc" -ne 0 ]; then
        halt "no qemu-system-aarch64 process could be shown (pgrep exit $rc: 1 none, other undetermined): the guest is lost; row $ROW_SLUG was NOT started (packet section 4, halt 6)"
        exit 1
    fi
    if ! tunnel_now; then
        halt "tunnel_check failed before row $ROW_SLUG: the tunnel is lost; the row was NOT started and no attempt was created (packet section 4, halt 6)"
        exit 1
    fi
    echo "tunnel: the master answers"
    if ! fresh_row "$ROW_SLUG"; then
        halt "an id of row $ROW_SLUG is not fresh on the host, or an earlier attempt of the row that is not admitted exists: the row was NOT started and no attempt was created (packet section 4, halt 1)"
        exit 1
    fi
    # S3 (point 4): before row t8, the gate package's record of the running images against
    # S2's (gate_images_check). A difference, or a record that cannot be read, is a halt of
    # the same kind as an identity that differs: row t8 is not started.
    # S4 (point 6): the same check, before row t6 (S3's gate matched S2's record).
    if [ "$ROW_SLUG" = t6 ]; then
        say "row t6: the running images recorded by the gate driver at open, against S2's record"
        if ! gate_images_check; then
            halt "$WHY: row t6 was NOT started and no attempt was created (request of 2026-10-05, section 5 item 1: an identity differing from the recorded candidate)"
            exit 1
        fi
    fi

    # The attempt.
    A=$(new_attempt "G3 qualification $ROW_SLUG" official) || { A=""; halt "the attempt of row $ROW_SLUG could not be created: the row was NOT started"; exit 1; }
    ROW_FILE=$STATE/row-$ROW_SLUG.env
    row_set slug "$ROW_SLUG"
    row_set session_label "$LABEL"
    row_set attempt "$A"
    row_set attempt_name "$(basename "$A")"      # S3 (point 9): the new attempt's name, recorded
    row_set start_up "$now"
    row_set start_wall "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    row_set session_elapsed_at_start_s "$elapsed"
    row_set ceiling_min "$ceiling"
    row_set pid "$$"
    row_set pid_start "$(proc_start "$$")"
    row_set pgid "$(own_pgid)"
    row_set pgid_start "$(proc_start "$(own_pgid)")"
    row_set wsl_boot_id "$(wsl_boot_id)"
    row_set state preparing
    row_set step prepare
    [ -z "$go" ] || row_set rui_go "$go"
    trap 'on_signal INT' INT
    trap 'on_signal TERM' TERM
    trap 'on_signal HUP' HUP
    say "row $ROW_SLUG: attempt $A (ceiling $ceiling min, counted from the row's start at up=$now and shared by everything the row does: the operator enforces it with 'term $ROW_SLUG')"
    # S3 (point 9): the export tool numbers an attempt by its scenario slug. T8's new attempt
    # must be attempt02 (attempt01 is S2's halted one) and T9's attempt01; under any other
    # name the row halts here, before any step (nothing of the row is run or recorded
    # further; the attempt is classified 'not started' as it stands).
    # S4 (point 5): the same mechanism for t6, whose new attempt must be attempt02
    # (attempt01 is S2's invalid one, T6_ADMITTED; request of 2026-10-05, section 3).
    case $(basename "$A") in
        *"$(row_attempt_suffix "$ROW_SLUG")") ;;
        *)
            halt "row $ROW_SLUG: the new attempt is named $(basename "$A"), which does not end '$(row_attempt_suffix "$ROW_SLUG")' (the name the request of 2026-10-05, section 3, expects): an attempt of this row exists that was not accounted for, or the admitted one is not where it is kept. No step of the row was run"
            LATE_DONE=1     # no step ran: there is nothing of this row to register after it
            ;;
    esac

    files=$(row_files "$ROW_SLUG")
    ids=$(repo_identity) || halt "row $ROW_SLUG: the identity of the clean clone could not be read: $ids"
    if [ "$HALTED" -eq 0 ]; then
        # shellcheck disable=SC2086
        json=$(manifest_tool workload "$MANIFEST" "$ROWS_DIR" "$ROW_SLUG" "$(basename "$SESSION")" "$LABEL" "$ceiling" "$UP0" "$now" \
            "$(sha_of "$SELF")" "$HELPER_SHA" "$REPO" "$(row_workload_ids "$ROW_SLUG" | tr ' ' ',')" "$(row_harness_id "$ROW_SLUG")" \
            "$(row_id_note "$ROW_SLUG")" $files) \
            && (cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$ids" "workload=$json") \
            || halt "row $ROW_SLUG: the attempt fields could not be recorded"
    fi
    if [ "$HALTED" -eq 0 ]; then
        for sf in $files; do
            cp "$ROWS_DIR/$sf" "$A/environment/$sf" || halt "row $ROW_SLUG: $sf could not be copied into the attempt"
            [ ! -f "$ROWS_DIR/$sf.diff" ] || cp "$ROWS_DIR/$sf.diff" "$A/environment/$sf.diff" || halt "row $ROW_SLUG: $sf.diff could not be copied into the attempt"
        done
        # shellcheck disable=SC2086
        manifest_tool entries "$MANIFEST" "$ROWS_DIR" "$ROW_SLUG" $files > "$A/environment/rows.manifest.$ROW_SLUG.json" \
            && cp "$MANIFEST" "$A/environment/rows.manifest.json" && cp "$SELF" "$A/environment/g3_battery.sh" \
            || halt "row $ROW_SLUG: the manifest entries or this script could not be kept in the attempt"
        # What is sourced is the copy: it is verified again where it now stands.
        # shellcheck disable=SC2086
        manifest_tool verify "$MANIFEST" "$A/environment" "$LABEL" "$ROW_SLUG" $files \
            || halt "row $ROW_SLUG: the copies of the row files in the attempt are not the manifest's"
    fi
    if [ "$HALTED" -eq 0 ] && [ "$ROW_SLUG" = t9 ]; then
        ls -d "$P"/itest-acl-* > "$STATE/row-t9.acl-before.txt" 2> /dev/null
        sha_of /tmp/wrong.crt > "$STATE/row-t9.wrongcrt-before.txt" 2> /dev/null
    fi
    if [ "$HALTED" -eq 0 ]; then
        register_sources || halt "row $ROW_SLUG: a source could not be registered"
    fi
    if [ "$HALTED" -eq 0 ]; then
        row_set step guest-state-before
        say "row $ROW_SLUG: the gate's read before the row"
        gx "$A" guest-state-before "$GUEST_STATE"
        rc=$?
        BEFORE=$(console_of guest-state-before)
        [ "$rc" -eq 0 ] && [ -n "$BEFORE" ] \
            || halt "row $ROW_SLUG: the guest state before the row was not recorded (guest-state-before exit $rc; 97: the guest did not answer): no step of the row was run"
    fi
    if [ "$HALTED" -eq 0 ]; then
        run_row_steps
        [ "$T8_ANSWERED" -eq 0 ] || t8_evidence
        register_late
        gate_after
        if [ "${#GATE_BAD[@]}" -eq 0 ]; then
            row_set gate pass
            if [ "$ROW_SLUG" = t8 ]; then
                say "GATE $ROW_SLUG: pass (guest state recorded and NOT compared across the reboot, six services healthy, no recorder or collector unit active, tunnel up)"
            else
                say "GATE $ROW_SLUG: pass (guest state compared, six services healthy, no recorder or collector unit active, tunnel up)"
            fi
        else
            row_set gate "failed: $(printf '%s; ' "${GATE_BAD[@]}")"
            halt "row $ROW_SLUG: the gate did NOT pass (packet section 4, halt 3): $(printf '%s; ' "${GATE_BAD[@]}")"
        fi
    else
        register_late
    fi

    trap - INT TERM HUP
    row_set state awaiting-classification
    row_set step ended
    row_set end_up "$(up_now)"
    say "row $ROW_SLUG ended after $(($(up_now) - now)) s; the attempt is OPEN for the operator's classification"
    echo "attempt:  $A"
    echo "consoles: $A/console/ (commands.jsonl beside it)"
    ls "$A/console" | sed 's/^/  /'
    echo "STOP lines printed by the row (the line 'set -v' echoes is not one):"
    grep -n '^STOP:' "$A"/console/*.stdout.txt "$A"/console/*.stderr.txt 2> /dev/null | cut -c1-400 | sed 's/^/  /' || true
    echo "host files of the row: $P/<id>* (registered sources; copied by the export)"
    if [ "$HALTED" -ne 0 ]; then
        echo "HALT recorded for session $LABEL: classify this row, then 'close' (controlled close, hand back to Rui). No further row starts."
        exit 1
    fi
    echo "Next: read the console and the files, then 'classify $ROW_SLUG <status> <validity> <outcome> <reason> <next-action>'."
}

# --- classify -------------------------------------------------------------------------
# text_arg VALUE: the value itself, or the content of the file named after '@'.
text_arg() {
    case $1 in
        @*) one_line "$(cat "${1#@}")" ;;
        *) one_line "$1" ;;
    esac
}

cmd_classify() {
    local status validity outcome reason next class code st
    [ "$#" -eq 6 ] || refuse "usage: g3_battery.sh classify <slug> <finished|failed> <validity> <outcome> <reason> <next-action> (a reason or next-action of the form @FILE is read from FILE)"
    ROW_SLUG=$1
    status=$2
    validity=$3
    outcome=$4
    row_session "$ROW_SLUG" > /dev/null || refuse "unknown row '$ROW_SLUG'"
    start_log "classify-$ROW_SLUG"
    take_turn "classify $ROW_SLUG"
    ROW_FILE=$STATE/row-$ROW_SLUG.env
    [ -f "$ROW_FILE" ] || { ROW_FILE=""; refuse "row $ROW_SLUG was not started"; }
    st=$(state_get "$ROW_FILE" state)
    [ "$st" = awaiting-classification ] || refuse "row $ROW_SLUG is '$st', not awaiting classification (an interrupted row is already finished and exported; a classified row is never classified twice)"
    A=$(state_get "$ROW_FILE" attempt)
    [ -n "$A" ] && [ -d "$A" ] || refuse "the attempt of row $ROW_SLUG ($A) is not there"
    case $status in finished | failed) ;; *) refuse "status must be finished or failed" ;; esac
    # Packet section 5: the validity/outcome pairs of local_export finish.
    case "$validity/$outcome" in
        valid/pass) class="pass" ;;
        valid/fail) class="valid SUT failure" ;;
        invalid/unknown) class="invalid instrumentation" ;;
        valid/inconclusive | unknown/inconclusive) class="inconclusive / not demonstrated" ;;
        not-applicable/not-run) class="not started" ;;
        *) refuse "validity/outcome '$validity/$outcome' is not a pair of packet section 5 (valid/pass, valid/fail, invalid/unknown, valid/inconclusive, unknown/inconclusive, not-applicable/not-run)" ;;
    esac
    reason=$(text_arg "$5") || refuse "the reason could not be read"
    next=$(text_arg "$6") || refuse "the next action could not be read"
    [ -n "$reason" ] && [ -n "$next" ] || refuse "the reason and the next action must not be empty"
    LABEL=$(state_get "$ROW_FILE" session_label)
    SESSION_FILE=$STATE/session-$LABEL.env
    say "classify $ROW_SLUG: $class ($status, $validity/$outcome)"
    (cd "$REPO/src" && $LE finish --attempt "$A" --status "$status" --validity "$validity" --outcome "$outcome" \
        --reason "$reason" --next-action "$next") \
        || refuse "local_export finish refused the classification: nothing was exported and the row still awaits classification"
    headline "$A" "G3 qualification $ROW_SLUG: $class. $reason" || echo "WARNING: the headline could not be recorded"
    driver_code "$A"
    code=$?
    row_set state classified
    row_set class "$class"
    row_set classification "$status $validity/$outcome"
    row_set reason "$reason"
    row_set next_action "$next"
    row_set driver_code "$code"
    row_set export "$(receipt_state)"
    row_set classified_up "$(up_now)"
    echo "row $ROW_SLUG: classified '$class'; driver code $code; export: $(state_get "$ROW_FILE" export)"
    if [ "$code" -eq "$EXIT_EXPORT" ]; then
        halt "row $ROW_SLUG: the export FAILED (packet section 4, halt 2): the attempt is kept in WSL for 'local_export recover'"
    fi
    case $class in
        "not started") halt "row $ROW_SLUG is classified not started (packet section 4, halt 1): it is not attempted again under this approval" ;;
        # S3 (bounded check of 2026-10-05, O3): recorded as a halt, so that no further row starts.
        # S4 (point 1): the label in the text.
        "invalid instrumentation") halt "row $ROW_SLUG is classified invalid instrumentation (request, section 5 item 2): no further row of S4 starts" ;;
    esac
    case $(state_get "$ROW_FILE" gate) in
        pass) ;;
        *) echo "NOTE: this row's gate did not pass ($(state_get "$ROW_FILE" gate)): no further row starts; 'close' and hand back to Rui." ;;
    esac
    # S3 (bench s18, 2026-10-05): a halt of classify's own still names the next step.
    [ "$HALTED" -eq 0 ] || { echo "Next: 'close', then hand back to Rui: session $LABEL has a recorded halt, and no further row starts."; exit 1; }
    # The halts of the 'row' invocation (a failed gate, a step status 97 or 74) are in the
    # session's state file, not in this invocation's HALTED.
    if [ "$(state_get "$ROW_FILE" gate)" = pass ] && [ -z "$(state_get "$SESSION_FILE" halt)" ]; then
        echo "Next: the next row of session $LABEL, or 'close' after the last one."
    else
        echo "Next: 'close', then hand back to Rui: session $LABEL has a recorded halt (or this row's gate did not pass), and no further row starts without his direction."
    fi
}

# --- term -----------------------------------------------------------------------------
# S3 (point 11): 'term' (TERM to the row's group, never KILL; nothing is signalled when
# QEMU or the keepalive client is in that group), 'close' (the recorded stop with both
# env files and -t 130, then the frozen close driver; its paths for a guest that does not
# answer and for no QEMU process left), the turn, the keepalive checks, the cut-off,
# 'classify' and its six pairs, and the environment copy at open are the battery's,
# unchanged but for the label and the names of S3's records.
cmd_term() {
    local pgid members mpid margs
    [ "$#" -eq 1 ] || refuse "usage: g3_battery.sh term <slug>"
    ROW_SLUG=$1
    row_session "$ROW_SLUG" > /dev/null || refuse "unknown row '$ROW_SLUG'"
    start_log "term-$ROW_SLUG"
    ROW_FILE=$STATE/row-$ROW_SLUG.env
    [ -f "$ROW_FILE" ] || { ROW_FILE=""; refuse "row $ROW_SLUG was not started"; }
    pgid=$(state_get "$ROW_FILE" pgid)
    case $pgid in '' | *[!0-9]*) refuse "row $ROW_SLUG records no process group" ;; esac
    [ "$pgid" != "$(own_pgid)" ] || refuse "the recorded process group $pgid is this invocation's own"
    members=$(row_group "$ROW_FILE") \
        || refuse "no process of row $ROW_SLUG is left in its process group $pgid (state '$(state_get "$ROW_FILE" state)'; another WSL boot, or the number now names another group): nothing is signalled"
    say "term $ROW_SLUG: the process group $pgid (row state '$(state_get "$ROW_FILE" state)', step '$(state_get "$ROW_FILE" step)')"
    # The simulator's password is on its argv: the listing is printed (and so kept in this
    # invocation's console, an operator record) only masked and cut, as 'status' cuts it.
    printf '%s\n' "$members" | mask_argv | cut -c1-90
    # A HALT of 'term' is kept in the session's state file like every other halt.
    LABEL=$(state_get "$ROW_FILE" session_label)
    [ -z "$LABEL" ] || [ ! -f "$STATE/session-$LABEL.env" ] || SESSION_FILE=$STATE/session-$LABEL.env
    if printf '%s\n' "$members" | cut -d' ' -f2- | grep -Eq "$QEMU_EXE_RE"; then
        halt "term $ROW_SLUG: a qemu-system-aarch64 process is in the row's process group $pgid: nothing was signalled. QEMU is never killed without Rui's decision."
        exit 1
    fi
    # A keepalive client is 'sleep <seconds>' started by a WSL relay; a row's own sleeps
    # (the helpers' waits) have a shell as their parent.
    while read -r mpid margs; do
        case $margs in
            sleep\ [0-9]*)
                case $(ps -o comm= -p "$(ps -o ppid= -p "$mpid" 2> /dev/null | tr -d ' ')" 2> /dev/null) in
                    Relay*)
                        halt "term $ROW_SLUG: the keepalive client (pid $mpid, '$margs') is in the row's process group $pgid: nothing was signalled."
                        exit 1
                        ;;
                esac
                ;;
        esac
    done <<< "$members"
    kill -TERM -- "-$pgid"
    echo "TERM sent to the process group $pgid (exit $?). KILL is never sent."
    state_add "$ROW_FILE" term "up=$(up_now) TERM sent to the process group $pgid"
    echo "The row's own trap finishes its attempt 'interrupted' and exports it; T7's fault job restores its service from its trap."
    echo "Then: 'status'; check that no service was left stopped and no recorder or collector unit is active; 'close'."
}

# --- close ----------------------------------------------------------------------------
close_interrupted() {
    trap '' INT TERM HUP
    halt "close was interrupted by a signal ($1); a driver that was running handled its own attempt. Read 'status' and whether a qemu-system-aarch64 process is left"
    exit 130
}

# attempt_state DIR: '<status> <export receipt state>' of an attempt, read from its own
# files: 'running none' (open, not exported), 'interrupted complete' (finished and
# exported), 'unreadable none'.
attempt_state() {
    "$PY" -c '
import json, sys
def read(path, key, default):
    try:
        return str(json.load(open(path)).get(key) or default)
    except (OSError, ValueError, AttributeError):
        return default
print("%s %s" % (read(sys.argv[1] + "/attempt.json", "status", "unreadable").replace(" ", "_"),
                 read(sys.argv[1] + "/export/receipt.json", "state", "none").replace(" ", "_")))' "$1" 2> /dev/null \
        || echo "unreadable none"
}

# close_rows LABEL: the session's rows at the close (packet section 4, safe close: no
# row or poller running; the open attempt finished and exported as it stands BEFORE the
# stop). Refuses (exit 2) while a row runs, awaits classification, or left an attempt
# that is still open; SESSION_FILE is set by the caller.
close_rows() {
    local slug f st left a ast
    for slug in $(session_rows "$1"); do
        f=$STATE/row-$slug.env
        [ -f "$f" ] || continue
        st=$(state_get "$f" state)
        ! row_alive "$f" || refuse "row $slug is running (pid $(state_get "$f" pid), state '$st'): 'term $slug' sends TERM, never KILL"
        left=$(row_group "$f" | mask_argv | cut -c1-90 | head -n 3 | tr '\n' ';')
        [ -z "$left" ] || refuse "row $slug: a process is still in its process group $(state_get "$f" pgid) ($left): no row or poller may be running at the close ('term $slug')"
        case $st in
            classified | interrupted) ;;
            awaiting-classification) refuse "row $slug awaits classification: its attempt is finished and exported first ('classify $slug ...'; packet section 4, safe close)" ;;
            *)
                # The row's process died without its trap: this script neither finished
                # nor exported its attempt. The close does not power the guest off over
                # an attempt that is still open.
                a=$(state_get "$f" attempt)
                ast=$(attempt_state "$a")
                case $ast in
                    running\ * | unreadable\ *) left=open ;;
                    *\ complete) left="" ;;
                    *) left=open ;;
                esac
                [ -z "$left" ] \
                    || refuse "row $slug is recorded '$st', its process is gone and its attempt is not finished and exported (attempt.json status and export receipt: '$ast'). The safe close finishes and exports the open attempt BEFORE the stop (packet section 4): nothing was stopped. First fetch what the row left on the guest (its /tmp is lost at the power-off; README, 'Restorations'), then mark and export the attempt with the frozen tool, then 'close' again:  (cd \"$REPO/src\" && $LE recover --attempts-root \"$ATTEMPTS\" --dest-root \"$OUT\" --secrets-env \"$SECRETS_ENV\" --interrupt $(basename "$a"))"
                state_set "$f" state interrupted
                state_add "$f" closed_outside "up=$(up_now) was '$st' with its process gone; the attempt was finished and exported outside this script ($ast), read at the close"
                state_set "$f" export "$(A=$a receipt_state)"
                halt "row $slug: its process died without its trap (it was recorded '$st'); its attempt was finished and exported outside this script ($ast) and the row is now recorded 'interrupted' (packet section 4, halt 2). It is NOT classified: its class is written in the result note"
                ;;
        esac
    done
}

# rootfs_after_close SESSION_DIR: the root file system hash the frozen close driver
# recorded after the power-off (its 'artefacts-after-poweroff' step), kept in the
# session's state file. S4 (point 1): no session of this script opens after S4; the
# value is the one a later boot of this image would have to expect.
rootfs_after_close() {
    local line
    line=$(ls "$1"/console/*-artefacts-after-poweroff.stdout.txt 2> /dev/null | tail -n 1)
    if [ -n "$line" ]; then
        line=$(sed -n 's/^\([0-9a-f]\{64\}\)  .*\.ext4$/\1/p' "$line" | head -n 1)
        [ -z "$line" ] || state_set "$SESSION_FILE" rootfs_after_close "$line"
    fi
    echo "rootfs ext4 after the close: ${line:-NOT READ} (the image is mutable: a later boot expects this value)"
}

# data_disk_header: packet section 1 lists the data disk's ext4 header "before each boot
# and after each close". The frozen open driver lists it before each boot; this is the
# listing after the close, in its form (guest_session_open.sh, '## data disk'). Read-only
# (dumpe2fs -h opens the image for reading), and only when no qemu-system-aarch64 process
# is left: a disk a guest may still have mounted is not read. Evidence only: printed to
# this invocation's console (an operator record); it decides nothing.
data_disk_header() {
    local rc
    qemu_procs > /dev/null
    rc=$?
    if [ "$rc" -ne 1 ]; then
        echo "data disk after the close: NOT listed (qemu pgrep exit $rc: a qemu-system-aarch64 process is left, or that was not determined)"
        return 0
    fi
    echo "data disk after the close (read-only listing, no qemu-system-aarch64 process left):"
    ls -l "$DATA_DISK" 2>&1 | sed 's/^/  /'
    /usr/sbin/dumpe2fs -h "$DATA_DISK" 2> /dev/null | grep -E "state|features|mount count|Last mount" | sed 's/^/  /'
    rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || echo "  the ext4 header of $DATA_DISK was NOT read (dumpe2fs exit $rc); evidence only"
    return 0
}

# close_outside: 'close' with no open session. A session this script opened and did not
# close itself (the frozen guest_session_close.sh was run by hand after a lost guest, or
# an 'open' halted before any session existed) stays recorded 'open' or 'halted'. This
# script changes the record only on Rui's explicit direction (EGW_G3_RUI_GO, recorded)
# and only when nothing is left to close: no current_session, no qemu-system-aarch64
# process, no row running or unfinished. It records a halt with the change. It never
# returns. S4 (point 1): the one label is S4.
close_outside() {
    local l f st="" found=""
    [ ! -e "$EXEC/current_session" ] \
        || refuse "no open session: $EXEC/current_session names '${SESSION}', which is not a session directory. Nothing was changed; hand back to Rui"
    # shellcheck disable=SC2043
    for l in S4; do
        f=$STATE/session-$l.env
        [ -f "$f" ] || continue
        st=$(state_get "$f" state)
        [ "$st" = closed ] || { found=$l; break; }
    done
    [ -n "$found" ] || refuse "no open session"
    f=$STATE/session-$found.env
    [ -n "${EGW_G3_RUI_GO:-}" ] \
        || refuse "no open session ($EXEC/current_session is absent), but session $found is recorded '$st' in $f: it was closed outside this script, or its open left no session. That record is changed only on Rui's explicit direction: 'close' with EGW_G3_RUI_GO set to his words records the session closed, with a halt (his words are recorded)"
    LABEL=$found
    start_log "close-$LABEL"
    take_turn "close $LABEL (the record of a close made outside this script)"
    say "close $LABEL: no session is open; session $LABEL is recorded '$st'. EGW_G3_RUI_GO is set and is recorded: $EGW_G3_RUI_GO"
    qemu_procs > /dev/null
    case $? in
        1) ;;
        0) refuse "a qemu-system-aarch64 process is running although no session is open: session $LABEL is NOT recorded closed. QEMU is never killed without Rui's decision" ;;
        *) refuse "whether a qemu-system-aarch64 process is running could not be determined: session $LABEL is NOT recorded closed" ;;
    esac
    SESSION_FILE=$f
    close_rows "$LABEL"
    S=$(state_get "$SESSION_FILE" session_attempt)
    [ -z "$S" ] || [ ! -d "$S" ] || rootfs_after_close "$S"
    data_disk_header
    state_set "$SESSION_FILE" state closed
    state_set "$SESSION_FILE" closed_up "$(up_now)"
    state_set "$SESSION_FILE" closed_outside "the record said '$st'; no current_session and no qemu-system-aarch64 process at up=$(up_now); EGW_G3_RUI_GO: $EGW_G3_RUI_GO"
    halt "session $LABEL was not closed by this script (its record said '$st'; guest_session_close_exit='$(state_get "$SESSION_FILE" guest_session_close_exit)'): it is recorded closed on Rui's direction ($EGW_G3_RUI_GO). The session attempt's own package says how it ended: ${S:-no session attempt was recorded}"
    exit 1
}

cmd_close() {
    local rc
    [ "$#" -eq 0 ] || refuse "usage: g3_battery.sh close"
    [ -n "$SESSION" ] && [ -d "$SESSION" ] || close_outside
    LABEL=$(open_label) || refuse "no $STATE/session-<label>.env names the open session $SESSION: it was not opened by this script (the frozen guest_session_close.sh closes it)"
    start_log "close-$LABEL"
    # The turn: a 'close' is refused while 'open' (or any other changing subcommand) is
    # still running - the session's drivers must not lose the guest under them.
    take_turn "close $LABEL"
    say "close $LABEL: $SESSION"
    SESSION_FILE=$STATE/session-$LABEL.env
    close_rows "$LABEL"
    # The stop (up to 130 s for each service) and the power-off must not lose WSL under
    # them: the keepalive is checked before anything is stopped, as before every row.
    keepalive_check "$KEEPALIVE_MARGIN_S" \
        || refuse "the keepalive client is not attached with $KEEPALIVE_MARGIN_S s left (see above): nothing was stopped. Attach one, then 'close' again"
    trap 'close_interrupted INT' INT
    trap 'close_interrupted TERM' TERM
    trap 'close_interrupted HUP' HUP
    state_set "$SESSION_FILE" close_started_up "$(up_now)"

    qemu_procs > /dev/null
    if [ "$?" -eq 1 ]; then
        # The guest is gone (lost; T8 re-launches nothing, so a QEMU exit there is this
        # case, with its halt already recorded by the row): the units
        # cannot be read and there is no stack to stop, so asking again would answer 97
        # for ever. What is left of the controlled close is the session attempt, which
        # the frozen close driver finishes and exports as it stands; with no QEMU process
        # it signals nothing and powers nothing off.
        state_set "$SESSION_FILE" stack_stop_130_exit "not run: no qemu-system-aarch64 process"
        halt "close $LABEL: no qemu-system-aarch64 process is left (pgrep exit 1): the guest was lost before the close (packet section 4, halt 5 or 6). No unit was read and the recorded stop was NOT run - there is nothing to stop. The frozen guest_session_close.sh is run to finish and export the session attempt as it stands; its guest steps cannot succeed (expect exit 5)"
    else
        say "no recorder or collector unit active (read-only)"
        gx "$S" g3-close-units "$(units_script)"
        rc=$?
        case $rc in
            0) ;;
            3)
                halt "close: a recorder or collector unit is active (exit 3): nothing was stopped. The runbook's own cleanup is the operator's decision (README, 'Restorations': at most three tries); then 'close' again"
                exit 1
                ;;
            "$EXIT_NOT_REACHED")
                halt "close: the guest did not answer (exit 97) although a qemu-system-aarch64 process is running: whether a unit is active is UNKNOWN and nothing was stopped. 'close' answers the same for as long as the guest does not answer: hand back to Rui (QEMU is never killed without his decision; the frozen guest_session_close.sh is what finishes and exports the session attempt)"
                exit 1
                ;;
            *)
                halt "close: the units could not be read (exit $rc: 1 systemctl failed on the guest, 74 the console capture was lost): whether a unit is active is UNKNOWN and nothing was stopped. Read $S/console/, then 'close' again or hand back to Rui"
                exit 1
                ;;
        esac

        say "the recorded stop with the controller's 130 s allowance (PM condition 4)"
        gx "$S" stack-stop-130 "cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env stop -t 130; rc=\$?; echo \"stop exit=\$rc\"; docker ps -a --format '{{.Names}} {{.Status}}'; exit \$rc"
        rc=$?
        state_set "$SESSION_FILE" stack_stop_130_exit "$rc"
        if [ "$rc" -ne 0 ]; then
            halt "stop failed (stack-stop-130 exit $rc): the close driver was NOT run and QEMU is NOT forced off. Hand back to Rui"
            exit 1
        fi
    fi

    run_driver "$LABEL" guest_session_close
    rc=$?
    trap - INT TERM HUP
    rootfs_after_close "$S"
    data_disk_header
    if [ ! -e "$EXEC/current_session" ]; then
        # The frozen driver removes current_session only when no QEMU process is left.
        state_set "$SESSION_FILE" state closed
        state_set "$SESSION_FILE" closed_up "$(up_now)"
        say "session $LABEL closed (guest_session_close.sh exit $rc)"
        [ "$rc" -eq 0 ] || halt "guest_session_close.sh exited $rc although the guest is off (1: the session's records show a system fault, such as an OOM; 3: the record of the close is incomplete; 4: the export failed; 5: the stop or the power-off failed): read $DRIVER_CONSOLE"
    else
        state_set "$SESSION_FILE" state close-failed
        halt "guest_session_close.sh exited $rc and $EXEC/current_session is kept: the session is NOT closed. Read $DRIVER_CONSOLE; check for a qemu-system-aarch64 process by hand, never kill it"
    fi
    echo "What remains for the operator:"
    # S4 (point 1): the names of S4's operator records and of its result note.
    echo "  1. verify every export (the export tool's own verification, then 'sha256sum -c' in each package), then seal the operator records ($STATE: the session and row state files, console/, the driver consoles, the classification notes) as HIST_<UTC date>-g3-t6-s4-operator-records (with an -attemptNN suffix if that name exists);"
    echo "  2. write output_test/decisions/<date>_g3-t6-results.md (the row's validity, the amended criterion's items, and lost and late_confirmations reported apart as a sizing finding; no G3 claim);"
    echo "  3. release the keepalive client and the Windows keep-awake."
    [ "$HALTED" -eq 0 ] || exit 1
}

# --- status ---------------------------------------------------------------------------
cmd_status() {
    local l f rf slug st now up0 start ceiling
    now=$(up_now)
    echo "state directory: $STATE"
    echo "latest console of this script: $(ls "$STATE"/console/[0-9]*.txt 2> /dev/null | tail -n 1)"
    echo "open session (current_session): ${SESSION:-none}; host uptime now: $now s; WSL boot $(wsl_boot_id)"
    qemu_procs
    echo "qemu pgrep exit=$? (0 running, 1 none)"
    if [ -f "$STATE/turn.env" ]; then
        f=$STATE/turn.env
        st=ended
        [ "$(state_get "$f" wsl_boot_id)" != "$(wsl_boot_id)" ] || [ -z "$(state_get "$f" pid_start)" ] \
            || [ "$(proc_start "$(state_get "$f" pid)")" != "$(state_get "$f" pid_start)" ] || st="STILL RUNNING: open, row, classify and close are refused until it ends"
        echo "turn of the changing subcommands: last taken by '$(state_get "$f" what)' (pid $(state_get "$f" pid), $(state_get "$f" taken_wall)); that invocation: $st"
    fi
    # S3 (point 1): the one session of this script.
    # S4 (point 1): S4.
    # shellcheck disable=SC2043
    for l in S4; do
        f=$STATE/session-$l.env
        [ -f "$f" ] || { echo "session $l: not opened"; continue; }
        up0=$(state_get "$f" up0)
        echo "session $l: state=$(state_get "$f" state) attempt=$(state_get "$f" session_attempt) UP0=$up0"
        if [ "$(state_get "$f" state)" != closed ] && [ "$(state_get "$f" wsl_boot_id)" = "$(wsl_boot_id)" ]; then
            echo "  elapsed host uptime: $((now - up0)) s of $CUTOFF_S s (a row STARTS only before the cutoff; a running row keeps its ceiling)"
        fi
        sed -n 's/^halt=/  HALT: /p' "$f"
        for slug in $(session_rows "$l"); do
            rf=$STATE/row-$slug.env
            [ -f "$rf" ] || { echo "  row $slug: not started"; continue; }
            st=$(state_get "$rf" state)
            start=$(state_get "$rf" start_up)
            ceiling=$(state_get "$rf" ceiling_min)
            echo "  row $slug: $st; gate=$(state_get "$rf" gate); class=$(state_get "$rf" class); driver code=$(state_get "$rf" driver_code); export=$(state_get "$rf" export)"
            echo "    attempt $(state_get "$rf" attempt)"
            sed -n 's/^halt=/    HALT: /p' "$rf"
            case $st in
                classified | interrupted | awaiting-classification) ;;
                *)
                    if row_alive "$rf"; then
                        echo "    RUNNING: pid $(state_get "$rf" pid) group $(state_get "$rf" pgid), step '$(state_get "$rf" step)', $(((now - start) / 60)) min of its $ceiling min ceiling"
                        [ $((now - start)) -lt $((ceiling * 60)) ] || echo "    PAST ITS CEILING (packet section 4, halt 7): 'term $slug' sends TERM, never KILL"
                    else
                        echo "    its process (pid $(state_get "$rf" pid)) is GONE and the attempt was not closed by this script"
                    fi
                    ;;
            esac
            if row_group "$rf" > /dev/null; then
                echo "    processes still in its group $(state_get "$rf" pgid): $(row_group "$rf" | mask_argv | cut -c1-90 | head -n 8 | tr '\n' ';')"
            fi
        done
    done
}

# --- dispatch -------------------------------------------------------------------------
LABEL=""
UP0=""
main() {
    local sub=${1:-}
    [ "$#" -eq 0 ] || shift
    case $sub in
        open) cmd_open "$@" ;;
        row) cmd_row "$@" ;;
        classify) cmd_classify "$@" ;;
        term) cmd_term "$@" ;;
        close) cmd_close "$@" ;;
        status) cmd_status ;;
        *)
            # S4 (point 1): the usage of S4.
            echo "usage: EGW_EXEC_REPO=\$HOME/egw-exec/repo bash g3_battery.sh open S4 | row t6 | classify t6 <status> <validity> <outcome> <reason> <next-action> | term t6 | close | status" >&2
            return 2
            ;;
    esac
}
# One line, read whole before it runs: bash reads a script as it executes it, and the
# 'exit' ends the shell before anything after this line could be read from a file that
# changed in the meantime.
main "$@"; exit $?
