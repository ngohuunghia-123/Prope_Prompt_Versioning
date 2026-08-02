---
title: '[2601.22025] When Generic Prompt Improvements Hurt: Evaluation-Driven Iteration
  for LLM Applications'
id: 260122025-when-generic-prompt-improvements-hurt-evaluation-driven-iteration-for
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:17:09.840885Z'
source: https://arxiv.org/abs/2601.22025
source_domain: arxiv.org
fetched_at: '2026-08-02T03:17:09.837884Z'
fetch_provider: builtin
status: draft
type: note
tier: institutional
content_type: paper
deprecated: false
doi: arXiv:2601.22025
utility_score: 18.0
citation_count: 0
is_retracted: false
---

[2601.22025] When Generic Prompt Improvements Hurt: Evaluation-Driven Iteration for LLM Applications
Skip to main content
arXiv is now an independent nonprofit!
Learn more
×
Search arXiv
Press Enter to search ·
Advanced search
Computer Science > Computation and Language
arXiv:2601.22025
(cs)
[Submitted on 29 Jan 2026 (
v1
), last revised 9 Jun 2026 (this version, v2)]
Title:
When Generic Prompt Improvements Hurt: Evaluation-Driven Iteration for LLM Applications
Authors:
Daniel Commey
View a PDF of the paper titled When Generic Prompt Improvements Hurt: Evaluation-Driven Iteration for LLM Applications, by Daniel Commey
View PDF
HTML (experimental)
Abstract:
Evaluating Large Language Model (LLM) applications differs from conventional software testing because outputs are probabilistic, semantically variable, and sensitive to prompt and model changes. This technical report proposes the Minimum Viable Evaluation Suite (MVES), an audit-oriented structure for application-level LLM evaluation. MVES links application categories to failure modes, metrics, required artifacts, and validation evidence across general LLM applications, retrieval-augmented systems, and agentic workflows. We pair the framework with a reproducible local evaluation harness covering structured extraction, RAG citation/content-compliance, and instruction-following checks. Using Ollama with Llama 3 8B Instruct and Qwen 2.5 7B Instruct, we evaluate five prompt conditions over expanded 30-case-per-suite ablations. The results show that, in the tested local conditions, generic prompt additions do not produce monotonic improvements: stronger output-contract prompts improve strict extraction for both models, while RAG citation/content-compliance declines under some generic-rule conditions. The largest observed decline occurs for Qwen 2.5 on RAG when generic rules are appended to the user prompt, from 26/30 to 9/30. These findings support evaluation-driven prompt iteration: prompt changes should be treated as potential regression risks and tested against task-specific suites before deployment. The accompanying repository contains the test suites, prompt variants, evaluation harness, raw result logs, and scripts needed to reproduce the reported local ablations.
Comments:
Technical report. 42 pages, 3 figures. Code, test suites, and result logs:
this https URL
Subjects:
Computation and Language (cs.CL)
; Artificial Intelligence (cs.AI); Information Retrieval (cs.IR); Software Engineering (cs.SE)
Cite as:
arXiv:2601.22025
[cs.CL]
(or
arXiv:2601.22025v2
[cs.CL]
for this version)
https://doi.org/10.48550/arXiv.2601.22025
Focus to learn more
arXiv-issued DOI via DataCite
Submission history
From: Daniel Commey [
view email
]
[v1]
Thu, 29 Jan 2026 17:32:34 UTC (41 KB)
[v2]
Tue, 9 Jun 2026 23:57:32 UTC (44 KB)
Full-text links:
Access Paper:
View a PDF of the paper titled When Generic Prompt Improvements Hurt: Evaluation-Driven Iteration for LLM Applications, by Daniel Commey
View PDF
HTML (experimental)
TeX Source
view license
Current browse context:
cs.CL
< prev
|
next >
new
|
recent
|
2026-01
Change to browse by:
cs
cs.AI
cs.IR
cs.SE
References & Citations
NASA ADS
Google Scholar
Semantic Scholar
export BibTeX citation
Loading...
BibTeX formatted citation
×
loading...
Data provided by:
Bookmark
Bibliographic Tools
Bibliographic and Citation Tools
Bibliographic Explorer Toggle
Bibliographic Explorer
(
What is the Explorer?
)
Connected Papers Toggle
Connected Papers
(
What is Connected Papers?
)
Litmaps Toggle
Litmaps
(
What is Litmaps?
)
scite.ai Toggle
scite Smart Citations
(
What are Smart Citations?
)
Code, Data, Media
Code, Data and Media Associated with this Article
alphaXiv Toggle
alphaXiv
(
What is alphaXiv?
)
Links to Code Toggle
CatalyzeX Code Finder for Papers
(
What is CatalyzeX?
)
DagsHub Toggle
DagsHub
(
What is DagsHub?
)
GotitPub Toggle
Gotit.pub
(
What is GotitPub?
)
Huggingface Toggle
Hugging Face
(
What is Huggingface?
)
ScienceCast Toggle
ScienceCast
(
What is ScienceCast?
)
Demos
Demos
Replicate Toggle
Replicate
(
What is Replicate?
)
Spaces Toggle
Hugging Face Spaces
(
What is Spaces?
)
Spaces Toggle
TXYZ.AI
(
What is TXYZ.AI?
)
Related Papers
Recommenders and Search Tools
Link to Influence Flower
Influence Flower
(
What are Influence Flowers?
)
Core recommender toggle
CORE Recommender
(
What is CORE?
)
Author
Venue
Institution
Topic
About arXivLabs
arXivLabs: experimental projects with community collaborators
arXivLabs is a framework that allows collaborators to develop and share new arXiv features directly on our website.
Both individuals and organizations that work with arXivLabs have embraced and accepted our values of openness, community, excellence, and user data privacy. arXiv is committed to these values and only works with partners that adhere to them.
Have an idea for a project that will add value for arXiv's community?
Learn more about arXivLabs
.
Which authors of this paper are endorsers?
|
Disable MathJax
(
What is MathJax?
)