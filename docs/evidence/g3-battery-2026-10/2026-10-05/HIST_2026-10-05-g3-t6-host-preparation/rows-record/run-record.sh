#!/bin/bash
# The record of stream ROWS of the preparation of G3 session S4 (test 6 only): the extraction
# into P/rows, its --check and its refusals, the checker in blob mode, the dry run, the
# proofs, the checker's clone mode against a THROW-AWAY clone (never the execution clone), the
# manifest against the steps script's own manifest tool, and static checks. Each console is
# saved beside this script. WSL only.
#
# Isolated: HOME and EGW_EXEC_REPO point inside a temporary directory /tmp/g3-s4-rows-record.*
# (removed at the end); a stub git that records every call stands first on PATH for the
# blob-mode check; python is the system python3 with PYTHONDONTWRITEBYTECODE=1. No guest, no
# QEMU, no docker, no ssh, no build.
# Reads: P (the three scripts, the runbook blob, the steps script and its base copy), the
#   worktree t6m (the test module, the rule's source), the battery's t6.sh (S/g3/battery) and
#   its sealed copies under output_test, the sealed row files of the battery and of S3 under
#   output_test, and, for the throw-away clone only, the object store of the Windows
#   repository (git clone -s: the source is not written).
# Writes: P/rows (the extraction), P/rows-record (the consoles, rows-files.sha256) and the
#   temporary directory.
# In the consoles three long paths are abbreviated by a filter, and nothing else is changed:
#   <S> the session scratchpad, <OT> output_test, <WINREPO> the Windows repository.
# Usage (WSL): bash run-record.sh
set -u
REC=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 2
P=$(dirname "$REC")
S=$(dirname "$(dirname "$P")")
BLOB=$P/runbook.1fd9792.md
RULE=$S/t6m/src/tests/test_runbook_itest_helpers.py
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
OLD_T6=$S/g3/battery/prep/rows/t6.sh
SEALED_BATTERY="$OT/runs/2026-10-02/HIST_2026-10-02-g3-battery-host-preparation/rows"
SEALED_S3="$OT/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-host-preparation-attempt02/rows"
S2_T6="$OT/runs/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01/environment/t6.sh"
# the Windows repository: the main repository of the worktree t6m, read from the worktree's .git file
WINREPO=$(wslpath -u "$(sed -n 's#^gitdir: \(.*\)/\.git/worktrees/t6m$#\1#p' "$S/t6m/.git")") || exit 2
[ -d "$WINREPO/.git" ] || { echo "the Windows repository was not found from $S/t6m/.git" >&2; exit 2; }
COMMIT=1fd9792bb76f02c6948f33887207dba4837202db
OLD_COMMIT=8e492613d36490a560ae56beabd6d5c2c01a8696
REAL_HOME=$(getent passwd "$(id -un)" | cut -d: -f6)
T=$(mktemp -d /tmp/g3-s4-rows-record.XXXXXX) || exit 2
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/home" "$T/stub"
export HOME=$T/home EGW_EXEC_REPO=$T/home/egw-exec/repo PYTHONDONTWRITEBYTECODE=1
unset EGW_G3_RUNBOOK_BLOB
cd "$T" || exit 2
sha() { sha256sum "$1" | cut -d' ' -f1; }
now() { date -u +%FT%TZ; }
short() { sed -e "s#$S#<S>#g" -e "s#$OT#<OT>#g" -e "s#$WINREPO#<WINREPO>#g"; }
ABBR="paths abbreviated by the record's filter: <S> the session scratchpad, <OT> output_test, <WINREPO> the Windows repository"
EX="python3 -B $P/g3_extract_rows.py"

# the real trees this record must leave untouched: their listing times before and after
real_times() {
    for p in "$REAL_HOME/egw-exec" "$REAL_HOME/egw-exec/repo" "$REAL_HOME/egw-exec/repo/.git" "$REAL_HOME/egw-exec/repo/.git/HEAD" \
             "$REAL_HOME/egw-exec/repo/.git/index" "$REAL_HOME/egw-exec/attempts" "$REAL_HOME/egw-tcg" "$REAL_HOME/egw-tcg/itest" \
             "$REAL_HOME/egw-tcg/pilot" "$REAL_HOME/egw-tcg/pilot/campaign_plan.json"; do
        stat -c '%y %n' "$p" 2>&1
    done
}
real_times > "$T/real-before.txt"

# --- A. the extraction -------------------------------------------------------------------------
{
    echo "## $(now) g3_extract_rows.py (sha256 $(sha "$P/g3_extract_rows.py")) --replace; $(python3 --version), bash $BASH_VERSION; HOME=$HOME"
    echo "## $ABBR"
    echo "## runbook blob $BLOB (sha256 $(sha "$BLOB")); rule source $RULE (sha256 $(sha "$RULE")); its copy $P/test_runbook_itest_helpers.1fd9792.py (sha256 $(sha "$P/test_runbook_itest_helpers.1fd9792.py"))"
    echo "## test 6's family value, computed apart from the script: sed -n '1421,1428p' | sed 's/^host\$ //' | sha256sum -> $(sed -n '1421,1428p' "$BLOB" | sed 's/^host\$ //' | sha256sum | cut -d' ' -f1) (the script pins its first 16 hex digits)"
    $EX --runbook "$BLOB" --rule-source "$RULE" --out "$P/rows" --replace
    echo "extract exit=$?"
    echo
    echo "## the same inputs again with --check (nothing written): what would be written against what is there"
    $EX --runbook "$BLOB" --rule-source "$RULE" --out "$P/rows" --check
    echo "check-mode exit=$?"
    echo
    echo "## the same with the rule source's copy in P"
    $EX --runbook "$BLOB" --rule-source "$P/test_runbook_itest_helpers.1fd9792.py" --out "$P/rows" --check
    echo "check-mode (the copy of the rule source) exit=$?"
    echo
    echo "## the runbook on stdin, without --rule-source, with --check"
    $EX --runbook - --out "$P/rows" --check < "$BLOB"
    echo "check-mode (no rule source) exit=$? (1 expected: the manifest then says the rule was not checked, so it differs)"
    echo
    echo "## a wrong blob is refused (the blob with one byte appended, on stdin)"
    { cat "$BLOB"; printf 'x'; } | $EX --runbook - --rule-source "$RULE" --out "$T/never" 2>&1
    echo "wrong-blob exit=$? (1 expected)"
    echo
    echo "## a wrong rule source is refused (the test module with one byte appended)"
    { cat "$RULE"; printf 'x'; } > "$T/rule-plus-one-byte.py"
    $EX --runbook "$BLOB" --rule-source "$T/rule-plus-one-byte.py" --out "$T/never" 2>&1
    echo "wrong-rule exit=$? (1 expected)"
    echo "  nothing was written by the two refusals: $([ -e "$T/never" ] && echo "$T/never EXISTS" || echo "$T/never does not exist")"
    echo
    echo "## forbidden output directories are refused before anything is written (made-up paths inside the temporary directory: the guard is by path component and under \$HOME)"
    for d in "$T/guard/egw-exec/repo/rows" "$T/guard/egw-tcg/itest/rows" "$T/guard/egw-images/x" "$T/guard/yocto/x" "$T/guard/output_test/x" \
             "$T/guard/ChatGPT/x" "$T/guard/cand/rows" "$T/guard/pb/rows" "$T/guard/t6m/rows" "$T/guard/t6int/rows" "$T/guard/g3/s3prep/rows" \
             "$T/guard/g3/s3bprep/rows" "$T/guard/g3/battery/prep/rows" "$HOME/egw-exec/rows"; do
        $EX --runbook "$BLOB" --rule-source "$RULE" --out "$d" --replace 2>&1
        echo "forbidden-out exit=$? (1 expected); $([ -e "$d" ] && echo "$d EXISTS" || echo "not created")"
    done
    echo
    echo "## directories that hold the row files of another commit (copies of the sealed rows of the battery, 80e833f, and of S3, 8e49261) are never overwritten, --replace or not"
    for pair in "battery|$SEALED_BATTERY" "s3|$SEALED_S3"; do
        name=${pair%%|*}; src=${pair#*|}
        mkdir -p "$T/old-$name" && cp -r "$src" "$T/old-$name/rows"
        before=$(cd "$T/old-$name/rows" && sha256sum * | sha256sum | cut -d' ' -f1)
        $EX --runbook "$BLOB" --rule-source "$RULE" --out "$T/old-$name/rows" --replace 2>&1
        echo "other-commit ($name, --replace) exit=$? (1 expected)"
        $EX --runbook "$BLOB" --rule-source "$RULE" --out "$T/old-$name/rows" 2>&1
        echo "other-commit ($name, no --replace) exit=$? (1 expected)"
        after=$(cd "$T/old-$name/rows" && sha256sum * | sha256sum | cut -d' ' -f1)
        echo "  the copy's $(ls -A "$T/old-$name/rows" | wc -l) files before and after: $before / $after ($([ "$before" = "$after" ] && echo unchanged || echo CHANGED))"
        echo "  --check against it writes nothing and reports the differences: $($EX --runbook "$BLOB" --rule-source "$RULE" --out "$T/old-$name/rows" --check | tail -n 1)"
    done
} 2>&1 | short > "$REC/rows-extract.console.txt"

# --- B. the checker, blob mode -----------------------------------------------------------------
printf '%s\n' '#!/bin/bash' 'echo "git $*" >> "$G3_REC_GIT_CALLS"' 'echo "STUB git: called: $*" >&2' 'exit 99' > "$T/stub/git"
chmod +x "$T/stub/git"
export G3_REC_GIT_CALLS=$T/git-calls
: > "$G3_REC_GIT_CALLS"
{
    echo "## $(now) g3_check_rows.sh (sha256 $(sha "$P/g3_check_rows.sh")) --blob $BLOB $P/rows"
    echo "## $ABBR"
    echo "## blob mode; HOME=$HOME, EGW_EXEC_REPO=$EGW_EXEC_REPO (no clone there), a stub git first on PATH that records every call"
    PATH="$T/stub:$PATH" bash "$P/g3_check_rows.sh" --blob "$BLOB" "$P/rows"
    echo "check exit=$?"
    echo "git calls recorded by the stub: $(wc -l < "$G3_REC_GIT_CALLS") (0 expected: blob mode reads no clone)"
    echo
    echo "## the same through the environment variable EGW_G3_RUNBOOK_BLOB (last line only)"
    EGW_G3_RUNBOOK_BLOB=$BLOB PATH="$T/stub:$PATH" bash "$P/g3_check_rows.sh" "$P/rows" | tail -n 1
    echo "check (environment variable) exit=${PIPESTATUS[0]}"
    echo
    echo "## usage errors: no rows directory; --blob without a file"
    bash "$P/g3_check_rows.sh"; echo "exit=$? (2 expected)"
    bash "$P/g3_check_rows.sh" --blob; echo "exit=$? (2 expected)"
} 2>&1 | short > "$REC/rows-check.console.txt"

# --- C. the dry run ----------------------------------------------------------------------------
{
    echo "## $(now) g3_rows_dryrun.sh (sha256 $(sha "$P/g3_rows_dryrun.sh")) with g3_check_rows.sh (sha256 $(sha "$P/g3_check_rows.sh")), the blob $BLOB and the battery's t6.sh $OLD_T6"
    echo "## $ABBR"
    bash "$P/g3_rows_dryrun.sh" "$P/rows" "$P/g3_check_rows.sh" "$BLOB" "$OLD_T6"
    echo "dryrun exit=$?"
    echo "left under /tmp by the dry run: $(ls -d /tmp/g3-s4-dry-rows.* 2> /dev/null | wc -l) directory(ies) (0 expected)"
} 2>&1 | short > "$REC/rows-dryrun.console.txt"

# --- D. the proofs -----------------------------------------------------------------------------
{
    echo "## $(now) rows-proofs.sh (sha256 $(sha "$REC/rows-proofs.sh")) $P/rows $OLD_T6 $BLOB <the sealed copies>"
    echo "## $ABBR"
    echo "## the sealed packages' own SHA256SUMS for the copies of t6.sh used:"
    (cd "$(dirname "$SEALED_BATTERY")" && grep -E ' \./rows/t6\.sh$' SHA256SUMS | sha256sum -c - 2>&1 | sed 's/^/  first preparation SHA256SUMS: /')
    (cd "$(dirname "$(dirname "$S2_T6")")" && grep -E '  environment/t6\.sh$' SHA256SUMS | sha256sum -c - 2>&1 | sed 's/^/  S2 attempt01 SHA256SUMS: /')
    bash "$REC/rows-proofs.sh" "$P/rows" "$OLD_T6" "$BLOB" "$SEALED_BATTERY/t6.sh" "$S2_T6"
    echo "proofs exit=$?"
} 2>&1 | short > "$REC/rows-proofs.console.txt"

# --- E. the checker, clone mode, against a throw-away clone ------------------------------------
{
    echo "## $(now) g3_check_rows.sh (sha256 $(sha "$P/g3_check_rows.sh")) in CLONE MODE against a THROW-AWAY clone"
    echo "## $ABBR"
    echo "## NOT the execution clone: $T/clone/repo, made here with 'git clone -s --no-checkout' from the Windows repository (objects borrowed, the source not written),"
    echo "## sparse (docs/setup and src/tests only), HEAD detached. It shows that the clone-mode path of the checker works; it shows nothing about ~/egw-exec/repo."
    mkdir -p "$T/clone"
    git -c safe.directory='*' clone -q -s --no-checkout "$WINREPO" "$T/clone/repo" 2>&1 | sed 's/^/  git clone: /'
    C=$T/clone/repo
    git -C "$C" sparse-checkout set docs/setup src/tests 2>&1 | sed 's/^/  git sparse-checkout: /'
    git -C "$C" checkout -q --detach "$COMMIT" 2>&1 | sed 's/^/  git checkout: /'
    echo "the throw-away clone: HEAD $(git -C "$C" rev-parse HEAD), tree $(git -C "$C" rev-parse 'HEAD^{tree}'), $(git -C "$C" status --porcelain | wc -l) porcelain line(s)"
    echo
    echo "## (i) the clone at $COMMIT and clean"
    EGW_EXEC_REPO=$C bash "$P/g3_check_rows.sh" "$P/rows"
    echo "clone-mode check exit=$? (0 expected)"
    echo
    echo "## (ii) the same clone with an untracked file: the final clone check must fail (the ok lines are left out)"
    : > "$C/untracked-file"
    EGW_EXEC_REPO=$C bash "$P/g3_check_rows.sh" "$P/rows" | grep -v '^ok '
    echo "clone-mode check (untracked file) exit=${PIPESTATUS[0]} (1 expected)"
    rm -f "$C/untracked-file"
    echo
    echo "## (iii) the clone at S3's commit $OLD_COMMIT (where the execution clone stands before the host preparation): clone mode cannot pass (the ok lines are left out)"
    git -C "$C" checkout -q --detach "$OLD_COMMIT" 2>&1 | sed 's/^/  git checkout: /'
    echo "the throw-away clone: HEAD $(git -C "$C" rev-parse HEAD)"
    EGW_EXEC_REPO=$C bash "$P/g3_check_rows.sh" "$P/rows" | grep -v '^ok '
    echo "clone-mode check (clone at 8e49261) exit=${PIPESTATUS[0]} (1 expected)"
    echo
    echo "## (iv) no clone at all (EGW_EXEC_REPO names a directory that does not exist): clone mode cannot pass"
    EGW_EXEC_REPO=$T/no-clone bash "$P/g3_check_rows.sh" "$P/rows" 2>&1 | grep -c '^FAIL' | sed 's/^/FAIL lines: /'
    EGW_EXEC_REPO=$T/no-clone bash "$P/g3_check_rows.sh" "$P/rows" > /dev/null 2>&1
    echo "clone-mode check (no clone) exit=$? (1 expected)"
    echo
    echo "## (v) the extraction script refuses S3's runbook (the blob of $OLD_COMMIT, read with git show from the throw-away clone, on stdin)"
    echo "the blob of 8e49261: sha256 $(git -C "$C" show "$OLD_COMMIT:docs/setup/qemu_integrated_gateway.md" | sha256sum | cut -d' ' -f1), $(git -C "$C" show "$OLD_COMMIT:docs/setup/qemu_integrated_gateway.md" | wc -l) lines"
    git -C "$C" show "$OLD_COMMIT:docs/setup/qemu_integrated_gateway.md" | $EX --runbook - --rule-source "$RULE" --out "$T/never" 2>&1
    echo "old-runbook exit=$? (1 expected); $([ -e "$T/never" ] && echo "$T/never EXISTS" || echo "nothing written")"
    echo
    echo "## (vi) the extraction's two inputs read with git show from the throw-away clone (the form for the host, once the execution clone is at the commit): --check against $P/rows"
    git -C "$C" show "$COMMIT:src/tests/test_runbook_itest_helpers.py" > "$T/rule.from-clone.py"
    git -C "$C" show "$COMMIT:docs/setup/qemu_integrated_gateway.md" | $EX --runbook - --rule-source "$T/rule.from-clone.py" --out "$P/rows" --check
    echo "check-mode (inputs from the clone) exit=$? (0 expected)"
} 2>&1 | short > "$REC/rows-check-clone-mode.console.txt"

# --- F. the manifest against the steps script's own manifest tool ------------------------------
{
    echo "## $(now) manifest-compat.py (sha256 $(sha "$REC/manifest-compat.py")); $(python3 --version)"
    echo "## $ABBR"
    echo "## the steps script copies are READ (their MANIFEST_PY text is run on the row files), never executed; g3_battery.sh is another stream's file and may still change: its sha256 at this reading is printed"
    python3 -B "$REC/manifest-compat.py" "$P/rows" "$P/base/g3_battery.sh" "$P/g3_battery.sh"
    echo "compat exit=$?"
} 2>&1 | short > "$REC/manifest-compat.console.txt"

# --- G. static checks, the files and the untouched trees ---------------------------------------
{
    echo "## $(now) static checks of the scripts and of the row files (bash $BASH_VERSION, $(python3 --version))"
    cd "$P" || exit 2
    for f in g3_extract_rows.py g3_check_rows.sh g3_rows_dryrun.sh rows-record/rows-proofs.sh rows-record/manifest-compat.py rows-record/run-record.sh rows/*; do
        cr=$(tr -cd '\r' < "$f" | wc -c)
        bom=$([ "$(head -c 3 "$f" | od -An -tx1 | tr -d ' ')" = efbbbf ] && echo yes || echo no)
        utf=$(iconv -f UTF-8 -t UTF-8 "$f" > /dev/null 2>&1 && echo valid || echo INVALID)
        nl=$([ ! -s "$f" ] && echo "empty" || { [ "$(tail -c 1 "$f" | od -An -tx1 | tr -d ' ')" = 0a ] && echo "final newline" || echo "NO final newline"; })
        case $f in
            *.py) syn=$(python3 -B -c 'import ast, sys; ast.parse(open(sys.argv[1], encoding="utf-8").read()); print("python syntax ok")' "$f" 2>&1 | tail -n 1) ;;
            *.sh) syn=$(bash -n "$f" 2>&1 && echo "bash -n ok") ;;
            *) syn="-" ;;
        esac
        printf '%-34s CR bytes %s; BOM %s; UTF-8 %s; %s; %s\n' "$f" "$cr" "$bom" "$utf" "$nl" "$syn"
    done
    echo
    echo "## the three scripts against the untouched copies of P/base (git diff --no-index --numstat: added, removed; diff -u line count)"
    for f in g3_extract_rows.py g3_check_rows.sh g3_rows_dryrun.sh; do
        echo "$f: base $(sha "base/$f") ($(wc -l < "base/$f") lines) -> $(sha "$f") ($(wc -l < "$f") lines); numstat $(git diff --no-index --numstat "base/$f" "$f" | cut -f1,2 | tr '\t' ' '); diff -u $(diff -u "base/$f" "$f" | wc -l) lines"
    done
} 2>&1 | short > "$REC/rows-static.console.txt"
(cd "$P" && sha256sum g3_extract_rows.py g3_check_rows.sh g3_rows_dryrun.sh rows/* rows-record/rows-proofs.sh rows-record/manifest-compat.py rows-record/run-record.sh) > "$REC/rows-files.sha256"
real_times > "$T/real-after.txt"
{
    echo "## $(now) the real trees of the execution host: listing times before and after this record (stat only; nothing here names them otherwise)"
    echo "## before"
    cat "$T/real-before.txt"
    echo "## after"
    cat "$T/real-after.txt"
    cmp -s "$T/real-before.txt" "$T/real-after.txt" && echo "UNCHANGED: the two listings are identical" || echo "CHANGED: the two listings differ"
    echo "## no process is started in the background by this record; /tmp/g3-s4-* directories now (this record's own is removed when it ends):"
    ls -d /tmp/g3-s4-* 2>&1
} 2>&1 | short > "$REC/rows-untouched.console.txt"
echo "record written: $(ls "$REC" | tr '\n' ' ')"
grep -h 'exit=[0-9]' "$REC"/*.console.txt
