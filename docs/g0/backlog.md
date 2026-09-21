# Actionable backlog by gate (G0→G7)

**2026-09-21 addition — plan v2.1.** The seven supervisor deliverables below
extend the adopted QEMU execution path. References to the 2026-09-18 v2.0
baseline retain their historical meaning; the current plan owns the schedule.

## Supervisor deliverables added on 2026-09-21

Dates, ownership and exit criteria are in the
[plan, section 4.1.1](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).
Operational state is recorded only in PROGRESS.

| ID | Action / expected evidence | Dependency and scope control |
|---|---|---|
| SUP-01 | Review and maintain the [requirements matrix](../academic/gateway_requirements_and_platform_selection.md), linking each criterion to a component and test | Contracts and feedback; preserve D007 distinctions and keep documentary selection separate from test success |
| SUP-02 | Review the initial SoC decision and close documentary gaps needed for discussion | SUP-01 and primary sources; no procurement or native porting added |
| SUP-03 | Consolidate V1 architecture, external dependencies, provenance and consumer-control inventory | Existing diagram and C2DTA mapping; no new SSI, UI, blockchain or radio feature |
| SUP-04 | Prepare exact RQ/manuscript alignment changes for the new requirements/selection/evaluation sequence | SUP-01–SUP-03; current wording and QEMU boundary remain until an explicit aligned revision |
| SUP-05 | Assemble the bounded demonstrator packet from eligible existing evidence, with limitations and negative nominal result | G2 evidence criteria; repeat only when missing evidence or material changes require it; acceptance remains separate |
| SUP-06 | Link literature searches/readings to platform, Yocto, integration and evaluation decisions | Existing scoping-review allocation; reconcile local records with dev without calling syntax trials selection searches |
| SUP-07 | Reconcile requirements with admitted results or explicit limitations | Frozen protocol and analysis; preserve negative results and keep untested physical properties unverified |


> **Plan v2.0 adopted 2026-09-18 (QEMU-only execution amendment).** The
> student adopted [plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
> as the execution baseline on 2026-09-18. The **live actions are those of the
> QEMU execution path** in the section below. The gate sections that follow are
> the **dated August backlog, kept as history**: their windows have elapsed and
> their native prerequisites are withdrawn from mandatory scope, so they are
> not future commitments; each one carries the retargeting the adoption
> requires. Since 2026-09-19 this file also carries the confirmations the
> student reports — recorded as reported, never as documented supervisor
> decisions — and **no gate is closed and no claim is admitted** by any of them.
> **Updated 2026-09-19:** G0 was accepted on that date by the student's own
> decision, with the project manager's concurrence, for project initiation and
> baseline alignment; the G0 section below carries the reallocated residual
> obligations, and the rows on the integration battery are corrected and joined
> by four new actions from the battery and the diagnostic attempts of
> 2026-09-19. Current state remains in `PROGRESS.md`.

> **This file owns actions only**: required work, expected evidence,
> dependencies and cut rules. The versioned schedule and scope authority is
> the [integrated development plan v2.1](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).
> The current state of every deliverable and gate lives exclusively in
> [`../../PROGRESS.md`](../../PROGRESS.md); do not record completion,
> implementation status, execution results or evidence counts here.
>
> Recurring dependencies: **WSL2 ext4** means Ubuntu 24.04 on WSL2 with the
> Yocto checkout and build directory on a Linux filesystem (see
> [`../setup/wsl2_ubuntu_yocto.md`](../setup/wsl2_ubuntu_yocto.md));
> **integrated emulated guest** means the Yocto-produced ARM64 kernel and root
> filesystem booted under QEMU/TCG on the existing x86-64 workstation, hosting
> the six containers, with the simulator and harness outside it (see
> [`../setup/qemu_integrated_gateway.md`](../setup/qemu_integrated_gateway.md)).
> The published profile specifies four virtual CPUs and 8 GiB of RAM: emulator
> settings recorded per run, never a demonstrated equivalence to a four-core
> physical gateway. **ARM64 measurement VM** — a native, non-burstable ARM64
> environment — appears below only in deferred future-work rows; the rule that
> a burstable ARM64 host may never produce dissertation measurements is
> retained for any such future work.

## QEMU execution path — the live work packages (adopted plan, 2026-09-18)

Planning targets, not achieved milestones. A missed target is reported with its
cause, the remaining work and a revised forecast; it is never silently moved.

| Work package | Target / acceptance boundary |
|---|---|
| Governance publication | This documentation change, in parallel with ongoing bounded tests. It **records reported confirmations**, accepts no gate and admits no claim, and it confirms consistency only |
| Scoping-review protocol alignment | Target 2026-09-21; dated method, scope, eligibility and charting plan in `thesis/research/`, preserving the real preliminary-search history and never backdating |
| Scoping-review search and selection | Target 2026-09-26; logged searches and exports, deduplication and documented screening decisions; re-estimate the remaining workload from the real corpus at the 2026-09-21 checkpoint |
| Scoping-review charting and synthesis | Target 2026-09-30; evidence chart, selection flow, synthesis and bibliography, feeding the chapters sent on 2026-10-01 |
| Correct the review designation in the manuscript | Before 2026-10-01; Section 2.1 of the drafted manuscript still reads "a structured review with systematic elements". Edit `thesis/latex/chapters/02_background.tex` under its own change and regenerate `thesis/sections/05_background.md`; the designation becomes **scoping review**, matching Section 1 of the protocol |
| Publish the first-flow record and verify the teardown-incident correction | Incorporate the locally hash-sealed 2026-09-18 end-to-end record into the published evidence package; re-measure the Ditto memory footprint under the limits that pull request #34 merged for the `ditto-things` power-off OOM. No general or prolonged stability statement from bounded observations |
| Nine integration/recovery test families | Target 2026-09-21 to 2026-09-24; report per-test evidence, failures and residual risks. **Exercised once on 2026-09-18 and not complete**: functional results were shown for tests 2 and 8 and the tested checks of test 9, and the specific behaviours of tests 3, 4 (duplicate handling) and 7 (the MongoDB fault only); test 5 fails its deadline criterion, two sub-checks were not run — the sequence-reset sub-check of test 4 (`itest-dup-02`) and the Ditto repeat of test 7 (`itest-ditto-fault-01`) — and the timed harness parts of tests 1 and 6 are invalid. That record is a locally hash-sealed candidate archive held outside the repository, not admitted, so it admits no claim; the instrumentation defect is a separate change, and test acceptance is paused at the student's request. The follow-up actions are in the G2 section below *(corrected 2026-09-19: previously "seven families passed")* |
| Stable integrated QEMU baseline | Target 2026-09-25; no unresolved failure incompatible with the claimed stability scope |
| Bounded pilot and protocol freeze (`exp-v1`) | Target 2026-09-26 to 2026-09-29; select run identities, repeats, durations and acceptance criteria prospectively; hashed runtime lock for the controller image in place |
| Frozen emulated functional campaign | Target 2026-09-30 to 2026-10-02; only after a reviewed protocol and usable instrumentation |
| Data freeze and analysis (`data-v1`) | Target 2026-10-03 to 2026-10-05; every figure and table traceable to immutable evidence |
| Chapters 1-4 sent | Target 2026-10-01; written in parallel, not waiting for all tests |
| Full draft sent | Target 2026-10-08 |
| Feedback, corrections and QA | Target 2026-10-09 to 2026-10-18; supervisor turnaround must be requested, never assumed |
| Packaging and submission | Package 2026-10-19; submit 2026-10-20 |
| Essential contingency only | 2026-10-21 to 2026-10-31; no new features and no native porting work |

## Rules that apply to every gate

- Close a gate only through a dated decision linked from `PROGRESS.md`;
  passing checks, producing an artefact or **adopting a plan version** does not
  close a gate by itself.
- Correctness, fault handling, recovery, persistence, deployment and
  repeatability may be assessed in the integrated emulated guest against
  explicit criteria. Timing, observed throughput and resource use recorded
  there are informational and labelled emulated; they never support a
  performance or security statement, and emulated and any future native runs
  are never pooled in one aggregate.
- The measurement-host procurement rules — the 48-hour university/public-host
  rule and the AWS `c6g.xlarge` fallback — are **deferred with the native
  route** and are not obligations of any gate. The EUR 30 ceiling stands only
  as a limit on any future native work that a new budget decision (D012)
  authorises; the adopted plan requests no allocation, spending or native
  build.
- Reforecast triggers of the adopted schedule: the nine test families not
  complete by 2026-09-24, no stable baseline by 2026-09-25, no bounded pilot by
  2026-09-29, no data freeze by 2026-10-05, or the full draft not sent by
  2026-10-08. Record the cause, the remaining work and a revised forecast
  without adding scope.
- After G4, do not change metrics, thresholds, conditions or exclusion rules.
  An evidence-invalidating defect requires a new protocol/data version and
  reruns of the affected conditions under new run identities.
- After G5, permit no feature work. Record missing evidence as a limitation;
  never replace it with an inferred result.
- Supervisor silence is not approval **for the rows that stay open**: D007
  blocks `exp-v1`; the template-authenticity half of D004 blocks the final
  academic release; and the open part of D014 is only the wording of the
  native-evidence limitation and of claims about emulated timing and resource
  figures — the QEMU evaluation scope of RQ3 is reported approved (reported by
  the student, undated, not a documented supervisor decision) and is not
  re-requested, and numerical criteria belong to D007 *(corrected 2026-09-19;
  previously listed the evaluation scope and any academic use of emulated
  results (D014) as open and as a blocker of the final academic release)*. The title and RQ half of D011 and the second-operator question of
  D006 are reported settled by the student and block nothing; a reported
  confirmation is never treated as a documented decision, and none of them
  closes a gate. The student's adoption of the plan settles execution, not the
  open rows. *Reallocated by the G0 decision of 2026-09-19: D014 is no longer
  a blanket blocker — the reported approval of RQ3 evaluated with QEMU tests is
  not reopened, and any genuinely unsettled methodological or claim detail is
  tracked specifically at G4/G6; D007 still blocks `exp-v1` and the
  template-authenticity half of D004 is owed at G7.*
- Keep ACA-Py, DIDComm, Fabric, Indy, IPFS, wallets and executable
  SSI/blockchain flows outside P0 and outside any contingency window.
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
| Review differences between the imported title/RQs/integrated-Yocto wording and the governance baseline separately | Dated alignment decision; no inference of implementation or supervisor approval from a format conversion. The title and RQs the student reports approved (D011) are the reference; the approved verbatim RQ wording is in the manuscript, not here | The student's report; unchanged governance controls |
| Verify the 33 imported reference strings through the research protocol before academic release | Primary-source checks and research-register updates, distinguishing metadata verification from full-text reading | Access to the cited sources; separately authorised academic revision |

## Gate sections — dated August backlog, retargeted where the adoption requires it

> The window in each heading below is the August schedule and has elapsed; the
> live dates are the work packages above. Rows that depended on a native ARM64
> host are marked **deferred with the native route** rather than deleted, so
> the deferral stays visible.

## G0 — Authority and provenance (window of 13–15 August, elapsed; gate accepted 2026-09-19)

> **G0 accepted on 2026-09-19** — authority: the student (Rui Duarte), with the
> project manager's concurrence; scope: project initiation and baseline
> alignment ([decision record](../governance/decisions/2026-09-19-g0-closure.md)).
> This is a dated change of G0's exit scope, **not** a retroactive pass against
> the cut rule below, which is kept as written: the alignment request and the
> verified off-machine copy are **not** marked as performed. The residual
> obligations are reallocated as follows; the rows of this section stay as the
> record of the actions and are read against this table.
>
> | Residual obligation | Owner / acceptance boundary |
> |---|---|
> | Integration defects, missing sub-checks, timely delivery and admissible run evidence | Developer; G2/G3 remain pending |
> | D007 thresholds, prospective fault-window rules, loads/durations, 95-run feasibility and frozen protocol | Student/Developer and the required supervisor decision; G4, before `exp-v1` |
> | Any genuinely unsettled methodological or claim detail | Tracked specifically at G4/G6; the reported QEMU RQ3 approval is not reopened through a blanket D014 blocker |
> | Execute the scoping review and write and analyse the dissertation | Student, with technical support; Chapters 1–4 and G6, not completed by G0 |
> | Check the local template against the institution's supplied original, the final PDF's compliance, and implement the AI-use declaration | Student/Developer; G7 |
> | Maintain local source, configuration, log and data copies and complete the final evidence and reproduction package | Developer/Student; ongoing execution control and G7 |
> | Verify the off-machine copy, its hash and the restore path | Student; an active resilience action to do promptly, retained in the risk register (R25) and this backlog and required at G7 — **neither verified nor waived** by the G0 decision |

**Cut rule:** obtain the supervisor decisions that remain open without treating
silence as approval. The required result is an alignment request covering D007,
D014 and the unresolved halves of D004 and D010, plus versioned
authority/provenance records. The title, the research questions, the review
type, the schedule and the delivery obligations are reported confirmed and are
not re-requested. The university ARM64 request and the 48-hour public-host
fallback are **deferred with the native route** and are no longer conditions of
this gate.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Keep the scope document aligned with the title and RQs the student reports approved | [`scope_and_rqs.md`](scope_and_rqs.md) carrying the reported-approved title verbatim and scope summaries of the approved RQs, each marked as reported by the student and never as a documented decision. The student's adoption of plan v2.0 is not that approval either | The student's report; the approved verbatim RQ wording, held in the student manuscript |
| Send the **reduced** alignment package — D007, the open part of D014 (limitation and claim wording) and the unresolved halves of D004 and D010 — using the revised memo | Sent-message copy/date; `sent_at` and response references in the canonical decision log. *(Corrected 2026-09-19; previously also required a reply on the academic use of emulated results (D014) before the evaluation chapter is written: the QEMU evaluation scope of RQ3 is reported approved and is not re-requested.)* *Since the G0 decision of 2026-09-19 this is no longer a G0 condition and is not marked as sent: the D007 request belongs to G4 before `exp-v1`, the template authenticity inside D004 to G7, and D014's genuinely unsettled detail is tracked at G4/G6 rather than as a blanket precondition of the evaluation chapter* | Student action; the [revised memo draft](../governance/proposals/supervisor_alignment_memo_v2.0_proposal.md) |
| Hold a short alignment meeting when written decisions remain unresolved | Minutes recording each decision, owner and follow-up date | Supervisors' availability |
| Maintain an Ubuntu 24.04 WSL2 ext4 Yocto environment | `wsl -l -v`, filesystem proof for the build directory and environment capture | Student machine; WSL2 ext4 guide |
| ~~Request a university ARM64 measurement host and apply the 48-hour fallback rule~~ — **deferred with the native route on 2026-09-18** | None. It is not an obligation of the adopted plan and closes no gate. If native work is ever authorised, the original evidence list applies unchanged: request/reply record, price quotation before provisioning, and provider, region, CPU, tenancy/shared-vCPU, kernel, OS and clock provenance after provisioning | A new budget decision (D012); the EUR 30 ceiling; [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md) as a generic checklist only |
| Maintain the claim→evidence matrix | [`../claim_evidence_matrix.csv`](../claim_evidence_matrix.csv) with every public claim mapped to admissible evidence or an explicit limitation | Scientific framing and evidence policy |
| Maintain this action backlog and the risk register | Reviewed backlog plus [`risks.md`](risks.md), with operational state recorded only in `PROGRESS.md` | Gate reviews |
| Exclude unsupported results from the active dissertation | Chapters 5–6 contain no number or conclusion without admitted evidence; exclusion rationale recorded | Claim→evidence review |
| Preserve governance and repository provenance | Protected evidence tag, verified bundle/checksum inventory, source register and rewrite-equivalence record | Git/GitHub access; off-machine storage for the final bundle |

## G1 — Yocto/QEMU functional platform (window of 13–18 August, elapsed; gate accepted 2026-08-14)

**Cut rule:** require a clean identified build and five strict unattended
boots. Each accepted boot must report exactly `systemd=running`, zero failed
units, the required network/runtime assertions and a clean shutdown. Reduce
the image to a minimal runtime platform if the build or boot path cannot meet
the gate; QEMU evidence never supports performance claims.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Freeze the **integrated emulated environment** specification | Environment manifest covering the QEMU version, TCG mode and options, machine and CPU model, virtual CPUs, memory, guest image and kernel identities, container identities, workload and the actual host/WSL configuration. Guest and container readings are recorded separately from host QEMU-process readings and are never converted between each other by an assumed emulation slowdown factor; the achieved load and the contention of sharing the workstation with the generator are recorded too | Integrated emulated guest |
| Maintain the Scarthgap 5.0.19 `qemuarm64` kas manifest with exact layer tags/commits | `kas dump` and source revisions reproducible from a clean checkout | WSL2 ext4 |
| Produce a clean, identified `egw-image` build | Build record, package manifest, commit identity and verified checksums | WSL2 ext4; sufficient Linux-filesystem storage |
| Run the five-boot strict G1 acceptance campaign | Five distinct console/result pairs, strict assertion summaries, clean-shutdown evidence and verified `SHA256SUMS` | Identified build; strict unattended boot driver |
| Preserve preliminary bring-up evidence separately from the acceptance campaign | Immutable evidence inventory and provenance note that prevents preliminary artefacts from being substituted for the strict campaign | Evidence-integrity tooling |
| Verify `linux/arm64` support for every deployment image by pinned digest | Archived `docker manifest inspect` output per image | Network access; image lock; ARM64 deployment review |
| Update stale build-input comments **at the next Yocto functional rebuild — never as a standalone edit** (changing a recipe changes its checksum and forces a rebuild), and no later than the release candidate (G7). The affected inputs are `egw-image.bb` (its DESCRIPTION still says "two QEMU boots") and, since 2026-09-18, `egw-gateway-image.bb`, `egw-gateway-config.bb` and `kas/egw-qemuarm64-integrated.yml`, whose comments still describe plan v2.0 as an unpublished working revision although it was adopted and published on 2026-09-18 | Corrected comments in the rebuild's recipes and manifest; a note that the existing G1 and integrated-profile evidence remains pinned to the original inputs and is not invalidated | Next functional Yocto rebuild |
| Regenerate the PlantUML sources and their SVGs together — `diagrams/two_layer_experimental_deployment.puml`, `diagrams/c2dta_five_layer_reference.puml` and both `.svg` files — **never as a standalone edit of one of the pair**, applying the corrections recorded in [`../../diagrams/README.md`](../../diagrams/README.md), and no later than the release candidate (G7) | Regenerated `.puml` sources and matching SVGs carrying the corrected wording; a note that no earlier rendering is invalidated | A machine with a PlantUML installation |
| Complete institutional searches and full-text verification for claims used in Chapters 1–2 | Search exports, selection decisions and audited bibliography in `thesis/research/` | Institutional IEEE/ACM/Scopus or Web of Science access |

## G2 — Live vertical slice (window of 15–23 August, elapsed)

**Cut rule:** require the six containers deployed **inside the integrated
emulated guest** with TLS and an inspectable, identity-reconciled
wearable→MQTT→controller→Ditto→API trace, sealed and labelled emulated. If the
slice cannot be obtained, cut auxiliary APIs rather than expand scope; apply
the reforecast triggers of the adopted schedule.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Deploy the minimal ARM64 compose stack inside the guest: Mosquitto TLS, Ditto, MongoDB and controller | Clean `docker compose up`; health/readiness output; pinned image digests; runtime lock and `pip check` record | Integrated emulated guest; operational certificates and secrets |
| Incorporate the locally hash-sealed first-flow record of 2026-09-18 into the published evidence package | Sealed capsule with manifest and verified checksums, labelled emulated, naming the run identities and the maximum latency as an informational emulated observation; sealing is not acceptance | The candidate record held outside the repository |
| Resolve the `ditto-things` power-off OOM and the container memory sizing — *done through pull request #34; the follow-up is to re-measure the Ditto footprint after the remaining tests* | A separate change with its own evidence: a graceful stop before power-off and container memory limits sized against the observed usage; no general or prolonged stability statement from the bounded observations that followed | Integrated emulated guest |
| Complete the nine integration/recovery test families of the runbook | Per-test evidence, retained failures and a residual-risk list. The families were exercised once on 2026-09-18 — functional results shown for tests 2 and 8 and the tested checks of test 9, and the specific behaviours of tests 3, 4 (duplicate handling) and 7 (the MongoDB fault only); test 5 fails its deadline criterion, two sub-checks were not run — the sequence-reset sub-check of test 4 (`itest-dup-02`) and the Ditto repeat of test 7 (`itest-ditto-fault-01`) — and the timed harness parts of tests 1 and 6 are invalid — and that record is a locally hash-sealed candidate archive held outside the repository, not admitted, so the battery is **not complete** and admits no claim *(corrected 2026-09-19: previously "seven passed")*. After resumption, follow the proposed [acceptance sequence](../governance/proposals/acceptance_protocol_update_2026-09-19.md) (proposed, not adopted): one fresh bounded acceptance pair first, then only the affected or missing checks | Stable deployment in the guest; the instrumentation fix for the resource sampler; test acceptance resumed by the student |
| Run the two missing sub-checks: the sequence-reset sub-check of test 4 and the Ditto repeat of test 7 *(added 2026-09-19)* | Test 4: `run_test itest-dup-02 42 --scenario smoke --duration 60` giving `lost = 0` and every `delta` line `OK`, as the runbook requires, under its own run identity — or an equivalent existing record mapped to it; none was found in the 2026-09-18 archive. Test 7: the fault repeated once for Ditto (`R=itest-ditto-fault-01; SVC=ditto-things`, then the runbook's fault line and evaluation line again), accepted only when the interruption and the recovery are both shown; until then test 7 has demonstrated the MongoDB fault only. Neither was run on 2026-09-18: both steps are prose in the runbook and the extraction used for the battery took only fenced code blocks; extract both next time | Test acceptance resumed by the student; stable deployment in the guest |
| Retain and follow up the test 5 deadline failure *(added 2026-09-19)* | Test 5 of 2026-09-18 fails its stated criterion — 326 of 2,016 valid events were confirmed after the controller-clock deadline, against `lost = 0` and `late_confirmations = 0` — and that valid negative result is retained and analysed, never repeated until a pass and discarded. Any new attempt uses a new run identity and unchanged deadline semantics, and reconciles the two validation paths that disagreed on the simulator manifest | The delivery-backlog diagnosis below; test acceptance resumed by the student |
| Diagnose the delivery backlog under QEMU/TCG *(added 2026-09-19)* | A diagnosis, under unchanged deadline semantics, of why the controller — a single consumer processing messages sequentially against Ditto — sustained about 3-8 acknowledgements per second against 11.2 msg/s published in the invalid attempts of 2026-09-19, with its queue growing by 4.7-10.6 per second; read the guest-side event logs, which were not read for the diagnostic counts. A lower future workload comes only through an explicit prospective QEMU protocol decision; a deadline is never moved after lateness is observed | Guest-side logs after resumption; D007 and the protocol at G4 |
| Confirm the controller-restart queue finding and take the design decision *(added 2026-09-19)* | Confirmation from the guest-side event and container logs of whether the about 2,136 messages of `controller_restart-r02` that the backlog does not explain — 1,765 published before the restart and about 371 during the outage — were lost with the controller's in-memory queue (acknowledged on enqueue, clean session, fixed client id); then a separate, recorded design decision on that data path before any C12 evidence is collected. Missing fetched records are not proof of permanent loss | Guest-side logs after resumption; a separate design decision; claim C12 and RQ2 |
| Exercise the MQTT→Ditto controller against real services | TLS broker connection, accepted/rejected event records and a real Ditto twin update | Live compose stack |
| Execute the wearable→MQTT→controller→Ditto vertical slice | `sent_events.jsonl`, `events.jsonl` and `GET /twins/{device_id}` showing the expected materialised state | Controller, broker, Ditto and simulator |
| Run the simulator `smoke` scenario against the real broker | Simulator manifest and write-once raw output for a live run | Live compose stack |
| Add and run live integration tests | Persisted Linux test report containing at least one real MQTT/Ditto integration path; fakes remain unit evidence only | Integrated emulated guest |
| Advance Chapters 1–3 and the integrated emulated deployment diagram of [`../../diagrams/architecture.md`](../../diagrams/architecture.md), which is the design of record since 2026-09-18 (the two-layer deployment diagram is historical and is not reused as the architecture of record) | Compiling thesis sources and editable diagrams with no unsupported result claims. Diagram labels follow the authorised wearable-data wording of [`../governance/language-policy.md`](../governance/language-policy.md), keeping the literal `/telemetry` topic | The title and RQs reported approved; the open rows D007, D014 and the template half of D004 |

## G3 — P0 feature freeze (window of 24–30 August, elapsed; live target: the nine test families, 2026-09-21 to 2026-09-24)

**Cut rule:** freeze P0 at the local digital-twin core. Require three wearable
types and the mandatory nominal, invalid, reconnect, restart and failure
behaviours to run live with frozen CONTRACTS v1.1 and no open P0 defect.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Run three concurrent synthetic wearable types | Live run manifest, events and three queryable twin states | G2 vertical slice |
| Execute every mandatory scenario, including nominal, load, invalid payload, dropout/reconnect, restart and the stability run | One write-once manifest/evidence set per scenario and a demonstrated real disconnection/recovery path. The **24-hour soak is attempted** in the emulated environment, subject to the pilot's feasibility finding — superseding the earlier statement that it was not transferred; if the pilot finds it infeasible, a shorter bounded run replaces it and the absence of a 24-hour soak becomes an explicit limitation | Integrated emulated guest; pilot feasibility finding |
| Validate reconnect, retry and backpressure behaviour | Live integration records, consistent counters and documented recovery outcome | Controller and broker |
| Exercise the corrected metrics and experimental harness end to end | SUT-side resources, controller metrics, automatically collected events, valid measured windows and CLI-driven analysis | Live stack; corrected harness |
| Run the complete unit, integration and E2E test suite | Persisted Linux report with unit and live `integration` results separated | Integrated emulated guest |
| Execute a pilot soak | Pilot-only logs, resources and integrity report; no pilot number cited in the dissertation | Stable live stack |
| Complete Chapter 3 and advance Chapter 4; synchronise ADRs and diagrams with CONTRACTS v1.1 | Compiling thesis, editable diagrams and ADR index with consistent scope/interfaces | Feature-frozen P0 |

## G4 — Experimental freeze, tag `exp-v1` (window of 31 August–6 September, elapsed; live target 2026-09-26 to 2026-09-29)

**Cut rule:** require a complete non-citable micro-pilot and seal environment,
protocol, predefined run identities, thresholds, exclusion rules and analysis.
D007 must be decided before `exp-v1`. After the tag, apply the protocol-change
rule above.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Reproduce build and live smoke from a clean checkout | Clean-clone record covering dependency installation, build and E2E smoke | WSL2 ext4; integrated emulated guest |
| Generate and enforce the hashed Python runtime lock for the controller image deployed in the guest, **before the protocol freeze** | Committed hash lock including build dependencies; Docker install with `--require-hashes`, `--no-build-isolation` and `--no-deps`; image digest, guest manifest and archived `pip check` output. The image currently installs with `pip install .`, unlocked, and such an image is not admissible for thesis measurements | Build/provisioning host for the guest image; pinned base image |
| Apply correction-only changes after feature freeze | Identified commits linked to defects; no new feature scope | Frozen P0 |
| Execute the bounded pilot, including the **feasibility check of the 95-run attempt target**: achievable against requested publishing rate, clock boundaries, instrumentation, storage, recovery and host/guest contention | Pilot raw data, manifests, environment records and checksums for every condition; pilot data marked non-citable; a recorded feasibility finding with a fresh QEMU duration forecast. Select the emulated functional campaign here: run identities, repeats, durations, load levels and acceptance criteria are chosen prospectively, taking the historical composition as a target to attempt and never inheriting its thresholds | Integrated emulated guest; corrected harness |
| Regenerate analysis from pilot raw data through the delivered CLI | `processed/` and `figures/` produced by one documented command, including external runs or a documented exclusion | Complete micro-pilot |
| Complete Chapters 1–4 and the evaluation skeleton | Clean thesis build with methods, protocol and limitations but no invented results. Chapter 3's method label is **scoping review**, as reported settled under D003, and is never described as a systematic literature review | D007, D014 and the open half of D004; the scoping-review package above |
| Freeze protocol and predefined run identities as `exp-v1` | Annotated tag and checksumed protocol/run-plan package | All G4 acceptance evidence |

## G5 — Data freeze, tag `data-v1` (window of 7–13 September, elapsed; live targets: campaign 2026-09-30 to 2026-10-02, freeze 2026-10-03 to 2026-10-05)

**Cut rule:** require the complete predefined **emulated functional campaign**
frozen at the pilot, with write-once raw data, environment manifests and
verified checksums. The 95-run composition, the 24-hour soak included, is the
quantity that campaign **attempts to reach** under emulation, subject to the
pilot's feasibility finding. *(Superseded wording of 2026-09-18: "Never the 95
runs and never the 24-hour soak under emulation: those become documented
limitations.")* Whatever the attempt does not reach becomes a documented
limitation. An optional condition may be cut only as a documented limitation;
never fill an evidence gap with an unsupported conclusion.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Execute the frozen **emulated functional campaign** selected at the pilot. *(Superseded wording of 2026-09-18, kept for the record: "The 95-run campaign and the 24-hour soak are not carried over to the emulated environment.")* Its target composition is the historical 95 runs — 5 QEMU boots, 10 stack cold starts, 10 twin creations, 10 smoke sequences, 10 nominal, a 40-run load sweep at 10, 50, 100 and 250 messages/s, 3 invalid payload, 3 dropout/reconnect, 3 controller restart and 1 soak of 24 actual elapsed hours — attempted under emulation and subject to the pilot's feasibility finding | `experiments/results/raw/<run_id>/` for every predefined identity, each with manifest, environment, valid measurement window and verified `SHA256SUMS`, grouped by execution mode and never pooled across modes. The attempt target is **not** the frozen set and promises no valid run count; the frozen identities are still chosen prospectively at `exp-v1` | Integrated emulated guest; `exp-v1`; pilot feasibility finding |
| Preserve failures and rerun only evidence-invalidated conditions under new identities | Failure artefacts retained; dated deviation/exclusion record; replacement identity linked to the original attempt | Frozen protocol-change rule |
| Validate all raw data and regenerate analysis outputs | Admission report plus regenerated `processed/` and `figures/`, with provenance and checksum validation | Complete campaign |
| Write the experimental setup and limitations | Thesis text tracing environment, protocol deviations and limitations to evidence | Admitted campaign evidence |
| Freeze admitted data as `data-v1` and keep `raw/` immutable | Annotated tag, verified checksums and data-freeze decision linked from `PROGRESS.md` | Complete validation |

## G6 — Analysis and full draft (window of 14–18 September, elapsed; live targets: Chapters 1-4 by 2026-10-01, full draft by 2026-10-08)

**Cut rule:** require every chapter, figure and RQ answer to exist and derive
only from admitted `data-v1` raw evidence. Permit analysis and writing work,
not features.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Reproduce analysis solely from admitted sealed raw data | Documented command, admission log, tables, figures and confidence intervals regenerated from `data-v1` | `data-v1` |
| Complete Chapters 5–6, Abstract and Resumo using real evidence | Clean thesis build; every quantitative statement traced through the claim→evidence matrix | Reproduced analysis |
| Answer each RQ explicitly | Claim→evidence matrix and conclusion text with no unresolved state for cited claims | Reproduced analysis |
| Send Chapters 1-4 by 2026-10-01 and the complete draft by 2026-10-08 | Sent-message copy/date and document checksum recorded; supervisor turnaround must be requested, not assumed | Clean full-draft build |
| Restrict work to analysis, reproduction and writing | Commit/decision record showing no feature additions after G5 | G5 freeze |

## G7 — Release candidate (window of 19–25 September, elapsed; live target 2026-10-15 to 2026-10-18)

**Cut rule:** require a complete thesis with no placeholders, independent
review, an inspected reproduction package and traceable accepted claims.
Record contact attempts; supervisor silence does not waive D007 or the
template-authenticity half of D004. An **independent second-operator
reconstruction is not required** — the student reports it waived — and a
**scientific article is not required for delivery**; the article is deferred,
not deleted.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Typeset the dissertation in the institution-supplied `Template_LaTeX` source | Final document built from that template. Its use is reported mandatory; that is reported by the student and is not a documented supervisor decision | `Template_LaTeX` |
| Authenticate the local template copy against the current official 2026 source and settle the cover and author/supervisor/co-supervisor metadata | Record of the comparison and its outcome, and the settled metadata. **Still open** — the reported confirmation covers the requirement, not the authenticity of the local copy | Supervisors or the institution (the open half of D004) |
| Prepare the AI-use declaration during drafting and verify it here | Truthful declaration in the applicable institutional format, identifying the actual assistance received and the author's responsibility. Reported mandatory by final submission; Git and pull-request authorship conventions never excuse omitting it | Drafting; the applicable institutional format |
| Retain the local evidence archive | Source snapshots, configurations with secrets removed, raw results, logs, manifests and checksums, retained locally. A local copy is reported expected as evidence | Sealed evidence and run records |
| Run the final smoke and package the reproduction artefacts, including the **verified off-machine copy** | Versioned archive, SHA-256, restore instructions and a verified off-machine storage location with the restore check actually performed. This is a separate resilience control from the local archive above and is **still outstanding**. *Since the G0 decision of 2026-09-19, verifying the off-machine copy, its hash and the restore path is an active resilience action owned by the student, to be done promptly rather than left to this gate, and required here — neither verified nor waived* | `data-v1`; stable code/document tree; off-machine storage |
| Incorporate and record supervisor and independent-review feedback | Change list, replies and unresolved-item rationale | Review feedback |
| Perform language, references, front-matter, consistency and page-by-page visual QA | Completed editorial checklist; final PDF with correct metadata, diagrams and no TODOs/placeholders | Full draft; the open half of D004 |
| Produce and inspect the release candidate | Annotated `rc1` tag, PDF checksum and independent build/review record | All G7 acceptance evidence |

## Submission — blocking corrections only (packaging 2026-10-19, submission 2026-10-20)

**Cut rule:** make only release-blocking corrections. Promote `dev` to `main`
through the formal gate, create the final release and submit by **2026-10-20**.
The final delivery deadline is 2026-10-31; both dates are planning targets.

| Action | Expected evidence | Dependencies |
|---|---|---|
| Apply release-blocking corrections and rerun affected validation | Final validation report and linked corrections | `rc1` |
| Promote `dev` to `main` and create `v1.0.0-thesis` | Merge commit, protected final tag and clean checkout verification | Successful required checks; final gate decision |
| Create and verify an off-machine final repository bundle | Bundle verification, SHA-256 and storage location recorded | Off-machine storage |
| Submit the final PDF and archive the receipt | Portal receipt, submitted PDF checksum and submission decision linked from `PROGRESS.md` | Final release and portal access |

## Essential contingency window — 2026-10-21 to 2026-10-31

| Action | Expected evidence | Dependencies |
|---|---|---|
| Use the window only for essential corrections and to recover from a failed administrative submission step; add no scope, no new features and no native porting work | Corrected portal receipt or documented administrative incident | Submitted final release; institutional support if required |
