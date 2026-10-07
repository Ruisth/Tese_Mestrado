#!/bin/bash
# Dry run of the row files of G3 session S3: the one file that holds text no runbook test has
# executed (the prose-only step t9-exposure.sh), the carrier form of test 8's lines b to f
# (each sourced in a new shell WITHOUT the carrier T8 must refuse and call nothing; line f
# WITH T8=ok must start the smoke under its '-q2' id), and a self-test of g3_check_rows.sh
# in its blob mode on altered copies. ISOLATED: everything lives in a temporary directory
# /tmp/g3-s3-dry-rows.*; HOME of the steps and of the checker is inside it; EGW_EXEC_REPO
# points inside it (no clone is there: blob mode reads none); the steps run with stub 'ssh',
# 'scp', 'ss', 'python', 'timeout', 'sleep', 'curl', 'sudo' and 'docker' first on PATH and
# refuse to go on unless 'ssh' resolves to the stub; the checker runs with a stub 'git'
# first on PATH that records every call (none is expected). Nothing real is contacted: no
# guest, no ssh, no simulator, no harness, no clone. The temporary directory is removed at
# the end. The exit status is 0 only when every outcome was the expected one.
# Usage (WSL): bash g3_rows_dryrun.sh <rows directory> <path of g3_check_rows.sh> <runbook blob file>
set -u
USAGE='usage: g3_rows_dryrun.sh <rows directory> <g3_check_rows.sh> <runbook blob file>'
ROWS=$(cd "${1:?$USAGE}" && pwd) || exit 2
CHECK=${2:?$USAGE}
BLOB=${3:?$USAGE}
T=$(mktemp -d /tmp/g3-s3-dry-rows.XXXXXX) || exit 2
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/home/.ssh" "$T/bin" "$T/bin-check"
miss=0
unexpected() { echo "$*"; miss=$((miss + 1)); }

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
# every other command a row file could reach: it only says that it was called, and fails
for c in scp python timeout sleep curl sudo docker; do
    printf '%s\n' '#!/bin/bash' "printf 'STUB $c:'; printf ' [%s]' \"\$@\"; echo" 'exit 1' > "$T/bin/$c"
done
chmod +x "$T/bin"/*
cat > "$T/bin-check/git" <<'EOF'
#!/bin/bash
# stub git for the checker in blob mode: any call is recorded and fails
echo "git $*" >> "$G3_DRY_GIT_CALLS"
echo "STUB git: called (blob mode must not read a clone): $*" >&2
exit 99
EOF
chmod +x "$T/bin-check/git"

# the form of the steps script's hx call: one bash -c, stderr joined, set -v, the file sourced, stdin closed
step() { # step <file> [<bash text run before it>]
    env -i HOME="$T/home" PATH="$T/bin:/usr/bin:/bin" "$(command -v bash)" --norc --noprofile -c \
        "exec 2>&1; [ \"\$(command -v ssh)\" = '$T/bin/ssh' ] || { echo 'STOP: ssh is not the stub'; exit 99; }; ${2:-:}; set -v; . '$ROWS/$1'" < /dev/null
    echo "[step $1 ended with status $?]"
}
# stub helpers of the runbook's helper file: each says that it was called
HELPERS='P=$HOME/egw-tcg/itest; REC="echo CALLED: rec"; stop() { echo "STOP: $*"; return 1; }; for h in wait_ready drained metrics tunnel_down tunnel_up run_test; do eval "$h() { echo \"CALLED: $h \$*\"; }"; done'

echo "## test 8, lines b to f, each in a new shell WITHOUT the carrier (T8 empty): each must refuse with one STOP: line and call nothing"
for f in t8-b-wait-boot-id.sh t8-c-unaided.sh t8-d-tunnel.sh t8-e-state.sh t8-f-smoke.sh; do
    out=$(step "$f" "$HELPERS")
    stops=$(printf '%s\n' "$out" | grep -c '^STOP: test 8: ')
    calls=$(printf '%s\n' "$out" | grep -c '^CALLED: \|^STUB ')
    printf '%s\n' "$out" | grep '^STOP: \|^CALLED: \|^STUB \|^\[step ' | cut -c1-230
    if [ "$stops" = 1 ] && [ "$calls" = 0 ]; then echo "refused: $f printed one STOP: line and called no helper and no command"; else unexpected "NOT REFUSED: $f printed $stops STOP: line(s) and made $calls call(s)"; fi
done
echo
echo "## t8-f-smoke.sh WITH the carrier T8=ok (set before the file is sourced, as the steps script does) and a stub run_test"
out=$(step t8-f-smoke.sh "$HELPERS; T8=ok")
printf '%s\n' "$out"
printf '%s\n' "$out" | grep -qx 'CALLED: run_test itest-post-reboot-01-q2 42 --scenario smoke --duration 30' && ! printf '%s\n' "$out" | grep -q '^STOP: ' \
    && echo "started: run_test was called once with the smoke id itest-post-reboot-01-q2, and no STOP: was printed" || unexpected "NOT AS EXPECTED: t8-f-smoke.sh with T8=ok"
echo
echo "## t9-exposure.sh with stub ssh and ss"
out=$(step t9-exposure.sh)
printf '%s\n' "$out"
[ "$(printf '%s\n' "$out" | grep -cx 'root ssh exit=255\|ss exit=0\|docker ps exit=0')" = 3 ] \
    && echo "read: the three reads ran in order and each printed its exit status (255 from the stub's refusal of root, 0, 0)" || unexpected "NOT AS EXPECTED: t9-exposure.sh"
echo
echo "## self-test of the checker in blob mode: each altered copy must be refused"
export G3_DRY_GIT_CALLS="$T/git-calls"
: > "$G3_DRY_GIT_CALLS"
check() { # check <blob file> <rows directory>
    env -u EGW_G3_RUNBOOK_BLOB HOME="$T/home" EGW_EXEC_REPO="$T/home/egw-exec/repo" PATH="$T/bin-check:$PATH" bash "$CHECK" --blob "$1" "$2"
}
verdict() { # verdict <label> [<blob file>]: the checker on $T/rows must fail
    if out=$(check "${2:-$BLOB}" "$T/rows" 2>&1); then unexpected "NOT DETECTED: $1"; else echo "detected: $1 -> $(printf '%s\n' "$out" | grep -c '^FAIL') FAIL line(s), first: $(printf '%s\n' "$out" | grep -m1 '^FAIL' | cut -c1-200)"; fi
}
alter() { # alter <label> <file> <sed expression>
    rm -rf "$T/rows"; cp -r "$ROWS" "$T/rows"
    sed -i "$3" "$T/rows/$2"
    if cmp -s "$ROWS/$2" "$T/rows/$2"; then unexpected "NOT ALTERED (the expression changed nothing): $1"; return; fi
    verdict "$1"
}
alter "an id left without its suffix (t8-f-smoke.sh)" t8-f-smoke.sh 's/itest-post-reboot-01-q2/itest-post-reboot-01/'
alter "one of line c's 32 literals not substituted (t8-c-unaided.sh)" t8-c-unaided.sh 's/itest-reboot-q2\.containers\.post 2>/itest-reboot.containers.post 2>/'
alter "a changed character outside the ids (t8-b-wait-boot-id.sh: timeout 20 -> timeout 21)" t8-b-wait-boot-id.sh 's/timeout 20 ssh/timeout 21 ssh/'
alter "a comment line of line a removed (t8-a-reboot.sh)" t8-a-reboot.sh '2d'
alter "an id that must not change was changed (t9-de.sh)" t9-de.sh 's/metrics itest-acl-\$T before/metrics itest-acl-$T-q2 before/'
alter "a carriage return (t9-a.sh)" t9-a.sh '1s/$/\r/'
alter "a suffix added where no id stands (t9-c.sh)" t9-c.sh 's/--duration 10/--duration 10-q2/'
alter "an id of the battery in place of S3's (t9-b.sh: -q1)" t9-b.sh 's/--run-id itest-auth-wrongpw-q2/--run-id itest-auth-wrongpw-q1/'
alter "the exposure step's header naming the battery's commit (t9-exposure.sh)" t9-exposure.sh '3s/ at 8e49261 / at 80e833f /'
alter "the manifest naming session S2 for row t8 (rows.manifest.json)" rows.manifest.json '0,/"session": "S3"/s//"session": "S2"/'
rm -rf "$T/rows"; cp -r "$ROWS" "$T/rows"; printf '%s\n' ':' > "$T/rows/t8-b-return.sh"
verdict "a step file of the battery's names left in the directory (t8-b-return.sh)"
rm -rf "$T/rows"; cp -r "$ROWS" "$T/rows"
if check "$BLOB" "$T/rows" > /dev/null 2>&1; then echo "the unaltered copy passes"; else unexpected "THE UNALTERED COPY FAILS"; fi
verdict "a blob file that does not exist (the unaltered copy)" "$T/no-such-blob"
printf 'x\n' | cat "$BLOB" - > "$T/blob-plus-one-line"
verdict "a blob file with one line appended (the unaltered copy)" "$T/blob-plus-one-line"
calls=$(wc -l < "$G3_DRY_GIT_CALLS")
[ "$calls" = 0 ] && echo "git calls made by the checker in blob mode: 0 (no clone is read)" || unexpected "git calls made by the checker in blob mode: $calls (0 expected)"
echo
[ "$miss" = 0 ] && echo "DRY RUN AS EXPECTED (0 unexpected outcomes)" || echo "DRY RUN NOT AS EXPECTED ($miss unexpected outcome(s))"
[ "$miss" = 0 ]
