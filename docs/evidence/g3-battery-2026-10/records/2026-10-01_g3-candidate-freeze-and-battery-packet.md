# G3 candidate freeze and qualifying battery — decision packet (2026-10-01)

**For:** Rui Duarte. **From:** the Senior Software Developer, after the PM's clearance of PR #53 (register entry
"2026-10-01 20:34 WEST — PR53 bounded corrections cleared for merge") and Rui's merge at `80e833f`.

**Revision 2 (2026-10-01).** Revision 1 is kept beside this file as `.r1.md`. This revision adds the Project
Manager's four operational conditions (register entry "2026-10-01 22:50 WEST — freeze/battery packet favourable with
operational conditions"): official purpose for the qualifying rows (§3); the current labelled environment capture as
the harness input (§1, §3); the 3 h limit as a cutoff for starting a row, on one host `/proc/uptime` baseline (§4);
and a recorded `compose stop -t 130` before the unchanged close driver (§4). Following the same entry, the §5 T7 row
now says that "not demonstrated" is not a pass, the approval text carries the PM's windows (S1 after a verified
preparation; S2 only if S1 ends without a halt condition; a halt cancels further progress), and the choices table gains
the session-limit row. The candidate is the same.

## Summary for the decision

- **Candidate (§1).** Tools at `80e833f` (tree `dad725d`, the tree the PM cleared); helper heredoc `e5eba37e…`;
  the retained controller image `sha256:9a293fe1…` built from `489bc9e` (controller, simulator and deployment
  sources unchanged since then, so no rebuild); the five external images pinned by digest; CONTRACTS v1.2
  `247e3b02…`; the 2026-09-18 guest image (root file system `c49500a9…`, re-hashed today, unchanged since the
  2026-09-30 close). Ditto's 768 MiB limit is a bounded risk, not shown stable.
- **Battery (§2).** The nine families in runbook order, twelve rows, in two sessions: S1 = T1–T5 (about 1 h 40 min
  to 2 h), S2 = T6–T9 (about 1 h 25 min to 2 h 05 min). Fresh ids for every row (`-q1`); the harness rows use the
  unused plan entries `nominal-r02` (T1) and `controller_restart-r03` (T6).
- **Evidence (§3).** One `output_test` attempt per row (`--purpose official`, labelled G3 qualification), with
  console, simulator files, metrics, SUT logs and events, results and `SHA256SUMS`; session, preflight and operator
  records beside them (`engineering`, linked to the battery). The harness rows read the preflight's current
  environment capture (ARM64 emulated in QEMU/TCG), the previous input kept.
- **Limits (§4).** No row STARTS after 3 h of session time on one host `/proc/uptime` baseline; a row already running
  keeps its ceiling, so with T8 a session can reach about 5 h 15 min plus the close (the 1 h 25 min – 2 h 05 min
  figure is an estimate); a halt list; the runbook's own restorations only; a recorded `compose stop -t 130` before
  the unchanged close driver; QEMU never killed; no code fix, no repeat, no new id during the battery; every outcome
  exported.
- **Outcomes (§5).** Pass, valid SUT failure, invalid instrumentation, inconclusive or not demonstrated, not
  started — never a pass on insufficient evidence. The two accepted limits (T4 exit 5; N1 unexplained) stay (§6).
- **Blockers (§6).** No P0 or safety blocker found. The host preparation of §7 resolves the known preconditions (the
  execution clone and helper file are at `676d4bd`).
- **Decisions asked:** Q1 (freeze) and Q2 (lift the pause for this battery), with the execution choices below.

## Status and the two questions

**This is a request; it authorises nothing by itself.** G3 stays paused and `Not decided`; the merge alone neither
freezes the candidate nor lifts the pause. Nothing here ran on the guest: the host reads were read-only, with one
offline listing of the guest root file system (`debugfs -c`, no QEMU running). **Read at run time** marks a value the
drivers check when the session runs. The procedures stay in the [runbook][rb] (§6.1 helpers, [§7][s7] the nine
tests, [§8][s8] pilot and load rules), the [decision page][dp] and the [readiness map][rm].

- **Q1 — Freeze the candidate** of §1 for the G3 qualifying battery: the current images, no rebuild, and no change to
  code, configuration or helpers until the battery ends.
- **Q2 — Lift the G3 pause for this battery only:** the host preparation of §7, then two guest sessions running §2
  under §3–§5, on dates Rui sets. Q2 needs Q1.

C3, r03 and the compatibility session are not repeated. **Execution choices included in Q2** (Rui may change any):

| Choice | Recommended | Alternative |
|---|---|---|
| `DRAIN_QUIET_S` | 130 s (helper default; the runbook as written) | 490 s: about +2 h 55 min over the 29 drains. S1 then passes the 3 h limit (§4): a third session or a longer limit |
| Sessions | S1 = T1–T5, S2 = T6–T9, same candidate | One session of 3–4 h, with a limit above 3 h |
| Session limit | 3 h cutoff for STARTING a row, on the host `/proc/uptime` baseline; a row keeps its ceiling (up to about 5 h 15 min plus the close) | Absolute 3 h occupation: a row starts only if its ceiling and the close fit before 3 h; unrun rows go to a later decision |
| Ids | Runbook literal plus `-q1`; plan ids unchanged | — |
| `--purpose` | `official` for the 12 qualifying row attempts, labelled "G3 qualification" (metadata only: it accepts no gate and is not an official G4/G5 campaign); `engineering` for the session, preflight, health, preparation and operator records, each linked to the battery | — |
| Prose-only steps | Run and recorded: T1's `analyze` read (line 1320); T9's three exposure checks, read-only; T8's re-launch through the session's `session_open.sh` | Stated as not executed; T9 then cannot pass its Expected list |
| Evidence-only reads | Guest state around each row; T8's previous-boot journal and kernel OOM grep | Omitted |
| T7 with no `failed` record and no visible effect of the outage | Not demonstrated (the fault's effect is not shown) | Valid SUT failure (the Expected `failed` records are missing) |
| WSL keepalive | A dedicated `exec sleep` client, checked before each row; the `stop-keepalive` sentinel untouched | Delete the sentinel (a host write) |

## 1. Candidate

| Part | Identity | Checked by |
|---|---|---|
| Tooling | `80e833f44f647fe9cd8f5e99d3abf3c444de95aa` (2026-10-01 20:35 +01:00), the merge of `617fb40` (dev, PR #52) and `a20be8f957b23b75aa086a6740829dcb9741344b`, the head the PM cleared. Its tree `dad725d0bebc25c91712af2aa2705d5eeb92044f` is `a20be8f`'s: the frozen tree is exactly the cleared one | `repo_identity` in every attempt (`repo_dirty_lines=0`) |
| Clean checkout | WSL `~/egw-exec/repo` (now `676d4bd`, clean; moved in §7) and `~/egw-exec/venv` (Python 3.12.3; `pyproject.toml` and both locks unchanged since `676d4bd`). Not the Windows worktree (path-length artefacts) | Session open: HEAD, porcelain count |
| Drivers | `drivers_sha256` `4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5` (38 files; new: `fetch_started_at.sh` `9c6dc824c885ce6d2edacdfb5fe4a4db4a96b6e0b6454f93300ee1b007421827`); `local_export.py` `544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b` | **Read at run time** |
| Runbook | `docs/setup/qemu_integrated_gateway.md` `c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae` (1,614 lines) | §7 extraction |
| Helpers | §6.1 heredoc (lines 610–1154) `e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb`, 545 lines. The host file (`39403ead5a816e826e337a9c7768d5966a43cad724402398b3a13dcc47c61d17`, 544 lines, `676d4bd`; one comment differs) is regenerated in §7. `tunnel.sh` `38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1`, `ca.crt` `556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff` unchanged | `proof_helpers_check.py`; session open |
| Controller image | `egw-controller:0.1.0` `sha256:9a293fe13b1a020560d43fee328632a9ef8d91dec830899f18d3e2d964aa5f46`, arm64, built 2026-09-26T17:30:30Z from `489bc9e` (clean). Record `79e7d2105be035911e9fe596f609a77775b578f0578cab1bde77f0d610aa2022`; archive `9d347be45e886da09bb30d1029f30f7c5a70fd15ff75343856f0b3368bce841d` (53,423,616 B, re-hashed today). Already on the guest's data disk: no build, no load | Preflight interlock against the guest's copy of the record, **read at run time**; session open hashes the archive |
| No rebuild | Controller, simulator, schemas, Dockerfile, locks and `src/deployment` are byte-identical from `489bc9e` to `80e833f`; only `src/egw_experiments` differs, which the image's command (`egw_controller.app`) never imports. No need for a rebuild is shown; a rebuild would be a new image identity to verify | — |
| Other images | `src/deployment/images.lock.env` `8a9a05df7c9ca2eeb310e8e7702f16f854fb91771fb089a9a2109d638ae4a648` holds the five full digests: mosquitto 2.0.22 `212f89e1…`, mongo 7.0.39 `35a5926f…`, ditto-policies, -things and -gateway 3.9.4 `652f75b9…`, `a1cc8a12…`, `fc9102b5…` | Interlock (pinned by digest); `gate_health.sh` records the running digests |
| Deployment | `src/deployment` (21 files), git tree `e056d389f7dd640c142bf714bb8ceb389ec460c2` at `489bc9e`, `676d4bd` and `80e833f`; `compose.yaml` `1a32f6c2bd9e24eee075ef569828aa41ad6a7a7b260d4436e588dc9ca74d5982`, `mosquitto.conf` `ea37827cccd94ef3870c62b77ffbe0b34261f7f213f243212f03121219d99615`. 2026-09-30: 20 deployed files equal to the clone | `deployed_vs_clone.py`, **read at run time**. T6's `config_identity` only records (the harness checks the form); the operator compares: broker configuration `ea37827c…`, W 4,999, Q 1,000, byte limits 0, expiry 1 h, `sys_interval` 10, not reloaded, grace 130 s, image `9a293fe1…`/`489bc9e`, paho 2.1.0, `a3_choice` a. A difference is halt 6 |
| Contracts v1.2 | `src/CONTRACTS.md` `247e3b02a1ffc8e30da3f9df701db5f851f018505ecb9f907b54562b9cf095c9` ("v1.2, 2026-09-24", ADR 0011) and `src/schemas` (git tree `1d5284cf28bbabc5c7ea554d5a5366faec5fcf95`), identical since `489bc9e` | Q1, recorded in LOG, is the v1.2 freeze record. `docs/g0/backlog.md`:255 still says v1.1 (a separate correction) |
| Guest OS | The 2026-09-18 integrated image: kernel `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037`, rootfs archive `d4569c0e845f3a7e36d292953de64dde76b6e81b7482206d0f0f385bcf805fc7`, `qemuboot.conf` `7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4`, manifest `9f554f3bdd4bbb73c196afba4050bcded7a0ceaba41278cbb0622f6f1adf8940`; QEMU 8.2.7 `5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061`. The launcher and kas checkout `~/yocto/egw` (not a build record of the image) is at `489bc9e`, clean: `run-qemu-integrated.sh` `67da61d77a2548122afc34338493165290f6d1ac1dbc2ebccfd6d800dd0438e1`, `egw-qemuarm64-integrated.yml` `48eb8e9e493d9ac3ce48e82795ac2b200145212b15e0c60f84a6b7d6deeebb83`, `.lock.yml` `63c09f156f806b1c5bc7dcd7a782f2deee9424e5323eb4be4913b962d95ef3bf`, identical at `80e833f`; T8 re-launches with it. The booted `.ext4` is `c49500a9a7751a8753b8af44e2d76bd1d2d0e694b29524142cabf896f85e7260` since the 2026-09-30 close | Session open hashes before the boot; the close re-hashes the `.ext4`. Expected before S1: `c49500a9…`; before S2: S1's post-close value |
| Data disk | `egw-data.img`, 34,359,738,368 B (`/var/lib/docker`: images, MongoDB volume). **Not hashed.** ext4 clean, mount count 17, last write 2026-09-30 16:09:15 +01:00 | ext4 header listed before each boot and after each close |
| Harness inputs | Pilot plan `~/egw-tcg/pilot/campaign_plan.json` `5d902a429b9fd4e25f2c4586341f94be2853104fe12a76b88852a1ed30203e23`, master seed 42. `~/egw-tcg/sut_environment.json`, the harness's `--sut-env-from` input (runbook line 1045): today `a870c431af5fb533af93a438769d39241fdce52101f710bd38abee31323b010f` with empty emulation labels; **not used as is**. After each session's preflight and before its qualifying rows, that file is kept beside itself under its sha256 and replaced by the preflight's verified capture (`environment/sut_environment.json` of the preflight package: `capture-sut-environment.sh` on the guest with the labels QEMU 8.2.7 TCG on WSL2, `ARM64 EMULATED`, shared x86-64 host; `preflight.sh` lines 255–257, runbook 5.8). The new hash and its source package are recorded; no native-performance claim follows | Plan copied before and after each harness run; the environment copy recorded in the session's operator records, **read at run time** |
| Ditto memory | The three Ditto services are each **limited to** 768 MiB (`MaxRAMPercentage=50`, `ExitOnOutOfMemoryError`), raised after the 2026-09-18 OOM of `ditto-things` at 512 MiB; `mongodb` 512, `mosquitto` 128, controller 256 MiB. **Bounded, not shown stable:** one idle reading (2026-09-30, `ditto-things` 498 MiB, 64.9 %), no OOM, no restart | Guest state and OOM lines around every row; T7b and T8 exercise it |

## 2. Runs

Fresh ids for every run are the PM's order; the helpers would also refuse every 2026-09-18 literal that left host
artefacts (all but `itest-dup-02` and `itest-ditto-fault-01`, never run, and T9's three). Only the tokens below
change. Each was absent on 2026-10-01 from the host's `itest`, `itest-replay`, `pilot/results/raw`, `output_test` and
the guest's event directories (§7 checks again), except T9's ACL id, fresh by construction (stamp in the console).

| # | S | Slug | Row | Run id | Workload | Key expected checks | Est. min |
|---|---|---|---|---|---|---|---|
| 1 | S1 | `t1-smokes` | T1 smokes ×3, one attempt | `itest-smoke-01-q1`, `-02-q1`, `-03-q1` | Seed 42, `smoke`, 30 s, 336 each | Each **timed** (decision 3): `lost` 0, `late` 0; `delivered_unique = sent_valid`; three device types; `delta` OK | 19 |
| 2 | S1 | `t1-harness` | T1 harness | **Plan entry `nominal-r02`** (seed 246295039; decision 1b). No fallback: `T1H=stop` halts | 120 s warm-up + 600 s `nominal`, 6,720 | Manifest `valid`, sealed; `collector.problems` empty; `missing=none`; rows > 0 per service; ingest rule (30 instants, 90 %, 5 s). Delivery reported only | 16–22 |
| 3 | S1 | `t2` | T2 | `itest-3dev-01-q1` | Seed 7, `smoke`, 60 s, 672 | **Timed** `lost` 0, `late` 0; three twins, `policyId = thingId`, no missing property, `egw_id`, `schema_version`; `delta` OK | 7–17 |
| 4 | S1 | `t3` | T3 | `itest-invalid-01-q1` | Seed 42, `invalid-payload`, 120 s, 1,344 (67 invalid) | Not timed. `acceptance` 0 on the post-drain copy (invalid accepted 0, valid rejected 0, rejected = intended); `delta` OK; rejections in the bounded controller log | 9 |
| 5 | S1 | `t4-replay` | T4 replay | `itest-dup-01-q1` (replay directory `itest-replay/itest-dup-01-q1`) | Seed 42, `smoke`, 60 s, 672, then replayed once | `replay-check` 0 (decision 4, PR #53 F1); one process; `delivered_unique`, `lost`, `late`, `double_accepted` unchanged; twins identical | 13 |
| 6 | S1 | `t4-reset` | T4 sequence reset | `itest-dup-02-q1` | Seed 42, `smoke`, 60 s, 672 | **Timed** `lost` 0, `late` 0; `delta` OK | 7 |
| 7 | S1 | `t5` | T5 | `itest-dropout-01-q1` | Seed 42, `dropout-reconnect`, 180 s, 2,016; 3 windows ≈ 14.6 s | **Timed** `lost` 0, `late` 0; ≈ 3 disconnects, `buffered_dropout` > 0; bounded broker log with N+1 connections, N disconnections (wording UNVERIFIED); `double_accepted` 0; `delta` OK | 10–11 |
| 8 | S2 | `t6` | T6 | **Plan entry `controller_restart-r03`** (seed 2189910495), the last one left | 600 s `nominal`, 6,720; controller restart at +300 s | `T6=ok` (harness 0, sealed, drain quiet); capture with `die` and `start`; **C12 `lost` 0, `late` 0**; endpoint recovery ≤ 120 s; `delta` OK post-drain; 1a printed; the N1 report only reports | 18–32 |
| 9 | S2 | `t7-mongo` | T7 MongoDB | `itest-mongo-fault-01-q1` | Seed 42, `nominal`, 300 s, ≈ 3,360; `mongodb` stopped 45 s at +90 s | Not timed. `T7=0`; `failed` with `attempts` 3 and a 5xx/timeout error (or 1 with a 4xx); `accepted` resumes; `delta` OK; `lost` reported | 12–16 |
| 10 | S2 | `t7-ditto` | T7 Ditto | `itest-ditto-fault-01-q1` | The same, on `ditto-things` | As row 9; `ditto-things` watched at 768 MiB | 16–25 |
| 11 | S2 | `t8` | T8 | Prefix `itest-reboot-q1` (all 8 literals, lines 1486 and 1491); smoke `itest-post-reboot-01-q1` | Reboot with the stack up; then `smoke`, 30 s, 336 | `REBOOT SHOWN`; six containers back unaided; previous boot listed; `/var/lib/docker` on `/dev/vdb`; twins identical; old event directories intact; new `started_at`; smoke **timed** `lost` 0, `late` 0, `delta` OK | 15–25 |
| 12 | S2 | `t9` | T9 | (a) `itest-tls-wrongca-q1`, (b) `itest-auth-wrongpw-q1`, (c) `itest-notls-q1`; (d)+(e) `itest-acl-<UTC stamp>` | 10 s probes; the ACL probe ≈ 100 s | Not timed. (a) `exit=1`, certificate-verify error; (b), (c) `exit=1` after the 15 s timeout, with "not authorised" (b) or a TLS/socket error (c) in the bounded `<id>.sut/broker.log`; (d) probe 0, `verdict=PASS`, `changed fields: []`; (e) anonymous refused, rc 5; exposure checks | 6–8 |

The order is T1 to T9. A family passes only when all its rows pass (T1: smokes and harness; T4: replay and reset; T7:
both faults).

## 3. Execution and evidence

**Sequence.** The unchanged drivers ([`tools/session/`][drivers]): `guest_session_open.sh` → `preflight.sh` → the
environment copy of §1 (recorded) → `gate_health.sh` → the rows → the recorded `compose stop -t 130` of §4 →
`guest_session_close.sh`.

**Rows.** Each row is one attempt running its runbook lines, extracted verbatim from the `80e833f` blob with only the
§2 ids changed, through `hx` (the clean clone, its venv and the helpers; stdin closed; `set -v`, never `set -x`, as the
simulator password is on its argv; no `set -e`). Within a test, the runbook's carriers decide which lines run after a
`STOP:`; T9, whose lines have none, runs as four steps ((a), (b), (c), (d)+(e)), each only if the one before printed
no `STOP:` (runbook line 15). Command forms, gate commands and restorations are in the operator procedure (§7).

**Gate.** Guest state (container ids, start instants, restarts, `OOMKilled`, memory-cgroup OOM lines) before and after
each row; then the six containers healthy within 900 s, restarted only where the row restarts them (no comparison
across T8's reboot), no `egw-events-*` or `egw-resources-*` unit active, the tunnel up. The next row starts only when
this one is classified (§5) and its gate passed. The operator classifies from the row's console and files alone; no
evaluator code is added, and an exit status is never a verdict.

**Evidence** (`output_test/runs/<UTC date>/`; a session crossing midnight UTC uses two date folders):

| Record | Path and contents |
|---|---|
| Each row | `<UTC stamp>_g3-qualification-<slug>_attempt01/` (`--purpose official`, scenario "G3 qualification <slug>", from which `local_export` derives the directory name): `console/` (transcript, gate, extra steps); `simulator/<id>/` (every `<id>.*` sibling: transcript, marker, metrics, twins, reconcile and pre-replay or post-drain copies, `fault`/`ready`, and `.sut/` with the bounded broker and controller logs and the Docker events capture); `raw/<plan entry>/` for rows 2 and 8 (the capsule, with its own `SHA256SUMS` when valid); `other/` (T4's replay directory, T8's prefix files, T9's ACL evidence, plan and `processed/` snapshots); `environment/` (extracted text, substitution map, hashes, ids-only diff); `commands.jsonl`; `SUMMARY.md`; `SHA256SUMS` |
| Session, preflight, health | `…_guest-session_attempt08`/`09`, `…_live-preflight_attempt09`/`10`, `…_g2-gate-preconditions_attempt05`/`06` (the next numbers today; allocated at run time) |
| Preparation and operator records | `HIST_<date>-g3-battery-host-preparation/`; `HIST_<date>-g3-battery-operator-records/` (session plan, steps script, driver consoles, classification notes) |
| Result note | `output_test/decisions/<date>_g3-battery-s<N>-results.md`: every row and its class; no G3 claim |

Files holding an `.env` secret (a sanitised copy is kept) and T9's `/tmp/wrong.key` are not exported; `local_export
set run_id` is never used.

## 4. Limits, stops and close

**Occupation** (planning figures from earlier records and arithmetic, not measured on `80e833f`): S1 (rows 1–7)
≈ 1 h 40 min – 2 h; S2 (rows 8–12) ≈ 1 h 25 min – 2 h 05 min, each with ≈ 15–17 min of gates and session overhead.
Row ceilings (the helpers' own limits, minutes): T1 smokes 105, harness 35, T2 36, T3 37, T4 replay 67, reset 35, T5
38, T6 47, each T7 row 41, T8 135, T9 25. T5, T6 and T7 are the likeliest to run long under TCG.

**Limits.** The 3 h limit is a cutoff for STARTING a row, not a total duration. It is read on one host WSL
`/proc/uptime` baseline taken at the session open and kept through the whole session, T8's guest reboot included
(the host clock is not restarted by the guest; the WSL wall clock steps back, so it is not used). A row begun before
the cutoff keeps its stated ceiling and then closes safely: with T8's 135 min ceiling a row begun just before 3 h
can end at about 5 h 15 min, plus the close, so the §4 occupation figures are estimates, not bounds. Unrun rows need
a later decision, never a forced power-off to meet the clock. A row past its ceiling gets TERM to its process group,
never KILL: the traps mark the attempt `interrupted` and export it, and T7's trap restores the service. Host: keepalive checked before every row, keep-awake throughout, no other load,
`MSYS_NO_PATHCONV=1`, LF-only files.

**Halt** (controlled close, then hand back to Rui) on:
1. A row not started (a precondition, `T1H` or `F6` refused; harness exit 2).
2. Invalid instrumentation of the shared chain: step status 97 or 74; an export, transcript, marker, fetch or
   snapshot failure; a usage exit 2 of `acceptance`, `replay-check` or `delta`.
3. A failed gate: a service not healthy within 900 s, an OOM kill or unexpected restart, a unit still active after
   three cleanups.
4. Any restoration (T7's manual `start`, a controller left stopped by T6): restore, record, halt.
5. T8: QEMU not exited within 10 min, a re-launch STOP, or no `REBOOT SHOWN` (T9 is then not run).
6. Guest, tunnel or WSL lost; an identity differing from §1, or at S2's open or preflight from S1 (S2 not started);
   a T6 configuration value differing from §1 (T6 invalid).
7. A row past its ceiling, or the session limit.

A row never reached after a halt, and a smoke left unrun when row 1's loop breaks, run only on Rui's explicit go,
recorded in the halt or result note; a row classed Not started is not attempted again under this approval.

**Safe close.** Only the runbook's own restorations are used, and QEMU is never killed without Rui's decision (the
data disk is at stake). Fetches and cleanups run before any close, as the guest's `/tmp` is lost at power-off. Then:
no row or poller running, no recorder or collector unit active, the open attempt finished and exported as it stands;
**a recorded stop with the controller's 130 s allowance**, a step of the session attempt (`gx "$S" stack-stop-130
… $DC stop -t 130`, the close driver's own compose form), with its exit status and `docker ps -a` recorded (the close driver's own `compose stop -t 60` is
then idempotent; the frozen code is not edited; 130 s is not proof of clean drainage or stability, and a failed stop
is a halt and hand-back, never permission to force QEMU off); `guest_session_close.sh` on the boot named in
`.current_run` (tunnel down, `compose stop -t 60`, OOM state, power-off, no QEMU left, rootfs hashed, export); records
sealed, keepalive and keep-awake released.

**No fix, no repeat.** Without Rui's decision: no change to code, configuration, helpers, thresholds or `DRAIN_*`; no
`finish` repeat or `ACCEPT_UNACCOUNTED=1`; no new id for a refused row; no T9 probe repeat with a new tag; no later
broker read for T5 after its STOP. The runbook's "resolve the cause and repeat that line" (line 15) is not applied:
each STOP is recorded and classified. Every attempt is exported, including those not started or interrupted; nothing
is deleted.

## 5. Classification

- **Pass:** the procedure completed and every Expected item holds, read from the printed values and saved files
  (`PROCEDURE COMPLETE` alone is no verdict).
- **Valid SUT failure:** a complete evidence chain and an Expected item missed; G3 is not met on that family. A timed
  miss is also a sizing finding, never a pass. A `delta` MISMATCH (the runbook allows "a false MISMATCH, never a false
  OK") and a `duplicate_only_unexplained` identity are failures **with the cause not established**: `lost` is
  unchanged, and the result note reports no SUT defect for them.
- **Invalid instrumentation:** the chain was broken by the tooling or the host, not by the SUT.
- **Inconclusive / not demonstrated:** no verdict either way; never a pass.
- **Not started:** a precondition refused; nothing published.

`local_export finish` validity/outcome: pass `valid`/`pass`; failure `valid`/`fail`; invalid `invalid`/`unknown`;
inconclusive `valid`/`inconclusive` (`unknown` validity when unreadable); not started `not-applicable`/`not-run`; a
TERM leaves `interrupted`.

| Row | Valid SUT failure | Invalid instrumentation | Inconclusive / not demonstrated |
|---|---|---|---|
| T1 smokes | `lost` or `late` > 0 (`check` still exits 0); unique ≠ sent; a device type missing; MISMATCH | Transcript or marker failure (`check` 3); a host error in the simulator transcript; `check` warnings | `finish` stopped before its `after` pair |
| T1 harness | A SUT event behind an invalid reason, reported beside it | Exit 1 with a hook, fetch, companion or ingest reason | `harness_cmd` 3 |
| T2 | `lost` or `late` > 0; a twin property, `policyId` or attribute wrong | `RT=twin`; an unreadable twin file | `finish` STOP |
| T3 | `acceptance` 4 (even with `RT ≠ 0`); MISMATCH | `acceptance` 2; `sut_log` failed | `C3=stop`; `acceptance` 1 |
| T4 | `replay-check` 4; twins DIFFERENT; two processes; a CHANGED line; unique ≠ total; reset: `lost` or `late` > 0, MISMATCH | Replay simulator ≠ 0; `replay-check` 2; a snapshot or fetch failure | **`replay-check` 5 (accepted limit)**; exit 1; a drain that gave up |
| T5 | `lost` or `late` > 0; `double_accepted` > 0; MISMATCH | Fault not delivered (disconnects not ≈ 3, nothing buffered); broker log not read | Not N+1 and N in a log that was read (wording UNVERIFIED); a drain that gave up |
| T6 | `T6=gaveup`; C12 `lost` or `late` > 0, a duplicate-only identity included (cause not established); recovery > 120 s; MISMATCH; `double_accepted` > 0 | `HR=1` with an instrumentation reason (configuration identity included); `resources.csv` rejected; `delta` 1 or 2 | `HR=3` |
| T7 | Service not back (state read); `failed` of another shape; MISMATCH with complete instrumentation; records with no outcome | State `unknown`; interruption not shown or no simulator at +90 s; `RK ≠ 0`; `T7=incomplete:`; transcript or marker failure | A drain that gave up; no `failed` and no visible effect (choice above): not demonstrated, its Expected item unsatisfied, T7 NOT passed |
| T8 | Stack not ready in 3,600 s; a container down; `/var/lib/docker` not on `/dev/vdb`; DIFFERENT; old directories missing; smoke `lost` or `late` > 0, MISMATCH | Boot id unreadable; tunnel not reopened; snapshot failure; another data disk | Reboot not shown; QEMU never exited (a hang is reported as a SUT observation) |
| T9 | (a) exit 0; (b) or (c) a session accepted; (d) probe 1, or counters or `started_at` changed; (e) anonymous accepted | `sut_log` STOP; probe 2 or 255; an invalid `/metrics` snapshot; a counter change only with an outside publisher or operator action shown | (a) an error other than certificate verification; (b) or (c) no refusal line in a log that was read; probe 3 |

## 6. Known limits and blockers

**The two accepted limits** do not block the start. Neither is relaxed; each prevents declaring success on
insufficient evidence.
1. **T4 not demonstrated** is `replay-check` exit 5 only: after an `after` reading that is not quiet, every replayed
   identity with a line; after k ≥ 1 reconnections between the `after` and `replay` readings, every identity with 1
   to k added duplicates. With 672 identities, such a reconnection leaves T4 unpassed either way: if every identity
   has more than k, the extra duplicates exceed the budget and T4 fails (exit 4), which is never this limit.
2. **N1 unexplained:** a `duplicate_only_unexplained` identity, named or not, stays in `lost` and its device line a
   MISMATCH, so T6 fails on it with the cause not established; the report explains, never counts.

**P0 or safety blocker: none found** in the nine families' texts or the identities above. Preconditions §7 resolves
(no SUT defect, no code change): the execution clone lacks `80e833f` and a plain `git fetch` does not bring it (T3's
`acceptance` and T4's `replay-check` would exit 2; T1's manifest would name the wrong commit); the host helpers are
the `676d4bd` generation; `~/egw-venv` and the helpers' default `EGW_CLONE` point at `489bc9e` (`hx` avoids both); a
partial substitution of T8's prefix would print a false `REBOOT SHOWN` against the old boot id, so all eight literals
change together; the `stop-keepalive` sentinel defeats the README's keepalive loop.

**First exercised by the battery** (not demanded beforehand): the families' lines at `80e833f` on the guest, T6's
hook path with `fetch_started_at.sh`, the Ditto stop, a second boot in one session, non-interactive signal handling.

**Open risks:** Ditto memory (bounded, not shown stable); timed delivery never met on a valid run (`nominal-r01`
3,794 of 6,720 in time; T5 326 of 2,016 late on 2026-09-18), so timed rows may fail validly; T6's drain gives up below
about 4.7 msg/s sustained; W and Q checked against the backlog by arithmetic only; T8's held session not assessed (ADR
0011, N3); a graceful stop above about 124 s gets the resources file rejected (1a's S − D).

**On record, not blocking:** the image's `egw_experiments` from `489bc9e`; the unhashed data disk; the guest's
controller record checked by field; the backlog's v1.1; the empty labels in `sut_environment.json`; the stale
`compose.yaml` header ("3x ditto 512M").

**G3 closure** still needs valid qualifying results meeting the adopted criteria, family by family; running the nine
procedures is not enough. Any other result leaves G3 not met on that family, any further run is a new decision, and
the [decision page][dp]'s other open items ("What still stands") remain.

## 7. Preparation (host only; no guest)

Recorded in `HIST_<date>-g3-battery-host-preparation/`:
1. **Clone:** `~/egw-exec/repo` clean, fetched (`refs/remotes/origin/dev`) and detached at `80e833f`; tree
   `dad725d0…` and 0 porcelain lines confirmed; the venv imports `n1_report`, `proved_down` and `itest_reconcile`.
2. **Helpers** regenerated with `regen_helpers.py` (it keeps `itest-helpers.sh.39403ead5a81`): `HELPERS OK`,
   `e5eba37e…`, 545 lines, `bash -n` clean; `tunnel.sh`, `ca.crt` and `drivers_sha256` as in §1.
3. **Freshness** of every §2 id on the host and, offline, on the guest root file system (`debugfs -c`, only with no
   QEMU process and no `current_session`); both plan entries still `planned`; the plan hashed and
   `pilot/results/processed/` snapshotted.
4. **Row files:** an extraction script, kept with the operator records, writes one LF-only file per row (per step for
   T9) outside the clone from the `c55a2d3b…` blob, substituting only the §2 ids with asserted counts, and records
   each file's sha256 before and after and an ids-only diff. **These hashes are not known today.**
5. **Operator procedure:** the steps script with the exact command forms, the gate commands and the restorations.
6. **Keepalive** client and keep-awake ready; the sentinel left as it is.

S1 starts only if every check matches §1. The preparation package goes to Rui before S1; he may hold S1 on it.

**The approval asked.** Does Rui (Q1) freeze the candidate of §1 for the G3 qualifying battery, and (Q2) lift the G3
pause for this battery only: §7, then S1 in the next attended window after a verified preparation, and S2 in the
following attended window provided S1 reaches its planned end without a halt condition, with the execution choices
above (the PM's four conditions included: official purpose, the current environment capture, the 3 h start cutoff
on the host baseline, and the recorded `compose stop -t 130` before the close) or his changes? A halt cancels
further progress under this packet until Rui directs otherwise. Approving creates no G3 result; G3 stays `Not
decided` until the results are judged against the adopted criteria.

[rb]: https://github.com/Ruisth/Tese_Mestrado/blob/80e833f44f647fe9cd8f5e99d3abf3c444de95aa/docs/setup/qemu_integrated_gateway.md
[s7]: https://github.com/Ruisth/Tese_Mestrado/blob/80e833f44f647fe9cd8f5e99d3abf3c444de95aa/docs/setup/qemu_integrated_gateway.md#L1255
[s8]: https://github.com/Ruisth/Tese_Mestrado/blob/80e833f44f647fe9cd8f5e99d3abf3c444de95aa/docs/setup/qemu_integrated_gateway.md#L1533
[rm]: https://github.com/Ruisth/Tese_Mestrado/blob/80e833f44f647fe9cd8f5e99d3abf3c444de95aa/docs/governance/g3-readiness-map-2026-09-29.md
[dp]: https://github.com/Ruisth/Tese_Mestrado/blob/80e833f44f647fe9cd8f5e99d3abf3c444de95aa/docs/governance/proposals/2026-09-29-g3-pending-decisions.md
[drivers]: https://github.com/Ruisth/Tese_Mestrado/tree/80e833f44f647fe9cd8f5e99d3abf3c444de95aa/tools/session
