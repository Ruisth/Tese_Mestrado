#!/usr/bin/env bash
# Every file:line cited in adr-0011-controller-restart-recovery.md, printed at
# the merged dev head. Read-only: `git show`, `git grep`, `git diff --stat`,
# `git log` and `grep` only; nothing is checked out, written or fetched.
#
# Run from Git Bash:
#   bash <this directory>/adr0011_code_anchors.sh > <this directory>/../out/adr0011_code_anchors.out.txt 2>&1
set -u
# The worktree is located relative to this script (scripts/ -> v2/ -> pkgD/ -> the working
# directory that holds devwt/), or given explicitly in EGW_WORKTREE.
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${EGW_WORKTREE:-$(cd "$HERE/../../../devwt" && pwd)}
REF=35fe8bb
g() { git -C "$REPO" "$@"; }
# range <path> <from> <to>: numbered lines of <path> at $REF
range() { echo "--- $1:$2-$3"; g show "$REF:$1" | awk -v a="$2" -v b="$3" 'NR>=a && NR<=b {printf "%5d  %s\n", NR, $0}'; }
# find <path> <ERE>: numbered matching lines of <path> at $REF
find() { echo "--- $1 =~ /$2/"; g show "$REF:$1" | grep -n -E "$2" | cut -c1-220; }
# absent <path> <ERE>: prove a pattern does not occur
absent() { if g show "$REF:$1" | grep -q -E "$2"; then echo "PRESENT in $1: /$2/"; else echo "absent from $1: /$2/"; fi; }

echo "== identity of the merged head"
g log -1 --format='%H | author %an <%ae> | committer %cn <%ce> | %ci | %s' "$REF"
g log -1 --format='%H %s' origin/dev
echo "== ADR numbers ever added on any ref"
g log --all --diff-filter=A --name-only --format='' -- docs/adr/ | sort -u
echo "== references to 0009 and 0011 at $REF"
g grep -n -E '\b0009\b' "$REF" -- docs/adr docs/reviews/2026-09-17-egw-image-audit.md docs/evidence/integrated-qemu/2026-09-18-mongodb7-isolated/README.md | cut -c1-200
out11=$(g grep -n -E '\b0011\b' "$REF" -- . ':!docs/evidence')
if [ -n "$out11" ]; then echo "$out11" | cut -c1-200; else echo "no reference to 0011 outside docs/evidence at $REF"; fi

echo "== code identity: the controller between the run commits and $REF"
for c in 8e88670 fe954a9 ccd5fd6; do
  echo "diff --stat $c..$REF -- src/egw_controller src/deployment src/Dockerfile src/pyproject.toml:"
  g diff --stat "$c" "$REF" -- src/egw_controller src/deployment/compose.yaml src/deployment/mosquitto src/Dockerfile src/pyproject.toml
  echo "(end)"
done
echo "diff --stat 8e88670..$REF -- src/CONTRACTS.md:"; g diff --stat 8e88670 "$REF" -- src/CONTRACTS.md; echo "(end)"

echo "== MQTT bridge"
range src/egw_controller/mqtt.py 71 85
range src/egw_controller/mqtt.py 103 103
range src/egw_controller/mqtt.py 149 152
range src/egw_controller/mqtt.py 180 185
range src/egw_controller/mqtt.py 187 199
range src/egw_controller/mqtt.py 211 217
echo "--- manual_ack / clean_session anywhere under src/"
g grep -n -E 'manual_ack|clean_session' "$REF" -- src || echo "no match under src/"

echo "== service"
range src/egw_controller/service.py 39 39
range src/egw_controller/service.py 81 87
range src/egw_controller/service.py 150 169
range src/egw_controller/service.py 182 201
range src/egw_controller/service.py 287 292
range src/egw_controller/service.py 303 314
range src/egw_controller/service.py 316 343
range src/egw_controller/service.py 414 415
echo "--- signal / atexit / fsync in the package"
g grep -n -E 'signal|atexit|fsync' "$REF" -- src/egw_controller || echo "no match"

echo "== app, events, dedupe, ditto, metrics, config"
range src/egw_controller/app.py 140 164
range src/egw_controller/events.py 112 119
range src/egw_controller/dedupe.py 21 21
range src/egw_controller/dedupe.py 52 54
range src/egw_controller/dedupe.py 91 113
find src/egw_controller/ditto.py 'last_message_id|last_seq|last_run_id|last_ts|accepted_count'
find src/egw_controller/ditto.py 'TransportError|attempts|def _request|def patch_thing'
find src/egw_controller/metrics.py '"received"|"in_progress"|"processing_errors"|"started_at"|"uptime_s"|def snapshot'
find src/egw_controller/config.py 'queue|QUEUE|egw_id|EGW_ID'

echo "== contract"
range src/CONTRACTS.md 5 9
range src/CONTRACTS.md 16 16
range src/CONTRACTS.md 186 195
range src/CONTRACTS.md 272 273
range src/CONTRACTS.md 282 291
range src/CONTRACTS.md 304 306
range src/CONTRACTS.md 369 374

echo "== deployment"
range src/deployment/compose.yaml 46 52
range src/deployment/compose.yaml 84 88
range src/deployment/compose.yaml 253 256
range src/deployment/compose.yaml 290 290
range src/deployment/compose.yaml 309 313
absent src/deployment/compose.yaml 'stop_grace_period|stop_signal'
range src/deployment/mosquitto/config/mosquitto.conf 33 35
range src/deployment/mosquitto/config/mosquitto.conf 47 56
echo "mosquitto.conf line count: $(g show "$REF:src/deployment/mosquitto/config/mosquitto.conf" | wc -l)"
absent src/deployment/mosquitto/config/mosquitto.conf 'max_inflight_messages|max_queued_messages|persistent_client_expiration|max_inflight_bytes|max_queued_bytes'
find src/deployment/images.lock.env '^IMAGE_MOSQUITTO'
find src/Dockerfile 'pip install|^CMD|STOPSIGNAL|uvicorn'
absent src/Dockerfile 'STOPSIGNAL'
range src/pyproject.toml 10 16

echo "== harness, analysis, simulator"
range src/egw_experiments/controller_metrics.py 53 64
find src/egw_experiments/analyze.py '^\s*(lost|delivered|late_confirmations|double_accepted)|outcome == "accepted"'
range src/egw_experiments/analyze.py 1645 1655
find src/egw_experiments/protocol.py 'MAX_SAMPLE_GAP_S|RESTART_RECOVERY_MAX_S'
range src/egw_simulator/publisher.py 160 167

echo "== runbook"
find docs/setup/qemu_integrated_gateway.md '^drained\(\)|DRAIN_QUIET_S:-|DRAIN_LIMIT_S:-|export DRAIN_QUIET_S=490'
find docs/setup/qemu_integrated_gateway.md '^### Test 5|^### Test 6|^### Test 7|RESTART="ssh|restart controller|Every .delta. line must be|RESTART_RECOVERY_MAX_S|proposed, not adopted'
find docs/setup/qemu_integrated_gateway.md 'failed the deadline criterion above|326 late'

echo "== further anchors used in the text"
range docs/setup/qemu_integrated_gateway.md 1112 1112 | cut -c1-200
range docs/setup/qemu_integrated_gateway.md 1123 1123 | cut -c1-200
range src/CONTRACTS.md 348 351
range src/CONTRACTS.md 23 25
range src/egw_controller/service.py 390 390
range src/egw_controller/metrics.py 162 162
range src/egw_experiments/analyze.py 1780 1787
range src/egw_experiments/run.py 2983 2983
range src/deployment/compose.yaml 69 69
range src/deployment/compose.yaml 250 252
range src/deployment/mosquitto/config/mosquitto.conf 29 31
find docs/claim_evidence_matrix.md '^\| C12 '
find PROGRESS.md 'without a hashed lock'

echo "== plan and governance"
range docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md 104 104
find docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md '^\*\*G3 — P0 feature freeze|controller restart with recovery inside|dropout and reconnection with no loss|sizing finding'
g ls-tree --name-only "$REF" docs/governance/proposals/acceptance_protocol_update_2026-09-19.md docs/governance/decisions/2026-09-21-g2-closure.md
echo "--- the pause on the G3 qualifying runs: branch docs/g3-pause-answer, not on dev"
g log -1 --format='%H | %an | %cn | %ci | %s' 3549d46
g merge-base --is-ancestor 3549d46 "$REF" && echo "3549d46 IS on $REF" || echo "3549d46 is NOT an ancestor of $REF"
g show 3549d46:PROGRESS.md | grep -n -E 'stays on the G3 qualifying runs' | cut -c1-240

echo "== paho-mqtt in the analysis venv (NOT evidence about the image)"
wsl -d Ubuntu-24.04 --exec bash -lc 'P=$(ls -d ~/egw-exec/venv/lib/python3*/site-packages/paho/mqtt); grep -n "__version__" $P/__init__.py; grep -n -E "manual_ack: bool = False|self._manual_ack = manual_ack|clean_session = True|elif message.qos == 1:|return self._send_puback\(message.mid\)|def _send_puback|def ack\(self|def manual_ack_set" $P/client.py; echo "--- paho ack() body"; awk "NR>=4165 && NR<=4176 {printf \"%5d  %s\n\", NR, \$0}" $P/client.py'
echo "== uvicorn in the analysis venv (NOT evidence about the image)"
wsl -d Ubuntu-24.04 --exec bash -lc 'U=$(ls -d ~/egw-exec/venv/lib/python3*/site-packages/uvicorn); grep -n "^__version__" $U/__init__.py; grep -n -E "HANDLED_SIGNALS = |def handle_exit|self.should_exit = True|timeout_graceful_shutdown" $U/server.py | head; grep -n -E "async def shutdown|shutdown_event.wait|await self.shutdown_event" $U/lifespan/on.py'

echo "== round three: anchors added by the corrections of 2026-09-21"
echo "--- the exception path that consumes a message without a line (section 1.1)"
range src/egw_controller/service.py 191 197
echo "--- runbook: the quiet window's clean-session premise, test 5's expected list, test 6's delta rule, test 8"
range docs/setup/qemu_integrated_gateway.md 1004 1004 | cut -c1-120
g show "$REF:docs/setup/qemu_integrated_gateway.md" | sed -n '1004p' | grep -o -E 'together with the bridge not asking the broker for a persistent session'
g show "$REF:docs/setup/qemu_integrated_gateway.md" | sed -n '1112p' | grep -o -E 'duplicates. \(QoS 1 redelivery after reconnect\) are not failures, .double_accepted. must be 0'
g show "$REF:docs/setup/qemu_integrated_gateway.md" | sed -n '1130p' | grep -o -E 'Every .delta. line must be .OK.'
range docs/setup/qemu_integrated_gateway.md 1138 1138 | cut -c1-160
range docs/setup/qemu_integrated_gateway.md 1183 1183
echo "--- harness C12 gate: delivery across the restart requires lost == 0"
range src/egw_experiments/analyze.py 2704 2707
range src/egw_experiments/analyze.py 2715 2718
echo "--- ADR 0010: shutdown sequence unchanged; the shutdown exclusion in the contract"
range docs/adr/0010-controller-progress-counters.md 79 81
range docs/adr/0010-controller-progress-counters.md 113 116
range docs/adr/0010-controller-progress-counters.md 139 142
echo "--- plan: the sizing-finding rule, quoted"
range docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md 638 640
echo "--- the protocol proposal: the design decision after the guest-side evidence"
range docs/governance/proposals/acceptance_protocol_update_2026-09-19.md 418 425
range docs/governance/proposals/acceptance_protocol_update_2026-09-19.md 450 454
echo "--- the plan and PROGRESS.md anchors at b7e0c83 (the WSL clone and the G2 execution commit), for contrast"
for n in 104 630 631 638 639 640; do
  printf "plan:%s at %s: " "$n" "$REF"; g show "$REF:docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md" | sed -n "${n}p" | cut -c1-90
  printf "plan:%s at b7e0c83: " "$n"; g show "b7e0c83:docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md" | sed -n "${n}p" | cut -c1-90
done
echo "PROGRESS.md lines at $REF: $(g show "$REF:PROGRESS.md" | wc -l); at b7e0c83: $(g show b7e0c83:PROGRESS.md | wc -l)"
g show "$REF:PROGRESS.md" | sed -n '509p' | cut -c1-160
echo "--- LOG.md entry #C039 with the pause answer: at 3549d46 only"
g show 3549d46:LOG.md | grep -n -E 'the student decided on 2026-09-21 that it stays on the G3 qualifying runs' | cut -c1-120
g show "$REF:LOG.md" | grep -c -E 'the student decided on 2026-09-21 that it stays on the G3 qualifying runs' | sed 's/^/occurrences at the merged head: /'
echo "--- paho-mqtt 2.1.0 manual acknowledgement docstring (analysis venv; NOT evidence about the image)"
wsl -d Ubuntu-24.04 --exec bash -lc 'P=$(ls -d ~/egw-exec/venv/lib/python3*/site-packages/paho/mqtt); awk "NR>=4177 && NR<=4182 {printf \"%5d  %s\n\", NR, \$0}" $P/client.py'
echo "--- the ad-hoc helpers (~/egw-tcg/itest-helpers.sh, outside the repository): reading timeout, pre, finish"
wsl -d Ubuntu-24.04 --exec bash -lc 'awk "NR==30 || (NR>=173 && NR<=179) || (NR>=193 && NR<=196) {printf \"%5d  %s\n\", NR, substr(\$0,1,170)}" ~/egw-tcg/itest-helpers.sh'
echo "--- which of the nine runbook tests call drained, run_test (-> pre -> drained), pre or harness_run, at $REF"
g show "$REF:docs/setup/qemu_integrated_gateway.md" | awk '
  /^### Test [1-9] / { if (t) print_it(); t=$3; start=NR; d=0; r=0; p=0; h=0; next }
  /^## / { if (t) { print_it(); t="" } }
  t { d+=gsub(/(^|[^a-z_])drained([^a-z_]|$)/,"&"); r+=gsub(/run_test /,"&"); p+=gsub(/(^|[ ;&(])pre \$/,"&"); h+=gsub(/harness_run /,"&") }
  function print_it() { printf "test %s (from line %d): drained %d, run_test %d, pre %d, harness_run %d\n", t, start, d, r, p, h }
  END { if (t) print_it() }'
