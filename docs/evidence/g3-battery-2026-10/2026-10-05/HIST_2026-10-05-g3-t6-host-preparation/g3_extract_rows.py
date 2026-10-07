#!/usr/bin/env python3
"""G3 qualification, session S4 (test 6 only) - host preparation: the row files.

Reads the runbook blob of the merged commit (1fd9792, docs/setup/qemu_integrated_gateway.md),
asserts its sha256, extracts the host$ commands of section 7's test 6 with the rule of
_host_commands in src/tests/test_runbook_itest_helpers.py (the "host$ " prompt removed, the
continuation lines kept as they are), places them in the one step file of session S4 by
SOURCE LINE NUMBER, substitutes NOTHING (S4: the run id controller_restart-r04 is the
runbook's own literal, a plan entry, asserted to stand once, on the first line), and writes:

  <out>/<step>.sh          one LF-only bash text per step (sourced by the steps script)
  <out>/<step>.sh.diff     the unified diff of that step (empty: nothing is substituted)
  <out>/rows.manifest.json per file: row, step order, source line numbers, sha256 of the
                           extracted text before and after the (empty) substitution

The rows of tests 1 to 5 and 7 to 9 (sessions S1, S2 and S3, the "-q1" and "-q2" ids) are not
extracted: S4 runs test 6 (one step file, t6.sh, the eight host$ lines 1421-1428) and nothing
else. S4 has no prose-only step.

The script reads its two inputs and writes only inside <out>. It refuses an <out> inside the
execution clone, the run directory, the image and build trees, output_test, ChatGPT, a
read-only worktree or a sealed earlier preparation (by path component as well as under $HOME,
so a redirected HOME does not lift the refusal), and an <out> that holds the row files of
another commit (the rows of 80e833f and 8e49261 are never overwritten, with --replace or
without). It starts nothing and contacts nothing.

Usage (WSL):
  python3 g3_extract_rows.py --runbook <blob|-> [--rule-source <test file blob>] --out <dir> [--replace]
  python3 g3_extract_rows.py --runbook <blob|-> [--rule-source <test file blob>] --out <dir> --check
"""
import argparse
import ast
import collections
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys

RUNBOOK_COMMIT = "1fd9792bb76f02c6948f33887207dba4837202db"
RUNBOOK_PATH = "docs/setup/qemu_integrated_gateway.md"
RUNBOOK_SHA256 = "317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f"
RUNBOOK_LINES = 1624
RULE_SOURCE_PATH = "src/tests/test_runbook_itest_helpers.py"
RULE_SOURCE_SHA256 = "b63ef7d88ae22e623bf381ef0dc3e6fbfbf050d966d5b0e09cc961ee169d83be"
# S4 (brief, stream ROWS: "no substitution"): no suffix; each step file is the extracted text.
SUFFIX = None
EARLIER_SUFFIXES = ["-q1", "-q2"]   # the ids of sessions S1 and S2 ('-q1') and S3 ('-q2'): consumed, never reused
PROMPT = "host$ "

# The one section-7 heading whose fenced host$ commands session S4 runs, as the runbook's own
# tests name it, with the number of commands, the number of text lines and the first 16 hex
# digits of the sha256 of the joined text. S4: test 6's block changed (merged as 1fd9792: the
# run id r04, the transition rule on the harness line, the added exactly-once line); its values
# were taken for this preparation, on 2026-10-05, from the blob of 1fd9792 apart from this
# script (sed -n '1421,1428p', the prompt removed with sed, sha256sum).
HEADS = [
    ("### Test 6", 8, 8, "ec8ac010d79ba87f"),
]

# S4 (brief, stream ROWS): no token changes - no id is substituted.
OLD_IDS = []
# Never changed: the run id, the runbook's own literal (a plan entry added by plan-supplement).
UNCHANGED = ["controller_restart-r04"]
TOTAL_COUNTS = {}
# S4: the plan-entry literals of the extracted text, each with its count: r04, the run id (line
# 1421's assignment), and r01, named in line 1421's comment ("controller_restart-r01 ran on
# 2026-09-18, r02 on 2026-09-19 and r03 on 2026-10-03").
PLAN_LITERALS = {"controller_restart-r01", "controller_restart-r04"}
PLAN_COUNTS = {"controller_restart-r01": 1, "controller_restart-r04": 1}
# S4: what the block does, asserted on its lines (the family hash pins the whole text; these
# name the three changes against the battery's block of 80e833f). Line number, text it holds.
MARKERS = [
    (1421, "RID=controller_restart-r04; F6=used; "),
    (1425, " --restart-transition-rule 1a-option-a-2026-10-05; HR=$?; "),
    (1427, '[ "$T6" = ok ] && $REC acceptance $RAW6/logs/simulator/$RID --events $RAW6/events.post-drain.jsonl '
           '--exactly-once || stop '),
]

# A token: the id not preceded by a name character and not followed by a name character or a
# hyphen, so that an id is never matched inside a longer one. A preceding hyphen is allowed: the
# broker's client id is "egw-simulator-<run id>". S4: with no id the alternation would be empty
# and match the empty string everywhere, so the token is then a pattern that never matches.
TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])("
    + "|".join(re.escape(x) for x in sorted(OLD_IDS, key=len, reverse=True))
    + r")(?![A-Za-z0-9_-])"
) if OLD_IDS else re.compile(r"(?!)")
ITEST_LIKE = re.compile(r"itest-[A-Za-z0-9$-]*[A-Za-z0-9$]")
PLAN_LIKE = re.compile(r"(?:nominal|controller_restart|smoke_sequence)-r[0-9][0-9]")


def R(a, b=None):
    return list(range(a, (a if b is None else b) + 1))


# The step files, in the order of session S4. Per file: row, session, order within the row, the
# source line numbers of the extracted text, the lines on which a host$ command starts, the
# asserted substitution counts, and the reason for the line range where the lines on which
# commands start and the extracted text differ.
STEPS = [
    dict(file="t6.sh", row="t6", session="S4", order=1, lines=R(1421, 1428), starts=R(1421, 1428),
         subs={},
         note="Lines 1421-1428, eight one-line commands: the whole fenced block (line 1420 opens it, line 1429 "
              "closes it). Nothing is substituted: controller_restart-r04 is the runbook's own literal, a plan "
              "entry."),
]

# S4: one row, one step file; its note says what the block does.
ROWS = [
    ("t6", "S4", ["t6.sh"],
     "Plan entry controller_restart-r04 (seed read from the pilot plan; refused if already used): the harness run "
     "with the controller restarted at +300 s and the resource transition judged under the rule "
     "1a-option-a-2026-10-05 (line 1425), then - each only when T6=ok - delta on the twins (line 1426) and the "
     "per-identity check 'acceptance --exactly-once' on the post-drain copy (line 1427), and analyze (line 1428)."),
]


def die(msg):
    print("STOP: " + msg, file=sys.stderr)
    sys.exit(1)


def need(cond, msg):
    if not cond:
        die(msg)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ranges(nums):
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else "%d-%d" % (nums[i], nums[j]))
        i = j + 1
    return ", ".join(out)


# ---------------------------------------------------------------------------------------------
# The rule of _section and _host_commands (src/tests/test_runbook_itest_helpers.py), with the
# source line number kept beside every line. Nothing else differs.
# ---------------------------------------------------------------------------------------------
def section(lines, start):
    out, level, in_fence = [], None, False
    for no, ln in enumerate(lines, 1):
        if ln.startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"(#{1,6}) ", ln)
        if m and level is None:
            if ln.startswith(start):
                level = len(m.group(1))
            continue
        if m and level is not None and len(m.group(1)) <= level:
            break
        if level is not None:
            out.append((no, ln))
    need(level is not None, "runbook heading not found: %r" % start)
    return out


def host_commands(lines, start):
    cmds, cur, in_fence = [], None, False

    def flush():
        nonlocal cur
        if cur is not None:
            cmds.append(cur)
        cur = None

    for no, ln in section(lines, start):
        if ln.startswith("```"):
            in_fence = not in_fence
            flush()
        elif not in_fence:
            continue
        elif ln.startswith(PROMPT):
            flush()
            cur = [(no, ln[len(PROMPT):])]
        elif ln.startswith("guest$ "):
            flush()
        elif cur is not None:
            cur.append((no, ln))
    flush()
    return cmds


def frozen_rule(rule_text, runbook_text):
    """_host_commands as the frozen test file defines it, executed on the blob: the two functions are
    taken from the file's own source text; only what they read from is replaced (the runbook path by the
    blob's text, pytest.fail by an exception)."""
    tree = ast.parse(rule_text)
    wanted = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_section", "_host_commands"):
            wanted[node.name] = ast.get_source_segment(rule_text, node)
    need(set(wanted) == {"_section", "_host_commands"}, "the rule source does not define _section and _host_commands")

    class _Runbook:
        @staticmethod
        def read_text(encoding="utf-8"):
            return runbook_text

    class _Pytest:
        @staticmethod
        def fail(msg):
            raise AssertionError(msg)

    ns = {"re": re, "RUNBOOK": _Runbook, "pytest": _Pytest}
    exec(compile(wanted["_section"], RULE_SOURCE_PATH + ":_section", "exec"), ns)
    exec(compile(wanted["_host_commands"], RULE_SOURCE_PATH + ":_host_commands", "exec"), ns)
    return ns["_host_commands"]


def is_comment(text):
    return text.lstrip().startswith("#")


def only_defines(cmd_text):
    """The kind of a command that LOOKS like a definition and nothing else, or None: one assignment of a
    double-quoted string holding no substitution, or a text that opens with 'name() {' and ends with '}'.
    For a function this is a test of the head and of the last character only, not a parse: a text such as
    'f() { :; }; action; g() { :; }' would pass it. It holds for the five commands it is applied to (test
    7's definition lines); the proof that sourcing them runs one assignment and defines four functions,
    and nothing else, is the DEBUG-trap trace of g3_check_rows.sh.
    S3: kept as the battery's script had it and not called - no step file of tests 8 and 9 names
    'definitions' (the battery's t7-ditto.sh did), and the S3 checker carries no such trace.
    S4: likewise not called (t6.sh names no 'definitions')."""
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*="[^"$`\\\n]*"', cmd_text):
        return "assignment"
    m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\(\) \{", cmd_text)
    if m and cmd_text.rstrip().endswith("}"):
        return "function " + m.group(1)
    return None


def bash_n(data, name):
    try:
        p = subprocess.run(["bash", "-n"], input=data, capture_output=True)
    except OSError as exc:
        die("bash could not be started for the syntax check of %s: %s" % (name, exc))
    need(p.returncode == 0, "bash -n refuses %s: %s" % (name, p.stderr.decode("utf-8", "replace").strip()))


def forbidden_out(path):
    """Why PATH must not receive the row files, or None. The four trees of the execution host are refused
    under $HOME AND by path component: a dry run redirects HOME (to an isolated tree), and a guard that
    followed HOME alone would then let an --out typed into the real ~/egw-exec, ~/egw-tcg, ~/egw-images or
    ~/yocto through."""
    real = os.path.realpath(path)
    home = os.path.realpath(os.path.expanduser("~"))
    for sub in ("egw-exec", "egw-tcg", "egw-images", "yocto"):
        root = os.path.join(home, sub)
        if real == root or real.startswith(root + os.sep):
            return "inside %s" % root
    parts = real.replace("\\", "/").split("/")
    # S3: 'pb' is the read-only worktree at the merged commit ('cand' was the battery's).
    # S4 (brief, hard rule 1): 't6m' and 't6int', the read-only worktrees of this preparation, and the
    # sealed earlier preparations 's3prep', 's3bprep' and 'battery' (S/g3/battery) are refused as well.
    for bad in ("egw-exec", "egw-tcg", "egw-images", "yocto", "output_test", "ChatGPT", "cand", "pb",
                "t6m", "t6int", "s3prep", "s3bprep", "battery"):
        if bad in parts:
            return "inside a '%s' directory" % bad
    return None


def other_commit_rows(path):
    """S3: why PATH must not be written although it is no forbidden tree, or None: it holds a
    rows.manifest.json that is not of RUNBOOK_COMMIT (the battery's rows of 80e833f, sealed; S4: and S3's
    rows of 8e49261), or one that cannot be read. Such a directory is never overwritten, with --replace or
    without."""
    mf = os.path.join(path, "rows.manifest.json")
    if not os.path.exists(mf):
        return None
    try:
        with open(mf, encoding="utf-8") as fh:
            commit = (json.load(fh).get("runbook") or {}).get("commit")
    except (OSError, ValueError, AttributeError) as exc:
        return "its rows.manifest.json could not be read (%s)" % exc
    if commit != RUNBOOK_COMMIT:
        return "it holds the row files of another commit (%s)" % commit
    return None


def build(runbook_bytes, rule_bytes, script_bytes):
    need(sha(runbook_bytes) == RUNBOOK_SHA256,
         "the runbook is %s, not the frozen blob %s" % (sha(runbook_bytes), RUNBOOK_SHA256))
    need(b"\r" not in runbook_bytes, "the runbook blob holds a carriage return")
    text = runbook_bytes.decode("utf-8")
    lines = text.splitlines()
    need(text.endswith("\n") and len(lines) == RUNBOOK_LINES == text.count("\n") and lines == text.split("\n")[:-1],
         "the runbook does not split into %d newline-ended lines the same way for every reader" % RUNBOOK_LINES)

    # --- extraction, family by family -------------------------------------------------------
    rule_checked = False
    frozen = None
    if rule_bytes is not None:
        need(sha(rule_bytes) == RULE_SOURCE_SHA256,
             "the rule source is %s, not %s at %s" % (sha(rule_bytes), RULE_SOURCE_PATH, RUNBOOK_COMMIT[:7]))
        frozen = frozen_rule(rule_bytes.decode("utf-8"), text)
    all_cmds, by_line, head_of, heading_of = [], {}, {}, {}
    families = []
    for head, n_cmds, n_lines, sha16 in HEADS:
        cmds = host_commands(lines, head)
        plain = ["\n".join(t for _, t in c) for c in cmds]
        if frozen is not None:
            need(frozen(head) == plain, "the frozen _host_commands(%r) and this script's extraction differ" % head)
            rule_checked = True
        body = ("\n".join(plain) + "\n").encode("utf-8")
        need(len(cmds) == n_cmds and sum(len(c) for c in cmds) == n_lines and sha(body)[:16] == sha16,
             "%s: %d commands, %d lines, sha256 %s - the family extraction recorded %d, %d, %s"
             % (head, len(cmds), sum(len(c) for c in cmds), sha(body)[:16], n_cmds, n_lines, sha16))
        for c in cmds:
            all_cmds.append(c)
            for no, t in c:
                need(no not in by_line, "line %d extracted twice" % no)
                need(lines[no - 1] == (PROMPT + t if no == c[0][0] else t), "line %d: the text is not the blob's" % no)
                by_line[no] = t
                head_of[no] = c[0][0]
                heading_of[no] = head
        families.append({"heading": head, "commands": n_cmds, "text_lines": n_lines, "sha256": sha(body),
                         "host_command_starts": [c[0][0] for c in cmds]})

    whole = "\n".join(by_line[n] for n in sorted(by_line)) + "\n"
    # S4 (brief, stream ROWS): no suffix is added, and neither earlier session's suffix stands in the text.
    for earlier in EARLIER_SUFFIXES:
        need(earlier not in whole, "the extracted text holds '%s', the suffix of an earlier session's ids" % earlier)
    found = set(ITEST_LIKE.findall(whole))
    need(found == set(OLD_IDS),   # S4: test 6 names no itest id
         "the itest literals of the extracted text are not the request's: %s" % sorted(found))
    need(set(PLAN_LIKE.findall(whole)) == PLAN_LITERALS,
         "the plan-entry literals of the extracted text are not the expected ones: %s" % sorted(set(PLAN_LIKE.findall(whole))))
    # S4 (brief, stream ROWS: "no identifier substitution: controller_restart-r04 is the runbook's own literal").
    for lit, n in sorted(PLAN_COUNTS.items()):
        need(whole.count(lit) == n, "%s stands %d times in the extracted text, %d expected" % (lit, whole.count(lit), n))
    for no, marker in MARKERS:
        need(no in by_line and by_line[no].count(marker) == 1,
             "line %d does not hold, once, %r" % (no, marker))
    need(by_line[MARKERS[0][0]].startswith(MARKERS[0][1]) and by_line[MARKERS[2][0]].startswith(MARKERS[2][1]),
         "lines %d and %d do not open with the run id's assignment and the exactly-once check"
         % (MARKERS[0][0], MARKERS[2][0]))
    for old in OLD_IDS:
        need(whole.count(old) == TOTAL_COUNTS[old] == sum(1 for m in TOKEN.finditer(whole) if m.group(1) == old),
             "%s: %d occurrences as a string, %d as a token, %d expected"
             % (old, whole.count(old), sum(1 for m in TOKEN.finditer(whole) if m.group(1) == old), TOTAL_COUNTS[old]))

    # --- every extracted line lands in exactly one file ---------------------------------------
    use = collections.Counter(n for s in STEPS for n in s["lines"])
    twice = set()   # S3: no line stands in two files (the battery's test 7 definitions did)
    for no in sorted(by_line):
        need(use[no] == (2 if no in twice else 1), "line %d stands in %d step files" % (no, use[no]))
    need(set(use) == set(by_line), "a step file names a line that is not an extracted line: %s"
         % sorted(set(use) - set(by_line)))
    # S4 (brief, stream ROWS: "one file t6.sh, eight lines from 1421-1428").
    need(len(by_line) == 8 and sum(use.values()) == 8 and len(STEPS) == 1,
         "%d extracted lines in %d step files holding %d lines: 8, 1 and 8 expected"
         % (len(by_line), len(STEPS), sum(use.values())))
    for old, total in TOTAL_COUNTS.items():
        need(sum(s["subs"].get(old, 0) for s in STEPS) == total, "%s: the per-file counts do not add up to %d" % (old, total))

    outputs, files = collections.OrderedDict(), collections.OrderedDict()
    for s in STEPS:
        name, nums = s["file"], s["lines"]
        need(nums == sorted(nums) and len(set(nums)) == len(nums), "%s: line numbers not ascending" % name)
        inside = set(nums)
        starts = [n for n in nums if head_of[n] == n]
        need(starts == s["starts"], "%s: commands start on lines %s, not %s" % (name, starts, s["starts"]))
        # a command is never cut except before trailing comment lines, which run nothing
        orphan = []
        for c in all_cmds:
            cn = [no for no, _ in c]
            here = [no for no in cn if no in inside]
            if not here:
                continue
            if cn[0] in inside:
                need(here == cn[:len(here)], "%s: the command of line %d is not kept as one piece" % (name, cn[0]))
                rest = c[len(here):]
                need(all(is_comment(t) for _, t in rest),
                     "%s: the command of line %d is cut before a line that is not a comment" % (name, cn[0]))
                if rest:
                    kept = [t for _, t in c[:len(here)]]
                    need(not any("<<" in t or t.endswith("\\") for t in kept),
                         "%s: the command of line %d is cut inside a here-document or a continued line" % (name, cn[0]))
            else:
                need(all(is_comment(by_line[no]) for no in here),
                     "%s: lines %s belong to the command of line %d and are not comments" % (name, here, cn[0]))
                orphan += here
        defs = None
        if "definitions" in s:
            defs = []
            for c in all_cmds:
                cn = [no for no, _ in c]
                if cn[0] in s["definitions"]:
                    need(set(cn) <= set(s["definitions"]), "%s: a definition runs past line %d" % (name, s["definitions"][-1]))
                    kind = only_defines("\n".join(t for _, t in c))
                    need(kind is not None, "%s: the command of line %d does more than define" % (name, cn[0]))
                    defs.append({"lines": ranges(cn), "defines": kind})
            need(sorted(n for c in all_cmds if c[0][0] in s["definitions"] for n, _ in c) == s["definitions"],
                 "%s: the definition lines are not whole commands" % name)

        before = "\n".join(by_line[n] for n in nums) + "\n"
        counts, sub_lines, after_lines = collections.Counter(), collections.defaultdict(list), []
        for n in nums:
            def repl(m, n=n):
                counts[m.group(1)] += 1
                sub_lines[m.group(1)].append(n)
                return m.group(1) + SUFFIX
            after_lines.append(TOKEN.sub(repl, by_line[n]))
        after = "\n".join(after_lines) + "\n"
        need(dict(counts) == s["subs"], "%s: substitutions %s, expected %s" % (name, dict(counts), s["subs"]))
        # S4 (brief, stream ROWS: no substitution): the step file is the extracted text, byte for byte.
        need(SUFFIX is None and not s["subs"] and after == before,
             "%s: the step file differs from the extracted text (S4 substitutes nothing)" % name)
        for lit in UNCHANGED:
            need(after.count(lit) == before.count(lit)
                 and not any((lit + earlier) in after for earlier in EARLIER_SUFFIXES), "%s: %s was touched" % (name, lit))
        data = after.encode("utf-8")
        need(b"\r" not in data, "%s: a carriage return" % name)
        bash_n(data, name)
        diff = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="a/%s@%s lines %s (prompt removed)" % (RUNBOOK_PATH, RUNBOOK_COMMIT[:7], ranges(nums)),
            tofile="b/rows/%s" % name, n=0)).encode("utf-8")
        need((diff == b"") == (not s["subs"]), "%s: the diff and the substitution map disagree" % name)
        outputs[name] = data
        outputs[name + ".diff"] = diff
        entry = collections.OrderedDict()
        entry["row"] = s["row"]
        entry["session"] = s["session"]
        entry["step_order"] = s["order"]
        entry["kind"] = "runbook"
        entry["headings"] = sorted({heading_of[n] for n in nums}, key=[h[0] for h in HEADS].index)
        entry["source_line_numbers"] = nums
        entry["source_line_ranges"] = ranges(nums)
        entry["host_command_starts"] = starts
        entry["comment_lines_of_a_command_begun_in_another_file"] = orphan
        if defs is not None:
            entry["definitions_only"] = defs
        entry["lines"] = len(nums)
        entry["sha256_before"] = sha(before.encode("utf-8"))
        entry["sha256_after"] = sha(data)
        entry["bytes_before"] = len(before.encode("utf-8"))
        entry["bytes_after"] = len(data)
        entry["substitutions"] = [
            collections.OrderedDict([("old", old), ("new", old + SUFFIX), ("count", counts[old]),
                                     ("source_lines", sub_lines[old])])
            for old in OLD_IDS if counts[old]]
        entry["diff"] = name + ".diff"
        entry["diff_sha256"] = sha(diff)
        entry["diff_bytes"] = len(diff)
        entry["bash_n"] = "ok"
        entry["range_note"] = s["note"]
        files[name] = entry

    # S4: no prose-only step (S3's t9-exposure.sh and its constants are removed with test 9's row).

    # --- the manifest ------------------------------------------------------------------------
    order = [f for _, _, fs, _ in ROWS for f in fs]
    need(sorted(order) == sorted(files) and len(order) == len(set(order)), "the row table and the files disagree")
    for row, session, fs, _ in ROWS:
        for i, f in enumerate(fs, 1):
            need(files[f]["row"] == row and files[f]["session"] == session and files[f]["step_order"] == i,
                 "%s: row, session or step order differs from the row table" % f)
    manifest = collections.OrderedDict()
    manifest["schema"] = "g3-battery-rows-manifest/1"
    manifest["generated_by"] = "g3_extract_rows.py"
    manifest["generator_sha256"] = sha(script_bytes)
    manifest["runbook"] = collections.OrderedDict([
        ("commit", RUNBOOK_COMMIT), ("path", RUNBOOK_PATH), ("sha256", RUNBOOK_SHA256), ("lines", RUNBOOK_LINES)])
    manifest["extraction_rule"] = collections.OrderedDict([
        ("text", "the host$ commands of the fenced blocks under each heading, the 'host$ ' prompt removed and the "
                 "continuation lines kept as they are: _section and _host_commands of " + RULE_SOURCE_PATH),
        ("rule_source_sha256", RULE_SOURCE_SHA256),
        ("checked_against_the_frozen_functions", rule_checked),
        ("how", "the two functions were taken from the frozen file's own source text and executed on the blob; their "
                "output equals this script's extraction for the one heading" if rule_checked else
                "NOT checked in this execution (no --rule-source given): the script's own copy of the rule was used"),
    ])
    manifest["families"] = families
    # S4 (brief, stream ROWS: "substitution rule - none"): the form is kept, with nothing substituted.
    manifest["substitution_rule"] = collections.OrderedDict([
        ("suffix", SUFFIX),
        ("ids", []),
        ("unchanged", UNCHANGED),
        ("token", "none: session S4 substitutes no id"),
        ("asserted", "each step file is the extracted text, byte for byte (sha256_before equals sha256_after and the "
                     "diff is empty); the plan-entry literals of the extracted text are exactly controller_restart-r01 "
                     "(a comment of line 1421) and controller_restart-r04 (the run id, the runbook's own literal), "
                     "once each; the extracted text holds no itest id, no '-q1' and no '-q2' (the suffixes of the ids "
                     "of sessions S1 and S2 and of session S3, which are not reused)"),
    ])
    manifest["rows"] = [collections.OrderedDict([("row", r), ("session", se), ("steps", fs)] + ([("note", n)] if n else []))
                        for r, se, fs, n in ROWS]
    manifest["files"] = collections.OrderedDict((f, files[f]) for f in order)
    manifest["notes"] = [
        "Session S4 runs test 6 only (request of 2026-10-05, output_test/decisions/2026-10-05_g3-t6-session-request.md; "
        "criterion amended on 2026-10-05, LOG #C052; transition rule 1a-option-a-2026-10-05, LOG #C053). The rows of "
        "tests 1 to 5 and 7 to 9 (sessions S1, S2 and S3, the '-q1' and '-q2' ids) are not extracted here, and no "
        "earlier id is reused. Nothing is substituted: controller_restart-r04 is the runbook's own literal.",
        "Line ranges. A step file holds each host$ command whole, with its continuation lines (trailing comment "
        "lines), so its source_line_numbers are the lines of the text. Where the lines on which commands START and "
        "the text differ the file's range_note says why (in S4 they do not: eight one-line commands).",
        "Every line the rule extracts under the heading stands in exactly one step file (8 extracted lines, test "
        "6's whole fenced block 1421-1428; 8 lines in t6.sh). No command is cut between files.",
        "Test 6's block against the battery's (80e833f, lines 1421-1427, the t6.sh that ran in session S2): line 1 "
        "changed (the run id controller_restart-r04 and its comment), line 5 changed (the harness's "
        "--restart-transition-rule 1a-option-a-2026-10-05, a read-only print of the manifest's "
        "resources_transition_rows, and its comment), line 7 added (acceptance --exactly-once on the post-drain "
        "copy, only when T6=ok); the other five lines are unchanged.",
        "Not extracted, by the rule: line 1260 (the section's preamble under '## 7.', outside the heading: it "
        "sources ~/egw-tcg/.env and ~/egw-tcg/itest-helpers.sh). The steps script's hx runs a superset of it, "
        "HOST_PRE of the clean clone's tools/session/guest_common.sh: the execution venv activated, ~/egw-tcg/.env "
        "exported, EGW_CLONE set to the clean clone, the DEPLOYED ~/egw-tcg/itest-helpers.sh and ~/egw-tcg/tunnel.sh "
        "sourced (files of the host, not of the clone), and the tunnel checked or reopened.",
        "The step file holds the extracted lines and nothing else: no header, no added line. It holds no 'STOP:' "
        "text of its own: a line of its console that opens with 'STOP:' is printed by the helpers' stop.",
        "A <file>.diff is the unified diff (no context lines) between the extracted text and the step file; it is "
        "empty when the file has no substitution, as t6.sh.diff is (and as the battery's t6.sh.diff was).",
        "Every file is UTF-8 with LF line endings and one final newline, and passed 'bash -n'.",
        "Independent check: g3_check_rows.sh (beside this script) restates the line range and the literals on its "
        "own and compares t6.sh byte for byte with the blob's lines, cut with 'awk' and 'sed'. It reads the blob "
        "from the clean clone with 'git show' (and then also requires that clone at 1fd9792 and clean), or, before "
        "the clone has moved to that commit, from a file given with --blob whose sha256 it asserts (it then shows "
        "nothing about the clone).",
    ]
    outputs["rows.manifest.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return outputs, manifest


def main():
    ap = argparse.ArgumentParser(description="Write the row files of G3 session S4 (test 6) from the merged "
                                             "runbook blob.")
    ap.add_argument("--runbook", required=True, help="the runbook blob of 1fd9792: a path, or - for stdin")
    ap.add_argument("--rule-source", help="src/tests/test_runbook_itest_helpers.py of 1fd9792 (optional: the "
                                          "extraction is then also checked against the frozen functions)")
    ap.add_argument("--out", required=True, help="the directory of the row files")
    ap.add_argument("--check", action="store_true", help="write nothing: compare what would be written with <out>")
    ap.add_argument("--replace", action="store_true", help="overwrite row files that exist and differ")
    args = ap.parse_args()

    runbook = sys.stdin.buffer.read() if args.runbook == "-" else open(args.runbook, "rb").read()
    rule = open(args.rule_source, "rb").read() if args.rule_source else None
    with open(os.path.abspath(__file__), "rb") as fh:
        script = fh.read()
    outputs, manifest = build(runbook, rule, script)

    why = forbidden_out(args.out)
    need(why is None, "the output directory %s is %s: nothing is written there" % (args.out, why))

    if args.check:
        bad = 0
        for name, data in outputs.items():
            path = os.path.join(args.out, name)
            try:
                same = open(path, "rb").read() == data
            except OSError:
                same = False
            if not same:
                bad += 1
                print("DIFFERS or missing: %s" % name)
        extra = sorted(set(os.listdir(args.out)) - set(outputs)) if os.path.isdir(args.out) else []
        for name in extra:
            print("not a row file: %s" % name)
        print("check: %d files compared, %d differ or are missing, %d other files in %s"
              % (len(outputs), bad, len(extra), args.out))
        sys.exit(1 if bad or extra else 0)

    why = other_commit_rows(args.out)
    need(why is None, "the output directory %s is not written: %s" % (args.out, why))
    os.makedirs(args.out, exist_ok=True)
    clash = []
    for name, data in outputs.items():
        path = os.path.join(args.out, name)
        if os.path.exists(path) and open(path, "rb").read() != data:
            clash.append(name)
    need(not clash or args.replace, "these files exist in %s and differ (use --replace): %s" % (args.out, ", ".join(clash)))
    for name, data in outputs.items():
        with open(os.path.join(args.out, name), "wb") as fh:
            fh.write(data)

    print("runbook %s at %s: sha256 %s, %d lines" % (RUNBOOK_PATH, RUNBOOK_COMMIT[:7], RUNBOOK_SHA256, RUNBOOK_LINES))
    print("rule checked against the frozen _host_commands: %s" % manifest["extraction_rule"]["checked_against_the_frozen_functions"])
    for name, e in manifest["files"].items():
        subs = ", ".join("%s x%d" % (x["new"], x["count"]) for x in e["substitutions"]) or "-"
        print("%-24s %-10s %s step %d  lines %-28s before %s after %s  subs: %s"
              % (name, e["row"], e["session"], e["step_order"], e.get("source_line_ranges", e["kind"]),
                 (e["sha256_before"] or "-")[:12], e["sha256_after"][:12], subs))
    print("written: %d files in %s (manifest sha256 %s)" % (len(outputs), args.out, sha(outputs["rows.manifest.json"])))


if __name__ == "__main__":
    main()
