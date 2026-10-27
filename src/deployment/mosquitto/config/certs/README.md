# Mosquitto dev TLS material

This directory holds the development/campaign TLS material for the broker.
It is populated exclusively by `../../scripts/generate-dev-tls.sh` and is
**never committed to version control** (plan §9.2; see
`src/deployment/.gitignore`). Only this README is tracked.

## Files produced by the script

| File | Purpose | Committed |
|---|---|---|
| `ca.key` | Private key of the local dev CA (mode 600) | never |
| `ca.crt` | Dev CA certificate — distributed to MQTT clients (`--ca-cert` of the simulator, `EGW_MQTT_CA_CERT` of the controller) | never |
| `ca.srl` | OpenSSL serial bookkeeping | never |
| `server.key` | Broker private key (mode 600; owner becomes uid/gid 1883 — the broker's unprivileged user — after `scripts/prepare-broker-secrets.sh`) | never |
| `server.crt` | Broker certificate, signed by the dev CA | never |

## How they are generated

From `src/deployment/`:

```sh
# SAN = localhost, mosquitto, 127.0.0.1 (+ optional public host of the VM)
EGW_HOST=<vm-public-hostname-or-ip> ./scripts/generate-dev-tls.sh
# or: ./scripts/generate-dev-tls.sh --host <vm-public-hostname-or-ip>
```

- Local root CA (RSA 4096, `CN=EGW Dev Root CA`) and broker certificate
  (RSA 2048, `CN=mosquitto`), both SHA-256 and valid for **825 days**.
- The broker certificate carries `subjectAltName` entries for `localhost`
  (in-container healthcheck and local clients), `mosquitto` (compose service
  DNS name used by the controller) and `127.0.0.1`, plus the optional
  `EGW_HOST`/`--host` entry so the simulator running **outside** the VM can
  verify the broker identity (plan §5.1).
- Server-authentication only: `require_certificate false` in
  `mosquitto.conf`; client identity comes from username/password.

## Rules

- Regenerate at will (`--force` removes and recreates all four files);
  regeneration invalidates previously distributed `ca.crt` copies and must be
  followed by `scripts/prepare-broker-secrets.sh`.
- Copy **only** `ca.crt` to client machines; the two `.key` files never
  leave the VM.
- If any private key is exposed or accidentally staged for commit, treat it
  as compromised: delete the material, regenerate, and record the incident
  in the project LOG.
