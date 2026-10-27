#!/usr/bin/env bash
# vc01 - resolve every file:line cited by backlog_diagnosis.md and
# adr-0011-controller-restart-recovery.md against ~/egw-exec/repo at its
# CURRENT commit (HEAD), as the verification brief requires.
# Read-only: `git rev-parse`, `git show`, `git cat-file`, `git log` only.
# Run:  wsl -d Ubuntu-24.04 --exec bash -lc 'bash <this file>'
set -u
REPO="$HOME/egw-exec/repo"
g() { git -C "$REPO" "$@"; }
REF=HEAD
echo "== repository and commit"
echo "repo: $REPO"
g rev-parse HEAD
g log -1 --format='%H | %ci | %s' HEAD
for c in 35fe8bb 3549d46 8e88670 fe954a9 ccd5fd6 b7e0c83; do
  printf 'object %s: ' "$c"; g cat-file -t "$c" 2>/dev/null || echo "ABSENT from this clone"
done
r() { # r <path> <from> [to]
  local p="$1" a="$2" b="${3:-$2}"
  echo "--- $p:$a${3:+-$3}"
  if ! g cat-file -e "$REF:$p" 2>/dev/null; then echo "   FILE ABSENT at HEAD"; return; fi
  local n; n=$(g show "$REF:$p" | wc -l)
  if [ "$b" -gt "$n" ]; then echo "   RANGE BEYOND EOF (file has $n lines)"; fi
  g show "$REF:$p" | awk -v a="$a" -v b="$b" 'NR>=a && NR<=b {printf "%5d  %s\n", NR, substr($0,1,200)}'
}
C=src/egw_controller
echo; echo "######## backlog_diagnosis.md"
r src/egw_experiments/analyze.py 499 516
r $C/service.py 39
r $C/service.py 150 152
r $C/mqtt.py 187 189
r $C/mqtt.py 199
r $C/service.py 171 173
r $C/service.py 175 197
r $C/service.py 320
r $C/service.py 331
r $C/service.py 342
r $C/service.py 414
r $C/events.py 112 119
r src/deployment/scripts/collect-resources.sh 60 67
r src/egw_simulator/cli.py 79 87
r docs/setup/qemu_integrated_gateway.md 651
r docs/setup/qemu_integrated_gateway.md 653 654
r docs/setup/qemu_integrated_gateway.md 1004
echo "--- src/egw_simulator/scenarios.py: load-sweep"; g show "$REF:src/egw_simulator/scenarios.py" | grep -n -E 'load.sweep|load_sweep' | head
echo; echo "######## adr-0011-controller-restart-recovery.md"
r docs/evidence/integrated-qemu/2026-09-18-mongodb7-isolated/README.md 72
r docs/reviews/2026-09-17-egw-image-audit.md 615
r docs/adr/0010-controller-progress-counters.md 10
r src/Dockerfile 48
r src/pyproject.toml 11
r src/egw_experiments/controller_metrics.py 53 64
r $C/mqtt.py 73 76
r $C/mqtt.py 103
r $C/mqtt.py 149 152
r $C/mqtt.py 182 183
r $C/mqtt.py 190 199
r $C/mqtt.py 211 217
r $C/service.py 81 87
r $C/service.py 161 169
r $C/service.py 182 201
r $C/service.py 212 214
r $C/service.py 283 292
r $C/service.py 293 301
r $C/service.py 303 314
r $C/service.py 318 334
r $C/service.py 390 392
r $C/service.py 410 415
r $C/app.py 144 150
r $C/app.py 159 164
r $C/config.py 59
r $C/config.py 104
r $C/ditto.py 70 74
r $C/dedupe.py 52 54
r $C/dedupe.py 78 81
r $C/dedupe.py 91 113
r $C/metrics.py 162 181
r src/CONTRACTS.md 5 9
r src/CONTRACTS.md 11 25
r src/CONTRACTS.md 98 100
r src/CONTRACTS.md 125 127
r src/CONTRACTS.md 186 195
r src/CONTRACTS.md 275 287
r src/CONTRACTS.md 304 306
r src/CONTRACTS.md 348 351
r src/CONTRACTS.md 369 374
r src/deployment/compose.yaml 87
r src/deployment/compose.yaml 243 243
r src/deployment/compose.yaml 251 252
r src/deployment/compose.yaml 256
r src/deployment/compose.yaml 290
r src/deployment/compose.yaml 313 314
r src/deployment/mosquitto/config/mosquitto.conf 30 35
r src/deployment/mosquitto/config/mosquitto.conf 47 56
r src/deployment/images.lock.env 39
r src/egw_experiments/analyze.py 1766
r src/egw_experiments/analyze.py 1808
r src/egw_experiments/analyze.py 1821
r src/egw_experiments/analyze.py 1780 1787
r src/egw_experiments/protocol.py 112
r src/egw_experiments/run.py 2983
r src/egw_simulator/publisher.py 160 167
r docs/setup/qemu_integrated_gateway.md 1112
r docs/setup/qemu_integrated_gateway.md 1114
r docs/setup/qemu_integrated_gateway.md 1116 1138
r docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md 104
r docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md 630 631
r docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md 638 640
r docs/claim_evidence_matrix.md 173
r PROGRESS.md 509
r PROGRESS.md 180
echo "--- docs/governance/proposals/acceptance_protocol_update_2026-09-19.md present?"
g cat-file -e "$REF:docs/governance/proposals/acceptance_protocol_update_2026-09-19.md" 2>/dev/null && echo present || echo ABSENT
echo "--- ADR files at HEAD"; g ls-tree --name-only "$REF" docs/adr/
echo; echo "######## lines this verification relies on (not cited by the documents)"
r src/egw_experiments/analyze.py 2704 2719
r src/egw_experiments/protocol.py 168
r docs/setup/qemu_integrated_gateway.md 1183 1183
echo "--- runbook :1004, the drained blind spot and the clean session"
g show "$REF:docs/setup/qemu_integrated_gateway.md" | sed -n '1004p' | grep -o -E 'this is excluded only by[^;]*;' | cut -c1-400
echo "--- which of the nine runbook tests call drained, run_test (-> pre -> drained), pre or harness_run"
F=docs/setup/qemu_integrated_gateway.md
for t in 1 2 3 4 5 6 7 8 9; do
  s=$(g show "$REF:$F" | grep -n "^### Test $t " | cut -d: -f1)
  e=$(g show "$REF:$F" | awk -v s="$s" 'NR>s && /^### Test [0-9]|^## 8/ {print NR; exit}')
  echo "test $t (lines $s-$e): $(g show "$REF:$F" | sed -n "${s},${e}p" | grep -o -E 'run_test|drained|harness_run|pre [$]R' | sort | uniq -c | tr '\n' ' ')"
done
echo "--- the ad-hoc test path: pre -> drained (host helper, outside the repository)"
grep -n -E '^pre\(\)|wait_ready "\$\{READY_LIMIT_S:-60\}" && drained' "$HOME/egw-tcg/itest-helpers.sh" | cut -c1-160
echo; echo "######## what this clone knows of dev, and code identity at HEAD"
g for-each-ref --format='%(refname) %(objectname:short)' refs/remotes/origin/dev refs/remotes/upstream/dev
echo "fe954a9..HEAD -- src/egw_controller:"; g diff --stat fe954a9 HEAD -- src/egw_controller; echo "(end)"
echo "8e88670..HEAD -- controller, compose, mosquitto, Dockerfile, pyproject:"
g diff --stat 8e88670 HEAD -- src/egw_controller src/deployment/compose.yaml src/deployment/mosquitto src/Dockerfile src/pyproject.toml; echo "(end)"
echo "--- where the plan phrases the ADR cites sit at HEAD"
g show "$REF:docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md" | grep -n -E 'material changes require an ADR|controller restart with recovery inside|sizing finding' | cut -c1-200
echo "--- where the PROGRESS.md phrase the ADR cites sits at HEAD"
g show "$REF:PROGRESS.md" | grep -n -E 'without a hashed lock' | cut -c1-200
