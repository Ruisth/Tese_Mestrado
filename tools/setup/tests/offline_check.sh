#!/bin/bash
# tools/setup/tests/offline_check.sh - offline checks of tools/setup. It starts nothing: no guest, QEMU,
# Terraform, apt, sudo, network access or real secrets file is used. QEMU, qemu-img, sudo, curl, apt-get,
# dpkg-query, pgrep, ss, findmnt and id are stubs on PATH; the clone the preparation script sees is a
# stand-in under the temporary folder (its tf.sh and compare_env.sh are stubs), and HOME is a throw-away
# folder.
#   1. bash -n on every script under tools/setup;
#   2. shellcheck --severity=error on the same scripts when shellcheck is installed;
#   3. prepare_demo_host.sh arguments: usage, refusals, --kit=, --no-debian, --dry-run, derived paths;
#   4. step 1 against stub host files: WSL 2 / WSL 1 / not WSL, Ubuntu 24.04 / 22.04, low memory, root,
#      a clone or a location under /mnt or on a 9p drive, a location inside the clone, CRLF line endings,
#      a missing kit; a host with its own comparison set-up refused (EGW_* settings, a state root without
#      the marker, the measurement key, the session tooling), its own settings and marker accepted;
#   5. the deployment .env: fields filled, EGW_MQTT_PASSWORD = MOSQUITTO_CONTROLLER_PASSWORD, mode 600,
#      no value printed, sourceable by bash and sh, never overwritten, provision_stack.sh's rules met;
#   6. the settings file and the ONE guarded profile line: values, idempotence, ~/.bash_profile, an
#      updated path, a profile without a final newline, a dry run that writes nothing;
#   7. qcow2 -> raw ext4 with a stub qemu-img: the exact names of tools/compare/scenarios/yocto.env,
#      modes, records, a second call that converts nothing, a non-ext4 result refused;
#   8. make_demo_kit.sh on a stand-in package and controller archive: the zip, its .sha256, the layout
#      and modes; refusals for every rule of the secret scan, a damaged package, the sealed image's
#      names (also compressed, and .wic), a missing clean-scan record, a controller record mismatch, an
#      existing zip, --out in the clone, a data disk that is not empty or not ext4 (also one known only by
#      its qcow2 magic), a qcow2 with snapshots, a backing file or a data file, a zstd layer, a key inside
#      an xz layer, a compressed ext4 under a neutral name, a disk image inside an archive, a root file
#      system file whose first line is a password assignment, a password assignment right after a NUL
#      byte, anything after the test key's END line;
#      binary key markers without a body and 'password=None' in an image layer are NOT hits;
#   9. step 4 on that zip: dry run, extraction, conversion, SKIP on a re-run (also with the overlays of
#      run-linux.sh in yoctoScarthgap/work/), a different kit of the same date refused, a stale extraction
#      folder removed, .sha256 mismatch, missing .sha256, a tampered extracted file, unsafe or foreign zip
#      layouts, an inner SHA256SUMS mismatch;
#  10. the whole script on the stand-in clone: a dry run that writes nothing and calls no sudo, curl or
#      convert; a damaged ZIP stopped in step 1; the step-10 guards (a running QEMU, a busy port); step 3
#      marking the state root and removing a stale download; a real run with every external step stubbed,
#      then re-runs (plain, and with the settings sourced as in a login shell) in which every step is
#      SKIP and HOME is unchanged;
#  11. static rules: no personal paths, no process killing, no set -x;
#  12. the settings as the REAL tools read them: tools/compare/lib.sh with scenarios/yocto.env (the base
#      files step 4 wrote), tools/demo/lib.sh, and the names provision_stack.sh reads.
# Everything written goes to a temporary folder (under $TMPDIR when set) removed at the end.
# Exit 0 when every check passes, 1 otherwise.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SETUP=$(cd "$HERE/.." && pwd)
REPO=$(cd "$SETUP/../.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/egw-setup-check.XXXXXX") || { echo "cannot create a temporary folder"; exit 1; }
trap 'chmod -R u+w "$TMP" 2> /dev/null; rm -rf "$TMP"' EXIT
STUB=$TMP/stub
CLONE=$TMP/clone
LOGF=$TMP/stub.log
PATH0="$PATH:/usr/sbin:/sbin"
mkdir -p "$STUB" "$CLONE"
: > "$LOGF"
pass=0
fail=0
skip=0
ok() { pass=$((pass + 1)); printf 'ok    %s\n' "$1"; }
ko() { fail=$((fail + 1)); printf 'FAIL  %s\n' "$1"; }
sk() { skip=$((skip + 1)); printf 'skip  %s\n' "$1"; }
same() { if [ "$2" = "$3" ]; then ok "$1"; else ko "$1 (expected '$2', got '$3')"; fi; }
has() { case $3 in *"$2"*) ok "$1" ;; *) ko "$1 (no '$2' in: $(printf '%s' "$3" | tr '\n' ' ' | cut -c1-300))" ;; esac; }
hasnt() { case $3 in *"$2"*) ko "$1 ('$2' found)" ;; *) ok "$1" ;; esac; }
# secret_absent NAME VALUE TEXT: VALUE does not occur in TEXT; a failure never shows VALUE.
secret_absent() { if [ -n "$2" ] && case $3 in *"$2"*) false ;; *) true ;; esac; then ok "$1"; else ko "$1 (value found in the output, or empty)"; fi; }
snap() { (cd "$1" && find . -printf '%p %s %m %T@\n' | LC_ALL=C sort); }
mode_of() { stat -c %a "$1" 2> /dev/null; }
# The PEM markers are assembled here so that this file itself carries none.
PK="PRIV""ATE KEY-----"
PEM_B_RSA="-----BEGIN RSA $PK"
PEM_E_RSA="-----END RSA $PK"
PEM_B_SSH="-----BEGIN OPENSSH $PK"
PEM_E_SSH="-----END OPENSSH $PK"

# --- stubs -----------------------------------------------------------------------------------------
stub() { printf '#!/bin/bash\n%s\n' "$2" > "$STUB/$1"; chmod 0755 "$STUB/$1"; }
stub id 'if [ "${1:-}" = -u ]; then echo "${STUB_UID:-1000}"; else exec /usr/bin/id "$@"; fi'
stub sudo 'echo "sudo $*" >> "$STUB_LOG"; exit 99'
stub curl 'echo "curl $*" >> "$STUB_LOG"; exit 99'
stub apt-get 'echo "apt-get $*" >> "$STUB_LOG"; exit 99'
stub dpkg-query 'if [ "${STUB_DPKG:-installed}" = installed ]; then printf "install ok installed"; else exit 1; fi'
stub pgrep 'if [ "${STUB_PGREP_RC:-1}" = 0 ]; then echo "4242 qemu-system-aarch64 -machine virt"; fi; exit "${STUB_PGREP_RC:-1}"'
stub ss 'echo "State Recv-Q Send-Q Local Address:Port Peer Address:Port"; [ -z "${STUB_SS_LINE:-}" ] || echo "$STUB_SS_LINE"'
# findmnt: paths under $STUB_9P are on a Windows drive (9p); the rest are answered by the real findmnt.
stub findmnt 'case ${*: -1} in
    "${STUB_9P:-/nonexistent-9p}" | "${STUB_9P:-/nonexistent-9p}"/*) echo 9p ;;
    *) if [ -x /usr/bin/findmnt ]; then exec /usr/bin/findmnt "$@"; else echo ext4; fi ;;
esac'
stub qemu-system-aarch64 'case "$*" in
    --version) echo "QEMU emulator version 8.2.2 (offline-check stub)" ;;
    "-cpu help") printf "Available CPUs:\n  cortex-a57\n  cortex-a76\n  max\n" ;;
    "-device help") printf "name \"virtio-net-pci\", bus PCI\nname \"virtio-blk-pci\", bus PCI\nname \"virtio-rng-pci\", bus PCI\nname \"virtio-gpu-pci\", bus PCI\n" ;;
    *) echo "qemu-system-aarch64 $*" >> "$STUB_LOG"; exit 99 ;;
esac'
# qemu-img: "convert" drops the 512-byte stand-in qcow2 header (the payload is a real ext4 image); "info"
# answers the JSON kept in that header after byte 8, else a plain qcow2 (no snapshot, backing or data file).
stub qemu-img 'echo "qemu-img $*" >> "$STUB_LOG"
case ${1:-} in
    --version) echo "qemu-img version 8.2.2 (offline-check stub)" ;;
    convert) dd if="${*: -2:1}" of="${*: -1}" bs=512 skip=1 conv=sparse status=none ;;
    info) j=$(head -c 512 "${*: -1}" | tail -c +9 | tr -d "\000")
        if [ -n "$j" ]; then printf "%s\n" "$j"; else echo "{\"format\": \"qcow2\", \"virtual-size\": 8388608}"; fi ;;
    *) exit 99 ;;
esac'

# --- the stand-in clone ----------------------------------------------------------------------------
mkdir -p "$CLONE/tools/setup" "$CLONE/tools/compare/scenarios" "$CLONE/src/deployment" "$CLONE/src/egw_simulator"
cp "$SETUP"/*.sh "$CLONE/tools/setup/"
cp "$REPO/tools/compare/lib.sh" "$CLONE/tools/compare/"
cp "$REPO/tools/compare/scenarios/yocto.env" "$CLONE/tools/compare/scenarios/"
cp "$REPO/src/deployment/.env.example" "$CLONE/src/deployment/"
cp "$REPO/src/pyproject.toml" "$CLONE/src/"
cat > "$CLONE/tools/compare/tf.sh" << 'EOF'
#!/bin/bash
# offline-check stub of tf.sh: records the call and leaves what `init` leaves.
echo "tf.sh $*" >> "$STUB_LOG"
[ "${2:-}" = init ] || exit 9
d=$(cd "$(dirname "$0")" && pwd)/terraform/.terraform
mkdir -p "$d/providers" "$EGW_COMPARE_ROOT/tfstate/$1"
printf '{"backend": {"type": "local", "config": {"path": null, "workspace_dir": "%s"}}}\n' "$EGW_COMPARE_ROOT/tfstate" > "$d/terraform.tfstate"
EOF
cat > "$CLONE/tools/compare/compare_env.sh" << 'EOF'
#!/bin/bash
# offline-check stub of compare_env.sh: records the call; `prepare debian13` leaves a prepared base.
echo "compare_env.sh $* allow=${EGW_COMPARE_ALLOW_DOWNLOAD:-0} qemu=${EGW_COMPARE_QEMU:-}" >> "$STUB_LOG"
[ "$1 $2" = "prepare debian13" ] && [ "${EGW_COMPARE_ALLOW_DOWNLOAD:-}" = 1 ] || exit 9
mkdir -p "$EGW_COMPARE_ROOT/base/debian13" && echo stub > "$EGW_COMPARE_ROOT/base/debian13/prepared.qcow2"
echo "PREPARED debian13: (stub)"
EOF
PREP=$CLONE/tools/setup/prepare_demo_host.sh
printf 'Linux version 6.6.87.2-microsoft-standard-WSL2 (root@build) #1 SMP\n' > "$TMP/pv_wsl2"
printf 'Linux version 4.4.0-19041-Microsoft (Microsoft@Microsoft.com) #1\n' > "$TMP/pv_wsl1"
printf 'Linux version 6.8.0-45-generic (buildd@lcy02-amd64-075) #45-Ubuntu SMP\n' > "$TMP/pv_native"
printf 'NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="24.04"\n' > "$TMP/os_2404"
printf 'NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="22.04"\n' > "$TMP/os_2204"
printf 'MemTotal:       16303428 kB\n' > "$TMP/mem16"
printf 'MemTotal:        8000000 kB\n' > "$TMP/mem8"

# envrun [VAR=value ...] CMD...: CMD in a clean environment: throw-away HOME ($TMP/home unless given),
# stubs first on PATH, the stub host files of step 1, stdout and stderr together, run from $TMP.
envrun() {
    local assigns=()
    while [ $# -gt 0 ] && case $1 in [A-Za-z_]*=*) true ;; *) false ;; esac; do assigns+=("$1"); shift; done
    (cd "$TMP" && env -i PATH="$STUB:$PATH0" HOME="$TMP/home" TMPDIR="$TMP" STUB_LOG="$LOGF" \
        EGW_SETUP_PROC_VERSION="$TMP/pv_wsl2" EGW_SETUP_OS_RELEASE="$TMP/os_2404" EGW_SETUP_MEMINFO="$TMP/mem16" \
        EGW_SETUP_QEMU="$STUB/qemu-system-aarch64" EGW_SETUP_QEMU_IMG="$STUB/qemu-img" \
        "${assigns[@]}" "$@" 2>&1)
}
# prep [VAR=value ...] CODE: CODE run by bash with prepare_demo_host.sh (of the stand-in clone) sourced.
prep() {
    local assigns=()
    while [ $# -gt 1 ]; do assigns+=("$1"); shift; done
    envrun "${assigns[@]}" bash -c '. "$1" && eval "$2"' prep "$PREP" "$1"
}
mkdir -p "$TMP/home"

SCRIPTS=("$SETUP/prepare_demo_host.sh" "$SETUP/make_demo_kit.sh" "$SETUP/tests/offline_check.sh")

echo "== 1. bash -n (${#SCRIPTS[@]} scripts)"
for f in "${SCRIPTS[@]}"; do
    if bash -n "$f" 2> "$TMP/syntax.err"; then ok "bash -n ${f#"$REPO"/}"; else ko "bash -n ${f#"$REPO"/}: $(head -n 1 "$TMP/syntax.err")"; fi
done

echo "== 2. shellcheck --severity=error"
if command -v shellcheck > /dev/null 2>&1; then
    if (cd "$REPO" && shellcheck --severity=error "${SCRIPTS[@]}"); then ok "shellcheck --severity=error ($(shellcheck --version | sed -n 's/^version: //p'))"; else ko "shellcheck --severity=error"; fi
else
    sk "shellcheck not installed (CI runs it on every tracked script)"
fi

echo "== 3. arguments"
out=$(envrun bash "$PREP"); rc=$?
same "no argument: exit 2" 2 "$rc"
has "no argument: says --kit is required" "--kit <zip> is required" "$out"
out=$(envrun bash "$PREP" --kit k.zip --bogus); rc=$?
same "unknown argument: exit 2" 2 "$rc"
has "unknown argument named" "unknown argument: --bogus" "$out"
out=$(envrun bash "$PREP" --kit); rc=$?
same "--kit without a path: exit 2" 2 "$rc"
out=$(envrun bash "$PREP" --help); rc=$?
same "--help: exit 0" 0 "$rc"
has "--help prints the usage" "prepare_demo_host.sh --kit <egw-demo-kit-YYYYMMDD.zip>" "$out"
same "--kit= --no-debian --dry-run parsed" "$TMP/k.zip|1|1" "$(prep 'parse_args --kit=k.zip --no-debian --dry-run; printf "%s|%s|%s" "$KIT" "$NO_DEBIAN" "$DRY"')"
same "defaults: no-debian and dry-run off" "0|0" "$(prep 'parse_args --kit /x/k.zip; printf "%s|%s" "$NO_DEBIAN" "$DRY"')"
same "default settings and secrets paths" "$TMP/home/.config/egw-demo/env.sh|$TMP/home/.config/egw-demo/deployment.env" \
    "$(prep 'parse_args --kit /x/k.zip; printf "%s|%s" "$SETTINGS" "$SECRETS"')"
same "default comparison root, kit folder and venv" "$TMP/home/egw-compare|$TMP/home/egw-kit|$TMP/home/.local/share/egw-demo/venv" \
    "$(prep 'parse_args --kit /x/k.zip; printf "%s|%s|%s" "$COMPARE_ROOT" "$KIT_DIR" "$VENV"')"
same "EGW_DEMO_CONFIG, EGW_KIT_DIR, EGW_DEMO_VENV, EGW_COMPARE_ROOT honoured" "/c/env.sh|/k|/v|/r" \
    "$(prep EGW_DEMO_CONFIG=/c EGW_KIT_DIR=/k EGW_DEMO_VENV=/v EGW_COMPARE_ROOT=/r 'parse_args --kit /x/k.zip; printf "%s|%s|%s|%s" "$SETTINGS" "$KIT_DIR" "$VENV" "$COMPARE_ROOT"')"
same "Ubuntu's QEMU by default" "/usr/bin/qemu-system-aarch64|/usr/bin/qemu-img" \
    "$(prep EGW_SETUP_QEMU= EGW_SETUP_QEMU_IMG= 'printf "%s|%s" "$QEMU" "$QEMU_IMG"')"

echo "== 4. host checks (step 1)"
# A minimal kit ZIP for step 1 (its contents are checked in section 9).
K4=$TMP/k4/egw-demo-kit-20990101.zip
mkdir -p "$TMP/k4"
python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1], "w").writestr("egw-demo-kit-20990101/README.txt", "x")' "$K4"
H1="parse_args --kit '$K4'; step_host"
out=$(prep "$H1"); rc=$?
same "WSL 2 + Ubuntu 24.04: exit 0" 0 "$rc"
has "WSL 2 + Ubuntu 24.04: OK line" "[1/11] host checks: OK" "$out"
has "the kit's layout read in step 1" "kit egw-demo-kit-20990101, zip .sha256 absent" "$out"
hasnt "16 GiB: no memory warning" "GiB of memory, below" "$out"
out=$(prep "parse_args --kit '$TMP/k4/missing.zip'; step_host"); rc=$?
same "kit missing: exit 2 in step 1" 2 "$rc"
has "kit missing: named in step 1" "[1/11] host checks: STOP: kit not found or not readable" "$out"
out=$(prep EGW_SETUP_MEMINFO="$TMP/mem8" "$H1"); rc=$?
same "8 GiB: still exit 0" 0 "$rc"
has "8 GiB: memory warning with the .wslconfig hint" "below 12 GiB" "$out"
has "8 GiB: .wslconfig named" ".wslconfig" "$out"
out=$(prep EGW_SETUP_PROC_VERSION="$TMP/pv_wsl1" "$H1"); rc=$?
same "WSL 1: exit 2" 2 "$rc"
has "WSL 1: named" "this is WSL 1" "$out"
out=$(prep EGW_SETUP_PROC_VERSION="$TMP/pv_native" "$H1"); rc=$?
same "not WSL: exit 2" 2 "$rc"
has "not WSL: named" "not a WSL 2 kernel" "$out"
out=$(prep EGW_SETUP_OS_RELEASE="$TMP/os_2204" "$H1"); rc=$?
same "Ubuntu 22.04: exit 2" 2 "$rc"
has "Ubuntu 22.04: named" "'ubuntu 22.04', not Ubuntu 24.04" "$out"
out=$(prep "REPO=/mnt/c/Users/someone/egw; $H1"); rc=$?
same "clone under /mnt: exit 2" 2 "$rc"
has "clone under /mnt: refused" "on the Windows file system (/mnt/c/Users/someone/egw)" "$out"
out=$(prep EGW_COMPARE_ROOT=/mnt/c/egw-compare "$H1"); rc=$?
same "EGW_COMPARE_ROOT under /mnt: exit 2" 2 "$rc"
has "EGW_COMPARE_ROOT under /mnt: refused" "/mnt/c/egw-compare is on the Windows file system" "$out"
out=$(prep STUB_9P="$CLONE" "$H1"); rc=$?
same "clone on a 9p drive outside /mnt: exit 2" 2 "$rc"
has "clone on a 9p drive outside /mnt: refused" "the clone is on a Windows drive ($CLONE, file system 9p)" "$out"
mkdir -p "$TMP/w9p"
out=$(prep STUB_9P="$TMP/w9p" EGW_KIT_DIR="$TMP/w9p/kit" "$H1"); rc=$?
same "kit folder on a 9p drive outside /mnt: exit 2" 2 "$rc"
has "kit folder on a 9p drive outside /mnt: refused" "$TMP/w9p/kit is on a Windows drive (file system 9p)" "$out"
out=$(prep EGW_KIT_DIR="$CLONE/kit" "$H1"); rc=$?
same "kit folder inside the clone: exit 2" 2 "$rc"
has "kit folder inside the clone: refused" "overlaps the clone" "$out"
out=$(prep STUB_UID=0 "$H1"); rc=$?
same "root: exit 2" 2 "$rc"
has "root: refused" "not as root" "$out"
CR=$TMP/crlfclone
mkdir -p "$CR"
cp -r "$CLONE/tools" "$CLONE/src" "$CR/"
sed -i 's/$/\r/' "$CR/tools/compare/lib.sh"
out=$(prep "REPO='$CR'; $H1"); rc=$?
same "CRLF clone: exit 2" 2 "$rc"
has "CRLF clone: refused" "Windows (CRLF) line endings" "$out"
# A host with its own comparison set-up (the author's measurement host) is refused before any change.
FOREIGN="this host has its own comparison set-up; prepare_demo_host.sh is for a separate PC or WSL distribution"
for n in EGW_COMPARE_QEMU EGW_COMPARE_QEMU_IMG EGW_YOCTO_DEPLOY EGW_IMAGES_DIR EGW_COMPARE_SSH_KEY EGW_COMPARE_SECRETS_ENV EGW_EXEC_VENV EGW_EXEC; do
    H4=$TMP/home4.$n
    mkdir -p "$H4"
    out=$(prep HOME="$H4" "$n=/opt/own/setting" "$H1"); rc=$?
    same "$n set by another set-up: exit 2" 2 "$rc"
    has "$n set by another set-up: refused" "$n is already set (/opt/own/setting): $FOREIGN" "$out"
    same "$n set by another set-up: nothing written" "" "$(find "$H4" -mindepth 1)"
done
H4=$TMP/home4own
mkdir -p "$H4/.config/egw-demo"
printf "export EGW_COMPARE_QEMU='/usr/bin/qemu-system-aarch64'\n" > "$H4/.config/egw-demo/env.sh"
out=$(prep HOME="$H4" EGW_COMPARE_QEMU=/usr/bin/qemu-system-aarch64 "$H1"); rc=$?
same "a value this script's settings file exports: accepted" 0 "$rc"
H4=$TMP/home4root
mkdir -p "$H4/egw-compare/base/yocto"
out=$(prep HOME="$H4" "$H1"); rc=$?
same "a state root without the marker: exit 2" 2 "$rc"
has "a state root without the marker: refused" "$H4/egw-compare holds a comparison state this script did not make (no .egw-demo-host)" "$out"
: > "$H4/egw-compare/.egw-demo-host"
out=$(prep HOME="$H4" "$H1"); rc=$?
same "a state root with the marker: accepted" 0 "$rc"
H4=$TMP/home4empty
mkdir -p "$H4/egw-compare"
out=$(prep HOME="$H4" "$H1"); rc=$?
same "an empty state root: accepted" 0 "$rc"
H4=$TMP/home4key
mkdir -p "$H4/.ssh"
: > "$H4/.ssh/egw_campaign"
out=$(prep HOME="$H4" "$H1"); rc=$?
same "the measurement key present: exit 2" 2 "$rc"
has "the measurement key present: refused" "$H4/.ssh/egw_campaign exists (the measurement key or the session tooling): $FOREIGN" "$out"
H4=$TMP/home4exec
mkdir -p "$H4/egw-exec"
out=$(prep HOME="$H4" "$H1"); rc=$?
same "the session tooling present: exit 2" 2 "$rc"
has "the session tooling present: refused" "$H4/egw-exec exists" "$out"

echo "== 5. deployment .env (step 6)"
H5=$TMP/home5
mkdir -p "$H5"
S6='parse_args --kit /x/k.zip; step_secrets'
out=$(prep HOME="$H5" "$S6"); rc=$?
SEC=$H5/.config/egw-demo/deployment.env
same "created: exit 0" 0 "$rc"
has "created: OK line" "[6/11] secrets file: OK" "$out"
same "mode 600" 600 "$(mode_of "$SEC")"
same "folder mode 700" 700 "$(mode_of "$H5/.config/egw-demo")"
same "no CHANGE_ME left in an assignment" 1 "$(grep -Eq '^[A-Za-z_][A-Za-z0-9_]*=.*CHANGE_ME' "$SEC"; echo $?)"
val() { sed -n "s/^$1=//p" "$SEC" | head -n 1; }
SIM=$(val MOSQUITTO_SIMULATOR_PASSWORD)
CTL=$(val MOSQUITTO_CONTROLLER_PASSWORD)
MQ=$(val EGW_MQTT_PASSWORD)
DEV=$(val DITTO_DEVOPS_PASSWORD)
for v in SIM CTL DEV; do
    same "$v: 32 letters and digits" 0 "$(printf '%s' "${!v}" | grep -Eqx '[A-Za-z0-9]{32}'; echo $?)"
done
same "EGW_MQTT_PASSWORD equals MOSQUITTO_CONTROLLER_PASSWORD" 0 "$([ -n "$CTL" ] && [ "$CTL" = "$MQ" ]; echo $?)"
[ "$SIM" != "$CTL" ] && [ "$SIM" != "$DEV" ] && [ "$CTL" != "$DEV" ] && ok "three distinct values" || ko "three distinct values"
same "EGW_DITTO_PASSWORD left empty (pre-authentication mode)" "" "$(val EGW_DITTO_PASSWORD)"
same "the other template lines kept" "$(grep -c . "$CLONE/src/deployment/.env.example")" "$(($(grep -c . "$SEC") - 2))"
for v in "$SIM" "$CTL" "$DEV"; do secret_absent "no generated value printed" "$v" "$out"; done
has "the filled names are reported" "DITTO_DEVOPS_PASSWORD EGW_MQTT_PASSWORD MOSQUITTO_CONTROLLER_PASSWORD MOSQUITTO_SIMULATOR_PASSWORD" "$out"
same "provision_stack.sh's rules met" "" "$(prep HOME="$H5" "secrets_problem '$SEC'")"
# (compared, never printed: a failure shows 0/1, not the generated value)
same "sourceable by bash (as simulate.sh does)" 0 "$([ "$(env -i bash -c '. "$1" > /dev/null 2>&1; printf %s "$MOSQUITTO_SIMULATOR_PASSWORD"' x "$SEC")" = "$SIM" ]; echo $?)"
same "sourceable by sh (as the guest does)" 0 "$([ "$(env -i sh -c '. "$1" > /dev/null 2>&1; printf %s "$DITTO_DEVOPS_PASSWORD"' x "$SEC")" = "$DEV" ]; echo $?)"
before=$(sha256sum "$SEC")
out=$(prep HOME="$H5" "$S6"); rc=$?
same "re-run: exit 0" 0 "$rc"
has "re-run: SKIP" "[6/11] secrets file: SKIP" "$out"
same "re-run: file unchanged" "$before" "$(sha256sum "$SEC")"
H5b=$TMP/home5b
mkdir -p "$H5b/.config/egw-demo"
printf 'MOSQUITTO_SIMULATOR_PASSWORD=CHANGE_ME_simulator\n' > "$H5b/.config/egw-demo/deployment.env"
out=$(prep HOME="$H5b" "$S6"); rc=$?
same "incomplete existing file: exit 2" 2 "$rc"
has "incomplete existing file: never overwritten" "never overwritten" "$out"
same "incomplete existing file: unchanged" "MOSQUITTO_SIMULATOR_PASSWORD=CHANGE_ME_simulator" "$(cat "$H5b/.config/egw-demo/deployment.env")"
H5c=$TMP/home5c
mkdir -p "$H5c"
out=$(prep HOME="$H5c" "parse_args --kit /x/k.zip --dry-run; step_secrets"); rc=$?
has "dry run: WOULD" "[6/11] secrets file: WOULD" "$out"
same "dry run: nothing created" "" "$(find "$H5c" -mindepth 1)"

echo "== 6. settings file and profile line (step 8)"
H6=$TMP/home6
mkdir -p "$H6"
S8='parse_args --kit /x/k.zip; KIT_TOP=/kits/egw-demo-kit-20990101; step_settings'
out=$(prep HOME="$H6" EGW_SETUP_QEMU= EGW_SETUP_QEMU_IMG= "$S8"); rc=$?
ENVF=$H6/.config/egw-demo/env.sh
same "written: exit 0" 0 "$rc"
has "written: OK line" "[8/11] settings: OK" "$out"
got=$(env -i HOME="$H6" sh -c '. "$1"; printf "%s|%s|%s|%s|%s|%s|%s|%s" "$EGW_COMPARE_ROOT" "$EGW_COMPARE_QEMU" "$EGW_COMPARE_QEMU_IMG" "$EGW_YOCTO_DEPLOY" "$EGW_IMAGES_DIR" "$EGW_COMPARE_SSH_KEY" "$EGW_COMPARE_SECRETS_ENV" "$EGW_EXEC_VENV"' x "$ENVF")
same "the eight settings (read by sh)" "$H6/egw-compare|/usr/bin/qemu-system-aarch64|/usr/bin/qemu-img|/kits/egw-demo-kit-20990101/deploy|/kits/egw-demo-kit-20990101/controller|$H6/.ssh/egw_compare_share|$H6/.config/egw-demo/deployment.env|$H6/.local/share/egw-demo/venv" "$got"
same "no secret value in the settings file" 1 "$(grep -q 'PASSWORD' "$ENVF"; echo $?)"
same "one marked line in ~/.profile" 1 "$(grep -c 'egw-demo settings (tools/setup/prepare_demo_host.sh)' "$H6/.profile")"
same "~/.profile sources the settings" "$H6/.local/share/egw-demo/venv" "$(env -i HOME="$H6" bash -c '. "$HOME/.profile"; printf %s "${EGW_EXEC_VENV:-}"')"
b1=$(snap "$H6")
out=$(prep HOME="$H6" EGW_SETUP_QEMU= EGW_SETUP_QEMU_IMG= "$S8"); rc=$?
has "re-run: SKIP" "[8/11] settings: SKIP" "$out"
same "re-run: HOME unchanged" "$b1" "$(snap "$H6")"
out=$(prep HOME="$H6" EGW_SETUP_QEMU= EGW_SETUP_QEMU_IMG= 'parse_args --kit /x/k.zip; KIT_TOP=/kits/egw-demo-kit-20991231; step_settings'); rc=$?
has "another kit: settings rewritten, line kept" "written; line in $H6/.profile present" "$out"
same "another kit: new deploy path" "/kits/egw-demo-kit-20991231/deploy" "$(env -i sh -c '. "$1"; printf %s "$EGW_YOCTO_DEPLOY"' x "$ENVF")"
out=$(prep HOME="$H6" EGW_DEMO_CONFIG="$H6/cfg2" "$S8"); rc=$?
has "another settings path: the marked line updated" "line in $H6/.profile updated" "$out"
same "another settings path: still one marked line" 1 "$(grep -c 'egw-demo settings (tools/setup/prepare_demo_host.sh)' "$H6/.profile")"
same "another settings path: the line names it" 1 "$(grep -c "$H6/cfg2/env.sh" "$H6/.profile")"
H6b=$TMP/home6b
mkdir -p "$H6b"
printf 'export KEEP=1' > "$H6b/.profile"
prep HOME="$H6b" "$S8" > /dev/null
same "a profile without a final newline: first line intact" "export KEEP=1" "$(sed -n 1p "$H6b/.profile")"
same "a profile without a final newline: our line second" 1 "$(sed -n 2p "$H6b/.profile" | grep -c 'egw-demo settings')"
H6c=$TMP/home6c
mkdir -p "$H6c"
printf '# own login file\n' > "$H6c/.bash_profile"
prep HOME="$H6c" "$S8" > /dev/null
same "~/.bash_profile present: the line goes there" 1 "$(grep -c 'egw-demo settings' "$H6c/.bash_profile")"
same "~/.bash_profile present: ~/.profile untouched" 1 "$([ -e "$H6c/.profile" ]; echo $?)"
H6d=$TMP/home6d
mkdir -p "$H6d"
out=$(prep HOME="$H6d" 'parse_args --kit /x/k.zip --dry-run; KIT_TOP=/k/egw-demo-kit-20990101; step_settings')
has "dry run: WOULD" "[8/11] settings: WOULD" "$out"
same "dry run: nothing written" "" "$(find "$H6d" -mindepth 1)"

echo "== 7. qcow2 -> raw ext4 (step 4, stub qemu-img)"
# make_rootfs DIR: an ext4 image of DIR (mkfs.ext4 -d, no root needed) in $TMP/rootfs.ext4.
make_rootfs() {
    rm -f "$TMP/rootfs.ext4"
    truncate -s 8M "$TMP/rootfs.ext4" && mkfs.ext4 -q -F -d "$1" "$TMP/rootfs.ext4" > /dev/null 2>&1
}
# fake_qcow2 PAYLOAD OUT [INFO]: a 512-byte header with the qcow2 magic, then PAYLOAD (the stub converts it
# back); INFO, the JSON the stub's "qemu-img info" answers, is kept in the header.
fake_qcow2() { local j=${3:-}; { printf 'QFI\373\0\0\0\0%s' "$j"; head -c $((504 - ${#j})) /dev/zero; cat "$1"; } > "$2"; }
K7=$TMP/k7/egw-demo-kit-20990101
mkdir -p "$K7/yoctoScarthgap" "$TMP/r7/etc"
printf 'stand-in\n' > "$TMP/r7/etc/hostname"
make_rootfs "$TMP/r7" || ko "mkfs.ext4 -d (e2fsprogs) unavailable"
fake_qcow2 "$TMP/rootfs.ext4" "$K7/yoctoScarthgap/yoctoScarthgap.qcow2"
head -c 4096 /dev/urandom > "$K7/yoctoScarthgap/Image"
: > "$LOGF"
out=$(prep "DRY=0; kit_deploy '$K7'; echo \"rc=\$? state=\$DEPLOY_STATE msg=\$DEPLOY_MSG\"")
has "converted" "rc=0 state=converted" "$out"
RFS=$K7/deploy/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
same "the exact file name of yocto.env (rootfs)" 0 "$([ -s "$RFS" ]; echo $?)"
same "the exact file name of yocto.env (kernel)" 0 "$([ -s "$K7/deploy/Image" ]; echo $?)"
same "raw = the ext4 payload" 0 "$(cmp -s "$RFS" "$TMP/rootfs.ext4"; echo $?)"
same "kernel copied" 0 "$(cmp -s "$K7/deploy/Image" "$K7/yoctoScarthgap/Image"; echo $?)"
same "modes 444" "444 444" "$(mode_of "$RFS") $(mode_of "$K7/deploy/Image")"
same "deploy/SHA256SUMS verifies" 0 "$(cd "$K7/deploy" && sha256sum -c --quiet SHA256SUMS > /dev/null 2>&1; echo $?)"
same "SOURCE.txt names the qcow2's sha256" 1 "$(grep -c "^source_qcow2_sha256=$(sha256sum "$K7/yoctoScarthgap/yoctoScarthgap.qcow2" | cut -d' ' -f1)$" "$K7/deploy/SOURCE.txt")"
out=$(prep "DRY=0; kit_deploy '$K7'; echo \"rc=\$? state=\$DEPLOY_STATE msg=\$DEPLOY_MSG\"")
has "second call: present" "rc=0 state=present" "$out"
same "second call: one conversion in all" 1 "$(grep -c '^qemu-img convert' "$LOGF")"
K7b=$TMP/k7b/egw-demo-kit-20990101
mkdir -p "$K7b/yoctoScarthgap"
head -c 65536 /dev/urandom > "$TMP/noise"
fake_qcow2 "$TMP/noise" "$K7b/yoctoScarthgap/yoctoScarthgap.qcow2"
cp "$K7/yoctoScarthgap/Image" "$K7b/yoctoScarthgap/"
out=$(prep "DRY=0; kit_deploy '$K7b'; echo \"rc=\$? msg=\$DEPLOY_MSG\"")
has "not ext4: refused (3)" "rc=3" "$out"
has "not ext4: named" "not an unpartitioned ext4" "$out"
same "not ext4: nothing left" "" "$(find "$K7b/deploy" -type f)"
K7c=$TMP/k7c/egw-demo-kit-20990101
mkdir -p "$K7c/yoctoScarthgap"
cp "$K7/yoctoScarthgap/yoctoScarthgap.qcow2" "$K7/yoctoScarthgap/Image" "$K7c/yoctoScarthgap/"
out=$(prep "DRY=1; kit_deploy '$K7c'; echo \"rc=\$? state=\$DEPLOY_STATE msg=\$DEPLOY_MSG\"")
has "dry run: would" "rc=0 state=would" "$out"
same "dry run: no deploy folder" 1 "$([ -e "$K7c/deploy" ]; echo $?)"

echo "== 8. make_demo_kit.sh (stand-in package and controller archive)"
# make_package DIR [variant ...]: a stand-in for the sanitised package: a test key made here, a "qcow2"
# whose payload is a real ext4 holding authorized_keys (the test key) and an ssh-like binary with the key
# markers but no key body, an empty data disk (ext4 with lost+found only), BUILDINFO naming the key and
# the clean final scan, SHA256SUMS.
make_package() {
    local d=$1 r v e j w
    shift
    v=" $* "
    r=$TMP/rootsrc.$RANDOM$RANDOM
    e=$TMP/datasrc.$RANDOM$RANDOM
    w=$TMP/extrasrc.$RANDOM$RANDOM
    mkdir -p "$d/keys" "$r/home/egw/.ssh" "$r/opt/egw/deployment/data/events" "$r/usr/bin" "$e" "$w/etc"
    case $v in *" data-file "*) printf 'left behind\n' > "$e/events.log" ;; esac
    case $v in
        *" data-raw "*) head -c 65536 /dev/urandom > "$TMP/data.payload" ;;
        *) make_rootfs "$e" && mv "$TMP/rootfs.ext4" "$TMP/data.payload" || return 1 ;;
    esac
    case $v in
        *" backing "*) j='{"format": "qcow2", "backing-filename": "base.qcow2"}' ;;
        *" data-ext "*) j='{"format": "qcow2", "format-specific": {"type": "qcow2", "data": {"data-file": "data.raw"}}}' ;;
        *) j= ;;
    esac
    fake_qcow2 "$TMP/data.payload" "$d/data.qcow2" "$j"
    rm -rf "$e" "$TMP/data.payload"
    ssh-keygen -q -t ed25519 -N '' -C 'egw comparison images local test key' -f "$d/keys/egw_compare_share" > /dev/null || return 1
    cp "$d/keys/egw_compare_share.pub" "$r/home/egw/.ssh/authorized_keys"
    case $v in *" ak-extra "*)
        ssh-keygen -q -t ed25519 -N '' -f "$r/extra" > /dev/null && cat "$r/extra.pub" >> "$r/home/egw/.ssh/authorized_keys" && rm -f "$r/extra" "$r/extra.pub" ;;
    esac
    case $v in *" key-tail "*) printf 'MOSQUITTO_SIMULATOR_PASSWORD=abc123def\n' >> "$d/keys/egw_compare_share" ;; esac
    printf '%s\n\0%s\n\0' "$PEM_B_SSH" "$PEM_E_SSH" > "$r/usr/bin/fake-ssh"
    case $v in *" rootfs-env "*) printf 'A=1\n' > "$r/opt/egw/deployment/.env" ;; esac
    case $v in *" rootfs-pem "*) printf '%s\n%s\n%s\n' "$PEM_B_RSA" "$(head -c 120 /dev/urandom | base64 -w 64)" "$PEM_E_RSA" > "$r/usr/bin/key.pem" ;; esac
    # a file whose first line is the assignment, after a file (a-filler, written first) whose last block
    # ends in zero padding (rootfs-pw) or in 4096 bytes of text without a line break (rootfs-pw-blk)
    case $v in *" rootfs-pw "* | *" rootfs-pw-blk "*)
        mkdir -p "$r/opt/egw/conf"
        case $v in
            *" rootfs-pw "*) printf 'x\n' > "$r/opt/egw/conf/a-filler" ;;
            *) head -c 4096 /dev/zero | tr '\0' x > "$r/opt/egw/conf/a-filler" ;;
        esac
        printf 'ADMIN_PASSWORD=abc123def\n' > "$r/opt/egw/conf/notes.conf" ;;
    esac
    make_rootfs "$r" || return 1
    case $v in *" snap "*) j='{"format": "qcow2", "snapshots": [{"id": "1", "name": "pilot"}]}' ;; *) j= ;; esac
    fake_qcow2 "$TMP/rootfs.ext4" "$d/yoctoScarthgap.qcow2" "$j"
    head -c 65536 /dev/urandom > "$d/Image"
    printf '# stand-in package\n' > "$d/README.md"
    printf '#!/bin/sh\necho stand-in\n' > "$d/run-linux.sh"
    {
        printf 'replaced: /home/egw/.ssh/authorized_keys -> only the test key: %s\n' "$(ssh-keygen -lf "$d/keys/egw_compare_share.pub")"
        case $v in *" no-clean "*) ;; *) printf '  final scan clean\n' ;; esac
    } > "$d/BUILDINFO.txt"
    case $v in *" env-file "*) printf 'A=1\n' > "$d/.env" ;; esac
    case $v in *" pem "*) printf '%s\n%s\n%s\n' "$PEM_B_RSA" "$(head -c 120 /dev/urandom | base64 -w 64)" "$PEM_E_RSA" > "$d/notes.txt" ;; esac
    case $v in *" pw-env "*) printf 'MOSQUITTO_SIMULATOR_PASSWORD=abc123def\n' > "$d/conf.txt" ;; esac
    case $v in *" pw-text "*) printf 'db_password = hunter2\n' > "$d/notes2.txt" ;; esac
    # an assignment right after a NUL byte, with no line break in the 512 bytes before it
    case $v in *" pw-nul "*) { head -c 600 /dev/zero | tr '\0' x; printf '\0ADMIN_PASSWORD=abc123def\n'; } > "$d/notes.bin" ;; esac
    case $v in *" ext4 "*) cp "$TMP/rootfs.ext4" "$d/rootfs.ext4" ;; esac
    # the sealed image's deploy name, compressed; disk images by their names (the content does not matter)
    case $v in *" sealed-gz "*) gzip -n -c "$TMP/rootfs.ext4" > "$d/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4.gz" ;; esac
    case $v in *" wic "*) head -c 4096 /dev/urandom > "$d/egw-image.wic" ;; esac
    case $v in *" wic-xz "*) head -c 4096 /dev/urandom > "$d/egw-image.wic.xz" ;; esac
    case $v in *" rootfs-ext4x "*) head -c 4096 /dev/urandom > "$d/image.rootfs.ext4-old" ;; esac
    # a compressed ext4 under a neutral name (its first 1024 bytes are zero, which opens as an empty tar)
    # holding a private key
    case $v in *" gz-ext4 "* | *" tgz-ext4 "*)
        printf '%s\n%s\n%s\n' "$PEM_B_RSA" "$(head -c 120 /dev/urandom | base64 -w 64)" "$PEM_E_RSA" > "$w/etc/hidden.key"
        make_rootfs "$w" || return 1
        case $v in *" gz-ext4 "*) gzip -n -c "$TMP/rootfs.ext4" > "$d/disk.img.gz" ;; *) gzip -n -c "$TMP/rootfs.ext4" > "$d/backup.tar.gz" ;; esac
        rm -f "$w/etc/hidden.key" ;;
    esac
    # a qcow2 known only by its magic: a data disk that is not empty
    case $v in *" img-extra "*)
        printf 'left behind\n' > "$w/etc/events.log"
        make_rootfs "$w" && fake_qcow2 "$TMP/rootfs.ext4" "$d/extra.img" || return 1 ;;
    esac
    # disk images inside an archive, which this scan cannot read
    case $v in *" tar-qcow2 "* | *" tar-vmdk "*)
        rm -rf "$w" && mkdir -p "$w" && head -c 4096 /dev/urandom > "$TMP/disk.payload"
        case $v in
            *" tar-qcow2 "*) fake_qcow2 "$TMP/disk.payload" "$w/disk.qcow2" && tar -C "$w" -czf "$d/bundle.tar.gz" disk.qcow2 ;;
            *) { printf 'KDMV'; cat "$TMP/disk.payload"; } > "$w/disk.vmdk" && tar -C "$w" -czf "$d/bundle.tar.gz" disk.vmdk ;;
        esac
        rm -f "$TMP/disk.payload" ;;
    esac
    (cd "$d" && find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS)
    case $v in *" sums-bad "*) printf 'x' >> "$d/README.md" ;; esac
    rm -rf "$r" "$w"
}
# make_controller DIR [variant]: an OCI-layout archive with one gzip layer whose Python source holds
# 'password=None' (not a hit), and its identity record.
make_controller() {
    local d=$1 v=" ${2:-} " w
    w=$TMP/ctl.$RANDOM$RANDOM
    mkdir -p "$d" "$w/layer/app" "$w/oci/blobs/sha256"
    printf 'def connect(host, password=None):\n    return host, password\n' > "$w/layer/app/client.py"
    case $v in *" layer-env "*) printf 'A=1\n' > "$w/layer/app/.env" ;; esac
    case $v in *" layer-pem "*) printf '%s\n%s\n%s\n' "$PEM_B_RSA" "$(head -c 120 /dev/urandom | base64 -w 64)" "$PEM_E_RSA" > "$w/layer/app/server.pem" ;; esac
    tar -C "$w/layer" -cf - . | gzip -n > "$w/blob"
    mv "$w/blob" "$w/oci/blobs/sha256/$(sha256sum "$w/blob" | cut -d' ' -f1)"
    case $v in
        *" layer-zstd "*)
            # the zstd frame magic and some bytes: a layer the scan cannot open
            { printf '\050\265\057\375'; head -c 256 /dev/urandom; } > "$w/blob"
            mv "$w/blob" "$w/oci/blobs/sha256/$(sha256sum "$w/blob" | cut -d' ' -f1)" ;;
        *" layer-xz-pem "*)
            mkdir -p "$w/xzlayer/etc"
            printf '%s\n%s\n%s\n' "$PEM_B_RSA" "$(head -c 120 /dev/urandom | base64 -w 64)" "$PEM_E_RSA" > "$w/xzlayer/etc/hidden.key"
            tar -C "$w/xzlayer" -cf - . | python3 -I -c 'import lzma, sys; sys.stdout.buffer.write(lzma.compress(sys.stdin.buffer.read()))' > "$w/blob"
            mv "$w/blob" "$w/oci/blobs/sha256/$(sha256sum "$w/blob" | cut -d' ' -f1)" ;;
    esac
    printf '{"schemaVersion": 2}\n' > "$w/oci/index.json"
    printf '[]\n' > "$w/oci/manifest.json"
    printf '{"imageLayoutVersion": "1.0.0"}\n' > "$w/oci/oci-layout"
    tar -C "$w/oci" -cf "$d/egw-controller-0.1.0-arm64.tar" blobs index.json manifest.json oci-layout
    printf 'identity_format=1\nimage_ref=egw-controller:0.1.0\nsource_tree_state=clean\narchive_sha256=%s\n' \
        "$(sha256sum "$d/egw-controller-0.1.0-arm64.tar" | cut -d' ' -f1)" > "$d/egw-controller-0.1.0-arm64.identity.txt"
    case $v in *" record-bad "*) sed -i "s/^archive_sha256=.*/archive_sha256=$(printf '%064d' 0)/" "$d/egw-controller-0.1.0-arm64.identity.txt" ;; esac
    rm -rf "$w"
}
# mk OUTDIR PKG IMAGES [args...]: make_demo_kit.sh in the clean environment.
mk() {
    local o=$1 p=$2 i=$3
    shift 3
    envrun bash "$SETUP/make_demo_kit.sh" --package "$p" --images "$i" --out "$o" --date 20990101 --qemu-img "$STUB/qemu-img" "$@"
}
P8=$TMP/p8
I8=$TMP/i8
make_package "$P8"
make_controller "$I8"
: > "$LOGF"
out=$(mk "$TMP/out8" "$P8" "$I8"); rc=$?
ZIP=$TMP/out8/egw-demo-kit-20990101.zip
same "kit built: exit 0" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out" | sed 's/^/      | /'
has "kit built: KIT line" "KIT egw-demo-kit-20990101" "$out"
has "the scan reports no hit" ": 0 hit(s)" "$out"
has "the empty data disk is read and scanned" "1 other disk image(s)" "$out"
same "qemu-img info on each disk image before its conversion" "info convert info convert" \
    "$(grep -oE '^qemu-img (info|convert)' "$LOGF" | cut -d' ' -f2 | paste -sd' ' -)"
same "zip and .sha256 present" 0 "$([ -s "$ZIP" ] && [ -s "$ZIP.sha256" ]; echo $?)"
same ".sha256 matches the zip" 0 "$(cd "$TMP/out8" && sha256sum -c --quiet egw-demo-kit-20990101.zip.sha256 > /dev/null 2>&1; echo $?)"
hasnt "no private-key text printed" "$PK" "$out"
listing=$(python3 -I -c '
import stat, sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as zf:
    for i in zf.infolist():
        print(i.filename, oct(stat.S_IMODE(i.external_attr >> 16)))
' "$ZIP")
same "one top folder" "egw-demo-kit-20990101" "$(printf '%s\n' "$listing" | cut -d/ -f1 | sort -u)"
for f in README.txt SHA256SUMS controller/egw-controller-0.1.0-arm64.tar controller/egw-controller-0.1.0-arm64.identity.txt \
    yoctoScarthgap/SHA256SUMS yoctoScarthgap/yoctoScarthgap.qcow2 yoctoScarthgap/data.qcow2 yoctoScarthgap/Image yoctoScarthgap/BUILDINFO.txt yoctoScarthgap/keys/egw_compare_share.pub; do
    same "zip holds $f" 1 "$(printf '%s\n' "$listing" | grep -c "^egw-demo-kit-20990101/$f ")"
done
same "the private test key ships with mode 600" "egw-demo-kit-20990101/yoctoScarthgap/keys/egw_compare_share 0o600" \
    "$(printf '%s\n' "$listing" | grep '/keys/egw_compare_share 0o')"
same "run-linux.sh ships executable" 1 "$(printf '%s\n' "$listing" | grep -c '/run-linux.sh 0o755$')"
out=$(mk "$TMP/out8" "$P8" "$I8"); rc=$?
same "existing zip: exit 2" 2 "$rc"
has "existing zip: never overwritten" "never overwritten" "$out"
out=$(mk "$REPO/kit-out" "$P8" "$I8"); rc=$?
same "--out inside the clone: exit 2" 2 "$rc"
same "--out inside the clone: nothing created" 1 "$([ -e "$REPO/kit-out" ]; echo $?)"
# refusal PKG-VARIANT CONTROLLER-VARIANT EXPECTED-TEXT: the kit is refused with exit 3 and no zip.
refusal() {
    local p=$TMP/pr.$RANDOM$RANDOM i=$TMP/ir.$RANDOM$RANDOM o=$TMP/or.$RANDOM$RANDOM out rc
    # shellcheck disable=SC2086
    make_package "$p" $1
    make_controller "$i" "$2"
    out=$(mk "$o" "$p" "$i")
    rc=$?
    same "refused [$1|$2]: exit 3" 3 "$rc"
    has "refused [$1|$2]: reason" "$3" "$out"
    same "refused [$1|$2]: no zip" "" "$(find "$o" -name '*.zip*' 2> /dev/null)"
    hasnt "refused [$1|$2]: no private-key text printed" "$PK" "$out"
}
refusal env-file "" "the package lists .env"
refusal pem "" "notes.txt: pem"
refusal pw-env "" "conf.txt: env"
refusal pw-text "" "notes2.txt: text (password assignment on line(s) 1)"
refusal "" layer-env "!./app/.env: name"
refusal "" layer-pem "server.pem: pem"
refusal rootfs-env "" "rootfs:/opt/egw/deployment/.env: present"
refusal rootfs-pem "" "rootfs (raw): pem (1 complete"
refusal ak-extra "" "authorized_keys: does not hold exactly the shipped test key"
refusal sums-bad "" "does not match its own SHA256SUMS"
refusal ext4 "" "the package lists rootfs.ext4"
refusal no-clean "" "records no clean final secret scan"
refusal "" record-bad "does not match its identity record"
refusal data-file "" "yoctoScarthgap/data.qcow2: the file system holds more than an empty lost+found"
refusal data-raw "" "yoctoScarthgap/data.qcow2: not an unpartitioned ext4 file system"
refusal "" layer-zstd "zstd-compressed data, which this scan cannot open"
refusal "" layer-xz-pem "hidden.key: pem"
refusal sealed-gz "" "the package lists egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4.gz"
refusal wic "" "the package lists egw-image.wic"
refusal wic-xz "" "the package lists egw-image.wic.xz"
refusal rootfs-ext4x "" "the package lists image.rootfs.ext4-old"
refusal gz-ext4 "" "disk.img.gz: pem"
refusal tgz-ext4 "" "backup.tar.gz: pem"
refusal img-extra "" "yoctoScarthgap/extra.img: the file system holds more than an empty lost+found"
refusal tar-qcow2 "" "bundle.tar.gz!disk.qcow2: disk (a qcow2 image"
refusal tar-vmdk "" "bundle.tar.gz!disk.vmdk: disk (a VMDK image"
refusal rootfs-pw "" "rootfs (raw): env (1 PASSWORD"
refusal rootfs-pw-blk "" "rootfs (raw): env (1 PASSWORD"
refusal pw-nul "" "notes.bin: env"
refusal key-tail "" "keys/egw_compare_share: the allowed test key is not one OpenSSH private key alone"
refusal snap "" "yoctoScarthgap/yoctoScarthgap.qcow2: 1 internal snapshot(s)"
refusal backing "" "yoctoScarthgap/data.qcow2: a backing file"
refusal data-ext "" "yoctoScarthgap/data.qcow2: an external data file"

echo "== 9. the kit in step 4 (zip from section 8)"
KS='parse_args --kit "$Z"; step_kit'
H9=$TMP/home9
mkdir -p "$H9"
out=$(prep HOME="$H9" Z="$ZIP" 'parse_args --kit "$Z" --dry-run; step_kit'); rc=$?
same "dry run: exit 0" 0 "$rc"
has "dry run: WOULD extract" "[4/11] kit: WOULD extract egw-demo-kit-20990101" "$out"
same "dry run: nothing written" "" "$(find "$H9" -mindepth 1)"
: > "$LOGF"
out=$(prep HOME="$H9" Z="$ZIP" "$KS"); rc=$?
KT=$H9/egw-kit/egw-demo-kit-20990101
same "extracted: exit 0" 0 "$rc"
has "extracted: OK" "[4/11] kit: OK (egw-demo-kit-20990101: zip .sha256 present, SHA256SUMS verified, extracted done, root file system converted" "$out"
same "extracted: kit SHA256SUMS verifies" 0 "$(cd "$KT" && sha256sum -c --quiet SHA256SUMS > /dev/null 2>&1; echo $?)"
same "extracted: the key kept mode 600" 600 "$(mode_of "$KT/yoctoScarthgap/keys/egw_compare_share")"
same "extracted: no work folder left" "" "$(find "$H9/egw-kit" -maxdepth 1 -name '.extract.*')"
same "converted root file system in place" 0 "$([ -s "$KT/deploy/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4" ]; echo $?)"
b9=$(snap "$H9")
out=$(prep HOME="$H9" Z="$ZIP" "$KS"); rc=$?
has "re-run: SKIP" "[4/11] kit: SKIP" "$out"
same "re-run: HOME unchanged" "$b9" "$(snap "$H9")"
same "re-run: one conversion in all" 1 "$(grep -c '^qemu-img convert' "$LOGF")"
# run-linux.sh of the package keeps its overlays and known_hosts in yoctoScarthgap/work/.
mkdir -p "$KT/yoctoScarthgap/work"
printf 'overlay\n' > "$KT/yoctoScarthgap/work/root.qcow2"
out=$(prep HOME="$H9" Z="$ZIP" "$KS"); rc=$?
same "re-run after run-linux.sh (work/ present): exit 0" 0 "$rc"
has "re-run after run-linux.sh (work/ present): SKIP" "[4/11] kit: SKIP" "$out"
rm -rf "$KT/yoctoScarthgap/work"
# Another kit with the same date (another package) must not pass as the extracted one.
P8b=$TMP/p8b
make_package "$P8b"
out=$(mk "$TMP/out8b" "$P8b" "$I8"); rc=$?
same "a second kit of the same date built" 0 "$rc"
out=$(prep HOME="$H9" Z="$TMP/out8b/egw-demo-kit-20990101.zip" "$KS"); rc=$?
same "a different kit over the extracted one: exit 3" 3 "$rc"
has "a different kit over the extracted one: named" "holds a different kit than $TMP/out8b/egw-demo-kit-20990101.zip" "$out"
mkdir -p "$TMP/z1"
cp "$ZIP" "$TMP/z1/"
printf '%064d  egw-demo-kit-20990101.zip\n' 0 > "$TMP/z1/egw-demo-kit-20990101.zip.sha256"
out=$(prep HOME="$TMP/home9a" Z="$TMP/z1/egw-demo-kit-20990101.zip" "$KS"); rc=$?
same ".sha256 mismatch: exit 3" 3 "$rc"
has ".sha256 mismatch: named" "does not match $TMP/z1/egw-demo-kit-20990101.zip.sha256" "$out"
mkdir -p "$TMP/z2" "$TMP/home9b/egw-kit/.extract.stale01"
printf 'left by an interrupted run\n' > "$TMP/home9b/egw-kit/.extract.stale01/part"
cp "$ZIP" "$TMP/z2/"
out=$(prep HOME="$TMP/home9b" Z="$TMP/z2/egw-demo-kit-20990101.zip" "$KS"); rc=$?
same "no .sha256: exit 0" 0 "$rc"
has "no .sha256: warned" "WARN: no $TMP/z2/egw-demo-kit-20990101.zip.sha256" "$out"
has "no .sha256: OK" "zip .sha256 absent" "$out"
same "a stale extraction folder removed" "" "$(find "$TMP/home9b/egw-kit" -maxdepth 1 -name '.extract.*')"
chmod u+w "$KT/controller/egw-controller-0.1.0-arm64.identity.txt"
printf 'extra=1\n' >> "$KT/controller/egw-controller-0.1.0-arm64.identity.txt"
out=$(prep HOME="$H9" Z="$ZIP" "$KS"); rc=$?
same "tampered extracted file: exit 3" 3 "$rc"
has "tampered extracted file: named" "exists but does not verify" "$out"
# badzip NAME ENTRY...: a zip whose entries are ENTRY (each a file holding 'x').
badzip() {
    local z=$TMP/$1
    shift
    python3 -I -c '
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w") as zf:
    for n in sys.argv[2:]:
        zf.writestr(n, "x")
' "$z" "$@"
    printf '%s' "$z"
}
Z=$(badzip evil.zip egw-demo-kit-20990101/README.txt ../evil)
out=$(prep HOME="$TMP/home9c" Z="$Z" "$KS"); rc=$?
same "entry climbing out (..): exit 3" 3 "$rc"
has "entry climbing out (..): named" "unsafe entry name" "$out"
same "entry climbing out: nothing extracted" 1 "$([ -e "$TMP/home9c/egw-kit" ]; echo $?)"
Z=$(badzip two.zip egw-demo-kit-20990101/README.txt other/README.txt)
out=$(prep HOME="$TMP/home9c" Z="$Z" "$KS"); rc=$?
same "two top folders: exit 3" 3 "$rc"
has "two top folders: named" "exactly one top folder" "$out"
Z=$(badzip abs.zip /etc/passwd)
out=$(prep HOME="$TMP/home9c" Z="$Z" "$KS"); rc=$?
same "absolute entry: exit 3" 3 "$rc"
# a zip whose inner SHA256SUMS no longer matches one of its files
python3 -I -c '
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as src, zipfile.ZipFile(sys.argv[2], "w") as dst:
    for i in src.infolist():
        data = src.read(i)
        if i.filename.endswith("/README.txt"):
            data += b"changed\n"
        dst.writestr(i, data)
' "$ZIP" "$TMP/inner.zip"
out=$(prep HOME="$TMP/home9d" Z="$TMP/inner.zip" "$KS"); rc=$?
same "inner SHA256SUMS mismatch: exit 3" 3 "$rc"
has "inner SHA256SUMS mismatch: the file named" "README.txt" "$out"
same "inner SHA256SUMS mismatch: no kit folder, no work folder" "" "$(find "$TMP/home9d/egw-kit" -mindepth 1 2> /dev/null)"
python3 -I -c '
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as src, zipfile.ZipFile(sys.argv[2], "w") as dst:
    for i in src.infolist():
        dst.writestr(i, src.read(i))
    dst.writestr("egw-demo-kit-20990101/unlisted.txt", "x")
' "$ZIP" "$TMP/unlisted.zip"
out=$(prep HOME="$TMP/home9e" Z="$TMP/unlisted.zip" "$KS"); rc=$?
same "unlisted file in the kit: exit 3" 3 "$rc"
has "unlisted file in the kit: named" "not listed in the kit's SHA256SUMS: unlisted.txt" "$out"

echo "== 10. the whole script on the stand-in clone"
H10=$TMP/home10
mkdir -p "$H10"
: > "$LOGF"
b10=$(snap "$H10")
out=$(envrun HOME="$H10" bash "$PREP" --kit "$ZIP" --dry-run); rc=$?
same "dry run: exit 0" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out" | sed 's/^/      | /'
same "dry run: eleven step lines" 11 "$(printf '%s\n' "$out" | grep -cE '^\[([1-9]|1[01])/11\] ')"
hasnt "dry run: no STOP" "STOP" "$out"
same "dry run: HOME unchanged" "$b10" "$(snap "$H10")"
same "dry run: no sudo, curl, apt-get, convert or QEMU boot" "" "$(grep -E '^(sudo|curl|apt-get|qemu-img convert|qemu-system-aarch64|tf.sh|compare_env.sh)' "$LOGF")"
same "dry run: nothing written in the stand-in clone" "" "$(find "$CLONE/tools/compare" -name .terraform)"
out=$(envrun HOME="$H10" STUB_DPKG=missing bash "$PREP" --kit "$ZIP" --dry-run)
has "dry run, packages missing: the apt list" "[2/11] apt packages: WOULD install with sudo apt-get: $(prep 'printf %s "$APT_PACKAGES"')" "$out"
out=$(envrun HOME="$H10" bash "$PREP" --kit "$ZIP" --dry-run --no-debian)
has "--no-debian: step 10 SKIP" "[10/11] debian 13: SKIP (--no-debian" "$out"
out=$(envrun HOME="$H10" STUB_PGREP_RC=0 bash "$PREP" --kit "$ZIP" --dry-run); rc=$?
same "a QEMU running: step 10 refuses (exit 2)" 2 "$rc"
has "a QEMU running: never stopped" "is never stopped by this script" "$out"
out=$(envrun HOME="$H10" STUB_SS_LINE='LISTEN 0 128 127.0.0.1:8883 0.0.0.0:*' bash "$PREP" --kit "$ZIP" --dry-run); rc=$?
same "a busy port: step 10 refuses (exit 2)" 2 "$rc"
has "a busy port: named" "already have a listener: 8883" "$out"
: > "$LOGF"
out=$(envrun HOME="$TMP/home10z" bash "$PREP" --kit "$TMP/z1/egw-demo-kit-20990101.zip"); rc=$?
same "a damaged ZIP: exit 3" 3 "$rc"
has "a damaged ZIP: stopped in step 1" "[1/11] host checks: STOP: $TMP/z1/egw-demo-kit-20990101.zip does not match" "$out"
hasnt "a damaged ZIP: nothing installed first" "[2/11]" "$out"
same "a damaged ZIP: no sudo, curl or apt-get" "" "$(grep -E '^(sudo|curl|apt-get)' "$LOGF")"
# Step 3 alone: it marks the state root as this script's and removes a download folder left by an
# interrupted run (the curl stub fails, so it stops there).
H10t=$TMP/home10t
mkdir -p "$H10t/egw-compare/bin/.download.stale01"
out=$(prep HOME="$H10t" 'parse_args --kit /x/k.zip; step_terraform'); rc=$?
same "step 3, download failing: exit 1" 1 "$rc"
same "step 3: the state root marked" 0 "$([ -s "$H10t/egw-compare/.egw-demo-host" ]; echo $?)"
same "step 3: no download folder left (stale or new)" "" "$(find "$H10t/egw-compare/bin" -maxdepth 1 -name '.download.*')"
# Step 2 alone, for a user who may run every command without a password while another sudoers rule
# (the sudo group's) still asks for one: there 'sudo -v' asks for a password, 'sudo true' does not. The
# step must not wait for a password nobody types (the apt stand-in installs nothing, so it stops after).
stub sudo 'echo "sudo $*" >> "$STUB_LOG"; [ "${1:-}" != -v ] || { echo "sudo: a password is required" >&2; exit 1; }'
: > "$LOGF"
out=$(prep HOME="$TMP/home10s" STUB_DPKG=missing 'parse_args --kit /x/k.zip; step_apt'); rc=$?
same "step 2, sudo without a password: stops only after apt-get (exit 1)" 1 "$rc"
hasnt "step 2, sudo without a password: not refused" "sudo refused" "$out"
has "step 2, sudo without a password: apt-get ran" "sudo env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 update" "$(cat "$LOGF")"
hasnt "step 2, sudo without a password: no 'sudo -v'" "sudo -v" "$(cat "$LOGF")"
stub sudo 'echo "sudo $*" >> "$STUB_LOG"; exit 99'
# The ROM of the virtio network card: Ubuntu 24.04's ipxe-qemu installs it in /usr/lib/ipxe/qemu (on
# QEMU's firmware path), other builds in /usr/share/qemu; found in either folder, no warning.
mkdir -p "$TMP/rom_a" "$TMP/rom_b" && : > "$TMP/rom_b/efi-virtio.rom"
out=$(prep EGW_SETUP_ROM_DIRS="$TMP/rom_a $TMP/rom_b" 'qemu_check')
hasnt "QEMU check, ROM in the second folder: no warning" "WARN" "$out"
out=$(prep EGW_SETUP_ROM_DIRS="$TMP/rom_a" 'qemu_check')
has "QEMU check, ROM in no folder: a warning naming the folders" "WARN: efi-virtio.rom (package ipxe-qemu) is in none of: $TMP/rom_a;" "$out"
# A real run with every external step stubbed: Terraform present (in a state root this script marked),
# a venv whose python answers the import check, tf.sh and compare_env.sh stubs in the stand-in clone.
mkdir -p "$H10/egw-compare/bin" "$H10/.local/share/egw-demo/venv/bin"
: > "$H10/egw-compare/.egw-demo-host"
printf '#!/bin/sh\necho "Terraform v1.16.6"\necho "on linux_amd64"\n' > "$H10/egw-compare/bin/terraform"
printf '#!/bin/sh\necho "%s"\n' "$CLONE/src/egw_simulator" > "$H10/.local/share/egw-demo/venv/bin/python"
chmod 0755 "$H10/egw-compare/bin/terraform" "$H10/.local/share/egw-demo/venv/bin/python"
: > "$LOGF"
out=$(envrun HOME="$H10" bash "$PREP" --kit "$ZIP"); rc=$?
same "real run (stubbed): exit 0" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out" | sed 's/^/      | /'
for want in "[1/11] host checks: OK" "[2/11] apt packages: SKIP" "[3/11] terraform: SKIP" "[4/11] kit: OK" "[5/11] ssh key: OK" \
    "[6/11] secrets file: OK" "[7/11] python venv: SKIP" "[8/11] settings: OK" "[9/11] terraform init: OK" "[10/11] debian 13: OK" "[11/11] summary: OK"; do
    has "real run: $want" "$want" "$out"
done
has "real run: next commands" "bash tools/demo/demo.sh" "$out"
has "real run: first apply is longer" "pulls the five pinned container images" "$out"
has "real run: QEMU caveat" "not the 8.2.7 of the recorded measurements" "$out"
same "real run: key installed, mode 600" 600 "$(mode_of "$H10/.ssh/egw_compare_share")"
same "real run: tf.sh init for both scenarios" "tf.sh yocto init|tf.sh debian13 init" "$(grep '^tf.sh' "$LOGF" | paste -sd '|')"
same "real run: Debian prepared with the download allowed and Ubuntu's QEMU path from the settings" \
    "compare_env.sh prepare debian13 allow=1 qemu=$STUB/qemu-system-aarch64" "$(grep '^compare_env.sh' "$LOGF")"
same "real run: no sudo, curl or apt-get" "" "$(grep -E '^(sudo|curl|apt-get)' "$LOGF")"
SECRETS10=$H10/.config/egw-demo/deployment.env
for n in MOSQUITTO_SIMULATOR_PASSWORD MOSQUITTO_CONTROLLER_PASSWORD DITTO_DEVOPS_PASSWORD; do
    secret_absent "real run: $n value not printed" "$(sed -n "s/^$n=//p" "$SECRETS10")" "$out"
done
b10=$(snap "$H10")
: > "$LOGF"
out=$(envrun HOME="$H10" bash "$PREP" --kit "$ZIP"); rc=$?
same "re-run: exit 0" 0 "$rc"
same "re-run: steps 2-10 all SKIP" 9 "$(printf '%s\n' "$out" | grep -cE '^\[([2-9]|10)/11\] [a-z0-9 ]+: SKIP')"
same "re-run: HOME unchanged" "$b10" "$(snap "$H10")"
same "re-run: nothing called" "" "$(grep -E '^(sudo|curl|apt-get|qemu-img convert|tf.sh|compare_env.sh)' "$LOGF")"
# A re-run from a login shell, where the settings file of the first run is already exported: this
# script's own settings are not another set-up.
out=$(envrun HOME="$H10" bash -c '. "$1" && bash "$2" --kit "$3"' x "$H10/.config/egw-demo/env.sh" "$PREP" "$ZIP"); rc=$?
same "re-run with the settings exported: exit 0" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out" | sed 's/^/      | /'
same "re-run with the settings exported: steps 2-10 all SKIP" 9 "$(printf '%s\n' "$out" | grep -cE '^\[([2-9]|10)/11\] [a-z0-9 ]+: SKIP')"
same "re-run with the settings exported: HOME unchanged" "$b10" "$(snap "$H10")"
out=$(envrun HOME="$H10" bash -c '. "$1" && EGW_COMPARE_SSH_KEY=$HOME/.ssh/other bash "$2" --kit "$3"' x "$H10/.config/egw-demo/env.sh" "$PREP" "$ZIP"); rc=$?
same "a setting changed by hand: exit 2" 2 "$rc"
has "a setting changed by hand: refused in step 1" "[1/11] host checks: STOP: EGW_COMPARE_SSH_KEY is already set ($H10/.ssh/other)" "$out"

echo "== 11. static rules"
SRC_FILES=("$SETUP/prepare_demo_host.sh" "$SETUP/make_demo_kit.sh" "$SETUP/README.md")
# assembled from parts, so that this line does not match itself; the guest user's /home/egw is no person's
PERSONAL="rui""sth|rui""mf|/home/[a-z]+/|C:\\\\Users\\\\[A-Za-z]"
same "no personal paths" "" "$(for f in "${SRC_FILES[@]}" "$SETUP/tests/offline_check.sh"; do sed 's#/home/egw/##g' "$f" | grep -niE "$PERSONAL" | sed "s#^#${f##*/}:#"; done)"
same "no process is killed" "" "$(grep -nwE 'kill|pkill|killall' "$SETUP/prepare_demo_host.sh" "$SETUP/make_demo_kit.sh")"
same "no set -x" "" "$(grep -nE '^[[:space:]]*set -[a-z]*x' "${SCRIPTS[@]}")"
same "no key material in the sources" "" "$(grep -nE '^[A-Za-z0-9+/]{60,}={0,2}$' "${SRC_FILES[@]}" "$SETUP/tests/offline_check.sh")"

echo "== 12. the settings as the real tools read them"
# The settings file of step 8 for the kit extracted in section 9 (its deploy/ holds the two base files),
# then the REAL tools/compare/lib.sh, scenarios/yocto.env and tools/demo/lib.sh of this clone resolve it,
# so that a renamed or misspelt variable on either side fails here.
H12=$TMP/home12
mkdir -p "$H12"
prep HOME="$H12" EGW_SETUP_QEMU= EGW_SETUP_QEMU_IMG= "parse_args --kit /x/k.zip; KIT_TOP='$KT'; step_settings" > /dev/null
ENV12=$H12/.config/egw-demo/env.sh
got=$(env -i HOME="$H12" PATH="$PATH0" bash -c '. "$1" && . "$2/tools/compare/lib.sh" && scenario_load yocto \
    && printf "%s|%s|%s|%s|%s|%s" "$BASE_ROOTFS_SRC" "$BASE_KERNEL_SRC" "$COMPARE_QEMU" "$COMPARE_QEMU_IMG" "$COMPARE_SSH_KEY" "$COMPARE_ROOT"' x "$ENV12" "$REPO" 2>&1)
IFS='|' read -r rfs12 ker12 rest12 <<< "$got"
same "tools/compare (yocto): the root file system step 4 wrote" "$KT/deploy/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4|0" "$rfs12|$([ -s "$rfs12" ]; echo $?)"
same "tools/compare (yocto): the kernel step 4 wrote" "$KT/deploy/Image|0" "$ker12|$([ -s "$ker12" ]; echo $?)"
same "tools/compare: QEMU, qemu-img, key and state root from the settings" \
    "/usr/bin/qemu-system-aarch64|/usr/bin/qemu-img|$H12/.ssh/egw_compare_share|$H12/egw-compare" "$rest12"
got=$(env -i HOME="$H12" PATH="$PATH0" bash -c '. "$1" && . "$2/tools/demo/lib.sh" \
    && printf "%s|%s|%s|%s" "$DEMO_VENV" "$DEMO_SECRETS" "$DEMO_SSH_KEY" "$DEMO_COMPARE_ROOT"' x "$ENV12" "$REPO" 2>&1)
same "tools/demo: venv, secrets file, key and state root from the settings" \
    "$H12/.local/share/egw-demo/venv|$H12/.config/egw-demo/deployment.env|$H12/.ssh/egw_compare_share|$H12/egw-compare" "$got"
PS=$REPO/tools/compare/provision_stack.sh
same "provision_stack.sh reads EGW_COMPARE_SECRETS_ENV" 0 "$(grep -qF 'SECRETS=${EGW_COMPARE_SECRETS_ENV:-' "$PS"; echo $?)"
same "provision_stack.sh reads EGW_IMAGES_DIR" 0 "$(grep -qF 'IMAGES_DIR=${EGW_IMAGES_DIR:-' "$PS"; echo $?)"
same "provision_stack.sh's controller archive name" "$(prep 'printf %s "$CONTROLLER_TAR"')" "$(sed -n 's|^CTL_TAR=\$IMAGES_DIR/||p' "$PS")"
same "provision_stack.sh's identity record name" "$(prep 'printf %s "$CONTROLLER_RECORD"')" "$(sed -n 's|^CTL_RECORD=\$IMAGES_DIR/||p' "$PS")"
same "provision_stack.sh checks the four passwords step 6 fills" 0 \
    "$(grep -qF 'for name in MOSQUITTO_SIMULATOR_PASSWORD MOSQUITTO_CONTROLLER_PASSWORD EGW_MQTT_PASSWORD DITTO_DEVOPS_PASSWORD; do' "$PS"; echo $?)"

echo
echo "offline_check: $pass passed, $fail failed, $skip skipped"
[ "$fail" = 0 ]
