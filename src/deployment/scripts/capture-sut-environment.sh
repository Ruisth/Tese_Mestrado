#!/bin/sh
# capture-sut-environment.sh — capture the SUT environment manifest ON the
# ARM VM (the system under test), never on the harness/simulator host
# (audit 2026-08-08 section 9.2: environment.json used to describe the
# load-generator host, i.e. the wrong system).
#
# Writes sut_environment.json with:
#   - uname -a (kernel), /etc/os-release PRETTY_NAME, nproc,
#     CPU model from /proc/cpuinfo, MemTotal from /proc/meminfo,
#     docker --version, docker compose version, date -u (capture time);
#   - the plan 5.1 normative fields passed through the environment:
#       EGW_PROVIDER          e.g. "Hetzner Cloud"
#       EGW_REGION            e.g. "fsn1"
#       EGW_INSTANCE_TYPE     e.g. "CAX21 (4 vCPU ARM64, 8 GiB RAM)"
#       EGW_SHARED_VCPU_NOTE  e.g. "shared vCPU; performance may vary with
#                                   neighbor load" (the mandatory caveat)
#
# The analysis uses "nproc" to normalize docker-stats CPU percentages to
# host-level utilization (audit 9.7):
#   host_cpu_utilization = sum(container cpu_pct) / (100 * nproc)
#
# Usage (ON the VM):
#   EGW_PROVIDER="Hetzner Cloud" EGW_REGION="fsn1" \
#   EGW_INSTANCE_TYPE="CAX21" EGW_SHARED_VCPU_NOTE="shared vCPU" \
#   sh capture-sut-environment.sh [output-file]
#
# Default output: ./sut_environment.json. Fetch it to the harness host and
# pass it to every timed run:
#   scp vm:/opt/egw/sut_environment.json .
#   python -m egw_experiments run --run-id ... --sut-env-from sut_environment.json
# Re-capture whenever the VM changes (resize, kernel update, docker update);
# timed runs WITHOUT this file are marked validity 'invalid'.
#
# POSIX sh; no dependencies beyond coreutils and (optionally) docker.

set -u

OUT=${1:-sut_environment.json}

# Minimal JSON string escaping: backslash and double quote. Values are
# single-line by construction (first line taken, newlines stripped).
json_escape() {
    printf '%s' "$1" | tr -d '\n\r' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

# first_line <command...> — stdout's first line, or empty on failure.
first_line() {
    "$@" 2>/dev/null | head -n 1
}

kernel=$(first_line uname -a)
os_pretty=""
if [ -r /etc/os-release ]; then
    # PRETTY_NAME="Ubuntu 24.04.2 LTS" -> Ubuntu 24.04.2 LTS
    os_pretty=$(sed -n 's/^PRETTY_NAME="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' /etc/os-release | head -n 1)
fi
nproc_val=$(first_line nproc)
cpu_model=$(sed -n 's/^model name[[:space:]]*: *//p' /proc/cpuinfo 2>/dev/null | head -n 1)
if [ -z "$cpu_model" ]; then
    # ARM cores often expose no "model name"; fall back to the CPU part.
    cpu_model=$(sed -n 's/^CPU part[[:space:]]*: *//p' /proc/cpuinfo 2>/dev/null | head -n 1)
fi
mem_total_kb=$(sed -n 's/^MemTotal:[[:space:]]*\([0-9]*\) kB/\1/p' /proc/meminfo 2>/dev/null | head -n 1)
docker_version=$(first_line docker --version)
compose_version=$(first_line docker compose version)
captured_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# nproc must be a bare number or null (the analysis parses it as int).
case "$nproc_val" in
    ''|*[!0-9]*) nproc_json=null ;;
    *) nproc_json=$nproc_val ;;
esac
case "$mem_total_kb" in
    ''|*[!0-9]*) mem_json=null ;;
    *) mem_json=$mem_total_kb ;;
esac

cat > "$OUT" <<EOF
{
  "role": "sut",
  "captured_utc": "$(json_escape "$captured_utc")",
  "uname_a": "$(json_escape "$kernel")",
  "os_pretty_name": "$(json_escape "$os_pretty")",
  "nproc": $nproc_json,
  "cpu_model": "$(json_escape "$cpu_model")",
  "mem_total_kb": $mem_json,
  "docker_version": "$(json_escape "$docker_version")",
  "docker_compose_version": "$(json_escape "$compose_version")",
  "provider": "$(json_escape "${EGW_PROVIDER:-}")",
  "region": "$(json_escape "${EGW_REGION:-}")",
  "instance_type": "$(json_escape "${EGW_INSTANCE_TYPE:-}")",
  "shared_vcpu_note": "$(json_escape "${EGW_SHARED_VCPU_NOTE:-}")"
}
EOF

echo "wrote $OUT" >&2
if [ "$nproc_json" = null ]; then
    echo "WARNING: nproc unavailable; host-level CPU normalization (audit 9.7) will not be possible" >&2
fi
for var in EGW_PROVIDER EGW_REGION EGW_INSTANCE_TYPE EGW_SHARED_VCPU_NOTE; do
    eval "val=\${$var:-}"
    if [ -z "$val" ]; then
        echo "WARNING: $var not set; plan 5.1 requires provider/region/instance/shared-vCPU caveat in the SUT manifest" >&2
    fi
done
