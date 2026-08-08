# Git backup and remote (audit risk R25)

The repository lives inside a Nextcloud-synced NTFS folder. Nextcloud sync is
NOT a Git backup: it can propagate a corrupted `.git` faster than you notice
the corruption. Two complementary measures, both student actions except the
bundle generation:

## 1. Local bundle (generated automatically, copy it OFF Nextcloud)

A full-repository bundle is written to `backups/` (gitignored) at the end of
each working session:

```bash
cd "D:/Nextcloud/Edge Gateway/Claude"
git bundle create "backups/egw-$(date +%Y%m%d).bundle" --all
git bundle verify "backups/egw-$(date +%Y%m%d).bundle"
```

**Student action:** copy the newest `backups/*.bundle` to a location outside
Nextcloud (external disk, another machine). Restore test:

```bash
git clone egw-YYYYMMDD.bundle egw-restored && cd egw-restored && git log --oneline
```

## 2. Private remote (recommended, one-time setup)

Create a **private** repository (GitHub/GitLab — the C2DTA template assumes
GitHub) and push:

```bash
cd "D:/Nextcloud/Edge Gateway/Claude"
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
