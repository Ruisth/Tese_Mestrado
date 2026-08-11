# Git backup and remote (audit risk R25 / RA13)

Canonical workspace since 10/08/2026: `C:\Users\ruimf\Documents\Projeto Mestrado`.
The repository previously lived in a Nextcloud-synced folder; that sync risk is
now mitigated (sync could propagate a corrupted `.git` faster than anyone
notices). **What is still NOT mitigated:** the bundle under `Claude/backups/`
sits on the same physical disk as the repository, so it survives a mistake in
Git but not a disk failure. A copy in a different failure domain, or a private
remote, is still required.

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

## 2. Private remote (recommended, one-time setup)

Create a **private** repository (GitHub/GitLab — the C2DTA template assumes
GitHub) and push:

```bash
cd "C:/Users/ruimf/Documents/Projeto Mestrado/Claude"
git remote add origin git@github.com:<user>/egw-c2dta-thesis.git
git push -u origin main
```

Rules (plan §9.2):
- The repo MUST be private until submission decisions say otherwise.
- Secrets never enter Git regardless (`.env`, `passwd`, certs are ignored) —
  verify with `git status --ignored` before the first push.
- Tags are reserved for real evidence milestones only: `g1`, `g2`, `exp-v1`,
  `data-v1`, `rc1`, `v1.0-thesis` (audit §5.3 — no anticipatory tags).
- After the remote exists, push at least at every gate and every data freeze.

## 3. Windows <-> WSL2: synchronise through Git, never by copying

The Yocto build MUST run on the WSL2 ext4 filesystem, never on the Windows
NTFS workspace (plan section 5.1). The WSL side is therefore a **git clone**,
not a copy:

```bash
git clone "/mnt/c/Users/ruimf/Documents/Projeto Mestrado/Claude" ~/yocto/egw
```

Propagate changes with `git pull` inside WSL after committing on Windows:

```bash
cd ~/yocto/egw && git pull origin main
```

Never edit the same file on both sides, and never copy files between them by
hand: divergent manual copies are exactly how a "reproducible" build stops
being reproducible. Build artefacts (`build/`, `downloads/`, `sstate-cache/`)
live only inside WSL and are gitignored; the caches sit in `~/yocto-cache`,
outside the clone, so `git clean` cannot destroy them.
