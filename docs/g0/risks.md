# Risk register

> **Plan v2.0 adopted 2026-09-18 (QEMU-only execution amendment).** The student adopted [plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) as the execution baseline on 2026-09-18; its evidence classes, integrated-guest risks and schedule govern from that date. No native ARM64 VM could be obtained on 2026-09-17, and native deployment left mandatory scope on 2026-09-18. Provider availability, cost assumptions and dates recorded below are dated records, not current quotations, and the native-host rows are retained for any future native work rather than deleted. **Updated 2026-09-19:** where this register previously said that the supervisors had approved nothing, the position is now split — D007, D014 and the unresolved halves of D004 and D010 are open and unsent, while twelve further items are **reported confirmed by the student**, undated and never recorded as documented supervisor decisions. Neither the adoption nor any reported confirmation closes a gate. **Updated again 2026-09-19 (gate review):** G0 was accepted on that date by the student's own decision, with the project manager's concurrence, for project initiation and baseline alignment ([decision record](../governance/decisions/2026-09-19-g0-closure.md)); it is a dated change of G0's exit scope, not a retroactive pass, and it reallocates the open rows — D007 to G4, the template authenticity to G7, any genuinely unsettled method or claim detail to G4/G6 without a blanket D014 blocker — and leaves the off-machine copy an active resilience action owned by the student (R25). The same review records two findings of the integration battery and the invalid timed attempts of 2026-09-19 against existing identifiers, in the section *Findings recorded on 2026-09-19* below.

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

Updated: 2026-09-18 for the adoption of plan v2.0 (R1, R4, R7, R8, R11, R13,
R28, R29, R31, RA1 and RA12 retargeted at the integrated emulated guest; R4 and
R31 record materialisations of 2026-09-18; the residual risks of the adopted
baseline have their own section below). The sealed unit figure remains
`701 passed`. **The absent native ARM64 measurement host is no longer a
blocking dependency**: it bounds what RQ3 may claim and defers native-boot
evidence to future work.

Previous update: 2026-08-14 (R2/R12/R30 updated with the second clean-checkout
Yocto build; R25 records the verified post-G1 bundle and remaining
off-machine-copy blocker; R27 reflects the renewed state synchronisation; R31
records the PTY predicate defect and five fresh strict passes).

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
| R1 | No Raspberry Pi hardware | High | Low (the scope already excludes a physical Pi) | Both | Mitigated by design | — | Hardware remains unavailable | Functional and integration evidence from the integrated emulated guest; exclude every physical-hardware and native-performance claim |
| R2 | Yocto build slow or unstable | Medium | High | Both | **Materialised, then mitigated** — instability did appear during the first build (WSL2 host-clock drift breaking the `perl` compilation) and was corrected. The first build and the new clean-checkout build at `f0e19d5` each completed all 5,715 BitBake tasks successfully; the second deliberately reused external downloads/sstate and is not a cold-cache claim. Both evidence scopes are sealed in `docs/evidence/g1-yocto-qemu/` | met on 2026-08-11 and reconfirmed 2026-08-14 (v1.0 gate target 2026-08-16 with trigger 2026-08-20, superseded by the plan v1.1 window of 13–18 August — dates retained for the audit trail) | G1 at risk | WSL2 on a Linux filesystem, pinned revisions, minimal image and download cache |
| R3 | Images without ARM64 | Low | High | Both | Mitigating (digests verified from documentation on 2026-08-07; `manifest inspect` on the VM still missing) | 2026-08-23 | `manifest inspect` fails | Replace with a compatible official image; ACA-Py is cut, never emulated |
| R4 | Ditto exceeds resources | Medium | High | Student | **Materialised on 2026-09-18; no mitigation landed** - a memory-cgroup OOM killed the `ditto-things` JVM **during the power-off** of the first end-to-end session, at a 512 MiB container limit. Diagnosis of the same day: the three Ditto services idle at 94-95 % of that limit and reached 98.1 % after a 672-message workload, and a controlled `docker compose stop -t 60` after that workload produced no OOM anywhere in the boot. The corrective work is **open** and is a separate change; no stability is claimed until it lands | before the integrated baseline may be called stable (target 2026-09-25) | OOM or persistent swapping; a service already near its container limit while idle | Graceful stop before power-off; size the container memory limits against the observed usage; keep non-essential services removed. The guest's 8 GiB is an emulator setting, not a demonstrated equivalence to a physical gateway |
| R5 | The scope grows again | Medium | High | Both | Mitigating (audit §15: no scope creep detected) | continuous | A request with no link to the RQs | Enforce mandatory P0 and the explicit exclusions in plan v1.1 §3; require an explicit time trade-off for any proposed addition |
| R6 | Results without provenance | Medium | Critical | Agent | Mitigating (manifests/checksums implemented; still to be exercised in the pilot) | 2026-09-06 (before `exp-v1`) | A metric without `run_id`/manifest | Invalidate the run and repeat it before the data freeze |
| R7 | Late feedback | Medium | High | Student | Open, re-scoped on 2026-09-19 — contact is reported to have occurred: the student reports the state-of-the-art material sent and twelve items confirmed, none of it dated and none of it a documented supervisor decision. The residual exposure is the **turnaround on the rows that remain open** and inside the reported feedback window of 2026-10-09 to 2026-10-14, which is requested and not guaranteed. The reduced alignment package is still a draft | send the reduced package immediately with the revised memo; record every contact attempt | No reply to the recorded alignment request; the feedback window passing without comment | Send the open rows early — D007, D014 and the unresolved halves of D004 and D010 — record every contact attempt and continue only with reversible work; silence is never approval for those rows, and a reported confirmation is never recorded as a documented decision |
| R8 | Writing left to the end | High | Critical | Both | Open (audit §6: 18–22% of the target on 2026-08-08) | 2026-10-01 (chs. 1–4) and 2026-10-08 (full draft), both planning targets | Chapters 1–4 incomplete on 2026-10-01 | Protect a daily writing reserve and cut optional exposition before weakening evidence or expanding implementation scope |

## Additional operational risks

| ID | Risk | Prob. | Impact | Owner | State | Mitigation deadline | Early signal | Mitigation/decision |
|---|---|---|---|---|---|---|---|---|
| R9 | Workspace on Nextcloud/NTFS: builds, virtual environments or Git repositories corrupted or slowed by synchronisation and NTFS file semantics | Medium | High | Student | Partly mitigated (2026-08-10: the workspace left the synchronised Nextcloud folder, which removes the synchronisation component; it remains on NTFS/Windows, so the rule of never building here holds in full. The first Yocto build did run in WSL2 on ext4, as the rule requires) | continuous | Synchronisation conflicts (`... (conflicted copy)`), file locks, slow I/O, builds failing non-deterministically | Never run Yocto builds or the stack from `/mnt/d`/Nextcloud; builds and venvs stay in WSL2 ext4 or on the VM. Copy only final results to the workspace and use `SHA256SUMS` to detect corruption (plan v1.1 §§5 and 7) |
| R10 | Historical 2026-08-10 ARM64-VM trigger | Medium | Critical | Student | **Superseded by R28 and plan v1.1** — retained to preserve the audit trail; the current fact remains that no measurement VM exists | historical trigger elapsed | Any document applies the former 10/12 August cut rule as if it were current | Do not delete the historical record. **Dated note of 2026-09-18:** the 48-hour university/public-host rule is withdrawn from mandatory scope and deferred with the native route (adopted plan, section 4.4), so it applies only to future native work that a new budget decision (D012) authorises; nothing in this row is a current obligation and only R28 describes the present state. The generic checklist remains in [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md) as a checklist for that future work |
| R11 | Python version divergence: Windows host with 3.14, container/runtime environment and `pyproject` support from 3.11 | Medium | Medium | Agent | Mitigating — CI covers 3.11 and 3.14; the hashed runtime lock for the controller image is still absent, and the image deployed in the guest on 2026-09-18 installed with `pip install .` | runtime lock before `exp-v1` (target 2026-09-29) | Tests pass in one environment and fail in another; dependencies without target-architecture wheels; different deprecation warnings | Keep CI on 3.11/3.14, validate behaviour on Linux, and generate the hashed runtime lock for the controller image deployed in the guest before `exp-v1`, with recorded `pip check`, image digests and a guest manifest; an image with unlocked dependencies is not admissible for thesis measurements, and Windows-only validation is not target evidence |
| R12 | Insufficient disk space/memory on the host for the Yocto build in WSL2 | Medium | High | Student | Mitigated for two builds — both completed in WSL2 on ext4 without exhausting disk or memory; the post-campaign capture on 2026-08-14 recorded 818 GiB available. The risk still applies to every rebuild | 2026-08-09/2026-08-10 (before the 1st build) — met and reconfirmed 2026-08-14 | `df -h` below ~120 GB free before the build; memory pressure/OOM in WSL during BitBake | Check free space before every build; clean `tmp/` between builds if needed, keeping `downloads/` and `sstate-cache`; retain the `.wslconfig` memory/swap limits |
| R13 | **Host contention contaminates the emulated observations** — the load generator and the harness share the physical workstation with the QEMU process, so keeping them outside the guest does not establish physical resource isolation. The original wording of this risk, about performance variability of a shared-vCPU cloud VM, is retained for any future native work | High | Medium | Both | Open — the contention exists by construction in the adopted environment. *Related finding recorded on 2026-09-19: the controller does not keep up with the nominal publishing rate under emulation (see the section on findings recorded on 2026-09-19).* | close before `exp-v1` (target 2026-09-29) | Anomalous dispersion between repeated runs; host CPU saturation while a run is in progress | Record the achieved load, the host and WSL configuration and the contention itself in every run manifest; distinguish guest and container readings from host QEMU-process readings and never convert between them by an assumed emulation slowdown factor; report timing as informational and labelled emulated. **Future native work only:** record tenancy/shared-vCPU, use a non-burstable host, repetitions and 95% confidence intervals, and exclude only proven infrastructure or instrumentation failures, never a run merely because it is slow |
| R14 | Supervisors unavailable in August delays closing the scientific and administrative decisions | High | High | Student | Open, narrowed on 2026-09-19 — the August unavailability is history; the student now reports contact and twelve confirmations, all undated and none of them a documented supervisor decision. What is still undecided is D007, D014 and the unresolved halves of D004 and D010, for which no sent request or reply is recorded | send the reduced package immediately; record every contact attempt | No reply after a recorded contact attempt | Request asynchronous decisions on the open rows only, record contacts in the LOG and continue reversible work only. D014 and the template-authenticity half of D004 still block the final thesis and D007 blocks `exp-v1`; silence is not approval for them. *Reallocated by the G0 decision of 2026-09-19: D007 still blocks `exp-v1` (G4) and the template authenticity is owed at G7, while D014 is no longer a blanket blocker of the final thesis — its genuinely unsettled detail is tracked at G4/G6* |
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
| R25 | Loss of repository or evidence provenance | Medium | Critical | Student (the off-machine copy; *previously "Both", changed by the G0 decision of 2026-09-19*) | **Mitigating** — *G0 was accepted on 2026-09-19 without this copy: verifying it, its hash and the restore path is reallocated to an active resilience action owned by the student, to be done promptly and required at G7, and the decision neither verifies nor waives it.* The private remote exists; ten inventoried bundles verify, plus one unversioned post-PR-#25 handover bundle (`egw-20260814-post-pr25-merge.bundle`, SHA-256 `53014902…`, complete history to `2dafae1`) — the current handover artefact for the off-machine copy; exact-tree rewrite mappings are recorded; protected tags `evidence/g1-yocto-build-5770c0a` and `evidence/g1-bringup-driver-367c929` preserve the exact preliminary build and its driver lineage. The copy stays pending until destination-side hash verification and the restore drill are completed. No verified off-machine copy is recorded — the deadline of "before G1 acceptance" was missed: G1 was accepted on 2026-08-14 with the copy still outstanding, which sharpens rather than retires this risk | off-machine copy — immediate | All bundles remain on the same physical machine | Copy the current bundle off-machine, verify it there and record its SHA-256/location without publishing restricted history |
| R26 | Documentation diverges from the contract (drift after CONTRACTS v1.1: references to v1.0, idempotency without `run_id` scope) | High | Medium/High | Agent | Mitigating — diagrams/ch. 4 synchronisation completed on 2026-08-08; impact checklist added | continuous (at every contract change) | CONTRACTS changes without updating thesis/diagrams/READMEs | Impact checklist per ADR/contract change; drift check twice a week (audit §14.2) |
| R27 | The management state induces false confidence (PROGRESS/backlog/plan contradicting one another; hybrid states outside the taxonomy) | High | High | Agent | Mitigating — PROGRESS is the single source and the backlog has no state. Drift materialised again when the clean build/five boots made the 2026-08-13 wording obsolete; PROGRESS, both claim matrices, the Yocto guide, LOG and this register were synchronised in the same evidence change while retaining 0/15 accepted and, at that date, G1 pending; after the 2026-08-14 acceptance, a review pass found and fixed six further records still describing G1 as pending — the risk recurs at every state change and the mitigation remains synchronising every dependent record in the same change | review at every work block and at every gate | Divergent state documents | Single source of state in `PROGRESS.md` (Implemented/Verified/Accepted model); backlog with actions only; update all dependent records in the same evidence PR |

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
| RA1 | Email/rules/VM/WSL2 delay G0–G2 | Student | **Open — student action** | Largely overtaken by events: WSL2 with Ubuntu 24.04.4 LTS is installed and operational on ext4 and built both images (see R30), and since 2026-09-18 the integrated emulated guest is the adopted environment, so the absent native ARM64 VM blocks no gate (see R28). Narrowed on 2026-09-19: what remains is the **reduced** alignment package — D007, D014 and the unresolved halves of D004 and D010 — the other rows being reported confirmed by the student rather than answered in a documented decision. Overlaps R10 and R14; no change in the repository closes it. *Note of 2026-09-19: G0 was accepted on that date by the student's decision, so this risk no longer delays G0; the rows it waits on are reallocated to G4 (D007) and G7 (the template authenticity), with any unsettled method or claim detail tracked at G4/G6. The state stays with the student* |
| RA2 | The academic claim of an executed protocol remains in chapter 1 | Agent | **Mitigated** (documentary) | "pre-registered" replaced by "pre-specified, frozen before data collection" in chs. 1/2/6 and in the abstracts (block P2); `grep -r "pre-registered" thesis/latex/` with no occurrences on 2026-08-10. Ch. 5 still carries no numbers, with `\todo{pending data-v1}` |
| RA3 | A complete PDF sent with placeholders and TODOs | Student | **Partly mitigated** | The standalone extract `thesis/latex/ch2_supervisor_draft.tex` (+ compiled PDF) exists precisely to avoid sending `main.pdf` with placeholders. **Updated 2026-09-19:** the student reports that the state-of-the-art material was sent, so the sending this row waited on is reported to have happened. No date, copy or acknowledgement is held, so none is recorded and no `sent_at` is written anywhere; the report is the student's and is not a documented supervisor decision. The residual concern is unchanged — no complete PDF with placeholders is ever sent |
| RA4 | "Verified sources" read as full-text reading | Agent | **Mitigated** (documentary) | [`../../PROGRESS.md`](../../PROGRESS.md) now declares 7 sources read in full text (S001, S004–S009) and 18 by title/abstract only; the count is read from the `stage` column of `thesis/research/study_selection.csv` (7 `full_text`, 18 `title_abstract`). "Verified" now refers only to the source metadata. It does not cover R17 (institutional queries), which stays with the student |
| RA5 | Invalid runs enter the results | Agent | **Mitigated at M2** | `src/egw_experiments/analyze.py` excludes from the aggregation those runs whose manifest `validity` exists and is not `valid`; the exclusion requires a proven cause (cloud/instrumentation/configuration) and never the outcome of the run. Reinforced in block P5: the directory's `SHA256SUMS` is verified **before** any aggregation (column `integrity_ok` in `per_run.csv`), and both integrity-failing runs and **unsealed** runs of timed conditions stay out of summaries, saturation, acceptance and figures, with an explicit warning. Known limitation handled in block P5.4: this gate decides about the run, not about the numerical sanity of each sample — see R29 (technical-audit round). Live proof pending on the VM |
| RA6 | Local resources treated as ARM resources | Agent | **Mitigated at M2** | Mandatory host-provenance column in `resources.csv`; SUT collection by `src/deployment/scripts/collect-resources.sh` on the VM, ingested through `run --resources-from`; the local sampler is opt-in (`--local-resources`) and is marked with `resource_source` (`local-dev` invalidates a timed run). Block P5 added semantic validation of the series at analysis time (unusable rows discarded and **counted** by reason: missing column, empty field, unreadable timestamp, non-numeric value, time going backwards), visible in `resources_rows_dropped`/`metrics_rows_dropped`. Equivalent to R18; live proof pending |
| RA7 | C10–C13 pass without completeness | Agent | **Mitigated at M2** | `processed/acceptance_by_condition.csv` evaluates **every** planned condition with an explicit completeness gate (`runs_complete`); a planned condition with zero valid runs does not pass. Block P5 replaced the count with a comparison of the **set of identities** (`run_id` + repetition + seed + rate, per load level in the sweep) against the frozen plan, when the plan is supplied to the analysis. The reach of this guarantee depends on the plan actually arriving at the analysis through the delivered command — that was the gap found on 2026-08-10 and recorded as R28 (technical-audit round). Live proof pending |
| RA8 | Queue/CPU with gaps produce a false sustained window | Agent | **Mitigated at M2** | The sustained-window detectors only count intervals between consecutive samples within the maximum admitted gap; each run reports `resources_coverage_pct`/`metrics_coverage_pct` in `per_run.csv`; block P5 added the *head gap* (a series that only starts sampling once already inside the window is not continuous evidence), the count of **distinct instants** inside the measured window, and a minimum below which the criterion fails instead of passing silently. The statistical thresholds, the percentiles, the CI method and the 60 s window were **not** changed in any of these blocks — only the instrumentation changed. Residual dependency: series with non-finite values (R29, technical-audit round) attack exactly these calculations |
| RA9 | Raw resources overwritten | Agent | **Mitigated at M2** | `raw/<run_id>/` directories are write-once: with `SHA256SUMS` present the directory is sealed and any write with different content is refused (`run.py`) |
| RA10 | A manual campaign fails on order or completeness | Agent | **Mitigated at M2** | `campaign` subcommand (`src/egw_experiments/campaign.py`): runs the frozen plan in order, with resume, `blocked` classification for unsealed directories, recorded cooldowns and `campaign_log.jsonl`. Live proof pending |
| RA11 | Evidence of 452 not reproducible per commit | Agent | **Closed** | The pattern is established and repeated: every block re-runs the suite over a clean HEAD and seals the evidence in its own directory identified by the commit. The current sealed record is `docs/evidence/tests/2026-08-11-head-4e67717/` (`701 passed`). The earlier seals are kept for traceability and are **historical**, each tied to the commit it tested — `683` (`05166eb`), `618` (`19d74ff`), `593` (commit `57228e178c784987492ca71a708740a5a85d0d95`, tree `e3e4fc84546662a7ecc650dbfd79596e48dab6a3`) and `515` (commit `ca445a31e5d146cf0c214b3cd4a23a95a48b5289`, tree `b767b229e295b9453cbc2efcbfd0122bf8409d38`) — and none of them is the current figure. All of them have an empty `git status --porcelain` and `SHA256SUMS`. Hygiene note, with no effect on reproducibility: the `2026-08-08` prefix of the `57228e1` directory is the block's date, not the run's |
| RA12 | Dev lock mistaken for a runtime lock | Both | **Partly mitigated** | The header of `src/requirements.lock` identifies it as a **development** lock, without hashes, generated in the Windows venv, and names the sealed suite it was verified against (currently the sealed record of `701 passed`). Blocking dependency: the hashed runtime lock must be generated during the controller-image build on the build and provisioning host for the guest, and archived before `exp-v1`; the image deployed in the guest on 2026-09-18 installed with `pip install .`, unlocked, so until the lock exists it is forbidden to assert "reproducible rebuild" and that image is not admissible for thesis measurements. Equivalent to R24 |
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

## Residual risks of the adopted baseline (2026-09-18)

The adoption of plan v2.0 with the QEMU-only execution amendment removes the
procurement blocker and replaces it with three residual risks. They are stated
here against the **existing** identifiers rather than as new ones, because the
identifier range `R1`-`R33` and `RA1`-`RA15` is frozen and cited from
[`../governance/language-policy.md`](../governance/language-policy.md); minting
new identifiers requires extending that range in the same change.

| Residual risk | Where it is registered | Position under the adopted plan |
|---|---|---|
| **No native evidence exists, and none will be produced** | R28, R29, RA1 and the platform section of `PROGRESS.md` | Accepted consequence, not a blocker. It bounds RQ3 to the specified emulated environment and makes the absence of native performance, capacity and hardware statements an explicit limitation of the dissertation. Native deployment stays documented, unverified future work with its own protocol and data |
| **The wording of the native-evidence limitation and of claims about emulated figures is not agreed** | R7, R14 and decision D014 | Open and outside the student's control. The student reports supervisor approval to proceed with the QEMU tests and approval of RQ3 evaluated in QEMU, so the QEMU evaluation scope of RQ3 is reported approved (reported by the student, undated, not a documented supervisor decision) and is not re-requested. The open part of D014 is only the wording of the native-evidence limitation and of claims about emulated timing and resource figures, which remain functional and integration evidence only and never an ARM64 hardware performance conclusion; numerical criteria belong to D007. Ask for that wording in the reduced alignment package and track it specifically at G4/G6, without a blanket D014 blocker; silence is never approval, and the evaluation chapter does not present that wording as agreed before a reply. *(Corrected 2026-09-19, following the G0 decision of that day; previously this row was headed "Academic use of emulated results is not agreed" and listed that academic use as open, asking the question in the reduced alignment package.)* Every reported confirmation remains reported, undated and not a documented supervisor decision |
| **The schedule has no slack and no measured effort basis** | R8, R14 and RA15 (materialised) | The submission target of 2026-10-20 and the final deadline of 2026-10-31 rest on a first-party statement; the 225-345 hour estimate of 2026-09-16 is superseded pending the student's re-estimate, and `actual_h`, `remaining_h` and `forecast` remain empty, so no completion forecast exists. Two loads were added on 2026-09-19 without any slack being added: the **scoping-review package**, whose protocol/search/synthesis targets of 2026-09-21, 2026-09-26 and 2026-09-30 have to feed the chapters sent on 2026-10-01 and are to be re-estimated against the real corpus at the 2026-09-21 checkpoint; and the **95-run attempt target**, whose 70 simulator-driven runs alone carry a historical 33.17-hour logistics floor, excluding the 25 operator-driven runs, setup, transfers, analysis and retries, so the campaign window of 2026-09-30 to 2026-10-02 is conditional rather than comfortably provisioned. Apply the reforecast triggers of the adopted plan rather than moving a date silently, and replan explicitly if the pilot's fresh QEMU forecast does not fit |

Two further risks that the adopted environment creates are registered in place:
host contention between the load generator and the QEMU process on the same
workstation (R13), and the unlocked Python dependencies of the controller image
deployed in the guest (R11, R24, RA12), which must be resolved before the
protocol freeze.

## Findings recorded on 2026-09-19 (integration battery and diagnostic attempts)

The integration battery of 2026-09-18 and the two invalid timed attempts of
2026-09-19 (`smoke_sequence-r02` and `controller_restart-r02`) exposed two
risks. Like the residual risks above, they are registered against existing
identifiers, because the identifier range is frozen. The counts are
diagnostic: they come from invalid runs, and the guest-side event logs and
container logs were not read. Nothing here is a campaign result or admits a
claim, and test acceptance stays paused at the student's request.

| Finding | Where it is registered | Position |
|---|---|---|
| **A controller restart appears to discard the controller's in-memory queue** | R31 (a defect that only real execution reveals); claim C12 and RQ2 | Open — a design and data-path issue, not only emulator speed. In `controller_restart-r02`, of the 2,901 published messages without an accepted record in the fetched log, about 765 fit the backlog, but about 2,136 do not: 1,765 were published before the restart and about 371 during the outage. The MQTT client acknowledges on enqueue, the queue is in memory and the client uses a clean session with a fixed client id, so messages queued or published while no session existed would not survive a restart. Missing fetched records are not proof of permanent loss. Mitigation: confirm from the guest-side logs after resumption, take a separate, recorded design decision on the data path, and collect no C12 evidence before it. The lifecycle-aware rule for a deliberate restart is proposed separately, not adopted, in [the acceptance and protocol proposals](../governance/proposals/acceptance_protocol_update_2026-09-19.md) |
| **The controller does not keep up with the nominal publishing rate under emulation** | R13 (emulated observations), R23 (criteria after the freeze); the delivery criteria of claims C06, C10, C11, C12 and C14 | Open. Under QEMU/TCG the controller — a single consumer processing messages sequentially against Ditto — sustained about 3-8 acknowledgements per second against a publishing rate of 11.2 msg/s; its queue grew by 4.7-10.6 per second; latency p50 50-86 s and p95 69-157 s (emulated, informational); the broker kept up (median transit 2-14 ms). The late confirmations of tests 3, 5 and 7 of 2026-09-18 are consistent with the same backlog, and test 5 fails its deadline criterion on it (326 of 2,016 valid events confirmed late). Mitigation: diagnose under unchanged deadline semantics; lower a future workload only through an explicit prospective QEMU protocol decision at G4, never by moving a deadline after lateness is observed; retain valid failures as results instead of repeating until a pass |

## Link to the current contingency policy

The planned submission is 2026-10-20 and the final delivery deadline is
2026-10-31; 2026-10-21 to 2026-10-31 is a contingency window for essential
corrections and submission recovery only, never the default delivery period and
never time for optional scope. The source of both dates is the student's
first-party confirmation of 2026-09-18 after discussing them with the
supervisors; no administrative document is held in the repository. Every
milestone date is a planning target. The **requirement** to use the
institution-supplied template is reported confirmed by the student, undated and
not a documented supervisor decision; the authenticity of the local copy, the
cover and the front-matter rules stay in the reduced alignment package, with no
recorded send or supervisor reply. The cut rules therefore reduce scope or record a
limitation when a gate is missed; they do not silently move the deadline. The
existing image and two bring-up boots remain preliminary evidence. The clean
identified build and new five-boot strict set were produced and sealed on
2026-08-14; gate G1 was accepted later the same day (decision in
[`../governance/gate_decision_log.md`](../governance/gate_decision_log.md),
functional platform layer only) while the second-operator requirement of D006 is
reported waived, recorded on 2026-09-18 (the date of the record, never of the
waiver, for which none was reported) — reported by the student, not
documented — so no
reconstruction is owed and the wording stays *versioned* and *repeatable build by
the author*. The 2026-09-30 baseline and the 2026-09-29 internal cut-off
survive only in the archived plan v1.2 and in dated historical records.

---

## Risks added on 2026-08-10/2026-08-11 (real execution) — R28–R31

| ID | Risk | Prob. | Impact | Owner | State | Deadline | Early signal | Mitigation |
|---|---|---|---|---|---|---|---|---|
| **R28** | **A native non-burstable ARM64 host is absent.** Historical attempts with Oracle, Hetzner and Azure did not yield such a host; they do not establish current capacity or price | High — realised | **Bounds RQ3; no longer critical to delivery** | Both | **Materialised, re-scoped on 2026-09-18** — no university request/reply, current public quotation, provisioned host or environment capture is recorded, and none is requested by the adopted plan. Since the adoption of plan v2.0 with the QEMU-only execution amendment this **no longer blocks G2 onwards**: it bounds what RQ3 may claim and defers native-boot evidence to future work. GitHub issue #11 tracks the platform dependency as future work | none — it gates nothing in the adopted plan | A document or chapter that presents an emulated observation as native ARM64 performance or capacity | State the absence as an explicit limitation wherever a deployment or performance conclusion would otherwise be drawn, and keep emulated and any future native runs out of one aggregate. **Future native work only, and only if a new budget decision (D012) authorises it:** request the university host and record the request; after 48 hours without confirmation obtain a current quotation for a non-burstable public ARM64 host, with `c6g.xlarge` as the default fallback; confirm the total forecast is at most EUR 30 before creating anything, otherwise stop and escalate; and record provider, region, CPU, tenancy/shared-vCPU, kernel, OS, Docker, image digests and clock provenance |
| **R29** | **Use of a burstable instance as the measurement platform** — any available B/t4g-class SKU uses CPU-credit behaviour that can throttle the processor and contaminate RQ3 | High if not barred | **Critical for RQ3** | Agent | **Deferred with the native route on 2026-09-18**: no host of any class is provisioned or requested, so the risk cannot materialise under the adopted plan. The protocol boundary is retained unchanged for any future native work — a burstable host may serve functional integration only, and no number from it enters the dissertation. D008 remains `proposed_not_sent` and is superseded in substance by the evidence classes of the adopted plan | permanent, if native work resumes | Any timed run whose `sut_environment.json` reports a burstable B/t4g family | Exclude B/t4g-class hosts from all measured runs and automatically reject their evidence for RQ3. Run the official campaign only on a recorded non-burstable native ARM64 host; retain any burstable result solely as non-citable integration evidence (plan v1.1 §§3.1 and 5) |
| **R30** | **Build-host drift over time** — `wsl --install -d Ubuntu` started installing Ubuntu 26.04 (Python 3.14), outside the validated Scarthgap envelope (2024-04) | High | High | Both | **Materialised and mitigated (2026-08-10; reconfirmed 2026-08-14)** — Ubuntu 26.04 was rejected first, precisely because it ships Python 3.14, outside the tested envelope of Yocto Scarthgap; the guide now requires installing by name (`-d Ubuntu-24.04`). WSL2 with **Ubuntu 24.04.4 LTS** on ext4 produced both the preliminary image and the clean-checkout build at `f0e19d5`; the second capsule records the host/tool/filesystem identity | permanent | A build that fails in BitBake before the parse | The same command gives different hosts depending on the date: repeatability requires pinning the host version, not only the layers |
| **R31** | **Defects that only real execution reveals** — the first build found two bugs in Yocto work classified as verified until then: a `perl` build failure first misdiagnosed as a parallel-make race — the demonstrated cause was WSL2 host-clock drift, consistent with R2 — and `DL_DIR`/`SSTATE_DIR` resolving to a temporary kas folder | **Materialised in build and boot execution, including the strict rerun**; **likely** (harness) | High | Agent | Yocto faults corrected (`e83fb24`, `c0ebf7c`). The preliminary automated boots exposed six more defects before their seal. The first 2026-08-14 strict attempt then exposed a seventh instrumentation defect: the guest returned exact `STATE=running`, but the predicate rejected doubled PTY carriage returns. The attempt remains `fail`; PR #18/merge `9fe38ff` corrected the predicate and five fresh runs each passed 7/7. This mitigates the observed driver defect but closes no gate and validates no claim. The sealed 701-test suite still uses fakes and has never spoken to a real broker or Ditto. **The risk materialised again on 2026-09-18**: the first bounded end-to-end flow in the emulated guest exposed two real defects that every prior check had missed — the controller was attached to the wrong Compose network (`9ffd365`) and the host shell inherited a relative schema directory (`dc6d8bb`, `22fb0a9`), both fixed on `dev`. That is the risk behaving exactly as predicted; it closes no gate and validates no claim. **Recorded again on 2026-09-19:** the controller-restart attempt `controller_restart-r02` indicates that a restart discards the controller's in-memory queue — a design and data-path finding that awaits confirmation from the guest-side logs (section *Findings recorded on 2026-09-19*) | Micro-pilot before any campaign | A component declared "verified" that has never been executed in the target environment | Treat M2 as a hypothesis until target execution. Preserve failed attempts, fix instrumentation before rerunning, require new identities, and use the micro-pilot (smoke → nominal → dropout → restart) to reveal harness equivalents before the official campaign |
