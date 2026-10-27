# Experimental results

> **The results are not in this file.** Every result of the dissertation is listed, with its data
> and the code that analysed it, in [`../docs/results.md`](../docs/results.md).
>
> This file was the summary surface for the planned 95-run campaign, which the repository template
> expects. **That campaign was not run.** It was replaced by the Yocto–Debian 13 comparison (three
> runs per system), whose results are in [`../docs/results.md`](../docs/results.md) together with
> the test battery and the other records. The rest of this file is kept as the record of the
> planned campaign. Its zeros describe that campaign only, not the project.

## Status of the planned campaign

| Item | State |
|---|---|
| Runs of the planned campaign executed | **0** of 95 planned: the campaign was not run |
| Raw data in `results/raw/` | none: the folder holds only a placeholder file. The data of the results obtained are in `docs/evidence/` or kept locally, as listed in [`../docs/results.md`](../docs/results.md) |
| Processed tables in `results/processed/` | none (same reason) |
| Figures in `results/figures/` | none (same reason) |
| Claims of the planned campaign validated | **0 of 15**. The claims are listed in the [claim–evidence matrix](../docs/history/claim_evidence_matrix.md), now kept as a record |
| Protocol frozen (`exp-v1`) | never: it required a valid pilot first, and the pilot of longer runs was started but not finished |
| Data freeze (`data-v1`) | never: there was no campaign data to freeze |

The campaign environment of the plan adopted on 2026-09-18 was the integrated
Yocto ARM64 guest emulated under QEMU/TCG on the existing x86-64 workstation.
Every timing and resource figure produced there is informational and labelled
emulated: it describes only that configuration and is never native ARM64
capacity, physical-device latency or a performance claim. No native,
non-burstable ARM64 instance exists and none is required by the adopted plan;
its absence is an explicit limitation on RQ3 — see the
[risk register](../docs/history/g0/risks.md) (R28) and the
[state record](../docs/history/PROGRESS.md), both now kept as records.

## How this file was to be filled

Everything below the status table was to be regenerated, never typed:

```bash
python -m egw_experiments analyze --base-dir experiments/results --plan experiments/campaign_plan.json
```

That single command rebuilds `results/processed/` and `results/figures/` from
`results/raw/`, which was to be sealed and immutable after the data freeze. The
tables quoted here were to be copies of those outputs, with the originating
`run_id`s named, so that any number in the dissertation could be traced back to
raw data, the command that produced it and the commit it ran on. The same
`analyze` command is the one used to re-analyse a recorded run of the results
that were obtained ([`../docs/reproduce.md`](../docs/reproduce.md) §5).

## What the planned campaign would have summarised here

| Condition | Runs planned | Metric reported |
|---|---:|---|
| `qemu_boots` | 5 | functional pass/fail only — never timing (plan v1.1 §3.1) |
| `cold_start` | 10 | time to stack readiness |
| `twin_creation` | 10 | time to first materialised twin (first-contact technical provisioning — not the C2DTA business twinning ceremony; see `docs/academic/c2dta_p0_traceability.md`, comparison rule 7) |
| `smoke_sequence` | 10 | completion and zero loss |
| `nominal` | 10 | delivery rate, latency p50/p95/p99, CPU and memory |
| `load_sweep` | 40 | the same, per load level, plus the saturation verdict |
| `invalid_payload` | 3 | rejection of intentionally invalid events |
| `dropout_reconnect` | 3 | recovery after a real disconnect |
| `controller_restart` | 3 | delivery across a restart, no double acceptance |
| `soak` | 1 | 24 h stability, sampling continuity, no unrecovered interruption |

## Rules that were to apply to every number placed here

These rules were written for the planned campaign and are kept as its record.

- A run marked `invalid` never contributes to a table or a figure.
- Load levels without the full set of valid runs are reported as
  `insufficient-evidence`, never as "not saturated".
- The statistical unit is the run, not the message (archived plan v1.0 §7.3; frozen only at `exp-v1` under D007).
- No value appears in the dissertation before it appears here, and none appears
  here before it exists in `results/raw/`.
