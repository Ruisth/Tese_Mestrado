#!/usr/bin/env python3
"""Write the six-entry input plan of the minimal Yocto-vs-Debian-13 comparison.

    measure_plan.py write --out PATH --seeds S1 S2 S3

The comparison runs the existing nominal condition (600 s measured at 11.2
msg/s after a 120 s warm-up, protocol.py) six times through the existing
harness (``python -m egw_experiments run --plan``): three pairs, each one
run on the Yocto image and one on Debian 13 under one QEMU/TCG profile, the
order alternating so that neither distribution always follows the other
(pair 1 Yocto then Debian, pair 2 Debian then Yocto, pair 3 Yocto then
Debian; tools/compare/PROTOCOL.md section 3). This tool writes that input
and nothing else; it is not a general plan generator. The results are an
exploratory comparison, not campaign attempts, and carry no statistical
significance.

Every entry is ``plan_gen._run_entry`` of the frozen ``nominal`` condition
(its runner, scenario, rate, duration, warm-up and cool-down), so its shape
cannot drift from what the harness reads, with ``status`` ``planned`` and
``repetition`` the pair number. ``_run_entry`` derives the seed from the
master seed and the run id (``derive_run_seed``): one distinct seed per run,
the rule of a campaign plan, whose runs are independent repetitions. Here
the two runs of a pair must drive the same simulated devices and the same
event stream against the two distributions, so the seed is the pair's, Sk
for pair k, set after ``_run_entry`` returns; the three pair seeds must
differ, so that no pair repeats another. The seeds are arguments with no
default (the student's decision).

The top level is the campaign plan's: ``plan_version``, ``protocol_version``,
``master_seed``, ``conditions`` (the nominal record verbatim) and ``runs``.
The harness reads only ``runs`` (the loader is json.loads; run.py and
analyze.py take ``plan.get("runs")``) and echoes ``master_seed`` into each
manifest without deriving anything from it; it is written as S1, and the
inert ``comparison`` block says so. That block holds the purpose, the pair
order, the pair seeds and, per run id, its ``scenario`` (``yocto`` or
``debian13``), ``pair`` and ``order_in_pair``; each entry carries the same
three fields under ``comparison``, which the harness tolerates: it reads an
entry's named fields only, echoes the whole entry into the run's manifest
(``config.plan_entry``) and rewrites the plan with the entry's keys intact
when it updates a status (``update_plan_status``).

``write`` refuses, with nothing written (exit 2): other than three seeds; a
seed that is not a whole number in [0, 2**32); a seed repeated across pairs;
an output that exists (the plan is write-once; the open itself refuses a
target that exists). It writes the canonical serialisation
(``plan_to_json``) and prints one line per entry (run id, seed, scenario)
and the file's sha256.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from egw_experiments.plan_gen import PLAN_VERSION, _run_entry, plan_to_json
from egw_experiments.protocol import CONDITIONS_BY_ID, PROTOCOL_VERSION

USAGE = "measure_plan.py write --out PATH --seeds S1 S2 S3"
CONDITION_ID = "nominal"
YOCTO, DEBIAN = "yocto", "debian13"
#: The three pairs in execution order, each the order of its two runs.
PAIRS: tuple[tuple[str, str], ...] = ((YOCTO, DEBIAN), (DEBIAN, YOCTO), (YOCTO, DEBIAN))
PURPOSE = (
    "Exploratory comparison of the two gateway configurations (the Yocto image and Debian 13) "
    "under one QEMU/TCG profile, six nominal runs in three pairs; the results are not campaign "
    "attempts and carry no statistical significance."
)
MASTER_SEED_NOTE = (
    "S1, the seed of pair 1: the harness echoes this field into each manifest and derives "
    "nothing from it; the seed of every entry is its pair's (pair_seeds), set by this tool."
)
WHOLE_NUMBER = re.compile(r"[0-9]+")
SEED_LIMIT = 2**32


def run_id(pair: int, scenario: str) -> str:
    return f"cmp-p{pair}-{scenario}"


def build_plan(seeds: Sequence[int]) -> dict[str, Any]:
    """The plan of the pair seeds ``seeds`` (S1, S2, S3): six entries in pair
    order, the seed of pair k being Sk in both of its runs."""
    if len(seeds) != len(PAIRS) or len(set(seeds)) != len(seeds):
        raise ValueError(f"{len(PAIRS)} distinct pair seeds are needed, got {list(seeds)}")
    condition = CONDITIONS_BY_ID[CONDITION_ID]
    runs: list[dict[str, Any]] = []
    for pair, scenarios in enumerate(PAIRS, start=1):
        for position, scenario in enumerate(scenarios, start=1):
            entry = _run_entry(condition, run_id(pair, scenario), pair, seeds[0], condition.rate_msg_s)
            entry["seed"] = seeds[pair - 1]  # the pair's seed, equal in both distributions
            entry["order"] = len(runs) + 1
            entry["comparison"] = {"scenario": scenario, "pair": pair, "order_in_pair": position}
            runs.append(entry)
    return {
        "plan_version": PLAN_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "master_seed": seeds[0],
        "conditions": [condition.to_dict()],
        "runs": runs,
        "comparison": {
            "purpose": PURPOSE,
            "master_seed": MASTER_SEED_NOTE,
            "pair_seeds": {str(pair): seed for pair, seed in enumerate(seeds, start=1)},
            "pair_order": [[run_id(pair, s) for s in scenarios] for pair, scenarios in enumerate(PAIRS, start=1)],
            "runs": {entry["run_id"]: dict(entry["comparison"]) for entry in runs},
        },
    }


def parse_seeds(tokens: Sequence[str]) -> tuple[list[int], list[str]]:
    """The seeds ``tokens`` name, and every reason they are refused."""
    reasons = []
    if len(tokens) != len(PAIRS):
        reasons.append(f"{len(PAIRS)} seeds are needed, one per pair; {len(tokens)} given")
    seeds = []
    for token in tokens:
        if not WHOLE_NUMBER.fullmatch(token) or int(token) >= SEED_LIMIT:
            reasons.append(f"the seed {token!r} is not a whole number in [0, 2**32)")
        else:
            seeds.append(int(token))
    if len(set(seeds)) != len(seeds):
        reasons.append(f"the pair seeds must differ: {list(tokens)}")
    return seeds, reasons


def write_plan(plan: dict[str, Any], out: Path) -> str:
    """Write ``plan`` to ``out`` once (the open refuses a target that exists;
    a write that fails part-way removes what it created) and return the
    sha256 of what was written."""
    text = plan_to_json(plan)
    out.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(out, flags, 0o644)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except OSError:
        out.unlink(missing_ok=True)
        raise
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stop(reasons: list[str]) -> int:
    for reason in reasons:
        print(f"STOP: measure_plan: {reason}", file=sys.stderr)
    print("STOP: measure_plan: nothing was written", file=sys.stderr)
    return 2


def _write(args: argparse.Namespace) -> int:
    seeds, reasons = parse_seeds(args.seeds)
    if args.out.exists() or args.out.is_symlink():
        reasons.append(f"{args.out} exists: the plan is write-once and is not replaced")
    if reasons:
        return _stop(reasons)
    plan = build_plan(seeds)
    try:
        digest = write_plan(plan, args.out)
    except OSError as exc:
        return _stop([f"{args.out} was not written ({exc})"])
    for entry in plan["runs"]:
        print(f"{entry['run_id']} {entry['seed']} {entry['comparison']['scenario']}")
    print(f"wrote {args.out}: entries={len(plan['runs'])} sha256={digest}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="measure_plan.py", usage=USAGE)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", usage=USAGE, help="write the comparison plan, once")
    write.add_argument("--out", required=True, type=Path, help="the plan file (write-once)")
    write.add_argument("--seeds", required=True, nargs="+", metavar="S",
                       help="the three pair seeds, whole numbers in [0, 2**32), distinct; no default")
    args = parser.parse_args(argv)
    return _write(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
