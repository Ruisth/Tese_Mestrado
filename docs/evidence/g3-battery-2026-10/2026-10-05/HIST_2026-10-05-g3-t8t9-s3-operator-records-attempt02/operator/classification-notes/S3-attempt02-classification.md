# S3, second opening (2026-10-05) — classification notes

- Open 11:44:20Z: every identity check passed; the frozen preflight passed this time (attempt12: the collector held
  44 s of 45 s, within its tolerance), so the authorised exception for collector-duration was NOT used (no
  `preflight_exception` key). Environment copy, gate (attempt07), guest listing: OK.
- **T8 — pass** (attempt02, 11:51:26Z–12:04:29Z, 817 s). QEMU command line without `-no-reboot`; reboot command
  11:54:13Z; the guest answered from a new boot at the third poll (+27 s): boot id fc85c700… -> 0a780c6e…; the same
  QEMU process (pid 34407) after the wait; REBOOT SHOWN (read 1); CONTAINERS RETURNED UNAIDED (read 2; started
  11:55:01–11:55:03Z, nothing started by hand); PERSISTENCE SHOWN (35 event directories, /var/lib/docker on /dev/vdb);
  observations read exit 0; TUNNEL UP at line d; three seed-42 twins identical (exists true); CONTROLLER PROCESS NEW
  (11:48:04.516Z -> 11:55:23.920Z); smoke itest-post-reboot-01-q2: 336 sent, lost 0, late_confirmations 0, every
  delta OK, PROCEDURE COMPLETE; latency p95 57.6 s, max 58.8 s against the 60 s deadline (in time, with a small
  margin: an observation); previous boot: no OOM line, clean shutdown; restarts 0, oomkilled false; gate pass.
- **T9 — pass** (attempt01, 12:05:33Z–12:10:51Z, 332 s). (a) exit 1, CERTIFICATE_VERIFY_FAILED; (b) exit 1 after 15 s,
  the bounded broker log names the client "not authorised"; (c) exit 1, "SSL routines::wrong version number"; (d)
  probe exit 0, verdict PASS, 0 deliveries to the unauthorised subscriber, changed fields [], controller untouched;
  (e) anonymous refused rc 5, anon.out 0 bytes; exposure: root ssh refused, QEMU forwards only 2222 and 8883 on
  127.0.0.1, controller and gateway on 127.0.0.1 in the guest, mongodb unpublished; gate pass (guest state compared:
  0 faults, 0 problems). Observation: the broker container's healthcheck shows as "egw-healthcheck disconnected, not
  authorised" in the bounded logs.
- Close 12:11:56Z–12:13:05Z: recorded stop -t 130 exit 0; guest_session_close.sh exit 0; no memory-cgroup OOM; no
  QEMU left; root file system after the close 6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4; data
  disk clean.
