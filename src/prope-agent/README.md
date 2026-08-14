# prope-agent

A focused LangGraph-style system-prompt optimization agent.

```
INPUT  ──►  load_context
              │
              ▼
          analyze_prompt  (Prompt Analyst)
              │
              ▼
         optimize_prompt  (Prompt Optimizer)
              │
              ▼
            run_eval      (deterministic comparison)
              │
              ▼
        regression_gate   (cost / token / safety)
              │
              ▼
          explain_eval    (human-readable report)
              │
              ▼
OUTPUT ──► improved system prompt + analysis + comparison
```

## What it does

Given a system prompt, `prope-agent` runs a multi-step workflow:

1. **Loads context** and runs a baseline eval against the original prompt.
2. **Analyzes** the prompt for ambiguity, missing constraints, format
   weaknesses, hallucination risk, etc.
3. **Optimizes** the prompt — emits a candidate and a list of discrete
   changes.
4. **Evaluates** the candidate against the same dataset as the baseline.
5. **Runs a regression gate** with deterministic thresholds for token
   delta, cost delta, safety, and quality (LLM never decides pass/fail).
6. **Explains** the change for a reviewer.

The workflow is implemented as a linear async pipeline that mirrors the
`langgraph` description in the backend plan. If the `langgraph` package
is installed, `prope_agent.agents.graph.build_langgraph_app()` returns a
real `langgraph` graph using the same node functions.

## Install

```bash
cd src/prope-agent
pip install -e ".[dev]"
```

## Run as a CLI

```bash
# 1) Built-in demo prompt
prope-agent optimize --demo

# 2) Inline prompt
prope-agent optimize "You are a customer support bot."

# 3) Read from a file
prope-agent optimize --file examples/customer_support.txt

# 4) Full structured output (analysis + comparison + explanation)
prope-agent optimize --demo --explain

# 5) Use OpenAI instead of the local mock
export PROPE_AGENT_PROVIDER=openai
export PROPE_AGENT_OPENAI_API_KEY=sk-...
prope-agent optimize --demo
```

## Run as a service

```bash
cd src/prope-agent
uvicorn prope_agent.api.app:app --reload --port 8000
```

Then:

```bash
curl -X POST http://localhost:8000/optimize \
     -H "Content-Type: application/json" \
     -d '{"prompt": "You are a helpful assistant."}'

# poll for the result
curl http://localhost:8000/workflows/<id>
```

## REST endpoints

| Method | Path                                | Purpose                            |
|--------|-------------------------------------|------------------------------------|
| GET    | `/healthz`                          | Liveness                           |
| GET    | `/readyz`                           | Readiness                          |
| POST   | `/optimize`                         | Start a workflow (background)      |
| GET    | `/workflows`                        | List workflows                     |
| GET    | `/workflows/{id}`                   | Fetch full state (final_prompt)    |
| POST   | `/workflows/{id}/approve`           | HITL approval hook                 |

## Architecture

```
prope_agent/
├── agents/
│   ├── graph.py             # linear pipeline + optional langgraph adapter
│   ├── state.py             # PromptWorkflowState (TypedDict)
│   ├── nodes/
│   │   ├── load_context.py
│   │   ├── analyze_prompt.py
│   │   ├── optimize_prompt.py
│   │   ├── run_eval.py
│   │   ├── regression_gate.py
│   │   └── explain_eval.py
│   └── prompts/
│       └── templates.py     # system prompts for each node
├── api/
│   ├── app.py               # FastAPI surface
│   └── schemas.py           # Pydantic request/response models
├── cli/
│   └── main.py              # argparse CLI (`prope-agent optimize ...`)
├── core/
│   ├── config.py            # settings (env-driven)
│   ├── exceptions.py
│   └── logging.py
├── eval/
│   └── engine.py            # deterministic eval + quality gate
├── providers/
│   ├── base.py              # LLMProvider protocol
│   ├── mock_provider.py     # no-network "LLM" for dev/tests
│   ├── openai_provider.py   # OpenAI adapter
│   └── factory.py
└── storage/
    └── workflow_store.py    # in-memory workflow registry
```

## Quality gate rules (deterministic)

- **LLM never decides pass/fail.** The eval engine compares deterministic
  metrics; the gate is a pure function of those metrics.
- Safety regression of any kind → `FAIL`.
- Quality delta < -5% → `FAIL`.
- Quality delta < -1% → `PASS_WITH_WARNING`.
- Cost delta > 15% → `PASS_WITH_WARNING`.
- Otherwise → `PASS`.

These thresholds come from `prope_agent/core/config.py` and can be
overridden via environment variables (`PROPE_AGENT_TOKEN_WARNING_THRESHOLD`,
`PROPE_AGENT_COST_WARNING_THRESHOLD`,
`PROPE_AGENT_MIN_IMPROVEMENT_THRESHOLD`).

## Why a plain async pipeline, not a hard `langgraph` dep

The backend plan references LangGraph, but the workflow is strictly
linear and has no branching / tool loop / state-across-turns. Keeping it
as a dependency-injected pipeline:

- runs cleanly on a laptop without extra libraries,
- makes the "no LLM decides the gate" invariant obvious,
- and `build_langgraph_app()` returns a real `langgraph` graph using the
  same nodes if the package is installed.

## Tests

```bash
cd src/prope-agent
pytest
```

## Configuration

| Env var                                  | Default       | Notes                          |
|------------------------------------------|---------------|--------------------------------|
| `PROPE_AGENT_PROVIDER`                   | `mock`        | `mock` \| `openai`             |
| `PROPE_AGENT_OPENAI_API_KEY`             | (none)        | required if provider=openai    |
| `PROPE_AGENT_OPENAI_MODEL`               | `gpt-4o-mini` |                                |
| `PROPE_AGENT_OPENAI_BASE_URL`            | (none)        |                                |
| `PROPE_AGENT_MAX_OPTIMIZATION_PASSES`    | `2`           | reserved for iterative mode    |
| `PROPE_AGENT_TEMPERATURE`                | `0.3`         |                                |
| `PROPE_AGENT_MAX_TOKENS`                 | `2048`        |                                |
| `PROPE_AGENT_TOKEN_WARNING_THRESHOLD`    | `15.0`        | %                              |
| `PROPE_AGENT_COST_WARNING_THRESHOLD`     | `15.0`        | %                              |
| `PROPE_AGENT_SYNTHETIC_EVAL_CASES`       | `5`           | 1..50                          |

## Grounding notes

This module was designed alongside the broader backend plan. Key
constraints from the plan that shaped this implementation:

- PromptVersion is immutable — `final_prompt` is produced as a
  proposal; it never overwrites anything in storage.
- LLM never decides pass/fail — quality gate is a pure function.
- The pipeline is dependency-injected so it is testable without an
  external LLM.
- pgvector / Similar Prompt Retrieval / Optimization Memory are out of
  scope for this focused agent and would be added in Phase 7–8 of the
  plan.
