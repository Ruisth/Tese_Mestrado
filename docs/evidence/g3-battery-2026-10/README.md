# G3 qualifying battery of 2026-10-02 and 2026-10-03, and its T8/T9 completion of 2026-10-05 — evidence index (publication prepared, not made)

**An index, not a capsule; not a gate, not a claim.** This directory prepares
the publication of the twenty packages recorded by the two sessions of the G3
qualifying battery, S1 (2026-10-02, rows T1–T5) and S2 (2026-10-03, rows T6–T8;
T9 not run), executed on the frozen candidate `80e833f`. **The byte copies are
not in this directory.** What is here is the list of the packages, each with
its file count and the SHA-256 of its own `SHA256SUMS`, computed read-only from
the local originals under `output_test/runs/2026-10-02/` and
`output_test/runs/2026-10-03/` on 2026-10-03, so that a later copy can be
checked against the packages as they were sealed. The results themselves are
recorded in the
[results addendum](../../governance/g3-battery-2026-10-results.md) and in the
two result notes held locally beside the packages
(`output_test/decisions/2026-10-02_g3-battery-s1-results.md` and
`2026-10-03_g3-battery-s2-results.md`, outside this repository). G3 stays
`Not decided` in [`gate_decision_log.md`](../../governance/gate_decision_log.md);
merging this directory decides nothing, admits nothing and publishes nothing.

## The packages

Twenty packages, 1,120 sealed entries in all, 48,982,595 bytes on disk
(22,946,857 under `2026-10-02/`, 26,035,738 under `2026-10-03/`; about 49 MB).
"Files" is the number of entries of the package's `SHA256SUMS`, which lists
every file of the package except itself. Every seal verified on 2026-10-03,
read-only, before this index was written (`sha256sum -c` in each package: 20 of
20, 1,120 entries, no failure); the Project Manager's independent read-only
verification of the same day found the same 1,120 matching entries. The
official rows name their purpose, `80e833f` and `repo_dirty_lines: 0`.

| Package | What it holds | Files | `SHA256SUMS` of the package |
|---|---|---|---|
| `2026-10-02/HIST_2026-10-02-g3-battery-host-preparation` | the host preparation before S1: identities and freshness (part 1), the steps script `g3_battery.sh`, its README, the row files extracted from the `80e833f` runbook, their three verifications, the corrections and the isolated stub benches | 85 | `36de1093c9356ec5ac186499c7d9b61622067244013d99606c85a793020647b5` |
| `2026-10-02/20261002T150133Z_guest-session_attempt08` | S1: boot, open and close of the guest session, the recorded `compose stop -t 130` | 87 | `98a99e41c4f79fece970213893b8b35e1e36e9903b55034251eeebf393e25e0a` |
| `2026-10-02/20261002T150214Z_live-preflight_attempt09` | S1: live preflight and its interlock | 42 | `fefe3dc0916a512f5ce44ea273f0ef0e024380c9bc18a78e6765fbc02f345a99` |
| `2026-10-02/20261002T150720Z_g2-gate-preconditions_attempt05` | S1: health record the rows started from | 26 | `e695b2018fc2f45a26594774fe8460e89359c4c2c3a69a1f54146c78faeb97e2` |
| `2026-10-02/20261002T150829Z_g3-qualification-t1-smokes_attempt01` | row 1, official: T1's three smokes `itest-smoke-01/02/03-q1` | 66 | `6e9d48320216cf3abd59e600f46335564960c373a495dfd06a6b46a78bc9f087` |
| `2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01` | row 2, official: T1's harness run `nominal-r02` (sealed inner run directory) | 88 | `4b9abd744204be82c50ff63ff017fffe16e56b6d6bde3240933529c93f73e3ee` |
| `2026-10-02/20261002T154427Z_g3-qualification-t2_attempt01` | row 3, official: T2 `itest-3dev-01-q1` | 41 | `8ff4f7a788e208b4f9351960dbd3bd4b4dab2f9e1c667b2d20cc3deaeba6521d` |
| `2026-10-02/20261002T155313Z_g3-qualification-t3_attempt01` | row 4, official: T3 `itest-invalid-01-q1`, with its post-drain copy | 41 | `aa58b80de3e46a275e62e0c7ac6747056e69dd2e1138d42e6ffc7744b5151c0c` |
| `2026-10-02/20261002T160154Z_g3-qualification-t4-replay_attempt01` | row 5, official: T4's replay `itest-dup-01-q1` | 45 | `0551ef5980961a5327fea15a1dbce593a08f2fb9c43c16d0cdead5f948a37fba` |
| `2026-10-02/20261002T161432Z_g3-qualification-t4-reset_attempt01` | row 6, official: T4's sequence reset `itest-dup-02-q1` | 38 | `eed0f651edcbb2bb87ff3884d46d9dec5ca75c3f905865dd2147d6a1c88290ec` |
| `2026-10-02/20261002T162159Z_g3-qualification-t5_attempt01` | row 7, official: T5 `itest-dropout-01-q1`, with the bounded broker log | 41 | `8dcad24c85d0e7e02b29ea4ff1d038db9b4ff92d844e5272e7ad751c3dcca44c` |
| `2026-10-02/HIST_2026-10-02-g3-battery-s1-operator-records` | S1: the steps script's state directory as sealed, one console per invocation, the operator's launcher, waiter and sealing scripts, the classification notes | 51 | `98f767b1d8cee4ffe9f642167487b8f1a589e8e45bdfaff279a9bdeee3debbbb` |
| `2026-10-03/20261003T132249Z_guest-session_attempt09` | S2: boot, open and close of the guest session; holds the read-only post-reboot evidence step of T8 and the recorded `compose stop -t 130` | 89 | `92806a551995cc5ce7eddfbbb3161503a72683f2151879c5b8e4bc9b067db160` |
| `2026-10-03/20261003T132332Z_live-preflight_attempt10` | S2: live preflight and its interlock | 42 | `0966e94b16dfa15ab1c1f0973111e7510ab69363f0c55de2e9c8e5cb579943ae` |
| `2026-10-03/20261003T132836Z_g2-gate-preconditions_attempt06` | S2: health record the rows started from | 26 | `5ffa966aba9e980a4156f614cacffa37277cf7e59e44f3a8c6d71b2d1a266f0e` |
| `2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01` | row 8, official: T6 `controller_restart-r03`; the inner harness run is **invalid and unsealed** (its `SHA256SUMS` withheld by the harness), and the outer seal of this package does not validate it | 95 | `d0126c2249e3bd793e42ee4d1b953847a6991cff60592b54c6469d77c6f77e5d` |
| `2026-10-03/20261003T135147Z_g3-qualification-t7-mongo_attempt01` | row 9, official: T7's MongoDB fault `itest-mongo-fault-01-q1` | 52 | `d086d46bfeea85d27602e01615b3f9f587b65c701b2cd227ec02d728b8214f1a` |
| `2026-10-03/20261003T140639Z_g3-qualification-t7-ditto_attempt01` | row 10, official: T7's Ditto fault `itest-ditto-fault-01-q1` | 52 | `85aaf8392a5dc0cf274d154e3af00053c730aaaee86168d6509ad496010fe33e` |
| `2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01` | row 11, official, **incomplete**: T8 `itest-reboot-q1` up to the reboot; the post-reboot artefacts were never written, as the procedure halted waiting for a QEMU exit that does not occur | 32 | `6da5dc8163c7f69f5a2dbd397d6097d1889db8d9d4de5df0fb769c967cbd3d56` |
| `2026-10-03/HIST_2026-10-03-g3-battery-s2-operator-records` | S2: the steps script's state directory as sealed, consoles, the operator's helpers and sealing scripts, the classification notes, the halt record | 81 | `a4e9350c3f92b6363308f32bd9ef61f7707c9ba0c71639b764f7450666432ea3` |

## The T8/T9 completion of 2026-10-05

Eleven packages, 838 sealed entries, 9,021,983 bytes on disk, all under
`output_test/runs/2026-10-05/`, from the two openings of session S3 (tests 8
and 9) on the same candidate with the procedure and tools of `8e49261`. Every
seal verified read-only on 2026-10-05 before this index was extended
(`sha256sum -c` in each package: 11 of 11, 838 entries, no failure); the
Project Manager's read-only check of the same day found the 409 entries of
the seven packages of the preparation of the second opening and of the
second opening matching. The failed first opening is kept as it was sealed.

| Package | What it holds | Files | `SHA256SUMS` of the package |
|---|---|---|---|
| `2026-10-05/HIST_2026-10-05-g3-t8t9-host-preparation` | the preparation of S3: the clone moved to `8e49261`, identities and freshness, the operator script for S3, the step files re-extracted from the `8e49261` runbook with `-q2`, the bounded check and the stub benches | 288 | `1dc610d18751dcccc17111ca94b6b465fd7819cb2b2b6298f5c85f5b6c23a72f` |
| `2026-10-05/20261005T105614Z_guest-session_attempt10` | first opening: boot, the halt at open, the recorded `compose stop -t 130` and the close | 85 | `ef820eb906261e20dccc3618b6f30cb85ba150a8e3edc45cca90597be10a6cea` |
| `2026-10-05/20261005T105656Z_live-preflight_attempt11` | first opening: the preflight that ended exit 3 on `collector-duration` alone — **failed, instrumentation invalid**, kept so | 42 | `c4bc5475774416fe500d5d412fa946e8ea32e8861b6eb956f9fac0e723d24042` |
| `2026-10-05/HIST_2026-10-05-g3-t8t9-s3-operator-records` | first opening: the operator script's state, consoles and the halt note | 14 | `e5711eb754badea82fd91ff7baaf13fcbfe3b8a218ec2ec9744cab798a880175` |
| `2026-10-05/HIST_2026-10-05-g3-t8t9-host-preparation-attempt02` | the minimal preparation of the second opening: the operator copy with the post-close root file system value, a fresh state directory and the authorised exception's read-only checker, the host recheck and the focused benches | 74 | `cdcd92841279d0a15fa66e4de13124d69e2c1bb153edf14407ee8e9e4dd764b2` |
| `2026-10-05/20261005T114428Z_guest-session_attempt11` | second opening: boot, open and close, the recorded `compose stop -t 130` | 87 | `b7ad5f80d66bc6c7ce2421c821dcc732b2069a1f62c48bcda2feea8327d2acc9` |
| `2026-10-05/20261005T114511Z_live-preflight_attempt12` | second opening: the preflight, passed (the exception not used) | 42 | `eece4bd2e93b8ac2fd7eb655dc5f848b44dd0374b78c6582010785cd5d2f8c60` |
| `2026-10-05/20261005T115022Z_g2-gate-preconditions_attempt07` | second opening: the health record the rows started from | 26 | `74bbae18a29c5c7613361aa9ee99249b8876e048cf3596367573af5bd6ce096e` |
| `2026-10-05/20261005T115131Z_g3-qualification-t8_attempt02` | row 13, official: T8 `itest-reboot-q2` with the smoke `itest-post-reboot-01-q2` — pass | 85 | `dfd2da2173f040d8b93367d508781a44631704417c8bbb87707bb9d9632432cf` |
| `2026-10-05/20261005T120537Z_g3-qualification-t9_attempt01` | row 14, official: T9's five sub-checks and the exposure observations — pass | 71 | `9043c4203484d5dc9199fb0889bbd88d885c1a62e642963f3e70ffc9d699dd8c` |
| `2026-10-05/HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02` | second opening: the operator script's state, consoles and the classification notes | 24 | `21b2ad827ebd99d4140bc751f6a64c1eacba64066ee6ec38a5dec855fb8202e6` |

Each of the seven exported packages records its secret scan with an empty
`excluded` list; the four `HIST_` packages were swept before sealing (0 files
with a secret value, 0 with a private-key header). The publication step below
applies to these packages too.

`PACKAGES.sha256` beside this README holds the thirty-one digests (the twenty above and the eleven of 2026-10-05) in
`sha256sum` form, one line per package, with the path of each `SHA256SUMS`
relative to `output_test/runs/`; from that directory `sha256sum -c
<this file>` checks that the local seals are the ones indexed here. It is not
a seal of this directory: `tools/ci/verify_evidence.py` reads files named
`SHA256SUMS` only, and this directory has none until the copies are made.

## Secret review and sealing notes, as recorded at export

- **The seventeen exported packages** (the two sessions, the two preflights,
  the two gate records and the eleven rows) each carry an `export_manifest.json`
  whose `secret_scan` records that the values of the named password variables
  and PEM private-key blocks were searched in every file, and whose `excluded`
  list is empty: nothing was withheld from any of them.
- **The two operator-records packages** record, in their READMEs, that the
  sealing script stopped before sealing because its private-key sweep matched
  its own pattern text in the copy of itself (`operator/seal_ops.sh`, line
  25); no key is in either package. A second script repeated the sweep with a
  pattern that does not match that text (0 files with a secret value, 0 with
  a private-key header) and wrote the README and `SHA256SUMS` in place;
  nothing was copied again or replaced. Each carries one seal; neither was
  resealed.
- **The host-preparation package** has no export manifest and records no
  sweep of its own; its interface bench shows the simulator's password as
  `<SECRET>` over a placeholder value, and the steps script reads no secret.
  A sweep of all twenty packages against the execution host's environment
  values, as was done for the r03 capsule on 2026-09-29, is part of the
  publication step below, not of this index.

## The publication, proposed as a separate step

The byte copies are **not** committed with this index: about 58 MB
(58,004,578 bytes: the twenty packages of 2026-10-02/03 and the eleven of
2026-10-05), in thirty-one directories whose paths exceed what the Windows worktrees used for this
block can hold (the existing capsules already show as modified or deleted
there, which is why no file under `docs/evidence/` is staged from them). The
proposed step, for Rui's decision and under the convention of the
[r03 capsule](../finite-proof-r03/README.md): copy the thirty-one
packages byte for byte from a checkout that holds long paths (WSL, or
`core.longpaths=true` on a short path), keeping every export name and every
inner seal exactly as sealed; compare every file by SHA-256 with the originals
and check the inner seals against `PACKAGES.sha256`; run the secret sweep over
all 1,958 files (1,120 and 838) and keep its script and output locally with the block's
evidence; write the directory's own `SHA256SUMS` (every file, the inner seals
and this README, not itself) and the `.gitattributes` line that stores the
directory without text conversion; then publish it in its own pull request.
Nothing in the copies is to be rewritten: not an inner seal, not an export
`SUMMARY.md` ("a package here is a local copy; it is not published or
admitted evidence" was true when sealed), not a classification. Publishing
the copies would record the battery and its T8/T9 completion; it would not accept a family, a gate or
a claim, and the decisions the results addendum lists stay Rui's.
