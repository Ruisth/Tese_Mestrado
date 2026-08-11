<!-- GENERATED FILE - DO NOT EDIT.
     Source: latex/chapters/06_conclusions.tex
     Regenerate with: python thesis/tools/generate_sections.py
     The LaTeX tree under thesis/latex/ is the single edited source. -->

# Conclusions and Future Work

## Summary

This dissertation designs and implements a reproducible ARM64 edge gateway for digital twins of wearable devices: a Yocto-defined platform image intended to host a containerised stack of Mosquitto, a purpose-built ingestion controller, Eclipse Ditto and MongoDB, exercised by a deterministic three-device simulator. Its evaluation follows the pre-specified experimental protocol of Chapter , frozen before data collection, and is reported in Chapter  once the measurement campaign completes; no evaluation result is claimed in advance of that evidence. **\[TODO: pending data-v1 — complete the summary with what the evidence actually demonstrated, after Chapter  is populated.**

## Contributions Demonstrated

**\[TODO: pending data-v1 — restate the designed contributions of Section  strictly in terms of what the evidence in Chapter  supports; each demonstrated contribution must cite its evidence via the claim–evidence matrix. Contributions not supported by evidence are reported as limitations instead.**

## Answers to the Research Questions

**\[TODO: pending data-v1 — one concise paragraph per research question (RQ1–RQ3), consistent with Section ; no new claims may appear here that are not in Chapter .**

## Limitations

The following limitations are inherent to the study design and hold regardless of the campaign outcomes:

- All telemetry is synthetic; no physical wearables, real users or clinical-grade signals are involved.

- Performance evidence is to come from a single native ARM64 cloud VM with shared vCPUs; no physical single-board or embedded hardware is evaluated, and platform evidence from emulation is functional only.

- The stack under evaluation is a minimal digital-twin core; Ditto search and connectivity services, horizontal scaling and multi-gateway federation are not studied.

- The security configuration is a baseline (TLS, authentication, least-privilege ACLs) and is not subjected to a security evaluation.

- The identity, ledger and marketplace aspects of the broader C2DTA vision are out of scope; nothing in this work validates them.

- **\[TODO: pending data-v1 — add limitations that emerge from the campaign itself (e.g. conditions removed, variance observed, exclusions applied).\]**

## Future Work

Several directions follow naturally from this work:

- **Physical edge hardware.** Repeating the campaign on physical ARM64 single-board hardware, which was deliberately excluded from the scope of this project and about which this work makes no claims.

- **Identity integration.** A minimal decentralised-identity agent alongside the twin stack — kept strictly conditional and out of the core in this project — evaluated first for deployment feasibility and resource footprint on ARM64.

- **Richer device ecosystems.** More device types, device onboarding/offboarding dynamics, and multi-gateway topologies.

- **Stack breadth.** Enabling and measuring Ditto search and connectivity services, and comparing alternative brokers or twin frameworks under the same protocol and harness.

- **Longer horizons.** Multi-day soaks, upgrade-in-place of the Yocto image, and lifecycle management of digest-pinned services.
