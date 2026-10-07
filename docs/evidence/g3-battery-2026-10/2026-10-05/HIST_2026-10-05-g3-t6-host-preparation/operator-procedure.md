# G3 — session S4 (test 6 only): operator procedure (2026-10-05)

For the preparation package of S4. It is the working detail behind the request of 2026-10-05 (sections 2 to 6 and 8)
and changes no rule of it: where they differ, the request governs. The steps script, its subcommands and its halts are
in `g3_battery.README.md`. Test 6 is judged under the criterion amended on 2026-10-05 (LOG #C052) with the transition
rule `1a-option-a-2026-10-05` (LOG #C053). G3 stays `Not decided` whatever S4 shows.

## Sequence (one subcommand per invocation; `open`, `row` and `close` detached, launch lines in the README)

0. **Before the window.** The sealed preparation with Rui; his authorisation of S4 and his «estou presente». Host: a
   keepalive client (`exec sleep 43200`) with at least 6 h left, Windows kept awake, no other load, no QEMU process, no
   open session; the clone at `1fd9792` (tree `14f89c4`), the pilot plan holding `controller_restart-r04` `planned`,
   state directory `~/egw-exec/g3-t6-s4` absent.
1. `open S4` — identities (the collector `9e678b02…` included), `t6.sh`, r04 fresh, no t6 attempt but S2's admitted
   one, the root file system `6fce1688…`, keepalive; then the frozen `guest_session_open.sh`, `preflight.sh` (the
   stack's start, the collector's copy and install, 45 s of live collection, `collector-duration` on the uptime
   bounds — **no exception**: any non-zero exit is a halt), the environment copy, `gate_health.sh`, the guest's event
   directories (r04 absent).
2. `row t6` (ceiling 47 min from the row's start) — the gate's image record against S2's, the attempt
   (`…_g3-qualification-t6_attempt02`), the eight runbook lines in one step, the gate after (the controller's restart
   expected, nothing else).
3. Read the step's console, the run directory and `per_run.csv` (below); compare the configuration identity; then
   `classify t6 <finished|failed> <validity> <outcome> @reason.txt @next.txt`.
4. `close` — the controlled close below.
5. Every export verified (the export tool's own verification, then `sha256sum -c` in each package); the operator
   records sealed (`HIST_<UTC date>-g3-t6-s4-operator-records`, after a secret sweep); the result note in
   `output_test/decisions/`: the class, each criterion item with its source, `lost` and `late_confirmations` reported
   apart as a sizing finding, no G3 claim. Keepalive and keep-awake released.

At 47 min the row receives `term t6` (TERM to its process group, never KILL, never QEMU), is exported as interrupted,
and the session closes. No row starts at or after 3 h of host uptime from `UP0`.

## Where each quantity is read

Paths: `RAW6` = `~/egw-tcg/pilot/results/raw/controller_restart-r04` (in the package: `raw/controller_restart-r04/`);
the console = the step `t6` of the attempt (`console/NNN-t6.stdout.txt`; stderr is merged into it).

| Quantity | Where |
|---|---|
| `T6` | the console: `test 6: harness exit 0 and the recorder's cleanup done, run directory sealed, the drain quiet …` (`T6=ok`); `STOP: test 6: the drain gave up …` (`gaveup`); `STOP: test 6: the procedure is INCOMPLETE …` (`harness_cmd` 3); `test 6: resources_proved_down: not read - harness_cmd answered 2 …` (not started); `STOP: test 6: the harness run was not sealed, or it exited N …` with the `[harness] INVALID:` lines above it (exit 1, the reasons); `STOP: test 6: the harness exited 0 but the manifest's drain outcome is '…'` (classified by the manifest); `STOP: test 6: controller_restart-r04 refused as already used (F6='…'), no seed, not ready, not drained or no configuration identity - the harness run was NOT started` (the else branch of line 1425: not started) |
| drain | `RAW6/manifest.json` `drain.outcome` (`quiet`, `gave-up`, `error`); the seal: `RAW6/SHA256SUMS` |
| transition rows, proved-down interval | the console's two lines `test 6: resources_transition_rows: rule=… admitted=… why_not=… count=… instants=…` and `test 6: resources_proved_down: applies=… D=… S=… E=… …`, read from `RAW6/manifest.json` keys `resources_transition_rows` and `resources_proved_down`: reported, they decide nothing |
| `delta` | the console after line 1426: one line per device ending `: OK` or `: MISMATCH`, `/metrics: NOT compared (…)` (expected: no `/metrics` snapshots in test 6), the N1 report lines (reported only); exit 4 = MISMATCH, an `error:` line = exit 1, a usage text = exit 2; any non-zero is followed by `STOP: test 6: delta NOT run … or it exited non-zero`. With `T6` not `ok` the same `STOP` shows `(T6='<value>')` and `delta` did not run: it adds nothing to the class `T6` already gives |
| exactly once | the console after line 1427: `ACCEPTANCE BY THE END OF THE DRAIN controller_restart-r04 (events.post-drain.jsonl): …`, `EXACTLY ONCE …: accepted exactly once=… accepted more than once=… never accepted=…`, then `-> OK: every valid message … has exactly one accepted line …` (exit 0) or `-> FAIL: …` with each `NEVER ACCEPTED:` / `ACCEPTED MORE THAN ONCE:` line (exit 4); `error: …` is exit 1 (inputs not read); a non-zero exit is followed by `STOP: test 6: the per-identity exactly-once check was not run …`. The exit status itself is not printed: the line that precedes the `STOP` names it. With `T6` not `ok` the `STOP` shows `(T6='<value>')` and the check did not run. The line reads `T6` only, so it also runs after a `delta` MISMATCH |
| recovery, delivery | `~/egw-tcg/pilot/results/processed/per_run.csv` (written by line 1428's `analyze`; also `other/processed.after/per_run.csv` in the attempt), the row `run_id=controller_restart-r04`: **`restart_metrics_endpoint_recovery_s`** decides "recovery within 120 s" (`RESTART_RECOVERY_MAX_S`; request, section 6); `restart_functional_recovery_s` and `restart_functional_recovery_source` are reported beside it, `double_accepted`, `lost`, `late_confirmations`, `confirmation_deadline_source` (`controller-marker`), `validity`. C12's row in `acceptance_by_condition.csv` fails on completeness in a pilot tree: test 6 reads its own row |
| configuration identity | `RAW6/configuration_identity.json` (and `simulator/controller_restart-r04.config_identity.json` in the package), compared by the operator with the packet's section 1, as in S2: `broker_conf_sha256` `ea37827c…`; `broker_conf_values`: `max_inflight_messages` 4999, `max_queued_messages` 1000, `max_inflight_bytes` 0, `max_queued_bytes` 0, `persistent_client_expiration` `1h`, `sys_interval` 10; `broker_reloaded` false; `stop_grace_period` `130s`; `controller_image_id` `sha256:9a293fe1…5f46`; `controller_source_commit` `489bc9e…`; `paho_version` 2.1.0; `a3_choice` `a`. A value that differs: test 6 invalid (packet halt 6) |
| plan entry | `other/campaign_plan.before.json` (`planned`) and `.after.json` (the harness's `completed` or `failed`, `validity`) |
| the gate | the console of `row t6` (`GATE t6: pass` or `HALT: … the gate did NOT pass`), `guest-state-delta` (`EXPECTED-RESTART` for `egw-controller-1`, `faults=0 problems=0`) |

## Classification (request, section 6; no class added)

`classify` pairs: pass `valid/pass`; valid failure of the system `valid/fail`; invalid instrumentation
`invalid/unknown`; inconclusive `valid/inconclusive` (`unknown/inconclusive` when unreadable); not started
`not-applicable/not-run`. The observed cause and the evidence control; a `STOP:` is never instrumentation by default,
and an incomplete row is never a pass.

| Class | Test 6, run `controller_restart-r04` (the request's table, as written) |
|---|---|
| Pass | `T6=ok` (harness exit 0, run sealed, drain `quiet`); the controller restarted once mid-run (the restart record at +300 s with exit 0, the capture's `die` and `start`, the gate's `EXPECTED-RESTART` for `egw-controller-1`); recovery within 120 s (`restart_metrics_endpoint_recovery_s`); every `delta` line OK; `acceptance --exactly-once` exit 0 (`double_accepted` 0) |
| Valid failure of the system | `T6=gaveup`; `--exactly-once` exit 4 (a valid message absent, duplicate-only or accepted twice); recovery above 120 s; a `delta` MISMATCH; `double_accepted` above 0 |
| Invalid instrumentation | harness exit 1 with an instrumentation reason (the configuration identity and a rejected `resources.csv` included); `delta` 1 or 2; `--exactly-once` exit 1 or 2; no endpoint recovery value (`analyze`: insufficient instrumentation) |
| Inconclusive | `harness_cmd` 3; a row interrupted at the ceiling (exported `interrupted`, not demonstrated; not classified again) |
| Not started | r04 refused (`F6`), harness exit 2, a precondition |

A `delta` MISMATCH or a duplicate-only identity is a valid failure with the cause not established: the result note
reports no defect of the system for it (packet sections 5 and 6). Rules that stand beside the table, unchanged from
the packet and the request: a configuration value that differs from
the packet's section 1 makes test 6 invalid (packet section 4, halt 6); a step status 97 or 74, or a snapshot,
transcript or export failure, is instrumentation (request, section 5 item 2). Halts before the step: the gate's image
record halt creates no attempt (nothing to classify); the attempt-name halt is classified `not-applicable/not-run`; the
halts after the attempt exists and before the step (attempt fields, copies, sources, guest state before, snapshot
before) are instrumentation, `invalid/unknown`. A failed gate after the
row is a stop condition (3): the row is classified by the cause its record shows, and the gate's result is written
beside the class.

Reported beside the result, deciding nothing: `lost` and `late_confirmations` against the marker plus 60 s (a
sizing finding), `resources_transition_rows`, `resources_proved_down`, the N1 report, and the functional recovery
(`restart_functional_recovery_s`). "Recovery within 120 s" is read on `restart_metrics_endpoint_recovery_s` (the
packet's T6 row: "endpoint recovery ≤ 120 s"; the runbook's Expected: samples resuming within 120 s), as the request
states in section 6; that reading is one of the request's stated choices, so another reading is Rui's decision before
S4, never at classification.

## Stop conditions (request, section 5)

Each halts the session: nothing is repeated, the attempt is classified and exported as it stands, the session is
closed in a controlled way and handed back to Rui. QEMU is never killed or re-launched without Rui's decision.

1. At open, preflight or gate: the clone not at `1fd9792` or not clean; a tool or system identity of section 2 that
   differs; the root file system not at `6fce1688…`; r04 not `planned` or not fresh; a frozen driver ending non-zero
   (`collector-duration` included); the environment copy failing. Test 6 is then not run.
2. Instrumentation: a step status 97 or 74; an export, transcript or snapshot failure.
3. A failed gate: not six healthy services within 900 s; a recorder or collector unit active; an OOM kill.
4. The row past its ceiling (`term t6`).
5. Guest, tunnel, WSL or keepalive lost.
6. Any restoration: nothing on the guest is started, restarted or recreated by hand.

Not done without Rui's decision: any fix, repeat, new identifier, or change to code, configuration, helpers,
thresholds or `DRAIN_*`; a re-launch of QEMU; any signal to QEMU.

## Controlled close

(1) Fetches and cleanups first (the runbook's own, three tries at most; the guest's `/tmp` is lost at power-off).
(2) No row, recorder or collector running. After `term t6` (the ceiling) the recorder `egw-events-controller_restart-r04`
may be left running (bench F1): `close` then halts with nothing stopped; its remedy is the runbook's own cleanup
(`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`) through `hx` on the session's
attempt, three tries at most, recorded, then `close` again; the harness's collector unit ends by itself at its
600 s bound. Any other unit left active: record it, stop nothing by hand, hand back to Rui. (3) The attempt finished and exported as it stands (`classify`). (4)
`close`: the recorded `docker compose --env-file .env --env-file images.lock.env stop -t 130` with its exit status and
the container states; a non-zero stop is a halt and a hand-back, never a forced power-off. (5) The frozen
`guest_session_close.sh`: tunnel down, its own `compose stop -t 60`, the boot's OOM state, power-off, no QEMU left,
root file system hashed, data-disk file listed, export. (6) The script records the post-close root file system value
and lists the data disk's ext4 header, read-only.

## A guest that does not answer while QEMU is alive

**Preserve the state, signal nothing, ask Rui.** Nothing is stopped or powered off from the host; QEMU is left running
and is not signalled; the session stays open; no controlled close is claimed; what is done with QEMU is Rui's decision
in the window (the data disk is at stake). If QEMU has exited, nothing is re-launched and no stop is possible: only the
close driver runs, and the root file system is hashed as it was left. If WSL or the keepalive is lost there is nothing
left to close: the attempts left open are recovered and exported with the export tool (`local_export recover`), and
the loss is reported.
