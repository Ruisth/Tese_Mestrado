# Experimental results

> **No experimental data exists yet.** This file is the summary surface the
> repository template expects; it is filled from `results/processed/` once the
> campaign runs, and never by hand.

## Status

| Item | State |
|---|---|
| Runs executed | **0** of 95 planned |
| Raw data in `results/raw/` | none |
| Processed tables in `results/processed/` | none |
| Figures in `results/figures/` | none |
| Claims validated | **0 of 15** |
| Protocol frozen (`exp-v1`) | not yet — requires a valid pilot first |
| Data freeze (`data-v1`) | not yet |

The measurement platform (a native, non-burstable ARM64 instance) does not
exist yet; see the risk register (R28) and `PROGRESS.md`.

## How this file gets filled

Everything below the status table is regenerated, never typed:

```bash
python -m egw_experiments analyze --base-dir experiments/results --plan experiments/campaign_plan.json
```

That single command rebuilds `results/processed/` and `results/figures/` from
`results/raw/`, which is sealed and immutable after the data freeze. The tables
quoted here must be copies of those outputs, with the originating `run_id`s
named, so that any number in the dissertation can be traced back to raw data,
the command that produced it and the commit it ran on.

## What will be summarised here

| Condition | Runs planned | Metric reported |
|---|---:|---|
| `qemu_boots` | 5 | functional pass/fail only — never timing (plan v1.1 §3.1) |
| `cold_start` | 10 | time to stack readiness |
| `twin_creation` | 10 | time to first materialised twin |
| `smoke_sequence` | 10 | completion and zero loss |
| `nominal` | 10 | delivery rate, latency p50/p95/p99, CPU and memory |
| `load_sweep` | 40 | the same, per load level, plus the saturation verdict |
| `invalid_payload` | 3 | rejection of intentionally invalid events |
| `dropout_reconnect` | 3 | recovery after a real disconnect |
| `controller_restart` | 3 | delivery across a restart, no double acceptance |
| `soak` | 1 | 24 h stability, sampling continuity, no unrecovered interruption |

## Rules that apply to every number placed here

- A run marked `invalid` never contributes to a table or a figure.
- Load levels without the full set of valid runs are reported as
  `insufficient-evidence`, never as "not saturated".
- The statistical unit is the run, not the message (archived plan v1.0 §7.3; frozen only at `exp-v1` under D007).
- No value appears in the dissertation before it appears here, and none appears
  here before it exists in `results/raw/`.
