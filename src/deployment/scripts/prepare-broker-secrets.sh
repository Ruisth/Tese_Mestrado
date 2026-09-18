#!/bin/sh
# prepare-broker-secrets.sh — make the broker's private key and password file
# readable by the UNPRIVILEGED user the broker runs as, keep them closed to
# everyone else, and prove it before `docker compose up`.
#
# Why (sources consulted 2026-09-18):
#   * Mosquitto 2.x, when started as root, loads the configuration file and
#     drops to the unprivileged "mosquitto" user BEFORE it opens keyfile,
#     certfile, password_file and acl_file
#     (https://mosquitto.org/documentation/migrating-to-2-0/ ; src/mosquitto.c
#     of v2.0.22: config__parse_args -> drop_privileges ->
#     mosquitto_security_init -> listeners__start).
#   * In the official eclipse-mosquitto 2.0.x image that user is uid 1883 /
#     gid 1883 ("addgroup -S -g 1883 mosquitto", "adduser -S -u 1883 ...
#     mosquitto" in docker/2.0-openssl/Dockerfile of
#     https://github.com/eclipse-mosquitto/mosquitto, the directory the
#     Docker official-images manifest names for the tags 2.0.22 / 2.0).
#   * The image entrypoint runs "chown -R mosquitto:mosquitto /mosquitto ||
#     true" as root, but compose.yaml bind-mounts these files READ-ONLY, so
#     that chown fails (read-only file system) and the failure is swallowed.
#   A server.key left 0600 for the operator, or a passwd left root:root 0640,
#   is therefore unreadable by the broker and the broker exits at start-up.
#
# What it does:
#   apply (default)  passwd and certs/server.key -> owner BROKER_UID:BROKER_GID,
#                    mode 0600 (only if they differ; privileges are used only
#                    then). With --acl also acl -> same owner, mode 0640, which
#                    silences the Mosquitto 2.0.22 "owner is not mosquitto" /
#                    "world readable" warnings for acl_file. Do NOT use --acl
#                    in a git checkout: acl is a tracked file and git must be
#                    able to read it as the operator.
#   check (always)   (1) no secret (passwd, server.key, ca.key) has any
#                        permission bit for "others";
#                    (2) a one-shot container of the pinned broker image,
#                        started as BROKER_UID:BROKER_GID with the same
#                        read-only mounts as compose.yaml, must be able to
#                        read acl, passwd, ca.crt, server.crt and server.key
#                        and must NOT be able to read ca.key;
#                    (3) BROKER_UID and BROKER_GID must equal the uid and gid
#                        of the image's "mosquitto" user. Any difference is an
#                        ERROR, also for explicitly set ids: compose.yaml has
#                        no "user:" key for the broker, so the broker always
#                        drops to the image's user, and Mosquitto 2.0.22 warns
#                        when the group of password_file/acl_file is not its
#                        own (lib/misc_mosq.c: st_gid != getgid()).
#                    mosquitto.conf is tested too, but an unreadable
#                    mosquitto.conf is only a NOTE: it is the one file the
#                    broker reads as root, before the drop; the unprivileged
#                    user needs it only for a SIGHUP reload.
#   Exit 0 = the broker can read what it needs; 1 = do NOT start the stack;
#   2 = usage error.
#
# Usage:
#   ./prepare-broker-secrets.sh [--check] [--acl]
#     --check   verify only: change nothing, never call sudo
#     --acl     also hand the acl file to the broker user (guest copy only)
#
# Environment:
#   EGW_BROKER_UID / EGW_BROKER_GID  numeric ids (default 1883 / 1883, from
#                                    the official image source; never 0).
#                                    Only for an image whose "mosquitto" user
#                                    has other ids: check (3) fails unless
#                                    they match that image.
#   EGW_BROKER_IMAGE   image reference for the one-shot container; default:
#                      IMAGE_MOSQUITTO from LOCK_FILE. On the offline Yocto
#                      guest set it to the loaded tag, e.g.
#                      docker.io/library/eclipse-mosquitto:2.0.22
#   LOCK_FILE          default ../images.lock.env
#   CONF_DIR           default ../mosquitto/config
#   EGW_BROKER_PRIV    auto (default) | sudo | docker | none
#                      how to change ownership when not already root:
#                      auto   = sudo if "sudo -n true" works (no prompt), else
#                               docker; a password prompt is the last resort,
#                               used only when the docker method failed and
#                               stdin is a terminal;
#                      docker = chown/chmod from a one-shot root container of
#                               the broker image (the operator already has
#                               docker access; no sudo needed);
#                      none   = never escalate (fails if a change is needed).
#
# POSIX sh; works in BusyBox ash (needs: stat -c, id, sed, head, docker).

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEPLOY_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
CONF_DIR="${CONF_DIR:-$DEPLOY_DIR/mosquitto/config}"
LOCK_FILE="${LOCK_FILE:-$DEPLOY_DIR/images.lock.env}"
BROKER_UID="${EGW_BROKER_UID:-1883}"
BROKER_GID="${EGW_BROKER_GID:-1883}"
PRIV="${EGW_BROKER_PRIV:-auto}"

CHECK_ONLY=0
WITH_ACL=0

usage() {
    sed -n '2,81p' "$0" | sed 's/^# \{0,1\}//'
}

die() {
    echo "ERROR: $1" >&2
    [ -n "${2:-}" ] && echo "       $2" >&2
    exit "${3:-1}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK_ONLY=1; shift ;;
        --acl)   WITH_ACL=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

case "$BROKER_UID" in ''|*[!0-9]*) die "EGW_BROKER_UID must be numeric: '$BROKER_UID'" "" 2 ;; esac
case "$BROKER_GID" in ''|*[!0-9]*) die "EGW_BROKER_GID must be numeric: '$BROKER_GID'" "" 2 ;; esac
[ "$BROKER_UID" -ne 0 ] || die "EGW_BROKER_UID=0 refused: the broker must not run as root" "" 2
case "$PRIV" in
    auto|sudo|docker|none) ;;
    *) die "EGW_BROKER_PRIV must be auto, sudo, docker or none: '$PRIV'" "" 2 ;;
esac

command -v docker >/dev/null 2>&1 || die "docker CLI not found in PATH"
[ -d "$CONF_DIR" ] || die "config directory not found: $CONF_DIR"
CONF_DIR=$(CDPATH= cd -- "$CONF_DIR" && pwd)

IMAGE="${EGW_BROKER_IMAGE:-}"
if [ -z "$IMAGE" ] && [ -f "$LOCK_FILE" ]; then
    IMAGE=$(sed -n 's/^IMAGE_MOSQUITTO=//p' "$LOCK_FILE" | head -n 1)
fi
[ -n "$IMAGE" ] || die "no broker image reference" \
    "set EGW_BROKER_IMAGE or provide IMAGE_MOSQUITTO in $LOCK_FILE"

# --- 0. inputs must exist ------------------------------------------------------
missing=0
for rel in mosquitto.conf acl passwd certs/ca.crt certs/server.crt certs/server.key; do
    if [ ! -f "$CONF_DIR/$rel" ]; then
        echo "ERROR: missing: $CONF_DIR/$rel" >&2
        missing=1
    fi
done
[ "$missing" -eq 0 ] || die "broker inputs incomplete" \
    "run scripts/generate-dev-tls.sh and scripts/generate-dev-auth.sh first"

owner_mode() {
    # prints "<uid>:<gid> <octal mode>"; needs only search permission on the
    # directory, not read permission on the file.
    stat -c '%u:%g %a' "$1"
}

# "<mode>:<path relative to CONF_DIR>" of every file this script manages.
TARGETS="600:passwd 600:certs/server.key"
[ "$WITH_ACL" -eq 1 ] && TARGETS="$TARGETS 640:acl"

# --- 1. apply ownership and modes (only when something differs) -----------------
if [ "$CHECK_ONLY" -eq 0 ]; then
    pending=""
    for t in $TARGETS; do
        mode=${t%%:*}; rel=${t#*:}
        if [ "$(owner_mode "$CONF_DIR/$rel")" = "$BROKER_UID:$BROKER_GID $mode" ]; then
            echo "OK: $rel already $BROKER_UID:$BROKER_GID mode $mode"
        else
            pending="$pending $t"
        fi
    done

    apply_sudo() {
        # Returns non-zero at the first failure (no reliance on "set -e",
        # which is inactive when a function is called in a condition).
        for t in $pending; do
            mode=${t%%:*}; rel=${t#*:}
            sudo chown "$BROKER_UID:$BROKER_GID" "$CONF_DIR/$rel" || return 1
            sudo chmod "$mode" "$CONF_DIR/$rel" || return 1
        done
        return 0
    }

    apply_docker() {
        # Root inside a throw-away container of the broker image; the
        # config directory is mounted read-write for this step only.
        # $pending is a list of fixed literals: splitting is intended.
        # shellcheck disable=SC2086
        docker run --rm --network none --user 0:0 --entrypoint /bin/sh \
            -v "$CONF_DIR:/work" "$IMAGE" -c '
                set -eu
                owner=$1; shift
                for t in "$@"; do
                    mode=${t%%:*}; rel=${t#*:}
                    chown "$owner" "/work/$rel"
                    chmod "$mode" "/work/$rel"
                done' sh "$BROKER_UID:$BROKER_GID" $pending
    }

    if [ -n "$pending" ]; then
        method=$PRIV
        if [ "$(id -u)" -eq 0 ]; then
            method=direct
        elif [ "$PRIV" = "auto" ]; then
            # Never prompt first: the guest account has no usable password,
            # so an interactive sudo could only fail there. Docker access is
            # already a precondition of this script (read test below).
            if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
                method=sudo
            else
                method=docker
            fi
        fi
        echo "Changing ownership/mode of:$pending (method: $method)"
        case "$method" in
            direct)
                for t in $pending; do
                    mode=${t%%:*}; rel=${t#*:}
                    chown "$BROKER_UID:$BROKER_GID" "$CONF_DIR/$rel"
                    chmod "$mode" "$CONF_DIR/$rel"
                done ;;
            sudo)
                command -v sudo >/dev/null 2>&1 || die "sudo not found" \
                    "re-run with EGW_BROKER_PRIV=docker"
                apply_sudo || die "sudo chown/chmod failed" \
                    "re-run with EGW_BROKER_PRIV=docker"
                ;;
            docker)
                if apply_docker; then
                    :
                elif [ "$PRIV" = "auto" ] && command -v sudo >/dev/null 2>&1 && [ -t 0 ]; then
                    echo "NOTE: the docker method failed; last resort: sudo (may ask for a password)." >&2
                    apply_sudo || die "ownership change failed through docker and through sudo" \
                        "is the image '$IMAGE' present (offline guest: set EGW_BROKER_IMAGE to the loaded tag)?"
                else
                    die "ownership change through docker failed" \
                        "is the image '$IMAGE' present (offline guest: set EGW_BROKER_IMAGE to the loaded tag)?"
                fi
                ;;
            none)
                die "ownership/mode change needed but EGW_BROKER_PRIV=none" \
                    "as root: chown $BROKER_UID:$BROKER_GID <file> && chmod <mode> <file> for:$pending" ;;
        esac
        for t in $pending; do
            mode=${t%%:*}; rel=${t#*:}
            got=$(owner_mode "$CONF_DIR/$rel")
            [ "$got" = "$BROKER_UID:$BROKER_GID $mode" ] \
                || die "$rel is '$got' after the change, expected '$BROKER_UID:$BROKER_GID $mode'" \
                       "if the docker method was used under rootless Docker or userns-remap, re-run with EGW_BROKER_PRIV=sudo"
            echo "OK: $rel now $BROKER_UID:$BROKER_GID mode $mode"
        done
    fi
fi

failures=0

# --- 2. host-side: secrets must carry no permission bit for "others" ------------
for rel in passwd certs/server.key certs/ca.key; do
    [ -e "$CONF_DIR/$rel" ] || continue          # ca.key may be kept offline
    om=$(owner_mode "$CONF_DIR/$rel")
    mode=${om#* }
    others=${mode#"${mode%?}"}
    if [ "$others" != "0" ]; then
        echo "ERROR: $rel is accessible to others (owner:group mode = $om)" >&2
        failures=$((failures + 1))
    else
        echo "OK: $rel closed to others ($om)"
    fi
done
for t in $TARGETS; do
    mode=${t%%:*}; rel=${t#*:}
    om=$(owner_mode "$CONF_DIR/$rel")
    if [ "$om" != "$BROKER_UID:$BROKER_GID $mode" ]; then
        echo "NOTE: $rel is '$om', not '$BROKER_UID:$BROKER_GID $mode'; the read test below decides." >&2
        echo "      (Mosquitto 2.0.22 logs a warning when password_file/acl_file are not owned by its user.)" >&2
    fi
done

# --- 3. decisive test: read as the broker uid, same mounts as compose.yaml -----
echo "Read test as uid:gid $BROKER_UID:$BROKER_GID in a one-shot container of: $IMAGE"
rc=0
docker run --rm --network none --user "$BROKER_UID:$BROKER_GID" --entrypoint /bin/sh \
    -v "$CONF_DIR/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" \
    -v "$CONF_DIR/acl:/mosquitto/config/acl:ro" \
    -v "$CONF_DIR/passwd:/mosquitto/config/passwd:ro" \
    -v "$CONF_DIR/certs:/mosquitto/config/certs:ro" \
    "$IMAGE" -c '
        rc=0
        me=$(id -u)
        mygid=$(id -g)
        img=$(id -u mosquitto 2>/dev/null || echo unknown)
        imggid=$(id -g mosquitto 2>/dev/null || echo unknown)
        # compose.yaml sets no "user:" for the broker, so it always drops to
        # the image user: other ids prove nothing, explicitly set or not.
        if [ "$img" = "$me" ] && [ "$imggid" = "$mygid" ]; then
            echo "OK: $me:$mygid is the image user \"mosquitto\" (uid:gid)"
        else
            echo "ERROR: image user \"mosquitto\" is $img:$imggid (uid:gid), but the secrets were prepared and tested for $me:$mygid" >&2
            echo "       set EGW_BROKER_UID/EGW_BROKER_GID to the image values (or unset them) and re-run without --check" >&2
            rc=1
        fi
        # mosquitto.conf is read as root before the privilege drop, so start-up
        # does not depend on this; a SIGHUP reload happens after the drop.
        if cat /mosquitto/config/mosquitto.conf >/dev/null 2>&1; then
            echo "OK: uid $me reads mosquitto.conf"
        else
            echo "NOTE: uid $me cannot read mosquitto.conf: start-up is not affected (the broker reads it as root, before dropping privileges), but a SIGHUP reload would fail. chmod 644 it: it holds no secret." >&2
        fi
        for f in acl passwd certs/ca.crt certs/server.crt certs/server.key; do
            if cat "/mosquitto/config/$f" >/dev/null 2>&1; then
                echo "OK: uid $me reads $f"
            else
                echo "ERROR: uid $me CANNOT read /mosquitto/config/$f - the broker would exit at start-up" >&2
                rc=1
            fi
        done
        if cat /mosquitto/config/certs/ca.key >/dev/null 2>&1; then
            echo "ERROR: uid $me can read certs/ca.key - the CA key must stay closed to the broker (chmod 600, operator-owned)" >&2
            rc=1
        fi
        exit $rc' || rc=$?

if [ "$rc" -ge 125 ]; then
    echo "ERROR: the one-shot container could not be started (docker exit $rc)." >&2
    echo "       Image present? Offline guest: EGW_BROKER_IMAGE=<loaded tag>. Nothing was verified." >&2
    failures=$((failures + 1))
elif [ "$rc" -ne 0 ]; then
    echo "       If a certs/ file fails although its mode is right, check that the certs" >&2
    echo "       directory is searchable by others: chmod 755 $CONF_DIR/certs" >&2
    failures=$((failures + 1))
fi

echo
if [ "$failures" -gt 0 ]; then
    echo "FAILED: broker secrets are not ready. Do NOT start the stack." >&2
    exit 1
fi
echo "OK: the broker user ($BROKER_UID:$BROKER_GID) can read its key, certificates, password file and ACL;"
echo "    no secret is open to others."
