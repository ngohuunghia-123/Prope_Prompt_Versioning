---
title: Prompt Engineering Fails Quietly —  Prompt Regression Is Why | Towards Data
  Science
id: prompt-engineering-fails-quietly-prompt-regression-is-why-towards-data-science
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:49.901917Z'
source: https://towardsdatascience.com/prompt-engineering-fails-quietly-prompt-regression-is-why/
source_domain: towardsdatascience.com
fetched_at: '2026-08-02T03:11:49.878919Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 17.0
---

Prompt Engineering Fails Quietly —  Prompt Regression Is Why | Towards Data Science
Skip to content
Large Language Models
Prompt Engineering Fails Quietly —  Prompt Regression Is Why
A practical framework to detect hidden prompt regressions before they silently break production systems
Emmimal P Alexander
Jun 29, 2026
17 min read
Share
Image by the author, generated with ChatGPT (DALL·E)
TL;DR
Prompts are not static config files. Every instruction you add changes the behaviour of every query type the prompt already handles.
Most teams catch prompt failures through user reports, not tests. This article builds the test suite.
The suite runs 40 golden queries across four prompt versions, validates outputs with four deterministic checks, and detects the False Improvement pattern, where overall accuracy rises while a critical category collapses.
v4, the “best” prompt at 67.5% overall accuracy, triggered FALSE IMPROVEMENT DETECTED due to a 66.7% collapse in negation classification.
Zero external dependencies. Pure Python. Runs in under two seconds.
My RAG query layer was working fine. Then I added document routing for PDFs and policies, and the prompt ballooned from six instructions to fourteen. I spot-tested a few cases, everything looked right, and I shipped it.
Three weeks later, I was tracking down a support issue where negation queries (stuff like “Which products are not covered under warranty?”) were being misclassified as standard policy lookups instead of negation checks. The weird part was that I hadn’t touched the classification logic or the routing code. The only thing that changed was the system prompt.
That’s when I understood the problem. I was treating my prompt like a static config file. It isn’t. A prompt is a stochastic API, and every time you add instructions to it, you are changing the API contract for every query type it handles, not just the ones you were thinking about.
The software engineering world has a name for what I didn’t have: a regression test suite. The idea is simple. Before any change ships, you run the tests. If something that was passing is now failing, you do not ship. I had nothing like that for prompts. Most teams don’t.
This mirrors the core idea behind Test-Driven Development (Beck [5]): define expected behavior before making changes. The discipline forces you to define correct behavior before you touch the code. Applied to prompts, this means defining valid classification logic for each category before adding a new instruction. Without these definitions, you have no way to detect when a change breaks something you weren’t even thinking about.
The hidden cost problem exists in ML systems as well. Sculley et al. [4] documented how undeclared dependencies and unstable data interfaces accumulate as technical debt in production ML pipelines. A prompt that silently alters behavior across categories without detection is this exact class of problem. The interface looks stable from the outside, but the behavior has drifted underneath.
All numbers below are from real runs of this system on Python 3.12, Windows 11, CPU only.
The code is at:
https://github.com/Emmimal/prompt-regression-suite
The Setup
The regression suite tests four prompt versions against 40 golden queries across six intent categories, built on top of a RAG intent classification system [1]. The four versions reflect a real iteration sequence from the RAG intent classification system I built for this article. Every single change was made for a legitimate reason, and every single one introduced a hidden problem.
v1 is the baseline. It handles clean intent classification with minimal instructions and zero reasoning steps. There is just one rule about keeping things concise and another about the JSON output format.
v2 adds chain-of-thought reasoning. I brought this in because multi-hop queries like checking a response time for an enterprise plan with a P1 ticket after hours were getting misclassified. Chain-of-thought has been shown to significantly improve performance on complex reasoning tasks [2], and it did fix that specific problem. The mistake was applying it globally. The v2 prompt now tells the model to “be concise” in one rule, while demanding it “explain your reasoning step by step” in another. Those two rules contradict each other on every simple query the system touches.
v3 adds document routing. The new instructions tell the model to check for tabular, policy, and PDF signals before it classifies intent. One line in particular completely broke negation handling: “Prioritize document routing before intent classification.” Negation queries like “Which regions are excluded from the express shipping policy?” contain policy keywords, so under v3, the model resolves the document type before it ever touches intent. The negation check never even fires.
v4 combines both changes, and this is what became the production prompt. The total instruction surface area roughly tripled, and the latent conflicts from v2 and v3 are now compounding.
The Golden Set
The 40 queries are distributed across six categories.
Category
N
Failure Mode Targeted
simple_intent
10
overreasoning_noise
comparison
8
missing_comparative_anchor
aggregation
6
numeric_scope_collapse
negation
6
instruction_conflict
multi_hop
6
benefits_from_cot
edge_ambiguous
4
false_confidence
TOTAL
40
Each query was chosen to expose a specific failure mode, not to be a general representation. Take the comparison category, for instance. It is a known failure in this system because comparison queries require a comparative anchor that the current prompt architecture simply does not resolve. I am not hiding that in this benchmark, and you will see the
[KNOWN FAILURE]
annotation in every single diff report.
Instead of checking against a hardcoded reference answer, each query carries a validation signature: a set of deterministic constraints.
{
  "id": "NQ_01",
  "query": "Which products are not covered under the warranty policy?",
  "category": "negation",
  "expected_intent": "negation_check",
  "expected_schema_keys": ["intent", "confidence", "query_type", "rewritten_query"],
  "expected_patterns": ["not covered", "warranty"],
  "must_not_contain": ["I cannot", "As an AI"],
  "failure_mode": "instruction_conflict"
}
The
failure_mode
field isn’t there for documentation. It is a testable claim. If the prompt has an instruction conflict that intercepts negation resolution, this query will fail, and that failure mode label tells you exactly where to look.
The Validator
The
QueryValidator
class runs four deterministic checks on every single output. No LLM-as-a-judge, and absolutely no subjective quality scoring.
class QueryValidator:
    def validate(self, output: dict, query: dict) -> ValidationResult:

        # 1. Schema check: required keys present in output dict
        schema_failures = [k for k in expected_keys if k not in output]
        schema_pass = len(schema_failures) == 0

        # 2. Pattern check: expected patterns present in output text
        output_text = " ".join(str(v) for v in output.values()).lower()
        pattern_failures = [
            p for p in expected_patterns
            if not re.search(re.escape(p.lower()), output_text)
        ]
        pattern_pass = len(pattern_failures) == 0

        # 3. Intent check: classified intent matches expected label
        detected_intent = output.get("intent", "")
        intent_pass = detected_intent == expected_intent

        # 4. Guard check: must_not_contain strings are absent
        guard_violations = [g for g in must_not_contain if g.lower() in output_text]
        guard_pass = len(guard_violations) == 0
A query either passes all four checks or it fails. There’s no partial credit or complex weighting, and definitely no judge model introducing variance between runs. The category score is just
passed_count / total_count
. You feed it the same input, you get the exact same output every single time.
I completely skipped the LLM-as-a-judge route. Honestly, I realized something important here: regression testing isn’t really a quality problem — it’s a contract problem. Checking if the output intent matches the expected intent is binary, so a judge model just adds noise. Plus, running an LLM judge across 40 queries for every minor prompt tweak gets expensive fast. This script finishes in under two seconds and costs absolutely nothing.
The Scorer and False Improvement Detection
The
Scorer
class computes per-category accuracy and then does one more thing that is the actual point of this system.
REGRESSION_THRESHOLD = 0.10
CRITICAL_CATEGORIES = {"simple_intent", "negation"}

# False Improvement Detection
overall_improved = candidate.overall_score > baseline.overall_score
if overall_improved and critical_regressions:
    candidate.false_improvement_detected = True
    candidate.false_improvement_reason = (
        f"Overall score improved by "
        f"{(candidate.overall_score - baseline.overall_score) * 100:.1f}% "
        f"but critical categories regressed: [{cats}]"
    )
The false improvement pattern is this: a prompt change improves the aggregate accuracy score while collapsing performance on a specific critical category. The overall metric looks good, so you ship it because the number went up. The prompt is broken.
CRITICAL_CATEGORIES
is a system-specific design decision. For my intent classifier,
simple_intent
and
negation
are critical because they represent the majority of real traffic. Multi-hop queries matter, but they are rare. A 100% improvement on rare queries does not justify a 66.7% collapse on common ones. This is why you write integration tests before unit tests on a payment flow: protect the thing that breaks users first.
The Deterministic Simulator
The suite uses a deterministic mock simulator instead of live LLM calls. This is the most important architectural decision in the codebase and it needs a direct explanation.
The simulator does not produce random outputs. Each failure function reflects a specific real failure pattern caused by a specific instruction conflict in the corresponding prompt version.
def simulate_output(prompt_version: str, query: dict) -> dict:

    # v2 + simple_intent → CoT bleeds into rewritten_query, guard check fires
    if version == "v2" and category == "simple_intent":
        return _overreasoning_noise(query)

    # v3 + negation → doc routing intercepts before intent resolves
    if version == "v3" and category == "negation":
        if query_number in (1, 3, 5):
            return _instruction_conflict_moderate(query)

    # v4 + negation → both conflicts compound, intent misclassified as ambiguous
    if version == "v4" and category == "negation":
        if query_number in (1, 2, 4, 5):
            return _instruction_conflict_severe(query)
The
_instruction_conflict_severe
function produces
"intent": "ambiguous"
where the correct answer should be
"negation_check"
. Confidence drops to 0.39. The rewritten query contains CoT noise:
"Step 1: Scan for document type signals... Step 2: Negation keyword detected: but document routing takes priority... Step 3: Therefore classifying as ambiguous pending document context resolution."
That output fails the intent check (wrong intent), the pattern check (negation patterns absent), and the guard check (CoT step tokens present). That is three of four checks failing on the same output, which is what the benchmarked 66.7% negation collapse reflects: 4 of 6 negation queries failing under v4.
The choice between deterministic simulation and live LLM calls depends entirely on what you are trying to measure. Regression testing is not quality evaluation. Quality evaluation asks if an output is good; regression testing asks if a change broke something that was already working. They are distinct problems requiring different tools.
LLM-as-a-judge works well for quality evaluation because it can process open-ended outputs [3] where deterministic metrics fall short. Regression testing, however, demands absolute determinism. If your test results fluctuate between runs, you lose the ability to separate a genuine prompt regression from background noise. The fact that a deterministic simulator yields the exact same output every run is a feature, not a limitation.
The two methods complement each other. Run this regression suite before every prompt commit to intercept structural breaks, and run your LLM-as-a-judge evaluations periodically to audit the open-ended nuances that code-based checks cannot catch.
By avoiding live API calls, running
python run_regression.py
produces identical numbers every time, regardless of who clones the repository. You eliminate model variance, provider-side updates, and unnecessary API bills. For a regression framework, reproducibility is the only metric that matters.
Benchmark Results
CATEGORY SCORES BY PROMPT VERSION
Category
v1
v2
v3
v4
simple_intent
100.0%
40.0%
80.0%
90.0%
negation
100.0%
66.7%
50.0%
33.3%
aggregation
100.0%
100.0%
100.0%
100.0%
multi_hop
0.0%
100.0%
100.0%
100.0%
comparison
0.0%
0.0%
0.0%
0.0%
edge_ambiguous
25.0%
100.0%
100.0%
100.0%
OVERALL
57.5%
60.0%
67.5%
67.5%
The overall row is the one that gets prompts shipped to production. v4 ties v3 at 67.5%, both above the v1 baseline of 57.5%. By that metric, v4 is your best prompt. By the regression suite’s metric, v4 is a broken prompt.
VERDICT: v1 → v4

  ⚠  FALSE IMPROVEMENT DETECTED

  Overall score improved by 10.0% but critical categories
  regressed: [negation]

  Critical regressions:
    • negation   100.0% → 33.3%  ▼ 66.7%
      Failure mode: instruction_conflict

  STATUS:  ✗  DO NOT PROMOTE TO PRODUCTION
The same verdict fires for v2 and v3. All three candidates trigger
FALSE IMPROVEMENT DETECTED
. All three show overall improvement over baseline. All three have broken critical categories.
What Each Version Actually Did
This Image breakdown shows the regression cascade across all three candidates.
Performance breakdown of prompt engineering techniques (Chain of Thought and routing) against a baseline model. The aggregate accuracy scores are highly misleading; the 100% gain in multi-hop reasoning completely masks the severe performance degradation (negation collapse) occurring in standard negation tasks. Image by Author
The multi-hop accuracy shows exactly what happened. The v1 baseline scores 0.0% here. Without chain-of-thought, complex conditional queries (where three or more conditions must be resolved in sequence) get misclassified as
fact_retrieval
. The model cannot handle those conditions in parallel without explicit reasoning scaffolding. CoT fixed that completely, bringing v2, v3, and v4 up to 100.0%.
Chain-of-thought was the right fix for the specific problem it was meant to solve. The mistake was applying it globally. The exact instruction that fixed conditional reasoning chains caused the model to over-explain simple queries, corrupting the
rewritten_query
field with step-by-step noise. Implementing conditional CoT (applying reasoning only when
query_type == "complex"
) would have fixed multi-hop without breaking simple intent. Without a regression suite, you have no way to see that happen until users start reporting it.
The False Improvement Pattern, Visualised
The hidden trap of aggregate metrics in LLM evaluation: successive prompt engineering iterations (v1 to v4) successfully inflate the overall tracking score, but secretly cause a severe regression in negation accuracy, actively degrading the end-user experience. Image by Author
This is not a constructed worst case. It is the standard outcome of iterative prompt improvement without category-level tracking. Every change solves a real problem. Every change hides a real cost inside the aggregate metric.
The Architecture
The architecture of an automated prompt evaluation pipeline, designed to detect performance regressions by simulating output across multiple prompt versions and validating results against deterministic checks. Image by Author
Honest Design Decisions
The YAML parser in
loader.py
is a minimal, hand-written parser that handles string fields and multiline block scalars. I didn’t add PyYAML because adding a dependency to a framework designed to be auditable and easily cloned is the wrong trade-off. If you need YAML anchors or aliases in your prompt files, swapping in PyYAML is just a one-line change.
The deterministic simulator produces controlled degradation, not random noise. The specific queries that fail under each prompt version reflect real failure patterns from my production system. A different system with different instruction conflicts will have entirely different failure points. The framework is portable, but the degradation model is not. You need to write your own simulator based on the actual conflicts in your own prompt history.
The 10% regression threshold is arbitrary. I set it because it is the smallest change that is clearly not measurement noise in a deterministic system. For a medical triage system where
urgent_symptom
classification matters, I would set it at 5%. For a low-stakes recommendation system, 15% might be acceptable. The threshold is a parameter, not a principle.
The comparison category scores 0.0% across all four prompt versions. This is a known failure in the current prompt architecture, not a regression introduced by any of the four versions. The intent classifier does not have a comparative anchor resolution step, so queries that require comparing two entities across a shared attribute fail consistently. I have not hidden it or excluded it from the benchmark. It appears in every diff report with a
[KNOWN FAILURE]
annotation. A production regression suite should distinguish between expected failures that are tracked and regressions that are newly introduced. This benchmark makes that distinction explicit.
CRITICAL_CATEGORIES
currently covers
simple_intent
and
negation
. Adding a new critical category requires one line of code and a corresponding set of golden queries. The framework does not assume these two categories are universally important: they are important for my specific system.
How to Apply This in Your System
The validator and scorer are system-agnostic. Here is the minimum viable version—just enough to catch the “False Improvement” pattern before it hits production.
Start with 20 golden queries split across two categories. Pick the two types that handle your heaviest traffic, writing ten queries for each. For every single query, define the validation signature before writing the input itself. Being forced to articulate what correct behavior looks like is exactly what helps you select the right test cases. If you cannot write the signature, you don’t yet understand what the prompt is actually supposed to do for that query type.
Define two
CRITICAL_CATEGORIES
. These are the segments where a regression triggers an automatic ship block. For a customer support bot, that might be
refund_eligibility
and
escalation_trigger
; for a medical triage system, it’s
urgent_symptom
classification. The definition of “critical” is entirely system-specific, and this framework does not make assumptions about your requirements.
Run these tests before every prompt change, not after. Following the discipline Beck described [5], the suite runs before the code ships—never after the user reports a failure. The entire suite takes under two seconds to execute; there is no operational justification for delaying it.
Expand your golden set whenever a production bug surfaces. Every time a user reports a misclassification, add that query to the set along with its corresponding validation signature. Over time, the golden set becomes a comprehensive archive of your prompt’s entire historical failure surface.
Adjust the threshold for
CRITICAL_CATEGORIES
based on the impact of failure. The default 10% drop is just a starting point. For high-stakes categories, tighten the threshold to 5%. For low-stakes areas, 15% may be acceptable. Remember that the threshold is a parameter governed by the cost of failure, not a universal constant.
For the simulator, audit your prompt changelog. Every instruction introduced after the initial baseline represents a potential conflict. For each one, write a failure function that forces an output reflecting that specific conflict. If you added a routing priority rule, create a function that forces the misclassification of the query type that rule intercepts. The act of building this simulator forces you to map the prompt’s failure surface in a way manual testing never will.
Closing
Prompt engineering is not a one-time task. It is ongoing maintenance on a stochastic API. Every time you add an instruction to handle a new edge case, you are changing the behaviour of every query type the prompt already handles. Some of those changes are harmless. Some of them are silent collapses in categories you were not thinking about.
The regression suite does not prevent you from changing prompts. It tells you exactly what broke when you did.
Complete code:
https://github.com/Emmimal/prompt-regression-suite
Disclosure
All code in this article was written by me and is original work, developed and tested on Python 3.12, Windows 11, CPU only. The benchmark outputs are from real runs of
run_regression.py
and are fully reproducible by cloning the repository and running the entry point. The simulator produces deterministic outputs: the same run produces the same numbers every time. No LLM was called during benchmarking. The comparison query failure (0.0% across all four prompt versions) is a known architectural limitation of the current prompt design and is included in this benchmark unchanged. I have no financial relationship with any tool, library, or company mentioned in this article.
References
[1] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W.-t., Rocktäschel, T., Riedel, S., & Kiela, D. (2020).
Retrieval-augmented generation for knowledge-intensive NLP tasks
.
Advances in Neural Information Processing Systems, 33
, 9459–9474.
https://doi.org/10.48550/arXiv.2005.11401
[2] Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., Chi, E., Le, Q., & Zhou, D. (2022).
Chain-of-thought prompting elicits reasoning in large language models
.
Advances in Neural Information Processing Systems, 35
.
https://doi.org/10.48550/arXiv.2201.11903
[3] Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. Advances in Neural Information Processing Systems, 36, 46595–46623.
https://doi.org/10.48550/arXiv.2306.05685
[4] Sculley, D., Holt, G., Golovin, D., Davydov, E., Phillips, T., Ebner, D., Chaudhary, V., Young, M., Crespo, J.-F., & Dennison, D. (2015).
Hidden technical debt in machine learning systems
.
Advances in Neural Information Processing Systems, 28
, 2503–2511.
https://dl.acm.org/doi/10.5555/2969442.2969519
[5] Beck, K. (2002).
Test-Driven Development: By Example
. Addison-Wesley Professional.
If you found this useful, feel free to connect with me on LinkedIn and explore more of my work on my website.
I regularly share insights on LLM systems, prompt evaluation, and building reliable AI in production.
LinkedIn:
Emmimal P Alexander
Website:
EmiTechLogic
Written By
Emmimal P Alexander
See all from Emmimal P Alexander
Artificial Intelligence
,
Deep Dives
,
Llm
,
Prompt Engineering
,
Rag
Share This Article
Share on Facebook
Share on LinkedIn
Share on X
Towards Data Science is a community publication. Submit your insights to
				reach our global audience and earn through the TDS Author Payment
				Program.
Write for TDS
Related Articles
What Do Large Language Models “Understand”?
Artificial Intelligence
A deep dive on the meaning of understanding and how it applies to LLMs
Tarik Dzekman
August 21, 2024
31 min read
Making Sense of the Promise (and Risks) of Large Language Models
Artificial Intelligence
Our weekly selection of must-read Editors’ Picks and original features
TDS Editors
April 27, 2023
4 min read
Beware of Unreliable Data in Model Evaluation: A LLM Prompt Selection case study with Flan-T5
Artificial Intelligence
You may choose suboptimal prompts for your LLM (or make other suboptimal choices via model…
Chris Mauck
June 16, 2023
12 min read
Beating ChatGPT 4 in Chess with a Hybrid AI model
Artificial Intelligence
Better but not the best, GPT4 cheated but lost the match !
Octavio Santiago
January 22, 2024
7 min read
Semantic Search Engine for Emojis in 50+ Languages Using AI 😊🌍🚀
Artificial Intelligence
If you are on social media like Twitter or LinkedIn, you have probably noticed that…
Badr Alabsi, PhD
July 17, 2024
14 min read
If Oral and Written Communication Made Humans Develop Intelligence… What’s Up with Language Models?
Artificial Intelligence
Essay A discussion at the frontier between science and fiction. Human intelligence, with its extraordinary…
Luciano Abriata
June 30, 2023
15 min read
Throwing a Cat Among the Pigeons? Augmenting Human Computation With Large Language Models
Artificial Intelligence
I have always been fascinated by etymology. More often than not, there is an intriguing…
Ujwal Gadiraju
July 21, 2023
14 min read