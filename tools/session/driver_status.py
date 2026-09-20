"""Derive a session driver's exit status from the attempt it produced.

Usage: driver_status.py <attempt.json> <exported|failed|deferred> <stop failed: 0|1>
       driver_status.py --stop <code> <reason>

This is the ONE place where the table of `tools/session/README.md`
("Exit statuses") is applied: a driver never invents a code of its own. It
prints the single final line every driver ends with and exits with the derived
code, so `common.sh` only has to call it::

    "$PY" "$DRIVERS/driver_status.py" "$A/attempt.json" exported 0

The inputs are the attempt's own recorded verdicts (status, instrumentation
validity, system outcome, and the capture failures the export tool records),
the export receipt beside them, the result of the export, and one driver flag:

``exported``   the package was written to output_test and verified;
``failed``     the export failed: there is no verified package;
``deferred``   nothing was exported because the attempt stays open on purpose
               (guest_session_open.sh; guest_session_close.sh exports it). The
               line then says so: a deferred attempt has recorded no outcome
               and holds no package, so it is never named "system outcome
               pass; package exported and verified".

``exported`` is the export tool's exit status, and that status is 0 for a
package the tool finalised and sealed WITHOUT part of the evidence the attempt
registered (a source root it refused to read through a link, a declared
artefact that was never written, a destination index that could not be
rebuilt). The tool names that in one field of ``export/receipt.json``,
``package_state``: ``verified`` for a package that holds everything and is
listed in the destination's index, and ``verified; <what is missing>`` or
``not exported: ...`` for anything else. That field is read here, beside the
``attempt.json`` this is given, so the contracted final line can never say
"package exported and verified" for a package that is not one: such a run ends
3, with the state named on the line. A receipt that cannot be read, or that
does not carry the field, leaves the package's state unknown, which is not
"verified" either.

``stop failed`` is 1 only for a session close whose controlled stop or
power-off failed.

Observing the system fail is a result; failing to observe is an invalid
measurement. An attempt whose instrumentation is ``valid`` (or
``not-applicable``) and whose system outcome is ``fail`` therefore derives 1,
the valid negative result, for **every** driver, the session close included:
only its own controlled stop or power-off failing raises that to 5. A fault a
driver observed never becomes 3 by itself; 3 is for evidence that is missing,
unreadable or below a stated requirement.

``--stop`` is the second form: a driver that ends before an attempt exists (a
prerequisite of the attempt itself, or an interruption before it was created)
or that owns no attempt at all still prints the contracted final line, with no
run id, status ``no-attempt`` and the three verdicts unknown. The code is the
driver's, not derived; this form only names it and its meaning.

Precedence when several apply: 4 > 130 > 5 > 2 > 3 > 1 > 0. A code is never
lowered by a later observation, and an input that cannot be read is an error
(3), never a pass.
"""
import json
import os
import sys

EXPORT_RESULTS = ("exported", "failed", "deferred")

#: The one field of ``export/receipt.json`` that names what the export left in
#: the destination, and its only value for a package that holds everything the
#: attempt registered and is listed in the destination's index.
PACKAGE_STATE_FIELD = "package_state"
VERIFIED = "verified"

MEANING = {
    0: "ran; instrumentation valid (or not applicable); system outcome pass; "
       "package exported and verified",
    1: "valid negative result: ran; instrumentation valid; package exported "
       "and verified; system outcome fail",
    2: "a prerequisite failed: the test did not run",
    3: "instrumentation invalid, outcome inconclusive or unknown, or a "
       "mandatory step (capture, fetch, hash, check) failed",
    4: "the local export failed: no verified package in output_test (the "
       "attempt is kept in WSL; run 'local_export recover')",
    5: "the controlled stop or power-off failed",
    130: "interrupted: marked interrupted and exported",
}

# What the same codes mean for an attempt that stays OPEN on purpose. Nothing
# has been exported, the outcome has not been decided and the attempt is still
# running, so the line must not carry the words of a finished, exported run.
OPEN = "the guest session stays OPEN and is exported by guest_session_close.sh"
DEFERRED_MEANING = {
    0: f"ran; instrumentation valid (or not applicable); {OPEN}",
    3: f"instrumentation invalid, or a mandatory step (capture, fetch, hash, check) failed; {OPEN}",
}

# What 3 means when the attempt's own verdicts are all sound and it is the
# package that is not: the evidence reached output_test without part of what
# the attempt registered, so the run is not a complete record of itself.
PACKAGE_MEANING = ("the package reached output_test but is not a complete record of the "
                   "attempt: part of what the attempt registered is not in it")


def meaning(code, export_result):
    """The words printed beside a code, for the form the attempt is in."""
    if export_result == "deferred":
        return DEFERRED_MEANING.get(code, f"{MEANING[code]}; {OPEN}")
    return MEANING[code]


def package_state(attempt_path, export_result):
    """(the package holds everything, what the receipt says) for an export.

    The receipt sits beside the attempt, in ``export/receipt.json``, and is
    rewritten by every export. Only an export that says it wrote a package is
    judged here: a deferred attempt has none, and a failed export is already
    the most serious code there is.
    """
    if export_result != "exported":
        return True, ""
    receipt = os.path.join(os.path.dirname(os.path.abspath(attempt_path)), "export", "receipt.json")
    try:
        with open(receipt, encoding="utf-8") as fh:
            written = json.load(fh)
        if not isinstance(written, dict):
            raise ValueError("the receipt is not an object")
        state = written[PACKAGE_STATE_FIELD]
        if not isinstance(state, str) or not state.strip():
            raise ValueError(f"'{PACKAGE_STATE_FIELD}' names no state")
    except (KeyError, OSError, ValueError) as exc:
        return False, (f"UNKNOWN: the export receipt does not say what the export left in "
                       f"the destination ({receipt}: {exc})")
    return state == VERIFIED, state


def derive(attempt, export_result, stop_failed):
    """The exit status of a driver, from what the attempt records."""
    status = attempt.get("status")
    validity = attempt.get("instrumentation_validity")
    outcome = attempt.get("system_outcome")
    captures = attempt.get("capture_failures") or []
    if export_result == "failed":
        return 4
    if status == "interrupted" or outcome == "interrupted":
        return 130
    if stop_failed:
        return 5
    if outcome == "not-run":
        return 2
    if export_result == "deferred":
        # A guest session left open on purpose: no verdict has been recorded
        # yet, and that absence is not an instrumentation failure. A mandatory
        # step that failed is recorded on the open attempt as invalid
        # instrumentation, and the session is still open for the close driver.
        if captures or status != "running" or validity == "invalid":
            return 3
        return 0
    if captures or validity not in ("valid", "not-applicable"):
        return 3
    if outcome in ("inconclusive", "unknown") or status not in ("finished", "failed"):
        return 3
    if outcome == "fail":
        return 1
    if outcome == "pass":
        return 0
    return 3


def stop(argv):
    """The final line of a driver that ends before, or without, an attempt."""
    if len(argv) != 2 or argv[0] not in [str(code) for code in MEANING]:
        print(f"usage: driver_status.py --stop <{'|'.join(str(c) for c in MEANING)}> <reason>",
              file=sys.stderr)
        return 3
    code = int(argv[0])
    print(f"DRIVER RESULT none: exit={code} ({MEANING[code]}) status=no-attempt "
          f"instrumentation_validity=unknown system_outcome=unknown export=none "
          f"({argv[1]})")
    return code


def main(argv):
    if argv and argv[0] == "--stop":
        return stop(argv[1:])
    if len(argv) != 3 or argv[1] not in EXPORT_RESULTS or argv[2] not in ("0", "1"):
        print(f"usage: driver_status.py <attempt.json> <{'|'.join(EXPORT_RESULTS)}> <0|1>\n"
              f"       driver_status.py --stop <code> <reason>", file=sys.stderr)
        return 3
    path, export_result, stop_failed = argv[0], argv[1], argv[2] == "1"
    try:
        with open(path, encoding="utf-8") as fh:
            attempt = json.load(fh)
        if not isinstance(attempt, dict):
            raise ValueError("attempt.json is not an object")
    except (OSError, ValueError) as exc:
        code = 4 if export_result == "failed" else 3
        print(f"DRIVER RESULT unknown: exit={code} ({meaning(code, export_result)}) "
              f"status=unreadable instrumentation_validity=unreadable "
              f"system_outcome=unreadable export={export_result} ({path}: {exc})")
        return code
    code = derive(attempt, export_result, stop_failed)
    complete, package = package_state(path, export_result)
    words = meaning(code, export_result)
    if not complete and code in (0, 1):
        # Every verdict of the attempt is sound and the package is not: the
        # run is not reported as exported and verified (3 outranks 1 and 0).
        code, words = 3, PACKAGE_MEANING
    captures = attempt.get("capture_failures") or []
    line = (f"DRIVER RESULT {attempt.get('run_id')}: exit={code} ({words}) "
            f"status={attempt.get('status')} "
            f"instrumentation_validity={attempt.get('instrumentation_validity')} "
            f"system_outcome={attempt.get('system_outcome')} export={export_result}")
    if not complete:
        line += f" package=INCOMPLETE ({package})"
    if captures:
        line += f" capture_failures={len(captures)}"
    if stop_failed:
        line += " controlled_stop=failed"
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
