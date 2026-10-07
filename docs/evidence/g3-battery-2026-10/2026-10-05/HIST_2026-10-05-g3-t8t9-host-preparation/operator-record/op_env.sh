# Stream OPERATOR: the environment of the isolated exercises (sourced; B is the bench).
# HOME and every EGW_* point inside the bench, the stubs are first on PATH, the real
# venv's python is used read-only (no bytecode is written).
case ${B:-} in /tmp/g3-s3-op-?*) ;; *) echo "refused: B must be /tmp/g3-s3-op-<name>"; exit 2 ;; esac
[ -d "$B/repo/tools/session" ] && [ -x "$B/stubs/ssh" ] || { echo "refused: $B is not a bench of op_setup.sh"; exit 2; }
S=$(cd "$HERE/../../.." && pwd)       # the scratchpad: HERE (set by the caller) is S/g3/s3prep/operator-record
SCR=$S                                # kept under a second name: the steps script, once loaded, uses S for the session
G=${G:-$S/g3/s3prep/g3_battery.sh}
export BENCH=$B
export HOME=$B/home
export EGW_EXEC=$B/egw-exec EGW_ATTEMPTS=$B/egw-exec/attempts EGW_OUTPUT_TEST=$B/out
export EGW_SECRETS_ENV=$B/home/egw-tcg/.env EGW_EXEC_REPO=$B/repo
export EGW_EXEC_VENV=/home/ruisth/egw-exec/venv
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$B/repo/src
export EGW_YOCTO_CHECKOUT=$B/yocto/egw EGW_DATA_DISK=$B/data.img EGW_IMAGES_DIR=$B/images EGW_EVIDENCE_CANDIDATES=$B/ec
export EGW_G3_ROWS=${EGW_G3_ROWS:-$S/g3/s3prep/rows}
export EGW_G3_STATE=$B/state
export PATH=$B/stubs:$PATH
