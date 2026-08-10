# docs/ — índice

Documentação do projeto EGW. Fonte normativa de âmbito, cronograma e gates:
[`../../PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`](../../PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md);
contratos técnicos internos: [`../src/CONTRACTS.md`](../src/CONTRACTS.md).

## G0 — âmbito e arranque (pt-PT)

| Ficheiro | Conteúdo |
|---|---|
| [`g0/ambito_e_rqs.md`](g0/ambito_e_rqs.md) | Objetivo, RQ1–RQ3 (inglês), âmbito P0/P1, fora de âmbito e premissas fechadas |
| [`g0/email_orientadores_G0.md`](g0/email_orientadores_G0.md) | Draft do email de âmbito aos orientadores (gate G0; envio é ação do estudante) |
| [`g0/backlog.md`](g0/backlog.md) | Backlog acionável por gate (G0→G7) com estado, evidência esperada e dependências |
| [`g0/riscos.md`](g0/riscos.md) | Registo de riscos com sinais antecipados e mitigação: R1–R8 (plano §11), R9–R15 (operacionais), R16–R27 (auditoria externa) e RA1–RA15 (reanálise externa, seguidos linha a linha) |

## Integridade claim→evidência (pt-PT)

| Ficheiro | Conteúdo |
|---|---|
| [`claim_evidence_matrix.csv`](claim_evidence_matrix.csv) | Matriz claim→evidência (fonte de dados, plano §6.3) |
| [`claim_evidence_matrix.md`](claim_evidence_matrix.md) | Vista legível da matriz e regras de manutenção |
| [`evidence/tests/`](evidence/tests/) | Registos selados de execução da suite (JUnit + stdout + ambiente + `SHA256SUMS`). Evidência **M2**: unitária, com fakes, em Windows — não fecha gate nem valida claim |

## Guias de setup (EN — executados pelo estudante)

| Ficheiro | Conteúdo |
|---|---|
| [`setup/wsl2_ubuntu_yocto.md`](setup/wsl2_ubuntu_yocto.md) | WSL2 + Ubuntu 24.04 + Yocto Scarthgap + kas + QEMU e evidência para o G1 |
| [`setup/vm_arm64_hetzner.md`](setup/vm_arm64_hetzner.md) | Checklist da VM ARM64 (Hetzner CAX21), manifesto de ambiente, Docker, hardening e teardown |

## Decisões de arquitetura (EN)

| Ficheiro | Conteúdo |
|---|---|
| [`adr/README.md`](adr/README.md) | Índice e convenções dos ADRs (0001–0006 aceites em 07/08/2026) |
