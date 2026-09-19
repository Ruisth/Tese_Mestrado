# 0001 — Separate functional platform (QEMU) from performance platform (native ARM64 VM)

> **Superseded in part on 2026-09-18, for the adopted execution baseline.** [ADR 0008](0008-integrated-yocto-arm64-evaluation.md) — *Accepted by the student for project execution (2026-09-18), as amended for QEMU-only execution; academic framing reported approved by the student, academic use of emulated results not agreed* — supersedes this ADR's final-deployment rule and its virtualisation classification. The decision below is retained as the **historical record** and as the rule set that would apply to any future native measurement work; it is not a current description of the execution baseline, in which there is no native ARM64 performance platform. **The rules that survive unchanged** are that no performance conclusion of any kind is derived from QEMU runs, that every piece of evidence states its platform, and that data from different execution modes is never mixed in one analysis. The G1 evidence is unchanged. The plan in force is [version 2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md), adopted by the student on 2026-09-18 and amended on 2026-09-19. The supervisor position is split: the thresholds (D007) and the academic use of emulated results (D014) are not agreed and their package is unsent, while the title, the research questions and ten further items are reported confirmed by the student and are nowhere recorded as documented supervisor decisions.

**Status:** Accepted (2026-08-07) — fixed by integrated plan sections 5.1 and 12 (of the archived version 1.0); superseded in part by [0008](0008-integrated-yocto-arm64-evaluation.md) on 2026-09-18

**Extended by:** [0007](0007-three-tier-platform-model.md) (Proposed,
2026-08-12) — the dedicated ARM64 market proved unavailable, so the two-way
split below is refined into three tiers: this ADR separates emulated from
native, and 0007 adds that a *burstable* native instance is admissible for
functional integration but never as a source of numbers. Nothing in this ADR is
withdrawn or weakened by that extension.

## Context

The thesis targets an ARM64 edge gateway, but no physical Raspberry Pi 5 is
available (closed premise, plan section 12). The Yocto-built `egw-image` can be
booted in QEMU (`qemuarm64`), yet QEMU emulation on an x86 host does not produce
performance numbers that are representative of any real ARM64 deployment.
Publishing latency/throughput/resource figures obtained under emulation would be
indefensible, and the previous draft dissertation contained exactly this class
of unsupported quantitative claims.

## Decision

Use two strictly separated platforms:

- **Functional platform — QEMU (`qemuarm64` on WSL2/ext4):** used exclusively
  for Yocto build validation, boot, systemd bring-up, networking and OCI
  container-runtime checks. No performance conclusion of any kind is derived
  from QEMU runs.
- **Performance platform — native ARM64 cloud VM (Hetzner CAX21 or equivalent,
  4 vCPU, 8 GiB RAM, >= 80 GB disk):** hosts the containerised DT stack for the
  entire experimental campaign. Provider, region, exposed CPU, kernel, OS and
  the shared-vCPU limitation are recorded in the environment manifest.

During benchmarks the simulator runs outside the ARM VM; the primary latency
metric is measured inside the controller (see ADR 0005), so the external network
link is excluded from the gateway processing measurement.

## Consequences

- Positive: RQ1 (reproducible Yocto/ARM64 design) is answerable without physical
  hardware; RQ3 numbers come only from native ARM64 execution and are
  defensible; the absence of physical-device evaluation is a declared
  limitation, not a hidden gap.
- Negative: results characterise an ARM64 cloud-VM class of environment, not a
  specific edge board; the shared-vCPU variability must be reported and handled
  statistically (run as the statistical unit, dispersion reported).
- A Raspberry Pi 5 Yocto configuration may be documented as an overlay but is
  never validated and never supports any claim (plan 5.1).
- All evidence must state its platform; mixing QEMU-derived and VM-derived data
  in one analysis is prohibited.
- "Native ARM64 VM" was written before the market forced the distinction between
  a burstable and a non-burstable instance. ADR 0007 supplies it: a burstable
  instance is native, and is still barred from producing numbers, because CPU
  credit throttling would corrupt the load sweep and the saturation criterion.
  Read the two ADRs together when deciding where a number may come from.
