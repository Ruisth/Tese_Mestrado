# LOG — repositório Claude (Tema 1, Edge Gateway)

Formato: **Data · Fase · Ação · Resultado · Artefactos · Decisões · Próximos passos**
(igual ao `../LOG_Projeto.md`; este LOG cobre apenas o trabalho dentro de `Claude/`).

---

## Entrada #C001
- **Data:** 2026-08-07
- **Fase:** Bloco 07–09/08 (G0) do plano integrado
- **Ação:** Criação do repositório `Claude/` com Git, estrutura conforme o
  C2DTA Student Repository Template, e fixação dos contratos normativos internos.
- **Resultado:** Esqueleto do repositório; `src/CONTRACTS.md` v1.0 (tópicos MQTT,
  envelope, mapeamento de twins Ditto, endpoints do controlador, CLI do simulador,
  formato `events.jsonl`, variáveis de ambiente, portas); 4 JSON Schemas
  (envelope v1 + smartwatch/ring/clothing v1, draft 2020-12).
- **Artefactos:** `README.md`, `.gitignore`, `.gitattributes`, `src/CONTRACTS.md`,
  `src/schemas/*.schema.json`, `src/pyproject.toml`, `PROGRESS.md`.
- **Decisões:** medições no nível de topo do payload (continuidade com o payload
  de referência do paper/INTERFACES.md); `unevaluatedProperties: false` para
  rejeição de campos estranhos; namespace UUID v5 do projeto fixado.
- **Próximos passos:** desenvolvimento paralelo dos componentes P0 por ordem de
  entrega (G0 docs → Yocto/kas → deployment → controlador → simulador → harness →
  tese), com testes; verificação com pytest.

---

## Entrada #C002
- **Data:** 2026-08-07/08
- **Fase:** Blocos G0–G3 (desenvolvimento antecipado)
- **Ação:** Construção paralela dos 8 componentes P0 (workflow multi-agente com
  revisão adversarial de conformidade contratual nos 3 pacotes Python).
- **Resultado:**
  - `docs/`: pacote G0 completo (âmbito/RQs, email aos orientadores, backlog por
    gate, riscos R1–R15, matriz claim→evidência com 15 claims, guias WSL2 e
    Hetzner CAX21, ADRs 0001–0006).
  - `src/yocto/`: manifesto kas (formato 14) com pins verificados online em
    07/08 (poky `yocto-5.0.19` → `bb98354`, meta-openembedded scarthgap
    `ef3df29`, meta-virtualization scarthgap `0d9fb7f`), layer `meta-egw`,
    receita `egw-image`, smoke de container, scripts de build/QEMU.
  - `src/deployment/`: compose de 6 serviços com digests arm64 verificados no
    Docker Hub em 07/08 (Ditto 3.9.4, Mosquitto 2.0.22, Mongo 7.0.39), TLS,
    ACL, scripts de certs/auth/lock, Dockerfile do controlador;
    `docker compose config` OK.
  - `src/egw_controller/`, `src/egw_simulator/`, `src/egw_experiments/`:
    implementação completa conforme CONTRACTS + testes.
  - `src/things/` + `diagrams/`: TDs WoT 1.1 e diagramas Mermaid.
  - `thesis/`: esqueleto LaTeX (template ISCTE) compila — main.pdf, 46 pp.,
    0 referências/citações por resolver; 15 entradas bib verificadas via
    Crossref/W3C/OASIS em 07/08; protocolo da revisão scoping.
- **Artefactos:** commits `164e6cd`, `ef5b01c`.
- **Decisões:** ver ADRs e resultados dos agentes (registados nos commits).
- **Próximos passos:** aplicar correções das revisões.

---

## Entrada #C003
- **Data:** 2026-08-08
- **Fase:** Correções pós-revisão; CONTRACTS v1.0 → **v1.1**
- **Ação:** As revisões adversariais encontraram 1 bloqueador + 4 majors;
  contrato emendado e correções aplicadas por 3 agentes.
- **Resultado:**
  - **CONTRACTS v1.1 §4 — dedupe com âmbito por execução** (bloqueador): o piso
    de `seq` só se aplica dentro do mesmo `run_id`; `ingestion` ganha
    `last_run_id`. Sem isto, o warm-up (mesma seed → mesmos `device_uuid`)
    faria rejeitar ~20% das mensagens de cada execução medida como duplicadas,
    e as 10 execuções `smoke` consecutivas falhariam. Testes de regressão:
    warm-up→medida, 10 smokes, replay entre runs.
  - **Prazo de confirmação no domínio de relógio do controlador** (major): o
    analyze deriva o prazo de 60 s de `max(received_monotonic_ns)+janela` dos
    próprios eventos do controlador; o prazo do manifest é informativo
    (`clock_domain: harness-host`). Workflow off-VM documentado (plano §5.1)
    com exemplo de scp dos events.jsonl.
  - **PUBACK best-effort no simulador** (major): espera limitada ao tempo até
    ao próximo evento agendado + drain final; o débito nunca é limitado pelo
    RTT (necessário para o load-sweep a 250 msg/s). CONTRACTS §7 codifica.
  - **`device_type` em `sent_events.jsonl`** formalizado no CONTRACTS §7.
  - Menores: SUBACK antes de ready; contadores `dropped`/`queue_depth` no
    /metrics; validação de UUID em `/twins/{id}`; load-sweep 600→300 s;
    validação de `run_id`/`egw_id` no runner; cobertura de TLS wiring e das
    CLIs; notas dropout-reconnect (silêncio de dispositivo, não desconexão).
- **Evidência:** suite completa **400 passed** (Windows, Python 3.14).
- **Próximos passos (ações do estudante):** enviar email G0; instalar WSL2
  Ubuntu 24.04 e correr build Yocto (guia em docs/setup/); criar VM ARM64 e
  validar `aarch64` até 10/08; confirmar regras administrativas da extensão.

---

## Entrada #C004
- **Data:** 2026-08-08
- **Fase:** Correções da auditoria externa de gestão (ChatGPT, 08/08) — grupos A/B/C/D
- **Ação:** Análise da auditoria (fatos verificados contra o repositório antes
  de aceitar), aplicação integral das correções em 4 fluxos paralelos.
- **Resultado:**
  - **A — Higiene:** `main.bcf`/`main.run.xml` removidos do Git; regra do
    `certs/README.md` corrigida (agora versionado); bit executável nos 7
    scripts; `src/requirements.lock` (pip freeze, caveat de runtime lock na
    VM antes de `exp-v1`); `addopts` desseleciona `integration` por omissão;
    doc de backup/remote (`docs/setup/git_backup_remote.md`).
  - **B — Verdade documental:** PROGRESS reescrito como fonte única com modelo
    de 3 campos (Implementado/Verificado/Aceite) + escala M0–M5 + controlo de
    esforço; backlog sem estado; riscos R1–R27 com prob./impacto/owner;
    frase "review protocol executed" do cap. 2 substituída por claim limitado
    (revisão preliminar, protocolo por executar); diagramas e cap. 4
    sincronizados com CONTRACTS v1.1.
  - **C — Harness (riscos R18–R23):** fetch automático de `events.jsonl`
    (template + retries + subcomando `collect` de recuperação);
    `sut_environment.json` (script na VM) separado de
    `loadgen_environment.json`; collector de recursos na VM
    (`collect-resources.sh`); runs cronometrados sem ambiente/recursos do SUT
    ficam `validity: invalid`; janela medida no manifest com filtro do warm-up
    na análise; plano de campanha 76→95 runs (smoke×10, invalid-payload×3,
    dropout×3, controller-restart×3) mapeados aos claims C10–C14;
    `controller_metrics.csv` (queue_depth/dropped a 1 Hz) fecha o TODO do
    queue growth; CPU normalizada por nproc do SUT; condições externas
    (cold start, twin creation, boots QEMU) ingeridas e analisadas (C15);
    `measure-cold-start.sh` na VM. Regras de saturação marcadas
    "pending advisor sign-off" antes de `exp-v1`.
  - **C — Simulador:** `dropout-reconnect` agora faz desconexão MQTT real com
    buffering ordenado e redelivery no reconnect (janelas ao nível da execução,
    deterministas por seed); verificado contra o código-fonte do paho 2.1.0.
  - **D — Sprint teórico:** cap. 2 expandido de ~1 034 para 4 248 palavras
    substantivas; tabela de related work (C2DTA, Edge DT, OpenTwins, ODT vs
    este trabalho); bibliografia 15→25 entradas, todas verificadas em 08/08
    (Crossref/W3C/OASIS/páginas oficiais) com comentários datados;
    `study_selection.csv` com proveniência honesta (seed/snowball);
    `search_log.csv` só com pesquisas realmente executadas, marcadas
    "preliminary; non-institutional"; queries institucionais continuam
    pendentes (ação do estudante).
- **Evidência:** suite completa **452 passed** com evidência persistida em
  `docs/evidence/tests/2026-08-08/` (junit.xml, stdout, ambiente, commit);
  `main.pdf` 57 páginas, 0 referências/citações por resolver, 0 overfull
  > 20 pt nos capítulos editados; bundle de backup em `backups/`.
- **Decisões:** auditoria aceite em quase tudo; divergências documentadas:
  logs de pesquisa nunca fabricados (queries institucionais ficam para o
  estudante); dropout implementado (não apenas documentado) por ser o único
  caminho para o claim C10.
- **Próximos passos:** inalterados — ações externas do estudante (email G0,
  VM, WSL2, regras da extensão) e, depois, G1 com evidência real.

---

## Entrada #C005
- **Data:** 2026-08-08
- **Fase:** Execução da ordem de trabalhos do Senior PM (P2 → P1 → P3);
  GO formal em `../ChatGPT/DECISAO_FINAL_E_ORDEM_DE_TRABALHOS_CLAUDE_2026-08-08.md`
- **Ação e resultado por bloco:**
  - **P2 (académico):** claims prematuros removidos — caps. 1 e 3 já não
    afirmam protocolo/pesquisas executados; Tabela 2.1 com linha "This work"
    em linguagem de design e "pre-specified" em vez de "pre-registered";
    caps. 4/6 e abstracts sem tempos verbais de resultado; tabela reconstruída
    (legível). **PDF standalone do cap. 2 criado**:
    `thesis/latex/ch2_supervisor_draft.pdf` (16 pp., zero TODOs/placeholders,
    inspecionado página a página). Checkpoint cumprido: caminho comunicado ao
    estudante para envio imediato.
  - **P1a (validade base):** agregação bloqueada a runs `validity != valid`;
    `resource_source` tem de ser `sut-collector` em runs cronometrados
    (`local-dev` invalida); proveniência de host no CSV do collector com
    cross-check ao `sut_environment.json`; qualidade mínima de amostras e de
    campos SUT; exit codes do simulador/warm-up e overrides do protocolo
    passam a invalidar ou a registar `deviations` no manifesto (v1.2).
  - **P1b (aceitação/completude):** aceitação itera as condições PLANEADAS —
    zero runs ou n≠esperado = failed, nunca em branco; C10 exige
    `dropout_disconnects≥1` e `buffered_dropout≥1` + reconciliação com
    `/metrics`; C12 exige registo do hook de restart; DoD do soak (≥24 h,
    cobertura ≥99%, sem gaps >60 s, sem interrupção não recuperada); gaps
    >5 s quebram janelas "sustained"; saturação com veredicto
    `insufficient-evidence` quando falta evidência (regra estatística
    inalterada). Constantes novas marcadas "pending advisor sign-off".
  - **P1c (imutabilidade + batch):** raw write-once com diretórios selados
    (SHA256SUMS) — `collect` verifica checksums, só adiciona ficheiros em
    falta e regista `collection_history`; subcomando `campaign` executa o
    plano congelado pela ordem, com resume, stop-on-invalid, cooldowns e
    `campaign_log.jsonl`; **corrigido bug real de caminho** (o harness lia
    `sent_events.jsonl` fora do layout `<output>/<run_id>/` que o simulador
    escreve — o fake dos testes reproduzia o layout errado e escondia-o).
  - **P3 (selagem):** +x nos 3 scripts novos; `capture-sut-environment.sh`
    passou a emitir `node` (exigido pela validação); PROGRESS/backlog/
    riscos/título do doc G0 sincronizados (R16–R22 atualizados; RA1–RA15 da
    reanálise mapeados); re-execução da suite em HEAD limpo com evidência
    re-selada (ver `docs/evidence/tests/`).
- **Evidência:** suite completa **515 passed** (452 → 470 → 493 → 515);
  commits por entregável: P2 `59efa3f`, P1a `8a927d1`, P1b `8ee0370`,
  P1c `761c9a8`, P3 (este); dois PDFs compilam limpos.
- **Decisões/desvios:** "pre-registered"→"pre-specified" aplicado também aos
  caps. 1/6 e abstracts (coerência); refusal de overwrite aplica-se a
  qualquer ficheiro raw, não só a diretórios selados (write-once); timeboxes
  da ordem respeitados.
- **Próximos passos:** P4 (estudante): enviar email G0 + PDF standalone;
  WSL2; VM ARM64; bundle para fora do Nextcloud/remote; queries
  institucionais. Nenhum gate ou claim declarado aceite.
