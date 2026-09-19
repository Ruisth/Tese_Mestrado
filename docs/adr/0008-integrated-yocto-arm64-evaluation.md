# 0008 — Benchmark the service stack on the Yocto-built ARM64 guest

**Date:** 2026-09-16; amended 2026-09-18 (evidence classes, see the last section but one); links and facts updated 2026-09-18 when the plan v2.0 proposal moved under `docs/governance/proposals/`; **amended 2026-09-18 — adopted by the student for project execution with the QEMU-only execution amendment**; **amended 2026-09-19 — supervisor confirmations reported by the student** (see the last section)

**Status:** **Accepted by the student for project execution (2026-09-18), as amended for QEMU-only execution; the academic framing and the QEMU evaluation scope of RQ3 are reported approved, and only D014's limitation and claim wording is open.** Amended 2026-09-19. The student **reports** that the academic title, the research-question wording with RQ3 evaluated in QEMU, and the local-core scope were approved (D011), and that a supervisor approved proceeding with the QEMU tests. Those are **reported by the student**, carry no date, message or supervisor name, and are not documented supervisor decisions. What remains open is the wording of the native-evidence limitation and of claims about emulated timing and resource figures (the open part of D014, whose row is `partly_confirmed_reported_by_student`) and the experimental thresholds and other numerical criteria (D007); the QEMU evaluation scope of RQ3 is reported approved and is not re-requested. *(Corrected 2026-09-19 to match the narrowed D014 row of the [decision log](../governance/supervisor_decision_log.csv); this line previously said the academic use of emulated results was not agreed and D014's academic-use half unanswered. The dated statements below that say so are kept as written and are superseded by this line.)*

**Supersedes, for the adopted execution baseline** (student authority, 2026-09-18): the separate-operating-system/service deployment in [0001](0001-qemu-functional-vs-arm64-vm-performance.md) and [0007](0007-three-tier-platform-model.md). Their historical status is retained, and their rules continue to govern any future native measurement work.

**Authority:** the student's adoption of plan v2.0 with the QEMU-only execution amendment on 2026-09-18, published at the canonical path, [`docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md). That is the student's authority over project execution; it is **not** supervisor approval. Separately, the student reports **supervisor approval to proceed with the QEMU tests** — a supervisor confirmation reported by the student, undated and not a documented supervisor decision. Adopting a plan version accepts no gate and admits no claim, and neither does a reported confirmation.

## Context

The original thesis theme asks for a Yocto-based Linux distribution supporting wearable digital twins on ARM, and for the solution to be tested. The August two-layer proposal described the implemented state accurately but proposed a reduced final evaluation: Yocto boot checks and application benchmarks on a different Linux system. **As at 2026-08 no supervisor approval for that reframing was recorded, and none has been since**: that two-layer wording was never sent, and what the student reports approved in September is the integrated framing of D011, not this one. The student has explicitly requested the integrated objective.

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
- Keep the functional and service layers as a logical decomposition; demonstrate their integration before the pilot and final campaign. **Partly demonstrated on 2026-09-18**: the six-container stack was deployed inside the emulated guest and one bounded end-to-end functional path passed. That evidence is candidate evidence held outside the repository and unsealed; it admits no claim and closes no gate. The nine integration/recovery test families were themselves exercised once on 2026-09-18: functional results were demonstrated for tests 2 and 8 and for the tested checks of test 9, and the specific behaviours of tests 3 (rejection of invalid payloads), 4 (duplicate handling) and 7 (bounded retry under a MongoDB fault, not lossless delivery); test 5 fails its deadline criterion (326 of 2,016 valid events confirmed late); two sub-checks were not run — the sequence-reset sub-check of test 4 (`itest-dup-02`) and the Ditto repeat of test 7 (`itest-ditto-fault-01`), both runbook prose steps that the extracted test commands did not include, so test 7 demonstrated the MongoDB fault only; and the timed harness runs of tests 1 and 6 are invalid. That record is a locally hash-sealed candidate archive held outside the repository, not incorporated into or admitted by the project evidence record, so the battery is **not complete**, nothing has been measured, and it demonstrates nothing at a gate. *(Corrected on 2026-09-19: this bullet first said that seven tests passed and that tests 1 and 6 carried a failing harness part; re-read test by test, the record does not support that.)*
- Image, kernel, runtime, container and measurement changes are recorded and frozen together before citable experiments.
- The implementation remains pending. This ADR records the direction the student has adopted for project execution, not a successful deployment, a closed gate or supervisor approval.

## Amendment of 2026-09-18 — evidence classes and decisions reserved for the supervisors

This amendment changes no part of the decision above; it fixes how evidence is classed for emulated and native runs. It is now in force through section 3.5 of the [adopted plan](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md); the proposal text it was written against is retained under `docs/governance/proposals/` as history.

**Facts.** On 2026-09-17 no native ARM64 virtual machine had been obtained (the student's attempts with cloud providers had not produced one). The project review therefore ordered an integrated QEMU/TCG profile first: the Yocto ARM64 guest emulated on the x86-64 WSL2 workstation, with the six containers inside the guest; the native ARM64 route is the subsequent step. On 2026-09-18, in pull request #28 (merged into `dev` on 2026-09-18), the integrated image was built (commit `03e333e`) and booted twice under QEMU/TCG (commit `3209b17`) with every build and boot acceptance check passing. The same day an isolated MongoDB 7.0.39 test passed on that guest (start, write/read, restart, persistence across a guest power cycle); the build, boot and MongoDB records were sealed as technical evidence in `docs/evidence/integrated-qemu/` (pull request #29, merged into `dev` on 2026-09-18). Pull requests #32 (hand-over of the broker secrets and the ACL probe) and #31 (progress counters of the controller) were merged into `dev` the same day; merging validates no stack and accepts no gate. Later on 2026-09-18 the six-container stack **was** deployed inside the emulated guest and the first bounded end-to-end functional test (one smartwatch, 1 Hz, 60 s) **ran and passed**: 60 sent, 60 delivered unique, 0 lost, 0 late, 0 duplicate, 0 failed, 0 rejected; twin `org.c2dta:5689c879-…` with `last_seq` 59; reconciliation by identity exited 0. The maximum latency observed, 12,286 ms, is an emulated observation and never a performance result. **That evidence is candidate evidence held outside the repository and is unsealed**; sealing is not acceptance, and no gate and no claim is accepted. Two defects were found by the run and fixed on `dev` — the controller was attached to the wrong Compose network (`9ffd365`) and the host shell inherited a relative schema directory (`dc6d8bb`, `22fb0a9`). A memory-cgroup OOM killed the `ditto-things` JVM **during the power-off** of that session at a 512 MiB container limit; the diagnosis of 2026-09-18 records the three Ditto services idling at 94–95 % of that limit, reaching 98.1 % after a 672-message workload, and a controlled `docker compose stop -t 60` after that workload producing no OOM. The corrective work is open and is a separate change; no stability is claimed. **Nothing has been measured**, and the nine integration/recovery test families had not been run when this paragraph was first written; the correction below records what happened later the same day. The audit of the sealed G1 image, `docs/reviews/2026-09-17-egw-image-audit.md`, and the runbook `docs/setup/qemu_integrated_gateway.md` belong to pull request #28.

**Rules.**

1. *What runs under QEMU/TCG (ARM64 emulated on x86-64) may demonstrate.* Build and redeployment of the versioned Yocto image, boot, the container runtime, deployment of the six-container stack inside the guest, the functional path smartwatch simulator -> MQTT/TLS -> controller -> Ditto -> API, correctness, fault handling and recovery, and persistence. This is functional and integration evidence only. Of that list, the build, the boot and the isolated MongoDB test are demonstrated and sealed; the stack deployment and the bounded functional path are demonstrated as **unsealed candidate evidence held outside the repository**; correctness under the nine test families, fault handling, recovery and persistence are not yet demonstrated. Timing observed under emulation may be recorded only as informational and must be labelled emulated.
2. *Dependent on native ARM64.* Any statement about ARM hardware performance or capacity, and the native-boot evidence of the image (EFI/disk layout, cloud-image route). **RQ3 is reworded in the adopted plan, section 3.2**, so that it is bounded to the specified QEMU/TCG environment and does not require any of them; the version 1.2 wording — latency, sustainable throughput, saturation and per-container resource trade-offs on a non-burstable native-ARM64 environment — is withdrawn from scope and becomes future work.
3. *Permitted performance conclusions.* No conclusion about ARM64 hardware performance or capacity may be drawn from an emulated run. At most, relative observations may be reported, clearly labelled as emulated and not generalised beyond that environment. Emulated results are never native ARM64 performance evidence, and their academic use needs supervisor agreement.
4. *Reserved for the supervisors.* (a) The academic title and research-question wording (D011) are **reported approved** by the student, with RQ3 evaluated in QEMU — reported, undated and not a documented supervisor decision; the student's adoption of the plan is not what settled them, and the approved verbatim RQ wording lives in the student manuscript rather than in the repository. (b) The scope of the evaluation and any academic use of emulated results (D014) stay reserved, reworded on 2026-09-18 from a contingency conditional on failing to obtain a native host into a **standing request**, because native deployment has left mandatory scope. Approving the QEMU route, which the student also reports, is not approving the academic use of its results. Both rows are in the [decision log](../governance/supervisor_decision_log.csv), each naming its confirmed and its unresolved part; **D014's academic-use half has been neither sent nor agreed.**

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

**Boundary.** The *student* adopted this. *(Wording of 2026-09-18, superseded by
the amendment of 2026-09-19 below: "The supervisors have approved nothing: not
the title, not the research-question wording, not the thresholds, not the
revised academic evaluation. The student reported that a supervisor advised
proceeding with QEMU tests, which is student-reported advice.")* What holds
after that amendment: the title, the research-question wording and approval to
proceed with the QEMU tests are **reported by the student**, never recorded as
documented supervisor decisions; the **thresholds** (D007) and the **academic
use of emulated results** (D014) are not agreed and their package is unsent.
This amendment closes no gate, admits no claim, seals no evidence and makes no
emulated result native evidence. Every date after 2026-09-18 in the adopted plan
is a planning target.

**Relation to 0001 and 0007.** For the adopted execution baseline this ADR
supersedes their separate-operating-system/service deployment rule, on the
student's authority over project execution. Their recorded status, their
historical context and their rules for any future native measurement work are
retained; their banners are updated accordingly.

## Amendment of 2026-09-19 — supervisor confirmations reported by the student

**What changed.** Nothing in the decision, the rules or the evidence classes.
This amendment records what the student reports and corrects the statements
above that asserted total supervisor silence.

**What is reported.** The state-of-the-art material sent; supervisor approval to
proceed with the QEMU tests; and twelve confirmations — the title, verbatim
*Blockchain-powered Personal AI – Digital Twin Edge Gateway*; the research
questions with RQ3 evaluated in QEMU; the local-core scope; a scoping review as
the literature-review method; an instruction to attempt the historical 95-run
quantity, the 24-hour soak included, under QEMU; that a second operator is not
required; the review schedule; the mandatory institutional LaTeX template; a
mandatory AI-use declaration; an optional article; the authorised wearable-data
terminology; and a local evidence copy. Each is recorded in
[`../governance/supervisor_decision_log.csv`](../governance/supervisor_decision_log.csv)
under a `…_reported_by_student` status, with `sent_at` and `response_at` empty
because no date was reported.

**What is not reported, and stays open.** The experimental thresholds (D007);
the academic use of emulated results and the wording of the limitation that
records the absence of native evidence (D014); the authenticity of the local
template copy with its cover and metadata (inside D004); and the operational
storage semantics (inside D010).

**Consequence for this ADR.** The 95-run composition, with the soak, becomes a
**target to attempt** under QEMU, subject to the bounded pilot's feasibility
check and separate both from the frozen protocol and from the actual valid run
count; that supersedes the QEMU-only amendment's exclusion of it. The waiver of
the second operator removes an acceptance requirement and licenses no
vocabulary: without an independent reconstruction the wording stays *versioned*
and *repeatable build by the author*. Nothing here closes a gate, admits a
claim or turns a reported confirmation into a documented decision.

**One statement of fact corrected.** The statement about the nine
integration/recovery test families in the paragraph of facts above was written
in this change and is corrected there rather than preserved and superseded,
because it never stood on `dev`. What happened: later on 2026-09-18 the nine
families were exercised once; the per-test state is in the Consequences section
above — test 5 fails its deadline criterion, the sequence-reset sub-check of
test 4 and the Ditto repeat of test 7 were not run, and the timed harness runs
of tests 1 and 6 are invalid.
That record is a locally hash-sealed candidate archive held outside the
repository and not admitted, the battery is **not complete**, nothing has been
measured, and the resource-sampler defect is addressed under its own change,
which is not merged into `dev`. *(Corrected on 2026-09-19: this sentence first
said "seven passed, and tests 1 and 6 carry a failing harness part", and that
the instrumentation defect was fixed; both overstated the record.)* The
current position is in the Consequences section above and in
[`../governance/gate_decision_log.md`](../governance/gate_decision_log.md)
(G3).
