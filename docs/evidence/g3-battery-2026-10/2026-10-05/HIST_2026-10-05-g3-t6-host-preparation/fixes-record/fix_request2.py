"""The request's section 7 (the preparation's results) and section 9's two stated choices; the reflow of section 4's
last paragraph. Usage: python fix_request2.py <P>"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / "request-draft.md"
s = p.read_bytes().decode("utf-8")
pairs = [
    ("""At 47 min the row receives TERM to its process group (never KILL, never QEMU) and is exported as interrupted; the
Docker events recorder of r04 can then be left running (found by the preparation's bench): the runbook's own cleanup of
it, recorded, precedes the close. Host: a
keepalive with at least 6 h left, Windows kept awake, no other load.""",
     """At 47 min the row receives TERM to its process group (never KILL, never QEMU) and is exported as interrupted; the
Docker events recorder of r04 can then be left running (found by the preparation's bench): the runbook's own cleanup of
it, recorded, precedes the close. Host: a keepalive with at least 6 h left, Windows kept awake, no other load."""),
    ("""## 7. Preparation (offline; no guest)

(Filled in after the preparation.)""",
     """## 7. Preparation (delivered; no guest)

Package `output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation` (its seal is given in the hand-off).

- **Host, 2026-10-05 20:19Z, outcome `prepared`:** the clone moved from `8e49261` (clean) to `1fd9792` (tree `14f89c4`,
  clean, branches unchanged); every identity of section 2 equal (`repo_identity`: drivers `2c209b09…`, export tool
  `544c9b3d…`); helpers regenerated, `e5eba37e…` (545 lines), predecessor kept; r04 unused on the host and on the
  guest's root file system (read offline); S2's attempt01 the only earlier t6 attempt; root file system `6fce1688…`
  before and after; data disk 34,359,738,368 B, ext4 `clean`; the plan `c195bd3f…` → `61d55940…` (96 entries, the first
  95 byte-identical, r04 `planned` with seed 1715385812). No image was rebuilt.
- **Step file:** `t6.sh` (`ec8ac010…`) equals runbook lines 1421–1428 byte for byte; checked against the moved clone.
- **Operator script** `g3_battery.sh` (`7a63b361…`): S3's script set to S4 (label, `t6` only, the new identities, the
  collector compared at open and before the row, S3's exception removed).
- **Checks:** one bounded check by two readers (one material point: which recovery value decides, now stated in
  section 6; nine minor or wording points, applied); a bench of the final script on the real `t6.sh` with the real
  helper functions, stand-ins for the harness, `analyze` and the guest: 25 scenarios PASS, the script unchanged; one
  adversarial reading of the bench (one material point, the ceiling path of section 4, now in the procedure).
- **Verified nowhere but on the guest:** the real harness with the transition rule, the collector's uptime bounds,
  `--exactly-once` on a real post-drain copy, and `term` on the real harness."""),
    ("""One sentence suffices, for example: *"Autorizo uma única sessão S4 com o teste 6 (`controller_restart-r04`), nos termos
do pedido de 2026-10-05; sem repetições, sem alterações ao candidato e sem aceitação automática do G3."*""",
     """One sentence suffices, for example: *"Autorizo uma única sessão S4 com o teste 6 (`controller_restart-r04`), nos termos
do pedido de 2026-10-05; sem repetições, sem alterações ao candidato e sem aceitação automática do G3."*

Two points are choices of this request; say so if either should be otherwise: (1) "recovery within 120 s" read on
`restart_metrics_endpoint_recovery_s`, the packet's endpoint recovery, with the functional recovery reported beside it
(section 6); (2) after a TERM at the ceiling, the runbook's own recorder cleanup, recorded, before the close
(section 4)."""),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:90]
    s = s.replace(o, n)
p.write_bytes(s.encode("utf-8"))
print("ok")
