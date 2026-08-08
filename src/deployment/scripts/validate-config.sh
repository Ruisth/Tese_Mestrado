#!/bin/sh
# validate-config.sh — pre-deploy sanity gate for the EGW compose stack.
#
# Run from anywhere; it operates on the deployment directory it lives in.
# Checks, in order:
#   1. .env exists (copied from .env.example) and contains no CHANGE_ME
#      placeholder values;
#   2. TLS material exists (ca.crt, server.crt, server.key from
#      scripts/generate-dev-tls.sh);
#   3. the Mosquitto password file exists (scripts/generate-dev-auth.sh);
#   4. every IMAGE_* entry in images.lock.env is pinned by @sha256 digest
#      (plan §9.2);
#   5. ./data/events exists (created here so the bind mount is owned by the
#      invoking user, not root — the controller runs as uid 1000);
#   6. `docker compose config -q` accepts the merged configuration.
#
# Exit code 0 = safe to `up`; anything else = do NOT deploy.
#
# Usage:
#   ./validate-config.sh

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEPLOY_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
CERT_DIR="$DEPLOY_DIR/mosquitto/config/certs"

failures=0

fail() {
    echo "ERROR: $1" >&2
    [ -n "${2:-}" ] && echo "       $2" >&2
    failures=$((failures + 1))
}

# --- 1. .env -----------------------------------------------------------------
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    fail ".env not found in $DEPLOY_DIR" \
         "create it with: cp .env.example .env  (then fill in the CHANGE_ME values)"
elif grep -q 'CHANGE_ME' "$DEPLOY_DIR/.env"; then
    fail ".env still contains CHANGE_ME placeholder value(s)" \
         "set real passwords before deploying (never commit .env)"
else
    echo "OK: .env present, no placeholders"
fi

# --- 2. TLS material ---------------------------------------------------------
tls_missing=0
for f in ca.crt server.crt server.key; do
    if [ ! -f "$CERT_DIR/$f" ]; then
        tls_missing=1
        fail "TLS file missing: $CERT_DIR/$f"
    fi
done
if [ "$tls_missing" -eq 1 ]; then
    echo "       generate with: ./scripts/generate-dev-tls.sh [--host <vm-host>]" >&2
else
    echo "OK: TLS material present (ca.crt, server.crt, server.key)"
fi

# --- 3. Mosquitto password file ---------------------------------------------
if [ ! -f "$DEPLOY_DIR/mosquitto/config/passwd" ]; then
    fail "Mosquitto password file missing: mosquitto/config/passwd" \
         "generate with: ./scripts/generate-dev-auth.sh (passwords from .env or args)"
else
    echo "OK: Mosquitto password file present"
fi

# --- 4. image lock digests ---------------------------------------------------
LOCK_FILE="$DEPLOY_DIR/images.lock.env"
if [ ! -f "$LOCK_FILE" ]; then
    fail "images.lock.env not found: $LOCK_FILE"
else
    unpinned=$(grep -E '^IMAGE_[A-Z0-9_]+=' "$LOCK_FILE" | grep -v '@sha256:' || true)
    if [ -n "$unpinned" ]; then
        fail "images.lock.env has entries not pinned by digest:" "$unpinned"
        echo "       pin them with: ./scripts/resolve-image-lock.sh --update" >&2
    else
        n=$(grep -cE '^IMAGE_[A-Z0-9_]+=' "$LOCK_FILE")
        echo "OK: all $n image(s) in images.lock.env pinned by @sha256 digest"
    fi
fi

# --- 5. host event-log directory --------------------------------------------
# Must exist BEFORE `docker compose up`, otherwise docker creates the bind
# source as root and the non-root controller (uid 1000) cannot write to it.
if mkdir -p "$DEPLOY_DIR/data/events" 2>/dev/null; then
    echo "OK: data/events directory ready (bind mount for events.jsonl)"
else
    fail "could not create $DEPLOY_DIR/data/events"
fi

# --- 6. docker compose config ------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    fail "docker CLI not found in PATH"
elif [ -f "$DEPLOY_DIR/.env" ] && [ -f "$LOCK_FILE" ]; then
    # Same invocation shape as the real `up` (both env files, explicit).
    if (cd "$DEPLOY_DIR" && \
        docker compose --env-file .env --env-file images.lock.env config -q); then
        echo "OK: docker compose config accepted"
    else
        fail "docker compose config rejected the merged configuration (see above)"
    fi
else
    echo "SKIP: docker compose config (missing .env or images.lock.env)" >&2
fi

echo
if [ "$failures" -gt 0 ]; then
    echo "FAILED: $failures problem(s) found. Do NOT deploy." >&2
    exit 1
fi
echo "OK: configuration is complete and consistent. Safe to run:"
echo "    docker compose --env-file .env --env-file images.lock.env up -d --build"
