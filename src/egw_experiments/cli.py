"""Command-line interface of the experiment harness.

Subcommands (plan 5.8/9.1 'Reprodutibilidade'; audit 2026-08-08 section 9)::

    python -m egw_experiments plan --master-seed 42 [--output PATH] [--force]
    python -m egw_experiments campaign [--plan PATH] [--results-dir DIR] ...
    python -m egw_experiments run --run-id nominal-r01 [--plan PATH] ...
    python -m egw_experiments collect --run-id nominal-r01 [...]
    python -m egw_experiments analyze [--base-dir PATH] [--plan PATH]
    python -m egw_experiments verify-checksums [--base-dir PATH] [--run-id ID]

``plan`` writes the fully enumerated deterministic campaign plan;
``campaign`` (work order P1 item 12) is the OFFICIAL way to execute the
frozen plan end-to-end: it iterates the plan in its frozen order, runs
every simulator condition through the same code path as ``run``, skips
runs already sealed and valid (resume), prints an operator checklist for
external conditions and appends one JSONL line per run to
``<results-dir>/campaign_log.jsonl``. ``run``
executes exactly one planned run from the harness host, OFF the ARM VM
(plan 5.1: the simulator never runs on the VM during benchmarks;
``--broker`` is the VM's address, port 8883 with TLS). After the 60 s
confirmation window the runner collects the controller's ``events.jsonl``
AUTOMATICALLY via ``--fetch-events-cmd`` (or env ``EGW_FETCH_EVENTS_CMD``),
a command template with ``{run_id}`` and ``{dest}`` placeholders, retried
3 times with backoff; without a template it falls back to the local
event-log directory (dev only). External conditions (QEMU boots, cold
starts, twin creations) are ingested with ``--external-timings``.
``collect`` is the recovery path: it re-attempts events/resources/SUT
environment collection for an EXISTING run directory and (re)writes
SHA256SUMS only after successful collection.

Sprint P5 additions (report 5.3/5.4): ``run`` and ``campaign`` accept the
SUT collector hooks ``--collector-start-cmd`` / ``--collector-stop-cmd`` /
``--collector-fetch-cmd`` (executed before the warm-up, after the measured
run and after the confirmation window respectively), so a fresh campaign
produces its own ``resources.csv`` instead of requiring a pre-fetched one.
The collector's output — fetched by the hook or given with
``--resources-from`` to ``run``, ``campaign`` or ``collect`` — is accounted
for per service (``--expect-services``), companion file and collector
identity before the run directory is sealed;
``--allow-missing-controller-marker`` authorizes a timed run whose end was
not stamped in the controller's clock domain; ``campaign`` verifies the
SHA256SUMS of every sealed run before skipping it on resume and exits 1
when a full campaign still has external runs pending. ``analyze`` regenerates
everything under ``results/processed`` and ``results/figures`` from
``results/raw``; ``verify-checksums`` re-verifies the SHA256SUMS of raw
run directories (evidence integrity, plan 5.8).

Sprint P5.4: ``analyze`` takes ``--plan`` with the SAME default as
``run``/``campaign``/``collect``, so the frozen campaign plan is used
automatically whenever it exists. With a plan the acceptance completeness
criterion compares the exact SET of run identities (``run_id`` +
``repetition`` + ``seed`` + ``rate_msg_s``) against the plan instead of
merely counting runs; without one it degrades — with a loud warning — to
the count-only check, which cannot detect a duplicated, re-seeded,
mis-rated or swapped run. A plan path that does not exist (or cannot be
read) degrades the same way and never fails the analysis. The
``EGW_CAMPAIGN_PLAN`` environment variable is the documented fallback used
when ``--plan`` names nothing readable.

ADR 0011 item 18: ``run`` and ``campaign`` accept the SUT log fetches
``--fetch-broker-log-cmd`` / ``--fetch-controller-log-cmd`` /
``--fetch-docker-events-cmd`` (run after the events fetch, into
``logs/sut/``), the restart-evidence steps ``--twin-snapshot-cmd`` /
``--drain-cmd`` / ``--post-drain-fetch-cmd`` (applied to ``controller_restart``
runs only, as ``--restart-cmd`` is) and, with ``collect``,
``--config-identity-from`` (copied into the run directory as
``configuration_identity.json`` and embedded in the manifest) and the
ingestion of the restart evidence taken outside the harness,
``--twins-before-from`` / ``--twins-after-from`` /
``--post-drain-events-from`` / ``--drain-transcript-from`` (each file
verified against the run before it counts, copied write-once and recorded
with its provenance). A failed fetch or snapshot is a validity reason, like
a failed collector hook; the drain's outcome is recorded (quiet, gave-up or
error) and only 'error' is a reason; a ``controller_restart`` run without
its configuration identity, or without its restart evidence, is invalid —
no flag excuses the evidence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyze import CAMPAIGN_PLAN_ENV_VAR, analyze
from .campaign import run_campaign
from .checksums import verify_sha256sums
from .plan_gen import generate_campaign_plan, write_campaign_plan
from .run import (
    DEFAULT_PLAN_PATH,
    DEFAULT_RESULTS_BASE,
    FETCH_EVENTS_CMD_ENV,
    SUT_ENV_FILE_ENV,
    collect_run,
    execute_run,
    parse_expected_services,
)


def _add_collection_arguments(
    parser: argparse.ArgumentParser, *, resources_template: bool = False
) -> None:
    """Arguments shared by ``run``, ``collect`` and ``campaign``
    (audit 9.1-9.3). With ``resources_template`` (campaign) the
    ``--resources-from`` value may contain a ``{run_id}`` placeholder
    substituted per run."""
    parser.add_argument(
        "--fetch-events-cmd",
        default=None,
        help="command template that fetches the controller's events.jsonl "
        "from the VM; {run_id} and {dest} are substituted, e.g. "
        "'scp vm:/opt/egw/data/events/{run_id}/events.jsonl \"{dest}\"'. "
        "Executed after the confirmation window with 3 attempts and "
        f"exponential backoff (default: env {FETCH_EVENTS_CMD_ENV}). "
        "Without it the runner falls back to the local --event-log-dir "
        "lookup (dev only)",
    )
    parser.add_argument(
        "--event-log-dir",
        default=None,
        help="local fallback directory holding the controller's "
        "events.jsonl when no --fetch-events-cmd is configured "
        "(default: EGW_EVENT_LOG_DIR env or ./data/events)",
    )
    parser.add_argument(
        "--sut-env-from",
        default=None,
        help="path of the sut_environment.json captured ON the ARM VM by "
        "deployment/scripts/capture-sut-environment.sh and fetched here "
        f"(default: env {SUT_ENV_FILE_ENV}). Timed runs without it are "
        "marked validity 'invalid'",
    )
    parser.add_argument(
        "--config-identity-from",
        default=None,
        help="path of the configuration identity captured ON the guest for "
        "this run (a JSON document: the broker configuration's sha256 and "
        "its window/queue/expiry values, the statement that no reload "
        "happened, stop_grace_period, the controller image's id and source "
        "commit, the paho version installed in it, the A3 choice; ADR 0011). "
        "Copied into the run directory as configuration_identity.json and "
        "embedded in the manifest under 'configuration_identity'. The "
        "document must be a JSON object with broker_conf_sha256 (64 hex), "
        "broker_conf_values (the six C1 options), broker_reloaded (boolean), "
        "stop_grace_period, controller_image_id (sha256:...), "
        "controller_source_commit, paho_version and a3_choice ('a' or 'b'); "
        "anything else is not an identity. A controller_restart run without "
        "it is marked validity 'invalid'"
        + (
            ". May contain a {run_id} placeholder substituted per run"
            if resources_template
            else ""
        ),
    )
    parser.add_argument(
        "--resources-from",
        default=None,
        help="path of the resources.csv produced ON the ARM VM by "
        "deployment/scripts/collect-resources.sh and fetched here, with "
        "the collector's companions beside it (<file>.diagnostics.log and "
        "<file>.lifecycle.csv, plus <file>.self-test if the collector wrote "
        "one; deployment/scripts/fetch-collector-output.sh fetches all of "
        "them). The file is content-validated before ingestion (exact "
        "ts_utc,container,cpu_pct,mem_bytes,mem_pct,host header; at least "
        "30 sample rows; every host value matching the sut_environment "
        "node/hostname); a rejected file is treated as missing. The file "
        "and its companions are copied into logs/collector/resources-from/ "
        "and accounted for like the fetch hook's output (a missing "
        "companion, a self-test marker, no --expect-services or an expected "
        "service without rows marks a timed run 'invalid'). Timed runs "
        "without SUT resources are marked validity 'invalid'"
        + (
            ". May contain a {run_id} placeholder substituted per run, "
            "e.g. 'fetched/resources-{run_id}.csv'"
            if resources_template
            else ""
        ),
    )
    parser.add_argument(
        "--expect-services",
        type=_expect_services_arg,
        default=None,
        metavar="NAME,NAME,...",
        help="the services (container names) the SUT collector must account "
        "for, e.g. 'egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,"
        "egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1'. Names use "
        "only A-Z a-z 0-9 _ . - (as in collect-resources.sh). Substituted "
        "into the collector hooks as {expect_services}, so the start hook "
        "passes the SAME list to the collector (--expect-services "
        "{expect_services}); give the collector the same list when it is "
        "started by hand. Each name must have rows in the collector's CSV "
        "(fetch hook or --resources-from) and must not be missing from its "
        "inventory; a timed run whose SUT resources come from the collector "
        "without this flag is marked validity 'invalid'. On 'collect' it "
        "supplies the list for a run that recorded none (never changes a "
        "recorded one) and requires --resources-from",
    )
    parser.add_argument(
        "--allow-missing-sut-env",
        action="store_true",
        help="deliberately accept a timed run without sut_environment.json; "
        "the decision is recorded in the manifest (audit 9.2)",
    )
    parser.add_argument(
        "--allow-missing-resources",
        action="store_true",
        help="deliberately accept a timed run without SUT resources; the "
        "decision is recorded in the manifest (audit 9.1)",
    )
    # Restart evidence taken outside the harness (ADR 0011 item 18): the
    # runbook's helpers take the snapshots, the drain and the post-drain copy
    # of the events; each file is verified against the run before it counts.
    per_run = (
        ". May contain a {run_id} placeholder substituted per run"
        if resources_template
        else ""
    )
    parser.add_argument(
        "--twins-before-from",
        default=None,
        metavar="FILE",
        help="a twin snapshot taken BEFORE the measured run outside the "
        "harness (itest_reconcile snap --label before), ingested as "
        "twins.before.json once verified: a JSON object whose label is "
        "'before', with a devices object, and whose seed (when not null) is "
        "the plan entry's. controller_restart runs only; mutually exclusive "
        "with --twin-snapshot-cmd" + per_run,
    )
    parser.add_argument(
        "--twins-after-from",
        default=None,
        metavar="FILE",
        help="the twin snapshot taken AFTER the drain outside the harness "
        "(label 'after'), ingested as twins.after.json once verified like "
        "--twins-before-from. Not required when the drain gave up. "
        "controller_restart runs only; mutually exclusive with "
        "--twin-snapshot-cmd" + per_run,
    )
    parser.add_argument(
        "--post-drain-events-from",
        default=None,
        metavar="FILE",
        help="the copy of the controller's events.jsonl fetched AFTER the "
        "drain outside the harness, ingested as events.post-drain.jsonl "
        "once verified: non-empty JSON Lines whose every record carries "
        "this run's run_id and an outcome of accepted/rejected/duplicate/"
        "failed (a file of another run is refused, naming the mismatch). "
        "Not required when the drain gave up. controller_restart runs only; "
        "mutually exclusive with --post-drain-fetch-cmd" + per_run,
    )
    parser.add_argument(
        "--drain-transcript-from",
        default=None,
        metavar="FILE",
        help="the transcript of the runbook's 'drained' helper run outside "
        "the harness (drained 2>&1 | tee FILE), ingested as "
        "logs/sut/drain.txt and classified as a hook's output would be: its "
        "quiet line ('drained: queue_depth 0 ...') gives drain.outcome "
        "'quiet', its give-up line ('STOP: drained: no quiet window ...') "
        "'gave-up' (a failed recovery, retained as a valid observation), "
        "anything else is refused as an instrument failure. "
        "controller_restart runs only; mutually exclusive with --drain-cmd"
        + per_run,
    )
    parser.add_argument(
        "--allow-missing-controller-marker",
        action="store_true",
        help="deliberately accept a timed run whose end instant was NOT "
        "stamped in the controller's clock domain (no --controller-url, or "
        "the controller could not be polled / predates the "
        "confirmation-marker contract). Without it such a run is marked "
        "validity 'invalid': the 60 s confirmation deadline would otherwise "
        "be derived from the events it judges (report 5.2). The decision is "
        "recorded as a protocol deviation and leaves the analysis on the "
        "legacy event-derived deadline",
    )


def _expect_services_arg(value: str) -> list[str]:
    """argparse type of ``--expect-services``: NAME,NAME,... -> list."""
    try:
        return parse_expected_services(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _add_collector_hook_arguments(parser: argparse.ArgumentParser) -> None:
    """SUT collector hooks shared by ``run`` and ``campaign`` (sprint P5,
    report 5.3: a fresh campaign must produce its own resources.csv instead
    of requiring one that already exists).

    Every template accepts the ``{run_id}``, ``{duration_s}`` (warm-up +
    measured window + confirmation window + margin), ``{dest}`` and
    ``{expect_services}`` placeholders; each hook's command, exit code,
    start/end timestamps and full output are recorded (``collector_hooks``
    in the manifest, ``logs/collector/hook-<hook>.*.txt``) and a non-zero
    exit marks the run validity 'invalid' naming the hook. The fetched
    output is then accounted for (manifest ``collector``): a missing
    companion, a self-test marker or an expected service without rows marks
    the run invalid as well. ``--expect-services`` is a collection argument
    (:func:`_add_collection_arguments`): the manual ``--resources-from``
    path is accounted for in the same way.
    """
    parser.add_argument(
        "--collector-start-cmd",
        default=None,
        help="command template started BEFORE the warm-up to launch the "
        "SUT-side resource collector, e.g. \"ssh vm 'systemd-run --unit "
        "egw-resources-{run_id} --collect sh "
        "/opt/egw/deployment/scripts/collect-resources.sh "
        "/tmp/resources-{run_id}.csv --duration {duration_s} "
        "--expect-services {expect_services}'\"",
    )
    parser.add_argument(
        "--collector-stop-cmd",
        default=None,
        help="command template executed AFTER the measured run and BEFORE "
        "the confirmation window to stop the collector, e.g. "
        "\"ssh vm 'systemctl stop egw-resources-{run_id}'\"",
    )
    parser.add_argument(
        "--collector-fetch-cmd",
        default=None,
        help="command template executed AFTER the confirmation window that "
        "must write the collector's CSV to {dest} and its companions beside "
        "it ({dest}.diagnostics.log and {dest}.lifecycle.csv, plus "
        "{dest}.self-test if the collector wrote one), e.g. 'sh "
        "<clone>/src/deployment/scripts/fetch-collector-output.sh vm "
        "/tmp/resources-{run_id}.csv \"{dest}\"' (quote \"{dest}\": the "
        "template is split without a shell). The fetched CSV goes through the "
        "same validated ingest as --resources-from (mutually exclusive with "
        "it); a missing companion invalidates the run",
    )


def _add_sut_log_fetch_arguments(parser: argparse.ArgumentParser) -> None:
    """SUT log fetches shared by ``run`` and ``campaign`` (ADR 0011 item 18).

    Each template runs through the collector-hook machinery (no shell, the
    same ``{run_id}``, ``{dest}``, ``{duration_s}`` and ``{expect_services}``
    placeholders, full output kept as ``logs/sut/hook-<hook>.*.txt``) after
    the harness events fetch — on ``controller_restart`` after the drain and
    the post-drain steps, so the logs cover them — and must write its file
    to ``{dest}`` under ``logs/sut/``. The record goes to the manifest
    (``sut_log_fetches``); a non-zero exit, or an exit 0 without the file,
    marks the run validity 'invalid' naming the flag.
    """
    parser.add_argument(
        "--fetch-broker-log-cmd",
        default=None,
        help="command template that writes the broker's log for the run to "
        "{dest} (logs/sut/broker.log), e.g. a helper running 'docker compose "
        "logs --no-color mosquitto' on the guest and copying its output; "
        "quote \"{dest}\" (the template is split without a shell)",
    )
    parser.add_argument(
        "--fetch-controller-log-cmd",
        default=None,
        help="command template that writes the controller container's log "
        "for the run to {dest} (logs/sut/controller.log)",
    )
    parser.add_argument(
        "--fetch-docker-events-cmd",
        default=None,
        help="command template that writes the container engine's events for "
        "the controller over the run to {dest} (logs/sut/docker-events.log)",
    )


def _add_run_level_arguments(parser: argparse.ArgumentParser) -> None:
    """Run-level flags shared by ``run`` and ``campaign`` (same wiring)."""
    parser.add_argument(
        "--broker",
        default="localhost",
        help="MQTT broker host: the ARM VM's address (the harness and the "
        "simulator run off the VM during benchmarks, plan 5.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8883, help="MQTT port (default 8883, TLS)"
    )
    parser.add_argument("--username", default=None, help="MQTT username")
    parser.add_argument("--password", default=None, help="MQTT password")
    parser.add_argument("--ca-cert", default=None, help="CA certificate path (TLS)")
    parser.add_argument(
        "--no-tls",
        action="store_true",
        help="disable TLS; allowed only against localhost and never in "
        "benchmarks (CONTRACTS 1)",
    )
    parser.add_argument("--qos", type=int, default=1, help="MQTT QoS (default 1)")
    parser.add_argument(
        "--egw-id", default=None, help="gateway id (default: EGW_ID env or egw-01)"
    )
    parser.add_argument(
        "--post-run-wait",
        type=float,
        default=None,
        help="seconds to wait after the run for late confirmations "
        "(default: the 60 s confirmation window of plan 7.3)",
    )
    parser.add_argument(
        "--allow-warmup-failure",
        action="store_true",
        help="keep a timed run valid when the warm-up subprocess exits "
        "non-zero; the decision is recorded as a protocol deviation in the "
        "manifest (without this flag the run is marked validity 'invalid')",
    )
    parser.add_argument(
        "--allow-protocol-deviation",
        action="store_true",
        help="authorize an explicit protocol deviation (currently: "
        "--skip-warmup on nominal/load_sweep/soak); the deviation is "
        "recorded in the manifest (without this flag such a run is marked "
        "validity 'invalid')",
    )
    parser.add_argument(
        "--controller-url",
        default=None,
        help="controller base URL for 1 Hz GET /metrics sampling into "
        "controller_metrics.csv (queue growth, audit 9.7). Port 8000 is "
        "loopback-only on the VM: open an SSH tunnel first, e.g. "
        "'ssh -N -L 8000:127.0.0.1:8000 <vm>' then use "
        "http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--restart-cmd",
        default=None,
        help="command template ({run_id} placeholder) executed exactly once "
        "mid-run for the controller_restart condition (claim C12), e.g. "
        "'ssh vm docker compose -f /opt/egw/compose.yaml restart "
        "controller'; recorded in the manifest with timestamps. The "
        "campaign subcommand applies it ONLY to controller_restart runs",
    )
    parser.add_argument(
        "--restart-at-s",
        type=float,
        default=None,
        help="offset in seconds into the measured run at which "
        "--restart-cmd fires (default: half the run duration)",
    )
    # Restart evidence (ADR 0011 item 18): applied to controller_restart runs
    # only, as --restart-cmd is; every failure is a validity reason.
    parser.add_argument(
        "--twin-snapshot-cmd",
        default=None,
        help="command template that writes a snapshot of the run's twins to "
        "{dest}, executed once BEFORE the measured run (twins.before.json) "
        "and once AFTER the drain (twins.after.json), e.g. a helper running "
        "'itest_reconcile snap' against the guest; recorded in the manifest "
        "(twin_snapshots). controller_restart runs only",
    )
    parser.add_argument(
        "--drain-cmd",
        default=None,
        help="BLOCKING command template ({run_id} placeholder) executed after "
        "the confirmation window and the events fetch, returning once the "
        "controller has been quiet for the runbook's window (the 'drained' "
        "helper) or exiting non-zero when it gives up; recorded in the "
        "manifest (drain). controller_restart runs only",
    )
    parser.add_argument(
        "--post-drain-fetch-cmd",
        default=None,
        help="command template ({run_id}, {dest}) that fetches the "
        "controller's events.jsonl AFTER the drain into {dest} "
        "(events.post-drain.jsonl, kept apart from the harness copy "
        "events.jsonl); same retries as --fetch-events-cmd; recorded in the "
        "manifest (events_post_drain_fetch). controller_restart runs only",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="egw_experiments",
        description="EGW experiment harness: plan, run, collect, analyze, verify.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # plan ------------------------------------------------------------------
    p_plan = sub.add_parser(
        "plan", help="generate the deterministic campaign_plan.json"
    )
    p_plan.add_argument(
        "--master-seed",
        type=int,
        required=True,
        help="campaign master seed; the same seed always yields the same plan",
    )
    p_plan.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"output path (default: {DEFAULT_PLAN_PATH})",
    )
    p_plan.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing plan (statuses in it are lost)",
    )

    # run -------------------------------------------------------------------
    p_run = sub.add_parser(
        "run",
        help="execute one planned run from the harness host, OFF the ARM VM "
        "(plan 5.1): --broker is the VM's address (port 8883, TLS). Events "
        "are collected automatically via --fetch-events-cmd; SUT "
        "environment and resources are ingested via --sut-env-from / "
        "--resources-from; external conditions via --external-timings",
    )
    p_run.add_argument("--run-id", required=True, help="run_id from the plan")
    p_run.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"campaign plan path (default: {DEFAULT_PLAN_PATH})",
    )
    p_run.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )
    _add_run_level_arguments(p_run)
    p_run.add_argument(
        "--skip-warmup",
        action="store_true",
        help="skip the planned warm-up. Recorded as a protocol deviation; "
        "on nominal/load_sweep/soak the run is marked validity 'invalid' "
        "unless --allow-protocol-deviation is also given",
    )
    p_run.add_argument(
        "--skip-cooldown",
        action="store_true",
        help="skip the planned cooldown (recorded as a protocol deviation "
        "when the condition prescribes one)",
    )
    _add_collection_arguments(p_run)
    _add_collector_hook_arguments(p_run)
    _add_sut_log_fetch_arguments(p_run)
    p_run.add_argument(
        "--local-resources",
        action="store_true",
        help="DEV ONLY: sample docker stats on THIS host (the load "
        "generator, NOT the SUT) into resources.csv; mutually exclusive "
        "with --resources-from; recorded as resource_source 'local-dev'",
    )
    p_run.add_argument(
        "--external-timings",
        default=None,
        help="operator-produced timings.json for external conditions "
        "(qemu_boots, cold_start, twin_creation): {run_id, condition, "
        "samples:[{label, started_utc, ended_utc, duration_s}], method, "
        "notes}; see deployment/scripts/measure-cold-start.sh",
    )
    p_run.add_argument(
        "--external-logs",
        default=None,
        help="optional directory of operator logs copied into the external "
        "run's logs/ directory",
    )

    # campaign (batch runner, work order P1 item 12) --------------------------
    p_camp = sub.add_parser(
        "campaign",
        help="execute the frozen campaign plan end-to-end IN PLAN ORDER: "
        "the OFFICIAL way to run the campaign. Simulator conditions run "
        "through the same code path as 'run'; sealed+valid runs are "
        "skipped (resume); external conditions print an operator "
        "checklist; one JSONL line per run is appended to "
        "<results-dir>/campaign_log.jsonl",
    )
    p_camp.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"campaign plan path (default: {DEFAULT_PLAN_PATH})",
    )
    p_camp.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE}); "
        "runs land in <results-dir>/raw/<run_id>/ and the batch log in "
        "<results-dir>/campaign_log.jsonl",
    )
    p_camp.add_argument(
        "--only-conditions",
        default=None,
        help="comma-separated condition ids to execute (e.g. "
        "'smoke_sequence,nominal'); the frozen plan order among them is "
        "preserved",
    )
    p_camp.add_argument(
        "--start-from",
        default=None,
        help="skip every run BEFORE this run_id in the plan order (resume "
        "an interrupted campaign; sealed+valid runs are skipped anyway)",
    )
    p_camp.add_argument(
        "--dry-run",
        action="store_true",
        help="print the ordered execution table (including skips and "
        "external checklists) without executing anything",
    )
    p_camp.add_argument(
        "--continue-on-invalid",
        action="store_true",
        help="record an invalid/failed/blocked run in campaign_log.jsonl "
        "and move on instead of stopping at it (the exit code still "
        "reports the failure)",
    )
    p_camp.add_argument(
        "--no-cooldown",
        action="store_true",
        help="skip the plan's cooldown_s between runs; recorded as a "
        "protocol deviation (kind cooldown_skipped_before_run) in the "
        "manifest of the FOLLOWING executed run",
    )
    _add_run_level_arguments(p_camp)
    _add_collection_arguments(p_camp, resources_template=True)
    _add_collector_hook_arguments(p_camp)
    _add_sut_log_fetch_arguments(p_camp)

    # collect (recovery, audit 9.3) ------------------------------------------
    p_col = sub.add_parser(
        "collect",
        help="re-attempt events/resources/SUT-environment collection for an "
        "EXISTING run directory and (re)write SHA256SUMS after successful "
        "collection (recovery path; raw evidence is never overwritten)",
    )
    p_col.add_argument("--run-id", required=True, help="existing raw run_id")
    p_col.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"campaign plan path (default: {DEFAULT_PLAN_PATH})",
    )
    p_col.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )
    _add_collection_arguments(p_col)

    # analyze ---------------------------------------------------------------
    p_an = sub.add_parser(
        "analyze",
        help="regenerate processed/ and figures/ from raw/ (single script)",
    )
    p_an.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )
    p_an.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"campaign plan path (default: {DEFAULT_PLAN_PATH}), used for "
        "IDENTITY-based run completeness: the acceptance criterion compares "
        "the exact set of run identities (run_id + repetition + seed + "
        "rate_msg_s) against the plan instead of only counting runs, so a "
        "duplicated, re-seeded, mis-rated or swapped run is detected. When "
        "this path does not exist (or cannot be read) the analysis degrades "
        "to the count-only check with a loud warning and still succeeds; the "
        f"{CAMPAIGN_PLAN_ENV_VAR} environment variable is the documented "
        "fallback consulted when the default plan is absent",
    )

    # verify-checksums ------------------------------------------------------
    p_ver = sub.add_parser(
        "verify-checksums", help="verify SHA256SUMS of raw run directories"
    )
    p_ver.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"results base directory (default: {DEFAULT_RESULTS_BASE})",
    )
    p_ver.add_argument(
        "--run-id", default=None, help="verify only this run directory"
    )

    return parser


def _cmd_plan(args: argparse.Namespace) -> int:
    output: Path = args.output
    if output.exists() and not args.force:
        print(
            f"error: {output} already exists; it contains run statuses. "
            "Use --force to overwrite deliberately.",
            file=sys.stderr,
        )
        return 2
    plan = generate_campaign_plan(args.master_seed)
    write_campaign_plan(plan, output)
    print(
        f"wrote {output} (protocol {plan['protocol_version']}, "
        f"master seed {plan['master_seed']}, {len(plan['runs'])} runs)"
    )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    return execute_run(
        args.plan,
        args.run_id,
        base_dir=args.base_dir,
        broker=args.broker,
        port=args.port,
        username=args.username,
        password=args.password,
        ca_cert=args.ca_cert,
        no_tls=args.no_tls,
        qos=args.qos,
        egw_id=args.egw_id,
        event_log_dir=args.event_log_dir,
        post_run_wait_s=args.post_run_wait,
        skip_warmup=args.skip_warmup,
        skip_cooldown=args.skip_cooldown,
        fetch_events_cmd=args.fetch_events_cmd,
        sut_env_from=args.sut_env_from,
        resources_from=args.resources_from,
        local_resources=args.local_resources,
        allow_missing_sut_env=args.allow_missing_sut_env,
        allow_missing_resources=args.allow_missing_resources,
        allow_warmup_failure=args.allow_warmup_failure,
        allow_protocol_deviation=args.allow_protocol_deviation,
        allow_missing_controller_marker=args.allow_missing_controller_marker,
        controller_url=args.controller_url,
        restart_cmd=args.restart_cmd,
        restart_at_s=args.restart_at_s,
        collector_start_cmd=args.collector_start_cmd,
        collector_stop_cmd=args.collector_stop_cmd,
        collector_fetch_cmd=args.collector_fetch_cmd,
        expect_services=args.expect_services,
        fetch_broker_log_cmd=args.fetch_broker_log_cmd,
        fetch_controller_log_cmd=args.fetch_controller_log_cmd,
        fetch_docker_events_cmd=args.fetch_docker_events_cmd,
        twin_snapshot_cmd=args.twin_snapshot_cmd,
        drain_cmd=args.drain_cmd,
        post_drain_fetch_cmd=args.post_drain_fetch_cmd,
        twins_before_from=args.twins_before_from,
        twins_after_from=args.twins_after_from,
        post_drain_events_from=args.post_drain_events_from,
        drain_transcript_from=args.drain_transcript_from,
        config_identity_from=args.config_identity_from,
        external_timings=args.external_timings,
        external_logs=args.external_logs,
    )


def _cmd_campaign(args: argparse.Namespace) -> int:
    only_conditions = None
    if args.only_conditions:
        only_conditions = [
            c.strip() for c in args.only_conditions.split(",") if c.strip()
        ]
        if not only_conditions:
            print(
                "error: --only-conditions given but names no condition",
                file=sys.stderr,
            )
            return 2
    return run_campaign(
        args.plan,
        results_dir=args.results_dir,
        only_conditions=only_conditions,
        start_from=args.start_from,
        dry_run=args.dry_run,
        continue_on_invalid=args.continue_on_invalid,
        no_cooldown=args.no_cooldown,
        broker=args.broker,
        port=args.port,
        username=args.username,
        password=args.password,
        ca_cert=args.ca_cert,
        no_tls=args.no_tls,
        qos=args.qos,
        egw_id=args.egw_id,
        event_log_dir=args.event_log_dir,
        post_run_wait_s=args.post_run_wait,
        fetch_events_cmd=args.fetch_events_cmd,
        sut_env_from=args.sut_env_from,
        resources_from=args.resources_from,
        controller_url=args.controller_url,
        restart_cmd=args.restart_cmd,
        restart_at_s=args.restart_at_s,
        collector_start_cmd=args.collector_start_cmd,
        collector_stop_cmd=args.collector_stop_cmd,
        collector_fetch_cmd=args.collector_fetch_cmd,
        expect_services=args.expect_services,
        fetch_broker_log_cmd=args.fetch_broker_log_cmd,
        fetch_controller_log_cmd=args.fetch_controller_log_cmd,
        fetch_docker_events_cmd=args.fetch_docker_events_cmd,
        twin_snapshot_cmd=args.twin_snapshot_cmd,
        drain_cmd=args.drain_cmd,
        post_drain_fetch_cmd=args.post_drain_fetch_cmd,
        twins_before_from=args.twins_before_from,
        twins_after_from=args.twins_after_from,
        post_drain_events_from=args.post_drain_events_from,
        drain_transcript_from=args.drain_transcript_from,
        config_identity_from=args.config_identity_from,
        allow_missing_sut_env=args.allow_missing_sut_env,
        allow_missing_resources=args.allow_missing_resources,
        allow_warmup_failure=args.allow_warmup_failure,
        allow_protocol_deviation=args.allow_protocol_deviation,
        allow_missing_controller_marker=args.allow_missing_controller_marker,
    )


def _cmd_collect(args: argparse.Namespace) -> int:
    return collect_run(
        args.run_id,
        base_dir=args.base_dir,
        plan_path=args.plan,
        fetch_events_cmd=args.fetch_events_cmd,
        event_log_dir=args.event_log_dir,
        sut_env_from=args.sut_env_from,
        resources_from=args.resources_from,
        allow_missing_sut_env=args.allow_missing_sut_env,
        allow_missing_resources=args.allow_missing_resources,
        allow_missing_controller_marker=args.allow_missing_controller_marker,
        expect_services=args.expect_services,
        config_identity_from=args.config_identity_from,
        twins_before_from=args.twins_before_from,
        twins_after_from=args.twins_after_from,
        post_drain_events_from=args.post_drain_events_from,
        drain_transcript_from=args.drain_transcript_from,
    )


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Run the analysis with the campaign plan wired in (sprint P5.4).

    ``--plan`` defaults to the frozen plan, so identity-based completeness
    is the DEFAULT behaviour of the shipped command. An explicitly named
    plan is forwarded verbatim — if it cannot be read, ``analyze()`` says so
    loudly and degrades to the count-only check. The DEFAULT path merely
    being absent (a tree analyzed before the plan is frozen) is not an
    operator error: the plan is then left unset so ``analyze()`` applies its
    documented ``EGW_CAMPAIGN_PLAN`` fallback and, failing that, warns that
    completeness is checked BY COUNT ONLY.
    """
    plan_path: Path | None = args.plan
    if (
        plan_path is not None
        and Path(plan_path) == Path(DEFAULT_PLAN_PATH)
        and not Path(plan_path).exists()
    ):
        plan_path = None
    return analyze(base_dir=args.base_dir, plan_path=plan_path)


def _cmd_verify(args: argparse.Namespace) -> int:
    base = args.base_dir if args.base_dir is not None else DEFAULT_RESULTS_BASE
    raw_dir = Path(base) / "raw"
    if not raw_dir.is_dir():
        print(f"error: {raw_dir} does not exist", file=sys.stderr)
        return 2

    if args.run_id is not None:
        run_dirs = [raw_dir / args.run_id]
        if not run_dirs[0].is_dir():
            print(f"error: {run_dirs[0]} does not exist", file=sys.stderr)
            return 2
    else:
        run_dirs = sorted(p for p in raw_dir.iterdir() if p.is_dir())

    if not run_dirs:
        print(f"no run directories under {raw_dir}")
        return 0

    failures = 0
    for run_dir in run_dirs:
        problems = verify_sha256sums(run_dir)
        if problems:
            failures += 1
            print(f"FAIL {run_dir.name}")
            for problem in problems:
                print(f"  {problem}")
        else:
            print(f"OK   {run_dir.name}")

    if failures:
        print(f"{failures} of {len(run_dirs)} run directories failed verification")
        return 1
    print(f"all {len(run_dirs)} run directories verified")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        return _cmd_plan(args)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "campaign":
        return _cmd_campaign(args)
    if args.command == "collect":
        return _cmd_collect(args)
    if args.command == "analyze":
        return _cmd_analyze(args)
    if args.command == "verify-checksums":
        return _cmd_verify(args)
    raise AssertionError(f"unhandled command {args.command!r}")
