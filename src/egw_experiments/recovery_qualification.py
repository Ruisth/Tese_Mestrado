"""Recovery qualification of the controller_restart runs (ADR 0011 item 18;
review finding F2): an explicit layer beside the quantitative analyser.

``egw_experiments.analyze`` never reads ``drain.outcome``: its C12 criteria
are computed from the measured-window events and metrics, so a VALID run
whose drain gave up — a failed recovery, retained by ``run.py`` as an
observation and never a validity reason — can pass every row of
``acceptance_by_condition.csv``. ADR 0011 leaves ``analyze.py`` unchanged
and reserves the N1 counting for a separate decision, so the qualification
is enforced and reported here, in a layer of its own, and propagated into
the authoritative report as two files written beside the analyser's outputs
under ``processed/``:

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

This layer changes no count: lost, late, N1 and every other figure come
from ``egw_experiments.analyze``, whose per-run, summary, acceptance and
saturation outputs it neither reads nor rewrites, and it adds no row to the
acceptance table. It reads the sealed manifests' restart evidence records
alone (``drain``, ``twin_snapshots``, ``events_post_drain_fetch``,
``validity``, ``exclusion``) and the ``SHA256SUMS`` verification. The
``analyze`` command runs it after the analysis and keeps its own exit code
(``cli._cmd_analyze`` says why); ``recovery`` runs it alone. No timestamp
enters the files, so repeated runs over the same evidence are identical.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

from .analyze import (
    INTEGRITY_FAILED,
    INTEGRITY_OK,
    INTEGRITY_UNSEALED,
    check_run_integrity,
    load_campaign_plan_for_analysis,
)
from .run import (
    DEFAULT_RESULTS_BASE,
    DRAIN_OUTCOMES,
    MANIFEST_FILENAME,
    POST_DRAIN_EVENTS_FILENAME,
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
    "every figure comes from egw_experiments.analyze, unchanged (ADR 0011); "
    "the qualification is read from the sealed manifests' restart evidence "
    "records alone."
)

CSV_COLUMNS = [
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
]

_INTEGRITY_WORDS = {
    INTEGRITY_OK: "ok",
    INTEGRITY_FAILED: "failed",
    INTEGRITY_UNSEALED: "unsealed",
}


def qualification_of(facts: dict[str, Any]) -> tuple[str, str]:
    """The qualification of one run from the facts :func:`inspect_run`
    reads, and the reason when it is not ``recovery_observed``.

    Evidence first: a run that is not valid, not sealed and verified, or
    excluded evidences nothing, whatever its drain says. Then the drain:
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


def inspect_run(run_dir: Path, run_id: str, *, planned: bool) -> dict[str, Any]:
    """The facts of one controller_restart run, read from its sealed
    manifest, plus its qualification."""
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
    return facts


def qualify_recovery(
    base_dir: str | Path | None, plan_path: str | Path | None
) -> dict[str, Any]:
    """The qualification document: every controller_restart run of the plan
    (and any unplanned one under ``raw/``), the criterion, the statement.

    ``plan_path`` None falls back to the analyser's ``EGW_CAMPAIGN_PLAN``
    variable (:func:`load_campaign_plan_for_analysis`); an unreadable plan
    is reported in ``plan_problem`` and treated as no plan. Raises
    ``FileNotFoundError`` when ``raw/`` does not exist.
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

    not_qualified = [
        {"run_id": r["run_id"], "qualification": r["qualification"], "reason": r["reason"]}
        for r in runs
        if r["qualification"] != "recovery_observed"
    ]
    observed = sum(1 for r in runs if r["qualification"] == "recovery_observed")
    counts = f"{observed}/{len(runs)} controller_restart run(s) recovery_observed"
    if plan is None:
        passed = False
        detail = (
            (f"the campaign plan could not be read ({plan_problem})" if plan_problem
             else "no campaign plan supplied")
            + ", so the planned set of controller_restart runs is unknown; "
            + f"{counts} among the directories found in raw/"
        )
    elif not planned_ids:
        # An unplanned directory never stands for a planned run: with no
        # controller_restart run in the plan there is nothing to qualify,
        # whatever raw/ holds (its directories stay listed above, unplanned).
        passed = False
        detail = "the campaign plan lists no controller_restart run"
        if unplanned_ids:
            detail += (
                f"; {counts} among {len(unplanned_ids)} unplanned "
                + ("directory" if len(unplanned_ids) == 1 else "directories")
                + " in raw/, which do not stand for a planned run"
            )
        else:
            detail += " and raw/ holds none"
    else:
        passed = not not_qualified
        detail = counts + f" ({len(planned_ids)} planned"
        detail += f", {len(unplanned_ids)} unplanned)" if unplanned_ids else ")"
    return {
        "condition_id": CONDITION_ID,
        "plan": str(plan_path) if plan is not None and plan_path is not None else (
            "EGW_CAMPAIGN_PLAN" if plan is not None else None
        ),
        "plan_problem": plan_problem,
        "runs": runs,
        "criterion": {
            "name": CRITERION,
            "passed": passed,
            "detail": detail,
            "not_qualified": not_qualified,
        },
        "statement": STATEMENT,
    }


def summary_line(doc: dict[str, Any]) -> str:
    """The one line the CLI prints: the criterion, the counts, the runs
    that are not qualified and where the files are."""
    criterion = doc["criterion"]
    line = (
        f"[recovery] {criterion['name']}: "
        f"{'PASSED' if criterion['passed'] else 'FAILED'} - {criterion['detail']}"
    )
    if criterion["not_qualified"]:
        line += "; not qualified: " + ", ".join(
            f"{n['run_id']} ({n['qualification']}" + (f": {n['reason']}" if n["reason"] else "") + ")"
            for n in criterion["not_qualified"]
        )
    line += (
        f"; written to processed/{JSON_FILENAME} and processed/{CSV_FILENAME}; "
        "no count of lost, late or N1 changed"
    )
    return line


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
