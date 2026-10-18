#!/bin/sh
# guest_meminfo_sampler.sh — whole-guest memory sampler for the Yocto-vs-Debian
# comparison. Runs ON the guest (busybox ash or dash), never on the host: the
# comparison asks what the whole gateway guest holds in memory under each
# operating system — kernel, init, daemons and the stack together — and only
# the guest kernel's own accounting in /proc/meminfo gives that figure.
# mem_used_kb = MemTotal - MemAvailable: the kernel's estimate of what a new
# workload could not get without swapping (the "used" of free(1), reclaimable
# cache counted as free). It is not the sum of the containers' cgroups.
#
# Appends  ts_utc,epoch_s,mem_total_kb,mem_available_kb,mem_used_kb  lines, the
# header once when OUT_CSV is absent or empty. Each line is one printf, so a
# reader (scp, tail -f) sees a whole line or nothing. On SIGTERM, SIGINT or when
# --duration expires it appends one closing comment line
#   # end epoch_s=<n> samples=<count>
# and exits 0; readers skip lines starting with '#'. A sample whose two fields
# cannot be read writes NO line and one diagnostic on stderr (a hole is evidence,
# a zero would be a claim).
#
# Usage (ON the guest): sh guest_meminfo_sampler.sh OUT_CSV [--interval S] [--duration S]
# interval default 1; duration default 0 = until a signal. Exit 2: OUT_CSV
# missing, a non-integer interval or duration, /proc/meminfo unreadable or
# without the two fields. The duration runs on /proc/uptime (the guest's
# monotonic clock); the wall clock only stamps the lines. POSIX sh + awk as the
# image's busybox 1.36.1 offers them: no arrays, no `date %N`, no `head -N`,
# whole-second `sleep`. The cadence is the interval plus two short processes per
# sample (a little slower than nominal under emulation; the summary tool prints
# the sample count beside every median).
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
[ -r /proc/meminfo ] || { echo "error: /proc/meminfo is not readable" >&2; exit 2; }

# One awk pass per sample: both fields checked as integers, one CSV line or none.
AWK='$1 == "MemTotal:" { t = $2 } $1 == "MemAvailable:" { a = $2 }
END { if (t ~ /^[0-9]+$/ && a ~ /^[0-9]+$/ && a + 0 <= t + 0)
          printf "%s,%s,%s,%s,%d\n", TS, EP, t, a, t - a }'
sample() {
    now=$(date -u '+%s %Y-%m-%dT%H:%M:%SZ')
    SAMPLE=$(awk -v TS="${now#* }" -v EP="${now%% *}" "$AWK" /proc/meminfo 2> /dev/null)
}
# Elapsed seconds on the monotonic clock, read without a process.
uptime_s() { read -r UP _ < /proc/uptime 2> /dev/null || UP=${now%% *}; UP=${UP%%.*}; }

n=0
stop=0
trap 'stop=1' TERM INT
sample
[ -n "$SAMPLE" ] || { echo "error: no MemTotal/MemAvailable in /proc/meminfo" >&2; exit 2; }
[ -s "$OUT" ] || printf '%s\n' ts_utc,epoch_s,mem_total_kb,mem_available_kb,mem_used_kb > "$OUT" || exit 2
# The closing line is written exactly once, on every exit from here on.
trap 'printf "# end epoch_s=%s samples=%s\n" "$(date -u +%s)" "$n" >> "$OUT"' EXIT
uptime_s
started=$UP
while :; do
    if [ -n "$SAMPLE" ]; then printf '%s\n' "$SAMPLE" >> "$OUT" && n=$((n + 1))
    else echo "${now#* }: MemTotal/MemAvailable unreadable; no line" >&2; fi
    [ "$stop" -eq 0 ] && sleep "$INTERVAL"
    [ "$stop" -eq 0 ] || break
    uptime_s
    [ "$DURATION" -gt 0 ] && [ $((UP - started)) -ge "$DURATION" ] && break
    sample
done
exit 0
