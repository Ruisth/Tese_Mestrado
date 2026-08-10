# Registo de riscos

> Base: tabela do plano integrado §11 (R1–R8, conteúdo dos campos Risco/Sinal/
> Mitigação transcrito do plano sem alteração) + riscos operacionais adicionais
> deste repositório (R9–R15) + riscos da auditoria externa de 08/08/2026 §11
> (R16–R27, adaptados à situação real do repositório) + riscos da reanálise
> externa pós-correções de 08/08/2026 §11 (RA1–RA15, seguidos linha a linha na
> secção própria). Colunas de controlo (Probabilidade, Impacto, Owner, Estado,
> Prazo de mitigação) acrescentadas a todos os riscos conforme a auditoria §5.4.
> Rever a cada fecho de gate e sempre que um sinal antecipado for observado;
> registar ativações no LOG.
>
> Owner: `Estudante` (ações externas ao repositório), `Agente` (alterações no
> repositório), `Ambos`. Estado: `Aberto`, `Em mitigação`, `Parcialmente
> mitigado`, `Mitigado`, `Materializado`, `Fechado`. Probabilidade/Impacto de
> R16–R27: valores da auditoria; de R1–R15: avaliação de 08/08 (a rever com os
> orientadores).
>
> `Mitigado em M2` significa **apenas** que a correção existe no repositório e
> está coberta por testes unitários com fakes em Windows. Não é prova live, não
> fecha gate nenhum e não valida claim nenhum.

Atualizado: 2026-08-10 (bloco P5.3: mapeamento explícito RA1–RA15; as tabelas
R1–R27 mantêm-se como em 08/08/2026).

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
| R9 | Workspace em Nextcloud/NTFS: builds, ambientes virtuais ou repositórios Git corrompidos/lentos por sincronização e semântica de ficheiros NTFS | Média | Alto | Estudante | Em mitigação (regras documentadas; por aplicar nos builds) | contínuo (antes do 1.º build) | Conflitos de sincronização (`... (conflicted copy)`), locks de ficheiros, I/O lento, builds a falhar de forma não determinística | Nunca fazer builds Yocto nem correr a stack a partir de `/mnt/d`/Nextcloud (plano §5.1); builds e venvs em WSL2 ext4 ou na VM; copiar apenas resultados finais para o workspace; pausar a sincronização durante operações de I/O intensivo; `SHA256SUMS` para detetar corrupção |
| R10 | VM ARM64 não disponível a 10/08 (conta, pagamento, capacidade do fornecedor na região) | Média | Crítico | Estudante | Aberto | 10/08 (escalar 12/08) | Criação da VM ainda pendente em 09/08; região sem capacidade CAX | Aplicar a regra do G0 (§8.1): a 10/08 sem VM, mudar de fornecedor/região; a 12/08, comunicar risco aos orientadores; checklist pronta em [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md) para minimizar o tempo de setup |
| R11 | Divergência de versões de Python: host Windows com 3.14, containers/CI previstos com 3.12, `pyproject` exige >=3.11 | Média | Médio | Agente | Em mitigação | 16/08 (testes em Linux antes de G1) | Testes passam num ambiente e falham noutro; dependências sem wheels para a versão do host; warnings de depreciação diferentes | O ambiente de referência para testes e execução é Linux (WSL2/VM) com a versão do Python fixada no `Dockerfile`; não validar comportamento apenas no Python do host Windows; correr `pytest` no mesmo interpretador do container antes de declarar verde |
| R12 | Espaço em disco/memória insuficiente no host para o build Yocto em WSL2 | Média | Alto | Estudante | Aberto | 09–10/08 (antes do 1.º build) | `df -h` abaixo de ~120 GB livres antes do build; pressão de memória/OOM no WSL durante o BitBake | Verificar espaço antes do primeiro build (guia §disk sizing); limpar `tmp/` entre builds se necessário mantendo `downloads/` e `sstate-cache`; configurar `.wslconfig` (memória/swap) antes do G1 |
| R13 | Variabilidade de desempenho da VM cloud com vCPU partilhada (CAX21) contamina as medições | Alta | Médio | Ambos | Em mitigação (mitigação metodológica definida no plano §7.3) | 06/09 (fechar antes de `exp-v1`) | `steal time` elevado em `top`/`vmstat`; dispersão anómala entre execuções repetidas | Registar a limitação no manifesto de ambiente (plano §5.1); unidade estatística = execução com repetições (§7.3); reportar dispersão (desvio-padrão/IC95%); excluir apenas falhas comprovadas da cloud, nunca execuções lentas pelo resultado |
| R14 | Indisponibilidade dos orientadores em agosto (período de férias) atrasa o fecho do âmbito no G0 | Alta | Alto | Estudante | Aberto | 12/08 (escalar 17/08) | Sem resposta ao email de G0 até 12/08 | Enviar o email cedo com pedido de validação assíncrona; prosseguir com o âmbito documentado (§8.1 G7 aplica o mesmo princípio); registar tentativas de contacto no LOG; escalar no marco de 17/08 |
| R15 | Perda ou adulteração de dados brutos antes do arquivo (falha de disco, sync, engano humano) | Média | Crítico | Ambos | Em mitigação (`SHA256SUMS` por run implementado no harness; arquivo externo por executar) | 07/09 (antes da campanha oficial) | Checksums a falhar; ficheiros modificados após a recolha | `SHA256SUMS` por `run_id` gerados no fim de cada execução; `raw/` tratado como imutável desde a recolha (não apenas no freeze); cópia para arquivo versionado fora do Nextcloud logo após cada sessão de campanha |

## Riscos da auditoria externa (08/08/2026, §11) — R16–R27

Nota de 08/08 (atualizada apos os blocos P1a-P1c e P2 da ordem de trabalhos): R18, R19, R20 e R22 foram corrigidos em M2 (prova live pendente). Referências originais: R18, R19 e R22 (correções do harness), R21 (marker `integration`
e política de evidência), R24 (lock de desenvolvimento) e R25 (bundle de backup
e instruções de remote) estão a ser tratados em paralelo hoje; R26 teve a
sincronização diagramas/cap. 4 concluída e checklist adicionada. Estes estados
só passam a `Mitigado` com evidência arquivada.

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
| R25 | Perda do repositório local (zero remotes, zero tags, workspace em Nextcloud) | Média | Crítico | Ambos | Em mitigação — bundle criado e verificado a 08/08, mas ainda no mesmo domínio Nextcloud; cópia externa/remote pendente (estudante) | 09/08 | Repositório existe apenas no disco local/Nextcloud | Remote privado ou bundle Git verificado fora do Nextcloud; tags reservadas para evidência real (`g1`, `g2`, `exp-v1`, `data-v1`, `rc1`), nunca antecipadas |
| R26 | Documentação diverge do contrato (deriva pós-CONTRACTS v1.1: referências a v1.0, idempotência sem âmbito por `run_id`) | Alta | Médio/Alto | Agente | Em mitigação — sincronização diagramas/cap. 4 concluída a 08/08; checklist de impacto adicionada | contínuo (a cada alteração de contrato) | CONTRACTS muda sem atualização de tese/diagramas/READMEs | Checklist de impacto por ADR/alteração de contrato; verificação de drift duas vezes por semana (auditoria §14.2) |
| R27 | Estado de gestão induz falsa confiança (PROGRESS/backlog/plano contraditórios; estados híbridos fora da taxonomia) | Alta | Alto | Agente | Em mitigação — PROGRESS reestruturado como fonte única a 08/08; backlog sem estado | 09/08 e revisão diária | Documentos de estado divergentes | Fonte única de estado em `PROGRESS.md` (modelo Implementado/Verificado/Aceite); backlog só com ações; controlo diário de esforço (<10 min) |

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
| RA5 | Runs inválidos entram nos resultados | Agente | **Mitigado em M2** | `src/egw_experiments/analyze.py` exclui da agregação os runs cujo `validity` do manifesto exista e não seja `valid`; a exclusão exige causa comprovada (cloud/instrumentação/configuração) e nunca o resultado da execução. Prova live pendente de VM |
| RA6 | Recursos locais tratados como recursos ARM | Agente | **Mitigado em M2** | Coluna de proveniência de host obrigatória em `resources.csv`; recolha do SUT por `src/deployment/scripts/collect-resources.sh` na VM ingerida por `run --resources-from`; o amostrador local é opt-in (`--local-resources`) e fica marcado com `resource_source`. Equivale a R18; prova live pendente |
| RA7 | C10–C13 passam sem completude | Agente | **Mitigado em M2** | `processed/acceptance_by_condition.csv` avalia **todas** as condições planeadas com gate de completude explícito (`runs_complete`); uma condição planeada com zero runs válidos não passa. Prova live pendente |
| RA8 | Queue/CPU com gaps geram falso sustained | Agente | **Mitigado em M2** | Os detetores de janela sustentada só contam intervalos entre amostras consecutivas dentro do gap máximo admitido, e cada run reporta `resources_coverage_pct`/`metrics_coverage_pct` em `per_run.csv`. Os limiares estatísticos e a janela de 60 s **não** foram alterados — mudou apenas a instrumentação |
| RA9 | Raw resources sobrescritos | Agente | **Mitigado em M2** | Diretórios `raw/<run_id>/` são write-once: com `SHA256SUMS` presente o diretório fica selado e qualquer escrita com conteúdo diferente é recusada (`run.py`) |
| RA10 | Campanha manual falha na ordem ou completude | Agente | **Mitigado em M2** | Subcomando `campaign` (`src/egw_experiments/campaign.py`): executa o plano congelado pela ordem, com resume, classificação `blocked` para diretórios não selados, cooldowns registados e `campaign_log.jsonl`. Prova live pendente |
| RA11 | Evidência 452 não reproduzível por commit | Agente | **Mitigado** | Suite re-executada em HEAD limpo e re-selada em `docs/evidence/tests/2026-08-08-head-ca445a3/`: `515 passed`, commit testado `ca445a31e5d146cf0c214b3cd4a23a95a48b5289` (tree `b767b229e295b9453cbc2efcbfd0122bf8409d38`), `git status --porcelain` vazio, `SHA256SUMS` dos três ficheiros; commit da evidência `9491090`. Identificadores registados na entrada #C006 do [`../../LOG.md`](../../LOG.md) |
| RA12 | Lock dev confundido com lock runtime | Ambos | **Parcialmente mitigado** | O cabeçalho de `src/requirements.lock` identifica-o como lock de **desenvolvimento**, sem hashes, gerado no venv Windows, e nomeia a suite de 515 testes contra a qual foi congelado. Dependência bloqueante: o lock de runtime ARM64 com hashes tem de ser gerado no build da imagem na VM e arquivado antes de `exp-v1`; até lá é proibido afirmar «rebuild reproduzível». Equivale a R24 |
| RA13 | Bundle perdido no mesmo domínio Nextcloud | Estudante | **Aberto — ação do estudante** | `backups/egw-20260808-final.bundle` existe e foi verificado (SHA-256 recalculado localmente, coincidente com a verificação externa), mas continua **dentro** do domínio Nextcloud. Dependência bloqueante: cópia para suporte externo ou remote privado. Equivale a R25 |
| RA14 | Documentos de estado voltam a divergir | Agente | **Parcialmente mitigado** | `PROGRESS.md` é fonte única de estado e o bloco P5.3 corrigiu a deriva detetada (run_id reais na matriz claim→evidência, `diagrams/README.md` em CONTRACTS v1.1, `src/README.md` sem sugerir testes live, cabeçalho do lock com 515, LOG #C006 com os identificadores exatos). Dependência bloqueante: a revisão transversal periódica ainda não é rotina com registo próprio. Equivale a R27 |
| RA15 | Forecast irreal por ausência de horas | **Estudante** | **MATERIALIZADO** | O risco já ocorreu: `actual_h`, `remaining_h` e `forecast` estão vazios na tabela de controlo de esforço de [`../../PROGRESS.md`](../../PROGRESS.md), pelo que **não existe forecast de conclusão** e as datas de setembro não têm suporte quantitativo. São horas humanas: nenhum agente as pode estimar, inferir ou preencher — inventá-las seria fabricar dados. As durações do trabalho dos agentes ficam no `LOG.md` e **não** substituem estas colunas. Fecho exclusivo do estudante, no controlo diário de <10 min |

Só o estudante pode alterar o estado de RA1, RA3, RA13 e RA15; RA12 exige a VM.
Os estados `Mitigado em M2` (RA5–RA10) passam a `Mitigado` com prova live apenas
depois de G3/G4, com evidência arquivada.

## Ligação aos ativadores de contingência (§10)

A contingência até 31/10 é ativada no primeiro gate que torne setembro irrealista,
nunca apenas no fim do mês. Ativadores principais do plano: ausência de imagem
QEMU funcional em 20/08; ausência de vertical slice em 25/08; núcleo não congelado
em 30/08 com mais de dois dias de trabalho restante; piloto inválido em 06/09;
dados essenciais incompletos em 13/09; draft integral inexistente em 18/09. As
regras administrativas da extensão são confirmadas até 10/08 (pedido no email G0);
na ausência de uma data oficial anterior, o pedido é iniciado no máximo em 18/09.
