# Pinned external images pulled inside the guest — candidate evidence

- Date: 2026-09-18, 16:57 to 17:01 UTC. ARM64 guest **emulated** under QEMU/TCG on the x86-64 WSL2 host: functional evidence only. Candidate evidence, not sealed; no gate, no claim.
- Scope: step one of the first end-to-end functional test authorised on 2026-09-18. The five external images of the stack were pulled **by the digests pinned in `src/deployment/images.lock.env`** (`dev` at `0e536cd`) through QEMU's user-mode network. **Nothing was started**; the controller image is built separately on the provisioning host and is not part of this record.
- Clone at `3209b17` (clean); same root file system image and data disk as the earlier records of the day; strict SSH host-key checking.

| Variable | Image id | Pull time |
|---|---|---|
| `IMAGE_MOSQUITTO` `eclipse-mosquitto:2.0.22@sha256:212f89e1…2b3c` | `sha256:5fef2509a20f85341b1e5c4dd7864e1a4a15fba155b88afa025cbcd5b5611ce9` | 6 s |
| `IMAGE_MONGODB` `mongo:7.0.39@sha256:35a5926f…415d` | `sha256:d58a07b4b2ecaff800c05ed786685d18dcbb5b31a801fdc57bdfb819a9f46c8f` | already present (isolated test of the same day) |
| `IMAGE_DITTO_POLICIES` `eclipse/ditto-policies:3.9.4@sha256:652f75b9…d4bb` | `sha256:0e93f53bed2734b7ef83a59054b61077612cc40bbe47c4b6753d12eaefa3e99c` | 71 s |
| `IMAGE_DITTO_THINGS` `eclipse/ditto-things:3.9.4@sha256:a1cc8a12…47b0` | `sha256:38fef6b7598be0513532c227271c124437a54eb759c2a05f34305832d91b7122` | 15 s |
| `IMAGE_DITTO_GATEWAY` `eclipse/ditto-gateway:3.9.4@sha256:fc9102b5…682b` | `sha256:aeb24de31e2de444e767afe7bfbb8a70928c0527d8e6736bcb4813a5407fec7a` | 15 s |

Every image reports `arm64`, `linux` and a `RepoDigests` entry equal to its pin (`guest/image-identities.txt`: 20 checks, none failed).

**About `guest/pull-pinned-images.txt` (first session, 9 failed checks):** every pull in it succeeded — the `Digest:` and `Status: Downloaded newer image` lines are there — but the check script asked `docker image inspect` for the field `.Variant`, which the Ditto image configurations do not carry, so the template failed and the three Ditto images were reported as absent. That is a defect of the check script, not of the images; the transcript is kept as it was written, and the identities were recorded again in a second session with a correct template.

The sealed G1 build artefacts are unchanged after both sessions (`g1-after-images-boot-0{1,2}.sha256check.txt`). The arm64 child digests named in `images.lock.env` were not observed: the engine reports the manifest-list digest only.
