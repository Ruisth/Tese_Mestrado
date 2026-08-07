# PROGRESS — estado por item do plano integrado

Estados permitidos: `Pendente`, `Em curso`, `Bloqueado`, `Concluído`, `Cortado`
(plano §1). Nenhum `Concluído` sem evidência.

Atualizado: 2026-08-07.

## Bloco 07–09/08 (G0)

| Item do plano | Estado | Evidência |
|---|---|---|
| Inicializar Git | Concluído | repo `Claude/` (`git log`) |
| Contratos e schemas normativos | Em curso | `src/CONTRACTS.md`, `src/schemas/*.json` |
| Âmbito/RQs/matriz claim→evidência fechados | Em curso | `docs/g0/` |
| Backlog e registo de riscos | Em curso | `docs/g0/` |
| Guia WSL2 Ubuntu 24.04 (ext4) | Em curso | `docs/setup/` — execução da instalação é ação do estudante |
| Pedido de VM ARM (Hetzner CAX21) | Bloqueado | requer conta/pagamento do estudante; checklist em `docs/setup/` |
| Email de âmbito aos orientadores (G0) | Em curso | draft em `docs/g0/` — envio é ação do estudante |
| Quarentena de resultados sem evidência | Concluído (neste repo) | a dissertação deste repo nasce sem números não suportados |

## Blocos seguintes (G1–G7) — desenvolvimento antecipável sem VM/WSL

| Item | Estado | Evidência |
|---|---|---|
| Manifesto kas + layer meta-egw (G1) | Em curso | `src/yocto/` — build/boot QEMU requer WSL2 ext4 |
| Compose ARM64 mínimo + Mosquitto TLS + Ditto/MongoDB (G2) | Em curso | `src/deployment/` — deploy requer VM ARM |
| Controlador MQTT→Ditto (G2) | Em curso | `src/egw_controller/`, testes |
| Simulador unificado 3 wearables, 6 cenários (G2–G3) | Em curso | `src/egw_simulator/`, testes |
| WoT TD 1.1 (G2–G3) | Em curso | `src/things/` |
| Harness experimental + análise (G3–G4) | Em curso | `src/egw_experiments/` |
| Estrutura de evidência `results/` | Concluído | `experiments/results/{raw,processed,figures}` |
| Dissertação (esqueleto sem números inventados) | Em curso | `thesis/latex/` |

## Dependências externas (não executáveis por agente)

1. Instalar Ubuntu 24.04 no WSL2 e correr o build Yocto (guia pronto em `docs/setup/`).
2. Criar a VM Hetzner CAX21 (ou equivalente ARM64) e registar specs.
3. Enviar o email G0 aos orientadores e confirmar regras administrativas da extensão.
