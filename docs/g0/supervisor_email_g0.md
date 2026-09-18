# Draft de email aos orientadores - gate G0 e proposta de duas camadas

> **2026-09-16 integrated-Yocto planning amendment (proposal).** Unsent August draft: do not send unchanged. Its dates have elapsed, and the student has since proposed the integrated objective: see [plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) (proposal published for review), the [proposed scope](scope_and_rqs.md) and the revised [alignment memo](../governance/supervisor_alignment_memo.md) (draft, not sent). Nothing has been sent to or approved by the supervisors.

**Versão do draft:** 1.2 (2026-08-14)

**Estado:** **PROPOSED - NOT SENT**

**Aprovação dos orientadores:** nenhuma registada

> **Instruções internas - não enviar esta secção.** Rever nomes, tratamento,
> anexos e custo da infraestrutura antes do envio. Anexar o PDF atual do
> Capítulo 2, o memo [`two_layer_thesis_proposal.md`](two_layer_thesis_proposal.md)
> e a matriz [`supervisor_decision_matrix.csv`](supervisor_decision_matrix.csv).
> O envio é uma ação do estudante. Só depois do envio deve ser registada a data
> no [`../governance/supervisor_decision_log.csv`](../governance/supervisor_decision_log.csv)
> e no `LOG.md`; uma resposta deve ser registada separadamente e o silêncio
> nunca deve ser tratado como aprovação.

---

**Para:** Prof.ª Catarina Silva; Prof. Sérgio Moro

**Assunto:** Dissertação Edge Gateway / C2DTA - proposta de duas camadas,
Capítulo 2 e decisões necessárias

Cara Professora Catarina Silva, caro Professor Sérgio Moro,

Envio para vossa análise o draft atual do Capítulo 2 e uma proposta de
reformulação que pretende eliminar uma ambiguidade importante do trabalho: a
imagem Yocto validada em QEMU e a pilha de serviços de gémeos digitais para uma
máquina ARM64 nativa são dois artefactos experimentais relacionados, mas
separados. Neste momento não existe evidência de que a pilha Eclipse Ditto seja
executada dentro da imagem Yocto, pelo que proponho que a tese não o sugira.

## 1. Enquadramento e título propostos

**Título proposto:** *Design and Experimental Evaluation of a Two-Layer ARM64
Edge Gateway Prototype for the Local Digital-Twin Core of C2DTA*

O objetivo proposto é conceber e avaliar um protótipo ARM64 de duas camadas para
o núcleo local de gémeos digitais do C2DTA:

1. uma camada funcional Yocto/QEMU para build, boot, systemd, rede e runtime
   OCI, sem resultados de desempenho;
2. uma pilha separada de serviços em contentores numa máquina ARM64 nativa,
   formada por Mosquitto, Eclipse Ditto, MongoDB e o controlador MQTT-to-Ditto,
   onde serão feitos os testes ponta a ponta e, numa instância non-burstable, as
   medições.

As questões de investigação propostas são:

- **RQ1:** *How can a two-layer ARM64 Edge Gateway prototype be designed, built
  and redeployed when its Yocto/QEMU functional platform and native-ARM64
  containerised digital-twin stack are treated as separate artefact layers?*
- **RQ2:** *To what extent can the prototype ingest and materialise concurrent
  synthetic telemetry from three wearable-device types correctly and
  reliably, including under specified fault scenarios?*
- **RQ3:** *What latency, sustainable-throughput, saturation and per-container
  resource trade-offs constrain the digital-twin stack on a non-burstable
  native-ARM64 environment?*

Esta formulação é uma proposta. O título e as RQs atuais da tese não serão
substituídos antes da vossa validação explícita.

## 2. Ponto de situação verificável

- A imagem `egw-image` foi construída duas vezes a partir das revisões Yocto
  fixadas: primeiro no ambiente de desenvolvimento e, a 2026-08-14, a partir de
  um *checkout* limpo e identificado do repositório (5715 tarefas concluídas,
  com os registos e os *checksums* dos artefactos arquivados).
- A campanha de cinco boots QEMU ARM64 foi executada a 2026-08-14 pelo
  verificador automático, com critérios estritos: estado `systemd=running`
  exato, zero unidades em estado `failed` e encerramento limpo. Os cinco boots
  passaram as sete asserções obrigatórias. Uma primeira tentativa falhou por um
  defeito do próprio verificador; ficou preservada como falha no arquivo, o
  defeito foi corrigido com um teste de regressão, e só depois a campanha foi
  executada de novo.
- Com isto, a evidência funcional da plataforma Yocto/QEMU está completa e
  selada. A validação académica é vossa; a reprodução por um segundo operador
  independente é um requisito separado, dependente da decisão D006.
- A pilha de serviços, o controlador, o simulador e o harness existem no
  repositório e a suite selada contém 701 testes unitários com fakes. Ainda não
  foi executado um teste live MQTT-to-controller-to-Ditto nem uma campanha de
  medição ARM64.
- Não existe qualquer resultado da campanha oficial e nenhum número de QEMU ou
  de uma instância burstable será usado como resultado de desempenho.

## 3. Delimitação face ao paper C2DTA

O paper implementa uma arquitetura C2DTA mais ampla: Eclipse Ditto 3.0.0 e
Mosquitto, agentes ACA-Py/DIDComm, Hyperledger Fabric, Hyperledger Indy e IPFS.
Define oito cenários de ciclo de vida e avalia os primeiros sete em 88 passos;
o percurso de telemetria usa um simulador de smartwatch a 1 Hz. Essa avaliação
correu numa VM x86 e não será usada como baseline causal para os resultados
ARM64 desta dissertação.

O P0 proposto cobre apenas o núcleo local: telemetria MQTT/TLS, validação e
materialização em Eclipse Ditto para três tipos de wearable. ACA-Py, DIDComm,
Fabric, Indy, IPFS, marketplace, UI, Bluetooth e hardware físico ficam fora do
caminho crítico e são representados apenas na arquitetura de referência,
delimitação e trabalho futuro.

## 4. Risco de infraestrutura

A máquina ARM64 non-burstable de medição ainda não existe. Oracle, Hetzner e a
quota ARM dedicada da Azure não forneceram a capacidade necessária. Proponho:

1. aguardar 48 horas por uma solução institucional;
2. sem confirmação, usar temporariamente uma instância pública ARM64
   non-burstable com 4 vCPU, 8 GiB de RAM e pelo menos 80 GB;
3. confirmar o preço antes de criar a instância e não ultrapassar o teto total
   de 30 EUR sem nova autorização;
4. usar uma instância burstable apenas para integração funcional, nunca para
   resultados.

## 5. Decisões solicitadas

A matriz anexa organiza dez decisões, D001-D010. As mais urgentes são:

- validar ou corrigir o título, objetivo, RQs e separação em duas camadas;
- confirmar a exclusão de SSI/blockchain do P0;
- confirmar a designação da revisão de literatura e o template oficial de
  2026;
- decidir se a palavra *reproducible* exige uma reprodução por segundo
  operador;
- validar os thresholds antes do freeze `exp-v1`;
- confirmar os papéis de QEMU, ARM burstable e ARM non-burstable.

Acrescento duas confirmações não urgentes (D009 e D010), sobre desvios
documentados face ao template de repositório do projeto: primeiro, o termo
`telemetry` é o termo contratual dos tópicos MQTT e dos schemas versionados,
embora o template peça terminologia *smart devices/wearables* — proponho manter
o termo nos contratos e usar "wearable event data" na prosa da tese; segundo, o
stub genérico do template refere "no local data storage" no EGW, mas o próprio
paper atribui ao EGW o papel de guardião dos dados no *edge*, e o núcleo P0
persiste o estado dos gémeos em MongoDB/Ditto por desenho. Nenhum destes pontos
bloqueia o trabalho; peço apenas confirmação de que a delimitação está correta.

Se for possível, agradeço comentários iniciais até 2026-08-18. Sem resposta até
2026-08-20, proponho uma reunião breve para fechar D001, D004 e D007. Até existir
uma resposta explícita, estes pontos permanecem pendentes e não serão tratados
como aprovados.

Com os melhores cumprimentos,

Rui Duarte

ruimfduarte94@gmail.com
