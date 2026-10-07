#!/bin/bash
# Stream OPERATOR: after the isolated exercises - read-only. Shows that nothing under the
# real trees is newer than the first bench of this stream, that no bench process and no
# qemu-system-aarch64 process is left, and where the execution clone stands.
# Usage (WSL): op_after.sh <name of the first bench>    (the bench is /tmp/g3-s3-op-<name>; only the
# name is given, so that no command line of the caller holds the path the process search looks for)
set -u
REF=/tmp/g3-s3-op-${1:?usage: op_after.sh <name of the first bench>}/stubs/git
[ -e "$REF" ] || { echo "the reference $REF is not there"; exit 2; }
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) reference (the first file this stream wrote in WSL): $(stat -c '%y' "$REF")"
echo "entries under ~/egw-exec (venv apart), ~/egw-tcg and ~/egw-images newer than the reference:"
find "$HOME/egw-exec" "$HOME/egw-tcg" "$HOME/egw-images" -path "$HOME/egw-exec/venv" -prune -o -newer "$REF" -print 2> /dev/null | head -n 20
echo "(end of list)"
echo "entries under ~/yocto, to depth 4, newer than the reference:"
find "$HOME/yocto" -maxdepth 4 -newer "$REF" -print 2> /dev/null | head -n 20
echo "(end of list)"
echo "compiled python files of the venv newer than the reference: $(find "$HOME/egw-exec/venv" -newer "$REF" -name '*.pyc' 2> /dev/null | wc -l)"
for d in "$HOME/egw-exec" "$HOME/egw-exec/attempts" "$HOME/egw-exec/g3-battery" "$HOME/egw-tcg" "$HOME/egw-tcg/itest" "$HOME/egw-exec/repo/.git/index"; do
    echo "  $(stat -c '%y' "$d" | cut -c1-19)  ${d/#$HOME/~}"
done
echo "~/egw-exec/g3-t8t9-s3 exists: $([ -e "$HOME/egw-exec/g3-t8t9-s3" ] && echo YES || echo no); ~/egw-exec/current_session exists: $([ -e "$HOME/egw-exec/current_session" ] && echo YES || echo no)"
echo "execution clone HEAD: $(git -C "$HOME/egw-exec/repo" rev-parse HEAD)"
echo "qemu-system-aarch64 processes: $(pgrep -af '^(\S*/)?qemu-system-aarch64( |$)' | wc -l); processes of this stream's benches: $(pgrep -f '/tmp/g3-s3-op-' | grep -v -x "$$" | wc -l)"
echo "benches of this stream in WSL: $(ls -d /tmp/g3-s3-op-* 2> /dev/null | tr '\n' ' ')"
