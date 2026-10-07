#!/usr/bin/env python3
"""Cross-check of stream ROWS: does rows/rows.manifest.json answer the steps script's own manifest tool?

The steps script (g3_battery.sh) carries a Python text, MANIFEST_PY, that it runs as
'python -c "$MANIFEST_PY" verify <manifest> <rows directory> <session label> <row> <step file>...'
before a session is opened and before every row. This check takes that text out of a copy of the
steps script (it executes nothing else of it) and runs its 'verify' mode on the S3 row files, for
row t8 with its six step files and for row t9 with its five, under the session label S3; it also
runs it with the label S2 and with the battery's four t8 names, which must both be refused.

It READS the steps script copy, the manifest and the row files; it writes nothing.
Usage: python3 -B manifest-compat.py <rows directory> <g3_battery.sh copy>...
"""
import hashlib
import re
import subprocess
import sys

T8 = ["t8-a-reboot.sh", "t8-b-wait-boot-id.sh", "t8-c-unaided.sh", "t8-d-tunnel.sh", "t8-e-state.sh", "t8-f-smoke.sh"]
T9 = ["t9-a.sh", "t9-b.sh", "t9-c.sh", "t9-de.sh", "t9-exposure.sh"]
T8_BATTERY = ["t8-a-reboot.sh", "t8-b-return.sh", "t8-c-snapshot.sh", "t8-d-smoke.sh"]


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
        cases = [("S3", "t8", T8, 0), ("S3", "t9", T9, 0), ("S2", "t8", T8, 1), ("S3", "t8", T8_BATTERY, 1)]
        for label, slug, names, want in cases:
            p = subprocess.run([sys.executable, "-B", "-c", code, "verify", manifest, rows, label, slug] + names,
                               capture_output=True, text=True)
            out = (p.stdout + p.stderr).strip().splitlines()
            ok = p.returncode == want
            bad += not ok
            print("%s  verify %s %s (%d names): exit %d (%d expected); %d line(s), last: %s"
                  % ("as expected" if ok else "NOT AS EXPECTED", label, slug, len(names), p.returncode, want, len(out),
                     (out[-1] if out else "")[:230]))
    print()
    print("COMPATIBLE (every case as expected)" if not bad else "NOT COMPATIBLE (%d case(s))" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
