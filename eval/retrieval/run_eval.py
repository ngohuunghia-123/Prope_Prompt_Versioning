"""Run the golden set against the real search path and write a scorecard.

    python -m eval.retrieval.run_eval --limit 120 --label baseline

What runs is the product: ``agent.search.semantic_search`` over
``repository.search_prompts_hybrid``, with the same
``visible_subject_filter`` every HTTP route resolves. FastAPI is the only layer
skipped, and it does not rank anything.

Two systems are measured because the product ships two: ``ai`` (the hybrid
vector + lexical path) and ``quick`` (substring keyword). Reporting them side by
side is the only way to answer "is the expensive path earning its cost?", which
`docs/materials/2-rag-pipeline.pdf` p49 says to ask of every retrieval stage.

Traces go to Langfuse when it is configured: one span per query carrying the
query id, the difficulty, the ranks, and the scores — plus the extraction spans
the indexing path already emits. Query TEXT is sent for eval traces only, and
only because it is synthetic text this repository owns; nothing from a prompt
body ever goes with it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Read ``.env`` into the environment without adding a dependency.

    The harness runs outside compose, so nothing else populates the app-owned
    provider keys, the embedding host, or the Langfuse credentials.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_dotenv()

# The Langfuse SDK logs a paragraph-long warning every time it falls back to the
# compiled-in extraction prompt, which on a 200-prompt indexing run is 200
# paragraphs between the harness's own lines. The fallback itself is counted by
# `prompt_search_extraction_prompt_fallback_total` and reported at the end.
import logging  # noqa: E402

logging.getLogger("langfuse").setLevel(logging.ERROR)

from eval.retrieval import golden as golden_module  # noqa: E402
from eval.retrieval.corpus import load_corpus  # noqa: E402
from eval.retrieval.indexing import ArtifactCache, index_corpus  # noqa: E402
from eval.retrieval.metrics import (  # noqa: E402
    QueryOutcome,
    aggregate,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from eval.retrieval import provision  # noqa: E402

RESULT_DIR = PROJECT_ROOT / "eval" / "result"


def _langfuse():
    from prope.app_agent.telemetry import get_langfuse

    return get_langfuse()


def _agent_counters() -> dict:
    """What the indexing half of this run cost, straight off the product's own metrics.

    The deck's ROI slide (2-rag-pipeline p49) asks for quality *per unit of cost*;
    these are the units. Read from the live Prometheus counters rather than
    re-derived, so a change in how the module accounts for tokens shows up here
    instead of being quietly duplicated.
    """
    from prope.prompt_search import observability

    def value(metric, **labels) -> float:
        try:
            child = metric.labels(**labels) if labels else metric
            return float(child._value.get())
        except Exception:
            return 0.0

    return {
        "extractions": {
            outcome: value(observability.extraction_total, outcome=outcome)
            for outcome in ("success", "invalid_output", "unavailable")
        },
        "tokens_in": value(observability.extraction_tokens_total, direction="input"),
        "tokens_out": value(observability.extraction_tokens_total, direction="output"),
        "cost_usd": value(observability.extraction_cost_usd_total),
        "prompt_fallbacks": value(observability.extraction_prompt_fallback_total),
        "bodies_truncated": value(observability.extraction_body_truncated_total),
        "embedding_cache_hits": value(observability.embedding_cache_hits_total),
        "embedding_cache_misses": value(observability.embedding_cache_misses_total),
    }


async def _search_ai(db, workspace, query: str, limit: int):
    from prope.prompt_search.agent import semantic_search

    return await semantic_search(
        db=db,
        query=query,
        workspace_id=workspace.workspace_id,
        visible=await _visible(db, workspace),
        actor_id=workspace.user_id,
        cursor=None,
        limit=limit,
    )


async def _search_quick(db, workspace, query: str, limit: int):
    from prope.prompt_search import repository

    return await repository.list_prompts_for_quick_search(
        db,
        workspace_id=workspace.workspace_id,
        keyword=query,
        visible=await _visible(db, workspace),
        actor_id=workspace.user_id,
        cursor=None,
        limit=limit,
    )


async def _visible(db, workspace):
    from prope.access_control.seams import Actor, ActorType, SubjectType, visible_subject_filter

    actor = Actor(type=ActorType.USER, id=workspace.user_id, workspace_id=workspace.workspace_id)
    return await visible_subject_filter(db, actor, SubjectType.PROMPT)


def _score_outcome(query, retrieved: list[str], scores: list[float], matched, latency_ms: float) -> QueryOutcome:
    primary = frozenset(query.primary)
    relevant = query.relevant
    ideal = [golden_module.GAIN_PRIMARY] * len(query.primary) + [golden_module.GAIN_SECONDARY] * len(
        query.secondary
    )
    outcome = QueryOutcome(
        query_id=query.id,
        difficulty=query.difficulty,
        category=query.category,
        route=query.route,
        retrieved=retrieved,
        scores=scores,
        matched_fields=matched,
        latency_ms=latency_ms,
    )
    if query.difficulty == "adversarial":
        outcome.abstained = not retrieved
        return outcome
    outcome.recall_at_3 = recall_at_k(retrieved, primary, 3)
    outcome.recall_at_10 = recall_at_k(retrieved, primary, 10)
    outcome.recall_at_20 = recall_at_k(retrieved, primary, 20)
    outcome.precision_at_3 = precision_at_k(retrieved, relevant, 3)
    outcome.mrr = reciprocal_rank(retrieved, primary)
    outcome.ndcg_at_10 = ndcg_at_k(retrieved, query.gain, 10, ideal)
    outcome.first_is_primary = bool(retrieved) and retrieved[0] in primary
    return outcome


async def run_queries(workspace, queries, *, system: str, limit: int) -> list[QueryOutcome]:
    from prope.db.session import workspace_transaction

    langfuse = _langfuse()
    outcomes: list[QueryOutcome] = []

    for query in queries:
        if system == "quick" and query.route == "similar":
            # A 1,800-character probe is not a keyword. Quick search is not the
            # duplicate check and is not measured as if it were.
            continue

        span_context = (
            langfuse.start_as_current_observation(name=f"eval.retrieval.{system}", as_type="span")
            if langfuse is not None
            else nullcontext(None)
        )
        started = time.perf_counter()
        with span_context as span:
            try:
                async with workspace_transaction(workspace.sessionmaker, workspace.workspace_id) as db:
                    if system == "ai":
                        results = await _search_ai(db, workspace, query.query, limit)
                    else:
                        results = await _search_quick(db, workspace, query.query, limit)
                elapsed = (time.perf_counter() - started) * 1000
                retrieved = [
                    workspace.stem_by_prompt_id.get(row.prompt_id, row.prompt_id) for row in results
                ]
                outcome = _score_outcome(
                    query,
                    retrieved,
                    [float(row.similarity or 0.0) for row in results],
                    [list(row.matched_fields) for row in results],
                    elapsed,
                )
            except Exception as error:
                elapsed = (time.perf_counter() - started) * 1000
                outcome = QueryOutcome(
                    query_id=query.id,
                    difficulty=query.difficulty,
                    category=query.category,
                    route=query.route,
                    retrieved=[],
                    scores=[],
                    latency_ms=elapsed,
                    error=f"{type(error).__name__}: {error}",
                )

            if span is not None:
                # **The query text is deliberately absent**, including from
                # `input`. Six of these queries are 1,800-character extracts of
                # real prompt files — that is what a duplicate probe IS — and the
                # module lock is explicit that no prompt body reaches the
                # telemetry backend. An evaluation harness does not get an
                # exemption a product feature would be refused (A-020). `query_id`
                # identifies the row in `eval/retrieval/golden.py`, which is in
                # git, so nothing is lost but the leak.
                span.update(
                    input={"query_id": query.id, "system": system, "characters": len(query.query)},
                    output={"retrieved": outcome.retrieved[:10], "scores": outcome.scores[:10]},
                    metadata={
                        "query_id": query.id,
                        "difficulty": query.difficulty,
                        "category": query.category,
                        "expected_primary": list(query.primary),
                        "latency_ms": round(outcome.latency_ms, 1),
                        "error": outcome.error,
                    },
                )
                for name, value in (
                    ("recall_at_3", outcome.recall_at_3),
                    ("recall_at_20", outcome.recall_at_20),
                    ("mrr", outcome.mrr),
                    ("ndcg_at_10", outcome.ndcg_at_10),
                    ("precision_at_3", outcome.precision_at_3),
                ):
                    if value is not None:
                        try:
                            span.score_trace(name=f"{system}.{name}", value=float(value))
                        except Exception:
                            pass
                if outcome.abstained is not None:
                    try:
                        span.score_trace(
                            name=f"{system}.abstained",
                            value=1 if outcome.abstained else 0,
                            data_type="BOOLEAN",
                        )
                    except Exception:
                        pass
        outcomes.append(outcome)
    return outcomes


def _print_table(title: str, rollup: dict) -> None:
    print(f"\n  {title}")
    print(
        f"    {'group':<18} {'n':>3} {'hit@1':>7} {'rec@3':>7} {'rec@10':>7} {'rec@20':>7} "
        f"{'prec@3':>7} {'MRR':>7} {'nDCG':>7}"
    )
    for name, row in rollup.items():
        def fmt(key: str) -> str:
            value = row.get(key)
            return f"{value:.3f}" if isinstance(value, (int, float)) else "  -  "

        print(
            f"    {name:<18} {row['queries']:>3} {fmt('hit_at_1'):>7} {fmt('context_recall_at_3'):>7} "
            f"{fmt('context_recall_at_10'):>7} {fmt('context_recall_at_20'):>7} "
            f"{fmt('context_precision_at_3'):>7} {fmt('mrr'):>7} {fmt('ndcg_at_10'):>7}"
        )


def _failure_analysis(outcomes: list[QueryOutcome], queries, limit: int = 5) -> list[dict]:
    """The worst scored queries, for the deck's root-cause step (p5, p47)."""
    by_id = {query.id: query for query in queries}
    scored = [outcome for outcome in outcomes if outcome.difficulty != "adversarial"]
    scored.sort(key=lambda outcome: ((outcome.mrr if outcome.mrr is not None else 0.0), outcome.query_id))
    worst = []
    for outcome in scored[:limit]:
        query = by_id[outcome.query_id]
        worst.append(
            {
                "query_id": outcome.query_id,
                "difficulty": outcome.difficulty,
                "query": query.query[:200],
                "expected_primary": list(query.primary),
                "retrieved_top5": outcome.retrieved[:5],
                "scores_top5": [round(value, 4) for value in outcome.scores[:5]],
                "matched_fields_top5": outcome.matched_fields[:5],
                "mrr": outcome.mrr,
                "error": outcome.error,
            }
        )
    return worst


async def main(args: argparse.Namespace) -> int:
    required = golden_module.required_stems()
    corpus = load_corpus(args.limit, required=required)
    present = {item.stem for item in corpus}
    covered = [stem for stem in required if stem in present]
    print(
        f"corpus: {len(corpus)} prompts; {len(covered)}/{len(required)} golden targets present"
        + ("" if len(covered) == len(required) else "  (raise --limit for full coverage)")
    )

    async with provision.database() as superuser_url:
        workspace = await provision.open_workspace(superuser_url)
        try:
            tally = await provision.seed_prompts(workspace, corpus)
            print(f"seeded: {tally['created']} created, {tally['existing']} already present")

            queries = list(golden_module.HAND_WRITTEN) + golden_module.duplicate_probes(corpus)
            print(f"golden set: {len(queries)} queries")

            if not args.no_index:
                cache = ArtifactCache()
                print(f"artifact cache: {cache.summary()}")
                report = await index_corpus(
                    workspace,
                    corpus,
                    cache=cache,
                    concurrency=args.concurrency,
                    progress=lambda done, total: print(f"  indexed {done}/{total}", flush=True),
                )
                print(
                    f"indexed: {report.indexed} ok, {report.cached} from cache, {report.failed} failed "
                    f"in {report.seconds:.0f}s; {report.near_duplicates} prompts have a >=0.9 neighbour"
                )
                for line in report.errors[:10]:
                    print(f"  ! {line}")

            # What the judge is shown: title, purpose, and the extracted topics —
            # never a prompt body (A-020). Topics come from the same cached
            # extraction the index was built from, so the judge grades the
            # representation the ranker actually used.
            topics_cache = ArtifactCache()
            details = {
                item.stem: (
                    item.title,
                    item.purpose,
                    (
                        topics_cache.get_extraction(
                            ArtifactCache.key("extract-v1", item.title, item.purpose, item.body)
                        )
                        or {}
                    ).get("topics", []),
                )
                for item in corpus
            }

            systems = ["ai", "quick"] if args.system == "both" else [args.system]
            results: dict[str, dict] = {}
            for system in systems:
                outcomes = await run_queries(workspace, queries, system=system, limit=args.k)

                judgements: list = []
                if args.judge:
                    from eval.retrieval.judge import disagreements, judge_run

                    judgements = await judge_run(
                        outcomes, queries, lookup=details.get, depth=args.judge_depth
                    )
                    scored_by_query: dict[str, list[int]] = {}
                    for judgement in judgements:
                        scored_by_query.setdefault(judgement.query_id, []).append(judgement.score)
                    for outcome in outcomes:
                        outcome.judge_scores = scored_by_query.get(outcome.query_id, [])

                summary = aggregate(outcomes)
                results[system] = {
                    "summary": summary,
                    "failures": _failure_analysis(outcomes, queries),
                    "judgements": [
                        {
                            "query_id": judgement.query_id,
                            "prompt": judgement.prompt_stem,
                            "rank": judgement.rank,
                            "score": judgement.score,
                            "why": judgement.why,
                        }
                        for judgement in judgements
                    ],
                    "label_disagreements": (
                        disagreements(judgements, queries) if judgements else []
                    ),
                    "queries": [
                        {
                            "query_id": outcome.query_id,
                            "difficulty": outcome.difficulty,
                            "category": outcome.category,
                            "retrieved": outcome.retrieved,
                            "scores": [round(value, 4) for value in outcome.scores],
                            "matched_fields": outcome.matched_fields,
                            "recall_at_3": outcome.recall_at_3,
                            "recall_at_20": outcome.recall_at_20,
                            "mrr": outcome.mrr,
                            "ndcg_at_10": outcome.ndcg_at_10,
                            "abstained": outcome.abstained,
                            "latency_ms": round(outcome.latency_ms, 1),
                            "error": outcome.error,
                        }
                        for outcome in outcomes
                    ],
                }
                print(f"\n=== system: {system} ===")
                _print_table("overall", {"all": summary["overall"]})
                _print_table("by difficulty", summary["by_difficulty"])
                adversarial = summary["adversarial"]
                print(
                    f"\n  adversarial: {adversarial['queries']} queries, "
                    f"abstention {adversarial['abstention_rate']:.0%}, "
                    f"mean false positives {adversarial['mean_false_positives']:.1f}"
                )
                latency = summary["latency_ms"]
                if latency["p50"] is not None:
                    print(f"  latency: p50 {latency['p50']:.0f} ms, p95 {latency['p95']:.0f} ms")
                if summary["errors"]:
                    print(f"  errors: {summary['errors']}")
                judge = summary["judge"]
                if judge["pairs"]:
                    print(
                        f"  judge: {judge['pairs']} pairs, mean {judge['mean_score']:.2f}/5, "
                        f"{judge['share_relevant']:.0%} scored 4+; "
                        f"{len(results[system]['label_disagreements'])} disagree with the labels"
                    )

            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            RESULT_DIR.mkdir(parents=True, exist_ok=True)
            out = RESULT_DIR / f"{stamp}-{args.label}.json"
            out.write_text(
                json.dumps(
                    {
                        "label": args.label,
                        "ran_at": stamp,
                        "config": {
                            "corpus_size": len(corpus),
                            "queries": len(queries),
                            "k": args.k,
                            "embedding_model": os.environ.get("EMBEDDING_MODEL"),
                            "app_agent_model": os.environ.get("APP_AGENT_MODEL"),
                            "ranker": os.environ.get("PROMPT_SEARCH_RANKER", "default"),
                        },
                        "agent_counters": _agent_counters(),
                        "systems": results,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            print(f"\nwrote {out.relative_to(PROJECT_ROOT)}")
        finally:
            from prope.app_agent.telemetry import flush_langfuse

            flush_langfuse()
            await provision.close(workspace)
    return 0


def cli() -> int:
    parser = argparse.ArgumentParser(description="prompt-search retrieval evaluation")
    parser.add_argument("--limit", type=int, default=120, help="corpus size")
    # 20 rather than 10: `RETRIEVAL_LIMIT` is what the duplicate check actually
    # asks for now, and a harness measuring the top ten measures a funnel nobody
    # runs. `recall@20` is undefined below this.
    parser.add_argument("--k", type=int, default=20, help="results requested per query")
    parser.add_argument("--label", default="run", help="label for the result file")
    parser.add_argument("--system", choices=["ai", "quick", "both"], default="both")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--no-index", action="store_true", help="skip indexing (corpus already indexed)")
    parser.add_argument(
        "--judge",
        action="store_true",
        help="grade the top results with the App Agent (LLM-as-judge, rubric 1-5)",
    )
    parser.add_argument("--judge-depth", type=int, default=3, help="results judged per query")
    args = parser.parse_args()
    return asyncio.run(main(args))


if __name__ == "__main__":
    raise SystemExit(cli())
