# Third attempt (r03) run plan — one bounded guest session

Tools clone `R=/home/ruisth/egw-exec/repo` at `b65a06d` (merge of PR #49: quiet timer and proof-only fast metrics retry; clean); controller image and guest deployment as left by r01 (`489bc9e`). Every command runs as `wsl -d Ubuntu-24.04 --exec bash -lc '<cmd>'`, long steps in the background; WSL keepalive and Windows keep-awake held.

1. `cd $R && bash tools/session/guest_session_open.sh` — exit 0 required, else step 6 if a guest is up.
2. `cd $R && bash tools/session/preflight.sh` — its interlock verifies the loaded image against its record and starts the stack; the deployed tree must equal the clone (`src/deployment` identical to `489bc9e`). Exit 0 required, else step 6.
3. `EGW_EXEC_REPO=$R EGW_TOOLS_COMMIT=b65a06d… bash $X/session_steps.sh poststart 1790445352` (the installation epoch of the 2026-09-26 deployment) — the broker's start, no reload, the mounted configuration and the controller label `489bc9e`. Exit 0 required, else step 6.
4. `cd $R && env <the ten authorised values> bash tools/session/gate_health.sh` — exit 0 and a `services-healthy` record with `ALL HEALTHY` and `completed (sample N)`, else step 6.
5. `cd $R && env <the ten values> EGW_PROOF_HEALTHY_RECORD=<that record> bash tools/session/proof.sh proof-adr0011-r03 489bc9e5b5b0660026ea2630b8d1d124049ba2ce` — one attempt; the expected source commit is the image's; the tools' commit is recorded by the driver. Whatever its exit, step 6.
6. `cd $R && bash tools/session/guest_session_close.sh` — always once a guest is up; a failed closure is reported, never forced.

Not repeated from r01 (the guest already holds them, and no change touches them): image load, V-1 probe, candidate deployment. Nothing is repeated automatically.
