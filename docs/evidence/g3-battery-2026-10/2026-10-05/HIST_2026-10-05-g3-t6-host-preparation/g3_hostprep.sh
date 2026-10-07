#!/bin/bash
# Host preparation of session S4 of the G3 qualification (test 6 only, plan entry
# controller_restart-r04; request of 2026-10-05 in output_test/decisions/): the
# tools' clean clone moved from S3's 8e49261 to the merge of PR #57 (1fd9792,
# tree 14f89c4) without discarding anything - local changes, or a HEAD that is
# neither of the two, are a stop before anything is fetched - the helper
# regenerated from that commit's runbook (predecessor kept) and checked, every
# identity of the request's section 2 that the host holds compared (the new
# drivers, collector and deployment tree included), controller_restart-r04 and
# the attempt number of row t6 confirmed unused on the host and, offline and
# read-only, on the guest root file system, the data disk listed (never hashed),
# and, last, the plan entry controller_restart-r04 added to the pilot plan by the
# merged plan-supplement (the predecessor kept in the record).
# No guest is started; the controller image, the guest deployment and the data
# disk are NOT touched.
# Usage (WSL, login shell): g3_hostprep.sh <record-dir>
set -u
export PYTHONDONTWRITEBYTECODE=1   # S3: the venv's python leaves no bytecode in the clone
# S4 (brief, HOST): the merge of PR #57 and its tree. S3's commit is the only other HEAD the
# clone may be at (the battery's 80e833f, admitted in S3, is not admitted any more).
TOOLS=1fd9792bb76f02c6948f33887207dba4837202db
TREE=14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec
PREVIOUS=8e492613d36490a560ae56beabd6d5c2c01a8696    # S4: S3's commit, the clone's HEAD since S3's preparation (was BATTERY)
REVIEWED=e375026d84e549f8f0ebfed1899f8c31816152a8    # the reviewed head of PR #57: the same tree as the merge
IMAGE=489bc9e5b5b0660026ea2630b8d1d124049ba2ce
HELPER_SHA=e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb
HELPER_LINES=545
# S4 (brief, fixed values): S3's second close (HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02,
# state/session-S3.env, rootfs_after_close).
ROOTFS_SHA=6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4
# S4 (brief, fixed values): the identities that changed against S3's 8e49261 (request section 2).
DRIVERS_SHA=2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed          # repo_identity, 38 files (was 4a6a572d...)
COLLECTOR_SHA=9e678b024bde66bacc65fea936d05ca226a82e73c86d1cc23a9cf9f8fe8d9b97        # src/deployment/scripts/collect-resources.sh (was 11444c0a...)
DEPLOY_TREE=573e902b67339a3e6bfc784321dc2735cece09fc       # src/deployment at TOOLS
DEPLOY_TREE_CANDIDATE=e056d389f7dd640c142bf714bb8ceb389ec460c2   # src/deployment at IMAGE and at S3's commit
# S4 (brief, HOST, the plan entry): the pilot plan before (95 entries) and after (96) the entry.
PLAN=/home/ruisth/egw-tcg/pilot/campaign_plan.json
PLAN_BEFORE_SHA=c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60
PLAN_AFTER_SHA=61d55940fcccdb942ff508ab6fc920b0fa163837ef7459438d789a1879b1eaac
C=/home/ruisth/egw-exec/repo
H=/home/ruisth/egw-tcg/itest-helpers.sh
PY=/home/ruisth/egw-exec/venv/bin/python
ROOTFS=/home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
# S3: the paths guest_session_open.sh records its identities from (guest_common.sh: OLD, BUILD, DEP)
Y=/home/ruisth/yocto/egw
BUILD=$Y/src/yocto/build-integrated
DEP=$BUILD/tmp/deploy/images/qemuarm64
ATT=/home/ruisth/egw-exec/attempts
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"   # not OUT: common.sh, sourced below, sets OUT
# S4 (brief, HOST): the one run identifier of S4, and the data disk (guest_common.sh's DATA_DISK)
# with the size S3's open driver listed (request section 2).
RID=controller_restart-r04
DATA_DISK=/home/ruisth/yocto/egw-integrated/egw-data.img
DATA_DISK_SIZE=34359738368
T6_ADMITTED=20261003T132936Z_g3-qualification-t6_attempt01   # S4: S2's invalid attempt of row t6, kept
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
    [ "$got" = "$2" ] || fail "$1 is ${got:-unreadable}, S4 expects $2"
}

echo "g3_hostprep.sh (S4) sha256 $(sha256sum "$0" | cut -d' ' -f1)"
step "no guest, no open session"
Q=$(ps -eo pid=,args= | awk '{n=split($2,a,"/"); if (a[n]=="qemu-system-aarch64") print}')
[ -z "$Q" ] || { echo "$Q"; fail "a qemu-system-aarch64 process is running"; }
[ ! -e /home/ruisth/egw-exec/current_session ] || fail "a session is open ($(cat /home/ruisth/egw-exec/current_session))"
echo "no qemu-system-aarch64, no current_session"

step "tools clone $C: state before (S4: local changes, or a HEAD that is neither $PREVIOUS nor $TOOLS, are a stop; nothing is discarded)"
H0=$(git -C "$C" rev-parse HEAD) || fail "git rev-parse HEAD failed in $C"
echo "HEAD=$H0 branch=$(git -C "$C" symbolic-ref -q --short HEAD || echo '(detached)')"
# S4 (bounded check of 2026-10-05, F3): git's own status is kept (no pipe) and an empty listing is a stop.
git -C "$C" for-each-ref --format='%(objectname) %(refname)' refs/heads > "$PKG/branches-before.txt" \
    || fail "git for-each-ref failed in $C"
[ -s "$PKG/branches-before.txt" ] || fail "the branch listing of $C is empty"
cat "$PKG/branches-before.txt"
ST=$(GIT_OPTIONAL_LOCKS=0 git -C "$C" status --porcelain) || fail "git status failed"
[ -z "$ST" ] || { echo "$ST"; fail "$C has local changes (uncommitted or untracked work): nothing was fetched, moved or discarded"; }
echo "status: clean"
case $H0 in
    "$PREVIOUS") echo "HEAD is S3's commit: the clone is moved to $TOOLS below" ;;
    "$TOOLS") echo "HEAD is already $TOOLS: the checkout below changes nothing" ;;
    *) fail "the HEAD of $C is $H0, neither $PREVIOUS nor $TOOLS: nothing was fetched, moved or discarded" ;;
esac

step "fetch from the clone's origin (the Windows repository: its origin/dev, where PR #57 was merged) and check out $TOOLS detached"
git -C "$C" fetch --quiet origin refs/remotes/origin/dev || fail "fetch failed (the clone is still at $H0)"
FH=$(git -C "$C" rev-parse FETCH_HEAD) || fail "FETCH_HEAD could not be read (the clone is still at $H0)"
echo "FETCH_HEAD=$FH"
git -C "$C" cat-file -e "$TOOLS^{commit}" || fail "the commit $TOOLS is not in the clone after the fetch (the clone is still at $H0)"
git -C "$C" merge-base --is-ancestor "$TOOLS" "$FH" || fail "$TOOLS is neither the fetched tip $FH nor an ancestor of it (the clone is still at $H0)"
if [ "$FH" = "$TOOLS" ]; then echo "the fetched tip is $TOOLS itself"
else echo "the fetched tip $FH is a descendant of $TOOLS (accepted: the tip need not be the commit); the clone goes to $TOOLS, not to the tip"; fi
git -C "$C" -c advice.detachedHead=false checkout --quiet --detach "$TOOLS" || fail "checkout refused"
HD=$(git -C "$C" rev-parse HEAD); T=$(git -C "$C" rev-parse 'HEAD^{tree}'); echo "HEAD=$HD tree=$T"
[ "$HD" = "$TOOLS" ] && [ "$T" = "$TREE" ] || fail "$C is not at $TOOLS / $TREE"
ST=$(GIT_OPTIONAL_LOCKS=0 git -C "$C" status --porcelain) || fail "git status failed after the checkout"
[ -z "$ST" ] || { echo "$ST"; fail "$C is not clean after the checkout"; }
git -C "$C" for-each-ref --format='%(objectname) %(refname)' refs/heads > "$PKG/branches-after.txt" \
    || fail "git for-each-ref failed in $C"   # S4 (bounded check of 2026-10-05, F3)
cmp "$PKG/branches-before.txt" "$PKG/branches-after.txt" || fail "a branch changed"
echo "clean; every branch unchanged; parents: $(git -C "$C" rev-parse HEAD^1 HEAD^2 | tr '\n' ' ')"
RT=$(git -C "$C" rev-parse "$REVIEWED^{tree}") || fail "the reviewed head $REVIEWED is not in the clone"
echo "the reviewed head $REVIEWED has the tree $RT"
[ "$RT" = "$TREE" ] || fail "the reviewed head's tree is not $TREE"
CH=$(git -C "$C" diff --name-only "$PREVIOUS" "$TOOLS") || fail "git diff $PREVIOUS $TOOLS failed"
echo "files that differ between S3's $PREVIOUS and $TOOLS: $(printf '%s\n' "$CH" | grep -c .)"
printf '%s\n' "$CH" | sed 's/^/  /'
# S4 (brief, HOST): S3 stopped here on any file under tools/ or under src/ outside src/tests,
# because S3's tools were the battery's. S4's tools DID change (request section 2: the drivers,
# the collector, the harness): what changed is fixed by TREE above and compared by hash below
# (drivers_sha256, the collector, the deployment tree), so this list is recorded, not judged.
echo "(recorded, not judged: the tree is $TREE; the drivers, the collector and the deployment tree are compared below)"
git -C "$C" cat-file -e "$IMAGE^{commit}" || fail "the image commit $IMAGE is not in the clone"
# S4 (brief, HOST): src/deployment left the loop: it differs from the image commit by exactly
# the collector and its README (request section 2), compared just below.
for d in src/egw_controller src/egw_simulator src/schemas src/Dockerfile src/requirements-runtime.lock src/requirements.lock src/pyproject.toml src/CONTRACTS.md; do
    # S4 (bounded check of 2026-10-05, F3): a failed git, or a path at neither commit, is a stop, never 'identical'.
    git -C "$C" cat-file -e "$TOOLS:$d" && git -C "$C" cat-file -e "$IMAGE:$d" || fail "$d is not in both $IMAGE and $TOOLS"
    out=$(git -C "$C" diff --stat "$IMAGE" "$TOOLS" -- "$d") || fail "git diff failed for $d"
    [ -z "$out" ] || fail "$d differs from the image commit $IMAGE"
done
DD=$(git -C "$C" diff --name-only "$IMAGE" "$TOOLS" -- src/deployment) || fail "git diff $IMAGE $TOOLS -- src/deployment failed"
echo "src/deployment files that differ from $IMAGE: $(printf '%s\n' "$DD" | tr '\n' ' ')"
[ "$DD" = $'src/deployment/README.md\nsrc/deployment/scripts/collect-resources.sh' ] \
    || fail "src/deployment differs from the image commit $IMAGE by something other than exactly README.md and scripts/collect-resources.sh"
echo "controller, simulator, schemas, Dockerfile, locks, pyproject and CONTRACTS identical to $IMAGE; src/deployment differs only by README.md and the collector (no rebuild)"
# S4 (brief, HOST): the venv must import the clone's merged modules (plan-supplement below and
# the harness of row t6 run from it): the module path is compared, and g3-t6 must be defined.
VI=$("$PY" -c 'import egw_experiments, egw_experiments.n1_report, egw_experiments.proved_down, egw_experiments.itest_reconcile as r, egw_experiments.plan_gen as g; print(egw_experiments.__file__); print(sorted(r.COMMANDS)); print(sorted(g.SUPPLEMENTS))') \
    || fail "the venv does not import the candidate's modules"
printf '%s\n' "$VI"
[ "$(printf '%s\n' "$VI" | head -n 1)" = "$C/src/egw_experiments/__init__.py" ] || fail "the venv imports egw_experiments from elsewhere than $C/src"
printf '%s\n' "$VI" | tail -n 1 | grep -qF "'g3-t6'" || fail "the imported plan_gen defines no supplement g3-t6"

step "identities held on the host (request section 2; the kernel, qemuboot.conf, the QEMU binary and the Yocto checkout are compared as in S3; the drivers, the collector and the deployment tree are S4's new values)"
want runbook 317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f "$C/docs/setup/qemu_integrated_gateway.md"
N=$(wc -l < "$C/docs/setup/qemu_integrated_gateway.md"); echo "runbook lines: $N"
[ "$N" = 1624 ] || fail "the runbook has $N lines, not 1624"
want extraction-rule-source b63ef7d88ae22e623bf381ef0dc3e6fbfbf050d966d5b0e09cc961ee169d83be "$C/src/tests/test_runbook_itest_helpers.py"
want local_export 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b "$C/src/egw_experiments/local_export.py"
want fetch_started_at 9c6dc824c885ce6d2edacdfb5fe4a4db4a96b6e0b6454f93300ee1b007421827 "$C/tools/session/fetch_started_at.sh"
want images.lock.env 8a9a05df7c9ca2eeb310e8e7702f16f854fb91771fb089a9a2109d638ae4a648 "$C/src/deployment/images.lock.env"
want compose.yaml 1a32f6c2bd9e24eee075ef569828aa41ad6a7a7b260d4436e588dc9ca74d5982 "$C/src/deployment/compose.yaml"
want mosquitto.conf ea37827cccd94ef3870c62b77ffbe0b34261f7f213f243212f03121219d99615 "$C/src/deployment/mosquitto/config/mosquitto.conf"
want CONTRACTS 247e3b02a1ffc8e30da3f9df701db5f851f018505ecb9f907b54562b9cf095c9 "$C/src/CONTRACTS.md"
want collector "$COLLECTOR_SHA" "$C/src/deployment/scripts/collect-resources.sh"   # S4 (brief, HOST): the new collector
want tunnel.sh 38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1 /home/ruisth/egw-tcg/tunnel.sh
want ca.crt 556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff /home/ruisth/egw-tcg/ca.crt
want controller-record 79e7d2105be035911e9fe596f609a77775b578f0578cab1bde77f0d610aa2022 /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt
want controller-archive 9d347be45e886da09bb30d1029f30f7c5a70fd15ff75343856f0b3368bce841d /home/ruisth/egw-images/egw-controller-0.1.0-arm64.tar
grep -E '^(image_id|source_commit|archive_sha256)=' /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt
grep -q '^image_id=sha256:9a293fe13b1a020560d43fee328632a9ef8d91dec830899f18d3e2d964aa5f46$' /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt \
    || fail "the recorded controller image is not 9a293fe13b1a..."
echo "git trees: src/deployment=$(git -C "$C" rev-parse "$TOOLS:src/deployment") src/schemas=$(git -C "$C" rev-parse "$TOOLS:src/schemas")"
# S4 (brief, HOST): the clone's deployment tree is 573e902b, the candidate's e056d389, and the two
# differ in exactly README.md and scripts/collect-resources.sh.
[ "$(git -C "$C" rev-parse "$TOOLS:src/deployment")" = "$DEPLOY_TREE" ] || fail "src/deployment tree is not $DEPLOY_TREE"
[ "$(git -C "$C" rev-parse "$IMAGE:src/deployment")" = "$DEPLOY_TREE_CANDIDATE" ] || fail "the image commit's src/deployment tree is not $DEPLOY_TREE_CANDIDATE"
DT=$(git -C "$C" diff --name-only "$DEPLOY_TREE_CANDIDATE" "$DEPLOY_TREE") || fail "git diff $DEPLOY_TREE_CANDIDATE $DEPLOY_TREE failed"
echo "deployment trees: $DEPLOY_TREE_CANDIDATE (candidate) and $DEPLOY_TREE (clone) differ in: $(printf '%s\n' "$DT" | tr '\n' ' ')"
[ "$DT" = $'README.md\nscripts/collect-resources.sh' ] || fail "the deployment trees do not differ in exactly README.md and scripts/collect-resources.sh"
[ "$(git -C "$C" rev-parse "$TOOLS:src/schemas")" = 1d5284cf28bbabc5c7ea554d5a5366faec5fcf95 ] || fail "src/schemas tree is not 1d5284cf..."
EGW_EXEC_REPO=$C; . "$C/tools/session/common.sh"; DRIVERS=$REPO/tools/session   # common.sh derives DRIVERS from $0
[ "$REPO" = "$C" ] && [ "$PY" = /home/ruisth/egw-exec/venv/bin/python ] \
    || fail "common.sh set REPO=$REPO PY=$PY: an EGW_* variable of the environment redirects it"
ids=$(repo_identity) || fail "repo_identity failed"
echo "repo_identity: $ids"
echo "$ids" | grep -q "\"repo_commit\": \"$TOOLS\"" || fail "repo_identity does not name $TOOLS"
echo "$ids" | grep -q "\"drivers_sha256\": \"$DRIVERS_SHA\"" || fail "drivers_sha256 is not $DRIVERS_SHA"
echo "$ids" | grep -q '"export_tool_sha256": "544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b"' || fail "export_tool_sha256 is not 544c9b3d..."
echo "recorded, not compared (the environment input is replaced by the copy made after the preflight at open, the previous file kept beside it; the plan is the last step below):"
sha256sum /home/ruisth/egw-tcg/sut_environment.json
YH=$(git -C "$Y" rev-parse HEAD) || fail "git rev-parse HEAD failed in $Y"
YS=$(GIT_OPTIONAL_LOCKS=0 git -C "$Y" status --porcelain) || fail "git status failed in $Y"
echo "yocto checkout (launcher): $YH, porcelain lines: $(printf '%s' "$YS" | grep -c .)"
[ "$YH" = "$IMAGE" ] || fail "the Yocto checkout $Y is at $YH, S4 expects $IMAGE"
[ -z "$YS" ] || { echo "$YS"; fail "the Yocto checkout $Y is not clean"; }
want run-qemu-integrated 67da61d77a2548122afc34338493165290f6d1ac1dbc2ebccfd6d800dd0438e1 "$Y/src/yocto/scripts/run-qemu-integrated.sh"
want kernel 4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037 "$DEP/Image-qemuarm64.bin"
want qemuboot.conf 7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4 "$DEP/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf"
want qemu-system-aarch64 5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061 "$BUILD/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64"
echo "deploy_source_commit.txt: $(cat /home/ruisth/egw-tcg/deploy_source_commit.txt 2> /dev/null) (the deployment tree on the guest)"
want rootfs-ext4 "$ROOTFS_SHA" "$ROOTFS"

step "helper regenerated from the $TOOLS runbook (predecessor kept) and checked"
sha256sum "$H"
"$PY" "$C/tools/session/regen_helpers.py" "$C/docs/setup/qemu_integrated_gateway.md" "$H" || fail "regen_helpers.py failed"
"$PY" "$C/tools/session/proof_helpers_check.py" "$C/docs/setup/qemu_integrated_gateway.md" "$H" || fail "the helper is not the $TOOLS runbook's"
GOT=$(sha256sum "$H" | cut -d' ' -f1); N=$(wc -l < "$H"); echo "helper sha256=$GOT lines=$N"
[ "$GOT" = "$HELPER_SHA" ] && [ "$N" = "$HELPER_LINES" ] || fail "the regenerated helper is $GOT ($N lines), not $HELPER_SHA ($HELPER_LINES)"
bash -n "$H" || fail "the regenerated helper does not parse"
ls -l "$H"*

# S4 (brief, HOST, freshness of r04): the run directory, the itest files and the itest-replay
# entries of that name, then a search by NAME under the attempts directory, output_test and the
# three host folders a run of that name writes in (a folder that does not exist holds nothing).
step "$RID unused on the host (pilot results/raw, itest, itest-replay; no name holding it under the attempts directory, output_test, itest, itest-replay or pilot/results)"
[ -d "$ATT" ] && [ -d "$OT/runs" ] || fail "$ATT or $OT/runs is not a directory"
for f in /home/ruisth/egw-tcg/pilot/results/raw/$RID /home/ruisth/egw-tcg/itest/$RID /home/ruisth/egw-tcg/itest/$RID.* /home/ruisth/egw-tcg/itest-replay/$RID /home/ruisth/egw-tcg/itest-replay/$RID.*; do
    [ ! -e "$f" ] || fail "$f exists: $RID is not fresh"
done
NR=("$ATT" "$OT")
for d in /home/ruisth/egw-tcg/itest /home/ruisth/egw-tcg/itest-replay /home/ruisth/egw-tcg/pilot/results; do
    if [ -d "$d" ]; then NR+=("$d"); else echo "no $d: nothing of that name can be there"; fi
done
# By name; a sealed S4 preparation package is not searched (its records name the identifier).
HIT=$(find "${NR[@]}" -name 'HIST_*-g3-t6-host-preparation*' -prune -o -name "*$RID*" -print) \
    || fail "the attempts directory, output_test and the host folders could not be searched for $RID"
[ -z "$HIT" ] || { printf '%s\n' "$HIT"; fail "a name holding $RID exists: $RID is not fresh"; }
echo "fresh on the host: $RID"

step "earlier attempts of row t6 (the export tool numbers a new attempt after the highest of its slug under the attempts directory, output_test/runs and output_test/incomplete)"
ROOTS=("$ATT" "$OT/runs")
if [ -d "$OT/incomplete" ]; then ROOTS+=("$OT/incomplete"); else echo "no $OT/incomplete (the export tool skips a root that is not a directory)"; fi
find "${ROOTS[@]}" -name '*_g3-qualification-*_attempt*' > "$PKG/g3-qualification-attempts.unsorted.txt" \
    || fail "the earlier attempts could not be listed"
sort "$PKG/g3-qualification-attempts.unsorted.txt" > "$PKG/g3-qualification-attempts.txt" && rm -f "$PKG/g3-qualification-attempts.unsorted.txt"
cat "$PKG/g3-qualification-attempts.txt"
echo "the attempts of the other rows ($(grep -vc '_g3-qualification-t6_attempt' "$PKG/g3-qualification-attempts.txt") entries above) are admitted as they are"
# S4 (brief, HOST): exactly one earlier attempt of row t6 is admitted, S2's invalid one, where it
# is kept (the attempts directory, output_test/runs/2026-10-03/), as the steps script admits it;
# found anywhere else, or any other attempt of the slug, is a stop.
BAD=0; N6=0
while IFS= read -r f; do
    case ${f##*/} in
        *_g3-qualification-t6_attempt*)
            if [ "$f" = "$ATT/$T6_ADMITTED" ] || [ "$f" = "$OT/runs/2026-10-03/$T6_ADMITTED" ]; then
                N6=$((N6 + 1)); echo "admitted (row t6, S2's invalid attempt, kept): $f"
            else
                echo "NOT ADMITTED (row t6): $f"; BAD=1
            fi ;;
    esac
done < "$PKG/g3-qualification-attempts.txt"
[ "$BAD" -eq 0 ] || fail "an attempt of row t6 other than $T6_ADMITTED where it is kept exists"
[ "$N6" -ge 1 ] || fail "$T6_ADMITTED was not found: the new attempt of row t6 would not be numbered attempt02"
echo "row t6: $T6_ADMITTED found $N6 time(s), no other attempt of the slug (no attempt02): the new attempt is expected as ..._g3-qualification-t6_attempt02"
echo "state directory of S4 today (information; 'open S4' creates it): $(ls -d /home/ruisth/egw-exec/g3-t6-s4 2> /dev/null || echo absent)"

step "$RID unused on the guest root file system (offline, read-only: debugfs -c; no QEMU, no session)"
command -v debugfs > /dev/null || fail "debugfs is not available"
want rootfs-ext4-before-listing "$ROOTFS_SHA" "$ROOTFS"   # S4 (brief, HOST): hashed before and after the listing
debugfs -c -R "ls -l /opt/egw/deployment/data/events" "$ROOTFS" > "$PKG/guest-events-listing.txt" 2> "$PKG/guest-events-listing.stderr.txt" \
    || fail "the guest events directory could not be listed"
echo "guest event directories listed: $(grep -c . "$PKG/guest-events-listing.txt") lines"
awk '{print $NF}' "$PKG/guest-events-listing.txt" | sort -u > "$PKG/guest-events-names.txt"
cat "$PKG/guest-events-names.txt" | tr '\n' ' '; echo
grep -qxF -- . "$PKG/guest-events-names.txt" && grep -qxF -- .. "$PKG/guest-events-names.txt" \
    || fail "the listing holds no '.' and '..' entries: the guest events directory was not read ($(head -c 300 "$PKG/guest-events-listing.stderr.txt" | tr '\n' ' '))"
grep -qxF -- "$RID" "$PKG/guest-events-names.txt" && fail "the guest holds data/events/$RID: $RID is not fresh on the guest"
grep -q -- "^$RID" "$PKG/guest-events-names.txt" && fail "the guest holds a $RID* directory"
echo "fresh on the guest: $RID"
want rootfs-ext4-after-listing "$ROOTFS_SHA" "$ROOTFS"

# S4 (brief, HOST): the data disk, read-only as guest_session_open.sh lists it (its size and its
# ext4 header); never hashed. The size is compared; the header is recorded, not judged.
step "data disk (read-only: size and ext4 header, as the open driver lists them; never hashed)"
ls -l "$DATA_DISK" || fail "the data disk $DATA_DISK could not be listed"
DS=$(stat -c %s "$DATA_DISK") || fail "the size of the data disk could not be read"
echo "data disk size: $DS B"
[ "$DS" = "$DATA_DISK_SIZE" ] || fail "the data disk is $DS B, not $DATA_DISK_SIZE B"
DH=$(/usr/sbin/dumpe2fs -h "$DATA_DISK" 2> /dev/null) || fail "the data disk's ext4 header could not be read (dumpe2fs -h)"
printf '%s\n' "$DH" | grep -E "state|features|mount count|Last mount" | sed 's/^/data disk header: /'

# S4 (brief, HOST, the plan entry): last, once every check above has passed. The plan at its
# value of today is copied into the record (the predecessor), the merged plan-supplement adds
# the entry, and the result is compared: its sha256, 96 entries, the first 95 equal to the
# predecessor's (JSON values, and bytes: the plan without its last entry IS the predecessor,
# byte for byte), the other fields unchanged, the last entry exactly controller_restart-r04 as
# the request gives it. A plan already holding the entry (a re-run) is recorded, checked the
# same way and not changed; any other plan is a stop with nothing run. The top level of
# ~/egw-tcg/pilot is listed before and after: no other file appears there.
step "plan entry $RID (the merged plan-supplement, --entry g3-t6; the predecessor kept in the record)"
ls -A1 /home/ruisth/egw-tcg/pilot > "$PKG/pilot-listing-before.txt" || fail "the top level of ~/egw-tcg/pilot could not be listed"
PS=$(sha256sum "$PLAN" 2> /dev/null | cut -d' ' -f1)
echo "plan before: ${PS:-unreadable}  $PLAN"
PRED=-
case $PS in
    "$PLAN_AFTER_SHA")
        echo "plan already holds $RID ($PLAN_AFTER_SHA: a re-run after the entry was added): nothing is run or changed; it is checked below"
        ;;
    "$PLAN_BEFORE_SHA")
        [ ! -e "$PKG/campaign_plan.predecessor.json" ] || fail "campaign_plan.predecessor.json exists in the record - never overwritten; the plan was not changed"
        cp "$PLAN" "$PKG/campaign_plan.predecessor.json" && cmp -s "$PLAN" "$PKG/campaign_plan.predecessor.json" \
            || fail "the predecessor could not be kept in the record: the plan was not changed"
        PRED=$PKG/campaign_plan.predecessor.json
        echo "plan predecessor kept in the record: campaign_plan.predecessor.json, sha256 $(sha256sum "$PRED" | cut -d' ' -f1)"
        echo "running: cd $C/src && $PY -m egw_experiments plan-supplement --plan $PLAN --entry g3-t6"
        (cd "$C/src" && "$PY" -m egw_experiments plan-supplement --plan "$PLAN" --entry g3-t6) > "$PKG/plan-supplement.console.txt" 2>&1
        rc=$?
        cat "$PKG/plan-supplement.console.txt"
        echo "plan-supplement exit=$rc"
        [ "$rc" -eq 0 ] || fail "plan-supplement ended $rc (on a refusal it leaves the plan as it was)"
        ;;
    *) fail "the plan is ${PS:-unreadable}, neither $PLAN_BEFORE_SHA (before the entry) nor $PLAN_AFTER_SHA (with it): nothing was run or changed" ;;
esac
ls -A1 /home/ruisth/egw-tcg/pilot > "$PKG/pilot-listing-after.txt" || fail "the top level of ~/egw-tcg/pilot could not be listed after the step"
cmp -s "$PKG/pilot-listing-before.txt" "$PKG/pilot-listing-after.txt" \
    || { diff "$PKG/pilot-listing-before.txt" "$PKG/pilot-listing-after.txt"; fail "the top level of ~/egw-tcg/pilot changed: a file other than the plan"; }
echo "plan folder: the same $(grep -c . "$PKG/pilot-listing-after.txt") names at its top level before and after"
PA=$(sha256sum "$PLAN" 2> /dev/null | cut -d' ' -f1)
echo "plan after: ${PA:-unreadable}  $PLAN"
[ "$PA" = "$PLAN_AFTER_SHA" ] || fail "the plan is ${PA:-unreadable} after the step, not $PLAN_AFTER_SHA"
"$PY" - "$PLAN" "$PRED" "$PLAN_BEFORE_SHA" << 'PLAN_CHECK' || fail "the plan's content is not the predecessor plus exactly $RID"
import hashlib
import json
import sys

plan_path, pred_path, want_pred = sys.argv[1:4]
# The canonical serialisation (plan_gen.plan_to_json: indent 2, sorted keys, 'runs' the last
# key): an entry of 'runs' opens with four spaces, and the file ends with the list's closing.
TAIL = b"\n  ]\n}\n"
SEP = b",\n    {\n"
WANT = {"condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 96,
        "rate_msg_s": 11.2, "repetition": 4, "run_id": "controller_restart-r04", "runner": "simulator",
        "scenario": "nominal", "seed": 1715385812, "status": "planned", "supplement": "g3-t6",
        "warmup_s": 0}
bad = []
new = open(plan_path, "rb").read()
cut = new.rfind(SEP)
if cut < 0 or not new.endswith(TAIL):
    print("plan check: the plan does not end with an entry of its 'runs' list in the canonical form")
    sys.exit(1)
base = new[:cut] + TAIL
got = hashlib.sha256(base).hexdigest()
print("plan check: the plan up to the comma before its last entry, closed as the predecessor is: sha256 %s" % got)
if got != want_pred:
    bad.append("the plan without its last entry is %s, not the predecessor %s" % (got, want_pred))
if pred_path != "-":
    pred = open(pred_path, "rb").read()
    if pred != base:
        bad.append("the kept predecessor is not the plan without its last entry, byte for byte")
    elif not (pred.endswith(TAIL) and new.startswith(pred[:-len(TAIL)] + b",")):
        bad.append("the predecessor's bytes are not the first bytes of the plan")
    else:
        print("plan check: the kept predecessor's first %d bytes (all but its closing) are the plan's first %d bytes"
              % (len(pred) - len(TAIL), len(pred) - len(TAIL)))
else:
    print("plan check: no predecessor in this record (a re-run): the bytes are proved by the sha256 above")
old_plan = json.loads(base)
new_plan = json.loads(new)
old_runs = old_plan.get("runs") or []
new_runs = new_plan.get("runs") or []
print("plan check: %d entries before, %d after" % (len(old_runs), len(new_runs)))
if len(old_runs) != 95 or len(new_runs) != 96:
    bad.append("the entries are %d before and %d after, not 95 and 96" % (len(old_runs), len(new_runs)))
if new_runs[:len(old_runs)] != old_runs:
    bad.append("an entry of the predecessor changed (JSON comparison)")
if {k: v for k, v in new_plan.items() if k != "runs"} != {k: v for k, v in old_plan.items() if k != "runs"}:
    bad.append("a field of the plan other than 'runs' changed")
last = new_runs[-1] if new_runs else {}
print("plan entry %s" % json.dumps(last, sort_keys=True))
if json.dumps(last, sort_keys=True) != json.dumps(WANT, sort_keys=True):
    bad.append("the last entry is not exactly controller_restart-r04 as the request gives it")
if [e.get("run_id") for e in new_runs].count("controller_restart-r04") != 1:
    bad.append("controller_restart-r04 is not held exactly once")
for b in bad:
    print("plan check: NOT OK: " + b)
if bad:
    sys.exit(1)
print("plan check: OK (96 entries; the first 95 equal to the predecessor's, as JSON and as bytes; the other fields unchanged; the last entry exactly controller_restart-r04, planned)")
PLAN_CHECK

step "the clone after every step (still $TOOLS, clean: nothing written in it)"
HD=$(git -C "$C" rev-parse HEAD); T=$(git -C "$C" rev-parse 'HEAD^{tree}')
ST=$(GIT_OPTIONAL_LOCKS=0 git -C "$C" status --porcelain) || fail "git status failed at the end"
echo "HEAD=$HD tree=$T porcelain lines: $(printf '%s' "$ST" | grep -c .)"
[ "$HD" = "$TOOLS" ] && [ "$T" = "$TREE" ] && [ -z "$ST" ] || fail "the clone is not at $TOOLS / $TREE and clean at the end"

echo
echo "outcome=prepared (at $(now))"
