#!/usr/bin/env bash
# v10 - spot-check of file:line anchors cited by backlog_diagnosis.md and ADR 0011.
# Read-only git plumbing only (git show / git rev-parse / git diff --stat); run from Git Bash.
# Usage: bash v10_anchors.sh <repo worktree>
set -u
R=${1:?repo}
cd "$R" || exit 2
H=35fe8bb
show() { # rev path from to
  echo "--- $1:$2:$3-$4"
  git show "$1:$2" 2>/dev/null | sed -n "$3,$4p" | nl -ba -v "$3"
}
echo "HEAD $(git rev-parse HEAD) ; $H = $(git rev-parse $H)"
for c in fe954a9 8e88670; do echo "diff --stat $c..$H src/egw_controller:"; git diff --stat "$c" "$H" -- src/egw_controller | tail -1; echo "(end)"; done
show $H src/egw_controller/service.py 36 40
show $H src/egw_controller/service.py 284 345
show $H src/egw_controller/service.py 386 418
show $H src/egw_controller/events.py 108 121
show $H src/egw_controller/dedupe.py 50 115
show $H src/egw_controller/ditto.py 66 76
show $H src/egw_controller/app.py 140 165
show $H src/egw_controller/metrics.py 160 182
show $H src/egw_experiments/controller_metrics.py 50 66
show $H src/egw_experiments/analyze.py 1764 1768
show $H src/egw_experiments/analyze.py 1778 1790
show $H src/egw_experiments/analyze.py 1806 1823
show $H src/egw_experiments/protocol.py 110 113
show $H src/egw_experiments/run.py 2980 2986
show $H src/deployment/compose.yaml 80 90
show $H src/deployment/compose.yaml 243 313
show $H src/deployment/mosquitto/config/mosquitto.conf 25 60
show $H src/deployment/images.lock.env 37 40
show $H src/Dockerfile 44 50
show $H src/pyproject.toml 8 14
show $H src/CONTRACTS.md 1 12
show $H src/CONTRACTS.md 184 196
show $H src/CONTRACTS.md 274 290
show $H src/CONTRACTS.md 300 308
show $H src/CONTRACTS.md 345 352
show $H docs/setup/qemu_integrated_gateway.md 1108 1140
show $H docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md 102 106
show $H docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md 628 642
show $H docs/claim_evidence_matrix.md 171 175
show $H PROGRESS.md 505 512
show 3549d46 PROGRESS.md 176 184
show 3549d46 LOG.md 1 5
echo "--- grep C039 in LOG.md at 3549d46 and at $H"
git show 3549d46:LOG.md | grep -n "C039" | head -5
git show $H:LOG.md | grep -n "C039" | head -5
echo "--- is 3549d46 an ancestor of $H?"
if git merge-base --is-ancestor 3549d46 $H; then echo yes; else echo no; fi
echo "--- grep 'compose.yaml' limits (cpus / mem_limit / deploy) at $H"
git show $H:src/deployment/compose.yaml | grep -n "cpus\|mem_limit\|memory\|cpu_" | head -30
echo "--- stop_grace_period / stop_signal / STOPSIGNAL"
git show $H:src/deployment/compose.yaml | grep -n "stop_grace_period\|stop_signal" ; git show $H:src/Dockerfile | grep -n STOPSIGNAL; echo "(end)"
echo "--- manual_ack / clean_session under src/"
git grep -n "manual_ack\|clean_session" $H -- src | head; echo "(end)"
