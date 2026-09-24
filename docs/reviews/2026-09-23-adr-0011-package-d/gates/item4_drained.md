# Package D, gate item 4: the `drained` precondition under option 5

- **Date:** 2026-09-21. **For:** the student, with the project manager's review. **Answers:** item 4 of `decision_request.md` (line 31) and "Open before the decision", item 6, of ADR 0011 (`adr-0011-controller-restart-recovery.md:1121-1125`).
- **Scope:** read only. No guest was started. Nothing in the repository, the raw runs, the attempts or `output_test` was changed, and no folder outside `gates/` was written. No git command that changes state was run. No threshold, window, deadline, load or rule is changed here.
- **Platform:** every timing below comes from an ARM64 guest emulated under QEMU/TCG on the x86-64 workstation. None of them is native, and none is a capacity.
- **Claim status:** as in ADR 0011. **PROVED** means an artefact line states it, or arithmetic on artefact lines gives it. **DOCUMENTED** means the official documentation states it; this marker is added here for documentation claims. **CONSISTENT-WITH** means the sources point that way without excluding an alternative. **ASSUMED** means it rests on a source reading or on protocol semantics. Where none of these applies, the text says *I could not establish*.

## 0. The answer

1. **Yes, `drained` must change if option 5 is chosen.** It does not stop being truthful whenever the backlog sits at the broker. It stops being truthful in two states:
   - **S1:** the controller's HTTP server answers while its MQTT session is not connected or not yet resumed.
   - **S2:** the controller holds deliveries that it will not acknowledge on the current connection.

   In either state `queue_depth` can read 0 and the counters can stay still while the broker holds messages for the session. `drained` would then report a quiet window that is not quiet (section 3).
2. **Mosquitto 2.0.22 exposes no figure for one session's queue.**
   - Every `$SYS` topic counts the whole broker, not one client or session.
   - The `$SYS` values are refreshed every `sys_interval` (10 s by default; the deployment does not set it), and the deployed ACL lets no user read them.
   - In 2.0.x, `mosquitto_ctrl` only drives the dynamic-security plugin, which the deployment does not load.
   - The broker log documents no per-session queue.

   **A truthful check of that session's queue therefore cannot be built from what the broker exposes** (section 4).
3. **The check has to come from the controller.**
   - `/metrics` gains three fields: `mqtt_subscribed`, `mqtt_connection` and `unacked`.
   - `drained` treats a reading as quiet only when `queue_depth`, `in_progress` and `unacked` are all 0, the subscription is granted and the accounting identity holds.
   - Across the whole window, `started_at`, `mqtt_connection`, `received`, the four outcome counters, `dropped` and `processing_errors` must not change.
   - The refusal of `processing_errors` or `dropped` above zero, which the ADR proposes on its own, is not sufficient: it misses S1 (section 5).
4. **Cost.**
   - No extra request per reading. Today's reading was measured at 0.035 s or less on average on an idle guest, 27 readings per 130 s window (PROVED).
   - `DRAIN_QUIET_S` (130 s), `DRAIN_STEP_S` (5 s) and `DRAIN_LIMIT_S` (900 s) are unchanged.
   - A call gets longer only in S1 and S2. There it waits for the broker's redelivery to be processed, or ends with the existing `STOP` at its limit (section 6).
5. **Which families.**
   - The condition changes for all nine families, for every session driver and for ADR 0011's own proof.
   - The outcome changes only after a restart, a reconnection or a reboot, or after a delivery that was left without an outcome line (section 7).
   - What remains **assumed** is that a broker with nothing in flight to a session that stays connected holds nothing queued for it. The documented meaning of the queue implies this; no broker figure shows it.

## 1. Code identity and what was read

- **Merged `dev`:** `35fe8bb` (merge of pull request #41, 2026-09-21 12:03:49 +0100). It was read with `git show` through the worktree `scratchpad/devwt`, which shares its objects with the Windows clone (`item4_callsites.out.txt:2-3`).
- **The WSL clone is not at the merged `dev`.** `/home/ruisth/egw-exec/repo` is a detached `HEAD` at `b7e0c83` (`item4_callsites.out.txt:4`), and the object `35fe8bb` is absent from it. This record did not fetch it, because a fetch changes the clone's refs.
  - Every anchor used below is the same at both commits. `git diff --stat b7e0c83 35fe8bb` is empty for the runbook and for `tools/session/nominal.sh` and `slice.sh` (`item4_callsites.out.txt:5-6`).
  - `tools/session/persistence.sh` differs only after its line 464.
  - `gate_health.sh` differs, and is cited at `35fe8bb`.
- **The deployed helper file** `~/egw-tcg/itest-helpers.sh` (sha256 `f94cff6f…b11b6a`, 2026-09-19) is generated from the runbook heredoc (`tools/session/regen_helpers.py`). It differs from the heredoc at `35fe8bb` (`docs/setup/qemu_integrated_gateway.md:610-878`) only by three comment lines, `:864-866` (`item4_callsites.out.txt:55-60`).
  - In the deployed file, `drained` is at `:44-61`, `pre` at `:173-181` and `finish` at `:193-201` (`item4_callsites.out.txt:61-65`).
  - The session drivers source exactly this file through `HOST_PRE` (`tools/session/guest_common.sh:51`, used by `hx`, `:57-62`).
- **Line references:** "runbook" means `docs/setup/qemu_integrated_gateway.md` at `35fe8bb`. Every other repository path is at `35fe8bb` too, unless stated otherwise.

## 2. `drained` today

- **What it does** (runbook `:653-670`). One reading is one `GET /metrics` through the tunnel, printed on one line (`_mline`, `:638-643`): `queue_depth`, `started_at`, `accepted`, `rejected`, `duplicate`, `failed`, `dropped`.
  - A reading with `queue_depth` other than 0, or with any value different from the previous reading, opens a new window (`:658-659`).
  - The helper returns 0 when every reading over `DRAIN_QUIET_S` (130 s by default) was quiet, with one reading every `DRAIN_STEP_S` (5 s by default). It gives up with `STOP` after `DRAIN_LIMIT_S` (900 s by default) (`:654`, `:662-667`).
  - An unreachable or non-JSON `/metrics` is a `STOP`, never a reading (`:657`).
- **What is claimed for it:** a temporary precaution, not proof that processing has finished (`:645-652`, `:994`, `:1002`).
- **Its argument rests on today's session settings.** The case "a message delivered to the controller during the last seconds of the window" is excluded only by two things (`:1004`, item (a); repeated at `:1300`):
  - the operator's rule that nothing publishes while `drained` runs;
  - **the bridge not asking the broker for a persistent session.**

  Option 5 removes the second.
- **It reads none of the progress counters that the deployed controller already serves.** `received`, `in_progress` and `processing_errors` exist (runbook `:1241` says the helpers do not read them yet; `src/egw_controller/metrics.py:162-184`).
  - The deployed controller returned all three on 2026-09-20: `/home/ruisth/egw-exec/attempts/20260920T232447Z_g2-gate-preconditions_attempt01/console/002-controller-endpoints.stdout.txt`, `/metrics` body (PROVED).
- **The contract names the blind spot.** The counters cannot show a message "held by the broker or in a socket buffer", nor one discarded by the MQTT callback (`src/CONTRACTS.md:228-233`).
- **Neither the harness nor the reconciliation helper has a drain of its own.** Neither contains `drained` or a quiet window (`item4_callsites.out.txt:53`). The harness is wrapped by `drained` from outside (runbook `:1032`, `:1124-1125`; `tools/session/nominal.sh:151`, `:219`).

## 3. What option 5 changes: when `queue_depth` reads 0 while the broker holds messages

**What the broker keeps for a persistent session.**
- MQTT 3.1.1 (OASIS Standard, section 3.1.2.4 "Clean Session", [MQTT-3.1.2-4], [MQTT-3.1.2-5]) makes two classes of message part of the server's session state for a client:
  - QoS 1 messages sent to the client and not yet completely acknowledged;
  - QoS 1 messages pending transmission to the client.

  Both are stored while the client is disconnected, and delivered when it resumes the session (DOCUMENTED).
- Section 4.4 ("Message delivery retry", [MQTT-4.4.0-1]) requires unacknowledged PUBLISH packets to be re-sent when the client reconnects with a persistent session. It states that this is the only case in which redelivery is required (DOCUMENTED).
- The Mosquitto change log, release 1.5 (2018-05-02), "Broker features" (`ChangeLog.txt:2000-2001` as retrieved), records that outgoing messages are no longer retried after a timeout, only on reconnection. The entry itself names QoS greater than 1, although its reasons concern PUBLISH and PUBREL generally.
  - No later entry up to 2.0.22 records a reversal: the change log contains no other retry or resend entry for broker deliveries.
  - So a delivery the controller never acknowledges stays with the broker, occupying an in-flight slot, until the next session resumption. This is **CONSISTENT-WITH** the documentation and has not been tested on this broker. It also answers ADR 0011's open question at `:781-782` as far as the documentation goes.

**Two limits decide how much can wait unseen** (`mosquitto.conf(5)`, "General Options"):
- `max_inflight_messages`: outgoing QoS 1/2 messages in transmission at once. The default is 20.
- `max_queued_messages`: messages held per client above those in flight. The default is 1,000.
- The deployed `src/deployment/mosquitto/config/mosquitto.conf:1-56` sets neither.
- ADR 0011 intends to set both explicitly (code item 8, `:908-910`).

**Scope of the premise.** A backlog larger than the in-flight window W does **not** by itself make `drained` wrong.
- While the controller is connected and working, it holds up to W deliveries, so `queue_depth + in_progress > 0` and the window never becomes quiet.
- An empty queue between one acknowledgement and the broker's next send is transient. The counters move on the next reading.

The false quiet window needs one of two states.

**S1: the controller answers HTTP but is not connected to the broker, or has not resumed its session.**
- `/metrics` is served by the same process whether or not MQTT is up (`src/egw_controller/app.py:119-127`). MQTT readiness appears only in `/ready` (`:82-94`, via `bridge.connected`, `:169`).
- The bridge connects asynchronously at start-up (`src/egw_controller/mqtt.py:203-209`) and reconnects after a loss with a delay of 1 to 30 s (`:29-30`, `:82-84`). It is "ready" only once the SUBACK grants the subscription (`:149-152`); the flag is cleared on disconnect (`:180`).
- Under option 5, everything published since the disconnection waits at the broker for the session, up to the queue bound.
- Today's `drained` never calls `/ready`. `pre` calls `wait_ready` once, before the window (`:788`). `finish`, test 6's `after` line and the drivers' post-run drains call `drained` without it (`:804`, `:1125`; `nominal.sh:219`).
- So a restarted, rebooted or disconnected controller whose connection takes 130 s or more to come back would pass `drained` with an empty queue while the broker holds the backlog (ASSUMED from the source; not observed).
- Today this case is harmless, because a clean session leaves nothing at the broker (ADR 0011, section 2(e)).

**S2: the controller is connected and holds deliveries it will not acknowledge on this connection.**
- Under option 5 no PUBACK is sent for three kinds of delivery (ADR 0011, "acknowledgement" row of the behaviour table, `:649`; P2, `:676-679`):
  - a delivery dropped on overflow (`src/egw_controller/service.py:161-169`);
  - one whose processing ended without an outcome line (`service.py:188-197`; `processing_errors`, `metrics.py:159-160`);
  - one discarded because the bridge has no event loop (`mqtt.py:190-193`, which counts nothing).
- Each such delivery stays in flight at the broker for as long as the connection lasts (above), while `queue_depth` and `in_progress` return to 0 and the counters stop moving.
- If such deliveries fill the in-flight window, the broker sends nothing more, and everything queued behind them waits unseen. With the defaults above that is 20 stuck and up to 1,000 queued.
- If item 5 of the ADR chooses "the delivery holds an in-flight slot until the next session resumption" (`:1116-1120`), S2 is not an accident but the designed state.

**What it would do to a later run.** A false quiet window lets the next `before` snapshot be taken while the broker still holds deliveries for the controller's session. They reach the controller at the next resumption, possibly inside a later family, which is the ADR's "contamination across runs" (`:779-790`).
- The runbook argues that a miss of the controller's *own* backlog gives a false `MISMATCH` and never a false `OK` (`:994`).
- **Whether the same holds for deliveries redelivered by the broker I could not establish.** It depends on the `run_id` and `seq` rule (`dedupe.py:91-113`) and on which devices the later family uses, and it was not traced case by case here.

## 4. What Mosquitto 2.0.22 exposes

**Version caveat.**
- The web pages at mosquitto.org now document 2.1.x. The change log retrieved on 2026-09-21 starts at 2.1.2 (2026-02-09), and `mosquitto(8)` marks some options as available only from version 2.1.
- The deployed broker is `eclipse-mosquitto:2.0.22` (`src/deployment/images.lock.env:39`, cited by ADR 0011 at `:666`).
- Below, a claim about 2.0.22 is made only where the change log or the 2.0.x wording supports it.
- The local copy of the `mosquitto.conf(5)` source at `scratchpad/mosq-src/mosquitto.conf.5.xml` carries the same text for `sys_interval`, `max_inflight_messages`, `max_queued_messages`, `max_queued_bytes`, `acl_file` and `log_dest` (`:1033`, `:572`, `:676`, `:657`, `:113-118`, `:454-474`). It is kept in the package, byte for byte and with the same line numbers, as `gates/sources/mosquitto.conf.5-2.0.22.xml` (sha256 in `gates/sources/SHA256SUMS.txt`).
  - That copy was fetched on 2026-09-18 by an earlier session, and this note did not re-verify its provenance; `gates/item1_broker_limits.md`, section 1, identifies it by its sha256 with `man/mosquitto.conf.5.xml` at tag `v2.0.22`. Its change log starts at 2.0.22.
  - It is 2.0.x wording: it lacks the 2.1-only `enable_control_api` option and the seconds unit that 2.1.0 added to `persistent_client_expiration` (`ChangeLog.txt:143`).
- Retrieved copies and their hashes are in `gates/sources/SHA256SUMS.txt`.

| Channel | What it gives | Per client or session? | Update | In 2.0.22? | Usable as a drain check? |
|---|---|---|---|---|---|
| `$SYS/broker/store/messages/count` (formerly `messages/stored`) | messages currently in the message store; the documentation says this *includes* retained messages and messages queued for durable clients (`mosquitto(8)`, "Broker Status") | **no**, broker-wide | every `sys_interval` | yes, added in 1.5 (`ChangeLog.txt:2024`) | no (below) |
| `$SYS/broker/clients/disconnected` | persistent clients registered but not connected (ibid.) | no, a global count | as above | yes, renamed in 1.4 (`:2510-2511`) | the controller's own connection state is better |
| `$SYS/broker/publish/messages/dropped` | PUBLISH messages dropped because of in-flight or queue limits (ibid.) | no, global and cumulative | as above | the `publish/messages/+` family exists in 2.0.x (fix in 2.0.4, `:991-992`) | not a drain check; see 5.5 |
| `$SYS/broker/packet/out/count` | packets queued for delivery, summed over all clients (ibid.) | no | as above | *I could not establish* it: no change-log entry records its addition | no: packets waiting for the socket, not session messages |
| `mosquitto_ctrl` | in 2.0.x, the `dynsec` module only, plus external modules (`mosquitto_ctrl(1)`, "Modules") | not session state | on demand | the binary is in the image; the deployment loads no dynamic-security plugin (`mosquitto.conf:25-27` uses `password_file` and `acl_file`) | no |
| `$CONTROL/broker/v1` | `listPlugins` only, disabled by default (`ChangeLog.txt:180-182`; `mosquitto.conf(5)`, `enable_control_api`) | no | on demand | **no**, 2.1.0 | no |
| broker log | the types `debug`, `error`, `warning`, `notice`, `information`, `subscribe`, `unsubscribe`, `websockets`; connection entries with `connection_messages` (`mosquitto.conf(5)`, `log_type`, `connection_messages`) | its content is not documented in the manual; the change log records two kinds of line (item 4 below) | as events happen | yes | no (below) |
| MQTT CONNACK "Session Present" | whether a session existed, not its size (MQTT 3.1.1, section 3.2.2.2, [MQTT-3.2.2-2]); paho passes it to `on_connect` (`paho/mqtt/client.py:225-228`, `:3928`) | per session | per connection | yes | not a size |

**Why none of these can give a truthful check of the controller's session queue:**
1. **No per-client figure.** None of the `$SYS` topics listed in the current documentation is per client or per session.
   - No change-log entry from 2.0.0 to 2.1.2 adds or removes one.
   - The one count that mentions queues for durable clients is broker-wide, and "includes retained messages and messages queued for durable clients" is not "equals".
   - The documentation does not say whether it counts messages in flight to a *connected* durable client, or whether the broker's own `$SYS` messages count in it. **I could not establish** either.
   - So even in a deployment where the controller is the only durable client, no reading of it can be defined as "the controller's session is empty".
   - Under option 5 the controller would be the only durable client here (ASSUMED from the sources that follow). The simulator uses paho's default clean session (`src/egw_simulator/publisher.py:214-218`; `paho/mqtt/client.py:784-785`). The ACL probe's clients pass no option that disables the clean session (`src/deployment/scripts/probe-acl.sh:124`, `:133`), and the broker logged each of them with a `c1` field (`/home/ruisth/egw-tcg/itest/itest-acl-20260918T221558Z/broker.txt:1-2`, `:5`, `:7`, `:9`, `:11`).
2. **Staleness.**
   - `$SYS` topics other than static ones are refreshed every `sys_interval` seconds (`mosquitto(8)`, "Broker Status"). The default is 10 s (`mosquitto.conf(5)`, `sys_interval`), and the deployed configuration does not set it (`mosquitto.conf:1-56`).
   - Release 0.11 records that `$SYS` messages are republished only when their value changes (`ChangeLog.txt:3404`).
   - Until 2.1.0, the refresh was aligned to the broker's start time (`:134-136`).
   - Whether a new subscriber receives the current value at once (retained) is not documented. **I could not establish** it.
3. **Access.**
   - With `acl_file` set, only the topics listed are accessible (`mosquitto.conf(5)`, `acl_file`).
   - The deployed ACL grants `write c2dt/#` to `egw-simulator` and `read c2dt/#` to `egw-controller`, and nothing else (`src/deployment/mosquitto/config/acl:9-14`).
   - A wildcard filter never matches a `$` topic (MQTT 3.1.1, section 4.7.2, [MQTT-4.7.2-1]).
   - Reading `$SYS` would therefore need a new ACL grant. That changes the configuration test 9(d)/(e) proves (runbook `:1209-1212`) and adds an item to the configuration identity that ADR 0011 records (`:769-778`).
4. **The broker log.**
   - The deployed configuration logs `error`, `warning`, `notice`, `information`, `subscribe` and `unsubscribe`, with connection messages, to stdout (`mosquitto.conf:47-56`).
   - The manual does not describe the content of any log message. The change log records two kinds of line, below.
   - One preserved log shows 2.0.22 printing a `c1` field for each connection (`broker.txt:1-2` above). Read as the clean-session flag, it would identify a persistent session, not its size. That reading is **CONSISTENT-WITH**: the manual does not define the field, but the change log records, in release 1.2, that the connect line shows the client's clean-session and keepalive status (`ChangeLog.txt:2789` heading, `:2815-2816`), and the keepalive field of the controller's connections, `k60` (`gates/item2_r02_guest_evidence.md`, sections 4 and 5), matches the controller's `_KEEPALIVE_S = 60` (`src/egw_controller/mqtt.py:31`).
   - Per-message delivery and acknowledgement would appear, if anywhere, at `debug`, whose content is not documented either. Debug output is never published on `$SYS` log topics (`mosquitto.conf(5)`, `log_dest`).
   - Enabling `debug` would also change the broker's configuration during measured windows, at an unmeasured cost for every message.
   - The change log records, since release 1.3, that the broker logs when a client's outgoing messages begin to drop off the end of its queue (`ChangeLog.txt:2679-2680`). Whether 2.0.22 still does, at which log type, and whether the deployed log types (`mosquitto.conf:48-53`) include it: **I could not establish** it (not established). The broker log of the broker measurement (`gates/item1_broker_limits.md`, section 7) answers it.

**Conclusion (DOCUMENTED, for 2.0.22 as far as the change log attests):** a truthful check of the broker's queue for the session `egw-controller-egw-01` cannot be built from what Mosquitto 2.0.22 exposes.

## 5. The change `drained` needs

**Principle.** Under option 5, everything the broker has sent to the controller stays unacknowledged until its outcome line is written (ADR 0011, P1 and P2).
- The controller can therefore count what it has received and not yet acknowledged, and it can report whether its session is connected.
- The one part it cannot see is what the broker has queued and not yet sent. By the documented definition that part is the overflow of the in-flight window: `max_queued_messages` holds, per client, the messages beyond those currently in flight (`mosquitto.conf(5)`, `max_queued_messages`).
- So when the controller has been connected throughout, has nothing unacknowledged and receives nothing for a full window, the documentation leaves no reason for the broker to hold anything for it. This is **CONSISTENT-WITH** the documentation, not shown by a figure (section 4).
- The change therefore has two parts: one in the controller, one in the helper.

### 5.1 Controller: three additive `/metrics` fields

These fields are not among ADR 0011's ten code items (`:888-916`). Like ADR 0010's counters, each is scoped to one process, and its absence is never read as zero (`src/CONTRACTS.md:170-175`).

| Field | Type | Meaning |
|---|---|---|
| `mqtt_subscribed` | boolean | the subscription is granted on the current connection: today's `bridge.connected` (`mqtt.py:149-152`, `:180`, `:216`, `:219-221`), which `/metrics` does not carry |
| `mqtt_connection` | integer, cumulative | the number of successful CONNACKs this process has received, which identifies the current connection |
| `unacked` | integer, gauge | QoS 1 deliveries handed to the client on the current connection for which no PUBACK has been sent |

**How `unacked` has to be counted:**
- **Where:** at `on_message` (`mqtt.py:187-199`), not at `submit`. It then covers the hand-over to the event loop and the no-event-loop discard, which `received` cannot see (`src/CONTRACTS.md:228-233`, `:240-245`).
- **Decrease:** when `ack()` is issued for that delivery. It goes back to 0 on each new connection, because the earlier connection's deliveries are then the broker's to resend ([MQTT-4.4.0-1]; ADR 0011, "Duplicates", `:761-767`).
- **Who counts it:** the controller itself. paho 2.1.0 keeps no such record under manual acknowledgement: for QoS 1 it calls `on_message` and returns without a PUBACK and without storing the message (`/home/ruisth/egw-exec/venv/lib/python3.12/site-packages/paho/mqtt/client.py:4147-4150`). Only QoS 2 is kept (`:4153-4159`).
- **Thread rule:** it must be kept by the bridge, with its own synchronisation, because nothing may update `MetricsCounters` from the MQTT network thread (`metrics.py:50-55`). It is therefore **not** a term of the accounting identity (`src/CONTRACTS.md:215-217`).

The change also needs:
- contract text in `src/CONTRACTS.md` section 5, "Progress counters";
- the one-respect amendment of ADR 0010 that ADR 0011 already lists (`:936-942`);
- tests with fakes: `unacked` across a reconnection, during hand-over, on the no-event-loop discard, on overflow and on a failed event write.

### 5.2 Helper: runbook 6.1, `_mline` and `drained` (regenerated by `tools/session/regen_helpers.py`)

1. **`_mline` prints one line**, in this order: `queue_depth in_progress unacked mqtt_subscribed started_at mqtt_connection received accepted rejected duplicate failed dropped processing_errors`.
   - It fails, with no reading, when any of these is missing or of the wrong type. It uses the same rule as `metrics` (`:689`) and the contract (`src/CONTRACTS.md:170-175`).
   - It evaluates the accounting identity from the same response, in the contract's order (`src/CONTRACTS.md:220-226`).
2. **A reading is quiet** only if `queue_depth == 0`, `in_progress == 0`, `unacked == 0`, `mqtt_subscribed` is true and the identity holds.
   - A reading whose identity fails means "do not trust this reading" (`:224-226`). It opens a new window and is not a `STOP`.
3. **The part that must not change across the window:** `started_at mqtt_connection received accepted rejected duplicate failed dropped processing_errors`. Any difference opens a new window, as a new `started_at` does today (`:658-659`).
4. **Unchanged:**
   - `DRAIN_QUIET_S` 130 s, or 490 s where a first-contact message may be in progress (`:651`);
   - `DRAIN_STEP_S` 5 s and `DRAIN_LIMIT_S` 900 s (`:654`), and the 1,500 s set in `nominal.sh:219`;
   - the start of both output lines, `drained: queue_depth 0 and identical counters on … readings over … s` and `STOP: drained: no quiet window of … s within … s`. `nominal.sh:206-214` and `tools/session/README.md:71` parse the `STOP` line.
5. **The refusal of `processing_errors` or `dropped` above zero** (ADR 0011, `:784-786`, `:972-973`, `:1121-1125`):
   - With `unacked`, it is **not needed** for truthfulness. A delivery left without an outcome line keeps `unacked` above 0 while its connection lasts, so the window never becomes quiet. After a reconnection it is redelivered and counted anew.
   - Without `unacked`, the refusal together with `mqtt_subscribed` is the fallback. It still misses the no-event-loop discard, which moves no counter (`mqtt.py:190-193`). It is truthful only on the source reading that this discard happens only while the process is ending (the loop is attached before paho's network thread starts, `mqtt.py:203-209`; ASSUMED).
   - **On its own, as the ADR words it, the refusal is not sufficient:** it misses S1 entirely.
6. **`/ready` is not a good substitute for `mqtt_subscribed`.** Each `/ready` call awaits a Ditto request (`app.py:85`; `ditto.py:347-359`). Adding it to `drained` would make Ditto's reachability part of the drain and would put one Ditto request per reading on the controller's event loop.

### 5.3 Text that changes with it

- Runbook `:994-1004`: item (a)'s reliance on "the bridge not asking the broker for a persistent session" is replaced by the three fields and by the residual assumption stated in 5.5. ADR 0011 already lists this paragraph (`:943-947`).
- The same point in Appendix B, item 21 (`:1300`).
- The helper table row (`:890`).
- Section 9, item 7 (`:1241`): "the helpers do not read the new fields" ceases to hold.

### 5.4 Regression tests (fakes, before any guest run)

`drained` must refuse a quiet window in each of these cases:
- `mqtt_subscribed` false throughout;
- `unacked` above 0 with the queue empty;
- a change of `mqtt_connection`;
- a failed identity;
- a reading without the new fields.

It must also keep both output prefixes.

### 5.5 What the changed `drained` still does not show

- **Messages queued at the broker and never sent to a connected controller with nothing in flight.** That none are held rests on the documented meaning of the queue (above), not on a figure. It is **ASSUMED**; a bounded check is described in section 9.
- **Messages the broker discarded** beyond its queue bound (ADR 0011, N4). These are losses, not pending work.
  - `accounted` shows them after a run, identity by identity (runbook `:704-778`).
  - The broker's own global count is `$SYS/broker/publish/messages/dropped` (section 4). Reading it before and after each run would need the ACL grant of section 4, item 3. It is a run-level evidence item, not a drain check, and a separate decision.
- **The in-progress bound** (`:1004`, item (b)) and **the work inside Ditto or MongoDB after the 2xx** (item (c)). Both are unchanged.

## 6. What it costs per call under TCG

**Controller-side variant (recommended)**
- **Readings:** no additional request per reading. One `GET /metrics` per `DRAIN_STEP_S`, as today, is about 27 readings per 130 s window.
- **Measured reading time (PROVED):**
  - The G2 persistence `quiesce` step (`drained` alone, idle controller) took 130.957 s (`/home/ruisth/egw-exec/attempts/20260920T233212Z_g2-twin-persistence-restart_attempt01/commands.jsonl:1`). It reported 27 readings (`console/001-quiesce.stdout.txt:1`).
  - Taking out the 26 sleeps of 5 s, the 27 readings and the host preamble took 0.957 s or less. That is at most 0.035 s per reading on average.
  - Single `GET /metrics` steps of the same attempt took 0.023 s and 0.129 s (`commands.jsonl:2`, `:10`).
  - Every other preserved quiet window agrees within the whole-second resolution of the span it prints: 27 readings over 131 to 132 s (`gates/item4_drain_timings.out.txt:3-17`).
- **The extended response:** three more fields in the same response, whose cost is ASSUMED to be of the same order and has not been measured.
- **Controller path:** one counter update per delivery and one per acknowledgement, unmeasured. This adds to option 5's unmeasured `ack` call (ADR 0011, N6).
- **Length of one call:**
  - When the controller is connected and holds nothing, as long as today: 130 s at least.
  - In S1 and S2 it cannot end quiet until the broker's held deliveries have been redelivered and processed. If they are never acknowledged on that connection, it ends with `STOP` at `DRAIN_LIMIT_S`: up to 900 s (1,500 s in `nominal.sh`), and the precondition is then refused.
  - For scale, the one preserved drain after a backlog took 464.875 s after `nominal-r01`, with the backlog held in the controller (`20260919T195827Z_nominal-instrumentation-120-600_attempt01/commands.jsonl:5`).
  - Whether test 6's post-run drain would fit within 900 s under option 5: **I could not establish** it.

**`/ready` per reading (not recommended)**
- One more request per reading, each with a Ditto probe.
- The preserved upper bound is 0.468 s for `/health`, `/ready` and `/metrics` together on an idle stack (`20260920T232447Z_g2-gate-preconditions_attempt01/commands.jsonl:2`). That is 12.6 s or less over 27 readings when idle; under load it is unmeasured.

**`$SYS` read per reading (not truthful, section 4)**
- It needs an ACL grant, plus, per reading, an `ssh` to the guest and one `docker compose exec` of a Mosquitto client in the broker container.
- The preserved analogues:
  - one `ssh` step with a trivial command took 0.697 s (`20260920T233212Z_…/commands.jsonl:5`);
  - four back-to-back `docker compose exec … mosquitto_pub` calls with nothing between them (`src/deployment/scripts/probe-acl.sh:131-136`, `:176-182`) took 12 to 14 s by the probe's whole-second clock (`itest-acl-20260918T221558Z/verdict.txt:4`, `p1_start=8595`, `p4_end=8608`). That is 3.0 to 3.5 s each. The broker logged their connections 2.893, 3.654 and 3.212 s apart (`broker.txt:5`, `:7`, `:9`, `:11`).
- So about 4 s per reading: an estimate from two different steps, not a measurement of a `$SYS` read.
- At the unchanged 5 s step, that would cut the readings per window from about 27 to about 14 or 15. Each value could also be up to `sys_interval` (10 s) old.

## 7. Which families' preconditions change

The condition changes wherever `drained` runs, which means all nine families. The table says where the **outcome** can also change: where the new check would refuse, or wait longer, when today's would pass. Today's check passes in S1 and S2.

| Family or step | Call site (runbook unless stated) | Through | Where the outcome can change |
|---|---|---|---|
| First flow, 6.2 to 6.4 | `:908` (`pre`), `:920` | `pre`, direct | only in S1 or S2 |
| Test 1, three ad-hoc runs | `:1019` | `run_test` → `pre` (`:841`, `:788`) and `sim_post` → `post` → `finish` (`:827`, `:815`, `:804`) | only in S1 or S2 |
| Test 1, harness run | `:1032` | direct | only in S1 or S2 |
| Test 2 | `:1044` | `run_test` | only in S1 or S2 |
| Test 3 | `:1064` | `run_test` | only in S1 or S2 |
| Test 4 | `:1084`, `:1099` (`run_test`); `:1086`, `:1087` (direct, around the replay) | both | only in S1 or S2; the replay's copies all end in outcome lines, then PUBACKs (ASSUMED under option 5) |
| Test 5 | `:1107` | `run_test` | only in S1 or S2; the controller stays connected while the simulator drops out |
| **Test 6** | `:1124` (before), **`:1125` (after the restart)** | direct | **yes**: the new process must be subscribed, with nothing unacknowledged and the redelivered backlog processed, before `after` is taken (S1, then the redelivery) |
| Test 7, MongoDB and Ditto | `:1163`, `:1179` (`pre`); `finish` through `sim_post` | `pre`, `finish` | only in S2, if a fault leaves a delivery without an outcome line; a `failed` outcome has a line (`:1167`) |
| **Test 8** | **`:1186` (before the reboot)**; `:1192` (`run_test` after it) | direct, `run_test` | **yes**: the drain before the reboot is what ensures that the broker's persisted session (`mosquitto.conf:33-35`) holds nothing to redeliver after it; the snapshot after the reboot (`:1191`) runs without `drained` |
| Test 9 | `:1212` | direct | only in S1 or S2; the probe's topic `c2dt/acl-probe/<tag>` (`verdict.txt:1`) does not match the controller's filter `c2dt/+/+/telemetry` (`src/egw_controller/config.py:66`) |
| G2 slice | `tools/session/slice.sh:48` (`pre`), `:62` | `pre`, direct | only in S1 or S2 |
| **G2 persistence** | `tools/session/persistence.sh:385` | direct | **yes** for the family that follows: `compose down`/`up` restarts the broker and the controller together |
| Nominal and pilot | `tools/session/nominal.sh:151`, `:219` | direct | only in S1 or S2; the post-run drain is an observation after the sealed window (`:198-232`) |
| **ADR 0011's proof** | ADR `:809` | direct | **yes** (below) |

**The proof.** ADR 0011's proof judges its result after `drained` (`:809`). R1 refutes the option when a valid identity has no outcome line "after a completed drain" (`:858-859`), and a `drained` that reaches its limit makes the attempt inconclusive (`:869-871`).
- With today's `drained`, S1 or S2 after the SIGKILL could produce a false quiet window, and the missing identities would then be recorded as a refutation that is "never re-run away" (`:867`).
- With the change, the same state ends as inconclusive.
- **The change therefore belongs before the proof, not after it.**

**Not `drained`, but the same blind spot under option 5:**
- `gate_health.sh`'s counter baseline, one reading of zeros for a fresh process (`tools/session/gate_health.sh:264-315`), and its remedy of a restart (`:320`);
- the `queue_depth` check in `accounted` (runbook `:759-760`);
- `delta`'s check of `queue_depth` in the `to` snapshot (`src/egw_experiments/itest_reconcile.py:563-568`).

Each would need the same fields. This record does not assess them further.

## 8. Consequence for option 5

**Option 5 stays in, on five conditions:**
1. `mqtt_subscribed`, `mqtt_connection` and `unacked` are added to option 5's code change, with their contract text and tests (5.1).
2. `_mline` and `drained` are changed as in 5.2, with no threshold, window, limit or message prefix changed, before the proof run.
3. Runbook `:994-1004` and `:1300` are restated (5.3).
4. Item 5's choice between forcing a disconnection and holding the slot is made knowing that holding the slot makes every `drained` end with `STOP` until a session resumption.
5. The residual assumption of 5.5 is stated in the record.

Without the change, option 5 leaves `drained` reporting quiet windows that are not quiet in S1 and S2. The proof itself relies on `drained`.

## 9. The one bounded guest check (optional; not needed to decide)

- **Question:** with nothing published, does a controller that resumes its persistent session, after the changed `drained` has returned quiet, receive anything the broker still held for it? This tests the residual assumption of 5.5. It is an engineering diagnostic, not a G3 run.
- **When:** at the end of ADR 0011's proof run, after the changed `drained` has returned quiet and the post-drain fetch has been taken. It adds one controller restart under the same client id and persistent session, and one more `drained`.
- **What it records:**
  - both `drained` transcripts, with every field of every reading;
  - the broker's connection lines (`c0` expected, on the CONSISTENT-WITH reading of the `c` field in section 4, item 4);
  - the controller's "MQTT subscription granted" line (`mqtt.py:151-152`);
  - the new process's `/metrics` after its quiet window;
  - a second post-drain fetch.
- **Guest time:** about 2.5 to 3 minutes. The restart commands took 20.8 to 22.7 s (ADR 0011, [F:R01.0, R02.0]; `pkgD/v2/out/adr0011_figures.out.txt:6`, `:57`: 22.704 s in r01 and 20.790 s in r02); add one 130 s window, the `wait_ready` and the fetch. This is a planning figure, not a bound.
- **Ceiling.** Where the helpers set no limit, the figure is a stop rule chosen by design, not a measured duration. Reaching any limit or stop rule ends the check:
  - the restart command: the `stop_grace_period` recorded under C6, plus 5 minutes (stop rule);
  - `wait_ready`: its default limit of 60 s (runbook `:627`), checked only after a request of up to 30 s (`:629`) and a 5 s pause (`:632`), so at most about 95 s;
  - `drained`: `DRAIN_LIMIT_S` = 900 s (runbook `:654`), checked only after a reading of up to 30 s (`_mline`, `:639`) and a 5 s step (`:667-668`), so at most about 935 s;
  - one `/metrics` reading: at most 30 s (`metrics`, `:688`);
  - the second post-drain fetch: 5 minutes (stop rule; `fetch` has no limit of its own, `:672`).

  The check therefore ends within the `stop_grace_period` plus 1,660 s, about 28 minutes plus that grace period. It adds to the proof's own planning ceiling. *(2026-09-23: ADR 0011, "The finite proof", adopts this figure as the extension's ceiling; an earlier draft of the ADR gave 20 minutes, which the helpers' own limits above can exceed with no fault at all.)*
- **What refutes the residual assumption:** nothing is published, yet the new process receives any delivery (`received > 0`), or an identity gains its first outcome line after the first quiet window was declared.
- **Inconclusive** (the attempt is kept as incomplete and no result is claimed): the restart is not shown (the controller's `started_at` unchanged, or the restart command fails or reaches its stop rule); `wait_ready` or `drained` ends with `STOP` and no reading of the new process shows `received` > 0; a reading, the `/metrics` record or the fetch fails or reaches its stop rule; the tunnel fails. A refuting result observed before the check stopped stands.
- **Caveat:** it changes the proof's plan, so it is the student's decision.

## 10. What I could not establish

- Which `$SYS` topics 2.0.22 publishes beyond those the change log attests (for example `packet/out/*` and `mqtt/*`).
- Whether `$SYS` values reach a new subscriber at once.
- Whether `store/messages/count` counts messages in flight to a connected durable client, or the broker's own `$SYS` messages.
- Whether Mosquitto 2.0.22 sends a queued message as soon as an in-flight slot frees for a connected client. Only the documented definition of the queue supports this.
- Whether 2.0.22 still logs, as the change log records since release 1.3 (`ChangeLog.txt:2679-2680`), when a client's outgoing messages begin to drop off the end of its queue; at which log type; and whether the deployed log types (`mosquitto.conf:48-53`) include it.
- What the extended `/metrics` reading, `unacked`, a `$SYS` read or a `/ready` per reading costs under load.
- Whether test 6's post-run drain fits within 900 s under option 5.
- Whether a false quiet window under option 5 can only produce a false `MISMATCH`, never a false `OK`.

## Sources and reproduction

- **Scripts (read-only), in `gates/`:**
  - `item4_callsites.sh` (Git Bash; `git show`, `git grep`, `git rev-parse` and `git diff --stat` only) → `item4_callsites.out.txt`.
  - `item4_drain_timings.py` (`wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python <path>/item4_drain_timings.py'`) → `item4_drain_timings.out.txt`.
- **Documentation**, retrieved 2026-09-21 into `gates/sources/`. Hashes and URLs are in `SHA256SUMS.txt`. These are verification copies, not part of the record.
  - Mosquitto: `mosquitto(8)`, section "Broker Status"; `mosquitto.conf(5)`, sections "General Options" (`sys_interval`, `max_inflight_messages`, `max_queued_messages`, `max_queued_bytes`, `acl_file`, `log_type`, `log_dest`, `connection_messages`, `enable_control_api`); `mosquitto_ctrl(1)`, "Modules"; `mosquitto_ctrl_dynsec(1)`; the change log (entries 2.1.0, 2.0.22, 2.0.4, 1.5, 1.4, 1.1, 1.0, 0.11).
  - OASIS MQTT 3.1.1 (Standard): sections 3.1.2.4, 3.2.2.2, 4.4, 4.5, 4.7.2.
- **Library:** paho-mqtt 2.1.0 in `~/egw-exec/venv`, `paho/mqtt/client.py:225-228`, `:784-785`, `:3928`, `:4147-4159`, `:4165-4176`.
