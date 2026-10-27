# G3, session S3 (tests 8 and 9): operator records (sealed 2026-10-05T12:13:28Z)

state/: the steps script's state directory as it stood when this package was sealed (session and row state
files, one console per invocation, the frozen drivers' consoles, the environment copy record, the script and
manifest as opened). operator/: the operator's launcher and waiter (read-only helpers that start one
subcommand detached and wait for it), this sealing script, and the classification notes given to 'classify'
(one reason and one next-action file per classified row).
The session, preflight, gate and row packages are under output_test/runs/, each under its own UTC date;
state/session-S3.env and state/row-*.env name them. Nothing here is a G3 result.

The steps script, the row files and their verification are in HIST_2026-10-05-g3-t8t9-host-preparation-attempt02
(its SHA256SUMS: sha256 cdcd92841279d0a15fa66e4de13124d69e2c1bb153edf14407ee8e9e4dd764b2).
- steps script as opened (state/S3-g3_battery.sh): sha256 42de225aedfd25fa0f4975276bf2880e146c2ad66a4624f811487ba61ea0f034, equal to the preparation package's
- manifest as opened (state/S3-rows.manifest.json): sha256 678b92031e09213780bc3790be1473358746693fc1d86088891ff2697f340c5d, equal to the preparation package's
