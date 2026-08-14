# prope-agent — Quick contract demo

This folder ships a focused LangGraph-style workflow that takes a system
prompt in and emits an improved system prompt out.

## The contract

```
INPUT  →  one system prompt (string)
OUTPUT →  one improved system prompt (string)
```

## Demo (no API key required)

```python
from prope_agent import optimize_text

src = "You are a code review assistant. Look at code and find bugs."
out = optimize_text(src)
print(out)
```

Output (Mock provider — deterministic):

```
You are a code review assistant. Look at code and find bugs.

# Output format
Respond concisely. When a structured answer is requested, use JSON. ...

# Constraints
- Do not invent facts.
- If unsure, say so and ask one clarifying question.
- Refuse unsafe requests and explain why briefly.

# Examples
User: Summarize the attached spec in three bullets.
Assistant:
- Bullet one — main goal.
- Bullet two — key constraint.
- Bullet three — open question.
```

## Demo via CLI

```
prope-agent optimize --demo --explain
```

## Workflow

```
load_context → analyze_prompt → optimize_prompt → run_eval → regression_gate → explain_eval
```

All six nodes are real, dependency-injected async functions. The
deterministic quality gate never lets the LLM decide pass/fail. See
`prope_agent/agents/` and `prope_agent/eval/`.
