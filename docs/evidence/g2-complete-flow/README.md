# G2 complete flow on the integrated guest — capsule of 2026-09-20

**Functional evidence only; sealing is not acceptance.** This capsule archives
what was observed on the night of 2026-09-20 so that it can be verified later.
It accepts no gate, it decides nothing and it supports no performance claim of
the dissertation. The guest is ARM64 **emulated** under QEMU/TCG on an x86-64
WSL2 host, with the load generator on the same machine: every duration, lag and
rate in these files is an observation of an emulated guest and is informational
only, never native ARM64 performance. G2 stays `Not decided` until the decision
is recorded in `docs/governance/gate_decision_log.md`; publishing this capsule
and merging its pull request are not that decision.

## What was recorded, and on what

One guest session of 2026-09-20, 23:17:56 to 23:39:27 UTC: a single boot of the
integrated profile, then six further attempts — two preflights, the single-file
deployment made between them, the gate baseline, the bounded flow and the
restart — and finally a controlled stop and a clean power-off. The
six-container stack was started inside the emulated guest by the **first**
preflight, the one that then failed: its interlock ran `up -d` between 23:18:44
and 23:21:18, and the six containers were created and started there. The seven
packages below — the session package and those six attempts — are the complete
record of that session, including the attempt that failed.

| Item | Observed |
|---|---|
| Host | `Ruisth-Desktop`, WSL2 Ubuntu 24.04 (kernel 6.6.87.2-microsoft-standard-WSL2) on Windows 11 x86-64, 16 host CPUs, 31 GiB memory |
| Emulator | QEMU 8.2.7, TCG, `-machine virt -cpu cortex-a76 -smp 4 -m 8192` |
| Guest | `egw-qemu-integrated`, Poky 5.0.19 (scarthgap), kernel 6.6.142-yocto-standard, aarch64, Docker 25.0.9 with Compose v2.26.0 |
| Kernel `Image` | `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037`, byte-identical to the sealed G1 `Image` |
| Root file system | `20457c74f92adac33ef30029fdd6633c81839dffbaaf95da68ae96a19be6fa8f` before the boot, `ef0813c152dc86b3aa00f418bf76581a60ab244a5128ccc711114603b8265ef3` after the power-off; `runqemu` boots the ext4 file in place, so the change is the expected effect of a writable root file system |
| Sealed G1 artefacts | three artefacts — `Image`, `egw-image-qemuarm64.rootfs.ext4` and `egw-image-qemuarm64.rootfs.manifest` — read back `OK` after the session (`20260920T231756Z_guest-session_attempt02/g1-after-s1.sha256check.txt`). The reference values come from `docs/evidence/integrated-qemu/2026-09-18-build-boot/2026-09-18-integrated-68f9ae7/g1-deploy-before.sha256`, written on 2026-09-18 before the integrated build: for the kernel and the package manifest that chain reaches the sealed G1 capsule, and for the root file system it reaches that 2026-09-18 record, not the G1 capsule itself |

## Identities of what ran

| Item | Observed |
|---|---|
| Execution clone (the drivers) | commit `b7e0c83c3277f7469c05336f91949e7d1b89489a` of `feat/g2-session-drivers`. Six of the seven attempts record that commit with `repo_dirty_lines: 0`, read by the drivers themselves; the seventh, the single-file deployment, carries identities the developer wrote by hand and records the commit without a dirty-line count |
| Driver set | `drivers_sha256: e1c26c66628ebb959ee1a8b3238be799873042014f2ee2a96b831d6e32e9ee3f` |
| Export tool | `export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b` |
| Operating-system build source | Yocto checkout, launcher and kas at commit `8e886700f2b41676a6514d561d548763f52efed2` of `deploy/itests2`, clean |
| Broker | `eclipse-mosquitto:2.0.22@sha256:212f89e1…32b3c` |
| Database | `mongo:7.0.39@sha256:35a5926f…3415d` |
| Digital twin | `eclipse/ditto-policies`, `ditto-things` and `ditto-gateway` `3.9.4`, each by image digest |
| Controller | `egw-controller:0.1.0`, image id `sha256:2e30d8fcf921828b7564305a06240e2de79679920c06c4f3a1bfa9f3ec1c7f21`, built from source commit `0dfa53140996dfb1b95b9cb3a8d5721e85e4d4d9` on a clean `src/` tree, base `python:3.12.13-slim@sha256:229a2c5b…0d36` |
| Publishing path | broker listener 8883 with `cafile`, `certfile` and `keyfile`, `tls_version tlsv1.2`, `allow_anonymous false`, development CA `AA:34:ED:1E:B4:15:2D:1A:F3:A5:B1:9C:89:37:C6:C1:F9:00:E5:A6:CB:56:C4:BD:5B:E3:A2:A1:B0:B3:E6:DF`, private material mode 600 |

Unlike the session of 2026-09-19, the drivers that ran are the versioned ones:
the execution clone was clean at `b7e0c83`, so what ran is what the repository
holds.

## The seven packages

Each directory is one attempt, exported as it was produced, with its own
`SUMMARY.md`, `attempt.json`, `commands.jsonl`, full `console/` capture,
`export_manifest.json` and its own inner `SHA256SUMS`.

| Package | Driver exit | What it holds |
|---|---|---|
<!-- The driver exit is the status the driver printed on the operator's terminal and is NOT held in the capsule: the packages record each command's own exit code in commands.jsonl and each attempt's verdicts in attempt.json. It is repeated here only to say how each attempt ended. -->
| [`20260920T231756Z_guest-session_attempt02/`](20260920T231756Z_guest-session_attempt02/SUMMARY.md) | 0 | the session itself: the identities recorded before the boot, the boot, the guest state after it, the controlled stop of the stack, the power-off and the check of the sealed G1 artefacts afterwards. The other six packages reference this session |
| [`20260920T231844Z_live-preflight_attempt02/`](20260920T231844Z_live-preflight_attempt02/SUMMARY.md) | 2 | **failed and kept.** The two-directional comparison of the deployed tree with the clean clone found `scripts/fetch-collector-output.sh` present in the clone and absent on the guest, so the preflight stopped before its remaining eleven checks |
| [`20260920T232205Z_deploy-the-clone-fetch-helper_attempt01/`](20260920T232205Z_deploy-the-clone-fetch-helper_attempt01/SUMMARY.md) | 0 | that one file deployed, in a single command whose argv the package seals: the session's own `gscp` helper copied `src/deployment/scripts/fetch-collector-output.sh` from the execution clone to `/tmp/fetch-collector-output.sh` on the guest; `gssh` then ran `sudo cp` of it into `/opt/egw/deployment/scripts/`, `sudo chmod 0755`, and `sha256sum` over the two guest paths. This was a bounded single-file deployment made by the developer between the two preflight attempts — **not** the runbook's deployment step. The two hashes the attempt holds are both hashes **on the guest**, `9ae07b0c5e4b03385053d270e379b0bf767f34156839ad2c7a53a9aee2f3c7d4` for `/tmp/fetch-collector-output.sh` and the same value for `/opt/egw/deployment/scripts/fetch-collector-output.sh`: they show that the copy which arrived equals the file that was installed. The clone-side hash was printed outside the attempt and is not in this capsule |
| [`20260920T232219Z_live-preflight_attempt03/`](20260920T232219Z_live-preflight_attempt03/SUMMARY.md) | 0 | the preflight repeated and complete: the interlock ran again and its `up -d` found all six containers already `Running` — the stack itself had been started in `attempt02` above — the clone's resource collector deployed and checked live (46 samples, 45 distinct instants over a 45 s window, no gap), and the deployed tree equal to the clone in 19 of the 20 files it lists, the twentieth being `README.md`, which differs and is the one allowed difference |
| [`20260920T232447Z_g2-gate-preconditions_attempt01/`](20260920T232447Z_g2-gate-preconditions_attempt01/SUMMARY.md) | 0 | the gate baseline, read only: the six expected services running **and** healthy, `/health` 200 `ok`, `/ready` 200, `/metrics` 200 with every counter and `queue_depth` at 0 for the controller process started at 2026-09-20T23:21:31.554Z, the six container identities, the controller build identity and the broker's TLS configuration |
| [`20260920T232527Z_smartwatch-slice-1-hz-60-s_attempt02/`](20260920T232527Z_smartwatch-slice-1-hz-60-s_attempt02/SUMMARY.md) | 0 | one smartwatch at 1 Hz for 60 s, run id `itest-g2-01`, seed `20260921`: 60 sent valid, 60 delivered unique, 0 lost, 0 late, 0 double accepted, 0 intended-invalid accepted, deadline source `controller-marker`, marker lag 0.184 s. The twin `org.c2dta:62da1188-4cd1-434b-a9c7-236a8c211f84` did not exist before and came out with `last_run_id itest-g2-01`, `last_seq 59`, `accepted_count 60`; `/metrics` moved `accepted` and `received` from 0 to 60 with every other counter and `queue_depth` at 0 |
| [`20260920T233212Z_g2-twin-persistence-restart_attempt01/`](20260920T233212Z_g2-twin-persistence-restart_attempt01/SUMMARY.md) | 0 | persistence with nothing in flight: quiesced, state recorded, `compose down` then `up -d` with no volume removed, the restart shown (controller `started_at` 23:21:31.554Z then 23:37:38.535Z, and all six containers new objects started later), the six containers healthy again at sample 2 of the poll that followed, readiness re-checked by `wait_ready`, which exited 0 — **that exit status is the whole of the evidence for the readiness half**, because the helper prints nothing when it succeeds and both console files of that command are empty — and the same twin read back from the volumes with `last_run_id itest-g2-01`, `last_seq 59`, `accepted_count 60`. The run's event log holds 60 records before and 60 after |

## Why a failed attempt is kept here

`20260920T231844Z_live-preflight_attempt02/` exited 2 and is part of the record,
not an embarrassment to be tidied away. It shows three things a capsule of only
successful attempts could not: that the preflight is a real check and refuses to
continue when the guest and the clone disagree; that the disagreement was one
missing file, found by comparing in both directions rather than one; and that
the repair was a bounded single-file deployment, made by the developer between
the two preflight attempts and re-checked on the guest, so the successful
preflight that follows it is not a second opinion but the same check passing
after a change that is itself on the record. Failed and inconclusive attempts
stay next to the successful ones throughout this repository.

## What this capsule does not show

One device, 60 messages, 60 seconds, one run: nothing here is a capacity,
throughput, latency or soak result, and no threshold of a later gate is met by
it. The restart is a `compose down` and `up -d` of the stack, not a power cycle
of the guest. The controller's `/metrics` counters are per process and start
again at 0 after the restart, which is expected of a process counter and is not
loss; persistence is shown by the twin and the event log, not by those counters.
Controller throughput, backlog behaviour and in-flight recovery remain open, as
does any measurement on native ARM64 hardware.

## Three things to read carefully in this capsule

1. **Each package says of itself that it is "a local copy ... not published or
   admitted evidence".** That sentence was written by the export tool, and was
   true of the copy it wrote under the student's `output_test` folder. It is
   sealed inside each package and is therefore not edited here. Of the copy in
   this directory it is no longer true in its first half — this is the published
   copy — and still true in its second: publishing a capsule admits nothing, and
   G2 stays `Not decided` until a decision is recorded.
2. **"The complete record of that session" means the complete record of what the
   attempts captured.** One action of that session, the developer's own reading
   of the execution clone's copy of the deployed file, was printed on his
   terminal outside any attempt and is not here. Where this capsule says what an
   attempt holds, it holds it; where the narrative names something outside the
   attempts, it says so in that sentence.
3. **The "driver exit" column is not a sealed figure.** It is the status each
   driver printed for the operator. What the packages hold is each command's own
   exit code in `commands.jsonl` and each attempt's three verdicts in
   `attempt.json`.

## Verification, secrets and layout

`SHA256SUMS` in this directory lists every file of the capsule except itself,
including each package's own inner `SHA256SUMS`, and every seal below
`docs/evidence/` is read by `python tools/ci/verify_evidence.py` in continuous
integration (job *contracts, evidence and links*). What that check establishes
runs in one direction only: every entry a seal lists exists and hashes as the
seal records it. It does not walk the tree against the seals, so it cannot
report a file that is present here and covered by no seal; the completeness of
the listing was settled when the seal was written, not by the check. The seven
directories keep the names the export produced and are byte-for-byte copies of
the local packages under `output_test/runs/2026-09-20/`, which remains a local
copy and not admitted evidence; `.gitattributes` stores everything here without
text conversion, because three captured files carry the carriage returns of the
pseudo-terminal and those bytes are part of the record. The shell scripts and
Python drivers kept inside the session package are captured material, sealed and
not linted.

No private key, password file, certificate private material or large binary is
stored here. Two different things support that sentence, and only one of them
is recorded inside the capsule.

What the capsule itself records is in the seven `export_manifest.json` files.
Each export searched every file it copied — 240 files across the seven
packages, the remaining 21 being the `SUMMARY.md`, `export_manifest.json` and
`SHA256SUMS` the export writes itself — for the literal values of four named
variables, `DITTO_DEVOPS_PASSWORD`, `EGW_MQTT_PASSWORD`,
`MOSQUITTO_CONTROLLER_PASSWORD` and `MOSQUITTO_SIMULATOR_PASSWORD` — the Ditto
devops password, the gateway's own broker password and the two broker account
passwords — and for PEM private-key blocks. Each manifest records `excluded:
[]`, so nothing was held back from the copy on those grounds, and 0 expected
sources missing. That is the whole of the scan this capsule attests, and it is
narrower than the sweep described next.

Separately, before publishing, the developer swept the sealed tree himself:
all 261 files below the seven package directories, against every variable that
carries a value in the operating environment file of the execution host (those
empty there have no value to search for), and against PEM private-key and
OpenSSH private-key blocks, mosquitto password hashes, bearer and
basic-authorisation values and URLs carrying inline credentials. He found none
of them, and the four credential-carrying variables appear in no file.
**No artefact of this capsule records that sweep**: its output was not kept
here and nothing sealed below confirms it, so it is the developer's own check
and is cited as his.

What does appear, and is meant to, is non-secret configuration the transcripts
exist to show — among it the broker username, the ports 8883 and 8000, the time
zone, the retry settings and the gateway identifier; that list is illustrative
and not exhaustive. Certificates are described by subject, fingerprint, mode
and owner only; no byte of private material was copied.
