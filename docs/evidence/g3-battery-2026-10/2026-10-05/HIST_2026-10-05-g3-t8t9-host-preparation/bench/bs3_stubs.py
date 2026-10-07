#!/usr/bin/env python3
"""Stream BENCH: the stubs of the repository's own test module, put into a bench.

The test module src/tests/test_runbook_itest_helpers.py of the read-only worktree holds
stub commands written for the runbook's own lines (STUB_SSH, STUB_CURL, STUB_PYTHON,
STUB_SCP, STUB_SS, STUB_SLEEP, STUB_TIMEOUT, STUB_FETCH_SUT_LOG), a Bench class that
installs them, and t8_prepare, which gives the stub guest the state a success of test 8
needs. This script IMPORTS that module (its sha256 is asserted first) and uses those
objects as they are:

  <bench>/mod/stubs/   the module's stubs, as its Bench class installs them
  <bench>/mod/state/   the stub guest's state (EGW_STUB_STATE), prepared by t8_prepare
  <bench>/mod/clone/   the module's stub clone (its stub of proof_fetch_sut_log.sh)

and it writes the two host files with the runbook's own heredocs (the module's
tunnel_heredoc and helpers_heredoc), run with HOME inside the bench:

  <bench>/home/egw-tcg/tunnel.sh, <bench>/home/egw-tcg/itest-helpers.sh

Three things are added to what t8_prepare leaves, each for session S3:
  - the smoke's files under the S3 run id (the module's full_run with that id);
  - the broker log window of test 9 (b) and (c) (the state file the module's own
    test 9 cases set);
  - nothing else: every other state file is the module's.

Nothing of the worktree is written: PYTHONDONTWRITEBYTECODE=1 is required.
Usage (WSL, the execution venv's python): bs3_stubs.py <worktree> <bench>
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

MODULE_SHA256 = "fe8baa60d41a088807e071a462d4ff36674f7325ed18a9e480159b14db719ff1"
RUNBOOK_SHA256 = "4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db"
HELPER_SHA256 = "e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb"
TUNNEL_SHA256 = "38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1"
SMOKE_S3 = "itest-post-reboot-01-q2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    worktree, bench = Path(sys.argv[1]), Path(sys.argv[2])
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        print("refused: PYTHONDONTWRITEBYTECODE=1 is required (nothing of the worktree is written)")
        return 2
    sys.dont_write_bytecode = True
    if not str(bench).startswith("/tmp/g3-s3-bench/") or not bench.is_dir():
        print(f"refused: {bench} is not a bench directory under /tmp/g3-s3-bench/")
        return 2
    source = worktree / "src" / "tests" / "test_runbook_itest_helpers.py"
    got = sha256(source)
    if got != MODULE_SHA256:
        print(f"refused: the test module {source} is {got}, not {MODULE_SHA256}")
        return 1
    runbook = worktree / "docs" / "setup" / "qemu_integrated_gateway.md"
    got = sha256(runbook)
    if got != RUNBOOK_SHA256:
        print(f"refused: the runbook the module reads ({runbook}) is {got}, not {RUNBOOK_SHA256}")
        return 1
    sys.path.insert(0, str(worktree / "src"))
    spec = importlib.util.spec_from_file_location("runbook_itest_helpers_of_the_worktree", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(f"test module imported: {source.name} sha256 {MODULE_SHA256}; runbook sha256 {RUNBOOK_SHA256}")

    mod = bench / "mod"
    mod.mkdir()
    b = module.Bench(mod)
    module.t8_prepare(b)
    module.full_run(b, SMOKE_S3)
    b.set("broker.guest", "2026-10-05T10:00:01.000000000Z 1790000001: Client <unknown> disconnected, not authorised.")
    print("module stubs installed in mod/stubs: " + " ".join(sorted(p.name for p in b.stubs.iterdir())))
    print("stub guest state after t8_prepare (mod/state): " + " ".join(sorted(p.name for p in b.state.iterdir())))

    # The two host files, written by the runbook's own heredocs with HOME inside the bench.
    home = bench / "home"
    (home / "egw-tcg").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home))
    for label, text, name, want in (("tunnel.sh", module.tunnel_heredoc(), "tunnel.sh", TUNNEL_SHA256),
                                    ("itest-helpers.sh", module.helpers_heredoc(), "itest-helpers.sh", HELPER_SHA256)):
        done = subprocess.run(["bash", "-c", text], env=env, stdin=subprocess.DEVNULL)
        path = home / "egw-tcg" / name
        got = sha256(path) if done.returncode == 0 and path.is_file() else "not written"
        print(f"{label}: written by the runbook's own heredoc, sha256 {got} "
              f"({'as recorded' if got == want else 'NOT the recorded ' + want})")
        if got != want:
            return 1
    lines = len((home / "egw-tcg" / "itest-helpers.sh").read_text(encoding="utf-8").splitlines())
    print(f"itest-helpers.sh: {lines} lines")

    facts = {"pre_id": module.T8_PRE_ID, "post_id": module.T8_POST_ID, "containers": module.T8_CONTAINERS,
             "event_dirs": list(module.T8_EVENT_DIRS), "docker_mount": module.T8_DOCKER_MOUNT,
             "post_started": module.T8_POST_STARTED, "started": module.STARTED, "smoke_s3": SMOKE_S3}
    (bench / "mod.facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("module constants used: boot id before " + module.T8_PRE_ID + ", after " + module.T8_POST_ID
          + f"; {len(module.T8_CONTAINERS)} container ids; event directories {', '.join(module.T8_EVENT_DIRS)}; "
          + "mount source " + module.T8_DOCKER_MOUNT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
