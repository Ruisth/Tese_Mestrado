# G3, session S3 second opening (tests 8 and 9): minimal preparation (sealed 2026-10-05T11:44:15Z)

Authority: output_test/decisions/2026-10-05_g3-s3b-exception-authorisation.md. This package authorises nothing
and is not a G3 result: the session starts only on Rui's «estou presente». The first preparation,
HIST_2026-10-05-g3-t8t9-host-preparation, is unchanged; its step files and manifest are reused (rows/, same bytes).

- g3_battery.sh sha256 42de225aedfd25fa0f4975276bf2880e146c2ad66a4624f811487ba61ea0f034 (the sealed S3 script with three changes:
  the expected root file system b48b010d..., a fresh state directory, the authorised exception for collector-duration;
  verification/diffs/).
- s3b_preflight_exception.py sha256 ab6ee3216f51919105ea8a6c67aa8d8dc2e5d1c1cd860ab3b64451072d6e7a95 (read-only checker).
- rows/rows.manifest.json sha256 678b92031e09213780bc3790be1473358746693fc1d86088891ff2697f340c5d.
- recheck-record/console.txt: outcome=checked (at 2026-10-05T11:17:25Z) - the clone, the helper, the root file system and the
  -q2 identifiers re-read (read-only).
- bench/ and verification/bench-notes.md: the focused cases of the exception against stubs.
