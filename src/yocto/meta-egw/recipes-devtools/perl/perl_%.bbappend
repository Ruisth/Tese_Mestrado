# perl_%.bbappend — make perl's build independent of host clock stability.
#
# WHY (observed 2026-08-11, first real builds on WSL2 Ubuntu 24.04):
# perl's do_compile failed three times, on three different CPAN modules
# (cpan/Pod-Escapes, cpan/JSON-PP, cpan/Time-Local), always with the same
# sequence:
#
#   make[2]: Warning: File 'Makefile.PL' has modification time 0.71 s in the future
#   Makefile out-of-date with respect to Makefile.PL
#   Cleaning current config before rebuilding Makefile...
#   ==> Your Makefile has been rebuilt. <==
#   ==> Please rerun the make command.  <==
#   false
#   make[2]: *** [Makefile:738: Makefile] Error 1
#
# ExtUtils::MakeMaker compares the mtime of each generated Makefile with its
# Makefile.PL. When the Makefile looks older, it regenerates it and then
# deliberately fails with "Please rerun the make command" — a protocol
# oe_runmake does not implement, so do_compile dies.
#
# The comparison is only wrong because the host clock is unstable: measured
# against the Windows host clock, the WSL2 clock moved -0.45 s -> +0.35 s ->
# +1.33 s over 40 seconds under build load, so files written moments earlier
# can carry timestamps in the future. This is a known WSL2 behaviour and it is
# NOT something the recipe should depend on. Note the first failure happened
# with PARALLEL_MAKE at the host default and the later ones with "-j 1", which
# rules out a parallel-make race as the cause.
#
# THE FIX: pin every Makefile.PL to a fixed timestamp in the past before the
# compile starts. Any Makefile generated during the build is then
# unambiguously newer, whatever the clock does, so the regeneration branch is
# never taken. This removes a dependency on host wall-clock behaviour, which
# makes the build MORE reproducible, not less (claim C01).
#
# The permanent host-side remedy is to keep the WSL2 clock synchronised (e.g.
# `sudo hwclock -s`, or enabling systemd-timesyncd); that requires privileges
# the build does not have, and the build should survive without it anyway.

do_compile:prepend() {
    # 2001-09-09T01:46:40Z — arbitrary fixed instant, safely in the past.
    find "${B}" -name 'Makefile.PL' -exec touch -d @1000000000 {} + 2>/dev/null || true
}
