# PROGRESS — fonte única de estado por entregável

> **Este ficheiro é a fonte única de estado do projeto.** O backlog
> ([`docs/g0/backlog.md`](docs/g0/backlog.md)) contém apenas ações, evidência
> esperada, dependências e regras de corte — não contém estado. O registo formal
> das decisões de gate vive no Anexo C do plano integrado; a coluna «Aceite no
> gate» abaixo espelha-o. Estrutura conforme a auditoria externa de 08/08/2026
> (§5.1, §5.2, §14).

Atualizado: 2026-08-08.

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
gate registada. Em 08/08/2026 nenhum gate está fechado: todos os campos «Aceite
no gate» estão `Pendente` ou `Bloqueado`.

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
| Repositório Git inicializado | sim | estático — commits por entregável (ordem de trabalhos 08/08), working tree limpo; sem remote nem tags | G0 — Pendente | M1 |
| Contratos normativos (`src/CONTRACTS.md` v1.1) + schemas JSON | sim | unitário — `tests/test_schemas.py` (parte dos 515 testes); estático — 7 ficheiros JSON válidos; integração real não demonstrada | G2 — Pendente | M2 |
| Âmbito, RQs e matriz claim→evidência (15 claims) | sim | estático — 15/15 claims `Pendente — sem evidência`; sem validação dos orientadores | G0 — Pendente | M1 |
| Backlog e registo de riscos | sim | não (documentos de gestão) | G0 — Pendente | M1 |
| Guia WSL2 Ubuntu 24.04 (ext4) | sim | não — instalação não executada | G0 — Pendente | M1 |
| VM ARM64 (Hetzner CAX21 ou equivalente) | não | não | G0 — Bloqueado (conta/pagamento do estudante; prazo 10/08) | M0 |
| Email G0 aos orientadores + pedido das regras da extensão | sim (draft) | não — envio não efetuado | G0 — Bloqueado (envio é ação do estudante; prazo 09/08) | M1 |
| Quarentena de resultados sem evidência na dissertação | sim | estático — cap. 5 com 16 `\todo{pending data-v1}` e zero números; sem claims Pi/SSI | G0 — Pendente | M1 |

### Blocos G1–G7 — desenvolvimento antecipado sem VM/WSL

| Entregável | Implementado | Verificado | Aceite no gate | M |
|---|---|---|---|---|
| Manifesto `kas` + layer `meta-egw` + receita `egw-image` | sim | estático — pins Scarthgap 5.0.19 documentados 07/08; zero builds, zero boots | G1 — Bloqueado (requer WSL2 ext4; gate 16/08, trigger 20/08) | M1 |
| Compose ARM64 mínimo (Mosquitto TLS, Ditto 3.9.4, MongoDB, controlador) | sim | estático — `docker compose config` (validação sintática, sem log persistido); digests arm64 verificados documentalmente 07/08; `.env`/certificados/passwords operacionais não existem | G2 — Bloqueado (requer VM ARM; gate 23/08, trigger 25/08) | M1 |
| Controlador MQTT→Ditto | sim | unitário — testes com fakes (parte dos 515 testes); sem MQTT/Ditto reais, sem restart real, sem ARM64 | G2 — Pendente | M2 |
| Simulador unificado (3 wearables, 6 cenários) | sim | unitário — determinismo verificado; `dropout-reconnect` induz desconexão MQTT real com buffering e redelivery ordenado (correção da auditoria §7.3 concluída 08/08; cobre C10 em unitário) | G2–G3 — Pendente | M2 |
| Thing Descriptions WoT TD 1.1 | sim | unitário — `tests/test_things.py` cruza TD↔schema; integração real não demonstrada | G2–G3 — Pendente | M2 |
| Harness experimental + análise | sim | unitário — lacunas da auditoria §9 corrigidas a 08/08 (blocos P1a–P1c: gating por validade, proveniência de host, aceitação com completude, DoD do soak, caps de cadência, saturação com suficiência de evidência, raw selado write-once, batch runner `campaign`); prova live pendente de VM | G4 — Pendente | M2 |
| Estrutura de evidência `experiments/results/` | sim | estático — diretórios `raw/processed/figures` criados; zero dados (evidência experimental M0) | G5 — Pendente | M1 |
| Dissertação (esqueleto + cap. 2 substantivo) | sim | estático — latexmk compila: 57 pp., 0 referências por resolver; cap. 2 ~4 300 palavras; claims prematuros removidos dos caps. 1/3/4/6 e da Tabela 2.1 (bloco P2); caps. 3/5/6 continuam esqueleto | G6 — Pendente | M1–M2 |
| Fontes da revisão (`thesis/research/study_selection.csv`) | sim | estático — 25 fontes registadas, com metadados verificados (Crossref/W3C/OASIS/páginas oficiais). **Profundidade de leitura: 7 avaliadas em full text (S001, S004–S009) e 18 apenas por título/resumo** (`stage=title_abstract`, inclusão provisória para o draft ao orientador; passagem full-text por executar). «Verificado» refere-se aos metadados da fonte, nunca à leitura integral; as queries institucionais continuam pendentes (ação do estudante, risco R17) | G6 — Pendente | M1 |
| PDF standalone do cap. 2 para o orientador | sim | estático — `thesis/latex/ch2_supervisor_draft.pdf` (16 pp., sem TODOs/placeholders, revisão institucional declarada pendente); inspeção visual página a página | não é item de gate — envio = ação do estudante (nenhum gate fecha com isto) | M2 |
| Suite de testes unitários | sim | unitário — 515 testes a passar (Windows, Python 3.14.3, venv); evidência selada em `docs/evidence/tests/2026-08-08-head-ca445a3/` (JUnit + stdout + ambiente + commit + `SHA256SUMS`) sobre HEAD limpo `ca445a3`; **zero testes live/`integration` existem**, sem execução Linux nem ARM64 — criá-los é pré-requisito de G3 | G3 — Pendente | M2 |
| Correções do harness pós-auditoria (fetch de eventos, 2 ambientes, collector na VM, janela medida, condições C10–C14, queue growth, CPU normalizada) | sim | unitário — testes incluídos nos 515; plano de campanha com 95 runs; aceitação exige completude e evidência; execução real pendente de VM | G3–G4 — Pendente | M2 |

Nota: «Implementado = sim» significa apenas que o artefacto existe e, quando
indicado, passou verificação unitária/estática neste repositório. Os gates
G1–G5 só fecham com evidência de execução real (build/boot QEMU, deploy ARM,
trace E2E, dados de campanha), que depende das ações externas abaixo.

## Ações externas do estudante (com prazos)

| Ação | Prazo | Evidência esperada |
|---|---|---|
| Enviar o email G0 aos orientadores (draft em `docs/g0/email_orientadores_G0.md`) | 09/08 | email enviado; cópia e data no LOG |
| Pedir/confirmar regras administrativas da extensão (incluído no email G0) | 10/08 | pedido e resposta registados no LOG (plano §10) |
| Instalar Ubuntu 24.04 no WSL2 com diretório de build em ext4 (guia em `docs/setup/wsl2_ubuntu_yocto.md`) | 09–10/08 | `wsl -l -v`, `df -h` do diretório de build, log da instalação |
| Criar VM ARM64 e validar `uname -m` = `aarch64` (checklist em `docs/setup/vm_arm64_hetzner.md`) | 10/08 | `uname -a`, `lscpu`, `/etc/os-release` gravados no manifesto de ambiente |

Regra de corte G0 (plano §8.1): sem VM a 10/08, mudar de fornecedor; sem VM a
12/08, comunicar o risco aos orientadores.

## Controlo de esforço — caminho crítico (auditoria §5.2)

Esqueleto de controlo diário (<10 min/dia). Valores `(est.)` são estimativas da
auditoria §12.1; `actual_h`, `remaining_h` e `forecast` são preenchidos pelo
estudante — não inventar horas. Células vazias = por estimar/preencher.

> **Nota (08/08/2026):** as colunas `actual_h`, `remaining_h` e `forecast` estão
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
| Backup Git independente | Ambos | 0,5–1 (est.) | | | 09/08 | bundle/clone verificado fora do Nextcloud | | |
| Sprint de enquadramento teórico | Ambos | 18–24 (est.) | | | 10–11/08 | draft 4 000–5 000 palavras + logs de pesquisa preenchidos | | |
| Build Yocto + 2 boots QEMU | Estudante | | | | 16/08 (trigger 20/08) | log BitBake, `boot1/2.log`, `SHA256SUMS` | | WSL2 ext4 |
| Vertical slice E2E na VM | Ambos | | | | 23/08 (trigger 25/08) | trace `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` | | VM ARM |
| Correções do harness (R18–R22) | Agente | | | | antes de 06/09 | piloto válido sem intervenção ad hoc | | |
| Piloto completo + tag `exp-v1` | Ambos | | | | 06/09 | dados piloto em `raw/` com manifestos | | harness corrigido |
| Campanha oficial + `data-v1` | Ambos | | | | 13/09 18:00 | `raw/<run_id>/` completos + `SHA256SUMS` | | `exp-v1` |
| Draft integral aos orientadores | Ambos | | | | 18/09 | email de envio registado no LOG | | `data-v1` |
