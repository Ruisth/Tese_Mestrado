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

## Entry #C028 — Publish the integrated-Yocto plan revision v2.0 and ADR 0008 as a proposal

- **Date:** 2026-09-18
- **Phase:** Governance documentation only; no code, evidence, thesis chapter
  or search-protocol change. Entry ids #C023–#C027 are reserved for other open
  work and are not used here.
- **Request:** Publish the plan revision prepared on 2026-09-16 and ADR 0008 in
  parallel with the functional tests, distinguishing proposed decisions from
  decisions approved by the supervisors (none exists at this date), and state
  what will be demonstrated
  under QEMU, what still depends on native ARM64, which performance conclusions
  are permitted and which scope change needs supervisor agreement.
- **Action:** Bring the 2026-09-16 amendment into a documentation branch:
  plan v2.0 at the canonical path with a status box, plan v1.2 archived
  byte-for-byte (SHA-256
  `c346e4d958d22fad6d4f4635b4176bc2c1b584407199b165a197f94ef0e9fa53`),
  ADR 0008, scope/RQs v2.0, the revised alignment memo, decisions D011–D013
  and pointer banners in the ADRs, G0 documents, diagrams, setup guide,
  experiments and documentation indexes. Add plan section 10 and the ADR 0008
  amendment of 2026-09-18 (evidence classes: emulated QEMU/TCG versus native
  ARM64), decision D014 (re-scoping RQ3 or the evaluation to emulated
  functional evidence if no native ARM64 host is obtained in time) and a
  PROGRESS.md section for the proposal.
- **Status of the documents:** ADR 0008 is *Proposed — pending supervisor
  agreement (accepted by the student for technical planning only)*. Plan v2.0
  is a proposal published for review. Plan v1.2 remains the plan in force
  until the student decides after consulting the supervisors. D001–D014 are
  all `proposed_not_sent`; the alignment email and memo have not been sent;
  nothing is approved by the supervisors.
- **Facts recorded (from the 2026-09-16 amendment):** the final services must
  execute on the student's Yocto-built kernel/root filesystem during the ARM64
  campaign, and the August separate-platform academic proposal has no recorded
  supervisor approval. The revision rests on
  the source documents, configuration, recipes and manifests, a read-only
  inspection of the existing WSL kernel build and official custom-image
  references; no cloud resource, new Yocto build, integration run or campaign
  was executed for it. Estimate 225-345 active hours remaining at a reported
  8 h/day including weekends; student target
  2026-10-20 and student-reported extension date 2026-11-03, neither confirmed
  administratively.
- **Facts recorded (2026-09-17/18):** on 2026-09-17 no native ARM64 virtual
  machine had been obtained (attempts with cloud providers had not produced one), so the project review
  ordered an integrated QEMU/TCG profile first, with the native ARM64 route as
  the subsequent step. On 2026-09-18, in draft pull request #28 (not on
  `dev`), the integrated image was built (commit `03e333e`) and booted twice
  under QEMU/TCG (commit `3209b17`) with every build and boot acceptance check
  passing. The same day an isolated MongoDB 7.0.39 test passed on that guest;
  it is recorded in the separate draft pull request #29, branch `evidence/integrated-qemu-2026-09-18`
  (commit `f03c92c`, not on `dev`), which proposes to seal the build, boot and
  MongoDB records, and not in pull request #28. The six-container stack has
  not been deployed, nothing has been measured, and the evidence is candidate
  evidence, none of it sealed on `dev`; sealing would not be acceptance.
- **Evidence boundary:** ARM64 emulated on x86-64 yields functional and
  integration evidence only, never native ARM64 performance evidence; academic
  use of emulated results needs supervisor agreement. No gate, claim or
  supervisor decision is accepted by this entry, and no historical seal is
  changed.
- **Left out:** the integrated QEMU profile, its runbook and image audit
  (pull request #28), deployment and harness corrections, a further ADR in
  preparation,
  literature-search files, thesis chapters and review notes. The target dates
  of plan v2.0 section 6 were not reforecast.
- **Verification boundary:** the Markdown link checker and the evidence-seal
  checker were run locally on the branch; the GitHub workflow result, not this
  entry, establishes whether the required checks pass.
- **Forward pointer (added 2026-09-18):** superseded in part by #C031, which
  records the layout under `docs/governance/proposals/`, the dates confirmed
  by the student and the merge of pull requests #28 and #29. The text above is
  kept as written.

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
---

## Entry #C031 — Move the plan v2.0 proposal under `docs/governance/proposals/`; dates confirmed by the student

- **Date:** 2026-09-18
- **Phase:** Governance documentation only; no code, evidence, thesis chapter
  or search-protocol change. Identifier `#C030` is reserved for another open
  pull request and is not used here; entry #C028 is kept as written, with a
  dated forward pointer to this entry added at its end.
- **Request:** Two decisions of the project review of 2026-09-18, forwarded by
  the student. (1) Keep plan v1.2 at the canonical path and place v2.0 under
  `docs/governance/proposals/`, with references that distinguish the plan in
  force from the proposal. (2) Align the proposal with the planned submission
  and the final deadline confirmed by the student, and reforecast the work
  backwards from the submission without reporting forecasts as completed
  milestones.
- **Layout:** `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md` (plan
  v1.2, SHA-256
  `c346e4d958d22fad6d4f4635b4176bc2c1b584407199b165a197f94ef0e9fa53`),
  `docs/g0/scope_and_rqs.md` (August scope v1.1) and
  `docs/governance/supervisor_alignment_memo.md` (August memo) are again
  byte-identical to `dev`. The proposal texts that #C028 had placed at those
  paths are now
  `docs/governance/proposals/INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md`,
  `scope_and_rqs_v2.0_proposal.md` and
  `supervisor_alignment_memo_v2.0_proposal.md`, with their internal links
  corrected, and the directory has a README that says what is in force and
  how a proposal is adopted. The copy
  `docs/governance/archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2_en.md` added
  by #C028 is withdrawn, because the plan in force is at its canonical path
  again; the archive content that was already on `dev` is untouched. ADR 0008
  stays in `docs/adr/` with the status Proposed. Banners, index rows, the
  README files, ADR 0008 and `PROGRESS.md` point to the proposal path and say
  "proposal" when they mean plan v2.0, and to the canonical path when they
  mean the plan in force. The files on `dev` that call the canonical path the
  normative plan are correct again without being edited.
- **Dates decision and its source:** planned submission **2026-10-20** and
  final delivery deadline **2026-10-31**; the days from 2026-10-21 to
  2026-10-31 are a contingency window for essential corrections, submission
  difficulties and administrative recovery only, not the default delivery
  period and not time for optional scope. Source: the student's confirmation
  of 2026-09-18 after discussing the dates with the supervisors. It is a
  first-party statement; no institutional portal or administrative document
  was checked, and no supervisor reply is recorded by this entry. For current
  planning the pair supersedes the date 2026-11-03 quoted in #C028 and the
  2026-09-29 internal cut-off and 2026-09-30 baseline of plan v1.2; all three
  stay in the historical records, and plan v1.2 is not edited.
- **Forecast:** sections 6 and 7 of the proposal were rewritten on 2026-09-18
  as a forecast worked backwards from the submission: a milestone table with a
  status per milestone (demonstrated, in preparation, pending), the critical
  path, a native ARM64 decision point forecast for 2026-09-25, reforecast
  triggers and the cutting order. Capacity from 2026-09-19 to 2026-10-20 at
  the reported 8 h/day is 256 h against the unrevised estimate of 225-345
  active hours, so the submission date is feasible only near the lower
  estimate; the binding constraint is the 152 h before the full draft, which
  the estimate cannot yet be checked against. Branch C is prepared at risk
  until D014 is answered, and the native branch has no writing days left with
  a host obtained on the decision date. Decision D013 carries the
  review-window dates of the forecast and the dates note, and D014 the
  decision point and the requested reply date; every status, D001–D014, stays
  `proposed_not_sent`.
- **Facts recorded:** pull requests #28, #29, #32 and #31 were merged into
  `dev` on 2026-09-18; merging validates no stack and accepts no gate.
  Demonstrated so far, all emulated (ARM64 under QEMU/TCG on x86-64,
  functional evidence only): the image build, two boots with every acceptance
  check passing and the isolated MongoDB 7.0.39 test. Not demonstrated: the
  six-container stack on the guest, the functional path simulator -> MQTT/TLS
  -> controller -> Ditto -> API, any integration test on the real stack, any
  measurement. The first bounded end-to-end functional test (one smartwatch,
  1 Hz, 60 s) was authorised on 2026-09-18 and is in preparation; it has not
  run. No native ARM64 host has been obtained.
- **Known stale notes, left for a separate change:**
  `docs/setup/qemu_integrated_gateway.md`,
  `docs/reviews/2026-09-17-egw-image-audit.md`,
  `src/yocto/kas/egw-qemuarm64-integrated.yml` and the `egw-gateway-image`
  recipe, all on `dev` before this entry, say that the v2.0 revision is not
  yet published on `dev` and cite "plan v2.0" without a path. After this
  change the revision is on `dev` as a proposal only; the README of
  `docs/governance/proposals/` says how to read those citations. The build
  inputs are not touched by a documentation change.
- **Not changed and not implied:** no gate is accepted; no RQ or scope
  changes; no emulated performance claim is approved; nothing has been sent to
  or approved by the supervisors; plan v1.2 remains the plan in force and
  merging the pull request adopts nothing. Adoption of the proposal is a
  separate decision of the student after consulting the supervisors, to be
  recorded in this log. No historical entry, seal or run metadata is changed.
- **Verification boundary:** the three restored files were compared with
  `origin/dev` and show no difference; the Markdown link checker and the
  evidence-seal checker were run locally; the GitHub workflow result, not this
  entry, establishes whether the required checks pass.

---

## Entry #C032 — Publish the student's adoption of plan v2.0 with the QEMU-only execution amendment

- **Date:** 2026-09-18
- **Request:** The student adopted plan v2.0 with a dated QEMU-only execution
  amendment as the execution baseline on 2026-09-18, after discussing with the
  project review whether the Yocto image built for QEMU could later be reused
  on a native ARM64 virtual machine, and instructed that the adoption be
  published at the canonical plan path through one focused documentation pull
  request against `dev`.
- **Decision recorded:** the active baseline is **plan v2.0 with the QEMU-only
  execution amendment**, not the unmodified proposal. The system under test is
  the Yocto-produced ARM64 kernel and root filesystem booted under QEMU/TCG on
  the existing x86-64 workstation, hosting the six-service digital-twin stack,
  with the simulator and harness outside the guest. Native ARM64 deployment and
  native measurement leave mandatory scope and become documented, unverified
  future work: no cloud allocation, spending or native build is requested, the
  native-host decision deadlines and procurement dependencies are withdrawn
  from the critical path, and the native boot milestone leaves the gate set.
  RQ3 is bounded to the specified emulated environment. The native 95-run
  campaign and the 24-hour soak are **not** transferred to emulation; the
  emulated functional campaign is selected after the bounded pilot and frozen
  before execution. The submission target is 2026-10-20, the final delivery
  deadline 2026-10-31, and 2026-10-21 to 2026-10-31 is a contingency window for
  essential corrections only.
- **Boundary — what the adoption is not.** It is a **student decision about
  execution**. The supervisors approved nothing: not the title, not the
  research-question wording, not the thresholds and not the revised academic
  evaluation. Nothing has been sent to them and D001–D014 remain
  `proposed_not_sent`. The student reported that a supervisor advised
  proceeding with QEMU tests; that is **student-reported advice**, never
  approval and never a documented supervisor decision, and it is not written
  into the supervisor decision log. **Adoption closes no gate and admits no
  claim**, and it turns no emulated result into native ARM64 evidence. Every
  date after 2026-09-18 recorded in this change is a planning target. A green
  documentation pull request confirms consistency checks, not successful
  integration, supervisor approval or gate acceptance.
- **Action (records owned by this entry):** `PROGRESS.md` takes a dated
  adoption note, an "Adopted scope and forecast" section, a gate-status block
  for 2026-09-18 with G1 unchanged and G0 and G2–G7 Not decided, a row for the
  first-flow candidate evidence, the two evidence classes in place of the
  three-tier platform table, and a reforecast effort table whose `actual_h`,
  `remaining_h` and `forecast` columns stay empty (risk RA15). `README.md` and
  `docs/README.md` name the adopted plan and its facts. `docs/g0/scope_and_rqs.md`
  becomes version 2.0 with the integrated objective and the QEMU-bounded
  RQ1–RQ3, marked **working wording for academic review, not agreed with the
  supervisors**. `docs/g0/backlog.md` gains the QEMU execution path and keeps
  the August gate sections as history with their native prerequisites marked
  deferred. `docs/g0/risks.md` downgrades the native-host risk from blocking
  dependency to a bound on RQ3, records the residual risks of the adopted
  baseline against existing identifiers, and retargets the runtime-lock and
  contention risks. Both forms of the claim→evidence matrix take the evidence
  classes, the emulated environment and the deferral of the 24-hour soak, and
  were compared field by field afterwards. `diagrams/architecture.md` replaces
  the three-tier deployment figure with the integrated emulated topology, and
  `diagrams/README.md` marks the two-layer PlantUML view historical.
  `docs/academic/c2dta_p0_traceability.md` retargets its platform rows and its
  comparison rules.
- **Action (first end-to-end flow of 2026-09-18, recorded here because the
  corrected records depend on it):** inside the Yocto guest under QEMU/TCG the
  six-container stack was deployed and one bounded end-to-end functional test
  passed — one smartwatch at 1 Hz for 60 s; **60 sent, 60 delivered unique,
  0 lost, 0 late, 0 duplicate, 0 failed, 0 rejected**; twin
  `org.c2dta:5689c879-…` with `last_seq` 59; reconciliation by identity exited
  0. Maximum latency **12,286 ms**, recorded as an **emulated, informational**
  observation and never as a performance result. The run exposed two defects,
  both fixed on `dev`: the controller was attached to the wrong Compose network
  (`9ffd365`) and the host shell inherited a relative schema directory
  (`dc6d8bb`, `22fb0a9`). A memory-cgroup OOM killed the `ditto-things` JVM
  **during the power-off** of that session, at the 512 MiB container limit; the
  diagnosis of the same day found the three Ditto services idle at 94–95 % of
  that limit and at 98.1 % after a 672-message workload, and a controlled
  `docker compose stop -t 60` after that workload produced no OOM anywhere in
  the boot. The corrective work — a graceful stop before power-off and
  container memory sizing — is a **separate change and remains open**; no
  stability is claimed.
- **Evidence boundary:** the record of that flow is **candidate evidence held
  outside the repository and unsealed**. The only sealed capsules for the
  integrated profile remain the build, boot and isolated MongoDB records of
  2026-09-18 under `docs/evidence/integrated-qemu/`, and sealing is not
  acceptance. Nothing native has been built or booted. **None of the nine
  integration/recovery test families has been run** and nothing has been
  measured.
- **Identifier note:** `#C031` was written on the branch of the earlier
  governance pull request (`3673910`) and did not survive the merge
  `f09b0e6`, so it is absent from `LOG.md` on `dev` although `PROGRESS.md` and
  the D013 note of the supervisor decision log refer to it; the D014 note's
  citation of it is removed by this change. Identifiers
  are never reused, so the number stays unused here and the content it carried
  — the move of the proposal texts under `docs/governance/proposals/`, the
  return of plan v1.2 to its canonical path and the dates confirmed by the
  student on 2026-09-18 — is carried by this entry and by the dated update note
  in `PROGRESS.md`.
- **Decisions and next steps:** no gate, claim or maturity level is accepted,
  and no supervisor decision changes state. Next: seal the first-flow record
  inside the repository; resolve the teardown OOM and the container memory
  sizing as a separate change; run the nine integration/recovery test families
  in the guest; send the alignment package so that D004, D007, D011, D013 and
  D014 can be answered.
---

## Entry #C033 — Publish the supervisor confirmations reported by the student, the quantity supersession and the authorised terminology

- **Date:** 2026-09-19
- **Request:** The student reported a set of supervisor confirmations, recorded
  in the project-management record of 2026-09-18, and instructed that they be
  published in the canonical repository documents on the branch that already
  carries the adoption of plan v2.0. The records written before them state, as
  a blanket fact, that nothing had been sent to the supervisors and that nothing
  was approved. Those statements are no longer true and had to be replaced.
- **What is reported, and how it is recorded.** Twelve items, plus the sending
  of the state-of-the-art material and approval to proceed with the QEMU tests.
  (1) the title, exact wording *Blockchain-powered Personal AI – Digital Twin
  Edge Gateway*; (2) the research questions, with RQ3 evaluated in QEMU rather
  than on a native ARM64 virtual machine; (3) the local-core scope; (4) the
  literature-review method, settled in a follow-up as a **scoping review**;
  (5) an instruction to attempt the historical 95-run quantity, the 24-hour soak
  included, under QEMU; (6) that a second operator is not required; (7) the
  review schedule — Chapters 1–4 on 2026-10-01, the full draft on 2026-10-08,
  feedback between 2026-10-09 and 2026-10-14; (8) that the institution-supplied
  LaTeX template is mandatory; (9) that an AI-use declaration is mandatory by
  final submission; (10) that a scientific article is optional and not required
  for delivery; (11) the authorised wearable-data terminology; (12) that a local
  copy of the work is expected as evidence. **Every one of these is a supervisor
  confirmation reported by the student.** No date, no message, no supervisor
  name and no evidence file was reported for any of them, so none is invented:
  `sent_at` and `response_at` stay empty in every row of the decision log, and
  nothing is written anywhere as a documented supervisor decision.
- **What stays open, and stays unsent.** The experimental thresholds (D007); the
  scope of the evaluation and any academic use of emulated results, with the
  wording of the limitation that records the absence of native evidence (D014);
  the authenticity of the local `Template_LaTeX` copy against the current
  official 2026 source, with its cover and metadata (the open half of D004); and
  the operational storage semantics (the open half of D010). The alignment
  package is narrowed to exactly those and is still a draft. D001, D007, D008
  and D012 remain `proposed_not_sent`.
- **Boundary — what this entry is not.** **No gate is closed and no claim is
  admitted.** Approving the QEMU route is not approving the academic use of its
  results; approving the research questions settles neither the evaluation
  protocol nor the thresholds; a waived second operator does not license the word
  *reproducible* and says nothing about literature screening; choosing the review
  label executes no review; and an instruction to attempt a run quantity approves
  no threshold. Every reported confirmation stays a report. It never becomes a
  documented decision by being cited, and no gate row may use one as its decision
  record.
- **Action — decision registers.** `docs/governance/supervisor_decision_log.csv`
  keeps its nine columns and gains two status values,
  `confirmed_reported_by_student` and
  `partly_confirmed_reported_by_student`, defined in the authority table of plan
  section 1 and in `docs/README.md`. Row by row: D001 and D008 keep their
  historical August wording, which was never sent and is not what the student
  reports confirmed; D002 and D009 are confirmed; D003, D004, D005, D006, D010,
  D011, D013 and D014 are split into their confirmed and their unresolved parts;
  D007 stays unsent with a note recording that the quantity instruction settles
  no threshold; D012 stays unsent and deferred. `docs/g0/supervisor_decision_matrix.csv`
  keeps its five columns and its stateless convention, and takes dated
  supersession notes in the recommended-position and blocking-effect cells.
- **Action — the 95-run composition.** Plan section 3.3.1 records the
  composition with its per-condition table as the **target to attempt** under
  QEMU: 5 QEMU boots, 10 stack cold starts, 10 twin creations, 10 smoke
  sequences, 10 nominal, a 40-run load sweep at 10, 50, 100 and 250 messages/s,
  3 invalid payload, 3 dropout/reconnect, 3 controller restart and 1 soak of 24
  actual elapsed hours — 25 operator-driven and 70 simulator-driven. It is kept
  separate from the frozen protocol, which is still chosen prospectively at G4,
  and from the actual valid run count, and it is subject to the bounded pilot's
  feasibility check. **This supersedes the earlier "not transferred to QEMU"
  wording**, which is marked where it stands in the plan, the scope document, the
  backlog, the gate log, `PROGRESS.md`, `README.md` and both forms of the claim
  matrix rather than deleted. C13 returns from `Deferred — outside the adopted
  scope` to `Pending — no evidence`, so 13 claims are now pending and 0 of 15 are
  accepted.
- **Action — final delivery.** Plan section 4.3 names the institutional LaTeX
  template, the AI-use declaration and the local evidence archive as G7 criteria
  in their own right, all prospective. The second-operator requirement and the
  scientific article leave mandatory acceptance; the article is **deferred, not
  deleted**. The verified off-machine copy stays a separate resilience control
  and is still outstanding. C01 drops its D006 dependency and waits only on its
  formal claim admission, while the repeatability wording stays *versioned* and
  *repeatable build by the author*.
- **Action — terminology.** The authorised policy is written down once, in
  `docs/governance/language-policy.md`, and pointed at from plan section 3.6, from
  D009 and from `docs/README.md`. Active explanatory prose and diagram labels use
  *wearable data*, *wearable event data*, *sensor measurements* or *device
  events*; the literal `/telemetry` topic, API and schema identifiers,
  `src/CONTRACTS.md`, bibliography titles, quotations, sealed evidence and
  historical records keep their exact wording. **No blind global replacement was
  run**: the wording was applied only to the active prose edited in this change.
- **Action — review method.** D003 records the scoping review as reported
  settled, with execution unresolved, and plan sections 4.1 and 6 carry its three
  working targets — protocol by 2026-09-21, search and selection by 2026-09-26,
  synthesis by 2026-09-30, feeding the chapters sent on 2026-10-01 — to be
  re-estimated against the real corpus at the 2026-09-21 checkpoint.
- **Action — the scoping-review protocol.**
  `thesis/research/literature_review_protocol.md` is revised in place to
  **version 2.0, dated 2026-09-19**. It designates the review a scoping review
  and supersedes the combined "structured scoping/narrative" label by a dated
  note rather than by deletion; it adds the review question with its
  Population/Concept/Context framing and the recorded engineering adaptation,
  names JBI as the structuring guidance and PRISMA-ScR as the reporting
  framework, records the information sources and their access limits, separates
  the three preliminary rows `Q001`–`Q003` of `search_log.csv` from a formal
  execution that has not happened, keeps the A–J axis identifiers, describes the
  single-reviewer screening without claiming dual screening, and adds the
  charting fields, the five required outputs, the completion criterion, the
  limitations and departures, and the working schedule. **The revision executed
  no search, screened no record and charted no study**; it is not registered and
  not preregistered; `search_log.csv` and `study_selection.csv` are untouched.
  The lapsed targets of Section 13 — at least 30 verified sources by G6, and the
  August search window — are marked superseded where they stand, and no paper
  quota is reinstated. The prose of axis H takes the authorised wearable-data
  wording while the axis letter and every logged query string keep their exact
  form. Section 18 records that Section 2.1 of the drafted manuscript still
  carries the pre-revision description; its source is in the LaTeX tree, it is
  not edited here, and the correction is tracked as a backlog row due before
  2026-10-01.
- **Correction carried in the same change.** Entry `#C031` was restored to this
  diary on 2026-09-18, so the citations of it in `PROGRESS.md` and in the D013
  note of the decision log are no longer dangling; both were corrected here. The
  identifier note in `#C032` is left as written, because a dated diary entry is
  not rewritten.
- **Historical records left as written.** `LOG.md` entries `#C031` and `#C032`,
  the dated `PROGRESS.md` snapshot of 2026-08-14 — which takes a forward pointer
  only — the August proposals and memos, which take dated banners without their
  bodies being rewritten, and everything under `docs/evidence/`.
- **Correction — the nine integration/recovery test families.** The records
  written before this entry said, as a blanket fact, that none of the nine
  families had been run. Later on 2026-09-18 they were exercised once: **seven
  passed, and tests 1 and 6 have a failing harness part**, because the resource
  sampler under test cannot reach the harness's minimum sample count under
  emulation; that instrumentation defect is a separate change. The record is
  held outside the repository and unsealed, so the battery is **not complete**,
  nothing has been measured and G3 stays `Not decided`. The corrected wording
  replaces the blanket statement in `README.md`, `PROGRESS.md`, `docs/README.md`,
  `docs/g0/backlog.md`, `docs/governance/gate_decision_log.md`, section 2 (Baseline at
  2026-09-18) of the adopted plan and `docs/academic/c2dta_p0_traceability.md`; in
  `docs/adr/0008-integrated-yocto-arm64-evaluation.md`,
  `docs/setup/qemu_integrated_gateway.md` and
  `docs/governance/proposals/supervisor_alignment_memo_v2.0_proposal.md` — in the
  memo, both the statement of fact in item 6 and the sentence that called the
  reported QEMU approval student-reported advice — the statements were written in
  this change, so they are corrected in place and a dated note of 2026-09-19 records
  the correction. In the ADR, two sentences that did stand on `dev` — that the
  six-container stack had not been deployed, and that the first bounded
  functional test had not run — were overtaken by the events of 2026-09-18 and
  are not carried forward; both facts are restated correctly in the same
  paragraph, which keeps verbatim that sealing is not acceptance and that no
  gate and no claim is accepted. Elsewhere the dated
  sentences are kept where
  they stand and superseded by a dated note.
- **Also unchanged and still true.** The August G0 email draft at
  `docs/g0/supervisor_email_g0.md` is genuinely unsent. The
  first-flow record of 2026-09-18 remains candidate evidence held outside the
  repository and unsealed, and the `ditto-things` teardown incident remains open.
- **Decisions and next steps:** no gate, claim or maturity level changes, and no
  documented supervisor decision is created. Next: send the reduced alignment
  package covering D007, D014 and the unresolved halves of D004 and D010;
  **execute** the protocol published here — the formal searches, the screening,
  the charting and the synthesis — and correct the manuscript's Section 2.1;
  seal the first-flow record; resolve the teardown OOM and the container memory
  sizing; fix the resource sampler and **complete** the nine
  integration/recovery test families; and check the 95-run attempt target against
  the pilot's feasibility finding before any campaign window is treated as
  credible.

---

## Entry #C034 — SUT resource collector: cgroup v2 source, one stamp per wall-clock second, complete diagnostics and lifecycle record

- **Date:** 2026-09-19
- **Identifier:** the next after `#C033`. Entry `#C035` belongs to the focused
  governance and acceptance update prepared in parallel on branch
  `docs/acceptance-governance-2026-09-19` (pull request #36); neither entry
  depends on the other.
- **Request:** the PM review of 2026-09-19 (held outside this repository, in the
  project-management workspace), section 4.2 and step 2 of its work order: one
  focused collector change carrying the two source fixes it names, complete
  diagnostics, the service inventory and provenance, documentation that matches
  what actually ran, and tests at the production ingest limits.
- **Finding that motivates it.** `src/deployment/scripts/collect-resources.sh`
  sampled `docker stats --no-stream` once per sample. On the emulated guest one
  call cost 3-5 s idle and about 21 s under load (2026-09-18) and 3-4 s idle
  (2026-09-19), so a timed run could not reach the harness's 30 distinct
  instants. Two cgroup v2 rewrites then ran on the guest and each showed a
  different pacing defect, with timestamps of whole-second resolution: an
  uncommitted intermediate version (`f17bdd8c…`) slept a whole interval after
  each sample, giving 0.84 distinct instants per second over 600 s with a second
  skipped about every five; commit `aa7440d` (`b7aeddba…`) paced on whole seconds
  of `/proc/uptime`, and 30 samples in 29 s gave 26 distinct instants because
  samples shared a second. All of it is candidate evidence held outside the
  repository, in the WSL2 home of the student's workstation, and unsealed.
- **Action — source and arithmetic.** The collector reads cgroup v2 accounting
  directly: `cpu_pct` on docker's single-CPU basis (guest-accounted CPU time, not
  host QEMU CPU); `mem_bytes` as docker's cgroup v2 "used" (`memory.current`
  minus `inactive_file` when that is smaller, otherwise `memory.current`);
  `mem_pct` over `memory.max`. **Only an explicit `max` means unlimited**; an
  unreadable or empty `memory.max` now writes no row and a diagnostic instead of
  dividing by the guest's `MemTotal` (the first fix the PM review names). Any
  unreadable input writes no row: a hole is evidence of a failed sample, a zero
  would be a claim. The `/proc/uptime` reading is stored exactly as read:
  written back as an awk number it was rounded to 0.1 s after 2.8 h of uptime,
  to 1 s after 27.8 h, and turned into exponent form after 11.6 days.
- **Action — cadence and timestamps.** Built for what the gateway's busybox
  1.36.1 offers. It has no `$EPOCHREALTIME` (`CONFIG_ASH_RANDOM_SUPPORT` is off —
  a first draft of this change relied on it and a review caught that by running
  the image's own busybox) but it has a builtin fractional `sleep`. The
  timestamp is the second awk reads with `systime()`, checked against
  `date +%s` at startup and formatted in UTC by arithmetic, with no `strftime`
  and no time zone. Samples are paced on `/proc/uptime` with the fractional
  sleep, aimed 0.5 s into a second, with the offset between the two clocks
  calibrated after the first sample and again when a sample lands in the wrong
  second — at most once every 10 s, and never turned off: a first version of
  this redesign stopped calibrating after 20 attempts and fell back to
  whole-second pacing for good, which a long run under the image's busybox
  reached in about 11 minutes, because the WSL2 wall clock is stepped about
  0.5 s every 33 s. The last stamped second is kept in the state file: a sample in
  that second or an earlier one (a clock stepped back) is withheld with a
  diagnostic, and forward UTC gaps are counted, in every pacing mode. Withheld
  samples are counted separately, with the elapsed time they cost (the PM's
  second review, below).
- **Action — diagnostics, inventory and provenance.** Every diagnostic goes to
  `<csv>.diagnostics.log`, timestamped, appended and never deleted (the second
  fix the PM review names). That includes a sampler process that dies, which
  previously left a hole with no record. The start line records the collector's
  own sha256 and the host, so a run is bound to its exact instrument. The stop
  line records both counts.
  `<csv>.lifecycle.csv` records each container cgroup appearing, disappearing,
  resetting its CPU counter and first resolving to a name — the id-to-service
  mapping and the record of a restart. A container whose first reads fail
  appears once, not once per failed read. `--expect-services` names the services
  a run must observe; the stop writes one `inventory:` line (every name observed,
  the expected names, the missing ones and the ids never named), with or
  without a declaration.
- **Action — kept from the review of the first rewrite.** Substituted inputs,
  including the self-test clock `--stamp-epoch`, are refused without
  `--self-test`, and a self-test run is marked as such. The source is
  re-evaluated on every sample. An unresolved name is never cached. The output is
  locked against a second collector. The state file is replaced whole and
  validated before use. The Docker CLI is now called only for a container whose
  own `config.v2.json` cannot be read; before, it ran on the first sample of every
  run.
- **Action — documentation.** The script header and section 2 of
  `src/deployment/README.md` state the harness's real timing — the collector is
  stopped **before** the 60 s confirmation window, not after it as the earlier
  text said — and that the 30-instant rule is counted over the whole file. The
  README records, by exact version, what ran where. `tools/test/make-busybox-wrappers.sh`
  builds the wrappers that run the tests under the image's own busybox.
- **Action — the pull request's review.** Three findings, all taken. A sample
  withheld because the clock stepped back now asks for a recalibration too, as a
  sample in the wrong second already did. The seconds such a step re-enters
  stay without rows either way, because they were stamped already and the
  timestamps never go back. The `docker stats` source now follows the same
  stamp rules: the second its call starts in, withheld if not after the last
  one stamped, every forward UTC gap counted, a recalibration when it misses
  its second. The pass that records
  the disappearance of every container stamps no second, so it cannot
  withhold a docker sample in the same second, and it runs once. The service
  inventory reads the CSV as well as the lifecycle file, so names that only
  the docker source reports count as observed.
- **Action — the PM's second review (2026-09-19).** Two bounded findings,
  both taken. First, the seconds count measured forward UTC gaps only: after a
  wall clock stepped back and recovered, the stamps resumed at the next second,
  so the count added zero although elapsed time had passed without rows, and
  the text above said such a gap was counted. The count is now named
  `utc_gap_seconds` and defined as forward UTC gaps; withheld samples are
  counted separately (`withheld_samples`), each with its `/proc/uptime`
  reading, and every run of them reports the elapsed time from the last
  accepted sample to the one that ends it, less one interval and less any
  UTC-gap seconds that sample adds (`withheld_elapsed_s`), so the two counts
  never hold the same seconds. A run whose elapsed time cannot be measured,
  and a run still open when the collector stops, are counted apart. Neither
  count is a measured coverage: a forward clock step inflates the first, and
  a stamped sample that writes no row for a container is in neither. A
  withheld sample now updates the state's counters and keeps every container
  reading. Second, after a successful `docker ps` listing every discovered id
  was marked as named, so an id that a partial listing omitted was never asked
  for again; now the ids marked are exactly those the listing kept names, so
  an id it omits is asked for again even if an earlier listing named it (a
  restarted container is resolved from the listing kept). Regressions: a
  clock stepped back and then recovered; a withheld run that ends with a
  forward UTC gap, in two forms; and three partial listings with a restart
  between the second and the third, which fails on the old code and on a
  first draft of this fix. One focused review with a verification of each of
  its findings found both of those later defects in the draft, and the wrong
  wording of three messages and comments; all were corrected.
- **Branch history.** The branch first merged `dev` at `40aae52`. Its own draft
  edits to the governance records, which described the review findings as
  unrepaired and the guest as never exercised, were dropped in favour of `dev`'s
  text. The governance records are updated by entry `#C035`'s change.
- **Verified, and where.** `src/tests/test_collect_resources.py`: 234 cases on
  WSL2 Ubuntu 24.04 (Python 3.12.3, pytest 9.1.1), against a synthetic cgroup
  tree, under sh, dash, bash **and the gateway image's own busybox 1.36.1** (its
  `sh` and `awk`, sha256 `ebb5f78d…`, under the build's `qemu-aarch64` user
  emulator; eight cases stay host-shell only, because they put a fake `awk` or
  `docker` ahead of the real one or run two collectors side by side). They
  cover:
  - the exact arithmetic, including the long-uptime precision at 12,345.67,
    123,456.30 and 1,234,567.89 s;
  - an empty and a missing `memory.max`, and `inactive_file` above the usage;
  - a withheld second, a clock stepped back, a clock stepped back and then
    recovered, and both counts, from the cgroup source and from a fake
    `docker stats`;
  - a dying sampler process; two failures within one continuous run; an awk
    without `systime()` stamped by `date`;
  - the lifecycle of a restart and of a container whose first reads fail; the
    single pass that records every container's disappearance; the inventory,
    including docker-sourced names; a partial `docker ps` listing; the recorded
    collector hash;
  - UTC formatting against the calendar, including leap days and the 2100
    boundary, under a non-UTC time zone;
  - real-time pacing that never stamps a second twice and records every
    forward UTC gap, under every shell including that busybox;
  - a 33-sample run that passes `validate_resources_csv` with its production
    thresholds and a measured window, under dash and under that busybox.
  A long run under that busybox (six synthetic containers with moving counters,
  real clocks, 720 samples requested) kept the wall-clock pacing to the end on
  `bac41d4` and on `5d3ff8c`: 19 recalibrations, one for each 0.5 s step of the
  WSL2 wall clock, 18 forward UTC-gap seconds, no sample withheld, 58-60
  distinct instants in every full minute, and `validate_resources_csv` passed
  with the collector's start and stop as the window. It is a user-space
  compatibility run on synthetic cgroup files, not a soak and not 720
  consecutive one-second observations. For the head of this change, the test
  output (with JUnit XML), the long run's files and command, the collector's
  sha256 and the busybox and wrapper identities are kept in a local evidence
  capsule on the build host, `/home/ruisth/yocto/evidence-candidates/2026-09-19-collector-pr37/`, outside the
  published evidence and not admitted; the pull request description gives its
  figures.
  ShellCheck is not installed on this host; its error-level gate runs in CI.
- **What is NOT shown.** This version has **not run on the emulated guest**. Under
  the busybox emulation the shell and awk are the guest's, but the kernel,
  `/proc` and the cgroup trees are the build host's. The harness parts of
  integration tests 1 and 6 have not been re-run, and acceptance remains paused
  at the student's request. No official campaign has been completed or
  admitted, no run is admitted, no gate is closed and no claim is supported. The harness's start hook does not
  yet pass `--expect-services`, and its fetch hook collects the CSV alone. Those
  two points, the short-run margin and the treatment of a deliberate restart
  belong to the acceptance update (entry `#C035`, pull request #36), not to this
  script.
- **Decisions and next steps:** none taken here. After the student's instruction
  to resume and the relevant protocol decisions, the first guest run of this
  version is the acceptance pair the PM review sets out: resource ingestion and
  end-to-end deadline accounting and recovery evidence, on a nominal entry.

---

## Entry #C035 — Governance and acceptance update: G0 accepted, the integration battery restated test by test, the acceptance proposals

- **Date:** 2026-09-19
- **Identifier:** `#C034` belongs to the resource-sampler pull request prepared
  in parallel on branch `fix/resource-sampler-cgroup` and is not used here.
  Identifiers are never reused; when that pull request merges, its entry sits
  before this one.
- **Request:** The project review of 2026-09-19 (sections 2, 4.3, 4.4 and 5,
  and step 3 of section 7) asked for one bounded governance and acceptance
  update: correct the account of the integration battery of 2026-09-18, which
  the repository gave in 19 places across 12 files as "seven passed, and tests
  1 and 6 carry a failing harness part"; state the exclusion rule by evidence
  validity rather than by outcome; stop reopening the reported QEMU evaluation
  scope of RQ3 through D014; and write the acceptance and protocol proposals
  for review. The dated entry "2026-09-19 03:29 WEST - G0 closure" of the
  project-management instruction register, held outside the repository,
  together with its amendment at line 59, records the student's statement,
  verbatim "Penso que o G0 se pode considerar fechado", and the project
  manager's concurrence, and asks that the G0 decision and its scope amendment
  be published together in this update. **The guest stays off, and test
  acceptance remains paused at the student's request.**
- **Findings — the integration battery of 2026-09-18, test by test.** The
  record is the candidate archive
  `~/yocto/evidence-candidates/2026-09-18-integration-tests/` in the WSL2 home
  of the workstation. A confirmation is late when its Ditto acknowledgement
  falls after the controller-clock deadline, the controller marker plus 60 s;
  a late record does not rescue its message. The nine families were exercised
  once:
  1. *Smoke and harness artefacts:* three ad-hoc repetitions are recorded; the
     timed harness runs `smoke_sequence-r01` (2026-09-18) and `-r02`
     (2026-09-19) are **invalid**, their resource files not ingested.
  2. *Three wearables:* **functional result demonstrated** — 672 valid events,
     672 delivered in time, 0 lost, 0 late (600 from the smart clothing, 60
     from the smartwatch and 12 from the smart ring). The margin is thin: the
     last acknowledgement came 3.1 s before the deadline, and an earlier
     672-message preflight run had 378 late.
  3. *Invalid payloads:* **rejection behaviour demonstrated** — 67
     intended-invalid payloads rejected, none accepted and no valid one
     rejected — but 132 of the 1,277 valid events were confirmed late, so it is
     not a zero-late run.
  4. *Duplicates and sequence:* **duplicate handling demonstrated** — 672
     duplicates, none double-accepted. **The required sequence-reset sub-check
     `itest-dup-02` was not run**: the runbook states it in prose, the
     battery's commands were extracted from fenced code blocks only, and the
     archive holds no such record. The post-replay warning "IMPLAUSIBLE
     controller confirmation marker" is explained: the deliberate replay falls
     after the window and the guard compares the deadline with the latest
     receive time over all records, so the in-window figures are unaffected.
  5. *Disconnect and reconnect:* **fails its stated temporal criterion** — all
     2,016 valid events were eventually accepted, but only 1,690 within the
     deadline and **326 late**, where the runbook requires `lost = 0` and
     `late_confirmations = 0`. Three deliberate disconnects and 165 buffered
     events were observed. Two validation paths disagree: the reconciliation
     warns that the simulator manifest is absent from the harness layout,
     while the totals it appends from the simulator's own manifest show them.
  6. *Controller restart:* the timed harness runs `controller_restart-r01`
     (2026-09-18) and `-r02` (2026-09-19) are **invalid** (resource gaps and a
     controller-metrics outage), so recovery and delivery are not accepted.
  7. *MongoDB fault:* **bounded retry and fault behaviour demonstrated**, not
     lossless delivery — 62 events failed after their three attempts, and of
     the 3,298 accepted, 1,012 were late. The runbook's repeat for Ditto
     (`itest-ditto-fault-01`) was **not run** either, for the same extraction
     reason, so test 7 covers only its MongoDB half.
  8. *Guest reboot:* **reboot and persistence demonstrated** — the boot id
     changed, the twin counters persisted and a fresh 336-event run reconciled
     with 0 lost and 0 late. The controller's own counters restarted at 0, as
     the runbook expects.
  9. *TLS and authorisation:* **the tested checks passed** — wrong CA, wrong
     password and plaintext refused, the ACL probe passed and anonymous access
     was refused (exit code 5). This is not a general security assurance.

  All 312 entries of the archive's `SHA256SUMS` verify. It is a **locally
  hash-sealed candidate archive, not incorporated into or admitted by the
  project evidence record**, and an outer archive seal does not make a nested
  invalid run valid. Two sub-checks were not run, the sequence reset of test 4
  and the Ditto repeat of test 7: both stood in the runbook's prose, and the
  tooling that extracted the battery's commands took only fenced code blocks
  and dropped them. The battery is **not complete** and no official campaign has
  been completed or admitted; its measurements are diagnostic, not accepted
  campaign results or native performance evidence.
- **Findings — the invalid timed attempts of 2026-09-19.** Both
  `smoke_sequence-r02` and `controller_restart-r02` (run directories under
  `~/egw-tcg/pilot/results/raw/`) are **invalid**: ingestion rejected the first
  run's resource file for 25 distinct sample instants against a minimum of 30,
  and the second's for one 6.0 s gap in the controller's series, 00:18:29Z to
  00:18:35Z, inside the recorded restart interval, against the 5 s limit; the
  second run's `controller_metrics.csv` also has 26 failed polls and a
  29.115 s gap. Counted by exact message ID against each manifest's
  controller-clock deadline — **diagnostic counts, never campaign results** —
  `smoke_sequence-r02` published 336: 236 in time, 15 late and 85 with no
  accepted record in the fetched log, all 85 a backlog that the controller's
  accepted counter shows was accepted later (a check on the counter, not on
  message identities); `controller_restart-r02` published 6,720: 3,795 in
  time, 24 late and 2,901 with no record. Two findings follow, with their
  limits:
  - **Throughput.** Under QEMU/TCG the controller's single consumer, which
    processes messages one at a time with one sequential Ditto request each,
    sustained about 3–8 acknowledgements per second against a publishing rate
    of 11.2 msg/s; its queue grew by 4.7–10.6 per second, and latency was
    50–86 s at the median and 69–157 s at the 95th percentile (emulated,
    informational). The broker kept up, with a median transit of 2–14 ms. The
    late confirmations of tests 3, 5 and 7 of the battery fit the same
    backlog: in every battery run the controller had received every message by
    the marker.
  - **The restart appears to discard the controller's in-memory queue.** Of
    the 2,901 messages of `controller_restart-r02` without an accepted record,
    about 765 fit the backlog, but about 2,136 do not: 1,765 were published
    before the restart and about 371 during the outage. The MQTT client
    acknowledges on enqueue, the queue is in memory and the client uses a clean
    session with a fixed client id, so messages queued, or published while no
    session existed, would not survive a restart. This bears directly on claim
    C12 and on RQ2, and it is a design and data-path issue, not only a matter
    of emulator speed.
  - **Limits of both.** They come from two invalid runs, under emulation. The
    guest-side event log on the data disk, the twins' ingestion counters and
    the container logs were **not read**; the fetched event log is a snapshot
    taken about 2.6 s after the deadline; the stop timeline is inferred; and no
    permanent loss is asserted. The controller code is identical between the
    harness commit of the r02 runs (`8e88670`) and `dev`, but the commit of the
    image deployed in the guest was not verified. The restart finding needs
    confirmation from the guest-side logs after resumption, and then a separate
    design decision.
  - **Instrument binding and hook order.** Both r02 runs used an intermediate
    collector, sha256 `f17bdd8c66da…4e47a`, that matches no committed version;
    the version pushed as `aa7440d` (`b7aeddba…136e`) was installed at
    00:26:31Z, after both runs had begun, and has been exercised only idle. The
    manifests record the harness commit, whose collector is a different one,
    and no collector hash. The harness stops the collector **before** the 60 s
    confirmation window (`run.py` lines 1941–1943), so a condition without a
    warm-up gives the collector almost no pre-roll and its priming sample falls
    inside the measured window (first rows 1.4 s and 1.7 s after the start of
    the window in the two r02 runs).
- **Findings — governance.** Section 4.3 of the canonical plan excluded "an
  unsealed or failing run" from every summary, acceptance and figure. That
  contradicted the plan's own "Failures kept" condition and its rule that
  slowness alone never excludes a run, and it is broader than the implemented
  analysis (`analyze.py` lines 312–342 and 3498–3534), which excludes by
  validity and integrity and keeps a valid run with `lost > 0`, so that the run
  fails its criterion. D014 held open, as a blanket blocker of G4–G7 and of the
  final academic release, a question the student reports already answered: the
  research questions approved with RQ3 evaluated with QEMU tests. And three
  documents disagreed about G0's conditions: plan section 4.2 named the
  alignment package and not the off-machine copy, which the plan's G7 criterion
  already carried; the gate log named both; `PROGRESS.md` tagged the
  off-machine copy "G0 — In progress" and the alignment email "G0 — Blocked".
- **Action — the G0 decision.**
  [`docs/governance/decisions/2026-09-19-g0-closure.md`](docs/governance/decisions/2026-09-19-g0-closure.md)
  (new) is the durable decision record, readable from a clean checkout: G0
  **Accepted** on 2026-09-19 for project initiation and baseline alignment,
  authority Student (Rui Duarte), with the project manager's concurrence; the
  accepted scope; the register's residual-obligation table, with a column
  naming where this repository tracks each obligation; the previous state;
  what the decision does not do; and the source entry and its amendment quoted
  verbatim, the register named by its file name only. It is a dated change of
  G0's exit scope, **not** a retroactive pass against the legacy conditions.
  `docs/governance/gate_decision_log.md`: the G0 row reads Accepted,
  2026-09-19, Student (Rui Duarte), citing the record and this entry; the
  replaced `Not decided` row is kept verbatim under a new "Superseded row
  states" section; a dated sentence says that the decision rests on the
  student's own statement, not on a reported confirmation. Plan section 4.2:
  the G0 bullet states the decision, with its former wording kept as a dated
  note, and the "G0 external actions" row of section 2 and section 6 say that
  the alignment package is no longer a G0 condition. `PROGRESS.md`,
  `README.md`, `docs/README.md`, `docs/g0/backlog.md` and `docs/g0/risks.md`
  record the acceptance and the reallocation: integration defects and
  admissible run evidence to G2/G3; D007, the fault-window rules, the loads,
  the 95-run feasibility and the frozen protocol to G4; genuinely unsettled
  method or claim detail tracked at G4/G6, with no blanket D014 blocker; the
  scoping review's execution and the writing to Chapters 1–4 and G6; the
  template check, the AI-use declaration and the final evidence package to G7;
  and the verified off-machine copy, its hash and its restore path as an active
  resilience action owned by the student — R25's owner changes from "Both" to
  the student — retained in the risk register and the backlog and required at
  G7, **neither verified nor waived**.
- **Action — the battery restated in place.** Each current-state statement is
  corrected where it stands, with a short dated note: the status section and
  G3 row of `README.md`; in `PROGRESS.md`, the gate-status block, now dated
  2026-09-19, with its G3 bullet, and the effort row of the nine families; the
  runbook row of `docs/README.md`; both battery rows of `docs/g0/backlog.md`;
  the G3 note of the gate log; the unit-evidence row of plan section 2; the
  Evaluation automation cell of `docs/academic/c2dta_p0_traceability.md`; the
  status note of `docs/setup/qemu_integrated_gateway.md`; and, in
  `docs/adr/0008-integrated-yocto-arm64-evaluation.md`, the Consequences
  bullet and the corrected statement of the 2026-09-19 amendment, which no
  longer says that the sampler defect is fixed — it is addressed under its own
  change, not merged into `dev`. "Unsealed" becomes "locally hash-sealed
  candidate archive, not admitted" in the same places. In the same pass, the first-flow record of 2026-09-18, all 51 entries of whose `SHA256SUMS` verify, becomes a "locally hash-sealed candidate, outside the published evidence package, not admitted" wherever current state called it unsealed; blanket statements that nothing has been measured become "no official campaign has been completed or admitted", the diagnostic measurements being neither accepted campaign results nor native performance evidence; and the memory and graceful-stop correction merged through pull request #34 is no longer called open, general or prolonged stability staying not demonstrated. Where such a statement stood on `dev` in the runbook status, ADR 0008's amendment of 2026-09-18 or a historical proposal, it is kept and superseded by a dated note or marker. The historical
  proposals under `docs/governance/proposals/` take dated markers beside the
  false sentences, without rewriting them: sections 6.1 and 6.2 of the plan
  v2.0 proposal, and the banner and item 6 of the v2.0 alignment memo, whose
  bold sentences are marked not to be sent as written. The runbook also gains
  dated notes on the failure of test 5, on the invalid timed runs of test 6,
  the latter pointing to the proposed restart rule, and on test 7, which
  covered the MongoDB fault only; and, in the test 1 paragraph, the hook order
  as implemented — stop hook before the 60 s window, fetch hook after it.
- **Action — the two prose steps of the runbook fenced.** In
  `docs/setup/qemu_integrated_gateway.md` the two steps that the extraction
  tooling dropped are now fenced `host$` blocks, their commands unchanged, so
  that they cannot be skipped the same way: the test 4 sequence reset
  (`run_test itest-dup-02 ...`), right after test 4's expected results, and
  the test 7 Ditto repeat (`R=itest-ditto-fault-01; SVC=ditto-things`, then
  test 7's test line and evaluation line, copied unchanged), under a heading
  of its own, "Repeat of test 7 for Ditto", because the runbook's tests
  (`src/tests/test_runbook_itest_helpers.py`) read the fenced commands of the
  test 7 section as a single run. A dated note in test 4 and in test 7 records
  that the step was not run. This is a change of form only: no command,
  criterion or result changes, and neither sub-check has been run.
- **Action — the exclusion rule and D014.** Plan section 4.3 (G5) now excludes
  by evidence validity, never by outcome: a run with missing or corrupted
  provenance or invalid instrumentation is excluded from the eligible
  quantitative aggregates but retained and reported with its reason; a valid
  run showing overload, loss, late confirmation or failed recovery is retained
  and analysed — the system fails the criterion and the observation does not
  vanish; conditions are never repeated until they pass, and changed
  configurations or protocols are never mixed unidentified. This is a wording
  correction; the analysis code already behaves this way. D014, in the plan
  (banner and sections 1.1, 2, 3.2, 3.5, 4.3, 4.4 and 6) and in
  `docs/governance/supervisor_decision_log.csv`: the QEMU evaluation scope of
  RQ3 is recorded as **reported approved** — reported by the student, undated,
  not a documented supervisor decision — and is not reopened; the open part is
  narrowed to the wording of the limitation that records the absence of native
  evidence and of any claim about emulated timing or resource figures, tracked
  at G4 and G6, with the numerical criteria under D007; D014 is no longer a
  blanket blocker of G4–G7 or of the final academic release. Its status stays
  `partly_confirmed_reported_by_student`, with `sent_at` and `response_at`
  empty. D008 and D011 in the decision log, and D008 in
  `docs/g0/supervisor_decision_matrix.csv`, take dated notes that point to the
  narrowed D014, their statuses unchanged. The plan also states the scoping
  review (D003) and the waiver of a second software tester (D006) as settled
  decisions, separate from their incomplete execution and documentation, and
  its section 9 itemises this update. Current-state text elsewhere that still
  described the QEMU evaluation scope or the academic use of emulated results
  as open under D014 is corrected in place, each with a dated note — rule 6 of
  Section 8 of the runbook among them — and the historical v2.0 alignment memo
  takes dated markers, without rewriting, beside its banner sentence, its D014
  request and the two sentences that treat the evaluation scope as unagreed or
  as a condition of submission. Where any such wording remains, rule 5 of plan
  section 3.5 and the D014 row of the decision log govern.
- **Action — what is new and true.** `PROGRESS.md`: a row for the per-test
  record of the battery, a row for the diagnostic findings of the r02
  attempts, and the controller row corrected, which said that no real restart
  had been exercised. `docs/g0/backlog.md`: four G2 actions — run the two
  missing sub-checks, the test 4 sequence reset and the Ditto repeat of
  test 7; retain and follow up the test 5 deadline failure; diagnose the
  delivery backlog under QEMU/TCG; and confirm the controller-restart queue
  finding before a design decision. `docs/g0/risks.md`: a section "Findings recorded on 2026-09-19"
  registers the restart queue finding against R31 (with C12 and RQ2) and the
  throughput finding against R13 and R23, with cross-notes; no identifier is
  created, because the range is frozen. `docs/claim_evidence_matrix.md` and
  `docs/claim_evidence_matrix.csv`: C12 stays `Pending — no evidence` and takes
  a dated note, admitting nothing, that points to the findings and to the
  proposed restart rule.
- **Action — the acceptance and protocol proposals.**
  [`docs/governance/proposals/acceptance_protocol_update_2026-09-19.md`](docs/governance/proposals/acceptance_protocol_update_2026-09-19.md)
  (new), marked **PROPOSED — for review, not adopted**, gives the verified facts
  and, per item, what stays unchanged and who decides: (1) short-run selection
  — keep the 30-distinct-instant minimum and the 60 s confirmation rule, and
  run the next instrumentation acceptance as a nominal entry with its declared
  duration unchanged, under a new run identity, which is not a passed 30-second
  smoke; whether the count should be taken inside the window and whether
  duplicate `(container, ts)` rows should be rejected stay open questions;
  (2) a lifecycle-aware rule for a deliberate restart — a designated window for
  the restarted container only, opened at the start of the restart command,
  closed at the first successful `/ready` answered by the new instance and
  capped at the command's finish plus `RESTART_RECOVERY_MAX_S`, the run failing
  its recovery criteria if the cap is reached; the 5 s limit everywhere else;
  data never zero-filled or interpolated; the first post-start CPU-delta sample
  within 5 s of the close; no exemption for delivery accounting; fifteen
  regression cases; (3) late delivery as its own issue, with the two findings
  above and unchanged deadline semantics; (4) the test 4 sequence-reset
  coverage, with the Ditto half of test 7, recording that both prose steps
  were moved into fenced blocks on 2026-09-19 as a change of form only;
  (5) binding every run to the hashes
  of its exact helper, deployment configuration, controller image and
  collector; (6) the acceptance sequence after resumption — one fresh bounded
  acceptance pair first, stop on failure, then only the affected or missing
  checks, then G3, with no jump to the 95 runs or the 24-hour soak.
  `docs/governance/proposals/README.md` gains its index row.
- **Verified, and how.** Every fact above was verified on 2026-09-19,
  read-only, against primary evidence: the battery archive (`sha256sum -c`
  over its 312 entries; every per-test figure recomputed from
  `sent_events.jsonl`, `events.jsonl` and the controller marker, and matching
  the reconciliation outputs exactly); the r02 run directories (manifests,
  `controller_metrics.csv` and the fetched event logs, counted by exact message
  ID); the candidate archive
  `~/yocto/evidence-candidates/2026-09-19-sampler-fix/` for the collector
  installations and their hashes; and the source at `dev` revision `40aae52`
  and at `aa7440d`, read with `git show` and `git grep`. The reconciliation and
  analysis code is byte-identical between `8e88670`, `9ffd365` and `40aae52`.
  Both quotations in the decision record were compared with the register and
  are identical. On this change, from the work-tree root:
  `python tools/ci/check_markdown_links.py` (91 Markdown files) and
  `python tools/ci/verify_evidence.py` (304 artefacts across 14 evidence
  seals) pass; the three edited CSV files parse with their column counts
  unchanged (9, 9 and 5); the runbook's code fences balance, and
  `src/tests/test_experiments_itest_reconcile.py`, which parses the runbook's
  `$REC` lines, passes (106 cases); `src/tests/test_runbook_itest_helpers.py`,
  which does not run on Windows, passes on the WSL2 Ubuntu host (64 cases)
  with both fenced sub-check steps in place. The GitHub workflow result, not
  this entry, establishes whether the required checks pass.
- **Not shown and not done.** The guest was not booted and its data disk was
  not accessed; no test, harness run or campaign was executed; **test
  acceptance stays paused at the student's request** and nothing here resumes
  it. **No evidence is admitted**: the battery archive and the first-flow
  record stay outside `docs/evidence/`, and every r02 figure is diagnostic.
  **No gate beyond G0 is decided** — G1 stays accepted as recorded on
  2026-08-14 and G2–G7 stay `Not decided` — and **no claim is admitted**: 0 of
  15, C12 included. The G0 decision marks neither the historical alignment
  package as sent nor the off-machine copy as made, verified or waived; nothing
  is sent to the supervisors; no supervisor date, message or name is recorded,
  and no reported confirmation becomes a documented supervisor decision. None
  of the proposals is adopted: no protocol constant, validator, harness
  behaviour or code changes; D007's numbers and the protocol freeze stay
  separate decisions; and the old runs stay invalid under their original rules.
  The restart queue finding is not confirmed, no permanent loss is claimed and
  no design decision on the restart path is taken. Neither missing sub-check
  was run — the test 4 sequence reset and the Ditto repeat of test 7 were only
  moved into fenced blocks. The docstring of `resources.py` (lines 92–95)
  that places the collector stop after the confirmation window is code and is
  not changed here; the same wording on the sampler branch belongs to that pull
  request.
- **Correction of entries #C032 and #C033, which are not rewritten.** #C033
  said that the nine families were exercised once, that "seven passed, and
  tests 1 and 6 have a failing harness part", and that the record was "held
  outside the repository and unsealed". The first overstates the record and
  the second misclassifies it; the per-test account and the classification
  above replace both. #C032's statement that none of the nine families had
  been run was superseded by #C033 and is replaced, like #C033's, by the
  per-test account above. #C033's description of D014 as
  holding open the scope of the evaluation and any academic use of emulated
  results, and its sentence that approving the QEMU route is not approving the
  academic use of its results, are superseded by the D014 revision above. The
  other boundaries of both entries stand, with three exceptions, the dated entries themselves being kept as written: the first-flow record they call unsealed is a locally hash-sealed candidate (all 51 `SHA256SUMS` entries verify), outside the published evidence package and not admitted; the `ditto-things` teardown correction they call open has since been merged into `dev` through pull request #34, with general or prolonged stability not demonstrated; and "nothing has been measured" is too broad — no official campaign has been completed or admitted, and the diagnostic measurements are not accepted campaign results or native performance evidence.
- **Decisions and next steps.** Decided by the student on 2026-09-19: **G0
  Accepted** for project initiation and baseline alignment. No other gate,
  claim or maturity level changes, no documented supervisor decision is
  created, and none of the proposals is adopted. Next: the student verifies
  the off-machine copy, its hash and its restore path promptly, as an active
  resilience action required at G7, and decides on each proposal as the
  proposal document names. After the student resumes test acceptance, and not
  before: read the guest-side event log, the twins' ingestion counters and the
  container logs of `controller_restart-r02`, read-only, to confirm or refute
  the restart queue finding, and take a separate design decision on the
  restart path before any C12 evidence is collected; then, if the proposed
  acceptance sequence is adopted, one fresh bounded acceptance pair requiring
  resource ingestion, end-to-end deadline accounting and recovery evidence,
  stopping on failure, and afterwards only the affected or missing checks —
  `itest-dup-02` and the Ditto repeat of test 7 among them — under new run
  identities, unchanged deadline semantics and recorded instrument hashes; then
  G3. No jump to the 95 runs or the 24-hour soak. The resource-sampler change
  (`#C034`) proceeds under its own review, and D007 is still owed before
  `exp-v1`.

---

## Entry #C036 — Local test outputs, the collector's six services before the seal, and the first valid harness run on the emulated guest

- **Date:** 2026-09-19
- **Request:** the project-management work order of 2026-09-19 (held outside
  this repository), packages A to C and its first checkpoint: a clean
  execution baseline, a local `output_test` folder in which every test attempt
  is exported with verified checksums at completion and on failure, the
  collector's expected services and companions accounted for in the executable
  workflow before the seal, then a live preflight, a smartwatch slice and the
  nominal instrumentation entry. The 95 runs and the 24-hour soak are not part
  of it, and the acceptance proposal of `#C035` stays unadopted.
- **Action — baseline.** A clean clone of `dev` for execution
  (`/home/ruisth/egw-exec/repo`, with its own virtual environment from
  `src/requirements.lock`) and a clean worktree for development; the old
  Windows working tree is preserved untouched. The OS image is not rebuilt: its
  build inputs (`src/yocto/kas`, `meta-egw`) did not change from `03e333e` to
  `fb1690d`, nor did the controller image's (`0dfa531`), so the identified
  kernel, rootfs and controller archive are reused; each guest session records
  how the Yocto checkout, the clean clone and the deployed tree differ.
- **Action — local outputs.** `egw_experiments.local_export`
  ([`docs/setup/local_test_outputs.md`](docs/setup/local_test_outputs.md)):
  one package per attempt under `output_test/runs/<date>/<run_id>/`, never
  replacing an earlier one, with every copied file re-read and compared by
  SHA-256, raw capsules copied byte for byte with their own seals, secrets and
  private keys excluded with redacted derivatives, special files listed and
  never read, instrumentation validity, system outcome and copy verification
  kept apart, and an index regenerated from the packages on disk. The session
  drivers of [`tools/session/`](tools/session/README.md) run the bounded
  checks and export every attempt on every exit path.
- **Action — the collector in the executable workflow.** `--expect-services`
  with the six Compose names reaches the collector through the start hook;
  `src/deployment/scripts/fetch-collector-output.sh` fetches the CSV with its
  `.diagnostics.log` and `.lifecycle.csv` companions (and a `.self-test`
  marker), each checked against the guest's own sha256; before the seal the
  manifest records the deployed collector hash, the fetch helper's hash, the
  inventory and the rows of every expected service, and a missing companion, a
  self-test marker, a missing or different expected set, a missing service or
  an expected service without rows makes a timed run invalid. The manual path
  (`--resources-from`) is accounted for the same way. A timed-out hook's whole
  process group is killed. No ingest threshold and no delivery rule changed.
- **Review.** One static review of the branch, with an adversarial
  verification of each finding, confirmed 26 defects: the export's recovery
  could mark a still-running attempt interrupted and freeze that verdict, a
  secret in an attempt field could reach the summary, an unscanned package
  looked scanned, and smaller ones in the export and the harness. All were
  fixed with tests before this entry.
- **Verified, and where.** Unit suite in WSL2 Ubuntu 24.04 (Python 3.12.3):
  1,364 passed and 53 skipped at `fe954a9` (the busybox variants of the
  collector tests, which need the wrapper environment); 1,369 passed at
  `03958c2`, the head reviewed on 2026-09-19, and 1,765 passed with 64 skipped
  after the corrections of 2026-09-20 below. Each count belongs to the commit
  beside it. Every attempt below is a package in
  `C:\Users\ruimf\Documents\Projeto Mestrado\output_test` with a verified seal,
  listed in its `INDEX.md`:
  - export checks: one passing test module and one deliberately failing test,
    both exported, the failure kept as a failure;
  - fifteen historical packages backfilled (the 2026-09-18 capsules, the
    invalid r01 and r02 harness runs, the unclosed session `sampler-01`, the
    collector capsule), copied as preserved and indexed as historical;
  - one guest session: boot to SSH in 34 s after an ext4 journal recovery on
    both disks, the stack stopped before power-off, no memory-cgroup OOM, the
    G1 artefacts unchanged;
  - **live preflight — valid, pass:** the stack started through the 5.5
    interlock; the clone's collector (`d3b219bc…`) replaced `b7aeddba…` on the
    guest; a 45 s run gave 45 distinct instants for each of the six services,
    no UTC gap, no withheld sample, inventory `missing=none`, and
    `validate_resources_csv` passed; the deployed tree equals the clone except
    `README.md`;
  - **smartwatch slice — valid, pass:** `itest-slice-01`, seed 20260920 (a fresh
    twin): 60 sent, 60 delivered, 0 lost, 0 late, `check` and `delta` 0, twin
    `accepted_count` from absent to 60, marker lag 0.148 s;
  - **nominal entry `nominal-r01` — instrumentation valid, system fail:** the
    first harness run on the emulated guest that the harness itself marks
    valid and seals, with `resources.csv` ingested (720 rows for each of the
    six services), the companions and hook outputs sealed, the controller
    marker lag 0.019 s and collector hash `11444c0a…` (the clone at `fe954a9`).
    At the controller-clock deadline 3,794 of 6,720 valid messages were
    delivered and 2,926 were lost at the deadline (85 of them confirmed late
    before the harness fetch); after the drain all 6,720 had an `accepted`
    outcome, 2,926 of them late. Latency p50 264 s. This is a system result on
    ARM64 EMULATED (QEMU/TCG): the controller processes about 5 to 6 messages
    per second against 11.2 offered.
- **What is not shown.** No gate is decided and no claim moves: the preflight,
  the slice and the nominal entry are engineering diagnostics, not acceptance
  runs under an adopted rule. The nominal outcome is not a capacity
  measurement. The controller's restart recovery (package D) and the final
  battery (package E) have not started. `output_test` is a local copy, neither
  published evidence nor a backup.
- **Provenance of the live observations** (corrected here on 2026-09-20, after
  the project review: the earlier draft of this pull request described them as
  one commit). The export checks, the guest session, the live preflight and the
  smartwatch slice ran from `a3b0d56`; only the nominal entry ran from
  `fe954a9`. `tools/session/` did not exist in the repository at either commit:
  it was versioned at `d7b7a72`, **after** every live command. What ran were the
  working copies in `/home/ruisth/egw-exec/drivers`, whose concatenated sha256
  each attempt records (`identities.drivers_sha256`: `8be60f66…` for the export
  checks, `ca0eb1f6…` for the session and the preflight, `aab9fff5…` for the
  slice, `9e3a334b…` for the nominal entry, as `slice.sh` and then `nominal.sh`
  were added). The seven drivers that existed when the session opened were
  byte-identical throughout it, and the copies preserved inside the guest-session
  package equal those working copies file by file. The versioned drivers differ
  from them substantially — between 6 and 229 changed lines per file — first
  because every workstation path became overridable and then because of the
  corrections below, so the observations of 2026-09-19 were not produced by the
  drivers this pull request versions.
- **Corrections after the project review of 2026-09-19** (made on 2026-09-20,
  before any merge; three commits). The review asked for five: the export
  destination is now confined physically (a symbolic link, a Windows junction,
  another reparse point or a hard link at an owned path is refused instead of
  written through, and every generated file is written through a temporary file
  and one rename); a console capture that fails is recorded with its byte
  counts, exits 74 and cannot be finished as valid, and one rule now decides
  that verdict for the attempt, the package, the summary and the index; the
  preflight and the harness both require a usable start, inventory and closing
  record with an ordered window, and reconcile the closing record with the CSV
  only where it contradicts itself, leaving spacing and coverage to
  `validate_resources_csv` against the protocol's own tolerance; a registered
  source keeps its own name, so a linked, dangling or relative root is listed
  and never read; and every driver derives its exit status from the verdicts it
  recorded (0 pass, 1 a valid negative result, 2 a prerequisite, 3 invalid
  instrumentation or a mandatory step, 4 an export that could not be verified,
  5 a controlled stop, 130 interrupted), skipping what depends on a failed
  prerequisite. Six adversarial reviews of the corrections themselves, each
  with reproductions, found 84 further defects — among them a hard link that
  defeated the confinement, a capture failure that could be lost, an export
  check that read any non-zero code as the intended failure, a tree comparison
  that looked in one direction only, and, twice, a correction of ours that
  would have invalidated runs the protocol accepts. All were fixed with tests.
  The known limitations that remain are recorded in the pull request. No
  acceptance threshold, delivery rule, deadline or ingest limit was changed, and
  regenerating the index from the twenty-one existing packages reproduces them
  unchanged: no earlier verdict moved.
- **One more correction, after the project review of 2026-09-20.** The review
  held the pull request for a semantic defect of the work above, introduced by
  this developer: an OOM kill or a restart the run positively showed made the
  driver record the instrumentation invalid, which would discard exactly the
  negative results this dissertation has to analyse. Observing the system fail
  is a result; failing to observe is an invalid measurement. Every step after
  the harness now falls into one of three groups — evidence that is missing,
  unreadable or incomparable (the measurement is invalid, naming the
  requirement), a fault the run showed (the system outcome fails, the
  measurement stays as valid as the evidence says) and a post-window
  observation that could not be made (recorded as incomplete, leaving the
  sealed window's verdict alone, with nothing claiming eventual delivery or a
  complete tail) — and a fault that also breaks the clock domain the
  confirmation deadline rests on gives that specific invalidity with the fault
  kept as a fact. Four further review rounds of that correction found fifteen
  defects in it, all fixed with tests, three of which were the same error
  reversed: a comparison that crashed, or a record left incomplete by a lost
  console capture, could have been written up as a failure of the guest; a
  clean pass could be claimed on incomplete evidence; and the new health rule
  would have failed the very preflight of 2026-09-19 that passed, whose record
  reads `egw-controller-1 running starting`. A criterion that rejects the
  evidence already held is as wrong as one that admits what it should not.
- **Decisions and next steps:** none taken here. The next packages are the
  bounded recovery ADR and fix (D), then the coordinated battery on one
  unchanged candidate (E). The authorship rule of 2026-09-19 (author and
  committer both `Ruisth` for every commit, merges included) is not met by a
  merge made on GitHub, whose committer is `GitHub`; the repository ruleset
  requires pull requests and has no bypass actor, so a compliant merge
  procedure needs a decision by the student on the ruleset.


## #C037 — Requirements matrix and supervisor deliverables — 2026-09-21

- **Request:** after supplying the supervisor's implementation-focused email,
  the student asked to create the matrix and add the deliverables to planning.
- **Base and preservation:** fetched origin; dev/origin-dev resolved to
  ccd5fd647a57842707999fa3f2492befa228e11b. Prepared the change on
  docs/g0-supervisor-matrix in an isolated worktree. Preserved the older dirty
  Windows checkout, the original manuscript and all experimental records.
- **Delivered:** 18 requirements with sources, authority, criteria and test/gate
  mappings; primary-source platform comparison and provisional Pi 5 8 GB
  recommendation; i.MX95 EVK alternative and Pi 4 exclusion for MongoDB 7;
  research-question crosswalk and V1 consumer-control inventory.
- **Planning:** version 2.1 adds SUP-01–SUP-07 with owners, dates, dependencies
  and exit criteria, in parallel with existing implementation/review work.
  Updated PROGRESS, backlog, risk entries RS01–RS03 and documentation links.
  Archived the source plan v2.0 exactly, SHA-256 dcbccda1477d1dd4ddce6fb451457e9ec37ff608045eae141bd998f0907b4d1a.
- **Evidence:** inspected the local 2026-09-20 smartwatch/persistence summaries
  for planning; recorded them as unadmitted engineering candidates in PROGRESS.
  No experiment was run, record resealed, acceptance resumed, threshold changed
  or claim/gate admitted. QEMU-only execution, title/RQ numbering, the
  95-attempt target and delivery dates remain unchanged.
- **Decision boundary:** the student's request authorises the documentary and
  planning changes; it is not a supervisor approval of a board or revised RQs.
  No spending, physical build or native evaluation was undertaken. Publication
  and integration follow the repository review workflow.
- **Verification:** repository-local links passed for 94 Markdown files;
  evidence verification passed for 304 artefacts across 14 seals; the archived
  v2.0 matches the source Git blob byte for byte; 18 unique requirement rows
  and seven deliverables were checked against the plan/state/backlog IDs.
  Active-document whitespace checks passed; the archive retains its exact
  historical bytes. A separate documentary review identified only version-link
  ambiguity, corrected before publication. No application tests were required
  for this documentation-only change.

---

## Entry #C038 — The complete G2 flow inside the emulated guest, and the acceptance proposal it is presented with

- **Date:** 2026-09-21
- **Request:** the project-management work order of 2026-09-20 (held outside
  this repository) and its five clauses — preparation, complete path,
  persistence, evidence and acceptance: assemble the complete G2 candidate on a
  clean identified baseline, establish the gate preconditions the plan asks for
  rather than the weaker ones an engineering preflight accepts, run exactly one
  bounded flow, prove stored-state persistence while nothing is in flight,
  publish the capsule and put the gate to the student clause by clause. The
  nine integration families, the nominal workload, the soak and the 95 runs are
  not part of it.
- **Action — the two drivers.** `tools/session/gate_health.sh` for the stricter
  G2 preconditions and `tools/session/persistence.sh` for section 6.5 of the
  runbook, versioned at `b7e0c83` on `feat/g2-session-drivers` above the merged
  `dev` at `ccd5fd6`. Unlike the session of 2026-09-19, whose live observations
  came from unversioned working copies, **six of the seven attempts of this
  session record `repo_commit b7e0c83…` with `repo_dirty_lines: 0`**, read by
  the driver itself: what ran is what the repository holds. The seventh, the
  single-file deployment between the two preflights, was not run by a driver;
  its identities were written by hand and name the commit without a dirty-line
  count.
- **Action — the session.** One guest session
  (`20260920T231756Z_guest-session_attempt02`): identities read before the boot,
  boot, state after the boot, the stack stopped before power-off, and the three
  artefacts the G1 seal covers — `Image`, `egw-image-qemuarm64.rootfs.ext4` and
  `egw-image-qemuarm64.rootfs.manifest` — each read back `OK` afterwards; every
  command of the attempt exited 0. The
  candidate is the image `egw-gateway-image-qemuarm64` of build
  `20260918120819` (kernel
  `Image-qemuarm64.bin` `4457ef38…`, rootfs archive `d4569c0e…`) under QEMU
  8.2.7 TCG, `-machine virt -cpu cortex-a76 -smp 4 -m 8192`, with the six
  container identities and the controller build identity `0dfa5314…`. **ARM64
  EMULATED (QEMU/TCG) on an x86-64 host; never native ARM64, never KVM.**
- **The preflight that failed, and why.**
  `20260920T231844Z_live-preflight_attempt02` is recorded **`failed`, with the
  instrumentation invalid and the system not run, and is kept**. The
  two-directional comparison of the deployed tree against the clean clone found
  `src/deployment/scripts/fetch-collector-output.sh` in the clone and not on the
  guest — a file the clone has carried since pull request #38 — so the driver
  stopped at that prerequisite and recorded the eleven checks after it as not
  run, rather than reporting a preflight it could no longer trust. **The
  six-container stack was started inside this failed attempt**, not inside the
  one that repeated it: its first command ran the 5.5 interlock and `up -d`
  between 23:18:44 and 23:21:18, creating and starting all six containers, and
  the failure came four commands later. This is the one-directional comparison
  corrected on 2026-09-20 doing its work: the earlier
  form compared only the paths the guest listed, so a file the clone held and
  the guest had never received was not a difference at all, and the preflight
  would have passed.
- **What was fixed, and how.**
  `20260920T232205Z_deploy-the-clone-fetch-helper_attempt01` deployed that
  single file in one command, whose argv the package seals: the session's own
  `gscp` helper copied `src/deployment/scripts/fetch-collector-output.sh` from
  the execution clone to `/tmp/fetch-collector-output.sh` on the guest, then
  `gssh` ran `sudo cp`
  of it into `/opt/egw/deployment/scripts/`, `sudo chmod 0755` and `sha256sum`
  over the two guest paths. **That was a bounded single-file deployment made by
  the developer between the two preflight attempts, not the runbook's
  deployment step**: the attempt's own note cites runbook 5.1 as the provenance
  of the deployed tree, but no step 5.1 was run. The two hashes the attempt
  holds are **both hashes on the guest** — `/tmp/fetch-collector-output.sh` and
  `/opt/egw/deployment/scripts/fetch-collector-output.sh`, each
  `9ae07b0c…` — so what they show is that the copy which arrived equals the
  file that was installed; the clone-side hash was printed outside the attempt
  and is not in the package. The repeat ran under a new attempt identity,
  `20260920T232219Z_live-preflight_attempt03`, whose sixteen commands all
  exited 0: the 5.5 interlock re-run, its `up -d` finding all six containers
  already `Running`, the clone's collector deployed and checked live (46 samples, 45 distinct instants, 45 rows for each of the six services,
  no UTC gap, no withheld sample, `missing=none`, no problem), and the deployed
  tree equal to the clone except `README.md`. The services had been started from
  the tree as it stood before that copy; the file is an instrumentation helper
  and not a service input, and the tree was equal to the clone before the gate
  snapshot and before the flow.
- **Results — the gate preconditions.**
  `20260920T232447Z_g2-gate-preconditions_attempt01`, all seven commands exit
  0: the six expected services **running and healthy** — the plan's condition, not the
  `running starting` of the older snapshot — `/health` 200 `{"status":"ok"}`,
  `/ready` 200 with MQTT connected and Ditto reachable, and `/metrics` 200 with
  every counter and `queue_depth` at 0 for the controller process identified by
  `started_at 2026-09-20T23:21:31.554Z`; the six container identities, **five of
  which carry a pinned repository digest** — the controller's records
  `repo_digest=none`, because that image was built locally and never pulled
  from a registry, and it is identified instead by its image id and its build
  record; the controller build identity verified against its record, and the
  broker's TLS configuration recorded as configuration only (listener 8883,
  `cafile`/`certfile`/`keyfile`, `tls_version tlsv1.2`, `allow_anonymous false`,
  CA fingerprint `AA:34:ED:1E:…`, private material at mode 600, read as uid:gid
  1883:1883).
- **Results — the flow.**
  `20260920T232527Z_smartwatch-slice-1-hz-60-s_attempt02`, all seven commands
  exit 0, run `itest-g2-01`, seed 20260921, one smartwatch at 1 Hz for 60 s over TLS to port
  8883: 60 sent valid, 60 delivered unique, **lost 0, late 0, double-accepted 0,
  intended-invalid accepted 0**, deadline from the controller marker, marker lag
  0.184 s, nothing unaccounted. The twin
  `org.c2dta:62da1188-4cd1-434b-a9c7-236a8c211f84` did not exist before and came
  out with `last_run_id itest-g2-01`, `last_seq 59`, `accepted_count 60`, its
  fields matching section 4 of `src/CONTRACTS.md`; `/metrics accepted 0 -> 60`
  and `received 0 -> 60` as well, with every other counter and `queue_depth` at
  0. The latency block it also produced carries its own emulation label and is
  not a performance result; its figures — p50 274.2 ms, p95 8 114.7 ms, max
  9 999.0 ms over 60 confirmations at 1 msg/s — are written out in limitation
  15 of the proposal so that the student reads them rather than passes them.
- **Results — persistence.**
  `20260920T233212Z_g2-twin-persistence-restart_attempt01`, all seventeen
  commands exit 0: publication stopped and the queue drained (`queue_depth 0` and identical counters on 27
  consecutive readings over 131 s, recorded as an observation and not as proof
  that processing had finished); state saved; `compose down` then `up -d` with
  **no volume removed**; the restart **shown**, controller
  `started_at 23:21:31.554Z -> 23:37:38.535Z` and all six containers new objects
  started later; all six healthy again at sample 2 of the poll that followed,
  and readiness re-checked by `wait_ready`, which exited 0 — **that exit status
  is the whole of the evidence for the readiness half**, because the helper
  prints nothing when it succeeds and both console files of that command are
  empty; and, before anything further was published, the same twin read back
  identical, with the run's event log holding
  60 records before and 60 after. The new controller process's counters are 0
  again, which is expected of a per-process counter and is not loss.
- **Published.** The capsule `docs/evidence/g2-complete-flow/` holds the seven
  attempts, the failed preflight among them, each with its own seal and
  manifest; the local packages are under `output_test/runs/2026-09-20/`, which
  is a local copy and neither published evidence nor a backup.
- **The proposal.**
  [`docs/governance/proposals/2026-09-21-g2-acceptance-proposal.md`](docs/governance/proposals/2026-09-21-g2-acceptance-proposal.md)
  sets the session against the normative G2 clauses and the conditions common to
  G2–G7 one row at a time, with the exact evidence path for each, and records
  what is under-recorded (the architecture of the five registry images), what
  holds without being exercised (no intended-invalid payload was offered, and
  the transport refusals were not repeated in this session), and the residual
  limitations of the demonstration itself: one device, sixty messages, one
  restart, one guest, one repetition, an emulated platform, a publisher that
  runs on the host and reaches the guest through port-forwards, and a controller
  image whose Python dependencies are still unlocked.
- **What is not shown.** No gate is decided and no claim moves. **G2 remains
  `Not decided`**, and stays so until the student records a dated decision with
  an authority and a durable decision record; sealing a capsule, a green pull
  request and this entry are none of them that decision. Nothing here accepts
  the nine integration/recovery families, in-flight restart recovery, the
  nominal 11.2 msg/s workload — which failed its delivery deadline on 2026-09-19
  and **stays open** — the soak, the 95-run campaign, any native evidence or any
  capacity figure.
- **Decisions and next steps:** none taken here. The proposal is for the
  student; the points it leaves to him are the capsule's evidence check, whether
  the attempts of 2026-09-19 must be referenced from the capsule, whether the
  two unexercised sub-clauses are acceptable at G2, and the wording of the scope
  he would be accepting. The controller's backlog and in-flight recovery remain
  the open downstream work, and D007 is still owed before `exp-v1`.
