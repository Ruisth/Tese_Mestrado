# History — index of project records

These files record how the project reached its current state: plans, gate decisions, proposals,
reviews, past runbooks, work logs and past-session tooling. They are records; their recorded content
is kept, and a few carry a dated status note at the top.
A dated statement inside one of them describes the project on that date, not today; the current state
is in the [front page](../../README.md) and the guides indexed in [docs/README.md](../README.md).
Formal gate outcomes are recorded only in the
[gate decision log](../governance/gate_decision_log.md).

## Previous front page

- [README-before-2026-10-26.md](README-before-2026-10-26.md) — the front page until 2026-10-26; its
  fenced block is byte-identical to `README.md` at commit `eaeb35f`: the gate, plan, authorisation and
  correction narratives.

## Work log and state record

- [LOG.md](LOG.md) — work diary, entries #C001–#C061 (#C001–#C010 in Portuguese); among them
  #C055 G3 accepted, #C059 comparison tooling, #C060 series a02, #C061 the `yoctowrynose` scenario.
- [PROGRESS.md](PROGRESS.md) — deliverable state record; each block carries its own date; its
  top block of 2026-09-21 and its planned dates are that version's planning targets.

## Plans

- [Integrated development plan v2.1](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) — the plan of
  2026-09-21 (QEMU-only execution baseline adopted on 2026-09-18); its schedule dates are the targets of
  that version.
- [governance/archive/](../governance/archive/) — plans v1.0 (Portuguese), v1.2 and v2.0, preserved
  unmodified.

## Gate decisions and the G3 battery

- [Gate decision log](../governance/gate_decision_log.md) — G0, G1, G2 and G3 accepted; G4 to G7 not
  decided; superseded row states kept verbatim.
- [G0 decision, 2026-09-19](../governance/decisions/2026-09-19-g0-closure.md) — project initiation and
  baseline alignment.
- [G2 decision, 2026-09-21](../governance/decisions/2026-09-21-g2-closure.md) — one bounded smartwatch
  flow and twin persistence, bounded functional scope.
- [G3 decision, 2026-10-07](../governance/decisions/2026-10-07-g3-closure.md) — the functional P0 freeze
  on the emulated candidate.
- [G3 battery results](../governance/g3-battery-2026-10-results.md) — row by row, sessions S1–S4, with
  the standing rows as of 2026-10-07 and the historical attempts.
- [G3 readiness map, 2026-09-29](../governance/g3-readiness-map-2026-09-29.md) — the nine families before
  the battery.
- [T5 and T6 decisions, 2026-10-05](../governance/g3-t5-t6-decisions-2026-10-05.md) — T5's
  interpretation and T6's amended criterion.
- [Supervisor decision log](../governance/supervisor_decision_log.csv) — requests D001–D014 and their
  recorded status.
- [Claim–evidence matrix](claim_evidence_matrix.md) — claims C01–C15 of the planned campaign; the a02
  comparison lies outside it.

## Proposals

- [governance/proposals/](../governance/proposals/README.md) — proposals and the texts of adopted
  proposals: G2 acceptance, G3 closing, pending G3 decisions, T6 sampling, the acceptance-protocol update
  of 2026-09-19 (not adopted), and the plan, scope and memo texts of v2.0.
- [Supervisor alignment memo](../governance/supervisor_alignment_memo.md) — August text, not sent.
- [Comparative protocol](../../tools/compare/PROTOCOL.md) — the proposed Yocto–Debian 13 protocol, not
  executed as written; what ran is series a02 ([docs/results.md](../results.md)).

## Architecture decisions

- [ADR index](../adr/README.md) — ADRs 0001–0011 (no 0009) with their recorded statuses. Its note that
  the qualifying battery of ADR 0011 is pending predates G3 (2026-10-07).

## Reviews

- [Yocto image audit, 2026-09-17](reviews/2026-09-17-egw-image-audit.md) — the integrated-gateway
  change set; section 13 records the first build and boot of 2026-09-18.
- [Test procedure corrections, 2026-09-18](reviews/2026-09-18-test-procedure-corrections.md) — the
  integration test procedures as corrected that day.
- [ADR 0011 package D](reviews/2026-09-23-adr-0011-package-d/README.md) — review record of ADR 0011,
  2026-09-20 to 2026-09-24.
- [reviews/historical/](reviews/historical/) — synthesis of the 2026-08-08 reviews and the lineage of
  the supervisor memo.

## Past runbooks

- [Integrated gateway runbook](../setup/qemu_integrated_gateway.md) — the manual procedure of
  2026-09-18/19 (build, boot, six containers, tests 1–9). `tools/compare/provision_stack.sh` automates
  its sections 5.1–5.6, and its section 6.1 is still the source of the helper file the measurement uses.
- [Native ARM64 VM checklist](setup/vm_arm64_hetzner.md) — deferred on 2026-09-18; never used for any
  result.
- The other setup guides (WSL2 and Yocto, local test outputs, Git backup) are current and listed in
  [docs/README.md](../README.md).

## G0 package and academic records

- [docs/g0/](g0/scope_and_rqs.md) — scope and RQs v2.0 (2026-09-18), backlog, risk register, the
  supervisor email draft (not sent), the two-layer thesis proposal (not adopted), the decision matrix and
  the seven-questions matrix.
- [C2DTA P0 traceability](../academic/c2dta_p0_traceability.md) — paper function to P0 matrix, v1.2 of
  2026-09-18; its evidence statements predate G2 and G3.
- [Requirements and platform selection](../academic/gateway_requirements_and_platform_selection.md) —
  REQ-01 to REQ-18 and the Pi 5 / i.MX95 screening, v1.0 of 2026-09-21; documentary.

## Experiments and past-session tooling

- [experiments/g4-pilot/](../../experiments/g4-pilot/README.md) — input plan of the G4 pilot; G4 is not
  decided.
- [experiments/README.md](../../experiments/README.md) — harness and campaign manual for the 95-run
  protocol, which was never executed.
- [tools/session/](../../tools/session/README.md) — session drivers of the G2, G3 and G4 guest sessions.
  Kept in place: the comparison measurement calls two of its files.
- [tools/probe/](../../tools/probe/README.md) — the broker-hold diagnostic of ADR 0011 (condition C3).
- Sealed evidence capsules are listed in [docs/README.md](../README.md) and, result by result, in
  [docs/results.md](../results.md).

## Dissertation, article and diagrams

- [thesis/](../../thesis/README.md) — the historical LaTeX conversion of 2026-09-17 and the
  research-protocol records; the current manuscript is kept outside the repository.
- [paper/](../../paper/) — IEEE article, deferred.
- [Two-layer deployment diagram](diagrams/two_layer_experimental_deployment.puml) — the
  experimental deployment proposal superseded on 2026-09-18.
