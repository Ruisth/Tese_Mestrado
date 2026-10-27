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

``supplement_plan`` / ``apply_plan_supplement`` add ONE supplementary entry
(``SUPPLEMENTS``) to an existing plan file without regenerating it: the
entries it holds keep their bytes, statuses included, and the new entry is
built by the same ``_run_entry`` and seed rule. ``generate_campaign_plan``
never adds one, so the plan of a master seed is unchanged.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .protocol import CONDITIONS, CONDITIONS_BY_ID, PROTOCOL_VERSION

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


#: Supplementary entries: one fresh run identity each, added to an EXISTING
#: plan file by :func:`supplement_plan` and never by
#: :func:`generate_campaign_plan`, so the plan of a master seed and
#: PROTOCOL_VERSION are unchanged. A key names its frozen condition and a
#: repetition number beyond the condition's planned ones, so its run_id is
#: one no generated plan holds. The entry is :func:`_run_entry` of that
#: condition (its runner, scenario, rate, duration, warm-up and cool-down),
#: seeded by :func:`derive_run_seed` from the plan's master seed and the new
#: run_id, numbered after the plan's last entry and marked ``supplement``.
#:
#: ``g3-t6`` (offline block authorised 2026-10-05): G3's test 6 takes its run
#: id from the pilot plan's controller_restart entries, and r01-r03 are all
#: used on the guest (2026-09-18, 2026-09-19, 2026-10-03); its next run takes
#: controller_restart-r04.
SUPPLEMENTS: dict[str, tuple[str, int]] = {"g3-t6": ("controller_restart", 4)}

#: The fields an entry is written with that never change afterwards; the
#: status and what the harness writes beside it (``result_dir``,
#: ``finished_utc``, ``validity``) change as runs execute and are not compared.
FROZEN_ENTRY_FIELDS = (
    "run_id", "condition_id", "runner", "scenario", "repetition", "rate_msg_s",
    "duration_s", "warmup_s", "cooldown_s", "seed", "order", "supplement",
)


class PlanSupplementError(ValueError):
    """Why a supplementary entry is not added; the plan is left as it was."""


def supplementary_entry(master_seed: int, key: str, order: int) -> dict[str, Any]:
    """The supplementary entry ``key`` of a plan of ``master_seed``, numbered ``order``."""
    condition_id, repetition = SUPPLEMENTS[key]
    condition = CONDITIONS_BY_ID[condition_id]
    run_id = f"{condition_id}-r{repetition:02d}"
    entry = _run_entry(condition, run_id, repetition, master_seed, condition.rate_msg_s)
    entry["order"] = order
    entry["supplement"] = key
    return entry


def _frozen(entry: dict[str, Any]) -> dict[str, Any]:
    return {field: entry.get(field) for field in FROZEN_ENTRY_FIELDS}


def supplement_plan(text: str, key: str) -> tuple[str, dict[str, Any], bool]:
    """``text`` (a plan file's content) with the supplementary entry ``key``
    appended: (the new text, the entry, whether it was added).

    The text must be the canonical serialisation the harness writes
    (:func:`plan_to_json`, as ``plan`` and the run statuses write it), so
    that the new text is the old one up to its last entry, byte for byte,
    then the new entry. Its entries must be the frozen generation of its
    master seed (every field but the run statuses), followed only by
    supplementary entries as :func:`supplementary_entry` builds them. An
    entry ``key`` already holds is never added again: the text comes back
    unchanged, whatever status its run reached. Anything else raises
    :class:`PlanSupplementError` naming the reason.
    """
    if key not in SUPPLEMENTS:
        raise PlanSupplementError(
            f"unknown supplement {key!r} (defined: {', '.join(sorted(SUPPLEMENTS))})"
        )
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanSupplementError(f"not a JSON plan ({exc})") from None
    runs = plan.get("runs") if isinstance(plan, dict) else None
    if not isinstance(runs, list) or not all(isinstance(e, dict) for e in runs):
        raise PlanSupplementError("no 'runs' list of entries")
    if plan_to_json(plan) != text:
        raise PlanSupplementError(
            "not the canonical serialisation the harness writes (plan_to_json): "
            "rewriting it would change bytes of the entries it holds"
        )
    master_seed = plan.get("master_seed")
    if type(master_seed) is not int:
        raise PlanSupplementError(f"master_seed {master_seed!r} is not a whole number")
    frozen = generate_campaign_plan(master_seed)
    for field in ("plan_version", "protocol_version", "conditions"):
        if plan.get(field) != frozen[field]:
            raise PlanSupplementError(
                f"its {field} is not the one generated for master seed {master_seed}"
            )
    base = frozen["runs"]
    if len(runs) < len(base):
        raise PlanSupplementError(
            f"it holds {len(runs)} entries, fewer than the {len(base)} generated "
            f"for master seed {master_seed}"
        )
    for position, want in enumerate(base):
        if _frozen(runs[position]) != _frozen(want):
            raise PlanSupplementError(
                f"entry {position + 1} ({runs[position].get('run_id')}) is not "
                f"{want['run_id']} as generated for master seed {master_seed} "
                "(only its status may change)"
            )
    held: dict[str, Any] | None = None
    seen: set[str] = set()
    for position in range(len(base), len(runs)):
        got = runs[position]
        other = got.get("supplement")
        if (
            not isinstance(other, str)
            or other not in SUPPLEMENTS
            or other in seen
            or _frozen(got) != _frozen(supplementary_entry(master_seed, other, position + 1))
        ):
            raise PlanSupplementError(
                f"entry {position + 1} ({got.get('run_id')}) is neither generated for "
                f"master seed {master_seed} nor a supplementary entry as defined"
            )
        seen.add(other)
        if other == key:
            held = got
    if held is not None:
        return text, held, False
    entry = supplementary_entry(master_seed, key, len(runs) + 1)
    if entry["run_id"] in {e.get("run_id") for e in runs} or not RUN_ID_RE.match(entry["run_id"]):
        raise PlanSupplementError(f"{entry['run_id']} collides with an entry the plan holds")
    runs.append(entry)
    return plan_to_json(plan), entry, True


def apply_plan_supplement(path: str | Path, key: str) -> tuple[dict[str, Any], bool]:
    """Add the supplementary entry ``key`` to the plan file at ``path`` in
    place (:func:`supplement_plan`): (the entry, whether it was added).

    The new content is written beside the file (LF bytes, the file's mode)
    and moved over it in one step, only while the file still holds what was
    read; a refusal or a file changed meanwhile raises
    :class:`PlanSupplementError` and leaves it as it was.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PlanSupplementError(f"cannot be read ({exc})") from None
    new_text, entry, added = supplement_plan(text, key)
    if not added:
        return entry, False
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".supplement", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        shutil.copymode(path, tmp)
        if path.read_bytes() != raw:
            raise PlanSupplementError("it changed while the supplement was prepared")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return entry, True
