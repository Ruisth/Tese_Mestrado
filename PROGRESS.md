# PROGRESS — fonte única de estado por entregável

> **Este ficheiro é a fonte única de estado do projeto.** O backlog
> ([`docs/g0/backlog.md`](docs/g0/backlog.md)) contém apenas ações, evidência
> esperada, dependências e regras de corte — não contém estado. O registo formal
> das decisões de gate vive no Anexo C do plano integrado; a coluna «Aceite no
> gate» abaixo espelha-o. Estrutura conforme a auditoria externa de 08/08/2026
> (§5.1, §5.2, §14).

Atualizado: 2026-08-10 (bloco P5.4: números de teste alinhados com a última
evidência selada, estado dos gates no dia da decisão do G0).

## Modelo de estado — três campos independentes (auditoria §5.1)

Cada entregável tem uma única linha com três campos independentes:

| Campo | Valores |
|---|---|
| **Implementado** | `sim` / `não` — o artefacto existe no repositório |
| **Verificado** | nível + evidência: `unitário — …`, `estático — …`, `integrado — …`, `não` |
| **Aceite no gate** | gate + estado da taxonomia do plano §1 (`Pendente`, `Em curso`, `Bloqueado`, `Concluído`, `Cortado`) + data/decisão quando ocorrer |

Regras: nenhum «Concluído» sem evidência arquivada. «Implementado» e «verificado
unitariamente» nunca implicam aceitação no gate. Definition of Done por
entregável (auditoria §14.1): artefacto existe + revisto + executado no ambiente
aplicável + evidência arquivada + matriz claim→evidência atualizada + decisão de
gate registada. Em 10/08/2026 continua a não existir nenhum gate fechado: todos
os campos «Aceite no gate» estão `Pendente` ou `Bloqueado`.

## Escala de maturidade M0–M5 (auditoria §2.3)

| Nível | Significado |
|---|---|
| M0 | Ausente — sem artefacto nem evidência |
| M1 | Preparado — documentação/configuração/código existem |
| M2 | Verificado localmente — validação sintática ou unitária persistida |
| M3 | Integrado — funciona com dependências reais no ambiente-alvo |
| M4 | Avaliado — evidência experimental reprodutível |
| M5 | Aceite — gate fechado e decisão registada |

O repositório está globalmente entre M1 e M2; o plano exige M3–M5 para a maioria
dos claims e gates.

## Estado por entregável

### Bloco 07–09/08 (G0 — decisão a 10/08)

| Entregável | Implementado | Verificado | Aceite no gate | M |
|---|---|---|---|---|
| Repositório Git inicializado e publicado | sim | estático — commits por entregável, working tree limpo; **remote privado ativo a 11/08** (`Ruisth/Tese_Mestrado`, privado, ruleset a exigir PR em `main` e `dev` e a proibir force-push); `refs/tags` continua vazio (tags reservadas a evidência real); a 10/08 a árvore de trabalho e os bundles de `backups/` passaram a residir fora da pasta sincronizada Nextcloud | G0 — Pendente | M2 |
| Contratos normativos (`src/CONTRACTS.md` v1.1) + schemas JSON | sim | unitário — `tests/test_schemas.py` (parte da suite selada de 618 testes); estático — 7 ficheiros JSON válidos; integração real não demonstrada | G2 — Pendente | M2 |
| Âmbito, RQs e matriz claim→evidência (15 claims) | sim | estático — 15/15 claims `Pendente — sem evidência`; sem validação dos orientadores | G0 — Pendente | M1 |
| Backlog e registo de riscos | sim | não (documentos de gestão) | G0 — Pendente | M1 |
| Guia WSL2 Ubuntu 24.04 (ext4) | sim | não — instalação não executada | G0 — Pendente | M1 |
| VM ARM64 (plataforma de medição) | não | não | G0 — **Bloqueado: indisponibilidade de mercado** (Oracle: home region fixa sem capacidade; Hetzner: CAX esgotadas; Azure Students: quota 0 em todas as famílias ARM dedicadas). Prazo 10/08 ultrapassado; regra §8.1: comunicar o risco até 12/08. Quota pedida (DPLSv5/v6); fallback AWS `c6g.xlarge` ~7 EUR | M0 |
| Email G0 aos orientadores + pedido das regras da extensão | sim (draft) | não — envio não efetuado | G0 — Bloqueado (envio é ação do estudante; prazo 09/08) | M1 |
| Quarentena de resultados sem evidência na dissertação | sim | estático — cap. 5 com 16 `\todo{pending data-v1}` e zero números; sem claims Pi/SSI | G0 — Pendente | M1 |

### Blocos G1–G7 — desenvolvimento antecipado sem VM/WSL

| Entregável | Implementado | Verificado | Aceite no gate | M |
|---|---|---|---|---|
| Manifesto `kas` + layer `meta-egw` + receita `egw-image` | sim | **integrado — imagem construida e DOIS boots QEMU registados a 11/08**: build de 5715 tarefas todas com sucesso; ambos os boots com 6 de 6 asserções obrigatórias e 3 observações registadas e poweroff limpo (systemd `running`, `multi-user.target` ativo, zero unidades falhadas, rede slirp, Docker 25.0.9, container importado e executado). Evidencia selada em `docs/evidence/g1-yocto-qemu/` com `SHA256SUMS`. 6 defeitos encontrados pela execucao real e corrigidos | **G1 — Em curso: evidencia produzida, aceitacao do gate PENDENTE** (decisao formal por registar; os 5 boots da campanha sao um conjunto posterior) | M3 |
| Compose ARM64 mínimo (Mosquitto TLS, Ditto 3.9.4, MongoDB, controlador) | sim | estático — `docker compose config` (validação sintática, sem log persistido); digests arm64 verificados documentalmente 07/08; `.env`/certificados/passwords operacionais não existem | G2 — Bloqueado (requer VM ARM; gate 23/08, trigger 25/08) | M1 |
| Controlador MQTT→Ditto | sim | unitário — testes com fakes (parte da suite selada de 618 testes); sem MQTT/Ditto reais, sem restart real, sem ARM64 | G2 — Pendente | M2 |
| Simulador unificado (3 wearables, 6 cenários) | sim | unitário — determinismo verificado; `dropout-reconnect` induz desconexão MQTT real com buffering e redelivery ordenado (correção da auditoria §7.3 concluída 08/08; cobre C10 em unitário) | G2–G3 — Pendente | M2 |
| Thing Descriptions WoT TD 1.1 | sim | unitário — `tests/test_things.py` cruza TD↔schema; integração real não demonstrada | G2–G3 — Pendente | M2 |
| Harness experimental + análise | sim | unitário — lacunas da auditoria §9 corrigidas a 08/08 (blocos P1a–P1c: gating por validade, proveniência de host, aceitação com completude, DoD do soak, caps de cadência, saturação com suficiência de evidência, raw selado write-once, batch runner `campaign`); bloco P5 (08/08) acrescentou marcador de fim de execução no domínio de relógio do controlador, hooks do collector no `campaign`, verificação de `SHA256SUMS` antes de qualquer agregação, completude por **identidade** contra o plano, validação semântica das séries e evidência limitada de recuperação no C12; bloco P5.4 (10/08) trata defeitos de alcance pela CLI e de valores não finitos (código fora deste bloco documental — ver `docs/g0/riscos.md`, R28/R29); **nenhuma regra estatística, percentil, método de IC ou a janela de 60 s foi alterada**; prova live pendente de VM | G4 — Pendente | M2 |
| Estrutura de evidência `experiments/results/` | sim | estático — diretórios `raw/processed/figures` criados; zero dados (evidência experimental M0) | G5 — Pendente | M1 |
| Dissertação (esqueleto + cap. 2 substantivo) | sim | estático — latexmk compila: 57 pp., 0 referências por resolver; cap. 2 ~4 300 palavras; claims prematuros removidos dos caps. 1/3/4/6 e da Tabela 2.1 (bloco P2); caps. 3/5/6 continuam esqueleto | G6 — Pendente | M1–M2 |
| Fontes da revisão (`thesis/research/study_selection.csv`) | sim | estático — 25 fontes registadas, com metadados verificados (Crossref/W3C/OASIS/páginas oficiais). **Profundidade de leitura: 7 avaliadas em full text (S001, S004–S009) e 18 apenas por título/resumo** (`stage=title_abstract`, inclusão provisória para o draft ao orientador; passagem full-text por executar). «Verificado» refere-se aos metadados da fonte, nunca à leitura integral; as queries institucionais continuam pendentes (ação do estudante, risco R17) | G6 — Pendente | M1 |
| PDF standalone do cap. 2 para o orientador | sim | estático — `thesis/latex/ch2_supervisor_draft.pdf` (16 pp., sem TODOs/placeholders, revisão institucional declarada pendente); inspeção visual página a página | não é item de gate — envio = ação do estudante (nenhum gate fecha com isto) | M2 |
| Suite de testes unitários | sim | unitário — **evidência selada: `701 passed`** sobre HEAD limpo `4e67717` em `docs/evidence/tests/2026-08-11-head-4e67717/`, com JUnit, stdout, ambiente, intérprete, `pip freeze`, `pip check`, versão do pytest, SHA-256 do lock e `SHA256SUMS`. Selagens anteriores mantidas para rasto (`683`, `618`, `593`, `515`). **Zero testes live/`integration` existem** — criá-los é pré-requisito de G3 | G3 — Pendente | M2 |
| Correções do harness pós-auditoria (fetch de eventos, 2 ambientes, collector na VM, janela medida, condições C10–C14, queue growth, CPU normalizada) | sim | unitário — testes incluídos na suite selada de 593; plano de campanha com 95 runs; a aceitação exige completude (por identidade contra o plano quando o plano é fornecido à análise) e evidência — incluindo evidência de recuperação real no C12; execução real pendente de VM | G3–G4 — Pendente | M2 |

Nota: «Implementado = sim» significa apenas que o artefacto existe e, quando
indicado, passou verificação unitária/estática neste repositório. Os gates
G1–G5 só fecham com evidência de execução real (build/boot QEMU, deploy ARM,
trace E2E, dados de campanha), que depende das ações externas abaixo.

## Estado dos gates a 10/08

Registo factual da situação na data de decisão do G0. **Nada aqui declara
um gate fechado nem falhado**: a decisão de gate pertence ao estudante e aos
orientadores e regista-se no Anexo C do plano e no [`LOG.md`](LOG.md).

- **G0 (data de decisão: 10/08) — data atingida, três ações externas por
  concluir.** Não existe no repositório evidência de nenhuma delas: (i) email G0
  aos orientadores — o draft existe em
  [`docs/g0/email_orientadores_G0.md`](docs/g0/email_orientadores_G0.md), sem
  registo de envio no LOG; (ii) WSL2 com Ubuntu 24.04 em ext4 — sem `wsl -l -v`
  nem `df -h` arquivados; (iii) VM ARM64 — sem `uname -a`/`lscpu`/`/etc/os-release`
  e sem manifesto de ambiente. São ações do estudante; nenhuma alteração no
  repositório as substitui.
- **Regras de corte do próprio plano (§8.1), transcritas sem interpretação:**
  sem VM a **10/08**, mudar de fornecedor; sem VM a **12/08**, comunicar o risco
  aos orientadores. A aplicação de qualquer destas regras é ação do estudante e
  fica registada no LOG quando ocorrer.
- **G1 (16/08, trigger 20/08) e G2 (23/08, trigger 25/08)** — sem alteração:
  zero builds Yocto, zero boots QEMU, zero deploys na VM. Dependem inteiramente
  de (ii) e (iii); `experiments/results/raw/` continua vazio.
- **G3–G7** — sem alteração; continuam a depender de evidência de execução real
  (e G3 exige, além disso, testes live/`integration`, que não existem).
- **O trabalho de repositório de 10/08 (blocos P5/P5.4) é correção de código e
  de documentação em M2**: aumenta a qualidade da instrumentação e da verdade
  documental e **não desbloqueia nem fecha gate nenhum**.

## Ações externas do estudante (com prazos)

| Ação | Prazo | Evidência esperada |
|---|---|---|
| Enviar o email G0 aos orientadores (draft em `docs/g0/email_orientadores_G0.md`) | 09/08 | email enviado; cópia e data no LOG |
| Pedir/confirmar regras administrativas da extensão (incluído no email G0) | 10/08 | pedido e resposta registados no LOG (plano §10) |
| Instalar Ubuntu 24.04 no WSL2 com diretório de build em ext4 (guia em `docs/setup/wsl2_ubuntu_yocto.md`) | 09–10/08 | `wsl -l -v`, `df -h` do diretório de build, log da instalação |
| Criar VM ARM64 e validar `uname -m` = `aarch64` (checklist em `docs/setup/vm_arm64_hetzner.md`) | 10/08 | `uname -a`, `lscpu`, `/etc/os-release` gravados no manifesto de ambiente |

Regra de corte G0 (plano §8.1): sem VM a 10/08, mudar de fornecedor; sem VM a
12/08, comunicar o risco aos orientadores.

## Plataformas — três degraus (extensão do ADR 0001, a validar com orientadores)

A indisponibilidade de ARM64 dedicado obrigou a distinguir uma plataforma de
integração de uma de medição. Regra dura: **nenhum número da série B entra na
dissertação.**

| Papel | Plataforma | Estado | Números na tese |
|---|---|---|---|
| Funcional (SO/boot) | QEMU `qemuarm64` no WSL2 | build em curso | Nunca (plano §5.1) |
| Integração ARM64 | Azure `B4pls_v2` (burstable, sem quota) | disponível, por usar | **Nunca** — créditos de CPU contaminariam o load-sweep e o critério de saturação |
| Medição (RQ3) | `D4pls_v5` (quota pedida) ou AWS `c6g.xlarge` | **inexistente** | **Exclusivamente daqui** |

## Controlo de esforço — caminho crítico (auditoria §5.2)

Esqueleto de controlo diário (<10 min/dia). Valores `(est.)` são estimativas da
auditoria §12.1; `actual_h`, `remaining_h` e `forecast` são preenchidos pelo
estudante — não inventar horas. Células vazias = por estimar/preencher.

> **Nota (08/08/2026, confirmada a 10/08/2026):** as colunas `actual_h`,
> `remaining_h` e `forecast` estão
> deliberadamente **vazias** e são de preenchimento exclusivo do estudante: são
> esforço humano e nenhum agente as pode estimar ou inferir. As durações do
> trabalho executado por agentes não entram nesta tabela — ficam registadas nas
> entradas do [`LOG.md`](LOG.md). Enquanto estas três colunas estiverem vazias,
> **não existe forecast de conclusão** e o risco RA15 mantém-se materializado
> (ver [`docs/g0/riscos.md`](docs/g0/riscos.md)).

| Item (caminho crítico) | owner | planned_h | actual_h | remaining_h | due | evidence | forecast | blocker |
|---|---|---|---|---|---|---|---|---|
| Email G0 + regras da extensão | Estudante | 0,5–1 (est.) | | | 09–10/08 | email + data no LOG | | |
| WSL2 Ubuntu 24.04 em ext4 | Estudante | 2–4 (est.) | | | 09–10/08 | outputs de versão e filesystem | | |
| VM ARM64 `aarch64` | Estudante | 1–2 (est.) | | | 10/08 | manifesto inicial arquivado | | conta/pagamento |
| Backup Git independente | Ambos | 0,5–1 (est.) | | | 09/08 | bundle/clone verificado fora do Nextcloud — repositório e bundles fora da pasta sincronizada desde 10/08; falta ainda o remote privado (opção mais forte) | | |
| Sprint de enquadramento teórico | Ambos | 18–24 (est.) | | | 10–11/08 | draft 4 000–5 000 palavras + logs de pesquisa preenchidos | | |
| Build Yocto + 2 boots QEMU | Estudante | | | | 16/08 (trigger 20/08) | log BitBake, `boot1/2.log`, `SHA256SUMS` | | WSL2 ext4 |
| Vertical slice E2E na VM | Ambos | | | | 23/08 (trigger 25/08) | trace `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` | | VM ARM |
| Correções do harness (R18–R22) | Agente | | | | antes de 06/09 | piloto válido sem intervenção ad hoc | | |
| Piloto completo + tag `exp-v1` | Ambos | | | | 06/09 | dados piloto em `raw/` com manifestos | | harness corrigido |
| Campanha oficial + `data-v1` | Ambos | | | | 13/09 18:00 | `raw/<run_id>/` completos + `SHA256SUMS` | | `exp-v1` |
| Draft integral aos orientadores | Ambos | | | | 18/09 | email de envio registado no LOG | | `data-v1` |
