#!/bin/bash
# Bench of the S4 operator script (stream BENCH of the S4 preparation, 2026-10-05): the
# real ~/egw-exec, ~/egw-tcg and output_test before and after the benches, read-only.
# Adapted from S3b's bench/bs3b_untouched.sh (bench root, output_test added, the plan's
# sha256 and the S4 state directory named).
#   before <dir>   makes the marker file <dir>/.started (the one thing written, inside the
#                  bench root) and keeps in <dir>: the listing of every entry of the two
#                  trees and of output_test (path, modification time, size), the listing of
#                  /tmp, the clone's HEAD, the plan's sha256;
#   after <dir>    takes them again, compares them with the kept ones, and counts the
#                  entries of the three trees that are newer than the marker; lists every
#                  process left that names a bench, every fake QEMU loop, and the host's
#                  keepalive clients.
# <dir> must be a folder under /tmp/g3-s4-bench. Nothing is written under the three trees.
# Usage (WSL, the real HOME): bs4_untouched.sh before|after /tmp/g3-s4-bench/<dir>
set -u
MODE=${1:?usage: bs4_untouched.sh before|after /tmp/g3-s4-bench/<dir>}
DIR=${2:?usage: bs4_untouched.sh before|after /tmp/g3-s4-bench/<dir>}
ROOT=/tmp/g3-s4-bench
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
PLAN_SHA=c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60
case $DIR in "$ROOT"/?*) ;; *) echo "refused: <dir> must be under $ROOT"; exit 2 ;; esac
case $HOME in /tmp/*) echo "refused: HOME is a bench's ($HOME): this script reads the real HOME"; exit 2 ;; esac
MARK=$DIR/.started
listing() { find "$HOME/egw-exec" "$HOME/egw-tcg" -printf '%p\t%T+\t%s\n' 2> /dev/null | LC_ALL=C sort; }
ot_listing() { find "$OT" -printf '%P\t%T+\t%s\n' 2> /dev/null | LC_ALL=C sort; }
tmp_listing() { ls -1 /tmp | LC_ALL=C sort; }
head_of() { cat "$HOME/egw-exec/repo/.git/HEAD" 2> /dev/null; }
plan_sha() { sha256sum "$HOME/egw-tcg/pilot/campaign_plan.json" 2> /dev/null | cut -d' ' -f1; }
facts() {
    local p
    p=$(plan_sha)
    echo "plan ~/egw-tcg/pilot/campaign_plan.json: sha256 $p ($([ "$p" = "$PLAN_SHA" ] && echo "the value of the brief, c195bd3f..." || echo "NOT $PLAN_SHA"))"
    echo "S4's default state directory ~/egw-exec/g3-t6-s4: $([ -e "$HOME/egw-exec/g3-t6-s4" ] && echo EXISTS || echo 'does not exist')"
    echo "~/egw-exec/current_session: $([ -e "$HOME/egw-exec/current_session" ] && echo EXISTS || echo 'does not exist')"
    echo "~/egw-tcg/pilot/results/raw/controller_restart-r04: $([ -e "$HOME/egw-tcg/pilot/results/raw/controller_restart-r04" ] && echo EXISTS || echo 'does not exist')"
    echo "attempts of row t6 in ~/egw-exec/attempts: $(ls -d "$HOME"/egw-exec/attempts/*_g3-qualification-t6_attempt* 2> /dev/null | sed 's#.*/##' | tr '\n' ' ')"
}
keepalives() { ps -eo pid=,etimes=,args= 2> /dev/null | awk '$3 == "sleep" && NF == 4 && $4 >= 3600 { printf "pid %s sleep %s, running for %s s; ", $1, $4, $2 }'; }
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) bs4_untouched.sh $MODE (HOME=$HOME); host uptime $(cut -d' ' -f1 /proc/uptime) s"
case $MODE in
    before)
        mkdir -p "$DIR" || exit 1
        [ ! -e "$MARK" ] || { echo "refused: $MARK exists (a 'before' was taken already in $DIR)"; exit 2; }
        listing > "$DIR/untouched.before.listing.txt"
        ot_listing > "$DIR/untouched.before.ot.txt"
        tmp_listing > "$DIR/untouched.before.tmp.txt"
        head_of > "$DIR/untouched.before.head.txt"
        : > "$MARK"
        echo "entries of ~/egw-exec and ~/egw-tcg: $(wc -l < "$DIR/untouched.before.listing.txt"); sha256 of the listing: $(sha256sum < "$DIR/untouched.before.listing.txt" | cut -d' ' -f1)"
        echo "entries of output_test: $(wc -l < "$DIR/untouched.before.ot.txt"); sha256 of the listing: $(sha256sum < "$DIR/untouched.before.ot.txt" | cut -d' ' -f1)"
        echo "clone HEAD: $(cat "$DIR/untouched.before.head.txt")"
        facts
        echo "/tmp entries named g3-s4-*: $(grep '^g3-s4-' "$DIR/untouched.before.tmp.txt" | tr '\n' ' ')"
        echo "marker: $MARK made at $(date -u -r "$MARK" +%Y-%m-%dT%H:%M:%SZ)"
        echo "keepalive clients, 'sleep N' with N of 3600 or more (not started and not ended by this stream): $(keepalives)"
        ;;
    after)
        [ -e "$MARK" ] || { echo "refused: no marker $MARK"; exit 2; }
        listing > "$DIR/untouched.after.listing.txt"
        ot_listing > "$DIR/untouched.after.ot.txt"
        tmp_listing > "$DIR/untouched.after.tmp.txt"
        head_of > "$DIR/untouched.after.head.txt"
        echo "entries of ~/egw-exec and ~/egw-tcg: $(wc -l < "$DIR/untouched.after.listing.txt"); sha256 of the listing: $(sha256sum < "$DIR/untouched.after.listing.txt" | cut -d' ' -f1)"
        if cmp -s "$DIR/untouched.before.listing.txt" "$DIR/untouched.after.listing.txt"; then
            echo "listing of ~/egw-exec and ~/egw-tcg (path, modification time, size of every entry): IDENTICAL before and after"
        else
            echo "listing of ~/egw-exec and ~/egw-tcg: DIFFERENT -"; diff "$DIR/untouched.before.listing.txt" "$DIR/untouched.after.listing.txt" | head -n 40
        fi
        echo "entries of output_test: $(wc -l < "$DIR/untouched.after.ot.txt"); sha256 of the listing: $(sha256sum < "$DIR/untouched.after.ot.txt" | cut -d' ' -f1)"
        if cmp -s "$DIR/untouched.before.ot.txt" "$DIR/untouched.after.ot.txt"; then
            echo "listing of output_test (path, modification time, size of every entry): IDENTICAL before and after"
        else
            echo "listing of output_test: DIFFERENT -"; diff "$DIR/untouched.before.ot.txt" "$DIR/untouched.after.ot.txt" | head -n 40
        fi
        echo "entries newer than the marker ($(date -u -r "$MARK" +%Y-%m-%dT%H:%M:%SZ)): ~/egw-exec and ~/egw-tcg $(find "$HOME/egw-exec" "$HOME/egw-tcg" -newer "$MARK" 2> /dev/null | wc -l); output_test $(find "$OT" -newer "$MARK" 2> /dev/null | wc -l)"
        echo "clone HEAD: $(cat "$DIR/untouched.after.head.txt") ($(cmp -s "$DIR/untouched.before.head.txt" "$DIR/untouched.after.head.txt" && echo unchanged || echo CHANGED))"
        facts
        echo "/tmp entries that were not there before: $(LC_ALL=C comm -13 "$DIR/untouched.before.tmp.txt" "$DIR/untouched.after.tmp.txt" | tr '\n' ' ')"
        # Every process a bench started (the fake QEMU, a subcommand, a stub, the harness
        # stand-in) names its bench directory on its command line or runs under its HOME.
        # (this script names the bench root on its own command line: it and its own subshells
        # are left out of the count)
        left=$(/usr/bin/pgrep -af "$ROOT/" | grep -v 'bs4_untouched\.sh')
        echo "processes whose command line names the bench root $ROOT (this script left out): $(printf '%s' "$left" | grep -c .)"
        scr=$(cd "$(dirname "$0")/../../.." && pwd)     # the scratchpad, shown as <S>
        [ -z "$left" ] || printf '%s\n' "$left" | sed "s#$scr#<S>#g" | cut -c1-160
        echo "processes named qemu-system-aarch64 on this host (real pgrep, the frozen drivers' pattern): $(/usr/bin/pgrep -f '^(\S*/)?qemu-system-aarch64( |$)' | wc -l); bash loops that stood for QEMU: $(/usr/bin/pgrep -f 'qemu-system-aarch64 -machine virt' | wc -l)"
        echo "keepalive clients, 'sleep N' with N of 3600 or more (not started and not ended by this stream): $(keepalives)"
        ;;
    *) echo "usage: bs4_untouched.sh before|after /tmp/g3-s4-bench/<dir>"; exit 2 ;;
esac
