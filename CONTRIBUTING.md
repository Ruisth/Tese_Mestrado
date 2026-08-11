# Repository conventions

## Working language

British English (en-GB) is the sole working language: code comments, tests,
documentation, branch names, commit messages, pull requests and reviews. Dates
use ISO 8601 (`YYYY-MM-DD`). The full policy, its exceptions and the list of
things that are never translated are in
[`docs/governance/language-policy.md`](docs/governance/language-policy.md).

## Branch model

| Branch | Role |
|---|---|
| `main` | Stable versions only, promoted by pull request from `dev` |
| `dev` | Where work lands, always by pull request |
| `<type>/g<gate>-<short-objective>` | Working branch, created from an up-to-date `dev` |

Never commit directly to `dev` or `main`. An active ruleset requires a pull
request on both and forbids force-pushes and deletions.

Example branch names:

```text
docs/g0-closeout
build/g1-yocto-qemu
feat/g2-arm64-vertical-slice
test/g3-harness-pilot
fix/controller-recovery-readiness
```

## Commit messages

Conventional Commits:

```text
<type>(<scope>): <technical outcome>
```

Examples:

```text
build(yocto): validate two qemuarm64 boots
feat(controller): materialise telemetry in Ditto
test(harness): validate live dropout recovery
docs(thesis): complete research methodology
fix(simulator): preserve sequence after reconnect
```

## Authorship and metadata policy

- Every commit uses the repository owner as both author and committer.
- No attribution trailers (`Co-authored-by`, `Generated-by`, `Assisted-by` or
  equivalents).
- Assistance-tool names do not appear in titles, descriptions, comments,
  reviews, commit messages or pull-request metadata. They may appear freely in
  file and directory names and in file contents.

The `.github/workflows/metadata-policy.yml` workflow checks this on every pull
request. It fails the check and records the findings in the run log; it never
posts automatic comments or reviews.

Before any push:

```powershell
git config --local user.name
git config --local user.email
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
git log origin/dev..HEAD --format="%h | %an <%ae> | %cn <%ce> | %s"
```

## Scope of a pull request

One pull request delivers **one verifiable objective**, typically one to three
days of work, and includes the implementation, the tests, the documentation,
the management state and the evidence for that objective. Dates belong to
milestones and to the schedule, not to the content of a pull request.

The template in `.github/pull_request_template.md` is filled in on every pull
request.

**Merging a pull request demonstrates implementation and verification; it does
not close a gate.** Accepting a gate still requires the evidence defined in the
plan, and is recorded in `PROGRESS.md` and in Annex C of the plan.

## Merging

Use **Create a merge commit**. Never squash, never rebase: archived evidence
under `docs/evidence/` references commit hashes, and rewriting them would
invalidate those references.
