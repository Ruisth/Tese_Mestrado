# Pull the five external images of the stack by their pinned digests INSIDE the
# guest and record their identities. Fed to 'sh -s' over SSH as operator 'egw'
# (BusyBox ash). The references are the IMAGE_* lines of
# src/deployment/images.lock.env on dev (0e536cd); nothing is started.
FAILS=0
check() { name=$1; shift; if "$@" >/dev/null 2>&1 </dev/null; then echo "CHECK PASS  $name"; else echo "CHECK FAIL  $name"; FAILS=$((FAILS + 1)); fi; }
up()    { cut -d. -f1 /proc/uptime; }

echo "### state before"
date -u
docker images --digests </dev/null
df -h /var/lib/docker </dev/null

while read -r NAME REF; do
    [ -n "$NAME" ] || continue
    PIN=${REF##*@sha256:}
    echo
    echo "### $NAME = $REF"
    t0=$(up)
    docker pull "$REF" </dev/null 2>&1 | tail -n 4
    RC=$?
    echo "pull took $(( $(up) - t0 )) s"
    docker image inspect --format 'id={{.Id}} arch={{.Architecture}} variant={{.Variant}} os={{.Os}} size={{.Size}} repodigests={{.RepoDigests}} created={{.Created}}' "$REF" > /tmp/egw-pull.$$ 2>&1 </dev/null
    cat /tmp/egw-pull.$$
    check "$NAME present after pull" grep -q '^id=sha256:' /tmp/egw-pull.$$
    check "$NAME architecture is arm64" grep -q ' arch=arm64 ' /tmp/egw-pull.$$
    check "$NAME carries the pinned digest" grep -q "$PIN" /tmp/egw-pull.$$
done <<'EOF'
IMAGE_MOSQUITTO docker.io/library/eclipse-mosquitto:2.0.22@sha256:212f89e1eaeb2c322d6441b64396e3346026674db8fa9c27beac293405c32b3c
IMAGE_MONGODB docker.io/library/mongo:7.0.39@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d
IMAGE_DITTO_POLICIES docker.io/eclipse/ditto-policies:3.9.4@sha256:652f75b9accfc1da8cbc228bcede0f7778e732b9625225dafad4a2930903d4bb
IMAGE_DITTO_THINGS docker.io/eclipse/ditto-things:3.9.4@sha256:a1cc8a12d167ae5a22a31c9163913736ca14dcef4b544e6270265965089247b0
IMAGE_DITTO_GATEWAY docker.io/eclipse/ditto-gateway:3.9.4@sha256:fc9102b5ed18e5ee402fd5a1a023c5d93c215dce6fd3f24d7efb4a9f6e08682b
EOF
rm -f /tmp/egw-pull.$$

echo
echo "### state after (nothing was started)"
docker images --digests </dev/null
docker ps -a </dev/null
docker volume ls </dev/null
df -h /var/lib/docker </dev/null
sync
echo
echo "PULL RESULT: failed_checks=$FAILS"
