# operator: 4 findings

## O1 [material] g3_battery.sh:1659-1663 (and g3_battery.README.md lines 58 and 170-173)
CODE: if [ -n "$(state_get "$f" halt)" ]; then
    [ -n "${EGW_G3_RUI_GO:-}" ] || refuse "NOT STARTED: session $LABEL has a recorded halt (...). A halt cancels further progress until Rui directs otherwise; with his explicit go, set EGW_G3_RUI_GO to his words (they are recorded)"
    go=$EGW_G3_RUI_GO
    echo "session $LABEL has a recorded halt; EGW_G3_RUI_GO is set and is recorded: $go"
fi
(README 58: 'the session has a recorded halt (unless EGW_G3_RUI_GO)'; README 171-172: 'No further row starts until Rui directs otherwise (EGW_G3_RUI_GO="<his words>", recorded)')
SCENARIO: T8 halts at any point (STOP: in step c, wait expiry 'reboot not shown', smoke without PROCEDURE COMPLETE, failed gate, interrupt). The operator runs 'classify t8 ...' (row-t8.env becomes 'classified', so the previous-row check at 1646-1654 passes), then 'EGW_G3_RUI_GO="..." bash g3_battery.sh row t9'. The halt check at 1659 is satisfied by the variable, 'go' is recorded, and T9 starts and runs all its steps. This is the only path by which row t9 can start after a T8 halt, and the README offers it as the general way on after any halt. The same bypass lets 'row t8' start after a halt recorded before T8's attempt, for example a gate record that differs from S2's.
EVIDENCE: Decision summary, choice 2: 'A procedural, instrumentation or safe-state halt does not permit continuation.' Request, section 5, lead sentence: 'Each of these halts the session ... handed back to Rui'. Section 5 item 4: '**Test 9 is then not run.**' Item 1: 'No row, or no further row, is then run.' Traced in cmd_row: prev-state check (1641-1654), then the halt check (1659-1663), and no other gate on t9. Halts are only appended (state_add) and nothing removes them, so classify cannot clear one. The bench did not exercise EGW_G3_RUI_GO (bench-notes, Not benched, item 6).
FIX: For S3, make the refusal unconditional:
if [ -n "$(state_get "$f" halt)" ]; then
    refuse "NOT STARTED: session $LABEL has a recorded halt ($(state_get "$f" halt)). In S3 a halt ends the session (decision summary, choice 2; request, section 5): classify, 'close', hand back to Rui"
fi
In the README, remove '(unless EGW_G3_RUI_GO)' at line 58 and replace lines 171-172 with 'No further row of S3 starts after a halt.' EGW_G3_RUI_GO can stay only for close_outside.

## O2 [material] g3_battery.sh:1546-1553 (gate_after); also run_step of t8-e-state, t8-f-smoke and every T9 step
CODE: hx "$A" gate-tunnel-check 'tunnel_check && echo "TUNNEL CHECK: the master answers on $TUNNEL_SOCK"'
...
if grep -q '^TUNNEL UP$' "$(console_of gate-tunnel-check)" 2> /dev/null; then
    echo "NOTE: the tunnel was DOWN after the row and the preamble of hx reopened it (TUNNEL UP in the gate's console): name it in the classification"
    row_set gate_tunnel "found down after the row and reopened by the preamble of hx"
fi
SCENARIO: Line d reopens the tunnel and t8-tunnel-check confirms it. Then the project's ssh master dies, for example during step e/f or before the gate (ServerAlive under TCG load). gate_after's hx runs HOST_PRE, whose '{ tunnel_check || tunnel_up; }' calls tunnel_up. tunnel_up runs tunnel_down (it removes a stale socket or sends -O exit), opens a new master and prints 'TUNNEL UP'. The step's own tunnel_check then passes (rc 0), GATE_BAD stays empty, and the script prints 'GATE t8: pass' and records no halt. 'classify t8 ...' then prints 'Next: the next row of session S3', and 'row t9' is accepted. The preambles of step f and of every T9 step reopen a lost tunnel the same way, and no step console is searched for 'TUNNEL UP'. Neither the README nor operator-procedure.md mentions this NOTE, so the operator sees only 'GATE t8: pass'.
EVIDENCE: Request, section 5 item 7: 'Guest, tunnel, WSL or keepalive lost, other than through T8's own reboot' is a halt. Item 9: 'Any restoration (... `tunnel_down && tunnel_up` outside line d): record, halt.' Runbook lines 554-561: tunnel_up calls tunnel_down and opens a new master, and prints 'TUNNEL UP' only for a master it opened. guest_common.sh line 67: HOST_PRE ends '{ tunnel_check || tunnel_up; }'. README 'Restorations' (235-241) says a restoration is run by hand and is itself a halt, but the script's own preamble does it silently. gate_after is unchanged from base (inherited), but the S3 stop conditions apply to it. Request section 8 accepts only the preamble reopening before line b.
FIX: In gate_after, make the reopen a gate failure:
if grep -q '^TUNNEL UP$' "$(console_of gate-tunnel-check)" 2> /dev/null; then
    row_set gate_tunnel "found down after the row and reopened by the preamble of hx"
    GATE_BAD+=("the tunnel was found down after the row and reopened by the preamble of hx (request, section 5, items 7 and 9)")
fi
In steps_t8 after the run_step of t8-e-state and t8-f-smoke, and in steps_t9 after each run_step, add 'grep -q "^TUNNEL UP$" "$(console_of <step>)" && halt "row ...: the preamble of hx reopened a lost tunnel before step <step> (request, section 5, items 7 and 9)"'. Exclude steps b and c, whose reopen the request accepts, and step d, whose TUNNEL UP is the line's own.

## O3 [minor] g3_battery.sh:1890-1893 and 1901-1905 (cmd_classify)
CODE: "invalid instrumentation") echo "NOTE: invalid instrumentation of the shared chain is a halt condition (packet section 4, halt 2). If this is one, do not run a further row: 'close' and hand back to Rui." ;;
...
if [ "$(state_get "$ROW_FILE" gate)" = pass ] && [ -z "$(state_get "$SESSION_FILE" halt)" ]; then
    echo "Next: the next row of session $LABEL, or 'close' after the last one."
SCENARIO: T8's smoke completes with no STOP: and its gate passes, for example with the tunnel NOTE of the finding above. The operator then classifies T8 'failed invalid unknown', as README line 146 tells them to for a host tunnel event, or because of a capture failure that the export records. classify records no halt and its last line is 'Next: the next row of session S3', so a following 'row t9' is accepted by the script.
EVIDENCE: Decision summary, choice 2: 'A procedural, instrumentation or safe-state halt does not permit continuation.' Request, section 5 item 2: instrumentation is a halt. The script records a halt for 'not started' (1891) but not for 'invalid instrumentation'. README 208-210 leaves it to the operator, but the script's own closing line contradicts that.
FIX: "invalid instrumentation") halt "row $ROW_SLUG is classified invalid instrumentation (request, section 5 item 2; decision summary, choice 2): no further row of S3 starts" ;;

## O4 [wording] g3_battery.README.md:170-171
CODE: A halt stops the script there; it closes nothing (except at `close` with the guest gone) and is recorded in the session's state file once the session is in use.
SCENARIO: In 'row', a halt inside the steps does not stop the invocation. cmd_row 1793-1817 still runs t8_evidence (when the guest answered), register_late and the whole gate_after. The gate takes a guest-state read, a healthy wait of up to 900 s, the units read and an hx tunnel check whose preamble can reopen the tunnel. Only then does the row become 'awaiting-classification'. An operator who reads the HALT line and runs 'classify' at once is refused, and may wrongly believe nothing more touched the guest or host after the HALT.
EVIDENCE: g3_battery.sh 1793-1817: run_row_steps; [ T8_ANSWERED ] || t8_evidence; register_late; gate_after. Only the halts before run_row_steps skip these, through the HALTED test at 1793.
FIX: A halt before a row's steps ends the invocation there. A halt inside the steps ends the row's steps, but the evidence reads and the gate still run, after which the row awaits classification. Nothing is closed, except at `close` with the guest gone.

### verified ok
- Diff against base read hunk by hunk (411 insertions/132 deletions); bash -n passes on g3_battery.sh and on all 11 row files.
- Every poll of the wait is the single 'ex ... timeout "$d" env E=$SESSION bash -c "$T8_POLL_SH" ...' call; d=min(20,left) with left>=1 checked before each poll, so d is never 0, the last poll is bounded by the remainder, and a budget already spent on entry gives expiry with 0 polls; the sleep is capped to what is left.
- Budget origin is a_end=$(up_now) taken right after run_step t8-a-reboot (whole seconds of /proc/uptime, monotonic); nothing after cmd_row writes start_up or ceiling_min (t8_wait_ssh only reads them; state_set's '^key=' filter does not touch them).
- Counting rule: success only when rc==0 AND the whole new console matches the anchored UUID regex AND id != pre; output of a poll ending 124/255/97/any non-zero is never counted (only reported); a console already read (prev) is never re-read; failed polls' stdout/stderr consoles stay in the attempt.
- 74 from a poll returns 74 at once and gives its own halt text; a saved id not of UUID form returns 3 before any poll; expiry text says 'reboot not shown within the wait' and line b is not run in all three.
- T8_POLL_SH is character for character gx's text (guest_common.sh 49-50): same session_common.sh, hence same key ~/.ssh/egw_campaign, port 2222, user egw, $E/boot/known_hosts, BatchMode/StrictHostKeyChecking; S2's gx step 005-t8-post-reboot-evidence used exactly that argv successfully on the rebooted guest (host key persisted); local_export exec runs the child with stdin=/dev/null, so timeout's own process group cannot stop ssh on a TTY read (and rows are launched with setsid, no controlling tty).
- local_export exec returns 74 only for a lost capture, otherwise the child's status (128+N for a signal); timeout returns 124 on expiry; itest_reconcile check exits 0 regardless of verdict, so PROCEDURE COMPLETE with lost/late>0 is reachable.
- No compose up/start/restart/docker start anywhere; the only kills are kill -0 on the console tee and kill -TERM to the row's recorded group (refused when QEMU or the keepalive is a member); QEMU is only read (pgrep, /proc/PID/stat, /proc/PID/cmdline).
- -no-reboot reading: whole-argument match of -no-reboot/--no-reboot/...reboot=shutdown..., exit 3 -> halt before step a, unreadable cmdline -> halt; 'before' still prints the QEMU PROCESS line t8_qemu parses.
- Step c requires both '^CONTAINERS RETURNED UNAIDED' and '^PERSISTENCE SHOWN' plus no_stop, and names what is missing; step f requires '^TEST STATUS itest-post-reboot-01-q2: .* -> PROCEDURE COMPLETE\.' (matches runbook line 881) and no STOP:; the set -v echo of each step file starts with 'if'/'[' so no anchored marker can be satisfied by the echoed line; t8-a-reboot.sh holds the literal 'STOP:' (comment line 1495) so no_stop uses '^STOP:' there; the other ten files hold none.
- Carrier chain matches runbook line 1493: b gets T8=rebooting, c rebooted, d returned, e reconnected, f ok; a sets T8=stop itself.
- All six t8 files equal runbook lines 1486-1495/1496/1497/1498/1499/1500 byte for byte after removing '-q2' and 'host$ ' (-q2 counts 15, 8, 32, 0, 5, 1); the four fenced t9 files equal 1509-1510, 1511-1524, 1525-1527, 1528-1534 the same way; runbook blob sha256 4acf8de6... and 1,623 lines; manifest sha256_after, sessions S3 and step order match row_files.
- verify_candidate's paths equal guest_session_open.sh 112-119 ($DEP/Image-qemuarm64.bin, ${ROOTFS_EXT4%.ext4}.qemuboot.conf, $BUILD/.../qemu-system-aarch64, git -C $OLD); the four constants equal S2's 001-identities-before-boot.stdout.txt (4457ef38..., 7739c945..., 5d389c65..., 489bc9e5..., 0 porcelain lines).
- GATE_IDENTITIES_S2 equals lines 1-6 of S2's container_identities.txt (sha256 60f7e99b...) cut before ' container_id=' (sorted sets identical, 6 '^identity ' lines; 'identity_format=1' is not counted); the gate attempt is taken from the gate driver's 'DRIVER RESULT <run id>:' line exactly as the preflight's (driver_status.py prints attempt run_id); the check runs before new_attempt and its failure is a recorded halt.
- ROOTFS_BEFORE_S3 equals rootfs_after_close of the sealed session-S2.env; the 2026-10-03 post-battery HIST packages are pytest records, not guest boots.
- fresh_row admits exactly $ATTEMPTS/$T8_ADMITTED and $OUT/runs/2026-10-03/$T8_ADMITTED; a recursive find of output_test/runs and incomplete shows only that one t8/t9 attempt name, so local_export new_attempt (rglob, _RUN_ID full-name match) will number t8 attempt02 and t9 attempt01; the name check halts before any step otherwise.
- open refuses S1/S2 with the 'authority is consumed' text before any log or turn; STATE defaults to $EXEC/g3-t8t9-s3; nothing reads or writes $EXEC/g3-battery.
- Function bodies identical to base: cmd_term, take_turn, close_rows, cmd_classify, gate_after, no_stop, run_step, on_signal, keepalive_check, environment_copy, wait_group, row_group, row_alive, state_set/state_get, halt, start_log, finish_log, run_driver, data_disk_header, steps_t9, register_late, register_sources, t8_shown, t8_evidence, run_row_steps, check_guest_state, open_halt; cmd_close differs only in the 'What remains' text, close_outside and cmd_status only in the label loop; the stop line keeps both --env-file and -t 130, the 97 path stops nothing and the no-QEMU path runs only the frozen close driver.
- Path to row t9 traced: it requires row-t8.env classified|interrupted and no session halt; every T8 failure path in steps_t8 calls halt (written to session-S3.env since SESSION_FILE is set at 1669 before any check), except the PROCEDURE COMPLETE + no STOP: path; the only bypass is EGW_G3_RUI_GO (finding 1).
### not checked
- Real-host behaviour of OpenSSH under timeout against a rebooting guest, and of the tunnel master after the in-process reboot (no ssh/wsl allowed).
- Whether 'git -C ~/yocto/egw status --porcelain' stays empty WHILE QEMU runs under the launcher's 'kas shell' (verify_candidate now runs it at row t8 and row t9; an untracked, non-ignored file written in the checkout during the session would halt T8 falsely). S2 recorded 0 lines only before the boot.
- The WSL attempts directory (~/egw-exec/attempts) contents: not readable under the rules; relied on the bench note that only the admitted attempt01 exists there.
- Shellcheck and the 32 bench scenarios were not re-run (no script of P may be run).
- g3_hostprep.sh, seal_prep.sh, ops/*.sh and g3_extract_rows.py / g3_check_rows.sh (other groups).
- The header and constant of t9-exposure.sh were only read, not compared with the first preparation's file.
- Note on my own conduct: while comparing the gate constants I inadvertently wrote two scratch files, /tmp/got.txt and /tmp/want.txt (Git Bash temporary directory, outside the project). They were not deleted because deletion is also forbidden; they hold only the six public identity lines.