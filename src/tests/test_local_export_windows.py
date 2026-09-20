"""Native-Windows cases for egw_experiments.local_export: NTFS junctions and hard links.

Under WSL an NTFS junction below ``/mnt/c`` is reported as a symlink, so the
symlink cases in ``test_local_export.py`` already cover the real export path.
Native Windows reports a junction as a reparse point instead, and creating a
symlink there needs a privilege the student's account may not hold, so the same
refusals are proved here with junctions made by ``_winapi.CreateJunction``.

An NTFS hard link is the redirect that needs no privilege at all
(``mklink /H``, ``fsutil hardlink create``, ``os.link``), and it is the one a
resolved path cannot detect: the second name is inside the export root and
``realpath`` agrees. Those cases are proved here on real NTFS, beside the same
cases on ext4 in ``test_local_export.py``.

The whole module is skipped off Windows, where junctions do not exist.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from egw_experiments import local_export as le

pytestmark = pytest.mark.skipif(os.name != "nt", reason="NTFS junctions exist on Windows only")


def _junction(target: Path, link: Path) -> None:
    """Create the NTFS junction ``link`` pointing at the directory ``target``."""
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every entry under ``root``: directories as ``None``, files by their bytes."""
    return {p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


@pytest.fixture()
def places(tmp_path: Path) -> tuple[Path, Path, Path]:
    """An attempts root, a destination root and a folder outside both of them."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_text("sentinel\n", encoding="utf-8")
    return tmp_path / "wsl attempts", tmp_path / "Projeto Mestrado" / "output_test", outside


def _finished_attempt(attempts: Path) -> Path:
    a = le.new_attempt(attempts, "nominal", "engineering")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    return a


def test_a_junction_is_recognised_as_a_link(places):
    _attempts, dest, outside = places
    dest.mkdir(parents=True)
    link = dest / "junction"
    _junction(outside, link)
    assert le._link_like(link)
    assert le._link_type(link) == "junction or other reparse point"
    assert not le._link_like(dest)  # a real directory is not refused


def test_a_junction_as_the_staging_folder_is_refused(places):
    attempts, dest, outside = places
    a = _finished_attempt(attempts)
    (dest / "incomplete").mkdir(parents=True)
    _junction(outside, dest / "incomplete" / a.name)
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="junction or other reparse point"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before
    assert not (dest / "runs").exists()


def test_a_junction_as_the_final_date_folder_is_refused(places):
    attempts, dest, outside = places
    a = _finished_attempt(attempts)
    (dest / "runs").mkdir(parents=True)
    _junction(outside, dest / "runs" / le.run_date(a.name))
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="junction or other reparse point"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before
    assert not (dest / "incomplete").exists()


def test_a_junction_inside_a_resumed_staging_folder_is_never_written_through(places):
    attempts, dest, outside = places
    a = le.new_attempt(attempts, "nominal", "engineering")
    le.run_command(a, "probe", [sys.executable, "-c", "print('console output')"], echo=False)
    le.finish_attempt(a, "finished")
    staging = dest / "incomplete" / a.name
    staging.mkdir(parents=True)
    _junction(outside, staging / "console")
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="junction or other reparse point"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before
    assert not (dest / "runs").exists()


def test_a_junction_as_a_package_folder_is_listed_as_refused_and_never_read(places):
    attempts, dest, outside = places
    a = _finished_attempt(attempts)
    le.export_attempt(a, dest)
    (outside / "attempt.json").write_text('{"run_id": "not mine", "scenario": "foreign"}', encoding="utf-8")
    _junction(outside, next((dest / "runs").iterdir()) / "20260919T000000Z_foreign_attempt99")
    before = _tree(outside)
    le.rebuild_index(dest)
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert "REFUSED: link" in index and "foreign_attempt99" in index
    assert a.name in index
    assert _tree(outside) == before


def test_an_ntfs_hard_link_is_recognised_without_being_a_reparse_point(places):
    _attempts, dest, outside = places
    dest.mkdir(parents=True)
    os.link(outside / "sentinel.txt", dest / "INDEX.md")
    assert not le._link_like(dest / "INDEX.md")  # nothing about it is a link to follow
    assert os.path.realpath(dest / "INDEX.md").startswith(str(dest))  # and it resolves inside the root
    assert le._hard_linked(dest / "INDEX.md")  # only the link count tells


def test_a_hard_linked_index_file_is_refused_on_ntfs(places):
    attempts, dest, outside = places
    a = _finished_attempt(attempts)
    dest.mkdir(parents=True)
    os.link(outside / "sentinel.txt", dest / "INDEX.md")
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="hard link"):
        le.export_attempt(a, dest)
    with pytest.raises(le.UnsafePathError, match="hard link"):
        le.rebuild_index(dest)
    assert _tree(outside) == before
    assert not (dest / "runs").exists()


def test_a_hard_linked_staging_leaf_is_refused_on_ntfs(places):
    attempts, dest, outside = places
    a = _finished_attempt(attempts)
    staging = dest / "incomplete" / a.name
    staging.mkdir(parents=True)
    os.link(outside / "sentinel.txt", staging / "SUMMARY.md")
    before = _tree(outside)
    # The refusal states the second name the link count measured, and not
    # where that name is, which nothing here looked up.
    with pytest.raises(le.UnsafePathError, match="this file has 2 names") as excinfo:
        le.export_attempt(a, dest)
    assert "outside" not in str(excinfo.value)
    assert _tree(outside) == before
    assert not (dest / "runs").exists()
    assert json.loads((a / "attempt.json").read_text(encoding="utf-8"))["status"] == "finished"


def test_a_junction_as_a_source_root_is_listed_and_never_read(places, tmp_path):
    attempts, dest, outside = places
    (outside / "notes.txt").write_text("content-only-reachable-through-the-link\n", encoding="utf-8")
    link = tmp_path / "capsule-link"
    _junction(outside, link)
    a = le.new_attempt(attempts, "nominal", "engineering")
    le.add_source(a, "raw", link, role="harness capsule")
    le.finish_attempt(a, "finished")
    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    types = {s["package_path"]: s["type"] for s in m["skipped_special"]}
    assert types["raw/capsule-link"] == "junction or other reparse point"
    assert not (package / "raw").exists()
    copied = b"".join(p.read_bytes() for p in package.rglob("*") if p.is_file())
    assert b"content-only-reachable-through-the-link" not in copied


def test_a_read_only_latest_summary_still_leaves_the_package_in_the_record(places):
    """The read-only attribute is the everyday Windows way for one write to fail.

    A restore from an older copy of ``output_test``, an editor or a sync
    client holding the file open: the record must go on naming every package
    that was sealed, and say which file beside it is stale.
    """
    attempts, dest, _outside = places
    first = _finished_attempt(attempts)
    le.export_attempt(first, dest)
    before_latest = (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8")
    os.chmod(dest / "LATEST_SUMMARY.md", stat.S_IREAD)  # sets FILE_ATTRIBUTE_READONLY
    try:
        second = _finished_attempt(attempts)
        m = le.export_attempt(second, dest)
        assert m["index_note"].startswith("LATEST_SUMMARY.md could not be rebuilt")
        assert "INDEX.md was written and names it as stale" in m["index_note"]
        index = (dest / "INDEX.md").read_text(encoding="utf-8")
        assert second.name in index and "must not be read as the newest" in index
        assert (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8") == before_latest
        assert second.name not in before_latest
        assert not list(dest.glob("*.tmp"))  # no unexplained companion left in the root
        receipt = json.loads((second / "export" / "receipt.json").read_text(encoding="utf-8"))
        # INDEX.md names it; only the pointer beside it is stale. The state is
        # still not a plain `verified`, so the driver goes on refusing it.
        assert receipt["package_state"].startswith("verified; the destination's index names it;")
        assert "not named in the destination's index" not in receipt["package_state"]
    finally:
        os.chmod(dest / "LATEST_SUMMARY.md", stat.S_IWRITE | stat.S_IREAD)
    le.rebuild_index(dest)
    assert second.name in (dest / "INDEX.md").read_text(encoding="utf-8")
    assert second.name in (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8")


def test_a_hard_link_at_a_tmp_companion_of_the_index_is_refused_on_ntfs(places):
    """The companion an index file is written through is an owned path too."""
    attempts, dest, outside = places
    a = _finished_attempt(attempts)
    dest.mkdir(parents=True)
    os.link(outside / "sentinel.txt", dest / "LATEST_SUMMARY.md.tmp")
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="hard link") as excinfo:
        le.rebuild_index(dest)
    assert getattr(excinfo.value, "file", "") == "LATEST_SUMMARY.md"  # the warning names the right one
    assert _tree(outside) == before
    assert not (dest / "INDEX.md").exists()  # nothing was written before the companion was proved
