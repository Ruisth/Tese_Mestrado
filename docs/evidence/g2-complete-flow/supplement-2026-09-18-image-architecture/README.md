# Supplement — image architecture recorded on 2026-09-18

**Record of this supplement: 2026-09-21.** It publishes an older, already sealed
package so that the architecture of the five external images used in the G2
session of 2026-09-20 can be read from evidence instead of assumed. It accepts
no gate, admits no claim and closes nothing: G2 stays `Not decided` until a
decision is recorded in `docs/governance/gate_decision_log.md`.

## What is published here, and from where

This directory is a byte-for-byte copy of the local package

`output_test/runs/2026-09-18/HIST_2026-09-18-stack-images-provisioning`

which is itself the preserved copy of the guest candidate directory
`/home/ruisth/yocto/evidence-candidates/2026-09-18-stack-images-provisioning`,
exported on 2026-09-19 at 19:28:46 UTC by `egw_experiments.local_export`. All 32
files of that package are here with their original names, bytes and dates, and
at the exact relative paths its own seals record, so that both seals still
verify where they stand: the package seal [`SHA256SUMS`](SHA256SUMS) (31
entries) and the inner seal of the captured guest directory
[`raw/2026-09-18-stack-images-provisioning/SHA256SUMS`](raw/2026-09-18-stack-images-provisioning/SHA256SUMS)
(25 entries), 56 entries in all. Every file the two seals list is present, and
every copied file is covered by one of them; no checksum file was copied without
the files it names. Nothing in the copy was edited, renamed or re-sealed, so the
package still says of itself what it said where it was written — including, in
[`SUMMARY.md`](SUMMARY.md), that it is a local copy, candidate evidence, not
admitted. That sentence is sealed inside the package and is therefore not edited
here; as with the seven attempt packages of this capsule, the first half of it
is no longer true of the copy in this directory, and the second half still is.

This `README.md` is the only file of the supplement that the historical package
did not contain. It is covered by the capsule's outer `SHA256SUMS`, not by the
package's own seals, which remain exactly as they were written. The package's
`export_manifest.json` lists each copied file with its source path and SHA-256,
and records `excluded: []` and no missing source.

## This is evidence of 2026-09-18, not of the G2 session

The observations below were recorded on **2026-09-18**, during the provisioning
of the stack images: the five pinned external images were pulled inside the
emulated ARM64 guest and inspected there. **Nothing was started** in that
session, and it is not part of the G2 session of 2026-09-20 archived in the
seven attempt packages of this capsule.

**The architecture fields were therefore not captured during the G2 session.**
The G2 gate snapshot
[`../20260920T232447Z_g2-gate-preconditions_attempt01/environment/container_identities.txt`](../20260920T232447Z_g2-gate-preconditions_attempt01/environment/container_identities.txt)
records, for each of the five registry images, the pinned reference, the full
image id and the repository digest, but no `arch` or `os` field. What joins the
two records is the full image id: a content identifier of one image
configuration. Where the id recorded on 2026-09-18 and the id recorded during
the G2 session are the same string, the two sessions used the same image, and
the architecture read on 2026-09-18 is the architecture of that image.

The five pinned digests are multi-architecture indexes, so a digest alone does
not say which image the guest resolved; that is precisely why the full image ids
are compared here. The historical record also notes that the engine reports the
manifest-list digest only, so the arm64 child digests named in
`src/deployment/images.lock.env` were not observed on either date.

## The evidence cited, and the chronology around it

The architecture fields come from

[`raw/2026-09-18-stack-images-provisioning/guest/image-identities.txt`](raw/2026-09-18-stack-images-provisioning/guest/image-identities.txt)

**SHA-256** `7419ce9445213bc42bc25becca7a26d0ff8ed458e21fb15d5139b88a56bd332f`,
timestamped **2026-09-18 17:01:19 UTC** in its own first line and ending
`IDENTITY RESULT: failed_checks=0` over 20 checks — presence, architecture,
operating system and pinned digest for each of the five images.

That is the second of the two guest sessions the package holds, and the package
holds both:

| Session | Guest booted (UTC) | What the driver recorded |
|---|---|---|
| `images-boot-01` | 2026-09-18 16:57:16 | the pulls, in `raw/2026-09-18-stack-images-provisioning/guest/pull-pinned-images.txt`, ending `PULL RESULT: failed_checks=9`; session exit 1 |
| `images-boot-02` | 2026-09-18 17:00:46 | the identity check, in `raw/2026-09-18-stack-images-provisioning/guest/image-identities.txt`, ending `IDENTITY RESULT: failed_checks=0`; session exit 0 |

The earlier transcript is kept and is not read here as a pass. Its nine failed
checks are a defect of the check script, not of the images: the template asked
`docker image inspect` for `.Variant`, a field the three Ditto image
configurations do not carry, so the template failed and those three images were
reported absent although their `Digest:` and `Status: Downloaded newer image`
lines stand in the same transcript. The identities were then recorded again, in
the second session, with a corrected template. The architecture statement below
rests on `image-identities.txt` alone; the failed first check is named so that
the sequence stays visible, not to be counted as evidence of success.

The sealed G1 build artefacts read back `OK` after both sessions
(`g1-after-images-boot-01.sha256check.txt`,
`g1-after-images-boot-02.sha256check.txt`).

## The five-image crosswalk

Built by reading both files and comparing their fields, not by copying any
earlier table. The fourth column is the repository digest as recorded on
2026-09-18; it is the same string in the G2 gate snapshot for all five images.

| Image | Full image id recorded on 2026-09-18 | Platform recorded on 2026-09-18 | Repository digest | Image id recorded in the G2 gate snapshot |
|---|---|---|---|---|
| Mosquitto — `docker.io/library/eclipse-mosquitto:2.0.22` | `sha256:5fef2509a20f85341b1e5c4dd7864e1a4a15fba155b88afa025cbcd5b5611ce9` | `linux/arm64` (`arch=arm64 os=linux`) | `eclipse-mosquitto@sha256:212f89e1eaeb2c322d6441b64396e3346026674db8fa9c27beac293405c32b3c` | `sha256:5fef2509a20f85341b1e5c4dd7864e1a4a15fba155b88afa025cbcd5b5611ce9` |
| MongoDB — `docker.io/library/mongo:7.0.39` | `sha256:d58a07b4b2ecaff800c05ed786685d18dcbb5b31a801fdc57bdfb819a9f46c8f` | `linux/arm64` (`arch=arm64 os=linux`) | `mongo@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d` | `sha256:d58a07b4b2ecaff800c05ed786685d18dcbb5b31a801fdc57bdfb819a9f46c8f` |
| Ditto policies — `docker.io/eclipse/ditto-policies:3.9.4` | `sha256:0e93f53bed2734b7ef83a59054b61077612cc40bbe47c4b6753d12eaefa3e99c` | `linux/arm64` (`arch=arm64 os=linux`) | `eclipse/ditto-policies@sha256:652f75b9accfc1da8cbc228bcede0f7778e732b9625225dafad4a2930903d4bb` | `sha256:0e93f53bed2734b7ef83a59054b61077612cc40bbe47c4b6753d12eaefa3e99c` |
| Ditto things — `docker.io/eclipse/ditto-things:3.9.4` | `sha256:38fef6b7598be0513532c227271c124437a54eb759c2a05f34305832d91b7122` | `linux/arm64` (`arch=arm64 os=linux`) | `eclipse/ditto-things@sha256:a1cc8a12d167ae5a22a31c9163913736ca14dcef4b544e6270265965089247b0` | `sha256:38fef6b7598be0513532c227271c124437a54eb759c2a05f34305832d91b7122` |
| Ditto gateway — `docker.io/eclipse/ditto-gateway:3.9.4` | `sha256:aeb24de31e2de444e767afe7bfbb8a70928c0527d8e6736bcb4813a5407fec7a` | `linux/arm64` (`arch=arm64 os=linux`) | `eclipse/ditto-gateway@sha256:fc9102b5ed18e5ee402fd5a1a023c5d93c215dce6fd3f24d7efb4a9f6e08682b` | `sha256:aeb24de31e2de444e767afe7bfbb8a70928c0527d8e6736bcb4813a5407fec7a` |

**All five rows match**: for each image the full image id is the same string in
the two records, the repository digest is the same string, and the pinned
reference — repository, tag and digest — is the same. The G2 snapshot carries a
sixth identity, the locally built controller `egw-controller:0.1.0`; it is not a
registry image, it is outside these five, and its own `image_architecture=arm64`
and `image_os=linux` are recorded in that snapshot itself.

## What this supplement establishes, and what it does not

It establishes that the five external images carrying the pinned digests were
`linux/arm64` when they were inspected on 2026-09-18, and that the images
recorded during the G2 session of 2026-09-20 carry the same full image ids and
the same repository digests.

It does not establish that those fields were read during the G2 session: they
were not, and no artefact of the seven G2 attempt packages contains them. It is
a substitute for no G2 observation other than this identity question — no flow,
timing, persistence or health result of 2026-09-20 depends on it, and none is
imported from 2026-09-18. It says nothing about the locally built controller
image beyond what the G2 snapshot already records. If a later candidate changes
any of the five images, this bridge must be reassessed for that image, because
it holds only for these exact ids.

Nothing here is a performance result: both sessions ran on an ARM64 guest
**emulated** under QEMU/TCG.
