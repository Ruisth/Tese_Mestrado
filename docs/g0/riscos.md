# Registo de riscos

> Base: tabela do plano integrado §11 (riscos R1–R8, transcritos sem alteração de
> conteúdo) + riscos operacionais adicionais identificados na criação deste
> repositório (R9–R15). Rever a cada fecho de gate e sempre que um sinal
> antecipado for observado; registar ativações no LOG.

Atualizado: 2026-08-07.

## Riscos do plano (§11)

| ID | Risco | Sinal antecipado | Mitigação/decisão |
|---|---|---|---|
| R1 | Falta de hardware Raspberry Pi | Hardware continua indisponível | QEMU funcional + VM ARM nativa; excluir alegações de hardware físico |
| R2 | Build Yocto lento ou instável | G1 em risco | WSL2 em filesystem Linux, revisions fixadas, imagem mínima e cache de downloads |
| R3 | Imagens sem ARM64 | Falha no `manifest inspect` | Substituir por imagem oficial compatível; ACA-Py é cortado, nunca emulado |
| R4 | Ditto excede recursos | OOM ou swap persistente | VM mínima de 8 GiB, limites medidos e serviços não essenciais removidos |
| R5 | Âmbito volta a crescer | Pedido sem ligação às RQs | Aplicar P0/P1/out-of-scope e exigir troca explícita de horas |
| R6 | Resultados sem proveniência | Métrica sem `run_id`/manifesto | Invalidar a execução e repeti-la antes do data freeze |
| R7 | Feedback tardio | Sem resposta nos marcos | Entregar capítulos cedo e continuar com as decisões documentadas |
| R8 | Escrita fica para o fim | Capítulos 1–4 incompletos em 06/09 | Reserva diária de escrita e corte imediato de P1 |

## Riscos operacionais adicionais

| ID | Risco | Sinal antecipado | Mitigação/decisão |
|---|---|---|---|
| R9 | Workspace em Nextcloud/NTFS: builds, ambientes virtuais ou repositórios Git corrompidos/lentos por sincronização e semântica de ficheiros NTFS | Conflitos de sincronização (`... (conflicted copy)`), locks de ficheiros, I/O lento, builds a falhar de forma não determinística | Nunca fazer builds Yocto nem correr a stack a partir de `/mnt/d`/Nextcloud (plano §5.1); builds e venvs em WSL2 ext4 ou na VM; copiar apenas resultados finais para o workspace; pausar a sincronização durante operações de I/O intensivo; `SHA256SUMS` para detetar corrupção |
| R10 | VM ARM64 não disponível a 10/08 (conta, pagamento, capacidade do fornecedor na região) | Criação da VM ainda pendente em 09/08; região sem capacidade CAX | Aplicar a regra do G0 (§8.1): a 10/08 sem VM, mudar de fornecedor/região; a 12/08, comunicar risco aos orientadores; checklist pronta em [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md) para minimizar o tempo de setup |
| R11 | Divergência de versões de Python: host Windows com 3.14, containers/CI previstos com 3.12, `pyproject` exige >=3.11 | Testes passam num ambiente e falham noutro; dependências sem wheels para a versão do host; warnings de depreciação diferentes | O ambiente de referência para testes e execução é Linux (WSL2/VM) com a versão do Python fixada no `Dockerfile`; não validar comportamento apenas no Python do host Windows; correr `pytest` no mesmo interpretador do container antes de declarar verde |
| R12 | Espaço em disco/memória insuficiente no host para o build Yocto em WSL2 | `df -h` abaixo de ~120 GB livres antes do build; pressão de memória/OOM no WSL durante o BitBake | Verificar espaço antes do primeiro build (guia §disk sizing); limpar `tmp/` entre builds se necessário mantendo `downloads/` e `sstate-cache`; configurar `.wslconfig` (memória/swap) antes do G1 |
| R13 | Variabilidade de desempenho da VM cloud com vCPU partilhada (CAX21) contamina as medições | `steal time` elevado em `top`/`vmstat`; dispersão anómala entre execuções repetidas | Registar a limitação no manifesto de ambiente (plano §5.1); unidade estatística = execução com repetições (§7.3); reportar dispersão (desvio-padrão/IC95%); excluir apenas falhas comprovadas da cloud, nunca execuções lentas pelo resultado |
| R14 | Indisponibilidade dos orientadores em agosto (período de férias) atrasa o fecho do âmbito no G0 | Sem resposta ao email de G0 até 12/08 | Enviar o email cedo com pedido de validação assíncrona; prosseguir com o âmbito documentado (§8.1 G7 aplica o mesmo princípio); registar tentativas de contacto no LOG; escalar no marco de 17/08 |
| R15 | Perda ou adulteração de dados brutos antes do arquivo (falha de disco, sync, engano humano) | Checksums a falhar; ficheiros modificados após a recolha | `SHA256SUMS` por `run_id` gerados no fim de cada execução; `raw/` tratado como imutável desde a recolha (não apenas no freeze); cópia para arquivo versionado fora do Nextcloud logo após cada sessão de campanha |

## Ligação aos ativadores de contingência (§10)

A contingência até 31/10 é ativada no primeiro gate que torne setembro irrealista,
nunca apenas no fim do mês. Ativadores principais do plano: ausência de imagem
QEMU funcional em 20/08; ausência de vertical slice em 25/08; núcleo não congelado
em 30/08 com mais de dois dias de trabalho restante; piloto inválido em 06/09;
dados essenciais incompletos em 13/09; draft integral inexistente em 18/09. As
regras administrativas da extensão são confirmadas até 10/08 (pedido no email G0);
na ausência de uma data oficial anterior, o pedido é iniciado no máximo em 18/09.
