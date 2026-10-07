#!/bin/bash
# Static check of the values g3_hostprep.sh (S4) holds (read-only; run from the Windows
# shell, where git reads the read-only worktree of 1fd9792). Each value is read out of
# the script's text and compared with its source: a git object of the merged commit,
# the sealed records of S3 in output_test, or this stream's read-only look at the host
# (ro_look.console.txt) and plan bench (plan_check_bench.console.txt). Nothing is written
# but this script's console.
# Usage: bash host-record/static_values.sh   (from the preparation folder)
set -u
cd "$(dirname "$0")/.." || exit 2
F=g3_hostprep.sh
W=../../t6m                     # the read-only worktree, detached at 1fd9792
OT="C:/Users/ruimf/Documents/Projeto Mestrado/output_test"
S3REC="$OT/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-host-preparation/part1-record/console.txt"
S3ENV="$OT/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02/state/session-S3.env"
S3OPEN="$OT/runs/2026-10-05/20261005T114428Z_guest-session_attempt11/console/001-identities-before-boot.stdout.txt"
SAME=0 DIFF=0
v() { sed -n "s/^$1=\([^ ]*\).*/\1/p" "$F" | head -n 1; }                        # NAME=value
w() { sed -n "s/^want $1 \([0-9a-f]\{64\}\) .*/\1/p" "$F" | head -n 1; }          # want <label> <sha> ...
rec() { sed -n "s/^$1: \([0-9a-f]\{64\}\)  .*/\1/p" "$S3REC" | head -n 1; }       # S3's sealed record
blob() { git -C "$W" cat-file blob "$TOOLS:$1" | sha256sum | cut -c1-64; }
cmpv() {   # cmpv <label> <value in the script> <value of the source> <source>
    if [ -n "$2" ] && [ "$2" = "$3" ]; then echo "same      $1: $2 ($4)"; SAME=$((SAME + 1))
    else echo "DIFFERENT $1: script '${2}' source '${3}' ($4)"; DIFF=$((DIFF + 1)); fi
}
echo "g3_hostprep.sh sha256 $(sha256sum "$F" | cut -c1-64)"
TOOLS=$(v TOOLS)
cmpv TOOLS "$TOOLS" "$(git -C "$W" rev-parse HEAD)" "the worktree's HEAD, the merge of PR #57"
cmpv TOOLS-is-origin-dev "$TOOLS" "$(git -C "$W" rev-parse refs/remotes/origin/dev)" "refs/remotes/origin/dev of the Windows repository today"
cmpv TREE "$(v TREE)" "$(git -C "$W" rev-parse "$TOOLS^{tree}")" "git rev-parse TOOLS^{tree}"
cmpv REVIEWED "$(v REVIEWED)" "$(git -C "$W" rev-parse "$TOOLS^2")" "second parent of the merge"
cmpv REVIEWED-tree "$(git -C "$W" rev-parse "$(v REVIEWED)^{tree}")" "$(v TREE)" "the reviewed head's tree is the merge's"
cmpv PREVIOUS "$(v PREVIOUS)" "$(sed -n 's/^HEAD=\([0-9a-f]*\) tree=.*/\1/p' "$S3REC" | head -n 1)" "S3's sealed host-preparation record, the clone after its checkout"
git -C "$W" merge-base --is-ancestor "$(v PREVIOUS)" "$TOOLS" && cmpv PREVIOUS-ancestor yes yes "PREVIOUS is an ancestor of TOOLS" || cmpv PREVIOUS-ancestor no yes "PREVIOUS is an ancestor of TOOLS"
cmpv IMAGE "$(v IMAGE)" "$(sed -n 's/^source_commit=//p' "$S3REC" | head -n 1)" "S3's sealed record, controller identity source_commit"
cmpv IMAGE-yocto "$(v IMAGE)" "$(sed -n 's/^yocto checkout (launcher): \([0-9a-f]*\),.*/\1/p' "$S3REC" | head -n 1)" "S3's sealed record, the Yocto checkout"
H=$(git -C "$W" cat-file blob "$TOOLS:docs/setup/qemu_integrated_gateway.md" \
    | awk -v s="host\$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'" 'f && $0 == "EOF" {f = 0; done = 1; next} f {print} !done && index($0, s) == 1 {f = 1}')
cmpv HELPER_SHA "$(v HELPER_SHA)" "$(printf '%s\n' "$H" | sha256sum | cut -c1-64)" "the section 6.1 heredoc cut out of the runbook blob at TOOLS"
cmpv HELPER_LINES "$(v HELPER_LINES)" "$(printf '%s\n' "$H" | wc -l | tr -d ' ')" "its line count"
cmpv ROOTFS_SHA "$(v ROOTFS_SHA)" "$(sed -n 's/^rootfs_after_close=//p' "$S3ENV")" "session-S3.env of S3's second opening, rootfs_after_close"
cmpv ROOTFS_SHA-today "$(v ROOTFS_SHA)" "$(sed -n 's/^\([0-9a-f]\{64\}\)  .*rootfs-20260918120819.ext4$/\1/p' host-record/ro_look.console.txt)" "ro_look.console.txt (the host today)"
cmpv DRIVERS_SHA "$(v DRIVERS_SHA)" "$(bash ../battery/drivers_hash.sh "$W" "$TOOLS" C | sed 's/.*drivers_sha256=//')" "drivers_hash.sh on the worktree at TOOLS (C collation)"
cmpv DRIVERS_SHA-en "$(v DRIVERS_SHA)" "$(bash ../battery/drivers_hash.sh "$W" "$TOOLS" en | sed 's/.*drivers_sha256=//')" "drivers_hash.sh (en collation)"
cmpv COLLECTOR_SHA "$(v COLLECTOR_SHA)" "$(blob src/deployment/scripts/collect-resources.sh)" "blob at TOOLS"
cmpv DEPLOY_TREE "$(v DEPLOY_TREE)" "$(git -C "$W" rev-parse "$TOOLS:src/deployment")" "git rev-parse TOOLS:src/deployment"
cmpv DEPLOY_TREE_CANDIDATE "$(v DEPLOY_TREE_CANDIDATE)" "$(git -C "$W" rev-parse "$(v IMAGE):src/deployment")" "git rev-parse IMAGE:src/deployment"
cmpv DEPLOY_TREE_CANDIDATE-S3 "$(v DEPLOY_TREE_CANDIDATE)" "$(sed -n 's/^git trees: src\/deployment=\([0-9a-f]*\) .*/\1/p' "$S3REC")" "S3's sealed record (the clone's tree at 8e49261)"
cmpv deployment-diff "$(git -C "$W" diff --name-only "$(v DEPLOY_TREE_CANDIDATE)" "$(v DEPLOY_TREE)" | tr '\n' ' ')" "README.md scripts/collect-resources.sh " "git diff --name-only of the two trees"
cmpv no-rebuild-deployment "$(git -C "$W" diff --name-only "$(v IMAGE)" "$TOOLS" -- src/deployment | tr '\n' ' ')" "src/deployment/README.md src/deployment/scripts/collect-resources.sh " "git diff --name-only IMAGE TOOLS -- src/deployment (the script's expected text)"
for d in src/egw_controller src/egw_simulator src/schemas src/Dockerfile src/requirements-runtime.lock src/requirements.lock src/pyproject.toml src/CONTRACTS.md; do
    cmpv "no-rebuild $d" "$(git -C "$W" diff --stat "$(v IMAGE)" "$TOOLS" -- "$d" | wc -l | tr -d ' ')" 0 "git diff --stat IMAGE TOOLS"
done
cmpv PLAN_BEFORE_SHA "$(v PLAN_BEFORE_SHA)" "$(sed -n 's/^\([0-9a-f]\{64\}\)  .*\/egw-tcg\/pilot\/campaign_plan.json$/\1/p' host-record/ro_look.console.txt | head -n 1)" "ro_look.console.txt (the plan today)"
cmpv PLAN_AFTER_SHA "$(v PLAN_AFTER_SHA)" "$(sed -n 's/^plan-supplement exit=0; plan-supplement on the copy: sha256 //p' host-record/plan_check_bench.console.txt)" "plan_check_bench.console.txt (the merged plan-supplement on a copy)"
cmpv RID "$(v RID)" "$(git -C "$W" cat-file blob "$TOOLS:docs/setup/qemu_integrated_gateway.md" | sed -n '1421s/^host\$ RID=\([^;]*\);.*/\1/p')" "the RID assignment of the runbook's test 6 block (line 1421; its comment also names r01-r03 as used)"
cmpv DATA_DISK "$(v DATA_DISK)" "$(git -C "$W" cat-file blob "$TOOLS:tools/session/guest_common.sh" | sed -n 's/^DATA_DISK=\${EGW_DATA_DISK:-\(.*\)}$/\1/p')" "guest_common.sh's default"
cmpv DATA_DISK_SIZE "$(v DATA_DISK_SIZE)" "$(awk '/^## data disk/ {getline; print $5; exit}' "$S3OPEN")" "S3's second open, 001-identities-before-boot"
cmpv DATA_DISK_SIZE-today "$(v DATA_DISK_SIZE)" "$(sed -n 's/^data disk size: //p' host-record/ro_look.console.txt)" "ro_look.console.txt"
T6=$(v T6_ADMITTED)
[ -d "$OT/runs/2026-10-03/$T6" ] && cmpv T6_ADMITTED-in-output_test yes yes "output_test/runs/2026-10-03/$T6" || cmpv T6_ADMITTED-in-output_test no yes "output_test/runs/2026-10-03/$T6"
cmpv T6_ADMITTED-in-attempts "$(sed -n 's/^  .*\/attempts\/\(.*_g3-qualification-t6_attempt.*\)$/\1/p' host-record/ro_look.console.txt)" "$T6" "ro_look.console.txt (the attempts directory today)"
cmpv T6-attempts-in-output_test "$(find "$OT" -name '*_g3-qualification-t6_attempt*' | sed 's|.*/||' | tr '\n' ' ')" "$T6 " "every t6 attempt under output_test today"
cmpv RID-names-in-output_test "$(find "$OT" -name "*$(v RID)*" | wc -l | tr -d ' ')" 0 "names holding the run id under output_test today"
cmpv runbook "$(w runbook)" "$(blob docs/setup/qemu_integrated_gateway.md)" "blob at TOOLS"
cmpv runbook-lines "$(sed -n 's/^\[ "\$N" = \([0-9]*\) \].*/\1/p' "$F" | head -n 1)" "$(git -C "$W" cat-file blob "$TOOLS:docs/setup/qemu_integrated_gateway.md" | wc -l | tr -d ' ')" "blob at TOOLS"
cmpv extraction-rule-source "$(w extraction-rule-source)" "$(blob src/tests/test_runbook_itest_helpers.py)" "blob at TOOLS"
cmpv local_export "$(w local_export)" "$(blob src/egw_experiments/local_export.py)" "blob at TOOLS"
cmpv export_tool_sha256 "$(sed -n 's/.*"export_tool_sha256": "\([0-9a-f]*\)".*/\1/p' "$F" | head -n 1)" "$(blob src/egw_experiments/local_export.py)" "blob at TOOLS"
cmpv fetch_started_at "$(w fetch_started_at)" "$(blob tools/session/fetch_started_at.sh)" "blob at TOOLS"
cmpv images.lock.env "$(w images.lock.env)" "$(blob src/deployment/images.lock.env)" "blob at TOOLS"
cmpv compose.yaml "$(w compose.yaml)" "$(blob src/deployment/compose.yaml)" "blob at TOOLS"
cmpv mosquitto.conf "$(w mosquitto.conf)" "$(blob src/deployment/mosquitto/config/mosquitto.conf)" "blob at TOOLS"
cmpv CONTRACTS "$(w CONTRACTS)" "$(blob src/CONTRACTS.md)" "blob at TOOLS"
cmpv schemas-tree "$(sed -n 's/.*rev-parse "\$TOOLS:src\/schemas")" = \([0-9a-f]*\) .*/\1/p' "$F" | head -n 1)" "$(git -C "$W" rev-parse "$TOOLS:src/schemas")" "git rev-parse TOOLS:src/schemas"
for l in tunnel.sh ca.crt controller-record controller-archive run-qemu-integrated kernel qemuboot.conf qemu-system-aarch64; do
    cmpv "$l" "$(w "$l")" "$(rec "$l")" "S3's sealed host-preparation record"
done
cmpv image_id "$(sed -n "s/.*'^image_id=sha256:\([0-9a-f]*\)\\$'.*/\1/p" "$F" | head -n 1)" "$(sed -n 's/^image_id=sha256://p' "$S3REC" | head -n 1)" "S3's sealed record, controller identity"
cmpv venv-module-path "$(sed -n 's/^\/home\/ruisth\/egw-exec\/repo\/src\/egw_experiments\/__init__.py$/yes/p' host-record/ro_look.console.txt)" yes "ro_look.console.txt: the venv imports the clone's module (the path the script requires)"
cmpv plan-entry "$(grep -c '^PASS P1c ' host-record/plan_check_bench.console.txt)" 1 "plan_check_bench.console.txt: the entry the merged plan-supplement built equals the script's expected entry (P1c)"
echo
echo "summary: $SAME same, $DIFF DIFFERENT"
[ "$DIFF" -eq 0 ]
