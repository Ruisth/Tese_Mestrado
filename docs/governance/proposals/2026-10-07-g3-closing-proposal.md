# G3 closing proposal — the P0 feature freeze on the emulated candidate

**Written:** 2026-10-07.
**Status: PROPOSED — for the student's decision, not adopted.**

> **A proposal, not a decision. G3 stays `Not decided`** in the
> [gate-decision log](../gate_decision_log.md) until the student (Rui Duarte)
> records a dated decision there, with an authority and a durable record.
> Merging this file and its capsule decides nothing: "**Sealing is not
> acceptance**, and neither is a green documentation pull request" (plan
> line 599).
>
> **ARM64 EMULATED (QEMU/TCG) on an x86-64 WSL2 host**, the load generator
> alongside ([results addendum](../g3-battery-2026-10-results.md) line 27).
> Timings are observations, never performance results.

**Sources.** Repository files with their line numbers as at `dev` = `1fd9792`, before this pull request; packages
under the [capsule](../../evidence/g3-battery-2026-10/README.md). "Addendum": the results addendum; "Packet": the
decision packet of 2026-10-01, revision 2 (`2026-10-01_g3-candidate-freeze-and-battery-packet.md`); the Packet and the
other notes cited by file name are the local notes of `output_test/decisions/`, published byte for byte in the
capsule's [`records/`](../../evidence/g3-battery-2026-10/records/); "Register": the Project Manager's instruction
register, held outside the repository, cited by entry heading and line.

## 1. What G3 asks

[Plan section 4.3](../INTEGRATED_DEVELOPMENT_PLAN_2026.md) (lines 626–641),
clause by clause in section 4; the families are the runbook's
([`qemu_integrated_gateway.md`](../../setup/qemu_integrated_gateway.md)
section 7).

## 2. The candidate and its identities

| Layer | Identity | Recorded in |
|---|---|---|
| Emulation, guest | QEMU 8.2.7 **TCG**, `-cpu cortex-a76 -smp 4 -m 8192`, no `-no-reboot`; the integrated Yocto image of 2026-09-18 (build `20260918120819`); the launcher and kas checkout at `489bc9e`, clean, which is not a build record of the image (Packet line 81); identical in the five openings | session packages `console/001-identities-before-boot.stdout.txt` lines 14–15, 17–18, 35–36, 38–42; the QEMU command line, `boot/s1.log` line 35 |
| Root file system | each open equal to the previous close, `c49500a9…` to `1605905b…` | operator-records packages, close consoles line 61 |
| Controller image | `sha256:9a293fe1…` from `489bc9e`, verified at every preflight, never rebuilt | gate records `environment/container_identities.txt` line 6; preflights' `console/001-stack-start-interlock.stdout.txt` line 9 |
| Images, containers | five pinned images (`images.lock.env` `8a9a05df…`); the same six container ids around every row | gate records lines 1–6; rows' `console/*guest-state-*.stdout.txt` |
| Deployment | `compose.yaml` `1a32f6c2…`, `mosquitto.conf` `ea37827c…`; collector `11444c0a…` (S1–S3), `9e678b02…` (S4) | preflights `console/004-deployed-tree-hashes.stdout.txt` lines 4–10 |

## 3. The sessions and the packages

**The capsule:** 38 packages (31 indexed, 7 added for T6) and the 22 local
notes of the battery under `records/`; 2,525 sealed entries, 75,731,082 bytes
of packages; each package's `SHA256SUMS` intact;
`PACKAGES.sha256` of 38 lines; outer seal `SHA256SUMS` (`4517e91e36dbe03963a25474c47af5c05510ba2a221f4d0ef5fc41bb59fb00f9`);
originals compared and secrets swept
([README](../../evidence/g3-battery-2026-10/README.md));
`repo_dirty_lines` 0 in every row (rows' `attempt.json`).

| Session | Authorisation (local note) | Rows | Outcome as recorded |
|---|---|---|---|
| S1, 2026-10-02 | `2026-10-02_g3-freeze-and-battery-authorisation.md` (Q1 freeze, Q2 battery) | 1–7: T1–T5 | no halt (Addendum line 29) |
| S2, 2026-10-03 | the same | 8–11: T6, T7 ×2, T8; 12: T9 | halt 5 at T8; T9 not run (Addendum line 30) |
| S3 first opening, 2026-10-05 | `2026-10-05_g3-s3-session-authorisation.md` | none | halted at the preflight (Addendum line 77) |
| S3 second opening, 2026-10-05 | `2026-10-05_g3-s3b-exception-authorisation.md` (exception not used) | 13–14: T8, T9 | Addendum lines 78–83 |
| S4, 2026-10-07 | `2026-10-07_g3-s4-session-authorisation.md` | 15: T6 | `2026-10-07_g3-t6-results.md` lines 9–16 |

## 4. Clause by clause

### 4.1 The conditions common to G2–G7 (plan lines 588–604)

**C1** labelling: all 28 exported `SUMMARY.md` labelled, harness input
labelled (Packet line 83): **met**. **C2** identity binding: section 2,
**met**. **C3** sealing: `tools/ci/verify_evidence.py` green on the final
head; **open until then**. **C4** sealing is not acceptance: honoured. **C5**
failures kept: section 4.6. **C6** no pooling, no performance result: no
native run, **met**.

### 4.2 The nine families

Classes: Addendum lines 44–55, 82–83; row 15,
`2026-10-07_g3-t6-results.md` line 21. Expected lists: runbook lines
1305–1412, 1464 (T1–T5, T7, at `80e833f`); 1503, 1537 (T8, T9, at `8e49261`);
1427, 1433 (T6, at `1fd9792`).

| Subtest | Row, package | Class as recorded | Shown (source); qualifications |
|---|---|---|---|
| T1 smokes | 1, `2026-10-02/20261002T150829Z_g3-qualification-t1-smokes_attempt01` | Pass | 336 of 336 ×3, `lost` 0, `delta` OK (`console/002-t1-smokes.stdout.txt`) |
| T1 harness `nominal-r02` | 2, `2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01` | Pass (artefact chain, decision 1b) | manifest `valid`, collector `missing=none` (`raw/nominal-r02/manifest.json`); delivery reported only (Addendum line 45), not counted towards C14 (runbook line 1320) |
| T2 | 3, `2026-10-02/20261002T154427Z_g3-qualification-t2_attempt01` | Pass | 672 of 672, `lost` 0, `delta` OK (`console/002-t2.stdout.txt`); twins pre-existed (limitation 7) |
| T3 | 4, `2026-10-02/20261002T155313Z_g3-qualification-t3_attempt01` | Pass | 67 invalid rejected, 0 valid rejected, 1,277 valid accepted (`console/002-t3.stdout.txt` lines 124–166); not timed |
| T4 replay | 5, `2026-10-02/20261002T160154Z_g3-qualification-t4-replay_attempt01` | Pass | 672 of 672 `duplicate`, none accepted again, k = 0 (`console/002-t4-replay.stdout.txt` lines 181–245); not timed |
| T4 sequence reset | 6, `2026-10-02/20261002T161432Z_g3-qualification-t4-reset_attempt01` | Pass | 672 of 672, 0 duplicates, `lost` 0 (`console/002-t4-reset.stdout.txt` lines 124–131); first run (Addendum line 49) |
| T5 | 7, `2026-10-02/20261002T162159Z_g3-qualification-t5_attempt01` | Pass, as sealed; reading admitted 2026-10-05 | 2,016 of 2,016, `double_accepted` 0; 4 disconnection lines = 3 faults + teardown (`simulator/itest-dropout-01-q1.*`); no C10 claim ([decision record](../g3-t5-t6-decisions-2026-10-05.md) lines 9–16) |
| T6 `controller_restart-r03` | 8, `2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01` | **Invalid instrumentation**: two controller rows inside the proved-down interval, inner run unsealed (Addendum line 51) | `T6=stop` (`console/003-t6.stdout.txt` lines 33–49) |
| T6 `controller_restart-r04` | 15, `2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02` | **Pass** under the criterion amended on 2026-10-05 | `T6=ok`, run sealed, drain `quiet`; one restart at +300 s, then `EXPECTED-RESTART`; endpoint 12.134 s ≤ 120 s; `delta` OK, N1 0/0; 6,720 exactly once **in this run** (`console/003-t6.stdout.txt` lines 46–58; `console/006-guest-state-delta.stdout.txt` line 6; `raw/controller_restart-r04/manifest.json`, `restart`; `other/processed.after/per_run.csv`) |
| T7 MongoDB | 9, `2026-10-03/20261003T135147Z_g3-qualification-t7-mongo_attempt01` | Pass | same container restarted; 3,360 of 3,360 with an outcome, 44 `failed`; `delta` OK (`console/002-t7-mongo.stdout.txt`); `lost` 1,209 = 1,165 late + 44 failed (Addendum line 52) |
| T7 Ditto | 10, `2026-10-03/20261003T140639Z_g3-qualification-t7-ditto_attempt01` | Pass (first run of this half) | the same; 5 `failed`; no OOM at 768 MiB; `lost` 1,895 = 1,890 late + 5 failed (Addendum line 53) |
| T8 `itest-reboot-q1` | 11, `2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01` | **Inconclusive / not demonstrated — HALT** (incomplete) | not evaluated; procedure defect: runbook line 1487 at `80e833f` assumed a QEMU exit never produced (Addendum, "Boundaries the Project Manager states", T8) |
| T9 in S2 | 12, no package | **Not run** | after the halt |
| T8 `itest-reboot-q2` | 13, `2026-10-05/20261005T115131Z_g3-qualification-t8_attempt02` | Pass | same QEMU process; reboot, containers back unaided, event directories kept, tunnel up, twins identical, new controller; smoke 336 of 336 (consoles 002–015) |
| T9 | 14, `2026-10-05/20261005T120537Z_g3-qualification-t9_attempt01` | Pass | wrong CA, wrong password, plaintext and anonymous refused; ACL probe `verdict=PASS` (consoles 002–006) |

**Position.** Every subtest has a Pass row on its own adopted criterion
(rows 1–7, 9–10, 13–15; Register, 2026-10-07 14:19 WEST, lines 5090–5091).

### 4.3 One unchanged image and container set, in order

Section 2 held; containers restarted, never recreated (preflights'
`console/001-stack-start-interlock.std*.txt`: no `Recreate`). The Packet's
plan, "S1 = T1–T5, S2 = T6–T9, same candidate" (line 58), was not kept: the
standing rows span five cold boots, two in-process reboots and three tool
commits. After T8's halt in S2 and its correction (PR #54), T8 and T9 ran in
S3 with fresh `-q2` identities (Addendum rows 11–12; "Outstanding decisions", item 3). T6's S2 run
stays invalid; after the student's prospective amendment of 2026-10-05
(option 2, with option A), T6 ran alone in S4
([decision record](../g3-t5-t6-decisions-2026-10-05.md) lines 18–73). The
only deployed change was the collector, replaced at S4's open
(`2026-10-07/20261007T120444Z_live-preflight_attempt13`
`console/003-collector-install.stdout.txt` lines 1–2). The Register: "This was
not one continuous identical-tool execution" (lines 5089–5090). The student
decides (section 9).

### 4.4 The public contracts frozen

`src/CONTRACTS.md` v1.2 `247e3b02…` and `src/schemas` `1d5284cf…` are
identical at `489bc9e`, `80e833f`, `8e49261` and `1fd9792`
(`HIST_2026-10-02-g3-battery-host-preparation` `part1-record/console.txt`
lines 17, 28, 37; `HIST_2026-10-05-g3-t8t9-host-preparation` lines 32, 45, 53;
`HIST_2026-10-05-g3-t6-host-preparation` lines 64, 78, 87). **Met**: Q1 is the
freeze record; [`backlog.md`](../../g0/backlog.md) line 255 still says "v1.1"
(Packet line 80).

### 4.5 No open P0 defect; the `ditto-things` incident

- **No open P0 defect is recorded.** "P0" is the plan's mandatory scope (lines
  282–299), not a severity; no P0 defect register exists (`docs/`,
  `PROGRESS.md`, `LOG.md`, `README.md`). "P0 or safety blocker: none found"
  (Packet line 228); no row is a valid SUT failure (Addendum lines 44–55,
  77–83).
- **Two findings of 2026-09-19 stay "Open"**, neither labelled P0
  ([`risks.md`](../../g0/risks.md) lines 230–231): a restart appears to
  discard the in-memory queue, though ADR 0011 option 5 and its proof r03
  have since been accepted, the proof with qualifications
  ([ADR 0011](../../adr/0011-controller-restart-recovery.md) lines 3–12), and
  r04 accepted 6,720 exactly once (`2026-10-07_g3-t6-results.md` line 31);
  and the nominal-rate shortfall, a sizing finding (plan lines 638–640).
- **Battery defects** were of procedure or instrumentation, fixed in tools,
  never in the system under test (Addendum, "Boundaries the Project Manager states"; LOG lines
  4515–4554, 4652–4656, 4787–4821;
  `2026-10-07_g3-t6-preparation-supplement.md` lines 12–22).
- **`ditto-things`** was OOM-killed at 512 MiB on 2026-09-18 (plan line 189);
  PR #34 set 768 MiB (`src/deployment/compose.yaml` lines 159, 194, 240),
  and the stack is stopped gracefully before power-off (plan line 189). **Proposed bounded
  wording:** across S1–S4, T7's Ditto fault and T8's reboots included, no
  memory-cgroup OOM kill and no OOM-killed container was recorded (the five
  operator-records packages; Addendum line 53). Not a stability statement;
  the footprint re-measurement (`backlog.md` line 239) is **not recorded**.

### 4.6 Every failed run retained

Kept as sealed, none relabelled (capsule README): row 8, r03, invalid
instrumentation (Addendum line 51); row 11, `itest-reboot-q1`, incomplete, with
`2026-10-03/20261003T132249Z_guest-session_attempt09` (line 54); row 12, not
run (line 55); S3's first opening,
`2026-10-05/20261005T105656Z_live-preflight_attempt11`, instrumentation
invalid, inconclusive (line 77). Earlier runs (2026-09-18; T6 r01–r02) keep
their records (gate-decision log; runbook line 1435). **Met.**

### 4.7 No threshold moved

| Date | Change | Source | Thresholds |
|---|---|---|---|
| 2026-09-30 | decisions 1a–4 | the student ([pending-decisions page](2026-09-29-g3-pending-decisions.md) lines 40–51) | none moved (lines 232–233); T6 made timed, a tightening (`2026-10-05_g3-t6-decision-page.md` line 52) |
| 2026-10-01 | T4 replay judgement | cleared in the Register, 2026-10-01 20:34 WEST; merged by the student as `80e833f`; frozen by Q1/Q2 of 2026-10-02 (Packet lines 3–4) | a tightening |
| 2026-10-03 and 2026-10-04 | T8 in-process reboot | recommended in the Register, 2026-10-03 15:50 WEST, relayed by the student; merged as `8e49261`; used under the authorisation of 2026-10-05 (LOG lines 4394–4398) | none (Addendum line 82) |
| 2026-10-05 | T5 reading | the student ([decision record](../g3-t5-t6-decisions-2026-10-05.md) lines 3–16) | none |
| 2026-10-05 | **T6, option 2:** the deadline reported, not required | the student (same record, lines 18–45) | **a criterion changed by dated decision, prospectively, before its run**; "the controller-restart family only" (plan line 640); 60 s and the load unchanged |
| 2026-10-05 | option A; `collector-duration` bounds | the student (`2026-10-05_g3-t6-sampling-option-a-decision.md` lines 3–8, item 2) | none; tolerance unchanged (LOG line 4806) |

Thresholds (60 s, 11.2 msg/s, 600 s, 120 s, 5 s, 30 instants, 90 %)
unchanged; 5 s, 120 s, 90 % stay "PENDING ADVISOR SIGN-OFF BEFORE exp-v1"
(`src/egw_experiments/protocol.py` lines 109–112, 119–121, 165–168). **Met**:
every change dated, none silent; T6's amendment stated.

## 5. Tools and procedure versus the system under test

| Change | Where | Authority | System under test |
|---|---|---|---|
| S1/S2 tools | `80e833f`, PR #53 (in `src/`, only `src/egw_experiments/` outside the tests differs from `489bc9e`; the session tools and the runbook changed too) | Q1/Q2, 2026-10-02 | unchanged; never imported by the image (Packet line 77) |
| T8 procedure | `8e49261`, PR #54 | authorisation of 2026-10-05 | "nothing under src/ outside src/tests" (`HIST_2026-10-05-g3-t8t9-host-preparation` `part1-record/console.txt` line 31) |
| T6 prerequisites | `1fd9792`, PR #57; collector `11444c0a…` → `9e678b02…` | decisions of 2026-10-05; S4 authorisation | "no change to the system under test" (LOG lines 4778–4781); the collector is instrumentation (lines 4808–4810) |
| Emergency cleanup | `ops/g3_recorder_cleanup.sh` (`HIST_2026-10-07-g3-t6-preparation-supplement`) | requested in the Register, 2026-10-05 21:56 WEST; within the student's S4 authorisation | operator path; not exercised (`2026-10-07_g3-t6-results.md` lines 18–19) |
| Harness inputs | `sut_environment.json` per preflight (Packet line 83); r04 added (`HIST_2026-10-05-g3-t6-host-preparation` `host-record/static_values.console.txt` lines 31–32) | each preparation | host side |

A rebuild at `1fd9792` would differ from the retained image (LOG lines
4839–4841).

## 6. What is not claimed

1. Any performance, capacity, latency, efficiency or native property (plan
   lines 640–641).
2. **Timely delivery at 11.2 msg/s** (section 7): T1's `nominal-r02` validates
   the artefact chain only, and T6's populations are the initial, late and
   final ones of section 7.2, never summed.
3. Any claim: no C10 or C12 admission; C06, C10, C11, C12, C14 stay "Pending —
   no evidence" ([claim matrix](../../claim_evidence_matrix.md) lines 167–175).
   T5's `check` warning about C10, a documented layout mismatch, stays as
   recorded ([decision record](../g3-t5-t6-decisions-2026-10-05.md) lines 9–16).
4. T7 beyond its two bounded faults, one stop of MongoDB and one of Ditto: no
   general lossless or prolonged-stability claim under dependency faults
   (Addendum, "Boundaries the Project Manager states").
5. A general exactly-once guarantee beyond r04 (Register, 2026-10-07 14:19
   WEST, lines 5024–5026), or durability across a broker restart or guest
   loss (ADR 0011 N3, lines 1337–1349).
6. Stability over time; no soak ran (claim matrix line 174, C13).
7. T9 beyond the tested controls: no security audit, no LAN or firewall
   exposure (Addendum lines 92–96).
8. T8 beyond event-directory names and identical twins: no byte-level
   persistence across a reboot (Addendum lines 87–88).
9. Reproducibility: one run per family (LOG line 4600).
10. A G4 pilot, `exp-v1` or campaign; the 2026-10-20 target and the 2026-10-31
    latest date unchanged (Register, 2026-10-07 14:19 WEST, lines 5104–5105).
11. A re-judgement: `restart_recovery_observed_every_run: FAILED - 1/4` stays
    as printed (r04 `console/003-t6.stdout.txt` line 64).

## 7. Residual limitations

1. **Emulated, on a shared host** (Addendum line 27); one run per family
   (LOG lines 4600–4601).
2. **Timely delivery at the nominal load was not demonstrated.** For r04,
   `lost` = `sent_valid` − the messages confirmed by the deadline in the timed
   copy (`events.jsonl`, fetched after the confirmation window) = **2,153**;
   `late_confirmations` = the accepted lines of that same timed copy whose
   acknowledgement is after the deadline = **67**, and each of those 67 is one
   of the 2,153 (a late line is not counted as confirmed), so **the 67 are
   included in the 2,153, never added to it**; the other **2,086** were
   accepted after the timed copy was taken, during the drain. **None of the
   2,153 is a permanent loss:** all 6,720 valid messages were accepted exactly
   once by the end of the drain (`events.post-drain.jsonl`). Functional
   recovery was demonstrated in this run; timely delivery at 11.2 msg/s,
   deadline = the controller marker + 60 s, was not
   ([`analyze.py`](../../../src/egw_experiments/analyze.py) lines 1750–1821;
   `2026-10-07_g3-t6-results.md` lines 31–36). `nominal-r02`, with no
   post-drain copy: 2,136 not confirmed by the deadline (`lost`), 111 of them
   late in its only copy, the other 2,025 absent from it and not traced per
   identity (`raw/nominal-r02/manifest.json`). The cause is not isolated: the
   serial consumer served about 6–9 msg/s, and lateness also occurred without
   a restart (LOG lines 4723–4731).
3. **Thin margins:** T8's smoke, 1.338 s; T1's first smoke, p95 about 50 s
   (Addendum lines 44, 82).
4. **T6's figures:** 12.134 s is the endpoint's return, not functional
   recovery (20.04 s); the 120 s bound awaits sign-off; the monotonic clock
   across a restart is `UNVERIFIED` (runbook line 1433); N1 0/0 does not
   prove every branch; the cleanup is tested offline only
   (Register, 2026-10-05 21:56 WEST, lines 4989–4995; 2026-10-07 14:19 WEST,
   lines 5028–5031, 5056–5058).
5. **Not assessed:** a reboot while the broker holds the controller's
   persistent session; W and Q, by arithmetic only (Packet lines 240–241).
6. **Not hashed:** the data disk (Packet line 82); root file system changes
   below whole-file hashes (close consoles line 61).
7. **Unmentioned in the session records:** T1 harness, 23
   `controller_metrics.csv` rows dropped in `per_run.csv`; T2, the
   pre-existing twins (`simulator/*.twins.before.json`); T4 replay, an
   "IMPLAUSIBLE controller confirmation marker" warning
   (`console/002-t4-replay.stdout.txt` lines 200, 233); T9,
   `other/wrong.crt` exported, no private key (`sources.json` lines 41–42),
   contrary to the S3 note (`2026-10-05_g3-t8-t9-s3b-results.md` lines 61–62).

## 8. What the student would be accepting

For the G3 row; the date is left to the recording.

> **G3 — P0 feature freeze. Accepted on the emulated candidate below, for the
> nine integration/recovery families each on its own adopted criterion, and for
> nothing else.** Evidence: the capsule `docs/evidence/g3-battery-2026-10/`
> (38 packages, outer seal `4517e91e36dbe03963a25474c47af5c05510ba2a221f4d0ef5fc41bb59fb00f9`): S1 and S2 (2026-10-02 and 2026-10-03, tools
> `80e833f`), S3 (2026-10-05, `8e49261`), S4 (2026-10-07, `1fd9792`), every
> failed, incomplete and halted attempt kept as recorded. The system under test
> was the same throughout: controller image `sha256:9a293fe1…` from `489bc9e`,
> the five pinned images, the same six container objects, `compose.yaml`
> `1a32f6c2…`, `mosquitto.conf` `ea37827c…`, contracts v1.2 `247e3b02…`, the
> Yocto build `20260918120819` under QEMU 8.2.7 **TCG**. **ARM64 EMULATED
> (QEMU/TCG) on an x86-64 host — never native ARM64, never KVM.** Not one pass
> in order: a dated, prospective amendment of T6's criterion (2026-10-05; plan
> line 640) and dated, authorised changes of procedure (T8) and of
> instrumentation (the collector); none of the system under test.
> **Timely delivery at 11.2 msg/s was not demonstrated** (`controller_restart-r04`:
> 2,153 of 6,720 accepted after the deadline, the 67 late among them, none
> permanently lost). The `ditto-things` incident is bounded to these sessions,
> without a stability statement. No performance, capacity, stability or native
> property; no claim admitted; no G4 pilot, `exp-v1` or campaign. The
> limitations of section 7 of this proposal are part of what is accepted.

The row also needs: outcome `Accepted`; **decided at** the recording date;
authority Student (Rui Duarte); a durable decision record like
[`decisions/2026-09-21-g2-closure.md`](../decisions/2026-09-21-g2-closure.md);
the present row kept under "Superseded row states".

## 9. Points for the student before deciding

1. Has the evidence check run green on the final head (C3)?
2. Do five openings and three tool commits satisfy "in order on one unchanged
   image and container set" (section 4.3)?
3. T6 passes under the criterion decided on 2026-10-05, which stays
   decided; timely delivery at 11.2 msg/s is not shown and stays a sizing
   finding (section 7.2). Does section 8 state this as intended?
4. Is either "Open" finding (`risks.md` lines 230–231) a P0 defect? Should
   the rows change?
5. Does the bounded `ditto-things` wording suffice, the re-measurement
   outstanding?
6. Do limitation 7's observations need a dated note? Separately:
   `backlog.md` line 255; `compose.yaml` line 26 ("3x ditto 512M"); the S4
   supplement and authorisation notes and the sealed supplement package
   date register line 4937 2026-10-07, while the entry is headed
   2026-10-05 21:56 WEST: corrected in
   [`records/2026-10-07_register-date-correction.md`](../../evidence/g3-battery-2026-10/records/2026-10-07_register-date-correction.md),
   the sealed bytes kept.
7. Does section 8 say what the student intends?

## 10. Until the student records it, G3 is not decided

**G3 stays `Not decided`.** Only the gate-decision log holds a gate outcome;
only the student's dated decision, with an authority and a durable record,
changes it. Evidence, checks, a sealed capsule or this proposal do not.
