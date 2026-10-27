#!/bin/bash
# Independent reviewer's check: the debugfs listing rule of g3_hostprep.sh (lines 242-250) on a
# throw-away ext4 image in /tmp (the real root file system is not read).
set -u
T=$(mktemp -d /tmp/g3-s4-check-dbg.XXXXXX)
trap 'rm -rf "$T"' EXIT
RID=controller_restart-r04
mk() { # mk <name> <dirs under events...>
    rm -rf "$T/root"; mkdir -p "$T/root/opt/egw/deployment/data/events"
    local n=$1; shift
    for d in "$@"; do mkdir -p "$T/root/opt/egw/deployment/data/events/$d"; done
    rm -f "$T/$n.ext4"; truncate -s 16M "$T/$n.ext4"
    /usr/sbin/mke2fs -q -t ext4 -d "$T/root" "$T/$n.ext4" > /dev/null 2>&1 || { echo "mke2fs failed"; exit 1; }
}
rule() { # rule <image>: the script's lines, fail replaced by an echo
    local PKG=$T/pkg; rm -rf "$PKG"; mkdir -p "$PKG"
    if ! debugfs -c -R "ls -l /opt/egw/deployment/data/events" "$1" > "$PKG/l.txt" 2> "$PKG/e.txt"; then echo "  -> fail: could not be listed"; return; fi
    echo "  debugfs rc 0; stdout lines $(grep -c . "$PKG/l.txt")"
    sed 's/^/    | /' "$PKG/l.txt" | head -8
    awk '{print $NF}' "$PKG/l.txt" | sort -u > "$PKG/n.txt"
    grep -qxF -- . "$PKG/n.txt" && grep -qxF -- .. "$PKG/n.txt" || { echo "  -> fail: no . and .. ($(head -c 200 "$PKG/e.txt" | tr '\n' ' '))"; return; }
    grep -qxF -- "$RID" "$PKG/n.txt" && { echo "  -> fail: holds $RID"; return; }
    grep -q -- "^$RID" "$PKG/n.txt" && { echo "  -> fail: holds a $RID* directory"; return; }
    echo "  -> fresh on the guest"
}
echo "== events with r01..r03 only"; mk a controller_restart-r01 controller_restart-r02 controller_restart-r03 itest-reboot-q2; rule "$T/a.ext4"
echo "== events with r04"; mk b controller_restart-r03 controller_restart-r04; rule "$T/b.ext4"
echo "== events with r04.x"; mk c controller_restart-r04.old; rule "$T/c.ext4"
echo "== no events directory"; rm -rf "$T/root"; mkdir -p "$T/root/opt/egw/deployment/data"; truncate -s 16M "$T/d.ext4"; /usr/sbin/mke2fs -q -t ext4 -d "$T/root" "$T/d.ext4" > /dev/null 2>&1; rule "$T/d.ext4"
echo "== empty events directory"; mk e; rule "$T/e.ext4"
debugfs -V 2>&1 | head -1
