"""Stream OPERATOR: which functions of g3_battery.sh differ from the draft (base/), read only.

Usage: python op_fndiff.py <base/g3_battery.sh> <g3_battery.sh>
A function is the text from a line 'name() {' at column 0 to the next line that is '}'
alone (one-line functions 'name() { ...; }' are taken whole). Prints, for every function
of either file, whether its text is identical, changed (with the number of differing
lines), only in the base or only in the new file.
"""
import difflib
import hashlib
import re
import sys

HEAD = re.compile(rb"^([A-Za-z_][A-Za-z0-9_]*)\(\) \{")


def functions(path):
    out, name, body = {}, None, []
    for line in open(path, "rb").read().split(b"\n"):
        if name is None:
            m = HEAD.match(line)
            if m:
                name, body = m.group(1).decode(), [line]
                if line.rstrip().endswith(b"}"):
                    out[name], name = body, None
        else:
            body.append(line)
            if line == b"}":
                out[name], name = body, None
    return out


def main():
    base, new = functions(sys.argv[1]), functions(sys.argv[2])
    for label, path in (("base", sys.argv[1]), ("new", sys.argv[2])):
        print("%s: sha256 %s" % (label, hashlib.sha256(open(path, "rb").read()).hexdigest()))
    same = []
    for name in sorted(set(base) | set(new)):
        if name not in new:
            print("only in the base : %s" % name)
        elif name not in base:
            print("only in the new  : %s (%d lines)" % (name, len(new[name])))
        elif base[name] == new[name]:
            same.append(name)
        else:
            a = [x.decode("utf-8") for x in base[name]]
            b = [x.decode("utf-8") for x in new[name]]
            d = [x for x in difflib.unified_diff(a, b, lineterm="", n=0) if x[:1] in "+-" and x[:3] not in ("+++", "---")]
            print("changed          : %s (-%d +%d lines)" % (name, sum(x[0] == "-" for x in d), sum(x[0] == "+" for x in d)))
    print("identical (%d)   : %s" % (len(same), " ".join(same)))


main()
