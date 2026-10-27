# The `nominal-r01` backlog — corrected diagnosis

- **Date:** 2026-09-21
- **Package:** D, first half — diagnosis of the message backlog of the nominal run of 2026-09-19. The controller's restart recovery is the second half and is proposed in ADR 0011 (`adr-0011-controller-restart-recovery.md`, beside this document), not here.
- **Status:** corrected draft for review, round three. It replaces the round-one draft `../backlog_diagnosis.md`, applies every finding of the two round-one verification reports (`../verification_figures.md`, `../verification_constraints.md`) that concerns the diagnosis, and applies the findings of the two round-two reports (`verify_figures.md`, `verify_constraints.md`, beside this document) that concern it; section 12 maps each one to where it is handled. It is **not** presented as verified — that is for the project manager's review. It closes no gate, admits no claim, accepts no result, and changes no threshold, deadline, offered load, warm-up, ingest rule or protocol.
- **Platform label, governing every figure:** an **ARM64 guest emulated under QEMU/TCG** — Poky 5.0.19 `scarthgap`, kernel `6.6.142-yocto-standard`, 4 vCPU, 8,204,356 kB — on an x86_64 WSL2 host with 16 CPUs [`sut_environment.json`, `loadgen_environment.json` → s01 §0]. The guest description comes from a file captured at 2026-09-19T00:06:48Z, 19.9 h before the measured window, and copied into the run by the harness's `--sut-env-from` (`~/egw-tcg/itest-helpers.sh:244`): it describes that earlier capture of the guest, not the run's own boot [`sut_environment.json`, `manifest` → s08 §E]. The host line is the load generator's environment. No figure here is native performance; the preserved data contain no native measurement, so none is translated to native hardware. **No capacity, sustainable-rate or maximum-throughput statement is made**: one failed offered load cannot support one.
- **Method:** read-only analysis of data that already exist. No guest was started, no run repeated, nothing measured live, no network touched; nothing under the repository, the raw runs, the attempts, `output_test` or the project-management folder was modified. The only git commands run were read-only (`diff`, `log`, `rev-parse`, `show`, `merge-base --is-ancestor`, `branch --contains`).
- **Code identity:** `src/egw_controller/` is byte-identical between the run's commit `fe954a9` and the merged `dev` head `35fe8bb`, and also `b7e0c83` (the WSL clone's head, an ancestor of `35fe8bb`) and `3549d46` (the branch that records the pause answer, not on `dev`): `git diff fe954a9 <head> -- src/egw_controller/` is empty for all three. The other files cited here are unchanged between `b7e0c83` and `35fe8bb`. Code and documents are cited at `35fe8bb` [s09].

---

## 0. How to read the provenance

Every figure is followed by `[file → sNN §X]`: the source file, then the script `scripts/sNN_*.py` (`s09` is `scripts/s09_code_identity.sh`) and the section X of its output `out/sNN_*.out.txt`, both beside this document. Every figure used as evidence here was re-derived by those scripts. Round-one and first-verification values appear only where a correction is described, labelled as superseded, never as evidence.

| Short name | File (all read-only) |
|---|---|
| `sent` | `/home/ruisth/egw-tcg/pilot/results/raw/nominal-r01/sent_events.jsonl` |
| `sealed` | `…/nominal-r01/events.jsonl` — the harness's own fetch, sealed |
| `metrics` | `…/nominal-r01/controller_metrics.csv` |
| `res` | `…/nominal-r01/resources.csv` |
| `manifest` | `…/nominal-r01/manifest.json` |
| `post` | `/home/ruisth/egw-exec/attempts/20260919T195827Z_nominal-instrumentation-120-600_attempt01/analysis/events.post-drain.jsonl` |
| `warm` | `…/analysis/warmup.events.jsonl` |
| `acct` | `…/analysis/accounting.json` |
| `snap` | `…/analysis/snapshots/nominal-r01.metrics.{before,after}.json` |
| `cmds` | `…/commands.jsonl` of the same attempt |
| `console` | `…/console/NNN-*.stdout.txt` of the same attempt |

**Clock domains.** Controller monotonic (`sealed`, `post`, `warm`) carries every latency and every ordering. Harness monotonic (`sent`), harness wall (`metrics`, `manifest`, `cmds`) and guest wall (`res`, and the `wall_utc` of the controller's own `/metrics` answers in `snap`) are joined to it only through the controller end marker in `manifest` (2,331,405,170,833 ns, read at harness wall 20:12:45.750Z, lag 0.018718 s), and never for latency. At the marker the guest wall read 0.126 s ahead of the harness wall [manifest → s06 §D]. **el** = seconds from the measured-window start in the controller clock (end marker minus the 600.106644 s measured duration). The run is `valid` with no deviations [manifest → s01 §0].

---

## 1. Summary

- **The recorded result.** 3,794 of 6,720 identities were confirmed within the deadline; 2,926 were not — 85 confirmed late and 2,841 with no outcome when the harness fetched the log. A separate observation after the drain shows all 2,926 eventually accepted, late. Nothing was dropped, rejected, duplicated or failed (section 2).
- **What the queue did.** At 11.2002 msg/s offered, the controller served fewer messages than arrived in **every one of the 60 ten-second blocks** of the measured window, so the number of messages inside it grew throughout the window, from 750 to 3,593 (section 3).
- **Where the time went.** Each message's latency is exactly its wait behind earlier messages plus its own passage; the wait is 99.96 % of the summed latency (section 4).
- **What the served rate reflects.** Each measured message occupied the single consumer for 151.44 ms on average while ingress ran, drifting from 181 to 117 ms inside the window; the served rate is the reciprocal of that occupancy by identity. What the occupancy consists of, and whether it depends on the consumer being serial, is not established. For at least 63.3 % of the time the consumer was busy, the controller container was not on a CPU; whether that time was the Ditto `PATCH`, the event-log write, waiting to be scheduled or something else the code allows cannot be separated (sections 5–7).
- **Not established.** Any capacity or steady service rate; what moved the service rate during the run; what inside the Ditto round trip takes the time; whether more concurrency would help; what an empty start would have produced — the warm-up counterfactual is **dropped** because it is not derivable without an untestable assumption (section 9).
- **Proposed, for the student's decision.** One bounded diagnostic run: 2.24 msg/s for 720 s, sized against the **lowest** rate this run served (4.60 msg/s over its first minute), asking whether the queue stays bounded below every rate the run showed and how long one passage takes when nothing waits ahead of it (section 11). Whether it runs, and whether before the recovery decision, is option T3 of ADR 0011's throughput decision.

---

## 2. The three populations, and when each was collected

The confirmation deadline is the controller end marker plus the unchanged 60 s: 2,391,405,170,833 ns controller monotonic, 60.000000000 s after the marker [manifest → s01 §A]. Through the marker it corresponds to about 20:13:45.750Z harness wall [manifest → s01 §D] — a mapping, not an artefact line. The log was collected twice: by the harness fetch, and by a separate post-drain observation. The first 3,879 lines of the post-drain file are byte-identical to the sealed file [sealed, post → s01 §B]: one log, read at two instants.

| | Population | Count | Seen in | Collected at |
|---|---|---:|---|---|
| **P1** | Confirmed within the deadline | **3,794** | `sealed`; the same 3,794 identities in `post` | **Harness fetch**: scp started 20:13:57.289Z (`manifest` `events_fetch`), harness command ended 20:13:58.570Z (`cmds` seq 4); the newest record read is an acknowledgement 12.659 s after the deadline (≈ 20:13:58.409Z harness wall). The fetch read the log between 11.539 s (scp start) and 12.820 s (command end) after the deadline [manifest, cmds, sealed → s01 §D]. |
| **P2** | Confirmed late, already visible at the fetch | **85** | `sealed` | Same fetch; acknowledgements from 0.012 s to 12.659 s after the deadline [sealed → s01 §D] |
| **P3** | **No outcome at the original collection point** | **2,841** | absent from `sealed` | Same fetch |
| P2′ | Confirmed late (eventual delivery), as seen after the drain | **2,926** = the 85 of P2 + all 2,841 of P3 | `post` | **Post-drain observation**, its scp starting 466.238 s after the harness fetch's: `drained` ran 20:13:58.613Z → 20:21:43.488Z (`cmds` seq 5) and saw `queue_depth` 0 with unchanged counters on 27 readings over 131 s (`console/005-post-drain`); scp 20:21:43.527Z → 20:21:44.589Z (`cmds` seq 6); newest acknowledgement in the file 345.362 s after the deadline (≈ 20:19:31.111Z) [cmds, console, post → s01 §D] |
| P3′ | No outcome after the drain | **0** | `post` | Same observation; the `/metrics` reading at 20:21:45.640Z (the controller's own wall clock, i.e. the guest's) shows `accepted` = `received` = 8,124, `queue_depth` 0, `in_progress` 0, `dropped` 0, `processing_errors` 0, 134.402 s after the last acknowledgement [snap → s01 §D] |

Transitions by identity: P1 → P1 3,794; P2 → P2′ 85; P3 → P2′ 2,841 [sealed, post → s01 §C]. Per device at the fetch (in time / late / no outcome): `smart_clothing` 3,387 / 75 / 2,538, `smartwatch` 339 / 8 / 253, `smart_ring` 68 / 2 / 50 — identical to `acct` [sealed, acct → s01 §C].

**Rules that follow** (as the project manager's review record `PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 2.3, requires):

1. **The run's delivery result is P1 against 6,720**: `delivered_unique` 3,794 and `lost` 2,926, i.e. 56.46 % in time and 43.54 % not [acct → s01 §C]. `lost` there means "not confirmed uniquely within the deadline" and is 85 (P2) + 2,841 (P3). It is not reset to zero by the drain, and it is not read as permanent disappearance.
2. **P2′ never stands in for a deadline count, nor a deadline count for P2′.** P2′ equals `lost` numerically only because every P3 identity was later accepted; it is a different population, observed at a different instant.
3. **What the post-drain file adds about P3, and nothing more:** all 2,841 had been received before the deadline (no measured identity was received after it) and were acknowledged between 12.891 s and 345.362 s after it [post → s01 §D]. The statement "2,926 were still inside the controller at the deadline" is the same predicate as P2′ once every identity has arrived — **not** an independent confirmation, which round one claimed it was.
4. 736 publish records carry no `puback_monotonic_ns` [sent → s01 §A]. That field is the simulator's best-effort capture and defines no population here.

**Latency by population** (seconds; the harness's own percentile convention, `src/egw_experiments/analyze.py:499-516`):

| Population | Collected at | n | mean | p50 | p95 | p99 | max |
|---|---|---:|---:|---:|---:|---:|---:|
| **P1, in time — the run's reported latency** | harness fetch | 3,794 | 254.169 | **264.430** | **321.070** | 322.713 | **323.248** |
| P2, late at the fetch | harness fetch | 85 | 322.905 | 322.282 | 325.907 | 326.303 | 326.483 |
| P2′, late | post-drain | 2,926 | 371.312 | 374.706 | 404.244 | 405.047 | 405.470 |
| all 6,720 | post-drain | 6,720 | 305.175 | 320.275 | 402.699 | 404.444 | 405.470 |

[sealed, post → s01 §E]. Only the first row is the run's latency: it reproduces `acct` `harness_row` (264.429926 / 321.069848 / 323.248067 s) to the microsecond [acct → s01 §E]. The post-drain rows include acknowledgements up to 345 s after the deadline. Round one quoted the last row (320.27 / 402.70 / 405.47 s) as the run's distribution; it is not.

---

## 3. What the queue did

### 3.1 Offered, arrived, served

| Quantity | Value | Source |
|---|---|---|
| Offered | 11.200204 msg/s over the publish span; 6,720 records, first at +0.156 s and last at +600.055 s from the window start (harness clock); plan 11.2 | [sent → s02 §A] |
| Offered per 60 s block from the window start | 671, then 672 in each of the other nine blocks: 11.1833–11.2000 msg/s. The run-level rate matches the plan to three decimal places (11.200); a 60 s block cannot, since 60 s of 11.2 msg/s is not a whole number of messages | [sent → s02 §A] |
| Messages marked `intended_invalid` | 0 | [sent → s02 §A] |
| Arrivals at the controller | 11.201088 msg/s (controller clock) | [post → s02 §B] |
| Served, warm-up, counters | 593 over 120.047 s = 4.939732 msg/s | [metrics → s02 §C] |
| Served, window, counters | 3,863 over the 598.261 s between the first and last in-window samples = **6.457048 msg/s** | [metrics → s02 §C] |
| Served, window, event log | 3,878 acknowledgements in el (0, 600.107] = 6.462185 msg/s — +0.0796 % against the counters, from a different mechanism | [warm, post → s02 §C] |
| Served after the window end, event log | 3,593 acknowledgements up to the last one at el +1,005.469 s: 3,593 ÷ (last acknowledgement − window end) = 8.863682 msg/s (a definition; other natural definitions move the fourth decimal) | [warm, post → s02 §C] |
| Offered ÷ served, window, counters | 1.734570; net accumulation 4.743156 msg/s | [sent, metrics → s02 §C] |

**Served rate in 60 s blocks** under one unchanged offered load:

| el (s) | arrivals | acknowledgements | msg/s, event log | msg/s, counters |
|---|---:|---:|---:|---:|
| −120 … −60 | 671 | 276 | **4.6000** | **4.6009** |
| −60 … 0 | 672 | 317 | 5.2833 | 5.2899 |
| 0 … 60 | 672 | 393 | 6.5500 | 6.5428 |
| 60 … 120 | 672 | 334 | 5.5667 | 5.5650 |
| 120 … 180 | 672 | 319 | 5.3167 | 5.3158 |
| 180 … 240 | 671 | 360 | 6.0000 | 6.0130 |
| 240 … 300 | 673 | 369 | 6.1500 | 6.1400 |
| 300 … 360 | 672 | 370 | 6.1667 | 6.1520 |
| 360 … 420 | 672 | 392 | 6.5333 | 6.5527 |
| 420 … 480 | 672 | 413 | 6.8833 | 6.8607 |
| 480 … 540 | 672 | 414 | 6.9000 | 6.9094 |
| 540 … 600 | 672 | 513 | 8.5500 | 8.4576 |

[warm, post, metrics → s02 §D]. The served rate was neither steady nor monotone: inside the window it fell for three minutes (6.55 → 5.32) and then rose to 8.55; in 30 s blocks it spans 5.10 (el 120–150) to 9.47 (el 570–600) [s02 §D]. Round one's "monotone climb 4.94 → 6.46 → 8.86" was three phase averages, and its "climbed 61 %" and "33 % below its eventual value" do not reproduce from the blocks; both are dropped.

### 3.2 The queue

- `controller_metrics.csv` has 721 samples; `queue_depth` is 0 in exactly two, at 20:00:45.540Z and 20:00:45.566Z, both before the first arrival at ≈ 20:00:45.763Z [metrics, warm → s02 §E].
- Inside the window (599 samples) the depth starts at 752, ends at 3,590, never goes below 752, and falls between consecutive samples only six times, by at most 3 [metrics → s02 §E]. The queue never drained inside the window.
- Reconstructed from the event stamps (arrivals minus acknowledgements up to an instant; one message in service whenever the controller is non-empty): **750** in the controller at el 0 (749 waiting + 1), **3,593** at the window end (3,592 + 1), 2,926 at the deadline [warm, post → s02 §E].
- `dropped`, `rejected`, `duplicate` and `failed` are zero in every sample [metrics → s02 §E]. The peak of 3,590 is 35.9 % of the 10,000-message cap (`src/egw_controller/service.py:39`); the overflow path was never exercised.
- Growth: sampled 752 → 3,590 = 2,838 over 598.261 s, against 2,837.65 predicted by the deficit over the same interval; the reconstruction gives 750 → 3,593 = 2,843 over 600.107 s, i.e. 4.7375 msg/s [s02 §E]. The figures agree at the 0.2 % level; round one's "closes exactly" was a rounding coincidence.

### 3.3 The conclusion this carries, and no further

> **At 11.2 msg/s offered, the controller at `fe954a9` in this configuration, on this emulated guest, served fewer messages than it received in every one of the 60 ten-second blocks of the 600 s window [warm, post → s02 §D], so the number of messages inside it grew throughout the window, from 750 to 3,593. The deadline failure is lateness, not destruction: every one of the 6,720 identities was eventually accepted, 2,926 of them after the deadline, and none was dropped, rejected, duplicated or failed (section 2).**

What it does **not** carry:

- **No capacity, no sustainable rate, no maximum throughput.** Under one unchanged offered load the served rate moved between 4.60 and 8.55 msg/s in 60 s blocks; one failed load does not define the rate this stack could sustain. The ratio 1.7346 is a ratio of two rates of this window, not a distance to a ceiling, and whether any change within the present design would close it is something these data can neither rule in nor rule out (section 7.2). Round one's "no amount of tuning within the present design closes a factor of 1.73" is withdrawn.
- **Nothing about other loads or other timed conditions.** The 1 Hz slice of the same day passed (`PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 2.3); only the 11.2 msg/s nominal workload failed its deadline in this configuration.
- **Nothing about restart losses.** Identities that never obtained any outcome — the failure mode of the two invalid `controller_restart` runs — are a different failure and belong to the recovery decision. Their split in `controller_restart-r02` into received-and-discarded, never-delivered and undetermined depends on an assumed disconnect instant and is not direct proof (`../restart_evidence.md`, section 4). What this run adds to that decision is one observed count and one source reading: at the window end 3,593 identities were inside the controller [s02 §E], held in an in-process `asyncio.Queue` (`service.py:150-152`); what a restart at that instant would have done to them is not established by this run.
- **Nothing native.**

---

## 4. Where each message's time went

### 4.1 The checks the split rests on

- The 8,064 messages of the run (1,344 warm-up + 6,720 measured) were acknowledged in exactly their arrival order (FIFO) [warm, post → s03 §A].
- The last warm-up arrival (el +0.009955 s) precedes the first measured arrival (el +0.193468 s), and the last warm-up acknowledgement (el +126.513075 s) precedes the first measured one (el +126.661899 s): warm-up and measured messages do not interleave [s03 §A].
- No message arrived after its predecessor's acknowledgement, so the single consumer was **continuously busy** from the first arrival (el −119.880 s) to the last acknowledgement (el +1,005.469 s) [s03 §A].
- For every record, (acknowledgement − arrival) ÷ 10⁶ equals `latency_ms` exactly [s03 §A].
- The first message of each of the three devices is a warm-up message, so the first-contact seeding of the twins happened in the warm-up; no record has `attempts` > 1 or a non-null `error` [s03 §A].

**Code basis.** `received_monotonic_ns` is taken on the MQTT network thread at arrival (`src/egw_controller/mqtt.py:187-189`) and the message is handed to the event loop (`:199`); one strictly serial consumer takes a message and awaits its whole processing before the next (`service.py:175-197`, loop at `:182-190`); the acknowledgement stamp is taken after the awaited Ditto `PATCH` returns (`service.py:320`, `:331`); `latency_ms` = acknowledgement − arrival (`:342`); the event line is written and flushed after the stamp (`service.py:414`, `events.py:112-119`). There is **no stamp at dequeue and none around the HTTP call**.

### 4.2 The exact split

Given those checks, for measured message *k* in service order: **wait**ₖ = ackₖ₋₁ − arrivalₖ, **own**ₖ = ackₖ − ackₖ₋₁, and latencyₖ = waitₖ + ownₖ exactly. No service rate is assumed.

| | min | p50 | mean | p95 | max |
|---|---:|---:|---:|---:|---:|
| wait (s) | 126.320 | 320.194 | 305.044 | — | 405.370 |
| own (ms) | 59.68 | 112.61 | 130.80 | 217.47 | 2,542.14 |

[warm, post → s03 §B]

- The wait is **99.9571 %** of the summed latency of the 6,720 messages; per message, the wait share is 99.9638 % at the median and 98.6474 % at its smallest [s03 §B]. Round one's 99.9572 % came from the approximation 1 ÷ (messages ahead + 1); the exact split replaces it.
- The first measured message: latency 126.468 s = 126.320 s waiting behind the 749 warm-up messages then in the controller + 0.149 s of its own [s03 §B].

**What "own" is.** Everything the consumer did between two acknowledgement stamps: the previous event line's write and flush, dequeue, decode, validation, dedupe, the merge patch, the Ditto `PATCH` round trip, and any interval in which the consumer was runnable but not running. It is **not** the Ditto round trip, and it was measured under two conditions — for 3,127 messages while ingress ran, for 3,593 after it stopped (section 5).

---

## 5. The per-message budget, corrected

| Population | n | mean | p50 | p95 | 1 ÷ mean |
|---|---:|---:|---:|---:|---:|
| **M-in** — measured messages acknowledged inside the window, ingress running (el 126.66–600.107) | 3,127 | **151.44 ms** | 128.57 | 248.94 | 6.6032 msg/s |
| M-after — measured messages acknowledged after the window end, no ingress | 3,593 | 112.83 ms | 97.97 | 182.03 | 8.8628 msg/s |
| M-all — all 6,720 measured messages (mixes both conditions) | 6,720 | 130.80 ms | 112.61 | 217.47 | 7.6454 msg/s |
| W-in — warm-up messages acknowledged inside the window | 751 | 168.58 ms | 139.61 | 298.58 | 5.9318 msg/s |
| D — every acknowledgement inside the window (round one's "154.77 ms") | 3,878 | 154.76 ms | 130.86 | 261.08 | 6.4616 msg/s |

[warm, post → s03 §C]

- **D is not a figure of the measured window's messages**: 751 of its 3,878 messages (19.4 %) are warm-up messages, carrying 126.605 s of its 600.160 s of consumer time (21.1 %) [s03 §C]. The measured window's own messages, served while ingress ran, are **M-in: 151.44 ms**.
- **M-in is not steady.** By 60 s block of the acknowledgement: 181.09 ms (el 120–180, n = 295), 166.33, 163.01, 162.25, 152.81, 145.36, 145.03, then 116.98 ms (el 540–600, n = 513); no measured message was served in el 0–120 [s03 §C].

**What it is:** the mean time the single, continuously busy consumer spent per message between two acknowledgements, for the named population and interval.

**What it is not:**

- **not a second observation of the served rate.** Its reciprocal is the served rate of the same population over the same interval by construction: D's 3,878 gaps sum to exactly the 600.160 s between the last pre-window and the last in-window acknowledgement [s03 §C]. Round one's "1 ÷ 0.15477 s = 6.46 msg/s, which is what was observed" is an identity — and it did not even match the counter rate (6.4616 against 6.457048 msg/s);
- **not the Ditto round trip** — section 6.2 bounds how much of it can be off the controller's CPU; nothing says how much of it is the `PATCH`;
- **not a message's latency** — at the median wait share (99.9638 %) the own passage is 0.0362 % of a message's latency (section 4.2);
- **not a steady-state service time** — it drifts from 181 to 117 ms inside the window;
- **not a capacity, ceiling or maximum rate** — it was measured while the consumer was saturated at one offered load;
- **not transferable** to another offered rate or configuration, and **not native**.

---

## 6. The resource picture

### 6.1 The six sampled containers, measured window (600 instants)

`cpu_pct` is 100 × Δ`usage_usec` ÷ Δ elapsed from cgroup v2 inside the guest: 100 = one vCPU, and the guest's four vCPUs are 400 (`src/deployment/scripts/collect-resources.sh:60-67`).

| Container | CPU % mean | p50 | p95 | max | memory, max % of its limit |
|---|---:|---:|---:|---:|---:|
| `egw-ditto-things-1` | 70.63 | 62.06 | 126.47 | 177.62 | 76.13 |
| `egw-ditto-gateway-1` | 65.52 | 60.05 | 109.35 | 190.12 | 68.02 |
| `egw-controller-1` | 36.70 | 28.19 | 109.64 | 128.28 | 26.94 |
| `egw-mongodb-1` | 28.87 | 8.89 | 114.49 | 160.83 | 76.45 |
| `egw-ditto-policies-1` | 19.95 | 12.77 | 60.01 | 116.85 | 70.89 |
| `egw-mosquitto-1` | 5.16 | 2.79 | 15.34 | 84.17 | 5.44 |
| **sum of the six** | **226.83** | 220.49 | 316.79 | 361.77 | — |

[res → s06 §B]

- Summed CPU ≥ 300: 55 of 600 instants; ≥ 350: 5; ≥ 380: none [res → s06 §B]. The highest in-window median is `ditto-things` at 62.06 % (round one's "63 %" does not reproduce; over all 720 instants the two highest medians are 65.98 % `ditto-things` and 63.12 % `ditto-gateway`) [res → s06 §B].
- Shares of the six containers' CPU: Ditto services 68.82 %, MongoDB 12.73 %, controller 16.18 % [res → s06 §C]. Per acknowledgement inside the window — all 3,878, 751 of them warm-up, because CPU cannot be attributed to individual messages — the six containers spent 350.94 ms of CPU and the controller 56.78 ms [res, warm, post → s06 §C].
- Mosquitto held 4.27 MiB on average [res → s06 §B]. No container was OOM-killed or restarted [console/010 → s06 §E]. The deployment sets memory limits only, no CPU limits (`src/deployment/compose.yaml`) [s09].
- Coverage: 720 instants × 6 containers, maximum spacing 1.000 s; **one** instant after the window end, so nothing is known about resources during the drain [res → s06 §A].

**What can be said, and how little it is.** No container has a CPU limit, so none can be saturated against a limit of its own; what could saturate is the guest's four vCPUs, and the six containers' one-second means summed to at most 361.77 % of 400 % [res → s06 §B]. One-second means can hide saturation inside a second, and only the six container cgroups were sampled, so the guest's other processes (the container daemon, the SSH server, the collector itself, the kernel) and QEMU's own threads on the host are unobserved: guest-level or host-level saturation cannot be excluded. Round one's "nothing was saturated", and round two's "no CPU saturation was observed in the six sampled containers", are both withdrawn.

### 6.2 The controller's CPU against the consumer's busy time

The consumer was busy for the whole window (section 4.1). Averaged over the 600 instants, the whole controller container — consumer, MQTT network thread, `/metrics`, event-log writes — used **36.70 %** of one vCPU: 220.19 CPU-seconds summed over the 600 one-second instants (36.692 % if divided by the 600.107 s window instead; immaterial) [res → s06 §C]. The consumer's own CPU time is part of that, so the consumer can have been running for at most 36.70 % of the window: for **at least 63.30 %** of the time it was busy with a message, it was not on a CPU (the other threads' share makes the true figure larger, by an amount these data do not give). That time includes awaiting the Ditto `PATCH` (the only `await` on the path of an already-seeded device, `service.py:320`; `attempts` is 1 everywhere, so there was no back-off sleep), the synchronous event-log write and flush (`events.py:112-119`), and being runnable but not scheduled on four emulated vCPUs. The list is not exhaustive: the code also allows, for example, the event-loop thread waiting for the interpreter lock while the MQTT network thread runs. **The data cannot divide it.** Round one attributed all of it to the Ditto round trip; that does not follow, and its "130 ms for one HTTP `PATCH`" (the whole passage, mislabelled) and "emulation is the multiplier, not the mechanism" (a statement about native cost with no native evidence) are withdrawn.

### 6.3 Acknowledgements against summed CPU — an association only

| Summed CPU band (%) | instants | acknowledgements/s, event log (E) | acknowledgements/s, counters (C) |
|---|---:|---:|---:|
| 150–200 | 221 | 7.937 | 7.904 |
| 200–250 | 174 | 6.546 | 6.538 |
| 250–300 | 149 | 5.168 | 5.174 |
| 300–350 | 50 | 3.740 | 3.860 |
| ≥ 350 | 5 | 3.600 | 3.791 |

Pearson r against summed CPU: E −0.6229, C −0.6337; one instant below 150 falls in no band [res, warm, post, metrics → s06 §D]. E counts every acknowledgement, warm-up and measured, in the second before each resource instant (guest wall), mapped through the controller's own wall reading at the marker. C differences the interpolated `accepted` counter (harness wall) over the same second, after mapping the resource instant from guest wall to harness wall with the marker's offset (+0.126 s). Round two read the guest instant as harness wall for C (7.929 → 3.786, r −0.6589); that was not the same second, and it is corrected here [s06 §D]. Round one's figures (8.005 → 3.800, r −0.6126) and the verification's (7.873 → 3.800, r −0.5972; r −0.3869 when warm-up acknowledgements are left out) differ from these by construction: the sign and rough size are stable, the digits are not. **Seconds with more container CPU are seconds with fewer acknowledgements**; that could be contention slowing the path, or CPU spent on work that is not acknowledgements (MongoDB bursts, JVM activity). These data cannot say which.

---

## 7. The causal account

### 7.1 What the data support

1. **The latency is queue wait**: 99.96 % of the summed latency is time spent behind earlier messages (section 4.2).
2. **The wait grew because service fell short of arrivals throughout**: fewer acknowledgements than arrivals in every ten-second block of the window, 2,843 more messages in the controller at its end than at its start [warm, post → s02 §D, §E]. The first measured message already waited 126.32 s behind the warm-up backlog [warm, post → s05 §A]. By count, the 3,593 in the controller at the window end are the 750 carried over from the warm-up at el 0, plus the window's 6,721 arrivals (one of them a warm-up message), minus its 3,878 acknowledgements, 751 of which served warm-up messages [warm, post → s08 §B]. That none of the 3,593 was itself a warm-up message follows from FIFO order; it does not show that the warm-up backlog had no bearing on that count, which is the counterfactual of section 9.2 and is not established.
3. **The served rate equals, by identity, the reciprocal of the single consumer's mean occupancy per message** (section 5; `service.py:182-190`). What that occupancy consists of, and whether it depends on the consumer being serial, is not established (section 7.2, items 1 and 6). The consumer can have been running for at most 36.70 % of that occupancy on average, the whole controller container's CPU share [res → s06 §C].
4. **The resources around it**: the six containers averaged 2.2683 of 4 vCPUs (226.83 %) and peaked at 3.6177 (361.77 %) [res → s06 §B]; 68.82 % of their CPU was in the three Ditto services; no container reached its memory limit; acknowledgements fall as summed CPU rises (section 6).
5. **The service rate moved under constant offered load, and again when ingress stopped.** In 30 s blocks: 9.47 msg/s in the last half-minute of the window; 11.60 and 10.63 in the first minute after it; 6.90 in the half-minute that contains the harness's collector fetch hook (20:13:48.078Z → 20:13:57.285Z) and events scp (20:13:57.289Z); then 7.90–9.53 in the ten full 30 s blocks that followed, and 10.29 in the last, partial block (158 acknowledgements in the 15.362 s before the last acknowledgement), when the backlog cleared [warm, post, manifest → s02 §F, §G; s08 §D].

### 7.2 What the data cannot separate

1. **Inside one passage**: controller computation, the `PATCH` round trip, event-log I/O and scheduling delay. Nothing is stamped between the two stamps, and the CPU series is a 1 s average over a whole container.
2. **Inside the Ditto round trip**: gateway routing, policy enforcement, `things` persistence, the MongoDB write. CPU shares are not latency shares.
3. **Why the service rate moved.** A warm-up (time or state) effect, contention with ingress and the harness's own activity in the guest are confounded. At the window end publication stopped (last arrival el +600.046 s), the resource collector was stopped (hook at 20:12:45.769Z) and the 1 Hz `/metrics` polling ended (last sample 20:12:44.846Z), all together [post, manifest, metrics → s02 §B, §F]; the rise inside the window happened at constant offered load; and after ingress stopped the rate did not stay high. Round one's "that difference is the cost of receiving" compared the first half-minute of the drain (11.600 msg/s, 1.7965 × the window's counter rate [s02 §F]) with the window **average**; against the adjacent half-minute the step is 9.47 → 11.60, and it did not last.
4. **The direction of the CPU–acknowledgement association** (section 6.3).
5. **The guest outside the six containers, and the host** — unsampled.
6. **Whether more concurrency in the consumer would raise the served rate.** 89.2857 % of the measured messages (6,000 of 6,720) target one twin [sent → s01 §A], and how Eclipse Ditto orders concurrent updates to one thing is not established from any source this project may use. The project manager's instruction stands: no concurrency and no resource-limit change without addressing ordering, duplicates, durability and configuration identity. This document proposes neither.
7. **Anything native.**

---

## 8. Little's law is an identity here, not a check

- The system is empty at both ends of the interval bounded by the two `/metrics` snapshots — 20:00:42.825Z (`queue_depth` 0, `in_progress` 0, `accepted` 60) and 20:21:45.640Z (0, 0, 8,124), both on the controller's own (guest) wall clock [snap → s04 §A, s08 §C]. The 8,064 messages give ∫N dt = Σ sojourn = 2,143,130.910 message-seconds. Over the busy interval inside it, from the first arrival (el −119.880 s) to the last acknowledgement (el +1,005.469 s), 1,125.348 s: L = 1,904.4154, λ = 7.1658 msg/s, W = 265.7652 s, L ÷ (λW) = 1.0000000000 [warm, post → s04 §B, s08 §C]. Over the snapshot interval itself, 1,262.814 s on the controller's monotonic clock: L = 1,697.1073, λ = 6.3857 msg/s, the same W and the same ratio [snap, warm, post → s08 §C]. The ratio does not depend on the interval chosen, which is the point of the next bullet.
- **That is the identity ∫N dt = Σ(departureᵢ − arrivalᵢ)**, which holds for any set of stamps in which each departure follows its arrival. The same computation on fabricated departures — arrival plus a random 0–900 s, or arrival plus 1 ms — also gives 1.0000000000 [s04 §C]. It says nothing about the measurement chain and is used as evidence nowhere here. Round one's "strong internal-consistency proof of the whole measurement chain" is withdrawn.
- **The cross-check that does carry weight** compares two different mechanisms of the controller: the waiting queue reconstructed from the event stamps against the `queue_depth` (`qsize()`, `service.py:171-173`) the harness polled — 721 samples, mean difference +0.110, median 0, maximum |difference| 3, none outside ±3 [warm, post, metrics → s03 §D]. The two share no code path; they are joined through the one end-marker anchor.
- λ = 7.1658 msg/s is the throughput of the busy interval, which includes 405.42 s with no arrivals [s08 §C]. It is not a sustainable rate and is not quoted as one.

---

## 9. What the window inherited from the warm-up

### 9.1 Observed

| Quantity | Value | Source |
|---|---|---|
| Warm-up messages in the controller at el 0 | 750 (749 waiting + 1 in service) | [warm → s05 §A] |
| Warm-up messages acknowledged after el 0 | 751 — the 750, plus one that arrived at el +0.009955 s | [warm → s05 §A] |
| Warm-up messages in the controller when the first measured message arrived (el +0.193468 s) | 749 | [warm, post → s05 §A] |
| Last warm-up acknowledgement | el +126.513075 s | [warm → s05 §A] |
| Consumer time spent on warm-up work after the first measured arrival | 126.319607 s | [warm, post → s05 §A] |
| Warm-up messages among the 3,593 in the controller at the window end | 0 | [warm → s05 §A] |
| Measured messages that arrived before the last warm-up acknowledgement / after it | 1,417 / 5,303 | [warm, post → s08 §A] |
| The 3,593 at the window end, by count | 750 in the controller at el 0 + 6,721 arrivals − 3,878 acknowledgements (751 of them warm-up) | [warm, post → s08 §B] |

For the first 126.3 s after the first measured message arrived, the consumer served only warm-up messages (FIFO, no interleaving, never idle — section 4.1). That time is part of the wait of the **1,417** measured messages that arrived before the last warm-up acknowledgement; the waits of the other **5,303** contain no warm-up service time at all, and any effect of the warm-up on them is the propagated shift of section 9.2, which is not established. Likewise, that none of the 3,593 in the controller at the window end was a warm-up message follows from FIFO order, but by count the 3,593 include the 750 carried over at el 0, and 751 of the window's 3,878 acknowledgements served warm-up messages; how much the warm-up backlog added to the end-of-window count is the same counterfactual, and is not established. Excluding the warm-up rows from an analysis does not remove that backlog from the running system (project manager's record `PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 2.3). The three round-one counts 749, 750 and 751 are all correct; they count at three different instants, which are now named.

### 9.2 The counterfactual is dropped

"What would latency and on-time delivery have been from an empty start?" needs a model of how long each measured message would have taken had it been served earlier. Two replays of the **same observed durations**, differing only in what a duration is attached to, give:

| Replay — **not a finding** | shift of each acknowledgement | on time by the deadline | still late |
|---|---|---:|---:|
| R-msg: each measured message keeps its own observed occupancy (the verification report's replay) | 126.3196 s, uniform | 4,776 (+982) | 1,944 |
| R-slot: the server keeps the durations of its observed service slots after el 0, in order, the first slot measured from el 0 (round one's replay) | 101.159 s mean, 67.063–140.303 s | 4,543 (+749) | 2,177 |

[warm, post → s05 §B]. Both reproduce to the digit. The verification report's claim that its values are exact "and not a matter of modelling choice" holds only under R-msg; round one's values hold under R-slot. **The run's own data argue that neither assumption is safe**: messages of the same device mix took 168.58 ms on average while served in el 0–126 and 151.44 ms afterwards (section 5), and the service rate moved with time and with ingress (sections 3.1, 7.1). So neither "a message carries its own cost" nor "the server's speed is a fixed function of its slot" is established, and the shift cannot be derived exactly. **No counterfactual figure is kept, none enters any conclusion, and this document does not assert what an empty start would have produced.** (Both replays happen to leave more than 1,900 identities late; that is a property of two assumptions, not of the run.) The 120 s warm-up is part of the frozen protocol and is not changed or judged here.

---

## 10. What I could not establish

1. **A capacity, a steady service rate or a maximum throughput** for this stack on this guest. None exists in this run (section 3.1).
2. **How one passage divides** between controller computation, the Ditto `PATCH`, event-log I/O and scheduling delay (sections 4.2, 6.2).
3. **How the Ditto round trip divides** between its services and MongoDB.
4. **What moved the service rate** — warm-up, ingress contention or the harness's activity in the guest (section 7.2).
5. **Which way the CPU–acknowledgement association runs** (section 6.3).
6. **Anything about the guest outside the six containers, or about the host.**
7. **Resource use during the drain** — one instant exists.
8. **Whether more consumer concurrency would raise the served rate** (section 7.2).
9. **What an empty start would have produced** (section 9.2).
10. **How the 10,000-message cap behaves when reached** — it was never exercised.
11. **Why 736 publish records carry no PUBACK** — the run directory has no broker-side evidence. No population here depends on it.
12. **What the controller logged** — no controller container log is preserved in the run directory (`logs/` holds simulator, warm-up and collector output only).
13. **The native equivalent of any figure.**

---

## 11. The one bounded measurement proposed next

### 11.1 The question

> **Does the same candidate keep its controller queue bounded when offered, with the same device mix, a rate below every served rate `nominal-r01` showed — and how long is one message's passage when nothing waits ahead of it?**

It tests the account of section 7 where that account makes a prediction, under one assumption the run cannot check: that at 2.24 msg/s the consumer's service rate is no lower than the rates it showed while saturated in `nominal-r01`. Under that assumption a load below every rate the run served should not build a queue. A queue that grew anyway would not revise the 11.2 msg/s deficit of `nominal-r01`, which is arithmetic on that run's stamps (section 3); it would show a service rate that depends on the load or on time in a way section 7 does not capture. It also makes the passage directly observable — impossible in `nominal-r01`, where every measured message waited at least 126 s. It changes no code, no configuration, no limit and no concurrency, and it is not a repeat of the failed condition (`PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 5, item 4).

### 11.2 Sizing, against the lowest rate the run showed

| | Value | Source |
|---|---|---|
| **Lowest 60 s served rate of `nominal-r01`** | **4.6000 msg/s** (event log; counters 4.6009), el −120 … −60 — the first minute of load, first-contact seeding included | [warm, post, metrics → s02 §D, s07 §A] |
| Lowest 30 s and 10 s rates | 3.8333 and 3.0000 msg/s, in the same first minute | [warm, post → s07 §A] |
| Lowest inside the window | 5.3167 (60 s), 5.1000 (30 s), 3.9000 (10 s) msg/s | [warm, post → s07 §A] |
| **Offered rate proposed** | **2.24 msg/s** — one fifth of 11.2; the simulator's 1 : 0.2 : 10 split gives `smartwatch` 0.2 Hz, `smart_ring` 0.04 Hz, `smart_clothing` 2.0 Hz | [s07 §B]; `src/egw_simulator/cli.py:79-87` |
| Ratio to the lowest 60 / 30 / 10 s rate | 0.487 / 0.584 / 0.747 | [s07 §B] |
| Publication | 720 s — the same loaded time as `nominal-r01` (120 s + 600 s): about 1,613 messages (1,440 + 144 + 28.8) | [s07 §B] |
| Service needed at the lowest 60 s rate | 350.6 s for all of them, inside the 720 s | [s07 §B] |
| Deliberately **not** used for sizing | the window average 6.457048 msg/s and the drain rate 8.863682 msg/s | [s02 §C] |

The offered rate sits below the lowest rate the run served at every block width from 10 s to 60 s; at 1 s resolution the run served nothing in 12 of the 600 in-window seconds [s02 §D], so no rate can be sized at that width.

### 11.3 Procedure and finite duration

- **One run**, under a fresh diagnostic run id and seed, outside the campaign plan — the plan's 95 runs use no offered rate below 10 msg/s [`~/egw-tcg/pilot/campaign_plan.json` → s07 §B] — on the same controller code (`src/egw_controller/` unchanged since `fe954a9`), with the image identities recorded.
- **Through the existing ad-hoc path** used for the 1 Hz slice of 2026-09-19: `run_test <id> <seed> --scenario load-sweep --rate 2.24 --duration 720` (`~/egw-tcg/itest-helpers.sh`, `run_test` → `pre`, `sim_post`). `load-sweep` here is the simulator's scenario — the nominal device profile at an operator-chosen rate (`src/egw_simulator/scenarios.py`) — not the campaign's `load_sweep` condition. The path runs the `drained` precondition, the simulator, the controller marker, the fetch and the reconciliation by identity, and collects `sent_events.jsonl` and `events.jsonl`: that is all the primary readouts need, through the exact reconstruction of section 4, which agreed with the sampled depth within ±3 in `nominal-r01`.
- The unchanged 60 s confirmation window after the controller marker.
- **Collection instant.** On this path the event log is fetched once, by `finish`, after `wait` and `drained` have run (`~/egw-tcg/itest-helpers.sh:193-196`): that single copy is a post-drain collection, not a fetch at the deadline. Confirmed on time and confirmed late are therefore separated by comparing each acknowledgement stamp with the deadline (controller end marker + 60 s, both on the controller's monotonic clock), as in section 2, and "no outcome" means no outcome after the drain.
- **Duration.** Expected guest time about **17.5 min**: 133 s of precondition, as observed in the nominal attempt [cmds → s07 §C], + 720 s + 60 s + about 135 s of quiet window after the run. About 23.5 min if `DRAIN_QUIET_S=490` is exported after the run, as the runbook advises when a `MISMATCH` must be excluded as a timing artefact (`docs/setup/qemu_integrated_gateway.md:651`, `:1004`). **Planning ceiling 46.0 min, not a bound**: each `drained` stops with `STOP` at `DRAIN_LIMIT_S` = 900 s (`:653-654`); `wait` gives up only after the 60 s window plus its default `--extra-timeout` of 120 s (`src/egw_experiments/itest_reconcile.py:235`, `:604`); `pre` first waits up to 60 s for `/ready` (`itest-helpers.sh:179`): 60 + 900 + 720 + 180 + 900 = 2,760 s [s07 §C]. The figure still excludes the fetch, the snapshots and `accounted`, and `drained` checks its limit only between readings, each of which may take up to 30 s (`itest-helpers.sh:30`).

### 11.4 Prediction, refutation, readouts

**Prediction from section 7.1, under the assumption stated in section 11.1:** over the 720 s the reconstructed number in the controller returns to 0 repeatedly and shows no sustained growth, and every identity is confirmed within the deadline.

**Refuted if either:**

- **sustained growth**: the reconstructed number in the controller does not return to 0 at any instant of the last 120 s of publication — a queue that no longer empties. The criterion is judged over minutes of the probe's own record, not on two instants against the ±3 agreement of section 8: that band measures agreement between two instruments, not how much the queue fluctuates, and in `nominal-r01` 17 measured passages lasted longer than 1.339 s, the time in which three messages arrive on average at 2.24 msg/s [warm, post → s07 §C], so one slow passage at the end of publication could breach a ±3 band without any sustained shortfall; or
- any identity is confirmed after the deadline (acknowledgement stamp later than the controller end marker + 60 s), or has no outcome in the copy fetched after the drain (section 11.3).

Either result would mean that, at a load below every rate this candidate served in `nominal-r01`, its service rate fell below the rates it showed while saturated — a service rate that depends on the load or on time, which section 7 does not capture. It would not revise the 11.2 msg/s deficit of `nominal-r01`, which is arithmetic on that run's stamps. The result is recorded as a negative result with the attempt preserved, and reported to the student for the throughput decision.

**Inconclusive if** the procedure stops (a `STOP` from any helper, a missing controller marker): the attempt is kept as incomplete and no figure is reported from it.

**Readouts reported whatever the verdict, deciding nothing on their own:** the latency of the messages that found the controller empty (zero wait in the reconstruction) — the passage with no queue wait; its trend across the 720 s, since a drift at constant low load would point to a time-dependent effect independent of the ingress rate; and the occupancy of back-to-back messages, for comparison with section 5.

**What a positive result would mean, and no more:** that at 2.24 msg/s for 720 s the queue stayed bounded on this candidate. Nothing about any other rate, no capacity figure, no maximum throughput, nothing native; the `nominal-r01` verdict stands unchanged.

### 11.5 What it does not do, and where it sits

- It does not change the nominal condition (11.2 msg/s, 600 s, 120 s warm-up, 60 s window) or any threshold, deadline, rule or gate criterion, and it does not relabel `nominal-r01`.
- It is **not a G3 qualifying run.** The student's decision, recorded on a branch, not yet on `dev` — in `PROGRESS.md` (`:180`) and in `LOG.md` entry #C039 at commit `3549d46` on the branch `docs/g3-pause-answer`, which is not an ancestor of `35fe8bb` [s09] — keeps the G3 qualifying runs paused until the candidate is frozen after package D, while bounded engineering diagnostics continue.
- It introduces no concurrency, no resource-limit change and no code change.
- **Package D now proposes four guest sessions**, each an engineering diagnostic and none a G3 run:
  1. this measurement, option T3 of the ADR's throughput decision (2.24 msg/s for 720 s on today's code; its question in 11.1, its planning ceiling in 11.3, its refutation and inconclusive cases in 11.4);
  2. the broker-only measurement of ADR 0011 ("The broker measurement (condition C3)"), designed in `gates/item1_broker_limits.md`, section 7, which states its question, refuting results, inconclusive cases and a ceiling set by stop rules;
  3. the finite proof of ADR 0011 (`adr-0011-controller-restart-recovery.md`, "The finite proof": 11.2 msg/s for 300 s, a SIGKILL of the controller at t+150 s, no timing in any criterion);
  4. the proof's optional extension, one more controller restart and one more `drained` at the end of the proof, with nothing published (`gates/item4_drained.md`, section 9, which states its question, refuting result, inconclusive cases and ceiling).
- Neither this measurement's design nor the proof's depends on the other's result: the proof is not sized on any served rate, so this measurement need not precede it. The broker measurement needs no controller change. The proof can run only after the broker measurement has supported option 5 (condition C3), and after the recovery change and its regression tests are merged and the candidate is built; the extension, if the student adds it, runs at the end of the proof. Whether this measurement runs at all, and whether before the recovery decision, is the student's call under option T3 of the ADR's throughput decision.
- **What the ad-hoc path does not provide by default:** the 1 Hz `/metrics` series and the guest resource series that the harness records for plan runs. Without them the run answers its question from the event log alone and adds nothing about resources. Whether to add them — the collector's start, stop and fetch commands already exist in `harness_run` — is the executor's choice; I could not establish whether the ad-hoc path can run them without change.

---

## 12. Corrections applied

### 12.1 Round one

| Finding (report, item) | Round one | Here |
|---|---|---|
| Populations mixed (PM instruction; figures C4) | "2,926 lost means 2,926 late", with deadline and post-drain counts side by side | Three populations with counts and collection instants (section 2); the deadline verdict stays 3,794 / 2,926 |
| Latency percentiles (figures C4) | 320.27 / 402.70 / 405.47 s as the run's | 264.430 / 321.070 / 323.248 s over P1 at the fetch; post-drain rows labelled (section 2) |
| "2,926 by a different route" (figures A3) | independent corroboration | same predicate, not independent (section 2, rule 3) |
| Warm-up counterfactual (figures §1.6) | 204.016 s, 101.159 s, +749, 2,177 as findings; the verification's replacement 178.855 s, 126.32 s, +982, 1,944 called exact | both reproduce under different replay assumptions; not derivable exactly; **dropped** (section 9.2) |
| 749 / 750 / 751 (figures §1.3, §1.6) | contradictory counts | three counts at three named instants (section 9.1) |
| Per-message budget (figures B1) | 154.77 ms "of the measured window" | 151.44 ms over the 3,127 measured messages served with ingress running; D's 19.4 % warm-up share stated; what it is and is not (section 5) |
| Throughput = 1 ÷ budget (figures A2; constraints B13) | "exactly, which is what was observed" | an identity; 6.4616 against 6.457048 (section 5) |
| Little's law (figures A1) | "strong internal-consistency proof" | identity, shown on fabricated stamps; the real cross-check is the ±3 reconstruction (section 8) |
| Growth closure (figures C5) | 2,838 vs 2,838, "exact" | 2,837.65 vs 2,838 sampled; 2,843 reconstructed; 0.2 % (section 3.2) |
| Wait share (figures §1.4) | 99.9572 % by approximation | 99.9571 % of summed latency by the exact split (section 4.2) |
| Off-CPU time (figures B2) | "≥ 97.93 ms is the Ditto HTTP round trip" | ≥ 63.30 % of busy time off the controller's CPU, not divisible (section 6.2) |
| "130 ms for one PATCH"; "emulation is the multiplier" (figures B3; constraints B2) | stated | withdrawn (section 6.2) |
| "No amount of tuning closes 1.73" (constraints B8) | stated | withdrawn (section 3.3) |
| "Nothing was saturated" (figures B4; constraints 4(g)) | heading and summary | withdrawn; what the six containers' samples can and cannot show (section 6.1; see 12.2) |
| Highest median CPU (figures §1.5) | 63 %, `ditto-things` | 62.06 % in window; 65.98 % over all instants (section 6.1) |
| CPU bands and r (figures §1.5) | 8.005 → 3.800, r −0.6126 | re-derived by two stated methods; association only (section 6.3) |
| Offered "per 60 s block to four decimals" (figures C3) | stated | 671–672 per block, 11.1833–11.2000 msg/s (section 3.1) |
| "Monotone climb", "61 %", "33 % below eventual" (figures §1.7) | stated | block series shown; phrases dropped (section 3.1) |
| Drain uplift as "the cost of receiving" | 1.80 × | adjacent-block comparison; confounded (section 7.2) |
| Drain rate definition (figures §1.2) | unstated | definition stated (section 3.1) |
| Probe sized on the average (figures B5) | 5.0 msg/s against 6.457 | 2.24 msg/s against the lowest block, 4.60 msg/s (section 11.2) |
| Probe timing (figures §1.9) | 180 s precondition, 13 min | observed 133 s; 17.5 / 23.5 min expected; a 46.0 min planning ceiling, not a bound (section 11.3; see 12.2) |
| Total of guest runs (constraints 4(c)) | not stated | two until the gate answers; four sessions since, each an engineering diagnostic and none a G3 run; this probe and the proof do not depend on each other, and whether and when the probe runs is the student's call (section 11.5; see 12.2) |
| Date on an act; unnamed authority (constraints B11, 4(f)) | "clearance of 2026-09-20" | records named by file (sections 3.3, 9.1, 11) |
| Folder name naming a tool (constraints B12) | in the Method line | "project-management folder" |
| Reproduction (constraints 4(a), 4(b)) | relative command; analyses unlocated | self-locating runner; round-one files located (section 13) |
| Restart counterfactual (the 3,593 "would have been in that second class" had the process been killed) | stated | removed; only the observed count and the source reading of where they were held remain (section 3.3); the restart runs' partition belongs to the ADR and remains assumption-dependent |

### 12.2 Round two

Findings of `verify_figures.md` (section 5) and `verify_constraints.md` (section 3) that concern this document.

| Finding | Round two | Here |
|---|---|---|
| X1; F16 — the order of the two runs rested on the superseded ADR draft, and the probe was made a precondition of the recovery decision | "this one comes first … that sizing has to be redone" | neither run depends on the other; whether and when the probe runs is the student's call under ADR 0011's T3 (sections 1, 11.4, 11.5) |
| R-D1 — "every measured message's wait includes that time"; "none of the 3,593 was a warm-up message" read as bearing on the count | stated for all 6,720; identity used for a count | 1,417 of 6,720 waited while warm-up messages were served; 3,593 = 750 + 6,721 − 3,878; the warm-up's bearing is the counterfactual of 9.2 (sections 7.1, 9.1) |
| R-D4 — the probe's prediction, band and collection instant | unstated assumption; "not explained by the deficit alone"; ±3 band on two instants; "no outcome at the fetch" | assumption stated (11.1); a refutation shows a load- or time-dependent service rate, not a revised deficit; sustained growth judged over the last 120 s (17 passages > 1.339 s); collection instant named and late read from the stamps (11.3, 11.4) |
| R-D2 — Little's law interval | L, λ labelled with the snapshot interval but computed over another | both intervals named, with both sets of values (section 8) |
| R-D3 — an identity presented as the cause | "Why … one strictly serial consumer" | occupancy stated as an identity; its content and its dependence on seriality not established (sections 1, 7.1) |
| R-D5 — plan rate | "to four decimal places" | three (section 3.1) |
| R-D6 — method C | guest instants read as harness wall | mapped through the marker offset: 7.904 … 3.791, r −0.6337 (section 6.3) |
| R-D7 — drain range | "7.90–9.53 until the backlog cleared" | 7.90–9.53 in the full blocks, 10.29 in the last partial block (section 7.1) |
| R-D8 — probe duration | "hard bound 43.0 min" | planning ceiling 46.0 min, not a bound, with what it excludes (section 11.3) |
| R-D9 — R-slot convention | unstated | first slot measured from el 0 (section 9.2) |
| R-D10 (a)–(f); F17 — provenance | platform file of an earlier capture; 220.19 CPU-s "in 600.107 s"; "none taken from round one"; guest-clock instants unlabelled; code at `3549d46`; pause record not said to be off `dev`; "no CPU saturation observed"; "decided in the recovery ADR draft" | each corrected in place (header, sections 0, 2, 6.1, 6.2, 8, 11.5) |
| Reasoning table, "≥ 63.30 % off-CPU" | list read as exhaustive | "the list is not exhaustive" (section 6.2) |

---

## 13. Reproduction

The scripts are in `scripts/` beside this document and their outputs in `out/`. From WSL:

```
wsl -d Ubuntu-24.04 --exec bash -lc 'bash "<directory of this document>/scripts/run_all.sh"'
```

`run_all.sh` locates its own directory, runs the eight Python scripts below with `~/egw-exec/venv/bin/python`, and writes only `out/<script>.out.txt`. `s09_code_identity.sh` runs from Git Bash against the Windows worktree of the repository, which it locates relative to itself (or from `EGW_WORKTREE`): `bash "<directory of this document>/scripts/s09_code_identity.sh" > "<directory of this document>/out/s09_code_identity.out.txt"`. The scripts use the standard library and read-only git commands only, open every source read-only, start no guest and contact no network.

| Script | Produces |
|---|---|
| `common.py` | loaders, the clock anchors, the harness's percentile convention |
| `s01_populations.py` | deadline, populations at both collection points, collection instants, latency by population |
| `s02_rates_and_queue.py` | offered, arrival and served rates; 60, 30 and 10 s blocks; queue facts; the window end and the drain |
| `s03_wait_and_budget.py` | FIFO, non-interleaving and continuous-busy checks; the exact wait/own split; the budget by population; the reconstruction cross-check |
| `s04_little_identity.py` | Little's law over the empty-to-empty interval, and on fabricated stamps |
| `s05_warmup_inheritance.py` | the warm-up counts at named instants, and the two replays |
| `s06_resources.py` | the resource tables, the controller CPU fraction, the CPU association, the guest state after the run |
| `s07_probe_sizing.py` | the lowest block rates, the sizing arithmetic of section 11, the passages behind its refutation criterion and its planning ceiling |
| `s08_corrections.py` | the round-three figures: the 1,417 / 5,303 split, the 3,593 decomposition, Little's law over both intervals, the drain's last partial block, the platform file's capture instant |
| `s09_code_identity.sh` | code identity at `35fe8bb`, the repository anchors cited here, the absence of CPU limits, the pause record's commit and branch |

The round-one analyses (`queue_anatomy.md`, `where_time_goes.md`, `controller_today.md`, `restart_evidence.md`), the round-one drafts and the two round-one verification reports are in the parent directory of this one, with their scripts under `../scripts/`; the two round-two reports are beside this document, with their scripts under `scripts/verify/` and `scripts/verify_constraints/`. This document takes no figure from any of them. Both directories are working directories of this analysis and will not persist on their own: they must travel with this document.

---

**This is a corrected draft for review. It closes no gate, admits no claim, accepts no result, and changes no threshold, deadline, offered load or rule. `nominal-r01` remains a valid run that failed its delivery criterion.**
