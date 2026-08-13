"""Tests for the unattended QEMU boot driver (yocto/scripts/boot_check.py).

The driver produces the gate G1 boot evidence and will be reused for the
campaign boots, so these tests are about whether its VERDICT can be trusted:
that a command which timed out is never credited, that the echoed command line
cannot satisfy a check on its own, that a boot which did not power down
cleanly is not reported as a pass, and that supplementary observations are
never counted as things the driver verified.

No test starts a virtual machine. `FakeConsole` replays canned serial
transcripts through the real `Console.run_check`, so the marker slicing and the
timeout handling under test are the ones that ship.
"""
from __future__ import annotations

import importlib.util
import re
import shlex
import shutil
import subprocess
from collections import deque
from pathlib import Path

# The driver ships inside the Yocto layer rather than in an installed package,
# so it is loaded by path instead of by package name.
MODULE_PATH = Path(__file__).resolve().parents[1] / "yocto" / "scripts" / "boot_check.py"
_SPEC = importlib.util.spec_from_file_location("egw_yocto_boot_check", MODULE_PATH)
boot_check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(boot_check)


# --------------------------------------------------------------------------
# doubles and helpers
# --------------------------------------------------------------------------
class FakeConsole(boot_check.Console):
    """A console that replays canned serial output instead of booting QEMU.

    Only `send` and `read_until` are replaced: that is exactly the boundary the
    pseudo-terminal sits behind, so `run_check` (marker slicing, completion
    flag) is exercised as written.
    """

    def __init__(self, transcripts: list[str]) -> None:
        # Deliberately does NOT call super().__init__: that would start a guest.
        self.transcripts = deque(transcripts)
        self.buffer = ""
        self.sent: list[str] = []

    def send(self, line: str) -> None:
        self.sent.append(line)
        if self.transcripts:
            self.buffer += self.transcripts.popleft()

    def read_until(self, pattern: str, timeout: float) -> bool:
        return re.search(pattern, self.buffer) is not None


def transcript(index: int, command: str, output: str, *, complete: bool = True) -> str:
    """Build the serial output the console shows for one check.

    Mirrors the real session: the terminal echoes the command line with the
    marker literals still split by quotes, and only the command's own output
    carries the bare markers. `complete=False` drops the completion marker,
    which is what a timed-out command looks like.
    """
    echoed = f"EGW# echo 'EGW_CHECK''_BEGIN_{index}'; {command}; echo 'EGW_CHECK''_DONE_{index}'\r\n"
    body = f"EGW_CHECK_BEGIN_{index}\r\n{output}\r\n"
    return echoed + body + (f"EGW_CHECK_DONE_{index}\r\n" if complete else "")


def assertion(identifier: str, command: str, token: str) -> boot_check.Check:
    """A required assertion that passes when `token` appears in the output."""
    return boot_check.Check(
        identifier, command, lambda out, token=token: token in out, boot_check.REQUIRED_ASSERTION
    )


def observation(identifier: str, command: str, token: str) -> boot_check.Check:
    """A supplementary observation, recorded but never counted as verification."""
    return boot_check.Check(
        identifier, command, lambda out, token=token: token in out, boot_check.OBSERVATION
    )


#: Output that satisfies each real check, taken from the 2026-08-11 boot logs.
REAL_OUTPUTS = {
    "kernel_and_release": "Linux qemuarm64 6.6.142-yocto-standard #1 SMP aarch64 GNU/Linux\r\nID=poky",
    "systemd_state": "STATE=running",
    "systemd_targets": "  multi-user.target     loaded active active Multi-User System\r\nmulti-user.target",
    "failed_units": "FAILED_UNITS_END",
    "networking": "default via 10.0.2.2 dev enp0s1  src 10.0.2.15  metric 1024",
    "gateway_reachable": "3 packets transmitted, 3 packets received, 0% packet loss",
    "container_runtime": " Server Version: 25.0.9\r\n Storage Driver: overlay2",
    "container_smoke": "PASS container executed (docker import + run)\r\nSMOKE_EXIT=0",
    "smoke_diagnostics": "INTERP=/lib/ld-linux-aarch64.so.1\r\nBUSYBOX_DIRECT_OK",
}


def passing_transcripts(*, incomplete: set[str] = frozenset()) -> list[str]:
    """A full set of transcripts in which every real check succeeds."""
    return [
        transcript(index, check.command, REAL_OUTPUTS[check.id], complete=check.id not in incomplete)
        for index, check in enumerate(boot_check.CHECKS)
    ]


def build_record(entries: list[dict], *, reached_console: bool = True, clean_poweroff: bool = True) -> dict:
    """The record shape `main` assembles, without booting anything."""
    return {
        "boot": "test-boot",
        "reached_console": reached_console,
        "checks": entries,
        "clean_poweroff": clean_poweroff,
    }


def entry_by_id(record: dict, identifier: str) -> dict:
    return next(entry for entry in record["checks"] if entry["id"] == identifier)


# --------------------------------------------------------------------------
# a command that never finished must never count as a pass
# --------------------------------------------------------------------------
def test_missing_completion_marker_fails_the_check_and_is_flagged_as_timed_out() -> None:
    check = assertion("smoke", "run-the-smoke-test", "SMOKE_EXIT=0")
    console = FakeConsole([transcript(0, check.command, "SMOKE_EXIT=0", complete=False)])

    entries = boot_check.run_checks(console, [check])

    assert entries[0]["passed"] is False, "a check whose marker never arrived cannot pass"
    assert entries[0]["timed_out"] is True, "the timeout must be visible in the record"
    assert entries[0]["completed"] is False
    assert "timed out" in entries[0]["reason"], "the reason must name the timeout, not be a bare False"


def test_partial_output_satisfying_the_predicate_is_still_recorded_as_failed() -> None:
    # container_smoke prints SMOKE_EXIT=0 and could then wedge before the
    # marker; the driver cannot tell that from a command still running, so it
    # must refuse to credit either.
    index = next(i for i, c in enumerate(boot_check.CHECKS) if c.id == "container_smoke")
    check = boot_check.CHECKS[index]
    console = FakeConsole([transcript(0, check.command, REAL_OUTPUTS["container_smoke"], complete=False)])

    entry = boot_check.run_checks(console, [check])[0]

    assert entry["predicate_passed"] is True, "the partial output does satisfy the predicate"
    assert entry["passed"] is False, "but an unfinished command must still be recorded as failed"
    assert entry["timed_out"] is True


def test_a_timed_out_required_assertion_fails_the_whole_boot() -> None:
    console = FakeConsole(passing_transcripts(incomplete={"container_smoke"}))
    record = build_record(boot_check.run_checks(console))

    boot_check.summarise(record)

    assert record["outcome"] == "fail"
    assert record["summary"]["checks_timed_out"] == ["container_smoke"]
    assert any("container_smoke" in reason and "timed out" in reason for reason in record["outcome_reasons"])


def test_a_timed_out_observation_is_not_counted_as_recorded() -> None:
    console = FakeConsole(passing_transcripts(incomplete={"smoke_diagnostics"}))
    record = build_record(boot_check.run_checks(console))

    boot_check.summarise(record)

    summary = record["summary"]
    assert summary["supplementary_observations_recorded"] == 1, "a partial observation was not recorded"
    assert summary["checks_timed_out"] == ["smoke_diagnostics"]
    # An observation asserts nothing, so it does not decide the boot, but the
    # timeout stays visible in the summary above.
    assert record["outcome"] == "pass"


# --------------------------------------------------------------------------
# the echoed command line is not evidence
# --------------------------------------------------------------------------
def test_the_echoed_command_alone_cannot_satisfy_a_predicate() -> None:
    check = assertion("systemd_state", "systemctl is-system-running", "running")
    raw = transcript(0, check.command, "starting")
    assert "running" in raw, "the echoed command must contain the word the predicate looks for"

    entry = boot_check.run_checks(FakeConsole([raw]), [check])[0]

    assert entry["passed"] is False, "the word 'running' came from the echo, not from the output"
    assert entry["completed"] is True, "the command did finish; only the predicate failed"
    assert "running" not in entry["output_tail"], "the echoed line must be sliced away"


def test_extract_command_output_returns_only_the_command_output() -> None:
    raw = transcript(3, "systemctl is-system-running --wait", "STATE=starting")

    sliced = boot_check.extract_command_output(raw, 3)

    assert "STATE=starting" in sliced
    assert "systemctl" not in sliced, "the echoed command line is not part of the output"
    assert "EGW_CHECK_DONE_3" not in sliced


def test_extract_command_output_keeps_the_whole_buffer_when_markers_are_absent() -> None:
    # No slicing is possible, so nothing is hidden; the completion flag is what
    # stops the unmarked text from being read as a pass.
    assert boot_check.extract_command_output("kernel panic", 2) == "kernel panic"


# --------------------------------------------------------------------------
# the power-down is part of the verdict
# --------------------------------------------------------------------------
def test_an_incomplete_power_down_fails_the_boot_despite_every_assertion_passing() -> None:
    console = FakeConsole(passing_transcripts())
    record = build_record(boot_check.run_checks(console), clean_poweroff=False)

    boot_check.summarise(record)

    summary = record["summary"]
    assert summary["required_assertions_passed"] == summary["required_assertions_total"] == 7
    assert record["outcome"] == "fail", "a guest that never powered down cleanly is not a pass"
    assert "did not power down cleanly" in " ".join(record["outcome_reasons"])
    assert "clean power-down NOT confirmed" in record["headline"]


def test_a_boot_that_never_reached_the_console_fails() -> None:
    record = build_record([], reached_console=False, clean_poweroff=False)

    boot_check.summarise(record)

    assert record["outcome"] == "fail"
    assert "the console prompt was never reached" in record["outcome_reasons"]


def test_a_short_run_fails_because_not_every_check_ran() -> None:
    console = FakeConsole(passing_transcripts()[:4])
    entries = boot_check.run_checks(console, boot_check.CHECKS[:4])
    record = build_record(entries)

    boot_check.summarise(record)

    assert record["outcome"] == "fail"
    assert "only 4 of 9 checks ran" in record["outcome_reasons"]
    assert "only 4 of 7 required assertions were recorded" in record["outcome_reasons"]


# --------------------------------------------------------------------------
# assertions and observations are reported apart
# --------------------------------------------------------------------------
def test_required_assertions_and_observations_are_counted_separately() -> None:
    console = FakeConsole(passing_transcripts())
    record = build_record(boot_check.run_checks(console))

    boot_check.summarise(record)

    summary = record["summary"]
    assert summary["required_assertions_total"] == 7
    assert summary["required_assertions_passed"] == 7
    assert summary["supplementary_observations_total"] == 2
    assert summary["supplementary_observations_recorded"] == 2
    assert summary["checks_run"] == summary["checks_expected"] == 9
    assert record["headline"] == (
        "7 of 7 required assertions passed; 2 of 2 supplementary observations recorded; "
        "clean power-down confirmed"
    )
    assert "9 of 9" not in record["headline"], "nine checks were run but only seven verified anything"


def test_every_entry_declares_its_kind_in_the_result() -> None:
    console = FakeConsole(passing_transcripts())
    record = build_record(boot_check.run_checks(console))

    kinds = {entry["id"]: entry["kind"] for entry in record["checks"]}

    assert kinds == {
        "kernel_and_release": boot_check.REQUIRED_ASSERTION,
        "systemd_state": boot_check.REQUIRED_ASSERTION,
        "systemd_targets": boot_check.REQUIRED_ASSERTION,
        "failed_units": boot_check.REQUIRED_ASSERTION,
        "networking": boot_check.REQUIRED_ASSERTION,
        "gateway_reachable": boot_check.OBSERVATION,
        "container_runtime": boot_check.REQUIRED_ASSERTION,
        "container_smoke": boot_check.REQUIRED_ASSERTION,
        "smoke_diagnostics": boot_check.OBSERVATION,
    }
    assert all(entry["required"] == (entry["kind"] == boot_check.REQUIRED_ASSERTION) for entry in record["checks"])


def test_non_gate_diagnostics_remain_declared_as_observations() -> None:
    by_id = {check.id: check for check in boot_check.CHECKS}

    assert by_id["gateway_reachable"].kind == boot_check.OBSERVATION
    # Its predicate is True by construction.
    assert by_id["smoke_diagnostics"].predicate("anything at all") is True
    assert by_id["smoke_diagnostics"].kind == boot_check.OBSERVATION


def test_degraded_systemd_state_fails_the_required_assertion() -> None:
    check = next(c for c in boot_check.CHECKS if c.id == "systemd_state")
    entry = boot_check.run_checks(
        FakeConsole([transcript(0, check.command, "STATE=degraded")]), [check]
    )[0]

    assert check.kind == boot_check.REQUIRED_ASSERTION
    assert entry["completed"] is True
    assert entry["passed"] is False


def test_any_failed_systemd_unit_fails_the_required_assertion() -> None:
    check = next(c for c in boot_check.CHECKS if c.id == "failed_units")
    output = (
        "bad.service loaded failed failed Deliberately broken service\r\n"
        "FAILED_UNITS_END"
    )
    entry = boot_check.run_checks(
        FakeConsole([transcript(0, check.command, output)]), [check]
    )[0]

    assert check.kind == boot_check.REQUIRED_ASSERTION
    assert entry["completed"] is True
    assert entry["passed"] is False


def test_an_observation_whose_output_does_not_match_does_not_fail_the_boot() -> None:
    checks = [assertion("kernel", "uname -a", "aarch64"), observation("ping", "ping -c 3 10.0.2.2", "0% packet loss")]
    console = FakeConsole(
        [
            transcript(0, checks[0].command, "aarch64 GNU/Linux"),
            transcript(1, checks[1].command, "3 packets transmitted, 0 packets received"),
        ]
    )
    record = build_record(boot_check.run_checks(console, checks))

    boot_check.summarise(record, checks)

    assert entry_by_id(record, "ping")["passed"] is False
    assert record["summary"]["supplementary_observations_recorded"] == 1, "it ran, so it was recorded"
    assert record["outcome"] == "pass", "an observation asserts nothing and cannot fail the boot"


def test_the_summary_states_that_observations_are_not_verification() -> None:
    record = build_record([])

    boot_check.summarise(record)

    assert "never counted as verification" in record["summary"]["note"]


# --------------------------------------------------------------------------
# the happy path still passes
# --------------------------------------------------------------------------
def test_a_fully_successful_run_reports_pass() -> None:
    console = FakeConsole(passing_transcripts())
    record = build_record(boot_check.run_checks(console))

    boot_check.summarise(record)

    assert [entry["passed"] for entry in record["checks"]] == [True] * 9
    assert record["outcome_reasons"] == []
    assert record["outcome"] == "pass"
    assert record["summary"]["checks_timed_out"] == []


# --------------------------------------------------------------------------
# the in-guest commands must run on this image's BusyBox
# --------------------------------------------------------------------------
def test_no_check_uses_busybox_incompatible_head_c() -> None:
    # BusyBox 1.36.1 in egw-image rejects 'head -c' ("invalid option -- 'c'",
    # observed 2026-08-11), which silenced the interpreter probe entirely.
    for check in boot_check.CHECKS:
        assert "head -c" not in check.command, f"{check.id} uses an option this BusyBox rejects"


def test_the_interpreter_probe_reads_the_binary_and_reports_honestly() -> None:
    command = next(c.command for c in boot_check.CHECKS if c.id == "smoke_diagnostics")

    assert "strings /bin/busybox" in command, "the probe must read the interpreter out of the binary"
    assert "tr -c '[:print:]'" in command, "with a BusyBox-safe fallback when 'strings' is absent"
    assert "unavailable" in command, "an unanswerable probe must say so rather than invent a value"
    assert "INTERP=unknown" not in command


def _bash_visible_path(path: Path) -> str:
    """Translate a Windows path for WSL's bash; POSIX paths pass through."""
    raw = path.resolve().as_posix()
    if re.match(r"^[A-Za-z]:/", raw):
        return f"/mnt/{raw[0].lower()}{raw[2:]}"
    return raw


def test_run_qemu_pipeline_propagates_kas_failure_through_tee(tmp_path) -> None:
    """Exercise the real pipeline function with a failing fake kas command."""
    bash = shutil.which("bash")
    if bash is None:
        import pytest

        pytest.skip("bash is required to exercise run-qemu.sh")
    script = MODULE_PATH.with_name("run-qemu.sh")
    script_text = script.read_text(encoding="utf-8")
    assert script_text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in script_text

    log_path = tmp_path / "qemu-pipeline.log"
    shell_program = "\n".join(
        [
            f"source {shlex.quote(_bash_visible_path(script))}",
            "kas() { printf 'simulated kas failure\\n'; return 23; }",
            "KAS_FILE=ignored.yml",
            f"LOG_FILE={shlex.quote(_bash_visible_path(log_path))}",
            "set +e",
            "run_qemu_logged",
        ]
    )
    proc = subprocess.run(
        [bash, "-c", shell_program],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 23
    assert "simulated kas failure" in proc.stdout
    assert log_path.read_text(encoding="utf-8") == "simulated kas failure\n"
