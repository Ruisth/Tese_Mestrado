#!/bin/sh
# fetch-collector-output.sh — fetch the output of the SUT resource collector
# (collect-resources.sh) for one run, check every file against the guest's own
# sha256 and say exactly what was fetched. Runs on the HARNESS host (WSL2 for
# the emulated gateway), never on the guest. It is the harness's
# --collector-fetch-cmd (src/egw_experiments/run.py): the harness splits the
# template without a shell, so call the script through `sh` (git does not keep
# the executable bit on every checkout) and quote "{dest}":
#
#   --collector-fetch-cmd 'sh <clone>/src/deployment/scripts/fetch-collector-output.sh egw-tcg /tmp/resources-{run_id}.csv "{dest}"'
#
# Usage:
#   sh fetch-collector-output.sh <ssh-target> <remote-csv> <local-csv>
#
# <ssh-target> is an ssh destination or ~/.ssh/config alias (A-Z a-z 0-9 _ . @ -).
# <remote-csv> is the collector's absolute output path on the guest
# (A-Z a-z 0-9 _ . / - only, so it needs no quoting on the remote shell).
# <local-csv> is where the CSV goes; its directory must exist.
#
# Files, in this order (<remote-csv><suffix> -> <local-csv><suffix>):
#   (no suffix)        the CSV                            mandatory
#   .diagnostics.log   the collector's diagnostics        mandatory
#   .lifecycle.csv     container lifecycle and names      mandatory
#   .self-test         the self-test marker               optional
# For each file: ask the guest whether it exists (ssh ... test -f), read the
# guest's sha256sum, copy it (scp -q), hash the local copy and compare. One
# status line per file on stdout, for example
#   fetch: resources-nominal-r01.csv.lifecycle.csv present sha256=<hex> verified
# then one "fetch: result exit=N ..." line. A present .self-test marker is
# fetched and reported but does not change the exit status: it means the
# output is NOT a measurement, and the harness judges that (manifest
# 'collector.problems' make the run invalid).
#
# Exit status:
#   0  every mandatory file present, copied and verified
#   2  usage error: arguments, characters of the target or remote path, a
#      missing local directory, no sha256sum on this host
#   3  a mandatory file is absent on the guest
#   4  a copied file's sha256 differs from the guest's (for example a
#      collector still writing because the stop hook failed)
#   5  an ssh or scp failure (guest unreachable, key refused, copy failed)
#   6  a local destination already exists: nothing is fetched, because raw
#      run evidence is write-once
# Every file is attempted even after a failure, and the highest of 5, 4 and 3
# that occurred is returned. A copy that failed or does not match is left in
# place for inspection; the harness records the exit status and the run is
# invalid.
#
# ssh and scp run with -o BatchMode=yes -o ConnectTimeout=10 and stdin from
# /dev/null: a guest that is down or a key that is refused fails within
# seconds instead of waiting for a password or the harness's 300 s hook
# timeout. EGW_FETCH_SSH and EGW_FETCH_SCP replace the two commands (tests:
# src/tests/test_fetch_collector_output.py).
#
# POSIX sh: tested under dash and bash.

set -u

SSH_CMD=${EGW_FETCH_SSH:-ssh}
SCP_CMD=${EGW_FETCH_SCP:-scp}

usage() {
    echo "usage: sh fetch-collector-output.sh <ssh-target> <remote-csv> <local-csv>" >&2
    exit 2
}

[ $# -eq 3 ] || usage
TARGET=$1
REMOTE=$2
LOCAL=$3
[ -n "$TARGET" ] && [ -n "$REMOTE" ] && [ -n "$LOCAL" ] || usage

case "$TARGET" in
    -* | *[!A-Za-z0-9_.@-]*)
        echo "fetch: invalid ssh target '$TARGET' (A-Z a-z 0-9 _ . @ - only, not starting with -)" >&2
        exit 2
        ;;
esac
case "$REMOTE" in
    /*) ;;
    *)
        echo "fetch: the remote CSV path must be absolute: '$REMOTE'" >&2
        exit 2
        ;;
esac
case "$REMOTE" in
    *[!A-Za-z0-9_./-]*)
        echo "fetch: the remote CSV path may hold only A-Z a-z 0-9 _ . / -: '$REMOTE'" >&2
        exit 2
        ;;
esac
case "$LOCAL" in
    */) usage ;;
esac

LOCAL_DIR=$(dirname -- "$LOCAL")
if [ ! -d "$LOCAL_DIR" ]; then
    echo "fetch: the local directory '$LOCAL_DIR' does not exist" >&2
    exit 2
fi
if ! command -v sha256sum > /dev/null 2>&1; then
    echo "fetch: sha256sum is not available on this host" >&2
    exit 2
fi

# scp reads an argument with a colon before its first slash as host:path, so
# a relative local path is anchored with ./ before it is handed to scp.
case "$LOCAL" in
    /*) LOCAL_ARG=$LOCAL ;;
    *) LOCAL_ARG=./$LOCAL ;;
esac
NAME=${LOCAL##*/}
SUFFIXES=".diagnostics.log .lifecycle.csv .self-test"

# Raw evidence is write-once: refuse before anything is fetched.
for suffix in "" $SUFFIXES; do
    if [ -e "$LOCAL$suffix" ] || [ -h "$LOCAL$suffix" ]; then
        echo "fetch: $NAME$suffix already exists at '$LOCAL$suffix'; refusing to overwrite it (nothing fetched)"
        echo "fetch: result exit=6 (a local destination already exists)"
        exit 6
    fi
done

worst=0
fail() {
    if [ "$1" -gt "$worst" ]; then
        worst=$1
    fi
}

remote() {
    "$SSH_CMD" -o BatchMode=yes -o ConnectTimeout=10 "$TARGET" "$1" < /dev/null
}

# fetch_one <suffix> <mandatory|optional>
fetch_one() {
    f_remote=$REMOTE$1
    f_local=$LOCAL$1
    f_name=$NAME$1
    remote "test -f '$f_remote'"
    f_rc=$?
    if [ "$f_rc" -eq 1 ]; then
        echo "fetch: $f_name absent ($2)"
        if [ "$2" = mandatory ]; then
            fail 3
        fi
        return 0
    fi
    if [ "$f_rc" -ne 0 ]; then
        echo "fetch: $f_name not checked: ssh exit $f_rc while testing $TARGET:$f_remote"
        fail 5
        return 0
    fi
    f_out=$(remote "sha256sum '$f_remote'")
    f_rc=$?
    f_remote_sum=${f_out%% *}
    if [ "$f_rc" -ne 0 ] || [ "${#f_remote_sum}" -ne 64 ]; then
        echo "fetch: $f_name not copied: no sha256 from the guest (ssh exit $f_rc)"
        fail 5
        return 0
    fi
    case "$f_remote_sum" in
        *[!0-9a-f]*)
            echo "fetch: $f_name not copied: unexpected sha256sum output from the guest"
            fail 5
            return 0
            ;;
    esac
    "$SCP_CMD" -q -o BatchMode=yes -o ConnectTimeout=10 "$TARGET:$f_remote" "$LOCAL_ARG$1" < /dev/null
    f_rc=$?
    if [ "$f_rc" -ne 0 ] || [ ! -f "$f_local" ]; then
        echo "fetch: $f_name transfer failed (scp exit $f_rc)"
        fail 5
        return 0
    fi
    f_out=$(sha256sum < "$f_local")
    f_local_sum=${f_out%% *}
    if [ "$f_local_sum" != "$f_remote_sum" ]; then
        echo "fetch: $f_name present sha256=$f_remote_sum local_sha256=$f_local_sum MISMATCH"
        fail 4
        return 0
    fi
    if [ "$1" = .self-test ]; then
        echo "fetch: $f_name present sha256=$f_local_sum verified (self-test marker: this output is NOT a measurement)"
    else
        echo "fetch: $f_name present sha256=$f_local_sum verified"
    fi
    return 0
}

fetch_one "" mandatory
fetch_one .diagnostics.log mandatory
fetch_one .lifecycle.csv mandatory
fetch_one .self-test optional

case "$worst" in
    0) echo "fetch: result exit=0 (every mandatory file present and verified)" ;;
    3) echo "fetch: result exit=3 (a mandatory file is absent on the guest)" ;;
    4) echo "fetch: result exit=4 (a copied file does not match the guest's sha256)" ;;
    *) echo "fetch: result exit=$worst (an ssh or scp failure)" ;;
esac
exit "$worst"
