# T6: resource sampling versus the restart's Docker events (2026-10-03)

**Status: option A ADOPTED by Rui on 2026-10-05, with the Project Manager's conditions; options B and C NOT
adopted.** Prospective, for the new G3 T6 run only (the Project Manager's register entry of 2026-10-05, 15:14 WEST,
and the decision note of the same date, both held locally, outside the repository): admitted transition rows,
measured zeros included, count for the 30 distinct instants, take part in the existing coverage calculations and
enter the existing CPU/RAM aggregates; `analyze.py` is unchanged; no campaign criterion is adopted. Implemented
offline as the opt-in `run --restart-transition-rule 1a-option-a-2026-10-05`. No threshold, deadline, load,
controller, launcher, image or frozen helper changes; `controller_restart-r03` stays invalid under decision 1a
([pending decisions](2026-09-29-g3-pending-decisions.md)), its sealed package and verdict untouched. Written
2026-10-03 as a proposal, from existing bytes only, at the Project Manager's request; the four qualifications of
the Project Manager's review of 2026-10-03 (19:59 WEST) are worked into the text below, each marked *(2026-10-05)*.
*(Until 2026-10-05 this line read "PROPOSED, for Rui's decision. Adopts nothing".)*

## 1. What the bytes show

Sources: `output_test/runs/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01/raw/controller_restart-r03/`;
`collect-resources.sh` (deployed sha256 `11444c0a…`), `resources.py` and `proved_down.py` at `80e833f`. Guest
clock throughout; `timeNano` and `StartedAt` are the daemon's. A row's stamp is a **whole second taken before
the reads**: the shell sleeps to a slot 0.5 s into a second (paced on `/proc/uptime`), finds the cgroup
directories holding `cpu.stat` and `memory.current`, then awk takes `systime()` and reads them; a directory
first found gives `appeared` in `.lifecycle.csv` (priming, no row), one no longer found `disappeared`.

| Instant | `egw-controller-1` |
|---|---|
| 13:37:11Z | row `70.51,69947392,26.06`: old process's last (66.7 MiB) |
| 13:37:12Z | lifecycle `disappeared`; no rows 12Z–16Z |
| **13:37:14.060** | **`die`** (`kill` 11.282, `stop` 13.997) = **D**; sec(D) = 13:37:14 |
| 13:37:16Z | lifecycle `appeared` |
| 13:37:17Z | row `0.00,2703360,1.01` (no CPU, 2.58 MiB): **rejected** "between the die and the start" |
| **13:37:18.762** | **`start`** (`StartedAt` 18.699) = **S**; sec(S) = 13:37:18 |
| 13:37:18Z | row `16.06,3588096,1.34` (3.42 MiB): **rejected** "in the second of the start" |
| 13:37:19Z | row `83.63,9887744,3.68`: first after sec(S) + 1 s |
| 13:37:28.984 | `/metrics` `started_at`: the new process's own start stamp (first `/metrics` answer 13:37:30.090Z on the guest clock; 13:37:30.213Z as the harness host stamped it) |

**The mismatch.** Both edges pass (3.0 s, 1.0 s); only the two rows fail (`rejected_rows`). By its stamps, the
collector no longer found the cgroup in the sample stamped 13:37:12Z, before `die`, and found it again in the one
stamped 13:37:16Z, before `StartedAt`; the rows stamped 13:37:17Z and 13:37:18Z follow. Each stamp is taken when
a sample begins, before its sequential reads, on a guest clock that stepped back 0.62 s at calibration 11: the
stamps bound when the samples began, not when each read completed. The 13:37:18Z sample began (uptime 878.14 s,
about 13:37:18.58 by calibration 10) 0.12–0.74 s before `StartedAt`, depending on which side of that step the
daemon stamped, so whether its reads preceded `StartedAt` is undecidable; nor do the bytes say when the
13:37:17Z reading was taken relative to `start`. *(2026-10-05: the text of 2026-10-03 also said that row "was read
0.8–1.8 s before `start`" and put the reappearance "1.7–2.7 s before `StartedAt`"; both inferred read times from
acquisition stamps and are withdrawn.)* A runtime creates the cgroup and puts the container's init in it before
the process starts; no CPU and 2.6 MiB fit that state (consistent with the bytes, not measured). With a 1 Hz
collector, rows stamped in (sec(D), sec(S)] are what a working collector can produce while the cgroup exists
before the daemon stamps `start`; 1a rejects them ("no instance was running to measure").

## 2. Prospective options; the collector's file stays byte for byte

All three were written to keep conditions 1–5 of 1a (D and S), the 5 s rule on both edges, every other
container's rule and `analyze.py` (B does not keep the edge after a capped restart; see B); each is a new tooling
head (offline, tests red first, dated decision), the SUT candidate (image `9a293fe1…`) untouched, no past run
made valid.

**Option A, transition rows reported, not rejected (validator only)**: 1a's two "rejected" bullets on C become

> A row of C stamped after sec(D) and at or before sec(S), only when sec(S) > sec(D) and never after sec(E) when
> the interval is capped, is a *transition row*: the cgroup exists before the daemon stamps `start`. It stays in
> the file, is reported with its values (`resources_proved_down.transition_rows`) and neither opens nor closes an
> edge. It is admissible only if `.lifecycle.csv` records C's id `disappeared` then `appeared`, both after the last
> row at or before sec(D) and at or before the first transition row; otherwise every such row is rejected whatever
> its values, as now. The first row after the interval is the first stamped at or after sec(S) + one sampling
> interval, as now.

*(2026-10-05: the clause "the cgroup exists before the daemon stamps `start`" is the proposal's rationale, not established for a row in sec(S) — see section 1; the rows are reported under `resources_transition_rows`.)*

**Adopted 2026-10-05, with the Project Manager's conditions** (the status line); implemented as the opt-in
`run --restart-transition-rule 1a-option-a-2026-10-05`, which reports the rows under the manifest key
`resources_transition_rows`, beside `resources_proved_down` rather than inside it. *(2026-10-05)* **The counting
choice is decided:** admitted transition rows, measured zeros included, count for the 30 distinct instants, take
part in the existing coverage calculations and enter `analyze.py`'s existing aggregates within the current
analysis window, which `analyze.py` reads unchanged; they describe cgroup resources in that window, not a ready
service, and the outage is never declared measured. D and S bound them, but admissibility rests on the
instrument's own lifecycle file: **that witness is the same instrument's record, not independent causal proof**
(it shows when the collector stopped and started finding the container's cgroup); a zero alone proves nothing,
and 1a's value-independent rejection stands without the pair. Cases (U1–U11 and the pinned cases kept): A1 this
run, accepted, two rows reported; A2 no `appeared`, rejected; A3 `appeared` after the transition row, rejected;
A4 zero-filled rows without the pair, rejected (U7 kept); A5 no transition row, shorter edge after; A6 `appeared`
in sec(S), U1–U11 unchanged; A7 capped, a row after sec(E) rejects the file (pinned 10:03:01 case); A8 sec(D) =
sec(S), that second's row stays rejected (pinned conservative case).

**Option B, the row checks end at the collector's own reappearance (validator only).**

> For the checks on C the interval runs from sec(D) to A, the stamp at which `.lifecycle.csv` records C's id
> `appeared` after its `disappeared`. Rows after sec(D) and before A are rejected whatever their values; rows at or
> after A are ordinary. The edge after is the first row after A minus sec(E), floored at zero. Without the pair
> there is no interval and the ordinary rule decides.

Simpler; the boundary becomes the instrument's own discovery and the one-interval-after-sec(S) sub-rule goes
(the 13:37:18Z row counts). Cases: B1 this run, accepted; B2 a row before A, rejected; B3 no pair, no interval;
B4 A plus one interval over 5 s after sec(E), edge after fails; B5 U8–U11 unchanged.

*(2026-10-05)* **B is not recommended in its current form, and not adopted:** it does not keep the capped-edge
protection it claims. Counterexample (the Project Manager's): D = 0, S = 130, E = 120, appearance A = 3, rows at
every second from 4 to 131. B's edge after, max(0, first row after A − E), is 0 s; the retained rule's edge after,
from sec(E) to the first row at or after sec(S) + 1 s (131), is 11 s and rejects.

**Option C, collection correction.** The collector reads `State` from the `config.v2.json` it already opens and
writes a lifecycle row `pre_start`, no CSV row, until `Running` is true. Consequences: a new collector sha256 on
the guest (image, containers and configuration unchanged) after a diagnostic session on state-file timing;
pre-start readings no longer recorded, against raw-row retention. *(2026-10-05: the text of 2026-10-03 added "1a
is met unchanged"; that is not established and is withdrawn - `Running` can already be true during sec(S), whose
row 1a still forbids, and the state can be read after an earlier acquisition stamp.)* Not adopted.

**Recommendation: Option A** (adopted 2026-10-05 with conditions, see the status line): it names the rows for
what the bytes support, keeps 1a's interval and edge rules,
changes nothing on the guest and makes this run's package its fixture; B lets the instrument bound its own
exemption, C changes the deployed instrument unobserved and discards readings. A neither makes T6 pass
(section 3) nor qualifies `controller_restart-r03` nor authorises a repeat (a separate decision; SUT shown
unchanged, prior results kept).

## 3. The timely-delivery problem, separately

The Project Manager's accounting: 6,720 valid sent identities; initial events copy 4,800 accepted (4,718 by the
controller deadline, 82 late), 1,920 without result; post-drain copy all 6,720 uniquely accepted, 2,002 beyond
the deadline, zero absent, zero duplicate-only; "lost 2,002" is the deadline metric, not permanent loss. No
option above changes these figures, which on a valid run would miss C12 (`lost = 0`, late included; decision 3),
the throughput shortfall of `nominal-r02` (4,584/6,720 timely at the same 11.2 msg/s, reported only);
a runtime change aimed at them means a new candidate and an explicit requalification plan (every family re-run,
prior results kept); no lower load, longer deadline or pilot-only C12 is proposed; on this invalid run they
remain observations, neither a failure verdict nor a capacity claim.
