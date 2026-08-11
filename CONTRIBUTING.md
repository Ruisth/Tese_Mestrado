# Convenções do repositório

## Modelo de branches

| Branch | Papel |
|---|---|
| `main` | Apenas versões estáveis, promovidas por pull request a partir de `dev` |
| `dev` | Onde o trabalho aterra, sempre por pull request |
| `<tipo>/g<gate>-<objetivo-curto>` | Ramo de trabalho, criado a partir de `dev` atualizado |

Nunca fazer commit diretamente em `dev` ou `main`. Um ruleset ativo obriga a
pull request nas duas e proíbe force-push e eliminação.

Exemplos de nomes de ramo:

```text
docs/g0-closeout
build/g1-yocto-qemu
feat/g2-arm64-vertical-slice
test/g3-harness-pilot
fix/controller-recovery-readiness
```

## Mensagens de commit

Conventional Commits:

```text
<tipo>(<scope>): <resultado técnico>
```

Exemplos:

```text
build(yocto): validate two qemuarm64 boots
feat(controller): materialise telemetry in Ditto
test(harness): validate live dropout recovery
docs(thesis): complete research methodology
fix(simulator): preserve sequence after reconnect
```

## Política de autoria e metadados

- Todos os commits usam exclusivamente o autor e committer do repositório.
- Não adicionar trailers de atribuição (`Co-authored-by`, `Generated-by`,
  `Assisted-by` ou equivalentes).
- Nomes de ferramentas de assistência não aparecem em títulos, descrições,
  comentários, revisões, mensagens de commit ou metadados de pull request.
  Podem existir livremente em nomes e conteúdos de ficheiros e pastas.

O workflow `.github/workflows/metadata-policy.yml` verifica isto em cada pull
request. Falha a verificação e regista as ocorrências no log da execução; não
publica comentários nem revisões automáticas.

Antes de qualquer push:

```powershell
git config --local user.name
git config --local user.email
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
git log origin/dev..HEAD --format="%h | %an <%ae> | %cn <%ce> | %s"
```

## Âmbito de um pull request

Um PR corresponde a **um objetivo verificável**, tipicamente 1–3 dias de
trabalho, e inclui a implementação, os testes, a documentação, o estado de
gestão e a evidência desse objetivo. As datas pertencem aos milestones e ao
cronograma, não ao conteúdo do PR.

O template em `.github/pull_request_template.md` é preenchido em todos os PRs.

**O merge de um pull request demonstra implementação e verificação; não fecha
um gate.** A aceitação de um gate continua a exigir a evidência definida no
plano e é registada em `PROGRESS.md` e no Anexo C do plano.

## Merge

Usar **Create a merge commit**. Nunca squash nem rebase: o histórico de
commits é referenciado pela evidência arquivada em `docs/evidence/`, e
reescrevê-lo invalidaria essas referências.
