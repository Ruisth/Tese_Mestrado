"""Judge a pytest JUnit report: exactly one test ran, and it failed.

Usage: junit_one_failure.py <junit.xml>

The deliberate-failure check of `export_checks.sh` is judged on what the run
produced, never on "pytest exited non-zero": a report that is absent,
unreadable, holds no test case, holds more than one, or holds a case that did
not fail means the check itself did not behave as intended. Errors and skips
are not failures: a collection error, a skipped module or an empty report all
leave the check unproven.

It prints one line and exits 0 (exactly one test case, failed) or 1 (anything
else, including a report that cannot be read). The report is the driver's own
pytest output, read from the attempt it was written into; anything the parser
refuses (including an entity it cannot resolve) is a report that cannot be
read, which is a problem, never a pass.
"""
import sys
import xml.etree.ElementTree as ElementTree


def judge(path):
    """(exit status, one line) for the JUnit report at ``path``."""
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        return 1, f"the JUnit report could not be read: {exc}"
    cases = list(root.iter("testcase"))
    if len(cases) != 1:
        return 1, f"the JUnit report holds {len(cases)} test case(s), not exactly one"
    case = cases[0]
    outcomes = sorted({child.tag for child in case
                       if child.tag in ("failure", "error", "skipped")})
    name = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
    if outcomes != ["failure"]:
        return 1, (f"the single test case {name} did not fail: "
                   f"{', '.join(outcomes) if outcomes else 'it passed'}")
    return 0, f"the JUnit report holds exactly one test case, {name}, and it failed"


def main(argv):
    if len(argv) != 1:
        print("usage: junit_one_failure.py <junit.xml>", file=sys.stderr)
        return 1
    code, line = judge(argv[0])
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
