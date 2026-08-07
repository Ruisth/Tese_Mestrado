# Matriz claim→evidência

> Instrumento de integridade exigido pelo plano integrado §6.3: **nenhum valor
> quantitativo entra no PDF final sem dados brutos, comando de execução,
> configuração e caminho de reprodução.** A fonte de dados desta matriz é
> [`claim_evidence_matrix.csv`](claim_evidence_matrix.csv) (mesmas colunas e
> conteúdo); este ficheiro é a vista legível.

## Regras de manutenção

- Cada afirmação verificável da dissertação (capítulos 4–6, Abstract, Resumo)
  recebe um `claim_id` antes de o texto ser escrito.
- Estados de validação permitidos: `Pendente — sem evidência`,
  `Em recolha`, `Validado (run_id + commit)` e `Removido do texto`.
- Um claim só passa a `Validado` quando `ficheiro_evidencia`, `script_analise` e
  `config_commit` apontam para artefactos reais e reproduzíveis (dados em
  `experiments/results/raw/<run_id>/` com `manifest.json` e `SHA256SUMS`).
- Claims que não obtenham evidência até ao data freeze (`data-v1`, 13/09) são
  removidos do texto ou reescritos como limitação — nunca preenchidos com uma
  conclusão sem evidência (plano §8.1, G5).
- Os caminhos e scripts abaixo marcados como `(planeado)` referem artefactos do
  âmbito P0 ainda por produzir; os `run_id` indicados são convenções esperadas.

## Claims semeados (P0)

Todos os claims nascem com estado `Pendente — sem evidência` em 07/08/2026.

| claim_id | Afirmação | Cap. | RQ | Método | Ficheiro de evidência | Script de análise | Config/commit | Estado |
|---|---|---|---|---|---|---|---|---|
| C01 | A imagem `egw-image` é construída de forma reproduzível a partir de um manifesto `kas` com tags/commits exatos fixados (Yocto 5.0.19/Scarthgap), desde um checkout limpo documentado | 4 | RQ1 | Build BitBake desde checkout limpo; log completo; checksums dos artefactos | `experiments/results/raw/g1-build-01/logs/bitbake.log`; `.../SHA256SUMS` | n/a (verificação por log e checksum) | (a preencher) | Pendente — sem evidência |
| C02 | A `egw-image` arranca em `qemuarm64` até systemd, com rede e runtime OCI funcional, de forma repetível (2 boots no G1; 5 na campanha final), incluindo um container de teste | 4 e 5 | RQ1 | Boots QEMU registados em log; container de teste no guest; sem inferência de desempenho | `experiments/results/raw/g1-boot-01/logs/boot{1,2}.log` | n/a (verificação por log) | (a preencher) | Pendente — sem evidência |
| C03 | Todas as imagens OCI da stack (Mosquitto, Ditto `gateway`/`policies`/`things` 3.9.4, MongoDB, controlador) são `linux/arm64` nativas e fixadas por digest | 4 | RQ1 | `docker manifest inspect` por imagem; lockfile de digests versionado | `src/deployment/images.lock.env`; `experiments/results/raw/g1-oci-01/logs/manifest-inspect.log` | n/a (verificação por inspeção) | (a preencher) | Pendente — sem evidência |
| C04 | O tempo até readiness da stack DT na VM ARM64 é medido em 10 cold starts independentes, com média, desvio-padrão e IC95% | 5 | RQ3 | 10 cold starts instrumentados pelo harness; readiness = `GET /ready` 200; unidade estatística = execução | `experiments/results/raw/coldstart-*/manifest.json` e `logs/` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C05 | Um evento de telemetria percorre MQTT (TLS, QoS 1) → controlador → Ditto e o estado resultante é recuperável pela API (vertical slice) | 4 | RQ2 | Trace reproduzível: `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}` | `experiments/results/raw/g2-slice-01/events.jsonl` e `manifest.json` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C06 | Com três wearables concorrentes no cenário nominal (~11,2 msg/s agregados), pelo menos 99% dos eventos válidos enviados são contabilizados ponta a ponta | 5 | RQ2 | 10 execuções nominais de 10 min após 2 min de warm-up; taxa de entrega = confirmações Ditto únicas / mensagens válidas enviadas (plano §7.3) | `experiments/results/raw/nominal-*/events.jsonl` e `manifest.json` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C07 | A latência primária MQTT→confirmação Ditto (p50/p95/p99) é medida no controlador com relógio monotónico no mesmo processo; o `ts` do simulador nunca entra nesta medição | 5 | RQ3 | `latency_ms = (ditto_ack_monotonic_ns − received_monotonic_ns)/1e6`; agregação e percentis por execução | `experiments/results/raw/nominal-*/events.jsonl` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C08 | O `load-sweep` a 10, 50, 100 e 250 msg/s (10 execuções de 5 min por carga, ordem aleatorizada, 2 min de cooldown) identifica a saturação operacional segundo os critérios do plano §7.3 | 5 | RQ3 | Saturação = perda >1%, fila persistente, p95 >1 s ou CPU >90% durante 60 s | `experiments/results/raw/sweep-*/events.jsonl` e `resources.csv` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C09 | CPU e RAM por contentor são recolhidos a cada segundo em todas as execuções cronometradas e reportados por execução | 5 | RQ3 | Amostragem de recursos a 1 Hz pelo harness | `experiments/results/raw/*/resources.csv` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C10 | No cenário `dropout-reconnect` o sistema recupera após perda de ligação: mensagens válidas confirmadas sem duplicados aplicados aos twins e contadores coerentes | 5 | RQ2 | Cenário com QoS 1; verificação de idempotência por `message_id`/`seq`; contadores do controlador | `experiments/results/raw/dropout-*/events.jsonl` e `manifest.json` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C11 | No cenário `invalid-payload`, 100% dos payloads deliberadamente inválidos são rejeitados pela validação JSON Schema antes de qualquer atualização de twin e não contam como perdas | 5 | RQ2 | Eventos marcados `intended_invalid` no registo do simulador cruzados com `outcome=rejected` no controlador | `experiments/results/raw/invalid-*/events.jsonl`; `sent_events.jsonl` do simulador | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C12 | A deteção de duplicados sobrevive a um restart do controlador porque o estado (`last_message_id`, `last_seq`) persiste na feature `ingestion` do twin | 4 e 5 | RQ2 | Restart do controlador a meio de uma execução; reenvio de mensagens já confirmadas; `outcome=duplicate` sem nova escrita | `experiments/results/raw/restart-*/events.jsonl`; teste de integração em `src/tests/` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C13 | O soak nominal de 24 horas termina sem crash não recuperado e sem perda da recolha de métricas; análise descritiva, sem IC próprio | 5 | RQ2 e RQ3 | Execução soak de 24 h com recolha contínua de recursos (plano §7.3) | `experiments/results/raw/soak-01/{events.jsonl,resources.csv,logs/}` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C14 | Dez execuções `smoke` consecutivas terminam com sucesso no ambiente de campanha | 5 | RQ2 | 10 execuções consecutivas do cenário `smoke` pelo harness, todas com verificação E2E | `experiments/results/raw/smoke-01..10/manifest.json` | `src/egw_experiments/` (planeado) | (a preencher) | Pendente — sem evidência |
| C15 | Um único script de análise regenera todas as tabelas e figuras da dissertação a partir de `experiments/results/raw`, sem edição manual | 4 e 5 | RQ1 | Execução do script sobre `raw/` num checkout limpo; diff nulo face aos artefactos publicados | `experiments/results/processed/`; `experiments/results/figures/` | `src/egw_experiments/` (script único, planeado) | (a preencher) | Pendente — sem evidência |
