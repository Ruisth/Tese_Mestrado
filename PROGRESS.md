# PROGRESS — single source of state per deliverable

> **This file is the single source of state for the project.** The backlog
> ([`docs/g0/backlog.md`](docs/g0/backlog.md)) holds only actions, expected
> evidence, dependencies and cut rules — it holds no state. The formal record of
> gate outcomes is [`docs/governance/gate_decision_log.md`](docs/governance/gate_decision_log.md);
> the "Accepted at gate" column below mirrors it. Structure as per the external audit of 2026-08-08
> (§5.1, §5.2, §14).

Updated: 2026-09-17 for the dissertation source import only. The supplied
Word manuscript is now the source of the canonical LaTeX draft: Chapters 1–2,
three tables, one research-process figure and 33 preserved reference strings.
Chapters 3–6 and unprovided front matter contain empty structure only. This
snapshot supersedes the older draft's page/word counts and completeness
statements; it does not change the governance plan, record supervisor
approval or accept a gate or claim. Integrated-Yocto wording is imported
source content, not evidence that a plan amendment has been adopted. See
[the import record](thesis/latex/WORD_IMPORT.md) and
[source inventory](thesis/latex/word-import-manifest.json) for the source
identity and current verification evidence.

Updated: 2026-09-18 for the plan v2.0 proposal section and two
governance rows only (that section is now the adopted-scope section below); no state field, gate, claim or supervisor decision
changes. Updated again the same day: the proposal texts moved under
`docs/governance/proposals/`, plan v1.2 was returned, unmodified, to its
canonical path, and the proposal section took the dates confirmed by the
student. That move was described in LOG entry `#C031`, which was written on a
feature branch and lost in a later merge. **This note corrected on 2026-09-19:**
`#C031` was restored to `LOG.md` on 2026-09-18, verbatim and in identifier
order, on the branch that publishes this change, so the citation is no longer
dangling; the identifier is not reused, and [LOG `#C032`](LOG.md) continues to
carry the same record.

Updated: 2026-09-18 for the **adoption of plan v2.0 with the QEMU-only
execution amendment**. The student adopted it for project execution on that
date and instructed its publication at the canonical path; see
[the adopted plan](docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md),
[ADR 0008](docs/adr/0008-integrated-yocto-arm64-evaluation.md) — *Accepted by
the student for project execution; academic framing reported approved by the
student, academic use of emulated results not agreed* — and
[LOG `#C032`](LOG.md). The same update records the first end-to-end flow of
2026-09-18 inside the emulated Yocto guest. **The adoption closes no gate and
admits no claim**, and no emulated result becomes native ARM64 evidence. Every
date after 2026-09-18 in this file is a planning target.

Updated: 2026-09-19 to record the **supervisor confirmations reported by the
student** ([LOG `#C033`](LOG.md)). The blanket statement that nothing had been
sent and nothing approved is withdrawn: the state-of-the-art material is
reported sent, a supervisor is reported to have approved proceeding with the
QEMU tests, and twelve further items are reported confirmed — the title, the
research questions with RQ3 in QEMU, the local-core scope, a scoping review as
the review method, an attempt at the historical 95-run quantity, no second
operator, the review schedule, the mandatory institutional template, a mandatory
AI-use declaration, an optional article, the authorised wearable-data
terminology and a local evidence copy. **All of that is reported by the
student**: none of it is a documented supervisor decision, no date, message or
supervisor name was reported for any of it, and none of it closes a gate or
admits a claim. What stays unsent is the reduced alignment package covering
D007, D014 and the unresolved halves of D004 and D010. The `status` column of
the decision log now carries three values — `proposed_not_sent`,
`confirmed_reported_by_student` and `partly_confirmed_reported_by_student` —
with `sent_at` and `response_at` empty in every row.

Addendum 2026-09-18, controller observability only: `GET /metrics` gains the
additive progress counters `received`, `in_progress` and `processing_errors`
([ADR 0010](docs/adr/0010-controller-progress-counters.md), status Proposed;
`src/CONTRACTS.md` section 5). They are verified by unit tests with fakes
only and have not been run on a gateway, against a live broker or Ditto, or
on ARM64. The addendum changes no gate, claim, maturity level or sealed test
figure, and the contract title stays v1.1.

Previous governance and technical baseline: 2026-08-14 (**PRs #12–#25 are all merged**, #15
included: the two-layer proposal package publishes as PROPOSED documents with
no normative effect and academic alignment remains subject to D001; a
clean-checkout image build plus five strict QEMU boots is sealed under
`docs/evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/`; **gate G1 was
formally accepted on 2026-08-14** in
[`docs/governance/gate_decision_log.md`](docs/governance/gate_decision_log.md),
scope: functional platform layer only, D006 unaffected; the plan was bumped to
v1.2 to regularise the in-place amendment of v1.1; the current sealed unit
figure remains 701 tests).

**Claim status: 0 of 15 accepted.** C01 has partial evidence: the identified
same-operator clean-checkout build is now produced and sealed, and its **formal
admission is the single step still outstanding** — the second-operator
requirement of D006 is reported waived, recorded on 2026-09-18 (the date of the record, never of the waiver, for which none was reported), as reported by the
student and not as a documented supervisor decision, so it is no longer a
dependency of the claim, while the wording stays *versioned* and
*repeatable build by the author* precisely because no independent reconstruction
exists. C02 has the preliminary two-boot seal and the new strict
five-boot G1 set; the predefined later `data-v1` identities and the formal
claim admission remain separate — the gate decision admitted no claim. The remaining **13 still have no admissible experimental
evidence**. **Gate G1 is the only accepted gate** (2026-08-14, functional
platform layer only — accepting the gate validated no claim); G0 and G2–G7
remain undecided.

## Adopted scope and forecast — plan v2.0, adopted 2026-09-18 (QEMU-only execution amendment)

The student instructed that the evaluated system must boot the Yocto-built
Linux image and run the gateway services inside it, and — because no native
ARM64 host could be obtained — that it be evaluated under QEMU/TCG on the
existing x86-64 workstation. On 2026-09-18 the student adopted
[plan v2.0 with the QEMU-only execution amendment](docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
as the execution baseline;
[ADR 0008](docs/adr/0008-integrated-yocto-arm64-evaluation.md) is *Accepted by
the student for project execution (2026-09-18)*. The proposal texts stay under
[`docs/governance/proposals/`](docs/governance/proposals/README.md) as the
record of what was proposed; the canonical text governs where the two differ.

The adoption settles **execution only**. The title, the research questions with
RQ3 in QEMU, the local-core scope, the review type, the review schedule, the
template obligation, the second-operator waiver, the optional article, the
terminology policy and the local evidence copy are **reported confirmed by the
student** — reported, and nowhere recorded as documented supervisor decisions.
What remains open is the experimental thresholds (D007), the academic use of
emulated results (D014), the authenticity of the local template copy inside
D004 and the storage semantics inside D010; their package is unsent, and D001,
D007, D008 and D012 stay `proposed_not_sent`. Native ARM64 deployment and native performance
measurement are documented, unverified future work and are not required to
complete this dissertation; their absence is an explicit limitation, not a
blocker. **Adoption closes no gate and admits no claim**, and no emulated
result becomes native ARM64 evidence. The sections below retain their dates,
scope and evidence.

| Item under the adopted plan | Implemented / verified state | Next evidence required |
|---|---|---|
| Original G1 Yocto/QEMU platform | Existing build and five strict boots; original G1 acceptance preserved | No relabelling as a native integrated gateway |
| Integrated QEMU/TCG profile (ARM64 emulated on the x86-64 WSL2 workstation) | Ordered first by the project review once no native ARM64 virtual machine could be obtained on 2026-09-17. In pull request #28 (merged into `dev` on 2026-09-18) the integrated image was built (commit `03e333e`) and booted twice under QEMU/TCG (commit `3209b17`) on 2026-09-18 with every build and boot acceptance check passing. The same day an isolated MongoDB 7.0.39 test passed on that guest (start, write/read, restart, persistence across a guest power cycle); the build, boot and MongoDB records were sealed as technical evidence in `docs/evidence/integrated-qemu/` (pull request #29, merged into `dev` on 2026-09-18). Pull requests #32 (broker secret hand-over and ACL probe) and #31 (controller progress counters) were merged into `dev` the same day; merging validates no stack and accepts no gate. Later the same day the six-container stack was **deployed inside the guest** and the first bounded end-to-end functional test (one smartwatch, 1 Hz, 60 s) **ran**: 60 sent, 60 delivered unique, 0 lost, 0 late, 0 duplicate, 0 failed, 0 rejected; twin `org.c2dta:5689c879-…` with `last_seq` 59; reconciliation by identity exited 0. Maximum latency 12,286 ms — **emulated, informational, never a performance result**. The record of that run is **candidate evidence held outside the repository and unsealed**, so it supports no claim. Two defects it exposed were fixed on `dev`: the controller was attached to the wrong Compose network (`9ffd365`) and the host shell inherited a relative schema directory (`dc6d8bb`, `22fb0a9`). A memory-cgroup OOM killed the `ditto-things` JVM **during the power-off** of that session (512 MiB container limit); the corrective work is a separate change and is open (see the Ditto-resources risk in [`docs/g0/risks.md`](docs/g0/risks.md)). No stability is claimed, nothing has been measured, and sealing is not acceptance | Seal the first-flow record inside the repository; resolve the teardown OOM and container memory sizing; complete the nine integration/recovery test families of the runbook (**exercised once on 2026-09-18**: seven passed; tests 1 and 6 carry a failing harness part from the resource sampler under emulation; that record is held outside the repository and unsealed, so the battery is not complete). Functional and integration evidence only, never native ARM64 performance evidence (adopted plan, evidence classes) |
| Native Yocto VM target — **future work under the adopted plan** | Not implemented or boot-verified; AWS custom AMI route documented as a candidate. The student confirmed on 2026-09-16 that no ARM64 VM and no benchmarks existed; no provider allocation is assumed. On 2026-09-17 no native ARM64 virtual machine could be obtained (cloud attempts failed). The QEMU-only amendment of 2026-09-18 removes the native target from mandatory scope: it is **documented, unverified future work**, it blocks no gate of the adopted plan, and no allocation, spending or native build is requested | Nothing is required of it for this dissertation. If native work is ever authorised: platform-specific image, native boot, image identity, network/storage/reboot, each with its own protocol and data. Latency, throughput, saturation and resource-capacity results stay outside the adopted scope and are recorded as an explicit limitation |
| Services on Yocto (G2) | Controller/simulator/Compose code exists; a bounded integrated trace was produced inside the emulated guest on 2026-09-18 (row above) — **emulated, unsealed, candidate evidence outside the repository**, so no acceptance evidence exists and G2 stays Not decided | Sealed, identity-reconciled MQTT/TLS → controller → Ditto → API evidence from the guest, labelled emulated; the nine integration/recovery families |
| Experimental pipeline | Tools and historical unit checks exist; no valid integrated pilot or campaign | Guest-bound provenance, runtime verification, pilot and frozen protocol |
| Dissertation | Chapters 1–2 imported from the supplied Word manuscript on 2026-09-17; Chapters 3–6 are empty structure (see the update note above) | Architecture and RQ sections revised to the adopted integrated, emulation-bounded scope; evidence-based results; full review and final format. The title and the RQs are **reported approved by the student** under D011 — reported, not documented — with the approved verbatim RQ wording held in the student manuscript, so the repository publishes scope summaries. D001's two-layer wording was never sent and is superseded as a live request |
| Supervisor agreement | **Reported confirmed by the student** (2026-09-19, LOG #C033), and recorded as reported rather than as documented decisions: the state-of-the-art material sent; approval to proceed with the QEMU tests; the title, verbatim *Blockchain-powered Personal AI – Digital Twin Edge Gateway*; the research questions with RQ3 evaluated in QEMU; the local-core scope; a scoping review as the review method; an attempt at the historical 95-run quantity under QEMU; no second operator; the review schedule of Chapters 1–4 on 2026-10-01, full draft on 2026-10-08 and feedback 2026-10-09 to 2026-10-14; the mandatory institutional template; a mandatory AI-use declaration; an optional article; the authorised wearable-data terminology; and a local evidence copy. No date, message or supervisor name was reported for any of them. **Still outstanding:** the reduced alignment package. The student's adoption of the plan is **not** a supervisor decision and is not recorded as one | Replies recorded in the decision log for the rows that stay open: D007 (thresholds), D014 (the academic use of emulated results and the wording of the limitation that records the absence of native evidence), the authenticity of the local template copy with the cover and metadata (inside D004), and the operational storage semantics (inside D010). D012 stays deferred with the native route; no allocation or spending is requested. The unresolved parts of D011 and D013 — the approved verbatim RQ wording, which lives in the student manuscript, and the dates after the feedback window — are tracked in their rows, not re-requested |
| Effort and dates (adopted plan) | The estimate of 225-345 active hours (2026-09-16) is **superseded pending re-estimation** after the current integration battery; it was never a fresh measurement and agent execution time is not the student's writing capacity. 8 h/day reported. Planned submission 2026-10-20 and final delivery deadline 2026-10-31, confirmed by the student on 2026-09-18 after discussing the dates with the supervisors (a first-party statement; no administrative document checked); 2026-10-21 to 2026-10-31 is a contingency window for essential corrections only | A re-estimate by the student, split between the work before and after the full draft, and logged hours. The work-package dates of the adopted plan are planning targets, none of them completed; a missed target is reported with its cause, the remaining work and a revised forecast, never silently moved |

Read-only inspection of the existing WSL build on 2026-09-16 found kernel 6.6.142
with EFI, cgroups/overlayfs/virtio support, but ACPI, NVMe and ENA disabled; the
installed manifest lacks Compose, while a Compose V2 recipe is available. These
checks identify adaptation work, not a new runtime success. No gate or claim is
accepted by the adopted plan or by the emulated results. The work packages and
reforecast triggers are in the adopted plan; they were reforecast on 2026-09-18
backwards from the planned submission of 2026-10-20 and are planning targets,
not completed milestones.

## State model — three independent fields (audit §5.1)

Each deliverable has a single row with three independent fields:

| Field | Values |
|---|---|
| **Implemented** | `yes` / `no` — the artefact exists in the repository |
| **Verified** | level + evidence: `unit — …`, `static — …`, `integration — …`, `no` |
| **Accepted at gate** | gate + state from the taxonomy of plan §1 (`Pending`, `In progress`, `Blocked`, `Complete`, `Cut`) + date/decision once it occurs |

Rules: no "Complete" without archived evidence. "Implemented" and "unit
verified" never imply acceptance at a gate. Definition of Done per deliverable
(audit §14.1): the artefact exists + reviewed + executed in the applicable
environment + evidence archived + claim→evidence matrix updated + gate decision
recorded. As at 2026-08-14 exactly one gate is closed: G1 is `Complete`
(accepted 2026-08-14, decision in the gate log); every other "Accepted at
gate" field is `Pending`, `In progress` or `Blocked`.

## Maturity scale M0–M5 (audit §2.3)

| Level | Meaning |
|---|---|
| M0 | Absent — no artefact and no evidence |
| M1 | Prepared — documentation/configuration/code exist |
| M2 | Verified locally — syntactic or unit validation persisted |
| M3 | Integrated — works with real dependencies in the target environment |
| M4 | Evaluated — reproducible experimental evidence |
| M5 | Accepted — gate closed and decision recorded |

The repository sits globally between M1 and M2. The Yocto/QEMU platform
deliverable is the single exception: with gate G1 accepted on 2026-08-14 it
reaches M5 for its functional scope (M4 does not apply — the gate is
functional and involves no experimental evaluation). The plan requires M3–M5
for most claims and gates.

## State per deliverable

### Block 2026-08-07 to 2026-08-09 (G0 — decision date 2026-08-10)

| Deliverable | Implemented | Verified | Accepted at gate | M |
|---|---|---|---|---|
| Git repository initialised and published | yes | static — private remote active since 2026-08-11 (`Ruisth/Tese_Mestrado`); on 2026-08-13 the ruleset was aligned with the written policy: pull requests and merge commits only on `main`/`dev`, force-push/deletion forbidden, review-thread resolution required and six technical/metadata checks mandatory in strict mode. PRs #12–#25 passed all required checks and were merged; all known review threads are resolved with factual replies. The preliminary G1 build is reachable through protected tag `evidence/g1-yocto-build-5770c0a`, and a second protected tag `evidence/g1-bringup-driver-367c929` preserves the bring-up driver lineage. Ten inventoried bundles verify, plus one **unversioned post-PR-#25 handover bundle** (`egw-20260814-post-pr25-merge.bundle`, SHA-256 `53014902…`, complete history to the PR #25 merge `2dafae1`) — the current handover artefact, deliberately kept out of the provenance inventory per the management order. A verified off-machine copy is still pending: it stays open until destination-side hash verification and the restore drill are completed | G0 — In progress | M2 |
| Normative plan (v1.1, since bumped to v1.2), provenance register and technical CI | yes | static — the normative plan, archived byte-identical v1.0, D001–D008 log, source/provenance registers and CI workflows were merged to `dev` through PR #12. On 2026-08-13 its required GitHub checks passed for Python 3.11/3.14, contracts/evidence/links, shell safety, LaTeX and metadata; this verifies the change but does not itself accept a gate. Plan v2.0 was first published as a proposal under `docs/governance/proposals/` (documentation pull requests of 2026-09-18; LOG #C028) and was **adopted by the student on 2026-09-18 with the QEMU-only execution amendment** (LOG #C032), replacing v1.2 at the canonical path; v1.2 is preserved unmodified in `docs/governance/archive/`. Adoption is a student decision: it records no supervisor approval and accepts no gate | G0 — In progress; G1 — Complete (accepted 2026-08-14, gate log) | M2 |
| Normative contracts (`src/CONTRACTS.md` v1.1) + JSON schemas | yes | unit — `tests/test_schemas.py` (part of the current sealed suite of 701 tests); static — 7 valid JSON files; real integration not demonstrated | G2 — Pending | M2 |
| Scope, RQs and claim→evidence matrix (15 claims) | yes | static — **0 of 15 claims accepted**: C01 is partial (the same-operator clean-checkout rebuild is sealed; its formal claim admission is the one step still outstanding, the second-operator requirement of D006 being reported waived), C02 holds the preliminary bring-up seal and the separate strict five-boot G1 set (the later predefined `data-v1` identities remain pending unless a dated protocol decision admits this set), and the remaining **13 have no admissible experimental evidence** — all `Pending — no evidence`, C13 included: the 24-hour soak returns as a **target to attempt** under QEMU inside the 95-run composition, subject to the pilot's feasibility check, superseding its earlier deferral out of scope. The two-layer title/objective/RQ/abstract wording and the D001–D010 matrix live in the PR #15 proposal package. The decision log now carries mixed statuses (2026-09-19): `proposed_not_sent` for D001, D007, D008 and D012, `confirmed_reported_by_student` for D002 and D009, and `partly_confirmed_reported_by_student` for the rest, each naming its confirmed and its unresolved part; `sent_at` and `response_at` are empty everywhere. The title and the RQ wording published in [`docs/g0/scope_and_rqs.md`](docs/g0/scope_and_rqs.md) v2.0 are **reported approved by the student** under D011 — reported, not documented — with the approved verbatim RQ wording held in the student manuscript, so the repository publishes scope summaries | G0 — Pending | M1 |
| Backlog and risk register | yes | no (management documents) | G0 — Pending | M1 |
| WSL2 Ubuntu 24.04 guide (ext4) | yes | **installed, exercised and captured**: WSL2 with Ubuntu 24.04.4 LTS is operational, with the build directory on ext4, and produced both Yocto evidence sets. The 2026-08-14 capsule records the kernel, OS, kas/Python/Git versions, filesystem type, capacity and the separate build/driver commits in `environment.txt` (Ubuntu 26.04 was rejected first because it ships Python 3.14, outside the tested envelope of Yocto Scarthgap) | G0 — Pending | M2 |
| ARM64 VM (native measurement platform) — **deferred future work** | no | no — no university request/reply, public quotation, provisioned host or environment capture is recorded. Earlier Oracle/Hetzner/Azure attempts did not yield a non-burstable host. Under the adopted plan of 2026-09-18 the university request, the 48-hour fallback rule and the AWS `c6g.xlarge` default leave mandatory scope: **no allocation, spending or native build is requested**, and the EUR 30 ceiling stands only as a limit on any future native work that a new budget decision (D012) authorises | not a gate item of the adopted plan — **deferred with the native route; it blocks no gate**. Its absence bounds what RQ3 may claim and is recorded as an explicit limitation | M0 |
| G0 alignment email with Chapter 2 and D001–D010 | yes (draft in PR #15) | no — that August draft is not sent, and **no `sent_at` or supervisor response is recorded for any row**, because no date was reported. Recorded separately on 2026-09-19: the student **reports** that the state-of-the-art material was sent and that twelve items were confirmed (see the supervisor-agreement row above). Those are reported by the student, are not documented supervisor decisions, and do not discharge this draft | G0 — Blocked (sending the reduced package covering D007, D014 and the unresolved halves of D004 and D010 is a student action) | M1 |
| Exclusion of unsupported result content from unprovided dissertation sections | yes | source boundary — Chapters 3–6 contain headings/empty sections only in the 2026-09-17 Word import; former result placeholders and draft conclusions are not imported. This supersedes the old Chapter 5 TODO count, not the evidence-admission rules | G0 — Pending | M1 |

### Blocks G1–G7 — development on the integrated emulated platform

WSL2 exists and is operational, and since 2026-09-18 the integrated Yocto ARM64
guest under QEMU/TCG is the adopted environment for the remaining work. No
native ARM64 platform exists; under the adopted plan its absence bounds what
RQ3 may claim and defers native-boot evidence to future work, and it blocks no
gate.

| Deliverable | Implemented | Verified | Accepted at gate | M |
|---|---|---|---|---|
| `kas` manifest + `meta-egw` layer + `egw-image` recipe | yes | **integration — preliminary and strict evidence sealed**: the 2026-08-11 seal preserves the first build and two automated bring-up boots. On 2026-08-14 a new checkout/build directory at `f0e19d5` completed all 5,715 BitBake tasks successfully while deliberately reusing the external downloads/sstate cache (2,261 tasks did not need rerun; not a cold-cache claim). Rootfs SHA-256 is `6c37fcc1…`, kernel SHA-256 is `4457ef38…`, and the manifest has 639 packages. The first strict attempt is preserved as `fail`: the guest returned exact `STATE=running`, zero failed units and clean power-down, but the pre-fix predicate rejected doubled PTY carriage returns. PR #18, merged as `9fe38ff`, fixed the predicate and added a regression; five new IDs then each passed 7 of 7 required assertions, recorded 2 of 2 observations, reached the console and powered down cleanly. Both seals verify independently. Functional evidence only: nothing here supports a performance or security statement | **G1 — Complete: accepted on 2026-08-14** (decision recorded in [`docs/governance/gate_decision_log.md`](docs/governance/gate_decision_log.md), authority: student; scope: functional platform layer only — it validates no claim and supports no performance statement). The second-operator requirement of D006 is reported waived, recorded on 2026-09-18 (the date of the record, never of the waiver, for which none was reported), so no reconstruction is owed; the repeatability wording stays *versioned* and *repeatable build by the author*, and the later predefined `data-v1` identities are not silently replaced | M5 (functional scope) |
| Integrated QEMU/TCG gateway profile (`kas/egw-qemuarm64-integrated.yml`, `egw-gateway-image`, `egw-gateway-config`, `scripts/build-profile.sh`, `scripts/run-qemu-integrated.sh`, runbook `docs/setup/qemu_integrated_gateway.md`) | built and booted once under QEMU/TCG (2026-09-18); later the same day the six-container stack was **deployed in the guest** and the first bounded end-to-end flow ran — build, boot and MongoDB evidence sealed (row below), the first-flow record **outside the repository and unsealed**; sealing is not acceptance | build from commit `03e333e` (5,556 tasks) after a first attempt at `68f9ae7` failed on an RPM directory-mode conflict; two boots from commit `3209b17` after a first boot attempt failed in the wrapper's `runqemu` invocation; every artefact and guest acceptance check of runbook 2.4 and 3.4 passed (Cortex-A76 model, 4 vCPUs, 8 GiB, data disk on `/var/lib/docker`, Compose v2.26.0, key-only SSH, persistence across boots); kernel `Image` byte-identical to G1 although its tasks were re-executed; G1 build tree and inputs untouched, the eight evidence seals verify (59 artefacts). Record: `docs/reviews/2026-09-17-egw-image-audit.md` Section 13. Evidence sealed in `docs/evidence/integrated-qemu/`. ARM64 **emulated**: functional evidence only | none — the profile is the environment of the adopted plan v2.0 (2026-09-18, QEMU-only amendment); adoption accepts no gate | M1 |
| Evidence of the integrated QEMU/TCG profile (pull request #28): build, two boots, isolated MongoDB 7 test | sealed 2026-09-18 — **functional only, emulated; this capsule covers build, boot and an isolated MongoDB test and contains no stack deployment, no end-to-end flow and no measurement** | integration (emulated) — `docs/evidence/integrated-qemu/`: image built at `03e333e` after a preserved failed attempt at `68f9ae7`, two boots at `3209b17` with every build and guest acceptance check passing (Cortex-A76 model, 4 vCPUs, 8 GiB, data disk on `/var/lib/docker`, Docker 25.0.9 with Compose v2.26.0, key-only SSH, persistence across boots), kernel `Image` byte-identical to G1, G1 build tree unchanged; MongoDB 7.0.39 pulled by digest inside the guest: start, write/read, restart, recreation and persistence across a guest power cycle, 35 checks, 0 failed. Manifests verified by `tools/ci/verify_evidence.py` | none — sealing is not acceptance; no gate, no claim | M2 |
| Record of the first end-to-end flow in the guest (2026-09-18) | produced 2026-09-18 — **candidate evidence held outside the repository; not sealed, not in `docs/evidence/`** | integration (emulated), unsealed — six containers deployed inside the Yocto guest; one smartwatch at 1 Hz for 60 s; 60 sent, 60 delivered unique, 0 lost, 0 late, 0 duplicate, 0 failed, 0 rejected; twin `org.c2dta:5689c879-…` with `last_seq` 59; reconciliation by identity exited 0; maximum latency 12,286 ms, **emulated and informational, never a performance result**. The run exposed and led to two fixes on `dev` (controller on the wrong Compose network, `9ffd365`; relative schema directory inherited by the host shell, `dc6d8bb`, `22fb0a9`), and a memory-cgroup OOM killed the `ditto-things` JVM during the power-off of that session at the 512 MiB container limit; the corrective work is open and is a separate change | none — unsealed candidate evidence admits no claim and closes no gate; it becomes admissible only once sealed in the repository and admitted by a dated decision | M2 (emulated, unsealed) |
| Minimal ARM64 compose (Mosquitto TLS, Ditto 3.9.4, MongoDB, controller) | yes | static — `docker compose config` (syntactic validation, no persisted log); arm64 digests verified documentally on 2026-08-07. On 2026-09-18 the six services were deployed from this configuration inside the emulated Yocto guest, so operational `.env`, certificates and secrets existed for that run; that record is the unsealed candidate evidence above and is not held in the repository | G2 — Pending (no native prerequisite; the gate now depends on sealed, identity-reconciled evidence from the emulated guest) | M2 |
| Broker secret hand-over and ACL probe (`scripts/prepare-broker-secrets.sh`, `scripts/probe-acl.sh`, step 3b of `validate-config.sh`) | written 2026-09-18 — **whether either script was executed during the first-flow session of 2026-09-18 is not recorded in this repository**; verify against the run record before restating it either way | unit (stubs) — `src/tests/test_probe_acl_verdict.py`: 94 cases of the probe's verdict logic under dash and bash with a stub `docker` (Linux only; skipped on Windows); `sh -n` on every script. Mosquitto 2 opens `password_file` and `keyfile` after dropping to uid 1883, so both are handed to that uid with mode 0600 and the read is proved in a one-shot container; the probe proves the ACL with known traffic and answers PASS, FAIL or INCONCLUSIVE, never PASS on an execution error or an incomplete broker-log collection | none — accepts no gate | M2 |
| Prebuilt controller image in the deployment and versioned reconciliation helper (`compose.yaml` without `build:` and with `pull_policy: never`, `scripts/build-controller-image.sh`, `scripts/verify-controller-image.sh`, step 7 of `validate-config.sh`, `src/egw_experiments/itest_reconcile.py`; LOG `#C030`) | written 2026-09-18 and **exercised the same day**: the controller image was built, loaded into the emulated guest and run there for the first end-to-end flow, and the reconciliation helper exited 0 by identity (unsealed candidate evidence, row above). The controller image still has **unlocked Python dependencies** (`pip install .`); such an image is not admissible for thesis measurements and this must be resolved before the protocol freeze | unit (stubs and fakes) — `src/tests/test_deployment_prebuilt_controller.py` (35 cases: 7 read the compose decision as text on every platform, 28 run both scripts with a stub `docker` under dash and bash on Linux) and `src/tests/test_experiments_itest_reconcile.py` (106 cases, fakes only, unmodified `compute_run_metrics`, the confirmation window imported and never redefined, every `$REC` line extracted from the runbook and parsed); `docker compose config` accepts the file and the resolved model differs from the previous one only in the controller's `build`/`pull_policy`; runbook Sections 4 to 7 follow the route (five external images pulled by pinned digest inside the guest, controller loaded from a checksummed archive and compared with its identity record, the deployment tree and the harness checked out at that image's commit). ShellCheck not run locally | none — accepts no gate | M2 |
| MQTT→Ditto controller | yes | unit — tests with fakes (part of the current sealed suite of 701 tests); the progress counters of `GET /metrics` added on 2026-09-18 (`received`, `in_progress`, `processing_errors`, ADR 0010) are unit-verified by tests **outside the sealed suite** — accounting identity, single-snapshot reading, fault and cancellation paths, all with fakes. On 2026-09-18 the controller ran against a real Mosquitto broker and a real Ditto inside the emulated ARM64 guest for the first bounded flow (unsealed candidate evidence, row above); **no real restart has been exercised**, and the progress counters remain unit-verified only | G2 — Pending | M2 |
| Unified simulator (3 wearables, 6 scenarios) | yes | unit — determinism verified; `dropout-reconnect` induces a real MQTT disconnection with buffering and ordered redelivery (audit §7.3 correction completed on 2026-08-08; covers C10 at unit level) | G2–G3 — Pending | M2 |
| WoT TD 1.1 Thing Descriptions | yes | unit — `tests/test_things.py` cross-checks TD↔schema; real integration not demonstrated | G2–G3 — Pending | M2 |
| Experimental harness + analysis | yes | unit — audit §9 gaps corrected on 2026-08-08 (blocks P1a–P1c: gating by validity, host provenance, acceptance with completeness, soak DoD, cadence caps, saturation with sufficiency of evidence, write-once sealed raw data, `campaign` batch runner); PR #13 rejects resource samples from a different UTC window, enforces at least 90% coverage and the protocol gap cap per container, makes simulator run directories write-once, propagates QEMU pipeline failures and makes `systemd=running` plus zero failed units strict boot assertions. After the PR #17 campaign-path regression and PR #18 PTY regression, the current evidence branch passed `718` tests locally on 2026-08-14; this is **not** a new test-evidence seal, so the canonical sealed figure remains 701. Live proof of the harness and the hashed runtime lock for the controller image are now owed by the **emulated guest**, before the protocol freeze | G4 — Pending (the harness sits outside G1's accepted functional scope) | M2 |
| `experiments/results/` evidence structure | yes | static — `raw/processed/figures` directories created; zero data (experimental evidence M0) | G5 — Pending | M1 |
| Dissertation (Word-source Chapters 1–2 with empty remaining sections) | yes | local document verification — source fidelity passed for 56 text blocks, 117 table cells, 33 references and the figure; seven projection tests passed; Markdown regeneration is identical; the supplied-template PDF compiles to 43 pages, including empty structure and front matter, with no unresolved citations or overfull boxes. Evidence: [WORD_IMPORT.md](thesis/latex/WORD_IMPORT.md). Previous draft counts are historical; this is not bibliographic validation or a complete dissertation | G6 — Pending | M2 (document verification only) |
| Review sources (`thesis/research/study_selection.csv`) | yes | historical research register — 25 sources recorded, with verified metadata (Crossref/W3C/OASIS/official pages). **Reading depth: 7 assessed in full text (S001, S004–S009) and 18 by title/abstract only** (`stage=title_abstract`, provisional inclusion for the previous supervisor draft; the full-text pass is still to be run). This register is unchanged and is not a verification record for the 33 Word-imported reference strings. No fresh metadata audit is claimed; institutional queries remain pending (student action, risk R17) | G6 — Pending | M1 |
| Standalone Chapter 2 review derivative | yes | local document verification — current source follows the imported Chapter 2 and compiles to 10 pages with no unresolved citations or overfull boxes. Evidence: [WORD_IMPORT.md](thesis/latex/WORD_IMPORT.md). The PR #14 16-page PDF and its former checksum describe the historical draft only. Source conversion is not evidence that a document was sent | not a gate item — sending is a student action (no gate closes on this) | M2 (document verification only) |
| Unit test suite | yes | unit — **sealed evidence: `701 passed`** over clean HEAD `4e67717` in `docs/evidence/tests/2026-08-11-head-4e67717/`, with JUnit, stdout, environment, interpreter, `pip freeze`, `pip check`, pytest version, SHA-256 of the lock file and `SHA256SUMS`. Current sealed figure: `701`. Earlier sealings are kept for traceability and are **historical only** (`683`, `618`, `593`, `515`), each tied to the commit it tested and never the current figure. **Zero live/`integration` tests exist** — creating them is a prerequisite for G3 | G3 — Pending | M2 |
| Post-audit harness corrections (event fetch, 2 environments, collector on the VM, measured window, conditions C10–C14, queue growth, normalised CPU) | yes | unit — tests included in the current sealed suite of 701 (they were first sealed in the historical run of `593`); campaign plan with 95 runs — a historical plan of the native era, superseded by the emulated functional campaign to be selected at the bounded pilot; acceptance requires completeness (by identity against the plan when the plan is supplied to the analysis) and evidence — including evidence of real recovery in C12; real execution now owed by the emulated guest | G3–G4 — Pending | M2 |

Note: "Implemented = yes" means only that the artefact exists and, where stated,
passed unit/static verification in this repository. Gates G1–G5 close only with
evidence of real execution (QEMU build/boot — produced for G1 on 2026-08-11 —,
deployment in the emulated Yocto guest, a sealed end-to-end trace, campaign
data); what remains still depends on the external actions below.

## Gate status as at 2026-09-18

Factual record after the adoption of plan v2.0 with the QEMU-only execution
amendment. **The adoption closes no gate and admits no claim**; gate outcomes
are recorded solely in
[`the formal gate-decision log`](docs/governance/gate_decision_log.md).

- **G0 — Not decided.** The reduced alignment package — D007, D014 and the
  unresolved halves of D004 and D010 — remains unsent, and the verified
  off-machine copy remains outstanding. The confirmations reported by the
  student on 2026-09-18 close nothing here. The university
  ARM64 request and its 48-hour fallback rule are **deferred with the native
  route** and are no longer conditions of this gate.
- **G1 — Accepted on 2026-08-14**, functional platform layer only, unchanged by
  the adoption. It validates no claim.
- **G2 — Not decided.** Native deployment is outside the adopted scope. A
  bounded end-to-end flow ran inside the emulated Yocto guest on 2026-09-18;
  its record is candidate evidence held outside the repository and unsealed, so
  no acceptance evidence exists.
- **G3 — Not decided.** The nine integration/recovery test families were
  exercised once on 2026-09-18: seven passed, and tests 1 and 6 carry a failing
  harness part, because the resource sampler under test cannot reach the
  harness's minimum sample count under emulation. That record is held outside
  the repository and unsealed; the battery is **not complete**, nothing has been
  measured and no live `integration` test exists in the pytest suite. The
  instrumentation defect is a separate change.
- **G4 — Not decided.** No bounded pilot and no protocol freeze; the controller
  image still installs its Python dependencies without a hashed lock.
- **G5 — Not decided.** No frozen emulated functional campaign;
  `experiments/results/raw/` is empty. Since 2026-09-19 the 95-run composition,
  the 24-hour soak included, is the quantity the campaign **attempts to reach**
  under QEMU, subject to the pilot's feasibility check; this supersedes the
  earlier statement that it was not carried over. The attempt is not the frozen
  protocol and promises no valid run count.
- **G6 — Not decided.** No analysis exists, because no admitted data exists.
- **G7 — Not decided.** No release candidate exists.
- **Prospective acceptance criteria** for G2–G7 under the integrated emulated
  system live in the adopted plan. They are prospective: writing them accepts
  nothing.

## Gate status as at 2026-08-14

> Dated snapshot, kept as written. Its native prerequisites and its August
> windows were superseded on 2026-09-18 by the adopted plan v2.0 with the
> QEMU-only execution amendment; read the 2026-09-18 block above for the
> current position. Historical records are not rewritten.
>
> **Forward pointer added 2026-09-19.** Its statements that the alignment email
> had not been sent and that D001–D010 all remained `proposed_not_sent` were
> true when written. They are superseded by the confirmations the student
> reports: read the 2026-09-19 update note at the top of this file and the
> supervisor-agreement row above. The sentences below are not edited.

Factual record of the situation. **Nothing here declares a gate closed or
failed**: the gate decision belongs to the student and the supervisors and is
recorded only in the
[`formal gate-decision log`](docs/governance/gate_decision_log.md), with its
dated decision record. [`LOG.md`](LOG.md) is a diary, not that authority.

- **G0 (13–15 August) — In progress.** The versioned plan/provenance controls,
  source register and draft alignment package exist. The alignment email has
  not been sent, D001–D010 remain `proposed_not_sent`, no university ARM64
  request/reply is recorded and there is no off-machine bundle copy. WSL2 with
  Ubuntu 24.04.4 LTS on ext4 is operational; its kernel, OS, tool and filesystem
  capture is now archived with the 2026-08-14 G1 evidence. Repository changes
  cannot substitute for the remaining external actions.
- **Current ARM64 fallback rule (plan v1.2):** record the university request and
  allow 48 hours for confirmation; otherwise obtain a current quotation for a
  non-burstable public ARM64 host, confirm the forecast stays within EUR 30,
  and only then provision. No request timestamp, quotation or provisioned host
  is recorded, so the 48-hour clock cannot be claimed to have started.
- **G1 (13–18 August)** — the technical execution requested by plan v1.1 (historical reference; the plan line is now v1.2) is
  now archived: the preliminary seal remains intact, and the 2026-08-14 nested
  seal contains a clean-checkout build at `f0e19d5`, one preserved
  instrumentation-failure attempt, and five fresh boots driven at `9fe38ff`,
  each with 7 of 7 required assertions, 2 of 2 observations, zero failed units
  and a clean power-down. **The gate was formally accepted on 2026-08-14**
  (student authority, decision recorded in the
  [gate decision log](docs/governance/gate_decision_log.md)); the acceptance
  covers the functional platform layer only and validates no claim. A
  second-operator reconstruction is the separate D006 decision, and later
  `data-v1` identities remain separate. No QEMU evidence supports a
  performance or security claim.
- **G2 (15–23 August; serious-risk trigger 25 August)** — unchanged: zero deployments on the
  ARM64 VM, which does not exist; `experiments/results/raw/` remains empty.
- **G3–G7** — unchanged; they still depend on evidence of real execution (and G3
  additionally requires live/`integration` tests, which do not exist).
- **PRs #12–#25 are governance, technical, operational-record,
  G1-path and factual academic corrections.** They raise provenance,
  instrumentation and documentary quality. **PR #21 is the single exception
  that records a formal gate decision**: it merged the G1 acceptance row of
  2026-08-14 into `docs/governance/gate_decision_log.md`. None of the others
  records any gate decision, and the PR #15 proposal package, though merged,
  has no normative effect before explicit supervisor decisions.

## External student actions (with deadlines)

| Action | Deadline | Expected evidence |
|---|---|---|
| Send the **reduced** alignment package covering the rows that remain open — the thresholds (D007), the scope of the evaluation and the academic use of emulated results (D014), the authenticity of the local template copy with the cover and metadata (inside D004) and the operational storage semantics (inside D010) — using the revised memo (drafts under `docs/g0/` and `docs/governance/proposals/`) | **immediate**; silence is never approval for these rows | email sent; copy/date in the LOG and decision-log `sent_at` fields. The state-of-the-art material is reported sent with no date held, so no `sent_at` is written for it |
| Authenticate the local `Template_LaTeX` copy against the current official 2026 source, and settle the cover and front-matter metadata (the open half of D004) | immediate | request and reply recorded in the LOG and canonical decision log. The **requirement** to use the institution-supplied template is reported confirmed and is not re-requested |
| Prepare the AI-use declaration during drafting and verify it at G7 | before packaging on 2026-10-19 | a truthful declaration in the applicable institutional format, identifying the actual assistance received and the author's responsibility; reported mandatory by final submission |
| Install Ubuntu 24.04 on WSL2 with the build directory on ext4 (guide in `docs/setup/wsl2_ubuntu_yocto.md`) | 2026-08-09 to 2026-08-10 | **done and evidenced**: Ubuntu 24.04.4 LTS operational on ext4; the 2026-08-14 capsule records kernel, OS, tools, filesystem type/capacity and the clean build/driver identities |
| ~~Request a university ARM64 host and apply the 48-hour public-host fallback rule~~ | **Deferred on 2026-09-18 with the native route.** It is not an obligation of the adopted plan, it closes no gate and the adopted plan requests no allocation or spending. The historical row is kept so the deferral is visible rather than silently deleted | none required; if native work is ever authorised, the original evidence list applies unchanged |

## Platforms — two evidence classes (adopted plan v2.0, 2026-09-18)

The three-tier platform model of ADR 0007 described a native measurement tier
that was never provisioned. Under the adopted plan the project has **two
evidence classes**, and the earlier tier table is historical.

| Class | Environment | What it may support | Numbers in the thesis |
|---|---|---|---|
| **Emulated — the adopted environment** | Yocto-produced ARM64 kernel and root filesystem booted under QEMU/TCG on the existing x86-64 workstation, hosting the six containers; simulator and harness outside the guest | Correctness, fault handling, recovery, persistence, deployment and repeatability, each against explicit criteria. Timing, observed throughput and resource use are **informational, labelled emulated**, describe only the identified emulated configuration and are never native ARM capacity, physical-device latency, energy efficiency or performance superiority | Only as explicitly emulated, informational observations, and only if the supervisors agree to their academic use (D014). Guest and container readings are never converted to host QEMU-process readings by an assumed slowdown factor |
| **Native — documented, unverified future work** | A compatible ARM64 host (QEMU/KVM or a provider-managed VM), not built and not booted | Nothing yet. Any native performance evaluation needs its own protocol and data; old emulated results never become native evidence after a port | **None exist.** Their absence is an explicit limitation of this dissertation |

Hard rules that survive unchanged: emulated and any future native runs are
**never pooled in one aggregate**; the published integrated profile's four
virtual CPUs and 8 GiB are emulator settings, not a demonstrated equivalence to
a four-core physical gateway; and no number from a burstable host would ever
enter the dissertation if native work resumed.

The historical tier table of 2026-08-14 is retained in
[`docs/adr/0007-three-tier-platform-model.md`](docs/adr/0007-three-tier-platform-model.md)
and in the risk register, and applies only to any future native work.

## Effort control — critical path (audit §5.2)

Daily control skeleton (<10 min/day). Values marked `(est.)` are estimates from
audit §12.1; `actual_h`, `remaining_h` and `forecast` are filled in by the
student — do not invent hours. Empty cells = still to be estimated/filled in.

> **Note (2026-08-08, confirmed on 2026-08-10):** the `actual_h`, `remaining_h`
> and `forecast` columns are deliberately **empty** and are to be filled in by
> the student alone: they are human effort and no agent may estimate or infer
> them. The durations of work carried out by agents do not enter this table —
> they are recorded in the entries of [`LOG.md`](LOG.md). While these three
> columns remain empty, **there is no completion forecast** and risk RA15 stays
> materialised (see [`docs/g0/risks.md`](docs/g0/risks.md)).

Due dates below are the **planning targets** of the adopted plan v2.0 of
2026-09-18. None of them is an achieved milestone; a missed target is reported
with its cause, the remaining work and a revised forecast, never silently
moved. The `planned_h` estimates of 2026-09-16 are superseded pending the
student's re-estimate after the integration battery, so the column is left as
it was and is not re-derived here.

| Item (critical path) | owner | planned_h | actual_h | remaining_h | due | evidence | forecast | blocker |
|---|---|---|---|---|---|---|---|---|
| Reduced alignment package: D007, D014 and the unresolved halves of D004 and D010 | Student | 0.5–1 (est.) | | | immediate | email + date in the LOG and decision log | | not sent |
| Scoping-review protocol, search, selection and synthesis | Student | | | | protocol 2026-09-21; search and selection 2026-09-26; synthesis 2026-09-30 | dated protocol revision, logged searches and exports, screening decisions, evidence chart, selection flow and synthesis, owned by `thesis/research/` | | working targets, to be re-estimated against the real corpus at the 2026-09-21 checkpoint |
| AI-use declaration | Student | | | | prepared during drafting; verified at G7 | truthful declaration in the applicable institutional format | | reported mandatory by final submission |
| WSL2 Ubuntu 24.04 on ext4 | Student | 2–4 (est.) | | | 2026-08-09 to 2026-08-10 | **produced:** version, tools, filesystem and capacity archived in the 2026-08-14 G1 capsule | | |
| ~~ARM64 VM `aarch64`~~ | Student | 1–2 (est.) | | | **deferred 2026-09-18 with the native route** | none required by the adopted plan | | not a blocker of any gate |
| Independent Git backup | Both | 0.5–1 (est.) | | | before further cleanup | private remote plus verified full bundle/checksum copied and verified off-machine | | off-machine destination not recorded |
| Theoretical framing sprint | Both | 18–24 (est.) | | | 2026-08-10 to 2026-08-11 | draft of 4,000–5,000 words + research logs filled in | | |
| Clean Yocto rebuild + five strict QEMU boots | Student | | | | 2026-08-18 | **produced and sealed 2026-08-14:** build at `f0e19d5`; five fresh result/log pairs driven at `9fe38ff`, each with `systemd=running`, zero failed units and clean shutdown; one earlier instrumentation failure preserved; nested `SHA256SUMS` verifies | | gate G1 accepted 2026-08-14 (gate log); the second operator of D006 is reported waived, so nothing further is owed here |
| Governance publication of the adopted plan | Both | | | | 2026-09-18 | this documentation change; it confirms consistency only and accepts no gate | | |
| First bounded end-to-end flow in the guest | Both | | | | 2026-09-18 | **ran 2026-09-18, emulated:** 60/60 accounted, twin `last_seq` 59, reconciliation exit 0; record held outside the repository and unsealed | | sealing inside the repository is outstanding |
| Nine integration/recovery test families in the guest | Both | | | | 2026-09-21 to 2026-09-24 | per-test evidence, failures and residual risks; **exercised once on 2026-09-18, not complete** — seven passed, tests 1 and 6 carry a failing harness part from the resource sampler under emulation; the record is held outside the repository and unsealed | | teardown OOM and container memory sizing open; the resource-sampler instrumentation defect is a separate change |
| Stable integrated QEMU baseline | Both | | | | 2026-09-25 | no unresolved failure incompatible with the claimed stability scope | | nine test families |
| Bounded pilot + protocol freeze (`exp-v1`) | Both | | | | 2026-09-26 to 2026-09-29 | prospectively selected run identities, repeats, durations and acceptance criteria; hashed runtime lock for the controller image | | stable baseline; D007 |
| Frozen emulated functional campaign | Both | | | | 2026-09-30 to 2026-10-02 | complete `raw/<run_id>/` + `SHA256SUMS` for the frozen set | | `exp-v1` |
| Data freeze and analysis (`data-v1`) | Both | | | | 2026-10-03 to 2026-10-05 | every figure and table traceable to immutable evidence | | frozen campaign |
| Chapters 1–4 sent | Student | | | | 2026-10-01 | sending email recorded in the LOG | | written in parallel; does not wait for the tests |
| Full draft sent | Student | | | | 2026-10-08 | sending email recorded in the LOG | | `data-v1` for the results chapters |
| Feedback, corrections and QA | Both | | | | 2026-10-09 to 2026-10-18 | change list, replies and unresolved-item rationale | | supervisor turnaround must be requested, not assumed |
| Packaging and submission | Student | | | | package 2026-10-19; submit 2026-10-20 | reproduction package, checksums and the portal receipt | | final delivery deadline 2026-10-31; 2026-10-21 to 2026-10-31 is essential contingency only |
