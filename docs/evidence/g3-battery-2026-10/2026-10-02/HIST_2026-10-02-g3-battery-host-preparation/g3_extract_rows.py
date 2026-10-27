#!/usr/bin/env python3
"""G3 qualifying battery - host preparation, part 2: the row files.

Reads the runbook blob of the frozen commit (80e833f, docs/setup/qemu_integrated_gateway.md),
asserts its sha256, extracts the host$ commands of each section-7 test with the rule of
_host_commands in src/tests/test_runbook_itest_helpers.py (the "host$ " prompt removed, the
continuation lines kept as they are), splits them into the step files of the battery by
SOURCE LINE NUMBER, substitutes ONLY the run ids of the decision packet (section 2: every
runbook literal gains "-q1") with an asserted number of occurrences per file, and writes:

  <out>/<step>.sh          one LF-only bash text per step (sourced by the steps script)
  <out>/<step>.sh.diff     the unified ids-only diff of that step (empty when nothing changed)
  <out>/rows.manifest.json per file: row, step order, source line numbers, sha256 of the
                           extracted text before and after the substitution, each substitution
                           with its count

Two steps have no fenced runbook line (prose only): t1-harness-analyze.sh (runbook line 1320)
and t9-exposure.sh (runbook line 1529). They are written from the constants below, with the
runbook sentence each derives from quoted in a comment at the top of the file; the sentence is
asserted to stand, verbatim, on that line of the blob.

The script reads its two inputs and writes only inside <out>. It refuses an <out> inside the
frozen clone, the run directory, the image and build trees, output_test, ChatGPT or the
read-only worktree (by path component as well as under $HOME, so a redirected HOME does not
lift the refusal). It starts nothing and contacts nothing.

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

RUNBOOK_COMMIT = "80e833f44f647fe9cd8f5e99d3abf3c444de95aa"
RUNBOOK_PATH = "docs/setup/qemu_integrated_gateway.md"
RUNBOOK_SHA256 = "c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae"
RUNBOOK_LINES = 1614
RULE_SOURCE_PATH = "src/tests/test_runbook_itest_helpers.py"
RULE_SOURCE_SHA256 = "da8d31ddeb4f53c057d279a01964ef6464152660368cd08ef5c8ab6767700489"
SUFFIX = "-q1"
PROMPT = "host$ "

# The ten section-7 headings whose fenced host$ commands make the battery, as the runbook's own
# tests name them, with the number of commands, the number of text lines and the first 16 hex
# digits of the sha256 of the joined text that the family extraction of 2026-10-01
# (extract_families.py; fam-A.md, fam-B.md, fam-C.md) recorded for each.
HEADS = [
    ("### Test 1", 5, 5, "027d4c7c148be544"),
    ("### Test 2", 3, 13, "0526d9691e25d570"),
    ("### Test 3", 5, 29, "e593ab0e8f045d61"),
    ("### Test 4", 10, 10, "dbc1ce7d030a3972"),
    ("### Test 5", 3, 3, "3f23d8bef765b3e4"),
    ("### Test 6", 7, 7, "ebc9700c8968b633"),
    ("### Test 7", 9, 23, "df7366ab5369088b"),
    ("### Repeat of test 7 for Ditto", 4, 4, "ae8becc19b6dbf24"),
    ("### Test 8", 5, 7, "235a4090a8ff9169"),
    ("### Test 9", 10, 26, "9518fefe751c3d93"),
]

# Packet section 2: the only tokens that change. Each gains SUFFIX.
OLD_IDS = [
    "itest-smoke-$i",
    "itest-3dev-01",
    "itest-invalid-01",
    "itest-dup-01",
    "itest-dup-02",
    "itest-dropout-01",
    "itest-mongo-fault-01",
    "itest-ditto-fault-01",
    "itest-reboot",
    "itest-post-reboot-01",
    "itest-tls-wrongca",
    "itest-auth-wrongpw",
    "itest-notls",
]
# Never changed: the two plan entries, the ACL probe's stamped id and the replay directory's name.
UNCHANGED = ["nominal-r02", "controller_restart-r03", "itest-acl-$T", "itest-replay"]
# How many times each old id stands in the whole extracted text (T8's prefix: 8, lines 1486 and 1491).
TOTAL_COUNTS = {
    "itest-smoke-$i": 2,
    "itest-3dev-01": 1,
    "itest-invalid-01": 1,
    "itest-dup-01": 1,
    "itest-dup-02": 1,
    "itest-dropout-01": 1,
    "itest-mongo-fault-01": 1,
    "itest-ditto-fault-01": 1,
    "itest-reboot": 8,
    "itest-post-reboot-01": 1,
    "itest-tls-wrongca": 1,
    "itest-auth-wrongpw": 4,
    "itest-notls": 3,
}
PLAN_LITERALS = {"nominal-r01", "nominal-r02", "nominal-r03", "controller_restart-r01", "controller_restart-r03"}

# A token: the id not preceded by a name character and not followed by a name character or a
# hyphen, so that an id is never matched inside a longer one. A preceding hyphen is allowed: the
# broker's client id is "egw-simulator-<run id>" (the comment of line 1509 names it).
TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])("
    + "|".join(re.escape(x) for x in sorted(OLD_IDS, key=len, reverse=True))
    + r")(?![A-Za-z0-9_-])"
)
ITEST_LIKE = re.compile(r"itest-[A-Za-z0-9$-]*[A-Za-z0-9$]")
PLAN_LIKE = re.compile(r"(?:nominal|controller_restart|smoke_sequence)-r[0-9][0-9]")


def R(a, b=None):
    return list(range(a, (a if b is None else b) + 1))


# The step files, in the order of the battery. Per file: row, session, order within the row, the
# source line numbers of the extracted text, the lines on which a host$ command starts, the
# asserted substitution counts, and the reason for the line range where the work order's named
# range (the lines on which commands start) and the extracted text differ.
STEPS = [
    dict(file="t1-smokes.sh", row="t1-smokes", session="S1", order=1, lines=R(1300), starts=[1300],
         subs={"itest-smoke-$i": 2},
         note="One command, line 1300. The id stands twice: run_test's argument and the STOP text; "
              "'$i-q1' expands as ${i} followed by '-q1', a hyphen not being a name character."),
    dict(file="t1-harness.sh", row="t1-harness", session="S1", order=1, lines=R(1310, 1313), starts=R(1310, 1313),
         subs={},
         note="Lines 1310-1313, four one-line commands. Nothing is substituted: nominal-r02 is a plan entry."),
    dict(file="t2.sh", row="t2", session="S1", order=1, lines=R(1325, 1337), starts=[1325, 1326, 1327],
         subs={"itest-3dev-01": 1},
         note="Commands start on lines 1325-1327; the third carries its here-document, lines 1328-1337, "
              "kept as continuation lines by the rule: the text is lines 1325-1337."),
    dict(file="t3.sh", row="t3", session="S1", order=1, lines=R(1345, 1373), starts=[1345, 1346, 1347, 1348, 1358],
         subs={"itest-invalid-01": 1},
         note="Commands start on lines 1345-1348 and 1358; the fourth carries lines 1349-1357 and the fifth lines "
              "1359-1373 (two here-documents): the text is lines 1345-1373, one fenced block."),
    dict(file="t4-replay.sh", row="t4-replay", session="S1", order=1, lines=R(1383, 1391), starts=R(1383, 1391),
         subs={"itest-dup-01": 1},
         note="Lines 1383-1391, nine one-line commands. The directory name itest-replay (lines 1384 and 1387) "
              "is not an id and is not changed."),
    dict(file="t4-reset.sh", row="t4-reset", session="S1", order=1, lines=R(1399), starts=[1399],
         subs={"itest-dup-02": 1},
         note="Line 1399, the sequence reset's own fenced block."),
    dict(file="t5.sh", row="t5", session="S1", order=1, lines=R(1407, 1409), starts=R(1407, 1409),
         subs={"itest-dropout-01": 1},
         note="Lines 1407-1409, three one-line commands."),
    dict(file="t6.sh", row="t6", session="S2", order=1, lines=R(1421, 1427), starts=R(1421, 1427),
         subs={},
         note="Lines 1421-1427, seven one-line commands. Nothing is substituted: controller_restart-r03 is a plan entry."),
    dict(file="t7-mongo.sh", row="t7-mongo", session="S2", order=1, lines=R(1439, 1461),
         starts=[1439, 1440, 1441, 1442, 1443, 1458, 1459, 1460, 1461],
         subs={"itest-mongo-fault-01": 1},
         note="Commands start on lines 1439-1443 and 1458-1461; lines 1444-1457 are the body of fault(), the "
              "continuation lines of the command of line 1443: the text is lines 1439-1461, the whole fenced block."),
    dict(file="t7-ditto.sh", row="t7-ditto", session="S2", order=1, lines=R(1440, 1458) + R(1477, 1480),
         starts=[1440, 1441, 1442, 1443, 1458, 1477, 1478, 1479, 1480],
         subs={"itest-ditto-fault-01": 1},
         definitions=R(1440, 1458),
         note="Opens with test 7's definitions, lines 1440-1458, verbatim: the assignment of DC (1440) and the "
              "functions svc_state (1441), fault_recover (1442), fault (1443-1457) and readyp (1458). Each of the "
              "five commands only defines (asserted: one plain assignment of a double-quoted string without a "
              "substitution, four 'name() {' definitions), so nothing acts before line 1477. Line 1439 (R and SVC "
              "of the MongoDB sub-check) is left out: line 1477 sets both for Ditto. Lines 1459-1461 (the test "
              "line and the two evaluation lines of the MongoDB sub-check) are left out: lines 1478-1480 are the "
              "same lines for Ditto. These nineteen definition lines also stand in t7-mongo.sh; no id is in them."),
    dict(file="t8-a-reboot.sh", row="t8", session="S2", order=1, lines=R(1486, 1488), starts=[1486],
         subs={"itest-reboot": 3},
         note="The command of line 1486 with its two continuation lines 1487-1488, which the rule keeps: they are "
              "comments (the runbook's instruction to re-launch with the same data disk, done by the steps script "
              "between this step and the next) and run nothing. The work order names line 1486 only."),
    dict(file="t8-b-return.sh", row="t8", session="S2", order=2, lines=R(1489, 1490), starts=[1489, 1490],
         subs={},
         note="Lines 1489-1490, two one-line commands (the guest's state after the re-launch; the tunnel reopened)."),
    dict(file="t8-c-snapshot.sh", row="t8", session="S2", order=3, lines=R(1491), starts=[1491],
         subs={"itest-reboot": 5},
         note="Line 1491. With the three of line 1486 these are the eight literals of T8's prefix, changed together."),
    dict(file="t8-d-smoke.sh", row="t8", session="S2", order=4, lines=R(1492), starts=[1492],
         subs={"itest-post-reboot-01": 1},
         note="Line 1492."),
    dict(file="t9-a.sh", row="t9", session="S2", order=1, lines=R(1501, 1502), starts=[1501, 1502],
         subs={"itest-tls-wrongca": 1},
         note="Lines 1501-1502. Line 1500, the comment '# (a) wrong CA -> TLS verification fails', stands in the "
              "fence before the first host$ line and is dropped by the rule, so it is in no file."),
    dict(file="t9-b.sh", row="t9", session="S2", order=2, lines=R(1503, 1516), starts=[1515, 1516],
         subs={"itest-auth-wrongpw": 4},
         note="Lines 1503-1514 are comments: by the rule they are continuation lines of the command of line 1502 "
              "((a)'s simulator), and by their text they describe (b) and (c); they run nothing and are placed "
              "here by source line. Commands: lines 1515 and 1516. The id stands four times, once in the comment "
              "of line 1509 inside the client id 'egw-simulator-itest-auth-wrongpw', which changes with it."),
    dict(file="t9-c.sh", row="t9", session="S2", order=3, lines=R(1517, 1519), starts=[1518, 1519],
         subs={"itest-notls": 3},
         note="Line 1517 is a comment, by the rule a continuation line of the command of line 1516. Commands: "
              "lines 1518 and 1519."),
    dict(file="t9-de.sh", row="t9", session="S2", order=4, lines=R(1520, 1526), starts=[1523, 1524, 1525, 1526],
         subs={},
         note="Lines 1520-1522 are comments, by the rule continuation lines of the command of line 1519. Commands: "
              "lines 1523-1526. Nothing is substituted: itest-acl-$T is fresh by its UTC stamp."),
]

ROWS = [
    ("t1-smokes", "S1", ["t1-smokes.sh"], None),
    ("t1-harness", "S1", ["t1-harness.sh", "t1-harness-analyze.sh"],
     "t1-harness-analyze.sh is the prose-only step of runbook line 1320."),
    ("t2", "S1", ["t2.sh"], None),
    ("t3", "S1", ["t3.sh"], None),
    ("t4-replay", "S1", ["t4-replay.sh"], None),
    ("t4-reset", "S1", ["t4-reset.sh"], None),
    ("t5", "S1", ["t5.sh"], None),
    ("t6", "S2", ["t6.sh"], None),
    ("t7-mongo", "S2", ["t7-mongo.sh"], None),
    ("t7-ditto", "S2", ["t7-ditto.sh"], None),
    ("t8", "S2", ["t8-a-reboot.sh", "t8-b-return.sh", "t8-c-snapshot.sh", "t8-d-smoke.sh"],
     "Between t8-a-reboot.sh and t8-b-return.sh the steps script waits for the first QEMU to exit and re-launches "
     "(no row file). t8-c-snapshot.sh only if the tunnel is up; t8-d-smoke.sh only after REBOOT SHOWN and no STOP:."),
    ("t9", "S2", ["t9-a.sh", "t9-b.sh", "t9-c.sh", "t9-de.sh", "t9-exposure.sh"],
     "Each of t9-a, t9-b, t9-c, t9-de only if the one before printed no STOP:. t9-exposure.sh is the prose-only "
     "step of runbook line 1529; the steps script runs it likewise only if t9-de printed no STOP: (runbook "
     "line 15), so after a STOP of (d)+(e) the three read-only exposure reads are not in the package."),
]

# ---------------------------------------------------------------------------------------------
# The two prose-only steps. Constants of this script, not runbook lines.
# ---------------------------------------------------------------------------------------------
T1_LINE = 1320
T1_QUOTE = (
    'The harness applies the confirmation deadline itself (manifest `confirmation_deadline_clock_domain: '
    '"controller"`), so no `pre`/`post` is used here; read the result with `python -m egw_experiments analyze '
    '--base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json` and the columns '
    '`confirmation_deadline_source`, `sent_valid`, `delivered_unique`, `lost`, `late_confirmations`, '
    '`double_accepted` of `~/egw-tcg/pilot/results/processed/per_run.csv`'
)
T1_ANALYZE_CMD = (
    "python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json"
)
T1_ANALYZE_SAME_AS_LINE = 1427   # test 6's own fenced analyze line: the same command, character for character
T1_COLUMNS = ["confirmation_deadline_source", "sent_valid", "delivered_unique", "lost", "late_confirmations",
              "double_accepted"]
T1_PER_RUN = "~/egw-tcg/pilot/results/processed/per_run.csv"
T1_PLAN_ENTRY = "nominal-r02"

T1_BODY = r'''python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json; echo "analyze exit=$?"
python3 - ~/egw-tcg/pilot/results/processed/per_run.csv nominal-r02 <<'EOF'
import csv, sys
path, rid = sys.argv[1], sys.argv[2]
cols = ("confirmation_deadline_source", "sent_valid", "delivered_unique", "lost", "late_confirmations", "double_accepted")
with open(path, newline="", encoding="utf-8") as fh:
    rows = [r for r in csv.DictReader(fh) if r.get("run_id") == rid]
print("per_run.csv:", path, "- rows of", rid + ":", len(rows))
for r in rows:
    print(rid, " ".join("%s=%s" % (c, r.get(c)) for c in cols))
sys.exit(0 if len(rows) == 1 else 1)
EOF
echo "per_run read exit=$? (0: exactly one row of nominal-r02 was printed; anything else: none, several, or the file was not read)"
'''

T9_LINE = 1529
T9_QUOTE = (
    'Also keep `ssh -p 2222 root@127.0.0.1` refused and `nmap`-free port evidence: `ss -ltn` on the host shows '
    'only 2222 and 8883 forwarded by QEMU; inside the guest `docker ps` shows `127.0.0.1:8080` and '
    '`127.0.0.1:8000` bindings and MongoDB with no published port (work order item 5).'
)
T9_BODY = r'''# (1) root over ssh on the forwarded port 2222. BatchMode: no prompt, so no password is ever asked or typed;
#     the host key is checked against the runbook's pinned file and nothing is added to it; the one key the
#     guest accepts for 'egw' is the key offered. Only "Permission denied" counts as the refusal: "Host key
#     verification failed", a timeout or "Connection refused" is no evidence, and exit 0 is a root login.
ssh -n -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o UserKnownHostsFile="$HOME/.ssh/known_hosts_egw_tcg" -o IdentitiesOnly=yes -i "$HOME/.ssh/egw_campaign" -p 2222 root@127.0.0.1 true; echo "root ssh exit=$?"
# (2) the host's listening TCP sockets with their owning process. Expected: 2222 and 8883 forwarded by QEMU;
#     8000 and 8080 belong to this project's own ssh tunnel master (runbook 5.7), not to QEMU.
ss -ltnp; echo "ss exit=$?"
# (3) the guest's published container ports, read over ssh. Expected: bindings on 127.0.0.1:8080 and
#     127.0.0.1:8000, and MongoDB with no published port.
ssh -n egw-tcg 'docker ps --format "{{.Names}} {{.Ports}}"'; echo "docker ps exit=$?"
'''

OPERATOR_T9 = ('`ssh -n -o BatchMode=yes ... -p 2222 root@127.0.0.1 true`, where only "Permission denied" counts; '
               '`ss -ltnp`; the guest\'s `docker ps` ports')


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
    and nothing else, is the DEBUG-trap trace of g3_check_rows.sh."""
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
    for bad in ("egw-exec", "egw-tcg", "egw-images", "yocto", "output_test", "ChatGPT", "cand"):
        if bad in parts:
            return "inside a '%s' directory" % bad
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
    need(SUFFIX not in whole, "the extracted text already holds '%s'" % SUFFIX)
    found = set(ITEST_LIKE.findall(whole))
    need(found == set(OLD_IDS) | {"itest-acl-$T", "itest-replay"},
         "the itest literals of the extracted text are not the packet's: %s" % sorted(found))
    need(set(PLAN_LIKE.findall(whole)) == PLAN_LITERALS,
         "the plan-entry literals of the extracted text are not the expected ones: %s" % sorted(set(PLAN_LIKE.findall(whole))))
    for old in OLD_IDS:
        need(whole.count(old) == TOTAL_COUNTS[old] == sum(1 for m in TOKEN.finditer(whole) if m.group(1) == old),
             "%s: %d occurrences as a string, %d as a token, %d expected"
             % (old, whole.count(old), sum(1 for m in TOKEN.finditer(whole) if m.group(1) == old), TOTAL_COUNTS[old]))

    # --- every extracted line lands in exactly one file (test 7's definitions in two) --------
    use = collections.Counter(n for s in STEPS for n in s["lines"])
    twice = set(R(1440, 1458))
    for no in sorted(by_line):
        need(use[no] == (2 if no in twice else 1), "line %d stands in %d step files" % (no, use[no]))
    need(set(use) == set(by_line), "a step file names a line that is not an extracted line: %s"
         % sorted(set(use) - set(by_line)))
    need(len(by_line) == 127 and sum(use.values()) == 146 and len(STEPS) == 18,
         "%d extracted lines in %d step files holding %d lines: 127, 18 and 146 expected"
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
        for old in OLD_IDS:
            want = s["subs"].get(old, 0)
            need(before.count(old) == want, "%s: %s stands %d times as a string, %d expected" % (name, old, before.count(old), want))
            need(after.count(old + SUFFIX) == want and after.count(old) == want,
                 "%s: after the substitution %s is not everywhere followed by %s" % (name, old, SUFFIX))
        need(after.count(SUFFIX) == sum(s["subs"].values()) and after.replace(SUFFIX, "") == before,
             "%s: the substituted text differs from the extracted text by more than the ids" % name)
        for lit in UNCHANGED:
            need(after.count(lit) == before.count(lit) and (lit + SUFFIX) not in after, "%s: %s was touched" % (name, lit))
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

    # --- the two prose-only steps ------------------------------------------------------------
    l1320, l1529 = lines[T1_LINE - 1], lines[T9_LINE - 1]
    need(T1_QUOTE in l1320, "runbook line %d does not hold the sentence quoted for t1-harness-analyze.sh" % T1_LINE)
    need(T1_ANALYZE_CMD in T1_QUOTE and by_line[T1_ANALYZE_SAME_AS_LINE] == T1_ANALYZE_CMD,
         "the analyze command is not the one of lines %d and %d" % (T1_LINE, T1_ANALYZE_SAME_AS_LINE))
    need(all("`%s`" % c in T1_QUOTE for c in T1_COLUMNS) and "`%s`" % T1_PER_RUN in T1_QUOTE,
         "a column or the per_run.csv path of t1-harness-analyze.sh is not named by line %d" % T1_LINE)
    need(T1_BODY.startswith(T1_ANALYZE_CMD + ";") and all('"%s"' % c in T1_BODY for c in T1_COLUMNS)
         and (" " + T1_PER_RUN + " " + T1_PLAN_ENTRY + " ") in T1_BODY and T1_BODY.count(T1_PLAN_ENTRY) == 2,
         "the body of t1-harness-analyze.sh and its constants disagree")
    need(l1529.endswith(T9_QUOTE), "runbook line %d does not end with the sentence quoted for t9-exposure.sh" % T9_LINE)
    prose = [
        ("t1-harness-analyze.sh", "t1-harness", "S1", 2, T1_LINE, T1_QUOTE,
         "# G3 battery, row t1-harness, step 2 of 2: PROSE-ONLY step. No fenced runbook line exists for it.\n"
         "# Written by g3_extract_rows.py from a constant of that script; nothing is extracted and no id is substituted.\n"
         "# It derives from %s at %s (sha256 %s), line %d, which says:\n"
         "#   \"%s\"\n"
         "# Decision packet of 2026-10-01 (revision 2), execution choice \"Prose-only steps\": T1's analyze read (line 1320)\n"
         "# is run and recorded. The plan entry is nominal-r02 (decision 1b; packet section 2, row 2). The analyze command\n"
         "# is, character for character, the runbook's own fenced line %d (test 6). The second command prints the six\n"
         "# columns line 1320 names from this run's row of per_run.csv. Both print; neither judges.\n"
         % (RUNBOOK_PATH, RUNBOOK_COMMIT[:7], RUNBOOK_SHA256, T1_LINE, T1_QUOTE, T1_ANALYZE_SAME_AS_LINE)
         + T1_BODY,
         "The analyze command of line 1320 (the same as the fenced line 1427) and a read of the six columns line "
         "1320 names from nominal-r02's row of processed/per_run.csv. A constant of the script, not an extraction."),
        ("t9-exposure.sh", "t9", "S2", 5, T9_LINE, T9_QUOTE,
         "# G3 battery, row t9, step 5 of 5: PROSE-ONLY step. No fenced runbook line exists for it.\n"
         "# Written by g3_extract_rows.py from a constant of that script; nothing is extracted and no id is substituted.\n"
         "# It derives from %s at %s (sha256 %s), line %d (the last sentence of test 9's Expected), which says:\n"
         "#   \"%s\"\n"
         "# Decision packet of 2026-10-01 (revision 2), execution choice \"Prose-only steps\": T9's three exposure checks\n"
         "# are run and recorded, read-only. Operator procedure, T9: %s.\n"
         "# The three commands only read, each prints what it read and its exit status, and none judges.\n"
         % (RUNBOOK_PATH, RUNBOOK_COMMIT[:7], RUNBOOK_SHA256, T9_LINE, T9_QUOTE, OPERATOR_T9)
         + T9_BODY,
         "The three exposure checks of the last sentence of line 1529 in the non-interactive, read-only forms of the "
         "packet's execution choices: root over ssh on 2222 with -n and BatchMode=yes (only 'Permission denied' "
         "counts), ss -ltnp on the host, the guest's docker ps port bindings through ssh egw-tcg. A constant of the "
         "script, not an extraction."),
    ]
    for name, row, session, order, line_no, quote, body, note in prose:
        data = body.encode("utf-8")
        need(b"\r" not in data and body.endswith("\n") and not body.endswith("\n\n"), "%s: line endings" % name)
        need(not TOKEN.search(body) and SUFFIX not in body, "%s: a prose-only step holds a battery id" % name)
        bash_n(data, name)
        outputs[name] = data
        entry = collections.OrderedDict()
        entry["row"] = row
        entry["session"] = session
        entry["step_order"] = order
        entry["kind"] = "prose-only, runbook line %d" % line_no
        entry["source_line_numbers"] = [line_no]
        entry["derived_from_sentence"] = quote
        entry["lines"] = body.count("\n")
        entry["sha256_before"] = None
        entry["sha256_after"] = sha(data)
        entry["bytes_after"] = len(data)
        entry["substitutions"] = []
        entry["diff"] = None
        entry["bash_n"] = "ok"
        entry["range_note"] = note
        files[name] = entry

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
                "output equals this script's extraction for each of the ten headings" if rule_checked else
                "NOT checked in this execution (no --rule-source given): the script's own copy of the rule was used"),
    ])
    manifest["families"] = families
    manifest["substitution_rule"] = collections.OrderedDict([
        ("suffix", SUFFIX),
        ("ids", [collections.OrderedDict([("old", o), ("new", o + SUFFIX), ("occurrences", TOTAL_COUNTS[o])]) for o in OLD_IDS]),
        ("unchanged", UNCHANGED),
        ("token", "an id not preceded by [A-Za-z0-9_] and not followed by [A-Za-z0-9_-]; every occurrence of each id "
                  "as a plain string is such a token (asserted), so none is left behind and none is matched inside "
                  "a longer id"),
        ("asserted", "per file the count of each id; the text after the substitution with every '-q1' removed is the "
                     "extracted text; the unchanged literals are untouched; the extracted text held no '-q1'"),
    ])
    manifest["rows"] = [collections.OrderedDict([("row", r), ("session", se), ("steps", fs)] + ([("note", n)] if n else []))
                        for r, se, fs, n in ROWS]
    manifest["files"] = collections.OrderedDict((f, files[f]) for f in order)
    manifest["notes"] = [
        "Line ranges. The work order names the lines on which host$ commands START; a step file holds each command "
        "whole, with its continuation lines (here-documents, a function body, trailing comment lines), so its "
        "source_line_numbers are the lines of the text. Where the two differ the file's range_note says why.",
        "Every line the rule extracts under the ten headings stands in exactly one step file, except test 7's "
        "definition lines 1440-1458, which stand in t7-mongo.sh and again at the top of t7-ditto.sh (127 extracted "
        "lines; 146 lines in the eighteen runbook step files).",
        "A command is cut between two files only before trailing comment lines (asserted): lines 1503-1514 (after "
        "the command of line 1502), 1517 (after 1516) and 1520-1522 (after 1519). Comments run nothing.",
        "Not extracted, by the rule: line 1500 (a comment before the first host$ line of test 9's fence) and line "
        "1260 (the section's preamble under '## 7.', outside the ten headings: it sources ~/egw-tcg/.env and "
        "~/egw-tcg/itest-helpers.sh). The steps script's hx runs a superset of it, HOST_PRE of the clean clone's "
        "tools/session/guest_common.sh: the execution venv activated, ~/egw-tcg/.env exported, EGW_CLONE set to "
        "the clean clone, the DEPLOYED ~/egw-tcg/itest-helpers.sh and ~/egw-tcg/tunnel.sh sourced (files of the "
        "host, not of the clone), and the tunnel checked or reopened.",
        "The step files of kind 'runbook' hold the extracted lines and nothing else: no header, no added line. "
        "The two prose-only files are constants of the script and open with the runbook sentence they derive from.",
        "A <file>.diff is the unified diff (no context lines) between the extracted text and the step file; its "
        "line numbers count the lines of the extracted text, and the header names the runbook lines. It is empty "
        "when the file has no substitution; the prose-only files have none.",
        "Every file is UTF-8 with LF line endings and one final newline, and passed 'bash -n'.",
        "Independent check: g3_check_rows.sh (beside this script) restates the line ranges and the ids on its own "
        "and compares each runbook step file, with every '-q1' removed, byte for byte with the blob's lines read "
        "by 'git show', 'awk' and 'sed'; it also traces that the first nineteen lines of t7-ditto.sh run one "
        "assignment and define four functions, and nothing else.",
    ]
    outputs["rows.manifest.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return outputs, manifest


def main():
    ap = argparse.ArgumentParser(description="Write the G3 battery's row files from the frozen runbook blob.")
    ap.add_argument("--runbook", required=True, help="the runbook blob of 80e833f: a path, or - for stdin")
    ap.add_argument("--rule-source", help="src/tests/test_runbook_itest_helpers.py of 80e833f (optional: the "
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
