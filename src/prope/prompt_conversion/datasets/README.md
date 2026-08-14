# The conversion golden set

`conversion_golden.jsonl` — one JSON object per line:

| field                  | required | meaning                                                     |
|------------------------|----------|-------------------------------------------------------------|
| `source_format`        | yes      | `txt` \| `markdown` \| `json` \| `yaml`                       |
| `source_text`          | yes      | The source as an author would paste it                       |
| `expected_block_types` | no       | The types a correct conversion produces. Omit when arguable  |
| `note`                 | no       | Why this example is in the set. Read by people, not by code  |

`evaluation.load_examples()` runs every `source_text` through `normalize_source`
at load, so a malformed record fails with a file and a line number rather than
as an opaque zero somewhere inside a compile.

## What is in here, and what is deliberately not

Twelve examples, chosen for coverage of the ways a conversion goes wrong rather
than for volume: one per source format, one per block type, one with a repeated
variable, one with XML metacharacters, one prompt-injection attempt, one
Vietnamese source, one with all six types at once. Twelve is small for
`MIPROv2`, which is why `optimize.py` picks `BootstrapFewShot` below thirty and
says so in its output.

**Nothing in here is a real corporate prompt, and nothing may be added that is.**
A-020 holds the pilot to synthetic sources until OQ-006 and OQ-013 are answered,
and a golden set is exactly where real customer prompts would leak into the
repository — permanently, in git history, under review by anyone with a
checkout. Every example above was written for this file.

## Growing it

The material's advice is to grow a golden set from production failures. The
version of that this module can actually do without violating the paragraph
above: when a conversion fails, `service.py` records the outcome, the source
format and the coverage ratio — never the source. An operator who reproduces
the failure writes a NEW synthetic example with the same shape. That is slower
and it is the only way that stays inside A-020.

## Running it

```sh
uv run python -m prope.prompt_conversion.optimize --evaluate-only
uv run python -m prope.prompt_conversion.optimize --publish
```

Both spend real tokens against `APP_OPENAI_API_KEY`. Neither promotes anything:
`--publish` writes an unlabelled Langfuse prompt version, and a human moves the
`production` label.
