"""The session facts of the finite proof of ADR 0011: ``proof_session.json``.

Usage: proof_session.py write PATH --healthy-limit-s N --attempt-limit-s N [KEY=VALUE ...]
       proof_session.py update PATH KEY=VALUE ...
       proof_session.py reach PATH RULE INSTANT
       proof_session.py show PATH

The proof's evaluator (``egw_experiments.proof_evaluator``) reads this file
beside the sealed run directory for what only the driver can know: the
values the session used, the two stop rules the ADR imposes by design and
whether either was reached, the restoration state the driver observed, the
restart-shown record and whether the optional extension was chosen. The
field names are the evaluator's (``values``, ``stop_rules`` as a list of
``{rule, limit_s, reached, reached_at}``, ``restoration``, ``restart_shown``,
``extension``), with ``clocks`` and ``instants`` kept for the record; a test
pins them to the evaluator's reader.

WRITE ONCE, THEN UPDATE, READABLE AT EVERY STEP. ``write`` creates the file
before the first ``drained`` starts, with the values and the stop rules not
reached (it refuses an existing file: a session's facts are never restarted
over). ``update`` merges fields into it - a dotted KEY (``values.W``,
``instants.harness_exit``) names a nested field - and ``reach`` marks one
stop rule as reached at INSTANT. Every write goes to a temporary file first
and is renamed over the record, so the file the evaluator reads is a whole
JSON document at any instant, whatever step the driver is in when it is
read (or interrupted). VALUE is parsed as JSON when it is JSON and kept as a
string otherwise, as ``local_export set`` reads its fields.

The two stop rules are the ADR's, verbatim ("The finite proof", ceiling):
the stack with the candidate healthy within 20 minutes of its start, and the
attempt stopped 50 minutes after its first ``drained`` starts. Their limits
are the values the driver reads before it starts (``EGW_HEALTH_LIMIT_S``,
``EGW_PROOF_ATTEMPT_LIMIT_S``): the student may set other values, and the
values used are recorded here before the session starts.

Exit status: 0 done; 2 usage, a file that exists on ``write``, a file that
cannot be read or written, a rule that is not one of the two, or an instant
that is empty. Every refusal prints ``STOP: proof_session: ...`` on stderr
and leaves the file as it was.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

USAGE = (
    "usage: proof_session.py write PATH --healthy-limit-s N --attempt-limit-s N [KEY=VALUE ...]\n"
    "       proof_session.py update PATH KEY=VALUE ...\n"
    "       proof_session.py reach PATH <healthy|attempt> INSTANT\n"
    "       proof_session.py show PATH"
)

#: The two stop rules of the proof's ceiling, verbatim from ADR 0011 ("The
#: finite proof"): "set by two stop rules imposed by design, not measured
#: durations".
STOP_RULES = {
    "healthy": (
        "the stack with the candidate healthy within 20 minutes of its start (as for "
        "the broker measurement, and on the same records)"
    ),
    "attempt": "the attempt stopped 50 minutes after its first `drained` starts",
}

#: What the ADR says happens when one is reached, carried into the file so
#: the record explains itself.
STOP_RULE_CONSEQUENCE = (
    "If a stop rule is reached, the session stops and the proof is recorded "
    "inconclusive. The student may set other values before the session; the values "
    "used are recorded before it starts"
)


class SessionError(Exception):
    """A refusal: printed as ``STOP: proof_session: ...`` and exit 2."""


def parse_value(text: str):
    """JSON when it is JSON, the string otherwise (as ``local_export set``)."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def parse_assignment(item: str) -> tuple[list[str], object]:
    key, sep, value = item.partition("=")
    if not sep or not key.strip():
        raise SessionError(f"{item!r} is not KEY=VALUE")
    parts = [p for p in key.strip().split(".")]
    if any(not p for p in parts):
        raise SessionError(f"{key!r} is not a field name (empty component)")
    return parts, parse_value(value)


def assign(document: dict, parts: list[str], value: object) -> None:
    """Set a (possibly nested) field; an intermediate that is not an object
    is replaced, never silently written into."""
    node = document
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def initial(healthy_limit_s: int, attempt_limit_s: int) -> dict:
    return {
        "proof": "ADR 0011, The finite proof",
        "values": {},
        "stop_rules": [
            {"id": "healthy", "rule": STOP_RULES["healthy"], "limit_s": healthy_limit_s,
             "reached": False, "reached_at": None},
            {"id": "attempt", "rule": STOP_RULES["attempt"], "limit_s": attempt_limit_s,
             "reached": False, "reached_at": None},
        ],
        "stop_rule_consequence": STOP_RULE_CONSEQUENCE,
        "clocks": {},
        "instants": {},
        "restart_shown": None,
        "restoration": "not-started",
        "extension": None,
    }


def read(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionError(f"{path} cannot be read: {exc}") from None
    if not isinstance(document, dict):
        raise SessionError(f"{path} is not a JSON object")
    return document


def write_whole(path: Path, document: dict, *, create: bool) -> None:
    """The document as one file: written beside PATH and renamed over it, so
    a reader never sees a partial record. ``create`` refuses an existing
    file (a race included: the rename is preceded by an exclusive create)."""
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if create:
        try:
            with path.open("x", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        except FileExistsError:
            raise SessionError(f"{path} exists: the session facts are written once") from None
        except OSError as exc:
            raise SessionError(f"{path} could not be written: {exc}") from None
        return
    try:
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        raise SessionError(f"{path} could not be updated: {exc}") from None


def whole_number(text: str, name: str) -> int:
    if not text.isdigit():
        raise SessionError(f"{name} {text!r} is not a whole number of seconds")
    return int(text)


def cmd_write(argv: list[str]) -> int:
    if len(argv) < 5:
        raise SessionError(USAGE)
    path = Path(argv[0])
    rest = argv[1:]
    limits: dict[str, int] = {}
    assignments: list[str] = []
    index = 0
    while index < len(rest):
        item = rest[index]
        if item in ("--healthy-limit-s", "--attempt-limit-s"):
            if index + 1 >= len(rest):
                raise SessionError(f"{item} needs a value")
            limits[item] = whole_number(rest[index + 1], item)
            index += 2
            continue
        assignments.append(item)
        index += 1
    if "--healthy-limit-s" not in limits or "--attempt-limit-s" not in limits:
        raise SessionError("write needs --healthy-limit-s and --attempt-limit-s (the two stop rules' limits)")
    document = initial(limits["--healthy-limit-s"], limits["--attempt-limit-s"])
    for item in assignments:
        parts, value = parse_assignment(item)
        assign(document, parts, value)
    write_whole(path, document, create=True)
    print(f"proof_session: wrote {path}: {len(document['stop_rules'])} stop rules, "
          f"{len(document['values'])} value(s)")
    return 0


def cmd_update(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SessionError(USAGE)
    path = Path(argv[0])
    document = read(path)
    for item in argv[1:]:
        parts, value = parse_assignment(item)
        assign(document, parts, value)
    write_whole(path, document, create=False)
    print(f"proof_session: updated {path}: {', '.join(a.partition('=')[0] for a in argv[1:])}")
    return 0


def cmd_reach(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SessionError(USAGE)
    path, rule_id, instant = Path(argv[0]), argv[1], argv[2]
    if rule_id not in STOP_RULES:
        raise SessionError(f"{rule_id!r} is not a stop rule of the proof ({', '.join(STOP_RULES)})")
    if not instant.strip():
        raise SessionError("the instant the rule was reached at is empty")
    document = read(path)
    rules = document.get("stop_rules")
    if not isinstance(rules, list):
        raise SessionError(f"{path} carries no stop_rules list")
    matched = [r for r in rules if isinstance(r, dict) and r.get("id") == rule_id]
    if len(matched) != 1:
        raise SessionError(f"{path} does not carry the stop rule {rule_id!r} exactly once")
    matched[0]["reached"] = True
    matched[0]["reached_at"] = instant
    write_whole(path, document, create=False)
    print(f"proof_session: stop rule reached ({rule_id}) at {instant}: {STOP_RULES[rule_id]}")
    return 0


def cmd_show(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SessionError(USAGE)
    document = read(Path(argv[0]))
    sys.stdout.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return 0


COMMANDS = {"write": cmd_write, "update": cmd_update, "reach": cmd_reach, "show": cmd_show}


def main(argv: list[str]) -> int:
    try:
        if not argv or argv[0] not in COMMANDS:
            raise SessionError(USAGE)
        return COMMANDS[argv[0]](argv[1:])
    except SessionError as exc:
        print(f"STOP: proof_session: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
