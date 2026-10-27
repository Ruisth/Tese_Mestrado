# G3 battery, row t9, step 5 of 5: PROSE-ONLY step. No fenced runbook line exists for it.
# Written by g3_extract_rows.py from a constant of that script; nothing is extracted and no id is substituted.
# It derives from docs/setup/qemu_integrated_gateway.md at 80e833f (sha256 c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae), line 1529 (the last sentence of test 9's Expected), which says:
#   "Also keep `ssh -p 2222 root@127.0.0.1` refused and `nmap`-free port evidence: `ss -ltn` on the host shows only 2222 and 8883 forwarded by QEMU; inside the guest `docker ps` shows `127.0.0.1:8080` and `127.0.0.1:8000` bindings and MongoDB with no published port (work order item 5)."
# Decision packet of 2026-10-01 (revision 2), execution choice "Prose-only steps": T9's three exposure checks
# are run and recorded, read-only. Operator procedure, T9: `ssh -n -o BatchMode=yes ... -p 2222 root@127.0.0.1 true`, where only "Permission denied" counts; `ss -ltnp`; the guest's `docker ps` ports.
# The three commands only read, each prints what it read and its exit status, and none judges.
# (1) root over ssh on the forwarded port 2222. BatchMode: no prompt, so no password is ever asked or typed;
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
