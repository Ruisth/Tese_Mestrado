#!/usr/bin/env bash
# v11 - the third-party line citations of ADR 0011, read in ~/egw-exec/venv (read-only). Run inside WSL.
set -u
V=~/egw-exec/venv
PY=$V/bin/python
$PY -c "import paho.mqtt, uvicorn; print('paho', paho.mqtt.__version__, 'uvicorn', uvicorn.__version__)"
P=$($PY -c "import paho.mqtt.client as c; print(c.__file__)")
U=$($PY -c "import uvicorn.server as s; print(s.__file__)")
for r in 740,752 783,787 4145,4153 4163,4177; do echo "--- paho client.py:$r"; sed -n "${r}p" "$P" | nl -ba -v "${r%,*}"; done
for r in 34,38 340,349; do echo "--- uvicorn server.py:$r"; sed -n "${r}p" "$U" | nl -ba -v "${r%,*}"; done
echo "--- paho: does the client impose PUBACK ordering, or send in callback order?"
grep -n "def ack\|def _send_puback\|manual_ack" "$P" | head -20
