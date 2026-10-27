# Historical synthesis of the 2026-08-08 project reviews

> **NON-NORMATIVE / HISTORICAL.** This document condenses review material from
> the legacy `ChatGPT/` workspace. It preserves reasoning that remains useful;
> it does not copy code, override the integrated plan or report current project
> state. All counts, dates and findings from 8 August are historical unless
> independently revalidated against the current tree.

## Source identity

| Legacy source | SHA-256 |
|---|---|
| `ChatGPT/ANALISE_GESTAO_PROJETO_CLAUDE_2026-08-08.md` | `59cfefe3c1a0147a57c4bd2fb2fb93293d41e96b65430e643270b9173838017d` |
| `ChatGPT/REANALISE_GESTAO_PROJETO_CLAUDE_POS_CORRECOES_2026-08-08.md` | `59ad781047bdfb8b764c6668f42aab1c3b8ab3c90693bafe8293b3470e3ef636` |
| `ChatGPT/VERIFICACAO_P2_P1_P3_E_PLANO_P5_ANTES_P4_2026-08-08.md` | `fbfcbfd77134be1a9d11191568aec2e878843c6522a977dffdb5d8c37fb81f67` |
| `ChatGPT/DECISAO_FINAL_E_ORDEM_DE_TRABALHOS_CLAUDE_2026-08-08.md` | `b8319bb9e92fbe8c88e51c8bb7e32f13a4103e92c4514c128bfcaeffc32b3a90` |
| `ChatGPT/thesis/research/supervisor_questions_memo.md` | `ac9348904102f02dbf13f53528c35c73835018846434952c5dbe1129b35b9d59` |
| `ChatGPT/thesis/research/supervisor_decision_log.csv` | `2f57ddbc26e5da8ba0fa943bb61e148c488d00718c7ff8e63fd15e9f6cb6b1e3` |

The originals remain untouched in the legacy workspace. This synthesis is the
only material migrated into the active repository.

## Conclusions retained

1. **Existence, verification and acceptance are separate.** A file, test count,
   planned campaign or page count cannot close a gate. Every deliverable should
   report: implemented artefact, verification level/evidence, gate acceptance,
   and residual risk.
2. **Operational evidence controls progress.** At the review cut, the project
   had a strong scaffold but no live ARM64/MQTT/Ditto evidence. This distinction
   remains valid even though the exact test counts and implementation inventory
   have since changed.
3. **One state authority is required.** `PROGRESS.md` should own state; the
   backlog owns actions, the plan owns scope/gates and the diary owns history.
   Updating evidence without a cross-document truth sweep repeatedly caused
   drift.
4. **Theoretical work and implementation can advance in parallel, but neither
   substitutes for infrastructure.** The Chapter 2 standalone draft was a useful
   deliverable; WSL2, the ARM64 host, live integration and institutional searches
   remained operator-controlled dependencies.
5. **A micro-pilot must precede the official campaign.** Run a smoke, short
   nominal case, dropout/reconnect and restart; inspect every artefact manually
   and automatically before freezing the full protocol.
6. **Invalid runs must never influence results.** Wrong-host resources, missing
   evidence, incomplete identities, failed external actions, insufficient
   repetitions or corrupted checksums require exclusion/invalid status, not
   partial success.
7. **Raw evidence is write-once.** Recollection or repetition must create a new
   run identity and lineage. Silent replacement invalidates auditability.
8. **No scope reopening while critical evidence is missing.** ACA-Py/SSI and
   other extensions must not displace the Yocto, vertical-slice, campaign and
   dissertation path.
9. **Academic wording must track reading depth and evidence.** Metadata
   verification is not full-text assessment; planned queries are not an
   executed review; results and conclusions must remain empty until data exists.
10. **Human effort is not inferred by an agent.** Planned, actual and remaining
    student hours are supplied by the student; tool/agent duration belongs only
    in the work diary.

## Findings superseded or requiring revalidation

- The original inventories (139/148 tracked files), test totals
  (400/452/515), commit counts, absence of remotes and short Chapter 2 figures
  describe earlier cuts and must not appear as current facts.
- Several P1/P5 harness defects were subsequently corrected and covered by the
  later sealed unit suite. Their historical discovery is useful, but closure
  must be checked from current code and evidence rather than inferred here.
- WSL2 later became operational and produced G1 build evidence. The measurement
  VM and live integration remain governed by current `PROGRESS.md`.
- The old instruction to advance P2→P1→P3 was a time-bounded management choice,
  not a permanent delivery sequence.
- The legacy supervisor memo was never sent. Its useful two-layer framing was
  migrated into the current proposal and decision log, with D007 and D008 added;
  it confers no approval.

## Residual review principles for future gates

At each gate, verify all of the following from current records:

- the tested tree/commit is identifiable and reachable, with rewrite lineage
  retained where applicable;
- checksums pass before any aggregation;
- the environment manifest describes the system under test, not the load host;
- live dependencies were actually exercised where the claim requires them;
- conditions, minimum repetitions and failure/recovery criteria match the
  frozen plan;
- `PROGRESS.md`, the claim matrix, risk register and diary describe the same
  evidence without upgrading its maturity;
- a gate decision is dated and attributable rather than implied.

## Historical review verdict, restated safely

The legacy reviews found a well-organised and ambitious foundation whose main
risk was optimistic interpretation of artefact existence. Their durable advice
is to prioritise external unblockers, theory suitable for supervisor review,
real platform/service evidence, validity of the experimental harness, and
continuous claim-to-evidence alignment. The exact present state must always be
read from the active repository's authoritative records.
