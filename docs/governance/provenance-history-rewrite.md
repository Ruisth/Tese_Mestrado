# Repository provenance and rewritten-history mapping

> **Control record — updated 2026-08-14.** This document preserves evidence lineage. It
> does not authorise publishing pre-rewrite history and does not itself change
> any Git reference.

## Protected evidence identity

The annotated tag `evidence/g1-yocto-build-5770c0a` was published and points to
the exact G1 build commit
`5770c0ad4f4e1a5205845afcb9aa9eb797e76df0`. Evidence that cites the build must
prefer the tag and retain the commit SHA alongside it.

## Verified repository bundles

| Bundle | Bytes | SHA-256 | Purpose |
|---|---:|---|---|
| `backups/egw-20260808-final.bundle` | 991,862 | `edf0c2409052498533667b78719c85468a8eba05d87b605b4ce0440fa35ba017` | Historical 8 August final bundle. |
| `backups/egw-20260808-p5.bundle` | 1,076,018 | `10287e3514d156c8374a6ff13dd8a5cc94257484173364c0b6fbe92b1562db13` | Historical P5 bundle. |
| `backups/egw-20260808.bundle` | 547,224 | `101fc6654d0e73692aff1a8d0afb14d4c0e011a18e20864ec89bfbba9e45575f` | Earlier 8 August bundle. |
| `backups/pre-rewrite-20260811-203811.bundle` | 1,129,824 | `d8e1efc3eededf2cead9ec98acb534862a3b533c13c90f03ed0ef7c7e640c1b4` | Pre-rewrite preservation. Do not publish until authorship, secrets and metadata are audited. |
| `backups/egw-20260813-pre-sync.bundle` | 1,364,594 | `71a20cce98104006aa532818935e558d5e02c259acc64c798900b35cbddc189d` | Complete pre-synchronisation safety bundle. |
| `backups/egw-20260813-post-implementation.bundle` | 1,633,967 | `45b01350262c8e96c7a547a7a85ac69b94d8167e52d24b392fd2cc69f8f219fb` | Complete post-implementation snapshot through operational-record commit `71f4792`; includes protected G1 evidence tag and draft proposal commit `bc82911`. |
| `backups/egw-20260814-g1-strict-evidence.bundle` | 1,819,509 | `5b2cf69fcb7bdee7f2e2916bccfc04d852fe8b91077a2d38accd02a96a2bab12` | Complete-history snapshot through strict G1 evidence commit `d4bfa9d`; preserves 12 refs, including `dev`, the draft proposal branch and the protected preliminary G1 tag. |

All seven files and hashes were checked in the workspace. The 2026-08-14 bundle
reports a complete history and preserves 12 refs; it was created after the
strict evidence commit and before this inventory row to avoid a
self-referential checksum.
At least one current complete bundle must also be copied off this machine and
verified there; multiple bundles on one disk are not an independent backup.

## Exact-tree lineage across the history rewrite

The 2026-08-13 audit established the following old-commit to reachable-commit
mappings by exact tree identity. The abbreviated IDs are unambiguous within the
audited repository snapshot.

| Historical reference | Reachable equivalent | Required documentary treatment |
|---|---|---|
| `25b7eea` | `983c18f` | Cite the reachable SHA for checkout; retain `25b7eea` as historical execution lineage. |
| `57228e1` | `8a98340` | Cite the reachable SHA for checkout; retain the full old SHA already sealed in the evidence environment record. |
| `ca445a3` | `01b29de` | Cite the reachable SHA for checkout; retain the full old SHA already sealed in the evidence environment record. |
| `9491090` | `02f767e` | Replace operational references; keep the old evidence-containing commit as lineage. |
| `03ee5c9` | `73b4029` | Replace operational rehearsal references; keep the old SHA in the historical note. |
| `e83fb24` | `14f2318` | Replace operational defect-fix references; retain old SHA as pre-rewrite lineage. |
| `c0ebf7c` | `d941de8` | Replace operational defect-fix references; retain old SHA as pre-rewrite lineage. |

### Referencing rule

For every affected evidence document:

1. preserve the original executed/tested SHA in a field labelled
   `historical_execution_commit` or equivalent;
2. add the reachable equivalent in a separate
   `reachable_equivalent_same_tree` field;
3. use the reachable SHA for reconstruction commands;
4. state that equivalence is by exact Git tree, not by commit identity—the
   author, parent and timestamp metadata may differ;
5. never rewrite sealed raw files or checksums merely to modernise a SHA.

Before an automated bulk update, expand each abbreviated reachable ID to its
full object ID from the current repository and verify tree equality again.

## Retention and deletion rule

- Do not delete the legacy feature branch or any bundle merely because the G1
  commit now has a tag. First verify tag reachability from a clean clone and the
  off-machine bundle.
- Do not publish the pre-rewrite bundle without a content, authorship, secret
  and personal-data audit.
- Record any future tag, bundle, deletion or off-machine copy in `LOG.md` with
  date, operator, path and SHA-256.
