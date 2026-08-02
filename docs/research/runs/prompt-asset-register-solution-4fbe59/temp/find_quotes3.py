import os
import re

REP = "research/notes/final_report_prompt-asset-register-solution-4fbe59.md"
text = open(REP, encoding="utf-8").read()
body = text.split("## Sources")[0]

notes = []
for fn in os.listdir("research/notes"):
    if fn.endswith(".md") and not fn.startswith("final_report"):
        notes.append(open("research/notes/" + fn, encoding="utf-8", errors="replace").read())


def norm(s):
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


notes_n = [norm(v) for v in notes]

# Double-quote delimited spans ONLY (straight and curly). No apostrophes.
spans = []
for pat in ["“([^”]{3,600})”", '"([^"]{3,600})"']:
    for m in re.finditer(pat, body):
        spans.append((m.group(0), m.group(1)))

bad = [(f, i) for f, i in spans if not any(norm(i) in v for v in notes_n)]

print("double-quoted spans:", len(spans), " unverified:", len(bad))
for full, inner in bad:
    idx = body.find(full)
    print("=====")
    print("INNER:", inner)
    print("CTX  :", re.sub(r"\s+", " ", body[max(0, idx - 200): idx + len(full) + 200]))
