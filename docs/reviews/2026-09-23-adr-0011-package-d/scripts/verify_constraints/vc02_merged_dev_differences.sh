#!/usr/bin/env bash
# vc02 - the cited files that differ between the WSL clone's current commit
# (b7e0c83) and the merged dev head the ADR names (35fe8bb), and the cited
# lines of those files at 35fe8bb and at 3549d46. Uses the Windows worktree,
# the only local repository holding 35fe8bb. Read-only: git show / diff / log.
# Run from Git Bash:  bash <this file>
set -u
# the worktree sits four levels above this script: <scratchpad>/devwt, beside pkgD/
REPO="$(cd "$(dirname "$0")/../../../.." && pwd)/devwt"
g() { git -C "$REPO" "$@"; }
r() { # r <ref> <path> <from> [to]
  local ref="$1" p="$2" a="$3" b="${4:-$3}"
  echo "--- $ref:$p:$a${4:+-$4}"
  local n; n=$(g show "$ref:$p" | wc -l)
  if [ "$b" -gt "$n" ]; then echo "   RANGE BEYOND EOF (file has $n lines)"; fi
  g show "$ref:$p" | awk -v a="$a" -v b="$b" 'NR>=a && NR<=b {printf "%5d  %s\n", NR, substr($0,1,230)}'
}
echo "== refs"
g log -1 --format='%H %ci %s' 35fe8bb
g log -1 --format='%H %ci %s' origin/dev
g log -1 --format='%H %ci %s' 3549d46
g merge-base --is-ancestor b7e0c83 35fe8bb && echo "b7e0c83 is an ancestor of 35fe8bb"
g merge-base --is-ancestor 3549d46 35fe8bb && echo "3549d46 IS on 35fe8bb" || echo "3549d46 is NOT an ancestor of 35fe8bb"
echo "== cited paths changed b7e0c83..35fe8bb"
g diff --stat b7e0c83 35fe8bb -- src/egw_controller src/egw_experiments src/egw_simulator src/deployment src/CONTRACTS.md src/Dockerfile src/pyproject.toml docs/setup docs/adr docs/claim_evidence_matrix.md docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md docs/governance/proposals/acceptance_protocol_update_2026-09-19.md PROGRESS.md docs/evidence/integrated-qemu docs/reviews
echo "(end)"
echo "== plan lines at 35fe8bb"
P=docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md
r 35fe8bb $P 104
r 35fe8bb $P 630 631
r 35fe8bb $P 638 640
echo "--- where the phrases are at 35fe8bb and at b7e0c83"
for ref in 35fe8bb b7e0c83; do
  echo "[$ref]"; g show "$ref:$P" | grep -n -E 'material changes require an ADR|controller restart with recovery inside|sizing finding' | cut -c1-200
done
echo "== PROGRESS.md"
r 35fe8bb PROGRESS.md 509
r 3549d46 PROGRESS.md 509
r 3549d46 PROGRESS.md 180
r 35fe8bb PROGRESS.md 180
for ref in b7e0c83 35fe8bb 3549d46; do
  echo "[$ref] PROGRESS.md lines: $(g show "$ref:PROGRESS.md" | wc -l)"
  g show "$ref:PROGRESS.md" | grep -n -E 'without a hashed lock|unpinned|not locked|G3 qualifying runs' | cut -c1-220
done
echo "== LOG #C039 at 3549d46 and 35fe8bb"
for ref in 35fe8bb 3549d46; do
  echo "[$ref]"; g show "$ref:LOG.md" 2>/dev/null | grep -n -E '#C039|C039' | head -5 | cut -c1-220
done
echo "== ADR README format and status vocabulary at 35fe8bb"
g show 35fe8bb:docs/adr/README.md
echo "== length and section headings of every ADR at 35fe8bb"
for f in $(g ls-tree --name-only 35fe8bb docs/adr/ | grep -E '/[0-9]{4}-'); do
  echo "$f: $(g show "35fe8bb:$f" | wc -l) lines; headings: $(g show "35fe8bb:$f" | grep -E '^## ' | sed 's/^## //' | tr '\n' '|')"
done
echo "== session, acknowledgement and restart terms in the existing ADRs at 35fe8bb"
g grep -n -i -E 'clean.?session|persistent session|puback|manual.?ack|shutdown sequence|restart' 35fe8bb -- docs/adr/ | cut -c1-200
echo "== ADR 0010 on the shutdown sequence and the shutdown exclusion, at 35fe8bb"
A10=docs/adr/0010-controller-progress-counters.md
r 35fe8bb $A10 78 81
r 35fe8bb $A10 113 116
r 35fe8bb $A10 139 141
echo "== the protocol proposal on the order of evidence and design decision, at 35fe8bb and b7e0c83"
PP=docs/governance/proposals/acceptance_protocol_update_2026-09-19.md
for ref in 35fe8bb b7e0c83; do r $ref $PP 418 425; r $ref $PP 452 455; done
echo "== header block of every ADR at 35fe8bb"
for f in $(g ls-tree --name-only 35fe8bb docs/adr/ | grep -E '/[0-9]{4}-'); do
  echo "----- $f"; g show "35fe8bb:$f" | head -14
done
echo "== ADR numbers ever added on any ref"
g log --all --diff-filter=A --name-only --format='' -- docs/adr/ | sort -u
echo "== 0011 anywhere at 35fe8bb (all paths)"
g grep -n -E '\b0011\b' 35fe8bb -- . | cut -c1-200 | head -20
echo "== 0011 on any ref's docs/adr"
for ref in $(g for-each-ref --format='%(refname)' refs/heads refs/remotes); do g ls-tree --name-only "$ref" docs/adr/ 2>/dev/null | grep -E '/0011|/0009' | sed "s|^|$ref: |"; done
echo "(end)"
