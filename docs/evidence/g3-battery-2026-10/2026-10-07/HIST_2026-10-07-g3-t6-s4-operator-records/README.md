# G3, session S4 (test 6 only): operator records (sealed 2026-10-07T12:35:55Z)

state/: the steps script's state directory as it stood when this package was sealed (session and row state
files, one console per invocation, the frozen drivers' consoles, the environment copy record, the script and
manifest as opened). operator/: the operator's launcher and waiter (read-only helpers that start one
subcommand detached and wait for it), this sealing script, and the classification notes given to 'classify'
(none here: there was no notes directory when this package was sealed).
The session, preflight, gate and row packages are under output_test/runs/, each under its own UTC date;
state/session-S4.env and state/row-*.env name them. Nothing here is a G3 result.

The steps script, the row file and their verification are in HIST_2026-10-05-g3-t6-host-preparation
(its SHA256SUMS: sha256 34715555f87e7ad3e8f48fe7cc847425b08c65276c82994dd4ea2dd065baafd4).
- steps script as opened (state/S4-g3_battery.sh): sha256 7a63b361af2f25bd8ab81101ca10ec79fcb05a6e6f0cf0a70bc2ec63f3f8425c, equal to the preparation package's
- manifest as opened (state/S4-rows.manifest.json): sha256 7d2a0f0d940c1d2f978a33693869fe4372cf7c63c4592d3d911d1440bdb8fb47, equal to the preparation package's
