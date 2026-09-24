#!/usr/bin/env bash
# s09 - code identity and the repository anchors of backlog_diagnosis.md, at the merged dev head.
# Read-only: `git diff`, `git show`, `git merge-base --is-ancestor`, `git branch --contains`,
# `git grep` only; nothing is checked out, written or fetched.
# Run from Git Bash:  bash <this directory>/s09_code_identity.sh > <this directory>/../out/s09_code_identity.out.txt 2>&1
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${EGW_WORKTREE:-$(cd "$HERE/../../../devwt" && pwd)}
REF=35fe8bb
g() { git -C "$REPO" "$@"; }
range() { echo "--- $1:$2-$3 at $REF"; g show "$REF:$1" | awk -v a="$2" -v b="$3" 'NR>=a && NR<=b {printf "%5d  %s\n", NR, substr($0,1,170)}'; }

echo "== code identity of src/egw_controller/ (the run's commit fe954a9 against the heads read today)"
for c in 35fe8bb b7e0c83 3549d46; do
  printf "git diff fe954a9 %s -- src/egw_controller/ : %s changed line(s)\n" "$c" "$(g diff fe954a9 "$c" -- src/egw_controller/ | wc -l)"
done
g log -1 --format='%h %ci %s' "$REF"
g merge-base --is-ancestor b7e0c83 "$REF" && echo "b7e0c83 (WSL clone HEAD) is an ancestor of $REF"
g merge-base --is-ancestor 3549d46 "$REF" && echo "3549d46 IS on $REF" || echo "3549d46 is NOT an ancestor of $REF (not on dev)"
echo "branches containing 3549d46:"; g branch -a --contains 3549d46 | sed 's/^/  /'

echo "== the other cited files, b7e0c83 against $REF (empty = unchanged)"
g diff --stat b7e0c83 "$REF" -- src/egw_experiments/analyze.py src/egw_experiments/itest_reconcile.py \
  src/deployment/scripts/collect-resources.sh src/egw_simulator/cli.py src/egw_simulator/scenarios.py \
  src/deployment/compose.yaml docs/setup/qemu_integrated_gateway.md
echo "(end)"

echo "== anchors at $REF"
range src/egw_controller/service.py 39 39
range src/egw_controller/service.py 150 152
range src/egw_controller/service.py 171 173
range src/egw_controller/service.py 182 197
range src/egw_controller/service.py 320 320
range src/egw_controller/service.py 331 331
range src/egw_controller/service.py 342 342
range src/egw_controller/service.py 414 414
range src/egw_controller/events.py 112 119
range src/egw_controller/mqtt.py 187 189
range src/egw_controller/mqtt.py 199 199
range src/egw_experiments/analyze.py 499 503
range src/deployment/scripts/collect-resources.sh 60 67
range src/egw_simulator/cli.py 79 87
range src/egw_experiments/itest_reconcile.py 235 235
range src/egw_experiments/itest_reconcile.py 604 604
range docs/setup/qemu_integrated_gateway.md 651 651
range docs/setup/qemu_integrated_gateway.md 653 654
echo "--- CPU limits in compose.yaml at $REF"
if g show "$REF:src/deployment/compose.yaml" | grep -n -E '^\s*(cpus|cpu_count|cpu_quota|cpu_period|cpu_shares|cpuset)\s*:'; then :; else echo "no CPU limit key in compose.yaml"; fi
g show "$REF:src/deployment/compose.yaml" | grep -c -E '^\s*mem_limit\s*:|^\s*memory\s*:' | sed 's/^/memory-limit keys: /'

echo "== the pause record: PROGRESS.md and LOG.md entry #C039 at 3549d46"
g show 3549d46:PROGRESS.md | grep -n -E 'stays on the G3 qualifying runs' | cut -c1-160
g show 3549d46:LOG.md | grep -n -E '^## Entry #C039|the student decided on 2026-09-21 that it stays on the G3 qualifying runs' | cut -c1-160
