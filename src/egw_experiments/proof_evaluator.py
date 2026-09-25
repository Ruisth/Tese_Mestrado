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

- ``instrumentation``: the harness's own ``validity`` quoted as recorded
  and admitted for the proof in two forms only (E-12: 'valid', or the
  campaign's MAX_SAMPLE_GAP_S deviation in the one form the harness
  records it; :func:`harness_admission`, which the driver calls too), the
  seal, whether the proof's evidence is complete (both twin snapshots
  verified, a verified drain that was quiet or gave up, the harness copy of
  the events fetched, the post-drain copy fetched and verified, the three
  SUT logs fetched, the collector file, the configuration identity embedded
  with W, a readable pre-kill reading, the directory sealed and verified) -
  every absence named, so that "any fetch listed above fails" can be
  applied - and whether the run is eligible for the proof at all (E-11: the
  harness's validity admitted, the prescribed load and fault at its
  instant, the publication completed, the population record whole, the
  fault demonstrated), every failed requirement named;
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
on evidence that was read and verified (E-7): a post-drain copy, a twin
snapshot or the controller log that is absent, unverified or unreadable
leaves the criteria that depend on it null, never observed; a
duplicate-only identity whose line falls in the sampling band around the
kill, or whose publication falls inside the restart command's window, can
be shown neither way (E-8), never refuted on that ground; the twin's
figures on such an identity's device refute only when no naming of it
fits them (E-9), the namings respecting the sources the run evidences,
their capacity across the whole run and their order against each
candidate's redelivery on the controller clock (E-10); and a run that is
not the prescribed execution with its records, or whose harness validity
is not admitted, is not eligible: inconclusive, never support (E-11,
E-12).

Exit codes, as ``broker_measure.sh`` reads the broker verdict: 0 supports,
1 refutes, 3 inconclusive, 2 not evaluated (an input unreadable, a seal
that fails, a rule text that drifted from the ADR, a usage error, or a
failure of the evaluator itself - never exit 1, which is a result).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

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
from .protocol import MAX_SAMPLE_GAP_S
from .run import (
    COLLECTOR_FETCH_SUBDIR,
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
    compute_validity,
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

#: The proof's prescribed execution (ADR 0011, "The finite proof": "the
#: `nominal` scenario at 11.2 msg/s, three wearables, no warm-up, 300 s of
#: publication = 3,360 messages", the fault "issued through the harness
#: restart hook"), as the manifest's entry records it (run.py writes the
#: entry's scenario, duration_s, rate_msg_s, warmup_s and condition_id at
#: the top level) and as tools/session/proof_plan.py writes the plan.
PROOF_LOAD: dict[str, Any] = {
    "condition_id": "controller_restart",
    "scenario": "nominal",
    "duration_s": 300,
    "rate_msg_s": 11.2,
    "warmup_s": 0,
}
#: The plan's own count, 300 s x 11.2 msg/s: the count the population must
#: show when the simulator's manifest is absent and the file's line count
#: is the only source (E-11), with no tolerance.
PROOF_EXPECTED_MESSAGES = 3360
#: The prescribed fault instant (ADR 0011, the finite proof's table: "fault |
#: at t+150 s, ... issued through the harness restart hook (`--restart-cmd`,
#: `--restart-at-s`) so that both instants are in the manifest"): run.py
#: records the instant it scheduled as the restart record's requested_at_s.
PROOF_RESTART_AT_S = 150
#: The simulator's own manifest, where the harness keeps it
#: (run.simulator_run_dir, analyze.read_simulator_manifest): its `completed`
#: and `totals.sent` are the record of what was published (CONTRACTS 7).
SIMULATOR_MANIFEST_REL = "logs/simulator/{run_id}/manifest.json"
#: The collector file the ADR lists under "What it records" (item 5), from
#: the SUT collector (the manifest's resource_source).
COLLECTOR_FILENAME = "resources.csv"
SUT_COLLECTOR_SOURCE = "sut-collector"

#: The forms of the harness's validity E-12 names (harness_admission).
ADMISSION_VALID = "valid"
ADMISSION_SAMPLING_GAP_ONLY = "sampling-gap-only"
ADMISSION_NOT_ADMITTED = "not-admitted"
ADMISSION_UNKNOWN = "unknown"
#: run.ingest_resources' rejection warning, word for word: f"{source_label}
#: {src} REJECTED (SUT resources treated as missing): " followed by
#: resources.validate_resources_csv's problems joined by "; ". The two
#: source labels are the ones execute_run passes: '--collector-fetch-cmd
#: output' for the file the harness's own fetch hook wrote, and
#: '--resources-from' (ingest_resources' default) otherwise.
INGEST_REJECTED_MARK = " REJECTED (SUT resources treated as missing): "
INGEST_SOURCE_FETCH = "--collector-fetch-cmd output"
INGEST_SOURCE_RESOURCES_FROM = "--resources-from"
#: resources.validate_resources_csv's sampling-gap problem, which is always
#: the last problem it lists: f"{n} sampling gap(s) exceed the protocol
#: maximum of {max_sample_gap_s:g} s (MAX_SAMPLE_GAP_S): " followed by the
#: first three gaps, each f"{label} ({gap:.1f} s)" with a label beginning
#: f"container {name!r}: ", joined by "; ", then "; ..." when there are more
#: (ingest_resources calls it with the protocol's MAX_SAMPLE_GAP_S).
_GAP_PROBLEM_RE = re.compile(
    r"(\d+) sampling gap\(s\) exceed the protocol maximum of "
    + re.escape(f"{MAX_SAMPLE_GAP_S:g}")
    + r" s \(MAX_SAMPLE_GAP_S\): (.+)",
    re.S,
)
_GAP_ITEM_RE = re.compile(r"container (?:'[^']*'|\"[^\"]*\"): .+ \((\d+\.\d) s\)", re.S)
_GAP_ITEMS_SHOWN = 3

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
        "\"Published before the kill\", \"published inside the restart "
        "command's window\" and \"published while the controller was away\" "
        "are report figures on the host clocks, with a stated band; they never "
        "decide a restart class, and only P-4 reads them to attribute the kill "
        "as an N1 case's source. An ambiguous identity with only `duplicate` "
        "lines is not rejected as R3 on the ground of its class: it can be "
        "shown neither way (E-8)."
    ),
    "P-4": (
        "An N1 case's source is established by inference, since the "
        "controller's A5 occurrence names the delivery (topic, mid, qos, dup, "
        "connection, received_monotonic_ns) and not the identity: "
        "'a3-connection-end' when an ERROR occurrence of the connection-end "
        "message names the candidate's device in its topic and its "
        "in-progress delivery's received_monotonic_ns precedes the "
        "candidate's redelivered duplicate line; 'kill' when the candidate is "
        "restart-class, was published before the restart command's start on "
        "the host clock (the manifest's started_monotonic_ns, before which "
        "the kill cannot have landed) and the manifest's restart executed "
        "with exit 0. A candidate that is ambiguous under P-3, or published "
        "inside the restart command's window, is not thereby refused the "
        "kill as its source: with the other conditions met it can be shown "
        "neither way (E-8). A candidate is named only with the twin's "
        "evidence: the device's surplus equals the number of cases named on "
        "it and the after snapshot's last_seq is not below the candidate's "
        "seq. Each occurrence names one case at most (N1): a device's "
        "occurrences are offered first to its candidates the kill cannot "
        "explain (lined before the kill, published after the restart "
        "command's end, or the restart not executed with exit 0), so an "
        "occurrence two candidates contend for goes to the one no other "
        "source could explain, and each candidate takes the unused "
        "occurrence received last before its redelivered duplicate line "
        "(the earlier log line on a tie), so the occurrences name as many "
        "candidates as their order allows, whatever the order of the log "
        "lines."
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
        "of the ceiling was reached is unknown, and the proof is inconclusive; "
        "so is whether the restart was shown when the facts are absent or "
        "carry no restart_shown (null): an absent required fact is never read "
        "as false or zero, and the fault is then not demonstrated (E-11)."
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
        "each is R3. When one candidate claims it beside another "
        "duplicate-only identity that may have been in progress at the kill "
        "(not lined before it, not published after the restart command's "
        "end) and can be shown neither way (E-7, E-8), the case may be the "
        "other's: the claimant is neither named nor R3, and its device is "
        "undecided (E-9). A candidate the twin shows unapplied is R3 whatever "
        "was in progress at the kill and claims no case. When the readings "
        "record more than one controller process start after the pre-kill "
        "one, a further death is recorded that the plan did not prescribe and "
        "P-4 never names as a source. Each death is placed on the controller "
        "clock between the last reading of the process that died and the "
        "first reading of the next (monotonic_ns), and it may have preceded a "
        "candidate's redelivery only when the lower bound of that interval is "
        "below the received_monotonic_ns of the candidate's first duplicate "
        "line, or equal to it (a tie the readings cannot order, read "
        "inclusively as the band of P-3 and E-8 is), or when either cannot be "
        "read or the readings contradict the interval (the dying process read "
        "at or after the next one's first reading); a death wholly after the "
        "redelivery cannot be its source. Beside a further death that may have preceded a claimant's "
        "redelivery, a claimant of the kill cannot be told from an identity "
        "in progress at that further death, so no kill case is named and "
        "every claimant is neither named nor R3, its device undecided (E-9); "
        "a further death wholly after every claimant's redelivery leaves this "
        "rule as under one death, and a further death that may have preceded "
        "no duplicate-only candidate's redelivery explains nothing and is "
        "reported. Each recorded death counts one to the capacity, for the "
        "candidates whose redelivery it may have preceded (E-10)."
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
        "device, S4, S5, R3 and R4 are null for what depends on it; when the "
        "controller log (item 6) was not fetched, was recorded fetched but is "
        "absent, or is unreadable, an A3 connection end can be shown neither "
        "way, so a duplicate-only candidate that is not named with the kill "
        "as its source is neither named nor R3, S4 and R3 are null for it and "
        "S5 and R4 for its device unless the twin's figures refute under "
        "every naming of it (E-9), while a candidate the twin shows unapplied "
        "(no surplus, or more candidates than the surplus) stays R3 on the "
        "twin's evidence, which was read. The absence is named as a failed "
        "fetch and the run is inconclusive unless a refutation was observed "
        "on evidence that was read."
    ),
    "E-8": (
        "A duplicate-only candidate that is ambiguous under P-3 (a `duplicate` "
        "line received at or inside the controller-clock band between the "
        "last pre-kill reading and the first post-kill one, a line without "
        "received_monotonic_ns, or no band at all), or one published on the "
        "host clock inside the restart command's window (from the command's "
        "start, the manifest's started_monotonic_ns, to its end, finished_utc "
        "after started_utc plus the host band, the kill landing somewhere in "
        "it) or whose publication cannot be placed against that start, is "
        "neither named nor R3 on that ground: whether it was in progress at "
        "the kill cannot be shown from a reading inside the sampling band or "
        "a publication inside the command's window, since no criterion of "
        "the ADR involves timing and a poll or hook instant decides nothing "
        "of it. S4 and R3 are null for the candidate, and S5 and R4 for its "
        "device unless the twin's figures refute under every naming of it "
        "(E-9); the run is inconclusive on that ground, never refuted. A "
        "candidate lined before the kill on the controller clock, published "
        "after the command's end, or one the twin shows unapplied, is R3 as "
        "before."
    ),
    "E-9": (
        "S5 and R4 on a device with a duplicate-only candidate that can be "
        "shown neither way (E-7 over the controller log, E-8, or E-4 beside "
        "such a candidate): the twin's figures are shown as read and nothing "
        "is decided on them while some naming of the device's undecided "
        "candidates that the count allows (delta equal to the accepted lines "
        "plus the cases named, one per candidate named) leaves `delta` right, "
        "this run's last_run_id with the highest applied seq as last_seq, and "
        "no last_seq regression; each naming tried is listed. When no naming "
        "fits the count (a surplus beyond the undecided candidates), or every "
        "one that fits leaves a mismatch or a regression, or the last_seq "
        "regressed against the before snapshot or below the seqs the run is "
        "shown to have applied (P-5), the twin refutes on evidence that was "
        "read: R4 is observed and S5 does not hold, with S4 and R3 still null "
        "for the candidate. Every naming tried respects the sources the run "
        "evidences and their capacity across the whole run (E-10)."
    ),
    "E-10": (
        "The namings E-9 tries respect the sources the run evidences, their "
        "capacity across the whole run and P-4's order rule (a source "
        "precedes the candidate's redelivered duplicate line), each source "
        "serving what it can (N1: at most one such identity per death, or "
        "per connection ended under A3 after a PATCH, since there is one "
        "consumer): a recorded death gives at most one N1 case in the run, "
        "whichever device's, and only to a candidate whose redelivery it may "
        "have preceded on the controller clock (placed as E-4 states) - the "
        "deaths are every controller process start the readings record "
        "after the pre-kill one, or the manifest's kill (P-4's conditions on "
        "its restart record) when they record none, less the kill case "
        "already named - and each A5 occurrence read from the controller log "
        "at most one, of its own device alone, and only to a candidate whose "
        "redelivery its in-progress delivery may have preceded (received "
        "before the candidate's first duplicate line, or either stamp "
        "unreadable); occurrences on one device never serve another's need. "
        "With the log read, an occurrence that precedes an undecided "
        "candidate (E-8, E-4) names another case under P-4, and which of a "
        "device's occurrences served which of its cases is inference: the "
        "check is a matching of the candidates each undecided device's count "
        "requires, beside the cases named with an occurrence on those "
        "devices, to these sources, each source used once and each such "
        "named case keeping one - any occurrence of its device that may have "
        "preceded its redelivery or, when nothing read excludes it from the "
        "kill (not lined before it, not published after the restart "
        "command's end, the restart executed with exit 0), any death that "
        "may have - so a named case may leave its occurrence to an undecided "
        "candidate, and the occurrence P-4 recorded against a case never "
        "decides the capacity; the counts are small. When no such matching "
        "exists (a surplus of two on one device, or of one on each of two, with one "
        "death and no occurrence that may precede them; or a further death "
        "wholly after the redeliveries it would have to explain), no "
        "source-consistent naming explains the twins: R4 is observed and S5 "
        "does not hold, on the twin's evidence and the record, which were "
        "read, with every undecided device's figures, the deaths as placed "
        "and the sources each candidate may have had shown; a device that no "
        "matching of its own candidates to the sources serves, even with "
        "every recorded death available to it, is the mismatch by itself, "
        "whatever the deaths served elsewhere, and otherwise only the "
        "aggregate is established and no device is named as the mismatch; "
        "no identity is named as the case, with no A3 event assumed that the "
        "log does not record; S4 and R3 stay null for the candidates. When "
        "the controller log cannot serve the criteria (E-7) the number of A3 "
        "connection ends is unknown, so the capacity is unknown: E-9's count "
        "alone applies and the run stays inconclusive, never refuted on "
        "capacity grounds, since an unread log is not proof of zero A3 "
        "events."
    ),
    "E-11": (
        "The proof is evaluated only on the execution the ADR prescribes and "
        "the records it lists ('The finite proof', 'What it records'), with "
        "the harness's own validity quoted as recorded and admitted only as "
        "E-12 states: 'valid', or the campaign's MAX_SAMPLE_GAP_S deviation "
        "in the one form the harness records it (the ADR names that rule as "
        "one the proof's reconciliation does not touch, 'What it cannot "
        "show'); any other harness invalidity makes the run not eligible, "
        "every harness reason quoted, and an admission that cannot be read "
        "leaves the eligibility unknown (P-6), never met. Required besides, "
        "whatever the harness's verdict: the load and fault of the plan "
        "(condition controller_restart, the nominal scenario, 300 s at 11.2 "
        "msg/s, no warm-up, as the manifest's entry records them) with the "
        "simulator exited 0; the publication completed and the population "
        "whole (the simulator's own manifest, "
        "logs/simulator/<run_id>/manifest.json, says completed under the same "
        "load and its totals.sent equals the records of this run in "
        "sent_events.jsonl, none of which is skipped (E-5), without a "
        "message_id, repeated or of another run: a skipped or malformed line "
        "never shrinks the denominator; without that manifest the only count "
        "is the file's, which must then equal the plan's 300 x 11.2 = 3,360 "
        "with no tolerance); the fault at the plan's instant and demonstrated "
        "(the manifest's restart record requested at t+150 s, its "
        "requested_at_s, executed with exit 0, and the session facts' "
        "restart_shown true; absent or null, restart_shown is unknown, P-6); "
        "and every record of 'What it records' present with its fetch "
        "recorded successful: the harness copy events.jsonl with events_fetch "
        "ok (a readable file beside a failed or unrecorded fetch is not the "
        "copy) and the collector file resources.csv from the SUT collector "
        "(in E-12's sampling-gap form, the rejected collector file where the "
        "rejection names it, and the seal the harness withheld for the "
        "missing resources.csv alone accepted with the reason stated), beside "
        "the twin snapshots, the drain, the post-drain copy, the three SUT "
        "logs, the readings, the configuration identity and the seal. A run "
        "that fails any of these is not eligible: inconclusive with every "
        "reason named, never 'supports'; a refutation observed on evidence "
        "that was read and verified stands (P-7)."
    ),
    "E-12": (
        "The harness's validity is admitted for the proof in two forms only, "
        "recognised from what run.py writes and never from free text: "
        "'valid' (validity 'valid' with no reason); or the campaign's "
        "sampling-gap deviation the ADR anticipates (the harness 'may again "
        "mark the run invalid under MAX_SAMPLE_GAP_S'), in the one form the "
        "harness records it when its ingest rejects the collector file: "
        "validity 'invalid' with exactly the two reasons run.compute_validity "
        "writes for it ('no SUT resources' and 'mandatory artefact(s) missing "
        "from the run directory' for resources.csv alone), "
        "missing_mandatory_artifacts ['resources.csv'], resource_source "
        "'none', and exactly one warning of the ingest rejection "
        "(run.ingest_resources: '<source> <file> REJECTED (SUT resources "
        "treated as missing): <problems>') whose every problem is "
        "resources.validate_resources_csv's MAX_SAMPLE_GAP_S sampling-gap "
        "problem; the rejected collector file present and non-empty in the "
        "run directory at the path the rejection names, relative to the run "
        "directory (logs/collector/resources-<run_id>.csv for the harness's "
        "own fetch); no resources.csv at the top of the run directory; and "
        "SHA256SUMS absent, which run.py withholds for the missing "
        "resources.csv alone, or present and verifying. A rejection that also "
        "lists another problem, a further validity reason, a rejected file "
        "outside the run directory, absent or empty, or any other invalidity "
        "is not admitted, every harness reason quoted; a manifest field that "
        "cannot be read leaves the admission unknown (P-6), never admitted. "
        "In the sampling-gap form the evidence inventory (E-11) requires the "
        "collector file where the rejection names it instead of "
        "resources.csv, and accepts the withheld seal with the reason stated: "
        "the evaluator's own sha256 of every file it read, in the document's "
        "sources, carries the integrity of what it used; a SHA256SUMS present "
        "that does not verify is never accepted. The driver applies the same "
        "function (harness_admission), so the two parts cannot disagree."
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
# The harness's validity, admitted for the proof (E-12)
# ---------------------------------------------------------------------------


def sampling_gap_validity_reasons() -> list[str]:
    """The validity reasons run.compute_validity writes, and only those, for
    a timed run whose one departure is the collector file its ingest
    rejected: resource_source 'none' gives the 'no SUT resources' reason and
    resources.csv missing from the run directory the 'mandatory artefact(s)
    missing' reason (which also withholds the seal). Obtained from the
    harness's own function, so the recognition follows its wording; the
    restart evidence is left out of the call because, complete, it adds no
    reason (a controller_restart run with a failed item-18 step carries a
    further reason and is not this form)."""
    _validity, reasons = compute_validity(
        timed=True,
        sut_env_present=True,
        allow_missing_sut_env=False,
        resource_source="none",
        allow_missing_resources=False,
        restart_required=False,
        restart_ok=True,
        missing_artifacts=[COLLECTOR_FILENAME],
    )
    return reasons


def _directory_files(run_dir: Path) -> tuple[set[str], set[str]]:
    """Every file of the run directory by its relative path, and those of
    them that are empty (the loader and harness_admission read the same
    facts, so the evaluator and the driver cannot disagree on them)."""
    present: set[str] = set()
    empty: set[str] = set()
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        present.add(rel)
        if path.stat().st_size == 0:
            empty.add(rel)
    return present, empty


def _ingest_rejections(warnings: list[str]) -> list[str]:
    return [w for w in warnings if INGEST_REJECTED_MARK in w]


def _parse_rejection(text: str) -> tuple[str, str, str] | None:
    """(source label, rejected file, problems) of one ingest rejection, or
    None when its source is not one of the two run.py passes."""
    for label in (INGEST_SOURCE_FETCH, INGEST_SOURCE_RESOURCES_FROM):
        if text.startswith(label + " "):
            at = text.find(INGEST_REJECTED_MARK, len(label) + 1)
            if at < 0:
                return None
            return label, text[len(label) + 1 : at], text[at + len(INGEST_REJECTED_MARK) :]
    return None


def _not_sampling_gaps_only(problems: str) -> str | None:
    """Why the rejection's problems are not resources.validate_resources_csv's
    sampling-gap problem alone, or None when they are. That problem is the
    last the function lists, so a rejection whose text does not start with
    it lists another problem first."""
    match = _GAP_PROBLEM_RE.fullmatch(problems)
    if match is None:
        return (
            "the ingest rejection lists a problem other than a MAX_SAMPLE_GAP_S sampling gap "
            f"(resources.validate_resources_csv): {problems!r}"
        )
    count = int(match.group(1))
    items = match.group(2).split("; ")
    more = items[-1] == "..."
    if more:
        items = items[:-1]
    shaped = (
        0 < len(items) <= _GAP_ITEMS_SHOWN
        and (count > _GAP_ITEMS_SHOWN and len(items) == _GAP_ITEMS_SHOWN if more else count == len(items))
    )
    if not shaped:
        return (
            "the ingest rejection's sampling-gap problem is not in the form "
            f"resources.validate_resources_csv writes: {problems!r}"
        )
    for item in items:
        gap = _GAP_ITEM_RE.fullmatch(item)
        if gap is None or float(gap.group(1)) < MAX_SAMPLE_GAP_S:
            return (
                f"the ingest rejection lists {item!r}, which is not a container's sampling gap "
                f"over MAX_SAMPLE_GAP_S ({MAX_SAMPLE_GAP_S:g} s)"
            )
    return None


def _run_dir_relative(src: str, run_id: str) -> str | None:
    """The rejected file's path relative to the run directory the harness
    wrote (base/raw/<run_id>): what follows the last path segment equal to
    the run id, or None when the path names no such segment (a file outside
    the run directory) or climbs out of it."""
    parts = [part for part in src.replace("\\", "/").split("/") if part]
    at = max((i for i, part in enumerate(parts[:-1]) if part == run_id), default=None)
    if at is None:
        return None
    tail = parts[at + 1 :]
    if any(part in (".", "..") for part in tail):
        return None
    return "/".join(tail)


def fetch_collector_rel(run_id: str) -> str:
    """Where the harness's own fetch hook writes the collector file
    (run.execute_run: logs_dir / COLLECTOR_FETCH_SUBDIR /
    f"resources-{run_id}.csv"), relative to the run directory."""
    return f"logs/{COLLECTOR_FETCH_SUBDIR}/resources-{run_id}.csv"


def rejected_collector_file(manifest: dict[str, Any]) -> str | None:
    """The collector file the manifest's one ingest rejection names,
    relative to the run directory, or None (no single rejection, a source
    run.py does not use, or a file outside the run directory)."""
    warnings = manifest.get("warnings") if isinstance(manifest, dict) else None
    run_id = manifest.get("run_id") if isinstance(manifest, dict) else None
    if not isinstance(warnings, list) or not isinstance(run_id, str) or not run_id:
        return None
    rejections = _ingest_rejections([w for w in warnings if isinstance(w, str)])
    parsed = _parse_rejection(rejections[0]) if len(rejections) == 1 else None
    return _run_dir_relative(parsed[1], run_id) if parsed is not None else None


def admission_of(
    manifest: Any,
    files_present: set[str],
    empty_files: set[str],
    integrity: str | Callable[[], str],
) -> dict[str, Any]:
    """E-12 on the facts of a run directory: its files by relative path, the
    empty ones, and the state of its seal (analyze.check_run_integrity's
    'true', 'false' or 'unsealed', or a callable giving it, read only when
    the seal matters). harness_admission reads these facts from the
    directory; evaluate passes the loader's, which are the same."""
    rule = IDENTIFICATION_RULES["E-12"]

    def _result(
        admitted: bool | None,
        form: str,
        reasons: list[str],
        collector_file: str | None = None,
        seal_withheld_for: str | None = None,
    ) -> dict[str, Any]:
        return {
            "admitted": admitted,
            "form": form,
            "reasons": reasons,
            "collector_file": collector_file,
            "seal_withheld_for": seal_withheld_for,
            "rule": rule,
        }

    if not isinstance(manifest, dict):
        return _result(None, ADMISSION_UNKNOWN, ["the manifest is not a JSON object: its validity cannot be read"])
    validity = manifest.get("validity")
    reasons = manifest.get("validity_reasons")
    if validity not in ("valid", "invalid"):
        return _result(
            None, ADMISSION_UNKNOWN,
            [f"validity {validity!r} cannot be read: run.py writes 'valid' or 'invalid'"],
        )
    if not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
        return _result(
            None, ADMISSION_UNKNOWN,
            [f"validity_reasons {reasons!r} cannot be read: run.py writes a list of texts"],
        )
    quoted = [f"harness validity reason (quoted): {reason}" for reason in reasons]
    if validity == "valid":
        if reasons:
            return _result(
                None, ADMISSION_UNKNOWN,
                ["validity 'valid' beside validity reason(s): run.py writes 'valid' only with none", *quoted],
            )
        return _result(True, ADMISSION_VALID, [])
    if reasons != sampling_gap_validity_reasons():
        return _result(
            False, ADMISSION_NOT_ADMITTED,
            [
                "validity 'invalid' for reason(s) other than exactly the two run.compute_validity "
                "writes when its ingest rejects the collector file ('no SUT resources' and "
                "'mandatory artefact(s) missing from the run directory' for resources.csv alone): "
                "not the campaign's sampling-gap deviation",
                *quoted,
            ],
        )
    run_id = manifest.get("run_id")
    resource_source = manifest.get("resource_source")
    missing = manifest.get("missing_mandatory_artifacts")
    warnings = manifest.get("warnings")
    unreadable: list[str] = []
    if not isinstance(run_id, str) or not run_id:
        unreadable.append(f"run_id {run_id!r} cannot be read")
    if not isinstance(resource_source, str):
        unreadable.append(f"resource_source {resource_source!r} cannot be read")
    if not isinstance(missing, list) or not all(isinstance(m, str) for m in missing):
        unreadable.append(f"missing_mandatory_artifacts {missing!r} cannot be read")
    if not isinstance(warnings, list) or not all(isinstance(w, str) for w in warnings):
        unreadable.append(f"warnings {warnings!r} cannot be read")
    if unreadable:
        return _result(
            None, ADMISSION_UNKNOWN,
            [
                "the manifest carries the sampling-gap form's two validity reasons, but what "
                "decides the form cannot be read: " + "; ".join(unreadable),
                *quoted,
            ],
        )
    failures: list[str] = []
    if resource_source != "none":
        failures.append(f"resource_source {resource_source!r}, not 'none' as the rejected ingest leaves it")
    if missing != [COLLECTOR_FILENAME]:
        failures.append(
            f"missing_mandatory_artifacts {missing!r}, not ['{COLLECTOR_FILENAME}'] alone"
        )
    rejections = _ingest_rejections(warnings)
    collector_file: str | None = None
    if len(rejections) != 1:
        failures.append(
            f"{len(rejections)} warning(s) of the ingest rejection ('{INGEST_REJECTED_MARK.strip()}'), "
            "not exactly one"
        )
    else:
        parsed = _parse_rejection(rejections[0])
        if parsed is None:
            failures.append(
                "the ingest rejection names a source that run.py does not pass "
                f"({INGEST_SOURCE_FETCH!r} or {INGEST_SOURCE_RESOURCES_FROM!r}): {rejections[0]!r}"
            )
        else:
            label, src, problems = parsed
            why = _not_sampling_gaps_only(problems)
            if why is not None:
                failures.append(why)
            rel = _run_dir_relative(src, run_id)
            if rel is None:
                failures.append(
                    f"the rejected file {src!r} is not in the run directory (no path segment "
                    f"{run_id!r} before it): it cannot be read where the rejection names it"
                )
            elif label == INGEST_SOURCE_FETCH and rel != fetch_collector_rel(run_id):
                failures.append(
                    f"the rejected file of the harness's own fetch is at {rel}, not at "
                    f"{fetch_collector_rel(run_id)} where run.py writes it"
                )
            elif rel not in files_present:
                failures.append(f"the rejected collector file {rel} is absent from the run directory")
            elif rel in empty_files:
                failures.append(f"the rejected collector file {rel} is empty")
            else:
                collector_file = rel
    if COLLECTOR_FILENAME in files_present:
        failures.append(
            f"{COLLECTOR_FILENAME} is present at the top of the run directory, which run.py "
            "writes only when its ingest accepts the collector file"
        )
    seal_withheld_for: str | None = None
    if SUMS_FILENAME in files_present:
        state = integrity() if callable(integrity) else integrity
        if state != INTEGRITY_OK:
            failures.append(f"{SUMS_FILENAME} is present and does not verify (seal {state!r})")
    else:
        seal_withheld_for = (
            f"the missing mandatory artefact {COLLECTOR_FILENAME} alone (run.py withholds "
            f"{SUMS_FILENAME} while a mandatory artefact is missing)"
        )
    if failures:
        return _result(
            False, ADMISSION_NOT_ADMITTED,
            [*failures, *quoted, *(f"ingest rejection (quoted): {w}" for w in rejections)],
        )
    return _result(
        True, ADMISSION_SAMPLING_GAP_ONLY,
        [
            "the campaign's MAX_SAMPLE_GAP_S deviation alone, in the form the harness records "
            f"it: the collector file rejected at ingest and kept at {collector_file}",
            *quoted,
            f"ingest rejection (quoted): {rejections[0]}",
        ],
        collector_file,
        seal_withheld_for,
    )


def harness_admission(manifest: dict, run_dir: Path) -> dict:
    """E-12 for the driver and the evaluator alike: whether the harness's
    validity is admitted for the proof, read from the manifest and the run
    directory (no file is written). Returns ``{"admitted": True | False |
    None, "form": "valid" | "sampling-gap-only" | "not-admitted" |
    "unknown", "reasons": [str], "collector_file": relpath | None,
    "seal_withheld_for": str | None, "rule": str}``: 'valid' when the
    manifest's validity is 'valid'; 'sampling-gap-only' in the one form
    E-12 names, with the rejected collector file's path relative to the run
    directory and, when SHA256SUMS is absent, what the harness withheld it
    for; 'not-admitted' for any other invalidity, every harness reason
    quoted; 'unknown' (admitted None) when a field that decides it, or the
    run directory itself, cannot be read. ``manifest`` may be any JSON
    value (anything but an object is unknown)."""
    run_dir = Path(run_dir)
    try:
        if not run_dir.is_dir():
            raise OSError(f"{run_dir} is not a directory")
        files_present, empty_files = _directory_files(run_dir)
    except OSError as exc:
        return {
            "admitted": None,
            "form": ADMISSION_UNKNOWN,
            "reasons": [f"the run directory cannot be read: {exc}"],
            "collector_file": None,
            "seal_withheld_for": None,
            "rule": IDENTIFICATION_RULES["E-12"],
        }
    return admission_of(manifest, files_present, empty_files, lambda: check_run_integrity(run_dir)[0])


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
    #: The simulator's own manifest (SIMULATOR_MANIFEST_REL): the record of
    #: what it published (E-11); None when absent or unreadable (then named
    #: in ``problems``).
    simulator_manifest: dict[str, Any] | None = None
    #: The files of ``files_present`` that are empty (E-12 needs the
    #: rejected collector file non-empty).
    empty_files: set[str] = field(default_factory=set)


def simulator_manifest_rel(run_id: str) -> str:
    return SIMULATOR_MANIFEST_REL.format(run_id=run_id)


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
    files_present, empty_files = _directory_files(run_dir)
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

    # The simulator's own manifest (E-11): read where the harness keeps it;
    # the problem names the relative path, as every other does.
    simulator_manifest: dict[str, Any] | None = None
    sim_rel = simulator_manifest_rel(str(manifest.get("run_id") or run_dir.name))
    if sim_rel in files_present:
        try:
            simulator_manifest = _read_json_object(run_dir / sim_rel)
        except ProofInputError as exc:
            text = str(exc)
            name = Path(sim_rel).name
            problems.append(sim_rel + text[len(name):] if text.startswith(name) else f"{sim_rel}: {text}")
        else:
            _sha(sim_rel)
    if COLLECTOR_FILENAME in files_present:
        _sha(COLLECTOR_FILENAME)
    # The collector file the harness's ingest rejected, where its rejection
    # names it (E-12): inventoried in that form, so its digest is carried.
    rejected = rejected_collector_file(manifest)
    if rejected is not None and rejected in files_present:
        _sha(rejected)

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
        simulator_manifest=simulator_manifest,
        empty_files=empty_files,
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


@dataclass(frozen=True)
class Death:
    """One recorded death of the controller, placed on its clock (E-4):
    after the last reading of the process that died (``after``) and before
    the first reading of the next (``before``), both monotonic_ns as the
    controller reported them. The first is the kill (the pre-kill process's
    death); the others are further deaths the plan did not prescribe."""

    index: int
    dying_started_at: str | None
    next_started_at: str | None
    after: int | None
    before: int | None

    @property
    def placed(self) -> bool:
        """Its lower bound is read and the readings do not contradict it
        (the dying process read at or after the next one's first reading)."""
        return self.after is not None and (self.before is None or self.after < self.before)

    def may_precede(self, redelivered: int | None) -> bool:
        """Whether the death may have preceded a redelivered duplicate line
        received at ``redelivered`` (None: the line's stamp is unread): only a
        death wholly after it cannot (E-4). A line received at the dying
        process's last reading itself is a tie the readings cannot order,
        read inclusively as the band of P-3 and E-8 is."""
        if redelivered is None or not self.placed:
            return True
        return self.after <= redelivered

    def placement(self) -> str:
        if self.after is None:
            return (
                f"not placed on the controller clock (no readable monotonic_ns of process "
                f"{self.dying_started_at}), so it may have preceded any redelivery"
            )
        span = (
            f"between the last reading of process {self.dying_started_at} (monotonic_ns {self.after}) "
            + (
                f"and the first reading of process {self.next_started_at} ({self.before})"
                if self.before is not None
                else "and a next reading that cannot be read"
            )
        )
        if not self.placed:
            return span + ", which the readings contradict, so it may have preceded any redelivery"
        return span

    def as_dict(self) -> dict[str, Any]:
        return {
            "death": self.index,
            "kind": "kill" if self.index == 0 else "further",
            "dying_started_at": self.dying_started_at,
            "next_started_at": self.next_started_at,
            "after_monotonic_ns": self.after,
            "before_monotonic_ns": self.before,
            "placed": self.placed,
            "placement": self.placement(),
        }


def recorded_deaths(split: ProcessSplit, restart_ok: bool) -> list[Death]:
    """The deaths the readings record, in order (E-4, E-10): one per
    controller process after the pre-kill one, the processes ordered by
    their first reading on the controller clock (then by started_at), each
    death placed between the last reading of the process that died and the
    first reading of the next; or, when they record none, the manifest's
    kill if it executed with exit 0, placed after the last pre-kill reading."""
    rows_of: dict[str | None, list[MetricsRow]] = {split.pre_started_at: list(split.pre_kill)}
    for row in split.post_kill:
        rows_of.setdefault(row.started_at, []).append(row)

    def _first(started_at: str | None) -> int | None:
        return min((r.monotonic_ns for r in rows_of.get(started_at, []) if r.monotonic_ns is not None), default=None)

    def _last(started_at: str | None) -> int | None:
        return max((r.monotonic_ns for r in rows_of.get(started_at, []) if r.monotonic_ns is not None), default=None)

    order = sorted(
        {r.started_at for r in split.post_kill if r.started_at is not None},
        key=lambda s: (_first(s) is None, _first(s) or 0, s),
    )
    chain = [split.pre_started_at, *order]
    deaths = [
        Death(index, chain[index], chain[index + 1], _last(chain[index]), _first(chain[index + 1]))
        for index in range(len(order))
    ]
    if not deaths and restart_ok:
        deaths.append(Death(0, split.pre_started_at, None, _last(split.pre_started_at), None))
    return deaths


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
    published_during_restart: list[str]
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
            "published_during_restart": len(self.published_during_restart),
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
    # The restart command's window on the host clock: started_monotonic_ns
    # is the instant the harness spawned the command and the kill lands
    # somewhere before it returned (finished_utc, 20-23 s later in r01/r02);
    # the two wall-clock stamps give its length, with the band for a step
    # between them.
    restart_end_host_ns = None
    if kill_host_ns is not None and isinstance(restart, dict):
        started = _parse_ts(str(restart.get("started_utc") or ""))
        finished = _parse_ts(str(restart.get("finished_utc") or ""))
        if started is not None and finished is not None:
            length_ns = max(0, int((finished - started).total_seconds() * 1_000_000_000))
            restart_end_host_ns = kill_host_ns + length_ns + band_ns
    before: list[str] = []
    during: list[str] = []
    away: list[str] = []
    after: list[str] = []
    unplaced: list[str] = []
    for message_id, sent in valid.items():
        publish = sent.publish_monotonic_ns
        if publish is None or kill_host_ns is None:
            unplaced.append(message_id)
        elif publish < kill_host_ns:
            before.append(message_id)
        elif restart_end_host_ns is None or publish < restart_end_host_ns:
            during.append(message_id)
        elif resub_host_ns is None:
            away.append(message_id)
        elif publish < resub_host_ns + band_ns:
            away.append(message_id)
        else:
            after.append(message_id)
    if kill_host_ns is None:
        notes.append("the manifest's restart record carries no started_monotonic_ns: publication is unplaced")
    elif restart_end_host_ns is None:
        notes.append(
            "the restart record's started_utc or finished_utc cannot be read: the restart "
            "command's end is unplaced on the host clock, so every identity published after "
            "its start is counted as published inside its window"
        )
    if kill_host_ns is not None and resub_host_ns is None:
        notes.append(
            "no post-kill reading shows mqtt_subscribed true (or the manifest's host "
            "anchor is absent): every identity published after the kill is counted "
            "as published while the controller was away"
        )
    away_window = {
        "kill_host_monotonic_ns": kill_host_ns,
        "restart_started_utc": restart.get("started_utc") if isinstance(restart, dict) else None,
        "restart_finished_utc": restart.get("finished_utc") if isinstance(restart, dict) else None,
        "restart_command_end_host_monotonic_ns": restart_end_host_ns,
        "resubscribed_row": resubscribed.place() if resubscribed else None,
        "resubscribed_host_monotonic_ns": resub_host_ns,
        "band_s": HOST_CLOCK_STEP_BAND_S,
        "subscription_granted_ts_in_controller_log": subscription_granted_ts,
        "note": (
            "host wall clock and host monotonic through the manifest's anchor, with "
            f"a {HOST_CLOCK_STEP_BAND_S:g} s band for the host clock steps; the restart "
            "command's window runs from its start (kill_host_monotonic_ns, the spawn) to "
            "its end (finished_utc after started_utc, plus the band) and the kill lands "
            "inside it; the controller log's subscription line is on the guest clock "
            "and is reported beside it, never used to decide; none of these figures "
            "decides a criterion, and only P-4 reads them for an N1 case's source"
        ),
    }
    return Classification(
        pre_kill_lined=_sorted_ids(pre_lined, valid),
        restart_class=_sorted_ids(restart_class, valid),
        ambiguous=_sorted_ids(ambiguous, valid),
        published_before_kill=_sorted_ids(before, valid),
        published_during_restart=_sorted_ids(during, valid),
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
    ``cannot_show`` (neither named nor R3: no twin evidence exists for the
    device or the controller log cannot serve the criteria, E-7; the
    candidate is ambiguous on the controller clock or its publication falls
    inside the restart command's window, E-8; or it claims the kill beside
    such a candidate, E-4). ``undecided_devices`` maps each device whose
    S5/R4 tolerance depends on such a candidate to the rule, the reason and
    the candidates (E-9 decides what the twin still shows on it)."""

    named: list[dict[str, Any]]
    r3: list[dict[str, Any]]
    r4_unexplained: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    notes: list[str]
    cannot_show: list[dict[str, Any]] = field(default_factory=list)
    undecided_devices: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: The sources the run evidences and their capacity for the namings
    #: E-9 tries on the undecided devices (E-10): whether they are known
    #: (the controller log read), the kill's availability, the A5
    #: occurrences read and used, per undecided device the occurrences
    #: that may have preceded one of its candidates, and the sources that
    #: may have been those of each case named with an occurrence.
    sources: dict[str, Any] = field(default_factory=dict)

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
    log_problem: str | None = None,
    post_kill_started_at: list[str] | None = None,
    deaths: list[Death] | None = None,
) -> N1Naming:
    """The N1 cases of S4, named only with a source and the twin's evidence
    (P-4, E-4); the duplicate-only identities that are not named are R3,
    and a device surplus beyond its named cases is R4. A candidate on a
    device without twin evidence (``surplus`` None because a snapshot is
    absent, not verified or unreadable - ``twins_problem`` says which - or
    a device neither snapshot names) is neither named nor R3: nothing shows
    whether it was applied (E-7). Nor is a candidate whose source cannot be
    established because the controller log cannot serve the criteria
    (``log_problem`` says why, E-7), because it is ambiguous on the
    controller clock or was published inside the restart command's window
    (E-8), or because it claims the kill beside such a candidate that may
    have been in progress at it (E-4): its device is then undecided for
    S5/R4 (E-9). ``post_kill_started_at`` is every controller process the
    readings record after the pre-kill one and ``deaths`` the deaths they
    record, placed on the controller clock (:func:`recorded_deaths`): each
    counts one to the capacity for the candidates whose redelivery it may
    have preceded (E-10); a further death, which the plan did not prescribe,
    is never named as a source (P-4), and no claimant of the kill is named
    beside one that may have preceded its redelivery (E-4). Without
    ``deaths`` every death recorded may have preceded every redelivery."""
    restart = restart if isinstance(restart, dict) else {}
    restart_ok = restart.get("executed") is True and restart.get("returncode") == 0
    #: The deaths the run records: every process start the readings show
    #: after the pre-kill process, or the manifest's kill when the readings
    #: show none (E-10), each placed on the controller clock (E-4).
    starts = list(post_kill_started_at or [])
    if deaths is None:
        deaths = [
            Death(index, None, None, None, None) for index in range(max(len(starts), 1 if restart_ok else 0))
        ]
    death_count = len(deaths)
    further_deaths = deaths[1:]
    #: Each candidate's redelivery on the controller clock for the order
    #: rule of E-4 and E-10: its first duplicate line's received stamp, or
    #: None when a duplicate line carries none (any source may precede it).
    redelivery_of: dict[str, int | None] = {}
    restart_class = set(classification.restart_class)
    ambiguous = set(classification.ambiguous)
    before_kill = set(classification.published_before_kill)
    during_restart = set(classification.published_during_restart)
    unplaced = set(classification.publication_unplaced)
    candidates: list[dict[str, Any]] = []
    for message_id in _sorted_ids(valid, valid):
        identity_lines = lines.get(message_id, [])
        if not _has(identity_lines, "duplicate") or _has(identity_lines, "accepted"):
            continue
        sent = valid[message_id]
        duplicates = [_received(line) for line in identity_lines if line.get("outcome") == "duplicate"]
        known = [r for r in duplicates if r is not None]
        redelivery_of[message_id] = min(known) if known and len(known) == len(duplicates) else None
        candidates.append(
            {
                **_identity(sent),
                "outcomes": _outcomes_of(identity_lines),
                "first_duplicate_received_monotonic_ns": min(known) if known else None,
                "in_restart_class": message_id in restart_class,
                "class": (
                    "restart_class" if message_id in restart_class
                    else "ambiguous" if message_id in ambiguous
                    else "pre_kill_lined"
                ),
                "published_before_kill": message_id in before_kill,
                "published_during_restart": message_id in during_restart,
                "publication_unplaced": message_id in unplaced,
            }
        )
    by_device: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_device.setdefault(candidate["device_uuid"] or "", []).append(candidate)

    named: list[dict[str, Any]] = []
    r3: list[dict[str, Any]] = []
    r4: list[dict[str, Any]] = []
    cannot: list[dict[str, Any]] = []
    undecided: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    kill_claimants: list[tuple[dict[str, Any], Surplus]] = []
    #: Unshown candidates that may have been in progress at the kill (E-4):
    #: (message_id, the rule that leaves them unshown).
    possible_claimants: list[tuple[str, str]] = []
    used_occurrences: set[int] = set()

    def _reject(candidate: dict[str, Any], why: str) -> None:
        r3.append({**candidate, "why_not_named": why})

    def _cannot_show(candidate: dict[str, Any], rule_id: str, why: str) -> None:
        """Neither named nor R3 (E-7 over the log, E-8, E-4): the candidate's
        device is then undecided for S5/R4, whose tolerance depends on the
        case (E-9)."""
        cannot.append({**candidate, "why_not_shown": why})
        entry = undecided.setdefault(
            candidate["device_uuid"] or "", {"rule": rule_id, "why": why, "message_ids": []}
        )
        entry["message_ids"].append(candidate["message_id"])

    def _may_have_been_at_the_kill(candidate: dict[str, Any]) -> bool:
        """Nothing read excludes the candidate from the kill: its line was
        not written by the pre-kill process, it was not published after the
        restart command's end, and the record shows the kill."""
        return (
            candidate["class"] != "pre_kill_lined"
            and restart_ok
            and (
                candidate["published_before_kill"]
                or candidate["published_during_restart"]
                or candidate["publication_unplaced"]
            )
        )

    def _band_place(candidate: dict[str, Any]) -> str:
        received = candidate["first_duplicate_received_monotonic_ns"]
        band = classification.band
        lower, upper = band.get("k_lower_monotonic_ns"), band.get("k_upper_monotonic_ns")
        if lower is None or upper is None:
            return (
                "the kill could not be placed on the controller clock (no readable "
                "monotonic_ns on both sides of the restart)"
            )
        if received is None:
            return "its duplicate line carries no received_monotonic_ns"
        return (
            f"its duplicate line was received at {received} on the controller clock, "
            f"at or inside the sampling band between the last pre-kill reading ({lower}, "
            f"row {(band.get('lower_row') or {}).get('row')}) and the first post-kill "
            f"reading ({upper}, row {(band.get('upper_row') or {}).get('row')})"
        )

    def _window_place(candidate: dict[str, Any]) -> str:
        window = classification.away_window
        start, end = window.get("kill_host_monotonic_ns"), window.get("restart_command_end_host_monotonic_ns")
        if candidate["publication_unplaced"]:
            return (
                "its publication cannot be placed against the restart command's start on "
                "the host clock (no publish_monotonic_ns on its sent line, or no "
                "started_monotonic_ns in the manifest's restart record)"
            )
        publish = valid[candidate["message_id"]].publish_monotonic_ns
        return (
            f"it was published at {publish} on the host clock inside the restart command's "
            f"window, from the command's start at {start} to its end at "
            + (
                f"{end} (finished_utc after started_utc, plus the {HOST_CLOCK_STEP_BAND_S:g} s host band)"
                if end is not None
                else "an instant that cannot be read (no readable started_utc/finished_utc)"
            )
            + ", where the kill lands"
        )

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
                if _may_have_been_at_the_kill(candidate):
                    possible_claimants.append((candidate["message_id"], "E-7"))
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
        # P-4 with N1's capacity, each occurrence naming one case at most:
        # the candidates the kill cannot explain are offered the device's
        # occurrences first (an occurrence two candidates contend for goes
        # to the one no other source could explain), and each takes the
        # unused occurrence received last before its redelivery (the
        # earlier log line on a tie). An occurrence's candidates are then
        # every one redelivered after it, so taking the latest leaves the
        # earlier ones to the candidates redelivered sooner: the
        # occurrences name as many candidates as their order allows,
        # whatever the order of the log lines.
        for candidate in sorted(device_candidates, key=_may_have_been_at_the_kill):
            redelivered = candidate["first_duplicate_received_monotonic_ns"]
            occurrence = max(
                (
                    occ
                    for occ in occurrences
                    if occ["line"] not in used_occurrences
                    and occ["device_uuid"] == device
                    and _is_int(occ["identity"].get("received_monotonic_ns"))
                    and redelivered is not None
                    and occ["identity"]["received_monotonic_ns"] < redelivered
                ),
                key=lambda occ: (occ["identity"]["received_monotonic_ns"], -occ["line"]),
                default=None,
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
            elif log_problem is not None:
                _cannot_show(
                    candidate, "E-7",
                    "no A5 occurrence can be read: the controller log cannot serve the criteria "
                    f"({log_problem}), so an A3 connection end can be shown neither way, and the "
                    "kill is not established as its source (E-7)",
                )
                if _may_have_been_at_the_kill(candidate):
                    possible_claimants.append((candidate["message_id"], "E-7"))
            else:
                # The grounds that reject the kill as its source (R3), apart
                # from those that only leave it unshown (E-8): a band on the
                # controller clock, or the restart command's window on the
                # host clock, decides nothing.
                why = []
                unshown = []
                if candidate["class"] == "pre_kill_lined":
                    why.append("lined before the kill on the controller clock, not of the restart classes")
                if not restart_ok:
                    why.append("the manifest's restart did not execute with exit 0")
                if not candidate["published_before_kill"]:
                    if candidate["published_during_restart"] or candidate["publication_unplaced"]:
                        unshown.append(_window_place(candidate))
                    else:
                        why.append("published after the restart command's end on the host clock, not before the kill")
                if candidate["class"] == "ambiguous":
                    unshown.append(_band_place(candidate))
                if not why:
                    # Restart-class, published before the command's start and
                    # the restart shown is a kill claimant above, so a ground
                    # that only leaves it unshown remains here.
                    _cannot_show(
                        candidate, "E-8",
                        "whether it was in progress at the kill cannot be shown: "
                        + "; ".join(unshown)
                        + "; a poll or hook instant decides nothing of the criterion (E-8)",
                    )
                    possible_claimants.append((candidate["message_id"], "E-8"))
                    continue
                if unshown:
                    why.append("(" + "; ".join(unshown) + ": which alone would not reject it, E-8)")
                taken = sorted(
                    occ["line"]
                    for occ in occurrences
                    if occ["line"] in used_occurrences
                    and occ["device_uuid"] == device
                    and _is_int(occ["identity"].get("received_monotonic_ns"))
                    and redelivered is not None
                    and occ["identity"]["received_monotonic_ns"] < redelivered
                )
                _reject(
                    candidate,
                    (
                        "each A5 occurrence naming its device before its redelivery (controller log "
                        f"line(s) {', '.join(str(line) for line in taken)}) names another case, one "
                        "case per connection end (N1),"
                        if taken
                        else "no A5 occurrence names its device before its redelivery"
                    )
                    + " and the kill cannot be its source: " + "; ".join(why),
                )

    def _further_before(candidate: dict[str, Any]) -> list[Death]:
        """The further deaths that may have preceded the candidate's
        redelivered duplicate line on the controller clock (E-4)."""
        redelivered = redelivery_of.get(candidate["message_id"])
        return [death for death in further_deaths if death.may_precede(redelivered)]

    def _redelivery_text(candidate: dict[str, Any]) -> str:
        redelivered = redelivery_of.get(candidate["message_id"])
        return (
            f"received at {redelivered}" if redelivered is not None
            else "a duplicate line without received_monotonic_ns"
        )

    def _deaths_text(found: list[Death]) -> str:
        return "; ".join(f"death {death.index} {death.placement()}" for death in found)

    if further_deaths:
        notes.append(
            f"the readings record {death_count} controller process starts after the pre-kill one "
            f"({', '.join(starts)}): the plan prescribes one kill, so a further death is "
            "recorded that P-4 never names as a source; each recorded death counts one to "
            "the capacity for the candidates whose redelivery it may have preceded (E-10), and "
            "no claimant of the kill is named beside a further death that may have preceded its "
            "redelivery (E-4): " + _deaths_text(deaths)
        )
    claimant_further = {candidate["message_id"]: _further_before(candidate) for candidate, _facts in kill_claimants}
    if len(kill_claimants) == 1 and claimant_further[kill_claimants[0][0]["message_id"]]:
        # E-4 with a further death that may have preceded the claimant's
        # redelivery: it may have been in progress at the command's kill or
        # at that death, which P-4 cannot name; the twin shows it applied,
        # so it is not R3 either.
        candidate, facts = kill_claimants[0]
        if facts.after_last_seq is None or candidate["seq"] is None or facts.after_last_seq < candidate["seq"]:
            _reject(
                candidate,
                f"the after snapshot's last_seq {facts.after_last_seq} is below the identity's seq {candidate['seq']}",
            )
        else:
            _cannot_show(
                candidate, "E-4",
                "it claims the kill as its source (restart-class, published before the restart "
                f"command's start, the restart executed with exit 0), but the readings record "
                f"{death_count} controller process starts after the pre-kill one ({', '.join(starts)}), "
                "and a further death may have preceded its redelivered duplicate line "
                f"({_redelivery_text(candidate)}): {_deaths_text(claimant_further[candidate['message_id']])}; "
                "at most one N1 case per death (E-4), and whether it was in progress at the "
                "command's kill or at the further death, which is never named as a source "
                "(P-4), cannot be told, so it is neither named nor R3",
            )
    elif len(kill_claimants) == 1:
        candidate, facts = kill_claimants[0]
        if facts.after_last_seq is None or candidate["seq"] is None or facts.after_last_seq < candidate["seq"]:
            _reject(
                candidate,
                f"the after snapshot's last_seq {facts.after_last_seq} is below the identity's seq {candidate['seq']}",
            )
        elif possible_claimants:
            # E-4: one consumer dies once. If an unshown identity was in
            # progress at the kill this one was not, and nothing read tells
            # them apart.
            others = ", ".join(f"{message_id} ({rule})" for message_id, rule in sorted(possible_claimants))
            notes.append(
                f"one identity claims the kill as its source beside {len(possible_claimants)} "
                "duplicate-only identity(ies) that may have been in progress at the kill and "
                "can be shown neither way: none is named (E-4)"
            )
            _cannot_show(
                candidate, "E-4",
                "it claims the kill as its source (restart-class, published before the restart "
                f"command's start, the restart executed with exit 0), but {len(possible_claimants)} "
                "other duplicate-only identity(ies) may have been in progress at the kill and can "
                f"be shown neither way: {others}; at most one N1 case per death (E-4), so it is "
                "neither named nor R3",
            )
        else:
            source_evidence = {
                "restart_started_utc": restart.get("started_utc"),
                "restart_finished_utc": restart.get("finished_utc"),
                "restart_returncode": restart.get("returncode"),
                "restart_stderr_tail": restart.get("stderr_tail"),
                "inference": IDENTIFICATION_RULES["P-4"],
            }
            if further_deaths:
                # E-4: every further death recorded follows its redelivery on
                # the controller clock, so none of them can be its source.
                source_evidence["further_deaths_after_its_redelivery"] = (
                    f"its redelivered duplicate line ({_redelivery_text(candidate)}) precedes every "
                    f"further death recorded: {_deaths_text(further_deaths)} (E-4)"
                )
            named.append(
                {
                    **candidate,
                    "source": "kill",
                    "source_evidence": source_evidence,
                    "twin_evidence": _twin_evidence(facts),
                }
            )
    elif len(kill_claimants) > 1:
        notes.append(
            f"{len(kill_claimants)} duplicate-only identities claim the kill as their source; at "
            "most one N1 case per death (N1), so none is named"
        )
        # E-4: the further-death reading applies only when a further death
        # may have preceded some claimant's redelivery; deaths wholly after
        # every claimant's redelivery leave them claiming the one kill.
        preceded = sorted(message_id for message_id, found in claimant_further.items() if found)
        after_all = (
            "; the further death(s) recorded follow every claimant's redelivered duplicate line "
            "on the controller clock, so none of them can be a claimant's source (E-4)"
            if further_deaths else ""
        )
        for candidate, _facts in kill_claimants:
            if preceded:
                _cannot_show(
                    candidate, "E-4",
                    f"{len(kill_claimants)} identities claim the kill as their source and the "
                    f"readings record {death_count} controller process starts after the pre-kill one "
                    f"({', '.join(starts)}), a further death having possibly preceded the redelivery "
                    f"of {', '.join(preceded)}: at most one N1 case per death (E-4), and which of "
                    "them, if any, was in progress at the command's kill rather than at the "
                    "further death, which is never named as a source (P-4), cannot be told, so "
                    "none is named and none is R3",
                )
            elif log_problem is not None:
                _cannot_show(
                    candidate, "E-7",
                    "more than one identity claims the one death (at most one N1 case per "
                    "death, E-4) and no A5 occurrence can be read that would name another "
                    f"source: the controller log cannot serve the criteria ({log_problem}) (E-7)"
                    + after_all,
                )
            else:
                _reject(
                    candidate,
                    "more than one identity claims the one death: at most one N1 case per death (E-4)"
                    + after_all,
                )
    for device in sorted(surplus or {}):
        facts = surplus[device]
        if device in undecided:
            continue  # the surplus may be the unshown case's evidence: undecided, not unexplained
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
    for entry in undecided.values():
        entry["message_ids"].sort()
    # E-10: the sources the run evidences, for the namings E-9 tries on the
    # undecided devices, each with P-4's order rule, an occurrence serving
    # its own device alone and a death a candidate of any device whose
    # redelivery it may have preceded (E-4), the kill no longer once its
    # case is named. With the log read, an occurrence that precedes an
    # undecided candidate names a case above: which of a device's
    # occurrences served which of its cases is inference, so the cases
    # named with an occurrence take part in the matching too, each with
    # every occurrence of its device that may have preceded its redelivery
    # and, when nothing read excludes it from the kill, every death that
    # may have; an undecided candidate is offered every occurrence of its
    # device that may have preceded it, one such a case holds included.
    # With the log unusable, the number of A3 connection ends, and so the
    # capacity, is unknown.
    kill_named = [case["message_id"] for case in named if case["source"] == "kill"]
    available = [death for death in deaths if not (death.index == 0 and kill_named)]

    def _a5_may_serve(occ: dict[str, Any], redelivered: int | None) -> bool:
        received = occ["identity"].get("received_monotonic_ns")
        return not _is_int(received) or redelivered is None or received < redelivered

    def _a5_lines(device: str, redelivered: int | None) -> list[int]:
        return sorted(
            occ["line"] for occ in occurrences if occ["device_uuid"] == device and _a5_may_serve(occ, redelivered)
        )

    possible: dict[str, dict[str, list[int]]] = {}
    a5_possible: dict[str, list[int]] = {}
    for device, entry in undecided.items():
        lines_here: set[int] = set()
        for message_id in entry["message_ids"]:
            redelivered = redelivery_of.get(message_id)
            a5 = _a5_lines(device, redelivered)
            lines_here.update(a5)
            possible[message_id] = {
                "a5_lines": a5,
                "deaths": [death.index for death in available if death.may_precede(redelivered)],
            }
        a5_possible[device] = sorted(lines_here)
    #: The cases named with an A5 occurrence, each with the sources that may
    #: have been its own for the matching of E-10.
    named_sources: dict[str, dict[str, Any]] = {}
    for case in named:
        if case["source"] != "a3-connection-end":
            continue
        redelivered = redelivery_of.get(case["message_id"])
        named_sources[case["message_id"]] = {
            "device_uuid": case["device_uuid"] or "",
            "named_with_line": case["source_evidence"]["controller_log_line"],
            "a5_lines": _a5_lines(case["device_uuid"] or "", redelivered),
            "deaths": (
                [death.index for death in available if death.may_precede(redelivered)]
                if _may_have_been_at_the_kill(case)
                else []
            ),
        }
    # A further death that may have preceded no duplicate-only candidate's
    # redelivery explains nothing (E-4): reported, never a source.
    explains_nothing = [
        death.index
        for death in further_deaths
        if not any(death.may_precede(redelivery_of.get(c["message_id"])) for c in candidates)
    ]
    if explains_nothing:
        notes.append(
            f"further death(s) {', '.join(str(i) for i in explains_nothing)} may have preceded no "
            "duplicate-only candidate's redelivered duplicate line on the controller clock: they "
            "explain nothing and serve no case (E-4, E-10)"
        )
    death_records = [
        {
            **death.as_dict(),
            "may_precede": sorted(
                c["message_id"] for c in candidates if death.may_precede(redelivery_of.get(c["message_id"]))
            ),
            "spent_on_named_kill_case": kill_named[0] if death.index == 0 and kill_named else None,
        }
        for death in deaths
    ]
    sources = {
        "known": log_problem is None,
        "why_unknown": log_problem,
        "deaths_recorded": death_count,
        "post_kill_started_at": starts,
        "kill_available": max(0, death_count - len(kill_named)),
        "kill_named": kill_named,
        "a5_occurrences_read": len(occurrences),
        "a5_occurrences_used": sorted(used_occurrences),
        "a5_possible_by_device": dict(sorted(a5_possible.items())),
        "deaths": death_records,
        "deaths_available": [death.index for death in available],
        "deaths_explaining_nothing": explains_nothing,
        "possible_sources": dict(sorted(possible.items())),
        "named_sources": dict(sorted(named_sources.items())),
    }
    return N1Naming(named, r3, r4, candidates, notes, cannot, dict(sorted(undecided.items())), sources)


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
    candidate that can be shown neither way (E-7, E-8) is neither: with no
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
    rules = ("P-4", "E-4", "E-7", "E-8")
    if naming.r3:
        reason = f"{len(naming.r3)} identity(ies) with only duplicate lines and no named N1 case"
        return (
            Criterion("S4", False, dict(evidence), rules, reason),
            Criterion("R3", True, dict(evidence), rules, reason),
        )
    if naming.cannot_show:
        reason = (
            f"{len(naming.cannot_show)} identity(ies) with only duplicate lines that can be "
            "shown neither named nor R3: " + "; ".join(sorted({c["why_not_shown"] for c in naming.cannot_show}))
        )
        return (
            Criterion("S4", None, dict(evidence), rules, reason),
            Criterion("R3", None, dict(evidence), rules, reason),
        )
    return (
        Criterion("S4", True, dict(evidence), rules),
        Criterion("R3", False, dict(evidence), rules),
    )


def _twin_figures(
    facts: Surplus, run_id: str, named_cases: int, applied_seqs: list[int]
) -> tuple[list[str], str | None, int | None]:
    """One device's S5 problems and P-5 regression under a given naming:
    ``named_cases`` N1 cases named on it and ``applied_seqs`` the seqs the
    run applied there (its accepted lines' and the named cases'). The
    runbook's `delta` rule with E-2's tolerance: the count, this run's
    last_run_id with the highest applied seq as last_seq when the run
    applied on the device, the device's own problems of absence."""
    expected = max(applied_seqs) if applied_seqs else None
    problems = list(facts.problems)
    if facts.delta is not None:
        if facts.delta != facts.accepted_lines + named_cases:
            problems.append(
                f"accepted_count advanced by {facts.delta} against {facts.accepted_lines} "
                f"accepted line(s) and {named_cases} named N1 case(s)"
            )
        if expected is not None and (facts.after_last_run_id != run_id or facts.after_last_seq != expected):
            problems.append(
                f"last_run_id {facts.after_last_run_id!r} last_seq {facts.after_last_seq} "
                f"against this run's highest applied seq {expected}"
            )
    regressed = None
    if facts.after_last_seq is not None:
        if facts.after_last_run_id == run_id and expected is not None and facts.after_last_seq < expected:
            regressed = f"last_seq {facts.after_last_seq} is below the run's highest applied seq {expected}"
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
    return problems, regressed, expected


def _namings_of_undecided(
    facts: Surplus,
    run_id: str,
    named_cases: int,
    applied_seqs: list[int],
    undecided_seqs: list[int | None],
) -> list[dict[str, Any]]:
    """E-9: every naming of a device's undecided candidates that the
    twin's count allows, each with the figures it would leave. The count
    fixes how many would be named (delta equals the accepted lines plus
    the cases named); the highest seq among them is what the twin's
    last_seq must then show, so one naming per possible highest seq is
    tried (a candidate without a seq adds none). Empty when no naming fits
    the count."""
    if facts.delta is None:
        return []
    count = facts.delta - facts.accepted_lines - named_cases
    if count < 0 or count > len(undecided_seqs):
        return []
    known = sorted(s for s in undecided_seqs if s is not None)
    without_seq = len(undecided_seqs) - len(known)
    tops: list[int | None] = []
    if count == 0 or without_seq >= count:
        tops.append(None)
    if count > 0:
        for seq in known:
            # `seq` is the highest of a naming of `count` candidates when
            # at least count - 1 others carry a seq not above it, or none.
            if seq not in tops and bisect.bisect_right(known, seq) + without_seq >= count:
                tops.append(seq)
    namings: list[dict[str, Any]] = []
    for top in tops:
        seqs = applied_seqs + ([top] if top is not None else [])
        problems, regressed, expected = _twin_figures(facts, run_id, named_cases + count, seqs)
        namings.append(
            {
                "named_cases": count,
                "highest_named_seq": top,
                "expected_last_seq": expected,
                "problems": problems,
                "regressed": regressed,
                "delta_ok": not problems and regressed is None,
            }
        )
    return namings


def _source_matching(
    demands: dict[str, int], members: dict[str, list[str]], options: dict[str, list[str]]
) -> int:
    """E-10's matching: the most candidates the sources can serve, each
    device ``d`` contributing at most ``demands[d]`` of its ``members[d]``,
    each candidate served by one of its ``options`` (the sources that may
    have preceded its redelivery) and each source serving one candidate.
    A maximum flow over device -> candidate -> source, by augmenting
    paths; the counts are small. Every device's count is served when the
    result equals the sum of the demands."""
    source_node, sink = ("s",), ("t",)
    graph: dict[tuple[str, ...], dict[tuple[str, ...], int]] = {source_node: {}, sink: {}}

    def _edge(u: tuple[str, ...], v: tuple[str, ...], capacity: int) -> None:
        graph.setdefault(u, {})
        graph.setdefault(v, {})
        graph[u][v] = graph[u].get(v, 0) + capacity
        graph[v].setdefault(u, 0)

    for device, demand in demands.items():
        if demand <= 0:
            continue
        _edge(source_node, ("d", device), demand)
        for message_id in members.get(device, []):
            _edge(("d", device), ("c", message_id), 1)
            for option in options.get(message_id, []):
                _edge(("c", message_id), ("x", option), 1)
    for node in [node for node in graph if node[0] == "x"]:
        _edge(node, sink, 1)

    def _augment(node: tuple[str, ...], seen: set[tuple[str, ...]]) -> bool:
        if node == sink:
            return True
        seen.add(node)
        for nxt in sorted(graph[node]):
            if graph[node][nxt] > 0 and nxt not in seen and _augment(nxt, seen):
                graph[node][nxt] -= 1
                graph[nxt][node] += 1
                return True
        return False

    flow = 0
    while _augment(source_node, set()):
        flow += 1
    return flow


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
    verified or unreadable) both are null (E-7). A device that is undecided
    (its tolerance depends on a duplicate-only case that can be shown
    neither way: E-7 over the controller log, E-8, E-4) is read under E-9:
    null while some naming of its undecided candidates that the count
    allows leaves the figures right, a mismatch or regression that stands
    under every one otherwise, on the twin's evidence, which was read; and
    the namings of every undecided device together must fit the sources
    the run evidences (E-10): when they cannot, R4 is observed on the
    aggregate, no one device or identity named as the mismatch."""
    if surplus is None:
        why = cannot or "a twin snapshot is missing"
        evidence = {"devices": [], "note": f"no delta can be computed: {why}"}
        return (
            Criterion("S5", None, dict(evidence), ("E-2", "E-7"), why),
            Criterion("R4", None, dict(evidence), ("P-5", "E-2", "E-7"), why),
        )
    seq_of = {candidate["message_id"]: candidate["seq"] for candidate in naming.cannot_show}
    devices: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    undecided: list[dict[str, Any]] = []
    stands: list[str] = []
    undecided_rules: set[str] = set()
    #: The undecided devices whose count some naming explains: (device, the
    #: cases that naming needs, the row), for the capacity check (E-10).
    pending: list[tuple[str, int, dict[str, Any]]] = []
    for device in sorted(surplus):
        facts = surplus[device]
        cases = named_on(naming.named, device)
        applied = [s for s in (facts.max_seq_accepted, *(case["seq"] for case in cases)) if s is not None]
        problems, regressed, expected_last_seq = _twin_figures(facts, run_id, len(cases), applied)
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
        undecided_here = naming.undecided_devices.get(device)
        if undecided_here is not None:
            # E-9: the figures are shown as read, with the case unnamed.
            # Nothing is decided on them while some naming of the unshown
            # candidates that the count allows would leave them right; a
            # mismatch or regression that no naming removes was read from
            # the twin whatever the candidates were.
            ids = list(undecided_here["message_ids"])
            namings = _namings_of_undecided(facts, run_id, len(cases), applied, [seq_of.get(m) for m in ids])
            explained = any(n["delta_ok"] for n in namings)
            undecided_rules.add(undecided_here["rule"])
            row["undecided"] = {**undecided_here, "namings_tried": namings, "explained": explained}
            if explained:
                row["ok"] = None
                devices.append(row)
                undecided.append({"device_uuid": device, **undecided_here})
                pending.append((device, facts.delta - facts.accepted_lines - len(cases), row))
                continue
            note = (
                f"no naming of the device's {len(ids)} undecided candidate(s) ({', '.join(ids)}) "
                "leaves `delta` right: "
                + ("the count fits none" if not namings else "each naming tried leaves a problem or a regression")
                + "; the problems are stated with the candidate(s) unnamed, and each naming tried "
                "is listed with what it would leave (E-9)"
            )
            row["undecided"]["note"] = note
            stands.append(device)
            devices.append(row)
            if problems:
                mismatches.append(
                    {
                        "device_uuid": device,
                        "problems": problems,
                        "undecided_candidates": ids,
                        "namings_tried": namings,
                        "note": note,
                    }
                )
            if regressed is not None:
                regressions.append(
                    {"device_uuid": device, "regressed": regressed, "undecided_candidates": ids, "note": note}
                )
            continue
        devices.append(row)
        if problems:
            mismatches.append({"device_uuid": device, "problems": problems})
        if regressed is not None:
            regressions.append({"device_uuid": device, "regressed": regressed})
    # E-10: the namings that explain each undecided device's count must,
    # together, fit the sources the run evidences, each source serving what
    # it can and only a candidate whose redelivery it may have preceded: an
    # A5 occurrence a candidate of its own device alone, a death at most
    # one candidate of the whole run. The check is a matching of the
    # candidates each device's count requires to those sources, beside the
    # cases named with an occurrence on those devices, each of which keeps
    # a source there: which occurrence served which case is inference, so
    # a named case may leave its occurrence to an undecided candidate and
    # take another source that may have preceded it. With the log unusable
    # the capacity is unknown and nothing is decided on it.
    sources = naming.sources
    possible = sources.get("possible_sources") or {}
    named_sources = sources.get("named_sources") or {}
    members = {device: list(row["undecided"]["message_ids"]) for device, _count, row in pending}
    named_here = {
        device: sorted(m for m, entry in named_sources.items() if entry.get("device_uuid") == device)
        for device in members
    }
    sources_of = {
        **{m: possible.get(m) or {} for ids in members.values() for m in ids},
        **{m: named_sources[m] for ids in named_here.values() for m in ids},
    }
    a5_options = {m: [f"A5 line {line}" for line in entry.get("a5_lines", [])] for m, entry in sources_of.items()}
    all_options = {
        m: a5_options[m] + [f"death {index}" for index in entry.get("deaths", [])]
        for m, entry in sources_of.items()
    }

    def _served(devices: list[str], counts: dict[str, int], options: dict[str, list[str]]) -> int:
        """The most of the devices' needed cases the sources serve while
        every case named with an occurrence on them keeps one: each named
        case is a group of its own that needs one source, and the naming
        itself serves them all, so a maximum matching keeps every one of
        them served and the rest of its size is the needed cases'."""
        demands: dict[str, int] = {}
        groups: dict[str, list[str]] = {}
        for device in devices:
            demands[device] = counts[device]
            groups[device] = members[device]
            for m in named_here[device]:
                demands["named case " + m] = 1
                groups["named case " + m] = [m]
        return _source_matching(demands, groups, options) - sum(len(named_here[d]) for d in devices)

    a5_possible = {
        device: list((sources.get("a5_possible_by_device") or {}).get(device, []))
        for device, _count, _row in pending
    }
    needed_by_device = {device: count for device, count, _row in pending}
    # The cases a device needs beyond what its own occurrences can serve,
    # each occurrence only a candidate it may precede, beside the cases it
    # names: only a death can serve them.
    beyond_a5 = {
        device: count - _served([device], needed_by_device, a5_options)
        for device, count in needed_by_device.items()
    }
    capacity_evidence: dict[str, Any] = {
        "applied": bool(pending) and bool(sources.get("known")),
        "known": bool(sources.get("known")),
        "why_unknown": sources.get("why_unknown"),
        "deaths_recorded": sources.get("deaths_recorded"),
        "post_kill_started_at": sources.get("post_kill_started_at"),
        "kill_available": sources.get("kill_available"),
        "a5_possible_by_device": a5_possible,
        "needed_by_device": needed_by_device,
        "needed": sum(needed_by_device.values()) if pending else None,
        "beyond_a5_by_device": beyond_a5,
        "kill_needed": sum(beyond_a5.values()) if pending else None,
        "consistent": None,
        "matched": None,
        "deaths": sources.get("deaths"),
        "possible_sources": {
            **{m: possible.get(m) for ids in members.values() for m in sorted(ids)},
            **{
                m: {
                    "a5_lines": named_sources[m]["a5_lines"],
                    "deaths": named_sources[m]["deaths"],
                    "named": {"source": "a3-connection-end", "controller_log_line": named_sources[m]["named_with_line"]},
                }
                for ids in named_here.values() for m in ids
            },
        },
        "deaths_preceding_none": [],
        "rule": (
            "an A5 occurrence serves a candidate of its own device alone; a recorded death "
            "serves at most one candidate of the whole run; each serves only a candidate whose "
            "redelivered duplicate line it may have preceded on the controller clock, a death "
            "placed as E-4 states; a case named with an occurrence on an undecided device keeps "
            "one source in the matching, any occurrence of its device or, when nothing read "
            "excludes it from the kill, any death that may have preceded its redelivery (E-10)"
        ),
    }
    on_sources: dict[str, Any] | None = None
    late: list[int] = []
    if capacity_evidence["applied"]:
        kill_needed = int(capacity_evidence["kill_needed"])
        kill_available = int(sources.get("kill_available") or 0)
        matched = _served(list(needed_by_device), needed_by_device, all_options)
        consistent = matched == sum(needed_by_device.values())
        capacity_evidence["matched"] = matched
        capacity_evidence["consistent"] = consistent
        for device, _count, row in pending:
            # A device whose own occurrences cover its count is explained
            # whatever the deaths served; one that needs a death is
            # consistent only when the deaths serve every such device.
            row["undecided"]["source_consistent"] = beyond_a5[device] == 0 or consistent
        if not consistent:
            competing = [device for device, _count, _row in pending if beyond_a5[device] > 0]
            # A device that no matching of its own candidates serves, even
            # with every death available to it, is the mismatch by itself,
            # whatever the deaths served elsewhere; otherwise only the
            # aggregate is established.
            on_own = [
                device for device in competing
                if _served([device], needed_by_device, all_options) < needed_by_device[device]
            ]
            ids = sorted(m for device in competing for m in members[device])
            # The available deaths that may have preceded none of these
            # candidates' redeliveries, nor those of the cases named with an
            # occurrence beside them, explain none of them (E-4).
            late = [
                index for index in sources.get("deaths_available") or []
                if not any(
                    index in (sources_of[m].get("deaths") or [])
                    for m in ids + [n for device in competing for n in named_here[device]]
                )
            ]
            capacity_evidence["deaths_preceding_none"] = late
            order = (
                f", {len(late)} of which may have preceded none of their redelivered duplicate lines "
                "on the controller clock"
                if late
                else ", which their order against the redeliveries cannot assign to them"
                if kill_needed <= kill_available
                else ""
            )
            on_sources = {
                "device_uuid": on_own[0] if len(on_own) == 1 else None,
                "devices": competing,
                "stands_on": on_own,
                "problems": [
                    f"the undecided device(s) {', '.join(competing)} need {kill_needed} N1 case(s) "
                    "beyond the named ones that no A5 occurrence on their own device can serve "
                    f"({', '.join(f'{device}: {beyond_a5[device]}' for device in competing)}), "
                    f"against {kill_available} recorded death(s) available{order}, each serving at most "
                    "one candidate of the whole run and only one whose redelivery it may have "
                    "preceded: no source-consistent naming explains the twins"
                ],
                "undecided_candidates": ids,
                "note": (
                    (
                        f"the mismatch stands on {', '.join(on_own)} by itself, whatever the death(s) "
                        "served, since no matching of its own candidates to the sources that may "
                        "have preceded them serves its count, even with every recorded death; "
                        if on_own
                        else
                        "which device's figures are the mismatch cannot be told when more than one "
                        "needs a death, so "
                    )
                    + "no identity is named as the case and none as the mismatch; each device's "
                    "figures are shown as read, with the namings its count alone would allow (E-10)"
                ),
            }
            mismatches.append(on_sources)
    evidence = {
        "devices": devices,
        "mismatches": mismatches,
        "last_seq_regressions": regressions,
        "undecided": undecided,
        "surplus_unexplained": naming.r4_unexplained,
        "source_capacity": capacity_evidence,
        "note": (
            "the /metrics counters of `delta` are not compared: they restart from zero "
            "with the controller process"
        ),
    }
    reason = None
    if mismatches or regressions:
        parts = []
        per_device = len(mismatches) - (1 if on_sources is not None else 0)
        if per_device:
            parts.append(f"{per_device} device(s) with a delta mismatch beyond the named cases")
        if regressions:
            parts.append(f"{len(regressions)} device(s) whose last_seq regressed")
        if stands:
            parts.append(
                f"{len(stands)} of them under every naming of its unshown duplicate-only "
                "candidate(s) (E-9)"
            )
        if on_sources is not None:
            parts.append(
                f"{len(on_sources['devices'])} undecided device(s) whose twins need "
                f"{capacity_evidence['kill_needed']} N1 case(s) that only a death could serve "
                "(no A5 occurrence on their own device can), against "
                f"{capacity_evidence['kill_available']} recorded death(s)"
                + (
                    f", {len(late)} of which may have preceded none of their redeliveries"
                    if late
                    else ""
                )
                + ": a delta mismatch beyond the named cases stands on "
                + (
                    f"{', '.join(on_sources['stands_on'])} whatever the death(s) served"
                    if on_sources["stands_on"]
                    else "at least one of them, which cannot be told"
                )
                + " (E-10)"
            )
        reason = "; ".join(parts)
    observed = bool(mismatches or regressions)
    extra = ("E-9", "E-10", *sorted(undecided_rules)) if undecided_rules else ()
    if not observed and undecided:
        reason = (
            f"{len(undecided)} device(s) whose delta tolerance depends on a duplicate-only "
            "identity that can be shown neither named nor R3: "
            + "; ".join(f"{u['device_uuid']}: {u['why']}" for u in undecided)
        )
        return (
            Criterion("S5", None, dict(evidence), ("E-2", *extra), reason),
            Criterion("R4", None, dict(evidence), ("P-5", "E-2", *extra), reason),
        )
    return (
        Criterion("S5", not observed, dict(evidence), ("E-2", *extra), reason),
        Criterion("R4", observed, dict(evidence), ("P-5", "E-2", *extra), reason),
    )


def r1_missing_after_drain(
    valid: dict[str, Sent], lines: dict[str, list[dict[str, Any]]], drain: dict[str, Any] | None
) -> Criterion:
    """R1 only after a completed drain: the manifest's drain record
    verified by the harness (the helper's own quiet line, read and checked)
    with outcome 'quiet', never the outcome string alone. A drain that gave
    up, is not verified or has no record leaves the missing lines to the
    inconclusive rule (a refutation rests on verified evidence, E-7)."""
    drain = drain if isinstance(drain, dict) else {}
    outcome = drain.get("outcome")
    verified = drain.get("verified")
    completed = verified is True and outcome == "quiet"
    missing = _sorted_ids([m for m in valid if not lines.get(m)], valid)
    evidence = {
        "drain_outcome": outcome,
        "drain_verified": verified,
        "drain_completed": completed,
        "without_outcome_line": len(missing),
        "without_outcome_line_ids": missing,
    }
    if not completed:
        why = f"no completed drain (drain outcome {outcome!r}"
        if outcome == "quiet":
            why += f", verified {verified!r}: a quiet outcome the harness did not verify is not a completed drain"
        return Criterion("R1", None, evidence, ("P-7", "E-7"), why + "): R1 cannot be observed")
    reason = None if not missing else f"{len(missing)} published valid identity(ies) without an outcome line after a completed drain"
    return Criterion("R1", bool(missing), evidence, ("P-7", "E-7"), reason)


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
    post-drain copy, the twin snapshots, the controller log) to why (E-7)."""

    complete: bool
    present: dict[str, bool]
    missing: list[str]
    fetch_failures: list[str]
    drain: dict[str, Any]
    unusable: dict[str, str] = field(default_factory=dict)
    #: What the inventory accepts in E-12's sampling-gap form in place of a
    #: record it otherwise requires, each with its reason stated.
    accepted: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "present": self.present,
            "missing": self.missing,
            "fetch_failures": self.fetch_failures,
            "drain": self.drain,
            "cannot_serve_the_criteria": dict(sorted(self.unusable.items())),
            "accepted_in_the_sampling_gap_form": self.accepted,
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
    run_id: str | None = None,
    admission: dict[str, Any] | None = None,
) -> EvidenceStatus:
    """Whether the proof's evidence is complete, every absence named: the
    manifest's item-18 records (both snapshots verified, the drain verified
    and quiet or gave-up, the post-drain copy fetched and verified, the
    three SUT logs fetched with their files), the harness copy of the
    events with its fetch recorded ok (item 3's first copy), the collector
    file from the SUT collector (item 5), the configuration identity with
    W, a readable pre-kill reading and the seal; the simulator's own
    manifest is inventoried (E-11 reads it) and never a failed fetch by its
    absence. ``read_problems`` are the loader's (a file present but
    unreadable): each is a failed fetch of that file, since nothing of it
    can be read. When ``admission`` (E-12) is the sampling-gap form, the
    collector file is required where the harness's rejection names it
    instead of resources.csv, and the seal the harness withheld for the
    missing resources.csv alone is accepted with the reason stated; a seal
    present that does not verify is never accepted."""
    read_problems = list(read_problems or [])
    missing: list[str] = []
    failures: list[str] = []
    accepted: list[str] = []
    unusable: dict[str, str] = {}
    logs = "logs/" + SUT_LOG_SUBDIR
    run_id = str(run_id or manifest.get("run_id") or "")
    gap_form = isinstance(admission, dict) and admission.get("form") == ADMISSION_SAMPLING_GAP_ONLY
    rejected_file = admission.get("collector_file") if gap_form else None

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
        COLLECTOR_FILENAME,
        CONFIG_IDENTITY_FILENAME,
        *(f"{logs}/{name}" for name in SUT_LOG_FILES.values()),
        simulator_manifest_rel(run_id),
        SUMS_FILENAME,
    ]
    if isinstance(rejected_file, str) and rejected_file not in watched:
        watched.append(rejected_file)
    present = {rel: rel in files_present for rel in watched}

    # Item 3's first copy: the harness fetch of events.jsonl, recorded by
    # the harness (events_fetch); a readable file beside a failed or
    # unrecorded fetch is not the copy (a stale file, or the local fallback).
    fetch = manifest.get("events_fetch")
    timed = "events.jsonl"
    if not isinstance(fetch, dict):
        missing.append(
            f"{timed}: no harness fetch record (events_fetch, --fetch-events-cmd): the "
            "harness copy of the events is not shown fetched"
        )
    elif fetch.get("ok") is not True:
        failures.append(
            f"{timed}: the harness fetch failed after {len(fetch.get('attempts') or [])} attempt(s)"
            + (": the readable file beside it is not the copy" if present[timed] else "")
        )
    elif not present[timed]:
        missing.append(f"{timed}: recorded as fetched but absent from the run directory")
    elif _read_problem(timed) is not None:
        failures.append(_read_problem(timed))

    # Item 5's collector file, from the SUT collector; in E-12's sampling-gap
    # form, the file the harness rejected, where its rejection names it.
    if gap_form:
        if not isinstance(rejected_file, str) or not present.get(rejected_file):
            missing.append(
                f"{rejected_file}: absent (the collector file, item 5 of 'What it records', which "
                "the harness's ingest rejected under MAX_SAMPLE_GAP_S and keeps where its "
                "rejection names it, E-12)"
            )
        else:
            accepted.append(
                f"{COLLECTOR_FILENAME}: absent from the top of the run directory, as run.py leaves it "
                "when its ingest rejects the collector file under MAX_SAMPLE_GAP_S alone; the "
                f"collector file is required at {rejected_file}, where the rejection names it, and "
                "is present (E-12)"
            )
    elif not present[COLLECTOR_FILENAME]:
        missing.append(f"{COLLECTOR_FILENAME}: absent (the collector file, item 5 of 'What it records')")
    elif manifest.get("resource_source") != SUT_COLLECTOR_SOURCE:
        failures.append(
            f"{COLLECTOR_FILENAME}: resource_source {manifest.get('resource_source')!r}, not the SUT "
            f"collector's ({SUT_COLLECTOR_SOURCE!r})"
        )

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
        problem = None
        if record is None:
            missing.append(f"{rel}: no fetch record ({SUT_LOG_FETCH_FLAGS[hook]})")
            problem = missing[-1]
        elif record.get("returncode") != 0 or not record.get("dest_exists"):
            failures.append(
                f"{rel}: the fetch {SUT_LOG_FETCH_FLAGS[hook]} {_record_outcome(record)} and "
                + ("wrote its file" if record.get("dest_exists") else "wrote no file")
            )
            problem = failures[-1]
        elif not present[rel]:
            missing.append(f"{rel}: recorded as fetched but absent from the run directory")
            problem = missing[-1]
        elif _read_problem(rel) is not None:
            failures.append(_read_problem(rel))
            problem = failures[-1]
        if problem is not None and hook == "controller_log":
            # Only the controller log serves a criterion (the A5 occurrences
            # of S4/R3, E-7); the broker log and docker events are fetched
            # evidence the proof reports and never reads for a criterion.
            _cannot_serve(rel, problem)

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
    if integrity == INTEGRITY_UNSEALED and gap_form and admission.get("seal_withheld_for"):
        accepted.append(
            f"{SUMS_FILENAME}: absent, withheld by the harness for "
            f"{admission.get('seal_withheld_for')} (E-12); the evaluator's own sha256 of every file "
            "it read, in the document's sources, carries the integrity of what it used"
        )
    elif integrity == INTEGRITY_UNSEALED:
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
        accepted=accepted,
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


def restart_shown_of(session: dict[str, Any] | None) -> bool | None:
    """Whether the driver showed the restart, as the session facts record
    it: True, False, or None when the facts are absent or carry no boolean
    (unknown, never false: P-6)."""
    if session is None:
        return None
    shown = session.get("restart_shown")
    return shown if isinstance(shown, bool) else None


@dataclass
class Eligibility:
    """Whether the run is the prescribed execution with its records (E-11):
    ``eligible`` False when a requirement fails, None when a required fact
    is unknown (the restart shown, P-6) and nothing fails, True otherwise;
    every failed requirement in ``reasons``, every unknown one in
    ``unknown``, what was read in ``checks``."""

    eligible: bool | None
    reasons: list[str]
    unknown: list[str]
    checks: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": IDENTIFICATION_RULES["E-11"],
            "eligible": self.eligible,
            "reasons": self.reasons,
            "unknown": self.unknown,
            "checks": self.checks,
            "note": (
                "the harness's validity is quoted and admitted only as E-12 states ('valid', or "
                "the campaign's MAX_SAMPLE_GAP_S deviation in the one form the harness records "
                "it, which the ADR names as not touching the proof; checks.harness_admission); "
                "E-11 states what else the proof requires; a run that is not eligible is "
                "inconclusive, never 'supports', and a refutation observed on evidence that "
                "was read and verified stands (P-7)"
            ),
        }


def _same_number(value: Any, expected: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and float(value) == float(expected)
    )


def proof_eligibility(
    manifest: dict[str, Any],
    run_id: str,
    sent: SentIndex,
    skipped_sent: int,
    simulator_manifest: dict[str, Any] | None,
    sim_problem: str | None,
    evidence: EvidenceStatus,
    session: dict[str, Any] | None,
    admission: dict[str, Any] | None = None,
) -> Eligibility:
    """E-11: the harness's validity admitted (E-12, ``admission``: not
    admitted is not eligible, unknown or absent is unknown); the prescribed
    load and fault of the manifest's entry with the simulator exited 0; the
    publication completed and the population whole, on the simulator's own
    manifest (or, without it, the file's count against the plan's, with no
    tolerance); the fault at the plan's instant and demonstrated (the
    restart record and the session facts' restart_shown); and the evidence
    complete. Every failed requirement is named; an absent required fact
    is unknown, never read as satisfied."""
    reasons: list[str] = []
    unknown: list[str] = []
    checks: dict[str, Any] = {}

    # The load and fault of the plan, as the manifest's entry records them.
    wrong: list[str] = []
    for key, expected in PROOF_LOAD.items():
        value = manifest.get(key)
        ok = value == expected if isinstance(expected, str) else _same_number(value, expected)
        if not ok:
            wrong.append(f"{key} {value!r} (the plan's: {expected!r})")
    checks["load"] = {
        "read": {key: manifest.get(key) for key in PROOF_LOAD},
        "prescribed": dict(PROOF_LOAD),
        "ok": not wrong,
    }
    if wrong:
        reasons.append("load: the manifest's entry is not the diagnostic plan's: " + "; ".join(wrong))

    # The publication: the simulator exited 0 and, on its own manifest, ran
    # its schedule to the end and published what the copy holds.
    returncode = manifest.get("simulator_returncode")
    sim_exit_ok = _is_int(returncode) and returncode == 0
    checks["simulator_returncode"] = returncode
    if not sim_exit_ok:
        reasons.append(
            f"publication: the simulator did not exit 0 (simulator_returncode {returncode!r}): "
            "the publication is not shown completed"
        )

    # The population record: every line of this run read as one record.
    this_run = len(sent.valid) + len(sent.intended_invalid)
    unreliable: list[str] = []
    if skipped_sent:
        unreliable.append(f"{skipped_sent} line(s) skipped (not a JSON object or not UTF-8, E-5)")
    if sent.malformed:
        unreliable.append(f"{sent.malformed} record(s) of this run without a message_id")
    if sent.repeated:
        unreliable.append(f"{sent.repeated} record(s) repeating a message_id")
    if sent.other_run_id:
        unreliable.append(f"{sent.other_run_id} record(s) of another run")
    checks["population"] = {
        "records_of_this_run": this_run,
        "valid": len(sent.valid),
        "intended_invalid": len(sent.intended_invalid),
        "skipped_lines": skipped_sent,
        "malformed": sent.malformed,
        "repeated": sent.repeated,
        "other_run_id": sent.other_run_id,
        "reliable": not unreliable,
    }
    if unreliable:
        reasons.append(
            "population: sent_events.jsonl is not a reliable record of what was published, and "
            "a smaller denominator is never read from it: " + "; ".join(unreliable)
        )

    sim_rel = simulator_manifest_rel(run_id)
    sim = simulator_manifest if isinstance(simulator_manifest, dict) else None
    if sim is not None:
        totals = sim.get("totals") if isinstance(sim.get("totals"), dict) else {}
        rates = sim.get("rates_hz") if isinstance(sim.get("rates_hz"), dict) else {}
        declared = totals.get("sent")
        problems: list[str] = []
        if sim.get("run_id") != run_id:
            problems.append(f"its run_id is {sim.get('run_id')!r}")
        if sim.get("scenario") != PROOF_LOAD["scenario"]:
            problems.append(f"its scenario is {sim.get('scenario')!r}")
        if not _same_number(sim.get("duration_s"), PROOF_LOAD["duration_s"]):
            problems.append(f"its duration_s is {sim.get('duration_s')!r}")
        if not _same_number(rates.get("aggregate"), PROOF_LOAD["rate_msg_s"]):
            problems.append(f"its rates_hz.aggregate is {rates.get('aggregate')!r}")
        if sim.get("completed") is not True:
            problems.append(f"completed is {sim.get('completed')!r}: the schedule did not run to its end")
        if not _is_int(declared):
            problems.append(f"totals.sent {declared!r} is not an integer")
        elif declared != this_run:
            problems.append(
                f"totals.sent {declared} against {this_run} record(s) of this run in "
                "sent_events.jsonl: the copy is not whole"
            )
        checks["publication"] = {
            "source": "the simulator's own manifest",
            "file": sim_rel,
            "read": {
                "run_id": sim.get("run_id"),
                "scenario": sim.get("scenario"),
                "duration_s": sim.get("duration_s"),
                "aggregate_rate_hz": rates.get("aggregate"),
                "completed": sim.get("completed"),
                "totals_sent": declared,
            },
            "expected_from_plan": PROOF_EXPECTED_MESSAGES,
            "ok": not problems,
        }
        if problems:
            reasons.append(
                "publication: the simulator's manifest does not show the prescribed publication "
                "completed and whole: " + "; ".join(problems)
            )
    else:
        count_ok = this_run == PROOF_EXPECTED_MESSAGES
        checks["publication"] = {
            "source": (
                "sent_events.jsonl's count of this run's records against the plan's "
                "(the simulator's manifest is absent or unreadable)"
            ),
            "file": sim_rel,
            "problem": sim_problem,
            "records_of_this_run": this_run,
            "expected_from_plan": PROOF_EXPECTED_MESSAGES,
            "ok": count_ok and not unreliable,
        }
        if not count_ok:
            reasons.append(
                f"publication: the simulator's manifest ({sim_rel}) is absent or unreadable"
                + (f" ({sim_problem})" if sim_problem else "")
                + f", so the only count is sent_events.jsonl's: {this_run} record(s) of this run "
                f"against the plan's {PROOF_EXPECTED_MESSAGES} (300 s x 11.2 msg/s), with no tolerance"
            )

    # The fault demonstrated: the manifest's record and the driver's facts.
    restart = manifest.get("restart") if isinstance(manifest.get("restart"), dict) else {}
    restart_ok = (
        restart.get("executed") is True
        and _is_int(restart.get("returncode"))
        and restart.get("returncode") == 0
    )
    shown = restart_shown_of(session)
    requested_at = restart.get("requested_at_s")
    at_the_instant = _same_number(requested_at, PROOF_RESTART_AT_S)
    checks["fault"] = {
        "restart_executed": restart.get("executed"),
        "restart_returncode": restart.get("returncode"),
        "restart_ok": restart_ok,
        "restart_requested_at_s": requested_at,
        "prescribed_at_s": PROOF_RESTART_AT_S,
        "at_the_prescribed_instant": at_the_instant,
        "restart_shown": shown,
        "session_facts_present": session is not None,
    }
    if not at_the_instant:
        reasons.append(
            f"fault: the manifest's restart was requested at {requested_at!r} s "
            f"(restart.requested_at_s), not at the plan's t+{PROOF_RESTART_AT_S} s (ADR 0011: "
            f"'fault | at t+{PROOF_RESTART_AT_S} s'): the prescribed fault instant is not shown"
        )
    if not restart_ok:
        reasons.append(
            f"fault: the manifest's restart did not execute with exit 0 (executed "
            f"{restart.get('executed')!r}, returncode {restart.get('returncode')!r}): the fault "
            "is not demonstrated"
        )
    if shown is None:
        unknown.append(
            "fault: whether the restart was shown is unknown: "
            + (
                "no session facts (proof_session.json) were given"
                if session is None
                else "the session facts carry no restart_shown (null)"
            )
            + " (P-6)"
        )
    elif shown is False:
        reasons.append(
            "fault: the session facts record the restart as not shown (restart_shown false): "
            "the fault was not applied"
        )

    # The harness's validity, admitted only as E-12 states.
    checks["harness_admission"] = admission
    admitted = admission.get("admitted") if isinstance(admission, dict) else None
    if admitted is False:
        reasons.append(
            f"harness validity: not admitted for the proof (E-12, form {admission.get('form')!r}): "
            + " | ".join(admission.get("reasons") or [])
        )
    elif admitted is not True:
        unknown.append(
            "harness validity: whether it is admitted for the proof is unknown (E-12, P-6): "
            + (
                " | ".join(admission.get("reasons") or [])
                if isinstance(admission, dict)
                else "no admission was read"
            )
        )

    # The records of 'What it records', as the evidence inventory names them.
    checks["evidence_complete"] = evidence.complete
    if not evidence.complete:
        reasons.append(
            "records: the proof's evidence is not complete (see proof_evidence): "
            + "; ".join(evidence.missing + evidence.fetch_failures)
        )
    eligible: bool | None = False if reasons else (None if unknown else True)
    return Eligibility(eligible, reasons, unknown, checks)


def inconclusive_reasons(
    evidence: EvidenceStatus,
    criteria: dict[str, Criterion],
    drain_outcome: str | None,
    session: dict[str, Any] | None,
    failed_only: list[dict[str, Any]],
    r_any: bool,
    eligibility: Eligibility | None = None,
) -> list[str]:
    """The ADR's five conditions, in its order, plus the evaluator's own
    (P-2, P-6, E-3, E-7, E-8, E-11, E-12), each stated with what was read. A
    criterion of S2 to S5 that is null is always named here (E-7, E-8 when
    the band or the command's window is the ground, E-4 when a claimant
    stands beside a further death on evidence that was read), so a run that is inconclusive for that
    cause never goes without a stated reason; a run that is not eligible
    is named with every failed requirement (the evidence ones under "any
    fetch listed above fails")."""
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
    if eligibility is not None:
        reasons.extend(eligibility.unknown)
        named_apart = [why for why in eligibility.reasons if not why.startswith("records:")]
        if named_apart:
            reasons.append("not eligible (E-11): " + " | ".join(named_apart))
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
        # The rule that leaves the criteria unshown: E-8 (a band or window
        # placement), E-7 (evidence not read, and the default when the reason
        # names no rule: a copy, snapshot or log that cannot serve), or E-4
        # (a claimant beside a further death or an unshown candidate, on
        # evidence that was read) - never E-7 for what was read.
        label = next((rule for rule in ("E-8", "E-7", "E-4") if f"({rule})" in why), "E-7")
        reasons.append(f"{', '.join(rule_ids)} cannot be shown ({label}): {why}")
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
    # E-12: the harness's validity admitted for the proof, on the same facts
    # of the run directory harness_admission reads for the driver.
    admission = admission_of(manifest, artefacts.files_present, artefacts.empty_files, artefacts.integrity)
    evidence = evidence_status(
        manifest,
        artefacts.files_present,
        artefacts.integrity,
        len(split.pre_kill),
        config_problems,
        artefacts.problems,
        run_id=run_id,
        admission=admission,
    )
    # E-7: the post-drain copy serves the criteria only when it was fetched,
    # verified as this run's and read; the twins only when both snapshots
    # were; the controller log's A5 occurrences only when its fetch was
    # recorded ok and the file was read. Otherwise what depends on them is
    # null, never a refutation.
    post_problem = evidence.unusable.get(POST_DRAIN_EVENTS_FILENAME)
    if post_problem is None and artefacts.events_post_drain is None:
        post_problem = f"{POST_DRAIN_EVENTS_FILENAME}: not read"
    twins_problem = next(
        (evidence.unusable[f] for f in TWIN_SNAPSHOT_FILES.values() if f in evidence.unusable), None
    )
    if twins_problem is None and (artefacts.twins_before is None or artefacts.twins_after is None):
        twins_problem = "a twin snapshot was not read"
    post_copy_usable = post_problem is None
    log_rel = f"logs/{SUT_LOG_SUBDIR}/{SUT_LOG_FILES['controller_log']}"
    log_problem = evidence.unusable.get(log_rel)
    if log_problem is None and artefacts.controller_log is None:
        log_problem = f"{log_rel}: not read"

    sent = valid_identities(artefacts.sent_events, run_id)
    # E-11: the run is evaluated on the prescribed execution and its
    # records, or it is not eligible (inconclusive, never support).
    sim_rel = simulator_manifest_rel(run_id)
    sim_problem = next((p for p in artefacts.problems if p.startswith(sim_rel)), None)
    if sim_problem is None and artefacts.simulator_manifest is None and evidence.present.get(sim_rel):
        sim_problem = f"{sim_rel}: not read"
    eligibility = proof_eligibility(
        manifest,
        run_id,
        sent,
        artefacts.skipped_lines.get("sent_events.jsonl", 0),
        artefacts.simulator_manifest,
        sim_problem,
        evidence,
        session,
        admission,
    )
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
        sent.valid,
        post.by_id,
        surplus,
        occurrences if log_problem is None else [],
        classification,
        restart,
        twins_problem,
        log_problem,
        split.post_started_ats,
        recorded_deaths(split, restart.get("executed") is True and restart.get("returncode") == 0),
    )

    s1 = s1_kill_found_work(split.pre_kill, restart, manifest.get("controller_marker"))
    s6 = s6_window(rows, w)
    if post_copy_usable:
        s2 = s2_outcome_lines(sent.valid, post.by_id, classification, naming.named_ids)
        s3, r2 = s3_r2_double_accepted(post.by_id, sent.valid)
        s4, r3 = s4_r3_duplicates(naming)
        r1 = r1_missing_after_drain(sent.valid, post.by_id, drain)
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
    reasons = inconclusive_reasons(evidence, criteria, drain_outcome, session, failed_only, r_any, eligibility)
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
            "harness_admission": admission,
            "harness_condition_id": manifest.get("condition_id"),
            "seal": artefacts.integrity,
            "seal_problems": artefacts.integrity_problems,
            "proof_evidence": evidence.as_dict(),
            "proof_eligibility": eligibility.as_dict(),
            "drain_text_outcome": drain_text_outcome,
            "skipped_lines": dict(sorted(artefacts.skipped_lines.items())),
            "controller_log_non_json_lines": log_notes["non_json_lines"],
            "read_problems": artefacts.problems,
            "read_notes": artefacts.notes,
            "metrics_notes": row_notes,
            "configuration_identity_problems": config_problems,
            "note": (
                "the harness verdict belongs to the campaign rules and is kept as recorded "
                "(ADR 0011, what the proof cannot show); it is admitted for the proof only as "
                "E-12 states (harness_admission: 'valid', or the campaign's MAX_SAMPLE_GAP_S "
                "deviation in the one form the harness records it), and the proof's other "
                "requirements are checked apart (proof_evidence, proof_eligibility)"
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
                    "controller_log_usable": log_problem is None,
                    "controller_log_problem": log_problem,
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
                "(ADR 0011, what the proof cannot show); the proof was not evaluated, so "
                "nothing was admitted or decided"
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
    admission = instrumentation.get("harness_admission")
    line += (
        f"; harness validity {instrumentation.get('harness_validity')!r} kept as recorded"
        + (
            f" (admission {admission.get('form')!r}, E-12)"
            if isinstance(admission, dict)
            else ""
        )
        + f"; seal {instrumentation.get('seal')}"
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
