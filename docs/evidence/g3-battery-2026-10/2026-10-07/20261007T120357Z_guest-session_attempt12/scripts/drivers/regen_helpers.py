"""Regenerate ~/egw-tcg/itest-helpers.sh from the runbook's section 6.1 heredoc.

Usage: regen_helpers.py <runbook.md> <target helper file>
The previous file is kept beside it as <name>.<first 12 hex of its sha256>
before the new text is written; nothing else is touched.
"""
import hashlib
import os
import sys

runbook, target = sys.argv[1], sys.argv[2]
lines = open(runbook, encoding="utf-8").read().splitlines(keepends=True)
start = next(i for i, ln in enumerate(lines) if ln.startswith("host$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'"))
end = next(i for i in range(start + 1, len(lines)) if lines[i].rstrip("\n") == "EOF")
body = "".join(lines[start + 1:end])
if os.path.exists(target):
    old = open(target, "rb").read()
    keep = f"{target}.{hashlib.sha256(old).hexdigest()[:12]}"
    if not os.path.exists(keep):
        with open(keep, "wb") as fh:
            fh.write(old)
    print(f"kept the previous helper as {keep}")
with open(target, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(body)
print(f"wrote {target}: sha256 {hashlib.sha256(body.encode()).hexdigest()} ({body.count(chr(10))} lines)")
