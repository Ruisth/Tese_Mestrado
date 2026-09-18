# 0008 — Benchmark the service stack on the Yocto-built ARM64 guest

**Date:** 2026-09-16; amended 2026-09-18 (evidence classes, see the last section but one); links and facts updated 2026-09-18 when the plan v2.0 proposal moved under `docs/governance/proposals/`; **amended 2026-09-18 — adopted by the student for project execution with the QEMU-only execution amendment** (see the last section)

**Status:** **Accepted by the student for project execution (2026-09-18), as amended for QEMU-only execution — not agreed by the supervisors.** The decision has not been sent to them, nothing in it is approved by them, and **supervisor validation of the academic framing remains pending**: the academic title and research-question wording are decision D011, and the scope of the evaluation and any academic use of emulated results are decision D014. Both are `proposed_not_sent`.

**Supersedes, for the adopted execution baseline** (student authority, 2026-09-18): the separate-operating-system/service deployment in [0001](0001-qemu-functional-vs-arm64-vm-performance.md) and [0007](0007-three-tier-platform-model.md). Their historical status is retained, and their rules continue to govern any future native measurement work.

**Authority:** the student's adoption of plan v2.0 with the QEMU-only execution amendment on 2026-09-18, published at the canonical path, [`docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md). That is the student's authority over project execution; it is **not** supervisor approval. The student reported that a supervisor advised proceeding with QEMU tests: that is student-reported advice, not approval and not a documented supervisor decision. Adopting a plan version accepts no gate and admits no claim.

## Context

The original thesis theme asks for a Yocto-based Linux distribution supporting wearable digital twins on ARM, and for the solution to be tested. The August two-layer proposal described the implemented state accurately but proposed a reduced final evaluation: Yocto boot checks and application benchmarks on a different Linux system. No supervisor approval for that reframing is recorded. The student has now explicitly requested the integrated objective.

## Decision

The system under test boots the versioned Yocto-produced kernel and root filesystem **under QEMU/TCG on the existing x86-64 workstation**. The container runtime and all six gateway containers execute in that guest. Resource collection and runtime provenance come from the same guest; the simulator and campaign orchestration run outside it. Native ARM64 deployment is documented, unverified future work and is not a condition for completing the implementation, the functional tests or the dissertation.

*(Original wording of the paragraph above, 2026-09-16, superseded by the amendment of 2026-09-18: "The final system under test boots the versioned Yocto-produced kernel and root filesystem on a supported native ARM64 virtual machine.")*

**QEMU/TCG emulation contributes no ARM hardware performance result.** This is the operative rule of the adopted baseline, not a qualification of it: emulated runs yield functional and integration evidence only. QEMU/KVM on an ARM64 host is a different execution mode and could host a measured guest if hardware acceleration, exposed CPU, resource envelope and virtualisation limits were verified; that is future work. Never infer KVM availability from the label ARM64 or silently fall back to TCG. See the amendment of 2026-09-18 on evidence classes for what emulated runs may demonstrate and for the decisions reserved for the supervisors (D011, D014).

### Later native deployment (future work, not a prerequisite)

For AWS, the versioned `meta-aws` Scarthgap custom AMI route would be investigated first. Yocto boots directly as the Graviton VM OS; ordinary Graviton nested KVM is not a prerequisite or an assumption. A separate institutional ARM64/KVM host is an alternative only when genuinely available. **The current image is not cloud-ready**: platform drivers and boot disk, deployment tooling, operational access and integrated service checks would all still need work. This is reuse guidance for a possible later port; none of it is required by the adopted baseline, and no allocation or spending is requested.

## Consequences

- The old G1 build/boot evidence remains valid for its original functional scope. Native-image boot evidence is **future work**, not a requirement of this baseline; no historical seal is changed.
- Ubuntu may be a build, administration or temporary diagnostic environment. Ubuntu-hosted service measurements cannot be relabelled as the final Yocto-based campaign.
- A Yocto filesystem used only as a container/chroot is insufficient because the measured kernel would still be the outer host's kernel.
- An ARM64 cloud result characterises that guest/platform configuration. It does not prove performance on a physical gateway, universal image portability, superiority over Ubuntu or the full C2DTA identity/blockchain architecture.
- Keep the functional and service layers as a logical decomposition; demonstrate their integration before the pilot and final campaign. **Partly demonstrated on 2026-09-18**: the six-container stack was deployed inside the emulated guest and one bounded end-to-end functional path passed. That evidence is candidate evidence held outside the repository and unsealed; it admits no claim and closes no gate, and the nine integration/recovery test families remain unrun.
- Image, kernel, runtime, container and measurement changes are recorded and frozen together before citable experiments.
- The implementation remains pending. This ADR records the direction the student has adopted for project execution, not a successful deployment, a closed gate or supervisor approval.

## Amendment of 2026-09-18 — evidence classes and decisions reserved for the supervisors

This amendment changes no part of the decision above; it fixes how evidence is classed for emulated and native runs. It is now in force through section 3.5 of the [adopted plan](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md); the proposal text it was written against is retained under `docs/governance/proposals/` as history.

**Facts.** On 2026-09-17 no native ARM64 virtual machine had been obtained (the student's attempts with cloud providers had not produced one). The project review therefore ordered an integrated QEMU/TCG profile first: the Yocto ARM64 guest emulated on the x86-64 WSL2 workstation, with the six containers inside the guest; the native ARM64 route is the subsequent step. On 2026-09-18, in pull request #28 (merged into `dev` on 2026-09-18), the integrated image was built (commit `03e333e`) and booted twice under QEMU/TCG (commit `3209b17`) with every build and boot acceptance check passing. The same day an isolated MongoDB 7.0.39 test passed on that guest (start, write/read, restart, persistence across a guest power cycle); the build, boot and MongoDB records were sealed as technical evidence in `docs/evidence/integrated-qemu/` (pull request #29, merged into `dev` on 2026-09-18). Pull requests #32 (hand-over of the broker secrets and the ACL probe) and #31 (progress counters of the controller) were merged into `dev` the same day; merging validates no stack and accepts no gate. Later on 2026-09-18 the six-container stack **was** deployed inside the emulated guest and the first bounded end-to-end functional test (one smartwatch, 1 Hz, 60 s) **ran and passed**: 60 sent, 60 delivered unique, 0 lost, 0 late, 0 duplicate, 0 failed, 0 rejected; twin `org.c2dta:5689c879-…` with `last_seq` 59; reconciliation by identity exited 0. The maximum latency observed, 12,286 ms, is an emulated observation and never a performance result. **That evidence is candidate evidence held outside the repository and is unsealed**; sealing is not acceptance, and no gate and no claim is accepted. Two defects were found by the run and fixed on `dev` — the controller was attached to the wrong Compose network (`9ffd365`) and the host shell inherited a relative schema directory (`dc6d8bb`, `22fb0a9`). A memory-cgroup OOM killed the `ditto-things` JVM **during the power-off** of that session at a 512 MiB container limit; the diagnosis of 2026-09-18 records the three Ditto services idling at 94–95 % of that limit, reaching 98.1 % after a 672-message workload, and a controlled `docker compose stop -t 60` after that workload producing no OOM. The corrective work is open and is a separate change; no stability is claimed. **None of the nine integration/recovery test families has been run, and nothing has been measured.** The audit of the sealed G1 image, `docs/reviews/2026-09-17-egw-image-audit.md`, and the runbook `docs/setup/qemu_integrated_gateway.md` belong to pull request #28.

**Rules.**

1. *What runs under QEMU/TCG (ARM64 emulated on x86-64) may demonstrate.* Build and redeployment of the versioned Yocto image, boot, the container runtime, deployment of the six-container stack inside the guest, the functional path smartwatch simulator -> MQTT/TLS -> controller -> Ditto -> API, correctness, fault handling and recovery, and persistence. This is functional and integration evidence only. Of that list, the build, the boot and the isolated MongoDB test are demonstrated and sealed; the stack deployment and the bounded functional path are demonstrated as **unsealed candidate evidence held outside the repository**; correctness under the nine test families, fault handling, recovery and persistence are not yet demonstrated. Timing observed under emulation may be recorded only as informational and must be labelled emulated.
2. *Dependent on native ARM64.* Any statement about ARM hardware performance or capacity, and the native-boot evidence of the image (EFI/disk layout, cloud-image route). **RQ3 is reworded in the adopted plan, section 3.2**, so that it is bounded to the specified QEMU/TCG environment and does not require any of them; the version 1.2 wording — latency, sustainable throughput, saturation and per-container resource trade-offs on a non-burstable native-ARM64 environment — is withdrawn from scope and becomes future work.
3. *Permitted performance conclusions.* No conclusion about ARM64 hardware performance or capacity may be drawn from an emulated run. At most, relative observations may be reported, clearly labelled as emulated and not generalised beyond that environment. Emulated results are never native ARM64 performance evidence, and their academic use needs supervisor agreement.
4. *Reserved for the supervisors.* (a) The academic title and research-question wording (D011), which the student's adoption of the plan does **not** settle. (b) The scope of the evaluation and any academic use of emulated results (D014), reworded on 2026-09-18 from a contingency conditional on failing to obtain a native host into a **standing request**, because native deployment has left mandatory scope. They are recorded as D011 and D014 in the [decision log](../governance/supervisor_decision_log.csv) with the status `proposed_not_sent`; **none has been sent or agreed.**

## Amendment of 2026-09-18 — QEMU-only execution scope, adopted by the student

**What changed.** On 2026-09-18 the student adopted plan v2.0 with a dated
QEMU-only execution amendment and published it at the canonical path. This ADR
is amended to match. The system under test is the Yocto-produced ARM64 kernel
and root filesystem booted **under QEMU/TCG on the existing x86-64 workstation**,
with the container runtime and all six containers inside that guest. A native
ARM64 virtual machine is no longer the final execution target of the decision.

**What leaves mandatory scope.** The native ARM64 host, the procurement
dependency and its budget decision, the native-host decision deadline, the
48-hour fallback rule and the native Yocto boot formerly tracked as gate G1B.
They are **deferred, not deleted**: native deployment becomes documented,
unverified future work, described in section 8 of the adopted plan. No cloud
allocation, provisioning or spending is requested. The EUR 30 ceiling stands
only as a limit that would apply if native work were ever authorised (D012).

**What is retained unchanged.** The integrated objective and the requirement
that the measured guest actually boot the Yocto-produced kernel and root
filesystem; the rejection of a Yocto filesystem used only as a container or
chroot; digest-pinned ARM64 images; the evidence classes and the four rules
above; the distinction between verified hardware virtualisation and CPU
emulation; the bar on numbers from a burstable instance and the tiering rules of
[0007](0007-three-tier-platform-model.md) for any future native work; the
prohibition on pooling execution modes in one aggregate; and the rule that a
later successful native port does not retrofit emulated results into native
evidence.

**Boundary.** The *student* adopted this. **The supervisors have approved
nothing**: not the title, not the research-question wording, not the
thresholds, not the revised academic evaluation. The student reported that a
supervisor advised proceeding with QEMU tests, which is student-reported advice
and not a supervisor decision. Supervisor validation of the academic framing
remains pending through D011 and D014. This amendment closes no gate, admits no
claim, seals no evidence and makes no emulated result native evidence. Every
date after 2026-09-18 in the adopted plan is a planning target.

**Relation to 0001 and 0007.** For the adopted execution baseline this ADR
supersedes their separate-operating-system/service deployment rule, on the
student's authority over project execution. Their recorded status, their
historical context and their rules for any future native measurement work are
retained; their banners are updated accordingly.
