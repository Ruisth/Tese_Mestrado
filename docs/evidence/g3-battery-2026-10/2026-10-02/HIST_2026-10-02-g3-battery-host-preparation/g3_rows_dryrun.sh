#!/bin/bash
# Dry run of the row files that hold text no runbook test has executed (the two prose-only
# steps and the '$i-q1' form of the smokes), and a self-test of g3_check_rows.sh on altered
# copies. ISOLATED: HOME is a temporary directory under /tmp/g3-dry-rowsA.*, PATH holds stub
# 'ssh', 'ss' and 'python' first, and the script refuses to go on unless 'ssh' resolves to the
# stub. Nothing real is contacted: no guest, no ssh, no simulator, no harness. The clone is
# only read (git show, by the checker). The temporary directory is removed at the end.
# Usage (WSL): bash g3_rows_dryrun.sh <rows directory> <path of g3_check_rows.sh>
set -u
ROWS=$(cd "${1:?usage: g3_rows_dryrun.sh <rows directory> <g3_check_rows.sh>}" && pwd)
CHECK=${2:?usage: g3_rows_dryrun.sh <rows directory> <g3_check_rows.sh>}
REAL_HOME=$HOME
T=$(mktemp -d /tmp/g3-dry-rowsA.XXXXXX) || exit 2
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/home/egw-tcg/pilot/results/processed" "$T/bin" "$T/home/.ssh"

cat > "$T/bin/ssh" <<'EOF'
#!/bin/bash
# stub ssh: prints its arguments; root is refused, egw-tcg answers a fixed docker ps listing
printf 'STUB ssh argc=%s:' "$#"; printf ' [%s]' "$@"; echo
[ -t 0 ] && echo "STUB ssh: stdin is a terminal" || echo "STUB ssh: stdin is not a terminal"
case " $* " in
    *" root@127.0.0.1 "*) echo "root@127.0.0.1: Permission denied (publickey,password)." >&2; exit 255 ;;
    *" egw-tcg "*) echo "egw-controller-1 127.0.0.1:8000->8000/tcp"; echo "egw-mongodb-1 "; exit 0 ;;
esac
exit 1
EOF
cat > "$T/bin/ss" <<'EOF'
#!/bin/bash
printf 'STUB ss:'; printf ' [%s]' "$@"; echo
EOF
cat > "$T/bin/python" <<'EOF'
#!/bin/bash
printf 'STUB python:'; printf ' [%s]' "$@"; echo
EOF
chmod +x "$T/bin/ssh" "$T/bin/ss" "$T/bin/python"
printf '%s\n' 'run_id,condition_id,confirmation_deadline_source,sent_valid,delivered_unique,lost,late_confirmations,double_accepted' \
    'nominal-r01,nominal,controller-marker,6720,3794,2926,2926,0' \
    'nominal-r02,nominal,controller-marker,6720,6700,20,20,0' > "$T/home/egw-tcg/pilot/results/processed/per_run.csv"

# the form of the steps script's hx call: one bash -c, stderr joined, set -v, the file sourced, stdin closed
step() { # step <file> [<bash text run before it>]
    env -i HOME="$T/home" PATH="$T/bin:/usr/bin:/bin" "$(command -v bash)" --norc --noprofile -c \
        "exec 2>&1; [ \"\$(command -v ssh)\" = '$T/bin/ssh' ] || { echo 'STOP: ssh is not the stub'; exit 99; }; ${2:-:}; set -v; . '$ROWS/$1'" < /dev/null
    echo "[step $1 ended with status $?]"
}

echo "## t1-smokes.sh with stub run_test (the second repetition fails) and stub stop"
step t1-smokes.sh 'run_test() { echo "run_test: $*"; [ "$1" != itest-smoke-02-q1 ]; }; stop() { echo "STOP: $*"; return 1; }'
echo
echo "## t1-harness-analyze.sh with a stub python (analyze) and a made-up per_run.csv of two rows"
step t1-harness-analyze.sh
echo
echo "## t1-harness-analyze.sh when per_run.csv has no row of nominal-r02"
sed -i '/^nominal-r02,/d' "$T/home/egw-tcg/pilot/results/processed/per_run.csv"
step t1-harness-analyze.sh | grep -v '^#\|^import\|^path\|^cols\|^with\|^    \|^for\|^sys\|^EOF'
echo
echo "## t9-exposure.sh with stub ssh and ss"
step t9-exposure.sh
echo
echo "## self-test of the checker: each altered copy must be refused"
export HOME=$REAL_HOME
alter() { # alter <label> <file> <sed expression>
    rm -rf "$T/rows"; cp -r "$ROWS" "$T/rows"
    sed -i "$3" "$T/rows/$2"
    if out=$(bash "$CHECK" "$T/rows" 2>&1); then echo "NOT DETECTED: $1"; else echo "detected: $1 -> $(printf '%s\n' "$out" | grep -c '^FAIL') FAIL line(s), first: $(printf '%s\n' "$out" | grep -m1 '^FAIL')"; fi
}
alter "an id left without its suffix (t4-reset.sh)" t4-reset.sh 's/itest-dup-02-q1/itest-dup-02/'
alter "one of T8's five literals not substituted (t8-c-snapshot.sh)" t8-c-snapshot.sh 's/itest-reboot-q1 --label/itest-reboot --label/'
alter "a changed character outside the ids (t6.sh: 300 -> 301)" t6.sh 's/--restart-at-s 300/--restart-at-s 301/'
alter "an id that must not change was changed (t1-harness.sh)" t1-harness.sh 's/RID=nominal-r02/RID=nominal-r02-q1/'
alter "a carriage return (t5.sh)" t5.sh '1s/$/\r/'
alter "a suffix added where no id stands (t2.sh)" t2.sh 's/--duration 60/--duration 60-q1/'
rm -rf "$T/rows"; cp -r "$ROWS" "$T/rows"
if bash "$CHECK" "$T/rows" > /dev/null 2>&1; then echo "the unaltered copy passes"; else echo "THE UNALTERED COPY FAILS"; fi
