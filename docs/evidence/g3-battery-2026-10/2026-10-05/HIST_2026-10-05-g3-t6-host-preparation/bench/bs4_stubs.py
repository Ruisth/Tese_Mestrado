#!/usr/bin/env python3
"""Stream BENCH of the S4 preparation (2026-10-05): the stubs of the repository's own
test module, put into one bench of the S4 operator script.

Adapted from S3b's bench/bs3b_stubs.py. The test module
src/tests/test_runbook_itest_helpers.py of the read-only worktree <S>/t6m (the merged
tree 14f89c4; its sha256 is asserted first) holds stub commands written for the
runbook's own lines (STUB_SSH, STUB_CURL, STUB_PYTHON, STUB_SCP, STUB_SS, STUB_SLEEP,
STUB_TIMEOUT, STUB_EVENTS_CAPTURE, STUB_FETCH_SUT_LOG), a Bench class that installs them
and capture_text, the configuration identity a realistic guest answers. This script
IMPORTS that module (the merged egw_experiments from the bench's read-only source copy
first on sys.path) and uses those objects as they are:

  <bench>/mod/stubs/   the module's stubs, as its Bench class installs them
  <bench>/mod/state/   the stub guest's state (EGW_STUB_STATE)
  <bench>/mod/clone/   the module's stub clone: its STUB_EVENTS_CAPTURE and
                       STUB_FETCH_SUT_LOG, which bs4_setup.sh puts into the bench's
                       repository copy in place of events_capture.sh and
                       proof_fetch_sut_log.sh

and it writes the two host files with the runbook's own heredocs (the module's
tunnel_heredoc and helpers_heredoc, read from the worktree's runbook, the same bytes as
the blob), run with HOME inside the bench:

  <bench>/home/egw-tcg/tunnel.sh, <bench>/home/egw-tcg/itest-helpers.sh

What is added to the module's state for test 6 (S4), each the shape the module's own
test 6 cases give it:
  - identity_capture: capture_text(), what config_identity's remote script prints;
  - remote_events.jsonl: the guest's event log of controller_restart-r04 (the post-drain
    copy the harness's --post-drain-fetch-cmd reads through STUB_SCP);
  - broker.guest, controller.guest, docker-events.guest: what the bounded SUT reads
    answer (STUB_FETCH_SUT_LOG), the docker-events capture holding the die and the start
    of egw-controller-1.

Nothing of the worktree is written: PYTHONDONTWRITEBYTECODE=1 is required.
Usage (WSL, the execution venv's python): bs4_stubs.py <worktree> <source copy> <bench>
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

MODULE_SHA256 = "b63ef7d88ae22e623bf381ef0dc3e6fbfbf050d966d5b0e09cc961ee169d83be"
RUNBOOK_SHA256 = "317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f"
HELPER_SHA256 = "e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb"
TUNNEL_SHA256 = "38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1"
RID = "controller_restart-r04"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    worktree, source, bench = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        print("refused: PYTHONDONTWRITEBYTECODE=1 is required (nothing of the worktree is written)")
        return 2
    sys.dont_write_bytecode = True
    if not str(bench).startswith("/tmp/g3-s4-bench/") or not bench.is_dir():
        print(f"refused: {bench} is not a bench directory under /tmp/g3-s4-bench/")
        return 2
    module_file = worktree / "src" / "tests" / "test_runbook_itest_helpers.py"
    got = sha256(module_file)
    if got != MODULE_SHA256:
        print(f"refused: the test module {module_file} is {got}, not {MODULE_SHA256}")
        return 1
    runbook = worktree / "docs" / "setup" / "qemu_integrated_gateway.md"
    got = sha256(runbook)
    if got != RUNBOOK_SHA256:
        print(f"refused: the runbook the module reads ({runbook}) is {got}, not {RUNBOOK_SHA256}")
        return 1
    sys.path.insert(0, str(source / "src"))
    spec = importlib.util.spec_from_file_location("runbook_itest_helpers_of_the_worktree", module_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print(f"test module imported: {module_file.name} sha256 {MODULE_SHA256}; runbook sha256 {RUNBOOK_SHA256}")

    mod = bench / "mod"
    mod.mkdir()
    b = module.Bench(mod)
    b.set("identity_capture", module.capture_text().rstrip("\n"))
    events = [{"run_id": RID, "message_id": f"bench-msg-{i}", "outcome": "accepted", "attempts": 1, "error": None}
              for i in range(3)]
    b.jsonl("remote_events.jsonl", events)
    b.set("broker.guest", "2026-10-05T20:00:01.000000000Z 1790000001: bench broker line (stand-in)")
    b.set("controller.guest", "2026-10-05T20:00:01.000000000Z bench controller line (stand-in)")
    b.set("docker-events.guest",
          '{"Action":"die","Actor":{"Attributes":{"name":"egw-controller-1"}},"timeNano":1790000300000000000}\n'
          '{"Action":"start","Actor":{"Attributes":{"name":"egw-controller-1"}},"timeNano":1790000306000000000}')
    print("module stubs installed in mod/stubs: " + " ".join(sorted(p.name for p in b.stubs.iterdir())))
    print("stub guest state (mod/state): " + " ".join(sorted(p.name for p in b.state.iterdir())))
    print("module stub clone (mod/clone/tools/session): "
          + " ".join(sorted(p.name for p in (b.clone / "tools" / "session").iterdir())))

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
    (bench / "mod.facts.json").write_text(json.dumps({"identity_capture": module.capture_text(),
                                                      "six_services": module.SIX_SERVICES}, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
