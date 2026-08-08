# LOG — repositório Claude (Tema 1, Edge Gateway)

Formato: **Data · Fase · Ação · Resultado · Artefactos · Decisões · Próximos passos**
(igual ao `../LOG_Projeto.md`; este LOG cobre apenas o trabalho dentro de `Claude/`).

---

## Entrada #C001
- **Data:** 2026-08-07
- **Fase:** Bloco 07–09/08 (G0) do plano integrado
- **Ação:** Criação do repositório `Claude/` com Git, estrutura conforme o
  C2DTA Student Repository Template, e fixação dos contratos normativos internos.
- **Resultado:** Esqueleto do repositório; `src/CONTRACTS.md` v1.0 (tópicos MQTT,
  envelope, mapeamento de twins Ditto, endpoints do controlador, CLI do simulador,
  formato `events.jsonl`, variáveis de ambiente, portas); 4 JSON Schemas
  (envelope v1 + smartwatch/ring/clothing v1, draft 2020-12).
- **Artefactos:** `README.md`, `.gitignore`, `.gitattributes`, `src/CONTRACTS.md`,
  `src/schemas/*.schema.json`, `src/pyproject.toml`, `PROGRESS.md`.
- **Decisões:** medições no nível de topo do payload (continuidade com o payload
  de referência do paper/INTERFACES.md); `unevaluatedProperties: false` para
  rejeição de campos estranhos; namespace UUID v5 do projeto fixado.
- **Próximos passos:** desenvolvimento paralelo dos componentes P0 por ordem de
  entrega (G0 docs → Yocto/kas → deployment → controlador → simulador → harness →
  tese), com testes; verificação com pytest.

---

## Entrada #C002
- **Data:** 2026-08-07/08
- **Fase:** Blocos G0–G3 (desenvolvimento antecipado)
- **Ação:** Construção paralela dos 8 componentes P0 (workflow multi-agente com
  revisão adversarial de conformidade contratual nos 3 pacotes Python).
- **Resultado:**
  - `docs/`: pacote G0 completo (âmbito/RQs, email aos orientadores, backlog por
    gate, riscos R1–R15, matriz claim→evidência com 15 claims, guias WSL2 e
    Hetzner CAX21, ADRs 0001–0006).
  - `src/yocto/`: manifesto kas (formato 14) com pins verificados online em
    07/08 (poky `yocto-5.0.19` → `bb98354`, meta-openembedded scarthgap
    `ef3df29`, meta-virtualization scarthgap `0d9fb7f`), layer `meta-egw`,
    receita `egw-image`, smoke de container, scripts de build/QEMU.
  - `src/deployment/`: compose de 6 serviços com digests arm64 verificados no
    Docker Hub em 07/08 (Ditto 3.9.4, Mosquitto 2.0.22, Mongo 7.0.39), TLS,
    ACL, scripts de certs/auth/lock, Dockerfile do controlador;
    `docker compose config` OK.
  - `src/egw_controller/`, `src/egw_simulator/`, `src/egw_experiments/`:
    implementação completa conforme CONTRACTS + testes.
  - `src/things/` + `diagrams/`: TDs WoT 1.1 e diagramas Mermaid.
  - `thesis/`: esqueleto LaTeX (template ISCTE) compila — main.pdf, 46 pp.,
    0 referências/citações por resolver; 15 entradas bib verificadas via
    Crossref/W3C/OASIS em 07/08; protocolo da revisão scoping.
- **Artefactos:** commits `164e6cd`, `ef5b01c`.
- **Decisões:** ver ADRs e resultados dos agentes (registados nos commits).
- **Próximos passos:** aplicar correções das revisões.

---

## Entrada #C003
- **Data:** 2026-08-08
- **Fase:** Correções pós-revisão; CONTRACTS v1.0 → **v1.1**
- **Ação:** As revisões adversariais encontraram 1 bloqueador + 4 majors;
  contrato emendado e correções aplicadas por 3 agentes.
- **Resultado:**
  - **CONTRACTS v1.1 §4 — dedupe com âmbito por execução** (bloqueador): o piso
    de `seq` só se aplica dentro do mesmo `run_id`; `ingestion` ganha
    `last_run_id`. Sem isto, o warm-up (mesma seed → mesmos `device_uuid`)
    faria rejeitar ~20% das mensagens de cada execução medida como duplicadas,
    e as 10 execuções `smoke` consecutivas falhariam. Testes de regressão:
    warm-up→medida, 10 smokes, replay entre runs.
  - **Prazo de confirmação no domínio de relógio do controlador** (major): o
    analyze deriva o prazo de 60 s de `max(received_monotonic_ns)+janela` dos
    próprios eventos do controlador; o prazo do manifest é informativo
    (`clock_domain: harness-host`). Workflow off-VM documentado (plano §5.1)
    com exemplo de scp dos events.jsonl.
  - **PUBACK best-effort no simulador** (major): espera limitada ao tempo até
    ao próximo evento agendado + drain final; o débito nunca é limitado pelo
    RTT (necessário para o load-sweep a 250 msg/s). CONTRACTS §7 codifica.
  - **`device_type` em `sent_events.jsonl`** formalizado no CONTRACTS §7.
  - Menores: SUBACK antes de ready; contadores `dropped`/`queue_depth` no
    /metrics; validação de UUID em `/twins/{id}`; load-sweep 600→300 s;
    validação de `run_id`/`egw_id` no runner; cobertura de TLS wiring e das
    CLIs; notas dropout-reconnect (silêncio de dispositivo, não desconexão).
- **Evidência:** suite completa **400 passed** (Windows, Python 3.14).
- **Próximos passos (ações do estudante):** enviar email G0; instalar WSL2
  Ubuntu 24.04 e correr build Yocto (guia em docs/setup/); criar VM ARM64 e
  validar `aarch64` até 10/08; confirmar regras administrativas da extensão.
