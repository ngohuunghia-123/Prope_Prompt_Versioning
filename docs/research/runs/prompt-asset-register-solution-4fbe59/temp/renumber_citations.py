"""Convert [note-id] citation markers in the final report to numbered [N] form
and append a generated ## Sources section.

Deterministic: numbering follows order of first appearance. Unknown ids are
reported (never silently dropped) so the orchestrator can fix them.
"""
import os
import re
import sys

RUN = "prompt-asset-register-solution-4fbe59"
REPORT = os.path.join("research", "notes", f"final_report_{RUN}.md")
NOTES_DIR = os.path.join("research", "notes")


def load_index():
    """note-id -> (title, url) from each note's YAML frontmatter."""
    index = {}
    for fn in os.listdir(NOTES_DIR):
        if not fn.endswith(".md"):
            continue
        nid = fn[:-3]
        if nid.startswith("final_report_"):
            continue
        title, url = None, None
        path = os.path.join(NOTES_DIR, fn)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 40:
                    break
                s = line.strip()
                if title is None and s.startswith("title:"):
                    title = s[6:].strip().strip('"').strip("'")
                elif url is None and s.startswith("url:"):
                    url = s[4:].strip().strip('"').strip("'")
                if title and url:
                    break
        index[nid] = (title or nid, url or "")
    return index


def main():
    if not os.path.exists(REPORT):
        sys.exit(f"report not found: {REPORT}")

    index = load_index()
    text = open(REPORT, encoding="utf-8").read()

    order = []          # note ids in first-appearance order
    unknown = set()

    # Matches [id] and [id1, id2] / [id1; id2]. Ids are lowercase slugs with
    # digits/hyphens, at least 6 chars, so ordinary prose in brackets is skipped.
    token = r"[a-z0-9][a-z0-9\-]{5,}"
    pattern = re.compile(r"\[(" + token + r"(?:\s*[,;]\s*" + token + r")*)\]")

    def repl(match):
        ids = [p.strip() for p in re.split(r"[,;]", match.group(1))]
        nums = []
        for nid in ids:
            if nid not in index:
                unknown.add(nid)
                return match.group(0)  # leave untouched for manual review
            if nid not in order:
                order.append(nid)
            nums.append(str(order.index(nid) + 1))
        return "[" + ", ".join(nums) + "]"

    converted = pattern.sub(repl, text)

    # Drop any Sources section the synthesizer may have written anyway.
    converted = re.split(r"\n## Sources\s*\n", converted)[0].rstrip()

    lines = ["", "", "## Sources", ""]
    for i, nid in enumerate(order, 1):
        title, url = index[nid]
        lines.append(f"{i}. {title} — {url}" if url else f"{i}. {title}")
    converted += "\n".join(lines) + "\n"

    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(converted)

    words = len(re.findall(r"\S+", converted))
    print(f"citations renumbered: {len(order)} unique sources cited")
    print(f"word count: {words}")
    if unknown:
        print(f"UNKNOWN IDS LEFT UNCONVERTED ({len(unknown)}):")
        for nid in sorted(unknown):
            print(f"  - {nid}")
    else:
        print("no unknown ids")


if __name__ == "__main__":
    main()
