# Minimal comparison Yocto image vs Debian 13 — series a02 (2026-10-18/19)

Exploratory comparison of the two gateway configurations under one QEMU/TCG profile (`-cpu cortex-a76 -smp 4
-m 8192`, poky native QEMU 8.2.7, the same pinned images and configuration), three pairs of executions
(Y→D, D→Y, Y→D), the frozen `nominal` load (600 s at 11.2 msg/s after 120 s of warm-up), every metric in each
execution. n = 3 per scenario; no statistical significance, no maximum capacity, nothing about physical ARM.

| File | What |
|---|---|
| `table.md` | the comparative table: individual values in plan order, median and min–max per scenario, and the interpretation notes |
| `summary.csv` | one row per execution with every column of the table |
| `summary.json` | the same rows plus the per-scenario aggregates, the plan's identity and the rules' constants |
| `plan-a02.json` | the sealed plan (six entries, one seed per pair, `supersedes` the first plan) |

How the figures are made: `tools/compare/README.md` section 10 (`measure_base.sh`, `measure_run.sh`,
`measure_series.sh`, `measure_summary.py`) and the two calculation rules there — the load window lives on monotonic
clocks only (the host wall clock stepped back 15.7–22.0 s inside every window), rates are estimates between two
boundary samples. Raw records, logs, seals and the tool identities are outside the repository, in
`output_test/runs/2026-10-19/HIST_2026-10-19-compare-measurements-a02` (583 files, `SHA256SUMS` sha256 `87d7ada7…`),
with the decision note `output_test/decisions/2026-10-19_compare-measurements-a02.md`.

Headline (median of three): boot to ssh 15.8 s vs 46.3 s; stack ready 241.3 s vs 322.3 s; guest memory inside
the window 1 922.7 MiB vs 2 304.3 MiB; root filesystem 489 MiB vs 1 458 MiB; accepted within the 60 s deadline
4 426 vs 2 394 of 6 720; controller latency p50 220 s vs 351 s; drain 344 s vs 668 s. Neither configuration keeps
up with the nominal rate in this emulated profile. In the five executions whose post-drain log was read
and verified, every published identity was accepted by the end of the drain (none without outcome); for
`cmp-p1-yocto-a02` that log was not verified by the driver and no such figure is claimed.
