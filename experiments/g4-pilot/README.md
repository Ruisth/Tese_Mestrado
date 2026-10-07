# G4 bounded pilot — the input plan

`g4_pilot_plan.json` is the input of the bounded pilot of gate G4: "a short
nominal run, the plan's nominal duration, the load sweep and one bounded soak",
in order (`docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md:643-645`), with
the figures of runbook section 8 item 1 (`docs/setup/qemu_integrated_gateway.md:1544`):
five measured runs in four stages, one run per stage and per sweep level. The
route is the harness's existing one (`run --plan --base-dir`, `analyze
--base-dir --plan`); the file is reviewed input for it, not a new engine.
Nothing in it has run.

Pilot data is **non-citable** and no pilot number enters the dissertation
(`INTEGRATED_DEVELOPMENT_PLAN_2026.md:654-655`). The five runs are **not
campaign attempts**, and neither are G3's data (the project-management scope
judgement of 2026-10-07, kept outside the repository). The plan names no
execution mode: that is declared for each run when it is made, never supplied
by its input.

| | |
|---|---|
| File | `experiments/g4-pilot/g4_pilot_plan.json`: the campaign plan's canonical serialisation (`plan_to_json`: sorted keys, two-space indent, LF, one trailing newline, no timestamp) |
| sha256 | `8c011edd3e36df46ef3d27e4e6075954bb8d302393db5a80113260f3f66b8281` |
| Written by | [`tools/session/g4_pilot_plan.py`](../../tools/session/g4_pilot_plan.py) `write --master-seed 20261007`, with G3's plan as it stood after test 6 and the finite proof r03 plan, both held in `docs/evidence/`, passed as `--against`, and `--against-seed 42 --against-seed 7` |
| Master seed | `20261007`: a **working choice** presented to the student, after the finite proof's date convention (`20260925`). The tool has no default; another master seed is a new build with new seeds, a new file and a new sha256 |
| Pinned by | [`src/tests/test_g4_pilot_plan.py`](../../src/tests/test_g4_pilot_plan.py): the file's bytes equal `build_pilot_plan(20261007)`, and this README names its sha256 |

## The plan

| Order | Stage | `run_id` | `condition_id` | `scenario` | `rate_msg_s` | `duration_s` | `warmup_s` | `cooldown_s` | `seed` |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `g4pilot-s1-nominal-0120s-11p2mps-a01` | `nominal` | `nominal` | 11.2 | **120** | **0** | 0 | 3340462373 |
| 2 | 2 | `g4pilot-s2-nominal-0600s-11p2mps-a01` | `nominal` | `nominal` | 11.2 | 600 | 120 | 0 | 2626471893 |
| 3 | 3 | `g4pilot-s3-loadsweep-0300s-010mps-a01` | `load_sweep` | `load-sweep` | 10.0 | 300 | 0 | 120 | 3694409732 |
| 4 | 3 | `g4pilot-s3-loadsweep-0300s-050mps-a01` | `load_sweep` | `load-sweep` | 50.0 | 300 | 0 | 120 | 174127109 |
| 5 | 4 | `g4pilot-s4-soak-3600s-11p2mps-a01` | `soak` | `soak` | 11.2 | **3600** | 0 | 0 | 2294608585 |

Bold marks a departure from the frozen condition. Every entry has `runner`
`simulator`, `repetition` 1 and `status` `planned`.

- **Entries.** Each is `plan_gen._run_entry` of its frozen condition with the
  pilot's figures, numbered in stage order, plus one inert `pilot` block:
  `stage`, `label` (`PILOT - NON-CITABLE`) and `deviations` (one
  `{field, frozen, pilot, basis}` per figure that departs). Keeping the frozen
  `condition_id` keeps the unchanged validity rules on these runs: controller
  metrics are mandatory evidence on `load_sweep` and `soak`
  (`src/egw_experiments/run.py:508-510`), and the strict warm-up rule covers
  `nominal`, `load_sweep` and `soak` (`run.py:723-725`). Nothing in `run`,
  `collect` or `analyze` reads the `pilot` block; the harness echoes the whole
  entry into the run's manifest as `config.plan_entry` (`run.py:5768-5769`), so
  every run's own record states its departures.
- **`conditions`.** The three frozen records, verbatim
  (`CONDITIONS_BY_ID[...].to_dict()` of `nominal`, `load_sweep`, `soak`): the
  reference the entries' departures are stated against. The two nominal
  entries differ from each other, so no single edited record could describe
  both.
- **Top-level `pilot`.** `label`, `purpose`, `non_citable: true`,
  `not_campaign_attempts: true`, `deviations_from_protocol` (one row for every
  condition of the frozen protocol) and `sources` (the source of every field of
  the plan and of every entry).
- **`plan_version`** `1.0`, **`protocol_version`** `1.0.0`: the frozen protocol
  is not changed.

**Run ids** follow `g4pilot-s<stage>-<kind>-<dddd>s-<rate>mps-a<NN>`
(`<kind>` one of `nominal`, `loadsweep`, `soak`; `<rate>` three digits or
`<int>p<digit>`). No such id starts with a condition id or ends in `-rNN`, so
none can be read as a campaign id (`load_sweep-NNNmps-rNN`,
`<condition>-rNN`: `src/egw_experiments/plan_gen.py:96-105`); the stage,
duration and rate tokens equal the entry's figures (the tool and the tests
check it); and at most 57 characters keep the harness's warm-up id
`<run id>.warmup` inside CONTRACTS 2. `aNN` is the attempt: a repeat, only by
the student's decision, takes `a02`, a new seed derived from the new id and its
lineage (`INTEGRATED_DEVELOPMENT_PLAN_2026.md:959-960`); the tool has no repeat
command yet.

## Source mapping, field by field

The file's `pilot.sources` holds the same mapping. Paths are from the
repository root; `protocol.py`, `plan_gen.py` and `run.py` are under
`src/egw_experiments/`, `scenarios.py` and `devices.py` under
`src/egw_simulator/`, the runbook is `docs/setup/qemu_integrated_gateway.md`
and the plan is `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`.

| Field | Stage 1 (entry 1) | Stage 2 (entry 2) | Stage 3 (entries 3 and 4) | Stage 4 (entry 5) |
|---|---|---|---|---|
| `condition_id` | `nominal`: `protocol.py:277`; runbook 1544 (`--scenario nominal`) | as stage 1 | `load_sweep`: `protocol.py:297`; runbook 1544 (`load-sweep`) | `soak`: `protocol.py:398`; runbook 1544 (`--scenario soak`) |
| `runner` | `simulator`: `protocol.py:278` | as stage 1 | `protocol.py:298` | `protocol.py:399` |
| `scenario` | `nominal`: `protocol.py:279`; `scenarios.py:91-96` | as stage 1 | `load-sweep`: `protocol.py:299`; `scenarios.py:97-103` | `soak`: `protocol.py:400`; `scenarios.py:120-125` |
| `rate_msg_s` | 11.2: `protocol.py:285` (`NOMINAL_RATE_MSG_S`, `:54`); `scenarios.py:91-96` | as stage 1 | 10.0 and 50.0: `protocol.py:304` (the first two of four levels); runbook 1544 ("at 10 and 50 msg/s") | 11.2: `protocol.py:406`; `scenarios.py:120-125`; `devices.py:27` |
| `duration_s` | **120**: runbook 1544 (`--duration 120`); plan 644 ("a short nominal run") | 600: `protocol.py:281`; runbook 1544 ("the plan's nominal duration (600 s)"); plan 644-645 | 300: `protocol.py:301`; runbook 1544 ("300 s each") | **3600**: runbook 1544 (`--duration 3600`); plan 645 ("one bounded soak") |
| `warmup_s` | **0**: request annex of 2026-10-07, recommendation P2 (`output_test/decisions/2026-10-07_g4-pilot-request-annex.md:153`, kept outside the repository); runbook 1544 names no warm-up | 120: `protocol.py:282` (and `:18-20`); run as `<run id>.warmup` with the same seed (`run.py:5033-5054`) | 0: `protocol.py:302` | 0: `protocol.py:403` |
| `cooldown_s` | 0: `protocol.py:283` | as stage 1 | 120: `protocol.py:303`; what is left of it after the 60 s confirmation window is slept after each sweep run, the last included (`run.py:5968-5973`) | 0: `protocol.py:404` |
| `repetition` | 1: runbook 1544 ("one short nominal run") | 1: runbook 1544 | 1 per level: runbook 1544 | 1: `protocol.py:401`; runbook 1544 |
| `seed` | `derive_run_seed(master seed, run id)`: `plan_gen.py:43-50` | as stage 1 | as stage 1 | as stage 1 |
| `run_id` | fresh, never a campaign id: plan 959-960; `plan_gen.py:96-105` | as stage 1 | as stage 1 | as stage 1 |
| `status` | `planned`: `plan_gen.py:71` | as stage 1 | as stage 1 | as stage 1 |
| `order` | stage order: plan 643 ("in order"); runbook 1544 | as stage 1 | 3, then 4: runbook 1544 | 5 |

Plan level: `plan_version` `plan_gen.py:35`; `protocol_version` `protocol.py:49`;
`conditions` `protocol.py:276-295`, `296-321` and `397-420`, verbatim;
`master_seed` the student's decision, no default; `non_citable` plan 654-655;
`not_campaign_attempts` the project-management scope judgement of 2026-10-07
and plan 650-651 (the attempt target is not the frozen set).

## Every departure from the frozen conditions

**Entries** (each declared in its own `pilot.deviations`; the tests compute the
departures from the figures and the frozen records and require the declared
ones to equal them, so none is undeclared):

| Entry | Field | Frozen | Pilot | Basis |
|---|---|---|---|---|
| 1 | `duration_s` | 600 (`protocol.py:281`) | 120 | runbook 1544; plan 644 |
| 1 | `warmup_s` | 120 (`protocol.py:282`) | 0 | request annex recommendation P2; a working choice (see [Stage 1 warm-up](#stage-1-warm-up-a-working-choice)) |
| 5 | `duration_s` | 86,400 (`protocol.py:402`) | 3,600 | runbook 1544; plan 645; a bounded run is no C13 evidence (`docs/claim_evidence_matrix.md:174`) |

**Conditions** (the plan's `pilot.deviations_from_protocol`, one row for every
condition of the frozen protocol, so plan 958's "the bounded pilot covers all
conditions" is recorded and never silently waived):

| Condition | Frozen runs | Pilot runs | Departure |
|---|---|---|---|
| `qemu_boots`, `cold_start`, `twin_creation` | 5, 10, 10 | 0 | operator-measured; not run in this pilot |
| `smoke_sequence` | 10 | 0 | not run in this pilot |
| `nominal` | 10 × 600 s after 120 s | 2 | two runs of different shape: 120 s with no warm-up; 600 s after 120 s |
| `load_sweep` | 10 per level at 10, 50, 100, 250 msg/s, order randomised from the master seed (`protocol.py:21-24`; `plan_gen.py:84-98`) | 2 | one run at each of 10 and 50 msg/s, in that fixed order (50 msg/s only after 10); 100 and 250 msg/s not run |
| `invalid_payload`, `dropout_reconnect`, `controller_restart` | 3 each | 0 | not run in this pilot |
| `soak` | 1 × 86,400 s | 1 | one run of 3,600 s (entry 5) |

What is not run is not waived: coverage and any extrapolation are recorded for
the G4 decision, which this plan does not make.

### Stage 1 warm-up (a working choice)

The frozen nominal warm-up is 120 s (`protocol.py:282`); the runbook names only
`--scenario nominal --duration 120` for stage 1; the request annex recommends
writing warm-up 0 into the entry, rather than skipping a warm-up. The plan
does that, and states it in entry 1's `pilot.deviations`. Two consequences:

- **The harness records no deviation for it.** It flags a skipped warm-up only
  on `--skip-warmup` (`run.py:3981-3991`, `5563-5570`), which this plan does
  not use, and `--allow-protocol-deviation` is not used either. Entry 1's
  manifest says `warmup_s: 0`, and its `config.plan_entry.pilot.deviations`
  says why; the tests pin that no `skip_warmup` deviation is recorded.
- **First contact falls inside the measured window.** A fresh seed means three
  new devices (`devices.py:38-45`), so their first-contact policy and thing
  creation, which a warm-up absorbs, happen inside entry 1's 120 s: stage 1 is
  a whole-chain check, not a nominal measurement.

The alternative is the frozen 120 s warm-up for stage 1 as well
(protocol-consistent; about 2 more minutes and 1,344 more messages). Choosing
it changes the tool's reviewed constants and gives a new build.

## Seeds and devices

Every seed is `derive_run_seed(master seed, run id)`, so fresh ids give fresh
seeds. Every `write` checks, and the tests repeat, that the five seeds are
pairwise distinct and disjoint from: every seed of G3's plan (the campaign
plan of master seed 42, 95 entries, with its supplement `controller_restart-r04`,
seed 1715385812); the finite proof r03 (265481284); and the runbook's
`run_test` seeds 42 and 7 (42 is also the simulator's default seed). The
fifteen device UUIDs they give are disjoint from the devices of all of these.
`--against` adds further plans (the proof plans of r01 and r02, kept on the
host, for example) and `--against-seed` further seeds.

The campaign's run ids are fixed, but its seeds depend on a master seed that is
fixed only at the freeze: the check is repeated then, as `write --against
<the campaign plan>` to a scratch output. Fifteen new twins and policies in
Ditto and MongoDB over the pilot are storage growth the pilot measures anyway.

## Operating rules for the plan files

1. **A dedicated tree**, for example `~/egw-tcg/g4-pilot/{plan,results}`,
   never under `~/egw-tcg/pilot/`, which is G3's tree (its plan and its
   results). The tool refuses an output, a plan or a results base there, as
   given, with `..` folded or through a symbolic link (`--forbid-under`,
   default `~/egw-tcg/pilot`).
2. **A sealed copy and a working copy.** `write` writes the sealed copy once
   (`plan/g4_pilot_plan.sealed.json`; write-once) and it should be byte-equal
   to this file (same master seed, same sha256); its sha256 goes into the
   host-preparation package and the file is made read-only. The working copy
   `plan/g4_pilot_plan.json` is a byte copy of it. `run` rewrites the plan it
   is given (`running` when it starts, then `completed` or `failed` with
   `result_dir`, `finished_utc` and `validity`: `run.py:4752-4757`,
   `5959-5966`) and never reads `status`, so it is only ever given the working
   copy.
3. **Before each run**, `check --plan <working> --sealed <sealed>
   --sealed-sha256 <recorded> --base-dir <pilot>/results --run-id <run id>`:
   it writes nothing and refuses unless both copies are canonical, the sealed
   one is this tool's plan with every entry still `planned`, the working one
   holds every frozen field of it, the run id is `planned` with every entry
   before it run, `raw/<run id>` is absent, nothing lies under G3's tree and
   the entry is one the harness can run as planned (the harness itself reads
   the figures only after it has created the run directory and marked the
   entry `running`: `run.py:4752-4757`, `4788-4796`). Keep the working plan
   as `campaign_plan.before.json` before the run and as
   `campaign_plan.after.json` after it, as G3 did.
4. **Explicit flags, always.**
   - `run --plan <working> --base-dir <pilot>/results --run-id <run id> ...`:
     the defaults are the clone's `experiments/campaign_plan.json` and
     `experiments/results` (`src/egw_experiments/cli.py:574-585`;
     `run.py:355-356`). A forgotten `--plan` fails closed, since no other plan
     holds a pilot id (`run.py:4610-4615`); a forgotten `--base-dir` would put
     the run in the clone's tree.
   - `collect --plan <working> --base-dir <pilot>/results` (`cli.py:732-743`).
   - `analyze --base-dir <pilot>/results --plan <sealed>` with
     `EGW_CAMPAIGN_PLAN` unset (`env -u EGW_CAMPAIGN_PLAN ...`;
     `src/egw_experiments/analyze.py:1234-1236`), and the output checked for
     an `[analyze] WARNING: campaign plan ... could not be read` line: an
     unreadable `--plan` degrades completeness to counts and still exits 0
     (`analyze.py:3458-3467`).
5. **Never** `plan`, `plan-supplement` or `campaign` (other than `--dry-run`,
   which only prints) on the pilot plan or G3's; never `analyze` of
   `~/egw-tcg/pilot/results`. `analyze` wipes and rebuilds `processed/` and
   `figures/` of the base it is given (`analyze.py:3469-3470`): keep a copy
   per stage if per-stage outputs are wanted.

Illustrative only (no session is authorised by this file):

```sh
PYTHONPATH="$REPO/src" python "$REPO/tools/session/g4_pilot_plan.py" write --master-seed 20261007 \
  --out ~/egw-tcg/g4-pilot/plan/g4_pilot_plan.sealed.json \
  --against ~/egw-tcg/pilot/campaign_plan.json --against-seed 42 --against-seed 7
PYTHONPATH="$REPO/src" python "$REPO/tools/session/g4_pilot_plan.py" check \
  --plan ~/egw-tcg/g4-pilot/plan/g4_pilot_plan.json \
  --sealed ~/egw-tcg/g4-pilot/plan/g4_pilot_plan.sealed.json --sealed-sha256 "$SEALED_SHA256" \
  --base-dir ~/egw-tcg/g4-pilot/results --run-id g4pilot-s1-nominal-0120s-11p2mps-a01
```

## How `analyze` reads a five-entry plan

The tests pin each point below (`evaluate_acceptance`, `detect_saturation` and
`summarize_by_condition` with the five entries).

- **Completeness fails by construction for six of the seven simulator
  conditions.** The expected count comes from the frozen protocol
  (`analyze.py:2566-2568`), and a plan listing a different number fails
  identity completeness (`analyze.py:2591-2597`), which gates every
  substantive row to False (`analyze.py:2614-2618`): `smoke_sequence` 0 of 10,
  `nominal` 2 of 10, `load_sweep` 2 of 40, `invalid_payload`,
  `dropout_reconnect` and `controller_restart` 0 of 3 ("the campaign plan
  lists N run(s) for this condition, the frozen protocol plans M"; the
  wording is the analysis's, and the plan meant is this one).
- **The soak is the exception.** One listed, one planned: with a valid soak
  run whose identity matches, its `runs_complete` **passes** and its rows are
  evaluated ungated. `measured_window_ge_24h` fails by construction (3,600 s
  against 86,400 s); the coverage and cadence rows, `no_unrecovered_interruption`
  and `controller_metrics_reconciled` can read True on real data;
  `delivery_descriptive` stays empty. **None of these soak rows is C13
  evidence**: a bounded stability run "does **not** satisfy this Definition of
  Done" (`docs/claim_evidence_matrix.md:174`), and a pilot report must say so.
- **Saturation** is `insufficient-evidence` at every planned load (10, 50, 100
  and 250 msg/s), since ten runs per load are expected (`analyze.py:3004-3007`);
  the per-load raw `saturated` flag still reflects the single run.
- **The summary pools the 120 s and the 600 s nominal runs.** It groups by
  condition and rate (`analyze.py:2435-2437`), so entries 1 and 2 make one
  `nominal` row at 11.2 msg/s with n = 2 and a confidence interval: a
  mixed-duration aggregate. Never report that row; read pilot results **per
  run**, from `per_run.csv`, which carries `duration_s`.
- **Recovery** reports "the campaign plan lists no controller_restart run"
  (`src/egw_experiments/recovery_qualification.py:478-483`).
- **Isolation** holds only when `--base-dir` is the pilot base; the tests show
  that an explicit `--plan` wins over `EGW_CAMPAIGN_PLAN` and that a sibling
  tree's `processed/` and `figures/` are left as they were.

## Operational contract (proposal, not adopted)

To be written at integration.
