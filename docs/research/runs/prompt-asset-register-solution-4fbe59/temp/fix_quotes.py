"""Unquote spans that are not verbatim in any vault note.

The claim and its citation stay; only the quotation marks go, so the report
stops asserting verbatimness it cannot support.
"""
import os
import re

REP = "research/notes/final_report_prompt-asset-register-solution-4fbe59.md"

text = open(REP, encoding="utf-8").read()
head, sep, tail = text.partition("## Sources")

notes = {}
for fn in os.listdir("research/notes"):
    if fn.endswith(".md") and not fn.startswith("final_report"):
        raw = open("research/notes/" + fn, encoding="utf-8", errors="replace").read()
        notes[fn[:-3]] = raw


def norm(s):
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip()


notes_n = [norm(v) for v in notes.values()]


def verbatim(q):
    n = norm(q)
    return any(n in v for v in notes_n)


fixed = 0
kept = 0


def repl(m):
    global fixed, kept
    inner = m.group(1)
    if verbatim(inner):
        kept += 1
        return m.group(0)
    fixed += 1
    return inner


pattern = re.compile(r"“([^”]{10,400})”")
head = pattern.sub(repl, head)
pattern2 = re.compile(r'"([^"]{10,400})"')
head = pattern2.sub(repl, head)

open(REP, "w", encoding="utf-8", newline="\n").write(head + sep + tail)
print(f"quotes unquoted (not verbatim): {fixed}")
print(f"quotes kept (verbatim in vault): {kept}")
print("words:", len(re.findall(r"\S+", head + sep + tail)))
