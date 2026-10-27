#!/usr/bin/env python3
"""Cross-check of stream ROWS: does rows/rows.manifest.json answer the steps script's own manifest tool?

The steps script (g3_battery.sh) carries a Python text, MANIFEST_PY, that it runs as
'python -c "$MANIFEST_PY" verify <manifest> <rows directory> <session label> <row> <step file>...'
before a session is opened and before every row. This check takes that text out of a copy of the
steps script (it executes nothing else of it) and runs its 'verify' mode on the S4 row files, for
row t6 with its one step file under the session label S4; it also runs it with the labels S3 and
S2, and with row t8 and S3's six t8 names under S4, which must all be refused. It runs the
'entries' mode for row t6 and prints what it reports of the substitution rule and of t6.sh.

It READS the steps script copies, the manifest and the row files; it writes nothing.
Usage: python3 -B manifest-compat.py <rows directory> <g3_battery.sh copy>...
"""
import hashlib
import json
import re
import subprocess
import sys

T6 = ["t6.sh"]
T8_S3 = ["t8-a-reboot.sh", "t8-b-wait-boot-id.sh", "t8-c-unaided.sh", "t8-d-tunnel.sh", "t8-e-state.sh", "t8-f-smoke.sh"]


def main():
    rows = sys.argv[1]
    manifest = rows + "/rows.manifest.json"
    bad = 0
    print("manifest %s: sha256 %s" % (manifest, hashlib.sha256(open(manifest, "rb").read()).hexdigest()))
    for script in sys.argv[2:]:
        raw = open(script, "rb").read()
        m = re.search(r"^MANIFEST_PY='\n(.*?)\n'\n", raw.decode("utf-8"), re.S | re.M)
        print()
        print("## %s (sha256 %s)" % (script, hashlib.sha256(raw).hexdigest()))
        if not m:
            print("NOT FOUND: no MANIFEST_PY text in this copy")
            bad += 1
            continue
        code = m.group(1)
        print("MANIFEST_PY: %d lines, sha256 %s" % (code.count("\n") + 1, hashlib.sha256(code.encode("utf-8")).hexdigest()))
        cases = [("S4", "t6", T6, 0), ("S3", "t6", T6, 1), ("S2", "t6", T6, 1), ("S4", "t8", T8_S3, 1)]
        for label, slug, names, want in cases:
            p = subprocess.run([sys.executable, "-B", "-c", code, "verify", manifest, rows, label, slug] + names,
                               capture_output=True, text=True)
            out = (p.stdout + p.stderr).strip().splitlines()
            ok = p.returncode == want
            bad += not ok
            print("%s  verify %s %s (%d names): exit %d (%d expected); %d line(s), last: %s"
                  % ("as expected" if ok else "NOT AS EXPECTED", label, slug, len(names), p.returncode, want, len(out),
                     (out[-1] if out else "")[:230]))
        p = subprocess.run([sys.executable, "-B", "-c", code, "entries", manifest, rows, "t6"] + T6,
                           capture_output=True, text=True)
        try:
            e = json.loads(p.stdout)
            f = e["files"]["t6.sh"]
            ok = (p.returncode == 0 and e["row"]["session"] == "S4" and e["substitution_rule"]["suffix"] is None
                  and f["source_line_ranges"] == "1421-1428" and f["sha256_before"] == f["sha256_after"])
            print("%s  entries t6: exit %d; row %s session %s; substitution suffix %r; t6.sh lines %s, sha256_after %s, diff %s (%d bytes)"
                  % ("as expected" if ok else "NOT AS EXPECTED", p.returncode, e["row"]["row"], e["row"]["session"],
                     e["substitution_rule"]["suffix"], f["source_line_ranges"], f["sha256_after"], f["diff"], f["diff_bytes"]))
        except (ValueError, KeyError, TypeError) as exc:
            ok = False
            print("NOT AS EXPECTED  entries t6: exit %d, output not read (%s)" % (p.returncode, exc))
        bad += not ok
    print()
    print("COMPATIBLE (every case as expected)" if not bad else "NOT COMPATIBLE (%d case(s))" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
