#!/bin/sh
# proof_events_recorder.sh - the guest's continuous Docker events recorder of
# one proof run (ADR 0011 item 18; the r03 closure, Deliverable C).
#
# WHY A RECORDER. The run's Docker events used to be read once, at the end,
# as a history query ('docker events --since T0 --until NOW'). The daemon
# keeps a bounded history (256 events, as Docker documents it), and a query
# says nothing when that history was cut: r03's copy began at 21:19:32Z,
# twenty minutes after its '--since', with the kill and the start of the
# fault missing and the fetch exited 0. Adding '--since' again changes
# nothing. This recorder subscribes BEFORE the workload and the fault and
# follows the daemon until it is stopped after the post-drain copy, so what
# the run's window held is captured as it happens, and the end of the
# subscription is recorded, never inferred from a file that exists or from
# an exit status of 0 (the CLI answers 0 when the daemon closes the stream).
#
# Usage (on the guest, as the unit proof.sh starts: 'sudo systemd-run --unit
# egw-events-RUN_ID --collect sh DIR/recorder.sh DIR SINCE'):
#   proof_events_recorder.sh DIR SINCE_GUEST_EPOCH
#   DIR    the run's capture directory (/tmp/egw-events-RUN_ID), created by
#          the start step with the files below already present, so that
#          the driver's own user can append to them and read them
#   SINCE  the guest epoch the subscription replays from (a little before
#          the start: the replay proves the subscription answers, and the
#          daemon serves it under the same lock as the live stream)
#
# What it writes, all under DIR and all appended (never truncated):
#   events.jsonl   every container event, one JSON object per line
#                  ('docker events --format {{json .}}', with its timeNano)
#   cli.stderr     whatever the CLI said on stderr (empty when nothing)
#   lifecycle.txt  one line per transition, on the guest clock:
#                    start epoch=E pid=P since=S
#                    cli-start epoch=E cli_pid=P
#                    cli-exit epoch=E rc=R stop_requested=yes|no
#                  (the start step adds 'ready ...' between the last two).
#                  A stop that arrives before the CLI was started starts
#                  none and writes 'cli-exit epoch=E rc=none
#                  stop_requested=yes cli_started=no'.
#
# THE STOP IS THE ONLY EXPECTED END. 'systemctl stop' sends TERM to the unit
# (the recorder and the CLI alike): the trap marks the stop as requested and
# passes TERM to the CLI, and 'stop_requested=yes' is written with the CLI's
# end. A CLI that ends by itself - the daemon went away, the stream was
# closed, the CLI failed at start - is written 'stop_requested=no', WHATEVER
# its status: that is a break in coverage, which the fetch's checker
# (events_coverage.py) never reads as complete.
#
# BusyBox ash: no bashism, no 'SIG' prefix on the trap names; 'wait' returns
# early (above 128) when a trapped signal arrives, so the CLI's own status is
# read by a second 'wait' in that case (127 there: the first one had read it).
D=$1
SINCE=$2
L=$D/lifecycle.txt
stop=no
pid=
trap 'stop=yes; [ -z "$pid" ] || kill -TERM "$pid" 2> /dev/null' TERM INT HUP
echo "start epoch=$(date +%s) pid=$$ since=$SINCE" >> "$L"
if [ "$stop" = yes ]; then
    # Stopped before the CLI was started: none is started, so none is left
    # behind, and the record says so.
    echo "cli-exit epoch=$(date +%s) rc=none stop_requested=yes cli_started=no" >> "$L"
    exit 0
fi
docker events --since "$SINCE" --filter type=container --format '{{json .}}' >> "$D/events.jsonl" 2>> "$D/cli.stderr" &
pid=$!
# A stop that arrived between the start of the CLI and the line above found
# no pid to pass on: passed on now.
[ "$stop" = no ] || kill -TERM "$pid" 2> /dev/null
echo "cli-start epoch=$(date +%s) cli_pid=$pid" >> "$L"
rc=0
wait "$pid" || rc=$?
if [ "$stop" = yes ]; then
    rc2=0
    wait "$pid" 2> /dev/null || rc2=$?
    [ "$rc2" -eq 127 ] || rc=$rc2
fi
echo "cli-exit epoch=$(date +%s) rc=$rc stop_requested=$stop" >> "$L"
[ "$stop" = no ] || exit 0
exit "$rc"
