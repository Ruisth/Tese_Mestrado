# Actionable backlog by gate (G0→G7)

> **2026-09-16 integrated-Yocto planning amendment (proposal).** Revised work packages, prerequisites and forecast dates are proposed in [plan v2.0, sections 4-6](../governance/proposals/INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md), a proposal, not in force; its section 10 records that no native ARM64 VM could be obtained on 2026-09-17, the emulated QEMU/TCG-first order of work and the evidence classes. [Plan v1.2](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) remains the plan in force until the student decides after consulting the supervisors, so the dated August backlog below is kept unchanged; its elapsed dates are not future commitments. Current state remains in PROGRESS.md.

> **This file owns actions only**: required work, expected evidence,
> dependencies and cut rules. The versioned schedule and scope authority is
> the [integrated development plan v1.2](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).
> The current state of every deliverable and gate lives exclusively in
> [`../../PROGRESS.md`](../../PROGRESS.md); do not record completion,
> implementation status, execution results or evidence counts here.
>
> Recurring dependencies: **WSL2 ext4** means Ubuntu 24.04 on WSL2 with the
> Yocto checkout and build directory on a Linux filesystem (see
> [`../setup/wsl2_ubuntu_yocto.md`](../setup/wsl2_ubuntu_yocto.md)); **ARM64
> measurement VM** means a native, non-burstable ARM64 environment with 4
> vCPU, 8 GiB RAM and at least 80 GB. A burstable ARM64 host may support G2
> integration only and may not produce dissertation measurements.

## Rules that apply to every gate

- Close a gate only through a dated decision linked from `PROGRESS.md`;
  passing checks or producing an artefact does not close a gate by itself.
- If the university does not confirm the measurement host within 48 hours of
  the request, obtain a quotation for a public non-burstable ARM64 instance.
  Use AWS `c6g.xlarge` as the default fallback and do not provision above the
  authorised EUR 30 total ceiling.
- If G2 has no valid vertical slice by 25 August, record a serious September
  risk and reforecast without adding scope.
- After G4, do not change metrics, thresholds, conditions or exclusion rules.
  An evidence-invalidating defect requires a new protocol/data version and
  reruns of the affected conditions under new run identities.
- After G5, permit no feature work. Record missing evidence as a limitation;
  never replace it with an inferred result.
- Supervisor silence is not approval. D001 and D004 block the final academic
  release; D007 blocks `exp-v1`.
- Keep ACA-Py, DIDComm, Fabric, Indy, IPFS, wallets and executable
  SSI/blockchain flows outside P0 and outside any September or unauthorised
  October contingency.
- Preserve every failed attempt and raw artefact write-once. A repetition
  always receives a new predefined run identity.

## Source-faithful manuscript maintenance

These actions govern the 2026-09-17 Word-source conversion and subsequent
manuscript work. They do not revise the gate schedule or acceptance rules
below; current deliverable state remains in
[`PROGRESS.md`](../../PROGRESS.md).

| Action | Expected evidence | Dependencies |
|---|---|---|
| Preserve the supplied Word manuscript in the canonical LaTeX source and regenerate its Markdown mirror | Source SHA-256, chapter/table/figure/reference inventory, source-fidelity checks and build record in [WORD_IMPORT.md](../../thesis/latex/WORD_IMPORT.md) and [word-import-manifest.json](../../thesis/latex/word-import-manifest.json) | Supplied DOCX and `Template_LaTeX`; reproducible LaTeX/Pandoc toolchain |
| Keep unprovided chapters and front matter empty until separately authorised content is available | Chapters 3–6 contain headings/empty sections only; no restored old prose, sample text, TODOs or invented completion text | Explicitly supplied or authorised manuscript content; existing evidence-admission rules |
| Review differences between the imported title/RQs/integrated-Yocto wording and the governance baseline separately | Dated alignment decision; no inference of implementation or supervisor approval from a format conversion | D001 and applicable supervisor decisions; unchanged governance controls |
| Verify the 33 imported reference strings through the research protocol before academic release | Primary-source checks and research-register updates, distinguishing metadata verification from full-text reading | Access to the cited sources; separately authorised academic revision |

## G0 — Authority and provenance (13–15 August)

**Cut rule:** obtain the supervisor decisions and initiate the ARM64 host
request without treating silence as approval. Apply the 48-hour public-host
fallback rule above. The required result is an alignment request covering
D001–D008, versioned authority/provenance records and an initiated university
ARM64 request.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Obtain explicit validation of scope, title, objective, RQs and two-layer architecture | Supervisor reply and dated D001 decision linked from `PROGRESS.md`; [`scope_and_rqs.md`](scope_and_rqs.md) aligned with the decision | Supervisors |
| Send the consolidated alignment email with Chapter 2 and D001–D008 | Sent-message copy/date; `sent_at` and response references in the canonical decision log | Student action; [`supervisor_email_g0.md`](supervisor_email_g0.md); Chapter 2 attachment |
| Hold a short alignment meeting when written decisions remain unresolved | Minutes recording each decision, owner and follow-up date | Supervisors' availability |
| Maintain an Ubuntu 24.04 WSL2 ext4 Yocto environment | `wsl -l -v`, filesystem proof for the build directory and environment capture | Student machine; WSL2 ext4 guide |
| Request a university ARM64 measurement host and apply the 48-hour fallback rule | Request/reply record; price quotation before provisioning; provider, region, CPU, tenancy/shared-vCPU, kernel, OS and clock provenance after provisioning | University contact or student cloud account; EUR 30 ceiling; [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md) as a generic checklist only |
| Maintain the claim→evidence matrix | [`../claim_evidence_matrix.csv`](../claim_evidence_matrix.csv) with every public claim mapped to admissible evidence or an explicit limitation | Scientific framing and evidence policy |
| Maintain this action backlog and the risk register | Reviewed backlog plus [`risks.md`](risks.md), with operational state recorded only in `PROGRESS.md` | Gate reviews |
| Exclude unsupported results from the active dissertation | Chapters 5–6 contain no number or conclusion without admitted evidence; exclusion rationale recorded | Claim→evidence review |
| Preserve governance and repository provenance | Protected evidence tag, verified bundle/checksum inventory, source register and rewrite-equivalence record | Git/GitHub access; off-machine storage for the final bundle |

## G1 — Yocto/QEMU functional platform (13–18 August)

**Cut rule:** require a clean identified build and five strict unattended
boots. Each accepted boot must report exactly `systemd=running`, zero failed
units, the required network/runtime assertions and a clean shutdown. Reduce
the image to a minimal runtime platform if the build or boot path cannot meet
the gate; QEMU evidence never supports performance claims.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Freeze the ARM64 measurement environment specification | Environment manifest covering provider, region, CPU, kernel, OS, tenancy/shared-vCPU and clock | ARM64 measurement VM |
| Maintain the Scarthgap 5.0.19 `qemuarm64` kas manifest with exact layer tags/commits | `kas dump` and source revisions reproducible from a clean checkout | WSL2 ext4 |
| Produce a clean, identified `egw-image` build | Build record, package manifest, commit identity and verified checksums | WSL2 ext4; sufficient Linux-filesystem storage |
| Run the five-boot strict G1 acceptance campaign | Five distinct console/result pairs, strict assertion summaries, clean-shutdown evidence and verified `SHA256SUMS` | Identified build; strict unattended boot driver |
| Preserve preliminary bring-up evidence separately from the acceptance campaign | Immutable evidence inventory and provenance note that prevents preliminary artefacts from being substituted for the strict campaign | Evidence-integrity tooling |
| Verify `linux/arm64` support for every deployment image by pinned digest | Archived `docker manifest inspect` output per image | Network access; image lock; ARM64 deployment review |
| Update the `egw-image.bb` DESCRIPTION metadata (it still says "two QEMU boots") **at the next Yocto functional rebuild — never as a standalone edit** (changing the recipe changes its checksum and forces a rebuild), and no later than the release candidate (G7) | Corrected DESCRIPTION in the rebuild's recipe; a note that the existing G1 evidence remains pinned to the original recipe and is not invalidated | Next functional Yocto rebuild |
| Complete institutional searches and full-text verification for claims used in Chapters 1–2 | Search exports, selection decisions and audited bibliography in `thesis/research/` | Institutional IEEE/ACM/Scopus or Web of Science access |

## G2 — Live vertical slice (15–23 August)

**Cut rule:** require a native ARM64 deployment with TLS and an inspectable
wearable→MQTT→controller→Ditto→API trace. If the slice cannot be obtained,
cut auxiliary APIs rather than expand scope; apply the 25 August serious-risk
rule above.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Deploy the minimal ARM64 compose stack: Mosquitto TLS, Ditto, MongoDB and controller | Clean `docker compose up`; health/readiness output; pinned image digests; runtime lock and `pip check` record | ARM64 host; operational certificates and secrets |
| Exercise the MQTT→Ditto controller against real services | TLS broker connection, accepted/rejected event records and a real Ditto twin update | Live compose stack |
| Execute the wearable→MQTT→controller→Ditto vertical slice | `sent_events.jsonl`, `events.jsonl` and `GET /twins/{device_id}` showing the expected materialised state | Controller, broker, Ditto and simulator |
| Run the simulator `smoke` scenario against the real broker | Simulator manifest and write-once raw output for a live run | Live compose stack |
| Add and run live integration tests | Persisted Linux test report containing at least one real MQTT/Ditto integration path; fakes remain unit evidence only | ARM64 integration environment |
| Advance Chapters 1–3 and the logical two-layer deployment diagram | Compiling thesis sources and editable diagrams with no unsupported result claims | Supervisor decisions D001–D004 |

## G3 — P0 feature freeze (24–30 August)

**Cut rule:** freeze P0 at the local digital-twin core. Require three wearable
types and the mandatory nominal, invalid, reconnect, restart and failure
behaviours to run live with frozen CONTRACTS v1.1 and no open P0 defect.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Run three concurrent synthetic wearable types | Live run manifest, events and three queryable twin states | G2 vertical slice |
| Execute every mandatory scenario, including nominal, load, invalid payload, dropout/reconnect, restart and soak preparation | One write-once manifest/evidence set per scenario and a demonstrated real disconnection/recovery path | ARM64 live stack |
| Validate reconnect, retry and backpressure behaviour | Live integration records, consistent counters and documented recovery outcome | Controller and broker |
| Exercise the corrected metrics and experimental harness end to end | SUT-side resources, controller metrics, automatically collected events, valid measured windows and CLI-driven analysis | Live stack; corrected harness |
| Run the complete unit, integration and E2E test suite | Persisted Linux report with unit and live `integration` results separated | ARM64 integration environment |
| Execute a pilot soak | Pilot-only logs, resources and integrity report; no pilot number cited in the dissertation | Stable live stack |
| Complete Chapter 3 and advance Chapter 4; synchronise ADRs and diagrams with CONTRACTS v1.1 | Compiling thesis, editable diagrams and ADR index with consistent scope/interfaces | Feature-frozen P0 |

## G4 — Experimental freeze, tag `exp-v1` (31 August–6 September)

**Cut rule:** require a complete non-citable micro-pilot and seal environment,
protocol, predefined run identities, thresholds, exclusion rules and analysis.
D007 must be decided before `exp-v1`. After the tag, apply the protocol-change
rule above.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Reproduce build and live smoke from a clean checkout | Clean-clone record covering dependency installation, build and E2E smoke | WSL2 ext4; ARM64 host |
| Generate and enforce the integral ARM64 Python runtime lock | Committed hash lock including build dependencies; Docker install with `--require-hashes`, `--no-build-isolation` and `--no-deps`; image digest and archived `pip check` output | Native ARM64 host; pinned base image |
| Apply correction-only changes after feature freeze | Identified commits linked to defects; no new feature scope | Frozen P0 |
| Execute the complete micro-pilot | Pilot raw data, manifests, environment records and checksums for every condition; pilot data marked non-citable | ARM64 measurement VM; corrected harness |
| Regenerate analysis from pilot raw data through the delivered CLI | `processed/` and `figures/` produced by one documented command, including external runs or a documented exclusion | Complete micro-pilot |
| Complete Chapters 1–4 and the evaluation skeleton | Clean thesis build with methods, protocol and limitations but no invented results | D001, D003, D004 and D007 |
| Freeze protocol and predefined run identities as `exp-v1` | Annotated tag and checksumed protocol/run-plan package | All G4 acceptance evidence |

## G5 — Data freeze, tag `data-v1` (7–13 September)

**Cut rule:** require the complete predefined 95-run campaign, including
soak, with write-once raw data, environment manifests and verified checksums.
An optional condition may be cut only as a documented limitation; never fill
an evidence gap with an unsupported conclusion.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Execute the frozen 95-run campaign, covering functional, cold-start, twin-creation, nominal, fault/reconnect/restart, load/saturation and soak conditions | `experiments/results/raw/<run_id>/` for every predefined identity, each with manifest, environment, valid measurement window and verified `SHA256SUMS` | ARM64 measurement VM; `exp-v1` |
| Preserve failures and rerun only evidence-invalidated conditions under new identities | Failure artefacts retained; dated deviation/exclusion record; replacement identity linked to the original attempt | Frozen protocol-change rule |
| Validate all raw data and regenerate analysis outputs | Admission report plus regenerated `processed/` and `figures/`, with provenance and checksum validation | Complete campaign |
| Write the experimental setup and limitations | Thesis text tracing environment, protocol deviations and limitations to evidence | Admitted campaign evidence |
| Freeze admitted data as `data-v1` and keep `raw/` immutable | Annotated tag, verified checksums and data-freeze decision linked from `PROGRESS.md` | Complete validation |

## G6 — Analysis and full draft (14–18 September)

**Cut rule:** require every chapter, figure and RQ answer to exist and derive
only from admitted `data-v1` raw evidence. Permit analysis and writing work,
not features.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Reproduce analysis solely from admitted sealed raw data | Documented command, admission log, tables, figures and confidence intervals regenerated from `data-v1` | `data-v1` |
| Complete Chapters 5–6, Abstract and Resumo using real evidence | Clean thesis build; every quantitative statement traced through the claim→evidence matrix | Reproduced analysis |
| Answer each RQ explicitly | Claim→evidence matrix and conclusion text with no unresolved state for cited claims | Reproduced analysis |
| Send the complete draft to the supervisors by 18 September | Sent-message copy/date and document checksum recorded | Clean full-draft build |
| Restrict work to analysis, reproduction and writing | Commit/decision record showing no feature additions after G5 | G5 freeze |

## G7 — Release candidate (19–25 September)

**Cut rule:** require a complete thesis with no placeholders, independent
review, an inspected reproduction package and traceable accepted claims.
Record contact attempts; supervisor silence does not waive D001 or D004.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Run the final smoke and package the reproduction artefacts | Versioned archive, SHA-256, restore instructions and verified storage location | `data-v1`; stable code/document tree |
| Incorporate and record supervisor and independent-review feedback | Change list, replies and unresolved-item rationale | Review feedback |
| Perform language, references, front-matter, consistency and page-by-page visual QA | Completed editorial checklist; final PDF with correct metadata, diagrams and no TODOs/placeholders | Full draft; official template decision D004 |
| Produce and inspect the release candidate | Annotated `rc1` tag, PDF checksum and independent build/review record | All G7 acceptance evidence |

## Submission — blocking corrections only (26–29 September)

**Cut rule:** make only release-blocking corrections. Promote `dev` to `main`
through the formal gate, create the final release and submit by **29 September
at 17:00 Europe/Lisbon**.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Apply release-blocking corrections and rerun affected validation | Final validation report and linked corrections | `rc1` |
| Promote `dev` to `main` and create `v1.0.0-thesis` | Merge commit, protected final tag and clean checkout verification | Successful required checks; final gate decision |
| Create and verify an off-machine final repository bundle | Bundle verification, SHA-256 and storage location recorded | Off-machine storage |
| Submit the final PDF and archive the receipt | Portal receipt, submitted PDF checksum and submission decision linked from `PROGRESS.md` | Final release and portal access |

## Administrative reserve — 30 September

| Action | Expected evidence | Dependencies |
|---|---|---|
| Use the reserve only to recover from a failed administrative submission step; do not add scope or technical work | Corrected portal receipt or documented administrative incident | Submitted final release; institutional support if required |
