# G3, session S3 (tests 8 and 9): host preparation (sealed 2026-10-05T09:53:26Z)

Authority: the decision summary of 2026-10-04 (output_test/decisions/2026-10-04_g3-t8-t9-s3-decision-summary.md)
on the request of the same date (2026-10-04_g3-t8-t9-session-request.md). This package authorises nothing and is
not a G3 result: session S3 starts only on Rui's explicit authorisation and his go in the attended window.
The host-preparation script starts no guest and does not touch the controller image, the guest deployment or
the data disk.

## Part 1 - identities and freshness (part1-record/console.txt)

Outcome line of the record: `outcome=prepared (at 2026-10-05T08:41:28.481Z)`. STOP lines in the record: 0.
Lines of the record, verbatim (the HEAD= line that carries tree= is the clone after the checkout):

    HEAD=80e833f44f647fe9cd8f5e99d3abf3c444de95aa branch=(detached)
    FETCH_HEAD=8e492613d36490a560ae56beabd6d5c2c01a8696
    HEAD=8e492613d36490a560ae56beabd6d5c2c01a8696 tree=2f0514837f267d8975f7071041aad14a5c18dcab
    runbook: 4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db  /home/ruisth/egw-exec/repo/docs/setup/qemu_integrated_gateway.md
    repo_identity: {"repo_commit": "8e492613d36490a560ae56beabd6d5c2c01a8696", "repo_dirty_lines": 0, "export_tool_sha256": "544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b", "drivers_sha256": "4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5"}
    yocto checkout (launcher): 489bc9e5b5b0660026ea2630b8d1d124049ba2ce, porcelain lines: 0
    run-qemu-integrated: 67da61d77a2548122afc34338493165290f6d1ac1dbc2ebccfd6d800dd0438e1  /home/ruisth/yocto/egw/src/yocto/scripts/run-qemu-integrated.sh
    kernel: 4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/Image-qemuarm64.bin
    qemuboot.conf: 7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf
    qemu-system-aarch64: 5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64
    rootfs-ext4: 22e9da8533541582a2e4549f4c37f2b80f0f6a9bd3a5f0dd5e13605d7269efcd  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
    runbook:  /home/ruisth/egw-exec/repo/docs/setup/qemu_integrated_gateway.md
    helper sha256=e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb lines=545
    row t8: 20261003T142310Z_g3-qualification-t8_attempt01 found 2 time(s), no other attempt of the slug (no attempt02): the new attempt is expected as attempt02
    row t9: no attempt of the slug: the new attempt is expected as attempt01
    rootfs-ext4-after-listing: 22e9da8533541582a2e4549f4c37f2b80f0f6a9bd3a5f0dd5e13605d7269efcd  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4

Identifiers reported fresh on the host: 5; on the guest root file system
(read offline with debugfs -c): 5.

## Part 2 - the row files, the operator's steps script and the session tools

| File | sha256 |
|---|---|
| `g3_battery.sh` | `a77bd201a54d02620e625a620d2da796a8834289ec67daa808ed15324950f5cb` |
| `g3_battery.README.md` | `0c4bf2f81934eefeb1c6a07434c75918c0a5a0b2688c1cbf6d9039172f452a86` |
| `operator-procedure.md` | `5fb9a13a41388efd6a842a1bda9e0b49311ab4f3cdccc4403fd78bedce5b82ed` |
| `rows/rows.manifest.json` | `678b92031e09213780bc3790be1473358746693fc1d86088891ff2697f340c5d` |
| `g3_extract_rows.py` | `11c19af75faf43994c6f68f1ca7b6bdfc1aa7c0e56e1939b7c8dc52173604598` |
| `g3_check_rows.sh` | `2f1863b0f3b85f7ab2b8db65745f2d7a5d802ed0031fbcdb94e5cd666b64b11d` |
| `g3_rows_dryrun.sh` | `fbbca2f638f8a7b7364efcdd7756203504227c989708874c570c5339c48503e3` |
| `g3_hostprep.sh` | `6613f15286f272150cdfba9fa508fadf2f89762ac795686218c143f079d7570e` |
| `seal_prep.sh` | `1a51ab3471fc77094a068e6d8f4b43960a78d0d69c0bb3c10d9020b27bfb457c` |
| `ops/g3_go.sh` | `83950a9f532d84ab1057234062e1be882cbd62dda88e4a385603eee0529c0716` |
| `ops/g3_wait.sh` | `b1324eff4ca16692c61fd43961a4f628757be115d75ccbc23a55e7250d4afbaf` |
| `ops/seal_ops.sh` | `5429aacea1abf854002278bf666e5e4bca153f114a6e713b9183f8ed73a31691` |
| `ops/seal_ops_finish.sh` | `04cb1a4f32fa3592dc169c076c2e9619e00e6e9239ee212cee4d414f61b710cd` |

Step files (rows/; rows.manifest.json and verification/rows-notes.md say how each was made from the runbook
blob 4acf8de6... of 8e49261 and checked; the identifiers carry the suffix -q2):

| Step file | sha256 |
|---|---|
| `rows/t8-a-reboot.sh` | `00ff23db999e4ad5460c93010721e393d60c34fd4e596666cef9fd35fda8aa43` |
| `rows/t8-b-wait-boot-id.sh` | `f38f7fad40980359b6f3ea59142f8a2f0199a3d80a942e7b36826ddfdd9cade7` |
| `rows/t8-c-unaided.sh` | `df4ff611057b4f5a7df40b8b8f0fb2818eed43011c2c10109d7cc0881a7da39d` |
| `rows/t8-d-tunnel.sh` | `dbffd3defbdfbbadce3218bde6c4562d77b0e1813bd70a0562e6f921844809f5` |
| `rows/t8-e-state.sh` | `00d100f7232b93fe5e425f603b7915514b24e67258b692603fa335b99293f593` |
| `rows/t8-f-smoke.sh` | `874ef658228e30e19b561a6f5306b698e0665f3701c2fb28ab0d13feddb6dc76` |
| `rows/t9-a.sh` | `34be9077366b587ae976db89e7aaaeda2bcdbcf8d3976af8254d5a5219169dac` |
| `rows/t9-b.sh` | `29e7e98099e9bb30c58c4b141b87b4bf886ccd082a42da31a0c3b8656a4c4d5b` |
| `rows/t9-c.sh` | `e95f9f153a766f0ab0f21fefb4b93e0893578be80d863b411c1dfc1f64fbbf43` |
| `rows/t9-de.sh` | `4ad835244e065df402034f3f552938ce2e7b7c50a43f776db4b4c06078c2b6ae` |
| `rows/t9-exposure.sh` | `ec18b22a643203a1c2d9bc9a9519b5b4a6f69de65df9944d832f09744428fe9c` |

verification/: the notes of the preparation (what changed in each script and why, what was benched and what
was not) and diffs/, each revised file against the copy its revision started from (the scripts sealed in the
first preparation's package; the four ops scripts as sealed in S2's operator records; seal_prep.sh as the first
preparation used it, never sealed; for g3_battery.sh and its README, the draft of 2026-10-03). The folders named *-record/ and
bench/ hold the consoles of the extraction, of the checks and of the stub benches; ops/ holds the launcher,
the waiter and the two scripts that seal the operator records after the session. prep_brief.md is the brief
the scripts were revised to. Of the preparation folder, not copied: operator-procedure.battery.md base (base/ holds the copies
the diffs were made against; the battery's operator procedure is sealed in the first preparation's package).
The steps script's flow for the corrected test 8 and that test's corrected lines ran against stubs only:
S3 is their first use on the guest.
