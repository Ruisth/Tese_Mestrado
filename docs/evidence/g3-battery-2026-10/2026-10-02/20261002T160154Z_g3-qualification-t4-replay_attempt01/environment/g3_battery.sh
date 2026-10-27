#!/bin/bash
# G3 qualifying battery - the operator's steps script (host preparation, part 2).
#
# Authority: Rui's authorisation of 2026-10-02 under the decision packet of
# 2026-10-01 (revision 2) and the operator procedure of the host-preparation
# package. The candidate is FROZEN at 80e833f (tree dad725d): this script edits
# nothing of it. It sources the frozen tools/session/common.sh and
# guest_common.sh and records ONLY through their functions (new_attempt, ex, gx,
# gcp, hx, healthy_wait, headline, driver_code, driver_interrupt) and through
# local_export (set, add-source, finish).
#
# The operator runs ONE subcommand per invocation and classifies between rows:
#   open S1|S2     checks, UP0, then the frozen drivers guest_session_open.sh,
#                  preflight.sh, the environment copy (PM condition 2), gate_health.sh
#   row <slug>     one attempt (purpose official), the row's step files through hx,
#                  the gate before and after; the attempt is left OPEN
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
# Every halt prints 'HALT: ...' and leaves the decision to the operator.
#
# Usage (WSL, login shell; ONE subcommand per wsl.exe invocation, so that a row's
# process group is its own; g3_battery.README.md has the launch lines):
#   EGW_EXEC_REPO=$HOME/egw-exec/repo bash g3_battery.sh <subcommand> [arguments]
# Exit: 0 done; 1 a HALT; 2 refused (nothing was started or changed); 130 (or the
# code driver_status.py derives) after an interrupt.
# State: ${EGW_G3_STATE:-$EXEC/g3-battery} (session-<S1|S2>.env, row-<slug>.env, the
# consoles of every invocation and of the four drivers). Row files: the rows/ folder
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

# --- the frozen candidate (packet section 1) ------------------------------------------
TOOLS=80e833f44f647fe9cd8f5e99d3abf3c444de95aa
TREE=dad725d0bebc25c91712af2aa2705d5eeb92044f
DRIVERS_SHA=4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5
EXPORT_TOOL_SHA=544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b
RUNBOOK_SHA=c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae
HELPER_SHA=e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb
HELPER_LINES=545
TUNNEL_SHA=38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1
CA_SHA=556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff
ROOTFS_BEFORE_S1=c49500a9a7751a8753b8af44e2d76bd1d2d0e694b29524142cabf896f85e7260
CUTOFF_S=10800                  # PM condition 3: no row STARTS after 3 h of session time
GATE_HEALTHY_S=900              # the gate: six services healthy within 900 s
T8_QEMU_EXIT_S=600              # T8: at most 10 min for the first QEMU to exit
KEEPALIVE_OPEN_S=21600          # a keepalive client with at least 6 h left at the open
KEEPALIVE_MARGIN_S=1800         # and, before a row, the row's ceiling plus 30 min

# --- paths ----------------------------------------------------------------------------
STATE=${EGW_G3_STATE:-$EXEC/g3-battery}
ROWS_DIR=${EGW_G3_ROWS:-$SELF_DIR/rows}
MANIFEST=$ROWS_DIR/rows.manifest.json
HELPER=$HOME/egw-tcg/itest-helpers.sh
P=$HOME/egw-tcg/itest
REPLAY=$HOME/egw-tcg/itest-replay
PLAN=$HOME/egw-tcg/pilot/campaign_plan.json
RAWD=$HOME/egw-tcg/pilot/results/raw
PROCESSED=$HOME/egw-tcg/pilot/results/processed
SUT_ENV=$HOME/egw-tcg/sut_environment.json

# --- the twelve rows (packet section 2; the brief's table of step files) ---------------
ROWS_S1="t1-smokes t1-harness t2 t3 t4-replay t4-reset t5"
ROWS_S2="t6 t7-mongo t7-ditto t8 t9"

session_rows() { case $1 in S1) echo "$ROWS_S1" ;; S2) echo "$ROWS_S2" ;; esac; }

row_session() {
    case " $ROWS_S1 " in *" $1 "*) echo S1; return 0 ;; esac
    case " $ROWS_S2 " in *" $1 "*) echo S2; return 0 ;; esac
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
        t8) echo "t8-a-reboot.sh t8-b-return.sh t8-c-snapshot.sh t8-d-smoke.sh" ;;
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
        t8) echo "itest-post-reboot-01-q1" ;;
    esac
}
T8_PREFIX=itest-reboot-q1
T9_IDS="itest-tls-wrongca-q1 itest-auth-wrongpw-q1 itest-notls-q1"

row_harness_id() { case $1 in t1-harness) echo nominal-r02 ;; t6) echo controller_restart-r03 ;; esac; }

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
        t8) echo "$T8_PREFIX is the prefix of the reboot snapshots and of the boot id file, not a run id" ;;
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

# T8: the bounded wait for the first QEMU to exit (-no-reboot) and for the host ports
# 2222 and 8883 to be free. It only reads; QEMU is never signalled. Timed on
# /proc/uptime. 0 exited and free; 1 the limit passed; arguments: status file, limit,
# the executable pattern of guest_common.sh.
T8_WAIT='
status=$1; limit=$2; re=$3
up() { local u r; read -r u r < /proc/uptime; echo "${u%.*}"; }
t0=$(up); n=0
while :; do
    n=$((n + 1)); now=$(up)
    pgrep -af "$re" | cut -c1-160; q=${PIPESTATUS[0]}
    if o=$(ss -ltn); then
        if printf "%s\n" "$o" | grep -qE ":(2222|8883) "; then ports=busy; else ports=free; fi
    else
        ports=unknown
    fi
    if [ -f "$status" ]; then st="present: $(cat "$status")"; else st=absent; fi
    echo "sample $n at +$((now - t0)) s: qemu pgrep exit=$q (0 running, 1 none); $status $st; ports 2222/8883 $ports"
    if [ "$q" -eq 1 ] && [ -f "$status" ] && [ "$ports" = free ]; then
        echo "QEMU EXITED: no qemu-system-aarch64 process, the first boot wrote its status file, ports 2222 and 8883 are free"
        exit 0
    fi
    if [ $((now - t0)) -ge "$limit" ]; then
        echo "STOP: the first QEMU did not exit, or ports 2222/8883 were not freed, within $limit s - QEMU was NOT signalled and is NOT killed"
        exit 1
    fi
    sleep 5
done'

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
    w = {"battery": "G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)",
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

# open_label: the label (S1, S2) of the session whose state file names the session that
# is open now, or nothing.
open_label() {
    local l f
    [ -n "$SESSION" ] || return 1
    for l in S1 S2; do
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
    [ "$got" = "$2" ] || { WHY="$1 ($3) is $got, the packet names $2"; return 1; }
}

# verify_candidate: the identities of packet section 1 this host holds. Non-zero, with
# WHY, at the first that differs.
WHY=""
verify_candidate() {
    local head tree porcelain ids n
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
    want_sha helpers "$HELPER_SHA" "$HELPER" || return 1
    n=$(wc -l < "$HELPER") || n=unreadable
    [ "$n" = "$HELPER_LINES" ] || { WHY="the helper file has $n lines, not $HELPER_LINES"; return 1; }
    bash -n "$HELPER" || { WHY="the helper file does not parse (bash -n)"; return 1; }
    echo "helpers: $HELPER_LINES lines, bash -n clean"
    want_sha tunnel.sh "$TUNNEL_SHA" "$HOME/egw-tcg/tunnel.sh" || return 1
    want_sha ca.crt "$CA_SHA" "$HOME/egw-tcg/ca.crt" || return 1
    check_guest_state || return 1
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
fresh_row() {
    local slug=$1 bad=0 h f
    # shellcheck disable=SC2046
    [ -z "$(row_fresh_ids "$slug")" ] || fresh_itest $(row_fresh_ids "$slug") || bad=1
    h=$(row_harness_id "$slug")
    [ -z "$h" ] || fresh_plan "$h" || bad=1
    for f in "$ATTEMPTS"/*_g3-qualification-"$slug"_attempt* "$OUT"/runs/*/*_g3-qualification-"$slug"_attempt* \
        "$OUT"/incomplete/*_g3-qualification-"$slug"_attempt*; do
        [ ! -e "$f" ] || { echo "NOT FRESH: an earlier attempt of row $slug exists: $f"; bad=1; }
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
    local slug l f st expect rootfs listing id pre_id pre rc bad
    [ "$#" -eq 1 ] || refuse "usage: g3_battery.sh open S1|S2"
    LABEL=$1
    case $LABEL in S1 | S2) ;; *) refuse "usage: g3_battery.sh open S1|S2" ;; esac
    start_log "open-$LABEL"
    take_turn "open $LABEL"
    say "open $LABEL: steps script $SELF sha256 $(sha_of "$SELF")"
    echo "EGW_EXEC_REPO=$EGW_EXEC_REPO EXEC=$EXEC SESSION=${SESSION:-<none>} (the three values of the operator procedure); STATE=$STATE ROWS=$ROWS_DIR OUT=$OUT"

    # Refusals: nothing has been started and nothing is recorded.
    [ ! -e "$EXEC/current_session" ] || refuse "a session is open ($EXEC/current_session names '${SESSION}')"
    [ ! -e "$STATE/session-$LABEL.env" ] || refuse "$STATE/session-$LABEL.env exists: session $LABEL was already opened (a session is opened once; after a halt Rui directs what happens next)"
    for l in S1 S2; do
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
    if [ "$LABEL" = S2 ]; then
        # The authorisation: S2 only if S1 reached its planned end without a halt condition.
        f=$STATE/session-S1.env
        bad=""
        [ -f "$f" ] || bad="no record of S1 ($f)"
        [ -n "$bad" ] || [ "$(state_get "$f" guest_session_close_exit)" = 0 ] || bad="S1's close driver did not end 0"
        [ -n "$bad" ] || [ -z "$(state_get "$f" halt)" ] || bad="S1 recorded a halt: $(state_get "$f" halt)"
        if [ -z "$bad" ]; then
            for slug in $ROWS_S1; do
                [ "$(state_get "$STATE/row-$slug.env" state)" = classified ] || { bad="S1's row $slug is not classified"; break; }
            done
        fi
        if [ -n "$bad" ]; then
            [ -n "${EGW_G3_RUI_GO:-}" ] || refuse "S2 is authorised only if S1 reached its planned end without a halt condition, and: $bad. With Rui's explicit direction, set EGW_G3_RUI_GO to his words (they are recorded)"
            echo "S1 did not reach its planned end without a halt ($bad); EGW_G3_RUI_GO is set and is recorded: $EGW_G3_RUI_GO"
        fi
    fi

    # Checks (packet section 7: S1 starts only if every check matches section 1).
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
    if [ "$LABEL" = S1 ]; then
        expect=$ROOTFS_BEFORE_S1
    else
        expect=$(state_get "$STATE/session-S1.env" rootfs_after_close)
    fi
    rootfs=$(sha_of "$ROOTFS_EXT4") || rootfs=unreadable
    echo "rootfs ext4: $rootfs  $ROOTFS_EXT4"
    echo "expected:    ${expect:-<not recorded>} ($([ "$LABEL" = S1 ] && echo 'packet section 1' || echo "S1's post-close value"))"
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
    [ "$rc" -eq 0 ] || open_halt "preflight.sh exited $rc; see $DRIVER_CONSOLE"
    [ -n "$pre_id" ] && [ -d "$pre" ] || open_halt "the preflight's attempt could not be named from its DRIVER RESULT line"

    environment_copy "$pre" 2>&1 | tee_safe "$STATE/$LABEL-environment-copy.txt"
    rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || open_halt "the environment copy of PM condition 2 failed (see $STATE/$LABEL-environment-copy.txt): the harness rows would not read the labelled capture"

    run_driver "$LABEL" gate_health
    rc=$?
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
            add_src other "$P/$T8_PREFIX.boot_id.pre" "$T8_PREFIX.*" "T8's prefix files: the boot id before the reboot and the pre-reboot and post-reboot twin snapshots" || return 1
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

# run_step STEP: one hx exec whose shell sources $A/environment/STEP.sh. 0 when the step
# ran (whatever the status of its last line: never a verdict); 1 after a HALT (97: the
# preamble or the tunnel never loaded, nothing ran; 74: its console capture was lost).
run_step() {
    local step=$1 rc
    row_set state running
    row_set step "$step"
    row_set pgid "$(own_pgid)"
    row_set pgid_start "$(proc_start "$(own_pgid)")"
    row_set step_started_up "$(up_now)"
    say "row $ROW_SLUG: step $step (hx: one shell, the row file is sourced)"
    hx "$A" "$step" "$STEP_PRE; . '$A/environment/$step.sh'"
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

T8_RELAUNCHED=0
steps_t8() {
    local run1 rc
    run1=$(cat "$SESSION/.current_run" 2> /dev/null)
    row_set t8_first_run "$run1"
    if [ -z "$run1" ] || [ "$run1" = s2 ] || [ -e "$SESSION/boot/s2.started" ] || [ -e "$SESSION/boot/s2.status" ] \
        || [ -e "$SESSION/boot/$run1.status" ]; then
        halt "row t8: the session's boot records are not those of a first boot still running (.current_run='$run1'; boot/s2.* or boot/$run1.status exists): step a was NOT run"
        return
    fi
    run_step t8-a-reboot || return
    if ! no_stop t8-a-reboot; then
        halt "row t8: step a printed STOP: (no pre-reboot snapshot or no boot id) - the guest was NOT rebooted, and nothing further of T8 was run"
        return
    fi
    row_set step t8-wait-qemu-exit
    say "row t8: waiting at most $T8_QEMU_EXIT_S s for the first QEMU ($run1) to exit and ports 2222/8883 to be free (it is never killed)"
    ex "$A" t8-wait-qemu-exit bash -c "$T8_WAIT" _ "$SESSION/boot/$run1.status" "$T8_QEMU_EXIT_S" "$QEMU_EXE_RE"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        halt "row t8: the first QEMU did not exit within $T8_QEMU_EXIT_S s (exit $rc; packet section 4, halt 5). QEMU was NOT killed and is not to be without Rui's decision: the data disk is at stake"
        return
    fi
    row_set step t8-relaunch
    say "row t8: the re-launch through the session's own session_open.sh (run name s2, the same data disk)"
    ex "$A" t8-relaunch bash "$SESSION/scripts/session_open.sh" "$SESSION" s2
    rc=$?
    ex "$A" t8-qemu-after-relaunch bash -c 'pgrep -af "$1"; echo "qemu pgrep exit=$? (0 running, 1 none)"; cat "$2/.current_run"' _ "$QEMU_EXE_RE" "$SESSION"
    if [ "$rc" -ne 0 ]; then
        halt "row t8: the re-launch ended $rc (a re-launch STOP; packet section 4, halt 5): steps b, c and d were NOT run, and T9 is not run"
        return
    fi
    T8_RELAUNCHED=1
    run_step t8-b-return || return
    row_set step t8-tunnel-check
    ex "$A" t8-tunnel-check bash -c '. "$HOME/egw-tcg/tunnel.sh" && tunnel_check && echo "TUNNEL CHECK: the master answers on $TUNNEL_SOCK"'
    rc=$?
    if [ "$rc" -ne 0 ]; then
        halt "row t8: the tunnel is not up after step b (tunnel_check exit $rc): step c (its wait_ready 3600 would poll a dead port) and step d were NOT run"
        return
    fi
    run_step t8-c-snapshot || return
    if no_stop t8-b-return && no_stop t8-c-snapshot \
        && grep -Eq 'REBOOT SHOWN: boot id [0-9a-f-]+ -> [0-9a-f-]+' "$(console_of t8-c-snapshot)"; then
        run_step t8-d-smoke || return
    else
        halt "row t8: the consoles of steps b and c do not show REBOOT SHOWN with no STOP: (packet section 4, halt 5): step d, the post-reboot smoke, was NOT run, and T9 is not run"
    fi
}

# The evidence-only reads of the packet's execution choices for T8: the previous boot's
# journal and its kernel OOM lines. Read-only, after the row's own steps.
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
    if grep -q '^TUNNEL UP$' "$(console_of gate-tunnel-check)" 2> /dev/null; then
        echo "NOTE: the tunnel was DOWN after the row and the preamble of hx reopened it (TUNNEL UP in the gate's console): name it in the classification"
        row_set gate_tunnel "found down after the row and reopened by the preamble of hx"
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
    LABEL=$(row_session "$ROW_SLUG") || refuse "unknown row '$ROW_SLUG' (S1: $ROWS_S1; S2: $ROWS_S2)"
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
    if [ -n "$(state_get "$f" halt)" ]; then
        [ -n "${EGW_G3_RUI_GO:-}" ] || refuse "NOT STARTED: session $LABEL has a recorded halt ($(state_get "$f" halt)). A halt cancels further progress until Rui directs otherwise; with his explicit go, set EGW_G3_RUI_GO to his words (they are recorded)"
        go=$EGW_G3_RUI_GO
        echo "session $LABEL has a recorded halt; EGW_G3_RUI_GO is set and is recorded: $go"
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
        halt "an id of row $ROW_SLUG is not fresh on the host: the row was NOT started and no attempt was created (packet section 4, halt 1)"
        exit 1
    fi

    # The attempt.
    A=$(new_attempt "G3 qualification $ROW_SLUG" official) || { A=""; halt "the attempt of row $ROW_SLUG could not be created: the row was NOT started"; exit 1; }
    ROW_FILE=$STATE/row-$ROW_SLUG.env
    row_set slug "$ROW_SLUG"
    row_set session_label "$LABEL"
    row_set attempt "$A"
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
    say "row $ROW_SLUG: attempt $A (ceiling $ceiling min from now: the operator enforces it with 'term $ROW_SLUG')"

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
        [ "$T8_RELAUNCHED" -eq 0 ] || t8_evidence
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
        "invalid instrumentation") echo "NOTE: invalid instrumentation of the shared chain is a halt condition (packet section 4, halt 2). If this is one, do not run a further row: 'close' and hand back to Rui." ;;
    esac
    case $(state_get "$ROW_FILE" gate) in
        pass) ;;
        *) echo "NOTE: this row's gate did not pass ($(state_get "$ROW_FILE" gate)): no further row starts; 'close' and hand back to Rui." ;;
    esac
    [ "$HALTED" -eq 0 ] || exit 1
    # The halts of the 'row' invocation (a failed gate, a step status 97 or 74) are in the
    # session's state file, not in this invocation's HALTED.
    if [ "$(state_get "$ROW_FILE" gate)" = pass ] && [ -z "$(state_get "$SESSION_FILE" halt)" ]; then
        echo "Next: the next row of session $LABEL, or 'close' after the last one."
    else
        echo "Next: 'close', then hand back to Rui: session $LABEL has a recorded halt (or this row's gate did not pass), and no further row starts without his direction."
    fi
}

# --- term -----------------------------------------------------------------------------
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
# session's state file: S2 opens only on this value.
rootfs_after_close() {
    local line
    line=$(ls "$1"/console/*-artefacts-after-poweroff.stdout.txt 2> /dev/null | tail -n 1)
    if [ -n "$line" ]; then
        line=$(sed -n 's/^\([0-9a-f]\{64\}\)  .*\.ext4$/\1/p' "$line" | head -n 1)
        [ -z "$line" ] || state_set "$SESSION_FILE" rootfs_after_close "$line"
    fi
    echo "rootfs ext4 after the close: ${line:-NOT READ} (S2 opens only on this value)"
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
# an 'open' halted before any session existed) stays recorded 'open' or 'halted', and
# 'open S2' refuses on that record. This script changes the record only on Rui's
# explicit direction (EGW_G3_RUI_GO, recorded) and only when nothing is left to close:
# no current_session, no qemu-system-aarch64 process, no row running or unfinished. The
# halt it records keeps S2 behind his direction as well. It never returns.
close_outside() {
    local l f st="" found=""
    [ ! -e "$EXEC/current_session" ] \
        || refuse "no open session: $EXEC/current_session names '${SESSION}', which is not a session directory. Nothing was changed; hand back to Rui"
    for l in S1 S2; do
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
        # The guest is gone (lost, or T8's re-launch did not bring it back): the units
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
    echo "  1. seal the operator records ($STATE: the session and row state files, console/, the driver consoles, the classification notes) as HIST_<date>-g3-battery-operator-records;"
    echo "  2. write output_test/decisions/<date>_g3-battery-$(echo "$LABEL" | tr 'S' 's')-results.md (every row and its class; no G3 claim);"
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
    for l in S1 S2; do
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
            echo "usage: EGW_EXEC_REPO=\$HOME/egw-exec/repo bash g3_battery.sh open S1|S2 | row <slug> | classify <slug> <status> <validity> <outcome> <reason> <next-action> | term <slug> | close | status" >&2
            return 2
            ;;
    esac
}
# One line, read whole before it runs: bash reads a script as it executes it, and the
# 'exit' ends the shell before anything after this line could be read from a file that
# changed in the meantime.
main "$@"; exit $?
