"""Local, human-readable export of every test attempt (work order of 2026-09-19, 2.B).

An *attempt* is captured on the WSL Linux filesystem, in its own directory under
an attempts root, while it runs::

    <attempts-root>/<run_id>/
        attempt.json        what ran, its identities and its declared results
        commands.jsonl      one line per command: sanitised argv, times, exit code
        sources.json        artefacts written elsewhere (harness raw capsule,
                            simulator output and its sibling files)
        console/            stdout and stderr of every command
        environment/  tests/  analysis/
        export/receipt.json written after an export; never inside a package

It is then exported to a Windows folder (``output_test``), at completion **and on
failure**, as one package per attempt::

    <dest-root>/runs/<YYYY-MM-DD>/<run_id>/
        SUMMARY.md  export_manifest.json  attempt.json  commands.jsonl
        console/  environment/  tests/  analysis/
        raw/<capsule>/        the harness capsule, byte for byte, own seal kept
        simulator/<run>/      the simulator output, byte for byte, and siblings
        SHA256SUMS            every file of the package except itself
    <dest-root>/incomplete/<run_id>/   an export that has not been verified yet
    <dest-root>/INDEX.md  LATEST_SUMMARY.md  README.md

Rules the code keeps:

* Bytes are copied, never rewritten; every destination file is re-read and its
  SHA-256 compared with the source's. A package is finalised (moved from
  ``incomplete/`` to ``runs/``) only after every copied file verified and the
  package's own ``SHA256SUMS`` verified.
* An earlier package is never replaced. A second export of the same attempt is
  a no-op when the finalised package still verifies, and an error otherwise.
* The seal of a copied raw capsule is copied as it is. The outer ``SHA256SUMS``
  shows copy integrity only; it says nothing about a run's completeness.
* A file that contains a secret value (from the given env file) or a private
  key is not copied: it is listed as excluded, and a separately named,
  redacted derivative (``*.sanitized``) is written instead when it is text.
* Instrumentation validity, system outcome and copy verification are three
  separate fields. An export that fails never makes a failed test pass, and an
  export that succeeds never makes it pass either.
* Missing artefacts are listed as missing; nothing is fabricated.

The command line is ``python -m egw_experiments.local_export <command>``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .checksums import sha256_file, verify_sha256sums, write_sha256sums

TOOL_VERSION = "1"
EMULATED_LABEL = "ARM64 EMULATED (QEMU/TCG)"
PURPOSES = ("engineering", "pilot", "official")
VALIDITY_VALUES = ("valid", "invalid", "not-applicable", "unknown")
OUTCOME_VALUES = ("pass", "fail", "inconclusive", "not-run", "interrupted", "unknown")
STATUS_VALUES = ("running", "finished", "failed", "interrupted")
ATTEMPT_DIRS = ("console", "environment", "tests", "analysis")
SOURCE_KINDS = ("raw", "simulator", "other")
_SCAN_LIMIT = 64 * 1024 * 1024
_RUN_ID = re.compile(r"^(\d{8}T\d{6}Z)_([A-Za-z0-9-]+(?:_[A-Za-z0-9-]+)*)_attempt(\d{2,})$")
_HIST_ID = re.compile(r"^HIST_[A-Za-z0-9._-]+$")
_PRIVATE_KEY = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_SECRET_NAME = re.compile(r"(PASS|SECRET|TOKEN|KEY|CREDENTIAL)", re.IGNORECASE)


class ExportError(Exception):
    """An export that could not be completed; the partial package stays visible."""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _stamp(now: _dt.datetime | None = None) -> str:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def scenario_slug(scenario: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9-]+", "-", scenario.strip()).strip("-").lower()
    if not slug:
        raise ValueError(f"scenario {scenario!r} has no usable characters")
    return slug


def run_date(run_id: str, attempt: dict | None = None) -> str:
    """The package's date folder, from the run id (or a historical attempt's date)."""
    m = _RUN_ID.match(run_id)
    if m:
        s = m.group(1)
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if attempt and attempt.get("date"):
        return str(attempt["date"])
    raise ValueError(f"cannot derive a date from run id {run_id!r}")


def load_secrets(env_file: str | Path | None) -> dict[str, bytes]:
    """Values of secret-looking variables in an env file: NAME -> value bytes.

    The values are only ever used to search for them; they are never printed
    or written anywhere.
    """
    secrets: dict[str, bytes] = {}
    if not env_file:
        return secrets
    for raw in Path(env_file).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if _SECRET_NAME.search(name) and len(value) >= 4:
            secrets[name] = value.encode("utf-8")
    return secrets


def redact_text(text: str, secrets: dict[str, bytes]) -> str:
    for name, value in secrets.items():
        text = text.replace(value.decode("utf-8", "replace"), f"[REDACTED:{name}]")
    return text


# --------------------------------------------------------------------------
# Attempts (the WSL side)
# --------------------------------------------------------------------------


def _existing_numbers(slug: str, roots: Iterable[Path]) -> list[int]:
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob(f"*_{slug}_attempt*"):
            m = _RUN_ID.match(p.name)
            if m and m.group(2) == slug:
                found.append(int(m.group(3)))
    return found


def new_attempt(
    attempts_root: str | Path,
    scenario: str,
    purpose: str,
    *,
    dest_root: str | Path | None = None,
    seed: int | None = None,
    emulated: bool = True,
    now: _dt.datetime | None = None,
    fields: dict | None = None,
) -> Path:
    """Create a new attempt directory with a unique, Windows-safe run id."""
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {PURPOSES}")
    attempts_root = Path(attempts_root)
    slug = scenario_slug(scenario)
    roots = [attempts_root]
    if dest_root:
        roots += [Path(dest_root) / "runs", Path(dest_root) / "incomplete"]
    number = max(_existing_numbers(slug, roots), default=0) + 1
    run_id = f"{_stamp(now)}_{slug}_attempt{number:02d}"
    attempt_dir = attempts_root / run_id
    attempt_dir.mkdir(parents=True, exist_ok=False)
    for d in ATTEMPT_DIRS:
        (attempt_dir / d).mkdir()
    (attempt_dir / "commands.jsonl").touch()
    data = {
        "run_id": run_id,
        "scenario": scenario,
        "purpose": purpose,
        "emulated": emulated,
        "created_utc": utc_now(),
        "started_utc": None,
        "ended_utc": None,
        "status": "running",
        "pid": os.getpid(),
        "seed": seed,
        "instrumentation_validity": "unknown",
        "system_outcome": "unknown",
        "reason": "",
        "next_action": "",
        "identities": {},
        "workload": {},
        "expected_artefacts": [],
        "historical": False,
    }
    data.update(fields or {})
    _write_json(attempt_dir / "attempt.json", data)
    _write_json(attempt_dir / "sources.json", {"sources": []})
    return attempt_dir


def update_attempt(attempt_dir: str | Path, updates: dict) -> dict:
    attempt_dir = Path(attempt_dir)
    data = _read_json(attempt_dir / "attempt.json")
    for key, value in updates.items():
        if key == "instrumentation_validity" and value not in VALIDITY_VALUES:
            raise ValueError(f"instrumentation_validity must be one of {VALIDITY_VALUES}")
        if key == "system_outcome" and value not in OUTCOME_VALUES:
            raise ValueError(f"system_outcome must be one of {OUTCOME_VALUES}")
        if key == "status" and value not in STATUS_VALUES:
            raise ValueError(f"status must be one of {STATUS_VALUES}")
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    _write_json(attempt_dir / "attempt.json", data)
    return data


def add_source(
    attempt_dir: str | Path,
    kind: str,
    path: str | Path,
    *,
    siblings_glob: str | None = None,
    role: str = "",
) -> None:
    """Record an artefact written outside the attempt directory.

    ``siblings_glob`` (for example ``"<run_id>.*"``) names files and folders
    next to ``path`` that belong to it, such as the integration helpers'
    ``<run_id>.marker.json`` or ``<run_id>.reconcile/``.
    """
    if kind not in SOURCE_KINDS:
        raise ValueError(f"kind must be one of {SOURCE_KINDS}")
    attempt_dir = Path(attempt_dir)
    sources = _read_json(attempt_dir / "sources.json")
    sources["sources"].append(
        {"kind": kind, "path": str(Path(path).resolve() if Path(path).exists() else path),
         "siblings_glob": siblings_glob, "role": role, "added_utc": utc_now()}
    )
    _write_json(attempt_dir / "sources.json", sources)


def _next_seq(attempt_dir: Path) -> int:
    lines = (attempt_dir / "commands.jsonl").read_text(encoding="utf-8").splitlines()
    return len([ln for ln in lines if ln.strip()]) + 1


def _tee(stream, sinks) -> None:
    for chunk in iter(lambda: stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536), b""):
        for sink in sinks:
            try:
                sink.write(chunk)
                sink.flush()
            except (OSError, ValueError):
                pass


def run_command(
    attempt_dir: str | Path,
    name: str,
    argv: list[str],
    *,
    secrets: dict[str, bytes] | None = None,
    cwd: str | Path | None = None,
    env: dict | None = None,
    echo: bool = True,
) -> int:
    """Run one command, keeping its stdout and stderr in ``console/``.

    The argv recorded in ``commands.jsonl`` has every secret value replaced by
    its variable name. Returns the command's exit code (127 if it could not be
    started); the caller decides what that code means for the attempt.
    """
    attempt_dir = Path(attempt_dir)
    secrets = secrets or {}
    seq = _next_seq(attempt_dir)
    slug = scenario_slug(name)
    out_rel = f"console/{seq:03d}-{slug}.stdout.txt"
    err_rel = f"console/{seq:03d}-{slug}.stderr.txt"
    data = _read_json(attempt_dir / "attempt.json")
    if not data.get("started_utc"):
        update_attempt(attempt_dir, {"started_utc": utc_now()})
    started = utc_now()
    t0 = _dt.datetime.now(_dt.timezone.utc)
    code: int
    with open(attempt_dir / out_rel, "wb") as out_f, open(attempt_dir / err_rel, "wb") as err_f:
        try:
            proc = subprocess.Popen(
                argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL
            )
        except OSError as exc:
            err_f.write(f"could not start: {exc}\n".encode())
            code = 127
        else:
            sinks_out = [out_f] + ([sys.stdout.buffer] if echo else [])
            sinks_err = [err_f] + ([sys.stderr.buffer] if echo else [])
            threads = [
                threading.Thread(target=_tee, args=(proc.stdout, sinks_out), daemon=True),
                threading.Thread(target=_tee, args=(proc.stderr, sinks_err), daemon=True),
            ]
            for t in threads:
                t.start()
            code = proc.wait()
            for t in threads:
                t.join()
    record = {
        "seq": seq,
        "name": name,
        "argv": [redact_text(a, secrets) for a in argv],
        "cwd": str(cwd) if cwd else None,
        "started_utc": started,
        "ended_utc": utc_now(),
        "duration_s": round((_dt.datetime.now(_dt.timezone.utc) - t0).total_seconds(), 3),
        "exit_code": code,
        "stdout": out_rel,
        "stderr": err_rel,
    }
    with open(attempt_dir / "commands.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return code


def finish_attempt(attempt_dir: str | Path, status: str, **updates) -> dict:
    return update_attempt(attempt_dir, {"status": status, "ended_utc": utc_now(), **updates})


# --------------------------------------------------------------------------
# Export (the Windows side)
# --------------------------------------------------------------------------


@dataclass
class _Plan:
    files: list[tuple[Path, str]] = field(default_factory=list)  # (source, package-relative dest)
    missing: list[dict] = field(default_factory=list)
    special: list[dict] = field(default_factory=list)  # FIFOs, sockets, devices, symlinks: never copied


def _walk(plan: _Plan, base: Path, prefix: str) -> None:
    """Regular files under ``base``; anything else is listed, never read.

    A FIFO would block a naive copy or hash, and a symlink could point
    outside the attempt, so both are recorded as skipped instead.
    """
    for p in sorted(base.rglob("*")):
        rel = f"{prefix}/{p.relative_to(base).as_posix()}"
        if p.is_symlink():
            plan.special.append({"package_path": rel, "source": str(p), "type": "symlink"})
        elif p.is_file():
            plan.files.append((p, rel))
        elif not p.is_dir():
            plan.special.append({"package_path": rel, "source": str(p), "type": "special file (FIFO, socket or device)"})


def _plan_files(attempt_dir: Path) -> _Plan:
    """Everything the attempt directory holds (except its export receipts), then its sources.

    Drivers may add their own folders (for a guest session: ``boot/``,
    ``guest/``, ``host/``); they are exported like the standard ones.
    """
    plan = _Plan()
    for p in sorted(attempt_dir.iterdir()):
        if p.name == "export":
            continue
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            plan.special.append({"package_path": p.name, "source": str(p),
                                 "type": "symlink" if p.is_symlink() else "special file (FIFO, socket or device)"})
        elif p.is_file():
            plan.files.append((p, p.name))
        else:
            _walk(plan, p, p.name)
    sources = _read_json(attempt_dir / "sources.json")["sources"] if (attempt_dir / "sources.json").is_file() else []
    for src in sources:
        path = Path(src["path"])
        top = src["kind"]
        entries = [path]
        if src.get("siblings_glob"):
            parent = path.parent
            if parent.is_dir():
                entries += sorted(
                    p for p in parent.iterdir()
                    if p != path and fnmatch.fnmatchcase(p.name, src["siblings_glob"])
                )
        if not path.exists():
            plan.missing.append({"kind": top, "path": str(path), "role": src.get("role", "")})
            entries = entries[1:]
        for entry in entries:
            if entry.is_symlink():
                plan.special.append({"package_path": f"{top}/{entry.name}", "source": str(entry), "type": "symlink"})
            elif entry.is_dir():
                _walk(plan, entry, f"{top}/{entry.name}")
            elif entry.is_file():
                plan.files.append((entry, f"{top}/{entry.name}"))
            else:
                plan.special.append({"package_path": f"{top}/{entry.name}", "source": str(entry),
                                     "type": "special file (FIFO, socket or device)"})
    seen: set[str] = set()
    unique = []
    for src, rel in plan.files:
        if rel in seen:
            raise ExportError(f"two artefacts map to the same package path {rel!r}")
        seen.add(rel)
        unique.append((src, rel))
    plan.files = unique
    return plan


def _scan(path: Path, secrets: dict[str, bytes]) -> list[str]:
    """Names of the secrets (or 'PRIVATE-KEY') a file contains."""
    if path.stat().st_size > _SCAN_LIMIT:
        found = []
        with open(path, "rb") as fh:
            tail = b""
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                window = tail + chunk
                found += [n for n, v in secrets.items() if v in window and n not in found]
                if _PRIVATE_KEY.search(window) and "PRIVATE-KEY" not in found:
                    found.append("PRIVATE-KEY")
                tail = window[-4096:]
        return found
    data = path.read_bytes()
    found = [n for n, v in secrets.items() if v in data]
    if _PRIVATE_KEY.search(data):
        found.append("PRIVATE-KEY")
    return found


def _is_text(path: Path) -> bool:
    with open(path, "rb") as fh:
        head = fh.read(8192)
    return b"\x00" not in head


def _copy_verified(src: Path, dst: Path, retries: int = 2) -> tuple[str, str]:
    """Copy bytes and verify by re-reading the destination. Returns (state, sha256)."""
    want = sha256_file(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_file() and sha256_file(dst) == want:
        return "verified", want
    last = ""
    for _ in range(retries + 1):
        tmp = dst.with_name(dst.name + ".partial")
        shutil.copyfile(src, tmp)
        try:
            shutil.copystat(src, tmp)
        except OSError:
            pass
        last = sha256_file(tmp)
        if last == want:
            os.replace(tmp, dst)
            return "verified", want
    return "mismatch", want


def _wsl_to_windows(path: Path) -> str:
    s = path.as_posix()
    m = re.match(r"^/mnt/([a-z])/(.*)$", s)
    return f"{m.group(1).upper()}:\\" + m.group(2).replace("/", "\\") if m else s


def export_attempt(
    attempt_dir: str | Path,
    dest_root: str | Path,
    *,
    secrets: dict[str, bytes] | None = None,
    copier=None,
) -> dict:
    """Export one attempt into ``dest_root`` and return its export manifest.

    Raises :class:`ExportError` when a copy cannot be verified; the partial
    package then stays under ``incomplete/`` and a later call resumes it.
    """
    attempt_dir = Path(attempt_dir)
    dest_root = Path(dest_root)
    secrets = secrets or {}
    copier = copier or _copy_verified
    attempt = _read_json(attempt_dir / "attempt.json")
    run_id = attempt["run_id"]
    if not (_RUN_ID.match(run_id) or _HIST_ID.match(run_id)):
        raise ExportError(f"run id {run_id!r} is not a valid export identity")
    final = dest_root / "runs" / run_date(run_id, attempt) / run_id
    staging = dest_root / "incomplete" / run_id
    receipt_path = attempt_dir / "export" / "receipt.json"

    if final.exists():
        problems = verify_sha256sums(final)
        if not problems and (final / "export_manifest.json").is_file():
            manifest = _read_json(final / "export_manifest.json")
            if manifest.get("run_id") == run_id:
                rebuild_index(dest_root)
                return {**manifest, "note": "already exported; the package verifies"}
        raise ExportError(f"{final} already exists and does not verify as this attempt's package: {problems[:3]}")

    if attempt.get("status") == "running":
        raise ExportError("the attempt is still marked running; finish it (or recover it) first")

    plan = _plan_files(attempt_dir)
    staging.mkdir(parents=True, exist_ok=True)
    files, excluded, sanitized, failed = [], [], [], []
    for src, rel in plan.files:
        found = _scan(src, secrets)
        if found:
            entry = {"source": str(src), "package_path": rel, "contains": sorted(found)}
            if _is_text(src) and "PRIVATE-KEY" not in found:
                text = redact_text(src.read_text(encoding="utf-8", errors="replace"), secrets)
                srel = rel + ".sanitized"
                (staging / srel).parent.mkdir(parents=True, exist_ok=True)
                (staging / srel).write_text(text, encoding="utf-8")
                entry["sanitized_derivative"] = srel
                sanitized.append(srel)
            excluded.append(entry)
            stale = staging / rel
            if stale.exists():
                stale.unlink()
            continue
        state, digest = copier(src, staging / rel)
        item = {"source": str(src), "package_path": rel, "size": src.stat().st_size, "sha256": digest, "state": state}
        files.append(item)
        if state != "verified":
            failed.append(rel)

    # A resumed export may find files of an earlier, different plan in the
    # staging folder (never in a finalised package): they must not be sealed.
    # The partial copies of a failed attempt are kept for inspection.
    keep = {f["package_path"] for f in files} | set(sanitized) | {"export_manifest.json", "SUMMARY.md"}
    for p in sorted(staging.rglob("*"), reverse=True):
        rel = p.relative_to(staging).as_posix()
        if p.is_file() and rel not in keep and not (failed and rel.endswith(".partial")):
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()

    manifest = {
        "tool": "egw_experiments.local_export",
        "tool_version": TOOL_VERSION,
        "tool_sha256": sha256_file(Path(__file__)),
        "run_id": run_id,
        "exported_utc": utc_now(),
        "source_attempt_dir": str(attempt_dir.resolve()),
        "destination": {"package": str(final), "windows_path": _wsl_to_windows(final.resolve() if final.parent.exists() else final)},
        "path_mapping": "sources are WSL paths; sealed files inside raw/ keep their original absolute paths",
        "files": files,
        "missing_sources": plan.missing,
        "skipped_special": plan.special,
        "excluded": excluded,
        "sanitized_derivatives": sanitized,
        "copy_verification": "verified" if not failed else "failed",
        "failed_copies": failed,
    }
    _write_json(staging / "export_manifest.json", manifest)
    if failed:
        _write_receipt(receipt_path, "failed", staging, manifest)
        rebuild_index(dest_root)
        raise ExportError(f"{len(failed)} file(s) did not verify after copying: {failed[:5]}; the package stays in {staging}")

    (staging / "SUMMARY.md").write_text(render_summary(attempt, manifest, _read_commands(attempt_dir)), encoding="utf-8")
    for f in _scan_package_for_secrets(staging, secrets):
        raise ExportError(f"generated file {f} contains a secret value; not finalised")
    write_sha256sums(staging)
    problems = verify_sha256sums(staging)
    if problems:
        _write_receipt(receipt_path, "failed", staging, manifest)
        raise ExportError(f"the package's SHA256SUMS does not verify: {problems[:3]}")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final)
    manifest["destination"]["windows_path"] = _wsl_to_windows(final.resolve())
    _write_receipt(receipt_path, "complete", final, manifest)
    rebuild_index(dest_root)
    return manifest


def _scan_package_for_secrets(package: Path, secrets: dict[str, bytes]) -> list[str]:
    hits = []
    for name in ("SUMMARY.md", "export_manifest.json"):
        p = package / name
        if p.is_file() and _scan(p, secrets):
            hits.append(name)
    return hits


def _write_receipt(path: Path, state: str, where: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, {
        "state": state,
        "package": str(where),
        "written_utc": utc_now(),
        "copy_verification": manifest.get("copy_verification"),
        "files": len(manifest.get("files", [])),
        "excluded": len(manifest.get("excluded", [])),
    })


def _read_commands(attempt_dir: Path) -> list[dict]:
    p = attempt_dir / "commands.jsonl"
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# --------------------------------------------------------------------------
# Summaries and the index
# --------------------------------------------------------------------------


def _duration(attempt: dict) -> str:
    try:
        a = _dt.datetime.strptime(attempt["started_utc"], "%Y-%m-%dT%H:%M:%S.%fZ")
        b = _dt.datetime.strptime(attempt["ended_utc"], "%Y-%m-%dT%H:%M:%S.%fZ")
        return f"{(b - a).total_seconds():.1f} s"
    except (KeyError, TypeError, ValueError):
        return "unknown"


def _cell(value) -> str:
    if value is None or value == "" or value == {}:
        return "—"
    if isinstance(value, dict):
        return "<br>".join(f"{k}: {v}" for k, v in sorted(value.items()))
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_summary(attempt: dict, manifest: dict, commands: list[dict]) -> str:
    lines = [f"# {attempt['run_id']}", ""]
    if attempt.get("emulated", True):
        lines += [f"**{EMULATED_LABEL}** — observations of an emulated guest, not native ARM64 performance.", ""]
    if attempt.get("historical"):
        lines += ["**Historical attempt, copied as it was preserved.** Its validity is the one it had; the copy "
                  "does not upgrade it.", ""]
    lines += [
        "| Field | Value |",
        "|---|---|",
        f"| Purpose | {_cell(attempt.get('purpose'))} |",
        f"| Scenario | {_cell(attempt.get('scenario'))} |",
        f"| Status | {_cell(attempt.get('status'))} |",
        f"| Started (UTC) | {_cell(attempt.get('started_utc'))} |",
        f"| Ended (UTC) | {_cell(attempt.get('ended_utc'))} |",
        f"| Duration | {_duration(attempt)} |",
        f"| Seed | {_cell(attempt.get('seed'))} |",
        f"| Workload | {_cell(attempt.get('workload'))} |",
        f"| Identities | {_cell(attempt.get('identities'))} |",
        "",
        "## Result",
        "",
        "Three separate verdicts: whether the instrumentation produced valid evidence, what the "
        "system under test did, and whether this copy is intact.",
        "",
        "| Verdict | Value |",
        "|---|---|",
        f"| Instrumentation validity | **{_cell(attempt.get('instrumentation_validity'))}** |",
        f"| System outcome | **{_cell(attempt.get('system_outcome'))}** |",
        f"| Copy verification | **{manifest.get('copy_verification')}** — {len(manifest.get('files', []))} file(s) "
        f"copied and verified by SHA-256; {len(manifest.get('excluded', []))} excluded for secrets; "
        f"{len(manifest.get('missing_sources', []))} expected source(s) missing |",
        f"| Reason | {_cell(attempt.get('reason'))} |",
        f"| Next action | {_cell(attempt.get('next_action'))} |",
        "",
    ]
    if commands:
        lines += ["## Commands", "", "| # | Name | Exit code | Duration (s) | Output |", "|---|---|---|---|---|"]
        for c in commands:
            lines.append(f"| {c['seq']} | {_cell(c['name'])} | {c['exit_code']} | {c['duration_s']} | "
                         f"[stdout]({c['stdout']}) · [stderr]({c['stderr']}) |")
        lines += ["", "The full, sanitised argv of each command is in `commands.jsonl`.", ""]
    if manifest.get("missing_sources"):
        lines += ["## Missing artefacts", ""]
        lines += [f"- `{m['kind']}` {m.get('role') or ''}: `{m['path']}` did not exist at export time"
                  for m in manifest["missing_sources"]]
        lines.append("")
    if attempt.get("expected_artefacts"):
        present = {f["package_path"] for f in manifest.get("files", [])}
        lines += ["## Expected artefacts", ""]
        for exp in attempt["expected_artefacts"]:
            ok = any(fnmatch.fnmatchcase(p, exp) for p in present)
            lines.append(f"- `{exp}`: {'present' if ok else '**missing**'}")
        lines.append("")
    if manifest.get("skipped_special"):
        lines += ["## Not copied: special files", ""]
        lines += [f"- `{s['package_path']}`: {s['type']}; listed here, never read" for s in manifest["skipped_special"]]
        lines.append("")
    if manifest.get("excluded"):
        lines += ["## Excluded for secrets", ""]
        for e in manifest["excluded"]:
            derivative = f"; redacted copy `{e['sanitized_derivative']}`" if e.get("sanitized_derivative") else ""
            lines.append(f"- `{e['package_path']}` contains {', '.join(e['contains'])}; the original stays on "
                         f"the WSL side only{derivative}")
        lines.append("")
    lines += [
        "## Contents",
        "",
        "- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.",
        "- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.",
        "- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.",
        "",
        "A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.",
        "",
    ]
    return "\n".join(lines)


def _package_rows(dest_root: Path) -> list[dict]:
    rows = []
    for state, base in (("final", dest_root / "runs"), ("incomplete", dest_root / "incomplete")):
        if not base.is_dir():
            continue
        dirs = base.glob("*/*") if state == "final" else base.glob("*")
        for d in sorted(dirs):
            if not d.is_dir():
                continue
            a = d / "attempt.json"
            try:
                attempt = _read_json(a) if a.is_file() else {"run_id": d.name}
            except (OSError, json.JSONDecodeError):
                attempt = {"run_id": d.name}
            m = d / "export_manifest.json"
            try:
                manifest = _read_json(m) if m.is_file() else {}
            except (OSError, json.JSONDecodeError):
                manifest = {}
            rows.append({
                "run_id": attempt.get("run_id", d.name),
                "rel": d.relative_to(dest_root).as_posix(),
                "state": state,
                "scenario": attempt.get("scenario", ""),
                "purpose": attempt.get("purpose", ""),
                "historical": attempt.get("historical", False),
                "validity": attempt.get("instrumentation_validity", "unknown"),
                "outcome": attempt.get("system_outcome", "unknown"),
                "copy": manifest.get("copy_verification", "not verified") if state == "final" else "INCOMPLETE",
                "reason": attempt.get("reason", ""),
                "created": attempt.get("created_utc") or attempt.get("date", ""),
            })
    rows.sort(key=lambda r: (str(r["created"]), r["run_id"]))
    return rows


def rebuild_index(dest_root: str | Path) -> Path:
    """Regenerate INDEX.md and LATEST_SUMMARY.md from the packages themselves.

    The index is derived, so no entry can be lost: every package and every
    incomplete export on disk is listed.
    """
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    rows = _package_rows(dest_root)
    out = [
        "# Test attempts — index",
        "",
        f"Regenerated {utc_now()} from the packages on disk. Every attempt is kept; nothing here is replaced.",
        f"QEMU observations are **{EMULATED_LABEL}**.",
        "",
        "| Run | Scenario | Purpose | Instrumentation validity | System outcome | Copy | Reason |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        link = f"[{r['run_id']}]({r['rel'].replace(' ', '%20')}/SUMMARY.md)" if r["state"] == "final" else \
            f"{r['run_id']} (`{r['rel']}`)"
        tag = " *(historical)*" if r["historical"] else ""
        out.append(f"| {link}{tag} | {_cell(r['scenario'])} | {_cell(r['purpose'])} | {_cell(r['validity'])} | "
                   f"{_cell(r['outcome'])} | {_cell(r['copy'])} | {_cell(r['reason'])} |")
    out.append("")
    index = dest_root / "INDEX.md"
    index.write_text("\n".join(out), encoding="utf-8")
    finals = [r for r in rows if r["state"] == "final" and not r["historical"]]
    latest = dest_root / "LATEST_SUMMARY.md"
    if finals:
        r = finals[-1]
        latest.write_text(
            f"# Latest attempt\n\nA convenience pointer only; [INDEX.md](INDEX.md) is the record.\n\n"
            f"- [{r['run_id']}]({r['rel'].replace(' ', '%20')}/SUMMARY.md): {r['scenario']} — validity "
            f"{r['validity']}, outcome {r['outcome']}, copy {r['copy']}\n",
            encoding="utf-8",
        )
    readme = dest_root / "README.md"
    if not readme.exists():
        readme.write_text(README_TEXT, encoding="utf-8")
    return index


README_TEXT = """# output_test — local test outputs

Every test attempt of the Digital Twin Edge Gateway is exported here from WSL,
one folder per attempt, at completion and on failure. Nothing is replaced.

- `INDEX.md` lists every attempt with its validity, outcome and copy state.
- `runs/<date>/<run_id>/SUMMARY.md` says what ran, the result and why; open it first.
- `runs/<date>/<run_id>/console/` holds stdout and stderr of every command.
- `raw/` and `simulator/` inside a package are the original artefacts, byte for byte.
- `incomplete/<run_id>/` is an export that has not been verified yet: not a pass.
- `SHA256SUMS` in a package seals that copy. It shows copy integrity only; a run's own
  validity is in its summary and, for harness runs, in its raw manifest.

QEMU observations are ARM64 EMULATED (QEMU/TCG), never native ARM64 performance. A package
here is not published or admitted evidence and not an off-machine backup. Secrets are
never copied: a file that contains one is listed as excluded, with a redacted derivative.

Written by `python -m egw_experiments.local_export` (repository `src/egw_experiments/local_export.py`).
"""


# --------------------------------------------------------------------------
# Recovery and historical backfill
# --------------------------------------------------------------------------


def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True


def recover(attempts_root: str | Path, dest_root: str | Path, *, secrets: dict[str, bytes] | None = None) -> list[dict]:
    """Export every attempt that has no complete export receipt.

    An attempt still marked running whose process is gone is marked
    interrupted first: a crash never hides an attempt.
    """
    results = []
    for attempt_dir in sorted(Path(attempts_root).glob("*")):
        if not (attempt_dir / "attempt.json").is_file():
            continue
        receipt = attempt_dir / "export" / "receipt.json"
        if receipt.is_file() and _read_json(receipt).get("state") == "complete":
            continue
        attempt = _read_json(attempt_dir / "attempt.json")
        if attempt.get("status") == "running":
            if _pid_alive(attempt.get("pid")) and attempt.get("pid") != os.getpid():
                results.append({"run_id": attempt["run_id"], "result": "skipped: still running"})
                continue
            finish_attempt(attempt_dir, "interrupted", system_outcome="interrupted",
                           reason=(attempt.get("reason") or "") + " [marked interrupted by recover: the process "
                           "that ran it is gone]")
        try:
            export_attempt(attempt_dir, dest_root, secrets=secrets)
            results.append({"run_id": attempt["run_id"], "result": "exported"})
        except ExportError as exc:
            results.append({"run_id": attempt["run_id"], "result": f"export failed: {exc}"})
    return results


def backfill(
    source: str | Path,
    attempts_root: str | Path,
    dest_root: str | Path,
    *,
    name: str,
    scenario: str,
    date: str,
    note: str,
    original_validity: str = "unknown",
    original_outcome: str = "unknown",
    secrets: dict[str, bytes] | None = None,
) -> dict:
    """Copy a preserved historical attempt as it is, indexed as historical."""
    run_id = "HIST_" + re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    attempt_dir = Path(attempts_root) / "_historical" / run_id
    if not attempt_dir.exists():
        attempt_dir.mkdir(parents=True)
        for d in ATTEMPT_DIRS:
            (attempt_dir / d).mkdir()
        (attempt_dir / "commands.jsonl").touch()
        _write_json(attempt_dir / "attempt.json", {
            "run_id": run_id, "scenario": scenario, "purpose": "engineering", "emulated": True,
            "created_utc": f"{date}T00:00:00.000000Z", "date": date, "status": "finished", "historical": True,
            "original_identity": str(source), "instrumentation_validity": original_validity,
            "system_outcome": original_outcome, "reason": note, "next_action": "", "identities": {},
            "workload": {}, "expected_artefacts": [], "seed": None, "started_utc": None, "ended_utc": None,
        })
        _write_json(attempt_dir / "sources.json", {"sources": []})
        add_source(attempt_dir, "raw", source, role="historical capsule, copied as preserved")
    return export_attempt(attempt_dir, dest_root, secrets=secrets)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def _parse_value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m egw_experiments.local_export", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("new", help="create an attempt and print its directory")
    s.add_argument("--attempts-root", required=True)
    s.add_argument("--scenario", required=True)
    s.add_argument("--purpose", required=True, choices=PURPOSES)
    s.add_argument("--dest-root", help="also avoid run numbers already exported there")
    s.add_argument("--seed", type=int)
    s.add_argument("--native", action="store_true", help="not an emulated guest (default: emulated)")

    s = sub.add_parser("exec", help="run one command inside an attempt; exits with its code")
    s.add_argument("--attempt", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--secrets-env")
    s.add_argument("--cwd")
    s.add_argument("cmd", nargs=argparse.REMAINDER)

    s = sub.add_parser("add-source", help="record an artefact written outside the attempt")
    s.add_argument("--attempt", required=True)
    s.add_argument("--kind", required=True, choices=SOURCE_KINDS)
    s.add_argument("--path", required=True)
    s.add_argument("--siblings-glob")
    s.add_argument("--role", default="")

    s = sub.add_parser("set", help="set attempt fields: KEY=VALUE (VALUE parsed as JSON when possible)")
    s.add_argument("--attempt", required=True)
    s.add_argument("pairs", nargs="+")

    s = sub.add_parser("finish", help="close an attempt")
    s.add_argument("--attempt", required=True)
    s.add_argument("--status", required=True, choices=STATUS_VALUES[1:])
    s.add_argument("--validity", choices=VALIDITY_VALUES)
    s.add_argument("--outcome", choices=OUTCOME_VALUES)
    s.add_argument("--reason")
    s.add_argument("--next-action")

    s = sub.add_parser("export", help="export one attempt")
    s.add_argument("--attempt", required=True)
    s.add_argument("--dest-root", required=True)
    s.add_argument("--secrets-env")

    s = sub.add_parser("recover", help="export every attempt without a complete export")
    s.add_argument("--attempts-root", required=True)
    s.add_argument("--dest-root", required=True)
    s.add_argument("--secrets-env")

    s = sub.add_parser("backfill", help="copy a preserved historical attempt, indexed as historical")
    s.add_argument("--source", required=True)
    s.add_argument("--attempts-root", required=True)
    s.add_argument("--dest-root", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--scenario", required=True)
    s.add_argument("--date", required=True)
    s.add_argument("--note", required=True)
    s.add_argument("--validity", default="unknown", choices=VALIDITY_VALUES)
    s.add_argument("--outcome", default="unknown", choices=OUTCOME_VALUES)
    s.add_argument("--secrets-env")

    s = sub.add_parser("index", help="regenerate INDEX.md from the packages on disk")
    s.add_argument("--dest-root", required=True)

    a = p.parse_args(argv)
    try:
        if a.command == "new":
            d = new_attempt(a.attempts_root, a.scenario, a.purpose, dest_root=a.dest_root, seed=a.seed,
                            emulated=not a.native)
            print(d)
        elif a.command == "exec":
            cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
            if not cmd:
                p.error("exec needs a command after --")
            return run_command(a.attempt, a.name, cmd, secrets=load_secrets(a.secrets_env), cwd=a.cwd)
        elif a.command == "add-source":
            add_source(a.attempt, a.kind, a.path, siblings_glob=a.siblings_glob, role=a.role)
        elif a.command == "set":
            updates = {}
            for pair in a.pairs:
                key, _, value = pair.partition("=")
                updates[key] = _parse_value(value)
            update_attempt(a.attempt, updates)
        elif a.command == "finish":
            updates = {k: v for k, v in (("instrumentation_validity", a.validity), ("system_outcome", a.outcome),
                                         ("reason", a.reason), ("next_action", a.next_action)) if v is not None}
            finish_attempt(a.attempt, a.status, **updates)
        elif a.command == "export":
            m = export_attempt(a.attempt, a.dest_root, secrets=load_secrets(a.secrets_env))
            print(f"exported {m['run_id']}: {m['destination']['windows_path']} ({m['copy_verification']}, "
                  f"{len(m['files'])} files, {len(m['excluded'])} excluded)")
        elif a.command == "recover":
            for r in recover(a.attempts_root, a.dest_root, secrets=load_secrets(a.secrets_env)):
                print(f"{r['run_id']}: {r['result']}")
        elif a.command == "backfill":
            m = backfill(a.source, a.attempts_root, a.dest_root, name=a.name, scenario=a.scenario, date=a.date,
                         note=a.note, original_validity=a.validity, original_outcome=a.outcome,
                         secrets=load_secrets(a.secrets_env))
            print(f"backfilled {m['run_id']}: {m['destination']['windows_path']} ({m['copy_verification']})")
        elif a.command == "index":
            print(rebuild_index(a.dest_root))
    except (ExportError, ValueError, FileExistsError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
