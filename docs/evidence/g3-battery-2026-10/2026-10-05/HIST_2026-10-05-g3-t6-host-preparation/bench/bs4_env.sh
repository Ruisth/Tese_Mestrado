# Bench of the S4 operator script: the environment of one bench (sourced; B is the bench,
# HERE this folder). Adapted from S3b's bench/bs3b_env.sh: the bench root is
# /tmp/g3-s4-bench; EGW_G3_STATE and EGW_G3_ROWS are UNSET, so that the script under test,
# run in place, uses its own default state directory, $EGW_EXEC/g3-t6-s4 (inside the
# bench, read by the bench as BSTATE), and its own rows/ (<P>/rows); S3b's BENCH_FAST_DRAIN
# device is gone (line 1425 assigns the DRAIN_* carriers in front of harness_cmd, which a
# read-only variable would refuse): 'drained' runs its real 130 s quiet window.
# HOME and every EGW_* point inside the bench; the bench's stubs and the test module's
# stubs (without its sleep and timeout) are first on PATH; the execution venv's real python
# is used read-only through the bench venv (no bytecode is written).
case ${B:-} in /tmp/g3-s4-bench/_* | /tmp/g3-s4-bench/*/*) echo "refused: B must be /tmp/g3-s4-bench/<scenario>"; exit 2 ;; esac
case ${B:-} in /tmp/g3-s4-bench/?*) ;; *) echo "refused: B must be /tmp/g3-s4-bench/<scenario>"; exit 2 ;; esac
[ -d "$B/repo/tools/session" ] && [ -x "$B/stubs/ssh" ] && [ -x "$B/mod/stubs/ssh" ] || { echo "refused: $B is not a bench of bs4_setup.sh"; exit 2; }
grep -q 'BENCH STUB' "$B/repo/tools/session/guest_session_open.sh" || { echo "refused: the bench's session drivers are not the stubs"; exit 2; }
unset CTRL DITTO MQTT_PORT P TUNNEL_SOCK ACCEPT_UNACCOUNTED DEVICES EVENTS_EXPECTED BASH_ENV ENV \
    DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S READY_LIMIT_S EGW_G3_RUI_GO EGW_CLONE EGW_G3_STATE EGW_G3_ROWS \
    EGW_SCHEMA_DIR MOSQUITTO_SIMULATOR_PASSWORD
export BENCH=$B
export HOME=$B/home
export EGW_EXEC=$B/egw-exec EGW_ATTEMPTS=$B/egw-exec/attempts EGW_OUTPUT_TEST=$B/out
export EGW_SECRETS_ENV=$B/home/egw-tcg/.env EGW_EXEC_REPO=$B/repo
export EGW_EXEC_VENV=$B/venv
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$B/repo/src
export EGW_YOCTO_CHECKOUT=$B/yocto/egw EGW_DATA_DISK=$B/data.img EGW_IMAGES_DIR=$B/images EGW_EVIDENCE_CANDIDATES=$B/ec
BSTATE=$EGW_EXEC/g3-t6-s4
export EGW_STUB_STATE=$B/mod/state EGW_REAL_SLEEP=/usr/bin/sleep EGW_REAL_TEE=/usr/bin/tee EGW_REAL_TIMEOUT=/usr/bin/timeout
export PATH=$B/stubs:$B/mod/stubs-realtime:$BASE_PATH
