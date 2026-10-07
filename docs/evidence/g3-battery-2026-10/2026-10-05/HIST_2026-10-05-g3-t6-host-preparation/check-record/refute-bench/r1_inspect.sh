#!/bin/bash
# reviewer: read-only inspection of the bench's leftover state
SC=${1:-pass}
B=/tmp/g3-s4-bench/$SC
A=$(ls -d $B/egw-exec/attempts/*_g3-qualification-t6_attempt0* 2>/dev/null | grep -v 20261003T132936Z | head -n 1)
echo "attempt: $A"
ls "$A" "$A/console" "$A/environment" 2>&1
C=$(ls "$A"/console/*-t6.stdout.txt 2>/dev/null | tail -n 1)
echo "console: $C"
[ -n "$C" ] && wc -l "$C"
[ -n "$C" ] && grep -n '' "$C" | cut -c1-260 | head -n "${2:-200}"
