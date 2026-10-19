# Minimal comparison Yocto image vs Debian 13 — series a02 (2026-10-18/19)

Exploratory comparison of two complete gateway configurations under one QEMU/TCG profile (`-cpu cortex-a76
-smp 4 -m 8192`, poky native QEMU 8.2.7, the same pinned images and configuration), three pairs of executions
(Y→D, D→Y, Y→D), every metric in each execution. The load — the frozen `nominal` scenario, 600 s at 11.2 msg/s
after 120 s of warm-up — is the synthetic load inherited from the experimental scenario so that the executions
are reproducible and comparable; it is not a requirement, a target or a pass threshold. The figures describe the
observed processing capacity under the load tried; a single load cannot establish a maximum capacity. n = 3 per
scenario; no statistical significance, nothing about physical ARM, no isolated effect of the distribution (the
configurations differ in kernel, container runtime and userland).

| File | What |
|---|---|
| `table.md` | the comparative table: individual values in plan order, median, min–max and n per scenario, and the interpretation notes |
| `summary.csv` | one row per execution with every column of the table |
| `summary.json` | the same rows plus the per-scenario aggregates, the plan's identity and the rules' constants |
| `plan-a02.json` | the sealed plan (six entries, one seed per pair, `supersedes` the first plan) |

These three files are the corrected summary derivative `summary-a02-v2-20261019T125731Z` (generator commit
`34a5f9d`; inputs and their digests in `summary.json` under `provenance`), produced after the framing order of
2026-10-19 from the unchanged raw records; it replaces the earlier derivative `summary-a02-20261019T003925Z`, which
stays in the original `output_test` package, and is also packaged as
`output_test/runs/2026-10-19/HIST_2026-10-19-compare-measurements-a02-summary-v2`.

How the figures are made: `tools/compare/README.md` section 10 (`measure_base.sh`, `measure_run.sh`,
`measure_series.sh`, `measure_summary.py`) and the two calculation rules there — the load window lives on monotonic
clocks only (the host wall clock stepped back 15.7–22.0 s inside every window), rates are estimates between two
boundary samples. Raw records, logs, seals and the tool identities are outside the repository, in
`output_test/runs/2026-10-19/HIST_2026-10-19-compare-measurements-a02` (583 files, `SHA256SUMS` sha256 `87d7ada7…`),
with the decision note `output_test/decisions/2026-10-19_compare-measurements-a02.md`.

Headline (median of three, Yocto vs Debian 13): boot to ssh 15.8 s vs 46.3 s; stack ready 241.3 s vs 322.3 s;
guest memory inside the measured window 1 922.7 MiB vs 2 304.3 MiB; root filesystem 489 MiB vs 1 458 MiB;
observed acceptance rate between boundary samples 7.76 vs 4.95 msg/s (1.57×); confirmed by the end-of-load
marker + 60 s (the harness's observation limit, not a per-message deadline) 4 426 vs 2 394 of 6 720 (1.85×);
controller latency p50 220 s vs 351 s over those confirmations only (n = 4 426 vs 2 394); drain 344 s vs 668 s.
Queue growth and confirmations after the limit are observed behaviour under that load, not failures against it.
Validity: six executions with a valid harness run; five with the post-drain collection verified — in those five
every published identity was accepted by the end of the drain; the first Yocto execution (`cmp-p1-yocto-a02`)
keeps its localised instrumentation fault and enters no after-drain figure (reconciliation: Yocto n = 2,
Debian 13 n = 3). Time alignment: marker lag 0.018–0.085 s, pairing discrepancy ≤ 0.071 s, probe cadences
5/5/3 s, sampler about 1 s. Conclusion: in the emulated conditions tried, the Yocto configuration showed shorter
start-up times, lower memory and disk use and a higher observed acceptance rate than the Debian 13
configuration; exploratory results that establish no maximum capacity, no behaviour on physical ARM and no
isolated effect of the distribution.
