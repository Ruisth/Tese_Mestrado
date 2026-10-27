# Package D, v2: refutation pass on the corrected diagnosis and ADR 0011

- **Date:** 2026-09-21
- **Documents under test (not modified):** `backlog_diagnosis.md` (the corrected diagnosis) and `adr-0011-controller-restart-recovery.md` (ADR 0011, Proposed), both beside this report.
- **What this report does:** it tries to refute both documents. It re-derives their figures from the raw files with its own scripts, then tests every causal claim: does the data separate it, or does it rest on an assumption the documents do not name? It checks six items specifically: the populations and their collection instants; warm-up figures presented as window figures; post-drain counts standing in for deadline counts; Little's law presented as a validation; counterfactuals presented as findings; and the sizing of the proposed measurement against the lowest observed service rate.
- **What it does not do:** it accepts nothing, closes no gate and edits neither document. Every duration and rate below comes from an **ARM64 guest emulated under QEMU/TCG**. None of them is native performance, and no capacity or maximum-throughput figure is stated or implied.
- **Method:** read-only. No guest was started, no run repeated and nothing measured live. Only read-only git commands were used (`show`, `diff --stat`, `grep`, `ls-tree`, `merge-base --is-ancestor`, `rev-parse`, `log`). The scripts do not import the v2 scripts: they read the raw files directly. The v2 scripts were read only where a figure did not reproduce, to find the definition behind the difference.

---

## 0. Verdict in brief

Almost every figure reproduces. The documents fail in **five places, all in their reasoning or in how they refer to each other**, not in their arithmetic:

1. **Each document cites the other's round-one version, and the stale text contradicts the current one.** ADR T3 criticises "the capacity probe proposed in `backlog_diagnosis.md` section 7" at 5.0 msg/s and gives the lows as 4.94 and 5.35 msg/s. The v2 diagnosis proposes 2.24 msg/s in section 11, sized on 4.60 msg/s. In the other direction, diagnosis §11.5 orders the two guest runs by the ADR *draft's* 5.0 msg/s proof sizing. The v2 ADR has replaced that proof with 11.2 msg/s, a kill at t+150 s and no timing criterion. The reader receives two incompatible descriptions of the next measurement and of the order of the two runs.
2. **The restart counterfactual on `nominal-r01` is withdrawn in one document and kept in the other.** The diagnosis removes "the 3,593 would have been lost had the process been killed" (§12, last row). ADR §1.7 keeps it and labels it CONSISTENT-WITH. By the ADR's own taxonomy it is ASSUMED: it is a code reading about a kill that never happened.
3. **A warm-up counterfactual survives the drop of the counterfactual.** Diagnosis §9.1 says "every measured message's wait includes that time" (the 126.3 s). That holds literally for only 1,417 of the 6,720 measured messages. For the other 5,303 it is the uniform-shift assumption (R-msg) that §9.2 declares underivable. §7.1(2) and §9.1 also cite "none of the 3,593 … was a warm-up message" as if it bore on the end-of-window count. By count, 750 of the 3,593 are the carried-over backlog (3,593 = 750 + 6,721 − 3,878).
4. **The refutation logic of the proposed probe fails.** (a) Its prediction follows from §7 only under an unstated assumption: that the service rate at 2.24 msg/s is no lower than the saturated rates. (b) A refutation could not revise "the 11.2 msg/s deficit", which is arithmetic. (c) Its ±3 band measures agreement between two instruments, not how much the queue fluctuates: 17 measured passages lasted more than 3 ÷ 2.24 = 1.339 s. (d) On the ad-hoc path, "no outcome at the fetch" is read after `wait` and `drained`, i.e. at a post-drain instant the text does not name.
5. **Several ADR items are PROVED or promised beyond what the data or the protocol give:**
   - Cross-clock instants and group sizes are labelled PROVED. In r01 the groups move by one identity with the clock domain.
   - "14.646 s after the restart command" becomes 14.690 s when mapped to the command's own clock.
   - Option 2's "151 to 371" contradicts §1.3's upper bound of 327 for the same class.
   - P5 ("`latency_ms` keeps its meaning") is false for redelivered deliveries.
   - The acknowledgement rule of option 5 leaves gaps in PUBACK order that the ADR never discusses against the MQTT ordering rule.
   - N8's "rejected … at the restart" is wrong for r01.

The six specific checks are summarised in section 3.

**Count (section 2):** 555 individual figures were checked: 409 in the diagnosis and 146 in the ADR.

| Verdict | Figures |
|---|---:|
| Reproduced exactly | 512 |
| Reproduced with a different value (both values given below) | 29 |
| Arithmetic reproduced, but the stated meaning or bound does not hold | 10 |
| Not re-derived (quoted round-one values; the documents present them as superseded, not as evidence) | 4 |

---

## 1. Scripts and outputs

All of them are under `scripts/verify/`, beside this report, with outputs in `scripts/verify/out/`. `run_all.sh` re-runs the Python ones inside WSL with `~/egw-exec/venv/bin/python`. `v10_anchors.sh` runs from Git Bash against the Windows worktree.

| Script | Checks | Output |
|---|---|---|
| `vc.py` | independent loaders; clock anchors; numpy-convention percentile written anew | — |
| `v01_populations.py` | diagnosis §0–2, ADR §1.7: deadline, prefix property, P1/P2/P3/P2′/P3′, collection instants, latency by population | `out/v01_populations.out.txt` |
| `v02_rates_queue.py` | diagnosis §3, §7.1(5), §7.2(3), §11.2 lows; ADR N.3–N.5 and the definition behind its 60 s blocks | `out/v02_rates_queue.out.txt` |
| `v03_split_budget.py` | diagnosis §4, §5, §8 cross-check (with anchor sensitivity), §9.1 | `out/v03_split_budget.out.txt` |
| `v04_little.py` | diagnosis §8, over the interval used and over the interval named | `out/v04_little.out.txt` |
| `v05_replays.py` | diagnosis §9.2, both replays, two first-slot conventions | `out/v05_replays.out.txt` |
| `v06_resources.py` | diagnosis §6: both window selections, methods E and C with and without the guest–host offset | `out/v06_resources.out.txt` |
| `v08_restart.py` | ADR §1.1–1.6, R0x.0–R0x.11, the partition under three clock-domain choices | `out/v08_restart.out.txt` |
| `v09_adr_arith.py` | ADR S.1, S.2, P.1–P.3, W; diagnosis §11 sizing and time budget | `out/v09_adr_arith.out.txt` |
| `v10_anchors.sh` | `file:line` spot-check at `35fe8bb` and `3549d46`; code identity; limits; ADR numbering | `out/v10_anchors.out.txt` |
| `v11_libs.sh` | paho-mqtt 2.1.0 and uvicorn 0.52.1 line citations in `~/egw-exec/venv` | `out/v11_libs.out.txt` |
| `v12_reasoning_checks.py` | the figures behind the reasoning objections of section 4 | `out/v12_reasoning_checks.out.txt` |

Sources (all read-only):

- `/home/ruisth/egw-tcg/pilot/results/raw/nominal-r01/` (`manifest.json`, `sent_events.jsonl`, `events.jsonl`, `controller_metrics.csv`, `resources.csv`, `sut_environment.json`, `loadgen_environment.json`);
- `/home/ruisth/egw-exec/attempts/20260919T195827Z_nominal-instrumentation-120-600_attempt01/` (`analysis/`, `commands.jsonl`, `console/`);
- `/home/ruisth/egw-tcg/pilot/results/raw/controller_restart-r01/` and `-r02/`;
- `~/egw-tcg/pilot/campaign_plan.json` and `~/egw-tcg/itest-helpers.sh`;
- the repository through the worktree `../devwt`, at `35fe8bb` and `3549d46`.

The WSL clone `/home/ruisth/egw-exec/repo` is at `b7e0c83` (detached), not at the merged `dev` `35fe8bb`. `src/egw_controller/` is identical at all four commits (`fe954a9`, `8e88670`, `b7e0c83`, `3549d46`, compared with `35fe8bb`) [v10].

---

## 2. Figure by figure

Verdicts: **R** reproduced; **D** reproduced with a different value (both values given); **M** the arithmetic reproduces but the stated meaning or bound does not hold; **Q** quoted, not re-derived.

### 2.1 `backlog_diagnosis.md`

| # | § | Figure(s) in the document | n | Verdict | Re-derived [file → script, output section] |
|---|---|---|---:|---|---|
| D1 | 0 | Poky 5.0.19 `scarthgap`, kernel 6.6.142-yocto-standard, 4 vCPU, 8,204,356 kB | 4 | R | same [`sut_environment.json` → v01 §0]. The file's `captured_utc` is 2026-09-19T00:06:48Z, about 20 h before the run and before the guest session of 19:33:45Z. It was copied in by `--sut-env-from`, so it describes an earlier capture, not the run's boot. |
| D2 | 0 | x86_64 WSL2 host, 16 CPUs | 2 | R | [`loadgen_environment.json` → v01 §0]. This is the load generator's environment; neither file records where QEMU ran. |
| D3 | 0 | `src/egw_controller/` identical `fe954a9` ↔ `3549d46`, `b7e0c83` | 2 | R | empty `diff --stat`, also against `35fe8bb` [v10] |
| D4 | 0 | end marker 2,331,405,170,833 ns, 20:12:45.750Z, lag 0.018718 s | 3 | R | [manifest → v01 §0] |
| D5 | 0 | 600.106644 s; `valid`, no deviations | 2 | R | [manifest → v01 §0] |
| D6 | 2 | deadline 2,391,405,170,833 ns; 60.000000000 s; ≈20:13:45.750Z | 3 | R | [manifest → v01 §A] |
| D7 | 2 | first 3,879 lines byte-identical | 1 | R | [`events.jsonl`, `events.post-drain.jsonl` → v01 §B] |
| D8 | 2 | P1 3,794; scp 20:13:57.289Z; seq 4 end 20:13:58.570Z; newest ack +12.659 s ≈20:13:58.409Z; 11.539 s / 12.820 s | 7 | R | [manifest, `commands.jsonl`, sealed → v01 §C, §D] |
| D9 | 2 | P2 85; acknowledgements +0.012 s … +12.659 s | 3 | R | [v01 §D] |
| D10 | 2 | P3 2,841 | 1 | R | [v01 §C] |
| D11 | 2 | P2′ 2,926; +466.238 s; `drained` 20:13:58.613Z → 20:21:43.488Z, 27 readings over 131 s; scp 20:21:43.527Z → 20:21:44.589Z; newest ack +345.362 s ≈20:19:31.111Z | 9 | R | [`commands.jsonl`, `console/005`, post → v01 §D] |
| D12 | 2 | P3′ 0; `/metrics` 20:21:45.640Z: 8,124 = 8,124, depth 0, in progress 0, dropped 0, errors 0; +134.402 s | 8 | R | [snapshot → v01 §D]. 20:21:45.640Z is the controller's own wall clock (the guest's). The table does not say so, and elsewhere the document keeps that clock apart from the harness wall. |
| D13 | 2 | transitions 3,794 / 85 / 2,841; per device 9 counts; 56.46 % / 43.54 % | 14 | R | [v01 §C; equal to `accounting.json`] |
| D14 | 2 | P3 received before the deadline, acknowledged +12.891 … +345.362 s; 0 received after | 3 | R | [v01 §D] |
| D15 | 2 | 736 null `puback_monotonic_ns` | 1 | R | [v01 §C] |
| D16 | 2 | latency table: 4 rows × (n, mean, p50, p95, p99, max) | 24 | R | [v01 §E], to the millisecond |
| D17 | 2 | `harness_row` 264.429926 / 321.069848 / 323.248067 s | 3 | R | to the microsecond [v01 §E] |
| D18 | 3.1 | 11.200204 msg/s; first +0.156 s, last +600.055 s | 3 | R | [sent → v02 §A] |
| D19 | 3.1 | 671, then 672 × 9; 11.1833–11.2000 msg/s | 3 | R | [v02 §A] |
| D20 | 3.1 | "The run-level rate matches the plan to four decimal places" | 1 | **D** | 11.200204 rounds to **11.2002** at four decimals against the plan's 11.2000, so it matches only at three. n ÷ 600 = 11.200000 exactly, but only with the nominal 600 s, not the measured span [v02 §A]. |
| D21 | 3.1 | `intended_invalid` 0; arrivals 11.201088 msg/s | 2 | R | [v02 §A, §B] |
| D22 | 3.1 | 593 over 120.047 s = 4.939732 msg/s | 3 | R | first sample → last pre-window sample. To the first in-window sample instead: 601 over 121.045 s = 4.965096 [v02 §C]. |
| D23 | 3.1 | 3,863 over 598.261 s = 6.457048; 3,878 = 6.462185; +0.0796 % | 5 | R | [v02 §C] |
| D24 | 3.1 | 3,593 to el +1,005.469 s, 8.863682 msg/s | 3 | R | (n − 1) ÷ span gives 8.863580, as the document says [v02 §C] |
| D25 | 3.1 | 1.734570; 4.743156 msg/s | 2 | R | [v02 §C] |
| D26 | 3.1 | 60 s table: 12 rows × (arrivals, acks, event-log rate, counter rate) | 48 | R | [v02 §D]. One counter cell differs in the fourth decimal: −60…0 is **5.2899** in the document and **5.2900** here (interpolation). |
| D27 | 3.1 | 6.55 → 5.32 → 8.55; 30 s span 5.10 (el 120–150) … 9.47 (el 570–600) | 5 | R | [v02 §D] |
| D28 | 3.2 | 721 samples; depth 0 at .540Z and .566Z; first arrival ≈20:00:45.763Z | 4 | R | [v02 §E] |
| D29 | 3.2 | 599 in window; 752 → 3,590; min 752; 6 decreases, largest 3 | 6 | R | [v02 §E] |
| D30 | 3.2 | 750 (749 + 1); 3,593 (3,592 + 1); 2,926 | 3 | R | [v02 §E] |
| D31 | 3.2 | four counters zero throughout; 35.9 % of 10,000 | 2 | R | [v02 §E] |
| D32 | 3.2 | 2,838 over 598.261 s; 2,837.65; 2,843 over 600.107 s = 4.7375 msg/s; 0.2 % | 5 | R | [v02 §E] |
| D33 | 1, 3.3 | fewer acks than arrivals in 60 of 60 ten-second blocks; 4.60–8.55; 1.7346 | 4 | R | 0 of 60 blocks with acks ≥ arrivals [v02 §D] |
| D34 | 4.1 | 8,064 in FIFO; +0.009955 / +0.193468 / +126.513075 / +126.661899; busy −119.880 → +1,005.469 s; `latency_ms` exact; first per device warm-up; `attempts` 1, `error` null | 9 | R | [v03 §A] |
| D35 | 4.2 | wait: min 126.320, p50 320.194, mean 305.044, max 405.370; own: 59.68 / 112.61 / 130.80 / 217.47 / 2,542.14 ms | 9 | R | [v03 §B]; wait p95 (left blank in the document) is 402.568 s |
| D36 | 4.2 | 99.9571 %; 99.9638 %; 98.6474 %; 126.468 = 126.320 + 0.149 s; 749; 0.0362 % | 7 | R | [v03 §B] |
| D37 | 5 | budget table: 5 rows × (n, mean, p50, p95, 1 ÷ mean) | 25 | R | [v03 §C] |
| D38 | 5 | 751 / 3,878 = 19.4 %; 126.605 / 600.160 s = 21.1 %; M-in by block (8 means, n = 295 and 513); 600.160037 s identity; 6.4616 vs 6.457048 | 16 | R | [v03 §C] |
| D39 | 6.1 | resource table (6 rows × 5) + sum row (4) | 34 | R | [`resources.csv` → v06 §B]. Guest-wall and harness-wall window selections give the same 600 instants [v06 §A]. |
| D40 | 6.1 | ≥ 300: 55; ≥ 350: 5; ≥ 380: 0; 62.06 %; 65.98 % / 63.12 %; 4.27 MiB | 8 | R | [v06 §B] |
| D41 | 6.1 | 68.82 / 12.73 / 16.18 %; 350.94 / 56.78 ms; 720 × 6, max spacing 1.000 s, 1 instant after | 8 | R | [v06 §A, §C] |
| D42 | 6.2 | 36.70 %; "220.19 CPU-seconds in 600.107 s"; ≥ 63.30 % | 3 | R | 220.19 CPU-s is the total over the **600 one-second instants**, not over 600.107 s: over 600.107 s the share is 36.692 %. Immaterial [v06 §C]. |
| D43 | 6.3 | method E: 7.937 / 6.546 / 5.168 / 3.740 / 3.600; r −0.6229; band counts 221/174/149/50/5; 1 below 150 | 12 | R | [v06 §D] |
| D44 | 6.3 | method C: 7.929 / 6.527 / 5.149 / 3.853 / 3.786; r −0.6589 | 6 | **D** | The document describes C as "over the same second". It is not the same second: the v2 script reads the guest-wall resource instants as harness wall (its own comment: "assumes the guest and host wall clocks are synchronised"). Applying the marker's guest − harness offset (+0.126 s) gives **7.904 / 6.538 / 5.174 / 3.860 / 3.791, r −0.6337** [v06 §D]. The sign and the rough size hold, as the document says. |
| D45 | 6.3 | round one's 8.005 → 3.800, r −0.6126; the verification's 7.873, r −0.5972, −0.3869 | 4 | Q | quoted round-one values, shown only as contrast. §0 says "none is taken from the round-one analyses"; these are taken, although not as evidence. |
| D46 | 7.1(5) | 9.47; 11.60; 10.63; 6.90; hook 20:13:48.078Z → 20:13:57.285Z; scp 20:13:57.289Z | 6 | R | [v02 §F] |
| D47 | 7.1(5) | "then 7.90–9.53 until the backlog cleared" | 2 | **D** | the last block, a partial one (158 acks in the 15.36 s to the last acknowledgement), ran at **10.285** msg/s; the range after +90 s is 7.90–10.29 [v02 §F] |
| D48 | 7.2 | last arrival el +600.046 s; stop hook 20:12:45.769Z; last sample 20:12:44.846Z; 11.600 = 1.7965 ×; 89.2857 % (6,000 of 6,720) | 6 | R | [v02 §B, §F; v02 §A] |
| D49 | 8 | snapshots 20:00:42.825Z (0, 0, 60) and 20:21:45.640Z (0, 0, 8,124) | 6 | R | [snapshots → v04] |
| D50 | 8 | ∫N dt = Σ sojourn = 2,143,130.910; T 1,125.348 s; L 1,904.4154; λ 7.1658; W 265.7652; ratio 1 | 6 | **D** (L, λ, T) | The text says the interval is the two `/metrics` snapshots. The figures are computed from the **first arrival to the last acknowledgement** (1,125.348 s). Over the named snapshot interval (1,262.814 s): **L = 1,697.1073, λ = 6.3857 msg/s**; W and the ratio are unchanged [v04 A, B]. The last bullet's "about 405 s with no arrivals" (405.42 s) belongs to the interval actually used. |
| D51 | 8 | fabricated stamps give 1.0000000000 | 1 | R | [v04 C] |
| D52 | 8 | cross-check: 721 samples, mean +0.110, median 0, max \|d\| 3, none outside ±3 | 5 | R | mean −0.110 as sampled minus reconstructed (sign convention) [v03 §D]. The agreement depends on the one anchor: shifted +0.126 s (the guest–harness offset) it gives max \|d\| 5, shifted +0.5 s max \|d\| 8. |
| D53 | 9.1 | 750; 751; 1 at +0.009955; 749; +126.513075; 126.319607 s; 0 warm-up among 3,593 | 7 | R | [v03 §E] |
| D54 | 9.2 | R-msg: 126.3196 s uniform; 4,776 (+982); 1,944 | 4 | R | [v05] |
| D55 | 9.2 | R-slot: mean 101.159 s, 67.063–140.303 s; 4,543 (+749); 2,177 | 5 | **D** (3 of 5) | These values hold only if the first slot is measured **from el 0**. The document's wording ("durations of its observed service slots after el 0") equally fits taking the first inter-acknowledgement gap whole, which gives **101.066 / 66.971–140.211 s** with the same counts [v05]. The convention is not stated. |
| D56 | 9.2 | 168.58 ms vs 151.44 ms | 2 | R | [v03 §C] |
| D57 | 11.2 | 4.6000 / 4.6009; 3.8333; 3.0000; 5.3167 / 5.1000 / 3.9000 | 7 | R | [v02 §D] |
| D58 | 11.2 | 2.24 → 0.200 / 0.040 / 2.000 Hz; 0.487 / 0.584 / 0.747; 1,613 (1,440 + 144 + 28.8); 350.6 s; 12 of 600 zero seconds | 11 | R | [v09; v02 §D]. At the lowest 10 s rate the service would take 537.6 s. |
| D59 | 11.3 | 95 runs, lowest 10.0 msg/s; 133 s; 17.5 min; 23.5 min; 0.0042 msg/s | 5 | R | [`campaign_plan.json` → `commands.jsonl` → v09] |
| D60 | 11.3 | "Hard bound 43.0 min" | 1 | **M** | 900 + 720 + 60 + 900 = 2,580 s is right, but it is **not a bound**. `wait` gives up only after 60 s plus `--extra-timeout`, whose default is 120 s (`itest_reconcile.py:235`, `:604`). `pre` also runs `wait_ready` (up to 60 s). Each `drained` reading can add a 30 s `curl` timeout past `DRAIN_LIMIT_S`. So the bound is at least **46.0 min** [v09]. |
| D61 | 11.3 | runbook `:651`, `:653-654`, `:1004` | 3 | R | [v10 context, runbook read] |
| D62 | 11.5 | "the ADR draft sizes its proof run at 5.0 msg/s against the 6.457 msg/s average" | 2 | **M** | This is true of the round-one draft it names, but v2 ADR 0011 no longer sizes its proof on any rate (11.2 msg/s, kill at t+150 s, no timing criterion). The ordering argument built on it ("this one comes first … that sizing has to be redone") therefore no longer holds. |

### 2.2 `adr-0011-controller-restart-recovery.md`

| # | § | Figure(s) | n | Verdict | Re-derived |
|---|---|---|---:|---|---|
| A1 | Numbering | ADRs 0001–0008 and 0010 at `35fe8bb`; 0009/0011 never added; references at `README.md:72`, `2026-09-17-egw-image-audit.md:615`, `0010…:10`; nothing refers to "ADR 0011" | 4 | R | [`git ls-tree`, `git log --all --diff-filter=A`, `git grep` → v10 and the command in section 6] |
| A2 | Code identity | `35fe8bb` = merge of PR #41, 2026-09-21; `src/` identical to `8e88670` and `fe954a9`; `CONTRACTS.md` differs by one preamble sentence | 3 | R | [v10]. The one preamble line is rewrapped into two, so the diff is 2 insertions and 1 deletion. |
| A3 | Code identity | `Dockerfile:48` `RUN pip install .`; `pyproject.toml:11` `paho-mqtt>=2.1,<3`; paho 2.1.0, uvicorn 0.52.1 and their line citations | 9 | R | [v10, v11] |
| A4 | 1.1 | restart 00:18:15.344Z at t+300 (300.000 s), rc 0; fetch 00:24:18.026Z | 4 | R | [r02 manifest → v08 R02.0] |
| A5 | 1.1 | 6,720 / 3,819 / 2,901; block 1595–3730 = 2,136; block 5956–6720 = 765 | 5 | R | [v08 R02.1–2] |
| A6 | 1.1 | line 307, 00:18:19.443Z; 3,404; 1,536 (1,872 − 336); 1,867; residual 1; 1,594; 58; 1,809; 1,810 | 10 | R | [v08 R02.3–4] |
| A7 | 1.1 | cross-clock 1,536 | 1 | R | via the harness wall; anchor shifts of ±0.5 s give 1,533–1,539 [v08 R02.4] |
| A8 | 1.2 | 22:01:30.951Z; 6,720 / 4,538 / 2,182; 1,760 (2012–3771); 422 (6299–6720) | 6 | R | [v08 R01.0–2] |
| A9 | 1.2 | line 308; 3,416; 1,928 (7,909 − 5,981); 1,487; 1; 2,011; 83; 1,404; 1,405 | 9 | R | [v08 R01.3–4]. The r01 counters for `rejected` (67) and `duplicate` (672) do not move during the old process, so the accepted-only arithmetic holds. |
| A10 | 1.3 | r02 G1–G3b 1,810 / 119 / 56 / 151; bounds [1,809, 1,985] and [151, 327] | 6 | R | the same under every clock choice [v08 R02.7] |
| A11 | 1.3 | r01 G1–G3b 1,405 / **122 / 51 / 182** | 4 | **D** (3) | Reproduced only when the old process's last acknowledgement is mapped through the controller's own wall reading (the guest clock, +0.115 s) while publications stay on the harness clock. With the acknowledgement on the harness wall: **1,405 / 121 / 52 / 182**. With the collector row converted to the harness wall as well: **1,405 / 121 / 51 / 183** [v08 R01.7]. |
| A12 | 1.3 | r01 bounds [1,404, 1,578] and [182, 356] | 4 | **D** (2) | harness-consistent: **[1,404, 1,577]** and **[183, 356]** [v08 R01.7] |
| A13 | 1.3 | 0.23 and 0.83 samples/s | 2 | R | 0.2296 / 0.8331 controller rows per second [v08 R0x.6] |
| A14 | 1.3 | "moving that boundary by one second moves about eleven identities" | 1 | R | 11.2 msg/s × 1 s. It is cited from `restart_evidence.md` (round one), although the ADR says every figure it uses is re-derived by its own scripts. |
| A15 | 1.4 | 2,225 (3,819 − 1,594); r01 2,527 after its block | 2 | R | every one received at least 12.4 s (r02) or 14.0 s (r01) after the restart command finished [v08 R0x.5] |
| A16 | 1.5 | "14.646 s after the restart command (15.906 s in r01), its last at 00:18:29.990Z" | 3 | **D** | Mapped to the harness wall, the clock of the restart command: **14.690 s**, **15.791 s**, **00:18:30.034Z** (r01: 21:55:38.374Z instead of the script's 21:55:38.489Z). The ADR's values come from mapping the controller clock through its own wall reading (the guest clock: −0.044 s in r02, +0.115 s in r01) and subtracting a harness-clock instant [v08 R0x.5]. |
| A17 | 1.5 | 00:18:19.443Z; 00:18:48.558Z; 29.115 s | 3 | R | harness-only [v08 R02.3] |
| A18 | 1.5 | "10.5 s after the last answered poll in r02, and 10.8 s in r01" | 2 | **D** | **10.591 s** and **10.713 s** (10.6 and 10.7) on one clock [v08 R0x.5] |
| A19 | 1.6 | 421 (r02), 503 (r01) null PUBACK among identities with an outcome; `smart_clothing` seq 1422, sent line 1595 | 4 | R | [v08 R0x.11, R02.5] |
| A20 | 1.7 | 3,794 / 85 / 2,841 / 2,926 / 0; 20:13:57.289Z; 20:21:43.527Z; 464.875 s | 8 | R | [v01] |
| A21 | 1.7 | 3,593; 3,590; 35.90 %; 721 samples; `dropped` 0 | 5 | R | [v02 §E, v03 §E] |
| A22 | 1.8 | 4.94 / 6.457 / 8.864 msg/s | 3 | R | [v02 §C] |
| A23 | 1.8 | window 60 s blocks "5.35 to 8.57 msg/s" (script: 6.55, 5.56, 5.35, 5.98, 6.10, 6.18, 6.53, 6.90, 6.88, 8.57) | 2 | **D** | Reproduced only with an unstated coarser method: the last counter sample at or before each edge, divided by the span between samples [v02 §G]. For the same blocks the diagnosis gives **5.3167–8.5500** (event log) and **5.3158–8.4576** (interpolated counter). The two documents quote different values for one quantity without explanation. |
| A24 | 1.8 | 1,445 (r01) and 1,840 (r02) at t+300; 211–378 s for 1,867 | 4 | R | [v08 R0x.10; v09 S.2]. For the meaning of the 211–378 s, see finding R-A6. |
| A25 | 3 | cost table, 9 values | 9 | R | [v09 S.1] |
| A26 | 3 | test 5: 2,016 valid, 326 late | 2 | R | [runbook `:1114` → v10] |
| A27 | 3 (opt. 2) | outage 13.5 s to 33.2 s, "151 to 371 messages" | 4 | **D** (2) | On the harness wall: **13.549 s** and **33.205 s**, i.e. **152 to 372** messages [v08 R02.8]. The upper figure also contradicts §1.3 (finding R-A4). |
| A28 | 3 (opt. 4, 5) | 1,809 / 1,404 / 151 / 182; 128 MiB (`compose.yaml:87`) | 5 | R | [v08; v10] |
| A29 | Decision | 2W ≤ 9,999; 3,593 inside; Mosquitto 2.0.22 (`images.lock.env:39`) | 3 | R | [v09 W; v10] |
| A30 | N8 | `MAX_SAMPLE_GAP_S = 5.0`; r02's 6.0 s gap at 0.83 samples/s | 3 | R | [`protocol.py:112` → v10; v08 R02.6] |
| A31 | N8 | the ingest rule "rejected both restart runs' resource files **at the restart**" | 1 | **M** | Not so for r01. Its warning lists **7** gaps over 5 s, including 6.0 s gaps at **21:59:30Z–21:59:36Z** in both the controller and `ditto-gateway`, about 4 min after the restart [r01 manifest `warnings` → v08 R01.0]. A lifecycle-aware rule for the restarted container would not by itself have saved r01. |
| A32 | Proof | 3,360 messages; 818 (r01) and 988 (r02) queued at t+150 s | 3 | R | [v09 P.1; v08 R0x.10] |
| A33 | Proof | "about 16 to 28 minutes" (965 s / 1,685 s) | 2 | **M** | The arithmetic reproduces, but the harness's 60 s confirmation wait (`post_run_wait_s`) is left out: **17.1–29.1 min** [v09 P.2] |
| A34 | Proof | "Hard ceiling 35 minutes" | 1 | **M** | 900 + 300 + 900 s leaves out the 60 s confirmation wait, the restart command itself (22.7 s in r01, 20.8 s in r02) and `drained`'s per-reading `curl` timeout, so it is not a ceiling [v09 P.3; v08 R0x.0] |
| A35 | Relationship | 3,794 / 2,926; 326 of 2,016; 89.3 % | 4 | R | [v01; v10; v02 §A] |
| A36 | T3 | "offered 5.0 msg/s … the nominal warm-up served 4.94 msg/s and the slowest 60 s block of the window 5.35 msg/s" | 3 | **M** | These describe the **round-one** probe in "section 7". The v2 diagnosis proposes **2.24 msg/s** in **section 11**, sized on **4.60** msg/s, the lowest 60 s block, which lies in the warm-up; the 30 s and 10 s lows are 3.83 and 3.0. The 5.35 is the ADR's own coarser value (A23). |
| A37 | Consequences, alternatives | 1,867 needing 211–378 s | 2 | R | arithmetic [v09 S.2]; for the meaning, see finding R-A6 |

**Tally.** 555 figures (the n column: 409 in the diagnosis, 146 in the ADR). **R** 512. **D** 29: D20 (1), D26 (1 cell), D44 (6), D47 (1, the upper end), D50 (3), D55 (3), A11 (3), A12 (2), A16 (3), A18 (2), A23 (2), A27 (2, the message counts). **M** 10: D60 (1), D62 (2), A31 (1), A33 (2), A34 (1), A36 (3). **Q** 4: D45. Where only part of a row differs, the rest of that row counts as R.

---

## 3. The six specific checks

| Check | `backlog_diagnosis.md` | ADR 0011 |
|---|---|---|
| **Populations separated, each with its collection instant** | **Passes.** P1, P2 and P3 are shown at the harness fetch (scp at deadline +11.539 s; newest line read at +12.659 s), and P2′ and P3′ after the drain (scp at +466.238 s after the first). The transitions are given by identity [v01]. One gap: the proposed probe (§11.4) refutes on "no outcome at the fetch", but on the ad-hoc path the fetch happens only after `wait` and `drained` (`itest-helpers.sh`, `finish`). Its only copy is therefore a post-drain collection, and the text does not name that instant (finding R-D4). | **Passes for `nominal-r01`** (§1.7). **Not applied to the restart runs**: "with an outcome in the fetched copy" lumps on-time and late records together. r02: 3,819 = **3,795 on time + 24 late** (fetch at deadline +2.5 s). r01: 4,538 = **4,439 + 99** (fetch at deadline +8.3 s) [v12 (d)]. The argument about outcome existence is unaffected, but the PM's separation is not carried through. |
| **No warm-up figure presented as a window figure** | **Passes.** D (19.4 % warm-up) and the per-acknowledgement CPU (751 of 3,878 warm-up) are labelled. The lowest 60 s rate, 4.60, is labelled as the first minute of load, first contact included. | **Passes** on labels. But T3 gives the lows as the warm-up *average* (4.94) and a window block (5.35); the lowest 60 s rate observed (4.60, in the warm-up) is missing (A36). |
| **No post-drain count standing in for a deadline count** | **Passes.** Rule 3 of §2 explains why "2,926 inside at the deadline" is the same predicate as P2′. §3.2's reconstruction "2,926 at the deadline" is built from post-drain stamps and presented as a queue fact, not as a delivery count. | **Passes** (§1.7, "Relationship"). |
| **Little's law not called a validation** | **Passes**: §8 calls it an identity and demonstrates this on fabricated stamps. But L and λ are labelled with an interval (the two snapshots, 1,262.814 s) that is not the one used (first arrival → last acknowledgement, 1,125.348 s); over the named interval L = 1,697.1073 and λ = 6.3857 (D50). | Not used. |
| **No counterfactual as a finding unless derived exactly** | **Fails softly.** §9.2 drops both replays, rightly. But §9.1 keeps "every measured message's wait includes that time" (literally true for only 1,417 of 6,720), and §7.1(2) and §9.1 use "none of the 3,593 … was a warm-up message" as if the carried-over backlog had no bearing on the end-of-window count (finding R-D1). | **Fails.** §1.7 labels "a kill at that instant would have put those 3,593 in the class …" CONSISTENT-WITH; by the ADR's own taxonomy it is ASSUMED, and the diagnosis withdrew it (R-A1). §1.8, the consequences and the alternatives state "1,867 need 211 to 378 s", carrying `nominal-r01`'s phase rates over to r02 (R-A6). |
| **Measurement sized against the lowest observed service rate** | **Passes.** 2.24 msg/s is below the lowest 60, 30 and 10 s rates (4.60, 3.83, 3.00; ratio 0.747 at 10 s) [v02 §D, v09]. What fails is the refutation logic, not the sizing (R-D4). | The proof deliberately involves no timing (acceptable), but T3 misreports the lows and describes a superseded probe (A36). |

---

## 4. The reasoning, attacked

A claim counts as *separated by the data* when the data exclude the alternatives. It *rests on an assumption* when an alternative the data allow would give a different conclusion.

### 4.1 `backlog_diagnosis.md`

| Claim | Verdict | Why |
|---|---|---|
| "The latency is queue wait (99.96 %)" | **Separated by the data.** | The split is exact once FIFO order, non-interleaving and continuous business are checked, and all three reproduce [v03 §A–B]. |
| "The wait grew because service fell short of arrivals throughout" | **Arithmetic, correctly presented as a count.** It is not a cause. | — |
| Summary: "**Why** fewer were served than received: one strictly serial consumer; its occupancy … averaged 151.44 ms" | **Rests on an unstated assumption.** | "Served rate = 1 ÷ occupancy" is an identity, and §5 says so. Naming "one strictly serial consumer" as the *reason* presumes the occupancy would not stay the same per message under concurrency, which §7.2(6) says cannot be established. The data give the identity and the ≥ 63.3 % off-CPU bound; they give no "why" (finding R-D3). |
| "≥ 63.30 % of busy time not on a CPU" | **Separated by the data**, given that the consumer was continuously busy and the container CPU is an upper bound on any one thread. | The list of what fills that time (PATCH, event write, scheduling) leaves out one component the code allows: the event-loop thread waiting for the GIL while paho's network thread decodes TLS and runs callbacks, at 11.2 msg/s. This does not change the conclusion ("cannot be divided"), but the list is not exhaustive. |
| §9.1 "every measured message's wait includes that time" (126.3 s) | **Counterfactual stated as an observation.** | Only **1,417** measured messages arrived before the last warm-up acknowledgement (el 126.513). The waits of the other **5,303** contain no warm-up service time at all. Any warm-up effect on them is the propagated shift that §9.2 declares not derivable [v12 (a)]. |
| §9.1 "The queue's growth during the window is not the warm-up backlog: none of the messages in the controller at the window end was a warm-up message"; §7.1(2) uses the same fact | **Non-sequitur.** | Membership by identity follows trivially from FIFO. The *count* at the window end is 3,593 = **750 carried over** + 6,721 arrivals − 3,878 acknowledgements, and **751** of those 3,878 were warm-up messages [v12 (b)]. That the growth (2,843) excludes the 750 is true by definition. Using identity-level composition to suggest the warm-up had no bearing on the end-of-window queue is a counterfactual claim, the one §9.2 drops. |
| §7.2(3) the service rate moved (warm-up, ingress, harness activity confounded) | **Correctly left open.** | — |
| §6.3 association, direction unknown | **Correctly left open.** | Supporting detail: acknowledgements correlate at −0.09 with the controller's own CPU and at −0.595 with the sum excluding the controller [v06 §D]. The association is carried by the other containers, which argues further against any single-cause reading. |
| §6.1 "no CPU saturation was observed in the six sampled containers" | **Nearly empty.** | No container has a CPU limit (`compose.yaml` sets memory limits only [v10]), so a container cannot be "saturated" except through the guest total, which is not sampled. One-second means also hide saturation inside a second. The accurate statement is the second half of the same paragraph: guest-level or host-level saturation cannot be excluded. |
| §11 "if the backlog is a rate deficit at 11.2 msg/s, a load below every rate the run served must not build a queue" | **Rests on an unstated assumption.** | See finding R-D4. |

### 4.2 ADR 0011

| Claim | Verdict | Why |
|---|---|---|
| "at least 1,809 still queued when the process stopped — PROVED" | **PROVED only with an assumption.** | The step from "58 lines after the poll" to "at most 58 left the queue" relies on the code reading that every dequeued message writes a line unless it is the one in progress. The exception path (`service.py:191-197`) consumes a message without a line and raises only `processing_errors`, which the sampler does not record. This does not seem likely here (`ditto.aclose()` comes after the drain, `app.py:160-163`), but by the ADR's own taxonomy the step is ASSUMED. |
| G1–G3b "group sizes are PROVED" | **Overstated.** | The G1 cut compares the harness wall with the harness wall and is PROVED. The G2/G3a cut compares harness publication stamps with a controller-clock stamp converted to wall time, and the G3a/G3b cut compares them with a guest-wall collector row. By the ADR's own rule for the 1,536 these are CONSISTENT-WITH, and in r01 they move by one identity with the choice of clock [v08 R01.7]. |
| §1.5 "PROVED … 14.646 s after the restart command" | **Mixed clocks, overstated.** | Finding R-A3. |
| §1.3 bounds, not a partition | **Separated as bounds.** | Supporting detail: the ADR's own readings — §1.5, a SIGTERM near the last answered poll (CONSISTENT-WITH), and §2(f), `bridge.stop()` before the drain — would place the MQTT disconnect at about 00:18:19.4–00:18:20Z. That puts G2 and G3a in the outage class (a split near 1,810 / 326 / 0), while round one's boundary gave 1,810 / 195 / 131. Both fit the artefacts, which is exactly why the PM's qualification must stand: the partition is assumption-dependent. |
| §1.4 no redelivery after the restart (FIFO argument) | **Sound reasoning from the code.** Labelled correctly. | — |
| §1.7 "a kill at that instant would have put those 3,593 in the class …" | **Counterfactual, mislabelled.** | Finding R-A1. |
| §3 option 2 "In no phase of `nominal-r01` did the served rate reach 11.2 msg/s" | **True of the phase averages only.** | In the first 30 s without ingress the rate was 11.600 msg/s, and 10 s blocks reached 12.9 [v02 §F]. The conclusion drawn ("under continuing ingress … not expected to clear") still holds, since no block under ingress exceeded 9.47. |
| P5 "`latency_ms` keeps its meaning … while the in-flight window was not full" | **False for redeliveries.** | Finding R-A5. |
| Option 5's acknowledgement rule and MQTT ordering | **Unstated protocol constraint.** | Finding R-A7. |
| "nothing in option 5 changes those figures" (Relationship) | **Contradicts N6.** | The `ack` call has an unmeasured cost on the serial path, and by the ADR's own §3 algebra any cost lowers the served rate. "Nothing in option 5 would improve those figures" is what the evidence supports. |

---

## 5. Findings, ranked

| # | Severity | Where | Problem | Fix |
|---|---|---|---|---|
| X1 | **High** | ADR T3; diagnosis §11.5 | Each document describes the other's round-one version: ADR T3 criticises a 5.0 msg/s "capacity probe" in diagnosis section 7, and diagnosis §11.5 orders the runs by the ADR draft's 5.0 msg/s proof. The v2 texts say 2.24 msg/s (§11) and 11.2 msg/s with a kill at t+150 s and no timing criterion. The package gives contradictory instructions for the next guest runs. | Rewrite ADR T3 to cite diagnosis §11 (2.24 msg/s, sized on 4.60 / 3.83 / 3.0 msg/s, not a capacity probe). Rewrite diagnosis §11.5 against the v2 ADR proof, and restate the order of the two runs on grounds that still hold (or say that the order does not matter). |
| R-A1 | **High** | ADR §1.7 | "a kill at that instant would have put those 3,593 in the class …" is a counterfactual from code reading, labelled CONSISTENT-WITH; the diagnosis removed the same statement. | Drop it, or relabel it ASSUMED with the source reading only ("held in an in-process queue; what a kill would do is not observed"), as the diagnosis does. |
| R-D1 | **High** | diagnosis §9.1, §7.1(2) | "every measured message's wait includes that time" holds literally for 1,417 of 6,720; "none of the 3,593 was a warm-up message" is used as if it bore on the end-of-window count, which includes the 750 carried over. | Restrict it to the 1,417 that waited while warm-up messages were served. State the count decomposition 3,593 = 750 + 6,721 − 3,878. Say that the warm-up's effect on later messages is the counterfactual of §9.2 and is not established. |
| R-D4 | **Medium** | diagnosis §11.1, §11.4 | (a) The prediction needs an unstated assumption: the service rate at 2.24 msg/s is no lower than the saturated rates. (b) "The backlog would then not be explained by the 11.2 msg/s deficit alone" does not follow, since at 11.2 msg/s the backlog is arithmetic. (c) The ±3 band is agreement between two instruments (itself sensitive to the anchor), not process variability: 17 measured passages exceeded 1.339 s, so one slow passage at the end of publication can breach it. (d) "No outcome at the fetch" is a post-drain collection on the ad-hoc path. | State the assumption and what a refutation would actually show (a load- or time-dependent service rate). Set the band from the probe's own fluctuation, e.g. judge net growth over the last minutes against the maximum depth seen, not two instants. Name the probe's collection instant and read late confirmations from the stamps. |
| R-A5 | **Medium** | ADR P5, Consequences | For a redelivered delivery, `received_monotonic_ns` is stamped at the redelivery, so `latency_ms` excludes the time it spent in the killed process and at the broker. P5 is false for every redelivery even when the window is not full. The deadline verdict, which compares absolute stamps, is unaffected. | Restrict P5 to first deliveries. State that redelivered identities carry a latency from their redelivery, and report them apart. |
| R-A7 | **Medium** | ADR Decision (acknowledgement row), P2, "Duplicates" | Option 5 acknowledges after the outcome line and never acknowledges a delivery without one. This creates gaps in the order of acknowledgements. The ADR does not weigh this against the MQTT 3.1.1 ordering rules (section 4.6; to be checked: a client sends PUBACKs in the order the PUBLISH packets were received) or against paho 2.1.0's own docstring ("the caller MUST manually acknowledge every message", `client.py:4181`). An unacknowledged delivery on a live session also holds an in-flight slot until the next resumption. | Add the ordering rule to "Open before the decision". State the behaviour for a delivery that ends without a line on a live connection (disconnect to force redelivery, or accept the held slot and bound it), and test it. |
| R-A3 | **Medium** | ADR §1.3, §1.5, R0x.8 | Cross-clock instants and group sizes are labelled PROVED, and the clocks are mixed (the controller clock is mapped through the guest wall and then compared with harness instants): 14.646 → **14.690 s**; 15.906 → **15.791 s**; 10.5 / 10.8 → **10.6 / 10.7 s**; r01 groups 122 / 51 / 182 → **121 / 52 / 182** or **121 / 51 / 183**. | Map every controller stamp through `polled_utc` when comparing with harness instants. Label the cut-dependent sizes CONSISTENT-WITH, as done for the 1,536. |
| R-A4 | **Medium** | ADR §3 option 2 vs §1.3 | "151 to 371 messages" for the outage class counts from the restart command, while the old process was verifiably still receiving until its last answered poll (G1 includes publications up to it). §1.3's identity-based upper bound for the same class is **327**. | Use 151–327 (identity-based), or state that 371 is not a bound on the class. |
| R-A6 | **Medium** | ADR §1.8, Consequences, Alternatives rejected | "1,867 queued need 211 to 378 s" carries `nominal-r01`'s phase rates over to r02: a preliminary service-rate calculation stated as a need. r02's own old process served **5.051 msg/s** under ingress (→ **370 s**) and **5.476 msg/s** between its last answered poll and its last acknowledgement (→ **341 s**) [v08, v09]. | Present it as an illustration conditional on another run's rates, or use r02's own rates with their conditions. Keep the conclusion: far above any plausible stop allowance. |
| R-A8 | **Medium** | ADR N8 | "rejected both restart runs' resource files at the restart" is wrong for r01: 7 gaps, including 6.0 s gaps at 21:59:30–36Z in the controller and `ditto-gateway`, about 4 min after the restart. | Correct N8 for r01. Note that a lifecycle-aware rule for the restarted container would not have made r01's file admissible. |
| R-D2 | **Medium** | diagnosis §8 | L = 1,904.4154 and λ = 7.1658 are over first arrival → last acknowledgement (1,125.348 s), not over the snapshot interval the text names (1,262.814 s → L 1,697.1073, λ 6.3857). | Name the interval actually used, or recompute. |
| R-D3 | **Medium** | diagnosis §1 (Summary "Why …"), §7.1(3) | An identity is presented as the cause ("one strictly serial consumer"); §7.2(6) says the effect of seriality cannot be established. | Rephrase: "each message occupied the single consumer for 151.44 ms on average while ingress ran; what that occupancy consists of, and whether it depends on seriality, is not established". |
| X2 | Low | ADR §1.8 / N.7 vs diagnosis §3.1 | The same 60 s window blocks are 5.35–8.57 (ADR, an unstated coarse counter method) and 5.32–8.55 (diagnosis). | Use the diagnosis's event-log blocks, or state the method. |
| X3 | Low | ADR §1.1–1.2 | On-time and late are not separated among the restart runs' outcomes (r02: 3,795 + 24; r01: 4,439 + 99). | Add the split with the fetch instant (deadline +2.5 s and +8.3 s). |
| R-D5 | Low | diagnosis §3.1 | "matches the plan to four decimal places" is false (11.2002 against 11.2000). | Say "to three decimal places". |
| R-D6 | Low | diagnosis §6.3 | Method C is not "over the same second": guest instants are read as harness wall. | Apply the marker offset (C: 7.904 … 3.791, r −0.6337), or say so. |
| R-D7 | Low | diagnosis §7.1(5) | "7.90–9.53 until the backlog cleared" omits the last, partial block at 10.29 msg/s. | Give 7.90–10.29, or exclude the partial block explicitly. |
| R-D8 | Low | diagnosis §11.3; ADR proof | "Hard bound 43.0 min" is not a bound (≥ 46.0 min with `wait`'s 120 s default and `wait_ready`); the ADR's 16–28 min and "hard ceiling 35 min" leave out the harness's 60 s confirmation wait and the restart command (≈21–23 s). | Add the omitted terms, or call them planning figures. |
| R-D9 | Low | diagnosis §9.2 | R-slot's digits depend on an unstated first-slot convention. | State "first slot measured from el 0". |
| R-D10 | Low | diagnosis §0, §6.1, §6.2, §6.3, §2 | Several small provenance slips. (a) The platform comes from a file captured about 20 h before the run. (b) 220.19 CPU-s is over 600 s, not 600.107 s. (c) Round-one values are quoted despite "none is taken from round one". (d) 20:21:45.640Z is the guest clock, unlabelled. (e) Code is cited at `3549d46` / `b7e0c83`, neither of which is the merged `dev`, and the #C039 pause record is not on `dev` (the ADR says so; the diagnosis does not). (f) "No CPU saturation observed in the six containers" is nearly empty without CPU limits. | Correct each in one line. |
| R-A9 | Low | ADR "Relationship with the throughput problem" | "nothing in option 5 changes those figures" contradicts N6 (the `ack` cost is unmeasured). | "nothing in option 5 would improve them". |
| R-A10 | Low | ADR §1.1, §1.2 | "at least 1,809 / 1,404 … PROVED" relies on the code reading that no message left the queue through the exception path (`processing_errors` is not sampled). | Label that step ASSUMED, or cite the absence of `failed` lines together with the drain order as the reason it is unlikely. |
| R-A11 | Low | ADR §1.3 | "eleven identities per second" is taken from `restart_evidence.md`, although the ADR says every figure is re-derived. | Derive it (11.2 msg/s × 1 s) or cite it as round-one reasoning. |

---

## 6. What I could not establish

1. Whether Mosquitto 2.0.22 enforces or tolerates PUBACKs sent out of receipt order, and whether it resends within a live session. The ADR lists the latter as open; the former is not listed.
2. Whether the MQTT 3.1.1 text reads exactly as recalled in R-A7. It must be checked against the specification before the decision; the project's permitted sources include the MQTT documentation.
3. Whether QEMU ran on the WSL2 host that `loadgen_environment.json` describes; neither environment file records it.
4. Whether the ad-hoc path used for the 1 Hz slice was exactly `run_test … --scenario load-sweep` (the diagnosis says so; I did not trace that attempt).
5. What fraction of the proposed probe's runs would breach the ±3 band through one slow passage. It depends on the passage distribution at 2.24 msg/s, which does not exist yet.

The ADR numbering check (A1) used `git ls-tree 35fe8bb docs/adr/`, `git log --all --diff-filter=A -- 'docs/adr/0009*' 'docs/adr/0011*'` (empty) and `git grep -i "adr/0011\|ADR 0011\|0011-" 35fe8bb` excluding `docs/evidence` and SVG files (no match), all read-only.

---

## 7. Reproduction

From WSL:

```
wsl -d Ubuntu-24.04 --exec bash -lc 'bash "<directory of this report>/scripts/verify/run_all.sh"'
```

and from Git Bash:

```
bash "<directory of this report>/scripts/verify/v10_anchors.sh" "<worktree>" > "<directory of this report>/scripts/verify/out/v10_anchors.out.txt"
```

The scripts use the standard library only, open every source read-only, start no guest, contact no network and write only to `scripts/verify/out/`. Like the documents they test, they sit in a working directory that will not persist on its own: they must travel with this report.

---

**This report refutes figures and reasoning. It accepts nothing, closes no gate, and changes no threshold, deadline, offered load or rule. `nominal-r01` remains a valid run that failed its delivery criterion, and the restart partition 1,810 / 195 / 131 remains assumption-dependent, never direct proof.**
