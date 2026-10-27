#!/bin/bash
# Host preparation for the third finite-proof attempt (Rui's authorisation
# "Autorizo a sessão", recorded by the PM 2026-09-27 01:01 WEST): the tools'
# clean clone moved to the merge of PR #49 (b65a06d) without discarding anything, the helper regenerated from that
# commit's runbook (predecessor kept) and checked, the fresh run id confirmed.
# The controller image and the guest deployment are NOT touched.
# Usage (WSL): r03_hostprep.sh <package-dir>
set -u
TOOLS=b65a06ddc02842cd6464555e319ee4cc5e0d1bfb
TREE=403452085517da468a5b344a81d86009d680feb6
IMAGE=489bc9e5b5b0660026ea2630b8d1d124049ba2ce
RID=proof-adr0011-r03
C=/home/ruisth/egw-exec/repo
PKG=${1:?usage: r03_hostprep.sh <package-dir>}
[ ! -e "$PKG" ] || { echo "STOP: $PKG exists - never overwritten"; exit 2; }
mkdir -p "$PKG" || exit 2
exec > >(tee -a "$PKG/console.txt") 2>&1
now() { date -u +%FT%T.%3NZ; }
step() { echo; echo "## $(now) $*"; }
fail() { echo "STOP: $*"; echo "outcome=failed (at $(now))"; exit 1; }

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

step "fetch $TOOLS from the Windows repository (its origin/dev, the merge of PR #49)"
git -C "$C" fetch --quiet origin refs/remotes/origin/dev || fail "fetch failed"
FH=$(git -C "$C" rev-parse FETCH_HEAD); echo "FETCH_HEAD=$FH"
[ "$FH" = "$TOOLS" ] || fail "the fetched origin/dev is $FH, not $TOOLS"
git -C "$C" -c advice.detachedHead=false checkout --quiet --detach "$TOOLS" || fail "checkout refused"
H=$(git -C "$C" rev-parse HEAD); T=$(git -C "$C" rev-parse 'HEAD^{tree}'); echo "HEAD=$H tree=$T"
[ "$H" = "$TOOLS" ] && [ "$T" = "$TREE" ] || fail "$C is not at $TOOLS / $TREE"
[ -z "$(git -C "$C" status --porcelain)" ] || fail "$C is not clean after the checkout"
git -C "$C" for-each-ref --format='%(objectname) %(refname)' refs/heads > "$PKG/branches-after.txt"
cmp "$PKG/branches-before.txt" "$PKG/branches-after.txt" || fail "a branch changed"
echo "clean; every branch unchanged"
echo "what differs from the image's commit $IMAGE in the executed tooling (the controller image is NOT rebuilt):"
git -C "$C" diff --stat "$IMAGE" "$TOOLS" -- src/egw_experiments src/deployment src/schemas src/Dockerfile src/pyproject.toml src/requirements-runtime.lock tools/session/'*.sh' tools/session/'*.py' tools/session/guest
echo "(end); src/deployment must be absent above:"
[ -z "$(git -C "$C" diff --stat "$IMAGE" "$TOOLS" -- src/deployment)" ] || fail "src/deployment differs from the image commit: the guest's deployment would not match the clone"
echo "src/deployment identical to $IMAGE"

step "helper regenerated from the $TOOLS runbook (predecessor kept) and checked"
sha256sum /home/ruisth/egw-tcg/itest-helpers.sh
/home/ruisth/egw-exec/venv/bin/python "$C/tools/session/regen_helpers.py" "$C/docs/setup/qemu_integrated_gateway.md" /home/ruisth/egw-tcg/itest-helpers.sh || fail "regen_helpers.py failed"
/home/ruisth/egw-exec/venv/bin/python "$C/tools/session/proof_helpers_check.py" "$C/docs/setup/qemu_integrated_gateway.md" /home/ruisth/egw-tcg/itest-helpers.sh || fail "the helper is not the $TOOLS runbook's"
ls -l /home/ruisth/egw-tcg/itest-helpers.sh*
bash -n /home/ruisth/egw-tcg/itest-helpers.sh || fail "the regenerated helper does not parse"

step "the other identities the session reads (unchanged)"
echo "yocto checkout: $(git -C /home/ruisth/yocto/egw rev-parse HEAD)"
echo "deploy_source_commit.txt: $(cat /home/ruisth/egw-tcg/deploy_source_commit.txt) (the deployment tree on the guest)"
(cd /home/ruisth/egw-images && echo "$(sed -n 's/^archive_sha256=//p' egw-controller-0.1.0-arm64.identity.txt)  egw-controller-0.1.0-arm64.tar" | sha256sum -c -) || fail "the staged archive no longer matches its record"
grep -E '^(image_id|source_commit)=' /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt
/home/ruisth/egw-exec/venv/bin/python -c 'import egw_experiments; print(egw_experiments.__file__)'

step "the preserved data-disk baseline (stage (a) of 2026-09-26)"
B=/home/ruisth/egw-preservation/2026-09-26/egw-data.current-state.img
stat -c "size=%s blocks=%b mode=%a mtime=%y %n" "$B" || fail "the preserved copy is missing"
BH=$(sha256sum "$B" | cut -d' ' -f1); echo "preserved copy sha256=$BH"
[ "$BH" = 91e2d7b96a6ca5e43647735e765e900a2bbb66d14077ff2127a03d42d9f39cef ] || fail "the preserved copy no longer matches its recorded hash"
stat -c "live data disk: size=%s blocks=%b mtime=%y %n" /home/ruisth/yocto/egw-integrated/egw-data.img

step "run id $RID is fresh"
for f in /home/ruisth/egw-tcg/itest/$RID.* /home/ruisth/egw-tcg/itest/$RID /home/ruisth/egw-tcg/proof/plan-$RID.json /home/ruisth/egw-tcg/proof/results/raw/$RID; do
    [ ! -e "$f" ] || fail "$f exists: $RID is not fresh"
done
echo "no record of $RID"
echo "outcome=prepared (at $(now))"
