# History — index of project records

These files record how the project reached its current state: plans, milestone decisions, proposals,
supervision records, reviews, past runbooks, work logs and past-session tooling. They are records;
their recorded content is kept, and a few carry a dated status note at the top.
A dated statement inside one of them describes the project on that date, not today; the current state
is in the [front page](../../README.md) and the guides indexed in [docs/README.md](../README.md).

**Codes used in the records.** The records name the plan's milestones G0 to G7 ("gates"). Project
start-up (G0), the base image (G1), wearable-to-twin integration (G2) and the functional freeze after
the test battery (G3) were accepted; the later stages, from the experimental freeze to the release
candidate (G4 to G7), were not decided. T1 to T9 are the test families of the test battery, and S1 to
S4 its sessions. Below, each record has a descriptive name, with its code in parentheses where the
record itself uses one. Formal milestone outcomes are recorded only in the
[gate decision log](../governance/gate_decision_log.md).

## Previous front page

- [README-before-2026-10-26.md](README-before-2026-10-26.md) — the front page until 2026-10-26; its
  fenced block is byte-identical to `README.md` at commit `eaeb35f`: the milestone, plan, authorisation
  and correction narratives of that time.

## Work log and progress record

Both were at the repository root until 27 October 2026.

- [LOG.md](LOG.md) — work diary, entries #C001–#C065 (#C001–#C010 in Portuguese); among them #C055 the
  test battery accepted as the functional freeze (G3), #C059 the comparison tooling, #C060 the
  Yocto–Debian 13 comparison (series a02), #C061 the `yoctowrynose` scenario, #C062–#C064 the
  reorganisation for readers and the preparation of another PC for the demonstration, and #C065 the
  organisation of the repository for the assessment version.
- [PROGRESS.md](PROGRESS.md) — deliverable state record; each block carries its own date; its top block
  of 2026-09-21 and its planned dates are that version's planning targets.

## Governance and supervision records (`docs/governance/`)

This folder stays at its original path. The sealed evidence folders, which are never edited, link to
its files (among them the gate decision log, the test battery results and the plan), and a unit test
reads the plan. Its files:

**Plans**

- [Integrated development plan v2.1](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) — the plan of
  2026-09-21 (QEMU-only execution baseline adopted on 2026-09-18); its schedule dates are the targets of
  that version.
- [governance/archive/](../governance/archive/) — plans v1.0 (Portuguese), v1.2 and v2.0, preserved
  unmodified. Their links point to the workspace of that time, so the link check skips this folder.

**Milestone decisions**

- [Gate decision log](../governance/gate_decision_log.md) — the formal record of the milestone outcomes:
  G0 to G3 accepted, G4 to G7 not decided; superseded row states kept verbatim.
- [Start-up decision, 2026-09-19](../governance/decisions/2026-09-19-g0-closure.md) (G0) — project
  initiation and baseline alignment.
- [Wearable-to-twin integration decision, 2026-09-21](../governance/decisions/2026-09-21-g2-closure.md)
  (G2) — one bounded smartwatch flow and twin persistence, bounded functional scope.
- [Test battery decision, 2026-10-07](../governance/decisions/2026-10-07-g3-closure.md) (G3) — the
  functional freeze on the emulated candidate.

**Test battery records**

- [Test battery results](../governance/g3-battery-2026-10-results.md) — run by run, sessions S1–S4, with
  the standing rows as of 2026-10-07 and the historical attempts.
- [Readiness map, 2026-09-29](../governance/g3-readiness-map-2026-09-29.md) — the nine test families
  before the battery.
- [Decisions on two tests, 2026-10-05](../governance/g3-t5-t6-decisions-2026-10-05.md) — the reading
  of the disconnection count in the recovery after disconnection test (T5), and the amended criterion
  of the controller restart test (T6).

**Supervision records**

- [Supervisor decision log](../governance/supervisor_decision_log.csv) — requests D001–D014 and their
  recorded status.
- [Supervisor alignment memo](../governance/supervisor_alignment_memo.md) — August text, not sent.

**Proposals**

- [governance/proposals/](../governance/proposals/README.md) — proposals and the texts of adopted
  proposals: wearable-to-twin integration acceptance, the closing of the test battery, pending
  decisions before it, the sampling of the controller restart test, the acceptance-protocol update of
  2026-09-19 (not adopted), and the plan, scope and memo texts of v2.0.

**Conventions and control records**

- [Language policy](../governance/language-policy.md) — British English, ISO 8601 dates and the
  authorised wearable-data terminology; [CONTRIBUTING.md](../../CONTRIBUTING.md) still applies it.
- [External source register](../governance/external_source_register.md) — checksummed identities of
  sources held outside the repository (2026-08-13).
- [Provenance and history rewrite](../governance/provenance-history-rewrite.md) — the evidence tag,
  verified bundles and exact-tree mappings across the history rewrite of August 2026.

## Claims and measurement plans

- [Claim–evidence matrix](claim_evidence_matrix.md) ([CSV](claim_evidence_matrix.csv)) — claims
  C01–C15 of the planned campaign; the Yocto–Debian 13 comparison lies outside it.
- [Comparative protocol](../../tools/compare/PROTOCOL.md) — the proposed Yocto–Debian 13 protocol, not
  executed as written; what ran is series a02 ([docs/results.md](../results.md)).

## Architecture decisions

- [ADR index](../adr/README.md) — ADRs 0001–0011 (no 0009) with their recorded statuses. Its note that
  the qualifying battery of ADR 0011 is pending predates the test battery decision (2026-10-07).

## Reviews

- [Yocto image audit, 2026-09-17](reviews/2026-09-17-egw-image-audit.md) — the integrated-gateway
  change set; section 13 records the first build and boot of 2026-09-18.
- [Test procedure corrections, 2026-09-18](reviews/2026-09-18-test-procedure-corrections.md) — the
  integration test procedures as corrected that day.
- [ADR 0011 package D](reviews/2026-09-23-adr-0011-package-d/README.md) — review record of ADR 0011
  (controller restart recovery), 2026-09-20 to 2026-09-24.
- [reviews/historical/](reviews/historical/) — synthesis of the 2026-08-08 reviews and the lineage of
  the supervisor memo.

## Start-up records (`g0/`)

- [Scope and research questions](g0/scope_and_rqs.md) — RQ1–RQ3, version 2.0 (2026-09-18); the
  dissertation holds the current wording.
- [Backlog](g0/backlog.md) — the planned work, by milestone.
- [Risk register](g0/risks.md) — risks R1–R8 and those added later.
- [Supervisor email draft](g0/supervisor_email_g0.md) — in Portuguese; not sent.
- [Two-layer thesis proposal](g0/two_layer_thesis_proposal.md) — not adopted.
- [Supervisor decision matrix](g0/supervisor_decision_matrix.csv) — questions for the supervisors, with
  recommended positions.
- [Seven-questions matrix](g0/supervisor_seven_questions_matrix.md) — response matrix for the seven
  supervisor questions.

## Past runbooks and setup guides

- [Integrated gateway runbook](../setup/qemu_integrated_gateway.md) — the manual procedure of
  2026-09-18/19 (build, boot, six containers, tests 1–9). It stays in `docs/setup/` and is still used:
  `tools/compare/provision_stack.sh` automates its sections 5.1–5.6, and its section 6.1 is the source of
  the helper file the measurement uses.
- [Native ARM64 VM checklist](setup/vm_arm64_hetzner.md) — deferred on 2026-09-18; never used for any
  result.
- [Git backup and private remote](setup/git_backup_remote.md) — the Git backup and private remote of
  the student's workspace.
- The setup guides still in use (WSL2 and Yocto, the integrated gateway runbook, local test outputs) are
  listed in [docs/README.md](../README.md).

## Academic notes

- [C2DTA P0 traceability](../academic/c2dta_p0_traceability.md) — paper function to P0 matrix, v1.2 of
  2026-09-18; its evidence statements predate the wearable-to-twin integration and the test battery.
- [Requirements and platform selection](../academic/gateway_requirements_and_platform_selection.md) —
  REQ-01 to REQ-18 and the Pi 5 / i.MX95 screening, v1.0 of 2026-09-21; documentary.

## Experiments and past-session tooling

- [experiments/g4-pilot/](../../experiments/g4-pilot/README.md) — input plan of the pilot of longer,
  repeated runs (G4); that stage is not decided.
- [experiments/README.md](../../experiments/README.md) — harness and campaign manual for the 95-run
  protocol, which was never executed.
- [tools/session/](../../tools/session/README.md) — session drivers of the earlier guest sessions:
  wearable-to-twin integration, the test battery and the pilot. Kept in place: the comparison
  measurement (`tools/compare/measure_run.sh`) calls two of its files, `proof_hook_drained.sh` and
  `nominal_account.py`, and the reproduction guide runs a third, `regen_helpers.py`, to write the helper
  file the measurement reads.
- [tools/probe/](../../tools/probe/README.md) — the broker-hold diagnostic of ADR 0011 (condition C3).
- Sealed evidence folders are listed in [docs/README.md](../README.md) and, result by result, in
  [docs/results.md](../results.md).

## Dissertation, article, assistant prompts and diagrams

- [thesis/](../../thesis/README.md) — historical: the LaTeX conversion of 2026-09-17 and the
  research-protocol records; the current manuscript is kept outside the repository.
- [paper/](../../paper/) — the IEEE article, deferred; its section files are placeholders.
- [Paper assembly prompt](paper/README-GPT.md) — marked not to be used yet: the article is deferred.
- `ai/` — prompt kits for a coding assistant ([coding-agent.md](ai/coding-agent.md)) and a writing
  assistant ([writing-agent.md](ai/writing-agent.md)), adapted from the C2DTA Student Repository
  Template; they cite the plan of that time as their first authority.
- [Two-layer deployment diagram](diagrams/two_layer_experimental_deployment.puml)
  ([SVG](diagrams/two_layer_experimental_deployment.svg)) — the experimental deployment proposal
  superseded on 2026-09-18.

## Earlier paths

Text inside the records may still name the earlier paths. Links were updated when the files moved.

| Earlier path | Path now |
|---|---|
| `LOG.md`, `PROGRESS.md` (repository root) | `docs/history/LOG.md`, `docs/history/PROGRESS.md` |
| `ai/` | `docs/history/ai/` |
| `docs/reviews/` | `docs/history/reviews/` |
| `docs/g0/` | `docs/history/g0/` |
| `docs/claim_evidence_matrix.md`, `.csv` | `docs/history/claim_evidence_matrix.md`, `.csv` |
| `docs/setup/vm_arm64_hetzner.md`, `docs/setup/git_backup_remote.md` | `docs/history/setup/` |
| `paper/README-GPT.md` | `docs/history/paper/README-GPT.md` |
| `diagrams/two_layer_experimental_deployment.puml`, `.svg` | `docs/history/diagrams/` |
