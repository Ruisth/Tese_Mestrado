R=itest-invalid-01-q1; F3=used; [ ! -e $P/$R ] && ssh egw-tcg "[ ! -e /opt/egw/deployment/data/events/$R ]" && F3=fresh; if [ "$F3" = fresh ]; then T0_3=$(guest_epoch) && run_test $R 42 --scenario invalid-payload --duration 120; RT=$?; else RT=used; stop "test 3: $R is not fresh (F3='$F3': $P/$R exists on the host, the guest holds an event log of it, or the guest did not answer) - a run id used before is never judged, so the simulator was NOT started and nothing was published: choose a NEW run id"; fi     # F3: whether the run id was fresh before this run on the host ('pre' refuses a used one) AND on the guest, whose event log of a run id persists and is appended to and which 'pre' cannot see (a guest that does not answer leaves F3 'used'), so on a fresh one every file under $P/$R and every line of the fetched log are this run's, and on any other nothing is started (Section 7, rule 1: a failed precondition publishes nothing); the guest epoch before the test's first action bounds its controller log (fifth line); UNVERIFIED: the guest freshness read on the real guest (Appendix B, item 24)
C3=stop; [ "$F3" = fresh ] && ssh egw-tcg "cat /opt/egw/deployment/data/events/$R/events.jsonl" | cmp -s - $P/$R/events.jsonl && keep $P/$R/events.jsonl $P/$R.events.post-drain.jsonl && C3=ok || stop "test 3: no copy of the events fetched after the drain of this run (F3='$F3': a run id used before, on the host or on the guest, is never judged; on a fresh one the precondition failed, 'finish' stopped before its fetch - a drain that gave up -, or the fetched file is not the guest's whole log - a fetch that failed part-way, or a line appended after it), or it was not kept - test 3 is NOT evaluated"     # 'finish' (6.1) fetches events.jsonl only after its 'drained' (wait && drained && fetch): on a fresh run id that file is the end of test 3's planned collection, kept here write-once under test 6's name before anything could fetch it again - also when 'finish' stopped AFTER its fetch (RT not 0: 'accounted' naming a message without a logged outcome, for instance), so that such a message is judged on the next line and fails test 3; a drain that gave up stopped 'finish' before its fetch, so there is no copy; and the file is kept only when it is, byte for byte, the guest's log read again here (cmp): a fetch that failed part-way leaves a partial file, which is no copy; UNVERIFIED: the whole-log comparison on the real guest (Appendix B, item 24)
[ "$C3" = ok ] && $REC acceptance $P/$R --events $P/$R.events.post-drain.jsonl || stop "test 3: the per-identity acceptance check was not run (C3='$C3'), could not read its inputs (exit 1: test 3 NOT evaluated) or found a valid message never accepted in the post-drain copy (exit 4: test 3 FAILS)"     # every valid message (not intended_invalid) needs an accepted line of this run in the copy; no timestamp is read, so a late acceptance counts; UNVERIFIED: on a real event log (Appendix B, item 24)
[ "$RT" = 0 ] && python3 - ~/egw-tcg/itest/$R <<'EOF' || stop "test 3: not evaluated (RT='$RT') or the evaluation script failed"
import json, sys
d = sys.argv[1]
sent = {json.loads(l)["message_id"]: json.loads(l) for l in open(f"{d}/sent_events.jsonl")}
ev = [json.loads(l) for l in open(f"{d}/events.jsonl")]
inv = {m for m, s in sent.items() if s.get("intended_invalid")}
rej = {e["message_id"] for e in ev if e["outcome"] == "rejected"}
acc = {e["message_id"] for e in ev if e["outcome"] == "accepted"}
print("intended_invalid:", len(inv), "rejected:", len(rej), "intended_invalid accepted:", len(inv & acc), "valid rejected:", len(rej - inv))
EOF
[ "$RT" = 0 ] && sut_log controller $R "$T0_3" && python3 - ~/egw-tcg/itest/$R.sut/controller.log <<'EOF' || stop "test 3: the controller log bounded to this test was NOT read (RT='$RT', or sut_log stopped above), or it could not be counted - it shows no rejection, nor their absence"
import json, sys
n = rejected = 0
first = None
for line in open(sys.argv[1], encoding="utf-8"):
    n += 1
    try:
        doc = json.loads(line.partition(" ")[2])
    except ValueError:
        continue
    ctx = doc.get("context") if isinstance(doc, dict) else None
    if isinstance(ctx, dict) and doc.get("message") == "telemetry event processed" and ctx.get("outcome") == "rejected":
        rejected += 1
        first = first or ctx.get("error")
print("controller log of this test (%s): lines=%d rejected=%d first rejection error: %s" % (sys.argv[1], n, rejected, first))
EOF
