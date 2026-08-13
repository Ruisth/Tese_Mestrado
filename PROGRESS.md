# PROGRESS — single source of state per deliverable

> **This file is the single source of state for the project.** The backlog
> ([`docs/g0/backlog.md`](docs/g0/backlog.md)) holds only actions, expected
> evidence, dependencies and cut rules — it holds no state. The formal record of
> gate decisions lives in the decision records linked by the integrated plan;
> the "Accepted at gate" column below mirrors it. Structure as per the external audit of 2026-08-08
> (§5.1, §5.2, §14).

Updated: 2026-08-13 (plan v1.1 and provenance controls prepared; the protected
G1 build tag is published; `egw-image` and two QEMU bring-up boots remain the
latest platform evidence; the current sealed unit figure remains 701 tests).

**Claim status: 0 of 15 accepted.** C01 has partial evidence (the existing build
is identified, but the clean G1 rebuild and the separate D006 second-operator
decision are still missing); C02 has the evidence of the two bring-up boots,
with the campaign's five strict boots still to be executed; the remaining **13
still have no evidence**. No gate has been accepted.

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
recorded. As at 2026-08-13 there is still no closed gate: every "Accepted at
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

The repository sits globally between M1 and M2, the Yocto/QEMU platform
deliverable being the single exception at M3; the plan requires M3–M5 for most
claims and gates.

## State per deliverable

### Block 2026-08-07 to 2026-08-09 (G0 — decision date 2026-08-10)

| Deliverable | Implemented | Verified | Accepted at gate | M |
|---|---|---|---|---|
| Git repository initialised and published | yes | static — private remote active since 2026-08-11 (`Ruisth/Tese_Mestrado`); on 2026-08-13 the ruleset was aligned with the written policy: pull requests and merge commits only on `main`/`dev`, force-push/deletion forbidden, review-thread resolution required and six technical/metadata checks mandatory in strict mode. The exact G1 build is reachable through protected tag `evidence/g1-yocto-build-5770c0a`; five local bundles verify, including a complete pre-synchronisation bundle. An off-machine copy is still pending | G0 — In progress | M2 |
| Plan v1.1, provenance register and technical CI | yes | static — the normative plan, archived byte-identical v1.0, D001–D008 log, source/provenance registers and CI workflows were merged to `dev` through PR #12. On 2026-08-13 its required GitHub checks passed for Python 3.11/3.14, contracts/evidence/links, shell safety, LaTeX and metadata; this verifies the change but does not itself accept G0 or G1 | G0–G1 — In progress | M2 |
| Normative contracts (`src/CONTRACTS.md` v1.1) + JSON schemas | yes | unit — `tests/test_schemas.py` (part of the current sealed suite of 701 tests); static — 7 valid JSON files; real integration not demonstrated | G2 — Pending | M2 |
| Scope, RQs and claim→evidence matrix (15 claims) | yes | static — **0 of 15 claims accepted**: C01 is partial (the build is evidenced; the clean G1 rebuild and the separate D006 second-operator decision are pending), C02 holds the bring-up evidence (the campaign's five strict QEMU boots are still to be executed) and the remaining **13 have no evidence**; no validation by the supervisors | G0 — Pending | M1 |
| Backlog and risk register | yes | no (management documents) | G0 — Pending | M1 |
| WSL2 Ubuntu 24.04 guide (ext4) | yes | **the installation was carried out**: WSL2 with Ubuntu 24.04.4 LTS is installed and operational, with the build directory on ext4, and it is the environment that produced the `egw-image` build archived in `docs/evidence/g1-yocto-qemu/` (Ubuntu 26.04 was rejected first because it ships Python 3.14, outside the tested envelope of Yocto Scarthgap). Not yet archived as a G0 environment record: the `wsl -l -v` and `df -h` capture — hence the maturity level below stays where it was | G0 — Pending | M1 |
| ARM64 VM (measurement platform) | no | no | G0 — **Blocked: market unavailability** (Oracle: home region fixed, no Ampere capacity; Hetzner: CAX sold out; Azure for Students: quota 0 on every dedicated ARM family). Deadline 2026-08-10 missed; rule §8.1: report the risk by 2026-08-12. Quota requested (DPLSv5/v6); AWS `c6g.xlarge` fallback ~7 EUR | M0 |
| G0 email to the supervisors + request for the extension rules | yes (draft) | no — not sent | G0 — Blocked (sending is a student action; deadline 2026-08-09) | M1 |
| Quarantine of results without evidence in the dissertation | yes | static — ch. 5 with 16 `\todo{pending data-v1}` and zero numbers; no Pi/SSI claims | G0 — Pending | M1 |

### Blocks G1–G7 — development brought forward without the ARM64 measurement VM

WSL2 now exists and is operational; the platform that is still missing is the
ARM64 measurement VM.

| Deliverable | Implemented | Verified | Accepted at gate | M |
|---|---|---|---|---|
| `kas` manifest + `meta-egw` layer + `egw-image` recipe | yes | **integration — image built and TWO QEMU boots recorded on 2026-08-11**: build of 5715 BitBake tasks, all successful, from the tree at commit `5770c0a`; rootfs 382 MiB, kernel 23 MiB, 639 packages including `docker-moby` 25.0.9, `containerd` 2.0.10, `runc` 1.1.14 and systemd. Both boots were driven by the automated driver `src/yocto/scripts/boot_check.py` at commit `32f6604` — they were **not** manual — and each passed 6 of 6 required assertions, recorded 3 of 3 supplementary observations and confirmed a clean power-down (systemd `running`, `multi-user.target` active, zero failed units, slirp networking, Docker 25.0.9, container imported and run). Observations assert nothing and are never counted as verification. Evidence sealed in `docs/evidence/g1-yocto-qemu/` with `SHA256SUMS` that verifies from a clean clone. 6 defects found by the real execution and fixed. Functional evidence only: nothing here supports a performance or security statement | **G1 — In progress: evidence produced, gate acceptance PENDING** (the formal decision is still to be recorded; the campaign's five boots are a later set) | M3 |
| Minimal ARM64 compose (Mosquitto TLS, Ditto 3.9.4, MongoDB, controller) | yes | static — `docker compose config` (syntactic validation, no persisted log); arm64 digests verified documentally on 2026-08-07; operational `.env`/certificates/passwords do not exist | G2 — Blocked (requires the ARM VM; gate 2026-08-23, trigger 2026-08-25) | M1 |
| MQTT→Ditto controller | yes | unit — tests with fakes (part of the current sealed suite of 701 tests); no real MQTT/Ditto, no real restart, no ARM64 | G2 — Pending | M2 |
| Unified simulator (3 wearables, 6 scenarios) | yes | unit — determinism verified; `dropout-reconnect` induces a real MQTT disconnection with buffering and ordered redelivery (audit §7.3 correction completed on 2026-08-08; covers C10 at unit level) | G2–G3 — Pending | M2 |
| WoT TD 1.1 Thing Descriptions | yes | unit — `tests/test_things.py` cross-checks TD↔schema; real integration not demonstrated | G2–G3 — Pending | M2 |
| Experimental harness + analysis | yes | unit — audit §9 gaps corrected on 2026-08-08 (blocks P1a–P1c: gating by validity, host provenance, acceptance with completeness, soak DoD, cadence caps, saturation with sufficiency of evidence, write-once sealed raw data, `campaign` batch runner); the 2026-08-13 integrity correction rejects resource samples from a different UTC window, enforces at least 90% coverage and the protocol gap cap per container, makes simulator run directories write-once, propagates QEMU pipeline failures and makes `systemd=running` plus zero failed units strict boot assertions. Local branch validation: `717 passed`; this is **not** a new evidence seal, so the canonical sealed figure remains 701. Live proof and the ARM64 runtime lock remain pending the VM | G1/G4 — In progress/Pending | M2 |
| `experiments/results/` evidence structure | yes | static — `raw/processed/figures` directories created; zero data (experimental evidence M0) | G5 — Pending | M1 |
| Dissertation (skeleton + substantive ch. 2) | yes | static — latexmk compiles: 57 pp., 0 unresolved references; ch. 2 ~4,300 words; premature claims removed from chs. 1/3/4/6 and from Table 2.1 (block P2); chs. 3/5/6 remain a skeleton | G6 — Pending | M1–M2 |
| Review sources (`thesis/research/study_selection.csv`) | yes | static — 25 sources recorded, with verified metadata (Crossref/W3C/OASIS/official pages). **Reading depth: 7 assessed in full text (S001, S004–S009) and 18 by title/abstract only** (`stage=title_abstract`, provisional inclusion for the supervisor draft; the full-text pass is still to be run). "Verified" refers to the source metadata, never to the full reading; the institutional queries remain pending (student action, risk R17) | G6 — Pending | M1 |
| Standalone PDF of ch. 2 for the supervisor | yes | static — `thesis/latex/ch2_supervisor_draft.pdf` (16 pp., no TODOs/placeholders, institutional review declared pending); page-by-page visual inspection | not a gate item — sending is a student action (no gate closes on this) | M2 |
| Unit test suite | yes | unit — **sealed evidence: `701 passed`** over clean HEAD `4e67717` in `docs/evidence/tests/2026-08-11-head-4e67717/`, with JUnit, stdout, environment, interpreter, `pip freeze`, `pip check`, pytest version, SHA-256 of the lock file and `SHA256SUMS`. Current sealed figure: `701`. Earlier sealings are kept for traceability and are **historical only** (`683`, `618`, `593`, `515`), each tied to the commit it tested and never the current figure. **Zero live/`integration` tests exist** — creating them is a prerequisite for G3 | G3 — Pending | M2 |
| Post-audit harness corrections (event fetch, 2 environments, collector on the VM, measured window, conditions C10–C14, queue growth, normalised CPU) | yes | unit — tests included in the current sealed suite of 701 (they were first sealed in the historical run of `593`); campaign plan with 95 runs; acceptance requires completeness (by identity against the plan when the plan is supplied to the analysis) and evidence — including evidence of real recovery in C12; real execution pending the VM | G3–G4 — Pending | M2 |

Note: "Implemented = yes" means only that the artefact exists and, where stated,
passed unit/static verification in this repository. Gates G1–G5 close only with
evidence of real execution (QEMU build/boot — produced for G1 on 2026-08-11 —,
ARM deployment, E2E trace, campaign data); what remains still depends on the
external actions below.

## Gate status as at 2026-08-13

Factual record of the situation. **Nothing here declares a gate closed or
failed**: the gate decision belongs to the student and the supervisors and is
recorded in Annex C of the plan and in [`LOG.md`](LOG.md).

- **G0 (decision date: 2026-08-10) — date reached, two of the three external
  actions still outstanding.** (i) G0 email to the supervisors — the draft
  exists in
  [`docs/g0/supervisor_email_g0.md`](docs/g0/supervisor_email_g0.md) and was
  rewritten on 2026-08-12 so that it actually carries the §8.1 escalation of the
  missing ARM64 measurement VM, which it had previously been credited with but
  did not contain; there is still **no record of sending** in the LOG, and
  drafting does not discharge §8.1 — sending does; (ii) WSL2 with Ubuntu 24.04.4 LTS on ext4 —
  **done**: the environment is operational and produced the G1 build archived in
  `docs/evidence/g1-yocto-qemu/`; what is still missing is the `wsl -l -v` and
  `df -h` capture as an environment record; (iii) ARM64 VM — the VM does not
  exist, so there is no `uname -a`/`lscpu`/`/etc/os-release` and no environment
  manifest. (i) and (iii) are student actions; no change in the repository
  substitutes for them.
- **The plan's own cut rules (§8.1), transcribed without interpretation:**
  no VM by **2026-08-10**, change provider; no VM by **2026-08-12**, report the
  risk to the supervisors. Applying either rule is a student action and is
  recorded in the LOG when it occurs. **State on 2026-08-12: both rules have
  fired and neither is discharged.** The first was applied in substance —
  providers were changed three times, Oracle to Hetzner to Azure, and all three
  failed — but the change of provider produced no VM, so the condition it exists
  to remove still holds. The second falls due today: the report to the
  supervisors is written and is not sent. The repository can carry the draft no
  further; only the student can close either rule.
- **G1 (2026-08-16, trigger 2026-08-20)** — the platform is no longer
  undemonstrated: WSL2 is operational, the `egw-image` image was built from the
  manifest with pinned revisions (5715 tasks, all successful) and **two QEMU
  bring-up boots** were recorded by the automated driver
  `src/yocto/scripts/boot_check.py`, each passing 6 of 6 required assertions,
  recording 3 of 3 supplementary observations and confirming a clean power-down.
  Evidence sealed in `docs/evidence/g1-yocto-qemu/`. **Acceptance of the gate
  remains pending**: G1 still requires a clean identified rebuild and five new
  strict boots. A second-operator reconstruction is the separate D006 decision;
  none of the existing evidence supports a performance or security statement.
- **G2 (2026-08-23, trigger 2026-08-25)** — unchanged: zero deployments on the
  ARM64 VM, which does not exist; `experiments/results/raw/` remains empty.
- **G3–G7** — unchanged; they still depend on evidence of real execution (and G3
  additionally requires live/`integration` tests, which do not exist).
- **The repository work of 2026-08-10 (blocks P5/P5.4) is code and documentation
  correction at M2**: it raises the quality of the instrumentation and of the
  documentary truth and **neither unblocks nor closes any gate**.

## External student actions (with deadlines)

| Action | Deadline | Expected evidence |
|---|---|---|
| Send the consolidated G0/alignment email to the supervisors with Chapter 2 and D001–D008 (drafts under `docs/g0/`) | 2026-08-13 — **immediate**; follow up 2026-08-18 and request a short meeting on 2026-08-20 if unanswered | email sent; copy/date in the LOG and decision-log `sent_at` fields |
| Request/confirm the administrative rules of the extension (included in the G0 email) | 2026-08-10 — **elapsed**; the draft now asks for a reply by 2026-08-21 | request and reply recorded in the LOG (plan §10) |
| Install Ubuntu 24.04 on WSL2 with the build directory on ext4 (guide in `docs/setup/wsl2_ubuntu_yocto.md`) | 2026-08-09 to 2026-08-10 | **done on 2026-08-11**: Ubuntu 24.04.4 LTS operational on ext4 and used for the `egw-image` build (`docs/evidence/g1-yocto-qemu/`); the `wsl -l -v` and `df -h` outputs are still to be archived |
| Request a university ARM64 host; if not confirmed within 48 hours, obtain/provision the approved public fallback (non-burstable, 4 vCPU, 8 GiB, >=80 GB, maximum total EUR 30) and validate `uname -m` = `aarch64` | request 2026-08-13; fallback trigger 48 h after recorded request | request/reply in LOG; then `uname -a`, `lscpu`, `/etc/os-release`, provider/region/tenancy and environment manifest — **not done: the VM does not exist** |

G0 cut rule (plan §8.1): no VM by 2026-08-10, change provider; no VM by
2026-08-12, report the risk to the supervisors. Both dates have now passed with
no VM; the report exists as a draft and is unsent.

## Platforms — three tiers (extension of ADR 0001, to be validated with the supervisors)

The unavailability of dedicated ARM64 forced a distinction between an
integration platform and a measurement platform. Hard rule: **no number from the
B series enters the dissertation.**

| Role | Platform | State | Numbers in the thesis |
|---|---|---|---|
| Functional (OS/boot) | QEMU `qemuarm64` on WSL2 | image built (5715 tasks) and two bring-up boots passed on 2026-08-11, each with 6 of 6 required assertions | Never (plan §5.1) — functional only; QEMU results never support a performance or security statement |
| ARM64 integration | Azure `B4pls_v2` (burstable SKU identified) | no instance provisioned; eligibility/capacity still require confirmation | **Never** — CPU credits would corrupt the load sweep and the saturation criterion |
| Measurement (RQ3) | `D4pls_v5` (quota requested) or AWS `c6g.xlarge` | **does not exist** | **Exclusively from here** |

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
| G0 email + extension rules | Student | 0.5–1 (est.) | | | 2026-08-09 to 2026-08-10 | email + date in the LOG | | |
| WSL2 Ubuntu 24.04 on ext4 | Student | 2–4 (est.) | | | 2026-08-09 to 2026-08-10 | version and filesystem outputs — environment operational since 2026-08-11; capture still to be archived | | |
| ARM64 VM `aarch64` | Student | 1–2 (est.) | | | 2026-08-10 | initial manifest archived | | account/payment |
| Independent Git backup | Both | 0.5–1 (est.) | | | 2026-08-09 | verified bundle/clone outside Nextcloud — repository and bundles outside the synchronised folder since 2026-08-10; **private remote `Ruisth/Tese_Mestrado` active since 2026-08-11** (the stronger option), with a ruleset requiring pull requests on `main` and `dev` | | |
| Theoretical framing sprint | Both | 18–24 (est.) | | | 2026-08-10 to 2026-08-11 | draft of 4,000–5,000 words + research logs filled in | | |
| Yocto build + 2 QEMU boots | Student | | | | 2026-08-16 (trigger 2026-08-20) | BitBake log, `boot1/2.log`, `SHA256SUMS` — delivered on 2026-08-11 in `docs/evidence/g1-yocto-qemu/`; gate acceptance still pending | | cleared (WSL2 ext4 operational) |
| E2E vertical slice on the VM | Both | | | | 2026-08-23 (trigger 2026-08-25) | trace `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` | | ARM VM |
| Harness corrections (R18–R22) | Agent | | | | before 2026-09-06 | valid pilot with no ad hoc intervention | | |
| Full pilot + tag `exp-v1` | Both | | | | 2026-09-06 | pilot data in `raw/` with manifests | | corrected harness |
| Official campaign + `data-v1` | Both | | | | 2026-09-13 18:00 | complete `raw/<run_id>/` + `SHA256SUMS` | | `exp-v1` |
| Full draft to the supervisors | Both | | | | 2026-09-18 | sending email recorded in the LOG | | `data-v1` |
