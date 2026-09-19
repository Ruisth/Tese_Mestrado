# 0010 — Progress counters in the controller's `GET /metrics`: `received`, `in_progress`, `processing_errors`

**Status:** Proposed (2026-09-18) — additive extension of
[CONTRACTS.md](../../src/CONTRACTS.md) section 5, following the project review
of 2026-09-18. Nothing here accepts a gate, validates a claim or changes a
maturity level. The change is verified by unit tests with fakes only; it has
not been run against a live broker, Ditto or an ARM64 system.

Numbering: `dev` ends at 0007. Number 0008 is used by an open proposal
(pull request #30) and 0009 is kept for other open work; numbers are never
reused, so this record takes 0010.

## Context

Line numbers in this section refer to the base commit `184d264` of `dev`.

- `GET /metrics` returns `accepted`, `rejected`, `duplicate`, `failed`,
  `dropped`, `queue_depth`, `started_at`, `uptime_s`, `monotonic_ns` and
  `wall_utc` (`src/egw_controller/app.py:111-115`,
  `src/egw_controller/metrics.py:71-87`, `src/CONTRACTS.md:119-123`). There is
  no counter of messages received and no indicator of a message being
  processed.
- `queue_depth` is `asyncio.Queue.qsize()`
  (`src/egw_controller/service.py:165-167`). The single consumer removes a
  message with `await self._queue.get()` (`service.py:172`) and only then
  awaits `process()` (`service.py:176`), so the message being processed is
  **not** in `queue_depth`.
- An outcome counter is incremented inside `_emit`, after the event record is
  written (`service.py:393-394`). A message in a Ditto retry or back-off is
  therefore invisible in every field.
- Not every message ends in a counter. An exception that escapes `process()`
  is logged and swallowed by the consumer loop (`service.py:177-181`) with no
  counter and no event record; this includes a failed write of the event
  record, which skips the outcome increment on the next line. A message that
  reaches the MQTT callback while the bridge has no running event loop is
  discarded with a warning only (`src/egw_controller/mqtt.py:190-193`).
  `dropped` is incremented at the enqueue step on `QueueFull`
  (`service.py:158-159`).
- Consequence: a host-side check cannot tell "nothing is being processed"
  from "one message is in a retry" with one reading. A test procedure has to
  wait for a quiet interval as a precaution, which is not proof, and
  reconcile the messages sent with the logged outcomes by identity.

Rules that govern the change:

- `src/CONTRACTS.md:5-8` requires a coordinated update of simulator,
  controller, schemas, TDs, deployment, harness and tests, and a LOG entry.
- The integrated plan, section 1
  ([`INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md),
  its table row for the public implementation interfaces), states that
  "Version 1.1 is frozen for this restructuring;
  material changes require an ADR and regression tests." The accounting
  identity and the restart rules are new normative statements, so the change
  is treated as material: hence this ADR and the regression tests.
- Gate G3, the P0 feature freeze, is *Not decided* (same document, section 4.2),
  and its prospective acceptance criteria — which require the public contracts
  to be frozen — are in section 4.3. An additive, ADR-backed change is
  admissible now.
- The confirmation marker (`src/CONTRACTS.md`, sub-section "Confirmation
  marker", sprint P5) is the precedent for an additive `/metrics` change: a
  dated sub-section, the sentence "change no existing field", and no change
  of the v1.1 title. This ADR follows it, so no contract version string
  moves and `diagrams/**` stays out of the change.
- [`diagrams/README.md`](../../diagrams/README.md), last paragraph
  ("Contract version currently reflected by `architecture.md`"), says that
  when `src/CONTRACTS.md` is amended the version named there and in
  `architecture.md` is bumped in the same change. The rule is read here as
  the P5 change applied it (commit `49284b3`, 2026-08-10, amended
  `src/CONTRACTS.md` and no file under `diagrams/`): it keeps the version
  string of the diagrams equal to the contract title, and the title stays
  v1.1, so there is no version to bump. The parenthesis of that paragraph
  lists what v1.1 added (`queue_depth`/`dropped` among them), not the field
  set of `/metrics`, and `architecture.md` names the endpoint only, not its
  fields. The reading is to be repeated in the pull request so that a
  reviewer can reject it.

## Decision

Three additive integer fields in `GET /metrics`; normative wording,
the identity, the restart rules and the shutdown exclusion live in
CONTRACTS.md section 5, sub-section "Progress counters in `GET /metrics`".

- **`received`** is counted as the first statement of
  `ControllerService.submit()`, on the event loop, **before** the
  queue-capacity decision. It is one counting point for every producer of
  the queue.
- **`in_progress`** is raised immediately after the consumer takes a message
  (after the shutdown-marker check and **before** the `try`) and lowered in a
  `finally`. Placing the call before the `try` makes "the `finally` runs if
  and only if the gauge was raised" true by structure, including when the
  consumer is cancelled while waiting for a message.
- **`processing_errors`** is a **residual**: when processing of a message
  ends, the counter is raised — in the same lock acquisition that lowers
  `in_progress` — if no outcome counter moved since that processing started.
  It therefore covers an escaping exception, cancellation of the consumer
  and any future path that returns without recording an outcome, and it
  never double-counts a message whose outcome was already counted.
- Accounting identity, for every response of a running controller, all terms
  from that one response:
  `received == accepted + rejected + duplicate + failed + dropped +
  processing_errors + in_progress + queue_depth`.
- **One response is one snapshot.** Every term of the identity is written on
  the event-loop thread in a synchronous stretch (no `await` between the two
  updates that move a message from one term to another), and the only reader,
  the `/metrics` handler, is a coroutine whose body has no `await`, on the
  same thread. The MQTT network thread writes no counter. The existing lock
  in `MetricsCounters` still guarantees that no update is lost and that the
  counters are copied in one acquisition, but it does **not** give a reader
  on another thread the identity: the outcome increment and the lowering of
  `in_progress` are two acquisitions, and `queue_depth` is outside the lock.
  The identity is guaranteed for readers on the event loop, which is the only
  reader that exists.
- **Unchanged:** `queue_depth`, every existing field, `increment()`,
  `increment_dropped()`, `process()`, `_emit()`, `stop()`, the MQTT bridge,
  outcomes, event records, retry policy, log messages and the shutdown
  sequence. The new names are not event outcomes and never enter
  `events.OUTCOMES`. `CancelledError` still propagates.

The counters show the **internal state of one controller process only**. They
cannot show a message that never reached the pipeline, they carry no message
identity, and they **never replace the reconciliation, by identity, of the
messages sent with the outcomes recorded in `events.jsonl`**.

## Consequences

- Positive: one reading lets an operator see that the controller holds no
  work at that instant (`in_progress == 0 and queue_depth == 0`) and check
  the reading against the identity. A message that ends with no outcome,
  silent until now, becomes visible as `processing_errors`.
- `received` differs from the analysis term `received` of CONTRACTS.md
  section 9 ("controller callback"): the counter is taken one thread
  hand-over later and excludes a message discarded by the callback and a
  message still in hand-over. The contract states the difference; section 9
  and the latency definition are unchanged.
- `processing_errors` means "no outcome was recorded", not "not applied": the
  Ditto update precedes the event record, so the twin may already have been
  updated. The underlying defect — a failed event write skips the outcome
  counter — is made visible, not repaired.
- During shutdown `queue_depth` may include the one internal marker, so the
  right-hand side of the identity may exceed `received` by one. The contract
  states this exclusion in words rather than relying on the shutdown order of
  the HTTP server.
- The residual rule assumes the single consumer that `ControllerService`
  declares. An outcome increment from outside the consumer during processing
  would mask an error; no such caller exists.
- The snapshot property depends on three facts that a later change could
  break silently: the handler stays a coroutine with no `await` inside it,
  no transition gains an `await`, and no counter is written from the MQTT
  network thread. Regression tests pin each of them: a structural test
  keeps the handler a coroutine and a second one drives it by hand and fails
  if it suspends even once
  (`test_metrics_handler_never_gives_the_loop_back`); a reader that
  evaluates the identity at every loop iteration while messages go through
  Ditto fails when an `await` is placed inside a transition
  (`test_identity_holds_at_every_loop_iteration_while_messages_arrive`); a
  test with a real producer thread and HTTP polling repeats both checks
  under pressure and asserts that `submit` only ever runs on the loop
  thread; and a bridge test
  (`test_bridged_message_is_received_only_after_the_hand_over`) pins that a
  message is counted only after the hand-over to the loop. The rule is also
  stated at the handler and in the `metrics.py` docstring.
- The single lock acquisition that lowers `in_progress` and raises
  `processing_errors` is not what gives a reader the identity; confinement
  to the event loop is. A reader on the loop cannot observe the difference,
  and no black-box test can see it on an interpreter with a global lock, so
  the single acquisition is pinned by an implementation-level test
  (`test_each_operation_touches_the_counters_in_one_lock_acquisition`).
- Robustness: `processing_finished()` raises `RuntimeError`, changing no
  counter, when no message is in progress, so `in_progress` can never be
  negative. The consumer cannot reach that case: `processing_started()` sits
  immediately before the `try` whose `finally` calls
  `processing_finished()`.
- Cost on the processing path: three uncontended lock acquisitions and two
  sums over four integers per message. No measurement is claimed; the two
  latency stamps are untouched.
- Coordinated-update verdict: controller changed; tests updated and added;
  simulator, schemas, TDs and deployment unchanged (none reads or describes
  `/metrics`; only `/health` and `/ready` are probed); harness unchanged (it
  reads six counters and the marker by key and ignores other integer keys).

## Alternatives rejected

- **Counting `received` in the MQTT callback.** A message in hand-over would
  be on the left-hand side and in no right-hand term, so the identity would
  fail for an ordinary reading. It would need a fourth field, a change of the
  bridge constructor and state shared across threads.
- **A counter for messages discarded by the callback.** A fourth field
  outside the decision of 2026-09-18. In the wired application the event loop
  is attached before the network thread starts, so the path is not reachable
  at start-up.
- **Hiding the shutdown marker in `queue_depth`.** Edits an existing field
  that the harness consumes. Held in reserve; it would need its own decision.
- **Making the identity hold for readers on another thread.** Requires
  editing `_emit()` and wrapping the queue, for a reader that does not exist.
- **Incrementing `processing_errors` in the `except` branch.** Misses
  cancellation, double-counts an exception raised after an outcome, and
  misses a future `process()` that returns without an outcome.
- **Contract version bump, instance identifier, JSON Schema for `/metrics`,
  another exposition format.** Outside one small observability change; the
  P5 precedent covers additive fields.

## Follow-ups (not part of this decision)

- Recording the new fields in the harness file `controller_metrics.csv` and
  using them in the analysis.
- Using the single-reading test in the integration runbook. Whether that
  procedure shortens its quiet interval is a decision for that change; this
  ADR makes no such claim.
- Repairing the defect by which a failed event write leaves a message with no
  outcome.
