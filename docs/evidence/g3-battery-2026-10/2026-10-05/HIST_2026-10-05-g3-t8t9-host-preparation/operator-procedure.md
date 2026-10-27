# G3 — session S3 (tests 8 and 9): operator procedure (2026-10-04)

For the host-preparation package of S3. It is the working detail behind the request of 2026-10-04 (sections 4 to 6)
and its decision summary, and changes no rule of either: where they differ, the decision summary governs, then the
request. The steps script and its halts are described in `g3_battery.README.md`. G3 stays `Not decided`.

## Before the window

- The sealed preparation package is with Rui; S3 starts only on his explicit authorisation of the session and his
  «estou presente» in the window. Nothing of S3 is run before both.
- Host: two detached keepalive clients (`exec sleep 43200`) with at least 6 h left, Windows kept awake, no other load,
  no QEMU process, no open session. Identity: procedure and tools `8e49261` (tree `2f05148`); the candidate unchanged
  (no build, no image load, no configuration change); identifiers `-q2`; state directory `~/egw-exec/g3-t8t9-s3`.

## Sequence (one subcommand per invocation; long ones detached, launch lines in the README)

1. `open S3` — identities, row files, identifiers, root file system (`22e9da85…`), keepalive, then the frozen
   `guest_session_open.sh`, `preflight.sh`, the environment copy, `gate_health.sh`, the guest's event-directory
   listing. The preflight's stack start is the prescribed one and the only one of S3.
2. `row t8` (ceiling 135 min from the row's start, the 900 s wait included) — the gate record against S2's, the
   attempt (`…_g3-qualification-t8_attempt02`), the QEMU reading (no `-no-reboot`), line a, the wait, the same QEMU
   process, lines b to f, the previous boot's journal and kernel OOM lines, the gate (no comparison across the reboot).
3. Read the consoles and files; read the state recorded after T8 and the previous boot's OOM lines (an OOM kill in
   either, or a restart after the reboot, is a halt: T9 is not run). `classify t8 <status> <validity> <outcome>
   <reason> <next-action>`.
4. `row t9` (ceiling 25 min) only if T8 is classified, no halt is recorded and T8's gate passed — also after a T8
   whose smoke completed (`TEST STATUS itest-post-reboot-01-q2: … PROCEDURE COMPLETE`, no `STOP:`) and failed only its
   timed delivery: T8 stays failed. Steps (a), (b), (c), (d)+(e), the exposure checks; the gate; `classify t9 …`.
5. `close` — the controlled close below.
6. Every export verified (the export tool's own verification, then `sha256sum -c` in each package); the operator
   records sealed (`HIST_<UTC date>-g3-t8t9-s3-operator-records`, after a secret sweep); the result note
   `output_test/decisions/<date>_g3-t8-t9-results.md`: each row's validity, functional outcome and timed delivery
   stated apart, the packet's classes, no G3 claim. Keepalive and keep-awake released.

No row starts at or after 3 h of host uptime from the `UP0` taken at open. A row past its ceiling receives
`term <slug>` (TERM to its process group, never KILL, never QEMU), is exported as interrupted, and the session closes.

## Stop conditions (request, section 5)

Each halts the session: nothing is repeated, the open row is classified and exported as it stands, the session is
closed in a controlled way whenever the guest answers, and it is handed back to Rui.

1. At open, preflight, gate or the start of a row: the clone not at `8e49261` or not clean; a runbook, helper, tunnel
   or CA hash that differs; an identity that differs (the kernel, `qemuboot.conf`, the QEMU binary, the Yocto
   checkout and, before T8, the gate's record of the running images included); the root file system not at the
   expected value; an identifier not fresh; a frozen driver ending non-zero; the environment copy failing.
2. Instrumentation: a step status 97 or 74; an export, transcript, marker, fetch or snapshot failure; a usage exit 2
   of `delta`.
3. A failed gate: a service not healthy within the gate's wait; a recorder or collector unit active; in T9's gate an
   OOM kill, a restart or a replaced container; for T8 the operator's reading of item 3 of the sequence.
4. Test 8, lines a to e: `-no-reboot` on QEMU's command line before line a; any `STOP:`; the guest not answering with
   a different boot id within the wait; after the reboot no QEMU process, more than one, or one that is not the same
   process on the same disks; the tunnel not up after line d. **Test 9 is then not run.**
5. Test 8's smoke: no `TEST STATUS … PROCEDURE COMPLETE` line, or a `STOP:`. (With that line and no `STOP:`, `lost`
   or `late_confirmations` above 0 is a classified failure of T8, not a halt.)
6. Test 9: a `STOP:` ends T9 as it stands; an inconclusive probe is not repeated with a new tag.
7. Guest, tunnel, WSL or keepalive lost, other than through T8's own reboot.
8. A row past its ceiling, or the cut-off.
9. Any restoration (the runbook's own only: a capture cleanup, `tunnel_down && tunnel_up` outside line d): record,
   halt. **As clarified by the decision summary (condition B):** the prescribed initial preflight may start the
   unchanged stack before T8. What is forbidden is any manual or aided start, restart or recreation after the reboot
   (`compose up`, `start`, `restart`, `docker start`), and any recovery that would let a failed row continue. Line d's
   tunnel step and the normal safe-close operations stay; none of them is presented as unaided recovery of the
   containers.

Not done without Rui's decision: any fix; any repeat; a new identifier for a refused row; any change to code,
configuration, helpers, thresholds or `DRAIN_*`; a re-launch of QEMU; any signal to QEMU.

## Classification (request, section 6; the packet's classes; none of these is a pass)

`classify` pairs: pass `valid/pass`; valid failure of the system `valid/fail`; invalid instrumentation
`invalid/unknown`; inconclusive / not demonstrated `valid/inconclusive` (`unknown/inconclusive` when unreadable); not
started `not-applicable/not-run`. The observed cause and the evidence control; a `STOP:` is never instrumentation by
default, and an incomplete row is never a pass. A pass needs every Expected item of the runbook, read from the printed
values and the saved files (`PROCEDURE COMPLETE` alone is no verdict).

| Class | Test 8, corrected procedure |
|---|---|
| Valid failure of the system | the stack not ready within 3,600 s (line e); the six containers not returned unaided (line c: the last read ended with exit status 0 and listed another set); an event directory missing; `/var/lib/docker` on another source, or not mounted (`findmnt` exit 1 with nothing printed); the twins DIFFERENT; `started_at` unchanged (line e); the smoke's `lost` or `late_confirmations` above 0, or a `delta` MISMATCH (cause not established) |
| Invalid instrumentation | the boot id unreadable or not of the kernel's form; the event-directory or mount read ended by its timeout or by ssh (124, 255); the tunnel not reopened; a snapshot, marker, fetch, transcript or export failure; a usage exit 2 |
| Inconclusive / not demonstrated | reboot not shown (the wait, or line b; a hang is reported as an observation of the SUT); line c's container set never read with exit status 0 (the last read ended 124 or 255); QEMU exited, or not the same process on the same disks; a twin with `exists: false` in the pre-reboot snapshot; `finish` stopped before its `after` pair |
| Not started (the request's sentence after its table, and section 5 item 5) | a halt before the reboot for another cause: `-no-reboot` found; at line a not six running containers, no event directory or no mount source; a refused precondition of the smoke |

A row halted before any of its steps (the gate's record differing from S2's, an attempt under an unexpected name)
ran nothing: if an attempt exists it is classified not started.

Test 9, the packet's row, unchanged. Valid failure: (a) exit 0; (b) or (c) a session accepted; (d) probe 1, or
counters or `started_at` changed; (e) anonymous accepted. Invalid instrumentation: a `sut_log` STOP; probe 2 or 255; an
invalid `/metrics` snapshot. Inconclusive: (a) an error other than certificate verification; (b) or (c) no refusal
line in a log that was read; probe 3.

Only where the record shows that a line's own assumption failed (an output form or an exit status other than the
documented one, the tunnel on the host) is a row invalid instrumentation or not demonstrated.

## Controlled close

(1) Fetches and cleanups first (the runbook's own, three tries at most; the guest's `/tmp` is lost at power-off).
(2) No row, recorder or collector running. (3) The open attempt finished and exported as it stands (`classify`).
(4) `close`: the recorded `docker compose --env-file .env --env-file images.lock.env stop -t 130` with its exit status
and the container states; a non-zero stop is a halt and a hand-back, never a forced power-off. (5) The frozen
`guest_session_close.sh`: tunnel down, its own `compose stop -t 60`, the boot's OOM state, power-off, no QEMU left,
root file system hashed, data-disk file listed, export. (6) The script records the post-close root file system value
and lists the data disk's ext4 header, read-only.

## A guest that does not answer while QEMU is alive

During T8's wait, at a gate or at `close`: **preserve the state, signal nothing, ask Rui.** Nothing is stopped or
powered off from the host; QEMU is left running and is not signalled; the session stays open; no controlled close is
claimed; what is done with QEMU is Rui's decision in the window (the data disk is at stake). If QEMU has exited,
nothing is re-launched and no stop is possible: only the close driver runs, and the root file system is hashed as it
was left. If WSL or the keepalive is lost there is nothing left to close: the attempts left open are recovered and
exported with the export tool (`local_export recover`), and the loss is reported.
