# What the controller guarantees today, in code

- **Date:** 2026-09-20
- **Package:** D of the project-management work order — the controller's present behaviour, read from the source. This document describes what exists; it proposes nothing.
- **Method:** read-only. The controller package, `src/CONTRACTS.md`, the deployment descriptors and the relevant third-party sources were read end to end in the checkout `/home/ruisth/egw-exec/repo`. No guest was started, no run repeated, nothing measured live. Every command used is in `scripts/commands.sh`; the figures quoted come from `scripts/queue_and_outcomes.py`.
- **Code identity:** head `ccd5fd647a57842707999fa3f2492befa228e11b` (`git log -1`, author `Ruisth`, committer `GitHub`, 2026-09-20T20:51:18+01:00). The package `src/egw_controller/` is **byte-identical** to the commit `8e88670` that was deployed in the runs being diagnosed: `git diff --stat 8e88670..HEAD -- src/egw_controller src/CONTRACTS.md` reports one changed file, `src/CONTRACTS.md`, with two insertions and one deletion (a reference to plan v2.0 in the preamble). The code below is therefore the code that ran in `nominal-r01` and in both restart runs.
- **Third-party versions:** those of the analysis environment `~/egw-exec/venv` — paho-mqtt 2.1.0, uvicorn 0.52.1, fastapi 0.141.1, httpx 0.28.1, jsonschema 4.26.0, CPython 3.12.3. The **container image's** versions are not pinned: `src/Dockerfile:48` runs a bare `pip install .` and `src/pyproject.toml:10-16` only constrains `paho-mqtt>=2.1,<3`, `uvicorn>=0.30`, `httpx>=0.27`. I could not establish which versions are inside `egw-controller:0.1.0` without contacting the guest. Where third-party behaviour is load-bearing below, it is marked as read in the installed sources.

---

## 1. Where the PUBACK is produced

**The controller does not produce the PUBACK itself, and it is sent before the message exists anywhere in the controller's own state.**

The bridge creates a paho client with no `manual_ack` argument (`src/egw_controller/mqtt.py:73-76`), so paho's default `manual_ack: bool = False` applies (`paho/mqtt/client.py:742`, assigned at `:751`). In paho's inbound path, a QoS 1 PUBLISH is handled as follows (`paho/mqtt/client.py:4147-4153`):

```text
4147  elif message.qos == 1:
4148      self._handle_on_message(message)
4149      if self._manual_ack:
4150          return MQTT_ERR_SUCCESS
4151      else:
4152          return self._send_puback(message.mid)
```

`_send_puback` writes the PUBACK straight onto the socket (`paho/mqtt/client.py:3337-3339`). So the PUBACK leaves **as soon as the controller's `on_message` callback returns**, on paho's own network thread.

What the controller's callback does before returning (`src/egw_controller/mqtt.py:187-199`):

1. `received_monotonic_ns = self._monotonic_ns()` — the latency start point (`:189`, contract at `src/CONTRACTS.md:304`);
2. if the event loop is absent or closed, it logs a warning and **returns without doing anything else** (`:190-193`);
3. otherwise it builds an `InboundMessage` (`:194-198`) and calls `loop.call_soon_threadsafe(self._submit, inbound)` (`:199`).

`call_soon_threadsafe` only *schedules* `submit`; it does not run it. The ordering at the moment the PUBACK is written is therefore:

| Step | Where | Has it happened when the PUBACK is sent? |
|---|---|---|
| Arrival timestamp taken | `mqtt.py:189` | yes |
| Handed to the event loop | `mqtt.py:199` | scheduled, **not executed** |
| Put on the internal queue (`submit`) | `service.py:154-169` | no |
| Validated, deduplicated | `service.py:203-314` | no |
| Written to Ditto (`PATCH`, 2xx) | `service.py:320`, `ditto.py:335-345` | no |
| Recorded in `events.jsonl` | `service.py:414`, `events.py:112-119` | no |

**Consequence, stated plainly:** today the PUBACK means "a callback ran in the controller process". It does not mean queued, accepted, persisted, applied to the twin, or recorded. There is no code path in `src/egw_controller/` that defers the acknowledgement until any of those; `manual_ack` is never set and `manual_ack_set` is never called (confirmed by `grep -rn "manual_ack" src/egw_controller/` — no match).

A second consequence is that the broker's QoS 1 in-flight window cannot throttle the controller. `src/deployment/mosquitto/config/mosquitto.conf` (56 lines, read in full) sets no `max_inflight_messages`, and whatever that limit is, it is released by a PUBACK that does not wait for processing. The queue below therefore grows under load with no back-pressure anywhere in the chain.

---

## 2. The internal queue: what it is, whether it is bounded, and what happens when the process stops

### 2.1 What it is

`asyncio.Queue` in the controller process's memory (`src/egw_controller/service.py:150-152`):

```text
150  self._queue: asyncio.Queue[InboundMessage | None] = asyncio.Queue(
151      maxsize=queue_maxsize
152  )
```

It holds `InboundMessage` objects — topic, raw payload bytes and the arrival timestamp (`service.py:81-87`). It is **purely volatile**: nothing writes it to disk, and there is no `fsync`, `atexit` hook or signal handler anywhere in the package (`grep -rn "signal|atexit|fsync|queue_maxsize|QUEUE" src/egw_controller/*.py` returns only the three `queue_maxsize` lines).

There is exactly one consumer (`service.py:175-197`), so processing is strictly first-in, first-out per process.

### 2.2 Whether it is bounded

Bounded at **10 000 entries** (`service.py:39`, `DEFAULT_QUEUE_MAXSIZE = 10000`), applied because `create_app_from_env` constructs `ControllerService` without a `queue_maxsize` argument (`app.py:144-150`). The bound is a module constant: `src/egw_controller/config.py` defines no `EGW_*` variable for it (the full `Settings` field list is `config.py:55-76`), so it cannot be changed through the environment, only by editing the source.

On overflow (`service.py:154-169`):

```text
161      self._metrics.increment_received()
162      try:
163          self._queue.put_nowait(message)
164      except asyncio.QueueFull:
165          self._metrics.increment_dropped()
166          logger.warning(
167              "inbound queue full; dropping message",
168              extra={"context": {"topic": message.topic}},
169          )
```

The message is counted in `received` and in `dropped`, and the log line carries **only the topic** — not `message_id`, not `seq`. Nothing is written to `events.jsonl`. A dropped message is therefore invisible to identity reconciliation except as an absence.

**Observed, for context:** in `nominal-r01` the bound was never approached. Over the 721 samples of `results/raw/nominal-r01/controller_metrics.csv` the maximum `queue_depth` is **3 590** (last sample, 2026-09-19T20:12:44.846Z) and `dropped` is **0** in every sample (`scripts/queue_and_outcomes.py`). The nominal backlog is a throughput and deadline problem, not an overflow problem: `attempts/20260919T195827Z_nominal-instrumentation-120-600_attempt01/analysis/accounting.json` records `events_records_after_drain: 6720` with `after_drain.accepted_late: 2926`, i.e. every published identity was eventually accepted, 2 926 of them past the confirmation deadline.

### 2.3 On SIGTERM

The controller installs no signal handler of its own. uvicorn does: `HANDLED_SIGNALS` contains `SIGINT` and `SIGTERM` (`uvicorn/server.py:36-40`), and `handle_exit` sets `should_exit = True` for SIGTERM (`uvicorn/server.py:342-347`; only a **second** SIGINT sets `force_exit`). `Server.shutdown` then closes the listening sockets, waits for connections and tasks with `timeout=self.config.timeout_graceful_shutdown` (`uvicorn/server.py:272-298`) and finally runs the ASGI lifespan shutdown (`uvicorn/server.py:300-302`), which waits on `shutdown_event` with **no timeout at all** (`uvicorn/lifespan/on.py:64-70`). Nothing in the repository sets `--timeout-graceful-shutdown` (the image's command is `src/Dockerfile:70-71`), so uvicorn's own graceful wait is unbounded.

The lifespan `finally` block is the whole of the controller's shutdown (`src/egw_controller/app.py:159-164`):

```text
159      finally:
160          bridge.stop()
161          await service.stop()
162          await pipeline_task
163          await ditto.aclose()
164          events.close()
```

- `bridge.stop()` (`mqtt.py:211-217`) sends DISCONNECT and calls `loop_stop()`, which blocks until the paho network thread has finished (`paho/mqtt/client.py:2351-2365`). After this returns, no new message can be scheduled.
- `service.stop()` puts a `None` sentinel on the queue (`service.py:199-201`). `asyncio.Queue.put` does not yield when the queue is not full, so the sentinel is appended **immediately**, ahead of any `submit` callback that the network thread scheduled but the loop has not yet run.
- `await pipeline_task` then lets the consumer drain everything **ahead of** the sentinel (`service.py:182-197`), one message at a time, each with its Ditto call and retries. It stops at the sentinel (`service.py:184-185`).

So on SIGTERM the backlog is drained — **if the process is allowed to finish**. Two things bound that in practice:

1. `src/deployment/compose.yaml` sets **no `stop_grace_period`** for the controller (`grep -n "stop_grace_period|stop_signal" compose.yaml` returns nothing; the service is `compose.yaml:243-313`) and `src/Dockerfile` sets no `STOPSIGNAL`. The engine default applies: SIGTERM, then SIGKILL. The restart the runbook prescribes is `docker compose ... restart controller` with no `-t` (`docs/setup/qemu_integrated_gateway.md:1123`).
2. Draining is paced by the Ditto round trip under emulation. In the restart runs the allowance was consumed long before the queue emptied — `controller_restart-r02` carried 1 867 queued entries at its last good poll (`results/raw/controller_restart-r02/controller_metrics.csv`, sample 306, 2026-09-19T00:18:19.443Z; `scripts/queue_and_outcomes.py`), and `controller_restart-r01` 1 487 at sample 307.

**Messages enqueued behind the sentinel are never processed and never recorded.** This is not an accident of implementation; it is written into the contract: "A message enqueued behind the marker is counted in `received` and stays in `queue_depth`" (`src/CONTRACTS.md:284-286`).

### 2.4 On SIGKILL

No code runs. The queue, the message in progress, the `DedupeCache` and the counters are process memory and disappear with it. `src/CONTRACTS.md:287` states the same: "A process that is killed runs no code".

The event log survives only up to its last completed write: `EventLogger.log` appends one line and calls `fh.flush()` (`events.py:112-119`), which flushes the Python buffer to the kernel. There is no `os.fsync`, so a **guest** power loss can still lose the tail; a SIGKILL of the controller process alone cannot, because the bytes are already with the kernel and the file is bind-mounted to the host directory `deployment/data/events` (`compose.yaml:284-290`).

The container is declared `restart: unless-stopped` (`compose.yaml:256`), so after a kill the engine starts a new process, whose counters begin at zero (`metrics.py:106-116`) and whose `DedupeCache` is empty (`app.py:140`).

---

## 3. The MQTT session settings that decide what happens while the controller is down

Everything below is in `src/egw_controller/mqtt.py:71-85` and the paho defaults it inherits.

| Setting | Value today | Where |
|---|---|---|
| Protocol | MQTT 3.1.1 | not passed; paho default `protocol: MQTTProtocolVersion = MQTTv311` (`paho/mqtt/client.py:739`) |
| **Clean session** | **True** | not passed; for a non-v5 protocol paho sets `clean_session = True` when it is `None` (`paho/mqtt/client.py:784-785`, stored at `:789`) |
| Client id | `egw-controller-{EGW_ID}`, i.e. `egw-controller-egw-01` by default | `mqtt.py:75`; `EGW_ID` default at `config.py:59`, `:104` |
| Subscription QoS | 1, requested at every connect | `mqtt.py:103`; granted QoS 0 or 1 both accepted (`mqtt.py:35`, `:149-150`) |
| Topic filter | `c2dt/+/+/telemetry` | `config.py:66`, `:111` |
| Session expiry / MQTT 5 properties | none | no `properties` argument anywhere in `mqtt.py` |
| Keepalive | 60 s | `mqtt.py:31`, used at `:207` |
| Reconnect | automatic, 1 s to 30 s back-off | `mqtt.py:82-84` |
| Broker persistence | `persistence true`, `persistence_location /mosquitto/data/`, `autosave_interval 60` | `deployment/mosquitto/config/mosquitto.conf:33-35` |
| Broker queue limits | none configured | no `max_queued_messages`, `max_inflight_messages` or `persistent_client_expiration` in the 56 lines of `mosquitto.conf` |

**What this means for a controller that is down.** With Clean Session = 1 the broker discards the controller's session state at every disconnect and creates a fresh one at every CONNECT. Messages published to `c2dt/+/+/telemetry` while the controller is not connected are matched against no subscription and are not queued for it. The broker's `persistence true` preserves sessions and queued QoS 1 messages **across restarts of the broker**; it does not create a session for a client that asked for a clean one. The earlier diagnosis observed exactly this behaviour in `controller_restart-r02`: the new process received what was published after it resubscribed and nothing from the gap (`scratchpad/pmreview/restart_r02_diagnosis_2026-09-19.md`, "Subscription" row).

There is also a window on the way up. `bridge.start` calls `connect_async` and `loop_start` (`mqtt.py:203-209`), the SUBSCRIBE is only issued from `_on_connect` (`mqtt.py:103`), and readiness is only declared when the SUBACK grants it (`mqtt.py:129-159`). Between the old process's disconnect and the new subscription's SUBACK, nothing is subscribed. In `controller_restart-r02` that window was about 17 to 29 s (`restart_r02_diagnosis_2026-09-19.md`, "New subscriber").

---

## 4. What makes processing idempotent today, and what a replay would do

### 4.1 The three mechanisms

**a. The derived `message_id`.** `message_id` must be the UUID v5 of `"{run_id}:{device_uuid}:{seq}"` over the project namespace (`service.py:49`, `:72-78`; contract `src/CONTRACTS.md:35`, `:42-43`). The controller recomputes it and rejects any divergence *before* the dedupe cache is consulted and before any twin is seeded or patched (`service.py:270-285`, `:361-373`). This is what lets duplicate detection treat the identifier as a pure function of the three fields.

**b. The in-process `DedupeCache`** (`src/egw_controller/dedupe.py`). Per device it holds `last_seq`, `last_run_id`, `accepted_count` and an LRU of `message_id`s bounded at **1 024** entries (`dedupe.py:21`, `:32-37`, `:126-127`; the default is taken because `app.py:140` constructs `DedupeCache()` with no argument). `check` rejects a repeated `message_id` always, and rejects `seq <= last_seq` **only within the same `run_id`** (`dedupe.py:91-113`). `record` advances the state and is called **only after a Ditto 2xx** (`service.py:331-334`).

**c. The twin's `ingestion` feature**, which is the only part of this that survives a restart. Every accepted patch writes `last_message_id`, `last_seq`, `last_run_id`, `last_ts` and `accepted_count` (`ditto.py:68-76`). On the first message from a device after start-up the controller reads the twin and rebuilds the cache from it (`service.py:287-301`, `:375-388`; `dedupe.py:52-81`), creating policy and thing on true first contact (`ditto.py:301-321`).

Note the ordering inside `process`: seeding, then the duplicate check, then the Ditto patch, then `dedupe.record`, then the event record (`service.py:290-343`). The **twin is written before the local state is advanced and before anything is recorded**.

### 4.2 What is idempotent, and what is not

- A broker-level QoS 1 redelivery of a message already accepted is caught — by the LRU while the id is still in it, and otherwise by the `seq <= last_seq` rule within the same run. It is recorded as `outcome: "duplicate"` with null latency (`service.py:303-314`; `events.py:92-101` enforces the nulls).
- Idempotency is **at most once past the twin**, not exactly once end to end: there is no transaction spanning the Ditto write and the event record. A crash between `service.py:320` (the PATCH returned 2xx) and `service.py:414` (the line is written) leaves the twin updated with no record of it.
- The `accepted_count` written to the twin is the controller's local count plus one (`service.py:316-318`), seeded from the twin at start-up. It counts **accepted patches**, not distinct messages, and it is what the runbook's `delta` check reads across a restart (`docs/setup/qemu_integrated_gateway.md:1130`).
- A retried PATCH is applied to the twin more than once when the first attempt reached Ditto and its response was lost: `_request` retries on any `httpx.TransportError`, timeouts included (`ditto.py:228-250`). The body is identical on each attempt, so the twin's content is unchanged by the repetition — but the controller cannot tell a lost response from a lost request, and if the retries are exhausted it records `failed` (`ditto.py:251-255`, `service.py:321-329`) for a message the twin may already carry.

### 4.3 What a replay would do today

There is no replay mechanism in the controller: nothing re-reads `sent_events.jsonl`, `events.jsonl` or any store, and nothing re-publishes. A replay would have to come from outside, as a fresh publication. Its outcome is fully determined by the rules above:

| Replay | Outcome in code | Where |
|---|---|---|
| Same `run_id`, `seq` **above** the twin's `last_seq` for that device | accepted, patched, recorded normally | `dedupe.py:103-112` does not fire |
| Same `run_id`, `seq` **at or below** `last_seq` | `duplicate`, no Ditto call, null latency, recorded as `duplicate` — never as `accepted` | `service.py:303-314` |
| Same `run_id`, id still in the 1 024-entry LRU | `duplicate` | `dedupe.py:101-102` |
| A **different** `run_id` | different `message_id` (it is derived from `run_id`), seq floor reset, accepted again, `accepted_count` grows | `service.py:72-78`; `dedupe.py:128-133` |
| Same identity but a tampered `message_id` | `rejected`, no Ditto call | `service.py:276-285` |

Two consequences matter for the controller's recovery decision, and both are properties of the code as it stands.

1. Because the single consumer is FIFO, everything left unprocessed when a process dies has a `seq` **above** the last one that reached the twin for that device. A replay of exactly that backlog, under the same `run_id`, would therefore be accepted rather than rejected as duplicate.
2. The exception is the message that was **in flight to Ditto** when the process died. If its PATCH was applied, the twin's `last_seq` already covers it while `events.jsonl` does not; a replay of it would then be classified `duplicate` and could never acquire an `accepted` record. In `controller_restart-r02` that is the single identity `clothing 1422` (`restart_r02_diagnosis_2026-09-19.md`, attribution table), and whether its PATCH reached Ditto is listed there as still open.

---

## 5. What the counters expose, and what they cannot express

### 5.1 What `GET /metrics` returns

One JSON object, assembled in a single event-loop step (`app.py:119-127`; the handler is a coroutine deliberately, so that `snapshot()` and `queue_depth()` are read without an intervening `await`):

| Field | Meaning | Where |
|---|---|---|
| `accepted`, `rejected`, `duplicate`, `failed` | the four outcome counters | `metrics.py:106`, `:119-125`; `events.py:32` |
| `dropped` | discarded on queue overflow, never processed | `metrics.py:127-130`; `service.py:165` |
| `received` | handed to the pipeline, counted **before** the capacity decision | `metrics.py:132-135`; `service.py:161` |
| `in_progress` | taken from the queue, processing not ended (0 or 1) | `metrics.py:137-141`, `:143-160` |
| `processing_errors` | taken from the queue, ended with **no outcome counter having moved** | `metrics.py:143-160` |
| `queue_depth` | entries waiting, excluding the one in progress | `service.py:171-173`; added by the handler at `app.py:127` |
| `started_at`, `uptime_s` | process identity by wall-clock start and elapsed monotonic time | `metrics.py:115-116`, `:169`, `:181` |
| `monotonic_ns`, `wall_utc` | the confirmation marker, read at request time | `metrics.py:170-173`; contract `src/CONTRACTS.md:128-162` |

The accounting identity the contract states (`src/CONTRACTS.md:214-218`) holds for **one** response read on the controller's own event loop, and the module docstring is explicit that the lock does not give it to a reader on another thread (`metrics.py:46-57`).

`processing_errors` is a **residual**, not an error handler: `processing_finished` raises it, in the same lock acquisition that lowers `in_progress`, when the four outcome counters have not moved since `processing_started` (`metrics.py:153-160`). Its meaning is "no outcome was recorded", not "not applied" — the twin may already carry the update, because the Ditto write precedes the record (`src/CONTRACTS.md:186-195`).

### 5.2 What they cannot express

- **No message identity, anywhere.** Every field is an integer count or a clock reading. Nothing in the response names a `message_id`, a `device_uuid` or a `seq`. The contract says so in terms (`src/CONTRACTS.md:228-238`): the counters "never replace the reconciliation, by identity, of the messages sent with the outcomes recorded in `events.jsonl`".
- **No coverage of what never reached the pipeline** — a message not published, one held by the broker, one in a socket buffer, one still in the thread hand-over, or one discarded by the callback because no event loop was running (`src/CONTRACTS.md:230-234`; the discard is `mqtt.py:190-193`).
- **No comparability across a restart.** All counters restart at zero with the process (`metrics.py:106-116`); the contract's reader rules (`src/CONTRACTS.md:247-273`) allow differences only between readings of one process, and state that a closing reading's `in_progress + queue_depth` is "neither a lower nor an upper bound" on the messages left without an outcome.
- **`in_progress == 0 and queue_depth == 0` is not completeness.** It is the controller's statement that it holds no work *at that instant* (`src/CONTRACTS.md:220-226`).

### 5.3 The identity the harness reconciles by, and what was actually sealed

The harness reconciles by **`message_id`** — the UUID v5 of `run_id:device_uuid:seq` (`service.py:72-78`). In `analyze.py` the sent side builds `valid_ids` from `sent_events.jsonl` keyed on `message_id` (`analyze.py:1645-1655`), the controller side matches `accepted` records by the same key (`analyze.py:1765`, `:1789`), and `delivered`/`lost` follow from set arithmetic on those identities (`analyze.py:1808`, `:1821`; definitions at `analyze.py:15-52`).

The counters are a much weaker record than the endpoint suggests, because only six of the twelve fields are sampled. `controller_metrics.csv` has the header `ts_utc,accepted,rejected,duplicate,failed,dropped,queue_depth` (`src/egw_experiments/controller_metrics.py:53-64`), which the contract confirms is deliberate (`src/CONTRACTS.md:289-291`). `received`, `in_progress` and `processing_errors` appear **nowhere** in the harness: `grep -rn "processing_errors|in_progress" src/egw_experiments/*.py` returns no match, and they are absent from `results/raw/nominal-r01/manifest.json` (all 52 top-level keys listed by `scripts/commands.sh` step 6). The manifest keeps only the marker snapshot, under `controller_marker`.

**So the accounting identity cannot be evaluated from the sealed evidence of any run.** A concrete illustration from `nominal-r01`: the last sample of `controller_metrics.csv` (2026-09-19T20:12:44.846Z) reads `accepted = 4524`, `queue_depth = 3590`, everything else zero. Those two terms sum to 8 114, which cannot be reconciled against the 6 720 identities of the measured run, because the counters belong to the process — which also served the 120 s warm-up (`manifest.json: warmup_s = 120`, `measured_window_utc.start = 2026-09-19T20:02:45.643Z`, while the first CSV sample is 2026-09-19T20:00:45.540Z with `accepted = 60`) — and because `received` and `in_progress` were never recorded. I could not close that arithmetic from these files: the warm-up's own event log carries 1 344 accepted records (`analysis/warmup.events.jsonl`), and 6 720 + 1 344 = 8 064, fifty short of 8 114. The residual is exactly the kind of question the counters are unable to answer, and only reconciliation by identity settles it.

---

## 6. Every place where a message can be accepted by the broker and then disappear without a record

"Record" here means a line in `events.jsonl` carrying the message's identity. The list is ordered along the path; each entry names the code that makes it possible.

**A. Published and acknowledged to the publisher while no subscription exists.** Clean Session = 1 (`mqtt.py:73-76`; paho default at `paho/mqtt/client.py:784-789`) means the broker holds no session for a disconnected controller, so nothing is queued for it. Nothing reaches the controller and nothing anywhere records the message. This covers both the down time of the process and the gap between reconnect and SUBACK (`mqtt.py:103`, `:129-159`).

**B. Delivered to the callback with no running event loop.** `_on_message` logs `"message received before bridge start; dropping"` and returns (`mqtt.py:190-193`). The log line carries no identity, and paho sends the PUBACK immediately afterwards (`paho/mqtt/client.py:4148-4152`). The broker then considers the message delivered.

**C. Between the PUBACK and `submit`.** The PUBACK is written when the callback returns (`paho/mqtt/client.py:4148-4152`); `submit` runs later, on the event loop (`mqtt.py:199`, `service.py:154`). A process death in that interval leaves a message the broker has acknowledged and the controller never counted.

**D. Queue overflow.** `dropped` is incremented and a warning naming only the topic is logged; no `events.jsonl` line is written (`service.py:163-169`). Not observed in any of the three sealed runs — `dropped` is 0 in every sample of all three `controller_metrics.csv` files (`scripts/queue_and_outcomes.py`).

**E. In the volatile queue when the process is killed.** The queue is process memory (`service.py:150-152`); SIGKILL runs no code (`src/CONTRACTS.md:287`). This is the largest class in `controller_restart-r02`: 1 810 identities, proven received and then discarded unfinished (`restart_r02_diagnosis_2026-09-19.md`, attribution table).

**F. Enqueued behind the shutdown sentinel during a graceful stop.** `service.stop()` appends `None` without yielding (`service.py:199-201`); the consumer breaks at it (`service.py:184-185`). Anything scheduled by the network thread and executed after that point is counted in `received`, sits in `queue_depth` and is never processed (`src/CONTRACTS.md:284-286`).

**G. A graceful drain cut short by the engine's stop timeout.** No `stop_grace_period` in `compose.yaml:243-313`, no `STOPSIGNAL` in `src/Dockerfile`, no `--timeout-graceful-shutdown` in the command (`src/Dockerfile:70-71`). uvicorn would wait indefinitely (`uvicorn/lifespan/on.py:64-70`); the engine will not.

**H. The consumer cancelled.** `processing_errors` is incremented and nothing is recorded (`metrics.py:143-160`; `src/CONTRACTS.md:186-195`). `create_app_from_env` awaits the pipeline task rather than cancelling it (`app.py:162`), so this requires a cancellation from outside the lifespan.

**I. The event-log write itself failing.** `_emit` calls `self._events.log(event)` **before** `self._metrics.increment(outcome)` (`service.py:414-415`). An `OSError` from the append or flush (`events.py:112-119`) propagates out of `process`, is caught by the consumer's blanket handler (`service.py:191-195`) and ends as a `processing_errors` residual (`service.py:196-197`). The twin has already been patched.

**J. Between the Ditto 2xx and the record.** `patch_thing` returns at `service.py:320`, `dedupe.record` runs at `:332-334`, the line is written at `:414`. A death in that window leaves the twin advanced — and, by section 4.3, a replay of that identity classified `duplicate` for ever after.

**K. Recorded, but into a file the harness never collects.** When `run_id` is absent or does not match `^[A-Za-z0-9._-]{1,64}$`, the record goes to the `unknown` bucket, i.e. `{EGW_EVENT_LOG_DIR}/unknown/events.jsonl` (`events.py:36-39`, `:74-82`, `:103-110`). The harness fetches only `<run_id>/events.jsonl` (`manifest.json: events_source = "fetch-cmd: scp egw-tcg:/opt/egw/deployment/data/events/nominal-r01/events.jsonl ..."`). The record exists on the guest and is absent from the evidence.

**L. Guest power loss with records in the page cache.** `events.py:119` flushes to the kernel; there is no `os.fsync` in the package. A SIGKILL of the controller alone does not lose those bytes; a loss of the guest can.

**M. An invalid-UTF-8 topic reaching the callback.** `mqtt.py:195` reads `message.topic`, which paho decodes as UTF-8 and which raises `UnicodeDecodeError` for invalid bytes; the exception propagates out of `on_message`, paho re-raises it because `suppress_exceptions` is false by default (`paho/mqtt/client.py:877`, re-raise at `:4498-4506`), and the PUBACK at `:4152` is never reached. The message is neither acknowledged nor recorded, and the network thread ends. Read in the sources only — **not observed in any preserved run**, and a topic that fails UTF-8 decoding cannot match the filter `c2dt/+/+/telemetry` in the first place.

Paths **A**, **E** and **F** are the ones the two restart runs exercised. Paths **B**, **D**, **H**, **I**, **J**, **K**, **L** and **M** are reachable in the code as written and were not observed in the three sealed runs.

---

## 7. Summary: the guarantees that exist, and the ones that do not

**What the controller guarantees today, in code:**

1. Every message that reaches `ControllerService.process` and ends with an outcome gets exactly one line in `events.jsonl`, carrying its identity, its outcome, its attempt count and — for `accepted` only — the ack timestamp and latency (`service.py:390-415`; `events.py:84-101` refuses a record that breaks that rule).
2. No Ditto call is made before topic parsing, JSON decoding, schema validation, topic-versus-payload consistency and the `message_id` derivation have all passed (`service.py:212-285`).
3. An accepted message has a 2xx from Ditto behind it: `dedupe.record` and the `accepted` record happen only after `patch_thing` returned (`service.py:319-343`).
4. Within one process, a repeated `message_id` is never accepted twice; across a restart, the `seq` floor and `last_message_id` are rebuilt from the twin before the first message of each device is judged (`service.py:287-301`; `dedupe.py:52-81`, `:91-113`).
5. Retries are bounded and never applied to a 4xx (`ditto.py:228-255`), and the process does not die on a message that raises: the consumer catches everything and counts the residual (`service.py:191-197`; `metrics.py:143-160`).
6. One `/metrics` response is one self-consistent snapshot of that process (`app.py:119-127`; `metrics.py:162-184`).

**What is not guaranteed, and is not claimed anywhere in the code:**

1. The MQTT acknowledgement does not imply durability, processing, application or recording (section 1).
2. There is no durable inbound buffer. The queue is volatile, bounded at a hard-coded 10 000, and its contents do not survive a kill (section 2).
3. Nothing is retained for the controller while it is disconnected: Clean Session = 1 (section 3).
4. There is no exactly-once boundary spanning the twin write and the event record; a crash between them leaves the twin advanced and the record missing, and makes a later replay of that identity a `duplicate` (sections 4.2, 4.3).
5. The counters cannot express which messages are missing, and the three fields that would even let the accounting identity be checked are not written to any sealed artefact (section 5).

---

## 8. What I could not establish

- **Which paho-mqtt and uvicorn versions are inside `egw-controller:0.1.0`.** `src/Dockerfile:48` installs unpinned; `src/pyproject.toml:11` allows any `paho-mqtt>=2.1,<3`. Everything stated about paho and uvicorn behaviour was read in `~/egw-exec/venv` (paho-mqtt 2.1.0, uvicorn 0.52.1) and is marked as such. Settling it needs the guest, or the image.
- **The broker's effective `max_inflight_messages` and `max_queued_messages`.** `mosquitto.conf` sets neither; the compiled-in defaults of the deployed Mosquitto were not read here, and no broker was contacted.
- **Whether the PATCH of the in-flight message survived the restart in `controller_restart-r02`** (`clothing 1422`). Deciding it means reading the twin or Ditto's logs on the guest.
- **The fifty-message residual in `nominal-r01`'s last counter sample** (section 5.3): `accepted 4 524 + queue_depth 3 590 = 8 114` against `6 720 + 1 344 = 8 064`. The missing terms (`received`, `in_progress`) were never recorded, and I will not guess at the difference.
- **Whether any of paths B, D, H, I, J, K, L or M has ever occurred.** `dropped` is zero in every sample of all three runs, which excludes D for those runs; the others leave either no artefact at all or an artefact on the guest (a stderr log line, or an `unknown/events.jsonl`) that was not collected.
