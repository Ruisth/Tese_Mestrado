# 0008 — Benchmark the service stack on the Yocto-built ARM64 guest

**Date:** 2026-09-16; amended 2026-09-18 (evidence classes and proposal status, see the last section)

**Status:** Proposed — pending supervisor agreement (accepted by the student for technical planning only). The decision has not been sent to the supervisors and nothing in it is approved by them.

**Would supersede, once agreed:** the separate-operating-system/service deployment in [0001](0001-qemu-functional-vs-arm64-vm-performance.md) and [0007](0007-three-tier-platform-model.md). Until then both keep their recorded status.

**Authority:** [integrated plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md), itself a proposal published for review; [plan v1.2](../governance/archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2_en.md) remains the plan in force until the student decides after consulting the supervisors.

## Context

The original thesis theme asks for a Yocto-based Linux distribution supporting wearable digital twins on ARM, and for the solution to be tested. The August two-layer proposal described the implemented state accurately but proposed a reduced final evaluation: Yocto boot checks and application benchmarks on a different Linux system. No supervisor approval for that reframing is recorded. The student has now explicitly requested the integrated objective.

## Decision

The final system under test boots the versioned Yocto-produced kernel and root filesystem on a supported native ARM64 virtual machine. The container runtime and all six gateway containers execute in that guest. Resource collection and runtime provenance come from the same guest; the simulator and campaign orchestration run outside it.

QEMU/TCG emulation on the existing x86-64 WSL host remains useful for functional checks and contributes no ARM hardware performance result. QEMU/KVM on an ARM64 host is a different execution mode and can host the measured guest if hardware acceleration, exposed CPU, resource envelope and virtualisation limits are verified. Never infer KVM availability from the label ARM64 or silently fall back to TCG. See the amendment of 2026-09-18 for what emulated runs may demonstrate and for the contingency reserved for the supervisors (D014).

For AWS, investigate the versioned `meta-aws` Scarthgap custom AMI route first. Yocto boots directly as the Graviton VM OS; ordinary Graviton nested KVM is not a prerequisite or an assumption. A separate institutional ARM64/KVM host is an alternative only when genuinely available. The current image is not cloud-ready: platform drivers/boot disk, deployment tooling, operational access and integrated service checks still need work.

## Consequences

- The old G1 build/boot evidence remains valid for its original functional scope. New native-image boot evidence is required; no historical seal is changed.
- Ubuntu may be a build, administration or temporary diagnostic environment. Ubuntu-hosted service measurements cannot be relabelled as the final Yocto-based campaign.
- A Yocto filesystem used only as a container/chroot is insufficient because the measured kernel would still be the outer host's kernel.
- An ARM64 cloud result characterises that guest/platform configuration. It does not prove performance on a physical gateway, universal image portability, superiority over Ubuntu or the full C2DTA identity/blockchain architecture.
- Keep the functional and service layers as a logical decomposition; demonstrate their integration before the pilot and final campaign.
- Image, kernel, runtime, container and measurement changes are recorded and frozen together before citable experiments.
- The implementation remains pending. This ADR records the direction the student has authorised for technical planning, not a successful deployment, a closed gate or supervisor approval.

## Amendment of 2026-09-18 — evidence classes and decisions reserved for the supervisors

This amendment changes no part of the decision above; it fixes how evidence is classed for emulated and native runs. It matches [plan v2.0, section 10](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).

**Facts.** On 2026-09-17 no native ARM64 virtual machine had been obtained (the student's attempts with cloud providers had not produced one). The project review therefore ordered an integrated QEMU/TCG profile first: the Yocto ARM64 guest emulated on the x86-64 WSL2 workstation, with the six containers inside the guest; the native ARM64 route is the subsequent step. On 2026-09-18, in pull request #28 (merged into `dev` on 2026-09-18), the integrated image was built (commit `03e333e`) and booted twice under QEMU/TCG (commit `3209b17`) with every build and boot acceptance check passing. The same day an isolated MongoDB 7.0.39 test passed on that guest (start, write/read, restart, persistence across a guest power cycle); it is recorded in the separate draft pull request #29, branch `evidence/integrated-qemu-2026-09-18` (commit `f03c92c`, not on `dev`), which proposes to seal the build, boot and MongoDB records, and not in pull request #28. The six-container stack has not been deployed, nothing has been measured, the evidence is candidate evidence and none of it is sealed on `dev`, sealing would not be acceptance, and no gate and no claim is accepted. The audit of the sealed G1 image, `docs/reviews/2026-09-17-egw-image-audit.md`, and the runbook `docs/setup/qemu_integrated_gateway.md` belong to pull request #28.

**Rules.**

1. *Demonstrated under QEMU/TCG (ARM64 emulated on x86-64).* Build and redeployment of the versioned Yocto image, boot, the container runtime, deployment of the six-container stack inside the guest, the functional path smartwatch simulator -> MQTT/TLS -> controller -> Ditto -> API, correctness, fault handling and recovery, and persistence. This is functional and integration evidence only. Timing observed under emulation may be recorded only as informational and must be labelled emulated.
2. *Dependent on native ARM64.* Every latency, throughput, saturation and resource trade-off result (RQ3 as worded), any statement about ARM hardware performance or capacity, and the native-boot evidence of the image (EFI/disk layout, cloud-image route).
3. *Permitted performance conclusions.* No conclusion about ARM64 hardware performance or capacity may be drawn from an emulated run. At most, relative observations may be reported, clearly labelled as emulated and not generalised beyond that environment. Emulated results are never native ARM64 performance evidence, and their academic use needs supervisor agreement.
4. *Reserved for the supervisors.* Adopting the integrated objective (title and RQ wording), and — if no native ARM64 host is obtained in time — re-scoping RQ3 or the evaluation to emulated functional evidence; and any academic use of emulated results, whether or not a native host is obtained (rule 3). They are recorded as D011 and D014 in the [decision log](../governance/supervisor_decision_log.csv) with the status `proposed_not_sent`; none has been sent or agreed.
