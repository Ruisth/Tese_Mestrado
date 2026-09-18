# Integrated Yocto ARM64 Edge Gateway Dissertation Plan — version 2.0

> **Status — proposal published for review (2026-09-18).** Version 2.0 is a proposal; it is not the plan in force. [Version 1.2](archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2_en.md) remains the published plan in force until the student decides, after consulting the supervisors, whether to adopt this revision. Where the text below says "current", "final" or "must", read it as the content of the proposal. Every date after 2026-09-30 in sections 6 and 7 presupposes an extension that has not been confirmed administratively (see D013). The archived version 1.2 is byte-identical to the published file, so its relative links were written for `docs/governance/` and do not resolve from `archive/`; read them relative to `docs/governance/`.
>
> **Sent to the supervisors:** nothing. The G0 alignment email, the revised [alignment memo](supervisor_alignment_memo.md), decisions D001–D010 and the new decisions D011–D014 are all unsent (`proposed_not_sent` in the [decision log](supervisor_decision_log.csv)). **Approved by the supervisors:** nothing. [ADR 0008](../adr/0008-integrated-yocto-arm64-evaluation.md) is Proposed — pending supervisor agreement (accepted by the student for technical planning only).
>
> Technical preparation and functional integration tests proceed in parallel and do not wait for this review; they adopt no plan and accept no gate or claim. [Section 10](#10-evidence-classes-emulated-qemutcg-versus-native-arm64) fixes what emulated QEMU/TCG runs may demonstrate, what still depends on native ARM64 and which scope changes need supervisor agreement.

**Version/date:** 2.0 — 2026-09-16; amended 2026-09-18 (status box, section 10 and proposal wording)

**Authority:** the student's explicit instruction to correct the plan so that the gateway services are benchmarked on the student's Yocto-built Linux system. This authorises technical planning and preparation; it is not evidence of supervisor approval.

**Internal completion target:** 2026-10-20, ready for submission, including review and formal requirements.

**Institutional dates reported by the student:** 2026-09-30; extension deadline 2026-11-03. This document records those dates without asserting that an administrative extension application has been completed.

**Availability reported:** approximately 8 hours daily, including weekends.

**Proposed to supersede, if adopted:** [version 1.2](archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2_en.md), which remains in force (see the status box). Historical evidence and gate decisions retain their original meaning.

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

The separate article and defence preparation retain their later work package. The 20 October definition of done covers the dissertation, code/evidence package and required submission material; if the supervisors require the separate article before submission, it needs its own effort allocation.

## 3. Reusable evidence and gaps verified on 16 September

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

This is a read-only technical/documentary assessment, not a new build, runtime test or cloud allocation. The new platform image and service compatibility remain to be demonstrated.

## 4. Platform decision and bounded feasibility check

**Preferred AWS route, subject to access and a successful boot:** build a Yocto EC2 ARM64 image and register a custom Graviton AMI. The AWS-maintained `meta-aws` Scarthgap branch provides `aws-ec2-arm64` and `aws-ec2-image`; the observed reference commit on 16 September is `cad59b89c00012ab67d8b4f105714c8aaa5c16a4`. Treat it as a compatibility candidate, not a layer already integrated or proven with this repository's pins. Inspect its dependencies and select an exact revision before building.

The supplied route creates an EFI disk and uses S3 -> EBS `import-snapshot` -> `register-image` with ARM64/UEFI/HVM/ENA. This is distinct from importing a VM with `import-image`; AWS's VM Import/Export support page excludes ARM64 VMs. Verify IAM rights, the generated disk, boot mode, network/storage drivers, console access and cleanup procedures before allocating resources. Review generated helper scripts: use unique image names and do not allow a naming collision to deregister an existing AMI. Dimension the filesystem in advance; do not assume automatic online expansion.

An ordinary Graviton VM must not be assumed to support nested KVM. The preferred route boots Yocto directly as the VM operating system. The existing `c6g.xlarge` suggestion is only a candidate instance class until the custom-image path, CPU requirements, quota, region and costs are confirmed.

**Alternative if promptly available:** an institutional ARM64 host exposing KVM, or an ARM64 bare-metal host with permission to create a hardware-accelerated guest. QEMU/KVM on real ARM64 may host the measured Yocto guest when acceleration is explicitly verified and recorded. QEMU/TCG CPU emulation is never a performance measurement platform: it yields functional and integration evidence only, and any timing taken under it is informational and labelled emulated (section 10). The presence of the word QEMU does not, by itself, identify the execution mode. Do not silently fall back from KVM to TCG.

Use one final platform and image configuration for the campaign. Keep a proposed measurement envelope of 4 vCPU, 8 GiB RAM and at least 80 GiB storage, then verify actual footprint and headroom before freezing it. These are provisioning targets, not measured requirements or guarantees. Non-burstable operation is retained; record shared-host and virtualisation limitations. Keep load generation outside the measured guest.

**Feasibility exit by 19 September:** a selected route with documented image-boot support, access/IAM or KVM capability, resource availability and an approved cost envelope. The previous EUR 30 ceiling is retained as a spending limit pending a new explicit budget decision; the old cost estimate is obsolete. Do not provision a larger or bare-metal resource on the assumption that the old budget covers it.

**Time box:** allocate the first 8-16 active hours to selecting/checking the route and preparing a minimal boot candidate. If the route fails, choose a supported alternative and reforecast; do not spend a week assuming an ordinary ARM VM can run any custom image.

## 5. Implementation work packages and acceptance

1. **Platform-specific Yocto target.** Preserve the G1 target and artefacts. Add a distinct kas/machine configuration and output directory for the chosen VM; pin layers and kernel configuration. Produce the required bootloader/EFI disk, ACPI/PCI and network/storage support. Archive build ID, kernel/rootfs/disk hashes, package manifest and boot configuration. Prove console access, SSH, networking and persistent storage after reboot.
2. **Operational guest.** Add Compose V2 and the exact shell, TLS, time and evidence tools required by the runbook. Remove `debug-tweaks` and passwordless root for the networked target; use SSH keys and controlled service access. Configure clock synchronisation, DNS/CA trust, data-volume ownership, log rotation and adequate space for images/data/soak. Validate cgroup/overlay/network behaviour and required CPU instructions. CFS bandwidth control is needed only if CPU quotas become part of the protocol; record the existing disabled setting rather than inventing a quota experiment.
3. **Service deployment on Yocto.** Build the controller image in a documented build environment with pinned dependencies; transfer/pull verified ARM64 images, identify their digests and deploy the six containers. Add a versioned deployment configuration that removes the current controller `build:` path and identifies the prebuilt image by registry digest, or by a checksummed offline image archive plus verified image/config identity. The existing manifest/digest verification uses Buildx: execute the complete verification on the build/provisioning host and archive it, then verify the deployed identities in the guest. This avoids making Buildx mandatory on the measured guest without weakening the image checks. Prove MQTT/TLS -> controller -> Ditto -> API, then all three profiles, invalid input, duplicate handling, disconnect/reconnect, controller restart and persistent twin state.
4. **Measurement adaptation.** Collect resources, controller events and environment information inside the Yocto guest. Extend the manifest/validity checks to bind each run to the Yocto image, kernel, boot mode, VM and container identities; `uname -m=aarch64` alone is insufficient. Verify clock/window coverage and generated-load delivery. Add targeted regressions for wrong-OS/image provenance and wrong collector location; preserve existing validity requirements.
5. **Pilot and freeze.** Run a short pilot spanning the conditions on the actual integrated system, fix defects, agree the scientific thresholds and freeze the protocol/image/container/environment set. Any runtime/image change affecting measurements after freeze requires revalidation and repetition of affected conditions under new IDs.
6. **Campaign and analysis.** Retain the current plan of 95 runs, including the 24-hour soak, unless a justified amendment is recorded before freeze. Current timed windows/intervals total approximately 32.5 hours before external procedures, startup and repeats; allow 3-5 elapsed days after a valid pilot. Automatic execution is not counted as continuous human work. Historical functional boots may be admitted only by an explicit prospective mapping; do not count them as native-image boots.
7. **Writing and release.** Revise the introduction, RQs, DSR demonstration/evaluation, architecture diagram, methodology and environment tables. Complete results/discussion/conclusions from admitted evidence, then references, abstracts, AI declaration/form, format and visual QA. Prepare the final evidence index, hashes and off-machine copy. Record a real supervisor review and submission separately from technical completion.

## 6. Schedule protecting 20 October

These are target dates, not assertions that the milestones are complete. Writing Chapters 1-4 proceeds alongside platform/integration work.

| Target | Milestone | Required exit evidence |
|---|---|---|
| 19 Sep | G0 platform route and revised alignment package | Boot route/access/budget confirmed; updated scientific scope and review dates sent for discussion |
| 23 Sep | New G1B: native Yocto boot | Identified image running as the VM OS; SSH/network/storage and reboots demonstrated |
| 25 Sep | G2: integrated vertical slice | Services running on Yocto; externally generated event visible through the twin API |
| 29 Sep | G3/G4: correctness and valid pilot | Three profiles/fault tests, reliable collectors, pinned runtime and frozen experimental protocol |
| 5 Oct | G5: valid dataset | Campaign and checksums complete; failed attempts retained; analysis inputs usable |
| 11 Oct | G6: complete dissertation draft | Chapters 1-6, results, conclusions and abstracts sent to the supervisors |
| 16 Oct | Substantive review complete | Comments incorporated; unresolved scientific/format requirements addressed |
| 17-20 Oct | G7: final QA and ready-to-submit package | Final PDF, sources, AI material, references, evidence and backup checked |

Agree a review turnaround allowing comments by 14-15 October; this is a dependency, not an assumed commitment by the supervisors. Send Chapters 1-4 earlier to spread review work. Keep 21 October-3 November as contingency, not planned feature time.

**Escalation/reforecast:** no supported platform route by 19 September, no integrated trace by 25 September, no valid pilot by 29 September, no valid dataset by 5 October, or no reviewer window materially threatens 20 October. Report the failed milestone and remaining effort immediately. Preserve the integrated Yocto objective; reverting to Ubuntu benchmarks requires a new explicit scope decision, not an unreported shortcut.

## 7. Revised effort and feasibility

The previous estimate of 180-260 active hours assumed separately evaluated operating-system and service layers. The correction adds approximately 30-60 technical hours for VM-image adaptation, guest completion and integration revalidation, plus 12-24 writing/review hours. The technical increment includes cloud-image preparation; it must not be added again as a separate full cloud work package. Existing bug/review reserves are not duplicated.

**Updated planning range: approximately 225-345 active hours remaining** (rounded from 222-344). It assumes reuse of existing code/text, an available supported platform route and one substantial supervisor revision. Serious provider-access or boot incompatibilities require a fresh forecast beyond this range. These are estimates, not logged hours or statistical confidence intervals.

Counting 17 September through the target date, including weekends:

| Date | Days | Capacity at 8 h/day | Mean needed for 225-345 h |
|---|---:|---:|---:|
| 20 October | 34 | 272 h | 6.6-10.1 h/day |
| 3 November | 48 | 384 h | 4.7-7.2 h/day |

The 20 October target remains, but it is achievable only towards the favourable/middle part of the effort range: capacity exceeds the lower estimate by 47 hours and falls short of the upper estimate by 73 hours. It must not be represented as a secure date across all scenarios. The student-reported extension date, if confirmed, accommodates the range more plausibly, with 39-159 nominal hours remaining; reserve the final days for corrections/submission. Infrastructure and supervisor waits consume calendar even while independent writing progresses.

Track actual active hours and estimated hours remaining by work package daily. Do not fill historical time logs with invented values. Re-estimate immediately after native boot and after the pilot; those observations resolve the largest uncertainties.

## 8. Authority, consistency and preserved history

- `PROGRESS.md` remains the sole operational-state record; its new dated section presents the proposed scope separately from the August rows, which keep their dates, scope and evidence. The accepted G1 remains accepted only for its original scope. New G1B and G2-G7 are not accepted by this document.
- The gate-decision log remains the record of actual acceptance. The supervisor-decision log records responses, not assumptions. Preserve D001-D010 history; new integrated-scope decisions are recorded separately.
- [ADR 0008](../adr/0008-integrated-yocto-arm64-evaluation.md) — Proposed — pending supervisor agreement (accepted by the student for technical planning only) — would supersede the separate-OS/service interpretation of ADRs 0001/0007 once agreed. Hardware-accelerated virtualisation is distinguished from CPU emulation.
- Public message/API contracts are retained. Protocol/provenance schema changes are future implementation work requiring coordinated validation before freeze.
- The old two-layer academic proposal and existing Word/LaTeX drafts must not be used as current integrated-architecture descriptions until revised. This planning change does not silently rewrite source documents or mark their content approved.
- Preserve existing local changes, original Word/PDF files, raw data, evidence seals and historical plans. Version 1.2 was archived byte-for-byte (SHA-256 `c346e4d958d22fad6d4f4635b4176bc2c1b584407199b165a197f94ef0e9fa53`). The paper's evaluation hardware ISA is unspecified; old x86 assertions are not carried forward.

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

Added on 2026-09-18. The same rules are recorded in the amendment of [ADR 0008](../adr/0008-integrated-yocto-arm64-evaluation.md).

**Facts after 2026-09-16.** On 2026-09-17 no native ARM64 virtual machine had been obtained (the student's attempts with cloud providers had not produced one). The project review therefore ordered an **integrated QEMU/TCG profile first**: the Yocto ARM64 guest emulated on the x86-64 WSL2 workstation, with the six containers inside the guest; the native ARM64 route of section 4 is the subsequent step. On 2026-09-18, in pull request #28 (merged into `dev` on 2026-09-18), the integrated image was built (commit `03e333e`) and booted twice under QEMU/TCG (commit `3209b17`) with every build and boot acceptance check passing. The same day an isolated MongoDB 7.0.39 test passed on that guest (start, write/read, restart, persistence across a guest power cycle); the build, boot and MongoDB records were sealed as technical evidence in `docs/evidence/integrated-qemu/` (pull request #29, merged into `dev` on 2026-09-18). The six-container stack has **not** been deployed, nothing has been measured, sealing is not acceptance, and no gate and no claim is accepted. The audit of the sealed G1 image (`docs/reviews/2026-09-17-egw-image-audit.md`) and the runbook (`docs/setup/qemu_integrated_gateway.md`) belong to pull request #28. The target dates of section 6 were written on 2026-09-16 and have not been reforecast here; the escalation rule of section 6 applies to the platform route.

| Evidence class | Environment | What it may support |
|---|---|---|
| Emulated | ARM64 guest under QEMU/TCG on the x86-64 workstation | Functional and integration evidence only |
| Native | Non-burstable native ARM64 host, or QEMU/KVM on real ARM64 with verified acceleration (section 4) | Performance and capacity results, and native-boot evidence |

1. **Demonstrated under QEMU/TCG (emulated).** Build and redeployment of the versioned Yocto image; boot; the container runtime; deployment of the six-container stack inside the guest; the functional path smartwatch simulator -> MQTT/TLS -> controller -> Ditto -> API; correctness; fault handling and recovery; persistence. Timing observed under emulation may be recorded only as informational and must be labelled emulated.
2. **Still dependent on native ARM64.** Every latency, throughput, saturation and resource trade-off result (RQ3 as worded); any statement about ARM hardware performance or capacity; and the native-boot evidence of the image (EFI/disk layout, cloud-image route).
3. **Permitted performance conclusions.** No conclusion about ARM64 hardware performance or capacity may be drawn from an emulated run. At most, relative observations may be reported, clearly labelled as emulated and not generalised beyond that environment. An emulated result must never be presented as native ARM64 performance evidence, and any academic use of emulated results needs supervisor agreement.
4. **Scope changes that need supervisor agreement.** (a) Adopting the integrated objective, that is, the title and RQ wording of section 1 (decision D011). (b) If no native ARM64 host is obtained in time, re-scoping RQ3 or the evaluation to emulated functional evidence (decision D014). (c) Any academic use of emulated results, whether or not a native host is obtained (rule 3; recorded with D014). These are decisions still to be put to the supervisors: their rows in the [decision log](supervisor_decision_log.csv) are `proposed_not_sent`, and none may be applied to the dissertation as if it were agreed.

This proposal does not settle which gates may be decided on emulated evidence; G1B is by definition a native boot, and the gate-decision log remains the only record of acceptance.

**Change record:** version 2.0 restores integrated Yocto evaluation, replaces the September operational schedule with the student's 20 October safety target and 3 November extension date, updates effort and platform feasibility, and retains all evidence boundaries. No experiment, supervisor approval, provider allocation or submission is claimed by this update. Amendment of 2026-09-18: published as a proposal with the status box, section 10 and proposal wording; the verbs above describe what the proposal would do if adopted, and version 1.2 remains in force.
