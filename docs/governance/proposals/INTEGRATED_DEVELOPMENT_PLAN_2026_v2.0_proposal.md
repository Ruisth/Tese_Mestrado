# Integrated Yocto ARM64 Edge Gateway Dissertation Plan — version 2.0 (proposal)

> **Status — proposal, not in force (2026-09-18).** This file is kept under `docs/governance/proposals/` because version 2.0 is a proposal. The plan in force is [version 1.2](../INTEGRATED_DEVELOPMENT_PLAN_2026.md), unmodified at its canonical path `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`. It stays in force until the student decides, after consulting the supervisors, whether to adopt this revision; merging the pull request that carries this file adopts nothing (see the [README of this directory](README.md)). Where the text below says "current", "final" or "must", read it as the content of the proposal.
>
> **Dates.** Planned submission **2026-10-20**; final delivery deadline **2026-10-31**; 2026-10-21 to 2026-10-31 is a contingency window for essential corrections only. Source: the student's confirmation of 2026-09-18 after discussing the dates with the supervisors. It is a first-party statement; no administrative document has been checked (see D013), and that delivery after 2026-09-30 is formally available is as reported by the student and is not verified here. Every milestone date in section 6 is a **forecast** made on 2026-09-18, not a completed milestone.
>
> **Sent to the supervisors:** nothing. The G0 alignment email, the revised [alignment memo](supervisor_alignment_memo_v2.0_proposal.md), decisions D001–D010 and the new decisions D011–D014 are all unsent (`proposed_not_sent` in the [decision log](../supervisor_decision_log.csv)). **Approved by the supervisors:** nothing. [ADR 0008](../../adr/0008-integrated-yocto-arm64-evaluation.md) is Proposed — pending supervisor agreement (accepted by the student for technical planning only).
>
> Technical preparation and functional integration tests proceed in parallel and do not wait for this review; they adopt no plan and accept no gate or claim. [Section 10](#10-evidence-classes-emulated-qemutcg-versus-native-arm64) fixes what emulated QEMU/TCG runs may demonstrate, what still depends on native ARM64 and which scope changes need supervisor agreement.

**Version/date:** 2.0 — 2026-09-16; amended 2026-09-18 (status box, section 10 and proposal wording); amended again 2026-09-18 (moved under `docs/governance/proposals/`, dates aligned with the student's confirmation, sections 6 and 7 reforecast)

**Authority:** the student's explicit instruction to correct the plan so that the gateway services are benchmarked on the student's Yocto-built Linux system. This authorises technical planning and preparation; it is not evidence of supervisor approval.

**Planned submission:** 2026-10-20. This is the submission itself, not draft completion or readiness to submit; supervisor review, corrections, final verification and packaging are planned before it (section 6).

**Final delivery deadline:** 2026-10-31. The eleven calendar days from 2026-10-21 to 2026-10-31 are a contingency window for essential corrections, submission difficulties and administrative recovery only. The window is not the default delivery period and receives no optional scope. 2026-10-31 is a Saturday; whether a delivery is accepted on that day, or the effective last day is 2026-10-30, is not recorded here.

**Source of both dates:** the student's confirmation of 2026-09-18 after discussing the dates with the supervisors, recorded as the student's statement; no institutional portal or administrative document was checked. For current planning the pair supersedes the internal cut-off of 2026-09-29 and the delivery baseline of 2026-09-30, which stay in plan v1.2 and in the historical records.

**Availability reported:** approximately 8 hours daily, including weekends.

**Proposed to supersede, if adopted:** [version 1.2](../INTEGRATED_DEVELOPMENT_PLAN_2026.md), which remains in force (see the status box). Historical evidence and gate decisions retain their original meaning.

## 1. Correction and scientific objective

The original Theme 1 description (`Temas_Tese.pdf`, physical page 3, held at the workspace root) asks for a custom Yocto-based Linux distribution that supports multiple wearable digital twins on ARM, and for the solution to be tested. The base C2DTA paper (`artigos/EdgeGateway_Paper.pdf`, physical page 41) identifies ARM-cloud evaluation as future work but does not mention Yocto. The August proposal to assess Yocto and the application separately was an internal scope reduction; it was not an explicit requirement of either source and has no recorded supervisor approval.

The revised objective is to design, build and experimentally evaluate an **integrated Yocto-based ARM64 Edge Gateway** hosting the local digital-twin core of C2DTA. The gateway's Linux kernel and root filesystem are produced by the versioned Yocto build. Mosquitto, the controller, Eclipse Ditto and MongoDB execute as ARM64 containers on that system during the final campaign.

The two layers remain a logical decomposition (operating-system platform and application services), but form **one system under test**. A Yocto root filesystem inside an Ubuntu-hosted container/chroot does not satisfy the objective: the measured guest must actually boot the Yocto-produced kernel/root filesystem. Booting Yocto while running Ditto on another Ubuntu VM also does not satisfy it.

**Proposed title:** *Design and Experimental Evaluation of a Yocto-Based ARM64 Edge Gateway for the Local Digital-Twin Core of C2DTA*.

- **RQ1:** How can a versioned Yocto-based ARM64 gateway image be built, deployed and redeployed in an ARM64 virtual machine to host the local digital-twin core of C2DTA?
- **RQ2:** To what extent can the integrated gateway ingest and materialise concurrent synthetic telemetry from three wearable-device types correctly and reliably, including under specified fault scenarios?
- **RQ3:** What latency, sustainable-throughput, saturation and per-container resource trade-offs characterise the integrated gateway under controlled loads on the selected ARM64 virtual machine?

These are current working questions for technical planning and academic revision. Final wording and the retained local-core boundary must be discussed with the supervisors. No claim is accepted merely by changing this plan.

## 2. Required system and scope

```text
Existing x86-64 WSL build host
  -> versioned Yocto configuration and ARM64 image
  -> compatible native ARM64 virtual machine
       Yocto-built Linux kernel + root filesystem
         -> container runtime
              Mosquitto -> controller -> Ditto -> MongoDB

External simulator/harness --MQTT/TLS--> gateway VM
Guest-side collectors --archived evidence--> external analysis
```

Retain the existing three profiles (smartwatch, smart ring, smart clothing), nominal aggregate 11.2 messages/s, JSON contracts, MQTT/TLS and the six scenario families. Preserve the controller-side monotonic latency boundary: reception by the controller to Ditto's acknowledgement. It is not the full sensor-to-storage latency or proof of durable storage at that exact acknowledgement time.

The existing local-core boundary is retained. Executable SSI, DIDComm, ledgers, IPFS, AI services, additional device types and a physical-board campaign are not added by this correction. Their treatment must remain explicit in the dissertation and supervisor alignment. Physical deployment is a future port of the maintained distribution/configuration to a selected BSP, kernel and drivers, not a promise that an identical VM disk image runs on any ARM board. No superiority of Yocto over Ubuntu, energy advantage or physical-board performance may be inferred without a corresponding experiment.

The separate article and defence preparation retain their later work package. The definition of done for the 2026-10-20 submission covers the dissertation, code/evidence package and required submission material; if the supervisors require the separate article before submission, it needs its own effort allocation.

## 3. Reusable evidence and gaps verified on 2026-09-16

| Item | What has actually been checked | Consequence |
|---|---|---|
| Existing G1 | Identified Yocto build and five strict QEMU boots are archived; G1 was accepted for its original functional scope | Reuse as preliminary evidence; do not relabel it as an integrated gateway validation |
| Build environment | Read-only WSL inspection: Ubuntu-24.04, x86_64, existing build/cache and about 817 GiB free at inspection | Continue cross-building locally; no ARM cloud build server is inherently required |
| Kernel/container base | Existing Linux 6.6.142 configuration enables cgroups, memory accounting, namespaces, overlayfs, bridge networking and virtio devices; archived runtime is Moby 25.0.9 | Useful starting point; does not establish full stack compatibility |
| Cloud boot | Current kernel has EFI, but ACPI, ENA and NVMe are disabled; outputs include rootfs ext4/tar, not a complete cloud EFI disk | Add a platform-specific machine/kernel/image target; uploading the current ext4 file alone is not a validated route |
| Compose/tools | Current package manifest lacks Compose and several host-side tools used by deployment scripts; a Compose V2 recipe exists in the checked-out meta-virtualization revision | Add and pin the required tools; prefer prebuilt/pinned controller images to requiring a build toolchain on the measured guest |
| Full-stack CPU/RAM | Historical QEMU command uses Cortex-A57 and 256 MiB; MongoDB 7 requires ARMv8.2-A or later | Use an appropriate CPU and memory profile for full-stack diagnostics; do not reuse the smoke command unchanged |
| Measurement deployment | Student reports no VM and no benchmarks; no integrated Yocto run exists | Native boot, live integration, pilot and campaign are pending |
| Writing | Substantive introduction/background and reusable methodology/architecture; results and conclusions incomplete | Revise the system boundary and write in parallel with integration |

This is a read-only technical/documentary assessment dated 2026-09-16, not a new build, runtime test or cloud allocation. What has been demonstrated since then, all of it emulated, is recorded in section 10; the new platform image and service compatibility remain to be demonstrated.

## 4. Platform decision and bounded feasibility check

**Preferred AWS route, subject to access and a successful boot:** build a Yocto EC2 ARM64 image and register a custom Graviton AMI. The AWS-maintained `meta-aws` Scarthgap branch provides `aws-ec2-arm64` and `aws-ec2-image`; the reference commit observed on 2026-09-16 is `cad59b89c00012ab67d8b4f105714c8aaa5c16a4`. Treat it as a compatibility candidate, not a layer already integrated or proven with this repository's pins. Inspect its dependencies and select an exact revision before building.

The supplied route creates an EFI disk and uses S3 -> EBS `import-snapshot` -> `register-image` with ARM64/UEFI/HVM/ENA. This is distinct from importing a VM with `import-image`; AWS's VM Import/Export support page excludes ARM64 VMs. Verify IAM rights, the generated disk, boot mode, network/storage drivers, console access and cleanup procedures before allocating resources. Review generated helper scripts: use unique image names and do not allow a naming collision to deregister an existing AMI. Dimension the filesystem in advance; do not assume automatic online expansion.

An ordinary Graviton VM must not be assumed to support nested KVM. The preferred route boots Yocto directly as the VM operating system. The existing `c6g.xlarge` suggestion is only a candidate instance class until the custom-image path, CPU requirements, quota, region and costs are confirmed.

**Alternative if promptly available:** an institutional ARM64 host exposing KVM, or an ARM64 bare-metal host with permission to create a hardware-accelerated guest. QEMU/KVM on real ARM64 may host the measured Yocto guest when acceleration is explicitly verified and recorded. QEMU/TCG CPU emulation is never a performance measurement platform: it yields functional and integration evidence only, and any timing taken under it is informational and labelled emulated (section 10). The presence of the word QEMU does not, by itself, identify the execution mode. Do not silently fall back from KVM to TCG.

Use one final platform and image configuration for the campaign. Keep a proposed measurement envelope of 4 vCPU, 8 GiB RAM and at least 80 GiB storage, then verify actual footprint and headroom before freezing it. These are provisioning targets, not measured requirements or guarantees. Non-burstable operation is retained; record shared-host and virtualisation limitations. Keep load generation outside the measured guest.

**Feasibility exit:** a selected route with documented image-boot support, access/IAM or KVM capability, resource availability and an approved cost envelope. The text of 2026-09-16 set this exit for 2026-09-19. On 2026-09-18 no native ARM64 host had been obtained and no provider route was confirmed, so the exit is **pending** and is now governed by the native ARM64 decision point of section 6 (forecast 2026-09-25). The previous EUR 30 ceiling is retained as a spending limit pending a new explicit budget decision; the old cost estimate is obsolete. Do not provision a larger or bare-metal resource on the assumption that the old budget covers it.

**Time box:** allocate the first 8-16 active hours to selecting/checking the route and preparing a minimal boot candidate. If the route fails, choose a supported alternative and reforecast; do not spend a week assuming an ordinary ARM VM can run any custom image.

## 5. Implementation work packages and acceptance

1. **Platform-specific Yocto target.** Preserve the G1 target and artefacts. Add a distinct kas/machine configuration and output directory for the chosen VM; pin layers and kernel configuration. Produce the required bootloader/EFI disk, ACPI/PCI and network/storage support. Archive build ID, kernel/rootfs/disk hashes, package manifest and boot configuration. Prove console access, SSH, networking and persistent storage after reboot.
2. **Operational guest.** Add Compose V2 and the exact shell, TLS, time and evidence tools required by the runbook. Remove `debug-tweaks` and passwordless root for the networked target; use SSH keys and controlled service access. Configure clock synchronisation, DNS/CA trust, data-volume ownership, log rotation and adequate space for images/data/soak. Validate cgroup/overlay/network behaviour and required CPU instructions. CFS bandwidth control is needed only if CPU quotas become part of the protocol; record the existing disabled setting rather than inventing a quota experiment.
3. **Service deployment on Yocto.** Build the controller image in a documented build environment with pinned dependencies; transfer/pull verified ARM64 images, identify their digests and deploy the six containers. Add a versioned deployment configuration that removes the current controller `build:` path and identifies the prebuilt image by registry digest, or by a checksummed offline image archive plus verified image/config identity. The existing manifest/digest verification uses Buildx: execute the complete verification on the build/provisioning host and archive it, then verify the deployed identities in the guest. This avoids making Buildx mandatory on the measured guest without weakening the image checks. Prove MQTT/TLS -> controller -> Ditto -> API, then all three profiles, invalid input, duplicate handling, disconnect/reconnect, controller restart and persistent twin state.
4. **Measurement adaptation.** Collect resources, controller events and environment information inside the Yocto guest. Extend the manifest/validity checks to bind each run to the Yocto image, kernel, boot mode, VM and container identities; `uname -m=aarch64` alone is insufficient. Verify clock/window coverage and generated-load delivery. Add targeted regressions for wrong-OS/image provenance and wrong collector location; preserve existing validity requirements.
5. **Pilot and freeze.** Run a short pilot spanning the conditions on the actual integrated system, fix defects, agree the scientific thresholds and freeze the protocol/image/container/environment set. Any runtime/image change affecting measurements after freeze requires revalidation and repetition of affected conditions under new IDs.
6. **Campaign and analysis.** Retain the current plan of 95 runs, including the 24-hour soak, unless a justified amendment is recorded before freeze. Current timed windows/intervals total approximately 32.5 hours before external procedures, startup and repeats; allow 3-5 elapsed days after a valid pilot. Automatic execution is not counted as continuous human work. Historical functional boots may be admitted only by an explicit prospective mapping; do not count them as native-image boots.
7. **Writing and release.** Revise the introduction, RQs, DSR demonstration/evaluation, architecture diagram, methodology and environment tables. Complete results/discussion/conclusions from admitted evidence, then references, abstracts, AI declaration/form, format and visual QA. Prepare the final evidence index, hashes and off-machine copy. Record a real supervisor review and submission separately from technical completion.

## 6. Schedule: forecast of 2026-09-18 for the planned submission of 2026-10-20 (final deadline 2026-10-31)

**This section is a forecast.** It was made on 2026-09-18 by working backwards from the planned submission of 2026-10-20 and replaces the target dates written on 2026-09-16. Every date after 2026-09-18 is a forecast: it is not a commitment, not a completed milestone and not a gate decision. No gate is accepted by this section, and nothing in it has been agreed by the supervisors. The "Status" column gives the state on 2026-09-18 in three words only: **demonstrated** (done and recorded, here always emulated), **in preparation** (authorised, not run) and **pending** (not started, or waiting for someone else).

Backward chain: submission 2026-10-20 <- packaging 2026-10-19 <- final QA 2026-10-17 to 2026-10-18 <- corrections 2026-10-15 to 2026-10-17 (2026-10-17 is shared with final QA, see Q1) <- supervisor feedback window 2026-10-09 to 2026-10-14 <- full draft sent 2026-10-08 <- analysis <- data freeze <- campaign (or its contingency form) <- protocol freeze <- pilot <- stack stable on the emulated guest 2026-09-25 <- nine integration tests <- first functional flow.

"Runbook" below means [`docs/setup/qemu_integrated_gateway.md`](../../setup/qemu_integrated_gateway.md). Writing proceeds alongside the platform and integration work and shares the same 8 hours a day.

The text of 2026-09-16 tied each target date to a gate; the tables below use their own milestone identifiers. For orientation only, and accepting no gate: A0 and the decision point D correspond to the G0 platform route and alignment package, N1 to G1B, M3 to G2, M2 with the pilot and protocol freeze (C1–C2 or N3) to G3/G4, the data freeze (C4 or N4) to G5, W3 to G6, and Q1 with P1 to G7. Which gates may be decided on emulated evidence is not settled (section 10).

### 6.1 Demonstrated on 2026-09-18 (all emulated: ARM64 under QEMU/TCG on x86-64, functional evidence only)

| Item | Date | Evidence | Status |
|---|---|---|---|
| Integrated image build (commit `03e333e`) | 2026-09-18 | Sealed technical evidence under `docs/evidence/integrated-qemu/` | Demonstrated (emulated) |
| Two boots with every acceptance check passing (commit `3209b17`) | 2026-09-18 | Same capsule | Demonstrated (emulated) |
| Isolated MongoDB 7.0.39 test (start, write/read, restart, persistence across a guest power cycle) | 2026-09-18 | Same capsule | Demonstrated (emulated) |

Sealing and merging accept no gate and validate no stack. Not demonstrated: the six-container stack on the guest, the functional path smartwatch simulator -> MQTT/TLS -> controller -> Ditto -> API, any integration test on the real stack, and any measurement.

### 6.2 Common path (forecast)

| # | Milestone | Forecast | Depends on | Exit evidence | Status |
|---|---|---|---|---|---|
| A0 | Alignment package sent to the supervisors: D011–D014 (D014 worded as a conditional request), D013 with the dates of this forecast, D004 (template, AI declaration/form), D007 (thresholds) | 2026-09-21 | The student's decision to send | Copy and date of the sent message; `sent_at` filled in the decision log | Pending — drafts exist, nothing sent |
| M1 | First bounded end-to-end functional test on the emulated guest (one smartwatch, 1 Hz, 60 s) | 2026-09-19 to 2026-09-20; reforecast if not done by 2026-09-22 | Controller ARM64 image; six containers deployed in the guest (runbook sections 4-6) | `sent_events.jsonl`, `events.jsonl`, twin state through the API, reconciliation by identity; labelled emulated | In preparation — authorised on 2026-09-18, not run |
| M2 | The nine integration tests (runbook section 7), in order | 2026-09-21 to 2026-09-24 | M1 | One evidence directory per run; each test's expected list met; failures retained | Pending |
| M3 | Stack stable on the emulated guest | 2026-09-25 | M2 on one unchanged image and container set, including the guest-reboot test | Sealed functional/integration evidence; `PROGRESS.md` updated; no gate accepted by this | Pending |
| M4 | Measurement adaptation (runbook section 9, items 1-4: `execution_mode`, image identity, refusal to pool modes, wrong-provenance regression) | 2026-09-22 to 2026-09-27, in parallel with M2–M3; the manifest fields (`execution_mode`, image identity) by 2026-09-25, because the pilot C1 needs them | Nothing external | Unit tests and a pilot manifest carrying the new fields | Pending |
| W1 | Chapters 3-4 drafted; Chapters 1-4 sent early for review | Drafting 2026-09-19 to 2026-09-30; sent 2026-10-01 | For the final wording of title and RQs: a reply to D011; drafting itself is reversible work | Copy of the sent message; checksum of the compiled PDF | Pending — Chapters 3-4 are empty structure |
| **D** | **Native ARM64 decision point** | **2026-09-25, end of day** | A0 sent, so that D014 is already before the supervisors as a conditional request | Dated record: either "native host in hand" (access, custom-image boot route and budget confirmed, D012) or "D014 contingency requested" | Pending |

**Native ARM64 decision point (forecast 2026-09-25).** With the full draft due on 2026-10-08, the native branch needs, at the lower bound of every duration, 3 days for the native image and boot (G1B; the native target is unbuilt), 2 days for the stack and the nine tests on the native guest, 2 days for pilot and freeze, 3 elapsed days of campaign (section 5 allows 3-5) and 2 days of analysis: 12 days, 2026-09-26 to 2026-10-07. A host in hand at the end of 2026-09-25 therefore leaves zero float in the technical chain and **no day at all** for the results-dependent text of Chapters 5-6 (W2 needs the analysis N5), for which branch C keeps two days. Counted with those two days, branch N is two days short on 2026-09-25 and reaches zero float only with a host in hand by the end of 2026-09-23; every later day removes a campaign day. From a host obtained on the decision date, the full draft of 2026-10-08 could therefore carry native results only as preliminary text, or W3 slips; either case is a reforecast (section 6.7). The decision point is kept at 2026-09-25 in this forecast; whether to bring it forward is a decision of the student. If no native host is in hand on that date, the student records the fact and asks the supervisors for the D014 contingency; the contingency changes what the evaluation chapter can contain, **needs the supervisors' agreement** and is not applied on the student's decision alone. For the evaluation chapter to be written against an agreed scope, the request has to reach the supervisors before the decision point (A0) and a reply is needed by 2026-10-01. Silence is not approval, and a refusal or no reply by that date is a reforecast trigger (section 6.7).

### 6.3 Branch N — native host in hand by 2026-09-25 (forecast; assessed as tight to infeasible)

| # | Milestone | Forecast | Depends on | Exit evidence | Status |
|---|---|---|---|---|---|
| N1 | G1B: native Yocto boot | 2026-09-26 to 2026-09-28 | D = native; D012 (access and budget; EUR 30 ceiling retained) | Identified image running as the VM operating system; SSH, network, storage and reboots shown | Pending |
| N2 | Stack and nine tests repeated on the native guest | 2026-09-29 to 2026-09-30 | N1, M3 | As M2–M3, with `execution_mode` native | Pending |
| N3 | Pilot and protocol freeze | 2026-10-01 to 2026-10-02 | N2, M4; a reply to D007 | Non-citable pilot over every condition; frozen protocol, run identities, thresholds, image and container set | Pending |
| N4 | Campaign and data freeze | 2026-10-03 to 2026-10-05 (3 elapsed days; at 5 days it ends on 2026-10-07) | N3 | Write-once raw data, manifests, checksums, failures retained; dated freeze record | Pending |
| N5 | Analysis | 2026-10-06 to 2026-10-07 | N4 | Tables and figures regenerated from admitted raw data by the delivered command | Pending |

Float in branch N with a host in hand on 2026-09-25: 0 days in the technical chain at the lower bounds, -2 days once the two days of results-dependent writing (W2) are counted, and -4 days with a five-day campaign as well. N4 is the campaign of section 5 (95 runs with the 24-hour soak, 3-5 elapsed days). Writing included, it fits only with a host in hand by the end of 2026-09-23 (three-day campaign) or 2026-09-21 (five-day campaign); after that it would need the justified amendment, recorded before the freeze, that section 5 item 6 allows. There is no native host and no confirmed route on 2026-09-18, so branch N is a possibility to be decided at the decision point, not the expected path.

### 6.4 Branch C — D014 contingency (forecast; emulated functional evidence only; requires the supervisors' agreement)

| # | Milestone | Forecast | Depends on | Exit evidence | Status |
|---|---|---|---|---|---|
| C1 | Emulated pilot in the runbook section 8 order (120 s nominal, 600 s nominal, load sweep at 10 and 50 messages/s, 3600 s soak) | 2026-09-26 to 2026-09-27 | M3; the manifest fields of M4 (the rest of M4 before C2) | Valid manifests labelled "ARM64 emulated"; generator delivery check; pilot findings | Pending |
| C2 | Protocol freeze, contingency form: the functional evidence set (tests and runs, identities, acceptance lists, labels) | 2026-09-28 to 2026-09-29, prepared at risk | C1; D007 where thresholds remain. Recorded as the frozen protocol of the evaluation only once D014 is answered (reply needed by 2026-10-01) | Frozen, checksummed protocol and run plan; no timing threshold presented as ARM64 performance | Pending |
| C3 | Contingency campaign: the frozen functional set under predefined identities; never the 95 runs and never the 24-hour soak on the emulated environment (runbook section 8, rule 1) | 2026-09-30 to 2026-10-02, run at risk | C2. The runs are functional evidence under section 10 rule 1 whatever the reply; their use as the evaluation of the dissertation depends on D014 | Write-once evidence per run, checksums, failures retained | Pending |
| C4 | Data freeze | 2026-10-03 | C3 | Dated freeze record; raw evidence immutable | Pending |
| C5 | Analysis: correctness, fault handling, recovery, persistence; timing only as informational and labelled emulated | 2026-10-04 to 2026-10-05 | C4; a reply to D014 for the agreed wording | Outputs grouped by `execution_mode`; claim-evidence matrix updated; RQ3 performance evidence recorded as a limitation in the agreed wording | Pending |
| — | Days between the analysis and the full draft | 2026-10-06 to 2026-10-07 (2 days) | — | Taken by the results-dependent text of W2; not free float, and never used for features | — |

C2 and C3 are forecast before the date by which a reply to D014 is needed. They are prepared and run **at risk**: emulated functional runs need no agreement to exist (section 10 rule 1), but the contingency form becomes the protocol of the evaluation, and Chapter 5 is written against it, only if the supervisors agree. Nothing in this branch is applied to the dissertation as if it were agreed.

### 6.5 Writing, review and release (both branches; forecast)

| # | Milestone | Forecast | Depends on | Exit evidence | Status |
|---|---|---|---|---|---|
| W2 | Chapters 5-6, abstracts (English and Portuguese), conclusions | 2026-10-04 to 2026-10-07: structure and results-independent text on 2026-10-04 and 2026-10-05, results-dependent text on 2026-10-06 and 2026-10-07 (branch C; on branch N the analysis ends on 2026-10-07, see section 6.2) | Analysis (N5 or C5) for the results-dependent text; W1 | Clean build; every quantitative statement traced to admitted evidence; no placeholders | Pending |
| W3 | **Full draft sent to the supervisors** | **2026-10-08** | W2 | Copy and date of the sent message; PDF checksum | Pending |
| S1 | **Supervisor feedback window** | 2026-10-09 to 2026-10-14 (six calendar days, four working days) | W3; a turnaround agreed beforehand (D013). It is a request, not a commitment by the supervisors | Comments received and recorded | Pending — not requested |
| Q0 | QA groundwork during the feedback window: official template and metadata (D004), references, figures, evidence index, draft of the AI-use declaration and form | 2026-10-09 to 2026-10-14 | W3; a reply to D004 | Checklist items closed before the comments arrive | Pending |
| W4 | Corrections | 2026-10-15 to 2026-10-17 (earlier as comments arrive) | S1 | Change list, replies, rationale for unresolved items | Pending |
| Q1 | Final QA: formal requirements, the AI-use declaration and form required by the institution, template conformity, a similarity check if the institution or the supervisors require one, language, page-by-page visual check, no open notes | 2026-10-17 to 2026-10-18; on 2026-10-17, shared with W4, only the checks that do not depend on the corrected text, the page-by-page check following the last correction | W4 | Completed checklist; final PDF with correct metadata; declaration and form attached | Pending |
| P1 | Packaging: final PDF checksum, sources, evidence index and hashes, repository bundle, verified off-machine copy | 2026-10-19 | Q1 | Archive, SHA-256, storage location, restore check | Pending |
| **SUB** | **Submission** | **2026-10-20** | P1 | Portal receipt and checksum of the submitted PDF, recorded separately from technical completion | Pending |
| CW | Contingency window | 2026-10-21 to 2026-10-31 | Only a failed submission step or an essential correction | Corrected receipt or incident record | Not planned work |

### 6.6 Critical path and float

- **Expected case (branch C):** M1 -> M2 -> M3 -> C1 -> C2 -> C3 -> C4 -> C5 -> W2 -> W3 -> S1 -> W4 -> Q1 -> P1 -> SUB. The technical chain ends two days before W3 (2026-10-06 to 2026-10-07), but W2 occupies those days with the results-dependent text, so they are not free float. The writing chain W1 -> W2 has none: Chapters 3-6 are empty structure and have to be written inside the same 8 hours a day as the integration work. Writing, not the emulated campaign, is the most likely reason for W3 to slip.
- **Branch N:** zero float in the technical chain at lower-bound durations with a host in hand on 2026-09-25, and no day for results-dependent writing; negative once W2 or a five-day campaign is counted (section 6.3).
- **After W3:** no float before 2026-10-20. A feedback window that ends after 2026-10-14, or comments that require new experiments, cannot be absorbed; the only recovery is the contingency window, and only for essential corrections.
- **External dependencies on the path (owner: the supervisors; none requested yet):** a reply to D014 by 2026-10-01; D007 before any protocol freeze is recorded as such; D011 before title and RQs are final; D004 before final QA; D013 for the review turnaround. Under the rules in force D001 and D004 block the final academic release and D007 blocks `exp-v1`.
- **Send Chapters 1-4 early (W1)** to spread the review work; it is a request to the supervisors, not an assumed commitment.

### 6.7 Escalation and reforecast

Reforecast triggers (forecast dates): A0 not sent by 2026-09-21; M1 not done by 2026-09-22; M3 not reached by 2026-09-25; no pilot by 2026-09-29 (branch C, emulated) or by 2026-10-02 (branch N, native); no reply to D014 by 2026-10-01, or a refusal; no data freeze by 2026-10-05 (both branches; on branch N this already assumes the three-day campaign); W3 not sent by 2026-10-08; no agreed reviewer window. With neither a native host at the decision point nor agreement to D014 by 2026-10-01, this forecast holds no evaluation chapter with an agreed scope for the 2026-10-20 submission: the student reforecasts and escalates to the supervisors on that day, and the contingency window is not used to absorb it. Report the failed milestone and the remaining effort on the day it happens; gates are not moved silently to the last day. Preserve the integrated Yocto objective; reverting to Ubuntu benchmarks requires a new explicit scope decision, not an unreported shortcut.

### 6.8 Cutting order

In this order. Nothing below weakens evidence integrity, the validity rules, the supervisors' review, the AI-use declaration or final QA.

1. **Anything outside P0, and the separate article and defence preparation,** stay out (plan v1.2 section 3.4; section 2 above).
2. **Non-prerequisite engineering:** converting the nine tests into automated integration tests; the optional host-side sampler of the QEMU process (runbook section 9 item 5); auxiliary APIs (the G2 cut rule of [`docs/g0/backlog.md`](../../g0/backlog.md)).
3. **Optional exposition in the text,** before evidence or scope (mitigation of risk R8 in [`docs/g0/risks.md`](../../g0/risks.md)).
4. **Optional campaign conditions,** only as a documented limitation and only through a justified amendment recorded before the freeze (section 5 item 6). Which conditions are optional is not recorded anywhere and needs a decision of the student.
5. **Native performance evidence for RQ3,** through D014 and only with the supervisors' agreement: the evaluation then contains emulated functional and integration evidence, and latency, throughput, saturation and resource results become an explicit limitation and future work. Missing evidence becomes an explicit limitation; it is never replaced by an inferred result.
6. **Never as a shortcut:** reverting to Ubuntu-hosted benchmarks; changing thresholds after the freeze; feature work after the data freeze; using 2026-10-21 to 2026-10-31 for functionality.

## 7. Revised effort and feasibility

The previous estimate of 180-260 active hours assumed separately evaluated operating-system and service layers. The correction adds approximately 30-60 technical hours for VM-image adaptation, guest completion and integration revalidation, plus 12-24 writing/review hours. The technical increment includes cloud-image preparation; it must not be added again as a separate full cloud work package. Existing bug/review reserves are not duplicated.

**Planning range estimated on 2026-09-16: approximately 225-345 active hours remaining** (rounded from 222-344). It assumes reuse of existing code/text, an available supported platform route and one substantial supervisor revision. Serious provider-access or boot incompatibilities require a fresh forecast beyond this range. These are estimates, not logged hours or statistical confidence intervals. The range **has not been re-estimated**, and one of its assumptions has failed: no native ARM64 host existed on 2026-09-17. The emulated-first order of work is additional work if the native route is later added on top of it; it replaces work only if the D014 contingency is agreed.

Capacity counted from 2026-09-19 (the day after this forecast), weekends included. The original table of 2026-09-16 counted 34 days from 2026-09-17 (272 h); no credit is computed here for 2026-09-17 and 2026-09-18 because no hours are logged for them.

| Span (inclusive) | Days | Capacity at 8 h/day | Against 225 h | Against 345 h | Mean needed for 225-345 h |
|---|---:|---:|---:|---:|---:|
| 2026-09-19 to 2026-10-20 | 32 | 256 h | +31 h | -89 h | 7.0-10.8 h/day |
| 2026-09-19 to 2026-10-19 (2026-10-20 kept for submitting) | 31 | 248 h | +23 h | -97 h | 7.3-11.1 h/day |
| of which before the full draft (2026-09-19 to 2026-10-07) | 19 | 152 h | — | — | — |
| of which after the full draft is sent (2026-10-08 to 2026-10-19) | 12 | 96 h | — | — | — |

The 2026-10-20 submission is feasible at 8 hours a day only if the remaining effort is close to the lower estimate: 256 h covers the lowest quarter of the range, and the midpoint (285 h) already exceeds it by 29 h. For the middle and upper part of the range it is infeasible unless scope is cut by the order of section 6.8 or the daily hours rise. It must not be represented as a secure date. The binding constraint is earlier than the total: integration, pilot, the campaign or its contingency form, analysis and Chapters 3-6 all have to fit in the 152 h before the full draft, and the 96 h after it (48 h of them inside the feedback window, where only Q0 is planned) cannot absorb that work. The range has no split between work before and after the full draft, so this constraint cannot be checked here: "+31 h" is an upper bound on the margin, not a demonstrated margin, and even at 225 h the date holds only if at least 73 h of the estimate is work that falls after the draft is sent. The eleven days from 2026-10-21 to 2026-10-31 are **not** added to the capacity: using them to absorb the upper part of the range would turn the contingency into the default delivery period. A later deadline creates time, not evidence of completion. The plan gives no split of the range per work package, so the day placements of section 6 are calendar forecasts, not effort estimates. Infrastructure and supervisor waits consume calendar even while independent writing progresses.

Track actual active hours and estimated hours remaining by work package daily. Do not fill historical time logs with invented values. Re-estimate immediately after the first end-to-end functional test, after the native boot if there is one, and after the pilot; those observations resolve the largest uncertainties. The first re-estimate has to separate the hours needed before the full draft from those after it.

## 8. Authority, consistency and preserved history

- `PROGRESS.md` remains the sole operational-state record; its new dated section presents the proposed scope separately from the August rows, which keep their dates, scope and evidence. The accepted G1 remains accepted only for its original scope. New G1B and G2-G7 are not accepted by this document.
- The gate-decision log remains the record of actual acceptance. The supervisor-decision log records responses, not assumptions. Preserve D001-D010 history; new integrated-scope decisions are recorded separately.
- [ADR 0008](../../adr/0008-integrated-yocto-arm64-evaluation.md) — Proposed — pending supervisor agreement (accepted by the student for technical planning only) — would supersede the separate-OS/service interpretation of ADRs 0001/0007 once agreed. Hardware-accelerated virtualisation is distinguished from CPU emulation.
- Public message/API contracts are retained. Protocol/provenance schema changes are future implementation work requiring coordinated validation before freeze.
- The old two-layer academic proposal and existing Word/LaTeX drafts must not be used as current integrated-architecture descriptions until revised. This planning change does not silently rewrite source documents or mark their content approved.
- Preserve existing local changes, original Word/PDF files, raw data, evidence seals and historical plans. Version 1.2 remains unmodified at the canonical path (SHA-256 `c346e4d958d22fad6d4f4635b4176bc2c1b584407199b165a197f94ef0e9fa53`, identical to the file on `dev`), and so do the August scope (`docs/g0/scope_and_rqs.md`) and the August alignment memo (`docs/governance/supervisor_alignment_memo.md`) on which it relies. The paper's evaluation hardware ISA is unspecified; old x86 assertions are not carried forward.

## 9. Verification sources

Source documents and source code were inspected on 2026-09-16. Local build configuration was read without rebuilding or deploying. The platform references establish candidate mechanisms, not this project's successful execution.

- Original theme: workspace `Temas_Tese.pdf`, physical page 3; base paper: workspace `artigos/EdgeGateway_Paper.pdf`, physical pages 34-36 and 41.
- Existing image: `src/yocto/kas/egw-qemuarm64.yml`, `egw-image.bb`, and the sealed `docs/evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/` capsule.
- [AWS-maintained meta-aws](https://github.com/aws/meta-aws/tree/scarthgap) and [demonstration environments](https://github.com/aws4embeddedlinux/meta-aws-demos): native custom-image route, to be pinned and integrated.
- [AWS VM Import/Export requirements](https://docs.aws.amazon.com/vm-import/latest/userguide/prerequisites.html): ARM64 VM import limitation.
- [AWS nested virtualisation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/amazon-ec2-nested-virtualization.html): do not assume Graviton nested KVM.
- [MongoDB 7 production notes](https://www.mongodb.com/docs/v7.0/administration/production-notes/): minimum ARM microarchitecture.
- [Yocto QEMU guidance](https://docs.yoctoproject.org/5.0.19/dev-manual/qemu.html): functional emulation and hardware-accelerated execution must be identified precisely.

## 10. Evidence classes: emulated QEMU/TCG versus native ARM64

Added on 2026-09-18. The same rules are recorded in the amendment of [ADR 0008](../../adr/0008-integrated-yocto-arm64-evaluation.md).

**Facts after 2026-09-16.** On 2026-09-17 no native ARM64 virtual machine had been obtained (the student's attempts with cloud providers had not produced one). The project review therefore ordered an **integrated QEMU/TCG profile first**: the Yocto ARM64 guest emulated on the x86-64 WSL2 workstation, with the six containers inside the guest; the native ARM64 route of section 4 is the subsequent step. On 2026-09-18, in pull request #28 (merged into `dev` on 2026-09-18), the integrated image was built (commit `03e333e`) and booted twice under QEMU/TCG (commit `3209b17`) with every build and boot acceptance check passing. The same day an isolated MongoDB 7.0.39 test passed on that guest (start, write/read, restart, persistence across a guest power cycle); the build, boot and MongoDB records were sealed as technical evidence in `docs/evidence/integrated-qemu/` (pull request #29, merged into `dev` on 2026-09-18). Pull requests #32 (hand-over of the broker secrets and the ACL probe) and #31 (progress counters of the controller) were merged into `dev` the same day; neither has been exercised on the deployed stack. Merging the four pull requests validates no stack and accepts no gate. The six-container stack has **not** been deployed, nothing has been measured, sealing is not acceptance, and no gate and no claim is accepted. The first bounded end-to-end functional test (one smartwatch, 1 Hz, 60 s) was authorised on 2026-09-18 and is in preparation; it has **not** run. The audit of the sealed G1 image (`docs/reviews/2026-09-17-egw-image-audit.md`) and the runbook (`docs/setup/qemu_integrated_gateway.md`) belong to pull request #28. Section 6 was reforecast on 2026-09-18 from the planned submission of 2026-10-20; its dates are forecasts.

| Evidence class | Environment | What it may support |
|---|---|---|
| Emulated | ARM64 guest under QEMU/TCG on the x86-64 workstation | Functional and integration evidence only |
| Native | Non-burstable native ARM64 host, or QEMU/KVM on real ARM64 with verified acceleration (section 4) | Performance and capacity results, and native-boot evidence |

1. **What QEMU/TCG (emulated) runs may demonstrate.** Build and redeployment of the versioned Yocto image; boot; the container runtime; deployment of the six-container stack inside the guest; the functional path smartwatch simulator -> MQTT/TLS -> controller -> Ditto -> API; correctness; fault handling and recovery; persistence. Of these, only the build, the boot and the isolated MongoDB test have been demonstrated so far (section 6.1). Timing observed under emulation may be recorded only as informational and must be labelled emulated.
2. **Still dependent on native ARM64.** Every latency, throughput, saturation and resource trade-off result (RQ3 as worded); any statement about ARM hardware performance or capacity; and the native-boot evidence of the image (EFI/disk layout, cloud-image route).
3. **Permitted performance conclusions.** No conclusion about ARM64 hardware performance or capacity may be drawn from an emulated run. At most, relative observations may be reported, clearly labelled as emulated and not generalised beyond that environment. An emulated result must never be presented as native ARM64 performance evidence, and any academic use of emulated results needs supervisor agreement.
4. **Scope changes that need supervisor agreement.** (a) Adopting the integrated objective, that is, the title and RQ wording of section 1 (decision D011). (b) If no native ARM64 host is obtained in time, re-scoping RQ3 or the evaluation to emulated functional evidence (decision D014). (c) Any academic use of emulated results, whether or not a native host is obtained (rule 3; recorded with D014). These are decisions still to be put to the supervisors: their rows in the [decision log](../supervisor_decision_log.csv) are `proposed_not_sent`, and none may be applied to the dissertation as if it were agreed.

This proposal does not settle which gates may be decided on emulated evidence; G1B is by definition a native boot, and the gate-decision log remains the only record of acceptance.

**Change record:** version 2.0 restores integrated Yocto evaluation, replaces the September operational schedule with the student's 2026-10-20 safety target and 2026-11-03 extension date (wording of 2026-09-16, the dates given here in ISO form), updates effort and platform feasibility, and retains all evidence boundaries. No experiment, supervisor approval, provider allocation or submission is claimed by this update. Amendment of 2026-09-18: published as a proposal with the status box, section 10 and proposal wording; the verbs above describe what the proposal would do if adopted, and version 1.2 remains in force. Second amendment of 2026-09-18: the file moved to `docs/governance/proposals/` and version 1.2 returned, unmodified, to the canonical path; the dates became planned submission 2026-10-20 and final delivery deadline 2026-10-31 with the contingency window 2026-10-21 to 2026-10-31, on the student's confirmation of 2026-09-18 after discussing the dates with the supervisors (a first-party statement; the safety-target and extension-date wording of the first text, including the date 2026-11-03, is superseded and no longer used); sections 6 and 7 were reforecast backwards from the submission date and are labelled as forecasts; prose dates were normalised to ISO 8601. No gate acceptance, RQ change, scope expansion or approval of emulated performance claims follows from the amendment.
