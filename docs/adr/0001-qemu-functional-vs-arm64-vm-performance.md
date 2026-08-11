# 0001 — Separate functional platform (QEMU) from performance platform (native ARM64 VM)

**Status:** Accepted (2026-08-07) — fixed by integrated plan sections 5.1 and 12

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
