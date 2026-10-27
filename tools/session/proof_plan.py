"""Write the one-entry diagnostic plan of the finite proof of ADR 0011.

Usage: proof_plan.py write --run-id RID --master-seed N --out PATH [--pilot-plan PATH]

The harness accepts only a run id that is in the plan it is given
(``egw_experiments.run.execute_run`` refuses any other, exit 2), and the
finite proof is "a fresh run id recorded as a diagnostic, in a one-entry
diagnostic plan of its own ... never an edit of the pilot plan" (ADR 0011,
"The finite proof"). This helper writes that plan and nothing else: the
pilot plan is read, when it is named, only to refuse a run id it already
holds, and it is never written.

The entry is built by ``plan_gen._run_entry`` and ``derive_run_seed``, the
functions that enumerate the campaign plan, so its shape cannot drift from
what the harness reads (``scenario``, ``seed``, ``duration_s``,
``rate_msg_s``, ``warmup_s``, ``cooldown_s``, ``condition_id``, ``runner``).
Its condition is ``controller_restart``: the harness runs the twin-snapshot,
drain and post-drain hooks and applies the restart-evidence validity rules
on that condition only, and the frozen condition already is the ``nominal``
scenario with no warm-up and no cool-down. Its load is the proof's: 11.2
msg/s and 300 s of publication instead of the frozen condition's 600 s. The
condition record carried beside the entry states the same figures and is
annotated as the proof's diagnostic in its ``notes``; the frozen protocol
(``protocol.py``) is not touched, and the harness reads the entry, never the
condition record.

Refused, with nothing written (exit 2): a run id outside the charset of
CONTRACTS 2, one the campaign plan enumerates (its run ids do not depend on
the master seed, so this needs no pilot plan file), or one present in the
pilot plan named by ``--pilot-plan`` - a pilot plan that cannot be read is
refused too, because that the id is absent from it cannot then be
established; a master seed that is not a whole number; an output file that
already exists (the plan is write-once, as every record of a session is).
The plan is written with the campaign plan's canonical serialisation, so
the same run id and master seed always give a byte-identical file, and the
one line printed names the file, the entry and the file's sha256 for the
driver to record.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import replace
from pathlib import Path

from egw_experiments.plan_gen import (
    PLAN_VERSION,
    RUN_ID_RE,
    _run_entry,
    generate_campaign_plan,
    load_campaign_plan,
    plan_to_json,
)
from egw_experiments.protocol import CONDITIONS_BY_ID, PROTOCOL_VERSION

USAGE = "proof_plan.py write --run-id RID --master-seed N --out PATH [--pilot-plan PATH]"

#: The proof's condition and load (ADR 0011, "The finite proof": "the
#: `nominal` scenario at 11.2 msg/s, three wearables, no warm-up, 300 s of
#: publication"; the fault is issued through the harness restart hook, which
#: the harness records with its evidence on the controller_restart condition).
PROOF_CONDITION_ID = "controller_restart"
PROOF_DURATION_S = 300
PROOF_RATE_MSG_S = 11.2
PROOF_REPETITION = 1

#: The annotation the condition record carries in its ``notes``: what this
#: plan is, and what it departs from.
DIAGNOSTIC_NOTE = (
    "diagnostic: duration_s 300 for the finite proof (ADR 0011). One run of the "
    "controller_restart condition's load - the nominal scenario at 11.2 msg/s, "
    "no warm-up, no cool-down - with 300 s of publication instead of the frozen "
    "condition's 600 s and one repetition instead of three; an engineering "
    "diagnostic, not a G3 run, and never an entry of the pilot plan."
)

WHOLE_NUMBER = re.compile(r"[0-9]+")


def campaign_run_ids() -> set[str]:
    """The run ids the campaign plan enumerates, for every master seed.

    The ids are fixed by the frozen conditions (only the load sweep's ORDER
    depends on the seed), so a run id the pilot plan would hold is known
    without the pilot plan file.
    """
    return {entry["run_id"] for entry in generate_campaign_plan(0)["runs"]}


def pilot_run_ids(path: Path) -> set[str]:
    """The run ids of the pilot plan at ``path``, read through the harness's
    own loader; raises when the file does not hold a plan's ``runs`` list."""
    plan = load_campaign_plan(path)
    runs = plan.get("runs") if isinstance(plan, dict) else None
    if not isinstance(runs, list) or not all(isinstance(entry, dict) for entry in runs):
        raise ValueError("the file holds no 'runs' list of entries")
    return {entry.get("run_id") for entry in runs}


def build_plan(run_id: str, master_seed: int) -> dict:
    """The one-entry plan: the campaign plan's shape, one condition, one run.

    The entry is ``plan_gen._run_entry`` of the proof's condition, so it
    differs from a campaign entry of ``controller_restart`` only in the
    figures the proof sets (``duration_s`` 300); ``order`` is 1 as the
    campaign generator numbers its runs.
    """
    condition = replace(
        CONDITIONS_BY_ID[PROOF_CONDITION_ID],
        repetitions=PROOF_REPETITION,
        duration_s=PROOF_DURATION_S,
        rate_msg_s=PROOF_RATE_MSG_S,
        notes=DIAGNOSTIC_NOTE,
    )
    entry = _run_entry(condition, run_id, PROOF_REPETITION, master_seed, PROOF_RATE_MSG_S)
    entry["order"] = 1
    return {
        "plan_version": PLAN_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "master_seed": master_seed,
        "conditions": [condition.to_dict()],
        "runs": [entry],
    }


def refusal(run_id: str, master_seed: str, out: Path, pilot_plan: Path | None) -> str | None:
    """Why nothing is written, or None when the plan may be written."""
    if not RUN_ID_RE.match(run_id):
        return (f"the run id {run_id!r} is outside the charset of CONTRACTS 2 "
                f"({RUN_ID_RE.pattern})")
    if run_id in campaign_run_ids():
        return (f"the run id {run_id!r} is one the campaign plan enumerates, for every "
                "master seed: the proof needs a fresh run id of its own")
    if not WHOLE_NUMBER.fullmatch(master_seed):
        return f"the master seed {master_seed!r} is not a whole number"
    if pilot_plan is not None:
        try:
            held = pilot_run_ids(pilot_plan)
        except (OSError, ValueError) as exc:
            return (f"the pilot plan {pilot_plan} could not be read ({exc}): that "
                    f"{run_id!r} is absent from it cannot be established")
        if run_id in held:
            return (f"the run id {run_id!r} is in the pilot plan {pilot_plan}: the proof "
                    "is never an entry of the pilot plan")
    if out.exists():
        return f"{out} exists: the plan is write-once and is not replaced"
    return None


def write_plan(plan: dict, out: Path) -> str:
    """Write ``plan`` to ``out`` once, canonically; the sha256 of what was
    written. An ``out`` that came to exist meanwhile raises FileExistsError."""
    text = plan_to_json(plan)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="proof_plan.py", usage=USAGE)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", usage=USAGE, help="write the one-entry diagnostic plan")
    write.add_argument("--run-id", required=True, help="a fresh run id, never used on the guest")
    write.add_argument("--master-seed", required=True, help="a whole number")
    write.add_argument("--out", required=True, type=Path, help="the plan file (write-once)")
    write.add_argument("--pilot-plan", type=Path, default=None,
                       help="the pilot plan whose run ids are refused (read only)")
    args = parser.parse_args(argv)
    reason = refusal(args.run_id, args.master_seed, args.out, args.pilot_plan)
    if reason is not None:
        print(f"STOP: proof_plan: {reason}; nothing was written", file=sys.stderr)
        return 2
    plan = build_plan(args.run_id, int(args.master_seed))
    try:
        digest = write_plan(plan, args.out)
    except OSError as exc:
        print(f"STOP: proof_plan: {args.out} was not written ({exc})", file=sys.stderr)
        return 2
    entry = plan["runs"][0]
    print(f"wrote {args.out}: run_id={entry['run_id']} condition_id={entry['condition_id']} "
          f"scenario={entry['scenario']} duration_s={entry['duration_s']} "
          f"warmup_s={entry['warmup_s']} cooldown_s={entry['cooldown_s']} "
          f"rate_msg_s={entry['rate_msg_s']} seed={entry['seed']} "
          f"master_seed={plan['master_seed']} sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
