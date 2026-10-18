#!/bin/bash
# tools/compare/provision_stack.sh - bring the SAME application stack up on the running guest of
# one comparison scenario, idempotently, and record every step.
#
#   provision_stack.sh <scenario>        scenario: yocto | debian13 (tools/compare/scenarios)
#
# The guest must already be running (compare_env.sh start / tf.sh apply) and answer ssh as egw on
# 127.0.0.1:2222 with the scenario's own known_hosts file. The sequence is the runbook's
# (docs/setup/qemu_integrated_gateway.md 5.1-5.6), executed over ssh with the deployment's own
# POSIX scripts, so the two guests receive the same tree, the same pinned images, the same
# controller archive and the same secrets. Steps: guest-facts, deployment-tree, env-file,
# images-pull, controller-load, tls, auth, secrets, validate, up, healthy-wait. A re-run skips
# what is already in place (marker files under /opt/egw/evidence/provision on the guest, the
# engine's own image state, the generated files) and repeats the idempotent steps.
#
# Inputs on the host (overridable):
#   EGW_COMPARE_SECRETS_ENV      the .env with the four passwords (default $HOME/egw-tcg/.env);
#                                copied to the guest, never read into any log or record
#   EGW_IMAGES_DIR               egw-controller-0.1.0-arm64.tar and its .identity.txt
#                                (default $HOME/egw-images)
#   EGW_COMPARE_HEALTH_LIMIT_S   seconds allowed for six healthy + /ready, from up -d (default 1800)
#
# Records: $S_DIR/logs/provision-<stamp>.log (transcript) and $S_DIR/state/provision.json
# (steps with rc and host uptime seconds); the broker CA is fetched to $S_DIR/state/ca.crt.
# Exit: 0 stack healthy and ready; 1 stack started but not healthy/ready within the limit;
#       2 a prerequisite is missing on the host or the guest facts are wrong; 3 a step failed.
# The last line printed is always: PROVISION <scenario>: result=<...> log=<path>
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"

usage() { sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -eq 1 ] || usage
scenario=$1
scenario_load "$scenario"
mkdir -p "$S_DIR/logs" "$S_DIR/state" "$S_DIR/results"

SECRETS=${EGW_COMPARE_SECRETS_ENV:-$HOME/egw-tcg/.env}
IMAGES_DIR=${EGW_IMAGES_DIR:-$HOME/egw-images}
CTL_TAR=$IMAGES_DIR/egw-controller-0.1.0-arm64.tar
CTL_RECORD=$IMAGES_DIR/egw-controller-0.1.0-arm64.identity.txt
DEPLOY_SRC=$COMPARE_REPO/src/deployment
HEALTH_LIMIT_S=${EGW_COMPARE_HEALTH_LIMIT_S:-1800}
HEALTH_STEP_S=${EGW_COMPARE_HEALTH_STEP_S:-15}
GUEST_DEPLOY=/opt/egw/deployment
GUEST_MARKERS=/opt/egw/evidence/provision
SERVICES="egw-mosquitto-1 egw-mongodb-1 egw-ditto-policies-1 egw-ditto-things-1 egw-ditto-gateway-1 egw-controller-1"
DC='docker compose --env-file .env --env-file images.lock.env'

STAMP=$(stamp)
LOG=$S_DIR/logs/provision-$STAMP.log
RECORD=$S_DIR/state/provision.json
LAST_OUT=$(mktemp "${TMPDIR:-/tmp}/provision-last-out.XXXXXX") || exit 2
STEPS_JSON=
T_UP=
SECONDS_TO_HEALTHY=null
SECONDS_TO_READY=null
REPO_HEAD=$(git -C "$COMPARE_REPO" rev-parse HEAD 2> /dev/null || echo unknown)

log() { log_line "$LOG" "$1"; }
say() { echo "$1"; log "$1"; }
jstr() { local s=$1; s=${s//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
elapsed() { awk -v a="$1" -v b="$2" 'BEGIN { printf "%.2f", b - a }'; }
# fact TEXT KEY: the value of the first 'FACT KEY=value' line of TEXT.
fact() { printf '%s\n' "$1" | sed -n "s/^FACT $2=//p" | head -n 1; }

# finish CODE RESULT [MESSAGE]: write provision.json, print the PROVISION line last, exit CODE.
finish() {
    local code=$1 result=$2 msg=${3:-}
    [ -z "$msg" ] || say "$msg"
    {
        printf '{\n  "scenario": %s,\n  "utc": %s,\n  "repo_head": %s,\n' \
            "$(jstr "$SCENARIO")" "$(jstr "$(utc_now)")" "$(jstr "$REPO_HEAD")"
        printf '  "result": %s,\n  "exit": %s,\n  "log": %s,\n' "$(jstr "$result")" "$code" "$(jstr "$LOG")"
        printf '  "health_limit_s": %s,\n  "seconds_to_healthy": %s,\n  "seconds_to_ready": %s,\n' \
            "$HEALTH_LIMIT_S" "$SECONDS_TO_HEALTHY" "$SECONDS_TO_READY"
        printf '  "steps": [%s\n  ]\n}\n' "$STEPS_JSON"
    } > "$RECORD.tmp" && mv "$RECORD.tmp" "$RECORD"
    rm -f "$LAST_OUT"
    echo "PROVISION $SCENARIO: result=$result log=$LOG"
    exit "$code"
}
stop() { finish 2 prerequisites "STOP: $1"; }

# gx GUEST-COMMAND: run one POSIX command on the guest; transcript to the log, the console and
# $LAST_OUT (for the checks that follow). Returns ssh's status.
gx() {
    log "guest\$ $1"
    gssh "$1" 2>&1 | tee -a "$LOG" | tee "$LAST_OUT"
    return "${PIPESTATUS[0]}"
}
# gq GUEST-COMMAND: the same, transcript to the log only.
gq() {
    log "guest\$ $1"
    gssh "$1" >> "$LOG" 2>&1
}
last_has() { grep -q "$1" "$LAST_OUT"; }
marker_read() { gssh "cat $GUEST_MARKERS/$1.done 2> /dev/null"; }
marker_set() { gq "printf '%s\\n' '$(utc_now) $2' > $GUEST_MARKERS/$1.done"; }

# run_step NAME FUNCTION: time the step on the host monotonic clock and append it to the record.
# The function returns 0 (done), 10 (skipped: already in place) or anything else (failed). A failed
# step ends the run with exit 3, or with the code the step put in STEP_FAIL_CODE (2 = prerequisite).
STEP_NOTE=
STEP_FAIL_CODE=3
STEP_FAIL_RESULT=step-failed
run_step() {
    local name=$1 fn=$2 t0 t1 rc status
    STEP_NOTE=
    STEP_FAIL_CODE=3
    STEP_FAIL_RESULT=step-failed
    t0=$(uptime_s)
    say "== $name (uptime ${t0}s)"
    "$fn"
    rc=$?
    t1=$(uptime_s)
    case $rc in
        0) status=done ;;
        10) status=skipped; rc=0 ;;
        *) status=failed ;;
    esac
    [ -z "$STEP_NOTE" ] || log "   $name: $STEP_NOTE"
    STEPS_JSON="$STEPS_JSON${STEPS_JSON:+,}"$'\n'"    {\"name\": $(jstr "$name"), \"status\": $(jstr "$status"), \"rc\": $rc, \"uptime_start_s\": $t0, \"uptime_end_s\": $t1, \"seconds\": $(elapsed "$t0" "$t1"), \"note\": $(jstr "$STEP_NOTE")}"
    say "   $name: $status (rc=$rc, $(elapsed "$t0" "$t1") s)"
    [ "$status" != failed ] || finish "$STEP_FAIL_CODE" "$STEP_FAIL_RESULT" "STOP: step '$name' failed (rc=$rc); see $LOG"
}

# --- host prerequisites (nothing is sent to the guest before these hold) ------------------------
: > "$LOG"
log "provision_stack.sh scenario=$SCENARIO repo=$COMPARE_REPO head=$REPO_HEAD"
[ -r "$SECRETS" ] || stop "secrets file missing or unreadable: $SECRETS"
# Placeholders are looked for in assignments only (the header comment of .env.example names
# CHANGE_ME too). Only names are checked here; no value is ever read into this process.
if grep -Eq '^[A-Za-z_][A-Za-z0-9_]*=.*CHANGE_ME' "$SECRETS"; then
    stop "secrets file still carries a CHANGE_ME placeholder: $SECRETS"
fi
for name in MOSQUITTO_SIMULATOR_PASSWORD MOSQUITTO_CONTROLLER_PASSWORD EGW_MQTT_PASSWORD DITTO_DEVOPS_PASSWORD; do
    grep -Eq "^$name=.+" "$SECRETS" || stop "secrets file has no $name assignment: $SECRETS"
done
[ -s "$CTL_TAR" ] || stop "controller archive missing: $CTL_TAR"
[ -s "$CTL_RECORD" ] || stop "controller identity record missing: $CTL_RECORD"
record_sha=$(sed -n 's/^archive_sha256=//p' "$CTL_RECORD" | head -n 1)
[ -n "$record_sha" ] || stop "identity record has no archive_sha256 line: $CTL_RECORD"
tar_sha=$(sha256_of "$CTL_TAR")
[ "$tar_sha" = "$record_sha" ] || stop "controller archive sha256 $tar_sha differs from the record's $record_sha"
grep -q '^source_tree_state=clean$' "$CTL_RECORD" || stop "identity record is not from a clean build context (source_tree_state): $CTL_RECORD"
[ -d "$DEPLOY_SRC" ] || stop "deployment tree missing: $DEPLOY_SRC"
for f in compose.yaml images.lock.env scripts/validate-config.sh scripts/verify-controller-image.sh \
    scripts/prepare-broker-secrets.sh scripts/generate-dev-auth.sh scripts/generate-dev-tls.sh; do
    [ -f "$DEPLOY_SRC/$f" ] || stop "deployment tree lacks $f: $DEPLOY_SRC"
done
for tool in ssh scp tar sha256sum awk find sort xargs; do
    command -v "$tool" > /dev/null 2>&1 || stop "host tool missing: $tool"
done
log "controller archive $CTL_TAR sha256=$tar_sha (matches the record)"

# --- a. guest-facts ------------------------------------------------------------------------------
# FACT lines first (parsed on the host), then the raw transcript. Nothing here changes the guest.
FACTS_CMD='printf "FACT uid=%s\n" "$(id -u egw 2>/dev/null)"
printf "FACT docker=%s\n" "$(command -v docker 2>/dev/null)"
printf "FACT compose=%s\n" "$(docker compose version --short 2>/dev/null)"
printf "FACT label=%s\n" "$(findmnt -no LABEL /var/lib/docker 2>/dev/null)"
id egw; command -v docker; docker --version; docker compose version
findmnt -no SOURCE,FSTYPE,SIZE /var/lib/docker
ls -ld /opt/egw /opt/egw/deployment /opt/egw/deployment/data/events
true'
step_guest_facts() {
    local out rc uid docker compose label bad=
    STEP_FAIL_CODE=2
    STEP_FAIL_RESULT=prerequisites
    log "guest\$ <facts>"
    out=$(gssh "$FACTS_CMD" 2>&1)
    rc=$?
    printf '%s\n' "$out" >> "$LOG"
    printf '%s\n' "$out" | grep -v '^FACT ' || true
    [ $rc -eq 0 ] || { say "STOP: ssh to the guest failed (exit $rc)"; return 1; }
    uid=$(fact "$out" uid); docker=$(fact "$out" docker); compose=$(fact "$out" compose); label=$(fact "$out" label)
    [ "$uid" = 1000 ] || bad="$bad; user egw is uid '${uid:-absent}', not 1000"
    [ -n "$docker" ] || bad="$bad; docker is not on the guest PATH"
    [ -n "$compose" ] || bad="$bad; docker compose does not answer"
    [ "$label" = "$COMPARE_DATA_DISK_LABEL" ] || bad="$bad; /var/lib/docker is not mounted from a device labelled $COMPARE_DATA_DISK_LABEL (label '${label:-none}')"
    if [ -n "$bad" ]; then
        say "STOP: guest facts${bad}"
        return 1
    fi
    STEP_NOTE="uid=$uid docker=$docker compose=$compose label=$label"
}

# --- b. deployment-tree --------------------------------------------------------------------------
# Streamed with tar instead of scp -r: on a re-run passwd, server.key and acl are owned by the
# broker's uid 1883, and the generated secrets must never be overwritten by the host copy.
TREE_EXCLUDES=(--exclude=.env --exclude='mosquitto/config/passwd' --exclude='mosquitto/config/certs/*' --exclude=./data)
tree_sha() {
    (cd "$DEPLOY_SRC" && find . -type f ! -name .env ! -path './mosquitto/config/passwd' \
        ! -path './mosquitto/config/certs/*' ! -path './data/*' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
}
step_deployment_tree() {
    local want have rcs
    gq "mkdir -p $GUEST_MARKERS /opt/egw/images $GUEST_DEPLOY" || return 1
    want=$(tree_sha) || return 1
    have=$(marker_read 02-tree | awk '{ print $NF }')
    log "deployment tree content sha256 host=$want guest-marker=${have:-none} head=$REPO_HEAD"
    if [ -n "$have" ] && [ "$have" = "$want" ]; then
        STEP_NOTE="skipped: guest tree marker carries the same content sha256 ($want)"
        return 10
    fi
    log "host\$ tar -C $DEPLOY_SRC ${TREE_EXCLUDES[*]} -cf - . | ssh ... 'tar -C $GUEST_DEPLOY -xf -'"
    tar -C "$DEPLOY_SRC" "${TREE_EXCLUDES[@]}" -cf - . | gssh "tar -C $GUEST_DEPLOY -xf -" >> "$LOG" 2>&1
    rcs=("${PIPESTATUS[@]}")
    [ "${rcs[0]}" -eq 0 ] && [ "${rcs[1]}" -eq 0 ] || { say "STOP: tree copy failed (tar=${rcs[0]} ssh=${rcs[1]})"; return 1; }
    marker_set 02-tree "$want" || return 1
    STEP_NOTE="copied (content sha256 $want, head $REPO_HEAD)"
}

# --- c. env-file ---------------------------------------------------------------------------------
step_env_file() {
    log "host\$ scp $SECRETS egw@127.0.0.1:$GUEST_DEPLOY/.env"
    gscp "$SECRETS" "egw@127.0.0.1:$GUEST_DEPLOY/.env" >> "$LOG" 2>&1 || return 1
    gq "chmod 600 $GUEST_DEPLOY/.env" || return 1
    marker_set 03-env copied || return 1
}

# --- d. images-pull ------------------------------------------------------------------------------
# The verification group is the runbook's (5.2a), verbatim; it runs first on its own, so that a
# guest whose five images already verify is not pulled again.
IMAGES_VERIFY='{ n=0; bad=0; for ref in $(sed -n "s/^IMAGE_[A-Z_]*=//p" images.lock.env); do
    n=$((n+1)); got=$(docker image inspect --format "{{.RepoDigests}} {{.Architecture}}/{{.Os}}" "$ref" 2>/dev/null)
    case "$got" in *"@${ref##*@}"*" arm64/linux") echo "OK   $ref";; *) echo "FAIL $ref got=$got"; bad=$((bad+1));; esac
  done; if [ "$bad" = 0 ] && [ "$n" = 5 ]; then echo "IMAGE IDENTITY: all $n pulled images carry their pinned digest"; else echo "STOP: image identity NOT verified ($bad FAIL, $n checked, 5 expected)"; fi; }'
IMAGES_OK='^IMAGE IDENTITY: all 5 pulled images carry their pinned digest$'
step_images_pull() {
    gx "cd $GUEST_DEPLOY && $IMAGES_VERIFY" > /dev/null
    if last_has "$IMAGES_OK"; then
        STEP_NOTE="skipped: the five pinned images already verify on the guest"
        return 10
    fi
    gx "cd $GUEST_DEPLOY && $DC pull mosquitto mongodb ditto-policies ditto-things ditto-gateway; echo \"pull exit=\$?\"; mkdir -p /opt/egw/evidence; $IMAGES_VERIFY | tee /opt/egw/evidence/images-pull-identity.txt"
    last_has '^pull exit=0$' || { say "STOP: docker compose pull did not exit 0"; return 1; }
    last_has "$IMAGES_OK" || { say "STOP: pulled images do not carry their pinned digests (images-pull-identity.txt)"; return 1; }
    marker_set 04-images verified || return 1
    STEP_NOTE="pulled and verified (RepoDigests, arm64/linux)"
}

# --- e. controller-load --------------------------------------------------------------------------
step_controller_load() {
    local rc
    if gq "docker image inspect egw-controller:0.1.0 >/dev/null 2>&1"; then
        log "controller image already present on the guest engine: docker load skipped"
        STEP_NOTE="image present; "
    else
        log "host\$ ssh ... docker load < $CTL_TAR"
        gssh "docker load" < "$CTL_TAR" >> "$LOG" 2>&1 || { say "STOP: docker load failed"; return 1; }
        STEP_NOTE="loaded; "
    fi
    gq "mkdir -p /opt/egw/images" || return 1
    gscp "$CTL_RECORD" "$DEPLOY_SRC/scripts/verify-controller-image.sh" "egw@127.0.0.1:/opt/egw/images/" >> "$LOG" 2>&1 || return 1
    gx "cd /opt/egw/images && sh verify-controller-image.sh egw-controller-0.1.0-arm64.identity.txt"
    rc=$?
    [ $rc -eq 0 ] && last_has '^CONTROLLER IMAGE IDENTITY: verified' ||
        { say "STOP: controller image identity NOT verified (exit $rc)"; return 1; }
    marker_set 05-controller verified || return 1
    STEP_NOTE="${STEP_NOTE}identity verified against the record"
}

# --- f. tls --------------------------------------------------------------------------------------
step_tls() {
    gx "cd $GUEST_DEPLOY && { [ -s mosquitto/config/certs/ca.crt ] && echo 'tls: ca.crt present, generation skipped'; } || sh scripts/generate-dev-tls.sh" || return 1
    gscp "egw@127.0.0.1:$GUEST_DEPLOY/mosquitto/config/certs/ca.crt" "$S_DIR/state/ca.crt.tmp" >> "$LOG" 2>&1 || { say "STOP: ca.crt could not be fetched"; return 1; }
    [ -s "$S_DIR/state/ca.crt.tmp" ] || { rm -f "$S_DIR/state/ca.crt.tmp"; say "STOP: fetched ca.crt is empty"; return 1; }
    mv "$S_DIR/state/ca.crt.tmp" "$S_DIR/state/ca.crt" || return 1
    marker_set 06-tls "ca.crt sha256 $(sha256_of "$S_DIR/state/ca.crt")" || return 1
    STEP_NOTE="ca.crt at $S_DIR/state/ca.crt"
}

# --- g. auth -------------------------------------------------------------------------------------
# The passwords are read from .env ON THE GUEST (set -a there), never by this host process.
step_auth() {
    gx "cd $GUEST_DEPLOY && { [ -s mosquitto/config/passwd ] && echo 'auth: passwd present, generation skipped'; } || { set -a; . ./.env; set +a; sh scripts/generate-dev-auth.sh; }" || return 1
    marker_set 07-auth "passwd present" || return 1
}

# --- h. secrets ----------------------------------------------------------------------------------
step_secrets() {
    gx "cd $GUEST_DEPLOY && sh scripts/prepare-broker-secrets.sh --acl" || return 1
    marker_set 08-secrets "applied and checked" || return 1
}

# --- i. validate ---------------------------------------------------------------------------------
step_validate() {
    gx "cd $GUEST_DEPLOY && o=\$(stat -c '%u:%g' data/events) && echo \"data/events owner \$o\" && { [ \"\$o\" = 1000:1000 ] || { echo \"STOP: data/events is owned by \$o, not 1000:1000\"; exit 1; }; } && sh scripts/verify-controller-image.sh /opt/egw/images/egw-controller-0.1.0-arm64.identity.txt && sh scripts/validate-config.sh" || return 1
    marker_set 09-validate "validate-config.sh exit 0" || return 1
}

# --- j. up ---------------------------------------------------------------------------------------
step_up() {
    T_UP=$(uptime_s)
    gx "cd $GUEST_DEPLOY && $DC up -d; echo \"up exit=\$?\""
    last_has '^up exit=0$' || { say "STOP: docker compose up -d did not exit 0"; return 1; }
    marker_set 10-up "up -d exit 0" || return 1
}

# --- k. healthy-wait -----------------------------------------------------------------------------
# Polled from the host every HEALTH_STEP_S s; durations are host monotonic, counted from up -d.
INSPECT_FMT='{{.Name}} {{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}'
HEALTH_RESULT=
over_limit() { awk -v a="$1" -v b="$2" -v l="$HEALTH_LIMIT_S" 'BEGIN { exit !(b - a >= l) }'; }
step_healthy_wait() {
    local t0 now out healthy code
    t0=$T_UP
    while :; do
        out=$(gssh "docker inspect --format '$INSPECT_FMT' $SERVICES" 2>&1)
        now=$(uptime_s)
        healthy=$(printf '%s\n' "$out" | grep -c ' running/healthy$')
        log "health sample (+$(elapsed "$t0" "$now") s): $(printf '%s' "$out" | tr '\n' ' ')"
        echo "   healthy $healthy/6 at +$(elapsed "$t0" "$now") s"
        if [ "$healthy" -eq 6 ]; then
            SECONDS_TO_HEALTHY=$(elapsed "$t0" "$now")
            break
        fi
        if over_limit "$t0" "$now"; then
            HEALTH_RESULT="not healthy within $HEALTH_LIMIT_S s ($healthy/6 running/healthy)"
            return 1
        fi
        sleep "$HEALTH_STEP_S"
    done
    while :; do
        code=$(gssh "curl -s -o /dev/null -w '%{http_code}' --max-time 30 http://127.0.0.1:8000/ready" 2> /dev/null)
        now=$(uptime_s)
        log "ready sample (+$(elapsed "$t0" "$now") s): /ready -> '$code'"
        echo "   /ready -> '$code' at +$(elapsed "$t0" "$now") s"
        if [ "$code" = 200 ]; then
            SECONDS_TO_READY=$(elapsed "$t0" "$now")
            break
        fi
        if over_limit "$t0" "$now"; then
            HEALTH_RESULT="six healthy after $SECONDS_TO_HEALTHY s but /ready answered '$code', not 200, within $HEALTH_LIMIT_S s"
            return 1
        fi
        sleep "$HEALTH_STEP_S"
    done
    marker_set 11-healthy "healthy ${SECONDS_TO_HEALTHY}s ready ${SECONDS_TO_READY}s" || return 1
    STEP_NOTE="six running/healthy after $SECONDS_TO_HEALTHY s, /ready 200 after $SECONDS_TO_READY s (from up -d)"
}

run_step guest-facts step_guest_facts
run_step deployment-tree step_deployment_tree
run_step env-file step_env_file
run_step images-pull step_images_pull
run_step controller-load step_controller_load
run_step tls step_tls
run_step auth step_auth
run_step secrets step_secrets
run_step validate step_validate
run_step up step_up
# The health wait is not a failed step when the limit passes: the stack is up but not ready (exit 1).
t0=$(uptime_s)
say "== healthy-wait (uptime ${t0}s, limit $HEALTH_LIMIT_S s, step $HEALTH_STEP_S s)"
STEP_NOTE=
step_healthy_wait
rc=$?
t1=$(uptime_s)
status=done; [ $rc -eq 0 ] || status=unhealthy
STEPS_JSON="$STEPS_JSON${STEPS_JSON:+,}"$'\n'"    {\"name\": \"healthy-wait\", \"status\": $(jstr "$status"), \"rc\": $rc, \"uptime_start_s\": $t0, \"uptime_end_s\": $t1, \"seconds\": $(elapsed "$t0" "$t1"), \"note\": $(jstr "${STEP_NOTE:-$HEALTH_RESULT}")}"
say "   healthy-wait: $status (rc=$rc, $(elapsed "$t0" "$t1") s)"
[ $rc -eq 0 ] || finish 1 unhealthy "STOP: $HEALTH_RESULT"
finish 0 ok
