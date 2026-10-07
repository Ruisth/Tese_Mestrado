#!/bin/bash
# Bench of the second opening of S3: the fixture of the real failed preflight, in a bench.
#   <dest>/attempts/<run id>/      a COPY (cp -a) of the exported package
#                                  output_test/runs/2026-10-05/20261005T105656Z_live-preflight_attempt11
#                                  (read-only; checked against the package's own SHA256SUMS);
#   <dest>/preflight.console.txt   the driver console as the operator script saw it
#                                  (~/egw-exec/g3-t8t9-s3/S3-preflight.console.txt, kept in this
#                                  folder as fixture/S3-preflight.console.txt, sha256 checked)
#                                  WITHOUT its last line 'preflight.sh exit=3', which the
#                                  script's run_driver appends itself; it ends with the
#                                  DRIVER RESULT line;
#   <dest>/exit                    3, the stub driver's exit status.
# The run id, the directory name and the DRIVER RESULT line are the real ones and equal. Then
# bs3b_mutate.py makes the variant's one change to the copy. Prints what it made, with the
# sha256 of attempt.json and commands.jsonl and a hash of the whole attempt tree (every file's
# sha256, every entry's path, modification time, size and mode).
# Usage (WSL): bs3b_fixture.sh <variant> /tmp/g3-s3b-bench/<...>/<dest>
set -u
VARIANT=${1:?usage: bs3b_fixture.sh <variant> <dest>}
DEST=${2:?usage: bs3b_fixture.sh <variant> <dest>}
case $DEST in /tmp/g3-s3b-bench/?*) ;; *) echo "refused: <dest> must be under /tmp/g3-s3b-bench/"; exit 2 ;; esac
[ ! -e "$DEST/attempts" ] || { echo "refused: $DEST/attempts exists"; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
RID=20261005T105656Z_live-preflight_attempt11
PKG="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test/runs/2026-10-05/$RID"
CONSOLE=$HERE/fixture/S3-preflight.console.txt
CONSOLE_SHA=bd7bdb373948869d61ea35a48e2292b3ffcb2a93dd848da2936b8fdb1994390c
sha() { if [ -f "$1" ]; then /usr/bin/sha256sum "$1" | cut -d' ' -f1; else echo absent; fi; }
tree_hash() {     # tree_hash DIR: every file's sha256, every entry's path, mtime, size and mode
    [ -d "$1" ] || { echo absent; return; }
    (cd "$1" && { find . -type f -print0 | LC_ALL=C sort -z | xargs -0 /usr/bin/sha256sum; find . -printf '%P %T@ %s %m\n' | LC_ALL=C sort; }) | /usr/bin/sha256sum | cut -d' ' -f1
}
[ -d "$PKG" ] || { echo "refused: the package $PKG is not there"; exit 1; }
[ "$(sha "$CONSOLE")" = "$CONSOLE_SHA" ] || { echo "refused: $CONSOLE is not the recorded console ($CONSOLE_SHA)"; exit 1; }
[ "$(tail -n 1 "$CONSOLE")" = "preflight.sh exit=3" ] || { echo "refused: the console's last line is not 'preflight.sh exit=3'"; exit 1; }
mkdir -p "$DEST/attempts" || exit 1
cp -a "$PKG" "$DEST/attempts/$RID" || exit 1
n=$(cd "$DEST/attempts/$RID" && /usr/bin/sha256sum -c --quiet SHA256SUMS > /dev/null 2>&1 && wc -l < SHA256SUMS)
[ -n "$n" ] || { echo "refused: the copy does not match the package's own SHA256SUMS"; exit 1; }
head -n -1 "$CONSOLE" > "$DEST/preflight.console.txt" || exit 1
echo 3 > "$DEST/exit"
echo "fixture: a copy of the exported package $RID (output_test/runs/2026-10-05; $(find "$DEST/attempts/$RID" -type f | wc -l) files; the copy matches the package's own SHA256SUMS, $n files); the driver console (sha256 $CONSOLE_SHA, the operator script's S3-preflight.console.txt) without its last line 'preflight.sh exit=3'; last line now: $(tail -n 1 "$DEST/preflight.console.txt" | cut -c1-60)..."
PYTHONDONTWRITEBYTECODE=1 "$REAL_PY" "$HERE/bs3b_mutate.py" "$VARIANT" "$DEST" || exit 1
for a in "$DEST"/attempts/*/; do
    a=${a%/}
    echo "FIXTURE ${a##*/}: attempt.json $(sha "$a/attempt.json") commands.jsonl $(sha "$a/commands.jsonl") tree $(tree_hash "$a")"
done
echo "FIXTURE console: sha256 $(sha "$DEST/preflight.console.txt"); its DRIVER RESULT line: $(grep '^DRIVER RESULT ' "$DEST/preflight.console.txt" | cut -c1-80)..."
