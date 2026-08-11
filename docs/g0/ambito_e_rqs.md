# G0 — Âmbito e questões de investigação (proposto — aguarda validação dos orientadores)

> Derivado do plano integrado (`../../../PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`,
> v1.0 — 07/08/2026, NORMATIVO), secções 4 e 12. Este documento fixa o âmbito para o
> gate **G0 (10/08/2026)**. Qualquer alteração exige atualização do plano e registo no LOG.

**Estado:** proposto aos orientadores no bloco 07–09/08; ver
[`email_orientadores_G0.md`](email_orientadores_G0.md).

---

## 1. Objetivo (plano §4.1)

Conceber, implementar e avaliar um Edge Gateway ARM64 reproduzível, baseado em
Yocto e serviços contentorizados, capaz de receber telemetria sintética concorrente
de três wearables, validar os eventos e materializá-los como gémeos digitais no
Eclipse Ditto.

## 2. Questões de investigação definitivas (plano §4.2)

As RQs são fixadas em inglês, tal como constarão da dissertação:

1. **RQ1:** *How can a reproducible Yocto-based ARM64 edge gateway be designed to
   host containerised digital-twin services?*
2. **RQ2:** *To what extent can the gateway ingest and materialise concurrent
   synthetic telemetry from three wearable-device types correctly and reliably?*
3. **RQ3:** *What latency, throughput and resource-consumption trade-offs constrain
   deployment of the proposed platform on an ARM64 edge-class environment?*

ACA-Py e SSI **não são necessários** para responder a qualquer RQ.

## 3. Âmbito obrigatório — P0 (plano §4.3)

- Ambiente Linux reproduzível, controlo de versões e matriz claim→evidência
  ([`../claim_evidence_matrix.md`](../claim_evidence_matrix.md)).
- Yocto Project **5.0.19/Scarthgap**, com tags e commits exatos fixados num manifesto
  `kas`, sem depender do HEAD de branches móveis (Scarthgap é a linha LTS suportada
  até abril de 2028, segundo a documentação oficial do Yocto Project).
- Imagem `egw-image` construída e arrancada em `qemuarm64`, com systemd, rede e
  runtime OCI funcional.
- Stack ARM64 mínima com Mosquitto, Eclipse Ditto 3.9.4 (`gateway`, `policies` e
  `things`), MongoDB e controlador MQTT→Ditto; `search`, `connectivity` e UI ficam
  excluídos enquanto não forem necessários às RQs. Todas as imagens e dependências
  transitivas verificadas como `linux/arm64` e fixadas por digest.
- Simulador unificado por CLI para smartwatch, smart ring e smart clothing.
- Cenários `smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload`
  e `soak`.
- Testes unitários, integração, E2E, recuperação, carga e estabilidade de 24 horas.
- Campanha experimental numa VM ARM64 temporária (nativa, não emulada).
- Dissertação completa em inglês, com Resumo em português se exigido.
- Pacote de reprodutibilidade com código, configurações, logs, dados, checksums e
  script de análise.

## 4. Âmbito condicional — P1 (plano §4.4)

ACA-Py só pode avançar **depois do gate G3 (30/08)**, com timebox máximo total de
**12 horas**, e segundo as regras de corte do plano §8.1:

- só avança se build/boot QEMU, deploy ARM limpo, três dispositivos, cenários,
  testes, métricas e soak estiverem completos e **sem defeitos P0**;
- usar a imagem `ghcr.io/openwallet-foundation/acapy-agent:py3.13-1.6-lts`, fixada
  pelo digest verificado para ARM64, e `askar-anoncreds` em vez do wallet `askar`
  depreciado;
- confirmar suporte ARM64 **antes** de qualquer implementação;
- executar dois agentes locais, `did:peer`, convite Out-of-Band e uma mensagem
  DIDComm básica;
- não usar ledger público, Indy, emissão de credenciais ou lógica de propriedade;
- cortar imediatamente se não existir imagem ARM64, se algum gate P0 estiver
  vermelho ou se terminar o timebox; corte automático ao fim de 12 h ou em
  **03/09**, o que ocorrer primeiro.

A tese tem de ser defensável mesmo com todo o P1 cortado; ver
[`../adr/0002-ssi-acapy-conditional-p1.md`](../adr/0002-ssi-acapy-conditional-p1.md).

## 5. Fora de âmbito (plano §4.5)

- Hyperledger Indy, Fabric, IPFS como armazenamento obrigatório, marketplace,
  transferência de propriedade, credenciais verificáveis de negócio, AI/MAS,
  interface gráfica, dashboard, Bluetooth, OTA, LUKS, consumo energético e
  avaliação num Raspberry Pi físico.
- Mais de três tipos de dispositivo.
- Artigo científico e preparação detalhada da defesa antes da submissão. Se a tese
  for entregue em setembro, outubro pode ser usado para esses trabalhos sem reabrir
  o artefacto submetido.

A extensão de contingência (plano §10) **nunca** reintroduz Indy, Fabric, IPFS,
marketplace, UI ou outras funções cortadas.

## 6. Premissas fechadas (plano §12)

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
