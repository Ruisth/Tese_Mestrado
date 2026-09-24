# Package D, round two — constraint check of the corrected diagnosis and of ADR 0011

- **Date:** 2026-09-21
- **Checked, as found and not modified:** `backlog_diagnosis.md` (429 lines) and `adr-0011-controller-restart-recovery.md` (1,060 lines), both in this directory [line counts: `out/verify_constraints/vc03_wording_scan.out.txt` ← `scripts/verify_constraints/vc03_wording_scan.py`].
- **Against:** the verification brief's rules, and the project manager's standing instruction on package D (`PM_G2_ACCEPTANCE_REVIEW_PR40_2026-09-21.md`, section 5; `PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 5, items 2 and 3 — both read-only).
- **Method:** read-only. Four scripts under `scripts/verify_constraints/` (runner `run_verify_constraints.sh`), outputs under `out/verify_constraints/`. No guest was started, no run repeated, no network touched. The only git commands run were `rev-parse`, `show`, `cat-file`, `log`, `diff`, `grep`, `ls-tree`, `merge-base` and `for-each-ref`. Nothing was written outside this directory.
- **Reference in this report:** `D:n` is line *n* of `backlog_diagnosis.md`, `A:n` line *n* of `adr-0011-controller-restart-recovery.md`.

---

## 1. Verdict in brief

**No high-severity breach.** Neither document presents itself as verified (D:5, A:3-9). Neither gives a capacity, a sustainable rate or a maximum throughput (D:128, D:297, A:43-47). Neither changes a deadline, an offered load, the 60 s window or the ingest rule (D:362, A:647-652, A:963-965). The triple 1,810 / 195 / 131 is not used as proof (A:172-177, D:130). All dates are ISO, no supervisor's act is dated, and no text-generation tool is named in either document [`out/verify_constraints/vc03_wording_scan.out.txt` ← `scripts/verify_constraints/vc03_wording_scan.py`: 0 hits for supervisor terms and 0 for tool names in both documents].

**19 findings: 10 medium, 9 low** (section 3). They cluster in four places:

1. The ADR marks as **PROVED** several restart figures that cross clock domains or rest on the source reading, contrary to its own rule at A:108-111. It also keeps a restart counterfactual that the diagnosis removed as a correction (F2–F4).
2. The ADR tightens, as a "must", the `drained` precondition that all nine tests pass through (F5). It also calls the guest "the constraint" (F7) and refers to a "capacity probe" (F8).
3. Four of the ADR's anchors do not resolve at the commit the brief names, because that clone is not at the merged `dev` (F12). The ADR also carries review-round material and sources that do not exist in the repository (F13).
4. The two documents contradict each other on the order of the runs, on one counterfactual and on one set of figures (F4, F16, F19).

**Could the student decide the ADR from these two documents alone? Not yet** (section 5). He can see the real trade-off and pick a direction:

- **Option 5:** the restart classes are processed late instead of never, at an unmeasured cost and with the recovery depending on broker settings.
- **Option 4:** the limitation is recorded at no cost.

Three things stop him from actually deciding. The ADR itself lists four items as open before the decision, and the first of them can rule out option 5. The effect on G3 is stated for tests 5 and 6 only. And the two documents disagree on what runs first.

---

## 2. Which commit the citations were resolved against

The brief names `/home/ruisth/egw-exec/repo` "at its current commit" as the merged `dev`. **It is not.**

- Its HEAD is `b7e0c83` (detached, 2026-09-21 00:17:23 +0100, "feat(tools): the two drivers the G2 demonstration needs").
- Its `origin/dev` is `ccd5fd6`.
- `35fe8bb`, the merged `dev` that the ADR cites (A:28-29), and `3549d46`, which the diagnosis cites (D:8), are both absent from that clone.

[`out/verify_constraints/vc01_resolve_citations.out.txt` ← `scripts/verify_constraints/vc01_resolve_citations.sh`]

The Windows worktree `../../devwt` holds both commits. `b7e0c83` is an ancestor of `35fe8bb`, and `3549d46` is not on `35fe8bb` [`out/verify_constraints/vc02_merged_dev_differences.out.txt` ← `scripts/verify_constraints/vc02_merged_dev_differences.sh`].

Among the paths either document cites, only `PROGRESS.md` and `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md` differ between `b7e0c83` and `35fe8bb` [vc02]. The consequences:

- **Diagnosis:** every `file:line` resolves at `b7e0c83` with the content the text describes [vc01, first block]. `src/egw_controller/` is identical between `fe954a9` and `b7e0c83`, as D:8 states [vc01, last block].
- **ADR:** every anchor under `src/`, `docs/setup/`, `docs/adr/`, `docs/evidence/`, `docs/reviews/` and `docs/claim_evidence_matrix.md` resolves at `b7e0c83` with the described content. The controller, compose, Mosquitto, Dockerfile and pyproject paths are unchanged `8e88670..b7e0c83` [vc01]. **Four anchors do not resolve at `b7e0c83`:** plan `:104`, `:630-631`, `:638-640` and `PROGRESS.md:509`. A fifth, `PROGRESS.md:180`, is correctly scoped by the ADR to `3549d46`. All five resolve where the ADR says [vc02] — see F12.

---

## 3. Findings

Each finding gives the rule, the sentence that carries it, why it breaches, and the smallest fix.

### Rule: nothing called accepted, proved, guaranteed or closed that has not been decided and tested

**F1 — medium — A:268.**
> "### 2. What the controller guarantees today"

The section is a source reading. Part of it is ASSUMED for the image, whose paho version is not recorded (A:34-41, A:277-278, A:314-315), and nothing in it has been tested as a guarantee. Its content is mostly what the controller does *not* ensure. The brief lists "guaranteed" among the words that may not be applied without a decision and a test. The project manager's instruction is to record the selected behaviour before calling anything a guarantee.
*Fix:* "What the controller does today (source reading at `35fe8bb`)".

**F2 — medium — A:99, A:100, A:135, A:155, A:181-185, A:197-198, A:995.** The ADR defines PROVED as "an artefact line states it, or arithmetic on artefact lines gives it". Anything resting on source code is ASSUMED (A:49-53), and a sub-second comparison across clock domains is CONSISTENT-WITH (A:108-111). Several lines break that rule:

- A:99 — "of them written after the poll (1,594 - 1,536) 58 PROVED". The only independent check that the counter at the poll and the log agree is the cross-clock comparison the ADR itself calls CONSISTENT-WITH (A:108-111). The arithmetic alone gives "at most 58", because the event line is written before the counter moves (`service.py:414-415`).
- A:100 / A:135 — "still queued when the process stopped, at least (1,867 - 58) 1,809 PROVED" (1,404 for r01). The lower bound holds as arithmetic. Reading it as "still queued when the process stopped" rests on `queue_depth` being the in-process `asyncio.Queue` (`service.py:171-173`) and on the FIFO consumer — source code.
- A:155 — "The group sizes are PROVED; their labels are not." G1 is cut on the harness clock alone. G2 is cut at the old process's last acknowledgement, a controller-clock instant mapped through the marker. G3a/G3b are cut at a guest-clock collector row at one-second resolution [`scripts/adr0011_figures.py` lines 157-160 and 189-195, printed as `out/adr0011_figures.out.txt` R02.7 / R01.7]. Those three sizes are CONSISTENT-WITH by the ADR's own rule.
- A:181-185 — "every one published after the outage, were written by the new process". "Written by the new process" follows from FIFO order, which is code.
- A:197-198 — "PROVED: in r02 it wrote outcomes until 14.646 s after the restart command". This compares a controller-clock stamp with the harness's restart record at sub-second precision.
- A:995 (corrections table) — "at least 1,809 proved still queued at the stop".

*Fix:* keep PROVED for the counts read off the artefacts. Label the rest CONSISTENT-WITH or "PROVED as arithmetic; interpretation ASSUMED (source reading)". Word the headline as "at least 1,809 of the 1,867 counted in `queue_depth` at the last answered poll never obtained an outcome line in the fetched copy".

### Rule: the restart partition kept as assumption-dependent

**F3 — medium — A:160-168.**
> "The defensible statement is a bound: received by the old process and left without an outcome: at least 1,809, at most 1,985 in r02 … published while nothing was subscribed: at least 151, at most 327 in r02"

The ADR drops the triple, correctly. But these two bounds carry no status label in a section where every other line has one.

- Only the lower bound of the second line is given the cross-clock caveat (A:166-168). The upper bound of the first line, 1,985 = 2,136 − 151, carries the same caveat. Only 1,809 (lower, first line) and 327 = 2,136 − 1,809 (upper, second line) are free of it [`out/adr0011_figures.out.txt` R02.7 ← `scripts/adr0011_figures.py`].
- The two class names still rest on the clean-session semantics and in-order broker delivery, both ASSUMED in 2(e) (A:313-321).

*Fix:* label each bound. State which two ends are clock-free, and that the class names rest on 2(e).

**F4 — medium — A:252-254.**
> "CONSISTENT-WITH the mechanism of section 2: a kill at that instant would have put those 3,593 in the class that r01 and r02 show without an outcome."

This is a counterfactual derived from the source reading. No artefact points at it, so by A:49-53 it is ASSUMED, not CONSISTENT-WITH. The companion diagnosis removed exactly this counterfactual as a correction:
> "Restart counterfactual (the 3,593 "would have been in that second class" had the process been killed) | stated | removed" (D:400)

The two documents now disagree.
*Fix:* remove it, or keep only the observed count and where it was held (as D:130 does), labelled ASSUMED.

### Rule: no threshold, deadline, window, load or ingest rule changed in either direction

**F5 — medium — A:693-695, repeated as a test at A:864-865.**
> "So the `drained` precondition must also require `processing_errors == 0` and `dropped == 0` in the reading."

All nine runbook tests call `drained`, either directly or through `run_test` → `pre` → `wait_ready && drained && snap_pair` (`~/egw-tcg/itest-helpers.sh:173-179`) [vc01, "which of the nine runbook tests call drained"]. Adding two refusal conditions therefore tightens the precondition of every G3 family. It is written as a "must" inside a recovery proposal, not as a separate procedure decision.

The runbook's own argument for the quiet window rests on the session that option 5 removes. Its blind spot (a) "is excluded only by the operator's rule that no simulator, harness run or probe is publishing while `drained` runs, together with the bridge not asking the broker for a persistent session" (`docs/setup/qemu_integrated_gateway.md:1004`) [vc01]. The ADR neither cites `:1004` nor lists it under "What must change".
*Fix:* move the `drained` change to "Open before the decision" as a procedure change for the student, with its effect on every family. Add `qemu_integrated_gateway.md:1004` to "What must change".

**F6 — low — A:914-918.**
> "each timed family that misses its deadline is recorded as failed and as a sizing finding, never absorbed by changing the protocol (`INTEGRATED_DEVELOPMENT_PLAN_2026.md:638-640`)"

The cited plan text at `35fe8bb` says: "a result worse than expected at the nominal rate is recorded as a sizing finding for the pilot" [vc02]. The paraphrase widens the scope of a plan rule.
*Fix:* quote the plan.

### Rule: nothing emulated stated as native; no capacity or maximum-throughput claim from one failed load

Native: both documents pass (D:6, A:43-47).

**F7 — medium — A:563-565 and A:959-960.**
> "at an unmeasured per-message durable write on a guest that is already the constraint"
> "with its per-message cost unmeasured on a guest that is already the constraint"

This names the guest as the limiting factor. The diagnosis establishes neither that nor what limits the served rate:

- it cannot divide one passage between computation, the `PATCH`, event-log I/O and scheduling (D:248-252, D:298-304);
- guest-level or host-level saturation "cannot be excluded" — nor is it established (D:216).

*Fix:* "on a guest that served below the offered rate in every observed phase of one run" (as A:485-486 already says).

**F8 — medium — A:931-936.**
> "The capacity probe proposed in `backlog_diagnosis.md` section 7 would need re-sizing before use: it offered 5.0 msg/s against a margin computed from the window rate, although the nominal warm-up served 4.94 msg/s and the slowest 60 s block of the window 5.35 msg/s"

The diagnosis avoids capacity framing (D:358), so "capacity probe" is exactly that framing. The reference is also stale. The corrected diagnosis proposes its measurement in section 11, at 2.24 msg/s, sized on the lowest 60 s rate of 4.60 msg/s (D:313-334), and records the 5.0 msg/s sizing as corrected (D:394).
*Fix:* "the bounded diagnostic measurement of `backlog_diagnosis.md` section 11 (2.24 msg/s for 720 s)". Drop "would need re-sizing".

**F9 — low — A:458-461.**
> "In no phase of `nominal-r01` did the served rate reach 11.2 msg/s [F:N.5], so under continuing ingress at that rate such a burst is not expected to clear during the run"

This holds for the three phase averages only. In the first two 30 s blocks after the window end, the event log shows 11.600 and 10.633 msg/s [`out/s02_rates_and_queue.out.txt` lines 117-118, section G ← `scripts/s02_rates_and_queue.py`; echoed in `out/verify_constraints/vc04_cross_document.out.txt`]. The diagnosis reports both (D:244). Read alone, the sentence suggests a ceiling.
*Fix:* "in none of the three phase averages".

**F10 — low — A:952-953 (and A:889-890).**
> "At the rates observed, 1,867 queued need 211 to 378 s [F:S.2]"

This applies one failed run's phase rates to another run, in the present tense. S.2 is conditional arithmetic, and A:264-265 phrases it as such.
*Fix:* "would need, at `nominal-r01`'s phase rates, 211 to 378 s".

**F11 — low — A:540-547 (comparison table).** The rows "deliveries inside the controller at a kill" and "publications while the controller is away" use "lost". In this project `lost` is the analysis term "valid message sent without a unique confirmation within 60 s" (`src/CONTRACTS.md:371-372`; `analyze.py:1821`). The project manager's record says it must not be read as permanent disappearance (`PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 2.3).
*Fix:* "discarded (source reading)" and "never delivered (clean session, ASSUMED)".

### Rule: the ADR in the repository's format, status vocabulary and numbering, duplicating no existing decision, citing today's code by file:line

**Status vocabulary — pass.** "Proposed (2026-09-21)" is in the vocabulary (`docs/adr/README.md` at `35fe8bb`: `Proposed`, `Accepted`, `Deprecated`, `Superseded by NNNN`, qualifier allowed) [vc02].

**Numbering — pass.**

- No ADR numbered 0009 or 0011 has been added on any local or remote ref [vc02, "ADR numbers ever added on any ref"].
- 0009 is reserved (`docs/adr/0010-controller-progress-counters.md:10`; `docs/evidence/integrated-qemu/2026-09-18-mongodb7-isolated/README.md:72`) [vc01].

**No duplication — pass.** No existing ADR decides the MQTT session or the acknowledgement point [vc02, "session, acknowledgement and restart terms"]. Option 5 relies on ADR 0006 and conditions ADR 0005 under P5 (A:837-840). See F14.

**F12 — medium — A:28-29, A:407, A:841-842, A:917, A:683, A:820-821.**
> "Every `file:line` below is at the merged `dev` head `35fe8bb`"

The statement is true, and the anchors resolve at `35fe8bb` [vc02]. But at the commit the brief names — `~/egw-exec/repo` HEAD `b7e0c83`, which is also the G2 execution commit — four anchors do not resolve:

- `INTEGRATED_DEVELOPMENT_PLAN_2026.md:104` (the sentence is at `:87` there);
- `:630-631` (at `:572`);
- `:638-640` (at `:581`);
- `PROGRESS.md:509` (the file has 471 lines there; the phrase is at `:330`).

[vc01, "RANGE BEYOND EOF" and "where the plan phrases … sit at HEAD"]

That clone does not contain `35fe8bb`, so nothing in it can confirm the ADR's code-identity line. The code anchors are unaffected (section 2).
*Fix:* state that the plan and `PROGRESS.md` anchors hold at `35fe8bb` and not at `b7e0c83`, or cite the plan by section heading. Updating the WSL clone needs a fetch, which is a state change and was not done here.

**F13 — medium — A:988-1053 and A:56-64.** The repository describes ADRs as "MADR-style short form (Status / Context / Decision / Consequences)" (`docs/adr/README.md`). The nine existing ADRs run from 42 to 210 lines [vc02, "length and section headings"]; 0011 has 1,060.

Length alone is not the defect. Two sections would not survive being moved into `docs/adr/`:

- "Corrections to the draft of 2026-09-20" (A:988-1012) is about an unnumbered draft that is not in the repository, and cites `verification_figures.md` and `verification_constraints.md`.
- "Sources and reproduction" (A:1016-1053) points every `[F:…]` and `[C]` at scripts in "a working directory that will not survive the session" (A:1030-1032).

The body also cites `controller_today.md` and `restart_evidence.md` (A:60-64, A:167, A:176, A:365, A:380). Once committed, all of these dangle. Separately, the title states option 5 ("acknowledge each message only after its outcome is recorded, on a persistent MQTT session") while the Status says the decision is the student's. If he chooses option 4 or 3, the title is wrong.
*Fix:* commit the figure scripts and analyses beside an evidence or review record and cite that. Move the corrections table out of the ADR. Consider the neutral title "Controller restart recovery".

**F14 — low — A:806-810, A:837-840.** ADR 0010 records that it leaves "the shutdown sequence" unchanged (`docs/adr/0010-controller-progress-counters.md:113-116`). It puts the shutdown exclusion — `queue_depth` may include the marker — into the contract (`:80`, `:139-141`) [vc02]. Option 5 removes the marker-and-drain (A:579, A:809-810) and changes the meaning of `dropped` (A:806-807), which is a term of 0010's identity. The ADR lists which 0010 follow-ups it takes up, but not that it amends 0010's shutdown exclusion.
*Fix:* one sentence under "Contracts and records".

### Rule: the proposed measurement and the proposed proof finite, each with a question and a refuting result — never a campaign, a soak or a rerun of the long nominal entry

Both pass in substance.

- **Diagnosis:** question D:317, refutation D:347-350, inconclusive D:354, hard bound 43.0 min D:341 [`out/s07_probe_sizing.out.txt` section C ← `scripts/s07_probe_sizing.py`]. It runs at 2.24 msg/s outside the plan and is not the nominal entry (D:338, D:362).
- **ADR:** question A:718-721, support S1–S6, refutation R1–R4, inconclusive A:774-776. It runs 300 s and is explicitly not a campaign, soak, pilot or repetition (A:701-703).

**F15 — low — A:715.**
> "Hard ceiling 35 minutes with the helper's default limits, fetches excluded [F:P.3]"

P.3 is 900 + 300 + 900 s [`out/adr0011_figures.out.txt` P.3 ← `scripts/adr0011_figures.py`]. It leaves out the unchanged 60 s confirmation window that a harness run also waits, and the `/ready` wait. The diagnosis's bound includes the 60 s (D:341).
*Fix:* add the 60 s, or list what the ceiling excludes.

### Rule: the throughput question kept separate from the recovery decision and left to the student

**ADR — pass.** "Relationship with the throughput problem" (A:895-942) states that the recovery decision makes no family meet its deadline. It leaves T1–T4 to the student and lists concurrency among the rejected alternatives (A:961-962).

**F16 — medium — D:352 and D:365.**
> "the account of section 7 would have to be revised before the recovery decision or the G3 battery rests on it"
> "**Package D proposes two guest runs in total**: this one and the finite proof of the recovery ADR. This one comes first: the ADR draft sizes its proof run at 5.0 msg/s against the 6.457 msg/s average (`../adr-recovery-draft.md`) … so that sizing has to be redone"

The diagnosis makes its probe a precondition of the recovery decision and fixes the order of the runs. The ADR offers that probe to the student as option T3 of the throughput decision (A:931). The reason the diagnosis gives for the order is also stale. The corrected ADR's proof runs at 11.2 msg/s and uses no timing in any criterion (A:710-712, A:1002), so no sizing "has to be redone".
*Fix:* cite `adr-0011-controller-restart-recovery.md`, drop the stale reason, and say that whether the probe runs before the decision is the student's call under T3.

**F17 — low — D:4, D:8, D:363.**

- D:4 says the recovery "is decided in the recovery ADR draft". The ADR "records a proposal, not a decision" (A:4).
- D:8 cites code "at `3549d46`", a branch commit that is not on `dev` [vc02], while the ADR cites `35fe8bb`.
- D:363 cites the pause record "at commit `3549d46`" without saying that it is not on `dev` yet. A:910-912 does say so.

*Fix:* "proposed in ADR 0011"; cite at `35fe8bb`; add "not yet on `dev`".

### Rule: British English, ISO dates, no text-generation tool named

**Documents — pass.** No American spelling was found outside code identifiers such as `analyze.py`. Every date is `YYYY-MM-DD`, and every instant is ISO with `Z`. There are no tool names [vc03].

**F18 — low — `scripts/adr0011_code_anchors.sh:9`.** The script hard-codes an absolute path, and one segment of that path is the name of a text-generation tool [`out/verify_constraints/vc04_cross_document.out.txt`, part (a), with the name masked ← `scripts/verify_constraints/vc04_cross_document.py`]. The ADR says that its scripts "travel with this record" (A:1030-1032).
*Fix:* locate the worktree relative to the script, as `run_all.sh` does.

### Consistency between the two documents (no named rule; it affects the decision)

**F19 — low — A:260 and A:935 against D:101-110 and D:327.** The same quantity, the served rate in 60 s blocks of the measured window, appears in three constructions:

| Source | Range | Slowest block | Where |
|---|---|---|---|
| ADR | 5.35 to 8.57 msg/s | 5.3470 | `out/adr0011_figures.out.txt` N.7 ← `scripts/adr0011_figures.py` |
| Diagnosis, event log | 5.3167 to 8.5500 msg/s | 5.3167 | `out/s02_rates_and_queue.out.txt` lines 35-48 ← `scripts/s02_rates_and_queue.py` |
| Diagnosis, counters | 5.3158 to 8.4576 msg/s | 5.3158 | same |

[both echoed in vc04, part (c)]

A reader of both documents gets two different "slowest block" figures for one run.
*Fix:* one construction, from one script, cited by both.

---

## 4. Result by rule

| Rule | Diagnosis | ADR 0011 |
|---|---|---|
| Nothing called accepted / proved / guaranteed / closed without a decision and a test | pass | **breach**: F1, F2 |
| No threshold, deadline, window, load or ingest rule changed, either direction | pass | **breach**: F5 (the `drained` precondition, tightened); F6 (paraphrase) |
| Restart partition kept assumption-dependent | pass (D:130) | partly: triple dropped (A:172-177); F2, F3, F4 |
| Nothing emulated as native | pass | pass |
| No capacity or maximum-throughput claim from one failed load | pass | **breach**: F7, F8; F9, F10 low |
| No date naming a supervisor's act | pass | pass |
| ADR format, status vocabulary, numbering, no duplication, code by `file:line` at the current commit | — | status, numbering, no duplication: pass; format F13; anchors F12; F14 |
| Measurement and proof finite, with a question and a refuting result, never a campaign / soak / nominal rerun | pass | pass; F15 low |
| Throughput kept separate and left to the student | **breach**: F16 | pass |
| British English, ISO dates, no tool named | pass | pass in the text; F18 in a travelling script |

---

## 5. Could the student decide the ADR from these two documents alone?

**Not yet.** They are close. The choice in front of him is visible: option 5 against option 4, with option 3 held in reserve. Three things are still missing: the decisive open item, the effect on seven of the nine families, and one consistent sequence.

### 5.1 What is stated well

- **Options.** Five options, each with what it promises, what it does not, its cost on the controller's path and in the broker, and its effect on tests 5 and 6. A comparison table covers all five (A:540-547).
- **Costs.** The per-message costs are explicitly unmeasured. The algebra of what a measured cost would do is labelled as algebra (A:385-401).
- **The selected behaviour.** The admission, acknowledgement and persistence behaviour is recorded before anything is called a guarantee (A:570-598), as the project manager required. The four conditions — ordering, duplicates, durability and configuration identity — are addressed (A:658-695).
- **Unknowns.** Most are visible and phrased as "I could not establish":
  - the broker's in-flight window, queue bound and expiry, and their memory cost within 128 MiB (A:431-433, A:448-450, A:591-598);
  - redelivery within a live session (A:689-692);
  - the image's paho version (A:34-41);
  - whether the cross-thread `ack` is safe (A:802-805);
  - the guest-side evidence of r02 (A:224-229);
  - the twin rebuild across a restart (A:217-222).
  
  There is a section listing what is open before the decision (A:967-976), and the proof states what it cannot show (A:778-785).
- **Throughput.** It is kept apart and left to the student (T1–T4, A:895-942).

### 5.2 What stops a decision

1. **The ADR's own open items come first.** Open item 1 is whether `eclipse-mosquitto:2.0.22` accepts an in-flight window W with 3,593 ≤ W ≤ 4,999, and at what memory within 128 MiB. A:591-598 says that if it cannot, "the option is re-decided". Until that is answered from the broker's documentation, option 5 is a candidate, not a decision.

   Open item 2 is whether to read r02's guest-side evidence first. The repository's own proposal places the design decision after that evidence has been read (`docs/governance/proposals/acceptance_protocol_update_2026-09-19.md:418-425`, `:452-454`, a proposal, at both `b7e0c83` and `35fe8bb`) [vc02]. The ADR leaves this choice visible (A:972-973), but it is a gate on the decision, not a follow-up.

2. **The effect on the G3 families is stated for tests 5 and 6 only** (A:403-411). Four consequences the student needs are not stated:
   - **Every family:** all nine tests call `drained`, directly or through `run_test` → `pre` [vc01]. Option 5 removes the clean-session premise of the runbook's quiet-window argument (`qemu_integrated_gateway.md:1004`), and the ADR's remedy changes `drained` for all of them (F5).
   - **Test 8, guest reboot** (`qemu_integrated_gateway.md:1183`): a persistent controller session combined with the broker's 60 s autosave (`mosquitto.conf:33-35`) across a reboot is not discussed.
   - **Test 6 and claim C12 under every option.** The harness's C12 gate `delivery_across_restart_zero_lost` requires `lost == 0` under the deadline (`src/egw_experiments/analyze.py:2715-2718`) [vc01]. The ADR expects late confirmations under option 5 (A:532-533, A:902-906), so that gate is expected to fail under options 1–5 alike at 11.2 msg/s. The ADR says C12 "could not be supported on delivery" only under option 4 (A:504-506), which invites the reading that option 5 would support it. What differs between options is whether the identities are processed late or never — not whether test 6 passes.
   - **Test 6's `delta` in the battery.** An N1 identity leaves a twin one ahead of its `accepted` lines. The proof tolerates that (S5, A:755-757), but test 6 requires every `delta` line `OK` (`qemu_integrated_gateway.md:1130`). The battery would record a `MISMATCH`.
   
   Tests 1–4, 7 and 9 are not mentioned. The likely answer is "unchanged": for example, test 7's `failed` outcomes are acknowledged under the selected behaviour (A:577), so nothing is redelivered. But the student should not have to infer it.

3. **No cost in time.** Option 5's work is ten code items, contract edits, seven test groups, harness changes and one guest run (A:789-870). It is described as "the larger part of the work" (A:716) but not estimated. The stable-candidate target, 2026-09-25 in the project manager's record (`PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 5, item 5), is not weighed against any option; only T2 mentions the candidate date (A:929-930). Option 4's cost (none) is stated.

4. **The two documents give two sequences.** The diagnosis runs its probe first and makes the recovery decision wait on it (F16). The ADR makes that probe an optional T3. On top of that, one counterfactual is removed in one document and kept in the other (F4), the probe is misdescribed and stale (F8), and the slowest-block figure differs (F19).

### 5.3 Whether what is unknown is visible

Mostly yes, and more honestly than in round one. There are three exceptions:

- some assumption-dependent restart figures are presented as PROVED (F2, F3);
- the clean-session premise of `drained` is not mentioned (F5);
- the ADR does not say plainly that no option changes the expected test 6 / C12 verdict at 11.2 msg/s (5.2 item 2).

### 5.4 The smallest additions that would make it decidable

1. Answer open item 1 from the broker's documentation: the window, the queue bound, the expiry and their memory. Say whether option 5 survives.
2. Add one table: options 1–5 against tests 1–9 and the four C12 gates (hook, zero lost, zero double-accepted, recovery evidence). Each cell gives the expected outcome and the anchor, with "unchanged" written where it is unchanged.
3. Estimate the calendar cost of each option against the candidate target.
4. Resolve F16, F4, F8 and F19, so that both documents tell one story: what runs first, and why.
5. Record the student's answer on open item 2 (guest-side evidence first) before, not after, the decision.

---

## 6. Sources and reproduction

All paths are relative to this directory. Run from Git Bash:

```
bash scripts/verify_constraints/run_verify_constraints.sh
```

The runner writes only `out/verify_constraints/<script>.out.txt`.

| Script | Reads | Produces |
|---|---|---|
| `vc01_resolve_citations.sh` (in WSL) | `~/egw-exec/repo` at HEAD via `git show`; `~/egw-tcg/itest-helpers.sh` | every `file:line` of both documents at the current commit; the objects present; the lines of section 5 (`analyze.py:2704-2719`, runbook `:1004`, `:1183`, `pre`); which of the nine tests call `drained` |
| `vc02_merged_dev_differences.sh` (Git Bash) | the worktree `../../devwt` via `git show / diff / log / ls-tree / grep` | the cited files that differ `b7e0c83..35fe8bb`; the plan and `PROGRESS.md` anchors at `35fe8bb` and `3549d46`; the ADR README; length and headings of every ADR; the ADR numbers on every ref |
| `vc03_wording_scan.py` (WSL, standard library) | the two documents | every line carrying a watched word, per rule |
| `vc04_cross_document.py` (WSL, standard library) | the two documents; `scripts/*`; `out/adr0011_figures.out.txt`; `out/s02_rates_and_queue.out.txt` | tool names in the travelling scripts (masked); cross-references between the documents; the 60 s block and drain rates as each document's own output states them |

Figures quoted from the documents' own outputs (`out/adr0011_figures.out.txt`, `out/s02_rates_and_queue.out.txt`, `out/s07_probe_sizing.out.txt`) were produced by the scripts named beside them (`scripts/adr0011_figures.py`, `scripts/s02_rates_and_queue.py`, `scripts/s07_probe_sizing.py`). They were read here, not recomputed.

**This report closes no gate, admits no claim, accepts no result and changes no rule. It judges only whether the two documents keep the project's rules and whether they are enough for the student's decision.**
