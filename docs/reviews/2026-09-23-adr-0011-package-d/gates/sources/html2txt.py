"""Convert the saved official man pages (HTML) to plain text, one block per line.

Usage: python html2txt.py <in.html> <out.txt>
Read-only on its input; writes only <out.txt>. Standard library only.
"""
import html
import re
import sys
from html.parser import HTMLParser

BLOCK = {"p", "div", "dt", "dd", "li", "h1", "h2", "h3", "h4", "tr", "pre", "br", "table", "title"}


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in BLOCK:
            self.out.append("\n")
        if tag in ("h1", "h2", "h3", "h4"):
            self.out.append("## ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        if tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


src, dst = sys.argv[1], sys.argv[2]
p = P()
p.feed(open(src, encoding="utf-8", errors="replace").read())
text = "".join(p.out)
lines = []
for block in text.split("\n"):
    s = re.sub(r"\s+", " ", html.unescape(block)).strip()
    if s:
        lines.append(s)
open(dst, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print(dst, len(lines), "lines")
