---
title: Criterion-referenceability determines LLM-as-a-judge validity across physics
  assessment formats
id: criterion-referenceability-determines-llm-as-a-judge-validity-across-physics-ass
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:35:20.480296Z'
source: https://arxiv.org/html/2603.14732v1
source_domain: arxiv.org
fetched_at: '2026-08-02T03:35:20.475296Z'
fetch_provider: builtin
status: draft
type: note
tier: institutional
content_type: paper
deprecated: false
utility_score: 18.0
---

Criterion-referenceability determines LLM-as-a-judge validity across physics assessment formats
Title:
Content selection saved. Describe the issue below:
Description:
arXiv is now an independent nonprofit!
Learn more
×
License: arXiv.org perpetual non-exclusive license
arXiv:2603.14732v1 [physics.ed-ph] 16 Mar 2026
Criterion-referenceability determines LLM-as-a-judge validity across physics assessment formats
Will Yeadon
Department of Physics, Durham University, Durham DH1 3LE, UK
Tom Hardy
Department of Physics, Durham University, Durham DH1 3LE, UK
Paul Mackay
Department of Physics, Durham University, Durham DH1 3LE, UK
Elise Agra
Department of Physics, Durham University, Durham DH1 3LE, UK
Abstract
As large language models (LLMs) are increasingly considered for automated assessment and feedback, understanding when LLM marking can be trusted is essential. We evaluate LLM-as-a-judge marking across three physics assessment formats - structured questions, written essays, and scientific plots - comparing GPT-5.2, Grok 4.1, Claude Opus 4.5, DeepSeek-V3.2, Gemini Pro 3, and committee aggregations against human markers under blind, solution-provided, false-solution, and exemplar-anchored conditions. For
n
=
771
n=771
blind university exam questions, models achieve fractional mean absolute errors (fMAE)
≈
0.22
\approx 0.22
with robust discriminative validity (Spearman
ρ
>
0.6
\rho>0.6
). For secondary and university structured questions (
n
=
1151
n=1151
), providing official solutions reduces MAE and strengthens validity (committee
ρ
=
0.88
\rho=0.88
); false solutions degrade absolute accuracy but leave rank ordering largely intact (committee
ρ
=
0.77
\rho=0.77
; individual models
ρ
≥
0.59
\rho\geq 0.59
). Essay marking behaves fundamentally differently. Across
n
=
55
n=55
scripts (
n
=
275
n=275
essays), blind AI marking is harsher and more variable than human marking, with discriminative validity already poor (
ρ
≈
0.1
\rho\approx 0.1
). Adding a mark scheme does not improve discrimination (
ρ
≈
0
\rho\approx 0
; all confidence intervals include zero). Anchored exemplars shift the AI mean close to the human mean and compress variance below the human standard deviation, but discriminative validity remains near-zero - distributional agreement can occur without valid discrimination. For code-based plot elements (
n
=
1400
n=1400
), models achieve exceptionally high discriminative validity (
ρ
>
0.84
\rho>0.84
) with near-linear calibration. Across all task types, validity tracks criterion-referenceability - the extent to which a task maps to explicit, observable grading features - and benchmark reliability, rather than raw model capability.
I
Introduction
As large language models (LLMs) become increasingly capable of solving physics problems, attention naturally turns to whether these models can also be trusted to assess student work. Early evaluations showed GPT-3.5 could not reliably pass an introductory physics course
[
17
]
, but recent models now surpass human participants on structured Physics Olympiad problems
[
38
]
, and multimodal systems outperform average post-instruction undergraduates on standard concept inventories
[
14
]
. Thus, if generating answers is now straightforward, the reliability of marking and feedback from LLMs becomes an open question. This performance jump makes “LLM-as-a-judge”
[
9
]
tempting as a scaling tool, but it also risks substituting unreliable automated marking for expensive human judgement.
There is a growing push to use AI for improved feedback
[
37
]
, but the practical applicability is strictly constrained by governance. In England, Ofqual has explicitly stressed that using AI as the sole mechanism for awarding marks is not compliant with current regulations
[
30
]
. Similarly, the European Union’s AI Act treats AI systems intended to evaluate learning outcomes as a “high-risk” use category
[
6
]
. If AI is to be used as an assistant or auditor, the core danger is not merely average marking error, but undetected systematic bias that would undermine fairness and trust.
Early work on LLM grading of physics problems has demonstrated feasibility at the level of introductory courses
[
18
]
, and subsequent psychometric analysis has investigated when agreement with human markers can be trusted
[
16
]
. Subsequent work on a real 252-student thermodynamics exam found that fine-grained rubrics can paradoxically reduce AI grading accuracy
[
15
]
, while comparisons of conventional machine learning and LLMs for classifying student concept use in physics show that LLMs offer competitive performance with far less task-specific engineering
[
12
]
. Partial-credit grading of physics explanations has shown that LLMs can approach human-level accuracy on structured items, but that confidence varies substantially across question types
[
3
]
. In higher education more broadly, comparisons between human and LLM grading of written exams find that aggregate-level agreement can mask significant item-level discrepancies
[
7
]
, while validity and reliability analyses of automated essay scoring reveal that apparent distributional agreement with human marks does not guarantee stable or valid scoring
[
31
]
. These findings converge on a concern already well-established in the general LLM-as-a-judge literature that aggregate metrics such as mean absolute error or correlation can be misleading because LLM judges exhibit systematic prompt-conditioned biases - including position bias, verbosity preferences, and anchoring to provided reference materials - that can inflate apparent agreement without improving genuine evaluation
[
54
,
9
]
. These biases have been taxonomised in detail such as by Wang et al. who identify systematic positional bias
[
42
]
, Ye et al. who quantify twelve distinct bias types across models
[
49
]
, and Panickssery et al. who demonstrate a causal link between self-recognition and self-preference in LLM evaluation
[
32
]
.
A critical but underexplored question in the physics education context is whether these failure modes are task-specific or general. Physics degree programmes require student output across qualitatively different modalities - structured mathematical derivations, scientific writing, and computational or visual artefacts - and it is plausible that AI marking reliability varies substantially across these formats. In this paper we use the term
criterion-referenceability
to denote the extent to which the features that justify a mark can be made explicit, inspected, and applied consistently across responses. Highly criterion-referenceable tasks allow markers to map observable properties of the response onto well-defined grading criteria, whereas weakly criterion-referenceable tasks rely more heavily on holistic judgement. Reference materials and exemplars can dramatically reshape AI marking behaviour, and a model that is criterion-referenced for a structured question may become an anchored distributor (distributing marks around a specific numerical anchor) when faced with open-ended prose. Further, this anchoring could potentially be influenced by showing the LLM a range of different examples of work receiving specific marks. When adding marking support converts an LLM from a genuine evaluator into a distribution-matcher, low mean absolute error (MAE) is not only insufficient as a validity criterion
[
26
]
but can be actively misleading
[
36
]
.
To investigate this, we evaluate LLM-as-a-judge marking across three assessment formats drawn from a single undergraduate physics programme, each representing a major category of student output. This within-programme comparative design allows task-format effects to be isolated from institution or subject confounds. This work contributes to a growing body of PER scholarship applying NLP and machine-learning methods to physics assessment and qualitative analysis
[
44
,
39
,
29
,
8
]
.
We address two research questions:
1.
How do LLM marking errors and discriminative validity compare across structured questions, essays, and scientific plots? By discriminative validity we mean the degree to which the marking system correctly rank-orders responses.
2.
To what extent does the informational structure of the marking prompt - specifically, the presence or absence of a model solution, a false solution, or anchored exemplars - alter both absolute accuracy and rank-ordering validity within each task type?
The first setting comprises 771 exam questions from Durham University (2018–2022) across ten modules ranging from foundational physics to advanced condensed matter and theoretical astrophysics. Under institutional constraints, solutions are not distributed alongside this data, forcing any automated system to operate blind. This mirrors the likely deployment setting in many departments where question security prevents releasing schemes, making “blind” automated marking the realistic baseline rather than an artificial handicap. Prior work in physics education research also shows that human graders often evaluate solutions based on visible reasoning and domain knowledge rather than strict rubric matching, especially across different instructional contexts
[
25
]
.
The second setting uses datasets where an answer key is available: OCR GCSE and A-Level Physics (2017–2021) and standard university textbook questions. These datasets allow us to test both blind and scheme-aware marking, quantifying the marginal value of giving models access to official solutions. We also include false solutions to isolate whether models independently verify the physics or simply match text patterns against the provided standard. For the structured-question datasets, the marked responses are AI-generated rather than authentic student submissions, so these results should be interpreted as evidence about marking validity on a controlled response pool, not as a direct estimate of classroom deployment performance.
The second and third settings comprise
n
=
275
n=275
physics essays combined into 55 scripts and
n
=
1400
n=1400
individual scientific plots, representing the written and computational output modalities of undergraduate physics. Together, the three task types span the range from highly criterion-referenced (structured questions with a known answer) to highly judgement-dependent (holistic essay marking), with plot evaluation occupying an intermediate position - visually grounded and rubric-constrained, but not reducible to a single short correct answer. This project received ethical approval from the Durham University physics ethics committee ref:
EDU-2023-03-14T14_02_18-hvxg44
.
II
Methods
II.1
Overview
This study evaluates contemporary large language models (LLMs) as automated marking tools across multiple physics assessment formats: structured exam questions, GCSE and A-Level problems with official mark schemes, university textbook questions, short-form physics essays, and scientific coding plots. The aim is not to benchmark answer-generation performance per se, but to assess the reliability, calibration, and agreement of LLM-as-a-judge marking validity relative to human markers.
The datasets used here build directly on prior work exploring AI performance on physics examinations
[
51
]
, blinded human-AI comparisons in essay assessment
[
50
]
and blinded human-AI comparisons in scientific plots
[
52
]
. Rather than focusing on answer generation quality, the present study treats LLMs explicitly as evaluators. The use of LLM committees as aggregated evaluators follows recent evidence that a diverse panel of models reduces intra-model bias and outperforms single-model judges across multiple settings
[
40
]
. Across all datasets, previously human-marked responses were re-evaluated via API calls to multiple LLMs under controlled prompting conditions. Within each task family, the same underlying response pool was marked across all models and experimental conditions, and prompts were held constant across providers apart from provider-specific formatting required by the API.
II.2
Question Datasets
For the structured physics questions, two datasets were used. Firstly, a set of university exam questions (
n
=
771
n=771
) drawn from Durham University examinations (2018–2022), spanning advanced condensed matter physics, foundations modules, mathematical methods, astrophysics, cosmology, and atomic/optical physics. The solutions to these questions are not made public, hence they serve as a “blinded” dataset. Secondly, a set of curriculum questions was sourced from UK GCSE (
n
=
350
n=350
), A-Level (
n
=
370
n=370
), and university textbook questions (
n
=
431
n=431
), giving
n
=
1151
n=1151
structured questions in total. These questions and answers are publicly available, hence they can be used to probe how the use of a mark scheme affects LLM marking. A full breakdown is shown in Table
1
.
Table 1:
Question sources by dataset level.
The curriculum subset (GCSE, A-Level, and textbook questions) contains
n
=
1151
n=1151
items and the exam subset contains
n
=
771
n=771
items.
Level
Source
Years
n
n
Exam
Advanced Condensed Matter Physics
2018–2022
154
154
Exam
Foundations of Physics 1 (paper 1)
2020–2022
26
26
Exam
Foundations of Physics 2A
2018–2022
112
112
Exam
Foundations of Physics 3A
2018–2022
110
110
Exam
Mathematical Methods in Physics
2018–2022
107
107
Exam
Modern Atomic and Optical Physics 3
2020–2022
34
34
Exam
Planets and Cosmology 3
2019–2022
61
61
Exam
Theoretical Astrophysics
2021–2022
19
19
Exam
Theoretical Physics 2
2018–2022
109
109
Exam
Theoretical Physics 3
2020–2022
39
39
Textbook
Physics for Scientists and Engineers
–
179
179
Textbook
Physics: Principles with Applications (7th ed.)
–
141
141
Textbook
College Physics 2e
–
111
111
A Level
OCR A-Level Physics A (papers 1, 2)
2017–2020
243
243
A Level
OCR A-Level Physics B (Advancing Physics)
2020–2021
127
127
GCSE
OCR GCSE Physics A (Gateway, papers 1–4)
2018–2020
260
260
GCSE
OCR GCSE Physics B (21st Century, papers 1, 3)
2017–2022
90
90
Total
2017–2022
1922
The original question pools were manually inspected. Poorly formatted, ambiguous, or incomplete items (primarily from extracted exam
.tex
files) were removed to improve dataset integrity and ensure comparability across marking conditions. The exam questions were marked by their respective question setters (
n
=
22
n=22
), which serve as the reference marks. The curriculum questions were marked by
n
=
3
n=3
human markers from Durham University taking a majority vote as the reference. All answers to the question dataset were AI generated; given modern AI systems can answer these questions nearly completely correctly, a set of answers generated by both GPT-4 and GPT-3.5 were used
[
51
]
. These AI-generated responses achieved moderate overall scores against human marking providing a pool of both correct and incorrect responses. The mean per-question fractional score was
52.0
%
52.0\%
for the exam dataset (marked by question setters) and
60.7
%
60.7\%
for the curriculum dataset (majority vote of three markers), with
56.6
%
56.6\%
of curriculum questions receiving full marks under the majority-vote reference. A breakdown of the marks available per question is shown in FIG.
1
: curriculum questions are heavily concentrated at 1–2 marks per item (reflecting the short-answer format of GCSE and A-Level papers), whereas exam questions are more broadly distributed between 3 and 6 marks, reflecting the multi-step derivation style of university assessments. The higher mark allocations associated with university questions reflect a more complex rubric structure: multi-step derivations require the marker to assess representation, strategy, application, and logical progression jointly
[
5
]
, a structure that a model marking without a scheme must infer from context alone.
Figure 1:
Distribution of marks available per question for the exams and curriculum datasets. Values above 10 marks (13/771 exam questions; 0 curriculum questions) are omitted for clarity.
A key pedagogical question for educators is how the mark scheme used influences LLM evaluations. Within individual institutions marking culture can vary widely
[
25
]
; hence we used three marking regimes for the structured questions:
1.
Blinded marking.
The model was instructed to assess scientific correctness without access to a mark scheme.
2.
With solution.
The model was instructed to compare the student response explicitly to the supplied solution and award marks strictly.
3.
With false solution.
To test for anchoring bias, models evaluated responses against a deliberately corrupted reference solution. This isolates whether the model independently verifies the physics or merely matches text patterns against the provided standard. False solutions were generated by requesting DeepSeek-V3.2 to apply one of five mechanical perturbations to the original answer: a factor-of-10 error, a sign flip, substitution of zero with a non-zero value, a multiple-choice swap, or doubling the main numerical value. The perturbation was required to produce an output visibly and unambiguously different from the correct answer while preserving surface formatting.
A methodological caveat is warranted regarding the use of AI-generated responses as the student answer pool for the structured-question datasets. Because the Durham exam solutions are not distributed and cannot be reconstructed from student scripts under institutional data constraints, authentic student responses are unavailable for this setting. Further, the curriculum questions are from online sources and are not directly taught at Durham University meaning there isn’t a pool of student answers to compare to. AI-generated answers were therefore used as a practical necessity rather than by design. These responses may exhibit systematically different error profiles compared with genuine student work. For example, AI answers may not approach problems using the methods taught on the course(s) which could plausibly inflate marking agreement by presenting models with responses closer to their own distributional expectations. The validity conclusions drawn from the structured-question datasets should therefore be interpreted as an upper bound on likely real-world performance. Where authorship effects can be tested directly (essays, scientific plots), we examine them in Section
III.4
.
II.3
Essay Dataset
For essays, we initially used
n
=
60
n=60
scripts each containing five short-form essays (
∼
300
{\sim}300
words each) graded holistically out of 100 in 5-point increments under standard UK classification bands. Because the five essays within each script were authored, submitted, and marked as a single submission, we chose a sample size of
n
=
60
n=60
rather than
n
=
300
n=300
. To create a series of exemplars, we took five submissions from the 5th, 25th, 50th, 75th, and 95th percentile of aggregated human marks leaving a final dataset size of
n
=
55
n=55
scripts and
n
=
275
n=275
individual essays.
Element-level scores are reported for distributional description but all inferential statistics (rank correlations, confidence intervals) are computed at the script level. Evaluations were conducted by five independent markers with prior experience in the module who were blinded to the authorship of the work. The dataset includes both human-authored and AI-authored essays to increase the range of quality represented; authorship is treated as a data-collection covariate and is not a variable of interest in the present study, which concerns the behaviour of the AI markers rather than the AI authors.
To establish a baseline for human marking variability, we calculated pairwise inter-rater reliability across the five independent markers. The average human–human MAE was
6.84
6.84
marks. Rank-order agreement between human markers was very limited, with an average pairwise Spearman correlation of just
ρ
=
0.054
\rho=0.054
and a single-rater Intraclass Correlation Coefficient (ICC2) of
0.035
0.035
(95% CI:
[
−
0.01
,
0.11
]
[-0.01,0.11]
). Such low reliability is not unusual in short-form holistic marking, but it implies that fine-grained rank ordering should be interpreted cautiously. This demonstrates that open-ended physics essay marking is an inherently noisy, highly subjective task where even expert human markers fail to reach consensus on rank ordering - a baseline essential for interpreting all AI essay marking results that follow. This noisy baseline is not a methodological flaw, but an authentic representation of the reality of holistic grading in higher education. Apparent agreement with an aggregated human score can in principle be achieved by matching the distribution of a weakly reliable benchmark rather than by validly discriminating essay quality. For essay-level comparisons against a single human reference, we use the unrounded mean of the five human markers for each script as the aggregated human score. Three marking conditions were employed for the essays:
1.
Blind.
The model was instructed to assess scientific correctness without access to a mark scheme.
2.
With scheme.
The model was instructed to assess scientific correctness with use of the guidance scheme, which contains general content taught in the course and potential ideas to include. This is the method that the human markers used.
3.
With scheme and anchor.
The model was instructed to use the guidance scheme and a set of five exemplars drawn from the dataset at the 5th, 25th, 50th, 75th, and 95th percentile of average marks awarded by the human markers, each appended to the system prompt along with their scores. These 25 exemplar essays were removed from the evaluation set, leaving
n
=
275
n=275
anchored-condition scores.
II.4
Scientific Plot Dataset
We use
n
=
1400
n=1400
graded scientific plots derived from 100 student and AI-generated submissions for the ‘Laboratory Skills and Electronics’ module at Durham University, evaluated blindly by three independent markers. The dataset includes 14 distinct plot types per submission, covering physics topics such as numerical integration, Monte Carlo methods, and the Newton-Raphson method. The AI-generated plots were created with and without prompt engineering as covered in detail in
[
52
]
. Examples of plots produced by GPT-3.5 and GPT-4 are shown in Appendix
A
. As the plots were submitted separately by the students we use
n
=
1400
n=1400
as the sample size. Each plot was manually scored out of 5 based on its quality and accuracy in elucidating the underlying physics.
For this module there is no specific mark scheme for the plots. Human markers assessed the plots using a 0–5 scale of general plot quality: a score of 5 indicates a scientifically correct and clear plot with sensible axes, units, labels, and scale, while 0 indicates a blank, irrelevant, or unreadable plot. The LLMs were given the same instructions as the human markers, making this a relatively natural evaluation of automated marking in a lower-stakes setting. Importantly, this is not a test of unconstrained visual physics reasoning. Each plot occurred at the end of a Jupyter notebook task, and the model was shown the completed notebook content up to the point where the plotting code would begin, together with the final plot image. The task is therefore best interpreted as rubric-constrained evaluation of a contextualised scientific visual output rather than full multimodal physics reasoning.
II.5
AI Models and Marking Conditions
To capture the current state of the art, we use five models from leading labs: GPT-5.2 (OpenAI), Claude Opus 4.5 (Anthropic), Gemini Pro 3 (Google DeepMind), DeepSeek-V3.2 (DeepSeek), and Grok 4.1 (xAI). The core instruction prompt for structured questions is shown in FIG.
2
. This instruction decomposes the evaluation into four explicit steps. Such structured prompting has been shown to improve zero-shot scoring accuracy in educational assessment settings
[
47
]
, and evaluation frameworks that incorporate intermediate reasoning (e.g. G-Eval) achieve stronger agreement with human graders than direct scoring approaches
[
23
]
. In principle Chain of Thought prompting
[
43
]
or elsewise reasoning tokens can be used when generating responses, however given the different API structures the amount of reasoning used between models is difficult to keep constant.
Pilot work on the curriculum dataset (Appendix
B
) indicates that explicit Chain of Thought prompting can reduce fractional MAE for the same model (DeepSeek-V3.2) across blind and solution conditions, while the
DeepSeek-Reasoner model that generates native reasoning tokens prior to the final output does not yield comparable improvements and in some conditions performs worse than the baseline. Because different providers implement intermediate reasoning in architecturally distinct ways - explicit Chain of Thought in the prompt or reasoning tokens within the API calls - and because the volume of intermediate reasoning cannot be held constant across APIs, the main experiments use direct JSON-output prompting throughout to ensure a controlled cross-model comparison. The absolute
error values reported in the main text should therefore be interpreted as conservative estimates for structured questions under direct-output prompting.
INSTRUCTIONS:
1. Mark the student response by comparing
it to the model solution.
2. Award a whole integer mark between 0
and [AVAILABLE MARKS] (inclusive).
3. Do not invent marking criteria beyond
what is implied by the solution.
4. If the student gives an alternative
correct method not shown in the solution,
award credit if it is clearly correct.

Return JSON exactly:
{"awarded_marks": integer}
Figure 2:
Core marking prompt used for structured questions (solution condition).
For the solution and false solution conditions, the system message was replaced with an audit-marker instruction directing the model to mark by comparing the student response to the provided model solution and to be strict about what earns credit. The question block was extended to include a
MODEL SOLUTION
field alongside the student response and available marks. Temperature was set to 0 to eliminate stochastic variation across repeated calls; pilot work, detailed in Appendix
C
, suggested temperature changes did not affect the marks produced by the models. For essays, models were instructed to act as expert university markers using the same grading scale (0–100 in 5-point increments). For plots, models were instructed to act as expert markers using the same 0–5 scale; at the time of writing Grok 4.1 and DeepSeek-V3.2 did not accept image input, so only the remaining three models were used. Committee scores were computed as the rounded mean of all individual model scores for each question - a transparent consensus estimator that preserves partial disagreement between models without introducing an additional fitted aggregation layer.
All marking was performed on the same response sets within each task family. Batch processing was used where supported by the provider API and elsewise requests were looped with standard exponential-backoff retries. All prompts used in this study are shown in Appendix
D
. In all settings, no post-processing was required to cap marks, as no model output exceeded the available maximum over all responses.
II.6
Evaluation Metrics
Agreement statistics are reported using Mean Absolute Error (MAE) and fractional MAE (MAE divided by available marks) as primary absolute-accuracy measures. Calibration curves
[
10
]
assess systematic bias across the mark range by comparing mean predicted fractional marks to mean human fractional marks within equal-width bins; “calibration” here refers to score-scale alignment rather than probabilistic confidence calibration. Discriminative validity is assessed independently of distributional alignment using Spearman rank correlation (
ρ
\rho
) and Quadratic Weighted Kappa (QWK)
[
4
]
, both of which measure the degree to which the model correctly ranks student responses by quality rather than merely matching the marginal distribution of marks. Reporting both absolute-accuracy and rank-ordering metrics is essential because a system can achieve low MAE and good score-scale alignment while entirely failing to distinguish between good and poor student work
[
26
,
36
]
.
For rank correlations on the essay dataset (
n
=
55
n=55
scripts), the effective sample size is small enough that
ρ
\rho
values carry substantial uncertainty. Confidence intervals for Spearman
ρ
\rho
are estimated by Fisher
z
z
-transformation:
z
=
\tfrac
​
12
​
ln
⁡
(
\tfrac
​
1
+
ρ
​
1
−
ρ
)
z=\tfrac{1}{2}\ln\!\left(\tfrac{1+\rho}{1-\rho}\right)
, with a 95% CI constructed as
z
±
1.96
/
n
−
3
z\pm 1.96/\sqrt{n-3}
and then back-transformed. Because essay marks are awarded in 5-point increments ties are common which makes fine-grained rank separation harder and should be considered when interpreting small differences in
ρ
\rho
.
III
Quantitative analysis of marking errors
III.1
Structured Question Marking
III.1.1
Exams
Across the 771 Durham exam questions under blind marking, fractional MAE is tightly clustered across models (GPT-5.2:
0.226
0.226
, Claude:
0.202
0.202
, Gemini:
0.218
0.218
, DeepSeek:
0.250
0.250
, Grok:
0.226
0.226
, committee:
0.216
0.216
), with only modest separation between the best-performing model (Claude,
0.202
0.202
) and the weakest (DeepSeek,
0.250
0.250
) (FIG.
3
). The committee aggregation (
0.216
0.216
) lies close to the model average, indicating that ensemble averaging provides limited additional benefit over the best individual model. These results are broadly consistent with prior feasibility work on LLM grading in introductory physics
[
18
]
, while extending that work to a multi-model comparison across introductory-to-advanced undergraduate content under strictly blinded conditions. The discriminative validity observed here is also consistent with prior findings that the structure and complexity of the assessment construct strongly influence the accuracy of automated scoring systems
[
53
]
.
Beyond absolute error, the models demonstrate robust discriminative validity under blinded conditions (Table
2
). Rank correlations against human marks remain strong (e.g., Claude: Spearman
ρ
=
0.690
\rho=0.690
, QWK
=
0.659
=0.659
; GPT-5.2:
ρ
=
0.646
\rho=0.646
, QWK
=
0.608
=0.608
), indicating that models successfully rank student responses by physics quality even without reference solutions.
Figure 3:
Exams (Durham, blinded;
n
=
771
n=771
): fractional MAE by model. GPT-5.2:
0.226
0.226
; Claude:
0.202
0.202
; Gemini:
0.218
0.218
; DeepSeek:
0.250
0.250
; Grok:
0.226
0.226
; Committee:
0.216
0.216
.
Across all conditions, absolute error shows a modest positive association with available marks (regression
R
2
R^{2}
: exams
0.199
0.199
, curriculum blind
0.190
0.190
, curriculum solution
0.209
0.209
), consistent with the idea that multi-step derivations require the marker to assess several co-dependent reasoning components simultaneously
[
5
]
. Blinded automated marking may therefore be somewhat less reliable for longer-form, higher-mark questions, although available marks explain only a limited fraction of the total error variance.
III.1.2
Curriculum questions
For GCSE, A-Level, and textbook questions (where mark schemes are available), providing the official solution consistently reduces fractional MAE across all models (GPT-5.2:
0.135
→
0.086
0.135\rightarrow 0.086
; Claude:
0.127
→
0.067
0.127\rightarrow 0.067
; Gemini:
0.094
→
0.071
0.094\rightarrow 0.071
; DeepSeek:
0.186
→
0.108
0.186\rightarrow 0.108
; Grok:
0.116
→
0.102
0.116\rightarrow 0.102
; committee:
0.131
→
0.085
0.131\rightarrow 0.085
) (FIG.
4
). All of these values sit above the dashed reference line in FIG.
4
at
0.054
0.054
which shows the human inter-rater conditional fractional MAE - the average error of each human marker against the majority-vote ground truth. This value is non-zero, confirming that even human markers occasionally disagree on whether a full-marks answer deserves full credit.
Figure 4:
Curriculum questions: fractional MAE by model (blind vs. solution vs. false solution) across GCSE (
n
=
350
n=350
), A-Level (
n
=
370
n=370
), and university textbooks (
n
=
431
n=431
). The human inter-rater fMAE (
n
=
3
n=3
) is also shown.
Providing a false solution dramatically degrades absolute performance for all models, with fractional MAE rising to approximately
0.22
0.22
–
0.38
0.38
(GPT-5.2:
0.383
0.383
; Claude:
0.251
0.251
; Gemini:
0.216
0.216
; DeepSeek:
0.364
0.364
; Grok:
0.385
0.385
; committee:
0.317
0.317
). This substantially exceeds the blind MAE for every model, confirming that the models attend to and defer to the provided reference rather than independently evaluating student responses on physical grounds. This deference to reference material mirrors experimental findings that LLMs exhibit statistically significant anchoring across providers
[
24
,
28
,
54
]
.
While the false solution significantly degrades absolute accuracy, it does not destroy discriminative validity. Under blind and correct-solution conditions, models show strong alignment with human rankings (e.g., Gemini blind
ρ
=
0.845
\rho=0.845
, QWK
=
0.860
=0.860
; Claude solution
ρ
=
0.885
\rho=0.885
, QWK
=
0.907
=0.907
). When exposed to the false solution, these correlations dip but remain robust (e.g., Gemini false
ρ
=
0.744
\rho=0.744
; Claude false
ρ
=
0.719
\rho=0.719
; Table
2
). For structured mathematical physics, models retain the ability to rank good answers above bad answers while shifting their absolute scoring penalty to align with the incorrect reference.
Table 2:
Discriminative validity (Spearman
ρ
\rho
and QWK) for structured questions across conditions. 95% CIs for
ρ
\rho
by Fisher
z
z
-transformation.
Dataset
Model
Condition
ρ
\rho
95% CI (
ρ
\rho
)
QWK
Exams
GPT-5.2
Blind
0.646
[
0.603
,
0.686
]
[0.603,0.686]
0.608
Claude Opus 4.5
Blind
0.690
[
0.651
,
0.725
]
[0.651,0.725]
0.659
Gemini Pro 3
Blind
0.634
[
0.590
,
0.675
]
[0.590,0.675]
0.627
DeepSeek-V3.2
Blind
0.606
[
0.559
,
0.649
]
[0.559,0.649]
0.548
Grok 4.1
Blind
0.640
[
0.596
,
0.680
]
[0.596,0.680]
0.637
Committee
Blind
0.696
[
0.658
,
0.731
]
[0.658,0.731]
0.650
Curriculum
GPT-5.2
Blind
0.803
[
0.781
,
0.823
]
[0.781,0.823]
0.846
Claude Opus 4.5
Blind
0.820
[
0.800
,
0.838
]
[0.800,0.838]
0.865
Gemini Pro 3
Blind
0.845
[
0.828
,
0.861
]
[0.828,0.861]
0.860
DeepSeek-V3.2
Blind
0.724
[
0.696
,
0.751
]
[0.696,0.751]
0.778
Grok 4.1
Blind
0.821
[
0.801
,
0.839
]
[0.801,0.839]
0.852
Committee
Blind
0.849
[
0.832
,
0.865
]
[0.832,0.865]
0.867
GPT-5.2
Solution
0.863
[
0.847
,
0.877
]
[0.847,0.877]
0.887
Claude Opus 4.5
Solution
0.885
[
0.872
,
0.897
]
[0.872,0.897]
0.907
Gemini Pro 3
Solution
0.873
[
0.859
,
0.886
]
[0.859,0.886]
0.877
DeepSeek-V3.2
Solution
0.817
[
0.797
,
0.836
]
[0.797,0.836]
0.849
Grok 4.1
Solution
0.828
[
0.809
,
0.846
]
[0.809,0.846]
0.858
Committee
Solution
0.885
[
0.872
,
0.897
]
[0.872,0.897]
0.898
GPT-5.2
False solution
0.640
[
0.605
,
0.673
]
[0.605,0.673]
0.735
Claude Opus 4.5
False solution
0.719
[
0.690
,
0.746
]
[0.690,0.746]
0.804
Gemini Pro 3
False solution
0.744
[
0.717
,
0.769
]
[0.717,0.769]
0.817
DeepSeek-V3.2
False solution
0.589
[
0.550
,
0.626
]
[0.550,0.626]
0.672
Grok 4.1
False solution
0.619
[
0.582
,
0.653
]
[0.582,0.653]
0.721
Committee
False solution
0.772
[
0.748
,
0.794
]
[0.748,0.794]
0.758
The full distribution of committee absolute errors shifts left when the correct solution is provided, indicating systematic improvement rather than isolated correction of outliers (FIG.
5
). Under the false solution condition the distribution shifts markedly right, with a pronounced secondary peak at fractional errors of
0.8
0.8
–
1.0
1.0
, corresponding to cases where the model awarded near-zero marks because the student’s correct answer differed substantially from the deliberately incorrect reference.
Figure 5:
Curriculum questions: distribution of committee fractional absolute error (blind vs. solution vs. false solution) across GCSE, A-Level, and textbook questions (
n
=
1151
n=1151
total).
To probe whether the effect of solution quality is concentrated on the hardest questions or is more uniform, FIG.
6
shows the conditional fractional MAE restricted to the
n
=
652
n=652
questions on which the human marker awarded full marks. In this subset, blind and solution-provided performance are broadly comparable (committee:
0.079
0.079
blind,
0.084
0.084
solution), indicating that for questions with unambiguously correct student responses, models are already close to ceiling under blind conditions. Under the false solution condition, however, conditional MAE rises sharply (committee:
0.474
0.474
), confirming that the effect is driven by active misdirection from the incorrect reference. Notably, the best-performing individual models under blind and solution conditions (Claude blind:
0.041
0.041
; Claude solution:
0.041
0.041
) outperform the human inter-rater conditional baseline on the full-marks subset, while the committee (
0.079
0.079
blind;
0.084
0.084
solution) sits modestly above it. The false solution condition exceeds the human baseline by a large margin for all models.
Figure 6:
Curriculum questions: conditional fractional MAE for questions on which the human awarded full marks (
n
=
652
n=652
). All models maintain low MAE under blind and solution conditions (
∼
0.04
{\sim}0.04
–
0.12
0.12
) but suffer large errors under the false solution (
∼
0.29
{\sim}0.29
–
0.60
0.60
).
Calibration curves across exams and curriculum questions lie close to the diagonal for the blind and solution cases with modest deviations in mid-to-high mark bins under blind conditions that are reduced when solutions are provided (FIG.
7
). Providing a false solution causes large deviations from the diagonal.
Figure 7:
Calibration curves for structured questions (fractional marks) across exams and curriculum conditions. The dashed diagonal represents perfect score-scale alignment.
III.2
Essay Marking
III.2.1
Mark distributions
FIG.
8
shows stacked distributions of human marks (
n
=
300
n=300
marker-level scores, mean
66.3
66.3
,
σ
=
6.1
\sigma=6.1
), AI blind pooled (mean
52.4
52.4
,
σ
=
11.0
\sigma=11.0
), AI scheme pooled (mean
53.6
53.6
,
σ
=
9.8
\sigma=9.8
), and AI scheme+anchor pooled (
n
=
275
n=275
, mean
64.0
64.0
,
σ
=
4.3
\sigma=4.3
). The reduced
n
n
in the anchored condition reflects the deliberate removal of the five exemplar scripts used for anchoring calibration, which were selected at the 5th, 25th, 50th, 75th, and 95th percentiles of the human mark distribution. All per-script inferential statistics (Spearman
ρ
\rho
, QWK, MAE, and calibration curves) are computed over the matched
n
=
55
n=55
scripts throughout, ensuring like-for-like comparisons across conditions; the
n
=
300
n=300
pooled distributions are shown for illustrative purposes only.
The human distribution is approximately unimodal, centred around
65
65
–
70
70
, with limited spread. Blind and scheme-only AI distributions are both shifted approximately 14 marks below the human mean and display considerably inflated variance. Adding the scheme alone provides negligible improvement: the scheme-only mean (
53.6
53.6
) is only 1.2 marks above the blind mean (
52.4
52.4
), and the variance reduction is modest (from
σ
=
11.0
\sigma=11.0
to
σ
=
9.8
\sigma=9.8
). By contrast, the scheme+anchor condition qualitatively transforms the distribution: the mean rises to
64.0
64.0
(within 2.3 marks of the human mean) and variance is compressed to
σ
=
4.3
\sigma=4.3
, below even the human standard deviation of
6.1
6.1
.
This distributional shift should not be read straightforwardly as improved essay evaluation. Because the human benchmark itself has very low inter-rater reliability, close matching of its overall mean and variance can in principle be achieved by learning the expected score distribution without learning to discriminate essay quality. Distributional agreement can occur in a low-reliability task.
Figure 8:
Essay mark distributions (stacked;
n
=
300
n=300
per condition except scheme+anchor where
n
=
275
n=275
): humans (
μ
=
66.3
\mu=66.3
,
σ
=
6.1
\sigma=6.1
), AI blind pooled (
μ
=
52.4
\mu=52.4
,
σ
=
11.0
\sigma=11.0
), AI scheme pooled (
μ
=
53.6
\mu=53.6
,
σ
=
9.8
\sigma=9.8
), AI scheme+anchor pooled (
μ
=
64.0
\mu=64.0
,
σ
=
4.3
\sigma=4.3
). Vertical lines indicate pooled means for each condition.
III.2.2
Essay MAE by model
Model-level MAE (marks out of 100) across blind, scheme, and scheme+anchor conditions is shown in FIG.
9
. Under blind conditions, MAE ranges from
9.6
9.6
(Grok) to
25.1
25.1
(Gemini) - a factor of more than
2.5
2.5
across models - indicating substantial model-to-model variation in default scoring leniency. Adding the scheme reduces MAE for GPT-5.2 (
11.0
→
8.7
11.0\rightarrow 8.7
) and Claude (
13.9
→
12.6
13.9\rightarrow 12.6
) but actually increases it for Grok (
9.6
→
14.5
9.6\rightarrow 14.5
) and DeepSeek (
12.9
→
13.7
12.9\rightarrow 13.7
), suggesting that a content-based scheme without distributional anchoring can shift some models toward different systematic biases. The scheme+anchor condition, by contrast, produces consistent and dramatic improvements across all models: MAE falls to
4.2
4.2
(GPT-5.2),
5.9
5.9
(Claude),
3.4
3.4
(Gemini),
3.0
3.0
(DeepSeek),
3.9
3.9
(Grok), and
3.2
3.2
for the committee, representing reductions of roughly
3
3
–
8
×
8\times
relative to blind marking. This wide inter-model variation is consistent with automated essay scoring findings showing that default LLM scoring behaviour reflects substantial leniency and variance shifts across model and task framing
[
31
,
7
]
. A broader reflection on the automated essay scoring field argues that benchmark-focused evaluation has systematically neglected construct validity and generalisation
[
21
]
, while rubric-based LLM essay grading can achieve high reliability when rubrics are sufficiently criterion-referenced
[
48
]
- a pattern consistent with the criterion-referenceability distinction introduced here.
These MAE values must be interpreted against the human baseline. The average human–human MAE of
6.84
6.84
marks means that the blind and scheme-only AI conditions (committee MAE
≈
13.4
\approx 13.4
) represent genuine underperformance - roughly double the inter-rater disagreement between expert human markers. Conversely, the anchored condition’s committee MAE of
3.16
3.16
marks is tighter than human markers are capable of achieving against each other. Rather than being evidence of superior marking, this indicates that anchored prompts can reduce error against a noisy aggregated benchmark by pulling model scores toward the centre of the observed human distribution.
Figure 9:
Essays: MAE by model. Committee MAE falls from 13.42 (blind) and 12.86 (scheme) to 3.16 with anchoring. The dashed line indicates the average human–human MAE of 6.84.
Calibration curves confirm that blind and scheme-only marking are systematically harsh relative to human markers (FIG.
10
): points fall substantially below the diagonal, indicating that when a model assigns a given fractional mark, the corresponding human fractional mark is consistently higher. As with the MAE results, however, improved score-scale alignment should not be equated with improved validity unless the system also preserves the ability to distinguish stronger from weaker essays.
III.2.3
Discriminative validity and anchoring bias
While anchored exemplars dramatically improve distributional alignment and MAE, discriminative validity remains absent throughout. We computed Spearman rank correlation (
ρ
\rho
) and QWK against the aggregated human scores (Table
3
).
Table 3:
Essay discriminative validity (Spearman
ρ
\rho
and QWK) by model and condition (
n
=
55
n=55
scripts). 95% CIs for
ρ
\rho
by Fisher
z
z
-transformation. Human–human average
ρ
=
0.054
\rho=0.054
(95% CI
[
−
0.21
,
0.31
]
[-0.21,0.31]
) and ICC2
=
0.035
=0.035
(95% CI
[
−
0.01
,
0.11
]
[-0.01,0.11]
).
Model
Condition
ρ
\rho
95% CI (
ρ
\rho
)
QWK
Human avg.
-
0.054
[
−
0.21
,
0.31
]
[-0.21,0.31]
-
GPT-5.2
Blind
0.109
[
−
0.15
,
0.35
]
[-0.15,0.35]
0.029
GPT-5.2
Scheme
0.006
[
−
0.25
,
0.26
]
[-0.25,0.26]
0.020
GPT-5.2
Scheme+anchor
−
0.021
-0.021
[
−
0.27
,
0.23
]
[-0.27,0.23]
0.023
Claude Opus 4.5
Blind
0.154
[
−
0.10
,
0.39
]
[-0.10,0.39]
0.020
Claude Opus 4.5
Scheme
0.049
[
−
0.21
,
0.30
]
[-0.21,0.30]
0.008
Claude Opus 4.5
Scheme+anchor
−
0.016
-0.016
[
−
0.27
,
0.24
]
[-0.27,0.24]
0.012
Gemini Pro 3
Blind
−
0.013
-0.013
[
−
0.27
,
0.25
]
[-0.27,0.25]
0.003
Gemini Pro 3
Scheme
−
0.103
-0.103
[
−
0.35
,
0.16
]
[-0.35,0.16]
−
0.011
-0.011
Gemini Pro 3
Scheme+anchor
0.112
[
−
0.15
,
0.36
]
[-0.15,0.36]
0.091
DeepSeek-V3.2
Blind
0.091
[
−
0.17
,
0.34
]
[-0.17,0.34]
0.023
DeepSeek-V3.2
Scheme
−
0.049
-0.049
[
−
0.30
,
0.21
]
[-0.30,0.21]
0.002
DeepSeek-V3.2
Scheme+anchor
0.016
[
−
0.25
,
0.28
]
[-0.25,0.28]
0.045
Grok 4.1
Blind
0.090
[
−
0.17
,
0.34
]
[-0.17,0.34]
0.048
Grok 4.1
Scheme
−
0.024
-0.024
[
−
0.28
,
0.23
]
[-0.28,0.23]
0.002
Grok 4.1
Scheme+anchor
0.034
[
−
0.22
,
0.28
]
[-0.22,0.28]
0.052
Committee
Blind
0.088
[
−
0.17
,
0.34
]
[-0.17,0.34]
0.019
Committee
Scheme
−
0.044
-0.044
[
−
0.29
,
0.21
]
[-0.29,0.21]
0.002
Committee
Scheme+anchor
0.034
[
−
0.22
,
0.28
]
[-0.22,0.28]
0.066
Even without anchoring, LLM essay discriminative validity is already poor. Under blind conditions, rank correlations are weak and near-zero (e.g., Claude Opus 4.5 blind:
ρ
=
0.154
\rho=0.154
, 95% CI
[
−
0.10
,
0.39
]
[-0.10,0.39]
; GPT-5.2 blind:
ρ
=
0.109
\rho=0.109
; Committee blind:
ρ
=
0.088
\rho=0.088
). A correlation of
ρ
≈
0.1
\rho\approx 0.1
is insufficient for a marking system intended to distinguish student performance: the model is only marginally better than chance at ordering essays by quality relative to the aggregated human benchmark. Adding the scheme does not improve discriminative validity: all scheme-condition
ρ
\rho
values remain near-zero and statistically indistinguishable from the blind values given the width of the confidence intervals (e.g., GPT-5.2 scheme:
ρ
=
0.006
\rho=0.006
, 95% CI
[
−
0.25
,
0.26
]
[-0.25,0.26]
; committee scheme:
ρ
=
−
0.044
\rho=-0.044
, 95% CI
[
−
0.29
,
0.21
]
[-0.29,0.21]
). The anchoring condition shows a similar pattern: committee
ρ
\rho
sits at
0.034
0.034
(95% CI
[
−
0.22
,
0.28
]
[-0.22,0.28]
), with individual models GPT-5.2 (
ρ
=
−
0.021
\rho=-0.021
) and Claude (
ρ
=
−
0.016
\rho=-0.016
) likewise consistent with zero. Across all three conditions, no model or committee achieves a
ρ
\rho
value whose confidence interval excludes zero, and the between-condition differences are far smaller than the within-condition uncertainty.
These metrics reveal a more subtle failure mode than simply “AI is bad at essays.” The human benchmark itself exhibits extremely weak rank reliability, so this essay format is already a poor instrument for stable single-rater ordering. Anchored exemplars allow the models to move much closer to the aggregated human score distribution while discriminative validity remains absent throughout. Anchoring reduces error against a noisy consensus-derived reference without solving the underlying validity problem; the models behave less like independent evaluators and more like systems inferring where marks are expected to lie on average.
Figure 10:
Essays: calibration curves by model and condition (blind vs. scheme vs. scheme+anchor; scheme+anchor uses
n
=
275
n=275
). The dashed diagonal represents perfect score-scale alignment. Blind and scheme-only conditions show systematic under-marking relative to human scores; anchoring improves score-scale alignment without recovering discriminative validity.
III.3
Code Plot Marking
For structured code-based plotting assignments (total out of 70 marks, aggregated across 14 plots per script), MAE values differ meaningfully across models: Gemini is the strongest performer (
4.2
4.2
marks), followed by Claude (
6.6
6.6
) and GPT-5.2 (
7.1
7.1
) (FIG.
11
). Human–human inter-rater MAE ranges from
2.42
2.42
(markers 1 vs. 3) to
5.15
5.15
(markers 2 vs. 3). Gemini’s MAE therefore falls within the range of human–human disagreement - a threshold psychometric approaches to AI-assisted grading identify as meaningful for conditional deployment
[
16
]
.
A detailed characterisation of the qualitative features that distinguish AI-generated from student-authored plots in this dataset including systematic differences in colour scheme, axis alignment, and layout is provided in prior work
[
52
]
, where the same submissions were evaluated for authorship detectability. The present results extend that analysis by showing that these surface differences do not substantially impair AI marking validity: despite the stylistic differences between student and AI-generated code, discriminative validity remains high (
ρ
>
0.84
\rho>0.84
across all models), suggesting the models are responding to rubric-relevant features of plot quality rather than authorship-correlated stylistic cues.
Discriminative validity on scientific plots is exceptionally strong - and contrasts sharply with the essay results. Rank correlations indicate tight alignment with human ranking preferences (Gemini:
ρ
=
0.881
\rho=0.881
, QWK
=
0.926
=0.926
; Claude:
ρ
=
0.909
\rho=0.909
, QWK
=
0.802
=0.802
; GPT-5.2:
ρ
=
0.838
\rho=0.838
, QWK
=
0.725
=0.725
). These values are an order of magnitude higher than those observed in essay marking under any condition, confirming that the models genuinely differentiate between good and poor visual data representation rather than merely matching a central score tendency. Calibration curves show close adherence to the diagonal for all three models across the central fractional range (FIG.
12
), with some overestimation in the lowest-score bin and near-perfect agreement in the upper range.
Figure 11:
Scientific plots: MAE by model (total mark out of 70) across
n
=
1400
n=1400
plot elements (100 scripts). Human–human inter-rater MAE ranges from
2.42
2.42
to
5.15
5.15
, providing a reference scale.
Figure 12:
Scientific plots: calibration (total fractional mark) across
n
=
1400
n=1400
plot elements (100 scripts). The dashed diagonal represents perfect score-scale alignment.
This strong performance should still be interpreted narrowly. The task here is not arbitrary graph interpretation or deep multimodal scientific reasoning, but contextualised judgement of plot quality within a constrained Jupyter notebook-based workflow. The result supports LLM/VLM use for rubric-constrained evaluation of scientific plots in this specific setting, not a broader claim that visual physics assessment is generally solved. GPT-4V has separately been shown to score student-drawn scientific models with moderate accuracy using structured prompting
[
20
]
, and benchmarking on scientific plot comprehension confirms that current multimodal LLMs achieve meaningful but imperfect understanding of standard matplotlib-style outputs
[
45
]
. The strong performance observed here is therefore best understood as reflecting the constrained, rubric-aligned nature of the task rather than general visual physics reasoning.
The pooled histogram (FIG.
13
) shows that human pooled scores (mean
76.8
%
76.8\%
,
σ
=
21.8
\sigma=21.8
) span a broader range than AI pooled scores (mean
72.2
%
72.2\%
,
σ
=
15.0
\sigma=15.0
). The AI distribution is more concentrated around the
75
75
–
85
%
85\%
band, consistent with a systematic tendency toward conservative central marking. The AI mean (72.2%) is 4.6 percentage points lower than the human mean (76.8%). Human markers differ by 2.42–5.15 marks on average (
≈
\approx
3.5–7.4% of the total score), indicating that the AI–human difference lies within the range of typical human grading disagreement.
Figure 13:
Scientific plots: total mark distributions (%) - pooled humans (
μ
=
76.8
%
\mu=76.8\%
,
σ
=
21.8
\sigma=21.8
;
n
=
300
n=300
) vs. pooled AI (
μ
=
72.2
%
\mu=72.2\%
,
σ
=
15.0
\sigma=15.0
;
n
=
300
n=300
). AI marking is slightly more conservative and exhibits reduced variance relative to human markers.
III.4
Authorship effects and the absence of self-preference bias
The structured-question responses evaluated in this study are AI-generated rather than human-authored. For the exam questions, this is due to assessment integrity and for the curriculum questions this is a result of the question content not being directly taught at the institution the research took place at: Durham University. To assess whether this affects the reliability of our validity conclusions, we examined authorship effects in the datasets where student answers were available: the essay and code datasets. In the essay dataset - where human markers assigned near-identical mean scores to human- and AI-authored work (
μ
=
66.2
\mu=66.2
vs.
66.4
66.4
; Mann–Whitney
p
=
0.31
p=0.31
) - AI models consistently exhibited higher MAE on AI-authored essays than on human-authored ones across all blind and scheme conditions (e.g., committee blind:
+
5.4
+5.4
marks). The AI models also assigned systematically lower raw scores to AI-authored text across nearly all conditions (
p
<
0.05
p<0.05
), a differential not observed in the human marking. This is the exact opposite of what a self-leniency or stylistic-familiarity bias would predict
[
32
]
. In the code dataset, AI models showed lower MAE on AI-generated code relative to student code, but AI-generated code also received genuinely lower human scores (mean
40.7
40.7
vs.
64.3
64.3
out of 70), making it difficult to disentangle marking accuracy from score-range compression. Taken together, the available evidence does not support the view that AI marking of AI-generated responses inflates validity estimates; if any authorship bias operates, it runs in the conservative direction.
IV
Qualitative analysis of marking errors
To better understand the specific mechanisms driving disagreements between human and AI markers, we qualitatively analysed the curriculum dataset, where blind, solution, and false solution conditions could be compared for the exact same items. Given that the exams lacked comparative conditions, the human essay baseline was too noisy for reliable error characterisation, and the scientific plots were already highly calibrated, our qualitative analysis focuses exclusively on the curriculum questions. We defined five distinct types of marking disagreement by isolating cases where all five AI models reached a unanimous verdict that contradicted the human reference mark:
1.
Blind over-crediting
: all models award full marks, human awards zero (
n
=
13
n=13
).
2.
Blind under-crediting
: all models award zero, human awards full marks (
n
=
9
n=9
).
3.
Over-crediting with solution
: all models award full marks despite a provided solution, human awards zero (
n
=
2
n=2
).
4.
Under-crediting with solution
: all models award zero despite a provided solution, human awards full marks (
n
=
12
n=12
).
5.
False solution anchoring
: all models award zero under the false solution condition for a question the human marked as fully correct (
n
=
5
n=5
).
Under blind conditions, 13 questions elicited unanimous full marks from the AI ensemble while the human reference awarded zero. Inspection of these cases reveals a consistent pattern. The GPT-3.5 responses typically contain numerically plausible answers with physically reasonable formatting, yet they are quantitatively incorrect - often due to an order-of-magnitude error, a missing unit conversion, or a misapplied physical assumption. Representative examples are shown in FIG.
14
. Questions are lightly paraphrased from standard textbook sources due to copyright. For brevity, the full GPT-3.5 answers are not shown, but are available for all curriculum questions in the supplementary material. The copyrighted questions are not shared. These instances are exclusively short-answer numerical problems worth a single mark, where the GPT-3.5 response correctly adopts scientific notation and appropriate units. Rather than independently verifying the underlying calculation, all five models accepted the mathematically flawed answers at face value. This behaviour aligns with the broader finding that LLMs heavily weight surface-level structural plausibility when no explicit reference solution is available.
Blind over-crediting (all AI = full marks, human = 0)
Q1.
Determine the total force on the bottom of a swimming pool (
28.0
×
8.5
​
m
28.0\times 8.5\;\mathrm{m}
, depth
1.8
​
m
1.8\;\mathrm{m}
).
Solution:
2.8
×
10
7
​
N
2.8\times 10^{7}\;\mathrm{N}
(1 mark)
Q2.
A man consumes 3000 kcal of food in one day. If he loses half this energy by evaporating water, calculate the mass of water evaporated.
Solution:
2.59 kg   (1 mark)
Figure 14:
Representative paraphrased questions where all five AI models awarded full marks under blind conditions, but the human marker awarded zero. The GPT-3.5 responses contain plausible but quantitatively incorrect final values (e.g., calculating the gauge force of 4,198,320 N rather than the absolute force target of
2.8
×
10
7
​
N
2.8\times 10^{7}\;\mathrm{N}
for Q1, and 2.76 kg instead of 2.59 kg for Q2).
When the models were provided with the correct official solutions, instances of over-crediting dropped sharply from 13 to 2, a reduction of 85%. Unlike the resolved cases, these two persistent errors highlight limitations in how LLMs utilize reference solutions (FIG.
15
). The first involves the lenient crediting of flawed physics. For instance, in Q3, the AI awards full marks to a mathematically structured but physically incorrect derivation (calculating the extra force on the entire base of the jug rather than just the cork) even though the final numerical value (
≈
5882
​
N
\approx 5882\;\mathrm{N}
) fails to match the reference solution (
5.76
×
10
3
​
N
5.76\times 10^{3}\;\mathrm{N}
). The second involves qualitative explanations. Here, the official solution provides a sample valid response but does not explicitly define the threshold for how rigorously the physics must be articulated. Consequently, the AI models leniently accept vague responses that the human marker rejects under stricter, rubric-specific interpretive standards.
Persistent over-crediting with solution (all AI = full marks, human = 0)
Q3.
A host pours wine remnants into a jug and inserts a cork (
2.00
​
cm
2.00\;\mathrm{cm}
diameter) in direct contact with the wine. Find the force on the cork.
Solution:
5.76
×
10
3
​
N
5.76\times 10^{3}\;\mathrm{N}
(1 mark)
Q4.
Ali uses a hot water bottle to keep warm and decides to switch to a heated seed pack. Suggest how a fair comparison could be made.
Solution:
Any one from: heat both in the same microwave for the same time at the same power…   (1 mark)
Figure 15:
Representative paraphrased questions where all five AI models awarded full marks despite being provided with the correct solution, contradicting the human score of zero. In these cases, the models leniently accept flawed physical derivations despite mismatched final numbers (Q3) or reward vague qualitative phrasing (Q4), failing to apply the stricter rubric standards utilized by the human marker.
Conversely, 9 questions produced unanimous AI zeros against a human verdict of full marks under blind conditions. Representative examples are shown in FIG.
16
. These under-crediting errors cluster into three distinct categories. The first involves Fermi estimation, where questions require order-of-magnitude estimates (e.g., the number of books in a library or annual gasoline consumption). While the human marker accepts the GPT-3.5 answer as falling within a reasonable physical range, the models reject it, struggling to evaluate answers that lack a single, verifiable target. The second category comprises tolerance-dependent numerical answers. Here, GPT-3.5’s answer differs from the textbook value by an amount within normal rounding or unit-conversion tolerances, but the models rigidly apply an exact-match criterion. Finally, under-crediting occurs in conceptual multi-step items requiring the explanation of a physical process. If GPT-3.5’s phrasing is physically sound but structurally diverges from the model’s internal formulation, the AI frequently penalises the response.
Under-crediting (all AI = 0, human = full marks)
Q5.
A soccer field is 100.0 m long; an American football field is 100.0 yd. Which is longer, and by how much (in yards)?
Solution:
9.4 yards   (1 mark)
Q6.
Estimate the number of books that can be shelved in a library with
3500
​
m
2
3500\;\mathrm{m}^{2}
of floor space (8 shelves high, 1.5 m corridors, books 25 cm tall and 4 cm wide).
Solution:
6
×
10
5
6\times 10^{5}
books   (1 mark)
Figure 16:
Representative paraphrased questions where all five AI models awarded zero, while the human marker awarded full marks. These instances highlight model rigidity regarding rounding tolerances (e.g., rejecting an exact calculation of
9.361
9.361
yards for Q5) and equivalent phrasings. Questions are lightly paraphrased from standard textbook sources.
Interestingly, whilst providing the correct solution reduced over-crediting errors it actually increased under-crediting errors, with the count rising from
n
=
9
n=9
to
n
=
12
n=12
. This asymmetry - where solutions resolve 85% of over-crediting but actually increase under-crediting - has a straightforward explanation. Over-crediting errors typically involve a model accepting a wrong answer because it looks structurally plausible; providing the correct answer gives the model a concrete numerical target that exposes the GPT-3.5 response’s flaw. Under-crediting errors, however, involve a model rejecting a correct answer because it does not match a narrow, expected format. Providing the reference answer does not help in these cases because the GPT-3.5 response’s physics is already correct. The model’s failure stems not from an ignorance of the correct physics, but from an inability to recognise equivalent, approximately equal, or alternatively phrased responses. Indeed, providing the solution appears to introduce additional under-crediting cases, possibly because the explicit reference gives the model a stricter template against which to reject otherwise valid phrasings.
This asymmetry motivates the criterion-referenceability idea - when a solution specifies an exact, unambiguous target, providing it resolves most over-crediting disagreements. However, when the acceptable answer space is broad such as in Fermi estimates, rounding tolerance bands, or multiple valid phrasings of a physical concept the solution alone fails to supply the structural logic required to map diverse responses onto the marking criteria.
Finally, the strength of the anchoring effect was acutely demonstrated by five multi-mark questions that produced unanimous AI zeros under the false solution condition, despite the human awarding full marks. These items included multi-step calculations, derivations, and data interpretation questions. In each case, the false solution was generated via a minor mechanical perturbation of the correct answer (as detailed in Section
II
). All five models subsequently marked the perfectly correct GPT-3.5 response as wrong solely because it failed to match the false solution. While this represents a small subset of the broader false solution degradation reported in Section
III.1
, the unanimity across all five state-of-the-art models on multi-step derivations underscores a critical vulnerability that even when GPT-3.5’s working is physically transparent and internally consistent, LLMs will reliably defer to a flawed reference solution rather than independently evaluating the physics.
V
Discussion
Overall, the results across the three task types present a coherent picture. For structured questions, models achieve moderate absolute accuracy and robust discriminative validity under blind conditions, with both improving when a correct solution is supplied and degrading when a false solution is supplied. For essays, absolute accuracy is poor under blind conditions and improves superficially with anchoring, but discriminative validity is indistinguishable from zero under all conditions (
ρ
≈
0.1
\rho\approx 0.1
blind,
ρ
≈
0
\rho\approx 0
scheme and anchored; all confidence intervals include zero). For scientific plots, both absolute accuracy and discriminative validity are strong without any reference material. LLM marking reliability is strongly task-dependent; it tracks not raw model capability but whether the assessment task is sufficiently criterion-referenceable that both humans and models can map observed features of the response onto a stable grading judgement.
V.1
Criterion-referenceability
The results highlight a useful conceptual distinction between tasks that are strongly criterion-referenceable and those that are not. Structured physics questions are the clearest example. Even without an official mark scheme, there is a relatively well-defined target such as a correct derivation, a correct numerical answer, or a recognisable set of physically valid intermediate steps. This explains why the models retain substantial discriminative validity under blind marking and why providing a correct solution improves absolute accuracy further. This distinction aligns with findings in science education research showing that assessment construct features - such as complexity, diversity, and structural transparency - strongly influence automated scoring accuracy
[
53
]
.
The code-plot task, while not reducible to a single short correct answer, is also substantially criterion-referenceable in practice. A scientifically good plot has identifiable properties including sensible axes, labels, units, scales, clarity of presentation, and consistency with the notebook context. The model was not asked to interpret an arbitrary graph in isolation but to judge a contextualised visual output embedded within a constrained notebook workflow - a setting sufficiently structured for reliable relative judgements.
The essays lie at the opposite end of this spectrum. The marker must balance academic content, relevance, argument structure, style, and overall coherence - judgements that are not necessarily illegitimate, but are less transparent and less easily stabilised across raters. The results suggest that once a task ceases to be strongly criterion-referenceable, both human and AI marking become vulnerable to distributional heuristics and central tendency effects. This likely reflects task structure at least as much as current model capability.
V.2
Committee aggregation
Across all three task types, the committee (rounded mean of all individual models) provides modest but consistent benefits for absolute accuracy without substantially altering discriminative validity. For structured questions and scientific plots, the committee tracks or marginally improves upon the best individual model (see Table
2
and Section
III.3
). The gains from aggregation are therefore incremental rather than transformative in settings where individual models already perform well, consistent with the general finding that ensemble averaging reduces idiosyncratic model errors but cannot compensate for systematic task-level limitations
[
40
]
.
The essay results illustrate the limits of committee aggregation more starkly. Under the anchored condition, the committee achieves the lowest MAE (3.16) of any configuration, yet its discriminative validity (
ρ
=
0.034
\rho=0.034
) remains indistinguishable from zero. Averaging over models that individually lack rank-ordering ability does not recover discriminative signal. This suggests that committee aggregation is most useful as variance reduction in criterion-referenceable settings and least useful in tasks where the underlying validity problem is shared across models. We note that more sophisticated aggregation strategies - such as weighting by per-model reliability or using median rather than mean scoring - might yield different results, but given that the committee’s primary limitation tracks the task-level validity ceiling rather than aggregation noise, such refinements are unlikely to alter the central conclusions.
V.3
Interpretation of the essay results
The essay findings should not be interpreted as evidence that LLMs are inherently poor at essay evaluation. A more precise interpretation is that this short-form holistic essay task provides a weak instrument for stable rank ordering. Human markers exhibited almost no pairwise rank agreement (
ρ
=
0.054
\rho=0.054
on average; ICC2
=
0.035
=0.035
), indicating that the benchmark against which models are evaluated is already highly noisy at the single-rater level. In such conditions, reductions in MAE relative to the aggregated human score do not necessarily indicate that the model has learned to evaluate essay quality more validly; they may instead reflect alignment with the central tendency of the human score distribution. This behaviour is most clearly visible under the anchored condition. Providing exemplars compresses the AI score distribution and shifts its mean toward the aggregated human mean, but this occurs without any accompanying improvement in discriminative validity, which remains indistinguishable from zero. In other words, the models better reproduce the distribution of human scores without improving their ability to distinguish between essays.
The human benchmark therefore forms part of the empirical result rather than serving solely as an external reference. For tasks involving substantial subjective judgement, the relevant question is not only whether AI scores agree with human scores, but also whether the human marking process itself supports meaningful ranking. If that condition is not met, apparent agreement with the human benchmark does not constitute evidence of valid assessment. This observation aligns with concerns raised in the automated essay scoring literature that distributional agreement with human benchmarks can be achieved without construct-valid discrimination
[
21
,
31
]
.
V.4
Implications for educators and assessment design
These findings suggest a practical diagnostic for educators considering AI-assisted marking. Before asking whether LLM-as-a-judge can be used to mark a task, one should first establish whether the task is sufficiently criterion-referenceable that human markers themselves assign stable and discriminative judgements. If human raters cannot achieve acceptable rank agreement, an LLM is unlikely to recover valid ordering merely by being given more examples or guidance. In such cases, AI may still be useful for feedback, idea extraction, or preliminary moderation, but should not be treated as a dependable scoring instrument. AI-generated feedback on physics conceptual questions has been found to require only minor or no human modification in roughly 70% of cases
[
41
]
, suggesting that even when AI scoring reliability is insufficient for summative grading, AI-assisted formative feedback may still be a defensible near-term application.
Conversely, where the task is tightly linked to identifiable criteria - as in structured questions and the Jupyter notebook-based plot task - AI marking appears much more defensible as an assistive tool. Even here, however, task complexity matters: error increases with available marks, implying that multi-step derivations remain harder to evaluate reliably than short, highly constrained responses. This points toward a layered deployment model, in which AI support is most appropriate for lower-mark or strongly criterion-bound components, with human oversight reserved for longer, more interpretive, or higher-stakes judgements.
A further practical implication concerns the use of exemplars. In human marking cultures, exemplar scripts are often employed to improve standardisation. The present results show that for LLM-as-a-judge exemplars can have qualitatively different effects depending on the task. In open-ended essay marking they may improve superficial agreement while undermining genuine discrimination. Educators should not assume that giving an LLM more marking support automatically improves validity. Polverini and Gregorčič provide practical guidance on how understanding LLM functioning can inform pedagogical deployment
[
34
]
, and Wulff reviews how AI can enhance language-related research and instruction in physics more broadly
[
46
]
.
V.5
Governance and deployment
These results reinforce the governance concerns raised in the Introduction. Regulatory caution around AI in marking is not merely a response to the novelty of the technology, but to a genuine measurement problem. A system that produces low average error while failing to distinguish stronger from weaker work is not a valid assessor, even if its output appears well calibrated on aggregate. This is especially important in educational settings, where marks are not only summaries of performance but mechanisms for ranking, progression, and access to opportunity. Holmes et al. propose a widely cited ethical framework for AI in education covering fairness, accountability, and transparency
[
11
]
, and recent work on synthetic data generation in PER highlights both the promise of LLM-based methods and the methodological care required when AI systems interact with educational data
[
13
]
.
Recent discussions within the science education research community similarly emphasise that questions of validity, reliability, and ethical oversight must be addressed jointly when integrating AI into educational practice
[
19
]
. Within this framework, the present findings are more consistent with an assistive or auditing role for AI than with autonomous grading. In strongly criterion-referenceable tasks, LLMs may be useful for preliminary marking, second marking, anomaly detection, or feedback generation. In weakly criterion-referenceable tasks - especially where human inter-rater reliability is already poor - AI outputs should be treated as descriptive aids rather than authoritative judgements. The key governance question is therefore not “does the AI look roughly right on average?”, but “does this task admit a sufficiently valid and reliable marking process for AI outputs to be trusted in the first place?”
Finally, the practical deployment of LLM-as-a-judge marking requires consideration of inference costs, which vary considerably across providers. In the context of automated marking, a model typically generates only a few output tokens (a numerical score in a JSON object), meaning that the financial cost of the task is overwhelmingly driven by the input token volume. At the time of this study, API pricing for flagship models was roughly an order of magnitude higher per million input tokens than for alternative models, with input costs for Claude Opus 4.5 ($5.00), GPT-5.2 ($2.50), and Gemini Pro 3 ($2.00) significantly outpacing those of DeepSeek-V3.2 ($0.28) and Grok 4.1 ($0.20). Given that the technical integration and inference speeds are broadly comparable across these platforms, institutions considering large-scale deployment must weigh these substantial cost differentials against performance and reliability, alongside relevant data security and privacy constraints.
V.6
OCR and multimodal constraints
While our evaluation provides a robust baseline for digital inputs, authentic physics assessments predominantly comprise handwritten derivations and spatial diagrams. Existing approaches - whether pipelined OCR-to-LaTeX or end-to-end vision-language models - show persistent performance gaps on handwritten mathematical input relative to digital text
[
18
,
22
,
27
,
1
]
, and the broader role of multimodal LLMs in science education remains under active development
[
2
]
.
Our finding that LLMs achieve high discriminative validity (
ρ
>
0.84
\rho>0.84
) on scientific plots must therefore be interpreted alongside the broader literature on multimodal physics reasoning. Evaluating the structural and presentational quality of a generated plot against a standardised rubric - with access to the notebook context preceding the plot - is a relatively constrained task; direct semantic interpretation of complex visual physics data is not. Polverini and Gregorčič demonstrate that large multimodal models frequently fail to extract accurate information from kinematics graphs, and further evaluations on electromagnetism assessments reveal persistent difficulties with spatial reasoning
[
33
,
35
]
. This distinction between reliable contextual rubric matching and unreliable perceptual inference delineates where current models can and cannot yet be trusted. Until the visual encoders of multimodal models achieve greater perceptual robustness, deployment of AI grading for handwritten and visually complex physics submissions requires psychometrically calibrated, human-in-the-loop frameworks in which low-confidence interpretations automatically trigger human review
[
16
]
.
V.7
Limitations and future work
Several limitations should be noted. The structured-question datasets and the essay/plot datasets differ not only in task format but also in authorship composition and marking context, so the paper identifies robust cross-task contrasts without claiming that task format is the sole determinant of performance. The scientific plot results should be interpreted narrowly; they concern contextualised Jupyter notebook-based plot evaluation, not handwriting, arbitrary diagram interpretation, or general multimodal physics reasoning. And the essay dataset itself demonstrates that some assessment formats may be too psychometrically noisy to support strong claims about fine-grained ranking, whether by humans or by AI.
All main experiments were performed at temperature 0 to minimise stochastic variation and isolate systematic differences between tasks and prompting conditions. It remains possible that modest increases in temperature would alter score variance or anchoring behaviour for particular models, however preliminary work in Appendix
C
suggests altering temperature does not significantly affect model behaviour. Further, given the scale of the differences observed between task types and prompt conditions, decoding settings are unlikely to overturn the central conclusion that criterion-referenceability and benchmark reliability dominate the validity of LLM-as-a-judge marking.
VI
Conclusion
This study evaluated LLM-as-a-judge marking validity across three qualitatively different physics assessment formats: structured questions, short-form essays, and scientific plots. The results show that automated marking performance is strongly task-dependent. For structured questions and rubric-constrained plot evaluation, models achieve moderate absolute accuracy and strong discriminative validity, often approaching the range of human–human disagreement. In contrast, essay marking exhibits fundamentally different behaviour: while anchored exemplars can improve distributional alignment and reduce mean absolute error, discriminative validity remains indistinguishable from zero across all conditions, including under strong anchoring.
Across all three task types, the observed validity pattern is best explained by criterion-referenceability and benchmark reliability rather than raw model capability. Where grading criteria can be explicitly linked to observable features of a response, LLMs can reproduce human-like ranking behaviour even under blinded conditions. Where assessment depends on holistic judgement and human raters themselves exhibit low reliability, agreement with human score distributions can be manufactured without meaningful discrimination between stronger and weaker work.
For educational practice, this implies that the key question is not simply whether LLM outputs appear reasonable on average, but whether the underlying assessment task admits a stable and interpretable marking process. In strongly criterion-referenceable contexts, LLMs may plausibly support assistive roles such as preliminary marking, moderation, anomaly detection, or feedback generation. In weakly criterion-referenceable tasks, however, automated scores should be interpreted cautiously and treated as descriptive aids rather than authoritative judgements. Future work should extend these findings to handwritten physics solutions and more complex multimodal assessments, where OCR errors and visual reasoning limitations may further constrain the reliability of automated marking systems.
References
[1]
S. Baral, L. Lucy, R. Knight, A. Ng, L. Soldaini, N. Heffernan, and K. Lo
(2025)
DrawEduMath: evaluating vision language models with expert-annotated students’ hand-drawn math images
.
In
Proceedings of the 2025 Conference of the Nations of the Americas Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)
,
Albuquerque, New Mexico
,
pp. 6902–6920
.
External Links:
Document
Cited by:
§V.6
.
[2]
A. Bewersdorff, C. Hartmann, M. Hornberger, K. Seßler, M. Bannert, E. Kasneci, and C. Nerdel
(2025)
Taking the next step with generative artificial intelligence: the transformative role of multimodal large language models in science education
.
Learning and Individual Differences
118
,
pp. 102601
.
External Links:
Document
Cited by:
§V.6
.
[3]
Z. Chen and T. Wan
(2024)
Using large language models to assign partial credit to students’ explanations of problem-solving process: grade at human level accuracy with grading confidence index and personalized student-facing feedback
.
External Links:
2412.06910
,
Link
Cited by:
§I
.
[4]
J. Cohen
(1968)
Weighted kappa: nominal scale agreement with provision for scaled disagreement or partial credit
.
Psychological Bulletin
70
(
4
),
pp. 213–220
.
External Links:
Document
Cited by:
§II.6
.
[5]
J. L. Docktor, J. Dornfeld, E. Frodermann, K. Heller, L. Hsu, K. A. Jackson, A. Mason, Q. X. Ryan, and J. Yang
(2016)
Assessing student written problem solutions: a problem-solving rubric with application to introductory physics
.
Physical Review Physics Education Research
12
(
1
),
pp. 010130
.
External Links:
Document
Cited by:
§II.2
,
§III.1.1
.
[6]
European Union
(2024)
Regulation (EU) 2024/1689 of the european parliament and of the council of 13 june 2024 laying down harmonised rules on artificial intelligence (artificial intelligence act)
.
External Links:
Link
Cited by:
§I
.
[7]
J. Flodén
(2025)
Grading exams using large language models: a comparison between human and AI grading of exams in higher education using ChatGPT
.
British Educational Research Journal
51
(
1
),
pp. 201–224
.
External Links:
Document
Cited by:
§I
,
§III.2.2
.
[8]
R. K. Fussell, E. M. Stump, and N. G. Holmes
(2024)
Drawing trustworthy claims from machine coding of qualitative data
.
Physical Review Physics Education Research
20
,
pp. 010113
.
External Links:
Document
Cited by:
§I
.
[9]
J. Gu, X. Jiang, Z. Shi, H. Tan, X. Zhai, C. Xu, W. Li, Y. Shen, S. Ma, H. Liu, S. Wang, K. Zhang, Z. Lin, B. Zhang, L. Ni, W. Gao, Y. Wang, and J. Guo
(2026)
A survey on llm-as-a-judge
.
The Innovation
,
pp. 101253
.
External Links:
ISSN 2666-6758
,
Document
Cited by:
§I
,
§I
.
[10]
C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger
(2017)
On calibration of modern neural networks
.
In
Proceedings of the 34th International Conference on Machine Learning (ICML)
,
Proceedings of Machine Learning Research
, Vol.
70
.
External Links:
Link
Cited by:
§II.6
.
[11]
W. Holmes, K. Porayska-Pomsta, K. Holstein, E. Sutherland, T. Baker, S. Buckingham Shum, O. C. Santos, M. T. Rodrigo, M. Cukurova, I. I. Bittencourt, and K. R. Koedinger
(2022)
Ethics of AI in education: towards a community-wide framework
.
International Journal of Artificial Intelligence in Education
32
(
3
),
pp. 504–526
.
External Links:
Document
Cited by:
§V.5
.
[12]
F. Kieser, P. Tschisgale, S. Rauh, X. Bai, H. Maus, S. Petersen, M. Stede, K. Neumann, and P. Wulff
(2024)
David vs. Goliath: comparing conventional machine learning and a large language model for assessing students’ concept use in a physics problem
.
Frontiers in Artificial Intelligence
7
,
pp. 1408817
.
External Links:
Document
Cited by:
§I
.
[13]
F. Kieser, P. Wulff, J. Kuhn, and S. Küchemann
(2023)
Educational data augmentation in physics education research using ChatGPT
.
Physical Review Physics Education Research
19
(
2
),
pp. 020150
.
External Links:
Document
Cited by:
§V.5
.
[14]
G. Kortemeyer, M. Babayeva, G. Polverini, R. Widenhorn, and B. Gregorcic
(2025)
Multilingual performance of a multimodal artificial intelligence system on multisubject physics concept inventories
.
Physical Review Physics Education Research
21
(
2
),
pp. 020101
.
External Links:
Document
Cited by:
§I
.
[15]
G. Kortemeyer, J. Nöhl, and D. Onishchuk
(2024)
Grading assistance for a handwritten thermodynamics exam using artificial intelligence: an exploratory study
.
Physical Review Physics Education Research
20
(
2
),
pp. 020144
.
External Links:
Document
Cited by:
§I
.
[16]
G. Kortemeyer and J. Nöhl
(2024)
Assessing confidence in AI-assisted grading of physics exams through psychometrics: an exploratory study
.
External Links:
2410.19409
,
Link
Cited by:
§I
,
§III.3
,
§V.6
.
[17]
G. Kortemeyer
(2023)
Could an artificial-intelligence agent pass an introductory physics course?
.
Physical Review Physics Education Research
19
(
1
),
pp. 010132
.
External Links:
Document
Cited by:
§I
.
[18]
G. Kortemeyer
(2023)
Toward AI grading of student problem solutions in introductory physics: a feasibility study
.
Physical Review Physics Education Research
19
(
2
),
pp. 020163
.
External Links:
Document
Cited by:
§I
,
§III.1.1
,
§V.6
.
[19]
M. Kubsch, M. Kastaun, P. Wulff, N. Graulich, M. Ariely, B. Gregorcic,
et al.
(2025)
Report on the scoping workshop on AI in science education research 2025
.
External Links:
2511.14318
Cited by:
§V.5
.
[20]
G. Lee and X. Zhai
(2025)
NERIF: GPT-4V for automatic scoring of drawn models
.
Journal of Science Education and Technology
.
External Links:
Document
Cited by:
§III.3
.
[21]
S. Li and V. Ng
(2024)
Automated essay scoring: a reflection on the state of the art
.
In
Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP)
,
pp. 17876–17888
.
External Links:
Document
Cited by:
§III.2.2
,
§V.3
.
[22]
T. Liu, J. Chatain, L. Kobel-Keller, G. Kortemeyer, T. Willwacher, and M. Sachan
(2024)
AI-assisted automated short answer grading of handwritten university level mathematics exams
.
arXiv preprint arXiv:2408.11728
.
External Links:
Link
Cited by:
§V.6
.
[23]
Y. Liu, D. Iter, Y. Xu, S. Wang, R. Xu, and C. Zhu
(2023)
G-Eval: NLG evaluation using GPT-4 with better human alignment
.
In
Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing (EMNLP)
,
pp. 2511–2522
.
External Links:
Document
Cited by:
§II.5
.
[24]
J. Lou and Y. Sun
(2026)
Anchoring bias in large language models: an experimental study
.
Journal of Computational Social Science
.
Note:
arXiv:2412.06593
External Links:
Document
Cited by:
§III.1.2
.
[25]
E. Marshman and C. Singh
(2017)
Contrasting grading approaches in introductory physics and quantum mechanics: the case of graduate teaching assistants
.
Physical Review Physics Education Research
13
(
1
),
pp. 010120
.
External Links:
Document
Cited by:
§I
,
§II.2
.
[26]
S. Messick
(1995)
Validity of psychological assessment: validation of inferences from persons’ responses and performances as scientific inquiry into score meaning
.
American Psychologist
50
(
9
),
pp. 741–749
.
External Links:
Document
Cited by:
§I
,
§II.6
.
[27]
O. Nath, H. Bathina, M. S. U. R. Khan, and M. M. Khapra
(2025)
Can vision-language models evaluate handwritten math?
.
In
Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)
,
Vienna, Austria
,
pp. 14784–14814
.
External Links:
Document
Cited by:
§V.6
.
[28]
J. K. Nguyen
(2024)
Human bias in AI models? Anchoring effects and mitigation strategies in large language models
.
Journal of Behavioral and Experimental Finance
43
,
pp. 100868
.
External Links:
Document
Cited by:
§III.1.2
.
[29]
T. O. B. Odden, H. Tyseng, J. T. Mjaaland, M. F. Kreutzer, and A. Malthe-Sørenssen
(2024)
Using text embeddings for deductive qualitative research at scale in physics education
.
Physical Review Physics Education Research
20
(
2
),
pp. 020151
.
External Links:
Document
Cited by:
§I
.
[30]
Ofqual
(2024-04)
Principles for the use of artificial intelligence in marking
.
External Links:
Link
Cited by:
§I
.
[31]
A. Pack, A. Barrett, and J. Escalante
(2024)
Large language models and automated essay scoring of english language learner writing: insights into validity and reliability
.
Computers and Education: Artificial Intelligence
6
,
pp. 100234
.
External Links:
Document
Cited by:
§I
,
§III.2.2
,
§V.3
.
[32]
A. Panickssery, S. R. Bowman, and S. Feng
(2024)
LLM evaluators recognize and favor their own generations
.
External Links:
2404.13076
Cited by:
§I
,
§III.4
.
[33]
G. Polverini and B. Gregorcic
(2024)
Evaluating vision-capable chatbots in interpreting kinematics graphs: a comparative study of free and subscription-based models
.
Frontiers in Education
9
,
pp. 1452414
.
External Links:
Document
Cited by:
§V.6
.
[34]
G. Polverini and B. Gregorcic
(2024)
How understanding large language models can inform the use of ChatGPT in physics education
.
European Journal of Physics
45
(
2
),
pp. 025701
.
External Links:
Document
Cited by:
§V.4
.
[35]
G. Polverini, J. Melin, E. Önerud, and B. Gregorcic
(2025)
Performance of chatgpt on tasks involving physics visual representations: the case of the brief electricity and magnetism assessment
.
Physical Review Physics Education Research
21
,
pp. 010100
.
Cited by:
§V.6
.
[36]
S. Shankar, J.D. Zamfirescu-Pereira, B. Hartmann, A. G. Parameswaran, and I. Arawjo
(2024)
Who validates the validators? aligning LLM-assisted evaluation of LLM outputs with human preferences
.
External Links:
2404.12272
,
Link
Cited by:
§I
,
§II.6
.
[37]
N. Thakkar, M. Yuksekgonul, J. Silberg, A. Garg, N. Peng, F. Sha, R. Yu, C. Vondrick, and J. Zou
(2026)
A large-scale randomized study of large language model feedback in peer review
.
Nature Machine Intelligence
,
pp. 1–11
.
Cited by:
§I
.
[38]
P. Tschisgale, H. Maus, F. Kieser, B. Kroehs, S. Petersen, and P. Wulff
(2025)
Evaluating GPT- and reasoning-based large language models on Physics Olympiad problems: surpassing human performance and implications for educational assessment
.
Physical Review Physics Education Research
21
(
2
),
pp. 020115
.
External Links:
Document
Cited by:
§I
.
[39]
P. Tschisgale, P. Wulff, and M. Kubsch
(2023)
Integrating artificial intelligence-based methods into qualitative research in physics education research: a case for computational grounded theory
.
Physical Review Physics Education Research
19
(
2
),
pp. 020123
.
External Links:
Document
Cited by:
§I
.
[40]
P. Verga, S. Hofstatter, S. Althammer, Y. Su, A. Piktus, A. Arkhangorodsky, M. Xu, N. White, and P. Lewis
(2024)
Replacing judges with juries: evaluating LLM generations with a panel of diverse models
.
External Links:
2404.18796
Cited by:
§II.1
,
§V.2
.
[41]
T. Wan and Z. Chen
(2024)
Exploring generative AI assisted feedback writing for students’ written responses to a physics conceptual question with prompt engineering and few-shot learning
.
Physical Review Physics Education Research
20
,
pp. 010152
.
External Links:
Document
Cited by:
§V.4
.
[42]
P. Wang, L. Li, L. Chen, Z. Cai, D. Zhu, B. Lin, Y. Cao, L. Kong, Q. Liu, T. Liu, and Z. Sui
(2024)
Large language models are not fair evaluators
.
In
Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (ACL 2024)
,
pp. 9440–9450
.
External Links:
Document
Cited by:
§I
.
[43]
J. Wei, X. Wang, D. Schuurmans, M. Bosma, F. Xia, E. Chi, Q. V. Le, D. Zhou,
et al.
(2022)
Chain-of-thought prompting elicits reasoning in large language models
.
Advances in neural information processing systems
35
,
pp. 24824–24837
.
Cited by:
§II.5
.
[44]
J. Wilson, B. Pollard, J. M. Aiken, M. D. Caballero, and H. J. Lewandowski
(2022)
Classification of open-ended responses to a research-based assessment using natural language processing
.
Physical Review Physics Education Research
18
,
pp. 010141
.
External Links:
Document
Cited by:
§I
.
[45]
C. Wu, Y. Ge, Q. Guo, J. Wang, Z. Liang, Z. Lu, Y. Shan, and P. Luo
(2025)
Plot2Code: a comprehensive benchmark for evaluating multi-modal large language models in code generation from scientific plots
.
In
Findings of the Association for Computational Linguistics: NAACL 2025
,
pp. 3006–3028
.
External Links:
Document
Cited by:
§III.3
.
[46]
P. Wulff
(2024)
Physics language and language use in physics—what do we know and how AI might enhance language-related research and instruction
.
European Journal of Physics
45
(
2
),
pp. 023001
.
External Links:
Document
Cited by:
§V.4
.
[47]
C. Xiao
et al.
(2024)
Applying large language models and chain-of-thought for automatic scoring
.
Computers and Education: Artificial Intelligence
.
External Links:
Document
Cited by:
§II.5
.
[48]
F. Yavuz
et al.
(2025)
Utilizing large language models for EFL essay grading: an examination of reliability and validity in rubric-based assessments
.
British Journal of Educational Technology
.
External Links:
Document
Cited by:
§III.2.2
.
[49]
J. Ye, Y. Wang, Y. Huang, D. Chen, Q. Zhang, N. Moniz, T. Gao, W. Geyer, C. Huang, P. Chen, N. V. Chawla, and X. Zhang
(2024)
Justice or prejudice? quantifying biases in LLM-as-a-judge
.
External Links:
2410.02736
Cited by:
§I
.
[50]
W. Yeadon, E. Agra, O. Inyang, P. Mackay, and A. Mizouri
(2024)
Evaluating ai and human authorship quality in academic writing through physics essays
.
European Journal of Physics
45
(
5
),
pp. 055703
.
Cited by:
§II.1
.
[51]
W. Yeadon and T. Hardy
(2024)
The impact of ai in physics education: a comprehensive review from gcse to university levels
.
Physics Education
59
(
2
),
pp. 025010
.
Cited by:
§II.1
,
§II.2
.
[52]
W. Yeadon, A. Peach, and C. Testrow
(2024)
A comparison of human, gpt-3.5, and gpt-4 performance in a university-level coding course
.
Scientific Reports
14
(
1
),
pp. 23285
.
Cited by:
Appendix A
,
§II.1
,
§II.4
,
§III.3
.
[53]
X. Zhai, P. He, and J. Krajcik
(2022)
Applying machine learning to automatically assess scientific models
.
Journal of Research in Science Teaching
59
(
10
),
pp. 1765–1794
.
External Links:
Document
Cited by:
§III.1.1
,
§V.1
.
[54]
L. Zheng, W. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Lin, Z. Li, D. Li, E. P. Xing, H. Zhang, J. E. Gonzalez, and I. Stoica
(2023)
Judging LLM-as-a-judge with MT-bench and chatbot arena
.
External Links:
2306.05685
,
Document
,
Link
Cited by:
§I
,
§III.1.2
.
Appendix A
Examples of AI scientific plots
Examples of scientific plots produced by GPT-4 with prompt engineering, the highest average AI scoring group (FIG.
17
) and GPT-3.5 without prompt engineering, the lowest average AI scoring group (FIG.
18
) are shown below. These plots were produced for a laboratory task requiring the student to visually demonstrate the independence of integration error scaling from dimension versus the number of points used for Monte Carlo integration of an
n
n
-dimensional unit ball. Further details regarding the plotting tasks and generative methodologies are given in
[
52
]
.
Figure 17:
Plot produced by GPT-4 with prompt engineering, demonstrating the error scaling for Monte Carlo integration of an
n
n
-dimensional unit ball.
Figure 18:
Plot produced by GPT-3.5 without prompt engineering, attempting to demonstrate the error scaling for Monte Carlo integration of an
n
n
-dimensional unit ball.
Appendix B
Sensitivity to reasoning and Chain of Thought
To assess whether reasoning affects marking validity, we ran the DeepSeek-V3.2 marking pipeline under two additional configurations on the curriculum dataset (
n
=
1151
n=1151
) across all three structured-question conditions:
1.
Explicit Chain of Thought.
DeepSeek-V3.2 was instructed to reason step by step before returning its JSON mark. Temperature was set to 0.
2.
Native reasoner.
The DeepSeek-Reasoner model, which generates internal reasoning tokens prior to the final output, was given the same direct-output prompts as the baseline (no explicit Chain of Thought instruction). The reasoner model does not accept a temperature parameter.
As shown in FIG.
19
, explicit Chain of Thought prompting reduced fMAE relative to the baseline across all three conditions (blind:
0.187
→
0.111
0.187\to 0.111
; solution:
0.114
→
0.068
0.114\to 0.068
; false solution:
0.370
→
0.254
0.370\to 0.254
). The improvement is largest in the blind condition (
≈
41
%
\approx 41\%
reduction), consistent with the interpretation that step-by-step reasoning helps the model catch numerical errors it would otherwise overlook under direct-output prompting.
The DeepSeek-Reasoner model presents a contrasting pattern. Under blind marking it slightly outperforms the Chain of Thought result (fMAE
=
0.106
=0.106
vs.
0.111
0.111
), but under the solution condition it performs worse than the direct-output baseline (
0.127
0.127
vs.
0.114
0.114
), and under the false solution condition it produces the highest fMAE of any configuration (
0.392
0.392
vs.
0.370
0.370
baseline). One possible interpretation is that the reasoner’s extended internal reasoning causes it to engage more deeply with the provided reference material, amplifying rather than mitigating the anchoring effect. Where CoT operates as an explicit pre-output verification step that can surface discrepancies between the student response and the model’s own physics knowledge, the reasoner’s native reasoning tokens may instead elaborate on the comparison to the supplied solution, reinforcing deference to the reference regardless of its correctness.
The Chain of Thought configuration preserves the ordering of conditions in the main text: providing a correct solution improves absolute accuracy relative to blind marking, and providing a false solution degrades it. Further, the reasoner shows no clear overall benefit compared to the baseline. We thus conclude that the task-structure conclusions that marking validity tracks criterion-referenceability and the quality of the reference material rather than the specific model are robust to the choice of prompting strategy.
Figure 19:
Fractional MAE for blind, solution-informed, and false solution marking conditions across three marking methods: baseline (
T
=
0
T=0
), explicit Chain of Thought prompting and the DeepSeek-Reasoner model. The dashed line shows human inter-rater fMAE (0.053) for reference.
Appendix C
Sensitivity to Decoding Temperature
To assess whether temperature affects marking validity, we ran the DeepSeek-V3.2 marking pipeline at
T
=
0.4
T=0.4
and
T
=
0.8
T=0.8
with five repeated runs each, comparing mean fMAE against the deterministic
T
=
0
T=0
baseline across all three conditions. As shown in FIG.
20
, fMAE was stable across temperatures in all conditions: blind marking ranged from 0.187 to 0.199, solution-informed marking from 0.112 to 0.114, and false solution marking from 0.359 to 0.370. Temperature is therefore not a meaningful source of variance in these results, and the
T
=
0
T=0
condition used throughout the main analysis is representative of model behaviour at higher sampling temperatures.
Figure 20:
Fractional MAE for blind, solution-informed, and false solution marking conditions across sampling temperatures
T
=
0
T=0
,
0.4
0.4
, and
0.8
0.8
. The dashed line shows human inter-rater fMAE (0.053) for reference. Results are means over five runs for
T
>
0
T>0
.
Appendix D
Prompts used
SYSTEM:
You are an expert university physics examiner acting as an audit marker.
Assess scientific correctness.
Do not assume access to a mark scheme.
Do not invent missing context.
Follow the output format exactly.

USER:
QUESTION:
[QUESTION]

STUDENT RESPONSE:
[STUDENT RESPONSE]

AVAILABLE MARKS:
[AVAILABLE MARKS]

INSTRUCTIONS:
1. Assess the scientific correctness of the response.
2. Award a whole integer mark between 0 and the available marks
   (inclusive).
3. Do not assume access to a mark scheme.
4. Base your judgement on standard university physics expectations.

Return JSON:
{"awarded_marks": integer}
Figure 21:
Prompt template used for structured-question blind marking.
SYSTEM:
You are an expert university physics examiner acting as an audit marker.
Mark by comparing the student response to the provided model solution.
Do not invent missing context.
Be strict about what earns credit.
Follow the output format exactly.

USER:
QUESTION:
[QUESTION]

MODEL SOLUTION:
[MODEL SOLUTION]

STUDENT RESPONSE:
[STUDENT RESPONSE]

AVAILABLE MARKS:
[AVAILABLE MARKS]

INSTRUCTIONS:
1. Mark the student response by comparing it to the model solution.
2. Award a whole integer mark between 0 and [AVAILABLE MARKS] (inclusive).
3. Do not invent marking criteria beyond what is implied by the solution.
4. If the student gives an alternative correct method not shown in the solution,
award credit if it is clearly correct.

Return JSON:
{"awarded_marks": integer}
Figure 22:
Prompt template used for structured-question marking with a supplied solution used for both the correct solution and the false solution cases.
SYSTEM:
You are an expert university physics examiner acting as an audit marker.
This is humanities-style physics / history / philosophy of science writing.
Assess accuracy, relevance, and argument quality.
Do not assume access to a mark scheme.
Do not invent missing context.
Be strict about what earns credit.
Follow the output format exactly.

USER:
PAPER: [PAPER CODE]

QUESTION ([QUESTION ID]):
[QUESTION TEXT]

STUDENT ESSAY RESPONSE:
[ESSAY TEXT]

AVAILABLE MARKS (for this essay only): 20

Return JSON exactly:
{"awarded_marks": integer}
Figure 23:
Prompt template used for blind essay marking.
SYSTEM:
You are an expert university physics examiner acting as an audit marker.
This is humanities-style physics / history / philosophy of science writing.
Mark by comparing the student response to the provided mark scheme /
model answer.
Do not invent missing context.
Be strict about what earns credit.
Follow the output format exactly.

USER:
PAPER: [PAPER CODE]

QUESTION ([QUESTION ID]):
[QUESTION TEXT]

MARK SCHEME / MODEL ANSWER (guidance):
[MODEL ANSWER OR GUIDANCE TEXT]

STUDENT ESSAY RESPONSE:
[ESSAY TEXT]

AVAILABLE MARKS (for this essay only): 20

Return JSON exactly:
{"awarded_marks": integer}
Figure 24:
Prompt template used for essay marking with the scheme/guidance text.
CALIBRATION EXAMPLES (for score calibration only):
These are real student responses with known human mean marks (out of 20).
Use them ONLY to calibrate what ~low / ~mid / ~high marks look like.
Do NOT copy phrases from them. Do NOT mention them.

--- $\approx$5th percentile (human mean 12.2/20) ---
Human mean mark (out of 20): 12.2
Student response:
[EXEMPLAR RESPONSE 1]

--- $\approx$25th percentile (human mean 13.0/20) ---
Human mean mark (out of 20): 13.0
Student response:
[EXEMPLAR RESPONSE 2]

--- $\approx$50th percentile (human mean 13.4/20) ---
Human mean mark (out of 20): 13.4
Student response:
[EXEMPLAR RESPONSE 3]

--- $\approx$75th percentile (human mean 13.6/20) ---
Human mean mark (out of 20): 13.6
Student response:
[EXEMPLAR RESPONSE 4]

--- $\approx$95th percentile (human mean 14.2/20) ---
Human mean mark (out of 20): 14.2
Student response:
[EXEMPLAR RESPONSE 5]

END CALIBRATION EXAMPLES.

NOW MARK THIS NEW RESPONSE:

PAPER: [PAPER CODE]

QUESTION ([QUESTION ID]):
[QUESTION TEXT]

MARK SCHEME / MODEL ANSWER (guidance):
[MODEL ANSWER OR GUIDANCE TEXT]

STUDENT ESSAY RESPONSE:
[ESSAY TEXT]

AVAILABLE MARKS (for this essay only): 20

Return JSON ONLY:
{"awarded_marks": integer}
Figure 25:
Prompt template used for essay marking with scheme plus anchored calibration exemplars.
SYSTEM:
You are an expert university physics examiner marking plotting outputs.
You do NOT have a mark scheme.
Mark each plot on correctness (scientific correctness + whether it
communicates clearly).
Return ONLY valid JSON.

USER:
ASSIGNMENT/TASK TEXT (what the student was asked to do):
[ASSIGNMENT TEXT]

INSTRUCTIONS:
Use this 0--5 anchor scale:
5 = scientifically correct and clear; axes/units/labels/scale sensible;
    presentation clean.
4 = scientifically correct; minor presentation issues (small
    label/legend/scale problems).
3 = mostly correct but at least one substantive weakness affecting
    interpretation.
2 = major scientific/presentation problems; plot gives wrong/unclear
    takeaway.
1 = mostly wrong or key requirements missing.
0 = blank/irrelevant/unreadable.

Return JSON:
{"awarded_marks": integer}

[IMAGE INPUT: submitted plot]
Figure 26:
Prompt template used for rubric-constrained marking of scientific plots.