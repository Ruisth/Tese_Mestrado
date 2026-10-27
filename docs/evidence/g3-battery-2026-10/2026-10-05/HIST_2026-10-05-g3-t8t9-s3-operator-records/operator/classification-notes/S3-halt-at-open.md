# S3 — halt at open (2026-10-05)

- 10:56:06Z `open S3`: every identity check passed; the guest booted (session `20261005T105614Z_guest-session_attempt10`).
- The frozen `preflight.sh` (`20261005T105656Z_live-preflight_attempt11`) ended exit 3: instrumentation invalid,
  outcome inconclusive. Its step 16, `collector-duration`, exit 1: "the collector stopped 2 s before the duration=45s
  its 'start:' line declares (its own window is 43 s)". Every other step ended 0 (stack start, deployed tree equal to
  the clone, controller and stack health, broker secrets, clocks, environment capture, the 45 s live collector check
  with 43 rows per service and no problem, the fetch). In S2 the same check read 44 s of 45 s, within its 1 s tolerance.
- The script recorded `HALT: preflight.sh exited 3` (request, section 5 item 1: a frozen driver ending non-zero). The
  gate, the environment copy and both rows were not run; no row attempt exists; the `-q2` identifiers are unused.
- 11:02:29Z `close`: no recorder or collector unit active; the recorded `compose stop -t 130` exit 0 (controller,
  mosquitto, mongodb Exited (0); the three Ditto services Exited (143)); `guest_session_close.sh` exit 0 (no memory
  cgroup OOM, QEMU ended exit 0, no QEMU left, session attempt exported and verified). Root file system after the
  close `b48b010d571689ae03d610175fd1b127f6ef6b30f78b25448e6f32a3096de093`; data disk header `clean`.
- Nothing was repeated, fixed or changed. The authority for S3 is consumed.
