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

## Entrada #C008 — Primeira execução real do Yocto (G1) e bloqueio da VM ARM64
- **Data:** 2026-08-10 (noite) / 2026-08-11
- **Fase:** P4 — ações externas; G1 iniciado
- **Ação:** WSL2 instalado pelo estudante; ambiente preparado e **primeiro build
  Yocto real** lançado. Tentativa de criar a VM ARM64 em três fornecedores.

### Ambiente (evidência de G0/G1)
- **Ubuntu 26.04 rejeitado antes de custar tempo:** `wsl --install -d Ubuntu`
  instala hoje o 26.04, que traz **Python 3.14**; o BitBake do Scarthgap
  (abril/2024) é anterior às remoções de stdlib do 3.13/3.14 e o 26.04 não
  consta dos hosts validados. Substituído por **Ubuntu 24.04.4 LTS**
  (Python 3.12.3). Registado em `docs/setup/wsl2_ubuntu_yocto.md` (commit
  `8f2e4af`) com data e razão — é uma armadilha de reprodutibilidade típica:
  o mesmo comando dá hosts diferentes ao longo do tempo.
- Host de build: 16 cores, 31 GiB RAM, 955 GiB livres em **ext4**; repositório
  clonado para `~/yocto/egw` (nunca `/mnt/*`), conforme plano §5.1.

### Resultado do build
- **Parse: 2888 receitas, 4830 targets, 0 erros.** Primeira confirmação de que
  a layer `meta-egw`, o `LAYERSERIES_COMPAT` e as três receitas próprias
  (`egw-image`, `egw-base-config`, `egw-container-smoke`) são válidas num
  ambiente Yocto real — até aqui eram M1 (texto plausível nunca executado).
- **Os três pins de layers resolveram todos**, incluindo o commit
  `0d9fb7f` de `meta-virtualization`, que quando foi registado tinha **uma
  única fonte online** (o cgit oficial recusava fetches automatizados). Fica
  agora confirmado contra o repositório canónico.
- Build em curso à data desta entrada (tarefa 4386/5715, 0 erros).

### Dois defeitos reais encontrados no meu próprio trabalho Yocto
1. **Corrida no make paralelo do perl** (commit `e83fb24`). Falha intermitente,
   dependente do número de cores: o `ExtUtils::MakeMaker` regenera sub-Makefiles
   a meio do `do_compile` e pede que o make seja relançado; sob `-j 16` os jobs
   irmãos abortam. Corrigido com `PARALLEL_MAKE:pn-perl = "-j 1"` em vez de
   repetir até calhar — um build que passa umas vezes e falha outras não
   sustenta o claim C01.
2. **`DL_DIR`/`SSTATE_DIR` efémeros** (commit `c0ebf7c`) — **o mais grave**. O
   kas corre o BitBake com `HOME` substituído por uma pasta temporária
   (`kas/libcmds.py`: `tempfile.mkdtemp()` → `ctx.environ['HOME']`), pelo que
   `DL_DIR ?= "${HOME}/yocto-cache/downloads"` resolvia para `/tmp/tmpXXXX/...`.
   **Todos os builds começavam com cache vazia e perdiam-na no fim**, e o
   segundo falhou no `do_unpack` porque os stamps diziam "já descarregado"
   enquanto o tarball tinha desaparecido com a pasta temporária. Corrigido com
   a secção `env:` do kas (`EGW_CACHE_DIR`), que o kas passa ao BitBake via
   `BB_ENV_PASSTHROUGH_ADDITIONS`. Verificado: a cache persiste agora em
   `~/yocto-cache` (8,1 GiB à data desta entrada).

   **Impacto no claim C01:** o build era, de facto, não reproduzível — e
   nenhuma inspeção estática do manifesto o revelaria. Só aparece a quem o
   executa duas vezes e repara que a segunda não é mais rápida. Material
   direto para o capítulo de reprodutibilidade.

### VM ARM64 — bloqueada em três fornecedores (risco materializado)
| Fornecedor | Resultado |
|---|---|
| Oracle Cloud (Always Free, Ampere A1) | **Beco sem saída.** A *home region* é fixada no registo e não se muda; contas Always Free só podem usar essa região. Madrid sem capacidade A1 ⇒ conta estruturalmente bloqueada |
| Hetzner Cloud (CAX, Ampere Altra) | Todas as instâncias ARM indisponíveis |
| Azure for Students | Regiões limitadas a 5 (as restantes «não elegíveis»); quota **0 of 0** em todas as famílias ARM dedicadas (Dpsv5/v6, Dplsv5/v6). Só a **série B (burstable)** está disponível sem pedido de quota |

**Decisão (a validar com os orientadores):** a série B é **inaceitável como
plataforma de medição** — é *burstable* por créditos de CPU, pelo que o
load-sweep a 250 msg/s e o critério de saturação (CPU > 90 % sustentada)
mediriam o estrangulamento da faturação em vez do gateway, invalidando a RQ3.
Passa a existir um **terceiro degrau de plataforma**, extensão natural do
ADR 0001:

| Papel | Plataforma | Números na dissertação |
|---|---|---|
| Funcional (SO) | QEMU/`qemuarm64` no WSL2 | Nunca (plano §5.1) |
| Integração ARM64 | Azure `B4pls_v2` (burstable) | **Nunca** |
| Medição (RQ3) | `D4pls_v5` (se a quota for aprovada) ou AWS `c6g.xlarge` | **Exclusivamente daqui** |

Pedidos de quota submetidos para as famílias **DPLSv5** e **DPLSv6**
(Germany West Central, 4 vCPU). Fallback com custo conhecido: AWS
`c6g.xlarge` (4 vCPU Graviton2, 8 GiB, dedicado), ~7 EUR para a campanha
completa. Instâncias *burstable* (`t4g`, `Bpsv2`) ficam excluídas por motivo
metodológico, não de custo.

- **Próximos passos:** email G0 + PDF do capítulo 2 (atrasado desde 09/08;
  comunica também este risco, conforme plano §10); dois boots QEMU + smoke de
  container para fechar G1; micro-piloto assim que existir ARM64.

---

## Entrada #C007 — Sprint P5.4 (seis defeitos da auditoria de verificação)
- **Data:** 2026-08-10
- **Fase:** P5.4, autorizado pelo relatório
  `../ChatGPT/VERIFICACAO_P2_P1_P3_E_PLANO_P5_ANTES_P4_2026-08-08.md`
- **Ação:** As seis acusações técnicas do relatório foram **verificadas uma a
  uma contra o código antes de qualquer correção**; todas se confirmaram.
  Corrigidas por TDD (teste a falhar primeiro).
- **Resultado (commits `734d1ce`, `62b8b8b`):**
  1. **`analyze --plan`** — a completude por identidade existia mas era
     inalcançável pelo comando oficial (só por variável de ambiente não
     documentada); o subcomando passa a aceitar e propagar `--plan`.
  2. **Runs externos não selados** entravam nas estatísticas de duração; passam
     a exigir selo verificado (`integrity_ok == INTEGRITY_OK`).
  3. **C12** media apenas que o `GET /metrics` voltou a responder — renomeado
     para *endpoint recovery* e acrescentado um critério **funcional
     limitado no tempo**: primeira prova de que a ingestão retomou (primeiro
     evento aceite pós-restart no domínio de relógio do controlador, ou
     primeira amostra cujo contador ultrapassa a linha de base anterior).
  4. **Validação numérica estrita** — NaN, infinito, negativos e contadores
     fracionários eram aceites; `mem_bytes=inf` **rebentava a análise**
     (`int(float('inf'))` lança `OverflowError`, não apanhado por
     `except ValueError`). Um único `inf` no CPU fingia saturação; um `nan`
     tornava o `max()` dependente da ordem das linhas e desligava todas as
     comparações de limiar.
  5. **Marcador de confirmação** era lido depois de juntar os samplers (que
     podem bloquear ~25 s), alargando a janela efetiva para 60 + Δ s e
     enviesando a taxa de entrega para cima; passa a ser lido imediatamente
     após o fim da execução medida.
  6. **`campaign --start-from`** já não dispensa evidência externa saltada: os
     externos pendentes são contabilizados sobre o plano inteiro, a campanha
     reporta `incomplete` e sai com código não-zero.
  - Correção editorial: «registered» → «planned»/«specified» no capítulo 2
    (podia sugerir um protocolo formalmente pré-registado).
- **Evidência:** suite completa **618 testes** (593 → 618).
- **Decisões:** nenhum limiar estatístico, percentil, método de IC ou a janela
  de 60 s foi alterado; nenhum gate ou claim aceite.

---

## Entrada #C006 (sprint P5 — pré-voo antes do P4)
- **Data:** 2026-08-08
- **Fase:** Sprint P5 autorizado pelo Senior PM
  (`../ChatGPT/VERIFICACAO_P2_P1_P3_E_PLANO_P5_ANTES_P4_2026-08-08.md`)
- **Ação:** Dois bloqueadores críticos confirmados no código antes de agir, e
  corrigidos com teste de regressão a falhar primeiro.
- **Resultado:**
  - **Bloqueador 1 — prazo de confirmação circular** (regressão minha da ronda
    anterior): o prazo derivava de `max(received_monotonic_ns)+60 s`, pelo que
    a mensagem mais tardia empurrava o seu próprio prazo e nunca podia ser
    contada como perdida. Corrigido com um **marcador no domínio de relógio do
    controlador**: `GET /metrics` expõe `monotonic_ns`/`wall_utc` (aditivo), o
    harness lê-o ao fim da execução medida e grava
    `confirmation_deadline_clock_domain: "controller"`; a análise só confia no
    manifesto nesse caso. **A regra dos 60 s e a métrica de latência não
    mudaram** (CONTRACTS §5, secção nova). Regressão verificada empiricamente:
    com o ramo desligado a mensagem tardia conta como entregue; com o ramo
    ativo conta como perdida.
  - **Bloqueador 2 — `campaign` não era end-to-end**: só expandia um template
    para um CSV que tinha de existir; numa campanha nova a primeira execução
    cronometrada ficaria inválida pelas regras do P1a. Corrigido com hooks
    parametrizáveis start/stop/fetch do collector, executados pela ordem certa
    e registados no manifesto com exit codes (hook falhado ⇒ run inválido).
  - **Integridade e completude:** SHA256SUMS verificados antes de qualquer
    agregação (runs adulterados ou não selados excluídos e assinalados);
    completude por **identidade** contra o plano (run_id, repetição, seed,
    taxa), por nível de carga no sweep; artefactos obrigatórios por condição —
    em falta ⇒ inválido **e sem selagem**; resume verifica checksums;
    campanha completa com condições externas pendentes já não termina limpa.
  - **Qualidade das séries:** validação semântica de `resources.csv` e
    `controller_metrics.csv` (timestamps, instantes distintos, monotonia,
    numéricos, colunas), head gap medido, cobertura mínima também exigida às
    métricas do controlador; C12 passa a exigir evidência de recuperação real.
  - **P5.0:** PDF standalone do cap. 2 sem os 23 avisos de labels duplicadas,
    com metadata (título/assunto/keywords; sem dados pessoais inventados).
  - **P5.2:** ensaio seco arquivado em
    `docs/evidence/rehearsal/2026-08-08-dry-rehearsal.md` — plano determinista
    (SHA-256 idêntico com a mesma seed), 95 runs (25 externos + 70 do
    simulador), sweep com 10 runs por carga em ordem congelada, `--dry-run`
    sem criar artefactos, e **piso logístico de 33,17 h** só para os runs do
    simulador (soak 24 h incluído), excluindo externos, setup, transferências,
    análise e repetições.
  - **P5.3:** varrimento documental (drift de `run_id` na matriz, tabela
    RA1–RA15 com RA15 materializado, 7 full-text vs 18 título/resumo).
  - **Nota de método:** a tentativa interrompida do agente de análise tinha
    deixado grande parte do código **morto** (helpers e colunas declarados mas
    nunca chamados por `compute_run_metrics`). Só os testes o revelaram — o
    que confirma a regra de não aceitar implementação sem teste que a exercite.
- **Evidência:** **593 testes** (515 → 593); commits `33d004c`, `d3e25ca`,
  `e2d5113`, `c025d8d`, `03ee5c9`.
- **Decisões/desvios:** nenhuma regra estatística, percentil, método de IC ou
  janela de 60 s foi alterada (condição de paragem respeitada); constantes
  novas marcadas "pending advisor sign-off"; nenhum gate ou claim aceite.
- **Próximos passos:** P4 (estudante). Ao primeiro sinal de VM/WSL2, parar o
  trabalho de secretária e ir para o micro-piloto (smoke → nominal curto →
  dropout → restart) antes de qualquer campanha oficial.

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

---

## Entrada #C006
- **Data:** 2026-08-08
- **Fase:** Adenda de rastreabilidade ao bloco P3 (sem trabalho técnico novo)
- **Ação:** Registo dos identificadores exatos da evidência de P3, que a
  entrada #C005 descrevia apenas por referência genérica
  («ver `docs/evidence/tests/`»). A verificação externa de 08/08 assinalou
  esta imprecisão; esta entrada fecha-a. Nada aqui altera o estado de
  nenhum gate nem valida nenhum claim.
- **Identificadores exatos:**
  - **Caminho da evidência de P3:**
    `docs/evidence/tests/2026-08-08-head-ca445a3/`
    (contém `junit.xml`, `pytest-stdout.txt`, `environment.txt` e
    `SHA256SUMS` dos três).
  - **Commit testado (árvore exata sob teste):**
    `ca445a31e5d146cf0c214b3cd4a23a95a48b5289` (abreviado `ca445a3`), com
    **tree hash** `b767b229e295b9453cbc2efcbfd0122bf8409d38`;
    `git status --porcelain` vazio no momento da execução. Ambos os valores
    lidos de `environment.txt` do próprio diretório de evidência.
  - **Resultado:** `515 passed` em 7,10 s (Windows 11 Pro, Python 3.14.3,
    venv com `src/requirements.lock`), comando
    `python -m pytest tests -q --junitxml=junit.xml` a partir de `Claude/src`.
  - **Commit da evidência:** `9491090` — é o commit que **acrescenta** o
    diretório de evidência e, por construção, é posterior a `ca445a3`; toca
    apenas ficheiros sob `docs/evidence/tests/` e não altera código. A
    distinção entre commit testado e commit da evidência é intencional e não
    deve ser colapsada.
  - **Bundle final de backup:** `backups/egw-20260808-final.bundle`
    (991 862 bytes; SHA-256
    `edf0c2409052498533667b78719c85468a8eba05d87b605b4ce0440fa35ba017`,
    recalculado localmente em 08/08 e coincidente com o valor da verificação
    externa; contém a história completa com `main`/HEAD em `9491090`).
    Substitui `backups/egw-20260808.bundle`, anterior e mais curto.
- **Limitações registadas:** a suite é unitária, com fakes, em Windows — nível
  **M2**. Existem **zero** testes `integration`. O bundle continua dentro do
  domínio Nextcloud, pelo que **não é ainda um backup independente** (risco
  R25/RA13 permanece aberto, dependente de ação do estudante).
- **Retificação a #C005:** a formulação «RA1–RA15 da reanálise mapeados» usada
  na entrada #C005 era **demasiado ampla** e foi retirada de
  [`docs/g0/riscos.md`](docs/g0/riscos.md). Vários RA estavam apenas implícitos
  nas linhas R16–R27 e **RA15 (ausência de horas/forecast) está materializado**,
  não mitigado. O ficheiro de riscos passa a seguir RA1–RA15 linha a linha, com
  estado explícito e evidência ou dependência bloqueante por risco.
- **Próximos passos:** inalterados face a #C005.
