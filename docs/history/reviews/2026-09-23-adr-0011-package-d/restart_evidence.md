# What the two controller-restart runs prove, and what we only assumed

- **Date:** 2026-09-20
- **Package:** D of the project-management work order — controller backlog and recovery decision, from existing data only.
- **Method:** read-only re-derivation from the preserved artefacts. No guest was contacted, no run was repeated, nothing was measured live, no repository or run directory was modified. Every figure below was produced by a script left under `scripts/`, run with `~/egw-exec/venv/bin/python`; the raw outputs are under `out/`.
- **Status vocabulary, used on every claim:**
  - **PROVED** — a preserved artefact line states it, or it follows from artefact lines by arithmetic alone;
  - **CONSISTENT-WITH** — the artefacts do not contradict it and at least one observation points that way, but an alternative is not excluded;
  - **ASSUMED** — it rests on source code, on a library default, or on a mechanism that no preserved artefact records.

Both runs are **invalid** and **unsealed**. Nothing here is campaign evidence, nothing here is a performance result, and every duration is from an ARM64 guest emulated under QEMU/TCG.

---

## 1. Summary answer

**What the two runs prove.** A `docker compose restart` of the controller destroyed a large in-memory backlog and left a subscription outage of tens of seconds, and both are visible by identity, not by inference. In `controller_restart-r02`, 2,136 published identities never obtained an outcome, in one contiguous block of the publication order, and the counters show the process it belonged to disappearing with 1,867 messages in its queue. The arithmetic closes exactly: 1,809 messages still queued when the process stopped, plus one unaccounted message, equal the 1,810 identities that were provably inside the controller and never came out. `controller_restart-r01` reproduces the same signature with different numbers.

**What we only assumed.** The split of the remaining 326 identities — "received and then discarded" versus "published with no subscriber" — is **not** derivable from the artefacts. It turns on the instant the old process's MQTT client disconnected, and that instant is recorded nowhere: no broker connection log, no `docker events`, no container log, no exit code. The earlier diagnosis's 1,810 / 195 / 131 is one point on a continuum. Moving the assumed boundary by one second moves about eleven identities between the two classes.

**A correction to the earlier diagnosis.** Its PUBACK argument does not hold. In `controller_restart-r02`, 421 identities that the controller demonstrably processed carry a null `puback_monotonic_ns`, because the simulator's PUBACK capture is best-effort within a wait budget. A missing PUBACK is therefore a simulator recording miss, never evidence of non-delivery.

**A second correction.** The earlier diagnosis placed the class boundary at the death of the process (about 00:18:30Z). The artefacts place the *HTTP* shutdown about ten seconds earlier, at about 00:18:19.99Z, while outcomes kept being written — that is a graceful shutdown path running, and in that path the MQTT bridge is stopped before the queue is drained. On that reading almost the whole 326 was never delivered, and the honest statement is a bound, not a triple.

---

## 2. What the artefacts say about the restart itself

### 2.1 `controller_restart-r02`, 2026-09-19 (all instants UTC)

| Instant | Event | Artefact | Status |
|---|---|---|---|
| 00:13:15.344 | measured window opens | `manifest.json` `measured_window_utc.start` | PROVED |
| 00:18:15.344 | `docker compose … restart controller` issued over SSH, at the planned t+300 s | `manifest.json` `restart.started_utc`, `restart.requested_at_s` = 300.0 | PROVED |
| 00:18:19.443 | last successful `GET /metrics` of the old process: `accepted` 1872, `queue_depth` 1867 | `controller_metrics.csv:307` | PROVED |
| ~00:18:19.99 | HTTP stops answering: a 29.115 s gap opens in the 1 Hz poll series, last error `Remote end closed connection without response` | `controller_metrics.csv:307`→`:308`; `manifest.json` `controller_metrics.poll_errors` = 26, `samples_written` = 573 over a 600 s window, so this single gap accounts for essentially all the failed polls | PROVED that the server stopped answering between 00:18:19.443 and the next poll about a second later; CONSISTENT-WITH the ASGI shutdown starting there |
| 00:18:29.990 | last Ditto acknowledgement written by the old process (`smart_clothing` seq 1421) — the last proof the process was alive | `events.jsonl:1594` | PROVED |
| 00:18:29 → 00:18:35 | `egw-controller-1` absent from the resource collector; `mem_bytes` 58,122,240 → 3,592,192 | `logs/collector/resources-controller_restart-r02.csv` | PROVED (the container was not reported for 5 sample slots) |
| 00:18:36.134 | restart command returns, `returncode` 0, stderr `Container egw-controller-1 Restarting / Started` | `manifest.json` `restart` | PROVED |
| 00:18:48.504 | first message handled by the new process (`smartwatch` seq 333) | `events.jsonl:1595` | PROVED |
| 00:18:48.558 | first `GET /metrics` of the new process: `accepted` 0, `queue_depth` 0 | `controller_metrics.csv:308` | PROVED |
| 00:23:14.595 | final poll: `accepted` 1719, `queue_depth` 1261 | `controller_metrics.csv:574` | PROVED |

The old process survived **14.646 s** after the restart command was issued, and wrote **80** outcomes in that interval (`events.jsonl:1515`–`1594`). Source: `scripts/restart_partition.py`, `out/partition_r02.txt`.

**The MQTT subscription was down for at least 13.5 s.** That is the interval from the death bracket's upper bound (00:18:35.000, the latest instant at which the old process could still have been delivering) to the new process's first delivery (00:18:48.504). PROVED. The upper bound depends on when the bridge stopped, which is not recorded: **29.1 s** if it stopped when the HTTP server did (CONSISTENT-WITH the code order, in which uvicorn shuts the HTTP server before the lifespan `finally` calls `bridge.stop()`), and at most **33.2 s** measured from the restart command at 00:18:15.344.

### 2.2 The death instant is bracketed, not pinned

- Lower bound **00:18:29.990Z** — the last Ditto acknowledgement of the old process (`events.jsonl:1594`, controller clock). PROVED.
- Upper bound **00:18:35.000Z** — the first collector sample showing a container with 3.59 MB resident where the old one held 58.12 MB. PROVED.
- Width **5.010 s**. The collector sampled `egw-controller-1` at **0.83 samples/s**, not the 1 Hz the protocol assumes, so a missing sample does not pin the instant to the second. PROVED (`out/context.txt`).

Inside that bracket **56** identities were published (`smart_clothing` 3145–3194, `smart_ring` 63, `smartwatch` 315–319). Source: `scripts/restart_partition2.py`.

**Why ten seconds of survival, and what the manifest does not say.** `src/deployment/compose.yaml` sets no `stop_grace_period` for the controller and `src/Dockerfile` sets no `STOPSIGNAL`, so Docker's default applies: SIGTERM, then SIGKILL ten seconds later. The HTTP server stopped answering at about 00:18:19.99 and the last acknowledgement was written at 00:18:29.990 — exactly ten seconds later. That fit is **CONSISTENT-WITH** a SIGTERM at 00:18:19.99 and a SIGKILL at 00:18:29.99. It is **ASSUMED**, not proved: no exit code, no `docker events` record and no container log are preserved, so SIGKILL itself is not in evidence.

### 2.3 `controller_restart-r01`, 2026-09-18: the same signature

| Quantity | r01 | r02 |
|---|---:|---:|
| restart command issued | 21:55:22.583 | 00:18:15.344 |
| last successful poll of the old process | 21:55:27.661 | 00:18:19.443 |
| `queue_depth` at that poll | 1,487 | 1,867 |
| last Ditto acknowledgement of the old process | 21:55:38.489 | 00:18:29.990 |
| old-process survival after the command | 15.906 s | 14.646 s |
| death bracket width | 4.511 s | 5.010 s |
| first delivery to the new process | 21:55:59.421 | 00:18:48.504 |
| internal block of lost identities | 1,760 | 2,136 |
| collector cadence for `egw-controller-1` | 0.23 samples/s | 0.83 samples/s |

Source: `out/derive_r01.txt`, `out/derive_r02.txt`, `out/partition2_r01.txt`, `out/partition2_r02.txt`. All PROVED.

`controller_restart-r01`'s resource evidence around the restart is much weaker: at 0.23 samples/s its 9.0 s controller gap spans only two sample slots.

### 2.4 What the counters did across the restart

- The cumulative `accepted` counter falls **exactly once** in each run: 1872 → 0 at `controller_metrics.csv:308` (r02) and 7909 → 0 at `:309` (r01). A cumulative counter cannot fall inside one `MetricsCounters` instance, so this is a **new process**. PROVED (`out/checks.txt`).
- `rejected`, `duplicate`, `failed` and `dropped` did not move within either measured window (r02: all zero throughout; r01: constant at 67 and 672 before the restart, zero after). PROVED. In particular **`dropped` stayed at zero**: the 10,000-slot inbound queue never overflowed, so no identity was lost to queue capacity.
- `queue_depth` collapsed from 1,867 to 0 (r02) and 1,487 to 5 (r01). Those queued messages have **no outcome and no later arrival**. PROVED.
- The new process rebuilt the same backlog: r02 ended at `queue_depth` 1,261 after 266 s, r01 at 1,046 after 262 s. PROVED.

**Why a backlog exists at all.** The controller completed messages more slowly than the simulator published them, in both processes and both runs:

| | publication rate | old process | new process |
|---|---:|---:|---:|
| r02 | 11.2 msg/s | 5.05 msg/s | 6.46 msg/s |
| r01 | 11.2 msg/s | 6.32 msg/s | 7.23 msg/s |

Source: `scripts/restart_ledger.py`, `out/ledger.txt`. PROVED as observations of this emulated guest; these are **not** performance figures and say nothing about native ARM64 hardware.

At its own observed rate the r02 old process needed about **370 s** to drain the 1,867 messages it held. It had ten seconds.

### 2.5 The event log itself did not lose lines

For each run, the number of `events.jsonl` records acknowledged by the last old-process poll equals the `accepted` counter delta exactly — 1,536 in r02, 1,928 in r01, difference zero. PROVED (`out/partition2_r02.txt`, `out/partition2_r01.txt`). `EventLogger` flushes every line (`src/egw_controller/events.py:112-119`), and a flush survives a process kill because the page cache belongs to the kernel, not the process. The match is the empirical confirmation; the mechanism is ASSUMED.

Consequence: the absence of an outcome record is real absence, not a lost line.

---

## 3. The closed identity ledger

`controller_restart-r02`, from `scripts/restart_ledger.py` (`out/ledger.txt`). Every line is PROVED.

```
published identities (sent_events.jsonl)                     6,720
identities with an outcome (events.jsonl at the fetch)       3,819   all outcome='accepted'
  arrived before the restart gap                             1,594
  arrived after  the restart gap (new process)               2,225
identities with no outcome at the fetch                      2,901
  internal block, contiguous, sent_events.jsonl:1595-3730    2,136
  end-of-run block, contiguous, sent_events.jsonl:5956-6720    765
```

The old process closes exactly:

```
published by 00:18:19.443Z                                   3,404
  accepted within the window at that poll (counter delta)    1,536   = events.jsonl records acked by then
  queue_depth at that poll                                   1,867
  accepted + queue_depth                                     3,403   residual vs published = 1
  drained after that poll, before the process stopped           58
  => still queued when the process stopped                   1,809
  => + the residual                                          1,810   = the block members published by that poll
  pre-gap outcomes (1,594) + 1,810                           3,404   exact
```

`controller_restart-r01` closes the same way: 3,416 published by the last poll, 1,928 accepted, 1,487 queued, residual 1, 83 drained afterwards, 1,404 still queued, **1,405** with no outcome.

**The 765 end-of-run block is not established loss.** It is unresolved *at the fetch*. No post-drain second fetch exists for either restart run. In the sealed nominal run, where that second fetch does exist, 2,841 identities unresolved at the fetch turned out to be **0 lost and 2,926 late** (`analysis/accounting.json`: `events_records_at_fetch` 3,879, `events_records_after_drain` 6,720). PROVED for nominal; for the restart runs the tail block's fate is **"I could not establish"**.

---

## 4. The three-part attribution, re-derived

The earlier diagnosis of 2026-09-19 gave **1,810 received and discarded, 195 published with no subscriber, 131 undetermined**. The first figure reproduces exactly. The second and third do not survive as figures.

### 4.1 Part A — received and then discarded from the volatile queue: **1,810** (r02), **1,405** (r01)

- **Figures.** 1,810 block members published at or before 00:18:19.443Z: `smart_clothing` 1422–3038 (1,617), `smart_ring` 29–60 (32), `smartwatch` 143–303 (161).
- **Artefact lines.** `sent_events.jsonl:1595`–`3404`; `controller_metrics.csv:307` (`accepted` 1872, `queue_depth` 1867, everything else 0); `controller_metrics.csv:2` for the pre-window baseline `accepted` 336; `events.jsonl:1`–`1594` for the 1,594 identities that did obtain an outcome.
- **What is PROVED.** 3,404 identities had been published by that poll; 3,403 were accounted for inside the controller (1,536 accepted plus 1,867 queued); therefore **at least 3,403 of them had been received**. 1,594 of the 3,404 have outcomes and 1,810 do not, and 1,594 + 1,810 = 3,404 exactly. After the poll, 58 more outcomes were written, so 1,809 were still in the queue when the process stopped.
- **The assumption that turns the figures into the cause.** Two, both small:
  1. **ASSUMED** — that the one residual identity was inside the process (in flight to Ditto, or received microseconds after the snapshot) rather than still in the broker. The counter set written to the CSV cannot tell these apart, because `received`, `in_progress` and `processing_errors` are not among its columns. The defensible figure is therefore **1,809 proved, 1,810 with one identity assigned by elimination**.
  2. **ASSUMED** — that "still in an `asyncio.Queue` when the process ended" means "discarded". This follows from the queue being process memory (`src/egw_controller/service.py:150-151`, maxsize 10,000) and is not in doubt, but it is a source reading, not an artefact line.
- **What a future run would need to make it proof.** The sampler must write the fields that `GET /metrics` already returns and the CSV already throws away: `received`, `in_progress`, `processing_errors`, `started_at` and `uptime_s`. The controller exposed all five at the deployed commit `8e88670` (`src/egw_controller/metrics.py` `snapshot()`, `src/egw_controller/app.py:120-127`), and **the harness at the merged head `ccd5fd6` still writes only the seven columns** (`src/egw_experiments/controller_metrics.py:64`). With `received` in the CSV the residual closes by arithmetic; with `started_at` the process identity — and therefore the restart instant — is pinned to the sampling interval instead of being inferred from a counter falling.

### 4.2 Parts B and C — the 326 published across the outage (r02); 355 (r01)

The remaining block members split, on cuts that each sit on one artefact line:

| Group | r02 | r01 | Definition |
|---|---:|---:|---|
| G2 | 119 | 122 | published after the last successful poll and at or before the old process's last Ditto acknowledgement |
| G3a | 56 | 51 | published inside the death bracket |
| G3b | 151 | 182 | published after the death bracket, while the container was certainly new and not yet subscribed |
| **total** | **326** | **355** | |

Source: `scripts/restart_partition2.py`, `out/partition2_r02.txt`, `out/partition2_r01.txt`. The group sizes are PROVED; the *labels* are not.

- **What is PROVED for all 326.** None of them obtained an outcome, and none was redelivered after the controller came back. The `duplicate` counter of the new process stayed at zero for the whole post-restart period and the outcome histogram is `{'accepted': 3819}` with no other outcome present. So **the broker held nothing for this client while it was down and delivered nothing on reconnection**. That is a direct observation, not a deduction from the clean-session default.
- **What is PROVED for G3b (151 in r02).** They were published after the collector had already seen a fresh 3.59 MB process under the container name, and before that process took its first message at 00:18:48.504Z. Nothing could have received them. Subject to the clock caveat in section 6.
- **What is ASSUMED for G2 and G3a (175 in r02).** Whether the old process's MQTT client was still subscribed when they were published. The relevant code order is `bridge.stop()` and only then `service.stop()` (`src/egw_controller/app.py:160-161`), so the subscription goes down at the start of the shutdown, about ten seconds before the process dies. If that is what happened, G2 and G3a were never delivered. If instead the client stayed attached until the kill, up to 175 more identities were received and discarded.
- **The only observation that bears on it, and how weak it is.** The broker's CPU share drops while the controller is away: `egw-mosquitto-1` median 2.70 % in the 60 s before the last old-process poll, 1.76 % across the outage, 2.82 % in the 60 s after the new process's first poll (`out/context.txt`). A shift of under one percentage point, in a `docker stats` series sampled at 0.84 samples/s, is **CONSISTENT-WITH** the subscriber going away early but pins no instant.
- **Bounds, which is the honest form of the answer.**
  - received and then discarded: **at least 1,809, at most 1,985**;
  - published and never delivered: **at least 151, at most 327**;
  - and the mechanism reading above puts them at 1,810 and 326.
- **What a future run would need to make it proof.** One of these, all cheap and none of them preserved today:
  1. **Broker connection logging.** `log_type all` (or at minimum the connection notices) on `egw-mosquitto-1`, with the broker log fetched into the run directory. Mosquitto logs the client disconnect with its client id `egw-controller-egw-01` and a timestamp; that single line converts the whole question into arithmetic.
  2. **`docker events --since/--until` for the controller container**, fetched into the run directory: `kill` with the signal, `die` with the exit code (137 would prove SIGKILL), `start`. This also pins the death instant that section 2.2 can only bracket.
  3. **The controller's own container log.** `_on_disconnect` logs `MQTT disconnected` at WARNING and `_on_subscribe` logs `MQTT subscription granted; bridge ready` at INFO (`src/egw_controller/mqtt.py:183` and `:152`). Both instants are printed by the running code and both were thrown away: the run directory keeps only `logs/simulator/` and `logs/collector/`.
  4. **A resource collector that actually samples at 1 Hz**, so the container-absence window is five samples wide rather than five slots of a 0.83 samples/s series.

### 4.3 Why 195 / 131 specifically should not be repeated

The earlier note's split corresponds to placing the boundary at about 00:18:31Z. The sensitivity is linear and steep, at roughly eleven identities per second (`out/partition_r02.txt`):

| assumed boundary | received and discarded | undetermined | never delivered |
|---|---:|---:|---:|
| 00:18:25 | 1,810 | 63 | 263 |
| 00:18:27 | 1,810 | 86 | 240 |
| 00:18:29 | 1,810 | 108 | 218 |
| 00:18:30 | 1,810 | 119 | 207 |
| **00:18:31** | **1,810** | **131** | **195** |
| 00:18:33 | 1,810 | 153 | 173 |

The figures 195 and 131 are therefore a *choice of boundary* reported as a measurement. The first column, 1,810, is the only one that does not move.

### 4.4 The PUBACK argument does not support anything

The earlier note cited PUBACKs as corroboration ("PUBACKs are recorded for 172 of the 175 clothing messages"). The simulator's PUBACK capture is explicitly best-effort within a wait budget equal to the free time before the next publish (`src/egw_simulator/publisher.py:160-167`, `:340-362`; records written with a null PUBACK are never revisited, `src/egw_simulator/runner.py:427`). The artefacts show the consequence directly:

| | identities with an outcome | of them, no PUBACK recorded |
|---|---:|---:|
| r02 | 3,819 | **421** |
| r01 | 4,538 | **503** |

Source: `scripts/restart_checks.py`, `out/checks.txt`. PROVED. Four hundred and twenty-one identities that the controller demonstrably processed carry a null PUBACK, so a null PUBACK measures the simulator's wait budget, not delivery. No delivery or non-delivery claim may rest on this field.

---

## 5. What the twins show

**Nothing — no twin state was recorded for either restart run.**

- Neither run directory contains a twin snapshot, and neither historical attempt folder (`~/egw-exec/attempts/_historical/HIST_controller_restart-r01`, `-r02`) has an `analysis/` directory at all: they hold only `attempt.json`, `sources.json`, `commands.jsonl` and `export/receipt.json`. PROVED.
- A search of `~/egw-exec` and `~/egw-tcg` for twin snapshots returns the integration-test set and `nominal-r01` only. PROVED.
- So **I could not establish** what Ditto held before or after either restart, whether any twin's `last_seq` regressed, or whether the twin-backed dedupe cache rebuilt correctly after the restart — which is the mechanism ADR 0006 relies on ("after a restart, the cache is rebuilt by reading the twin").

For contrast, the sealed nominal run does have the snapshots, and they close the account: `smartwatch` `last_seq` 599 with `accepted_count` 720, `smart_ring` 119 / 144, `smart_clothing` 5999 / 7200 (`analysis/snapshots/nominal-r01.twins.after.json`) — 8,064 in total, i.e. the 6,720 of the run plus the 1,344 of the 120 s warm-up. PROVED for nominal.

The one indirect twin-side statement available for the restart runs is negative and useful: since nothing was redelivered after the restart (section 4.2), the twins cannot have received the 2,136 by any later path.

---

## 6. A caveat on cross-clock comparisons

Three clock domains meet in this analysis and the manifest is explicit about what they may be used for.

- `sent_events.jsonl` stamps are the **harness host's** monotonic clock, anchored by `measured_started_monotonic_ns` to `measured_window_utc.start`.
- `events.jsonl` stamps are the **controller process's** monotonic clock, anchored by `controller_marker` (`monotonic_ns` ↔ `wall_utc`, lag 0.023 s, within the 2.0 s tolerance).
- The two CSVs carry wall clocks, the harness host's and the guest's.

`manifest.json` `measured_window_clock` states that the wall clock is used **only** to window samples over windows of 300 s or more, where sub-second NTP error is negligible, and **never** for latency. It follows that a cross-domain comparison at tens of milliseconds — for instance, that the last block member was published at 00:18:48.444Z (harness) and the first post-restart message arrived at 00:18:48.504Z (controller), sixty milliseconds apart — is **beyond the accuracy the protocol claims**. Statements in this document that depend on a sub-second cross-domain alignment are marked CONSISTENT-WITH, not PROVED. Group boundaries separated by seconds or more are unaffected.

One cross-domain fact is worth recording because it makes the rest possible: `received_monotonic_ns` and `ditto_ack_monotonic_ns` never decrease across the restart in either run's `events.jsonl` (0 decreases in file order, `out/checks.txt`). The monotonic clock behind them is the guest kernel's, not the process's, so a single end-of-run `controller_marker` anchors pre-restart events as well as post-restart ones. PROVED as an observation; the kernel-wide `CLOCK_MONOTONIC` behind it is ASSUMED.

---

## 7. Why the harness marked both runs invalid

Not for losing messages. Message loss is not a validity criterion.

Both manifests give the same two reasons (`manifest.json` `validity_reasons`):

1. `no SUT resources: timed runs require the VM-side collector output … CPU/RAM on the SUT are essential for RQ3`;
2. `mandatory artefact(s) missing from the run directory: resources.csv — the run is incomplete for its condition kind, so it is marked invalid and NOT sealed (no SHA256SUMS)`.

The chain, PROVED at every step:

- the collector's own CSV *was* fetched successfully (hook `returncode` 0) and is in `logs/collector/`;
- at ingest it was **rejected** for exceeding `MAX_SAMPLE_GAP_S` = 5 s (`src/egw_experiments/analyze.py`, `protocol.py`);
- `resource_source` therefore became `none`, which is the first reason;
- `resources.csv` was consequently never written into the run directory, which is the second reason and also withholds `SHA256SUMS` — both directories are unsealed, whereas `nominal-r01` carries its `SHA256SUMS`.
- The `controller_restart` gate itself **passed**: the restart executed with `returncode` 0, and `deviations` is empty in both manifests.

The offending gaps (`out/context.txt`):

| run | gaps above 5 s | attributable to the restart | attributable to the sampler |
|---|---:|---|---|
| r02 | 1 | `egw-controller-1` 00:18:29 → 00:18:35 (6.0 s) | — |
| r01 | 7 | `egw-controller-1` 21:55:34 → 21:55:43 (9.0 s) | a simultaneous 6.0 s stall on **all six** containers at 21:59:30 → 21:59:36 |

So in `controller_restart-r02` the run was invalidated by **the condition under test**: restarting the controller makes its container disappear from `docker stats` for longer than the protocol's maximum sampling gap, and the protocol has no way to distinguish that from a sampler failure. In `controller_restart-r01` part of the damage is the separate sampler-cadence defect — 0.23 samples/s for the controller against the 1 Hz the protocol assumes.

**This is a design finding for the recovery ADR, not only an accident.** Any `controller_restart` condition run under the present rule will be invalidated by its own restart unless the ingest rule is given an expected-outage window for the restarted container, or the collector is made to emit an explicit "container absent" row rather than no row at all. Recommending either is outside this package; recording that the rule and the condition are in conflict is not.

---

## 8. Claims that the artefacts do not support

Listed so they are not repeated.

1. **"2,136 lost from RAM."** Refuted. At most 1,985 of them were ever inside the process, and at least 151 never reached it.
2. **"195 published with no subscriber; 131 undetermined."** Not measurements. They are a boundary choice at about 00:18:31Z, and the split moves by about eleven identities per second (section 4.3).
3. **"PUBACKs corroborate delivery."** Refuted: 421 processed identities in r02 carry a null PUBACK (section 4.4).
4. **"The process died by SIGKILL with exit code 137."** ASSUMED. No exit code, no `docker events`, no container log is preserved. The ten-second fit is a good fit, not a record.
5. **"The subscription was clean-session, so nothing was retained."** The *conclusion* is PROVED empirically (nothing was redelivered, `duplicate` stayed at zero). The *reason* is ASSUMED: `src/egw_controller/mqtt.py:73-76` constructs the paho client with no `clean_session` argument, so the default of the installed version applies, and **the paho version inside the running image is not recorded anywhere** — `src/Dockerfile` installs with an unpinned `RUN pip install .`, `sut_environment.json` records no Python package versions, and `egw-controller:0.1.0` is absent from `manifest.json` `image_digests` because it is built locally and never pulled. The harness host's virtual environment has paho-mqtt 2.1.0, which is **not** evidence about the guest image.
6. **"The controller image ran the code at commit `8e88670`."** ASSUMED. `manifest.json` `commit` records the harness repository's commit at run time; no artefact records the controller image's source commit or image id. Every source-based statement in this document inherits that assumption.
7. **"The 765 (r02) and 422 (r01) end-of-run identities were lost."** Not established. They are unresolved at the fetch, with no post-drain fetch to settle them, and the comparable nominal figure resolved to zero loss (section 3).

---

## 9. What a bounded future run would have to record

Grouped by what each item would convert from inference into proof. None of this requires a new measurement campaign; all of it is instrumentation of a run that is already in the plan.

**To close Part A (the residual identity, and the process identity).**
- Add `received`, `in_progress`, `processing_errors`, `started_at` and `uptime_s` to `controller_metrics.csv`. The controller already returns all five; the sampler discards them (`src/egw_experiments/controller_metrics.py:64`). `received` closes the residual by arithmetic; `started_at` pins the restart to the sampling interval instead of inferring it from a counter falling to zero.

**To close Parts B and C (the disconnect instant).**
- Broker connection logging on `egw-mosquitto-1`, fetched into the run directory.
- `docker events` for the controller container over the run window, fetched into the run directory — this also pins the death instant and the signal.
- The controller's container log, fetched into the run directory: it already prints both `MQTT disconnected` and `MQTT subscription granted; bridge ready`.

**To close the fate of the end-of-run block.**
- The post-drain second events fetch and the before/after twin snapshots that `nominal-r01` has and neither restart run has. Without them, "lost" and "late" cannot be told apart at the end of a run, which is exactly the distinction the recovery decision turns on.

**To let the condition produce a valid run at all.**
- Reconcile the `MAX_SAMPLE_GAP_S` ingest rule with a condition whose whole point is to make one container disappear (section 7), and fix the collector cadence, which was 0.23 samples/s in r01 and 0.83 samples/s in r02 against an assumed 1 Hz.

**To make the image's behaviour a fact rather than a source reading.**
- Record the controller image's id and source commit in the manifest, and pin the Python dependencies, so statements about the MQTT session semantics rest on the artefact rather than on a library default.

---

## 10. Provenance of every figure

All scripts are read-only, take a run identifier where applicable, and were run as `wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python scripts/<name>.py [<run_id>]'` from this directory. Nothing was installed.

| Script | Produces | Output |
|---|---|---|
| `scripts/restart_derive.py` | manifest facts, identity reconciliation, gap blocks, receipt timeline, counters across the restart, collector gaps, PUBACK coverage | `out/derive_r02.txt`, `out/derive_r01.txt` |
| `scripts/restart_partition.py` | boundary instants with their artefact lines, the earlier diagnosis's cuts recomputed, the boundary sensitivity table | `out/partition_r02.txt`, `out/partition_r01.txt` |
| `scripts/restart_partition2.py` | the non-overlapping G1/G2/G3 partition, the death bracket, the event-line completeness cross-check, broker rows around the outage | `out/partition2_r02.txt`, `out/partition2_r01.txt` |
| `scripts/restart_ledger.py` | the closed identity ledger, service rates, confirmation-deadline accounting | `out/ledger.txt` |
| `scripts/restart_context.py` | every collector gap above the protocol maximum, sampler cadence, broker CPU windows, environments, image digests | `out/context.txt` |
| `scripts/restart_checks.py` | PUBACK best-effort quantification, no-redelivery check, counter-fall check, monotonic-continuity check | `out/checks.txt` |
| `scripts/nominal_contrast.py` | the sealed nominal run's validity, backlog peak, post-drain accounting and twins | `out/nominal_contrast.txt` |

Source artefacts read, none modified:

- `/home/ruisth/egw-tcg/pilot/results/raw/controller_restart-r02/` and `-r01/` — `manifest.json`, `sent_events.jsonl`, `events.jsonl`, `controller_metrics.csv`, `logs/collector/resources-<run_id>.csv`, `logs/simulator.log`, `sut_environment.json`, `loadgen_environment.json`;
- `/home/ruisth/egw-tcg/pilot/results/raw/nominal-r01/` — `manifest.json`, `controller_metrics.csv`, `SHA256SUMS`;
- `/home/ruisth/egw-exec/attempts/20260919T195827Z_nominal-instrumentation-120-600_attempt01/analysis/` — `accounting.json`, `snapshots/nominal-r01.twins.after.json`;
- `/home/ruisth/egw-exec/attempts/_historical/HIST_controller_restart-r01/` and `-r02/`;
- `/home/ruisth/egw-exec/repo` at `ccd5fd6`, and `git show 8e88670:…` for the deployed commit — `src/egw_controller/{app,service,mqtt,metrics,events}.py`, `src/egw_simulator/{publisher,runner}.py`, `src/egw_experiments/{run,analyze,controller_metrics}.py`, `src/deployment/compose.yaml`, `src/Dockerfile`, `docs/adr/0006`, `docs/adr/0010`;
- `…/scratchpad/pmreview/restart_r02_diagnosis_2026-09-19.md`, the earlier diagnosis under review.
