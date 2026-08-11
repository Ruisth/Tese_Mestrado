<!-- GENERATED FILE - DO NOT EDIT.
     Source: latex/chapters/01_introduction.tex
     Regenerate with: python thesis/tools/generate_sections.py
     The LaTeX tree under thesis/latex/ is the single edited source. -->

# Introduction

## Context and Motivation

Consumer wearable devices — smartwatches, smart rings and sensorised clothing — continuously produce streams of personal measurements such as heart rate, skin temperature, blood-oxygen saturation and motion. In the prevailing deployment model, this telemetry is transmitted to vendor-operated cloud platforms, where it is stored, processed and exposed back to the consumer through proprietary applications. Digital twins — synchronised digital representations of physical assets — offer a principled way to organise such device state and make it queryable through uniform interfaces . At the same time, edge computing argues for moving computation and data handling closer to where data is produced, reducing dependence on wide-area connectivity and keeping sensitive data under local control .

This dissertation is developed in the context of the Consumer-Controlled Digital Twin Architecture (C2DTA) proposed by Pinto et al. , which places the consumer, rather than the device vendor, in control of the digital twins of their smart devices. Within that broader architecture, the component studied here is the *edge gateway*: the household-side platform that receives device telemetry, validates it and materialises it as digital twins on local, self-hosted infrastructure.

The engineering motivation is concrete. If a household edge gateway is to be credible, its operating platform must be *reproducible* — buildable from a pinned, versioned configuration rather than assembled by hand — and its digital-twin services must run on the ARM64 architecture that dominates low-power edge hardware. Whether an open-source digital-twin stack, hosted on such a platform, can correctly and reliably absorb the concurrent telemetry of several heterogeneous wearables, and at what resource cost, is an empirical question that requires systematic evidence.

## Problem Statement

The problem addressed by this dissertation is the absence of a reproducible, evidence-backed reference implementation and evaluation of an ARM64 edge gateway for wearable digital twins. Prior work in the C2DTA line evaluated a single smartwatch profile at one message per second on an x86 virtual machine ; it did not demonstrate a Yocto-built platform, ARM64 deployment, concurrent heterogeneous devices, load or robustness scenarios, resource-consumption profiling, or long-duration stability. Component-level studies exist — digital-twin frameworks at the edge , MQTT broker comparisons , container overhead on constrained devices — but they do not compose into a validated, reproducible gateway platform for this use case.

## Research Gap

Within the preliminary corpus assembled so far for this work — seed references from the project context, sources identified by snowballing from them, and preliminary non-institutional searches (Chapter  describes the review protocol and its limits) — we did not identify a published, reproducible evaluation of an edge gateway that combines (i) an operating system image built with the Yocto Project from a pinned configuration for ARM64, (ii) a containerised digital-twin stack based on Eclipse Ditto with an MQTT ingestion path, and (iii) a pre-specified experimental protocol, frozen before data collection, covering correctness, reliability, latency, throughput, resource consumption and long-duration stability under concurrent multi-device wearable telemetry. This combination is the gap this dissertation addresses. The claim is deliberately bounded: it is relative to the preliminary corpus examined at the time of writing, not an absolute statement about all published work. In particular, the institutional database queries prescribed by the review protocol (IEEE Xplore, the ACM Digital Library, and Scopus or Web of Science) have not yet been executed; the gap claim will be re-examined and re-stated once those searches are complete (Section ).

## Research Questions

The dissertation answers three research questions, fixed in the project plan and unchanged since its adoption:

1.  *How can a reproducible Yocto-based ARM64 edge gateway be designed to host containerised digital-twin services?*

2.  *To what extent can the gateway ingest and materialise concurrent synthetic telemetry from three wearable-device types correctly and reliably?*

3.  *What latency, throughput and resource-consumption trade-offs constrain deployment of the proposed platform on an ARM64 edge-class environment?*

RQ1 is a design and constructive question, answered by the artefact itself and by functional evidence of its reproducibility. RQ2 and RQ3 are empirical questions, answered exclusively with data produced by the experimental campaign described in Chapters  and .

## Objectives

The overall objective is to conceive, implement and evaluate a reproducible ARM64 edge gateway, based on the Yocto Project and containerised services, capable of receiving concurrent synthetic telemetry from three wearable-device types, validating the events, and materialising them as digital twins in Eclipse Ditto. This decomposes into the following specific objectives:

1.  Define versioned, normative interfaces for the telemetry path: MQTT topic layout, a common event envelope, per-device JSON Schemas, and WoT Thing Descriptions.

2.  Build a minimal, reproducible operating-system image (`egw-image`) with the Yocto Project Scarthgap LTS line from a pinned `kas` manifest, and validate it functionally on emulated ARM64 (`qemuarm64`) with systemd, networking and an OCI container runtime.

3.  Deploy a minimal ARM64 digital-twin stack — Mosquitto with TLS, Eclipse Ditto (gateway, policies, things), MongoDB and a purpose-built ingestion controller — with all images verified for `linux/arm64` and pinned by digest.

4.  Implement a deterministic, seedable CLI simulator for the three wearable types and six scenarios (`smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload`, `soak`).

5.  Execute a pre-specified experimental campaign on a native ARM64 environment and analyse it with a single reproducible pipeline from raw data to tables and figures.

6.  Deliver a reproducibility package: code, configuration, manifests, raw data, checksums and analysis scripts.

## Contributions

As designed, the dissertation contributes the following artefacts and evidence. Each contribution stands or falls with the evidence presented in Chapter ; none is claimed as demonstrated until that evidence exists.

1.  **A reproducible platform recipe.** A pinned Yocto/Scarthgap configuration (`kas` manifest and custom layer) producing a bootable ARM64 image with a container runtime, together with the documented procedure to rebuild it from a clean checkout.

2.  **A contract-first ingestion architecture.** Normative interfaces (topic layout, event envelope, JSON Schemas, Thing Descriptions, twin model) and a controller design providing validation, idempotent twin updates and structured evidence logging.

3.  **A deterministic wearable workload generator.** A seedable simulator producing reproducible multi-device telemetry across six scenarios, suitable for reuse in comparable studies.

4.  **A pre-specified, reproducible evaluation.** A protocol with fixed metrics, run counts and statistical rules, frozen before data collection, and a campaign whose raw data, manifests and analysis pipeline are archived and re-executable.

5.  **An evidence-bounded characterisation** of the latency, throughput, resource-consumption and stability envelope of the proposed gateway on an ARM64 edge-class environment.

## Scope and Delimitation

The scope is deliberately narrow so that every claim can be backed by evidence produced within the project window:

- Telemetry is *synthetic*, produced by the deterministic simulator; no physical wearables or human-subject data are used.

- Functional platform validation uses QEMU emulation (`qemuarm64`); performance evaluation uses a native ARM64 virtual machine. No performance conclusions are drawn from emulation, and no physical single-board hardware is evaluated.

- The digital-twin stack is a minimal core (Mosquitto, Ditto gateway, policies and things, MongoDB, controller); Ditto search, connectivity and user-interface services are excluded.

- SSI and blockchain elements of the broader C2DTA vision are discussed as context only (Chapter ); they are neither implemented nor evaluated here, and no claims are made about them.

- Exactly three wearable-device types are modelled; graphical interfaces, Bluetooth connectivity, over-the-air updates and energy measurements are out of scope.

## Document Structure

The remainder of this document is organised as follows. Chapter  reviews the background technologies and related work on edge computing, digital twins, embedded Linux, containerisation, MQTT and the Web of Things, and positions this work against the C2DTA line. Chapter  presents the research methodology: a Design Science Research framing, the literature-review protocol, the mapping from research questions to methods and metrics, and the experimental protocol. Chapter  describes the architecture and implementation of the gateway as realised in the project repository. Chapter  reports the evaluation and discusses the results against the research questions, including threats to validity. Chapter  summarises contributions, limitations and future work.
