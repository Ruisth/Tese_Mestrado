#!/bin/bash
# tools/compare/measure_base.sh <scenario> - the MEASURED BASE of one scenario for the minimal
# comparison (order of 2026-10-18): the work disks are rebuilt from the sealed bases, the stack is
# installed once by the normal `tf.sh <scenario> apply` (pinned images, verified controller, the
# same configuration), the guest is closed by `tf.sh <scenario> stop`, and the two work disks are
# copied, with their sha256, to $EGW_COMPARE_ROOT/measure/base/<scenario>/. Every measured run
# starts from a fresh copy of those two files (measure_run.sh), so nothing is installed during a
# measured boot and no run inherits another run's data. The application data in the base is the
# state right after provisioning: no event was published to it.
#
# Runs only with no guest running and no pilot session open. It refuses while a measured base
# exists for the scenario (removing one is a decision taken by hand, never by a script). The
# destroy of the current work disks goes through Terraform, so the workspace stays consistent;
# bases, logs and results are preserved as always.
# Exit: 0 base written; 1 a lifecycle step failed (what exists is left in place, the guest closed
#       where it could be); 2 prerequisite or guard (nothing done).
# Transcript: $EGW_COMPARE_ROOT/measure/logs/base-<scenario>-<stamp>.log
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"
[ $# -eq 1 ] || { echo "usage: measure_base.sh <scenario>" >&2; exit 2; }
scenario=$1
scenario_load "$scenario"
scenario_dirs
MEASURE=$COMPARE_ROOT/measure
BASE=$MEASURE/base/$scenario
mkdir -p "$MEASURE/logs" "$MEASURE/base"
LOG=$MEASURE/logs/base-$scenario-$(stamp).log
exec > >(tee -a "$LOG") 2>&1
echo "MEASURE-BASE $scenario: $(utc_now) log $LOG"

# --- guards (nothing starts if any fails) ---------------------------------------------------------
pilot_session_open && die "a pilot session is open ($COMPARE_EXEC/current_session): nothing done"
if o=$(qemu_others); then echo "$o"; die "another qemu-system-aarch64 is running: nothing done"; elif [ $? -eq 2 ]; then die "pgrep could not answer: nothing done"; fi
own_pid > /dev/null 2>&1 && die "the $scenario guest is running: close it first (tf.sh $scenario stop)"
[ ! -e "$BASE" ] || die "a measured base exists: $BASE (removing it is a decision taken by hand)"
for tool in cp sha256sum du; do command -v "$tool" > /dev/null 2>&1 || die "host tool missing: $tool"; done

# --- 1. rebuild the work disks and install the stack by the final commands --------------------------
echo "== 1. destroy the current work disks through Terraform (bases, logs and results are kept)"
EGW_COMPARE_AUTO_APPROVE=1 bash "$HERE/tf.sh" "$scenario" destroy || { echo "STOP: tf.sh $scenario destroy failed"; exit 1; }
echo "== 2. tf.sh $scenario apply: prepare, boot, provision, healthy"
EGW_COMPARE_HEALTH_STEP_S=${EGW_COMPARE_HEALTH_STEP_S:-5} bash "$HERE/tf.sh" "$scenario" apply || { echo "STOP: tf.sh $scenario apply failed; the guest, if running, is left for inspection (tf.sh $scenario stop closes it)"; exit 1; }
PROVISION_RESULT=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get("result", ""))' "$S_DIR/state/provision.json" 2> /dev/null || true)
[ "$PROVISION_RESULT" = ok ] || { echo "STOP: provisioning result is '$PROVISION_RESULT', not ok; closing"; bash "$HERE/tf.sh" "$scenario" stop; exit 1; }
echo "== 3. tf.sh $scenario stop"
bash "$HERE/tf.sh" "$scenario" stop || { echo "STOP: tf.sh $scenario stop failed (exit $?): the guest was not killed; nothing copied"; exit 1; }
own_pid > /dev/null 2>&1 && { echo "STOP: the guest is still running after the stop; nothing copied"; exit 1; }

# --- 2. copy the two work disks, seal, record -------------------------------------------------------
echo "== 4. copy the work disks to $BASE (sparse) and seal"
mkdir -p "$BASE/record" || exit 1
cp --sparse=always "$S_ROOT_DISK" "$BASE/root.qcow2" || { echo "STOP: copy of the root overlay failed"; exit 1; }
cp --sparse=always "$S_DATA_DISK" "$BASE/data.img" || { echo "STOP: copy of the data disk failed"; exit 1; }
chmod 0444 "$BASE/root.qcow2" "$BASE/data.img"
(cd "$BASE" && sha256sum root.qcow2 data.img > SHA256SUMS && sha256sum -c --quiet SHA256SUMS) || { echo "STOP: seal of the base failed"; exit 1; }
cp -p "$S_DIR/state/provision.json" "$S_MANIFEST" "$S_DIR/state/argv.txt" "$BASE/record/" 2> /dev/null
cp -p "$S_DIR"/logs/up-*.log "$S_DIR"/logs/provision-*.log "$BASE/record/" 2> /dev/null
REPO=$(cd "$HERE/../.." && pwd)
COMMIT=$(git -C "$REPO" rev-parse HEAD 2> /dev/null || echo unknown)
python3 - "$BASE/base.json" "$scenario" "$(utc_now)" "$COMMIT" "$BASE" "$(du -k "$BASE/root.qcow2" | cut -f1)" "$(du -k "$BASE/data.img" | cut -f1)" \
    "$(du -k --apparent-size "$BASE/root.qcow2" | cut -f1)" "$(du -k --apparent-size "$BASE/data.img" | cut -f1)" << 'PY'
import json, sys
path, scenario, utc, commit, base, root_alloc, data_alloc, root_app, data_app = sys.argv[1:]
sums = {}
with open(f"{base}/SHA256SUMS", encoding="utf-8") as f:
    for line in f:
        digest, name = line.split(None, 1)
        sums[name.strip().lstrip("*")] = digest
record = {
    "scenario": scenario, "utc": utc, "repo_head": commit, "base_dir": base,
    "root_qcow2": {"sha256": sums.get("root.qcow2"), "allocated_kib": int(root_alloc), "apparent_kib": int(root_app)},
    "data_img": {"sha256": sums.get("data.img"), "allocated_kib": int(data_alloc), "apparent_kib": int(data_app)},
    "application_data": "state right after provisioning; no event published",
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)
    f.write("\n")
PY
cat "$BASE/base.json"
echo "MEASURE-BASE $scenario: result=ok base=$BASE"
