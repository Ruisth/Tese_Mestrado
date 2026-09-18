# LOG — repositório Claude (Tema 1, Edge Gateway)

Formato: **Data · Fase · Ação · Resultado · Artefactos · Decisões · Próximos passos**
(igual ao `../LOG_Projeto.md`; este LOG cobre apenas o trabalho dentro de `Claude/`).

> **Ordering, identifiers and language (note added 2026-08-12).** Entries are
> listed by identifier, ascending. Identifiers are assigned when an entry is
> written and are never reused, so a renumbered entry may carry an earlier
> date than the entry before it — see `#C010`, published as a second `#C006`
> and renumbered on 2026-08-12 to remove the collision, with its date and
> content unchanged. Entries written from 2026-08-11 onwards are in British
> English, per [`docs/governance/language-policy.md`](docs/governance/language-policy.md);
> the earlier Portuguese entries are historical records and are corrected only
> by dated notes, never rewritten.

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
  [`docs/g0/risks.md`](docs/g0/risks.md) (então `riscos.md`). Vários RA estavam apenas implícitos
  nas linhas R16–R27 e **RA15 (ausência de horas/forecast) está materializado**,
  não mitigado. O ficheiro de riscos passa a seguir RA1–RA15 linha a linha, com
  estado explícito e evidência ou dependência bloqueante por risco.
- **Próximos passos:** inalterados face a #C005.

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

## Entrada #C009 — Imagem EGW-OS construída; publicação do repositório
- **Data:** 2026-08-11
- **Fase:** G1 (build) e G0 (preservação)

### Build concluído
`kas build` terminou com **5715 tarefas, todas com sucesso** (5161 servidas pela
sstate cache — confirmação de que a correção do `DL_DIR`/`SSTATE_DIR` funciona).
Artefactos em `build/tmp/deploy/images/qemuarm64/`:

| Artefacto | Dimensão |
|---|---|
| `egw-image-qemuarm64.rootfs.ext4` | 382 MiB |
| `Image` (linux-yocto 6.6.142) | 23 MiB |
| `rootfs.manifest` | 639 pacotes |
| SBOM SPDX | incluído |

O manifesto confirma os componentes exigidos pelo âmbito P0: `docker-moby
25.0.9`, `containerd 2.0.10`, `runc 1.1.14` e `systemd`.

**G1 continua ABERTO.** A imagem existir não fecha o gate: faltam os **dois
boots QEMU registados** e o **smoke de container dentro do guest**, que são a
evidência exigida pelos claims C01 e C02. Zero boots executados até à data.

> **Correction added 2026-08-12 — superseded by #C011.** «Zero boots
> executados até à data» was accurate when this entry was written and stopped
> being accurate later the same day: two unattended QEMU bring-up boots were
> driven by `src/yocto/scripts/boot_check.py` (commit `32f6604`) and both
> passed — 6 of 6 required assertions passed, 3 of 3 supplementary
> observations recorded, clean power-down confirmed — with the evidence
> sealed in `docs/evidence/g1-yocto-qemu/`. The rest of the paragraph still
> holds: gate G1 is **not** accepted — the evidence exists, the acceptance
> decision does not. The original sentence is left exactly as written, as the
> record of the state at that moment.

### Quarto defeito encontrado pela execução real
Ao terceiro insucesso do `perl do_compile` — em três módulos diferentes
(`Pod-Escapes`, `JSON-PP`, `Time-Local`) e já com `-j 1` — ficou claro que o
diagnóstico inicial de corrida no make paralelo estava **errado**: era uma
hipótese que encaixava no primeiro sintoma. A causa real é instabilidade do
relógio do WSL2, medida contra o relógio do Windows (−0,45 s → +0,35 s →
+1,33 s em 40 s sob carga), que faz o `make` ver `Makefile.PL` com data no
futuro e disparar o protocolo «rerun make» do MakeMaker. Resolvido em
`4720327` fixando a data dos `Makefile.PL` antes do compile, o que torna o
build independente do relógio do host — mais reproduzível, não menos.

### Publicação
Repositório privado `Ruisth/Tese_Mestrado` criado e ligado, com ruleset a
exigir pull request em `main` e `dev` e a proibir force-push e eliminação.
Modelo de trabalho: ramo `<tipo>/g<gate>-<objetivo>` → PR para `dev`;
`dev` → PR para `main` apenas em versões estáveis. O histórico foi limpo de
trailers de coautoria antes da publicação; todos os commits têm autoria única
do estudante. Risco R25/RA13 (perda do repositório) passa a mitigado: o
histórico existe agora num domínio de falha independente do disco local.

- **Evidência:** `docs/evidence/tests/2026-08-11-head-19d74ff/` (618 testes,
  HEAD limpo `19d74ff`).

---

## Entrada #C010 (sprint P5 — pré-voo antes do P4)

> **Renumbering note (2026-08-12).** This entry was published as a second
> `#C006`; it is renumbered here to remove the collision. Its date, content and
> evidence are unchanged. `#C006` keeps the traceability addendum to block P3,
> which other documents already cite by that identifier. Identifiers are
> assigned when an entry is written and are never reused, which is why `#C010`
> carries an earlier date than `#C009`.

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

## Entry #C011 — Gate G1 evidence: two unattended QEMU boots, sealed archive, language policy, first merged pull requests

- **Date:** 2026-08-11/2026-08-12
- **Phase:** G1 (functional platform — bring-up of the built image) and G0
  (governance and preservation)
- **Language:** first entry written under
  [`docs/governance/language-policy.md`](docs/governance/language-policy.md)
  (British English, sole working language since 2026-08-11). The entries above
  stay in Portuguese: published history is corrected by dated notes and never
  rewritten.
- **Action:** the `egw-image` recorded in #C009 was taken through **unattended**
  QEMU bring-up, the evidence was sealed and verified from a clean clone, the
  repository moved to a pull-request workflow, and the language policy was
  adopted. Entry #C009 said "Zero boots executados até à data"; that stopped
  being true later the same day and the correction is noted there.

### The boots were driven by a program, not typed by a person

`src/yocto/scripts/boot_check.py` (added in `3a9900e`, final state at
`32f6604`) attaches to the serial console over a pseudo-terminal, logs in, runs
a fixed list of in-guest checks, records the whole session and decides the
outcome from the output, exiting non-zero when a required check fails. It
replaces the interactive `run-qemu.sh`, which produced a console log only if a
human sat at the terminal and typed the checks — reproducible by nobody. Each
run writes `<name>.log` (the full console session) and `<name>.result.json`
(the per-check verdicts).

### Six defects that only running the thing could expose

None of them was visible by reading the code or the recipes. All were defects
in **how the evidence was collected**, not in the image being evidenced.

1. **BusyBox rejects the `head -N` shorthand** — two checks died on
   `head: invalid option`. Now `-n N` (`024115e`).
2. **`multi-user.target` was assumed to be the default target** — the driver
   asserted that unit active; the image reported it inactive while the system
   was running normally. The driver now reads the default target from the unit
   list and asserts that *that* target is active (`024115e`, `799ee48`).
3. **Kernel messages drown the console during container teardown** — the burst
   produced by container networking swallowed the completion marker and the
   smoke check timed out mid-teardown. The driver now raises the console log
   level after login, widens the terminal so long command lines are not
   wrapped, and gives the container checks their own longer timeouts
   (`024115e`).
4. **A dynamically linked BusyBox left without its loader** — the smoke image
   carried the binary and not its interpreter, and the kernel reports the
   missing **INTERPRETER** as "no such file or directory", which reads as if
   the binary itself were absent. The loader is now bundled (`799ee48`).
5. **usrmerge makes `/lib` and `/usr/lib` the same file on the host and two
   distinct paths inside a container** — `INIT_MANAGER=systemd` pulls usrmerge
   in, so on the running system the two spellings name one file; inside a
   freshly imported container rootfs they are two directories, and only the
   spelling recorded in the binary's `PT_INTERP` is consulted. Copying to one
   side left the other missing. Every object now goes under both names
   (`f53bb4b`).
6. **A check passed by matching its own command echo** — the systemd check
   searched for the word `running` and matched it inside its own
   `systemctl is-system-running` invocation, reporting a pass **while the
   system was still starting**. Checks are now bracketed by begin/end markers
   written as split literals, so only the text between them is judged, and the
   systemd check uses `is-system-running --wait` so every later check observes
   a settled system (`38e48f4`).

Two further faults of the same class were found while fixing these and are
recorded for the same reason: a stray `0x08` byte inside the systemd pattern,
invisible in a normal diff and only visible under `cat -A`, made that pattern
unmatchable (`05166eb`); and the driver's own verdict was untrustworthy
(`32f6604`) — a timed-out command could still be judged a pass because the
read result was discarded, `clean_poweroff` was recorded but excluded from the
decision, and three entries that assert nothing were being counted as
verification, which is what produced the earlier "9 of 9 checks" headline.
Entries now declare a kind, required assertions and supplementary observations
are reported separately, and 18 tests bind this behaviour through a fake
console, so no test starts a virtual machine.

### The two boots, with the result shape exactly as recorded

Both boots were driven by `boot_check.py` at commit `32f6604` — they were
**not** manual.

| Boot | Outcome | Required assertions | Supplementary observations | Clean power-down |
|---|---|---|---|---|
| `boot1` | pass | 6 of 6 passed | 3 of 3 recorded | confirmed |
| `boot2` | pass | 6 of 6 passed | 3 of 3 recorded | confirmed |

The six **required assertions** are what was verified: architecture and release
(`aarch64`, kernel 6.6.142, Poky 5.0.19 scarthgap); systemd state after
`is-system-running --wait`; the target list showing `multi-user.target` active;
networking with a slirp lease; the container runtime reporting a server version
(Docker 25.0.9, `overlay2`, systemd cgroup driver); and the in-image container
smoke test, which builds a single-layer OCI image from the target's own
BusyBox, imports it, runs a command inside it and removes it — the runtime
exercised end to end with no registry access.

The three **supplementary observations** (the failed-unit list, empty in both
boots; gateway reachability; the smoke diagnostics) are recorded for diagnosis,
**assert nothing and are never counted as verification**. One of them reports
`INTERP=unavailable` because the image carries no binutils and neither
`strings` nor the `tr` fallback is usable — it says so plainly instead of
printing a fabricated value.

Nothing timed in these runs is reportable. QEMU is the functional platform:
**no QEMU result supports a performance or a security statement.**

### Sealing, and two defects in the seal itself

Evidence archived in `docs/evidence/g1-yocto-qemu/` (`d15ac8b`): both console
sessions, both per-check result files, the build and checkout logs, the
639-package image manifest, the image and kernel digests, and `SHA256SUMS`
covering every file. The seal was wrong twice before it was right:

- the four `*.log` files listed in `SHA256SUMS` were kept out of the tree by
  `.gitignore`, so `sha256sum -c` could not succeed from a clean clone — the
  seal covered files nobody else could obtain. The exception was added and the
  files tracked (`32f6604`);
- `SHA256SUMS` had been written from PowerShell, in CRLF, so verification
  failed on every entry with "No such file or directory": it was looking for
  filenames with a trailing carriage return. All sealed text is LF now and
  every archive was re-sealed against the normalised bytes (`a6bcb27`).

Unit-test evidence for the integrated tree: **`701 passed`** over clean HEAD
`4e67717`, sealed in `docs/evidence/tests/2026-08-11-head-4e67717/` with the
interpreter path, `python -VV`, `pip freeze`, `pip check`, the pytest version,
the SHA-256 of `src/requirements.lock` and `SHA256SUMS` (sealed by `ddb9cbd`,
which is necessarily later than the commit it tests). The earlier figures
(`683`, `618`, `593`, `515`) are **historical**, each tied to the commit it
tested, and none of them is the current figure.

The evidence README and PROGRESS were corrected from "9 of 9 checks" to six
required assertions passed and three supplementary observations recorded
(`4e67717`, `ddb9cbd`, `df57d6c`), which is what the driver actually verified.

### State, stated plainly

- **Gate G1: evidence produced, acceptance PENDING.** Building, booting,
  merging and archiving demonstrate implementation and verification; accepting
  a gate is a separate decision, recorded in `PROGRESS.md` and in Annex C of
  the plan. **No gate has been accepted.** *(Dated note, 2026-08-14, later the
  same day: true when written; gate G1 was subsequently accepted — see #C015
  and the gate decision log.)*
- **Claims: 0 of 15 accepted.** C01 is partial — the rebuild from an
  independent clean checkout is still missing and belongs to G4. C02 holds the
  evidence of the **two bring-up boots**; the campaign's five `qemu_boots` runs
  are a separate, later set produced under the frozen protocol. The remaining
  13 claims have no evidence.
- The **ARM64 measurement VM still does not exist**: risk R28 is materialised,
  and R29 is why no
  burstable instance may produce a number. The three-tier platform model, until
  now recorded only in `PROGRESS.md` and in this LOG, is written up as
  [ADR 0007](docs/adr/0007-three-tier-platform-model.md) (**Proposed**, awaiting
  supervisor validation), which extends ADR 0001.

### Governance: language policy and the pull-request workflow

- **British English (en-GB) is the sole working language since 2026-08-11**
  (`eaf0733`), for all new and modified content. The only academic exception is
  the Portuguese Resumo and any front matter the university makes mandatory in
  Portuguese; drafts of external administrative communication, such as the
  supervisor emails, may also stay in Portuguese. Legacy Portuguese documents
  migrate in tracked batches; sealed evidence, published history, identifiers
  and machine-readable values are never translated.
- The private remote `Ruisth/Tese_Mestrado` (HTTPS) carries a ruleset requiring
  pull requests on `main` and `dev` and forbidding force-push and deletion.
  `dev` is the integration branch; `main` receives stable versions by pull
  request only. `refs/tags` stays empty, by choice.
- **Four pull requests were opened; #1 was closed and superseded.** Merged into
  `dev`: **#2** the P0 baseline (`e40b0a1`), **#3** repository governance
  (`238474b`), **#4** the gate G1 evidence (`e8647cc`).

### Decisions and next steps

- **Decisions:** no gate accepted, no claim validated and no maturity level
  raised by this work; the QEMU/measurement separation is unchanged and is now
  three-tier under ADR 0007 (Proposed); the six defects were corrected before
  the sealed run rather than worked around, and the driver was fixed *before*
  being reused for the campaign's five boots.
- **Next steps:** send the G0 email with the chapter 2 PDF and report the
  ARM64 risk to the supervisors, as the plan's rule §8.1 requires from
  2026-08-12 (student actions); obtain a dedicated ARM64 instance (approved
  quota or the AWS `c6g.xlarge` fallback); run the campaign's five QEMU boots
  under the frozen protocol; record the formal gate G1 decision.

## Entry #C012 — Plan v1.1 implementation and strict G1 campaign

**Date:** 2026-08-14 (Europe/Lisbon; execution crossed midnight from
2026-08-13)

**Scope:** governance/provenance controls, technical integrity blockers,
factual academic corrections, clean-checkout Yocto build and five strict QEMU
boots

**State decision:** G1 remains **In progress**; **0 of 15 claims accepted**

The restructuring was implemented through normal pull requests against `dev`:
PR #12 versioned plan v1.1, provenance and technical CI; PR #13 corrected the
evidence-integrity blockers; PR #14 merged only factual academic corrections;
the supervisor-dependent title/RQ/abstract package remains isolated in draft
PR #15; PR #16 synchronised the operational records; PR #17 hardened the
five-boot execution path; and PR #18 corrected the PTY state predicate. All
merged pull requests passed the required checks and their review threads were
resolved. The protected historical tag
`evidence/g1-yocto-build-5770c0a` preserves the exact preliminary build.

### Clean-checkout build

A new ext4 checkout at
`/home/ruisth/yocto/egw-g1-20260813-f0e19d5` was created at
`f0e19d5a51b4ade1e0637e6bff135c737996b1ba`; it had no pre-existing layer or
build directories. `kas checkout` resolved the three pinned layer commits and
the build completed all 5,715 tasks successfully. The external downloads and
sstate cache were shared by design: 2,261 tasks did not need to be rerun and
the sstate match was 55%, so this is a clean-checkout build, **not** a
cold-cache claim.

The resulting package manifest has 639 entries. The source artefacts were
hashed twice before sealing:

- rootfs: 2,607,275,008 bytes, SHA-256
  `6c37fcc10e31702e21ce5d9c73f7cb6aabd4fa512ef50680f8f1434d6a721da0`;
- kernel: 24,150,528 bytes, SHA-256
  `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037`.

### Preserved instrumentation failure and five fresh passes

The first strict attempt, `qemu-boot-01`, reached the console, reported exact
`STATE=running`, zero failed units, executed the offline container smoke test
and powered down cleanly. The driver nevertheless returned `fail` because its
pre-fix predicate rejected the doubled carriage returns emitted by the PTY.
That result and its raw log are preserved without relabelling or overwrite.

PR #18 changed the state predicate to accept only the stripped exact value
`STATE=running`, added a regression for the doubled carriage returns and kept
extra output/degraded state rejected. After the checkout was fast-forwarded to
the merged driver commit `9fe38ff4ed3c34915f506f1d3b91f3ba56b6df22`, five
fresh identities (`qemu-g1r2-01` to `qemu-g1r2-05`) were run. Every one:

- passed 7 of 7 required assertions, including exact `systemd=running` and
  zero failed units;
- recorded 2 of 2 supplementary observations, with gateway ping remaining an
  observation rather than a scientific gate;
- reached the console, completed the local OCI container smoke test and
  powered down cleanly;
- produced its own console log and result JSON with no timeout.

The build logs, environment, image metadata, invalid attempt and five counted
runs are sealed under
`docs/evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/`, independently of
the preliminary 2026-08-11 seal. PTY carriage returns in the raw console logs
are preserved as evidence bytes rather than normalised by Git.

### Interpretation and remaining blockers

This execution supplies the technical clean-build/five-boot artefacts requested
for G1, but producing and sealing evidence is not the formal gate decision.
C01 remains partial pending the D006 second-operator treatment; C02's strict G1
set does not silently replace the later predefined `data-v1` identities. No
QEMU output supports performance or security conclusions.

External state is unchanged: the alignment email and university ARM64 request
have not been sent, D001–D008 remain `proposed_not_sent`, the native
non-burstable ARM64 measurement VM and runtime lock do not exist, and no
off-machine bundle copy is recorded. G2 and all measurement gates therefore
remain blocked or pending exactly as stated in `PROGRESS.md`.

## Entry #C013 — Post-G1 local provenance bundle

**Date:** 2026-08-14

After evidence commit `d4bfa9d`, the complete-history bundle
`backups/egw-20260814-g1-strict-evidence.bundle` was created and verified with
`git bundle verify`. It is 1,819,509 bytes and has SHA-256
`5b2cf69fcb7bdee7f2e2916bccfc04d852fe8b91077a2d38accd02a96a2bab12`.
The bundle reports complete history and preserves 12 refs, including the
strict-evidence branch, `dev`, the draft academic proposal and the protected
preliminary G1 tag.

This is a local recovery object, not an independent backup. No off-machine
copy or remote destination has been recorded; risk R25 therefore remains
mitigating and G1 acceptance remains pending. *(Dated note, 2026-08-14, later
the same day: gate G1 was subsequently accepted — see #C015; the off-machine
gap is unchanged.)*

## Entry #C014 — PR #19 merge and post-merge recovery bundle

**Date:** 2026-08-14

PR #19 passed the six mandatory checks. A review found one stale claim summary
in `src/README.md`; commit `6e3dc5b` synchronised it while retaining 701 as the
last sealed test count, 718 as local-only, 0 of 15 accepted claims and the
separation between the strict G1 set and later `data-v1` identities. The thread
was answered and resolved. PR #19 was then merged into `dev` by merge commit
`c6668a88f02be5d73bac078bd241a04600e8c0b8`, and its work branch was deleted.

After that merge, `backups/egw-20260814-post-g1-merge.bundle` was created and
verified. It is 1,831,301 bytes, reports complete history with 12 refs and has
SHA-256
`35b7808072c2f3cfd82cfd9bfc40ce6769b8931d1301794332ef2e66fbd4abcb`.
The bundle remains on the same physical machine; the off-machine-copy blocker
is unchanged.

---

## Entry #C015 — Comparative audit, plan v1.2, gate G1 accepted, D009-D010
- **Date:** 2026-08-14
- **Phase:** Governance correction and proposal publication (pull requests #15 refresh and the truth-sweep PR)
- **Action:** A full comparative audit crossed the workspace (legacy management
  reports, university materials, the C2DTA paper, the supervisor template and
  seven questions), the repository and the GitHub remote. Verdict: the plan
  needed no new restructuring — v1.1 already is the restructuring — but it
  needed governance repair and, above all, sending: nothing had ever been sent
  to the supervisors. Actions taken in the repository:
  - **PR #15 refreshed and republished as PROPOSED documents**: merged `dev`
    (14 commits behind), replaced the stale status facts in the supervisor
    email with the sealed 2026-08-14 evidence (clean identified checkout build
    `f0e19d5`, five strict boots at 7 of 7 required assertions, the failed
    first attempt preserved), and added decisions **D009** (telemetry stays
    the contract term; thesis prose prefers "wearable event data") and
    **D010** (local persistence of twin state and evidence is by design) to
    the canonical log, the request matrix, the alignment memo and the email.
    Both raise documented deviations from the repository template, which the
    source register classifies as guidance, not an implementation contract.
    LaTeX integration remains blocked on D001.
  - **Plan bumped to v1.2**: the published v1.1 had been amended in place by
    the PR #19 merge (`c6668a8` added the gate-outcomes authority row),
    violating the plan's own rule that a change requires a dated new version.
    v1.2 records that amendment retroactively, fixes v1.1's final state as the
    file at `c6668a8`, changes no scope, schedule, gate or cut, and carries a
    citation-equivalence clause so that dated documents citing v1.1 —
    including sealed evidence — are never rewritten.
  - **Gate G1 formally accepted** (2026-08-14, student authority) in
    `docs/governance/gate_decision_log.md`, against the plan §4 criterion, on
    the strict capsule evidence. Scope: functional platform layer only; it
    validates no claim, supports no performance statement, and leaves D006
    with the supervisors. First closed gate of the project.
  - **Truth sweep**: the G1 criterion in the WSL2 guide (two boots by 16/08 →
    five strict boots, window 13–18 August); the false "unchanged since its
    adoption" sentence about the RQs in `01_introduction.tex` (they are
    proposed pending D001); provisional-title comments above both cover pages
    in `main.tex`; stale v1.0 gate dates in risk R2 marked as superseded;
    ADR 0007's escalation rule updated to the v1.1/v1.2 university-first,
    48-hour, EUR 30 procedure; ~25 citations of v1.0 section numbers across
    ten files requalified as `archived plan v1.0 §x` or remapped to their
    v1.1 equivalents (the archived §7 protocol has no v1.1 equivalent until
    `exp-v1` freezes under D007); chapter-2 word figure corrected to the
    texcount measurement (4,361 body words); `PROGRESS.md` synchronised
    (PRs through #20, G1 Complete, D001–D010).
  - **Provenance**: EXT-014..017 register the four 2026-08-08 external
    management reports (single unbacked copies on this disk — now flagged for
    every off-machine backup); the bundle gap after PR #20 is recorded; a new
    protected tag `evidence/g1-bringup-driver-367c929` was created and pushed
    at the tip of `feat/egw-p0-baseline` (annotated tag object `b21db3d`,
    target `367c929`, verified on the remote with `git ls-remote`) so the
    preliminary-evidence driver lineage survives independently of the branch.
- **Result:** proposal package publishable and email ready to send; plan
  governance self-consistent again; one gate closed with a dated decision.
- **Still outstanding (student actions):** send the alignment email and record
  `sent_at`; make the university ARM64 request and start the 48-hour clock;
  uninstall the two review apps; copy the newest bundle and the four legacy
  reports off-machine and verify the hashes there. *(Dated note, 2026-08-14,
  later the same day: the uninstall obligation was lifted by the management
  register — review applications may review, comment and suggest; they remain
  forbidden as commit author/committer, co-author, attribution trailer or
  credited metadata author, which `metadata-policy.yml` already enforces. The
  other three actions stand.)*
- **Decisions:** G1 accepted (gate log is the authority); D009/D010 join the
  request set; the PR #15 draft rule is narrowed to LaTeX integration only,
  by the owner's explicit choice recorded in this session.

---

## Entry #C016 — Post-merge recovery bundle covering PRs #15 and #21
- **Date:** 2026-08-14
- **Phase:** Provenance (after the PR #15 and PR #21 merges into `dev`)
- **Action:** Created `backups/egw-20260814-post-pr21-merge.bundle` with every
  local ref, immediately after `dev` reached the PR #21 merge commit
  `f1ce8d9`. `git bundle verify` passes. It is 1,848,999 bytes, preserves 14
  refs — `dev`, `main`, `feat/egw-p0-baseline`, both merged pull-request
  branches and both protected evidence tags
  (`evidence/g1-yocto-build-5770c0a`, `evidence/g1-bringup-driver-367c929`) —
  and has SHA-256
  `116d59eba74e1583c96c556f2c9c5cb6525816cc5166d3852c0a2ddb81f9d5a9`.
  This closes the bundle gap recorded in #C015: the PR #20 merge and
  everything after it are now covered by a single verified snapshot. The root
  README's normative-source paragraph was aligned with plan v1.2 in the same
  change.
- **Result:** nine bundles inventoried in
  `docs/governance/provenance-history-rewrite.md`, all on this machine.
- **Still outstanding (student action):** copy the newest bundle — and the
  four EXT-014..017 reports — off this machine and verify the hashes at the
  destination. A local bundle is a recovery object, not an independent backup.

---

## Entry #C017 — Management audit response: G1 record sync and terminology delimitation
- **Date:** 2026-08-14
- **Phase:** Documentation-only pull request, ordered by the external
  management audit register of 2026-08-14 (EXT source, held outside the
  repository).
- **Action:** Verified every audit claim against the repository before acting.
  Two named targets were already done and are recorded as such: the bundle
  inventory already listed nine bundles (PR #22), and both claim matrices had
  been synchronised with the G1 acceptance during the PR #21 review round.
  What was genuinely outstanding and is fixed here:
  - `src/README.md` still said "no gate has been accepted" (phrase split
    across a line break, which the earlier sweep greps missed);
  - `PROGRESS.md` still counted eight bundles with the superseded latest
    bundle, and its PR ranges stopped at #20;
  - the risk register: R25 rewritten for nine bundles, the two protected
    tags, the new latest bundle and the honest observation that the
    "off-machine copy before G1 acceptance" deadline was missed; R27 extended
    with the post-acceptance drift recurrence; the real-execution narrative
    updated with the acceptance.
  - **Terminology delimitations** added as comparison rules 6–8 of
    `docs/academic/c2dta_p0_traceability.md` and propagated to the claim
    matrix, `experiments/results.md` and `diagrams/README.md`: the smartwatch
    profile is the paper-aligned workload while smart ring/clothing are
    dissertation extensions; `twin_creation` is first-contact technical
    provisioning, never the C2DTA business twinning ceremony; the cloud VM is
    an edge-class proxy, not a consumer-controlled physical gateway. Frozen
    contract identifiers are unchanged — the delimitation lives in prose.
- **Result:** every active record now reads G1 accepted (functional scope,
  claims untouched) and the C2DTA delimitations are stated where numbers
  would be interpreted.
- **Next:** the CONTRACTS.md translation follows as its own pull request, per
  the language policy's batch plan and the same audit's order.

---

## Entry #C018 — CONTRACTS.md translated into British English
- **Date:** 2026-08-14
- **Phase:** Language migration (the active contract), ordered by the external
  management audit of 2026-08-14 and scheduled by the language policy.
- **Action:** `src/CONTRACTS.md` translated in place from Portuguese to
  British English, prose only. An independent adversarial verification
  compared the translation token-by-token against the Portuguese original at
  git HEAD: every port, topic string, JSON field, endpoint, status code,
  environment variable, CLI flag, scenario name, image tag, threshold,
  duration, regex, placeholder and the UUIDv5 namespace are byte-identical;
  both fenced code blocks are byte-identical; the 12 headings and 7 tables
  keep identical structure. Verdict: clean, zero blockers. Deliberate
  differences, all recorded: the version-line date rendered as ISO 8601;
  decimal commas normalised to points (values unchanged); six backticked
  Portuguese metric terms in §9 translated after a repo-wide grep confirmed
  they are prose, not code identifiers; a one-line translation notice added
  under the title; the stale "integrated plan §5" citation qualified as
  archived v1.0 with the v1.1/v1.2 authority stated. The contract version
  remains v1.1 — translation is not a contract change. The language policy's
  migration table now records the contract as translated, leaving only
  isolated Portuguese comments in three code/test files for a bounded pass
  before `exp-v1`.
- **Result:** the last active Portuguese document in the repository is
  migrated; the remaining Portuguese is historical (LOG entries, archive) or
  exception-covered (supervisor email, Resumo).

---

## Entry #C019 — Final documentation pass of the 2026-08-14 audit cycle
- **Date:** 2026-08-14
- **Phase:** Documentation-only pull request closing the residual list of the
  external management register (post-PR-#24 audit). Every item verified
  against the repository before acting.
- **Action:**
  - **Gate-vs-claim separation completed**: the conflating phrase "formal G1
    admission" in `src/README.md` (split across a line break, which earlier
    sweeps missed), plus ambiguous "formal admission" wording in
    `src/yocto/README.md`, `PROGRESS.md` and the claim matrix, now read
    "formal claim admission" with the gate decision explicitly admitting no
    claim; the plan's dated gate-table snapshot gained a note deferring
    post-baseline outcomes to the gate decision log.
  - **Traceability and diagram updated**: the C2DTA traceability row that
    still said "a Yocto build and two QEMU boots" now records both seals and
    the accepted gate; the two-layer PlantUML dropped "PRELIMINARILY
    EVIDENCED" for "GATE G1 ACCEPTED 2026-08-14 (FUNCTIONAL SCOPE ONLY)" and
    its simulator label now reads "paper-aligned smartwatch profile + two
    dissertation extensions"; the SVG was regenerated from source with
    PlantUML under WSL2.
  - **D006 request row** updated to the clean-checkout build and five strict
    boots (second-operator reproduction still pending).
  - **Bibliographic protocol v1.1**: normative basis repointed at the
    in-repository plan v1.2; archived-v1.0 section citations qualified; no
    method, query, criterion or target changed.
  - **Template claim corrected**: the ISCTE LaTeX template is no longer
    described as "official" — its 2026 status is exactly decision D004.
  - **R31 cause corrected**: the first build's perl failure was misdiagnosed
    as a parallel-make race; the demonstrated cause was WSL2 host-clock
    drift, consistent with R2.
  - **Platform terminology**: "dedicated" replaced by "non-burstable native
    ARM64" in all active platform terminology (ADR 0007 title and body,
    ADR 0001, both indexes, the VM guide, PROGRESS, the Yocto README) —
    dedicated tenancy was never evidenced. "Dedicated ARM family" survives
    only where it quotes Azure's own family classification or historical risk
    narrative. The 4 vCPU / 8 GiB / 80 GB profile is now framed as a
    pre-specified fixed resource envelope selected for feasibility, cost and
    experimental control — it does not originate in the C2DTA paper (which
    evaluated on an x86 VM with 16 GB/32 CPUs and sizes no ARM64 host) and
    the admissibility conditions for a different profile are stated.
  - **Bundle**: `backups/egw-20260814-post-pr24-merge.bundle` created from
    `dev` at `e8bf965` before this entry (1,865,313 bytes, SHA-256
    `95288fba…`, 21 refs, `git bundle verify` passing) — the designated
    off-machine-copy artefact, inventoried as the tenth bundle.
  - **Review-application policy change recorded** with a dated note at
    #C015: the uninstall obligation is lifted; reviewing and commenting are
    permitted; authorship, co-authorship, trailers and credited metadata
    remain forbidden and machine-enforced.
- **Result:** the residual documentation list of the audit cycle is closed.
  Per the same order, desk work stops here: the next technical action is G2 on
  a non-burstable native ARM64 host, starting with the paper-aligned
  smartwatch profile at 1 Hz, as soon as the host exists.
- **Still outstanding (student actions):** send the alignment email and
  record `sent_at`; university ARM64 request (48-hour clock); off-machine
  copy of the `95288fba…` bundle + EXT-014..017 + checksum record, with
  destination-side hash verification, `git bundle verify` and a restore
  drill.

---

## Entry #C020 — Post-PR-#25 residuals: the md/CSV matrix contradiction and six leftovers
- **Date:** 2026-08-14
- **Phase:** Minimal documentation repair ordered by the post-PR-#25 audit;
  every finding verified against the repository first. All nine were real.
- **Action:** The claim matrix's Markdown table rows C01/C02 still carried
  "G1 acceptance remains pending" and "Formal G1 admission is pending" while
  the CSV had been corrected — the two forms of the same matrix contradicted
  each other; the Markdown rows now mirror the CSV wording (gate accepted
  2026-08-14, functional scope, claim admission a separate pending step).
  Also fixed: the Yocto README's G1-window paragraph ("remains in progress"
  → accepted the same day, decision in the gate log); the PROGRESS effort row
  still calling the gate decision pending; PROGRESS PR ranges through #25;
  "dedicated" → "non-burstable native" at the three remaining sites in
  `diagrams/architecture.md` — two prose occurrences plus one Mermaid node
  label (the node was caught by review after the prose fix); the simulator README's "three C2DTA
  wearables" → the paper-aligned smartwatch and two dissertation extensions;
  and `main.tex`'s comment no longer calls the template official (D004).
- **Deliberately not fixed:** `egw-image.bb`'s DESCRIPTION still says "two
  QEMU boots" — editing the recipe would change its checksum and force a
  rebuild for a metadata string; per the management order it is corrected
  only at the next functional rebuild.
- **Bundle (unversioned, per the same order):**
  `backups/egw-20260814-post-pr25-merge.bundle` created from `dev` at the
  PR #25 merge `2dafae1` — 1,890,507 bytes, SHA-256 `53014902…`, complete
  history, `git bundle verify` passing — handed to the student with its
  `.sha256` file for the off-machine copy, deliberately NOT added to the
  provenance inventory (no dedicated recording pull request). The `95288fba…`
  post-PR-#24 bundle is preserved as an additional baseline.
- **Result:** desk work ends here. Next development: the paper-aligned
  smartwatch at 1 Hz on a non-burstable native ARM64 VM → MQTT/TLS →
  controller → Ditto → API (gate G2), once the host exists.

---

## Entry #C021 — Import the supplied Word manuscript into canonical LaTeX

- **Date:** 2026-09-17
- **Phase:** Source-faithful dissertation format conversion; no governance,
  experimental or bibliographic-metadata revision.
- **Source:** `Dissertation_Rui Duarte_Digital Twin Edge Gateway.docx`,
  SHA-256
  `c589422a42318cf1635ad895cbe23cd24e2157ed569554a8ab3cd5dcaea25945`.
- **Action:** Import the supplied Introduction and Theoretical Framework,
  three tables, one research-process figure and 33 reference strings into
  `thesis/latex/`, retaining the supplied `Template_LaTeX` formatting base,
  two covers and logos. Preserve the Word title and known administrative
  fields; leave unknown supervisor details blank. Leave Chapters 3–6 and
  unprovided front-matter content empty apart from structural headings.
  Refresh the generated Markdown mirrors and source documentation.
- **Bibliography boundary:** Preserve the Word reference strings through
  Biber/IEEE with a custom verbatim-reference driver; no new metadata audit
  or correction is asserted. The existing research register is unchanged.
- **Verification record:** [WORD_IMPORT.md](thesis/latex/WORD_IMPORT.md) and
  [word-import-manifest.json](thesis/latex/word-import-manifest.json).
  Local source-fidelity checks, seven projection regression tests, identical
  Markdown regeneration and both PDF builds passed. The PDFs contain 43 and
  10 pages respectively, without unresolved citations or overfull boxes;
  evidence is sealed under `docs/evidence/word-import-2026-09-17/`.
  Historical page counts and checksums above remain records of earlier
  drafts; they do not verify the imported manuscript.
- **Governance boundary:** Integrated-Yocto wording is supplied manuscript
  content, not adoption or approval of a new plan version. The current
  source snapshot supersedes earlier draft-completeness descriptions only.
  No gate, research claim or supervisor decision is accepted by the import;
  D001/D004 and the existing evidence requirements remain separate controls.

---

## Entry #C022 — Refresh the project overview and complete the CI font dependency

- **Date:** 2026-09-17
- **Request:** Update the root README to describe current project state, not
  the manuscript's format conversion.
- **Action:** Summarise the implemented components, accepted functional G1,
  pending native deployment, live validation, pilot, campaign and submission.
  Distinguish the student-directed integrated-Yocto target and unpublished
  2026-09-16 working reforecast from the published plan v1.2. Do not import the
  unrelated local edits, adopt the working plan, approve dates or accept claims.
- **CI correction:** The first Linux thesis build for PR #27 failed at font
  expansion while both local builds passed. The minimal Ubuntu package list
  omitted scalable T1 fonts under `--no-install-recommends`; add `cm-super`
  explicitly, retaining the manuscript and template unchanged. The package
  provides the corresponding Type 1 fonts with the original metrics
  ([upstream description](https://ctan.org/pkg/cm-super)).
- **Verification boundary:** Check README links and patch whitespace locally;
  the subsequent GitHub workflow result, not this entry, establishes whether
  the Linux build succeeds. Existing sealed build records remain unchanged.

---

## Entry #C023 — Integrated QEMU/TCG gateway profile (unbuilt proposal)

- **Date:** 2026-09-18
- **Request:** Verify whether the sealed `egw-image` is fit to host the
  digital-twin stack, and prepare a first change set limited to an integrated
  QEMU/TCG profile: the Yocto ARM64 guest emulated on the x86-64 host with the
  six containers inside the guest. No native ARM64 host could be obtained.
- **Finding:** The G1 image is a sound container host but cannot run the
  stack as sealed. Its QEMU profile is `-cpu cortex-a57 -m 256`, while MongoDB 7
  needs ARMv8.2-A and the compose memory limits alone total 2,432 MiB. It lacks
  the Compose V2 plugin, `curl`, a non-root operator with key-only SSH, a
  persistent journal, explicit NTP servers, a Docker `daemon.json`, an event
  directory writable by uid 1000 and storage for the images. Removable
  default-feature packages amount to about 24 MiB; size is not the problem.
- **Action:** Add `kas/egw-qemuarm64-integrated.yml` with its lock file,
  `egw-gateway-image.bb`, `egw-gateway-image-dev.bb`, the `egw-gateway-config`
  recipe, `scripts/build-profile.sh`, `scripts/run-qemu-integrated.sh`, the
  runbook `docs/setup/qemu_integrated_gateway.md` and the audit
  `docs/reviews/2026-09-17-egw-image-audit.md`. The profile keeps the G1
  machine, layers and pins, builds only in `build-integrated/`, selects
  `-cpu cortex-a76`, 8 GiB and four vCPUs, forwards 2222 and 8883, and keeps
  Docker data on a second ext4 disk outside the clone. The data-disk guard
  resolves the canonical path before anything is created.
- **Boundary:** Nothing was built, booted or measured. Every G1 input is
  byte-identical and the eight evidence seals on this branch verify (59
  artefacts). The environment is ARM64
  emulated on x86-64: functional and integration evidence only, never native
  performance evidence. The profile follows the student-directed
  integrated-Yocto target, whose plan revision and ADR 0008 are not yet
  published on `dev`; no plan version is adopted, no gate and no claim is
  accepted. The native-route files, the deployment corrections (broker secret
  ownership, ACL probe, prebuilt controller) and the harness reconciliation
  helper are deliberately left for later pull requests.
- **Verification record:** YAML and JSON parsing, `sh -n`/`bash -n`, a sandbox
  run of the data-disk guard, the repository link and evidence-seal checks.
  ShellCheck is not installed on the workstation, so the `shell safety` check
  is the first ShellCheck run of the two new scripts.

---

## Entry #C024 — First build and boot of the integrated QEMU/TCG profile

- **Date:** 2026-09-18
- **Request:** Validate, by a delimited build and boot in WSL2, the integrated
  profile of entry #C023 from an identified commit, preserving the G1 build
  artefacts, without deploying the stack, running a campaign or accepting a
  gate.
- **What happened:** The first build (commit `68f9ae7`) failed in
  `egw-gateway-image:do_rootfs` on an RPM conflict: `egw-gateway-config`
  created `/etc/sudoers.d` 0755 while `sudo-lib` ships it 0750. Commit
  `03e333e` creates it 0750; the build then succeeded (5,556 tasks). The first
  boot attempt ended before QEMU started: the pinned `runqemu` cannot resolve
  `IMAGE_LINK_NAME` when given an image name and a machine. Commit `3209b17`
  passes the image's own `.qemuboot.conf`; the rebuild was a no-op and two
  boots followed. Every failed attempt is preserved.
- **Result:** Every artefact check (runbook 2.4) and guest check (runbook 3.4)
  passed: Cortex-A76 model, four vCPUs, 8,204,356 kB of memory with
  `mem=8192M`, `/var/lib/docker` on the labelled data disk, Docker 25.0.9 with
  Compose v2.26.0, cgroup v2, key-only SSH for `egw` with `root` and password
  logins refused, NTP synchronised, no failed unit. The second boot showed both
  boots in the journal, the same SSH host key, data-disk UUID and Docker
  engine id.
- **Prediction refuted:** The kernel was re-executed rather than restored
  from the shared sstate cache, because meta-virtualization signs the whole
  `DISTRO_FEATURES` value into `do_kernel_metadata` and the profile removes
  `nfs`. The resulting `Image` is byte-identical to the G1 `Image`. The
  manifest comment is corrected.
- **Boundary:** The sealed G1 build tree is unchanged (listing and checksums
  compared before the first build, after the builds and after the boots). No
  image was loaded, no container was started, MongoDB 7 was not tried. The
  environment is ARM64 emulated on x86-64: functional evidence only. The
  candidate evidence is held outside the repository and is not sealed; no
  gate and no claim is accepted.
- **Record:** `docs/reviews/2026-09-17-egw-image-audit.md`, Section 13.

---

## Entry #C025 — Seal the build, boot and MongoDB evidence of the integrated QEMU/TCG profile

- **Date:** 2026-09-18
- **Request:** Archive, as sealed technical evidence, what was observed on
  2026-09-18 with the integrated QEMU/TCG profile of pull request #28, keeping
  the distinction between archiving evidence and accepting a gate or a claim.
- **Action:** Add `docs/evidence/integrated-qemu/` with two capsules copied
  byte for byte from the candidate evidence held in the WSL2 home:
  `2026-09-18-build-boot/` (failed first build at `68f9ae7`, successful build
  at `03e333e`, boot attempt that failed before QEMU started, no-op rebuild and
  two boots at `3209b17`, guest acceptance transcripts, persistence, offline
  SSH host-key record, root file system checksums before and after the boots)
  and `2026-09-18-mongodb7-isolated/` (MongoDB 7.0.39 pulled by the pinned
  digest inside the guest; start, write and read, restart, recreation and
  persistence across a guest power cycle; 35 checks, none failed). Store the
  directory without text conversion and exclude captured scripts under
  `docs/evidence/` from ShellCheck.
- **Review adjustments applied before sealing:** the manifests now cover the
  nested manifest of the failed attempt, and the SSH host-key continuity, which
  had not been saved during the run, is recorded offline from the root file
  system image and qualified as such. A scan found no private key, password or
  token; two files hold public keys of material created for this validation.
- **Boundary:** Functional evidence of an ARM64 guest **emulated** on x86-64.
  The six-container stack was not deployed and nothing was measured; timings
  in the transcripts are informational. The sealed G1 evidence and every G1
  build input are unchanged. No gate is accepted and no claim is supported.
- **Verification record:** `python tools/ci/verify_evidence.py` and
  `python tools/ci/check_markdown_links.py` on the branch.

---

## Entry #C026 — Broker secret ownership and an ACL probe with known traffic

- **Date:** 2026-09-18
- **Request:** Correct two deployment defects found by the project review of
  the integrated profile and make the ACL test prove what it claims.
- **Finding:** Mosquitto 2 loads its configuration and drops to its
  unprivileged user before it opens `password_file` and `keyfile`; in the
  official 2.0 image that user is uid/gid 1883, and the entrypoint cannot
  `chown` the read-only bind mounts of `compose.yaml`. With files owned by the
  invoking user and mode 0600 the broker cannot read its own key. Separately,
  Mosquitto's `acl_file` never refuses a SUBSCRIBE and filters at delivery, and
  a denied PUBLISH is acknowledged normally under MQTT 3.1.1, so a test without
  known traffic proves nothing.
- **Action:** Add `scripts/prepare-broker-secrets.sh` (owner 1883:1883, mode
  0600, refusal of any permission bit for others, read test as uid 1883 in a
  one-shot container with the mounts of `compose.yaml`, `--check` mode) and call
  it as step 3b of `validate-config.sh`; `generate-dev-auth.sh` hands `passwd`
  to that uid and honours `EGW_BROKER_IMAGE`; `generate-dev-tls.sh --force`
  removes the old outputs. Add `scripts/probe-acl.sh`: an authorised and an
  unauthorised subscriber listen concurrently while tagged messages are
  published by both users; the anonymous case counts only when the refusal is
  observed; a delivery is a line that starts with the topic; the unauthorised
  subscriber must be shown connected while the messages were published; an
  incomplete broker-log collection is INCONCLUSIVE unless independent proof of
  a security failure exists; preconditions exit 2 with nothing run.
- **Boundary:** Nothing was run against a Docker engine, a broker or the
  guest. `src/tests/test_probe_acl_verdict.py` exercises the verdict logic with
  a stub `docker` under dash and bash (94 cases); behaviour under BusyBox ash
  and against a real Mosquitto 2.0.22 is unobserved. No gate and no claim is
  accepted.

---

## Entry #C027 — Third review of the test procedure; isolated MongoDB 7 test recorded

- **Date:** 2026-09-18
- **Request:** The project review found four residual defects in the
  published test procedure (one reproduced by running the helper) and asked for
  a short, focused correction with positive and negative cases; it also
  recommended, and the student authorised, an isolated MongoDB 7 test on the
  integrated guest.
- **Action:** `accounted` now reconciles message identities instead of totals
  and never states that no work is pending; test 7 cannot be accepted unless
  the interruption and the recovery are both shown, and always attempts the
  recovery; failures of evidence capture are binding; tunnels are closed
  through a project-only control socket instead of a pattern kill. The cases
  are executable: `src/tests/test_runbook_itest_helpers.py` extracts the text
  from the runbook at run time (64 cases; the review's case fails against the
  published text). Report: `docs/reviews/2026-09-18-test-procedure-corrections.md`.
  The audit report records the round in Section 12.2 and the MongoDB test in
  Section 13.5; the runbook status and its Section 3.5 note that the guest can
  pull by the pinned digest.
- **Boundary:** Stubs only: nothing in runbook Sections 4-9 has run on the
  real host, guest or broker. The MongoDB test is functional evidence of an
  emulated guest (record in pull request #29); the stack was not deployed,
  nothing was measured, no gate and no claim is accepted. The entry ids #C025
  and #C026 belong to other open pull requests.

---

## Entry #C029 — Progress counters in the controller's `GET /metrics`

- **Date:** 2026-09-18
- **Identifier:** `#C023`–`#C028` are used by or reserved for other open work
  (pull requests #28, #29 and #30) and are not used here; identifiers are
  never reused. For the same reason the decision record is ADR 0010: 0008 is
  used by pull request #30 and 0009 is kept for other open work.
- **Request:** Project review of 2026-09-18, authorised by the student the
  same day: add `received`, `in_progress` and `processing_errors` to the
  controller as a delimited observability change, with explicit semantics,
  tests and restart handling. The counters show the controller's internal
  state; they do not replace the reconciliation, by identity, of messages
  sent with logged outcomes.
- **Finding that motivates it:** `queue_depth` is `Queue.qsize()` and the
  consumer removes a message before processing it, so a message in a Ditto
  retry is in no field of `/metrics`; an exception that escapes processing
  (a failed event-record write included) is logged and reaches no counter.
  One reading could not distinguish "idle" from "one message in progress".
- **Action:** Three additive integer fields. `received` is counted in
  `ControllerService.submit()` before the queue-capacity decision;
  `in_progress` is raised after the consumer takes a message and lowered in
  a `finally`; `processing_errors` is the residual, raised in the same lock
  acquisition when no outcome counter moved for that message. Every term of
  the identity is written on the event loop and the `/metrics` handler reads
  there, so one response is one snapshot. Identity, per response of a
  running controller: `received == accepted + rejected + duplicate + failed
  + dropped + processing_errors + in_progress + queue_depth`.
- **Contract rule followed:** plan v1.2 section 1 ("material changes require
  an ADR and regression tests") →
  [ADR 0010](docs/adr/0010-controller-progress-counters.md), status
  Proposed, and regression tests that keep the exact values of the existing
  fields. `src/CONTRACTS.md` section 5 gains a dated additive sub-section
  (semantics, identity, restart rules for readers, shutdown exclusion); the
  title stays v1.1, as for the P5 confirmation marker, so no version string
  or diagram moves: the rule of `diagrams/README.md` ("bump the version
  named here ... in the same change") has no version to bump, a reading the
  ADR states openly. Gate G3 ("contracts frozen") is `Pending`.
- **Coordinated update (CONTRACTS header clause):**

  | Component | Verdict | Basis |
  |---|---|---|
  | simulator | no change | does not read `/metrics` |
  | controller | changed | `metrics.py`, `service.py` (`submit`, `run`), docstrings and one comment in `app.py` |
  | schemas, TDs | no change | none describes `/metrics` |
  | deployment | no change | only `/health` and `/ready` are probed |
  | harness | no change | reads six counters and the marker by key; other integer keys are ignored; `controller_metrics.csv` keeps its columns |
  | tests | updated and added | the two tests that pin the exact key set are updated; new tests cover the identity, the single-snapshot reading, fault, cancellation and shutdown paths |

- **Not changed:** processing behaviour, outcomes, event records, retry
  policy, `queue_depth`, the MQTT bridge, the shutdown sequence, the
  simulator and the experiment harness. The defect by which a failed event
  write leaves a message with no outcome is made visible, not repaired.
- **Verification boundary:** unit tests with fakes only, outside the sealed
  suite; the sealed figure stays 701. No live broker, no Ditto, no ARM64, no
  run on the gateway. Local Markdown link check passed. The test counts of
  the verified commit are recorded in the pull request; the GitHub workflow
  result, not this entry, establishes the result on Python 3.11 and 3.14.
- **Decisions and next steps:** no gate, claim or maturity level changes.
  Follow-ups, each a separate change: record the new fields in
  `controller_metrics.csv`; use the single-reading test in the integration
  runbook (whether its quiet interval may be shortened is decided there);
  repair the event-write defect.

---

## Entry #C030 — Prebuilt controller image in the deployment; reconciliation helper versioned

- **Date:** 2026-09-18
- **Request:** Project review of 2026-09-18, authorised by the student the
  same day, before the first end-to-end functional test inside the
  integrated QEMU guest: the published Compose file still built the
  controller and `itest_reconcile.py` was outside `dev`; make the use of a
  prebuilt image explicit, version the helper, use the external images
  pinned by digest, publish no controller image, and record that the
  Dockerfile installs Python dependencies without a reproducible lock.
- **Action (deployment):** `src/deployment/compose.yaml`, service
  `controller`: the `build:` stanza is removed and `pull_policy: never` is
  added; `image: egw-controller:0.1.0` and `platform: linux/arm64` stay. No
  other service, port, limit, pin or the ACL changes. The only command shape
  on the gateway is `docker compose --env-file .env --env-file
  images.lock.env up -d` (no `--build`); `images.lock.env` remains the only
  source of the five external references, which are pulled by their pinned
  digests inside the guest. New `scripts/build-controller-image.sh`
  (provisioning host: `buildx`, `linux/arm64`, refuses a dirty build context
  — git-ignored files below a path the Dockerfile copies included, since they
  reach the image while `git status` stays silent about them —, `docker
  save`, identity record with source commit, base image, image id read from
  the archive, archive SHA-256, `python --version`, `pip freeze --all`, tool
  versions and UTC time; pushes nothing; traps `HUP`/`INT`/`TERM` so that an
  interrupted run leaves no archive without a record in any POSIX shell) and
  `scripts/verify-controller-image.sh` (gateway: compares the loaded image
  with the record — image id, architecture, OS and the revision label — and
  refuses a record from a dirty build context). `scripts/validate-config.sh`
  gains step 7 (controller image present, remedy `docker load -i <archive>`,
  never a build or a pull), and its step 1 now looks for `CHANGE_ME` in
  assignments only: the header comment of `.env.example` carries the word and
  survives `cp .env.example .env`, so the step failed on every correctly
  filled `.env` and the `up -d` interlock of runbook 5.5 could never have
  passed — a defect already on `dev`, found by the project review of this
  pull request.
  `scripts/probe-acl.sh` takes `images.lock.env` as its default second env
  file.
- **Action (harness):** `src/egw_experiments/itest_reconcile.py` (`mark`,
  `wait`, `check`, `snap`, `delta`, `same`) is versioned with
  `src/tests/test_experiments_itest_reconcile.py` (106 cases, fakes only, no
  network). It imports `CONFIRMATION_WINDOW_S`, `poll_controller_marker` and
  `compute_run_metrics` from the harness, never redefines the confirmation
  window and refuses a marker file whose deadline is not marker + window.
  `mark` measures the lag up to the **return** of the poll, as the harness
  does, so a slow round trip can no longer hide a lag above the 2 s
  tolerance; `delta` exits 4 for a device with accepted records that the
  `from` snapshot does not hold (a snapshot taken with another seed than the
  run, which used to close vacuously) and says when a `/metrics` reading is
  missing instead of passing over it; `check` adds warnings about files that
  are not shown to be this run's and whole, and about a controller clock that
  decreases along the event log, without changing a count or an exit status.
  The test module extracts every `$REC` command line from the runbook and
  parses it, so a drift between document and interface fails a case.
- **Action (runbook):**
  [`docs/setup/qemu_integrated_gateway.md`](docs/setup/qemu_integrated_gateway.md)
  Sections 3.5, 4, 4.5, 5 to 7 and Appendix B follow the implemented route:
  controller built with the script from a clean checkout, copied, streamed
  into `docker load` and compared with its identity record (4.1, 4.3, 4.4,
  repeated in front of `up -d` in 5.5); five external images pulled in the
  guest with a `RepoDigests` check (new 5.2a); `EGW_BROKER_IMAGE` no longer
  exported; every compose command names `images.lock.env`. The offline
  route (six archives, `images.offline.env`, `images.identity.env`) was
  never implemented and is removed from the text. The six points of 4.5 are
  marked done (1, 4, 6), superseded (2, 5) or both (3). Four further
  corrections came from the project review of this pull request: 4.3 brings
  the WSL clone
  to the commit named in the identity record and refuses a dirty `src/`, so
  the deployment tree (5.1), the guest-side verification script (4.4) and the
  harness (6.1) cannot come from a different commit than the image, and it
  records that commit in `deploy_source_commit.txt`, which 6.6 copies next to
  the Yocto build's own `source_commit.txt`; the pinned-digest verdict of
  5.2a and the identity verdict of 4.4 are now written to
  `/opt/egw/evidence/`, which 6.6 already fetches, and the `imagetools-*.txt`
  files of 4.2 reach the host copy; 4.1 and 4.4 state what the two scripts
  really print; and 5.7 names which `$REC` subcommand takes which URL option
  (`delta` and `same` take neither, so the earlier advice would have ended in
  a usage error).
- **Limitation — unlocked dependencies:** `src/Dockerfile` still installs
  with `pip install .`, without hashes or a lock, and its install method is
  deliberately unchanged here. The first functional demonstration therefore
  uses a controller image with **unlocked Python dependencies**; the
  identity record lists `pip freeze --all` of that one build, which
  documents it and does not make it reproducible. This must be resolved
  before the experimental freeze (`scripts/generate-runtime-lock.sh`,
  deployment README "Runtime Python lock"); such an image is not admissible
  for thesis measurements.
- **Boundary:** nothing here has run on the guest yet: no image was built,
  saved, loaded or pulled, no script of this entry has met a Docker engine,
  the stack was not deployed and no traffic was sent. Verified locally only:
  `docker compose config` accepts the file and its resolved model differs
  from the previous one only in the controller's `build`/`pull_policy`; unit
  tests with a stub `docker` and with fakes (35 cases for the deployment
  decision and the two image scripts, 106 for the helper; whole suite 1057
  passed under Linux); the rewritten runbook lines ran verbatim against
  stub `git`/`ssh`/`docker` commands under WSL (21 assertions for the
  pull-by-digest route, then 17 more for the lines changed after the project
  review of this pull request, the guest group under `dash` and `bash`) and
  `src/tests/test_runbook_itest_helpers.py` passed afterwards under Linux
  (64 cases). ShellCheck was not run locally; the GitHub workflow
  establishes that result and the test results on Python 3.11 and 3.14.
  Open, and named in runbook 4.5 as such:
  `.github/workflows/manual-arm64-integration.yml` still says `up -d
  --build` at line 34 and runs `validate-config.sh` at line 30 with no step
  that provides `egw-controller:0.1.0`, so its step 7 would now fail there —
  a known regression of a `workflow_dispatch` job whose self-hosted runner
  does not exist, left to the change that repairs that workflow; the text
  test of the deployment cases therefore still scans `src/deployment` only.
  Also open: the header comments of `src/Dockerfile` and `src/.dockerignore`
  still name the compose build context, and that comment edit belongs before
  the evidence build, because `dockerfile_sha256` of the identity record
  hashes the whole file.
- **Decisions and next steps:** no gate, claim or maturity level is
  accepted. Next, under the same authorisation: build the image from the
  merged `dev`, load it, deploy the six services in the guest and run one
  smartwatch at 1 Hz for 60 s, labelled as emulated functional evidence.
