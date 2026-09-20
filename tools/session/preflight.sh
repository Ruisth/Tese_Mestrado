#!/bin/bash
# Work order 2.C step 1: a brief live collector and preflight check with all
# six real services. Starts the stack through the runbook 5.5 interlock,
# installs the dev collector, records the deployed tree against the clean
# clone, checks health, memory/OOM, storage, clocks and broker secrets, then
# runs the collector for 45 s with the six expected services and fetches the
# CSV with its companions. Exports on success and on failure.
#
# Every step is a PREREQUISITE (its failure means the check did not run: the
# steps after it are skipped and named as not run, outcome not-run, exit 2) or
# a MANDATORY instrumentation step (its failure leaves the run invalid, exit 3).
# README.md, "Exit statuses", lists which is which.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "live preflight" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
trap 'driver_interrupt "$A"' INT TERM

NEW=$REPO/src/deployment/scripts/collect-resources.sh
NEWSHA=$(sha256sum "$NEW" | cut -d' ' -f1)
RID=preflight-$(date -u +%Y%m%dT%H%M%SZ)
CSV=$A/analysis/collector/resources-$RID.csv
mkdir -p "$A/analysis/collector"

STEPS=(stack-start-interlock collector-copy collector-install deployed-tree-hashes deployed-vs-clone
       controller-health stack-health broker-secrets-check clock-offset guest-clock
       sut-environment sut-environment-fetch collector-live fetch-collector-output collector-check
       collector-duration)
prerequisite=()   # failures that mean the preflight did not run
mandatory=()      # failed mandatory instrumentation: the run is invalid
skipped=()        # steps not run after a failed prerequisite

# stop_after NAME: record every step after NAME as not run.
stop_after() {
    local seen=0 s
    for s in "${STEPS[@]}"; do
        [ "$seen" -eq 1 ] && skipped+=("$s")
        [ "$s" = "$1" ] && seen=1
    done
}

# prereq NAME RC REASON: classify a prerequisite step and say whether the
# sequence may go on. A lost console capture (74) means the step itself ran, so
# it is recorded as the capture having failed (mandatory: invalid, code 3) and
# never as the preflight not having run.
prereq() {
    [ "$2" -eq 0 ] && return 0
    if [ "$2" -eq "$EXIT_CAPTURE_LOST" ]; then
        mandatory+=("$(capture_note "$1")")
    else
        prerequisite+=("$3")
    fi
    stop_after "$1"
    return 1
}

# mand NAME RC REASON: record a failed mandatory step, naming a lost console
# capture as such. The steps after it still run.
mand() {
    [ "$2" -eq 0 ] && return 0
    mandatory+=("$(step_note "$1" "$2" "$3")")
    return 1
}

# The identity of the clean clone is part of every verdict this driver records.
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$IDENTITIES" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"collector_samples\": \"45 s at 1 s\", \"expected_services\": \"$EXPECT_SERVICES\"}") \
    || prerequisite+=("the attempt fields could not be recorded")
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || prerequisite+=("the identity of the clean clone could not be read (see identities.identity_error)")
[ "${#prerequisite[@]}" -eq 0 ] || skipped=("${STEPS[@]}")

# The steps, in the runbook's order. A failed prerequisite ends this function.
steps() {
    gx "$A" stack-start-interlock "cd /opt/egw/deployment && stat -c '%u:%g %n' data/events && if ls scripts/prepare-broker-secrets.sh scripts/probe-acl.sh >/dev/null && grep -q '3b\.' scripts/validate-config.sh && sh scripts/verify-controller-image.sh /opt/egw/images/egw-controller-0.1.0-arm64.identity.txt && sh scripts/validate-config.sh; then $DC up -d; rc=\$?; echo \"up exit=\$rc\"; exit \$rc; else echo 'STOP: interlock failed - the stack was NOT started'; exit 1; fi"
    prereq stack-start-interlock $? "stack start interlock failed" || return

    # The collector that runs must be the clean clone's, byte for byte: the
    # copy and the installed file are both compared with the clone's sha256.
    gcp "$A" collector-copy "$NEW" egw@127.0.0.1:/tmp/collect-resources.new.sh
    mand collector-copy $? "collector copy failed"
    gx "$A" collector-install "set -e
OLDSHA=\$(sha256sum /opt/egw/deployment/scripts/collect-resources.sh | cut -d' ' -f1)
COPYSHA=\$(sha256sum /tmp/collect-resources.new.sh | cut -d' ' -f1)
[ \"\$COPYSHA\" = \"$NEWSHA\" ] || { echo \"STOP: the copied collector is not the clone's (\$COPYSHA, expected $NEWSHA)\"; exit 1; }
sudo mkdir -p /opt/egw/evidence/collector-previous
sudo cp /opt/egw/deployment/scripts/collect-resources.sh /opt/egw/evidence/collector-previous/collect-resources.\$OLDSHA.sh
sudo cp /tmp/collect-resources.new.sh /opt/egw/deployment/scripts/collect-resources.sh
sudo chmod 0755 /opt/egw/deployment/scripts/collect-resources.sh
echo \"previous=\$OLDSHA\"
sha256sum /opt/egw/deployment/scripts/collect-resources.sh
GOTSHA=\$(sha256sum /opt/egw/deployment/scripts/collect-resources.sh | cut -d' ' -f1)
[ \"\$GOTSHA\" = \"$NEWSHA\" ] || { echo \"STOP: the installed collector is not the clone's (\$GOTSHA, expected $NEWSHA)\"; exit 1; }"
    mand collector-install $? "collector install failed: the installed collector is not the clean clone's"

    # The listing's exclusions are passed to the comparison, which walks the
    # clone as well: a deployed file the guest has LOST is a difference too.
    gx "$A" deployed-tree-hashes "cd /opt/egw/deployment && sudo find . -type f ! -path './data/*' ! -name .env ! -name passwd ! -path './mosquitto/config/certs/*' -exec sha256sum {} + | sort -k2"
    prereq deployed-tree-hashes $? "the deployed tree could not be listed" || return
    OUTF=$(ls "$A"/console/*-deployed-tree-hashes.stdout.txt 2> /dev/null | tail -n 1)
    # README.md is the only deployed file allowed to differ from the clone.
    if [ -z "$OUTF" ]; then
        prerequisite+=("the deployed tree listing was not kept")
        stop_after deployed-tree-hashes
        return
    fi
    ex "$A" deployed-vs-clone "$PY" "$DRIVERS/deployed_vs_clone.py" \
        --exclude 'data/*' --exclude .env --exclude passwd --exclude 'mosquitto/config/certs/*' \
        -- "$OUTF" "$REPO/src/deployment" README.md
    prereq deployed-vs-clone $? "the deployed tree differs from the clean clone" || return

    hx "$A" controller-health 'for p in health ready metrics; do printf "%s: " $p; curl -s -m 30 -o /tmp/egw-pf-$p.json -w "%{http_code}\n" "$CTRL/$p"; cat /tmp/egw-pf-$p.json; echo; done; wait_ready 300 && echo "READY"'
    prereq controller-health $? "controller not ready" || return

    # All six expected services running and healthy, none OOMKilled. A dmesg
    # that cannot be read leaves the OOM state of this boot UNKNOWN, which is
    # not "no OOM": it fails the step.
    gx "$A" stack-health "cd /opt/egw/deployment || exit 1
rc=0
$DC ps --format '{{.Name}} {{.State}} {{.Health}}'
echo '## the six expected services'
SERVICES=$EXPECT_SERVICES
IFS=,
set -- \$SERVICES
unset IFS
for s in \"\$@\"; do
    st=\$(docker inspect -f '{{.State.Status}}' \"\$s\" 2>/dev/null) || st=absent
    hl=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \"\$s\" 2>/dev/null) || hl=unknown
    om=\$(docker inspect -f '{{.State.OOMKilled}}' \"\$s\" 2>/dev/null) || om=unknown
    rs=\$(docker inspect -f '{{.RestartCount}}' \"\$s\" 2>/dev/null) || rs=unknown
    echo \"\$s status=\$st health=\$hl OOMKilled=\$om restarts=\$rs\"
    [ \"\$st\" = running ] || rc=1
    [ \"\$hl\" = healthy ] || rc=1
    [ \"\$om\" = false ] || rc=1
done
echo '## every container'
for c in \$(docker ps -a --format '{{.Names}}'); do echo \"\$c OOMKilled=\$(docker inspect -f '{{.State.OOMKilled}}' \$c) restarts=\$(docker inspect -f '{{.RestartCount}}' \$c)\"; done
echo '## memory-cgroup OOM lines this boot'
if KMSG=\$(sudo -n dmesg 2>/dev/null); then
    N=\$(printf '%s\n' \"\$KMSG\" | grep -ci 'memory cgroup out of memory' || true)
    echo \"memory-cgroup OOM lines: \$N\"
    [ \"\$N\" = 0 ] || rc=1
else
    echo 'dmesg could not be read: the OOM state of this boot is UNKNOWN, which is not \"no OOM\"'
    rc=1
fi
echo '## storage'; df -h / /var/lib/docker /tmp; free -m
echo '## docker stats (one sample; slow under TCG)'; docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.MemPerc}} {{.CPUPerc}}'
exit \$rc"
    prereq stack-health $? "the stack is not healthy, a container was OOMKilled, or the OOM state is unknown" || return

    gx "$A" broker-secrets-check "cd /opt/egw/deployment && sh scripts/prepare-broker-secrets.sh --check --acl; rc=\$?; echo \"check exit=\$rc\"; exit \$rc"
    prereq broker-secrets-check $? "broker secrets check failed" || return

    # Both clock steps are LISTS of commands, so each accumulates its own rc:
    # the offset the harness's confirmation deadlines depend on must not be
    # left unobserved behind the echo that ends the loop, and a timedatectl
    # that cannot reach the time daemon must not hide behind 'date -u'.
    ex "$A" clock-offset env E="$SESSION" bash -c '. "$E/scripts/session_common.sh"; rc=0; for i in 1 2 3; do h0=$(date +%s.%N) || rc=1; g=$(gssh "date +%s") || rc=1; h1=$(date +%s.%N) || rc=1; [ -n "$g" ] || rc=1; echo "host_before=$h0 guest=$g host_after=$h1"; done; exit $rc'
    mand clock-offset $? "the host/guest clock offset was not observed"
    gx "$A" guest-clock 'rc=0; timedatectl show || rc=1; date -u || rc=1; exit $rc'
    mand guest-clock $? "the guest clock was not read"

    # SUT environment with the emulation label (runbook 5.8).
    gx "$A" sut-environment "cd /opt/egw/deployment && EGW_PROVIDER='QEMU 8.2.7 TCG (qemu-system-native) on WSL2 Ubuntu-24.04, Windows 11 x86-64' EGW_REGION='local-workstation' EGW_INSTANCE_TYPE='qemu -machine virt -cpu cortex-a76 -smp 4 -m 8192; ARM64 EMULATED' EGW_SHARED_VCPU_NOTE='TCG emulation on a shared x86-64 host; load generator co-located; never native ARM64' sh scripts/capture-sut-environment.sh /opt/egw/evidence/sut_environment.json && cat /opt/egw/evidence/sut_environment.json"
    prereq sut-environment $? "SUT environment capture failed" || return
    gcp "$A" sut-environment-fetch egw@127.0.0.1:/opt/egw/evidence/sut_environment.json "$A/environment/sut_environment.json"
    prereq sut-environment-fetch $? "SUT environment fetch failed" || return

    # Live collector: 45 s, six expected services, then CSV + companions
    # through the repository's fetch helper, which checks every mandatory file
    # against the guest's own sha256 (an absent optional .self-test marker is
    # explicitly optional and does not fail the fetch).
    gx "$A" collector-live "sudo systemd-run --unit egw-resources-$RID --collect sh /opt/egw/deployment/scripts/collect-resources.sh /tmp/resources-$RID.csv --duration 45 --expect-services $EXPECT_SERVICES && sleep 55 && systemctl is-active egw-resources-$RID; sudo -n journalctl -u egw-resources-$RID --no-pager | tail -n 20; ls -la /tmp/resources-$RID.csv*"
    mand collector-live $? "the live collector run left no output"
    hx "$A" fetch-collector-output "sh '$REPO/src/deployment/scripts/fetch-collector-output.sh' egw-tcg /tmp/resources-$RID.csv '$CSV'"
    mand fetch-collector-output $? "the collector output was not fetched and verified against the guest's sha256"
    ex "$A" collector-check "$PY" "$DRIVERS/collector_check.py" "$A/analysis/collector" "$RID" "$EXPECT_SERVICES" "$NEWSHA" "$A/environment/sut_environment.json"
    mand collector-check $? "live collector check failed (see analysis/collector/collector-check.json)"
    # The check above validates the collection against the COLLECTOR'S OWN
    # window, so a collector that died at two thirds of the duration its own
    # 'start:' line declares reconciles with itself and reads clean there. This
    # driver is the one that starts the collector, so it is the one that judges
    # the shortfall the check publishes (against that declaration: the 45 s
    # asked for above is not compared with it). Like every other step it goes through 'ex', so the
    # judgement's own stdout, stderr and exit code reach console/ and
    # commands.jsonl even when the helper could not run at all, and the cause
    # recorded for a failure is a sentence, never the helper's empty stdout.
    ex "$A" collector-duration "$PY" "$DRIVERS/collector_shortfall.py" \
        "$A/analysis/collector/collector-check.json"
    mand collector-duration $? "the collector did not hold the duration it declares, or the shortfall could not be judged (see console/ and commands.jsonl)"
}

[ "${#prerequisite[@]}" -eq 0 ] && steps

if [ "${#prerequisite[@]}" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "prerequisite failed: $(printf '%s; ' "${prerequisite[@]}")not run: ${skipped[*]}" \
        --next-action "STOP: fix before any longer test; the preflight did not run as a check")
elif [ "${#mandatory[@]}" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome inconclusive \
        --reason "the preflight ran, but mandatory instrumentation failed: $(printf '%s; ' "${mandatory[@]}")${skipped[*]:+not run: ${skipped[*]}}" \
        --next-action "STOP: read console/ and analysis/collector/; the instrumentation is not usable")
else
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "stack up through the interlock; dev collector deployed and live-checked with six services" \
        --next-action "smartwatch slice, then the nominal entry")
fi
driver_exit "$A"
