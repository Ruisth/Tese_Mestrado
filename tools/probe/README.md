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
| `../session/broker_measure.sh` | the session driver: the stack stopped, the probe broker started on its own volume with measurement copies of the configuration, the phases P0–P8, every record kept, the probe removed, the stack started and waited for, the verdict, the export |
| `../../src/tests/test_broker_hold.py` | the cases: the clients against a fake paho client, `generate` with the real simulator loop and a fake clock, the verdict on hand-written records of a supporting run and of every refuting and inconclusive shape |

The recorder was also run under the image's own busybox through
`tools/test/make-busybox-wrappers.sh` (every applet it uses is one the image
offers; `wc -c` stands in for `stat`).

## The phases (gate item 1, section 7)

| phase | what happens | expected if option 5 holds |
|---|---|---|
| setup | `compose stop -t 60` of the deployed stack; measurement copies of `mosquitto.conf` (the deployed file plus `max_inflight_messages W`, `max_inflight_bytes 0`, `max_queued_messages Q`, `max_queued_bytes 0`, `persistent_client_expiration 1h`) and of `acl` (plus `topic read $SYS/#` under `user egw-controller`), both hashed; a throwaway container of the pinned image with `--memory 128m` on port 8883, the deployed `certs` and `passwd` read-only, a **fresh named volume**; the guest recorder started | the broker opens its listener; `memory.max` = 134,217,728 |
| P0 (60 s) | the `$SYS` reader alone | `$SYS/broker/version` and the counters arrive |
| P1 (10 s) | `egw-probe-hold` connects: MQTT 3.1.1, `clean_session=False`, `manual_ack=True`, QoS 1 on `c2dt/+/+/telemetry` | SUBACK granted QoS 1 |
| P2 (446.3 s) | A = 4,999 real payloads published at the nominal cadence as `egw-simulator`; the subscriber records and acknowledges nothing | 4,999 distinct deliveries, DUP = 0; `messages/inflight` → 4,999; `dropped` = 0 |
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
`mosquitto.measure.conf`, `acl.measure`, `verdict.json` and the background
clients' own stdout/stderr; `environment/generate/` holds the simulator's
provenance of the generated set. A failed or interrupted attempt is exported
too. No credential is on any command line or in any record: the clients read
their passwords from the environment.

## Restoration

`compose start` of the deployed stack, then the shared "running and healthy"
wait of the G2 drivers; the probe container and its volume removed; the
measurement copies left under `/opt/egw/probe/<attempt>` on the guest (they
are also in the package). The interrupt handler does the same and says on the
final line which state it left the guest in (`stack=… probe=… recorder=…`).
`mosquitto-data`, `mongodb-data`, the sealed evidence and the original
recovery disks are never touched.

## Running it

Local functional check (no guest; a tool check, not evidence):

```bash
# a pinned broker on Docker Desktop with the deployment's dev TLS and auth,
# the measurement lines appended; then the clients against 127.0.0.1:8883
python tools/probe/broker_hold.py generate --work-dir /tmp/gen --out /tmp/messages.jsonl
MOSQUITTO_SIMULATOR_PASSWORD=... python tools/probe/broker_hold.py publish --messages /tmp/messages.jsonl --first 0 --count 50 --ca-cert ca.crt --record /tmp/p2.jsonl
```

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
