# G3 — session S3 (tests 8 and 9): decision summary (2026-10-04)

One page. Supporting detail: `2026-10-04_g3-t8-t9-session-request.md`, unchanged; where the two differ, this page governs. G3 stays `Not decided`.

## What was decided, and by whom

- **Rui's words, 2026-10-04:** «Respondo sim às 4 escolhas nos termos definidos pelo SPM», given on the Project Manager's opinion "2026-10-04 21:49 WEST" (register), which recommends authorising the preparation and one session S3 on those terms and states that it is not itself the authorisation.
- **How it is read here:** the four choices are decided, in the Project Manager's terms, and the preparation proceeds on that answer (choice 1 is a step of it). **S3 itself is not started on this answer:** it needs Rui's explicit authorisation of the session and his go in the attended window («estou presente»), after the sealed preparation package has been delivered.

## The four choices

1. The clean execution clone moves to `8e49261` at preparation; local changes found there are a stop, nothing is discarded. The procedure and tool identity is recorded apart from the unchanged candidate and its retained controller image.
2. T9 may run after a T8 smoke that completed and failed only its timed delivery, with no `STOP:` and a healthy gate in between; T8 stays failed. A procedural, instrumentation or safe-state halt does not permit continuation.
3. The wait of about 15 min before line b is an operational cut-off. If it expires the session halts and the reboot is reported as not demonstrated: not a boot-performance criterion, not automatically a failure of the system.
4. The proposed reading of the packet's classes for the corrected test 8 is accepted, the observed cause and the evidence controlling. A `STOP:` is never instrumentation by default, and an incomplete row is never a pass.

## Two conditions for the preparation

- **A. The new wait keeps the repair of pull request #54.** Every read is bounded (20 s or less, never more than the budget that remains, never a zero timeout); a read counts only with exit status 0 and a valid boot id different from the saved one; what a failed read printed is kept as a diagnostic; the 900 s budget is measured on the host's monotonic clock. The wait, its preamble and the later steps of T8 share the 135 min ceiling of the row: no budget is reset. The operator benches cover matching output followed by 124 or 255, a genuine success, and expiry.
- **B. Section 5, item 9 of the request, clarified.** The prescribed initial preflight may start the unchanged stack before T8. What is forbidden is any manual or aided start, restart or recreation after the reboot, and any recovery that would let a failed row continue. The tunnel step (line d) and the normal safe-close operations stay; none of them may be presented as unaided recovery of the containers.

## Identity, identifiers, limits

- **Procedure and tools:** merge `8e492613d36490a560ae56beabd6d5c2c01a8696`, tree `2f0514837f267d8975f7071041aad14a5c18dcab`; runbook sha256 `4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db`, 1,623 lines. Against `80e833f` nothing under `tools/`, and nothing under `src/` outside `src/tests`, differs.
- **Candidate, unchanged:** controller image id `sha256:9a293fe1…5f46` (from `489bc9e`); `images.lock.env` `8a9a05df…a648`; `src/deployment` tree `e056d389…`; kernel `4457ef38…`, `qemuboot.conf` `7739c945…`, QEMU 8.2.7 `5d389c65…`, launcher `67da61d7…`; root file system expected at `22e9da85…efcd`, the value S2's close recorded. No build, no image load, no configuration change.
- **Identifiers:** session `S3`; `itest-reboot-q2`, `itest-post-reboot-01-q2`, `itest-tls-wrongca-q2`, `itest-auth-wrongpw-q2`, `itest-notls-q2`; T8 as attempt02 of its row, T9 as attempt01.
- **Limits:** about 30–45 min expected; ceilings 135 min (T8) and 25 min (T9); no row starts at or after 3 h on the host's `/proc/uptime` baseline. Stop conditions: section 5 of the request, with item 9 as clarified above. A guest that cannot be closed safely while QEMU is alive: the state is preserved, QEMU is not signalled, no controlled close is claimed, and Rui's direction is asked.
- **Not included:** any build or load, any change to the candidate, T1–T7, an automatic retry, an amendment of T6, an acceptance of G3.

## Next

The sealed preparation package goes to Rui; then his explicit authorisation of S3 and «estou presente»; then S3, with every outcome kept in `output_test` and each export verified. A report is due at two hours of preparation if it is unfinished, naming what remains.
