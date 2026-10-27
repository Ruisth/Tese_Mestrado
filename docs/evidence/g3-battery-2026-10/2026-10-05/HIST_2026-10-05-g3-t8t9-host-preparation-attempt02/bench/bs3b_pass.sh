#!/bin/bash
# Bench of the second opening of S3: one pass of every scenario and of the checker alone,
# as ONE invocation, so that 'before' and 'after' of the real trees fall within one run of
# the distribution. Launched detached; its own output is kept by the caller as
# record/pass.driver.txt.
# Usage (WSL): bs3b_pass.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REC=$HERE/record
U=/tmp/g3-s3b-bench/_untouched
echo "pass started $(date -u +%FT%TZ); host uptime $(cut -d' ' -f1 /proc/uptime) s; g3_battery.sh $(sha256sum "$HERE/../g3_battery.sh" | cut -d' ' -f1); s3b_preflight_exception.py $(sha256sum "$HERE/../s3b_preflight_exception.py" | cut -d' ' -f1)"
rm -rf "$U"
bash "$HERE/bs3b_untouched.sh" before "$U" > "$REC/untouched.before.console.txt" 2>&1; echo "untouched before exit=$?"
bash "$HERE/bs3b_validator.sh" > "$REC/validator.console.txt" 2>&1; echo "validator exit=$?"
bash "$HERE/bs3b_all.sh" e1 e2 e3 e4a e4b e4b2 e4c e5a e5b e6 e7a e7b
echo "bs3b_all exit=$?"
bash "$HERE/bs3b_untouched.sh" after "$U" > "$REC/untouched.after.console.txt" 2>&1; echo "untouched after exit=$?"
echo "pass ended $(date -u +%FT%TZ); g3_battery.sh $(sha256sum "$HERE/../g3_battery.sh" | cut -d' ' -f1); s3b_preflight_exception.py $(sha256sum "$HERE/../s3b_preflight_exception.py" | cut -d' ' -f1)"
