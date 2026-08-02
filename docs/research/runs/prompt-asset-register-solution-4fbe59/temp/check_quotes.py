import os
import re

REP = "research/notes/final_report_prompt-asset-register-solution-4fbe59.md"

text = open(REP, encoding="utf-8").read()
body = text.split("## Sources")[0]

notes = {}
for fn in os.listdir("research/notes"):
    if fn.endswith(".md") and not fn.startswith("final_report"):
        raw = open("research/notes/" + fn, encoding="utf-8", errors="replace").read()
        notes[fn[:-3]] = re.sub(r"\s+", " ", raw)


def norm(s):
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip()


notes_n = {k: norm(v) for k, v in notes.items()}

spans = []
for pat in [r"“([^”]{10,400})”", r'"([^"]{10,400})"']:
    for m in re.finditer(pat, body):
        spans.append(m.group(1))

bad = []
for q in spans:
    n = norm(q)
    if not any(n in v for v in notes_n.values()):
        bad.append(q)

print(f"quoted spans: {len(spans)}   unverified: {len(bad)}")
for b in bad:
    print("-----")
    print(b[:300])
