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

Active documentation is translated when it is next modified. The original
six-branch sequence is historical: correctness work crossed those batch
boundaries, and the corresponding remote branches have been merged or removed.
Do not recreate the sequence merely to match an obsolete branch plan. Complete
the remaining active-language work in small reviewable pull requests before
the `exp-v1` freeze, without delaying G1/G2 execution.

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
repository is **not** yet fully migrated. What is true as of 2026-08-13:

| Document | State |
|---|---|
| Repository governance, main READMEs, `PROGRESS.md`, active `docs/g0/` controls and claim→evidence matrices | English; historical Portuguese sources are preserved rather than rewritten |
| `docs/setup/`, technical READMEs, active diagrams and ADR index | English where active; historical ADR text may retain original wording when changing it would distort the record |
| Dissertation and research support | Main dissertation prose and the Chapter 2 review PDF are English; the Portuguese Resumo is an explicit exception. Research records are predominantly English, with source titles left in their published language |
| `LOG.md` | **mixed by design**: entries from 2026-08-11 onwards use British English; earlier Portuguese entries are historical and remain untouched, with dated English corrections where needed |
| `src/CONTRACTS.md` | **outstanding and active**: still largely Portuguese. Translate in one contract-preserving PR before `exp-v1`, with schemas, examples, links and tests checked but no interface change |
| Code/test text | Predominantly English; isolated historical Portuguese comments remain in `src/egw_experiments/campaign.py`, `src/egw_experiments/resources.py` and `src/tests/test_experiments_campaign.py`. Remove them when those files are next changed or in a bounded text-only PR before `exp-v1` |
| External communication and front matter | `docs/g0/supervisor_email_g0.md` and the Resumo remain Portuguese under the stated exceptions |

The deviation from the former branch order was deliberate: the audit found
documents whose *content* contradicted reality, and those files were translated
while being corrected rather than left inaccurate to await a linguistic batch.
The remaining contract/code text is explicitly visible above; no checklist may
claim repository-wide completion while it remains.

No pull-request checklist should be read as asserting more than this. The
template's language item covers only the content that pull request creates or
modifies, precisely so that ticking it stays truthful while the legacy documents
wait their turn.

Order of work: translation must not delay gate execution; the active contract
and residual code/test text are normalised before the `exp-v1` freeze.

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
