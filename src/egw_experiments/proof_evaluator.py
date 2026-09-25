"""The finite proof's evaluator (ADR 0011, "The finite proof"): S1 to S6,
R1 to R4 and the inconclusive rule, applied by identity to the post-drain
copy of the events and to the twin snapshots of one proof session.

``python -m egw_experiments.proof_evaluator --run-dir DIR --out FILE
[--session FILE] [--adr FILE]``

What it is. The ADR's implementation record reserves for a layer of its own
"the proof's evaluator, which applies S1-S6 and R1-R4 - S4 with the twin's
evidence of a named N1 case - to the post-drain copy and the snapshots";
``run.py`` records ``drain.outcome`` and leaves the inconclusive rule to it.
This module reads one sealed run directory of the harness (manifest 1.4
with the item-18 records), the session facts the driver writes beside it,
and prints one verdict document, ``proof_verdict.json``, with three
sections that are never merged:

- ``instrumentation``: the harness's own ``validity`` kept as recorded and
  never decisive, the seal, and whether the proof's evidence is complete
  (both twin snapshots verified, a verified drain that was quiet or gave
  up, the post-drain copy fetched and verified, the three SUT logs fetched,
  the configuration identity embedded with W, a readable pre-kill reading,
  the directory sealed and verified) - every absence named, so that "any
  fetch listed above fails" can be applied;
- ``system_outcome``: the result, each criterion with the ADR's text
  verbatim, whether it holds (S) or was observed (R) and the evidence it
  rests on; the refutations, the inconclusive reasons, the report by class
  of identity, the named N1 cases and the window figure;
- ``restoration``: echoed from the session facts - the driver observes it,
  this module does not.

What it is not. Not ``recovery_qualification`` (campaign-level, gated on
the manifest's validity), not ``analyze`` (its C12 rows count in-window
repeats only) and not ``nominal_account``. It writes nothing into the run
directory and no timestamp into the document, so repeated runs over the
same evidence are byte-identical.

Identification rules. Where a criterion needs a rule to become code (which
reading is "the last reading before" the kill, which identities are the
restart classes, how an N1 case's source is established), the rule is
stated in :data:`IDENTIFICATION_RULES`, labelled with its flag, and carried
into the verdict beside the criterion it serves. No rule changes a
criterion, a threshold or a count of the ADR; every one is conservative:
what cannot be shown is never read as support, and a refutation rests only
on evidence that was read and verified (E-7): a post-drain copy or a twin
snapshot that is absent, unverified or unreadable leaves the criteria that
depend on it null, never observed.

Exit codes, as ``broker_measure.sh`` reads the broker verdict: 0 supports,
1 refutes, 3 inconclusive, 2 not evaluated (an input unreadable, a seal
that fails, a rule text that drifted from the ADR, a usage error, or a
failure of the evaluator itself - never exit 1, which is a result).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analyze import (
    INTEGRITY_FAILED,
    INTEGRITY_OK,
    INTEGRITY_UNSEALED,
    _parse_ts,
    check_run_integrity,
    controller_monotonic_ns_at,
)
from .checksums import SUMS_FILENAME, sha256_file
from .controller_metrics import CSV_HEADER, METRIC_FIELDS
from .itest_reconcile import HelperError, INGESTION_KEYS, load_devices
from .run import (
    CONFIG_IDENTITY_FILENAME,
    DRAIN_OUTCOMES,
    DRAIN_TRANSCRIPT_FILENAME,
    MANIFEST_FILENAME,
    POST_DRAIN_EVENTS_FILENAME,
    REPO_ROOT,
    RESTART_EVIDENCE_FLAGS,
    SUT_LOG_FETCH_FLAGS,
    SUT_LOG_FILES,
    SUT_LOG_SUBDIR,
    TWIN_SNAPSHOT_FILES,
    classify_drain_output,
    configuration_identity_problems,
    expected_twin_devices,
)

PROOF = "ADR 0011, The finite proof"
EVALUATOR_VERSION = "1"
LABEL = "ARM64 EMULATED (QEMU/TCG); an engineering diagnostic, not a G3 run"
VERDICT_FILENAME = "proof_verdict.json"

#: The ADR the rule texts are pinned to (``--adr`` and the unit test).
ADR_PATH = REPO_ROOT / "docs" / "adr" / "0011-controller-restart-recovery.md"

RESULT_SUPPORTS = "supports"
RESULT_REFUTES = "refutes"
RESULT_INCONCLUSIVE = "inconclusive"
RESULT_NOT_EVALUATED = "not-evaluated"

#: Exit code per result, as broker_measure.sh reads `broker_hold.py verdict`
#: (0 supports, 1 refutes, 3 inconclusive); 2 is argparse's usage code and
#: the code of everything that kept the proof from being evaluated.
EXIT_CODES = {
    RESULT_SUPPORTS: 0,
    RESULT_REFUTES: 1,
    RESULT_NOT_EVALUATED: 2,
    RESULT_INCONCLUSIVE: 3,
}

#: The WSL2 host clock is stepped backwards by 2-3 s about every 30 s
#: (LOG.md); every host wall-clock comparison the report makes carries this
#: band and never decides a criterion.
HOST_CLOCK_STEP_BAND_S = 3.0

#: The controller's log lines the evaluator reads (egw_controller.mqtt): an
#: A5 occurrence is the connection-end message at ERROR (the controller's
#: own stop logs the same message at INFO); the subscription line marks the
#: new process ready, on the guest clock, and is reported only.
A5_MESSAGE = "MQTT connection ended by the controller"
SUBSCRIPTION_GRANTED_MESSAGE = "MQTT subscription granted; bridge ready"

#: How an identity's post-drain lines are summarised for the report, in the
#: order of precedence: an `accepted` line is the recovered outcome whatever
#: follows it (a redelivery after the PUBACK adds a `duplicate`, N2).
OUTCOME_CLASSES = ("accepted", "duplicate", "failed", "rejected", "none")

#: The rules, verbatim from the ADR's "The finite proof" (and, for
#: "recovered", its options table): each is carried into the verdict beside
#: its result, and test_proof_evaluator pins every one to the ADR text so no
#: wording can drift silently. Line breaks of the ADR are single spaces.
RULES: dict[str, str] = {
    "restart_classes": (
        "The *restart classes* here are the valid identities published before "
        "the kill that have no outcome line written before it, and those "
        "published while the controller was away."
    ),
    "recovered": (
        "delivered to the controller after the kill or the outage — again, "
        "or for the first time — and ending with an `accepted` line; or, "
        "where its effect had already reached the twin, a `duplicate` line, "
        "which is the N1 case. An identity that obtains only a `failed` line "
        "has an outcome line but is not recovered"
    ),
    "support": (
        "all six, evaluated by identity after the drain. Only a run in which "
        "all six hold supports the option; a run that merely refutes nothing "
        "does not"
    ),
    "S1": (
        "The kill found work: the last reading before it shows "
        "`queue_depth + in_progress > 0`."
    ),
    "S2": (
        "Every published valid identity has at least one outcome line in the "
        "post-drain copy; and every valid identity of the restart classes ends "
        "with an `accepted` line, or is a named N1 case of S4. A restart-class "
        "identity whose only lines are `failed` does not support the option "
        '(see "Inconclusive").'
    ),
    "S3": "No identity has two `accepted` lines (`double_accepted = 0`).",
    "S4": (
        "Every identity with a `duplicate` line either also has an `accepted` "
        "line, or is a named N1 case. An N1 case has one of two sources, and "
        "the result names each case with its source **and with the twin's "
        "evidence that the identity was applied**: the identity in progress at "
        "the kill, or the identity in progress at a connection ended under A3 "
        "after its `PATCH` (item 6); and, on that identity's device, the "
        "post-drain twin snapshot's `accepted_count` exceeds the device's "
        "`accepted` lines by exactly the number of N1 cases named on it, with "
        "the twin's `last_seq` not below the identity's `seq`. Being in "
        "progress is not enough: an identity whose `PATCH` was never sent, "
        "redelivered after a later `seq` of its device had been applied, would "
        "also end with only a `duplicate` line — that is the order break R3 "
        "exists to detect, not an N1 case. Without the surplus the identity "
        "was not applied and R3 applies"
    ),
    "S5": (
        "The runbook's `delta` is `OK` for every twin "
        "(`qemu_integrated_gateway.md:1130`), except, on the device of each "
        "named N1 case of S4, a difference of exactly one per such case — "
        "the difference S4 requires as the case's evidence, not merely permits."
    ),
    "S6": (
        "`max(queue_depth + in_progress)` stayed below W — or the result "
        "states that the window filled, and from when (P5)."
    ),
    "R1": "After a completed drain, a published valid identity has no outcome line.",
    "R2": "An identity has two `accepted` lines.",
    "R3": (
        "An identity has only `duplicate` lines and is not a named N1 case of "
        "S4 (in progress at the kill, or at an A3 connection end listed under "
        "item 6, **and** shown applied by the twin's surplus of S4): a genuine "
        "message was rejected, through the ordering of N5 or a wrong rebuild."
    ),
    "R4": (
        "A `delta` mismatch beyond S5's named cases, or a twin whose `last_seq` "
        "regressed."
    ),
    "refutation": (
        "A refutation is a result: it is recorded and preserved, never re-run "
        "away."
    ),
    "inconclusive": (
        "the attempt is preserved as incomplete and no result is claimed: the "
        "kill found nothing in flight (S1 fails); a `drained` call reaches its "
        "limit; any fetch listed above fails; a stop rule of the ceiling is "
        "reached; or, when none of R1 to R4 holds, a restart-class identity "
        "ends with only `failed` lines, which the result names with the error "
        "each line records. An inconclusive run is not passing: the student "
        "decides whether to repeat it — the same design, recorded as a "
        "repeat, the first run kept — or to re-decide the option, as under "
        "C3."
    ),
    "cannot_show": (
        "One run supports the property for that run; it does not prove it in "
        "general. It says nothing about the graceful stop (regression tests), "
        "a broker restart or a guest loss (N3), any other load or duration, "
        "latency, throughput, or the validity of a `controller_restart` run "
        "under the ingest rule (N8). The harness may again mark the run "
        "invalid under `MAX_SAMPLE_GAP_S`; that verdict belongs to the "
        "campaign rules and is kept as recorded, while the proof's answer "
        "comes from reconciliation by identity, which that rule does not "
        "touch."
    ),
}

SUPPORT_RULE_IDS = ("S1", "S2", "S3", "S4", "S5", "S6")
REFUTATION_RULE_IDS = ("R1", "R2", "R3", "R4")

#: The rules this evaluator adds to make the criteria computable, each
#: labelled with its flag (P-n: a decision the design proposal puts to the
#: Project Manager; E-n: a reading of the ADR's text this module makes and
#: states). Every one is carried into the verdict beside the criterion it
#: serves, so a reader sees what was decided by the ADR and what by code.
IDENTIFICATION_RULES: dict[str, str] = {
    "P-1": (
        "S1's \"last reading before it\" is the last row, in file order, of "
        "controller_metrics.csv whose started_at is the pre-kill process's "
        "(the first readable row's); the row's ts_utc and the manifest's "
        "restart.started_utc are both harness-host wall clock and are shown "
        "beside each other as a cross-check only, since a WSL host step may "
        "misorder them by 2-3 s."
    ),
    "P-2": (
        "S6 with no readable reading of queue_depth and in_progress, or "
        "without W (the embedded configuration identity's "
        "broker_conf_values.max_inflight_messages is not a positive integer), "
        "cannot be stated and is treated as an inconclusive condition, "
        "although the ADR's rule does not list it: nothing can then be said "
        "about the window."
    ),
    "P-3": (
        "Restart-class membership is decided on the controller's clock: an "
        "identity is pre-kill-lined when some line's received_monotonic_ns is "
        "below the last pre-kill reading's monotonic_ns (the pre-kill process "
        "wrote it), restart-class when it has no line or every line's "
        "received_monotonic_ns is above the first post-kill reading's, and "
        "ambiguous when a line falls inside that band or carries no "
        "received_monotonic_ns. S2's second clause and the failed-only "
        "reading run over the restart class and the ambiguous identities "
        "together, so an ambiguous identity is never read as support. "
        "\"Published before the kill\" and \"published while the controller "
        "was away\" are report figures on the host clocks, with a stated band; "
        "they never decide a restart class, and only P-4 reads \"published "
        "before the kill\" to attribute the kill as an N1 case's source."
    ),
    "P-4": (
        "An N1 case's source is established by inference, since the "
        "controller's A5 occurrence names the delivery (topic, mid, qos, dup, "
        "connection, received_monotonic_ns) and not the identity: "
        "'a3-connection-end' when an ERROR occurrence of the connection-end "
        "message names the candidate's device in its topic and its "
        "in-progress delivery's received_monotonic_ns precedes the "
        "candidate's redelivered duplicate line; 'kill' when the candidate is "
        "restart-class, was published before the kill on the host clock and "
        "the manifest's restart executed with exit 0. A candidate is named "
        "only with the twin's evidence: the device's surplus equals the "
        "number of cases named on it and the after snapshot's last_seq is not "
        "below the candidate's seq."
    ),
    "P-5": (
        "R4's \"last_seq regressed\": the after snapshot's last_run_id is this "
        "run's and its last_seq is below the highest seq the run applied on "
        "the device (accepted lines and named N1 cases), or its last_run_id is "
        "the before snapshot's and its last_seq is below the before "
        "snapshot's; the seq floor resets per run_id."
    ),
    "P-6": (
        "Without the session facts (proof_session.json) whether a stop rule "
        "of the ceiling was reached is unknown, and the proof is inconclusive."
    ),
    "P-7": (
        "Precedence: a refutation observed (R2, R3 or R4 on what was read; R1 "
        "only after a completed drain) stands over every inconclusive "
        "condition, as broker_measure.sh treats a stop rule; otherwise any "
        "inconclusive condition makes the run inconclusive; 'supports' needs "
        "all six criteria to hold."
    ),
    "E-1": (
        "S2's \"ends with an `accepted` line\" is read as \"obtains an "
        "`accepted` line among its post-drain lines\": a redelivery after the "
        "PUBACK adds a `duplicate` line after the `accepted` one (N2), which "
        "S4 permits and S2 does not undo."
    ),
    "E-2": (
        "S5's tolerance on a device with named N1 cases: delta equals the "
        "device's accepted lines plus the named cases, and the expected "
        "last_seq is the highest seq among the run's accepted lines and its "
        "named cases on the device (an applied identity advanced the twin "
        "without an accepted line); the runbook's `delta` has no tolerance "
        "and exits 4 on such a device."
    ),
    "E-3": (
        "A criterion that does not hold while none of R1 to R4 is observed and "
        "none of the ADR's five inconclusive conditions applies (a "
        "restart-class identity whose lines are `rejected`, say) makes the "
        "run inconclusive, stated as 'does not support': a run that merely "
        "refutes nothing does not support the option, and no other result is "
        "defined for it."
    ),
    "E-4": (
        "At most one N1 case per death has the kill as its source (N1: one "
        "consumer); when more than one candidate claims it, none is named and "
        "each is R3."
    ),
    "E-5": (
        "A JSONL line that is not a JSON object, or not valid UTF-8 (a "
        "truncated or torn final line), is skipped and counted, as "
        "CONTRACTS.md's write rule tells a reader; the count is reported in "
        "the instrumentation section."
    ),
    "E-6": (
        "The device of an A5 occurrence is the third segment of its "
        "identity.topic (c2dt/<egw_id>/<device_uuid>/telemetry); a compose or "
        "docker prefix before the JSON object is stripped before parsing."
    ),
    "E-7": (
        "A refutation rests only on evidence that was read and verified: when "
        "the post-drain copy is absent, not verified by the harness as this "
        "run's, or unreadable, S2 to S5 and R1 to R4 can be shown neither way "
        "and are null; when a twin snapshot is so, or names no twin for the "
        "device, S4, S5, R3 and R4 are null for what depends on it. The "
        "absence is named as a failed fetch and the run is inconclusive unless "
        "a refutation was observed on evidence that was read."
    ),
}


class ProofInputError(Exception):
    """An input the proof cannot be evaluated without (exit 2)."""


def _ws(text: str) -> str:
    """The text with every run of whitespace as one space (the ADR wraps
    its lines; the constants above do not)."""
    return " ".join(text.split())


def rule_texts_not_in(adr_path: Path) -> list[str]:
    """The rule ids of :data:`RULES` whose text is not, whitespace aside,
    a substring of the ADR at ``adr_path``: a drift of the wording."""
    try:
        adr = _ws(Path(adr_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProofInputError(f"the ADR cannot be read: {exc}") from None
    return [rule_id for rule_id, text in RULES.items() if _ws(text) not in adr]


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _int_cell(text: Any) -> int | None:
    """A CSV cell as a non-negative integer, or None: an empty cell is an
    absent field and never zero (CONTRACTS 5); a fractional, negative or
    non-numeric cell is unreadable."""
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        try:
            number = float(raw)
        except ValueError:
            return None
        if not math.isfinite(number) or not number.is_integer():
            return None
        value = int(number)
    return value if value >= 0 else None


def _float_cell(text: Any) -> float | None:
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        number = float(raw)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _str_cell(text: Any) -> str | None:
    if text is None:
        return None
    raw = str(text).strip()
    return raw or None


# ---------------------------------------------------------------------------
# I/O layer: the artefacts of one proof session, read once, no logic
# ---------------------------------------------------------------------------


@dataclass
class RunArtefacts:
    """What :func:`load_run_dir` read from the run directory."""

    run_dir: Path
    manifest: dict[str, Any]
    sent_events: list[dict[str, Any]]
    events_timed: list[dict[str, Any]] | None
    events_post_drain: list[dict[str, Any]] | None
    twins_before: dict[str, Any] | None
    twins_after: dict[str, Any] | None
    metrics_rows: list[dict[str, Any]] | None
    metrics_header: list[str] | None
    configuration_identity: dict[str, Any] | None
    controller_log: list[str] | None
    broker_log: list[str] | None
    docker_events: list[str] | None
    drain_text: str | None
    integrity: str
    integrity_problems: list[str]
    sha256s: dict[str, str]
    files_present: set[str]
    skipped_lines: dict[str, int]
    problems: list[str]
    #: What was read but not as expected (a CSV header that is not the
    #: sampler's): reported, never a failed fetch.
    notes: list[str] = field(default_factory=list)


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    """The JSON objects of a JSONL file in file order, and the count of
    lines that are not one (E-5): skipped, never guessed at. Each line is
    decoded on its own, so a line that is not UTF-8 (a torn write) is one
    skipped line and not a failure of the whole file."""
    records: list[dict[str, Any]] = []
    skipped = 0
    with open(path, "rb") as fh:
        for raw in fh:
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw.decode("utf-8"))
            except ValueError:  # UnicodeDecodeError is one
                skipped += 1
                continue
            if isinstance(obj, dict):
                records.append(obj)
            else:
                skipped += 1
    return records, skipped


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProofInputError(f"{path.name} unreadable: {exc}") from None
    if not isinstance(obj, dict):
        raise ProofInputError(f"{path.name} is not a JSON object")
    return obj


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def load_run_dir(run_dir: Path) -> RunArtefacts:
    """Read every artefact of the run directory the proof needs. The
    manifest and sent_events.jsonl are required (ProofInputError without
    them); everything else is None when absent and named in ``problems``
    when present but unreadable, so the evidence status can say what is
    missing instead of the evaluation failing."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise ProofInputError(f"{run_dir} is not a directory")
    files_present = {
        p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file()
    }
    manifest = _read_json_object(run_dir / MANIFEST_FILENAME)
    problems: list[str] = []
    notes: list[str] = []
    skipped: dict[str, int] = {}
    sha256s: dict[str, str] = {}

    def _sha(rel: str) -> None:
        sha256s[rel] = sha256_file(run_dir / rel)

    _sha(MANIFEST_FILENAME)
    sent_path = run_dir / "sent_events.jsonl"
    if not sent_path.is_file():
        raise ProofInputError("sent_events.jsonl is missing: no published identity can be read")
    sent_events, skipped["sent_events.jsonl"] = _read_jsonl(sent_path)
    _sha("sent_events.jsonl")

    def _jsonl(rel: str) -> list[dict[str, Any]] | None:
        if rel not in files_present:
            return None
        try:
            records, skipped[rel] = _read_jsonl(run_dir / rel)
        except OSError as exc:
            problems.append(f"{rel} unreadable: {exc}")
            return None
        _sha(rel)
        return records

    def _twins(rel: str) -> dict[str, Any] | None:
        if rel not in files_present:
            return None
        try:
            devices = load_devices(run_dir / rel)
        except HelperError as exc:
            # The helper names the file by its full path; the document
            # carries the relative one, so the bytes do not depend on where
            # the run directory sits.
            text = str(exc)
            full = str(run_dir / rel)
            if text.startswith(full):
                text = rel + text[len(full):]
            problems.append(text if text.startswith(rel) else f"{rel}: {text}")
            return None
        _sha(rel)
        return devices

    def _text_lines(rel: str) -> list[str] | None:
        if rel not in files_present:
            return None
        try:
            lines = _read_lines(run_dir / rel)
        except OSError as exc:
            problems.append(f"{rel} unreadable: {exc}")
            return None
        _sha(rel)
        return lines

    events_timed = _jsonl("events.jsonl")
    events_post_drain = _jsonl(POST_DRAIN_EVENTS_FILENAME)
    twins_before = _twins(TWIN_SNAPSHOT_FILES["twin_snapshot_before"])
    twins_after = _twins(TWIN_SNAPSHOT_FILES["twin_snapshot_after"])

    metrics_rows: list[dict[str, Any]] | None = None
    metrics_header: list[str] | None = None
    if "controller_metrics.csv" in files_present:
        try:
            with open(run_dir / "controller_metrics.csv", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                metrics_rows = list(reader)
                metrics_header = list(reader.fieldnames or [])
        except (OSError, csv.Error, ValueError) as exc:  # a decode error is a ValueError
            problems.append(f"controller_metrics.csv unreadable: {exc}")
        else:
            _sha("controller_metrics.csv")
            if metrics_header != CSV_HEADER:
                notes.append(
                    "controller_metrics.csv: the header is not the sampler's "
                    f"{len(CSV_HEADER)}-column header; absent columns read as "
                    "absent fields"
                )

    configuration_identity: dict[str, Any] | None = None
    if CONFIG_IDENTITY_FILENAME in files_present:
        try:
            configuration_identity = _read_json_object(run_dir / CONFIG_IDENTITY_FILENAME)
        except ProofInputError as exc:
            problems.append(str(exc))
        else:
            _sha(CONFIG_IDENTITY_FILENAME)

    logs = "logs/" + SUT_LOG_SUBDIR
    controller_log = _text_lines(f"{logs}/{SUT_LOG_FILES['controller_log']}")
    broker_log = _text_lines(f"{logs}/{SUT_LOG_FILES['broker_log']}")
    docker_events = _text_lines(f"{logs}/{SUT_LOG_FILES['docker_events']}")

    drain_parts: list[str] = []
    for rel in (
        f"{logs}/hook-drain.stdout.txt",
        f"{logs}/hook-drain.stderr.txt",
        f"{logs}/{DRAIN_TRANSCRIPT_FILENAME}",
    ):
        lines = _text_lines(rel)
        if lines is not None:
            drain_parts.append("\n".join(lines))
    drain_text = "\n".join(drain_parts) if drain_parts else None

    integrity, integrity_problems = check_run_integrity(run_dir)
    if SUMS_FILENAME in files_present:
        _sha(SUMS_FILENAME)
    return RunArtefacts(
        run_dir=run_dir,
        manifest=manifest,
        sent_events=sent_events,
        events_timed=events_timed,
        events_post_drain=events_post_drain,
        twins_before=twins_before,
        twins_after=twins_after,
        metrics_rows=metrics_rows,
        metrics_header=metrics_header,
        configuration_identity=configuration_identity,
        controller_log=controller_log,
        broker_log=broker_log,
        docker_events=docker_events,
        drain_text=drain_text,
        integrity=integrity,
        integrity_problems=integrity_problems,
        sha256s=sha256s,
        files_present=files_present,
        skipped_lines=skipped,
        problems=problems,
        notes=notes,
    )


def load_session_facts(path: Path | None) -> dict[str, Any] | None:
    """The driver's proof_session.json, or None when no path was given (the
    stop rules are then unknown, P-6)."""
    if path is None:
        return None
    return _read_json_object(Path(path))


# ---------------------------------------------------------------------------
# Readings: controller_metrics.csv in file order, split by process
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricsRow:
    """One row of controller_metrics.csv: every counter ``int | None`` (an
    empty cell is None, never zero), the raw fields typed, file order kept
    in ``index``."""

    index: int
    ts_utc: str
    counters: dict[str, int | None]
    mqtt_subscribed: bool | None
    started_at: str | None
    wall_utc: str | None
    uptime_s: float | None
    monotonic_ns: int | None

    @property
    def queue_depth(self) -> int | None:
        return self.counters.get("queue_depth")

    @property
    def in_progress(self) -> int | None:
        return self.counters.get("in_progress")

    @property
    def unacked(self) -> int | None:
        return self.counters.get("unacked")

    @property
    def in_flight(self) -> int | None:
        """``queue_depth + in_progress`` when both are readable."""
        if self.queue_depth is None or self.in_progress is None:
            return None
        return self.queue_depth + self.in_progress

    def place(self) -> dict[str, Any]:
        return {
            "row": self.index,
            "ts_utc": self.ts_utc,
            "monotonic_ns": self.monotonic_ns,
            "started_at": self.started_at,
        }


def read_metrics_rows(raw_rows: list[dict[str, Any]]) -> tuple[list[MetricsRow], list[str]]:
    """The rows of controller_metrics.csv typed, in FILE order, with the
    notes on the host clock: a ``ts_utc`` earlier than the previous row's is
    reported and kept, never dropped (analyze's reader drops it and carries
    neither in_progress nor started_at, so it cannot serve S1 and S6)."""
    rows: list[MetricsRow] = []
    notes: list[str] = []
    previous = None
    for index, raw in enumerate(raw_rows):
        ts_utc = _str_cell(raw.get("ts_utc")) or ""
        subscribed_cell = _str_cell(raw.get("mqtt_subscribed"))
        subscribed = (
            True if subscribed_cell == "true" else False if subscribed_cell == "false" else None
        )
        row = MetricsRow(
            index=index,
            ts_utc=ts_utc,
            counters={name: _int_cell(raw.get(name)) for name in METRIC_FIELDS},
            mqtt_subscribed=subscribed,
            started_at=_str_cell(raw.get("started_at")),
            wall_utc=_str_cell(raw.get("wall_utc")),
            uptime_s=_float_cell(raw.get("uptime_s")),
            monotonic_ns=_int_cell(raw.get("monotonic_ns")),
        )
        rows.append(row)
        stamp = _parse_ts(ts_utc) if ts_utc else None
        if stamp is not None:
            if previous is not None and stamp < previous[1]:
                notes.append(
                    f"row {index}: ts_utc {ts_utc} is earlier than row "
                    f"{previous[0]}'s {previous[2]} (a host clock step); kept in "
                    "file order, never dropped"
                )
            previous = (index, stamp, ts_utc)
    return rows, notes


@dataclass
class ProcessSplit:
    """The rows by controller process: ``started_at`` identifies the
    process (CONTRACTS 5); the first readable row's is the pre-kill one."""

    pre_kill: list[MetricsRow]
    post_kill: list[MetricsRow]
    unreadable: list[MetricsRow]
    pre_started_at: str | None
    post_started_ats: list[str]


def split_by_process(rows: list[MetricsRow]) -> ProcessSplit:
    pre_started_at = next((r.started_at for r in rows if r.started_at is not None), None)
    pre_kill = [r for r in rows if r.started_at is not None and r.started_at == pre_started_at]
    post_kill = [r for r in rows if r.started_at is not None and r.started_at != pre_started_at]
    unreadable = [r for r in rows if r.started_at is None]
    return ProcessSplit(
        pre_kill=pre_kill,
        post_kill=post_kill,
        unreadable=unreadable,
        pre_started_at=pre_started_at,
        post_started_ats=sorted({r.started_at for r in post_kill if r.started_at}),
    )


@dataclass
class KillBand:
    """The kill placed on the controller's clock: after the last pre-kill
    reading (``lower``) and before the first post-kill reading (``upper``),
    both ``monotonic_ns`` values the controller itself reported (the
    controller's monotonic clock is boot-relative, so it survives the
    restart; see analyze.controller_monotonic_ns_at)."""

    lower: int | None
    upper: int | None
    lower_row: MetricsRow | None
    upper_row: MetricsRow | None

    @property
    def known(self) -> bool:
        return self.lower is not None and self.upper is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "k_lower_monotonic_ns": self.lower,
            "k_upper_monotonic_ns": self.upper,
            "lower_row": self.lower_row.place() if self.lower_row else None,
            "upper_row": self.upper_row.place() if self.upper_row else None,
            "clock": "controller monotonic_ns as /metrics reported it",
        }


def kill_band(pre_kill: list[MetricsRow], post_kill: list[MetricsRow]) -> KillBand:
    lower_row = max(
        (r for r in pre_kill if r.monotonic_ns is not None),
        key=lambda r: r.monotonic_ns,
        default=None,
    )
    upper_row = min(
        (r for r in post_kill if r.monotonic_ns is not None),
        key=lambda r: r.monotonic_ns,
        default=None,
    )
    return KillBand(
        lower=lower_row.monotonic_ns if lower_row else None,
        upper=upper_row.monotonic_ns if upper_row else None,
        lower_row=lower_row,
        upper_row=upper_row,
    )


# ---------------------------------------------------------------------------
# Identities: the simulator's sent lines and the controller's outcome lines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sent:
    """One published identity, as sent_events.jsonl records it."""

    message_id: str
    device_uuid: str | None
    device_type: str | None
    seq: int | None
    publish_monotonic_ns: int | None
    intended_invalid: bool


@dataclass
class SentIndex:
    valid: dict[str, Sent]
    intended_invalid: dict[str, Sent]
    other_run_id: int
    malformed: int
    repeated: int


def valid_identities(sent_events: list[dict[str, Any]], run_id: str) -> SentIndex:
    """The identities of this run by ``message_id``: the valid ones (not
    ``intended_invalid``) apart from the intended-invalid ones, which are
    reported and never enter a criterion. A repeated ``message_id`` keeps
    its first line and is counted."""
    valid: dict[str, Sent] = {}
    invalid: dict[str, Sent] = {}
    other = malformed = repeated = 0
    for record in sent_events:
        if record.get("run_id") != run_id:
            other += 1
            continue
        message_id = record.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            malformed += 1
            continue
        if message_id in valid or message_id in invalid:
            repeated += 1
            continue
        seq = record.get("seq")
        publish = record.get("publish_monotonic_ns")
        sent = Sent(
            message_id=message_id,
            device_uuid=record.get("device_uuid") if isinstance(record.get("device_uuid"), str) else None,
            device_type=record.get("device_type") if isinstance(record.get("device_type"), str) else None,
            seq=seq if _is_int(seq) else None,
            publish_monotonic_ns=publish if _is_int(publish) else None,
            intended_invalid=record.get("intended_invalid") is True,
        )
        (invalid if sent.intended_invalid else valid)[message_id] = sent
    return SentIndex(valid, invalid, other, malformed, repeated)


@dataclass
class LinesIndex:
    by_id: dict[str, list[dict[str, Any]]]
    other_run_id: int
    unattributed: int
    total: int

    def outcomes(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for lines in self.by_id.values():
            for line in lines:
                key = str(line.get("outcome"))
                counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))


def lines_by_identity(events: list[dict[str, Any]], run_id: str) -> LinesIndex:
    """The outcome lines of this run by ``message_id``, in file order; a
    line of another run or without a ``message_id`` is counted apart."""
    by_id: dict[str, list[dict[str, Any]]] = {}
    other = unattributed = 0
    for line in events:
        if line.get("run_id") != run_id:
            other += 1
            continue
        message_id = line.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            unattributed += 1
            continue
        by_id.setdefault(message_id, []).append(line)
    return LinesIndex(by_id, other, unattributed, len(events))


def _outcomes_of(lines: list[dict[str, Any]]) -> list[str]:
    return [str(line.get("outcome")) for line in lines]


def _has(lines: list[dict[str, Any]], outcome: str) -> bool:
    return any(line.get("outcome") == outcome for line in lines)


def _only(lines: list[dict[str, Any]], outcome: str) -> bool:
    return bool(lines) and all(line.get("outcome") == outcome for line in lines)


def _ending(lines: list[dict[str, Any]]) -> str:
    for outcome in OUTCOME_CLASSES[:-1]:
        if _has(lines, outcome):
            return outcome
    return "none"


def _received(line: dict[str, Any]) -> int | None:
    value = line.get("received_monotonic_ns")
    return value if _is_int(value) else None


def _sorted_ids(ids: Any, sent: dict[str, Sent]) -> list[str]:
    """Identities ordered by device, seq, message_id: a stable order for
    the document whatever the dict order was."""
    return sorted(
        ids,
        key=lambda m: (
            (sent[m].device_uuid or "") if m in sent else "",
            (sent[m].seq if m in sent and sent[m].seq is not None else -1),
            m,
        ),
    )


def _identity(sent: Sent) -> dict[str, Any]:
    return {"message_id": sent.message_id, "device_uuid": sent.device_uuid, "seq": sent.seq}


# ---------------------------------------------------------------------------
# The restart classes (P-3)
# ---------------------------------------------------------------------------


@dataclass
class Classification:
    pre_kill_lined: list[str]
    restart_class: list[str]
    ambiguous: list[str]
    published_before_kill: list[str]
    published_while_away: list[str]
    published_after_resubscription: list[str]
    publication_unplaced: list[str]
    band: dict[str, Any]
    away_window: dict[str, Any]
    notes: list[str]

    @property
    def restart_or_ambiguous(self) -> list[str]:
        return self.restart_class + self.ambiguous

    def as_dict(self) -> dict[str, Any]:
        return {
            "pre_kill_lined": len(self.pre_kill_lined),
            "restart_class": len(self.restart_class),
            "ambiguous": len(self.ambiguous),
            "published_before_kill": len(self.published_before_kill),
            "published_while_away": len(self.published_while_away),
            "published_after_resubscription": len(self.published_after_resubscription),
            "publication_unplaced": len(self.publication_unplaced),
            "band": self.band,
            "away_window": self.away_window,
            "notes": self.notes,
        }


def _host_monotonic_of(manifest: dict[str, Any], ts_utc: str | None) -> int | None:
    """A harness-host wall-clock instant in the harness's monotonic domain,
    through the manifest's anchor (measured_window_utc.start,
    measured_started_monotonic_ns); the simulator's publish_monotonic_ns
    lives in that domain (same host, CLOCK_MONOTONIC)."""
    window = manifest.get("measured_window_utc")
    anchor_ns = manifest.get("measured_started_monotonic_ns")
    if not isinstance(window, dict) or not _is_int(anchor_ns) or not ts_utc:
        return None
    start = _parse_ts(str(window.get("start") or ""))
    stamp = _parse_ts(ts_utc)
    if start is None or stamp is None:
        return None
    return anchor_ns + int((stamp - start).total_seconds() * 1_000_000_000)


def classify_identities(
    valid: dict[str, Sent],
    lines: dict[str, list[dict[str, Any]]],
    band: KillBand,
    restart: dict[str, Any],
    manifest: dict[str, Any],
    post_kill: list[MetricsRow],
    subscription_granted_ts: list[str],
) -> Classification:
    """The restart classes by the controller-clock band (P-3), and the
    report's publication sub-classes on the host clocks."""
    pre_lined: list[str] = []
    restart_class: list[str] = []
    ambiguous: list[str] = []
    notes: list[str] = []
    if not band.known:
        notes.append(
            "the kill could not be placed on the controller clock (no readable "
            "monotonic_ns on both sides of the restart): every lined identity is "
            "ambiguous and every unlined one restart-class"
        )
    for message_id in valid:
        identity_lines = lines.get(message_id, [])
        if not identity_lines:
            restart_class.append(message_id)
            continue
        if not band.known:
            ambiguous.append(message_id)
            continue
        received = [_received(line) for line in identity_lines]
        if any(r is not None and r < band.lower for r in received):
            pre_lined.append(message_id)
        elif all(r is not None and r > band.upper for r in received):
            restart_class.append(message_id)
        else:
            ambiguous.append(message_id)

    kill_host_ns = restart.get("started_monotonic_ns") if isinstance(restart, dict) else None
    kill_host_ns = kill_host_ns if _is_int(kill_host_ns) else None
    resubscribed = next((r for r in post_kill if r.mqtt_subscribed is True), None)
    resub_host_ns = _host_monotonic_of(manifest, resubscribed.ts_utc if resubscribed else None)
    band_ns = int(HOST_CLOCK_STEP_BAND_S * 1_000_000_000)
    before: list[str] = []
    away: list[str] = []
    after: list[str] = []
    unplaced: list[str] = []
    for message_id, sent in valid.items():
        publish = sent.publish_monotonic_ns
        if publish is None or kill_host_ns is None:
            unplaced.append(message_id)
        elif publish < kill_host_ns:
            before.append(message_id)
        elif resub_host_ns is None:
            away.append(message_id)
        elif publish < resub_host_ns + band_ns:
            away.append(message_id)
        else:
            after.append(message_id)
    if kill_host_ns is None:
        notes.append("the manifest's restart record carries no started_monotonic_ns: publication is unplaced")
    elif resub_host_ns is None:
        notes.append(
            "no post-kill reading shows mqtt_subscribed true (or the manifest's host "
            "anchor is absent): every identity published after the kill is counted "
            "as published while the controller was away"
        )
    away_window = {
        "kill_host_monotonic_ns": kill_host_ns,
        "restart_started_utc": restart.get("started_utc") if isinstance(restart, dict) else None,
        "restart_finished_utc": restart.get("finished_utc") if isinstance(restart, dict) else None,
        "resubscribed_row": resubscribed.place() if resubscribed else None,
        "resubscribed_host_monotonic_ns": resub_host_ns,
        "band_s": HOST_CLOCK_STEP_BAND_S,
        "subscription_granted_ts_in_controller_log": subscription_granted_ts,
        "note": (
            "host wall clock and host monotonic through the manifest's anchor, with "
            f"a {HOST_CLOCK_STEP_BAND_S:g} s band for the host clock steps; the "
            "controller log's subscription line is on the guest clock and is "
            "reported beside it, never used to decide; none of these figures "
            "decides a criterion"
        ),
    }
    return Classification(
        pre_kill_lined=_sorted_ids(pre_lined, valid),
        restart_class=_sorted_ids(restart_class, valid),
        ambiguous=_sorted_ids(ambiguous, valid),
        published_before_kill=_sorted_ids(before, valid),
        published_while_away=_sorted_ids(away, valid),
        published_after_resubscription=_sorted_ids(after, valid),
        publication_unplaced=_sorted_ids(unplaced, valid),
        band=band.as_dict(),
        away_window=away_window,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------


@dataclass
class Criterion:
    """One rule with its result: for S1-S6 ``holds`` (True, False, or None
    when it cannot be read); for R1-R4 the same field means 'observed'."""

    rule_id: str
    holds: bool | None
    evidence: dict[str, Any]
    identification_rules: tuple[str, ...] = ()
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "rule": RULES[self.rule_id],
            "evidence": self.evidence,
            "identification_rules": {
                key: IDENTIFICATION_RULES[key] for key in self.identification_rules
            },
        }
        if self.rule_id in SUPPORT_RULE_IDS:
            doc["holds"] = self.holds
        else:
            doc["observed"] = self.holds
        if self.reason is not None:
            doc["reason"] = self.reason
        return doc


def s1_kill_found_work(
    pre_kill: list[MetricsRow], restart: dict[str, Any], controller_marker: Any = None
) -> Criterion:
    """S1 on the last pre-kill reading in file order (P-1)."""
    restart = restart if isinstance(restart, dict) else {}
    evidence: dict[str, Any] = {
        "restart_started_utc": restart.get("started_utc"),
        "restart_finished_utc": restart.get("finished_utc"),
        "restart_executed": restart.get("executed"),
        "restart_returncode": restart.get("returncode"),
        "pre_kill_rows": len(pre_kill),
        "cross_check_note": (
            "the reading's ts_utc and restart.started_utc are both harness-host wall "
            f"clock, shown as a cross-check only (a WSL host step may misorder them by "
            f"up to {HOST_CLOCK_STEP_BAND_S:g} s); started_at decides which process "
            "the reading belongs to"
        ),
    }
    if not pre_kill:
        evidence["last_reading"] = None
        return Criterion(
            "S1", None, evidence, ("P-1",),
            "no readable reading of the pre-kill process (no row with started_at)",
        )
    last = pre_kill[-1]
    evidence["last_reading"] = {
        **last.place(),
        "queue_depth": last.queue_depth,
        "in_progress": last.in_progress,
        "unacked": last.unacked,
        "in_flight": last.in_flight,
    }
    started = _parse_ts(str(restart.get("started_utc") or ""))
    if started is not None:
        evidence["restart_started_controller_monotonic_ns"] = controller_monotonic_ns_at(
            controller_marker, started
        )
    if last.in_flight is None:
        missing = [name for name in ("queue_depth", "in_progress") if last.counters.get(name) is None]
        return Criterion(
            "S1", None, evidence, ("P-1",),
            f"the last pre-kill reading (row {last.index}) has no {' and '.join(missing)}: "
            "an empty cell is an absent field, never zero, so the reading cannot be made",
        )
    holds = last.in_flight > 0
    reason = None if holds else (
        f"the last pre-kill reading (row {last.index}) shows queue_depth "
        f"{last.queue_depth} + in_progress {last.in_progress} = 0: the kill found nothing in flight"
    )
    return Criterion("S1", holds, evidence, ("P-1",), reason)


def s6_window(rows: list[MetricsRow], w: int | None) -> Criterion:
    """S6 over every readable reading; the window is stated filled from
    the first reading showing ``unacked >= W`` or ``queue_depth +
    in_progress >= W`` (P-2 when nothing can be stated)."""
    readable = [r for r in rows if r.in_flight is not None]
    evidence: dict[str, Any] = {
        "W": w,
        "readings": len(rows),
        "readable_readings": len(readable),
        "sampling_note": (
            "readings are taken at about 1 Hz and a failed poll writes no row, so a "
            "fill between two readings is unobservable"
        ),
    }
    if w is None:
        evidence.update({"max_queue_plus_in_progress": None, "filled": None, "filled_from": None})
        return Criterion(
            "S6", None, evidence, ("P-2",),
            "W (configuration_identity.broker_conf_values.max_inflight_messages) is not known",
        )
    if not readable:
        evidence.update({"max_queue_plus_in_progress": None, "filled": None, "filled_from": None})
        return Criterion(
            "S6", None, evidence, ("P-2",),
            "no reading carries both queue_depth and in_progress: nothing can be stated about the window",
        )
    peak = max(readable, key=lambda r: (r.in_flight, -r.index))
    filled_row = next(
        (
            r
            for r in rows
            if (r.unacked is not None and r.unacked >= w) or (r.in_flight is not None and r.in_flight >= w)
        ),
        None,
    )
    evidence["max_queue_plus_in_progress"] = peak.in_flight
    evidence["max_at"] = peak.place()
    evidence["filled"] = filled_row is not None
    evidence["filled_from"] = (
        {**filled_row.place(), "unacked": filled_row.unacked, "in_flight": filled_row.in_flight}
        if filled_row is not None
        else None
    )
    evidence["statement"] = (
        f"max(queue_depth + in_progress) = {peak.in_flight} stayed below W = {w}"
        if filled_row is None
        else f"the window filled from row {filled_row.index} ({filled_row.ts_utc})"
    )
    return Criterion("S6", True, evidence, ("P-2",))


def s2_outcome_lines(
    valid: dict[str, Sent],
    lines: dict[str, list[dict[str, Any]]],
    classification: Classification,
    named: list[str],
) -> Criterion:
    """S2: a line for every valid identity; an `accepted` line (E-1) or a
    named N1 case for every identity of the restart class and of the
    ambiguous band (P-3)."""
    without_line = [m for m in valid if not lines.get(m)]
    not_recovered = [
        m
        for m in classification.restart_or_ambiguous
        if not _has(lines.get(m, []), "accepted") and m not in named
    ]
    failed_only = [m for m in not_recovered if _only(lines.get(m, []), "failed")]
    evidence = {
        "valid_identities": len(valid),
        "without_outcome_line": len(without_line),
        "without_outcome_line_ids": _sorted_ids(without_line, valid),
        "restart_classes_evaluated": len(classification.restart_or_ambiguous),
        "restart_class": len(classification.restart_class),
        "ambiguous": len(classification.ambiguous),
        "not_accepted_and_not_named": len(not_recovered),
        "not_accepted_and_not_named_ids": [
            {**_identity(valid[m]), "outcomes": _outcomes_of(lines.get(m, []))}
            for m in _sorted_ids(not_recovered, valid)
        ],
        "failed_only": len(failed_only),
        "named_n1_cases": len(named),
    }
    holds = not without_line and not not_recovered
    reason = None
    if not holds:
        parts = []
        if without_line:
            parts.append(f"{len(without_line)} valid identity(ies) without an outcome line")
        if not_recovered:
            parts.append(
                f"{len(not_recovered)} restart-class identity(ies) neither accepted nor a named N1 case"
            )
        reason = "; ".join(parts)
    return Criterion("S2", holds, evidence, ("P-3", "E-1"), reason)


def s3_r2_double_accepted(
    lines: dict[str, list[dict[str, Any]]], valid: dict[str, Sent]
) -> tuple[Criterion, Criterion]:
    """S3 and R2 over EVERY `accepted` line of the post-drain copy, late
    ones included (per_run.csv's double_accepted counts in-window repeats
    only)."""
    doubled = [
        m for m, identity_lines in lines.items()
        if sum(1 for line in identity_lines if line.get("outcome") == "accepted") >= 2
    ]
    doubled = _sorted_ids(doubled, valid)
    evidence = {
        "double_accepted": len(doubled),
        "identities": [
            {
                **(_identity(valid[m]) if m in valid else {"message_id": m}),
                "accepted_lines": sum(1 for line in lines[m] if line.get("outcome") == "accepted"),
            }
            for m in doubled
        ],
        "note": "every accepted line of the post-drain copy counts, late ones included",
    }
    reason = None if not doubled else f"{len(doubled)} identity(ies) with two or more accepted lines"
    return (
        Criterion("S3", not doubled, dict(evidence), (), reason),
        Criterion("R2", bool(doubled), dict(evidence), (), reason),
    )


# ---------------------------------------------------------------------------
# The twin's evidence: surplus per device, N1 cases, delta with tolerance
# ---------------------------------------------------------------------------


@dataclass
class Surplus:
    """Per device: the snapshots' accepted_count difference against the
    device's accepted lines of the post-drain copy (every one counts, as
    itest_reconcile's delta counts them)."""

    device_uuid: str
    device_type: str | None
    exists_before: bool | None
    exists_after: bool | None
    before_accepted_count: int | None
    after_accepted_count: int | None
    delta: int | None
    accepted_lines: int
    surplus: int | None
    before_last_run_id: str | None
    before_last_seq: int | None
    after_last_run_id: str | None
    after_last_seq: int | None
    max_seq_accepted: int | None
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "device_uuid": self.device_uuid,
            "device_type": self.device_type,
            "accepted_count_before": self.before_accepted_count,
            "accepted_count_after": self.after_accepted_count,
            "delta": self.delta,
            "accepted_lines": self.accepted_lines,
            "surplus": self.surplus,
            "last_run_id_before": self.before_last_run_id,
            "last_seq_before": self.before_last_seq,
            "last_run_id_after": self.after_last_run_id,
            "last_seq_after": self.after_last_seq,
            "max_seq_accepted": self.max_seq_accepted,
            "problems": self.problems,
        }


def _ingestion(entry: Any) -> dict[str, Any]:
    ingestion = entry.get("ingestion") if isinstance(entry, dict) else None
    return {key: (ingestion or {}).get(key) for key in INGESTION_KEYS}


def device_surplus(
    twins_before: dict[str, Any] | None,
    twins_after: dict[str, Any] | None,
    lines: LinesIndex,
    run_id: str,
) -> dict[str, Surplus] | None:
    """The surplus of every device named by either snapshot or by an
    accepted line; None when a snapshot is missing (nothing can be
    compared). Absence is read as `delta` reads it: a device with accepted
    lines absent from the before snapshot, and a device of the before
    snapshot absent from the after one, are problems; a device only the
    after snapshot names, without an accepted line, is not compared."""
    if twins_before is None or twins_after is None:
        return None
    accepted_by_device: dict[str, list[dict[str, Any]]] = {}
    for identity_lines in lines.by_id.values():
        for line in identity_lines:
            if line.get("outcome") == "accepted":
                device = line.get("device_uuid")
                if isinstance(device, str):
                    accepted_by_device.setdefault(device, []).append(line)
    result: dict[str, Surplus] = {}
    for device in sorted(set(twins_before) | set(twins_after) | set(accepted_by_device)):
        before, after = twins_before.get(device), twins_after.get(device)
        ib, ia = _ingestion(before), _ingestion(after)
        acc = accepted_by_device.get(device, [])
        seqs = [line["seq"] for line in acc if line.get("run_id") == run_id and _is_int(line.get("seq"))]
        problems: list[str] = []
        if before is None and acc:
            problems.append("absent from the before snapshot")
        if before is not None and after is None:
            problems.append("absent from the after snapshot")
        b_count = ib["accepted_count"] if _is_int(ib["accepted_count"]) else None
        a_count = ia["accepted_count"] if _is_int(ia["accepted_count"]) else None
        delta = surplus = None
        if before is not None and after is not None:
            # As `delta` reads it: an absent twin's null accepted_count is 0.
            delta = (a_count or 0) - (b_count or 0)
            surplus = delta - len(acc)
        result[device] = Surplus(
            device_uuid=device,
            device_type=(before or after or {}).get("device_type") if isinstance(before or after, dict) else None,
            exists_before=before.get("exists") if isinstance(before, dict) else None,
            exists_after=after.get("exists") if isinstance(after, dict) else None,
            before_accepted_count=b_count,
            after_accepted_count=a_count,
            delta=delta,
            accepted_lines=len(acc),
            surplus=surplus,
            before_last_run_id=ib["last_run_id"] if isinstance(ib["last_run_id"], str) else None,
            before_last_seq=ib["last_seq"] if _is_int(ib["last_seq"]) else None,
            after_last_run_id=ia["last_run_id"] if isinstance(ia["last_run_id"], str) else None,
            after_last_seq=ia["last_seq"] if _is_int(ia["last_seq"]) else None,
            max_seq_accepted=max(seqs) if seqs else None,
            problems=problems,
        )
    return result


def _json_after_prefix(line: str) -> dict[str, Any] | None:
    """The JSON object of a log line, with any compose (`name | `) or
    docker (`--timestamps`) prefix before it stripped (E-6)."""
    start = line.find("{")
    if start < 0:
        return None
    try:
        obj = json.loads(line[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _device_of_topic(topic: Any) -> str | None:
    parts = topic.split("/") if isinstance(topic, str) else []
    return parts[2] if len(parts) == 4 and parts[0] == "c2dt" and parts[3] == "telemetry" else None


def a5_occurrences(log_lines: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The A5 occurrences of the controller log (the connection-end message
    at ERROR, with the delivery in progress), in file order, and the notes:
    the subscription-granted instants (guest clock, reported only) and the
    lines that were not JSON."""
    occurrences: list[dict[str, Any]] = []
    subscribed: list[str] = []
    non_json = 0
    for number, line in enumerate(log_lines, 1):
        if not line.strip():
            continue
        obj = _json_after_prefix(line)
        if obj is None:
            non_json += 1
            continue
        message = obj.get("message")
        if message == SUBSCRIPTION_GRANTED_MESSAGE:
            subscribed.append(str(obj.get("ts")))
        if message != A5_MESSAGE or obj.get("level") != "ERROR":
            continue
        context = obj.get("context") if isinstance(obj.get("context"), dict) else {}
        identity = context.get("identity") if isinstance(context.get("identity"), dict) else {}
        occurrences.append(
            {
                "line": number,
                "ts": obj.get("ts"),
                "cause": context.get("cause"),
                "connection": context.get("connection"),
                "occurrence": context.get("occurrence"),
                "identity": {
                    key: identity.get(key)
                    for key in ("topic", "mid", "qos", "dup", "connection", "received_monotonic_ns")
                },
                "device_uuid": _device_of_topic(identity.get("topic")),
            }
        )
    return occurrences, {"subscription_granted_ts": subscribed, "non_json_lines": non_json}


@dataclass
class N1Naming:
    """The duplicate-only candidates sorted three ways: ``named`` (an N1
    case with its source and the twin's evidence), ``r3`` (the twin shows
    the identity was not applied, or no source can be established) and
    ``cannot_show`` (no twin evidence exists for the device, E-7: neither
    named nor R3)."""

    named: list[dict[str, Any]]
    r3: list[dict[str, Any]]
    r4_unexplained: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    notes: list[str]
    cannot_show: list[dict[str, Any]] = field(default_factory=list)

    @property
    def named_ids(self) -> list[str]:
        return [case["message_id"] for case in self.named]

    def named_on(self, device: str) -> list[dict[str, Any]]:
        return [case for case in self.named if case["device_uuid"] == device]


def name_n1_cases(
    valid: dict[str, Sent],
    lines: dict[str, list[dict[str, Any]]],
    surplus: dict[str, Surplus] | None,
    occurrences: list[dict[str, Any]],
    classification: Classification,
    restart: dict[str, Any],
    twins_problem: str | None = None,
) -> N1Naming:
    """The N1 cases of S4, named only with a source and the twin's evidence
    (P-4, E-4); the duplicate-only identities that are not named are R3,
    and a device surplus beyond its named cases is R4. A candidate on a
    device without twin evidence (``surplus`` None because a snapshot is
    absent, not verified or unreadable - ``twins_problem`` says which - or
    a device neither snapshot names) is neither named nor R3: nothing shows
    whether it was applied (E-7)."""
    restart = restart if isinstance(restart, dict) else {}
    restart_ok = restart.get("executed") is True and restart.get("returncode") == 0
    restart_class = set(classification.restart_class)
    before_kill = set(classification.published_before_kill)
    candidates: list[dict[str, Any]] = []
    for message_id in _sorted_ids(valid, valid):
        identity_lines = lines.get(message_id, [])
        if not _has(identity_lines, "duplicate") or _has(identity_lines, "accepted"):
            continue
        sent = valid[message_id]
        duplicates = [_received(line) for line in identity_lines if line.get("outcome") == "duplicate"]
        known = [r for r in duplicates if r is not None]
        candidates.append(
            {
                **_identity(sent),
                "outcomes": _outcomes_of(identity_lines),
                "first_duplicate_received_monotonic_ns": min(known) if known else None,
                "in_restart_class": message_id in restart_class,
                "published_before_kill": message_id in before_kill,
            }
        )
    by_device: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_device.setdefault(candidate["device_uuid"] or "", []).append(candidate)

    named: list[dict[str, Any]] = []
    r3: list[dict[str, Any]] = []
    r4: list[dict[str, Any]] = []
    cannot: list[dict[str, Any]] = []
    notes: list[str] = []
    kill_claimants: list[tuple[dict[str, Any], Surplus]] = []
    used_occurrences: set[int] = set()

    def _reject(candidate: dict[str, Any], why: str) -> None:
        r3.append({**candidate, "why_not_named": why})

    for device in sorted(by_device):
        device_candidates = by_device[device]
        facts = surplus.get(device) if surplus is not None else None
        if facts is None or facts.surplus is None:
            if surplus is None:
                why = "no twin evidence: " + (twins_problem or "a twin snapshot is missing")
            elif facts is None:
                why = "no twin evidence for the device: neither snapshot names it"
            else:
                why = "no twin evidence for the device: " + "; ".join(facts.problems)
            for candidate in device_candidates:
                cannot.append({**candidate, "why_not_shown": why})
            continue
        if facts.surplus <= 0:
            for candidate in device_candidates:
                _reject(
                    candidate,
                    f"the twin shows no surplus on the device (surplus {facts.surplus}): "
                    "without the surplus the identity was not applied",
                )
            continue
        if len(device_candidates) > facts.surplus:
            for candidate in device_candidates:
                _reject(
                    candidate,
                    f"{len(device_candidates)} duplicate-only identities on the device against a "
                    f"surplus of {facts.surplus}: they cannot be told apart, so none is named",
                )
            continue
        for candidate in device_candidates:
            redelivered = candidate["first_duplicate_received_monotonic_ns"]
            occurrence = next(
                (
                    occ
                    for occ in occurrences
                    if occ["line"] not in used_occurrences
                    and occ["device_uuid"] == device
                    and _is_int(occ["identity"].get("received_monotonic_ns"))
                    and redelivered is not None
                    and occ["identity"]["received_monotonic_ns"] < redelivered
                ),
                None,
            )
            if occurrence is not None:
                if facts.after_last_seq is None or candidate["seq"] is None or facts.after_last_seq < candidate["seq"]:
                    _reject(
                        candidate,
                        f"the after snapshot's last_seq {facts.after_last_seq} is below the identity's seq {candidate['seq']}",
                    )
                    continue
                used_occurrences.add(occurrence["line"])
                named.append(
                    {
                        **candidate,
                        "source": "a3-connection-end",
                        "source_evidence": {
                            "controller_log_line": occurrence["line"],
                            "ts": occurrence["ts"],
                            "cause": occurrence["cause"],
                            "connection": occurrence["connection"],
                            "occurrence": occurrence["occurrence"],
                            "identity": occurrence["identity"],
                            "inference": IDENTIFICATION_RULES["P-4"],
                        },
                        "twin_evidence": _twin_evidence(facts),
                    }
                )
            elif candidate["in_restart_class"] and candidate["published_before_kill"] and restart_ok:
                kill_claimants.append((candidate, facts))
            else:
                why = []
                if not candidate["in_restart_class"]:
                    why.append("not in the restart class on the controller clock")
                if not candidate["published_before_kill"]:
                    why.append("not published before the kill on the host clock")
                if not restart_ok:
                    why.append("the manifest's restart did not execute with exit 0")
                _reject(
                    candidate,
                    "no A5 occurrence names its device before its redelivery and the kill cannot "
                    "be its source: " + "; ".join(why),
                )
    if len(kill_claimants) == 1:
        candidate, facts = kill_claimants[0]
        if facts.after_last_seq is None or candidate["seq"] is None or facts.after_last_seq < candidate["seq"]:
            _reject(
                candidate,
                f"the after snapshot's last_seq {facts.after_last_seq} is below the identity's seq {candidate['seq']}",
            )
        else:
            named.append(
                {
                    **candidate,
                    "source": "kill",
                    "source_evidence": {
                        "restart_started_utc": restart.get("started_utc"),
                        "restart_finished_utc": restart.get("finished_utc"),
                        "restart_returncode": restart.get("returncode"),
                        "restart_stderr_tail": restart.get("stderr_tail"),
                        "inference": IDENTIFICATION_RULES["P-4"],
                    },
                    "twin_evidence": _twin_evidence(facts),
                }
            )
    elif len(kill_claimants) > 1:
        notes.append(
            f"{len(kill_claimants)} duplicate-only identities claim the kill as their source; at "
            "most one N1 case per death (N1), so none is named"
        )
        for candidate, _facts in kill_claimants:
            _reject(candidate, "more than one identity claims the one death: at most one N1 case per death")
    for device in sorted(surplus or {}):
        facts = surplus[device]
        if facts.surplus is not None and facts.surplus > 0:
            named_here = len(named_on(named, device))
            if facts.surplus > named_here:
                r4.append(
                    {
                        "device_uuid": device,
                        "surplus": facts.surplus,
                        "named_n1_cases": named_here,
                        "unexplained": facts.surplus - named_here,
                    }
                )
    named.sort(key=_candidate_order)
    r3.sort(key=_candidate_order)
    cannot.sort(key=_candidate_order)
    return N1Naming(named, r3, r4, candidates, notes, cannot)


def _candidate_order(candidate: dict[str, Any]) -> tuple[str, int, str]:
    """Device, seq, message_id: the document's stable order of candidates."""
    seq = candidate["seq"]
    return (candidate["device_uuid"] or "", seq if seq is not None else -1, candidate["message_id"])


def named_on(named: list[dict[str, Any]], device: str) -> list[dict[str, Any]]:
    return [case for case in named if case["device_uuid"] == device]


def _twin_evidence(facts: Surplus) -> dict[str, Any]:
    return {
        "accepted_count_before": facts.before_accepted_count,
        "accepted_count_after": facts.after_accepted_count,
        "accepted_lines": facts.accepted_lines,
        "surplus": facts.surplus,
        "last_seq": facts.after_last_seq,
        "last_run_id": facts.after_last_run_id,
    }


def s4_r3_duplicates(naming: N1Naming) -> tuple[Criterion, Criterion]:
    """S4 holds when every duplicate-lined identity has an accepted line or
    is a named N1 case; R3 is observed for every one that is neither. A
    candidate without twin evidence (E-7) can be shown neither way: with no
    R3 observed elsewhere, S4 and R3 are then null."""
    evidence = {
        "duplicate_only_identities": len(naming.candidates),
        "named_n1_cases": len(naming.named),
        "not_named": len(naming.r3),
        "not_named_identities": naming.r3,
        "cannot_show": len(naming.cannot_show),
        "cannot_show_identities": naming.cannot_show,
        "notes": naming.notes,
    }
    rules = ("P-4", "E-4", "E-7")
    if naming.r3:
        reason = f"{len(naming.r3)} identity(ies) with only duplicate lines and no named N1 case"
        return (
            Criterion("S4", False, dict(evidence), rules, reason),
            Criterion("R3", True, dict(evidence), rules, reason),
        )
    if naming.cannot_show:
        reason = (
            f"{len(naming.cannot_show)} identity(ies) with only duplicate lines on a device "
            "without twin evidence: " + "; ".join(sorted({c["why_not_shown"] for c in naming.cannot_show}))
        )
        return (
            Criterion("S4", None, dict(evidence), rules, reason),
            Criterion("R3", None, dict(evidence), rules, reason),
        )
    return (
        Criterion("S4", True, dict(evidence), rules),
        Criterion("R3", False, dict(evidence), rules),
    )


def s5_r4_delta(
    surplus: dict[str, Surplus] | None,
    run_id: str,
    naming: N1Naming,
    cannot: str | None = None,
) -> tuple[Criterion, Criterion]:
    """S5 with its tolerance and R4: itest_reconcile's per-device rule
    (delta equals the device's accepted lines; last_run_id is this run's
    and last_seq the highest accepted seq when the run accepted on the
    device; a device with accepted lines absent from the before snapshot is
    a mismatch), tolerating exactly one per named N1 case on the device
    (E-2), plus the last_seq regression rule (P-5). Without a surplus
    (``cannot`` says why: a snapshot or the post-drain copy absent, not
    verified or unreadable) both are null (E-7)."""
    if surplus is None:
        why = cannot or "a twin snapshot is missing"
        evidence = {"devices": [], "note": f"no delta can be computed: {why}"}
        return (
            Criterion("S5", None, dict(evidence), ("E-2", "E-7"), why),
            Criterion("R4", None, dict(evidence), ("P-5", "E-2", "E-7"), why),
        )
    devices: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    for device in sorted(surplus):
        facts = surplus[device]
        cases = named_on(naming.named, device)
        named_seqs = [case["seq"] for case in cases if case["seq"] is not None]
        expected_last_seq = None
        seqs = [s for s in (facts.max_seq_accepted, *named_seqs) if s is not None]
        if seqs:
            expected_last_seq = max(seqs)
        problems = list(facts.problems)
        if facts.delta is not None:
            if facts.delta != facts.accepted_lines + len(cases):
                problems.append(
                    f"accepted_count advanced by {facts.delta} against {facts.accepted_lines} "
                    f"accepted line(s) and {len(cases)} named N1 case(s)"
                )
            if expected_last_seq is not None and (
                facts.after_last_run_id != run_id or facts.after_last_seq != expected_last_seq
            ):
                problems.append(
                    f"last_run_id {facts.after_last_run_id!r} last_seq {facts.after_last_seq} "
                    f"against this run's highest applied seq {expected_last_seq}"
                )
        regressed = None
        if facts.after_last_seq is not None:
            if (
                facts.after_last_run_id == run_id
                and expected_last_seq is not None
                and facts.after_last_seq < expected_last_seq
            ):
                regressed = f"last_seq {facts.after_last_seq} is below the run's highest applied seq {expected_last_seq}"
            elif (
                facts.after_last_run_id is not None
                and facts.after_last_run_id == facts.before_last_run_id
                and facts.before_last_seq is not None
                and facts.after_last_seq < facts.before_last_seq
            ):
                regressed = (
                    f"last_seq {facts.after_last_seq} is below the before snapshot's "
                    f"{facts.before_last_seq} under the same run_id {facts.after_last_run_id!r}"
                )
        row = {
            **facts.as_dict(),
            "named_n1_cases": len(cases),
            "expected_last_seq": expected_last_seq,
            "problems": problems,
            "regressed": regressed,
            "compared": facts.delta is not None,
            "ok": not problems and regressed is None,
        }
        if facts.delta is None and not problems:
            row["note"] = (
                "not compared: named by the after snapshot only and without an "
                "accepted line, which the runbook's `delta` does not compare"
            )
        devices.append(row)
        if problems:
            mismatches.append({"device_uuid": device, "problems": problems})
        if regressed is not None:
            regressions.append({"device_uuid": device, "regressed": regressed})
    evidence = {
        "devices": devices,
        "mismatches": mismatches,
        "last_seq_regressions": regressions,
        "surplus_unexplained": naming.r4_unexplained,
        "note": (
            "the /metrics counters of `delta` are not compared: they restart from zero "
            "with the controller process"
        ),
    }
    reason = None
    if mismatches or regressions:
        parts = []
        if mismatches:
            parts.append(f"{len(mismatches)} device(s) with a delta mismatch beyond the named cases")
        if regressions:
            parts.append(f"{len(regressions)} device(s) whose last_seq regressed")
        reason = "; ".join(parts)
    observed = bool(mismatches or regressions)
    return (
        Criterion("S5", not observed, dict(evidence), ("E-2",), reason),
        Criterion("R4", observed, dict(evidence), ("P-5", "E-2"), reason),
    )


def r1_missing_after_drain(
    valid: dict[str, Sent], lines: dict[str, list[dict[str, Any]]], drain_outcome: str | None
) -> Criterion:
    """R1 only after a completed drain (``drain.outcome == 'quiet'``): a
    drain that gave up leaves the missing lines to the inconclusive rule."""
    missing = _sorted_ids([m for m in valid if not lines.get(m)], valid)
    evidence = {
        "drain_outcome": drain_outcome,
        "without_outcome_line": len(missing),
        "without_outcome_line_ids": missing,
    }
    if drain_outcome != "quiet":
        return Criterion(
            "R1", None, evidence, ("P-7",),
            f"no completed drain (drain outcome {drain_outcome!r}): R1 cannot be observed",
        )
    reason = None if not missing else f"{len(missing)} published valid identity(ies) without an outcome line after a completed drain"
    return Criterion("R1", bool(missing), evidence, ("P-7",), reason)


def failed_only_restart_class(
    valid: dict[str, Sent], lines: dict[str, list[dict[str, Any]]], classification: Classification
) -> list[dict[str, Any]]:
    """The restart-class (and ambiguous, P-3) identities whose only lines
    are `failed`, each with the error every line records."""
    result = []
    for message_id in classification.restart_or_ambiguous:
        identity_lines = lines.get(message_id, [])
        if _only(identity_lines, "failed"):
            result.append(
                {
                    **_identity(valid[message_id]),
                    "class": "restart_class" if message_id in classification.restart_class else "ambiguous",
                    "errors": [line.get("error") for line in identity_lines],
                }
            )
    return result


# ---------------------------------------------------------------------------
# Evidence status, inconclusive reasons, the decision
# ---------------------------------------------------------------------------


@dataclass
class EvidenceStatus:
    """Whether the proof's evidence is complete, every absence named;
    ``unusable`` maps each file that cannot serve the criteria (the
    post-drain copy, the twin snapshots) to why (E-7)."""

    complete: bool
    present: dict[str, bool]
    missing: list[str]
    fetch_failures: list[str]
    drain: dict[str, Any]
    unusable: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "present": self.present,
            "missing": self.missing,
            "fetch_failures": self.fetch_failures,
            "drain": self.drain,
            "cannot_serve_the_criteria": dict(sorted(self.unusable.items())),
        }


def w_of(manifest: dict[str, Any]) -> int | None:
    """W = the broker's max_inflight_messages of the embedded configuration
    identity, or None."""
    identity = manifest.get("configuration_identity")
    values = identity.get("broker_conf_values") if isinstance(identity, dict) else None
    w = values.get("max_inflight_messages") if isinstance(values, dict) else None
    return w if _is_int(w) and w > 0 else None


def evidence_status(
    manifest: dict[str, Any],
    files_present: set[str],
    integrity: str,
    pre_kill_rows: int,
    config_problems: list[str],
    read_problems: list[str] | None = None,
) -> EvidenceStatus:
    """Whether the proof's evidence is complete, every absence named: the
    manifest's item-18 records (both snapshots verified, the drain verified
    and quiet or gave-up, the post-drain copy fetched and verified, the
    three SUT logs fetched with their files), the configuration identity
    with W, a readable pre-kill reading and the seal. ``read_problems`` are
    the loader's (a file present but unreadable): each is a failed fetch
    of that file, since nothing of it can be read."""
    read_problems = list(read_problems or [])
    missing: list[str] = []
    failures: list[str] = []
    unusable: dict[str, str] = {}
    logs = "logs/" + SUT_LOG_SUBDIR

    def _read_problem(rel: str) -> str | None:
        return next((p for p in read_problems if p.startswith(rel)), None)

    def _cannot_serve(rel: str, why: str) -> None:
        unusable.setdefault(rel, why)
    watched = [
        "sent_events.jsonl",
        "events.jsonl",
        POST_DRAIN_EVENTS_FILENAME,
        *TWIN_SNAPSHOT_FILES.values(),
        "controller_metrics.csv",
        CONFIG_IDENTITY_FILENAME,
        *(f"{logs}/{name}" for name in SUT_LOG_FILES.values()),
        SUMS_FILENAME,
    ]
    present = {rel: rel in files_present for rel in watched}

    def _record_outcome(record: dict[str, Any]) -> str:
        if record.get("error"):
            return f"error {record.get('error')}"
        return f"exit {record.get('returncode')}"

    snapshots = manifest.get("twin_snapshots")
    by_file = {
        r.get("file"): r for r in (snapshots if isinstance(snapshots, list) else []) if isinstance(r, dict)
    }
    for hook, file in TWIN_SNAPSHOT_FILES.items():
        record = by_file.get(file)
        if record is None:
            missing.append(f"{file}: no twin snapshot record ({RESTART_EVIDENCE_FLAGS[hook]})")
            _cannot_serve(file, missing[-1])
        elif record.get("verified") is not True:
            failures.append(
                f"{file}: the twin snapshot is not verified ({_record_outcome(record)}): "
                + ("; ".join(record.get("problems") or []) or "no file or a refused file")
            )
            _cannot_serve(file, failures[-1])
        elif not present[file]:
            missing.append(f"{file}: recorded as verified but absent from the run directory")
            _cannot_serve(file, missing[-1])
        elif _read_problem(file) is not None:
            failures.append(_read_problem(file))
            _cannot_serve(file, failures[-1])

    drain = manifest.get("drain")
    drain_facts = {
        "source": drain.get("source") if isinstance(drain, dict) else None,
        "outcome": drain.get("outcome") if isinstance(drain, dict) else None,
        "verified": drain.get("verified") if isinstance(drain, dict) else None,
    }
    if not isinstance(drain, dict):
        missing.append(f"drain: no record ({RESTART_EVIDENCE_FLAGS['drain']})")
    elif drain.get("verified") is not True or drain.get("outcome") not in ("quiet", "gave-up"):
        failures.append(
            f"drain: outcome {drain.get('outcome')!r} ({_record_outcome(drain)}): neither the "
            "helper's quiet line nor its give-up line, an instrument failure"
        )

    post = manifest.get("events_post_drain_fetch")
    post_file = POST_DRAIN_EVENTS_FILENAME
    if not isinstance(post, dict):
        missing.append(f"{post_file}: no post-drain fetch record (--post-drain-fetch-cmd)")
        _cannot_serve(post_file, missing[-1])
    elif post.get("source") != "ingested" and post.get("ok") is not True:
        failures.append(
            f"{post_file}: the post-drain fetch failed after "
            f"{len(post.get('attempts') or [])} attempt(s)"
        )
        _cannot_serve(post_file, failures[-1])
    elif post.get("verified") is not True:
        failures.append(
            f"{post_file}: fetched but not the post-drain copy of this run: "
            + "; ".join(post.get("problems") or [])
        )
        _cannot_serve(post_file, failures[-1])
    elif not present[post_file]:
        missing.append(f"{post_file}: recorded as verified but absent from the run directory")
        _cannot_serve(post_file, missing[-1])
    elif _read_problem(post_file) is not None:
        failures.append(_read_problem(post_file))
        _cannot_serve(post_file, failures[-1])

    fetches = manifest.get("sut_log_fetches")
    by_hook = {
        r.get("hook"): r for r in (fetches if isinstance(fetches, list) else []) if isinstance(r, dict)
    }
    for hook, name in SUT_LOG_FILES.items():
        rel = f"{logs}/{name}"
        record = by_hook.get(hook)
        if record is None:
            missing.append(f"{rel}: no fetch record ({SUT_LOG_FETCH_FLAGS[hook]})")
        elif record.get("returncode") != 0 or not record.get("dest_exists"):
            failures.append(
                f"{rel}: the fetch {SUT_LOG_FETCH_FLAGS[hook]} {_record_outcome(record)} and "
                + ("wrote its file" if record.get("dest_exists") else "wrote no file")
            )
        elif not present[rel]:
            missing.append(f"{rel}: recorded as fetched but absent from the run directory")
        elif _read_problem(rel) is not None:
            failures.append(_read_problem(rel))

    identity = manifest.get("configuration_identity")
    if not isinstance(identity, dict):
        missing.append("configuration_identity: not embedded in the manifest")
    elif config_problems:
        failures.append("configuration_identity: " + "; ".join(config_problems))
    elif w_of(manifest) is None:
        failures.append(
            "configuration_identity: broker_conf_values.max_inflight_messages (W) is not a positive integer"
        )

    if not present["sent_events.jsonl"]:
        missing.append("sent_events.jsonl: absent")
    if not present["controller_metrics.csv"]:
        missing.append("controller_metrics.csv: absent")
    elif _read_problem("controller_metrics.csv") is not None:
        failures.append(_read_problem("controller_metrics.csv"))
    elif pre_kill_rows < 1:
        failures.append(
            "controller_metrics.csv: no readable reading of the pre-kill process (a row "
            "with started_at is needed for S1)"
        )
    if integrity == INTEGRITY_UNSEALED:
        failures.append(f"{SUMS_FILENAME}: absent, the run directory was never sealed")
    elif integrity != INTEGRITY_OK:
        failures.append(f"{SUMS_FILENAME}: the seal does not verify")
    named = set(missing) | set(failures)
    for problem in read_problems:
        # A read problem of a file no record above covers (events.jsonl,
        # configuration_identity.json, the CSV header) is still named.
        if problem not in named:
            failures.append(problem)
    return EvidenceStatus(
        complete=not missing and not failures,
        present=present,
        missing=missing,
        fetch_failures=failures,
        drain=drain_facts,
        unusable=unusable,
    )


def stop_rules_of(session: dict[str, Any] | None) -> dict[str, Any]:
    """The stop rules as the session facts record them: which were
    reached, which are unreadable (P-6)."""
    if session is None:
        return {"known": False, "reached": [], "unreadable": [], "rules": None}
    rules = session.get("stop_rules")
    if not isinstance(rules, list):
        return {"known": False, "reached": [], "unreadable": [], "rules": rules}
    reached = [r for r in rules if isinstance(r, dict) and r.get("reached") is True]
    unreadable = [r for r in rules if not isinstance(r, dict) or not isinstance(r.get("reached"), bool)]
    return {"known": not unreadable, "reached": reached, "unreadable": unreadable, "rules": rules}


def inconclusive_reasons(
    evidence: EvidenceStatus,
    criteria: dict[str, Criterion],
    drain_outcome: str | None,
    session: dict[str, Any] | None,
    failed_only: list[dict[str, Any]],
    r_any: bool,
) -> list[str]:
    """The ADR's five conditions, in its order, plus the evaluator's own
    (P-2, P-6, E-3, E-7), each stated with what was read. A criterion of
    S2 to S5 that is null is always named here (E-7), so a run that is
    inconclusive for that cause never goes without a stated reason."""
    s1, s2, s6 = criteria["S1"], criteria["S2"], criteria["S6"]
    reasons: list[str] = []
    if s1.holds is False:
        reasons.append(f"the kill found nothing in flight (S1 fails): {s1.reason}")
    elif s1.holds is None:
        reasons.append(f"S1 cannot be read: {s1.reason}")
    if drain_outcome == "gave-up":
        reasons.append("a `drained` call reaches its limit (drain outcome 'gave-up')")
    if not evidence.complete:
        reasons.append(
            "any fetch listed above fails: "
            + "; ".join(evidence.missing + evidence.fetch_failures)
        )
    stop = stop_rules_of(session)
    if session is None:
        reasons.append(
            "whether a stop rule of the ceiling was reached is unknown: no session facts "
            "(proof_session.json) were given (P-6)"
        )
    elif not stop["known"]:
        reasons.append(
            "whether a stop rule of the ceiling was reached is unknown: the session facts "
            "carry no readable stop_rules (P-6)"
        )
    for rule in stop["reached"]:
        reasons.append(
            "a stop rule of the ceiling is reached: "
            + str(rule.get("rule") or rule.get("name") or "unnamed rule")
            + (f" (limit {rule.get('limit_s')} s)" if rule.get("limit_s") is not None else "")
        )
    if failed_only and not r_any:
        reasons.append(
            "when none of R1 to R4 holds, a restart-class identity ends with only `failed` "
            "lines: "
            + "; ".join(
                f"{item['message_id']} (device {item['device_uuid']}, seq {item['seq']}, {item['class']}): "
                + ", ".join(repr(error) for error in item["errors"])
                for item in failed_only
            )
        )
    if s6.holds is None:
        reasons.append(f"S6 cannot be stated (P-2): {s6.reason}")
    if s2.holds is False and not r_any:
        failed_ids = {item["message_id"] for item in failed_only}
        outstanding = [
            item for item in s2.evidence["not_accepted_and_not_named_ids"]
            if item["message_id"] not in failed_ids
        ]
        if outstanding:
            reasons.append(
                "does not support (E-3): S2 does not hold while no refutation is observed: "
                + s2.reason
            )
    unshown: dict[str, list[str]] = {}
    for rule_id in ("S2", "S3", "S4", "S5"):
        criterion = criteria[rule_id]
        if criterion.holds is None:
            unshown.setdefault(criterion.reason or "no reason recorded", []).append(rule_id)
    for why, rule_ids in unshown.items():
        reasons.append(f"{', '.join(rule_ids)} cannot be shown (E-7): {why}")
    return reasons


def decide(
    criteria: dict[str, Criterion], refutations: dict[str, Criterion], reasons: list[str]
) -> str:
    """P-7: an observed refutation stands; else any inconclusive reason;
    else supports only when all six hold. The last line is reached only by
    a criterion that neither holds nor gave a reason; inconclusive_reasons
    names every null one, so it is a safety net, not a path."""
    if any(c.holds is True for c in refutations.values()):
        return RESULT_REFUTES
    if reasons:
        return RESULT_INCONCLUSIVE
    if all(criteria[rule_id].holds is True for rule_id in SUPPORT_RULE_IDS):
        return RESULT_SUPPORTS
    return RESULT_INCONCLUSIVE


# ---------------------------------------------------------------------------
# The verdict document
# ---------------------------------------------------------------------------


def _class_report(ids: list[str], lines: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    counts = {outcome: 0 for outcome in OUTCOME_CLASSES}
    total_lines = 0
    for message_id in ids:
        identity_lines = lines.get(message_id, [])
        counts[_ending(identity_lines)] += 1
        total_lines += len(identity_lines)
    return {"identities": len(ids), "lines": total_lines, **counts}


def _copy_report(index: LinesIndex | None) -> dict[str, Any] | None:
    if index is None:
        return None
    return {
        "lines": index.total,
        "identities": len(index.by_id),
        "by_outcome": index.outcomes(),
        "other_run_id": index.other_run_id,
        "unattributed": index.unattributed,
    }


def evaluate(artefacts: RunArtefacts, session: dict[str, Any] | None) -> dict[str, Any]:
    """The verdict document of one proof session (no timestamp: the same
    evidence gives the same bytes)."""
    manifest = artefacts.manifest
    run_id = str(manifest.get("run_id") or artefacts.run_dir.name)
    restart = manifest.get("restart") if isinstance(manifest.get("restart"), dict) else {}
    drain = manifest.get("drain") if isinstance(manifest.get("drain"), dict) else {}
    drain_outcome = drain.get("outcome") if drain.get("outcome") in DRAIN_OUTCOMES else None
    identity = manifest.get("configuration_identity")
    config_problems = configuration_identity_problems(identity) if identity is not None else []
    w = w_of(manifest)

    rows, row_notes = read_metrics_rows(artefacts.metrics_rows or [])
    split = split_by_process(rows)
    evidence = evidence_status(
        manifest,
        artefacts.files_present,
        artefacts.integrity,
        len(split.pre_kill),
        config_problems,
        artefacts.problems,
    )
    # E-7: the post-drain copy serves the criteria only when it was fetched,
    # verified as this run's and read; the twins only when both snapshots
    # were. Otherwise what depends on them is null, never a refutation.
    post_problem = evidence.unusable.get(POST_DRAIN_EVENTS_FILENAME)
    if post_problem is None and artefacts.events_post_drain is None:
        post_problem = f"{POST_DRAIN_EVENTS_FILENAME}: not read"
    twins_problem = next(
        (evidence.unusable[f] for f in TWIN_SNAPSHOT_FILES.values() if f in evidence.unusable), None
    )
    if twins_problem is None and (artefacts.twins_before is None or artefacts.twins_after is None):
        twins_problem = "a twin snapshot was not read"
    post_copy_usable = post_problem is None

    sent = valid_identities(artefacts.sent_events, run_id)
    post = lines_by_identity(artefacts.events_post_drain or [], run_id)
    timed = lines_by_identity(artefacts.events_timed, run_id) if artefacts.events_timed is not None else None
    band = kill_band(split.pre_kill, split.post_kill)
    occurrences, log_notes = a5_occurrences(artefacts.controller_log or [])
    classification = classify_identities(
        sent.valid, post.by_id, band, restart, manifest, split.post_kill, log_notes["subscription_granted_ts"]
    )
    if not post_copy_usable:
        classification.notes.append(
            "the post-drain copy cannot serve the criteria, so no identity has a line "
            "here: the classes are a report figure only"
        )
    surplus = (
        device_surplus(artefacts.twins_before, artefacts.twins_after, post, run_id)
        if post_copy_usable and twins_problem is None
        else None
    )
    if post_problem is not None:
        cannot: str | None = f"the post-drain copy cannot serve the criteria: {post_problem}"
    elif twins_problem is not None:
        cannot = f"the twin evidence cannot serve the criteria: {twins_problem}"
    else:
        cannot = None
    naming = name_n1_cases(
        sent.valid, post.by_id, surplus, occurrences, classification, restart, twins_problem
    )

    s1 = s1_kill_found_work(split.pre_kill, restart, manifest.get("controller_marker"))
    s6 = s6_window(rows, w)
    if post_copy_usable:
        s2 = s2_outcome_lines(sent.valid, post.by_id, classification, naming.named_ids)
        s3, r2 = s3_r2_double_accepted(post.by_id, sent.valid)
        s4, r3 = s4_r3_duplicates(naming)
        r1 = r1_missing_after_drain(sent.valid, post.by_id, drain_outcome)
    else:
        why = str(cannot)
        unread = {"post_drain_copy": post_problem, "note": "no line of the post-drain copy was read"}
        s2 = Criterion("S2", None, dict(unread), ("P-3", "E-1", "E-7"), why)
        s3 = Criterion("S3", None, dict(unread), ("E-7",), why)
        r2 = Criterion("R2", None, dict(unread), ("E-7",), why)
        s4 = Criterion("S4", None, dict(unread), ("P-4", "E-4", "E-7"), why)
        r3 = Criterion("R3", None, dict(unread), ("P-4", "E-4", "E-7"), why)
        r1 = Criterion("R1", None, {**unread, "drain_outcome": drain_outcome}, ("P-7", "E-7"), why)
    s5, r4 = s5_r4_delta(surplus, run_id, naming, cannot)
    criteria = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6}
    refutations = {"R1": r1, "R2": r2, "R3": r3, "R4": r4}
    failed_only = failed_only_restart_class(sent.valid, post.by_id, classification) if post_copy_usable else []
    r_any = any(c.holds is True for c in refutations.values())
    reasons = inconclusive_reasons(evidence, criteria, drain_outcome, session, failed_only, r_any)
    result = decide(criteria, refutations, reasons)

    seed = manifest.get("seed")
    expected_devices = expected_twin_devices(seed) if _is_int(seed) else None
    devices_lined = sorted({s.device_uuid for s in sent.valid.values() if s.device_uuid})
    drain_text_outcome = (
        classify_drain_output(artefacts.drain_text, drain.get("returncode"))
        if artefacts.drain_text is not None
        else None
    )
    stop = stop_rules_of(session)
    document = {
        "proof": PROOF,
        "run_id": run_id,
        "evaluator_version": EVALUATOR_VERSION,
        "label": LABEL,
        "instrumentation": {
            "harness_validity": manifest.get("validity"),
            "harness_validity_reasons": manifest.get("validity_reasons"),
            "harness_condition_id": manifest.get("condition_id"),
            "seal": artefacts.integrity,
            "seal_problems": artefacts.integrity_problems,
            "proof_evidence": evidence.as_dict(),
            "drain_text_outcome": drain_text_outcome,
            "skipped_lines": dict(sorted(artefacts.skipped_lines.items())),
            "controller_log_non_json_lines": log_notes["non_json_lines"],
            "read_problems": artefacts.problems,
            "read_notes": artefacts.notes,
            "metrics_notes": row_notes,
            "configuration_identity_problems": config_problems,
            "note": (
                "the harness verdict belongs to the campaign rules and is kept as recorded "
                "(ADR 0011, what the proof cannot show); it does not decide the proof"
            ),
        },
        "system_outcome": {
            "result": result,
            "criteria": {rule_id: criterion.as_dict() for rule_id, criterion in {**criteria, **refutations}.items()},
            "refutations": [
                f"{rule_id}: {criterion.reason}" for rule_id, criterion in refutations.items() if criterion.holds is True
            ],
            "inconclusive_reasons": reasons,
            "failed_only_restart_class": failed_only,
            "n1_cases": naming.named,
            "window": {
                "W": w,
                "max_queue_plus_in_progress": s6.evidence.get("max_queue_plus_in_progress"),
                "filled": s6.evidence.get("filled"),
                "filled_from": s6.evidence.get("filled_from"),
            },
            "report": {
                "by_class": {
                    "restart_classes": _class_report(classification.restart_class, post.by_id),
                    "ambiguous": _class_report(classification.ambiguous, post.by_id),
                    "other_valid": _class_report(classification.pre_kill_lined, post.by_id),
                    "intended_invalid": _class_report(list(sent.intended_invalid), post.by_id),
                },
                "classification": classification.as_dict(),
                "copies": {
                    "events.jsonl": _copy_report(timed),
                    POST_DRAIN_EVENTS_FILENAME: _copy_report(post),
                },
                "sent": {
                    "valid": len(sent.valid),
                    "intended_invalid": len(sent.intended_invalid),
                    "other_run_id": sent.other_run_id,
                    "malformed": sent.malformed,
                    "repeated": sent.repeated,
                },
                "devices": {
                    "expected_from_seed": expected_devices,
                    "published_for": devices_lined,
                    "surplus": [facts.as_dict() for facts in (surplus or {}).values()],
                },
                "a5_occurrences": occurrences,
                "processes": {
                    "pre_kill_started_at": split.pre_started_at,
                    "post_kill_started_at": split.post_started_ats,
                    "pre_kill_rows": len(split.pre_kill),
                    "post_kill_rows": len(split.post_kill),
                    "unreadable_rows": len(split.unreadable),
                },
                "method": {
                    "outcome_precedence": list(OUTCOME_CLASSES),
                    "identification_rules": dict(IDENTIFICATION_RULES),
                    "criteria_copy": POST_DRAIN_EVENTS_FILENAME,
                    "criteria_copy_usable": post_copy_usable,
                    "criteria_copy_problem": post_problem,
                    "twin_evidence_problem": twins_problem,
                    "note": (
                        "the timed copy (events.jsonl) is reported beside the post-drain copy and "
                        "never enters a criterion"
                    ),
                },
            },
            "rules": {
                key: RULES[key] for key in ("restart_classes", "recovered", "support", "refutation", "inconclusive")
            },
        },
        "restoration": {
            "state": session.get("restoration") if session is not None else None,
            "note": "not computed here: the driver observes it",
        },
        "session_facts": {
            "present": session is not None,
            "stop_rules": stop["rules"],
            "stop_rules_reached": stop["reached"],
            "values": session.get("values") if session is not None else None,
            "restart_shown": session.get("restart_shown") if session is not None else None,
            "extension": session.get("extension") if session is not None else None,
        },
        "cannot_show": RULES["cannot_show"],
        "sources": dict(sorted(artefacts.sha256s.items())),
    }
    return document


def not_evaluated(artefacts: RunArtefacts, why: str, session: dict[str, Any] | None) -> dict[str, Any]:
    """The document of a run the proof did not evaluate (a seal that
    fails): the instrumentation section says why, the outcome is
    'not-evaluated' and nothing is claimed."""
    manifest = artefacts.manifest
    return {
        "proof": PROOF,
        "run_id": str(manifest.get("run_id") or artefacts.run_dir.name),
        "evaluator_version": EVALUATOR_VERSION,
        "label": LABEL,
        "instrumentation": {
            "harness_validity": manifest.get("validity"),
            "harness_validity_reasons": manifest.get("validity_reasons"),
            "seal": artefacts.integrity,
            "seal_problems": artefacts.integrity_problems,
            "not_evaluated": why,
            "note": (
                "the harness verdict belongs to the campaign rules and is kept as recorded "
                "(ADR 0011, what the proof cannot show); it does not decide the proof"
            ),
        },
        "system_outcome": {"result": RESULT_NOT_EVALUATED, "criteria": {}, "refutations": [], "inconclusive_reasons": [why]},
        "restoration": {
            "state": session.get("restoration") if session is not None else None,
            "note": "not computed here: the driver observes it",
        },
        "cannot_show": RULES["cannot_show"],
        "sources": dict(sorted(artefacts.sha256s.items())),
    }


def render(document: dict[str, Any]) -> str:
    """The document as the file and stdout carry it: sorted keys, two-space
    indent, one trailing newline; no timestamp, so the bytes repeat."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def summary_line(document: dict[str, Any]) -> str:
    outcome = document["system_outcome"]
    line = f"[proof] {document['run_id']}: {outcome['result']}"
    if outcome.get("refutations"):
        line += "; refutations: " + " | ".join(outcome["refutations"])
    if outcome.get("inconclusive_reasons"):
        line += "; inconclusive: " + " | ".join(outcome["inconclusive_reasons"])
    instrumentation = document["instrumentation"]
    line += (
        f"; harness validity {instrumentation.get('harness_validity')!r} kept as recorded; "
        f"seal {instrumentation.get('seal')}"
    )
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m egw_experiments.proof_evaluator",
        description=(
            "Apply the finite proof's rules (ADR 0011: S1-S6, R1-R4, the inconclusive "
            "rule) to one sealed run directory and write the verdict document."
        ),
    )
    parser.add_argument("--run-dir", required=True, help="the harness run directory (raw/<run_id>)")
    parser.add_argument("--out", required=True, help="where proof_verdict.json is written (write-once)")
    parser.add_argument("--session", default=None, help="the driver's proof_session.json (stop rules, restoration)")
    parser.add_argument(
        "--adr",
        default=None,
        help="the ADR to check the rule texts against before evaluating (default: none)",
    )
    args = parser.parse_args(argv)
    out = Path(args.out)
    try:
        if args.adr is not None:
            drifted = rule_texts_not_in(Path(args.adr))
            if drifted:
                raise ProofInputError(
                    "rule text(s) not found verbatim in the ADR: " + ", ".join(drifted)
                )
        artefacts = load_run_dir(Path(args.run_dir))
        session = load_session_facts(Path(args.session) if args.session else None)
        if artefacts.integrity == INTEGRITY_FAILED:
            document = not_evaluated(
                artefacts,
                f"{SUMS_FILENAME} does not verify: " + "; ".join(artefacts.integrity_problems),
                session,
            )
        else:
            document = evaluate(artefacts, session)
        text = render(document)
    except ProofInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CODES[RESULT_NOT_EVALUATED]
    except Exception as exc:  # broad on purpose: exit 1 is a result, never a crash
        # A failure of the evaluator itself must not read as a refutation
        # (exit 1) or as anything else the driver treats as a result: the
        # traceback is kept for the diagnosis and the proof is not evaluated.
        traceback.print_exc()
        print(f"error: the proof was not evaluated: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_CODES[RESULT_NOT_EVALUATED]
    sys.stdout.write(text)
    sys.stdout.flush()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except FileExistsError:
        print(f"error: refusing to overwrite {out}", file=sys.stderr)
        return EXIT_CODES[RESULT_NOT_EVALUATED]
    except OSError as exc:
        print(f"error: {out} could not be written: {exc}", file=sys.stderr)
        return EXIT_CODES[RESULT_NOT_EVALUATED]
    print(summary_line(document), file=sys.stderr)
    return EXIT_CODES[document["system_outcome"]["result"]]


if __name__ == "__main__":
    sys.exit(main())
