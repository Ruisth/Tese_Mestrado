"""Build bsupp_run.sh: the helpers of the sealed bench's bs4_run.sh (lines 1-241, unchanged but for the paths) and
the supplement's scenarios. Usage: python make_bsupp.py <S>"""
import sys
from pathlib import Path

S = Path(sys.argv[1])
src = (S / "g3/t6prep/bench/bs4_run.sh").read_bytes().decode("utf-8")
cut = src.index("\n{\ncase $SC in\n")
head = src[:cut + 1]
old_paths = """HERE=$(cd "$(dirname "$0")" && pwd)       # <P>/bench
PREP=$(cd "$HERE/.." && pwd)              # <P>
SCR=$(cd "$PREP/../.." && pwd)            # <S>"""
assert head.count(old_paths) == 1
head = head.replace(old_paths, """SUPP=$(cd "$(dirname "$0")/.." && pwd)    # <S>/g3/t6supp (the supplement)
SCR=$(cd "$SUPP/../.." && pwd)            # <S>
PREP=$SCR/g3/t6prep                       # <P>, the sealed preparation's working folder
HERE=$PREP/bench                          # the sealed bench: bs4_setup.sh, bs4_env.sh (used unchanged)""")
assert head.startswith("#!/bin/bash\n")
head = head.replace("#!/bin/bash\n", """#!/bin/bash
# SUPPLEMENT of 2026-10-07 (the Project Manager's order, register line 4937): the ONE offline
# verification of the recorder's emergency cleanup, ops/g3_recorder_cleanup.sh, on the path it
# is for: open S4, row t6 with the harness stand-in asleep, 'term t6' (the recorder unit is left
# active: finding F1 of the preparation's bench), then the new script, then 'close'. Built by
# make_bsupp.py from the sealed bench's bs4_run.sh: its helpers, below, are that file's lines
# 1-241 with only the three path lines changed; bs4_setup.sh and bs4_env.sh are used unchanged.
# In the bench copy only, after the TERM, events_capture.sh is the REAL one of 1fd9792 (the
# module's stub stood for it during the row); the stub guest answers its cleanup script and
# its scp from supp-stubs/ (first on PATH), with one fault per case:
#   supp-ok      none: try 1 keeps the four files; close; the session's package holds them
#   supp-retry   try 1: the scp of cli.stderr fails (3 of 4 copied: the INCOMPLETE staging
#                folder is kept and exported); try 2 keeps the four files; close
#   supp-hang    try 1: the scp of events.jsonl hangs; timeout 120 ends the try (exit 124);
#                try 2 keeps the four files; close
#   supp-halt    the unit is never shown stopped: three tries end 1; HALT; close NOT run by the
#                script; nothing signalled (the fake QEMU unchanged); the session stays open
""", 1)

scen = r'''
SUPP_SCRIPT=$SUPP/ops/g3_recorder_cleanup.sh
REAL_CAPTURE=$SCR/t6m/tools/session/events_capture.sh
REAL_CAPTURE_SHA=$(sha "$REAL_CAPTURE")
KEEP_NAME=recovery/events-partial-$RID

supp_stubs() {     # the stub guest's answers to the REAL cleanup (first on PATH)
    mkdir -p "$B/supp-stubs" "$B/guest-tmp/egw-events-$RID" || exit 1
    printf '{"status":"die","id":"bench","timeNano":1}\n{"status":"start","id":"bench","timeNano":2}\n' > "$B/guest-tmp/egw-events-$RID/events.jsonl"
    printf 'start epoch=1790000000\nready epoch=1790000001 events_bytes=100 unit=active\n' > "$B/guest-tmp/egw-events-$RID/lifecycle.txt"
    printf 'boot_id=bench\ndocker_mainpid=1\n' > "$B/guest-tmp/egw-events-$RID/start-facts.txt"
    : > "$B/guest-tmp/egw-events-$RID/cli.stderr"
    cat > "$B/supp-stubs/ssh" << 'EOS'
#!/bin/bash
# SUPPLEMENT BENCH WRAPPER of ssh: answers the REAL events_capture.sh cleanup script and the
# new script's read of the unit state from the stub guest's unit file; every other call goes
# to the sealed bench's wrapper unchanged.
S=$EGW_STUB_STATE
cmd="${@: -1}"
R=controller_restart-r04
log() { { printf 'ssh'; for a in "$@"; do printf ' [%s]' "$(printf '%s' "$a" | head -c 160 | tr '\n' ' ')"; done; echo; } >> "$S/ssh.log"; }
case $cmd in
    *unit_state_before_cleanup*)
        log "$@"; [ ! -e "$BENCH/guest.down" ] || { echo "ssh: connect to host: Connection refused" >&2; exit 255; }
        state=$(cat "$S/unit-$R" 2> /dev/null || echo inactive)
        echo "unit_state_before_cleanup=$state"
        rc=0
        case $state in
            inactive | failed) ;;
            *)
                echo "cleanup_stop_requested_guest_epoch=1790000600"
                echo "stop egw-events-$R" >> "$S/supp.unit-stops"
                if [ -e "$BENCH/supp.unit-stuck" ]; then rc=1; else echo inactive > "$S/unit-$R"; fi
                echo "unit_state_after_cleanup=$(cat "$S/unit-$R")" ;;
        esac
        echo "--- the recorder's lifecycle record (/tmp/egw-events-$R/lifecycle.txt; its capture stays in /tmp/egw-events-$R)"
        cat "$BENCH/guest-tmp/egw-events-$R/lifecycle.txt"
        echo "events_lines=$(wc -l < "$BENCH/guest-tmp/egw-events-$R/events.jsonl")"
        echo "cli_stderr_bytes=0"
        exit $rc ;;
    *"systemctl is-active egw-events-$R"*)
        log "$@"; [ ! -e "$BENCH/guest.down" ] || { echo "ssh: connect to host: Connection refused" >&2; exit 255; }
        s=$(cat "$S/unit-$R" 2> /dev/null || echo inactive)
        echo "unit_state=$s"
        case $s in inactive | failed) exit 0 ;; *) exit 1 ;; esac ;;
esac
exec "$BENCH/stubs/ssh" "$@"
EOS
    cat > "$B/supp-stubs/scp" << 'EOS'
#!/bin/bash
# SUPPLEMENT BENCH WRAPPER of scp: copies the recorder's files from the stub guest's /tmp;
# a fault flag of the case acts once (fail: exit 1; hang: sleeps until the try's timeout ends
# it); every other call goes to the module's stub unchanged.
S=$EGW_STUB_STATE
R=controller_restart-r04
src= dest=
for a in "$@"; do case $a in -*) ;; *) [ -z "$src" ] && src=$a || dest=$a ;; esac; done
case $src in
    "egw-tcg:/tmp/egw-events-$R/"*)
        f=${src##*/}
        echo "scp [$src] [$dest]" >> "$S/supp.scp.log"
        if [ -e "$BENCH/supp.scp.fail.$f" ]; then rm -f "$BENCH/supp.scp.fail.$f"; echo "scp: bench fault: $f not copied" >&2; exit 1; fi
        if [ -e "$BENCH/supp.scp.hang.$f" ]; then rm -f "$BENCH/supp.scp.hang.$f"; echo $$ > "$BENCH/supp.scp.hang.pid"; exec /usr/bin/sleep 600; fi
        [ -f "$BENCH/guest-tmp/egw-events-$R/$f" ] || { echo "scp: $src: No such file or directory" >&2; exit 1; }
        cp "$BENCH/guest-tmp/egw-events-$R/$f" "$dest" ;;
    *) exec "$BENCH/mod/stubs/scp" "$@" ;;
esac
EOS
    chmod +x "$B/supp-stubs/ssh" "$B/supp-stubs/scp"
}

term_path() {      # open S4, row t6 with the harness asleep, term t6: the recorder left active (F1)
    st bench_harness_sleep 900
    open_ok
    say "g3_battery.sh row t6 (detached, as ops/g3_go.sh starts it)"
    setsid bash "$G" row t6 < /dev/null > "$B/row.out" 2>&1 &
    ROWPID=$!
    local n=0
    while [ ! -s "$B/harness.started" ] && [ "$n" -lt 480 ] && kill -0 "$ROWPID" 2> /dev/null; do /usr/bin/sleep 1; n=$((n + 1)); done
    is "the harness stand-in is asleep inside the run" "$(exists "$B/harness.started")" exists
    run term t6
    want_rc 0 "term t6"
    n=0
    while kill -0 "$ROWPID" 2> /dev/null && [ "$n" -lt 400 ]; do /usr/bin/sleep 1; n=$((n + 1)); done
    wait "$ROWPID" 2> /dev/null
    want "the row's attempt finished 'interrupted' and exported" "^row t6: attempt finished 'interrupted'; driver code 130; export: verified -> " "$B/row.out"
    is "F1 reproduced: the recorder unit is left active on the stub guest" "$(cat "$EGW_STUB_STATE/unit-$RID" 2> /dev/null)" active
    Q0=$(qemu_state)
    note "the fake QEMU after the term: $Q0"
    # bench only: the REAL events_capture.sh of 1fd9792 in the copy, for the cleanup
    cp "$REAL_CAPTURE" "$B/repo/tools/session/events_capture.sh" || exit 1
    is "bench copy: events_capture.sh is now the REAL one of 1fd9792 (sha256)" "$(sha "$B/repo/tools/session/events_capture.sh")" "$REAL_CAPTURE_SHA"
    supp_stubs
    export PATH=$B/supp-stubs:$PATH
    SESS=$(cat "$EGW_EXEC/current_session")
    KEEP=$SESS/$KEEP_NAME
}

cleanup_run() {    # the new script, as the operator runs it
    say "ops/g3_recorder_cleanup.sh (sha256 $(sha "$SUPP_SCRIPT"))"
    T0=$(cut -d' ' -f1 /proc/uptime)
    EGW_EXEC_REPO=$B/repo setsid bash "$SUPP_SCRIPT" < /dev/null > "$B/cleanup.out" 2>&1
    RC=$?
    T1=$(cut -d' ' -f1 /proc/uptime)
    echo "-> exit $RC after $(awk -v a="$T0" -v b="$T1" 'BEGIN { printf "%.0f", b - a }') s"
    grep -E '^(## |events_capture|KEEP_DIR|try [0-9]|kept INCOMPLETE|OK:|HALT:|REFUSED:|the unit|STOP)' "$B/cleanup.out" | mask | cut -c1-400 | sed 's/^/    | /'
}

keep_complete() {  # the four files in KEEP_DIR, equal to the stub guest's
    local f
    for f in lifecycle.txt start-facts.txt; do
        is "KEEP_DIR/$f equals the guest's" "$(sha "$KEEP/$f")" "$(sha "$B/guest-tmp/egw-events-$RID/$f")"
    done
    is "KEEP_DIR/events.partial.jsonl equals the guest's events.jsonl" "$(sha "$KEEP/events.partial.jsonl")" "$(sha "$B/guest-tmp/egw-events-$RID/events.jsonl")"
    is "KEEP_DIR/cli-stderr.txt equals the guest's cli.stderr" "$(sha "$KEEP/cli-stderr.txt")" "$(sha "$B/guest-tmp/egw-events-$RID/cli.stderr")"
    is "no docker-events.log is written for the partial capture" "$(find "$SESS/recovery" -name docker-events.log | wc -l)" 0
}

session_steps() {  # the session attempt's recorded steps of the cleanup
    note "the session attempt's recorded cleanup steps: $(ls "$SESS/console" | sed -n 's/^[0-9]*-\(recorder-[^.]*\)\.stdout\.txt$/\1/p' | sort -u | tr '\n' ' ')"
}

close_and_package() {   # close; the session's package holds the partial capture
    close_ok
    PKG=$(ls -d "$EGW_OUTPUT_TEST"/runs/*/"$(basename "$SESS")" 2> /dev/null | head -n 1)
    is "the session's package exists" "$([ -n "$PKG" ] && echo exists || echo absent)" exists
    is "the package's SHA256SUMS verify" "$(cd "$PKG" && /usr/bin/sha256sum -c --quiet SHA256SUMS > /dev/null 2>&1 && echo verified || echo FAILED)" verified
    local f
    for f in events.partial.jsonl lifecycle.txt start-facts.txt cli-stderr.txt; do
        is "the package holds $KEEP_NAME/$f, equal to KEEP_DIR's" "$(sha "$PKG/$KEEP_NAME/$f")" "$(sha "$KEEP/$f")"
    done
    want "the package's SHA256SUMS lists the partial capture" "  $KEEP_NAME/events\.partial\.jsonl$" "$PKG/SHA256SUMS"
}

nothing_signalled() {   # nothing stopped, powered off or signalled but the recorder unit
    is "the fake QEMU before the close (same pid and start tick)" "$(qemu_state)" "$Q0"
    is "no stop of the stack or power-off reached the stub guest before close" "$(grep -cE 'stop -t (130|60)|poweroff|shutdown' "$EGW_STUB_STATE/ssh.log")" 0
    is "the script never runs close" "$(grep -c 'g3_battery' "$B/cleanup.out")" 0
}

{
case $SC in
    supp-ok)
        setup
        echo "EXPECTED: after the TERM the recorder is left active (F1); the new script's try 1 stops it and keeps the four files in <session>/$KEEP_NAME; both confirmations hold; 'OK: ... close may run'; a second invocation adds no try; close exports the session's package with the partial capture."
        term_path
        cleanup_run
        want_rc 0 "the new script"
        want "try 1 ended 0" '^try 1: exit 0$' "$B/cleanup.out"
        want "the cleanup kept the four files in KEEP_DIR" "^events_capture: cleanup: the recorder's 4 files kept in $KEEP \(a partial capture, not the run's\)$" "$B/cleanup.out"
        want "OK, close may run" "^OK: the recorder egw-events-$RID is stopped and its partial capture is kept in $KEEP \(try 1\): 'close' may run$" "$B/cleanup.out"
        is "the unit on the stub guest" "$(cat "$EGW_STUB_STATE/unit-$RID")" inactive
        is "stops sent to the unit" "$(wc -l < "$EGW_STUB_STATE/supp.unit-stops")" 1
        keep_complete
        session_steps
        want "the try is a recorded step of the session (commands.jsonl)" "recorder-cleanup-$RID-try1" "$SESS/commands.jsonl"
        want "the try ran under timeout 120 (commands.jsonl)" '"timeout", "120", "bash"' "$SESS/commands.jsonl"
        want "the unit-state confirmation is recorded" "recorder-unit-state-$RID" "$SESS/commands.jsonl"
        want "the listing confirmation is recorded" "recorder-partial-capture-$RID" "$SESS/commands.jsonl"
        nothing_signalled
        cleanup_run
        want_rc 0 "the new script again (idempotent)"
        want "no new try: KEEP_DIR already holds the capture" '^KEEP_DIR already holds the partial capture' "$B/cleanup.out"
        want_no "no try ran the second time" '^## .* try [0-9]' "$B/cleanup.out"
        close_and_package
        ;;
    supp-retry)
        setup
        echo "EXPECTED: try 1 copies 3 of the 4 files (the scp of cli.stderr fails), ends 1, its INCOMPLETE staging folder is kept; try 2 keeps the four files; close; the package holds KEEP_DIR and the incomplete folder."
        term_path
        touch "$B/supp.scp.fail.cli.stderr"
        cleanup_run
        want_rc 0 "the new script"
        want "try 1 ended 1" '^try 1: exit 1$' "$B/cleanup.out"
        want "try 1's STOP names the incomplete copy" "^STOP: events_capture: 3 of the recorder's 4 files copied, kept INCOMPLETE in $KEEP\.copy\." "$B/cleanup.out"
        want "the script names the kept incomplete folder" "^kept INCOMPLETE \(not the run's capture, not KEEP_DIR\): $KEEP\.copy\." "$B/cleanup.out"
        want "try 2 ended 0" '^try 2: exit 0$' "$B/cleanup.out"
        want "OK after try 2" "\(try 2\): 'close' may run$" "$B/cleanup.out"
        INC=$(ls -d "$KEEP".copy.* 2> /dev/null | head -n 1)
        is "the incomplete staging folder holds 3 files" "$(ls "$INC" 2> /dev/null | wc -l)" 3
        keep_complete
        nothing_signalled
        close_and_package
        is "the package also holds the incomplete folder" "$(ls -d "$PKG"/recovery/events-partial-$RID.copy.* 2> /dev/null | wc -l)" 1
        ;;
    supp-hang)
        setup
        echo "EXPECTED: try 1's scp of events.jsonl hangs; timeout 120 ends the try (exit 124) at about 120 s; try 2 keeps the four files; close."
        term_path
        touch "$B/supp.scp.hang.events.jsonl"
        cleanup_run
        want_rc 0 "the new script"
        want "try 1 ended 124 (the bound)" '^try 1: exit 124 \(the 120 s bound: timeout.s TERM\)$' "$B/cleanup.out"
        HP=$(cat "$B/supp.scp.hang.pid" 2> /dev/null)
        is "the hung scp was ended by the try's timeout" "$([ -n "$HP" ] && [ -d "/proc/$HP" ] && echo alive || echo gone)" gone
        D1=$(awk '/^## .* try 1 of/ { split($2, a, "T"); print a[2] }' "$B/cleanup.out" | head -n 1)
        D2=$(awk '/^## .* try 2 of/ { split($2, a, "T"); print a[2] }' "$B/cleanup.out" | head -n 1)
        note "try 1 began at $D1 and try 2 at $D2 (UTC, from the script's own lines)"
        S1=$(awk -v a="$D1" -v b="$D2" 'BEGIN { split(a, x, ":"); split(b, y, ":"); print (y[1]*3600+y[2]*60+y[3]) - (x[1]*3600+x[2]*60+x[3]) }')
        is "try 1 lasted about the 120 s bound (between 118 and 140 s, wall clock)" "$([ "$S1" -ge 118 ] && [ "$S1" -le 140 ] && echo yes || echo "no ($S1 s)")" yes
        want "try 2 ended 0" '^try 2: exit 0$' "$B/cleanup.out"
        keep_complete
        nothing_signalled
        close_and_package
        ;;
    supp-halt)
        setup
        echo "EXPECTED: the unit is never shown stopped: three tries end 1, nothing is copied, HALT ('do NOT run close'); the script runs no close and signals nothing; the session stays open."
        term_path
        touch "$B/supp.unit-stuck"
        cleanup_run
        want_rc 1 "the new script (HALT)"
        is "three tries ran" "$(grep -c '^try [0-9]: exit 1$' "$B/cleanup.out")" 3
        want "each try's STOP: not shown stopped, nothing copied" "^STOP: events_capture: the unit egw-events-$RID was not shown stopped \(exit 1\) - it may still run on the guest; nothing was copied to $KEEP" "$B/cleanup.out"
        want "the HALT tells the operator not to close" "^HALT: 3 tries did not show the recorder stopped with its partial capture kept - do NOT run 'close'; nothing was signalled or powered off; hand back to Rui" "$B/cleanup.out"
        is "KEEP_DIR was not created" "$(exists "$KEEP")" absent
        is "the unit on the stub guest" "$(cat "$EGW_STUB_STATE/unit-$RID")" active
        nothing_signalled
        is "the session is still open (current_session)" "$(exists "$EGW_EXEC/current_session")" exists
        is "the session's state" "$(skey state)" open
        ;;
    *)
        echo "unknown scenario '$SC'"
        exit 2
        ;;
esac
finish
[ "$FAILS" -eq 0 ]
exit
} 2>&1
'''
out = S / "g3/t6supp/bench/bsupp_run.sh"
out.write_bytes((head + scen).encode("utf-8"))
print("written", out, len(head.splitlines()), "helper lines")
