# 0002 — SSI/ACA-Py is strictly conditional P1 behind gate G3 and outside all RQs

**Status:** Accepted (2026-08-07) — fixed by integrated plan sections 4.2, 4.4 and 8.1

## Context

Earlier project plans placed a decentralised-identity stack (Hyperledger Indy,
verifiable credentials, IPFS, Fabric) on the critical path. The September
deadline makes that scope infeasible, and none of the three definitive research
questions (RQ1 reproducible Yocto/ARM64 gateway, RQ2 correct/reliable ingestion,
RQ3 performance trade-offs) requires SSI. The plan states explicitly: "ACA-Py e
SSI não são necessários para responder a qualquer RQ" and closes the premise
that the thesis must be defensible with all P1 scope cut.

## Decision

- SSI is reduced to a minimal ACA-Py demonstration, classified **P1
  (conditional)**, and may only start after **gate G3 (30/08)** passes with the
  full P0 core complete and free of P0 defects (QEMU build/boot, clean ARM
  deploy, three devices, all scenarios, tests, metrics, soak).
- Total timebox: **12 hours**; automatic cut at timebox exhaustion or on
  **03/09**, whichever comes first.
- If attempted: image `ghcr.io/openwallet-foundation/acapy-agent:py3.13-1.6-lts`
  pinned by an ARM64-verified digest; `askar-anoncreds` wallet (not the
  deprecated `askar`); two local agents, `did:peer`, an Out-of-Band invitation
  and one basic DIDComm message. No public ledger, no Indy, no credential
  issuance, no ownership logic.
- Immediate cut triggers: no ARM64 image available, any P0 gate red, or timebox
  exhausted. ACA-Py is cut, never emulated (plan section 11).
- SSI appears in the thesis background only as context; no RQ, claim or
  conclusion depends on it.

## Consequences

- Positive: the critical path contains only P0 work; the thesis remains fully
  defensible if the demo never happens; scope-creep pressure has a documented,
  automatic answer.
- Negative: the C2DTA long-term vision (identity, marketplace) is represented
  only as future work; if the demo is cut, continuity with earlier SSI-heavy
  plans exists only at the architectural-discussion level.
- Any request to expand SSI scope must be rejected or traded explicitly against
  P0 hours via the plan's cut rules (plan section 11, risk "Âmbito volta a
  crescer").
