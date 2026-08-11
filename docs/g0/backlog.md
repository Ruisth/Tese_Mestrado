# Actionable backlog by gate (G0→G7)

> **This file contains actions only**: what is left to do, the expected evidence,
> the dependencies and the cutting rules of each gate (plan §8/§8.1). **The state
> of every deliverable lives exclusively in [`../../PROGRESS.md`](../../PROGRESS.md)**
> (single source of state — external audit of 2026-08-08, §5.1); this file does
> not use the plan's state taxonomy. Items whose artefact already exists in the
> repository are marked "implemented — verification/acceptance pending (see
> PROGRESS)"; that means only that the code/document exists, never that the gate
> is closed. Items already executed are marked "done" with the path of their
> sealed evidence — that too says nothing about gate acceptance.
>
> Recurring external dependencies: **requires WSL2 ext4** = Ubuntu 24.04 on WSL2
> with the build on a Linux filesystem (guide: [`../setup/wsl2_ubuntu_yocto.md`](../setup/wsl2_ubuntu_yocto.md));
> **requires ARM VM** = a native ARM64 VM on a dedicated family (`Dplsv5`, `c6g`,
> `m6g`); the checklist ([`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md))
> remains the setup reference, but the Hetzner CAX line it describes is sold out
> — see R28 (real-execution round) in [`risks.md`](risks.md).

Updated: 2026-08-11 (translated into British English; the WSL2 installation, the
`egw-image` build and the two QEMU bring-up boots are recorded as done with
their evidence path, so the backlog stops asking for work that has been
executed; this file still carries no figures and no state — both live in
PROGRESS, with the corresponding sealed evidence).

---

## G0 — Scope and environment (2026-08-10)

Cutting rule (§8.1): VM created and `aarch64` access validated on 2026-08-10. With
no VM that day, change provider; with no VM on 2026-08-12, report the risk to the
supervisors.

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Close the scope, RQs and premises in a document | implemented — verification/acceptance pending (see PROGRESS) | [`scope_and_rqs.md`](scope_and_rqs.md) validated by the supervisors | Supervisors' reply |
| Send the scope email to the supervisors and ask for the administrative rules of the extension (deadline 2026-08-09, **elapsed**; the draft now asks for the rules by 2026-08-21) | draft implemented and, on 2026-08-12, extended to carry the plan §8.1 escalation of the missing ARM64 VM — **sending still to be executed** (see PROGRESS) | Email sent (copy and date in the LOG); draft in [`supervisor_email_g0.md`](supervisor_email_g0.md) | Student action |
| Scope meeting with the supervisors (proposed: 2026-08-10) | — | Minutes/record of the decision in the LOG | Supervisors' reply |
| Install Ubuntu 24.04 LTS on WSL2 with the build directory on ext4 (deadline 2026-08-09/2026-08-10) | **done** — WSL2 with Ubuntu 24.04.4 LTS operational on ext4; it is the host that built the image. Install by name (`-d Ubuntu-24.04`): the plain `-d Ubuntu` now yields Ubuntu 26.04, outside the tested envelope (R30) | `wsl -l -v`; `df -h` of the build directory; build logs in `docs/evidence/g1-yocto-qemu/` | Student action; guide in `docs/setup/` |
| Create the ARM64 VM (Hetzner CAX21 or equivalent) and validate `uname -m` = `aarch64` (deadline 2026-08-10) | **blocked — dedicated ARM64 market unavailability** (R28, materialised): Oracle, Hetzner and Azure for Students all failed; quota requested and AWS `c6g.xlarge` kept as fallback. Rule §8.1 applies | Output of `uname -a`, `lscpu`, `/etc/os-release` recorded in the environment manifest | Student's account/payment; checklist in `docs/setup/` |
| Seed the claim→evidence matrix | implemented — verification/acceptance pending (see PROGRESS) | [`../claim_evidence_matrix.csv`](../claim_evidence_matrix.csv) with every claim carrying its real evidence state | — |
| Backlog and risk register created | implemented — verification/acceptance pending (see PROGRESS) | This file + [`risks.md`](risks.md) maintained at every gate | — |
| Quarantine/remove results without evidence from the active dissertation | implemented — verification/acceptance pending (see PROGRESS) | Ch. 5 with no unsupported numbers; note in the LOG | — |

## G1 — Functional Yocto/QEMU (2026-08-16)

Cutting rule (§8.1): the image boots twice and runs a container. If it fails, reduce
the image to a minimal system with a runtime and move the deployment to an external
script. With no functional image on 2026-08-20, discuss extension/reformulation.

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Freeze the ARM VM (specs recorded, stable access) | blocked by R28 — the measurement VM does not exist | Environment manifest (provider, region, CPU, kernel, OS, shared-vCPU limitation) | Requires ARM VM (G0) |
| `kas` manifest for `qemuarm64` with exact tags/commits (Scarthgap 5.0.19) | implemented and exercised by the real build — verification/acceptance pending (see PROGRESS) | `kas dump` reproducible from a clean checkout | — |
| Build `egw-image` on WSL2 ext4 | **done (2026-08-11)** — 5715 BitBake tasks, all successful | Sealed in `docs/evidence/g1-yocto-qemu/`: `kas-checkout.log`, `kas-build.log`, `image-packages.manifest` and `SHA256SUMS` | Requires WSL2 ext4; >=120 GB free |
| Two QEMU boots with systemd, networking and OCI runtime | **done (2026-08-11)** — two bring-up boots driven by the automated driver `src/yocto/scripts/boot_check.py`, each with 6 of 6 required assertions passed, 3 of 3 supplementary observations recorded and a clean power-down confirmed; the observations assert nothing and are not counted as verification. Gate acceptance remains a separate decision (see PROGRESS) | Sealed in `docs/evidence/g1-yocto-qemu/`: `boot1.log`, `boot1.result.json`, `boot2.log`, `boot2.result.json`, `SHA256SUMS` | Build completed |
| Check the OCI architectures of the stack images (`linux/arm64` by digest) | `images.lock.env` lock implemented — the `manifest inspect` output on the VM is still missing (see PROGRESS) | Output of `docker manifest inspect` per image, archived | Requires ARM VM |
| Dissertation introduction/RQs under revision; review protocol executed and bibliography audited | protocol written and preliminary records filled in — the institutional queries (IEEE Xplore, ACM DL, Scopus/WoS) and the move to full text of the sources still at title/abstract are outstanding (see PROGRESS and risk R17) | Chapter 1 draft; institutional queries and selection decisions recorded in `thesis/research/`; `references.bib` audited | Institutional access (student action) |

## G2 — Vertical slice (2026-08-23)

Cutting rule (§8.1): a payload travels MQTT→controller→Ditto and is retrieved through
the API. If it fails, cut the auxiliary APIs and the whole of identity. With no E2E on
2026-08-25, declare a serious risk for September.

**Single blocking dependency: the ARM64 VM does not exist (R28, materialised).**
Every action below waits on it.

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Minimal ARM64 compose (Mosquitto TLS 8883, Ditto 3.9.4 gateway/policies/things, MongoDB, controller) | implemented — verification/acceptance pending (see PROGRESS); `.env`, password file and operational certificates still to be created | Clean `docker compose up` on the VM; real health/readiness | Requires ARM VM |
| MQTT→Ditto controller (schema validation, idempotency, retry, logging, endpoints) | implemented — verification/acceptance pending (see PROGRESS) | TLS connection to a real Mosquitto; twin updated in a real Ditto | Requires ARM VM |
| Vertical slice smartwatch→MQTT→controller→Ditto | — | Reproducible trace: `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` with the correct state | Compose on the ARM VM; controller |
| Simulator CLI with the `smoke` scenario | implemented — verification/acceptance pending (see PROGRESS) | `python -m egw_simulator run --scenario smoke ...` against a real broker, with a run manifest | Requires ARM VM |
| Initial tests (unit + local integration) | unit tests implemented (Windows) — still to be verified on Linux, and the real integration tests still to be created (see PROGRESS and risk R21) | `pytest` green on Linux with a persisted report; >=1 live integration test | Python 3.11+ in a Linux environment |
| Chapters 1–2; methodology started; logical diagram | supervisor draft of ch. 2 ready; the remaining chapters still to be completed (see PROGRESS) | Files in `thesis/` and `diagrams/` with substantial text | — |

## G3 — P0 feature freeze and ACA-Py decision (2026-08-30)

Cutting rule (§8.1): ACA-Py only proceeds if the QEMU build/boot, a clean ARM
deployment, three devices, the scenarios, tests, metrics and soak are complete and free
of P0 defects. Cut after 12 h or on 2026-09-03, whichever comes first.

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Three concurrent wearables in the simulator | implemented — still to be verified in real execution (see PROGRESS) | Run with `--devices smartwatch,smart_ring,smart_clothing`; three twins updated | Requires ARM VM |
| All scenarios (`smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload`, `soak`) | implemented in the simulator — live demonstration still to be executed (see PROGRESS) | Runs recorded with a manifest per scenario; real disconnection demonstrated in a live run | Requires ARM VM |
| Reconnect/backpressure in the controller and the simulator | — | `dropout-reconnect` integration test green; consistent counters | Controller + broker |
| Metrics and experimental harness | harness corrections applied at M2 (blocks P1a–P1c, P5 and P5.4) — live pilot still to be executed (see PROGRESS) | Resources collected on the right VM; `events.jsonl` collected automatically; warm-up excluded; conditions C10–C14 in the campaign plan; the analysis exercised through the real path of the delivered CLI | — |
| Complete test suite (unit, integration, E2E) | unit tests implemented — live/`integration` tests still to be created (see PROGRESS and risk R21) | `pytest` green including the `integration` mark on the VM, with a persisted report | Requires ARM VM |
| Pilot soak | — | A long pilot run without a crash; log and resources | Requires ARM VM |
| Chapter 3 and a first version of chapter 4; ADRs and diagrams | ADRs and diagrams implemented — verification/acceptance pending (see PROGRESS); chapters partial | `thesis/`; [`../adr/`](../adr/README.md) synchronised with CONTRACTS v1.1 | — |
| ACA-Py decision recorded at the gate | treat outside the base forecast (audit §16): it only proceeds with margin proven by real hours | Entry in the LOG + Annex C of the plan (authorised/cut) | State of the P0 items above |

## G4 — Frozen protocol, tag `exp-v1` (2026-09-06)

Cutting rule (§8.1): every pilot produces valid data and the analysis script generates
tables/figures. After this gate, metrics, conditions and exclusion criteria are not
changed.

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Reproduction from a clean checkout | the outstanding part of C01: the build is evidenced, the rebuild from an independent clean checkout belongs to this gate | Record of a clean clone building and running the E2E smoke | WSL2 ext4 + ARM VM |
| P0/P1 corrections after the feature freeze | — | Identified commits; no new features | — |
| Minimal ACA-Py (only if authorised at G3; up to 2026-09-03) | outside the base forecast (audit §16) | Two local agents, `did:peer`, OOB invitation, DIDComm message; verified ARM64 digest | G3 authorisation; 12 h timebox |
| Complete campaign pilot | — | Pilot data in `experiments/results/raw/` with manifests, no ad hoc intervention | Requires ARM VM; corrected harness (R18–R22) |
| The analysis script generates tables/figures from `raw/` | the analysis route for external runs is implemented (`--external-timings`); producing the timings on the VM is still to be executed (see PROGRESS) | `processed/` and `figures/` regenerated by a single script invoked as it is delivered (no parameters reachable only through the API), including external runs or a formally documented exception | Pilot data |
| Chapters 1–4 complete; full skeleton of the evaluation | — | `thesis/` compiling, with no invented numbers | — |
| Tag `exp-v1` | — | Tag in Git with the frozen protocol | The items above |

## G5 — Data freeze `data-v1` (2026-09-13, 18:00)

Cutting rule (§8.1): every metric essential to the RQs has complete data. An optional
condition may be removed by declaring the limitation; never fill the gap with a
conclusion that has no evidence.

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Official ARM campaign (§7.1: 5 functional QEMU boots, 10 cold starts, 10 twin creations, 10 nominal runs, load-sweep 10/50/100/250 msg/s ×10, 24 h soak) | the 5 `qemu_boots` runs are a later set under the frozen protocol, distinct from and not interchangeable with the two G1 bring-up boots | `experiments/results/raw/<run_id>/` complete, with `SHA256SUMS` | Requires ARM VM; tag `exp-v1` |
| Only corrections that invalidate experiments; repeat the affected conditions | — | LOG with a justification for each repetition | — |
| Validate the data and generate the figures | — | `processed/` + `figures/` regenerated; provenance validation (`run_id`/manifest) | Campaign |
| Write up the setup and limitations (chapter 5, context sections) | — | Text in `thesis/` | — |
| Tag `data-v1`; `raw/` immutable | — | Tag in Git; checksums verified | Complete campaign |

## G6 — Full draft (2026-09-18)

Cutting rule (§8.1): every chapter, figure and answer to the RQs exists. A
restructuring estimated above 20 h activates the contingency (§10).

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Chapters 5–6, Abstract and Resumo with real evidence | — | `thesis/` complete; every number traced in the claim→evidence matrix | `data-v1` |
| RQs answered with real evidence only | — | Claim→evidence matrix with no pending states in the claims used in the text | `data-v1` |
| Full draft sent to the supervisors on 2026-09-18 | — | Sending email recorded in the LOG | Clean compilation |
| No features; reproduction and analysis only | — | Git history with no feature commits after G5 | — |

## G7 — Release and approval (2026-09-25; `rc1` on 2026-09-27)

Cutting rule (§8.1): compliant PDF, archived artefact and feedback handled. A lack of
reply from the supervisors does not stop the work; the last documented decisions are
followed and the contact attempts are recorded.

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| Final smoke and packaging of the reproducibility package | — | Versioned archive with SHA-256 and its location recorded | `data-v1` |
| Handling of the feedback (requested deadline: 2026-09-23) | — | List of changes + recorded replies | Supervisors' feedback |
| Language, references, front matter, consistency and visual QA of the PDF | — | Editorial checklist completed; page-by-page inspection | Full draft |
| Release candidate `rc1` on 2026-09-27 | — | Tag `rc1` + PDF | The items above |
| Submission 2026-09-29 17:00; receipt and tag `v1.0-thesis` | — | Portal receipt; tag in Git | `rc1` |

## Post-gate — 2026-09-28/2026-09-30

| Action | Note | Expected evidence | Dependencies |
|---|---|---|---|
| 2026-09-28/2026-09-29: blocking corrections only; final PDF, metadata and portal | — | Internal submission on 2026-09-29 17:00 | `rc1` |
| 2026-09-30: strictly administrative reserve | — | Use only if the internal submission fails | — |
