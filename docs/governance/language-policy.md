# Repository language policy

**British English (en-GB) is the sole working language of this project.**

Adopted 2026-08-11. Retroactive conversion of active content is approved, but
only through new commits: published history is never rewritten to translate it.

## Scope

All newly created or modified content is written in English, including:

- source-code comments and docstrings;
- tests and assertion messages;
- command-line help and runtime messages;
- documentation and governance records;
- diagrams, tables and captions;
- branch names;
- commit subjects and bodies;
- pull-request titles and descriptions;
- reviews, comments, issues and release notes;
- experimental manifests and evidence descriptions;
- dissertation content.

Dates use ISO 8601, `YYYY-MM-DD`.

Spelling follows en-GB: *behaviour*, *initialise*, *analyse*, *artefact*,
*licence* (noun) / *license* (verb), *centre*, *organisation*, *modelling*,
*labelled*. American spellings that arrive inside quoted third-party text stay
as quoted.

## Exceptions

1. **The Portuguese Resumo**, and any other front matter the university makes
   mandatory in Portuguese.
2. **External administrative communication** — supervisor emails, faculty
   forms. Drafts of those may stay in Portuguese.
3. **Canonical names** from standards, protocols, APIs and third-party
   libraries, which are never translated.
4. **Historical artefacts**, where rewriting would compromise evidence or
   hashes.

## Never translated, for integrity reasons

Changing any of these breaks a checksum, a reference or a running system:

| Category | Examples |
|---|---|
| Published history | commit messages, closed pull requests, tags |
| Sealed evidence | `docs/evidence/**`, `experiments/results/raw/**`, `SHA256SUMS`, bundles, captured logs |
| Machine-readable values | JSON keys, enum values, serialised fields |
| Interfaces | API paths, MQTT topics, CLI flags, environment variables, service names |
| Identifiers | digests, hashes, seeds, versions, run identifiers |
| Sources | bibliographic titles and citations in their original language, external PDFs and documents |

A historical record that contains Portuguese stays intact. It may be
accompanied by an English summary; it is never edited in place.

## Identifiers that must survive translation unchanged

Gate names (`G0`–`G7`), claim identifiers (`C01`–`C15`), risk identifiers
(`R1`–`R33`, `RA1`–`RA15`), research questions (`RQ1`–`RQ3`), maturity levels
(`M0`–`M5`), tags (`exp-v1`, `data-v1`, `rc1`), dates, thresholds, units,
commands, paths.

## How the conversion proceeds

Active documentation is translated when it is next modified, plus the planned
migration below. The migration is split so that no single pull request becomes
unreviewable, and **it must not delay gate G1**: at most the governance batch
runs before the QEMU boots, the rest follows once G1 is green, and everything
is normalised before the `exp-v1` freeze.

| Order | Branch | Content |
|---:|---|---|
| 1 | `docs/g0-english-governance` | PR template, CONTRIBUTING, this policy, main READMEs |
| 2 | `docs/g1-english-technical-contracts` | CONTRACTS, ADRs, setup and technical documentation |
| 3 | `docs/g1-english-project-controls` | PROGRESS, scope and RQs, backlog, risks, claim matrix |
| 4 | `docs/g2-english-project-history` | LOG and the remaining historical narrative |
| 5 | `chore/g2-english-codebase-text` | comments, docstrings, text inside tests |
| 6 | `docs/g2-english-thesis-support` | thesis, research logs, manifests, residual documentation |

Planned renames, each with every link and reference updated in the same pull
request that performs it:

```text
docs/g0/ambito_e_rqs.md          -> docs/g0/scope_and_rqs.md        [done 2026-08-12]
docs/g0/email_orientadores_G0.md -> docs/g0/supervisor_email_g0.md  [done 2026-08-12]
docs/g0/riscos.md                -> docs/g0/risks.md                [done 2026-08-12]
thesis/latex/imagens/            -> thesis/latex/images/            [pending]
```

The Portuguese integrated plan v1.0 is preserved byte-for-byte under
`docs/governance/archive/`. The rebased English plan v1.1 at
`docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md` is normative from
2026-08-13 and records every intentional change; historical evidence is never
rewritten to match it.

## Status of the migration, stated plainly

The policy is in force for all new and modified content from 2026-08-11. The
repository is **not** yet fully migrated, and the migration is not following the
six-branch order above literally. What has actually been translated, as of
2026-08-12:

| Document | State |
|---|---|
| `README.md` (repository root) | translated (batch 1 content, done early on request) |
| `PROGRESS.md`, `docs/g0/`, both claim→evidence matrices, `docs/README.md` | translated (batch 3) |
| `docs/setup/`, `src/README.md`, `src/yocto/README.md`, `diagrams/`, the ADRs | translated where modified for correctness (batch 2 content, absorbed) |
| `LOG.md` | **mixed**: entries from 2026-08-11 onwards are in British English, the earlier Portuguese entries are untouched and are corrected only by dated notes (batch 4 outstanding) |
| `CONTRIBUTING.md` | translated (batch 1) |
| `src/CONTRACTS.md`, the thesis and research documents, code comments and docstrings | **outstanding** (batches 2, 5 and 6) |

The deviation from the branch order is deliberate and worth stating: the audit
of 2026-08-12 found documents whose *content* contradicted reality, and the
policy's own rule is that a document is translated when it is next modified. So
the files that had to be corrected were translated in the same change rather
than left in Portuguese to await their batch. The batches that remain are the
ones with no outstanding correctness defect.

No pull-request checklist should be read as asserting more than this. The
template's language item covers only the content that pull request creates or
modifies, precisely so that ticking it stays truthful while the legacy documents
wait their turn.

Order of work: the translation must not delay gate G1, and everything is
normalised before the `exp-v1` freeze.

## Definition of done for a translation pull request

- The diff contains linguistic and structural changes only.
- No functional behaviour, scope or acceptance criterion has changed.
- British English is used consistently.
- Gate, claim, risk and research-question identifiers are unchanged.
- Dates, thresholds, units, commands, paths, hashes and digests are unchanged.
- All renamed-file references and links have been updated.
- Relevant tests pass.
- LaTeX documents compile without new warnings or unresolved references.
- A word-level diff has been reviewed manually.
- No progress, maturity or gate status has been upgraded because of translation.
- Commit, pull-request and review communication is written in English.
