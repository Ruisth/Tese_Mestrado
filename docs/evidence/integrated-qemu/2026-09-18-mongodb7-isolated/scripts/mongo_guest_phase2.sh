# Isolated MongoDB 7 test, phase 2 - after a guest power cycle. Fed to
# 'sh -s' over SSH as operator 'egw' (BusyBox ash).
C=egw-mongo-test
V=egw-mongo-test-data
T=/tmp/egw-mongo-test2.$$
FAILS=0
run()   { echo; echo "\$ $*"; "$@" 2>&1 </dev/null; rc=$?; echo "[exit=$rc]"; return $rc; }
check() { name=$1; shift; if "$@" >/dev/null 2>&1 </dev/null; then echo "CHECK PASS  $name"; else echo "CHECK FAIL  $name"; FAILS=$((FAILS + 1)); fi; }
up()    { cut -d. -f1 /proc/uptime; }
mq()    { docker exec "$C" mongosh --quiet --eval "$1" 2>&1 </dev/null; }
wait_ping() {
    t0=$(up)
    while :; do
        if mq 'db.runCommand({ping:1}).ok' | grep -q '^1$'; then echo "ping ok after $(( $(up) - t0 )) s"; return 0; fi
        st=$(docker inspect -f '{{.State.Status}}' "$C" 2>/dev/null </dev/null)
        [ "$st" = running ] || { echo "container state is '$st' after $(( $(up) - t0 )) s - giving up"; return 1; }
        [ $(( $(up) - t0 )) -lt "$1" ] || { echo "no ping within $1 s"; return 1; }
        sleep 5
    done
}

echo "### 9. state after the guest power cycle"
run date -u
run sudo -n journalctl --list-boots --no-pager
run systemctl is-system-running
run findmnt -no SOURCE,FSTYPE /var/lib/docker
run docker ps -a
run docker images --digests
run docker volume ls
docker inspect -f 'status={{.State.Status}} exit={{.State.ExitCode}}' "$C" > "$T.state" 2>&1 </dev/null
check "the stopped container is still defined and was NOT started by the boot" grep -q '^status=exited ' "$T.state"
check "the pulled image is still present" sh -c "docker images --digests | grep -q 35a5926f71f8"

echo "### 10. start on the same volume and read"
run docker start "$C"
wait_ping 600; R=$?
check "mongod answered ping after the guest power cycle" test "$R" = 0
mq 'const d=db.getSiblingDB("egw_isolated_test"); print("count="+d.probe.countDocuments({})); print(JSON.stringify(d.probe.find().sort({_id:1}).toArray())); d.probe.insertOne({_id:"doc-3", phase:"after-guest-power-cycle", written:new Date()}); print("count_after_insert="+d.probe.countDocuments({}))' > "$T.read"
echo; echo '$ mongosh: read after the guest power cycle, then insert document 3'; cat "$T.read"
check "both documents survived the guest power cycle" grep -qx 'count=2' "$T.read"
check "document 1 is intact" grep -q '"_id":"doc-1"' "$T.read"
check "document 2 is intact" grep -q '"_id":"doc-2"' "$T.read"
check "document 3 was written" grep -qx 'count_after_insert=3' "$T.read"

echo "### 11. end state: container removed, image and test volume kept"
run docker stop -t 60 "$C"
docker inspect -f 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}' "$C" > "$T.stop" 2>&1 </dev/null; cat "$T.stop"
check "mongod stopped cleanly (exit 0)" grep -q '^status=exited exit=0 oom=false' "$T.stop"
echo; echo "----- BEGIN LOGS instance 3 -----"; docker logs "$C" 2>&1 </dev/null; echo "----- END LOGS instance 3 -----"
run docker rm "$C"
run docker ps -a
run docker volume ls
run docker images --digests
run df -h /var/lib/docker
run systemctl --failed --no-legend
run sync
rm -f "$T".*
echo
echo "PHASE 2 RESULT: failed_checks=$FAILS"
