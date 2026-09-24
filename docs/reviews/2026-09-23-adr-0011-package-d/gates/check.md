# Package D — check of the four gate answers and their fold into ADR 0011 and the decision request

- **Date:** 2026-09-21.
- **Checked:** `gates/item1_broker_limits.md` [I1], `gates/item2_r02_guest_evidence.md` [I2], `gates/item3_ack_order.md` [I3], `gates/item4_drained.md` [I4]; their fold into `adr-0011-controller-restart-recovery.md` [ADR] and `decision_request.md` [DR]; the pre-fold versions in `gates/prefold/`.
- **Purpose:** to refute. Every statement below names its source: a file and line, or a document and section. Where I could not settle a point, I say so.
- **What I did not do:** I modified no file other than this one. I started no guest. I ran no git command that changes state. I consulted no documentation beyond the permitted set.
  - One slip: I briefly wrote a scratch diff to `scratchpad/pkgD_adr_fold.diff`, outside `gates/`, and deleted it within the same minute. Nothing else was written.

## 0. Verdict

- **No gate answer refutes the recommendation's direction.**
  - Option 5 is still admissible, under conditions.
  - Option 4 is still the next best.
  - The sources the four notes cite hold wherever I re-read them (section 1).
- **The fold is faithful in substance.** The diff against `gates/prefold/` shows no change outside what the four notes support.
- **The recommendation is not yet safe to put in front of the student as written.** Two findings are high and eight are medium:
  1. **Condition C3 is too weak.** It passes a broker measurement that is only "not refuted", which includes an inconclusive run. The ADR calls the result "a guarantee" on the same weak test.
  2. **No document assesses what the global broker settings do to the pilot plan's load sweep and soak.** The candidate carries those settings.
  3. **The decision request overstates its own completeness and some evidence statuses.** It says "nothing is left" to answer, and it says "never processed … proved". It also repeats one claim that a permitted source contradicts: that the broker drops "silently".
- **The student cannot decide from `decision_request.md` alone** (section 4).

## 1. What I re-checked and found to hold

| Checked | Result | Source |
|---|---|---|
| Code anchors cited by the fold, at `35fe8bb`, sampled: `mqtt.py:29-30, :35, :73-76, :103, :149-152, :180, :187-199, :203-217`; `service.py:39, :81-87, :150-152, :161-169, :182-201, :212-229, :287-343, :390-415`; `events.py:103-119`; `ditto.py:228-255, :323-333`; `metrics.py:50-55`; `app.py:159-164`; `mosquitto.conf:33-35, :47-56`; `acl:3-4, :9-14`; `compose.yaml:87, :256, :290`; `CONTRACTS.md:170-175, :186-195, :228-233, :277-287, :369-372`; `analyze.py:2715-2718`; runbook `:994-1004, :1116-1138` | all hold | read with `git show 35fe8bb:<path>` through `scratchpad/devwt`; `origin/dev` = `35fe8bb` there |
| **WSL clone state.** The brief says `/home/ruisth/egw-exec/repo` is "now updated to the merged dev". | **It is not.** HEAD is detached at `b7e0c83`, and `35fe8bb` is not a valid object in it. The notes read `35fe8bb` through `devwt`, as each of them says. | `git log`, `git cat-file` in the WSL clone, 2026-09-21 |
| paho-mqtt 2.1.0 behaviour. File sha256 `5a3f0f73…` matches [I1 §1]. | holds | `client.py` lines listed below |

paho-mqtt 2.1.0 lines checked (`client.py`):

- `:742`, `:751` — `manual_ack` default and storage;
- `:784-785` — `clean_session` default;
- `:4147-4152` — automatic PUBACK;
- `:4165-4176` — `ack()` checks nothing;
- `:4180-4182` — "the caller MUST manually acknowledge every message";
- `:3776`, `:3163` — the outgoing packet deque is FIFO;
- `:1568`, `:1577` — socket close before the clear on reconnect;
- `:2859-2872` — `on_socket_close` is called under `_in_callback_mutex` only;
- `:2906-2913` — `ack()`'s path takes `_callback_mutex` only.

That last pair means A4's controller lock cannot deadlock against paho's locks. I checked this because A4 takes one lock on both threads.

| Checked | Result | Source |
|---|---|---|
| Paho documentation: whether it states thread safety for `ack()` | none stated; I3 §4.3 is right | eclipse.dev/paho/files/paho.mqtt.python/html/client.html (`Client`, `ack`, `manual_ack_set`) |
| MQTT 3.1.1 conformance statements cited | wording as cited | OASIS MQTT 3.1.1, §4.3.2 with the note to Figure 4.2, §4.4 `[MQTT-4.4.0-1]`, §4.5 `[MQTT-4.5.0-2]`, §4.6 `[MQTT-4.6.0-1…6]` and its non-normative comment, §3.1.2.4 `[MQTT-3.1.2-4…6]`, §3.14.4; copy `gates/sources/oasis_mqtt-v3.1.1-os.txt:3640-3835` |
| `mosquitto.conf(5)` entries as released with 2.0.22 | hold: defaults 20 and 1000, "applies globally", `persistent_client_expiration` in `h d w m y`, "silently dropped" for `max_queued_bytes` | `scratchpad/mosq-src/mosquitto.conf.5.xml` (sha256 `5d53da59…` as [I1 §1] states): `:308-338`, `:557-584`, `:657-705`, `:793-816`, `:843-871`, `:1033-1044` |
| ChangeLog entries cited | hold | `gates/sources/ChangeLog.txt` (sha256 `a29df2b6…`): `:143` (2.1.0), `:346` (2.0.22), `:487-489` (2.0.17), `:640` (2.0.13), `:991-992` (2.0.4), `:2000-2009` (1.5), `:2307-2308` (1.4.9), `:2815-2816` (1.2) |
| I1 arithmetic: 1,020; 2,573 and 3,979 short; 25,310 B ≈ 24.7 KiB, 34.4 KiB and 20.6 KiB; 544.6 s; 884.6 to 1,154.6 s | holds | [I1 §4, §5, §7] |
| Gate scripts re-run | outputs byte-identical to the recorded ones: `item1_payload_and_broker_memory.py`, `item2_r02_guest_evidence.py`, `item3_probe.py` (stdout), `item4_callsites.sh` | `diff` against `gates/out/*` and `gates/item4_callsites.out.txt`, all empty |
| r02 figures: 1,810 / 5–7 / 319–321; forced stop; exit 137; none of the 2,136 with an outcome; 765 and 422 late, none twice | hold as figures | `gates/out/item2_r02_guest_evidence.out.txt:6-16, :32-36, :44, :50, :126-136, :148` |
| **Integration.** Word diff of `gates/prefold/adr-…md` against the ADR, and of the pre-fold decision request against the current one. | Every changed passage traces to I1–I4. Nothing unrelated changed. No threshold, confirmation window, deadline, offered load, `DRAIN_*` value or ingest rule changed. The throughput decision stays separate and left to the student. Each guest session is labelled "not a G3 run". | `git diff --no-index --word-diff` (read-only) |

## 2. Findings

### High

**H1 — C3 and the "guarantee" rest on "not refuted", which an inconclusive run satisfies.**

- **Where:**
  - ADR `:17-23`: it "becomes a guarantee" once the broker measurement "has not refuted it" and the proof "has not refuted it";
  - C3, ADR `:836-839`;
  - ADR closing, `:1789-1793`;
  - DR `:30` (C3: "run without refuting the option") and step 2, `:63`.
- **Problem:**
  - The broker measurement has an explicit inconclusive class (ADR `:1152`; [I1 §7]). The proof has one too (ADR `:1244-1246`).
  - An inconclusive run "has run and has not refuted". So C3 is met while "within 128 MiB" is still unknown, which contradicts C3's own sentence at `:838-839`.
  - One outcome has no verdict at all; see M4.
  - "Guarantee" also contradicts the proof's own limit: "One run supports the property for that run; it does not prove it in general" (ADR `:1248-1249`).
  - The DR states the proof rule correctly: "supports … only if all six … hold" (`:67`). It does not state the broker measurement's rule, and says nothing about what follows an inconclusive run.
- **Fix:**
  - C3 should read: "the broker measurement has run and **supported** the option (all of S1–S5 of [I1 §7])". An inconclusive run is repeated or re-decided, never taken as passing.
  - The status paragraph and the closing should read "supported", not "not refuted".
  - Replace "guarantee" with "the behaviour this record proposes, supported by one broker measurement and one proof run".

**H2 — What the global broker settings do to the pilot plan's load sweep and soak is not assessed anywhere.**

- **Where:** ADR "The other families" (`:571-586`), P5 (`:976-983`), Open item 3 (`:1647-1652`). DR option 5 row (`:16`) and "Still unknown" (`:55`). No document mentions `load_sweep`, `soak` or the 95-run plan (grep of the ADR, the DR and I1–I4).
- **Problem:** the broker settings are global ([I1 §2]; `mosquitto.conf(5)` 2.0.22 `:582`, `:685`), and the frozen candidate carries them. The plan `/home/ruisth/egw-tcg/pilot/campaign_plan.json` holds:
  - 40 `load_sweep` runs of 300 s: 10 each at 10, 50, 100 and 250 msg/s;
  - one `soak` of 86,400 s at 11.2 msg/s.

  Arithmetic on the offered counts, with the measurement's candidate values W = 4,999 and Q = 1,000 ([I1 §7]), shows three effects:
  - **At 50 msg/s the window fills** unless the controller serves at least (15,000 − 4,999) / 300 = 33.3 msg/s on average. For 100 and 250 msg/s the figures are 83.3 and 233.3 msg/s.
    - The highest served rate observed in any 30 s block was 11.60 msg/s (ADR `:645-647`, citing `backlog_diagnosis.md` §7.1).
    - Once the window fills, P5 no longer holds: the wait moves to the broker and out of `latency_ms`. The ADR rejects exactly this effect as an alternative (`:1569-1571`).
  - **Overflow moves from the controller to the broker.** Beyond W + Q = 5,999 held, the broker drops. That drop is counted only broker-wide, and only if C2 is granted.
    - Today the controller holds 10,000 (`service.py:39`), and its overflow is counted per process in `dropped` (`service.py:161-169`).
    - At 50 msg/s the drop threshold moves from an average service of 16.7 msg/s (controller) to 30.0 msg/s (broker).
  - **The soak fills the window** unless the controller serves at least 11.14 msg/s on average over 24 h. Every observed phase of `nominal-r01` was below 11.2 msg/s (ADR `:400-405`).

  These are thresholds computed from offered counts. They are not capacity figures, and whether any load-sweep run fills the window is expected, not established. The DR presents consequences only "for the G3 families".
- **Fix:**
  - Add a row to the DR, and a paragraph to ADR section 3: under option 5, the plan's `load_sweep` runs at 50 msg/s or more, and the `soak`, are expected to fill the window. Their `latency_ms` then excludes the broker wait (P5), and overflow becomes a broker-side drop.
  - Leave it to the student, or to the G4 protocol decision (T4), whether W, Q or the load-sweep protocol must answer this before the freeze. This belongs beside open item 3.

### Medium

**M1 — "Nothing is left that must be answered before you decide" overstates item 1.**

- **Where:** DR `:8` ("the four gate items are answered") and `:28`.
- **Problem:**
  - The ADR's own open item 1 says "answered in part … It can still rule option 5 out" (`:1608-1615`).
  - The pre-fold DR listed this as the item that "can rule option 5 out" (`gates/prefold/decision_request.md`, item 1).
  - The unanswered part has become condition C3. That is a legitimate structure, but the DR's headline hides it.
- **Fix:** say plainly that item 1 is answered in part. Whether the pinned broker holds W within 128 MiB is still open, and it can refute option 5. The decision is therefore conditional on a measurement not yet run, which the student may run before deciding (DR `:51`).

**M2 — "Never processed … proved" is stronger than the evidence.**

- **Where:** DR `:12` ("That none of them was ever processed is proved by the guest's complete event log"); ADR `:268`, `:534`, `:686-687`, `:865-866`; [I2 §1.5, §6] (table, "Never processed: PROVED").
- **Problem:**
  - The complete guest log proves that none of the 2,136 has an outcome **line** (`item2…out.txt:12`).
  - The block includes r02's in-flight identity, `smart_clothing` seq 1422 (`sent_events.jsonl:1595`). Whether Ditto applied its `PATCH` "I could not establish" (ADR `:351-359`; [I2 §7]).
  - So "never processed" is proved only for "never obtained an outcome line". Up to one identity may have reached the twin.
- **Fix:** "none ever obtained an outcome line (PROVED); whether the one in flight at the kill reached its twin is not established".

**M3 — The DR drops the status labels on the restart classes.**

- **Where:** DR `:12` and `:26` ("r02 shows that both classes are real … about 320 published while no subscription existed"); ADR `:796-800`.
- **Problem:**
  - The 319–321 figure, and the label "for want of a session", are CONSISTENT-WITH. They rest on recovered bytes whose admission is still the student's call (ADR `:268-278`; [I2 §6, §9]).
  - "Received by the old process" for the 1,809 is arithmetic PROVED with a CONSISTENT-WITH reading (ADR `:175-178`).
  - The rule for this package is that restart classes stay assumption-dependent unless the guest evidence proves them. It proves the absence of outcomes, not the partition.
  - The DR says the recommendation does not depend on the recovered bytes (`:34`). Its first reason nevertheless leans on the ~320.
- **Fix:**
  - Attach the labels: "about 320 (CONSISTENT-WITH, on recovered bytes; 151–327 without them)".
  - Replace "shows … real" with "is consistent with both classes being real".

**M4 — The broker measurement has an outcome with no verdict: a per-device order break.**

- **Where:** ADR `:1149` (supports: "redelivered in per-device order") against `:1151` ("recorded, not refuting by itself: … a per-device order break"); [I1 §7] S5 against "Recorded, not refuting by themselves".
- **Problem:**
  - An order break fails the support rule. Yet it is neither a refutation nor inconclusive.
  - It is the one broker behaviour the 2.0.22 manual itself leaves open: `max_inflight_messages` "If set to 1, this will guarantee in-order delivery of messages" (`mosquitto.conf.5.xml` `:578-580`). No such guarantee is stated for W = 4,999.
  - P4, N5 and the proof's R3 depend on that order (ADR `:1013-1020`, `:1236-1238`).
- **Fix:** classify it, and let the student see how. Either treat a per-device order break of first copies in P7 as refuting option 5 as configured, or state in advance that it sends the option back for re-decision. Carry the classification into C3.

**M5 — The broker "drops silently", and "whether it logs a drop" is still called unknown. A permitted source contradicts both.**

- **Where:** DR `:87` ("beyond them the broker drops silently"); ADR `:737-738`; [I1 §0.2-3, §3 (":194-198"), §8, §9]; [I4 §4 item 4, §10]; ADR N4 `:1009-1010`; DR "Still unknown" `:51`.
- **Problem:**
  - The manual's "silently dropped" belongs to `max_queued_bytes` (`mosquitto.conf.5.xml` `:659-661`). Under the defaults that limit is unlimited (`:663`); the drop comes from `max_queued_messages`, whose entry says nothing of silence.
  - The Mosquitto ChangeLog, 1.3, reads: "Log when outgoing messages for a client begin to drop off the end of the queue" (`gates/sources/ChangeLog.txt:2679-2680`). [I2 §5] cites that very line.
  - [I1 §3] says a drop log line "is not stated in [M5], [M8] or [CL]". That is wrong for [CL].
  - The fold did not reconcile I1/I4 with I2.
- **Fix:**
  - Drop "silently" except for the byte limit.
  - Restate the unknown: the change log records since 1.3 that the broker logs when a client's queue begins to drop. Whether 2.0.22 still does, at which log type, and whether the deployed log types (`mosquitto.conf:48-53`) include it, is not established. The measurement's broker log answers it.

**M6 — N1 is not updated for A1: N1-shaped identities no longer need a death.**

- **Where:** ADR N1 `:987-991` ("At most one such identity per death"); Consequences `:1481-1482`; DR `:16` ("an N1 case gives one `delta` `MISMATCH`").
- **Problem:**
  - A1's fourth exception is "an exception after the Ditto 2xx", and it includes a failed event write after the `PATCH`. It leaves the twin advanced with no line.
  - A3 then ends the connection. The redelivery is `duplicate`, and the identity is counted `lost` ([I3 §5 L3, L11]; I3 calls it "the N1 shape").
  - So N1 cases can arise once per connection ended by A3, not only once per death.
  - The proof's S4 and S5 tolerate only "the single identity in progress at the kill" (ADR `:1222-1227`). An A3 event during the proof therefore reads as R3.
- **Fix:** N1: "at most one identity per death or per connection ended under A3 after a `PATCH`". Say the same in the DR's option 5 row.

**M7 — The proof's S2 and R1 count a `failed` line as recovery, and A1 widens `failed`.**

- **Where:** ADR S2 `:1219-1220`, R1 `:1233-1234`; the widened meaning of `failed` `:1369-1372`; DR `:52` ("whether option 5 recovers both classes").
- **Problem:**
  - S2 needs "at least one outcome line". Under A1, any exception before the `PATCH`, and every non-`DittoError` Ditto failure, ends in a `failed` line followed by a PUBACK. The broker then releases the delivery for good.
  - A proof run in which redelivered identities end `failed` would support the option, although nothing was delivered.
  - "Recovers" in the DR implies `accepted`.
- **Fix:** report `failed` and `rejected` identities separately in the proof. Either add "every valid identity has an `accepted` line, or is the named N1 case" to S2, or say in the DR that "recovered" means "obtained an outcome line of any kind".

**M8 — The guest measurements are not stated in the DR with their question and refuting result, and two are not bounded.**

- **Where:** DR `:42` (T3), `:51-53`, `:63`, `:67`.
- **Problem:**
  - The DR carries each run's question, except T3's.
  - It carries no refuting result for the broker measurement, the proof or the extension. The proof has a support rule only.
  - The broker measurement's "15–19 min" excludes stopping and restarting the stack, whose Ditto start under TCG is unverified (ADR `:1153`; [I1 §7]). That part has no bound.
  - The extension's "2.5–3 min" is a planning figure with no ceiling. It contains a `drained` call, which can run to `DRAIN_LIMIT_S` = 900 s (runbook `:654`; [I4 §9]).
  - T3's question and refutation exist only in `backlog_diagnosis.md` §11.1 and §11.4 (`:317-357`).
  - That section still says "Package D proposes two guest runs in total" (`:368`). There are now four: T3, the broker measurement, the proof and the optional extension.
- **Fix:** add one line per guest session to the DR, giving its question, the result that refutes, the inconclusive cases and a ceiling. Correct §11.5 of the diagnosis, or note in the DR that it is stale on this point.

### Low

| # | Where | Problem | Fix |
|---|---|---|---|
| L1 | ADR `:1747` ("The documentation they rely on is copied, with its hashes, in `gates/sources/`"); [I1 §1] tags [M5], [M8] | [M5] (2.0.22 `mosquitto.conf.5.xml`) sits in `scratchpad/mosq-src/`, outside `gates/sources/`. [M8] (2.0.22 `mosquitto.8.xml`, sha256 `7ff3b8f2…`) is kept nowhere I could find. Every `[M8] :n` cite is therefore unreproducible from the package. Both were fetched from the project's source tag (raw.githubusercontent.com), not from mosquitto.org. The `$SYS` entries used also appear on mosquitto.org's 2.1.x `mosquitto(8)` (`gates/sources/man_mosquitto-8.txt:241-245, :305-312, :342-348`). | Copy both into `gates/sources/` with their hashes, or cite mosquitto.org entries with the version caveat. |
| L2 | DR `:30`, `:34`; ADR C2 `:825-835` | C2 is called a condition, yet the student may decline it. [I4 §5.5] calls it "a separate decision". If it is declined, N4's "with C2 the run record shows that a drop happened" (`:1010-1012`) lapses. | Call it a choice attached to option 5, and state what is lost if it is declined: six conditions and one choice. |
| L3 | ADR `:272-274`, 2(e) `:471-473`; [I2 §5] against [I4 §4 item 4] (`:153`) | The broker log's `c1` field is read as the clean-session flag. I2 and the ADR label that reading CONSISTENT-WITH; I4 labels the same reading ASSUMED. The fold did not reconcile them. | Use one label. CONSISTENT-WITH is defensible: ChangeLog 1.2 `:2815-2816`, and `k60` matches `mqtt.py:31`. |
| L4 | `gates/item2_r02_guest_evidence.md:9` (the name of an assistant), `:18` (a workstation path); `gates/scripts/item3_anchors.sh:7` (a workstation path) | These files are to be committed with the review record (ADR `:1753-1760`). The project forbids naming AI tools. | Replace them with neutral wording and relative or variable paths before committing. |
| L5 | DR `:8`; `backlog_diagnosis.md:366` | The pause is recorded at `3549d46` on `docs/g3-pause-answer`. I verified that `3549d46` is not an ancestor of `35fe8bb`. The ADR says so (`:1517-1520`); the DR states the pause without that qualification. | Add "(recorded on a branch, not yet on `dev`)". |
| L6 | ADR N3 `:1001-1005` | Under a persistent session, the broker's store is written at close and every `autosave_interval` (`mosquitto.conf.5.xml:795-806`; `mosquitto.conf:35`). After a broker crash or a guest power loss, a snapshot up to 60 s old may bring back deliveries already acknowledged, as `duplicate` lines in a later run. This is an inference from the documented behaviour, not an observation; N3 speaks only of loss. | State it as not established, beside N3. |
| L7 | C6, ADR `:851-853`; runbook `:1123` (`docker compose … restart controller`, no `-t`) | C6 assumes the engine applies `stop_grace_period` to `compose restart`. No permitted source establishes that, and the proof uses SIGKILL, so it does not test C6. I could not establish it. | Say so under C6. Test 6 in the battery is the first place it is exercised. |
| L8 | DR `:28`; ADR `:1054` ("The acknowledgement order is settled") | The order "comes by construction" is reasoning about code not yet written. "Drained can be made truthful" omits the residual ASSUMED of [I4 §5.5]; the DR states it only elsewhere (`:53`). | Say "follows by construction, to be pinned by the regression tests", and "truthful except for the residual assumption stated in C5". |

## 3. Did the fold carry each answer faithfully?

- **Item 1.** Carried into C1–C3, the options, "The in-flight window W", the broker measurement and open item 1.
  - Faithfully, except that the fold inherited I1's two errors: "silently", and "a drop log not stated in [CL]" (M5).
  - The fold also inherited I1's verdict gap for an order break (M4).
- **Item 2.** Carried into §1.1–1.6, 2(e), 2(f) and the code identity. The recovered-bytes rule is stated at `:87-89` and `:274-278`.
  - It inherited I2's "never processed: PROVED" wording (M2).
  - The DR then dropped the labels (M3).
- **Item 3.** A1–A6, code items 1–13 and the tests are carried closely.
  - Missed: the consequence of L3 and A1's fourth exception for N1, S4 and S5 (M6).
  - Missed: the effect of the wider `failed` on the proof's S2 (M7).
- **Item 4.** C5, the three fields, D1 and D2, the families, the optional extension, and the blind spot in `gate_health.sh`, `accounted` and `delta` are carried.
  - C2 was turned from I4's "separate decision" into a condition that may be declined (L2).
- **Changed nothing else.** The word diff against `gates/prefold/` shows no change without a source in I1–I4. The pre-existing "not refuted" and "guarantee" wording was extended to the broker measurement (H1). That is a carried weakness, not a new one.

## 4. The answers

**Can the student decide from `decision_request.md` alone? No.**

- The DR gives a readable shape: two separate decisions, five options with costs, a conditional recommendation, a named next best, the choices that go with option 5, the unknowns, and the order of work.
- But to decide safely he needs four things it does not give him:
  - that condition C3 (and the ADR's "guarantee") would be satisfied by an inconclusive broker measurement, and that one measurement outcome has no verdict at all (H1, M4);
  - that option 5's global broker settings are expected to change `latency_ms` and move overflow to the broker in the pilot plan's load sweep and soak, which nothing assesses (H2);
  - each guest session's refuting result and a ceiling (M8);
  - the evidence statuses the DR drops: "never processed", and the ~320 class (M2, M3).

**Is the recommendation now safe to put in front of him? Not yet.**

- Its direction survives every check I could make: option 5 under conditions, option 4 next best, option 3 with option 2 in reserve.
- H1, H2 and M1–M8 are all corrections of wording, conditions or scope. None needs a guest session or a code change.
- Once they are made, the recommendation can go to him with the broker measurement as the first thing he may choose to run.
