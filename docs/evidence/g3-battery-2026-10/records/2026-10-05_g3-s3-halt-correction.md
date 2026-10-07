# G3 session S3 — correction of the halt's explanation and of one statement (2026-10-05)

Corrects two statements of `2026-10-05_g3-t8-t9-results.md`, after the Project Manager's review (register entry
"2026-10-05 12:09 WEST"). The packages and their verdicts are unchanged: the preflight attempt
`20261005T105656Z_live-preflight_attempt11` stays failed, instrumentation invalid, outcome inconclusive, under the
frozen rule.

## 1. The collector is not shown to have stopped early

The results note quoted the check's own text ("the collector stopped 2 s before the duration=45s") as the cause. What
the records show is a difference of clock basis, not an early stop:

- `tools/session/collector_check.py` at `8e49261` (lines 382-386) measures the window from the collector's UTC
  `start:` and `stop:` stamps: 11:00:39Z to 11:01:22Z, 43 s.
- `src/deployment/scripts/collect-resources.sh` at `8e49261` (lines 1130-1131, 1291-1293) runs its 45 s duration on
  `/proc/uptime` (`started_cs`, `UP_CS`).
- The collector's own calibration lines (`analysis/collector/…csv.diagnostics.log`, lines 3 and 11) record wall
  second 1791198040 at uptime 268.54 s and wall second 1791198078 at uptime 309.23 s: 38 s of UTC against 40.69 s of
  uptime in the same interval. The two clocks did not advance together on the guest.

The monotonic start and stop values were not exported, so neither a full 45 s run nor a 2 s early stop is measured by
this package. The 2.29 s of withheld samples are not added to the UTC window to make up a duration.

## 2. The next opening does not read the new root file system value by itself

The results note said that the root file system value and the attempt numbering "are re-read at any next open". That
is wrong for the root file system: the sealed operator script fixes `ROOTFS_BEFORE_S3` at `22e9da85…` (line 88), uses
it directly at open (lines 958-963), and refuses an existing `session-S3.env` (line 928). A further session needs a
new copy of the operator script with the verified post-close value
`b48b010d571689ae03d610175fd1b127f6ef6b30f78b25448e6f32a3096de093` and a fresh state directory, the old one kept. The
attempt numbering is read at run time by the export tool, as stated.
