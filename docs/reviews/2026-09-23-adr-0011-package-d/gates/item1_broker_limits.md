# Gate item 1 — can the deployed broker hold the controller's backlog?

- **Date:** 2026-09-21
- **Answers:** item 1 of `decision_request.md` (line 28) and item 1 of "Open before the decision" in
  `adr-0011-controller-restart-recovery.md` (lines 1098-1102).
- **The question:** can Eclipse Mosquitto 2.0.22, as deployed, hold an in-flight plus queued backlog of
  3,593 to 4,999 QoS 1 messages for the controller's persistent session without dropping any, and do so
  within its 128 MiB memory limit? The range comes from the ADR: 3,593 inside the controller at the end of
  `nominal-r01` (ADR line 293, [F:N.3]), and W ≤ 4,999 from 2W ≤ 9,999 (ADR lines 656-670).
- **What this note is:** a reading of documentation, repository files and preserved artefacts, plus the
  design of a measurement. No guest was started, nothing was measured live, and no repository, raw run,
  attempt, `output_test` or project-manager file was modified.
- **Status labels:** as in the ADR. **PROVED** means a document or artefact line states it, or arithmetic on
  such lines gives it. **CONSISTENT-WITH** means the evidence points that way but does not exclude an
  alternative. **ASSUMED** means it rests on a default or on protocol semantics that no artefact records.
  Where none of these applies, the note says *I could not establish*.

---

## 0. Answer

1. **Configuration.** The 2.0.22 manual documents no upper bound on the in-flight window
   (`max_inflight_messages`) or on the per-client queue (`max_queued_messages`), and the MQTT 3.1.1 packet
   identifier allows up to 65,535 unacknowledged deliveries per direction. A window of 3,593 to 4,999 can
   therefore be *configured* (PROVED from documentation). Whether the broker actually honours it has not
   been observed.
2. **Today's configuration cannot hold the range.** The deployed `mosquitto.conf` sets none of the
   window or queue options. Under the documented defaults a client may hold 20 in flight plus 1,000
   queued, which is 1,020 messages. That is 2,573 to 3,979 short of the range. Beyond it the broker drops
   (PROVED from documentation plus the file). Today this does no harm, because the controller acknowledges
   every delivery at once. Under option 5 it would drop, and it would also cap the controller's queue at
   20, moving the wait into the broker, which P5 excludes.
3. **When a persistent session's queue is full, the broker drops the message.** The manual calls the drop
   silent only for the byte limit (`max_queued_bytes`), which is unlimited by default; under the defaults
   the drop comes from `max_queued_messages`, whose entry says nothing about silence. The drop is counted
   only in the broker-wide `$SYS/broker/publish/messages/dropped` counter and its moving averages, which
   name no client and no message. Today no user may read `$SYS` (the ACL grants no such access), and no
   run records it. The ChangeLog records, since release 1.3, that the broker logs when a client's
   outgoing messages begin to drop off the end of its queue ([CL] 2679-2680). Whether 2.0.22 still does,
   at which log type, and whether the deployed log types (`mosquitto.conf:48-53`) include it, is not
   established (*I could not establish* it); the broker log of the section 7 measurement answers it.
4. **Memory within 128 MiB cannot be established without measuring.** Neither the documentation nor any
   admissible source gives a per-message memory cost. The only facts are these:
   - the payload and topic bytes of 4,999 real messages total at most 1.80 MiB;
   - the broker used 4.17 to 7.34 MiB in `nominal-r01`, while holding no backlog;
   - the broker would have to spend more than about 24.7 KiB per held message (79 times the largest
     payload) for 4,999 messages to reach the limit.

   These figures bound what the measurement must rule out. They are not an estimate.
5. **Consequence.** Option 5 is **in, with conditions**. The documentation does not rule it out, but it
   cannot be run on today's configuration. It needs:
   - the window, the queue bound, the byte limits and the expiry set explicitly;
   - the bounded broker-only measurement of section 7 run with a result that **supports** option 5,
     meaning every one of S1 to S5 holds. A run that is only "not refuted", an inconclusive one
     included, does not meet this condition.

   Making the drop counter readable and recording it is a choice attached to option 5, not a condition
   (section 8). The measurement needs no controller change and no image rebuild.

---

## 1. Sources and identity

**Repository.** `/home/ruisth/egw-exec/repo` is detached at `b7e0c83`, not at the merged `dev` head
`35fe8bb` (`git log -1`; `git branch -a`, where `origin/dev` there is `ccd5fd6`). `35fe8bb` exists as
`origin/dev` in the Windows clone that the worktree `scratchpad/devwt` shares. The four files this note
reads are byte-identical in the WSL working tree and at `35fe8bb`: `git hash-object` on the tree matches
`git rev-parse 35fe8bb:<path>` for all four.

| file | blob at `35fe8bb` and in the WSL tree |
|---|---|
| `src/deployment/mosquitto/config/mosquitto.conf` | `e3cb1029` |
| `src/deployment/compose.yaml` | `5e5d66ec` |
| `src/deployment/images.lock.env` | `7fa2f7ec` |
| `src/deployment/mosquitto/config/acl` | `2424f32f` |

`git diff --stat b7e0c83 35fe8bb -- src/deployment src/egw_controller src/egw_simulator src/pyproject.toml src/Dockerfile`
is empty. Every repository `file:line` below holds at both commits.

**Broker image.** The pin is
`docker.io/library/eclipse-mosquitto:2.0.22@sha256:212f89e1…c32b3c` (`images.lock.env:39`). The same
reference is recorded as the broker image in `raw/nominal-r01/manifest.json` (`image_digests.IMAGE_MOSQUITTO`)
and in `raw/controller_restart-r01/manifest.json:135` and `-r02/manifest.json:135`. **PROVED** that the
three runs recorded this pin. That the binary inside reports 2.0.22 has not been read (section 7 records
`$SYS/broker/version`).

**Documentation (version matters).** mosquitto.org now serves the **2.1.x** documentation: its
`ChangeLog.txt` opens with "2.1.2 - 2026-02-09" (line 1). Its `mosquitto.conf(5)` page differs from 2.0.22
in entries that bear on this item:

- `persistence`: the page recommends plugin-based persistence (`gates/sources/man_mosquitto-conf-5.txt:690-693`);
- `persistent_client_expiration`: the page accepts seconds, which 2.1.0 introduced (ChangeLog line 143, see
  section 2).

The 2.0.22 manuals were therefore read as released with 2.0.22.

| tag | document | identity |
|---|---|---|
| [M5] | `mosquitto.conf(5)` as released with 2.0.22: `man/mosquitto.conf.5.xml` at tag `v2.0.22` of the Eclipse Mosquitto project (`raw.githubusercontent.com/eclipse-mosquitto/mosquitto/v2.0.22/man/mosquitto.conf.5.xml`) | sha256 `5d53da59…4b651c4`. Kept in the package as `gates/sources/mosquitto.conf.5-2.0.22.xml`, a byte copy of `scratchpad/mosq-src/mosquitto.conf.5.xml`, with its hash in `gates/sources/SHA256SUMS.txt`; line numbers are that file's |
| [M8-org] | `mosquitto(8)` as served by mosquitto.org, which documents **2.1.x**: `https://mosquitto.org/man/mosquitto-8.html` | the copy retrieved on 2026-09-21 and kept as `gates/sources/man_mosquitto-8.html` (sha256 `261db8dc…`, in `gates/sources/SHA256SUMS.txt`); line numbers are those of its text conversion `gates/sources/man_mosquitto-8.txt`. **Version caveat:** this is not the 2.0.22 page. It marks some command-line options "Available from version 2.1." (`:55`, `:62`, `:69`); none of the entries cited in this note carries that mark, but that 2.0.22 documents them with the same meaning rests on [M8] below, which is not kept |
| [M8] | `mosquitto(8)` as released with 2.0.22: `man/mosquitto.8.xml` at tag `v2.0.22` | sha256 `7ff3b8f2…c2f5558f`. Read from the source tag when this note was first written, but **not kept**: its wording and line numbers are not reproducible from the package. Every statement this note first took from it is cited below against [M8-org], with the version caveat above |
| [CL] | `https://mosquitto.org/ChangeLog.txt`, fetched 2026-09-21; it contains the 2.0.x sections | sha256 `a29df2b6…a95796a`, the same as the copy at `gates/sources/ChangeLog.txt`; line numbers are that copy's. The 2.0.22 release tag's own `ChangeLog.txt` (sha256 `90074b0a…`, equal to `scratchpad/mosq-src/ChangeLog.txt`) carries the same 2.0.x entries |
| [M5-org] | `https://mosquitto.org/man/mosquitto-conf-5.html` (the 2.1.x page) | sha256 `8518d070…`, the same as `gates/sources/man_mosquitto-conf-5.html` |
| [MQTT] | OASIS MQTT Version 3.1.1, OASIS Standard, `https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html` | page sha256 `4c18b9bf…` as fetched |
| [PAHO] | paho-mqtt 2.1.0 in `~/egw-exec/venv`, `paho/mqtt/client.py` | sha256 `5a3f0f73…`. This is the analysis environment; the controller image's paho version is not recorded (ADR lines 42-49) |

For the four capacity options (`max_inflight_bytes`, `max_inflight_messages`, `max_queued_bytes`,
`max_queued_messages`), [M5-org] carries the same wording as [M5]
(`gates/sources/man_mosquitto-conf-5.txt:515-604`). A reader limited to mosquitto.org would therefore
reach the same answer on those four, but not on `persistence` or `persistent_client_expiration`.

**Figures of this note.** `gates/scripts/item1_payload_and_broker_memory.py` produces them (read-only).
Its output is `gates/out/item1_payload_and_broker_memory.out.txt`, cited as [OUT:A.n] and [OUT:B.run].

---

## 2. What the options do in 2.0.22, their defaults and scope, and what the deployment sets

| option | what the 2.0.22 manual says it does | default [M5] | scope [M5] | deployed `mosquitto.conf` |
|---|---|---|---|---|
| `max_inflight_messages` | "maximum number of outgoing QoS 1 or 2 messages that can be in the process of being transmitted simultaneously", including "messages that are being retried"; 0 means no maximum; 1 "will guarantee in-order delivery" (:572-580) | 20 (:578) | "applies globally" (:582) | **not set** |
| `max_inflight_bytes` | outgoing QoS 1/2 messages are "allowed in flight until this byte limit is reached"; with a limit, a message larger than it may still go, but alone (:559-563) | 0, no limit (:563) | global (:566) | **not set** |
| `max_queued_messages` | "maximum number of QoS 1 or 2 messages to hold in the queue (per client) above those messages that are currently in flight"; 0 means no maximum, "(not recommended)" (:678-681) | 1000 (:680) | global (:685) | **not set** |
| `max_queued_bytes` | bounds the bytes queued per client "above those currently in-flight"; "Once this limit has been reached, subsequent messages will be silently dropped"; with both limits set, queueing stops "until the first limit is reached" (:659-667) | 0, no maximum (:663) | global (:670) | **not set** |
| `persistence` | if true, "connection, subscription and message data will be written to the disk in mosquitto.db" at close and every `autosave_interval`, or on SIGUSR1, and reloaded at restart; if false, "stored in memory only" (:795-806) | false (:805-806) | global (:815) | **`true`** (`mosquitto.conf:33`), `persistence_location /mosquitto/data/` (`:34`) |
| `autosave_interval` | seconds between saves of "the in-memory database to disk" (:310-316) | 1800 (:315-316) | global (:318) | **`60`** (`mosquitto.conf:35`) |
| `autosave_on_changes` | if true, save by count of changes, "queued messages" among them, instead of by time (:326-334) | not stated in the entry (:324-340); *I could not establish* it from [M5], so whether the deployed 60 is read as seconds rests on the default being false (ASSUMED) | global (:336) | not set |
| `persistent_client_expiration` | removes the session of a persistent client "that [is] not currently connected" if it does not reconnect in time (:846-849). The unit must be one of `h d w m y`, hour to year, so **`m` is a month and the shortest period is one hour** (:860-867) | "never expire persistent clients" (:868-869) | global (:871) | **not set** |
| `memory_limit` | hard heap limit. When an outgoing message is denied, "the individual message will be dropped and the receiving client will be disconnected"; "only available if memory tracking support is compiled in" (:693-703) | no limit (:701) | General Options; no scope sentence | not set |
| `queue_qos0_messages` | QoS 0 queueing for disconnected persistent clients (:961-967) | false (:966-967) | global (:972) | not set; the controller subscribes at QoS 1 (`mqtt.py:103`) |
| `sys_interval` | seconds between updates of `$SYS`; 0 disables it (:1035-1040) | 10 (:1037-1038) | global (:1042) | not set |
| `per_listener_settings` | when true, per-listener control of `password_file`, `acl_file`, `psk_file`, `allow_anonymous`, `allow_zero_length_clientid`, `auto_id_prefix`, `plugin`, `plugin_opt_*` only (:770-780) | false (:785-788) | — | not set |

**Per-listener and global forms (PROVED from [M5]).** In 2.0.22 none of the window, queue, persistence or
expiry options has a per-listener form:

- each entry above says "This option applies globally";
- none of them appears among the options of the Listeners section (:1088-1598), whose general options are
  `bind_address` to `websockets_headers_size`, and none of them concerns in-flight messages or queues;
- `per_listener_settings` affects only authentication and access control (:770-780).

Two consequences follow. First, a window or queue bound chosen for the controller applies to **every**
client that subscribes to the broker, including test tools such as the ACL probe's `mosquitto_sub`
(`docs/setup/qemu_integrated_gateway.md:1210`). Second, no documented 2.0.22 option scopes it to one
client id.

**Fixes in 2.0.x that touch exactly these options** [CL]. The pinned 2.0.22 contains all of these fixes.
They are recorded because they show that these code paths have had defects:

| version | ChangeLog lines | entry |
|---|---|---|
| 2.0.0 | 1070 (heading), 1115-1116, 1158 | the default of `max_queued_messages` rose from 100 to 1000 |
| 2.0.13 | 633 (heading), 640 | "Various fixes around inflight quota management" |
| 2.0.17 | 483 (heading), 487 | "Fix `max_queued_messages 0` stopping clients from receiving messages" |
| 2.0.17 | 489 | "Fix `max_inflight_messages` not being set correctly" |
| 2.0.22 | 340 (heading), 346-347 | "Fix case where max_queued_messages = 0 was not treated as unlimited" |
| 2.1.0 | 143 | "Allow seconds when defining `persistent_client_expiration`" |

The 2.1.0 entry confirms that 2.0.22 does not accept seconds.

**What the controller asks for.** `Client(...)` is built with neither `protocol` nor `clean_session`
(`src/egw_controller/mqtt.py:73-76`). In paho-mqtt 2.1.0 the default protocol is MQTTv311
([PAHO] `client.py:739`), and for 3.1.1 `clean_session` defaults to `True` (`client.py:784-785`). This is
ASSUMED for the image, whose paho version is not recorded. Under 3.1.1 there is no client-side Receive
Maximum, so the broker's window for the controller is `max_inflight_messages` alone. `max_inflight_messages`
concerns outgoing messages (M5 :574), so it does not throttle the simulator's publications to the broker.

---

## 3. What the broker does when a persistent session's queue is full

**Session state (protocol).** After a CleanSession = 0 client disconnects, "the Server MUST store further
QoS 1 and QoS 2 messages that match any subscriptions that the client had at the time of disconnection as
part of the Session state" ([MQTT] section 3.1.2.4, [MQTT-3.1.2-5]). That state includes "QoS 1 and QoS 2
messages which have been sent to the Client, but have not been completely acknowledged" and those "pending
transmission" (ibid.). The protocol expects limits: "Stored Session state can be discarded as a result of
an administrator action, including an automated response to defined conditions … prompted by resource
constraints" ([MQTT] section 4.1, non-normative comment).

**Mosquitto 2.0.22 (documented; the `$SYS` entries as the 2.1.x page [M8-org] states them, with the
version caveat of section 1).** The broker drops the message:

- **the byte limit:** "Once this limit has been reached, subsequent messages will be silently dropped"
  ([M5] :659-661);
- **the count:** `$SYS/broker/publish/messages/dropped` is the total of PUBLISH messages "dropped due to
  inflight/queuing limits", with a pointer to `max_inflight_messages` and `max_queued_messages`
  ([M8-org] :342-348; the quoted words are the 2.1.x page's);
- **the rate:** `$SYS/broker/load/publish/dropped/{1min,5min,15min}` "shows the rate at which durable
  clients that are disconnected are losing messages" ([M8-org] :305-312).

**Where it is visible:**

- **Counted: yes, broker-wide.** Both counters are totals or rates for the whole broker. They name no
  client and no message ([M8-org] :342-348, :305-312), and they are published every `sys_interval`, 10 s
  by default, to subscribers of `$SYS` ([M8-org] :220-224; [M5] :1035-1038).
- **Readable in this deployment: no.** The ACL lists only `egw-simulator` (write `c2dt/#`) and
  `egw-controller` (read `c2dt/#`) (`acl:8-14`), and its header states that any user or topic not listed
  is denied (`acl:3-4`). No run records `$SYS` either: the harness writes the controller's `/metrics` and
  the per-container cgroup figures, and the collector columns are `ts_utc,container,cpu_pct,mem_bytes,mem_pct,host`
  (`src/deployment/README.md:406`).
- **Logged: not established.** The manual calls the drop silent only for the byte limit ([M5] :659-661),
  which is unlimited by default (:663). The entry for `max_queued_messages`, the limit that applies under
  the defaults, says nothing about silence or about a log line ([M5] :676-688). The ChangeLog, release
  1.3, records that the broker logs when a client's outgoing messages begin to drop off the end of its
  queue ([CL] 2661 heading, 2679-2680); no later entry in [CL] mentions such a line again. The deployed log types
  are `error`, `warning`, `notice`, `information`, `subscribe` and `unsubscribe`, with no `debug`, written
  to stdout (`mosquitto.conf:47-53`). Whether 2.0.22 still writes that line, at which log type, and
  whether the deployed types include it, *I could not establish*. The measurement (section 7) keeps the
  broker log whole and answers it.
- **Seen by the controller or the simulator: no documented signal.** The manual gives the publisher no
  indication of a drop at a subscriber's queue. Whether the publisher's PUBACK is affected is not stated,
  so *I could not establish* it. The simulator's PUBACK capture is best-effort anyway (ADR line 254-257).
  This is the ADR's N4 ("the controller cannot see that it did", ADR line 713-714).

**Accounting while the client is offline.** The manual defines the queue bound as "above those messages
that are currently in flight" ([M5] :678-680). How messages that were in flight when a persistent client
disconnected are counted against `max_queued_messages` while it is offline is not stated. It is either
"`Q` above the held in-flight ones" or "`Q` in total". *I could not establish* which; section 7 is
designed to discriminate.

**A consequence for the drop signal (inference from the documented semantics).** A persistent session
whose client never returns keeps its subscription. It therefore accumulates every later matching QoS 1
publication ([MQTT] section 3.1.2.4) up to its queue bound, and from then on every matching publication
raises the broker-wide drop counter. By default that session never expires ([M5] :868-869). A retired
`EGW_ID` or a probe client left under a persistent session would therefore make
`$SYS/broker/publish/messages/dropped` rise for ever and mask the controller's own drops. `persistent_client_expiration`
(at least one hour in 2.0.22) bounds this. So does a check that `$SYS/broker/clients/disconnected`
([M8-org] :241-245) is 0, or equal to the expected count, before each run.

---

## 4. The deployed configuration against the range 3,593 to 4,999

- **Effective values.** Nothing in the repository sets any of the options except `persistence`,
  `persistence_location` and `autosave_interval` (`mosquitto.conf:33-35`). `git grep` at `35fe8bb` for
  `max_inflight`, `max_queued`, `persistent_client_expiration`, `memory_limit`, `queue_qos0`, `sys_interval`
  and `upgrade_outgoing_qos` finds no configuration hit. The deployed broker therefore runs with the
  documented defaults: window 20, queue 1,000, no byte limits, no expiry, no `memory_limit`,
  `sys_interval` 10.
  - **ASSUMED:** that the image runs with the mounted file. `compose.yaml:65` mounts it read-only at
    `/mosquitto/config/mosquitto.conf`.
  - **CONSISTENT-WITH** that assumption: the preserved broker log excerpts of 2026-09-18 carry the
    configured timestamp format `%Y-%m-%dT%H:%M:%S` (`mosquitto.conf:55-56`) and password-authenticated
    connections (`~/egw-tcg/itest/itest-dropout-01.broker.txt:1-8`;
    `~/egw-tcg/itest/itest-acl-20260918T221558Z/broker.txt:1-15`). These lines are outside the repository
    and are not the controller's.
- **Capacity per client, connected (PROVED as documentation plus arithmetic).** 20 in flight plus 1,000
  queued "above those … in flight" gives 1,020. Against the range this is **2,573 short at 3,593 and 3,979
  short at 4,999**, and beyond it the broker drops (section 3).
- **What this means for option 5 on today's configuration.** The controller would hold at most 20
  unacknowledged deliveries, so every further message would wait in the broker, where it is not stamped.
  That contradicts P5 (ADR lines 688-695) and the ADR's "The in-flight window W" (lines 656-670). Anything
  beyond 1,020 held would be dropped, counted only broker-wide; whether it would be logged is not
  established (section 3). Today no drop happens, because the PUBACK is sent at
  callback return ([PAHO] `client.py:4147-4152`; ADR section 2a), so the broker never holds a backlog for
  the controller.
- **Room to configure (PROVED from documentation).**
  - [M5] states no upper bound for `max_inflight_messages` or `max_queued_messages`; 0 means "no maximum".
  - The protocol requires "a non-zero 16-bit Packet Identifier" for every QoS > 0 PUBLISH, and an
    identifier is reusable only after its PUBACK ([MQTT] section 2.3.1). This caps any window at 65,535 per
    session direction, and 4,999 is below it.
  - The ADR's `W` ≤ 4,999 and a finite `Q` are therefore expressible. `0` (unlimited) is advised against
    twice: by the manual ("not recommended") and by the 2.0.17 and 2.0.22 fixes to exactly that value [CL].
    A finite `Q` is also what "bounded, recorded" requires (ADR line 650).
- **Values that must be explicit for the bound to mean what it says.**
  - `max_inflight_bytes 0`. A byte window could hold the in-flight count below `W` ([M5] :559-563).
  - `max_queued_bytes`, either 0 or a value recorded with its unit reading. The manual does not say
    whether payload bytes or packet bytes count, and *I could not establish* it.
  - `persistent_client_expiration` in the 2.0.22 grammar (`h d w m y`; never seconds, never `m` for
    minutes).
  - `sys_interval` as deployed or explicit, since the drop counter is read through it.

  All of them "Reloaded on reload signal" ([M5] at each entry), so the run record should state that no
  reload happened during a run.
- **What `W` and `Q` must cover is not this item.** The in-flight part is at most `W`. The queued part is
  what arrives while the window is full, and what arrives while the controller is away:
  - the ADR bounds the latter at 151 to 327 per restart in r02 and 183 to 356 in r01 at 11.2 msg/s (ADR
    lines 196-200);
  - if in-flight messages count against `Q` while the client is offline (section 3), `Q` must exceed `W`
    plus that outage.

  Sizing `W` against the nine families is the ADR's open item 3 (line 1109-1110), not answered here.

---

## 5. Memory: what can and cannot be said

- **Held messages are in memory; persistence is a snapshot.** `autosave_interval` saves "the in-memory
  database to disk" ([M5] :310-312). With persistence off the data are "stored in memory only" (:804-806),
  and the file is written at close, at each interval and on SIGUSR1 (:799-804; [M8-org] :482-485 for
  SIGUSR1). This is
  CONSISTENT-WITH every held message, in flight or queued, occupying broker memory whatever
  `persistence` says, and with the file lagging memory by up to one interval (ADR N3).
- **No per-message cost is documented.** Neither [M5], [M8-org] nor [CL] gives the memory a stored QoS 1 message
  costs. `$SYS/broker/store/messages/bytes` counts only "bytes currently held by message payloads"
  ([M8-org] :412-415), not the broker's memory. The broker's own source is not among the sources admissible
  for this note, so it was not used. **The broker's memory per queued QoS 1 message cannot be established
  without measuring.**
- **What the data themselves weigh (PROVED, arithmetic on regenerated payloads).** The repository's
  simulator code regenerates the 6,720 `nominal-r01` payloads from the seed, run id, egw id and devices in
  its manifest. All 6,720 `message_id`s match `sent_events.jsonl` [OUT:A.1]. Payloads are 273 to 320 bytes
  (mean 313.5), and topics `c2dt/egw-01/<uuid>/telemetry` are 58 bytes [OUT:A.2, A.3]. 4,999 messages
  carry at most 1.526 MiB of payload, or 1.802 MiB with topics; 3,593 carry at most 1.096 MiB, or 1.295 MiB
  [OUT:A.4]. This is a floor on the data, not an estimate of memory.
- **What the broker used without a backlog (PROVED from the sealed run).** `nominal-r01`'s collector
  recorded the broker's `mem_bytes` at 4.17 MiB minimum, 4.19 MiB median and 7.34 MiB maximum over 720
  samples. `mem_pct` peaked at 5.73 %, which implies `memory.max` ≈ 128.03 MiB, consistent with
  `compose.yaml:87` (`memory: 128M`) [OUT:B.nominal-r01]. The broker held no backlog for the controller
  in that run, since the controller acknowledged at once (section 4). Two caveats on these figures:
  - `mem_bytes` is `memory.current` minus `inactive_file`, "not total cgroup usage", and "does not by itself
    give an OOM margin" (`src/deployment/scripts/collect-resources.sh:68-71`;
    `src/deployment/README.md:430-433`);
  - the two restart runs' resource files were rejected by the ingest rule (ADR N8) and their manifests
    record `resource_source` "none", so their broker figures are not used.
- **What the measurement has to rule out (arithmetic, not an estimate).** For 4,999 held messages to
  exhaust 128 MiB above the highest observed baseline, the broker would have to spend
  (134,217,728 − 7,692,288) / 4,999 = 25,310 B, about 24.7 KiB, per held message. That is 79 times the
  largest payload. For 3,593 the figure is 34.4 KiB; for 5,999 (4,999 plus a queue of 1,000) it is
  20.6 KiB. Whether the real cost is far below this, as a payload of about 0.3 KiB suggests, is exactly
  what cannot be stated without measuring. The costs that have not been measured are per-message
  structures, the per-client queue entries, the TLS and socket buffers of the 4,999 in-flight resends, the
  allocator, and the page cache of the 60 s autosave, which is charged to the same cgroup.
- **`memory_limit` as a guard.** It would turn heap exhaustion into a dropped message and a disconnected
  receiver instead of an OOM kill ([M5] :693-701), but only "if memory tracking support is compiled in"
  (:702-703). Whether the pinned image has it *I could not establish*. The heap topics "may be unavailable
  depending on compile time options" ([M8-org] :264-271), so their presence in the measurement tells.

---

## 6. Side finding for ADR open item 1: redelivery within a live session

The ADR asks whether the deployed broker resends an unacknowledged delivery while the connection stays up
(ADR lines 779-782, 1098-1100). The documentation points one way:

- The 1.5 ChangeLog states "Outgoing messages with QoS>1 are no longer retried after a timeout period.
  Messages will be retried when a client reconnects" ([CL] 1984 heading, 2000-2001).
- The 2.0.22 manual has no `retry_interval` option (no match in [M5]).
- MQTT 3.1.1 requires re-sending unacknowledged PUBLISH packets "When a Client reconnects with CleanSession
  set to 0", and "This is the only circumstance where a Client or Server is REQUIRED to redeliver
  messages" ([MQTT] section 4.4).

This is **CONSISTENT-WITH** no resend within a live connection. The ChangeLog's literal "QoS>1" names only
QoS 2, so whether it covers QoS 1 *I could not establish* from its text. The measurement below observes it
directly: it counts deliveries with DUP = 1 during a held window while the subscriber stays connected.

---

## 7. The bounded broker-only measurement that would establish it

**Purpose.** To establish, on this guest and in one run, whether the pinned broker, under candidate values,
does four things:

- accepts and honours a window `W` = 4,999;
- holds 4,999, and then 4,999 plus a queue, of real-sized QoS 1 messages for a non-acknowledging
  persistent session without drops and within 128 MiB;
- shows a drop when its queue is full, and where;
- keeps and redelivers the held messages, in per-device order, after the subscriber is killed.

It needs **no controller change, no image rebuild and no Ditto**. It is not a G3 run, not a repetition of
any run, and changes no threshold, load, deadline or rule.

**Set-up (nothing deployed is modified).**

- **The deployed stack is stopped** for the duration. The controller must not consume the probe's
  publications, and the probe broker takes port 8883, the port the harness's simulator already reaches
  as `127.0.0.1:8883` with TLS (`raw/nominal-r01/logs/simulator/nominal-r01/manifest.json`, `broker`).
- **The broker** is a throwaway container of the pinned image `images.lock.env:39`:
  - `--memory 128m`, equal to `compose.yaml:87`; record the cgroup's `memory.max` = 134,217,728 to prove it;
  - port 8883;
  - the deployed `certs` and `passwd`;
  - a **measurement copy** of `mosquitto.conf` and of `acl`, each hashed into the record;
  - a **fresh named volume** for `/mosquitto/data`, never the deployed `mosquitto-data`
    (`compose.yaml:69`, `:323-324`), so that no probe session or message survives into a later run. The
    container and the volume are removed at the end.
- **The measurement `mosquitto.conf`** is the deployed file (`persistence true`, `autosave_interval 60` and
  the rest unchanged) plus five lines:

  ```
  max_inflight_messages 4999
  max_inflight_bytes 0
  max_queued_messages 1000
  max_queued_bytes 0
  persistent_client_expiration 1h
  ```

  If the student chooses other `Q` or expiry values before the run, the run uses them and records them.
- **The measurement `acl`** is the deployed file plus one line under `user egw-controller`:
  `topic read $SYS/#`. It is a measurement-only grant that lets a reader see the broker's counters.
- **The clients** run where the simulator runs, over the existing tunnel, from `~/egw-exec/venv`
  (paho-mqtt 2.1.0):
  - **Publisher.** User `egw-simulator`, MQTT 3.1.1, QoS 1, TLS. It publishes the real payloads,
    regenerated with the repository's simulator code (envelope and profiles, the nominal three-device mix,
    `nominal-r01`'s seed) under a fresh run id of **the same length as `nominal-r01`** (11 characters, for
    example `brkhold-r01`), so that sizes stay 273 to 320 B. It publishes at 11.2 msg/s in the nominal
    order and records, per message, `message_id`, device, `seq`, payload bytes, publish instant and PUBACK
    instant.
  - **Holding subscriber.** User `egw-controller`, client id `egw-probe-hold`, never the controller's id.
    It connects with `protocol=MQTTv311`, `clean_session=False` and `manual_ack=True`, and subscribes to
    `c2dt/+/+/telemetry` at QoS 1. In paho 2.1.0 a QoS 1 delivery is then not acknowledged unless `ack()`
    is called ([PAHO] `client.py:4147-4150`, `:4165-4176`). It records, per delivery, `mid`, `dup`,
    `message_id`, device, `seq` and the receive instant, and it does not acknowledge until phase P7.
  - **`$SYS` reader.** User `egw-controller`, client id `egw-probe-sys`, clean session, QoS 0, subscribed
    to `$SYS/#`. It records every value with its receive instant.
- **Guest recorder** at 1 s, for the broker container's cgroup:
  - `memory.current`, `memory.max`, `memory.peak` if present (the guest kernel is 6.6.142,
    `raw/nominal-r01/sut_environment.json`);
  - `memory.stat` (`anon`, `file`, `active_file`, `inactive_file`);
  - `memory.events` (`max`, `oom`, `oom_kill`);
  - the container's restart count and state.

  Each save's effect is recorded as the size of `mosquitto.db` in the probe volume, read after every
  autosave and at the end. The broker log is kept whole, with container timestamps.

**Phases.** Counts are exact; durations are at 11.2 msg/s.

| phase | action | duration | expected if the option holds |
|---|---|---:|---|
| P0 | broker and `$SYS` reader only: baseline | 60 s | the `$SYS` topics arrive; `heap/*` present or absent is recorded |
| P1 | holding subscriber connects and subscribes | 10 s | SUBACK granted; `clients/connected` = 2 |
| P2 | publish **A = 4,999** while the subscriber is connected and not acknowledging | 446.3 s | subscriber receives 4,999 distinct deliveries, all DUP = 0; `messages/inflight` → 4,999; `store/messages/count` → 4,999; `publish/messages/dropped` = 0 |
| P3 | hold, subscriber connected, no publication | 130 s (two or more autosaves) | no new delivery, and no DUP = 1 delivery (section 6); dropped = 0; memory flat apart from saves; `mosquitto.db` size recorded |
| P4 | **SIGKILL** the subscriber process (no DISCONNECT); wait for the broker's disconnection line | ≤ 10 s, conditional on that log line | `clients/disconnected` = 1; store still 4,999 |
| P5 | publish **B = 1,100** while the subscriber is away | 98.2 s | see the discrimination below |
| P6 | hold, subscriber away | 70 s (at least one autosave) | counts stable; `mosquitto.db` size recorded |
| P7 | subscriber reconnects under `egw-probe-hold`, `clean_session=False`, and now acknowledges each delivery after recording it | until the store returns to its P0 value; limit 300 s | every held `message_id` delivered once more, the 4,999 former in-flight with DUP = 1, per-device `seq` ascending; the store returns to baseline; dropped unchanged |
| P8 | final readings, then reconnect `egw-probe-hold` with clean session to discard it, stop the probe broker, remove it and its volume, restart the stack | 30 s + stack start | — |

**P5 discriminates the offline accounting (section 3):**

- if `Q` counts **above** the held in-flight messages, the store reaches **5,999** and `dropped` rises by
  **100**;
- if `Q` counts **in total** while the client is offline, the store stays at **4,999** and `dropped` rises
  by **1,100**;
- any other outcome is recorded as observed.

Either way P5 answers where a full persistent queue's drop shows: in `$SYS`, in the log at the deployed
levels, or nowhere.

**Guest time and ceiling.**

- Total publication: 6,099 messages, 544.6 s.
- Measurement proper, P0 to the end of P8's probe removal: 884.6 s if P7 takes 30 s, 1,154.6 s at its
  300 s limit, so **about 15 to 19 minutes**.
- Stopping and restarting the deployed stack come on top. Ditto's start-up under TCG is still unverified
  in general (`qemu_integrated_gateway.md` Appendix B item 9, line 1288). The repository at `35fe8bb`
  records one stop and one restart under TCG, each a single observation and not a bound:
  - `docker compose … stop -t 60` took 15.943 s
    (`docs/evidence/g2-complete-flow/20260920T231756Z_guest-session_attempt02/commands.jsonl:5`);
  - `docker compose … down` then `up -d` took 179.142 s; the `wait_ready 3600` step that followed
    returned within 23.028 s, and the check that all six services were healthy took a further 26.508 s,
    228.7 s in all
    (`docs/evidence/g2-complete-flow/20260920T233212Z_g2-twin-persistence-restart_attempt01/commands.jsonl:7-9`).
- On those observations the session would take about 19 to 23 minutes, plus the probe broker's start,
  which is not recorded. This is a planning figure, not a bound.
- **Ceiling, set by stop rules.** The figures below are stop rules chosen by design, not measured
  durations. Reaching one ends the session:
  - stopping the deployed stack: 10 minutes;
  - starting the probe broker until the `$SYS` reader is connected: 5 minutes;
  - P0 to the removal of the probe broker and its volume: 25 minutes, against at most 1,154.6 s
    (19.2 minutes) by the phase table;
  - starting the deployed stack again until `/ready` answers 200 and all six services are healthy:
    60 minutes, the figure of the runbook's own limit for the `/ready` wait after a `down` and `up -d`
    under TCG (`wait_ready 3600`, runbook `:951`; "one hour is an upper bound", marked unverified,
    `:955`). Here it covers `up -d` as well.

  The session therefore ends within **100 minutes** in every case.

  *Superseded on 2026-09-23 by ADR 0011, "The broker measurement", which sets the one set of stop
  rules a session uses: the deployed stack stopped and the probe broker started within 5 minutes; the
  phases at their own limits (1,154.6 s); the stack healthy again within 20 minutes of its restart, on
  the one recorded restart of the whole stack under TCG (228.7 s) rather than on the runbook's
  unverified one-hour bound — about 45 minutes in all. The figures above are this note's earlier
  planning values and are kept as written. The student may set other values before a session; the
  values used are recorded before it starts.*
- Reaching any stop rule makes the attempt inconclusive, unless a refuting result (R1 to R6 below) was
  already observed, which stands. A session ended by a stop rule, or a deployed stack that is not
  healthy again within its 60 minutes, leaves the guest in a state that must be resolved before any other
  guest session.
- A phase that reaches its limit makes the attempt incomplete.

**Records** (into one attempt directory):

- the measurement `mosquitto.conf` and `acl` with their sha256;
- the broker image reference and `$SYS/broker/version`;
- `memory.max`;
- the 1 s cgroup file;
- the `$SYS` log;
- the broker log;
- the publisher and subscriber records;
- the `mosquitto.db` sizes;
- the phase boundaries on one clock.

**Result that supports option 5 on the broker side.** The measurement supports option 5 only if every
one of S1 to S5 holds. Any other outcome either refutes it (R1 to R6) or is inconclusive, and neither
meets condition 3 of section 8:

- **S1.** The broker starts with the five added lines and logs no configuration error.
- **S2.** By the end of P2 the subscriber has 4,999 distinct unacknowledged deliveries: the window reached
  `W`.
- **S3.** `publish/messages/dropped` = 0 through the end of P4, and no `message_id` among the first 4,999
  is missing from P7's redelivery.
- **S4.** `memory.events` `oom` = 0 and `oom_kill` = 0, no broker restart, and the peak
  (`memory.peak`, or the highest `memory.current`) is reported with its margin to `memory.max` and split
  into `anon` and `file`. The per-message cost is reported as (`anon` at end of P3 − `anon` in P1) / 4,999,
  and again for the P5 increment, as a figure of one run on this guest.
- **S5.** P7 redelivers every message held at the end of P6, and for every device its first copies
  arrive in ascending `seq` order (no R6).

**Result that refutes option 5 as configured.** The ADR's rule applies: "If the broker cannot, the option
is re-decided, never run silently with a smaller window" (ADR lines 669-670). Any one of these refutes it:

- **R1.** The broker refuses the configuration: it does not start, or it logs an error for any of the five
  lines.
- **R2.** The window is not honoured. With the subscriber connected and messages available, it receives
  fewer than 4,999 distinct deliveries by the end of P3.
- **R3.** A drop while held ≤ 4,999: `dropped` > 0 before P5, or a first-4,999 `message_id` never
  redelivered in P7.
- **R4.** The memory limit is not held: `oom` or `oom_kill` > 0, or the broker restarts, at any point up to
  the end of P6 (held ≤ 4,999 + `Q`).
- **R5.** The session is not kept. After the kill and the reconnection with `clean_session=False`, fewer
  `message_id`s are redelivered than the broker held at the end of P6, as read in `store/messages/count`.
- **R6.** A per-device order break of first copies in P7: for some device, the first P7 delivery of each
  `message_id`, taken in receive order, does not give ascending `seq`. Later copies of a `message_id`
  already delivered in P7 are recorded and not judged for order. This classification is decided in
  advance: with a window `W` greater than 1, the manual states no in-order guarantee (it gives one only
  for `max_inflight_messages` 1, [M5] :578-580), and ADR 0011's P4, N5 and the proof's R3 rely on
  that order. An order break refutes option 5 as configured; the option then goes back
  to the student for re-decision, with option 4 as the next best. Any re-designed option 5 needs its
  own record and is not this one.

**Recorded, not refuting by themselves.**

- If P5 gives the "in total" accounting, that is a sizing finding: `Q` must exceed `W` plus the outage
  allowance, and the student re-sizes `Q` before implementation.
- `memory.events` `max` > 0 without an OOM is reclaim of page cache, reported with the `anon`/`file` split.
- Deliveries with DUP = 1 during P3 answer section 6.

**Inconclusive** (preserved as incomplete; no result claimed):

- `$SYS` could not be read;
- the recorder has a gap over 5 s inside P2 to P7;
- the publisher did not publish its exact counts;
- the broker's disconnection line never appeared in P4;
- the tunnel failed;
- P7 reached its limit;
- a stop rule of the ceiling above was reached before any refuting result was observed.

An inconclusive run does not support option 5 and does not meet condition 3 of section 8. The student
decides whether to repeat it with the same design, recorded as a repeat with the first run kept, or to
re-decide the option.

**What it cannot show.**

- The connected-queue overflow at `W` + `Q`: P5 overflows only while the subscriber is away.
- Expiry, since the run lasts under an hour.
- A broker crash or restart, or a guest loss (N3).
- The controller's `ack` cost, or anything about the controller, Ditto or latency.
- Any other rate or duration, or a larger backlog than 5,999.
- Native hardware.

One run supports the broker-side premise for that run only.

---

## 8. Consequence for option 5

**In, with conditions.**

- Nothing in the 2.0.22 documentation rules option 5 out. The window and queue can be configured far
  beyond 4,999, and the protocol's limit is 65,535.
- Option 5 is **ruled out on today's configuration**. It would hold 1,020 messages, drop the rest
  (counted only broker-wide; whether the drop is logged is not established, section 3) and cap the
  controller's window at 20.
- Items 1 and 3 below are conditions; item 2 is a choice attached to option 5, not a condition:
  1. **Condition.** `max_inflight_messages` = `W` (3,593 ≤ `W` ≤ 4,999), `max_inflight_bytes 0`, a
     finite `max_queued_messages`, `max_queued_bytes`, and `persistent_client_expiration` in the 2.0.22
     grammar, all set explicitly and recorded. They are global, so they apply to every subscriber of the
     broker.
  2. **Choice.** `$SYS/broker/publish/messages/dropped` and `$SYS/broker/clients/disconnected` made
     readable and recorded with each run. Today no user may read them. Drops remain broker-wide and
     anonymous, so reconciliation by identity (the proof's S2/R1) stays the only per-message check. If
     the student declines this grant, the run-level evidence that a drop happened (ADR N4) lapses, and
     test 9's proof is unchanged, because the ACL it proves stays as deployed.
  3. **Condition.** The section 7 measurement has run and **supported** option 5: every one of S1 to S5
     holds. A run that is only "not refuted" does not meet this condition. An inconclusive run is not
     passing: the student decides whether to repeat it with the same design, recorded as a repeat with the
     first run kept, or to re-decide the option. Until a run has supported it, "within 128 MiB" is
     unknown, not assumed. One run supports the broker-side premise for that run and proves nothing in
     general.
- If it refutes, R6 (a per-device order break of first copies) included, option 5 is re-decided (ADR
  lines 669-670) and option 4 remains available as the next best. Any re-designed option 5 needs its own
  record.

---

## 9. What I could not establish

- The broker's memory per queued or in-flight QoS 1 message. It is not documented and it was not measured.
- Whether messages in flight when a persistent client disconnects count towards `max_queued_messages`
  while it is offline.
- Whether Mosquitto 2.0.22 still writes the line that the ChangeLog records since release 1.3, when a
  client's outgoing messages begin to drop off the end of its queue ([CL] 2679-2680); at which log type;
  and whether the deployed log types (`mosquitto.conf:48-53`) include it.
- Whether `max_queued_bytes` counts payload bytes or packet bytes.
- Whether the pinned image has memory tracking compiled in, which decides whether `memory_limit` and
  `$SYS/broker/heap/*` exist.
- Whether the 1.5 ChangeLog's "QoS>1" (no retry within a connection) covers QoS 1.
- Whether the publisher's PUBACK is affected when the broker drops for a subscriber.
- That the binary in the pinned image reports 2.0.22, and that it loads the mounted configuration. The
  latter is CONSISTENT-WITH the preserved log format only.
- The paho version inside the controller image (ADR lines 42-49).

---

## 10. Reproduction

- **Figures.** Run
  `wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python -B "<scratchpad>/pkgD/v2/gates/scripts/item1_payload_and_broker_memory.py"'`.
  The output is `gates/out/item1_payload_and_broker_memory.out.txt`. It reads
  `/home/ruisth/egw-exec/repo/src` (simulator code) and
  `/home/ruisth/egw-tcg/pilot/results/raw/{nominal-r01,controller_restart-r01,controller_restart-r02}/`, and
  writes nothing else.
- **Repository identity.** Run `git log -1`, `git branch -a` and `git hash-object <file>` in
  `/home/ruisth/egw-exec/repo`; `git rev-parse 35fe8bb:<file>`, `git diff --stat b7e0c83 35fe8bb -- …`
  and `git grep … 35fe8bb` in `scratchpad/devwt`. All are read-only.
- **Documentation hashes.** Run `curl -sSL <url> | sha256sum` for [M5], [CL], [M5-org], [M8-org] and
  [MQTT], as listed in section 1. The copies of [M5], [CL], [M5-org] and [M8-org] kept in
  `gates/sources/` are checked by `sha256sum -c SHA256SUMS.txt` there. [M8] was not kept (section 1).
