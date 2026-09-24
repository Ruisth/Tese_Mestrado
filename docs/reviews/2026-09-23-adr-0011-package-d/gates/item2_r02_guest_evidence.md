# Gate item 2 — `controller_restart-r02`: what the guest-side evidence says

- **Date:** 2026-09-21. **Answers:** item 2 of `decision_request.md:29` ("Is r02's
  guest-side evidence read first?") and item 2 of ADR 0011's "Open before the decision"
  (`adr-0011-controller-restart-recovery.md:1103-1108`).
- **Platform:** every instant and count below comes from an ARM64 guest emulated under
  QEMU/TCG, or from the harness host that drove it. Nothing is native, nothing is a capacity.
- **What was done:** the guest was **not** started. No repository, raw run, attempt,
  `output_test` or project-manager file was modified. The guest's two disk images were opened
  **read-only** (`debugfs` without `-w`; nothing mounted, no ext4 journal replayed) and the
  files named below were copied out into this gate's folder. Nothing was written to either image.
- **Status words** are the ADR's (`adr-0011…md:57-62`): **PROVED** (an artefact line states it,
  or arithmetic on artefact lines gives it), **CONSISTENT-WITH**, **ASSUMED**; otherwise
  *I could not establish*. One rule is added here, in section 3: a fact that rests only on
  **recovered residual bytes** is at most CONSISTENT-WITH.

**Abbreviations used for sources.** `GATES` is this note's folder, `gates/` of the package
(`scratchpad/pkgD/v2/gates/`).
`[G:X]` is block X of `GATES/out/item2_r02_guest_evidence.out.txt` (output of
`GATES/scripts/item2_r02_guest_evidence.py`), cited with its line as `out:N`.
`RAW` is `/home/ruisth/egw-tcg/pilot/results/raw/controller_restart-r02/`.
`CAP` is `/home/ruisth/yocto/evidence-candidates/2026-09-19-sampler-fix/`; the files of it cited
here are byte-identical in `output_test/runs/2026-09-19/HIST_2026-09-19-sampler-fix/raw/2026-09-19-sampler-fix/`
(SHA-256 compared for `boot/sampler-01.log`, `host/acceptance.log`, `host/acceptance2.log`, `driver.log`).
`ROOTFS` is `/home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4`;
`DATA` is `/home/ruisth/yocto/egw-integrated/egw-data.img`.
`J` is the guest's persistent journal file
`/var/log/journal/164be2431eb24037a415dd1641011fa6/system@1ce5b55b1e384e95abac528e90f476a9-0000000000002a76-00065bcaad8a43ea.journal`
in `ROOTFS` (boot `f99873bd9ff940259ae1135c277d9d86`, entries 2026-09-18T23:58:33Z to
2026-09-19T00:29:22Z), cited by entry time. `REC` is
`GATES/item2_extract/data_disk_jsonlog_2026-09-19T00.txt`, cited by byte offset in `DATA`.
Code anchors are at the merged `dev` head `35fe8bb`, as in the ADR.

---

## 1. The answer

1. **Not preserved where it was looked for.** None of the three places named — the raw
   run, the candidate capsule, the historical packages — holds the broker's log, the
   controller's log, the container states or the journal around the restart (section 2).
   The capsule holds only the guest's serial console (kernel lines), host-side logs and
   guest state files taken before and after the run, not during the restart.
2. **Preserved, unintentionally, on the guest's own disks**, and readable without starting
   the guest: (a) the persistent journal of the guest boot in which r02 ran, and (b) the
   guest's own, complete copy of r02's `events.jsonl`, both intact files on `ROOTFS`; (c) the
   broker's and the controller's container logs, which were deleted with their containers on
   2026-09-20 but survive as **residual bytes in free blocks** of `DATA` (section 3). The
   twins' state after r02 was never recorded and was not read.
3. **How the old process stopped — PROVED from `J`:** it was sent signal 15 no later than
   00:18:19.708Z; the engine logged at 00:18:29.708Z that it "failed to exit within 10s of
   signal 15" and forced the stop; the exit status recorded is 137, at 00:18:30.166Z. The
   same container was started again at 00:18:33.602Z (section 4).
4. **What the broker saw — CONSISTENT-WITH (recovered lines):** the old client
   `egw-controller-egw-01` had one uninterrupted connection from 00:03:32.618Z, with clean
   session flag `c1`, and disconnected at 00:18:19.877Z, 0.17 s after the latest possible
   instant of signal 15 and 10.1 s **before** its last outcome line. The new process
   connected at 00:18:48.375Z, again with `c1`, and its subscription was logged at
   00:18:48.420Z. No line reports messages queued or dropped for the controller (section 5).
5. **The three restart classes change** (section 6): at least 1,809 and at most 1,817
   received by the old process and left without an outcome line (was 1,809 to 1,985);
   **319 to 321** published while no subscription existed (was 151 to 327); **5 to 7**
   undetermined (was 176). None of the 2,136 obtained an outcome line, in the complete
   guest log — PROVED; whether the one in flight at the kill (`smart_clothing` seq 1422)
   reached its twin is not established (section 7).
   The end-of-run block of 765 was accepted late, all of it, none twice — PROVED.
6. **For the decision:** item 2 can be answered "read" — it has been read, and it confirms
   Finding 2 of the protocol proposal. Nothing in it argues against option 5; it confirms
   that both halves of option 5 address a real class. It adds one urgent condition: the
   residual bytes are perishable and should be preserved before the guest is booted again
   (section 9).

---

## 2. Where the evidence was looked for

| place | what it holds about r02 | broker log, controller log, container states, journal? |
|---|---|---|
| `RAW` | `manifest.json`, `sent_events.jsonl`, the harness copy of `events.jsonl`, `controller_metrics.csv`, the collector file, the simulator's logs (listing of `RAW`) | **none** |
| `output_test/runs/2026-09-19/HIST_controller_restart-r02/` | a byte copy of `RAW`: 13 files, every source under `RAW` (`export_manifest.json`; `sources.json:6`) | **none** |
| `CAP` (and `HIST_2026-09-19-sampler-fix`) | `host/acceptance.log`: the harness-side log of tests 1 and 6 (`:1-108`); `boot/sampler-01.log`: the guest's serial console for the whole session; `guest/*.txt`: eleven taken from 23:59Z to 00:04Z, before the run, and two at 00:26Z–00:27Z, after it (file times); none covers the restart | **journal: no.** The console carries kernel lines only; among them the controller's network endpoint being removed and re-created at kernel time 1209.30–1213.31 s (`boot/sampler-01.log:563-578`) |
| `HIST_egw-tcg-itest-host-dir-2026-09-19` | `raw/itest/controller_restart-r02.twins.before.json`: the "before" twin snapshot | **none**; the "after" snapshot was never taken |
| the other `HIST_*` of 2026-09-19 | nothing that names r02 | none |

Why the capsule has no journal: the session `sampler-01` (opened 2026-09-18T23:58:16Z,
`CAP/driver.log:3-5`) was never closed with its closing script, which would have saved
`journalctl -b` and the final container state (`CAP/scripts/session_close.sh:15-16`); no
`guest/journal-sampler-01.txt`, `guest/final-state-sampler-01.txt`,
`sampler-01.session.status` or `boot/sampler-01.status` exists in `CAP` (listing). The twin
snapshots: before the run all three r02 devices had no twin (`"exists": false`,
`CAP/host/acceptance.log:39-77`); after it, "'after' snapshot NOT taken - delta not run"
(`CAP/host/acceptance.log:90`). A search by r02's device UUIDs of `output_test`,
`/home/ruisth/egw-exec/attempts` and `/home/ruisth/egw-tcg/itest` found them only in the
"before" snapshot, in `acceptance.log` (which prints it) and in the historical copy of the
run itself.

**Correction to the proposal's wording.** It locates r02's "full event log on the data disk"
(`docs/governance/proposals/acceptance_protocol_update_2026-09-19.md:419-421`). The event
directory `/opt/egw/deployment/data/events` is on the root filesystem: the data disk is
mounted only at `/var/lib/docker` (`ROOTFS:/etc/fstab`, last line).

---

## 3. What was read from the guest disks, and what kind of evidence each is

No guest was running (`pgrep qemu-system-aarch64` empty, checked by both scripts before
reading). Commands, outputs and hashes are in section 10.

**Guest files (intact, allocated).** Copied with `debugfs -c` (read-only) by
`GATES/scripts/item2_extract_guest.sh`; record in `GATES/item2_extract/extraction_record.txt`.

- `J`, 8,388,608 bytes, archived at the next boot (inode mtime 2026-09-19T19:33:59Z), read with
  `journalctl --file`. It is the system's own log, never collected by the harness and not
  sealed. Its lines are treated as artefact lines.
- The guest copy of `/opt/egw/deployment/data/events/controller_restart-r02/events.jsonl`,
  1,522,738 bytes, last modified 2026-09-19T00:25:47Z (inode mtime). Its first 1,267,723
  bytes have the SHA-256 of the harness copy, `8899f993…4cd58`: the harness copy is an exact
  prefix of it [G:R02.E0, out:3-5]. Treated as an artefact.

**Recovered residual bytes (not files).** The containers that ran r02 — broker
`c63352d738f2…` and controller `9b2098915ade…` (names from
`output_test/runs/2026-09-19/20260919T193345Z_guest-session_attempt01/guest/final-state-s1.txt:9`
and its `docker ps -a` block) — were removed and recreated on 2026-09-20: every container
on `DATA` today was created at 2026-09-20T23:35:02Z (`config.v2.json` of each, read
read-only). Their json-file logs (`compose.yaml:46-52`, `driver: json-file`) went with them.
`GATES/scripts/item2_carve_data_disk.py` searched `DATA` for the fixed string
`"time":"2026-09-19T00:` and parsed the enclosing log line: 43,502 occurrences, 43,499
parsed lines, 3 unparsed (`REC`, header). **All 3,755 blocks holding them are free and owned
by no inode** (`GATES/item2_extract/data_disk_jsonlog_blocks.txt`, header). They are what is
left of deleted files: no seal, no guarantee of completeness, overwritable by any later
write to `DATA`.

**Why the recovered lines are nevertheless used, and how far.** They agree with preserved
artefacts to the millisecond:

- each of the 504 outcome lines the old process wrote from 00:17:00Z to its death has one
  distinct recovered Ditto `PATCH … 204` line for the same thing within 49.1 ms of its
  acknowledgement stamp, and no recovered `PATCH 204` line in that span is left unmatched
  [G:C3, out:112];
- after the last answered poll: 58 outcome lines, 58 `PATCH 204` lines [G:C5, out:114];
- the recovered broker lines run without a silence longer than 35 s from 00:03:32.5Z to
  00:28:44.6Z (136 lines) [G:B3, out:84], against a healthcheck every 30 s
  (`mosquitto.conf:42-45`) and a store autosave every 60 s (`mosquitto.conf:35`);
- the subscription instant they give falls between the last block member's publication and
  the next identity's (section 6), as it must.

So, in this note, a fact that rests only on recovered lines is **CONSISTENT-WITH**, never
PROVED; facts from `J`, the guest event log and the raw run keep the ADR's statuses.

---

## 4. The restart, as the guest recorded it

Guest wall clock, with the harness wall at the marker offset: guest minus harness =
−0.044 s (`RAW/manifest.json:87-96`: `wall_utc` 00:23:15.448Z, `polled_utc` 00:23:15.492Z).
Near 00:18:48Z the boundary identities bound that offset to between −0.129 and −0.024 s
[G:P4, out:129].

| guest wall (Z) | harness wall (Z) | event | source | status |
|---|---|---|---|---|
| 00:03:14.171 | — | controller container `9b2098915ade…` started for this session | `J` entry 00:03:14.170857 [G:J2, out:66] | PROVED |
| 00:03:32.618 / .634 | — | broker: controller connects `(p2, c1, k60, u'egw-controller')`; subscription `c2dt/+/+/telemetry` QoS 1 | `REC` 400588507, 400588700 [out:76-77] | CONSISTENT-WITH |
| 00:18:15.476 | 00:18:15.344 (hook start) | an SSH session from the host opens (the restart hook `docker compose … restart controller`, `RAW/manifest.json:154-164`) | `J` 00:18:15.476209, 00:18:16.192271 | session PROVED; that it is the hook, CONSISTENT-WITH (it closes at 00:18:36.084Z, the hook returned at 00:18:36.134Z harness) |
| 00:18:19.399 | 00:18:19.443 | last answered poll of the old process: `accepted` 1,872, `queue_depth` 1,867 | `RAW/controller_metrics.csv:307` | PROVED |
| ≤ 00:18:19.708 | ≤ 00:18:19.752 | **signal 15 sent** (10 s before the engine's timeout line) | `J` 00:18:29.716576 [out:44] | PROVED that signal 15 was sent with a 10 s timeout; the instant is arithmetic on that line |
| 00:18:19.763 / .868 | 00:18:19.807 / .912 | uvicorn: "Shutting down"; "Waiting for application shutdown." | `REC` 410341299, 410341702 [out:102-103] | CONSISTENT-WITH |
| 00:18:19.874 | 00:18:19.918 | controller: "MQTT disconnected", reason "Normal disconnection" | `REC` 410341816 [out:104] | CONSISTENT-WITH |
| 00:18:19.877 | 00:18:19.921 | broker: "Client egw-controller-egw-01 disconnected." | `REC` 400599754 [out:78] | CONSISTENT-WITH |
| 00:18:19.9 → 00:18:29.990 | → 00:18:30.034 | old process keeps writing outcome lines: 56 after "Shutting down", ending at `events.jsonl:1594` (`smart_clothing` seq 1421) | [G:C6, out:115]; `pkgD/v2/out/adr0011_figures.out.txt:81` (R02.5) | count CONSISTENT-WITH; last stamp CONSISTENT-WITH (cross-clock) |
| 00:18:29.708 | 00:18:29.752 | **engine: "Container failed to exit within 10s of signal 15 - using the force"** | `J` 00:18:29.716576 [out:44] | PROVED |
| 00:18:30.103 | 00:18:30.147 | container scope deactivated; 3 min 18.105 s CPU consumed | `J` [out:45-46] | PROVED |
| 00:18:30.166 | 00:18:30.210 | **exit status 137** recorded; `hasBeenManuallyStopped=true`, the restart policy not applied ("restart canceled") | `J` 00:18:30.932619 [out:50] | PROVED |
| 00:18:31.36, 00:18:32.36 | — | SSH forward to port 8000 refused: no controller HTTP listener | `J` [out:51, 59] | PROVED |
| 00:18:31.47 → 00:18:31.89 | — | old network endpoint (bridge port 6) removed, new one created | `J` [out:52-58]; `CAP/boot/sampler-01.log:563-574` | PROVED |
| 00:18:33.602 | 00:18:33.646 | same container `9b2098915ade…` started again | `J` [out:62] | PROVED |
| 00:18:48.166 / .192 | — | new process: "Started server process [1]"; "Uvicorn running" | `REC` 410359070, 410359400 [out:105-108] | CONSISTENT-WITH |
| 00:18:48.375 | 00:18:48.419 | **broker: controller connects `(p2, c1, k60, u'egw-controller')`**; controller: "MQTT connected; subscription requested" at 00:18:48.415 | `REC` 400600466, 410359542 [out:79, 109] | CONSISTENT-WITH |
| 00:18:48.420 | 00:18:48.464 | **broker: subscription QoS 1**; controller: "subscription granted; bridge ready", `granted_qos` 1 | `REC` 400600659, 410359864 [out:80, 110] | CONSISTENT-WITH |
| 00:18:48.504 | 00:18:48.548 | first delivery to the new process (`events.jsonl:1595`) | `pkgD/v2/out/adr0011_figures.out.txt:83` (R02.5) | CONSISTENT-WITH (cross-clock) |
| 00:25:47.887 | 00:25:47.931 | the last r02 outcome line ever written | [G:R02.E4, out:16]; inode mtime 00:25:47Z | PROVED |

What the timeline settles about the stop. Signal 15 was sent at most 0.31 s after the last
answered poll. The engine waited 10 s, then forced the stop, and recorded 137, which is
128 + 9, the number of SIGKILL (arithmetic on `J`'s line; that the engine encodes a signal
death this way is not stated by any permitted source, so the name "SIGKILL" is read from
the number). The old process did not stop draining at signal 15: it disconnected from the
broker first, then went on writing outcomes until 0.18 s before the recorded exit. The
recovered lines hold no "Application shutdown complete." for it, whereas the graceful stop
at the end of the session has one (`REC` 411324951, 00:28:41.357Z) — CONSISTENT-WITH a
drain cut short; an absence among residual bytes proves nothing on its own.

The order observed — DISCONNECT, then drain — is the one the ADR reads from the source:
`bridge.stop()` then `await service.stop()` and `await pipeline_task`
(`src/egw_controller/app.py:159-162`), `stop()` calling `disconnect()` then `loop_stop()`
(`src/egw_controller/mqtt.py:211-215`). The reason text "Normal disconnection" is, in
paho-mqtt 2.1.0, the name of reason code 0 for DISCONNECT
(`paho/mqtt/reasoncodes.py:51`, analysis environment `~/egw-exec/venv`).

---

## 5. What the broker recorded about the controller's session

All from recovered lines, so CONSISTENT-WITH at most.

- **Clean session, both times.** Both connections of `egw-controller-egw-01` carry `c1`
  [out:76, 79]. The ChangeLog records, since version 1.2, that the broker's connect line
  shows the client's clean-session and keepalive status (section "1.2 - 20130708",
  copy in `GATES/sources/ChangeLog.txt:2815-2816`), and the keepalive field beside it, `k60`,
  matches the controller's `_KEEPALIVE_S = 60` (`src/egw_controller/mqtt.py:31`); the
  manual does not define the fields, so reading `c1` as the clean-session flag is
  CONSISTENT-WITH, not PROVED. Under MQTT 3.1.1, with CleanSession 1 the
  session "lasts as long as the Network Connection" and its state must not be reused
  (OASIS MQTT 3.1.1, section 3.1.2.4, [MQTT-3.1.2-6]). This moves the ADR's "ASSUMED for the
  image" clean session (`adr-0011…md:363-371`) to CONSISTENT-WITH for r02.
- **One subscription per connection**, `c2dt/+/+/telemetry` at QoS 1, logged 16 ms and 45 ms
  after each connect [out:77, 80]; the controller's own lines report `granted_qos` 1 [out:110].
- **One uninterrupted old connection.** No other line for this client between 00:03:32.618Z
  and 00:18:19.877Z [G:B1, out:76-81], in a sequence with no silence over 35 s [out:84].
- **Nothing queued or dropped is reported.** No recovered broker line stamped
  2026-09-19T00 mentions dropped, queued or outgoing messages (the filter of [G:B1]: only
  the six controller lines at out:76-81 pass it). The ChangeLog records, since release
  1.3, that the broker logs when a client's outgoing messages begin to drop off the end of
  its queue (section "1.3 - 20140316", `GATES/sources/ChangeLog.txt:2679-2680`). Whether
  2.0.22 still does, at which log type, and whether the deployed log types
  (`mosquitto.conf:48-53`) include it, *I could not establish* (not established; the broker
  measurement of `gates/item1_broker_limits.md`, section 7, answers it), so the absence of
  such a line here does not by itself show that nothing was dropped. With `c1` there is no
  session left to queue into once the client is gone (MQTT 3.1.1, section 3.1.2.4).
- **Store autosave** at 00:18:37.518Z, inside the outage [out:89], as configured
  (`mosquitto.conf:33-35`).
- **The publisher was steady.** `egw-simulator-controller_restart-r02` connected once, at
  00:13:15.499Z (`c1`, `k30`), and disconnected at 00:23:15.397Z [out:82-83], as its own log
  says (`RAW/logs/simulator.log:2`, `dropout_disconnects=0`).
- `p2` is not interpreted here: in 2.0.x the protocol number in this log line is an
  internal Mosquitto value, changed to the MQTT number only in 2.1.0 (ChangeLog, section
  "2.1.0 - 2026-01-29", `GATES/sources/ChangeLog.txt:71-72`); which protocol version
  internal value 2 denotes *I could not establish* from the permitted documentation. The
  client library's default protocol is MQTT 3.1.1 (`paho/mqtt/client.py:739`, analysis
  environment).

---

## 6. The three restart classes, before and after

The internal block is `sent_events.jsonl:1595-3730`, 2,136 identities, first published
00:15:37.744Z and last 00:18:48.444Z (harness wall) [G:P0, out:124]. Its cut on the
broker's and the controller's instants [G:P1, out:126-133]:

| reading of the two instants | ≤ last answered poll | poll → old disconnect | old disconnect → new subscription | after the subscription |
|---|---:|---:|---:|---:|
| broker json times, marker offset | 1,810 | 6 | 320 | 0 |
| controller's own stamps, marker offset | 1,810 | 6 | 320 | 0 |
| earliest disconnect ("Shutting down"), broker subscription | 1,810 | 5 | 321 | 0 |
| broker json times, offset −0.129 s | 1,810 | 7 | 319 | 0 |
| broker json times, offset −0.024 s | 1,810 | 6 | 320 | 0 |

Two checks on the cut. All 320 identities published between the disconnect and the
subscription (json times) are `sent_events.jsonl:3411-3730`, and none has an outcome in
the complete guest copy; all of the first 200 published after the subscription have one
[G:P3, out:135-136]. The block ends 20 ms before the subscription line and the next
identity follows 79 ms after it (harness wall) [out:124-126].

| class (ADR 0011) | ADR 0011 today | after the guest evidence | status now |
|---|---|---|---|
| **received by the old process and left without an outcome** ("at least 1,809 discarded from the volatile queue") | at least 1,809, at most 1,985; arithmetic PROVED, "still queued when the process stopped" ASSUMED, "discarded" ASSUMED, the SIGKILL ASSUMED (`adr-0011…md:115-141`, `:196-199`, `:248-250`) | **at least 1,809, at most 1,817.** The 1,810 published by the last answered poll were all published while the old subscription existed. The process was forced to stop 10 s after signal 15 (exit status 137) while still writing outcomes, and **none of the 1,810 ever obtained an outcome line** from any process | lower bound: arithmetic PROVED, unchanged. Stop mode: **PROVED** (was ASSUMED). None obtained an outcome line: **PROVED** in the complete guest log (was PROVED only for the fetched copy); whether the one in flight at the kill (`smart_clothing` seq 1422, `sent_events.jsonl:1595`) reached its twin is not established (section 7). Still in the old process's queue at the kill: **CONSISTENT-WITH** (was ASSUMED); the one-by-one reading still rests on the counter source reading (`service.py:414-415`). Upper bound 1,817: CONSISTENT-WITH |
| **published while no subscriber existed** ("at least 151 and at most 327") | 151 to 327; both ends from cross-clock cuts on the old process's last acknowledgement and a collector row; the class name rests on the clean session, ASSUMED (`adr-0011…md:199-209`) | **319 to 321** (320 on the broker's own times): everything published from the old client's disconnect (00:18:19.877Z) to the new subscription (00:18:48.420Z), a 28.5 s window with no subscription for the controller's client id. Both connections logged `c1`. None ever obtained an outcome line | count: **CONSISTENT-WITH** (recovered instants, cross-clock at a bounded offset). None obtained an outcome line: **PROVED**. "For want of a session": **CONSISTENT-WITH** (was ASSUMED). The clock-free upper bound 327 still holds |
| **the undetermined rest** | 2,136 − 1,809 − 151 = 176, between the two bracketed classes (the ADR's G2 = 119 and G3a = 56, plus the residual identity) | **5 to 7**: published after the last answered poll and before the old client's disconnect; whether each reached the old client before it disconnected *I could not establish* | bounds CONSISTENT-WITH |

**The main correction.** The ADR cut G2 and G3a on the old process's **last
acknowledgement** (00:18:30.034Z harness) and on a collector row (`adr-0011…md:177-193`).
The old process's **subscription** had ended 10.1 s earlier, at signal 15. So 113 of G2's
119 and all 56 of G3a were published while no subscription existed; they belong with G3b
(151) in the no-subscriber class: 113 + 56 + 151 = 320.

The earlier triple 1,810 / 195 / 131, which the ADR already refuses as a measurement
(`adr-0011…md:212-217`), is superseded by 1,810 (+ up to 7) / 320 / 6 on the same reading.
It is still written in the historical package's reason field
(`output_test/runs/2026-09-19/HIST_controller_restart-r02/attempt.json:13`, `SUMMARY.md`);
that folder is read-only here and was not changed.

---

## 7. Other statements of ADR 0011 that this evidence moves

| ADR 0011 | says today | the guest evidence | status now |
|---|---|---|---|
| §1.5, `:241-250` | SIGTERM then SIGKILL about 10 s later, CONSISTENT-WITH; "ASSUMED: the SIGKILL itself … no artefact records the engine's default" | signal 15, a 10 s wait, a forced stop, exit status 137 (section 4) | **PROVED** for this stop (the name SIGKILL read from 137) |
| §2(f), `:382-389` | the engine's stop timeout decides how much of the drain happens; "no artefact records its value" | "within 10s of signal 15" | the value that applied to r02's stop, 10 s: **PROVED**. The engine default in general: *I could not establish* from the permitted sources |
| §1.4, `:227-230` | no redelivery after the restart, CONSISTENT-WITH (reasoning from the code) | none of the 2,136 has an outcome in the complete guest log; no identity has two `accepted` lines [G:R02.E2-E3, out:8-13]; both sessions `c1` | no redelivery happened: **PROVED** as an outcome; the mechanism (clean session) CONSISTENT-WITH |
| §1.6, `:258-260` | the end-of-run blocks: late or never processed, *I could not establish* | r02: all 765 of `sent_events.jsonl:5956-6720` accepted, all after the deadline, the last 92.440 s after it, none twice [G:R02.E2-E4, out:8, 13-17]. r01: all 422 of `:6299-6720` accepted late, the last 43.713 s after the deadline [G:R01.E3-E4, out:33-37] | **PROVED**: late, not lost, in both runs |
| §1.6, `:267-273` | guest-side evidence not read; whether it still exists, *I could not establish* | read (this note); what exists is listed in section 3 | — |
| §1.6, `:264-266` | whether the `PATCH` of the in-flight identity (`smart_clothing` seq 1422) reached Ditto, *I could not establish* | no `PATCH 204` line was logged by the old process after its last outcome line [G:C4, out:113] | CONSISTENT-WITH "no 2xx response received"; a `PATCH` applied by Ditto whose response never arrived is not excluded: *I could not establish* whether the twin carries it |
| code identity, `:42-49` | "ASSUMED: that the controller image in the guest was built from that source … unpinned" | the container that ran r02 (`9b2098915ade…`, `J`) has image `sha256:2e30d8fcf921…`, source commit `0dfa531`, `paho-mqtt==2.1.0`, `uvicorn==0.53.0` (`output_test/runs/2026-09-20/20260920T232447Z_g2-gate-preconditions_attempt01/environment/container_identities.txt:6, 10, 14, 45, 54`; `ROOTFS:/opt/egw/evidence/controller-image-verify.txt:1-8`); `git diff --stat 0dfa531 35fe8bb -- src/egw_controller src/Dockerfile src/pyproject.toml` is empty | **CONSISTENT-WITH** (two artefact lines joined on the container id, which rests on a container keeping the image it was created from). Note: uvicorn in the image is 0.53.0, not the 0.52.1 read in the analysis environment (`adr-0011…md:375-376`) |

---

## 8. What stays open

- **The twins' ingestion counters after r02.** Never snapshotted (`CAP/host/acceptance.log:90`);
  they exist, if at all, only in MongoDB's files in the `mongodb-data` volume on `DATA`
  (`compose.yaml:323-325`), which were not read. A later read would settle the in-flight
  identity: `accepted_count` is "the post-update total of confirmed messages for the device
  … seeded from the twin" (`src/egw_controller/ditto.py:56-57`, written at `:68-75`;
  seeded at `src/egw_controller/dedupe.py:78-80`), and the complete guest log holds 4,092
  `accepted` lines for `smart_clothing` [G:R02.E5, out:18]. 4,093 on its twin would mean the
  in-flight `PATCH` reached it (the N1 case); 4,092 would mean it did not.
- **The 5 to 7 identities** published between the last answered poll and the old client's
  disconnect: received or not, *I could not establish*.
- **The exact instant of signal 15:** only bounded, at or before 00:18:19.708Z (`J`) and
  before uvicorn's "Shutting down" at 00:18:19.763Z (recovered).
- **Whether the broker's text "Client … disconnected." denotes a client DISCONNECT** rather
  than another cause: the permitted documentation does not define its log texts; the
  controller's own recovered line says "Normal disconnection".
- **The admissibility of residual bytes as evidence** is the student's call (section 9).
- r01 was not asked about. Its guest event log was read (section 7); residual broker lines
  for its restart also exist in `DATA` (a disconnect at 2026-09-18T21:55:28Z and a `c1`
  reconnect at 21:55:59Z, offsets 390387439-390388192, found in a first probe). They were
  not analysed further, and r01's journal was not extracted.

---

## 9. Consequence for the decision

**Item 2 of the decision request.** The repository's proposal asks for Finding 2 to be
confirmed or refuted "from the guest-side evidence of `controller_restart-r02`: its full
event log …, the twins' ingestion counters and the controller container logs, read-only",
before the design decision (`acceptance_protocol_update_2026-09-19.md:418-428`, `:452-454`).
Two of the three have now been read without starting the guest: the full event log (an
intact file) and the controller's log (recovered bytes). The broker's log and the journal,
which the proposal did not name, were read too. The twins' counters were not. What was read
**confirms** Finding 2 (`:376-399`): the old process was stopped by force with its queue
still being drained, none of the 2,136 obtained an outcome line or was redelivered
(whether the one in flight at the kill reached its twin is not established), and the
restart opened a 28.5 s window in which the broker kept nothing for the controller's
clean session.

**Option 5.** Nothing here rules it out. The evidence sharpens its premise: in r02, about
1,810 identities were left without an outcome line inside the controller (the class that
acknowledging after the outcome line addresses) and about 320 were never delivered for want
of a session (the class that a persistent session addresses); on the ADR's reading of each
half (`adr-0011…md:630-632`), neither half alone would have kept both classes at the broker
for redelivery after the restart.
It also gives three sizing inputs, observations of one emulated run and not bounds: the
engine's 10 s stop allowance cut a drain short, so `stop_grace_period` has to be set
explicitly, as the ADR already proposes (`adr-0011…md:654`); a restart under this load
left the controller's client id without a subscription for 28.5 s, 320 publications at
11.2 msg/s, which the per-client queue bound of item 1 has to hold on top of the
unacknowledged window; and the new process needed 14.8 s from container start
(00:18:33.602Z) to its subscription (00:18:48.420Z).

**Conditions.**

1. **Preserve before the next boot.** The recovered broker and controller lines sit in free
   blocks of `DATA`; any later guest session can overwrite them. The copies in
   `GATES/item2_extract/` live in a session working directory that will not survive. The
   student, or whoever may write there, should copy `J`, both guest event logs, `REC`, its
   block map and the extraction record, with `GATES/out/item2_extract.SHA256SUMS.txt`, into
   an evidence package before the guest is started again; a read-only image copy of `DATA`
   would keep the residual bytes whole.
2. **Record the corrected classes in ADR 0011** — sections 1.3 to 1.6, 2(e), 2(f) and the
   code-identity paragraph, as in sections 6 and 7 — marking what rests on recovered bytes.
3. **Decide the evidential standing of recovered bytes.** If they are not admitted, the
   PROVED results of this note still stand (the forced stop, exit status 137, the 10 s
   timeout, the old process still writing outcomes when the stop was forced, the complete
   guest event log, the end-of-run blocks), while the no-subscriber class returns to the
   ADR's bracket of 151 to 327 and the first class's upper bound to 1,985.

---

## 10. Reproduction

All read-only. Run from WSL (`wsl -d Ubuntu-24.04 --exec bash -lc '…'`):

1. `bash GATES/scripts/item2_extract_guest.sh` — copies `J`, the runtime journal flushed at
   boot and the user journal of the same boot, and both restart runs' guest `events.jsonl`
   out of `ROOTFS` with `debugfs -c`; writes `GATES/item2_extract/extraction_record.txt`
   (inode times and SHA-256 of each copy). It stops if a `qemu-system-aarch64` process is running.
2. `python3 GATES/scripts/item2_carve_data_disk.py` — the fixed-string search of `DATA` and
   the block-allocation check, in one read-only `debugfs` session; writes `REC` and
   `GATES/item2_extract/data_disk_jsonlog_blocks.txt`. Same guard.
3. `~/egw-exec/venv/bin/python GATES/scripts/item2_r02_guest_evidence.py >
   GATES/out/item2_r02_guest_evidence.out.txt` — every figure of this note (blocks R02, R01,
   J, B, C, P, X). Its clock mappings are those of `pkgD/v2/scripts/adr0011_figures.py`.

Inputs: `RAW` (`manifest.json`, `sent_events.jsonl`, `events.jsonl`,
`controller_metrics.csv`) and the r01 equivalents; `ROOTFS` and `DATA` (images last written
2026-09-20T23:39Z, host file times); `CAP`; the `output_test` files cited. Documentation
used: the Eclipse Mosquitto ChangeLog and the OASIS MQTT 3.1.1 specification, as copied in
`GATES/sources/` (hashes in `GATES/sources/SHA256SUMS.txt`); paho-mqtt 2.1.0 source in
`~/egw-exec/venv`. Hashes of every extracted file: `GATES/out/item2_extract.SHA256SUMS.txt`.
Opening the images may have updated their access time on the host file system; their
contents were not written. During exploration two scratch files were briefly written
outside this folder (a search probe in WSL `/tmp`, a helper in Git Bash `/tmp`); both were
deleted and neither is used here.
