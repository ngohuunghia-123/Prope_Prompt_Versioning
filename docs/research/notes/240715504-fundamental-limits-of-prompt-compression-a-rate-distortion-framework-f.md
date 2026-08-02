---
title: '[2407.15504] Fundamental Limits of Prompt Compression: A Rate-Distortion Framework
  for Black-Box Language Models'
id: 240715504-fundamental-limits-of-prompt-compression-a-rate-distortion-framework-f
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:17:14.154466Z'
source: https://arxiv.org/abs/2407.15504
source_domain: arxiv.org
fetched_at: '2026-08-02T03:17:14.150499Z'
fetch_provider: builtin
status: draft
type: note
tier: institutional
content_type: paper
deprecated: false
doi: arXiv:2407.15504
utility_score: 15.0
---

[2407.15504] Fundamental Limits of Prompt Compression: A Rate-Distortion Framework for Black-Box Language Models
Skip to main content
arXiv is now an independent nonprofit!
Learn more
×
Search arXiv
Press Enter to search ·
Advanced search
Computer Science > Machine Learning
arXiv:2407.15504
(cs)
[Submitted on 22 Jul 2024 (
v1
), last revised 11 Dec 2024 (this version, v2)]
Title:
Fundamental Limits of Prompt Compression: A Rate-Distortion Framework for Black-Box Language Models
Authors:
Alliot Nagle
,
Adway Girish
,
Marco Bondaschi
,
Michael Gastpar
,
Ashok Vardhan Makkuva
,
Hyeji Kim
View a PDF of the paper titled Fundamental Limits of Prompt Compression: A Rate-Distortion Framework for Black-Box Language Models, by Alliot Nagle and 5 other authors
View PDF
HTML (experimental)
Abstract:
We formalize the problem of prompt compression for large language models (LLMs) and present a framework to unify token-level prompt compression methods which create hard prompts for black-box models. We derive the distortion-rate function for this setup as a linear program, and provide an efficient algorithm to compute this fundamental limit via the dual of the linear program. Using the distortion-rate function as the baseline, we study the performance of existing compression schemes on a synthetic dataset consisting of prompts generated from a Markov chain, natural language queries, and their respective answers. Our empirical analysis demonstrates the criticality of query-aware prompt compression, where the compressor has knowledge of the downstream task/query for the black-box LLM. We show that there is a large gap between the performance of current prompt compression methods and the optimal strategy, and propose Adaptive QuerySelect, a query-aware, variable-rate adaptation of a prior work to close the gap. We extend our experiments to a small natural language dataset to further confirm our findings on our synthetic dataset.
Comments:
42 pages, 17 figures. Accepted to NeurIPS 2024
Subjects:
Machine Learning (cs.LG)
; Computation and Language (cs.CL); Information Theory (cs.IT)
Cite as:
arXiv:2407.15504
[cs.LG]
(or
arXiv:2407.15504v2
[cs.LG]
for this version)
https://doi.org/10.48550/arXiv.2407.15504
Focus to learn more
arXiv-issued DOI via DataCite
Submission history
From: Adway Girish [
view email
]
[v1]
Mon, 22 Jul 2024 09:40:13 UTC (2,367 KB)
[v2]
Wed, 11 Dec 2024 01:59:36 UTC (3,668 KB)
Full-text links:
Access Paper:
View a PDF of the paper titled Fundamental Limits of Prompt Compression: A Rate-Distortion Framework for Black-Box Language Models, by Alliot Nagle and 5 other authors
View PDF
HTML (experimental)
TeX Source
view license
Current browse context:
cs.LG
< prev
|
next >
new
|
recent
|
2024-07
Change to browse by:
cs
cs.CL
cs.IT
math
math.IT
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
IArxiv recommender toggle
IArxiv Recommender
(
What is IArxiv?
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