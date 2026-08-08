# PROGRESS — estado por item do plano integrado

Estados permitidos: `Pendente`, `Em curso`, `Bloqueado`, `Concluído`, `Cortado`
(plano §1). Nenhum `Concluído` sem evidência.

Atualizado: 2026-08-08.

## Bloco 07–09/08 (G0)

| Item do plano | Estado | Evidência |
|---|---|---|
| Inicializar Git | Concluído | repo `Claude/` (`git log`) |
| Contratos e schemas normativos | Concluído | `src/CONTRACTS.md` v1.1, `src/schemas/*.json`; validados por `tests/test_schemas.py` |
| Âmbito/RQs/matriz claim→evidência fechados | Concluído (draft p/ orientadores) | `docs/g0/ambito_e_rqs.md`, `docs/claim_evidence_matrix.{csv,md}` (15 claims, todos Pendente) |
| Backlog e registo de riscos | Concluído | `docs/g0/backlog.md`, `docs/g0/riscos.md` (R1–R15) |
| Guia WSL2 Ubuntu 24.04 (ext4) | Concluído (guia) | `docs/setup/wsl2_ubuntu_yocto.md` — execução da instalação é ação do estudante |
| Pedido de VM ARM (Hetzner CAX21) | Bloqueado | requer conta/pagamento do estudante; checklist em `docs/setup/vm_arm64_hetzner.md` |
| Email de âmbito aos orientadores (G0) | Bloqueado (envio) | draft pronto em `docs/g0/email_orientadores_G0.md` — envio é ação do estudante |
| Quarentena de resultados sem evidência | Concluído (neste repo) | cap. 5 tem 16 `\todo{pending data-v1}` e zero números; grep sem claims Pi/SSI |

## Blocos seguintes (G1–G7) — desenvolvimento antecipado sem VM/WSL

| Item | Estado | Evidência |
|---|---|---|
| Manifesto kas + layer meta-egw (G1) | Concluído (código) / Bloqueado (build) | `src/yocto/` com pins verificados 07/08; build/boot QEMU requer WSL2 ext4 |
| Compose ARM64 mínimo + Mosquitto TLS + Ditto/MongoDB (G2) | Concluído (código) / Bloqueado (deploy) | `src/deployment/`; `docker compose config` OK; digests arm64 verificados 07/08 |
| Controlador MQTT→Ditto (G2) | Concluído (código+testes) | `src/egw_controller/`; 185 testes; revisão adversarial aplicada |
| Simulador unificado 3 wearables, 6 cenários (G2–G3) | Concluído (código+testes) | `src/egw_simulator/`; determinismo verificado; revisão aplicada |
| WoT TD 1.1 (G2–G3) | Concluído | `src/things/`; `tests/test_things.py` cruza TD↔schema |
| Harness experimental + análise (G3–G4) | Concluído (código+testes) | `src/egw_experiments/`; definições do plano §7.3; revisão aplicada |
| Estrutura de evidência `results/` | Concluído | `experiments/results/{raw,processed,figures}` |
| Dissertação (esqueleto sem números inventados) | Concluído (esqueleto) | `thesis/latex/` compila: main.pdf 46 pp., 0 refs/citações por resolver; 15 refs verificadas |
| Suite de testes | Concluído | **400 testes a passar** (Windows, Python 3.14, venv) |

Nota: "Concluído (código)" significa pronto e testado unitariamente neste
repositório; os gates G1/G2 só fecham com evidência de execução real
(boot QEMU, deploy ARM), que depende das ações externas abaixo.

## Dependências externas (não executáveis por agente)

1. Instalar Ubuntu 24.04 no WSL2 e correr o build Yocto (guia pronto em `docs/setup/`).
2. Criar a VM Hetzner CAX21 (ou equivalente ARM64) e registar specs.
3. Enviar o email G0 aos orientadores e confirmar regras administrativas da extensão.
