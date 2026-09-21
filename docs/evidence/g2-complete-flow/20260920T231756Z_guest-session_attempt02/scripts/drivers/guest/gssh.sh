#!/bin/bash
# Open an interactive SSH session on the running guest, or run one command there.
# Meant for watching a run: read, do not change anything during an evidence run.
# Usage: gssh.sh [command ...]
set -u
E=$(cd -- "$(dirname -- "$0")/.." && pwd)
KNOWN=$E/boot/known_hosts
exec ssh -i "$HOME/.ssh/egw_campaign" -p 2222 -o IdentitiesOnly=yes \
     -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN" \
     -o ConnectTimeout=10 -o LogLevel=ERROR egw@127.0.0.1 "$@"
