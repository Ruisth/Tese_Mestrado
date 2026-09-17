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
same-operator clean-checkout build is now produced and sealed, while D006 still
has to decide whether a second operator is required before retaining a stronger
reproducibility claim. C02 has the preliminary two-boot seal and the new strict
five-boot G1 set; the predefined later `data-v1` identities and the formal
claim admission remain separate — the gate decision admitted no claim. The remaining **13 still have no admissible experimental
evidence**. **Gate G1 is the only accepted gate** (2026-08-14, functional
platform layer only — accepting the gate validated no claim); G0 and G2–G7
remain undecided.

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
| Normative plan (v1.1, since bumped to v1.2), provenance register and technical CI | yes | static — the normative plan, archived byte-identical v1.0, D001–D008 log, source/provenance registers and CI workflows were merged to `dev` through PR #12. On 2026-08-13 its required GitHub checks passed for Python 3.11/3.14, contracts/evidence/links, shell safety, LaTeX and metadata; this verifies the change but does not itself accept a gate | G0 — In progress; G1 — Complete (accepted 2026-08-14, gate log) | M2 |
| Normative contracts (`src/CONTRACTS.md` v1.1) + JSON schemas | yes | unit — `tests/test_schemas.py` (part of the current sealed suite of 701 tests); static — 7 valid JSON files; real integration not demonstrated | G2 — Pending | M2 |
| Scope, RQs and claim→evidence matrix (15 claims) | yes | static — **0 of 15 claims accepted**: C01 is partial (the same-operator clean-checkout rebuild is sealed; D006/second-operator treatment and formal claim admission remain pending), C02 holds the preliminary bring-up seal and the separate strict five-boot G1 set (the later predefined `data-v1` identities remain pending unless a dated protocol decision admits this set), and the remaining **13 have no admissible experimental evidence**. The two-layer title/objective/RQ/abstract wording and the D001–D010 matrix live in the PR #15 proposal package; the canonical decision log remains `proposed_not_sent` for all ten decisions | G0 — Pending | M1 |
| Backlog and risk register | yes | no (management documents) | G0 — Pending | M1 |
| WSL2 Ubuntu 24.04 guide (ext4) | yes | **installed, exercised and captured**: WSL2 with Ubuntu 24.04.4 LTS is operational, with the build directory on ext4, and produced both Yocto evidence sets. The 2026-08-14 capsule records the kernel, OS, kas/Python/Git versions, filesystem type, capacity and the separate build/driver commits in `environment.txt` (Ubuntu 26.04 was rejected first because it ships Python 3.14, outside the tested envelope of Yocto Scarthgap) | G0 — Pending | M2 |
| ARM64 VM (measurement platform) | no | no — no university request/reply, public quotation, provisioned host or environment capture is recorded. Earlier Oracle/Hetzner/Azure attempts did not yield a non-burstable host. Plan v1.2 requires the university request first and a price check after 48 hours; AWS `c6g.xlarge` is the default fallback, subject to the EUR 30 ceiling | G0 — **Blocked: native non-burstable ARM64 host absent** | M0 |
| G0 alignment email with Chapter 2 and D001–D010 | yes (draft in PR #15) | no — not sent; no `sent_at` or supervisor response is recorded | G0 — Blocked (sending is a student action; follow-up 2026-08-18 and meeting request 2026-08-20 if unanswered) | M1 |
| Exclusion of unsupported result content from unprovided dissertation sections | yes | source boundary — Chapters 3–6 contain headings/empty sections only in the 2026-09-17 Word import; former result placeholders and draft conclusions are not imported. This supersedes the old Chapter 5 TODO count, not the evidence-admission rules | G0 — Pending | M1 |

### Blocks G1–G7 — development brought forward without the ARM64 measurement VM

WSL2 now exists and is operational; the platform that is still missing is the
ARM64 measurement VM.

| Deliverable | Implemented | Verified | Accepted at gate | M |
|---|---|---|---|---|
| `kas` manifest + `meta-egw` layer + `egw-image` recipe | yes | **integration — preliminary and strict evidence sealed**: the 2026-08-11 seal preserves the first build and two automated bring-up boots. On 2026-08-14 a new checkout/build directory at `f0e19d5` completed all 5,715 BitBake tasks successfully while deliberately reusing the external downloads/sstate cache (2,261 tasks did not need rerun; not a cold-cache claim). Rootfs SHA-256 is `6c37fcc1…`, kernel SHA-256 is `4457ef38…`, and the manifest has 639 packages. The first strict attempt is preserved as `fail`: the guest returned exact `STATE=running`, zero failed units and clean power-down, but the pre-fix predicate rejected doubled PTY carriage returns. PR #18, merged as `9fe38ff`, fixed the predicate and added a regression; five new IDs then each passed 7 of 7 required assertions, recorded 2 of 2 observations, reached the console and powered down cleanly. Both seals verify independently. Functional evidence only: nothing here supports a performance or security statement | **G1 — Complete: accepted on 2026-08-14** (decision recorded in [`docs/governance/gate_decision_log.md`](docs/governance/gate_decision_log.md), authority: student; scope: functional platform layer only — it validates no claim and supports no performance statement). D006 remains a separate second-operator decision, and the later predefined `data-v1` identities are not silently replaced | M5 (functional scope) |
| Minimal ARM64 compose (Mosquitto TLS, Ditto 3.9.4, MongoDB, controller) | yes | static — `docker compose config` (syntactic validation, no persisted log); arm64 digests verified documentally on 2026-08-07; operational `.env`/certificates/passwords do not exist | G2 — Blocked (requires the ARM VM; gate 2026-08-23, trigger 2026-08-25) | M1 |
| MQTT→Ditto controller | yes | unit — tests with fakes (part of the current sealed suite of 701 tests); no real MQTT/Ditto, no real restart, no ARM64 | G2 — Pending | M2 |
| Unified simulator (3 wearables, 6 scenarios) | yes | unit — determinism verified; `dropout-reconnect` induces a real MQTT disconnection with buffering and ordered redelivery (audit §7.3 correction completed on 2026-08-08; covers C10 at unit level) | G2–G3 — Pending | M2 |
| WoT TD 1.1 Thing Descriptions | yes | unit — `tests/test_things.py` cross-checks TD↔schema; real integration not demonstrated | G2–G3 — Pending | M2 |
| Experimental harness + analysis | yes | unit — audit §9 gaps corrected on 2026-08-08 (blocks P1a–P1c: gating by validity, host provenance, acceptance with completeness, soak DoD, cadence caps, saturation with sufficiency of evidence, write-once sealed raw data, `campaign` batch runner); PR #13 rejects resource samples from a different UTC window, enforces at least 90% coverage and the protocol gap cap per container, makes simulator run directories write-once, propagates QEMU pipeline failures and makes `systemd=running` plus zero failed units strict boot assertions. After the PR #17 campaign-path regression and PR #18 PTY regression, the current evidence branch passed `718` tests locally on 2026-08-14; this is **not** a new test-evidence seal, so the canonical sealed figure remains 701. Live proof and the ARM64 runtime lock remain pending the VM | G4 — Pending (the harness sits outside G1's accepted functional scope) | M2 |
| `experiments/results/` evidence structure | yes | static — `raw/processed/figures` directories created; zero data (experimental evidence M0) | G5 — Pending | M1 |
| Dissertation (Word-source Chapters 1–2 with empty remaining sections) | yes | local document verification — source fidelity passed for 56 text blocks, 117 table cells, 33 references and the figure; seven projection tests passed; Markdown regeneration is identical; the supplied-template PDF compiles to 43 pages, including empty structure and front matter, with no unresolved citations or overfull boxes. Evidence: [WORD_IMPORT.md](thesis/latex/WORD_IMPORT.md). Previous draft counts are historical; this is not bibliographic validation or a complete dissertation | G6 — Pending | M2 (document verification only) |
| Review sources (`thesis/research/study_selection.csv`) | yes | historical research register — 25 sources recorded, with verified metadata (Crossref/W3C/OASIS/official pages). **Reading depth: 7 assessed in full text (S001, S004–S009) and 18 by title/abstract only** (`stage=title_abstract`, provisional inclusion for the previous supervisor draft; the full-text pass is still to be run). This register is unchanged and is not a verification record for the 33 Word-imported reference strings. No fresh metadata audit is claimed; institutional queries remain pending (student action, risk R17) | G6 — Pending | M1 |
| Standalone Chapter 2 review derivative | yes | local document verification — current source follows the imported Chapter 2 and compiles to 10 pages with no unresolved citations or overfull boxes. Evidence: [WORD_IMPORT.md](thesis/latex/WORD_IMPORT.md). The PR #14 16-page PDF and its former checksum describe the historical draft only. Source conversion is not evidence that a document was sent | not a gate item — sending is a student action (no gate closes on this) | M2 (document verification only) |
| Unit test suite | yes | unit — **sealed evidence: `701 passed`** over clean HEAD `4e67717` in `docs/evidence/tests/2026-08-11-head-4e67717/`, with JUnit, stdout, environment, interpreter, `pip freeze`, `pip check`, pytest version, SHA-256 of the lock file and `SHA256SUMS`. Current sealed figure: `701`. Earlier sealings are kept for traceability and are **historical only** (`683`, `618`, `593`, `515`), each tied to the commit it tested and never the current figure. **Zero live/`integration` tests exist** — creating them is a prerequisite for G3 | G3 — Pending | M2 |
| Post-audit harness corrections (event fetch, 2 environments, collector on the VM, measured window, conditions C10–C14, queue growth, normalised CPU) | yes | unit — tests included in the current sealed suite of 701 (they were first sealed in the historical run of `593`); campaign plan with 95 runs; acceptance requires completeness (by identity against the plan when the plan is supplied to the analysis) and evidence — including evidence of real recovery in C12; real execution pending the VM | G3–G4 — Pending | M2 |

Note: "Implemented = yes" means only that the artefact exists and, where stated,
passed unit/static verification in this repository. Gates G1–G5 close only with
evidence of real execution (QEMU build/boot — produced for G1 on 2026-08-11 —,
ARM deployment, E2E trace, campaign data); what remains still depends on the
external actions below.

## Gate status as at 2026-08-14

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
| Send the consolidated G0/alignment email to the supervisors with Chapter 2 and D001–D010 (drafts under `docs/g0/`) | 2026-08-13 — **immediate**; follow up 2026-08-18 and request a short meeting on 2026-08-20 if unanswered | email sent; copy/date in the LOG and decision-log `sent_at` fields |
| Confirm the official 2026 template, submission/front-matter requirements and any authorised contingency (D004 and the G0 email) | immediate; request an explicit reply with D001–D008 | request and reply recorded in the LOG and canonical decision log |
| Install Ubuntu 24.04 on WSL2 with the build directory on ext4 (guide in `docs/setup/wsl2_ubuntu_yocto.md`) | 2026-08-09 to 2026-08-10 | **done and evidenced**: Ubuntu 24.04.4 LTS operational on ext4; the 2026-08-14 capsule records kernel, OS, tools, filesystem type/capacity and the clean build/driver identities |
| Request a university ARM64 host; if not confirmed within 48 hours, obtain/provision the approved public fallback (non-burstable, 4 vCPU, 8 GiB, >=80 GB, maximum total EUR 30) and validate `uname -m` = `aarch64` | request 2026-08-13; fallback trigger 48 h after recorded request | request/reply in LOG; then `uname -a`, `lscpu`, `/etc/os-release`, provider/region/tenancy and environment manifest — **not done: the VM does not exist** |

## Platforms — three tiers (extension of ADR 0001, to be validated with the supervisors)

The unavailability of non-burstable ARM64 capacity forced a distinction between an
integration platform and a measurement platform. Hard rule: **no number from the
B series enters the dissertation.**

| Role | Platform | State | Numbers in the thesis |
|---|---|---|---|
| Functional (OS/boot) | QEMU `qemuarm64` on WSL2 | preliminary two-boot seal preserved; 2026-08-14 same-operator clean-checkout build completed 5,715 tasks and five fresh strict boots each passed 7/7 assertions with zero failed units. One instrumentation false negative is preserved separately. Gate G1 accepted 2026-08-14 (functional scope; decision in the gate log) | Never (plan §3.1) — functional only; QEMU results never support a performance or security statement |
| ARM64 integration | Azure `B4pls_v2` (burstable SKU identified) | no instance provisioned; eligibility/capacity still require confirmation | **Never** — CPU credits would corrupt the load sweep and the saturation criterion |
| Measurement (RQ3) | University host or public non-burstable native ARM64; AWS `c6g.xlarge` is the default public fallback | **does not exist; no current quotation recorded** | **Exclusively from here** |

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

| Item (critical path) | owner | planned_h | actual_h | remaining_h | due | evidence | forecast | blocker |
|---|---|---|---|---|---|---|---|---|
| G0 alignment email + D001–D010 | Student | 0.5–1 (est.) | | | immediate; follow-up 2026-08-18 | email + date in the LOG and decision log | | not sent |
| WSL2 Ubuntu 24.04 on ext4 | Student | 2–4 (est.) | | | 2026-08-09 to 2026-08-10 | **produced:** version, tools, filesystem and capacity archived in the 2026-08-14 G1 capsule | | |
| ARM64 VM `aarch64` | Student | 1–2 (est.) | | | request 2026-08-13; quotation after 48 h without confirmation | request/reply, price check, then initial manifest | | institutional response/account/payment |
| Independent Git backup | Both | 0.5–1 (est.) | | | before further cleanup | private remote plus verified full bundle/checksum copied and verified off-machine | | off-machine destination not recorded |
| Theoretical framing sprint | Both | 18–24 (est.) | | | 2026-08-10 to 2026-08-11 | draft of 4,000–5,000 words + research logs filled in | | |
| Clean Yocto rebuild + five strict QEMU boots | Student | | | | 2026-08-18 | **produced and sealed 2026-08-14:** build at `f0e19d5`; five fresh result/log pairs driven at `9fe38ff`, each with `systemd=running`, zero failed units and clean shutdown; one earlier instrumentation failure preserved; nested `SHA256SUMS` verifies | | gate G1 accepted 2026-08-14 (gate log); D006 treatment still pending |
| E2E vertical slice on the VM | Both | | | | 2026-08-23 (trigger 2026-08-25) | trace `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` | | ARM VM |
| Harness corrections (R18–R22) | Agent | | | | before 2026-09-06 | valid pilot with no ad hoc intervention | | |
| Full pilot + tag `exp-v1` | Both | | | | 2026-09-06 | pilot data in `raw/` with manifests | | corrected harness |
| Official campaign + `data-v1` | Both | | | | 2026-09-13 18:00 | complete `raw/<run_id>/` + `SHA256SUMS` | | `exp-v1` |
| Full draft to the supervisors | Both | | | | 2026-09-18 | sending email recorded in the LOG | | `data-v1` |
