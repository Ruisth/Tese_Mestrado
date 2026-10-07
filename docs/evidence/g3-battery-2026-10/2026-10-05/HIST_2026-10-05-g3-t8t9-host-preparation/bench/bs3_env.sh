# Stream BENCH: the environment of one bench (sourced; B is the bench, HERE this folder).
# HOME and every EGW_* point inside the bench; the bench's stubs and the test module's
# stubs are first on PATH; the execution venv's real python is used read-only through the
# bench venv (no bytecode is written). Two switches, set by the scenario:
#   BENCH_SCALED=1      the module's STUB_SLEEP and STUB_TIMEOUT are on PATH (the scales
#                       are EGW_STUB_MS_PER_S and EGW_STUB_TIMEOUT_MS_PER_S); otherwise
#                       the host's own sleep and timeout are used (real time);
#   BENCH_FAST_DRAIN=1  the helper's 'drained' returns after two readings (venv/bin/activate
#                       of the bench says how); otherwise its real 130 s quiet window runs.
case ${B:-} in /tmp/g3-s3-bench/?*) ;; *) echo "refused: B must be /tmp/g3-s3-bench/<scenario>"; exit 2 ;; esac
[ -d "$B/repo/tools/session" ] && [ -x "$B/stubs/ssh" ] && [ -x "$B/mod/stubs/ssh" ] || { echo "refused: $B is not a bench of bs3_setup.sh"; exit 2; }
grep -q 'BENCH STUB' "$B/repo/tools/session/guest_session_open.sh" || { echo "refused: the bench's session drivers are not the stubs"; exit 2; }
SCR=$(cd "$HERE/../../.." && pwd)      # the scratchpad: HERE is <scratchpad>/g3/s3prep/bench
PREP=$SCR/g3/s3prep
unset CTRL DITTO MQTT_PORT P TUNNEL_SOCK ACCEPT_UNACCOUNTED DEVICES EVENTS_EXPECTED BASH_ENV ENV \
    DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S READY_LIMIT_S EGW_G3_RUI_GO EGW_CLONE
export BENCH=$B
export HOME=$B/home
export EGW_EXEC=$B/egw-exec EGW_ATTEMPTS=$B/egw-exec/attempts EGW_OUTPUT_TEST=$B/out
export EGW_SECRETS_ENV=$B/home/egw-tcg/.env EGW_EXEC_REPO=$B/repo
export EGW_EXEC_VENV=$B/venv
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$B/repo/src
export EGW_YOCTO_CHECKOUT=$B/yocto/egw EGW_DATA_DISK=$B/data.img EGW_IMAGES_DIR=$B/images EGW_EVIDENCE_CANDIDATES=$B/ec
export EGW_G3_ROWS=${EGW_G3_ROWS:-$PREP/rows}
export EGW_G3_STATE=$B/state
export EGW_STUB_STATE=$B/mod/state EGW_REAL_SLEEP=/usr/bin/sleep EGW_REAL_TEE=/usr/bin/tee EGW_REAL_TIMEOUT=/usr/bin/timeout
export BENCH_FAST_DRAIN=${BENCH_FAST_DRAIN:-0} BENCH_SCALED=${BENCH_SCALED:-0}
export EGW_STUB_MS_PER_S=${EGW_STUB_MS_PER_S:-1000} EGW_STUB_TIMEOUT_MS_PER_S=${EGW_STUB_TIMEOUT_MS_PER_S:-1000}
if [ "$BENCH_SCALED" = 1 ]; then
    export PATH=$B/stubs:$B/mod/stubs:$BASE_PATH
else
    export PATH=$B/stubs:$B/mod/stubs-realtime:$BASE_PATH
fi
