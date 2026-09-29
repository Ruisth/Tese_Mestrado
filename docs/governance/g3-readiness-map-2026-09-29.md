# G3 readiness map (2026-09-29)

**A map, not a decision.** For each of the nine integration and recovery
families, this page states what G3 requires, what exists today on the option-5
candidate, and what remains before a qualifying run. It changes no criterion,
threshold, load or scope, runs nothing, and makes none of the decisions it
names. G3 stays `Not decided` in the
[gate decision log](gate_decision_log.md) and the pause on qualifying runs
stays in force ([PROGRESS](../../PROGRESS.md), G3 bullet). The proof's own
exceptions — E-12's admission of the restart sampling gap and the N1 naming of
[ADR 0011](../adr/0011-controller-restart-recovery.md) — apply to the finite
proof only and are assumed nowhere below.

**What G3 requires.** The criterion is the plan's
([integrated plan](INTEGRATED_DEVELOPMENT_PLAN_2026.md), *G3 — P0 feature
freeze*): the nine families of the runbook
([`qemu_integrated_gateway.md`](../setup/qemu_integrated_gateway.md) §7) in
order on **one unchanged image and container set**, each meeting its own
Expected list; the public contracts frozen; no open P0 defect, the
`ditto-things` memory incident resolved or explicitly bounded; every failed run
kept; no threshold moved. The battery of 2026-09-18 ran on an older candidate
and was never admitted; it does not count, and its results below are context
only.

**Legend.** *Ready*: the procedure exists and needs only a qualifying run on
the frozen candidate — procedural readiness, never a passed run. *Pending*:
offline work or an unrun sub-check comes first. *Blocked*: under the unchanged
rules it cannot give a valid pass without a separate decision.

## The nine families

| Family | Status | Current evidence (context only) | Remaining action or blocker | Evidence expected |
|---|---|---|---|---|
| **T1** repeated smoke, harness artefacts | Pending | 2026-09-18 ad-hoc runs on the old candidate; harness runs `smoke_sequence-r01/-r02` invalid; `nominal-r01` (2026-09-19) instrumentation valid, delivery failed its deadline | Wire the run-scoped log and event capture into the runbook's `harness_cmd`, which today passes no `--fetch-*-log-cmd`; the short-run rule for resource instants is still unadopted | Three `TEST STATUS` records with `check`/`delta`; one sealed harness run directory |
| **T2** three wearables | Ready | 672 of 672 in time, the last acknowledgement 3.1 s before the deadline | Run on the frozen candidate; the small margin is a risk, not a blocker | `reconcile.json` with `lost=0`, `late=0`; every `delta` `OK`; twin readback |
| **T3** invalid payloads | Pending (minor) | 67 rejected, none accepted, no valid message rejected; 132 of 1,277 valid messages late | The rejections must be read from a run-scoped controller log; `docker compose logs` returns the container's whole history. T3's Expected list has no deadline item: whether T3 is a timed family under throughput choice T1 is an open question (decision 3 below) | `check` fields; run-scoped controller-log excerpt |
| **T4** duplicates **and sequence reset** | Pending | 672 duplicates, none accepted twice. **`itest-dup-02` (sequence reset) has never run** | Run both parts. Under option 5 a reconnection adds duplicates, which can break "duplicate = replayed count"; whether such duplicates fail T4 is an open question (decision 5 below) | dup-01: replay copies, twins `same`; **dup-02**: `reconcile` with `lost=0`, every `delta` `OK` |
| **T5** dropout and reconnection | Pending, high risk of failure | **Failed**: 326 of 2,016 late | Run it and record the result; option 5 does not change timing, and under throughput choice T1 (ADR 0011, decision B) a family that misses its deadline is recorded as failed. The broker grep reads the whole log: bound it | stderr totals, run-scoped broker excerpt, `lost`/`late`, `delta` |
| **T6** controller restart | **Blocked** | `controller_restart-r01/-r02` invalid; the finite proof r03 supported recovery for that run only, with its harness run invalid and a twin `delta` `MISMATCH` | Four blockers, below: the restart resource gap, N1 under the ordinary rules, zero-lost at 11.2 msg/s never shown, and log/event capture not wired into the runbook harness. The normal-sampler defect is repaired in this block | A sealed **valid** run directory; C12 columns of `per_run.csv`; every `delta` `OK`; restart record; run-scoped logs and events |
| **T7** MongoDB **and Ditto** fault | Pending | MongoDB half only (old candidate): 62 failed, 1,012 of 3,298 late. **`itest-ditto-fault-01` has never run** | Run both halves. The MongoDB result is not reusable: contract v1.2 changed the meaning of `failed`. Watch `ditto-things` at its 768 MiB limit. The Docker stop/start events of each fault come from the recorder | `fault.txt`, `ready.txt`, outcome counts, `delta`, stop/start events |
| **T8** guest reboot | Pending | Shown on the old candidate: 336 events, 0 lost, 0 late | Not yet assessed: a reboot while the broker holds the controller's persistent session (60 s autosave; ADR 0011 open item). Bound the `ditto-things` power-off incident | Boot IDs, container state, previous-boot journal (OOM check), twins `same`, post-reboot smoke with `lost=0`, `late=0` |
| **T9** TLS and authorisation | Pending (log scoping) | Tested checks passed on the old candidate, anonymous refusal included; negative cases remain G3 work | Run again: the broker configuration changed (C1), the ACL did not (C2 declined). T9(b) and (c) take their evidence from the broker's log (`docker compose logs --tail 20 mosquitto`), which is not scoped to the run: a run-scoped broker log copy is a prerequisite, as for T3, T5 and T7 | `verdict.txt` = `PASS` (an inconclusive result is never a pass), subscriber outputs, run-scoped broker excerpt for (b) and (c), `/metrics` unchanged |

## The issues the work order names

**1. The normal sampler.** Until 2026-09-29 the default controller-metrics
sampler let a typed `http.client.HTTPException` (such as `IncompleteRead`, a
kill between a response's headers and its body) end its thread, or raise from
the entry poll; for T6 a dead sampler would have removed the post-restart rows
and C12 would have failed on instrumentation. This block repairs it (LOG
#C046): the failure is a counted failed poll in every mode. r03 did not exercise
the defect (its failures were `RemoteDisconnected` and connection resets, which
are `OSError`s). **Deferred, with a trigger:** `poll_controller_marker` in
`run.py` still catches only `OSError` and `ValueError`, so a typed failure
there would leave the run without a manifest — to be repaired **before any
qualifying G3 run that uses `--controller-url`**. An I/O error writing a CSV
row still ends the sampler's thread silently; that is a design decision for the
same trigger.

**2. The resource gap at a restart.** `MAX_SAMPLE_GAP_S` = 5 s applies to every
container series; an excess gap rejects `resources.csv` and the harness marks
the run invalid. Every restart recorded so far exceeded it:

| Run | Gap at the restart |
|---|---|
| `controller_restart-r01` | 9.0 s (and later 6.0 s gaps) |
| `controller_restart-r02` | 6.0 s |
| Finite proof r01 / r02 / r03 | 8.0 s / 9.0 s / 8.0 s |

A collector cannot sample a container that is down, so a faster collector does
not remove the gap. The lifecycle-aware rule is proposed, not adopted. Until a
prospective decision, T6's harness run stays invalid; the rule touches only the
harness families (T1, T6), since T5, T7 and T8 run through `run_test` and ingest
no resources.

**3. N1, `delta` and loss under the ordinary rules.** `lost` is a valid message
without a unique confirmation inside the 60 s window. An N1 identity has only a
`duplicate` line, so it **counts as `lost`** until the separate decision ADR
0011 reserves, which fails C12's zero-lost; it also makes `delta` report a twin
surplus as `MISMATCH`, which fails T6's "every `delta` line OK". It is not a
double acceptance. Every proof kill produced one; whether a graceful restart
also does is unknown.

**4. Timed delivery.** The option-5 candidate has never been measured against
its deadlines on a valid run.

| Run | Finding |
|---|---|
| `nominal-r01` (2026-09-19) | 3,794 of 6,720 in the window; 6.457 msg/s served over the measured window (60 s blocks 5.32–8.55 msg/s) against 11.2 offered (ADR 0011, section 1) |
| T5 / T3 / T7 (MongoDB), 2026-09-18 | 326 of 2,016 / 132 of 1,277 / 1,012 of 3,298 late |
| T2, 2026-09-18 | in time, with a 3.1 s margin |
| T6 recovery bound | 120 s (`RESTART_RECOVERY_MAX_S`), never shown on a qualifying run |

Under throughput choice T1 (ADR 0011, decision B) each timed family that misses
its deadline is recorded as failed, so G3 is not met on it; whether T3, whose
Expected list names no deadline, is one of them is decision 3 below.

**5. Logs and Docker events.** r03's controller and broker logs were not scoped
to the run and its Docker events did not cover the kill. This block, in the
proof driver (`tools/session/proof.sh`), bounds both log copies by the run's
guest-clock boundaries and adds a continuous event recorder whose coverage is
judged, tested with stubs only; its first use on a guest is still to come, and
the runbook's harness command and the families that read logs (T1, T3, T5, T6,
T7 and T9(b)/(c)) are not yet wired to it.

**6. Other G3 conditions.** The candidate lock record is pending. The contracts
are at v1.2 while the backlog's cut rule still names v1.1: a freeze record is
needed. The `ditto-things` incident is mitigated, not declared stable. Whether
`gate_health.sh`, `accounted` and `delta` share `drained`'s former wall-clock
blind spot is not assessed. The broker window and queue (W, Q) against the
families' backlogs is open. There is no versioned battery driver.

## Decisions to surface (none made here)

1. Adopt or decline the lifecycle-aware restart rule, prospectively. Until then
   T6 stays invalid.
2. The analysis rule for N1 identities. Until then any N1 in T6 is a loss and a
   `MISMATCH`, and T6 fails.
3. Timed families that miss their deadlines are recorded as failed; which
   families are timed (T3's late confirmations among them) and any change to
   G3's scope need a dated prospective decision.
4. The candidate lock and the authorisation to resume the qualifying battery.
5. Whether duplicates added by a reconnection under option 5 fail T4's
   "duplicate = replayed count", or are reported beside it.
