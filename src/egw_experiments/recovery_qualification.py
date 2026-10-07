"""Recovery qualification of the controller_restart runs (ADR 0011 item 18;
review finding F2): an explicit layer beside the quantitative analyser.

``egw_experiments.analyze`` never reads ``drain.outcome``: its C12 criteria
are computed from the measured-window events and metrics, so a VALID run
whose drain gave up — a failed recovery, retained by ``run.py`` as an
observation and never a validity reason — can pass every row of
``acceptance_by_condition.csv``. ADR 0011 leaves ``analyze.py`` unchanged
and reserves the N1 counting for a separate decision (decision 2 of
2026-09-30 adopted the reporting column below and took no counting
decision), so the qualification is enforced and reported here, in a layer
of its own, and propagated into the authoritative report as two files
written beside the analyser's outputs under ``processed/``:

- ``recovery_qualification.json``: one record per controller_restart run of
  the campaign plan (in plan order; any unplanned controller_restart
  directory found in ``raw/`` follows, marked so), the aggregate criterion
  and the statement below;
- ``recovery_qualification.csv``: the same records, one row per run.

Per run: ``run_id``, ``planned``, ``validity`` (the manifest's, or
``absent`` / ``unreadable``), ``integrity`` (``SHA256SUMS``: ``ok``,
``unsealed``, ``failed``, ``absent``), ``excluded`` (a manifest
``exclusion``), ``drain_outcome`` (``quiet`` / ``gave-up`` / ``error`` /
``absent``), ``drain_source`` (``hook`` / ``ingested`` / null),
``captured_utc`` (the instant an ingested transcript's envelope names),
whether the before snapshot, the after snapshot and the post-drain events
are present in the run directory and verified by their manifest records,
and the ``qualification`` (:func:`qualification_of`):

- ``recovery_observed``: the run is valid, sealed and verified, not
  excluded, its drain outcome is ``quiet``, and the after snapshot and the
  post-drain events are present and verified;
- ``recovery_failed``: the run is valid, sealed and verified, not excluded,
  and its drain outcome is ``gave-up`` (the controller was not observed
  quiet within the helper's limit: a valid observation of failed recovery);
- ``not_evidenced``: anything else, with the ``reason``.

The criterion ``restart_recovery_observed_every_run`` is true only when the
plan lists at least one controller_restart run and every listed run
(planned, plus any unplanned one found) is ``recovery_observed``; otherwise
it is false and names the runs that are not, with their qualification and
reason. Without a campaign plan the planned set is unknown and the
criterion is false, saying so.

Execution modes (G4 core provenance, plan 655-661) are never pooled into
one criterion (plan 429-432; review of the G4 tooling, finding 8). Each
run's execution-mode group is the analyser's own classification
(:func:`egw_experiments.analyze.classify_execution_mode` on the run's
sealed manifest and environment records): a recorded mode, ``unrecorded``
(no provenance record), or no group (a provenance failure, which is never
evidence whatever its validity says, as in the analyser, or a planned run
without a directory). Every record carries its group (``execution_mode``,
the leading CSV column) and, in the JSON, ``execution_mode_status`` and
``execution_mode_problems``. The criterion is evaluated once per group
(:func:`evaluate_criterion`, which refuses runs of more than one group
itself with :class:`~egw_experiments.analyze.MixedExecutionModeError`)
against the whole plan: a planned run of another group is not evidence for
the group, and a run in no group keeps its own qualification; with no run
in any group it is evaluated once with no group (named ``none``). The JSON
holds these evaluations in ``criteria_by_execution_mode``; its
``criterion`` is the single evaluation of a tree of one group (its values
those of the layer before the execution modes, with ``execution_mode`` and
``execution_mode_label`` beside them), and for several groups a criterion
that never passes and names the groups. The CLI prints one line for it
and, for several groups, one line per group.

This layer changes no count: lost, late and every other figure of the
analysis come from ``egw_experiments.analyze``, whose per-run, summary,
acceptance and saturation outputs it neither reads nor rewrites, and it
adds no row to the acceptance table. N1 is counted nowhere: the two N1
columns below are this layer's own report of identities, read from the
run's files, and change no figure of the analysis (``STATEMENT``, written
unchanged into the JSON, says so). The
qualification is read from the sealed manifests'
restart evidence records alone (``drain``, ``twin_snapshots``,
``events_post_drain_fetch``, ``validity``, ``exclusion``) and the
``SHA256SUMS`` verification, with the analyser's provenance gate (a run
whose execution-mode classification is a provenance failure is never
evidence; see above). The ``analyze`` command runs it after the
analysis and keeps its own exit code (``cli._cmd_analyze`` says why);
``recovery`` runs it alone. No timestamp enters the files, so repeated runs
over the same evidence are identical.

The N1 identities (decision 2 of 2026-09-30, :mod:`egw_experiments.n1_report`)
are reported beside the qualification, per run with a directory: the columns
``n1_applied_unconfirmed`` and ``duplicate_only_unexplained`` (how many
duplicate-only identities are named and how many are not; empty for a
planned run without a directory, when no events copy can be read, or when
the report could not be made at all, which never stops the layer) and,
in the JSON record, ``n1`` with every identity, its possible sources or its
failed conditions. For them the layer also reads the run's files:
``sent_events.jsonl``, the post-drain copy (the timed ``events.jsonl`` only
when that copy is not present and verified, and then only to list the
identities as unexplained), the two twin snapshots, ``logs/sut/controller.log``
(the A3 source) and ``logs/sut/docker-events.log`` with its coverage record
(the death source, with the manifest's ``restart`` record), each only when
its fetch record shows it written, and ``controller_metrics.csv``, whose
readings place the death: it serves an identity only when they show one
process change whose new process's first reading precedes the identity's
first redelivery (review of PR #53, F2); without them it serves none.
Condition 3 is evaluable only on a run whose qualification is
``recovery_observed`` and whose before snapshot is verified. A named
identity stays lost: no count, no criterion and no qualification changes.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import n1_report
from .analyze import (
    INTEGRITY_FAILED,
    INTEGRITY_OK,
    INTEGRITY_UNSEALED,
    NO_GROUP_NAME,
    PROVENANCE_BLOCKING_STATUSES,
    _group_order,
    check_run_integrity,
    classify_execution_mode,
    execution_mode_label,
    load_campaign_plan_for_analysis,
    read_environment_records,
    require_single_execution_mode,
)
from .run import (
    DEFAULT_RESULTS_BASE,
    DRAIN_OUTCOMES,
    MANIFEST_FILENAME,
    POST_DRAIN_EVENTS_FILENAME,
    SUT_LOG_FILES,
    SUT_LOG_SUBDIR,
    TWIN_SNAPSHOT_FILES,
)

#: The only condition this layer qualifies (ADR 0011 item 18).
CONDITION_ID = "controller_restart"

#: The aggregate criterion, named as the acceptance table names its rows
#: but written in this layer's files only.
CRITERION = "restart_recovery_observed_every_run"

#: The three qualifications a run receives.
QUALIFICATIONS = ("recovery_observed", "recovery_failed", "not_evidenced")

JSON_FILENAME = "recovery_qualification.json"
CSV_FILENAME = "recovery_qualification.csv"

#: Written into both files: what this layer does not do.
STATEMENT = (
    "This layer changes no count of lost, late or N1 messages and adds "
    "nothing to the analyser's acceptance table (acceptance_by_condition.csv): "
    "every figure of the analysis comes from egw_experiments.analyze, "
    "unchanged (ADR 0011); the N1 columns are this layer's report of "
    "identities read from the run's files and change no figure; the "
    "qualification is read from the sealed manifests' restart evidence "
    "records alone."
)

#: The label of the JSON's ``criterion`` when the runs span several
#: execution-mode groups (it never passes; see ``criteria_by_execution_mode``).
SEVERAL_GROUPS_LABEL = (
    "several execution-mode groups: the criterion is evaluated once per group "
    "and never across groups"
)

CSV_COLUMNS = [
    # The run's execution-mode group (blank: no group), as the analyser's
    # other tables lead with theirs (G4 core provenance, plan 655-661).
    "execution_mode",
    "run_id",
    "planned",
    "validity",
    "integrity",
    "excluded",
    "drain_outcome",
    "drain_source",
    "captured_utc",
    "twins_before_verified",
    "twins_after_verified",
    "post_drain_verified",
    "qualification",
    "reason",
    # Decision 2 of 2026-09-30 (n1_report): reported, never counted.
    "n1_applied_unconfirmed",
    "duplicate_only_unexplained",
]

#: The coverage record the Docker events fetch (proof_fetch_sut_log.sh)
#: keeps beside the capture, under logs/sut/.
DOCKER_EVENTS_COVERAGE = "docker-events.coverage.txt"

#: The controller's /metrics readings of a harness run
#: (egw_experiments.controller_metrics), which place the death on the
#: controller clock for the N1 report.
CONTROLLER_METRICS_FILENAME = "controller_metrics.csv"

#: The timed copy of the events, read for the N1 identities only when the
#: post-drain copy is not present and verified.
TIMED_EVENTS_FILENAME = "events.jsonl"

_INTEGRITY_WORDS = {
    INTEGRITY_OK: "ok",
    INTEGRITY_FAILED: "failed",
    INTEGRITY_UNSEALED: "unsealed",
}


def qualification_of(facts: dict[str, Any]) -> tuple[str, str]:
    """The qualification of one run from the facts :func:`inspect_run`
    reads, and the reason when it is not ``recovery_observed``.

    Evidence first: a run that is not valid, not sealed and verified, or
    excluded evidences nothing, whatever its drain says; nor does a run
    with an execution-mode provenance failure (``execution_mode_status``
    unset, unknown or inconsistent: the analyser's gate, which never
    aggregates such a run whatever its validity says; facts without the
    key, as :func:`run_facts` gives them, are not gated). Then the drain:
    ``gave-up`` is the failed recovery, ``quiet`` needs the after snapshot
    and the post-drain events present and verified, anything else (an
    instrument failure, a missing step) evidences nothing.
    """
    blockers: list[str] = []
    if facts.get("validity") != "valid":
        blockers.append(f"validity {facts.get('validity')!r}")
    if facts.get("integrity") != "ok":
        blockers.append(f"integrity {facts.get('integrity')!r}")
    if facts.get("excluded"):
        blockers.append("excluded per the manifest")
    status = facts.get("execution_mode_status")
    if status in PROVENANCE_BLOCKING_STATUSES:
        blockers.append(f"execution-mode provenance failure ({status!r})")
    if blockers:
        return "not_evidenced", "; ".join(blockers) + ": the run is not evidence"
    outcome = facts.get("drain_outcome")
    if outcome == "gave-up":
        return "recovery_failed", (
            "the drain gave up: the controller was not observed quiet within "
            "the helper's limit after the restart (drain.outcome 'gave-up', a "
            "valid observation of failed recovery)"
        )
    if outcome != "quiet":
        return "not_evidenced", (
            f"drain outcome {outcome!r}: no quiet state was observed after "
            "the restart"
        )
    missing: list[str] = []
    if not facts.get("twins_after_verified"):
        missing.append(f"the after snapshot ({TWIN_SNAPSHOT_FILES['twin_snapshot_after']})")
    if not facts.get("post_drain_verified"):
        missing.append(f"the post-drain events ({POST_DRAIN_EVENTS_FILENAME})")
    if missing:
        return "not_evidenced", (
            "drain quiet but " + " and ".join(missing) + " not present and verified"
        )
    return "recovery_observed", ""


def _record_state(
    record: Any, run_dir: Path, file: str
) -> tuple[bool, bool]:
    """(present, verified) of one restart evidence record: present when the
    record exists and its file is in the run directory, verified when the
    record says so as well."""
    if not isinstance(record, dict):
        return False, False
    present = (run_dir / file).is_file()
    return present, present and record.get("verified") is True


def run_facts(
    run_dir: Path, run_id: str, *, planned: bool
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The facts of one controller_restart run, read from its sealed
    manifest, with its qualification, and the manifest itself (None when it
    is absent or unreadable)."""
    manifest: Any = None
    facts: dict[str, Any] = {
        "run_id": run_id,
        "planned": planned,
        "validity": "absent",
        "integrity": "absent",
        "excluded": False,
        "drain_outcome": "absent",
        "drain_source": None,
        "captured_utc": None,
        "twins_before_present": False,
        "twins_before_verified": False,
        "twins_after_present": False,
        "twins_after_verified": False,
        "post_drain_present": False,
        "post_drain_verified": False,
    }
    manifest_path = run_dir / MANIFEST_FILENAME
    if run_dir.is_dir() and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
        if not isinstance(manifest, dict):
            facts["validity"] = "unreadable"
        else:
            facts["validity"] = str(manifest.get("validity"))
            facts["excluded"] = manifest.get("exclusion") is not None
            integrity, _problems = check_run_integrity(run_dir)
            facts["integrity"] = _INTEGRITY_WORDS.get(integrity, integrity)
            drain = manifest.get("drain")
            if isinstance(drain, dict):
                outcome = drain.get("outcome")
                facts["drain_outcome"] = outcome if outcome in DRAIN_OUTCOMES else "error"
                facts["drain_source"] = drain.get("source")
                facts["captured_utc"] = drain.get("captured_utc")
            snapshots = manifest.get("twin_snapshots")
            by_file = {
                r.get("file"): r
                for r in (snapshots if isinstance(snapshots, list) else [])
                if isinstance(r, dict)
            }
            for hook, key in (
                ("twin_snapshot_before", "twins_before"),
                ("twin_snapshot_after", "twins_after"),
            ):
                file = TWIN_SNAPSHOT_FILES[hook]
                present, verified = _record_state(by_file.get(file), run_dir, file)
                facts[f"{key}_present"], facts[f"{key}_verified"] = present, verified
            present, verified = _record_state(
                manifest.get("events_post_drain_fetch"), run_dir, POST_DRAIN_EVENTS_FILENAME
            )
            facts["post_drain_present"], facts["post_drain_verified"] = present, verified
    facts["qualification"], facts["reason"] = qualification_of(facts)
    return facts, (manifest if isinstance(manifest, dict) else None)


def execution_mode_of(run_dir: Path, manifest: dict[str, Any] | None) -> dict[str, Any]:
    """The run's execution-mode group as the analyser classifies it
    (:func:`egw_experiments.analyze.classify_execution_mode` on the run's
    own sealed manifest and environment records, a missing or unreadable
    manifest read as an empty one, as there): ``execution_mode`` (the
    group: the recorded mode, ``unrecorded``, or None for a provenance
    failure), ``execution_mode_status`` and ``execution_mode_problems``. A
    planned run without a directory has no group and no status."""
    if not Path(run_dir).is_dir():
        return {"execution_mode": None, "execution_mode_status": None, "execution_mode_problems": []}
    mode = classify_execution_mode(
        manifest if manifest is not None else {}, read_environment_records(run_dir)
    )
    return {
        "execution_mode": mode["execution_mode_group"],
        "execution_mode_status": mode["execution_mode_status"],
        "execution_mode_problems": list(mode["problems"]),
    }


def inspect_run(run_dir: Path, run_id: str, *, planned: bool) -> dict[str, Any]:
    """The facts of one controller_restart run, read from its sealed
    manifest, with its execution-mode group (:func:`execution_mode_of`),
    its qualification and its N1 identities (decision 2 of 2026-09-30:
    reported, never counted)."""
    facts, manifest = run_facts(run_dir, run_id, planned=planned)
    facts.update(execution_mode_of(run_dir, manifest))
    facts["qualification"], facts["reason"] = qualification_of(facts)
    n1 = None
    if run_dir.is_dir():
        try:
            n1 = n1_of_run(run_dir, run_id, facts, manifest)
        except Exception as exc:  # broad on purpose: the report never stops the layer (analyze runs it)
            n1 = {"events_copy": None, "problem": f"the N1 report was not made ({type(exc).__name__})"}
    counted = n1 is not None and n1.get("events_copy") is not None
    facts["n1_applied_unconfirmed"] = len(n1["n1_applied_unconfirmed"]) if counted else None
    facts["duplicate_only_unexplained"] = len(n1["duplicate_only_unexplained"]) if counted else None
    facts["n1"] = n1
    return facts


# ---------------------------------------------------------------------------
# the N1 identities of a run directory (decision 2 of 2026-09-30)
# ---------------------------------------------------------------------------


def n1_evidence_problem(facts: dict[str, Any]) -> str | None:
    """What leaves condition 3 of the N1 rule unshown on a run, or None: the
    after snapshot must follow a quiet drain, and the snapshots and the
    post-drain copy must be present and verified on a valid, sealed and
    verified run that is not excluded - the qualification
    ``recovery_observed``, plus the before snapshot verified."""
    if facts.get("qualification") != "recovery_observed":
        return (
            f"the run's recovery qualification is {facts.get('qualification')!r} "
            f"({facts.get('reason')})"
        )
    if not facts.get("twins_before_verified"):
        return (
            f"the before snapshot ({TWIN_SNAPSHOT_FILES['twin_snapshot_before']}) "
            "is not present and verified"
        )
    return None


def _fetch_problem(manifest: dict[str, Any] | None, hook: str) -> str | None:
    """None when the manifest's record of the SUT fetch ``hook`` shows its
    file written (exit 0 and the file present), else why not."""
    if manifest is None:
        return "the run's manifest was not read"
    records = manifest.get("sut_log_fetches")
    record = next(
        (r for r in (records if isinstance(records, list) else [])
         if isinstance(r, dict) and r.get("hook") == hook),
        None,
    )
    if record is None:
        return f"the manifest records no {hook} fetch"
    if record.get("returncode") != 0 or not record.get("dest_exists"):
        return f"the {hook} fetch did not end 0 with its file"
    return None


def n1_death_source(
    run_dir: Path, manifest: dict[str, Any] | None
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """The death source of a harness run directory, from the manifest's
    ``restart`` record and the Docker events capture with its coverage
    record, placed by the run's ``controller_metrics.csv`` (without it the
    death serves no identity): (deaths, note), deaths None when the capture
    cannot be read."""
    why = _fetch_problem(manifest, "docker_events")
    if why is not None:
        return None, why
    sut = Path(run_dir) / "logs" / SUT_LOG_SUBDIR
    lines, why = n1_report.read_text_lines(sut / SUT_LOG_FILES["docker_events"])
    if lines is None:
        return None, f"the Docker events capture was not read ({why})"
    coverage, _why = n1_report.read_text_lines(sut / DOCKER_EVENTS_COVERAGE)
    readings, readings_note = n1_report.read_controller_readings(Path(run_dir) / CONTROLLER_METRICS_FILENAME)
    return n1_report.controller_deaths(
        manifest.get("restart"), lines, "\n".join(coverage) if coverage is not None else None,
        readings=readings, readings_note=readings_note,
    )


def n1_a3_source(
    run_dir: Path, manifest: dict[str, Any] | None
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """The A3 connection ends of a harness run's controller log: (ends,
    None), or (None, why) when the log cannot be read."""
    why = _fetch_problem(manifest, "controller_log")
    if why is not None:
        return None, why
    lines, why = n1_report.read_text_lines(
        Path(run_dir) / "logs" / SUT_LOG_SUBDIR / SUT_LOG_FILES["controller_log"]
    )
    if lines is None:
        return None, why
    return n1_report.a3_connection_ends(lines), None


def n1_of_run(
    run_dir: Path, run_id: str, facts: dict[str, Any], manifest: dict[str, Any] | None
) -> dict[str, Any]:
    """The N1 report of one run directory (:mod:`egw_experiments.n1_report`),
    with the events copy it read (``events_copy``): the post-drain copy when
    it is present and verified, otherwise the timed copy, whose identities
    are then listed as unexplained only."""
    copy = POST_DRAIN_EVENTS_FILENAME if facts.get("post_drain_verified") else TIMED_EVENTS_FILENAME
    events, why = n1_report.read_jsonl(Path(run_dir) / copy)
    if events is None:
        return {"events_copy": None, "problem": f"no events copy could be read ({why})"}
    sent, _why = n1_report.read_jsonl(Path(run_dir) / "sent_events.jsonl")
    snapshots = {
        hook: n1_report.twin_devices(n1_report.read_json_object(Path(run_dir) / file)[0])
        for hook, file in TWIN_SNAPSHOT_FILES.items()
    }
    problem = n1_evidence_problem(facts)
    if problem is None and copy != POST_DRAIN_EVENTS_FILENAME:
        problem = f"the post-drain copy ({POST_DRAIN_EVENTS_FILENAME}) is not present and verified"
    deaths, deaths_note = n1_death_source(run_dir, manifest)
    ends, a3_note = n1_a3_source(run_dir, manifest)
    report = n1_report.n1_applied_unconfirmed(
        run_id=run_id,
        sent_records=sent,
        events=events,
        twins_before=snapshots["twin_snapshot_before"],
        twins_after=snapshots["twin_snapshot_after"],
        twin_evidence_problem=problem,
        deaths=deaths,
        deaths_note=deaths_note,
        a3_ends=ends,
        a3_note=a3_note,
    )
    return {"events_copy": copy, **report}


def evaluate_criterion(
    members: list[dict[str, Any]],
    *,
    execution_mode: str | None = None,
    elsewhere: Iterable[dict[str, Any]] = (),
    planned_ids: Sequence[str] | None = None,
    plan_problem: str | None = None,
) -> dict[str, Any]:
    """The criterion of ONE execution-mode group (plan 429-432: execution
    modes are never pooled into one criterion).

    ``members`` are the run records (:func:`inspect_run`) of the group:
    records of more than one group among them, or of a group other than
    ``execution_mode`` when it is named, raise
    :class:`~egw_experiments.analyze.MixedExecutionModeError`, as the
    analyser's aggregators do; the caller partitions the runs.
    ``elsewhere`` are the records the group's evaluation must still name:
    the planned runs outside the group (a planned run of another group is
    not evidence for this one, so it is ``not_evidenced`` here, its own
    qualification in the reason) and the runs in no group (a planned run
    without a directory, a provenance failure), which keep their own
    qualification. The records are taken in plan order, then the
    unplanned ones by run id, as the JSON lists them.

    ``planned_ids`` are the plan's controller_restart runs, None when no
    plan was read (``plan_problem`` then says why, when the plan could not
    be read). Returns ``name``, ``execution_mode``,
    ``execution_mode_label``, ``passed``, ``detail`` and
    ``not_qualified``.
    """
    group = require_single_execution_mode(
        [{"execution_mode_group": record.get("execution_mode")} for record in members],
        what=f"{CRITERION} (recovery qualification)",
        execution_mode=execution_mode,
    )
    planned = list(planned_ids) if planned_ids is not None else []
    position = {run_id: index for index, run_id in enumerate(planned)}
    records = sorted(
        [*members, *elsewhere],
        key=lambda r: (
            (0, position[r["run_id"]], "")
            if r.get("run_id") in position
            else (1, 0, str(r.get("run_id")))
        ),
    )

    def entry(record: dict[str, Any]) -> dict[str, Any]:
        other = record.get("execution_mode")
        if other is None or other == group:
            return {
                "run_id": record["run_id"],
                "qualification": record["qualification"],
                "reason": record["reason"],
            }
        return {
            "run_id": record["run_id"],
            "qualification": "not_evidenced",
            "reason": (
                f"in execution-mode group {other!r}, not {group!r}: execution "
                "modes are never pooled (plan 429-432); its own qualification "
                f"is {record['qualification']}"
            ),
        }

    entries = [entry(record) for record in records]
    not_qualified = [e for e in entries if e["qualification"] != "recovery_observed"]
    counts = (
        f"{len(entries) - len(not_qualified)}/{len(entries)} controller_restart "
        "run(s) recovery_observed"
    )
    unplanned = [record for record in records if not record.get("planned")]
    if planned_ids is None:
        passed = False
        detail = (
            (f"the campaign plan could not be read ({plan_problem})" if plan_problem
             else "no campaign plan supplied")
            + ", so the planned set of controller_restart runs is unknown; "
            + f"{counts} among the directories found in raw/"
        )
    elif not planned:
        # An unplanned directory never stands for a planned run: with no
        # controller_restart run in the plan there is nothing to qualify,
        # whatever raw/ holds (its directories stay listed, unplanned).
        passed = False
        detail = "the campaign plan lists no controller_restart run"
        if unplanned:
            detail += (
                f"; {counts} among {len(unplanned)} unplanned "
                + ("directory" if len(unplanned) == 1 else "directories")
                + " in raw/, which do not stand for a planned run"
            )
        else:
            detail += " and raw/ holds none"
    else:
        passed = not not_qualified
        detail = counts + f" ({len(planned)} planned"
        detail += f", {len(unplanned)} unplanned)" if unplanned else ")"
    return {
        "name": CRITERION,
        "execution_mode": group,
        "execution_mode_label": execution_mode_label(group),
        "passed": passed,
        "detail": detail,
        "not_qualified": not_qualified,
    }


def qualify_recovery(
    base_dir: str | Path | None, plan_path: str | Path | None
) -> dict[str, Any]:
    """The qualification document: every controller_restart run of the plan
    (and any unplanned one under ``raw/``) with its execution-mode group,
    the criterion evaluated once per group, the statement.

    ``plan_path`` None falls back to the analyser's ``EGW_CAMPAIGN_PLAN``
    variable (:func:`load_campaign_plan_for_analysis`); an unreadable plan
    is reported in ``plan_problem`` and treated as no plan. Raises
    ``FileNotFoundError`` when ``raw/`` does not exist.

    The groups are those of the runs (in the analyser's order: the
    recorded modes, then ``unrecorded``), or the single group None when no
    run has one. ``criteria_by_execution_mode`` holds one
    :func:`evaluate_criterion` per group; ``criterion`` is that evaluation
    when there is one group, and for several a criterion that never passes
    (no criterion is met across groups) and names them.
    """
    base = Path(base_dir) if base_dir is not None else DEFAULT_RESULTS_BASE
    raw_dir = base / "raw"
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"{raw_dir} does not exist")
    plan, plan_problem = load_campaign_plan_for_analysis(plan_path)
    planned_ids: list[str] = []
    if plan is not None:
        planned_ids = [
            str(entry["run_id"])
            for entry in plan["runs"]
            if isinstance(entry, dict)
            and entry.get("condition_id") == CONDITION_ID
            and entry.get("run_id")
        ]
    unplanned_ids: list[str] = []
    for run_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        if run_dir.name in planned_ids:
            continue
        try:
            manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(manifest, dict) and manifest.get("condition_id") == CONDITION_ID:
            unplanned_ids.append(run_dir.name)
    runs = [inspect_run(raw_dir / run_id, run_id, planned=True) for run_id in planned_ids]
    runs += [inspect_run(raw_dir / run_id, run_id, planned=False) for run_id in unplanned_ids]

    groups: list[str | None] = sorted(
        {r["execution_mode"] for r in runs if r["execution_mode"] is not None},
        key=_group_order,
    ) or [None]
    criteria = [
        evaluate_criterion(
            [r for r in runs if r["execution_mode"] == group],
            execution_mode=group,
            elsewhere=[
                r
                for r in runs
                if r["execution_mode"] != group
                and (r["planned"] or r["execution_mode"] is None)
            ],
            planned_ids=planned_ids if plan is not None else None,
            plan_problem=plan_problem,
        )
        for group in groups
    ]
    if len(criteria) == 1:
        criterion = criteria[0]
    else:
        verdicts = ", ".join(
            f"{c['execution_mode']} {'PASSED' if c['passed'] else 'FAILED'}" for c in criteria
        )
        criterion = {
            "name": CRITERION,
            "execution_mode": None,
            "execution_mode_label": SEVERAL_GROUPS_LABEL,
            "passed": False,
            "detail": (
                f"the controller_restart runs belong to {len(groups)} "
                f"execution-mode groups ({', '.join(str(g) for g in groups)}); the "
                f"criterion is evaluated once per group ({verdicts}) and never "
                "across groups (plan 429-432)"
            ),
            "not_qualified": [],
        }
    return {
        "condition_id": CONDITION_ID,
        "plan": str(plan_path) if plan is not None and plan_path is not None else (
            "EGW_CAMPAIGN_PLAN" if plan is not None else None
        ),
        "plan_problem": plan_problem,
        "runs": runs,
        "criterion": criterion,
        "criteria_by_execution_mode": criteria,
        "statement": STATEMENT,
    }


def _criterion_line(criterion: dict[str, Any], *, group: bool) -> str:
    """One ``[recovery]`` line: the criterion, its detail, its group when
    ``group``, and the runs that are not qualified."""
    line = (
        f"[recovery] {criterion['name']}: "
        f"{'PASSED' if criterion['passed'] else 'FAILED'} - {criterion['detail']}"
    )
    if group:
        named = criterion.get("execution_mode")
        line += f"; execution-mode group {named if named is not None else NO_GROUP_NAME}"
    if criterion["not_qualified"]:
        line += "; not qualified: " + ", ".join(
            f"{n['run_id']} ({n['qualification']}" + (f": {n['reason']}" if n["reason"] else "") + ")"
            for n in criterion["not_qualified"]
        )
    return line


def summary_line(doc: dict[str, Any]) -> str:
    """What the CLI prints: one line with the criterion, its group, the
    counts, the runs that are not qualified and where the files are; for
    runs of several execution-mode groups, that line (the criterion that
    names the groups) followed by one line per group."""
    per_group = doc["criteria_by_execution_mode"]
    several = len(per_group) > 1
    first = _criterion_line(doc["criterion"], group=not several) + (
        f"; written to processed/{JSON_FILENAME} and processed/{CSV_FILENAME}; "
        "no count of lost, late or N1 changed"
    )
    if not several:
        return first
    return "\n".join([first, *(_criterion_line(c, group=True) for c in per_group)])


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def write_recovery_qualification(
    base_dir: str | Path | None = None, plan_path: str | Path | None = None
) -> tuple[int, str]:
    """Write the two files under ``<base>/processed/`` (created if absent,
    never cleaned: the analyser owns the rest of it) and return the exit
    code with the summary line: (0, line), or (2, "") with the error on
    stderr when ``raw/`` does not exist."""
    base = Path(base_dir) if base_dir is not None else DEFAULT_RESULTS_BASE
    try:
        doc = qualify_recovery(base, plan_path)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2, ""
    processed_dir = base / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    (processed_dir / JSON_FILENAME).write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (processed_dir / CSV_FILENAME).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for run in doc["runs"]:
            writer.writerow(_csv_value(run.get(column)) for column in CSV_COLUMNS)
    return 0, summary_line(doc)
