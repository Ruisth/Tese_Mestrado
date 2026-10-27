# G3 qualifying battery, session S1: operator records

state/: the steps script's state directory as it stood when this package was sealed (session and row state
files, one console per invocation, the frozen drivers' consoles, the environment copy record, the script and
manifest as opened). operator/: the operator's launcher and waiter (read-only helpers that start one
subcommand detached and wait for it), the sealing scripts, and the classification notes given to 'classify'
(one reason and one next-action file per row). The row, session, preflight and gate packages are beside this
one under the same date; the steps script, the row files and their verification are in
HIST_2026-10-02-g3-battery-host-preparation.

Sealing note: seal_ops.sh stopped before sealing, because its private-key sweep matched its own pattern text
in the copy of itself (operator/seal_ops.sh, line 25); no key is in the package. seal_ops_finish.sh repeated the
sweep with a pattern that does not match that text (0 files with a secret value, 0 with a private-key header)
and wrote this README and SHA256SUMS in place; nothing was copied again or replaced.
