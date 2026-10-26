# Results and their sources

This page lists each result that the dissertation presents. For each one it gives:

- where the result appears in the dissertation;
- the outcome, as the linked record states it;
- where the data are;
- which code produced or analysed them.

It adds no result and changes no criterion, outcome or classification. How to repeat the
analysis is in [reproduce.md](reproduce.md). What the system is and how its parts talk is in
[architecture.md](architecture.md).

## Read every figure with these limits

- **Emulated, one host.** Every figure comes from an ARM64 guest emulated by QEMU 8.2.7 in TCG
  mode on one x86-64 host (Windows 11 with WSL2 Ubuntu 24.04). The load generator ran on the same
  host. The guest's 4 virtual CPUs and 8 GiB are emulator settings, not a physical gateway.
  Nothing here describes physical ARM hardware.
- **Load values are experimental parameters.** These values are inherited from the harness's
  `nominal` scenario:
  - 11.2 msg/s;
  - 600 s measured windows;
  - 120 s warm-up;
  - the end-of-load marker + 60 s observation limit.

  They are not requirements, targets or pass thresholds. No result on this page is a maximum
  capacity.
- **Exploratory comparison.** The Yocto vs Debian 13 comparison has n = 3 per configuration and no
  statistical significance. It compares whole configurations (kernel, container runtime and
  userland differ), so it shows no isolated effect of the distribution.

**Dissertation references.** The current manuscript is the student's Word file, kept outside
this repository ([thesis/README.md](../thesis/README.md)). Section, table and figure numbers below
are those of its version of 2026-10-24. Check them against the submitted version. The
manuscript's Table B.1 indexes the same evidence with repository paths.

**Data.** Data are of two kinds:

- **Repository.** A capsule under [`docs/evidence/`](evidence/). Every `SHA256SUMS` there is
  verified in CI by `python tools/ci/verify_evidence.py`. The short digest quoted is the sha256 of
  the capsule's top-level `SHA256SUMS`.
- **Local only.** A package on the student's workstation, in the `output_test` tree described in
  [setup/local_test_outputs.md](setup/local_test_outputs.md). It is not in the repository, and
  the reason is given each time.

## Overview

| # | Result | Dissertation | Outcome as recorded | Data | Analysis code |
|---|---|---|---|---|---|
| [R1](#r1-g1-base-image-build-and-five-boots) | G1 base image: clean build and five boots | 5.1, Table D.3 | Build passed. Five strict boots, each 7 of 7 assertions | Repository | `src/yocto/scripts/boot_check.py` |
| [R2](#r2-integrated-image-build-and-boot) | Integrated image: build and boot | 5.1, Table D.3 | One build failed, one passed. Boot and persistence boot passed | Repository | Runbook §2–3 |
| [R3](#r3-mongodb-7-alone-on-the-emulated-cpu-model) | MongoDB 7 alone on the emulated CPU model | 5.1, Table D.3 | 35 checks passed, 0 failed | Repository | Commands inside the capsule |
| [R4](#r4-g2-one-wearable-end-to-end-and-twin-persistence) | G2: one wearable end to end, twin persistence | 4.6, 5.2, Table 5.4 | 60 of 60 in time. Twin intact after a quiescent restart | Repository | `tools/session/`, `itest_reconcile.py` |
| [R5](#r5-finite-proof-r03-of-controller-restart-recovery) | Finite proof r03 of controller-restart recovery | 4.4, Table B.1 | Evaluator `supports`, for that run only | Repository (r03), local only (r01, r02) | `proof_evaluator.py` |
| [R6](#r6-g3-functional-battery-t1t9) | G3 functional battery T1–T9 | 5.2, Table 5.1 | A standing Pass row per family. T6 passed under the criterion amended on 2026-10-05 | Repository | `egw_experiments`, `tools/session/` |
| [R7](#r7-timed-delivery-in-the-two-600-s-g3-runs) | Timed delivery in the two 600 s G3 runs | 5.3 | **Not met** under TCG | Repository | `analyze.py` |
| [R8](#r8-cpu-and-memory-per-container) | CPU and memory per container | 5.4, Table 5.2 | Descriptive | Repository (raw). Percentile script local only | `analyze.py`, local script |
| [R9](#r9-comparison-a02-yocto-image-vs-debian-13) | Comparison a02: Yocto image vs Debian 13 | 5.5, Table 5.3, Figures 5.1–5.2 | Exploratory, n = 3 | Repository (summary). Raw local only | `tools/compare/measure_*` |
| [R10](#r10-per-container-comparison-and-derived-figures) | Per-container comparison and derived figures | 5.5, Table D.8 | Descriptive | Local only | Local only |
| [R11](#r11-host-contention-and-storage-run-a03h) | Host contention and storage, run a03h | 5.6, 5.7, Tables D.5–D.7 | One execution, not pooled with a02 | Local only | `measure_run.sh`. Sampler and analysis local only |
| [R12](#r12-requirements-reading) | Requirements reading | 5.6, Table 5.4, Table A.2 | The dissertation's own reading of R1–R11 | No new data | — |
| [R13](#r13-unit-test-suite) | Unit-test suite | Table B.1 | 701 passed (repository seal). 4,044 passed, 12 skipped (local) | Repository and local only | `src/tests/` |
| [R14](#r14-g4-pilot) | G4 pilot | 5.7 (named as non-citable) | No figure cited | Local only | — |

Gate decisions are the student's and are recorded in
[governance/gate_decision_log.md](governance/gate_decision_log.md):

- G0, G1, G2 and G3: **Accepted**, each in a bounded scope;
- G4 to G7: **Not decided**.

The 95-run campaign of the plan was never executed. The claim matrix
([claim_evidence_matrix.md](claim_evidence_matrix.md)) belongs to that campaign and validates no
claim. The a02 comparison is outside it.

---

## R1. G1 base image: build and five boots

- **Outcome:**
  - Clean-checkout build of `egw-image` at `f0e19d5` on 2026-08-14: 5,715 tasks, all succeeded, 639
    packages.
  - Five strict boots, `qemu-g1r2-01` to `-05`, under `-cpu cortex-a57 -smp 4 -m 256`. Each passed
    7 of 7 required assertions.
  - The failed first attempt, `qemu-boot-01`, is kept as an instrumentation false negative.
  - A preliminary build and two boots of 2026-08-11 passed 6 of 6 assertions each.
- **Decision:** G1 was accepted on 2026-08-14, for the functional platform layer only.
- **Data:**
  - [`evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/`](evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/README.md)
    (`SHA256SUMS` `3d934fa2…`);
  - the preliminary set in [`evidence/g1-yocto-qemu/`](evidence/g1-yocto-qemu/README.md) (`260455ba…`).
- **Code:**
  - `src/yocto/kas/egw-qemuarm64.yml` and its `.lock.yml`;
  - `src/yocto/scripts/build.sh`, `run-qemu.sh` and `boot_check.py`.

  This G1 image is historical. The evaluated image is the integrated one (R2).

## R2. Integrated image: build and boot

- **Outcome, 2026-09-18:**
  - The build at `68f9ae7` **failed** in `do_rootfs`, on a directory-mode conflict on
    `/etc/sudoers.d`.
  - The build at `03e333e` succeeded: 5,556 tasks and 614 packages.
  - The first boot attempt, `integrated-boot-01`, **failed before QEMU started**.
  - After a no-op rebuild at `3209b17`, `integrated-boot-02` booted under
    `-machine virt -cpu cortex-a76 -smp 4 -m 8192`. SSH answered after 19 s, every guest acceptance
    check passed, and the root file system used 344.4 MiB of 2.2 GiB.
  - `integrated-boot-03` verified persistence.
  - The six-container stack was not deployed in this capsule.
- **Data:**
  - [`evidence/integrated-qemu/2026-09-18-build-boot/`](evidence/integrated-qemu/2026-09-18-build-boot/README.md)
    (`ca907fec…`);
  - the failed attempts are kept beside the successful ones.
- **Code:**
  - `src/yocto/kas/egw-qemuarm64-integrated.yml` and its `.lock.yml`;
  - `src/yocto/scripts/build-profile.sh` and `run-qemu-integrated.sh`;
  - runbook [setup/qemu_integrated_gateway.md](setup/qemu_integrated_gateway.md) §2–3.

## R3. MongoDB 7 alone on the emulated CPU model

- **Outcome, 2026-09-18:**
  - `mongo:7.0.39` ran on the `cortex-a76` model and reported `cpuArch` aarch64, with no illegal
    instruction.
  - 27 checks passed in phase 1 and 8 in phase 2, with 0 failed. They covered start, write and
    read, restart, recreation and a guest power cycle.
  - One container only, not the stack.
- **Data:** [`evidence/integrated-qemu/2026-09-18-mongodb7-isolated/`](evidence/integrated-qemu/2026-09-18-mongodb7-isolated/README.md)
  (`10734ca3…`).
- **Code:** the commands are inside the capsule (runbook §3.5).

## R4. G2: one wearable end to end and twin persistence

- **Outcome, 2026-09-20:**
  - Run `itest-g2-01`, seed `20260921`: one smartwatch at 1 Hz for 60 s.
  - All 60 valid messages were confirmed within the controller-clock deadline, with none lost,
    late or duplicated.
  - Twin `org.c2dta:62da1188-…` ended with sequence 59 and accepted count 60.
  - The twin was intact after one declared, quiescent whole-stack restart.
- **Decision:** G2 was accepted on 2026-09-21 in that bounded functional scope
  ([decision record](governance/decisions/2026-09-21-g2-closure.md)). The gate log lists the
  disclosed limitations.
- **Data:** [`evidence/g2-complete-flow/`](evidence/g2-complete-flow/README.md) (`9a5c08f7…`). It
  holds all seven attempts of the session, including the failed preflight.
- **Code:**
  - the session drivers in `tools/session/` at `b7e0c83`;
  - `src/egw_experiments/itest_reconcile.py`;
  - runbook §6.

## R5. Finite proof r03 of controller-restart recovery

- **Outcome, 2026-09-28:**
  - The evaluator's verdict is `supports`, **for that run only**.
  - The harness's own verdict on the raw run is `invalid`, and its inner seal is withheld.
  - The twin `delta` check ended `MISMATCH` (exit 4), which the capsule explains.
  - On 2026-09-29 the student accepted r03 as meeting the purpose of a finite engineering
    diagnostic. It is not a G3 pass and admits no claim.
- **Data:**
  - [`evidence/finite-proof-r03/`](evidence/finite-proof-r03/README.md) (`8443cf20…`);
  - **local only:** r01 and r02 (both `inconclusive`), which were never published.
- **Code:**
  - `src/egw_experiments/proof_evaluator.py`;
  - `tools/session/proof*`;
  - [ADR 0011](adr/0011-controller-restart-recovery.md).

## R6. G3 functional battery T1–T9

**Sessions.** The battery ran in four sessions on one unchanged emulated system under test:

| Session | Date |
|---|---|
| S1 | 2026-10-02 |
| S2 | 2026-10-03 |
| S3 | 2026-10-05 |
| S4 | 2026-10-07 |

**Decision.** The student accepted G3 on 2026-10-07 as the functional P0 freeze on the emulated
candidate, and for nothing else ([decision record](governance/decisions/2026-10-07-g3-closure.md)).

**Standing rows.** They are quoted from the "Standing rows as of 2026-10-07" section of the
[results addendum](governance/g3-battery-2026-10-results.md):

| Family | Run | Recorded result | Class as recorded |
|---|---|---|---|
| T1 smokes | `itest-smoke-01/02/03-q1` | 336 of 336 each, `lost` 0, `late` 0 | Pass |
| T1 harness | `nominal-r02` | Artefact chain valid. Delivery **reported only**: 4,584 of 6,720 in time | Pass (artefact chain) |
| T2 | `itest-3dev-01-q1` | 672 of 672. Three twins with `policyId` = `thingId` | Pass |
| T3 | `itest-invalid-01-q1` | 67 invalid, all rejected, none accepted. 1,277 valid, all accepted in the post-drain copy | Pass |
| T4 replay | `itest-dup-01-q1` | 672 duplicates, none accepted again | Pass |
| T4 reset | `itest-dup-02-q1` | 672 of 672 | Pass |
| T5 | `itest-dropout-01-q1` | 2,016 of 2,016. 3 dropouts, 165 buffered | Pass, as sealed (reading admitted 2026-10-05) |
| T6 | `controller_restart-r04` | Endpoint recovery 12.134 s. 6,720 accepted exactly once after the drain. 4,567 of 6,720 by the deadline | Pass (the criterion amended on 2026-10-05) |
| T7 | `itest-mongo-fault-01-q1`, `itest-ditto-fault-01-q1` | 44 and 5 `failed` after three attempts, then acceptance resumed | Pass |
| T8 | `itest-reboot-q2`, `itest-post-reboot-01-q2` | Six containers back unaided, twins identical, smoke 336 of 336 | Pass |
| T9 | five sub-checks | Wrong CA, wrong password, plaintext and anonymous refused. ACL probe passed | Pass |

**Kept, not standing.** These attempts keep their records:

- row 8, `controller_restart-r03`: invalid instrumentation;
- row 11, `itest-reboot-q1`: incomplete, halted;
- row 12, T9 in S2: not run;
- the first opening of S3: halted at its preflight.

The T6 criterion was amended on 2026-10-05, for runs made after that date
([decision](governance/g3-t5-t6-decisions-2026-10-05.md)). Under it, T6 passes on:

- recovery within 120 s;
- every valid message accepted exactly once after the drain.

Timely delivery is reported, not judged (R7).

- **Data:** [`evidence/g3-battery-2026-10/`](evidence/g3-battery-2026-10/README.md):
  - 38 packages;
  - outer `SHA256SUMS` `4517e91e…`;
  - `PACKAGES.sha256` with each package's seal;
  - the battery's 22 local records, under `records/`.
- **Code:**
  - `src/egw_experiments/`: `run`, `analyze`, `itest_reconcile`, `proved_down`,
    `recovery_qualification`;
  - the session drivers in `tools/session/`;
  - `src/deployment/scripts/probe-acl.sh` (T9);
  - runbook §7.

## R7. Timed delivery in the two 600 s G3 runs

**The negative result.** At the inherited 11.2 msg/s, neither 600 s run confirmed every message
by the end-of-load marker + 60 s. "Lost" here means "not confirmed by that limit", not a
permanent loss.

The values below are the analyser's, read from the sealed `per_run.csv`:

| Run | Confirmed by the limit | `lost` (of which late) | Latency p50 | Latency p95 |
|---|---|---|---|---|
| `nominal-r02` (T1) | 4,584 of 6,720 | 2,136 (111) | 178,846.6 ms | 247,078.9 ms |
| `controller_restart-r04` (T6) | 4,567 of 6,720 | 2,153 (67) | 128,042.5 ms | 250,648.7 ms |

- For `controller_restart-r04`, all 6,720 messages were accepted exactly once by the end of the
  drain.
- `nominal-r02` has **no post-drain copy**, so its eventual acceptance is not established.
- The 30, 60, 120 and 180 s rows at the same rate were in time. The two 300 s T7 fault rows are not
  timed; they report `lost` 1,209 (1,165 late) and 1,895 (1,890 late)
  ([results addendum](governance/g3-battery-2026-10-results.md), rows 9–10).
- Latency runs from controller reception to Ditto confirmation. It covers only the confirmations
  within the limit.
- **Data:** the `other/processed.after/per_run.csv` files of these two packages:
  - [`…/2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01/`](evidence/g3-battery-2026-10/2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01/);
  - [`…/2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02/`](evidence/g3-battery-2026-10/2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02/).
- **Code:** `src/egw_experiments/analyze.py`.

## R8. CPU and memory per container

**`nominal-r02`.** 682 sampling instants. The per-instant sum over the six containers was:

| Measure | Median | Maximum |
|---|---|---|
| Memory | 2,000 MB | 2,175 MB |
| CPU (% of one virtual CPU) | 218 % | 355 % |

Two containers stand out:

- `ditto-things` averaged 608 MB, about 75 % of its 768 MiB limit;
- MongoDB peaked at 412 MB.

**`controller_restart-r04`.** Over 601 complete instants: median memory 2,003 MB, median CPU 237 %.

- **Data:** the sealed raw samples, `raw/<run>/resources.csv`, in the two packages of R7. The
  analyser's cross-check (mean and maximum only) is in `other/processed.after/resources_by_run.csv`.
- **Code:**
  - `src/egw_experiments/analyze.py` for the mean and maximum;
  - **local only:** the per-instant sums and nearest-rank p95 of Table 5.2 come from a read-only
    script in the dissertation working folder. It is not in the repository. The medians above can
    be recomputed from the sealed CSVs ([reproduce.md](reproduce.md#65-recompute-the-table-52-medians-from-sealed-samples)).

## R9. Comparison a02: Yocto image vs Debian 13

**Run.** 2026-10-18 21:37Z to 2026-10-19 00:39Z, under one QEMU/TCG profile
(`-cpu cortex-a76 -smp 4 -m 8192`):

- six valid executions in three pairs, Y→D, D→Y and Y→D;
- seeds 2026101801 to 03;
- plan `plan-a02.json`, sha256 `94fc9691…`;
- the load was the `nominal` scenario: 600 s at 11.2 msg/s after 120 s of warm-up.

**Medians of three**, as the capsule states them:

| Metric | Yocto | Debian 13 |
|---|---|---|
| Boot to first SSH answer | 15.8 s | 46.3 s |
| Launch to stack ready | 241.3 s | 322.3 s |
| Launch to gateway functional | 258.8 s | 341.9 s |
| Guest memory inside the measured window | 1,922.7 MiB | 2,304.3 MiB |
| Root file system used | 489 MiB | 1,458 MiB |
| Observed acceptance rate (estimate between boundary samples) | 7.76 msg/s | 4.95 msg/s |
| Confirmed by the end-of-load marker + 60 s | 4,426 of 6,720 | 2,394 of 6,720 |
| Controller latency p50, confirmations within the limit only | 220.1 s | 350.6 s |
| Drain to a 130 s quiet window | 344.0 s | 668.3 s |
| Duplicates, double acceptances | 0, 0 | 0, 0 |

**Neither configuration kept pace** with the inherited 11.2 msg/s under TCG. The rest was
confirmed during the drain in the five executions whose post-drain log was verified. The
post-drain fetch of `cmp-p1-yocto-a02` failed, so the after-drain reconciliation has Yocto
n = 2 and Debian 13 n = 3.

**Excluded from the statistics.** The first attempt, `cmp-p1-yocto`, was invalid by
instrumentation. The series also stopped twice on instrumentation. Both are recorded, and nothing
was repeated.

**Data:**

- **Repository:** [`evidence/compare-a02/`](evidence/compare-a02/README.md):
  - `table.md`, `summary.csv` and `summary.json`: the corrected derivative
    `summary-a02-v2-20261019T125731Z`;
  - `plan-a02.json`.

  The capsule has no `SHA256SUMS` of its own. `summary.json` records its inputs and their
  digests.
- **Local only:**
  - the raw records,
    `output_test/runs/2026-10-19/HIST_2026-10-19-compare-measurements-a02`: 583 files, `SHA256SUMS`
    `87d7ada7…`, about 69 MB. Only the summary derivative above was published to the repository;
    the raw package stays in the student's local evidence tree;
  - the decision note `output_test/decisions/2026-10-19_compare-measurements-a02.md`.

**Code:**

- `tools/compare/measure_base.sh`, `measure_plan.py`, `measure_run.sh`, `measure_series.sh`,
  `guest_meminfo_sampler.sh` and `drain_hook.sh`;
- `tools/compare/measure_summary.py` (generator commit `34a5f9d`);
- `python -m egw_experiments analyze` for `per_run.csv`;
- `tools/session/proof_hook_drained.sh` and `nominal_account.py`.

The calculation rules are in [tools/compare/README.md](../tools/compare/README.md) §10. The
protocol in [tools/compare/PROTOCOL.md](../tools/compare/PROTOCOL.md) is an earlier **proposal**.
The executed series is the one in §10 and in this capsule.

**Figures 5.1 and 5.2.** The plotting scripts are **local only**, in the dissertation working
folder. Their input is the repository file `evidence/compare-a02/summary.csv`.

## R10. Per-container comparison and derived figures

Table D.8 breaks the a02 guest memory and CPU down by container and derives further figures, such
as processor time per accepted message and the composition of the root file system.

- **Data: local only.** The table is computed from the per-container `resources.csv`, the
  `timeline.json` and the memory samples of the local a02 raw package (R9).
- **Code: local only.** A read-only script, outside the repository.

Neither the data nor the script is published here, so this table cannot be recomputed from the
repository alone.

## R11. Host contention and storage, run a03h

**The run.** On 2026-10-24, one execution, `cmp-p1-yocto-a03h`, used the unchanged comparison
procedure on the Yocto image. The host was sampled at 1 Hz beside it. The run is not pooled with
a02.

**Delivery:** 4,144 of 6,720 confirmed by the observation limit; all 6,720 accepted once after the
drain.

**Host, during warm-up and load:**

| Measure | Value |
|---|---|
| Host CPU busy, all 16 logical processors | mean 17.1 %, p95 21.7 % |
| QEMU process | mean 276 % of one processor |
| Load generator | at most 2 % of one processor |

**Storage:** the root file system used 489–494 MiB.

**Data: local only.** The run was made for the dissertation on 2026-10-24 and its package was not
published to the repository; the dissertation's Table B.1 says so too.

- the package
  `output_test/runs/2026-10-24/HIST_2026-10-24-req10-req11-host-contention-and-storage` (145 files,
  `SHA256SUMS` `b993b395…`);
- plan `plan-a03h.json` (sha256 `c956af83…`; only its first entry was executed);
- the note `output_test/decisions/2026-10-24_req10-req11-run-results.md`.

**Code:**

- the execution is `tools/compare/measure_run.sh`, unchanged;
- **local only:** the host sampler and the analysis scripts, in the dissertation working folder.

Table D.5 also uses the collector maxima of `nominal-r02` and `controller_restart-r04` (R8).

## R12. Requirements reading

Table 5.4 and Table A.2 are the dissertation's own reading of R1–R11 against its requirements
list. They involve no new data, and no project record adopts them as a gate decision or an
admitted claim.

The list used there was revised on 2026-10-24 and is not in the repository. The repository holds
the earlier version, v1.0 of 2026-09-21:
[academic/gateway_requirements_and_platform_selection.md](academic/gateway_requirements_and_platform_selection.md).

## R13. Unit-test suite

The suite is broker-free: it uses fakes for MQTT and Ditto.

- **Repository:** the newest sealed record is
  [`evidence/tests/2026-08-11-head-4e67717/`](evidence/tests/2026-08-11-head-4e67717/): 701
  passed at `4e67717` (`SHA256SUMS` `1f8982ef…`).
- **Local only:** the run of 2026-10-08 at `643591c`, cited in Table B.1. It gave 4,044 passed
  and 12 skipped (4,056 tests). Its package is
  `output_test/runs/2026-10-08/HIST_2026-10-08-g4-pr60-corrections-integrated-attempt01`
  (`SHA256SUMS` `88da0b80…`).
- **Code:** `src/tests/`. Run it with the command in [src/README.md](../src/README.md).

## R14. G4 pilot

- **What ran:** pilot sessions on the integrated guest in October 2026. The repository records
  that the open of session B halted on 2026-10-08 (`LOG.md` #C058).
- **In the dissertation:** no figure is cited; Section 5.7 names the pilot as non-citable.
- **Data:**
  - the input plan is in [experiments/g4-pilot/](../experiments/g4-pilot/README.md);
  - the session records are **local only** and non-citable;
  - among the local session records: session B's second opening on 2026-10-09, whose run `s4` was
    classed `valid/fail` (33 `failed` outcomes during the drain), and the consolidation note
    `output_test/decisions/2026-10-09_g4-pilot-consolidation-decision.md`; non-citable.
- **Decision:** G4 is `Not decided`.

---

## Negative results and failed attempts kept

None of these is deleted, re-labelled or repeated to replace it.

**Results of the system itself:**

- timed delivery at the inherited 11.2 msg/s was not met under TCG:
  - by either configuration in a02 (R9);
  - by either 600 s G3 run (R7);
  - by `nominal-r01` on 2026-09-19, the first valid harness run on the guest: 3,794 of 6,720
    in time (raw records local only; its analyser row is in the sealed `per_run.csv` of the T1
    harness package; `LOG.md` #C036);
- the two 300 s T7 fault rows, not timed: `lost` 1,209 and 1,895, reported only (R6, R7);
- `nominal-r02` has no post-drain copy (R7).

**Failed, invalid or incomplete attempts in the repository:**

- `qemu-boot-01` (R1);
- build `68f9ae7` and `integrated-boot-01` (R2);
- the failed preflight of the G2 session (R4);
- the harness verdict `invalid` of r03 (R5);
- G3 rows 8, 11 and 12, and S3's first opening (R6).

**Local only:**

- finite proofs r01 and r02;
- `controller_restart-r01` and `-r02` (raw records; their analyser rows, both `invalid`, are in the
  sealed `per_run.csv` of the R7 packages);
- the first a02 attempt, `cmp-p1-yocto`;
- the 2026-09-18 first flow and battery, a candidate archive that was not admitted;
- G4 pilot session B: the open halted on 2026-10-08, and run `s4` of its second opening was classed
  `valid/fail` (R14).

## Not results

These records support the demonstration, not the evaluation:

- the functional validations of the comparison environments on 2026-10-18
  ([tools/compare/README.md](../tools/compare/README.md) §9);
- the demonstration checks of 2026-10-20 in the three scenarios ([demo.md](demo.md), step 2;
  `LOG.md` #C061).

The third scenario, `yoctowrynose`, is a **demonstration scenario that was never measured**. Its
times are not comparable with a02.

How to run the demonstration: [demo.md](demo.md). Decisions, plans and reviews:
[history/README.md](history/README.md).
