"""The bounded check of the S4 preparation (2026-10-05): F3 (host script fails closed on git) and F2 (sealing lines).
Usage: python fix_check2.py <P>"""
import sys
from pathlib import Path

P = Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_bytes().decode("utf-8")
    assert "\r\n" not in s, name
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:100])
        s = s.replace(old, new)
    p.write_bytes(s.encode("utf-8"))


edit("g3_hostprep.sh", [
    ("""git -C "$C" for-each-ref --format='%(objectname) %(refname)' refs/heads | tee "$PKG/branches-before.txt"
""",
     """# S4 (bounded check of 2026-10-05, F3): git's own status is kept (no pipe) and an empty listing is a stop.
git -C "$C" for-each-ref --format='%(objectname) %(refname)' refs/heads > "$PKG/branches-before.txt" \\
    || fail "git for-each-ref failed in $C"
[ -s "$PKG/branches-before.txt" ] || fail "the branch listing of $C is empty"
cat "$PKG/branches-before.txt"
"""),
    ("""    [ -z "$(git -C "$C" diff --stat "$IMAGE" "$TOOLS" -- "$d")" ] || fail "$d differs from the image commit $IMAGE"
""",
     """    # S4 (bounded check of 2026-10-05, F3): a failed git, or a path at neither commit, is a stop, never 'identical'.
    git -C "$C" cat-file -e "$TOOLS:$d" && git -C "$C" cat-file -e "$IMAGE:$d" || fail "$d is not in both $IMAGE and $TOOLS"
    out=$(git -C "$C" diff --stat "$IMAGE" "$TOOLS" -- "$d") || fail "git diff failed for $d"
    [ -z "$out" ] || fail "$d differs from the image commit $IMAGE"
"""),
])

s = (P / "g3_hostprep.sh").read_bytes().decode("utf-8")
print("branches-after uses:", [ln for ln in s.splitlines() if "branches-after" in ln][:4])

edit("host-notes.md", [
    ("""bash "$P/seal_prep.sh" "$P" "$P/operator-procedure.md" "$OT/runs/$D/HIST_$D-g3-t6-host-preparation"; echo "exit=$?"; (cd""",
     """bash "$P/seal_prep.sh" "$P" "$P/operator-procedure.md" "$OT/runs/$D/HIST_$D-g3-t6-host-preparation"; rc=$?; echo "exit=$rc"; { [ $rc -eq 0 ] || [ $rc -eq 3 ]; } && (cd"""),
])
s = (P / "host-notes.md").read_bytes().decode("utf-8")
i = s.index('bash "$P/ops/seal_ops.sh" S4')
print(s[i:i + 700])
