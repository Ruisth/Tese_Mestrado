# T6: resource sampling versus the restart's Docker events (2026-10-03)

**Status: PROPOSED, for Rui's decision. Adopts nothing.** No rule, threshold, deadline, load, controller,
launcher, image or frozen helper changes here; `controller_restart-r03` stays invalid under decision 1a
([pending decisions](2026-09-29-g3-pending-decisions.md)); no row deleted, zero-filled or relabelled; the sealed
package untouched. Existing bytes only, at the Project Manager's request of 2026-10-03.

## 1. What the bytes show

Sources: `output_test/runs/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01/raw/controller_restart-r03/`
(read only); `collect-resources.sh` (deployed sha256 `11444c0a…`), `resources.py` and `proved_down.py` at
`80e833f`. Guest clock throughout; Docker's `timeNano` and `StartedAt` are the daemon's stamps. A collector row's
stamp is a **whole second taken before the reads**: the shell sleeps to a slot aimed 0.5 s into a second (paced on
`/proc/uptime`), discovers the cgroup directories holding `cpu.stat` and `memory.current`, then awk takes
`systime()` and reads them. A directory first discovered gives `appeared` in `.lifecycle.csv` and primes without a
row; one no longer found gives `disappeared`.

| Instant | Source | `egw-controller-1` |
|---|---|---|
| 13:37:11Z | row `70.51,69947392,26.06` | last row of the old process (66.7 MiB) |
| 13:37:12Z | lifecycle `disappeared` | no cgroup; no rows 12Z–16Z |
| **13:37:14.060** | event **`die`** (`kill` 11.282, `stop` 13.997) | **D**; sec(D) = 13:37:14 |
| 13:37:16Z | lifecycle `appeared` | cgroup readable; priming sample, no row |
| 13:37:17Z | row `0.00,2703360,1.01` | no CPU, 2.58 MiB: **rejected** "between the die and the start" |
| **13:37:18.762** | event **`start`** (`StartedAt` 18.699) | **S**; sec(S) = 13:37:18 |
| 13:37:18Z | row `16.06,3588096,1.34` | 3.42 MiB: **rejected** "in the second of the start" |
| 13:37:19Z | row `83.63,9887744,3.68` | first row after sec(S) + 1 s: edge after 1.0 s |
| 13:37:28.984 | `/metrics` `started_at` | the new process answers |

Both edges pass (3.0 s, 1.0 s); the two rows are the only problems (`resources_proved_down.rejected_rows`).

**The mismatch.** The cgroup was gone by the 13:37:12Z sample, before `die`, and back by 13:37:16Z, 1.7–2.8 s
before `StartedAt`; the 13:37:17Z row was read 0.8–1.8 s before `start`. The diagnostics log puts the 13:37:18Z
sample at uptime 878.14 s, about 13:37:18.58 (calibration 10): 0.12–0.74 s before `StartedAt`, depending on
whether the daemon stamped before or after the 0.62 s backward clock step of calibration 11, which widens the
brackets above by as much; whether the read after that stamp preceded `StartedAt` is undecidable. A runtime
creates the cgroup and places the container's init in it before the process starts: no CPU and 2.6 MiB fit that
pre-start state. That is an explanation consistent with the bytes, not a measured fact. With a 1 Hz collector and
over a second from the cgroup's discovery to `StartedAt` (here at least 1.7 s under TCG), rows in (sec(D), sec(S)]
are the expected outcome of a working collector; 1a rejects them because "no instance was running to measure" and
"the first row after S must come at least one sampling interval (1 s) after sec(S)".

## 2. Options, prospective; the collector's file stays byte for byte

Common to all: conditions 1–5 of 1a (D and S), the 5 s rule on both edges, every other container's rule and
`analyze.py` unchanged; each a new tooling head (offline, tests red first, then a dated decision); the SUT
candidate (image `9a293fe1…`) untouched; none makes a past run valid.

**Option A, transition rows reported, not rejected (validator only).** Replace the two "rejected" bullets of 1a's
checks on C with:

> A row of C stamped after sec(D) and at or before sec(S), only when sec(S) > sec(D) and never after sec(E) when
> the interval is capped, is a *transition row*: the cgroup exists before the daemon stamps `start`. It stays in
> the file, is reported with its values (`resources_proved_down.transition_rows`) and neither opens nor closes an
> edge. It is admissible only if `.lifecycle.csv` records C's id `disappeared` then `appeared`, both after the last
> row at or before sec(D) and at or before the first transition row; otherwise every such row is rejected whatever
> its values, as now. The first row after the interval is the first stamped at or after sec(S) + one sampling
> interval, as now.

This run's file would meet it; transition rows still count for the 30-instant and coverage rules and enter
`analyze.py`'s aggregates. Their admissibility rests on the instrument's own lifecycle file: the daemon's D and S
still bound which rows can be transition rows, but 1a's value-independent rejection is kept only when the pair is
absent. Cases beside U1–U11 and the pinned cases of `test_proved_down.py`: A1 this run, accepted, two rows
reported; A2 no `appeared`, rejected; A3 `appeared` after the transition row, rejected; A4 zero-filled rows
without the pair, rejected (U7 kept); A5 no transition row shortens the edge after; A6 `appeared` in sec(S):
U1–U11 unchanged; A7 capped: a row after sec(E) is no transition row, file rejected (pinned 10:03:01 case); A8
sec(D) = sec(S): that second's row stays rejected (pinned conservative case).

**Option B, the row checks end at the collector's own reappearance (validator only).**

> For the checks on C the interval runs from sec(D) to A, the stamp at which `.lifecycle.csv` records C's id
> `appeared` after its `disappeared`. Rows after sec(D) and before A are rejected whatever their values; rows at or
> after A are ordinary. The edge after is the first row after A minus sec(E), floored at zero. Without the pair
> there is no interval and the ordinary rule decides.

Simpler, but the boundary moves to the instrument's own discovery and the one-interval-after-sec(S) sub-rule is
dropped (the 13:37:18Z row counts). Cases: B1 this run, accepted; B2 a row before A, rejected; B3 no pair, no
interval; B4 A plus one interval over 5 s after sec(E), edge after fails; B5 U8–U11 unchanged.

**Option C, collection correction.** The collector reads the container's `State` from the `config.v2.json` it
already opens and writes a lifecycle row `pre_start`, no CSV row, while `Running` is not yet true; 1a is then met
unchanged. Consequences: a new collector sha256 (a changed file on the guest, not the image, containers or
configuration) whose state-file timing needs a diagnostic session first; the pre-start readings are no longer
recorded, against raw-row retention.

**Recommendation: Option A.** The smallest change that names the rows for what the bytes support, keeps 1a's
interval and edge rules, changes nothing on the guest and makes this run's package its fixture. B lets the
instrument bound its own exemption; C changes the deployed instrument unobserved and discards readings. A would
not make T6 pass (section 3), qualify `controller_restart-r03` or authorise a repeat: whether and under which run
identity T6 runs again is a separate decision, with the SUT shown unchanged and prior results preserved.

## 3. The timely-delivery problem, separately

Independent of section 2. The Project Manager's accounting: 6,720 valid sent identities; the initial events copy
holds 4,800 accepted (4,718 by the controller deadline, 82 late), 1,920 without result; the post-drain copy holds
all 6,720 uniquely accepted, 2,002 beyond the deadline, zero absent, zero duplicate-only. "lost 2,002" is the
deadline metric (marker plus 60 s on the controller clock), not permanent loss; 82 is not the eventual lateness.
No option above changes these figures, which on a valid run would miss C12 (`lost = 0`, late included; decision 3):
the throughput finding of `nominal-r02` (4,584/6,720 timely at the same 11.2 msg/s, reported only). A runtime
change aimed at it creates a new candidate and needs an explicit requalification plan, every family re-run, prior
results kept. Not proposed: a lower load, a longer deadline, or C12 as pilot-only. On a valid run these figures
would fail the timed criterion and be a sizing finding (ADR 0011, throughput choice T1); on this invalid run they
remain observations, neither a qualifying failure verdict nor a capacity claim.
