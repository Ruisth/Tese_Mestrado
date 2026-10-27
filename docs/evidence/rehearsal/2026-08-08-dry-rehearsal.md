# Dry rehearsal of the frozen campaign — 2026-08-08 (P5.2)

**Nature:** logistics rehearsal only. **No scientific result was produced, no
raw data was written, no tag was created, no claim or gate was touched.**
Everything below was executed against a scratch directory outside the
repository; `experiments/results/` is untouched and still empty.

Commit under test: `03ee5c9` (P5.3), working tree clean.
Command environment: Windows 11, Python 3.14.3, dev venv (`src/requirements.lock`).

## 1. Plan determinism

```
python -m egw_experiments plan --master-seed 42 --output <scratch>/a/campaign_plan.json
python -m egw_experiments plan --master-seed 42 --output <scratch>/b/campaign_plan.json
```

| Check | Result |
|---|---|
| SHA-256 of both plans | `b2897d3fca90e8bed1547b547ab27e63…` (identical) |
| Deterministic for the same master seed | **yes** |
| Protocol version | 1.0.0 |
| Unique `run_id` for every run | **yes** |

## 2. Composition (95 runs)

| Condition | Runs | Runner |
|---|---:|---|
| `qemu_boots` | 5 | external |
| `cold_start` | 10 | external |
| `twin_creation` | 10 | external |
| `smoke_sequence` | 10 | simulator |
| `nominal` | 10 | simulator |
| `load_sweep` | 40 | simulator |
| `invalid_payload` | 3 | simulator |
| `dropout_reconnect` | 3 | simulator |
| `controller_restart` | 3 | simulator |
| `soak` | 1 | simulator |
| **Total** | **95** | 25 external + 70 simulator-driven |

Load-sweep randomisation: exactly 10 runs per rate level (10, 50, 100 and
250 msg/s), interleaved in a seed-derived order (first rates observed:
10, 10, 50, 250, 100, 100, 250, 50, 10, 250, 100, 100, 100, 50 …). The order is
frozen in the plan and the runner never reshuffles it.

## 3. `campaign --dry-run`

```
python -m egw_experiments campaign --plan <plan> --results-dir <scratch>/results --dry-run
```

| Check | Result |
|---|---|
| Runs listed | 95 of 95, in frozen plan order |
| External runs | printed as operator checklist lines carrying the exact `run --external-timings` ingest command |
| Files created under `--results-dir` | **0** |
| Exit code | 0 |

## 4. Minimum logistic wall-clock

Per simulator-driven run: `warmup_s + duration_s + 60 s confirmation + cooldown_s`.

| Condition | Hours |
|---|---:|
| `smoke_sequence` | 0.25 |
| `nominal` | 2.17 |
| `load_sweep` | 5.33 |
| `invalid_payload` | 0.30 |
| `dropout_reconnect` | 0.55 |
| `controller_restart` | 0.55 |
| `soak` | 24.02 |
| **Total (70 runs)** | **33.17** |

**Not included, and each adds real time:** the 25 external runs; stack setup
and teardown; collector start/stop/fetch hooks; evidence transfers; analysis;
and any run that fails validity and must be repeated. The figure is a floor,
not an estimate of the campaign's duration.

Planning consequence: the window between the protocol freeze (`exp-v1`,
06/09) and the data freeze (`data-v1`, 13/09) only accommodates this if the
campaign runs unattended through `campaign` and the pilot has already removed
the validity failures — a single 24 h soak plus ~9 h of other runs leaves
little room for repetition.

## 5. What this rehearsal does NOT establish

- No run was executed; the harness has never talked to a real broker, Ditto,
  or an ARM64 VM.
- No claim moved from `Pendente — sem evidência`; no gate changed state.
- The protocol is **not** frozen: `exp-v1` requires a real pilot first.
- The saturation and soak constants remain **pending advisor sign-off**.
