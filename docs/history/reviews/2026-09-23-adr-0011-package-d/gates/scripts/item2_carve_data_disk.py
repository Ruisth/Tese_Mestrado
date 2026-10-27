#!/usr/bin/env python3
"""Package D, gate item 2: READ-ONLY search of the guest's Docker data-disk image.

The containers that ran controller_restart-r02 (broker c63352d738f2..., controller
9b2098915ade...) were removed and recreated on 2026-09-20, so their json-file logs no
longer exist as files. This looks for docker json-file log lines whose "time" field is
2026-09-19T00:MM (the guest session in which r02 ran) anywhere in the image bytes:

  1. `grep -a -b -o -F '"time":"2026-09-19T00:'` gives the byte offset of every such
     time field (a fixed-string search: no regular-expression backtracking);
  2. for each offset, the enclosing {"log":...,"stream":...,"time":...} line is read
     back from the image and parsed as JSON; lines that do not parse are counted, not kept;
  3. the allocation state of every 4 KiB block holding a kept line is asked of debugfs,
     opened read-only (no -w), in one session (testb, then icheck).

Nothing is mounted, the guest is not started and nothing is written to the image.
Output goes only to gates/item2_extract/. Run from WSL with any Python 3:

  python3 <review-record>/gates/scripts/item2_carve_data_disk.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

IMG = "/home/ruisth/yocto/egw-integrated/egw-data.img"
OUT = Path(__file__).resolve().parent.parent / "item2_extract"
HITS = OUT / "data_disk_jsonlog_2026-09-19T00.txt"
BLK = OUT / "data_disk_jsonlog_blocks.txt"
NEEDLE = b'"time":"2026-09-19T00:'
BS = 4096


def main() -> int:
    if subprocess.run(["pgrep", "-f", "qemu-system-aarch64"], capture_output=True).returncode == 0:
        print("STOP: a qemu-system-aarch64 process is running; the image is in use", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    st = os.stat(IMG)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    g = subprocess.run(["grep", "-a", "-b", "-o", "-F", NEEDLE.decode()], stdin=open(IMG, "rb"),
                       capture_output=True, env={**os.environ, "LC_ALL": "C"})
    offs = [int(x.split(b":", 1)[0]) for x in g.stdout.splitlines() if x]
    kept, bad = {}, 0
    with open(IMG, "rb") as fh:
        for o in offs:
            lo = max(0, o - 8192)
            fh.seek(lo)
            buf = fh.read(o - lo + 256)
            rel = o - lo
            start = buf.rfind(b'{"log":"', 0, rel)
            end = buf.find(b'"}', rel)
            if start < 0 or end < 0:
                bad += 1
                continue
            raw = buf[start:end + 2]
            try:
                j = json.loads(raw.decode("utf-8"))
                assert set(j) == {"log", "stream", "time"}
            except Exception:
                bad += 1
                continue
            kept[lo + start] = raw.decode("utf-8")
    with HITS.open("w", encoding="utf-8") as w:
        w.write(f"# image={IMG}\n# image_size={st.st_size} image_mtime_epoch={st.st_mtime}\n")
        w.write(f"# searched_utc={started}\n# needle={NEEDLE.decode()} occurrences={len(offs)} "
                f"parsed_lines={len(kept)} unparsed={bad}\n")
        for o in sorted(kept):
            w.write(f"{o}:{kept[o]}\n")
    blocks = sorted({o // BS for o in kept})
    cmd = OUT / ".item2_debugfs_cmds"
    with cmd.open("w") as c:
        for b in blocks:
            c.write(f"testb {b}\n")
        for k in range(0, len(blocks), 200):
            c.write("icheck " + " ".join(str(b) for b in blocks[k:k + 200]) + "\n")
    d = subprocess.run(["debugfs", "-f", str(cmd), IMG], capture_output=True, text=True)
    cmd.unlink()
    in_use = [ln for ln in d.stdout.splitlines() if ln.startswith("Block ") and "marked in use" in ln]
    not_used = [ln for ln in d.stdout.splitlines() if ln.startswith("Block ") and "not in use" in ln]
    owned = [ln for ln in d.stdout.splitlines() if ln[:1].isdigit() and "<block not found>" not in ln
             and "\t" in ln]
    with BLK.open("w", encoding="utf-8") as w:
        w.write(f"# block_size={BS} distinct_blocks={len(blocks)} marked_in_use={len(in_use)} "
                f"not_in_use={len(not_used)} owned_by_an_inode={len(owned)}\n")
        w.write(d.stdout)
    for p in (HITS, BLK):
        print(hashlib.sha256(p.read_bytes()).hexdigest(), p.name)
    print(f"occurrences={len(offs)} parsed={len(kept)} unparsed={bad} blocks={len(blocks)} "
          f"in_use={len(in_use)} not_in_use={len(not_used)} owned={len(owned)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
