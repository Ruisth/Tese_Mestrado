# G1 clean-build and strict five-boot evidence

This capsule records a clean-checkout Yocto build and the five strict QEMU
boots required by plan v1.1. It is **functional evidence only**. It supports
statements about the build, boot, systemd, networking and the OCI runtime; it
does not support latency, throughput, resource, security or native-ARM64
claims.

The execution crossed midnight in Europe/Lisbon. The kas logs use local time:
the build ran from 2026-08-13 23:10 to 2026-08-14 00:08. The boot JSON files
retain UTC timestamps from 2026-08-13 23:09 to 23:24, corresponding to
2026-08-14 00:09 to 00:24 in Lisbon. The capsule therefore uses the local date
2026-08-14.

## Build identity and clean-checkout meaning

| Item | Recorded value |
|---|---|
| Source commit used to build the image | `f0e19d5a51b4ade1e0637e6bff135c737996b1ba` |
| Source tree | `ec0299e9d4b4f89828849e4c925bebad96f0c2d7` |
| Driver commit used for the passing campaign | `9fe38ff4ed3c34915f506f1d3b91f3ba56b6df22` |
| Driver tree | `f8155ee9cdaf6de2223935897e960165678c6e0c` |
| Target | `qemuarm64`, `aarch64-poky-linux`, Poky 5.0.19 (Scarthgap) |
| Build result | 5,715 tasks attempted; 2,261 did not need to be rerun; all succeeded |
| Shared-state summary | 2,714 wanted; 1,511 local; 1,203 missed; 55% match |
| Packages | 639 entries in `image-packages.manifest` |
| Warnings | one WSL2/VHDX capacity advisory; no build error |

"Clean checkout" means that the repository checkout, layer directories and
build directory were new. The external downloads and sstate cache under
`~/yocto-cache` were deliberately shared, as specified by the kas manifest.
This was not a cold-cache build, and the evidence makes no such claim. The
checkout was fast-forwarded from the build commit to the driver commit only
after the image had been built, so the two identities are recorded separately.

The pinned layer revisions resolved in `kas-checkout.log` are:

- poky: `bb98354685781296e3b3737e7762412100f359c2`;
- meta-openembedded: `ef3df29f2cfca6a9513b51ebcdccf82b6c8a836f`;
- meta-virtualization: `0d9fb7fef86c5cbc177045c7b86bc71948f8657d`.

## Image artefacts

The multi-gigabyte image and kernel remain in the ext4 build tree and are not
duplicated in Git. Their size and SHA-256 were calculated at the source after
the build and recalculated before sealing this capsule:

| Artefact | Bytes | SHA-256 |
|---|---:|---|
| `egw-image-qemuarm64.rootfs-20260813221142.ext4` | 2,607,275,008 | `6c37fcc10e31702e21ce5d9c73f7cb6aabd4fa512ef50680f8f1434d6a721da0` |
| `Image--6.6.142+git0+4a6f16d14b_1f7f3a52da-r0-qemuarm64-20260813221142.bin` | 24,150,528 | `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037` |

`image-packages.manifest` and `image-qemuboot.conf` are copied into this
capsule. `manifest.json` carries the same build and artefact identities in a
machine-readable form.

## Strict boot campaign

The first run exposed an instrumentation false negative. The guest returned
`STATE=running`, zero failed units, a successful container smoke test and a
clean power-down, but the predicate at the build commit did not accept the
double carriage returns emitted by the PTY. That run remains archived as
`qemu-boot-01` with outcome `fail`; it is not reinterpreted and does not count
among the five required boots. PR #18 corrected only the exact state predicate
and added a regression test before any run was repeated.

The five new identities were then executed by the driver at `9fe38ff4`:

| Boot | Outcome | Required assertions | Observations | Timed out | Console | Clean power-down |
|---|---|---:|---:|---|---|---|
| `qemu-g1r2-01` | pass | 7/7 | 2/2 | none | reached | confirmed |
| `qemu-g1r2-02` | pass | 7/7 | 2/2 | none | reached | confirmed |
| `qemu-g1r2-03` | pass | 7/7 | 2/2 | none | reached | confirmed |
| `qemu-g1r2-04` | pass | 7/7 | 2/2 | none | reached | confirmed |
| `qemu-g1r2-05` | pass | 7/7 | 2/2 | none | reached | confirmed |

For every counted boot, the required assertions establish the pinned guest
release and architecture, exact `systemd=running`, zero failed units,
multi-user target, networking, a live Docker server and the offline OCI
container smoke test. Gateway ping and smoke diagnostics remain supplementary
observations and never decide the outcome. The absolute `console_log` paths in
the JSON files are the original WSL paths; each archived log is matched by the
same basename in this directory.

## Interpretation and gate state

This capsule demonstrates a same-operator clean-checkout build and five strict
functional boots. It does not demonstrate an independent second-operator
reconstruction, which remains decision D006. It also does not replace the five
`qemu_boots` observations defined for the later frozen experimental campaign
unless that protocol is formally amended.

**G1 is not declared accepted here.** Formal gate acceptance remains pending,
and the canonical project state remains 0 of 15 claims accepted. Evidence
production, evidence integrity and gate acceptance are separate decisions.

## Capsule contents and integrity

- `kas-checkout.log` and `kas-build.log`: layer resolution and complete build;
- `qemu-boot-01.*`: preserved instrumentation false negative;
- `qemu-g1r2-01.*` to `qemu-g1r2-05.*`: five counted boots;
- `image-packages.manifest` and `image-qemuboot.conf`: image metadata;
- `environment.txt`: host/tool/filesystem capture;
- `manifest.json`: machine-readable provenance and campaign index;
- `SHA256SUMS`: hashes of every other file in this directory.

The parent evidence directory has a separate historical seal. This nested
capsule has its own non-overlapping `SHA256SUMS`. Verify it from the capsule:

```bash
sha256sum -c SHA256SUMS
```

Repository CI also parses every result JSON and validates every evidence seal.

