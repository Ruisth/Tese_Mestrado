# G3, session S4 (test 6 only): host preparation (sealed 2026-10-05T20:33:11Z)

Authority: the request of 2026-10-05 (output_test/decisions/2026-10-05_g3-t6-session-request.md), made on the
Project Manager's register entry of 2026-10-05 after the merges of pull requests #55, #56 and #57. This package
authorises nothing and is not a G3 result: session S4 starts only on Rui's explicit authorisation and his go in
the attended window. The host-preparation script starts no guest and does not touch the controller image, the
guest deployment or the data disk; besides the execution clone and the helper file, the one file it changes is
the pilot plan, by the merged plan-supplement (entry controller_restart-r04; the predecessor is kept in
part1-record/ when this record added the entry).

## Part 1 - identities, freshness and the plan entry (part1-record/console.txt)

Outcome line of the record: `outcome=prepared (at 2026-10-05T20:19:25.832Z)`. STOP lines in the record: 0.
Lines of the record, verbatim (the first HEAD= line is the clone before the fetch, the one that carries tree= right
after it the clone after the checkout, the last one the clone at the end):

    HEAD=8e492613d36490a560ae56beabd6d5c2c01a8696 branch=(detached)
    FETCH_HEAD=1fd9792bb76f02c6948f33887207dba4837202db
    HEAD=1fd9792bb76f02c6948f33887207dba4837202db tree=14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec
    runbook: 317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f  /home/ruisth/egw-exec/repo/docs/setup/qemu_integrated_gateway.md
    collector: 9e678b024bde66bacc65fea936d05ca226a82e73c86d1cc23a9cf9f8fe8d9b97  /home/ruisth/egw-exec/repo/src/deployment/scripts/collect-resources.sh
    deployment trees: e056d389f7dd640c142bf714bb8ceb389ec460c2 (candidate) and 573e902b67339a3e6bfc784321dc2735cece09fc (clone) differ in: README.md scripts/collect-resources.sh 
    repo_identity: {"repo_commit": "1fd9792bb76f02c6948f33887207dba4837202db", "repo_dirty_lines": 0, "export_tool_sha256": "544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b", "drivers_sha256": "2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed"}
    yocto checkout (launcher): 489bc9e5b5b0660026ea2630b8d1d124049ba2ce, porcelain lines: 0
    run-qemu-integrated: 67da61d77a2548122afc34338493165290f6d1ac1dbc2ebccfd6d800dd0438e1  /home/ruisth/yocto/egw/src/yocto/scripts/run-qemu-integrated.sh
    kernel: 4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/Image-qemuarm64.bin
    qemuboot.conf: 7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf
    qemu-system-aarch64: 5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64
    rootfs-ext4: 6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
    runbook:  /home/ruisth/egw-exec/repo/docs/setup/qemu_integrated_gateway.md
    helper sha256=e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb lines=545
    row t6: 20261003T132936Z_g3-qualification-t6_attempt01 found 2 time(s), no other attempt of the slug (no attempt02): the new attempt is expected as ..._g3-qualification-t6_attempt02
    rootfs-ext4-before-listing: 6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
    rootfs-ext4-after-listing: 6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4  /home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
    data disk size: 34359738368 B
    data disk header: Last mounted on:          /var/lib/docker
    data disk header: Filesystem features:      has_journal ext_attr resize_inode dir_index filetype extent 64bit flex_bg sparse_super large_file huge_file dir_nlink extra_isize metadata_csum
    data disk header: Filesystem state:         clean
    data disk header: Last mount time:          Mon Oct  5 12:54:33 2026
    data disk header: Maximum mount count:      -1
    data disk header: Journal features:         journal_incompat_revoke journal_64bit journal_checksum_v3
    plan before: c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60  /home/ruisth/egw-tcg/pilot/campaign_plan.json
    plan predecessor kept in the record: campaign_plan.predecessor.json, sha256 c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60
    added controller_restart-r04 (supplement g3-t6: condition controller_restart, repetition 4, seed 1715385812, order 96) to /home/ruisth/egw-tcg/pilot/campaign_plan.json; every entry it held is unchanged
    plan-supplement exit=0
    plan folder: the same 2 names at its top level before and after
    plan after: 61d55940fcccdb942ff508ab6fc920b0fa163837ef7459438d789a1879b1eaac  /home/ruisth/egw-tcg/pilot/campaign_plan.json
    plan check: the plan up to the comma before its last entry, closed as the predecessor is: sha256 c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60
    plan check: the kept predecessor's first 39404 bytes (all but its closing) are the plan's first 39404 bytes
    plan check: 95 entries before, 96 after
    plan entry {"condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 96, "rate_msg_s": 11.2, "repetition": 4, "run_id": "controller_restart-r04", "runner": "simulator", "scenario": "nominal", "seed": 1715385812, "status": "planned", "supplement": "g3-t6", "warmup_s": 0}
    plan check: OK (96 entries; the first 95 equal to the predecessor's, as JSON and as bytes; the other fields unchanged; the last entry exactly controller_restart-r04, planned)
    HEAD=1fd9792bb76f02c6948f33887207dba4837202db tree=14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec porcelain lines: 0

Identifier reported fresh on the host: 1 line(s); on the guest root file system
(read offline with debugfs -c): 1 line(s).

## Part 2 - the row file, the operator's steps script and the session tools

| File | sha256 |
|---|---|
| `g3_battery.sh` | `7a63b361af2f25bd8ab81101ca10ec79fcb05a6e6f0cf0a70bc2ec63f3f8425c` |
| `g3_battery.README.md` | `0dee7f06be71e30a2ac94989e80435e622ba2a1ef81b4392b3358f436261da3c` |
| `operator-procedure.md` | `8f536620047a5a256af14142d9433df9cca42dc47a68bbd44f946a2c0f23f2a6` |
| `rows/rows.manifest.json` | `7d2a0f0d940c1d2f978a33693869fe4372cf7c63c4592d3d911d1440bdb8fb47` |
| `g3_extract_rows.py` | `e3aa669d38c6320db1bfa853fd25834ac4d848e6fb04c6e9f341fbfd39c23050` |
| `g3_check_rows.sh` | `ae7038d3e046afa921ca7084240388bd8e87fe4c34797b9c750bffedc4d48494` |
| `g3_rows_dryrun.sh` | `1f32c56c32895b5d2cfd466b5e18db8cc3465a295df61085527294f75983c994` |
| `g3_hostprep.sh` | `4a002b8e27030199be3dbb00d612aa7d50cb4fc400c06634a11ccd07d4e68a1b` |
| `seal_prep.sh` | `178e9f42fc9cfe5e23f5bd13d3c1bd2fc34ae4c516367f6a20f67f1723ae622f` |
| `ops/g3_go.sh` | `cb77af8965ba00d844c40328944f3a16d4b5a9ba07b953368bf663f2cfe10625` |
| `ops/g3_wait.sh` | `28dc98ce620b80f677b3e13e20a0292b62419f1a711c5810bebeb290f8ee2415` |
| `ops/seal_ops.sh` | `d8b3de3cff5bfc210f64b4f0eb91d630812194f6e63875d4bf1a8048d4d72044` |
| `ops/seal_ops_finish.sh` | `97f50ceb4ae8e0319e34b6d7c064b88dc40f54b591032ae9083c5edf3b99b51b` |

Step files (rows/; rows.manifest.json and verification/rows-notes.md say how each was made from the runbook
blob 31716593... of 1fd9792, runbook.1fd9792.md here, and checked; no identifier is substituted: controller_restart-r04 is
the runbook's own literal):

| Step file | sha256 |
|---|---|
| `rows/t6.sh` | `ec8ac010d79ba87ff7f2b4c828c4fbe85c7f0c765d6869670552a6c1ba326377` |

verification/: the notes of the preparation (what changed in each script and why, what was benched and what
was not) and diffs/, each revised file against the copy its revision started from (base/: g3_hostprep.sh, the
three row scripts and seal_prep.sh as sealed in HIST_2026-10-05-g3-t8t9-host-preparation; g3_battery.sh, its
README, the operator procedure and the four ops scripts as sealed in
HIST_2026-10-05-g3-t8t9-host-preparation-attempt02, the ones S3's second opening ran). The folders named
*-record/ and bench/ hold the consoles of the extraction, of the checks and of the stub benches; ops/ holds the
launcher, the waiter and the two scripts that seal the operator records after the session. prep_brief.md and
prep_bench_brief.md are the briefs the scripts were revised and benched to. Of the preparation folder, not
copied: base preflight.1fd9792.sh test_runbook_itest_helpers.1fd9792.py (base/ holds the copies the diffs were made against; preflight.1fd9792.sh and
test_runbook_itest_helpers.1fd9792.py are copies of the repository's files at 1fd9792 given for reading; any other
entry named is a working folder of the preparation, not part of it).
Test 6's merged lines and the steps script's t6 path have not run on the guest (what ran against stubs is in
verification/bench-notes.md): S4 is their first use on the guest.
