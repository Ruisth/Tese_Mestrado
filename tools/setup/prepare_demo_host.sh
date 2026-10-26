#!/bin/bash
# tools/setup/prepare_demo_host.sh - prepare a fresh WSL2 Ubuntu 24.04 host for the demonstration from the
# demonstration kit (the ZIP built by tools/setup/make_demo_kit.sh) and this clone, with one command.
# Idempotent: a re-run skips every finished step and changes nothing.
#
#   prepare_demo_host.sh --kit <egw-demo-kit-YYYYMMDD.zip> [--no-debian] [--dry-run]
#
#   --kit PATH    the kit ZIP (it may lie under /mnt/c: it is only read); <zip>.sha256 beside it is checked
#   --no-debian   leave out step 10, the one-off Debian 13 preparation (download and first boot)
#   --dry-run     check and report every step and change nothing (no apt, download, file or profile change)
#
# One line per step: OK, SKIP (already done), WOULD (dry run) or STOP: reason.
#    1 host checks      WSL 2, Ubuntu 24.04, the clone on the Linux file system with LF line endings, not
#                       root; refused on a host that already has its own comparison set-up (EGW_* settings
#                       not written by this script, a state root without this script's marker, the
#                       measurement key or the session tooling): this script is for a separate PC or WSL
#                       distribution; the kit ZIP readable, equal to <zip>.sha256 and safely laid out;
#                       warnings below 11 GiB of memory and 25 GB of free disk
#    2 apt packages     the host packages of tools/compare and tools/demo (sudo apt-get, waiting for the
#                       package lists lock and the dpkg lock), then QEMU's CPU and device lists read (help
#                       output only: no guest)
#    3 terraform        1.16.6 into $EGW_COMPARE_ROOT/bin/terraform, checked against HashiCorp's SHA256SUMS
#                       (and, on x86-64, against the sha256 recorded in tools/compare/README.md)
#    4 kit              extraction outside the clone, the kit's SHA256SUMS; the root file system converted
#                       (qemu-img) to the raw ext4 file the yocto scenario reads; the controller archive
#                       checked against its identity record; refused while the yocto scenario's base copy
#                       ($EGW_COMPARE_ROOT/base/yocto) holds another kit's root file system. Keep the ZIP:
#                       a re-run reads it again
#    5 ssh key          the kit's TEST key installed as ~/.ssh/egw_compare_share (mode 600), never over
#                       a different key
#    6 secrets file     the deployment .env made from src/deployment/.env.example with fresh random
#                       passwords (python3 secrets), mode 600, outside the clone; never overwritten, never
#                       printed (only the names of the filled fields are)
#    7 python venv      the project installed from src/ (pip install -e); `import egw_simulator` checked
#    8 settings         ~/.config/egw-demo/env.sh (paths only, no secret) and ONE guarded line that sources
#                       it in the login profile bash reads (~/.bash_profile, ~/.bash_login, else ~/.profile)
#    9 terraform init   tf.sh yocto init and tf.sh debian13 init
#   10 debian 13        EGW_COMPARE_ALLOW_DOWNLOAD=1 compare_env.sh prepare debian13: the dated image checked
#                       against its published SHA512, then one provisioning boot under QEMU (several
#                       minutes, at most EGW_COMPARE_FIRSTBOOT_LIMIT_S, 1800 s by default); refused while any
#                       qemu-system-aarch64 runs, a port of the profile is busy or another scenario's guest
#                       holds the profile's lock; optional (--no-debian)
#   11 summary          the next commands
#
# Locations (environment; all outside the clone and off the Windows file system):
#   EGW_COMPARE_ROOT   the comparison state root (default $HOME/egw-compare), as in tools/compare/lib.sh;
#                      step 3 marks it as this script's with the file .egw-demo-host
#   EGW_KIT_DIR        where the kit is extracted (default $HOME/egw-kit)
#   EGW_DEMO_CONFIG    the settings file and the secrets file (default ${XDG_CONFIG_HOME:-$HOME/.config}/egw-demo)
#   EGW_DEMO_VENV      the virtual environment (default ${XDG_DATA_HOME:-$HOME/.local/share}/egw-demo/venv)
# Transcripts of apt, the downloads, pip, terraform and the Debian preparation:
#   ${XDG_STATE_HOME:-$HOME/.local/state}/egw-demo/setup/
#
# Exit: 0 done; 1 a step failed (apt, download, pip, terraform, Debian preparation); 2 usage or a refused
# check; 3 integrity (a checksum differs, an unexpected kit layout). It never kills a process, starts no
# guest except the Debian provisioning boot of step 10 (through compare_env.sh and its guards), writes in
# the clone only what tf.sh init and pip install -e create there (both ignored by git), and never prints a
# password or a private key.
set -u

SETUP_HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$SETUP_HERE/../.." && pwd -P)

TF_VERSION=1.16.6
TF_URL=https://releases.hashicorp.com/terraform/$TF_VERSION
# sha256 of terraform_1.16.6_linux_amd64.zip as recorded in tools/compare/README.md section 3. On x86-64
# the download must match it AND HashiCorp's SHA256SUMS; on arm64 only the latter is available.
TF_SHA256_LINUX_AMD64=38034b38d03096399a7a1264a14561a8029b2b496fd1f169452656e53968f1b7
# The host packages of tools/compare and tools/demo (tools/setup/README.md says why each is needed).
APT_PACKAGES="qemu-system-arm qemu-utils ipxe-qemu python3 python3-venv unzip curl ca-certificates openssh-client e2fsprogs iproute2 procps git"
# The guest is given 8 GiB. memory=12GB in .wslconfig (tools/setup/README.md) makes WSL report about
# 11.7 GiB, so the warning starts below 11 GiB.
MIN_MEM_KB=$((11 * 1024 * 1024))
MIN_FREE_KB=$((25 * 1000 * 1000 * 1000 / 1024))
CONTROLLER_TAR=egw-controller-0.1.0-arm64.tar
CONTROLLER_RECORD=egw-controller-0.1.0-arm64.identity.txt
KIT_REQUIRED="yoctoScarthgap/yoctoScarthgap.qcow2 yoctoScarthgap/Image yoctoScarthgap/keys/egw_compare_share yoctoScarthgap/keys/egw_compare_share.pub controller/$CONTROLLER_TAR controller/$CONTROLLER_RECORD"
PROFILE_MARK='# egw-demo settings (tools/setup/prepare_demo_host.sh)'
QEMU_EXE_RE='^(\S*/)?qemu-system-aarch64( |$)'
PROFILE_PORTS="2222 8883 8099"
# The file that marks a comparison state root as made by this script (written in step 3).
HOST_MARK=.egw-demo-host
# Settings of tools/compare, tools/demo and the session tooling that a host with its own comparison
# set-up exports; any of them set to a value the settings file of this script does not export refuses.
FOREIGN_VARS="EGW_COMPARE_QEMU EGW_COMPARE_QEMU_IMG EGW_YOCTO_DEPLOY EGW_IMAGES_DIR EGW_COMPARE_SSH_KEY EGW_COMPARE_SECRETS_ENV EGW_EXEC_VENV EGW_EXEC"

COMPARE_ROOT=${EGW_COMPARE_ROOT:-$HOME/egw-compare}
KIT_DIR=${EGW_KIT_DIR:-$HOME/egw-kit}
CONFIG_DIR=${EGW_DEMO_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/egw-demo}
VENV=${EGW_DEMO_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/egw-demo/venv}
LOG_DIR=${XDG_STATE_HOME:-$HOME/.local/state}/egw-demo/setup
SSH_KEY=$HOME/.ssh/egw_compare_share
# Test hooks, used by tools/setup/tests/offline_check.sh only: the files read by step 1, the QEMU
# binaries (the settings file names whatever these resolve to; the defaults are Ubuntu's), the folders
# searched for the virtio network card's ROM, and how long step 2 waits for the package lists lock (the
# pause between tries and the bound on the whole wait, in seconds).
PROC_VERSION=${EGW_SETUP_PROC_VERSION:-/proc/version}
OS_RELEASE=${EGW_SETUP_OS_RELEASE:-/etc/os-release}
MEMINFO=${EGW_SETUP_MEMINFO:-/proc/meminfo}
QEMU=${EGW_SETUP_QEMU:-/usr/bin/qemu-system-aarch64}
QEMU_IMG=${EGW_SETUP_QEMU_IMG:-/usr/bin/qemu-img}
ROM_DIRS=${EGW_SETUP_ROM_DIRS:-/usr/share/qemu /usr/lib/ipxe/qemu}
APT_LOCK_SLEEP_S=${EGW_SETUP_APT_LOCK_SLEEP_S:-10}
APT_LOCK_WAIT_S=${EGW_SETUP_APT_LOCK_WAIT_S:-600}

STEPS=11
CUR=0
CUR_NAME=arguments
KIT=
NO_DEBIAN=0
DRY=0
KIT_TOP=
KIT_NAME=
KIT_SIDECAR=
QEMU_VERSION=

# --- output and small helpers ----------------------------------------------------------------------

step() { CUR=$1; CUR_NAME=$2; }
report() { printf '[%s/%s] %s: %s\n' "$CUR" "$STEPS" "$CUR_NAME" "$*"; }
note() { printf '       %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*"; }
stop() {
    local code=$1
    shift
    printf '[%s/%s] %s: STOP: %s\n' "$CUR" "$STEPS" "$CUR_NAME" "$*" >&2
    exit "$code"
}
usage() { awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"; }
usage_stop() {
    printf 'STOP: %s\nusage: prepare_demo_host.sh --kit <egw-demo-kit-YYYYMMDD.zip> [--no-debian] [--dry-run] (--help)\n' "$1" >&2
    exit 2
}
# shq TEXT: TEXT as one POSIX single-quoted word (the settings file is read by sh as well as bash).
shq() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
sha256_of() { sha256sum "$1" | cut -d' ' -f1; }
# under PATH DIR: 0 when PATH is DIR or lies below it.
under() { case "$1/" in "$2"/*) return 0 ;; esac; return 1; }
new_log() {
    mkdir -p "$LOG_DIR" || stop 1 "cannot create $LOG_DIR"
    printf '%s/%s-%s.log' "$LOG_DIR" "$1" "$(date -u +%Y%m%dT%H%M%SZ)"
}
# tail_of LOG: the last lines of a transcript, indented (tool output only; nothing secret goes there).
tail_of() { tail -n "${2:-8}" "$1" 2> /dev/null | sed 's/^/       | /' >&2; }

parse_args() {
    while [ $# -gt 0 ]; do
        case $1 in
            --kit)
                [ $# -ge 2 ] && [ -n "$2" ] || usage_stop "--kit needs the path of the kit ZIP"
                KIT=$2
                shift 2
                ;;
            --kit=*) KIT=${1#--kit=}; shift ;;
            --no-debian) NO_DEBIAN=1; shift ;;
            --dry-run) DRY=1; shift ;;
            -h | --help) usage; exit 0 ;;
            *) usage_stop "unknown argument: $1" ;;
        esac
    done
    [ -n "$KIT" ] || usage_stop "--kit <zip> is required"
    KIT=$(realpath -m -- "$KIT")
    COMPARE_ROOT=$(realpath -m -- "$COMPARE_ROOT")
    KIT_DIR=$(realpath -m -- "$KIT_DIR")
    CONFIG_DIR=$(realpath -m -- "$CONFIG_DIR")
    VENV=$(realpath -m -- "$VENV")
    SETTINGS=$CONFIG_DIR/env.sh
    SECRETS=$CONFIG_DIR/deployment.env
}

# --- 1. host checks --------------------------------------------------------------------------------

# fs_type PATH: the type of the file system that holds PATH (or, when PATH does not exist yet, its
# nearest existing parent), as findmnt reports it; stat -f when findmnt has no answer.
fs_type() {
    local p=$1 t
    while [ ! -e "$p" ] && [ "$p" != / ]; do p=$(dirname "$p"); done
    t=$(findmnt -n -o FSTYPE -T "$p" 2> /dev/null | head -n 1)
    [ -n "$t" ] || t=$(stat -f -c %T "$p" 2> /dev/null)
    printf '%s' "$t"
}
# windows_fs PATH: 0 when PATH lies on a Windows drive as WSL mounts it (9p, drvfs or virtiofs), wherever
# /etc/wsl.conf puts the drives (the /mnt prefix is checked separately).
windows_fs() {
    case $(fs_type "$1") in 9p | v9fs | drvfs | virtiofs) return 0 ;; esac
    return 1
}

# foreign_setup: stop when this host already has its own comparison set-up (the author's measurement
# host, for example). This script would take it over for every later login shell: Ubuntu's QEMU, the
# test key and new passwords in place of the measured set-up. Settings that the settings file of this
# script exports with the same value, and a state root carrying this script's marker, pass.
foreign_setup() {
    local n v why="this host has its own comparison set-up; prepare_demo_host.sh is for a separate PC or WSL distribution"
    for n in $FOREIGN_VARS; do
        v=${!n:-}
        [ -n "$v" ] || continue
        grep -qxF -- "export $n=$(shq "$v")" "$SETTINGS" 2> /dev/null || stop 2 "$n is already set ($v): $why"
    done
    if [ -e "$COMPARE_ROOT" ] && [ ! -e "$COMPARE_ROOT/$HOST_MARK" ]; then
        [ -d "$COMPARE_ROOT" ] || stop 2 "$COMPARE_ROOT exists and is not a folder"
        [ -z "$(ls -A "$COMPARE_ROOT" 2> /dev/null)" ] || stop 2 "$COMPARE_ROOT holds a comparison state this script did not make (no $HOST_MARK): $why"
    fi
    for v in "$HOME/.ssh/egw_campaign" "${EGW_EXEC:-$HOME/egw-exec}"; do
        [ ! -e "$v" ] || stop 2 "$v exists (the measurement key or the session tooling): $why"
    done
}

# kit_precheck: the kit ZIP readable, equal to <zip>.sha256 when that file is present, and laid out as one
# top folder egw-demo-kit-YYYYMMDD (KIT_NAME; KIT_SIDECAR says whether the .sha256 was checked). Read
# only, so that a wrong or damaged ZIP is found in step 1, before anything is installed.
kit_precheck() {
    local want got
    [ -f "$KIT" ] && [ -r "$KIT" ] || stop 2 "kit not found or not readable: $KIT"
    if [ -r "$KIT.sha256" ]; then
        want=$(awk 'NR == 1 { print $1 }' "$KIT.sha256")
        got=$(sha256_of "$KIT")
        [ "$want" = "$got" ] || stop 3 "$KIT does not match $KIT.sha256 (a damaged or different file)"
        KIT_SIDECAR=present
    else
        KIT_SIDECAR=absent
        warn "no $KIT.sha256 beside the kit: the zip as a whole is not checked (its SHA256SUMS still is)"
    fi
    KIT_NAME=$(kit_listing "$KIT") || stop 3 "$KIT_NAME"
}

step_host() {
    step 1 "host checks"
    local v os mem_kb free_kb d f
    v=$(cat "$PROC_VERSION" 2> /dev/null) || stop 2 "cannot read $PROC_VERSION"
    # WSL 2 kernels say 'microsoft' in lower case (...-microsoft-standard-WSL2); WSL 1 says 'Microsoft'.
    case $v in
        *microsoft*) ;;
        *Microsoft*) stop 2 "this is WSL 1; QEMU needs WSL 2 (in Windows: wsl --set-version Ubuntu-24.04 2)" ;;
        *) stop 2 "not a WSL 2 kernel ($PROC_VERSION does not mention microsoft): this script prepares a WSL2 Ubuntu 24.04 host" ;;
    esac
    # shellcheck disable=SC1090
    os=$( (. "$OS_RELEASE" && printf '%s %s' "${ID:-}" "${VERSION_ID:-}") 2> /dev/null)
    [ "$os" = "ubuntu 24.04" ] || stop 2 "the distribution is '${os:-unknown}', not Ubuntu 24.04 ($OS_RELEASE); install it in Windows with: wsl --install -d Ubuntu-24.04"
    case "$REPO/" in
        /mnt/*) stop 2 "the clone is on the Windows file system ($REPO); clone or copy it into your WSL home (for example ~/egw) and run it from there" ;;
    esac
    if windows_fs "$REPO"; then
        stop 2 "the clone is on a Windows drive ($REPO, file system $(fs_type "$REPO")); clone or copy it into your WSL home (for example ~/egw) and run it from there"
    fi
    for f in tools/compare/tf.sh tools/compare/compare_env.sh tools/compare/lib.sh tools/compare/scenarios/yocto.env src/deployment/.env.example src/pyproject.toml; do
        [ -f "$REPO/$f" ] || stop 2 "$REPO is not a complete clone of the project ($f missing)"
    done
    for f in tools/compare/compare_env.sh tools/compare/lib.sh tools/compare/scenarios/yocto.env; do
        if grep -q $'\r' "$REPO/$f"; then
            stop 2 "$REPO/$f has Windows (CRLF) line endings; clone the repository inside WSL (git clone), not with Git for Windows"
        fi
    done
    for d in "$COMPARE_ROOT" "$KIT_DIR" "$CONFIG_DIR" "$VENV"; do
        case "$d/" in /mnt/*) stop 2 "$d is on the Windows file system; keep every location under your WSL home" ;; esac
        if windows_fs "$d"; then stop 2 "$d is on a Windows drive (file system $(fs_type "$d")); keep every location under your WSL home"; fi
        if under "$d" "$REPO" || under "$REPO" "$d"; then stop 2 "$d overlaps the clone ($REPO); the scripts keep their state outside it"; fi
    done
    [ "$(id -u)" != 0 ] || stop 2 "run it as your normal WSL user, not as root (it calls sudo for apt only)"
    foreign_setup
    kit_precheck
    mem_kb=$(awk '/^MemTotal:/ { print $2; exit }' "$MEMINFO" 2> /dev/null)
    case $mem_kb in '' | *[!0-9]*) mem_kb=0 ;; esac
    if [ "$mem_kb" -lt "$MIN_MEM_KB" ]; then
        warn "WSL has $(awk -v k="$mem_kb" 'BEGIN { printf "%.1f", k / 1048576 }') GiB of memory, below 11 GiB; the guest is given 8 GiB. Raise WSL's limit in Windows: %UserProfile%\\.wslconfig with '[wsl2]' and 'memory=12GB', then 'wsl --shutdown'"
    fi
    free_kb=$(df -Pk "$HOME" 2> /dev/null | awk 'NR == 2 { print $4 }')
    case $free_kb in '' | *[!0-9]*) free_kb=0 ;; esac
    if [ "$free_kb" -lt "$MIN_FREE_KB" ]; then
        warn "$(awk -v k="$free_kb" 'BEGIN { printf "%.1f", k * 1024 / 1e9 }') GB free under $HOME, below about 25 GB (images, the Debian base, the data disks and the container images)"
    fi
    report "OK (WSL 2, Ubuntu 24.04, clone $REPO, no other comparison set-up, $(awk -v k="$mem_kb" 'BEGIN { printf "%.1f", k / 1048576 }') GiB memory, $(awk -v k="$free_kb" 'BEGIN { printf "%.0f", k * 1024 / 1e9 }') GB free; kit $KIT_NAME, zip .sha256 $KIT_SIDECAR)"
}

# --- 2. apt packages -------------------------------------------------------------------------------

pkg_missing() {
    local p m=
    for p in $APT_PACKAGES; do
        dpkg-query -W -f='${Status}' "$p" 2> /dev/null | grep -q 'install ok installed' || m="$m $p"
    done
    printf '%s' "${m# }"
}

# qemu_check: the machine profile of tools/compare/lib.sh needs the cortex-a76 CPU and four virtio devices;
# both lists are read from QEMU's help output (no guest is started).
qemu_check() {
    local devs d miss=
    [ -x "$QEMU" ] && [ -x "$QEMU_IMG" ] || stop 2 "$QEMU or $QEMU_IMG is missing"
    QEMU_VERSION=$("$QEMU" --version 2> /dev/null | head -n 1)
    "$QEMU" -cpu help 2> /dev/null | grep -qw cortex-a76 || stop 2 "${QEMU_VERSION:-$QEMU} does not offer the cortex-a76 CPU of the machine profile"
    devs=$("$QEMU" -device help 2> /dev/null)
    for d in virtio-net-pci virtio-blk-pci virtio-rng-pci virtio-gpu-pci; do
        printf '%s\n' "$devs" | grep -q "\"$d\"" || miss="$miss $d"
    done
    [ -z "$miss" ] || stop 2 "${QEMU_VERSION:-$QEMU} lacks the device(s):$miss"
    # the ROM of the virtio-net-pci card: Ubuntu 24.04's ipxe-qemu installs it in /usr/lib/ipxe/qemu, which is
    # on QEMU's firmware path; other builds keep it in /usr/share/qemu
    for d in $ROM_DIRS; do [ -e "$d/efi-virtio.rom" ] && return 0; done
    warn "efi-virtio.rom (package ipxe-qemu) is in none of: $ROM_DIRS; QEMU may refuse the virtio-net-pci card"
}

# apt_update LOG: sudo apt-get update, appended to LOG. DPkg::Lock::Timeout covers the dpkg lock only, not
# /var/lib/apt/lists/lock that 'update' takes, which apt-daily holds while it refreshes the lists on a
# fresh install: while the output says 'Could not get lock', it is run again every APT_LOCK_SLEEP_S
# seconds, for at most APT_LOCK_WAIT_S seconds in all. Any other failure returns at once. LC_ALL=C keeps
# that message in English.
apt_update() {
    local log=$1 start=$SECONDS out rc said=0
    while :; do
        out=$(sudo env DEBIAN_FRONTEND=noninteractive LC_ALL=C apt-get -o DPkg::Lock::Timeout=600 update 2>&1)
        rc=$?
        printf '%s\n' "$out" >> "$log"
        [ "$rc" != 0 ] || return 0
        case $out in *"Could not get lock"*) ;; *) return "$rc" ;; esac
        [ $((SECONDS - start + APT_LOCK_SLEEP_S)) -le "$APT_LOCK_WAIT_S" ] || return "$rc"
        [ "$said" = 1 ] || note "another apt holds the package lists lock: trying again every $APT_LOCK_SLEEP_S s, for at most $APT_LOCK_WAIT_S s"
        said=1
        sleep "$APT_LOCK_SLEEP_S"
    done
}

step_apt() {
    step 2 "apt packages"
    local missing log
    local -a pkgs
    missing=$(pkg_missing)
    if [ -z "$missing" ]; then
        qemu_check
        report "SKIP (all installed; ${QEMU_VERSION:-QEMU} offers cortex-a76 and the virtio devices)"
        return 0
    fi
    if [ "$DRY" = 1 ]; then
        report "WOULD install with sudo apt-get: $missing"
        return 0
    fi
    command -v sudo > /dev/null 2>&1 || stop 2 "sudo is missing; as root run: apt-get install $missing"
    read -r -a pkgs <<< "$missing"
    log=$(new_log apt)
    note "installing with sudo apt-get (sudo may ask for your password): $missing"
    # 'sudo true', not 'sudo -v': 'sudo -v' asks for a password whenever any sudoers rule needs one, even
    # for a user allowed to run every command without one, and would wait for a password nobody types
    sudo true || stop 1 "sudo refused"
    # On a fresh install apt-daily or unattended-upgrades may hold the package lists lock or the dpkg
    # lock: wait for each (10 minutes) instead of failing at once.
    { apt_update "$log" \
        && sudo env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y "${pkgs[@]}" >> "$log" 2>&1; } \
        || { tail_of "$log"; stop 1 "apt-get failed; see $log"; }
    missing=$(pkg_missing)
    [ -z "$missing" ] || stop 1 "still not installed: $missing; see $log"
    qemu_check
    report "OK (installed: ${pkgs[*]}; ${QEMU_VERSION:-QEMU} offers cortex-a76 and the virtio devices; log $log)"
}

# --- 3. terraform ----------------------------------------------------------------------------------

tf_version_of() { CHECKPOINT_DISABLE=1 "$1" version 2> /dev/null | head -n 1; }

# mark_root: the marker that tells step 1 of a later run that $COMPARE_ROOT is this script's.
mark_root() {
    [ -e "$COMPARE_ROOT/$HOST_MARK" ] && return 0
    printf 'Comparison state root of a host prepared for the demonstration by tools/setup/prepare_demo_host.sh.\n' \
        > "$COMPARE_ROOT/$HOST_MARK" || stop 1 "cannot write $COMPARE_ROOT/$HOST_MARK"
}

step_terraform() {
    step 3 "terraform"
    local tf=$COMPARE_ROOT/bin/terraform arch zip tmp log line got
    if [ -e "$tf" ]; then
        got=$(tf_version_of "$tf")
        [ "$got" = "Terraform v$TF_VERSION" ] || stop 2 "$tf is '${got:-unreadable}', not Terraform v$TF_VERSION; move it away and run again"
        report "SKIP ($tf is Terraform v$TF_VERSION)"
        return 0
    fi
    case $(uname -m) in
        x86_64) arch=amd64 ;;
        aarch64) arch=arm64 ;;
        *) stop 2 "no Terraform build for this machine ($(uname -m))" ;;
    esac
    zip=terraform_${TF_VERSION}_linux_${arch}.zip
    if [ "$DRY" = 1 ]; then
        report "WOULD download $TF_URL/$zip and its SHA256SUMS, verify and install $tf"
        return 0
    fi
    mkdir -p "$COMPARE_ROOT/bin" || stop 1 "cannot create $COMPARE_ROOT/bin"
    mark_root
    # A download folder left by an interrupted run (Ctrl+C) is removed first.
    rm -rf "$COMPARE_ROOT/bin"/.download.*
    tmp=$(mktemp -d "$COMPARE_ROOT/bin/.download.XXXXXX") || stop 1 "cannot create a download folder"
    log=$(new_log terraform-download)
    if ! curl -fsSL --retry 3 --retry-delay 5 -o "$tmp/$zip" "$TF_URL/$zip" >> "$log" 2>&1 \
        || ! curl -fsSL --retry 3 --retry-delay 5 -o "$tmp/SHA256SUMS" "$TF_URL/terraform_${TF_VERSION}_SHA256SUMS" >> "$log" 2>&1; then
        rm -rf "$tmp"
        stop 1 "download from $TF_URL failed; see $log"
    fi
    line=$(grep -E "^[0-9a-f]{64}  $zip\$" "$tmp/SHA256SUMS")
    if [ -z "$line" ] || ! (cd "$tmp" && printf '%s\n' "$line" | sha256sum -c --quiet --strict - > /dev/null 2>&1); then
        rm -rf "$tmp"
        stop 3 "$zip does not match HashiCorp's SHA256SUMS"
    fi
    if [ "$arch" = amd64 ] && [ "$(sha256_of "$tmp/$zip")" != "$TF_SHA256_LINUX_AMD64" ]; then
        rm -rf "$tmp"
        stop 3 "$zip does not match the sha256 recorded in tools/compare/README.md ($TF_SHA256_LINUX_AMD64)"
    fi
    if ! unzip -q -o "$tmp/$zip" terraform -d "$tmp" >> "$log" 2>&1 || ! chmod 0755 "$tmp/terraform"; then
        rm -rf "$tmp"
        stop 1 "unzip of $zip failed; see $log"
    fi
    got=$(tf_version_of "$tmp/terraform")
    if [ "$got" != "Terraform v$TF_VERSION" ]; then
        rm -rf "$tmp"
        stop 3 "the downloaded binary reports '${got:-nothing}'"
    fi
    mv "$tmp/terraform" "$tf" || stop 1 "cannot install $tf"
    rm -rf "$tmp"
    report "OK ($tf, Terraform v$TF_VERSION, $zip verified)"
}

# --- 4. kit ----------------------------------------------------------------------------------------

# kit_listing ZIP: print the zip's single top folder egw-demo-kit-YYYYMMDD; print the reason and return 3
# when an entry is absolute, climbs out (..), is a symbolic link or lies outside that one folder.
kit_listing() {
    python3 -I - "$1" << 'PY'
import re
import stat
import sys
import zipfile

try:
    zf = zipfile.ZipFile(sys.argv[1])
except (OSError, zipfile.BadZipFile) as exc:
    print(f"not a readable zip ({exc.__class__.__name__})")
    sys.exit(3)
tops = set()
for info in zf.infolist():
    name = info.filename
    parts = name.split("/")
    if not name or name.startswith("/") or "\\" in name or ".." in parts or re.match(r"^[A-Za-z]:", name):
        print(f"unsafe entry name in the zip: {name!r}")
        sys.exit(3)
    if stat.S_ISLNK(info.external_attr >> 16):
        print(f"symbolic link in the zip: {name!r}")
        sys.exit(3)
    tops.add(parts[0] if len(parts) > 1 else "/" + parts[0])
if len(tops) != 1 or not re.fullmatch(r"egw-demo-kit-[0-9]{8}", next(iter(tops))):
    print("the zip must hold exactly one top folder egw-demo-kit-YYYYMMDD/ (found: " + ", ".join(sorted(tops)) + ")")
    sys.exit(3)
print(next(iter(tops)))
PY
}

# kit_check_sums TOP: the kit's SHA256SUMS lists the required files, every listed file verifies and no
# file is unlisted (deploy/, which step 4 derives, and yoctoScarthgap/work/, where the package's own
# run-linux.sh keeps its overlays, excepted). Prints the reason and returns 3 otherwise.
kit_check_sums() {
    local top=$1 f out unlisted
    [ -s "$top/SHA256SUMS" ] || { echo "$top has no SHA256SUMS"; return 3; }
    for f in $KIT_REQUIRED; do
        awk -v r="$f" '{ p = substr($0, 67); sub(/^\.\//, "", p) } p == r { found = 1 } END { exit !found }' "$top/SHA256SUMS" \
            || { echo "the kit's SHA256SUMS does not list $f"; return 3; }
    done
    if ! out=$(cd "$top" && sha256sum -c --quiet --strict SHA256SUMS 2>&1); then
        echo "files of the kit do not match its SHA256SUMS: $(printf '%s\n' "$out" | sed -n 's/: FAILED.*$//p; s/^sha256sum: //p' | head -n 5 | tr '\n' ' ')"
        return 3
    fi
    unlisted=$(cd "$top" && find . -type f ! -path ./SHA256SUMS ! -path './deploy/*' ! -path './yoctoScarthgap/work/*' | sed 's|^\./||' | LC_ALL=C sort \
        | LC_ALL=C comm -23 - <(awk '{ p = substr($0, 67); sub(/^\.\//, "", p); print p }' SHA256SUMS | LC_ALL=C sort))
    [ -z "$unlisted" ] || { echo "files not listed in the kit's SHA256SUMS: $(printf '%s ' $unlisted)"; return 3; }
    return 0
}

# controller_check DIR: the archive matches its identity record, as provision_stack.sh requires.
controller_check() {
    local d=$1 rec
    [ -s "$d/$CONTROLLER_TAR" ] && [ -s "$d/$CONTROLLER_RECORD" ] || { echo "$d lacks $CONTROLLER_TAR or $CONTROLLER_RECORD"; return 3; }
    rec=$(sed -n 's/^archive_sha256=//p' "$d/$CONTROLLER_RECORD" | head -n 1)
    [ -n "$rec" ] || { echo "the identity record has no archive_sha256 line"; return 3; }
    [ "$(sha256_of "$d/$CONTROLLER_TAR")" = "$rec" ] || { echo "the controller archive does not match its identity record"; return 3; }
    grep -q '^source_tree_state=clean$' "$d/$CONTROLLER_RECORD" || { echo "the identity record is not from a clean build context"; return 3; }
}

# yocto_targets DIR: the two files the yocto scenario reads (BASE_ROOTFS_SRC, BASE_KERNEL_SRC) when
# EGW_YOCTO_DEPLOY=DIR, taken from tools/compare/scenarios/yocto.env itself, so its exact names are used.
yocto_targets() {
    (
        EGW_YOCTO_DEPLOY=$1
        # shellcheck disable=SC1091
        . "$REPO/tools/compare/scenarios/yocto.env" > /dev/null 2>&1
        printf '%s\n%s\n' "${BASE_ROOTFS_SRC:-}" "${BASE_KERNEL_SRC:-}"
    )
}

# kit_deploy TOP: the deploy folder TOP/deploy with the raw ext4 root file system (converted from the
# kit's compressed qcow2) and the kernel, under the names the yocto scenario reads; recorded in
# deploy/SHA256SUMS and deploy/SOURCE.txt. Sets DEPLOY_STATE (present, converted, would) and, when it
# returns non-zero, DEPLOY_MSG (the reason). Called directly, never in $(...), so that both survive.
DEPLOY_STATE=
DEPLOY_MSG=
deploy_fail() { DEPLOY_MSG=$2; return "$1"; }
kit_deploy() {
    local top=$1 dep=$1/deploy src=$1/yoctoScarthgap/yoctoScarthgap.qcow2 rootfs kernel want
    DEPLOY_STATE=
    DEPLOY_MSG=
    { read -r rootfs; read -r kernel; } < <(yocto_targets "$dep")
    if [ "$(dirname "${rootfs:-/}")" != "$dep" ] || [ "$(dirname "${kernel:-/}")" != "$dep" ]; then
        deploy_fail 3 "tools/compare/scenarios/yocto.env no longer reads its base from \$EGW_YOCTO_DEPLOY"
        return
    fi
    want=$(sha256_of "$src")
    if [ -s "$dep/SHA256SUMS" ] && [ -s "$rootfs" ] && [ -s "$kernel" ] \
        && grep -qx "source_qcow2_sha256=$want" "$dep/SOURCE.txt" 2> /dev/null \
        && (cd "$dep" && sha256sum -c --quiet --strict SHA256SUMS > /dev/null 2>&1); then
        DEPLOY_STATE=present
        return 0
    fi
    if [ "$DRY" = 1 ]; then
        DEPLOY_STATE=would
        return 0
    fi
    [ -x "$QEMU_IMG" ] || { deploy_fail 2 "qemu-img missing: $QEMU_IMG"; return; }
    mkdir -p "$dep" || { deploy_fail 1 "cannot create $dep"; return; }
    rm -f "$rootfs" "$rootfs.part" "$kernel" "$kernel.part" "$dep/SHA256SUMS" "$dep/SOURCE.txt"
    if ! "$QEMU_IMG" convert -f qcow2 -O raw "$src" "$rootfs.part" > /dev/null; then
        rm -f "$rootfs.part"
        deploy_fail 1 "qemu-img convert failed"
        return
    fi
    # ext4 superblock magic 0xEF53 at byte 1080 (offset 56 of the superblock at 1024): no partition table.
    if [ "$(od -An -tx1 -j1080 -N2 "$rootfs.part" | tr -d ' \n')" != 53ef ]; then
        rm -f "$rootfs.part"
        deploy_fail 3 "the converted root file system is not an unpartitioned ext4"
        return
    fi
    mv "$rootfs.part" "$rootfs" && chmod 0444 "$rootfs" || { deploy_fail 1 "cannot write $rootfs"; return; }
    cp "$top/yoctoScarthgap/Image" "$kernel.part" && mv "$kernel.part" "$kernel" && chmod 0444 "$kernel" || { deploy_fail 1 "cannot write $kernel"; return; }
    (cd "$dep" && sha256sum "$(basename "$rootfs")" "$(basename "$kernel")" > SHA256SUMS) || { deploy_fail 1 "cannot write $dep/SHA256SUMS"; return; }
    printf 'kit=%s\nsource_qcow2=yoctoScarthgap/yoctoScarthgap.qcow2\nsource_qcow2_sha256=%s\nconverted_utc=%s\nqemu_img=%s\n' \
        "$(basename "$top")" "$want" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$("$QEMU_IMG" --version 2> /dev/null | head -n 1)" > "$dep/SOURCE.txt"
    DEPLOY_STATE=converted
}

# base_check DEP: compare_env.sh copies the yocto scenario's base once into $COMPARE_ROOT/base/yocto
# (base_copy: rootfs.ext4, then never refreshed) and records it in that folder's SHA256SUMS (base_seal).
# Stop when that record names another root file system than the one in DEP (as DEP/SHA256SUMS records
# it): the settings would name this kit while tf.sh kept booting the earlier kit's image.
base_check() {
    local dep=$1 rootfs base new
    base=$(awk '$2 == "rootfs.ext4" { print $1 }' "$COMPARE_ROOT/base/yocto/SHA256SUMS" 2> /dev/null | head -n 1)
    [ -n "$base" ] || return 0
    rootfs=$(yocto_targets "$dep" | head -n 1)
    new=$(awk -v f="$(basename "$rootfs")" '$2 == f { print $1 }' "$dep/SHA256SUMS" 2> /dev/null | head -n 1)
    [ "$base" = "$new" ] && return 0
    stop 2 "$COMPARE_ROOT/base/yocto holds the root file system of another kit (rootfs.ext4 ${base:0:12}..., this kit's ${new:0:12}...), and tools/compare never replaces a base copy: run 'bash tools/compare/tf.sh yocto destroy', remove $COMPARE_ROOT/base/yocto and run this script again"
}

# zip_member ZIP NAME: the bytes of one member of ZIP on standard output (python3: no unzip needed).
zip_member() {
    python3 -I -c 'import sys, zipfile; sys.stdout.buffer.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]))' "$1" "$2" 2> /dev/null
}

step_kit() {
    step 4 "kit"
    local name msg rc tmp extracted=present
    # Checked in step 1 already; called here too when step 4 runs alone (the offline check).
    [ -n "$KIT_NAME" ] || kit_precheck
    name=$KIT_NAME
    KIT_TOP=$KIT_DIR/$name
    if [ -e "$KIT_TOP" ]; then
        msg=$(kit_check_sums "$KIT_TOP") || stop 3 "$KIT_TOP exists but does not verify: $msg. Move that folder away and run again"
        # The same date may stamp another build: the folder must hold the kit given now, not an older one.
        zip_member "$KIT" "$name/SHA256SUMS" | cmp -s - "$KIT_TOP/SHA256SUMS" \
            || stop 3 "$KIT_TOP holds a different kit than $KIT; move that folder away and run again"
    elif [ "$DRY" = 1 ]; then
        extracted=would
    else
        mkdir -p "$KIT_DIR" || stop 1 "cannot create $KIT_DIR"
        # An extraction folder left by an interrupted run (Ctrl+C) is removed first.
        rm -rf "$KIT_DIR"/.extract.*
        tmp=$(mktemp -d "$KIT_DIR/.extract.XXXXXX") || stop 1 "cannot create a folder in $KIT_DIR"
        if ! unzip -q "$KIT" -d "$tmp" < /dev/null > /dev/null 2>&1; then
            rm -rf "$tmp"
            stop 3 "unzip of $KIT failed"
        fi
        if ! msg=$(kit_check_sums "$tmp/$name"); then
            rm -rf "$tmp"
            stop 3 "$msg"
        fi
        mv "$tmp/$name" "$KIT_TOP" && rmdir "$tmp" || stop 1 "cannot move the kit into $KIT_TOP"
        extracted="done"
    fi
    if [ "$extracted" = would ]; then
        report "WOULD extract $name into $KIT_DIR, verify its SHA256SUMS, convert the root file system into $KIT_TOP/deploy and check the controller archive"
        return 0
    fi
    msg=$(controller_check "$KIT_TOP/controller") || stop 3 "$msg"
    kit_deploy "$KIT_TOP"
    rc=$?
    [ "$rc" = 0 ] || stop "$rc" "$DEPLOY_MSG"
    [ "$DEPLOY_STATE" = would ] || base_check "$KIT_TOP/deploy"
    if [ "$extracted" = present ] && [ "$DEPLOY_STATE" = present ]; then
        report "SKIP ($KIT_TOP verified; deploy/ holds the converted root file system; controller archive matches its record)"
    elif [ "$DEPLOY_STATE" = would ]; then
        report "WOULD convert the root file system into $KIT_TOP/deploy (kit verified, controller archive matches its record)"
    else
        report "OK ($name: zip .sha256 $KIT_SIDECAR, SHA256SUMS verified, extracted $extracted, root file system $DEPLOY_STATE in $KIT_TOP/deploy, controller archive matches its record)"
    fi
}

# --- 5. ssh key ------------------------------------------------------------------------------------

step_ssh_key() {
    step 5 "ssh key"
    local src=$KIT_TOP/yoctoScarthgap/keys/egw_compare_share
    if [ ! -s "$src" ]; then
        [ "$DRY" = 1 ] || stop 3 "the kit has no test key ($src)"
        if [ -e "$SSH_KEY" ]; then report "WOULD compare $SSH_KEY with the kit's test key"; else report "WOULD install the kit's test key as $SSH_KEY (mode 600)"; fi
        return 0
    fi
    if [ -e "$SSH_KEY" ] || [ -e "$SSH_KEY.pub" ]; then
        cmp -s "$src" "$SSH_KEY" && cmp -s "$src.pub" "$SSH_KEY.pub" \
            || stop 2 "$SSH_KEY (or .pub) exists and differs from the kit's test key; it is never overwritten"
        if [ "$(stat -c %a "$SSH_KEY")" != 600 ]; then
            [ "$DRY" = 1 ] && { report "WOULD set mode 600 on $SSH_KEY"; return 0; }
            chmod 600 "$SSH_KEY" || stop 1 "chmod 600 $SSH_KEY failed"
            report "OK ($SSH_KEY present; mode set to 600)"
            return 0
        fi
        report "SKIP ($SSH_KEY is the kit's test key, mode 600)"
        return 0
    fi
    [ "$DRY" = 1 ] && { report "WOULD install the kit's test key as $SSH_KEY (mode 600)"; return 0; }
    if [ ! -d "$HOME/.ssh" ]; then
        mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh" || stop 1 "cannot create $HOME/.ssh"
    fi
    (umask 077 && cp "$src" "$SSH_KEY.part" && chmod 600 "$SSH_KEY.part" && mv "$SSH_KEY.part" "$SSH_KEY") || stop 1 "cannot write $SSH_KEY"
    (cp "$src.pub" "$SSH_KEY.pub.part" && chmod 644 "$SSH_KEY.pub.part" && mv "$SSH_KEY.pub.part" "$SSH_KEY.pub") || stop 1 "cannot write $SSH_KEY.pub"
    report "OK ($SSH_KEY and .pub installed: a TEST key authorised only in the kit's image and the Debian guest made here)"
}

# --- 6. secrets file -------------------------------------------------------------------------------

# secrets_problem FILE: why FILE cannot serve as the deployment .env (provision_stack.sh's own rules:
# the four names assigned, no CHANGE_ME outside comments); nothing when it can. No value is read here.
secrets_problem() {
    local f=$1 n
    [ -r "$f" ] || { echo "it is not readable"; return 0; }
    [ "$(grep -v '^[[:space:]]*#' "$f" | grep -c CHANGE_ME)" = 0 ] || { echo "it still carries a CHANGE_ME placeholder"; return 0; }
    for n in MOSQUITTO_SIMULATOR_PASSWORD MOSQUITTO_CONTROLLER_PASSWORD EGW_MQTT_PASSWORD DITTO_DEVOPS_PASSWORD; do
        grep -Eq "^$n=.+" "$f" || { echo "it has no $n assignment"; return 0; }
    done
}

# secrets_generate TEMPLATE OUT: OUT made from TEMPLATE with a fresh random value (32 letters and digits,
# python3 secrets) for every password field that holds a CHANGE_ME placeholder; EGW_MQTT_PASSWORD takes
# the value of MOSQUITTO_CONTROLLER_PASSWORD (the template says they MUST be equal). OUT is created
# exclusively with mode 600. Prints the names of the filled fields, never a value.
secrets_generate() {
    python3 -I - "$1" "$2" << 'PY'
import os
import re
import secrets
import string
import sys
from datetime import datetime, timezone

template, out = sys.argv[1], sys.argv[2]
ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
ALPHABET = string.ascii_letters + string.digits
SAME_AS = {"EGW_MQTT_PASSWORD": "MOSQUITTO_CONTROLLER_PASSWORD"}


def fresh():
    return "".join(secrets.choice(ALPHABET) for _ in range(32))


with open(template, encoding="utf-8") as fh:
    lines = fh.read().splitlines()
placeholders = [m.group(1) for m in map(ASSIGN.match, lines) if m and "CHANGE_ME" in m.group(2)]
odd = [n for n in placeholders if "PASSWORD" not in n]
if odd:
    print("placeholder in a field that is not a password: " + ", ".join(odd), file=sys.stderr)
    sys.exit(3)
values = {n: fresh() for n in placeholders if n not in SAME_AS}
for name, source in SAME_AS.items():
    if name in placeholders:
        if source not in values:
            print(f"{name} must equal {source}, which the template does not hold", file=sys.stderr)
            sys.exit(3)
        values[name] = values[source]
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
body = [f"# Generated by tools/setup/prepare_demo_host.sh on {stamp} from src/deployment/.env.example:",
        "# fresh random passwords for this PC only. Never commit, share or print this file."]
for line in lines:
    m = ASSIGN.match(line)
    body.append(f"{m.group(1)}={values[m.group(1)]}" if m and m.group(1) in values else line)
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(body) + "\n")
print(" ".join(sorted(values)))
PY
}

step_secrets() {
    step 6 "secrets file"
    local why names
    if [ -e "$SECRETS" ]; then
        why=$(secrets_problem "$SECRETS")
        [ -z "$why" ] || stop 2 "$SECRETS exists but $why; it is never overwritten: fix it or remove it and run again"
        if [ "$(stat -c %a "$SECRETS")" != 600 ]; then
            [ "$DRY" = 1 ] && { report "WOULD set mode 600 on $SECRETS"; return 0; }
            chmod 600 "$SECRETS" || stop 1 "chmod 600 $SECRETS failed"
            report "OK ($SECRETS present and complete; mode set to 600)"
            return 0
        fi
        report "SKIP ($SECRETS present: the four passwords assigned, no placeholder, mode 600; values not shown)"
        return 0
    fi
    [ "$DRY" = 1 ] && { report "WOULD create $SECRETS from src/deployment/.env.example with fresh random passwords (mode 600)"; return 0; }
    mkdir -p "$CONFIG_DIR" && chmod 700 "$CONFIG_DIR" || stop 1 "cannot create $CONFIG_DIR"
    rm -f "$SECRETS.part"
    names=$(secrets_generate "$REPO/src/deployment/.env.example" "$SECRETS.part") || { rm -f "$SECRETS.part"; stop 3 "the template src/deployment/.env.example could not be filled"; }
    why=$(secrets_problem "$SECRETS.part")
    if [ -n "$why" ]; then
        rm -f "$SECRETS.part"
        stop 3 "the generated file is unusable: $why"
    fi
    mv "$SECRETS.part" "$SECRETS" || stop 1 "cannot write $SECRETS"
    report "OK ($SECRETS, mode 600; fresh random values for: $names; values not shown)"
}

# --- 7. python venv --------------------------------------------------------------------------------

# venv_ok: the venv imports egw_simulator from this clone (no bytecode is written into the clone).
venv_ok() {
    local where
    [ -x "$VENV/bin/python" ] || return 1
    where=$(PYTHONDONTWRITEBYTECODE=1 "$VENV/bin/python" -c 'import os, egw_simulator; print(os.path.realpath(os.path.dirname(egw_simulator.__file__)))' 2> /dev/null) || return 1
    [ "$where" = "$(realpath -m "$REPO/src/egw_simulator")" ]
}

step_venv() {
    step 7 "python venv"
    local log
    if venv_ok; then
        report "SKIP ($VENV imports egw_simulator from this clone)"
        return 0
    fi
    [ "$DRY" = 1 ] && { report "WOULD create $VENV and run pip install -e $REPO/src"; return 0; }
    log=$(new_log venv)
    if [ ! -x "$VENV/bin/python" ]; then
        mkdir -p "$(dirname "$VENV")" || stop 1 "cannot create $(dirname "$VENV")"
        python3 -m venv "$VENV" >> "$log" 2>&1 || { tail_of "$log"; stop 1 "python3 -m venv failed (package python3-venv); see $log"; }
    fi
    note "installing the project from src/ into $VENV (pip, from PyPI)"
    PYTHONDONTWRITEBYTECODE=1 "$VENV/bin/python" -m pip install --disable-pip-version-check -e "$REPO/src" >> "$log" 2>&1 \
        || { tail_of "$log"; stop 1 "pip install -e $REPO/src failed; see $log"; }
    venv_ok || stop 1 "egw_simulator is not importable from $VENV/bin/python; see $log"
    report "OK ($VENV, project installed from $REPO/src; import egw_simulator works)"
}

# --- 8. settings -----------------------------------------------------------------------------------

settings_values() {
    EGW_COMPARE_ROOT=$COMPARE_ROOT
    EGW_COMPARE_QEMU=$QEMU
    EGW_COMPARE_QEMU_IMG=$QEMU_IMG
    EGW_YOCTO_DEPLOY=$KIT_TOP/deploy
    EGW_IMAGES_DIR=$KIT_TOP/controller
    EGW_COMPARE_SSH_KEY=$SSH_KEY
    EGW_COMPARE_SECRETS_ENV=$SECRETS
    EGW_EXEC_VENV=$VENV
    export EGW_COMPARE_ROOT EGW_COMPARE_QEMU EGW_COMPARE_QEMU_IMG EGW_YOCTO_DEPLOY EGW_IMAGES_DIR \
        EGW_COMPARE_SSH_KEY EGW_COMPARE_SECRETS_ENV EGW_EXEC_VENV
}

settings_text() {
    cat << EOF
# egw-demo settings - written by tools/setup/prepare_demo_host.sh; run it again to change them.
# Where tools/compare and tools/demo find their inputs on this PC: paths only, never a secret value.
# Sourced by the login profile: open a new terminal (or run 'bash -l') after a change.
export EGW_COMPARE_ROOT=$(shq "$EGW_COMPARE_ROOT")
export EGW_COMPARE_QEMU=$(shq "$EGW_COMPARE_QEMU")
export EGW_COMPARE_QEMU_IMG=$(shq "$EGW_COMPARE_QEMU_IMG")
export EGW_YOCTO_DEPLOY=$(shq "$EGW_YOCTO_DEPLOY")
export EGW_IMAGES_DIR=$(shq "$EGW_IMAGES_DIR")
export EGW_COMPARE_SSH_KEY=$(shq "$EGW_COMPARE_SSH_KEY")
export EGW_COMPARE_SECRETS_ENV=$(shq "$EGW_COMPARE_SECRETS_ENV")
export EGW_EXEC_VENV=$(shq "$EGW_EXEC_VENV")
EOF
}

# profile_file: the file a bash login shell reads (the first of these that exists).
profile_file() {
    local f
    for f in "$HOME/.bash_profile" "$HOME/.bash_login"; do
        [ -e "$f" ] && { printf '%s\n' "$f"; return 0; }
    done
    printf '%s\n' "$HOME/.profile"
}
profile_line() { printf 'if [ -r %s ]; then . %s; fi  %s\n' "$(shq "$SETTINGS")" "$(shq "$SETTINGS")" "$PROFILE_MARK"; }

step_settings() {
    step 8 "settings"
    local text pf line s_state p_state
    [ -n "$KIT_TOP" ] || stop 2 "the kit folder is unknown (step 4)"
    settings_values
    text=$(settings_text)
    if [ -f "$SETTINGS" ] && [ "$(cat "$SETTINGS")" = "$text" ]; then
        s_state=present
    elif [ "$DRY" = 1 ]; then
        s_state=would
    else
        mkdir -p "$CONFIG_DIR" && chmod 700 "$CONFIG_DIR" || stop 1 "cannot create $CONFIG_DIR"
        printf '%s\n' "$text" > "$SETTINGS.part" && mv "$SETTINGS.part" "$SETTINGS" || stop 1 "cannot write $SETTINGS"
        s_state=written
    fi
    pf=$(profile_file)
    line=$(profile_line)
    if [ -f "$pf" ] && grep -qxF -- "$line" "$pf"; then
        p_state=present
    elif [ "$DRY" = 1 ]; then
        p_state=would
    elif [ -f "$pf" ] && grep -qF -- "$PROFILE_MARK" "$pf"; then
        # Our own marked line with another path: replaced in place, every other line kept.
        awk -v mark="$PROFILE_MARK" -v line="$line" 'index($0, mark) { if (!done) print line; done = 1; next } { print }' "$pf" > "$pf.egw-demo.tmp" \
            && cat "$pf.egw-demo.tmp" > "$pf" && rm -f "$pf.egw-demo.tmp" || stop 1 "cannot update $pf"
        p_state=updated
    else
        if [ -s "$pf" ] && [ -n "$(tail -c 1 "$pf")" ]; then printf '\n' >> "$pf"; fi
        printf '%s\n' "$line" >> "$pf" || stop 1 "cannot write $pf"
        p_state=added
    fi
    if [ "$s_state" = present ] && [ "$p_state" = present ]; then
        report "SKIP ($SETTINGS unchanged; $pf already sources it)"
    elif [ "$s_state" = would ] || [ "$p_state" = would ]; then
        report "WOULD write $SETTINGS ($s_state) and the guarded line in $pf ($p_state)"
    else
        report "OK ($SETTINGS $s_state; line in $pf $p_state)"
    fi
}

# --- 9. terraform init -----------------------------------------------------------------------------

tf_initialised() {
    local tfdir=$REPO/tools/compare/terraform
    [ -d "$tfdir/.terraform/providers" ] && [ -s "$tfdir/.terraform/terraform.tfstate" ] || return 1
    python3 -I - "$tfdir/.terraform/terraform.tfstate" "$COMPARE_ROOT/tfstate" << 'PY' || return 1
import json
import sys

try:
    backend = json.load(open(sys.argv[1], encoding="utf-8")).get("backend") or {}
except (OSError, ValueError):
    sys.exit(1)
sys.exit(0 if (backend.get("config") or {}).get("workspace_dir") == sys.argv[2] else 1)
PY
    [ -d "$COMPARE_ROOT/tfstate/yocto" ] && [ -d "$COMPARE_ROOT/tfstate/debian13" ]
}

step_tf_init() {
    step 9 "terraform init"
    local log s
    if tf_initialised; then
        report "SKIP (module initialised with state under $COMPARE_ROOT/tfstate; workspaces yocto and debian13 exist)"
        return 0
    fi
    [ "$DRY" = 1 ] && { report "WOULD run: bash tools/compare/tf.sh yocto init; bash tools/compare/tf.sh debian13 init"; return 0; }
    log=$(new_log terraform-init)
    for s in yocto debian13; do
        bash "$REPO/tools/compare/tf.sh" "$s" init >> "$log" 2>&1 || { tail_of "$log"; stop 1 "tf.sh $s init failed; see $log"; }
    done
    report "OK (providers installed from the lock file; workspaces yocto and debian13; log $log)"
}

# --- 10. debian 13 ---------------------------------------------------------------------------------

step_debian() {
    step 10 "debian 13"
    local others rc p busy='' log holder
    if [ "$NO_DEBIAN" = 1 ]; then
        report "SKIP (--no-debian; later: EGW_COMPARE_ALLOW_DOWNLOAD=1 bash tools/compare/compare_env.sh prepare debian13)"
        return 0
    fi
    if [ -s "$COMPARE_ROOT/base/debian13/prepared.qcow2" ]; then
        report "SKIP ($COMPARE_ROOT/base/debian13/prepared.qcow2 exists; tf.sh debian13 apply verifies it)"
        return 0
    fi
    # The guards of compare_env.sh, checked first so that nothing is downloaded in vain. Nothing is stopped.
    others=$(pgrep -af "$QEMU_EXE_RE")
    rc=$?
    case $rc in
        0) stop 2 "a qemu-system-aarch64 is running and is never stopped by this script; power it off (tf.sh <s> stop) and run again:
$others" ;;
        1) ;;
        *) stop 2 "could not determine whether a QEMU process is running (pgrep exit $rc)" ;;
    esac
    for p in $PROFILE_PORTS; do
        if ss -ltn 2> /dev/null | grep -qE "[:.]$p "; then busy="$busy $p"; fi
    done
    [ -z "$busy" ] || stop 2 "host port(s) needed by the Debian first boot already have a listener:$busy"
    [ ! -e "${EGW_EXEC:-$HOME/egw-exec}/current_session" ] || stop 2 "a pilot session is open (${EGW_EXEC:-$HOME/egw-exec}/current_session)"
    # The profile's lock as lock_acquire (tools/compare/lib.sh) reads it: held by another scenario whose
    # state/qemu.pid is not empty (or naming none), compare_env.sh refuses; a stale one it takes over.
    if [ -e "$COMPARE_ROOT/lock/active" ]; then
        holder=$(cat "$COMPARE_ROOT/lock/active/holder" 2> /dev/null)
        [ -n "$holder" ] || stop 2 "the profile's lock $COMPARE_ROOT/lock/active names no scenario, so compare_env.sh would refuse the first boot; when no tools/compare command is running, remove that folder and run again"
        if [ "$holder" != debian13 ] && [ -s "$COMPARE_ROOT/scenarios/$holder/state/qemu.pid" ]; then
            stop 2 "the profile's lock is held by scenario '$holder' ($COMPARE_ROOT/scenarios/$holder/state/qemu.pid is not empty), so compare_env.sh would refuse the first boot; power it off (bash tools/compare/tf.sh $holder stop) and run again"
        fi
    fi
    [ "$DRY" = 1 ] && { report "WOULD run: EGW_COMPARE_ALLOW_DOWNLOAD=1 bash tools/compare/compare_env.sh prepare debian13 (download of the pinned image, SHA512 check, one provisioning boot)"; return 0; }
    log=$(new_log debian13-prepare)
    note "downloading the pinned Debian 13 image (about 0.4 GB, SHA512-checked) and booting it once to install the"
    note "container engine; this takes several minutes under emulation (transcript $log)"
    EGW_COMPARE_ALLOW_DOWNLOAD=1 bash "$REPO/tools/compare/compare_env.sh" prepare debian13 >> "$log" 2>&1
    rc=$?
    [ "$rc" = 0 ] || { tail_of "$log"; stop 1 "compare_env.sh prepare debian13 exited $rc; see $log and $COMPARE_ROOT/scenarios/debian13/logs/. The Debian 13 scenario is optional: run again with --no-debian to finish the preparation without it"; }
    report "OK ($COMPARE_ROOT/base/debian13/prepared.qcow2 written; log $log)"
}

# --- 11. summary -----------------------------------------------------------------------------------

step_summary() {
    step 11 "summary"
    if [ "$DRY" = 1 ]; then
        report "dry run: nothing was changed; run again without --dry-run to prepare the host"
        return 0
    fi
    report "OK - the host is prepared"
    cat << EOF

Next, in a NEW Ubuntu terminal (or after: bash -l), so that the settings apply. A terminal that is not a
login shell (some editor terminals, wsl -e bash) must first run: . $SETTINGS
  cd $REPO
  bash tools/demo/demo.sh                   # the menu; or the manual commands of README.md
  bash tools/compare/tf.sh yocto apply      # or start the Yocto gateway directly
The first 'apply' of each scenario pulls the five pinned container images onto a fresh data disk and loads
the controller image, so it takes longer than the later ones (about 10 minutes under emulation).
tf.sh starts the gateway; the kit's own yoctoScarthgap/run-linux.sh is not needed (it starts a QEMU outside
the guards of tools/compare). Keep the kit ZIP and its .sha256: a re-run of this script reads them again.
EOF
    [ "$NO_DEBIAN" = 1 ] && echo "Debian 13 is not prepared (--no-debian): run this script again without it to add the debian13 scenario."
    echo "QEMU here is Ubuntu's ${QEMU_VERSION:-8.2.x}, not the 8.2.7 of the recorded measurements: this host runs the"
    echo "demonstration; it does not reproduce the measured series. The yoctowrynose scenario is not in the kit."
}

main() {
    parse_args "$@"
    echo "prepare_demo_host.sh: clone $REPO, kit $KIT$([ "$DRY" = 1 ] && echo ' (dry run)')"
    step_host
    step_apt
    step_terraform
    step_kit
    step_ssh_key
    step_secrets
    step_venv
    step_settings
    step_tf_init
    step_debian
    step_summary
}

# Sourced by the offline check for its functions; run, it prepares the host.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
