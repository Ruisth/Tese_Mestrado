"""Compare the guest's deployed tree (sha256 list on stdin file) with the clean clone.

Usage: deployed_vs_clone.py [--exclude GLOB]... <sha256sum-output-file>
                            <clone src/deployment dir> [allowed ...]
Secrets (.env, passwd, certs) and data/ are never listed by the caller.

The comparison runs in BOTH directions, because a file the guest has lost is as
much a difference as a file it has changed: every listed path is compared with
the clone's bytes, and every file of the clone that the listing does not carry
is reported as only in the clone. The caller passes its own exclusions, the
ones it used when it listed the deployed tree, so that a path it never listed
is not mistaken for a lost file: a ``--exclude`` value without a slash matches
a file's name anywhere in the tree (``find -name``), one with a slash matches
the package-relative path (``find -path``, without the leading ``./``).

Every difference is a problem, and the comparison fails closed: an empty or
unreadable listing, a line that is not `<64 hex> <path>`, a file that is only on
the guest, a file that is only in the clone and a file whose bytes differ all
make the exit status non-zero. The optional trailing arguments name the
package-relative paths whose difference is allowed (the preflight driver allows
`README.md` only); an allowed path is listed as such and counted apart, never
hidden.

Exit status: 0 no difference outside the allowed paths; 1 at least one
difference, or the listing could not be used.
"""
import fnmatch
import hashlib
import os
import sys

USAGE = ("usage: deployed_vs_clone.py [--exclude GLOB]... <sha256sum-output-file> "
         "<clone src/deployment dir> [allowed ...]")


def parse(argv):
    """The exclusion globs, the listing, the clone and the allowed paths."""
    excludes, rest = [], list(argv)
    while rest and rest[0].startswith("-"):
        option = rest.pop(0)
        if option == "--":
            break
        if option != "--exclude" or not rest:
            print(f"UNKNOWN OPTION {option}\n{USAGE}", file=sys.stderr)
            sys.exit(1)
        excludes.append(rest.pop(0))
    if len(rest) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    return excludes, rest[0], rest[1], set(rest[2:])


def excluded(rel, globs):
    """True when the caller never listed this clone path on the guest."""
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatchcase(rel if "/" in glob else name, glob) for glob in globs)


def clone_files(repo, globs):
    """Every file of the clone the caller would have listed, package-relative."""
    found = set()
    for directory, _, names in os.walk(repo):
        for name in names:
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            rel = os.path.relpath(path, repo).replace(os.sep, "/")
            if not excluded(rel, globs):
                found.add(rel)
    return found


excludes, listing, repo, allowed = parse(sys.argv[1:])
try:
    with open(listing, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
except OSError as exc:
    print(f"UNUSABLE LISTING  {listing}: {exc}")
    sys.exit(1)

deployed = {}
unreadable = 0
for number, line in enumerate(lines, 1):
    if not line.strip():
        continue
    parts = line.strip().split(None, 1)
    if len(parts) != 2 or len(parts[0]) != 64 or any(c not in "0123456789abcdef" for c in parts[0]):
        print(f"UNREADABLE     line {number}: {line!r}")
        unreadable += 1
        continue
    deployed[parts[1][2:] if parts[1].startswith("./") else parts[1]] = parts[0]

same = differ = only_guest = only_clone = allowed_differences = 0
for rel, digest in sorted(deployed.items()):
    p = os.path.join(repo, rel)
    if not os.path.isfile(p):
        print(f"ONLY ON GUEST  {rel}{'  (allowed)' if rel in allowed else ''}")
        if rel in allowed:
            allowed_differences += 1
        else:
            only_guest += 1
        continue
    with open(p, "rb") as fh:
        local = hashlib.sha256(fh.read()).hexdigest()
    if local == digest:
        same += 1
    elif rel in allowed:
        print(f"DIFFERS        {rel}  guest={digest[:12]} clone={local[:12]}  (allowed)")
        allowed_differences += 1
    else:
        print(f"DIFFERS        {rel}  guest={digest[:12]} clone={local[:12]}")
        differ += 1

for rel in sorted(clone_files(repo, excludes) - set(deployed)):
    print(f"ONLY IN CLONE  {rel}{'  (allowed)' if rel in allowed else ''}")
    if rel in allowed:
        allowed_differences += 1
    else:
        only_clone += 1

print(f"deployed files equal to the clean clone: {same}; different: {differ}; "
      f"only on the guest: {only_guest}; only in the clone: {only_clone}; "
      f"allowed differences: {allowed_differences}; unreadable lines: {unreadable}")
if not deployed:
    print(f"NOTHING COMPARED: {listing} holds no usable sha256 line; the deployed "
          "tree was NOT compared with the clone")
    sys.exit(1)
sys.exit(1 if (differ or only_guest or only_clone or unreadable) else 0)
