#!/bin/bash
# Work order 2.C step 1: a brief live collector and preflight check with all
# six real services. Starts the stack through the runbook 5.5 interlock,
# installs the dev collector, records the deployed tree against the clean
# clone, checks health, memory/OOM, storage, clocks and broker secrets, then
# runs the collector for 45 s with the six expected services and fetches the
# CSV with its companions. Exports on success and on failure.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || { echo "STOP: no open session" >&2; exit 1; }
A=$(new_attempt "live preflight" engineering) || exit 1
trap '(cd "$REPO/src" && $LE finish --attempt "$A" --status interrupted --outcome interrupted --reason "driver interrupted" 2>/dev/null); export_attempt "$A"' INT TERM
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$(repo_identity)" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"collector_samples\": \"45 s at 1 s\", \"expected_services\": \"$EXPECT_SERVICES\"}")
problems=()

gx "$A" stack-start-interlock "cd /opt/egw/deployment && stat -c '%u:%g %n' data/events && if ls scripts/prepare-broker-secrets.sh scripts/probe-acl.sh >/dev/null && grep -q '3b\.' scripts/validate-config.sh && sh scripts/verify-controller-image.sh /opt/egw/images/egw-controller-0.1.0-arm64.identity.txt && sh scripts/validate-config.sh; then $DC up -d; echo \"up exit=\$?\"; else echo 'STOP: interlock failed - the stack was NOT started'; exit 1; fi" \
    || problems+=("stack start interlock failed")

NEW=$REPO/src/deployment/scripts/collect-resources.sh
NEWSHA=$(sha256sum "$NEW" | cut -d' ' -f1)
gcp "$A" collector-copy "$NEW" egw@127.0.0.1:/tmp/collect-resources.new.sh || problems+=("collector copy failed")
gx "$A" collector-install "set -e; OLDSHA=\$(sha256sum /opt/egw/deployment/scripts/collect-resources.sh | cut -d' ' -f1); sudo mkdir -p /opt/egw/evidence/collector-previous; sudo cp /opt/egw/deployment/scripts/collect-resources.sh /opt/egw/evidence/collector-previous/collect-resources.\$OLDSHA.sh; sudo cp /tmp/collect-resources.new.sh /opt/egw/deployment/scripts/collect-resources.sh; sudo chmod 0755 /opt/egw/deployment/scripts/collect-resources.sh; echo \"previous=\$OLDSHA\"; sha256sum /opt/egw/deployment/scripts/collect-resources.sh" \
    || problems+=("collector install failed")

gx "$A" deployed-tree-hashes "cd /opt/egw/deployment && sudo find . -type f ! -path './data/*' ! -name .env ! -name passwd ! -path './mosquitto/config/certs/*' -exec sha256sum {} + | sort -k2"
OUTF=$(ls "$A"/console/*-deployed-tree-hashes.stdout.txt | tail -n 1)
ex "$A" deployed-vs-clone "$PY" "$DRIVERS/deployed_vs_clone.py" "$OUTF" "$REPO/src/deployment"

hx "$A" controller-health 'for p in health ready metrics; do printf "%s: " $p; curl -s -m 30 -o /tmp/egw-pf-$p.json -w "%{http_code}\n" "$CTRL/$p"; cat /tmp/egw-pf-$p.json; echo; done; wait_ready 300 && echo "READY"' \
    || problems+=("controller not ready")
gx "$A" stack-health "cd /opt/egw/deployment && $DC ps --format '{{.Name}} {{.State}} {{.Health}}'; for c in \$(docker ps -a --format '{{.Names}}'); do echo \"\$c OOMKilled=\$(docker inspect -f '{{.State.OOMKilled}}' \$c) restarts=\$(docker inspect -f '{{.RestartCount}}' \$c)\"; done; echo '## memory-cgroup OOM lines this boot'; sudo -n dmesg | grep -ci 'memory cgroup out of memory' || true; echo '## storage'; df -h / /var/lib/docker /tmp; free -m; echo '## docker stats (one sample; slow under TCG)'; docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.MemPerc}} {{.CPUPerc}}'"
gx "$A" broker-secrets-check "cd /opt/egw/deployment && sh scripts/prepare-broker-secrets.sh --check --acl; echo \"check exit=\$?\"" \
    || problems+=("broker secrets check failed")
ex "$A" clock-offset env E="$SESSION" bash -c '. "$E/scripts/session_common.sh"; for i in 1 2 3; do h0=$(date +%s.%N); g=$(gssh "date +%s"); h1=$(date +%s.%N); echo "host_before=$h0 guest=$g host_after=$h1"; done'
gx "$A" guest-clock 'timedatectl show; date -u'

# SUT environment with the emulation label (runbook 5.8).
gx "$A" sut-environment "cd /opt/egw/deployment && EGW_PROVIDER='QEMU 8.2.7 TCG (qemu-system-native) on WSL2 Ubuntu-24.04, Windows 11 x86-64' EGW_REGION='local-workstation' EGW_INSTANCE_TYPE='qemu -machine virt -cpu cortex-a76 -smp 4 -m 8192; ARM64 EMULATED' EGW_SHARED_VCPU_NOTE='TCG emulation on a shared x86-64 host; load generator co-located; never native ARM64' sh scripts/capture-sut-environment.sh /opt/egw/evidence/sut_environment.json && cat /opt/egw/evidence/sut_environment.json" \
    || problems+=("SUT environment capture failed")
gcp "$A" sut-environment-fetch egw@127.0.0.1:/opt/egw/evidence/sut_environment.json "$A/environment/sut_environment.json" \
    || problems+=("SUT environment fetch failed")

# Live collector: 45 s, six expected services, then CSV + companions.
RID=preflight-$(date -u +%Y%m%dT%H%M%SZ)
gx "$A" collector-live "sudo systemd-run --unit egw-resources-$RID --collect sh /opt/egw/deployment/scripts/collect-resources.sh /tmp/resources-$RID.csv --duration 45 --expect-services $EXPECT_SERVICES && sleep 55 && systemctl is-active egw-resources-$RID; sudo -n journalctl -u egw-resources-$RID --no-pager | tail -n 20; ls -la /tmp/resources-$RID.csv*"
mkdir -p "$A/analysis/collector"
for suf in "" .diagnostics.log .lifecycle.csv; do
    gcp "$A" "fetch-resources$suf" "egw@127.0.0.1:/tmp/resources-$RID.csv$suf" "$A/analysis/collector/resources-$RID.csv$suf" \
        || problems+=("fetch of resources-$RID.csv$suf failed")
done
gx "$A" collector-remote-hashes "sha256sum /tmp/resources-$RID.csv /tmp/resources-$RID.csv.diagnostics.log /tmp/resources-$RID.csv.lifecycle.csv; ls /tmp/resources-$RID.csv.self-test 2>&1"
ex "$A" collector-check "$PY" "$DRIVERS/collector_check.py" "$A/analysis/collector" "$RID" "$EXPECT_SERVICES" "$NEWSHA" "$A/environment/sut_environment.json"
crc=$?
[ "$crc" -eq 0 ] || problems+=("live collector check failed (see analysis/collector/collector-check.json)")

if [ "${#problems[@]}" -eq 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "stack up through the interlock; dev collector deployed and live-checked with six services" \
        --next-action "smartwatch slice, then the nominal entry")
    rc=0
else
    reason=$(printf '%s; ' "${problems[@]}")
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome fail \
        --reason "$reason" --next-action "STOP: fix before any longer test")
    rc=1
fi
export_attempt "$A"
exit $rc
