# Finite proof of ADR 0011, third attempt (r03) — capsule of 2026-09-28

**An engineering diagnostic of one run; not a gate, not a claim.** This capsule
publishes the record of the third attempt at the finite proof of
[ADR 0011](../../adr/0011-controller-restart-recovery.md), executed on
2026-09-28, and the scope of the student's decision about it, recorded on
2026-09-29. The guest is ARM64 **emulated** under QEMU/TCG (`-cpu cortex-a76
-smp 4 -m 8192`) on an x86-64 WSL2 host, with the load generator on the same
machine: every duration, lag and rate below is an observation of an emulated
guest and is informational only. G3 stays paused and `Not decided` in
[`gate_decision_log.md`](../../governance/gate_decision_log.md); publishing this
capsule and merging its pull request decide nothing about it.

## The decision this capsule supports, and its limits

On 2026-09-29 the student accepted r03 as meeting the purpose of the finite
engineering diagnostic **for this run**, with the missing Docker kill/start
timeline explicitly acknowledged (ADR 0011, *The decision recorded on
2026-09-29*; LOG #C046). That acceptance is **not** a declaration that the run
complied with the ADR's evidence collection, not a G3 pass, not a showing of
exactly-once recovery, not a capacity or performance result and not the
admission of any dissertation claim. What the decision keeps exactly as
recorded:

- the evaluator's verdict **`supports`** (exit 0), for this run only;
- the harness's own verdict on its raw run, **`invalid`**, with its inner seal
  withheld;
- the ordinary twin `delta` result, exit 4 (`MISMATCH`, a smart-clothing twin
  surplus of one), which the N1 case below explains;
- the proof-only admission of the sampling gap (E-12, form
  `sampling-gap-only`), which applies to the proof and to nothing else.

The first and second attempts (r01 and r02, 2026-09-26, both `inconclusive`)
are unchanged and are not published here; their packages and hand-offs remain
local, under `output_test/`.

## What was recorded

One guest session, 20:54:12 to 21:28:19 UTC on 2026-09-28, and one attempt,
`proof-adr0011-r03`; nothing was repeated. The seven directories are
byte-for-byte copies of the local packages under `output_test/runs/2026-09-28/`,
which stay the originals; each keeps its export name and its own seal.

| Package | What it holds | `SHA256SUMS` of the package |
|---|---|---|
| `HIST_2026-09-28-r03-host-preparation` | tools clone moved to `b65a06d`, helper regenerated, identities checked, before the session | `e1e5b8bea10be4083a7cdc8b4b1592cb75b9395a612533be3e5ff291c9904e78` |
| `20260928T205412Z_guest-session_attempt06` | boot, open and close of the guest session | `64a7750ac7fcb84d91434c3b932c18a1f66ab2a0680f668c73aa8bc8558ec9da` |
| `20260928T205459Z_live-preflight_attempt07` | live preflight and its interlock | `e8c5a7e87ef73c74544c5d773cdd150872f3d668bdd895c469c6971421d298fd` |
| `20260928T210029Z_candidate-start-check_attempt03` | post-start identity check of the candidate | `93baab9df09e42f342375107998746115e78176c4559c90be556b642e96367d2` |
| `20260928T210104Z_g2-gate-preconditions_attempt04` | health record the proof started from | `0c496a389c265fdf752275161b23e544cd85ab831b249ba58a0cf3ad3f567285` |
| `20260928T210147Z_finite-proof-adr-0011_attempt03` | the proof: plan, harness raw run, fault record, snapshots, verdict | `e09d4019d64628ee7bef0498bec9b23c4e6f1d0c56da1f496c0f33d389f475ec` |
| `HIST_2026-09-28-r03-operator-records` | wrapper console logs of each step, run plan, ad-hoc driver, hand-off verification; resealed once, its first seal kept as `SHA256SUMS.1` | `5166c446e92ced77940ceb83bb1c039ab4119a3d6ef72ac61b7f796143c7d7e0` |

**Identities.** Tools: clean clone at `b65a06d` (tree `4034520`), the merge of
pull request #49, `repo_dirty_lines: 0`, driver set
`761df315a4702b5b128d31f9cac546ec7d810125c767bf2c850750cd4450139e`, export tool
`544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b`. Candidate:
controller image
`sha256:9a293fe13b1a020560d43fee328632a9ef8d91dec830899f18d3e2d964aa5f46`, built
from `489bc9e` and retained (no build or load in this session); guest Poky
5.0.19. The preserved data-disk baseline still hashed to
`91e2d7b96a6ca5e43647735e765e900a2bbb66d14077ff2127a03d42d9f39cef`.

**Result, as the proof package states it** (`analysis/proof_verdict.json`,
`SUMMARY.md`): instrumentation `valid`; S1–S6 hold, R1–R4 not observed, no stop
rule reached; 3,360 distinct published identities, 3,359 `accepted` and one
`duplicate`-only. Fault dispatched at 21:12:52Z (host clock); the same container
started again at 21:13:03.73Z (guest clock); all six services healthy at the
restoration check; clean close.

## Read these carefully

1. **The Docker kill/start timeline is missing.** `raw/proof-adr0011-r03/logs/sut/docker-events.log`
   holds 41 lines, 21:19:32.507Z to 21:26:28.142Z, all healthcheck `exec_*`
   events: no `kill`, `die` or `start`. The query was bounded `--since` the
   session's guest epoch (21:01:49Z) and exited 0; the cause of the truncation
   was not established, and a bounded event history in the daemon fits it. The
   restart is shown instead by the fault record
   (`analysis/snapshots/*restart.txt`) and the container's `StartedAt`.
2. **The two SUT logs are not scoped to the run.** `controller.log` holds the
   container's whole log since 2026-09-26T17:59:10Z, so the r01 and r02 sessions
   are in it; `broker.log` goes back to 2026-09-20T23:35:07Z. They are published
   as sealed, unfiltered. The evaluator found no A5 occurrence anywhere in the
   controller log, so no earlier-session line decided this verdict; earlier
   lines do appear in report-only fields.
3. **`complete` is not coverage.** The verdict's
   `instrumentation.proof_evidence.complete = true` records that each log
   fetch has a record, exited 0 and left a readable file in the run directory.
   It does not check what interval the files cover, and it is not collection
   compliance.
4. **The harness run is invalid and unsealed.** The collector file was rejected
   at ingest for one gap on `egw-controller-1`, 21:12:54–21:13:02Z (8.0 s),
   beyond `MAX_SAMPLE_GAP_S`; the harness then records `no SUT resources` and a
   missing `resources.csv`, and withholds its inner `SHA256SUMS`. E-12 admits
   that form for the proof only; for any G3 run it is a failure.
5. **One N1 case.** The `duplicate`-only identity (`059c22fc…`, smart clothing,
   sequence 621) was received 0.209 s after the first post-kill metrics reading,
   so the unchanged evaluator names it an N1 case (source kill, twin surplus 1).
   Under the ordinary rules it counts as `lost` and makes `delta` report
   `MISMATCH`; that is why `console/025-delta.stdout.txt` exits 4.
6. **Wording frozen at export time.** Each export `SUMMARY.md` ends "A package
   here is a local copy. It is not published or admitted evidence": it was true
   when sealed and cannot be edited; this copy publishes the record without
   admitting it. The host-preparation summary says the executed tooling differs
   from `489bc9e` "in `cli.py`, `controller_metrics.py`, `run.py` and
   `proof.sh` only"; the runbook's section 6.1 helper also differs, and the
   remaining differences are the LOG, tests and the session README
   (`src/deployment` is identical). The packages sit under `2026-09-28`, not the
   `2026-09-27` the authorisation anticipated, because the drivers file them by
   the UTC date of their run IDs.
7. **Paths that are not in this repository.** Some records name files under the
   operator's home directory or the project manager's local notes; they are
   text, not links, and are not needed to verify anything here.

## Verification, secrets and layout

`SHA256SUMS` in this directory lists every file of the capsule except itself,
including the seven inner seals, `SHA256SUMS.1` and this README, and continuous
integration verifies every seal below `docs/evidence/`
(`tools/ci/verify_evidence.py`, job *contracts, evidence and links*). The check
runs in one direction: every entry a seal lists exists and hashes as recorded;
a file covered by no seal would not be reported. The host-preparation seal uses
the coreutils binary-mode marker (`<hash> *<name>`); the verifier accepts that
form since 2026-09-29 rather than the seal being rewritten. Before the copy,
every local seal (and `SHA256SUMS.1`) verified; after it, the 301 files were
compared by SHA-256 with the originals and all were identical.
`.gitattributes` stores this directory without text conversion, because six
captured files contain carriage returns that are part of the record.

No private key, password file or credential value is stored here, on two
grounds. The five export manifests record their own scan (the values of four
named password variables and PEM private-key blocks, `excluded: []`); the two
`HIST_` packages have no export manifest. Separately, on 2026-09-29, before
publication, the developer swept all 301 files against the value of every
variable that has one in the execution host's environment file (20 variables),
and for PEM and OpenSSH private keys, mosquitto password hashes, bearer and
basic authorisation values and URLs with inline credentials: none was found.
That sweep's script and output are kept locally with this block's evidence
under `output_test/runs/2026-09-29/`, not in this capsule. Non-secret
configuration the transcripts exist to show does appear — among it the broker
username, ports, time zone, retry settings and gateway identifier.
