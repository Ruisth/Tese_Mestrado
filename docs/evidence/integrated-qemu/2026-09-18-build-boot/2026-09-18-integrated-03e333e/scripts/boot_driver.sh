#!/bin/bash
# Starts the integrated guest detached, with a pseudo-terminal for runqemu's
# serial console. Usage: boot_driver.sh <evidence-dir> <run-name>
set -u
E=$1
RUN=$2
mkdir -p "$E/boot"
cd /home/ruisth/yocto/egw/src/yocto || exit 1
if ss -ltn | grep -E ':(2222|8883) ' > "$E/boot/ports-busy.txt"; then
    echo "exit=90 reason=host-port-busy finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$E/boot/$RUN.status"
    exit 90
fi
rm -f "$E/boot/ports-busy.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$E/boot/$RUN.started"
export EGW_LOG_DIR="$E/boot"
# A FIFO with a silent writer keeps the console's stdin open without ever
# sending a byte to the guest.
FIFO="$E/boot/$RUN.stdin.fifo"
rm -f "$FIFO"; mkfifo "$FIFO"
sleep infinity > "$FIFO" &
KEEP=$!
script -qfec "./scripts/run-qemu-integrated.sh $RUN" "$E/boot/$RUN.console.typescript" < "$FIFO" > /dev/null 2>&1
echo "exit=$? finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$E/boot/$RUN.status"
kill "$KEEP" 2>/dev/null
rm -f "$FIFO"
