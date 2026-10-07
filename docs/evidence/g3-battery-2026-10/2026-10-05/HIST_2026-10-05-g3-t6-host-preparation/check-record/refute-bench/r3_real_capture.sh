#!/bin/bash
# reviewer: read-only: the REAL events_capture.sh (source copy) - the order of writes and the stop in 'cleanup'
S=/tmp/g3-s4-bench/_src/tools/session
sha256sum "$S/events_capture.sh" "$S/proof_fetch_sut_log.sh"
wc -l "$S/events_capture.sh"
grep -n '' "$S/events_capture.sh" | cut -c1-220 | sed -n "${1:-1},${2:-400}p"
