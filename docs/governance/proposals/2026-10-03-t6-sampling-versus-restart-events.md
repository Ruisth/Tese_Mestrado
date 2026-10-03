# T6: resource sampling versus the restart's Docker events (2026-10-03)

**Status: PROPOSED, for Rui's decision. Adopts nothing.** No rule, threshold, deadline, load, controller,
launcher, image or frozen helper changes here. `controller_restart-r03` stays invalid under decision 1a as adopted
([pending-decisions page](2026-09-29-g3-pending-decisions.md)); no row is deleted, zero-filled or relabelled; the
sealed package is untouched. Written from existing bytes only, at the Project Manager's request of 2026-10-03.

## 1. What the bytes show

Sources: the T6 package `output_test/runs/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01/raw/controller_restart-r03/`
(read only); at `80e833f`, `src/deployment/scripts/collect-resources.sh` (deployed sha256 `11444c0a…`),
`src/egw_experiments/resources.py` and `proved_down.py`. Every instant is on the guest clock.

**Three timestamps meet at the restart.** A Docker event's `timeNano` is the daemon's clock when it records the
action. `StartedAt` is `docker inspect`'s `State.StartedAt`, set when the container's process was started. A
collector row carries a **whole second taken before the reads**: the shell sleeps to a slot aimed 0.5 s into a
wall-clock second (paced on `/proc/uptime`), discovers the cgroup directories whose `cpu.stat` and
`memory.current` exist, then starts awk, whose first statement takes `systime()` and only then reads each
directory. A stamp `hh:mm:ssZ` means "discovered just before, and read just after, an instant in [ss.0,
ss + 1.0)", nominally near ss.5, moved by the guest's clock steps (18 withheld samples here). A directory first
discovered gives `appeared` in `.lifecycle.csv` and primes the CPU delta without a row; one no longer discovered
gives `disappeared`.

| Instant | Source | `egw-controller-1` (id `a7428fc5…`) |
|---|---|---|
| 13:37:11.282 | event `kill`, signal 15 | the stop of `docker compose restart controller` begins |
| 13:37:11Z | row `70.51,69947392,26.06` | the old process's last row: 66.7 MiB of its 256 MiB limit |
| 13:37:11.847 | `controller.log` | `Finished server process [1]` |
| 13:37:12Z | lifecycle `disappeared` | no cgroup found; no rows 13:37:12Z–16Z |
| 13:37:13.997 / **14.060** | events `stop` / **`die`** (exit 0) | **D**; sec(D) = 13:37:14 |
| 13:37:16Z | lifecycle `appeared` | the cgroup is back and readable; priming sample, no row |
| 13:37:17Z | row `0.00,2703360,1.01` | no CPU, 2.58 MiB: **rejected**, "between the die and the start" |
| 13:37:18.699 | `StartedAt` | the process was started |
| **13:37:18.762** | event **`start`** (`restart` at .785) | **S**; sec(S) = 13:37:18; S − `StartedAt` = 0.063 s |
| 13:37:18Z | row `16.06,3588096,1.34` | 3.42 MiB: **rejected**, "in the second of the start" |
| 13:37:19Z | row `83.63,9887744,3.68` | first row at or after sec(S) + 1 s: edge after 1.0 s |
| 13:37:28.984 | `/metrics` `started_at` | the new process answers (first reading 13:37:30.09Z) |

Edge before 3.0 s and edge after 1.0 s pass; the two rows are the only problems
(`resources_proved_down.rejected_rows`); the controller has 580 rows against 585 for every other container.

**The mismatch.** The cgroup the collector measures was gone by the 13:37:12Z sample, 1.1–2.1 s *before* the
daemon stamped `die`, and back by the 13:37:16Z sample, 1.7–2.8 s *before* `StartedAt` and `start`; the 13:37:17Z
row was read 0.8–1.8 s before `start`. A container runtime creates the cgroup and places the container's init in
it before the process is started, and the daemon records `start` after that: no CPU and 2.6 MiB fit that pre-start
state, and the 13:37:18Z row a second in which the exec happened. That is an explanation consistent with the bytes,
not a measured fact: the collector records neither the sub-second instant nor which process the cgroup held, and
the withheld sample at 13:37:18Z ("a clock stepped back, or two samples in one second") leaves it undecidable
whether that row preceded `StartedAt`. What the bytes do establish: with a 1 Hz collector and a create-to-start
above one second (here at least 1.7 s under TCG), rows stamped in (sec(D), sec(S)] are the expected outcome of a
working collector. Decision 1a's premise, that the cgroup appears at S so that the sample in sec(S) primes and the
first row comes after, does not hold on this runtime.

## 2. Options, prospective; the collector's file stays byte for byte

Common to all: conditions 1–5 of decision 1a that establish D and S, the 5 s rule on both edges, every other
container's rule and `analyze.py` are unchanged. Each is a new tooling head (an offline change with its tests, red
first, then a dated decision); the SUT candidate (image `9a293fe1…`, compose, broker configuration) is untouched.
None makes a past run valid.

**Option A, transition rows reported, not rejected (validator only).** Replace the two "rejected" bullets of 1a's
checks on C with:

> A row of C stamped after sec(D) and at or before sec(S) is a *transition row*: the cgroup the collector reads
> exists before the daemon stamps `start`. It stays in the file, is reported with its values
> (`resources_proved_down.transition_rows`) and neither opens nor closes an edge. It is admissible only if
> `.lifecycle.csv` records C's container id `disappeared` and then `appeared`, both stamped after the last row at or
> before sec(D) and at or before the first transition row; otherwise every such row is rejected whatever its values,
> as now. The first row after the interval is the first row stamped at or after sec(S) + one sampling interval, as now.

This run's file would meet it; the lifecycle cross-check keeps the fabrication guard; the transition rows still
count for the 30-instant and coverage rules and enter `analyze.py`'s aggregates as rows of C (2 of 580 here).
Cases, beside U1–U11 of `test_proved_down.py`: A1 this run's rows, accepted, two transition rows reported; A2 no
`appeared` in the lifecycle file, rejected; A3 `appeared` stamped after the transition row, rejected; A4 zero-filled
or interpolated rows without the lifecycle pair, rejected (U7 kept); A5 a transition row never shortens the edge
after; A6 `appeared` in sec(S): no transition row, U1–U11 unchanged.

**Option B, the row checks end at the collector's own reappearance (validator only).**

> For the checks on C, the interval runs from sec(D) to A, the stamp at which `.lifecycle.csv` records C's id
> `appeared` after its `disappeared`. Rows stamped after sec(D) and before A are rejected whatever their values;
> rows at or after A are ordinary rows. The edge after is the first row after A minus sec(E), floored at zero.
> Without the `disappeared`/`appeared` pair there is no interval, and the ordinary rule decides the file.

No rejected row here and simpler than A, but the boundary moves from a daemon-stamped event to the instrument's
own discovery, and the sub-rule that the first counted row comes one interval after sec(S) is dropped (the
13:37:18Z row, a second spanning the exec, counts). Cases: B1 this run, accepted; B2 a row before A, rejected; B3
no `appeared` after `disappeared`, no interval; B4 A plus one interval more than 5 s after sec(E), edge after
fails; B5 U8–U11 unchanged.

**Option C, collection correction: the collector marks the pre-start cgroup.** It already opens the container's
`config.v2.json` for its name; the same file carries the daemon's `State` (`Running`, `Pid`, `StartedAt`), to be
confirmed on the guest first. A readable cgroup whose state does not yet show `Running` true with a `StartedAt`
later than its `disappeared` would write a lifecycle row `pre_start` and no CSV row; the first sample showing it
writes `running` and primes, and 1a is met unchanged. Consequences: a new collector sha256, the deployed
instrument's identity (the preflight installs it and keeps the previous copy under
`/opt/egw/evidence/collector-previous/`): a changed file on the guest, though not the image, the containers or the
configuration; the state file's timing has never been observed on the guest and needs a diagnostic session; the
pre-start readings are no longer recorded at all, the opposite of raw-row retention. Cases (self-test tree): C1
`Running` false, `pre_start`, no row; C2 then `Running` true with a later `StartedAt`, `running`, priming, first
row one sample later; C3 state unreadable, rows as today.

**Recommendation: Option A.** The smallest change that names the rows for what the bytes support, keeps every
guard 1a has, changes nothing on the guest, and makes this run's package its fixture. B lets the instrument bound
its own exemption; C changes the deployed instrument before its timing was observed, and discards readings.
Adopting A would not make T6 pass (section 3), would not qualify `controller_restart-r03` and would not authorise
a repeat: whether T6 runs again, and under which run identity, is a separate decision, with the next preparation
showing the SUT unchanged and prior results preserved.

## 3. The timely-delivery problem, separately

Independent of section 2. The Project Manager's read-only accounting: 6,720 valid sent identities; the initial
events copy holds 4,800 accepted (4,718 by the controller deadline, 82 late) and 1,920 with no result; the post-drain
copy holds all 6,720 uniquely accepted, 2,002 beyond the same deadline, zero absent, zero duplicate-only. "lost
2,002" is the deadline metric (the marker plus 60 s, on the controller clock), not permanent loss, and 82 is not the
eventual lateness. Recovery was 4.75 s functional and 11.9 s endpoint, within `RESTART_RECOVERY_MAX_S`. A file that
met any option above would still fail C12 (`lost = 0`, late confirmations included; decision 3) on these figures, as
`nominal-r02` (4,584/6,720 timely) did at the same 11.2 msg/s. Any runtime change aimed at it (controller, Ditto,
broker, compose limits) creates a new candidate, a new controller image or configuration identity, and needs an
explicit requalification plan with every family re-run on it, prior results kept for assessment. Not proposed
here, and outside this page: a lower load, a longer deadline, or reading C12 as pilot-only. The miss is a sizing
finding (ADR 0011, throughput choice T1) and stays a failure of the timed criterion.
