# Tese_Mestrado — EGW: Digital Twin Edge Gateway (Tema 1, C2DTA)

> Consumer-Controlled Digital Twin Architecture — dissertação de mestrado, ISCTE-IUL.
> Fluxo de trabalho: commits e pull requests em `dev`; `main` recebe apenas
> versões estáveis, por PR.

Implementação e dissertação do Edge Gateway ARM64 reproduzível (Yocto/Scarthgap +
serviços contentorizados) que recebe telemetria sintética de três wearables,
valida os eventos e materializa-os como gémeos digitais no Eclipse Ditto.

**Normative source:** `PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md` (held in the workspace OUTSIDE this repository, so it is deliberately not a link; it is converted to `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md` by the language migration)
(plano integrado, v1.0 — 07/08/2026). Este repositório segue o âmbito P0 desse
plano; ver [PROGRESS.md](PROGRESS.md) para o estado por gate.

## Estrutura (segue o C2DTA Student Repository Template)

```
Claude/
├─ src/                  # implementação (simulador, controlador, deployment, Yocto, experiências)
│  ├─ CONTRACTS.md       # interfaces normativas partilhadas (tópicos, envelope, twins, portas)
│  ├─ schemas/           # JSON Schemas versionados (envelope + 3 wearables)
│  ├─ things/            # W3C WoT Thing Descriptions 1.1
│  ├─ egw_simulator/     # simulador CLI unificado (3 wearables, 6 cenários)
│  ├─ egw_controller/    # bridge MQTT→Ditto (FastAPI + validação + idempotência)
│  ├─ egw_experiments/   # harness da campanha experimental + análise
│  ├─ deployment/        # compose ARM64 (Mosquitto TLS, Ditto 3.9.4, MongoDB, controlador)
│  ├─ yocto/             # manifesto kas + layer meta-egw (Scarthgap 5.0.x, qemuarm64)
│  └─ tests/             # testes unitários e de integração
├─ docs/                 # G0 (âmbito, riscos, backlog), ADRs, guias de setup, matriz claim→evidência
├─ thesis/               # dissertação LaTeX (template ISCTE) + protocolo da revisão
├─ experiments/results/  # raw/ (imutável pós-freeze), processed/, figures/
├─ diagrams/             # PlantUML/Mermaid
├─ paper/                # artigo IEEE — fora de âmbito antes da submissão da tese
├─ ai/                   # prompt kits (coding/writing agents)
├─ PROGRESS.md           # estado por item do plano, com evidência
└─ LOG.md                # diário de trabalho (formato do LOG_Projeto.md)
```

## Como começar

- Implementação Python (simulador, controlador, harness): ver [src/README.md](src/README.md).
- Deployment da stack DT em ARM64: ver [src/deployment/README.md](src/deployment/README.md).
- Build Yocto/QEMU: ver [src/yocto/README.md](src/yocto/README.md).
- Preparação do ambiente (WSL2, VM ARM): ver [docs/setup/](docs/setup/).

## Regras deste repositório

- Nada é declarado "Concluído" sem evidência verificável (commit, log, teste, dado).
- `experiments/results/raw/` é imutável após o data freeze (`data-v1`).
- Nenhum número quantitativo entra na dissertação sem dados brutos + manifesto + script.
- Secrets nunca entram no Git; existe `src/deployment/.env.example`.
