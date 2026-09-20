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
* Every path the export owns is built from the destination root's *physical*
  path and inspected component by component. A symlink, a Windows junction or
  any other reparse point on the way to an owned path is refused, never written
  through and never deleted through: a lexical prefix does not prove where the
  filesystem would put the bytes. A hard link at an owned path is refused too —
  it shares its bytes with a name outside the root while every check says it is
  inside — and every generated file is written through a fresh temporary file
  and one ``os.replace``. An export creates only directories and regular files,
  each with one name, so a link, a hard link or a FIFO found inside a staging
  folder or a package is foreign and the package is refused.
* The console file of a command is evidence: a write, flush, close or pipe-read
  failure on it is recorded (``capture_failures``), downgrades the attempt's
  validity and makes ``exec`` exit 74, while the command keeps its own exit
  code. The terminal echo is optional and its failure is not evidence loss. The
  verdict is the union of the attempt's list, the records in
  ``commands.jsonl`` and ``console/`` read in both directions — a file no
  record names, a recorded file that is gone or shorter than its record
  claims, and a ``console/`` that is a link or cannot be read at all — so one
  source going silent never makes an incomplete capture read as complete. One
  function decides that verdict (:func:`apply_capture_verdict`), and the
  attempt's file, the manifest, ``SUMMARY.md`` and the ``INDEX.md`` row are
  all built from it, so they cannot disagree; the export brings the attempt to
  it before the package is planned.
* Missing artefacts are listed as missing; nothing is fabricated. An artefact
  the export was told to copy and did not copy — refused, or never written —
  is named where the verdicts are read, never only in a list further down, and
  the export receipt each attempt keeps says in one field (``package_state``)
  whether what reached the destination is a verified package or a verified
  package with something missing.

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
import signal as _signal
import stat
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, NoReturn

from .checksums import sha256_file, verify_sha256sums, write_sha256sums

TOOL_VERSION = "1"
EMULATED_LABEL = "ARM64 EMULATED (QEMU/TCG)"
EXIT_CAPTURE_FAILED = 74  # EX_IOERR: the command ran, its console file did not keep everything
PURPOSES = ("engineering", "pilot", "official")
VALIDITY_VALUES = ("valid", "invalid", "not-applicable", "unknown")
OUTCOME_VALUES = ("pass", "fail", "inconclusive", "not-run", "interrupted", "unknown")
STATUS_VALUES = ("running", "finished", "failed", "interrupted")
ATTEMPT_DIRS = ("console", "environment", "tests", "analysis")
SOURCE_KINDS = ("raw", "simulator", "other")
#: Names this export writes itself inside a package; an artefact called like
#: one of them is refused instead of being sealed under the generated file's
#: bytes. ``SANITIZED_SUFFIX`` is the derivative written beside an excluded
#: file, which is a generated name too.
GENERATED_FILES = ("SUMMARY.md", "export_manifest.json", "SHA256SUMS")
# Said once, so the receipt can tell "the record itself could not be written"
# from "the record was written and a convenience file beside it is stale".
INDEX_WAS_WRITTEN = "INDEX.md was written and names it as stale"
SANITIZED_SUFFIX = ".sanitized"
_SCAN_LIMIT = 64 * 1024 * 1024
_RUN_ID = re.compile(r"^(\d{8}T\d{6}Z)_([A-Za-z0-9-]+(?:_[A-Za-z0-9-]+)*)_attempt(\d{2,})$")
_HIST_ID = re.compile(r"^HIST_[A-Za-z0-9._-]+$")
_PRIVATE_KEY = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_SECRET_NAME = re.compile(r"(PASS|SECRET|TOKEN|KEY|CREDENTIAL)", re.IGNORECASE)


class ExportError(Exception):
    """An export that could not be completed; the partial package stays visible."""


class UnsafePathError(ExportError):
    """An owned path that is, or passes through, a link: refused, never followed."""


class ForeignEntryError(UnsafePathError):
    """An entry no export creates, found in a staging folder or in a package.

    ``refused_as`` is the copy state ``INDEX.md`` publishes for the package it
    was found in, so the index says what was refused instead of calling every
    refusal a link.
    """

    def __init__(self, message: str, refused_as: str) -> None:
        super().__init__(message)
        self.refused_as = refused_as


class IndexWriteError(ExportError):
    """One generated index file could not be written; the others are as they were.

    ``file`` is the name of the one that failed, so the warning the operator
    reads never points at a file that was written successfully.
    """

    def __init__(self, file: str, restored: list[str], not_restored: list[str], cause: BaseException,
                 also: str = "") -> None:
        note = f"; {', '.join(restored)} put back as it was" if restored else ""
        if not_restored:
            note += f"; and {', '.join(not_restored)} could NOT be put back"
        if also:
            note += f"; {also}"
        super().__init__(f"{file} could not be written ({cause}){note}")
        self.file = file


# --------------------------------------------------------------------------
# Path safety
# --------------------------------------------------------------------------

_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _link_like(path: str | Path) -> bool:
    """True when ``path`` itself is a symlink, a Windows junction or a reparse point.

    ``lstat`` never follows the last component, so a dangling link is caught as
    well; a path that does not exist is not link-like. WSL presents an NTFS
    junction under ``/mnt/c`` as a symlink, and native Windows reports it
    through the file attributes, so both sides of this machine are covered.
    """
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    if getattr(st, "st_file_attributes", 0) & _REPARSE_POINT:
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is None:
        return False
    try:
        return bool(isjunction(path))
    except (OSError, ValueError):
        return False


def _link_type(path: str | Path) -> str:
    """How a refused entry is named in a manifest or in the index."""
    try:
        if stat.S_ISLNK(os.lstat(path).st_mode):
            return "symlink"
    except (OSError, ValueError):
        pass
    return "junction or other reparse point"


def _link_on_the_way(path: str | Path) -> Path | None:
    """The first component of ``path`` that is a link, or ``None``.

    ``os.lstat`` leaves only the *last* component unresolved, so a link
    anywhere above a source root is followed in silence and the bytes read are
    not the ones the recorded path names. The chain is therefore walked
    component by component, the way :meth:`_Destination.check` walks an owned
    path, and the component that is a link is named instead of being followed.
    """
    p = Path(path)
    current = Path(p.anchor) if p.anchor else Path()
    for name in (p.parts[1:] if p.anchor else p.parts):
        current = current / name
        if _link_like(current):
            return current
    return None


def _entry_kind(path: str | Path) -> str:
    """What an entry that is neither a directory nor a regular file is.

    A refusal that says only "not a regular file" sends the operator looking
    for the wrong obstacle, so the message names what was found.
    """
    try:
        mode = os.lstat(path).st_mode
    except (OSError, ValueError):
        return "an entry that could not be inspected"
    for test, name in ((stat.S_ISFIFO, "a FIFO"), (stat.S_ISSOCK, "a socket"),
                       (stat.S_ISCHR, "a character device"), (stat.S_ISBLK, "a block device")):
        if test(mode):
            return name
    return "an entry that is neither a directory nor a regular file"


def _name_count(path: str | Path) -> int:
    """How many names an existing regular file has; 1 when the count says nothing."""
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return 1
    return int(getattr(st, "st_nlink", 1)) if stat.S_ISREG(st.st_mode) else 1


def _hard_linked(path: str | Path) -> bool:
    """True when an existing regular file at ``path`` also has another name.

    A hard link is not a link the path leads *through*: it is a second name for
    the same inode, so ``realpath`` still says the path is inside the export
    root while a write truncates the other name's bytes in place. Every file
    the export creates is fresh, so more than one link is foreign. Only regular
    files are tested: a directory legitimately has one link per subdirectory on
    ext4 (measured 3 for a directory with one child), and NTFS reports 1 for
    every directory, so the count says nothing there.
    """
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return False
    return stat.S_ISREG(st.st_mode) and getattr(st, "st_nlink", 1) > 1


class _Destination:
    """The physical export root; every owned path is built and checked through it.

    The root is resolved once, and only here: a destination that is itself a
    link is therefore followed on purpose, so the export writes physically
    inside its target. Everything below it is built from that physical root and
    inspected component by component before anything is created, copied,
    written, deleted or promoted, because neither a lexical prefix nor a run id
    that matches the expected pattern says where the filesystem would put the
    bytes. An existing owned file that carries a second name (a hard link) is
    refused for the same reason, and every generated file is written through a
    fresh temporary file and one ``os.replace``, so a name that appeared
    between the check and the write is replaced rather than written through.
    """

    #: The names the export owns directly under the root.
    OWNED_TOP = ("runs", "incomplete", "INDEX.md", "LATEST_SUMMARY.md", "README.md")

    def __init__(self, dest_root: str | Path) -> None:
        self.given = Path(dest_root)
        self.root = Path(os.path.realpath(self.given))

    def __str__(self) -> str:
        return str(self.root)

    # -- checking ----------------------------------------------------------

    def _refuse(self, path: str | Path, why: str) -> NoReturn:
        raise UnsafePathError(f"refusing to use {path}: {why}; the export root is {self.root}")

    def _parts(self, path: Path) -> list[str]:
        try:
            rel = Path(os.path.abspath(path)).relative_to(self.root)
        except ValueError:
            self._refuse(path, "it is not under the export root")
        parts = [p for p in rel.parts if p not in ("", ".")]
        if any(p == ".." for p in parts):
            self._refuse(path, "it climbs out of the export root")
        return parts

    def check(self, path: Path, *, leaf_may_be_file: bool = True) -> Path:
        """``path`` itself, once every component that exists is proved safe.

        Each existing component from the root down must be a real directory —
        the last one may also be a regular file with no second name — and none
        of them may be a link. The physical path is then compared with the
        physical root, so a component that changed between the two checks is
        caught as well.
        """
        parts = self._parts(path)
        current = self.root
        for i, name in enumerate(parts):
            current = current / name
            try:
                st = os.lstat(current)
            except FileNotFoundError:
                break  # nothing below an absent component can exist either
            except OSError as exc:
                self._refuse(current, f"it could not be inspected ({exc})")
            if _link_like(current):
                self._refuse(current, f"it is a {_link_type(current)}")
            last = i == len(parts) - 1
            if stat.S_ISDIR(st.st_mode):
                continue
            if last and leaf_may_be_file and stat.S_ISREG(st.st_mode):
                if st.st_nlink > 1:
                    self._refuse(current, f"it is a hard link ({st.st_nlink} names share its bytes) and writing "
                                          "it would rewrite the other name in place")
                continue
            if stat.S_ISREG(st.st_mode):
                # An ordinary file in the way is an obstacle the operator can
                # open and move; naming it "neither a directory nor a regular
                # file" would send them looking for a device or a pipe.
                self._refuse(current, "it is a regular file where a directory is expected")
            self._refuse(current, f"it is {_entry_kind(current)}")
        root_n = os.path.normcase(str(self.root))
        try:
            physical = os.path.normcase(os.path.realpath(path))
            inside = physical == root_n or os.path.commonpath([physical, root_n]) == root_n
        except ValueError:
            inside = False
        if not inside:
            self._refuse(path, f"it resolves to {os.path.realpath(path)}, outside the export root")
        return path

    def check_owned_top(self) -> None:
        """Refuse a linked top-level name before the export creates anything."""
        for name in self.OWNED_TOP:
            self.check(self.root / name)

    # -- creating and removing --------------------------------------------

    def make_dir(self, path: Path) -> Path:
        """Create ``path`` and its missing parents one component at a time.

        Every component is checked before it is created and inspected again
        afterwards, so a link that appears between the two is refused instead
        of being written through.
        """
        self.check(path, leaf_may_be_file=False)
        if path.is_dir():
            return path
        os.makedirs(self.root, exist_ok=True)
        current = self.root
        for name in self._parts(path):
            current = current / name
            self.check(current, leaf_may_be_file=False)
            try:
                os.mkdir(current)
            except FileExistsError:
                pass
            self.check(current, leaf_may_be_file=False)
            if not current.is_dir():
                self._refuse(current, "it is not a directory after being created")
        return path

    def make_file(self, path: Path, *temp_suffixes: str) -> Path:
        """``path``, with its parents created safely and its own name proved free of links.

        ``temp_suffixes`` names the temporary companions the caller writes
        through (``.tmp``, ``.partial``): they are owned paths too, and
        ``shutil.copyfile`` or a plain write would truncate one in place.
        """
        self.make_dir(path.parent)
        for candidate in (path, *(path.with_name(path.name + s) for s in temp_suffixes)):
            if _link_like(candidate):
                self._refuse(candidate, f"it is a {_link_type(candidate)}")
            if _hard_linked(candidate):
                self._refuse(candidate, "it is a hard link and writing it would rewrite the other name in place")
        return self.check(path)

    def write_bytes(self, path: Path, data: bytes) -> Path:
        """Write an owned file through a fresh temporary file and one replace.

        A generated file is never opened in place: a name that appeared between
        the check and the write — a hard link planted at an owned path, which
        shares its bytes with a file outside the root — is replaced, so the
        other name keeps what it held.
        """
        target = self.make_file(path, ".tmp")
        tmp = self.check(target.with_name(target.name + ".tmp"))
        if os.path.lexists(tmp):
            tmp.unlink()
        with open(tmp, "xb") as fh:
            fh.write(data)
        try:
            os.replace(tmp, target)
        except OSError:
            # A replace the filesystem refused (a read-only target, a handle
            # an editor holds open) would otherwise leave an unexplained
            # '.tmp' beside the file it never became.
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        return target

    def write_text(self, path: Path, text: str) -> Path:
        """Write an owned text file, in UTF-8 with LF endings, through a fresh file."""
        return self.write_bytes(path, text.encode("utf-8"))

    def write_json(self, path: Path, data: dict) -> Path:
        """Write an owned JSON file through a fresh file."""
        return self.write_text(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def unlink(self, path: Path) -> None:
        """Delete an owned file: never a link, and never through one."""
        self.check(path)
        path.unlink()

    def rmdir(self, path: Path) -> None:
        """Remove an owned empty directory: never a link, and never through one."""
        self.check(path, leaf_may_be_file=False)
        path.rmdir()

    # -- walking -----------------------------------------------------------

    def _refuse_foreign(self, path: str | Path, why: str, refused_as: str) -> NoReturn:
        raise ForeignEntryError(
            f"refusing to use {path}: {why}; the export root is {self.root}", refused_as)

    def walk(self, base: Path) -> list[tuple[Path, bool]]:
        """Everything under ``base`` as ``(path, is_dir)``, children before parents.

        ``os.scandir`` is used directly so a linked directory is never
        descended into. An export creates only directories and regular files,
        each with one name, so anything else found in a staging folder or in a
        package is foreign — a link, a hard link (which would tie a sealed
        package to a file it cannot see) and a FIFO, socket or device alike —
        and the whole package is refused rather than sealed around it.
        """
        self.check(base, leaf_may_be_file=False)
        entries: list[tuple[Path, bool]] = []
        stack = [base]
        while stack:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    p = Path(e.path)
                    if _link_like(p):
                        self._refuse_foreign(
                            p, f"an export never creates links, so this {_link_type(p)} is foreign",
                            "REFUSED: link")
                    names = _name_count(p)
                    if names > 1:
                        # The count says a second name exists; it does not say
                        # where, and the export does not go looking, so the
                        # refusal states what was measured and nothing else.
                        self._refuse_foreign(
                            p, f"this file has {names} names and an export creates every file with one, "
                               "so it is foreign", "REFUSED: link")
                    is_dir = e.is_dir(follow_symlinks=False)
                    if not is_dir and not e.is_file(follow_symlinks=False):
                        self._refuse_foreign(
                            p, f"an export creates only directories and regular files, so {_entry_kind(p)} "
                               "here is foreign", "REFUSED: special file")
                    entries.append((p, is_dir))
                    if is_dir:
                        stack.append(p)
        entries.sort(key=lambda item: item[0].as_posix(), reverse=True)
        return entries


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
        return valid_date(str(attempt["date"]))
    raise ValueError(f"cannot derive a date from run id {run_id!r}")


def valid_date(text: str) -> str:
    """A calendar date in the form YYYY-MM-DD, or ValueError.

    The date becomes a folder name under ``runs/``: anything else (``..``, an
    absolute path) could place a package outside the destination root.
    """
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError(f"date {text!r} is not in the form YYYY-MM-DD")
    _dt.date.fromisoformat(text)
    return text


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
        "validity_note": "",
        "system_outcome": "unknown",
        "reason": "",
        "next_action": "",
        "identities": {},
        "workload": {},
        "expected_artefacts": [],
        "capture_failures": [],
        "historical": False,
    }
    data.update(fields or {})
    _write_json(attempt_dir / "attempt.json", data)
    _write_json(attempt_dir / "sources.json", {"sources": []})
    return attempt_dir


_CONSOLE_FILE = re.compile(r"^(\d{3,})-(.+)\.(stdout|stderr)\.txt$")


@dataclass
class _ConsoleDir:
    """What ``console/`` holds, and what stopped the export from seeing it.

    An empty ``files`` mapping is not the same fact as a directory that could
    not be listed, so the second is carried beside the first instead of being
    swallowed: a source of the capture verdict that goes silent has to say so,
    or a package with no console evidence at all reads as a complete capture.
    ``listing_error`` is what stopped the *directory itself* from being read —
    it is a link, it is not a directory, or it could not be listed — kept
    apart from the entries, because a stream's own refusal must state what was
    measured and never a cause the export did not establish.
    """

    files: dict[str, int] = field(default_factory=dict)
    problems: list[tuple[str, str]] = field(default_factory=list)  # (console path, why)
    listing_error: str = ""


def _console_inventory(attempt_dir: str | Path) -> _ConsoleDir:
    """Every console file on disk with its size, and every one that could not be read.

    The directory is proved before it is listed. ``exec`` creates ``console/``
    and nothing else does, so one that is a link — or that is not a directory
    at all — holds bytes that are not provably this attempt's evidence, and
    ``iterdir`` would follow it and report every recorded stream as found, at
    its full size, behind the link. The planner refuses such a directory and
    copies nothing from it, so a verdict that called it complete would
    contradict the package it sits in.
    """
    console = Path(attempt_dir) / "console"
    found = _ConsoleDir()
    if _link_like(console):
        found.listing_error = f"the console directory is a {_link_type(console)} and an export never creates one"
        found.problems.append(("console", f"{found.listing_error}, so what it holds is not provably this "
                                          "attempt's own evidence"))
        return found
    try:
        st = os.lstat(console)
    except FileNotFoundError:
        return found  # an attempt that has no console/ at all: nothing to account for
    except OSError as exc:
        found.listing_error = f"the console directory could not be inspected ({exc.strerror or exc})"
        found.problems.append(("console", f"{found.listing_error}, so nothing here can say what it holds"))
        return found
    if not stat.S_ISDIR(st.st_mode):
        what = "a regular file" if stat.S_ISREG(st.st_mode) else _entry_kind(console)
        found.listing_error = f"console is not a directory: it is {what}"
        found.problems.append(("console", f"{found.listing_error}, so it cannot be the folder this attempt's "
                                          "console output was kept in"))
        return found
    try:
        entries = sorted(console.iterdir())
    except OSError as exc:
        found.listing_error = f"the console directory could not be listed ({exc.strerror or exc})"
        found.problems.append(("console", f"{found.listing_error}, so nothing here can say what it holds"))
        return found
    for p in entries:
        rel = f"console/{p.name}"
        if _link_like(p):
            found.problems.append((rel, f"it is a {_link_type(p)}; an export never creates one, so what it "
                                        "points at is not this attempt's own evidence"))
            continue
        try:
            st = os.lstat(p)
        except OSError as exc:
            found.problems.append((rel, f"it could not be inspected ({exc.strerror or exc})"))
            continue
        if stat.S_ISREG(st.st_mode):
            found.files[rel] = st.st_size
        else:
            what = "a directory" if stat.S_ISDIR(st.st_mode) else _entry_kind(p)
            found.problems.append((rel, f"it is {what}, not a file that can hold console output"))
    return found


def _as_console_dir(console: _ConsoleDir | dict[str, int] | None) -> _ConsoleDir | None:
    """The inventory as one type; ``None`` still means nobody looked at ``console/``."""
    if console is None:
        return None
    return console if isinstance(console, _ConsoleDir) else _ConsoleDir(files=dict(console))


def _failure_id(f: dict):
    """One stream's identity, the same one on every side of the union.

    The console file names a stream better than ``(seq, stream)`` does,
    because a file the console pattern does not explain has no sequence
    number and no stream: keyed on those two it would be admitted again on
    every read — counted twice, and, with a second one beside it, one of the
    two dropped.
    """
    return f.get("console") or (f.get("seq"), f.get("stream"))


def _failure_order(f: dict) -> tuple:
    seq = f.get("seq")
    return (seq is None, seq or 0, str(f.get("stream") or ""), str(f.get("console") or ""))


def capture_failures(attempt: dict, commands: list[dict],
                     console: _ConsoleDir | dict[str, int] | None = None) -> list[dict]:
    """Every console stream known not to have been kept in full, deduplicated.

    Three sources are joined, because none of them alone can be trusted:

    * the attempt's own ``capture_failures``, which is written *after* the
      command's record and can therefore be lost (a read-only attempt
      directory, a crash between the two writes, a later ``set``);
    * the records in ``commands.jsonl``, whose ``capture`` object says what
      each stream kept — but which an interrupted command never reaches;
    * the console files themselves, created before the child starts, so one
      with no record is output nobody accounted for, and one a record *does*
      name must still be there and still hold what that record claims.

    The third source is read in both directions on purpose. A record saying
    881 bytes were kept proves nothing about a file that has since been
    truncated or removed, and hashing a truncated file does not bring the
    missing output back, so a recorded stream whose file is gone or shorter
    than its record is a capture failure like any other.

    Each entry keeps the fields of the attempt's list (``seq``, ``name``,
    ``stream``, ``error``, ``bytes_received``, ``bytes_kept``) so the drivers
    and ``attempt.json`` see one shape, plus the console file it concerns.
    ``bytes_received`` is ``None`` when nothing recorded how much the child
    produced.
    """
    console = _as_console_dir(console)
    named = {(c.get("seq"), s): c.get(s) for c in commands for s in ("stdout", "stderr") if c.get(s)}
    found: dict = {}
    for f in attempt.get("capture_failures") or []:
        entry = dict(f)
        # A stored entry from before the console path was recorded is given
        # the one its command's record names, so both sides key it alike.
        entry.setdefault("console", None)
        if not entry["console"]:
            entry["console"] = named.get((entry.get("seq"), entry.get("stream")))
        found.setdefault(_failure_id(entry), entry)
    for c in commands:
        capture = c.get("capture") or {}
        for stream in ("stdout", "stderr"):
            state = capture.get(stream) or {}
            if state.get("state") != "failed":
                continue
            entry = {"seq": c.get("seq"), "name": c.get("name"), "stream": stream,
                     "error": state.get("error") or "recorded as failed with no reason",
                     "bytes_received": state.get("bytes_received"), "bytes_kept": state.get("bytes_kept"),
                     "console": c.get(stream)}
            found.setdefault(_failure_id(entry), entry)
    if console is not None:
        _add_lost_console_files(found, commands, console)
        _add_unaccounted_console_files(found, commands, console)
        for rel, why in console.problems:
            found.setdefault(rel, {
                "seq": None, "name": rel, "stream": "unknown", "error": why,
                "bytes_received": None, "bytes_kept": None, "console": rel, "unreadable": True})
    return sorted(found.values(), key=_failure_order)


def _add_lost_console_files(found: dict, commands: list[dict], console: _ConsoleDir) -> None:
    """A recorded stream whose console file is gone, or shorter than its record claims.

    A refusal states what was measured. When the directory itself could not be
    read, nothing was measured about the file — a directory that cannot be
    listed can still hold every one of them, openable by name — so the reason
    given is the one the export established, and "no longer in the attempt" is
    kept for the case it really saw: a listing that succeeded without it. The
    same holds one level down: when the inventory refused this very entry (it
    is a link, it could not be inspected, it is not a file), that reason is the
    measured one and it is used instead. Nothing was measured about the bytes
    in either case, so ``bytes_kept`` stays unknown rather than being reported
    as zero against a record that says otherwise.
    """
    refused = dict(console.problems)
    for c in commands:
        capture = c.get("capture") or {}
        for stream in ("stdout", "stderr"):
            rel = c.get(stream)
            if not rel or rel in found:
                continue  # already known to be incomplete: one stream, one entry
            state = capture.get(stream) or {}
            kept = state.get("bytes_kept")
            size = console.files.get(rel)
            if size is None and rel in refused:
                error = refused[rel]
            elif size is None and console.listing_error:
                error = f"{console.listing_error}, so this stream cannot be shown to hold what the record claims"
            elif size is None:
                error = ("the console file is no longer in the attempt: the stream cannot be shown to hold "
                         "what the record claims")
            elif isinstance(kept, int) and size < kept:
                error = f"the console file holds {size} byte(s); the record says {kept} were kept"
            else:
                continue
            found[rel] = {"seq": c.get("seq"), "name": c.get("name"), "stream": stream, "error": error,
                          "bytes_received": state.get("bytes_received"), "bytes_kept": size,
                          "console": rel, "lost": True}


def _add_unaccounted_console_files(found: dict, commands: list[dict], console: _ConsoleDir) -> None:
    """A console file whose name follows the ``exec`` pattern and that no record names.

    Only that shape is a lost stream of this attempt: ``exec`` creates the
    file before the child starts, so one left without a record is a command
    that was interrupted or whose record could never be appended. A name the
    pattern does not explain was written by something else and is reported as
    what it is — see :func:`console_extras` — never as a stream nobody kept.
    """
    recorded = {c.get(s) for c in commands for s in ("stdout", "stderr") if c.get(s)}
    for rel, size in sorted(console.files.items()):
        m = _CONSOLE_FILE.match(rel.rsplit("/", 1)[-1])
        if rel in recorded or not m:
            continue
        found.setdefault(rel, {
            "seq": int(m.group(1)), "name": m.group(2), "stream": m.group(3),
            "error": "no command record: the command never reached commands.jsonl (interrupted, or the "
                     "record could not be appended), so nothing says how much output it produced",
            "bytes_received": None, "bytes_kept": size, "console": rel, "unaccounted": True})


def console_extras(commands: list[dict], console: _ConsoleDir | dict[str, int] | None) -> list[dict]:
    """Files in ``console/`` this export did not write and no record names.

    ``exec`` names every console file ``<NNN>-<slug>.<stream>.txt``. A name
    that does not follow it came from something else — an editor's swap file
    beside a console file a reader opened, an operator's note in a folder the
    drivers tell them to read, a ``desktop.ini`` written when the attempt
    directory is browsed from Windows — so it is listed as the extra file it
    is. It is copied with the rest of the package and it downgrades nothing:
    a stray byte must not cost a measured run its validity.
    """
    console = _as_console_dir(console)
    if console is None:
        return []
    recorded = {c.get(s) for c in commands for s in ("stdout", "stderr") if c.get(s)}
    return [{"console": rel, "bytes": size} for rel, size in sorted(console.files.items())
            if rel not in recorded and not _CONSOLE_FILE.match(rel.rsplit("/", 1)[-1])]


def apply_capture_verdict(attempt: dict, commands: list[dict],
                          console: _ConsoleDir | dict[str, int] | None) -> dict:
    """``attempt`` with the capture verdict of these three sources applied.

    This is the one place a capture verdict is decided: the list of streams
    that were not kept in full and what that costs the instrumentation
    validity. The attempt's own file, the export manifest, ``SUMMARY.md`` and
    the ``INDEX.md`` row are all built from this function on the same inputs,
    so no two of them can say different things about one attempt.
    """
    data = dict(attempt)
    data["capture_failures"] = capture_failures(attempt, commands, console)
    _downgrade_on_capture_failure(data)
    return data


def _apply_capture_failures(attempt_dir: Path, data: dict) -> None:
    """Fold every known capture failure into the attempt, then downgrade its validity.

    While the attempt is still running, a console file with no record is a
    command that has not finished yet, not an unaccounted one, and a console
    file shorter than its record is one still being written; once the attempt
    is closed, nothing else will ever record it.
    """
    console = _console_inventory(attempt_dir) if data.get("status") != "running" else None
    data.update(apply_capture_verdict(data, _read_commands(attempt_dir), console))


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
    _apply_capture_failures(attempt_dir, data)
    _write_json(attempt_dir / "attempt.json", data)
    return data


def _downgrade_on_capture_failure(data: dict) -> None:
    """No verdict but ``invalid`` survives a console capture known to be incomplete.

    ``valid`` is not the only value a driver writes: ``new_attempt`` starts
    every attempt at ``unknown`` and ``guest_session_close.sh`` closes the
    ordinary session with ``not-applicable``, and a stream that was not kept is
    evidence lost in either state. The README written into the destination and
    ``docs/setup/local_test_outputs.md`` both promise the downgrade without
    qualification, so every value that is not already ``invalid`` is
    downgraded. The caller's own verdict is kept in ``validity_note``, so the
    downgrade is visible as a downgrade and not as an opinion the driver never
    expressed.
    """
    failures = data.get("capture_failures") or []
    was = data.get("instrumentation_validity") or "unknown"
    if not failures or was == "invalid":
        return
    streams = sorted({f"{f.get('stream') or '?'} of {f.get('name') or '?'}" for f in failures})
    data["instrumentation_validity"] = "invalid"
    data["validity_note"] = (
        f"downgraded from {was!r}: {len(failures)} console capture(s) failed ({', '.join(streams)}); "
        "the recorded output is incomplete, so the evidence cannot be called valid"
    )


def refuse_relative_components(path: str | Path) -> None:
    """Refuse a source path that holds a ``.`` or ``..`` component.

    The export never resolves a source's last component, so that a root which
    is a link keeps its link identity. A trailing ``..`` would defeat exactly
    that: ``lstat`` resolves the whole chain for such a spelling, the link is
    followed and the bytes behind it are read, and the ``..`` also takes the
    package path out of its ``raw/`` or ``simulator/`` folder. The drivers
    always register a plain path, so one with either component is refused
    where it is given rather than repaired.
    """
    raw = os.fspath(path)
    separators = [os.sep] + ([os.altsep] if os.altsep else [])
    parts = re.split("|".join(re.escape(s) for s in separators), raw)
    if any(part in (".", "..") for part in parts):
        raise ValueError(f"source path {raw!r} has a '.' or '..' component; give the path without one, so that "
                         "its last component is a real name and a source root that is a link stays a link")


def _physical_parent(p: Path) -> Path:
    """``p`` with its parent made physical as far as the filesystem knows it.

    The last component is never resolved, so a source root that is a link
    keeps its link identity. The parent is resolved because a link there says
    *where* the artefact is, not what it is called — but a driver registers a
    capsule before the harness creates it (``nominal.sh`` refuses to start
    unless the raw directory is absent), so the parent often does not exist
    yet. The longest prefix that does exist is therefore resolved and the
    names below it are kept as given, instead of storing the whole spelling
    unresolved and leaving ``lstat`` to resolve the chain at export time.
    """
    parent = p.parent
    below: list[str] = []
    while not parent.exists() and parent != parent.parent:
        below.append(parent.name)
        parent = parent.parent
    physical = Path(os.path.realpath(parent))
    for name in reversed(below):
        physical = physical / name
    return physical / p.name


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
    refuse_relative_components(path)
    sources = _read_json(attempt_dir / "sources.json")
    # Always absolute: a path that does not exist yet must not later be
    # resolved against whatever directory the export happens to run in. The
    # last component is never resolved, so a source root that is a link keeps
    # its link identity and the export can list it instead of reading through
    # it; only the parent is made physical.
    p = Path(path).absolute()
    if p.name:
        p = _physical_parent(p)
    sources["sources"].append(
        {"kind": kind, "path": str(p),
         "siblings_glob": siblings_glob, "role": role, "added_utc": utc_now()}
    )
    _write_json(attempt_dir / "sources.json", sources)


def _open_console_pair(attempt_dir: Path, slug: str):
    """The next free command number, with its two console files created exclusively.

    The number is one more than any number already used in ``console/``, so an
    interrupted command (console files, no record) or a concurrent one never has
    its output overwritten.
    """
    console = attempt_dir / "console"
    console.mkdir(exist_ok=True)
    while True:
        used = [int(m.group(1)) for m in (re.match(r"^(\d{3,})-", p.name) for p in console.iterdir()) if m]
        seq = max(used, default=0) + 1
        out_rel = f"console/{seq:03d}-{slug}.stdout.txt"
        err_rel = f"console/{seq:03d}-{slug}.stderr.txt"
        try:
            out_f = open(attempt_dir / out_rel, "xb")
        except FileExistsError:
            continue
        try:
            err_f = open(attempt_dir / err_rel, "xb")
        except FileExistsError:
            out_f.close()
            continue
        return seq, out_rel, err_rel, out_f, err_f


def _position(sink) -> int | None:
    """How many bytes a sink really holds, when it can say; ``None`` otherwise."""
    try:
        pos = sink.tell()
    except (OSError, ValueError, AttributeError):
        return None
    return pos if isinstance(pos, int) else None


@dataclass
class _Capture:
    """What reached the console file of one stream, and what stopped it.

    The console file is the mandatory sink: it is the evidence, and a failure
    on it is a loss of evidence. The terminal echo is optional; it exists so
    the operator can watch, and losing it loses nothing.
    """

    stream: str
    echo_requested: bool = True
    bytes_received: int = 0
    bytes_kept: int = 0
    error: str = ""
    echo_error: str = ""

    @property
    def state(self) -> str:
        return "failed" if self.error else "complete"

    def _kept(self, measured: int | None) -> None:
        """Replace the counted bytes by what the console file really holds."""
        if measured is None:
            return
        self.bytes_kept = max(0, min(int(measured), self.bytes_received))

    def write(self, sink, chunk: bytes) -> None:
        """Send one chunk to the console file; the first failure abandons that sink."""
        self.bytes_received += len(chunk)
        if sink is None or self.error:
            return
        try:
            sink.write(chunk)
            sink.flush()
        except (OSError, ValueError) as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            # Part of the failing chunk may have been accepted before the
            # error: what the file holds is evidence that survived, and
            # reporting it as lost would keep a reader from opening it.
            self._kept(_position(sink))
        else:
            self.bytes_kept += len(chunk)

    def echo(self, sink, chunk: bytes) -> None:
        """Send one chunk to the terminal; a failure here is recorded, never counted as loss."""
        if sink is None or self.echo_error:
            return
        try:
            sink.write(chunk)
            sink.flush()
        except (OSError, ValueError) as exc:
            self.echo_error = f"{type(exc).__name__}: {exc}"

    def read_failed(self, exc: BaseException) -> None:
        """The child's pipe could not be read: the rest of the output is lost."""
        if not self.error:
            self.error = f"read: {type(exc).__name__}: {exc}"

    def close(self, sink, path: Path | None = None) -> None:
        """Close the console file; a close that fails lost buffered bytes.

        ``path`` is the console file itself: after any failure its size on disk
        is the honest count, whether the loss happened during a write (part of
        a chunk was accepted) or at the close (buffered bytes never reached it).
        """
        try:
            sink.close()
        except (OSError, ValueError) as exc:
            if not self.error:
                self.error = f"close: {type(exc).__name__}: {exc}"
        if self.error and path is not None:
            try:
                self._kept(os.path.getsize(path))
            except OSError:
                pass

    def record(self) -> dict:
        return {
            "state": self.state,
            "bytes_received": self.bytes_received,
            "bytes_kept": self.bytes_kept,
            "error": self.error or None,
            "echo": f"failed: {self.echo_error}" if self.echo_error
                    else ("written" if self.echo_requested else "not requested"),
        }

    def failure(self, seq: int, name: str, console: str = "") -> dict:
        return {"seq": seq, "name": name, "stream": self.stream, "error": self.error,
                "bytes_received": self.bytes_received, "bytes_kept": self.bytes_kept,
                "console": console or None}


def _tee(stream, sink, echo, capture: _Capture) -> None:
    """Drain one pipe into its console file, echoing it to the terminal when asked.

    The pipe is read to the end whatever happens to the sinks: a child whose
    output filled the pipe would otherwise block for ever and never report its
    own exit code. A pipe that cannot be read is itself a loss of evidence and
    is recorded as one, instead of ending the thread with a traceback and
    leaving the capture looking complete.
    """
    read = stream.read1 if hasattr(stream, "read1") else stream.read
    while True:
        try:
            chunk = read(65536)
        except (OSError, ValueError) as exc:
            capture.read_failed(exc)
            return
        if not chunk:
            return
        capture.write(sink, chunk)
        capture.echo(echo, chunk)


def run_command_record(
    attempt_dir: str | Path,
    name: str,
    argv: list[str],
    *,
    secrets: dict[str, bytes] | None = None,
    cwd: str | Path | None = None,
    env: dict | None = None,
    echo: bool = True,
) -> dict:
    """Run one command and return the record written to ``commands.jsonl``.

    The argv recorded there has every secret value replaced by its variable
    name. ``exit_code`` is always the command's own (127 if it could not be
    started, and on POSIX the negative value ``wait`` returns for a child
    killed by a signal, whose number is then also in ``killed_by_signal``);
    whether each console file kept everything is the separate ``capture``
    object, because a truncated capture is a loss of evidence and not a failure
    of the command. A capture failure is written to the attempt's
    ``capture_failures``, which downgrades its validity, *before* the record is
    appended: the record is the only trace left if that write cannot be made,
    and :func:`capture_failures` reads both.
    """
    attempt_dir = Path(attempt_dir)
    secrets = secrets or {}
    slug = scenario_slug(name)
    seq, out_rel, err_rel, out_file, err_file = _open_console_pair(attempt_dir, slug)
    data = _read_json(attempt_dir / "attempt.json")
    if not data.get("started_utc"):
        update_attempt(attempt_dir, {"started_utc": utc_now()})
    started = utc_now()
    t0 = _dt.datetime.now(_dt.timezone.utc)
    cap_out = _Capture("stdout", echo_requested=echo)
    cap_err = _Capture("stderr", echo_requested=echo)
    code: int
    try:
        try:
            proc = subprocess.Popen(
                argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL
            )
        except OSError as exc:
            cap_err.write(err_file, f"could not start: {exc}\n".encode())
            code = 127
        else:
            threads = [
                threading.Thread(target=_tee, daemon=True,
                                 args=(proc.stdout, out_file, sys.stdout.buffer if echo else None, cap_out)),
                threading.Thread(target=_tee, daemon=True,
                                 args=(proc.stderr, err_file, sys.stderr.buffer if echo else None, cap_err)),
            ]
            for t in threads:
                t.start()
            code = proc.wait()
            for t in threads:
                t.join()
    finally:
        cap_out.close(out_file, attempt_dir / out_rel)
        cap_err.close(err_file, attempt_dir / err_rel)
    killed = -code if code < 0 else 0  # POSIX: wait() returns -N for a child killed by signal N
    record = {
        "seq": seq,
        "name": name,
        "argv": [redact_text(a, secrets) for a in argv],
        "cwd": str(cwd) if cwd else None,
        "started_utc": started,
        "ended_utc": utc_now(),
        "duration_s": round((_dt.datetime.now(_dt.timezone.utc) - t0).total_seconds(), 3),
        "exit_code": code,
        "killed_by_signal": killed or None,
        "stdout": out_rel,
        "stderr": err_rel,
        "capture": {"stdout": cap_out.record(), "stderr": cap_err.record()},
    }
    failures = [c.failure(seq, name, rel) for c, rel in ((cap_out, out_rel), (cap_err, err_rel)) if c.error]
    if failures:
        # Written first: an append that fails would otherwise be the only trace
        # of the loss, and a failure to record the loss is a loss in itself.
        try:
            kept = _read_json(attempt_dir / "attempt.json").get("capture_failures") or []
            update_attempt(attempt_dir, {"capture_failures": list(kept) + failures})
        except (OSError, ValueError) as exc:
            record["capture"]["not_persisted"] = f"{type(exc).__name__}: {exc}"
    with open(attempt_dir / "commands.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


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

    Returns the command's exit code (127 if it could not be started); the
    caller decides what that code means for the attempt. Use
    :func:`run_command_record` to see whether the console capture was complete.
    """
    return run_command_record(attempt_dir, name, argv, secrets=secrets, cwd=cwd, env=env, echo=echo)["exit_code"]


def capture_failed(record: dict) -> bool:
    """True when either console file of a recorded command did not keep everything."""
    capture = record.get("capture") or {}
    return any((capture.get(s) or {}).get("state") == "failed" for s in ("stdout", "stderr"))


def signal_name(number: int) -> str:
    """``SIGKILL`` for 9, or ``signal 9`` when this platform has no name for it."""
    try:
        return _signal.Signals(number).name
    except (ValueError, AttributeError):
        return f"signal {number}"


def command_exit_status(record: dict) -> int:
    """The status the command line reports for one recorded command.

    ``exit_code`` keeps what the child really returned, which on POSIX is the
    negative of the signal that killed it; ``sys.exit`` would turn that into
    ``256 - N``, a status no caller can read against the drivers' table. A
    killed child is therefore reported as ``128 + N``, as a shell does, while
    ``commands.jsonl`` keeps the raw value and the signal's number.
    """
    killed = record.get("killed_by_signal")
    if killed:
        return 128 + int(killed)
    code = record.get("exit_code")
    return code if isinstance(code, int) and code >= 0 else 2


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
    skipped_roots: list[dict] = field(default_factory=list)  # registered source roots among them


def _walk(plan: _Plan, base: Path, prefix: str, *, registered: bool = False) -> None:
    """Regular files under ``base``; anything else is listed, never read.

    ``os.scandir`` is used directly so a linked directory is recorded and never
    descended into: a FIFO would block a naive copy or hash, and a link (a
    POSIX symlink, a Windows junction) could take the export outside the
    artefact it names.

    ``registered`` marks what belongs to a source the driver named, so an
    artefact of a registered capsule that was not copied is counted where the
    verdicts are read and not only in the list of special files further down.
    """
    mark = {"registered": True} if registered else {}
    try:
        with os.scandir(base) as it:
            children = sorted(it, key=lambda e: e.name)
    except OSError as exc:
        plan.special.append({"package_path": prefix, "source": str(base),
                             "type": f"unreadable directory ({exc.strerror or exc})", **mark})
        return
    for e in children:
        p = Path(e.path)
        rel = f"{prefix}/{e.name}"
        if _link_like(p):
            plan.special.append({"package_path": rel, "source": str(p), "type": _link_type(p), **mark})
        elif e.is_dir(follow_symlinks=False):
            _walk(plan, p, rel, registered=registered)
        elif e.is_file(follow_symlinks=False):
            plan.files.append((p, rel))
        else:
            plan.special.append({"package_path": rel, "source": str(p),
                                 "type": "special file (FIFO, socket or device)", **mark})


def _refuse_source(src: dict) -> dict | None:
    """Why a recorded source must not be read at all, or ``None`` when it may be.

    The rules ``add_source`` keeps on the write side are proved again here, on
    the read side, because none of them is settled by the writing:

    * a ``sources.json`` written before those rules existed, or by hand, can
      hold a relative path, which is resolved against whatever directory the
      export happens to run in (``$REPO/src`` for every driver) rather than
      against the place the artefact was written;
    * it can hold a ``.`` or ``..`` component, and ``lstat`` resolves the whole
      chain such a spelling hides — the link the rule exists for is then
      followed;
    * the chain above the root can change between ``add-source`` and the
      export (the project's own story is a ``results/`` pointing at another
      disk), and a parent that did not exist at registration was never made
      physical, so the recorded spelling is not where the bytes are.

    In each case the root is named and never read, instead of the export
    copying whatever the chain resolves to today and sealing it under the
    run's own capsule name.
    """
    top, raw = src["kind"], src["path"]
    name = Path(raw).name or str(raw)
    if not Path(raw).is_absolute():
        return {"package_path": f"{top}/{name}", "source": str(raw), "registered": True,
                "type": "a relative path; it would be resolved against the directory the export runs in, so "
                        "the bytes it names are not provably this run's"}
    try:
        refuse_relative_components(raw)
    except ValueError:
        return {"package_path": f"{top}/{name}", "source": str(raw), "registered": True,
                "type": "a path with a '.' or '..' component; it is never resolved, so the link such a "
                        "spelling hides is never followed"}
    through = _link_on_the_way(Path(raw).parent)
    if through is not None:
        return {"package_path": f"{top}/{name}", "source": str(raw), "registered": True,
                "type": f"reached through a {_link_type(through)} at {through}, so the bytes behind it are "
                        "not provably the ones this path names"}
    return None


def _plan_files(attempt_dir: Path) -> _Plan:
    """Everything the attempt directory holds (except its export receipts), then its sources.

    Drivers may add their own folders (for a guest session: ``boot/``,
    ``guest/``, ``host/``); they are exported like the standard ones.
    """
    plan = _Plan()
    for p in sorted(attempt_dir.iterdir()):
        if p.name == "export":
            continue
        if _link_like(p):
            plan.special.append({"package_path": p.name, "source": str(p), "type": _link_type(p)})
        elif p.is_file():
            plan.files.append((p, p.name))
        elif p.is_dir():
            _walk(plan, p, p.name)
        else:
            plan.special.append({"package_path": p.name, "source": str(p),
                                 "type": "special file (FIFO, socket or device)"})
    sources = _read_json(attempt_dir / "sources.json")["sources"] if (attempt_dir / "sources.json").is_file() else []
    taken: set[str] = set()
    for idx, src in enumerate(sources, start=1):
        path = Path(src["path"])
        top = src["kind"]
        role = src.get("role", "")
        refused = _refuse_source(src)
        if refused is not None:
            plan.special.append(refused)
            plan.skipped_roots.append({**refused, "kind": top, "role": role})
            continue
        entries = [path]
        if src.get("siblings_glob"):
            parent = path.parent
            if parent.is_dir():
                entries += sorted(
                    p for p in parent.iterdir()
                    if p != path and fnmatch.fnmatchcase(p.name, src["siblings_glob"])
                )
        # ``lexists``: a link that resolves to nothing is still a link, so it
        # belongs in the list of entries that are named but never read — and
        # the artefact it names does not exist either, so it is missing too.
        if not os.path.lexists(path):
            plan.missing.append({"kind": top, "path": str(path), "role": src.get("role", "")})
            entries = entries[1:]
        elif not os.path.exists(path):
            plan.missing.append({"kind": top, "path": str(path), "role": src.get("role", ""),
                                 "note": "is a link that resolves to nothing, so the artefact it names was "
                                         "never written (or no longer exists)"})
        for entry in entries:
            # Two sources with the same name (two runs called 'r01' in two
            # places) get distinct folders instead of making the export fail.
            name = entry.name
            if f"{top}/{name}".casefold() in taken:
                name = f"source{idx:02d}-{entry.name}"
            taken.add(f"{top}/{name}".casefold())
            rel = f"{top}/{name}"
            skipped: dict | None = None
            if _link_like(entry):
                skipped = {"package_path": rel, "source": str(entry), "type": _link_type(entry),
                           "registered": True}
            elif entry.is_dir():
                _walk(plan, entry, rel, registered=True)
            elif entry.is_file():
                plan.files.append((entry, rel))
            else:
                skipped = {"package_path": rel, "source": str(entry),
                           "type": "special file (FIFO, socket or device)", "registered": True}
            if skipped is not None:
                plan.special.append(skipped)
                if entry == path:
                    # A registered root that is skipped means the artefact the
                    # driver named is NOT in this package: the verdicts must
                    # say so, not only the list of special files.
                    plan.skipped_roots.append({**skipped, "kind": top, "role": role})
    # Windows paths are case-insensitive: two names that differ only by case
    # would land on one file there, so the plan is refused instead. A planned
    # file called like one this export generates is refused for the same
    # reason: the copy would be scanned, verified and recorded in the manifest
    # with its own SHA-256, and then replaced in place by the generated file,
    # leaving the manifest asserting a hash no file in the package has and the
    # operator's bytes gone with nothing saying they were dropped.
    seen: dict[str, str] = {}
    generated = {name.casefold() for name in GENERATED_FILES}
    planned = {rel.casefold() for _src, rel in plan.files}
    for _src, rel in plan.files:
        key = rel.casefold()
        if key in seen:
            raise ExportError(f"two artefacts map to the same package path on Windows: {seen[key]!r} and {rel!r}")
        seen[key] = rel
        base = key[: -len(SANITIZED_SUFFIX)] if key.endswith(SANITIZED_SUFFIX) else ""
        if key in generated or (base and base in planned):
            generates = f" for {rel[: -len(SANITIZED_SUFFIX)]!r}" if base else ""
            raise ExportError(f"an artefact of this attempt is called {rel!r}, which is the name this export "
                              f"generates{generates}; move or rename it, so it is never sealed under a "
                              "SHA-256 that belongs to the file it replaced")
    return plan


def _glob_match(path: str, pattern: str) -> bool:
    """Shell-style match where ``*`` and ``?`` never cross a ``/``."""
    rx = "".join("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c) for c in pattern)
    return re.fullmatch(rx, path) is not None


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
    if not str(dest_root).strip():
        raise ExportError("no destination root given")
    attempt_dir = Path(attempt_dir)
    dest = _Destination(dest_root)
    secrets = secrets or {}
    copier = copier or _copy_verified
    attempt = _read_json(attempt_dir / "attempt.json")
    run_id = attempt["run_id"]
    if not (_RUN_ID.match(run_id) or _HIST_ID.match(run_id)):
        raise ExportError(f"run id {run_id!r} is not a valid export identity")
    # Nothing is created before the root's own names and both package paths are
    # proved to be where they look like they are.
    dest.check_owned_top()
    final = dest.check(dest.root / "runs" / run_date(run_id, attempt) / run_id, leaf_may_be_file=False)
    staging = dest.check(dest.root / "incomplete" / run_id, leaf_may_be_file=False)
    receipt_path = attempt_dir / "export" / "receipt.json"

    if os.path.lexists(final):
        # ``verify_sha256sums`` follows a link and never sees a linked folder
        # as a file, so a link planted in a finalised package would be neither
        # listed nor reported: the walker refuses the package instead.
        dest.walk(final)
        problems = verify_sha256sums(final)
        if not problems and (final / "export_manifest.json").is_file():
            manifest = _read_json(final / "export_manifest.json")
            if manifest.get("run_id") == run_id:
                stale = _stale_against(manifest, attempt_dir)
                if stale:
                    raise ExportError(
                        f"a package of this attempt was finalised from an earlier state ({len(stale)} "
                        f"difference(s): {'; '.join(stale[:5])}); the current state was NOT exported and the "
                        "package is never replaced")
                # The receipt is (re)written here too: an export whose index
                # rebuild failed after finalisation would otherwise keep a
                # 'failed' receipt for ever and be re-exported on every run.
                # It is written after the rebuild, so it carries what the
                # destination's record does or does not say about the package.
                index_note = _rebuild_index_quietly(dest)
                _write_receipt(receipt_path, "complete", final, manifest, index_note=index_note)
                return {**manifest, "note": "already exported; the package verifies",
                        **({"index_note": index_note} if index_note else {})}
        raise ExportError(f"{final} already exists and does not verify as this attempt's package: {problems[:3]}")

    if attempt.get("status") == "running":
        raise ExportError("the attempt is still marked running; finish it (or recover it) first")

    try:
        return _export(attempt, attempt_dir, dest, final, staging, receipt_path, secrets, copier)
    except OSError as exc:
        # Disk full, access denied, a vanished file, a rename blocked by a
        # Windows handle: the partial package stays visible and is indexed.
        _write_receipt(receipt_path, "failed", staging, {"copy_verification": f"failed: {exc}"})
        _rebuild_index_quietly(dest)
        raise ExportError(f"export interrupted by an operating-system error: {exc}; the partial package stays in "
                          f"{staging} and a later export resumes it") from exc


def _rebuild_index_quietly(dest: _Destination) -> str:
    """Rebuild the index; return why it could not be, instead of raising.

    The index is derived from the packages on disk, so it can always be rebuilt
    later (``local_export index``). A failure here must never rewrite the state
    of an export that already finished: a package finalised and sealed stays
    finalised and sealed whether or not ``INDEX.md`` could be written.

    The note names the file that failed, which is not always ``INDEX.md``: a
    warning about the file that *was* written would send the operator to look
    at the wrong one.
    """
    try:
        rebuild_index(dest)
    except (ExportError, OSError) as exc:
        name = getattr(exc, "file", "INDEX.md")
        return f"{name} could not be rebuilt ({exc}); run 'local_export index --dest-root ...' once it can be"
    return ""


def _stale_against(manifest: dict, attempt_dir: Path) -> list[str]:
    """Every difference between what the attempt holds now and what the package holds.

    The package is compared with the plan this export would make of the attempt
    today, not with three file names. Three names cannot see a capsule that has
    grown under a registered source, a console file appended after the seal, a
    folder that has since become a link, or an artefact removed from the
    attempt — and ``backfill.sh`` is built to be re-run over capsules that are
    explicitly still growing. Every planned file is compared by SHA-256 with
    the one the manifest recorded, both sets of paths are compared, and so are
    the entries the plan refuses or cannot read, because those decide the
    package's own completeness verdict.

    A file the secret scan kept out has no recorded SHA-256, so it is compared
    by presence alone; that is noted where the caller reports the gate.
    """
    recorded = {f["package_path"]: f["sha256"] for f in manifest.get("files", [])}
    excluded = {str(e.get("package_path")) for e in manifest.get("excluded") or []}
    plan = _plan_files(attempt_dir)
    changed: list[str] = []
    planned: set[str] = set()
    for src, rel in plan.files:
        planned.add(rel)
        if rel in excluded:
            continue
        if rel not in recorded:
            changed.append(f"{rel} is in the attempt and not in the package")
            continue
        try:
            digest = sha256_file(src)
        except OSError as exc:
            changed.append(f"{rel} can no longer be read ({exc.strerror or exc})")
            continue
        if digest != recorded[rel]:
            changed.append(rel)
    changed += [f"{rel} is in the package and no longer in the attempt"
                for rel in sorted(recorded) if rel not in planned]
    sealed = {str(s.get("package_path")) for s in manifest.get("skipped_special") or []}
    changed += [f"{rel} is refused or unreadable now and was not when the package was sealed"
                for rel in sorted({s["package_path"] for s in plan.special} - sealed)]
    return changed


def _reconcile_capture(attempt: dict, attempt_dir: Path, commands: list[dict],
                       console: _ConsoleDir) -> tuple[dict, str]:
    """Bring the attempt to the capture verdict the export computes, before it is packaged.

    The export is the last gate before the evidence leaves WSL and the only
    place that knows both verdicts: the one stored in ``attempt.json`` and the
    one :func:`apply_capture_verdict` computes from the three sources read
    here. An attempt whose file was written by something other than
    :func:`update_attempt`, or closed while ``console/`` could not be listed,
    would otherwise be packaged with a ``valid`` it no longer deserves while
    ``SUMMARY.md`` on the same page says the capture was incomplete.

    The whole verdict is compared, never the list of failed streams alone: the
    union is monotone, so a stored list that is already right is the ordinary
    case, and an attempt whose *validity* was never downgraded beside it is
    exactly what a driver, a recovery by hand or an older tool leaves behind.
    The downgrade goes through the ordinary update path, so it is recorded
    with its note, and it happens before the files are planned and copied, so
    ``attempt.json``, ``SUMMARY.md`` and ``INDEX.md`` say the same thing.
    """
    verdict = apply_capture_verdict(attempt, commands, console)
    if verdict == attempt:
        return attempt, ""
    try:
        return update_attempt(attempt_dir, {}), ""
    except (OSError, ValueError) as exc:
        # A read-only attempt directory must not stop the export: the package
        # is still written, it carries the verdict this export computed, and
        # it says which of the two the packaged attempt.json holds.
        return verdict, (f"attempt.json could not be brought to this export's capture verdict ({exc}); the "
                         "verdict in this manifest and in SUMMARY.md is the union of the three sources, and "
                         "the one inside the packaged attempt.json is the older, weaker one")


def _export(attempt, attempt_dir, dest, final, staging, receipt_path, secrets, copier) -> dict:
    run_id = attempt["run_id"]
    commands = _read_commands(attempt_dir)
    console = _console_inventory(attempt_dir)
    attempt, reconciled = _reconcile_capture(attempt, attempt_dir, commands, console)
    plan = _plan_files(attempt_dir)
    dest.make_dir(staging)
    files, excluded, sanitized, failed = [], [], [], []
    for src, rel in plan.files:
        found = _scan(src, secrets)
        if found:
            entry = {"source": str(src), "package_path": rel, "contains": sorted(found)}
            if _is_text(src) and "PRIVATE-KEY" not in found:
                text = redact_text(src.read_text(encoding="utf-8", errors="replace"), secrets)
                srel = rel + SANITIZED_SUFFIX
                dest.write_text(staging / srel, text)
                entry["sanitized_derivative"] = srel
                sanitized.append(srel)
            excluded.append(entry)
            stale = dest.check(staging / rel)
            if stale.is_file():
                stale.unlink()
            continue
        state, digest = copier(src, dest.make_file(staging / rel, ".partial"))
        item = {"source": str(src), "package_path": rel, "size": src.stat().st_size, "sha256": digest, "state": state}
        files.append(item)
        if state != "verified":
            failed.append(rel)

    # A resumed export may find files of an earlier, different plan in the
    # staging folder (never in a finalised package): they must not be sealed.
    # The partial copies of a failed attempt are kept for inspection.
    keep = {f["package_path"] for f in files} | set(sanitized) | {"export_manifest.json", "SUMMARY.md"}
    for p, is_dir in dest.walk(staging):
        rel = p.relative_to(staging).as_posix()
        if not is_dir and rel not in keep and not (failed and rel.endswith(".partial")):
            dest.unlink(p)
        elif is_dir and not any(p.iterdir()):
            dest.rmdir(p)

    copied = {f["package_path"] for f in files}
    expected_missing = [exp for exp in (attempt.get("expected_artefacts") or [])
                        if not any(_glob_match(p, exp) for p in copied)]
    root_paths = {s["package_path"] for s in plan.skipped_roots}
    # Everything the attempt holds that this package does not. The registered
    # roots are counted on their own, so what is left is split only so the
    # counts can be read — never so that one of the two may be left out of the
    # verdict. One half is an artefact a level below a registered root (the
    # reconciliation file a slice's verdict came from, an events.jsonl inside
    # the capsule); the other is an entry of the attempt directory itself: a
    # ``commands.jsonl`` left as a link when it was moved off a full disk, a
    # session's ``guest/`` left root-owned by its ``sudo`` step, a folder that
    # could not be listed. The rule is the one ``console/`` was given: anything
    # the export refused or could not read inside the attempt is evidence the
    # package does not hold, whatever it is called.
    not_copied = [s for s in plan.special if s["package_path"] not in root_paths]
    registered_artefacts = [s for s in not_copied if s.get("registered")]
    attempt_entries = [s for s in not_copied if not s.get("registered")]
    # A registered root that was never written is counted here too: a package
    # sealed without its capsule is a package sealed without its capsule,
    # whether the capsule was refused or never existed, and a reader who has
    # only ``copy_verification`` must never see a plain ``verified`` for one.
    incomplete = (len(plan.skipped_roots) + len(not_copied) + len(expected_missing)
                  + len(plan.missing))
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
        "skipped_source_roots": plan.skipped_roots,
        "skipped_registered_artefacts": registered_artefacts,
        "skipped_attempt_entries": attempt_entries,
        "expected_artefacts_missing": expected_missing,
        "capture_failures": capture_failures(attempt, commands, console),
        "console_extra_files": console_extras(commands, console),
        "capture_reconciliation": reconciled,
        "excluded": excluded,
        "sanitized_derivatives": sanitized,
        "copy_verification": "failed" if failed else ("verified" if not incomplete else "verified; incomplete"),
        "package_completeness": "complete" if not incomplete else (
            f"incomplete: {len(plan.skipped_roots)} registered source root(s), {len(registered_artefacts)} "
            f"registered artefact(s) below one, {len(attempt_entries)} file(s) or folder(s) of the attempt "
            f"itself, {len(plan.missing)} registered artefact(s) that were never written and "
            f"{len(expected_missing)} declared expected artefact(s) are NOT in this package"),
        "failed_copies": failed,
        "secret_scan": {
            "secret_values": sorted(secrets),
            "private_keys": True,
            "note": "values of the listed variables (names only) and PEM private keys were searched in every file"
                    if secrets else "NO env file was given: only PEM private keys were searched",
        },
    }
    manifest = json.loads(redact_text(json.dumps(manifest, ensure_ascii=False), secrets))
    dest.write_json(staging / "export_manifest.json", manifest)
    if failed:
        _write_receipt(receipt_path, "failed", staging, manifest)
        _rebuild_index_quietly(dest)
        raise ExportError(f"{len(failed)} file(s) did not verify after copying: {failed[:5]}; the package stays in {staging}")

    # The summary is rendered from redacted copies: a secret that reached an
    # attempt field (a reason, a workload note) must not reach Windows.
    attempt_r = json.loads(redact_text(json.dumps(attempt, ensure_ascii=False), secrets))
    commands_r = [json.loads(redact_text(json.dumps(c, ensure_ascii=False), secrets)) for c in commands]
    dest.write_text(staging / "SUMMARY.md", render_summary(attempt_r, manifest, commands_r, console))
    hits = _scan_package_for_secrets(staging, secrets)
    if hits:
        for name in hits:
            dest.unlink(staging / name)
        _write_receipt(receipt_path, "failed", staging, manifest)
        _rebuild_index_quietly(dest)
        raise ExportError(f"generated file(s) {hits} still held a secret value and were removed; not finalised")
    sums = dest.make_file(staging / "SHA256SUMS")
    if sums.is_file():
        # ``write_sha256sums`` opens it in place, so an earlier one is removed
        # first and the seal is always written to a file of this export's own.
        dest.unlink(sums)
    write_sha256sums(staging)
    problems = verify_sha256sums(staging)
    listed = {ln[66:] for ln in (staging / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if len(ln) > 66}
    unlisted = [f["package_path"] for f in files if f["package_path"] not in listed]
    if problems or unlisted:
        _write_receipt(receipt_path, "failed", staging, manifest)
        _rebuild_index_quietly(dest)
        raise ExportError(f"the package's SHA256SUMS does not verify ({problems[:3]}) or misses copied files "
                          f"({unlisted[:3]}); not finalised")
    dest.make_dir(final.parent)
    dest.check(final, leaf_may_be_file=False)
    if os.path.lexists(final):
        raise ExportError(f"{final} appeared while this export ran; the package is never replaced")
    os.replace(staging, final)
    manifest["destination"]["windows_path"] = _wsl_to_windows(final.resolve())
    # The package is finalised and sealed: an index that cannot be rebuilt is
    # reported beside it and never turns it back into a failure. The receipt
    # is written afterwards and carries that note, because a package the
    # record does not name is not fully exported and the driver that reads the
    # receipt must not say it is.
    index_note = _rebuild_index_quietly(dest)
    _write_receipt(receipt_path, "complete", final, manifest, index_note=index_note)
    return {**manifest, "index_note": index_note} if index_note else manifest


def _scan_package_for_secrets(package: Path, secrets: dict[str, bytes]) -> list[str]:
    hits = []
    for name in ("SUMMARY.md", "export_manifest.json"):
        p = package / name
        if p.is_file() and _scan(p, secrets):
            hits.append(name)
    return hits


def package_state(state: str, manifest: dict, index_note: str = "", gone: str = "") -> str:
    """The one field that says what this export left in the destination.

    A reader with only this field — ``tools/session/driver_status.py`` reads
    ``package_state`` out of ``export/receipt.json`` — must never see
    ``verified`` for a package that is not one. It reads ``verified`` only for
    a package that was finalised and sealed, holds everything the attempt
    named and is listed in the destination's index; anything missing is named
    after the semicolon, and a package that is not there says so first.
    """
    if gone:
        return f"not in the destination: {gone}"
    if state != "complete":
        return f"not exported: {manifest.get('copy_verification') or 'the export did not finish'}"
    bits = []
    completeness = manifest.get("package_completeness") or ""
    if completeness and completeness != "complete":
        bits.append(completeness)
    if index_note:
        # ``INDEX.md`` is the record. When it was written and only a file
        # beside it failed, the package IS named by the record, and saying it
        # is not would send the operator looking for a row that is there.
        # ``_write_together`` already draws that distinction; it only has to
        # reach this field, which stays away from a plain ``verified`` either way.
        named = INDEX_WAS_WRITTEN in index_note
        bits.append(f"the destination's index names it; {index_note}" if named
                    else f"not named in the destination's index: {index_note}")
    return "; ".join(["verified", *bits])


def _write_receipt(path: Path, state: str, where: Path, manifest: dict, *,
                   index_note: str = "", gone: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, {
        "state": state,
        "package": str(where),
        "written_utc": utc_now(),
        "package_state": package_state(state, manifest, index_note, gone),
        "copy_verification": manifest.get("copy_verification"),
        "package_completeness": manifest.get("package_completeness"),
        "index_note": index_note,
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


def _exit_cell(command: dict) -> str:
    """The exit code of one command, saying so when a signal ended it."""
    killed = command.get("killed_by_signal")
    if killed:
        return f"{command.get('exit_code')} (killed by {signal_name(int(killed))})"
    return str(command.get("exit_code"))


def _capture_cell(command: dict, failures: dict | None = None, excluded: dict | None = None) -> str:
    """The console-capture state of one command, as the commands table shows it.

    ``failures`` is the whole attempt's union keyed by console path, so a
    stream the export found truncated or gone is shown here too and not only
    in the result table; ``excluded`` names the console files a secret kept
    out of the package, which is not a loss of evidence on the WSL side but
    must never read as "kept" either.
    """
    capture = command.get("capture")
    failures, excluded = failures or {}, excluded or {}
    if not capture:
        return "not recorded"
    streams = {s: (capture.get(s) or {}) for s in ("stdout", "stderr")}
    failed = [f"{s} **INCOMPLETE**: {_bytes_cell(c.get('bytes_kept'))} of {_bytes_cell(c.get('bytes_received'))} "
              f"bytes kept ({c.get('error') or 'no reason recorded'})"
              for s, c in streams.items() if c.get("state") == "failed"]
    failed += [f"{s} **INCOMPLETE**: {failures[command[s]]['error']}"
               for s in ("stdout", "stderr")
               if command.get(s) in failures and streams[s].get("state") != "failed"]
    if capture.get("not_persisted"):
        failed.append(f"the loss could not be written to attempt.json ({capture['not_persisted']})")
    if failed:
        return "; ".join(failed)
    notes = [f"{s} echo failed" for s, c in streams.items() if str(c.get("echo", "")).startswith("failed")]
    kept_out = [s for s in ("stdout", "stderr") if command.get(s) in excluded]
    if kept_out:
        return (f"complete ({', '.join(kept_out)} excluded for secrets; the package holds the redacted copy)"
                + (f" (terminal only: {', '.join(notes)})" if notes else ""))
    return "complete" + (f" (terminal only: {', '.join(notes)})" if notes else "")


def _bytes_cell(value) -> str:
    return "an unknown number of" if value is None else str(value)


def _failure_phrase(f: dict) -> str:
    """One capture failure, as the result table names it."""
    seq, stream = f.get("seq"), f.get("stream")
    if not seq and stream in (None, "", "unknown"):
        # A console file or directory nothing could account for: there is no
        # command and no stream to name, so it is named by what it is.
        return f"`{f.get('console') or f.get('name') or '?'}` ({f.get('error') or 'no reason recorded'})"
    where = f" ({f['console']})" if f.get("console") else ""
    # Nothing was measured about a stream whose file the export refused or
    # could not read, so the cell says the number is unknown instead of
    # reading as a measurement of it.
    kept = f.get("bytes_kept")
    measured = (f"{kept} of {_bytes_cell(f.get('bytes_received'))} bytes kept" if kept is not None
                else f"how much of {_bytes_cell(f.get('bytes_received'))} bytes was kept is unknown")
    return (f"{stream or '?'} of {f.get('name') or '?'} (command {seq if seq else '?'}"
            f"{where}, {measured})")


def _excluded_console(excluded: Iterable[dict]) -> list[dict]:
    """The console files a secret value kept out of the package."""
    return [e for e in excluded if str(e.get("package_path", "")).startswith("console/")]


def _capture_verdict(attempt: dict, commands: list[dict],
                     console: _ConsoleDir | dict[str, int] | None = None,
                     excluded: Iterable[dict] = ()) -> str:
    """The console-capture state of the whole attempt, as the result table shows it.

    The verdict is the union of everything that says a stream was not kept:
    the attempt's list, the records, the console files nothing accounted for
    and the recorded files that are no longer there or no longer hold what
    their record claims. One source going silent can never make the verdict
    read complete, and a console file the secret scan kept out of the package
    is never called "kept in full" here either.
    """
    failures = capture_failures(attempt, commands, console)
    kept_out = _excluded_console(excluded)
    aside = ""
    if kept_out:
        names = ", ".join(f"`{e['package_path']}`" for e in kept_out)
        aside = (f". Separately, {len(kept_out)} console file(s) hold a secret value and are NOT in this "
                 f"package: {names}; the capture of them succeeded on the WSL side, where the originals stay, "
                 "and this package holds a redacted copy where one could be written")
    if failures:
        streams = ", ".join(_failure_phrase(f) for f in failures)
        return (f"**INCOMPLETE** — {len(failures)} console stream(s) were not kept in full: {streams}. "
                "The command's own exit code is still the one recorded; this is a loss of evidence, not its "
                f"result{aside}")
    if not commands:
        return "not applicable — no command was run through this attempt"
    unrecorded = [c for c in commands if not c.get("capture")]
    if unrecorded:
        # Silence is not evidence that everything was kept — and it is not
        # evidence of its own cause either. A record written before this tool
        # kept capture state, one truncated on append, one written by hand and
        # one written by a foreign tool all look alike here, so the cell states
        # what was measured and nothing more.
        return (f"**not recorded** for {len(unrecorded)} of {len(commands)} command record(s): they say "
                f"nothing about whether their console files kept everything{aside}")
    if kept_out:
        return f"**complete on the WSL side** — every command's stdout and stderr were kept in full{aside}"
    return "**complete** — every command's stdout and stderr were kept in full"


def _copy_cell(manifest: dict) -> str:
    """The copy verdict, with everything that is NOT in the package beside it."""
    skipped = manifest.get("skipped_source_roots") or []
    artefacts = manifest.get("skipped_registered_artefacts") or []
    entries = manifest.get("skipped_attempt_entries") or []
    expected = manifest.get("expected_artefacts_missing") or []
    text = (f"**{manifest.get('copy_verification')}** — {len(manifest.get('files', []))} file(s) copied and "
            f"verified by SHA-256; {len(manifest.get('excluded', []))} excluded for secrets; "
            f"{len(manifest.get('missing_sources', []))} expected source(s) missing")
    if skipped:
        names = ", ".join(f"`{s['package_path']}` ({s['type']})" for s in skipped)
        text += (f"; {len(skipped)} registered source root(s) skipped and NOT in this package: {names}")
    if artefacts:
        names = ", ".join(f"`{s['package_path']}` ({s['type']})" for s in artefacts)
        text += (f"; {len(artefacts)} registered artefact(s) below a source root NOT in this package: {names}")
    if entries:
        names = ", ".join(f"`{s['package_path']}` ({s['type']})" for s in entries)
        text += (f"; {len(entries)} file(s) or folder(s) the attempt itself holds, which this export refused "
                 f"or could not read, NOT in this package: {names}")
    if expected:
        names = ", ".join(f"`{e}`" for e in expected)
        text += (f"; {len(expected)} declared expected artefact(s) matched nothing that was copied: {names}")
    return text


def _output_cell(command: dict, present: set[str], excluded: dict[str, dict]) -> str:
    """The commands table's links, which never point at a file the package lacks.

    A console file the secret scan excluded, or one that is no longer in the
    attempt, is not in this package: a link to it would promise the reader
    evidence they cannot open, so the cell says what became of it instead and
    links the redacted copy when there is one.
    """
    cells = []
    for stream in ("stdout", "stderr"):
        rel = command.get(stream)
        if not rel:
            cells.append(f"{stream}: not recorded")
        elif rel in present:
            cells.append(f"[{stream}]({rel})")
        elif (excluded.get(rel) or {}).get("sanitized_derivative"):
            cells.append(f"[{stream}, redacted]({excluded[rel]['sanitized_derivative']}) "
                         "(the original holds a secret value and stays on the WSL side)")
        elif rel in excluded:
            cells.append(f"{stream}: excluded for secrets, not in this package")
        else:
            cells.append(f"{stream}: not in this package")
    return " · ".join(cells)


def render_summary(attempt: dict, manifest: dict, commands: list[dict],
                   console: _ConsoleDir | dict[str, int] | None = None) -> str:
    excluded = {e["package_path"]: e for e in manifest.get("excluded") or []}
    present = {f["package_path"] for f in manifest.get("files") or []} | set(
        manifest.get("sanitized_derivatives") or [])
    failures = capture_failures(attempt, commands, console)
    by_console = {f["console"]: f for f in failures if f.get("console")}
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
        "system under test did, and whether this copy is intact. The console capture is part of "
        "the first: evidence that was not kept in full cannot make an attempt valid.",
        "",
        "| Verdict | Value |",
        "|---|---|",
        f"| Instrumentation validity | **{_cell(attempt.get('instrumentation_validity'))}** |",
        f"| Validity note | {_cell(attempt.get('validity_note'))} |",
        f"| System outcome | **{_cell(attempt.get('system_outcome'))}** |",
        f"| Console capture | {_cell(_capture_verdict(attempt, commands, console, excluded.values()))} |",
        f"| Copy verification | {_copy_cell(manifest)} |",
        f"| Secret scan | {_cell((manifest.get('secret_scan') or {}).get('note', 'not recorded'))} |",
        f"| Reason | {_cell(attempt.get('reason'))} |",
        f"| Next action | {_cell(attempt.get('next_action'))} |",
        "",
    ]
    if commands:
        lines += ["## Commands", "",
                  "| # | Name | Exit code | Duration (s) | Console capture | Output |",
                  "|---|---|---|---|---|---|"]
        for c in commands:
            lines.append(f"| {c['seq']} | {_cell(c['name'])} | {_exit_cell(c)} | {c['duration_s']} | "
                         f"{_cell(_capture_cell(c, by_console, excluded))} | "
                         f"{_cell(_output_cell(c, present, excluded))} |")
        # The table is rendered from the records, which are read through
        # whatever ``commands.jsonl`` is; the file itself reaches the package
        # only when the planner copied it, so the sentence names what the
        # reader can actually open here.
        if "commands.jsonl" in present:
            argv = "The full, sanitised argv of each command is in `commands.jsonl`."
        elif (excluded.get("commands.jsonl") or {}).get("sanitized_derivative"):
            argv = (f"`commands.jsonl` holds a secret value and is not in this package; the redacted copy "
                    f"`{excluded['commands.jsonl']['sanitized_derivative']}` carries each command's argv.")
        else:
            argv = ("`commands.jsonl` is **NOT in this package**: the table above is everything this package "
                    "says about each command's argv. See the copy verdict.")
        lines += ["", argv, ""]
    if manifest.get("capture_reconciliation"):
        lines += ["## The attempt's own verdict could not be updated", "",
                  manifest["capture_reconciliation"] + ".", ""]
    extras = manifest.get("console_extra_files") or []
    if extras:
        lines += ["## Files in console/ this export did not write", "",
                  "`exec` names every console file `<NNN>-<name>.<stream>.txt`. These do not follow that name "
                  "and no record in `commands.jsonl` names them, so something other than this export put them "
                  "there. They are copied with the rest of the package, unless the secret scan excluded one; "
                  "none of them is a lost console stream and none of them downgrades a verdict.", ""]
        lines += [f"- `{e['console']}`: {e['bytes']} byte(s)" for e in extras]
        lines.append("")
    unaccounted = [f for f in failures if f.get("unaccounted")]
    if unaccounted:
        lines += ["## Console output nobody accounted for", "",
                  "These console files exist in this package and no record in `commands.jsonl` names them: the "
                  "command was interrupted, or its record could never be appended. What they hold is a part of "
                  "the output, never provably all of it.", ""]
        lines += [f"- `{f['console']}`: {f['bytes_kept']} byte(s) kept, no command record" for f in unaccounted]
        lines.append("")
    if manifest.get("missing_sources"):
        lines += ["## Missing artefacts", ""]
        lines += [f"- `{m['kind']}` {m.get('role') or ''}: `{m['path']}` "
                  f"{m.get('note') or 'did not exist at export time'}"
                  for m in manifest["missing_sources"]]
        lines.append("")
    if attempt.get("expected_artefacts"):
        copied = {f["package_path"] for f in manifest.get("files", [])}
        missing = manifest.get("expected_artefacts_missing")
        if missing is None:
            missing = [e for e in attempt["expected_artefacts"] if not any(_glob_match(p, e) for p in copied)]
        lines += ["## Expected artefacts", ""]
        for exp in attempt["expected_artefacts"]:
            lines.append(f"- `{exp}`: {'**missing**' if exp in missing else 'present'}")
        lines.append("")
    if manifest.get("skipped_special"):
        lines += ["## Not copied: special files", ""]
        # "never read" is a refusal this export made; for an entry it could not
        # read it would state the opposite of what happened.
        lines += [f"- `{s['package_path']}`: {s['type']}; "
                  + ("it could not be read" if str(s["type"]).startswith("unreadable")
                     else "listed here, never read")
                  for s in manifest["skipped_special"]]
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


def _package_dirs(base: Path, depth: int) -> list[tuple[Path, bool]]:
    """Package folders under ``base`` as ``(path, refused)``.

    A link is never descended into and never read, but it is returned so the
    index can show it: an entry that cannot be trusted is listed as refused,
    never quietly left out.
    """
    if _link_like(base) or not base.is_dir():
        return []
    found: list[tuple[Path, bool]] = []
    with os.scandir(base) as it:
        for e in sorted(it, key=lambda e: e.name):
            p = Path(e.path)
            if _link_like(p):
                found.append((p, True))
            elif not e.is_dir(follow_symlinks=False):
                continue
            elif depth > 1:
                found += _package_dirs(p, depth - 1)
            else:
                found.append((p, False))
    return found


def _package_rows(dest: _Destination) -> list[dict]:
    rows = []
    for state, base in (("final", dest.root / "runs"), ("incomplete", dest.root / "incomplete")):
        if _link_like(base):
            rows.append(_refused_row(base, dest, state))
            continue
        for d, refused in _package_dirs(base, 2 if state == "final" else 1):
            if refused:
                rows.append(_refused_row(d, dest, state))
                continue
            try:
                # The same walker the export uses: a link planted anywhere
                # inside a package makes the whole package untrustworthy, and
                # reading a verdict through one would publish, inside the
                # index, a value that came from outside the export root.
                dest.walk(d)
            except (UnsafePathError, OSError) as exc:
                rows.append(_refused_row(d, dest, state, why=str(exc),
                                         copy=getattr(exc, "refused_as", "REFUSED: link")))
                continue
            # attempt.json may have been excluded for a secret: its redacted
            # derivative then carries the verdicts.
            a = d / "attempt.json"
            if not a.is_file():
                a = d / "attempt.json.sanitized"
            try:
                attempt = _read_json(a) if a.is_file() else {"run_id": d.name}
            except (OSError, json.JSONDecodeError):
                attempt = {"run_id": d.name}
            m = d / "export_manifest.json"
            try:
                manifest = _read_json(m) if m.is_file() else {}
            except (OSError, json.JSONDecodeError):
                manifest = {}
            copy = manifest.get("copy_verification", "not verified") if state == "final" else "INCOMPLETE"
            for count, what in (
                (len(manifest.get("skipped_source_roots") or []), "source root(s) skipped"),
                (len(manifest.get("skipped_registered_artefacts") or []), "registered artefact(s) not copied"),
                (len(manifest.get("skipped_attempt_entries") or []),
                 "file(s) or folder(s) of the attempt not copied"),
                (len(manifest.get("expected_artefacts_missing") or []), "expected artefact(s) missing"),
                (len(manifest.get("missing_sources") or []), "registered artefact(s) never written"),
            ):
                if count:
                    copy = f"{copy}; {count} {what}"
            stored = attempt.get("instrumentation_validity", "unknown")
            # The same rule that decides the attempt's own verdict, applied to
            # the failures the package's manifest records: the row cannot say
            # something the package it points at does not.
            row = {"instrumentation_validity": stored, "capture_failures": manifest.get("capture_failures") or []}
            _downgrade_on_capture_failure(row)
            validity = row["instrumentation_validity"]
            if validity != stored:
                # The package's own manifest contradicts the verdict stored
                # beside it (an attempt.json written by something other than
                # this tool, or one this export could not rewrite): the loss of
                # evidence wins, and the row says where to read about it.
                validity = f"{validity} (console capture: see SUMMARY.md)"
            rows.append({
                "run_id": attempt.get("run_id", d.name),
                "rel": d.relative_to(dest.root).as_posix(),
                "state": state,
                "scenario": attempt.get("scenario", ""),
                "purpose": attempt.get("purpose", ""),
                "historical": attempt.get("historical", False),
                "validity": validity,
                "outcome": attempt.get("system_outcome", "unknown"),
                "copy": copy,
                "reason": attempt.get("reason", ""),
                "created": attempt.get("created_utc") or attempt.get("date", ""),
            })
    rows.sort(key=lambda r: (str(r["created"]), r["run_id"]))
    return rows


def _refused_row(path: Path, dest: _Destination, state: str, why: str = "",
                 copy: str = "REFUSED: link") -> dict:
    """An index row for an entry the export will not read: named, never read."""
    return {
        "run_id": path.name, "rel": path.relative_to(dest.root).as_posix(), "state": "refused",
        "scenario": "", "purpose": "", "historical": False, "validity": "unknown", "outcome": "unknown",
        "copy": copy,
        "reason": why or f"this {state} entry is a {_link_type(path)}; the export never creates one, so it is "
                         f"listed here and never read",
        "created": "",
    }


def rebuild_index(dest_root: str | Path | _Destination) -> Path:
    """Regenerate INDEX.md and LATEST_SUMMARY.md from the packages themselves.

    The index is derived, so no entry can be lost: every package and every
    incomplete export on disk is listed, including the ones refused as links.
    """
    dest = dest_root if isinstance(dest_root, _Destination) else _Destination(dest_root)
    dest.make_dir(dest.root)
    # All three are proved free of links — and so are the temporary companions
    # they are written through, which a hard link planted at one of them would
    # otherwise tie to a file outside the root — before any of them is
    # written, so a linked name is refused whether or not this particular call
    # would reach it.
    proved = []
    for name in ("INDEX.md", "LATEST_SUMMARY.md", "README.md"):
        try:
            proved.append(dest.make_file(dest.root / name, ".tmp"))
        except (ExportError, OSError) as exc:
            exc.file = name  # so the warning names this file and not always INDEX.md
            raise
    index, latest, readme = proved
    rows = _package_rows(dest)
    # The convenience files are written first and INDEX.md last, so the record
    # can name the ones that could not be replaced.
    pending = []
    finals = [r for r in rows if r["state"] == "final" and not r["historical"]]
    if finals:
        r = finals[-1]
        pending.append((
            latest,
            f"# Latest attempt\n\nA convenience pointer only; [INDEX.md](INDEX.md) is the record.\n\n"
            f"- [{r['run_id']}]({r['rel'].replace(' ', '%20')}/SUMMARY.md): {r['scenario']} — validity "
            f"{r['validity']}, outcome {r['outcome']}, copy {r['copy']}\n",
        ))
    if not os.path.lexists(readme):
        pending.append((readme, README_TEXT))
    _write_together(dest, pending, index, lambda stale: _index_text(rows, stale))
    return index


def _index_text(rows: list[dict], stale: list[str]) -> str:
    """INDEX.md: every package on disk, and any generated file left behind it."""
    out = [
        "# Test attempts — index",
        "",
        f"Regenerated {utc_now()} from the packages on disk. Every attempt is kept; nothing here is replaced.",
        f"QEMU observations are **{EMULATED_LABEL}**.",
        "The Copy column repeats the verdict each package recorded when it was sealed; this rebuild does not "
        "re-check a package's `SHA256SUMS`. `local_export recover` is what re-checks it.",
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
    if stale:
        out += ["**This table is the record.** The file(s) beside it could NOT be rewritten in this rebuild, "
                "so they still describe an earlier state of this folder and must not be read as the newest: "
                + "; ".join(stale) + ". Run `local_export index --dest-root ...` once they can be written.",
                ""]
    return "\n".join(out)


def _write_together(dest: _Destination, pending: list[tuple[Path, str]], index: Path, index_text) -> None:
    """Write the convenience files, then INDEX.md, which names the ones that failed.

    A read-only attribute, a file an editor or a sync client holds open, or a
    full disk makes one write fail while the others succeed, and the generated
    files would then disagree about the newest package. Putting all of them
    back was the round-3 answer and it costs more than it saves:
    ``LATEST_SUMMARY.md`` is a convenience pointer, ``INDEX.md`` is the record,
    and rolling the record back for the pointer's sake leaves every later
    package unlisted for as long as the one lock holds. So the files that can
    be written are written, ``INDEX.md`` is written last and says which of them
    is stale, and the failure is still raised — it reaches the export receipt
    and the operator, and it is never a silent pass. A failure on ``INDEX.md``
    itself is the other way round: the ones already replaced are put back, so
    no generated file names a package the record does not.
    """
    before = [(path, path.read_bytes() if path.is_file() else None) for path, _text in pending]
    written: list[Path] = []
    stale: list[str] = []
    first: tuple[str, BaseException] | None = None
    for path, text in pending:
        try:
            dest.write_text(path, text)
        except (ExportError, OSError) as exc:
            stale.append(f"{path.name} ({exc})")
            first = first or (path.name, exc)
            continue
        written.append(path)
    try:
        dest.write_text(index, index_text(stale))
    except (ExportError, OSError) as exc:
        restored, not_restored = [], []
        for done, data in before:
            if done not in written:
                continue
            try:
                if data is None:
                    dest.unlink(done)
                else:
                    dest.write_bytes(done, data)
                restored.append(done.name)
            except (ExportError, OSError) as undo:
                not_restored.append(f"{done.name} ({undo})")
        raise IndexWriteError(index.name, restored, not_restored, exc) from exc
    if first is not None:
        raise IndexWriteError(first[0], [], [], first[1], also=INDEX_WAS_WRITTEN)


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
here is not published or admitted evidence and not an off-machine backup. A file that
holds the value of a secret variable of the env file given to the export, or a private
key, is not copied: it is listed as excluded, with a redacted derivative. Each summary
states which variables were searched.

The export never creates a shortcut of any kind. A symlink, a junction or another
reparse point on the way to a folder or file listed above is refused, never written
through and never deleted through; so is a hard link, a second name for the same bytes
that no resolved path can tell from an ordinary file. An entry inside this folder that
is one is listed in `INDEX.md` as `REFUSED: link` and never read, and a FIFO, socket or
device planted in a package is listed there as `REFUSED: special file`. A command whose
stdout or stderr could not be kept in full says so in its summary, and so does a console
file that no command record accounts for, one whose record claims more bytes than the
file holds, and a `console/` folder that is a link or could not be read at all: the
command's own exit code stays as it was, and the attempt's instrumentation validity is
downgraded to `invalid` from whatever it was. `Copy` reads `verified; incomplete` when a
registered artefact the attempt named is not in the package, whether it was refused or
never written.

Written by `python -m egw_experiments.local_export` (repository `src/egw_experiments/local_export.py`).
"""


# --------------------------------------------------------------------------
# Recovery and historical backfill
# --------------------------------------------------------------------------


#: The one row of :func:`recover` that is neither a success nor a failure: the
#: attempt is still being driven from another terminal and is left alone until
#: the operator names it with ``--interrupt``.
_RECOVER_RUNNING = "running: not touched"


def recover(
    attempts_root: str | Path,
    dest_root: str | Path,
    *,
    secrets: dict[str, bytes] | None = None,
    interrupt: Iterable[str] = (),
) -> list[dict]:
    """Export every attempt (historical ones included) without a complete export.

    An export counts as complete only while the package its receipt names is
    still in the destination and still verifies against its own
    ``SHA256SUMS``; one that lost files after it was finalised is exported
    again, or, since a package is never replaced, reported as a failure row.

    An attempt still marked running is NOT touched: whether its process is
    alive cannot be told reliably (it may be driven by a shell script from
    another terminal). The operator names the attempts that died with
    ``interrupt``; each is then marked interrupted, keeping any outcome it had
    already recorded, and exported. Every attempt is handled on its own: a
    failure is reported and the loop goes on, and so is a failure of the index
    rebuild at the end. The caller decides what the rows mean;
    :func:`recover_failures` names the ones that are failures.
    """
    interrupt = set(interrupt)
    root = Path(attempts_root)
    candidates = sorted(root.glob("*")) + sorted((root / "_historical").glob("*"))
    results = []
    for attempt_dir in candidates:
        if not (attempt_dir / "attempt.json").is_file():
            continue
        try:
            receipt = attempt_dir / "export" / "receipt.json"
            written = _read_json(receipt) if receipt.is_file() else {}
            complete = written.get("state") == "complete"
            gone = _package_not_there(written.get("package")) if complete else ""
            if complete and not gone:
                continue
            if gone:
                # The receipt claimed a verified package and the destination no
                # longer holds one: the claim is withdrawn before anything else
                # is tried, so a reader of the receipt is never told the
                # evidence is there while this run works out whether it is.
                _write_receipt(receipt, "failed", Path(written.get("package") or attempt_dir), {}, gone=gone)
            attempt = _read_json(attempt_dir / "attempt.json")
            if attempt.get("status") == "running":
                if attempt["run_id"] not in interrupt:
                    results.append({"run_id": attempt["run_id"], "result": f"{_RECOVER_RUNNING} (name it with "
                                    "--interrupt if its process died)"})
                    continue
                commands = _read_commands(attempt_dir)
                updates = {"recovered_utc": utc_now(),
                           "reason": (attempt.get("reason") or "") + " [marked interrupted by the operator through "
                                     "recover]"}
                if attempt.get("system_outcome", "unknown") == "unknown":
                    updates["system_outcome"] = "interrupted"
                update_attempt(attempt_dir, {"status": "interrupted",
                                             "ended_utc": commands[-1]["ended_utc"] if commands else None, **updates})
            export_attempt(attempt_dir, dest_root, secrets=secrets)
            results.append({"run_id": attempt_dir.name,
                            "result": "exported again: the package its receipt named is not in the destination"
                                      if complete else "exported"})
        except (ExportError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            results.append({"run_id": attempt_dir.name, "result": f"export failed: {exc}"})
    try:
        rebuild_index(dest_root)
    except (ExportError, OSError) as exc:
        results.append({"run_id": "INDEX.md", "result": f"index rebuild failed: {exc}"})
    return results


def _package_not_there(package: str | None) -> str:
    """Why the package a complete receipt names is no longer a verified package.

    The empty string means it is there and still verifies. The receipt is
    written on the WSL side and says what this tool did; it can say nothing
    about what happened to the destination afterwards. ``recover`` is the
    remedy the drivers point to for evidence that did not reach
    ``output_test``, so a package that was tidied away, renamed, restored over
    or left holding fewer files than it was sealed with is sent back through
    the export instead of being reported as already there. Its own
    ``SHA256SUMS`` is therefore verified and not merely looked for: a package
    is small, ``recover`` runs once per session, and every other way a package
    stops holding the evidence — a half-finished copy to another machine, a
    sync client that dropped the large files, an operator tidying inside
    ``runs/<date>/<run_id>`` — passes a test that only asks whether the folder
    is there. Re-exporting a package that *is* there is a no-op.
    """
    if not package:
        return "the receipt names no package"
    p = Path(package)
    if not p.is_dir():
        return f"{p} is not in the destination"
    if not (p / "export_manifest.json").is_file():
        return f"{p} holds no export_manifest.json"
    problems = verify_sha256sums(p)
    if problems:
        return f"{p} no longer verifies against its own SHA256SUMS: {problems[:3]}"
    return ""


def recover_failures(results: list[dict]) -> list[dict]:
    """The rows of :func:`recover` that mean nothing reached the destination."""
    return [r for r in results
            if not r["result"].startswith("exported") and not r["result"].startswith(_RECOVER_RUNNING)]


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
    emulated: bool = True,
    secrets: dict[str, bytes] | None = None,
) -> dict:
    """Copy a preserved historical attempt as it is, indexed as historical.

    A name identifies one source: backfilling another source under a name
    already used is refused, never reported as the earlier package.
    """
    date = valid_date(date)
    # Both are refused before anything is created, so a bad source leaves no
    # historical attempt behind. A linked source root would be listed and never
    # read, so the package would be empty and look like a preserved attempt
    # that held nothing.
    refuse_relative_components(source)
    given = Path(source).absolute()
    if _link_like(given):
        raise ExportError(f"the historical source {given} is a {_link_type(given)} to {os.path.realpath(given)}; "
                          f"a link is listed and never read, so backfill it by its physical path")
    run_id = "HIST_" + re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    attempt_dir = Path(attempts_root) / "_historical" / run_id
    if attempt_dir.exists():
        stored = _read_json(attempt_dir / "attempt.json")
        recorded = stored.get("original_identity")
        if recorded != str(Path(source).absolute()) and recorded != str(Path(source).resolve()):
            raise ExportError(f"historical name {run_id!r} is already used for {recorded}; not {source}")
        # A second backfill under the same name carries the same verdict or it
        # carries a corrected one, and a correction that is discarded while the
        # driver reports success is the one outcome this must not have: the
        # published package would go on stating the verdict that was superseded.
        differs = [f"{field}: the historical attempt holds {stored.get(field)!r}, this call gives {value!r}"
                   for field, value in (("scenario", scenario), ("date", date),
                                        ("instrumentation_validity", original_validity),
                                        ("system_outcome", original_outcome), ("reason", note),
                                        ("emulated", emulated))
                   if stored.get(field) != value]
        if differs:
            raise ExportError(
                f"the historical attempt {run_id!r} was recorded with other values and is never rewritten in "
                f"place, so its package is never replaced: {'; '.join(differs)}. Backfill the corrected record "
                f"under another --name, which keeps both what was published and the correction beside it")
    else:
        attempt_dir.mkdir(parents=True)
        for d in ATTEMPT_DIRS:
            (attempt_dir / d).mkdir()
        (attempt_dir / "commands.jsonl").touch()
        _write_json(attempt_dir / "attempt.json", {
            "run_id": run_id, "scenario": scenario, "purpose": "engineering", "emulated": emulated,
            "created_utc": f"{date}T00:00:00.000000Z", "date": date, "status": "finished", "historical": True,
            "original_identity": str(Path(source).resolve()), "instrumentation_validity": original_validity,
            "validity_note": "", "system_outcome": original_outcome, "reason": note, "next_action": "",
            "identities": {}, "workload": {}, "expected_artefacts": [], "capture_failures": [], "seed": None,
            "started_utc": None, "ended_utc": None,
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

    s = sub.add_parser("exec", help="run one command inside an attempt; exits with its code, or "
                                    f"{EXIT_CAPTURE_FAILED} when its console capture failed")
    s.add_argument("--attempt", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--secrets-env", required=True, help="env file whose secret values are redacted from the argv")
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
    s.add_argument("--secrets-env", required=True, help="env file whose secret values are searched for")

    s = sub.add_parser("recover", help="export every attempt without a complete export; exits 2 when any of them "
                                       "could not be exported (an attempt still running is left alone, which is "
                                       "not a failure)")
    s.add_argument("--attempts-root", required=True)
    s.add_argument("--dest-root", required=True)
    s.add_argument("--secrets-env", required=True, help="env file whose secret values are searched for")
    s.add_argument("--interrupt", nargs="*", default=[], metavar="RUN_ID",
                   help="attempts still marked running whose process died: mark them interrupted and export them")

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
    s.add_argument("--not-emulated", action="store_true", help="a host-side record (a build), not a guest observation")
    s.add_argument("--secrets-env", required=True, help="env file whose secret values are searched for")

    s = sub.add_parser("index", help="regenerate INDEX.md from the packages on disk")
    s.add_argument("--dest-root", required=True)

    a = p.parse_args(argv)
    if getattr(a, "dest_root", None) is not None and not a.dest_root.strip():
        p.error("--dest-root must not be empty")
    try:
        if a.command == "new":
            d = new_attempt(a.attempts_root, a.scenario, a.purpose, dest_root=a.dest_root, seed=a.seed,
                            emulated=not a.native)
            print(d)
        elif a.command == "exec":
            cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
            if not cmd:
                p.error("exec needs a command after --")
            rec = run_command_record(a.attempt, a.name, cmd, secrets=load_secrets(a.secrets_env), cwd=a.cwd)
            if capture_failed(rec):
                # The command's own code stays in commands.jsonl; this exit
                # says the evidence is incomplete, which the caller must not
                # read as the command's result.
                print(f"error: the console capture of {a.name!r} failed (the command itself exited "
                      f"{rec['exit_code']}); see capture_failures in attempt.json", file=sys.stderr)
                if (rec.get("capture") or {}).get("not_persisted"):
                    print(f"error: and the loss could not be written to attempt.json: "
                          f"{rec['capture']['not_persisted']}; commands.jsonl keeps the record",
                          file=sys.stderr)
                return EXIT_CAPTURE_FAILED
            if rec.get("killed_by_signal"):
                print(f"error: {a.name!r} was killed by {signal_name(int(rec['killed_by_signal']))}; "
                      f"commands.jsonl records exit_code {rec['exit_code']}", file=sys.stderr)
            return command_exit_status(rec)
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
            clauses = [f"{len(m['files'])} files", f"{len(m['excluded'])} excluded"]
            for count, what in ((len(m.get("skipped_source_roots") or []), "source root(s) skipped"),
                                (len(m.get("skipped_registered_artefacts") or []),
                                 "registered artefact(s) not copied"),
                                (len(m.get("skipped_attempt_entries") or []),
                                 "file(s) or folder(s) of the attempt not copied"),
                                (len(m.get("expected_artefacts_missing") or []),
                                 "expected artefact(s) missing"),
                                (len(m.get("missing_sources") or []),
                                 "registered artefact(s) never written"),
                                (len(m.get("capture_failures") or []), "console stream(s) not kept in full")):
                if count:
                    clauses.append(f"{count} {what}")
            print(f"exported {m['run_id']}: {m['destination']['windows_path']} "
                  f"({m['copy_verification']}, {', '.join(clauses)})")
            if m.get("capture_reconciliation"):
                print(f"warning: {m['capture_reconciliation']}", file=sys.stderr)
            if m.get("index_note"):
                print(f"warning: {m['index_note']}", file=sys.stderr)
        elif a.command == "recover":
            results = recover(a.attempts_root, a.dest_root, secrets=load_secrets(a.secrets_env),
                              interrupt=a.interrupt)
            for r in results:
                print(f"{r['run_id']}: {r['result']}")
            failures = recover_failures(results)
            if failures:
                # The recovery is the remedy for an export that failed, so it
                # cannot report its own failure as a success: a wrapper reading
                # only the status would record the evidence as recovered.
                print(f"error: {len(failures)} of {len(results)} attempt(s) were not exported; nothing was "
                      f"written to the destination for them", file=sys.stderr)
                return 2
        elif a.command == "backfill":
            m = backfill(a.source, a.attempts_root, a.dest_root, name=a.name, scenario=a.scenario, date=a.date,
                         note=a.note, original_validity=a.validity, original_outcome=a.outcome,
                         emulated=not a.not_emulated, secrets=load_secrets(a.secrets_env))
            print(f"backfilled {m['run_id']}: {m['destination']['windows_path']} ({m['copy_verification']})")
        elif a.command == "index":
            print(rebuild_index(a.dest_root))
    except (ExportError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
