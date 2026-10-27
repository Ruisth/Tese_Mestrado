"""Item 4: every preserved 'drained' step and what its own console line says.

Read-only. For each attempt under /home/ruisth/egw-exec/attempts (the historical
folder excluded), every commands.jsonl entry whose command text calls 'drained'
is printed with its duration and exit code, and the one 'drained:' line of its
console record, from which the mean time of one reading is derived:

    a quiet window of n readings spans (n - 1) loop turns, each one reading
    ('_mline': one curl of GET /metrics through the tunnel plus one python3
    parse on the host) and one 'sleep 5' (DRAIN_STEP_S default, runbook :654),
    so   mean reading time = span_s / (n - 1) - 5.

Also prints every step whose command runs a Mosquitto client (mosquitto_pub,
mosquitto_sub) or the ACL probe inside the guest, with its duration, as the only
preserved timings of a broker-side client call under TCG.
Run: ~/egw-exec/venv/bin/python item4_drain_timings.py
"""
import json
import pathlib
import re

ROOT = pathlib.Path("/home/ruisth/egw-exec/attempts")
LINE = re.compile(r"^drained: queue_depth 0 and identical counters on (\d+) consecutive readings over (\d+) s \((.*)\)")

for attempt in sorted(p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("_")):
    cj = attempt / "commands.jsonl"
    if not cj.is_file():
        continue
    for lineno, raw in enumerate(cj.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        rec = json.loads(raw)
        text = " ".join(rec.get("argv") or [])
        last = text.split("\n", 1)[-1]
        # 'drained' directly, or through 'pre'/'finish'/'post'/'run_test' (runbook :788, :804, :815, :841)
        calls_drained = re.search(r"(^|[\s;&|(])(drained|pre|finish|post|run_test)($|[\s;&|)])", last) is not None
        calls_broker_client = any(k in text for k in ("mosquitto_sub", "mosquitto_pub", "probe-acl.sh"))
        if not (calls_drained or calls_broker_client):
            continue
        tag = "DRAINED" if calls_drained else "BROKER-CLIENT"
        print(f"{tag} {attempt.name}/commands.jsonl:{lineno} seq={rec.get('seq')} name={rec.get('name')} "
              f"started={rec.get('started_utc')} duration_s={rec.get('duration_s')} exit={rec.get('exit_code')}")
        if not calls_drained:
            continue
        for key in ("stdout", "stderr"):
            rel = rec.get(key)
            if not rel:
                continue
            f = attempt / rel
            if not f.is_file():
                continue
            for n, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                m = LINE.match(ln)
                if m:
                    readings, span = int(m.group(1)), int(m.group(2))
                    # 'span' is bash $SECONDS arithmetic (whole seconds, runbook :662-663): the true span
                    # lies in (span - 1, span + 1), so the mean reading time is bounded, not measured.
                    lo = max(0.0, (span - 1) / (readings - 1) - 5) if readings > 1 else float("nan")
                    hi = (span + 1) / (readings - 1) - 5 if readings > 1 else float("nan")
                    print(f"    {rel}:{n} readings={readings} span_s={span} last_reading=({m.group(3)}) "
                          f"-> mean reading time in [{lo:.3f}, {hi:.3f}] s "
                          f"(({span}-1)/({readings}-1)-5 .. ({span}+1)/({readings}-1)-5)")
                elif ln.startswith("STOP: drained"):
                    print(f"    {rel}:{n} {ln[:200]}")
