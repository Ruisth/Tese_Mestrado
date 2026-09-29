# Finite proof r03: operator records (2026-09-28)

| File | What it is |
|---|---|
| `console/r03-*.log` | the wrapper console log of each step (open, preflight, post-start check, gate health, proof, close); each ends with the driver's `DRIVER RESULT` line and `<step> exit=N at <host UTC>`; scanned with the project's secret rule before copying (0 hits) |
| `session_plan_r03.md` | the run plan followed |
| `session_steps.sh` | the ad-hoc driver as run for the post-start check (tools commit `b65a06d` and image commit `489bc9e` checked apart) |

Exit codes: open 0, preflight 0, post-start check 0, gate health 0, proof 0 (the evaluator supports), close 0.

Packages are under `runs/2026-09-28/` because the drivers file them by the UTC date of their run IDs (the session ran on 2026-09-28), not under the `runs/2026-09-27/` the authorisation text anticipated.
