#!/bin/bash
# Stream OPERATOR: ONE light pass of the whole script (open S3, row t8, classify, row t9,
# classify, close) before it is handed to the benches, on FAKE row files and stub drivers.
# It shows that the subcommands still fit together after the changes for S3; it is not
# the bench of the real step files (that is the bench stream's work, P/bench/).
# Built on op_setup.sh, then, in the bench only: the four session drivers replaced by
# stubs (no QEMU, no guest), a sha256sum stub that answers the recorded drivers hash for
# the drivers' stream, an ssh stub that answers the guest reads from canned text, fake
# row files (t8: six, t9: five) with their manifest, a fake QEMU process (a bash loop).
# Usage (WSL): op_smoke_setup.sh /tmp/g3-s3-op-<name>
set -u
B=${1:?usage: op_smoke_setup.sh /tmp/g3-s3-op-<name>}
HERE=$(cd "$(dirname "$0")" && pwd)
bash "$HERE/op_setup.sh" "$B" || exit 1
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
DRIVERS_SHA=4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5
mkdir -p "$B/rows" "$B/out/runs/2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01" || exit 1
printf '{"role": "sut", "provider": "", "region": "", "instance_type": "", "shared_vcpu_note": ""}\n' > "$B/home/egw-tcg/sut_environment.json"
printf 'bench data disk\n' > "$B/data.img"
# The gate's record: S2's sealed file with other container ids and start instants.
sed 's/container_id=[0-9a-f]*/container_id=1111111111111111111111111111111111111111111111111111111111111111/; s/started=.*$/started=2026-10-05T10:00:00.000000001Z/' \
    "$OT/runs/2026-10-03/20261003T132836Z_g2-gate-preconditions_attempt06/environment/container_identities.txt" > "$B/gate.identities" || exit 1

# --- stub session drivers, in the COPY only ----------------------------------------------
D=$B/repo/tools/session
cat > "$D/guest_session_open.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of guest_session_open.sh: no QEMU, no guest (a fake process stands for QEMU).
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -z "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "a session is already open: $SESSION"
S=$(new_attempt "guest session" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
SESSION=$S
echo "$S" > "$EXEC/current_session"
mkdir -p "$S/scripts" "$S/boot" "$S/guest" "$S/host"
cp "$DRIVERS/guest/session_common.sh" "$S/scripts/"
echo s1 > "$S/.current_run"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/boot/s1.started"
bash "$BENCH/stubs/fake_qemu_start.sh"
(cd "$REPO/src" && $LE set --attempt "$S" "identities=$(repo_identity)" "pid=4242")
ex "$S" boot bash -c 'echo "bench stub boot"'
echo "session open: $S (bench stub)"
driver_exit_open "$S"
EOS
cat > "$D/preflight.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of preflight.sh.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "live preflight" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
gx "$A" stack-start-interlock "cd /opt/egw/deployment && echo 'up exit=0 (bench: the prescribed stack start of the preflight)'"
printf '{"role": "sut", "captured_utc": "2026-10-05T00:00:00Z", "node": "bench", "provider": "QEMU 8.2.7 TCG (bench stub)", "region": "local-workstation", "instance_type": "qemu -machine virt; ARM64 EMULATED", "shared_vcpu_note": "bench"}\n' > "$A/environment/sut_environment.json"
(cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass --reason "bench stub preflight" --next-action "none")
driver_exit "$A"
EOS
cat > "$D/gate_health.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of gate_health.sh: it keeps a record of the running images in its attempt,
# in the frozen driver's place and form (environment/container_identities.txt).
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "G2 gate preconditions" engineering) || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
healthy_wait "$A" services-healthy 30 1
cp "$BENCH/gate.identities" "$A/environment/container_identities.txt"
(cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass --reason "bench stub gate" --next-action "none")
driver_exit "$A"
EOS
cat > "$D/guest_session_close.sh" << 'EOS'
#!/bin/bash
# BENCH STUB of guest_session_close.sh. The fake process that stands for QEMU is the
# bench's own and is ended here, as the power-off ends the real one.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
S=$SESSION
[ -n "$S" ] && [ -d "$S" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
gx "$S" stack-stop "cd /opt/egw/deployment && $DC stop -t 60; echo \"stop exit=\$?\""
kill "$(cat "$BENCH/qemu.pid")" 2> /dev/null
rm -f "$BENCH/qemu.pid"
ex "$S" artefacts-after-poweroff bash -c 'sha256sum "$1"; echo "no qemu process left"' _ "$ROOTFS_EXT4"
rm -f "$EXEC/current_session"
(cd "$REPO/src" && $LE finish --attempt "$S" --status finished --validity not-applicable --outcome pass --reason "bench stub close" --next-action "none")
driver_exit "$S"
EOS

# --- stubs: the drivers' stream answers the recorded hash (the driver files are stubs) ---
python3 - "$B/stubs/sha256sum" "$DRIVERS_SHA" << 'EOF'
import sys
p, sha = sys.argv[1], sys.argv[2]
t = open(p).read()
old = '[ "${#files[@]}" -gt 0 ] || exec /usr/bin/sha256sum "$@"\n'
new = '[ "${#files[@]}" -gt 0 ] || { cat > /dev/null; echo "%s  -"; exit 0; }\n' % sha
assert t.count(old) == 1, "sha256sum stub anchor not found"
open(p, "w", newline="\n").write(t.replace(old, new))
EOF
cat > "$B/stubs/ss" << 'EOS'
#!/bin/bash
# BENCH STUB: no listening socket.
exit 0
EOS
cat > "$B/stubs/curl" << 'EOS'
#!/bin/bash
printf '200'
EOS
# The ssh stub of op_setup.sh, with canned answers for the guest reads of the gate and the close.
python3 - "$B/stubs/ssh" << 'EOF'
import sys
p = sys.argv[1]
t = open(p).read()
old = '        *boot_id*) cat "$BENCH/guest/boot_id" ;;\n'
new = old + (
    '        *State.OOMKilled*) for s in mosquitto mongodb ditto-policies ditto-things ditto-gateway controller; do echo "egw-$s-1 Up 5 minutes (healthy)"; done\n'
    '            for s in mosquitto mongodb ditto-policies ditto-things ditto-gateway controller; do echo "container egw-$s-1 oomkilled=false restarts=0 id=c0ffee$(printf %s "$s" | /usr/bin/sha256sum | cut -c1-58) started=2026-10-05T10:00:00.000000001Z"; done\n'
    '            echo "memory-cgroup OOM lines: 0" ;;\n'
    '        *"ALL HEALTHY"*) echo "2026-10-05T10:00:00Z sample 1: bench"; echo "ALL HEALTHY: the 6 expected services are running and healthy (sample 1)" ;;\n'
    '        *"list-units"*) echo "no egw-events-* and no egw-resources-* unit is active" ;;\n'
    '        *"stop -t 130"*) echo "bench compose stub: stop -t 130"; echo "stop exit=0" ;;\n')
assert t.count(old) == 1, "ssh stub anchor not found"
open(p, "w", newline="\n").write(t.replace(old, new))
EOF
chmod +x "$B"/stubs/*

# --- FAKE row files (they run no runbook line) and their manifest -------------------------
R=$B/rows
cat > "$R/t8-a-reboot.sh" << 'EOS'
if ssh egw-tcg cat /proc/sys/kernel/random/boot_id > $P/itest-reboot-q2.boot_id.pre && [ -s $P/itest-reboot-q2.boot_id.pre ]; then T8=rebooting; echo "reboot command sent (bench fake of line a)"; ( echo refuse > "$BENCH/ssh.mode"; sleep 4; echo 22222222-2222-4222-8222-222222222222 > "$BENCH/guest/boot_id"; echo ok > "$BENCH/ssh.mode" ) > /dev/null 2>&1 < /dev/null & else stop "test 8: no boot id - the guest was NOT rebooted (bench fake)"; fi
EOS
cat > "$R/t8-b-wait-boot-id.sh" << 'EOS'
[ "$T8" = rebooting ] && B1=$(timeout 20 ssh -n egw-tcg cat /proc/sys/kernel/random/boot_id) && echo "REBOOT SHOWN: boot id $(cat $P/itest-reboot-q2.boot_id.pre) -> $B1 (bench fake of line b)" && T8=rebooted || stop "test 8: reboot NOT shown (bench fake; T8='$T8')"
EOS
cat > "$R/t8-c-unaided.sh" << 'EOS'
[ "$T8" = rebooted ] && echo "CONTAINERS RETURNED UNAIDED: bench fake of line c" && echo "PERSISTENCE SHOWN: bench fake of line c" && T8=returned || stop "test 8: the containers did NOT return unaided (bench fake; T8='$T8')"
EOS
cat > "$R/t8-d-tunnel.sh" << 'EOS'
[ "$T8" = returned ] && tunnel_down && tunnel_up && T8=reconnected || stop "test 8: tunnel NOT reopened (bench fake; T8='$T8')"
EOS
cat > "$R/t8-e-state.sh" << 'EOS'
[ "$T8" = reconnected ] && echo "CONTROLLER PROCESS NEW: bench fake of line e" && T8=ok || stop "test 8: persistence across the reboot NOT verified (bench fake; T8='$T8')"
EOS
cat > "$R/t8-f-smoke.sh" << 'EOS'
if [ "$T8" = ok ]; then R=itest-post-reboot-01-q2; mkdir -p $P/$R; echo '  "lost": 2,'; echo '  "late_confirmations": 7,'; echo "TEST STATUS $R: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE. This is NOT the verdict (bench fake of line f)."; else stop "test 8: the post-reboot smoke is NOT started (bench fake; T8='$T8')"; fi
EOS
cat > "$R/t9-a.sh" << 'EOS'
echo "bench fake of (a)"; echo "exit=1"
EOS
cat > "$R/t9-b.sh" << 'EOS'
echo "bench fake of (b)"; echo "exit=1"
EOS
cat > "$R/t9-c.sh" << 'EOS'
echo "bench fake of (c)"; echo "exit=1"
EOS
cat > "$R/t9-de.sh" << 'EOS'
T=$(date -u +%Y%m%dT%H%M%SZ); mkdir -p $P/itest-acl-$T && echo "verdict=PASS" > $P/itest-acl-$T/verdict.txt; echo "probe exit=0 (bench fake of (d)+(e))"
EOS
cat > "$R/t9-exposure.sh" << 'EOS'
echo "bench fake of the exposure checks"
EOS
python3 - "$R" << 'EOF'
import collections, hashlib, json, os, sys
out = sys.argv[1]
ROWS = [("t8", "S3", ["t8-a-reboot.sh", "t8-b-wait-boot-id.sh", "t8-c-unaided.sh", "t8-d-tunnel.sh", "t8-e-state.sh", "t8-f-smoke.sh"]),
        ("t9", "S3", ["t9-a.sh", "t9-b.sh", "t9-c.sh", "t9-de.sh", "t9-exposure.sh"])]
files = collections.OrderedDict()
for row, session, steps in ROWS:
    for order, name in enumerate(steps, 1):
        data = open(os.path.join(out, name), "rb").read()
        files[name] = {"row": row, "session": session, "step_order": order, "kind": "BENCH FAKE (not a runbook line)",
                       "source_line_ranges": "none", "sha256_before": None,
                       "sha256_after": hashlib.sha256(data).hexdigest(), "substitutions": []}
doc = {"schema": "g3-battery-rows-manifest/1", "generated_by": "op_smoke_setup.sh (FAKE rows)", "generator_sha256": None,
       "runbook": {"commit": "bench", "sha256": "bench"},
       "rows": [{"row": r, "session": s, "steps": st} for r, s, st in ROWS], "files": files}
open(os.path.join(out, "rows.manifest.json"), "w", newline="\n").write(json.dumps(doc, indent=2) + "\n")
EOF
echo "smoke bench ready: $B"
