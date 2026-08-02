---
title: '[2604.27789] Test Before You Deploy: Governing Updates in the LLM Supply Chain'
id: 260427789-test-before-you-deploy-governing-updates-in-the-llm-supply-chain
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:32.394739Z'
source: https://arxiv.org/abs/2604.27789
source_domain: arxiv.org
fetched_at: '2026-08-02T03:11:32.388740Z'
fetch_provider: builtin
status: draft
type: note
tier: institutional
content_type: paper
deprecated: false
doi: arXiv:2604.27789
utility_score: 17.0
---

[2604.27789] Test Before You Deploy: Governing Updates in the LLM Supply Chain
Skip to main content
arXiv is now an independent nonprofit!
Learn more
×
Search arXiv
Press Enter to search ·
Advanced search
Computer Science > Software Engineering
arXiv:2604.27789
(cs)
[Submitted on 30 Apr 2026]
Title:
Test Before You Deploy: Governing Updates in the LLM Supply Chain
Authors:
Mohd Sameen Chishti
,
Damilare Peter Oyinloye
,
Jingyue Li
View a PDF of the paper titled Test Before You Deploy: Governing Updates in the LLM Supply Chain, by Mohd Sameen Chishti and 2 other authors
View PDF
HTML (experimental)
Abstract:
Large Language Models (LLMs) are increasingly used as core dependencies in software systems. However, the hosted LLM services evolve continuously through provider-side updates without explicit version changes. These silent updates can introduce behavioral drift, causing regressions in functionality, formatting, safety constraints, or other application-specific requirements. Existing approaches focus primarily on regression testing or versioning but do not provide deployer-side mechanisms for governing compatibility during opaque model evolution. This paper proposes a deployment-side governance framework based on three components: clearly defined rules for how the model is allowed to behave (production contracts), focused testing organized by deployment risk categories (risk-category-based testing suite), and release checkpoints that block updates unless they meet defined safety and performance standards (compatibility gates). Through exploratory validation across multiple LLM versions, we provide evidence that targeted testing in specific risk areas can uncover performance regressions that overall metrics miss. We also identify several open research challenges, including how to systematically build effective test suites, how to set reliable performance thresholds in non-deterministic systems, and how to detect and explain model drift when providers offer limited transparency. Overall, we frame LLM update management as a software supply chain governance problem and outline a research agenda for putting deployer-side compatibility controls into practice.
Comments:
4 pages, 1 figure, accepted to The 2nd International Workshop on Large Language Model Supply Chain Analysis (LLMSC2026) co-located with FSE 2026
Subjects:
Software Engineering (cs.SE)
; Artificial Intelligence (cs.AI)
Cite as:
arXiv:2604.27789
[cs.SE]
(or
arXiv:2604.27789v1
[cs.SE]
for this version)
https://doi.org/10.48550/arXiv.2604.27789
Focus to learn more
arXiv-issued DOI via DataCite
Related DOI
:
https://doi.org/10.1145/3803437.3805535
Focus to learn more
DOI(s) linking to related resources
Submission history
From: Jingyue Li Prof. [
view email
]
[v1]
Thu, 30 Apr 2026 12:32:13 UTC (141 KB)
Full-text links:
Access Paper:
View a PDF of the paper titled Test Before You Deploy: Governing Updates in the LLM Supply Chain, by Mohd Sameen Chishti and 2 other authors
View PDF
HTML (experimental)
TeX Source
view license
Current browse context:
cs.SE
< prev
|
next >
new
|
recent
|
2026-04
Change to browse by:
cs
cs.AI
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