"""Write and check the five-entry input plan of the G4 bounded pilot.

Usage: g4_pilot_plan.py write --master-seed N --out PATH [--against PLAN]...
                              [--against-seed N]... [--forbid-under DIR]
       g4_pilot_plan.py check --plan WORKING --sealed SEALED --base-dir BASE
                              --run-id RID [--sealed-sha256 HEX] [--forbid-under DIR]

The bounded pilot of G4 is "complete, in order, on the integrated emulated
system: a short nominal run, the plan's nominal duration, the load sweep and
one bounded soak" (plan section 4.3), and runbook section 8 item 1 gives its
figures: 120 s of nominal, the 600 s nominal after its warm-up, 300 s of
load sweep at 10 and at 50 msg/s, a 3,600 s soak. The harness route is the
existing one (``run --plan --base-dir``, ``analyze --base-dir --plan``); what
it lacks is reviewed pilot input. This tool writes that input and nothing
else. The five entries are reviewed constants (``PILOT_SPECS``), never
arguments: it is not a general plan generator, and its one input is the
master seed, which has no default (the student's decision, as the finite
proof's was).

Each entry is ``plan_gen._run_entry`` of its frozen condition with the
pilot's figures, so its shape cannot drift from what the harness reads, and
keeps the frozen ``condition_id``, so the unchanged validity rules apply to
it. It carries an inert ``pilot`` block (its stage, the label, and each
figure that departs from its frozen condition with the basis of the
departure), which the harness echoes into the run's manifest
(``config.plan_entry``) and otherwise never reads. The condition records
travel verbatim; the plan's own ``pilot`` block states the purpose, that the
runs are non-citable and are not campaign attempts, every condition-level
departure (counts, rate levels, order, the conditions not run) and the
source of every field. The plan names no execution mode: that is declared
for each run when it is made, never supplied by its input.

``write`` refuses, with nothing written (exit 2): a master seed that is not a
whole number; an output that exists (the plan is write-once) or lies under
the forbidden directory (G3's tree, ``~/egw-tcg/pilot`` by default, as given
or as it resolves); an ``--against`` plan that cannot be read; a pilot run
id an ``--against`` plan holds; a pilot seed, or a device derived from one,
that G3's plan (the campaign plan of master seed 42 with its supplement),
the finite proof r03, the run_test seeds 42 and 7, an ``--against`` plan or
an ``--against-seed`` already spends. It writes the campaign plan's
canonical serialisation and prints one line per entry and the file's sha256.
The text goes to a temporary file beside the output and is published under
the output's name by a hard link, which never replaces a file: a write that
fails part-way leaves no part of the plan and removes the directories it
created, and the message names anything it could not remove.

``check`` writes nothing. ``run`` rewrites the plan it is given and never
reads an entry's status, so the pilot is run through a working copy of the
sealed plan, and ``check`` is run before each run. It refuses (exit 2)
unless: both copies are the canonical serialisation; the sealed copy is,
byte for byte, this tool's plan for its master seed
(``plan_to_json(build_pilot_plan(master_seed))``, so every entry is still
``planned`` and no free text, label, basis or source was changed); its
sha256 is the one named, when one is; the working copy holds every frozen
field of the sealed one and nothing the harness does not write; the run id
is ``planned`` and every entry before it has run; ``<base>/raw/<run id>`` is
absent; neither copy nor the base lies under the forbidden directory; and
the entry is one the harness can run as planned, read as the harness reads
it (run.py reads the figures only after it has created the run directory
and marked the entry ``running``).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

from egw_experiments.plan_gen import (
    FROZEN_ENTRY_FIELDS,
    PLAN_VERSION,
    RUN_ID_RE,
    RUN_STATUSES,
    SUPPLEMENTS,
    _run_entry,
    generate_campaign_plan,
    load_campaign_plan,
    plan_to_json,
    supplementary_entry,
)
from egw_experiments.protocol import (
    CONDITIONS,
    CONDITIONS_BY_ID,
    PROTOCOL_VERSION,
    TIMED_CONDITION_IDS,
)
from egw_simulator.devices import DEVICE_TYPES, device_uuid_for
from egw_simulator.scenarios import SCENARIOS

USAGE_WRITE = ("g4_pilot_plan.py write --master-seed N --out PATH [--against PLAN]... "
               "[--against-seed N]... [--forbid-under DIR]")
USAGE_CHECK = ("g4_pilot_plan.py check --plan WORKING --sealed SEALED --base-dir BASE "
               "--run-id RID [--sealed-sha256 HEX] [--forbid-under DIR]")
USAGE = f"{USAGE_WRITE}\n       {USAGE_CHECK}"

#: G3's tree on the host (runbook 5.2: the pilot plan and its results); the
#: pilot never writes there, and its plan and base never lie there.
DEFAULT_FORBID_UNDER = "~/egw-tcg/pilot"

PILOT_LABEL = "PILOT - NON-CITABLE"
PILOT_REPETITION = 1
#: The harness runs a warm-up as ``<run id>.warmup`` (run.py 5042), which
#: must still fit CONTRACTS 2 (64 characters).
WARMUP_SUFFIX = ".warmup"
MAX_PILOT_ID_LEN = 64 - len(WARMUP_SUFFIX)
#: ``g4pilot-s<stage>-<kind>-<dddd>s-<rate>mps-a<NN>``: never a condition id
#: prefix, never a ``-rNN`` repetition, and its stage, duration and rate
#: tokens must equal the entry's figures.
PILOT_ID_RE = re.compile(
    r"^g4pilot-s([1-4])-(nominal|loadsweep|soak)-([0-9]{4})s-([0-9]{3}|[0-9]+p[0-9])mps-a([0-9]{2})$"
)
ID_KINDS = {"nominal": "nominal", "load_sweep": "loadsweep", "soak": "soak"}
PILOT_CONDITION_IDS = ("nominal", "load_sweep", "soak")

#: Every field of an entry as written, and what the harness writes beside
#: the status afterwards (run.py, update_plan_status).
ENTRY_FIELDS = frozenset({
    "run_id", "condition_id", "runner", "scenario", "repetition", "rate_msg_s",
    "duration_s", "warmup_s", "cooldown_s", "seed", "status", "order",
})
HARNESS_WRITTEN = ("status", "result_dir", "finished_utc", "validity")
TOP_LEVEL_KEYS = frozenset({"plan_version", "protocol_version", "master_seed", "conditions", "runs", "pilot"})

#: The seeds spent elsewhere that every write is checked against: G3's
#: plan (the campaign plan of master seed 42 with its supplement), the
#: finite proof r03 (its sealed plan: master seed 20260925) and the run_test
#: seeds of the runbook's battery (42 is also the simulator's default seed).
G3_MASTER_SEED = 42
PROOF_R03_SEED = 265481284
RUN_TEST_SEEDS = {42: "tests 1 and 3", 7: "test 2"}

WHOLE_NUMBER = re.compile(r"[0-9]+")

# Where the values come from (paths from the repository root; the request
# annex is kept outside the repository, in the local decisions folder).
PROTOCOL = "src/egw_experiments/protocol.py"
PLAN_GEN = "src/egw_experiments/plan_gen.py"
RUN = "src/egw_experiments/run.py"
SCENARIOS_PY = "src/egw_simulator/scenarios.py"
DEVICES_PY = "src/egw_simulator/devices.py"
RUNBOOK = "docs/setup/qemu_integrated_gateway.md"
PLAN = "docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md"
MATRIX = "docs/claim_evidence_matrix.md"
REQUEST_ANNEX = "output_test/decisions/2026-10-07_g4-pilot-request-annex.md"


@dataclass(frozen=True)
class PilotSpec:
    """One reviewed entry: its stage, fresh run id, frozen condition and
    figures, the source of each figure, and the basis of each figure that
    departs from the frozen condition."""

    stage: int
    run_id: str
    condition_id: str
    rate_msg_s: float
    duration_s: int
    warmup_s: int
    cooldown_s: int
    sources: tuple[tuple[str, str], ...]
    deviation_basis: tuple[tuple[str, str], ...] = ()


#: The five entries, in stage order (runbook 1544; plan 643-645).
PILOT_SPECS: tuple[PilotSpec, ...] = (
    PilotSpec(
        stage=1,
        run_id="g4pilot-s1-nominal-0120s-11p2mps-a01",
        condition_id="nominal",
        rate_msg_s=11.2,
        duration_s=120,
        warmup_s=0,
        cooldown_s=0,
        sources=(
            ("rate_msg_s", f"{PROTOCOL}:285 (NOMINAL_RATE_MSG_S, :54); {SCENARIOS_PY}:91-96"),
            ("duration_s", f"{RUNBOOK}:1544 (--duration 120); {PLAN}:644 (a short nominal run)"),
            ("warmup_s", f"{REQUEST_ANNEX}:153 (recommendation P2, kept outside the repository); "
                         f"{RUNBOOK}:1544 names no warm-up"),
            ("cooldown_s", f"{PROTOCOL}:283"),
            ("repetition", f"{RUNBOOK}:1544 (one short nominal run)"),
        ),
        deviation_basis=(
            ("duration_s", f"{RUNBOOK}:1544 (--scenario nominal --duration 120); "
                           f"{PLAN}:644 (a short nominal run)"),
            ("warmup_s", f"{REQUEST_ANNEX}:153 (recommendation P2: warm-up 0 written into the entry, "
                         f"rather than a warm-up skipped; kept outside the repository); {RUNBOOK}:1544 "
                         "names no warm-up; a working choice for the student, the alternative being "
                         "the frozen 120 s"),
        ),
    ),
    PilotSpec(
        stage=2,
        run_id="g4pilot-s2-nominal-0600s-11p2mps-a01",
        condition_id="nominal",
        rate_msg_s=11.2,
        duration_s=600,
        warmup_s=120,
        cooldown_s=0,
        sources=(
            ("rate_msg_s", f"{PROTOCOL}:285 (NOMINAL_RATE_MSG_S, :54); {SCENARIOS_PY}:91-96"),
            ("duration_s", f"{PROTOCOL}:281; {RUNBOOK}:1544 (the plan's nominal duration (600 s)); "
                           f"{PLAN}:644-645"),
            ("warmup_s", f"{PROTOCOL}:282 (after 120 s warm-up, :18-20); run as '<run id>.warmup' "
                         f"with the same seed ({RUN}:5033-5054)"),
            ("cooldown_s", f"{PROTOCOL}:283"),
            ("repetition", f"{RUNBOOK}:1544 (then the plan's nominal duration)"),
        ),
    ),
    PilotSpec(
        stage=3,
        run_id="g4pilot-s3-loadsweep-0300s-010mps-a01",
        condition_id="load_sweep",
        rate_msg_s=10.0,
        duration_s=300,
        warmup_s=0,
        cooldown_s=120,
        sources=(
            ("rate_msg_s", f"{PROTOCOL}:304 (the first of the four levels); {RUNBOOK}:1544 "
                           "(load-sweep at 10 and 50 msg/s)"),
            ("duration_s", f"{PROTOCOL}:301; {RUNBOOK}:1544 (300 s each)"),
            ("warmup_s", f"{PROTOCOL}:302"),
            ("cooldown_s", f"{PROTOCOL}:303 (what is left of it after the confirmation window is "
                           f"slept after the run: {RUN}:5968-5973)"),
            ("repetition", f"{RUNBOOK}:1544 (one run at each level)"),
        ),
    ),
    PilotSpec(
        stage=3,
        run_id="g4pilot-s3-loadsweep-0300s-050mps-a01",
        condition_id="load_sweep",
        rate_msg_s=50.0,
        duration_s=300,
        warmup_s=0,
        cooldown_s=120,
        sources=(
            ("rate_msg_s", f"{PROTOCOL}:304 (the second of the four levels); {RUNBOOK}:1544 "
                           "(load-sweep at 10 and 50 msg/s)"),
            ("duration_s", f"{PROTOCOL}:301; {RUNBOOK}:1544 (300 s each)"),
            ("warmup_s", f"{PROTOCOL}:302"),
            ("cooldown_s", f"{PROTOCOL}:303 (what is left of it after the confirmation window is "
                           f"slept after the run: {RUN}:5968-5973)"),
            ("repetition", f"{RUNBOOK}:1544 (one run at each level)"),
        ),
    ),
    PilotSpec(
        stage=4,
        run_id="g4pilot-s4-soak-3600s-11p2mps-a01",
        condition_id="soak",
        rate_msg_s=11.2,
        duration_s=3600,
        warmup_s=0,
        cooldown_s=0,
        sources=(
            ("rate_msg_s", f"{PROTOCOL}:406; {SCENARIOS_PY}:120-125 (NOMINAL_AGGREGATE_RATE_HZ, "
                           f"{DEVICES_PY}:27)"),
            ("duration_s", f"{RUNBOOK}:1544 (--duration 3600); {PLAN}:645 (one bounded soak)"),
            ("warmup_s", f"{PROTOCOL}:403"),
            ("cooldown_s", f"{PROTOCOL}:404"),
            ("repetition", f"{PROTOCOL}:401; {RUNBOOK}:1544 (a short soak)"),
        ),
        deviation_basis=(
            ("duration_s", f"{RUNBOOK}:1544 (a short soak, --scenario soak --duration 3600); "
                           f"{PLAN}:645 (one bounded soak); a bounded run is no C13 evidence "
                           f"({MATRIX}:174)"),
        ),
    ),
)
SPECS_BY_ID = {spec.run_id: spec for spec in PILOT_SPECS}

#: The sources of the fields every entry takes from its frozen condition,
#: and of the fields that are not condition values.
CONDITION_SOURCES: dict[str, dict[str, str]] = {
    "nominal": {
        "condition_id": f"{PROTOCOL}:277; {RUNBOOK}:1544 (--scenario nominal)",
        "runner": f"{PROTOCOL}:278",
        "scenario": f"{PROTOCOL}:279; {SCENARIOS_PY}:91-96",
    },
    "load_sweep": {
        "condition_id": f"{PROTOCOL}:297; {RUNBOOK}:1544 (load-sweep)",
        "runner": f"{PROTOCOL}:298",
        "scenario": f"{PROTOCOL}:299; {SCENARIOS_PY}:97-103",
    },
    "soak": {
        "condition_id": f"{PROTOCOL}:398; {RUNBOOK}:1544 (--scenario soak)",
        "runner": f"{PROTOCOL}:399",
        "scenario": f"{PROTOCOL}:400; {SCENARIOS_PY}:120-125",
    },
}
ENTRY_SOURCES = {
    "run_id": (f"{PLAN}:959-960 (a predeclared identity; a repeat takes a new one and its "
               f"lineage); never an id the campaign generator emits ({PLAN_GEN}:96-105)"),
    "seed": f"{PLAN_GEN}:43-50 (derive_run_seed of the master seed and the run id)",
    "status": f"{PLAN_GEN}:71",
    "order": f"{PLAN}:643 (in order); {RUNBOOK}:1544",
}
PLAN_SOURCES = {
    "plan_version": f"{PLAN_GEN}:35",
    "protocol_version": f"{PROTOCOL}:49 (unchanged: the frozen protocol is not changed)",
    "master_seed": (f"no default: the student's decision; every seed is derived from it "
                    f"({PLAN_GEN}:43-50)"),
    "conditions": (f"{PROTOCOL}:276-295, 296-321 and 397-420, verbatim (the reference the entries' "
                   "departures are stated against)"),
    "non_citable": f"{PLAN}:654-655 (pilot data is non-citable; no pilot number enters the dissertation)",
    "not_campaign_attempts": ("the project-management scope judgement of 2026-10-07 (neither these "
                              "five runs nor G3's data are campaign attempts; kept outside the "
                              f"repository); {PLAN}:650-651 (the attempt target is not the frozen set)"),
}

PURPOSE = (
    "Input of the bounded pilot of gate G4: a short nominal run, the plan's nominal duration, the "
    "load sweep and one bounded soak, in order, one run per stage and per sweep level "
    f"({PLAN}:643-645; {RUNBOOK}:1544). The pilot checks the feasibility of the campaign's attempt "
    "target; it is not the frozen protocol, which is chosen prospectively after it."
)

#: Each condition's departure as a whole: (note, basis). Every condition of
#: the frozen protocol is listed, the ones this pilot does not run included,
#: so "the bounded pilot covers all conditions" (plan 958) is recorded and
#: never silently waived.
_NOT_RUN = "not run in this pilot: recorded, not waived"
CONDITION_DEPARTURES: dict[str, tuple[str, str]] = {
    "qemu_boots": (f"operator-measured (runner external); {_NOT_RUN}", f"{PLAN}:958"),
    "cold_start": (f"operator-measured (runner external); {_NOT_RUN}", f"{PLAN}:958"),
    "twin_creation": (f"operator-measured (runner external); {_NOT_RUN}", f"{PLAN}:958"),
    "smoke_sequence": (_NOT_RUN, f"{PLAN}:958"),
    "nominal": ("two runs of different shape: 120 s with no warm-up (stage 1) and 600 s after a "
                "120 s warm-up (stage 2)", f"{RUNBOOK}:1544; {PLAN}:643-645"),
    "load_sweep": ("one run at each of 10 and 50 msg/s, 50 msg/s after 10; 100 and 250 msg/s not "
                   "run", f"{RUNBOOK}:1544; {PROTOCOL}:300, 304"),
    "invalid_payload": (_NOT_RUN, f"{PLAN}:958"),
    "dropout_reconnect": (_NOT_RUN, f"{PLAN}:958"),
    "controller_restart": (_NOT_RUN, f"{PLAN}:958"),
    "soak": ("one run of 3,600 s in place of 86,400 s (its entry declares the duration); a bounded "
             "run is no C13 evidence", f"{RUNBOOK}:1544; {PLAN}:645; {MATRIX}:174"),
}
SWEEP_FROZEN_ORDER = f"randomised from the master seed ({PROTOCOL}:21-24; {PLAN_GEN}:84-98)"

#: The figures an entry may depart from its frozen condition in (its
#: runner and scenario are the condition's by construction).
DEPARTURE_FIELDS = ("rate_msg_s", "duration_s", "warmup_s", "cooldown_s")


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------


def _differences(condition_id: str, values: dict[str, Any]) -> list[dict[str, Any]]:
    """The figures of ``values`` that depart from the frozen condition: one
    ``{field, frozen, pilot}`` each, in DEPARTURE_FIELDS order. A sweep
    entry's rate departs only when it is none of the sweep's levels."""
    frozen = CONDITIONS_BY_ID[condition_id]
    out = []
    for field in DEPARTURE_FIELDS:
        value = values.get(field)
        if field == "rate_msg_s" and frozen.rates_msg_s:
            if value not in frozen.rates_msg_s:
                out.append({"field": field, "frozen": list(frozen.rates_msg_s), "pilot": value})
            continue
        if value != getattr(frozen, field):
            out.append({"field": field, "frozen": getattr(frozen, field), "pilot": value})
    return out


def frozen_differences(spec: PilotSpec) -> list[dict[str, Any]]:
    """Where the reviewed entry ``spec`` departs from its frozen condition."""
    return _differences(spec.condition_id, {field: getattr(spec, field) for field in DEPARTURE_FIELDS})


def declared_deviations(spec: PilotSpec) -> list[dict[str, Any]]:
    """The departures of ``spec`` with their basis; a departure without a
    stated basis, or a basis for a figure that does not depart, raises."""
    basis = dict(spec.deviation_basis)
    out = [{**difference, "basis": basis.get(difference["field"])} for difference in frozen_differences(spec)]
    undeclared = [d["field"] for d in out if not d["basis"]]
    stray = sorted(set(basis) - {d["field"] for d in out})
    if undeclared or stray:
        raise ValueError(f"{spec.run_id}: departures without a basis {undeclared}, "
                         f"a basis for figures that do not depart {stray}")
    return out


def pilot_sources(spec: PilotSpec) -> dict[str, str]:
    """The source of every field of the entry ``spec`` is written as."""
    named = {**ENTRY_SOURCES, **CONDITION_SOURCES[spec.condition_id], **dict(spec.sources)}
    if set(named) != ENTRY_FIELDS:
        raise ValueError(f"{spec.run_id}: sources for {sorted(named)}, fields {sorted(ENTRY_FIELDS)}")
    return named


def pilot_entry(spec: PilotSpec, master_seed: int, order: int) -> dict[str, Any]:
    """``plan_gen._run_entry`` of the frozen condition with the pilot's
    figures, numbered ``order``, with its inert ``pilot`` block."""
    condition = replace(
        CONDITIONS_BY_ID[spec.condition_id],
        duration_s=spec.duration_s,
        warmup_s=spec.warmup_s,
        cooldown_s=spec.cooldown_s,
    )
    entry = _run_entry(condition, spec.run_id, PILOT_REPETITION, master_seed, spec.rate_msg_s)
    entry["order"] = order
    entry["pilot"] = {"stage": spec.stage, "label": PILOT_LABEL, "deviations": declared_deviations(spec)}
    return entry


def condition_departures(runs: Sequence[Any]) -> list[dict[str, Any]]:
    """One row per condition of the frozen protocol: the runs it plans and
    the ones ``runs`` holds, its rate levels and theirs, the sweep's order,
    and the note and basis of the departure."""
    rows = []
    for condition in CONDITIONS:
        mine = [e for e in runs if isinstance(e, dict) and e.get("condition_id") == condition.id]
        rates = [e.get("rate_msg_s") for e in mine]
        note, basis = CONDITION_DEPARTURES[condition.id]
        row: dict[str, Any] = {
            "condition_id": condition.id,
            "frozen_runs": condition.repetitions * max(1, len(condition.rates_msg_s or ())),
            "pilot_runs": len(mine),
            "frozen_rates_msg_s": (
                list(condition.rates_msg_s) if condition.rates_msg_s
                else [condition.rate_msg_s] if condition.rate_msg_s is not None else []
            ),
            "pilot_rates_msg_s": sorted({r for r in rates if type(r) in (int, float)}),
            "note": note,
            "basis": basis,
        }
        if condition.rates_msg_s:
            row["frozen_order"] = SWEEP_FROZEN_ORDER
            row["pilot_order_msg_s"] = rates
        rows.append(row)
    return rows


def build_pilot_plan(master_seed: int) -> dict[str, Any]:
    """The pilot plan of ``master_seed``: the campaign plan's shape, the
    three frozen condition records verbatim, the five entries in stage
    order, and the plan's ``pilot`` block."""
    if type(master_seed) is not int or master_seed < 0:
        raise ValueError(f"the master seed {master_seed!r} is not a whole number")
    runs = [pilot_entry(spec, master_seed, order) for order, spec in enumerate(PILOT_SPECS, start=1)]
    return {
        "plan_version": PLAN_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "master_seed": master_seed,
        "conditions": [CONDITIONS_BY_ID[cid].to_dict() for cid in PILOT_CONDITION_IDS],
        "runs": runs,
        "pilot": {
            "label": PILOT_LABEL,
            "purpose": PURPOSE,
            "non_citable": True,
            "not_campaign_attempts": True,
            "deviations_from_protocol": condition_departures(runs),
            "sources": {
                "plan": dict(PLAN_SOURCES),
                "runs": {spec.run_id: pilot_sources(spec) for spec in PILOT_SPECS},
            },
        },
    }


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------


def campaign_run_ids() -> set[str]:
    """Every run id the campaign plan enumerates, for every master seed
    (only the sweep's order depends on it), and every supplementary id."""
    ids = {entry["run_id"] for entry in generate_campaign_plan(0)["runs"]}
    return ids | {f"{cid}-r{rep:02d}" for cid, rep in SUPPLEMENTS.values()}


def entry_problems(entry: dict[str, Any]) -> list[str]:
    """Why the harness could not run ``entry`` as planned: the fields it
    reads, read as it reads them (run.py 4788-4796), which it reads only
    after it has created the run directory and marked the entry running."""
    problems = []
    rid = entry.get("run_id")
    if not isinstance(rid, str) or not PILOT_ID_RE.fullmatch(rid):
        problems.append(f"run_id {rid!r} is not a pilot run id ({PILOT_ID_RE.pattern})")
    if not isinstance(rid, str) or not RUN_ID_RE.fullmatch(f"{rid}{WARMUP_SUFFIX}"):
        problems.append(f"run_id {rid!r}: the warm-up id '<run id>{WARMUP_SUFFIX}' falls outside "
                        f"CONTRACTS 2 ({RUN_ID_RE.pattern}; at most {MAX_PILOT_ID_LEN} characters)")
    if entry.get("runner") != "simulator":
        problems.append(f"runner {entry.get('runner')!r} is not 'simulator': the harness would take "
                        "its external branch")
    cid = entry.get("condition_id")
    if cid not in TIMED_CONDITION_IDS:
        problems.append(f"condition_id {cid!r} is not a simulator condition of the frozen protocol")
    spec = SPECS_BY_ID.get(rid) if isinstance(rid, str) else None
    if spec is not None and cid != spec.condition_id:
        problems.append(f"condition_id {cid!r} is not the pilot's {spec.condition_id!r}")
    scenario = entry.get("scenario")
    if scenario not in SCENARIOS:
        problems.append(f"scenario {scenario!r} is not a simulator scenario ({', '.join(SCENARIOS)})")
    elif cid in CONDITIONS_BY_ID and scenario != CONDITIONS_BY_ID[cid].scenario:
        problems.append(f"scenario {scenario!r} is not condition {cid!r}'s "
                        f"({CONDITIONS_BY_ID[cid].scenario!r})")
    rate = entry.get("rate_msg_s")
    if type(rate) not in (int, float) or not math.isfinite(rate) or rate <= 0:
        problems.append(f"rate_msg_s {rate!r} is not a positive number")
    for field, minimum in (("duration_s", 1), ("warmup_s", 0), ("cooldown_s", 0), ("repetition", 1)):
        value = entry.get(field)
        if type(value) is not int or value < minimum:
            problems.append(f"{field} {value!r} is not a whole number of at least {minimum}")
    seed = entry.get("seed")
    if type(seed) is not int or not 0 <= seed < 2**32:
        problems.append(f"seed {seed!r} is not a whole number in [0, 2**32)")
    return problems


def id_problems(entry: dict[str, Any]) -> list[str]:
    """Whether a pilot id states its entry's figures and could be read as a
    campaign id (a malformed id is ``entry_problems``' to report)."""
    rid = entry.get("run_id")
    match = PILOT_ID_RE.fullmatch(rid) if isinstance(rid, str) else None
    if match is None:
        return []
    stage, kind, duration, rate, _attempt = match.groups()
    block = entry.get("pilot") if isinstance(entry.get("pilot"), dict) else {}
    problems = []
    if int(stage) != block.get("stage"):
        problems.append(f"the id names stage {stage}, the entry's stage is {block.get('stage')!r}")
    if kind != ID_KINDS.get(entry.get("condition_id")):
        problems.append(f"the id names {kind!r}, the entry's condition is {entry.get('condition_id')!r}")
    if int(duration) != entry.get("duration_s"):
        problems.append(f"the id names {int(duration)} s, the entry's duration_s is {entry.get('duration_s')!r}")
    if float(rate.replace("p", ".")) != entry.get("rate_msg_s"):
        problems.append(f"the id names {rate} msg/s, the entry's rate_msg_s is {entry.get('rate_msg_s')!r}")
    if rid in campaign_run_ids() or any(rid.startswith(c.id) for c in CONDITIONS) or rid.startswith("qemu_boot"):
        problems.append("the id could be read as a campaign run id")
    return problems


def plan_problems(plan: Any) -> list[str]:
    """Why ``plan`` is not this tool's pilot plan for its master seed: its
    shape, its entries' frozen fields and pilot blocks, each id against its
    figures, the departures each entry and the plan declare against the
    ones computed from the figures and the frozen protocol, the sources,
    and fresh seeds and devices within the plan. Statuses are not judged."""
    if not isinstance(plan, dict):
        return ["the plan is not a JSON object"]
    problems = []
    if set(plan) != TOP_LEVEL_KEYS:
        problems.append(f"its top-level keys are {sorted(plan)}, not {sorted(TOP_LEVEL_KEYS)}")
    master_seed = plan.get("master_seed")
    if type(master_seed) is not int or master_seed < 0:
        return problems + [f"its master_seed {master_seed!r} is not a whole number"]
    built = build_pilot_plan(master_seed)
    for key in ("plan_version", "protocol_version", "conditions"):
        if plan.get(key) != built[key]:
            problems.append(f"its {key} is not the pilot's")
    runs = plan.get("runs")
    if not isinstance(runs, list) or not all(isinstance(entry, dict) for entry in runs):
        return problems + ["it holds no 'runs' list of entries"]
    ids = [entry.get("run_id") for entry in runs]
    if ids != [spec.run_id for spec in PILOT_SPECS]:
        return problems + [f"its run ids are {ids}, not the pilot's in stage order"]

    for position, (entry, want) in enumerate(zip(runs, built["runs"]), start=1):
        where = f"entry {position} ({want['run_id']})"
        for field in FROZEN_ENTRY_FIELDS:
            if entry.get(field) != want.get(field):
                problems.append(f"{where}: {field} is {entry.get(field)!r}, the pilot's is {want.get(field)!r}")
        problems += [f"{where}: {problem}" for problem in entry_problems(entry) + id_problems(entry)]
        block = entry.get("pilot")
        if not isinstance(block, dict) or set(block) != {"stage", "label", "deviations"}:
            problems.append(f"{where}: it carries no pilot block of stage, label and deviations")
            continue
        if (block["stage"], block["label"]) != (want["pilot"]["stage"], PILOT_LABEL):
            problems.append(f"{where}: its pilot block names stage {block['stage']!r} and label "
                            f"{block['label']!r}")
        declared = block["deviations"] if isinstance(block["deviations"], list) else []
        if not all(isinstance(d, dict) and isinstance(d.get("basis"), str) and d["basis"] for d in declared):
            problems.append(f"{where}: a declared departure has no basis")
        stated = [{k: v for k, v in d.items() if k != "basis"} for d in declared if isinstance(d, dict)]
        computed = _differences(entry["condition_id"], entry) if entry.get("condition_id") in CONDITIONS_BY_ID else []
        if sorted(json.dumps(d, sort_keys=True) for d in stated) != sorted(
                json.dumps(d, sort_keys=True) for d in computed):
            problems.append(f"{where}: it declares the departures {stated}, its figures depart in {computed}")

    seeds = [entry.get("seed") for entry in runs]
    if len(set(map(repr, seeds))) != len(seeds):
        problems.append(f"its seeds are not pairwise distinct: {seeds}")
    elif all(type(seed) is int for seed in seeds):
        devices = [device_uuid_for(seed, device_type) for seed in seeds for device_type in DEVICE_TYPES]
        if len(set(devices)) != len(devices):
            problems.append("two of its entries share a device")

    pilot = plan.get("pilot")
    if not isinstance(pilot, dict):
        return problems + ["it carries no top-level pilot block"]
    if pilot.get("non_citable") is not True or pilot.get("not_campaign_attempts") is not True:
        problems.append("its pilot block does not state the runs non-citable and not campaign attempts")
    if not isinstance(pilot.get("purpose"), str) or not pilot["purpose"]:
        problems.append("its pilot block states no purpose")
    rows = pilot.get("deviations_from_protocol")

    def counted(row: Any) -> Any:
        return {k: v for k, v in row.items() if k not in ("note", "basis", "frozen_order")} if isinstance(row, dict) else row

    want_rows = condition_departures(runs)
    if not isinstance(rows, list) or [counted(r) for r in rows] != [counted(r) for r in want_rows]:
        problems.append("its deviations_from_protocol do not state the counts, levels and order its "
                        "entries and the frozen protocol give")
    elif not all(r.get("note") and r.get("basis") for r in rows) or any(
            "frozen_order" in w and not r.get("frozen_order") for r, w in zip(rows, want_rows)):
        problems.append("a row of its deviations_from_protocol has no note, basis or frozen order")
    sources = pilot.get("sources") if isinstance(pilot.get("sources"), dict) else {}
    run_sources = sources.get("runs") if isinstance(sources.get("runs"), dict) else {}
    if not isinstance(sources.get("plan"), dict) or set(sources["plan"]) != set(PLAN_SOURCES):
        problems.append(f"its sources do not name the plan's fields {sorted(PLAN_SOURCES)}")
    for rid in ids:
        named = run_sources.get(rid)
        if not isinstance(named, dict) or set(named) != ENTRY_FIELDS or not all(
                isinstance(s, str) and s for s in named.values()):
            problems.append(f"its sources do not name every field of {rid}")
    return problems


def built_problems(raw: bytes, plan: dict[str, Any]) -> list[str]:
    """Why ``raw`` (the bytes of ``plan``) is not, byte for byte, this
    tool's plan for the master seed ``plan`` names,
    ``plan_to_json(build_pilot_plan(master_seed))``: so a changed free
    text, label, basis or source, or a key added anywhere, is found as
    surely as a changed figure. A master seed that is not a whole number is
    ``plan_problems``' to report."""
    master_seed = plan.get("master_seed")
    if type(master_seed) is not int or master_seed < 0:
        return []
    if raw != plan_to_json(build_pilot_plan(master_seed)).encode("utf-8"):
        return [f"the sealed plan is not, byte for byte, this tool's plan for its master seed {master_seed} "
                f"(plan_to_json(build_pilot_plan({master_seed})))"]
    return []


def sealed_problems(sealed: dict[str, Any]) -> list[str]:
    """Why ``sealed`` is not a copy the harness was never given: an entry
    with another status than ``planned``, or a field the harness writes."""
    problems = []
    runs = sealed.get("runs") if isinstance(sealed.get("runs"), list) else []
    for position, entry in enumerate(runs, start=1):
        if not isinstance(entry, dict):
            continue
        where = f"entry {position} ({entry.get('run_id')}) of the sealed plan"
        if entry.get("status") != "planned":
            problems.append(f"{where} has status {entry.get('status')!r}: the sealed copy is never given to run")
        extra = sorted(set(entry) - ENTRY_FIELDS - {"pilot"})
        if extra:
            problems.append(f"{where} carries {', '.join(extra)}: the sealed copy is never given to run")
    return problems


def working_problems(working: Any, sealed: dict[str, Any]) -> list[str]:
    """Where the working copy departs from the sealed one in anything but
    what the harness writes (an entry's status and the fields beside it)."""
    if not isinstance(working, dict):
        return ["the working plan is not a JSON object"]
    problems = [f"the working plan's {key} differs from the sealed plan's"
                for key in sorted(set(working) | set(sealed)) if key != "runs" and working.get(key) != sealed.get(key)]
    w_runs, s_runs = working.get("runs"), sealed.get("runs")
    if not isinstance(w_runs, list) or not isinstance(s_runs, list) or not all(
            isinstance(entry, dict) for entry in w_runs + s_runs):
        return problems + ["the working or the sealed plan holds no 'runs' list of entries"]
    if [e.get("run_id") for e in w_runs] != [e.get("run_id") for e in s_runs]:
        return problems + ["the working plan's run ids differ from the sealed plan's"]
    for position, (w, s) in enumerate(zip(w_runs, s_runs), start=1):
        where = f"entry {position} ({s.get('run_id')}) of the working plan"
        for field in (*FROZEN_ENTRY_FIELDS, "pilot"):
            if w.get(field) != s.get(field):
                problems.append(f"{where} differs from the sealed plan in {field}")
        extra = sorted(set(w) - set(s) - set(HARNESS_WRITTEN))
        if extra:
            problems.append(f"{where} carries a field the harness never writes: {', '.join(extra)}")
        if w.get("status") not in RUN_STATUSES:
            problems.append(f"{where} has the status {w.get('status')!r}, which the harness never writes")
    return problems


def readiness(working: Any, run_id: str, base_dir: Path) -> list[str]:
    """Why ``run_id`` is not the next run of the working copy: absent, not
    ``planned``, an entry before it still to run, its run directory there,
    or an entry the harness could not run as planned."""
    runs = working.get("runs") if isinstance(working, dict) else None
    if not isinstance(runs, list) or not all(isinstance(entry, dict) for entry in runs):
        return ["the working plan holds no 'runs' list of entries"]
    position = next((i for i, entry in enumerate(runs) if entry.get("run_id") == run_id), None)
    if position is None:
        return [f"the run id {run_id!r} is not in the working plan"]
    entry = runs[position]
    problems = []
    if entry.get("status") != "planned":
        problems.append(f"{run_id} has status {entry.get('status')!r} in the working plan, not 'planned': "
                        "the harness never reads it, and a run the plan holds is never made again")
    for number, earlier in enumerate(runs[:position], start=1):
        if earlier.get("status") not in ("completed", "failed"):
            problems.append(f"entry {number} ({earlier.get('run_id')}) comes before {run_id} and is still "
                            f"{earlier.get('status')!r}: the pilot runs in order")
    run_dir = base_dir / "raw" / run_id
    if run_dir.exists() or run_dir.is_symlink():
        problems.append(f"{run_dir} exists: a run directory is never reused")
    problems += [f"{run_id}: {problem}" for problem in entry_problems(entry)]
    return problems


def reference_seeds() -> dict[int, str]:
    """The seeds spent elsewhere, each with where it is spent: every write
    is checked against them, whatever ``--against`` names."""
    g3 = generate_campaign_plan(G3_MASTER_SEED)["runs"]
    g3 = g3 + [supplementary_entry(G3_MASTER_SEED, key, len(g3) + 1) for key in SUPPLEMENTS]
    spent: dict[int, str] = {}
    for entry in g3:
        spent.setdefault(entry["seed"], f"G3's plan, the campaign plan of master seed "
                                        f"{G3_MASTER_SEED} ({entry['run_id']})")
    spent.setdefault(PROOF_R03_SEED, "the finite proof r03 (proof-adr0011-r03, master seed 20260925)")
    for seed, tests in RUN_TEST_SEEDS.items():
        spent.setdefault(seed, f"the run_test seed {seed} of the runbook's battery ({tests})")
    return spent


def collisions(plan: dict[str, Any], others: Sequence[tuple[str, dict[str, Any]]],
               seeds: Iterable[int] = ()) -> list[str]:
    """The pilot run ids another plan holds, and the pilot seeds and devices
    the references, another plan or a named seed already spend."""
    runs = plan["runs"]
    problems = []
    for name, other in others:
        held = {entry.get("run_id") for entry in other.get("runs", []) if isinstance(entry, dict)}
        problems += [f"the run id {entry['run_id']!r} is held by {name}" for entry in runs if entry["run_id"] in held]
    spent = dict(reference_seeds())
    for name, other in others:
        for entry in other.get("runs", []):
            if isinstance(entry, dict) and type(entry.get("seed")) is int:
                spent.setdefault(entry["seed"], f"{name} ({entry.get('run_id')})")
    for seed in seeds:
        spent.setdefault(seed, f"--against-seed {seed}")
    devices: dict[str, str] = {}
    for seed, where in spent.items():
        for device_type in DEVICE_TYPES:
            devices.setdefault(device_uuid_for(seed, device_type), where)
    for entry in runs:
        if entry["seed"] in spent:
            problems.append(f"the seed {entry['seed']} of {entry['run_id']!r} is spent by {spent[entry['seed']]}")
            continue
        for device_type in DEVICE_TYPES:
            device = device_uuid_for(entry["seed"], device_type)
            if device in devices:
                problems.append(f"the device {device} ({device_type}) of {entry['run_id']!r} is a device "
                                f"of {devices[device]}")
    return problems


def lies_under(path: Path, directory: Path) -> bool:
    """Whether ``path`` is ``directory`` or lies inside it: as given, with
    '..' folded, or as it resolves through symbolic links."""

    def forms(p: Path) -> set[Path]:
        given = p.expanduser()
        given = given if given.is_absolute() else Path.cwd() / given
        out = {given, Path(os.path.abspath(given))}
        try:
            out.add(given.resolve())
        except (OSError, RuntimeError):
            pass
        return out

    roots = forms(directory)
    return any(form == root or root in form.parents for form in forms(path) for root in roots)


def read_plan(path: Path) -> dict[str, Any]:
    """The plan at ``path``, read through the harness's own loader; raises
    when the file does not hold a plan's ``runs`` list."""
    plan = load_campaign_plan(path)
    runs = plan.get("runs") if isinstance(plan, dict) else None
    if not isinstance(runs, list) or not all(isinstance(entry, dict) for entry in runs):
        raise ValueError("the file holds no 'runs' list of entries")
    return plan


class PlanNotWritten(Exception):
    """``write_plan`` did not publish the plan under ``out``: ``cause`` is
    the error, and ``left`` names what this write created and could not
    remove again (normally nothing)."""

    def __init__(self, out: Path, cause: OSError, left: list[Path]) -> None:
        super().__init__(f"{out} was not written ({cause})")
        self.out, self.cause, self.left = out, cause, left


def _missing_directories(directory: Path) -> list[Path]:
    """``directory`` and its ancestors that do not exist yet, deepest first:
    the ones a ``mkdir(parents=True)`` of it would create."""
    missing = []
    for candidate in (directory, *directory.parents):
        if candidate.exists() or candidate.is_symlink():
            break
        missing.append(candidate)
    return missing


def _remove(temporary: Path | None, directories: list[Path]) -> list[Path]:
    """Remove ``temporary`` and then the (empty) ``directories``, deepest
    first; what could not be removed."""
    left = []
    if temporary is not None:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            left.append(temporary)
    for directory in directories:
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            left.append(directory)
    return left


def write_plan(plan: dict[str, Any], out: Path) -> tuple[str, list[Path]]:
    """Write ``plan`` to ``out`` once, canonically, and never leave a part of
    it under ``out``: the text goes to a new temporary file in ``out``'s
    directory, is synced, and is then published under ``out`` by a hard
    link, which refuses a target that exists, so an ``out`` that came to
    exist meanwhile is never replaced. Returns the sha256 of what was
    written and what could not be removed afterwards (the temporary name of
    the same file; normally nothing). On any failure before the link the
    temporary file and the directories this write created are removed, and
    PlanNotWritten names what, if anything, is left."""
    text = plan_to_json(plan)
    created = _missing_directories(out.parent)
    temporary: Path | None = None
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        candidate = out.parent / f".{out.name}.{os.getpid()}.{secrets.token_hex(6)}.partial"
        descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o666)
        temporary = candidate
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.link(temporary, out)
    except OSError as exc:
        raise PlanNotWritten(out, exc, _remove(temporary, created)) from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), _remove(temporary, [])


# ---------------------------------------------------------------------------
# the commands
# ---------------------------------------------------------------------------


def _stop(reasons: list[str], last: str) -> int:
    for reason in reasons:
        print(f"STOP: g4_pilot_plan: {reason}", file=sys.stderr)
    print(f"STOP: g4_pilot_plan: {last}", file=sys.stderr)
    return 2


def _write(args: argparse.Namespace, forbid: Path) -> int:
    reasons = []
    if not WHOLE_NUMBER.fullmatch(args.master_seed):
        reasons.append(f"the master seed {args.master_seed!r} is not a whole number")
    reasons += [f"the against seed {seed!r} is not a whole number"
                for seed in args.against_seed if not WHOLE_NUMBER.fullmatch(seed)]
    if lies_under(args.out, forbid):
        reasons.append(f"the output {args.out} lies under {forbid}, where this tool never writes")
    if args.out.exists() or args.out.is_symlink():
        reasons.append(f"{args.out} exists: the plan is write-once and is not replaced")
    others = []
    for path in args.against:
        try:
            others.append((str(path), read_plan(path)))
        except (OSError, ValueError) as exc:
            reasons.append(f"the against plan {path} could not be read ({exc}): that it holds none of "
                           "the pilot's run ids, seeds and devices cannot be established")
    if reasons:
        return _stop(reasons, "nothing was written")
    plan = build_pilot_plan(int(args.master_seed))
    reasons = [f"the plan built: {problem}" for problem in plan_problems(plan)]
    reasons += collisions(plan, others, [int(seed) for seed in args.against_seed])
    if reasons:
        return _stop(reasons, "nothing was written")
    try:
        digest, left = write_plan(plan, args.out)
    except PlanNotWritten as exc:
        if exc.left:
            return _stop([str(exc)], "nothing else was written, but these are left behind and are to be "
                                     f"removed by hand: {', '.join(map(str, exc.left))}")
        return _stop([str(exc)], "nothing was written")
    for order, entry in enumerate(plan["runs"], start=1):
        print(f"entry {order}: run_id={entry['run_id']} stage={entry['pilot']['stage']} "
              f"condition_id={entry['condition_id']} scenario={entry['scenario']} "
              f"duration_s={entry['duration_s']} warmup_s={entry['warmup_s']} "
              f"cooldown_s={entry['cooldown_s']} rate_msg_s={entry['rate_msg_s']} seed={entry['seed']}")
    print(f"wrote {args.out}: entries={len(plan['runs'])} master_seed={plan['master_seed']} sha256={digest}")
    for path in left:
        print(f"g4_pilot_plan: the temporary name {path} of the plan just written could not be removed: "
              "remove it by hand", file=sys.stderr)
    return 0


def _read_canonical(path: Path, label: str, reasons: list[str]) -> tuple[Any, bytes | None]:
    try:
        raw = path.read_bytes()
        plan = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        reasons.append(f"{label} {path} could not be read ({exc})")
        return None, None
    if plan_to_json(plan).encode("utf-8") != raw:
        reasons.append(f"{path} is not the canonical serialisation the harness writes (plan_to_json)")
    return plan, raw


def _same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return Path(os.path.abspath(a)) == Path(os.path.abspath(b))


def _check(args: argparse.Namespace, forbid: Path) -> int:
    reasons = [f"{label} {path} lies under {forbid}, where the pilot never writes"
               for label, path in (("the working plan", args.plan), ("the sealed plan", args.sealed),
                                   ("the results base", args.base_dir))
               if lies_under(path, forbid)]
    if _same_file(args.plan, args.sealed):
        reasons.append("the working plan and the sealed plan are the same file: the harness rewrites "
                       "the plan it is given, and the sealed copy is never given to it")
    working, _ = _read_canonical(args.plan, "the working plan", reasons)
    sealed, sealed_raw = _read_canonical(args.sealed, "the sealed plan", reasons)
    if sealed_raw is not None and args.sealed_sha256 is not None:
        actual = hashlib.sha256(sealed_raw).hexdigest()
        if actual != args.sealed_sha256:
            reasons.append(f"the sealed plan's sha256 is {actual}, not {args.sealed_sha256}")
    if isinstance(sealed, dict):
        reasons += [f"the sealed plan: {problem}" for problem in plan_problems(sealed)]
        reasons += built_problems(sealed_raw, sealed)
        reasons += sealed_problems(sealed)
        if working is not None:
            reasons += working_problems(working, sealed)
    elif sealed is not None:
        reasons.append("the sealed plan is not a JSON object")
    if working is not None:
        reasons += readiness(working, args.run_id, args.base_dir)
    if reasons:
        return _stop(reasons, f"check: {args.run_id} is not ready to run; nothing was written")
    runs = working["runs"]
    position = next(i for i, entry in enumerate(runs) if entry["run_id"] == args.run_id)
    print(f"ready: {args.run_id} (order {position + 1} of {len(runs)}, stage "
          f"{runs[position]['pilot']['stage']}): {args.plan} holds every frozen field of {args.sealed}, "
          f"the entries before it have run and {args.base_dir / 'raw' / args.run_id} is absent; "
          "nothing was written")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="g4_pilot_plan.py", usage=USAGE)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", usage=USAGE_WRITE, help="write the pilot plan, once")
    write.add_argument("--master-seed", required=True, help="a whole number; there is no default")
    write.add_argument("--out", required=True, type=Path, help="the plan file (write-once)")
    write.add_argument("--against", action="append", default=[], type=Path,
                       help="a plan whose run ids, seeds and devices are refused (read only; repeatable)")
    write.add_argument("--against-seed", action="append", default=[],
                       help="a seed spent elsewhere, refused with its devices (repeatable)")
    write.add_argument("--forbid-under", type=Path, default=Path(DEFAULT_FORBID_UNDER),
                       help=f"a tree the output never lies under (default {DEFAULT_FORBID_UNDER}, G3's)")
    check = commands.add_parser("check", usage=USAGE_CHECK,
                                help="check the working copy against the sealed one before a run")
    check.add_argument("--plan", required=True, type=Path, help="the working copy the harness is given")
    check.add_argument("--sealed", required=True, type=Path, help="the sealed copy, never given to the harness")
    check.add_argument("--base-dir", required=True, type=Path, help="the pilot's results base")
    check.add_argument("--run-id", required=True, help="the entry about to run")
    check.add_argument("--sealed-sha256", default=None, help="the sealed copy's recorded sha256")
    check.add_argument("--forbid-under", type=Path, default=Path(DEFAULT_FORBID_UNDER),
                       help=f"a tree neither copy nor the base lies under (default {DEFAULT_FORBID_UNDER}, G3's)")
    args = parser.parse_args(argv)
    forbid = args.forbid_under.expanduser()
    if args.command == "write":
        return _write(args, forbid)
    return _check(args, forbid)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
