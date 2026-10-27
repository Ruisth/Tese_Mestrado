# Gate item 3 — the acknowledgement order, and every delivery that ends without an outcome line

- **Date:** 2026-09-21.
- **Answers:** item 3 of `decision_request.md` (line 30) and item 5 of "Open before the decision" in
  `adr-0011-controller-restart-recovery.md` (lines 1112-1120), for option 5 as the ADR states it
  (lines 577-609, 649-654).
- **Status:** analysis for the student's decision. It changes no code, no contract, no threshold and
  no rule, and it accepts nothing. No guest was started, no broker was contacted, and no command that
  changes repository state was run.

**Code identity.** Every `file:line` under `src/` is at the merged `dev` head `35fe8bb` (merge of pull
request #41, 2026-09-21). The WSL clone named for this item, `/home/ruisth/egw-exec/repo`, is **not**
at that commit: its HEAD is `b7e0c83`, detached. I read it anyway, because every blob of
`src/egw_controller/`, `src/CONTRACTS.md`, `src/pyproject.toml`, `src/deployment/compose.yaml` and
`src/deployment/mosquitto/config/mosquitto.conf` in its working tree is byte-identical to `35fe8bb`,
compared blob hash by blob hash against the Windows repository [A §1]. The repository's working tree
was clean before and after this work (`git status --short` empty).

**Library identity.** paho-mqtt behaviour is read in `~/egw-exec/venv` (paho-mqtt 2.1.0; Python
3.12.3) [A §3; P:1, P:16]. It is **not** evidence about the controller image: the image installs its
dependencies unpinned (`src/pyproject.toml:11`, `paho-mqtt>=2.1,<3`) on
`python:3.12.13-slim` (`src/Dockerfile:25`), and no run manifest records the paho version inside it
(ADR 0011, lines 42-49).

**Labels.**
- **SPEC** — normative text of *MQTT Version 3.1.1*, OASIS Standard, 29 October 2014
  (docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html), cited by section and conformance
  identifier.
- **DOC** — the Mosquitto documentation on mosquitto.org (`mosquitto.conf(5)` manual page;
  `ChangeLog.txt`) or the Eclipse Paho Python documentation (eclipse.dev/paho/files/paho.mqtt.python/html/),
  cited by document and entry.
- **SOURCE** — code read at `file:line`; `client.py` means
  `~/egw-exec/venv/lib/python3.12/site-packages/paho/mqtt/client.py` (2.1.0); `asyncio/…` means
  `/usr/lib/python3.12/asyncio/…` in the analysis environment.
- **PROBED** — observed by running `gates/scripts/item3_probe.py` in the analysis environment (no
  network, no broker, nothing written to disk); `[P:n]` is line *n* of `gates/out/item3_probe.out.txt`,
  and the tracebacks are in `gates/out/item3_probe.stderr.txt`. A probe result is a fact about that
  Python and that paho, not about the image.
- **ASSUMED** — rests on protocol semantics or a library behaviour that no preserved artefact records.
- *I could not establish* — said where none of the above settles a point.

`[A §n]` is section *n* of `gates/out/item3_anchors.out.txt`, which prints every cited line range.

---

## 1. The answer in brief

1. **MQTT 3.1.1 requires a receiving client to send its PUBACKs in the order in which it received the
   QoS 1 PUBLISH packets** [SPEC §4.6, MQTT-4.6.0-2], and to answer every QoS 1 PUBLISH with a PUBACK
   [SPEC §4.3.2, MQTT-4.3.2-2; §4.5, MQTT-4.5.0-2]. It does not require the PUBACK to wait for, or to
   precede, the application's processing (§4.3.2, note to Figure 4.2), so acknowledging after the
   outcome line is permitted. The server is required to resend an unacknowledged PUBLISH only when a
   client resumes a persistent session [SPEC §4.4, MQTT-4.4.0-1], and Mosquitto documents that it does
   not resend on a live connection (DOC, `ChangeLog.txt`, 1.5).
2. **paho-mqtt 2.1.0 gives manual acknowledgement and nothing more.** `ack(mid, 1)` queues one PUBACK
   packet for that identifier, whichever connection is current, without checking that the identifier
   was delivered, is outstanding or was already acknowledged; it is a silent no-op unless the client
   was built with `manual_ack=True`, and a no-op for QoS 0 (`client.py:4165-4176`; P:17-19). Paho keeps
   no record of received QoS 1 messages, discards PUBACKs not yet written when it reconnects
   (`client.py:1577`) and sends queued PUBACKs strictly in the order `ack()` was called
   (`client.py:3776`, `:3163`). Order, completeness and connection scoping are the application's job.
3. **With the single FIFO consumer, PUBACKs requested right after each outcome line leave in receipt
   order automatically — except where a delivery ends without an outcome line.** Today that happens on
   eleven paths (section 5). On two of them the cause is in the payload (L1, deterministic) or in
   Ditto's answer (L2, possibly persistent), and on a third in the event log (L3): under option 5 as
   written, each such delivery would never be acknowledged, would hold a broker in-flight slot for the
   rest of the connection, and — when the cause persists — would fail again at every redelivery: a
   poison message, of which *W* turn into a stall [P:4-10].
4. **Of the ADR's two choices for a delivery that ends without an outcome line while the connection
   stays up, only "end the connection" is defensible.** "Hold an in-flight slot" leaves the duty of
   MQTT-4.3.2-2 and MQTT-4.5.0-2 unmet for the life of the connection, cannot recover within it (DOC,
   1.5), and loops for ever on a deterministic failure. Ending the connection is itself only safe once
   deterministic failures produce outcome lines.
5. **The rule option 5 needs** (section 7): every delivery the consumer takes ends in exactly one
   outcome line — a processing error included — unless the event log cannot be written, the consumer
   is cancelled, the process dies, or an exception follows the Ditto 2xx; the PUBACK is requested once,
   by the consumer, right after that line and before the next delivery is taken; PUBACKs on a
   connection form a gap-free prefix of that connection's deliveries in receipt order, so the first
   delivery that cannot be acknowledged ends acknowledgement on that connection and the connection
   itself; acknowledgements and processing are scoped to the connection that delivered.
6. **Consequence:** option 5 stays **in, with conditions** — the rule of section 7 and the code changes
   of section 8, several of which are not in the ADR's list ("What must change", lines 888-916). With
   the rule, the broker's treatment of out-of-order PUBACKs, which I could not establish, no longer
   matters, because the controller never sends one.

---

## 2. What MQTT 3.1.1 requires of a client that receives QoS 1 messages [SPEC]

| Section, identifier | What it requires (paraphrased) |
|---|---|
| §4.3.2, MQTT-4.3.2-2 (Receiver) | Respond to a QoS 1 PUBLISH with a PUBACK carrying its Packet Identifier, "having accepted ownership of the Application Message". After sending that PUBACK, treat any PUBLISH with the same identifier as a new publication, whatever its DUP flag. |
| §4.3.2, note 1 to Figure 4.2 | The receiver need not complete onward delivery before sending the PUBACK; ownership passes to the receiver when the sender receives the PUBACK. Acknowledging *after* the outcome line is therefore allowed, not required. |
| §4.3.2 (Sender), MQTT-4.3.2-1; §2.3.1, MQTT-2.3.1-3 and -4 | The sender treats the PUBLISH as unacknowledged until the PUBACK arrives; the identifier becomes reusable once the sender has received the PUBACK. This is the ground for the ADR's connection scoping (ADR lines 761-767, marked ASSUMED there): a late PUBACK carrying a reused identifier releases a different message. |
| §4.5, MQTT-4.5.0-2 | The client must acknowledge every PUBLISH it receives according to its QoS, whether or not it elects to process the message. |
| §4.6, MQTT-4.6.0-2 | The client must send PUBACKs in the order in which the corresponding QoS 1 PUBLISH packets were received. (MQTT-4.6.0-1: re-sent PUBLISH packets go in their original order.) |
| §4.6, MQTT-4.6.0-5 and -6 | By default every topic is ordered; the server applies the same rules when delivering to each subscriber, and sends PUBLISH packets for the same topic and QoS in the order received from a given client. The non-normative comment adds that duplicates can arrive after a successor (1,2,3,2,3,4) unless the in-flight window is 1. |
| §4.4, MQTT-4.4.0-1 | On reconnection with CleanSession 0, client and server must re-send every unacknowledged QoS > 0 PUBLISH with its original identifier; this is the only case in which redelivery is required. |
| §3.1.2.4, MQTT-3.1.2-4 and -5 | With CleanSession 0 the server keeps the session after disconnection and stores further QoS 1 messages that match the client's subscriptions. With CleanSession 1 the session is discarded (MQTT-3.1.2-6). |
| §4.1 | The client's session state lists QoS 1/2 messages it *sent* and QoS 2 messages it received — no received QoS 1 message. A QoS 1 receiver keeps no protocol state for what it received; the server keeps the unacknowledged ones. |
| §3.14.4, MQTT-3.14.4-2 | After sending DISCONNECT the client sends no further packet on that connection — no PUBACK can follow the controller's own DISCONNECT. |

**What the specification does not settle.** It sets no time limit on a PUBACK. It does not say whether
a client that acknowledges later deliveries while never acknowledging an earlier one on that connection
breaches MQTT-4.6.0-2, or only leaves MQTT-4.3.2-2 and MQTT-4.5.0-2 unmet until the connection ends:
*I could not establish* which reading is intended from the text. It is unambiguous that, while the
connection lasts, the unacknowledged delivery's duty to respond is unmet, and that the server need not
resend it before a reconnection (§4.4).

---

## 3. What the Mosquitto documentation says, on this item only [DOC]

The deployed broker is `eclipse-mosquitto:2.0.22` (`src/deployment/images.lock.env:39`). Line numbers
below are in the verification copies under `gates/sources/`, retrieved on 2026-09-21 by another gate
item; `ChangeLog.txt` and `man_mosquitto-conf-5.html` have the same SHA-256 as the copies I retrieved
the same day (`gates/sources/SHA256SUMS.txt`), and `man_mosquitto-conf-5.txt` is that page's text.

- **No resend on a live connection.** `ChangeLog.txt`, release 1.5 (2018-05-02; heading at line 1984),
  Broker features, lines 2000-2008: outgoing messages are no longer retried after a timeout; they are
  retried when the client reconnects. The entry's wording names QoS greater than 1, while its
  rationale speaks of both PUBLISH and PUBREL; whether it was meant to cover QoS 1 *I could not
  establish* from the documentation. I found no later entry up to 2.0.22 (2025-07-11) that reintroduces a time-based retry: searched for
  retry, in-flight, PUBACK, order, queue and session, the 2.0.x entries found concern in-flight quota
  and queue limits (2.0.13, line 640; 2.0.17, line 489; 2.0.22, line 346), session expiry and bridges,
  and connection retries (2.0.9, line 825); none concerns resending messages on a live connection.
  Item 1 (`item1_broker_limits.md`, section 6) reads the same entry the same way and proposes a
  broker-only measurement of it.
- **In-flight accounting.** `mosquitto.conf(5)`, `max_inflight_messages`
  (`man_mosquitto-conf-5.txt:524-533`): the maximum number of outgoing QoS 1 or 2 messages in the process of being transmitted, counting those
  in handshakes and those being retried; default 20; 1 guarantees in-order delivery. Unlike
  `max_queued_messages` (`:596-604`: per client, default 1000), the entry does not say whether the
  count is per client. `max_queued_bytes` (`:584-595`): beyond the limit, messages are silently dropped.
  Read with the 1.5 entry: a delivery never acknowledged on a live connection stays counted as in flight
  until the connection ends — an inference from the definitions, not an observation.
- **Unknown PUBACKs.** `ChangeLog.txt`, 1.4.9 (heading at line 2291), lines 2307-2308: the broker copes
  with an unknown incoming PUBACK without disconnecting.
- **Out-of-order PUBACKs.** Nothing in these documents says how 2.0.22 treats a PUBACK that is out of
  receipt order. *I could not establish* it. Rule R3 below makes it moot.
- **Caveat.** The online manual page documents the current release (its `max_packet_size` entry states
  a default that applies from release 2.1 on, `man_mosquitto-conf-5.txt:574`), not 2.0.22 as such.
  Sizing *W* and the queue bound is item 1's question, not this one.

---

## 4. What paho-mqtt 2.1.0 does with manual acknowledgement [SOURCE; PROBED where marked]

**4.1 Turning it on.** `Client(..., manual_ack=False)` is the default (`client.py:742`), stored as a
plain attribute (`:751`); the docstring says the application then acknowledges after processing
(`:690-695`). `manual_ack_set(on)` only assigns that attribute (`:4178-4184`); its docstring, and the
same entry in the Paho documentation (`client.html`, `manual_ack_set`), require the caller to
acknowledge every message. The attribute is read on the network thread for every QoS 1 PUBLISH
(`:4149`) and unsynchronised, so it belongs in the constructor, before `connect_async`, not toggled
while connected. The controller today passes neither `manual_ack` nor `clean_session`
(`src/egw_controller/mqtt.py:73-76`), so paho acknowledges and the session is clean (`client.py:784-785`;
P:20).

**4.2 Where the automatic PUBACK goes, and what `ack()` does.** For a QoS 1 PUBLISH, paho calls
`on_message` and then, unless `manual_ack`, queues the PUBACK (`client.py:4147-4152`). For QoS 0 there
is no PUBACK (`:4144-4146`). `ack(mid, qos)` (`:4165-4176`): if `manual_ack` is off it returns success
and sends nothing [P:17]; for `qos == 1` it calls `_send_puback(mid)` → `_send_command_with_mid`
(`:3337-3339`, `:3454-3461`) → `_packet_queue` (`:3758-3795`); for `qos == 0` it sends nothing [P:19].
It never checks that `mid` was delivered, is outstanding, was already acknowledged, or belongs to the
current connection. Called while no connection exists, it returned `MQTT_ERR_NO_CONN` (4) and left the
packet queued [P:18]. In threaded mode `_packet_queue` returns success once the packet is queued
(`:3793-3795`), so a success code means "queued", never "written"; paho offers no callback for a
written PUBACK.

**4.3 Threading.** `on_message` runs on the network thread, under `_in_callback_mutex`
(`client.py:4498-4501`). `ack()` may be called from any thread: `_packet_queue` appends to the
`_out_packet` deque without a lock (`:3776`), writes one byte to the socket pair to wake the network
thread's `select` (`:3780-3784`), and — because `_thread` is set under `loop_start` — leaves the write
to the network thread (`:3788-3791`), which pops from the left (`:3163`). This is the same path
`publish()` takes (`:3444`), and the Paho documentation's `loop_start()` example publishes from the main
thread while the loop thread runs (index page, "loop_start() / loop_stop()"). I found no explicit
thread-safety statement for `ack()` in the Paho documentation, so its safety from the event-loop thread
rests on that shared path and on the deque, not on a documented guarantee. If the network thread is not
running, `_packet_queue` writes from the caller's thread instead (`:3788-3791`).

**4.4 Order.** `_out_packet` is FIFO (`client.py:812`, append `:3776`, `popleft` `:3163`): PUBACKs are
written in the order `ack()` was called. Paho neither reorders nor enforces receipt order.

**4.5 Unacknowledged messages across a reconnection.** Paho stores no received QoS 1 message
(`client.py:4147-4152`; only QoS 2 enters `_in_messages`, `:4153-4161`, and `:3741-3752` drops the
rest on reconnection). `reconnect()` closes the socket (`:1568`) and then **clears `_out_packet`**
(`:1577`): a PUBACK queued but not yet written is silently discarded, and one queued after that point
leaves on the new connection with its old identifier. On every close path I read, the socket-close
callback runs before that clear: `_sock_close` calls `on_socket_close` (`:1123-1135`, `:2859-2872`) on
the keep-alive paths (`:2151-2168`, `:3276-3297`), on a read or write error (`:3036-3052`), on the
client's own DISCONNECT (`:3222-3236`), on a server DISCONNECT (`:4033-4039`), and in `reconnect()`
itself (`:1568`, reached, for example, after the `select` error path `:1680-1683`, which returns
without closing). `on_disconnect` accompanies each of those closes except `reconnect()`'s own, so it
is not a reliable place to mark the end of a connection; `on_socket_close` is. `loop_forever` calls
`reconnect()` after each lost connection (`:2294-2330`). With a persistent session the broker resends
the unacknowledged deliveries with their original identifiers (SPEC §4.4) and the DUP flag, which paho
exposes as `message.dup` (`:4094`).

**4.6 `disconnect()` ends the network loop.** After `disconnect()` the state is `DISCONNECTING`, so
`loop_forever` returns instead of reconnecting (`client.py:2308-2316`); the Paho documentation says the
loop is also stopped by `disconnect()` (index page, "loop_start() / loop_stop()"). Forcing a redelivery
inside one process therefore needs `disconnect()`, then `loop_stop()`, then `connect_async()` and
`loop_start()` again — there is no single thread-safe "drop and reconnect" call. Queued PUBACKs are
written before the DISCONNECT that follows them (FIFO, `:3160-3236`).

**4.7 An exception in `on_message`.** `suppress_exceptions` is false by default (`client.py:877`; P:20),
so paho re-raises it (`:4498-4506`). It leaves `_handle_publish` before the automatic PUBACK
(`:4148-4152`), passes through `_loop` unguarded (`:1685-1688`) and `loop_forever` (`:2294-2297`), and
ends the network thread (`_thread_main`, `:4521-4525`) without calling `on_disconnect`. Observed for an
invalid-UTF-8 topic, which `message.topic` decodes and raises on [P:21].

---

## 5. Every path by which a delivered message ends without an outcome line today

"Under option 5" reads the ADR literally — PUBACK only after the outcome line, never for a delivery
without one, only on the delivering connection (ADR line 649) — with item 5 still open, so an
unacknowledged delivery simply stays unacknowledged. Classes: **GAP** — on a live connection, later
deliveries are acknowledged and this one is not; **HELD** — it occupies a broker in-flight slot until the
connection ends (section 3); **REDELIVERED** — the broker resends it at the next session resumption
(SPEC §4.4; ASSUMED for the deployed broker until item 1 is answered); **STALL** — the controller stops
receiving or stops consuming.

Today every QoS 1 delivery that reaches `on_message` and returns is acknowledged at callback return
(`client.py:4147-4152`), so each path below is, today, a message the broker has released.

| # | Path | Where | How it is reached (evidence) | Under option 5 as written |
|---|---|---|---|---|
| L1 | **Payload-driven exception swallowed by the consumer** | caught at `service.py:191-195`, counted by `metrics.py:143-160` | The decode stage catches only `UnicodeDecodeError`, `JSONDecodeError` and `NonStandardJSONConstantError` (`service.py:217-221`). A payload nested 200,000 deep raises `RecursionError`, a 5,000-digit integer a plain `ValueError` [P:12-13]; an unhashable `device_type` raises `TypeError` in `validator_for` (`schema.py:125`, reached from `schema.py:143`, `service.py:245`). Each ended with no line and `processing_errors` 1 [P:4-6]; the consumer went on to the next delivery [P:7]. Deterministic. | GAP, HELD, REDELIVERED at every resumption and failing again each time: a **poison** delivery. *W* of them fill the window: **STALL** (then the broker queues up to its bound and drops silently, section 3). Across restarts it returns until the session expires. |
| L2 | **Ditto-answer-driven exception swallowed by the consumer** | same | `get_twin` returns `response.json()` for any status below 400 (`ditto.py:333`, `:238-239`): a non-JSON 200 raised `JSONDecodeError` [P:8]; a JSON list raised `AttributeError` in `seed_from_twin` (`dedupe.py:65`) [P:9]. `_request` catches only `httpx.TransportError` (`ditto.py:233`), so other `httpx` errors escape too (SOURCE; not probed). May be transient or persistent. | GAP, HELD, REDELIVERED; if persistent, as L1 (poison, then STALL). |
| L3 | **Event-log write fails** | `EventLogger.log` (`events.py:112-119`) raises inside `_emit` before the counter moves (`service.py:414-415`) | An unwritable directory raised at `events.py:107` after the PATCH was applied: no line, `processing_errors` 1, one PATCH [P:10]. A failed **flush** keeps the line in Python's buffer and a later successful flush writes it [P:14-15]; `EventLogger` keeps the same handle (`events.py:104-105`), so the "failed" line can reach the file later, before the next line. | GAP, HELD, REDELIVERED; the redelivery finds the twin advanced and is `duplicate` (the N1 shape), and a late-flushed first line can add a second line for the identity. If the failure persists (disk full, bind mount gone) every delivery fails: **STALL** after *W*. |
| L4 | **Consumer cancelled** | `CancelledError` passes `except Exception` (`service.py:191`); `finally` counts it (`:196-197`); `src/CONTRACTS.md:284-286` | Only by a cancellation from outside the lifespan, which awaits the task (`app.py:162`). | At shutdown: REDELIVERED (the connection ends with the process). With the connection still up: **STALL** — nothing consumes, nothing is acknowledged, the window fills. |
| L5 | **No event loop in the callback** | `mqtt.py:190-193` | Not reachable through `start()`, which sets the loop (`mqtt.py:205`) before `connect_async` (`:206`) and `loop_start` (`:209`); `is_closed()` only if the loop closed before `bridge.stop()` joined the network thread (`app.py:159-160`, `mqtt.py:211-217`). | GAP, HELD, REDELIVERED. |
| L6 | **Exception escaping `on_message`** | `mqtt.py:195` (`message.topic`), `:199` (`call_soon_threadsafe` raises `RuntimeError` on a closed loop, `asyncio/base_events.py:838-840`, `:539-541`) | Paho re-raises and the network thread ends (section 4.7) [P:21]. `_connected` is cleared only in `on_disconnect`, a denied SUBACK or `stop()` (`mqtt.py:161`, `:180`, `:216`), so `/ready` keeps reporting MQTT connected (`app.py:84-86`) while nothing arrives. Reachability: `controller_today.md` section 6, path M. | **STALL** today and under option 5, until the process restarts; with a persistent session the broker would keep the delivery and resend it then. |
| L7 | **Queue overflow** | `service.py:162-169` | Not observed: `dropped` 0 in every sample of the three runs (ADR lines 422-428). | GAP, HELD, REDELIVERED. With one connection the queue cannot exceed *W*, if the broker honours *W* (item 1); after *k* reconnections inside one process, before the queue drains, it can hold (*k*+1)·*W*, because the broker resends every unacknowledged delivery (SPEC §4.4) while the originals are still queued. The ADR's condition 2*W* ≤ 9,999 (lines 656-662) covers one reconnection, not two. |
| L8 | **Behind the shutdown marker** | `service.py:199-201` with `:184-185`; `app.py:159-162`; `src/CONTRACTS.md:282-283` | `Queue.put` does not yield when the queue is not full (`asyncio/queues.py:110-135`), so the marker goes in ahead of callbacks already scheduled; observed: one delivery left queued after the consumer ended [P:11]. | REDELIVERED: the connection ends at the stop and no PUBACK may follow DISCONNECT (SPEC §3.14.4). The ADR's stop order replaces this path (ADR line 651). |
| L9 | **In hand-over at a kill** | `mqtt.py:199` → `service.py:154` | `controller_today.md` section 6, path C. | REDELIVERED (intended). |
| L10 | **Queued or in progress at a kill, or a drain cut short by the engine** | `service.py:150-152`; ADR section 2(f), 2(g) | r01/r02: at least 1,404 and 1,809 by arithmetic (ADR section 1.3). | REDELIVERED (intended); a death between `service.py:320` and `:414` gives the N1 case. |
| L11 | **After the Ditto 2xx, before the line** | `service.py:320` to `:414` | Death (L10) or the event write failing (L3). | As L3 or L10. |

Three further cases end **with** a line, or outside option 5, but bear on acknowledgement:

- **L12 — reconnection inside one process.** Deliveries of the ended connection are still queued; under
  the ADR's connection scoping (lines 761-767) each obtains a line and no PUBACK, the broker resends it,
  and the copy is recorded `duplicate` (ADR N2) — and the queue grows (L7).
- **L13 — QoS 0 deliveries.** Readiness accepts a granted QoS 0 (`mqtt.py:35`, `:149-150`), and a QoS 0
  delivery has no PUBACK at all (`client.py:4144-4146`; `ack(mid, 0)` sends nothing, P:19). Option 5
  protects none of them.
- **L14 — a line in the `unknown` bucket** (`events.py:74-82`). A line exists, so option 5 acknowledges
  it; the harness does not collect it (`controller_today.md` section 6, path K).

**What this shows.** On a live connection, option 5 left as written creates a gap on L1, L2, L3, L5 and
L7; it stalls on L4 (connection up), L6 and on a persistent L1, L2 or L3; it recovers, as intended, on
L4 (at shutdown), L8, L9, L10 and L11. L1 is the new hazard: today such a payload is silently lost;
under option 5 without a further rule it is resent for ever.

---

## 6. The acknowledgement order under option 5

**Receipt order is preserved end to end, by construction, when the consumer acknowledges.** Paho
dispatches PUBLISH packets one at a time on one thread (`client.py:4091-4152`); `call_soon_threadsafe`
appends to the loop's ready deque and the loop runs it in FIFO order (`mqtt.py:199`;
`asyncio/base_events.py:814-818`, `:838-847`, `:1970-1972`); `submit` appends with `put_nowait`
(`service.py:163`; `asyncio/queues.py:53-54`); the single consumer takes from the left
(`service.py:183`; `asyncio/queues.py:50-51`); paho writes PUBACKs in call order (section 4.4). If the
consumer requests each delivery's PUBACK right after its outcome line and before taking the next
delivery, the PUBACKs of one connection leave in receipt order, as MQTT-4.6.0-2 requires — **provided
no delivery is skipped**. (The asyncio anchors are CPython 3.12.3 in the analysis environment; the
image runs 3.12.13.)

**A skipped delivery is the whole problem.** Every path of section 5 that ends without a line either
ends the connection anyway (L4 at shutdown, L8-L10, and L11 when a death causes it: the broker
resends, no conformance question) or
leaves a live connection with a PUBLISH that is never answered (L1, L2, L3, L5, L7, and L4 with the
connection up).

**The ADR's two choices for that case (item 5):**

- *Hold an in-flight slot until the next session resumption.* Excluded, on three grounds. It leaves the
  duty of MQTT-4.3.2-2 and MQTT-4.5.0-2 unmet for the life of the connection, and whether acknowledging
  past it breaches MQTT-4.6.0-2 is unsettled (section 2). The broker does not resend on a live
  connection (section 3), so nothing recovers the delivery until the connection ends, and each held
  delivery removes one slot from the window: *W* of them stall the controller. And a deterministic
  failure (L1, a persistent L2 or L3) fails again at every resumption.
- *End the connection to force redelivery.* Required — but only safe once deterministic failures
  produce lines (R1 below); otherwise it becomes a reconnection loop on one poison delivery.

**With rule R3 the broker's treatment of out-of-order PUBACKs does not arise**: no PUBACK is ever sent,
on a connection, for a delivery received after one that was not acknowledged.

**Concurrency.** Any future concurrent consumer (the throughput option T2, ADR lines 1044-1054) would
complete deliveries out of receipt order and would need an acknowledgement sequencer that releases only
the completed prefix in receipt order (MQTT-4.6.0-2); this record does not assess it.

---

## 7. The rule option 5 needs

- **R1 — one line per delivery.** Every delivery the consumer takes ends in exactly one outcome line, a
  processing error included, with four exceptions only: the event log cannot be written; the consumer
  is cancelled; the process dies; an exception is raised after the Ditto 2xx for that delivery (where a
  `failed` line would misreport an applied twin). A failure while decoding or validating the payload is
  `rejected`; a failure in the Ditto exchange that is not a `DittoError` (non-JSON or non-object twin,
  other `httpx` errors) is `failed`, as a timeout is today; any other exception raised before the PATCH
  request is sent is `failed`, with the exception named in `error`. The unit is the delivery (each copy),
  not the identity: a redelivered copy obtains its own line, `duplicate` when the first copy reached the
  twin.
- **R2 — the acknowledgement point.** For a QoS 1 delivery, the PUBACK is requested exactly once, by the
  consumer, immediately after `EventLogger.log` for that delivery has returned without raising, and
  before the consumer takes the next delivery. Never for a QoS 0 delivery; never for a delivery with no
  line.
- **R3 — the order.** On each connection, the PUBACKs sent form a gap-free prefix of that connection's
  QoS 1 deliveries in receipt order. The first delivery that cannot be acknowledged — one of R1's
  exceptions, an overflow, a callback without an event loop — ends acknowledgement on that connection:
  no later PUBACK is requested on it, and the controller ends the connection, so that the broker resends
  every unacknowledged delivery at the next session resumption (SPEC §4.4). Two ways satisfy R3, and
  the choice is the student's, recorded and tested: (a) *in process* — stop taking deliveries,
  `disconnect()`, `loop_stop()`, `connect_async()`, `loop_start()` (section 4.6), with a back-off and
  `/ready` false meanwhile; (b) *fail fast* — stop taking deliveries, disconnect and exit non-zero,
  leaving the restart to the container policy (`restart: unless-stopped`, `compose.yaml:256`; what the
  engine does with a non-zero exit is not established from this item's sources), which reuses the path
  the finite proof exercises. A bounded in-process retry of the event write before giving up is
  compatible with R3.
- **R4 — connection scope.** Every delivery carries the identity of the connection that delivered it,
  stamped on the network thread in `on_message`. That identity advances in `on_socket_close`, which runs
  on every close path before paho clears its outgoing packets (section 4.5). Checking the identity and
  queuing the PUBACK happen under one lock that the close callback also takes, so no PUBACK for an ended
  connection can reach the next one. Deliveries of an ended connection are not processed when taken,
  and should be purged from the queue when the connection ends; the one in progress completes, obtains
  its line and is not acknowledged. The queue then holds at most one connection's unacknowledged
  deliveries (at most *W*), and N2's reconnection duplicates fall to at most one per lost connection —
  the delivery in progress.
- **R5 — a persistent cause is visible.** R3 repeated for one persistent cause (the event log
  unwritable) must end in a visible state, not a silent reconnection or restart loop: whichever of R3(a)
  or R3(b) is chosen records each occurrence and bounds the repetition, and `/ready` is false while the
  controller cannot record outcomes.
- **R6 — QoS 1 only.** The bridge is ready only when the SUBACK grants QoS 1; a QoS 0 grant would
  silently disable every acknowledgement (L13).

In one sentence: **every delivery ends in exactly one outcome line, a processing error included, before
its PUBACK; PUBACKs are sent in receipt order with no gap on any connection; and a delivery that cannot
have a line ends the connection, never the order.**

---

## 8. The code changes the rule implies

Line numbers at `35fe8bb`. Items marked **(ADR)** are already in ADR 0011's list ("What must change",
lines 888-916); the others are new.

1. **(ADR 1)** `mqtt.py:73-76` — `clean_session=False` and `manual_ack=True` in the constructor, not via
   `manual_ack_set` (section 4.1).
2. **(ADR 2, extended)** `mqtt.py:187-199` and `InboundMessage` (`service.py:81-87`) — carry `mid`,
   `qos`, `dup` and the connection identity, all stamped on the network thread.
3. **New (R4)** `MqttBridge` — a connection identity advanced in an `on_socket_close` handler under a
   lock; an `ack(delivery)` method that, under the same lock, returns without sending unless the identity
   is current, the QoS is 1 and acknowledgement is still open on this connection, then calls
   `client.ack(mid, 1)` and records the return code; a purge of the ended connection's deliveries,
   scheduled onto the event loop from the close handler (it runs before any delivery of the next
   connection, by the FIFO of `asyncio/base_events.py:1970-1972`).
4. **(ADR 3, made exact)** `service.py:182-197` — skip deliveries of an ended connection; request the
   PUBACK iff a line was written for this delivery (a flag set by `_emit` after `self._events.log`
   returns, `service.py:414`, not inferred from the absence of an exception); on a delivery that ends
   without a line, close acknowledgement on its connection and start R3's connection end.
5. **New (R1)** `service.py:212-229` — catch `ValueError` and `RecursionError` in the decode stage and
   record `rejected` (`UnicodeDecodeError`, `JSONDecodeError` and `NonStandardJSONConstantError`,
   `service.py:52`, are all `ValueError`s).
6. **New (R1)** `schema.py:123-130`, `:143` — a non-string `device_type` raises
   `SchemaValidationError`, so it is `rejected`.
7. **New (R1)** `ditto.py:323-333` and `dedupe.py:52-81` — a twin body that is not JSON, or not an
   object, raises `DittoError` (→ `failed`); `ditto.py:228-255` — the `httpx` errors that are not
   `TransportError` become a non-retried `DittoError`.
8. **New (R1)** `service.py:203-343` — a residual handler that turns any other exception raised before
   the PATCH request into a `failed` line naming the exception, and leaves the four exceptions of R1
   without a line.
9. **New (R1, R3)** `events.py:103-119` — a failed write must leave no data behind for a later flush
   (P:14-15): for example one unbuffered write per line on an append-only descriptor, or dropping the
   handle and its buffer on error. Whether a partial line can still result, and how the harness reads
   one, *I could not establish*; a regression test pins whichever behaviour is chosen.
10. **New (L6)** `mqtt.py:187-199` — no exception may leave `on_message`: catch it there and start R3's
    connection end, so the network thread never dies silently with `/ready` still true.
11. **New (R6)** `mqtt.py:35`, `:149-150` — readiness only on a granted QoS 1.
12. **(ADR 4, 5)** `service.py:161-169`, `mqtt.py:190-193` — no PUBACK for an overflow or a
    no-event-loop discard; under R3 each also ends acknowledgement on that connection.
13. **(ADR 6)** `app.py:159-164`, `service.py:199-201` — the ADR's stop order: the delivery in progress
    recorded and acknowledged, then DISCONNECT; paho writes the queued PUBACK before the DISCONNECT that
    follows it (section 4.6), and none can follow it (SPEC §3.14.4).
14. **(ADR 10)** lock the Python dependencies, so that everything in section 4 rests on a known paho
    version.

**Consequences for the ADR's text.** The "hold an in-flight slot" alternative (lines 649, 1116-1120,
974-976) is excluded. P2's "the broker delivers it again at the controller's next session resumption"
(lines 676-679) holds under R3 because the controller forces that resumption itself. The window
condition 2*W* ≤ 9,999 (lines 656-662) is not sufficient without the purge of change 3 (L7); with it
the queue holds at most *W* plus the stop marker. N2's reconnection clause (lines 704-707) falls to at
most one delivery per lost connection. Contract text: the meaning of `failed` widens to "not confirmed,
including a processing error before the PATCH" (`src/CONTRACTS.md` section 9 and
`service.py:11-12`), and `processing_errors` (`src/CONTRACTS.md:186-195`) then counts only R1's four
exceptions.

**Regression tests with fakes, added to the ADR's list (lines 958-980).** Each L1 and L2 trigger ends in
exactly one `rejected` or `failed` line and one PUBACK; an event-write failure (directory and flush)
ends in no line, no PUBACK for it or for anything after it on that connection, R3's connection end, and
no late line after recovery; a PUBACK requested after the connection identity advanced is not sent; the
purge leaves no delivery of an ended connection in the queue; an exception in `on_message` ends the
connection instead of the network thread; a QoS 0 grant keeps the bridge not ready; PUBACK order equals
receipt order across a mixed stream of accepted, rejected, duplicate and failed deliveries.

---

## 9. What I could not establish

- How Mosquitto 2.0.22 treats a PUBACK sent out of receipt order (section 3). Moot under R3.
- Whether the 1.5 entry on retries (no resend on a live connection) was meant for QoS 1 as well as
  QoS 2; whether `max_inflight_messages` is counted per client (section 3; item 1's question).
- Which reading of MQTT-4.6.0-2 applies to a delivery never acknowledged on a connection that is later
  closed (section 2).
- A documented thread-safety guarantee for `ack()` from another thread in the Paho documentation
  (section 4.3).
- The paho version and the CPython `io` behaviour inside the controller image (image unpinned;
  `src/Dockerfile:25`, `src/pyproject.toml:11`); every paho and CPython statement here is about the
  analysis environment.
- Whether any of L1, L2, L3, L5, L6 or L7 has occurred in a preserved run: they leave no line, and the
  error logs that would show them were not collected (ADR section 1.6).
- What a partial line left by a failed write looks like, and how the harness reads one (change 9).
- What the container engine does on a non-zero exit under `restart: unless-stopped`, for R3(b).

---

## 10. Consequence for option 5

**In, with conditions.** The acknowledgement order does not rule option 5 out: with one FIFO consumer
the order MQTT 3.1.1 requires comes by construction. The conditions are rule R1-R6 (section 7) and the
code changes of section 8, and one of the ADR's two choices for item 5 falls: a delivery without an
outcome line ends the connection (R3(a) or R3(b), the student's choice), never holds a slot. Without R1
option 5 would turn today's silently lost malformed payloads into poison deliveries that can stall the
controller; without R4 a late PUBACK can release an unprocessed message.

**No guest measurement is needed for this item.** It is closed by the specification, the paho source
and the controller source; R3 removes the one broker behaviour that the documentation leaves open, and
the rule is checked by regression tests with fakes before the finite proof.

---

## Sources and reproduction

- `gates/scripts/item3_anchors.sh` — prints every `file:line` range cited (controller at `35fe8bb`
  through the byte-identical WSL clone, paho 2.1.0) and the blob-by-blob identity check; read-only (`git
  ls-tree`, `git hash-object` without `-w`, `awk`). Output `gates/out/item3_anchors.out.txt`. Run from
  Git Bash: `bash item3_anchors.sh > ../out/item3_anchors.out.txt`.
- `gates/scripts/item3_probe.py` — runs the real `ControllerService.run()` loop with in-memory fakes, a
  real `DittoClient` over `httpx.MockTransport`, and paho's `Client` without a network; imports the
  repository with bytecode writing off; writes nothing to disk. Output `gates/out/item3_probe.out.txt`,
  tracebacks `gates/out/item3_probe.stderr.txt`. Run:
  `wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python -B <gates>/scripts/item3_probe.py'`.
- `/usr/lib/python3.12/asyncio/base_events.py` and `queues.py` (analysis environment) for the FIFO
  anchors of section 6.
- OASIS, *MQTT Version 3.1.1*, OASIS Standard, 29 October 2014: §§2.3.1, 3.1.2.4, 3.14.4, 4.1, 4.3.2,
  4.4, 4.5, 4.6.
- mosquitto.org: `mosquitto.conf(5)` (entries `max_inflight_messages`, `max_inflight_bytes`,
  `max_queued_messages`, `max_queued_bytes`); `ChangeLog.txt` (releases 1.4.9, 1.5, 2.0.13, 2.0.17,
  2.0.22).
- Eclipse Paho Python documentation: index page ("loop_start() / loop_stop()", "Callbacks") and
  `client.html` (`Client`, `ack`, `manual_ack_set`).
- Package D records: `adr-0011-controller-restart-recovery.md`, `decision_request.md`,
  `controller_today.md` (section 6).
