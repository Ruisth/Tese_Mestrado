# Isolated MongoDB 7 test, phase 1 - fed to 'sh -s' over SSH as operator 'egw'
# on the Yocto guest (BusyBox ash). Mirrors the mongodb service of
# src/deployment/compose.yaml (user, command, memory limit, TZ, volume on
# /data/db, NO published port) with a separate test volume and test database.
IMG='docker.io/library/mongo:7.0.39@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d'
PIN=35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d
C=egw-mongo-test
V=egw-mongo-test-data
T=/tmp/egw-mongo-test.$$
FAILS=0
run()   { echo; echo "\$ $*"; "$@" 2>&1 </dev/null; rc=$?; echo "[exit=$rc]"; return $rc; }
check() { name=$1; shift; if "$@" >/dev/null 2>&1 </dev/null; then echo "CHECK PASS  $name"; else echo "CHECK FAIL  $name"; FAILS=$((FAILS + 1)); fi; }
up()    { cut -d. -f1 /proc/uptime; }
mq()    { docker exec "$C" mongosh --quiet --eval "$1" 2>&1 </dev/null; }
wait_ping() { # wait_ping <limit-seconds>: until mongosh ping answers 1
    t0=$(up)
    while :; do
        if mq 'db.runCommand({ping:1}).ok' | grep -q '^1$'; then
            echo "ping ok after $(( $(up) - t0 )) s"; return 0
        fi
        st=$(docker inspect -f '{{.State.Status}}' "$C" 2>/dev/null </dev/null)
        [ "$st" = running ] || { echo "container state is '$st' after $(( $(up) - t0 )) s - giving up"; return 1; }
        [ $(( $(up) - t0 )) -lt "$1" ] || { echo "no ping within $1 s"; return 1; }
        sleep 5
    done
}
start_container() {
    run docker run -d --name "$C" --user mongodb --memory 512m -e TZ=UTC -v "$V":/data/db "$IMG" mongod --storageEngine wiredTiger --noscripting
}

echo "### 0. state before"
run date -u
run docker ps -a
run docker images --digests
run docker volume ls
run df -h /var/lib/docker
check "no container of an earlier test exists" sh -c "! docker inspect $C"
check "no volume of an earlier test exists" sh -c "! docker volume inspect $V"

echo "### 1. pull by the pinned reference of images.lock.env"
t0=$(up); run docker pull "$IMG"; PULL_RC=$?; echo "pull took $(( $(up) - t0 )) s"
check "pull succeeded" test "$PULL_RC" = 0
docker image inspect --format 'id={{.Id}} arch={{.Architecture}} variant={{.Variant}} os={{.Os}} size={{.Size}} repodigests={{.RepoDigests}} created={{.Created}}' "$IMG" > "$T.image" 2>&1 </dev/null
echo; echo '$ docker image inspect (identity)'; cat "$T.image"
check "image architecture is arm64" grep -q ' arch=arm64 ' "$T.image"
check "image carries the pinned digest" grep -q "$PIN" "$T.image"

echo "### 2. the binary runs on this CPU model (the G1 cortex-a57 profile could not)"
docker run --rm --user mongodb "$IMG" mongod --version > "$T.version" 2>&1 </dev/null; echo; echo '$ docker run --rm ... mongod --version'; cat "$T.version";
check "mongod --version reports v7.0.39" grep -q 'db version v7.0.39' "$T.version"
check "no illegal instruction when the binary starts" sh -c "! grep -qiE 'illegal instruction|SIGILL' $T.version"

echo "### 3. start as the compose service does (no -p: nothing is published)"
run docker volume create "$V"
start_container
wait_ping 600; PING_RC=$?
check "mongod answered ping" test "$PING_RC" = 0
docker inspect -f 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} restarts={{.RestartCount}} started={{.State.StartedAt}} user={{.Config.User}} memory={{.HostConfig.Memory}} ports={{json .NetworkSettings.Ports}} portbindings={{json .HostConfig.PortBindings}} mounts={{json .Mounts}}' "$C" > "$T.inspect" 2>&1 </dev/null
echo; echo '$ docker inspect (state, limits, ports, mounts)'; cat "$T.inspect"
check "container is running" grep -q '^status=running ' "$T.inspect"
check "container was not OOM-killed" grep -q ' oom=false ' "$T.inspect"
check "memory limit is 512 MiB" grep -q ' memory=536870912 ' "$T.inspect"
check "no host port binding exists" grep -q ' portbindings={} ' "$T.inspect"
check "data directory is the test volume" grep -q "\"Name\":\"$V\"" "$T.inspect"
run docker port "$C"
netstat -ltn > "$T.netstat" 2>&1 </dev/null; echo; echo '$ netstat -ltn (guest host namespace)'; cat "$T.netstat"
check "27017 is not reachable from the guest host namespace" sh -c "! grep -qE ':27017 ' $T.netstat"

echo "### 4. connection, write and read (test database egw_isolated_test only)"
echo; echo '$ mongosh: server identity'; mq 'const b=db.serverBuildInfo(); const h=db.hostInfo(); const s=db.serverStatus(); print(JSON.stringify({version:b.version, gitVersion:b.gitVersion, bits:b.bits, storageEngine:s.storageEngine.name, cpuArch:h.system.cpuArch, numCores:h.system.numCores, memSizeMB:h.system.memSizeMB, memLimitMB:h.system.memLimitMB, os:h.os.name+" "+h.os.version, wiredTigerCacheMaxBytes:s.wiredTiger.cache["maximum bytes configured"]}))'
echo; echo '$ mongosh: insert document 1'; mq 'const d=db.getSiblingDB("egw_isolated_test"); const r=d.probe.insertOne({_id:"doc-1", phase:"first-start", note:"isolated MongoDB 7 test on the Yocto guest", written:new Date()}); print(JSON.stringify(r))'
mq 'const d=db.getSiblingDB("egw_isolated_test"); print("count="+d.probe.countDocuments({})); print(JSON.stringify(d.probe.find().sort({_id:1}).toArray()))' > "$T.read1"
echo; echo '$ mongosh: read back'; cat "$T.read1"
check "exactly one document is stored" grep -qx 'count=1' "$T.read1"
check "document 1 can be read back" grep -q '"_id":"doc-1"' "$T.read1"

echo "### 5. container restart"
run docker restart -t 60 "$C"
wait_ping 600; R1=$?
check "mongod answered ping after docker restart" test "$R1" = 0
mq 'const d=db.getSiblingDB("egw_isolated_test"); print("count="+d.probe.countDocuments({})); d.probe.insertOne({_id:"doc-2", phase:"after-container-restart", written:new Date()}); print("count_after_insert="+d.probe.countDocuments({}))' > "$T.read2"
echo; echo '$ mongosh: read after restart, then insert document 2'; cat "$T.read2"
check "document 1 survived the container restart" grep -qx 'count=1' "$T.read2"
check "document 2 was written" grep -qx 'count_after_insert=2' "$T.read2"

echo "### 6. container removed and recreated on the same volume"
run docker stop -t 60 "$C"
docker inspect -f 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}' "$C" > "$T.stop1" 2>&1 </dev/null; echo; echo '$ docker inspect after stop'; cat "$T.stop1"
check "mongod stopped cleanly (exit 0)" grep -q '^status=exited exit=0 oom=false' "$T.stop1"
echo; echo "----- BEGIN LOGS instance 1 -----"; docker logs "$C" 2>&1 </dev/null; echo "----- END LOGS instance 1 -----"
run docker rm "$C"
start_container
wait_ping 600; R2=$?
check "mongod answered ping in the recreated container" test "$R2" = 0
mq 'const d=db.getSiblingDB("egw_isolated_test"); print("count="+d.probe.countDocuments({})); print(JSON.stringify(d.probe.find().sort({_id:1}).toArray()))' > "$T.read3"
echo; echo '$ mongosh: read in the recreated container'; cat "$T.read3"
check "two documents are stored after the recreation" grep -qx 'count=2' "$T.read3"
check "document 1 survived the recreation" grep -q '"_id":"doc-1"' "$T.read3"
check "document 2 survived the recreation" grep -q '"_id":"doc-2"' "$T.read3"

echo "### 7. resource snapshot (informational only: emulated CPU, no performance meaning)"
run docker stats --no-stream --format 'name={{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}} mem%={{.MemPerc}} pids={{.PIDs}}' "$C"
run free -m
run df -h /var/lib/docker
run docker system df -v

echo "### 8. stop before the guest power cycle (the container and the volume stay)"
run docker stop -t 60 "$C"
docker inspect -f 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}' "$C" > "$T.stop2" 2>&1 </dev/null; echo; echo '$ docker inspect after stop'; cat "$T.stop2"
check "mongod stopped cleanly before power-off (exit 0)" grep -q '^status=exited exit=0 oom=false' "$T.stop2"
docker logs "$C" > "$T.logs2" 2>&1 </dev/null
echo; echo "----- BEGIN LOGS instance 2 -----"; cat "$T.logs2"; echo "----- END LOGS instance 2 -----"
check "log has 'Waiting for connections'" grep -q 'Waiting for connections' "$T.logs2"
check "log has no illegal instruction, fatal assertion or WiredTiger error" sh -c "! grep -qiE 'illegal instruction|SIGILL|Fatal assertion|\"s\":\"F\"|WiredTiger error' $T.logs2"
run sync
rm -f "$T".*
echo
echo "PHASE 1 RESULT: failed_checks=$FAILS"
