# Local test outputs (`output_test`)

Every test attempt of the gateway — unit and integration tests, simulator runs,
harness runs, guest sessions, builds — leaves an inspectable package on the
student's Windows computer, including the attempts that fail. This page says
where the packages are, what each contains and which rules the export keeps.
It implements section 2.B of the project-management work order of 2026-09-19.
It is a **local copy**: a package here is not published or admitted evidence,
and it is not an off-machine backup.

## Where

| Place | Holds |
|---|---|
| `C:\Users\ruimf\Documents\Projeto Mestrado\output_test\` | the packages, outside the `Claude` repository |
| `/home/ruisth/egw-exec/attempts/<run_id>/` (WSL) | the live capture of each attempt, on the Linux filesystem |
| `/home/ruisth/egw-exec/repo` (WSL) | the clean clone the attempts run from, at an identified commit |

```text
output_test/
  README.md  INDEX.md  LATEST_SUMMARY.md
  runs/<YYYY-MM-DD>/<run_id>/
    SUMMARY.md             what ran, the three verdicts, the reason, the next action
    export_manifest.json   every file with its source path and SHA-256
    attempt.json  commands.jsonl  sources.json
    console/               stdout and stderr of every command
    environment/ tests/ analysis/ (and boot/ guest/ host/ for a guest session)
    raw/<capsule>/         the harness capsule, byte for byte, with its own seal
    simulator/<run>/       the simulator output and its sibling files
    SHA256SUMS             the package's seal (copy integrity only)
  incomplete/<run_id>/     an export not verified yet: never a pass
```

`INDEX.md` is regenerated from the packages on disk, so no attempt can drop out
of it. Historical attempts that were preserved before this export existed are
copied as they are and marked *(historical)*; their validity is the one they
had.

## Run ids

`<UTC time>_<scenario>_attempt<NN>`, for example
`20260920T090000Z_nominal-instrumentation-120-600_attempt01`: no colon, so it
is a valid Windows name; the number never repeats for a scenario. A harness run
keeps its own plan run id (`nominal-r01`) inside the package, in `raw/` and in
the summary's workload: the plan entry and the export identity are different
things.

## Three verdicts, never merged

| Verdict | Values | Says |
|---|---|---|
| Instrumentation validity | `valid`, `invalid`, `not-applicable`, `unknown` | whether the attempt produced trustworthy evidence |
| System outcome | `pass`, `fail`, `inconclusive`, `not-run`, `interrupted`, `unknown` | what the system under test did |
| Copy verification | `verified` or `failed` | whether this copy is intact |

A valid measurement of late or lost messages is a **system failure**, not
invalid evidence. An export that succeeds never makes a failed test pass, and a
failed export never hides a test result: the partial package stays under
`incomplete/` and the attempt stays in WSL until it is exported.

## Commands

The tool is `python -m egw_experiments.local_export` (source:
[`src/egw_experiments/local_export.py`](../../src/egw_experiments/local_export.py)).
Run it from the clean clone's `src/` with its virtual environment.

```bash
A=$(python -m egw_experiments.local_export new --attempts-root ~/egw-exec/attempts \
      --scenario "smartwatch slice" --purpose engineering --dest-root "$OUT")
python -m egw_experiments.local_export exec --attempt "$A" --name pytest \
      --secrets-env ~/egw-tcg/.env -- python -m pytest tests -q
python -m egw_experiments.local_export add-source --attempt "$A" --kind simulator \
      --path ~/egw-tcg/itest/itest-slice-01 --siblings-glob 'itest-slice-01.*'
python -m egw_experiments.local_export finish --attempt "$A" --status finished \
      --validity valid --outcome pass --reason "every identity accounted"
python -m egw_experiments.local_export export --attempt "$A" --dest-root "$OUT" \
      --secrets-env ~/egw-tcg/.env
python -m egw_experiments.local_export recover --attempts-root ~/egw-exec/attempts \
      --dest-root "$OUT" --secrets-env ~/egw-tcg/.env      # after a crash
```

`exec` keeps each command's stdout and stderr in `console/` and records its
argv in `commands.jsonl` with every secret value replaced by the variable's
name; it exits with the command's own exit code. `add-source` names artefacts
written elsewhere (a harness raw directory, a simulator run directory and its
`<run_id>.*` siblings), which the export copies under `raw/` or `simulator/`.

## Rules the export keeps

- Bytes are copied, never rewritten; every destination file is re-read and
  compared by SHA-256, and a package leaves `incomplete/` only after all copies
  and its own `SHA256SUMS` verify. An interrupted export resumes without
  rerunning the attempt.
- An earlier package is never replaced; a second export of the same attempt is
  a no-op while the package still verifies, and an error otherwise.
- A copied raw capsule keeps its own seal. An originally incomplete or unsealed
  run stays incomplete or unsealed: the outer seal shows copy integrity only.
  Sealed absolute paths are not edited; `export_manifest.json` records the WSL
  source of each file.
- A file holding a secret value from the given env file, or a private key, is
  not copied. It is listed as excluded and, when it is text, replaced by a
  separately named redacted derivative (`*.sanitized`); the original stays on
  the WSL side only.
- FIFOs, sockets and symlinks are listed and never read.
- Missing artefacts are listed as missing; nothing is fabricated.
- Raw packages and archives never enter Git. Only the tool, its tests and this
  page are versioned.

The analysis (`python -m egw_experiments analyze --base-dir <dir>`) rewrites
`<dir>/processed` and `<dir>/figures`. Point it at a copy of a package's
`raw/` tree, never at the package itself, so that a sealed package is not
modified.
