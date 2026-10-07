#!/bin/bash
# Host preparation of the G3 qualifying battery (packet revision 2 of
# 2026-10-01, section 7; authorised by Rui on 2026-10-02): the tools' clean
# clone moved to the merge of PR #53 (80e833f, tree dad725d) without
# discarding anything, the helper regenerated from that commit's runbook
# (predecessor kept) and checked, every identity of the packet's section 1
# that the host holds checked, the run ids and plan entries confirmed unused
# on the host and, offline and read-only, on the guest root file system.
# No guest is started; the controller image, the guest deployment and the
# data disk are NOT touched.
# Usage (WSL, login shell): g3_hostprep.sh <record-dir>
set -u
TOOLS=80e833f44f647fe9cd8f5e99d3abf3c444de95aa
TREE=dad725d0bebc25c91712af2aa2705d5eeb92044f
IMAGE=489bc9e5b5b0660026ea2630b8d1d124049ba2ce
HELPER_SHA=e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb
HELPER_LINES=545
C=/home/ruisth/egw-exec/repo
H=/home/ruisth/egw-tcg/itest-helpers.sh
PY=/home/ruisth/egw-exec/venv/bin/python
ROOTFS=/home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
IDS="itest-smoke-01-q1 itest-smoke-02-q1 itest-smoke-03-q1 itest-3dev-01-q1 itest-invalid-01-q1 itest-dup-01-q1 itest-dup-02-q1 itest-dropout-01-q1 itest-mongo-fault-01-q1 itest-ditto-fault-01-q1 itest-reboot-q1 itest-post-reboot-01-q1 itest-tls-wrongca-q1 itest-auth-wrongpw-q1 itest-notls-q1"
PLAN_IDS="nominal-r02 controller_restart-r03"
PKG=${1:?usage: g3_hostprep.sh <record-dir>}
[ ! -e "$PKG/console.txt" ] || { echo "STOP: $PKG/console.txt exists - never overwritten"; exit 2; }
mkdir -p "$PKG" || exit 2
exec > >(tee -a "$PKG/console.txt") 2>&1
now() { date -u +%FT%T.%3NZ; }
step() { echo; echo "## $(now) $*"; }
fail() { echo "STOP: $*"; echo "outcome=failed (at $(now))"; exit 1; }
want() { # want <label> <expected sha256> <file>
    local got; got=$(sha256sum "$3" 2> /dev/null | cut -d' ' -f1)
    echo "$1: $got  $3"
    [ "$got" = "$2" ] || fail "$1 is ${got:-unreadable}, the packet names $2"
}

step "no guest, no open session"
Q=$(ps -eo pid=,args= | awk '{n=split($2,a,"/"); if (a[n]=="qemu-system-aarch64") print}')
[ -z "$Q" ] || { echo "$Q"; fail "a qemu-system-aarch64 process is running"; }
[ ! -e /home/ruisth/egw-exec/current_session ] || fail "a session is open ($(cat /home/ruisth/egw-exec/current_session))"
echo "no qemu-system-aarch64, no current_session"

step "tools clone $C: state before"
echo "HEAD=$(git -C "$C" rev-parse HEAD) branch=$(git -C "$C" symbolic-ref -q --short HEAD || echo '(detached)')"
git -C "$C" for-each-ref --format='%(objectname) %(refname)' refs/heads | tee "$PKG/branches-before.txt"
ST=$(git -C "$C" status --porcelain) || fail "git status failed"
[ -z "$ST" ] || { echo "$ST"; fail "$C has uncommitted or untracked work: not moved"; }
echo "status: clean"

step "fetch $TOOLS from the Windows repository (its origin/dev, the merge of PR #53)"
git -C "$C" fetch --quiet origin refs/remotes/origin/dev || fail "fetch failed"
FH=$(git -C "$C" rev-parse FETCH_HEAD); echo "FETCH_HEAD=$FH"
[ "$FH" = "$TOOLS" ] || fail "the fetched origin/dev is $FH, not $TOOLS: the identity moved, stop"
git -C "$C" -c advice.detachedHead=false checkout --quiet --detach "$TOOLS" || fail "checkout refused"
HD=$(git -C "$C" rev-parse HEAD); T=$(git -C "$C" rev-parse 'HEAD^{tree}'); echo "HEAD=$HD tree=$T"
[ "$HD" = "$TOOLS" ] && [ "$T" = "$TREE" ] || fail "$C is not at $TOOLS / $TREE"
[ -z "$(git -C "$C" status --porcelain)" ] || fail "$C is not clean after the checkout"
git -C "$C" for-each-ref --format='%(objectname) %(refname)' refs/heads > "$PKG/branches-after.txt"
cmp "$PKG/branches-before.txt" "$PKG/branches-after.txt" || fail "a branch changed"
echo "clean; every branch unchanged; parents: $(git -C "$C" rev-parse HEAD^1 HEAD^2 | tr '\n' ' ')"
echo "the cleared head a20be8f has the same tree: $(git -C "$C" rev-parse 'a20be8f957b23b75aa086a6740829dcb9741344b^{tree}')"
for d in src/egw_controller src/egw_simulator src/schemas src/deployment src/Dockerfile src/requirements-runtime.lock src/requirements.lock src/pyproject.toml src/CONTRACTS.md; do
    [ -z "$(git -C "$C" diff --stat "$IMAGE" "$TOOLS" -- "$d")" ] || fail "$d differs from the image commit $IMAGE"
done
echo "controller, simulator, schemas, deployment, Dockerfile, locks, pyproject and CONTRACTS identical to $IMAGE (no rebuild)"
"$PY" -c 'import egw_experiments, egw_experiments.n1_report, egw_experiments.proved_down, egw_experiments.itest_reconcile as r; print(egw_experiments.__file__); print(sorted(r.COMMANDS))' \
    || fail "the venv does not import the candidate's modules"

step "candidate identities held on the host (packet section 1)"
want runbook c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae "$C/docs/setup/qemu_integrated_gateway.md"
want local_export 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b "$C/src/egw_experiments/local_export.py"
want fetch_started_at 9c6dc824c885ce6d2edacdfb5fe4a4db4a96b6e0b6454f93300ee1b007421827 "$C/tools/session/fetch_started_at.sh"
want images.lock.env 8a9a05df7c9ca2eeb310e8e7702f16f854fb91771fb089a9a2109d638ae4a648 "$C/src/deployment/images.lock.env"
want compose.yaml 1a32f6c2bd9e24eee075ef569828aa41ad6a7a7b260d4436e588dc9ca74d5982 "$C/src/deployment/compose.yaml"
want mosquitto.conf ea37827cccd94ef3870c62b77ffbe0b34261f7f213f243212f03121219d99615 "$C/src/deployment/mosquitto/config/mosquitto.conf"
want CONTRACTS 247e3b02a1ffc8e30da3f9df701db5f851f018505ecb9f907b54562b9cf095c9 "$C/src/CONTRACTS.md"
want tunnel.sh 38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1 /home/ruisth/egw-tcg/tunnel.sh
want ca.crt 556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff /home/ruisth/egw-tcg/ca.crt
want campaign_plan 5d902a429b9fd4e25f2c4586341f94be2853104fe12a76b88852a1ed30203e23 /home/ruisth/egw-tcg/pilot/campaign_plan.json
want controller-record 79e7d2105be035911e9fe596f609a77775b578f0578cab1bde77f0d610aa2022 /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt
want controller-archive 9d347be45e886da09bb30d1029f30f7c5a70fd15ff75343856f0b3368bce841d /home/ruisth/egw-images/egw-controller-0.1.0-arm64.tar
grep -E '^(image_id|source_commit|archive_sha256)=' /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt
grep -q '^image_id=sha256:9a293fe13b1a020560d43fee328632a9ef8d91dec830899f18d3e2d964aa5f46$' /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt \
    || fail "the recorded controller image is not 9a293fe13b1a..."
echo "git trees: src/deployment=$(git -C "$C" rev-parse "$TOOLS:src/deployment") src/schemas=$(git -C "$C" rev-parse "$TOOLS:src/schemas")"
[ "$(git -C "$C" rev-parse "$TOOLS:src/deployment")" = e056d389f7dd640c142bf714bb8ceb389ec460c2 ] || fail "src/deployment tree is not e056d389..."
[ "$(git -C "$C" rev-parse "$TOOLS:src/schemas")" = 1d5284cf28bbabc5c7ea554d5a5366faec5fcf95 ] || fail "src/schemas tree is not 1d5284cf..."
EGW_EXEC_REPO=$C; . "$C/tools/session/common.sh"; DRIVERS=$REPO/tools/session   # common.sh derives DRIVERS from $0
ids=$(repo_identity) || fail "repo_identity failed"
echo "repo_identity: $ids"
echo "$ids" | grep -q '4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5' || fail "drivers_sha256 is not 4a6a572d..."
echo "harness environment input today (replaced after each preflight, PM condition 2; kept beside itself then):"
sha256sum /home/ruisth/egw-tcg/sut_environment.json
echo "yocto checkout (launcher): $(git -C /home/ruisth/yocto/egw rev-parse HEAD), porcelain lines: $(git -C /home/ruisth/yocto/egw status --porcelain | wc -l)"
want run-qemu-integrated 67da61d77a2548122afc34338493165290f6d1ac1dbc2ebccfd6d800dd0438e1 /home/ruisth/yocto/egw/src/yocto/scripts/run-qemu-integrated.sh
echo "deploy_source_commit.txt: $(cat /home/ruisth/egw-tcg/deploy_source_commit.txt 2> /dev/null) (the deployment tree on the guest)"
want rootfs-ext4 c49500a9a7751a8753b8af44e2d76bd1d2d0e694b29524142cabf896f85e7260 "$ROOTFS"

step "helper regenerated from the $TOOLS runbook (predecessor kept) and checked"
sha256sum "$H"
"$PY" "$C/tools/session/regen_helpers.py" "$C/docs/setup/qemu_integrated_gateway.md" "$H" || fail "regen_helpers.py failed"
"$PY" "$C/tools/session/proof_helpers_check.py" "$C/docs/setup/qemu_integrated_gateway.md" "$H" || fail "the helper is not the $TOOLS runbook's"
GOT=$(sha256sum "$H" | cut -d' ' -f1); N=$(wc -l < "$H"); echo "helper sha256=$GOT lines=$N"
[ "$GOT" = "$HELPER_SHA" ] && [ "$N" = "$HELPER_LINES" ] || fail "the regenerated helper is $GOT ($N lines), not $HELPER_SHA ($HELPER_LINES)"
bash -n "$H" || fail "the regenerated helper does not parse"
ls -l "$H"*

step "run ids and plan entries unused on the host"
for id in $IDS; do
    for f in /home/ruisth/egw-tcg/itest/$id /home/ruisth/egw-tcg/itest/$id.* /home/ruisth/egw-tcg/itest-replay/$id /home/ruisth/egw-tcg/pilot/results/raw/$id; do
        [ ! -e "$f" ] || fail "$f exists: $id is not fresh"
    done
    echo "fresh on the host: $id"
done
ls -d /home/ruisth/egw-exec/attempts/*g3-qualification* /mnt/c/Users/ruimf/Documents/Projeto\ Mestrado/output_test/runs/*/*g3-qualification* 2> /dev/null \
    && fail "an earlier g3-qualification attempt exists"
"$PY" - "$PLAN_IDS" << 'EOF' || fail "a plan entry is not planned and unused"
import json, os, sys
plan = json.load(open("/home/ruisth/egw-tcg/pilot/campaign_plan.json"))
runs = {r["run_id"]: r for r in plan["runs"]}
bad = 0
for rid in sys.argv[1].split():
    r = runs.get(rid)
    raw = os.path.exists("/home/ruisth/egw-tcg/pilot/results/raw/" + rid)
    sut = os.path.exists("/home/ruisth/egw-tcg/itest/" + rid + ".sut")
    print(rid, "seed", r and r.get("seed"), "status", r and r.get("status"), "raw_dir", raw, "sut_dir", sut,
          "condition", r and r.get("condition_id"), "duration_s", r and r.get("duration_s"), "warmup_s", r and r.get("warmup_s"))
    if not r or r.get("status") != "planned" or raw or sut:
        bad = 1
print("master_seed", plan.get("master_seed"))
sys.exit(bad)
EOF
echo "pilot/results/processed today (T1's and T6's analyze rewrite it; snapshotted in each row):"
ls -l /home/ruisth/egw-tcg/pilot/results/processed 2> /dev/null | head -20

step "run ids unused on the guest root file system (offline, read-only: debugfs -c; no QEMU, no session)"
command -v debugfs > /dev/null || fail "debugfs is not available"
debugfs -c -R "ls -l /opt/egw/deployment/data/events" "$ROOTFS" > "$PKG/guest-events-listing.txt" 2> "$PKG/guest-events-listing.stderr.txt" \
    || fail "the guest events directory could not be listed"
echo "guest event directories listed: $(grep -c . "$PKG/guest-events-listing.txt") lines"
awk '{print $NF}' "$PKG/guest-events-listing.txt" | sort -u > "$PKG/guest-events-names.txt"
cat "$PKG/guest-events-names.txt" | tr '\n' ' '; echo
for id in $IDS $PLAN_IDS; do
    grep -qxF -- "$id" "$PKG/guest-events-names.txt" && fail "the guest holds data/events/$id: $id is not fresh on the guest"
    case "$id" in itest-reboot-q1) grep -q -- "^itest-reboot-q1" "$PKG/guest-events-names.txt" && fail "the guest holds an itest-reboot-q1* directory";; esac
    echo "fresh on the guest: $id"
done
want rootfs-ext4-after-listing c49500a9a7751a8753b8af44e2d76bd1d2d0e694b29524142cabf896f85e7260 "$ROOTFS"

echo
echo "outcome=prepared (at $(now))"
