import os
import re

REP = "research/notes/final_report_prompt-asset-register-solution-4fbe59.md"
body = open(REP, encoding="utf-8").read().split("## Sources")[0]

notes = []
for fn in os.listdir("research/notes"):
    if fn.endswith(".md") and not fn.startswith("final_report"):
        notes.append(open("research/notes/" + fn, encoding="utf-8", errors="replace").read())

# Case-SENSITIVE, whitespace-collapsed only. Closest to a strict verbatim check.
notes_s = [re.sub(r"\s+", " ", v) for v in notes]

spans = []
for pat in ["“([^”]{3,600})”", '"([^"]{3,600})"']:
    for m in re.finditer(pat, body):
        spans.append((m.group(0), m.group(1)))

bad = []
for full, inner in spans:
    probe = re.sub(r"\s+", " ", inner).strip()
    if not any(probe in v for v in notes_s):
        bad.append((full, probe))

print("spans:", len(spans), " strict-unverified:", len(bad))
for full, probe in bad:
    idx = body.find(full)
    print("=====")
    print("INNER:", probe)
    print("CTX  :", re.sub(r"\s+", " ", body[max(0, idx - 150): idx + len(full) + 150]))
