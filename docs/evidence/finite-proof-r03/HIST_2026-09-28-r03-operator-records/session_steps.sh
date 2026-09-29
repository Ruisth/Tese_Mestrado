#!/bin/bash
# The recorded steps of the finite-proof session that no driver of 489bc9e
# performs (decision packet revision 2, authorised by Rui on 2026-09-26):
#   load       runbook 4.4: stream-load the identified archive into the guest
#              engine and verify it against its record (previous record kept)
#   v1         V-1 go/no-go: a disposable container of the pinned broker image
#              with the stack's restart policy, killed and started as the
#              fault hook does; compatible = same id, later StartedAt, running,
#              UNCHANGED RestartCount, no OOM, both commands exit 0 (judged by
#              guest_state_delta.py --expect-restarted); V-3 observed alongside
#   deploy     runbook 5.1, single files: the four deployment files that differ
#              from the guest's tree of 23 September, previous versions kept,
#              owner and mode kept; nothing else touched
#   poststart  after preflight's 'up -d': the broker started after the
#              installation, no 'Reloading config' line, the mounted
#              configuration and the controller's label are the candidate's
# Each subcommand is ONE attempt, recorded and exported with the drivers' own
# common.sh / guest_common.sh (console/, commands.jsonl, SUMMARY.md,
# SHA256SUMS) and ends with their DRIVER RESULT line and exit code.
# Usage (WSL, login shell):
#   EGW_EXEC_REPO=/home/ruisth/egw-exec/repo bash session_steps.sh load|v1|deploy
#   EGW_EXEC_REPO=/home/ruisth/egw-exec/repo bash session_steps.sh poststart INSTALLED_EPOCH
set -u
SELF=$(readlink -f "$0")
: "${EGW_EXEC_REPO:?EGW_EXEC_REPO must name the clean 489bc9e clone}"
. "$EGW_EXEC_REPO/tools/session/common.sh"
. "$EGW_EXEC_REPO/tools/session/guest_common.sh"
DRIVERS=$REPO/tools/session
COMMIT=489bc9e5b5b0660026ea2630b8d1d124049ba2ce          # the controller image's source commit
# The clean clone the tools run from. For the second attempt (r02) the tools
# are at the quiet-timer repair while the controller image stays the one built
# from COMMIT: the two identities are checked apart, and never relabelled.
TOOLS_COMMIT=${EGW_TOOLS_COMMIT:-$COMMIT}
IMAGES=/home/ruisth/egw-images
ID_FILE=$IMAGES/egw-controller-0.1.0-arm64.identity.txt
TAR=$IMAGES/egw-controller-0.1.0-arm64.tar
PROBE=egw-v1-probe
FILES=(compose.yaml mosquitto/config/mosquitto.conf scripts/build-controller-image.sh README.md)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
CMD=${1:-}

[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
[ "$(git -C "$REPO" rev-parse HEAD 2> /dev/null)" = "$TOOLS_COMMIT" ] \
    || driver_stop "$EXIT_PREREQUISITE" "the clone $REPO is not at $TOOLS_COMMIT"
[ -z "$(git -C "$REPO" status --porcelain 2> /dev/null)" ] \
    || driver_stop "$EXIT_PREREQUISITE" "the clone $REPO is not clean"

# --- attempt bookkeeping ------------------------------------------------------
start_attempt() {
    local ids
    A=$(new_attempt "$1" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
    trap 'end_attempt failed invalid interrupted "interrupted by a signal" "read console/; nothing is repeated automatically" "interrupted"' INT TERM
    ids=$(repo_identity) || { end_attempt failed invalid not-run "the identity of the clean clone could not be read" \
        "STOP: fix the clone before the session goes on" "clone identity not read"; }
    (cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "identities=$ids") > /dev/null \
        || end_attempt failed invalid not-run "the attempt fields could not be recorded" "STOP" "attempt fields not recorded"
    cp "$SELF" "$A/environment/session_steps.sh" \
        || end_attempt failed invalid not-run "this driver could not be kept in its attempt" "STOP" "driver not kept"
}

# end_attempt STATUS VALIDITY OUTCOME REASON NEXT HEADLINE: close, export, exit.
end_attempt() {
    trap - INT TERM
    (cd "$REPO/src" && $LE finish --attempt "$A" --status "$1" --validity "$2" --outcome "$3" \
        --reason "$4" --next-action "$5")
    headline "$A" "$6" || true
    driver_exit "$A"
}

# must NAME RC TEXT: a step without which the attempt cannot go on. A lost
# console capture is invalid instrumentation, a step that never reached the
# guest observed nothing, anything else is the step's own failure. Before the
# guest was changed that is 'not run'; once a step has changed it (CHANGED
# names what), it is inconclusive and the reason says what WAS changed.
CHANGED=""
must() {
    local changed=""
    [ "$2" -eq 0 ] && return 0
    [ -z "$CHANGED" ] || changed="; the guest WAS changed: $CHANGED"
    if [ "$2" -eq "$EXIT_CAPTURE_LOST" ]; then
        end_attempt failed invalid inconclusive "$(capture_note "$1")$changed" \
            "read commands.jsonl for the step's own exit code; nothing is repeated automatically" "$1: console capture lost"
    fi
    if [ -n "$CHANGED" ]; then
        end_attempt failed invalid inconclusive "$(step_note "$1" "$2" "$3")$changed" \
            "STOP: close the session safely and report; nothing is fixed and repeated automatically" "$1 failed (exit $2) after the guest was changed"
    fi
    end_attempt failed invalid not-run "$(step_note "$1" "$2" "$3")" \
        "STOP: report; nothing is fixed and repeated automatically" "$1 failed (exit $2)"
}

out_of() { ls "$A"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1; }

# --- load: runbook 4.4 ----------------------------------------------------------
do_load() {
    start_attempt "controller image load"
    ex "$A" host-archive-check bash -c '
        set -u; cd "$1" || exit 2
        f=egw-controller-0.1.0-arm64.identity.txt
        s=$(sed -n "s/^archive_sha256=//p" "$f"); [ -n "$s" ] || { echo "STOP: the record names no archive_sha256"; exit 1; }
        echo "$s  egw-controller-0.1.0-arm64.tar" | sha256sum -c - || { echo "STOP: the archive differs from its record"; exit 1; }
        grep -qx "source_tree_state=clean" "$f" || { echo "STOP: the record is not from a clean build context"; exit 1; }
        grep -qx "source_commit=$2" "$f" || { echo "STOP: the record is not of $2"; exit 1; }
        grep -qx "image_architecture=arm64" "$f" || { echo "STOP: the image is not arm64"; exit 1; }
        grep -q "^python_dependencies=LOCKED " "$f" || { echo "STOP: the dependencies are not locked"; exit 1; }
        grep -E "^(image_id|image_architecture|image_os|source_commit|source_tree_state|archive_sha256|python_dependencies|built_utc)=" "$f"' \
        _ "$IMAGES" "$COMMIT"
    must host-archive-check $? "the staged archive is not the identified $COMMIT build: nothing was loaded"

    gx "$A" guest-before "df -h / /var/lib/docker; docker image inspect -f 'image before: id={{.Id}} label={{index .Config.Labels \"org.opencontainers.image.revision\"}}' egw-controller:0.1.0 || echo 'no egw-controller:0.1.0 image before the load'; docker ps -a --format '{{.Names}} {{.Status}} {{.Image}}'"
    must guest-before $? "the guest state before the load was not recorded: nothing was loaded"

    gx "$A" keep-previous "set -u; P=/opt/egw/evidence/controller-image-previous/$STAMP
sudo mkdir -p \"\$P\" || exit 1
for f in /opt/egw/images/egw-controller-0.1.0-arm64.identity.txt /opt/egw/images/verify-controller-image.sh /opt/egw/evidence/controller-image-verify.txt; do
    if [ -e \"\$f\" ]; then sudo cp -p \"\$f\" \"\$P/\" || exit 1; else echo \"absent before the load: \$f\"; fi
done
sudo ls -l \"\$P\"; sudo sha256sum \"\$P\"/* 2> /dev/null; exit 0"
    must keep-previous $? "the previous identity record could not be kept: nothing was loaded"

    CHANGED="the archive may have been loaded into the guest engine (tag egw-controller:0.1.0)"
    ex "$A" stream-load env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" || exit 97
gssh docker load < "$1"' _ "$TAR"
    must stream-load $? "docker load of the identified archive failed: the controller image is NOT verified in the guest"
    CHANGED="the identified archive was loaded into the guest engine (tag egw-controller:0.1.0)"

    gx "$A" images-dir "mkdir -p /opt/egw/images && ls -ld /opt/egw/images"
    must images-dir $? "/opt/egw/images is not usable"
    gcp "$A" identity-copy "$ID_FILE" egw@127.0.0.1:/opt/egw/images/
    must identity-copy $? "the identity record was not copied to the guest"
    gcp "$A" verify-script-copy "$REPO/src/deployment/scripts/verify-controller-image.sh" egw@127.0.0.1:/opt/egw/images/
    must verify-script-copy $? "verify-controller-image.sh was not copied to the guest"

    gx "$A" verify-controller-image "mkdir -p /opt/egw/evidence && cd /opt/egw/images && sh verify-controller-image.sh egw-controller-0.1.0-arm64.identity.txt > /opt/egw/evidence/controller-image-verify.txt 2>&1; rc=\$?; cat /opt/egw/evidence/controller-image-verify.txt; exit \$rc"
    must verify-controller-image $? "the controller image identity was NOT verified on the guest: do not continue with the deployment"

    gx "$A" guest-after "df -h / /var/lib/docker; docker image inspect -f 'image after: id={{.Id}} label={{index .Config.Labels \"org.opencontainers.image.revision\"}} arch={{.Architecture}}' egw-controller:0.1.0; docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedSince}}'"
    must guest-after $? "the guest state after the load was not recorded"

    end_attempt finished valid pass "the identified $COMMIT archive was loaded and verified on the guest (previous record kept under /opt/egw/evidence/controller-image-previous/$STAMP)" \
        "V-1, then the candidate deployment" "identified image loaded and verified"
}

# --- v1: the V-1 go/no-go probe ---------------------------------------------------
PROBE_STATE="rc=0; c=$PROBE
pol=\$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' \$c) || rc=1
st=\$(docker inspect -f '{{.State.Status}} running={{.State.Running}} restarting={{.State.Restarting}} exit={{.State.ExitCode}}' \$c) || rc=1
echo \"probe policy=\${pol:-unknown} state=\${st:-unknown} guest_epoch=\$(date +%s)\"
oom=\$(docker inspect -f '{{.State.OOMKilled}}' \$c) || rc=1
res=\$(docker inspect -f '{{.RestartCount}}' \$c) || rc=1
cid=\$(docker inspect -f '{{.Id}}' \$c) || rc=1
sat=\$(docker inspect -f '{{.State.StartedAt}}' \$c) || rc=1
echo \"container \$c oomkilled=\${oom:-unknown} restarts=\${res:-unknown} id=\${cid:-unknown} started=\${sat:-unknown}\"
[ -n \"\$oom\" ] && [ -n \"\$res\" ] && [ -n \"\$cid\" ] && [ -n \"\$sat\" ] || rc=1
if KMSG=\$(sudo -n dmesg 2> /dev/null); then
    echo \"memory-cgroup OOM lines: \$(printf '%s\n' \"\$KMSG\" | grep -ci 'memory cgroup out of memory' || true)\"
else
    echo 'dmesg could not be read: the OOM state of this boot is UNKNOWN'; rc=1
fi
exit \$rc"

PROBE_REMOVE="docker rm -f -v $PROBE
if L=\$(docker ps -a --format '{{.Names}} {{.Status}}'); then
    if printf '%s\n' \"\$L\" | cut -d' ' -f1 | grep -qx '$PROBE'; then echo 'STOP: $PROBE is still there'; exit 1; fi
else
    echo 'STOP: the containers could not be listed after the removal'; exit 1
fi
echo '$PROBE removed with its anonymous volumes'; printf '%s\n' \"\$L\""
PROBE_UP=0

# probe_interrupted: the INT/TERM trap of the V-1 attempt. A probe that may
# exist is removed first (it carries 'unless-stopped' and would come back at
# every later boot), and the record says whether that removal succeeded.
probe_interrupted() {
    local note="interrupted by a signal"
    trap - INT TERM
    if [ "$PROBE_UP" = 1 ]; then
        if gx "$A" probe-remove-interrupted "$PROBE_REMOVE"; then
            note="$note; $PROBE removed"
        else
            note="$note; $PROBE MAY STILL EXIST on the guest: remove it (docker rm -f -v $PROBE) before anything else"
        fi
    fi
    end_attempt failed invalid interrupted "$note" "read console/; nothing is repeated automatically" "interrupted"
}

do_v1() {
    local rc before_rc kill_rc start_rc delta_rc running policy v3_rc remove_rc before after restarts0 v3
    start_attempt "v1 restart policy probe"
    gx "$A" stack-state "if L=\$(docker ps -a --format '{{.Names}} {{.Status}}'); then printf '%s\n' \"\$L\"; else echo 'STOP: the containers could not be listed'; exit 1; fi
if printf '%s\n' \"\$L\" | cut -d' ' -f1 | grep -qx '$PROBE'; then echo 'STOP: a container named $PROBE exists already'; exit 1; fi; exit 0"
    must stack-state $? "the guest's containers could not be listed, or a container named $PROBE exists already: nothing was started"

    # From here a probe may exist: the trap removes it before anything else.
    PROBE_UP=1
    trap probe_interrupted INT TERM
    gx "$A" probe-start "cd /opt/egw/deployment || exit 1
IMG=\$(sed -n 's/^IMAGE_MOSQUITTO=//p' images.lock.env); [ -n \"\$IMG\" ] || { echo 'STOP: IMAGE_MOSQUITTO not found'; exit 1; }
echo \"image=\$IMG\"; echo \"guest_epoch_before_run=\$(date +%s)\"
docker run -d --pull never --name $PROBE --label egw.v1.probe=$STAMP --restart unless-stopped --network none --memory 128m \"\$IMG\" || exit 1
i=0; while [ \$i -lt 30 ]; do [ \"\$(docker inspect -f '{{.State.Running}}' $PROBE)\" = true ] && break; sleep 1; i=\$((i + 1)); done
sleep 3
docker inspect -f 'ports={{json .HostConfig.PortBindings}} binds={{json .HostConfig.Binds}} mounts={{range .Mounts}}{{.Type}}:{{.Destination}} {{end}}network={{.HostConfig.NetworkMode}} memory={{.HostConfig.Memory}} policy={{.HostConfig.RestartPolicy.Name}} running={{.State.Running}}' $PROBE"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        gx "$A" probe-remove "$PROBE_REMOVE"
        remove_rc=$?
        [ "$remove_rc" -ne 0 ] || PROBE_UP=0
        [ "$remove_rc" -eq 0 ] || end_attempt failed invalid inconclusive "the disposable container could not be started (probe-start exit $rc) and could not be removed (probe-remove exit $remove_rc)" \
            "STOP: remove $PROBE (docker rm -f -v $PROBE) before anything else; close the session safely; report" "V-1 probe not removed"
        must probe-start "$rc" "the disposable container could not be started (it was removed again)"
    fi

    gx "$A" probe-state-before "$PROBE_STATE"
    before_rc=$?
    before=$(out_of probe-state-before)
    rc=0
    if [ "$before_rc" -eq 0 ]; then
        # The fault hook's two commands (proof_restart_controller.sh), with one
        # reading between them; whether the policy restarted the container by
        # itself is SEEN in the readings and in the events, and judged below.
        gx "$A" probe-kill-start "docker kill --signal=KILL $PROBE; k=\$?; echo \"kill exit=\$k guest_epoch=\$(date +%s)\"
docker inspect -f 'between: status={{.State.Status}} running={{.State.Running}} restarting={{.State.Restarting}} restarts={{.RestartCount}} started={{.State.StartedAt}} finished={{.State.FinishedAt}} exit={{.State.ExitCode}}' $PROBE
docker start $PROBE; s=\$?; echo \"start exit=\$s guest_epoch=\$(date +%s)\"
[ \$k -eq 0 ] && [ \$s -eq 0 ]"
        rc=$?
        kill_rc=$(grep -o 'kill exit=[0-9]*' "$(out_of probe-kill-start)" 2> /dev/null | cut -d= -f2)
        start_rc=$(grep -o 'start exit=[0-9]*' "$(out_of probe-kill-start)" 2> /dev/null | cut -d= -f2)
        gx "$A" probe-observe "sleep 10; echo \"observed 10 s after the start, guest_epoch=\$(date +%s)\""
        gx "$A" probe-state-after "$PROBE_STATE"
        after=$(out_of probe-state-after)
        # V-3 (proof_fetch_sut_log.sh): a bounded 'docker events' read returns
        # instead of following the daemon; the probe's own events, since its run.
        SINCE=$(sed -n 's/^guest_epoch_before_run=//p' "$(out_of probe-start)")
        ex "$A" v3-events timeout -k 10 60 env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" || exit 97
gssh "docker events --filter container=$1 --since $2 --until \$(date +%s)"' _ "$PROBE" "${SINCE:-0}"
        v3_rc=$?
    fi

    gx "$A" probe-remove "$PROBE_REMOVE"
    remove_rc=$?
    [ "$remove_rc" -ne 0 ] || PROBE_UP=0
    v3="V-3: the bounded docker events read returned (exit ${v3_rc:-not run})"
    [ "${v3_rc:-1}" -eq 0 ] || v3="V-3: the bounded docker events read did NOT return normally (exit ${v3_rc:-not run}; 124 = still following after 60 s)"
    [ "$remove_rc" -eq 0 ] || end_attempt failed invalid inconclusive "the disposable container could not be removed (probe-remove exit $remove_rc); $v3" \
        "STOP: remove $PROBE (docker rm -f -v $PROBE) before anything else; close the session safely; report" "V-1 probe not removed"
    must probe-state-before "$before_rc" "the probe's state before the fault could not be read (the probe was removed; no fault was issued)"
    # kill/start that ran and failed is an observation (judged below); a step
    # that never reached the guest or lost its capture is not.
    if [ "$rc" -eq "$EXIT_NOT_REACHED" ] || [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        must probe-kill-start "$rc" "the fault commands did not reach the guest (the probe was removed)"
    fi
    ex "$A" v1-judgement "$PY" "$DRIVERS/guest_state_delta.py" --expect "$PROBE" --expect-restarted "$PROBE" "$before" "$after"
    delta_rc=$?
    running=$(grep -o 'running=[a-z]*' "$after" 2> /dev/null | head -n 1 | cut -d= -f2)
    policy=$(grep -o 'policy=[a-z-]*' "$after" 2> /dev/null | head -n 1 | cut -d= -f2)
    restarts0=$(grep -o ' restarts=[^ ]*' "$before" 2> /dev/null | head -n 1 | cut -d= -f2)
    if [ "$delta_rc" -ne 0 ] && [ "$delta_rc" -ne 1 ]; then
        end_attempt failed invalid inconclusive "the two probe records could not be compared (guest_state_delta exit $delta_rc); $v3" \
            "STOP before the deployment and the proof; close the session safely; report" "V-1 not determined"
    fi
    if [ "$delta_rc" -eq 0 ] && [ "$kill_rc" = 0 ] && [ "$start_rc" = 0 ] && [ "$running" = true ] \
        && [ "$policy" = unless-stopped ] && [ "$restarts0" = 0 ]; then
        end_attempt finished valid pass "V-1 compatible: same id, later StartedAt, RestartCount 0 before and unchanged after, no OOM, running, kill and start exit 0 under restart policy unless-stopped; $v3" \
            "the candidate deployment" "V-1 compatible"
    fi
    end_attempt failed valid fail "V-1 incompatible: guest_state_delta exit $delta_rc, kill exit ${kill_rc:-?}, start exit ${start_rc:-?}, running=${running:-?}, policy=${policy:-?}, RestartCount before=${restarts0:-?} (see v1-judgement); $v3" \
        "STOP before the deployment and the proof; close the session safely; report" "V-1 incompatible"
}

# --- deploy: runbook 5.1, single files ---------------------------------------------
STACK_RE='^egw-(mosquitto|mongodb|ditto-policies|ditto-things|ditto-gateway|controller)-1$'
do_deploy() {
    local f name exp check install running
    start_attempt "candidate deployment"
    ex "$A" clone-files bash -c 'cd "$1/src/deployment" && git -C "$1" rev-parse HEAD && sha256sum "${@:2}"' _ "$REPO" "${FILES[@]}"
    must clone-files $? "the candidate files could not be read from the clone"

    gx "$A" stack-state "if L=\$(docker ps --format '{{.Names}}'); then printf '%s\n' \"\$L\"; else echo 'STOP: the running containers could not be listed'; exit 1; fi"
    must stack-state $? "the running containers could not be listed"
    running=$(grep -E "$STACK_RE" "$(out_of stack-state)" | tr '\n' ' ')
    if [ -n "$running" ]; then
        CHANGED="the stack was stopped before the deployment"
        gx "$A" stack-stop "cd /opt/egw/deployment && $DC stop -t 60; r=\$?; echo \"stop exit=\$r\"; exit \$r"
        must stack-stop $? "the stack ($running) could not be stopped before the deployment"
    fi
    gx "$A" stack-stopped "if L=\$(docker ps --format '{{.Names}}'); then :; else echo 'STOP: the running containers could not be listed'; exit 1; fi
if printf '%s\n' \"\$L\" | grep -E '$STACK_RE'; then echo 'STOP: a stack container is running'; exit 1; fi; echo 'no stack container running'"
    must stack-stopped $? "the stack is not stopped (or could not be listed): the broker would not read the new configuration at its start"

    gx "$A" files-before "cd /opt/egw/deployment || exit 1; for f in ${FILES[*]}; do sudo stat -c '%u:%g %a %s %y %n' \"\$f\" || exit 1; sudo sha256sum \"\$f\" || exit 1; done"
    must files-before $? "the deployed files could not be read before the deployment"

    gx "$A" staging-dir "rm -rf /tmp/egw-deploy-489bc9e && mkdir -p /tmp/egw-deploy-489bc9e && ls -ld /tmp/egw-deploy-489bc9e"
    must staging-dir $? "the staging folder could not be created"
    # First every copy is checked, then every file installed: a bad copy
    # installs nothing. Each file is written IN PLACE (BusyBox cp would unlink
    # and re-create it as root), so inode, owner and mode stay, and both are
    # compared before and after.
    check="set -u; T=/tmp/egw-deploy-489bc9e"
    install="set -u; T=/tmp/egw-deploy-489bc9e; D=/opt/egw/deployment; P=/opt/egw/evidence/deployment-previous/$STAMP"
    for f in "${FILES[@]}"; do
        name=$(basename "$f")
        exp=$(sha256sum "$REPO/src/deployment/$f" | cut -d' ' -f1)
        gcp "$A" "copy-$name" "$REPO/src/deployment/$f" "egw@127.0.0.1:/tmp/egw-deploy-489bc9e/$name"
        must "copy-$name" $? "$f was not copied to the guest"
        check="$check
got=\$(sha256sum \"\$T/$name\" | cut -d' ' -f1); [ \"\$got\" = $exp ] || { echo \"STOP: the copy of $f is \$got, not $exp\"; exit 1; }; echo \"copy of $f: \$got\""
        install="$install
om=\$(sudo stat -c '%u:%g %a' \"\$D/$f\") || { echo 'STOP: $f could not be read'; exit 1; }
sudo mkdir -p \"\$P/\$(dirname $f)\" && sudo cp -p \"\$D/$f\" \"\$P/$f\" || { echo 'STOP: the previous $f could not be kept'; exit 1; }
sudo sh -c 'cat \"\$1\" > \"\$2\"' _ \"\$T/$name\" \"\$D/$f\" || { echo 'STOP: $f could not be written'; exit 1; }
inst=\$(sudo sha256sum \"\$D/$f\" | cut -d' ' -f1); [ \"\$inst\" = $exp ] || { echo \"STOP: the installed $f is \$inst, not $exp\"; exit 1; }
om2=\$(sudo stat -c '%u:%g %a' \"\$D/$f\"); [ \"\$om2\" = \"\$om\" ] || { echo \"STOP: the owner/mode of $f changed from \$om to \$om2\"; exit 1; }
echo \"installed $f: \$inst, owner/mode \$om2 kept\""
    done
    gx "$A" copies-check "$check"
    must copies-check $? "a copied file is not the clone's: nothing was installed"
    install="$install
echo \"installed_epoch=\$(date +%s) installed_utc=\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
sudo ls -lR \"\$P\"; rm -rf \"\$T\"; exit 0"
    CHANGED="${CHANGED:+$CHANGED; }candidate files may be installed (previous versions in /opt/egw/evidence/deployment-previous/$STAMP)"
    gx "$A" install "$install"
    must install $? "the candidate files were not all installed (see install: a STOP line names which)"

    gx "$A" files-after "cd /opt/egw/deployment || exit 1; for f in ${FILES[*]}; do sudo stat -c '%u:%g %a %s %y %n' \"\$f\" || exit 1; sudo sha256sum \"\$f\" || exit 1; done"
    must files-after $? "the deployed files could not be read after the deployment"
    ex "$A" files-vs-clone bash -c 'set -o pipefail
cd "$1/src/deployment" || exit 2
diff <(sha256sum "${@:4}" | sort -k2) <(grep -E "^[0-9a-f]{64}  " "$3" | sort -k2) || { echo "an installed file differs from the clone"; exit 1; }
diff <(awk "\$1 ~ /^[0-9]+:[0-9]+\$/ {print \$1, \$2, \$NF}" "$2") <(awk "\$1 ~ /^[0-9]+:[0-9]+\$/ {print \$1, \$2, \$NF}" "$3") || { echo "an owner or mode changed"; exit 1; }
echo "the four installed files equal the clone; owner and mode as before"' \
        _ "$REPO" "$(out_of files-before)" "$(out_of files-after)" "${FILES[@]}"
    must files-vs-clone $? "an installed file differs from the clone, or its owner or mode changed"
    end_attempt finished valid pass "the four candidate files are installed and equal to the $COMMIT clone; owner and mode compared and kept; previous versions under /opt/egw/evidence/deployment-previous/$STAMP; .env, passwd, acl, certificates, data/ and volumes untouched" \
        "preflight.sh (starts the stack on this configuration)" "candidate files deployed"
}

# --- poststart: after preflight's 'up -d' ------------------------------------------
do_poststart() {
    local installed=${1:-} conf
    [[ "$installed" =~ ^[0-9]+$ ]] || driver_stop "$EXIT_PREREQUISITE" "usage: session_steps.sh poststart INSTALLED_EPOCH (from the deployment's install step)"
    start_attempt "candidate start check"
    conf=$(sha256sum "$REPO/src/deployment/mosquitto/config/mosquitto.conf" | cut -d' ' -f1)
    gx "$A" start-state "cd /opt/egw/deployment || exit 1; rc=0
for c in egw-mosquitto-1 egw-mongodb-1 egw-ditto-policies-1 egw-ditto-things-1 egw-ditto-gateway-1 egw-controller-1; do
    docker inspect -f 'start {{.Name}} started={{.State.StartedAt}} restarts={{.RestartCount}} oom={{.State.OOMKilled}} status={{.State.Status}}' \"\$c\" || rc=1
done
if L=\$(docker logs egw-mosquitto-1 2>&1) && [ -n \"\$L\" ]; then echo \"reload_lines=\$(printf '%s\n' \"\$L\" | grep -c 'Reloading config')\"; else echo 'reload_lines=unread'; rc=1; fi
echo \"mounted_conf_sha256=\$(docker exec egw-mosquitto-1 sha256sum /mosquitto/config/mosquitto.conf | cut -d' ' -f1)\"
echo \"controller_label=\$(docker inspect -f '{{index .Config.Labels \"org.opencontainers.image.revision\"}}' \$(docker inspect -f '{{.Image}}' egw-controller-1))\"
echo \"controller_grace=\$(docker inspect -f '{{.Config.StopTimeout}}' egw-controller-1)\"
echo \"guest_epoch=\$(date +%s)\"
exit \$rc"
    must start-state $? "the containers' start state could not be read"
    ex "$A" start-judgement "$PY" -c '
import re, sys
from datetime import datetime, timezone
path, installed, conf, commit = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
text = open(path, encoding="utf-8").read()
def epoch(s):
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z", s)
    if not m:
        return None
    base = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    return base + float("0." + (m.group(2) or "0"))
bad = []
broker = re.search(r"^start /egw-mosquitto-1 started=(\S+)", text, re.M)
b = epoch(broker.group(1)) if broker else None
if b is None:
    bad.append("the broker StartedAt was not read")
elif b <= installed:
    bad.append("the broker started at %.3f, not after the installation at %d" % (b, installed))
else:
    print("broker started %.1f s after the installation" % (b - installed))
reload = re.search(r"^reload_lines=(\d+)$", text, re.M)
if not reload or reload.group(1) != "0":
    bad.append("reload_lines is %s, not 0" % (reload.group(1) if reload else "unread"))
mounted = re.search(r"^mounted_conf_sha256=([0-9a-f]{64})$", text, re.M)
if not mounted or mounted.group(1) != conf:
    bad.append("the mounted mosquitto.conf is %s, not %s as in the clone" % (mounted.group(1) if mounted else "unread", conf))
label = re.search(r"^controller_label=(\S+)$", text, re.M)
if not label or label.group(1) != commit:
    bad.append("the controller label is %s, not %s" % (label.group(1) if label else "unread", commit))
starts = [epoch(s) for s in re.findall(r"^start \S+ started=(\S+)", text, re.M)]
if len(starts) != 6 or None in starts:
    bad.append("not six readable start instants")
else:
    print("six starts span %.1f s (earliest to latest)" % (max(starts) - min(starts)))
for line in bad:
    print("NOT AS REQUIRED: " + line)
print("start check: %s" % ("as required" if not bad else "NOT as required"))
sys.exit(1 if bad else 0)' "$(out_of start-state)" "$installed" "$conf" "$COMMIT"
    rc=$?
    [ "$rc" -ne "$EXIT_CAPTURE_LOST" ] || must start-judgement "$rc" ""
    [ "$rc" -eq 0 ] || end_attempt failed valid fail "the candidate did not start as required (see start-judgement)" \
        "STOP before gate_health and the proof; close the session safely; report" "candidate start not as required"
    end_attempt finished valid pass "the broker started after the installation with the candidate's mosquitto.conf and no reload; the controller is the $COMMIT image" \
        "gate_health.sh with the packet's environment" "candidate started as required"
}

case "$CMD" in
    load) do_load ;;
    v1) do_v1 ;;
    deploy) do_deploy ;;
    poststart) do_poststart "${2:-}" ;;
    *) driver_stop "$EXIT_PREREQUISITE" "usage: session_steps.sh load|v1|deploy|poststart INSTALLED_EPOCH" ;;
esac
