# Corrections to the integration test procedures — final report (2026-09-18)

## 1. Scope and status

The project review of 2026-09-18 (pull request #28, head `ae7c661`) confirmed four residual defects in the test procedures of the [integrated QEMU runbook](../setup/qemu_integrated_gateway.md) and in the local ACL probe `src/deployment/scripts/probe-acl.sh`. This report records the corrections and their positive and negative cases. The build and the two boots recorded after the [image audit](2026-09-17-egw-image-audit.md) were accepted and were not repeated. **Nothing in runbook Sections 4-9 has ever run on the real host, guest or broker.** Every case below ran the published text, taken verbatim from the runbook, or the unmodified probe, against stub commands (`ssh`, `scp`, `curl`, `docker`, the simulator, a shortened `sleep`) in a non-interactive shell under WSL Ubuntu-24.04. That shows the decision logic for a given observation: which status and which printed line follow from which inputs. It does not show that the real commands produce those observations, and it is not evidence of integration.

`src/deployment/scripts/probe-acl.sh` and `src/tests/test_probe_acl_verdict.py` are **not part of pull request #28**; they travel with the deployment pull request. The runbook and [`test_runbook_itest_helpers.py`](../../src/tests/test_runbook_itest_helpers.py) belong to pull request #28.

## 2. The four defects

**1 — `accounted` decided on totals.** Confirmed: the helper of runbook 6.1 computed the sent `message_id`s without a record, but decided on "sum of counter differences >= records sent". Reproduction of the project review, with the published code: A and B are sent; A is accepted and then received again as a duplicate; B has no outcome; the sum is 2 = sent; the helper returned 0 and printed `OK: every published message has reached a terminal counter` while showing `without_event_record=1`. Correction: `accounted` reconciles identities. A published record counts only when the fetched `events.jsonl` holds a record with the same `message_id`, this `run_id` and one of `accepted`, `rejected`, `duplicate`, `failed`; every other record is named under `NO LOGGED OUTCOME` or `NOT RECONCILABLE` and the status is non-zero. The counter movement is printed as a secondary figure that decides nothing, and no helper states that nothing is pending. `ACCEPT_UNACCOUNTED=1` captures the after state, records the decision and still ends non-zero (also in 6.4). The 130 s quiet window stays as a temporary precaution and is worded as such. Residual limits: the fetched log is a copy; a missing outcome may be transient or permanent and the log cannot tell; a run id reused after its host artefacts were removed is reported `OK` (Section 7, limits (i)-(iii)).

**2 — Test 7 could pass without an interruption.** Confirmed: only the `start` status could produce a `STOP` line, and the status of `wait $FAULTP` was dropped. Correction: both exit codes are kept and printed with the service state read after each step. `INTERRUPTION SHOWN` needs `stop` exit 0 and `running` to `exited`; `RECOVERY SHOWN` needs `start` exit 0 and `exited` to `running`. The recovery is attempted on every path the fault job controls, and `T7` is 0 only when the simulator, the fault job (`FW`), both `SHOWN` lines, no `STOP` line and a live `/ready` poller (`RK`) all hold. Residual limits: a job stopped or killed with `KILL` cannot recover (the line reports the `wait` status and the manual command); `UNVERIFIED:` the state strings of Compose 2.26.0 and the real OpenSSH client as a background job.

**3 — Failed evidence capture could go unnoticed.** Confirmed: element 1 of `PIPESTATUS` (`tee`) was never read in `sim_post`, in 6.2 and in test 9; in the probe `LOGS_RC` was printed and read by no verdict branch. Correction, runbook: the transcript target is created before the simulator starts, every element of `PIPESTATUS` is copied at once, and completion needs simulator 0, `tee` 0 and a non-empty file; the other evidence-writing lines of Sections 4-9 are bound the same way. Correction, probe: an incomplete collection of the broker log (non-zero status, empty output, anchor line not found exactly once, `grep` error, short `broker.txt`, evidence directory not writable, `verdict.txt` not written) gives `INCONCLUSIVE` (exit 3); `FAIL` keeps precedence when a delivery, an accepted anonymous session or an accepted-session line is independently present. Residual limits: a partial log returned with status 0 and a write lost during the run to a file whose expected size is 0 bytes are not detectable (stated in the probe header: necessary, not sufficient); `UNVERIFIED:` `docker compose logs --timestamps` on the guest — if it does not hold, every run is `INCONCLUSIVE`, never `PASS`, and `broker_logs.err` keeps the reason.

**4 — `pkill -f 'ssh -f -N'`.** Confirmed twice (5.7 message, test 8 line). Correction: 5.7 writes `~/egw-tcg/tunnel.sh`; the tunnel is an ssh master on the project's own control socket `~/egw-tcg/tunnel.ctl` and is checked and closed only through it (`-O check`, `-O exit`). A socket file is removed only when the check answers `Connection refused`; any other failure is a `STOP` and the file is left alone. No `pkill` or `killall` remains in the runbook. Residual limits: a real master opened with `-M` and closed with `-O exit` was not exercised (no sshd was started); the `Connection refused` wording was observed with OpenSSH 9.6p1 only — another wording ends in `STOP`, never in a removal.

## 3. Executable cases

Both modules were re-run for this report on 2026-09-18 under WSL Ubuntu-24.04 (bash 5.2.21, dash, Python 3.12.3, pytest 9.1.1), in a `/tmp` mirror of the repository layout. "Observed" is the result of that run. Numbers follow the order in the module; each test name states scenario and expected outcome. P = positive (the procedure is expected to succeed), N = negative (it must refuse).

### 3.1 `src/tests/test_runbook_itest_helpers.py` — observed `64 passed in 13.15s` (13 P, 51 N)

| # | Test id (fragment) | Scenario | Expected | Observed | P/N |
|---|---|---|---|---|---|
| 1 | `helper_heredoc_is_quoted_and_loads` | helper file written by the runbook heredoc | loads; holds the variable name, not the password | PASSED | P |
| 2 | `helper_file_sourced_with_an_empty_password` | password variable empty | `STOP`, not reported as loaded | PASSED | N |
| 3 | `accounted_every_published_record_has_a_logged_outcome` | all identities logged | exit 0, `-> OK` | PASSED | P |
| 4 | `accounted_review_case_a_accepted_then_duplicate_b_without_record` | the review's A/B case, counters = sent | non-zero, B named, no `OK` | PASSED | N |
| 5-7 | `accounted_outcome_logged_under_another_run_id`, `..._not_one_of_the_four`, `..._published_twice` | other `run_id`; outcome not one of the four; duplicate id in the sent file | non-zero, never `OK` | PASSED | N |
| 8-11 | `accounted_fetched_event_log_missing/empty/malformed`, `fetch_scp_failure` | event log absent, empty, malformed; `scp` fails | refused; nothing decided | PASSED | N |
| 12 | `accounted_controller_restart_..._identities_still_decide_ok` | `started_at` changed, all logged | exit 0, counters `not comparable` | PASSED | P |
| 13-15 | `..._restart_..._with_b_missing`, `..._queue_not_empty`, `..._metrics_unreachable` | B missing after a restart; queue depth > 0; `/metrics` unreachable | refused | PASSED | N |
| 16 | `accounted_operator_accepts_b_missing` | `ACCEPT_UNACCOUNTED=1` | decision recorded, no `OK` line | PASSED | N |
| 17 | `run_test_transcript_written_every_step_0` | all steps succeed | exit 0, `PROCEDURE COMPLETE` | PASSED | P |
| 18-21 | `run_test_transcript_target_cannot_be_created`, `..._real_tee_write_failure`, `..._tee_reports_failure`, `..._empty_transcript` | transcript unwritable; `tee` fails (real and stub); empty transcript, simulator exit 0 | failed; simulator not started in 18; `post` still runs | PASSED | N |
| 22-25 | `run_test_simulator_exit_3`, `..._precondition_fails_*` (3) | simulator fails; `/ready` not 200; run id used; `/metrics` unreachable | failed; simulator never called in 23-25 | PASSED | N |
| 26-27 | `run_test_b_without_logged_outcome`, `..._b_missing_accepted_by_the_operator` | B without outcome; then accepted by the operator | no after state; captured but still non-zero | PASSED | N |
| 28 | `flow_6_2_to_6_4_every_step_0` | 6.2-6.4 verbatim, all good | files written, no `STOP` | PASSED | P |
| 29-34 | `flow_6_2_tee_reports_failure`, `..._transcript_target`, `..._precondition_fails`, `flow_6_3_b_without_logged_outcome`, `..._twin_get_fails`, `..._twin_file_cannot_be_written` | capture or precondition failures in 6.2 and 6.3 | `STOP`; 6.4 refuses to run | PASSED | N |
| 35 | `test_9_broker_log_saved` | log saved | exit 0, no `STOP` | PASSED | P |
| 36-38 | `test_9_broker_log_ssh_fails_with_partial_output`, `..._tee_reports_failure`, `..._empty_output` | `ssh` 255 with partial output; `tee` fails; empty | `STOP` naming the status | PASSED | N |
| 39 | `test_7_stop_and_start_succeed` | `running` -> `exited` -> `running` | `T7=0`, both `SHOWN` lines | PASSED | P |
| 40-41 | `test_7_stop_fails_and_start_succeeds`, `..._label_recovery_shown_is_not_printed` | the review's case: stop fails, start succeeds | not accepted; service started again; `NO RECOVERY TO SHOW` | PASSED | N |
| 42-45 | `test_7_stop_succeeds_and_start_fails`, `..._both_fail`, `..._state_stays_running`, `..._state_unreadable` | start fails; both fail; stop exit 0 without state change; state `unknown` | not accepted; both exit codes printed | PASSED | N |
| 46-48 | `test_7_wait_status_non_zero`, `..._killed_after_the_stop_gives_wait_137`, `..._receives_term_during_the_outage` | `wait` status non-zero with both `SHOWN` lines; job killed; `TERM` | not accepted; recovery attempted on `TERM` | PASSED | N |
| 49-51 | `test_7_no_simulator_at_injection_time`, `..._simulator_fails`, `..._precondition_fails` | no simulator at +90 s; simulator fails; `pre` fails | nothing stopped or injected; never 0 | PASSED | N |
| 52 | `test_7_real_pgrep_finds_the_simulator` | real `pgrep` | fault injected | PASSED | P |
| 53 | `test_7_real_pgrep_simulator_already_gone` | real `pgrep`, no process | nothing stopped, never 0 | PASSED | N |
| 54, 56 | `tunnel_open_line_of_5_7_no_master_ports_free`, `tunnel_open_master_already_answers` | clean state; second call | one master on the project socket; `MASTER ANSWERS`, never doubled | PASSED | P |
| 55, 57 | `tunnel_open_host_port_busy_and_no_master`, `tunnel_open_ssh_exits_non_zero` | port busy; ssh fails | `STOP`, opens nothing, kills nothing | PASSED | N |
| 58 | `tunnel_reopen_line_of_test_8_..._unrelated_ssh_forwarder_survives` | test 8 line with a foreign `ssh -f -N` process alive | only the project socket closed; foreign process survives | PASSED | P |
| 60-61 | `tunnel_close_no_socket_file`, `tunnel_close_stale_socket_connection_refused` | nothing to close; stale socket | return 0; only that file removed | PASSED | P |
| 59, 62-64 | `tunnel_close_exit_request_fails`, `..._check_cannot_be_evaluated`, `..._path_is_not_a_socket`, `tunnel_text_every_ssh_control_command_names_the_project_socket` | `-O exit` fails; check not evaluable; regular file at the path; static text check | `STOP`, file left alone; no command matches processes by pattern | PASSED | N |

### 3.2 `src/tests/test_probe_acl_verdict.py` — observed `94 passed in 82.63s (0:01:22)` (47 scenarios under dash and under bash: 2 P, 92 N)

| Test id | Scenario | Expected | Observed | P/N |
|---|---|---|---|---|
| `test_acl_enforced_anonymous_refused_complete_log_gives_pass_exit_0` | ACL enforced, refusal observed, log complete | `PASS`, exit 0 | PASSED x2 | P |
| `test_verdict[anonymous_session_accepted_*]` (2), `[anonymous_client_received_a_message_*]`, `[anonymous_refusal_printed_but_broker_logged_an_accepted_session_*]` | anonymous session accepted (rc 27, rc 0), delivery, accepted-session line | `FAIL`, exit 1 | PASSED x8 | N |
| `test_verdict[anonymous_exec_error_*]` (2), `[anonymous_refusal_text_with_other_bytes_*]`, `[anonymous_tls_error_*]`, `[anonymous_rc_5_*]` (2) | refusal not observed as specified | `INCONCLUSIVE`, exit 3 | PASSED x12 | N |
| `test_verdict[message_delivered_to_the_write_only_user_*]`, `[publication_of_the_read_only_user_delivered_v311_*]`, `[..._v5_*]` | ACL not enforced | `FAIL`, exit 1 | PASSED x6 | N |
| `test_verdict[bytes_that_are_not_a_delivery_*]`, `[unauthorised_subscriber_ended_before_*]`, `[last_publication_returned_too_close_*]`, `[..._lost_its_connection_*]`, `[..._subscribed_twice_*]`, `[authorised_subscriber_never_started_*]`, `[first_publisher_did_not_run_*]` | liveness or positive control not shown | `INCONCLUSIVE`, exit 3 | PASSED x14 | N |
| `test_verdict[log_collection_failed_with_full_output_*]`, `[..._with_partial_output_*]`, `[log_collection_empty_with_rc_0_*]`, `[..._no_longer_contains_the_anchor_line_*]`, `[anchor_could_not_be_read_*]`, `[anchor_collection_empty_*]` | the review's item 3: collection failed, empty or not covering the run, all else passing | `INCONCLUSIVE`, exit 3, never `PASS` | PASSED x12 | N |
| `test_verdict[log_collection_failed_and_unauthorised_delivery_*]`, `[log_collection_failed_and_anonymous_session_alive_*]` | collection failed and independent proof of a security failure | `FAIL`, exit 1 (precedence) | PASSED x4 | N |
| `test_evidence_directory_unwritable_after_the_run_*` | evidence directory read-only during the final collection | `INCONCLUSIVE`, exit 3, warning on stderr | PASSED x2 | N |
| `test_precondition[*]` (10), `test_deployment_directory_missing_*`, `test_evidence_directory_cannot_be_created_*` | bad tag, window or ready value; `.env` or a password missing; evidence directory exists; directories missing | exit 2, stdout empty, `docker` never called | PASSED x24 | N |
| `test_dot_env_referencing_an_unset_variable_*`, `test_dot_env_that_is_not_read_to_its_end_*[exit_0, exit_1, syntax_error, last_command_fails]` | `.env` ends or aborts the shell | exit 2, nothing run, never the `PASS` or `FAIL` code | PASSED x10 | N |

Sensitivity, as reported by the authors of the cases (not repeated for this report): each reviewed defect re-introduced into a copy of the runbook makes between 1 and 11 cases fail, and the probe as the project review read it fails 20 cases, 14 of them with `exit=0 / verdict=PASS`.

## 4. Findings of the adversarial verification beyond the four items

- **Same defect classes elsewhere in the runbook (corrected).** The 6.4 line ignored `unaccounted.txt` (now a `STOP`). `accounted` did not read `run_id` or `outcome`, printed `OK` with zero published records and called a repeated absence "permanent" (now `MAY be permanent`). The 6.5 restart and the test 8 reboot did not bind the result (now a changed `started_at`, and a changed kernel boot id, are required: `RESTART SHOWN`, `REBOOT SHOWN`). Any status 255 of `-O check` was read as a stale socket; `TUNNEL UP` rested on a process check (now `MASTER ANSWERS`); one `STOP` text covered two branches of `tunnel_up`; the 5.5 `grep` ran on a log that might not have been read; the 9(d) display group tested only its last command; 3.1 advised killing whatever holds the ports.
- **Interactive shell (corrected).** On a pseudo-terminal, a line typed during test 7 stopped the background fault job with `SIGTTIN` and the service stayed `exited`. Both background jobs now run with `< /dev/null`, and `RK` shows whether the `/ready` poller covered the run. After Ctrl-C the poller survives: the runbook names the clean-up command.
- **Found by the independent cases (corrected).** `RECOVERY SHOWN` was printed on paths where nothing had been stopped (the verdict was not affected); it now needs `exited` before the `start`. In the probe, a `.env` that aborted the shell under bash left with exit 1, the `FAIL` code, and a `.env` containing `exit 0` left with 0, the `PASS` code, with nothing run; an EXIT trap around the read turns every such end into exit 2. The fix first proposed (`set +u`) was rejected: with it the probe would run.
- **Rejected with evidence.** Dropping the anchor step of the probe: without it the case "window no longer contains the start of the run" returns `PASS` while printing a claim about the whole run. Bounding the `/ready` poller loop: a fixed count would fail good runs.
- **Left as is.** `kill $READYP` (recorded PID of a job of the same shell); the display-only `grep` lines of 3.5 and 5.6 (Section 3 ran as written); the length of the runbook (history sentences were cut; Appendix B still records each pass). Applied afterwards: the runbook names `broker_logs.err` and Appendix B item 19 says 69 stubbed cases. Open, small: the runbook does not describe the `.env` precondition cases of the probe; that text travels with the deployment pull request.

## 5. What remains unverified, and what decides it

| Unverified | Decided by |
|---|---|
| Every helper and line of Sections 4-9 against the real controller, Ditto, `ssh`, `scp` and `tee`; `svc_state` strings (`running`, `exited`, `docker compose ps -aq`) on Compose 2.26.0; `/proc/sys/kernel/random/boot_id` on the guest kernel; the real OpenSSH client as a background job and as master (`-M`, `-O exit`) | first deployment on the guest (runbook Sections 5-7) |
| Probe texts the stub imitates: refusal wording, accepted-session and subscribe lines, `docker compose logs --timestamps` reprinting a line identically, its status and stderr | a real Mosquitto 2.0.22 broker on the guest (test 9(d)) |
| The probe (`#!/bin/sh`) and the guest-side 5.5 line under BusyBox ash, including the EXIT trap after an aborting error; only dash and bash were run | BusyBox ash on the guest |
| Whether the controller has work pending at a given instant: not observable today, so the 130 s window is a precaution and no helper claims it | the controller counters `received`, `in_progress` and `processing_errors`, accepted by the project review as a separate, delimited change (runbook Section 9 item 7, not implemented); they will not replace identity reconciliation |
| Full disk; a partial broker log returned with status 0; `grep` failure branch of the probe (read, no case in the module) | not decided by any planned step; stated as limits |

## 6. How to reproduce

On Linux or WSL (on Windows both modules skip by design), from a checkout that holds the files, with `pytest` and `pytest-asyncio` installed in a virtual environment. `python3`, `bash`, `dash` and `pgrep` must be present. No Docker, QEMU or broker is started.

```
cd src
python -m pytest tests/test_runbook_itest_helpers.py -q -p no:cacheprovider -rA
python -m pytest tests/test_probe_acl_verdict.py -q -p no:cacheprovider -rA
```

Expected summary lines: `64 passed` and `94 passed` (no skip, no xfail). The second module skips when `src/deployment/scripts/probe-acl.sh` is absent, which is the case on the branch of pull request #28.
