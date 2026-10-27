"""Cases for tools/compare/measure_plan.py: the six-entry input plan of the
minimal Yocto-vs-Debian-13 comparison (three pairs of the frozen nominal
condition, one seed per pair, equal in both distributions).

The tool is run as the operator runs it, a subprocess of this interpreter
with the clone's ``src`` on PYTHONPATH (as test_g4_pilot_plan runs
g4_pilot_plan.py), and its functions are loaded from the file where a case
needs the plan as a value. Nothing here starts a guest or the harness's run
command; the harness's own plan loader and status writer are exercised on
the file to show it is accepted as written.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from egw_experiments import plan_gen
from egw_experiments import run as run_mod
from egw_experiments.plan_gen import FROZEN_ENTRY_FIELDS, load_campaign_plan, plan_to_json
from egw_experiments.protocol import CONDITIONS_BY_ID, PROTOCOL_VERSION

SRC_DIR = Path(__file__).resolve().parents[1]
REPO = SRC_DIR.parent
TOOL = REPO / "tools" / "compare" / "measure_plan.py"

SEEDS = (20261018, 7, 4294967295)
IDS = ("cmp-p1-yocto", "cmp-p1-debian13", "cmp-p2-debian13", "cmp-p2-yocto",
       "cmp-p3-yocto", "cmp-p3-debian13")
SCENARIO_OF = {rid: rid.rsplit("-", 1)[1] for rid in IDS}
PAIR_OF = {rid: int(rid.split("-")[1][1:]) for rid in IDS}


def _load_tool():
    spec = importlib.util.spec_from_file_location("measure_plan", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return _load_tool()


def _run_tool(*argv: str) -> subprocess.CompletedProcess:
    # The tool's streams are read as UTF-8 whatever the host's console code page is.
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(TOOL), *argv], env=env,
                          capture_output=True, text=True, encoding="utf-8")


def _write(tmp_path: Path, *seeds: str, out: Path | None = None,
           options: tuple[str, ...] = ()) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the tool's ``write`` as the operator does; (its result, the plan path)."""
    out = out or tmp_path / "compare" / "plan" / "measure_plan.json"
    tokens = seeds or tuple(str(s) for s in SEEDS)
    return _run_tool("write", "--out", str(out), "--seeds", *tokens, *options), out


@pytest.fixture(scope="module")
def written(tmp_path_factory) -> tuple[subprocess.CompletedProcess, Path, dict]:
    result, out = _write(tmp_path_factory.mktemp("plan"))
    assert result.returncode == 0, (result.stdout, result.stderr)
    return result, out, load_campaign_plan(out)


def test_six_entries_in_pair_order_with_the_exact_ids(written):
    _, _, plan = written
    assert [e["run_id"] for e in plan["runs"]] == list(IDS)
    assert [e["order"] for e in plan["runs"]] == list(range(1, 7))
    assert [SCENARIO_OF[rid] for rid in IDS] == ["yocto", "debian13", "debian13", "yocto", "yocto", "debian13"]


def test_seeds_equal_within_a_pair_and_each_pair_has_its_own(written):
    _, _, plan = written
    by_id = {e["run_id"]: e for e in plan["runs"]}
    for rid in IDS:
        assert by_id[rid]["seed"] == SEEDS[PAIR_OF[rid] - 1], rid
        assert by_id[rid]["repetition"] == PAIR_OF[rid], rid
    assert plan["master_seed"] == SEEDS[0]
    assert len({e["seed"] for e in plan["runs"]}) == 3


def test_every_entry_is_the_frozen_nominal_condition(written):
    _, _, plan = written
    nominal = CONDITIONS_BY_ID["nominal"]
    for entry in plan["runs"]:
        assert entry["condition_id"] == "nominal"
        assert entry["runner"] == "simulator" and entry["scenario"] == "nominal"
        assert entry["rate_msg_s"] == 11.2 and entry["duration_s"] == 600
        assert entry["warmup_s"] == 120 and entry["cooldown_s"] == nominal.cooldown_s == 0
        assert entry["status"] == "planned"
        # _run_entry's shape: every frozen field but the seed as it builds it, plus order and the block
        built = plan_gen._run_entry(nominal, entry["run_id"], entry["repetition"], 0, nominal.rate_msg_s)
        for field in FROZEN_ENTRY_FIELDS:
            if field not in ("seed", "order", "supplement"):
                assert entry[field] == built[field], field
        assert set(entry) == set(built) | {"order", "comparison"}
    assert plan["plan_version"] == plan_gen.PLAN_VERSION
    assert plan["protocol_version"] == PROTOCOL_VERSION
    assert plan["conditions"] == [nominal.to_dict()]


def test_the_file_is_canonical_and_the_harness_accepts_it(written, tmp_path):
    result, out, plan = written
    raw = out.read_bytes()
    assert b"\r" not in raw
    text = raw.decode("utf-8")
    assert text == plan_to_json(load_campaign_plan(out))
    assert text == plan_to_json(plan)
    # one line per entry (run id, seed, scenario), then the file's sha256
    lines = result.stdout.splitlines()
    assert lines[:6] == [f"{rid} {SEEDS[PAIR_OF[rid] - 1]} {SCENARIO_OF[rid]}" for rid in IDS]
    assert len(lines) == 7 and f"sha256={hashlib.sha256(raw).hexdigest()}" in lines[6]
    # an entry read as run.py reads it (scenario, seed, duration_s, rate_msg_s, warmup_s, cooldown_s)
    for entry in plan["runs"]:
        assert (entry["scenario"], int(entry["seed"]), int(entry["duration_s"]), float(entry["rate_msg_s"]),
                int(entry.get("warmup_s") or 0), int(entry.get("cooldown_s") or 0)) == (
            "nominal", SEEDS[PAIR_OF[entry["run_id"]] - 1], 600, 11.2, 120, 0)
    # the harness's status writer finds the entry and keeps both blocks intact
    working = tmp_path / "working.json"
    working.write_bytes(raw)
    assert run_mod.update_plan_status(working, "cmp-p1-yocto", "running") is True
    updated = load_campaign_plan(working)
    assert working.read_text(encoding="utf-8") == plan_to_json(updated)
    assert updated["runs"][0]["status"] == "running"
    assert updated["runs"][0]["comparison"] == plan["runs"][0]["comparison"]
    assert updated["comparison"] == plan["comparison"]
    assert updated["runs"][1:] == plan["runs"][1:]


def test_build_plan_is_deterministic_and_is_what_was_written(written, tool):
    _, out, _ = written
    assert plan_to_json(tool.build_plan(list(SEEDS))) == out.read_text(encoding="utf-8")
    assert tool.build_plan(list(SEEDS)) == tool.build_plan(list(SEEDS))
    with pytest.raises(ValueError):
        tool.build_plan([1, 1, 2])
    with pytest.raises(ValueError):
        tool.build_plan([1, 2])


def test_an_existing_output_is_refused_and_left_as_it_was(tmp_path):
    out = tmp_path / "measure_plan.json"
    out.write_bytes(b"keep me\n")
    result, _ = _write(tmp_path, out=out)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert result.stdout == ""
    assert "exists" in result.stderr and result.stderr.rstrip().endswith("nothing was written")
    assert out.read_bytes() == b"keep me\n"


@pytest.mark.parametrize("seeds, phrase", [
    (("1", "2"), "3 seeds are needed"),
    (("1", "2", "3", "4"), "3 seeds are needed"),
    (("1", "1", "2"), "must differ"),
    (("1", "2", "02"), "must differ"),
    (("1.5", "2", "3"), "not a whole number"),
    (("-1", "2", "3"), "not a whole number"),
    (("abc", "2", "3"), "not a whole number"),
    (("4294967296", "2", "3"), "not a whole number in [0, 2**32)"),
])
def test_bad_seeds_are_refused_and_nothing_is_written(tmp_path, seeds, phrase):
    result, out = _write(tmp_path, *seeds)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert result.stdout == ""
    assert phrase in result.stderr, result.stderr
    assert result.stderr.rstrip().endswith("nothing was written")
    assert not out.exists() and not out.parent.exists()


def test_missing_seeds_is_a_usage_error(tmp_path):
    out = tmp_path / "measure_plan.json"
    result = _run_tool("write", "--out", str(out))
    assert result.returncode == 2 and "usage: measure_plan.py" in result.stderr
    assert not out.exists()


def test_the_comparison_block_maps_each_run_to_its_scenario(written):
    _, _, plan = written
    block = plan["comparison"]
    assert block["runs"] == {
        rid: {"scenario": SCENARIO_OF[rid], "pair": PAIR_OF[rid], "order_in_pair": 1 + i % 2}
        for i, rid in enumerate(IDS)
    }
    assert block["pair_order"] == [list(IDS[0:2]), list(IDS[2:4]), list(IDS[4:6])]
    assert block["pair_seeds"] == {"1": SEEDS[0], "2": SEEDS[1], "3": SEEDS[2]}
    assert "exploratory" in block["purpose"].lower()
    assert "not campaign attempts" in block["purpose"] and "no statistical significance" in block["purpose"]
    assert "S1" in block["master_seed"]
    assert block["id_suffix"] is None and block["supersedes"] is None
    for entry in plan["runs"]:
        assert entry["comparison"] == block["runs"][entry["run_id"]]


# --------------------------------------------------------------------------
# a new series: --id-suffix and --supersedes
# --------------------------------------------------------------------------

SUFFIX = "a02"
SUFFIXED = tuple(f"{rid}-{SUFFIX}" for rid in IDS)


@pytest.fixture(scope="module")
def series(tmp_path_factory) -> tuple[Path, Path, subprocess.CompletedProcess]:
    """A first plan, then the second series written with a suffix against it."""
    root = tmp_path_factory.mktemp("series")
    first_result, first = _write(root, out=root / "first" / "measure_plan.json")
    assert first_result.returncode == 0, (first_result.stdout, first_result.stderr)
    result, second = _write(root, out=root / "second" / "measure_plan.json",
                            options=("--id-suffix", SUFFIX, "--supersedes", str(first)))
    assert result.returncode == 0, (result.stdout, result.stderr)
    return first, second, result


def test_suffixed_ids_keep_the_order_and_the_block_maps_them(series):
    _, second, result = series
    plan = load_campaign_plan(second)
    assert [e["run_id"] for e in plan["runs"]] == list(SUFFIXED)
    assert [e["order"] for e in plan["runs"]] == list(range(1, 7))
    assert all(plan_gen.RUN_ID_RE.fullmatch(rid) for rid in SUFFIXED)
    assert [e["seed"] for e in plan["runs"]] == [SEEDS[PAIR_OF[rid] - 1] for rid in IDS]
    block = plan["comparison"]
    assert block["id_suffix"] == SUFFIX
    assert block["runs"] == {
        f"{rid}-{SUFFIX}": {"scenario": SCENARIO_OF[rid], "pair": PAIR_OF[rid], "order_in_pair": 1 + i % 2}
        for i, rid in enumerate(IDS)
    }
    assert block["pair_order"] == [list(SUFFIXED[0:2]), list(SUFFIXED[2:4]), list(SUFFIXED[4:6])]
    for entry in plan["runs"]:
        assert entry["comparison"] == block["runs"][entry["run_id"]]
    assert result.stdout.splitlines()[:6] == [
        f"{rid}-{SUFFIX} {SEEDS[PAIR_OF[rid] - 1]} {SCENARIO_OF[rid]}" for rid in IDS]


def test_supersedes_records_the_earlier_plan_with_its_sha256_and_ids(series):
    first, second, result = series
    raw = first.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    plan = load_campaign_plan(second)
    assert plan["comparison"]["supersedes"] == {
        "path": str(first.absolute()), "sha256": digest, "run_ids": list(IDS)}
    lines = result.stdout.splitlines()
    assert len(lines) == 8 and lines[6] == f"supersedes {first.absolute()} sha256={digest}"
    assert lines[7].startswith("wrote ") and f"sha256={hashlib.sha256(second.read_bytes()).hexdigest()}" in lines[7]
    assert first.read_bytes() == raw, "the superseded plan is read only"
    assert second.read_text(encoding="utf-8") == plan_to_json(plan)
    assert plan_to_json(plan) == plan_to_json(_load_tool().build_plan(
        list(SEEDS), SUFFIX, {"path": str(first.absolute()), "sha256": digest, "run_ids": list(IDS)}))


def test_a_run_id_the_superseded_plan_holds_is_refused(series, tmp_path):
    first, _, _ = series
    result, out = _write(tmp_path, options=("--supersedes", str(first)))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert result.stdout == ""
    for rid in IDS:
        assert f"the run id {rid!r} is held by the superseded plan" in result.stderr
    assert result.stderr.rstrip().endswith("nothing was written")
    assert not out.exists() and not out.parent.exists()


@pytest.mark.parametrize("content, phrase", [
    (None, "could not be read"),
    (b"not json\n", "could not be read"),
    (b"\xff\xfe\x00", "could not be read"),
    (b'{"a": 1}\n', "holds no 'runs' list"),
    (b'{"runs": "x"}\n', "holds no 'runs' list"),
])
def test_an_unreadable_superseded_plan_is_refused(tmp_path, content, phrase):
    earlier = tmp_path / "earlier.json"
    if content is not None:
        earlier.write_bytes(content)
    result, out = _write(tmp_path, options=("--id-suffix", SUFFIX, "--supersedes", str(earlier)))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert phrase in result.stderr, result.stderr
    assert result.stderr.rstrip().endswith("nothing was written")
    assert not out.exists() and not out.parent.exists()


@pytest.mark.parametrize("suffix", ["", "a_02", "a.02", "a 02", "x" * 17, "é"])
def test_an_invalid_id_suffix_is_refused(tmp_path, suffix, tool):
    result, out = _write(tmp_path, options=("--id-suffix", suffix))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "id suffix" in result.stderr and result.stderr.rstrip().endswith("nothing was written")
    assert not out.exists() and not out.parent.exists()
    with pytest.raises(ValueError):
        tool.build_plan(list(SEEDS), suffix)


def test_a_sixteen_character_suffix_is_accepted(tmp_path):
    result, out = _write(tmp_path, options=("--id-suffix", "A-1" + "z" * 13))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert load_campaign_plan(out)["runs"][0]["run_id"] == "cmp-p1-yocto-A-1" + "z" * 13
