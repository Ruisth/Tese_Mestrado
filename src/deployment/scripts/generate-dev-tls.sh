#!/bin/sh
# generate-dev-tls.sh — create the local dev CA and the Mosquitto server
# certificate (TLS server-auth only; CONTRACTS.md §1, plan §5.2).
#
# Outputs into ../mosquitto/config/certs/ (never committed; see the README
# there): ca.key, ca.crt, server.key, server.crt.
#
# SAN entries: DNS:localhost, DNS:mosquitto, IP:127.0.0.1, plus an optional
# public hostname/IP of the ARM64 VM (so the external simulator can verify
# the broker) taken from --host or the EGW_HOST environment variable.
#
# Usage:
#   ./generate-dev-tls.sh [--host <name-or-ip>] [--cert-dir <dir>] [--force]
#
# Requires: openssl (3.x on Ubuntu 24.04).

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CERT_DIR="${CERT_DIR:-$SCRIPT_DIR/../mosquitto/config/certs}"
EXTRA_HOST="${EGW_HOST:-}"
FORCE=0
DAYS=825

usage() {
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --host)
            [ $# -ge 2 ] || { echo "ERROR: --host needs a value" >&2; exit 2; }
            EXTRA_HOST=$2; shift 2 ;;
        --cert-dir)
            [ $# -ge 2 ] || { echo "ERROR: --cert-dir needs a value" >&2; exit 2; }
            CERT_DIR=$2; shift 2 ;;
        --force)
            FORCE=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

command -v openssl >/dev/null 2>&1 || {
    echo "ERROR: openssl not found in PATH" >&2; exit 1;
}

mkdir -p "$CERT_DIR"

if [ "$FORCE" -ne 1 ]; then
    for f in ca.key ca.crt server.key server.crt; do
        if [ -e "$CERT_DIR/$f" ]; then
            echo "ERROR: $CERT_DIR/$f already exists; use --force to overwrite." >&2
            echo "       Overwriting invalidates every previously distributed ca.crt." >&2
            exit 1
        fi
    done
fi

SAN="DNS:localhost,DNS:mosquitto,IP:127.0.0.1"
if [ -n "$EXTRA_HOST" ]; then
    case "$EXTRA_HOST" in
        *[!0-9.]*) SAN="$SAN,DNS:$EXTRA_HOST" ;;   # contains non-digit/dot -> DNS name
        *)         SAN="$SAN,IP:$EXTRA_HOST" ;;    # dotted digits only -> IP
    esac
fi

echo "Generating dev CA and server certificate in: $CERT_DIR"
echo "subjectAltName: $SAN"
echo "validity: $DAYS days"

# --- local dev CA ----------------------------------------------------------
openssl genrsa -out "$CERT_DIR/ca.key" 4096
openssl req -x509 -new -key "$CERT_DIR/ca.key" -sha256 -days "$DAYS" \
    -subj "/O=C2DTA EGW dev/CN=EGW Dev Root CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -out "$CERT_DIR/ca.crt"

# --- broker key + CSR + CA-signed certificate ------------------------------
openssl genrsa -out "$CERT_DIR/server.key" 2048
openssl req -new -key "$CERT_DIR/server.key" \
    -subj "/O=C2DTA EGW dev/CN=mosquitto" \
    -out "$CERT_DIR/server.csr"

EXT_FILE="$CERT_DIR/server.ext.$$"
{
    printf 'subjectAltName=%s\n' "$SAN"
    printf 'basicConstraints=CA:FALSE\n'
    printf 'keyUsage=critical,digitalSignature,keyEncipherment\n'
    printf 'extendedKeyUsage=serverAuth\n'
} > "$EXT_FILE"

openssl x509 -req -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" -CAcreateserial \
    -days "$DAYS" -sha256 -extfile "$EXT_FILE" \
    -out "$CERT_DIR/server.crt"

rm -f "$CERT_DIR/server.csr" "$EXT_FILE"

# Private keys stay owner-only; certificates are public material. The broker
# container reads the key as root before dropping privileges, so 600 is safe.
chmod 600 "$CERT_DIR/ca.key" "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/ca.crt" "$CERT_DIR/server.crt"

echo
echo "Done. Server certificate:"
openssl x509 -in "$CERT_DIR/server.crt" -noout -subject -enddate -ext subjectAltName
echo
echo "Distribute ONLY ca.crt to MQTT clients (simulator --ca-cert /"
echo "controller EGW_MQTT_CA_CERT). Never commit anything from $CERT_DIR"
echo "except its README.md (see src/deployment/.gitignore)."
