# Registo de riscos

> Base: tabela do plano integrado §11 (R1–R8, conteúdo dos campos Risco/Sinal/
> Mitigação transcrito do plano sem alteração) + riscos operacionais adicionais
> deste repositório (R9–R15) + riscos da auditoria externa de 08/08/2026 §11
> (R16–R27, adaptados à situação real do repositório). Colunas de controlo
> (Probabilidade, Impacto, Owner, Estado, Prazo de mitigação) acrescentadas a
> todos os riscos conforme a auditoria §5.4. Rever a cada fecho de gate e sempre
> que um sinal antecipado for observado; registar ativações no LOG.
>
> Owner: `Estudante` (ações externas ao repositório), `Agente` (alterações no
> repositório), `Ambos`. Estado: `Aberto`, `Em mitigação`, `Mitigado`,
> `Materializado`, `Fechado`. Probabilidade/Impacto de R16–R27: valores da
> auditoria; de R1–R15: avaliação de 08/08 (a rever com os orientadores).

Atualizado: 2026-08-08.

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

Nota de 08/08: R18, R19 e R22 (correções do harness), R21 (marker `integration`
e política de evidência), R24 (lock de desenvolvimento) e R25 (bundle de backup
e instruções de remote) estão a ser tratados em paralelo hoje; R26 teve a
sincronização diagramas/cap. 4 concluída e checklist adicionada. Estes estados
só passam a `Mitigado` com evidência arquivada.

| ID | Risco | Prob. | Impacto | Owner | Estado | Prazo mitigação | Sinal antecipado | Mitigação/decisão |
|---|---|---|---|---|---|---|---|---|
| R16 | Enquadramento teórico não desbloqueia o orientador (cap. 2 com ~1 034 palavras para meta de 6 000–7 000) | Alta | Crítico | Ambos | Aberto | 10–11/08 | Sem draft enviável em 11/08 | Sprint imediato de teoria (auditoria §6.6/§12.2); suspender features novas até ao envio ao orientador |
| R17 | Claim de novidade sem pesquisa registada (`search_log.csv` e `study_selection.csv` só com cabeçalhos) | Alta | Alto | Ambos | Aberto | 11/08 (antes do envio ao orientador) | Texto enviado com CSVs vazios | Executar o protocolo de revisão e registar queries/decisões reais, ou limitar o claim às fontes efetivamente examinadas; nunca fabricar entradas de pesquisa |
| R18 | Recursos medidos no host errado (`docker stats` corre no Docker local do host do harness por defeito) | Alta | Crítico | Agente | Em mitigação — correção do harness em curso a 08/08 | antes de G4 (06/09) | Piloto sem identificação inequívoca da VM | Collector na VM ou canal remoto explícito e registado + dois manifestos (`sut_environment` na VM, `loadgen_environment` no host do simulador) |
| R19 | `events.jsonl` não recolhido pelo runner (transferência manual `scp` incompatível com o fluxo síncrono; run marcado como falhado) | Alta | Crítico | Agente | Em mitigação — correção do harness em curso a 08/08 | antes de G4 (06/09) | Primeiro piloto falha por ficheiro ausente | Automatizar a fase de recolha antes do piloto; sem intervenção ad hoc por run |
| R20 | Condições obrigatórias ausentes do plano de campanha (10 smokes, `invalid-payload`, reconnect real, restart) — claims C10–C14 sem percurso | Alta | Alto | Agente | Aberto | antes do piloto (30/08–06/09) | Campaign plan sem C10–C14 | Matriz condição→claim antes do piloto; acrescentar as condições em falta ao gerador de plano |
| R21 | Testes unitários confundidos com integração (marker `integration` registado mas sem uso; sem testes live) | Alta | Alto | Agente | Em mitigação — marker e política de evidência corrigidos a 08/08 | G3 (30/08) | Gate declarado apenas com fakes | Definition of Done por nível (auditoria §8.4) e relatório de testes persistente; criar testes live de integração/E2E antes de G3 |
| R22 | Warm-up contamina métricas de recursos (sampler abrange warm-up + execução; análise não filtra a janela medida) | Alta | Alto | Agente | Em mitigação — correção do harness em curso a 08/08 | antes de G4 (06/09) | `resources.csv` inclui período pré-medição | Registar `measured_started_utc` no manifesto e filtrar a janela medida na análise |
| R23 | Critério de saturação muda depois do freeze (queue growth `TODO`; CPU sem normalização por nº de CPUs; regra «metade dos runs» não validada) | Média/Alta | Alto | Ambos | Aberto | antes de `exp-v1` (06/09) | Regra de queue growth/CPU sem decisão em G3 | Fechar métrica e regra com o orientador antes do freeze; instrumentar queue depth ou remover o critério por decisão formal registada |
| R24 | Dependências Python mudam entre builds (`>=` em `pyproject.toml`, sem lockfile com hashes) | Média | Alto | Agente | Em mitigação — lock de desenvolvimento criado a 08/08; lock de runtime com hashes antes de `exp-v1` | 06/09 | Novo build resolve versões diferentes | Lockfile com versões/hashes antes de `exp-v1`; não afirmar «rebuild reproduzível» até lá |
| R25 | Perda do repositório local (zero remotes, zero tags, workspace em Nextcloud) | Média | Crítico | Ambos | Em mitigação — bundle de backup e instruções de remote em produção a 08/08 | 09/08 | Repositório existe apenas no disco local/Nextcloud | Remote privado ou bundle Git verificado fora do Nextcloud; tags reservadas para evidência real (`g1`, `g2`, `exp-v1`, `data-v1`, `rc1`), nunca antecipadas |
| R26 | Documentação diverge do contrato (deriva pós-CONTRACTS v1.1: referências a v1.0, idempotência sem âmbito por `run_id`) | Alta | Médio/Alto | Agente | Em mitigação — sincronização diagramas/cap. 4 concluída a 08/08; checklist de impacto adicionada | contínuo (a cada alteração de contrato) | CONTRACTS muda sem atualização de tese/diagramas/READMEs | Checklist de impacto por ADR/alteração de contrato; verificação de drift duas vezes por semana (auditoria §14.2) |
| R27 | Estado de gestão induz falsa confiança (PROGRESS/backlog/plano contraditórios; estados híbridos fora da taxonomia) | Alta | Alto | Agente | Em mitigação — PROGRESS reestruturado como fonte única a 08/08; backlog sem estado | 09/08 e revisão diária | Documentos de estado divergentes | Fonte única de estado em `PROGRESS.md` (modelo Implementado/Verificado/Aceite); backlog só com ações; controlo diário de esforço (<10 min) |

## Ligação aos ativadores de contingência (§10)

A contingência até 31/10 é ativada no primeiro gate que torne setembro irrealista,
nunca apenas no fim do mês. Ativadores principais do plano: ausência de imagem
QEMU funcional em 20/08; ausência de vertical slice em 25/08; núcleo não congelado
em 30/08 com mais de dois dias de trabalho restante; piloto inválido em 06/09;
dados essenciais incompletos em 13/09; draft integral inexistente em 18/09. As
regras administrativas da extensão são confirmadas até 10/08 (pedido no email G0);
na ausência de uma data oficial anterior, o pedido é iniciado no máximo em 18/09.
