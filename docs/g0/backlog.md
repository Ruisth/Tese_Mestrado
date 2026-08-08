# Backlog acionável por gate (G0→G7)

> **Este ficheiro contém apenas ações**: o que falta fazer, a evidência esperada,
> as dependências e as regras de corte de cada gate (plano §8/§8.1). **O estado de
> cada entregável vive exclusivamente em [`../../PROGRESS.md`](../../PROGRESS.md)**
> (fonte única de estado — auditoria externa de 08/08/2026, §5.1); este ficheiro
> não usa a taxonomia de estados do plano. Itens cujo artefacto já existe no
> repositório estão marcados «implementado — por verificar/aceitar (ver
> PROGRESS)»; isso significa apenas que o código/documento existe, nunca que o
> gate está fechado.
>
> Dependências externas recorrentes: **requer WSL2 ext4** = Ubuntu 24.04 no WSL2
> com build em filesystem Linux (guia: [`../setup/wsl2_ubuntu_yocto.md`](../setup/wsl2_ubuntu_yocto.md));
> **requer VM ARM** = VM ARM64 nativa tipo Hetzner CAX21 (checklist:
> [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md)).

Atualizado: 2026-08-08.

---

## G0 — Âmbito e ambiente (10/08)

Regra de corte (§8.1): VM criada e acesso `aarch64` validado a 10/08. Sem VM nesse
dia, mudar de fornecedor; sem VM em 12/08, comunicar risco aos orientadores.

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Fechar âmbito, RQs e premissas em documento | implementado — por verificar/aceitar (ver PROGRESS) | [`ambito_e_rqs.md`](ambito_e_rqs.md) validado pelos orientadores | Resposta dos orientadores |
| Enviar email de âmbito aos orientadores e pedir regras administrativas da extensão (prazo 09/08; regras até 10/08) | draft implementado — envio por executar (ver PROGRESS) | Email enviado (cópia e data no LOG); draft em [`email_orientadores_G0.md`](email_orientadores_G0.md) | Ação do estudante |
| Reunião de âmbito com os orientadores (proposta: 10/08) | — | Ata/registo da decisão no LOG | Resposta dos orientadores |
| Instalar Ubuntu 24.04 LTS no WSL2 com build dir em ext4 (prazo 09–10/08) | — | `wsl -l -v`; `df -h` do diretório de build; log da instalação | Ação do estudante; guia em `docs/setup/` |
| Criar VM ARM64 (Hetzner CAX21 ou equivalente) e validar `uname -m` = `aarch64` (prazo 10/08) | — | Output de `uname -a`, `lscpu`, `/etc/os-release` gravado no manifesto de ambiente | Conta/pagamento do estudante; checklist em `docs/setup/` |
| Semear matriz claim→evidência | implementado — por verificar/aceitar (ver PROGRESS) | [`../claim_evidence_matrix.csv`](../claim_evidence_matrix.csv) com claims `Pendente — sem evidência` | — |
| Backlog e registo de riscos criados | implementado — por verificar/aceitar (ver PROGRESS) | Este ficheiro + [`riscos.md`](riscos.md) mantidos a cada gate | — |
| Quarentenar/remover resultados sem evidência da dissertação ativa | implementado — por verificar/aceitar (ver PROGRESS) | Cap. 5 sem números não suportados; nota no LOG | — |

## G1 — Yocto/QEMU funcional (16/08)

Regra de corte (§8.1): imagem própria arranca duas vezes e executa um container.
Se falhar, reduzir a imagem ao sistema mínimo com runtime e mover o deploy para
script externo. Sem imagem funcional em 20/08, discutir extensão/reformulação.

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Congelar VM ARM (specs registadas, acesso estável) | — | Manifesto de ambiente (fornecedor, região, CPU, kernel, SO, limitação vCPU partilhado) | Requer VM ARM (G0) |
| Manifesto `kas` para `qemuarm64` com tags/commits exatos (Scarthgap 5.0.19) | implementado — por verificar/aceitar (ver PROGRESS) | `kas dump` reproduzível a partir de checkout limpo | — |
| Build de `egw-image` em WSL2 ext4 | — | Log completo do BitBake; `SHA256SUMS` dos artefactos | Requer WSL2 ext4; >=120 GB livres |
| Dois boots QEMU com systemd, rede e runtime OCI | — | `boot1.log`, `boot2.log` (systemd running, ping, `podman/docker run` de container de teste) | Build concluído |
| Verificar arquiteturas OCI das imagens da stack (`linux/arm64` por digest) | lock `images.lock.env` implementado — falta output de `manifest inspect` na VM (ver PROGRESS) | Output de `docker manifest inspect` por imagem, arquivado | Requer VM ARM |
| Introdução/RQs da dissertação em revisão; protocolo da revisão executado e bibliografia auditada | protocolo redigido — revisão não executada: `search_log.csv` e `study_selection.csv` só têm cabeçalhos (ver PROGRESS e risco R17) | Capítulo 1 draft; queries e seleção registadas em `thesis/research/`; `references.bib` auditado | — |

## G2 — Vertical slice (23/08)

Regra de corte (§8.1): um payload percorre MQTT→controlador→Ditto e é recuperado
pela API. Se falhar, cortar APIs auxiliares e toda a identidade. Sem E2E em 25/08,
declarar risco sério para setembro.

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Compose ARM64 mínimo (Mosquitto TLS 8883, Ditto 3.9.4 gateway/policies/things, MongoDB, controlador) | implementado — por verificar/aceitar (ver PROGRESS); `.env`, password file e certificados operacionais por criar | `docker compose up` limpo na VM; health/readiness reais | Requer VM ARM |
| Controlador MQTT→Ditto (validação por schema, idempotência, retry, logging, endpoints) | implementado — por verificar/aceitar (ver PROGRESS) | Ligação TLS a Mosquitto real; twin atualizado num Ditto real | Requer VM ARM |
| Vertical slice smartwatch→MQTT→controlador→Ditto | — | Trace reproduzível: `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` com estado correto | Compose na VM ARM; controlador |
| CLI do simulador com cenário `smoke` | implementado — por verificar/aceitar (ver PROGRESS) | `python -m egw_simulator run --scenario smoke ...` contra broker real, com manifesto de execução | Requer VM ARM |
| Testes iniciais (unitários + integração local) | unitários implementados (400, Windows) — por verificar em Linux e com integração real (ver PROGRESS e risco R21) | `pytest` verde em Linux com relatório persistido; >=1 teste live de integração | Python 3.11+ em ambiente Linux |
| Capítulos 1–2; metodologia iniciada; diagrama lógico | esqueleto existente — volume muito abaixo do alvo (auditoria §6; ver PROGRESS) | Ficheiros em `thesis/` e `diagrams/` com texto substancial | — |

## G3 — Feature freeze P0 e decisão ACA-Py (30/08)

Regra de corte (§8.1): ACA-Py só avança se build/boot QEMU, deploy ARM limpo, três
dispositivos, cenários, testes, métricas e soak estiverem completos e sem defeitos
P0. Cortar ao fim de 12 h ou em 03/09, o que ocorrer primeiro.

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Três wearables concorrentes no simulador | implementado — por verificar em execução real (ver PROGRESS) | Execução com `--devices smartwatch,smart_ring,smart_clothing`; três twins atualizados | Requer VM ARM |
| Todos os cenários (`smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload`, `soak`) | implementados no simulador — auditoria §7.3: `dropout-reconnect` não induzia desconexão MQTT real, correção em curso a 08/08; por verificar (ver PROGRESS) | Execuções registadas com manifesto por cenário; desconexão real demonstrada em execução live | Requer VM ARM |
| Reconnect/backpressure no controlador e simulador | — | Teste de integração `dropout-reconnect` verde; contadores coerentes | Controlador + broker |
| Métricas e harness experimental | implementado com lacunas (auditoria §9) — correções em curso a 08/08 (riscos R18/R19/R20/R22; ver PROGRESS) | Recursos recolhidos na VM certa; `events.jsonl` recolhido automaticamente; warm-up excluído; condições C10–C14 no plano de campanha | — |
| Suite de testes completa (unitários, integração, E2E) | unitários implementados — testes live/`integration` por criar (ver PROGRESS e risco R21) | `pytest` verde incluindo marca `integration` na VM, com relatório persistido | Requer VM ARM |
| Soak piloto | — | Execução longa piloto sem crash; log e recursos | Requer VM ARM |
| Capítulo 3 e primeira versão do 4; ADRs e diagramas | ADRs e diagramas implementados — por verificar/aceitar (ver PROGRESS); capítulos parciais | `thesis/`; [`../adr/`](../adr/README.md) sincronizados com CONTRACTS v1.1 | — |
| Decisão ACA-Py registada no gate | tratar fora do forecast base (auditoria §16): só avança com margem comprovada por horas reais | Entrada no LOG + Anexo C do plano (autorizado/cortado) | Estado dos itens P0 acima |

## G4 — Protocolo congelado, tag `exp-v1` (06/09)

Regra de corte (§8.1): todos os pilotos produzem dados válidos e o script de
análise gera tabelas/figuras. Depois deste gate não se alteram métricas, condições
ou critérios de exclusão.

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Reprodução desde checkout limpo | — | Registo de um clone limpo a construir e executar o smoke E2E | WSL2 ext4 + VM ARM |
| Correções P0/P1 pós-freeze de features | — | Commits identificados; sem features novas | — |
| ACA-Py mínimo (apenas se autorizado no G3; até 03/09) | fora do forecast base (auditoria §16) | Dois agentes locais, `did:peer`, convite OOB, mensagem DIDComm; digest ARM64 verificado | Autorização G3; timebox 12 h |
| Piloto completo da campanha | — | Dados piloto em `experiments/results/raw/` com manifestos, sem intervenção ad hoc | Requer VM ARM; harness corrigido (R18–R22) |
| Script de análise gera tabelas/figuras a partir de `raw/` | runs externos (boots/cold starts/twin creation) ainda sem percurso de análise (auditoria §9.6; ver PROGRESS) | `processed/` e `figures/` regenerados por um único script, incluindo runs externos ou exceção formalmente documentada | Dados piloto |
| Capítulos 1–4 completos; esqueleto integral da avaliação | — | `thesis/` compilável, sem números inventados | — |
| Tag `exp-v1` | — | Tag no Git com protocolo congelado | Itens acima |

## G5 — Data freeze `data-v1` (13/09, 18:00)

Regra de corte (§8.1): todas as métricas essenciais às RQs têm dados completos.
Pode remover-se uma condição opcional, declarando a limitação; nunca preencher a
lacuna com uma conclusão sem evidência.

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Campanha ARM oficial (§7.1: 5 boots QEMU funcionais, 10 cold starts, 10 criações de twin, 10 execuções nominais, load-sweep 10/50/100/250 msg/s ×10, soak 24 h) | — | `experiments/results/raw/<run_id>/` completos com `SHA256SUMS` | Requer VM ARM; tag `exp-v1` |
| Apenas correções que invalidem experiências; repetir condições afetadas | — | LOG com justificação de cada repetição | — |
| Validar dados e gerar figuras | — | `processed/` + `figures/` regenerados; validação de proveniência (`run_id`/manifesto) | Campanha |
| Redigir setup e limitações (capítulo 5, secções de contexto) | — | Texto em `thesis/` | — |
| Tag `data-v1`; `raw/` imutável | — | Tag no Git; checksums verificados | Campanha completa |

## G6 — Draft integral (18/09)

Regra de corte (§8.1): todos os capítulos, figuras e respostas às RQs existem.
Uma reestruturação estimada acima de 20 h ativa a contingência (§10).

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Capítulos 5–6, Abstract e Resumo com evidência real | — | `thesis/` completo; cada número rastreado na matriz claim→evidência | `data-v1` |
| RQs respondidas apenas com evidência real | — | Matriz claim→evidência sem estados `Pendente` em claims usados no texto | `data-v1` |
| Draft integral enviado aos orientadores em 18/09 | — | Email de envio registado no LOG | Compilação limpa |
| Sem features; apenas reprodução e análise | — | Histórico Git sem commits de feature após G5 | — |

## G7 — Release e aprovação (25/09; `rc1` em 27/09)

Regra de corte (§8.1): PDF conforme, artefacto arquivado e feedback tratado. A
falta de resposta dos orientadores não paralisa o trabalho; seguem-se as últimas
decisões documentadas e registam-se as tentativas de contacto.

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| Smoke final e empacotamento do pacote de reprodutibilidade | — | Arquivo versionado com SHA-256 e localização registada | `data-v1` |
| Tratamento do feedback (prazo solicitado: 23/09) | — | Lista de alterações + respostas registadas | Feedback dos orientadores |
| Linguagem, referências, front matter, consistência e QA visual do PDF | — | Checklist editorial concluída; inspeção página a página | Draft integral |
| Release candidate `rc1` em 27/09 | — | Tag `rc1` + PDF | Itens acima |
| Submissão 29/09 17:00; recibo e tag `v1.0-thesis` | — | Recibo do portal; tag no Git | `rc1` |

## Pós-gate — 28–30/09

| Ação | Nota | Evidência esperada | Dependências |
|---|---|---|---|
| 28–29/09: apenas correções bloqueantes; PDF final, metadados e portal | — | Submissão interna a 29/09 17:00 | `rc1` |
| 30/09: reserva exclusivamente administrativa | — | Usar apenas se a submissão interna falhar | — |
