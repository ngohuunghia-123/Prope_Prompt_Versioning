# Extraction golden set

`extraction_golden.jsonl` is the fixed evaluation suite for the metadata
extraction agent. One JSON object per line:

| field | meaning |
|---|---|
| `note` | why this record exists — which behaviour it pins down. **Required.** |
| `title`, `purpose`, `body` | the three inputs, exactly as `extract_metadata` receives them |
| `expected.expected_keywords` | terms a human decided the extraction must find |

## Every record is synthetic, and a test enforces it

**A-020 holds the line: no real corporate prompts in the pilot until OQ-006 and
OQ-013 are answered.** A golden set is the most tempting place to break that —
real prompts are right there, they are more representative, and the file looks
like test data rather than like production content. It is still the same text,
committed to the repository, read by an optimizer, and sent to a third-party
model on every evaluation run.

So every record is written by hand. `tests/unit/test_prompt_search_dspy.py`
asserts that each one carries a `note`, which is the cheapest available proxy: a
prompt somebody pasted in from a real workspace does not come with an
explanation of which behaviour it pins down.

Addresses use the `.invalid` TLD (RFC 2606) so that nothing in this file can
resolve, be mailed, or be fetched.

## Expected keywords are scored for RECALL only

`evaluation._expected_recall` asks how many of the expected terms the extraction
found. It never penalises terms the human did not think of. An extraction that
returns all four expected keywords plus three good ones of its own is better than
one that returns exactly four, and a precision score would say the opposite.

Matching is substring-over-folded-text, so `refund` is found by `refunds` and
`kiem tra` by `kiểm tra`.

## What the coverage is meant to be

Adding a record is cheap; adding one that duplicates an existing behaviour costs
an evaluation call on every future run for no information. The set currently
pins down:

- both languages alone, and one genuinely bilingual body
- an entity-rich prompt and one that names nothing, because inventing an entity
  and missing one are different failures
- two shapes of prompt injection — the imperative (`IGNORE ALL PREVIOUS
  INSTRUCTIONS`) and the impersonated conversation turn — since the body is
  untrusted data by construction
- a body shorter than the requested keyword count, where the right answer is
  fewer terms rather than padding
- repeated `{{template}}` variables, which are mechanics and not subject matter
- contact details and a URL, which are indexed around rather than into
- a body long enough to exercise truncation

## Running it

```bash
uv run python -m prope.prompt_search.agent.optimize --evaluate-only
```

This calls the real model with the real key. It costs money and it is not part
of `pytest`; the unit tests exercise the metric against fixed metadata instead.
