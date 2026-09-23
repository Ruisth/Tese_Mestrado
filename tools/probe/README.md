# The broker-hold measurement (ADR 0011, condition C3)

**An engineering diagnostic, not a G3 run.** One bounded measurement of the
pinned Mosquitto 2.0.22 alone, designed in package D's gate item 1, section 7,
and summarised in ADR 0011, "The broker measurement". It asks one question of
the broker on this guest: with an in-flight window `W` = 4,999 and a queue
bound `Q` = 1,000, does it accept and honour the window, hold 4,999 and then
4,999 plus a queue of real-sized QoS 1 messages for a non-acknowledging
persistent session within its 128 MiB limit without drops, show where a full
queue drops, and keep and redeliver the held messages, in per-device order,
after the subscriber is killed?

It changes no threshold, load, deadline or rule; it needs no controller change,
no image rebuild and no Ditto; its values are **probe settings**, not adopted
production or campaign settings; and one run supports the broker-side premise
of option 5 **for that run only**. It proves nothing about the controller
design, approves none of ADR 0011's implementation items and accepts no gate.

## What is here

| File | Role |
|---|---|
| `broker_hold.py` | the host-side clients (`generate`, `publish`, `hold`, `sysreader`, `discard`) and the `verdict` that applies S1–S5, R1–R6 and the inconclusive rules to the records |
| `guest/probe_recorder.sh` | the guest-side 1 s recorder of the probe broker's memory cgroup, its `memory.events`, the size of its `mosquitto.db` and its container state (BusyBox ash, root) |
| `../session/broker_measure.sh` | the session driver: the stack stopped, the probe broker started on its own volume with measurement copies of the configuration, the phases P0–P8, every record kept, the probe's state read and the probe removed, the stack started and waited for, the verdict, the export |
| `../../src/tests/test_broker_hold.py` | the cases: the clients against a fake paho client, `generate` with the real simulator loop and a fake clock, the verdict on hand-written records of a supporting run and of every refuting and inconclusive shape |
| `local_check.py` | the local functional check: the real clients and the real verdict through the same phases against an isolated container of the pinned image on the workstation's Docker (x86-64), the attempt written in the driver's layout; a tool check, never evidence about the guest |
| `../../src/tests/test_broker_measure_driver.py` | the driver's lifecycle on the drivers' stub bench (a fake guest with a stateful `docker`, a `systemd-run` that really runs the recorder, a stub of the probe tool whose verdict is the real one): P7 waits for the client, a client that does not end is ended, an interruption — also one landing while the stack is being stopped — restores, a name in use stops the driver, a failed restoration or a missing record never yields a pass |

## Two outputs, kept apart

The attempt records two things and never lets one stand for the other:

- **`broker_verdict`** — the broker observation, as `verdict` computed it from the
  records (`environment/probe/verdict.json`): `supports`, `refutes`,
  `inconclusive`, or `not-computed`.
- **`restoration`** — what the guest was left with: `stack=… probe=… recorder=…`.

The attempt's own outcome, and so the driver's exit status, is a **pass only
when the observation supports, every mandatory record was made and the stack
is running and healthy again with the probe removed**. A refutation with a
complete record is a valid negative (exit 1). A missing record makes the
instrumentation invalid and the outcome inconclusive (3) whatever the
observation; a restoration that did not finish makes a supporting observation
an inconclusive session (3), with the observation still in `broker_verdict`.

## How a refutation is made

Every refutation rests on something the instrument **observed**: an error line
in a broker log that was fetched (R1), the drop counter (R3), an OOM or a
restart from the recorder or from `docker inspect` before removal (R4), a
CONNACK without `session_present` in P7 or fewer redelivered in a P7 that ran
to its end (R5), an order break (R6). A shortfall that would rest only on
records that are absent — a publisher that did not offer its exact counts, a
P7 that hit its limit or has no end record, an empty log — is **never** a
refutation: the run is inconclusive. An observed refutation stands even when
another part of the attempt is incomplete.

Support needs the whole window measured: the recorder covering P2–P7 from its
first to its last second with no gap over 5 s, no unreadable counter, the
container `running` throughout with `memory.max` at the expected 128 MiB, and
`docker inspect` reporting `OOMKilled=false` before removal. The host's phase
instants are carried onto the guest clock by adding the recorded offset
(guest minus host).

## What the clients promise

- The holding subscriber insists on a SUBACK that grants QoS 1 and, in P7, on
  a CONNACK with `session_present`; anything else ends it (exit 2) or is
  recorded for R5.
- In P7 the delivery's record is written **first**; only then is the PUBACK
  requested, and the request's own outcome is written as a separate `ack`
  record. A record that cannot be written stops every acknowledgement from
  then on and the client ends 3: nothing is acknowledged that the file does
  not hold.
- The driver starts each client as its own child, waits for it with a bound,
  records its exit status in `phases.jsonl` and ends it itself only when the
  bound is reached — which is recorded as a stop rule, never as the broker's
  behaviour.

## Ownership and restoration

Before anything is touched, the driver refuses to start if a container named
`egw-probe-broker`, a volume of its attempt-specific name, its guest directory
or its recorder unit already exist. The probe container and volume carry the
label `egw.probe.attempt=<attempt id>`, and removal reads that label back: a
container of that name without this attempt's label is left alone and
reported. The intent of every mutation (`stopping`, `creating`, `starting`) is
recorded before the command is dispatched, so an interruption that lands while
the command is in flight is treated as "it may have taken effect" and the
restoration reads the guest back. Every guest command of the setup and the
restoration is bounded by `timeout` (`EGW_PROBE_STEP_TIMEOUT_S`, 300 s); the
restoration itself is never cut short to keep a total duration.

The recorder was also run under the image's own busybox through
`tools/test/make-busybox-wrappers.sh` (every applet it uses is one the image
offers; `wc -c` stands in for `stat`).

## The phases (gate item 1, section 7)

| phase | what happens | expected if option 5 holds |
|---|---|---|
| setup | `compose stop -t 60` of the deployed stack; measurement copies of `mosquitto.conf` (the deployed file plus `max_inflight_messages W`, `max_inflight_bytes 0`, `max_queued_messages Q`, `max_queued_bytes 0`, `persistent_client_expiration 1h`) and of `acl` (plus `topic read $SYS/#` under `user egw-controller`), both hashed; a throwaway container of the pinned image with `--memory 128m` on port 8883, the deployed `certs` and `passwd` read-only, a **fresh named volume**; the guest recorder started | the broker opens its listener; `memory.max` = 134,217,728 |
| P0 (60 s) | the `$SYS` reader alone | `$SYS/broker/version` and the counters arrive |
| P1 (10 s) | `egw-probe-hold` connects: MQTT 3.1.1, `clean_session=False`, `manual_ack=True`, QoS 1 on `c2dt/+/+/telemetry` | SUBACK granted QoS 1 |
| P2 (446.3 s) | A = 4,999 real payloads published at the nominal cadence as `egw-simulator`; the subscriber records and acknowledges nothing | 4,999 distinct deliveries, DUP = 0, in the subscriber's own records (the observation S2 rests on: the pinned 2.0.22 publishes no `messages/inflight`); the store count rises by 4,999 above its baseline; `dropped` = 0 |
| P3 (130 s) | hold, subscriber connected | no new delivery; memory flat apart from saves |
| P4 (≤ 10 s) | SIGKILL of the subscriber process (no DISCONNECT); the broker's disconnection line awaited | `clients/disconnected` = 1; store still 4,999 |
| P5 (98.2 s) | B = 1,100 published while the subscriber is away | store 5,999 and `dropped` + 100 if `Q` counts above the held window; store 4,999 and `dropped` + 1,100 if in total (recorded either way) |
| P6 (70 s) | hold, subscriber away | counts stable |
| P7 (≤ 300 s) | the subscriber resumes its session and acknowledges each redelivery after recording it | every held message delivered once more, the 4,999 with DUP = 1, per-device `seq` ascending; the store back to its P0 value |
| P8 (30 s) | final readings; the session discarded with one clean-session connect; the probe stopped, removed with its volume; `compose start`; the six services running and healthy again | — |

## The rules (applied by `broker_hold.py verdict`, never by hand)

- **Supports option 5 on the broker side** only if every one of **S1–S5** holds:
  S1 the broker started with the added lines and logged no error; S2 the
  window reached W (4,999 distinct unacknowledged deliveries by the end of P3);
  S3 `dropped` = 0 through P4 and every P2 message redelivered in P7; S4 no
  OOM, no `oom_kill`, no restart, the peak memory reported with its margin and
  its `anon`/`file` split, the per-message cost reported; S5 everything held at
  the end of P6 redelivered, first copies in ascending `seq` per device.
- **Refutes option 5 as configured** on any of **R1–R6**: R1 the configuration
  refused; R2 fewer than 4,999 held; R3 a drop while at most 4,999 are held, or
  a P2 message never redelivered; R4 an OOM or a broker restart; R5 fewer
  redelivered than the store held; R6 a per-device order break of first copies
  in P7. A refutation is a result: recorded, never re-run away; option 5 goes
  back to the student, option 4 next best.
- **Inconclusive**, which is **not passing**: `$SYS` unreadable; a recorder gap
  over 5 s inside P2–P7; the publisher off its exact counts; no disconnection
  line in P4; P7 at its limit; a stop rule reached. The student decides
  whether to repeat it (same design, recorded as a repeat, this run kept) or
  to re-decide the option.
- **Recorded, not refuting by themselves:** the "in total" accounting of P5 (a
  sizing finding: `Q` is re-sized before implementation); `memory.events max`
  > 0 without an OOM (page-cache reclaim); DUP = 1 deliveries during P3.

## Stop rules (imposed by design, not measured durations)

| rule | value | on reaching it |
|---|---|---|
| the stack stopped and the probe broker started | 300 s (`EGW_PROBE_SETUP_LIMIT_S`) | inconclusive |
| the broker's disconnection line after the kill | 10 s (`EGW_PROBE_P4_S`) | inconclusive |
| P7, the redelivery | 300 s (`EGW_PROBE_P7_LIMIT_S`) | inconclusive |
| the stack running and healthy again after `compose start` | 1,200 s (`EGW_HEALTH_LIMIT_S`) | inconclusive, and the guest is left in a state to resolve before any other session |

Planning figures: 884.6 to 1,154.6 s of phases (about 15 to 19 minutes);
about 19 to 23 minutes with the one recorded stop (15.9 s) and restart
(228.7 s) of the stack; about 45 minutes as the ceiling the stop rules make.
None is a measured duration of this measurement.

## Identities recorded in the attempt

The clean clone's commit and the drivers' hash (`identities`); the pinned
image reference from the deployed `images.lock.env` and the container's image
id (`probe-start`); `$SYS/broker/version`; the sha256 of both measurement
files and of the deployed originals (`probe-config`); `memory.max`; the probe
settings (`environment/probe/params.json`); paho-mqtt 2.1.0 from the venv.

## Export paths

Everything lands in the attempt and is exported to `output_test` as one
package, as every driver's attempt is: `console/` holds each step's stdout
and stderr; `environment/probe/` holds `params.json`, `phases.jsonl`,
`messages.jsonl`, `publish_p2.jsonl`, `publish_p5.jsonl`, `hold_p1.jsonl`,
`hold_p7.jsonl`, `sys.jsonl`, `discard.jsonl`, `recorder.csv`, `broker.log`,
`probe_state.json` (the container's status, `OOMKilled`, restart count and
exit code read before removal), `mosquitto.measure.conf`, `acl.measure`,
`verdict.json` and the background clients' own stdout/stderr;
`environment/generate/` holds the simulator's provenance of the generated
set. On the guest the measurement's files live under
`/opt/egw/probe/<attempt id>/` (the two measurement copies, the recorder's
script and its CSV), never under the deployment tree. A failed or interrupted attempt is exported
too. No credential is on any command line or in any record: the clients read
their passwords from the environment.

## Restoration

The clients reaped; the recorder unit stopped and its CSV fetched; the probe
container's state read, its log fetched, the container and its volume removed
(only when its label is this attempt's); `compose start` of the deployed
stack, then the shared "running and healthy" wait of the G2 drivers; the
measurement copies left under `/opt/egw/probe/<attempt>` on the guest (they
are also in the package). The interrupt handler does the same and says on the
final line which state it left the guest in (`stack=… probe=… recorder=…`).
`mosquitto-data`, `mongodb-data`, the sealed evidence and the original
recovery disks are never touched.

## Running it

Local functional check (no guest; a tool check, not evidence). The dev TLS
material comes from `src/deployment/scripts/generate-dev-tls.sh --cert-dir
<dir>`, the password file from `mosquitto_passwd` inside the pinned image with
throwaway passwords handed through the environment, the messages from
`generate`; the two passwords are read from a `NAME=value` file and never
reach a command line:

```bash
python tools/probe/broker_hold.py generate --work-dir <dir>/generate --out <dir>/messages.jsonl
python tools/probe/local_check.py --image eclipse-mosquitto@sha256:<the pinned digest> \
  --conf src/deployment/mosquitto/config/mosquitto.conf --acl src/deployment/mosquitto/config/acl \
  --certs <dir>/certs --passwd <dir>/passwd --secrets-env <dir>/secrets.env \
  --messages <dir>/messages.jsonl --out <dir>/attempts/<name> [--W 4999 --Q 1000 --A 4999 --B 1100 ...]
```

It writes the attempt in the driver's layout and prints the verdict; the
attempt is carried into `output_test` with `local_export backfill`, labelled
as a local functional tool verification and never as QEMU evidence.

### What the first local runs showed about the tool (2026-09-23, x86-64 image of the pinned digest)

Observations of the workstation's broker that changed the tool, not
statements about the guest:

- the broker's store count (`$SYS/broker/store/messages/count`) includes its
  own retained messages, the `$SYS` topics among them (51 on that broker
  after P0), so every store figure is read relative to the baseline at the
  end of P1, the subscriber's expected count in P7 is that difference, and
  the store's return to its baseline is read at the end of P8, the final
  readings, since the broker publishes a `$SYS` value only when it changed
  and only every `sys_interval`;
- the pinned 2.0.22 image publishes no `$SYS/broker/messages/inflight`; S2
  rests on the subscriber's own records, as designed, and that figure stays
  empty;
- a subscriber killed without a DISCONNECT leaves an `OpenSSL Error … unexpected
  eof while reading` line in the broker's log; an error line after the
  listener opened is a session line, recorded and never read as a refused
  configuration (R1 is an error line before the listener, or the container
  refusing to run);
- the broker logged `Outgoing messages are being dropped for client
  egw-probe-hold.` when the queue filled in P5, at the deployed log types —
  the line the ChangeLog records since 1.3, which gate item 1 left NOT
  ESTABLISHED for 2.0.22; the verdict now keeps such lines as a figure;
- with the subscriber away the queue counted **above** the held in-flight
  window (store W + Q, dropped B − Q) on that broker; whether the guest's
  arm64 variant does the same is what the guest measurement records.

With the design's counts (W = 4,999, Q = 1,000, A = 4,999, B = 1,100 at
11.2 msg/s) the tool ran end to end on that broker in 14.6 minutes and its
verdict was *supports* (4,999 held, 5,999 held with the subscriber away and
100 dropped, all 5,999 redelivered in order with DUP = 1 on the 4,999, peak
memory 17,649,664 bytes, 16.83 MiB, no OOM); with the redelivery client
limited to 2 s it reported the broker verdict *inconclusive* and removed its
container — the tool's negative path passed its check, which is not a
successful broker measurement. The three attempts are in `output_test` as
`HIST_2026-09-23-broker-probe-local-check-{smoke03,full01,fail01}`. None of
it says anything about the emulated guest.

Since then the driver also: reads the recorder unit's real state before
declaring it stopped, and fetches its CSV either way; keeps one setup budget
over every setup step and starts no stage beyond it; starts no later phase
once a stop rule is reached (a P4 without the disconnection line publishes
nothing in P5 and resumes no session), keeping the partial observation; and
removes the probe container and volume only when their label is exactly
this attempt's id. The verdict keeps an observed OOM or restart even when
another sample is unreadable, and treats rows without a readable epoch as
inconclusive.

On the guest, inside an open session, after the recovered bytes of r02 have
been preserved and only with the student's explicit authorisation for one
session:

```bash
bash -lc 'tools/session/broker_measure.sh'
```

Exit statuses are the drivers' (`tools/session/README.md`): 0 supports
(valid, pass), 1 refutes (valid, fail), 3 inconclusive, 2 a prerequisite
failed, 130 interrupted; the one final line names the verdict and the guest's
state.
