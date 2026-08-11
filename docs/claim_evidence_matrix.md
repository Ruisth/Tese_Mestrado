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
- Os `run_id` indicados **não são convenções**: são exatamente os identificadores
  que `src/egw_experiments/plan_gen.py` gera a partir das condições congeladas em
  `src/egw_experiments/protocol.py` (`<condicao>-r<NN>`, com o prefixo `qemu_boot`
  para a condição `qemu_boots` e `load_sweep-<taxa:03d>mps-r<NN>` para o sweep).
  Qualquer divergência entre esta matriz e o gerador é um defeito desta matriz.
- Os marcadores `(planeado)` foram removidos das colunas de script em 08/08/2026:
  o caminho de análise (incluindo o das condições externas), os collectors do SUT
  e o amostrador de métricas **existem no repositório**. Isto é uma afirmação
  sobre código, não sobre evidência: **o código existir não valida claim nenhum**,
  pelo que os 15 claims permanecem `Pendente — sem evidência`.
- **Selagem obrigatória da evidência (blocos P5/P5.4).** Antes de um diretório de
  run ser usado para o que quer que seja, o seu `SHA256SUMS` é verificado. Um run
  cuja evidência **não verifique** fica fora de sumários, saturação, aceitação e
  figuras; um run **não selado** de uma condição cronometrada é excluído do mesmo
  modo. A mesma exigência passou a aplicar-se com igual severidade às condições
  **externas** (`timings.json`, C02/C04): só um run com selo **verificado**
  contribui para as estatísticas de duração — não selado e selo falhado são
  ambos excluídos e ambos avisados. Runs fora do protocolo congelado (por exemplo
  o run de bring-up do G2 que sustenta C05) são **assinalados** pela análise, não
  excluídos: para efeitos desta matriz, um run de bring-up não selado **não é
  evidência aceitável** para o claim.
- **Completude por identidade (bloco P5).** A aceitação por condição compara o
  **conjunto de identidades** dos runs válidos — `run_id` mais repetição, seed e
  taxa, por nível de carga no `load_sweep` — com o plano congelado; identidades
  em falta, a mais, duplicadas ou trocadas **falham** o critério e são nomeadas.
  Sem plano, a verificação degrada para contagem e diz expressamente que a
  verificação por identidade **não** foi feita. Requisito operacional
  correspondente (risco R28 em [`g0/riscos.md`](g0/riscos.md)): a análise que
  sustentar estes claims tem de ser corrida pelo comando entregue, com o plano
  congelado efetivamente em uso.
- Nenhuma regra estatística, percentil, método de IC ou a janela de confirmação
  de 60 s foi alterada por estes blocos: mudou a instrumentação e a verificação,
  não o protocolo.

## Claims semeados (P0)

Todos os claims nascem com estado `Pendente — sem evidência` em 07/08/2026 e
mantêm esse estado em 10/08/2026 (15/15). As revisões de 08/08 e 10/08 tornaram
as colunas de método mais exigentes; **nenhuma delas produziu evidência**, porque
`experiments/results/raw/` continua vazio.

### Nota operacional — `twin_creation` (proposta, a confirmar com orientadores)

`twin_creation` é uma condição do plano §7.1 (10 execuções independentes) sem
`claim_id` próprio; alimenta o contexto de C04 (arranque da stack) e C05 (fatia
vertical). **Definição operacional proposta — `proposta — a confirmar com os
orientadores`, não congelada:** cronometrar `twin_creation_time_ms` desde o
**primeiro evento de telemetria de um `device_uuid` desconhecido** (instante de
receção no controlador), passando pela **criação do par `policy` + `thing` no
Ditto** (CONTRACTS §4/§5: policy `org.c2dta:{device_uuid}` e thing criados no
primeiro evento do dispositivo), até o twin ficar **legível por
`GET /twins/{device_id}` com 200**. Marco final = primeira leitura bem-sucedida,
não a resposta do `PATCH`. Enquanto esta definição não for confirmada, nenhum
valor de `twin_creation` entra no texto. Não existe ainda script de medição
desta condição em `src/deployment/scripts/` (ao contrário de
`measure-cold-start.sh`), o que é dependência bloqueante desta medição.

| claim_id | Afirmação | Cap. | RQ | Método | Ficheiro de evidência | Script de análise | Config/commit | Estado |
|---|---|---|---|---|---|---|---|---|
| C01 | A imagem `egw-image` é construída de forma reproduzível a partir de um manifesto `kas` com tags/commits exatos fixados (Yocto 5.0.19/Scarthgap), desde um checkout limpo documentado | 4 | RQ1 | Build BitBake desde checkout limpo; log completo; checksums dos artefactos | `docs/evidence/g1-yocto-qemu/kas-checkout.log`, `kas-build.log`, `image-packages.manifest`, `SHA256SUMS`; imagem sha256 `9e9b8e8c…`; kernel sha256 `4457ef38…` | n/a (verificação por log e checksum) | `build/g1-yocto-qemu` | **Parcial** — build de 5715 tarefas, todas com sucesso, registado e selado (2026-08-11). **Falta a reprodução a partir de um checkout limpo e independente**, que pertence ao G4; até lá o claim não pode ser dado como demonstrado. Aceitação do gate G1: pendente |
| C02 | A `egw-image` arranca em `qemuarm64` até systemd, com rede e runtime OCI funcional, de forma repetível, incluindo um container de teste. **Dois conjuntos distintos e não intermutáveis:** (a) **2 boots de bring-up do G1** (plano §7.1, critério de passagem do gate G1, executados à mão); (b) **5 boots da condição `qemu_boots`** do protocolo congelado, na campanha final | 4 e 5 | RQ1 | (a) boots do G1 registados em log; (b) condição `qemu_boots` ingerida por `run --external-timings`. Em ambos: container de teste dentro do guest e **zero** inferência de desempenho (plano §5.1) | `docs/evidence/g1-yocto-qemu/boot1.log`, `boot1.result.json`, `boot2.log`, `boot2.result.json`, `SHA256SUMS` | `src/yocto/scripts/boot_check.py` @ `32f6604` | `build/g1-yocto-qemu` | **Evidência de bring-up produzida (2026-08-11)** — dois boots, cada um com **6 de 6 asserções obrigatórias aprovadas, 3 de 3 observações suplementares registadas e poweroff limpo confirmado**, pelo driver `src/yocto/scripts/boot_check.py` no commit `32f6604`. As observações não contam como verificação. **Os 5 boots da condição `qemu_boots` da campanha continuam por executar.** Aceitação do gate G1: pendente |
| C03 | Todas as imagens OCI da stack (Mosquitto, Ditto `gateway`/`policies`/`things` 3.9.4, MongoDB, controlador) são `linux/arm64` nativas e fixadas por digest | 4 | RQ1 | `docker manifest inspect` por imagem; lockfile de digests versionado | `src/deployment/images.lock.env`; `experiments/results/raw/g1-oci-01/logs/manifest-inspect.log` | n/a (verificação por inspeção) | (a preencher) | Pendente — sem evidência |
| C04 | O tempo até readiness da stack DT na VM ARM64 é medido em 10 cold starts independentes, com média, desvio-padrão e IC95% | 5 | RQ3 | 10 cold starts medidos na VM por `src/deployment/scripts/measure-cold-start.sh` e ingeridos por `run --external-timings`; readiness = `GET /ready` 200; unidade estatística = execução. **Selagem obrigatória (P5.4):** só um `cold_start-rNN` com `SHA256SUMS` **verificado** contribui para a média/desvio-padrão/IC95%; não selado e selo falhado são ambos excluídos, com aviso, e ficam listados em `external_runs.csv` com a respetiva marca. Ver a nota operacional proposta de `twin_creation` acima | `experiments/results/raw/cold_start-r01/…` … `cold_start-r10/{manifest.json,logs/}` | `src/egw_experiments/analyze.py` (condição externa analisada pelo MESMO script: `summary_by_condition.csv`, `external_runs.csv`) | (a preencher) | Pendente — sem evidência |
| C05 | Um evento de telemetria percorre MQTT (TLS, QoS 1) → controlador → Ditto e o estado resultante é recuperável pela API (vertical slice) | 4 | RQ2 | Trace reproduzível: `sent_events.jsonl` + `events.jsonl` + `GET /twins/{device_id}`. A mesma leitura 200 é o marco final da definição proposta de `twin_creation` (nota acima). **Selagem obrigatória:** por ser um run de bring-up fora do protocolo congelado, a análise **assinala** (não exclui) um diretório não selado — a exigência é desta matriz: sem `SHA256SUMS` gerado no fim da recolha e verificável, o trace não conta como evidência de C05 | `experiments/results/raw/g2-slice-01/events.jsonl` e `manifest.json` (run de bring-up do G2, fora do plano congelado) | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C06 | Com três wearables concorrentes no cenário nominal (~11,2 msg/s agregados), pelo menos 99% dos eventos válidos enviados são contabilizados ponta a ponta | 5 | RQ2 | 10 execuções nominais de 10 min após 2 min de warm-up; taxa de entrega = confirmações Ditto únicas / mensagens válidas enviadas (plano §7.3) | `experiments/results/raw/nominal-r01/…` … `nominal-r10/{events.jsonl,manifest.json}` | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C07 | A latência primária MQTT→confirmação Ditto (p50/p95/p99) é medida no controlador com relógio monotónico no mesmo processo; o `ts` do simulador nunca entra nesta medição | 5 | RQ3 | `latency_ms = (ditto_ack_monotonic_ns − received_monotonic_ns)/1e6`; agregação e percentis por execução | `experiments/results/raw/nominal-r01/events.jsonl` … `nominal-r10/events.jsonl` | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C08 | O `load-sweep` a 10, 50, 100 e 250 msg/s (10 execuções de 5 min por carga, ordem aleatorizada, 2 min de cooldown) identifica a saturação operacional segundo os critérios do plano §7.3 | 5 | RQ3 | Saturação = perda >1%, fila persistente, p95 >1 s ou CPU >90% durante 60 s | `experiments/results/raw/load_sweep-{010,050,100,250}mps-r01..r10/{events.jsonl,resources.csv}` (40 runs) | `src/egw_experiments/analyze.py` (`saturation.json`, `summary_by_condition.csv`) | (a preencher) | Pendente — sem evidência |
| C09 | CPU e RAM por contentor são recolhidos a cada segundo em todas as execuções cronometradas e reportados por execução | 5 | RQ3 | Amostragem a 1 Hz pelo collector do SUT (`src/deployment/scripts/collect-resources.sh`), ingerida por `run --resources-from` | `resources.csv` de cada execução cronometrada: `smoke_sequence-r01..r10`, `nominal-r01..r10`, `load_sweep-{010,050,100,250}mps-r01..r10`, `invalid_payload-r01..r03`, `dropout_reconnect-r01..r03`, `controller_restart-r01..r03`, `soak-r01` | `src/egw_experiments/analyze.py` (`resources_by_run.csv`, `per_run.csv`) | (a preencher) | Pendente — sem evidência |
| C10 | No cenário `dropout-reconnect` o sistema recupera após perda de ligação: mensagens válidas confirmadas sem duplicados aplicados aos twins e contadores coerentes | 5 | RQ2 | Condição `dropout_reconnect` (3 execuções de 600 s; desconexão MQTT real com buffer no dispositivo, QoS 1); contabilização tolerante a reentrega em buffer dentro da janela de 60 s; aceitação (zero perdidas, zero double-accepted, desconexões reais em cada execução — totals `dropout_disconnects`/`buffered_dropout` >= 1 do manifesto do simulador — e reconciliação do contador `accepted` com `controller_metrics.csv`; work order P1b) em `acceptance_by_condition.csv` | `experiments/results/raw/dropout_reconnect-r01..r03/{events.jsonl,manifest.json}` | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C11 | No cenário `invalid-payload`, 100% dos payloads deliberadamente inválidos são rejeitados pela validação JSON Schema antes de qualquer atualização de twin e não contam como perdas | 5 | RQ2 | Condição `invalid_payload` (3 execuções de 300 s à taxa nominal); eventos `intended_invalid` do simulador cruzados com `outcome=rejected`; aceitação (todos rejeitados, zero aceites; entrega dos válidos conforme plano §7.3) em `acceptance_by_condition.csv` | `experiments/results/raw/invalid_payload-r01..r03/{events.jsonl,sent_events.jsonl}` | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C12 | A deteção de duplicados sobrevive a um restart do controlador porque o estado (`last_message_id`, `last_seq`) persiste na feature `ingestion` do twin | 4 e 5 | RQ2 | Condição `controller_restart` (3 execuções nominais de 600 s com restart a meio via `--restart-cmd`/`--restart-at-s` do harness, registado no manifesto); aceitação (registo do hook executado com timestamps e exit 0 em cada execução, entrega através do restart, zero `message_id` double-accepted; work order P1b) em `acceptance_by_condition.csv`. **Evidência de recuperação real (bloco P5):** um hook com exit 0 prova que um comando correu, não que o controlador caiu e voltou; por isso a aceitação exige, calculado de `controller_metrics.csv` em torno dos instantes do restart: (a) **indício de indisponibilidade** — buraco de amostragem superior ao cap de cadência a cavalo do restart (uma leitura falhada não escreve linha, logo os buracos SÃO a evidência) ou reposição do contador `accepted`; (b) **recuperação limitada** — a primeira amostra após o fim do restart dentro de `RESTART_RECOVERY_MAX_S` (`protocol.py`, **pendente de aprovação do orientador** antes de `exp-v1`); (c) **progresso** — o contador `accepted` cresce depois do restart. Sem a série ou sem o registo do restart, os critérios **falham** por instrumentação insuficiente, nunca ficam em branco | `experiments/results/raw/controller_restart-r01..r03/{events.jsonl,manifest.json}`; teste de integração live em `src/tests/` (**por criar** — pré-requisito de G3) | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C13 | O soak nominal de 24 horas termina sem crash não recuperado e sem perda da recolha de métricas; análise descritiva, sem IC próprio | 5 | RQ2 e RQ3 | Execução soak de 24 h com recolha contínua de recursos (plano §7.3); Definition of Done em `acceptance_by_condition.csv`: janela medida >= 24 h; `resources.csv` e `controller_metrics.csv` com cobertura >= 99% da janela sem gaps > 60 s **e sem head gap > 60 s** (bloco P5: uma série que só começa a amostrar bem dentro da janela não é evidência contínua) e com um mínimo de instantes distintos válidos dentro da janela; sem interrupção não recuperada (sem gap > 120 s nas métricas, última amostra a <= 120 s do fim); limiares pendentes de aprovação do orientador antes de `exp-v1` (work order P1b) | `experiments/results/raw/soak-r01/{events.jsonl,resources.csv,controller_metrics.csv,logs/}` | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C14 | Dez execuções `smoke` consecutivas terminam com sucesso no ambiente de campanha | 5 | RQ2 | Condição `smoke_sequence`: 10 execuções `smoke` consecutivas pelo harness, todas com exit code 0 e zero mensagens válidas perdidas; aceitação em `acceptance_by_condition.csv` | `experiments/results/raw/smoke_sequence-r01..r10/manifest.json` | `src/egw_experiments/analyze.py` | (a preencher) | Pendente — sem evidência |
| C15 | Um único script de análise regenera todas as tabelas e figuras da dissertação a partir de `experiments/results/raw`, sem edição manual | 4 e 5 | RQ1 | Execução de `python -m egw_experiments analyze` sobre `raw/` num checkout limpo — **o comando tal como é entregue**, com o plano congelado efetivamente em uso (risco R28), e não uma invocação equivalente por API; diff nulo face aos artefactos publicados; as condições externas (`qemu_boots`, `cold_start`, `twin_creation`) são ingeridas via `run --external-timings` e analisadas pelo MESMO script (`summary_by_condition.csv`, `external_runs.csv`) | `experiments/results/processed/`; `experiments/results/figures/` | `src/egw_experiments/analyze.py` (script único) | (a preencher) | Pendente — sem evidência |
