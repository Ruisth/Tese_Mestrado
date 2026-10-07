"""Build bsupp_setup.sh from the sealed bench's bs4_setup.sh: the same bench, with two changes only. (1) Its paths
point at the sealed bench folder for the files it reads (bs4_stubs.py, bs4_harness.py). (2) The plan it copies is
the predecessor kept in the sealed preparation package (sha256 c195bd3f...), read-only: the real plan holds r04
since the host preparation of 2026-10-05 (61d55940...), and the bench adds r04 itself to its copy, as before.
Usage: python make_bsupp_setup.py <S>"""
import sys
from pathlib import Path

S = Path(sys.argv[1])
s = (S / "g3/t6prep/bench/bs4_setup.sh").read_bytes().decode("utf-8")
pairs = [
    ("""HERE=$(cd "$(dirname "$0")" && pwd)       # <P>/bench
PREP=$(cd "$HERE/.." && pwd)              # <P>
SCR=$(cd "$PREP/../.." && pwd)            # <S>""",
     """SUPPB=$(cd "$(dirname "$0")" && pwd)      # <S>/g3/t6supp/bench (the supplement)
SCR=$(cd "$SUPPB/../../.." && pwd)        # <S>
PREP=$SCR/g3/t6prep                       # <P>
HERE=$PREP/bench                          # the sealed bench folder: bs4_stubs.py, bs4_harness.py"""),
    ("""REAL_PLAN=/home/ruisth/egw-tcg/pilot/campaign_plan.json""",
     """# SUPPLEMENT (2026-10-07): the plan before r04, as the sealed preparation package kept it (read-only).
REAL_PLAN="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation/part1-record/campaign_plan.predecessor.json\""""),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:60]
    s = s.replace(o, n)
s = s.replace("#!/bin/bash\n", "#!/bin/bash\n# SUPPLEMENT COPY (2026-10-07) of the sealed bench's bs4_setup.sh, made by make_bsupp_setup.py: the paths and\n# the plan's source changed, nothing else.\n", 1)
(S / "g3/t6supp/bench/bsupp_setup.sh").write_bytes(s.encode("utf-8"))

r = (S / "g3/t6supp/bench/bsupp_run.sh").read_bytes().decode("utf-8")
o = 'bash "$HERE/bs4_setup.sh" "$B"'
assert r.count(o) == 1
r = r.replace(o, 'bash "$SUPP/bench/bsupp_setup.sh" "$B"')
(S / "g3/t6supp/bench/bsupp_run.sh").write_bytes(r.encode("utf-8"))
print("ok")
