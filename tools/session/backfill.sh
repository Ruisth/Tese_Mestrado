#!/bin/bash
# Work order 2.B item 11: copy the preserved earlier iterations into
# output_test as HISTORICAL packages, without rerunning, modifying their seals
# or upgrading their validity. Each keeps its original identity (path).
#
# Nothing is run here, so there is no test verdict to report and this driver
# owns no attempt: it ends through driver_stop, which prints the same final
# line as every other driver with no run id and the three verdicts unknown. It
# exits 0 when every capsule reached output_test as a verified package, 4 when
# any backfill failed, and 130 when it was interrupted with none of the
# capsules already done having failed (README.md, "Exit statuses": 4 > 130);
# each capsule is exported by the export tool as it is copied, so an interrupt
# leaves the capsules already done exported.
set -u
. "$(dirname "$0")/common.sh"
EC=/home/ruisth/yocto/evidence-candidates
RAW=/home/ruisth/egw-tcg/pilot/results/raw
fails=0

# interrupted: the INT/TERM handler. A capsule that did not reach output_test
# as a verified package is not withdrawn by the signal that stopped the rest,
# and it is the more serious of the two facts (README.md: 4 > 130), so the
# interrupt is reported through that precedence and never as a plain 130.
interrupted() {
    [ "$fails" -eq 0 ] || driver_stop "$EXIT_EXPORT" \
        "interrupted; $fails capsule(s) did not reach output_test as a verified package, and the remaining ones were not backfilled"
    driver_stop "$EXIT_INTERRUPTED" "interrupted: the remaining capsules were not backfilled"
}
trap interrupted INT TERM

bf() {  # bf SOURCE NAME SCENARIO DATE VALIDITY OUTCOME NOTE
    (cd "$REPO/src" && $LE backfill --source "$1" --attempts-root "$ATTEMPTS" --dest-root "$OUT" \
        --secrets-env "$SECRETS_ENV" --name "$2" --scenario "$3" --date "$4" --validity "$5" \
        --outcome "$6" --note "$7") || fails=$((fails + 1))
}

bf "$EC/2026-09-18-integrated-68f9ae7" "2026-09-18-integrated-68f9ae7" "yocto build (integrated profile)" 2026-09-18 \
    unknown fail "candidate capsule; failed build (sudoers conflict); sealed locally (SHA256SUMS); not admitted"
bf "$EC/2026-09-18-integrated-03e333e" "2026-09-18-integrated-03e333e" "yocto build (integrated profile)" 2026-09-18 \
    unknown unknown "candidate capsule; the build that produced the image in use; boot-01 failed before QEMU; sealed locally; not admitted"
bf "$EC/2026-09-18-integrated-3209b17" "2026-09-18-integrated-3209b17" "guest boot (integrated profile)" 2026-09-18 \
    unknown unknown "candidate capsule; no-op rebuild and boots 02/03; sealed locally; not admitted (published counterpart under docs/evidence/integrated-qemu)"
bf "$EC/2026-09-18-mongodb7-isolated-3209b17" "2026-09-18-mongodb7-isolated-3209b17" "mongodb 7 isolated test" 2026-09-18 \
    unknown unknown "candidate capsule; sealed locally; not admitted (published counterpart under docs/evidence/integrated-qemu)"
bf "$EC/2026-09-18-stack-images-provisioning" "2026-09-18-stack-images-provisioning" "stack image provisioning" 2026-09-18 \
    unknown unknown "candidate capsule; image identities; sealed locally; not admitted"
bf "$EC/2026-09-18-first-flow" "2026-09-18-first-flow" "first end-to-end flow (smartwatch)" 2026-09-18 \
    unknown unknown "locally hash-sealed candidate (51 entries), outside the published evidence package, not admitted; itest-flow-01 failed (simulator exit 1), itest-flow-02 60/60"
bf "$EC/2026-09-18-integration-tests" "2026-09-18-integration-tests" "nine integration/recovery families (battery)" 2026-09-18 \
    unknown unknown "locally hash-sealed candidate archive (312 entries), not admitted; battery not complete: T5 fails its deadline, T4 sequence reset and T7 Ditto repeat not run, T1/T6 harness runs invalid; its README's 'seven passed' is superseded"
bf "$EC/2026-09-19-sampler-fix" "2026-09-19-sampler-fix" "acceptance session sampler-01 (unclosed)" 2026-09-19 \
    unknown interrupted "unsealed candidate; session never closed (no status, no journal); acceptance paused mid-run"
bf "$EC/2026-09-19-collector-pr37" "2026-09-19-collector-pr37" "collector capsule (host, busybox under qemu-user)" 2026-09-19 \
    not-applicable pass "local capsule for commit 29afa92: 234 tests passed and a 720-sample long run on synthetic cgroup files; not the guest"
bf "$RAW/smoke_sequence-r01" "smoke_sequence-r01" "harness smoke_sequence" 2026-09-18 \
    invalid unknown "INVALID: resources.csv rejected (7 distinct instants); no sut_environment.json; unsealed by the harness"
bf "$RAW/smoke_sequence-r02" "smoke_sequence-r02" "harness smoke_sequence" 2026-09-19 \
    invalid unknown "INVALID: resources.csv rejected (25 distinct instants < 30); unsealed by the harness; interim collector f17bdd8c"
bf "$RAW/controller_restart-r01" "controller_restart-r01" "harness controller_restart" 2026-09-18 \
    invalid fail "INVALID: resource gaps and 29 failed /metrics polls; unsealed; restart queue loss diagnosed later"
bf "$RAW/controller_restart-r02" "controller_restart-r02" "harness controller_restart" 2026-09-19 \
    invalid fail "INVALID: one 6 s resource gap; unsealed; 2,136 internal identity gaps (diagnosed: 1,810 discarded from the volatile queue, 195 never delivered, 131 undetermined; assumption-qualified)"
bf /home/ruisth/egw-tcg/itest "egw-tcg-itest-host-dir-2026-09-19" "ad-hoc integration runs (host dir)" 2026-09-19 \
    unknown unknown "the live host directory of ad-hoc integration runs and their sibling files as of 2026-09-19; mostly also inside the first-flow and integration-tests capsules"
bf /home/ruisth/egw-tcg/itest-replay "egw-tcg-itest-replay-2026-09-18" "test 4 replay (itest-dup-01)" 2026-09-18 \
    unknown unknown "replay output of test 4 (itest-dup-01); not in any capsule"
echo "backfill failures: $fails"
[ "$fails" -eq 0 ] || driver_stop "$EXIT_EXPORT" "$fails capsule(s) did not reach output_test as a verified package"
driver_stop "$EXIT_PASS" "every capsule reached output_test as a verified package"
