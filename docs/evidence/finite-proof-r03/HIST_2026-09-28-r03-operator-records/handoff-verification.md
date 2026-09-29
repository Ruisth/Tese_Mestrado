# identities-outcomes

The Identities and Outcomes sections hold up against the records: no value is wrong. I found one overclaim, one misleading placement and one precision gap, all listed at the end.

Base path: `C:/Users/ruimf/Documents/Projeto Mestrado/output_test/runs/2026-09-28/`. Abbreviations used below:
- P = `20260928T210147Z_finite-proof-adr-0011_attempt03/`
- R = `P/raw/proof-adr0011-r03/`
- HP = `HIST_2026-09-28-r03-host-preparation/`
- OPS = `HIST_2026-09-28-r03-operator-records/`
- CS = `20260928T210029Z_candidate-start-check_attempt03/`
- LP = `20260928T205459Z_live-preflight_attempt07/`
- GS = `20260928T205412Z_guest-session_attempt06/`
- G2 = `20260928T210104Z_g2-gate-preconditions_attempt04/`
- AUTH = `ChatGPT/FINITE_PROOF_R03_AUTHORISATION_2026-09-27.md`

Line numbers in the section headings are hand-off lines.

**Identities (lines 7–20)**
- Clean clone `b65a06d`, tree `4034520`, merge of PR #49: SUPPORTED. HP/console.txt:10,14,15; `git log -1 b65a06d` in `Claude/` gives tree 403452085517…, "Merge pull request #49".
- Differs from `489bc9e` "only in" cli.py, controller_metrics.py, run.py and proof.sh; `src/deployment` identical: `src/deployment` identical is SUPPORTED (HP/console.txt:22-23). "Only" is an OVERCLAIM, see item 1 at the end.
- Helper `1634c35bc79d…`, `HELPERS OK`: SUPPORTED. HP/console.txt:26-33; P/console/001-helpers-check.stdout.txt:4-5.
- Image `sha256:9a293fe13b1a…` from `489bc9e`, retained: SUPPORTED. HP/console.txt:44-45; P/console/017-identity-check.stdout.txt:1.
- "Not rebuilt or reloaded": SUPPORTED only by absence. No build or load step was run (OPS/SUMMARY.md:9), and the image record says built 2026-09-26T17:30:30Z (LP/console/001-stack-start-interlock.stdout.txt:7). See item 2.
- Preflight interlock verified the image against its record: SUPPORTED. LP/console/001-stack-start-interlock.stdout.txt:2-9.
- Post-start check read label `489bc9e`, no reload, the candidate's mosquitto.conf: SUPPORTED as recorded (CS/console/001-start-state.stdout.txt:7-9; 002-start-judgement.stdout.txt:3). But "no reload" is about the broker, not the image (item 2).
- Proof identity check compared the label with `489bc9e`: SUPPORTED. The P/commands.jsonl entry 17 argv has expected `489bc9e5…`, and `controller_source_commit` is the image's revision label (runbook at b65a06d, lines 946 and 978).
- Disk baseline `91e2d7b9…`: SUPPORTED. HP/console.txt:50, checked at 20:53:17Z before the session.
- Run ID and attempt ID: SUPPORTED. R/manifest.json:333; P/SUMMARY.md:1.
- Ten frozen values: SUPPORTED. AUTH:19-28 lists ten, and they match P/analysis/proof_verdict.json:195-210.
- Master seed `20260925`, derived seed `265481284`: SUPPORTED. P/environment/proof_plan.json (`master_seed`, `runs[0].seed`); P/console/014-proof-plan.stdout.txt:1.
- Devices fresh: SUPPORTED. R/twins.before.json:7,18,29 all have `"exists": false`; P/console/025-delta.stdout.txt:1-3 shows `existed_before=False`.
- Healthy record completed 21:01:10Z: SUPPORTED. G2/console/001-services-healthy.stdout.txt:2; P/console/007-healthy-rule.stdout.txt:1.
- Earliest candidate start 20:55:13Z: SUPPORTED. CS/console/001-start-state.stdout.txt:2 (mongodb 20:55:13.582Z).
- Fast metrics retry enabled by proof.sh: SUPPORTED. `--metrics-fast-retry` is in the P/commands.jsonl entry 19 argv; R/manifest.json:230 `"enabled": true`; `git diff 489bc9e b65a06d -- tools/session/proof.sh` adds the flag.

**Outcomes (lines 24–40)**
- Every SHA256SUMS checks out: SUPPORTED. I ran `sha256sum -c` on all 7 packages; all OK, and the seal prefixes match the table.
- Export verified 121 files, including `controller_metrics.attempts.csv`: SUPPORTED. P/SUMMARY.md:27; P/export_manifest.json:562.
- SHA256SUMS has 123 entries: SUPPORTED. P/SHA256SUMS has 123 lines, the attempts file at line 80.
- `instrumentation_validity=valid`: SUPPORTED. P/SUMMARY.md:23; OPS/console/r03-proof.log:1097.
- Harness "invalid" with the inner seal withheld, as in r01 and r02: SUPPORTED. R/manifest.json:312-314,416-420 and no SHA256SUMS in R. The 2026-09-26 r01 and r02 `proof_verdict.json` files show `harness_validity` invalid, seal unsealed, form `sampling-gap-only`.
- Reason is the MAX_SAMPLE_GAP_S gap alone, `egw-controller-1`, 21:12:54–21:13:02Z (8.0 s): SUPPORTED. R/manifest.json:425; proof_verdict.json:16.
- E-12 admits it as `sampling-gap-only`: SUPPORTED. proof_verdict.json:9,11.
- Outer package sealed: SUPPORTED.
- First drain 490.22 s (595.93 → 1086.15): SUPPORTED. P/console/016-pre.stdout.txt:1.
- Post-harness drain 490.03 s (1612.67 → 2102.70): SUPPORTED. R/logs/sut/hook-drain.stdout.txt:2.
- Result `supports`, evaluator exit 0: SUPPORTED. proof_verdict.json:918; the P/commands.jsonl entry 29 has exit 0.
- Driver exit 0: SUPPORTED. OPS/console/r03-proof.log:1097-1098.
- S1–S6 hold: SUPPORTED. proof_verdict.json:440,459,472,505,626,649.
- R1–R4 not observed: SUPPORTED. proof_verdict.json:250,260,299,417.
- No stop rule reached, no inconclusive reason: SUPPORTED. proof_verdict.json:193 and 657 (both empty lists).
- 3,360 identities, 3,359 `accepted`, 1 `duplicate`: SUPPORTED. proof_verdict.json:795,798; recounted in R/events.post-drain.jsonl.
- `059c22fc…`, device `9ce5fe46…`, smart clothing, seq 621: SUPPORTED. R/events.post-drain.jsonl:698; R/sent_events.jsonl:698.
- First post-kill reading, row 158, 1177.4019 s, `mqtt_subscribed=false`, queue 0: SUPPORTED. proof_verdict.json:759,766-768; R/controller_metrics.csv:160 (file line 160 is the evaluator's 0-based row 158) reads monotonic 1177401890818, queue 0, in_progress 0, false.
- "55 ms after the last failed poll": SUPPORTED as request start to request start. R/controller_metrics.attempts.csv:454 (attempt 453, start 1275.486112) to :455 (attempt 454, start 1275.541019) is 54.9 ms. The 158 earlier OK attempts map to rows 0–157, so attempt 454 is row 158. See item 3.
- 20.3 s failure episode: SUPPORTED. attempts.csv:160 (start 1255.197603) to :454 (end 1275.490845) is 20.29 s.
- 295 failed polls, cap not reached: SUPPORTED. 295 error rows; R/manifest.json:228,231-232,238 show `cap_reached` 0, 1 episode, 295 retries, 295 poll errors.
- Duplicate received 0.209 s after that reading: SUPPORTED. 1177611049682 − 1177401890818 = 0.20916 s (events.post-drain.jsonl:698; proof_verdict.json:662).
- Restart-class N1 case, source kill, surplus 1 (3,000 against 2,999): SUPPORTED. proof_verdict.json:671-686; R/twins.after.json:35.
- Evaluator unchanged: SUPPORTED. `git diff 489bc9e b65a06d -- src/egw_experiments/proof_evaluator.py` is empty.
- "One run supports the property for this run only": SUPPORTED. proof_verdict.json:2.
- Same container restarted: SUPPORTED. P/console/023-restart-shown.stdout.txt:3.
- Fault dispatched 21:12:52Z (host): SUPPORTED. P/analysis/snapshots/proof-adr0011-r03.restart.txt:11.
- StartedAt 21:13:03.73Z (guest): SUPPORTED. Same restart.txt:17.
- Six services healthy, check completed 21:26:59Z: SUPPORTED. P/console/028-services-healthy-after.stdout.txt:2-3.
- No OOM, guest-state delta shows no fault: SUPPORTED. P/console/027-guest-state-delta.stdout.txt:2,6-8; OPS/console/r03-close.log:23-24; GS/console/006-oom-before-poweroff.stdout.txt:1-2.
- Close exit 0 at 21:28:34Z: SUPPORTED. r03-close.log:34.
- Stack stopped: SUPPORTED. r03-close.log:16-22.
- QEMU ended 21:28:16Z: SUPPORTED. r03-close.log:26.
- Session closed 21:28:17Z: SUPPORTED. r03-close.log:28.
- G1 check OK: SUPPORTED. r03-close.log:27; GS/g1-after-s1.sha256check.txt:1-3.
- No QEMU left: SUPPORTED. r03-close.log:31.
- Candidate retained on disk: SUPPORTED. r03-close.log:17-22,30 show the containers exited but not removed, and `egw-data.img` present.

**WRONG / UNSUPPORTED / overclaim items only**
1. **OVERCLAIM, line 8.** "The executed tooling differs from … `489bc9e` only in `cli.py`, `controller_metrics.py`, `run.py` and `proof.sh`" is not true.
   - The record it copies (HP/console.txt:16-21) comes from a diff limited to certain paths. HP/r03_hostprep.sh:47 covers only src/egw_experiments, src/deployment, src/schemas, the Dockerfile, pyproject, the lock file and tools/session `*.sh`/`*.py`/guest, and leaves out `docs/`.
   - `git diff --stat 489bc9e b65a06d` also shows `docs/setup/qemu_integrated_gateway.md` (45 lines changed). Its section 6.1 heredoc is the helper that ran, `itest-helpers.sh` (`1634c35bc79d`).
   - That helper's `drained` quiet timer moved from Bash SECONDS to `/proc/uptime` in PR #48 (`921aca2`, `b7b919c`). Outcome 3 depends on exactly that change.
   - Correct statement: the executed tooling also differs in the helper generated from the runbook. The non-executed differences are LOG.md, tests and tools/session/README.md.
2. **MISLEADING PLACEMENT, line 12.** The "no reload" read by the post-start check is the broker's `Reloading config` count in `docker logs egw-mosquitto-1`. See OPS/session_steps.sh:349,376-378 and CS/console/001-start-state.stdout.txt:7 (`reload_lines=0`).
   - It says nothing about the controller image, but it sits under "Controller image: … not rebuilt or reloaded".
   - "Not reloaded" rests only on the fact that no load step was run (the `do_load` step is at session_steps.sh:95-141 and is absent from OPS/SUMMARY.md:9). The image ID cannot show it, because reloading the same archive gives the same ID.
3. **PRECISION, line 34.** The "55 ms" does not say which clock or which endpoints it uses.
   - It is request start to request start on the harness-host clock (attempts.csv:454→455, 54.9 ms).
   - Measured from when the failed poll finished, the gap is 50.2 ms.
   - The reading's response finished 180.7 ms after the failed poll finished (attempt 454 finished at 1275.671578).
   - "Row 158" is the evaluator's 0-based index; it is file line 160 of `controller_metrics.csv`.

No value in these two sections is WRONG, and no other claim is UNSUPPORTED.

# packages-observation

**Verification of the r03 hand-off: sections "Packages" and "Observation, remaining items"**

**Packages** (`output_test/runs/2026-09-28/`)

All seven seal prefixes match my own sha256 of each `SHA256SUMS`. Every package passed `sha256sum -c` with exit code 0 (rc=0) and no failures. Each `SHA256SUMS` lists every file in its package except itself: nothing extra, nothing missing.

| Package | sha256 of `SHA256SUMS` | Files OK | Verdict |
|---|---|---|---|
| HIST_2026-09-28-r03-host-preparation | `e1e5b8bea10be408…` | 5/5 | SUPPORTED |
| 20260928T205412Z_guest-session_attempt06 | `64a7750ac7fcb84d…` | 77/77 | SUPPORTED |
| 20260928T205459Z_live-preflight_attempt07 | `e8c5a7e87ef73c74…` | 42/42 | SUPPORTED |
| 20260928T210029Z_candidate-start-check_attempt03 | `93baab9df09e42f3…` | 10/10 | SUPPORTED |
| 20260928T210104Z_g2-gate-preconditions_attempt04 | `0c496a389c265fdf…` | 26/26 | SUPPORTED |
| 20260928T210147Z_finite-proof-adr-0011_attempt03 | `e09d4019d64628ee…` | 123/123 | SUPPORTED |
| HIST_2026-09-28-r03-operator-records | `ab2d02d5ea310f17…` | 9/9 | SUPPORTED |

- **"(open/close)" for the guest session: SUPPORTED.** `guest-session_attempt06/SUMMARY.md:10-11` gives Started 20:54:12Z and Ended 21:28:19Z, and line 30 says "session closed: stack stopped before power-off". `s1.session.status` reads "exit=0 closed=2026-09-28T21:28:17Z".
- **121 files verified and 123 entries (line 24): SUPPORTED.**
  - `finite-proof…/SUMMARY.md:27` says "121 file(s) copied and verified".
  - `SHA256SUMS` has 123 lines.
  - `controller_metrics.attempts.csv` is listed once.
- **Folder `2026-09-28` instead of `2026-09-27`: SUPPORTED for the five driver packages.**
  - The authorisation (`FINITE_PROOF_R03_AUTHORISATION_2026-09-27.md:41`) names `output_test\runs\2026-09-27\`.
  - At b65a06d, `src/egw_experiments/local_export.py:518-523` builds the date folder from the run ID's `YYYYMMDD`.
  - The two HIST packages have no `export_manifest.json` or `attempt.json`, so the operator made them, not a driver (see the imprecision item at the end).

**Observation: controller log scope**

- **"holds the container's whole log since its recreation in r01 (2026-09-26 17:59)": SUPPORTED.**
  - `raw/proof-adr0011-r03/logs/sut/controller.log:1` is "2026-09-26T17:59:10.028211723Z INFO: Started server process [1]".
  - The file has 11,862 lines: 7,910 dated 2026-09-26 and 3,952 dated 2026-09-28.
  - The recreation is in `runs/2026-09-26/20260926T175617Z_live-preflight_attempt05/console/001-stack-start-interlock.stderr.txt:6-7`: "Container egw-controller-1 Recreate" / "Recreated".
  - The r02 and r03 preflights only show "Created", not "Recreate": `20260926T210503Z_live-preflight_attempt06/.../001-…stderr.txt:6` and `20260928T205459Z_live-preflight_attempt07/.../001-…stderr.txt:5`.
  - `hook-controller_log.stdout.txt:1` reports "11862 line(s), 2691883 bytes, sha256 5b3a49ab…". That matches my own hash, and `proof_verdict.json:227`.
- **"the r01 and r02 sessions are included": SUPPORTED.**
  - "Started server process" appears at lines 1 (17:59:10), 1187 (18:14:39), 3945 (21:07:50) and 4970 (21:23:11), all on 26-09.
  - Line 7910 is "2026-09-26T21:38:06 … Finished server process"; line 7911 is 2026-09-28T20:58:19.
  - The r01 session ran 17:53:10–18:29:31Z and the r02 session 21:04:12–21:38:58Z (`2026-09-26/…guest-session_attempt04/SUMMARY.md:10-11` and `…attempt05/SUMMARY.md:10-11`).
- **"the fetch hook reads `docker logs` without `--since`": SUPPORTED.**
  - `git show b65a06d:tools/session/proof_fetch_sut_log.sh:97` is `GUEST_CMD='docker logs --timestamps egw-controller-1 2>&1'`.
  - The script uses SINCE only for docker-events (lines 22-25 and 99).
  - `manifest.json:157` shows the hook was passed 1790629309 (2026-09-28T21:01:49Z), and it went unused for this log.
  - `manifest.json:128` records commit `b65a06ddc028…`.
- **"The evaluator found no A5 occurrence anywhere in it": SUPPORTED.**
  - `analysis/proof_verdict.json:692` has `"a5_occurrences": []`. `console/029-evaluate.stdout.txt` is byte-identical to that file.
  - `proof_verdict.json:864-865` shows `controller_log_problem: null` and `controller_log_usable: true`.
  - In the b65a06d evaluator, `proof_evaluator.py:224` defines A5 as "MQTT connection ended by the controller".
  - Lines 2409-2445 scan every line of the log with no date or session filter and keep only `level == "ERROR"`. Line 5252 passes in the whole log.
  - My own grep found no ERROR-level lines in the whole file. The A5 message text appears only twice, both at INFO with `cause: "stop"` (lines 3939 and 7905, both on 26-09), so neither counts as A5.
  - The non-JSON count also matches: 1,717 by my count and at `proof_verdict.json:6`.
- **"nothing from earlier sessions entered this verdict": OVERCLAIM (minor).**
  - True for decisions: the evaluator reads the subscription list only to report it (`proof_evaluator.py:2046`). The window code at 2892-2893 reads only the kill and restart host-monotonic instants. `proof_verdict.json:736` says it is "never used to decide".
  - But content from earlier sessions does appear in the verdict document:
    - `proof_verdict.json:747-753` lists six "subscription granted" instants, four of them from 2026-09-26.
    - `controller_log_non_json_lines: 1717` at `proof_verdict.json:6` covers the whole log; 1,144 of those lines are from 26-09.
  - Better wording: "nothing from earlier sessions decided this verdict".
- **"Worth bounding before further runs": this is a recommendation, not a fact.** The broker log is also unbounded and the note leaves it out.
  - Hook line 95 runs `compose logs … mosquitto` without `--since`. `broker.log` has lines dated 2026-09-20 (65), 09-23 (1,722), 09-26 (712) and 09-28 (353).
  - This does not affect the verdict: `proof_evaluator.py:4664-4666` says the evaluator never reads the broker log for a criterion.

**Observation: still open and authorisation limits**

- **The default sampler defect (a typed `HTTPException` ends the thread): SUPPORTED.** `output_test/decisions/2026-09-26_metrics-fast-retry-handoff.md:48` says the exception "ends the sampler thread" and "the default remains open". The authorisation (`:48`) says "No … default-sampler repair is added to this session".
- **The ADR-purpose question left to the PM and Rui: SUPPORTED.** The authorisation (`:44`, `:48`) says "no … gate/claim acceptance".
- **"No further attempt is authorised. G3 remains paused.": SUPPORTED.** The authorisation (`:50`) limits it to "only for the single r03 session above". `:48` says "No automatic repeat" and "**G3 remains paused.**"

**Side note (not a claim in the hand-off):** `docker-events.log` has 41 lines and starts at 2026-09-28T21:19:32Z, even though `--since` was 21:01:49Z. It therefore does not cover the kill at 21:12:52Z. Anyone who later cites docker events for the restart would be relying on an incomplete record.

**WRONG / UNSUPPORTED / overclaim items only:**
1. OVERCLAIM (minor), line 58: "nothing from earlier sessions entered this verdict". Earlier-session data is in the verdict document as reported-only fields (`proof_verdict.json:747-753`, four of six entries dated 2026-09-26; and `:6`, the 1,717 non-JSON lines counted over the whole log). It decided nothing (`proof_evaluator.py:2046`, `2892-2893`; `proof_verdict.json:736`).
2. IMPRECISION (minor), line 54: "the drivers file them by the UTC date of their run IDs". This holds for the five driver packages (`local_export.py:518-523`). The two HIST packages have no export manifest or run ID; the operator placed them by hand.
3. OMISSION (minor), line 58: the scope note covers only `controller.log`. `broker.log` is unbounded in the same way (hook line 95; entries back to 2026-09-20), and it is not used for any criterion.

No WRONG or UNSUPPORTED facts in either section.