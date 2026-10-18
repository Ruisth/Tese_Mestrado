"""Cases for tools/compare/guest_meminfo_sampler.sh, the whole-guest memory sampler
of the comparison measurement.

The script under test is the repository file itself, run unmodified under every POSIX
shell the host has (sh, dash, bash) and, when the Yocto build's image rootfs and its
qemu-aarch64 are present (or ``EGW_TEST_BUSYBOX_DIR`` already names a wrapper
directory), under the gateway image's own busybox through the wrappers that
``tools/test/make-busybox-wrappers.sh`` builds, with PATH holding nothing else. The
runs are real: they read this host's /proc/meminfo for a few seconds, so the cases
check the file's shape and arithmetic (header once, one complete line per sample,
``mem_used_kb = mem_total_kb - mem_available_kb``, the closing ``# end`` line, a clean
exit 0 on SIGTERM), never a memory figure. The refusal of an unreadable /proc/meminfo
is exercised by hiding it under a user and mount namespace when ``unshare`` allows that
on this host; otherwise that one sub-case is skipped and says so. Nothing here says
anything about a guest.
"""
from __future__ import annotations

import datetime
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

if sys.platform == "win32" or shutil.which("bash") is None:
    pytest.skip("the sampler's cases need a POSIX host with bash", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "compare" / "guest_meminfo_sampler.sh"
WRAPPERS = REPO_ROOT / "tools" / "test" / "make-busybox-wrappers.sh"
if not SCRIPT.is_file():
    pytest.skip(f"{SCRIPT} is not in this tree", allow_module_level=True)

HEADER = "ts_utc,epoch_s,mem_total_kb,mem_available_kb,mem_used_kb"
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
END_RE = re.compile(r"^# end epoch_s=(\d+) samples=(\d+)$")

# The image's busybox: a ready wrapper directory, else the integrated build's rootfs and
# qemu-aarch64 at the paths make-busybox-wrappers.sh documents (EGW_YOCTO_BUILD overrides).
BUSYBOX_DIR_GIVEN = os.environ.get("EGW_TEST_BUSYBOX_DIR", "")
YOCTO_BUILD = Path(os.environ.get("EGW_YOCTO_BUILD", "~/yocto/egw/src/yocto/build-integrated")).expanduser()
IMAGE_ROOTFS = YOCTO_BUILD / "tmp/work/qemuarm64-poky-linux/egw-gateway-image/1.0/rootfs"
QEMU_AARCH64 = YOCTO_BUILD / "tmp/sysroots-components/x86_64/qemu-native/usr/bin/qemu-aarch64"

SHELLS = [
    pytest.param("sh", marks=pytest.mark.skipif(shutil.which("sh") is None, reason="sh is not installed")),
    pytest.param("dash", marks=pytest.mark.skipif(shutil.which("dash") is None, reason="dash is not installed")),
    pytest.param("bash", marks=pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")),
    pytest.param("busybox"),
]

UNSHARE = shutil.which("unshare")


def unshare_can_hide_meminfo() -> bool:
    """True when a user+mount namespace of this user can bind /dev/null over /proc/meminfo."""
    if UNSHARE is None:
        return False
    probe = subprocess.run(
        [UNSHARE, "-Urm", "/bin/sh", "-c", "mount --bind /dev/null /proc/meminfo && [ ! -s /proc/meminfo ]"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
    )
    return probe.returncode == 0


@pytest.fixture(scope="session")
def busybox_dir(tmp_path_factory: pytest.TempPathFactory) -> tuple[str | None, str]:
    """(wrapper directory, reason when None): the given one, or one built from the image."""
    if BUSYBOX_DIR_GIVEN:
        if os.access(os.path.join(BUSYBOX_DIR_GIVEN, "sh"), os.X_OK):
            return BUSYBOX_DIR_GIVEN, ""
        return None, f"EGW_TEST_BUSYBOX_DIR={BUSYBOX_DIR_GIVEN} has no executable sh"
    if not WRAPPERS.is_file():
        return None, f"{WRAPPERS} is not in this tree"
    if not (IMAGE_ROOTFS / "usr/bin/busybox.nosuid").is_file():
        return None, f"the image's busybox is not at {IMAGE_ROOTFS} (EGW_YOCTO_BUILD, or set EGW_TEST_BUSYBOX_DIR)"
    if not os.access(QEMU_AARCH64, os.X_OK):
        return None, f"no executable qemu-aarch64 at {QEMU_AARCH64}"
    out = tmp_path_factory.mktemp("egw-bb")
    build = subprocess.run(
        ["sh", str(WRAPPERS), str(IMAGE_ROOTFS), str(QEMU_AARCH64), str(out)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
    )
    if build.returncode != 0 or not os.access(out / "sh", os.X_OK):
        return None, f"make-busybox-wrappers.sh failed (rc {build.returncode}): {build.stderr.strip()[-300:]}"
    return str(out), ""


def shell_command(shell: str, busybox: tuple[str | None, str]) -> tuple[list[str], dict[str, str]]:
    """The command prefix and the environment that run the script under a shell."""
    if shell == "busybox":
        directory, reason = busybox
        if directory is None:
            pytest.skip(f"busybox wrappers unavailable: {reason}")
        return [os.path.join(directory, "sh")], {"PATH": directory, "HOME": "/tmp"}
    return [shell], dict(os.environ)


def run_sampler(shell: str, busybox: tuple[str | None, str], args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
    cmd, env = shell_command(shell, busybox)
    return subprocess.run(cmd + [str(SCRIPT)] + args, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout)


def parse(path: Path) -> tuple[list[str], list[list[str]], list[str]]:
    """(header lines, data rows split on commas, comment lines) of a sampler file."""
    headers: list[str] = []
    rows: list[list[str]] = []
    comments: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            comments.append(line)
        elif line == HEADER:
            headers.append(line)
        else:
            rows.append(line.split(","))
    return headers, rows, comments


def check_rows(rows: list[list[str]]) -> None:
    now = time.time()
    for row in rows:
        assert len(row) == 5, row
        ts, epoch, total, avail, used = row
        assert TS_RE.match(ts), row
        for cell in (epoch, total, avail, used):
            assert cell.isdigit(), row
        assert int(used) == int(total) - int(avail), row
        assert 0 <= int(avail) <= int(total), row
        assert abs(int(epoch) - now) < 3600, row
        stamped = datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert stamped == ts, f"ts_utc is not the UTC rendering of epoch_s: {row}"


@pytest.mark.parametrize("shell", SHELLS)
def test_duration_run_writes_header_consistent_lines_and_end_line(shell: str, busybox_dir, tmp_path: Path) -> None:
    out = tmp_path / "meminfo.csv"
    proc = run_sampler(shell, busybox_dir, [str(out), "--duration", "3", "--interval", "1"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == HEADER
    headers, rows, comments = parse(out)
    assert headers == [HEADER]
    assert len(rows) >= 2, lines
    check_rows(rows)
    assert len(comments) == 1 and lines[-1] == comments[0], lines
    end = END_RE.match(comments[0])
    assert end, comments[0]
    assert int(end.group(2)) == len(rows)
    assert int(end.group(1)) >= int(rows[-1][1])


@pytest.mark.parametrize("shell", SHELLS)
def test_sigterm_ends_a_duration_0_run_cleanly(shell: str, busybox_dir, tmp_path: Path) -> None:
    out = tmp_path / "meminfo.csv"
    cmd, env = shell_command(shell, busybox_dir)
    proc = subprocess.Popen(cmd + [str(SCRIPT), str(out)], env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(2.0)
        proc.send_signal(signal.SIGTERM)
        _stdout, stderr = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, stderr
    headers, rows, comments = parse(out)
    assert headers == [HEADER]
    assert len(rows) >= 1
    check_rows(rows)
    assert len(comments) == 1
    end = END_RE.match(comments[0])
    assert end and int(end.group(2)) == len(rows), comments
    assert out.read_text(encoding="utf-8").endswith(comments[0] + "\n")


def test_header_written_once_across_two_runs_on_one_file(busybox_dir, tmp_path: Path) -> None:
    out = tmp_path / "meminfo.csv"
    for _ in range(2):
        proc = run_sampler("sh", busybox_dir, [str(out), "--duration", "1"])
        assert proc.returncode == 0, proc.stderr
    headers, rows, comments = parse(out)
    assert headers == [HEADER]
    assert len(rows) >= 2
    assert len(comments) == 2 and all(END_RE.match(c) for c in comments)
    assert out.read_text(encoding="utf-8").splitlines()[0] == HEADER


@pytest.mark.parametrize("shell", SHELLS)
def test_refusals_exit_2_and_write_nothing(shell: str, busybox_dir, tmp_path: Path) -> None:
    out = tmp_path / "meminfo.csv"
    refused = [
        [],
        [str(out), "--interval", "1.5"],
        [str(out), "--interval", "x"],
        [str(out), "--interval", "0"],
        [str(out), "--duration", "abc"],
        [str(out), "--duration", "-1"],
        [str(out), "--interval"],
        [str(out), "--bogus"],
    ]
    for args in refused:
        proc = run_sampler(shell, busybox_dir, args)
        assert proc.returncode == 2, (args, proc.stderr)
        assert proc.stdout == ""
        assert "usage:" in proc.stderr, (args, proc.stderr)
    assert not out.exists()

    if not unshare_can_hide_meminfo():
        pytest.skip("unshare -Urm cannot bind /dev/null over /proc/meminfo on this host; the refusal of an "
                    "unreadable /proc/meminfo is not exercised")
    cmd, env = shell_command(shell, busybox_dir)
    inner = cmd + [str(SCRIPT), str(out), "--duration", "1"]
    if shell == "busybox":
        inner = [shutil.which("env") or "/usr/bin/env", "-i", f"PATH={env['PATH']}", f"HOME={env['HOME']}"] + inner
    proc = subprocess.run(
        [UNSHARE, "-Urm", "/bin/sh", "-c", 'mount --bind /dev/null /proc/meminfo && exec "$0" "$@"', *inner],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 2, proc.stderr
    assert "/proc/meminfo" in proc.stderr
    assert not out.exists()
