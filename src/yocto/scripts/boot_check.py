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

The check list holds two different kinds of entry and they are never mixed in
the reporting, because the totals are quoted downstream as evidence:

    required assertion   a predicate over the command output that must hold
                         for the boot to count; it decides the outcome.
    observation          material recorded for diagnosis (a failed-unit
                         listing, a reachability probe, container facts). It
                         is kept in the log and in the JSON, and it is NEVER
                         counted as something the driver verified.

A boot is reported as `pass` only when the console was reached, every check
ran, every required assertion passed and the guest powered down cleanly. A
check whose completion marker never arrived is recorded as failed and flagged
as timed out, whatever its partial output happens to contain: the driver
cannot tell a slow command from a wedged one, so it never credits either.

Exit status is 0 only under that same rule, so a caller can rely on it. This
driver reports what it observed; accepting or closing a gate is a separate,
human decision. Requires kas and a deployed image; run scripts/build.sh first.
"""

from __future__ import annotations

import json
import os
import re
import select
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, NamedTuple

try:  # POSIX only: a pseudo-terminal is the only way to drive the QEMU console.
    import pty
except ImportError:  # pragma: no cover - guarded so the verdict logic stays importable
    # Booting still requires a POSIX host (Console.__init__ refuses without it),
    # but the reporting and decision code can then be exercised anywhere.
    pty = None

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

#: The two kinds of entry in CHECKS. Only REQUIRED_ASSERTION decides a boot.
REQUIRED_ASSERTION = "required_assertion"
OBSERVATION = "observation"


class Check(NamedTuple):
    """One console command, what it must show, and whether it decides the boot."""

    id: str
    command: str
    predicate: Callable[[str], bool]
    kind: str

    @property
    def required(self) -> bool:
        return self.kind == REQUIRED_ASSERTION


class CommandOutput(NamedTuple):
    """The output of one check and whether the command actually finished.

    `completed` is False when the completion marker never arrived, i.e. the
    command timed out. `text` is then whatever partial output was captured and
    must not be trusted: a half-finished command can easily print the token a
    predicate is looking for before it stalls.
    """

    text: str
    completed: bool


CHECKS: list[Check] = [
    Check(
        "kernel_and_release",
        "uname -a; head -n 3 /etc/os-release",
        lambda out: "aarch64" in out,
        REQUIRED_ASSERTION,
    ),
    Check(
        "systemd_state",
        # --wait blocks until startup finishes. Without it the checks race the
        # boot: the serial autologin hands over a shell before systemd has
        # reached its default target, so the target below reads as still
        # starting. 'echo STATE=' isolates the answer from the command text.
        "echo STATE=$(systemctl is-system-running --wait 2>&1)",
        lambda out: re.search(r"STATE=(running|degraded)", out) is not None,
        REQUIRED_ASSERTION,
    ),
    Check(
        "systemd_targets",
        "systemctl list-units --type=target --no-pager --no-legend; systemctl get-default",
        # Gate G1 asks that systemd reach multi-user. Assert that from the unit
        # list, where an active target is listed with 'active active'. Asking
        # 'systemctl is-active multi-user.target' proved unreliable on this
        # image: it answered 'inactive' while the system was running normally
        # (observed 2026-08-11), so the unit list is the evidence used instead.
        lambda out: re.search(r"multi-user\.target\s+loaded\s+active", out) is not None,
        REQUIRED_ASSERTION,
    ),
    Check(
        "failed_units",
        "systemctl --failed --no-pager --no-legend; echo FAILED_UNITS_END",
        # An OBSERVATION, and honestly labelled as one: the predicate only
        # confirms that the listing ran to its own end marker, so it asserts
        # nothing about the units themselves. A minimal image may legitimately
        # carry a failed unit unrelated to the gate criteria; the log makes any
        # such unit visible rather than hidden, and a human reads it.
        lambda out: "FAILED_UNITS_END" in out,
        OBSERVATION,
    ),
    Check(
        "networking",
        # BusyBox's 'ip' applet has no '-br' (brief) flag: the earlier form
        # printed a usage message and only 'ip route' contributed, so half the
        # command was silently doing nothing. Observed in boot1.log line 562.
        "ip addr; ip route",
        lambda out: re.search(r"10\.0\.2\.\d+", out) is not None,
        REQUIRED_ASSERTION,
    ),
    Check(
        "gateway_reachable",
        "ping -c 3 -W 5 10.0.2.2 || true",
        lambda out: "3 packets transmitted, 3 " in out or " 0% packet loss" in out,
        OBSERVATION,
    ),
    Check(
        "container_runtime",
        "systemctl start docker || true; sleep 5; docker info 2>&1 | head -n 20",
        lambda out: "Server Version" in out,
        REQUIRED_ASSERTION,
    ),
    Check(
        "container_smoke",
        "egw-container-smoke.sh; echo SMOKE_EXIT=$?",
        lambda out: "SMOKE_EXIT=0" in out,
        REQUIRED_ASSERTION,
    ),
    Check(
        "smoke_diagnostics",
        # Recorded unconditionally so a smoke failure arrives with the facts
        # needed to diagnose it, instead of costing another boot. The predicate
        # is True by construction, which is precisely why this is an
        # OBSERVATION and not an assertion.
        #
        # Every command here must be BusyBox-safe: the image ships BusyBox
        # 1.36.1 and no binutils. The previous probe used 'head -c', which this
        # BusyBox rejects ("head: invalid option -- 'c'", observed 2026-08-11),
        # so the interpreter was reported as 'unknown' on every boot. The probe
        # now reads the ELF interpreter out of the binary directly: 'strings'
        # when the applet is compiled in, otherwise 'tr' turning the runs of
        # printable bytes into lines. 'unavailable' is printed only if both
        # routes fail, so a broken probe can no longer masquerade as an answer.
        "INTERP=$(strings /bin/busybox 2>/dev/null | grep -m 1 '^/lib/ld-'); "
        "[ -n \"$INTERP\" ] || "
        "INTERP=$(tr -c '[:print:]' '\\n' < /bin/busybox 2>/dev/null | grep -m 1 '^/lib/ld-'); "
        "echo \"INTERP=${INTERP:-unavailable}\"; "
        "ls -l /lib/ld-linux-aarch64.so.1 /lib/libc.so.6 2>&1 | head -n 4; "
        "docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | head -n 3; "
        "docker run --rm egw-smoke:local /bin/busybox echo BUSYBOX_DIRECT_OK 2>&1 | tail -n 2",
        lambda out: True,
        OBSERVATION,
    ),
]

#: Checks that legitimately take longer than CMD_TIMEOUT_S: importing and
#: running a container image under full ARM64 emulation is not quick.
SLOW_CHECKS = {"container_smoke": 600.0, "container_runtime": 420.0}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_command_output(text: str, index: int) -> str:
    """Return ONLY what check `index` printed, never the echoed command line.

    The terminal echoes what is typed, so a predicate evaluated over the raw
    buffer can match the command text instead of the result. That is not
    hypothetical: the systemd check matched the word 'running' inside its own
    'systemctl is-system-running' invocation and reported a pass while the
    system was still starting (observed 2026-08-11).

    Both markers are sent as split literals, so the echoed line carries the
    quotes ("EGW_CHECK''_BEGIN_3") and only the OUTPUT carries the bare token.
    Slicing between the bare tokens therefore excludes the echo. When the
    markers are missing or out of order the whole buffer is returned, which is
    the honest answer: the caller pairs it with a completion flag and does not
    treat unmarked text as a pass.
    """
    begin, done = BEGIN.format(index), DONE.format(index)
    start = text.rfind(begin)
    end = text.rfind(done)
    if start != -1 and end != -1 and end > start:
        return text[start + len(begin):end]
    return text


class Console:
    """The QEMU serial console, driven over a pseudo-terminal."""

    def __init__(self, log: "open") -> None:
        if pty is None:  # pragma: no cover - POSIX hosts always have it
            raise RuntimeError("booting the guest needs a POSIX host: no pty module here")
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

    def run_check(self, index: int, command: str, timeout: float) -> CommandOutput:
        """Run one check, reporting its output and whether it actually finished.

        The completion marker is the only evidence that the command ran to the
        end, so its arrival is returned to the caller rather than discarded.
        Silently dropping it let a command that timed out be judged on its
        partial output, and a partial output can satisfy a predicate.
        """
        self.buffer = ""
        self.send(f"echo 'EGW_CHECK''_BEGIN_{index}'; {command}; echo 'EGW_CHECK''_DONE_{index}'")
        completed = self.read_until(re.escape(DONE.format(index)), timeout)
        return CommandOutput(extract_command_output(self.buffer, index), completed)

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


def evaluate_check(check: Check, output: CommandOutput, timeout: float) -> dict:
    """Turn one command's output into the record entry for that check.

    A check that never reached its completion marker is recorded as failed and
    as timed out, whatever the predicate makes of the partial text. Both facts
    are kept separately (`predicate_passed` and `timed_out`) so a reader can
    see WHY an entry failed instead of being handed a bare False.
    """
    predicate_passed = bool(check.predicate(output.text))
    entry = {
        "id": check.id,
        "kind": check.kind,
        "required": check.required,
        "command": check.command,
        "completed": output.completed,
        "timed_out": not output.completed,
        "predicate_passed": predicate_passed,
        "passed": bool(output.completed and predicate_passed),
        "output_tail": output.text[-1200:],
    }
    if not output.completed:
        entry["reason"] = (
            f"timed out after {timeout:.0f}s: the completion marker never arrived, so the "
            "output below is partial and the check cannot count as passed"
        )
    elif not predicate_passed:
        entry["reason"] = "the command finished but its output did not satisfy the check"
    return entry


def describe_entry(entry: dict) -> str:
    """One short line about an entry, for the operator watching the run."""
    if entry["timed_out"]:
        return "TIMED OUT (recorded as failed)"
    if entry["kind"] == OBSERVATION:
        return "recorded" if entry["passed"] else "recorded (nothing matched; not a failure)"
    return "pass" if entry["passed"] else "FAIL"


def run_checks(console: "Console", checks: list[Check] = CHECKS) -> list[dict]:
    """Run every check against `console` and return the record entries."""
    entries: list[dict] = []
    for index, check in enumerate(checks):
        print(f"[driver] check {index + 1}/{len(checks)}: {check.id} [{check.kind}]")
        timeout = SLOW_CHECKS.get(check.id, CMD_TIMEOUT_S)
        entry = evaluate_check(check, console.run_check(index, check.command, timeout), timeout)
        entries.append(entry)
        print(f"[driver]   {describe_entry(entry)}")
    return entries


def summarise(record: dict, checks: list[Check] = CHECKS) -> dict:
    """Fill in the counters, the reasons and the outcome; return the record.

    Required assertions and supplementary observations are counted apart on
    purpose. Reporting "9 of 9 checks passed" credited three entries that
    assert nothing (one only confirms its own end marker, one is a
    reachability probe, one is a diagnostic whose predicate is True by
    construction) and so overstated what the boot verified.
    """
    entries = record.get("checks", [])
    required = [e for e in entries if e.get("kind") == REQUIRED_ASSERTION]
    observations = [e for e in entries if e.get("kind") == OBSERVATION]
    expected_required = sum(1 for c in checks if c.required)

    summary = {
        "required_assertions_total": expected_required,
        "required_assertions_run": len(required),
        "required_assertions_passed": sum(1 for e in required if e.get("passed")),
        "supplementary_observations_total": len(checks) - expected_required,
        "supplementary_observations_run": len(observations),
        "supplementary_observations_recorded": sum(1 for e in observations if e.get("completed")),
        "checks_expected": len(checks),
        "checks_run": len(entries),
        "checks_timed_out": [e["id"] for e in entries if e.get("timed_out")],
        "reached_console": bool(record.get("reached_console")),
        "clean_poweroff": bool(record.get("clean_poweroff")),
        "note": (
            "supplementary observations are recorded for diagnosis and are never counted "
            "as verification; only the required assertions and the clean power-down decide "
            "the outcome, and the outcome is a driver report, not a gate decision"
        ),
    }

    reasons: list[str] = []
    if not summary["reached_console"]:
        reasons.append("the console prompt was never reached")
    if summary["checks_run"] != summary["checks_expected"]:
        reasons.append(f"only {summary['checks_run']} of {summary['checks_expected']} checks ran")
    if summary["required_assertions_run"] != summary["required_assertions_total"]:
        # Belt and braces: an entry that lost its kind must never shrink the
        # denominator quietly and turn a partial run into a pass.
        reasons.append(
            f"only {summary['required_assertions_run']} of "
            f"{summary['required_assertions_total']} required assertions were recorded"
        )
    for entry in required:
        if not entry.get("passed"):
            why = "timed out" if entry.get("timed_out") else "output did not satisfy the check"
            reasons.append(f"required assertion '{entry['id']}' failed ({why})")
    if not summary["clean_poweroff"]:
        reasons.append("the guest did not power down cleanly")

    record["summary"] = summary
    record["headline"] = headline(summary)
    record["outcome_reasons"] = reasons
    record["outcome"] = "fail" if reasons else "pass"
    return record


def headline(summary: dict) -> str:
    """The one line quoted downstream; it must not blur the two kinds apart."""
    return (
        f"{summary['required_assertions_passed']} of {summary['required_assertions_total']} "
        "required assertions passed; "
        f"{summary['supplementary_observations_recorded']} of "
        f"{summary['supplementary_observations_total']} supplementary observations recorded; "
        + ("clean power-down confirmed" if summary["clean_poweroff"] else "clean power-down NOT confirmed")
    )


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

            record["checks"] = run_checks(console)

            # An unclean power-down is a fact about the boot, not a detail:
            # a guest that will not shut down has not demonstrated the orderly
            # lifecycle the gate asks for, so it feeds the outcome below.
            console.send("poweroff")
            record["clean_poweroff"] = console.read_until(
                r"(reboot: Power down|Power down|System halted)", POWEROFF_TIMEOUT_S
            )
            if not record["clean_poweroff"]:
                record["poweroff_error"] = (
                    f"no power-down message within {POWEROFF_TIMEOUT_S:.0f}s of 'poweroff'"
                )
        except SystemExit:
            pass
        finally:
            console.close()

    summarise(record)
    record["finished_utc"] = utc_now()
    record["console_log"] = str(log_path)
    result_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"[driver] {record['headline']}")
    for reason in record["outcome_reasons"]:
        print(f"[driver] reason: {reason}")
    print(f"[driver] outcome: {record['outcome']}")
    print(f"[driver] console log : {log_path}")
    print(f"[driver] result      : {result_path}")
    return 0 if record["outcome"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
