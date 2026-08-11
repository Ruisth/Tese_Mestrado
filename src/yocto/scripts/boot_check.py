#!/usr/bin/env python3
"""Boot egw-image under QEMU and run the gate G1 in-guest checks unattended.

FUNCTIONAL VALIDATION ONLY. QEMU results support build, boot, systemd,
networking and OCI-runtime claims. They never support a performance claim
(plan section 5.1), so nothing here is timed for reporting.

Gate G1 requires the image to boot twice, reach systemd multi-user, bring
networking up and execute one container. Doing that by hand leaves evidence
nobody can reproduce, so this driver attaches to the serial console, logs in,
runs a fixed list of checks, records the full session and decides pass or fail
from the output.

    python3 scripts/boot_check.py boot1
    python3 scripts/boot_check.py boot2

Each run writes, under EGW_LOG_DIR (default ~/yocto/logs):

    <name>.log          the complete serial console session
    <name>.result.json  the per-check verdicts and the overall outcome

Exit status is 0 only when every required check passed, so a caller can rely
on it. Requires kas and a deployed image; run scripts/build.sh first.
"""

from __future__ import annotations

import json
import os
import pty
import re
import select
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
YOCTO_DIR = SCRIPT_DIR.parent
KAS_FILE = "kas/egw-qemuarm64.yml"
LOG_DIR = Path(os.environ.get("EGW_LOG_DIR", Path.home() / "yocto" / "logs"))

BOOT_TIMEOUT_S = float(os.environ.get("EGW_BOOT_TIMEOUT_S", 900))
CMD_TIMEOUT_S = float(os.environ.get("EGW_CMD_TIMEOUT_S", 240))
POWEROFF_TIMEOUT_S = 120.0

#: Marker echoed after each command so completion can be detected without
#: guessing at the shell prompt, which the image is free to restyle.
DONE = "EGW_CHECK_DONE_{}"
BEGIN = "EGW_CHECK_BEGIN_{}"

#: (identifier, command, predicate over the captured output, required)
CHECKS: list[tuple[str, str, "callable[[str], bool]", bool]] = [
    (
        "kernel_and_release",
        "uname -a; head -n 3 /etc/os-release",
        lambda out: "aarch64" in out,
        True,
    ),
    (
        "systemd_state",
        # --wait blocks until startup finishes. Without it the checks race the
        # boot: the serial autologin hands over a shell before systemd has
        # reached its default target, so the target below reads as still
        # starting. 'echo STATE=' isolates the answer from the command text.
        "echo STATE=$(systemctl is-system-running --wait 2>&1)",
        lambda out: re.search(r"STATE=(running|degraded)", out) is not None,
        True,
    ),
    (
        "systemd_targets",
        "systemctl list-units --type=target --no-pager --no-legend; systemctl get-default",
        # Gate G1 asks that systemd reach multi-user. Assert that from the unit
        # list, where an active target is listed with 'active active'. Asking
        # 'systemctl is-active multi-user.target' proved unreliable on this
        # image: it answered 'inactive' while the system was running normally
        # (observed 2026-08-11), so the unit list is the evidence used instead.
        lambda out: re.search(r"multi-user\.target\s+loaded\s+active", out) is not None,
        True,
    ),
    (
        "failed_units",
        "systemctl --failed --no-pager --no-legend; echo FAILED_UNITS_END",
        # Recorded for the evidence log. Not required: a minimal image may
        # legitimately carry a failed unit unrelated to the gate criteria, and
        # the log makes any such unit visible rather than hidden.
        lambda out: "FAILED_UNITS_END" in out,
        False,
    ),
    (
        "networking",
        "ip -br addr; ip route",
        lambda out: re.search(r"10\.0\.2\.\d+", out) is not None,
        True,
    ),
    (
        "gateway_reachable",
        "ping -c 3 -W 5 10.0.2.2 || true",
        lambda out: "3 packets transmitted, 3 " in out or " 0% packet loss" in out,
        False,
    ),
    (
        "container_runtime",
        "systemctl start docker || true; sleep 5; docker info 2>&1 | head -n 20",
        lambda out: "Server Version" in out,
        True,
    ),
    (
        "container_smoke",
        "egw-container-smoke.sh; echo SMOKE_EXIT=$?",
        lambda out: "SMOKE_EXIT=0" in out,
        True,
    ),
    (
        "smoke_diagnostics",
        # Recorded unconditionally so a smoke failure arrives with the facts
        # needed to diagnose it, instead of costing another boot.
        "echo INTERP=$(head -c 200 /bin/busybox | strings 2>/dev/null | grep -m1 ld-linux || echo unknown); "
        "ls -l /lib/ld-linux-aarch64.so.1 /lib/libc.so.6 2>&1 | head -n 4; "
        "docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | head -n 3; "
        "docker run --rm egw-smoke:local /bin/busybox echo BUSYBOX_DIRECT_OK 2>&1 | tail -n 2",
        lambda out: True,
        False,
    ),
]

#: Checks that legitimately take longer than CMD_TIMEOUT_S: importing and
#: running a container image under full ARM64 emulation is not quick.
SLOW_CHECKS = {"container_smoke": 600.0, "container_runtime": 420.0}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Console:
    """The QEMU serial console, driven over a pseudo-terminal."""

    def __init__(self, log: "open") -> None:
        self.log = log
        self.buffer = ""
        primary, secondary = pty.openpty()
        self.primary = primary
        command = f"kas shell {KAS_FILE} -c {shlex.quote('runqemu qemuarm64 nographic slirp')}"
        env = dict(os.environ, KAS_WORK_DIR=str(YOCTO_DIR), LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8")
        self.proc = subprocess.Popen(
            ["/bin/sh", "-c", command],
            cwd=YOCTO_DIR,
            stdin=secondary,
            stdout=secondary,
            stderr=secondary,
            env=env,
            preexec_fn=os.setsid,
        )
        os.close(secondary)

    def read_until(self, pattern: str, timeout: float) -> bool:
        """Consume output until `pattern` matches, or the timeout expires."""
        deadline = time.time() + timeout
        regex = re.compile(pattern)
        while time.time() < deadline:
            if regex.search(self.buffer):
                return True
            ready, _, _ = select.select([self.primary], [], [], 1.0)
            if not ready:
                if self.proc.poll() is not None:
                    return bool(regex.search(self.buffer))
                continue
            try:
                chunk = os.read(self.primary, 65536)
            except OSError:
                return bool(regex.search(self.buffer))
            if not chunk:
                return bool(regex.search(self.buffer))
            text = chunk.decode("utf-8", errors="replace")
            self.buffer += text
            self.log.write(text)
            self.log.flush()
        return bool(regex.search(self.buffer))

    def send(self, line: str) -> None:
        os.write(self.primary, (line + "\n").encode())
        self.log.write(f"\n[driver] >>> {line}\n")
        self.log.flush()

    def run_check(self, index: int, command: str, timeout: float) -> str:
        """Run one check and return ONLY its output, never the echoed command.

        The terminal echoes what is typed, so a predicate evaluated over the
        raw buffer can match the command text instead of the result. That is
        not hypothetical: the systemd check matched the word 'running' inside
        its own 'systemctl is-system-running' invocation and reported a pass
        while the system was still starting (observed 2026-08-11).

        Both markers are written as split literals, so the echoed line carries
        the quotes and the OUTPUT carries the bare token. Slicing between the
        bare tokens therefore excludes the echo.
        """
        begin, done = BEGIN.format(index), DONE.format(index)
        self.buffer = ""
        self.send(f"echo 'EGW_CHECK''_BEGIN_{index}'; {command}; echo 'EGW_CHECK''_DONE_{index}'")
        self.read_until(re.escape(done), timeout)
        text = self.buffer
        start = text.rfind(begin)
        end = text.rfind(done)
        if start != -1 and end != -1 and end > start:
            return text[start + len(begin):end]
        return text

    def close(self) -> None:
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            os.close(self.primary)
        except OSError:
            pass


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else f"boot-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    images = YOCTO_DIR / "build" / "tmp" / "deploy" / "images" / "qemuarm64"
    if not images.is_dir():
        print("ERROR: no deployed image found - run scripts/build.sh first.", file=sys.stderr)
        return 2

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    result_path = LOG_DIR / f"{name}.result.json"

    record: dict = {
        "boot": name,
        "started_utc": utc_now(),
        "purpose": "gate G1 functional validation; never a performance measurement",
        "checks": [],
    }

    print(f"[driver] booting egw-image; console -> {log_path}")
    with open(log_path, "w", encoding="utf-8") as log:
        console = Console(log)
        try:
            booted = console.read_until(r"(login:|~#|# $)", BOOT_TIMEOUT_S)
            record["reached_console"] = booted
            if not booted:
                record["error"] = f"no console prompt within {BOOT_TIMEOUT_S:.0f}s"
                raise SystemExit(1)

            if re.search(r"login:", console.buffer):
                console.send("root")
                console.read_until(r"(~#|# $|Password:)", 60)
                if re.search(r"Password:", console.buffer):
                    record["error"] = "the image asked for a password; debug-tweaks not in effect"
                    raise SystemExit(1)

            # Kernel messages go to this same console. Container operations
            # produce a burst of them (bridge, veth, netfilter), which drowns
            # the command output the checks are matched against. Raise the
            # console log level so only genuine emergencies interrupt.
            console.send("dmesg -n 1")
            # A narrow terminal wraps long command lines, which corrupts both
            # the echoed command and the completion marker.
            console.send("stty cols 1000 rows 1000 2>/dev/null || true")
            console.send("export PS1='EGW# '")
            console.read_until(r"EGW# ", 30)

            for index, (identifier, command, predicate, required) in enumerate(CHECKS):
                print(f"[driver] check {index + 1}/{len(CHECKS)}: {identifier}")
                timeout = SLOW_CHECKS.get(identifier, CMD_TIMEOUT_S)
                out = console.run_check(index, command, timeout)
                passed = bool(predicate(out))
                record["checks"].append(
                    {
                        "id": identifier,
                        "command": command,
                        "required": required,
                        "passed": passed,
                        "output_tail": out[-1200:],
                    }
                )
                print(f"[driver]   {'pass' if passed else 'FAIL'}")

            console.send("poweroff")
            console.read_until(r"(reboot: Power down|Power down|System halted)", POWEROFF_TIMEOUT_S)
            record["clean_poweroff"] = bool(
                re.search(r"(Power down|System halted)", console.buffer)
            )
        except SystemExit:
            pass
        finally:
            console.close()

    required_ok = all(c["passed"] for c in record["checks"] if c["required"])
    all_present = len(record["checks"]) == len(CHECKS)
    record["outcome"] = "pass" if (required_ok and all_present and record.get("reached_console")) else "fail"
    record["finished_utc"] = utc_now()
    record["console_log"] = str(log_path)
    result_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"[driver] outcome: {record['outcome']}")
    print(f"[driver] console log : {log_path}")
    print(f"[driver] result      : {result_path}")
    return 0 if record["outcome"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
