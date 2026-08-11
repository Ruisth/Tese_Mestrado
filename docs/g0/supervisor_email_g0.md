# Draft de email aos orientadores — gate G0

> **Instruções internas (não enviar esta secção):** este draft cumpre duas
> obrigações do plano integrado ao mesmo tempo — fechar o âmbito e as questões de
> investigação (§8 e §8.2) e comunicar formalmente aos orientadores o risco da
> plataforma de medição, como §8.1 determina quando não existe máquina ARM64 a
> 2026-08-10, e como §10 exige que conste deste email. Enviar a 2026-08-12.
> Rever nomes e tratamentos antes de enviar. O envio é ação do estudante:
> registar no LOG a data de envio e, mais tarde, a resposta recebida.

---

**Para:** Prof.ª Catarina Silva; Prof. Sérgio Moro
**Assunto:** Dissertação Edge Gateway (C2DTA) — âmbito e questões de
investigação, ponto de situação e um risco de infraestrutura a decidir; proposta
de reunião a 2026-08-14

Cara Professora Catarina Silva, caro Professor Sérgio Moro,

Espero que se encontrem bem. Escrevo por três motivos: fechar convosco o âmbito e
as questões de investigação da dissertação, dar-vos um ponto de situação honesto
do que já está construído e comunicar-vos um problema de infraestrutura que
condiciona a parte experimental e para o qual proponho uma solução. Peço a vossa
validação (ou objeções) aos pontos seguintes, de forma a concentrar o trabalho
até à entrega de 2026-09-30.

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

**2. Ponto de situação: o que já está construído**

A imagem do sistema operativo do gateway já é construída de ponta a ponta a
partir de revisões fixadas das camadas Yocto, num ambiente de construção Linux
igualmente fixado (5715 tarefas de compilação, todas concluídas com sucesso). A
imagem inclui o runtime de contentores necessário aos serviços. Foram executados
dois arranques dessa imagem em emulação QEMU ARM64, conduzidos por um verificador
automático e sem intervenção manual, ambos passando na totalidade das
verificações obrigatórias e terminando com encerramento limpo; os registos e as
respetivas somas de verificação ficaram arquivados no repositório, de modo a
poderem ser reproduzidos a partir de uma cópia limpa.

Duas ressalvas que faço questão de deixar explícitas. Primeiro, considero esta
etapa documentada, não validada: a validação é vossa e está por fazer, e é um dos
pontos que gostaria de levar à reunião. Segundo, nenhum destes resultados
sustenta qualquer afirmação de desempenho — a emulação não representa o
comportamento temporal do hardware e, por isso, não produzirá um único número
para a dissertação.

**3. Plataformas de avaliação: sem Raspberry Pi físico**

Não tenho acesso a um Raspberry Pi 5. Proponho, por isso, separar explicitamente
três plataformas, com papéis que não se misturam:

- **emulação QEMU ARM64** — validação funcional do sistema operativo construído
  com Yocto (arranque, rede, execução de contentores). Não produz números;
- **instância ARM64 *burstable* na cloud** — integração funcional dos serviços em
  condições reais de rede e de sistema operativo. Também não produz números;
- **instância ARM64 dedicada na cloud** — única origem admissível dos resultados
  de latência, débito, consumo de recursos e estabilidade que respondem à RQ3.

O compromisso associado é simples e assumo-o por escrito: nenhum valor medido em
emulação ou numa instância *burstable* entrará na dissertação. A razão é que
estas instâncias funcionam por créditos de CPU e, esgotados os créditos, o
processador é estrangulado — o que falsearia qualquer medição de latência ou de
saturação. Esta separação, e a ausência de hardware físico, serão declaradas como
limitação na dissertação.

**4. Comunicação formal de risco: a máquina de medição ARM64 não existe**

Este é o ponto que mais precisa da vossa atenção. A máquina virtual dedicada com
CPU ARM64 nativa, prevista para 2026-08-10, não foi obtida. Tentei três
fornecedores e todos falharam, por motivos distintos:

- **Oracle Cloud** — a região de origem da conta é fixada no momento do registo e
  não tem capacidade Ampere disponível; numa conta gratuita não é possível
  subscrever outra região;
- **Hetzner** — todas as instâncias ARM da linha CAX estão indisponíveis, em
  todas as localizações;
- **Azure for Students** — a subscrição está limitada a cinco regiões e a quota é
  zero em todas as famílias ARM dedicadas (`Dpsv5`/`Dpsv6`, `Dplsv5`/`Dplsv6`).
  Apenas a família *burstable* (série B) é obtida sem pedido de quota, e essa
  está excluída da medição pela razão explicada no ponto anterior.

A consequência é concreta: a implantação em ARM64, os ensaios ponta a ponta e a
campanha de medição que responde à RQ3 dependem todos desta máquina e estão, por
isso, parados. É neste momento a única dependência externa que bloqueia o
progresso do trabalho experimental; a construção do sistema e o desenvolvimento
dos serviços continuam a avançar em paralelo.

O que já fiz e o que proponho: submeti um pedido de aumento de quota na Azure
para as famílias `DPLSv5` e `DPLSv6`. Se a quota não for concedida em tempo útil,
recorro a uma instância dedicada paga na AWS (`c6g.xlarge`), cujo custo estimado
é de cerca de 7 EUR para a campanha completa, dado que a instância só está ativa
durante os ensaios. Dou-vos este número para que fique claro que o problema é
limitado e tem solução conhecida, e não uma incerteza em aberto. Do vosso lado
peço apenas duas coisas: a vossa concordância com o modelo de três plataformas
descrito no ponto 3 e a vossa autorização para avançar com a alternativa paga se
a quota não chegar até 2026-08-21.

**5. Cortes de âmbito propostos**

Para tornar setembro exequível, proponho: (a) a componente de identidade
descentralizada (SSI/ACA-Py) fica estritamente condicional — só será tentada, num
formato mínimo de demonstração, se todo o núcleo estiver completo e sem defeitos
a 2026-08-30, e não é necessária para responder a nenhuma questão de
investigação; (b) ficam fora de âmbito Hyperledger Indy, Fabric, IPFS,
marketplace, credenciais verificáveis, interfaces gráficas e avaliação em
hardware físico. A dissertação será defensável mesmo sem a componente de
identidade.

**6. Regras administrativas da extensão até 2026-10-31**

Por prudência, gostaria de confirmar até 2026-08-21 as regras administrativas de
uma eventual extensão do prazo até 2026-10-31: procedimento, aprovações
necessárias e data-limite institucional para submeter o pedido. O plano de
trabalho continua a assumir a submissão a 2026-09-29, mas quero conhecer o
processo antecipadamente para, se algum marco crítico falhar, ativar a
contingência cedo e não no fim do mês.

**7. Reunião e calendário de acompanhamento**

Proponho uma reunião breve (30 minutos, presencial ou online) na sexta-feira,
2026-08-14, para validar o âmbito e decidir o ponto 4. Se essa data não for
possível, fico igualmente disponível na segunda-feira, 2026-08-17. Proponho ainda
o seguinte calendário de pontos de contacto:

- 2026-08-17 — Introdução, lacuna de investigação, arquitetura e protocolo experimental (se a reunião do ponto anterior ficar nesta data, os dois assuntos podem ser tratados na mesma sessão);
- 2026-08-31 — demonstração do núcleo funcional e decisão sobre a componente de identidade;
- 2026-09-07 — validação do protocolo experimental congelado;
- 2026-09-18 — envio do draft integral da dissertação;
- 2026-09-23 — data solicitada para o vosso feedback final;
- 2026-09-25 — fecho académico e administrativo, antes da submissão a 2026-09-29.

Se preferirem outro dia ou formato para a reunião, tenho disponibilidade flexível.

Com os melhores cumprimentos,
Rui Duarte
ruimfduarte94@gmail.com
