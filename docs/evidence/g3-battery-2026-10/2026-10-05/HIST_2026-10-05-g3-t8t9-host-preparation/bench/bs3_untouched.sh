#!/bin/bash
# Stream BENCH: the real ~/egw-exec and ~/egw-tcg before and after the benches, read-only.
#   before <dir>   makes the marker file /tmp/g3-s3-bench/.started (the one thing written,
#                  inside the bench root) and keeps in <dir>: the listing of every entry of
#                  the two trees (path, modification time, size), the listing of /tmp, the
#                  clone's HEAD;
#   after <dir>    takes the listings again, compares them with the kept ones, and counts
#                  the entries of the two trees that are newer than the marker.
# Nothing is written under the two trees; <dir> is a folder of the record.
# Usage (WSL, the real HOME): bs3_untouched.sh before|after <record dir>
set -u
MODE=${1:?usage: bs3_untouched.sh before|after <record dir>}
DIR=${2:?usage: bs3_untouched.sh before|after <record dir>}
ROOT=/tmp/g3-s3-bench
MARK=$ROOT/.started
listing() {
    find "$HOME/egw-exec" "$HOME/egw-tcg" -printf '%p\t%T+\t%s\n' 2> /dev/null | LC_ALL=C sort
}
tmp_listing() { ls -1 /tmp | LC_ALL=C sort; }
head_of() { cat "$HOME/egw-exec/repo/.git/HEAD" 2> /dev/null; }
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) bs3_untouched.sh $MODE (HOME=$HOME)"
case $MODE in
    before)
        mkdir -p "$ROOT" "$DIR" || exit 1
        [ ! -e "$MARK" ] || { echo "refused: $MARK exists (a 'before' was taken already)"; exit 2; }
        listing > "$DIR/untouched.before.listing.txt"
        tmp_listing > "$DIR/untouched.before.tmp.txt"
        head_of > "$DIR/untouched.before.head.txt"
        : > "$MARK"
        echo "entries of ~/egw-exec and ~/egw-tcg: $(wc -l < "$DIR/untouched.before.listing.txt"); sha256 of the listing: $(sha256sum < "$DIR/untouched.before.listing.txt" | cut -d' ' -f1)"
        echo "clone HEAD: $(cat "$DIR/untouched.before.head.txt")"
        echo "/tmp entries: $(tr '\n' ' ' < "$DIR/untouched.before.tmp.txt")"
        echo "marker: $MARK made at $(date -u -r "$MARK" +%Y-%m-%dT%H:%M:%SZ)"
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
        echo "/tmp entries that were not there before: $(LC_ALL=C comm -13 "$DIR/untouched.before.tmp.txt" "$DIR/untouched.after.tmp.txt" | tr '\n' ' ')"
        echo "/tmp/wrong.key or /tmp/wrong.crt: $(ls /tmp/wrong.key /tmp/wrong.crt 2> /dev/null | tr '\n' ' ')$(ls /tmp/wrong.key /tmp/wrong.crt > /dev/null 2>&1 || echo 'neither exists')"
        echo "the S3 state directory ~/egw-exec/g3-t8t9-s3: $([ -e "$HOME/egw-exec/g3-t8t9-s3" ] && echo EXISTS || echo 'does not exist')"
        # A scenario's bench is $ROOT/s<number>...: every process a bench started (the fake
        # QEMU, a row, a poll, a stub) names that directory on its command line. The pattern
        # does not match this script's own invocation, whose argument is another directory.
        echo "processes whose command line names a scenario's bench ($ROOT/s<number>...): $(/usr/bin/pgrep -f "$ROOT/s[0-9]" | wc -l)"
        /usr/bin/pgrep -af "$ROOT/s[0-9]" | cut -c1-160
        echo "processes named qemu-system-aarch64 on this host (real pgrep, the frozen drivers' pattern): $(/usr/bin/pgrep -f '^(\S*/)?qemu-system-aarch64( |$)' | wc -l); bash loops that stood for QEMU: $(/usr/bin/pgrep -f 'qemu-system-aarch64 -machine virt' | wc -l)"
        echo "keepalive client (not started and not ended by this stream): $(ps -eo pid=,etimes=,args= 2> /dev/null | awk '$3 == "sleep" && $4 == 43200 { print "pid " $1 ", running for " $2 " s" }')"
        ;;
    *) echo "usage: bs3_untouched.sh before|after <record dir>"; exit 2 ;;
esac
