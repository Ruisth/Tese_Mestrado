# Isolated MongoDB 7 test on the integrated Yocto guest — candidate evidence

- Date: 2026-09-18, 13:50 to 13:54 UTC.
- Question answered: **does MongoDB 7 work on this Yocto image and in this
  emulated profile?** Answer: yes, functionally. This is not a capacity or
  performance statement: the guest is ARM64 **emulated** under QEMU/TCG on an
  x86-64 WSL2 host, and every timing below is informational only.
- Status: candidate evidence, not sealed. No gate is accepted and no claim is
  supported. The six-container stack was **not** deployed; one container of
  one image ran, on a separate test volume, with a test database.
- Authorisation: given by the student on 2026-09-18 after the project review
  recommended it (image identified by digest, separate test storage, no
  external exposure, no reuse of important data).
- Source: clone at commit `3209b17` (clean), the same root file system image
  and data disk as the build-and-boot validation of the same day
  (`../2026-09-18-integrated-3209b17/`). The SSH host key is the one recorded
  there; every connection used strict host-key checking.

## Image identity

| Item | Observed |
|---|---|
| Reference pulled | `docker.io/library/mongo:7.0.39@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d` (the pin of `src/deployment/images.lock.env`) |
| `RepoDigests` | `mongo@sha256:35a5926f…415d` |
| Image id | `sha256:d58a07b4b2ecaff800c05ed786685d18dcbb5b31a801fdc57bdfb819a9f46c8f` |
| Architecture | `arm64`, variant `v8`, `linux`; 828,268,923 bytes |
| Server | `db version v7.0.39`, git `636e201a5c0732b95e88bb011a72938ce01d290b`, WiredTiger, `cpuArch` `aarch64`, 4 cores, memory limit 512 MiB seen by mongod, WiredTiger cache 268,435,456 bytes |

The image was pulled **inside the guest** through QEMU's user-mode network
(65 s). The lock file names the arm64 child manifest
`sha256:640a48a0…d4b5`; the engine reports the index digest only, so the child
digest was not observed.

## What was done (scripts in `scripts/`, transcripts in `guest/`)

Container started as the `mongodb` service of `src/deployment/compose.yaml`
is: `--user mongodb`, `mongod --storageEngine wiredTiger --noscripting`,
512 MiB memory limit, `TZ=UTC`, data on a named volume — here the separate
volume `egw-mongo-test-data` — and **no published port**.

| Step | Result |
|---|---|
| Binary starts on the Cortex-A76 model (`mongod --version`) | v7.0.39, no illegal instruction (the sealed G1 profile used Cortex-A57, which MongoDB 7 does not support) |
| First start | ping answered after 5 s; running, not OOM-killed, no port binding; nothing listens on 27017 in the guest host namespace |
| Write and read | document `doc-1` inserted into `egw_isolated_test.probe` and read back |
| `docker restart` | ping after 14 s; `doc-1` present; `doc-2` inserted |
| Container removed and recreated on the same volume | ping after 12 s; both documents present; first instance had stopped with exit 0 |
| Guest power cycle (clean power-off, second boot) | container still defined and not started by the boot; after `docker start`, ping after 18 s; both documents intact; `doc-3` inserted |
| Logs | `Waiting for connections` in every instance; no fatal assertion, no WiredTiger error |
| End state | container removed; **image and test volume kept** on the data disk |

Checks: 27 passed in phase 1, 8 in phase 2, 0 failed (`guest/phase1.txt`,
`guest/phase2.txt`, lines `CHECK PASS|FAIL`). Memory snapshot while idle:
171.8 MiB of 512 MiB (informational).

The sealed G1 build artefacts are unchanged after this test
(`g1-after-mongo-test.sha256check.txt`).

## Left on the data disk

- Image `mongo@sha256:35a5926f…` (the stack uses the same pin).
- Volume `egw-mongo-test-data` with the three test documents. Remove with
  `docker volume rm egw-mongo-test-data` when it is no longer wanted.
- Two anonymous volumes created for the image's `/data/configdb` declaration
  by the two test containers (`docker rm` without `-v` keeps them); they are
  empty of project data.

## Not shown by this test

Ditto's use of MongoDB, authentication, replica sets, load, soak, behaviour
under memory pressure, native ARM64 hardware, and the MongoDB 8 question
(`docs/adr/0009-mongodb-8-evaluation.md`, proposed, separate decision).
