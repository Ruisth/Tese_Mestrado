# Literature Review Protocol — Structured Scoping/Narrative Review

Version 1.0 — 2026-08-07.
Normative basis: integrated plan (`../../../PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`) §6.2;
summarised in the dissertation, Chapter 3, Section "Literature Review Protocol".

> **Status note — 2026-08-08.** The institutional database queries required by
> Section 3 (IEEE Xplore, ACM Digital Library, Scopus/Web of Science) have
> **not yet been executed**: they require institutional access and are a
> pending student action, scheduled for the search-execution window of
> 2026-08-10 to 2026-08-30 (plan §8). What exists as of this date is the
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

## 1. Method designation

This review is a **structured scoping/narrative review**. It is explicitly
**NOT a full systematic literature review (SLR)**: it borrows systematic
elements — logged search strings, dated queries, explicit inclusion/exclusion
criteria, deduplication and snowballing — but it does not claim exhaustive
coverage, dual independent screening, formal quality appraisal, or PRISMA
compliance. The dissertation must never describe it as an SLR.

Purpose: ground the background chapter (Chapter 2) and the design decisions of
the artefact in verified primary literature, standards and official
documentation, with a transparent, reproducible search trail.

## 2. Review questions and topic axes

The review supports the three thesis research questions (plan §4.2) through
these topic axes. Each retained study is tagged with at least one axis.

| Axis | Topic | Feeds |
|---|---|---|
| A | Edge computing and edge/IoT gateway architectures | Ch. 1, 2 |
| B | Digital twins (concepts, surveys, edge deployments) | Ch. 2 |
| C | Digital-twin platforms (Eclipse Ditto and alternatives) | Ch. 2, 4 |
| D | Embedded Linux build systems (Yocto, Buildroot, reproducible builds) | Ch. 2, 4 |
| E | Containers/virtualisation on ARM and constrained edge devices | Ch. 2, 4 |
| F | MQTT and IoT messaging (brokers, QoS, reliability) | Ch. 2, 4 |
| G | W3C Web of Things (Thing Description, interoperability) | Ch. 2, 4 |
| H | Wearable devices, telemetry characteristics, synthetic workload generation | Ch. 2, 4 |
| I | Performance-evaluation and benchmarking methodology (edge/IoT, statistics) | Ch. 3, 5 |
| J | C2DTA line and consumer-controlled digital twins; SSI as context only | Ch. 1, 2 |

## 3. Databases and sources

Primary bibliographic databases (plan §6.2):

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

Every executed query is logged in `search_log.csv` (Section 9) with its exact
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

Single-reviewer screening (the author), in two logged stages:

1. **Title/abstract screening** (`stage = title_abstract`): quick relevance
   check against I1/E1; undecided candidates advance.
2. **Full-text screening** (`stage = full_text`): all criteria applied;
   the deciding criterion is logged for every exclusion.

Because screening is single-reviewer, the review claims breadth and
traceability, not exhaustiveness — one more reason the study is not an SLR.

## 11. Logging tables specification

Both tables live in `thesis/research/` and are committed with every update.
Field values never contain unescaped commas (use `;` inside fields).

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
| `notes` | free text (syntax quirks, truncation rule, etc.) |

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

## 13. Targets and timeline

- Target: **at least 30 verified sources** in `thesis/refs/references.bib` by
  gate **G6 (2026-09-18)**, privileging primary studies, standards and
  official documentation (plan §6.2). As of protocol v1.0 the bibliography
  holds 15 verified core entries; growth happens exclusively through this
  protocol — never by padding or bulk import.
- Search execution window: aligned with the writing of Chapters 1–3
  (plan §8, weeks of 2026-08-10 to 2026-08-30); late additions (e.g. for the
  discussion) remain possible until G6 and follow the same logging rules.
