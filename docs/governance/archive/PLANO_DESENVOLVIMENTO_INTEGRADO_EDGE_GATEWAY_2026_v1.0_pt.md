# Plano integrado da tese Edge Gateway — 07/08/2026 a 30/09/2026

> **Estado: NORMATIVO.** Este documento é a fonte de verdade para âmbito, execução,
> cronograma, gates, cortes e evidências da tese. Em caso de conflito com planos
> anteriores, prevalece este documento.

**Versão:** 1.0 — 07/08/2026  
**Prazo oficial:** 30/09/2026  
**Prazo interno de submissão:** 29/09/2026, 17:00 Europe/Lisbon  
**Extensão máxima de contingência:** 31/10/2026  
**Carga de trabalho:** 40 h/semana como referência; 35 h mínimo; 45 h máximo  
**Idioma da dissertação:** inglês, mantendo o Resumo em português se o template o exigir

---

## 1. Como usar e manter este plano

- Atualizar este ficheiro no final de cada dia de trabalho, indicando decisões,
  bloqueios, evidências produzidas e estado do gate seguinte.
- Usar apenas os estados `Pendente`, `Em curso`, `Bloqueado`, `Concluído` e
  `Cortado`.
- Não declarar uma tarefa concluída sem uma evidência verificável: commit, log,
  ficheiro de dados, screenshot, PDF, resultado de teste ou ata de decisão.
- Não alterar retrospectivamente dados brutos ou critérios experimentais depois do
  data freeze. Correções produzem uma nova versão identificada.
- Tratar os seguintes documentos como históricos e não normativos:
  - [`Plano_Tese_EdgeGateway_v2.md`](Plano_Tese_EdgeGateway_v2.md);
  - [`egw_project/DEVELOPMENT_PLAN.md`](egw_project/DEVELOPMENT_PLAN.md);
  - [`egw_project/docs/fase3_plano_desenvolvimento.md`](egw_project/docs/fase3_plano_desenvolvimento.md).
- Preservar os planos históricos como registo das decisões anteriores. Não os usar
  para reintroduzir funcionalidades cortadas.

### Estado inicial em 07/08/2026

| Elemento | Estado | Evidência/observação |
|---|---|---|
| Plano integrado | Concluído | Este documento, versão 1.0 |
| Repositório Git | Pendente | Não foram detetados metadados Git na raiz durante a auditoria de 07/08 |
| Linux/Yocto toolchain | Pendente | WSL2 só apresenta `docker-desktop`; não existe Ubuntu, `kas`, BitBake ou QEMU ARM configurado |
| EGW-OS reproduzível | Pendente | Existem apenas a layer e a receita de imagem iniciais |
| Stack DT | Pendente | Compose atual não inclui Eclipse Ditto/MongoDB |
| Controlador MQTT→Ditto | Pendente | API FastAPI e webhook são scaffolding |
| Simulador unificado | Pendente | Existem três scripts independentes e rígidos |
| Testes e campanha | Pendente | Não existem testes, harness, dados brutos ou análise reproduzível |
| Dissertação | Em curso | Estrutura de seis capítulos existente, mas ainda muito preliminar |

---

## 2. Resumo executivo e viabilidade

A entrega em setembro é viável apenas com um núcleo focado:

1. EGW-OS construído com Yocto/Scarthgap e validado funcionalmente em QEMU;
2. stack de gémeos digitais executada numa VM ARM64 nativa;
3. simulador CLI para três tipos de wearable;
4. avaliação experimental rastreável e reproduzível;
5. dissertação completa em inglês, baseada exclusivamente em evidência real.

O plano base requer aproximadamente **275 horas**. À capacidade-alvo de 40
horas/semana existem cerca de **316 horas** até 30/09. As 41 horas adicionais não
são âmbito garantido; são consumidas, por esta ordem:

As semanas completas reservam **35 h P0 + 5 h condicionais**; os blocos parciais de
07–09/08 e 28–30/09 reservam **15 h P0 + 3 h condicionais**. Assim, o cronograma
totaliza exatamente 275 h de base e 41 h de capacidade condicional.

| Uso condicional | Limite |
|---|---:|
| ACA-Py/DIDComm mínimo, se autorizado pelo gate G3 | 12 h |
| Robustez e correções técnicas | 8 h |
| Revisão bibliográfica e editorial adicional | 13 h |
| Experiências adicionais não essenciais | 4 h |
| Reserva real | 4 h |

Se a disponibilidade real ficar nas 35 horas/semana, toda esta parcela adicional é
cortada, começando por ACA-Py e pela comparação x86 opcional.

---

## 3. Diagnóstico consolidado

- Não existe um ficheiro explicitamente identificado como plano produzido pelo
  Claude. O plano v2.3 da raiz é tratado como o candidato principal, complementado
  pelos dois planos históricos do projeto.
- O plano v2.3 contém princípios válidos — escrita paralela, QEMU-first, timeboxes e
  independência de outras teses — mas começou em julho e os primeiros marcos já
  passaram.
- Os planos antigos colocam Indy, credenciais, IPFS e Fabric no caminho crítico, em
  conflito com o âmbito reduzido necessário para setembro.
- A implementação atual é um protótipo inicial: três emuladores rígidos, controlador
  FastAPI incompleto, composição sem Eclipse Ditto, integração MQTT→Ditto ausente,
  layer Yocto sem build reproduzível e ausência de testes, CI, resultados e scripts
  de benchmark.
- A dissertação ativa é [`dissertation/main.tex`](dissertation/main.tex), tem cerca
  de 3 100 palavras de corpo e inclui resultados quantitativos sobre Raspberry Pi
  5/ARM sem dados brutos, scripts ou logs correspondentes. Estes valores têm de ser
  removidos ou claramente marcados como provisórios antes de qualquer revisão.
- O artigo C2DTA avalia um smartwatch a 1 Hz numa VM x86. Não demonstra Yocto, ARM,
  Raspberry Pi, três wearables, stress, consumo de recursos ou estabilidade durante
  24 horas. Estas diferenças constituem trabalho novo da tese.
- A compilação LaTeX atual funciona, mas apresenta problemas bibliográficos,
  destinos duplicados, conteúdo fora das margens, lista de figuras vazia e
  inconsistências linguísticas.
- O DOCX foi analisado estruturalmente e textualmente, incluindo a imagem embebida.
  A inspeção visual página a página deve ser repetida quando existir LibreOffice no
  ambiente.
- O ficheiro `EdgeGateway_Paper.pdf` é um PDF válido, não um ZIP. O registo do projeto
  deve ser corrigido para não perpetuar esta classificação incorreta.

---

## 4. Objetivo, questões de investigação e âmbito

### 4.1 Objetivo

Conceber, implementar e avaliar um Edge Gateway ARM64 reproduzível, baseado em
Yocto e serviços contentorizados, capaz de receber telemetria sintética concorrente
de três wearables, validar os eventos e materializá-los como gémeos digitais no
Eclipse Ditto.

### 4.2 Questões de investigação definitivas

1. **RQ1:** *How can a reproducible Yocto-based ARM64 edge gateway be designed to
   host containerised digital-twin services?*
2. **RQ2:** *To what extent can the gateway ingest and materialise concurrent
   synthetic telemetry from three wearable-device types correctly and reliably?*
3. **RQ3:** *What latency, throughput and resource-consumption trade-offs constrain
   deployment of the proposed platform on an ARM64 edge-class environment?*

ACA-Py e SSI não são necessários para responder a qualquer RQ.

### 4.3 Âmbito obrigatório — P0

- Ambiente Linux reproduzível, controlo de versões e matriz claim→evidência.
- Yocto Project **5.0.19/Scarthgap**, com tags e commits exatos fixados num manifesto
  `kas`, sem depender do HEAD de branches móveis. Scarthgap é
  a linha LTS suportada até abril de 2028 segundo a
  [documentação oficial](https://docs.yoctoproject.org/scarthgap/_static/theyoctoproject.pdf).
- Imagem `egw-image` construída e arrancada em `qemuarm64`, com systemd, rede e
  runtime OCI funcional.
- Stack ARM64 mínima com Mosquitto, Eclipse Ditto 3.9.4 (`gateway`, `policies` e
  `things`), MongoDB e controlador MQTT→Ditto; `search`, `connectivity` e UI ficam
  excluídos enquanto não forem necessários às RQs. Todas as imagens e dependências
  transitivas devem ser verificadas como `linux/arm64` e fixadas por digest.
  Referências: [Ditto 3.9.4](https://eclipse.dev/ditto/release_notes_394.html)
  e [imagens Ditto](https://hub.docker.com/r/eclipse/ditto-gateway/tags).
- Simulador unificado por CLI para smartwatch, smart ring e smart clothing.
- Cenários `smoke`, `nominal`, `load-sweep`, `dropout-reconnect`,
  `invalid-payload` e `soak`.
- Testes unitários, integração, E2E, recuperação, carga e estabilidade de 24 horas.
- Campanha experimental numa VM ARM64 temporária.
- Dissertação completa em inglês, com Resumo em português se exigido.
- Pacote de reprodutibilidade com código, configurações, logs, dados, checksums e
  script de análise.

### 4.4 Âmbito condicional — P1

ACA-Py só pode avançar depois do gate G3, com timebox máximo total de 12 horas:

- usar a imagem `ghcr.io/openwallet-foundation/acapy-agent:py3.13-1.6-lts`, fixada
  pelo digest verificado para ARM64, e `askar-anoncreds` em vez do wallet `askar`
  depreciado; seguir as imagens atuais descritas no
  [site oficial](https://aca-py.org/main/) e na
  [documentação de contentores](https://aca-py.org/main/deploying/ContainerImagesAndGithubActions/);
- confirmar suporte ARM64 antes de qualquer implementação;
- executar dois agentes locais, `did:peer`, convite Out-of-Band e uma mensagem
  DIDComm básica;
- não usar ledger público, Indy, emissão de credenciais ou lógica de propriedade;
- cortar imediatamente se não existir imagem ARM64, se algum gate P0 estiver
  vermelho ou se terminar o timebox.

### 4.5 Fora de âmbito

- Hyperledger Indy, Fabric, IPFS como armazenamento obrigatório, marketplace,
  transferência de propriedade, credenciais verificáveis de negócio, AI/MAS,
  interface gráfica, dashboard, Bluetooth, OTA, LUKS, consumo energético e
  avaliação num Raspberry Pi físico.
- Mais de três tipos de dispositivo.
- Artigo científico e preparação detalhada da defesa antes da submissão. Se a tese
  for entregue em setembro, outubro pode ser usado para esses trabalhos sem reabrir
  o artefacto submetido.

---

## 5. Arquitetura e interfaces normativas

### 5.1 Ambiente e implantação

- Instalar Ubuntu 24.04 LTS no WSL2 e validar que o diretório de build reside no seu
  filesystem Linux/ext4. O estado inicial contém apenas `docker-desktop`, sem uma
  distribuição adequada, `kas`, BitBake ou QEMU ARM.
- Manter os fontes no workspace, mas executar builds Yocto nesse filesystem Linux,
  fora de Nextcloud/NTFS.
- Criar um manifesto `kas` para `qemuarm64`. Uma configuração Raspberry Pi 5 pode
  ser documentada num overlay separado, mas não é validada nem sustenta alegações.
  A receita base QEMU não inclui `hwcodecs` ou outros pacotes específicos de Pi.
- Usar durante toda a campanha uma VM Hetzner CAX21 ou equivalente com ARM64
  nativo, 4 vCPU, 8 GiB de RAM e pelo menos 80 GB de disco. Registar fornecedor,
  região, CPU exposta, kernel, sistema operativo e a limitação de CPU partilhado.
  Referência: [Hetzner Cloud](https://www.hetzner.com/cloud/?pk_content=VBVO47VycYLt).
- Usar QEMU exclusivamente para build, boot, systemd, rede e validação funcional.
  Não produzir conclusões de desempenho baseadas em QEMU.
- Executar o simulador fora da VM ARM durante benchmarks. A métrica primária de
  latência é medida no controlador entre a receção MQTT e a confirmação HTTP do
  Ditto, evitando incluir a ligação externa na medição do processamento do gateway.

### 5.2 MQTT

- Porta `8883`, TLS, autenticação e QoS 1.
- Tópico normativo: `c2dt/{egw_id}/{device_uuid}/telemetry`.
- O broker não permite acesso anónimo externo.

### 5.3 Envelope comum de evento

Cada schema de dispositivo mantém os seus campos de medição e acrescenta:

| Campo | Tipo/regra |
|---|---|
| `schema_version` | string de versão do schema |
| `run_id` | identificador imutável da execução experimental |
| `message_id` | UUID v5 derivado de `run_id`, `device_uuid` e `seq` |
| `seq` | inteiro monotónico por dispositivo |
| `ts` | timestamp UTC em RFC 3339 |
| `egw_id` | identificador do gateway |
| `device_uuid` | identificador estável do dispositivo |
| `device_type` | `smartwatch`, `smart_ring` ou `smart_clothing` |

### 5.4 Gémeos Ditto

- Identificador: `org.c2dta:{device_uuid}`.
- Atualização idempotente: rejeitar `message_id` repetido e `seq` não crescente.
- Guardar no twin o último `message_id` e `seq` confirmados, permitindo recuperar o
  controlo de duplicados depois de um restart do controlador.
- Propriedades organizadas por feature do respetivo dispositivo.

### 5.5 Controlador

- Subscrição MQTT assíncrona.
- Validação obrigatória por JSON Schema antes de atualizar o twin.
- Conversão e atualização do Ditto por HTTP.
- Retry limitado, logging estruturado e contadores de eventos aceites, rejeitados,
  duplicados e falhados.
- Endpoints mínimos:
  - `GET /health`: processo ativo;
  - `GET /ready`: MQTT e Ditto acessíveis;
  - `GET /twins/{device_id}`: leitura do twin normalizada pelo controlador.

### 5.6 Simulador

Interface de referência:

```text
python -m simulator run --scenario nominal --seed 42 \
  --broker <host> --duration 600 --rate 11.2 --output <dir>
```

- Seed, taxa, duração, TLS, QoS, número de dispositivos e output são explícitos ou
  gravados no manifesto.
- `--rate` representa a taxa agregada. Nos cenários com três dispositivos, essa taxa
  é repartida proporcionalmente pelas frequências nominais `1:0,2:10`; assim,
  `--rate 11.2` corresponde a 1 msg/s do smartwatch, 0,2 msg/s do ring e 10 msg/s
  do smart clothing.
- Os perfis são determinísticos para a mesma seed.
- Cada payload é validado localmente antes de ser publicado, exceto no cenário
  `invalid-payload`, que marca intencionalmente os eventos de teste.

### 5.7 WoT

- Atualizar os Thing Descriptions para WoT TD 1.1 e contexto
  `https://www.w3.org/2022/wot/td/v1.1`.
- Adicionar `forms`, eliminar `nosec` quando TLS estiver ativo e alinhar propriedades
  com os JSON Schemas.

### 5.8 Estrutura de evidência

```text
results/
├── raw/<run_id>/
│   ├── events.jsonl
│   ├── resources.csv
│   ├── manifest.json
│   ├── logs/
│   └── SHA256SUMS
├── processed/
└── figures/
```

Cada `events.jsonl` regista pelo menos `run_id`, `message_id`, `seq`,
`received_monotonic_ns`, `ditto_ack_monotonic_ns`, `latency_ms`, `outcome`,
`attempts` e erro, quando exista. Cada `manifest.json` regista cenário, seed, commit,
digests OCI, ambiente, configuração, timestamps, versão do protocolo e eventuais
critérios de exclusão.

Dados em `raw/` tornam-se imutáveis no data freeze; processados e figuras são sempre
regenerados por um único script. Código, configuração, dissertação e manifestos
entram no repositório Git da raiz. Os dados brutos volumosos ficam fora do histórico
Git normal, mas são preservados num arquivo versionado com SHA-256 e localização
registada no manifesto/release.

---

## 6. Plano da dissertação

### 6.1 Estrutura e conteúdo

| Capítulo | Conteúdo obrigatório | Alvo indicativo |
|---|---|---:|
| 1 — Introduction | Problema, motivação, lacuna, RQs, objetivos, contribuições e delimitação | 2 500–3 000 palavras |
| 2 — Background and Related Work | Edge, digital twins, IoT/wearables, Yocto, contentores, MQTT, WoT e SSI apenas como contexto | 6 000–7 000 |
| 3 — Research Methodology | DSR, protocolo da revisão, requisitos, matriz RQ→método→métrica e protocolo experimental | 4 000–5 000 |
| 4 — Architecture and Implementation | Arquitetura real, interfaces, decisões, EGW-OS, plataforma, simulador, segurança e reprodutibilidade | 5 000–6 000 |
| 5 — Evaluation and Discussion | Resultados reais, comparação, respostas às RQs e ameaças à validade | 5 000–6 000 |
| 6 — Conclusions and Future Work | Contribuições demonstradas, limitações e trabalho futuro | 1 500–2 000 |

O objetivo global de 25 000–30 000 palavras é indicativo e fica subordinado às
regras oficiais e à qualidade da evidência. Abstract, resultados, discussão e
conclusão só recebem números definitivos depois do data freeze.

### 6.2 Revisão de literatura

- Designar o método como **structured scoping/narrative review**, não como SLR
  completa.
- Registar strings de pesquisa, datas, bases, critérios de inclusão/exclusão,
  deduplicação e snowballing.
- Pesquisar IEEE Xplore, ACM Digital Library e Scopus ou Web of Science.
- Usar pelo menos 30 fontes verificadas, privilegiando artigos primários, normas e
  documentação oficial.
- Corrigir a entrada de Morabito, os metadados de OpenTwins, a publicação final do
  C2DTA e qualquer fonte não verificada proveniente do compass.
- Não usar afirmações absolutas como “não existem estudos” sem as limitar à pesquisa
  efetivamente executada.

### 6.3 Integridade claim→evidência

Manter uma matriz com as colunas `claim_id`, afirmação, capítulo, RQ, método,
ficheiro de evidência, script de análise, configuração/commit e estado de validação.
Nenhum valor quantitativo entra no PDF final sem dados brutos, comando de execução,
configuração e caminho de reprodução.

---

## 7. Protocolo experimental

### 7.1 Condições

- Os dois boots de G1 são bring-up preliminar; a campanha final repete cinco boots
  QEMU para consistência funcional, sem inferência de desempenho.
- Dez cold starts da stack ARM.
- Dez criações independentes de twin.
- Dez execuções nominais de dez minutos depois de dois minutos de warm-up.
- `load-sweep` a 10, 50, 100 e 250 msg/s, com dez execuções de cinco minutos por
  carga, ordem aleatorizada e dois minutos de cooldown.
- Um `soak` nominal de 24 horas.
- Recolher CPU e RAM a cada segundo em todas as execuções cronometradas.

### 7.2 Métricas

- Tempo até readiness da stack.
- Latência MQTT→confirmação Ditto: p50, p95 e p99.
- Eventos aceites, rejeitados, duplicados e perdidos.
- Throughput sustentável.
- CPU e RAM por contentor.
- Recuperação após restart/reconnect.
- Estabilidade durante o soak.

### 7.3 Estatística e validade

- `enviada`: mensagem válida que o cliente entregou ao publish MQTT; `recebida`:
  callback observado pelo controlador; `duplicada`: `message_id` já processado;
  `rejeitada`: falha deliberada ou real de validação; `confirmada`: atualização Ditto
  respondeu com sucesso; `perdida`: mensagem válida enviada sem confirmação única
  até 60 segundos após o fim da execução.
- A taxa de entrega é `confirmações Ditto únicas / mensagens válidas enviadas`.
  Payloads deliberadamente inválidos e corretamente rejeitados não contam como
  perdas.
- A latência primária é calculada por
  `(ditto_ack_monotonic_ns - received_monotonic_ns) / 1e6` no mesmo processo; o
  campo `ts` do simulador não é usado nessa medição.
- A unidade estatística é cada execução independente, não cada mensagem.
- Reportar média, desvio-padrão e IC95%; acrescentar mediana e percentis para
  distribuições assimétricas.
- O soak é analisado descritivamente e não recebe um intervalo de confiança próprio.
- Saturação operacional é a primeira carga em que ocorra pelo menos uma condição:
  perda superior a 1%, crescimento persistente da fila, p95 superior a 1 segundo ou
  CPU sustentada acima de 90% durante 60 segundos.
- Excluir apenas falhas comprovadas da cloud, instrumentação ou configuração. Uma
  execução lenta nunca é excluída apenas pelo resultado.
- Tratar aproximadamente 11,2 msg/s como cenário nominal, não como capacidade máxima
  previamente demonstrada.

---

## 8. Cronograma e gates

| Período | Horas | Plataforma e simulador | Dissertação e evidência | Gate verificável |
|---|---:|---|---|---|
| **07–09/08** | 15 + 3 | Inicializar/associar Git; instalar Ubuntu 24.04 WSL2 em ext4; baseline; evidência; pedir VM ARM; backlog e riscos | Remover/quarentenar resultados sem evidência; fechar RQs, âmbito e matriz claim→evidência | **G0:** âmbito enviado aos orientadores; regras da extensão pedidas |
| **10–16/08** | 35 + 5 | VM ARM congelada; manifesto `kas`; build e dois boots de `egw-image`; systemd, rede e runtime OCI; verificar arquiteturas OCI | Introdução/RQs em revisão; protocolo da revisão e bibliografia auditada | **G1 — 16/08:** QEMU funcional e container de teste executado |
| **17–23/08** | 35 + 5 | Compose ARM64 mínimo; Mosquitto TLS; Ditto/MongoDB; vertical slice smartwatch→MQTT→controlador→Ditto; CLI `smoke`; testes iniciais | Capítulos 1–2; metodologia iniciada; diagrama lógico | **G2 — 23/08:** evento consultável no Ditto com trace reproduzível |
| **24–30/08** | 35 + 5 | Três wearables; todos os cenários; reconnect/backpressure; métricas; harness; testes; soak piloto | Capítulo 3 e primeira versão do 4; ADRs e diagramas | **G3 — 30/08:** feature freeze P0 e decisão automática sobre ACA-Py |
| **31/08–06/09** | 35 + 5 | Reprodução desde checkout limpo; correções P0/P1; ACA-Py apenas se autorizado e até 03/09; piloto completo | Capítulos 1–4 completos; esqueleto integral da avaliação | **G4 — 06/09:** protocolo congelado e tag `exp-v1` |
| **07–13/09** | 35 + 5 | Campanha ARM oficial; apenas correções que invalidem experiências; repetir condições afetadas | Redigir setup e limitações; validar dados e gerar figuras | **G5 — 13/09 18:00:** data freeze `data-v1` |
| **14–20/09** | 35 + 5 | Sem features; apenas reprodução e análise | Capítulos 5–6, Abstract e Resumo; draft integral enviado em 18/09 | **G6 — 18/09:** RQs respondidas apenas com evidência real |
| **21–27/09** | 35 + 5 | Smoke final, empacotamento e release candidate | Feedback, linguagem, referências, front matter, consistência e visual QA | **G7:** aprovação pretendida em 25/09; `rc1` em 27/09 |
| **28–29/09** | 12 + 2 | Apenas correções bloqueantes | PDF final, metadados e portal | Submissão **29/09 17:00**; recibo e tag `v1.0-thesis` |
| **30/09** | 3 + 1 | Nenhuma tarefa normal | Reserva exclusivamente para recuperação administrativa | Prazo oficial; usar apenas se a submissão interna falhar |

### 8.1 Regras de corte por gate

- **G0 — 10/08:** VM criada e acesso `aarch64` validado. Sem VM nesse dia, mudar de
  fornecedor; sem VM em 12/08, comunicar risco.
- **G1 — 16/08:** imagem própria arranca duas vezes e executa um container. Se falhar,
  reduzir a imagem ao sistema mínimo com runtime e mover o deploy para script externo.
  Sem imagem funcional em 20/08, discutir extensão/reformulação.
- **G2 — 23/08:** um payload percorre MQTT→controlador→Ditto e é recuperado pela API.
  Se falhar, cortar APIs auxiliares e toda a identidade. Sem E2E em 25/08, declarar
  risco sério para setembro.
- **G3 — 30/08:** ACA-Py só avança se build/boot QEMU, deploy ARM limpo, três
  dispositivos, cenários, testes, métricas e soak estiverem completos e sem defeitos
  P0. Cortar ao fim de 12 h ou em 03/09, o que ocorrer primeiro.
- **G4 — 06/09:** todos os pilotos produzem dados válidos e o script de análise gera
  tabelas/figuras. Depois deste gate não se alteram métricas, condições ou critérios
  de exclusão.
- **G5 — 13/09:** todas as métricas essenciais às RQs têm dados completos. Pode ser
  removida uma condição opcional, declarando a limitação; nunca preencher a lacuna
  com uma conclusão sem evidência.
- **G6 — 18/09:** todos os capítulos, figuras e respostas às RQs existem. Uma
  reestruturação estimada acima de 20 h ativa a contingência.
- **G7 — 25/09:** PDF conforme, artefacto arquivado e feedback tratado. A falta de
  resposta dos orientadores não paralisa o trabalho; seguem-se as últimas decisões
  documentadas e registam-se as tentativas de contacto.

### 8.2 Marcos com os orientadores

- **10/08:** âmbito, RQs, ausência de hardware, separação QEMU/ARM cloud, cortes e
  regras administrativas.
- **17/08:** Introdução, lacuna, arquitetura e protocolo.
- **31/08:** demonstração do núcleo e decisão ACA-Py.
- **07/09:** validação do protocolo congelado.
- **18/09:** draft integral.
- **23/09:** prazo solicitado para feedback final.
- **25/09:** fecho académico e administrativo.

---

## 9. Testes e critérios de aceitação

### 9.1 Testes

- Unitários: geração determinística, seed, sequências, schemas, limitação de taxa e
  payloads inválidos.
- Integração: TLS/QoS1, MQTT→controlador→Ditto, duplicados, reconnect, retry e restart
  dos serviços.
- E2E: três dispositivos concorrentes e estado final correto nos três twins.
- Plataforma: build limpo, dois boots QEMU, systemd, rede e runtime OCI.
- Robustez: dez `smoke` consecutivos, falhas/restarts e soak de 24 horas.
- Reprodutibilidade: um script regenera tabelas e figuras a partir de `results/raw`.
- Dissertação: compilação LaTeX, referências, paginação, margens, figuras, metadados e
  inspeção visual de todas as páginas.

### 9.2 Aceitação final

- Um checkout documentado constrói `egw-image`, arranca em QEMU, chega a systemd e
  executa o runtime de contentores.
- O deploy ARM usa apenas imagens ARM64 nativas com versões/digests fixados.
- Os três wearables produzem eventos válidos face aos schemas e TDs.
- Dez execuções `smoke` consecutivas terminam com sucesso.
- O cenário nominal contabiliza pelo menos 99% dos eventos ponta a ponta.
- O soak termina sem crash não recuperado e sem perda da recolha de métricas.
- Todos os testes unitários e de integração passam.
- Dados, manifestos, checksums e análise reproduzem todas as tabelas e figuras.
- Secrets, certificados privados e passwords não entram no controlo de versões;
  existe `.env.example`.
- A dissertação não contém números inventados, placeholders finais, referências
  quebradas ou alegações não demonstradas sobre Pi 5, segurança, SSI ou blockchain.
- O PDF final não contém conteúdo relevante fora das margens.
- Código, documentação, dados, release e comprovativo de submissão ficam arquivados.

---

## 10. Contingência até 31/10/2026

A extensão é pedida no primeiro gate que torne setembro irrealista e nunca apenas no
fim do mês. O procedimento, aprovações obrigatórias e a data-limite institucional são
confirmados até 10/08 e prevalecem sobre qualquer data interna; na ausência de uma
data oficial anterior, o pedido é iniciado no máximo em 18/09.

Ativadores principais:

- ausência de imagem QEMU funcional em 20/08;
- ausência de vertical slice em 25/08;
- núcleo não congelado em 30/08 com mais de dois dias de trabalho restante;
- piloto inválido em 06/09;
- dados essenciais incompletos em 13/09;
- draft integral inexistente em 18/09.

Se a contingência for ativada:

| Período | Resultado obrigatório |
|---|---|
| **01–04/10** | Diagnóstico, nova baseline e remoção de ACA-Py |
| **05–11/10** | Última correção do núcleo e feature freeze definitivo |
| **12–18/10** | Repetição das experiências afetadas e `data-v2` |
| **19–25/10** | Reescrita e revisão final |
| **26–29/10** | Release, arquivo e submissão |
| **30–31/10** | Reserva exclusivamente administrativa |

A extensão nunca reintroduz Indy, Fabric, IPFS, marketplace, UI ou outras funções
cortadas.

---

## 11. Riscos e mitigação

| Risco | Sinal antecipado | Mitigação/decisão |
|---|---|---|
| Falta de hardware Raspberry Pi | Hardware continua indisponível | QEMU funcional + VM ARM nativa; excluir alegações de hardware físico |
| Build Yocto lento ou instável | G1 em risco | WSL2 em filesystem Linux, revisions fixadas, imagem mínima e cache de downloads |
| Imagens sem ARM64 | Falha no manifest inspect | Substituir por imagem oficial compatível; ACA-Py é cortado, nunca emulado |
| Ditto excede recursos | OOM ou swap persistente | VM mínima de 8 GiB, limites medidos e serviços não essenciais removidos |
| Âmbito volta a crescer | Pedido sem ligação às RQs | Aplicar P0/P1/out-of-scope e exigir troca explícita de horas |
| Resultados sem proveniência | Métrica sem `run_id`/manifesto | Invalidar a execução e repeti-la antes do data freeze |
| Feedback tardio | Sem resposta nos marcos | Entregar capítulos cedo e continuar com as decisões documentadas |
| Escrita fica para o fim | Capítulos 1–4 incompletos em 06/09 | Reserva diária de escrita e corte imediato de P1 |

---

## 12. Premissas fechadas

- Baseline temporal: 07/08/2026.
- Disponibilidade: 35–45 h/semana.
- Prazo oficial: 30/09/2026; prazo interno: 29/09 às 17:00.
- Não existe Raspberry Pi 5 disponível.
- Avaliação de desempenho numa VM ARM64; QEMU é apenas funcional.
- Dissertação em inglês; Resumo em português quando exigido.
- Simulador por CLI, sem dashboard.
- ACA-Py é estritamente condicional e dispensável para todas as RQs.
- A tese tem de ser defensável mesmo que todo o âmbito P1 seja cortado.
- O alvo de palavras é indicativo, não um substituto de evidência ou qualidade.

---

## Anexo A — Inventário dos 58 artefactos preexistentes analisados

O inventário exclui metadados de ferramentas, caches e artefactos temporários. A
ação indicada é a decisão deste plano, não uma indicação de que a ação já foi
executada. É a fotografia anterior à criação deste documento: com o plano integrado,
o workspace passa a conter 59 ficheiros de projeto.

| # | Caminho | Categoria | Função e estado observado | Relevância | Ação definida |
|---:|---|---|---|---|---|
| 1 | `EdgeGateway_Paper.pdf` | Investigação base | Artigo C2DTA; avaliação x86 com um smartwatch | Alta | Citar como trabalho anterior e delimitar claramente o que não avaliou |
| 2 | `C2DTA_Seven_Questions_Answers_1.docx` | Enquadramento | Respostas extensas e diagrama embebido; contém afirmações a verificar | Alta | Aproveitar contexto validado; rever visualmente com LibreOffice e verificar claims atuais |
| 3 | `compass_artifact_wf-bc3ec062-7176-5823-8bec-b56ecbdf0527_text_markdown.md` | Bibliografia | Mapa amplo de fontes; inclui metadados e afirmações imprecisos | Alta | Usar como lista de pistas, nunca como bibliografia sem verificação primária |
| 4 | `INTERFACES.md` | Contrato técnico | Contrato preliminar multi-tese, mais amplo que a implementação atual | Alta | Alinhar com MQTT/TLS, schemas e P0; marcar integrações externas como futuras |
| 5 | `LOG_Projeto.md` | Gestão/evidência | Diário útil, mas com estados e classificação do PDF incorretos | Alta | Corrigir factos e manter diariamente com ligações para evidências |
| 6 | `Plano_Tese_EdgeGateway_v2.md` | Plano histórico | Plano v2.3 comprimido, parcialmente ultrapassado | Alta/histórica | Preservar com aviso; este plano integrado prevalece |
| 7 | `universidade/TypesDissertationProjects.pptx` | Orientação académica | Tipos de projetos de dissertação | Média | Usar para justificar a classificação DSR do trabalho |
| 8 | `universidade/MoreAboutPublications.pptx` | Orientação académica | Recomendações sobre publicações | Baixa antes da entrega | Reservar para trabalho pós-submissão |
| 9 | `universidade/LiteratureReviewTools.pptx` | Orientação académica | Ferramentas e processo de revisão | Alta | Aplicar à revisão estruturada e ao registo das pesquisas |
| 10 | `universidade/FinalCommentsPresentationDefense.pptx` | Orientação académica | Defesa, estrutura e comunicação | Média | Usar depois da submissão para slides e ensaio |
| 11 | `universidade/EscritaArtigo.pptx` | Orientação académica | Escrita de artigo científico | Baixa antes da entrega | Não colocar no caminho crítico; reutilizar depois da tese |
| 12 | `universidade/Dissertation_SLR.pdf` | Metodologia | Material sobre revisões sistemáticas | Alta | Adaptar apenas os elementos executados; não chamar SLR ao estudo |
| 13 | `universidade/Dissertation_part_SR_PRISMA.pdf` | Metodologia | Seleção e reporting PRISMA | Alta | Usar fluxo PRISMA apenas se todos os registos forem mantidos |
| 14 | `universidade/Dissertation_part_HowtoStart.pdf` | Escrita | Recomendações para iniciar e estruturar a tese | Média | Aplicar ao problema, objetivos, lacuna e plano de capítulos |
| 15 | `universidade/Dissertation_part_Guidelines for a successful thesis writing.pdf` | Escrita | Boas práticas de redação e consistência | Alta | Usar como checklist editorial |
| 16 | `universidade/Dissertation_part_DesignScienceResearch.pdf` | Metodologia | Design Science Research e ciclo construir–avaliar | Muito alta | Fundamentar a metodologia e mapear o artefacto às RQs |
| 17 | `universidade/Dissertation_part_CaseStudy.pdf` | Metodologia | Orientações para case study | Média | Usar apenas conceitos compatíveis; não reclassificar o estudo sem justificação |
| 18 | `universidade/Dissertation_part_Applying-the-SLR-and-Mapping-Methodology.pdf` | Metodologia | Aplicação de SLR/mapping | Alta | Informar strings, seleção, deduplicação e snowballing |
| 19 | `dissertation/references.bib` | Dissertação | Bibliografia ativa, curta e com entradas a corrigir | Muito alta | Auditar metadados, eliminar associações erradas e expandir para ≥30 fontes verificadas |
| 20 | `dissertation/main.tex` | Dissertação | Entrada LaTeX ativa; compila com warnings | Muito alta | Manter como fonte principal, corrigir front matter, idiomas e warnings |
| 21 | `dissertation/imagens/ista.png` | Dissertação | Logótipo institucional | Baixa | Preservar e validar resolução no PDF final |
| 22 | `dissertation/imagens/iscte.png` | Dissertação | Logótipo institucional | Baixa | Preservar e validar resolução no PDF final |
| 23 | `dissertation/chapters/01_introduction.tex` | Dissertação | Introdução preliminar | Muito alta | Reescrever problema, lacuna, RQs, objetivos, contribuições e limites |
| 24 | `dissertation/chapters/02_state_of_the_art.tex` | Dissertação | Estado da arte muito curto e revisão apresentada como sistemática | Muito alta | Transformar em revisão scoping/narrativa estruturada e acrescentar comparação |
| 25 | `dissertation/chapters/03_methodology.tex` | Dissertação | Metodologia DSR preliminar | Muito alta | Acrescentar matriz RQ→método→métrica, protocolo e validade |
| 26 | `dissertation/chapters/04_architecture_and_development.tex` | Dissertação | Arquitetura/desenvolvimento ainda pouco sustentados pelo artefacto | Muito alta | Atualizar apenas a partir da implementação e ADRs reais |
| 27 | `dissertation/chapters/05_evaluation.tex` | Dissertação | Contém resultados sem pacote de evidência correspondente | Crítica | Remover/quarentenar valores e preencher apenas após `data-v1` |
| 28 | `dissertation/chapters/06_conclusion.tex` | Dissertação | Conclusões prematuras baseadas em resultados por demonstrar | Crítica | Reescrever depois da avaliação e responder explicitamente às RQs |
| 29 | `Template_LaTeX/references.bib` | Template | Bibliografia de exemplo/referência | Baixa | Não misturar automaticamente com a bibliografia ativa |
| 30 | `Template_LaTeX/main.tex` | Template | Template institucional de LaTeX | Alta | Consultar para conformidade sem substituir o documento ativo |
| 31 | `Template_LaTeX/imagens/ista.png` | Template | Logótipo do template | Baixa | Preservar como referência |
| 32 | `Template_LaTeX/imagens/iscte.png` | Template | Logótipo do template | Baixa | Preservar como referência |
| 33 | `exemplos_tese/report_IotT.pdf` | Exemplo académico | Relatório intermédio, não dissertação final | Média | Usar apenas para estrutura/clareza; não usar como alvo de extensão |
| 34 | `exemplos_tese/Report_DEI.pdf` | Exemplo académico | Relatório intermédio | Média | Consultar organização e apresentação de trabalho |
| 35 | `exemplos_tese/ReportBeatrizGoncalves96068 (1).pdf` | Exemplo académico | Relatório intermédio | Média | Consultar estilo e argumentação, sem copiar conteúdo |
| 36 | `exemplos_tese/Dissertation_1.pdf` | Exemplo académico | Exemplo fornecido, de dimensão intermédia | Média | Usar como referência visual, não como norma institucional |
| 37 | `egw_project/DEVELOPMENT_PLAN.md` | Plano histórico | Plano antigo com prazo de agosto e stack Indy/IPFS no caminho crítico | Alta/histórica | Preservar com aviso; não executar o caminho crítico antigo |
| 38 | `egw_project/docs/revisao_recomendacoes.md` | Revisão técnica | Recomendações e diagnóstico anteriores | Média | Triar contra o âmbito P0 e converter itens válidos em backlog |
| 39 | `egw_project/docs/fase3_plano_desenvolvimento.md` | Especificação histórica | Planta detalhada mas excessiva e dependente de SSI/blockchain | Alta/histórica | Preservar como referência; implementar apenas módulos compatíveis com P0 |
| 40 | `egw_project/docs/fase2_arquitetura_metricas.md` | Arquitetura | Arquitetura e métricas de fase anterior | Alta | Reconciliar com QEMU funcional, ARM cloud e protocolo congelado |
| 41 | `egw_project/docs/fase1_problema_estado_arte.md` | Investigação | Formulação inicial do problema e estado da arte | Alta | Reutilizar apenas claims verificados e alinhados com as novas RQs |
| 42 | `egw_project/docs/estado_arte_referencias.md` | Bibliografia | Lista de referências para estado da arte | Alta | Verificar cada referência antes de migrar para BibTeX |
| 43 | `egw_project/docs/C2DTA_Seven_Questions_Answers_1.txt` | Fonte derivada | Extração textual do DOCX | Média | Usar para pesquisa local; manter o DOCX como fonte canónica |
| 44 | `egw_project/docs/bibliografia_adicional_sugerida.md` | Bibliografia | Sugestões com algumas entradas não confirmadas | Média | Não citar sem localizar e verificar a publicação primária |
| 45 | `egw_project/docs/bibliografia.md` | Bibliografia | Bibliografia inicial de trabalho | Alta | Deduplicar e reconciliar com `dissertation/references.bib` |
| 46 | `egw_project/meta-egw/recipes-core/images/egw-image.bb` | Yocto | Receita de imagem mínima e ainda não validada | Muito alta | Completar dependências mínimas, construir e provar boot em QEMU |
| 47 | `egw_project/meta-egw/conf/layer.conf` | Yocto | Configuração inicial da layer | Muito alta | Validar compatibilidade Scarthgap e integrar no manifesto `kas` |
| 48 | `egw_project/docker/mosquitto/config/mosquitto.conf` | Plataforma | Configuração MQTT atual sem segurança P0 completa | Muito alta | Implementar listener TLS 8883, autenticação e persistência/logs necessários |
| 49 | `egw_project/docker/docker-compose.yml` | Plataforma | Inclui Mosquitto, IPFS e ACA-Py antigo; não inclui Ditto | Crítica | Reestruturar para o core Ditto/MongoDB/Mosquitto/controlador; mover SSI para profile opcional e remover IPFS do core |
| 50 | `egw_project/controller/requirements.txt` | Controlador | Dependências iniciais | Alta | Atualizar e fixar versões mínimas necessárias, evitando dependências P1 no core |
| 51 | `egw_project/controller/main.py` | Controlador | FastAPI com endpoints/webhook stub e TODOs | Crítica | Implementar bridge assíncrona MQTT→schema→Ditto, health/readiness e métricas |
| 52 | `egw_project/emulators/wot/smart_ring.jsonld` | WoT/schema | TD inicial com contexto antigo e `nosec` | Alta | Atualizar para TD 1.1, adicionar forms TLS e alinhar com schema |
| 53 | `egw_project/emulators/wot/smart_clothing.jsonld` | WoT/schema | TD inicial com contexto antigo e `nosec` | Alta | Atualizar para TD 1.1, adicionar forms TLS e alinhar com schema |
| 54 | `egw_project/emulators/wot/smartwatch.jsonld` | WoT/schema | TD inicial com contexto antigo e `nosec` | Alta | Atualizar para TD 1.1, adicionar forms TLS e alinhar com schema |
| 55 | `egw_project/emulators/smart_ring.py` | Simulador | Emulador isolado, aleatório e com configuração rígida | Muito alta | Migrar para pacote CLI com profile, seed, seq, schemas e cenários |
| 56 | `egw_project/emulators/smart_clothing.py` | Simulador | Emulador isolado, aleatório e com configuração rígida | Muito alta | Migrar para pacote CLI e preservar apenas o modelo útil de medições |
| 57 | `egw_project/emulators/smartwatch.py` | Simulador | Emulador isolado, aleatório e com configuração rígida | Muito alta | Migrar para pacote CLI e reproduzir o cenário de 1 Hz do artigo |
| 58 | `egw_project/emulators/requirements.txt` | Simulador | Dependências mínimas não fixadas para uma CLI testável | Alta | Consolidar dependências, fixar versões e acrescentar validação/testes |

### Resumo da cobertura

| Grupo | Ficheiros |
|---|---:|
| Raiz e fontes nucleares | 6 |
| Materiais da universidade | 12 |
| Dissertação ativa | 10 |
| Template LaTeX | 4 |
| Exemplos académicos | 4 |
| Projeto Edge Gateway | 22 |
| **Total** | **58** |

---

## Anexo B — Base documental principal

- [`EdgeGateway_Paper.pdf`](EdgeGateway_Paper.pdf)
- [`C2DTA_Seven_Questions_Answers_1.docx`](C2DTA_Seven_Questions_Answers_1.docx)
- [`compass_artifact_wf-bc3ec062-7176-5823-8bec-b56ecbdf0527_text_markdown.md`](compass_artifact_wf-bc3ec062-7176-5823-8bec-b56ecbdf0527_text_markdown.md)
- [`universidade/Dissertation_part_DesignScienceResearch.pdf`](universidade/Dissertation_part_DesignScienceResearch.pdf)
- [`universidade/Dissertation_SLR.pdf`](universidade/Dissertation_SLR.pdf)
- [`universidade/Dissertation_part_SR_PRISMA.pdf`](universidade/Dissertation_part_SR_PRISMA.pdf)
- [`universidade/Dissertation_part_Guidelines for a successful thesis writing.pdf`](<universidade/Dissertation_part_Guidelines for a successful thesis writing.pdf>)
- Restantes materiais académicos inventariados no Anexo A.

---

## Anexo C — Registo de gates

| Gate | Data | Estado | Evidência | Decisão/corte |
|---|---|---|---|---|
| G0 — âmbito e ambiente | 10/08/2026 | Pendente | — | — |
| G1 — Yocto/QEMU | 16/08/2026 | Pendente | — | — |
| G2 — vertical slice | 23/08/2026 | Pendente | — | — |
| G3 — core freeze/ACA-Py | 30/08/2026 | Pendente | — | — |
| G4 — protocolo freeze | 06/09/2026 | Pendente | — | — |
| G5 — data freeze | 13/09/2026 | Pendente | — | — |
| G6 — draft integral | 18/09/2026 | Pendente | — | — |
| G7 — release/submissão | 25–29/09/2026 | Pendente | — | — |
