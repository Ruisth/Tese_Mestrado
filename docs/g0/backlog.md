# Backlog acionável por gate (G0→G7)

> Derivado da tabela do plano integrado §8 e das regras de corte §8.1. Estados
> usados neste backlog: `Pendente` e `Em curso`. Itens já concluídos com evidência
> saem do backlog e ficam registados em [`../../PROGRESS.md`](../../PROGRESS.md)
> (ex.: inicialização do Git, estrutura `experiments/results/`). Atualizar este
> ficheiro a cada fecho de gate.
>
> Dependências externas recorrentes: **requer WSL2 ext4** = Ubuntu 24.04 no WSL2
> com build em filesystem Linux (guia: [`../setup/wsl2_ubuntu_yocto.md`](../setup/wsl2_ubuntu_yocto.md));
> **requer VM ARM** = VM ARM64 nativa tipo Hetzner CAX21 (checklist:
> [`../setup/vm_arm64_hetzner.md`](../setup/vm_arm64_hetzner.md)).

Atualizado: 2026-08-07.

---

## G0 — Âmbito e ambiente (10/08)

Regra de corte (§8.1): VM criada e acesso `aarch64` validado a 10/08. Sem VM nesse
dia, mudar de fornecedor; sem VM em 12/08, comunicar risco aos orientadores.

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Fechar âmbito, RQs e premissas em documento | Em curso | [`ambito_e_rqs.md`](ambito_e_rqs.md) commitado | — |
| Enviar email de âmbito aos orientadores e pedir regras administrativas da extensão | Em curso | Email enviado (cópia e data no LOG); draft em [`email_orientadores_G0.md`](email_orientadores_G0.md) | Ação do estudante |
| Reunião de âmbito com os orientadores (proposta: 10/08) | Pendente | Ata/registo da decisão no LOG | Resposta dos orientadores |
| Instalar Ubuntu 24.04 LTS no WSL2 com build dir em ext4 | Pendente | `wsl -l -v`; `df -h` do diretório de build; log da instalação | Ação do estudante; guia em `docs/setup/` |
| Criar VM ARM64 (Hetzner CAX21 ou equivalente) e validar `uname -m` = `aarch64` | Pendente | Output de `uname -a`, `lscpu`, `/etc/os-release` gravado no manifesto de ambiente | Conta/pagamento do estudante; checklist em `docs/setup/` |
| Semear matriz claim→evidência | Em curso | [`../claim_evidence_matrix.csv`](../claim_evidence_matrix.csv) commitada, claims `Pendente — sem evidência` | — |
| Backlog e registo de riscos criados | Em curso | Este ficheiro + [`riscos.md`](riscos.md) commitados | — |
| Quarentenar/remover resultados sem evidência da dissertação ativa | Pendente | Diff em `thesis/` sem números não suportados; nota no LOG | Migração do capítulo 5 para este repo |

## G1 — Yocto/QEMU funcional (16/08)

Regra de corte (§8.1): imagem própria arranca duas vezes e executa um container.
Se falhar, reduzir a imagem ao sistema mínimo com runtime e mover o deploy para
script externo. Sem imagem funcional em 20/08, discutir extensão/reformulação.

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Congelar VM ARM (specs registadas, acesso estável) | Pendente | Manifesto de ambiente (fornecedor, região, CPU, kernel, SO, limitação vCPU partilhado) | Requer VM ARM (G0) |
| Manifesto `kas` para `qemuarm64` com tags/commits exatos (Scarthgap 5.0.19) | Em curso | `src/yocto/` commitado; `kas dump` reproduzível | — |
| Build de `egw-image` em WSL2 ext4 | Pendente | Log completo do BitBake; `SHA256SUMS` dos artefactos | Requer WSL2 ext4; >=120 GB livres |
| Dois boots QEMU com systemd, rede e runtime OCI | Pendente | `boot1.log`, `boot2.log` (systemd running, ping, `podman/docker run` de container de teste) | Build concluído |
| Verificar arquiteturas OCI das imagens da stack (`linux/arm64` por digest) | Pendente | Output de `docker manifest inspect` por imagem; `images.lock.env` | — |
| Introdução/RQs da dissertação em revisão; protocolo da revisão e bibliografia auditada | Pendente | Capítulo 1 draft; protocolo da revisão em `thesis/`; `references.bib` auditado | — |

## G2 — Vertical slice (23/08)

Regra de corte (§8.1): um payload percorre MQTT→controlador→Ditto e é recuperado
pela API. Se falhar, cortar APIs auxiliares e toda a identidade. Sem E2E em 25/08,
declarar risco sério para setembro.

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Compose ARM64 mínimo (Mosquitto TLS 8883, Ditto 3.9.4 gateway/policies/things, MongoDB, controlador) | Em curso | `src/deployment/` commitado; `docker compose up` limpo na VM | Requer VM ARM |
| Controlador MQTT→Ditto (validação por schema, idempotência, retry, logging, endpoints) | Em curso | `src/egw_controller/` + testes unitários a passar | — |
| Vertical slice smartwatch→MQTT→controlador→Ditto | Pendente | Trace reproduzível: `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` com estado correto | Compose na VM ARM; controlador |
| CLI do simulador com cenário `smoke` | Em curso | `python -m egw_simulator run --scenario smoke ...` com manifesto de execução | — |
| Testes iniciais (unitários + integração local) | Em curso | `pytest` verde em `src/tests/` | Python 3.11+ em ambiente Linux |
| Capítulos 1–2; metodologia iniciada; diagrama lógico | Pendente | Ficheiros em `thesis/` e `diagrams/` commitados | — |

## G3 — Feature freeze P0 e decisão ACA-Py (30/08)

Regra de corte (§8.1): ACA-Py só avança se build/boot QEMU, deploy ARM limpo, três
dispositivos, cenários, testes, métricas e soak estiverem completos e sem defeitos
P0. Cortar ao fim de 12 h ou em 03/09, o que ocorrer primeiro.

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Três wearables concorrentes no simulador | Em curso | Execução com `--devices smartwatch,smart_ring,smart_clothing`; três twins atualizados | — |
| Todos os cenários (`smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload`, `soak`) | Em curso | Execuções registadas com manifesto por cenário | Requer VM ARM para execuções válidas |
| Reconnect/backpressure no controlador e simulador | Pendente | Teste de integração `dropout-reconnect` verde; contadores coerentes | Controlador + broker |
| Métricas e harness experimental | Em curso | `src/egw_experiments/` gera `resources.csv` (CPU/RAM a 1 s) e agrega `events.jsonl` | — |
| Suite de testes completa (unitários, integração, E2E) | Em curso | `pytest` verde incluindo marca `integration` na VM | Requer VM ARM |
| Soak piloto | Pendente | Execução longa piloto sem crash; log e recursos | Requer VM ARM |
| Capítulo 3 e primeira versão do 4; ADRs e diagramas | Em curso | `thesis/`; [`../adr/`](../adr/README.md) commitado | — |
| Decisão ACA-Py registada no gate | Pendente | Entrada no LOG + Anexo C do plano (autorizado/cortado) | Estado dos itens P0 acima |

## G4 — Protocolo congelado, tag `exp-v1` (06/09)

Regra de corte (§8.1): todos os pilotos produzem dados válidos e o script de
análise gera tabelas/figuras. Depois deste gate não se alteram métricas, condições
ou critérios de exclusão.

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Reprodução desde checkout limpo | Pendente | Registo de um clone limpo a construir e executar o smoke E2E | WSL2 ext4 + VM ARM |
| Correções P0/P1 pós-freeze de features | Pendente | Commits identificados; sem features novas | — |
| ACA-Py mínimo (apenas se autorizado no G3; até 03/09) | Pendente | Dois agentes locais, `did:peer`, convite OOB, mensagem DIDComm; digest ARM64 verificado | Autorização G3; timebox 12 h |
| Piloto completo da campanha | Pendente | Dados piloto em `experiments/results/raw/` com manifestos | Requer VM ARM |
| Script de análise gera tabelas/figuras a partir de `raw/` | Pendente | `processed/` e `figures/` regenerados por um único script | Dados piloto |
| Capítulos 1–4 completos; esqueleto integral da avaliação | Pendente | `thesis/` compilável, sem números inventados | — |
| Tag `exp-v1` | Pendente | Tag no Git com protocolo congelado | Itens acima |

## G5 — Data freeze `data-v1` (13/09, 18:00)

Regra de corte (§8.1): todas as métricas essenciais às RQs têm dados completos.
Pode remover-se uma condição opcional, declarando a limitação; nunca preencher a
lacuna com uma conclusão sem evidência.

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Campanha ARM oficial (§7.1: 5 boots QEMU funcionais, 10 cold starts, 10 criações de twin, 10 execuções nominais, load-sweep 10/50/100/250 msg/s ×10, soak 24 h) | Pendente | `experiments/results/raw/<run_id>/` completos com `SHA256SUMS` | Requer VM ARM; tag `exp-v1` |
| Apenas correções que invalidem experiências; repetir condições afetadas | Pendente | LOG com justificação de cada repetição | — |
| Validar dados e gerar figuras | Pendente | `processed/` + `figures/` regenerados; validação de proveniência (`run_id`/manifesto) | Campanha |
| Redigir setup e limitações (capítulo 5, secções de contexto) | Pendente | Texto em `thesis/` | — |
| Tag `data-v1`; `raw/` imutável | Pendente | Tag no Git; checksums verificados | Campanha completa |

## G6 — Draft integral (18/09)

Regra de corte (§8.1): todos os capítulos, figuras e respostas às RQs existem.
Uma reestruturação estimada acima de 20 h ativa a contingência (§10).

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Capítulos 5–6, Abstract e Resumo com evidência real | Pendente | `thesis/` completo; cada número rastreado na matriz claim→evidência | `data-v1` |
| RQs respondidas apenas com evidência real | Pendente | Matriz claim→evidência sem estados `Pendente` em claims usados no texto | `data-v1` |
| Draft integral enviado aos orientadores em 18/09 | Pendente | Email de envio registado no LOG | Compilação limpa |
| Sem features; apenas reprodução e análise | Pendente | Histórico Git sem commits de feature após G5 | — |

## G7 — Release e aprovação (25/09; `rc1` em 27/09)

Regra de corte (§8.1): PDF conforme, artefacto arquivado e feedback tratado. A
falta de resposta dos orientadores não paralisa o trabalho; seguem-se as últimas
decisões documentadas e registam-se as tentativas de contacto.

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| Smoke final e empacotamento do pacote de reprodutibilidade | Pendente | Arquivo versionado com SHA-256 e localização registada | `data-v1` |
| Tratamento do feedback (prazo solicitado: 23/09) | Pendente | Lista de alterações + respostas registadas | Feedback dos orientadores |
| Linguagem, referências, front matter, consistência e QA visual do PDF | Pendente | Checklist editorial concluída; inspeção página a página | Draft integral |
| Release candidate `rc1` em 27/09 | Pendente | Tag `rc1` + PDF | Itens acima |
| Submissão 29/09 17:00; recibo e tag `v1.0-thesis` | Pendente | Recibo do portal; tag no Git | `rc1` |

## Pós-gate — 28–30/09

| Item | Estado | Evidência esperada | Dependências |
|---|---|---|---|
| 28–29/09: apenas correções bloqueantes; PDF final, metadados e portal | Pendente | Submissão interna a 29/09 17:00 | `rc1` |
| 30/09: reserva exclusivamente administrativa | Pendente | Usar apenas se a submissão interna falhar | — |
