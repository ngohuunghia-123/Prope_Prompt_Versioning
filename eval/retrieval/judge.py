"""LLM-as-judge over the pairs no human labelled.

`docs/materials/7-ai-evaluation-benchmarking.pdf` p23-28. The golden set answers
*did we find the prompt we were looking for*; it cannot answer *is the rest of
this list any good*, because nobody hand-labelled 200 prompts against 42
queries. That is the gap a judge closes, and the two measurements check each
other: a result the labels call irrelevant and the judge calls a 5 is a hole in
the labels, not a win for the ranker.

The deck's bias list (p27) is followed, and two of the four are answered by
construction rather than by prompting:

* **Position bias** — each (query, prompt) pair is judged alone. There is no
  list to be first in.
* **Self-preference** — the judge is the same app-owned model that wrote the
  index metadata, which is the one bias here that is NOT mitigated. Recorded
  rather than hidden: it is a reason to read the judge as a second opinion and
  the labels as the measurement.
* **Verbosity bias** — the rubric scores relevance to a question, and the judge
  sees a title and a purpose, never a whole prompt body.
* **Consistency** — temperature 0.

**No prompt body is sent.** The judge sees the title, the extracted topics and
the purpose. That is not a telemetry decision, it is A-020: real corporate
prompts may not leave the system for a convenience, and an evaluation harness
does not get an exemption a product feature would be refused.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

RUBRIC = """You are grading a prompt-library search engine.

A user searched for: {query}

One result came back:
  Title: {title}
  Topics: {topics}
  Purpose: {purpose}

Score how well this result answers what the user searched for, 1-5:
5 = exactly what they asked for
4 = a good answer; they would use it
3 = related and plausibly useful, but not what was asked
2 = same broad field, does not answer the request
1 = unrelated

Concise entries are not penalised. Judge the match, not the writing.

Reply with JSON only: {{"score": <1-5>, "why": "<one short sentence>"}}"""


@dataclass(frozen=True, slots=True)
class Judgement:
    query_id: str
    prompt_stem: str
    rank: int
    score: int
    why: str


def _parse(text: str) -> tuple[int, str]:
    """Take the score out of whatever the model wrapped it in.

    Fenced JSON, bare JSON, or a sentence with a number in it — all three occur,
    and a judge that crashes the run because it added a code fence is a judge
    nobody keeps.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            payload = json.loads(match.group(0))
            score = int(payload.get("score", 0))
            if 1 <= score <= 5:
                return score, str(payload.get("why", ""))[:200]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    digits = re.search(r"[1-5]", text)
    return (int(digits.group(0)) if digits else 0), text[:200]


async def judge_pair(
    *,
    query: str,
    title: str,
    purpose: str,
    topics: list[str],
) -> tuple[int, str]:
    from prope.app_agent import APP_AGENT_MODEL, get_openai_client

    client = await get_openai_client()
    response = await client.chat.completions.create(
        model=APP_AGENT_MODEL,
        messages=[
            {
                "role": "user",
                "content": RUBRIC.format(
                    query=query[:600],
                    title=title,
                    topics=", ".join(topics[:6]) or "(none)",
                    purpose=purpose[:300],
                ),
            }
        ],
        temperature=0.0,
        max_tokens=120,
    )
    return _parse(response.choices[0].message.content or "")


async def judge_run(
    outcomes,
    queries,
    *,
    lookup,
    depth: int = 3,
    concurrency: int = 6,
) -> list[Judgement]:
    """Grade the top ``depth`` results of every non-adversarial query.

    ``lookup(stem)`` returns ``(title, purpose, topics)``. Failures are dropped
    rather than raised: a judge is a second opinion, and losing it must not lose
    the run that produced the thing being judged.
    """
    by_id = {query.id: query for query in queries}
    gate = asyncio.Semaphore(concurrency)
    judgements: list[Judgement] = []

    async def one(outcome, stem: str, rank: int) -> None:
        query = by_id[outcome.query_id]
        details = lookup(stem)
        if details is None:
            return
        title, purpose, topics = details
        async with gate:
            try:
                score, why = await judge_pair(
                    query=query.query, title=title, purpose=purpose, topics=topics
                )
            except Exception:
                return
        if score:
            judgements.append(Judgement(outcome.query_id, stem, rank, score, why))

    await asyncio.gather(
        *(
            one(outcome, stem, rank)
            for outcome in outcomes
            if outcome.difficulty != "adversarial"
            for rank, stem in enumerate(outcome.retrieved[:depth], start=1)
        )
    )
    return judgements


def disagreements(judgements: list[Judgement], queries) -> list[dict]:
    """Where the judge and the golden labels contradict each other.

    Both directions matter and they mean different things. A labelled-relevant
    result the judge scores 1-2 questions the label. An unlabelled result the
    judge scores 5 means the golden set is missing a right answer — which
    silently depresses precision for every run ever compared against it.
    """
    by_id = {query.id: query for query in queries}
    found: list[dict] = []
    for judgement in judgements:
        query = by_id.get(judgement.query_id)
        if query is None:
            continue
        labelled = judgement.prompt_stem in query.relevant
        if labelled and judgement.score <= 2:
            found.append(
                {
                    "kind": "label_says_relevant_judge_disagrees",
                    "query_id": judgement.query_id,
                    "prompt": judgement.prompt_stem,
                    "score": judgement.score,
                    "why": judgement.why,
                }
            )
        elif not labelled and judgement.score >= 5:
            found.append(
                {
                    "kind": "unlabelled_but_judge_says_exact",
                    "query_id": judgement.query_id,
                    "prompt": judgement.prompt_stem,
                    "score": judgement.score,
                    "why": judgement.why,
                }
            )
    return found
