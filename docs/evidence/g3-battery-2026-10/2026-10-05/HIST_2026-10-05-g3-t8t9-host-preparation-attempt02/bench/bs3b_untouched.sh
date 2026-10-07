#!/bin/bash
# Bench of the second opening of S3: the real ~/egw-exec and ~/egw-tcg before and after the
# benches, read-only (adapted from the earlier preparation's bench/bs3_untouched.sh).
#   before <dir>   makes the marker file <dir>/.started (the one thing written, inside the
#                  bench root) and keeps in <dir>: the listing of every entry of the two
#                  trees (path, modification time, size), the listing of /tmp, the clone's
#                  HEAD;
#   after <dir>    takes the listings again, compares them with the kept ones, and counts
#                  the entries of the two trees that are newer than the marker.
# <dir> must be a folder under /tmp/g3-s3b-bench. Nothing is written under the two trees.
# Usage (WSL, the real HOME): bs3b_untouched.sh before|after /tmp/g3-s3b-bench/<dir>
set -u
MODE=${1:?usage: bs3b_untouched.sh before|after /tmp/g3-s3b-bench/<dir>}
DIR=${2:?usage: bs3b_untouched.sh before|after /tmp/g3-s3b-bench/<dir>}
ROOT=/tmp/g3-s3b-bench
case $DIR in "$ROOT"/?*) ;; *) echo "refused: <dir> must be under $ROOT"; exit 2 ;; esac
MARK=$DIR/.started
listing() {
    find "$HOME/egw-exec" "$HOME/egw-tcg" -printf '%p\t%T+\t%s\n' 2> /dev/null | LC_ALL=C sort
}
tmp_listing() { ls -1 /tmp | LC_ALL=C sort; }
head_of() { cat "$HOME/egw-exec/repo/.git/HEAD" 2> /dev/null; }
facts() {
    echo "the first opening's state directory ~/egw-exec/g3-t8t9-s3: $([ -d "$HOME/egw-exec/g3-t8t9-s3" ] && echo "exists, $(find "$HOME/egw-exec/g3-t8t9-s3" | wc -l) entries" || echo 'does not exist')"
    echo "  its S3-preflight.console.txt sha256 $(sha256sum < "$HOME/egw-exec/g3-t8t9-s3/S3-preflight.console.txt" 2> /dev/null | cut -d' ' -f1); session-S3.env sha256 $(sha256sum < "$HOME/egw-exec/g3-t8t9-s3/session-S3.env" 2> /dev/null | cut -d' ' -f1), state=$(sed -n 's/^state=//p' "$HOME/egw-exec/g3-t8t9-s3/session-S3.env" 2> /dev/null | tail -n 1)"
    echo "the second opening's default state directory ~/egw-exec/g3-t8t9-s3-attempt02: $([ -e "$HOME/egw-exec/g3-t8t9-s3-attempt02" ] && echo EXISTS || echo 'does not exist')"
    echo "~/egw-exec/current_session: $([ -e "$HOME/egw-exec/current_session" ] && echo EXISTS || echo 'does not exist')"
}
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) bs3b_untouched.sh $MODE (HOME=$HOME); host uptime $(cut -d' ' -f1 /proc/uptime) s"
case $MODE in
    before)
        mkdir -p "$DIR" || exit 1
        [ ! -e "$MARK" ] || { echo "refused: $MARK exists (a 'before' was taken already in $DIR)"; exit 2; }
        listing > "$DIR/untouched.before.listing.txt"
        tmp_listing > "$DIR/untouched.before.tmp.txt"
        head_of > "$DIR/untouched.before.head.txt"
        : > "$MARK"
        echo "entries of ~/egw-exec and ~/egw-tcg: $(wc -l < "$DIR/untouched.before.listing.txt"); sha256 of the listing: $(sha256sum < "$DIR/untouched.before.listing.txt" | cut -d' ' -f1)"
        echo "clone HEAD: $(cat "$DIR/untouched.before.head.txt")"
        facts
        echo "/tmp entries: $(tr '\n' ' ' < "$DIR/untouched.before.tmp.txt")"
        echo "marker: $MARK made at $(date -u -r "$MARK" +%Y-%m-%dT%H:%M:%SZ)"
        echo "keepalive clients, 'sleep N' with N of 3600 or more (not started and not ended by this stream): $(ps -eo pid=,etimes=,args= 2> /dev/null | awk '$3 == "sleep" && NF == 4 && $4 >= 3600 { printf "pid %s sleep %s, running for %s s; ", $1, $4, $2 }')"
        ;;
    after)
        [ -e "$MARK" ] || { echo "refused: no marker $MARK"; exit 2; }
        listing > "$DIR/untouched.after.listing.txt"
        tmp_listing > "$DIR/untouched.after.tmp.txt"
        head_of > "$DIR/untouched.after.head.txt"
        echo "entries of ~/egw-exec and ~/egw-tcg: $(wc -l < "$DIR/untouched.after.listing.txt"); sha256 of the listing: $(sha256sum < "$DIR/untouched.after.listing.txt" | cut -d' ' -f1)"
        if cmp -s "$DIR/untouched.before.listing.txt" "$DIR/untouched.after.listing.txt"; then
            echo "listing (path, modification time, size of every entry): IDENTICAL before and after"
        else
            echo "listing: DIFFERENT -"; diff "$DIR/untouched.before.listing.txt" "$DIR/untouched.after.listing.txt" | head -n 40
        fi
        echo "entries newer than the marker ($(date -u -r "$MARK" +%Y-%m-%dT%H:%M:%SZ)): $(find "$HOME/egw-exec" "$HOME/egw-tcg" -newer "$MARK" 2> /dev/null | wc -l)"
        echo "clone HEAD: $(cat "$DIR/untouched.after.head.txt") ($(cmp -s "$DIR/untouched.before.head.txt" "$DIR/untouched.after.head.txt" && echo unchanged || echo CHANGED))"
        facts
        echo "/tmp entries that were not there before: $(LC_ALL=C comm -13 "$DIR/untouched.before.tmp.txt" "$DIR/untouched.after.tmp.txt" | tr '\n' ' ')"
        echo "/tmp/wrong.key or /tmp/wrong.crt: $(ls /tmp/wrong.key /tmp/wrong.crt 2> /dev/null | tr '\n' ' ')$(ls /tmp/wrong.key /tmp/wrong.crt > /dev/null 2>&1 || echo 'neither exists')"
        # A scenario's bench is $ROOT/e<number>...: every process a bench started (the fake
        # QEMU, a subcommand, a stub) names that directory on its command line.
        echo "processes whose command line names a scenario's bench ($ROOT/e<number>...): $(/usr/bin/pgrep -f "$ROOT/e[0-9]" | wc -l)"
        /usr/bin/pgrep -af "$ROOT/e[0-9]" | cut -c1-160
        echo "processes named qemu-system-aarch64 on this host (real pgrep, the frozen drivers' pattern): $(/usr/bin/pgrep -f '^(\S*/)?qemu-system-aarch64( |$)' | wc -l); bash loops that stood for QEMU: $(/usr/bin/pgrep -f 'qemu-system-aarch64 -machine virt' | wc -l)"
        echo "keepalive clients, 'sleep N' with N of 3600 or more (not started and not ended by this stream): $(ps -eo pid=,etimes=,args= 2> /dev/null | awk '$3 == "sleep" && NF == 4 && $4 >= 3600 { printf "pid %s sleep %s, running for %s s; ", $1, $4, $2 }')"
        ;;
    *) echo "usage: bs3b_untouched.sh before|after /tmp/g3-s3b-bench/<dir>"; exit 2 ;;
esac
