<!-- GENERATED FILE - DO NOT EDIT.
     Source: latex/chapters/03_methodology.tex
     Regenerate with: python thesis/tools/generate_sections.py
     The LaTeX tree under thesis/latex/ is the single edited source. -->

# Research Methodology

## Design Science Research Framing

This dissertation follows the DSR paradigm: knowledge is produced by building an innovative artefact for a relevant problem and by rigorously evaluating it . The process is organised according to the methodology of Peffers et al.: problem identification and motivation (Chapter ), definition of solution objectives (Section ), design and development (Chapter ), demonstration and evaluation (Chapter ), and communication through this document and the accompanying reproducibility package .

The build–evaluate cycle is iterated: functional gates (working image boot, end-to-end vertical slice, feature freeze, protocol freeze, data freeze) punctuate development, and the evaluation protocol is frozen *before* the measurement campaign, so that results cannot retroactively shape metrics, conditions or exclusion criteria. The artefact comprises the platform image recipe, the deployed digital-twin stack, the ingestion controller, the simulator, and the experiment harness; the evaluation treats the composed system as the unit of study.

## Literature Review Protocol

The literature study is a *structured scoping/narrative review*, explicitly not a full systematic literature review: it uses systematic elements — logged search strings, dated queries, explicit inclusion/exclusion criteria, deduplication and snowballing — without claiming the exhaustiveness or dual-screening rigour of an SLR. The full protocol, including the search-log and study-selection table specifications, is versioned in the project repository (`thesis/research/literature_review_protocol.md`); this section summarises it.

The protocol prescribes searches on IEEE Xplore, the ACM Digital Library, and Scopus or Web of Science, complemented by primary sources for standards and official documentation. Every query is to be recorded with its date, database, exact string, filters and result counts. Candidate studies pass title/abstract screening and then full-text screening against explicit criteria, with every decision logged with the criterion applied. Bibliographic metadata of every retained source is verified against its primary record (publisher page, Crossref, or standards-body page) before it enters the bibliography. Claims of absence (“no study was identified”) are always bounded by the searches performed to date and never stated absolutely. The review targets at least 30 verified sources, privileging primary studies, standards and official documentation.

At the time of writing, the institutional database queries prescribed above have *not yet been executed*: they require institutional access and are scheduled for the search-execution window of the project plan. Only preliminary non-institutional searches (Crossref queries and open-web checks) have been performed, and only those are logged in the protocol’s search log (`search_log.csv`); the current corpus additionally comprises seed references from the project context, standards and official documentation, and sources identified by snowballing. Every results-dependent statement in this document — in particular the research-gap claim of Section  and the absence statements of Chapter  — is bounded to this preliminary corpus and will be re-stated once the institutional searches are complete.

## Requirements

The solution objectives translate into the following requirement groups, which the architecture chapter traces to design decisions:

- **Reproducibility.** The platform image is built from pinned revisions; container images are digest-pinned and verified for `linux/arm64`; experiments are described by machine-readable manifests; analysis regenerates all tables and figures from raw data.

- **Correctness.** Every telemetry event is validated against a versioned JSON Schema before touching the twin; twin updates are idempotent under at-least-once delivery.

- **Reliability.** The ingestion path tolerates broker disconnects, controller restarts and invalid payloads, with bounded retries and explicit accounting of every message outcome.

- **Observability.** The controller exposes health, readiness and metrics endpoints and writes a per-run structured event log that is the primary measurement source.

- **Security (baseline).** TLS on the external MQTT listener, authenticated access only, least-privilege topic ACLs, and no secrets in version control.

## From Research Questions to Methods and Metrics

Table  fixes the mapping from each research question to the method that answers it and the metrics that constitute the answer. The metrics follow the project plan’s experimental protocol (§7.2 of the plan) and are defined precisely in Section .

| **RQ** | **Method** | **Metrics / evidence** |
|:---|:---|:---|
| RQ1 (design of a reproducible Yocto-based ARM64 gateway) | DSR build of image recipe and stack; functional validation: clean-checkout rebuild, repeated QEMU boots, container-runtime smoke test; architecture documentation | Successful pinned-manifest build; boot to systemd with networking on `qemuarm64` (five boots in the final campaign); OCI container executed on the image; stack time-to-readiness (ten cold starts); ten independent twin creations |
| RQ2 (correct and reliable ingestion of concurrent telemetry) | Controlled experiments with the deterministic simulator: `smoke`, `nominal`, `dropout-reconnect`, `invalid-payload` scenarios; unit, integration and E2E tests; final twin-state verification | Counts of accepted, rejected, duplicate and lost events; delivery rate (unique Ditto confirmations / valid messages sent); correct rejection of invalid payloads; recovery after restart/reconnect; correctness of final state of the three twins |
| RQ3 (latency, throughput and resource trade-offs on ARM64) | Measurement campaign on a native ARM64 VM: ten nominal runs, `load-sweep` at four load levels with randomised order, 24-hour `soak`; per-second resource sampling | Latency MQTT-receive to Ditto-acknowledgement (p50, p95, p99); sustainable throughput and operational saturation point; CPU and RAM per container; soak stability (descriptive) |

Research questions mapped to methods and metrics. {#tab:rq-matrix}

## Experimental Protocol

The protocol is fixed before the campaign (gate “protocol freeze”) and versioned with the repository. Its conditions are:

- **Platform (functional only).** Five QEMU boots of the built image for functional consistency; no performance inference is made from emulation.

- **Stack readiness.** Ten cold starts of the ARM64 stack, measuring time until all services report ready.

- **Twin lifecycle.** Ten independent twin creations.

- **Nominal load.** Ten runs of ten minutes at the nominal aggregate rate, each preceded by a two-minute warm-up excluded from analysis.

- **Load sweep.** Aggregate rates of 10, 50, 100 and 250 messages per second; ten runs of five minutes per level; randomised execution order; two minutes of cool-down between runs.

- **Soak.** One 24-hour run at nominal load, analysed descriptively.

- **Resource sampling.** CPU and RAM collected every second, per container, in all timed executions.

The simulator runs outside the system under test during benchmarks, so that workload generation does not compete for gateway resources, and the primary latency metric is measured entirely inside the controller process (Section ), excluding the external network leg from the gateway-processing measurement. The nominal aggregate rate corresponds to the sum of the three devices’ nominal frequencies and is treated as a scenario definition, not as a previously demonstrated capacity.

## Metrics, Statistics and Validity Rules

Message outcomes are defined as follows: *sent* — a valid message delivered to the MQTT publish call; *received* — the controller observed the message callback; *duplicate* — a `message_id` already processed; *rejected* — a validation failure (deliberate or real); *confirmed* — the Ditto update returned success; *lost* — a valid sent message with no unique confirmation until 60 seconds after the end of the run. The delivery rate is the ratio of unique Ditto confirmations to valid messages sent; deliberately invalid payloads that are correctly rejected do not count as losses.

The primary latency is computed inside the controller as the difference between two monotonic-clock readings in the same process — at the MQTT receive callback and after the Ditto acknowledgement — converted to milliseconds; the simulator’s wall-clock timestamp is not used for latency.

The statistical unit is the *run*, never the individual message. For each condition we report mean, standard deviation and 95% confidence interval across runs, adding median and percentiles for skewed distributions. The soak run is analysed descriptively and receives no confidence interval. *Operational saturation* is defined as the first load level at which at least one of the following holds: loss above 1%, persistent queue growth, p95 latency above one second, or sustained CPU above 90% for 60 seconds. Runs may be excluded only for demonstrated cloud, instrumentation or configuration failures, never merely for slow results; after the data freeze, raw data is immutable and corrections produce a new identified version.

Threats to validity and their mitigations are discussed with the results in Section .
