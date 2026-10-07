# G3 — request for one bounded session: test 6 only (2026-10-05)

**Status: a request.** It authorises nothing by itself and creates no G3 result; G3 stays `Not decided`. Order: the
Project Manager's register entry of 2026-10-05 after the merges of pull requests #55, #56 and #57 (relayed by Rui):
one short request for test 6, a sealed preparation, then authorisation for one attempt. Test 6 is judged under the
criterion amended on 2026-10-05 (decision record `docs/governance/g3-t5-t6-decisions-2026-10-05.md`, LOG #C052) with
option A's transition rule (LOG #C053); S4 is a run made after that adoption.

**In short.** One session, S4: test 6 once, on plan entry `controller_restart-r04` (seed 1715385812), on the
unchanged candidate, with the procedure and tools merged at `1fd9792`; the new collector is installed by the frozen
preflight at the session's open; about 30–40 min of guest occupation; row ceiling 47 min; whatever the result, the
attempt is exported to `output_test` and the session closed in a controlled way; no repeat, no build, no change to the
candidate beyond the collector the preflight installs, no change to a criterion.

## 1. What is asked

Rui's explicit authorisation for **one** guest session, S4, in a window Rui attends: one attempt of test 6, then a
controlled close whatever the result. S4 starts only on Rui's go in that window; the sealed preparation (section 7) is
delivered first.

## 2. Identity

**Procedure and tools: the merged commit.** `1fd9792…` on `dev` (merge of pull request #57), tree `14f89c4…`, the tree
of the reviewed head `e375026`. Runbook `docs/setup/qemu_integrated_gateway.md` sha256 `31716593…`, 1,624 lines. Test
6's eight lines (1421–1428) are re-extracted verbatim; no identifier is substituted (r04 is the runbook's own literal).

| Tool | Value at `1fd9792` | Against S3 (`8e49261`) |
|---|---|---|
| Helpers of section 6.1 | `e5eba37e…`, 545 lines | unchanged |
| `tunnel.sh`, `ca.crt` | `38f5cae9…`, `556e139f…` | unchanged |
| Export tool `local_export.py` | `544c9b3d…` | unchanged |
| `drivers_sha256` (38 files of `tools/session`) | `2c209b09…` | was `4a6a572d…` (`collector_check.py`, `collector_shortfall.py`, a comment of `preflight.sh`) |
| Collector `collect-resources.sh` | `9e678b02…` | was `11444c0a…` (instrumentation: `uptime_s=` and `boot_id=` on its `start:` and `stop:` records) |

The execution clone `~/egw-exec/repo` moves from `8e49261` to `1fd9792` (detached, clean) at the preparation, so the
harness, its hooks and the identity checks are the merged ones.

**System under test: unchanged, identified apart.** Controller image `egw-controller:0.1.0`, id `9a293fe1…5f46`, from
`489bc9e`; the five pinned images (`images.lock.env` `8a9a05df…`); `compose.yaml` `1a32f6c2…`; `mosquitto.conf`
`ea37827c…`; `CONTRACTS.md` `247e3b02…`; `src/schemas` `1d5284cf…`; kernel `4457ef38…`, `qemuboot.conf` `7739c945…`,
QEMU `5d389c65…`, Yocto checkout `489bc9e`. The clone's `src/deployment` tree becomes `573e902b…` (was `e056d389…`),
differing only by the collector and `README.md`. On the guest the preflight copies and installs the clone's collector
(the previous one kept in `/opt/egw/evidence/collector-previous/`) and then compares the deployed tree with the clone
(`README.md` excepted): the deployed tree then differs from the candidate's recorded one by the collector only. Root file
system expected at `6fce1688…` (the value S3's second close recorded); data disk `egw-data.img`, 34,359,738,368 B,
listed before the boot and after the close, never hashed.

## 3. Plan entry and parameters

`controller_restart-r04`: supplement `g3-t6`, order 96, seed 1715385812 (derived by the plan's own rule), scenario
`nominal`, 600 s at 11.2 msg/s (6,720 messages), warm-up 0; `docker compose restart controller` at +300 s; the
transition rule `1a-option-a-2026-10-05`; drain 130 s quiet, 5 s step, 900 s limit (the runbook's defaults); the
StartedAt read. Added to `~/egw-tcg/pilot/campaign_plan.json` by `plan-supplement` at the preparation; r01–r03 and every
other entry byte-identical (the harness then rewrites r04's own `status` during the run, as it did for r03). Package expected as `…_g3-qualification-t6_attempt02` (attempt01 is S2's invalid r03
attempt, kept).

## 4. Sequence and limits

`guest_session_open.sh`; `preflight.sh` (the stack's start through its interlock, the collector's copy and install,
the deployed tree against the clone, health, 45 s of live collection and `collector-duration` judged on the uptime
bounds — no exception this time); the environment copy as in S1–S3; `gate_health.sh`; row t6 (`--purpose official`);
its classification; the recorded `compose stop -t 130`; `guest_session_close.sh`.

| Part | Expected | Limit |
|---|---|---|
| Open, preflight, gate | about 7–10 min (as in S1–S3) | none of its own |
| T6 | about 20–25 min (S2's row: 20 min, its step 19 min) | ceiling 47 min (the packet's) |
| Classification | about 2 min | — |
| Stop and close | about 1.5 min | none of its own |

At 47 min the row receives TERM to its process group (never KILL, never QEMU) and is exported as interrupted; the
Docker events recorder of r04 can then be left running (found by the preparation's bench): the runbook's own cleanup of
it, recorded, precedes the close. Host: a keepalive with at least 6 h left, Windows kept awake, no other load.

## 5. Stop conditions

Each halts the session: nothing is repeated; the attempt is classified and exported as it stands; the session is closed
in a controlled way whenever the guest answers, and handed back to Rui. If the guest does not answer while QEMU runs,
the state is preserved, nothing is signalled and Rui decides in the window. QEMU is never killed or re-launched without
Rui's decision.

1. At open, preflight or gate: the clone not at `1fd9792` or not clean; a tool or system identity of section 2 that
   differs; the root file system not at `6fce1688…`; r04 not `planned` or not fresh; a frozen driver ending non-zero
   (`collector-duration` included); the environment copy failing. Test 6 is then not run.
2. Instrumentation: a step status 97 or 74; an export, transcript or snapshot failure; a usage exit 2 of `delta` or
   `acceptance`.
3. A failed gate: not six healthy services within 900 s; a recorder or collector unit active; an OOM kill; an
   unexpected restart or replacement.
4. The row past its ceiling; no row starts after the 3 h start cut-off.
5. Guest, tunnel, WSL or keepalive lost.
6. Any restoration: nothing on the guest is started, restarted or recreated by hand (as in S3; a controller left
   stopped by the test's restart is a failure the record shows, and the close's stop covers it).

Not done without Rui's decision: any fix, repeat, new identifier, or change to code, configuration, helpers,
thresholds or `DRAIN_*`.

## 6. Evidence and classification

Everything under `output_test/runs/<UTC date>/`: the session, preflight and gate packages, the row's package (its
console, the sealed run directory `controller_restart-r04`, the write-once twin siblings, `commands.jsonl`,
`SUMMARY.md`, `SHA256SUMS`) and the operator records; every attempt exported and verified, secret sweep before each
seal; a result note in `output_test/decisions/`.

The packet's T6 row, read under the amended criterion (no class added):

| Class | Test 6, run `controller_restart-r04` |
|---|---|
| Pass | `T6=ok` (harness exit 0, run sealed, drain `quiet`); the controller restarted once mid-run (the restart record at +300 s with exit 0, the capture's `die` and `start`, the gate's `EXPECTED-RESTART` for `egw-controller-1`); recovery within 120 s (`restart_metrics_endpoint_recovery_s` of `per_run.csv`, the packet's endpoint recovery); every `delta` line OK; `acceptance --exactly-once` exit 0 (`double_accepted` 0) |
| Valid failure of the system | `T6=gaveup`; `--exactly-once` exit 4 (a valid message absent, duplicate-only or accepted twice); recovery above 120 s; a `delta` MISMATCH; `double_accepted` above 0 |
| Invalid instrumentation | harness exit 1 with an instrumentation reason (the configuration identity and a rejected `resources.csv` included); `delta` 1 or 2; `--exactly-once` exit 1 or 2; no endpoint recovery value (`analyze`: insufficient instrumentation) |
| Inconclusive | `harness_cmd` 3; a row interrupted at the ceiling (exported `interrupted`, not demonstrated) |
| Not started | r04 refused (`F6`), harness exit 2, a precondition |

A `delta` MISMATCH or a duplicate-only identity is a valid failure with the cause not established: the result note
reports no defect of the system for it (packet sections 5 and 6). Reported beside the result, deciding nothing: `lost` and `late_confirmations` against the marker plus 60 s (a sizing
finding), the functional recovery (`restart_functional_recovery_s`), `resources_transition_rows`,
`resources_proved_down`, the N1 report.

## 7. Preparation (sealed; no guest)

Package `output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation` (its seal is given in the hand-off).

- **Host, 2026-10-05 20:19Z, outcome `prepared`:** the clone moved from `8e49261` (clean) to `1fd9792` (tree `14f89c4`,
  clean, branches unchanged); every identity of section 2 equal (`repo_identity`: drivers `2c209b09…`, export tool
  `544c9b3d…`); helpers regenerated, `e5eba37e…` (545 lines), predecessor kept; r04 unused on the host and on the
  guest's root file system (read offline); S2's attempt01 the only earlier t6 attempt; root file system `6fce1688…`
  before and after; data disk 34,359,738,368 B, ext4 `clean`; the plan `c195bd3f…` → `61d55940…` (96 entries, the first
  95 byte-identical, r04 `planned` with seed 1715385812). No image was rebuilt.
- **Step file:** `t6.sh` (`ec8ac010…`) equals runbook lines 1421–1428 byte for byte once the `host$ ` prompt is
  removed; checked against the moved clone.
- **Operator script** `g3_battery.sh` (`7a63b361…`): S3's script set to S4 (label, `t6` only, the new identities, the
  collector compared at open and before the row, S3's exception removed).
- **Checks:** one bounded check by two readers (one material point: which recovery value decides, now stated in
  section 6; nine minor or wording points, applied); a bench of the final script on the real `t6.sh` with the real
  helper functions, stand-ins for the harness, `analyze`, `itest_reconcile` (`delta`, `--exactly-once`), the four
  session drivers and the guest: 25 scenarios PASS, the script unchanged (not exercised: the ceiling and the cut-off in
  real time, statuses 97 and 74, an export failure); one adversarial reading of the bench (one material point, the
  ceiling path of section 4, now in the procedure).
- **Not yet verified, and verifiable only on the guest:** the items of section 8 and `term` on the real harness.

## 8. Boundaries

- Not in S4: tests 1–5 and 7–9; any build or image load; any change to the candidate beyond the collector the merged
  preflight installs; any criterion or threshold.
- What S4 writes on the guest: the stack's start; the collector's install; r04's 6,720 messages, their event directory
  and the twins of its devices; the controller's restart.
- Unverified on the guest (Appendix B items 23 and 24): the transition rule on a live restart, the collector's uptime
  bounds, the exactly-once line on a real post-drain copy, `delta`'s N1 options (`--restart-evidence`) on a real run
  directory, `fetch_started_at.sh`, the Docker events of a compose restart on the guest's engine.
- After S4, whatever its result, G3 stays `Not decided`; closing G3 is a separate decision.

## 9. Decision asked

One sentence suffices, for example: *"Autorizo uma única sessão S4 com o teste 6 (`controller_restart-r04`), nos termos
do pedido de 2026-10-05; sem repetições, sem alterações ao candidato além do novo coletor instalado pelo preflight e sem
aceitação automática do G3."*

Three points are choices of this request; say so if any should be otherwise: (1) "recovery within 120 s" read on
`restart_metrics_endpoint_recovery_s`, the packet's endpoint recovery, with the functional recovery reported beside it
(section 6); (2) after a TERM at the ceiling, the runbook's own recorder cleanup, recorded, before the close
(section 4); (3) `--exactly-once` exit 1 (inputs not read) classed as invalid instrumentation, as test 6's row treats
`delta` 1, where the packet's test 3 row classed `acceptance` 1 as inconclusive (section 6).
