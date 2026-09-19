# Literature Review Protocol — Scoping Review

Version 2.0 — 2026-09-19 (v1.1 — 2026-08-14; v1.0 — 2026-08-07). This revision
designates the review a **scoping review**, adds the review question and its
Population/Concept/Context framing, the reporting framework, the charting
fields, the required outputs, the completion criterion, the limitations and a
working schedule. It repoints the normative basis at the adopted plan v2.0. It
executes no search, screens no record and charts no study.
Normative basis: the adopted integrated plan v2.0
([`../../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)),
which supersedes the plan v1.2 that versions 1.0 and 1.1 of this protocol cited;
the review method and the source target originate in archived plan v1.0 §6.2 and
are carried forward as recorded below;
summarised in the dissertation, Chapter 3, Section "Literature Review Protocol".

> **Status note — 2026-08-08.** The institutional database queries required by
> Section 3 (IEEE Xplore, ACM Digital Library, Scopus/Web of Science) have
> **not yet been executed**: they require institutional access and are a
> pending student action, scheduled for the search-execution window of
> 2026-08-10 to 2026-08-30 (archived plan v1.0 §8; the writing window in the
> current plan is section 4). What exists as of this date is the
> preliminary corpus for the advisor draft of Chapter 2: 25 verified entries
> in `thesis/refs/references.bib`, every one registered in
> `study_selection.csv` with its honest provenance (`known-source` seeds,
> standards and official documentation, and `compass-lead` candidates), and
> `search_log.csv` containing **only** the preliminary non-institutional
> searches actually performed (Crossref API and open web), labelled as such.
> No IEEE/ACM/Scopus/WoS query has been logged because none has been run.
> Peer-reviewed papers included at this stage are marked
> `stage = title_abstract` with a provisional-inclusion note; the full-text
> screening pass and the institutional queries remain to be done under this
> protocol, and all absence/gap claims in the dissertation remain bounded to
> the sources examined so far.

> **Status note — 2026-09-19.** The statement above is still accurate on the
> point that matters: **the formal search has not been executed.** `search_log.csv`
> still holds exactly three rows, `Q001`–`Q003`, all dated 2026-08-08 and all
> labelled preliminary and non-institutional; `study_selection.csv` still holds
> 25 candidate rows, of which 7 have reached `stage = full_text` and 18 remain
> at `stage = title_abstract`. No IEEE Xplore, ACM Digital Library, Scopus or
> Web of Science query has been run under this protocol. The
> search-execution window named in the 2026-08-08 note has passed unused; the
> replacement working targets are in Section 18. This protocol revision is
> **not registered and not preregistered**, and its publication is not evidence
> that any stage of the review has been carried out.

## 1. Method designation

This review is a **scoping review**, conducted and reported as such.

> **Designation corrected — 2026-09-19.** Versions 1.0 and 1.1 of this protocol
> designated the study a "structured scoping/narrative review" and stated that
> it was "explicitly NOT a full systematic literature review (SLR)", claiming
> neither exhaustive coverage, dual independent screening, formal quality
> appraisal nor PRISMA compliance. That combined label is **superseded**. The
> student reports that the supervisor confirmed a **scoping review** in a
> follow-up; the review type is settled by that reported confirmation and is
> not reopened here. The confirmation is recorded as **reported by the student**,
> not as a documented supervisor decision, and it is registered against D003 in
> [`../../docs/governance/supervisor_decision_log.csv`](../../docs/governance/supervisor_decision_log.csv).
> The earlier text is not deleted from the project's history; it is corrected
> from this date forward. Nothing in the correction closes a gate or admits a
> claim, and selecting a label completes no part of the review.

Consequences of the designation, all of which remain true of the work actually
done:

- The dissertation never describes this review as a systematic literature
  review or an SLR.
- The review maps the **scope, types and distribution** of available evidence
  against the review question of Section 2. It does not pool results, and it
  does not claim exhaustive coverage of the literature.
- Screening is single-reviewer (Section 10). **No dual independent screening is
  claimed or performed**, at any stage.
- No scored risk-of-bias appraisal is imported from the systematic-review route
  (Section 17). Study methods and limitations are charted (Section 14) and
  discussed; that is not a formal critical appraisal.

**Structure and reporting.** The protocol is structured using the Joanna Briggs
Institute (JBI) scoping-review guidance and the review is reported using
**PRISMA-ScR**. PRISMA-ScR is a *reporting* framework: it prescribes what must
be stated about a review that has been carried out, and it is never evidence
that a search, a screening pass or a synthesis has happened. Departures from
the adopted guidance are recorded in Section 17 rather than glossed over, and
full JBI compliance is not claimed.

Guidance sources:

- JBI, question and scope guidance: <https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862687>
- JBI, protocol guidance: <https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862667>
- JBI, study-selection guidance: <https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862769>
- JBI, appraisal guidance: <https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862791>
- PRISMA-ScR: <https://www.prisma-statement.org/scoping>

Purpose: ground the background chapter (Chapter 2) and the design decisions of
the artefact in verified primary literature, standards and official
documentation, with a transparent, traceable search trail; and separate
peer-reviewed study evidence from standards and implementation documentation,
reporting the source types actually included.

## 2. Review question, PCC framing and topic axes

### 2.1 Review question

**Which implemented edge gateway architectures host digital-twin services for
wearable data, how are those gateways built and deployed on embedded Linux, and
how are their correctness, resource use and evaluation environments reported?**

Sub-questions, each mapped to the axes of Section 2.3:

1. What gateway and digital-twin architectures are reported, and which
   platforms and messaging contracts do they use? (Axes A, B, C, F, G, J)
2. How are the images, containers and runtimes of such gateways produced and
   deployed on embedded or constrained ARM targets? (Axes D, E)
3. What wearable-data workloads are used, and how are they characterised or
   synthesised? (Axis H)
4. In what execution environments — physical, virtualised or emulated — are
   these systems evaluated, with what methods, metrics and stated limitations?
   (Axes E, I)

This is the **review** question. It is not a dissertation research question and
it does not replace or restate RQ1–RQ3.

### 2.2 Population, Concept, Context — and the adaptation recorded

JBI frames a scoping-review question as Population/Concept/Context. This review
is about engineered systems, not human participants, so the framing is adapted
and the adaptation is recorded here:

| Element | As adapted for this review | Adaptation recorded |
|---|---|---|
| **Population** | Reported edge gateway and edge-hosted digital-twin systems, together with the platforms, build systems and brokers they are composed of | The unit of interest is a **system or artefact**, not a human population. No participant characteristic, sampling frame or demographic eligibility applies. Where a source studies people (for example a wearable dataset collected from participants), the population charted is still the system or dataset under study. |
| **Concept** | Architecture and composition; build, packaging and deployment on embedded Linux; ingestion and materialisation of wearable data; evaluation and measurement methodology, including reported metrics and limitations | Spans design and evaluation rather than a single intervention or outcome. No effect measure and no comparator are required for eligibility. |
| **Context** | Resource-constrained or edge deployment, including virtualised and emulated execution environments, and local (non-cloud-dependent) digital-twin cores; English- or Portuguese-language sources; 2010–2026, with no lower bound for methodology classics | Emulated and virtualised environments are **in context** and are charted as such (Section 14), because the dissertation's own evaluation runs under QEMU/TCG. Including an emulated study is not a statement that emulated figures stand for native capacity. |

Departures from the JBI framing beyond the adaptation above are recorded in
Section 17.

### 2.3 Topic axes

The review supports the three thesis research questions through these topic
axes. Each retained study is tagged with at least one axis. The student reports
that the research questions are approved, with RQ3 evaluated under QEMU/TCG
rather than on a native ARM64 virtual machine; that report is registered against
D011 in
[`../../docs/governance/supervisor_decision_log.csv`](../../docs/governance/supervisor_decision_log.csv)
as reported by the student, not as a documented supervisor decision. The
approved verbatim RQ wording is held in the student manuscript and is not
reproduced here; the "Feeds" column below maps axes to chapters, not to
supervisor quotations.

The axis identifiers **A–J are stable** and are not renumbered, retired or
reassigned by this revision. They are the `axis` values of `search_log.csv` and
`study_selection.csv`.

| Axis | Topic | Feeds |
|---|---|---|
| A | Edge computing and edge/IoT gateway architectures | Ch. 1, 2 |
| B | Digital twins (concepts, surveys, edge deployments) | Ch. 2 |
| C | Digital-twin platforms (Eclipse Ditto and alternatives) | Ch. 2, 4 |
| D | Embedded Linux build systems (Yocto, Buildroot, reproducible builds) | Ch. 2, 4 |
| E | Containers/virtualisation on ARM and constrained edge devices | Ch. 2, 4 |
| F | MQTT and IoT messaging (brokers, QoS, reliability) | Ch. 2, 4 |
| G | W3C Web of Things (Thing Description, interoperability) | Ch. 2, 4 |
| H | Wearable devices, wearable data characteristics, synthetic workload generation | Ch. 2, 4 |
| I | Performance-evaluation and benchmarking methodology (edge/IoT, statistics) | Ch. 3, 5 |
| J | C2DTA line and consumer-controlled digital twins; SSI as context only | Ch. 1, 2 |

> **Terminology note — 2026-09-19.** Axis H previously read "telemetry
> characteristics". The axis *letter* is unchanged; only its descriptive prose
> was updated under the terminology policy the student reports authorised
> (wearable data, wearable event data, sensor measurements or device events in
> active explanatory prose). Literal identifiers are never rewritten to match
> that prose: the draft search string for axis H in Section 4 keeps `telemetry`
> as a query token, executed query strings in `search_log.csv` are never edited,
> and bibliographic titles are quoted exactly as published.

## 3. Databases and sources

Primary bibliographic databases (archived plan v1.0 §6.2):

1. **IEEE Xplore** (https://ieeexplore.ieee.org)
2. **ACM Digital Library** (https://dl.acm.org)
3. **Scopus** or **Web of Science** (whichever is accessible via the
   institutional subscription; the one used is recorded per query)

Complementary primary sources (not databases; used for standards and official
documentation): W3C (w3.org/TR), OASIS (docs.oasis-open.org), Yocto Project
(docs.yoctoproject.org), Eclipse Foundation (eclipse.dev/ditto), Crossref
(api.crossref.org) for metadata verification.

Google Scholar may be used **only as a locator** (to find the primary record
of an already-identified candidate or for forward snowballing); hits from
Scholar are never logged as database results.

**Access limitations are part of the record.** For every database actually
used, the `notes` column of `search_log.csv` states the access route
(institutional subscription, open access, none) and any limitation that
affected the result — an unavailable database, a subscription that does not
cover a venue, an export cap, a full text that could not be obtained. A
database listed above that is never reached is reported as **not searched**,
with the reason, in the PRISMA-ScR reporting of Section 12. It is never quietly
dropped from this list and never reported as searched.

### The compass leads file

`../../../compass_artifact_wf-bc3ec062-7176-5823-8bec-b56ecbdf0527_text_markdown.md`
is treated as a **leads list only**. The plan (§6.2) records that its metadata
and some claims are unreliable. No entry from that file may be cited or added
to `thesis/refs/references.bib` without full verification against the primary
record (Section 8). Leads taken from it are logged in `study_selection.csv`
with `origin = compass-lead`. Known problem entries flagged by the plan and to
be corrected or dropped during verification: the Morabito container-
virtualisation entry (frequently mis-cited; verify against the Crossref record
of DOI 10.1109/ACCESS.2017.2704444), the OpenTwins metadata (preprint versus
journal version), and the final publication data of the C2DTA article
(online-first 2025 versus version-of-record issue).

## 4. Search strategy and draft search strings

Every executed query is logged in `search_log.csv` (Section 11) with its exact
string, database syntax, date, filters and result counts. The strings below
are the **draft baseline**; refinements are permitted but each executed
variant is logged as its own row. Default filters: publication year 2010–2026
(no lower bound for axis I methodology classics and for foundational
methodology sources such as design-science references), document types:
journal articles, conference papers, standards; language: English.

| Axis | Draft string (database-neutral; adapt syntax per database) |
|---|---|
| A | ("edge computing" OR "edge gateway" OR "IoT gateway") AND (architecture OR platform) AND (evaluation OR benchmark* OR "case study") |
| B | "digital twin*" AND (edge OR gateway OR "resource-constrained" OR embedded) AND (implementation OR evaluation OR survey) |
| C | ("Eclipse Ditto" OR "digital twin platform" OR "digital twin framework") AND (IoT OR edge) |
| D | ("Yocto" OR "Buildroot" OR "embedded Linux" OR "reproducible build*") AND (image OR "build system" OR distribution) |
| E | (container* OR Docker OR "OCI") AND (ARM OR aarch64 OR "single-board" OR "edge device*" OR IoT) AND (overhead OR performance OR virtualization) |
| F | MQTT AND (broker* OR "quality of service" OR QoS OR reliability) AND (edge OR IoT) AND (comparison OR performance OR evaluation) |
| G | ("Web of Things" OR "Thing Description" OR "WoT") AND (interoperab* OR "digital twin" OR IoT) |
| H | (wearable* OR smartwatch OR "smart ring" OR "smart clothing" OR "e-textile*") AND (telemetry OR "data stream*" OR "data rate*" OR simulat* OR emulat*) |
| I | (benchmark* OR "performance evaluation" OR "measurement methodology") AND (edge OR IoT OR cloud) AND ("confidence interval*" OR statistic* OR repetition* OR reproducib*) |
| J | ("digital twin*" AND (consumer OR "user-controlled" OR "data sovereignty")) OR "consumer-controlled digital twin" |

### 4.1 Preliminary searches versus formal execution

These are two different things and the record keeps them apart.

- **Preliminary searches (done).** `Q001`–`Q003` in `search_log.csv`, all dated
  2026-08-08, are non-institutional searches — one Crossref API lookup and two
  open-web verification searches — run to locate or verify individual records
  for the advisor draft of Chapter 2. They are labelled preliminary in the file.
  They are **not** a formal search of this protocol and are never counted as
  one, in the selection flow or anywhere in the dissertation.
- **Formal execution (not done).** The searches of Section 3 against IEEE
  Xplore, the ACM Digital Library and the accessible one of Scopus/Web of
  Science **have not been run**. When they are run, each is appended to
  `search_log.csv` as a new `Q` row carrying its own real execution date. The
  existing rows `Q001`–`Q003` are never edited, re-dated or relabelled to look
  like formal executions, and no row is ever written for a search that was not
  actually performed.
- **Query identifier space.** `Q001…` is the identifier space of *executed*
  queries and is separate from the axis letters A–J. A changed query, a changed
  filter or a changed source policy is recorded as a new logged variant, or as
  a dated amendment to this protocol (Section 19) when it changes the method —
  never as a retrospective edit of an earlier row.
- **Original exports are kept.** For every formal query, the database's own
  exported record set is retained alongside the log row, so that counts in the
  dissertation can be reconciled against the export rather than recalled.

## 5. Inclusion criteria

A candidate is included when **all** applicable criteria hold:

- **I1.** Relevant to at least one axis (A–J) and usable for a concrete
  section of the dissertation.
- **I2.** One of: (a) peer-reviewed primary study or survey; (b) published
  standard or W3C/OASIS Recommendation-track document; (c) official project
  documentation of a technology actually used by the artefact; or (d) grey
  literature admitted under E3's exception and explicitly marked as such.
- **I3.** Written in English or Portuguese.
- **I4.** Full text (or, for standards/documentation, the authoritative
  published page) accessible to the author.
- **I5.** Bibliographic metadata verifiable against the primary record
  (Section 8).

Inclusion follows these criteria and the review question. It never follows a
desired conclusion, a target number of sources or the needs of a particular
paragraph of the dissertation.

## 6. Exclusion criteria

A candidate is excluded (with the criterion logged) when **any** holds:

- **E1.** No relation to any axis, or purely tangential mention.
- **E2.** Preprint (e.g. arXiv) with no peer-reviewed version, unless used
  strictly as clearly-marked grey literature for a non-load-bearing statement.
- **E3.** Vendor or marketing material without verifiable technical substance.
  Exception: vendor engineering documentation may be used as grey literature
  for engineering context, never for scientific claims, and is always marked.
- **E4.** Metadata cannot be verified against a primary record (unresolvable
  DOI, inconsistent authorship/venue, ghost citation).
- **E5.** Duplicate of an already-logged record (Section 7).
- **E6.** Non-archival abstract, poster or slide deck, unless uniquely
  relevant and explicitly marked.

## 7. Deduplication procedure

1. Normalise DOIs (lowercase, strip `https://doi.org/`); two records with the
   same DOI are duplicates.
2. Without a DOI: match on normalised title (case/punctuation-insensitive)
   plus year plus first-author family name.
3. The first-logged record is kept; the duplicate row keeps
   `decision = exclude`, `criterion = E5` and `dedup_of = <study_id kept>`.
4. Preprint/journal pairs: keep the peer-reviewed version, exclude the
   preprint as E5 with a note (this is the OpenTwins case).

Records removed as duplicates are counted, so that the retrieved, deduplicated,
screened and included totals reconcile in the selection flow (Section 12).

## 8. Verification rule (mandatory before citation)

No source enters `thesis/refs/references.bib` before its metadata is verified
against the **primary record**:

- Articles/papers: the Crossref record (`https://api.crossref.org/works/<doi>`)
  and/or the publisher landing page; DOI must resolve.
- Standards: the standards body's own page (W3C TR page, OASIS document page).
- Official documentation: the project's canonical documentation site, with
  the version/release stated.

Each BibTeX entry carries a comment line:
`% verified <YYYY-MM-DD> via <source>` describing what was checked. The
verification is also recorded in `study_selection.csv`
(`verified_date`, `verified_via`). Entries that cannot be verified are not
cited (E4).

**Metadata verification is not reading.** Citation verification, title/abstract
screening and full-text extraction are three distinct states and are never
merged into a single "verified" count. A `verified_date` shows that the
bibliographic record is real, not that the study has been read.

## 9. Snowballing procedure

After the database queries of each axis are screened:

1. **Backward snowballing:** scan the reference lists of included studies for
   candidates; log each as `origin = snowball-backward` with the parent
   `study_id` in `notes`.
2. **Forward snowballing:** inspect citing works via Scopus/Web of Science
   (or Google Scholar as locator only); log as `origin = snowball-forward`.
3. One snowballing iteration is the default; a second iteration is permitted
   for an axis with fewer than three included studies, and is logged as such.

Snowballed candidates pass the same criteria, deduplication and verification
as database results.

## 10. Screening procedure

Screening is carried out by **a single reviewer, the author**, in two logged
stages:

1. **Title/abstract screening** (`stage = title_abstract`): quick relevance
   check against I1/E1; undecided candidates advance.
2. **Full-text screening** (`stage = full_text`): all criteria applied;
   the deciding criterion is logged for every exclusion.

The actual checking procedure is exactly this and is reported as such: one
reviewer, two stages, every full-text exclusion carrying its criterion, with
the counts reconciled in the selection flow. **No second independent screener
is used, and no reviewer agreement is measured.** The single-reviewer
limitation is carried into Section 17 and into the dissertation's reporting of
the review.

The student reports that the supervisor waived the requirement for a second
operator to rebuild and test the *software*. That waiver concerns software
testing only. It says nothing about literature screening, it does not stand in
for a second screener, and it is never cited as evidence of dual screening.

## 11. Logging tables specification

Both tables live in `thesis/research/` and are committed with every update.
Field values never contain unescaped commas (use `;` inside fields). The
evidence-charting table specified in Section 14 is a **third, separate**
artefact and does not replace either of these.

### `search_log.csv` — one row per executed query

| Column | Content |
|---|---|
| `query_id` | `Q001`, `Q002`, ... stable identifier |
| `date` | execution date, `YYYY-MM-DD` |
| `database` | `IEEE Xplore`, `ACM DL`, `Scopus`, `Web of Science` |
| `axis` | axis letter(s), e.g. `A` or `A;B` |
| `search_string` | the exact string as typed, database syntax included |
| `filters` | years, document types, other facets applied |
| `results_total` | hit count reported by the database |
| `results_screened` | how many hits were actually screened (e.g. first 100 by relevance; state the rule) |
| `exported_to_selection` | how many rows were added to `study_selection.csv` |
| `notes` | free text (syntax quirks, truncation rule, access route and limitations, etc.) |

### `study_selection.csv` — one row per candidate record

| Column | Content |
|---|---|
| `study_id` | `S001`, `S002`, ... stable identifier |
| `query_id` | originating query, or empty for snowball/lead origins |
| `origin` | `database`, `snowball-backward`, `snowball-forward`, `compass-lead`, `known-source` |
| `title` | as published |
| `first_author` | family name |
| `year` | publication year |
| `venue` | journal/conference/standards body |
| `doi_or_url` | DOI preferred; canonical URL otherwise |
| `axis` | axis letter(s) |
| `stage` | `title_abstract` or `full_text` (the furthest stage reached) |
| `decision` | `include`, `exclude`, `pending` |
| `criterion` | deciding criterion (`I1`..`I5`, `E1`..`E6`) for final decisions |
| `dedup_of` | `study_id` of the kept record, when `criterion = E5` |
| `verified_date` | `YYYY-MM-DD` of metadata verification (included studies only) |
| `verified_via` | e.g. `Crossref API`, `w3.org TR page`, `publisher page` |
| `bibkey` | BibTeX key in `thesis/refs/references.bib` (included studies only) |
| `notes` | free text |

## 12. Reporting rules

- **No absolute-absence claims.** The dissertation never states "no studies
  exist" or "this is the first work to ...". Absence claims are always bounded
  to the executed protocol, e.g. "within the searches executed under this
  protocol, no study was identified that ...". (Plan §6.2.)
- Every citation in the dissertation resolves to a verified entry in
  `thesis/refs/references.bib`.
- Grey literature is always identified as such in the text or in the entry's
  note field, and never supports a scientific claim.
- Counts reported in the dissertation about the review itself (queries,
  screened, included) are computed from these two CSVs, not remembered.
- **PRISMA-ScR reporting.** The dissertation carries a PRISMA-ScR checklist
  giving, for each item, the location in the manuscript where it is addressed,
  together with a selection flow showing records retrieved, duplicates removed,
  records screened at title/abstract, full texts sought and obtained, full texts
  excluded with reasons, and studies included and charted. The numbers in the
  flow reconcile with `search_log.csv` and `study_selection.csv`.
- The **source types actually included** are reported separately: peer-reviewed
  studies and surveys, standards, official documentation and marked grey
  literature are counted apart, never merged into one "sources" figure.
- **No meta-analysis** is performed and none is required. Heterogeneous
  hardware, workloads and environments make a pooled performance number
  meaningless; the synthesis is descriptive and thematic (Section 15, output 5).
- A database that was not searched, a full text that could not be obtained and a
  planned step that was not carried out are reported as such.

## 13. Targets and timeline

> **Superseded — 2026-09-19.** The two targets below were written under plan
> v1.0/v1.2 and are kept for the record. Both are now out of date: the
> **G6 target date of 2026-09-18 has passed** and G6 is not decided, and
> the **search-execution window of 2026-08-10 to 2026-08-30 passed without the
> institutional searches being run**. The replacement working targets are in
> Section 18. In addition, the source count below is retained only as an
> indicative planning figure: under a scoping review, no quota of papers makes
> the review valid or invalid, and inclusion follows Section 5, never a number.

- Target: **at least 30 verified sources** in `thesis/refs/references.bib` by
  gate **G6 (2026-09-18)**, privileging primary studies, standards and
  official documentation (archived plan v1.0 §6.2). As of protocol v1.0 the bibliography
  holds 15 verified core entries; growth happens exclusively through this
  protocol — never by padding or bulk import.
- Search execution window: aligned with the writing of Chapters 1–3
  (archived plan v1.0 §8, weeks of 2026-08-10 to 2026-08-30); late additions (e.g. for the
  discussion) remain possible until G6 and follow the same logging rules.

## 14. Evidence charting

Charting is the scoping review's extraction step. It produces a table, distinct
from `study_selection.csv`, with **one row per included study**. The file is
created when charting begins; it does not exist yet, because no study has been
charted.

| Charting field | Content |
|---|---|
| `study_id` | the `S…` identifier of the included record, so every charted row traces back to retrieval |
| `bibliographic_identity` | authors, year, title, venue, DOI or canonical URL |
| `source_type` | peer-reviewed study, survey, standard, official documentation, or marked grey literature |
| `architecture_platform` | the gateway/twin architecture and the platform or framework used |
| `execution_environment` | physical hardware, virtual machine, container host, emulator; instruction-set architecture and resources as reported by the source, or `unspecified` when the source does not say |
| `workload` | data sources, device types, message rates, durations, synthetic or real |
| `methods_metrics` | evaluation method, repetitions, metrics and any statistical treatment reported |
| `limitations` | limitations stated by the source, and limitations evident from its reporting |
| `relevance` | the axis or axes and the section of this dissertation the study informs |
| `notes` | free text, including anything the source leaves unstated |

Rules:

- A field the source does not report is charted as `unspecified`. It is never
  inferred, converted from another environment or filled in from a related
  paper.
- Charting is done from the **full text**. A record still at
  `stage = title_abstract` is not charted, and metadata verification
  (Section 8) is not charting.
- Study methods and limitations are charted and discussed. That is not a
  scored risk-of-bias appraisal, and it is not reported as one (Section 17).

## 15. Required outputs

The review package consists of five outputs, produced in parallel with the
technical work. Output 1 is this document. Outputs 2 to 5 do not exist and no
part of them has been produced at the date of this revision. Section 18 still
treats output 1 as settling on 2026-09-21, because the eligibility criteria and
the charting fields may yet be refined before the formal search begins.

1. **This dated protocol revision** — labelled a scoping review, defining the
   review question, eligibility, information sources, the search and screening
   process, the charting fields and the limitations, with prior versions kept in
   the repository history and summarised in the amendment log of Section 19, and
   with preliminary searches held separate from formal execution. Changes to the
   method after selection has begun are logged as dated amendments
   (Section 19), never applied by silently rewriting this file.
2. **Exact search logs and original exports** for IEEE Xplore, the ACM Digital
   Library and the Scopus/Web of Science coverage specified in Section 3,
   including the exact strings, fields, filters, execution dates and access
   limitations. The A–J axes and the `Q…` identifier space are preserved; a
   changed query or source policy is a recorded variant or amendment, never a
   fabricated past execution.
3. **Deduplicated records and screening decisions** — title/abstract and
   full-text decisions, full-text exclusion reasons, and a reconciled selection
   flow, together with a plain description of the actual reviewer arrangement
   (single reviewer) and its limitations. Full JBI compliance is not claimed
   where the procedure differs.
4. **The evidence-charting table** of Section 14, keeping citation
   verification, abstract screening and full-text extraction as distinct states.
5. **The descriptive/thematic synthesis** — a gap analysis bounded to the
   searches actually executed, the PRISMA-ScR checklist with manuscript
   locations, the selection flow and the bibliography. No meta-analysis, no
   universal "no studies exist" claim and no paper quota.

## 16. Completion criterion

The review package is complete when **all** of the following hold:

1. Every included study is traceable from retrieval, through selection, to a
   charted row — `search_log.csv` → `study_selection.csv` → the charting table
   of Section 14. A study that no formal query retrieved has no `query_id`, and
   one is never invented for it: a seeded source is traceable instead through
   the `origin` column of `study_selection.csv` (`known-source` or
   `compass-lead`) together with `verified_via` and `verified_date`, which say
   where it came from and how it was checked. Both routes are retrieval
   provenance; neither is a substitute for the other, and the preliminary
   records are not rewritten to manufacture a link. State of 2026-09-19: of the
   25 rows currently marked included, all 25 carry a seeded `origin`
   (15 `known-source`, 10 `compass-lead`); 24 carry no `query_id`, and one
   `compass-lead` row, `S021`, additionally links to `Q001`, which is itself
   preliminary. The two routes therefore overlap rather than partition the
   set, and the PRISMA-ScR flow reports them separately while declaring that
   row once. The formal execution of the searches will add rows carrying a
   `query_id`; until it has run, this criterion is satisfied by the seeded
   route only, and the
   PRISMA-ScR flow reports the two routes separately rather than merging them
   into one retrieval count.
2. The reported counts reconcile: retrieved, duplicates removed, screened,
   full texts sought and obtained, excluded with reasons, included and charted.
3. The reported methods and limitations match the work actually done, including
   the single-reviewer screening, any database not searched and any full text
   not obtained.
4. The synthesis answers the review question of Section 2 and supports the
   design rationale of the dissertation, within the bounds of the executed
   searches.

Choosing the label "scoping review" satisfies none of these. This package
closes no gate and admits no claim; it is an input to the dissertation
chapters, not an acceptance criterion that has been met.

## 17. Limitations and departures from the adopted guidance

Stated here, and repeated in the dissertation's reporting of the review:

- **Single reviewer.** All screening and charting is done by the author.
  There is no second independent screener, no duplicate extraction and no
  measure of reviewer agreement (Section 10). The review therefore claims
  breadth and traceability, not exhaustiveness.
- **Not registered.** This protocol is not registered and not preregistered on
  any platform. It is a dated, version-controlled document in this repository,
  and nothing more is claimed for it.
- **Written before formal execution, not "prospectively executed".** The
  protocol is dated before the formal searches, but the review has a real
  history: preliminary, non-institutional searches were performed in August 2026
  for the advisor draft, and 25 candidate records already exist. That history is
  preserved (Section 4.1) rather than presented as the product of this protocol.
- **No formal critical appraisal.** A scored risk-of-bias or quality-appraisal
  instrument is not applied. Study methods and limitations are charted
  (Section 14) and discussed in the synthesis. If a formal appraisal is later
  adopted, this protocol is amended first (Section 19) to say which instrument
  is used, to which sources and why; it is not applied retrospectively and then
  described as planned.
- **Partial JBI alignment.** JBI guidance structures the protocol, but this
  review **departs from it on dual screening** and adapts the Population element
  to engineered systems (Section 2.2). The absence of a scored appraisal is
  **not** counted as a departure: a formal critical appraisal is not an automatic
  requirement of a scoping review, and the bullet above records why none is
  applied and what would have to be amended first if one were adopted. Full JBI
  compliance is not claimed, and neither is conformity asserted on any point
  beyond the two named here.
- **Coverage bounded by access.** Institutional access determines which of
  Scopus and Web of Science is used, and may prevent obtaining some full texts.
  Every such limitation is recorded (Section 3) and reported (Section 12).
- **Language.** Only English- and Portuguese-language sources are eligible
  (I3); relevant work published in other languages is missed by design.
- **A scoping review maps evidence.** It does not establish effectiveness,
  does not rank platforms and does not license a performance comparison between
  a source's reported figures and this dissertation's emulated measurements, in
  either direction.

## 18. Working schedule

Replacing the superseded dates of Section 13. These are **working targets** set
to feed the dissertation chapters; they are not supervisor promises, not
achieved milestones and not evidence that any step has been performed.

| Target date | Step |
|---|---|
| 2026-09-21 | This protocol settled; checkpoint — re-estimate the remaining screening and full-text workload against the real corpus size |
| 2026-09-26 | Formal searches executed and logged, exports retained, deduplication done, screening decisions recorded |
| 2026-09-30 | Charting, selection flow, descriptive/thematic synthesis and bibliography complete enough to write from |
| 2026-10-01 | Chapters 1–4 sent, drawing on the synthesis |

At the 2026-09-21 checkpoint the remaining workload is estimated from the
**actual** number of retrieved records, not from an assumption. If the work
cannot fit before 2026-10-01, the gap is recorded and an explicit
prioritisation or method amendment is agreed and logged in Section 19. The
review is not silently downgraded to a narrative review, an unfinished review
is not described as complete, and a target date that slips is reported with its
cause and a revised forecast rather than moved quietly. The review tables and
the PRISMA-ScR reporting are reconciled again for the full draft of 2026-10-08
and rechecked at G7.

**Outstanding correction in the manuscript.** Section 2.1 of the drafted
manuscript still carries the pre-2026-09-19 description — "a structured review
with systematic elements" — and does not use the scoping-review designation of
Section 1. Its edited source is `thesis/latex/chapters/02_background.tex`, whose
generated copy is `thesis/sections/05_background.md`; neither is touched by this
revision, because the LaTeX tree is edited under its own change. The correction
is due before the Chapters 1–4 hand-off of 2026-10-01 and is tracked as a row in
[`../../docs/g0/backlog.md`](../../docs/g0/backlog.md).

## 19. Amendment log

Every change of method after this revision is recorded here with its date and
its justification, before it affects selection or reporting. Amendments are
added; earlier entries are never edited away.

| Version | Date | Change | Justification |
|---|---|---|---|
| 1.0 | 2026-08-07 | Initial protocol, designated "structured scoping/narrative review" | Archived plan v1.0 §6.2 |
| 1.1 | 2026-08-14 | Repointed the normative basis at the in-repository plan; no method, query, criterion or target changed | Plan v1.2 published at the canonical path |
| 2.0 | 2026-09-19 | Designated the review a **scoping review** and superseded the "scoping/narrative" label (Section 1); added the review question and the PCC framing with its recorded adaptation (Section 2); named JBI as the structuring guidance and PRISMA-ScR as the reporting framework (Sections 1, 12); separated preliminary searches from formal execution (Section 4.1); added access-limitation recording (Section 3); added the charting fields (Section 14), the five required outputs (Section 15), the completion criterion (Section 16), the limitations and departures (Section 17) and the working schedule (Section 18); marked the G6 and August search-window targets superseded (Section 13); updated the prose of axis H under the authorised terminology policy without changing the axis letter or any logged query string; repointed the normative basis at the adopted plan v2.0 | Review type reported confirmed as a scoping review by the student's follow-up (D003); plan v2.0 adopted 2026-09-18; the earlier targets had lapsed. No search was executed, no record screened and no study charted by this revision |
