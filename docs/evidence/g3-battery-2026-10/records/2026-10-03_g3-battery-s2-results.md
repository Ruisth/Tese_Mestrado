# G3 qualifying battery — session S2 results (2026-10-03)

**Authority:** Rui's authorisation of 2026-10-02 ([record](2026-10-02_g3-freeze-and-battery-authorisation.md)) under the packet of 2026-10-01, revision 2, S1 having reached its planned end without a halt ([S1 results](2026-10-02_g3-battery-s1-results.md)), and his "Sim, estou presente, arranca a S2" of 2026-10-03.
**Candidate:** unchanged, tools `80e833f`, helper `e5eba37e…`, controller image `9a293fe1…` from `489bc9e`.

**S2 ended on a halt condition (packet §4, halt 5) at row T8, after a controlled close.** T9 was not run. **This note makes no G3 claim:** G3 stays `Not decided`, and any further run is Rui's decision.

## Session

- Opened 13:22:49Z, closed 14:39:43Z: about 1 h 17 min of guest occupation. Open, preflight and gate health each ended 0; the harness input was the preflight's current capture (`3f663ed0…`, ARM64 EMULATED), the earlier one kept. The root file system before the boot was S1's post-close value (`f59a60ff…`).
- Rows T6, T7 (both faults) and T8 ran; T9 did not.
- Close: the recorded `compose stop -t 130` ended 0, the close driver ended 0; no memory-cgroup OOM in either boot of the session; no QEMU left. Root file system after the close: `22e9da85…`.

## Rows

| # | Row | Run id | Class | What the evidence shows |
|---|---|---|---|---|
| 8 | T6 controller restart | `controller_restart-r03` | **Invalid instrumentation** | The restart ran (die 13:37:14.06Z, start 13:37:18.76Z; recovery 4.75 s functional, 11.9 s endpoint). The proved-down interval was established, but the collector wrote two rows of the controller inside it (13:37:17Z, cpu 0.00; and in the start's own second), which rule 1a rejects whatever their values; the file, and so the run, is invalid and unsealed. Reported only: 4,718 of 6,720 in time, `lost` 2,002 (82 late), `double_accepted` 0 |
| 9 | T7 MongoDB fault | `itest-mongo-fault-01-q1` | **Pass** | Interruption and recovery shown; capture complete (`die`, `stop`, `start`); 44 `failed` after 3 attempts with HTTP 500, acceptance resumed; `delta` OK; N1 report 0/0. Reported: `lost` 1,209 (1,165 late) |
| 10 | T7 Ditto fault | `itest-ditto-fault-01-q1` | **Pass** (first run ever) | Interruption and recovery shown; capture complete; 5 `failed` after 3 attempts with a read timeout, acceptance resumed; `delta` OK; N1 report 0/0; no OOM at 768 MiB. Reported: `lost` 1,895 (1,890 late) |
| 11 | T8 guest reboot | `itest-reboot-q1` | **Inconclusive / not demonstrated — HALT** | The guest rebooted (previous boot ended cleanly 14:25:44Z; new boot 14:26:15Z); the six containers were back unaided by 14:26:46Z, healthy, `/var/lib/docker` on `/dev/vdb`, every event directory intact. But QEMU did not exit: the launcher runs it without `-no-reboot`, so the guest rebooted inside the same process. The procedure waited 600 s for the exit and halted without signalling QEMU. Steps b–d (`REBOOT SHOWN`, twins `same`, the post-reboot smoke) did not run |
| 12 | T9 TLS and authorisation | — | **Not run** (after the halt) | — |

Families after both sessions: T1, T2, T3, T4, T5 and T7 passed their Expected lists as I read them; T6 is invalid (not evidence); T8 is not demonstrated; T9 did not run.

## Points for the Project Manager's review

1. **T6 and rule 1a.** The rule worked as adopted: the interval was derived from a complete capture and a matching StartedAt, and the two edge gaps were within 5 s. What invalidated the run is the rule's rejection of collector rows inside the interval: the collector sampled the restarted container's cgroup 1.7 s before Docker recorded its `start` (a near-empty row), and again in the start's second. Whether such rows should invalidate the run, or be treated otherwise, is a decision about the rule's wording, not a correction I can make. Even a valid run would have failed C12's zero-lost obligation (2,002 lost at 11.2 msg/s): the same throughput finding as `nominal-r02`.
2. **T8 and the launcher.** Runbook line 1487 ("QEMU exits (-no-reboot). Re-launch exactly as in 3.3") does not hold for the launcher this session used (`run-qemu-integrated.sh`, no `-no-reboot` on QEMU's command line). The reboot did happen and the stack came back by itself, which is the behaviour test 8 wants to see, but its Expected list was not evaluated. A corrected T8 procedure (steps b–d on the rebooted guest, boot ids compared) is a decision for Rui; T9 then also needs its run.
3. **Throughput.** Every nominal-rate row of the battery (T1 harness, T6, both T7 faults) left a large late backlog under TCG; only the 60 s and 180 s ad-hoc rows were in time. T7 is not timed, so it passes; T6 is.

## Evidence (`output_test/runs/2026-10-03/`; every seal verifies)

| Package | Files |
|---|---|
| `20261003T132249Z_guest-session_attempt09` (holds the read-only post-reboot evidence step) | 89 |
| `20261003T132332Z_live-preflight_attempt10` | 42 |
| `20261003T132836Z_g2-gate-preconditions_attempt06` | 26 |
| `20261003T132936Z_g3-qualification-t6_attempt01` (official; the unsealed harness capsule inside) | 95 |
| `20261003T135147Z_g3-qualification-t7-mongo_attempt01` (official) | 52 |
| `20261003T140639Z_g3-qualification-t7-ditto_attempt01` (official) | 52 |
| `20261003T142310Z_g3-qualification-t8_attempt01` (official; incomplete: the post-reboot artefacts were never written) | 32 |
| `HIST_2026-10-03-g3-battery-s2-operator-records` | 81 |

## Next

Nothing under the packet: the halt cancels further progress until Rui directs otherwise. Decisions open to Rui, with the PM's advice: the T8 procedure and its re-run with T9; whether rule 1a's treatment of collector rows inside the proved-down interval stands; whether T6 is attempted again under a new decision. No repeat, no change to the candidate was made here.
