# Local test outputs (`output_test`)

Every test attempt of the gateway — unit and integration tests, simulator runs,
harness runs, guest sessions, builds — leaves an inspectable package on the
student's Windows computer, including the attempts that fail. This page says
where the packages are, what each contains and which rules the export keeps.
It implements section 2.B of the project-management work order of 2026-09-19,
with the path-safety, console-capture and source-root corrections asked for by
the project review of the same date (F1, F2 and F4) and the rounds of
corrections that followed the adversarial reviews of those, the last of them
on 2026-09-20. It is a
**local copy**: a package here is not published or admitted evidence, and it is
not an off-machine backup.

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
| Copy verification | `verified`, `verified; incomplete` or `failed` | whether this copy is intact, and whether it holds everything the attempt named or held |

`verified; incomplete` means every byte that *was* copied verified, and
something the attempt itself named or held is nevertheless not in the package:
a registered source root that was skipped, a registered artefact below one, a
registered artefact that was never written at all, a declared
`expected_artefacts` pattern that matched nothing copied, or an entry of the
attempt directory itself that this export refused or could not read — a
`commands.jsonl` left as a link when it was moved off a full disk, a session's
`guest/` left root-owned by its `sudo` step, a folder that could not be listed.
The rule is one rule and it is not a list of names: anything inside the attempt
that the export refused or could not read is evidence the package does not
hold, so it reaches the verdict instead of only the list of special files. The
`Copy verification` cell names each one, `package_completeness` in the manifest
counts them, the `INDEX.md` copy column repeats the counts, and the export
receipt in WSL carries the same value — so a reader who has only that one field
never sees a plain `verified` for a package sealed without its capsule.

The receipt (`<attempt>/export/receipt.json`, never inside a package) states
that in **one** field, `package_state`, which is what the session drivers read
to report a run:

| `package_state` | Means |
|---|---|
| `verified` | the package is in `output_test`, sealed, holds everything the attempt named, and `INDEX.md` lists it |
| `verified; incomplete: …` | sealed and verified, with what is missing named after the colon |
| `verified; not named in the destination's index: …` | sealed and verified, but `INDEX.md` itself could not be rebuilt, so the record does not name it |
| `verified; the destination's index names it; …` | sealed, verified and named by `INDEX.md`, while a convenience file beside it (`LATEST_SUMMARY.md`) is stale |
| `not exported: …` | no verified package was produced; the partial one stays under `incomplete/` |
| `not in the destination: …` | a package this attempt had is gone or no longer verifies (written by `recover`) |

A valid measurement of late or lost messages is a **system failure**, not
invalid evidence. An export that succeeds never makes a failed test pass, and a
failed export never hides a test result: the partial package stays under
`incomplete/` and the attempt stays in WSL until it is exported.

Instrumentation validity is `invalid` whenever the attempt records a console
capture that failed, whatever it was before: `valid`, the `not-applicable` the
session-close driver writes and the `unknown` every attempt starts at are all
downgraded, because a stream that was not kept is evidence lost in each of
them. The export stores `invalid` and a `validity_note` saying what was
downgraded and why, so a driver that asked for something else still sees its
own request in that note and the downgrade reads as a downgrade, not as a
verdict nobody gave.

## The console capture is evidence

`exec` keeps each command's stdout and stderr in `console/`. Those files are the
mandatory sink; the copy echoed to the terminal is optional and exists only so
the operator can watch.

- A write, flush or close failure on a console file (a full disk, a closed
  handle) is recorded in `commands.jsonl` as `capture: {state: failed,
  bytes_received, bytes_kept, error}` for that stream, and written to the
  attempt's `capture_failures` list. That sink is then abandoned while the pipe
  goes on being drained, so the command never blocks on a full buffer.
- A failure to read the child's own pipe is recorded the same way (`read: …`).
  There is then nothing left to drain, so that stream stops there instead of
  ending the reading thread with a traceback and leaving the capture looking
  complete.
- `bytes_kept` is what the console file really holds, re-measured after any
  failure: the head of a chunk the disk accepted before refusing is evidence
  that survived, and bytes lost in a buffer at the close were never kept.
- `exec` then exits **74** (`EX_IOERR`). The command's *own* exit code is still
  what `commands.jsonl` records as `exit_code`: 74 says the evidence is
  incomplete, never that the command failed. A child killed by a signal keeps
  the raw value `wait` returned (`-N`) in `exit_code`, names the signal in
  `killed_by_signal`, and makes `exec` exit `128 + N`, as a shell does.
- The loss is written to `attempt.json` *before* the record is appended, and a
  failure to write it is itself recorded (`not_persisted`) and still exits 74,
  never 2: whichever of the two writes survived, the loss is on disk.
- A failure of the terminal echo alone is recorded as `echo: failed: …` and is
  not a loss of evidence: `exec` exits with the command's own code.
- The whole-attempt verdict is the **union** of three sources: the attempt's
  `capture_failures`, every record in `commands.jsonl` whose capture state is
  `failed`, and `console/` itself. One source going silent therefore cannot
  make an incomplete capture read as complete or as "not applicable", and the
  union is what downgrades the validity, what the summary prints and what the
  export records in `export_manifest.json`. While an attempt is still running,
  a console file without a record is a command in flight, not an unaccounted
  one, and one shorter than its record is a file still being written.
- `console/` is read in **both** directions. A file whose name follows the
  `<NNN>-<name>.<stream>.txt` pattern that no record names is a stream nobody
  accounted for (an interrupted command leaves its console files and no
  record). A file a record *does* name must still be there and still hold at
  least the `bytes_kept` that record asserts: one truncated or removed between
  the command and the export is a capture failure too, because hashing a
  truncated file does not make the missing output come back.
- The directory itself is proved before it is listed. `console/` is written by
  `exec` and by nothing else, so one that is a **link** — an operator moving it
  off a full disk and leaving a shortcut behind — or that is not a directory at
  all holds bytes that are not provably this attempt's: it is a capture failure
  in its own right, every stream recorded in it is reported as unprovable, and
  the planner refuses to copy it, so the verdict and the package agree. A
  `console/` that cannot be listed, and an entry in it that is a link or a
  special file, are capture failures too. An empty listing and a directory
  nobody could look into are different facts and the export never confuses
  them: a package with no console evidence can never read as a complete
  capture.
- Each refusal states what was **measured**. A directory that cannot be listed
  can still hold every recorded file, openable by name, so its streams are
  reported as "the console directory could not be listed …, so this stream
  cannot be shown to hold what the record claims"; "no longer in the attempt"
  is kept for the case the export really saw, a listing that succeeded without
  the file in it. When the listing refused the **entry** itself — it is a link,
  it could not be inspected, it is not a file — that reason is the measured one
  and it is the one reported, and the bytes kept are left unknown rather than
  stated as zero against a record that says otherwise.
- A file in `console/` whose name does **not** follow that pattern was written
  by something else — an editor's swap file, an operator's note in a folder the
  drivers tell them to read, a `desktop.ini` left by browsing the attempt from
  Windows. It is copied with the rest of the package (unless the secret scan
  excludes it) and listed under "Files in console/ this export did not write",
  with its size. It is never published as a lost stream
  and it never downgrades a verdict: a stray byte must not cost a measured run
  its validity.
- **One** function decides the verdict — the list of streams that were not kept
  and what that costs the validity — and the attempt's own file, the manifest,
  `SUMMARY.md` and the `INDEX.md` row are all built from it on the same inputs,
  so no two of them can disagree about one attempt. What is compared is the
  whole verdict and never the list alone: the union is monotone, so a stored
  list that is already right is the ordinary case, and an attempt whose
  *validity* was never downgraded beside it is exactly what a driver, a
  recovery by hand or an older tool leaves behind.
- The export is the last gate before the evidence leaves WSL, so it brings the
  attempt to that verdict **before** the package is planned and copied, through
  the ordinary update path (the downgrade and its note are recorded). If the
  attempt directory cannot be written, the package still carries the verdict
  this export computed and says so, in its own section and in the manifest's
  `capture_reconciliation`, and the `INDEX.md` row then applies the same rule
  to the manifest rather than repeating the stale verdict beside it
  (`invalid (console capture: see SUMMARY.md)`).
- The summary shows the capture state in the commands table and in the result
  table, and names each unaccounted console file under "Console output nobody
  accounted for". The commands table never links a file the package does not
  hold: a console file excluded for a secret is shown as excluded with a link
  to its redacted copy, and the result row then reads "complete on the WSL
  side" and names the file that stayed there — never "kept in full".

## Commands

The tool is `python -m egw_experiments.local_export` (source:
[`src/egw_experiments/local_export.py`](../../src/egw_experiments/local_export.py)).
Run it from the clean clone's `src/` with its virtual environment.

```bash
OUT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"   # the WSL path of the Windows folder
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
python -m egw_experiments.local_export recover --attempts-root ~/egw-exec/attempts \
      --dest-root "$OUT" --secrets-env ~/egw-tcg/.env --interrupt <run_id>   # an attempt whose process died
```

`exec` keeps each command's stdout and stderr in `console/` and records its
argv in `commands.jsonl` with every secret value replaced by the variable's
name; it exits with the command's own exit code, or with 74 when a console file
did not keep everything. `add-source` names artefacts written elsewhere (a
harness raw directory, a simulator run directory and its `<run_id>.*`
siblings), which the export copies under `raw/` or `simulator/`; the last
component of the path is recorded as it was given, so a source root that is a
link stays a link and is listed instead of read. Its **parent** is made
physical as far as the filesystem knows it: a driver registers a capsule before
the harness creates it (`nominal.sh` refuses to start unless the raw directory
is absent), so the longest prefix that already exists is resolved and the names
below it are kept as given. A path holding a `.` or `..` component is refused
where it is given: `..` survives the absolute spelling, and `lstat` then
resolves the whole chain behind it, which would read through exactly the link
the rule keeps. Two sources with the same name get distinct folders.
`--secrets-env` is required on `exec`, `export`, `recover` and `backfill`, and
every summary states which variables were searched.
`recover` exports every attempt without a
complete export, historical ones included, and never touches an attempt still
marked running unless it is named with `--interrupt`: a running attempt may be
driven from another terminal. It also looks at the destination and not only at
the WSL receipt: an export counts as complete only while the package its
receipt names is still there **and still verifies against its own
`SHA256SUMS`**, so one that was tidied away, renamed, restored over or left
holding fewer files than it was sealed with is exported again — or, since a
package is never replaced, reported as a failure row, which makes `recover`
exit 2. The receipt's `package_state` is rewritten to
`not in the destination: …` first, so nothing goes on claiming a verified
package while the recovery works out whether there is one.
A package already finalised from an earlier
state of its attempt is never replaced; exporting the changed attempt then
fails with a message that says so.

Both rules above are proved again at **export** time, on the read side,
together with the third one the write side keeps — that the recorded path is
absolute — because none of them is settled by the writing: a `sources.json`
written before they existed (or by hand) can hold a relative path or a `.` or
`..` component, and the chain above a root can change between `add-source` and
the export — the project's own story is a `results/` that points at another
disk. A relative path would be resolved against the directory the export runs
in (`$REPO/src` for every driver), so whatever happened to sit there would be
sealed under the run's own capsule name; it is named and never read. Every
component of a recorded source path is likewise walked with `lstat` before the
source is touched, and a root reached through a link is named, with the
offending component, and never read.

A registered source root that the export did not copy — because it is a link,
is reached through one, is relative, holds a `.` or `..` component, or is a
FIFO or another special file — is named where the verdicts are read: in the manifest as
`skipped_source_roots`, in the summary's "Copy verification" cell, in the
`INDEX.md` copy column and in `copy_verification` itself. A registered artefact
*below* a root (a file inside the capsule, a glob sibling) that was not copied
is counted there too, as `skipped_registered_artefacts`, and so is a declared
`expected_artefacts` pattern that matched nothing copied. A root that is a link
resolving to nothing counts as a **missing** artefact as well: it is a link, so
it is listed and never read, and the artefact it names does not exist either.

The export runs automatically, at completion and on failure, when an attempt
is driven by the session drivers in [`tools/session/`](../../tools/session/README.md);
a command run by hand is exported by hand.

## Rules the export keeps

- Bytes are copied, never rewritten; every destination file is re-read and
  compared by SHA-256, and a package leaves `incomplete/` only after all copies
  and its own `SHA256SUMS` verify. An interrupted export resumes without
  rerunning the attempt.
- An earlier package is never replaced; a second export of the same attempt is
  a no-op while the package still verifies **and still holds what the attempt
  holds now**, and an error otherwise. The comparison is made against the whole
  plan — every planned file's SHA-256 against the one the manifest recorded,
  both sets of paths, and the entries the export refuses or cannot read — so a
  capsule that has grown under a registered source, a console file appended
  after the seal or a folder that has since become a link is refused loudly and
  never reported as already exported. A file the secret scan kept out has no
  recorded SHA-256 and is compared by presence alone.
- A historical attempt is never rewritten in place. `backfill` under a name
  already used repeats the export only when `--scenario`, `--date`,
  `--validity`, `--outcome`, `--note` and the emulation flag are the ones
  recorded; a corrected verdict is refused, naming each field that differs, and
  is backfilled under another `--name` so that what was published and the
  correction stand beside each other.
- A copied raw capsule keeps its own seal. An originally incomplete or unsealed
  run stays incomplete or unsealed: the outer seal shows copy integrity only.
  Sealed absolute paths are not edited; `export_manifest.json` records the WSL
  source of each file.
- A file holding a secret value from the given env file, or a private key, is
  not copied. It is listed as excluded and, when it is text, replaced by a
  separately named redacted derivative (`*.sanitized`); the original stays on
  the WSL side only. The summary and the export manifest are written from
  redacted copies of the attempt's fields.
- FIFOs, sockets and links are listed and never read on the source side, and
  refused outright inside a staging folder or a package, where an export
  creates only directories and regular files. Two package paths that differ
  only by letter case are refused, because Windows would merge them.
- Every path the export owns is built from the destination root's **physical**
  path, resolved once, and every component that already exists is inspected
  before anything is created, copied, written, deleted or promoted; an owned
  file that already carries a second name is refused, and every generated file
  is written to a fresh temporary file and put in place with one atomic
  replace. See "What the export refuses" below.
- A package that was finalised, sealed and receipted stays that way. `INDEX.md`
  is derived from the packages on disk, so a rebuild that fails is reported on
  its own, naming the file that failed (which is not always `INDEX.md`), and
  never rewrites a complete receipt as a failure — but the receipt does say
  that the record does not name the package, so no driver reports the export as
  wholly done. `local_export index` rebuilds the index later.
- Missing artefacts are listed as missing; nothing is fabricated. An operating
  system error during the copy (a full disk, a file held open by Explorer)
  leaves the partial package under `incomplete/`, listed in the index, and a
  later export resumes it.
- Raw packages and archives never enter Git. Only the tool, its tests, the
  session drivers and this page are versioned.

## What the export refuses

A folder name that looks right says nothing about where the filesystem would
put the bytes. `incomplete/<run_id>`, a folder inside it, `runs/`,
`runs/<date>` or `INDEX.md` can each be a **symlink**, a **Windows junction**
or another **reparse point** that sends a write — or a deletion — into a
directory the export was never pointed at. A run id that matches the expected
pattern does not make the path physically contained either.

So, before anything is created, copied, written, deleted or promoted, each
component from the physical root down is inspected without being followed: it
must be a real directory (a real file for a leaf), and the resolved path must
still be inside the physical root. Directories are created one component at a
time and checked again after creation. A component that is a link makes the
export **refuse** with an error that names the path; nothing is written and
nothing is removed. Each refusal says what was actually found: an ordinary file
where a directory belongs is named as one, and a FIFO, socket or device is
named as what it is, so nobody is sent looking for the wrong obstacle.

A **hard link** is refused as well, and it is the case a resolved path cannot
catch: a second name for the same bytes is *inside* the root, so every check
about where the path leads agrees with it, while writing that name rewrites a
file outside the root in place and ties the sealed package to it for ever. On
Windows it is also the redirect that needs no privilege (`mklink /H`,
`fsutil hardlink create`), where a symlink needs Developer Mode or an
administrator. Every file the export creates has exactly one name, so an owned
file whose link count is above one is foreign, whether it sits in the staging
folder, in a finalised package or at `INDEX.md`. The refusal says what the
count measured — that the file has *n* names — and not where the other name
is, because nothing looked that up. Directories are not counted this way: ext4
gives a directory one link per subdirectory.

| Where | What happens |
|---|---|
| `incomplete/`, `incomplete/<run_id>`, or a folder or file inside the staging folder | refused; the export writes nothing and removes nothing |
| `runs/`, `runs/<date>` | refused; the finished package is never moved through a link |
| `INDEX.md`, `LATEST_SUMMARY.md`, `README.md` | refused; the index is never written through a link |
| a hard link at any of those names, or at a `.partial`/`.tmp` companion | refused; the other name keeps its own bytes |
| a package folder under `runs/<date>/` or `incomplete/`, or a link of any kind inside one | never read; listed in `INDEX.md` with copy state `REFUSED: link` and the reason |
| a FIFO, socket or device inside a staging folder or a finalised package | never read; the package is refused and listed in `INDEX.md` with copy state `REFUSED: special file`, naming what was found |
| a registered source root, a sibling of one, or anything inside an attempt | never read; listed in the manifest and the summary under "Not copied: special files", and counted in `copy_verification` and `package_completeness` |
| a folder inside an attempt that cannot be listed (a root-owned `guest/`, a `console/` with no read permission) | listed as unreadable, saying so rather than "never read", and counted in `copy_verification` and `package_completeness` |
| a registered source root recorded relative, reached through a link, or recorded with a `.` or `..` component | never read; listed as a skipped source root, naming what made it unprovable |
| a historical source given to `backfill` | refused, with the physical path to use instead, rather than producing an empty package |
| an artefact of the attempt called `SUMMARY.md`, `export_manifest.json`, `SHA256SUMS`, or `<name>.sanitized` beside the `<name>` it would be derived from | the whole export is refused, naming the file to move or rename: the generated file would replace the copy while the manifest kept the copy's SHA-256 |

`INDEX.md` is the record and `LATEST_SUMMARY.md` is a convenience pointer to
its newest row, so they are written in that order of importance: the
convenience files first, `INDEX.md` last. A file that cannot be replaced — a
read-only attribute, an editor or a sync client holding it open — therefore
does not stop the record from naming a package that was sealed; `INDEX.md` is
written and says which file beside it is stale and must not be read as the
newest, and the failure is still reported, in the export receipt's
`package_state` and to the operator, so it is never a silent pass. The one
file that may not be left behind the others is `INDEX.md` itself: if *it*
cannot be written, everything already replaced is put back as it was. No
`.tmp` companion is left in the root after a replace the filesystem refused.

Every file the export generates — `SUMMARY.md`, the manifest, a `*.sanitized`
derivative, `INDEX.md`, `LATEST_SUMMARY.md`, `README.md` — is written to a
fresh temporary file and put in place with one `os.replace`, never opened in
place: a name that appeared between the check and the write is replaced instead
of written through. `SHA256SUMS` is written by the shared checksum helper, so
any earlier one is removed first and the seal is always a file of this export's
own making.

The export creates only directories and regular files, so a link, a hard link,
a FIFO, a socket or a device found inside a staging folder or a package is
foreign and that package is refused rather than sealed around it. A finalised
package is therefore walked before it is trusted — its `SHA256SUMS` alone sees
neither a linked folder nor a FIFO, which are neither files to hash nor
unlisted ones — and the index reads a package's verdicts only after that
walk, so no value read from outside the root is ever published inside it. The
destination root may itself be a link: it is resolved once, on purpose, so the
packages are written physically inside its target. WSL reports an NTFS junction
under `/mnt/c` as a symlink and native Windows reports it as a reparse point;
both are recognised, and `src/tests/test_local_export_windows.py` proves the
Windows side with real junctions and real NTFS hard links.

`recover` treats a refusal like any other failure of one attempt: it reports it
and goes on to the next attempt. It then **exits 2** if any attempt could not
be exported, because it is the remedy the driver table points to after a failed
export and must not report its own failure as a success; an attempt still
marked running, which it deliberately leaves alone, is not a failure.

## What the export does not check

The export says what it did and what it refused. It does not audit the
destination beyond that, and reading a package is not the same as trusting the
run it holds.

- It does not watch `output_test` between runs. A package deleted, renamed,
  restored over or left holding fewer files than it was sealed with is noticed
  only the next time `recover` runs, and only for an attempt still kept in WSL;
  an attempt already removed from WSL leaves nothing to re-export, and
  `INDEX.md` then simply stops listing it.
- It does not verify a package it was not asked about. `INDEX.md` is rebuilt
  from what is on disk and repeats each package's own recorded verdicts; only
  the package being exported, one found where a new export would go, and the
  one a complete receipt names while `recover` runs have their `SHA256SUMS`
  checked again. So the index's Copy column is the verdict recorded **when the
  package was sealed**, not a re-check made at rebuild time, and the header of
  `INDEX.md` says so; `local_export recover` is what re-checks it. A package
  that lost a file after it was sealed therefore keeps its sealed-time
  `verified` in the table until `recover` runs.
- `copy_verification` is about this copy, not about the run. A `verified`
  package can still hold a run whose instrumentation was invalid, and a capsule
  that arrived incomplete stays incomplete: the outer seal shows copy integrity
  only. An artefact the attempt registered and that was never written is
  reported on its own, as `missing_sources`, **and** counted in
  `verified; incomplete`, because a package sealed without its capsule reads
  alike whether the capsule was refused or never existed.
- It does not check that an attempt registered every artefact it should have.
  An artefact nobody named is an artefact nobody misses; `expected_artefacts`
  is the attempt's own declaration and only what it declares is checked.

## Analysing an exported run

The analysis (`python -m egw_experiments analyze --base-dir <dir>`) reads
`<dir>/raw/<run_id>/` and rewrites `<dir>/processed` and `<dir>/figures`. To
analyse an exported harness run, copy its `raw/<run_id>/` folder into a new
working folder, as `<work>/raw/<run_id>/`, and pass `--base-dir <work>`: a
sealed package is then never modified.
