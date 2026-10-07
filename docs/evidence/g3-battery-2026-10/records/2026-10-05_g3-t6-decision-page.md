# G3 — T6 (controller restart under nominal load): the choice (2026-10-05)

**For Rui's decision; adopts nothing.** The run `controller_restart-r03` stays invalid and is not converted. No session, repeat or controller change follows from this page. Order: the Project Manager's register entry of 2026-10-05, 13:42 WEST.

**Correction (2026-10-05, later; the Project Manager's register entry of 15:14 WEST).** The original text below is kept as written. Three of its statements say more than the records show: "The restart does not cause this" should read **"lateness also occurred without a restart; these records do not isolate the restart's contribution"**; "the records show the current candidate cannot meet the criterion" and "it would have to serve more than 11.2 msg/s sustained" state an impossibility and a necessary condition that these observations do not establish (they ignore the finite drain allowance): the records show non-compliance observed at the nominal rate and no proven remedy. The correction does not reopen Rui's choice of Option 2.

## Two separate problems

**1. Collection validity (tooling).** Rule 1a rejected two collector rows of the controller, stamped 13:37:17Z and 13:37:18Z, inside the proved-down interval: Docker's `die` at 13:37:14.06Z, `start` at 13:37:18.76Z. The collector's own lifecycle record has the cgroup gone at 13:37:12Z and back at 13:37:16Z. The run is invalid and unsealed. This is fixable in tooling only, prospectively. Option A of the T6 page is the Project Manager's preferred direction, but the page still lacks his four F2 qualifications. Separately, the `collector-duration` check judges UTC stamps against a duration run on uptime, and must be corrected before a resource-dependent run such as T6 relies on it.

**2. Deadline compliance (the system).** At 11.2 msg/s for 600 s, T6 sent 6,720 messages. 4,718 were confirmed by the deadline (marker plus 60 s) and 2,002 after it. In the post-drain copy all 6,720 were accepted exactly once.

The restart does not cause this:
- `nominal-r02` (T1 harness, same candidate, no restart) had 2,136 beyond the deadline.
- In both runs, every message published after about 410–420 s was late.
- The controller's consumer is strictly serial: one message at a time, one Ditto PATCH, the PUBACK in receipt order by contract. It served about 6.3–8.7 msg/s under ingress and about 10.1 msg/s while draining (derived from its counters), against 11.2 offered.
- The 30–180 s rows at the same rate were in time, but with thin margins: the T8 smoke's last acknowledgement came 1.338 s before its deadline.
- No record isolates the per-message cost (Ditto round trip, controller CPU, event-log write, TCG scheduling).

**Fixing problem 1 cannot fix problem 2.**

## The choice

### Option 1 — keep the current criterion; produce valid new evidence

The criterion stays as in force: `lost = 0` and `late_confirmations = 0` against marker plus 60 s, C12's obligation (decision 3 of 2026-09-30, runbook "Timed families").

Prerequisites (tooling, candidate unchanged):
- a collection-validity rule adopted prospectively (Option A with the F2 qualifications);
- `collector-duration` measured on paired monotonic bounds;
- a new `controller_restart` plan entry (r01–r03 are used).

**A change to the system under test**, because the records show the current candidate cannot meet the criterion. To pass, it would have to serve more than 11.2 msg/s sustained under TCG, absorb the roughly 20 s restart gap (about 230 messages), and clear its backlog within 60 s of the run's end. No record shows any change achieving that:
- The only candidate change identified is per-device concurrency behind an acknowledgement sequencer. It needs its own ADR covering ordering, duplicates, durability and configuration identity, plus evidence that it helps (89.3 % of the load is one twin).
- Ditto or QEMU resource changes are unmeasured, and also change the candidate.
- First step: the bounded diagnostic ADR 0011 describes (2.24 msg/s for 720 s, about 80 min, no code change, not a G3 run), to find where a passage's time goes.

**Consequence: a new candidate.**
- Every family is re-run on it, prior results kept: T1–T4 and T7–T9 would be re-qualified.
- The image is rebuilt (about 2 min), loaded and verified.
- The battery takes about 3 h of guest time plus preparation.

**Estimate:** about 5–8 working days. That is diagnostic, design and ADR, implementation and tests, image, preparation and battery. The previous controller change was estimated at 39–54 h to its battery. The outcome is uncertain, and the 2026-10-20 submission is at risk.

### Option 2 — a prospective, explicit, scoped amendment for T6 only, before any implementation or run

**Exact wording proposed** (replaces, for T6 only, the timed-family obligation of decision 3):

> T6 passes when the controller is restarted once mid-run with recovery within 120 s, every valid message is accepted exactly once in the post-drain copy (none absent, none duplicate-only, `double_accepted` 0), and every `delta` line reads OK. `lost` and `late_confirmations` against the marker plus 60 s are reported for T6 beside the result and recorded as a sizing finding; they are not a pass condition of T6. This applies to runs made after its dated adoption only.

**Consequences:**
- **Decision 3 is reversed for T6 alone.** This returns T6 to its pre-2026-09-30 reading ("loss reported as measured"); every other timed family keeps `lost = 0` and `late = 0`.
- **Plan §4.3 must be amended in the same dated decision.** It now says no threshold moves and a nominal-rate shortfall is never absorbed by changing the protocol.
- **C12 cannot claim timely delivery at the nominal rate under TCG.** The dissertation states the 2,002-of-6,720 shortfall, and `nominal-r02`'s, as a sizing finding.
- **T6 still needs one valid new run** on the unchanged candidate: the three tooling prerequisites of Option 1, then one bounded session of about 45 min.
- **r03 stays invalid.**

**Estimate:**
- about 1 working day offline for the prerequisites, with tests, review and PR;
- one session of about 1 h;
- the records.

Not proposed, and excluded by the Project Manager and ADR 0011: a lower load, a longer deadline, or C12 as pilot-only.

## Recommendation

**Option 2, with its plan amendment, if the timeliness shortfall is to be reported rather than engineered away before 2026-10-20.** The records show the shortfall at the nominal rate is a property of the candidate, with or without a restart. Option 1 cannot be shown to succeed before a diagnostic, and it re-opens every family.

**Option 1 if timely delivery at 11.2 msg/s under TCG is a claim the dissertation must make.** In that case, authorise first only the diagnostic and an ADR draft.

Either way, the tooling prerequisites come first and G3 stays `Not decided` until T6 has a valid result under the criterion chosen.

## Decision asked

1. Option 1 or Option 2.
2. If Option 2: the wording above, as is or amended, and the plan §4.3 amendment, both dated and prospective.
3. In both cases: authorise the offline tooling prerequisites (collection-validity rule with the F2 qualifications, `collector-duration` on monotonic bounds, a new plan entry). Any session is authorised separately.
