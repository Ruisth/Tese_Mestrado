"""Deterministic campaign plan generation.

``generate_campaign_plan(master_seed)`` enumerates every planned run of the
frozen protocol (protocol.py) into an ordered list with:

- stable ``run_id`` values (charset ``[A-Za-z0-9._-]``, CONTRACTS 2);
- per-run seeds derived deterministically from the master seed;
- the load-sweep block shuffled with ``random.Random(master_seed)``
  (plan 7.1: randomized order);
- a ``status`` field per run (``planned`` initially; the runner updates it).

Determinism: the same master seed always produces byte-identical plan JSON.
The plan contains no timestamps for exactly this reason.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from .protocol import CONDITIONS, PROTOCOL_VERSION

PLAN_VERSION = "1.0"

RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

#: Allowed values of the per-run ``status`` field.
RUN_STATUSES = ("planned", "running", "completed", "failed", "excluded")


def derive_run_seed(master_seed: int, run_id: str) -> int:
    """Derive a per-run seed in [0, 2**32) from the master seed and run_id.

    ``random.Random`` seeded with a string uses SHA-512 of the string bytes
    (CPython, seeding version 2), so this is deterministic across processes
    and platforms and independent of PYTHONHASHSEED.
    """
    return random.Random(f"{master_seed}:{run_id}").randrange(2**32)


def _run_entry(
    condition: Any,
    run_id: str,
    repetition: int,
    master_seed: int,
    rate_msg_s: float | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "condition_id": condition.id,
        "runner": condition.runner,
        "scenario": condition.scenario,
        "repetition": repetition,
        "rate_msg_s": rate_msg_s,
        "duration_s": condition.duration_s,
        "warmup_s": condition.warmup_s,
        "cooldown_s": condition.cooldown_s,
        "seed": derive_run_seed(master_seed, run_id),
        "status": "planned",
    }


def generate_campaign_plan(master_seed: int) -> dict[str, Any]:
    """Generate the fully enumerated, ordered campaign plan.

    The same ``master_seed`` always yields an identical plan (same run_ids,
    same per-run seeds, same load-sweep order).
    """
    runs: list[dict[str, Any]] = []

    for condition in CONDITIONS:
        if condition.id == "load_sweep":
            assert condition.rates_msg_s is not None
            # Enumerate every (rate, repetition) pair, then shuffle the whole
            # block with random.Random(master_seed) (plan 7.1: randomized
            # order). run_ids keep the per-rate repetition number; the list
            # position is the execution order.
            pairs = [
                (rate, rep)
                for rate in condition.rates_msg_s
                for rep in range(1, condition.repetitions + 1)
            ]
            random.Random(master_seed).shuffle(pairs)
            for rate, rep in pairs:
                run_id = f"load_sweep-{int(rate):03d}mps-r{rep:02d}"
                runs.append(_run_entry(condition, run_id, rep, master_seed, rate))
        else:
            prefix = "qemu_boot" if condition.id == "qemu_boots" else condition.id
            for rep in range(1, condition.repetitions + 1):
                run_id = f"{prefix}-r{rep:02d}"
                runs.append(
                    _run_entry(condition, run_id, rep, master_seed, condition.rate_msg_s)
                )

    for order, entry in enumerate(runs, start=1):
        entry["order"] = order

    # Sanity: run_ids unique and contract-conformant.
    seen: set[str] = set()
    for entry in runs:
        rid = entry["run_id"]
        if not RUN_ID_RE.match(rid):
            raise ValueError(f"generated run_id violates CONTRACTS 2 charset: {rid!r}")
        if rid in seen:
            raise ValueError(f"duplicate run_id generated: {rid!r}")
        seen.add(rid)

    return {
        "plan_version": PLAN_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "master_seed": master_seed,
        "conditions": [c.to_dict() for c in CONDITIONS],
        "runs": runs,
    }


def plan_to_json(plan: dict[str, Any]) -> str:
    """Canonical JSON serialization (stable key order, trailing newline)."""
    return json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_campaign_plan(plan: dict[str, Any], path: str | Path) -> Path:
    """Write ``campaign_plan.json`` (canonical serialization)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan_to_json(plan), encoding="utf-8")
    return path


def load_campaign_plan(path: str | Path) -> dict[str, Any]:
    """Load a previously generated campaign plan."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
