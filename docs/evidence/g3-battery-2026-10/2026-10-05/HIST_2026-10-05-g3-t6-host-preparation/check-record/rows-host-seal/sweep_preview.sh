#!/bin/bash
# Independent reviewer's preview of the sealing sweep (read-only): the same loop as seal_prep.sh
# (values through a file descriptor, never on a command line, never printed) over the files of
# the preparation folder that seal_prep.sh would copy today. Prints names, counts and matching
# file NAMES only.
set -u
P=/mnt/c/Users/ruimf/AppData/Local/Temp/claude/C--Users-ruimf-Documents-Projeto-Mestrado/d631a3f3-65ca-4372-97f1-525d6d1e593d/scratchpad/g3/t6prep
ENVF=$HOME/egw-tcg/.env
TARGETS=("$P"/*.md "$P"/*.sh "$P"/*.py "$P/rows" "$P/ops" "$P/rows-record" "$P/host-record" "$P/operator-record")
[ -d "$P/bench" ] && TARGETS+=("$P/bench")
hits=0 swept=0
while IFS='=' read -r name value; do
    case "$name" in *PASS*|*SECRET*|*TOKEN*|*KEY*|*CREDENTIAL*) ;; *) continue ;; esac
    value=${value%\"}; value=${value#\"}; value=${value%\'}; value=${value#\'}
    [ "${#value}" -ge 4 ] || { echo "skipped (shorter than 4): $name"; continue; }
    files=$(grep -rlF -f <(printf '%s\n' "$value") -- "${TARGETS[@]}" 2> /dev/null)
    n=$(printf '%s' "$files" | grep -c .)
    echo "secret sweep preview: $name -> $n file(s)"
    [ "$n" -eq 0 ] || printf '%s\n' "$files" | sed "s|$P|<P>|; s/^/    /"
    hits=$((hits + n)); swept=$((swept + 1))
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENVF")
echo "swept=$swept hits=$hits"
grep -c $'\r' "$ENVF" | sed 's/^/CR lines in .env: /'
