"""Compare the guest's deployed tree (sha256 list on stdin file) with the clean clone.

Usage: deployed_vs_clone.py <sha256sum-output-file> <clone src/deployment dir>
Secrets (.env, passwd, certs) and data/ are never listed by the caller.
"""
import hashlib
import os
import sys

listing, repo = sys.argv[1], sys.argv[2]
deployed = {}
for line in open(listing, encoding="utf-8"):
    parts = line.strip().split(None, 1)
    if len(parts) == 2 and len(parts[0]) == 64:
        deployed[parts[1][2:] if parts[1].startswith("./") else parts[1]] = parts[0]
same = differ = only_guest = 0
for rel, digest in sorted(deployed.items()):
    p = os.path.join(repo, rel)
    if not os.path.isfile(p):
        print(f"ONLY ON GUEST  {rel}")
        only_guest += 1
        continue
    with open(p, "rb") as fh:
        local = hashlib.sha256(fh.read()).hexdigest()
    if local == digest:
        same += 1
    else:
        print(f"DIFFERS        {rel}  guest={digest[:12]} clone={local[:12]}")
        differ += 1
print(f"deployed files equal to the clean clone: {same}; different: {differ}; only on the guest: {only_guest}")
