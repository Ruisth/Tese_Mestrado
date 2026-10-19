# Yocto image vs Debian 13 — measurement summary

**Exploratory comparison: n=3 per scenario, one QEMU/TCG profile, no statistical significance claimed.** Generated 2026-10-19T00:39:26Z from 6 run(s). Plan `/home/ruisth/egw-compare/measure/plan-a02.working.json` (sha256 `93a034d04f0b0a3b2c514f084bf0e3524d70896054610554abe4fde935172bc6`), 6 planned run(s).

| Metric | Yocto: runs in plan order | Yocto median | Yocto min–max | Debian 13: runs in plan order | Debian 13 median | Debian 13 min–max |
|---|---|---|---|---|---|---|
| Run id | cmp-p1-yocto-a02 / cmp-p2-yocto-a02 / cmp-p3-yocto-a02 | — | — | cmp-p1-debian13-a02 / cmp-p2-debian13-a02 / cmp-p3-debian13-a02 | — | — |
| Pair | 1 / 2 / 3 | — | — | 1 / 2 / 3 | — | — |
| Order in pair | 1 / 2 / 1 | — | — | 2 / 1 / 2 | — | — |
| Seed | 2026101801 / 2026101802 / 2026101803 | — | — | 2026101801 / 2026101802 / 2026101803 | — | — |
| Boot to first ssh answer, s (`boot_ssh_s`) | 15.8 / 15.8 / 16.4 | 15.8 | 15.8–16.4 | 46.0 / 46.3 / 46.8 | 46.3 | 46.0–46.8 |
| Launch to stack ready (/ready 200), s (`stack_ready_s`) | 238.8 / 241.3 / 243.5 | 241.3 | 238.8–243.5 | 322.3 / 338.8 / 314.2 | 322.3 | 314.2–338.8 |
| Launch to gateway functional (twin read back), s (`gateway_functional_s`) | 256.8 / 258.8 / 261.2 | 258.8 | 256.8–261.2 | 341.9 / 361.6 / 338.2 | 341.9 | 338.2–361.6 |
| Guest memory used at rest, median, MiB (`mem_rest_median_mib`) | 1893.6 / 1892.9 / 1933.4 | 1893.6 | 1892.9–1933.4 | 2233.7 / 2296.3 / 2292.3 | 2292.3 | 2233.7–2296.3 |
| Guest memory used at rest, max, MiB (`mem_rest_max_mib`) | 2050.7 / 2070.6 / 2093.3 | 2070.6 | 2050.7–2093.3 | 2406.9 / 2487.7 / 2458.8 | 2458.8 | 2406.9–2487.7 |
| Memory samples at rest (`mem_rest_samples`) | 110 / 110 / 110 | 110 | 110–110 | 103 / 103 / 102 | 103 | 102–103 |
| Measured window on the host monotonic clock, s (`load_duration_monotonic_s`) | 600.151 / 600.177 / 600.146 | 600.151 | 600.146–600.177 | 600.166 / 600.144 / 600.124 | 600.144 | 600.124–600.166 |
| Measured window as a UTC span (informational), s (`load_window_utc_span_s`) | 584.428 / 580.270 / 579.164 | 580.270 | 579.164–584.428 | 582.365 / 581.217 / 578.148 | 581.217 | 578.148–582.365 |
| Host wall-clock step inside the window: UTC span − monotonic duration, s (`wall_clock_step_s`) | -15.723 / -19.907 / -20.982 | -19.907 | -20.982–-15.723 | -17.801 / -18.927 / -21.976 | -18.927 | -21.976–-17.801 |
| Controller marker lag at the run end, s (`clock_pairing_marker_lag_s`) | 0.026 / 0.018 / 0.019 | 0.019 | 0.018–0.026 | 0.079 / 0.085 / 0.045 | 0.079 | 0.045–0.085 |
| Host–guest event pairs in the clock cross-check (`clock_pairing_pairs`) | 4514 / 4510 / 4416 | 4510 | 4416–4514 | 2567 / 2483 / 2459 | 2483 | 2459–2567 |
| Clock cross-check: window end from the pairs − from the marker, s (`clock_pairing_discrepancy_s`) | -0.015 / -0.012 / -0.008 | -0.012 | -0.015–-0.008 | -0.071 / -0.058 / -0.031 | -0.058 | -0.071–-0.031 |
| Measured window start on the guest monotonic clock, s (`mem_load_window_start_guest_s`) | 504.655 / 506.498 / 507.842 | 506.498 | 504.655–507.842 | 604.643 / 625.011 / 600.395 | 604.643 | 600.395–625.011 |
| Measured window end on the guest monotonic clock, s (`mem_load_window_end_guest_s`) | 1104.807 / 1106.675 / 1107.988 | 1106.675 | 1104.807–1107.988 | 1204.809 / 1225.155 / 1200.519 | 1204.809 | 1200.519–1225.155 |
| Guest memory used inside the measured window, median, MiB (`mem_load_median_mib`) | 1911.6 / 1922.7 / 1981.9 | 1922.7 | 1911.6–1981.9 | 2304.3 / 2289.6 / 2316.2 | 2304.3 | 2289.6–2316.2 |
| Guest memory used inside the measured window, max, MiB (`mem_load_max_mib`) | 2084.9 / 2089.9 / 2153.3 | 2089.9 | 2084.9–2153.3 | 2488.6 / 2501.1 / 2534.2 | 2501.1 | 2488.6–2534.2 |
| Memory samples inside the measured window (`mem_load_samples`) | 541 / 541 / 541 | 541 | 541–541 | 495 / 491 / 493 | 493 | 491–495 |
| Whole load-phase sampler file, median, MiB (transparency only) (`mem_loadfile_median_mib`) | 1911.9 / 1922.4 / 1975.1 | 1922.4 | 1911.9–1975.1 | 2305.6 / 2301.0 / 2307.2 | 2305.6 | 2301.0–2307.2 |
| Whole load-phase sampler file, max, MiB (transparency only) (`mem_loadfile_max_mib`) | 2104.3 / 2098.4 / 2153.3 | 2104.3 | 2098.4–2153.3 | 2500.9 / 2501.1 / 2534.2 | 2501.1 | 2500.9–2534.2 |
| Whole load-phase sampler file, samples (`mem_loadfile_samples`) | 1029 / 1033 / 1042 | 1033 | 1029–1042 | 1217 / 1233 / 1245 | 1233 | 1217–1245 |
| Root filesystem used before load, KiB (`df_root_used_kib`) | 500828 / 500964 / 502312 | 500964 | 500828–502312 | 1493412 / 1489648 / 1493844 | 1493412 | 1489648–1493844 |
| /var/lib/docker used before load, KiB (`df_docker_used_kib`) | 2071164 / 2071140 / 2071148 | 2071148 | 2071140–2071164 | 2071152 / 2071224 / 2071168 | 2071168 | 2071152–2071224 |
| Valid messages sent (`sent_valid`) | 6720 / 6720 / 6720 | 6720 | 6720–6720 | 6720 / 6720 / 6720 | 6720 | 6720–6720 |
| Published rate, msg/s (sent_valid / load_duration_monotonic_s) (`published_rate_msg_s`) | 11.20 / 11.20 / 11.20 | 11.20 | 11.20–11.20 | 11.20 / 11.20 / 11.20 | 11.20 | 11.20–11.20 |
| Delivered unique (accepted within the deadline) (`delivered_unique`) | 4430 / 4426 / 4327 | 4426 | 4327–4430 | 2480 / 2394 / 2364 | 2394 | 2364–2480 |
| Accepted between the two boundary samples (counter difference) (`accepted_between_samples`) | 4692 / 4657 / 4604 | 4657 | 4604–4692 | 3051 / 2973 / 2962 | 2973 | 2962–3051 |
| Span between the two boundary samples, s (`accepted_rate_span_s`) | 600.660 / 600.322 / 599.971 | 600.322 | 599.971–600.660 | 599.550 / 600.046 / 600.070 | 600.046 | 599.550–600.070 |
| Window start − start boundary sample, s (`accepted_rate_start_gap_s`) | 0.860 / 0.856 / 0.529 | 0.856 | 0.529–0.860 | 0.094 / 0.215 / 0.081 | 0.094 | 0.081–0.215 |
| Window end − end boundary sample, s (`accepted_rate_end_gap_s`) | 0.351 / 0.711 / 0.703 | 0.703 | 0.351–0.711 | 0.710 / 0.314 / 0.136 | 0.314 | 0.136–0.710 |
| Estimated accepted rate between the boundary samples, msg/s (`accepted_rate_est_msg_s`) | 7.81 / 7.76 / 7.67 | 7.76 | 7.67–7.81 | 5.09 / 4.95 / 4.94 | 4.95 | 4.94–5.09 |
| Delivery rate (`delivery_rate`) | 0.6592 / 0.6586 / 0.6439 | 0.6586 | 0.6439–0.6592 | 0.3690 / 0.3563 / 0.3518 | 0.3563 | 0.3518–0.3690 |
| Lost (no confirmation within the deadline) (`lost`) | 2290 / 2294 / 2393 | 2294 | 2290–2393 | 4240 / 4326 / 4356 | 4326 | 4240–4356 |
| Late confirmations (`late_confirmations`) | 84 / 84 / 89 | 84 | 84–89 | 87 / 89 / 95 | 89 | 87–95 |
| Duplicates (`duplicates`) | 0 / 0 / 0 | 0 | 0–0 | 0 / 0 / 0 | 0 | 0–0 |
| Double accepted (`double_accepted`) | 0 / 0 / 0 | 0 | 0–0 | 0 / 0 / 0 | 0 | 0–0 |
| Latency p50, ms (`latency_ms_p50`) | 218837.7 / 220130.9 / 225307.9 | 220130.9 | 218837.7–225307.9 | 349580.1 / 350634.2 / 361070.3 | 350634.2 | 349580.1–361070.3 |
| Latency p95, ms (`latency_ms_p95`) | 263265.0 / 264386.2 / 269236.4 | 264386.2 | 263265.0–269236.4 | 433717.3 / 441800.1 / 446041.9 | 441800.1 | 433717.3–446041.9 |
| Latency samples (`latency_samples`) | 4430 / 4426 / 4327 | 4426 | 4327–4430 | 2480 / 2394 / 2364 | 2394 | 2364–2480 |
| At the harness fetch: accepted in time (`fetch_accepted_in_time`) | 4430 / 4426 / 4327 | 4426 | 4327–4430 | 2480 / 2394 / 2364 | 2394 | 2364–2480 |
| At the harness fetch: accepted late (`fetch_accepted_late`) | 84 / 84 / 89 | 84 | 84–89 | 87 / 89 / 95 | 89 | 87–95 |
| At the harness fetch: no outcome (`fetch_no_outcome`) | 2206 / 2210 / 2304 | 2210 | 2206–2304 | 4153 / 4237 / 4261 | 4237 | 4153–4261 |
| After the drain: accepted in time (`drain_accepted_in_time`) | — / 4426 / 4327 | 4376.5 | 4327–4426 | 2480 / 2394 / 2364 | 2394 | 2364–2480 |
| After the drain: accepted late (`drain_accepted_late`) | — / 2294 / 2393 | 2343.5 | 2294–2393 | 4240 / 4326 / 4356 | 4326 | 4240–4356 |
| After the drain: accepted without an ack instant (`drain_accepted_no_ack`) | — / 0 / 0 | 0 | 0–0 | 0 / 0 / 0 | 0 | 0–0 |
| After the drain: no outcome (`drain_no_outcome`) | — / 0 / 0 | 0 | 0–0 | 0 / 0 / 0 | 0 | 0–0 |
| Drain, s (`drain_s`) | 338.6 / 344.0 / 353.7 | 344.0 | 338.6–353.7 | 647.6 / 668.3 / 679.0 | 668.3 | 647.6–679.0 |
| Why the measured window is unavailable (`load_window_reason`) | — / — / — | — | — | — / — / — | — | — |
| Why the rate estimate is unavailable (`accepted_rate_reason`) | — / — / — | — | — | — / — / — | — | — |
| Post-drain event log fetch, as the driver said (`drain_fetch_claim`) | not-fetched / fetched / fetched | — | — | fetched / fetched / fetched | — | — |
| Drain result (`drain_result`) | quiet / quiet / quiet | — | — | quiet / quiet / quiet | — | — |
| Harness exit (`harness_exit`) | 0 / 0 / 0 | — | — | 0 / 0 / 0 | — | — |

Notes:

- Probe cadences: ssh 5 s, ready 5 s, accept 3 s, drain 5 s. The start times carry that cadence as their resolution.
- boot_ssh_s, stack_ready_s and gateway_functional_s are host-monotonic seconds from the instant recorded just before the QEMU launch (one clock, the host's /proc/uptime) to the first ssh answer, to the controller's /ready 200 and to the twin read back after the functional event.
- Latency is controller reception → Ditto confirmation, as the controller measures it; it is not simulator → Ditto and does not include the broker leg.
- `lost` means no confirmation within the harness's deadline, not definitive loss; `late_confirmations` counts confirmations that arrived after it.
- Memory is of the whole gateway guest: MemTotal − MemAvailable from the guest's /proc/meminfo, one sample per second (`mem_*_samples` says how many); median and max. It is not the containers' memory and not the host QEMU process. Each sampler line carries `uptime_s`, the guest's /proc/uptime (CLOCK_BOOTTIME, equal to the controller's CLOCK_MONOTONIC while the guest never suspends).
- The measured window lives on MONOTONIC clocks and on nothing else. Its duration is the harness manifest's finished_monotonic_ns − measured_started_monotonic_ns on the harness host (`load_duration_monotonic_s`). Its end on the guest clock is the controller's CLOCK_MONOTONIC instant polled at the run end (controller_monotonic_at_run_end_ns, paired with finished_monotonic_ns), accepted only when the controller marker is ok and its lag is within its tolerance (`clock_pairing_marker_lag_s`); its start is that end minus the duration (`mem_load_window_start_guest_s`, `mem_load_window_end_guest_s`). The pairing is cross-checked against the host-guest event pairs of sent_events.jsonl/events.jsonl: the minimum of received − publish over at least 100 message ids (`clock_pairing_pairs`) must place the window end within 1.0 s of the marker's (`clock_pairing_discrepancy_s`). When any of this fails the window is unavailable (`load_window_reason`) and every window-dependent cell is empty: 600 s is never assumed, and the two monotonic clocks are never subtracted without this pairing.
- measured_window_utc is never used as the duration or the bounds: the host wall clock can step during a run (it did, by about −13 s, in the first real run). `load_window_utc_span_s` and `wall_clock_step_s` (UTC span − monotonic duration) are informational only.
- Load memory (`mem_load_*`) is bounded to that window: a sampler line counts when window start <= uptime_s <= window end on the guest clock. Warm-up, the confirmation window and the drain are outside it. `mem_loadfile_*` describe the whole load-phase file, including warm-up, confirmation and drain, for transparency only and are not the load figure.
- accepted_rate_est_msg_s is an estimated rate between the two boundary samples (gaps reported), not an exact count inside the window: controller_metrics.csv rows are placed by their guest monotonic_ns; the boundary samples are the last row at or before the window start and the last at or before its end, each required within 5.0 s before its bound (`accepted_rate_start_gap_s`, `accepted_rate_end_gap_s`), with the rows strictly time-ordered and the counter not decreasing; `accepted_between_samples` is the counter difference and `accepted_rate_span_s` the monotonic span between the two rows. `accepted_rate_reason` says why the estimate is unavailable.
- published_rate_msg_s = sent_valid / load_duration_monotonic_s: the simulator's publications during the measured run, not an acceptance rate. delivered_unique keeps the analyser's meaning (accepted within the deadline) and is not divided by anything here.
- sent_valid, delivered_unique, delivery_rate, lost, late_confirmations, duplicates, double_accepted and the latency percentiles are the harness analyser's per_run.csv values, joined by the harness run id; latency_samples is its `latency_count`.
- The post-drain reconciliation is reported apart from the deadline accounting: `fetch_*` are accounting.json's buckets at the harness fetch and `drain_*` its buckets after the drain, per published valid identity (accepted_in_time, accepted_late, accepted_no_ack_time, no_outcome; a bucket absent from the counter is zero by construction); `drain_fetch_claim` is what the driver said about the post-drain event log, and the drain buckets are empty when that log was not read completely. None of these changes delivered_unique, lost or late_confirmations.
- df_*_used_kib are the Used column of `df -P -k` on the guest for / and /var/lib/docker, before the load.
- Median: the middle value of three; with two values their mean; with one, that value. min–max are the extremes of the values available; n says how many. An empty cell is an unavailable value, never a zero.
- ignored, not in the plan: cmp-p1-yocto

Warnings while summarising:

- cmp-p1-yocto-a02: accounting.json: after_drain is null (after_drain_fetch='not-fetched'; the post-drain event log is on disk but its fetch did not succeed: what it holds may be a partial tail, and no figure is claimed from it); drain bucket cells left empty
