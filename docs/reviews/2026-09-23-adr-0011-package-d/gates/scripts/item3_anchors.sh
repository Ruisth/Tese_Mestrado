#!/usr/bin/env bash
# Item 3 anchors: prints every file:line range cited in item3_ack_order.md.
# Read-only: git ls-tree / git hash-object (no -w) / sed -n only. Run from
# Git Bash on the workstation:
#   bash item3_anchors.sh > ../out/item3_anchors.out.txt
set -u
WINREPO="${WINREPO:-$(cd "$(dirname "$0")/../../../../devwt" && pwd)}"   # the scratchpad worktree of the Windows repository; it shares its objects and refs
MERGED_DEV=35fe8bb

echo "== 1. Code identity: src/egw_controller at ${MERGED_DEV} (Windows repository) vs the WSL clone's working tree"
git -C "$WINREPO" log -1 --format='%H %ci %s' "$MERGED_DEV"
DEV_BLOBS=$(git -C "$WINREPO" ls-tree "$MERGED_DEV" src/egw_controller/ src/pyproject.toml src/CONTRACTS.md \
  src/deployment/mosquitto/config/mosquitto.conf src/deployment/compose.yaml \
  | awk '{print $3, $4}' | sort -k2)
echo "WSL clone HEAD: $(wsl -d Ubuntu-24.04 --exec bash -lc 'cd /home/ruisth/egw-exec/repo && git rev-parse HEAD && git rev-parse --abbrev-ref HEAD' | tr -d '\r' | tr '\n' ' ')"
WSL_BLOBS=$(wsl -d Ubuntu-24.04 --exec bash -lc '
  cd /home/ruisth/egw-exec/repo
  for f in src/egw_controller/*.py src/egw_controller/README.md src/pyproject.toml src/CONTRACTS.md \
           src/deployment/mosquitto/config/mosquitto.conf src/deployment/compose.yaml; do
    echo "$(git hash-object "$f") $f"
  done | sort -k2' | tr -d '\r')
if [ "$DEV_BLOBS" = "$WSL_BLOBS" ]; then
  echo "IDENTICAL: every blob of the listed files matches ${MERGED_DEV}"
else
  echo "DIFFERENT:"; diff <(echo "$DEV_BLOBS") <(echo "$WSL_BLOBS")
fi
echo "$WSL_BLOBS"

wsl -d Ubuntu-24.04 --exec bash -lc '
R=/home/ruisth/egw-exec/repo/src
P=$HOME/egw-exec/venv/lib/python3.12/site-packages/paho/mqtt/client.py
show() { echo "-- $1:$2"; awk -v a="${2%-*}" -v b="${2#*-}" "NR>=a && NR<=b {printf \"%5d  %s\n\", NR, \$0}" "$1"; }
echo; echo "== 2. Controller (repository working tree, identical to 35fe8bb per section 1)"
show $R/egw_controller/mqtt.py 33-36
show $R/egw_controller/mqtt.py 73-76
show $R/egw_controller/mqtt.py 149-161
show $R/egw_controller/mqtt.py 172-199
show $R/egw_controller/mqtt.py 203-217
show $R/egw_controller/service.py 11-12
show $R/egw_controller/service.py 52-53
show $R/egw_controller/service.py 81-87
show $R/egw_controller/service.py 150-169
show $R/egw_controller/service.py 182-201
show $R/egw_controller/service.py 210-229
show $R/egw_controller/service.py 244-254
show $R/egw_controller/service.py 287-301
show $R/egw_controller/service.py 316-343
show $R/egw_controller/service.py 414-415
show $R/egw_controller/schema.py 123-130
show $R/egw_controller/schema.py 139-143
show $R/egw_controller/ditto.py 228-255
show $R/egw_controller/ditto.py 323-333
show $R/egw_controller/dedupe.py 52-81
show $R/egw_controller/events.py 74-82
show $R/egw_controller/events.py 103-119
show $R/egw_controller/metrics.py 143-160
show $R/egw_controller/app.py 82-88
show $R/egw_controller/app.py 153-164
show $R/deployment/compose.yaml 243-256
show $R/deployment/mosquitto/config/mosquitto.conf 29-35
show $R/CONTRACTS.md 186-195
show $R/CONTRACTS.md 275-287
show $R/deployment/images.lock.env 39-39
show $R/Dockerfile 25-25
show $R/pyproject.toml 11-11
echo; echo "== 3. paho-mqtt $($HOME/egw-exec/venv/bin/python -c "import paho.mqtt as m; print(m.__version__)") in ~/egw-exec/venv"
show $P 690-695
show $P 742-751
show $P 784-789
show $P 812-812
show $P 877-877
show $P 1123-1135
show $P 1566-1604
show $P 1680-1688
show $P 2151-2168
show $P 2294-2330
show $P 2332-2366
show $P 2859-2872
show $P 3036-3052
show $P 3160-3180
show $P 3222-3236
show $P 3337-3339
show $P 3444-3444
show $P 3454-3461
show $P 3741-3752
show $P 3758-3795
show $P 4033-4039
show $P 4091-4096
show $P 4115-4119
show $P 4143-4161
show $P 4165-4184
show $P 4467-4506
show $P 4521-4525
show $P 4527-4547
A=/usr/lib/python3.12/asyncio
echo; echo "== 4. CPython asyncio in the analysis environment ($(python3 --version))"
show $A/base_events.py 539-541
show $A/base_events.py 814-818
show $A/base_events.py 838-847
show $A/base_events.py 1966-1972
show $A/queues.py 47-54
show $A/queues.py 110-147
'
