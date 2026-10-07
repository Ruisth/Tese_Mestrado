# G3 qualifying battery of 2026-10-02 and 2026-10-03, its T8/T9 completion of 2026-10-05 and test 6 of 2026-10-07 — evidence capsule

**A capsule of byte copies; not a gate, not a claim.** This directory publishes
the thirty-eight packages recorded by the G3 qualifying battery: sessions S1
(2026-10-02, rows T1–T5) and S2 (2026-10-03, rows T6–T8; T9 not run) on the
frozen candidate with the tools of `80e833f`; the two openings of session S3 (2026-10-05, tests 8
and 9) with the procedure of `8e49261`; and test 6 again, its preparation and
session S4 (2026-10-07) with the tools of `1fd9792`, under the criterion amended
on 2026-10-05 — each package copied byte for byte from its local original under
`output_test/runs/<UTC date>/`, which stays as it was. The results are recorded
in the [results addendum](../../governance/g3-battery-2026-10-results.md); the
case for closing the gate, clause by clause, is the
[G3 closing proposal](../../governance/proposals/2026-10-07-g3-closing-proposal.md).
G3 stays `Not decided` in
[`gate_decision_log.md`](../../governance/gate_decision_log.md) until the
student records a dated decision; publishing this capsule and merging its pull
request decide nothing, admit nothing and accept no family, gate or claim.

## The packages

Twenty packages, 1,120 sealed entries in all, 48,982,595 bytes on disk
(22,946,857 under `2026-10-02/`, 26,035,738 under `2026-10-03/`; about 49 MB).
"Files" is the number of entries of the package's `SHA256SUMS`, which lists
every file of the package except itself. Every seal verified on 2026-10-03,
read-only, before this index was written (`sha256sum -c` in each package: 20 of
20, 1,120 entries, no failure); the Project Manager's independent read-only
verification of the same day found the same 1,120 matching entries. The
official rows name their purpose, `80e833f` and `repo_dirty_lines: 0`. The
paths below are relative to this directory (and, before publication, to
`output_test/runs/`).

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

## Test 6 again: its preparation and session S4 (2026-10-05 to 2026-10-07)

Seven packages, 567 sealed entries, 17,726,504 bytes on disk: the preparation
of S4 under `2026-10-05/` and the supplement and the session under
`2026-10-07/`, on the same candidate with the tools of `1fd9792` (pull request
#57: the transition rule, the collector's uptime bounds, the exactly-once check
and the plan entry `controller_restart-r04`; the system under test unchanged,
the collector being instrumentation that the frozen preflight installed at
S4's open). Every seal verified read-only on 2026-10-07 before the copies were
made (`sha256sum -c` in each package: 7 of 7, 567 entries, no failure).

| Package | What it holds | Files | `SHA256SUMS` of the package |
|---|---|---|---|
| `2026-10-05/HIST_2026-10-05-g3-t6-host-preparation` | the preparation of S4: the clone moved to `1fd9792`, the identities, `controller_restart-r04` unused on the host and on the guest's root file system, the entry r04 added to the pilot plan (the predecessor kept), the operator script for S4, the step file re-extracted from the `1fd9792` runbook, the bounded checks, the stub benches and their adversarial readings | 268 | `34715555f87e7ad3e8f48fe7cc847425b08c65276c82994dd4ea2dd065baafd4` |
| `2026-10-07/HIST_2026-10-07-g3-t6-preparation-supplement` | the supplement before S4's authorisation: the recorder's emergency cleanup that keeps its partial capture inside the session's package, the procedure's update and its one offline verification (the cleanup was not needed in S4) | 29 | `74dbe1a9c8faf6ea1359c6cdac059ec21b98314669e454bc31a3d79fe71750f6` |
| `2026-10-07/20261007T120357Z_guest-session_attempt12` | S4: boot, open and close of the guest session, the recorded `compose stop -t 130` | 87 | `84018cda4eb0ad696cb62f6225fcfd1c67387d00cb72bec84152833441a392dd` |
| `2026-10-07/20261007T120444Z_live-preflight_attempt13` | S4: the preflight, passed, with the new collector installed (the previous one kept on the guest) and `collector-duration` judged on the collector's uptime bounds | 42 | `921d721295f14764ff3a376d934bc3b83b229be00085b9faf3390f79483d369a` |
| `2026-10-07/20261007T121006Z_g2-gate-preconditions_attempt08` | S4: the health record the row started from | 26 | `9dd069d9302d77f9c94843a50586749c63f4c5c251483b214dc3436543dafa73` |
| `2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02` | row 15, official: T6 `controller_restart-r04` (sealed inner run directory) — pass under the criterion amended on 2026-10-05 | 97 | `26f556065ee079b2a67c4c5dc659a373195214d5e2b4552565a460de53230283` |
| `2026-10-07/HIST_2026-10-07-g3-t6-s4-operator-records` | S4: the operator script's state, consoles and the classification notes | 18 | `7aaf134131b49a9efe295ca9b26d06cb6e3b42dec7116834653e717d4dc3f856` |

`PACKAGES.sha256` beside this README holds the thirty-eight digests in
`sha256sum` form, one line per package, with the path of each `SHA256SUMS`
relative to this directory (the same relative path as under
`output_test/runs/`); from this directory `sha256sum -c PACKAGES.sha256`
checks that the copies' seals are the recorded ones. The thirty-one lines of
the index of 2026-10-05 are kept byte for byte; the file is sorted by path,
so the seven new lines are interleaved (line 28 and lines 33–38). For the
three `HIST_` packages of test 6 the digest was recorded at sealing; for the
four packages S4's export sealed, no digest of the seal was recorded then:
theirs were read from the originals at publication, after each original
verified in place, and the Project Manager's recomputation of their entries
(register entry of 2026-10-07 14:19 WEST) found no failure.

## The records: the battery's local notes

The authorisations, requests, result notes and decisions that the results
addendum and the [closing proposal](../../governance/proposals/2026-10-07-g3-closing-proposal.md)
cite were held locally under `output_test/decisions/`. The twenty-two of
2026-10-01 to 2026-10-07 are published here, byte for byte, so that the
battery and the scoped decision on test 6 can be read from a clean checkout;
the originals stay where they were. Each was compared with its original by
SHA-256 when copied; they are covered by this directory's outer seal.

| Record | What it is | sha256 (first 16) |
|---|---|---|
| [`2026-10-01_g3-candidate-freeze-and-battery-packet.md`](records/2026-10-01_g3-candidate-freeze-and-battery-packet.md) | the decision packet, revision 2: the candidate frozen, the nine families in order, the classes, limits and stop rules | `d4b215dda0bdb760…` |
| [`2026-10-01_g3-candidate-freeze-and-battery-packet.r1.md`](records/2026-10-01_g3-candidate-freeze-and-battery-packet.r1.md) | the packet's first revision, kept | `7059e52714f43ef5…` |
| [`2026-10-02_g3-battery-s1-results.md`](records/2026-10-02_g3-battery-s1-results.md) | S1's result note (rows 1–7) | `74fadc838a05e359…` |
| [`2026-10-02_g3-freeze-and-battery-authorisation.md`](records/2026-10-02_g3-freeze-and-battery-authorisation.md) | Rui's authorisation of the freeze (Q1) and the battery (Q2), with the four conditions | `531d0eda38b1f70b…` |
| [`2026-10-03_g3-battery-s2-results.md`](records/2026-10-03_g3-battery-s2-results.md) | S2's result note (rows 8–11; T9 not run) | `9a9e3cbb33fe0a18…` |
| [`2026-10-04_g3-t8-t9-s3-decision-summary.md`](records/2026-10-04_g3-t8-t9-s3-decision-summary.md) | the one-page summary of Rui's four choices for S3 | `e92ebdf1286bc8be…` |
| [`2026-10-04_g3-t8-t9-session-request.md`](records/2026-10-04_g3-t8-t9-session-request.md) | the request for session S3 (tests 8 and 9) | `03e51744b050ea46…` |
| [`2026-10-05_g3-s3-halt-correction.md`](records/2026-10-05_g3-s3-halt-correction.md) | the dated correction of that halt's reading (clock basis) | `f6eaea5cb08ae81b…` |
| [`2026-10-05_g3-s3-preparation-handoff.md`](records/2026-10-05_g3-s3-preparation-handoff.md) | S3's preparation delivered | `c9f0d38d648bb501…` |
| [`2026-10-05_g3-s3-session-authorisation.md`](records/2026-10-05_g3-s3-session-authorisation.md) | Rui's authorisation of S3 | `ebfbfffc39534bb1…` |
| [`2026-10-05_g3-s3b-exception-authorisation.md`](records/2026-10-05_g3-s3b-exception-authorisation.md) | Rui's authorisation of the prospective exception for S3's second opening (not used) | `27067ecb8b421a02…` |
| [`2026-10-05_g3-t5-t6-decisions.md`](records/2026-10-05_g3-t5-t6-decisions.md) | Rui's decisions on T5's reading and T6's criterion (option 2) | `3700522d3b66a3f8…` |
| [`2026-10-05_g3-t6-decision-page.md`](records/2026-10-05_g3-t6-decision-page.md) | the one-page choice for test 6 (options 1 and 2) | `4453e1d5deb18e14…` |
| [`2026-10-05_g3-t6-preparation-handoff.md`](records/2026-10-05_g3-t6-preparation-handoff.md) | S4's preparation delivered | `484446e9497519c0…` |
| [`2026-10-05_g3-t6-sampling-option-a-decision.md`](records/2026-10-05_g3-t6-sampling-option-a-decision.md) | Rui's adoption of option A with the Project Manager's conditions | `d40853a17d0a0d66…` |
| [`2026-10-05_g3-t6-session-request.md`](records/2026-10-05_g3-t6-session-request.md) | the request for session S4 (test 6 only): identities, plan entry r04, limits, stop conditions, classes | `0efcf3927430933b…` |
| [`2026-10-05_g3-t8-t9-results.md`](records/2026-10-05_g3-t8-t9-results.md) | S3's first opening: the halt at the preflight | `d752ad2b0a33e519…` |
| [`2026-10-05_g3-t8-t9-s3b-results.md`](records/2026-10-05_g3-t8-t9-s3b-results.md) | S3's second opening: T8 and T9 (rows 13–14) | `cdb0052928b6d84d…` |
| [`2026-10-07_g3-s4-session-authorisation.md`](records/2026-10-07_g3-s4-session-authorisation.md) | Rui's authorisation of S4 | `1a61d7b87d393d9a…` |
| [`2026-10-07_g3-t6-preparation-supplement.md`](records/2026-10-07_g3-t6-preparation-supplement.md) | the supplement: the recorder's emergency cleanup with its partial capture kept | `4d58302bfb1881ee…` |
| [`2026-10-07_g3-t6-results.md`](records/2026-10-07_g3-t6-results.md) | S4's result note (row 15) | `08d2b4c53bfb531b…` |
| [`2026-10-07_register-date-correction.md`](records/2026-10-07_register-date-correction.md) | a dated correction: the register entry that asked for the supplement is headed 2026-10-05 21:56 WEST | `cc04dd1bea5505b0…` |

One date in these records is corrected, not rewritten: the supplement note,
the S4 authorisation and the `README.md` of the sealed package
`2026-10-07/HIST_2026-10-07-g3-t6-preparation-supplement` call the Project
Manager's register entry at line 4937 "the opinion of 2026-10-07"; the entry
is headed 2026-10-05 21:56 WEST, and 2026-10-07 is the date it was relayed
([correction](records/2026-10-07_register-date-correction.md)). The sealed
bytes are kept.

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
  A sweep of all thirty-eight packages against the execution host's
  environment values was made at the publication (below).
- **The seven packages of test 6:** the four exported ones carry an
  `export_manifest.json` whose `excluded` list is empty; the three `HIST_`
  packages were swept before sealing (0 files with a secret value, 0 with a
  private-key header).

## The publication of 2026-10-07

Done under the Project Manager's order of 2026-10-07 (register line 5068), from
a WSL clone, so that no path is shortened. For each of the thirty-eight
packages, in order: its `SHA256SUMS` hashed and compared with the recorded
digest where one was recorded (`PACKAGES.sha256` for the thirty-one, the
value recorded at sealing for the three `HIST_` packages of test 6; for the
four packages S4's export sealed, read from the original), the original
verified in place (`sha256sum -c`), the copy made
(never over an existing directory), the copy verified, and the two trees
compared file by file (every file, the seal itself included; no entry that is
neither a file nor a directory). All thirty-eight passed: 2,525 sealed entries,
2,563 files with the thirty-eight seals, 75,731,082 bytes. The secret sweep of
the copies (the values of the execution host's four secret variables, never
printed, and PEM private-key headers) found nothing. Nothing in the copies was
rewritten: not an inner seal, not an export `SUMMARY.md` ("a package here is a
local copy; it is not published or admitted evidence" was true when sealed),
not a classification; invalid, incomplete and halted attempts are published as
they were sealed.

Three things the repository needed for the bytes to stay exact:

- a `.gitattributes` line stores this directory without text conversion;
- the repository's `*.out` ignore rule had held back three files of the T9
  package (`other/itest-acl-20261005T120642Z/anon.out`, `ctl-sub.out`,
  `sim-sub.out`); they were added explicitly, and every seal was then verified
  again from a tree extracted from the commit (`git archive`);
- `tools/ci/check_markdown_links.py` no longer checks the Markdown files of a
  sealed package (a directory named as an attempt or `HIST_`, whose own
  `SHA256SUMS` lists the file): copies of repository documents kept by a
  preparation or a review (a runbook blob, a reviewer's copy of a README) keep
  relative links that do not resolve from inside the package, and their bytes
  cannot change. Capsule READMEs such as this one are still checked.

`SHA256SUMS` in this directory is the capsule's outer seal: every file below
this directory (the packages, their own seals, the records, `PACKAGES.sha256`
and this README), not itself. `tools/ci/verify_evidence.py` checks it, and every inner
seal, on every pull request.

## How to verify

From this directory: `sha256sum -c --quiet SHA256SUMS` (every file of the
capsule), `sha256sum -c --quiet PACKAGES.sha256` (each package's seal is the
one recorded at sealing), and `sha256sum -c --quiet SHA256SUMS` inside any
package. The packages' paths are long (up to 185 characters from the
repository root): a Windows checkout needs `core.longpaths=true` and a short
base path.
