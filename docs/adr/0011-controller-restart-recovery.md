# 0011 — Controller restart recovery

**Status:** Accepted by the student for bounded implementation (2026-09-24) —
proposed on 2026-09-21, condition C3 met on 2026-09-23, the decision recorded
on 2026-09-24 ("The decision recorded on 2026-09-24", under Decision); the
finite proof and the qualifying battery are pending. It records the
student's decision to implement option 5, acknowledging each message
only after its outcome is recorded, on a persistent MQTT session, **under the
conditions that the answers to its four gate items set** (2026-09-21; six
conditions and one choice, "The conditions option 5 carries", in the
Decision). Those answers admit option 5 only with conditions and rule it out
on today's broker configuration; none rules it out as such. **On 2026-09-23
the broker measurement ran on the guest and supported the option** — every
one of S1–S5 held in
`20260923T195448Z_broker-hold-measurement-c3_attempt04` (`output_test`,
execution commit `8e68017`; LOG `#C040`) — so C3 is met for that run, and
the open part of gate item 1 is closed for the pinned broker as this guest
holds it: it honours W = 4,999, held 5,999 within 128 MiB (peak 12,750,848
bytes), counted its queue above the in-flight window (store W + Q, dropped
B − Q), logged its transition into dropping at the deployed log types (one
`notice` line per client per connection, N4), and redelivered
everything held in per-device order on the resumed session. That is the
broker-side premise for one run; it is not the controller's recovery, not
timely delivery, and no gate or claim. It replaces the unnumbered draft of
2026-09-20 (`adr-recovery-draft.md`), which is not to be cited; the corrections
to that draft, and those of the second review round, are recorded outside this
record, in its review annex (`adr-0011-review-annex.md`), which does not enter
`docs/adr/`. Nothing here accepts a gate, admits a claim, validates a result,
changes a maturity level, or changes any threshold, confirmation window,
deadline, offered load, ingest rule or evidence class.

**Nothing in this record is a guarantee.** The code at the merged `dev`
implements none of it. It becomes the behaviour this record proposes,
supported by one broker measurement and one proof run, only after four things
have happened, in this order (the first two have: the decision on 2026-09-24,
the measurement on 2026-09-23): the student records the decision; the broker
measurement below has run on the pinned broker and **supported** the option,
every condition of its support row holding (S1–S5 of [I1 §7]); the change, its
contract text and its regression tests are merged; and the finite proof below
has run and **supported** the option, all six of its S1–S6 holding. A run that
is inconclusive has not refuted the option but does not support it either, and
is not passing (condition C3; "The finite proof"). Even then it covers only
what those two runs cover: one run supports the property for that run and
proves nothing in general.

**Numbering.** `docs/adr/` at the merged `dev` holds 0001–0008 and 0010, and no
ADR file numbered 0009 or 0011 has been added on any ref of the repository
[C]. 0009 is kept for the MongoDB 8 evaluation: it is referenced as
`docs/adr/0009-mongodb-8-evaluation.md` in
`docs/evidence/integrated-qemu/2026-09-18-mongodb7-isolated/README.md:72` and
in `docs/reviews/2026-09-17-egw-image-audit.md:615`, and ADR 0010 records that
0009 "is kept for other open work" (`docs/adr/0010-controller-progress-counters.md:10`).
Nothing outside `docs/evidence/` refers to 0011 [C]. Numbers are never reused
(`docs/adr/README.md`), so this record takes 0011.

**Code identity.** Every `file:line` below is at the merged `dev` head
`35fe8bb` (the merge of pull request #41, 2026-09-21) [C]. The directory
`src/egw_controller/`, `src/deployment/compose.yaml`, `src/deployment/mosquitto/`,
`src/Dockerfile` and `src/pyproject.toml` are identical at `35fe8bb`, at
`8e88670` (the harness commit recorded in both restart runs' manifests) and at
`fe954a9` (the nominal run's): `git diff --stat` is empty for all three [C].
`src/CONTRACTS.md` differs from `8e88670` by one preamble line. The
anchors in `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md` and
`PROGRESS.md` hold at `35fe8bb` and not at `b7e0c83`, the G2 execution commit
held by the WSL clone, where those files have other line numbers; the one
`PROGRESS.md` anchor on the pause (`:180`) is at `3549d46`, as stated where it
is used [C]. No run manifest records the controller image's id or source
commit, and the image installs its Python dependencies unpinned
(`src/Dockerfile:48`, `RUN pip install .`; `src/pyproject.toml:11`,
`paho-mqtt>=2.1,<3`). For the container that ran r02 (`9b2098915ade…`), two
records outside the run join on the container id: image
`sha256:2e30d8fcf921…`, source commit `0dfa531`, `paho-mqtt==2.1.0` and
`uvicorn==0.53.0`, and `git diff --stat 0dfa531 35fe8bb` is empty for
`src/egw_controller`, `src/Dockerfile` and `src/pyproject.toml` [I2 §7].
**CONSISTENT-WITH**, not PROVED: the join rests on a container keeping the image
it was created from. Item 2 did not establish it for the other runs, where
the image's source stays **ASSUMED**, and a rebuilt image may install another
paho version. Third-party
behaviour cited below (paho-mqtt, uvicorn) was read in the analysis environment
`~/egw-exec/venv` (paho-mqtt 2.1.0, uvicorn 0.52.1) [C]; the paho version
matches the one recorded for r02's container, the uvicorn version does not
(0.53.0 there) [I2 §7].

**Platform.** Every duration, rate and count below comes from an ARM64 guest
emulated under QEMU/TCG on the x86-64 workstation. None is native-hardware
performance, none is a capacity, and no maximum throughput is inferred from any
of them: the one run with a valid resource record at 11.2 msg/s failed its
delivery criterion.

**Status of each claim.** **PROVED** — an artefact line states it, or
arithmetic on artefact lines gives it. **CONSISTENT-WITH** — the artefacts
point that way and do not exclude an alternative. **ASSUMED** — it rests on
source code, a library or engine default, or protocol semantics that no
preserved artefact records. Where none of these applies, the text says *I
could not establish*.

**Sources.** `[F:X]` is block X of `pkgD/v2/scripts/adr0011_figures.py`
(output `pkgD/v2/out/adr0011_figures.out.txt`); `[C]` is
`pkgD/v2/scripts/adr0011_code_anchors.sh` (output
`pkgD/v2/out/adr0011_code_anchors.out.txt`). Both are read-only; their inputs
and commands are in the last section. `[I1 §n]`, `[I2 §n]`, `[I3 §n]` and
`[I4 §n]` are section *n* of the four gate notes that answer this record's
gate items, in `pkgD/v2/gates/`: `item1_broker_limits.md` (the broker's limits),
`item2_r02_guest_evidence.md` (r02's guest-side evidence), `item3_ack_order.md`
(the acknowledgement order) and `item4_drained.md` (the `drained`
precondition). Each carries its own sources, scripts and outputs, and each
labels documentation it relies on by document and section. Three of those
labels recur here. `[M5]` is `mosquitto.conf(5)` as released with 2.0.22, kept
as `gates/sources/mosquitto.conf.5-2.0.22.xml` (sha256 `5d53da59…`, listed in
`gates/sources/SHA256SUMS.txt`; a byte copy of the file [I1 §1] read, taken
from the project's 2.0.22 source tag, not from mosquitto.org); its line numbers
are that file's. `[M8]` is `mosquitto(8)` as released with 2.0.22 (sha256
`7ff3b8f2…` [I1 §1]); no copy of it is kept in the package, so the gate notes'
`[M8] :n` line numbers cannot be reproduced from it. Where this record relies
on a `mosquitto(8)` statement it cites the mosquitto.org page instead,
`gates/sources/man_mosquitto-8.txt`, which documents 2.1.x, not 2.0.22; a
statement that page does not carry would be marked as read from the 2.0.22
source tag but not kept, and so not reproducible from the package (none of
this record's statements is in that case). `[CL]` is the Mosquitto change log,
`gates/sources/ChangeLog.txt` (sha256 `a29df2b6…`). `[G:X]` is block X
of `gates/out/item2_r02_guest_evidence.out.txt`. Item 2 adds one label: a fact
resting only on log bytes recovered from free blocks of the guest's data disk
is at most CONSISTENT-WITH [I2 §3]. So as not to collide with the proof's
S1–S6 and R1–R4, item 3's acknowledgement rule R1–R6 is written **A1–A6**
here (A3(a) and A3(b) for its two ways of ending a connection), and item 4's
two drain states S1 and S2 are written **D1** (the controller answers HTTP but
its session is not connected or not resumed) and **D2** (it holds deliveries it
will not acknowledge on the current connection) [I4 §3]. Item 1's own support
conditions for the broker measurement are cited only as "S1–S5 of [I1 §7]",
always with that tag, so that they are not read as the proof's S1–S6. The package D analyses
(`controller_today.md`, `restart_evidence.md`) and the round-one verification
reports (`verification_figures.md`, `verification_constraints.md`) are cited by
name for reasoning; every figure used here is re-derived by this record's own
scripts or by the gate notes' scripts. Every file named in this paragraph
lives, today, in the package D working directory; when this record enters the
repository they are committed with it as one review record, and every `[F:…]`,
`[C]`, `[I…]`, `[G:…]` and file reference resolves there (see "Sources and
reproduction").

---

## Context

### 1. The problem, from the evidence

#### 1.1 `controller_restart-r02` (2026-09-19; `invalid`, unsealed)

The restart command was issued at 00:18:15.344Z, at the planned t+300 s of a
600 s window at 11.2 msg/s, and returned 0 (`manifest.json`, `restart`)
[F:R02.0]. The event log was fetched once, starting 00:24:18.026Z
(`manifest.json`, `events_fetch`), 2.534 s after the confirmation deadline
mapped to harness wall through the marker [F:R02.1]; "with an outcome" below
means present in that copy, whether confirmed by the deadline or after it.

```text
published identities (sent_events.jsonl)                           6,720   PROVED
with an outcome in the fetched events.jsonl (all 'accepted')       3,819   PROVED
  confirmed by the deadline                                        3,795   PROVED
  confirmed after the deadline, present at the fetch                  24   PROVED
without an outcome in that copy                                    2,901   PROVED
  contiguous block, sent_events.jsonl:1595-3730                    2,136   PROVED
  contiguous block, sent_events.jsonl:5956-6720 (end of run)         765   PROVED
```

[F:R02.1, R02.2]. On time and late compare each acknowledgement stamp with
the deadline, both on the controller's monotonic clock.

The process that was restarted, accounted for from its last answered poll
(`controller_metrics.csv:307`, 00:18:19.443Z) [F:R02.3, R02.4]:

```text
published by that poll                                             3,404   PROVED
  accepted since the window opened (1,872 - 336)                   1,536   PROVED
  queue_depth in that poll                                         1,867   PROVED
  residual: published - accepted - queued                              1   PROVED
identities with an outcome ahead of the block                      1,594   PROVED
  beyond the 1,536 counted at the poll (1,594 - 1,536)                58   PROVED as arithmetic
still queued when the process stopped, at least (1,867 - 58)       1,809   arithmetic PROVED; reading ASSUMED
  + the residual identity, assigned to the process by elimination  1,810   ASSUMED for that one identity
```

"At least", because with one FIFO consumer and `dropped` at 0 the 58 came from
the head of the queue — unless the residual was the message in progress at the
poll and was itself one of the 58, in which case 1,810 were still queued.

The arithmetic is on artefact lines. Reading it as "at most 58 left the queue
after the poll, so at least 1,809 were still queued when the process stopped"
rests on the source, not on an artefact line, and is **ASSUMED**: an outcome
line is written before its counter moves (`service.py:414-415`), and a message
taken from the queue that ends on the exception path (`service.py:191-197`)
leaves no line and raises only `processing_errors`, which the sampler does not
record. What holds without the source is G1 of section 1.3: 1,810 identities
published by the last answered poll have no outcome in the fetched copy.

The 1,536 also equals the number of `events.jsonl` records acknowledged before
the poll once their controller-clock stamps are converted through the
controller marker [F:R02.4]; that comparison crosses clock domains at
sub-second precision and is CONSISTENT-WITH, not PROVED. The residual is
assigned by elimination because `received` and `in_progress` are not among the
columns the sampler writes (`src/egw_experiments/controller_metrics.py:53-64`)
[C]. That "still queued when the process stopped" means "discarded" was
**ASSUMED** here: it follows from the queue being process memory (section 2b),
not from an artefact line.

**What the guest's own records add** [I2 §3, §6]. The guest keeps a complete
copy of r02's `events.jsonl`, of which the harness copy is an exact prefix, and
its persistent journal of that boot; both were read from the guest's disk
images without starting the guest. In the complete guest copy **none of the
2,136 identities of the internal block ever obtained an outcome**, from either
process, and no identity has two `accepted` lines — **PROVED** [G:R02.E2–E3].
The old process was forced to stop while still writing outcomes (section 1.5).
So "still in the old process's queue at the kill" moves from ASSUMED to
**CONSISTENT-WITH**; the one-by-one reading of the 1,809 still rests on the
counter source reading (`service.py:414-415`) [I2 §6].

#### 1.2 `controller_restart-r01` (2026-09-18; `invalid`, unsealed) — corrected

The draft of 2026-09-20 gave r01 "1,405 identities with no outcome". **That was
wrong.** 1,405 is r01's analogue of r02's 1,810 (still queued plus the
residual). The event log was fetched once, starting 22:01:30.951Z, 8.305 s
after the confirmation deadline mapped to harness wall [F:R01.0, R01.1]:

```text
published identities                                                6,720   PROVED
with an outcome in the fetched events.jsonl (all 'accepted')        4,538   PROVED
  confirmed by the deadline                                         4,439   PROVED
  confirmed after the deadline, present at the fetch                   99   PROVED
without an outcome in that copy                                     2,182   PROVED
  contiguous block, sent_events.jsonl:2012-3771                     1,760   PROVED
  contiguous block, sent_events.jsonl:6299-6720 (end of run)          422   PROVED
published by the last answered poll (controller_metrics.csv:308)    3,416   PROVED
  accepted since the window opened (7,909 - 5,981)                  1,928   PROVED
  queue_depth in that poll                                          1,487   PROVED
  residual                                                              1   PROVED
identities with an outcome ahead of the block                       2,011   PROVED
  beyond the 1,928 counted at the poll (2,011 - 1,928)                 83   PROVED as arithmetic
still queued when the process stopped, at least (1,487 - 83)        1,404   arithmetic PROVED; reading ASSUMED
  + the residual                                                    1,405   ASSUMED for that one identity
```

[F:R01.1–R01.4]. The reading of 1,404 rests on the same source reading as
r02's 1,809 (section 1.1). In r01's complete guest copy of `events.jsonl`, none
of the 1,760 of the internal block has an outcome — **PROVED**
[G:R01.E3, `gates/out/item2_r02_guest_evidence.out.txt:32`]. r01's journal and
its residual broker lines were not analysed [I2 §8].

#### 1.3 The internal block: bounds, not a partition

After the last answered poll, the members of each internal block split by
publication instant on three cuts [F:R02.7, R01.7]:

| group | cut | r02 | r01 |
|---|---|---:|---:|
| G1 | published by the last answered poll (harness wall) | 1,810 | 1,405 |
| G2 | after that poll, up to the old process's last acknowledgement (r02: `events.jsonl:1594`, 00:18:30.034Z harness wall) | 119 | 121 |
| G3a | from that acknowledgement to the first collector row of the new container (r02: 00:18:35Z guest wall) | 56 | 51 |
| G3b | after that row, before the new process's first delivery | 151 | 183 |
| total | | 2,136 | 1,760 |

Only G1 is PROVED: its cut compares harness publication stamps with a
harness-wall poll. G2, G3a and G3b are CONSISTENT-WITH, by the rule applied to
the 1,536 in section 1.1: the G2/G3a cut compares publication stamps with a
controller-clock stamp mapped to harness wall through the marker, and the
G3a/G3b cut compares them with a guest-wall collector row at one-second
resolution, mapped to harness wall with the offset measured at the marker. In
r01 that mapping moves one identity: with the row as recorded, G3a and G3b are
52 and 182 [F:R01.7]. Their labels are not established either. Whether G2 and
G3a reached the old process turns on the instant its MQTT client disconnected,
and no artefact of the run records it: no broker connection log, no controller
container log, no `docker events` and no exit code were collected. On the
harness-side artefacts alone, the defensible statement is a bound:

- received by the old process and left without an outcome: **at least 1,809, at
  most 1,985** in r02; at least 1,404, at most 1,577 in r01 (1,578 with the row
  as recorded);
- published while nothing was subscribed: **at least 151, at most 327** in r02;
  at least 183 (182 with the row as recorded), at most 356 in r01.

Two ends are free of any cross-clock comparison: the lower bound of the first
line (1,809; 1,404), which is arithmetic on the poll ledger read through the
source reading of section 1.1, and the upper bound of the second (327 =
2,136 − 1,809; 356 = 1,760 − 1,404) [F:R02.7, R01.7]. The other two ends
depend on the G2, G3a and G3b cuts and are CONSISTENT-WITH. Both class names
rest on the clean-session semantics and the in-order broker delivery of
section 2(e), both ASSUMED. r01's bracket rests on a collector that sampled the
controller at 0.23 samples/s [F:R01.6], against 0.83 samples/s in r02
[F:R02.6], so its bounds are the weaker of the two.

**What the broker's and the controller's own lines change, in r02 only**
[I2 §4–§6]. The containers that ran r02 were removed on 2026-09-20, but their
log lines survive as residual bytes in free blocks of the guest's data disk;
they agree with preserved artefacts to the millisecond (each of the old
process's 504 outcome lines from 00:17:00Z has one recovered Ditto `PATCH … 204`
line within 49.1 ms) [I2 §3; G:C3]. On them, the old client
`egw-controller-egw-01` disconnected from the broker at 00:18:19.877Z (guest
wall), 10.1 s **before** its last outcome line, and the new process's
subscription was logged at 00:18:48.420Z. G2 and G3a were cut above on the old
process's last acknowledgement, but its subscription had ended at signal 15:
113 of G2's 119 and all 56 of G3a were published while no subscription existed,
and belong with G3b's 151 [I2 §6]. The cut on the broker's instants:

| class | harness-side bounds (above) | with the recovered lines | status |
|---|---:|---:|---|
| received by the old process, never given an outcome line | 1,809 to 1,985 | **1,809 to 1,817** | lower bound arithmetic PROVED; that none ever obtained an outcome line PROVED in the complete guest log; whether the one in flight at the kill (`smart_clothing` seq 1422) reached its twin is not established (section 1.6); upper bound CONSISTENT-WITH |
| published while no subscription existed | 151 to 327 | **319 to 321** (320 on the broker's times) | count CONSISTENT-WITH (recovered instants, bounded offset); that none ever obtained an outcome line PROVED |
| undetermined | 176 | **5 to 7** (published between the last answered poll and the old client's disconnect) | CONSISTENT-WITH |

[I2 §6; G:P1–P3]. Both connections of the controller were logged with `c1`,
which moves the clean session of section 2(e) from ASSUMED to CONSISTENT-WITH
for r02 [I2 §5]. Reading the log's `c1` field as the clean-session flag is
itself CONSISTENT-WITH, not PROVED, wherever this record uses it: the
documentation does not define the field, but the change log records, in
release 1.2, that the clean-session and keepalive status are shown in the log
when a client connects ([CL] `:2789`, `:2815-2816`), and the `k60` beside it
matches the controller's keepalive of 60 s (`src/egw_controller/mqtt.py:31`,
`_KEEPALIVE_S = 60`, passed to the connect call at `:207`). [I4 §4] labels the
same reading ASSUMED; this record uses the one label, CONSISTENT-WITH. The
bounds rest on recovered bytes; whether such bytes are
admitted as evidence is the student's decision [I2 §9, condition 3]. If they are
not, the PROVED results of section 1.5 and of the complete guest log stand, and
the two classes return to the harness-side bounds above. r01's restart was not
re-cut [I2 §8].

**The earlier triple 1,810 / 195 / 131 is not a measurement and is not used
here.** Only its first figure reproduces [F:R02.4]. The other two follow from
one choice of boundary at about 00:18:31Z, and at the offered 11.2 msg/s
moving that boundary by one second moves about eleven identities between them
[F:R02.0, R02.7]. The partition stays assumption-dependent: it is never direct
proof of 1,810 discards from RAM or of 195 losses for want of a subscriber. On
the recovered lines it is superseded by 1,810 (+ up to 7) / 320 / 6 [I2 §6].

#### 1.4 What bears on redelivery

- **PROVED:** none of r02's 2,136 has an outcome record of any kind in the
  fetched copy, while the 2,225 identities that follow the block in
  `sent_events.jsonl` (3,819 − 1,594) all have one [F:R02.5]. The same holds
  for r01's 1,760, with 2,527 after its block [F:R01.5]. That those later
  outcomes were written by the new process follows from the FIFO order of
  section 2c: **ASSUMED** (source reading).
- **CONSISTENT-WITH** no redelivery after the restart: the consumer is FIFO
  (section 2c), so a delivery resent at reconnection would have been processed
  before the later publications that did obtain outcomes. This is reasoning
  from the code, not an artefact line.
- **PROVED since** [I2 §7]: in r02's complete guest copy none of the 2,136 has
  an outcome and no identity has two `accepted` lines [G:R02.E2–E3], so no
  redelivery happened as far as outcomes show; the mechanism, a clean session
  on both connections (`c1`), is CONSISTENT-WITH (recovered broker lines,
  section 1.3).
- The draft's argument — "the `duplicate` counter stayed at zero, so nothing
  was redelivered" — does not hold: a redelivered message that had not reached
  the twin would be classified `accepted`, not `duplicate`. What carries the
  point is the absence of any outcome for the 2,136.

#### 1.5 How the old process ended

- **PROVED** (harness wall only): in r02 its HTTP server last answered at
  00:18:19.443Z; the next answered poll, at 00:18:48.558Z, came from the new
  process, a 29.115 s gap [F:R02.3].
- **CONSISTENT-WITH** (a controller-clock stamp compared with the harness's
  restart record through the marker): in r02 it wrote outcomes until 14.690 s
  after the restart command started (15.791 s in r01), its last at
  00:18:30.034Z harness wall (21:55:38.374Z in r01) [F:R02.5, R01.5].
- **CONSISTENT-WITH** a SIGTERM near the last answered poll and a SIGKILL about
  ten seconds later: the last outcome is 10.6 s after the last answered poll in
  r02, and 10.7 s in r01, on the same mapping [F:R02.5, R01.5].
- **PROVED for r02 from the guest's journal** [I2 §4; G:J1–J2]: signal 15 was
  sent no later than 00:18:19.708Z (guest wall); the engine logged at
  00:18:29.708Z that the container "failed to exit within 10s of signal 15"
  and forced the stop; exit status 137 was recorded at 00:18:30.166Z, with the
  restart policy not applied; the same container was started again at
  00:18:33.602Z. The name SIGKILL is read from 137 (128 + 9); no permitted
  source states that encoding [I2 §4]. The old process disconnected from the
  broker first and went on writing outcomes until 0.18 s before the recorded
  exit (recovered lines, CONSISTENT-WITH) [I2 §4]. The engine's default stop
  timeout in general is not established; 10 s is what applied to this stop
  [I2 §7].
- **ASSUMED for r01:** the SIGKILL itself. No exit code, `docker events` record
  or container log of r01 was collected, and r01's journal was not extracted
  [I2 §8].

#### 1.6 What could not carry any argument, and what the guest's records settled since

- **The simulator's PUBACK stamp.** Its capture is best-effort within a wait
  budget (`src/CONTRACTS.md:348-351`; `src/egw_simulator/publisher.py:160-167`)
  [C]. 421 identities that obtained an outcome in r02, and 503 in r01, carry a
  null `puback_monotonic_ns` [F:R02.11, R01.11]. No delivery claim rests on it.
- **The end-of-run blocks** (765 in r02, 422 in r01). Neither run has a
  post-drain second fetch [F:R02.9, R01.9]. The guest's complete copies settle
  them: all 765 of r02 and all 422 of r01 were accepted, all after the
  deadline, none twice — the last 92.440 s after it in r02 and 43.713 s in r01.
  **PROVED**: late, not lost [I2 §7; G:R02.E2–E4, R01.E3–E4].
- **The twins.** No twin state was recorded after either restart run
  (`restart_evidence.md` section 5; r02's "after" snapshot was never taken,
  [I2 §2]). Whether the twin-backed duplicate state rebuilt correctly after the
  restart — the mechanism ADR 0006 relies on — *I could not establish*. For
  r02's in-flight identity, `smart_clothing` seq 1422 (`sent_events.jsonl:1595`
  [F:R02.5]), no `PATCH 204` line was logged by the old process after its last
  outcome line [G:C4]: CONSISTENT-WITH no 2xx response received; a `PATCH`
  applied by Ditto whose response never arrived is not excluded, and whether
  the twin carries it *I could not establish* [I2 §7]. Its twin's
  `accepted_count` would settle it (4,093 would be the N1 case, 4,092 not); it
  exists, if at all, only in MongoDB's files on the guest's data disk, which
  were not read [I2 §8].
- **The guest-side evidence.** The protocol proposal asks for the full guest
  event log, the twins' ingestion counters and the controller container logs of
  r02 to be read before this decision
  (`docs/governance/proposals/acceptance_protocol_update_2026-09-19.md`,
  section 3, proposal item 2). **They have been read, except the twins'
  counters, without starting the guest** [I2 §1, §9]: the complete guest event
  log and the guest's journal as intact files, the controller's and the
  broker's logs as residual bytes. Nothing was preserved in the raw run, the
  candidate capsule or the historical packages [I2 §2]. What was read confirms
  the proposal's Finding 2 [I2 §9]. The residual bytes are perishable: any
  later guest session can overwrite them, so they are to be preserved before
  the guest is booted again [I2 §9, condition 1].

#### 1.7 What was at stake without a restart: `nominal-r01` (2026-09-19; `valid`, sealed)

Its populations, each with the copy and the instant at which it was collected
[F:N.0–N.2]. The deadline is the controller end marker plus the unchanged 60 s
(`manifest.json`, `confirmation_deadline_monotonic_ns`).

| population | count | collected in | at |
|---|---:|---|---|
| confirmed by the deadline | 3,794 | the sealed `raw/nominal-r01/events.jsonl` | harness fetch started 2026-09-19T20:13:57.289Z (`manifest.json`, `events_fetch`) |
| accepted after the deadline, present at that fetch | 85 | same | same |
| without an outcome at that fetch | 2,841 | same, by absence | same |
| accepted after the deadline, all | 2,926 = 2,841 + 85 | `analysis/events.post-drain.jsonl` | fetch started 2026-09-19T20:21:43.527Z (`commands.jsonl` seq 6), after the `drained` helper ran 464.875 s (seq 5) |
| without an outcome after the drain | 0 | same | same |

All 2,841 without an outcome at the harness fetch ended accepted late; none was
lost after the drain [F:N.2]. The run failed its delivery criterion and stays
failed: a late record stays late, and the post-drain copy rescues nothing.

At the window end **3,593** identities were inside the controller — received,
not yet acknowledged by Ditto [F:N.3] — held, on the source reading, in the
in-process `asyncio.Queue` (`service.py:150-152`; ASSUMED). The highest sampled
`queue_depth` was 3,590, 35.90 % of the 10,000-slot cap, and `dropped` was 0 in
all 721 samples [F:N.4]. The nominal run had no restart, so what a kill at that
instant would have done to them is not observed, and nothing here states it.

#### 1.8 Why a backlog existed

In `nominal-r01` the served rate observed in each phase — 4.94 msg/s during
the warm-up, 6.457 msg/s over the measured window, 8.864 msg/s draining with no
ingress — and in each 60 s block of the window (5.32 to 8.55 msg/s,
event-log acknowledgements per block, the construction of
`backlog_diagnosis.md` section 3.1) was below the 11.2 msg/s offered
[F:N.5, N.7]. These are observations of one failed run under emulation; they
are not a capacity and fix no maximum. The two restart runs held 1,445 (r01)
and 1,840 (r02) queued at t+300 s, just before their restart
[F:R01.10, R02.10]. As an illustration only: borrowing `nominal-r01`'s phase
rates, r02's 1,867 queued would have needed about 211 to 378 s to serve
[F:S.2]; at r02's own old-process rates — 5.051 msg/s under ingress, from the
sampler's first reading to the last answered poll (counters, harness wall),
and 5.476 msg/s from that poll to the last acknowledgement (cross-clock) —
about 370 and 341 s [F:R02.12]. The restart gave the old
process about 14.7 s of further output (section 1.5).

### 2. What the controller does today (source reading at `35fe8bb`)

Code at `35fe8bb` [C]. Nothing in this section has been tested.

**(a) The PUBACK is sent before the message exists in the controller's own
state.** The client is built with neither a `manual_ack` nor a `clean_session`
argument (`src/egw_controller/mqtt.py:73-76`); neither word occurs anywhere
under `src/` [C]. In paho-mqtt 2.1.0 the default is `manual_ack: bool = False`
(`paho/mqtt/client.py:742`, stored at `:751`), and a QoS 1 PUBLISH is
acknowledged by `_send_puback(message.mid)` as soon as `on_message` returns
(`client.py:4147-4152`) [C] — ASSUMED for the image in general, whose paho
version no run manifest records; CONSISTENT-WITH for r02's container, recorded
with paho-mqtt 2.1.0 (Code identity; [I2 §7]). The callback stamps `received_monotonic_ns` (`mqtt.py:189`), returns
doing nothing else if no event loop is attached (`:190-193`), and otherwise
only *schedules* the enqueue with `loop.call_soon_threadsafe(self._submit,
inbound)` (`:199`). So when the PUBACK leaves, the message has not been counted
(`service.py:161`), queued (`:163`), validated, written to Ditto (`:320`) or
recorded (`:414`). **Today the PUBACK means "a callback ran in the controller
process" — not received, queued, applied or recorded.** Relative to durable
admission, the controller has none: the only durable points a message ever
reaches are the twin write and the flushed outcome line (d, h), and the PUBACK
precedes both.

**(b) The inbound queue is volatile and bounded.**
`asyncio.Queue(maxsize=queue_maxsize)` (`service.py:150-152`),
`DEFAULT_QUEUE_MAXSIZE = 10000` (`:39`), applied because `create_app_from_env`
passes no size (`app.py:144-150`); no `EGW_*` variable sets it
(`config.py`) [C]. On overflow the message is counted in `received` and
`dropped`, and the warning names only its topic (`service.py:161-169`). The
package has no `signal`, `atexit` or `fsync` [C].

**(c) One consumer, strictly FIFO** (`service.py:182-197`): take a message,
raise `in_progress`, `await self.process(message)`, catch everything, lower
`in_progress` — and raise `processing_errors` if no outcome counter moved
(ADR 0010).

**(d) The outcome is recorded after the twin is written, and flushed, not
synced.** Inside `process`: on a device's first message the duplicate state is
seeded from its twin (`service.py:287-301`), then the duplicate check
(`:303-314`), the Ditto `PATCH` (`:320`), `dedupe.record` (`:332-334`), and the
event line and outcome counter (`_emit`, `:390-415`, with the write at `:414`).
Every path through `process` that returns normally writes exactly one outcome
line: `rejected` for each validation failure (`:212-285`), otherwise
`duplicate`, `failed` or `accepted`. `EventLogger.log` writes and `flush()`es
each line (`events.py:112-119`): to the kernel, not to disk.

**(e) The MQTT session is clean; the client id is stable.** For MQTT 3.1.1
paho sets `clean_session = True` when none is given (`client.py:785` in 2.1.0)
[C] — ASSUMED for the image. The client id is `egw-controller-{EGW_ID}`
(`mqtt.py:75`; default `egw-01`, `config.py:59`, `:104`). The subscription is
requested at every connect (`mqtt.py:103`) and readiness is declared only when
the SUBACK grants it (`:149-152`). ASSUMED from the protocol, which states it
(OASIS MQTT 3.1.1, section 3.1.2.4, [MQTT-3.1.2-6]; [I2 §5]), and
CONSISTENT-WITH section 1.4: with a clean session the broker keeps nothing for
the controller while it is disconnected, and discards unacknowledged deliveries
together with the session. That r02's controller connected with a clean
session both times is CONSISTENT-WITH its recovered broker lines (`c1`, read as
the clean-session flag, itself CONSISTENT-WITH: section 1.3) [I2 §5]; for the
other runs it stays ASSUMED.

**(f) A graceful stop takes the subscription down first, then drains; only the
engine bounds the drain.** uvicorn handles SIGTERM (`uvicorn/server.py:36`,
`:342-347` in 0.52.1 [C]; ASSUMED for the image) and runs the lifespan
`finally` (`app.py:159-164`): `bridge.stop()` — DISCONNECT, then `loop_stop()`
(`mqtt.py:211-217`) — then `await service.stop()`, which appends the `None`
marker (`service.py:199-201`), then `await pipeline_task`, which drains
everything ahead of the marker. A delivery that the network thread scheduled
but the loop had not yet run lands behind the marker and "is counted in
`received` and stays in `queue_depth`" (`src/CONTRACTS.md:282-283`).
`compose.yaml` sets no `stop_grace_period` or `stop_signal` for the controller,
and `src/Dockerfile` no `STOPSIGNAL` [C]; the runbook restarts with
`docker compose … restart controller` and no `-t`
(`docs/setup/qemu_integrated_gateway.md:1123`). The engine's own stop timeout
therefore decides how much of the drain happens. No run artefact records its
value; the guest's journal records that 10 s applied to r02's stop, which was
forced while the old process was still writing outcomes (section 1.5;
[I2 §4, §7, §9]). **On SIGTERM, then,
the volatile queue loses** the deliveries behind the marker and, if the
engine's timeout expires before the drain ends, everything not yet drained —
all of it already acknowledged to the broker. In r02 the order was the one
read here from the source: DISCONNECT first, then the drain (recovered lines,
CONSISTENT-WITH) [I2 §4]. uvicorn is 0.53.0 in r02's container, not the 0.52.1
read in the analysis environment [I2 §7].

**(g) A killed process runs no code** (`src/CONTRACTS.md:286-287`). **On
SIGKILL the volatile queue loses everything in it**, together with the message
in progress, the deliveries still being handed over from the network thread and
the in-memory duplicate state — all acknowledged to the broker. Lines already
written survive, because they are with the kernel and the event directory is a
bind mount (`compose.yaml:290`). The container is `restart: unless-stopped`
(`compose.yaml:256`).

**(h) What is durable.** Every accepted `PATCH` writes the twin's `ingestion`
feature — `last_message_id`, `last_seq`, `last_run_id`, `last_ts`,
`accepted_count` (`ditto.py:70-74`) — and after start-up each device's
duplicate state is rebuilt from it on that device's first message
(`service.py:287-292`; `dedupe.py:52-81`; ADR 0006). The rule rejects a
repeated `message_id` and, within one `run_id`, any `seq <= last_seq`
(`dedupe.py:91-113`).

**(i) What a replay would do today.** There is no replay path. A message
delivered again under the same `run_id` is accepted if its `seq` is above the
twin's `last_seq` and classified `duplicate` otherwise (`dedupe.py:103-112`).
FIFO processing means that everything left unprocessed at a death has a higher
`seq` than what reached the twin for that device — except the one message in
progress. If its `PATCH` was applied before the death and its line not yet
written (between `service.py:320` and `:414`), the twin covers it, the event
log does not, and any later delivery of it is `duplicate` for ever
(`controller_today.md` section 4.3). `analyze.py` counts an identity as
delivered only through an `accepted` record (`src/egw_experiments/analyze.py:1766`,
`:1808`, `:1821`), so such an identity is reported `lost` although the twin
carries it.

What each way of stopping loses today:

| event | deliveries left without an outcome | code | evidence |
|---|---|---|---|
| controller disconnected — down, or between reconnect and SUBACK | everything published meanwhile | (e) | r02: 319–321 on the recovered broker lines, 151–327 without them; r01: 183–356 (section 1.3) |
| graceful stop that completes | deliveries scheduled but not enqueued when the marker is appended, already acknowledged | (a), (f) | not separable in the runs |
| graceful stop cut short by the engine, or SIGKILL | the queue, the message in progress and deliveries in hand-over, all already acknowledged | (a), (b), (g) | r02: a stop forced 10 s after signal 15, PROVED (section 1.5); 1,809–1,817 without an outcome line (lower bound by arithmetic; that none ever obtained an outcome line PROVED in the guest log, whether the one in flight at the kill reached its twin not established; "still queued at the stop" CONSISTENT-WITH). r01: at least 1,404 by arithmetic, "still queued at the stop" ASSUMED (sections 1.1–1.3) |
| queue overflow | the dropped delivery, identified only by topic | (b) | not observed: `dropped` 0 in every sample of all three runs [F:R01.3, R02.3, N.4] |
| failed event write, cancelled consumer | the message in progress; the twin may carry it | (c), (d); `src/CONTRACTS.md:186-195` | not observed |

`controller_today.md` section 6 lists thirteen such paths (A to M) with their
anchors; the table keeps the ones this decision acts on.

### 3. The options

**Cost arithmetic common to every option.** The consumer is serial (2c). An
added per-message cost *x* on its path turns a served rate *r* into
1 / (1/*r* + *x*). That is algebra, not a measurement: **for no option below is
*x* measured on this platform**, and no preserved artefact measures an `ack`
call, a durable write or an `fsync` on this guest. What a measured *x* would
cost against the rates observed in the three phases of `nominal-r01` [F:S.1]:

| added *x* | warm-up, 4.940 msg/s | window, 6.457 msg/s | drain, 8.864 msg/s |
|---:|---:|---:|---:|
| 1 ms | −0.49 % | −0.64 % | −0.88 % |
| 10 ms | −4.71 % | −6.07 % | −8.14 % |
| 50 ms | −19.81 % | −24.41 % | −30.71 % |

The phase rates are observations of one failed run, not ceilings. The table
replaces the draft's "ceiling on the 154.77 ms budget", a base in which
warm-up acknowledgements were mixed into the window
(`verification_figures.md`, finding B1).

**The two G3 families this decision touches most** (runbook section 7). **Test
6** is a harness run of the `controller_restart` condition — 600 s at
11.2 msg/s with a restart at t+300 s (`qemu_integrated_gateway.md:1116-1138`);
its G3 criterion is "controller restart with recovery inside the bounded window
and no record accepted twice" (`docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md:630-631`).
**Test 5** disconnects the *simulator*, which buffers during its dropout
windows and publishes the backlog on reconnection; its one execution
(2026-09-18) accepted all 2,016 valid events but 326 after the deadline, and
failed (`qemu_integrated_gateway.md:1114`).

**The other families.** All nine runbook tests pass through the `drained`
helper, directly or through `run_test` → `pre` (`~/egw-tcg/itest-helpers.sh:173-179`)
[C], so a change to `drained` touches every family (see "Ordering, duplicates,
durability and configuration identity"). Under option 5 that change is needed
(gate item 4, [I4 §0, §8]): the *condition* changes for all nine families, the
session drivers and the proof; the *outcome* can change only after a restart, a
reconnection or a reboot, or after a delivery left without an outcome line —
for test 6 after its restart, for test 8 before its reboot, for the G2
persistence driver, and for the proof ([I4 §7], which lists every call site).
The broker's window and queue options are global in 2.0.22, so under option 5
they apply to every subscriber, test 9's ACL probe included [I1 §2]. Test 8,
the guest reboot (`qemu_integrated_gateway.md:1183`), is otherwise not assessed
here under a persistent controller session with the broker's 60 s autosave
(`mosquitto.conf:33-35`). Beyond `drained` and the broker's global options, the
effect of each option on tests 1 to 4, 7 and 9 is not assessed in this record
either.

**The pilot plan's load sweep and soak, under option 5.** The broker's window
and queue settings are global ([I1 §2]; [M5] `:582`, `:685`), so the frozen
candidate carries them into every campaign condition, not only into the nine
families. The campaign plan is generated from the repository
(`experiments/README.md:97-107`; `src/egw_experiments/plan_gen.py:24`,
`:74-95`); the generated file the pilot uses, `~/egw-tcg/pilot/campaign_plan.json`
(named at `tools/session/nominal.sh:46`), lies outside the repository and was
not read for this record. The figures below are the repository's at
`35fe8bb`: `load_sweep` runs 10 repetitions (`src/egw_experiments/protocol.py:300`)
of 300 s (`:301`) at each of 10, 50, 100 and 250 msg/s (`:304`;
`experiments/README.md:68`), 40 runs; the `soak` is one run (`protocol.py:401`)
of 86,400 s (`:402`) at the nominal rate (`:406`), 11.2 msg/s (`:54`). With the
broker measurement's candidate values W = 4,999 and Q = 1,000 [I1 §7], the
offered counts give the thresholds below (a smaller W raises both kinds, a
smaller Q the second):

- **The window fills.** A 300 s run offers 3,000, 15,000, 30,000 and 75,000
  messages at the four rates. At 10 msg/s that is fewer than W, so the window
  cannot fill. At 50, 100 and 250 msg/s the window fills during the run if the
  controller serves less than (15,000 − 4,999) / 300 = 33.3, (30,000 − 4,999) /
  300 = 83.3 and (75,000 − 4,999) / 300 = 233.3 msg/s on average over it. The
  highest 30 s served rate this record cites for `nominal-r01` is 11.60 msg/s,
  after ingress had stopped (option 2 below; `backlog_diagnosis.md` section
  7.1). The soak offers 967,680 messages; its window fills if the controller
  serves less than (967,680 − 4,999) / 86,400 = 11.14 msg/s on average over
  24 h, and every phase of `nominal-r01` served less than 11.2 msg/s (section
  1.8). Once the window has filled, P5 no longer holds for the rest of the
  run: the wait moves into the broker and out of `latency_ms`, the effect
  rejected as an alternative ("A small in-flight window as deliberate
  back-pressure").
- **Overflow moves from the controller to the broker.** Beyond W + Q = 5,999
  held, the broker drops: at 50, 100 and 250 msg/s if the controller serves
  less than 30.0, 80.0 and 230.0 msg/s on average, and in the soak below
  11.13 msg/s. Today the controller's 10,000-slot queue (`service.py:39`)
  overflows below about 16.7, 66.7 and 216.7 msg/s, and 11.08 msg/s in the
  soak, and counts each drop per process in `dropped` (`service.py:161-169`).
  Under option 5 the drop is counted only broker-wide, and only if the student
  makes choice C2 (N4); the broker measurement cannot show this connected-queue
  overflow either [I1 §7].
- **What this is.** Thresholds on offered counts, not capacity figures: that a
  load-sweep run at 50 msg/s or more, or the soak, fills the window is
  expected, not established. Whether W, Q or the load-sweep protocol must
  answer it before the freeze is left to the student, or to the G4 protocol
  decision (T4); it sits beside open item 3.

#### Option 1 — acknowledge only after durable admission

Build the client with manual acknowledgement and send a delivery's PUBACK only
once the controller holds the delivery durably. The only durable point the
controller has is the outcome line (2d), so here "durable admission" means
**after the outcome line has been written**.

- **Promises, alone:** while one connection lasts, the broker regards as
  delivered only what has an outcome line.
- **Does not promise:** anything across a restart. With a clean session the
  broker discards the session, unacknowledged deliveries included, at the
  disconnect (ASSUMED from the protocol). Alone, it recovers nothing that r01
  or r02 lost.
- **Throughput cost here:** one `ack` call per delivery from the event-loop
  thread; unmeasured. The larger cost falls on measurement: while the broker's
  in-flight window for the controller is full, further deliveries wait in the
  broker, where nothing is stamped, so `latency_ms` (`src/CONTRACTS.md:304-306`;
  ADR 0005) would exclude that wait and fall while no confirmation arrives
  sooner. `mosquitto.conf` configures neither `max_inflight_messages` nor
  `max_queued_messages` [C]; the 2.0.22 manual documents their defaults as 20
  in flight and 1,000 queued per client above those in flight [I1 §2], so on
  today's configuration the window fills at 20.
- **Effect on G3:** test 6 unchanged in substance — the restart still discards.
  Test 5: if the window is smaller than the reconnect burst, the burst waits in
  the broker and the reported latency falls without any confirmation arriving
  sooner — a change in what is measured, never an improvement.

#### Option 2 — a persistent MQTT session with the stable client id

Build the client with `clean_session=False` on the existing id (`mqtt.py:75`).
The broker already runs `persistence true`, `persistence_location
/mosquitto/data/` and `autosave_interval 60` (`mosquitto.conf:33-35`); no
`persistent_client_expiration` is set [C].

- **Promises, alone:** while the controller is disconnected, the broker keeps
  its subscription, queues QoS 1 publications for it and delivers them on
  reconnection (ASSUMED from the protocol; never observed on this broker), up
  to a per-client queue bound that is not configured; its documented default
  is 1,000 above those in flight, and beyond it the broker drops, counted only
  in a broker-wide `$SYS` counter that no user may read today [I1 §2, §3].
  Whether the drop is logged is set out under N4.
- **Does not promise:** the deliveries already acknowledged and waiting in the
  controller's queue — the larger class, at least 1,809 in r02 (1,809 to 1,817
  on the recovered lines, section 1.3). The PUBACK is still sent at callback
  return (2a).
- **Throughput cost here:** nothing on the controller's path. The broker's cost
  of holding session state and writing it every 60 s is unmeasured
  (`verification_figures.md`, finding B7). The outage's publications arrive at
  once on reconnection: in r02 that class counted at least 151 and at most 327
  identities on the harness-side artefacts, and 319 to 321 on the recovered
  broker lines, over a 28.5 s outage (section 1.3; [I2 §6]). A persistent
  session also removes the premise of today's `drained` argument, that the
  bridge asks for no persistent session (`qemu_integrated_gateway.md:1004`), so
  state D1 — HTTP answering while the session is not resumed — applies to
  this option too; item 4 describes D1 (its S1) for option 5 [I4 §3] and did
  not assess option 2. In none of the three phase averages of
  `nominal-r01` [F:N.5], and in none of the 30 s blocks of its measured window
  (at most 9.47 msg/s, `backlog_diagnosis.md` section 3.1), did the served rate
  reach 11.2 msg/s; after ingress stopped it did, briefly (11.60 msg/s in the
  first 30 s, ibid. section 7.1). So under continuing ingress at that rate
  such a burst is not expected to clear during the run — expected from one
  run, not established.
- **Effect on G3:** test 6 — the outage class would be queued and delivered
  instead of never delivered, but the larger class is untouched, so test 6
  would still leave identities without an outcome. Test 5 — no effect: the
  controller is not the client that disconnects.

#### Option 3 — a durable local inbox with ordered, idempotent replay

On arrival, append the delivery to a local store on the event bind mount
(`compose.yaml:290`); acknowledge after that write; have the consumer read from
the store and mark a record done after its outcome line; on start-up replay the
unfinished records in order through the unchanged pipeline, with idempotence
from ADR 0006.

- **Promises:** a delivery acknowledged to the broker survives a controller
  kill and is processed after the restart. `received_monotonic_ns` keeps its
  meaning, because the store is written after the stamp.
- **Does not promise:** the outage class — a message published while the
  controller is down never reaches the inbox, so option 3 needs option 2 for
  it; durability against a guest loss unless each write is `fsync`ed;
  exactly-once (the in-progress case of 2i remains).
- **Throughput cost here:** one durable write per delivery on the ingress path,
  plus an `fsync` for guest-loss durability, plus the replay at start-up — all
  unmeasured on this guest; the table above gives what a measured cost would
  do, on a guest that already served below the offered rate in every observed
  phase (section 1.8). It is also the largest change: a persistent format, a
  recovery path, truncated-tail handling after a guest loss, a new contract and
  its tests.
- **Effect on G3:** with option 2, test 6's two classes would both be
  recovered (intended), at an unmeasured per-message cost that would slow every
  timed family, tests 5 and 6 included, by the table's arithmetic for whatever
  that cost proves to be.

#### Option 4 — do nothing, and state the limitation

- **Promises:** today's behaviour (section 2), at no cost.
- **Keeps:** a restart under backlog leaves the controller's queue without
  outcomes — at least 1,809 in r02 and 1,404 in r01 by arithmetic, none with an
  outcome line in either run's complete guest log (PROVED, sections 1.1, 1.2;
  whether the one in flight at the kill reached its twin is not established) —
  and the broker keeps nothing for the outage (in r02 319 to 321 on the
  recovered broker lines, at least 151 without them; 182 to 183 at least in
  r01, subject to the clock caveat of section 1.3). It keeps `drained`'s
  argument as it stands: with a clean session the broker holds nothing for the
  controller [I4 §3].
- **Effect on G3:** test 6 would record identities without an outcome across
  every restart under backlog: a measured negative result, reported as such,
  and the G3 criterion "recovery … and no record accepted twice" would not be
  met on delivery. Claim C12 — "duplicate detection survives a controller
  restart", whose acceptance includes delivery through the restart
  (`docs/claim_evidence_matrix.md:173`) — could not be supported on delivery.
  Whether the harness's zero-lost gate for that condition passes at
  11.2 msg/s is an unresolved risk under every option, not only this one: the
  earlier candidate confirmed late in every timed run and no changed candidate
  has been measured (see "Relationship with the throughput problem"); what the
  options settle is whether the restart classes are processed late or never,
  and under option 4 they are never processed *(corrected 2026-09-24; this
  sentence had predicted that the gate fails under every option)*. Test 5 —
  no effect. Defensible only if the dissertation
  states the limitation and reports the condition as a negative result.

#### Option 5 — options 1 and 2 together: the broker holds every delivery until its outcome is recorded

Acknowledge each delivery only after its outcome line is written (option 1), on
a persistent session with the stable client id (option 2), with the broker's
in-flight window for the controller set large enough that the backlog stays in
the controller's queue, where it is stamped (in 2.0.22 the window is a global
setting, so it applies to every subscriber [I1 §2]).

- **Promises:** set out exactly in the Decision. In short: nothing the broker
  has delivered to the controller is released at the broker before its outcome
  is recorded, and nothing published while the controller is away is dropped
  for want of a session — both within explicitly configured and recorded
  broker bounds.
- **Does not promise:** set out in the Decision — exactly-once, broker or guest
  loss, unbounded retention, ordering beyond the broker's, throughput,
  deadlines.
- **Throughput cost here:** one `ack` call per delivery on the controller's
  path (unmeasured), and one counter update per delivery and one per
  acknowledgement for the `unacked` field that `drained` needs (unmeasured)
  [I4 §6]. The broker holds up to a window's worth of unacknowledged copies
  and writes a larger store every 60 s (unmeasured; its container limit is
  128 MiB, `compose.yaml:87`). What those copies cost in the broker's memory
  is documented nowhere and cannot be established without measuring; the data
  alone weigh at most 1.80 MiB for 4,999 messages, the broker used 4.17 to
  7.34 MiB in `nominal-r01` while holding no backlog, and it would have to
  spend more than about 24.7 KiB per held message for 4,999 to reach the
  limit — bounds for the measurement to rule out, not an estimate
  [I1 §5]. No new persistent format and no per-message write by the
  controller.
- **On today's broker configuration it cannot run** [I1 §4]: the documented
  defaults hold 20 in flight and 1,000 queued per client, 2,573 to 3,979 short
  of the range 3,593 to 4,999 examined below, and beyond them the broker drops
  (N4); the window of 20 would also move the wait into the broker, which
  P5 excludes. It needs the settings and the broker measurement set out under
  "The conditions option 5 carries", and, if the student makes that choice
  (C2), the readable drop counter.
- **Size of the change:** no longer small. The four gate items add to the ten
  code items first listed a rule for every delivery that ends without an
  outcome line [I3 §7, §8], three `/metrics` fields and a changed `drained`
  [I4 §5], explicit broker settings and, if the student makes choice C2, an
  ACL grant [I1 §8], and the tests that go with them ("What must change").
- **Effect on G3:** test 6 — both classes would be redelivered to the new
  process instead of being left without an outcome (intended; tested by the
  proof below). The redelivered backlog then joins continuing ingress at
  11.2 msg/s, so late confirmations are expected as in `nominal-r01`. "No
  record accepted twice" rests on the ADR 0006 rebuild, untested across a
  restart (section 1.6). Test 6 also requires every `delta` line `OK`
  (`qemu_integrated_gateway.md:1130`): a restart, or a connection ended under
  A3 after a `PATCH`, that produces an N1 case leaves one twin one ahead of its
  `accepted` lines, which the battery records as a `MISMATCH` — the proof
  tolerates that case when it is named (S5), the battery's criterion does not.
  Test 6's `drained` after the restart must then wait
  until the new process is subscribed, holds nothing unacknowledged and has
  processed the redelivered backlog [I4 §7]; whether that fits within the
  helper's 900 s limit *I could not establish* [I4 §6]. Test 5 — unchanged
  provided the window is not full: the simulator's reconnect burst reaches the
  controller as today, and its deadline result is a matter of processing rate
  that this option does not touch. Test 8 — the `drained` before the reboot is
  what ensures that the broker's persisted session holds nothing to redeliver
  after it [I4 §7]; otherwise not assessed. Tests 1 to 4, 7 and 9 — the
  `drained` condition changes; the outcome changes only in D1 or D2 [I4 §7].
  The broker's window and queue settings apply to every subscriber, test 9's
  probe included [I1 §2], and a `$SYS` read grant would change the ACL that
  test 9(d)/(e) proves [I4 §4].

| | 1 alone | 2 alone | 3 with 2 | 4 | 5 |
|---|---|---|---|---|---|
| deliveries inside the controller at a kill | discarded (source reading) | discarded (source reading) | recovered (intended) | discarded (source reading) | recovered (intended) |
| publications while the controller is away | never delivered (clean session, ASSUMED) | queued by the broker (intended) | queued by the broker (intended) | never delivered (clean session, ASSUMED) | queued by the broker (intended) |
| added cost on the controller's path | `ack` call, unmeasured | none | durable write (+ `fsync`), unmeasured | none | `ack` call and `unacked` counter updates, unmeasured [I4 §6] |
| added cost in the broker | none | session state, unmeasured | session state, unmeasured | none | session state and held copies, unmeasured |
| meaning of `latency_ms` | changes when the window fills (at 20 on today's configuration [I1 §2]) | unchanged | unchanged | unchanged | unchanged for first deliveries while the window is not full; a redelivery is timed from its redelivery |
| `drained` precondition | not assessed | D1 applies (persistent session; by item 4's reasoning, not assessed there) | D1 applies (as option 2) | unchanged, truthful as argued today [I4 §3] | must change: D1 and D2 [I4 §3, §5] |
| on today's broker configuration | window 20 | queue 1,000 per client | queue 1,000 per client | not concerned | cannot run: 1,020 held at most, drops beyond (N4) [I1 §4] |
| size of the change | small | one argument and broker configuration | large | none | twenty work items, contract text, tests, broker configuration ("What must change") |
| after the four gate items | not recommended: recovers nothing across a restart | not recommended alone: the larger class stays in RAM | held in reserve: its write is unmeasured | the next best if option 5 is refuted or cannot be made ready | **recommended, under conditions**; ruled out on today's configuration |

*Recovered*, in this table and wherever this record uses the word of a
delivery or an identity, means: delivered to the controller after the kill or
the outage — again, or for the first time — and ending with an `accepted`
line; or, where its effect had already reached the twin, a `duplicate` line,
which is the N1 case. An identity that obtains only a `failed` line has an
outcome line but is not recovered; under A1 `failed` also covers a processing
error raised before the `PATCH` ("What must change", contracts and records).

---

## Decision

### The decision recorded on 2026-09-24

**The student decided option 5 for bounded implementation on 2026-09-24**, in
the words "Avança com a opção 5" ("go ahead with option 5"), in answer to the
decision request of 2026-09-23 (`decision_request.md` in the review record;
its Portuguese page is held outside the repository) and to the project
manager's note of 2026-09-24 (`PM_PACKAGE_D_READY_FOR_DECISION_2026-09-24.md`,
held with the project manager's records outside the repository), which
recommended that decision with the choices below. The choices the request put
to the student go with the decision as recommended; any of them the student
amends is re-recorded here, dated.

- **Recovery (decision A): option 5** — the bounded implementation of "What
  must change": the twenty items, the contract text, the regression tests
  with fakes and an identified controller image — with **option 4 as a
  separate, prospective scope decision** if the proof refutes the option or a
  checkpoint below is missed; never an automatic fallback.
- **A3: (a), in process** — the connection closed and reopened by the
  controller — under A5's bound: a back-off on reopening, `/ready` false
  while outcomes cannot be recorded, acknowledgement and the queue scoped to
  the connection (A4's purge), and a visible, bounded failure when the same
  cause repeats. Condition C3 tested none of these controller behaviours; the
  regression tests and the proof cover them.
- **Queue bound and expiry (C1): `max_queued_messages 1000` and
  `persistent_client_expiration 1h`** — the two values the broker measurement
  exercised on 2026-09-23. They are the candidate's configuration, not a
  validated expiry (no session expired in that measurement) nor a queue shown
  adequate for any outage but r02's 28.5 s at 11.2 msg/s with queue space
  free when it began; `persistent_client_expiration` is the expiry of a
  disconnected session, not a message lifetime. Being global, they bind every
  family — tests 1 to 4 included — the pilot and the campaign; the regression
  coverage is not narrowed on the strength of a family summary's "only
  `drained`".
- **C2: declined, knowingly.** The ACL stays as deployed and test 9's proof
  unchanged. What is lost is stated under C2 and N4: no broker counter deltas
  per run and no disconnected-client pre-check; the broker log's one `notice`
  line per client per connection is no substitute. Complete broker logs and
  reconciliation by identity are kept for every run. A missing or late
  identity whose cause cannot be attributed is **indeterminate in cause**
  only: it stays in the outcome and loss accounting under the unchanged
  rules, it never makes a run evidence-invalid, and it never disappears from
  the results.
- **Throughput (decision B): T1** — the candidate is frozen with the recovery
  change only; each timed family that misses its deadline is recorded as
  failed, and the throughput question goes to the prospective G4 protocol
  decision (T4), which resolves no G3 criterion. **The optional extension of
  the proof, T2 (throughput work first) and T3 (the bounded throughput
  measurement) are not in this package.**
- **Carved and recovered bytes:** their standing is unchanged by this
  decision [I2 §9]; no result and no loss is reclassified.

**Checkpoints** (the project manager's recommendation of 2026-09-23, adopted
with the decision): a progress return by **2026-09-27** or after the first
eight reported engineering hours, whichever comes first — behaviours and
tests completed, regressions passing and failing, blockers, remaining effort;
by **2026-10-01** the bounded implementation complete with its regression
tests passing and the candidate identified, ready for the proof; by
**2026-10-03** the mandatory proof valid and supporting the option, residuals
reviewed and the candidate ready to freeze — an inconclusive, refuted or
unfinished proof does not meet it. Missing either terminal checkpoint returns
the matter to the student before any further work: no automatic option 4, no
relaxed criterion, and any change of G3's scope only by a dated prospective
decision. The engineering estimate of 39 to 54 hours to the battery is an
estimate, not a delivery rate; engineering hours, guest occupation, unattended
CI and waiting are reported apart.

**What this decision does not do.** It authorises no guest session: the finite
proof, the resumption of the qualifying G3 battery and the G4 pilot each need
the student's separate authorisation, and the pause on the qualifying G3 runs
stays in force. It accepts no gate and admits no claim: a supporting proof
supports the recovery mechanism for that run and qualifies no zero-loss
family, and the proof's named N1 exceptions waive no G3 criterion — those
identities stay `lost` until the separate decision reserved under "What must
change". The submission target stays 2026-10-20, with 2026-10-31 the latest
date and not the working date.

**Decided: option 5, under conditions** (proposed on 2026-09-21, decided on
2026-09-24) — the controller acknowledges each
MQTT delivery only after its outcome line is recorded, on a persistent session
under its existing client id, with the broker's bounds for that session set
explicitly and recorded. The broker becomes the controller's durable inbox; the
controller adds no store of its own. The four gate items admit it only under
the conditions listed below, and rule it out on today's broker configuration
[I1 §8; I3 §10; I4 §8]; r02's guest-side evidence argues nothing against it
[I2 §9].

Neither half works alone: acknowledging late on a clean session loses the
unacknowledged deliveries with the session (option 1), and a persistent session
with today's acknowledgement leaves the larger class in RAM (option 2). r02's
guest-side evidence is consistent with both classes being real: about 1,810
identities left without an outcome line inside the controller (at least 1,809
by arithmetic, PROVED; "received by the old process" CONSISTENT-WITH;
section 1.1), the class that acknowledging after the outcome line addresses,
and about 320 published while no subscription existed (CONSISTENT-WITH, on
recovered bytes; 151 to 327 without them; section 1.3), the class that a
persistent session addresses [I2 §9]. The evidence proves that none of them
obtained an outcome line, not how they divide between the two classes, and the
recommendation does not depend on the recovered bytes. Option 3 with option 2
would give the same recovery with `latency_ms` unaffected even when the backlog
is large, but at an unmeasured per-message durable write on a guest that served
below the offered rate in every observed phase of one run, and as the largest
change of the five; it is held in reserve, not dismissed.

### The conditions option 5 carries

Option 5 carries six conditions and one choice. The six conditions (C1 and C3
to C7) are each part of the decision; none is a follow-up. C2 is a choice
attached to option 5, not a condition: the student makes it or declines it,
and what is lost if he declines it is stated with it. Where a condition leaves
a choice, the choice is the student's and is recorded with the decision.

- **C1. Broker settings, explicit and recorded** [I1 §4, §8]. In
  `mosquitto.conf`: `max_inflight_messages` = W (3,593 ≤ W ≤ 4,999, "The
  in-flight window W" below); `max_inflight_bytes 0`, so that no byte window
  holds the count below W; a finite `max_queued_messages` Q (0, "no maximum", is
  advised against by the manual, [M5] `:680-681`, and was the subject of fixes
  in 2.0.17 and 2.0.22); `max_queued_bytes`, 0 or a recorded value with the
  reading of its unit, which the manual leaves open ([M5] `:659-663`);
  `persistent_client_expiration` in the 2.0.22 grammar — units `h d w m y`, at
  least one hour, `m` a month, never seconds ([M5] `:860-867`);
  `sys_interval` as deployed or explicit. In 2.0.22 all of them are
  global, with no per-listener or per-client form, so they apply to every
  subscriber of the broker [I1 §2]. The run record states that no
  configuration reload happened during the run [I1 §4]. Q and the expiry are
  the student's values; the broker measurement uses Q = 1,000 and 1 h unless
  others are chosen first [I1 §7]. Those two values are what C3 exercised on
  2026-09-23: the candidate's configuration, not a validated expiry — the
  measurement let no session expire ('cannot show', below) — nor a queue
  shown adequate for any outage but r02's 28.5 s at 11.2 msg/s, and that only
  with queue space free when it began; `persistent_client_expiration` is the
  expiry of a disconnected session, not a message lifetime. Being global, the
  values bind every family, the pilot and the campaign (section 3).
- **C2 — a choice attached to option 5, not a condition: broker drops made
  visible at run level** [I1 §3, §8]. If the student makes it, the drop
  counter `$SYS/broker/publish/messages/dropped` and
  `$SYS/broker/clients/disconnected` are made readable and recorded with each
  run, and `clients/disconnected` is checked to be 0, or the expected count,
  before each run. Both are broker-wide and name no client or message
  (`gates/sources/man_mosquitto-8.txt:241-245`, `:342-348`, the mosquitto.org
  page, which documents 2.1.x; [I1 §3] reads the same entries in [M8], which
  is not kept), so reconciliation by identity stays the only per-message
  check. Reading them needs an ACL grant, which changes the configuration that
  test 9(d)/(e) proves and adds an item to the configuration identity; item 4
  treats reading them as a run-level evidence item, not a drain check, and as
  a separate decision [I4 §4, §5.5]. **If the student declines it,** N4's
  run-level drop evidence lapses: a broker drop shows only as a missing
  identity after the run, found by reconciliation by identity. Test 9's proof
  is then unchanged, because the ACL stays as deployed. The broker log is
  no substitute (corrected 2026-09-23, N4): its one `notice` line per client
  per connection marks the transition into dropping, not a count and not a
  run, so declining C2 is a knowing choice — complete broker logs and
  reconciliation by identity kept, counter deltas and the disconnected-client
  pre-check forgone, and a missing identity without an attributable cause
  classified indeterminate, never 'dropped by the broker' by inference. If
  the student requires that attribution, C2 is chosen prospectively with the
  minimum read grant (the two topics) and the affected authorisation test
  revised. The broker measurement
  uses its own measurement-only grant either way [I1 §7].
- **C3. The broker measurement has run on the pinned broker and supported the
  option** ("The broker measurement" below; [I1 §7]), before implementation:
  every condition of its support row holds (S1–S5 of [I1 §7]). Not refuting
  it is not enough. An inconclusive run is not passing: the student decides
  whether to repeat it — the same design, recorded as a repeat, the first run
  kept — or to re-decide the option. A per-device order break in the
  measurement's P7 refutes option 5 as configured, with a window W greater
  than 1; this record classifies it so in advance ("The broker measurement").
  The option then goes back to the student for re-decision, with option 4 as
  the next best, as after any other refutation; an option 5 re-designed around
  an order break needs its own record and is not this one. Until C3 is met,
  "within 128 MiB" is unknown, not assumed [I1 §8], and so is the broker's
  order under the window. **Met on 2026-09-23:** the measurement ran on the
  guest, `20260923T195448Z_broker-hold-measurement-c3_attempt04` (execution
  commit `8e68017`, exported and verified), and every one of S1–S5 held —
  no refutation, nothing inconclusive; three earlier attempts of the same
  session, two stopped by host and guest prerequisites and one inconclusive
  on an instrument artefact, are preserved with it (LOG `#C040`). Its
  figures: 4,999 held with nothing acknowledged; 5,999 held with the
  subscriber away and 100 dropped, the queue counted **above** the in-flight
  window (store W + Q, dropped B − Q) and the drop logged as `Outgoing
  messages are being dropped for client egw-probe-hold.` at the deployed log
  types — one line for 100 drops, the transition into dropping, not a
  count (N4; corrected 2026-09-23); no
  OOM, no restart, peak 12,750,848 bytes, about 771 B of anon per held
  message; all 5,999 redelivered once on the resumed session, DUP = 1 on
  the 4,999, per-device `seq` ascending; the store back at its baseline.
  One run, this guest, this broker as it holds it: the premise is supported
  for that run and proved for nothing more (open item 1).
- **C4. The acknowledgement rule A1–A6** [I3 §7] and the code it implies
  [I3 §8] ("The behaviour this records" and "What must change"). Of the two
  choices this record left open for a delivery that ends without an outcome
  line on a live connection, only ending the connection is kept; holding an
  in-flight slot is excluded [I3 §6]. How the connection ends — A3(a) in
  process, or A3(b) exit and let the container restart — is the student's
  choice, recorded and tested [I3 §7].
- **C5. The `drained` change** [I4 §5, §8]: three additive `/metrics` fields,
  `_mline` and `drained` changed with no threshold, window, limit or message
  prefix changed, the runbook text restated, all **before the proof**; the
  residual assumption of [I4 §5.5] stated in the record. That assumption is:
  a broker with nothing in flight to a session that stays connected holds
  nothing queued for it — ASSUMED from the documented meaning of the queue,
  and testable only on the guest, by the proof's optional extension [I4 §9].
  With the change, `drained` is truthful except for that residual assumption.
- **C6. An explicit `stop_grace_period`, recorded**, covering the message in
  progress, not the backlog. In r02 the engine's 10 s allowance cut the old
  process's drain short [I2 §9]. No permitted source establishes that the
  engine applies `stop_grace_period` to `docker compose … restart controller`
  issued without `-t`, which is how the runbook restarts the controller
  (`qemu_integrated_gateway.md:1123`); *I could not establish* it. The proof
  kills the controller with SIGKILL, so it does not test C6; test 6 of the
  battery is the first place C6 is exercised.
- **C7. Locked Python dependencies**, so that the acknowledgement and session
  behaviour rests on a known paho version (`PROGRESS.md:509`; [I3 §8, item 14]).

### If option 5 is refuted, or its conditions cannot be met before the freeze

**The next best is option 4 — keep today's behaviour and state the limitation —
with option 3 with option 2 kept in reserve.** The reasons, from this record:

- **What option 4 costs:** no code, no broker change, no guest time. `drained`
  stays truthful as it is argued today, because with a clean session the broker
  holds nothing for the controller [I4 §3]. The restart classes are never
  processed: test 6 records identities without an outcome after every restart
  under backlog — in r02, 1,809 to 1,817 that never obtained an outcome line
  (PROVED; whether the one in flight at the kill reached its twin is not
  established) and 319 to 321 never delivered (CONSISTENT-WITH, on recovered
  bytes) (section 1.3) — a negative result reported as such; the G3
  criterion "recovery … and no record accepted twice" is not met on delivery,
  and claim C12 cannot be supported on delivery (option 4 above). Whether
  the zero-lost gate passes at 11.2 msg/s is an unresolved risk under every
  option, option 4 included: the earlier candidate confirmed late in every
  timed run and the changed candidate is unmeasured ("Relationship with the
  throughput problem"); option 4 is not equivalent to a recovery option on
  that gate, it merely leaves the restart classes unprocessed *(corrected
  2026-09-24; this sentence had predicted that the gate fails under every
  option)*.
- **Why not option 3 with option 2 in its place:** it would recover both
  classes (intended), and because it acknowledges after its own local write it
  does not ask the broker to hold the backlog in flight (option 3 above). But
  its per-message durable write, and the `fsync` that guest-loss durability
  would need, are unmeasured on a guest that served below the offered rate in
  every observed phase of one run; it is the largest change of the five; and it
  still carries a persistent session, so it needs C1's queue bound and expiry
  and a `drained` that sees state D1 (option 2 above). It stays in reserve, not
  dismissed.
- **What decides between them after a refutation:** which condition failed. A
  refutation by the broker measurement concerns the broker's hold of a large
  in-flight backlog, or its per-device order under such a window (C3); option 3
  does not ask the broker to hold such a backlog in flight, since it
  acknowledges after its own write. A refutation by the proof's R2, R3 or R4
  concerns the twin-backed rebuild or the broker's order (P4, N5), on which
  option 3's replay through the unchanged pipeline, with idempotence from ADR
  0006, also relies (option 3 above). Either way the refutation is recorded,
  and the choice is re-decided here, never run silently with a smaller window.
  An inconclusive run is not a refutation and not a pass: it is repeated as a
  recorded repeat, or the option is re-decided (C3).

### The behaviour this records

This is the admission, acknowledgement and persistence behaviour selected. Until
the decision is recorded, the broker measurement has supported it (C3) and the
proof has run and supported it, none of it is more than a proposal; even then
it is the behaviour this record proposes, supported by one broker measurement
and one proof run, and it is shown for those runs only.

| aspect | behaviour selected |
|---|---|
| admission | unchanged: a delivery enters the controller's volatile queue (`service.py:150-169`); the controller keeps no local durable copy |
| outcome line (A1) | every delivery the consumer takes ends in exactly one outcome line, a processing error included, with four exceptions only: the event log cannot be written; the consumer is cancelled; the process dies; an exception is raised after the Ditto 2xx for that delivery. A failure while decoding or validating the payload is `rejected`; a failure in the Ditto exchange that is not a `DittoError` is `failed`; any other exception raised before the `PATCH` is sent is `failed`, naming the exception. The unit is the delivery, each copy included [I3 §7]. Without A1, payloads that today raise past the decode stage (a deeply nested document, a 5,000-digit integer, a non-string `device_type`) end with no line [I3 §5, L1; `gates/out/item3_probe.out.txt:4-6`] and under this option would be resent for ever: a poison delivery, W of which stall the controller [I3 §5] |
| acknowledgement (A2, A6) | for a QoS 1 delivery, the PUBACK is requested exactly once, by the consumer, immediately after `EventLogger.log` for that delivery has returned without raising (`service.py:414`; `events.py:112-119`), and before the consumer takes the next delivery; never for a QoS 0 delivery, and never for a delivery with no line. The bridge is ready only when the SUBACK grants QoS 1, since a QoS 0 grant would silently disable every acknowledgement [I3 §7] |
| order (A3) | on each connection the PUBACKs sent form a gap-free prefix of that connection's QoS 1 deliveries in receipt order, as MQTT 3.1.1 requires ([MQTT-4.6.0-2]; [I3 §2]). The first delivery that cannot be acknowledged — one of A1's four exceptions, an overflow, a callback without an event loop — ends acknowledgement on that connection, and the controller ends the connection, so that the broker resends every unacknowledged delivery at the next session resumption ([MQTT-4.4.0-1]). Either **A3(a)**, in process: stop taking deliveries, `disconnect()`, `loop_stop()`, `connect_async()`, `loop_start()`, with a back-off and `/ready` false meanwhile; or **A3(b)**, fail fast: stop taking deliveries, disconnect and exit non-zero, leaving the restart to `restart: unless-stopped` (`compose.yaml:256`), which reuses the path the proof exercises — what the engine does on a non-zero exit is not established [I3 §7, §9]. The student chooses; the choice is recorded and tested. Holding an in-flight slot until the next resumption is **excluded**: it leaves the protocol's duty to answer every QoS 1 PUBLISH unmet for the life of the connection, nothing recovers the delivery while the connection lasts, and a deterministic failure fails again at every resumption [I3 §6] |
| connection scope (A4) | every delivery carries the identity of the connection that delivered it, stamped on the network thread; that identity advances in `on_socket_close`, which paho runs on every close path before it clears its queued packets; checking the identity and queuing the PUBACK happen under one lock that the close callback also takes, so no PUBACK for an ended connection reaches the next one. Deliveries of an ended connection are purged from the queue; the one in progress completes, obtains its line and is not acknowledged [I3 §4.5, §7] |
| a persistent cause (A5) | a cause that repeats A3 (the event log unwritable) ends in a visible state, not a silent reconnection or restart loop: each occurrence recorded, the repetition bounded, `/ready` false while outcomes cannot be recorded [I3 §7] |
| persistence | the broker's persistent session for client id `egw-controller-{EGW_ID}`, with `persistence true` and `autosave_interval 60` as today; the window, the queue bounds, the byte limits and the session expiry set explicitly in `mosquitto.conf` as condition C1 states, and recorded with every run; they apply to every subscriber of the broker [I1 §2] |
| graceful stop | stop taking messages after the one in progress, record it, send its PUBACK, then disconnect; the rest of the queue is abandoned unacknowledged, for redelivery to the next process. Today's drain after the disconnect is removed: once disconnected, no PUBACK can be sent, so draining would only produce `duplicate` records later |
| kill | nothing runs; every delivery without a PUBACK stays with the broker |
| restart | the new process connects under the same client id with a persistent session; the broker resends the unacknowledged deliveries and those queued while the controller was away; they pass through the unchanged pipeline, where each device's duplicate state is rebuilt from its twin on its first message (ADR 0006) |
| stop allowance | an explicit `stop_grace_period` for the controller in `compose.yaml`, recorded; it has to cover the message in progress, not the backlog. In r02 the engine's 10 s allowance applied and cut the drain short (section 1.5; [I2 §9]) |
| drain precondition | `/metrics` carries three additive fields — `mqtt_subscribed`, `mqtt_connection` (successful CONNACKs of this process) and `unacked` (QoS 1 deliveries handed to the client on the current connection without a PUBACK, counted by the bridge at `on_message`) — and `drained` treats a reading as quiet only when `queue_depth`, `in_progress` and `unacked` are all 0, `mqtt_subscribed` is true and the accounting identity holds, with `started_at`, `mqtt_connection`, `received`, the four outcome counters, `dropped` and `processing_errors` unchanged across the window; `DRAIN_QUIET_S`, `DRAIN_STEP_S`, `DRAIN_LIMIT_S` and both output prefixes unchanged [I4 §5.1, §5.2] |

**The in-flight window W.** W must be at least the largest number of
deliveries the controller is expected to hold during a family run, so that the
wait stays where `latency_ms` stamps it. This record first bounded it by
2W ≤ 9,999, so that a reconnection inside one process — which, on a persistent
session, may resend every unacknowledged delivery while the originals are still
queued — could not overflow the 10,000-slot queue together with the shutdown
marker (`service.py:39`; `src/CONTRACTS.md:279-281`). That bound covers one
reconnection, not two: without a purge the queue can hold (*k*+1)·W after *k*
reconnections; with A4's purge it holds at most W plus the marker [I3 §5 L7,
§8]. The range 3,593 ≤ W ≤ 4,999 is kept: it is the range the broker's
documentation was read against, and the broker measurement tests W = 4,999; a
backlog larger than 5,999 is beyond what that measurement can show [I1 §7]. The
one observation available, 3,593 inside the controller at the end of
`nominal-r01` [F:N.3], lies inside that range. It is one failed run's figure,
not a bound, and it grows with the length of any run the stack does not keep up
with.

What the deployed broker (`eclipse-mosquitto:2.0.22`,
`src/deployment/images.lock.env:39`) does with such a window [I1 §0, §4]:

- **It can be configured.** The 2.0.22 manual (`mosquitto.conf(5)` as released
  with 2.0.22, entries `max_inflight_messages` and `max_queued_messages`,
  [M5] `:572-584`, `:676-688`) states no upper bound for either, and MQTT
  3.1.1's 16-bit packet identifier caps a window at 65,535 per direction; so the documentation states, and
  that the broker honours such a window has not been observed [I1 §0, §4].
- **Today it is not.** The deployed file sets neither option, so the
  documented defaults apply: 20 in flight plus 1,000 queued, 1,020 held at most,
  2,573 short of 3,593 and 3,979 short of 4,999; beyond them the broker drops.
- **Whether it honours W, and within 128 MiB, is not established.** No
  per-message memory cost is documented; only a guest measurement can answer
  (C3). Until it has, "within 128 MiB" is unknown, not assumed [I1 §8].

**The queue bound Q** has to hold what arrives while the controller is away —
in r02's restart, 319 to 321 publications over the 28.5 s in which no
subscription existed, on the recovered broker lines [I2 §6, §9] — and, if the
broker counts the in-flight deliveries it holds against Q while the client is
offline, W plus that outage [I1 §4]. Which of the two the broker does *I could
not establish* from its documentation; the broker measurement discriminates
[I1 §3, §7]. The new process in r02 needed 14.8 s from container start to its
subscription [I2 §9]. If the broker cannot hold W and Q, the option is
re-decided, never run silently with a smaller window.

### What it would promise — once decided, implemented, and supported by the broker measurement and the proof

- **P1.** For every QoS 1 delivery the controller receives, the PUBACK is sent
  after the delivery's outcome line is in `events.jsonl`, never before.
- **P2.** A delivery for which no outcome line is written — A1's four
  exceptions (the process killed, the consumer cancelled, the event write
  failing, an exception after the Ditto 2xx), the queue full, no event loop —
  is not acknowledged, and the broker delivers it again at the controller's
  next session resumption. On a live connection the controller forces that
  resumption itself by ending the connection (A3) [I3 §8]. The broker is not
  required to resend on a live connection ([MQTT-4.4.0-1]), and Mosquitto's
  `ChangeLog.txt`, release 1.5, is CONSISTENT-WITH its not doing so; that
  entry names QoS greater than 1, and whether it covers QoS 1 *I could not
  establish* [I1 §6; I3 §3].
- **P3.** While the controller is disconnected, the broker keeps its
  subscription to `c2dt/+/+/telemetry`, queues publications for it and
  delivers them on reconnection, up to the configured and recorded queue bound
  ([MQTT-3.1.2-5]; [I1 §3]).
- **P4.** A delivery redelivered after its effect has already reached the twin
  is **intended** to be classified `duplicate` by the unchanged rule once the
  duplicate state is rebuilt from the twin, and no twin state is intended to
  regress. This is the least supported of the five today (section 1.6); the
  proof exists to test it.
- **P5.** `latency_ms` keeps its meaning — MQTT callback to Ditto 2xx, ADR 0005
  — for every first delivery received while the in-flight window was not full;
  each run records whether and when it filled. It does **not** keep it for a
  redelivered delivery: `received_monotonic_ns` is stamped when the redelivery
  arrives (`mqtt.py:189`), so its `latency_ms` excludes the time the message
  spent in the killed process and at the broker. Redelivered identities are
  reported apart from first deliveries. The deadline verdict, which compares
  absolute stamps, is unaffected.

### What it does not promise

- **N1. Not exactly-once.** A death between the Ditto 2xx (`service.py:320`) and
  the line (`:414`) leaves the twin advanced and no line. The redelivery is
  `duplicate`, the identity never obtains an `accepted` record, and
  `analyze.py` reports it `lost` (2i). A death is not the only source. A1's
  fourth exception — an exception raised after the Ditto 2xx, a failed event
  write after the `PATCH` included — also leaves the twin advanced with no line;
  A3 then ends the connection, the redelivery is `duplicate`, and the identity
  is counted `lost` [I3 §5 L3, L11]. So there is at most one such identity per
  death, or per connection ended under A3 after a `PATCH`, since there is one
  consumer.
- **N2. Not the absence of `duplicate` records.** A death after the line and
  before the PUBACK leaves the identity with its `accepted` record and, later,
  a `duplicate`; a reconnection inside one process can produce `duplicate`
  records too — with A4's purge, at most one per lost connection, from the
  delivery in progress [I3 §7, §8]. Neither is a double acceptance. An event write that fails at `flush()` today
  keeps the line in Python's buffer, and a later successful flush writes it
  [I3 §5 L3; `gates/out/item3_probe.out.txt:14-15`], so a failed first line
  could add a second line for the identity; the event-log change of "What must
  change" removes that path.
- **N3. Not durability against a broker restart or a guest loss.** The broker's
  store is written every 60 s (`mosquitto.conf:33-35`; its comment at `:30-31`
  states the intent that in-flight and queued state survive broker restarts).
  What a broker crash, a broker stop or a guest power loss loses *I could not
  establish*. The event log is flushed, not synced (`events.py:112-119`).
  **Beside N3, NOT ESTABLISHED: a stale snapshot could also bring deliveries
  back.** The 2.0.22 manual says the store is written when the broker closes
  and at every `autosave_interval` ([M5] `:795-806`, `:308-316`), 60 s as deployed
  (`mosquitto.conf:35`). Under a persistent session, after a broker crash or a
  guest power loss, a snapshot up to 60 s old could therefore bring back
  deliveries that the controller had already acknowledged, and they would
  appear as `duplicate` lines in a later run. This is an inference from the
  documented behaviour, not an observation; no run has shown it.
- **N4. Not unbounded retention.** Beyond the configured queue bound the broker
  discards. The 2.0.22 manual calls the drop "silently dropped" only for the
  byte limit, `max_queued_bytes` ([M5] `:659-663`), which is unlimited by
  default; under the defaults the bound is the count, `max_queued_messages`,
  whose entry says nothing of silence or of a log line ([M5] `:676-688`). The
  change log records, in release 1.3, that the broker logs when outgoing
  messages for a client "begin to drop off the end of the queue" ([CL]
  `:2661`, `:2679-2680`); [I1 §3] says no such line is stated in [CL], which
  is wrong for [CL]. Whether 2.0.22 still logs it, at which log type, and
  whether the deployed log types (`mosquitto.conf:48-53`: `error`, `warning`,
  `notice`, `information`, `subscribe`, `unsubscribe`) include that type was
  **NOT ESTABLISHED** until 2026-09-23. **Established on 2026-09-23** by
  attempt04 and by the tagged v2.0.22 source: the broker logs `Outgoing
  messages are being dropped for client <id>.` at `notice`, which the deployed
  types include, **once per client at the transition into dropping**
  (`src/database.c:521-549`, flag `is_dropping`), clears the flag only at that
  client's next CONNECT (`src/handle_connect.c:253`), and increments the
  broker-wide counter for every drop (`G_MSGS_DROPPED_INC`, published as
  `$SYS/broker/publish/messages/dropped`, `src/sys_tree.c:338`); attempt04 saw
  one line for 100 drops. The line proves at least one drop for its named
  client since its last CONNECT — never how many, and never per run: a later
  run on the same connection can drop without a new line, and no line is not
  proof of zero drops. Under option 5 the controller keeps one connection
  across runs, reopened only on a restart or under A3. The
  drop is counted in the broker-wide `$SYS/broker/publish/messages/dropped`,
  which names no client and no message (`gates/sources/man_mosquitto-8.txt:342-348`,
  the 2.1.x page; [I1 §3]). The controller cannot see that it did. With C2 the
  run record shows that a drop happened and how many; if the student declines
  C2, that run-level evidence lapses and the log's transition line does not
  replace it. Either way reconciliation by identity shows which identity is
  missing; without C2 a missing identity whose cause cannot be attributed is
  indeterminate.
- **N5. Not ordering beyond the broker's.** P4 assumes that the broker resends a
  device's deliveries in publication order. A later `seq` accepted before an
  earlier one would make the earlier one `duplicate` although never applied
  (`dedupe.py:103-112`). MQTT 3.1.1 requires re-sent PUBLISH packets in their
  original order and same-topic delivery in the order received
  ([MQTT-4.6.0-1], [MQTT-4.6.0-5], [MQTT-4.6.0-6]; [I3 §2]); that the deployed
  broker does so is ASSUMED. The 2.0.22 manual states in-order delivery only
  for a window of 1 (`max_inflight_messages` set to 1, [M5] `:578-580`), and
  states nothing of the kind for W = 4,999. Observed by the broker
  measurement (per-device order on redelivery [I1 §7]), where an order break
  refutes option 5 as configured (C3), and tested by the proof, not promised.
- **N6. Not a change in throughput.** The served rate is unchanged except by the
  unmeasured cost of the `ack` call and of the `unacked` counter updates
  [I4 §6].
- **N7. Not a deadline pass** for any timed family — see "Relationship with the
  throughput problem".
- **N8. Not a valid `controller_restart` run.** The ingest rule
  `MAX_SAMPLE_GAP_S = 5.0` (`src/egw_experiments/protocol.py:112`) rejected both
  restart runs' resource files: r02's for one 6.0 s gap at the restart
  [F:R02.0]; r01's for seven gaps over 5 s, among them the 9.0 s gap at the
  restart and 6.0 s gaps from 21:59:30Z to 21:59:36Z in both the controller and
  `ditto-gateway`, about four minutes after the restart command
  (21:55:22.583Z) [F:R01.0]. The lifecycle-aware rule for the deliberately
  restarted container is proposed and not adopted
  (`qemu_integrated_gateway.md:1138`), and it would not by itself have made
  r01's file admissible. Whether a collector sampling at a true 1 Hz would keep
  the gap under the limit is unresolved (r02's 6.0 s gap was recorded at
  0.83 samples/s [F:R02.6]).
- **N9. Nothing about the past runs.** r02's in-flight identity stays as
  section 1.6 leaves it; the end-of-run blocks of both restart runs were
  settled by the guests' own event logs (late, not lost), not by this option.
- **N10. Nothing at all until the decision is recorded, the broker measurement
  has supported it (C3), and the proof has run and supported it.** An
  inconclusive run of either supports nothing.

### Ordering, duplicates, durability and configuration identity

The project manager's standing condition for any change to concurrency or to
resource limits (`PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`,
section 5, item 2). This option adds no concurrency, but it does set broker
limits, so all four are addressed here.

- **Ordering.** One FIFO consumer, unchanged; the order per device then depends
  only on the broker's delivery and redelivery order (N5). The proof checks,
  device by device, that no `duplicate` hides a `seq` the twin had not
  covered. The acknowledgement order follows by construction, to be pinned by
  the regression tests ("What must change", tests) [I3 §1, §6]: MQTT 3.1.1
  requires a client to send its PUBACKs in the order in which it received the
  QoS 1 PUBLISH packets ([MQTT-4.6.0-2]) and to answer every one of them
  ([MQTT-4.3.2-2], [MQTT-4.5.0-2]), and permits the PUBACK to follow the
  application's processing (section 4.3.2, note to Figure 4.2). With one FIFO
  consumer that requests each PUBACK right after the delivery's outcome line
  and before taking the next, the PUBACKs of one connection leave in receipt
  order by construction — paho-mqtt 2.1.0 writes them in the order `ack()` is
  called (`client.py:3776`, `:3163`) — provided no delivery is skipped, which
  A3 provides for by ending the connection at the first delivery that cannot
  be acknowledged. This is reasoning about code not yet written. How
  Mosquitto 2.0.22 treats a PUBACK out of receipt order *I could not
  establish*; under A3 the controller never sends one [I3 §3, §6].
  paho-mqtt 2.1.0 states that under manual acknowledgement "the caller MUST
  manually acknowledge every message" (`client.py:4180-4181`) [C]; its `ack()`
  checks nothing — not that the identifier was delivered, is outstanding, or
  belongs to the current connection — so order, completeness and connection
  scope are the controller's (A2–A4) [I3 §4.2]. Any future concurrent consumer
  would complete deliveries out of receipt order and would need an
  acknowledgement sequencer releasing only the completed prefix [I3 §6].
- **Duplicates.** Expected and bounded (N1, N2); detected by ADR 0006,
  unchanged; `double_accepted` must stay 0 (`analyze.py:1780-1787`).
  Acknowledgements are scoped to the connection on which the delivery arrived
  (A4): after a reconnection inside one process, a delivery that arrived on the
  earlier connection is not acknowledged; the broker resends it and the resent
  copy is acknowledged. The reason: MQTT 3.1.1 makes a packet identifier
  reusable once the sender has received its PUBACK ([MQTT-4.3.2-1],
  [MQTT-2.3.1-3], [MQTT-2.3.1-4]; [I3 §2]), so a late PUBACK carrying an old
  identifier could release a different message that has not been processed;
  and paho discards PUBACKs queued but not yet written when it reconnects, and
  sends one queued after that point on the new connection with its old
  identifier (`client.py:1577`; [I3 §4.5]).
- **Durability.** As N3; the event log's durability is unchanged.
- **Configuration identity.** The broker values of C1 and `stop_grace_period`
  live in versioned files whose hashes go into the manifest, with the statement
  that no reload happened during the run (each option is reloaded on the
  reload signal) [I1 §4]; with C2, the ACL grant is part of that identity and
  the `$SYS` readings go with each run [I1 §8; I4 §4]. The window and queue
  options are global, so they are part of every family's configuration, not
  only the controller's [I1 §2]. A persistent session that never returns — a
  retired `EGW_ID`, or a probe left under a persistent session — accumulates
  every later matching publication up to its queue bound and then raises the
  broker-wide drop counter for ever, masking the controller's own drops;
  `persistent_client_expiration` (at least one hour in 2.0.22) bounds this, and
  so does checking `$SYS/broker/clients/disconnected` before each run [I1 §3]
  (`gates/sources/man_mosquitto-8.txt:241-245`, the 2.1.x page).
  The controller
  image's id and source commit go into the manifest (the deployment already
  names them as the image's identity, `compose.yaml:251-252`), and the Python
  dependencies are locked — today they are not (`PROGRESS.md:509`) — so that
  the session and acknowledgement behaviour rests on a known paho version
  rather than a library default. `EGW_ID` must be unique per deployment: the
  client id is the session's identity, a second controller under the same id
  would take the session over (ASSUMED from the protocol), and a retired id
  leaves a session at the broker until the configured expiry.
- **Contamination across runs.** A delivery left unacknowledged while the
  controller stays connected is not resent until the next session resumption:
  MQTT 3.1.1 requires redelivery only then ([MQTT-4.4.0-1]), and Mosquitto's
  change log records that outgoing messages are no longer retried after a
  timeout, only on reconnection (release 1.5) — CONSISTENT-WITH no resend on a
  live connection; whether that entry, which names QoS greater than 1, covers
  QoS 1 *I could not establish*, and the broker measurement observes it
  directly [I1 §6, §7; I3 §3]. Such a resumption may fall inside a later run,
  where the twin patch would land between that run's before and after
  snapshots and appear as a `delta` mismatch. Two conditions close this. A3
  ends any connection on which a delivery cannot be acknowledged, so no
  delivery stays unacknowledged on a live connection [I3 §7]. And `drained`
  changes (C5): under a persistent session it could otherwise report a quiet
  window in D1 or D2 while the broker holds deliveries for the session, and
  Mosquitto 2.0.22 exposes no per-session queue figure from which a truthful
  check could be built [I4 §0, §3, §4]. The refusal of `processing_errors` or
  `dropped` above zero, which this record first proposed on its own, is not
  sufficient: it misses D1 [I4 §5.2]. What the changed `drained` still does not
  show is a message queued at the broker and never sent to a connected
  controller with nothing in flight; that none is held rests on the documented
  meaning of the queue and is **ASSUMED** [I4 §5.5]. Whether a false quiet
  window can only ever produce a false `MISMATCH`, never a false `OK`, *I could
  not establish* [I4 §3, §10].

---

## The broker measurement (condition C3)

**An engineering diagnostic, not a G3 run.** One bounded run of the pinned
broker alone, designed in full in [I1 §7] and summarised here. It is not a
repetition of any run and changes no threshold, load, deadline or rule. It
needs no controller change, no image rebuild and no Ditto [I1 §7], so it can
run before implementation starts — and, if the student prefers to decide on
its result, before the decision. Like every guest session from now on, it runs only
after r02's residual evidence has been preserved ("Open items", item 2).

| | |
|---|---|
| question | does the pinned broker, with the candidate values, accept and honour W = 4,999; hold 4,999, then 4,999 plus a queue, of real-sized QoS 1 messages for a non-acknowledging persistent session without drops and within 128 MiB; show a drop when its queue is full, and where; and keep and redeliver the held messages, in per-device order, after the subscriber is killed? |
| set-up | the deployed stack stopped; a throwaway container of the pinned image with `--memory 128m` (as `compose.yaml:87`) on port 8883, the deployed certificates and password file, a measurement copy of `mosquitto.conf` (the deployed file plus `max_inflight_messages 4999`, `max_inflight_bytes 0`, `max_queued_messages 1000`, `max_queued_bytes 0`, `persistent_client_expiration 1h`, or the student's values) and of `acl` (plus a measurement-only `$SYS` read grant), each hashed; a fresh volume, removed at the end, never the deployed `mosquitto-data` |
| clients | a publisher of regenerated real payloads (273 to 320 B) at 11.2 msg/s; a holding subscriber under its own client id `egw-probe-hold` (never the controller's), persistent session, manual acknowledgement, not acknowledging until the last phase; a `$SYS` reader; a 1 s recorder of the broker container's memory counters and `memory.events` |
| phases | baseline; 4,999 published with the subscriber connected and silent; a hold of 130 s (two autosaves; any resend with DUP = 1 on the live connection is recorded); SIGKILL of the subscriber; 1,100 more published while it is away — which tells whether Q counts above or including the held in-flight messages (store 5,999 and 100 dropped, or store 4,999 and 1,100 dropped; the store read from `$SYS/broker/store/messages/count`, `gates/sources/man_mosquitto-8.txt:407-411`, the 2.1.x page); a hold; reconnection with acknowledgement (phase P7 of [I1 §7]) until the store returns to its baseline (limit 300 s) |
| supports option 5 on the broker side | all of (S1–S5 of [I1 §7]; C3 is met only when every one holds): the broker starts with the added lines and logs no configuration error; the subscriber holds 4,999 distinct unacknowledged deliveries; no drop up to the kill, and every one of the first 4,999 redelivered; no OOM, no broker restart, the peak memory reported with its margin and split into `anon` and `file`, and a per-message figure for this run; every message held at the end redelivered in per-device order |
| refutes option 5 as configured | any of: the configuration refused; fewer than 4,999 distinct deliveries held; a drop while at most 4,999 are held; an OOM or a broker restart; fewer messages redelivered than the store held; a per-device order break in P7 — the first copy received in P7 of each held message not in ascending `seq` for its device. The last is classified here in advance, where [I1 §7] had recorded it as not refuting by itself: the 2.0.22 manual states in-order delivery only for a window of 1 ([M5] `:578-580`), W here is greater than 1, and P4, N5 and the proof's R3 depend on that order. It sends the option back to the student for re-decision (C3) |
| recorded, not refuting by itself | the "in total" accounting (a sizing finding: Q re-sized before implementation); page-cache reclaim without OOM; any resend with DUP = 1 on the live connection; whether, and at which log type, the broker logs a drop (N4) |
| inconclusive | `$SYS` unreadable; a recorder gap over 5 s; the publisher off its exact counts; no disconnection line after the kill; a tunnel failure; the last phase reaching its limit; a stop rule of the next row reached. An inconclusive run is not passing and C3 is not met: the student decides whether to repeat it — the same design, recorded as a repeat, the first run kept — or to re-decide the option |
| guest time | about 15 to 19 minutes of measurement (6,099 messages, 544.6 s of publication; 884.6 s with the last phase at 30 s, 1,154.6 s at its 300 s limit, the final 30 s phase included) [I1 §7], plus the stop and restart of the deployed stack: on the one recorded stop (15.9 s) and the one recorded restart (228.7 s) of the whole stack under TCG, about 19 to 23 minutes in all, plus the probe broker's start, which is not recorded — a planning figure, not a bound; Ditto's start under TCG is unverified in general (`qemu_integrated_gateway.md`, Appendix B item 9) [I1 §7] |
| ceiling | about 45 minutes, made of the phases' own limits (1,154.6 s) and two **stop rules imposed by design, not measured durations**: the deployed stack stopped and the probe broker started within 5 minutes (the one recorded stop of the stack, with `stop -t 60`, took 15.9 s: `docs/evidence/g2-complete-flow/20260920T231756Z_guest-session_attempt02/commands.jsonl:5`); and the stack healthy again within 20 minutes of its restart (the one recorded restart of the whole stack under TCG, `compose down` then `up -d`, took 179.1 s, and readiness and health followed in 23.0 s and 26.5 s, 228.7 s in all: `docs/evidence/g2-complete-flow/20260920T233212Z_g2-twin-persistence-restart_attempt01/commands.jsonl:7-9`; the runbook's earlier estimate of tens of minutes is marked unverified, `qemu_integrated_gateway.md:502`). If a stop rule is reached, the session stops and the measurement is recorded inconclusive. The student may set other values before the session; the values used are recorded before it starts |
| cannot show | the connected-queue overflow at W + Q; expiry; a broker crash or restart, or a guest loss (N3); anything about the controller, its `ack` cost, Ditto or latency; any other rate, or a backlog above 5,999; native hardware |

[I1 §7]. A refutation is recorded, and option 5 is re-decided ("If option 5 is
refuted …"). Only a run in which every condition of the support row holds
meets C3; an inconclusive run is repeated or the option re-decided, never
taken as passing. One run supports the broker-side premise for that run only.

---

## The finite proof

**An engineering diagnostic, not a G3 run.** One bounded diagnostic run. It is
not a G3 qualifying run, not a repetition of `nominal-r01` or of
`controller_restart-r01..r03`, and not a campaign, soak or pilot; it changes no
threshold, deadline, load or rule. It runs only after the broker measurement
has supported the option (C3), after the change — the `drained` change included
(C5; [I4 §7]) — and its regression tests are merged, and after the candidate is
built.

| | |
|---|---|
| identity | a fresh run id recorded as a diagnostic, in a one-entry diagnostic plan of its own — the harness refuses a run id absent from its plan (`src/egw_experiments/run.py:2983`) — never an edit of the pilot plan |
| candidate | the controller image rebuilt from the recorded commit that carries the change, with the recorded broker configuration; every other image unchanged |
| load | the `nominal` scenario at 11.2 msg/s, three wearables, no warm-up, 300 s of publication = 3,360 messages [F:P.1] |
| fault | at t+150 s, SIGKILL of the controller's container followed by a start, issued through the harness restart hook (`--restart-cmd`, `--restart-at-s`) so that both instants are in the manifest |
| why this rate and instant | the property concerns deliveries in flight at a kill. The two earlier runs at this rate held 818 (r01) and 988 (r02) queued at t+150 s [F:R01.10, R02.10], so the kill is expected — not guaranteed — to find several hundred deliveries unacknowledged in the controller. No criterion below involves timing, so the served rate does not size this run |
| why SIGKILL | it is the case in which no controller code runs, and the one r02 ended in: its stop was forced 10 s after signal 15, with exit status 137 (section 1.5, PROVED from the guest's journal). The graceful path is covered by regression tests and exercised by test 6 in the battery |
| after publication | the runbook's `drained` helper as changed under C5 (`qemu_integrated_gateway.md:653-654`: quiet window 130 s by default; 490 s where a first-contact message may be in progress, `:651`), then the fetches listed below. With today's `drained`, states D1 or D2 after the kill could give a false quiet window, and the missing identities would be recorded as a refutation that is never re-run away; with the change the same state ends as inconclusive, so the change comes before the proof [I4 §7] |
| guest time | about 17 to 29 minutes as a planning figure: quiet window + 300 s + the unchanged 60 s confirmation wait + a drain no longer than the 405.4 s that `nominal-r01`'s larger backlog took + quiet window [F:P.2, N.3]. Planning ceiling 36 minutes with the helper's default limits (900 + 300 + 60 + 900 s) [F:P.3]. It is not a hard bound: it excludes the `/ready` wait, the restart command's own duration (22.7 s in r01, 20.8 s in r02 [F:R01.0, R02.0]), each `drained` reading's `curl` time, the fetches and the snapshots. An attempt that reaches a limit is recorded as incomplete |
| ceiling | about 70 minutes, set by two **stop rules imposed by design, not measured durations**: the stack with the candidate healthy within 20 minutes of its start (as for the broker measurement, and on the same records), and the attempt stopped 50 minutes after its first `drained` starts — the 36 minutes of the helper's limits plus 14 minutes for what that figure excludes. If a stop rule is reached, the session stops and the proof is recorded inconclusive. The student may set other values before the session; the values used are recorded before it starts |
| not guest time | the code, contract and test changes below, which come first and are the larger part of the work |
| optional extension | item 4's bounded check of the residual assumption of `drained` [I4 §9]. Its question: with nothing published, does a broker with nothing in flight to a connected persistent session hold nothing queued for it? At the end of the run, after the changed `drained` has returned quiet and the post-drain fetch has been taken, one more controller restart under the same client id and persistent session and one more `drained`, with nothing published; about 2.5 to 3 minutes as a planning figure. **Refutes** the assumption if the new process receives any delivery (`received > 0`), or if an identity gains its first outcome line after the first quiet window. **Inconclusive** if the restart is not shown (`started_at` unchanged) or `/ready` is not reached, if its `drained` reaches its limit, if a fetch fails, or if the stop rule below is reached; nothing is then claimed about the assumption. **Ceiling** the `stop_grace_period` recorded under C6 plus 1,660 s, about 28 minutes plus that period, as [I4 §9] sets it out from the helpers' own limits and two stop rules imposed by design, not measured durations: the restart command within the grace period plus 5 minutes (the restart commands of r01 and r02 took 22.7 and 20.8 s [F:R01.0, R02.0]); `wait_ready` at most about 95 s; one `drained` at its limit, `DRAIN_LIMIT_S` = 900 s (`qemu_integrated_gateway.md:654`), read as at most about 935 s; one `/metrics` reading of at most 30 s; and the second fetch within 5 minutes. If the extension has not ended within that time, it stops and is recorded inconclusive. It changes the proof's plan, so it is the student's decision; it is not needed to decide |

**The question.** With deliveries unacknowledged inside the controller when its
process is killed, does every published identity obtain an outcome once the
redelivered backlog has drained — with no identity accepted twice, and no
identity classified `duplicate` whose effect the twin did not already carry?

**What it records.** Items 1 to 3 and 6 exist in no restart run today.

1. `controller_metrics.csv` with `received`, `in_progress`,
   `processing_errors`, `started_at` and `uptime_s` — returned by `/metrics`
   (`metrics.py:162-181`) and discarded by the sampler
   (`controller_metrics.py:53-64`) [C] — and the three fields added under C5,
   `mqtt_subscribed`, `mqtt_connection` and `unacked` [I4 §5.1]. This takes up
   the first follow-up of ADR 0010, which listed recording those fields as a
   separate change.
2. The broker's log (`docker compose logs mosquitto`, as test 5 already
   collects it), the controller container's log and `docker events` for the
   controller over the run, fetched into the run directory. The broker already
   logs connections with one-second timestamps (`mosquitto.conf:47-56`); the
   controller already logs `MQTT disconnected` (`mqtt.py:182-183`) and
   `MQTT subscription granted; bridge ready` (`:151-152`).
3. Twin snapshots before and after, and two event copies kept apart: the
   harness fetch and a post-drain fetch.
4. The configuration identity: the broker configuration's hash and its C1
   values, the statement that no reload happened, `stop_grace_period`, the
   choice made under A3, the controller image's id and source commit, and the
   paho version installed in it; with C2, the ACL's hash and the `$SYS` drop
   and disconnected-client readings before and after the run [I1 §8].
5. `sent_events.jsonl`, `events.jsonl`, the collector file and the manifest, as
   today.
6. Every connection end under A3 during the run — its instant, its cause (one
   of A1's four exceptions, an overflow, or a callback without an event loop)
   and the identity in progress at that moment — as A5 requires each
   occurrence to be recorded [I3 §7], so that an N1 case caused by an A3
   connection end is named and not read as R3.

**What the result reports.** By identity after the drain, and separately for
the restart classes and for every other valid identity: how many ended
`accepted`, `duplicate`, `failed` and `rejected`. The *restart classes* here
are the valid identities published before the kill that have no outcome line
written before it, and those published while the controller was away. Under
A1 a `failed` line also covers a processing error raised before the `PATCH`
("What must change", contracts and records), so an outcome line of any kind is
not recovery ("recovered", under the options table).

**Result that supports the property** — all six, evaluated by identity after
the drain. Only a run in which all six hold supports the option; a run that
merely refutes nothing does not:

- **S1.** The kill found work: the last reading before it shows
  `queue_depth + in_progress > 0`.
- **S2.** Every published valid identity has at least one outcome line in the
  post-drain copy; and every valid identity of the restart classes ends with an
  `accepted` line, or is a named N1 case of S4. A restart-class identity whose
  only lines are `failed` does not support the option (see "Inconclusive").
- **S3.** No identity has two `accepted` lines (`double_accepted = 0`).
- **S4.** Every identity with a `duplicate` line either also has an `accepted`
  line, or is a named N1 case. An N1 case has one of two sources, and the
  result names each case with its source **and with the twin's evidence that
  the identity was applied**: the identity in progress at the kill, or the
  identity in progress at a connection ended under A3 after its `PATCH`
  (item 6); and, on that identity's device, the post-drain twin snapshot's
  `accepted_count` exceeds the device's `accepted` lines by exactly the
  number of N1 cases named on it, with the twin's `last_seq` not below the
  identity's `seq`. Being in progress is not enough: an identity whose
  `PATCH` was never sent, redelivered after a later `seq` of its device had
  been applied, would also end with only a `duplicate` line — that is the
  order break R3 exists to detect, not an N1 case. Without the surplus the
  identity was not applied and R3 applies *(added 2026-09-24, from the
  review of the published record)*.
- **S5.** The runbook's `delta` is `OK` for every twin (`qemu_integrated_gateway.md:1130`),
  except, on the device of each named N1 case of S4, a difference of exactly
  one per such case — the difference S4 requires as the case's evidence,
  not merely permits.
- **S6.** `max(queue_depth + in_progress)` stayed below W — or the result
  states that the window filled, and from when (P5).

**Result that refutes the option as configured** — any one:

- **R1.** After a completed drain, a published valid identity has no outcome
  line.
- **R2.** An identity has two `accepted` lines.
- **R3.** An identity has only `duplicate` lines and is not a named N1 case of
  S4 (in progress at the kill, or at an A3 connection end listed under item 6,
  **and** shown applied by the twin's surplus of S4): a genuine message was
  rejected, through the ordering of N5 or a wrong rebuild.
- **R4.** A `delta` mismatch beyond S5's named cases, or a twin whose
  `last_seq` regressed.

A refutation is a result: it is recorded and preserved, never re-run away.

**Inconclusive** — the attempt is preserved as incomplete and no result is
claimed: the kill found nothing in flight (S1 fails); a `drained` call reaches
its limit; any fetch listed above fails; a stop rule of the ceiling is
reached; or, when none of R1 to R4 holds, a restart-class identity ends with
only `failed` lines, which the result names with the error each line records.
An inconclusive run is not
passing: the student decides whether to repeat it — the same design, recorded
as a repeat, the first run kept — or to re-decide the option, as under C3.

**What it cannot show, even if it supports the option.** One run supports the
property for that run; it does not prove it in general. It says nothing about
the graceful stop (regression tests), a broker restart or a guest loss (N3), any other load
or duration, latency, throughput, or the validity of a `controller_restart` run
under the ingest rule (N8). The harness may again mark the run invalid under
`MAX_SAMPLE_GAP_S`; that verdict belongs to the campaign rules and is kept as
recorded, while the proof's answer comes from reconciliation by identity,
which that rule does not touch.

---

## What must change

Listed as work; no code is written here. Line numbers are at `35fe8bb`. The
first list of this record had ten code items; the four gate items bring it to
twenty. Each item names where it comes from: "first list" for the ten, or the
gate note.

**Code — the controller**

1. `src/egw_controller/mqtt.py:73-76` — a persistent session and manual
   acknowledgement, both in the constructor, never through `manual_ack_set`
   while connected; the client id (`:75`) unchanged (first list; [I3 §4.1,
   §8 item 1]).
2. `mqtt.py:187-199` and `InboundMessage` (`service.py:81-87`) — carry the
   delivery's packet identifier, its QoS, its DUP flag and the identity of the
   connection it arrived on, all stamped on the network thread (first list,
   extended; [I3 §8 item 2]).
3. `MqttBridge` — the connection identity of A4, advanced in an
   `on_socket_close` handler under a lock; an `ack(delivery)` method that, under
   the same lock, sends nothing unless the identity is current, the QoS is 1 and
   acknowledgement is still open on that connection, then calls
   `client.ack(mid, 1)` and records its return code; a purge of the ended
   connection's deliveries, scheduled onto the event loop from the close handler
   ([I3 §8 item 3]).
4. `service.py:182-197` and `_emit` (`:390-415`) — skip deliveries of an ended
   connection; request the PUBACK if and only if a line was written for this
   delivery, from a flag that `_emit` sets after `self._events.log` returns
   (`:414`), not from the absence of an exception; on a delivery that ends
   without a line, close acknowledgement on its connection and start A3's
   connection end, by the way the student chose (A3(a) or A3(b)), with A5's
   recorded and bounded repetition. The call crosses from the event-loop thread
   to paho's network thread: in paho 2.1.0 `ack()` reaches `_packet_queue`,
   which appends to a deque and wakes the network thread, the path `publish()`
   also takes; the Paho documentation gives no explicit thread-safety statement
   for `ack()`, so its safety is confirmed against the locked version before it
   is relied on (first list, made exact; [I3 §4.3, §8 item 4]).
5. `service.py:212-229` — the decode stage also catches `ValueError` and
   `RecursionError` and records `rejected` (A1; [I3 §8 item 5]).
6. `schema.py:123-130`, `:143` — a non-string `device_type` raises
   `SchemaValidationError`, so it is `rejected` (A1; [I3 §8 item 6]).
7. `ditto.py:323-333` and `dedupe.py:52-81` — a twin body that is not JSON, or
   not an object, raises `DittoError`, so it is `failed`; `ditto.py:228-255` —
   the `httpx` errors that are not `TransportError` become a non-retried
   `DittoError` (A1; [I3 §8 item 7]).
8. `service.py:203-343` — a residual handler that turns any other exception
   raised before the `PATCH` request into a `failed` line naming the exception,
   and leaves A1's four exceptions without a line (A1; [I3 §8 item 8]).
9. `events.py:103-119` — a failed write leaves no data behind for a later
   flush, for example one unbuffered write per line on an append-only
   descriptor, or dropping the handle and its buffer on error; whether a
   partial line can still result, and how the harness reads one, *I could not
   establish*, and a regression test pins the behaviour chosen (A1, A3;
   [I3 §8 item 9]).
10. `mqtt.py:187-199` — no exception may leave `on_message`: it is caught there
    and starts A3's connection end, so the network thread never dies silently
    with `/ready` still true ([I3 §5 L6, §8 item 10]).
11. `mqtt.py:35`, `:149-150` — readiness only on a granted QoS 1 (A6;
    [I3 §8 item 11]).
12. `service.py:161-169` and `mqtt.py:190-193` — no PUBACK for a delivery
    dropped on overflow or discarded for want of an event loop, and each ends
    acknowledgement on that connection (A3); `dropped` then means "left for
    redelivery at the next session resumption" (first list; [I3 §8 item 12]).
13. `app.py:159-164` and `service.py:199-201` — the stop order of the Decision,
    replacing the marker-and-drain; paho writes the queued PUBACK before the
    DISCONNECT that follows it, and none can follow the DISCONNECT (first list;
    [I3 §4.6, §8 item 13]).
14. `metrics.py` and the bridge — three additive `/metrics` fields,
    `mqtt_subscribed`, `mqtt_connection` and `unacked`; `unacked` is counted by
    the bridge at `on_message`, with its own synchronisation, because nothing
    may update `MetricsCounters` from the network thread (`metrics.py:50-55`),
    and it is therefore not a term of the accounting identity (C5;
    [I4 §5.1]).

**Deployment**

15. `src/deployment/compose.yaml`, controller service (`:243-313`) — an explicit
    `stop_grace_period` (first list; C6).
16. `src/deployment/mosquitto/config/mosquitto.conf` — the values of C1, each
    with a comment naming this decision (first list, extended; [I1 §4, §8]).
17. `src/deployment/mosquitto/config/acl` — the `$SYS` read grant of C2, if the
    student adopts it ([I1 §8]; [I4 §4]).

**Harness and helpers**

18. Harness — the five sampler fields and the three of item 14; fetch hooks
    for the broker log, the controller container log and `docker events`; the
    post-drain fetch and twin snapshots for the restart condition; manifest
    fields for the configuration identity ("Ordering, duplicates, durability and
    configuration identity"), with C2's `$SYS` readings before and after each
    run if the grant is adopted (first list, extended; [I1 §8]).
19. Runbook section 6.1 — `_mline` and `drained` as [I4 §5.2] sets out: one
    reading line with the thirteen fields in a fixed order, no reading when a
    field is missing or of the wrong type, the accounting identity evaluated
    from the same response, a quiet reading as the Decision's "drain
    precondition" row states; regenerated into the helpers by
    `tools/session/regen_helpers.py`; merged before the proof (C5; [I4 §5.2,
    §7]).
20. The controller's Python dependencies locked (`PROGRESS.md:509` records that
    they are not) (first list; C7).

**Contracts and records**

- `src/CONTRACTS.md` section 1 (`:11-25`): the persistent session and the
  acknowledgement point.
- Section 5 (`:98-127`) and its shutdown paragraph (`:275-287`): the
  acknowledgement point (A2), the order (A3), the connection scope (A4), the
  stop order, redelivery, the new meaning of `dropped`, and N1 to N5 in words;
  the three fields of item 14 under "Progress counters", each scoped to one
  process and never read as zero when absent (`src/CONTRACTS.md:170-175`)
  [I4 §5.1].
- The meaning of `failed` widens to "not confirmed, including a processing
  error before the `PATCH`" (`src/CONTRACTS.md` section 9 and
  `service.py:11-12`), and `processing_errors` (`src/CONTRACTS.md:186-195`) then
  counts only A1's four exceptions [I3 §8].
- The latency definition (`:304-306`) unchanged, with P5's condition, its
  exception for redelivered deliveries and the window record added.
- `analyze.py` unchanged by this decision. Whether an N1 identity — carried by
  the twin, with only a `duplicate` line — may be counted as delivered, under an
  explicit rule, in its own column and checked against the twin, changes what
  the project measures and is **a separate decision**. Until it is taken, such
  an identity counts as `lost`, as today.
- ADR 0005 unchanged under P5's condition; ADR 0006 relied upon and unchanged;
  ADR 0010's first follow-up taken up (the sampler fields), and its third — a
  failed event write leaves a message without an outcome — not repaired but
  made redeliverable (P2), with the connection ended (A3).
- ADR 0010 amended. It records the shutdown sequence as unchanged
  (`docs/adr/0010-controller-progress-counters.md:113-116`) and puts the
  shutdown exclusion — `queue_depth` may include the one internal marker —
  into the contract (`:79-81`, `:139-142`) [C]. This option removes the
  marker-and-drain, changes the meaning of `dropped`, a term of 0010's
  identity, narrows `processing_errors` to A1's four exceptions [I3 §8], and
  adds three fields to the counters' contract [I4 §5.1]; it amends 0010 in
  those respects, and the contract text of section 5 changes with it.
- The runbook, `docs/setup/qemu_integrated_gateway.md`: `:994-1004`, whose
  item (a) rests on the bridge not asking the broker for a persistent session,
  restated with the three fields and the residual assumption of [I4 §5.5]; the
  same point in Appendix B, item 21 (`:1300`); the helper table row (`:890`);
  and section 9, item 7 (`:1241`), "the helpers do not read the new fields",
  which ceases to hold [I4 §5.3].
- The plan freezes `src/CONTRACTS.md` v1.1 and states that "material changes
  require an ADR and regression tests" (`INTEGRATED_DEVELOPMENT_PLAN_2026.md:104`);
  the contract requires a coordinated update and a LOG entry
  (`src/CONTRACTS.md:5-9`). This is a material change to delivery semantics:
  this record is the ADR, and the regression tests are listed below. Whether to
  admit the change now is for the student, with the project manager's review.
- Entered the repository on 2026-09-24 with its index row in
  `docs/adr/README.md` (status: accepted by the student for bounded
  implementation), the LOG entry the coordinated update requires (`#C041`),
  the amendment note in ADR 0010 and the review record under
  `docs/reviews/2026-09-23-adr-0011-package-d/`.

**Tests** — regression tests with fakes, before any guest run:

- the PUBACK after the outcome line, never before; one per delivery; none
  without an outcome line (A1's four exceptions); none on overflow or on the
  no-event-loop discard; none for a QoS 0 delivery;
- each payload-driven and Ditto-driven trigger that today ends without a line
  (a deeply nested document, a 5,000-digit integer, a non-string
  `device_type`; a non-JSON or non-object twin; an `httpx` error that is not a
  `TransportError`) ending in exactly one `rejected` or `failed` line and one
  PUBACK [I3 §5 L1–L2, §8];
- an event-write failure, at open and at flush, ending in no line, no PUBACK
  for it or for anything after it on that connection, A3's connection end, and
  no late line after recovery [I3 §8];
- a PUBACK requested after the connection identity advanced is not sent; the
  purge leaves no delivery of an ended connection in the queue; the resent copy
  is acknowledged [I3 §8];
- an exception in `on_message` ends the connection, not the network thread; a
  QoS 0 grant keeps the bridge not ready [I3 §8];
- PUBACK order equal to receipt order across a mixed stream of `accepted`,
  `rejected`, `duplicate` and `failed` deliveries [I3 §8];
- the way of ending a connection chosen under A3, with A5's recorded and
  bounded repetition and `/ready` false while outcomes cannot be recorded;
- the client requested with a persistent session and manual acknowledgement
  in the constructor;
- the graceful stop: the message in progress recorded and acknowledged, the
  rest left unacknowledged, the disconnect last;
- redelivery after a simulated restart against a fake twin: an applied delivery
  classified `duplicate`, an unapplied one `accepted`, no regression of
  `last_seq`, per-device order preserved;
- `unacked` across a reconnection, during the hand-over, on the no-event-loop
  discard, on overflow and on a failed event write [I4 §5.1];
- `drained` refusing a quiet window with `mqtt_subscribed` false throughout,
  with `unacked` above 0 and the queue empty, on a change of
  `mqtt_connection`, on a failed identity and on a reading without the new
  fields, and keeping both output prefixes [I4 §5.4];
- the harness writing the eight fields; the manifest carrying the identity
  fields;
- the runbook's test 6 stating, as test 5's expected list already does
  (`qemu_integrated_gateway.md:1112`), that `duplicate` records after a
  reconnection are not failures and that `double_accepted` must be 0 — a
  statement of what is expected, not a change of criterion.

---

## Implementation record (2026-09-24)

The bounded implementation of "What must change" was written on 2026-09-24 in
pull request #46 (branch `feat/adr-0011-option-5`), with fakes only: no
broker, Ditto or guest ran. Items 1 to 16 and 18 to 20 are implemented; item
17 (the `$SYS` grant of C2) is not, by the decision recorded above. The
contract is v1.2 (`src/CONTRACTS.md`). Where this record left a point to the
implementer, the choice made is stated here; each is pinned by a regression
test and none changes a count, a threshold or a stop rule of the proof.

- **Delivery identity.** `InboundMessage` carries `mid`, `qos`, `dup` and
  `connection`, stamped on the network thread; the defaults (0, 0, false, 0)
  describe a QoS 0 delivery of no connection, so every earlier constructor
  stays valid.
- **Connection identity and lock.** One re-entrant lock in the bridge guards
  the connection number (1 before the first CONNACK, advanced at every socket
  close), the acknowledgement window, `unacked`, the CONNACK count and the
  subscription. `on_socket_close` advances the number, resets `unacked`,
  clears the subscription and schedules the purge onto the event loop; it
  never raises. `ack()` sends only for a QoS 1 delivery of the current
  connection while acknowledgement is open on it; `client.ack` runs under
  the lock, which is safe because with the network thread alive it takes no
  paho mutex, and re-entrant because with the thread absent paho writes on
  the caller's thread and a write error would run the close handler there.
- **A3(a) and A5.** `end_connection(cause, identity)` closes acknowledgement,
  writes an ERROR line `MQTT connection ended by the controller` with the
  cause (`no-outcome-line`, `overflow`, `no-event-loop`, `on-message-error`),
  the connection, the identity in progress (topic, mid, qos, dup, connection,
  arrival stamp), the occurrence and the back-off, and wakes a supervisor
  thread that runs `disconnect()`, `loop_stop()`, the back-off and the
  reconnection. Back-off: 1, 2, 4 … 30 s for the n-th consecutive end; bound:
  after ten consecutive ends with no delivery acknowledged in between the
  client is left disconnected — `disconnect` and `loop_stop` run before the
  bound is checked, so "staying disconnected" is real — with `/ready` at 503,
  `mqtt_subscribed` false and `/metrics` still served. An acknowledged
  delivery resets the count. One connection counts one occurrence: the
  first delivery that cannot be acknowledged closes acknowledgement and
  requests the end; a further such delivery on the same connection, before
  the socket closes, is logged and counts nothing *(from the review of the
  pull request: otherwise several queued deliveries of one connection could
  reach the bound by themselves)*. The graceful stop closes acknowledgement with
  the cause `stop`, logged at INFO, counting no occurrence. The occurrence
  log is the medium the proof reads (item 18 fetches the controller's log).
- **PUBACK from the written line.** `_emit` returns true after
  `EventLogger.log` returned; `process()` returns it; `run()` requests the
  PUBACK before taking the next delivery. `process()` is split into the
  decision — every stage up to and including the `PATCH`, any other exception
  a `failed` line naming it (item 8), the decode stage catching `ValueError`
  and `RecursionError` (item 5) — and the emit, which runs after the decision
  so that the clock read, the dedupe record and the write raise with no line
  (A1's fourth exception). A `RuntimeError` raised inside `patch_thing` is
  therefore `failed`, as a timeout is; the regression that pinned it as a
  processing error now raises after the 2xx.
- **Purge and skip.** `purge(ended)` re-queues the other connections'
  deliveries in order and counts each removed one `dropped`; `run()` skips a
  taken delivery of a connection below the current one, counted `dropped`,
  never in progress. The ending connection is retired the moment the end
  is requested: `end_connection` returns the connection it closed and the
  consumer skips every later delivery of it from that instant, and the
  bridge schedules the purge at once as well as at the socket close. No
  later delivery of an ended connection can therefore advance the twin or
  the cache ahead of an earlier one left to the broker *(from the review
  of the pull request: a failed `PATCH` whose `failed` line also failed,
  followed by a later `seq` of the same device applied before the socket
  closed, would have turned the resent first identity into a false
  duplicate — the order break R3 exists to detect; the earlier text here
  had called that window a source of duplicates only, which was wrong)*.
- **Overflow and the callback without a loop.** Both count the delivery in
  `unacked` (QoS 1 only, the gauge's definition) and end the connection;
  `dropped` keeps its counting point.
- **Consumer and stop.** `run()` takes with `get_nowait` and waits on an event
  set by `submit` and `stop` — a `get` task would take a delivery in a step
  of its own, so a reader on the loop could see it in no term and a
  cancellation could lose it; `stop()` sets the event and queues nothing.
  A cancelled consumer (A1's second exception) ends the connection with
  the cause `consumer-cancelled`, naming the delivery in progress, and the
  bridge stays disconnected, since nothing consumes any more; readiness
  requires a live consumer. The lifespan stops the consumer, then the
  bridge in an executor (the join of the network thread never blocks the
  loop), then Ditto and the event log, each clean-up running whatever the
  previous step raised *(from the review of the pull request)*.
- **Event log (item 9).** One unbuffered `write` of the encoded line on an
  append-only handle; an `OSError` or a short write (reported as `EIO`)
  closes and forgets the handle; a partial line can remain and is terminated
  with a newline at the next open, so no later line merges with it; a reader
  skips a line that is not JSON. `close()` flushes nothing because nothing is
  buffered.
- **Items 6 and 7.** A non-string `device_type` is refused by a type check
  before the validator lookup; `DittoProtocolError(DittoError)`, never
  retried, covers an `httpx` error outside the transport layer and a 2xx
  `GET` whose body is not a JSON object — `null` included, so only a 404 means
  "no twin" and a `null` body no longer re-creates the twin; a twin whose
  `features`, `ingestion` or `properties` is not an object is read as empty.
- **Deployment (items 15, 16, 20).** `stop_grace_period: 130s`; the six C1
  options explicit in `mosquitto.conf` (`sys_interval 10`, the default, so
  that the file's hash carries it); `src/requirements-runtime.lock`, resolved
  by the steps of `generate-runtime-lock.sh` inside the pinned base image
  under `linux/arm64` user-mode emulation on the workstation (the container
  reports `aarch64`; the script's own host check refuses the x86-64 host, so
  its `docker run` was issued directly with the same arguments) and installed
  by the Dockerfile with `--require-hashes`; paho-mqtt 2.1.0, the version of
  the analysis environment and of the r02 container. Images built before
  that commit are unlocked and are not admissible for the proof.
- **Harness (item 18).** Ten columns after `queue_depth`; the raw fields are
  written verbatim only when of their documented type (a mistyped one is an
  empty cell counted as invalid); the three log fetches run last, after the
  drain, so they cover it; a fetch or snapshot that exits 0 without its file
  is a validity reason, as is a drain that gives up (`--drain-cmd` bounded
  at 1,800 s, twice the helper's own limit); `twins.before.json` is taken
  after the warm-up; `--config-identity-from` is also accepted by `collect`
  and may carry `{run_id}` in a campaign; the manifest keys are
  `sut_log_fetches`, `twin_snapshots`, `drain`, `events_post_drain_fetch`,
  `configuration_identity` and `configuration_identity_file`, additive
  within version 1.4. For a `controller_restart` run the before snapshot,
  the drain and — when the drain was quiet — the after snapshot and the
  post-drain copy of the events are required, taken by the hooks or
  ingested from the runbook helpers' files with `--twins-before-from`,
  `--twins-after-from`, `--post-drain-events-from` and
  `--drain-transcript-from` (each verified against the run before it
  counts — the snapshot's label and seed, every post-drain event's
  `run_id` and outcome, the helper's own lines in the transcript — with
  its source and hash recorded); no flag excuses a missing step, and a
  hook's file is verified by the same rules. The drain's outcome is
  classified from the helper's lines: `quiet`; `gave-up`, a valid
  observation of failed recovery, recorded with a warning, never a
  validity reason, the after evidence then not required; or `error`, an
  instrument failure and a reason — the proof's evaluator applies the
  ADR's inconclusive rule to `drain.outcome` itself. The twin snapshot
  hooks run under `SNAPSHOT_TIMEOUT_S`, which the collector's
  `{duration_s}` includes when a snapshot is configured, so the before
  snapshot cannot outlast the collector. The runbook's test 6 captures the
  drain's transcript, fetches the post-drain copy, takes the after
  snapshot and ingests the four files with `collect` before `delta`. The
  identity document must be a JSON object carrying `broker_conf_sha256`, the
  six C1 values, `broker_reloaded`, `stop_grace_period`,
  `controller_image_id`, `controller_source_commit`, `paho_version` and
  `a3_choice`, each of the stated type; anything else is refused with a
  warning and embeds nothing *(both from the review of the pull request)*.
- **Runbook (item 19).** `_mline` exits 3 with the line when the identity
  fails in the response; `metrics()` keeps its seven keys, since `accounted`
  reads only those; `regen_helpers.py` is unchanged and now pinned by a
  regeneration-equality test.

**Not in the pull request, needed before the proof:** the guest-side
capture that writes `configuration_identity.json` (the broker configuration's
hash and C1 values, the statement that no reload happened,
`stop_grace_period`, the controller image's id and source commit, the paho
version, the A3 choice) and the three log-fetch helpers, which belong to the
proof's session driver; the identified controller image built from the
commit that carries the lock; the regeneration of the deployed helper file
with `regen_helpers.py` (the new `_mline` refuses a controller build without
the thirteen fields); the proof's evaluator, which applies S1–S6 and R1–R4 —
S4 with the twin's evidence of a named N1 case — to the post-drain copy and
the snapshots. None of this runs on the guest without the student's separate
authorisation.

## Consequences

- **Positive, if the broker measurement and the proof support the option.** The
  two classes that r01 and r02 left without outcomes would be redelivered
  instead, using a store the deployment already runs and no new persistent
  format. Neither is recovered — redelivered and ending `accepted`, or
  `duplicate` in a named N1 case — until the decision is recorded, the broker
  measurement has supported the option (C3) and the proof has supported it;
  even then only for those runs.
- **The failure surface moves to the broker.** Its queue bound, its disk and its
  in-flight window become load-bearing, and a message it discards is invisible
  to the controller — which is why the values are set and recorded rather than
  left to defaults. Those defaults are now read — 20 in flight and 1,000
  queued — and they cannot hold the backlog [I1 §4]. The settings are global,
  so they bind every subscriber of the broker [I1 §2]; a drop is counted only
  broker-wide, and only if `$SYS` is made readable (C2) [I1 §3].
- **Malformed payloads stop being silent losses.** Today a payload that raises
  past the decode stage ends with no line and no trace beyond
  `processing_errors`; under A1 it is `rejected` with a line. Without A1 this
  option would have turned such payloads into poison deliveries that could
  stall the controller [I3 §5, §10].
- **`drained` changes for every family.** Its condition changes wherever it
  runs; its outcome only after a restart, a reconnection, a reboot or a
  delivery left without a line [I4 §7]. It costs no extra request per reading;
  a call gets longer only in D1 or D2, where it waits for the redelivery to be
  processed or ends with the existing `STOP` at its limit [I4 §6]. The same
  blind spot sits in `gate_health.sh`'s counter baseline, in `accounted`'s
  `queue_depth` check and in `delta`'s check of `queue_depth`; each would need
  the same fields, and they are not assessed here [I4 §7].
- **`duplicate` records become normal** after restarts and reconnections; they
  are read as redeliveries, as the runbook already reads them for test 5.
- **One class remains** (N1): at most one identity per death, or per
  connection ended under A3 after a `PATCH`, reported `lost` by the analysis
  until the separate decision above is taken.
- **The graceful drain disappears.** A restart leaves the backlog at the broker
  instead of racing the engine's stop timeout — which, in r02, allowed 10 s and
  then forced the stop (section 1.5). As an illustration only: at
  `nominal-r01`'s phase rates r02's 1,867 queued would have needed 211 to
  378 s [F:S.2], and at r02's own old-process rates 341 to 370 s [F:R02.12].
- **Latency stays comparable with `nominal-r01` only under P5's condition**,
  for first deliveries only, and each run records whether the condition held;
  redelivered identities are reported apart.
- **The `controller_restart` validity question stays open** (N8).

### Relationship with the throughput problem

**The recovery decision does not by itself make any timed family meet its
deadline.** It changes where undelivered messages go when the controller
restarts — from nowhere to the broker — and nothing about how fast the
controller confirms them. In `nominal-r01`, 3,794 of 6,720 identities were
confirmed by the deadline and 2,926 after it, with none lost after the drain
[F:N.1, N.2]; option 5 establishes no improvement of those figures — it is not
a timing change — and its `ack` call adds an unmeasured cost on the serial
path (N6). The earlier candidate failed that deadline; the changed candidate
has not been measured, so neither a timely-delivery improvement nor an
inevitable failure is demonstrated for test 5 (326 of 2,016 late in its one
execution), for test 6 at 11.2 msg/s or for any other family timed at a rate
the stack did not keep up with. Late delivery stays a risk the battery
measures, not a foregone result *(corrected 2026-09-24; this paragraph had
said that nothing in option 5 would improve the figures and that those
families would still confirm late)*.

In particular, the harness's C12 gate for the `controller_restart` condition,
`delivery_across_restart_zero_lost`, requires `lost == 0`
(`src/egw_experiments/analyze.py:2715-2718`) [C], and `lost` is every "valid
message sent without a unique confirmation within 60 s after the end of the
run" (`src/CONTRACTS.md:371-372`), late confirmations included. Late confirmations were observed in every timed
run of the earlier candidate, so that gate is at risk under options 1 to 5
alike; whether it passes on the changed candidate is not established either
way, and only the battery measures it. What the options settle is whether the
restart classes are processed late or never; they do not settle that gate
*(corrected 2026-09-24; this paragraph had said the gate was expected to fail
under every option and that the options did not differ in whether it passes)*.

Whether throughput work belongs to the candidate before G3 is **a separate
decision for the student**. The G3 qualifying runs stay paused until the
candidate is frozen after package D, by the student's answer recorded on
2026-09-21 (`PROGRESS.md:180` on the branch `docs/g3-pause-answer`, commit
`3549d46`, not yet on `dev`) [C]. The options for that decision:

- **T1 — freeze the candidate with the recovery change only.** The nine
  families run as one qualifying battery; each timed family that misses its
  deadline is recorded as failed, under the plan's rule that "a result worse
  than expected at the nominal rate is recorded as a sizing finding for the
  pilot, never absorbed by changing the protocol"
  (`INTEGRATED_DEVELOPMENT_PLAN_2026.md:638-640`) [C]. G3 would then not be met
  on those families, and the record would say so. Cheapest in time; the least
  ambitious result.
- **T2 — throughput work before the freeze**, for example per-device
  concurrency in the consumer. It needs its own ADR that addresses ordering
  (processing one device's messages out of order would let the `seq` floor
  classify genuine messages as duplicates, `dedupe.py:103-112`), duplicates,
  durability and configuration identity. Under option 5 it would also need an
  acknowledgement sequencer: concurrent consumers complete deliveries out of
  receipt order, and MQTT 3.1.1 requires PUBACKs in receipt order
  ([MQTT-4.6.0-2]), so only the completed prefix could be released [I3 §6]. It also needs evidence that it would help: 89.3 % of
  the nominal load targets one twin [F:N.6], and how Ditto serialises
  concurrent updates to one thing is not established from any source available
  here. It would reopen parts of this record and costs time against the
  planned candidate date.
- **T3 — a bounded diagnostic measurement first**, then T1 or T2: the one
  proposed in `backlog_diagnosis.md` section 11 — one run at 2.24 msg/s for
  720 s, sized below the lowest rates `nominal-r01` served (4.60, 3.83 and
  3.00 msg/s over 60, 30 and 10 s, all in its first minute of load). It asks
  whether the controller's queue stays bounded at that load and how long one
  passage takes when nothing waits ahead of it; it changes no code and is not
  a G3 qualifying run. Its design does not depend on this record's proof, nor
  the proof's on it. A measurement, never a capacity claim. It is **refuted**
  by sustained growth — the reconstructed number in the controller never
  returns to 0 in the last 120 s of publication — or by any identity confirmed
  after the deadline or without an outcome after the drain; it is
  **inconclusive** if the procedure stops (a `STOP` from any helper, a missing
  controller marker) or a stop rule below is reached (`backlog_diagnosis.md`
  section 11.4). Its planning ceiling of 46.0 minutes (section 11.3) is not a
  bound; its **ceiling** here is about 80 minutes, set by two stop rules
  imposed by design, not measured durations: the stack healthy within 20
  minutes of its start (as for the broker measurement), and the attempt
  stopped 60 minutes after `pre` starts. Section 11.5 of the diagnosis lists
  the same four guest sessions as "Open items" below.
- **T4 — a prospective protocol decision on QEMU workloads** belongs to G4 and
  the protocol freeze, is taken before execution, and never re-labels the
  failed nominal run
  (`docs/governance/proposals/acceptance_protocol_update_2026-09-19.md`,
  section 3, proposal item 5). It is listed so that it is not confused with T1 to T3; it
  is not a candidate decision.

---

## Alternatives rejected

- **Raising the queue cap.** A larger volatile queue loses more at a kill, not
  less; `dropped` was 0 in every sample of all three runs [F:R01.3, R02.3, N.4].
- **Writing the queue out on SIGTERM.** Does nothing for a SIGKILL, and a
  graceful stop is not guaranteed to reach it.
- **A stop allowance long enough for the drain.** As an illustration, r02's
  1,867 queued would need 211 to 378 s at `nominal-r01`'s phase rates [F:S.2],
  or 341 to 370 s at r02's own old-process rates [F:R02.12]; an allowance that
  long ties every restart to the backlog, and a kill still loses everything.
- **A small in-flight window as deliberate back-pressure.** It moves the wait
  out of `latency_ms` (option 1) and would make latency look better without
  any confirmation arriving sooner.
- **Option 3 as the first step.** The stronger local property and the largest
  change, with its per-message cost unmeasured on a guest that served below
  the offered rate in every observed phase of one run. Held in reserve.
- **Consumer concurrency as part of this decision.** It addresses throughput,
  not recovery, and needs its own evidence (T2).
- **Holding an in-flight slot for a delivery that ends without an outcome
  line.** It leaves the protocol's duty to answer that PUBLISH unmet for the
  life of the connection, nothing resends it while the connection lasts, each
  such delivery removes a slot from the window, and a deterministic failure
  fails again at every resumption [I3 §6]. It would also make every `drained`
  end with `STOP` until a session resumption [I4 §3, §8].
- **Option 5 on the broker's defaults.** 20 in flight and 1,000 queued hold at
  most 1,020 messages and drop the rest; the window of 20 moves the wait out of
  `latency_ms` [I1 §4].
- **A `drained` built on the broker's `$SYS` topics.** None is per client or per
  session, each is refreshed only every `sys_interval`, the ACL grants no one
  access to them, and the broker log documents no per-session queue: no
  truthful check of the controller's session queue can be built from them
  [I4 §4] (the topics and their refresh: `gates/sources/man_mosquitto-8.txt:219-224`,
  `:230-421`, the 2.1.x page). A `$SYS` read per reading would also cost about 4 s, an estimate
  from two other steps [I4 §6].
- **`/ready` in each `drained` reading.** Each call awaits a Ditto request, so
  Ditto's reachability would become part of the drain [I4 §5.2].
- **Refusing only `processing_errors` or `dropped` above zero in `drained`.**
  It misses D1 entirely [I4 §5.2].
- **Relaxing the 60 s window or lowering the 11.2 msg/s load to make a run
  pass.** Changing a criterion to meet it is not a repair, and it is not this
  decision's scope.

## Open items

**Nothing listed here has to be answered before the student decides.** Items
1, 2, 5 and 6 were the gates on the decision in the first version of this
record. The four gate notes of 2026-09-21 answered items 2, 5 and 6, and item
1 only in part; its open part — whether the pinned broker holds W within
128 MiB and redelivers it in per-device order — became condition C3, and
**the broker measurement of 2026-09-23 met C3 for that run** (attempt04;
the status paragraph and C3 above). What remains of each item is stated with
it, with how and when it is closed. What can only be closed on the guest is
closed by a bounded engineering diagnostic, never by a G3 run.

1. **The broker's limits — answered; the open part closed by the measurement
   for this guest and this run** [I1 §0]. The 2.0.22 documentation allows the
   window and the queue to be set far beyond 4,999; today's configuration
   cannot hold the range; a drop is counted only broker-wide. **Closed on
   2026-09-23 by the broker measurement** (attempt04): the pinned broker
   honoured W = 4,999, held 5,999 within 128 MiB and redelivered in per-device
   order; it counted the held in-flight messages **above** the queue bound
   while the client was offline (store W + Q, dropped B − Q); it logged its
   transition into dropping, once, at `notice` (N4: presence for that
   connection, not a count). What the design had listed as still
   open — whether it honours W, holds it within 128 MiB, and
   redelivers in per-device order; whether it counts the held in-flight
   messages against Q while the client is offline; whether 2.0.22 still logs
   a drop as the change log records since release 1.3, at which log type, and
   whether the deployed log types include it (N4). A refuting result, an order
   break included, rules option 5 out as configured; an inconclusive one leaves
   C3 unmet. Not established from the documentation either: whether
   `max_queued_bytes` counts payload or packet bytes; whether memory tracking
   is compiled in, which decides whether `memory_limit` and
   `$SYS/broker/heap/*` exist ([M5] `:702-703`;
   `gates/sources/man_mosquitto-8.txt:264-271`, the 2.1.x page); that the
   binary reports 2.0.22 and loads the mounted file (CONSISTENT-WITH the preserved log format
   only); whether a drop at a subscriber's queue affects the publisher's PUBACK
   [I1 §9].
2. **r02's guest-side evidence — answered: read** [I2 §1]. It confirms the
   proposal's Finding 2 and argues nothing against option 5 [I2 §9]. What
   remains:
   - **Preservation, before the guest is booted again — urgent.** The recovered
     broker and controller lines sit in free blocks of the guest's data disk,
     and any later guest session can overwrite them; the extracted copies in
     `gates/item2_extract/` live in a working directory that will not survive.
     Whoever may write to an evidence package copies the journal, both guest
     event logs, the recovered-line file, its block map and the extraction
     record, with `gates/out/item2_extract.SHA256SUMS.txt`; a read-only image
     copy of the data disk keeps the residual bytes whole [I2 §9, condition 1].
     This precedes every guest session: the broker measurement, the T3
     measurement and the proof included.
   - **The evidential standing of recovered bytes** — the student's decision.
     If they are not admitted, the PROVED results stand and the two classes
     return to the harness-side bounds of section 1.3 [I2 §9, condition 3]. The
     recommendation does not depend on it.
   - **The twins' counters after r02** — never snapshotted; they exist, if at
     all, only in MongoDB's files on the data disk, which were not read. They
     would settle whether r02's in-flight identity is an N1 case [I2 §8]. Not
     needed to decide.
   - The 5 to 7 identities published between the last answered poll and the
     old client's disconnect; the exact instant of signal 15; whether the
     broker's text "Client … disconnected." denotes a client DISCONNECT; r01's
     journal and residual broker lines, not analysed [I2 §8].
3. **The values of W and Q** against the backlogs the nine families are
   expected to produce — still open. Q must also hold the outage (319 to 321 in
   r02's restart, on the recovered lines) and, if the broker counts the held
   in-flight messages against Q while the client is offline, W plus that outage
   [I1 §4; I2 §9]. The broker measurement answers the accounting question, and
   Q is re-sized before implementation if needed [I1 §7]. Beside this item: the
   pilot plan's `load_sweep` runs at 50 msg/s or more, and its `soak`, are
   expected — not established — to fill the window under option 5, so that
   their `latency_ms` excludes the broker wait (P5) and their overflow becomes
   a broker-side drop ("The pilot plan's load sweep and soak, under option 5",
   in section 3). Whether W, Q or the load-sweep protocol must answer this
   before the freeze is left to the student, or to the G4 protocol decision
   (T4).
4. **The analysis rule for N1 identities** — a separate decision.
5. **The acknowledgement order — answered** [I3 §1]. MQTT 3.1.1 requires
   PUBACKs in receipt order; with one FIFO consumer the order follows by
   construction, to be pinned by the regression tests; a delivery that cannot
   have a line ends the connection (A3) and never holds a slot. What remains:
   the student's choice between A3(a) and A3(b); what the engine does on a
   non-zero exit under `restart: unless-stopped`, which A3(b) relies on; a
   documented thread-safety statement for `ack()` from another thread; how 2.0.22 treats a
   PUBACK out of receipt order (moot under A3); which reading of
   [MQTT-4.6.0-2] applies to a delivery never acknowledged on a connection that
   is later closed; what a partial line left by a failed write looks like, and
   how the harness reads one [I3 §9]. **No guest measurement is needed**: the
   rule is checked by regression tests with fakes before the proof [I3 §10].
6. **The `drained` procedure — answered** [I4 §0]: it must change (C5), before
   the proof; with the change it is truthful except for the residual
   assumption stated in C5. What remains: that assumption itself — a broker
   with nothing in flight to a session that stays connected holds nothing
   queued for it —
   ASSUMED from the documented meaning of the queue, testable **only on the
   guest**, by the proof's optional extension [I4 §9], an engineering
   diagnostic, not a G3 run, and the student's decision; whether test 6's
   post-run drain fits within 900 s under option 5; what the extended reading
   costs under load; whether a false quiet window can only produce a false
   `MISMATCH`, never a false `OK` [I4 §10]; and the same blind spot in
   `gate_health.sh`, `accounted` and `delta`, not assessed [I4 §7].
7. **The effect on the other families — narrowed.** `drained`'s effect on every
   family is set out [I4 §7], and the broker's settings apply to every
   subscriber [I1 §2]. Still not assessed: test 8 under a persistent controller
   session beyond its `drained` (a reboot with a held session and the broker's
   60 s autosave), and tests 1 to 4, 7 and 9 beyond `drained` and the broker's
   global settings.
8. **The calendar cost** of option 5's work against the stable-candidate
   target of 2026-09-25 in the project manager's record
   (`PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 5, item 5)
   — I could not establish an estimate. The work has grown from ten code items
   to twenty ("What must change"), and the guest time now includes the broker
   measurement (about 15 to 19 minutes of measurement, plus stopping and
   restarting the stack; ceiling about 45 minutes) [I1 §7] beside the proof
   (17 to 29 minutes as a planning figure; ceiling about 70 minutes), the
   optional extension (ceiling about 28 minutes plus C6's `stop_grace_period`)
   and T3 (ceiling about 80 minutes),
   each listed below. Option 4 costs none.
9. **C2's `$SYS` grant** — a choice attached to option 5, not a condition: the
   student makes it or declines it. Declining it loses N4's run-level drop
   evidence — the log's single transition line per connection is no
   substitute — and leaves test 9's proof unchanged (C2).

**The guest sessions, one line each.** Four guest sessions are now proposed,
none of them a G3 run, each after r02's residual evidence has been preserved
(item 2). Every ceiling below includes stop rules imposed by design, not
measured durations; it is counted from the session's first step after the
guest has booted to the end of its last fetch (the boot took 33.2 s and the
session close 10.7 s on 2026-09-20,
`docs/evidence/g2-complete-flow/20260920T231756Z_guest-session_attempt02/commands.jsonl:2`,
`:7`). A session that reaches a stop rule stops and is recorded inconclusive.
The student may set other values before a session; the values used are
recorded before it starts. The 20-minute rule for a healthy stack rests on the
one recorded restart of the whole stack under TCG, 228.7 s from `compose down`
to all services healthy
(`docs/evidence/g2-complete-flow/20260920T233212Z_g2-twin-persistence-restart_attempt01/commands.jsonl:7-9`),
against an earlier estimate of tens of minutes that the runbook marks
unverified (`qemu_integrated_gateway.md:502`).

| session | question | result that refutes | inconclusive | ceiling |
|---|---|---|---|---|
| T3, 2.24 msg/s for 720 s on today's code (throughput decision) | does the candidate keep its controller queue bounded at a load below every rate `nominal-r01` served, and how long is one passage with nothing ahead of it? | the reconstructed number in the controller never returns to 0 in the last 120 s of publication; or an identity confirmed after the deadline, or without an outcome after the drain (`backlog_diagnosis.md` section 11.4) | a `STOP` from any helper; a missing controller marker; a stop rule reached | about 80 minutes: stack healthy within 20 minutes, then the attempt stopped 60 minutes after `pre` starts (above the 46.0-minute sum of the helpers' limits, section 11.3) |
| broker measurement (C3) | does the pinned broker accept and honour W = 4,999, hold 4,999 and then 4,999 plus a queue within 128 MiB without drops, show where a full queue drops, and keep and redeliver the held messages, in per-device order, after the subscriber is killed? | the configuration refused; fewer than 4,999 held; a drop while at most 4,999 are held; an OOM or a broker restart; fewer redelivered than the store held; a per-device order break in P7 | `$SYS` unreadable; a recorder gap over 5 s; the publisher off its counts; no disconnection line after the kill; a tunnel failure; the last phase at its limit; a stop rule reached | about 45 minutes: stack stopped and probe broker started within 5 minutes, the phases at their limits (1,154.6 s), stack healthy again within 20 minutes |
| the finite proof | with deliveries unacknowledged inside the controller at a SIGKILL, does every published identity obtain an outcome after the drain, the restart classes an `accepted` one or a named N1 case, with none accepted twice and no `duplicate` hiding an unapplied `seq`? | R1 to R4 ("The finite proof") | S1 fails; a `drained` at its limit; a fetch fails; a restart-class identity with only `failed` lines, none of R1 to R4 holding; a stop rule reached | about 70 minutes: stack with the candidate healthy within 20 minutes, then the attempt stopped 50 minutes after its first `drained` starts (36 minutes of helper limits plus 14) |
| the proof's optional extension | with nothing published, does a broker with nothing in flight to a connected persistent session hold nothing queued for it? | the new process receives a delivery (`received > 0`), or an identity gains its first outcome line after the first quiet window [I4 §9] | the restart not shown or `/ready` not reached; its `drained` at its limit; a fetch fails; a stop rule reached | C6's `stop_grace_period` plus 1,660 s, about 28 minutes plus that period: the restart within the grace period plus 5 minutes, `wait_ready` about 95 s, one `drained` at `DRAIN_LIMIT_S` = 900 s (`qemu_integrated_gateway.md:654`) read as about 935 s, one `/metrics` reading of 30 s, the fetch within 5 minutes [I4 §9] |

## Follow-ups (not part of this decision)

- The throughput decision (T1 to T4).
- The lifecycle-aware ingest rule for a deliberate restart (proposal section 2),
  and a collector that samples at a true 1 Hz.
- The fate of r02's in-flight identity (`smart_clothing` seq 1422), which the
  twins' counters on the guest's data disk would settle (item 2 above). Both
  restart runs' end-of-run blocks are settled: late, not lost (section 1.6).
- The historical package of r02 still carries the earlier triple
  1,810 / 195 / 131 in its reason field
  (`output_test/runs/2026-09-19/HIST_controller_restart-r02/attempt.json:13`,
  `SUMMARY.md`); that folder was not changed [I2 §6].

---

## Review history

The corrections to the unnumbered draft of 2026-09-20, and those of the second
review round of 2026-09-21, are recorded in this record's review annex
(`adr-0011-review-annex.md`). The annex is part of the review record, not of
the ADR, and does not enter `docs/adr/`.

The answers to the four gate items (2026-09-21, `gates/item1_broker_limits.md`,
`gates/item2_r02_guest_evidence.md`, `gates/item3_ack_order.md`,
`gates/item4_drained.md`) are folded into this record. What they changed:
r02's stop, its classes and its clean session (sections 1.1 to 1.6, 2(e),
2(f), code identity); the broker's defaults and scope in the options; the
proposal, now under six conditions (C1 and C3 to C7) and one choice (C2), with
option 4 named as the next best; the acknowledgement rule A1 to A6 in place of
the open choice; the `drained` change; the broker measurement; the twenty items
of "What must change"; and the open items, of which none now has to be
answered before the decision, although item 1 is answered only in part and its
open part is condition C3, which can still rule option 5 out. The
version before the fold is kept at `gates/prefold/`.

The refutation check of 2026-09-21 (`gates/check.md`, 18 findings) was
applied on 2026-09-23 (`gates/precheck/` holds the version before it). On the
same day the tool of the broker measurement was built, reviewed in five
rounds, checked on the workstation's Docker and run on the guest; the
measurement's fourth attempt of the session met C3 (the status paragraph,
C3 and open item 1 record it; the tool, its corrections and the session are
in LOG `#C040` and in `output_test`).

The project manager's review of the C3 result (2026-09-23, after the
measurement) corrected three statements, applied the same day
(`gates/precheck/adr-0011.pre-d1d3.md` holds the version before them): the
broker log's drop line is one `notice` line per client per connection, at the
transition into dropping, not a count and not a run, so declining C2 is a
knowing loss of run-level drop accounting (N4, C2, C3, open items 1 and 9;
the tagged v2.0.22 source is cited where it is stated); the status paragraph
says what was logged; and C1 states that Q = 1,000 and the one-hour
disconnected-session expiry are the values C3 exercised, not a validated
expiry or a queue shown adequate beyond r02's outage. The record still
establishes no timely delivery and no controller recovery; those remain for
the battery and the finite proof.

On 2026-09-24 the student decided option 5 for bounded implementation ("The
decision recorded on 2026-09-24"); the record entered `docs/adr/` with that
section, the status above, the two paragraphs of "Relationship with the
throughput problem" corrected as marked there (the project manager's residual
D2 finding of 2026-09-24), the closing paragraph restated, and the review
record — analyses, gate notes, scripts, outputs, verification reports, annex
and decision request — committed under
`docs/reviews/2026-09-23-adr-0011-package-d/` (its `README.md` says what is
not kept there and where it is). The review of the published record on the
same day added the twin's evidence to S4 (a named N1 case needs the device's
`accepted_count` surplus, or R3 applies) and restated the two remaining
sentences that predicted the zero-lost gate's failure under every option
(option 4's row of the options table and the fallback assessment) as an
unresolved risk, each marked where it stands.

---

## Sources and reproduction

**Scripts** (read-only; nothing installed):

- `pkgD/v2/scripts/adr0011_figures.py` — every figure. Run as
  `wsl -d Ubuntu-24.04 --exec bash -lc "~/egw-exec/venv/bin/python $PKGD_WSL/v2/scripts/adr0011_figures.py"`;
  output `pkgD/v2/out/adr0011_figures.out.txt`.
- `pkgD/v2/scripts/adr0011_code_anchors.sh` — every `file:line`, run from Git
  Bash as `bash "$PKGD/v2/scripts/adr0011_code_anchors.sh"`, using `git show`,
  `git grep`, `git diff --stat`, `git log` and `git merge-base --is-ancestor`
  only; it locates the repository worktree relative to itself (or from
  `EGW_WORKTREE`); output `pkgD/v2/out/adr0011_code_anchors.out.txt`.
- Not yet in either script's output: the anchors and figures added when the
  check of the fold (`gates/check.md`, section 2) was applied on 2026-09-21 —
  `src/egw_experiments/protocol.py:54`, `:300-304`, `:401-406`,
  `src/egw_experiments/plan_gen.py:24`, `:74-95`, `experiments/README.md:68`,
  `:97-107`, `tools/session/nominal.sh:46`, `src/egw_controller/mqtt.py:31`,
  `:207`, `src/deployment/mosquitto/config/mosquitto.conf:48-53`,
  `qemu_integrated_gateway.md:502`, and the command durations in
  `docs/evidence/g2-complete-flow/` cited under "The broker measurement" and
  "Open items". Each was read with `git show 35fe8bb:<path>` in
  `scratchpad/devwt`; the load-sweep and soak thresholds of section 3 are
  arithmetic on those figures, shown where they are used.
- The gate notes' own scripts, all read-only, each with its command in its
  note's reproduction section: `gates/scripts/item1_payload_and_broker_memory.py`
  ([I1 §10]); `gates/scripts/item2_extract_guest.sh`,
  `item2_carve_data_disk.py` and `item2_r02_guest_evidence.py` ([I2 §10]; the
  first two refuse to run while a guest is running and open the disk images
  read-only); `gates/scripts/item3_anchors.sh` and `item3_probe.py`
  ([I3], "Sources and reproduction"); `gates/item4_callsites.sh` and
  `gates/item4_drain_timings.py` ([I4], "Sources and reproduction"). The
  documentation they rely on is copied in `gates/sources/`, with its hashes in
  `gates/sources/SHA256SUMS.txt`, with one exception. The copies are the
  mosquitto.org pages, which document 2.1.x, the change log [CL], the MQTT
  3.1.1 standard and `mosquitto.conf(5)` as released with 2.0.22 [M5]
  (`mosquitto.conf.5-2.0.22.xml`, sha256 `5d53da59…`, taken from the
  project's 2.0.22 source tag, not from mosquitto.org). The exception is
  `mosquitto(8)` as released with 2.0.22 [M8] (sha256 `7ff3b8f2…`), which is
  kept nowhere in the package: the gate notes' `[M8] :n` citations cannot be
  reproduced from it, and this record cites the mosquitto.org 2.1.x page
  (`gates/sources/man_mosquitto-8.txt`) in their place, with that version
  caveat (see "Sources" at the head of this record).

`$PKGD` was the package D working directory in a session scratchpad on
Windows, and `$PKGD_WSL` the same directory under `/mnt/c/`; neither survives.
Since 2026-09-24 the two scripts, their outputs, the analyses this record
cites (`controller_today.md`, `restart_evidence.md`, `backlog_diagnosis.md`),
the verification reports, the review annex, the decision request and the four
gate notes with their scripts and outputs are the review record
`docs/reviews/2026-09-23-adr-0011-package-d/` (its `README.md` lists them),
from which every `gates/…`, `scripts/…`, `out/…`, `[F:…]`, `[I…]` and `[G:…]`
citation of this record resolves; `pkgD/v2/` in the paths above reads as that
directory. The documentation copies of `gates/sources/` are identified there
by their hashes and not committed; the guest files extracted for item 2 are
the evidence package of "Open items", item 2, held outside the repository.

**Inputs read, none modified:**
`/home/ruisth/egw-tcg/pilot/results/raw/controller_restart-r01/` and `-r02/`
(`manifest.json`, `sent_events.jsonl`, `events.jsonl`, `controller_metrics.csv`,
`logs/collector/resources-<run_id>.csv`);
`/home/ruisth/egw-tcg/pilot/results/raw/nominal-r01/` (`manifest.json`,
`sent_events.jsonl`, `events.jsonl`, `controller_metrics.csv`);
`/home/ruisth/egw-exec/attempts/20260919T195827Z_nominal-instrumentation-120-600_attempt01/`
(`analysis/events.post-drain.jsonl`, `analysis/warmup.events.jsonl`,
`commands.jsonl`); the repository at `35fe8bb`, `3549d46` and `b7e0c83` through
the worktree `scratchpad/devwt`; paho-mqtt and uvicorn in `~/egw-exec/venv`;
`~/egw-tcg/itest-helpers.sh` (outside the repository). The gate notes list
their own inputs; among them, for item 2, the guest's root-filesystem and data
disk images, opened read-only with nothing mounted and nothing written [I2 §3,
§10].

**Records relied upon for direction, not for figures:**
`PM_G2_ACCEPTANCE_REVIEW_PR40_2026-09-21.md`, section 5, and
`PM_REVIEW_PR38_LOCAL_OUTPUT_AND_NOMINAL_2026-09-19.md`, section 5, items 2 and
3 (both recorded by the project manager);
`docs/governance/proposals/acceptance_protocol_update_2026-09-19.md`, section
3.

No guest was started, no run was repeated, nothing was measured live, and no
command that changes repository state was run.

---

**This record is accepted by the student for bounded implementation
(2026-09-24). It closes no gate, admits no claim, accepts no result and
changes no rule. The student has recorded the decision and the broker
measurement has run and supported the option (C3); until the change and its
tests are merged and the finite proof has run and supported the option,
nothing described here is more than a decided design — the code at the merged
`dev` implements none of it. Even then it is the behaviour this record
decides, supported by one broker measurement and one proof run, for those
runs only.**
