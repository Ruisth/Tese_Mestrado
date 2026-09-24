#!/bin/bash
# Item 4: every place 'drained' is defined or called, at the merged dev head and
# in the WSL execution clone, plus the deployed helper file compared with the
# runbook heredoc it is generated from. Read-only: git show / git grep /
# git rev-parse / git diff --stat only; nothing is checked out or fetched.
# Run from Git Bash: bash item4_callsites.sh
set -u
WIN_REPO="${WIN_REPO:-$(cd "$(dirname "$0")/../../../devwt" && pwd)}"   # the scratchpad worktree; it shares objects and refs with the Windows clone
REV="${REV:-35fe8bb}"
RB=docs/setup/qemu_integrated_gateway.md

echo "== identity"
git -C "$WIN_REPO" rev-parse "$REV"
git -C "$WIN_REPO" log -1 --format='%h %ci %s' "$REV"
echo "WSL clone HEAD: $(wsl -d Ubuntu-24.04 --exec bash -lc 'git -C /home/ruisth/egw-exec/repo rev-parse HEAD')"
echo "runbook and tools/session/{nominal,slice}.sh differ between b7e0c83 and $REV? (empty = identical)"
git -C "$WIN_REPO" diff --stat b7e0c83 "$REV" -- "$RB" tools/session/nominal.sh tools/session/slice.sh

echo; echo "== runbook ($RB at $REV): definition, callers, the quiet-window argument"
git -C "$WIN_REPO" show "$REV:$RB" | grep -n -E '^drained\(\)|^_mline\(\)|^pre\(\)|^finish\(\)|^post\(\)|^run_test\(\)|&& drained|drained &&|\bdrained\b.*;|DRAIN_(QUIET|STEP|LIMIT)_S:-' | cut -c1-170

echo; echo "== tools/session at $REV"
git -C "$WIN_REPO" grep -n -E '(^|[^_[:alnum:]])drained([^_[:alnum:]]|$)|(^|[" ])pre [A-Z$]' "$REV" -- tools/session/ | grep -v '^[^:]*:[^:]*:[0-9]*:#' | cut -c1-170

echo; echo "== harness and reconciliation helper: any drain of their own?"
git -C "$WIN_REPO" grep -n -i -E 'drained|quiet window' "$REV" -- src/egw_experiments/ | cut -c1-170 || echo "(none)"

echo; echo "== deployed helper file vs the runbook heredoc (runbook :610-878 at $REV)"
diff <(git -C "$WIN_REPO" show "$REV:$RB" | sed -n '610,878p' | tr -d '\r') \
     <(wsl -d Ubuntu-24.04 --exec bash -lc 'cat ~/egw-tcg/itest-helpers.sh' | tr -d '\r') && echo IDENTICAL
wsl -d Ubuntu-24.04 --exec bash -lc 'sha256sum ~/egw-tcg/itest-helpers.sh; grep -n -E "^drained\(\)|^pre\(\)|^finish\(\)|&& drained" ~/egw-tcg/itest-helpers.sh'
