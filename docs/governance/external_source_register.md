# External source register

> **Control record, 2026-08-13.** These sources remain outside the active
> repository. This register stores identifiers and checksums only; it grants no
> redistribution right and is not evidence that every statement in a source has
> been verified.

## Locator policy

- `WORKSPACE_ROOT` means the local controlled root
  `C:\Users\ruimf\Documents\Projeto Mestrado`. The literal local path is for
  operator verification only and must not be published in dissertation metadata.
- `Repository locator` is relative to the `Claude/` repository root. It may
  resolve only in the managed workspace; links are deliberately not used because
  the files are outside the repository.
- A checksum identifies bytes, not scholarly authority. Primary sources must
  still be verified and cited through their stable public identifier.
- `Internal/restricted` means do not commit or redistribute the binary without
  explicit rights confirmation. It does not assert a formal security
  classification.

## Registered sources

| ID | Source and controlled locators | Bytes | SHA-256 | Provenance and intended use | Confidentiality / redistribution | Stable public permalink |
|---|---|---:|---|---|---|---|
| EXT-001 | `EdgeGateway_Paper.pdf`; repo `../EdgeGateway_Paper.pdf`; local `%WORKSPACE_ROOT%\EdgeGateway_Paper.pdf` | 4,617,369 | `de0d0591a4982d764402139293ed5d63f3b420ad180fbe46eb6f2b032f21a7c6` | Published C2DTA implementation paper supplied in the project workspace; scientific baseline and comparison source. | Local copy restricted; cite/link the publisher version. | [DOI 10.1016/j.bcra.2025.100342](https://doi.org/10.1016/j.bcra.2025.100342) |
| EXT-002 | `C2DTA Student Repository Template.docx`; repo `../C2DTA Student Repository Template.docx`; local `%WORKSPACE_ROOT%\C2DTA Student Repository Template.docx` | 17,594 | `a8f2f43f06d76a39f437e6df55c9f21ba228378f1137810373bb3555a35978d1` | Repository-structure template supplied with the project. Guidance only; not an implementation contract. | Internal/restricted; no redistribution assumed. | None recorded. |
| EXT-003 | `C2DTA_Seven_Questions_Answers_1.docx`; repo `../C2DTA_Seven_Questions_Answers_1.docx`; local `%WORKSPACE_ROOT%\C2DTA_Seven_Questions_Answers_1.docx` | 369,074 | `b5e69f3cb67891b02192fc08014731c31c3f56d735d4c88bd5300a034f6fb17a` | Working answers to the seven supervisor questions, including an embedded diagram. Use as a prompt for verification, not as a citable authority. | Internal/restricted; may contain unverified and time-sensitive claims. | None recorded. |
| EXT-004 | `EscritaArtigo.pptx`; repo `../universidade/EscritaArtigo.pptx`; local `%WORKSPACE_ROOT%\universidade\EscritaArtigo.pptx` | 16,195,223 | `8e050a92f4c775b86cd6ecefc55bcf3cf0e60ea486782d7edb3369369f1df643` | University teaching material on scientific-paper writing; post-thesis support, not a project requirement. | Internal course material; do not redistribute. | None recorded. |
| EXT-005 | `FinalCommentsPresentationDefense.pptx`; repo `../universidade/FinalCommentsPresentationDefense.pptx`; local `%WORKSPACE_ROOT%\universidade\FinalCommentsPresentationDefense.pptx` | 7,158,647 | `6c6b4242ef6f450bfbbfae9d85f10af9637756c345d5ff45bd8d6e0b9def5df4` | University teaching material on final presentation and defence. | Internal course material; do not redistribute. | None recorded. |
| EXT-006 | `LiteratureReviewTools.pptx`; repo `../universidade/LiteratureReviewTools.pptx`; local `%WORKSPACE_ROOT%\universidade\LiteratureReviewTools.pptx` | 1,731,108 | `3f57823d79428952d3d0746c49c45de33c767f0e664af484982388e2accfbaf7` | University teaching material on literature-review tools and process; informs search logging and selection. | Internal course material; do not redistribute. | None recorded. |
| EXT-007 | `MoreAboutPublications.pptx`; repo `../universidade/MoreAboutPublications.pptx`; local `%WORKSPACE_ROOT%\universidade\MoreAboutPublications.pptx` | 37,599,410 | `6c74f0b88b369024d52bbd63f63fe533ee8d97da930d346b496dd314a2334038` | University teaching material on publication; outside the pre-submission critical path. | Internal course material; do not redistribute. | None recorded. |
| EXT-008 | `TypesDissertationProjects.pptx`; repo `../universidade/TypesDissertationProjects.pptx`; local `%WORKSPACE_ROOT%\universidade\TypesDissertationProjects.pptx` | 29,198,683 | `1b8fa4b056a14c5146eff1b248baf5dd86f1c30bdbb1b6a53d869bd4e2aef415` | University teaching material on dissertation/project types; contextual support for the DSR classification. | Internal course material; do not redistribute. | None recorded. |
| EXT-009 | `PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`; repo `../PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`; local `%WORKSPACE_ROOT%\PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md` | 41,962 | `53233a44d6967ded9e33eb6a9c6d2721ff44d0f003ce389fb58cd502a9f64b8d` | User-approved Portuguese integrated plan v1.0 dated 2026-08-07. Superseded prospectively by v1.1; preserved byte-for-byte in the repository archive. | Project-internal; publish only with the repository owner's approval. | Repository archive after publication. |
| EXT-010 | `Plano_Tese_EdgeGateway_v2.md`; repo `../Plano_Tese_EdgeGateway_v2.md`; local `%WORKSPACE_ROOT%\Plano_Tese_EdgeGateway_v2.md` | 18,566 | `a06e30f7e21c344f0fdbc0eeb4d5340d363c47f8f6600dbd9a7080104dc4a901` | Historical compressed plan covering the multi-thesis context. Non-normative; useful for official theme boundaries only. | Project-internal; historical. | None recorded. |
| EXT-011 | `compass_artifact_wf-bc3ec062-7176-5823-8bec-b56ecbdf0527_text_markdown.md`; repo `../compass_artifact_wf-bc3ec062-7176-5823-8bec-b56ecbdf0527_text_markdown.md`; local `%WORKSPACE_ROOT%\compass_artifact_wf-bc3ec062-7176-5823-8bec-b56ecbdf0527_text_markdown.md` | 38,235 | `35e93f6dba8212f231a0cd0e71ab7186083b337bd21b7f3334005fa612dff51d` | Generated bibliographic compass supplied in the workspace. It is a discovery aid only: entries and novelty claims require primary-source verification. | Project-internal working material; contains unverified claims. | None for the generated artefact. |
| EXT-012 | `INTERFACES.md`; repo `../INTERFACES.md`; local `%WORKSPACE_ROOT%\INTERFACES.md` | 4,499 | `38b6d5f972d892e8b9293615bd95482c8249a2ad92e9235aaceebe04c0a7b84f` | Historical multi-thesis interface draft. Reconcile useful boundaries with `src/CONTRACTS.md`; never override the active contract. | Project-internal, draft and non-normative. | None recorded. |
| EXT-013 | `LOG_Projeto.md`; repo `../LOG_Projeto.md`; local `%WORKSPACE_ROOT%\LOG_Projeto.md` | 13,648 | `2679ec4086232b9e13cf4f1d4ea75d8a678e50959434bf4a28e5edbba756e60e` | Historical project diary. It contains superseded state and at least one corrected PDF classification; use only as lineage. | Project-internal, historical and non-normative. | None recorded. |
| EXT-014 | `ANALISE_GESTAO_PROJETO_CLAUDE_2026-08-08.md`; local `%WORKSPACE_ROOT%\ChatGPT\ANALISE_GESTAO_PROJETO_CLAUDE_2026-08-08.md` | 50,219 | `59cfefe3c1a0147a57c4bd2fb2fb93293d41e96b65430e643270b9173838017d` | First external management audit of 2026-08-08; origin of the M0–M5 maturity scale and risks R16–R27. Condensed non-normatively in `docs/reviews/historical/2026-08-08-legacy-review-synthesis.md`. | Project-internal, historical. | None — single local copy, untracked in the legacy tree; include in every off-machine backup. |
| EXT-015 | `REANALISE_GESTAO_PROJETO_CLAUDE_POS_CORRECOES_2026-08-08.md`; local `%WORKSPACE_ROOT%\ChatGPT\REANALISE_GESTAO_PROJETO_CLAUDE_POS_CORRECOES_2026-08-08.md` | 40,308 | `59ad781047bdfb8b764c6668f42aab1c3b8ab3c90693bafe8293b3470e3ef636` | Post-correction re-audit of 2026-08-08; origin of risks RA1–RA15 and the four-field reporting format. | Project-internal, historical. | None — single local copy, untracked in the legacy tree; include in every off-machine backup. |
| EXT-016 | `DECISAO_FINAL_E_ORDEM_DE_TRABALHOS_CLAUDE_2026-08-08.md`; local `%WORKSPACE_ROOT%\ChatGPT\DECISAO_FINAL_E_ORDEM_DE_TRABALHOS_CLAUDE_2026-08-08.md` | 9,298 | `b8319bb9e92fbe8c88e51c8bb7e32f13a4103e92c4514c128bfcaeffc32b3a90` | Work order of 2026-08-08 (GO for P2 → P1 → P3, P4 as user-only actions). | Project-internal, historical. | None — single local copy, untracked in the legacy tree; include in every off-machine backup. |
| EXT-017 | `VERIFICACAO_P2_P1_P3_E_PLANO_P5_ANTES_P4_2026-08-08.md`; local `%WORKSPACE_ROOT%\ChatGPT\VERIFICACAO_P2_P1_P3_E_PLANO_P5_ANTES_P4_2026-08-08.md` | 19,281 | `fbfcbfd77134be1a9d11191568aec2e878843c6522a977dffdb5d8c37fb81f67` | Verification of P2/P1/P3 and the P5 sprint authorisation of 2026-08-08; the final external management document. | Project-internal, historical. | None — single local copy, untracked in the legacy tree; include in every off-machine backup. |

The five PPTX files also exist under
`ChatGPT/thesis/refs/source-materials/universidade/`. On 2026-08-13 each legacy
copy matched its canonical `universidade/` counterpart byte-for-byte. The
duplicates are not separate sources and are therefore not registered twice.

## Integrity check

From PowerShell at `WORKSPACE_ROOT`, an operator may verify a source without
modifying it:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\EdgeGateway_Paper.pdf'
```

Any checksum change creates a new register row/version; do not silently replace
the recorded identity.
