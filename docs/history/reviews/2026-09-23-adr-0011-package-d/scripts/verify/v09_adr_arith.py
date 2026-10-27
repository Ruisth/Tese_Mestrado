"""v09 - ADR 0011 arithmetic: S.1 cost table, S.2 drain times, P.1-P.3 proof timing, N.6, W range,
and the probe sizing of backlog_diagnosis.md section 11 (s07). Inputs are figures re-derived in v02/v03/v08.
Read-only; prints only.
"""
from vc import hdr

warm, win, drain = 4.939732, 6.457048, 8.863682          # v02 C
lowest60, lowest30, lowest10 = 4.6000, 38.3333 / 10, 3.0  # v02 D
hdr("S.1 cost table: r' = 1/(1/r + x)")
for x in (0.001, 0.010, 0.050):
    out = []
    for r in (warm, win, drain):
        rp = 1 / (1 / r + x)
        out.append("%.3f->%.3f (%+.2f %%)" % (r, rp, 100 * (rp / r - 1)))
    print("x=%2d ms: " % (x * 1000) + " ; ".join(out))
print("with the lowest 60 s block (%.2f): x=1/10/50 ms -> %s" % (lowest60, ["%+.2f %%" % (100 * (1 / (1 + lowest60 * x) - 1)) for x in (0.001, 0.01, 0.05)]))

hdr("S.2 drain times of the queued backlog at nominal-r01 phase rates (other run)")
for qd in (1867, 1487):
    print("%d: drain %.1f s ; window %.1f s ; warm %.1f s ; lowest 60 s %.1f s ; lowest 30 s %.1f s" % (
        qd, qd / drain, qd / win, qd / warm, qd / lowest60, qd / lowest30))
print("r02's own old-process rates (v08): under ingress 5.0510 msg/s -> %.0f s ; after the last poll 5.476 msg/s -> %.0f s" % (1867 / 5.0510, 1867 / 5.476))
print("r01's own: 6.3197 -> %.0f s for 1487 ; after the last poll 7.748 -> %.0f s" % (1487 / 6.3197, 1487 / 7.748))

hdr("P.1-P.3 proof timing")
print("P.1 300 s x 11.2 = %.0f" % (300 * 11.2))
for qw in (130, 490):
    t = qw + 300 + 405.4 + qw
    print("P.2 quiet %d: %.1f s = %.1f min ; adding the harness's 60 s confirmation wait: %.1f min" % (qw, t, t / 60, (t + 60) / 60))
print("P.3 900+300+900 = %d s = %.1f min ; + 60 s confirmation wait = %.1f min ; + restart command ~21-23 s (r01 22.704 s, r02 20.790 s)" % (
    2100, 35.0, 2160 / 60))

hdr("W range: 2W <= 9,999 -> W <= %d ; 3,593 inside the controller -> 3,593 <= W <= 4,999: %s" % (9999 // 2, 3593 <= 4999))

hdr("Diagnosis 11.2 probe sizing")
R = 2.24
print("per device 1:0.2:10 of %.2f -> watch %.3f ring %.3f clothing %.3f" % (R, R * 1 / 11.2, R * 0.2 / 11.2, R * 10 / 11.2))
print("messages in 720 s: %.1f + %.1f + %.1f = %.1f" % (720 * R * 1 / 11.2, 720 * R * 0.2 / 11.2, 720 * R * 10 / 11.2, 720 * R))
print("ratios: /4.60 %.3f ; /3.8333 %.3f ; /3.0 %.3f" % (R / 4.6, R / (115 / 30), R / 3.0))
print("service at 4.60 for 1612.8: %.1f s ; at 3.0 (lowest 10 s): %.1f s" % (1612.8 / 4.6, 1612.8 / 3.0))
print("3/720 = %.5f msg/s" % (3 / 720))
print("expected: 133+720+60+135 = %d s = %.1f min ; with 490: %d s = %.1f min" % (133 + 720 + 60 + 135, (133 + 720 + 60 + 135) / 60,
                                                                             133 + 720 + 60 + 495, (133 + 720 + 60 + 495) / 60))
print("'hard bound' 900+720+60+900 = %d s = %.1f min ; with wait's --extra-timeout default 120 s and wait_ready 60 s: %d s = %.1f min" % (
    2580, 2580 / 60, 2580 + 120 + 60, (2580 + 180) / 60))
# expected queue at low load under the probe: worst own passage observed 2.542 s
print("messages arriving during one 2.542 s passage at 2.24 msg/s: %.1f ; at the clothing device's 2 Hz alone: %.1f" % (2.542 * 2.24, 2.542 * 2.0))
