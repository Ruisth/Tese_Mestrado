#!/bin/sh
# guest_meminfo_sampler.sh — whole-guest memory sampler for the Yocto-vs-Debian
# comparison. Runs ON the guest (busybox ash or dash), never on the host: the
# comparison asks what the whole gateway guest holds in memory under each operating
# system — kernel, init, daemons and the stack together — and only the guest
# kernel's own accounting in /proc/meminfo gives that figure. mem_used_kb =
# MemTotal - MemAvailable, the kernel's estimate of what a new workload could not
# get without swapping (free(1)'s "used"); not the sum of the containers' cgroups.
#
# Appends  ts_utc,epoch_s,uptime_s,mem_total_kb,mem_available_kb,mem_used_kb
# lines, the header once when OUT_CSV is absent or empty. uptime_s is the first
# field of /proc/uptime, read in the same sample as the memory fields: the guest's
# CLOCK_BOOTTIME, equal to the controller's CLOCK_MONOTONIC while the guest never
# suspends, and the clock the summary tool windows the lines on; ts_utc/epoch_s
# are the wall clock, for reading only. Each line is one printf, so a reader
# (scp, tail -f) sees a whole line or nothing. On SIGTERM, SIGINT or when
# --duration expires it appends one closing comment line
#   # end epoch_s=<n> samples=<count>
# and exits 0; readers skip lines starting with '#'. A sample whose fields cannot
# be read writes NO line (never a zero) and one diagnostic on stderr.
#
# Usage (ON the guest): sh guest_meminfo_sampler.sh OUT_CSV [--interval S] [--duration S]
# interval default 1; duration default 0 = until a signal. Exit 2: OUT_CSV missing,
# a non-integer interval or duration, /proc/meminfo or /proc/uptime unreadable, or
# meminfo without its two fields. POSIX sh + awk as the image's busybox 1.36.1
# offers them: no arrays, no `date %N`, no `head -N`, whole-second `sleep`; the
# cadence is the interval plus two short processes per sample (slower than nominal
# under emulation; the summary tool prints the sample count beside every median).
set -u
usage() { echo "usage: $0 OUT_CSV [--interval S] [--duration S]" >&2; exit 2; }
[ $# -ge 1 ] || usage
OUT=$1
shift
INTERVAL=1
DURATION=0
while [ $# -gt 0 ]; do
    case "$1" in
        --interval) [ $# -ge 2 ] || usage; INTERVAL=$2; shift 2 ;;
        --duration) [ $# -ge 2 ] || usage; DURATION=$2; shift 2 ;;
        *) usage ;;
    esac
done
for v in "$INTERVAL" "$DURATION"; do
    case "$v" in '' | *[!0-9]*) usage ;; esac
done
[ "$INTERVAL" -ge 1 ] || usage
[ -r /proc/meminfo ] && [ -r /proc/uptime ] || { echo "error: /proc/meminfo or /proc/uptime is not readable" >&2; exit 2; }

# One awk pass per sample: the fields checked as numbers, one CSV line or none.
AWK='$1 == "MemTotal:" { t = $2 } $1 == "MemAvailable:" { a = $2 }
END { if (t ~ /^[0-9]+$/ && a ~ /^[0-9]+$/ && a + 0 <= t + 0 && UPT ~ /^[0-9]+(\.[0-9]+)?$/)
          printf "%s,%s,%s,%s,%s,%d\n", TS, EP, UPT, t, a, t - a }'
# /proc/uptime read without a process: UPRAW exactly as written, UP in whole seconds.
uptime_s() { read -r UPRAW _ < /proc/uptime || UPRAW=; UP=${UPRAW%%.*}; }
sample() {
    now=$(date -u '+%s %Y-%m-%dT%H:%M:%SZ')
    uptime_s
    SAMPLE=$(awk -v TS="${now#* }" -v EP="${now%% *}" -v UPT="$UPRAW" "$AWK" /proc/meminfo 2> /dev/null)
}

n=0
stop=0
trap 'stop=1' TERM INT
sample
[ -n "$SAMPLE" ] || { echo "error: no MemTotal/MemAvailable in /proc/meminfo, or no uptime" >&2; exit 2; }
[ -s "$OUT" ] || printf '%s\n' ts_utc,epoch_s,uptime_s,mem_total_kb,mem_available_kb,mem_used_kb > "$OUT" || exit 2
# The closing line is written exactly once, on every exit from here on.
trap 'printf "# end epoch_s=%s samples=%s\n" "$(date -u +%s)" "$n" >> "$OUT"' EXIT
started=$UP
while :; do
    if [ -n "$SAMPLE" ]; then printf '%s\n' "$SAMPLE" >> "$OUT" && n=$((n + 1))
    else echo "${now#* }: MemTotal/MemAvailable/uptime unreadable; no line" >&2; fi
    [ "$stop" -eq 0 ] && sleep "$INTERVAL"
    [ "$stop" -eq 0 ] || break
    uptime_s
    [ "$DURATION" -gt 0 ] && [ $((UP - started)) -ge "$DURATION" ] && break
    sample
done
exit 0
