# G3 — request for one bounded session: test 8 and test 9 only (2026-10-04)

**Status: a request.** It authorises nothing by itself and creates no G3 result; G3 stays `Not decided`. Order: the Project Manager's register entry "2026-10-04 01:00 WEST", relayed by Rui. The authority of 2026-10-02 (sessions S1 and S2, the `-q1` identifiers) is consumed.

**In short.** One session, S3: test 8 and test 9, once each, on the unchanged candidate, with the procedure merged at `8e49261` and fresh `-q2` identifiers; about 30–45 min expected; ceilings of 135 min (T8) and 25 min (T9); any `STOP:` in test 8 (lines a to f) halts the session and test 9 is not run, while a smoke that completes and only misses its timed checks does not; QEMU is never re-launched, and never killed without Rui's decision; everything is kept in `output_test`; no repeat, no build, no change to the candidate or to a criterion.

## 1. What is asked

Rui's explicit authorisation for (i) the preparation of section 7 and (ii) **one** guest session, S3, in a window Rui attends: test 8 (persistence across the in-process reboot) and test 9 (TLS, authentication, ACL, exposure), once each, then a controlled close. S3 starts only on Rui's go in that window, after the preparation package has been delivered. One halt of section 5 needs Rui's decision in the window itself (a guest that does not answer while QEMU runs).

## 2. Identity

**Procedure and tools: the merged commit.** `8e492613d36490a560ae56beabd6d5c2c01a8696` on `dev` (pull request #54), tree `2f0514837f267d8975f7071041aad14a5c18dcab`, which is the tree of the reviewed head `7c371e3`. Runbook `docs/setup/qemu_integrated_gateway.md`: sha256 `4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db`, 1,623 lines.

Against the battery's `80e833f`, ten files differ: the runbook, one test module, LOG, PROGRESS and six documentation files. Nothing under `tools/`, and nothing under `src/` outside `src/tests`, differs. In the runbook only test 8's block and Expected paragraph, the note of section 3.2 and Appendix B item 25 changed: the helper heredoc of section 6.1 (`e5eba37e…`), `tunnel.sh` and test 9's block are byte-identical. Test 8's corrected lines were exercised against stubs only (1,061 tests passed on `cba4808`); S3 would be their first execution on the guest.

Recommended, and part of what is asked: the execution clone `~/egw-exec/repo` moves from `80e833f` to `8e49261` (detached, clean) at preparation, so that every attempt's `repo_identity` names the commit whose procedure ran and the identity checks read the merged runbook. `drivers_sha256` is expected unchanged (`4a6a572d…`), since no driver file differs.

**System under test: the same candidate, identified apart.** No build, no image load, no configuration change.

| Item | Recorded identity (battery packet section 1; S2's open, preflight and gate) |
|---|---|
| Controller image | `egw-controller:0.1.0`, image id `sha256:9a293fe1…5f46`, built from `489bc9e`; archive `9d347be4…` |
| Five pinned images | `images.lock.env` `8a9a05df…a648`: mosquitto 2.0.22, mongo 7.0.39, three Ditto 3.9.4 services, digests as recorded at S2's gate |
| Deployment | `src/deployment` git tree `e056d389…`; `compose.yaml` `1a32f6c2…`; `mosquitto.conf` `ea37827c…`; the deployed tree equal to the clone's |
| Contracts | `src/CONTRACTS.md` `247e3b02…`; `src/schemas` tree `1d5284cf…` |
| Guest OS | kernel `4457ef38…`; `qemuboot.conf` `7739c945…`; launcher `run-qemu-integrated.sh` `67da61d7…` in the Yocto checkout at `489bc9e`; QEMU 8.2.7 `5d389c65…` |
| Root file system | `.ext4` expected at `22e9da8533541582a2e4549f4c37f2b80f0f6a9bd3a5f0dd5e13605d7269efcd`, the value S2's close recorded (the image is mutable: each open expects the previous close's value) |
| Data disk | `egw-data.img`, 34,359,738,368 B; never hashed: its size and ext4 header are listed before the boot and after the close |

How each is compared, a difference being a STOP: on the host, by the host-preparation script (all the host-readable values; the kernel, `qemuboot.conf`, the QEMU binary and the Yocto checkout's commit are added for S3, since today the open driver only records them) and again at open by the operator script (clone, drivers, export tool, runbook, helper, tunnel, CA, root file system and, added for S3, the same four values); on the guest, by the frozen preflight (the controller image id against the guest's record, the deployed tree against the clone). The frozen gate driver records the running image ids and digests and compares nothing: for S3 the operator script compares that record with S2's before row T8, and a difference is a halt. Observed, not an identity: at S1's and S2's boots QEMU's command line carried no `-no-reboot` (why `runqemu` did not add it was not established); for S3 the operator script reads the running QEMU's command line before line a, and `-no-reboot` on it is a halt before the reboot is issued.

Nothing of S1 or S2 is re-run or replaced; their packages stay as sealed.

## 3. Identifiers (fresh)

- Session label `S3`, with its own state directory; the S1/S2 state is left as sealed.
- Test 8: prefix `itest-reboot-q2` (all 60 literals of lines a to e change together) and smoke run id `itest-post-reboot-01-q2`.
- Test 9: `itest-tls-wrongca-q2`, `itest-auth-wrongpw-q2`, `itest-notls-q2`; `itest-acl-<UTC stamp>` is fresh by construction.
- Packages: T8 as `…_g3-qualification-t8_attempt02` (attempt01 is S2's halted one, kept) and T9 as `…_g3-qualification-t9_attempt01`; the session, preflight and gate packages take their next numbers (expected: guest-session attempt10, live-preflight attempt11, g2-gate-preconditions attempt07; the export tool assigns them at run time).
- Before the session each identifier is shown to have no file on the host, and none has an event directory on the guest's root file system, read offline and read-only (`debugfs -c`, no QEMU running); only the smoke id would leave one there, since the prefix and T9's three identifiers write none by design. No `-q1` identifier is reused: `itest-reboot-q1` left two host files and the others are named in sealed records.

## 4. Sequence and duration limits

Sequence, with the unchanged drivers: `guest_session_open.sh`; `preflight.sh`; the environment copy of the earlier condition 2, kept as in S1/S2 although no row of S3 reads it (the harness input `~/egw-tcg/sut_environment.json` is replaced by the preflight's labelled capture, the previous file kept beside it); `gate_health.sh`; row T8 (lines a to f, each a recorded step), the previous boot's journal and kernel OOM lines (read-only), its gate and classification; row T9 ((a), (b), (c), (d)+(e), then the three read-only exposure checks), its gate and classification; the recorded `compose stop -t 130`; `guest_session_close.sh`. Both rows carry `--purpose official` ("G3 qualification"); the other packages stay engineering.

| Part | Expected | Limit |
|---|---|---|
| Open, preflight, gate | about 7 min (as in S1 and S2) | none of its own |
| T8 | 15–25 min (the packet's planning figure, not a measurement; in S2 the six containers were started again about 1 min after the old boot ended; line e's readiness wait after a reboot was never observed) | ceiling 135 min |
| T9 | 6–8 min (the packet's planning figure; never run in the battery) | ceiling 25 min |
| Stop and close | about 1.5 min | none of its own |
| Session | about 30–45 min of guest occupation, with one to two and a half minutes of classification per row | no row starts at or after 3 h on the host's `/proc/uptime` baseline taken at open: a start cut-off, not a total |

With both rows just under their ceilings and the open and close as in S1/S2 the session would last about 2 h 50 min to 3 h: an estimate, not a bound, since the open and the close have no limit of their own. The ceilings and the cut-off are the packet's, unchanged. The merged lines' own bounds add up to more than T8's ceiling (lines b and c up to about 45 min each, line e 60 min, the smoke up to about 32 min), so the ceiling is the binding limit: at 135 min the row receives TERM to its process group (never KILL, never QEMU), is exported as interrupted, and the session closes.

One wait is new: before line b the operator script polls, read-only, for about 15 min at most (a 900 s limit tested after each poll, one poll every 10 s) until the guest answers with a different boot id; the step's preamble needs the rebooted guest's sshd. It replaces the packet's 10 min wait for a QEMU exit and is shorter than line b's own bound: a guest that needs longer halts T8 as "reboot not shown" without line b being run. In S2 the new boot began 31 s after the old one ended.

Host rules as before: two detached keepalive clients with at least 6 h left, Windows kept awake, no other load, long subcommands launched detached.

## 5. Stop conditions

Each of these halts the session: nothing is repeated; the open row is classified and exported as it stands; the session is closed in a controlled way (section 6) whenever the guest answers, and handed back to Rui. If the guest does not answer while its QEMU process is running (item 4's wait, item 7), nothing is stopped or powered off from the host: QEMU is left running and is not signalled, the session stays open, and what is done with QEMU is Rui's decision in the window (the data disk is at stake). If QEMU has exited, nothing is re-launched and no stop is possible: only the close driver runs, and the root file system is hashed as it was left. If WSL or the keepalive is lost there is nothing left to close: the attempts left open are recovered and exported with the export tool, and the loss is reported.

1. At open, preflight, gate or the start of a row: the clone not at `8e49261` or not clean; a runbook, helper, tunnel or CA hash that differs; an identity of section 2 that differs; the root file system not at the expected value; an identifier not fresh; a frozen driver ending non-zero; the environment copy failing. No row, or no further row, is then run.
2. Instrumentation: a step status 97 or 74 (preamble not loaded, console capture lost); an export, transcript, marker, fetch or snapshot failure; a usage exit 2 of `delta`.
3. A failed gate: a service not healthy within the gate's wait (900 s in a row's gate; 1,800 s, its default, in the gate driver at open, as in S1 and S2); a recorder or collector unit active at the gate; in T9's gate, an OOM kill, a restart or a replaced container. T8's gate compares no guest state across the reboot (packet section 3): the state recorded after T8 and the previous boot's kernel OOM lines are read by the operator before T8 is classified; an OOM kill found in either, or a restart after the reboot, is a halt and T9 is not run (the operator's rule: the script records no halt for it).
4. Test 8, lines a to e: `-no-reboot` on QEMU's command line before line a; any `STOP:`; the guest not answering with a different boot id within the wait; after the reboot no QEMU process, more than one, or one that is not the same process on the same disks; the tunnel not up after line d. **Test 9 is then not run.** QEMU is never re-launched, and never killed without Rui's decision.
5. Test 8's smoke (line f): a smoke whose console shows `TEST STATUS itest-post-reboot-01-q2: … PROCEDURE COMPLETE` and no `STOP:`, and which misses its timed checks (`lost` or `late_confirmations` above 0), is a classified failure of T8, not a halt, and T9 then runs if the gate passes. A smoke whose console does not show that line, or shows a `STOP:`, is a halt and T9 is not run; the row is classified by its cause with the packet's classes (a `delta` MISMATCH: valid failure, cause not established; a transcript, marker, fetch or snapshot failure, or a usage exit 2: invalid instrumentation; `finish` stopped before its `after` pair: inconclusive; a refused precondition: not started). The operator script records that halt (added for S3).
6. Test 9: each step runs only if the one before printed no `STOP:`; a `STOP:` ends T9 as it stands. The runbook's own remedy for an inconclusive probe (exit 3: repeat with a new tag) is **not** applied.
7. Guest, tunnel, WSL or keepalive lost, other than through T8's own reboot (the guest is away while it reboots and the tunnel's master dies with it; item 4 bounds both).
8. A row past its ceiling, or the cut-off.
9. Any restoration (the runbook's own only: a capture cleanup, `tunnel_down && tunnel_up` outside line d): record, halt. Nothing on the guest is started, restarted or recreated by hand at any point of S3 (`compose up`, `start`, `restart`, `docker start`): between the reboot and line c it would make the return an aided one, which line c cannot detect and test 8 does not accept.

Not done without Rui's decision: any fix; any repeat; a new identifier for a refused row; any change to code, configuration, helpers, thresholds or `DRAIN_*`.

## 6. Evidence, close and classification

- Everything is kept under `output_test/runs/<UTC date>/`: the session, preflight and gate packages; one package per row (the console of every step, T8's prefix files and smoke files, T9's broker-log extracts and ACL evidence, `commands.jsonl`, `SUMMARY.md`, `SHA256SUMS`); the operator records. Every attempt is exported, including one not started or interrupted; nothing is deleted. Every export is verified (the export tool's own verification, then `sha256sum -c` in each package) before the result note is written. Files holding a secret and T9's throw-away key are not exported; a secret sweep precedes each seal.
- Close: fetches and cleanups first (the runbook's own, three tries at most; the guest's `/tmp` is lost at power-off); no row, recorder or collector running; the open attempt finished and exported as it stands; the recorded `docker compose --env-file .env --env-file images.lock.env stop -t 130`, with its exit status and the container states; then the frozen close driver (tunnel down, its own `compose stop -t 60`, then idempotent, the boot's OOM state, power-off, no QEMU left, root file system hashed, data-disk file listed, export); then the operator script records the post-close root file system value and lists the data disk's ext4 header, read-only. A non-zero stop is a halt and a hand-back, never a forced power-off.
- Result note `output_test/decisions/<date>_g3-t8-t9-results.md`: each row's validity, functional outcome and timed delivery stated apart, with the packet's classes (its section 5) and no G3 claim. T9's row of that section is unchanged. T8's row was written for a QEMU that exits; it is read for the corrected procedure as below — a proposed reading, no class added or removed, and none of these is a pass:

| Class | Test 8, corrected procedure |
|---|---|
| Valid failure of the system | the stack not ready within 3,600 s (line e); the six containers not returned unaided (line c: the last read ended with exit status 0 and listed another set); an event directory missing; `/var/lib/docker` on another source, or not mounted (`findmnt` exit 1 with nothing printed); the twins DIFFERENT; `started_at` unchanged (line e); the smoke's `lost` or `late_confirmations` above 0, or a `delta` MISMATCH (cause not established) |
| Invalid instrumentation | the boot id unreadable or not of the kernel's form; the event-directory or mount read ended by its timeout or by ssh (124, 255); the tunnel not reopened; a snapshot, marker, fetch, transcript or export failure |
| Inconclusive / not demonstrated | reboot not shown (the wait, or line b; a hang is reported as a SUT observation); line c's container set never read with exit status 0 (the last read ended 124 or 255); QEMU exited, or not the same process on the same disks; a twin with `exists: false` in the pre-reboot snapshot |

The smoke's other outcomes are classed in section 5, item 5. A halt before the reboot for another cause (`-no-reboot` found; not six running containers, no event directory or no mount source at line a) is "not started". The packet's "another data disk" and "QEMU never exited" belonged to the re-launch and no longer apply.

## 7. Preparation (after authorisation, before the session; no guest)

1. Scripts, offline: the extraction script, the row checker, the dry run, the host-preparation script (which gains the comparison of the kernel, `qemuboot.conf`, the QEMU binary and the Yocto checkout's commit with the recorded values) and the two sealing scripts revised from the battery's copies for the merged commit, the `-q2` identifiers and S3 (the first preparation's copies stay as sealed); the operator script finished from its draft: label S3 with rows t8 and t9 only, the `-q2` identifiers, the authority recorded in each row, the identities and comparisons of section 2 (the same four values at open; the gate's record against S2's before row T8), the expected root file system value, the read of QEMU's command line before line a, the `PERSISTENCE SHOWN` marker, the halt after line f unless the smoke's console shows `PROCEDURE COMPLETE` and no `STOP:`, T8 admitted as attempt02 after the one recorded attempt01.
2. On the host: the clone fetched and checked out at `8e49261` first; then the six step files of test 8 and the four fenced step files of test 9 re-extracted verbatim from the merged runbook blob, with identifier-only diffs, and checked against that clone; T9's exposure step, which is not a runbook line, written again from the same constant as in the battery's preparation (three read-only commands from the last sentence of test 9's Expected; only the commit, hash and line number in its header change); a new manifest for S3; benches of the operator script on the real step files against stubs; one bounded check of every revised script and of the step files; then the helper file regenerated from the clone (expected byte-identical, the predecessor kept), the identities of section 2 compared, the identifiers shown unused, the root file system re-hashed.
3. Sealed as a host-preparation package in `output_test` and given to Rui before S3. A mismatch is a STOP, and Rui can hold the session on the package.

About 2–3 h, mostly unattended (an estimate: the first preparation recorded no duration).

## 8. Boundaries

- Not in S3: T1–T7 (T6 is not appended); any build; any image, container or configuration change; any criterion or threshold change; `-no-reboot`.
- What S3 writes on the guest, apart from the reboot: T8's smoke (336 messages, its event directory, the three twins); T9's ACL probe, which creates `/opt/egw/evidence/itest-acl-<stamp>` on the root file system and publishes four non-retained probe messages that the controller's filter does not match; the refused connections of (a) to (c) in the broker log. On the host, T9(a) writes `/tmp/wrong.key` (not exported) and `/tmp/wrong.crt`. The exposure checks only read, and run only if (d)+(e) printed no `STOP:`.
- T8 runs first. Its twin comparison relies on the three seed-42 twins that S1 and S2 left on the data disk (the runbook asks for test 8 after a seed-42 run; S2's pre-reboot snapshot showed all three existing). The pre-reboot snapshot is read at classification.
- What S3 can show: test 8's and test 9's checks on this candidate under QEMU/TCG, once. Unverified on the guest: the corrected lines' assumptions (Appendix B item 25: the output form of `docker ps`, the bounded ssh against a booting guest, the exit statuses the lines rely on, `wait_ready 3600` after a reboot) and the operator script's own T8 flow (the wait through the session's ssh, the QEMU same-process reading, the carrier between shells), benched against stubs only. One host-side case is known and not reproduced: the driver's preamble reopens the tunnel before line b, so line d closes and reopens a live ssh master, and a failure there halts T8 at line d. A `STOP:` on these lines is classified from its console and files with the classes of section 6, unchanged: only where the record shows that a line's own assumption failed (an output form or an exit status other than the documented one, the tunnel on the host) is the row invalid instrumentation or not demonstrated.
- T8's smoke is timed: in S1 the first smoke's p95 was about 50 s against the 60 s deadline. A late confirmation fails T8 and is not repeated.
- Open after S3 whatever its outcome: the interpretation of T5; T6, which stays invalid, with its admissibility and its timed criterion (2,002 deliveries after the deadline) undecided. G3 stays `Not decided`.

## 9. Decision asked

One sentence suffices, for example: *"I authorise the preparation and one session S3 with tests 8 and 9 only, under the request of 2026-10-04; no repeats, no change to the candidate, no automatic acceptance of G3."*

Four points are choices of this request; say so if any should be otherwise: (1) the clone's move to `8e49261` (section 2); (2) T9 running after a T8 whose smoke completed and missed its timed checks (section 5, item 5); (3) the 15 min wait before line b (section 4); (4) the reading of the packet's T8 classes for the corrected procedure (section 6).
