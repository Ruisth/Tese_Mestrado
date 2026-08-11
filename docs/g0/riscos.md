# Registo de riscos

> Base: tabela do plano integrado §11 (R1–R8, conteúdo dos campos Risco/Sinal/
> Mitigação transcrito do plano sem alteração) + riscos operacionais adicionais
> deste repositório (R9–R15) + riscos da auditoria externa de 08/08/2026 §11
> (R16–R27, adaptados à situação real do repositório) + riscos da reanálise
> externa pós-correções de 08/08/2026 §11 (RA1–RA15, seguidos linha a linha na
> secção própria) + riscos da auditoria técnica de 10/08/2026 (R28–R29, classe
> nova: correção que existe mas não é alcançada ou é contornada em silêncio).
> Colunas de controlo (Probabilidade, Impacto, Owner, Estado,
> Prazo de mitigação) acrescentadas a todos os riscos conforme a auditoria §5.4.
> Rever a cada fecho de gate e sempre que um sinal antecipado for observado;
> registar ativações no LOG.
>
> Owner: `Estudante` (ações externas ao repositório), `Agente` (alterações no
> repositório), `Ambos`. Estado: `Aberto`, `Em mitigação`, `Parcialmente
> mitigado`, `Mitigado`, `Materializado`, `Fechado`. Probabilidade/Impacto de
> R16–R27: valores da auditoria; de R1–R15: avaliação de 08/08 e de R28–R29:
> avaliação de 10/08 (a rever com os orientadores).
>
> `Mitigado em M2` significa **apenas** que a correção existe no repositório e
> está coberta por testes unitários com fakes em Windows. Não é prova live, não
> fecha gate nenhum e não valida claim nenhum.

Atualizado: 2026-08-10 (bloco P5.4: R9 e R25 revistos após a saída do workspace
do domínio Nextcloud; R24 realinhado com a suite selada; RA5–RA8, RA11, RA13 e
RA14 revistos à luz das correções P5/P5.4; RA15 mantém-se **materializado**;
nova classe de risco R28–R29 da auditoria técnica de 10/08).

## Riscos do plano (§11)

| ID | Risco | Prob. | Impacto | Owner | Estado | Prazo mitigação | Sinal antecipado | Mitigação/decisão |
|---|---|---|---|---|---|---|---|---|
| R1 | Falta de hardware Raspberry Pi | Alta | Baixo (âmbito já exclui Pi físico) | Ambos | Mitigado por desenho | — | Hardware continua indisponível | QEMU funcional + VM ARM nativa; excluir alegações de hardware físico |
| R2 | Build Yocto lento ou instável | Média | Alto | Ambos | Aberto | 16/08 (trigger 20/08) | G1 em risco | WSL2 em filesystem Linux, revisions fixadas, imagem mínima e cache de downloads |
| R3 | Imagens sem ARM64 | Baixa | Alto | Ambos | Em mitigação (digests verificados documentalmente 07/08; falta `manifest inspect` na VM) | 23/08 | Falha no `manifest inspect` | Substituir por imagem oficial compatível; ACA-Py é cortado, nunca emulado |
| R4 | Ditto excede recursos | Média | Alto | Estudante | Aberto | 23/08 | OOM ou swap persistente | VM mínima de 8 GiB, limites medidos e serviços não essenciais removidos |
| R5 | Âmbito volta a crescer | Média | Alto | Ambos | Em mitigação (auditoria §15: sem scope creep detetado) | contínuo | Pedido sem ligação às RQs | Aplicar P0/P1/out-of-scope e exigir troca explícita de horas |
| R6 | Resultados sem proveniência | Média | Crítico | Agente | Em mitigação (manifestos/checksums implementados; por exercitar no piloto) | 06/09 (antes de `exp-v1`) | Métrica sem `run_id`/manifesto | Invalidar a execução e repeti-la antes do data freeze |
| R7 | Feedback tardio | Média | Alto | Estudante | Aberto | marcos §8.2 (10/08, 17/08, 31/08, 07/09, 18/09, 23/09) | Sem resposta nos marcos | Entregar capítulos cedo e continuar com as decisões documentadas |
| R8 | Escrita fica para o fim | Alta | Crítico | Ambos | Aberto (auditoria §6: 18–22% do alvo em 08/08) | 06/09 (caps 1–4) e 18/09 (draft) | Capítulos 1–4 incompletos em 06/09 | Reserva diária de escrita e corte imediato de P1 |

## Riscos operacionais adicionais

| ID | Risco | Prob. | Impacto | Owner | Estado | Prazo mitigação | Sinal antecipado | Mitigação/decisão |
|---|---|---|---|---|---|---|---|---|
| R9 | Workspace em Nextcloud/NTFS: builds, ambientes virtuais ou repositórios Git corrompidos/lentos por sincronização e semântica de ficheiros NTFS | Média | Alto | Estudante | Parcialmente mitigado (10/08: o workspace saiu da pasta sincronizada Nextcloud, o que elimina a componente de sincronização; permanece em NTFS/Windows, pelo que a regra de nunca construir aqui mantém-se integralmente) | contínuo (antes do 1.º build) | Conflitos de sincronização (`... (conflicted copy)`), locks de ficheiros, I/O lento, builds a falhar de forma não determinística | Nunca fazer builds Yocto nem correr a stack a partir de `/mnt/d`/Nextcloud (plano §5.1); builds e venvs em WSL2 ext4 ou na VM; copiar apenas resultados finais para o workspace; pausar a sincronização durante operações de I/O intensivo; `SHA256SUMS` para detetar corrupção |
| R10 | VM ARM64 não disponível a 10/08 (conta, pagamento, capacidade do fornecedor na região) | Média | Crítico | Estudante | Aberto | 10/08 (escalar 12/08) | Criação da VM ainda pendente em 09/08; região sem capacidade CAX | Aplicar a regra do G0 (§8.1): a 10/08 sem VM, mudar de fornecedor/região; a 12/08, comunicar risco aos orientadores; checklist pronta em [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md) para minimizar o tempo de setup |
| R11 | Divergência de versões de Python: host Windows com 3.14, containers/CI previstos com 3.12, `pyproject` exige >=3.11 | Média | Médio | Agente | Em mitigação | 16/08 (testes em Linux antes de G1) | Testes passam num ambiente e falham noutro; dependências sem wheels para a versão do host; warnings de depreciação diferentes | O ambiente de referência para testes e execução é Linux (WSL2/VM) com a versão do Python fixada no `Dockerfile`; não validar comportamento apenas no Python do host Windows; correr `pytest` no mesmo interpretador do container antes de declarar verde |
| R12 | Espaço em disco/memória insuficiente no host para o build Yocto em WSL2 | Média | Alto | Estudante | Aberto | 09–10/08 (antes do 1.º build) | `df -h` abaixo de ~120 GB livres antes do build; pressão de memória/OOM no WSL durante o BitBake | Verificar espaço antes do primeiro build (guia §disk sizing); limpar `tmp/` entre builds se necessário mantendo `downloads/` e `sstate-cache`; configurar `.wslconfig` (memória/swap) antes do G1 |
| R13 | Variabilidade de desempenho da VM cloud com vCPU partilhada (CAX21) contamina as medições | Alta | Médio | Ambos | Em mitigação (mitigação metodológica definida no plano §7.3) | 06/09 (fechar antes de `exp-v1`) | `steal time` elevado em `top`/`vmstat`; dispersão anómala entre execuções repetidas | Registar a limitação no manifesto de ambiente (plano §5.1); unidade estatística = execução com repetições (§7.3); reportar dispersão (desvio-padrão/IC95%); excluir apenas falhas comprovadas da cloud, nunca execuções lentas pelo resultado |
| R14 | Indisponibilidade dos orientadores em agosto (período de férias) atrasa o fecho do âmbito no G0 | Alta | Alto | Estudante | Aberto | 12/08 (escalar 17/08) | Sem resposta ao email de G0 até 12/08 | Enviar o email cedo com pedido de validação assíncrona; prosseguir com o âmbito documentado (§8.1 G7 aplica o mesmo princípio); registar tentativas de contacto no LOG; escalar no marco de 17/08 |
| R15 | Perda ou adulteração de dados brutos antes do arquivo (falha de disco, sync, engano humano) | Média | Crítico | Ambos | Em mitigação (`SHA256SUMS` por run implementado no harness; arquivo externo por executar) | 07/09 (antes da campanha oficial) | Checksums a falhar; ficheiros modificados após a recolha | `SHA256SUMS` por `run_id` gerados no fim de cada execução; `raw/` tratado como imutável desde a recolha (não apenas no freeze); cópia para arquivo versionado fora do Nextcloud logo após cada sessão de campanha |

## Riscos da auditoria externa (08/08/2026, §11) — R16–R27

Nota de 08/08, atualizada a 10/08 (blocos P1a–P1c, P2, P5 e P5.4): R18, R19, R20
e R22 foram corrigidos em M2 (prova live pendente); R21 continua em mitigação
enquanto não existir um único teste `integration`; R24 mantém-se em mitigação
(o lock de runtime ARM64 só nasce na VM); R25 passou a **mitigado** com a saída
do repositório e dos bundles do domínio Nextcloud a 10/08; R26 teve a
sincronização diagramas/cap. 4 concluída e checklist adicionada. Os estados
`Mitigado em M2` só passam a `Mitigado` com evidência de execução real
arquivada.

| ID | Risco | Prob. | Impacto | Owner | Estado | Prazo mitigação | Sinal antecipado | Mitigação/decisão |
|---|---|---|---|---|---|---|---|---|
| R16 | Enquadramento teórico não desbloqueia o orientador (cap. 2 com ~1 034 palavras para meta de 6 000–7 000) | Alta | Crítico | Ambos | Mitigado — draft standalone pronto a 08/08; envio pendente (estudante) | 10–11/08 | Sem draft enviável em 11/08 | Sprint imediato de teoria (auditoria §6.6/§12.2); suspender features novas até ao envio ao orientador |
| R17 | Claim de novidade sem pesquisa registada (`search_log.csv` e `study_selection.csv` só com cabeçalhos) | Alta | Alto | Ambos | Parcialmente mitigado — logs preliminares preenchidos com proveniência honesta; queries institucionais pendentes (estudante) | 11/08 (antes do envio ao orientador) | Texto enviado com CSVs vazios | Executar o protocolo de revisão e registar queries/decisões reais, ou limitar o claim às fontes efetivamente examinadas; nunca fabricar entradas de pesquisa |
| R18 | Recursos medidos no host errado (`docker stats` corre no Docker local do host do harness por defeito) | Alta | Crítico | Agente | Mitigado em M2 a 08/08 — collector na VM, dois manifestos, proveniência de host obrigatória; prova live pendente | antes de G4 (06/09) | Piloto sem identificação inequívoca da VM | Collector na VM ou canal remoto explícito e registado + dois manifestos (`sut_environment` na VM, `loadgen_environment` no host do simulador) |
| R19 | `events.jsonl` não recolhido pelo runner (transferência manual `scp` incompatível com o fluxo síncrono; run marcado como falhado) | Alta | Crítico | Agente | Mitigado em M2 a 08/08 — fetch automático com retries + subcomando `collect` | antes de G4 (06/09) | Primeiro piloto falha por ficheiro ausente | Automatizar a fase de recolha antes do piloto; sem intervenção ad hoc por run |
| R20 | Condições obrigatórias ausentes do plano de campanha (10 smokes, `invalid-payload`, reconnect real, restart) — claims C10–C14 sem percurso | Alta | Alto | Agente | Mitigado em M2 a 08/08 — plano de 95 runs com C10–C14 e aceitação com completude obrigatória | antes do piloto (30/08–06/09) | Campaign plan sem C10–C14 | Matriz condição→claim antes do piloto; acrescentar as condições em falta ao gerador de plano |
| R21 | Testes unitários confundidos com integração (marker `integration` registado mas sem uso; sem testes live) | Alta | Alto | Agente | Em mitigação — marker e política de evidência corrigidos a 08/08 | G3 (30/08) | Gate declarado apenas com fakes | Definition of Done por nível (auditoria §8.4) e relatório de testes persistente; criar testes live de integração/E2E antes de G3 |
| R22 | Warm-up contamina métricas de recursos (sampler abrange warm-up + execução; análise não filtra a janela medida) | Alta | Alto | Agente | Mitigado em M2 a 08/08 — janela medida no manifesto, filtro na análise e caps de cadência | antes de G4 (06/09) | `resources.csv` inclui período pré-medição | Registar `measured_started_utc` no manifesto e filtrar a janela medida na análise |
| R23 | Critério de saturação muda depois do freeze (queue growth `TODO`; CPU sem normalização por nº de CPUs; regra «metade dos runs» não validada) | Média/Alta | Alto | Ambos | Aberto | antes de `exp-v1` (06/09) | Regra de queue growth/CPU sem decisão em G3 | Fechar métrica e regra com o orientador antes do freeze; instrumentar queue depth ou remover o critério por decisão formal registada |
| R24 | Dependências Python mudam entre builds (`>=` em `pyproject.toml`, sem lockfile com hashes) | Média | Alto | Agente | Em mitigação — lock de desenvolvimento criado a 08/08; lock de runtime com hashes antes de `exp-v1` | 06/09 | Novo build resolve versões diferentes | Lockfile com versões/hashes antes de `exp-v1`; não afirmar «rebuild reproduzível» até lá |
| R25 | Perda do repositório local (zero remotes, zero tags, workspace em Nextcloud) | Média | Crítico | Ambos | **Mitigado** — a 10/08 o repositório e os bundles de `backups/` foram copiados para fora da pasta sincronizada Nextcloud, para uma localização privada; a condição «bundle no mesmo domínio de sincronização» deixou de se verificar. **Continua sem remote e sem tags** (`.git/config` sem `[remote]`, `refs/tags` vazio) e a cópia vive no mesmo disco físico do trabalho: o **remote privado continua a ser a opção mais forte** e o único que sobrevive a falha de disco | remote privado antes de `exp-v1` (06/09) | Repositório e bundle no mesmo suporte físico; ausência de remote | Remote privado (opção preferida) ou bundle Git verificado fora do Nextcloud (feito); tags reservadas para evidência real (`g1`, `g2`, `exp-v1`, `data-v1`, `rc1`), nunca antecipadas |
| R26 | Documentação diverge do contrato (deriva pós-CONTRACTS v1.1: referências a v1.0, idempotência sem âmbito por `run_id`) | Alta | Médio/Alto | Agente | Em mitigação — sincronização diagramas/cap. 4 concluída a 08/08; checklist de impacto adicionada | contínuo (a cada alteração de contrato) | CONTRACTS muda sem atualização de tese/diagramas/READMEs | Checklist de impacto por ADR/alteração de contrato; verificação de drift duas vezes por semana (auditoria §14.2) |
| R27 | Estado de gestão induz falsa confiança (PROGRESS/backlog/plano contraditórios; estados híbridos fora da taxonomia) | Alta | Alto | Agente | Em mitigação — PROGRESS reestruturado como fonte única a 08/08; backlog sem estado; a 10/08 (P5.4) foi corrigida nova deriva: PROGRESS apontava para a evidência selada anterior (`515`/`ca445a3`) e o backlog repetia essa métrica e afirmava CSVs de pesquisa vazios que já não estavam vazios | revisão a cada bloco de trabalho e a cada gate | Documentos de estado divergentes | Fonte única de estado em `PROGRESS.md` (modelo Implementado/Verificado/Aceite); backlog só com ações; controlo diário de esforço (<10 min) |

## Riscos da reanálise externa pós-correções (08/08/2026, §11) — RA1–RA15

A verificação externa de 08/08 assinalou que a afirmação anterior deste ficheiro
(«RA1–RA15 mapeados») era **demasiado ampla**: vários RA estavam apenas
implícitos nas linhas R16–R27 e um deles já se tinha materializado. Essa
afirmação foi retirada. A tabela seguinte segue os quinze riscos **um a um**,
com estado explícito e, em cada linha, ou a evidência concreta no repositório ou
a dependência que bloqueia o fecho. O enunciado da coluna «Risco» é o da
reanálise §11, sem reescrita.

Leitura obrigatória desta tabela: `Mitigado em M2` = correção presente no código
e coberta por testes unitários com fakes em Windows — **sem prova live, sem
gate fechado, sem claim validado**. `Ação do estudante` = nenhuma alteração no
repositório fecha o risco.

| RA | Risco (reanálise §11) | Owner | Estado | Evidência concreta ou dependência bloqueante |
|---|---|---|---|---|
| RA1 | Email/regras/VM/WSL2 atrasam G0–G2 | Estudante | **Aberto — ação do estudante** | Dependência bloqueante: email G0 por enviar, WSL2 Ubuntu 24.04 em ext4 por instalar e VM ARM64 por criar (linhas «G0 — Bloqueado» em [`../../PROGRESS.md`](../../PROGRESS.md)). Sobrepõe-se a R10 e R14; nenhuma ação do agente o fecha |
| RA2 | Claim académico de protocolo executado permanece no capítulo 1 | Agente | **Mitigado** (documental) | «pre-registered» substituído por «pre-specified, frozen before data collection» nos caps. 1/2/6 e nos abstracts (bloco P2); `grep -r "pre-registered" thesis/latex/` sem ocorrências em 10/08. O cap. 5 mantém-se sem números, com `\todo{pending data-v1}` |
| RA3 | PDF completo enviado com placeholders e TODOs | Estudante | **Parcialmente mitigado** | Existe o extrato standalone `thesis/latex/ch2_supervisor_draft.tex` (+ PDF compilado), precisamente para evitar enviar o `main.pdf` com placeholders. Dependência bloqueante: o envio ao orientador é ação do estudante e ainda não ocorreu |
| RA4 | «Verified sources» interpretado como leitura integral | Agente | **Mitigado** (documental) | [`../../PROGRESS.md`](../../PROGRESS.md) declara agora 7 fontes em full text (S001, S004–S009) e 18 só por título/resumo; contagem lida da coluna `stage` de `thesis/research/study_selection.csv` (7 `full_text`, 18 `title_abstract`). «Verificado» passou a referir-se apenas aos metadados da fonte. Não cobre R17 (queries institucionais), que continua com o estudante |
| RA5 | Runs inválidos entram nos resultados | Agente | **Mitigado em M2** | `src/egw_experiments/analyze.py` exclui da agregação os runs cujo `validity` do manifesto exista e não seja `valid`; a exclusão exige causa comprovada (cloud/instrumentação/configuração) e nunca o resultado da execução. Reforçado no bloco P5: o `SHA256SUMS` do diretório é verificado **antes** de qualquer agregação (coluna `integrity_ok` em `per_run.csv`) e tanto os runs com falha de integridade como os runs **não selados** de condições cronometradas ficam fora de sumários, saturação, aceitação e figuras, com aviso explícito. Limite conhecido tratado no bloco P5.4: este gate decide sobre o run, não sobre a sanidade numérica de cada amostra — ver R29. Prova live pendente de VM |
| RA6 | Recursos locais tratados como recursos ARM | Agente | **Mitigado em M2** | Coluna de proveniência de host obrigatória em `resources.csv`; recolha do SUT por `src/deployment/scripts/collect-resources.sh` na VM ingerida por `run --resources-from`; o amostrador local é opt-in (`--local-resources`) e fica marcado com `resource_source` (`local-dev` invalida um run cronometrado). O bloco P5 acrescentou validação semântica das séries no momento da análise (linhas inutilizáveis descartadas e **contadas** por motivo: coluna em falta, campo vazio, timestamp ilegível, valor não numérico, tempo a recuar), visível em `resources_rows_dropped`/`metrics_rows_dropped`. Equivale a R18; prova live pendente |
| RA7 | C10–C13 passam sem completude | Agente | **Mitigado em M2** | `processed/acceptance_by_condition.csv` avalia **todas** as condições planeadas com gate de completude explícito (`runs_complete`); uma condição planeada com zero runs válidos não passa. O bloco P5 substituiu a contagem por comparação do **conjunto de identidades** (`run_id` + repetição + seed + taxa, por nível de carga no sweep) contra o plano congelado, quando o plano é fornecido à análise. A alçada desta garantia depende de o plano chegar mesmo à análise pelo comando entregue — foi essa a lacuna encontrada a 10/08 e registada em R28. Prova live pendente |
| RA8 | Queue/CPU com gaps geram falso sustained | Agente | **Mitigado em M2** | Os detetores de janela sustentada só contam intervalos entre amostras consecutivas dentro do gap máximo admitido; cada run reporta `resources_coverage_pct`/`metrics_coverage_pct` em `per_run.csv`; o bloco P5 acrescentou o *head gap* (série que só começa a amostrar já dentro da janela não é evidência contínua), a contagem de **instantes distintos** dentro da janela medida e um mínimo abaixo do qual o critério falha em vez de passar em silêncio. Os limiares estatísticos, os percentis, o método de IC e a janela de 60 s **não** foram alterados em nenhum destes blocos — mudou apenas a instrumentação. Dependência residual: séries com valores não finitos (R29) atacam exatamente estes cálculos |
| RA9 | Raw resources sobrescritos | Agente | **Mitigado em M2** | Diretórios `raw/<run_id>/` são write-once: com `SHA256SUMS` presente o diretório fica selado e qualquer escrita com conteúdo diferente é recusada (`run.py`) |
| RA10 | Campanha manual falha na ordem ou completude | Agente | **Mitigado em M2** | Subcomando `campaign` (`src/egw_experiments/campaign.py`): executa o plano congelado pela ordem, com resume, classificação `blocked` para diretórios não selados, cooldowns registados e `campaign_log.jsonl`. Prova live pendente |
| RA11 | Evidência 452 não reproduzível por commit | Agente | **Fechado** | O padrão está estabelecido e repetido: cada bloco re-executa a suite em HEAD limpo e sela a evidência num diretório próprio identificado pelo commit. Existem duas selagens verificáveis — `docs/evidence/tests/2026-08-08-head-ca445a3/` (`515 passed`, commit `ca445a31e5d146cf0c214b3cd4a23a95a48b5289`, tree `b767b229e295b9453cbc2efcbfd0122bf8409d38`) e `docs/evidence/tests/2026-08-08-head-57228e1/` (`593 passed`, commit `57228e178c784987492ca71a708740a5a85d0d95`, tree `e3e4fc84546662a7ecc650dbfd79596e48dab6a3`, execução datada de 2026-08-10T21:22:25Z) — ambas com `git status --porcelain` vazio e `SHA256SUMS` dos três ficheiros. Nota de higiene, sem impacto na reprodutibilidade: o prefixo `2026-08-08` do segundo diretório é o do bloco e não a data da execução |
| RA12 | Lock dev confundido com lock runtime | Ambos | **Parcialmente mitigado** | O cabeçalho de `src/requirements.lock` identifica-o como lock de **desenvolvimento**, sem hashes, gerado no venv Windows, e nomeia a suite selada de 593 testes contra a qual foi verificado. Dependência bloqueante: o lock de runtime ARM64 com hashes tem de ser gerado no build da imagem na VM e arquivado antes de `exp-v1`; até lá é proibido afirmar «rebuild reproduzível». Equivale a R24 |
| RA13 | Bundle perdido no mesmo domínio Nextcloud | Estudante | **Mitigado** | A 10/08 o estudante copiou o conjunto (repositório de trabalho e bundles de `backups/`, incluindo `egw-20260808-final.bundle` e `egw-20260808-p5.bundle`) para fora da pasta sincronizada Nextcloud, para uma localização privada: a condição do risco — evidência de backup dentro do mesmo domínio de sincronização — deixou de se verificar. **Continua a ser preferível um remote Git privado**: a cópia atual partilha o disco físico com o trabalho e não sobrevive a falha desse disco, e o repositório mantém-se sem remote e sem tags. Equivale a R25 |
| RA14 | Documentos de estado voltam a divergir | Agente | **Parcialmente mitigado** | `PROGRESS.md` é fonte única de estado; o bloco P5.3 corrigiu a primeira deriva (run_id reais na matriz claim→evidência, `diagrams/README.md` em CONTRACTS v1.1, `src/README.md` sem sugerir testes live, LOG #C006 com os identificadores exatos) e o bloco P5.4 corrigiu a segunda, do mesmo tipo: PROGRESS e `src/requirements.lock` apontavam para a selagem anterior (`515`/`ca445a3`) depois de existir uma selagem mais recente, e o backlog afirmava que os CSVs de pesquisa só tinham cabeçalhos quando já continham 25 fontes e 3 pesquisas registadas. **O risco reincidiu duas vezes em três dias**, sempre a seguir a um bloco que produziu evidência nova. Dependência bloqueante: a revisão transversal ainda não é rotina com registo próprio — a regra operacional passa a ser «quem sela evidência nova atualiza, no mesmo bloco, PROGRESS, o cabeçalho do lock e a matriz». Equivale a R27 |
| RA15 | Forecast irreal por ausência de horas | **Estudante** | **MATERIALIZADO** | O risco já ocorreu: `actual_h`, `remaining_h` e `forecast` estão vazios na tabela de controlo de esforço de [`../../PROGRESS.md`](../../PROGRESS.md), pelo que **não existe forecast de conclusão** e as datas de setembro não têm suporte quantitativo. São horas humanas: nenhum agente as pode estimar, inferir ou preencher — inventá-las seria fabricar dados. As durações do trabalho dos agentes ficam no `LOG.md` e **não** substituem estas colunas. Fecho exclusivo do estudante, no controlo diário de <10 min |

Só o estudante pode alterar o estado de RA1, RA3 e RA15; RA12 exige a VM. RA13
saiu desta lista a 10/08 por ação do próprio estudante. Os estados
`Mitigado em M2` (RA5–RA10) passam a `Mitigado` com prova live apenas depois de
G3/G4, com evidência arquivada.

## Riscos da auditoria técnica (10/08/2026) — R28–R29

A ronda de auditoria de 10/08 revelou uma **classe de risco nova**, distinta das
anteriores: as anteriores eram sobre o que **falta**; estas são sobre correções
que **existem no repositório e mesmo assim não produzem o efeito prometido** —
porque o caminho realmente entregue ao operador não passa por elas, ou porque
uma entrada patológica as contorna sem erro. Um risco desta classe é
particularmente perigoso porque a documentação, os testes da função isolada e a
leitura do código dizem todos que a proteção existe.

Ambos os defeitos abaixo foram endereçados no bloco P5.4 (código do harness,
fora do âmbito deste ficheiro). **Este registo não os declara fechados:** o
estado de cada correção lê-se na evidência selada de 10/08 e na entrada P5.4 do
[`../../LOG.md`](../../LOG.md), e o item de verificação permanente no fim desta
secção mantém-se **aberto até `exp-v1`**.

| ID | Risco | Prob. | Impacto | Owner | Estado | Prazo mitigação | Sinal antecipado | Mitigação/decisão |
|---|---|---|---|---|---|---|---|---|
| R28 | Implementação existe mas é inalcançável pela CLI entregue, ou degrada em silêncio (defeito `--plan`): a completude por **identidade** contra o plano congelado só era exercida quando o plano era passado programaticamente a `analyze(plan_path=...)` ou pela variável de ambiente; o subcomando `analyze` da CLI não expunha `--plan` e não o passava, pelo que o comando documentado como oficial degradava para a verificação **por contagem** sem erro nem falha visível | Alta | Crítico | Agente | Endereçado no bloco P5.4 (10/08) — verificação permanente ativa até `exp-v1` | antes de `exp-v1` (06/09) | Uma proteção descrita na documentação cujo teste exercita a função Python e nunca o comando entregue; opção que só existe como parâmetro de API ou variável de ambiente | Todo o caminho de garantia tem de ser alcançável pelo comando tal como é entregue e, quando a garantia não puder ser aplicada, o comando tem de o **dizer em voz alta** em vez de degradar em silêncio; os testes exercitam o `main()`/CLI, não apenas a função interna |
| R29 | Valores não finitos ou não numéricos (NaN, ±Inf, campos de texto) nas séries e nos `timings.json` fazem a análise falhar ou — pior — enviesam-na sem falhar: um NaN contamina médias e percentis e desordena comparações, um campo não numérico levanta exceção a meio da agregação | Alta | Crítico | Agente | Endereçado no bloco P5.4 (10/08) — verificação permanente ativa até `exp-v1` | antes de `exp-v1` (06/09) | Estatística de campanha com resultado `nan`, ordenação de percentis inconsistente, ou exceção de conversão numérica durante a análise | Sanidade numérica no ingresso: valores não finitos e não convertíveis são recusados e **contados** como amostra descartada (com motivo), nunca aceites em silêncio, exatamente como as restantes validações semânticas das séries; regras estatísticas, percentis, método de IC e janela de 60 s permanecem inalterados |

**Item de verificação permanente antes de `exp-v1` (não fecha com um commit).**
Para cada proteção do harness que a documentação, o PROGRESS ou a matriz
claim→evidência invoquem: (a) exercitá-la pelo **comando entregue**, com os
argumentos por omissão, e não apenas pela função Python; (b) confirmar que, na
ausência das condições necessárias, o comando **falha ou avisa de forma
inequívoca** em vez de produzir um resultado silenciosamente mais fraco; (c)
confirmar que entradas patológicas (vazias, não finitas, não numéricas,
duplicadas, fora de ordem) resultam em recusa contada, nunca em resultado
aceite. Enquanto este item estiver aberto, nenhuma proteção do harness pode ser
descrita como garantida em execução real.

## Ligação aos ativadores de contingência (§10)

A contingência até 31/10 é ativada no primeiro gate que torne setembro irrealista,
nunca apenas no fim do mês. Ativadores principais do plano: ausência de imagem
QEMU funcional em 20/08; ausência de vertical slice em 25/08; núcleo não congelado
em 30/08 com mais de dois dias de trabalho restante; piloto inválido em 06/09;
dados essenciais incompletos em 13/09; draft integral inexistente em 18/09. As
regras administrativas da extensão são confirmadas até 10/08 (pedido no email G0);
na ausência de uma data oficial anterior, o pedido é iniciado no máximo em 18/09.

---

## Riscos acrescentados em 10–11/08/2026 (execução real)

| ID | Risco | Prob. | Impacto | Owner | Estado | Prazo | Sinal antecipado | Mitigação |
|---|---|---|---|---|---|---|---|---|
| **R28** | **Indisponibilidade de mercado de ARM64 dedicado bloqueia a plataforma de medição** — Oracle (home region fixada no registo, sem capacidade Ampere e sem possibilidade de mudar de região numa conta Always Free), Hetzner (CAX esgotadas em todas as localizações) e Azure for Students (regiões limitadas a 5; quota `0 of 0` em Dpsv5/v6 e Dplsv5/v6) falharam no mesmo dia | **Materializado** | **Crítico** | Ambos | Aberto — quota pedida (DPLSv5 e DPLSv6, Germany West Central, 4 vCPU); fallback AWS `c6g.xlarge` (~7 EUR pela campanha) | VM operacional antes de G2 (23/08) | Prazo de 10/08 do G0 ultrapassado | Não depender de free tiers para o caminho crítico: orçamentar ~7–15 EUR de instância dedicada. Comunicar no email G0 (plano §10). Regra §8.1: sem VM a 12/08, comunicar formalmente o risco aos orientadores |
| **R29** | **Uso de instância *burstable* como plataforma de medição** — a série B do Azure (a única sem pedido de quota) funciona por créditos de CPU; ao esgotarem, o processador é estrangulado | Alta se não for barrado | **Crítico para a RQ3** | Agente | Mitigado por decisão: série B admitida **apenas** como plataforma de integração funcional; nenhum número dela entra na dissertação (ver PROGRESS, «três degraus») | permanente | Qualquer execução cronometrada cujo `sut_environment.json` indique família B/t4g | Excluir `Bpsv2`/`t4g` do protocolo; a campanha só corre em família dedicada (`Dplsv5`, `c6g`, `m6g`). O estrangulamento por créditos apareceria como saturação de CPU e falsificaria o critério do plano §7.3 |
| **R30** | **Deriva do host de build ao longo do tempo** — `wsl --install -d Ubuntu` passou a instalar o Ubuntu 26.04 (Python 3.14), fora do envelope validado do Scarthgap (abril/2024) | Alta | Alto | Ambos | Mitigado 10/08 — guia passa a exigir instalação por nome (`-d Ubuntu-24.04`), com a razão e a data registadas | permanente | Build que falha em BitBake antes do parse | O mesmo comando dá hosts diferentes consoante a data: a reprodutibilidade exige fixar a versão do host, não só das layers |
| **R31** | **Defeitos que só a execução real revela** — o primeiro build encontrou 2 bugs no trabalho Yocto até aí classificado como verificado: corrida no make paralelo do perl e `DL_DIR`/`SSTATE_DIR` a resolver para uma pasta temporária do kas (caches perdidas todas as execuções, tornando falso o claim C01 de build reproduzível) | **Materializado** (Yocto); **provável** (harness) | Alto | Agente | Yocto: corrigido (`e83fb24`, `c0ebf7c`). Harness: **por mitigar** — 618 testes correm todos contra *fakes*; nunca falou com broker, Ditto ou VM reais | Micro-piloto antes de qualquer campanha | Componente declarado «verificado» que nunca foi executado no ambiente-alvo | Tratar M2 (unitário com fakes) como hipótese, não como facto. O micro-piloto (smoke → nominal curto → dropout → restart) existe precisamente para revelar os equivalentes destes bugs no harness antes de custarem uma campanha |
