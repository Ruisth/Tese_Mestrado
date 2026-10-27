# (b) and (c): the broker log is the actual evidence, the simulator discards the CONNACK reason. Each sub-check takes the
# guest epoch just before its simulator, 3 s back (guest_epoch 3: the guest's wall clock steps back by up to 3 s, and a
# step between that read and the broker's line would stamp the line before the bound, where '--since' drops it), and
# reads the broker log bounded to [that epoch, the guest's clock at the read] right after it (sut_log, 6.1): never an
# earlier session's line. Those 3 s may hold the last line of the step before it ((a)'s TLS failure in (b)'s log; one
# of (b)'s in (c)'s, if (b)'s read took less than 3 s). A line in (c)'s log that names (b)'s client id,
# egw-simulator-itest-auth-wrongpw-q1, is (b)'s, never (c)'s. UNVERIFIED: whether the broker's "not authorised" line names
# the client id at all or reads <unknown> (as in (e) below); either way a "not authorised" line in (c)'s log, named or
# <unknown>, is never (c)'s evidence, which is a TLS/socket error (Expected below). A lower bound that was not read runs
# no probe and prints no 'exit=' (a STOP names the sub-check): exit 1 is the refusal status (b) and (c) expect, so an
# unbounded probe's exit could read as their evidence, and its connection attempt would change the broker log.
# (b) wrong password -> CONNACK not authorised
if T0_9B=$(guest_epoch 3); then python -m egw_simulator run --scenario smoke --seed 42 --duration 10 --run-id itest-auth-wrongpw-q1 --output ~/egw-tcg/itest --broker 127.0.0.1 --port 8883 --username egw-simulator --password wrong --ca-cert ~/egw-tcg/ca.crt; echo "exit=$?"; else stop "test 9(b): the lower bound of (b)'s evidence was NOT read - the probe was NOT run"; fi
sut_log broker itest-auth-wrongpw-q1 "$T0_9B" && cat ~/egw-tcg/itest/itest-auth-wrongpw-q1.sut/broker.log || stop "test 9(b): the broker log bounded to (b) was NOT read - (b) has no evidence (a read that failed shows no refusal)"
