# G3 qualifying battery: host preparation (2026-10-02)

Authority: Rui's authorisation of 2026-10-02 (output_test/decisions/2026-10-02_g3-freeze-and-battery-authorisation.md)
under the decision packet of 2026-10-01, revision 2. Host only: no guest was started, the controller image,
the guest deployment and the data disk were not touched. Nothing here is a G3 result.

## Part 1 - identities and freshness (part1-record/console.txt, outcome=prepared)

- The clean WSL clone ~/egw-exec/repo moved to 80e833f44f647fe9cd8f5e99d3abf3c444de95aa (tree dad725d0...), every branch unchanged.
- Helper file regenerated: sha256 e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb, 545 lines, HELPERS OK (the previous one kept as itest-helpers.sh.39403ead5a81).
- Every identity of the packet's section 1 that the host holds matches (runbook, export tool, drivers_sha256, deployment files, CONTRACTS, tunnel.sh, ca.crt, plan, controller record and archive, launcher, root file system c49500a9...).
- The fifteen -q1 ids and the plan entries nominal-r02 and controller_restart-r03 are unused on the host and, read offline with debugfs -c, on the guest root file system.

## Part 2 - the row files and the operator's steps script

| File | sha256 |
|---|---|
| `g3_battery.sh` | `fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1` |
| `g3_battery.README.md` | `cb5ee3020018707aa7870ed77bd528ade88b4a7abc2be2fedaa7e11be1c6e5fa` |
| `g3_extract_rows.py` | `6940366cca642d8f824092278e82e500112d8a3f9df36ed6d32cbc6595ead304` |
| `rows/rows.manifest.json` | `cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c` |
| `g3_hostprep.sh` | `a7a6e15cd263117706caea1d80eda23adfe0c66343d32501eef0c3222a8e6ca0` |
| `operator-procedure.md` | `55f13a5c76cd64b479f16e10cc680c88e0e1f3f2e386cdb0217fce53cf0b74a6` |

Row and step files (rows/; extracted from the runbook blob c55a2d3b... of 80e833f with the frozen test's own
extraction rule; only the run ids changed, with asserted counts; ids-only diffs beside them):

| Step file | sha256 |
|---|---|
| `rows/t1-harness-analyze.sh` | `d0fb59187c8fad3626c04c15b703911e599586a20231ba7c27849209b6e647c8` |
| `rows/t1-harness.sh` | `d6194365dfac0f3eac539d198777452872c01f1a276c77b866ff1b267f09d39c` |
| `rows/t1-smokes.sh` | `1b9869dae23aa6e92f8a80cb64023fdd7bb26b07b1ea993582b8777ab552e582` |
| `rows/t2.sh` | `43fa83f2fc17b52dd41cb6d4f902ce2276ee2a0fae1e104b8692fe044f59e3b6` |
| `rows/t3.sh` | `9731c836d334d9534109d8da738b63243c483286303016ba7df1ad42371497f6` |
| `rows/t4-replay.sh` | `fb646091cbc47287eee6d7d960eb15eae8c390309c766dbfb8aa784d56ac2954` |
| `rows/t4-reset.sh` | `3c5d4ec05701e41517762814f9e7207d5956394496a00c839f0b41596d020681` |
| `rows/t5.sh` | `31572a360b1db5a2e7c39845421f80d6d66b4293d715b803b30f15de44ffe555` |
| `rows/t6.sh` | `ebc9700c8968b633990e0a198027bbfb5d6a246e3828e696cf8a5467b36d3400` |
| `rows/t7-ditto.sh` | `23ea0b99fa9f3e7eccbe429e42d51a9b2c68d9cc2d0b4c641a0ab7b306cc74e0` |
| `rows/t7-mongo.sh` | `dd4545c3538a137acfc2a33eb99a749cf037e1ae18242773e4faf963b56d67c7` |
| `rows/t8-a-reboot.sh` | `bb2d76e5ea3630b72fc39810f528766f549d0fc3f97667102874a3c77242a5c3` |
| `rows/t8-b-return.sh` | `f8259e353019bd02e604344292a07208c8b1116098af47b31f90b1a932a097c7` |
| `rows/t8-c-snapshot.sh` | `9a60f8d6f75b99a573c91f5353a8b8963c641000974389ffd7867ce2477e73a2` |
| `rows/t8-d-smoke.sh` | `f541f1caf33787327fe2d437da9c4994e540ce1346aa2987aca89a19e5514d53` |
| `rows/t9-a.sh` | `3ff287632ab2ca135e59c221c748d88339e5d8c11b07fce4e0c776ab666b5869` |
| `rows/t9-b.sh` | `d6d86b2599dbef67ba3d15501f21944bd638272f4080be68b46f2996dea93c8e` |
| `rows/t9-c.sh` | `9a3ae72b023c73ffa165451d34ec3095592c048b3dce3e335dddbd063d7632b7` |
| `rows/t9-de.sh` | `4ad835244e065df402034f3f552938ce2e7b7c50a43f776db4b4c06078c2b6ae` |
| `rows/t9-exposure.sh` | `484f3fdf6a753d4eaae35be9a0538af9c7e51e64088ee0946a848b2f34c76f85` |

Verification (verification/): three independent verifications (row text identity; the steps script against the
frozen interfaces with a stub dry run; safety and packet fidelity), the corrections (fix-notes.md and the diffs)
and one recheck. Two material defects were found in the first version of the steps script and corrected (a
process listing that showed the simulator password; two concurrent 'row' invocations both running the row);
eight minor ones corrected. bench-records/ holds the isolated stub-bench consoles. Nothing in the steps script
or the row files has run against the guest: the battery is their first real use.

Choices made in preparation, for Rui's information: T9's exposure check offers the campaign key to root
(a stronger test of the refusal: only 'Permission denied' counts); the steps script records every halt and
refuses the next row, and S2, until Rui's words are given to it; 'close' with no QEMU process left runs the
frozen close driver so that the session attempt is exported as it stands.
