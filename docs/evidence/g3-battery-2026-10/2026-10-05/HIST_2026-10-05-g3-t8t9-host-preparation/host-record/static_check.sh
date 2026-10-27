#!/bin/bash
# Static check of every constant of g3_hostprep.sh (S3) against the source it
# was taken from. Read-only: 'git show' / 'git rev-parse' in the Windows
# repository (the clone's origin), sealed records under output_test, and the
# console of ro_look.sh (what the host holds today). Nothing is run on the host
# and g3_hostprep.sh is only read.
# Usage (Git Bash on Windows): static_check.sh
set -u
S=$(cd "$(dirname "$0")/../../.." && pwd)     # the scratchpad: this script is in g3/s3prep/host-record/
P=$S/g3/s3prep
OT="C:/Users/ruimf/Documents/Projeto Mestrado/output_test"
REPO=$S/pb     # a worktree of the Windows repository (the clone's origin): the same objects and refs
H=$P/g3_hostprep.sh
S2REC="$OT/runs/2026-10-03/20261003T132249Z_guest-session_attempt09/console/001-identities-before-boot.stdout.txt"
S2ENV="$OT/runs/2026-10-03/HIST_2026-10-03-g3-battery-s2-operator-records/state/session-S2.env"
PREP1="$OT/runs/2026-10-02/HIST_2026-10-02-g3-battery-host-preparation"
SUMMARY="$OT/decisions/2026-10-04_g3-t8-t9-s3-decision-summary.md"
LOOK=$P/host-record/ro_look.console.txt
echo "g3_hostprep.sh sha256 $(sha256sum "$H" | cut -d' ' -f1)"
bad=0
row() {   # row <what> <value in the script> <value of the source> <source>
    local v=same; [ -n "$2" ] && [ "$2" = "$3" ] || { v=DIFFERENT; bad=$((bad + 1)); }
    printf '%-9s %-24s %s\n          source: %s\n' "$v" "$1" "$2" "$4"
}
const() { sed -n "s/^$1=\([0-9A-Za-z_-]*\).*/\1/p" "$H"; }                 # NAME=value at line start
wanted() { awk -v l="$1" '$1 == "want" && $2 == l {print $3}' "$H"; }       # want <label> <sha256> <file>
blob() { git -C "$REPO" show "$TOOLS:$1" | sha256sum | cut -d' ' -f1; }
rec() { grep -E "^[0-9a-f]{64}  .*$1\$" "$2" | cut -d' ' -f1 | sort -u; }  # the hash a record gives for a file name

TOOLS=$(const TOOLS); TREE=$(const TREE); BATTERY=$(const BATTERY); REVIEWED=$(const REVIEWED); IMAGE=$(const IMAGE)
row TOOLS "$TOOLS" "$(grep -o '8e49261[0-9a-f]\{33\}' "$SUMMARY" | sort -u)" "decision summary (the merge of PR #54)"
row "TOOLS in the origin" "$TOOLS" "$(git -C "$REPO" rev-parse "$TOOLS^{commit}")" "git rev-parse in the Windows repository"
git -C "$REPO" merge-base --is-ancestor "$TOOLS" refs/remotes/origin/dev && echo "          the Windows repository's refs/remotes/origin/dev ($(git -C "$REPO" rev-parse refs/remotes/origin/dev)) holds it (what the script fetches)" || { echo "DIFFERENT the Windows repository's origin/dev does not hold $TOOLS"; bad=$((bad + 1)); }
row TREE "$TREE" "$(git -C "$REPO" rev-parse "$TOOLS^{tree}")" "git rev-parse TOOLS^{tree}; also in the decision summary: $(grep -c "$TREE" "$SUMMARY") line(s)"
row BATTERY "$BATTERY" "$(git -C "$REPO" rev-parse "$TOOLS^1")" "first parent of the merge; S2's record names it as the execution clone: $(grep -c "^$BATTERY\$" "$S2REC") line(s)"
row REVIEWED "$REVIEWED" "$(git -C "$REPO" rev-parse "$TOOLS^2")" "second parent of the merge (the head of PR #54)"
row "REVIEWED tree" "$TREE" "$(git -C "$REPO" rev-parse "$REVIEWED^{tree}")" "git rev-parse REVIEWED^{tree}"
row IMAGE "$IMAGE" "$(sed -n 's/^source_commit=//p' "$S2REC")" "S2's record, controller image record: source_commit"
row "IMAGE (Yocto checkout)" "$IMAGE" "$(awk '/^## OS build source/{getline; print}' "$S2REC")" "S2's record, OS build source (the Yocto checkout's HEAD)"
row "ROOTFS_SHA" "$(const ROOTFS_SHA)" "$(sed -n 's/^rootfs_after_close=//p' "$S2ENV")" "session-S2.env, rootfs_after_close"
row "ROOTFS_SHA today" "$(const ROOTFS_SHA)" "$(rec 'rootfs-20260918120819.ext4' "$LOOK")" "ro_look.console.txt"
START="host\$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'"
git -C "$REPO" show "$TOOLS:docs/setup/qemu_integrated_gateway.md" | awk -v s="$START" 'index($0, s) == 1 {f = 1; next} f && $0 == "EOF" {exit} f' > "$P/host-record/.heredoc.tmp"
row HELPER_SHA "$(const HELPER_SHA)" "$(sha256sum "$P/host-record/.heredoc.tmp" | cut -d' ' -f1)" "the section 6.1 heredoc of the runbook blob at TOOLS"
row HELPER_LINES "$(const HELPER_LINES)" "$(wc -l < "$P/host-record/.heredoc.tmp" | tr -d ' ')" "the same heredoc, lines"
rm -f "$P/host-record/.heredoc.tmp"
row "helper today" "$(const HELPER_SHA)" "$(rec 'itest-helpers.sh' "$LOOK")" "ro_look.console.txt"
row "runbook" "$(wanted runbook)" "$(blob docs/setup/qemu_integrated_gateway.md)" "git show TOOLS:docs/setup/qemu_integrated_gateway.md"
row "runbook lines" "$(sed -n 's/^\[ "\$N" = \([0-9]*\) \] || fail "the runbook has.*/\1/p' "$H")" "$(git -C "$REPO" show "$TOOLS:docs/setup/qemu_integrated_gateway.md" | wc -l | tr -d ' ')" "the same blob, lines"
row "extraction-rule-source" "$(wanted extraction-rule-source)" "$(blob src/tests/test_runbook_itest_helpers.py)" "git show TOOLS:src/tests/test_runbook_itest_helpers.py"
row local_export "$(wanted local_export)" "$(blob src/egw_experiments/local_export.py)" "git show TOOLS:src/egw_experiments/local_export.py"
row fetch_started_at "$(wanted fetch_started_at)" "$(blob tools/session/fetch_started_at.sh)" "git show TOOLS:tools/session/fetch_started_at.sh"
row images.lock.env "$(wanted images.lock.env)" "$(blob src/deployment/images.lock.env)" "git show TOOLS:src/deployment/images.lock.env"
row compose.yaml "$(wanted compose.yaml)" "$(blob src/deployment/compose.yaml)" "git show TOOLS:src/deployment/compose.yaml"
row mosquitto.conf "$(wanted mosquitto.conf)" "$(blob src/deployment/mosquitto/config/mosquitto.conf)" "git show TOOLS:src/deployment/mosquitto/config/mosquitto.conf"
row CONTRACTS "$(wanted CONTRACTS)" "$(blob src/CONTRACTS.md)" "git show TOOLS:src/CONTRACTS.md"
row "src/deployment tree" "$(grep -o 'src/deployment")" = [0-9a-f]*' "$H" | awk '{print $NF}')" "$(git -C "$REPO" rev-parse "$TOOLS:src/deployment")" "git rev-parse TOOLS:src/deployment"
row "src/schemas tree" "$(grep -o 'src/schemas")" = [0-9a-f]*' "$H" | awk '{print $NF}')" "$(git -C "$REPO" rev-parse "$TOOLS:src/schemas")" "git rev-parse TOOLS:src/schemas"
DRV=$({
    for f in $(git -C "$REPO" ls-tree --name-only "$TOOLS" tools/session/ | grep -E '\.sh$' | LC_ALL=C sort); do git -C "$REPO" show "$TOOLS:$f"; done
    for f in $(git -C "$REPO" ls-tree --name-only "$TOOLS" tools/session/ | grep -E '\.py$' | LC_ALL=C sort); do git -C "$REPO" show "$TOOLS:$f"; done
    for f in $(git -C "$REPO" ls-tree --name-only "$TOOLS" tools/session/guest/ | grep -E '\.sh$' | LC_ALL=C sort); do git -C "$REPO" show "$TOOLS:$f"; done; } | sha256sum | cut -d' ' -f1)
row drivers_sha256 "$(grep -o '"drivers_sha256": "[0-9a-f]*"' "$H" | cut -d'"' -f4)" "$DRV" "the blobs of tools/session/*.sh, *.py and guest/*.sh at TOOLS, concatenated in the order of common.sh's driver_files"
row export_tool_sha256 "$(grep -o '"export_tool_sha256": "[0-9a-f]*"' "$H" | cut -d'"' -f4)" "$(blob src/egw_experiments/local_export.py)" "git show TOOLS:src/egw_experiments/local_export.py"
row tunnel.sh "$(wanted tunnel.sh)" "$(rec 'egw-tcg/tunnel.sh' "$S2REC")" "S2's record, host helpers; today: $(rec 'egw-tcg/tunnel.sh' "$LOOK")"
row ca.crt "$(wanted ca.crt)" "$(rec 'egw-tcg/ca.crt' "$S2REC")" "S2's record, host helpers; today: $(rec 'egw-tcg/ca.crt' "$LOOK")"
row controller-archive "$(wanted controller-archive)" "$(rec 'egw-controller-0.1.0-arm64.tar' "$S2REC")" "S2's record, controller image record"
row controller-record "$(wanted controller-record)" "$(sed -n 's/^controller-record: \([0-9a-f]*\) .*/\1/p' "$PREP1/part1-record/console.txt")" "the first preparation's sealed record; today: $(rec 'identity.txt' "$LOOK")"
row "controller image id" "$(grep -o 'image_id=sha256:[0-9a-f]*' "$H" | head -n 1)" "$(grep -o '^image_id=sha256:[0-9a-f]*' "$S2REC")" "S2's record, controller image record"
row run-qemu-integrated "$(wanted run-qemu-integrated)" "$(rec 'scripts/run-qemu-integrated.sh' "$S2REC")" "S2's record, OS build source; today: $(rec 'run-qemu-integrated.sh' "$LOOK")"
row "kernel (added)" "$(wanted kernel)" "$(rec 'Image-qemuarm64.bin' "$S2REC")" "S2's record, OS build artefacts; today: $(rec 'Image-qemuarm64.bin' "$LOOK")"
row "qemuboot.conf (added)" "$(wanted qemuboot.conf)" "$(rec 'qemuboot.conf' "$S2REC")" "S2's record, OS build artefacts; today: $(rec 'qemuboot.conf' "$LOOK")"
row "QEMU binary (added)" "$(wanted qemu-system-aarch64)" "$(rec 'usr/bin/qemu-system-aarch64' "$S2REC")" "S2's record, QEMU; today: $(rec 'usr/bin/qemu-system-aarch64' "$LOOK")"
QP=$(sed -n 's/.*Q="\x27"\$BUILD"\x27\(\/[^"]*\)".*/\1/p' "$S/pb/tools/session/guest_session_open.sh")
row "QEMU path under BUILD" "$(awk '$1 == "want" && $2 == "qemu-system-aarch64" {print $4}' "$H" | sed 's/^"\$BUILD//; s/"$//')" "$QP" "guest_session_open.sh line 117 (the frozen open driver)"
ADM=$(const T8_ADMITTED)
row T8_ADMITTED "$ADM" "$(basename "$(ls -d "$OT"/runs/2026-10-03/*_g3-qualification-t8_attempt01)")" "output_test/runs/2026-10-03 (S2's halted attempt)"
for id in $(sed -n 's/^IDS="\(.*\)"$/\1/p' "$H"); do
    row "identifier" "$id" "$(grep -o "\`$id\`" "$SUMMARY" | tr -d '`' | sort -u)" "decision summary, identifiers"
done
echo
echo "the copies the revision started from (P/base):"
row "base/g3_hostprep.sh" "$(sha256sum "$P/base/g3_hostprep.sh" | cut -d' ' -f1)" "$(sha256sum "$PREP1/g3_hostprep.sh" | cut -d' ' -f1)" "the first preparation's sealed package"
row "base/seal_prep.sh" "$(sha256sum "$P/base/seal_prep.sh" | cut -d' ' -f1)" "$(sha256sum "$S/g3/battery/prep/seal_prep.sh" | cut -d' ' -f1)" "S/g3/battery/prep (the first preparation's working folder; the script was not sealed in its own package)"
for f in g3_go.sh g3_wait.sh seal_ops.sh seal_ops_finish.sh; do
    row "base/ops/$f" "$(sha256sum "$P/base/ops/$f" | cut -d' ' -f1)" "$(sha256sum "$OT/runs/2026-10-03/HIST_2026-10-03-g3-battery-s2-operator-records/operator/$f" | cut -d' ' -f1)" "S2's sealed operator records, operator/"
done
row "base/g3_battery.sh" "$(sha256sum "$P/base/g3_battery.sh" | cut -d' ' -f1)" "$(sha256sum "$S/g3/post/g3_battery.sh" | cut -d' ' -f1)" "S/g3/post (the draft of 2026-10-03)"
row "base/g3_battery.README.md" "$(sha256sum "$P/base/g3_battery.README.md" | cut -d' ' -f1)" "$(sha256sum "$S/g3/post/g3_battery.README.md" | cut -d' ' -f1)" "S/g3/post (the draft of 2026-10-03)"
echo
echo "constants that differ from their source: $bad"
[ "$bad" -eq 0 ]
