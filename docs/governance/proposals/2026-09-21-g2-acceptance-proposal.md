# G2 acceptance proposal — the complete flow inside the emulated guest

**Written:** 2026-09-21.
**Status: PROPOSED — for the student's decision, not adopted.**

> **Nothing here accepts a gate, admits a claim, closes anything or guarantees
> anything.** This file sets out, clause by clause, what the session of
> 2026-09-20/21 produced against the **prospective** criteria of
> [section 4.3 of the adopted plan](../INTEGRATED_DEVELOPMENT_PLAN_2026.md), so
> that the student can decide. **G2 remains `Not decided`** in the
> [gate-decision log](../gate_decision_log.md) until he records a decision
> there with a date, an authority and a durable decision record. Publishing the
> evidence capsule, a green pull request, this proposal and the fact that every
> check passed are none of them that decision: "**Sealing is not acceptance**,
> and neither is a green documentation pull request" (plan section 4.3, common
> condition 4).
>
> **Everything below is ARM64 EMULATED (QEMU/TCG) on an x86-64 host.** Never
> native ARM64, never KVM. No figure in this document is a performance,
> capacity or timing result, and none may be used as one (plan section 3.5).

## 1. What G2 is, and what it is not

Under the adopted plan, G2 — *live vertical slice* — is **one complete and
inspectable wearable → MQTT/TLS → controller → Ditto → API path inside the
emulated guest**: the six services deployed from the versioned deployment tree
and all healthy, health and readiness answering and the counters at zero before
the run, the deployed images identified, the controller image verified against
its build record, configuration validation clean with the broker able to read
its own secrets, one bounded flow (one smartwatch, 1 Hz, 60 s) meeting the
runbook acceptance list, reconciliation by identity with nothing unaccounted,
consistent counter deltas, the twin readable through the API and matching the
contract, persistence across a service restart **shown, not assumed**, TLS in
force on the publishing path, and a complete evidence capsule whose checksums
verify. In the plan's own words, "**G2 establishes no native deployment, no
timing or resource figure, no stability over time and no claim admission**". It
does not require the nine integration/recovery families, in-flight
controller-restart recovery, the nominal workload, a soak, the 95-run campaign
or any native hardware; those stay downstream, and G2 neither waives nor hides
their open failures.

## 2. The candidate and its identities

One guest session, recorded in seven attempt packages — the session package
itself and the six attempts run within it — on one unchanged image and
container set.

| Layer | Identity |
|---|---|
| Emulation label | **ARM64 EMULATED (QEMU/TCG)** on an x86-64 host; never native ARM64, never KVM |
| Operating system | Poky (Yocto Project Reference Distro) 5.0.19 *scarthgap*; image `egw-gateway-image-qemuarm64`, build stamp `20260918120819` |
| Kernel artefact | `Image-qemuarm64.bin` `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037`; running kernel `6.6.142-yocto-standard`, `aarch64` |
| Rootfs archive | `egw-gateway-image-qemuarm64.rootfs-20260918120819.tar.bz2` `d4569c0e845f3a7e36d292953de64dde76b6e81b7482206d0f0f385bcf805fc7`; disk image `.ext4` `20457c74f92adac33ef30029fdd6633c81839dffbaaf95da68ae96a19be6fa8f` **as read before the boot**, which is the only instant at which that hash identifies the image: `runqemu` boots the ext4 file in place, and the same package holds the hash of the same file after the power-off, `ef0813c152dc86b3aa00f418bf76581a60ab244a5128ccc711114603b8265ef3` (`A1/console/008-artefacts-after-poweroff.stdout.txt`), the expected effect of a writable root file system; manifest `9f554f3bdd4bbb73c196afba4050bcded7a0ceaba41278cbb0622f6f1adf8940`; `qemuboot.conf` `7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4` |
| OS build source | Yocto checkout `8e886700f2b41676a6514d561d548763f52efed2`, clean; launcher `scripts/run-qemu-integrated.sh` `67da61d7…`; `kas/egw-qemuarm64-integrated.yml` `48eb8e9e…`; lock `63c09f15…` |
| QEMU and machine | QEMU emulator version **8.2.7**, binary `5d389c65…`; `-machine virt -cpu cortex-a76 -smp 4 -m 8192`, **TCG**; guest `nproc` 4, 8 012 MiB of usable memory |
| Host | WSL2 Ubuntu 24.04 on Windows 11 x86-64, kernel `6.6.87.2-microsoft-standard-WSL2`, 16 CPUs, 31 798 MiB; load generator co-located with QEMU |
| Container: broker | `egw-mosquitto-1` — `docker.io/library/eclipse-mosquitto:2.0.22@sha256:212f89e1eaeb2c322d6441b64396e3346026674db8fa9c27beac293405c32b3c` |
| Container: database | `egw-mongodb-1` — `docker.io/library/mongo:7.0.39@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d` |
| Container: twin policies | `egw-ditto-policies-1` — `docker.io/eclipse/ditto-policies:3.9.4@sha256:652f75b9accfc1da8cbc228bcede0f7778e732b9625225dafad4a2930903d4bb` |
| Container: twin things | `egw-ditto-things-1` — `docker.io/eclipse/ditto-things:3.9.4@sha256:a1cc8a12d167ae5a22a31c9163913736ca14dcef4b544e6270265965089247b0` |
| Container: twin gateway | `egw-ditto-gateway-1` — `docker.io/eclipse/ditto-gateway:3.9.4@sha256:fc9102b5ed18e5ee402fd5a1a023c5d93c215dce6fd3f24d7efb4a9f6e08682b` |
| Container: controller | `egw-controller-1` — `egw-controller:0.1.0`, image id `sha256:2e30d8fcf921828b7564305a06240e2de79679920c06c4f3a1bfa9f3ec1c7f21` (local image, no repository digest) |
| Controller build identity | `image_architecture=arm64`, `image_os=linux`; `source_commit=0dfa53140996dfb1b95b9cb3a8d5721e85e4d4d9`, build context clean; archive `egw-controller-0.1.0-arm64.tar` `3572f914ad4876253c7c66f032d29a126a1a29dd3516d89ad06c5513e766a3f4`, 50 799 616 bytes; base `python:3.12.13-slim@sha256:229a2c5b…`; built `2026-09-18T18:47:31Z`; **`python_dependencies=UNLOCKED`** |
| Execution commit | **`b7e0c83c3277f7469c05336f91949e7d1b89489a`** on `feat/g2-session-drivers`. Six of the seven attempts record it with `repo_dirty_lines: 0`, read by the driver itself; the seventh (A3, the single-file deployment) was not run by a driver and carries identities written by hand, naming the commit without a dirty-line count |
| Merged baseline | **`ccd5fd647a57842707999fa3f2492befa228e11b`** (`dev`). `b7e0c83` is that baseline plus one commit which touches eight files: it adds `tools/session/gate_health.sh` and `tools/session/persistence.sh`, and changes `tools/session/common.sh`, `tools/session/guest_common.sh`, `tools/session/driver_status.py`, `tools/session/README.md` and the two test modules `src/tests/test_session_drivers.py` and `src/tests/test_fetch_collector_output.py`. Nothing under `src/egw_controller/`, `src/egw_experiments/` or `src/deployment/` differs from the baseline |
| Instruments | drivers `e1c26c66628ebb959ee1a8b3238be799873042014f2ee2a96b831d6e32e9ee3f` (concatenated); export tool `544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b`; host helpers `itest-helpers.sh` `f94cff6f…`, `tunnel.sh` `38f5cae9…`, `ca.crt` `556e139f…` |
| Deployed tree | `/opt/egw/deployment`: 19 files equal to the clean clone, 0 different, 0 only on the guest, 0 only in the clone, 1 allowed difference (`README.md`) |

**Unlike the session of 2026-09-19, what ran is what the repository holds.** Every
attempt records `repo_commit b7e0c83…` with `repo_dirty_lines: 0`, and the
drivers that ran are the versioned ones of `tools/session/`. That was not true
of 2026-09-19, whose live observations came from unversioned working copies
(`LOG.md` `#C036`, "Provenance of the live observations").

## 3. The seven attempts, and where they are

Published copies are in the capsule **`docs/evidence/g2-complete-flow/`**, one
directory per attempt, published by the change that accompanies this proposal.
Local copies are the packages under
**`output_test/runs/2026-09-20/`** of `Projeto Mestrado` (a local copy, neither
published evidence nor a backup). Both use the same attempt directory names, so
one path below serves for both roots.

Each package records three separate verdicts — whether the instrumentation
produced valid evidence, what the system under test did, and whether the copy is
intact — and the exit code of every single command it ran.

| # | Attempt directory | Started (UTC) | Recorded verdicts | What it did |
|---|---|---|---|---|
| A1 | `20260920T231756Z_guest-session_attempt02` | 23:17:56 | `finished`; validity not applicable; system **pass**; every command exit 0 | Boot, identities before the boot, state after the boot, controlled stop, power-off, and the three artefacts of the G1 seal — `Image`, `egw-image-qemuarm64.rootfs.ext4` and `egw-image-qemuarm64.rootfs.manifest` — each read back `OK` |
| A2 | `20260920T231844Z_live-preflight_attempt02` | 23:18:44 | **`failed`**; instrumentation **invalid**; system **not-run** | **FAILED and kept**: the six-container stack was started **here**, by this attempt's interlock, between 23:18:44 and 23:21:18; the comparison that followed then found the deployed tree differing from the clone |
| A3 | `20260920T232205Z_deploy-the-clone-fetch-helper_attempt01` | 23:22:05 | `finished`; valid; **pass**; command exit 0 | The one missing file deployed, ad hoc and single-file, by the developer |
| A4 | `20260920T232219Z_live-preflight_attempt03` | 23:22:19 | `finished`; valid; **pass**; all 16 commands exit 0 | The interlock re-run, its `up -d` finding all six containers already `Running`; collector deployed and checked live; tree equal to the clone |
| A5 | `20260920T232447Z_g2-gate-preconditions_attempt01` | 23:24:47 | `finished`; valid; **pass**; all 7 commands exit 0 | All six healthy, endpoints, zero counters, identities, broker TLS configuration |
| A6 | `20260920T232527Z_smartwatch-slice-1-hz-60-s_attempt02` | 23:25:28 | `finished`; valid; **pass**; all 7 commands exit 0 | The bounded flow, `itest-g2-01`, seed 20260921 |
| A7 | `20260920T233212Z_g2-twin-persistence-restart_attempt01` | 23:32:12 | `finished`; valid; **pass**; all 17 commands exit 0 | Quiesce, declared restart, readback |

The drivers' own process exit statuses (0 pass, 2 a prerequisite, and the rest
of the scale introduced on 2026-09-20) are **not** stored inside the packages;
what the packages record is the three verdicts above and the per-command exit
codes, and that is what is cited here.

**A2 is part of the evidence, not an embarrassment.** Its fifth command exited
1 and the attempt was recorded `failed`, with the instrumentation **invalid**
and the system **not-run**. The two-directional comparison of the deployed tree
against the clean clone had found
`src/deployment/scripts/fetch-collector-output.sh` in the clone and not on the
guest — a file the clone has carried since pull request #38 — and the driver
stopped there rather than run eleven checks it could no longer trust. The
six-container stack had already been started by that same attempt, whose first
command ran the interlock and `up -d` between 23:18:44 and 23:21:18; the
failure came four commands later.

A3 then deployed that one file in a single command, whose argv it seals: the
session's own `gscp` helper (`A1/scripts/session_common.sh`) copied
`src/deployment/scripts/fetch-collector-output.sh` from the execution clone to
`/tmp/fetch-collector-output.sh` on the guest; `gssh` then ran `sudo cp` of it
into `/opt/egw/deployment/scripts/`, `sudo chmod 0755` and `sha256sum` over the
two guest paths. **That was a bounded single-file deployment made by the
developer between the two preflight attempts, not the runbook's deployment
step**: the attempt's own note cites runbook 5.1 as the provenance of the
deployed tree, but no step 5.1 was run here. The two hashes the attempt holds
are both hashes **on the guest** — `/tmp/fetch-collector-output.sh` and
`/opt/egw/deployment/scripts/fetch-collector-output.sh`, each
`9ae07b0c5e4b03385053d270e379b0bf767f34156839ad2c7a53a9aee2f3c7d4` — so what
they show is that the copy which arrived equals the file that was installed.
The clone-side hash was printed outside the attempt and is not in the package.
A4 then repeated the preflight under a new attempt identity. The plan's common
condition 5 asks exactly for this.

## 4. Clause by clause

Verdicts are **met**, **met, with the note stated**, **partly met** and **not
established here**. Every "observed" cell is a reading taken from the evidence
named beside it; nothing is inferred.

**The evidence column holds the A1–A7 shorthand of section 3, not paths.**
`A4/console/005-deployed-vs-clone.stdout.txt` means that file inside the
attempt directory section 3 lists as A4 — the same relative path under the
capsule `docs/evidence/g2-complete-flow/` and under the local copy
`output_test/runs/2026-09-20/`, so section 3's table is what turns a cell into
a path. Where a cell names a package (`A2/`) or a set (`A1…A7/SUMMARY.md`) it
is naming that directory or that set of files, not a single one.

### 4.1 Conditions common to G2–G7 (plan section 4.3)

| # | Condition | What was observed | Evidence (A1–A7 shorthand, section 3) | Met? |
|---|---|---|---|---|
| C1 | **Labelling**: every artefact carries the emulation label; never native ARM64, never KVM | Every attempt summary opens with "**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance"; the environment record states `provider: QEMU 8.2.7 TCG … on WSL2 Ubuntu-24.04, Windows 11 x86-64`, `instance_type: qemu -machine virt -cpu cortex-a76 -smp 4 -m 8192; ARM64 EMULATED` and `shared_vcpu_note: … never native ARM64`; the flow's latency block carries `latency_label: "ARM64 EMULATED (QEMU/TCG); not a performance result"` | `A1…A7/SUMMARY.md`; `A4/console/011-sut-environment.stdout.txt`; `A6/console/005-check.stdout.txt` | **Met** for this evidence. The duty continues into every sentence written about it later |
| C2 | **Identity binding**: each run bound to image, kernel, boot mode, virtual machine and container identities | Section 2 above, in full: OS build artefacts and their SHA-256 taken **before** the boot; the QEMU binary, version, machine, CPU model, vCPU count and memory; the six container identities with image, image id, container id and start time, **five of the six also carrying a repository digest** — the controller's line records `repo_digest=none`, because that image was built locally and never pulled from a registry, and it is identified instead by its image id and its build record; the controller build identity; the execution commit with zero dirty lines | `A1/console/001-identities-before-boot.stdout.txt`; `A4/console/011-sut-environment.stdout.txt`; `A5/environment/container_identities.txt`, `A5/environment/egw-controller-build-identity.txt` | **Met** |
| C3 | **Sealing**: write-once copy, a `SHA256SUMS` over every file but itself, verified by the repository's evidence check; a new capsule under `docs/evidence/<new-name>/`, never inside the sealed G1 capsule | Each attempt package carries its own `SHA256SUMS` and an `export_manifest.json` giving every file its source path and hash; every package reports copy verification **verified** with 0 expected sources missing (A1 66 files, A2 13, A3 5, A4 40, A5 24, A6 32, A7 60). The capsule is `docs/evidence/g2-complete-flow/`, a new name outside `docs/evidence/g1-yocto-qemu/` | `A1…A7/SHA256SUMS`, `A1…A7/export_manifest.json` | **Partly met — the part this document cannot establish.** The capsule's own root seal and the repository's evidence check are produced and run by the publishing change, not by this file. **If that check has not run green over the capsule, this clause is not met and the gate is not decidable** |
| C4 | **Sealing is not acceptance**, and neither is a green pull request | This proposal claims no acceptance; the drivers' own "next action" for A7 reads "publish the G2 evidence capsule and present the gate for the decision; the acceptance itself stays with Rui" | `A7/SUMMARY.md` | **Honoured** (a rule, not a thing to demonstrate) |
| C5 | **Failures kept**; a repeat uses a new predefined run identity | A2 is recorded `failed`, instrumentation `invalid`, system `not-run`, and is preserved and published beside the successful attempts; the repeat is `attempt03`, not a rerun of `attempt02`. The flow used a fresh run identity `itest-g2-01` and seed `20260921`, never used before on this MongoDB volume | `A2/` in full; `A4/`; `A6/attempt.json` | **Met**, with the note in section 6 about the earlier attempts of 2026-09-19 |
| C6 | **No pooling of execution modes**; no result is a performance result | No native run exists, so nothing is pooled. The one timing block produced (p50 274.2 ms, p95 8 114.7 ms, max 9 999.0 ms over 60 confirmations at 1 msg/s) is labelled emulated and not a performance result, and is quoted here only to show it exists, not as a finding; the same three figures are carried into limitation 15 of section 6, where the student reads them before deciding | `A6/console/005-check.stdout.txt` | **Met** |

### 4.2 The G2 condition, clause by clause (plan section 4.3, G2)

| # | Clause | What was observed | Evidence (A1–A7 shorthand, section 3) | Met? |
|---|---|---|---|---|
| G2.1 | Six services **deployed from the versioned deployment tree** and all **healthy** | The deployed tree equals the clean clone at `b7e0c83` except `README.md` (19 equal, 0 different, 0 only on either side). At 2026-09-20T23:24:48Z, sample 1: `egw-mosquitto-1`, `egw-mongodb-1`, `egw-ditto-policies-1`, `egw-ditto-things-1`, `egw-ditto-gateway-1`, `egw-controller-1` all `running/healthy` — "ALL HEALTHY: the 6 expected services are running and healthy" | `A4/console/005-deployed-vs-clone.stdout.txt`; `A5/console/001-services-healthy.stdout.txt` | **Met.** Note: the stack was started **inside A2, the preflight that failed**, by that attempt's own interlock between 23:18:44 and 23:21:18, from a tree that still lacked the collector **fetch helper** — an instrumentation script and not a service input. A4's `up -d` created nothing: it found all six containers already `Running`. The tree was equal to the clone from 23:22:08, before the gate snapshot and before the flow |
| G2.2 | Health and readiness answering, **counters at zero before the run** | `/health` 200 `{"status":"ok"}`; `/ready` 200 `{"status":"ready","mqtt_connected":true,"ditto_ready":true}`; `/metrics` 200 with `accepted 0, rejected 0, duplicate 0, failed 0, dropped 0, received 0, in_progress 0, processing_errors 0, queue_depth 0`, `started_at 2026-09-20T23:21:31.554Z`. That `started_at` identifies the same controller process that then ran the flow | `A5/environment/health.json`, `ready.json`, `metrics.json`, `http_codes.txt`; `A5/console/003-endpoints-verdict.stdout.txt`, `004-counters-verdict.stdout.txt` | **Met.** The zero is of the controller **process** counters and of a device never seen before; nothing was deleted or reset to obtain it |
| G2.3 | Every deployed image **`linux/arm64`** and identified by its **pinned digest** | The interlock reports "all 5 image(s) in `images.lock.env` pinned by `@sha256` digest"; each running container's repository digest is recorded (section 2). The controller image records `image_architecture=arm64`, `image_os=linux` | `A4/console/001-stack-start-interlock.stdout.txt`; `A5/environment/container_identities.txt` | **Partly met.** The five registry images are pinned by digest and run on an `aarch64` guest, but **their architecture is not recorded anywhere in this evidence**; only the controller image carries an explicit architecture field |
| G2.4 | Controller image **verified against its build record** before start-up | Before `up -d`: `OK: image id sha256:2e30d8fc…`, `OK: architecture arm64`, `OK: os linux`, `OK: revision label 0dfa5314…`, `OK: source commit 0dfa5314…, clean build context`, `CONTROLLER IMAGE IDENTITY: verified`. The same identity was re-read at the gate | `A4/console/001-stack-start-interlock.stdout.txt`; `A5/console/006-controller-build-identity.stdout.txt` | **Met.** The record itself states `python_dependencies=UNLOCKED`, carried to section 6 |
| G2.5 | **Configuration validation exiting cleanly**, broker secrets readable by the broker's **unprivileged user** | `OK: .env present, no placeholders`; `OK: docker compose config accepted`; `OK: passwd closed to others (1883:1883 600)`, `OK: certs/server.key closed to others (1883:1883 600)`, `OK: certs/ca.key closed to others (1000:1000 600)`; a one-shot container as uid:gid `1883:1883` — the image's own `mosquitto` user — read `mosquitto.conf`, `acl`, `passwd`, `ca.crt`, `server.crt`, `server.key`; `check exit=0` | `A4/console/001-stack-start-interlock.stdout.txt`, `A4/console/008-broker-secrets-check.stdout.txt` | **Met** |
| G2.6 | **One bounded flow**: one smartwatch, 1 Hz, 60 s, meeting the runbook acceptance list | `scenario=smoke seed=20260921 run_id=itest-g2-01 broker=127.0.0.1:8883 tls=True qos=1 duration=60.0s rate=1.0msg/s devices=smartwatch`; `sent=60`. Acceptance list: `confirmation_deadline_source: controller-marker`, `sent_valid 60`, `delivered_unique 60`, **`lost 0`**, **`late_confirmations 0`**, `duplicates 0`, **`double_accepted 0`**, `failed 0`, `rejected_valid 0`, **`intended_invalid_accepted 0`**, `confirmed_unmatched 0`, `events_accepted_total 60`; marker lag 0.184 s | `A6/console/002-simulator-and-mark.stdout.txt`, `005-check.stdout.txt`, `007-verdict.stdout.txt`; `A6/simulator/itest-g2-01.*` | **Met**, with the note that `intended_invalid_sent` was 0: nothing invalid was offered, so that sub-clause holds without being exercised (section 6) |
| G2.7 | **Reconciliation by identity**, zero unaccounted records | `SLICE PASS check=0 delta=0 unaccounted=no`: every published identity accounted for against the controller's event log and the twin | `A6/console/007-verdict.stdout.txt`; `A6/simulator/itest-g2-01.reconcile.json` | **Met** |
| G2.8 | Every counter delta **consistent per device and per controller process** | Per device: twin `62da1188-4cd1-434b-a9c7-236a8c211f84` `existed_before=False`, `accepted_count None -> 60 (delta 60)`, accepted records in `events.jsonl` 60, `last_run_id itest-g2-01`, `last_seq 59`: OK. Per process: `/metrics accepted 0 -> 60 (delta 60)`; `rejected`, `duplicate`, `failed` and `dropped` all `0 -> 0`. **`received` moved `0 -> 60` as well** — the delta check does not print it, and the two readings are `A5/environment/metrics.json` (`"received":0`) before and `A7/console/002-metrics-before.stdout.txt` (`"received":60`) after, for the same controller process `started_at 2026-09-20T23:21:31.554Z` | `A6/console/006-delta.stdout.txt`; `A5/environment/metrics.json`; `A7/console/002-metrics-before.stdout.txt` | **Met** |
| G2.9 | Twin **readable through the API** and **matching the contract** | Read from the Ditto HTTP API by the `twin` helper of the host-side `itest-helpers.sh`, which is not sealed in the capsule. What the cited file holds is the **response body alone** — no request line, no header, and therefore **no pre-authenticated subject**. The subject `pre:egw-controller` does appear in the capsule, but in two other places: the persistence driver sealed with the session (`A1/scripts/drivers/persistence.sh`, `x-ditto-pre-authenticated: pre:egw-controller`) and A7's own `commands.jsonl`, which is the A7 read-back, not this one. The response carries `thingId` and `policyId` `org.c2dta:62da1188-…`, attributes `device_type`, `egw_id`, `schema_version`, and features `vitals → heart_rate_bpm`, `location → lat, lon` and `ingestion → last_message_id, last_seq, last_run_id, last_ts, accepted_count` — section 4 of [`src/CONTRACTS.md`](../../../src/CONTRACTS.md) field for field | `A6/console/004-twin-readback.stdout.txt`; `A6/simulator/itest-g2-01.twin.62da1188-….json` | **Met**, by comparison of the recorded response against the contract and by the `delta` check of the ingestion fields; **no automated schema validation of the API response is recorded** |
| G2.10 | Persistence across a service restart **shown, not assumed** | Publication stopped and the queue drained (`queue_depth 0` and identical counters on 27 consecutive readings over 131 s). State saved. `docker compose down` then `up -d`, **no volume removed**, same pinned image references. The restart is **shown**: controller `started_at 2026-09-20T23:21:31.554Z -> 2026-09-20T23:37:38.535Z`, and each of the six containers is a **new object started later** (e.g. `egw-mongodb-1` `27667b7c7e28 -> 946354a51791`). All six containers were healthy again at sample 2 of the poll that followed. Readiness was re-checked by `wait_ready`, which **exited 0 — and that exit status is the whole of the evidence for the readiness half**: the helper writes nothing when it succeeds, so both console files of that command (`A7/console/008-ready-again.stdout.txt` and `008-ready-again.stderr.txt`) are empty, and no `/ready` body or status line from after the restart is captured anywhere in the package. Then, **before anything further was published**, the same twin read back `identical`: `last_run_id itest-g2-01`, `last_seq 59`, `last_message_id ad6d3d6f…`, `last_ts 2026-09-20T23:28:39.715Z`, `accepted_count 60`; the run's event log held **60 records before and 60 after** | `A7/console/001-quiesce.stdout.txt`, `008-ready-again.stdout.txt` and `.stderr.txt` (both empty), `009-services-healthy-again.stdout.txt`, `012-restart-shown.stdout.txt`, `014-twin-state-same.stdout.txt`, `017-stored-state.stdout.txt`; `A7/commands.jsonl` for the exit status of `ready-again`; `A7/environment/twin.persist-before.json` | **Met.** The new controller process's counters are 0 again; that is a per-process counter and **is not loss**, and the evidence says so in those words |
| G2.11 | **TLS in force** on the publishing path | Broker configuration: `listener 8883 0.0.0.0`, `cafile`, `certfile`, `keyfile`, `tls_version tlsv1.2`, `allow_anonymous false`, `password_file`, `acl_file`; CA `O=C2DTA EGW dev, CN=EGW Dev Root CA`, fingerprint `AA:34:ED:1E:B4:15:2D:1A:…`; `server.key` and `passwd` mode 600. The publisher connected with `tls=True` to port 8883 and delivered all 60 messages | `A5/environment/tls_configuration.txt`; `A6/console/002-simulator-and-mark.stdout.txt` | **Met** as configuration plus a successful TLS session. **The negative probes — wrong CA, wrong password, plaintext, anonymous — were not repeated in this session** (section 6) |
| G2.12 | A **complete evidence capsule whose checksums verify** | Seven attempts, the failure among them, each with its own verified seal and manifest | `docs/evidence/g2-complete-flow/` | **Not established here** — same boundary as C3. The capsule's root seal and the repository evidence check belong to the publishing change |

### 4.3 The same thing in the five clauses the student was given

| Clause | Covered by | Position |
|---|---|---|
| **Preparation** | C2, G2.1, G2.3, G2.4, G2.5 and A1–A5 | Met, except that the architecture of the five registry images is not recorded (G2.3) |
| **Complete path** | G2.6, G2.7, G2.8, G2.9, G2.11 and A6 | Met, with two sub-clauses satisfied without being exercised: intended-invalid input and the transport refusals |
| **Persistence** | G2.10 and A7 | Met, for one declared whole-stack restart with an empty queue |
| **Evidence** | C3, C5, G2.12 and the whole of section 3 | Met locally, attempt by attempt; **the capsule's own seal and the repository evidence check are outside this document** |
| **Acceptance** | C4 and section 7 | **Open. It is the student's, and this file is not it** |

## 5. What is **not** claimed

Accepting G2 would claim none of the following, and this document claims none of
them:

1. **The nine integration/recovery families.** They were exercised once on
   2026-09-18 and their record stands as the gate log restates it, test by test,
   including **test 5 failing its stated criterion** and the invalid harness runs
   of tests 1 and 6. That is G3, and nothing here touches it.
2. **In-flight restart recovery.** The restart of A7 happened with the queue
   empty and nothing publishing, by design. Restarting under an active backlog is
   a different test and a different, open problem.
3. **The nominal workload of 11.2 msg/s.** On 2026-09-19 the nominal entry
   `nominal-r01` was instrumentation-valid and the **system failed**: 3 794 of
   6 720 valid messages delivered at the controller-clock deadline and 2 926 lost
   at the deadline. **That failure stays open**, it is not waived, absorbed or
   explained away by anything here, and it is the reason the flow of A6 is
   described as bounded rather than representative.
4. **The 24-hour soak.** Not run.
5. **The 95-run campaign.** Not run; it remains a target the campaign *attempts*
   under emulation, subject to the pilot's feasibility check at G4.
6. **Native ARM64 behaviour, native boot or native performance.** No native run
   exists, and none is implied by a guest that reports `aarch64`.
7. **Any capacity, throughput, latency, resource or efficiency figure.** The
   latency block of A6 is an emulated observation carrying its own label; it is
   not a measurement of anything. Its three figures are set out in limitation
   15 of section 6 so that they are read, not buried.
8. **Stability over time**, and **no claim admission**: no C-claim moves, no
   other gate moves, no D007 threshold is approved by implication, and no
   supervisor decision is created, cited or implied.

## 6. Residual limitations of this demonstration itself

Stated so that the student decides with them in view, not around them.

1. **One device, one type.** One smartwatch. The smart ring and the smart
   clothing were not exercised; three wearable types is a G3 condition.
2. **Sixty messages, sixty seconds, about one message per second.** At 1.0
   msg/s against the nominal 11.2 msg/s, that is about an **eleventh** of the
   rate that failed on 2026-09-19. A bounded flow passing at 1 Hz says nothing
   about the rate at which the controller falls behind.
3. **One restart.** One declared whole-stack `down`/`up -d` with the queue empty.
   Not a reboot, not a dependency fault, not a restart under load.
4. **One guest, one session, one repetition.** Each check ran once. Nothing here
   demonstrates reproducibility, and no repeat under a second identity was made.
5. **An emulated platform, on a shared host.** QEMU/TCG on an x86-64 workstation
   whose 16 CPUs also carried the load generator; the environment record notes
   that contention itself.
6. **The wearable is outside the guest.** The simulator, the reconciliation
   helpers and the API reads ran on the WSL2 host and reached the broker and the
   Ditto API through SSH port-forwards. The TLS session runs from the host-side
   publisher to the broker inside the guest. "Inside the emulated guest"
   therefore describes the six services and the stored twin, not the simulated
   device.
7. **Two sub-clauses hold without being exercised.** No intended-invalid payload
   was offered, so "no intended-invalid record accepted" is true of an empty set;
   and TLS enforcement rests on configuration (`allow_anonymous false`,
   `tls_version tlsv1.2`, 600-mode private material) plus one successful TLS
   session, not on a refusal probe repeated in this session.
8. **Image architecture is under-recorded.** See G2.3.
9. **The controller image's Python dependencies are `UNLOCKED`**, by its own
   build record — to be resolved before the experimental freeze.
10. **The drain is an observation, not a proof.** The driver's own words:
    "drained: `queue_depth 0` and identical counters on 27 consecutive readings
    over 131 s — an observation, not proof that processing has finished".
11. **Health is a point-in-time reading.** All six were healthy at sample 1; no
    interval of sustained health is claimed.
12. **The host helper is bound by hash but trails the runbook.**
    `itest-helpers.sh` `f94cff6f…` is exactly the text that section 6.1 of
    `docs/setup/qemu_integrated_gateway.md` generates at revision `0fd75b9`; at
    the execution commit `b7e0c83` the same section generates `c73f1e9a…`. The
    two differ **only by three comment lines** describing `EGW_CLONE`, a variable
    the drivers set explicitly before sourcing the file, so no behaviour differs.
    This was checked while writing this proposal, by regenerating the helper with
    `tools/session/regen_helpers.py` from the runbook at each revision; it is a
    check of the repository, not a sealed observation, and it is reproducible.
13. **The earlier attempts of 2026-09-19 are not inside this capsule.**
    `attempt01` of the guest session, the preflight and the slice, and the failed
    nominal entry, are preserved under `output_test/runs/2026-09-19/` and are not
    copied into `docs/evidence/g2-complete-flow/`. Whether the capsule must carry
    a traceable reference to them is one of the points for the student in
    section 8.
14. **`output_test` is a local copy** — not published evidence, not formal gate
    admission and not an off-machine backup. The verified off-machine copy
    remains outstanding as a resilience action (risk R25).
15. **The timing this very run produced, stated here and not only in a cell.**
    The bounded flow's own latency block reads **p50 274.2 ms, p95 8 114.7 ms
    and max 9 999.0 ms** over its 60 confirmations at 1 msg/s
    (`A6/console/005-check.stdout.txt`), under its own label `ARM64 EMULATED
    (QEMU/TCG); not a performance result`. It belongs in this list because it
    is what the student should have in view when he reads limitation 2: at one
    message per second, on this emulated candidate, the ninety-fifth percentile
    confirmation took over eight seconds and the slowest took just under ten.
    These figures measure the emulated candidate under one bounded run and
    nothing else — they are not a performance, capacity or latency result, no
    threshold is set by them, and none of them may be quoted as a figure of the
    gateway.

## 7. What the student would be accepting

If he accepts, he accepts **this and nothing more**. The wording below is drafted
so that it can be recorded in the
[gate-decision log](../gate_decision_log.md) as the G2 row's notes. The date is
left open deliberately: a date belongs to the **recording** of the decision, and
this file supplies no date for an act that has not been taken.

> **G2 — live vertical slice. Accepted for one bounded wearable → MQTT/TLS →
> controller → Ditto → API flow and for stored-twin persistence across one
> declared service restart, on the emulated candidate identified below, and for
> nothing else.** The evidence is the capsule
> `docs/evidence/g2-complete-flow/`, seven attempts of the guest session of
> 2026-09-20/21 including the preflight that failed and was kept, executed at
> commit `b7e0c83c3277f7469c05336f91949e7d1b89489a` (the merged baseline
> `ccd5fd647a57842707999fa3f2492befa228e11b` plus the one commit that adds the two
> session drivers and the changes they need) with
> a clean execution clone, on the Yocto image `egw-gateway-image-qemuarm64`
> build `20260918120819` (kernel `Image-qemuarm64.bin` `4457ef38…`, rootfs
> archive `d4569c0e…`) under QEMU 8.2.7 **TCG**, `-machine virt -cpu cortex-a76
> -smp 4 -m 8192`, with the six container identities and the controller build
> identity `0dfa5314…` recorded in the capsule. **Execution mode: ARM64
> EMULATED (QEMU/TCG) on an x86-64 host — never native ARM64, never KVM.** What
> was shown: the six services deployed from the versioned tree and all healthy,
> `/health` 200, `/ready` 200 and every controller counter and the queue at zero
> before the run; the deployment images pinned by digest and the controller image
> verified against its build record; configuration validation clean and the
> broker's unprivileged user able to read its own secrets; one smartwatch at
> 1 Hz for 60 s (`itest-g2-01`, seed 20260921) with `sent_valid 60`,
> `delivered_unique 60`, `lost 0`, `late_confirmations 0`, `double_accepted 0`,
> `intended_invalid_accepted 0`, deadline from the controller marker, nothing
> unaccounted and consistent counter deltas per device and per controller
> process; the twin read through the API matching section 4 of
> `src/CONTRACTS.md`; and, after a declared `down`/`up -d` with volumes
> preserved and the queue empty, a restart **shown** by a new controller process
> and six new container objects, with the same twin returning `last_run_id
> itest-g2-01`, `last_seq 59` and `accepted_count 60` before anything further was
> published. **Scope of the decision:** this bounded functional path only. It
> admits no claim; it establishes **no native deployment, no timing or resource
> figure, no capacity, no stability over time and no claim admission**. It does
> **not** accept the nine integration/recovery families (G3), in-flight restart
> recovery, the nominal 11.2 msg/s workload — which failed its delivery deadline
> on 2026-09-19 and **stays open** — the soak, the 95-run campaign or any native
> evidence. The residual limitations recorded in
> `docs/governance/proposals/2026-09-21-g2-acceptance-proposal.md` section 6 are
> part of what is accepted, not exceptions to it.

To make that row lawful under this log's own conventions, the decision also
needs:

- **Formal outcome:** `Accepted`.
- **Decided at:** the date on which the student records the decision. No earlier
  date may be written there, and no date may be attached to anyone else's act.
- **Decision authority:** Student (Rui Duarte).
- **Decision record:** a durable file, on the pattern of
  [`decisions/2026-09-19-g0-closure.md`](../decisions/2026-09-19-g0-closure.md),
  holding the student's own statement so that the decision can be read from a
  clean checkout. **This proposal is not that record**, and neither is `LOG.md`,
  which is a diary.
- **Evidence identity:** `docs/evidence/g2-complete-flow/`, named with the
  execution commit `b7e0c83…` and the image build `20260918120819`, with the
  local packages under `output_test/runs/2026-09-20/` cited as the local copy
  they are.
- **Superseded state:** the present G2 row, kept verbatim under "Superseded row
  states", so that what it replaces is not erased.

## 8. Points for the student before he decides

1. Whether the capsule's root seal and the repository's evidence check have run
   green over `docs/evidence/g2-complete-flow/` — clauses C3 and G2.12 are not
   met until they have.
2. Whether the capsule must carry a traceable reference to the attempts of
   2026-09-19 preserved under `output_test/runs/2026-09-19/` (limitation 13).
3. Whether the two sub-clauses satisfied without being exercised — intended-
   invalid input and the transport refusals — are acceptable at G2 or must be
   demonstrated on this candidate before acceptance (limitation 7).
4. Whether the unrecorded architecture of the five registry images must be
   recorded before acceptance or carried as a residual (G2.3).
5. Whether the scope wording of section 7 says what he means it to say, and
   whether anything in section 6 should be moved from a limitation into a
   condition.

## 9. Until he records it, the gate is not decided

**G2 stays `Not decided`.** The gate-decision log is the sole home of a formal
gate outcome, and its state does not change because evidence exists, because
checks passed, because a capsule was sealed, because a pull request went green
or because this proposal was written. It changes when the student records a
dated decision with an authority and a durable decision record — and not before.
