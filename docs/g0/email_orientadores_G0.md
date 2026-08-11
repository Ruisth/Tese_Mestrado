# Draft de email aos orientadores — gate G0

> **Instruções (não enviar esta secção):** enviar até 09/08/2026 para cumprir o
> gate G0 do plano integrado (§8 e §8.2). Rever os nomes/tratamentos antes de
> enviar e anexar (ou colar) as três questões de investigação tal como abaixo.
> O envio do email é ação do estudante; registar a data de envio no LOG.

---

**Para:** Prof.ª Catarina Silva; Prof. Sérgio Moro
**Assunto:** Dissertação Edge Gateway (C2DTA) — proposta de âmbito e questões de investigação; reunião a 10/08

Cara Professora Catarina Silva, caro Professor Sérgio Moro,

Espero que se encontrem bem. Escrevo para fechar convosco o âmbito e as questões
de investigação da dissertação, de forma a concentrar o trabalho até à entrega de
30 de setembro. Peço a vossa validação (ou objeções) aos pontos seguintes.

**1. Objetivo e questões de investigação propostas**

O objetivo é conceber, implementar e avaliar um edge gateway ARM64 reproduzível,
baseado em Yocto e serviços em contentores, que recebe telemetria sintética
concorrente de três tipos de wearable (smartwatch, smart ring, smart clothing),
valida os eventos e materializa-os como gémeos digitais no Eclipse Ditto. As
questões de investigação, na formulação que proponho manter em inglês:

- RQ1: How can a reproducible Yocto-based ARM64 edge gateway be designed to host
  containerised digital-twin services?
- RQ2: To what extent can the gateway ingest and materialise concurrent synthetic
  telemetry from three wearable-device types correctly and reliably?
- RQ3: What latency, throughput and resource-consumption trade-offs constrain
  deployment of the proposed platform on an ARM64 edge-class environment?

**2. Plataforma de avaliação: sem Raspberry Pi físico**

Não tenho acesso a um Raspberry Pi 5, pelo que proponho separar explicitamente
duas plataformas: (a) validação funcional do sistema operativo construído com
Yocto em emulação QEMU ARM64 (arranque, rede, execução de contentores), sem
qualquer conclusão de desempenho; e (b) avaliação de desempenho numa máquina
virtual cloud com CPU ARM64 nativa (latência, débito, consumo de recursos,
estabilidade de 24 horas). Esta separação e a ausência de hardware físico serão
declaradas como limitação na dissertação.

**3. Cortes de âmbito propostos**

Para tornar setembro exequível, proponho: (a) a componente de identidade
descentralizada (SSI/ACA-Py) fica estritamente condicional — só será tentada, num
formato mínimo de demonstração, se todo o núcleo estiver completo e sem defeitos a
30/08, e não é necessária para responder a nenhuma questão de investigação; (b)
ficam fora de âmbito Hyperledger Indy, Fabric, IPFS, marketplace, credenciais
verificáveis, interfaces gráficas e avaliação em hardware físico. A dissertação
será defensável mesmo sem a componente de identidade.

**4. Regras administrativas da extensão até 31/10**

Por prudência, gostaria de confirmar até 10/08 as regras administrativas de uma
eventual extensão do prazo até 31/10/2026: procedimento, aprovações necessárias e
data-limite institucional para submeter o pedido. O plano de trabalho assume a
entrega a 29/09, mas quero conhecer o processo antecipadamente para, se algum
marco crítico falhar, ativar a contingência cedo e não no fim do mês.

**5. Reunião e calendário de acompanhamento**

Proponho uma reunião breve (30 minutos, presencial ou online) na segunda-feira,
10/08, para validar o âmbito acima. Proponho ainda o seguinte calendário de
pontos de contacto:

- 17/08 — Introdução, lacuna de investigação, arquitetura e protocolo experimental;
- 31/08 — demonstração do núcleo funcional e decisão sobre a componente de identidade;
- 07/09 — validação do protocolo experimental congelado;
- 18/09 — envio do draft integral da dissertação;
- 23/09 — data solicitada para o vosso feedback final;
- 25/09 — fecho académico e administrativo, antes da submissão a 29/09.

Se preferirem outro dia ou formato para a reunião, tenho disponibilidade flexível.

Com os melhores cumprimentos,
Rui Duarte
ruimfduarte94@gmail.com
