# Git backup and remote (audit risk R25 / RA13)

Canonical workspace since 2026-08-10: `C:\Users\ruimf\Documents\Projeto Mestrado`.
The repository previously lived in a Nextcloud-synced folder; that sync risk is
now mitigated (sync could propagate a corrupted `.git` faster than anyone
notices). The private remote of section 2 **exists**, so the history is already
held in a second failure domain.

**What is still NOT mitigated:** the bundle under `Claude/backups/` sits on the
same physical disk as the repository, so it survives a mistake in Git but not a
disk failure. The one outstanding item is an **off-machine copy of the newest
bundle** — a different physical device or a different failure domain. The remote
does not replace it: a bundle restores a repository that GitHub never received,
and it is the only backup that survives losing access to the account.

## 1. Local bundle (generated at the end of a working session)

```bash
cd "C:/Users/ruimf/Documents/Projeto Mestrado/Claude"
git bundle create "backups/egw-$(date +%Y%m%d).bundle" --all
git bundle verify "backups/egw-$(date +%Y%m%d).bundle"
```

**Student action:** copy the newest `backups/*.bundle` to a DIFFERENT physical
device (external disk, another machine, cloud drive). Restore test:

```bash
git clone egw-YYYYMMDD.bundle egw-restored && cd egw-restored && git log --oneline
```

## 2. Private remote — it exists

The remote is the private GitHub repository `Ruisth/Tese_Mestrado`, over HTTPS:

```bash
cd "C:/Users/ruimf/Documents/Projeto Mestrado/Claude"
git remote -v
# origin  https://github.com/Ruisth/Tese_Mestrado.git (fetch)
# origin  https://github.com/Ruisth/Tese_Mestrado.git (push)
```

Only a fresh clone or a second machine needs it wired up again:

```bash
git remote add origin https://github.com/Ruisth/Tese_Mestrado.git
git fetch origin
git switch dev
```

### How work reaches the remote

`dev` is the integration branch; `main` receives stable versions from `dev` by
pull request only. An active ruleset on **both** branches requires a pull
request and forbids force-push and deletion, so a direct `git push` to `dev` or
`main` is rejected by the server — pushing a working branch and opening a pull
request is the only route (see `CONTRIBUTING.md`):

```bash
git switch dev && git pull                       # start from an up-to-date dev
git switch -c <type>/g<gate>-<short-objective>
# ... commit ...
git push -u origin <type>/g<gate>-<short-objective>
# then open the pull request into dev on GitHub
```

Rules (archived plan v1.0 §9.2; the evidence boundary is now plan v1.1 §3.1):
- The repo is **private** and stays private until submission decisions say
  otherwise.
- Secrets never enter Git regardless (`.env`, `passwd`, certs are ignored) —
  verify with `git status --ignored` before pushing.
- Tags are reserved for real evidence milestones only: `g1`, `g2`, `exp-v1`,
  `data-v1`, `rc1`, `v1.0-thesis` (audit §5.3 — no anticipatory tags).
  **No tag has been created so far, by choice:** no gate has been accepted, and
  a tag would assert a milestone that has not been reached.
- Push at least at every gate and every data freeze — by pull request, as above.

## 3. Windows <-> WSL2: synchronise through Git, never by copying

The Yocto build MUST run on the WSL2 ext4 filesystem, never on the Windows
NTFS workspace (archived plan v1.0 §5.1; the WSL2/ext4 requirement is restated in plan v1.1 §2). The WSL side is therefore a **git clone**,
not a copy:

```bash
git clone "/mnt/c/Users/ruimf/Documents/Projeto Mestrado/Claude" ~/yocto/egw
```

The `origin` of that clone is the Windows workspace, so changes committed on
Windows propagate with a pull of the **integration branch, `dev`** (`main` only
ever carries stable versions promoted by pull request, so pulling it into the
build tree would silently build an older tree):

```bash
cd ~/yocto/egw && git pull origin dev
```

Cloning straight from the private remote instead
(`git clone https://github.com/Ruisth/Tese_Mestrado.git ~/yocto/egw`) is
equivalent and preferable when the build tree must match what was reviewed:
it then pulls with `git pull origin dev` as well, and carries only what has
actually been pushed.

Never edit the same file on both sides, and never copy files between them by
hand: divergent manual copies are exactly how a "reproducible" build stops
being reproducible. Build artefacts (`build/`, `downloads/`, `sstate-cache/`)
live only inside WSL and are gitignored; the caches sit in `~/yocto-cache`,
outside the clone, so `git clean` cannot destroy them.
