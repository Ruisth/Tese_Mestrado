# G3 qualifying battery — session S1 results (2026-10-02)

**Authority:** Rui's authorisation of 2026-10-02 ([record](2026-10-02_g3-freeze-and-battery-authorisation.md)) under the packet of 2026-10-01, revision 2, and his "Sim, estou presente, arranca a S1".
**Candidate:** tools `80e833f` (tree `dad725d`), helper `e5eba37e…`, controller image `9a293fe1…` from `489bc9e`; nothing changed during the session.

**This note makes no G3 claim.** G3 stays `Not decided`: S2 (T6–T9) has not run, and the results below are for the Project Manager's and Rui's review.

## Session

- Opened 15:01:30Z, closed 16:34:13Z: about 1 h 33 min of guest occupation, against the 3 h cutoff for starting a row (the last row started at 1 h 25 min).
- Open, preflight and gate health each ended 0. The harness environment input was replaced by the preflight's capture (`f6a53cee…`: QEMU 8.2.7 TCG, ARM64 EMULATED), with the earlier file kept (`…a870c431af5f`).
- **No halt condition.** Every row's gate passed: guest state unchanged, no OOM kill, no restart, six services healthy, no recorder or collector unit left, tunnel up.
- Close: the recorded `compose stop -t 130` ended 0 (controller, broker and MongoDB exited 0; the three Ditto services exited 143, their JVMs' answer to SIGTERM); the close driver ended 0; no memory-cgroup OOM; no QEMU left. Root file system after the close: `f59a60ff…` (S2 opens only on this value).

## Rows

| # | Row | Run id | Class | Decisive figures |
|---|---|---|---|---|
| 1 | T1 smokes ×3 | `itest-smoke-01/02/03-q1` | **Pass** | Each: 336 sent, 336 delivered, `lost` 0, `late` 0, `double_accepted` 0; three device types; every `delta` line OK |
| 2 | T1 harness | `nominal-r02` | **Pass (artefact chain)** | Manifest `valid`, sealed, no collector problem, 682 instants per service, capture complete. Delivery reported only: 4,584 of 6,720 in time (`lost` 2,136, 111 of them late) |
| 3 | T2 | `itest-3dev-01-q1` | **Pass** | 672 of 672, `lost` 0, `late` 0; three twins with `policyId` = `thingId`, no missing property, `egw_id`, `schema_version`; `delta` OK |
| 4 | T3 | `itest-invalid-01-q1` | **Pass** | 67 invalid, 67 rejected, none accepted; 1,277 valid, all accepted in the post-drain copy (`acceptance` 0), none rejected; `delta` OK |
| 5 | T4 replay | `itest-dup-01-q1` | **Pass** | `replay-check` 0: 672 of 672 with a duplicate line, none accepted again, `after` reading quiet, no reconnection (k = 0); twins identical; accounting unchanged |
| 6 | T4 reset | `itest-dup-02-q1` | **Pass** | 672 of 672, `lost` 0, `late` 0, no duplicate; `delta` OK (first run of this sub-check) |
| 7 | T5 | `itest-dropout-01-q1` | **Pass, two points for review** | 2,016 of 2,016, `lost` 0, `late` 0, `double_accepted` 0; 3 disconnects, 165 buffered; `delta` OK |

Families so far: T1, T2, T3, T4 (both parts) and T5 passed their Expected lists as I read them.

## Points for the Project Manager's review

1. **T5, the broker-log wording.** The Expected list (marked `UNVERIFIED`) says "N+1 connections and N disconnections". With N = 3 the bounded log shows 4 connections and **4** disconnection lines: the three dropout disconnections, each followed by a new connection, and one more when the simulator ended. The bounded read is taken after the run, so that last line is always inside it. I classed the item as met; read literally, the count of disconnection lines is N+1.
2. **T5, one `check` warning.** "dropout run without simulator-manifest totals … the C10 acceptance criterion fails for this run". It concerns the campaign criterion C10 and the harness layout, which an ad-hoc run does not have. The totals are in this run's own manifest and stderr (3 and 165). It is not an item of test 5's Expected list.
3. **T1 harness, the delivery figures.** Not a criterion of that row. At the nominal rate (11.2 msg/s) only 68 % was confirmed in time under TCG: a sizing finding. The same rate is T6's and T7's load in S2, where T6's zero-lost obligation (C12) applies.
4. **T1 smokes, margin.** In the first smoke the p95 latency was about 50 s and the maximum about 51 s against the 60 s deadline (emulated; informational). The later runs were far lower (T2 maximum 5.9 s).

## Evidence (`output_test/runs/2026-10-02/`; every seal verifies)

| Package | Files |
|---|---|
| `20261002T150133Z_guest-session_attempt08` | 87 |
| `20261002T150214Z_live-preflight_attempt09` | 42 |
| `20261002T150720Z_g2-gate-preconditions_attempt05` | 26 |
| `20261002T150829Z_g3-qualification-t1-smokes_attempt01` (official) | 66 |
| `20261002T152710Z_g3-qualification-t1-harness_attempt01` (official) | 88 |
| `20261002T154427Z_g3-qualification-t2_attempt01` (official) | 41 |
| `20261002T155313Z_g3-qualification-t3_attempt01` (official) | 41 |
| `20261002T160154Z_g3-qualification-t4-replay_attempt01` (official) | 45 |
| `20261002T161432Z_g3-qualification-t4-reset_attempt01` (official) | 38 |
| `20261002T162159Z_g3-qualification-t5_attempt01` (official) | 41 |
| `HIST_2026-10-02-g3-battery-host-preparation` | 85 |
| `HIST_2026-10-02-g3-battery-s1-operator-records` | 51 |

## Host-side notes (no effect on the guest or the results)

- One of the two WSL keepalive clients, the one run as an app background task, was ended by the app's time limit about 30 minutes in. The detached client stayed attached and a second detached one was added; the guest and the running row were unaffected.
- The first sealing of the operator records stopped on its own private-key pattern text (a false alarm); it was finished in place, with nothing replaced. The package's README says so.

## Next

S2 (T6–T9) in the following attended window, on Rui's word: S1 reached its planned end without a halt condition. No repeat, no change to the candidate.
