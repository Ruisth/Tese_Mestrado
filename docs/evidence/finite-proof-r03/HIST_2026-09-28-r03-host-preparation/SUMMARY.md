# Third finite-proof attempt (r03): host preparation (2026-09-28)

- **Authority:** Rui's "Autorizo a sessão" (recorded by the PM, `ChatGPT/FINITE_PROOF_R03_AUTHORISATION_2026-09-27.md`, 2026-09-27 01:01 WEST): one session, one attempt `proof-adr0011-r03`.
- **Tools clone** `~/egw-exec/repo`: `b7b919c` → `b65a06d` (tree `4034520`, the merge of PR #49), fetched from the Windows repository's `origin/dev`; clean before and after, branches unchanged. Executed tooling differs from the image's commit `489bc9e` in `cli.py`, `controller_metrics.py`, `run.py` and `proof.sh` only; `src/deployment` is identical.
- **Helper:** regenerated from the `b65a06d` runbook, sha256 `1634c35bc79d…` (396 lines), `HELPERS OK`; predecessor kept.
- **Unchanged:** controller image `sha256:9a293fe13b1a…` from `489bc9e` (the staged archive matches its record); Yocto checkout and `deploy_source_commit.txt` at `489bc9e`.
- **Preserved disk baseline:** `~/egw-preservation/2026-09-26/egw-data.current-state.img` still hashes to `91e2d7b9…` (mode 0444).
- **Fresh run ID** `proof-adr0011-r03`; no guest running, no open session.
- **Outcome:** prepared, 2026-09-28T20:53:52Z.

Files: `console.txt`, `branches-before.txt`, `branches-after.txt`, `r03_hostprep.sh`, `SHA256SUMS`.
