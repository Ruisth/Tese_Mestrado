# Risk register

> Base: the integrated plan's §11 table (R1–R8; the Risk / Early signal /
> Mitigation fields are transcribed from the plan without alteration) +
> additional operational risks from this repository (R9–R15) + risks from the
> external audit of 2026-08-08 §11 (R16–R27, adapted to the real situation of
> the repository) + risks from the external post-correction re-analysis of
> 2026-08-08 §11 (RA1–RA15, followed line by line in their own section) +
> risks from the technical audit of 2026-08-10 (a new class: a correction that
> exists but is never reached, or is silently bypassed) + risks raised by real
> execution on 2026-08-10/2026-08-11 (dedicated ARM64 market unavailability,
> burstable instances, build-host drift, and defects that only real execution
> reveals). Control columns (Probability, Impact, Owner, State, Mitigation
> deadline) were added to every risk, as required by audit §5.4.
> Review at every gate closure and whenever an early signal is observed;
> record activations in the LOG.
>
> Owner: `Student` (actions outside the repository), `Agent` (changes inside
> the repository), `Both`. State: `Open`, `Mitigating`, `Partly mitigated`,
> `Mitigated`, `Materialised`, `Closed`. Probability/Impact for R16–R27 are
> the audit's values; for R1–R15, the assessment of 2026-08-08; for R28–R33,
> the assessment of 2026-08-10/2026-08-11 (all to be reviewed with the
> supervisors).
>
> `Mitigated at M2` means **only** that the correction exists in the
> repository and is covered by unit tests with fakes on Windows. It is not
> live proof, it closes no gate and it validates no claim.

Updated: 2026-08-11 (translated into British English and renamed from
`riscos.md`; R2, R9, R10 and R12 realigned with the WSL2 installation and the
`egw-image` build; R25 and RA13 mitigated by the private remote; R30
materialised and mitigated; R31 **materialised again** during the G1 boots;
RA1 corrected — WSL2 is installed, the measurement VM is not; RA11 realigned
with the sealed evidence of `701 passed`; R28 (market) is now the single
blocking dependency from G2 onwards).

**Identifier collision, resolved on 2026-08-12.** Two different rounds had
issued risks under the same identifiers: R28 and R29 were first used on
2026-08-10 for the technical-audit class (a guarantee unreachable through the
delivered CLI; non-finite values), and again on 2026-08-11 for the risks
raised by real execution (dedicated ARM64 market unavailability; a burstable
instance used as measurement platform). An identifier that means two unrelated
things is not a cosmetic defect: `docs/governance/language-policy.md` lists
risk identifiers among the values that are never rewritten precisely because
other documents cite them, and here the citations disagreed with each other —
the claim→evidence matrix pointed at the technical-audit pair while the
backlog and `experiments/results.md` pointed at the real-execution pair.

**The technical-audit pair was renumbered to R32–R33** and the real-execution
round keeps R28–R31. The real-execution block was already contiguous through
R30–R31 and carried the larger number of citations, so moving it would have
broken both. The mapping is recorded here because documents that predate
2026-08-12 — sealed evidence, merged pull requests, the LOG entries of
2026-08-10/11 — still carry the old spelling and are **not** rewritten:

| Issued as | Now | Risk |
|---|---|---|
| R28 (technical-audit round, 2026-08-10) | **R32** | A guarantee unreachable through the delivered CLI (the `--plan` defect) |
| R29 (technical-audit round, 2026-08-10) | **R33** | Non-finite or non-numeric values accepted by the analysis |

Every citation inside the working documents was updated in the same change:
[`../../PROGRESS.md`](../../PROGRESS.md), the claim→evidence matrix in both
its Markdown and CSV forms, and the frozen identifier range in
[`../governance/language-policy.md`](../governance/language-policy.md).

## Plan risks (§11)

| ID | Risk | Prob. | Impact | Owner | State | Mitigation deadline | Early signal | Mitigation/decision |
|---|---|---|---|---|---|---|---|---|
| R1 | No Raspberry Pi hardware | High | Low (the scope already excludes a physical Pi) | Both | Mitigated by design | — | Hardware remains unavailable | Functional QEMU + native ARM VM; exclude every physical-hardware claim |
| R2 | Yocto build slow or unstable | Medium | High | Both | **Materialised, then mitigated** — instability did appear during the first build (WSL2 host-clock drift breaking the `perl` compilation) and was corrected; the `egw-image` build then completed on 2026-08-11 with 5715 BitBake tasks, all successful (evidence sealed in `docs/evidence/g1-yocto-qemu/`) | met on 2026-08-11 (gate target 2026-08-16, trigger 2026-08-20) | G1 at risk | WSL2 on a Linux filesystem, pinned revisions, minimal image and download cache |
| R3 | Images without ARM64 | Low | High | Both | Mitigating (digests verified from documentation on 2026-08-07; `manifest inspect` on the VM still missing) | 2026-08-23 | `manifest inspect` fails | Replace with a compatible official image; ACA-Py is cut, never emulated |
| R4 | Ditto exceeds resources | Medium | High | Student | Open | 2026-08-23 | OOM or persistent swapping | Minimal 8 GiB VM, measured limits and non-essential services removed |
| R5 | The scope grows again | Medium | High | Both | Mitigating (audit §15: no scope creep detected) | continuous | A request with no link to the RQs | Apply P0/P1/out-of-scope and require an explicit exchange of hours |
| R6 | Results without provenance | Medium | Critical | Agent | Mitigating (manifests/checksums implemented; still to be exercised in the pilot) | 2026-09-06 (before `exp-v1`) | A metric without `run_id`/manifest | Invalidate the run and repeat it before the data freeze |
| R7 | Late feedback | Medium | High | Student | Open | milestones §8.2 (2026-08-10, 2026-08-17, 2026-08-31, 2026-09-07, 2026-09-18, 2026-09-23) | No reply at the milestones | Deliver chapters early and continue with the documented decisions |
| R8 | Writing left to the end | High | Critical | Both | Open (audit §6: 18–22% of the target on 2026-08-08) | 2026-09-06 (chs. 1–4) and 2026-09-18 (draft) | Chapters 1–4 incomplete on 2026-09-06 | Daily writing reserve and immediate cutting of P1 |

## Additional operational risks

| ID | Risk | Prob. | Impact | Owner | State | Mitigation deadline | Early signal | Mitigation/decision |
|---|---|---|---|---|---|---|---|---|
| R9 | Workspace on Nextcloud/NTFS: builds, virtual environments or Git repositories corrupted or slowed by synchronisation and NTFS file semantics | Medium | High | Student | Partly mitigated (2026-08-10: the workspace left the synchronised Nextcloud folder, which removes the synchronisation component; it remains on NTFS/Windows, so the rule of never building here holds in full. The first Yocto build did run in WSL2 on ext4, as the rule requires) | continuous (before the 1st build) | Synchronisation conflicts (`... (conflicted copy)`), file locks, slow I/O, builds failing non-deterministically | Never run Yocto builds or the stack from `/mnt/d`/Nextcloud (plan §5.1); builds and venvs in WSL2 ext4 or on the VM; copy only final results to the workspace; pause synchronisation during I/O-intensive operations; `SHA256SUMS` to detect corruption |
| R10 | ARM64 VM not available on 2026-08-10 (account, payment, provider capacity in the region) | Medium | Critical | Student | **Materialised** — on 2026-08-11 the VM still does not exist: three providers failed on the same day (Oracle, Hetzner, Azure for Students). Carried forward as R28 (real-execution round), which now owns this risk | 2026-08-10 (escalate 2026-08-12) — missed | VM creation still pending on 2026-08-09; region without CAX capacity (signal observed) | Apply the G0 rule (§8.1): with no VM on 2026-08-10, change provider/region; on 2026-08-12, report the risk to the supervisors; checklist ready in [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md) to minimise setup time |
| R11 | Python version divergence: Windows host with 3.14, containers/CI planned with 3.12, `pyproject` requires >=3.11 | Medium | Medium | Agent | Mitigating | 2026-08-16 (tests on Linux before G1) | Tests pass in one environment and fail in another; dependencies without wheels for the host version; different deprecation warnings | The reference environment for tests and execution is Linux (WSL2/VM) with the Python version pinned in the `Dockerfile`; do not validate behaviour only on the Windows host's Python; run `pytest` on the same interpreter as the container before declaring green |
| R12 | Insufficient disk space/memory on the host for the Yocto build in WSL2 | Medium | High | Student | Mitigated for the first build — it completed on 2026-08-11 in WSL2 on ext4 without exhausting disk or memory; the risk still applies to every rebuild | 2026-08-09/2026-08-10 (before the 1st build) — met | `df -h` below ~120 GB free before the build; memory pressure/OOM in WSL during BitBake | Check free space before the first build (guide §disk sizing); clean `tmp/` between builds if needed, keeping `downloads/` and `sstate-cache`; configure `.wslconfig` (memory/swap) before G1 |
| R13 | Performance variability of a cloud VM with shared vCPU (CAX21) contaminates the measurements | High | Medium | Both | Mitigating (methodological mitigation defined in plan §7.3; the measurement VM does not yet exist — see R28) | 2026-09-06 (close before `exp-v1`) | High `steal time` in `top`/`vmstat`; anomalous dispersion between repeated runs | Record the limitation in the environment manifest (plan §5.1); statistical unit = run with repetitions (§7.3); report dispersion (standard deviation/95% CI); exclude only proven cloud failures, never runs that were slow because of the result |
| R14 | Supervisors unavailable in August (holiday period) delays closing the scope at G0 | High | High | Student | Open | 2026-08-12 (escalate 2026-08-17) | No reply to the G0 email by 2026-08-12 | Send the email early with a request for asynchronous validation; continue with the documented scope (§8.1 G7 applies the same principle); record contact attempts in the LOG; escalate at the 2026-08-17 milestone |
| R15 | Loss or tampering of raw data before archiving (disk failure, sync, human error) | Medium | Critical | Both | Mitigating (`SHA256SUMS` per run implemented in the harness; external archive still to be produced) | 2026-09-07 (before the official campaign) | Failing checksums; files modified after collection | `SHA256SUMS` per `run_id` generated at the end of every run; `raw/` treated as immutable from collection onwards (not only at the freeze); copy to a versioned archive outside Nextcloud right after each campaign session |

## External-audit risks (2026-08-08, §11) — R16–R27

Note of 2026-08-08, updated on 2026-08-10 (blocks P1a–P1c, P2, P5 and P5.4) and
on 2026-08-11: R18, R19, R20 and R22 were corrected at M2 (live proof pending);
R21 remains under mitigation while not a single `integration` test exists; R24
remains under mitigation (the ARM64 runtime lock can only be born on the VM);
R25 became **mitigated** — the repository and the bundles left the Nextcloud
domain on 2026-08-10 and a private remote was created on 2026-08-11; R26 had
the diagrams/ch. 4 synchronisation completed and a checklist added. States of
`Mitigated at M2` only become `Mitigated` with archived evidence of real
execution.

| ID | Risk | Prob. | Impact | Owner | State | Mitigation deadline | Early signal | Mitigation/decision |
|---|---|---|---|---|---|---|---|---|
| R16 | The theoretical framing does not unblock the supervisor (ch. 2 with ~1 034 words against a target of 6 000–7 000) | High | Critical | Both | Mitigated — standalone draft ready on 2026-08-08; sending still pending (student) | 2026-08-10/2026-08-11 | No sendable draft on 2026-08-11 | Immediate theory sprint (audit §6.6/§12.2); suspend new features until it is sent to the supervisor |
| R17 | Novelty claim without a recorded search (`search_log.csv` and `study_selection.csv` with headers only) | High | High | Both | Partly mitigated — preliminary logs filled in with honest provenance; institutional queries pending (student) | 2026-08-11 (before sending to the supervisor) | Text sent with empty CSVs | Execute the review protocol and record the real queries/decisions, or limit the claim to the sources actually examined; never fabricate search entries |
| R18 | Resources measured on the wrong host (`docker stats` runs by default on the local Docker of the harness host) | High | Critical | Agent | Mitigated at M2 on 2026-08-08 — collector on the VM, two manifests, mandatory host provenance; live proof pending | before G4 (2026-09-06) | A pilot without unambiguous identification of the VM | Collector on the VM, or an explicit and recorded remote channel, + two manifests (`sut_environment` on the VM, `loadgen_environment` on the simulator host) |
| R19 | `events.jsonl` not collected by the runner (manual `scp` transfer incompatible with the synchronous flow; run marked as failed) | High | Critical | Agent | Mitigated at M2 on 2026-08-08 — automatic fetch with retries + `collect` subcommand | before G4 (2026-09-06) | The first pilot fails because of a missing file | Automate the collection phase before the pilot; no ad hoc intervention per run |
| R20 | Mandatory conditions missing from the campaign plan (10 smokes, `invalid-payload`, real reconnect, restart) — claims C10–C14 without a route | High | High | Agent | Mitigated at M2 on 2026-08-08 — plan of 95 runs with C10–C14 and acceptance with mandatory completeness | before the pilot (2026-08-30/2026-09-06) | Campaign plan without C10–C14 | Condition→claim matrix before the pilot; add the missing conditions to the plan generator |
| R21 | Unit tests mistaken for integration tests (the `integration` marker is registered but unused; no live tests) | High | High | Agent | Mitigating — marker and evidence policy corrected on 2026-08-08 | G3 (2026-08-30) | A gate declared on fakes alone | Definition of Done per level (audit §8.4) and a persistent test report; create live integration/E2E tests before G3 |
| R22 | Warm-up contaminates the resource metrics (the sampler covers warm-up + run; the analysis does not filter the measured window) | High | High | Agent | Mitigated at M2 on 2026-08-08 — measured window in the manifest, filter in the analysis and cadence caps | before G4 (2026-09-06) | `resources.csv` includes the pre-measurement period | Record `measured_started_utc` in the manifest and filter the measured window in the analysis |
| R23 | The saturation criterion changes after the freeze (queue growth `TODO`; CPU not normalised by number of CPUs; the "half of the runs" rule not validated) | Medium/High | High | Both | Open | before `exp-v1` (2026-09-06) | The queue-growth/CPU rule still undecided at G3 | Close the metric and the rule with the supervisor before the freeze; instrument queue depth or remove the criterion by a formally recorded decision |
| R24 | Python dependencies change between builds (`>=` in `pyproject.toml`, no lockfile with hashes) | Medium | High | Agent | Mitigating — development lock created on 2026-08-08; runtime lock with hashes before `exp-v1` | 2026-09-06 | A new build resolves different versions | Lockfile with versions/hashes before `exp-v1`; do not assert "reproducible rebuild" until then |
| R25 | Loss of repository or evidence provenance | Medium | Critical | Both | **Mitigating** — the private remote exists; five local bundles verify; exact-tree rewrite mappings are recorded; protected tag `evidence/g1-yocto-build-5770c0a` preserves the exact build. Residual blocker: no verified off-machine copy of the current complete bundle is recorded | off-machine copy before G1 acceptance | All bundles remain on the same physical machine; evidence object not reachable from a clean clone | Verify the protected tag from a clean clone; copy the current complete bundle off-machine and record its SHA-256/location without publishing restricted history |
| R26 | Documentation diverges from the contract (drift after CONTRACTS v1.1: references to v1.0, idempotency without `run_id` scope) | High | Medium/High | Agent | Mitigating — diagrams/ch. 4 synchronisation completed on 2026-08-08; impact checklist added | continuous (at every contract change) | CONTRACTS changes without updating thesis/diagrams/READMEs | Impact checklist per ADR/contract change; drift check twice a week (audit §14.2) |
| R27 | The management state induces false confidence (PROGRESS/backlog/plan contradicting one another; hybrid states outside the taxonomy) | High | High | Agent | Mitigating — PROGRESS restructured as the single source on 2026-08-08; backlog without state; on 2026-08-10 (P5.4) a new drift was corrected: PROGRESS pointed at the previous sealed evidence (`515`/`ca445a3`) and the backlog repeated that figure and asserted that the research CSVs were empty when they no longer were | review at every work block and at every gate | Divergent state documents | Single source of state in `PROGRESS.md` (Implemented/Verified/Accepted model); backlog with actions only; daily effort control (<10 min) |

## Risks from the external post-correction re-analysis (2026-08-08, §11) — RA1–RA15

The external verification of 2026-08-08 flagged that this file's earlier
statement ("RA1–RA15 mapped") was **too broad**: several RA items were merely
implicit in lines R16–R27, and one of them had already materialised. That
statement was withdrawn. The table below follows the fifteen risks **one by
one**, with an explicit state and, on each line, either the concrete evidence
in the repository or the dependency that blocks closure. The wording of the
"Risk" column is the re-analysis's §11 wording, unrewritten.

Mandatory reading of this table: `Mitigated at M2` = correction present in the
code and covered by unit tests with fakes on Windows — **no live proof, no
closed gate, no validated claim**. `Student action` = no change in the
repository closes the risk.

| RA | Risk (re-analysis §11) | Owner | State | Concrete evidence or blocking dependency |
|---|---|---|---|---|
| RA1 | Email/rules/VM/WSL2 delay G0–G2 | Student | **Open — student action** | Partly overtaken by events: WSL2 with Ubuntu 24.04.4 LTS is installed and operational on ext4, and it is what built the image (see R30). What remains: the G0 email is still unsent and the ARM64 measurement VM **does not exist** — three providers failed (see R28), which makes it the single blocking dependency from G2 onwards. Overlaps R10 and R14; no agent action closes it |
| RA2 | The academic claim of an executed protocol remains in chapter 1 | Agent | **Mitigated** (documentary) | "pre-registered" replaced by "pre-specified, frozen before data collection" in chs. 1/2/6 and in the abstracts (block P2); `grep -r "pre-registered" thesis/latex/` with no occurrences on 2026-08-10. Ch. 5 still carries no numbers, with `\todo{pending data-v1}` |
| RA3 | A complete PDF sent with placeholders and TODOs | Student | **Partly mitigated** | The standalone extract `thesis/latex/ch2_supervisor_draft.tex` (+ compiled PDF) exists precisely to avoid sending `main.pdf` with placeholders. Blocking dependency: sending it to the supervisor is a student action and has not yet happened |
| RA4 | "Verified sources" read as full-text reading | Agent | **Mitigated** (documentary) | [`../../PROGRESS.md`](../../PROGRESS.md) now declares 7 sources read in full text (S001, S004–S009) and 18 by title/abstract only; the count is read from the `stage` column of `thesis/research/study_selection.csv` (7 `full_text`, 18 `title_abstract`). "Verified" now refers only to the source metadata. It does not cover R17 (institutional queries), which stays with the student |
| RA5 | Invalid runs enter the results | Agent | **Mitigated at M2** | `src/egw_experiments/analyze.py` excludes from the aggregation those runs whose manifest `validity` exists and is not `valid`; the exclusion requires a proven cause (cloud/instrumentation/configuration) and never the outcome of the run. Reinforced in block P5: the directory's `SHA256SUMS` is verified **before** any aggregation (column `integrity_ok` in `per_run.csv`), and both integrity-failing runs and **unsealed** runs of timed conditions stay out of summaries, saturation, acceptance and figures, with an explicit warning. Known limitation handled in block P5.4: this gate decides about the run, not about the numerical sanity of each sample — see R29 (technical-audit round). Live proof pending on the VM |
| RA6 | Local resources treated as ARM resources | Agent | **Mitigated at M2** | Mandatory host-provenance column in `resources.csv`; SUT collection by `src/deployment/scripts/collect-resources.sh` on the VM, ingested through `run --resources-from`; the local sampler is opt-in (`--local-resources`) and is marked with `resource_source` (`local-dev` invalidates a timed run). Block P5 added semantic validation of the series at analysis time (unusable rows discarded and **counted** by reason: missing column, empty field, unreadable timestamp, non-numeric value, time going backwards), visible in `resources_rows_dropped`/`metrics_rows_dropped`. Equivalent to R18; live proof pending |
| RA7 | C10–C13 pass without completeness | Agent | **Mitigated at M2** | `processed/acceptance_by_condition.csv` evaluates **every** planned condition with an explicit completeness gate (`runs_complete`); a planned condition with zero valid runs does not pass. Block P5 replaced the count with a comparison of the **set of identities** (`run_id` + repetition + seed + rate, per load level in the sweep) against the frozen plan, when the plan is supplied to the analysis. The reach of this guarantee depends on the plan actually arriving at the analysis through the delivered command — that was the gap found on 2026-08-10 and recorded as R28 (technical-audit round). Live proof pending |
| RA8 | Queue/CPU with gaps produce a false sustained window | Agent | **Mitigated at M2** | The sustained-window detectors only count intervals between consecutive samples within the maximum admitted gap; each run reports `resources_coverage_pct`/`metrics_coverage_pct` in `per_run.csv`; block P5 added the *head gap* (a series that only starts sampling once already inside the window is not continuous evidence), the count of **distinct instants** inside the measured window, and a minimum below which the criterion fails instead of passing silently. The statistical thresholds, the percentiles, the CI method and the 60 s window were **not** changed in any of these blocks — only the instrumentation changed. Residual dependency: series with non-finite values (R29, technical-audit round) attack exactly these calculations |
| RA9 | Raw resources overwritten | Agent | **Mitigated at M2** | `raw/<run_id>/` directories are write-once: with `SHA256SUMS` present the directory is sealed and any write with different content is refused (`run.py`) |
| RA10 | A manual campaign fails on order or completeness | Agent | **Mitigated at M2** | `campaign` subcommand (`src/egw_experiments/campaign.py`): runs the frozen plan in order, with resume, `blocked` classification for unsealed directories, recorded cooldowns and `campaign_log.jsonl`. Live proof pending |
| RA11 | Evidence of 452 not reproducible per commit | Agent | **Closed** | The pattern is established and repeated: every block re-runs the suite over a clean HEAD and seals the evidence in its own directory identified by the commit. The current sealed record is `docs/evidence/tests/2026-08-11-head-4e67717/` (`701 passed`). The earlier seals are kept for traceability and are **historical**, each tied to the commit it tested — `683` (`05166eb`), `618` (`19d74ff`), `593` (commit `57228e178c784987492ca71a708740a5a85d0d95`, tree `e3e4fc84546662a7ecc650dbfd79596e48dab6a3`) and `515` (commit `ca445a31e5d146cf0c214b3cd4a23a95a48b5289`, tree `b767b229e295b9453cbc2efcbfd0122bf8409d38`) — and none of them is the current figure. All of them have an empty `git status --porcelain` and `SHA256SUMS`. Hygiene note, with no effect on reproducibility: the `2026-08-08` prefix of the `57228e1` directory is the block's date, not the run's |
| RA12 | Dev lock mistaken for a runtime lock | Both | **Partly mitigated** | The header of `src/requirements.lock` identifies it as a **development** lock, without hashes, generated in the Windows venv, and names the sealed suite it was verified against (currently the sealed record of `701 passed`). Blocking dependency: the ARM64 runtime lock with hashes must be generated during the image build on the VM and archived before `exp-v1`; until then it is forbidden to assert "reproducible rebuild". Equivalent to R24 |
| RA13 | Bundle lost in the same Nextcloud domain | Student | **Mitigated** | On 2026-08-10 the student copied the set (working repository and `backups/` bundles, including `egw-20260808-final.bundle` and `egw-20260808-p5.bundle`) out of the synchronised Nextcloud folder to a private location: the risk's condition — backup evidence inside the same synchronisation domain — no longer holds. **Closed on 2026-08-11 with the creation of the private remote** `Ruisth/Tese_Mestrado`: the history now exists off the local disk. Equivalent to R25 |
| RA14 | State documents diverge again | Agent | **Partly mitigated** | `PROGRESS.md` is the single source of state; block P5.3 corrected the first drift (real run_ids in the claim→evidence matrix, `diagrams/README.md` on CONTRACTS v1.1, `src/README.md` no longer suggesting live tests, LOG #C006 with the exact identifiers) and block P5.4 corrected the second, of the same kind: PROGRESS and `src/requirements.lock` pointed at the previous seal (`515`/`ca445a3`) after a more recent seal existed, and the backlog asserted that the research CSVs held headers only when they already held 25 sources and 3 recorded searches. **The risk recurred twice in three days**, always right after a block that produced new evidence. Blocking dependency: the cross-cutting review is not yet a routine with its own record — the operating rule is now "whoever seals new evidence updates, in the same block, PROGRESS, the lock header and the matrix". Equivalent to R27 |
| RA15 | Unrealistic forecast for want of recorded hours | **Student** | **MATERIALISED** | The risk has already occurred: `actual_h`, `remaining_h` and `forecast` are empty in the effort-control table of [`../../PROGRESS.md`](../../PROGRESS.md), so **no completion forecast exists** and the September dates have no quantitative support. These are human hours: no agent can estimate, infer or fill them in — inventing them would be fabricating data. The durations of agent work stay in `LOG.md` and do **not** replace these columns. Closure belongs exclusively to the student, in the daily control of <10 min |

Only the student can change the state of RA1, RA3 and RA15; RA12 requires the
VM. RA13 left this list on 2026-08-10 by the student's own action and was
closed on 2026-08-11 by the private remote. The `Mitigated at M2` states
(RA5–RA10) only become `Mitigated` with live proof after G3/G4, with archived
evidence.

## Technical-audit risks (2026-08-10) — R32–R33

The audit round of 2026-08-10 revealed a **new class of risk**, distinct from
the previous ones: the previous ones were about what is **missing**; these are
about corrections that **exist in the repository and still do not produce the
promised effect** — because the path actually delivered to the operator does
not go through them, or because a pathological input bypasses them without an
error. A risk of this class is particularly dangerous because the
documentation, the tests of the isolated function and a reading of the code
all say the protection is there.

Both defects below were addressed in block P5.4 (harness code, outside the
scope of this file). **This register does not declare them closed:** the state
of each correction is read from the sealed evidence of 2026-08-10 and from the
P5.4 entry in [`../../LOG.md`](../../LOG.md), and the standing verification
item at the end of this section remains **open until `exp-v1`**.

| ID | Risk | Prob. | Impact | Owner | State | Mitigation deadline | Early signal | Mitigation/decision |
|---|---|---|---|---|---|---|---|---|
| R32 | The implementation exists but is unreachable through the delivered CLI, or degrades silently (the `--plan` defect): completeness by **identity** against the frozen plan was only exercised when the plan was passed programmatically to `analyze(plan_path=...)` or through the environment variable; the CLI's `analyze` subcommand did not expose `--plan` and did not pass it, so the command documented as official degraded to the **count-based** check with neither error nor visible failure | High | Critical | Agent | Addressed in block P5.4 (2026-08-10) — standing verification active until `exp-v1` | before `exp-v1` (2026-09-06) | A protection described in the documentation whose test exercises the Python function and never the delivered command; an option that exists only as an API parameter or an environment variable | Every guarantee path must be reachable through the command exactly as it is delivered and, when the guarantee cannot be applied, the command must **say so out loud** instead of degrading in silence; the tests exercise `main()`/the CLI, not only the internal function |
| R33 | Non-finite or non-numeric values (NaN, ±Inf, text fields) in the series and in `timings.json` make the analysis fail or — worse — bias it without failing: a NaN contaminates means and percentiles and disorders comparisons, a non-numeric field raises an exception midway through the aggregation | High | Critical | Agent | Addressed in block P5.4 (2026-08-10) — standing verification active until `exp-v1` | before `exp-v1` (2026-09-06) | Campaign statistics with a `nan` result, inconsistent percentile ordering, or a numeric-conversion exception during the analysis | Numerical sanity on ingest: non-finite and non-convertible values are refused and **counted** as a discarded sample (with a reason), never accepted in silence, exactly like the other semantic validations of the series; the statistical rules, percentiles, CI method and 60 s window remain unchanged |

**Standing verification item before `exp-v1` (it does not close with a
commit).** For every harness protection invoked by the documentation, by
PROGRESS or by the claim→evidence matrix: (a) exercise it through the
**delivered command**, with the default arguments, and not only through the
Python function; (b) confirm that, in the absence of the necessary conditions,
the command **fails or warns unambiguously** instead of producing a silently
weaker result; (c) confirm that pathological inputs (empty, non-finite,
non-numeric, duplicated, out of order) result in a counted refusal, never in
an accepted result. While this item is open, no harness protection may be
described as guaranteed in real execution.

## Link to the contingency activators (§10)

The contingency to 2026-10-31 is activated at the first gate that makes
September unrealistic, never only at the end of the month. The plan's main
activators: no functional QEMU image on 2026-08-20; no vertical slice on
2026-08-25; core not frozen on 2026-08-30 with more than two days of work
left; invalid pilot on 2026-09-06; essential data incomplete on 2026-09-13; no
full draft on 2026-09-18. The first of these will not fire: the image was
built and booted twice on 2026-08-11, with the evidence sealed — which changes
nothing about the acceptance of gate G1, which remains pending. The
administrative rules of the extension are confirmed by 2026-08-10 (requested
in the G0 email); in the absence of an earlier official date, the request is
started by 2026-09-18 at the latest.

---

## Risks added on 2026-08-10/2026-08-11 (real execution) — R28–R31

| ID | Risk | Prob. | Impact | Owner | State | Deadline | Early signal | Mitigation |
|---|---|---|---|---|---|---|---|---|
| **R28** | **Dedicated ARM64 market unavailability blocks the measurement platform** — Oracle (home region fixed at registration, no Ampere capacity and no way to change region on an Always Free account), Hetzner (CAX sold out in every location) and Azure for Students (regions limited to 5; quota `0 of 0` on every dedicated ARM family) failed on the same day. Only the burstable B series is available, and it is barred from measurement (see R29) | High — realised | **Critical** | Both | **Materialised** — the measurement VM does not exist; quota requested (DPLSv5 and DPLSv6, Germany West Central, 4 vCPU); fallback AWS `c6g.xlarge` (~7 EUR for the campaign). **Single blocking dependency for G2 onwards** | VM operational before G2 (2026-08-23) | The G0 deadline of 2026-08-10 passed with no VM | Do not depend on free tiers for the critical path: budget ~7–15 EUR of dedicated instance. Report it in the G0 email (plan §10). Rule §8.1: no VM on 2026-08-12 ⇒ formally report the risk to the supervisors |
| **R29** | **Use of a *burstable* instance as the measurement platform** — Azure's B series (the only one with no quota request) works on CPU credits; once they run out, the processor is throttled | High if not barred | **Critical for RQ3** | Agent | Mitigated by decision: the B series is admitted **only** as a functional integration platform; no number from it enters the dissertation (see PROGRESS, "three steps") | permanent | Any timed run whose `sut_environment.json` reports a B/t4g family | Exclude `Bpsv2`/`t4g` from the protocol; the campaign only runs on a dedicated family (`Dplsv5`, `c6g`, `m6g`). Credit throttling would show up as CPU saturation and would falsify the criterion of plan §7.3 |
| **R30** | **Build-host drift over time** — `wsl --install -d Ubuntu` started installing Ubuntu 26.04 (Python 3.14), outside the validated Scarthgap envelope (2024-04) | High | High | Both | **Materialised and mitigated (2026-08-10)** — Ubuntu 26.04 was rejected first, precisely because it ships Python 3.14, outside the tested envelope of Yocto Scarthgap; the guide now requires installing by name (`-d Ubuntu-24.04`), with the reason and the date recorded. The build host is WSL2 with **Ubuntu 24.04.4 LTS** on ext4, and that is what produced the image | permanent | A build that fails in BitBake before the parse | The same command gives different hosts depending on the date: reproducibility requires pinning the host version, not only the layers |
| **R31** | **Defects that only real execution reveals** — the first build found 2 bugs in Yocto work classified as verified until then: a race in perl's parallel make, and `DL_DIR`/`SSTATE_DIR` resolving to a temporary kas folder (caches lost on every run, which made claim C01 of a reproducible build false) | **Materialised twice** (Yocto build, G1 boots); **likely** (harness) | High | Agent | Yocto: corrected (`e83fb24`, `c0ebf7c`). **G1 boots: materialised again** — running the automated driver `src/yocto/scripts/boot_check.py` (commit `32f6604`) exposed **six further defects**, among them a check that passed by matching the word `running` inside the echo of its own `systemctl is-system-running` command rather than in the command's output; all six were corrected before the sealed run. Harness: **still unmitigated** — the sealed suite of 701 tests runs entirely against *fakes*; it has never spoken to a real broker, a real Ditto or a real VM | Micro-pilot before any campaign | A component declared "verified" that has never been executed in the target environment | Treat M2 (unit tests with fakes) as a hypothesis, not a fact. A check that a console echo can satisfy is not evidence: an assertion must read the command's output, never the transcript that contains the command itself. The micro-pilot (smoke → short nominal → dropout → restart) exists precisely to reveal the harness equivalents of these bugs before they cost a campaign |
