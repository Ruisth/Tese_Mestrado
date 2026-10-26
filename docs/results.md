# Results

This page lists each result of the dissertation: what was done, the outcome as recorded, where the
data are and which code analysed them. It adds no result and changes no outcome. How the system works:
[architecture.md](architecture.md). How to repeat the analysis: [reproduce.md](reproduce.md).

## Read every figure with these limits

- **Emulation only.** Every figure comes from an ARM64 computer emulated by QEMU 8.2.7 (TCG mode) on
  one x86-64 PC with Windows 11 and WSL2 (Ubuntu 24.04). The simulated devices ran on the same PC. The
  gateway's 4 virtual CPUs and 8 GiB are emulator settings (`-cpu cortex-a76 -smp 4 -m 8192`), not a
  physical board.
- **The load is a test setting.** Most tests sent 11.2 messages per second in total. The long runs
  lasted 600 s, after 120 s of warm-up. These values come from the test tools; they are not
  requirements or targets. No figure is a maximum capacity.
- **The time limit.** A message counts as confirmed in time if its twin was updated within 60 s of the
  end of the load. The data files call a message that missed this limit `lost`. That alone does not
  mean lost for good: where a later record exists, most were confirmed afterwards. Only the messages
  recorded as `failed` (in the database and twin-service failure tests) were never applied.

## Data and section numbers

- **Dissertation numbers** (sections, tables, figures) follow a draft made shortly before
  submission. Check them against the submitted version. The manuscript is kept outside this repository
  ([thesis/README.md](../thesis/README.md)). Its Table B.1 lists the same data.
- **Data in the repository** are folders under [`evidence/`](evidence/), copied byte for byte and never
  edited. Their `SHA256SUMS` files are checked by `python tools/ci/verify_evidence.py`.
- **Data kept locally** stay on the student's computer, not in the repository. They are listed at the
  [end of this page](#data-kept-locally).

## Overview

| Result | Dissertation | Outcome as recorded |
|---|---|---|
| [Building and starting the image](#building-and-starting-the-image) | 5.1, Table D.3 | Built and started; first attempts failed and are kept |
| [One device end to end](#one-device-end-to-end) | 4.6, 5.2, Table 5.4 | 60 of 60 in time; twin kept after a restart |
| [Three device types at once](#three-device-types-at-once) | 5.2, Table 5.1 | Passed |
| [Invalid messages](#invalid-messages) | 5.2, Table 5.1 | Passed |
| [Repeated messages](#repeated-messages) | 5.2, Table 5.1 | Passed |
| [Network drop](#network-drop) | 5.2, Table 5.1 | Passed, on a stated reading of the broker log |
| [Controller restart](#controller-restart) | 4.4, 5.2, Tables 5.1 and B.1 | Passed under a relaxed criterion; many messages late |
| [Database or twin-service failure](#database-or-twin-service-failure) | 5.2, Table 5.1 | Passed; not timed |
| [Gateway reboot and persistence](#gateway-reboot-and-persistence) | 5.2, Table 5.1 | Passed |
| [Broker access control](#broker-access-control) | 5.2, Table 5.1 | Passed, for the controls tested |
| [Delivery time under sustained load](#delivery-time-under-sustained-load) | 5.3 | **Not met** |
| [Resource use](#resource-use) | 5.4, 5.5, Tables 5.2 and D.8 | Descriptive |
| [Yocto vs Debian 13](#yocto-vs-debian-13) | 5.5, Table 5.3, Figures 5.1–5.2 | Exploratory, three runs each |
| [Host-load check](#host-load-check) | 5.6, 5.7, Tables D.5–D.7 | One run; data kept locally |

## Building and starting the image

- **Done:** the base Yocto image was built from a clean checkout and started five times in a row
  (`-cpu cortex-a57 -smp 4 -m 256`). The gateway image, which adds the container platform, was then
  built and started (`-machine virt -cpu cortex-a76 -smp 4 -m 8192`).
- **Outcome:**
  - base image: the build succeeded, and each of the five starts passed all 7 automatic checks;
  - gateway image: SSH answered after 19 s, every check passed, and the root file system used
    344.4 MiB of 2.2 GiB. A further start confirmed that data persist. The six containers were not part
    of this check;
  - MongoDB 7 needs a newer ARM processor than the base image's emulated one, hence the Cortex-A76
    model. MongoDB 7 alone passed 35 checks on that model, with none failed.
- **Also kept:** the first start of the base image (a false failure of the checking tool), the first
  gateway build (a file-permission conflict) and the first gateway start (it failed before QEMU ran).
- **Data:** [`evidence/g1-yocto-qemu/`](evidence/g1-yocto-qemu/README.md) (base image),
  [`evidence/integrated-qemu/`](evidence/integrated-qemu/README.md) (gateway image and MongoDB 7).
- **Code:** `src/yocto/kas/` (`egw-qemuarm64.yml`, `egw-qemuarm64-integrated.yml`, their lock files);
  `src/yocto/scripts/` (`build.sh`, `build-profile.sh`, `run-qemu.sh`, `run-qemu-integrated.sh`,
  `boot_check.py`); steps in [setup/qemu_integrated_gateway.md](setup/qemu_integrated_gateway.md) §2–3.

## One device end to end

- **Done:** one simulated smartwatch sent one message per second for 60 s (seed 20260921). The six
  containers were then restarted together, with no message in flight.
- **Outcome:** 60 of 60 messages confirmed in time; none lost, late or accepted twice. After the
  restart the twin was read back unchanged.
- **Also kept:** a failed pre-check before the run.
- **Data:** [`evidence/g2-complete-flow/`](evidence/g2-complete-flow/README.md).
- **Code:** the test scripts in `tools/session/`; `src/egw_experiments/itest_reconcile.py`; steps in
  [setup/qemu_integrated_gateway.md](setup/qemu_integrated_gateway.md) §6.

## Functional tests

The tests below ran on one unchanged emulated gateway: the same image, containers and configuration
throughout. So did the 10-minute run without faults (see
[Delivery time under sustained load](#delivery-time-under-sustained-load)). Each test folder holds its
records and a `SHA256SUMS` seal.

- **Data:** [`evidence/g3-battery-2026-10/`](evidence/g3-battery-2026-10/README.md), one folder per
  test (linked below). The full record of every run, failed and incomplete attempts included:
  [test record](governance/g3-battery-2026-10-results.md).
- **Code:** `src/egw_experiments/` (`run.py`, `analyze.py`, `itest_reconcile.py`, `proved_down.py`,
  `recovery_qualification.py`); the test scripts in `tools/session/`; steps in
  [setup/qemu_integrated_gateway.md](setup/qemu_integrated_gateway.md) §7.

### Three device types at once

- **Done:** a smartwatch, a smart ring and a smart clothing item sent together for 60 s; three shorter
  runs of 30 s did the same.
- **Outcome:** passed. 672 of 672 messages in time, and three twins, each with its own access policy.
  Each short run: 336 of 336 in time.
- **Data:** [60 s run](evidence/g3-battery-2026-10/2026-10-02/20261002T154427Z_g3-qualification-t2_attempt01/),
  [short runs](evidence/g3-battery-2026-10/2026-10-02/20261002T150829Z_g3-qualification-t1-smokes_attempt01/).

### Invalid messages

- **Done:** a 120 s run mixed 67 invalid messages with 1,277 valid ones.
- **Outcome:** passed. All 67 invalid messages were rejected and none was accepted. All 1,277 valid
  messages were accepted, counted after the backlog cleared. This test is not timed.
- **Data:** [run folder](evidence/g3-battery-2026-10/2026-10-02/20261002T155313Z_g3-qualification-t3_attempt01/).

### Repeated messages

- **Done:** the 672 messages of a 60 s run were sent a second time. Then a new 60 s run started its
  message counters again at 0.
- **Outcome:** passed. None of the repeated messages was accepted again, and the twins did not change.
  The new run had 672 of 672 accepted in time: a restarted counter was not taken for a repeat.
- **Data:** [repeat](evidence/g3-battery-2026-10/2026-10-02/20261002T160154Z_g3-qualification-t4-replay_attempt01/),
  [new run](evidence/g3-battery-2026-10/2026-10-02/20261002T161432Z_g3-qualification-t4-reset_attempt01/).

### Network drop

- **Done:** during a 180 s run, the simulated devices lost their connection three times and
  reconnected, holding 165 messages meanwhile.
- **Outcome:** passed. 2,016 of 2,016 messages in time, none accepted twice. The broker log shows four
  disconnections for three drops; the fourth is the normal end of the session. The pass rests on that
  reading, which is stated with the result.
- **Data:** [run folder](evidence/g3-battery-2026-10/2026-10-02/20261002T162159Z_g3-qualification-t5_attempt01/).

### Controller restart

- **Done:** during a 600 s run at 11.2 msg/s, the controller was restarted once, 300 s in.
- **Outcome:** passed, but only under a criterion relaxed after an earlier attempt: the controller
  answers again within 120 s, and every valid message is accepted exactly once after the backlog
  clears. Here the controller answered after 12.134 s, and 6,720 of 6,720 messages were accepted
  exactly once. Delivery time was reported, not judged: 4,567 were confirmed in time and 2,153 later.
- **Also kept:** three earlier attempts, classed invalid: one for a measurement fault (in the
  repository), two kept locally.
- **Diagnostic run** (Section 4.4, Table B.1): one earlier run checked how the controller recovers its
  queue after a restart ([design record](adr/0011-controller-restart-recovery.md)). Its evaluator
  found that this one run supports the design. The test tools classed the same run invalid, and one
  twin count was off by one (explained in the folder). Two earlier tries were inconclusive (local).
- **Data:** [test run](evidence/g3-battery-2026-10/2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02/),
  [invalid attempt](evidence/g3-battery-2026-10/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01/),
  [diagnostic run](evidence/finite-proof-r03/README.md).
- **Code:** as above, plus `src/egw_experiments/proof_evaluator.py` and `tools/session/proof*` for the
  diagnostic run.

### Database or twin-service failure

- **Done:** in two 300 s runs at 11.2 msg/s, the database (MongoDB), then the twin service (Ditto),
  was interrupted and brought back.
- **Outcome:** passed. While each service was down, some messages failed after three attempts (44 with
  MongoDB down, 5 with Ditto down). Acceptance then resumed and the twins stayed consistent. Not
  timed: 1,209 and 1,895 messages were not confirmed in time, the failed ones included (reported only).
- **Data:** [MongoDB](evidence/g3-battery-2026-10/2026-10-03/20261003T135147Z_g3-qualification-t7-mongo_attempt01/),
  [Ditto](evidence/g3-battery-2026-10/2026-10-03/20261003T140639Z_g3-qualification-t7-ditto_attempt01/).

### Gateway reboot and persistence

- **Done:** the emulated gateway was rebooted with the six containers running.
- **Outcome:** passed. The six containers came back without manual help, and the three existing twins
  were identical. A 30 s run afterwards had 336 of 336 messages in time. Persistence was checked on
  the twins and on the names of the controller's event folders, not on every byte.
- **Also kept:** a first attempt that stopped before its checks. The procedure waited for QEMU to
  exit, which a reboot does not do.
- **Data:** [run folder](evidence/g3-battery-2026-10/2026-10-05/20261005T115131Z_g3-qualification-t8_attempt02/),
  [first attempt](evidence/g3-battery-2026-10/2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01/).

### Broker access control

- **Done:** five checks against the MQTT broker.
- **Outcome:** passed. A client given the wrong certificate authority could not connect: it rejected
  the broker's certificate. The broker refused a wrong password, an unencrypted connection and an
  anonymous client. A subscriber without permission received nothing from a topic it may not use. These are the controls tested, not a security audit.
- **Also kept:** a first attempt that never ran, because the earlier reboot attempt had stopped.
- **Data:** [run folder](evidence/g3-battery-2026-10/2026-10-05/20261005T120537Z_g3-qualification-t9_attempt01/).
- **Code:** as above, plus `src/deployment/scripts/probe-acl.sh`.

## Measurements under load

### Delivery time under sustained load

- **Done:** two 600 s runs at 11.2 msg/s: one without faults, and the controller-restart run.
- **Outcome: not met.** Neither run confirmed every message in time.

| Run | Confirmed in time | Latency, median | Latency, 95th percentile |
|---|---|---|---|
| Without faults | 4,584 of 6,720 | 178.8 s | 247.1 s |
| Controller restart | 4,567 of 6,720 | 128.0 s | 250.6 s |

- Latency runs from the controller receiving a message to Ditto confirming it, for the messages
  confirmed in time only.
- In the restart run, all 6,720 messages were accepted exactly once after the backlog cleared. The run
  without faults has no record taken after the backlog cleared, so its final count is not known.
- Shorter runs at the same rate (30 to 180 s) were in time. An earlier run without faults, kept
  locally, had 3,794 of 6,720 in time.
- **Data:** `other/processed.after/per_run.csv` in the
  [run without faults](evidence/g3-battery-2026-10/2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01/)
  and the [restart run](evidence/g3-battery-2026-10/2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02/).
- **Code:** `src/egw_experiments/analyze.py`.

### Resource use

- **Done:** during the two 600 s runs, the CPU and memory of the six containers were sampled throughout.
- **Outcome (descriptive).** Run without faults, 682 samples, sum of the six containers:

| Measure | Median | Maximum |
|---|---|---|
| Memory | 2,000 MB | 2,175 MB |
| CPU (% of one virtual CPU) | 218 % | 355 % |

- Ditto's things service averaged 608 MB, about 75 % of its 768 MiB limit. MongoDB peaked at 412 MB.
- Restart run, 601 complete samples: median memory 2,003 MB, median CPU 237 %.
- Table D.8 breaks the comparison's memory and CPU down by container and adds derived figures, such as
  processor time per accepted message. It is computed from the comparison's raw data, kept locally.
- **Data:** the raw samples `raw/<run>/resources.csv` in the two run folders above; the analyser's mean
  and maximum in `other/processed.after/resources_by_run.csv`.
- **Code:** `src/egw_experiments/analyze.py` for the mean and maximum. The sums, the 95th percentiles of
  Table 5.2 and Table D.8 come from scripts kept locally. The medians can be recomputed from the sealed
  files ([reproduce.md](reproduce.md)).

### Yocto vs Debian 13

- **Done:** the same six containers ran on the Yocto image and on Debian 13, with the same emulator
  settings and the same load: 600 s at 11.2 msg/s after 120 s of warm-up. Three pairs of runs, in the
  order Yocto–Debian, Debian–Yocto, Yocto–Debian, with seeds 2026101801 to 2026101803.
- **Outcome (exploratory).** Medians of three runs:

| Measure | Yocto | Debian 13 |
|---|---|---|
| Start to first SSH answer | 15.8 s | 46.3 s |
| Launch to services ready | 241.3 s | 322.3 s |
| Launch to gateway working (a twin read back) | 258.8 s | 341.9 s |
| Memory used during the load | 1,922.7 MiB | 2,304.3 MiB |
| Root file system used | 489 MiB | 1,458 MiB |
| Messages accepted per second (estimate) | 7.76 | 4.95 |
| Confirmed in time | 4,426 of 6,720 | 2,394 of 6,720 |
| Latency, median (messages in time only) | 220.1 s | 350.6 s |
| Time to clear the backlog (until 130 s with no activity) | 344.0 s | 668.3 s |
| Repeated or double-accepted messages | 0 | 0 |

- Neither system kept pace with 11.2 msg/s. The other messages were confirmed while the backlog
  cleared, in the five runs whose final record was checked. In one Yocto run that record could not be
  fetched, so the counts after the backlog have two Yocto runs and three Debian runs.
- **Also kept, not in the figures:** a first attempt, invalid because of a measurement fault, and two
  stops of the series for the same kind of reason. Nothing was repeated to replace them.
- **Data:** [`evidence/compare-a02/`](evidence/compare-a02/README.md): the table, one row per run
  (`summary.csv`, `summary.json`) and the plan (`plan-a02.json`). The raw records (583 files, about
  69 MB) are kept locally.
- **Code:** in `tools/compare/`: `measure_base.sh`, `measure_plan.py`, `measure_run.sh`,
  `measure_series.sh`, `guest_meminfo_sampler.sh`, `drain_hook.sh` and `measure_summary.py`;
  `python -m egw_experiments analyze`; `tools/session/proof_hook_drained.sh` and `nominal_account.py`.
  The procedure and calculation rules used are in [tools/compare/README.md](../tools/compare/README.md)
  §10; [PROTOCOL.md](../tools/compare/PROTOCOL.md) is an earlier proposal. The plotting scripts of
  Figures 5.1–5.2 are kept locally; their input is `summary.csv`.

### Host-load check

- **Done:** one more run of the unchanged comparison procedure on the Yocto image, with the PC itself
  sampled once per second, to see how busy the PC was and how much disk the image used.
- **Outcome:** one run, not pooled with the comparison.
  - During warm-up and load, the PC's 16 logical processors were busy 17.1 % on average (95th
    percentile 21.7 %). QEMU used 276 % of one processor on average; the simulated devices at most 2 %.
  - The root file system used 489–494 MiB.
  - 4,144 of 6,720 messages were in time; all 6,720 were accepted once after the backlog cleared.
- **Data:** kept locally. Table D.5 also uses the resource maxima of the two 600 s runs above.
- **Code:** `tools/compare/measure_run.sh`, unchanged. The PC sampler and analysis scripts are local.

## Other records

- **Requirements** (Section 5.6, Tables 5.4 and A.2). The dissertation reads the results above against
  its list of requirements. This adds no data. The repository holds an earlier version of that list:
  [academic/gateway_requirements_and_platform_selection.md](academic/gateway_requirements_and_platform_selection.md).
- **Unit tests** (Table B.1). They use stand-ins for MQTT and Ditto. In the repository: 701 passed
  ([`evidence/tests/2026-08-11-head-4e67717/`](evidence/tests/2026-08-11-head-4e67717/)). A later run,
  kept locally: 4,044 passed, 12 skipped. Code: `src/tests/`; the command is in
  [src/README.md](../src/README.md).
- **A pilot of longer, repeated runs** (Section 5.7). It was started but not finished, and the
  dissertation cites no figure from it. One session stopped at its start, and one run was recorded as
  failed: 33 messages failed while its backlog cleared. Plan:
  [experiments/g4-pilot/](../experiments/g4-pilot/README.md); records kept locally.
- **Demonstration checks are not results.** The checks of the two comparison environments
  ([tools/compare/README.md](../tools/compare/README.md) §9) and of the demonstration scenarios
  ([demo.md](demo.md)) only show that the demonstration works. The additional Yocto demonstration
  scenario was never measured; its times are not comparable with the comparison.

## Limitations

- **Emulation on one PC.** Nothing here describes speed, capacity or energy on real ARM hardware.
- **Timing under load.** No 600 s run, on either system, confirmed every message in time at 11.2 msg/s.
- **A small comparison.** Three runs per system; kernel, container runtime and system software all
  differ, so no effect of the distribution alone can be isolated.
- **Each test shows only what it tested.** "Exactly once" means one acceptance per message of that
  run. The access checks are not a security audit. Persistence was checked on the twins and on the
  names of the event folders.
- **No large series.** A larger planned series of repeated measurements was not run.
- **Some data are local.** Table 5.2's percentiles, Tables D.5–D.8 and Figures 5.1–5.2 cannot be fully
  recomputed from the repository alone.

## Data kept locally

These stay in the student's local `output_test` folder ([setup/local_test_outputs.md](setup/local_test_outputs.md)),
each with its own `SHA256SUMS`:

| Data | Local folder |
|---|---|
| Raw records of the comparison | `runs/2026-10-19/HIST_2026-10-19-compare-measurements-a02` |
| Host-load check | `runs/2026-10-24/HIST_2026-10-24-req10-req11-host-contention-and-storage` |
| Later unit-test run | `runs/2026-10-08/HIST_2026-10-08-g4-pr60-corrections-integrated-attempt01` |
| Earlier attempts: controller restart, diagnostic tries, the first run without faults, early trial runs on the gateway image, the pilot | under `runs/` |

The scripts for Table 5.2's sums and percentiles, Table D.8, the host-load analysis and Figures 5.1–5.2
are in the dissertation's working folder.
