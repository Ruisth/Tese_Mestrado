# Claim→evidence matrix

> Integrity instrument required by the integrated plan §6.3: **no quantitative
> value enters the final PDF without raw data, execution command,
> configuration and a reproduction path.** The data source for this matrix is
> [`claim_evidence_matrix.csv`](claim_evidence_matrix.csv) (same columns, same
> content); this file is the readable view.

## Maintenance rules

- Every verifiable statement in the dissertation (chapters 4–6, Abstract,
  Resumo) is given a `claim_id` before the text is written.
- Permitted validation states: `Pending — no evidence`, `In collection`, a
  partial state (`Partial — …` / `Bring-up evidence produced — …`) used when
  evidence exists but does not demonstrate the whole statement,
  `Validated (run_id + commit)` and `Removed from the text`. A partial row must
  name what is still outstanding and which gate owns it.
- A claim only becomes `Validated` when `evidence_file`, `analysis_script` and
  `config_commit` point at real, reproducible artefacts (data in
  `experiments/results/raw/<run_id>/` with `manifest.json` and `SHA256SUMS`).
- Claims that obtain no evidence by the data freeze (`data-v1`, 2026-09-13) are
  removed from the text or rewritten as a limitation — never filled in with a
  conclusion that has no evidence (plan §8.1, G5).
- The `run_id` values given here **are not conventions**: they are exactly the
  identifiers that `src/egw_experiments/plan_gen.py` generates from the
  conditions frozen in `src/egw_experiments/protocol.py`
  (`<condition>-r<NN>`, with the `qemu_boot` prefix for the `qemu_boots`
  condition and `load_sweep-<rate:03d>mps-r<rep:02d>` for the sweep). Any
  divergence between this matrix and the generator is a defect of this matrix.
- The `(planned)` markers were removed from the script columns on 2026-08-08:
  the analysis path (including the one for the external conditions), the SUT
  collectors and the metrics sampler **exist in the repository**. That is a
  statement about code, not about evidence: **code existing validates no claim
  whatsoever**, which is why 13 of the 15 claims still carry
  `Pending — no evidence` and none is validated.
- **Mandatory sealing of the evidence (blocks P5/P5.4).** Before a run
  directory is used for anything at all, its `SHA256SUMS` is verified. A run
  whose evidence **does not verify** stays out of summaries, saturation,
  acceptance and figures; an **unsealed** run of a timed condition is excluded
  in the same way. The same requirement now applies with equal severity to the
  **external** conditions (`timings.json`, C02/C04): only a run with a
  **verified** seal contributes to the duration statistics — unsealed and
  failed seal are both excluded and both warned about. Runs outside the frozen
  protocol (for example the G2 bring-up run that underpins C05) are **flagged**
  by the analysis, not excluded: for the purposes of this matrix, an unsealed
  bring-up run **is not acceptable evidence** for the claim.
- **Completeness by identity (block P5).** Acceptance per condition compares
  the **set of identities** of the valid runs — `run_id` plus repetition, seed
  and rate, per load level in the `load_sweep` — against the frozen plan;
  identities missing, extra, duplicated or swapped **fail** the criterion and
  are named. With no plan, the check degrades to counting and says explicitly
  that the identity check was **not** done. Corresponding operational
  requirement (risk R32 in [`g0/risks.md`](g0/risks.md)): the analysis that
  underpins these claims has to be run by the delivered command, with the
  frozen plan actually in use.
- **Blocking infrastructure dependency.** The ARM64 measurement VM **does not
  exist**: three providers failed (Oracle — home region fixed, no Ampere
  capacity; Hetzner — CAX sold out; Azure for Students — zero quota on every
  dedicated ARM family, and the burstable B series is barred from measurement
  because CPU credits would corrupt the load sweep and the saturation
  criterion). Every claim measured on that VM (C04 and the whole timed
  campaign, C06–C14) is therefore blocked on infrastructure, not merely on
  execution. QEMU does **not** stand in for it: the plan makes that platform
  functional-only, so a QEMU result never supports a performance or security
  statement.
- No statistical rule, percentile, CI method or the 60 s confirmation window
  was changed by these blocks: what changed was the instrumentation and the
  verification, not the protocol.

## Seeded claims (P0)

All 15 claims were created with the state `Pending — no evidence` on
2026-08-07 and still carried it on 2026-08-10. The 2026-08-11 seal moved
**C01** and **C02** to partial. On 2026-08-14, a new clean checkout/build at
`f0e19d5` and five fresh strict boots driven at `9fe38ff` were sealed without
overwriting the preliminary evidence or the first failed instrumentation
attempt. C01 remains partial pending D006/second-operator treatment and formal
admission. C02 remains partial because the strict G1 set is distinct from the
predefined later `data-v1` identities unless a dated protocol decision admits
it. The other **13 claims remain `Pending — no evidence`**.

**0 of the 15 claims are accepted**, and **no gate has been accepted**: G1
stays in progress — evidence produced, acceptance pending.
`experiments/results/raw/` is still empty; the preliminary G1 evidence and the
nested 2026-08-14 capsule live in `docs/evidence/g1-yocto-qemu/`, with separate
`SHA256SUMS` scopes that verify from a clean clone. The revisions of 2026-08-08
and 2026-08-10 made the method columns more demanding; **neither of them
produced evidence**.

### Operational note — `twin_creation` (proposed, to be confirmed with the supervisors)

`twin_creation` is a condition of plan §7.1 (10 independent runs) with no
`claim_id` of its own; it feeds the context of C04 (stack start-up) and C05
(vertical slice). **Proposed operational definition — `proposed — to be
confirmed with the supervisors`, not frozen:** time `twin_creation_time_ms`
from the **first telemetry event of an unknown `device_uuid`** (instant of
receipt in the controller), through the **creation of the `policy` + `thing`
pair in Ditto** (CONTRACTS §4/§5: policy `org.c2dta:{device_uuid}` and thing
created on the device's first event), until the twin becomes **readable by
`GET /twins/{device_id}` with 200**. Final milestone = first successful read,
not the `PATCH` response. Until this definition is confirmed, no
`twin_creation` value enters the text. There is still no measurement script
for this condition in `src/deployment/scripts/` (unlike
`measure-cold-start.sh`), which is a blocking dependency of this measurement,
on top of the measurement VM not existing.

| claim_id | Statement | Chapter | RQ | Method | Evidence file | Analysis script | Config/commit | Validation status |
|---|---|---|---|---|---|---|---|---|
| C01 | The `egw-image` image has a versioned, repeatable same-operator build from a documented clean checkout and a `kas` manifest with exact tags/commits pinned (Yocto 5.0.19/Scarthgap) | 4 | RQ1 | BitBake build from a new checkout/build directory; shared-cache policy recorded; full build log; checksums of the artefacts | `docs/evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/kas-checkout.log`, `kas-build.log`, `image-packages.manifest`, `environment.txt`, `manifest.json`, `SHA256SUMS`; rootfs SHA-256 `6c37fcc1…`; kernel SHA-256 `4457ef38…` | (n/a — verification by log and checksum) | `src/yocto/kas/egw-qemuarm64.yml` @ `f0e19d5` | **Partial** — a clean identified same-operator checkout/build completed all 5,715 tasks and is sealed (2026-08-14); 2,261 tasks did not need rerun from shared sstate, so this is not a cold-cache claim. D006 still has to decide second-operator treatment before any stronger reproducibility wording, and G1 acceptance remains pending |
| C02 | The `egw-image` boots on `qemuarm64` through to systemd with networking and a working OCI runtime, repeatably, including running a test container | 4 and 5 | RQ1 | **Three distinct, non-interchangeable sets:** (a) preliminary bring-up — two sealed boots driven at `32f6604`; (b) strict G1 acceptance set — one instrumentation-failure attempt preserved, followed by five fresh boots driven at `9fe38ff`; (c) later frozen campaign — five predefined `qemu_boots` identities ingested by `run --external-timings`. In every set, a test container is run inside the guest and **ZERO** performance inference is drawn | Preliminary seal: `docs/evidence/g1-yocto-qemu/boot1.*`, `boot2.*`, top-level `SHA256SUMS`; strict G1 seal: `docs/evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/qemu-boot-01.*`, `qemu-g1r2-01.*` to `qemu-g1r2-05.*`, nested `SHA256SUMS` | `src/yocto/scripts/boot_check.py` @ `9fe38ff`; later external timings: `src/egw_experiments` | image build @ `f0e19d5`; passing driver @ `9fe38ff` | **Partial — strict G1 set produced and sealed (2026-08-14).** The invalid first attempt remains `fail` and is not counted. Five fresh boots each passed **7 of 7 required assertions**, recorded **2 of 2 observations**, reported exact `systemd=running` and zero failed units, reached the console and powered down cleanly. Formal G1 admission is pending; the predefined later `data-v1` identities remain pending unless a dated protocol decision explicitly admits this set. **0 of 15 claims are accepted** |
| C03 | All the stack OCI images (Mosquitto, Ditto `gateway`/`policies`/`things` 3.9.4, MongoDB, controller) are native `linux/arm64` and pinned by digest | 4 | RQ1 | `docker manifest inspect` per image; versioned digest lockfile | `src/deployment/images.lock.env`; `experiments/results/raw/g1-oci-01/logs/manifest-inspect.log` | (n/a — verification by inspection) | (to be filled in) | Pending — no evidence |
| C04 | The time to readiness of the DT stack on the ARM64 VM is measured over 10 independent cold starts, with mean, standard deviation and 95% CI | 5 | RQ3 | 10 cold starts measured on the VM by `src/deployment/scripts/measure-cold-start.sh` and ingested by `run --external-timings`; readiness = `GET /ready` 200; statistical unit = run. **MANDATORY SEALING (block P5.4):** only a `cold_start-rNN` whose `SHA256SUMS` **VERIFIES** contributes to the mean/standard deviation/95% CI; an unsealed directory and a failed seal are both excluded with a warning and both listed in `external_runs.csv` with the corresponding integrity mark. Note on the sibling condition `twin_creation` (plan §7.1, with no `claim_id` of its own): **PROPOSED** operational definition — to be confirmed with the supervisors — time it from the first telemetry event of an unknown `device_uuid`, through the creation of the `policy`+`thing` pair in Ditto (CONTRACTS §4/§5), until the twin becomes readable by `GET /twins/{device_id}` with 200. The measurement VM does not exist yet, so this condition is blocked on infrastructure | `experiments/results/raw/cold_start-r01/manifest.json` .. `experiments/results/raw/cold_start-r10/manifest.json`; `experiments/results/raw/cold_start-r01/logs/` .. `experiments/results/raw/cold_start-r10/logs/` (run_id generated by `plan_gen.py` for the `cold_start` condition) | `src/egw_experiments/analyze.py` (external condition analysed by the SAME script: `summary_by_condition.csv` and `external_runs.csv`) | (to be filled in) | Pending — no evidence |
| C05 | A telemetry event travels MQTT (TLS, QoS 1) -> controller -> Ditto and the resulting state is retrievable through the API (vertical slice) | 4 | RQ2 | Reproducible trace: `sent_events.jsonl` from the simulator + `events.jsonl` from the controller + a `GET /twins/{device_id}` read. That same `GET /twins/{device_id}` 200 read is the final milestone of the **PROPOSED** operational definition of `twin_creation` described in C04 (to be confirmed with the supervisors). **MANDATORY SEALING:** because this is a bring-up run outside the frozen protocol, the analysis **FLAGS** (does not exclude) an unsealed directory; the requirement is this matrix own — without a `SHA256SUMS` generated at the end of collection and verifiable, the trace does not count as evidence for C05 | `experiments/results/raw/g2-slice-01/events.jsonl`; `experiments/results/raw/g2-slice-01/manifest.json` (G2 bring-up run, outside the frozen campaign plan) | `src/egw_experiments/analyze.py` | (to be filled in) | Pending — no evidence |
| C06 | With three concurrent wearables in the nominal scenario (~11.2 msg/s aggregate), at least 99% of the valid events sent are accounted for end to end (unique Ditto acknowledgements / valid messages sent) | 5 | RQ2 | 10 nominal runs of 10 min after 2 min of warm-up; delivery rate as per plan §7.3 | `experiments/results/raw/nominal-r01/events.jsonl` .. `experiments/results/raw/nominal-r10/events.jsonl`; the homologous `manifest.json` files (nominal condition) | `src/egw_experiments/analyze.py` | (to be filled in) | Pending — no evidence |
| C07 | The primary MQTT->Ditto acknowledgement latency (p50/p95/p99) is measured in the controller with a monotonic clock in the same process; the simulator `ts` never enters this measurement | 5 | RQ3 | `latency_ms = (ditto_ack_monotonic_ns - received_monotonic_ns)/1e6` per event; aggregation per run; percentiles per run | `experiments/results/raw/nominal-r01/events.jsonl` .. `experiments/results/raw/nominal-r10/events.jsonl` | `src/egw_experiments/analyze.py` | (to be filled in) | Pending — no evidence |
| C08 | The `load-sweep` at 10, 50, 100 and 250 msg/s (10 runs of 5 min per load, randomised order, 2 min of cooldown) identifies operational saturation according to the criteria of plan §7.3 | 5 | RQ3 | load-sweep campaign driven by the harness; saturation = loss >1% or persistent queue or p95 >1 s or CPU >90% for 60 s | `experiments/results/raw/load_sweep-{010,050,100,250}mps-r01..r10/events.jsonl`; `experiments/results/raw/load_sweep-{010,050,100,250}mps-r01..r10/resources.csv` (40 run_id generated by `plan_gen.py`: `load_sweep-<rate:03d>mps-r<rep:02d>`) | `src/egw_experiments/analyze.py` (`saturation.json`, `summary_by_condition.csv`) | (to be filled in) | Pending — no evidence |
| C09 | CPU and RAM per container are collected every second in all timed runs and reported per run | 5 | RQ3 | Resource sampling at 1 Hz by the SUT collector (`src/deployment/scripts/collect-resources.sh`) ingested by `run --resources-from` in every timed run | `resources.csv` from every timed run in `experiments/results/raw/`: `smoke_sequence-r01..r10`; `nominal-r01..r10`; `load_sweep-{010,050,100,250}mps-r01..r10`; `invalid_payload-r01..r03`; `dropout_reconnect-r01..r03`; `controller_restart-r01..r03`; `soak-r01` | `src/egw_experiments/analyze.py` (`resources_by_run.csv`, `per_run.csv`) | (to be filled in) | Pending — no evidence |
| C10 | In the dropout-reconnect scenario the system recovers after a connection loss: the valid messages are acknowledged with no duplicates applied to the twins and the counters remain coherent | 5 | RQ2 | `dropout_reconnect` condition of the campaign plan (3 runs of 600 s; real MQTT disconnection with buffering on the device and QoS 1); delivery accounting tolerant of buffered redelivery inside the 60 s confirmation window; idempotency check by `message_id`/`seq`; acceptance (zero lost, zero double-accepted, real disconnections in every run — totals `dropout_disconnects`/`buffered_dropout` >= 1 from the simulator manifest — and reconciliation of the `accepted` counter with `controller_metrics.csv`, work order P1b) in `processed/acceptance_by_condition.csv` | `experiments/results/raw/dropout_reconnect-r01..r03/events.jsonl`; `experiments/results/raw/dropout_reconnect-r01..r03/manifest.json` | `src/egw_experiments/analyze.py` (`acceptance_by_condition.csv`) | (to be filled in) | Pending — no evidence |
| C11 | In the invalid-payload scenario, 100% of the deliberately invalid payloads are rejected by JSON Schema validation before any twin update and do not count as losses | 5 | RQ2 | `invalid_payload` condition of the campaign plan (3 runs of 300 s at the nominal aggregate rate); events marked `intended_invalid` in the simulator `sent_events.jsonl` cross-checked against `outcome=rejected` in the controller; acceptance (all `intended_invalid` rejected, zero accepted; delivery of the valid ones as per plan §7.3) in `processed/acceptance_by_condition.csv` | `experiments/results/raw/invalid_payload-r01..r03/events.jsonl`; `experiments/results/raw/invalid_payload-r01..r03/sent_events.jsonl` | `src/egw_experiments/analyze.py` (`acceptance_by_condition.csv`) | (to be filled in) | Pending — no evidence |
| C12 | Duplicate detection survives a controller restart because the state (`last_message_id`, `last_seq`) persists in the `ingestion` feature of the twin | 4 and 5 | RQ2 | `controller_restart` condition of the campaign plan (3 nominal runs of 600 s with a controller restart halfway through, executed by the harness `--restart-cmd`/`--restart-at-s` hook and recorded in the manifest with timestamps); acceptance (record of the hook executed with timestamps and exit 0 in every run, delivery through the restart, zero double-accepted `message_id`; work order P1b) in `processed/acceptance_by_condition.csv`. **REAL RECOVERY EVIDENCE (block P5):** a hook with exit 0 proves that a command ran, not that the controller went down and came back, so acceptance requires three criteria computed from `controller_metrics.csv` around the restart instants — (a) **sign of unavailability**: a sampling hole larger than the cadence cap straddling the restart (a failed read writes no row, so the holes ARE the evidence) or a reset of the `accepted` counter; (b) **bounded recovery**: the first sample after the end of the restart falls within `RESTART_RECOVERY_MAX_S` (`protocol.py`; **PENDING SUPERVISOR APPROVAL** before `exp-v1`); (c) **progress**: the `accepted` counter grows after the restart. Without the series or without the record of the restart the criteria **FAIL** for insufficient instrumentation, they are never left blank | `experiments/results/raw/controller_restart-r01..r03/events.jsonl`; `experiments/results/raw/controller_restart-r01..r03/manifest.json`; `src/tests/` (live integration test **still to be created** — prerequisite of G3) | `src/egw_experiments/analyze.py` (`acceptance_by_condition.csv`) | (to be filled in) | Pending — no evidence |
| C13 | The 24-hour nominal soak finishes with no unrecovered crash and no loss of metrics collection; descriptive analysis, with no CI of its own | 5 | RQ2 and RQ3 | 24 h soak run with continuous resource collection; descriptive analysis as per plan §7.3; Definition of Done evaluated in `processed/acceptance_by_condition.csv` (measured window >= 24 h; `resources.csv` and `controller_metrics.csv` with coverage >= 99% of the window with no gaps > 60 s **and no head gap > 60 s** (block P5: a series that only starts sampling well inside the window is not continuous evidence) and with a minimum of distinct valid instants inside the measured window; no unrecovered interruption: no gap > 120 s in the metrics and last sample <= 120 s from the end; thresholds pending supervisor approval before `exp-v1`; work order P1b) | `experiments/results/raw/soak-r01/events.jsonl`; `experiments/results/raw/soak-r01/resources.csv`; `experiments/results/raw/soak-r01/controller_metrics.csv`; `experiments/results/raw/soak-r01/logs/` | `src/egw_experiments/analyze.py` (`acceptance_by_condition.csv`) | (to be filled in) | Pending — no evidence |
| C14 | Ten consecutive smoke runs finish successfully in the campaign environment | 5 | RQ2 | `smoke_sequence` condition of the campaign plan: 10 consecutive `smoke` runs driven by the harness, all with exit code 0 and zero valid messages lost; acceptance in `processed/acceptance_by_condition.csv` | `experiments/results/raw/smoke_sequence-r01..r10/manifest.json` | `src/egw_experiments/analyze.py` (`acceptance_by_condition.csv`) | (to be filled in) | Pending — no evidence |
| C15 | A single analysis script regenerates all the tables and figures of the dissertation from `experiments/results/raw`, with no manual editing | 4 and 5 | RQ1 | Run `python -m egw_experiments analyze` over `raw/` in a clean checkout — **THE COMMAND AS DELIVERED**, with the frozen plan actually in use (risk R32 in [`g0/risks.md`](g0/risks.md)), never an equivalent invocation through the API; null diff against the published artefacts; the external conditions (`qemu_boots`, `cold_start`, `twin_creation`) are ingested via `run --external-timings` and analysed by the SAME script (`summary_by_condition.csv` and `external_runs.csv`), with no separate pipeline | `experiments/results/processed/`; `experiments/results/figures/` | `src/egw_experiments/analyze.py` (single analysis script) | (to be filled in) | Pending — no evidence |
