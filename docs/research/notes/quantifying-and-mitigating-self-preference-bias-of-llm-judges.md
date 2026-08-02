---
title: Quantifying and Mitigating Self-Preference Bias of LLM Judges
id: quantifying-and-mitigating-self-preference-bias-of-llm-judges
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:10:59.428518Z'
source: https://arxiv.org/html/2604.22891v2
source_domain: arxiv.org
fetched_at: '2026-08-02T03:10:59.407518Z'
fetch_provider: builtin
status: draft
type: note
tier: institutional
content_type: paper
deprecated: false
utility_score: 16.0
---

Quantifying and Mitigating Self-Preference Bias of LLM Judges
Title:
Content selection saved. Describe the issue below:
Description:
arXiv is now an independent nonprofit!
Learn more
×
License: CC BY 4.0
arXiv:2604.22891v2 [cs.LG] 28 Apr 2026
Quantifying and Mitigating Self-Preference Bias of LLM Judges
Jinming Yang
yangjinming@std.uestc.edu.cn
Chuxian Qiu
chuxianqiu@std.uestc.edu.cn
Zhenyu Deng
zhenyudeng@std.uestc.edu.cn
Xinshan Jiao
jiaoxinshan@std.uestc.edu.cn
Tao Zhou
zhutou@ustc.edu
CompleX Lab, School of Computer Science and Engineering, University of Electronic Science and Technology of China, Chengdu, China
Abstract
LLM-as-a-Judge has become a dominant approach in automated evaluation systems, playing critical roles in model alignment, leaderboard construction, quality control, and so on. However, the scalability and trustworthiness of this approach can be substantially distorted by Self-Preference Bias (SPB), which is a directional evaluative deviation in which LLMs systematically favor or disfavor their own generated outputs during evaluation. Existing measurements rely on costly human annotations and conflate generative capability with evaluative stance, and thus are impractical for large-scale deployment in real-world systems. To address this issue, we introduce a fully automated framework to quantifying and mitigating SPB, which constructs equal-quality pairs of responses with negligible quality differences, enabling statistical disentanglement of discriminability from bias propensity without human gold standards. Empirical analysis across 20 mainstream LLMs reveals that advanced capabilities are often uncorrelated, or even negatively correlated, with low SPB. To mitigate this bias, we propose a structured multi-dimensional evaluation strategy grounded in cognitive load decomposition, which reduces SPB by 31.5% on average.
keywords:
Large language models , LLM-as-a-Judge , Self-preference bias , Bias quantification , Bias mitigation , Cognitive load decomposition
1
Introduction
Recently, LLM-as-a-Judge has emerged as a dominant paradigm for replacing costly human evaluation, playing a critical role in model alignment and leaderboard construction
(Zheng
et al.
,
2023
; Liu
et al.
,
2023
)
. This paradigm has found widespread adoption across diverse expert system applications, including automated content quality assessment in information retrieval systems, reward modeling for reinforcement learning from human feedback (RLHF), and the construction of evaluation benchmarks for comparing competing LLM architectures. Platforms such as Chatbot Arena and LMSYS rely extensively on automated model-based evaluation to rank and compare LLM performance at scale, making the reliability of such evaluation mechanisms a matter of critical practical importance.
The core assumption underlying this paradigm is fairness, namely the increasing model scale and stronger reasoning capabilities will naturally lead models to overcome bias and act as more objective evaluators. However, current evaluation approaches are constrained by two critical limitations. First, they rely heavily on costly and poorly scalable human gold standards. To establish evaluation benchmarks, previous studies often depend on large-scale expert annotation, a process that is both resource-intensive and misaligned with fast-paced model evolution
(Chiang and Lee,
2023
)
. As the number of candidate models grows and task domains diversify, maintaining up-to-date human gold standards becomes increasingly prohibitive for real-world deployment. Second, they conflate capability with Self-Preference Bias (SPB). When a strong model selects its own output, conventional metrics based on deviation from gold standards cannot reliably tell whether the preference arises from higher quality or from self-identification
(Panickssery
et al.
,
2024
; Liu
et al.
,
2024
)
. This conflation presents a fundamental challenge for any automated evaluation system that aims to serve as a trustworthy expert judge.
Figure 1:
Overview of the SPB quantification and mitigation framework. The workflow comprises five stages: (a) constructing equal-quality pairs via dual benchmarks to statistically isolate bias from generation quality; (b) verifying judgment capability on high-contrast sets to exclude incompetent randomizers; (c) quantifying SPB by decoupling the Probabilistic Inclination Ratio (PIR) from the baseline Null-PIR; (d) classifying models into four archetypes based on capability and bias; and (e) mitigating bias via structured multi-dimensional evaluation.
To address this methodological dilemma, we introduce a fully automated framework for SPB quantification and mitigation, as illustrated in Fig.
1
. Unlike approaches that rely on human judges, our core intuition is grounded in comparisons across multiple reference models instead of gold-standard judgments. By pairing responses whose score differences fall below a perceptual threshold, namely the
ε
\varepsilon
-bandwidth, we construct equal-quality pairs wherein quality differences are negligible. Under such conditions, model choices are less likely to be driven by intrinsic quality gaps between responses, allowing subsequent analyses to assess SPB with reduced quality-related confounding. This design allows the LLM-based evaluation system works without human gold standards.
Our analysis of 20 mainstream models uncovers a counterintuitive pattern in which stronger model capabilities are often associated with larger SPB. Several state-of-the-art models achieve high discriminability while still exhibiting pronounced self-preference. We term these models
Machiavellian Judges
—capable of recognizing quality yet systematically biased in favor of their own outputs. This finding carries substantial practical implications, as it challenges the common assumption that the most powerful models are automatically the fairest evaluators.
We further propose a structured multi-dimensional evaluation strategy. Drawing on cognitive load theory
(Sweller,
1988
)
, the proposed approach decomposes holistic judgments into a set of simpler subtasks, thereby reducing intuition-driven bias and promoting more objective evaluation. This strategy is designed to be directly applicable within existing LLM-as-a-Judge pipelines, requiring only prompt modifications rather than model retraining.
The main contributions of this paper are summarized as follows.
•
We design a framework for SPB quantification and mitigation, which operates without human gold standards and explicitly resolves the conflation between model capability and evaluative bias. This framework provides a scalable solution suitable for deployment in automated evaluation systems across diverse expert system domains.
•
We identify and formalize a previously hidden class of Machiavellian Judges, demonstrating that high model capability does not necessarily imply evaluative objectivity. This finding establishes new criteria for judge model selection in practical applications.
•
We develop a structured multi-dimensional evaluation strategy that achieves an average SPB reduction of 31.5%, providing a practical and effective pathway toward fairer and more reliable LLM-as-a-Judge systems without model retraining or human supervision.
2
Related Work
2.1
LLM-as-a-Judge in evaluation systems
The LLM-as-a-Judge paradigm leverages large language models as automated evaluators for open-ended tasks, offering a scalable alternative to human evaluation
(Zheng
et al.
,
2023
; Li
et al.
,
2024
)
. This paradigm has been rapidly adopted in a variety of practical evaluation systems.
Zheng
et al.
(
2023
)
introduced MT-Bench and Chatbot Arena, establishing the foundation for large-scale automated model comparison that now serves as a widely adopted community benchmark.
Liu
et al.
(
2023
)
demonstrated that GPT-4-based evaluation achieves high correlation with human judgments in natural language generation tasks. Beyond academic benchmarks, the LLM-as-a-Judge approach has become integral to reward model training in RLHF pipelines, automated content moderation systems, and quality assurance workflows in industrial applications. As LLMs become increasingly deployed in expert system contexts—from hallucination detection pipelines
(Heo
et al.
,
2025
)
to automated bias identification frameworks
(Raza
et al.
,
2024
)
—the reliability and fairness of such automated evaluators become paramount concerns for system trustworthiness
(Huang
et al.
,
2024
)
.
Despite its growing adoption, LLM-as-a-Judge remains plagued by systematic biases
(Ye
et al.
,
2024
; Koo
et al.
,
2024
; Gallegos
et al.
,
2024
)
. Although comparison-based paradigms generally outperform score-based ones in stability
(Zheng
et al.
,
2023
)
, they are susceptible to multi-dimensional distortions.
Position bias
arising from order sensitivity has been documented across multiple model families
(Shi
et al.
,
2024
)
, with models showing significant preference for responses presented in specific positions regardless of content quality.
Length bias
favoring verbose responses represents another persistent challenge
(Hu
et al.
,
2024
)
, where models systematically assign higher scores to longer outputs even when additional content provides no substantive improvement.
Selection bias
, where LLM judges produce inconsistent judgments when option positions or ID tokens are swapped, has been addressed through calibration-based approaches such as CalibraEval
(Li
et al.
,
2025b
)
, which reformulates debiasing as an optimization task over prediction distributions. Broader cognitive biases tied to training distributions further compound these issues
(Koo
et al.
,
2024
; Guo
et al.
,
2024
)
. Furthermore, biases can manifest as “preference leakage” towards specific model families
(Li
et al.
,
2025a
)
or be exacerbated by inconsistent reporting protocols
(Lee
et al.
,
2025
)
. These systematic vulnerabilities underscore the need for rigorous bias characterization before deploying LLM judges in high-stakes evaluation settings.
2.2
Self-preference bias
Self-preference bias, where judges systematically favor their own outputs, is linked to model self-recognition and persists across architectures
(Panickssery
et al.
,
2024
; Liu
et al.
,
2024
; Wataoka
et al.
,
2024
; Lehr
et al.
,
2025
)
.
Panickssery
et al.
(
2024
)
provided seminal evidence that LLM evaluators can recognize and preferentially select their own generations, establishing SPB as a distinct and measurable phenomenon.
Liu
et al.
(
2024
)
further characterized this behavior as “narcissistic evaluation”, demonstrating that ego-driven score inflation is systematic rather than stochastic.
A critical methodological challenge lies in the conflation of capability and bias: conventional win-rate metrics fail to distinguish whether a strong model prefers itself due to narcissistic bias or genuine quality superiority
(Panickssery
et al.
,
2024
; Wataoka
et al.
,
2024
; Chen
et al.
,
2025a
,
b
)
. Consequently, simple difference metrics are insufficient for reliable characterization
(Chen
et al.
,
2025b
)
. This conflation is particularly problematic in practice, as it can lead to the deployment of biased judges under the mistaken assumption that their high capability ensures objectivity.
To address this, prior works have explored statistical calibration
(Spiliopoulou
et al.
,
2025
)
or analyzed internal representations and hidden states
(Duan
et al.
,
2024
; Tan
et al.
,
2024
)
, though these often rely on strong assumptions about model internals or lack scalability to diverse model families. Unlike self-bias in iterative self-improvement contexts
(Xu
et al.
,
2024
; Wu
et al.
,
2025
)
, SPB in external evaluation reliability remains comparatively underexplored. Crucially, recent approaches such as
Chen
et al.
(
2025b
)
utilize gold judgments as quality proxies to mitigate confounding factors, yet a gold-standard-free paradigm that can disentangle generative capability from evaluative bias without reliance on human annotation has not been established.
2.3
Cognitive debiasing strategies
The challenge of reducing bias in automated evaluation connects to a broader body of work on cognitive debiasing. Cognitive load theory
(Sweller,
1988
)
posits that complex holistic judgments place heavy demands on working memory, making evaluators more susceptible to heuristic-driven shortcuts and implicit biases. In human decision-making contexts, structured evaluation protocols that decompose complex decisions into simpler sub-tasks can reduce reliance on intuition and improve judgment quality
(Dawes
et al.
,
1989
)
.
This principle has been adapted to AI evaluation settings in various forms. Multi-dimensional rubrics and structured scoring guides are standard practice in human evaluation protocols for natural language generation (NLG) tasks, where they serve to anchor assessments to specific quality dimensions rather than overall impressions.
Hashemi
et al.
(
2024
)
demonstrated that calibrated multi-dimensional rubrics can significantly improve the alignment between LLM-based evaluation and human judgments, achieving a twofold reduction in prediction error compared to uncalibrated baselines. The extension of such structured approaches to LLM-based evaluation as a debiasing mechanism, however, remains underexplored. While
Liu
et al.
(
2023
)
incorporated multi-dimensional scoring in quality assessment, the application of structured decomposition as a specific debiasing mechanism for SPB has not been systematically investigated.
3
Methods
This section presents the core methodological components of the proposed SPB quantification and mitigation framework. The overall workflow, illustrated in Fig.
1
, comprises five stages: (a) constructing equal-quality pairs, (b) verifying judgment capability, (c) quantifying SPB, (d) classifying models into bias archetypes, and (e) mitigating bias via structured multi-dimensional evaluation.
3.1
Consistency between base models
The entire framework rests on a reliable quality benchmark for model responses. We employ two benchmark judges, GPT-5-Chat-Latest
(OpenAI,
2025
)
and Gemini-2.5-Pro
(Gemini Team and Google DeepMind,
2025
)
, denoted as
M
base
(
1
)
M_{\text{base}}^{(1)}
and
M
base
(
2
)
M_{\text{base}}^{(2)}
. These two models were selected because they provide stable high-quality judging behavior and strong agreement across large-scale scoring, and they are used exclusively for quality assessment rather than response generation. For each response, the two judges score five dimensions (Relevance, Accuracy, Depth, Logic, Clarity; complete prompt templates are provided in
A
) on a 0.0–10.0 scale (step 0.25), and the final score is their arithmetic mean.
Consistency between the two benchmark judges underpins the validity of the entire framework and critically affects the reliability of both equal-quality pair construction and self-preference analysis. To assess this consistency, we conduct a comprehensive statistical analysis over all 2,000 scoring instances (20 models
×
\times
100 questions). We compute the Spearman rank correlation coefficient
ρ
\rho
between the scores assigned by the two judges
(Spearman,
1904
)
. The results yield
ρ
=
0.658
\rho=0.658
, demonstrating statistically significant consistency between the two judges and confirming their shared capability to reliably distinguish high-quality from low-quality responses.
Further analysis of the score difference distribution for identical responses is summarized in Table
1
. Approximately 16.7% of sample pairs had identical ratings, about 48.4% had differences within 0.25 points (one rating step), approximately 71.9% had differences within 0.5 points, and about 91.4% had differences within 1.0 point. The average absolute difference was 0.54 points, the median was 0.38 points, and the standard deviation was 0.58 points. Over 90% of the rating differences fall within 1.0 point, ensuring that the quality benchmark constructed by averaging the two judges is more reliable than any single judge.
Table 1:
Distribution of score differences between two benchmark judges for the same responses. The cumulative percentage indicates the proportion of samples whose score differences are less than or equal to the given score.
Difference Range (Points)
Count
Cumulative (%)
Exact Match (= 0)
333
16.7
≤
\leq
0.25
968
48.4
≤
\leq
0.5
1,437
71.9
≤
\leq
1.0
1,827
91.4
≤
\leq
1.5
1,938
96.9
≤
\leq
2.0
1,978
98.9
>
>
2.0
22
100.0
Total
2,000
100.0
3.2
Equal-quality pairs
Building on the quality scores established above, we isolate SPB from quality by constructing equal-quality pairs whose qualities are relatively indistinguishable. Let
q
q
index questions and
i
,
j
i,j
index evaluated models (excluding the two benchmark judges). For model
M
i
M_{i}
on question
q
q
, denote its response as
r
i
,
q
r_{i,q}
and its scores from GPT-5-Chat-Latest and Gemini-2.5-Pro as
s
i
,
q
(
1
)
s_{i,q}^{(1)}
and
s
i
,
q
(
2
)
s_{i,q}^{(2)}
, respectively. Then we define
s
i
,
q
=
(
s
i
,
q
(
1
)
+
s
i
,
q
(
2
)
)
/
2
s_{i,q}=\bigl(s_{i,q}^{(1)}+s_{i,q}^{(2)}\bigr)/2
as the benchmark score on model
M
i
M_{i}
for question
q
q
. We define the quality indistinguishability threshold
ε
\varepsilon
based on the minimum resolution principle. Given the scoring step of 0.25, differences satisfying
|
s
i
,
q
−
s
j
,
q
|
≤
0.25
|s_{i,q}-s_{j,q}|\leq 0.25
are treated as measurement noise rather than true quality disparity. Thus, setting
ε
=
0.25
\varepsilon=0.25
, we define an equal-quality pair
(
r
i
,
q
,
r
j
,
q
)
(r_{i,q},r_{j,q})
for question
q
q
if
|
s
i
,
q
−
s
j
,
q
|
≤
ε
=
0.25
|s_{i,q}-s_{j,q}|\leq\varepsilon=0.25
. All subsequent bias quantifications (PIR and Null-PIR) are strictly restricted to these pairs.
To provide concrete intuition, we present a representative equal-quality pair from our dataset (
ε
=
0.25
\varepsilon=0.25
):
Equal-Quality Example:
Q0: “Can you tell me a very easy way to clean a showerhead?”
Claude-Sonnet-4.5
(Anthropic,
2025
)
(composite score: 9.25; Gemini-2.5-Pro: 9.5; GPT-5-Chat-Latest: 9.0): “One of the easiest ways… is using vinegar… Fill a plastic bag with white vinegar… place it over the showerhead… secure… soak (overnight works well)… run hot water…” (with a brief finish-safety caveat).
Kimi-K2-Thinking
(Moonshot AI,
2025b
)
(composite score: 9.375; Gemini-2.5-Pro: 9.75; GPT-5-Chat-Latest: 9.0): “The easiest way is the vinegar bag method… Fill a plastic bag with white vinegar (1–2 cups)… secure… wait 1–2 hours (or overnight)… optional quick toothbrush scrub… rinse.”
Δ
​
s
=
|
9.375
−
9.25
|
=
0.125
≤
ε
=
0.25
\Delta s=|9.375-9.25|=0.125\leq\varepsilon=0.25
. Both responses recommend the same vinegar-bag soaking method; differences are limited to presentation style and optional tips.
To verify the reliability of equal-quality pair judgments, we conduct a human validation study comparing automated equal-quality pairs against human quality judgments. We adopt a
clustering-based
protocol rather than forced pairwise comparison, because the latter requires selecting a winner even when differences are negligible, injecting noise precisely near the
ε
\varepsilon
-boundary; clustering directly constructs equivalence classes (“indistinguishable quality”), which is better aligned with our goal.
To enhance both the effectiveness and difficulty of the validation, we adopt a hard-cases selection strategy. We select 1,000 anonymized responses (10 per question), prioritizing pairs with minimal benchmark deviations (
Δ
​
s
∈
[
0
,
0.5
]
\Delta s\in[0,0.5]
) to maximize discrimination difficulty. Three domain experts independently clustered these responses based on perceived quality equivalence, with final cluster assignments determined by majority vote (
≥
2
/
3
\geq 2/3
). Inter-annotator agreement, measured by Fleiss’
κ
=
0.64
\kappa=0.64
, indicates substantial agreement
(Fleiss,
1971
)
.
We derive pair-level labels from the clusters: a pair
(
r
i
,
q
,
r
j
,
q
)
(r_{i,q},r_{j,q})
is labeled “equal-quality” if and only if the two responses fall in the same human cluster, and “unequal-quality” otherwise. Consistency between the automated and human methods is then defined at the pair level: a pair is
consistent
if both methods classify it as equal (same human cluster
and
|
s
i
,
q
−
s
j
,
q
|
≤
ε
|s_{i,q}-s_{j,q}|\leq\varepsilon
) or both classify it as unequal (different clusters
and
|
s
i
,
q
−
s
j
,
q
|
>
ε
|s_{i,q}-s_{j,q}|>\varepsilon
). The resulting 79.8% agreement rate is obtained on deliberately selected hard cases near the
ε
\varepsilon
-boundary. For reference, MT-Bench
(Zheng
et al.
,
2023
)
reports human–human agreement of 81–82% and GPT-4–human agreement of 80–85% under standard (non-adversarial) conditions. Our 79.8% on boundary-hard cases is consistent with the substantial inter-annotator agreement (
κ
=
0.64
\kappa=0.64
) and the benchmark-judge consistency (Spearman
ρ
≈
0.66
\rho\approx 0.66
), validating the use of constructed equal-quality pairs for self-preference quantification.
3.3
Judgment capability verification
Before quantifying a model’s SPB, it is essential to first verify whether the model possesses basic discriminability. Otherwise, a seemingly unbiased model might merely exhibit neutrality due to random selection rather than genuine evaluative objectivity. To this end, we construct a high-contrast set. Specifically, when the condition
s
j
,
q
−
s
k
,
q
≥
2.5
s_{j,q}-s_{k,q}\geq 2.5
is satisfied, we include the ordered pair
(
r
j
,
q
,
r
k
,
q
)
(r_{j,q},r_{k,q})
in the high-contrast set. This condition guarantees that
r
j
,
q
r_{j,q}
is significantly superior to
r
k
,
q
r_{k,q}
in terms of quality. For each evaluated model
M
i
M_{i}
, we randomly sample 100 pairs from this set, and denote the resulting set as
𝒟
H
​
C
(
i
)
\mathcal{D}_{HC}^{(i)}
.
For each pair
(
r
j
,
q
,
r
k
,
q
)
(r_{j,q},r_{k,q})
, we present the two responses to model
M
i
M_{i}
in a strictly randomized order , and record its final selection (who is better) as
c
i
​
(
r
j
,
q
,
r
k
,
q
)
c_{i}(r_{j,q},r_{k,q})
. Since
r
j
,
q
r_{j,q}
is defined by construction as the higher-quality response, the model’s judgment on this sample pair is considered correct if and only if
c
i
​
(
r
j
,
q
,
r
k
,
q
)
=
r
j
,
q
c_{i}(r_{j,q},r_{k,q})=r_{j,q}
. Therefore, the discriminability of model
M
i
M_{i}
is formulated as follows:
π
i
=
|
{
(
r
j
,
q
,
r
k
,
q
)
∈
𝒟
H
​
C
(
i
)
:
c
i
​
(
r
j
,
q
,
r
k
,
q
)
=
r
j
,
q
}
|
|
𝒟
H
​
C
(
i
)
|
,
\pi_{i}=\frac{\left|\left\{(r_{j,q},r_{k,q})\in\mathcal{D}_{HC}^{(i)}:\;c_{i}(r_{j,q},r_{k,q})=r_{j,q}\right\}\right|}{|\mathcal{D}_{HC}^{(i)}|},
(1)
which
π
i
\pi_{i}
represents the proportion of high-contrast pairs where the model correctly identifies the higher-quality response.
When
π
i
\pi_{i}
fluctuates around 0.5, it indicates that the model’s decisions approach random guessing even in clearly distinguishable scenarios, signifying a lack of basic discriminability. Only when
π
i
\pi_{i}
is significantly above the random baseline is the model considered to possess fundamental evaluative capability. In this paper, we adopt
π
i
≥
0.8
\pi_{i}\geq 0.8
as the empirical threshold for discriminability, and subsequent self-preference analysis is restricted exclusively to models satisfying this criterion.
3.4
SPB quantification
For a given model
M
i
M_{i}
, we aim to determine whether it tends to select its own output when there is no significant quality difference between its response and a third-party response. To achieve this, we first examine the proportion of cases in such equal-quality comparisons where the model selects its own response, named as the Probabilistic Inclination Ratio (PIR). Subsequently, we construct a third-party baseline that excludes the model’s own responses to subtract general confounding factors such as style or length preferences. The difference between these two values is defined as the SPB of model
M
i
M_{i}
.
To eliminate confounding factors, we design a neutral, single-letter output prompt (see
A
, Table
LABEL:tab:prompt-preference
). In the implementation, for each pair of responses to be compared, we conduct two independent evaluations: the first presents the two responses in a given order, and the second swaps their presentation order. The purpose of this mechanism is to avoid misinterpreting a model’s preference for a specific position (i.e., position bias) as a genuine preference for the content of a response.
For question
q
q
, let
𝒱
q
​
(
i
)
=
{
j
∣
j
≠
i
,
|
s
i
,
q
−
s
j
,
q
|
≤
ϵ
}
\mathcal{V}_{q}(i)=\{j\mid j\neq i,\ |s_{i,q}-s_{j,q}|\leq\epsilon\}
(2)
denote the set of third-party models whose responses fall within the same equal-quality domain as the response
r
i
,
q
r_{i,q}
. In other words, when
j
∈
𝒱
q
​
(
i
)
j\in\mathcal{V}_{q}(i)
,
r
j
,
q
r_{j,q}
and
r
i
,
q
r_{i,q}
can be considered to have equal quality under the benchmark evaluation. Consequently, the total count of such valid pairings is formulated as:
N
i
=
∑
q
=
1
Q
|
𝒱
q
​
(
i
)
|
.
N_{i}=\sum_{q=1}^{Q}|\mathcal{V}_{q}(i)|.
(3)
For any
j
∈
𝒱
q
​
(
i
)
j\in\mathcal{V}_{q}(i)
, we independently present the permutations
(
r
i
,
q
,
r
j
,
q
)
(r_{i,q},r_{j,q})
and
(
r
j
,
q
,
r
i
,
q
)
(r_{j,q},r_{i,q})
to
M
i
M_{i}
. If the model selects its own response
r
i
,
q
r_{i,q}
in both queries, it is recorded as a firm self-preference. Accordingly, we define:
ρ
i
=
∑
q
=
1
Q
|
{
j
∈
𝒱
q
​
(
i
)
:
c
i
​
(
r
i
,
q
,
r
j
,
q
)
=
r
i
,
q
,
c
i
​
(
r
j
,
q
,
r
i
,
q
)
=
r
i
,
q
}
|
N
i
.
\rho_{i}=\frac{\sum_{q=1}^{Q}\left|\left\{j\in\mathcal{V}_{q}(i):\;c_{i}(r_{i,q},r_{j,q})=r_{i,q},\;c_{i}(r_{j,q},r_{i,q})=r_{i,q}\right\}\right|}{N_{i}}.
(4)
Therefore,
ρ
i
\rho_{i}
represents the proportion of equal-quality pairings with third-party models where model
M
i
M_{i}
consistently chooses its own output regardless of the presentation order.
Relying solely on
ρ
i
\rho_{i}
is insufficient to distinguish pure self-preference from general target biases. If a model inherently favors a certain writing style, it might also select its own response more frequently in comparisons involving its own outputs. To address this, we further construct a third-party baseline that excludes the model’s own responses. For each question
q
q
, we define:
ℬ
q
(
i
)
=
{
(
j
,
k
)
∣
\displaystyle\mathcal{B}_{q}(i)=\big\{(j,k)\mid{}
j
≠
i
,
k
≠
i
,
j
≠
k
,
\displaystyle j\neq i,\ k\neq i,\ j\neq k,
(5)
|
s
i
,
q
−
s
j
,
q
|
≤
ϵ
,
|
s
i
,
q
−
s
k
,
q
|
≤
ϵ
,
|
s
j
,
q
−
s
k
,
q
|
≤
ϵ
}
.
\displaystyle|s_{i,q}-s_{j,q}|\leq\epsilon,\ |s_{i,q}-s_{k,q}|\leq\epsilon,\ |s_{j,q}-s_{k,q}|\leq\epsilon\big\}.
Here,
ℬ
q
​
(
i
)
\mathcal{B}_{q}(i)
consists of all ordered pairs of third-party models
(
j
,
k
)
(j,k)
, where
r
j
,
q
r_{j,q}
and
r
k
,
q
r_{k,q}
are not only equal in quality to each other but also fall into the same equal-quality neighborhood as
r
i
,
q
r_{i,q}
. We systematically designate the first element of the ordered pair,
r
j
,
q
r_{j,q}
, as the target response. The corresponding total number of third-party baseline combinations is:
N
i
null
=
∑
q
=
1
Q
|
ℬ
q
​
(
i
)
|
.
N_{i}^{\mathrm{null}}=\sum_{q=1}^{Q}|\mathcal{B}_{q}(i)|.
(6)
For any
(
j
,
k
)
∈
ℬ
q
​
(
i
)
(j,k)\in\mathcal{B}_{q}(i)
, we independently present
(
r
j
,
q
,
r
k
,
q
)
(r_{j,q},r_{k,q})
and
(
r
k
,
q
,
r
j
,
q
)
(r_{k,q},r_{j,q})
to model
M
i
M_{i}
. If the model selects the target response
r
j
,
q
r_{j,q}
across both corresponding permutations, it is recorded as a baseline preference. Based on this, we define:
ρ
i
null
=
∑
q
=
1
Q
|
{
(
j
,
k
)
∈
ℬ
q
​
(
i
)
:
c
i
​
(
r
j
,
q
,
r
k
,
q
)
=
r
j
,
q
,
c
i
​
(
r
k
,
q
,
r
j
,
q
)
=
r
j
,
q
}
|
N
i
null
.
\rho_{i}^{\mathrm{null}}=\frac{\sum_{q=1}^{Q}\left|\left\{(j,k)\in\mathcal{B}_{q}(i):\;c_{i}(r_{j,q},r_{k,q})=r_{j,q},\;c_{i}(r_{k,q},r_{j,q})=r_{j,q}\right\}\right|}{N_{i}^{\mathrm{null}}}.
(7)
ρ
i
null
\rho_{i}^{\mathrm{null}}
represents the rate at which model
M
i
M_{i}
firmly selects a pre-designated target response in third-party equal-quality comparisons that exclude its own outputs.
Building on this foundation, the Self-Preference Bias for model
M
i
M_{i}
is defined as:
β
i
=
ρ
i
−
ρ
i
null
.
\beta_{i}=\rho_{i}-\rho_{i}^{\mathrm{null}}.
(8)
If
β
i
>
0
\beta_{i}>0
, it indicates that the model
M
i
M_{i}
exhibits a tendency to select its own response compared to the third-party baseline, demonstrating the existence of SPB. If
β
i
≈
0
\beta_{i}\approx 0
, SPB is neglectable. Conversely, if
β
i
<
0
\beta_{i}<0
, it signifies that the model tends to favor outputs generated by others.
Theoretically, the introduction of Null-PIR enables this subtraction to operate as a statistical common-mode rejection mechanism. According to the Common Method Bias theory
(Podsakoff
et al.
,
2003
)
, latent tendencies (e.g., length bias, style bias) act as background covariates affecting both self and third-party evaluations. Consequently, the above differencing procedure effectively eliminates these systematic errors, isolating the pure self-preference component.
We assess significance via three complementary tests: (1) a one-sided Binomial test against chance; (2) a two-proportion Z-test comparing PIR and Null-PIR; and (3) a Bootstrap confidence interval approach (1,000 iterations)
(Efron,
1979
)
. Significance is declared only if robustly supported by these metrics, ensuring that identified biases are statistically reliable rather than artifacts of sampling variability.
3.5
Discriminability-bias classification
To better understand model behavior and provide actionable guidelines for judge selection, we propose a discriminability–bias classification framework that organizes models along two axes: discriminability
π
i
\pi_{i}
on the x-axis and SPB
β
i
\beta_{i}
on the y-axis.
We set the discriminability threshold to
π
thresh
=
0.8
\pi_{\mathrm{thresh}}=0.8
and the absolute bias threshold to
|
β
i
|
thresh
=
0.08
|\beta_{i}|_{\mathrm{thresh}}=0.08
. The bias threshold is chosen to separate substantively large bias from typical sampling fluctuation under our evaluation protocol. Based on the experimental data, the aggregated standard error of
β
i
\beta_{i}
is be approximately
σ
β
≈
0.022
\sigma_{\beta}\approx 0.022
. We therefore set
|
β
i
|
thresh
=
0.08
|\beta_{i}|_{\mathrm{thresh}}=0.08
as a conservative cutoff that lies clearly above the noise scale (roughly
3
3
–
4
×
σ
β
4\times\sigma_{\beta}
). This cutoff is intended for quadrant visualization and taxonomy; formal model-level significance statements are established separately using the binomial test, the two-proportion Z-test, and bootstrap confidence intervals, as mentioned in Section
3.4
.
Based on these thresholds, models are categorized into four classes:
Objective Judges
:
π
i
≥
0.8
\pi_{i}\geq 0.8
and
|
β
i
|
≤
0.08
|\beta_{i}|\leq 0.08
. Models in this category exhibit high discriminability while evaluating both their own and others’ outputs objectively, making them good candidates for deployment as judges in automated evaluation systems.
Machiavellian Judges
:
π
i
≥
0.8
\pi_{i}\geq 0.8
and
β
i
>
0.08
\beta_{i}>0.08
. These models possess high discriminability but systematically favor their own outputs, rendering them unreliable as judges. The term “Machiavellian” reflects their capacity to accurately assess quality while strategically exhibiting self-preference.
Incompetent Randomizers
:
π
i
<
0.8
\pi_{i}<0.8
, regardless of
β
i
\beta_{i}
. These models lack basic discriminability. Any observed “bias” is indistinguishable from random fluctuation, thus they are fundamentally unqualified for judging roles.
Blindly Biased Judges
:
π
i
≥
0.8
\pi_{i}\geq 0.8
and
β
i
<
−
0.08
\beta_{i}<-0.08
. These models possess high discriminability with strong negative SPB, favoring other models’ outputs over their own. Such strong negative bias indicates a lack of objectivity, making them unreliable as judges.
This taxonomy provides a systematic guideline for model evaluation and selection in practical settings, helping to identify genuinely objective judges, avoid misclassifying incompetent randomizers as objective evaluators, and recognize models that, despite high discriminability, exhibit either positive or negative bias.
3.6
SPB mitigation
To mitigate self-preference, we introduce a structured multi-dimensional evaluation strategy grounded in cognitive load and structured decision-making theories
(Sweller,
1988
)
. The baseline approach employs
pointwise
scoring, where each response is scored independently on a 0–10 scale across five dimensions, and the final score is their arithmetic mean. This pointwise regime is vulnerable to attribute-bundling and halo effects: a single stylistic cue (e.g., recognizing one’s own formatting conventions) can inflate multiple dimension scores simultaneously, as the judge need not compare the two responses directly (see
A
, Table
LABEL:tab:prompt-preference
).
Our mitigation replaces this with a
pairwise, per-dimension forced-choice
protocol. The judge must explicitly choose between Response A and Response B on each of five independent dimensions—Relevance, Accuracy, Depth, Logic, and Clarity (see
A
, Table
LABEL:tab:prompt-structured
)—before rendering a final verdict determined by majority vote across the five dimensions. By forcing local trade-offs (e.g., “which response is more accurate?”), the protocol makes it harder for a global stylistic cue to dominate all dimensions. The design draws on cognitive science evidence that humans have limited working memory and tend to use heuristic shortcuts under high multi-attribute load so the decomposition can reduce extraneous load by forcing dimension-wise deliberation. We note explicitly that this is a
functional analogy
—LLMs are not humans—and rely on empirical validation (SPB decreases while high-contrast discriminability is preserved; see Section
4.4
).
We apply this mitigation strategy to models exhibiting significant bias (
|
β
i
|
>
0.08
|\beta_{i}|>0.08
) on the established equal-quality pairs. In each evaluation instance, the judge is presented with two candidate responses, labeled Response A and Response B. To eliminate position bias, we preserve the double-query design, in which the same pair is judged twice, once as A/B and once as B/A. Based on these judgments, we quantify the mitigation effect using the improvement rate:
η
i
=
β
i
baseline
−
β
i
mitigation
β
i
baseline
,
\eta_{i}=\frac{\beta_{i}^{\mathrm{baseline}}-\beta_{i}^{\mathrm{mitigation}}}{\beta_{i}^{\mathrm{baseline}}},
(9)
where
β
i
baseline
\beta_{i}^{\mathrm{baseline}}
and
β
i
mitigation
\beta_{i}^{\mathrm{mitigation}}
denote the SPB magnitudes under the baseline and structured evaluation settings, respectively.
4
Results and Analysis
4.1
Experimental setup
Our experiment employs two benchmark judges and twenty evaluated models. The benchmark judges, denoted as
M
base
(
1
)
M_{\mathrm{base}}^{(1)}
and
M
base
(
2
)
M_{\mathrm{base}}^{(2)}
, are GPT-5-Chat-Latest
(OpenAI,
2025
)
and Gemini-2.5-Pro
(Gemini Team and Google DeepMind,
2025
)
, respectively. These two judges are used exclusively for quality assessment without participating in content generation.
Table 2:
Categorization of the 20 evaluated models. Models are grouped by organization and sorted from largest to smallest within each group. The total parameter count refers to the complete model size, whereas activated parameters correspond to the subset of parameters engaged during inference in MoE models.
Model
Availability
Total Parameters
Active Parameters
Architecture
Organization
Claude-Sonnet-4.5
Closed Source
Undisclosed
N/A
Undisclosed
Anthropic
Mistral-Nemo
Closed Source
12B
12B
Dense
Mistral AI
Grok-4-Fast
Closed Source
Undisclosed
N/A
Unified Arch
xAI
Grok-3-Mini
Closed Source
Undisclosed
N/A
Undisclosed
xAI
GLM-4.5-Air
Closed Source
106B
12B
MoE
Zhipu AI
DeepSeek-V3-0324
Open Source
671B
37B
MoE + MLA
DeepSeek AI
DeepSeek-V3.2
Open Source
671B
37B
MoE + DSA
DeepSeek AI
DeepSeek-R1-0528
Open Source
671B
37B
MoE (RL)
DeepSeek AI
Hunyuan-A13B-Instruct
Open Source
80B
13B
MoE
Tencent
Qwen3-235B-A22B-2507
Open Source
235B
22B
MoE
Alibaba
Qwen3-235B-A22B-Thinking-2507
Open Source
235B
22B
MoE (Mode)
Alibaba
Kimi-Dev-72B
Open Source
72B
72B
Dense
Moonshot AI
Kimi-Linear-48B-A3B-Instruct
Open Source
48B
3B
Hybrid Linear
Moonshot AI
Kimi-K2-Thinking
Open Source
Undisclosed
N/A
Undisclosed
Moonshot AI
Llama-3.3-70B-Instruct
Open Source
70B
70B
Dense
Meta
Llama-3.1-8B-Instruct
Open Source
8B
8B
Dense
Meta
Llama-3.2-3B-Instruct
Open Source
3B
3B
Dense
Meta
Gemma-3-27B
Open Source
27B
27B
Dense (Sliding)
Google
Gemma-3-12B
Open Source
12B
12B
Dense (Sliding)
Google
LongCat-Flash-Chat
Open Source
560B
∼
\sim
27B
MoE (ScMoE)
Meituan
To ensure a comprehensive evaluation of SPB across the current LLM landscape, we selected a diverse set spanning both closed-source and open-source models across a wide range of parameter scales from 3B to 671B. The selection covers distinct architectures including dense models, Mixture-of-Experts (MoE), and reasoning-enhanced models (e.g., Thinking series). This design ensures the singular role of benchmark judges, avoids potential family bias by excluding the benchmark judge families from the evaluated set, and allows the remaining models to act as both generators and self-judges in the evaluation stage. The detailed informations is presented in Table
2
.
We sample 100 single-turn tasks from the AlpacaEval evaluation set
(Dubois
et al.
,
2023
)
using stratified sampling with a fixed random seed. Following the root-verb distribution analysis, the subset covers seven categories: Text Generation (36%), Information Provision (34%), Explanation (16%), Question Answering (2%), Code Implementation (3%), Text Editing (3%), and Other tasks (6%). The full list of evaluation questions is provided in
LABEL:appendix:questions-list
. Because each of categories Question Answering, Code Implementation, Text Editing, and Others accounts for
≤
6
%
\leq 6\%
of the sample (2–6 instances), their per-category sample sizes are insufficient for reliable task-level behavioral claims. Accordingly, all task-specific analyses in Section
4.2
are restricted to the three sufficiently sampled categories: Text Generation, Information Provision, and Explanation. To eliminate confounding effects from parameter differences, all model API calls use identical inference parameters (temperature=0, top_p=1).
4.2
SPB of models
Table 3:
PIR (
ρ
i
\rho_{i}
), Null-PIR (
ρ
i
null
\rho_{i}^{\mathrm{null}}
), and SPB (
β
i
\beta_{i}
) for all models, sorted in descending order of SPB. Significance columns report outcomes of Binomial, Z-test, and Bootstrap tests (all two-sided). The “Sig (
≥
\geq
2/3)” column marks a model as significant only when at least two of the three tests agree.
Model
PIR
Null-PIR
SPB
# Equal-Quality Pairs
# Null Pairs
Binomial
Z-test
Bootstrap
Sig (
≥
\geq
2/3)
LongCat-Flash-Chat
0.741
0.434
0.307
1,311
890
Yes
Yes
Yes
Yes
DeepSeek-V3.2
0.566
0.341
0.226
1,349
916
Yes
Yes
Yes
Yes
Gemma-3-12B
0.598
0.418
0.181
1,305
864
Yes
Yes
Yes
Yes
Gemma-3-27B
0.568
0.416
0.152
1,357
902
Yes
Yes
Yes
Yes
Qwen3-235B-A22B-Thinking-2507
0.476
0.352
0.124
1,228
554
Yes
Yes
Yes
Yes
Grok-3-Mini
0.499
0.399
0.100
1,362
902
Yes
Yes
Yes
Yes
GLM-4.5-Air
0.510
0.415
0.095
1,336
827
Yes
Yes
Yes
Yes
Qwen3-235B-A22B-2507
0.504
0.415
0.090
1,396
948
Yes
Yes
Yes
Yes
Grok-4-Fast
0.373
0.337
0.035
1,371
922
No
Yes
No
No
DeepSeek-V3-0324
0.395
0.371
0.024
1,368
897
No
No
No
No
Llama-3.2-3B-Instruct
0.007
0.007
-0.001
1,004
667
No
No
No
No
Kimi-Linear-48B-A3B-Instruct
0.314
0.357
-0.043
1,283
846
No
Yes
Yes
Yes
Mistral-Nemo
0.030
0.082
-0.052
1,183
766
Yes
Yes
Yes
Yes
Llama-3.1-8B-Instruct
0.020
0.080
-0.060
1,050
710
Yes
Yes
Yes
Yes
DeepSeek-R1-0528
0.008
0.105
-0.097
1,247
845
Yes
Yes
Yes
Yes
Kimi-K2-Thinking
0.007
0.108
-0.102
1,296
848
Yes
Yes
Yes
Yes
Kimi-Dev-72B
0.125
0.242
-0.117
1,106
753
Yes
Yes
Yes
Yes
Llama-3.3-70B-Instruct
0.119
0.271
-0.151
1,331
898
Yes
Yes
Yes
Yes
Hunyuan-A13B-Instruct
0.236
0.388
-0.152
1,098
714
Yes
Yes
Yes
Yes
Claude-Sonnet-4.5
0.193
0.422
-0.229
1,155
773
Yes
Yes
Yes
Yes
Table
3
presents PIR, Null-PIR, and SPB for all 20 models, sorted by descending SPB. The results reveal a clear spectrum of self-preference: LongCat-Flash-Chat
(Meituan Generative AI,
2025
)
exhibits the strongest positive bias (
β
=
0.307
\beta=0.307
), followed by DeepSeek-V3.2
(DeepSeek-AI,
2025b
)
(
β
=
0.226
\beta=0.226
); at the other extreme, Claude-Sonnet-4.5
(Anthropic,
2025
)
shows the strongest negative bias (
β
=
−
0.229
\beta=-0.229
). In total, 8 models display positive self-preference (
β
>
0
\beta>0
), 9 models display negative self-preference, and 3 models—Grok-4-Fast
(xAI,
2025b
)
(
β
=
0.035
\beta=0.035
), DeepSeek-V3-0324
(DeepSeek-AI,
2024
)
(
β
=
0.024
\beta=0.024
), and Llama-3.2-3B-Instruct
(AI@Meta,
2024
)
(
β
=
−
0.001
\beta=-0.001
)—have near-zero SPB values.
To validate these findings, we adopt a unified “Sig (
≥
\geq
2/3)” rule: a model’s SPB is deemed statistically significant only when at least two of the three tests (Binomial, Z-test, Bootstrap) agree. Under this criterion, 17 of the 20 models reach significance; the three near-zero models do not, confirming that their observed SPB values are indistinguishable from sampling noise. We further compute 95% confidence intervals via hierarchical bootstrap over the 100 prompts, accounting for the nested dependence structure of pairwise decisions within each prompt. Representative intervals confirm the robustness of the point estimates: LongCat-Flash-Chat,
β
=
0.307
\beta=0.307
, 95% CI
[
0.259
,
0.350
]
[0.259,0.350]
; Claude-Sonnet-4.5,
β
=
−
0.228
\beta=-0.228
, 95% CI
[
−
0.270
,
−
0.183
]
[-0.270,-0.183]
. A sensitivity analysis over
ε
∈
[
0
,
0.75
]
\varepsilon\in[0,0.75]
(
LABEL:appendix:epsilon-sensitivity
) further confirms that the main conclusions hold under both stricter and looser equivalence thresholds.
Table
4
lists per-model SPB on each of the three sufficiently sampled task types; Table
5
aggregates significance counts and means. We observe a distinct dichotomy between the frequency and magnitude of self-preference.
Table 4:
Per-model SPB (
β
i
\beta_{i}
) on the three sufficiently sampled task types (Bootstrap test). Rows follow alphabetical order by model name. Within each task column,
boldface
marks the maximum and
underline
marks the minimum.
Model
Text Generation
Information Provision
Explanation
Claude-Sonnet-4.5
−
-
0.40
−
-
0.18
−
-
0.26
DeepSeek-R1-0528
0.00
−
-
0.09
−
-
0.07
DeepSeek-V3-0324
−
-
0.20
−
-
0.04
0.03
DeepSeek-V3.2
0.27
0.26
0.25
Gemma-3-12B
0.43
0.23
0.19
Gemma-3-27B
−
-
0.12
0.16
0.25
GLM-4.5-Air
0.01
0.17
0.21
Grok-3-Mini
0.10
0.11
0.05
Grok-4-Fast
0.17
0.01
−
-
0.02
Hunyuan-A13B-Instruct
−
-
0.16
−
-
0.18
−
-
0.16
Kimi-Dev-72B
0.07
−
-
0.08
−
-
0.13
Kimi-K2-Thinking
−
-
0.10
−
-
0.10
−
-
0.11
Kimi-Linear-48B-A3B-Instruct
0.05
−
-
0.13
−
-
0.12
Llama-3.1-8B-Instruct
−
-
0.14
−
-
0.08
−
-
0.06
Llama-3.2-3B-Instruct
0.00
−
-
0.01
−
-
0.01
Llama-3.3-70B-Instruct
−
-
0.04
−
-
0.17
−
-
0.17
LongCat-Flash-Chat
0.43
0.29
0.27
Mistral-Nemo
−
-
0.06
−
-
0.05
−
-
0.04
Qwen3-235B-A22B-2507
0.09
0.00
0.05
Qwen3-235B-A22B-Thinking-2507
0.86
0.54
0.47
Text Generation
tasks trigger the most widespread SPB (10 significant models), likely due to their open-ended nature, yet the average intensity is moderate (
β
¯
=
0.17
\bar{\beta}=0.17
). Qwen3-235B-A22B-Thinking-2507
(Yang
et al.
,
2025
)
exhibits the strongest self-preference (
β
=
0.336
\beta=0.336
), followed by LongCat-Flash-Chat (
β
=
0.319
\beta=0.319
). The prevalence of significance suggests that the open-ended nature of text generation makes models more prone to favor their own creative outputs.
Information Provision
shows eight significant models (
β
¯
=
0.21
\bar{\beta}=0.21
). Qwen3-235B-A22B-Thinking-2507 exhibits very strong self-preference (
β
=
0.466
\beta=0.466
), followed by LongCat-Flash-Chat (
β
=
0.270
\beta=0.270
).
Explanation
tasks show seven models with significant SPB (
β
¯
=
0.25
\bar{\beta}=0.25
). Qwen3-235B-A22B-Thinking-2507 exhibits its highest SPB here (
β
=
0.540
\beta=0.540
). The relatively high mean suggests models are prone to favor their own outputs in tasks requiring logical coherence.
Table 5:
Detailed information about models with significant positive SPB values for the three sufficiently sampled task types. For each task type, we report the number of models with significant positive SPB values and the specific names and SPB values of those models, as well as the mean SPB value.
Task Type
# Significant Models
Models with Significant Positive SPB
Mean SPB
Text Generation
10
DeepSeek-V3.2 (0.193), Qwen3-235B-A22B-2507 (0.177), Gemma-3-27B (0.117), Grok-4-Fast (0.096), LongCat-Flash-Chat (0.319), Gemma-3-12B (0.139), GLM-4.5-Air (0.133), Grok-3-Mini (0.127), DeepSeek-R1-0528 (0.026), Qwen3-235B-A22B-Thinking-2507 (0.336)
0.17
Information Provision
8
DeepSeek-V3.2 (0.250), Gemma-3-27B (0.210), LongCat-Flash-Chat (0.270), GLM-4.5-Air (0.194), Gemma-3-12B (0.250), Qwen3-235B-A22B-Thinking-2507 (0.466), Kimi-K2-Thinking (0.036), DeepSeek-R1-0528 (0.037)
0.21
Explanation
7
DeepSeek-V3.2 (0.255), Gemma-3-27B (0.170), LongCat-Flash-Chat (0.288), Gemma-3-12B (0.165), Grok-3-Mini (0.112), GLM-4.5-Air (0.231), Qwen3-235B-A22B-Thinking-2507 (0.540)
0.25
Notably, reasoning-augmented models exhibit pronounced directional evaluative bias across task types: Qwen3-235B-A22B-Thinking-2507 reaches extreme self-preference in Explanation tasks (
β
=
0.540
\beta=0.540
) and Information Provision (
β
=
0.466
\beta=0.466
), suggesting that stronger reasoning capabilities may paradoxically reinforce overconfidence in one’s own solutions.
4.3
Correlation analysis
A critical question is whether stronger models are inherently fairer. We analyze the relationship between SPB (
β
i
\beta_{i}
) and two capability metrics: generative quality (average score) and discriminability (
π
i
\pi_{i}
).
Figure 2:
Correlation analysis between quality and SPB. The x-axis represents the model’s average quality score across 100 test questions, while the y-axis denotes its SPB.
We first analyze the relationship between quality and SPB. Figure
2
plots the average quality scores against SPB. The absence of a clear linear correlation demonstrates that generative proficiency is decoupled from evaluative objectivity. A deeper inspection reveals divergent behaviors among high-capability models. DeepSeek-V3-0324 combines top-tier generation scores with near-zero bias (
β
=
0.024
\beta=0.024
), proving that high capability can coexist with impartiality. Claude-Sonnet-4.5, while also high-quality, exhibits significant negative bias (
β
=
−
0.229
\beta=-0.229
), suggesting a tendency toward overcorrection. However, although overall quality is not significantly correlated with SPB, many high-quality models still exhibit notable bias. For example, LongCat-Flash-Chat and DeepSeek-V3.2 combine strong average quality with relatively high positive SPB. This finding confirms that generative excellence is a poor proxy for fairness, underscoring that optimal judges must be selected based on verified neutrality rather than generation quality alone.
We next analyze discriminability
π
i
\pi_{i}
relative to SPB (
β
i
\beta_{i}
). Using thresholds
π
thresh
=
0.8
\pi_{\mathrm{thresh}}=0.8
and
|
β
i
|
thresh
=
0.08
|\beta_{i}|_{\mathrm{thresh}}=0.08
, we partition the model space (Fig.
3
) into four archetypes (Table
6
):
Figure 3:
Discrimination capability (
π
i
\pi_{i}
) vs. SPB (
β
i
\beta_{i}
). Dashed lines indicate thresholds:
π
thresh
=
0.8
\pi_{\mathrm{thresh}}=0.8
and
|
β
i
|
thresh
=
0.08
|\beta_{i}|_{\mathrm{thresh}}=0.08
.
Objective Judges.
Three models are good evaluators: DeepSeek-V3-0324
(DeepSeek-AI,
2024
)
(
π
=
0.82
,
β
=
0.024
\pi=0.82,\beta=0.024
), Grok-4-Fast (
π
=
0.85
,
β
=
0.035
\pi=0.85,\beta=0.035
), and Kimi-Linear-48B-A3B-Instruct
(Moonshot AI,
2025c
)
(
π
=
0.85
,
β
=
−
0.043
\pi=0.85,\beta=-0.043
). Despite Kimi-Linear-48B-A3B-Instruct’s mild negative bias, all fall within the neutrality zone, demonstrating that high discriminability can coexist with low SPB.
Table 6:
Discriminability
π
i
\pi_{i}
, SPB
β
i
\beta_{i}
, and
p
p
-values for testing whether discriminability on the high-contrast pairs is significantly above random guessing (50%), that is, whether the model identifies the benchmark-defined higher-quality response more often than chance.
Model
π
i
\pi_{i}
β
i
\beta_{i}
p
p
-value
Archetype
π
i
≥
0.8
\pi_{i}\geq 0.8
(high discriminability)
LongCat-Flash-Chat
0.87
0.307
<
10
−
14
<10^{-14}
Machiavellian Judge
Qwen3-235B-A22B-2507
0.86
0.090
<
10
−
13
<10^{-13}
Machiavellian Judge
Grok-4-Fast
0.85
0.035
<
10
−
12
<10^{-12}
Objective Judge
Kimi-Linear-48B-A3B-Instruct
0.85
-0.043
<
10
−
12
<10^{-12}
Objective Judge
Grok-3-Mini
0.85
0.100
<
10
−
12
<10^{-12}
Machiavellian Judge
Qwen3-235B-A22B-Thinking-2507
0.85
0.124
<
10
−
12
<10^{-12}
Machiavellian Judge
Claude-Sonnet-4.5
0.84
-0.229
<
10
−
11
<10^{-11}
Blindly Biased Judge
Kimi-Dev-72B
0.84
-0.117
<
10
−
11
<10^{-11}
Blindly Biased Judge
Llama-3.3-70B-Instruct
0.84
-0.151
<
10
−
11
<10^{-11}
Blindly Biased Judge
Hunyuan-A13B-Instruct
0.83
-0.152
<
10
−
11
<10^{-11}
Blindly Biased Judge
DeepSeek-V3.2
0.82
0.226
<
10
−
10
<10^{-10}
Machiavellian Judge
DeepSeek-V3-0324
0.82
0.024
<
10
−
10
<10^{-10}
Objective Judge
Gemma-3-27B
0.81
0.152
<
10
−
10
<10^{-10}
Machiavellian Judge
π
i
<
0.8
\pi_{i}<0.8
(low discriminability)
Gemma-3-12B
0.78
0.181
<
10
−
9
<10^{-9}
Incompetent Randomizer
Llama-3.1-8B-Instruct
0.77
-0.060
<
10
−
8
<10^{-8}
Incompetent Randomizer
Mistral-Nemo
0.75
-0.052
<
10
−
7
<10^{-7}
Incompetent Randomizer
DeepSeek-R1-0528
0.55
-0.097
0.184
Incompetent Randomizer
GLM-4.5-Air
0.52
0.095
0.381
Incompetent Randomizer
Llama-3.2-3B-Instruct
0.51
-0.001
0.460
Incompetent Randomizer
Kimi-K2-Thinking
0.51
-0.102
0.457
Incompetent Randomizer
Machiavellian Judges.
High capability does not guarantee fairness. Six models systematically favor themselves despite high discriminability: LongCat-Flash-Chat (
π
=
0.87
,
β
=
0.307
\pi=0.87,\beta=0.307
), DeepSeek-V3.2 (
π
=
0.82
,
β
=
0.226
\pi=0.82,\beta=0.226
), Gemma-3-27B
(Gemma Team and Google DeepMind,
2025
)
(
π
=
0.81
,
β
=
0.152
\pi=0.81,\beta=0.152
), Qwen3-235B-A22B-Thinking-2507 (
π
=
0.85
,
β
=
0.124
\pi=0.85,\beta=0.124
), Grok-3-Mini
(xAI,
2025a
)
(
π
=
0.85
,
β
=
0.100
\pi=0.85,\beta=0.100
), and Qwen3-235B-A22B-2507
(Yang
et al.
,
2025
)
(
π
=
0.86
,
β
=
0.090
\pi=0.86,\beta=0.090
). While these models can recognize what constitutes a good answer, they still favor their own outputs under equal-quality comparisons, making them the most hazardous type of judge.
Incompetent Randomizers.
This includes Llama-3.2-3B-Instruct
(AI@Meta,
2024
)
(
π
=
0.51
,
β
=
−
0.001
\pi=0.51,\beta=-0.001
), Llama-3.1-8B-Instruct
(AI@Meta,
2024
)
(
π
=
0.77
,
β
=
−
0.060
\pi=0.77,\beta=-0.060
), Mistral-Nemo
(Mistral AI,
2024
)
(
π
=
0.75
,
β
=
−
0.052
\pi=0.75,\beta=-0.052
), Gemma-3-12B
(Gemma Team and Google DeepMind,
2025
)
(
π
=
0.78
,
β
=
0.181
\pi=0.78,\beta=0.181
), GLM-4.5-Air
(Zhipu AI and GLM Team,
2025
)
(
π
=
0.52
,
β
=
0.095
\pi=0.52,\beta=0.095
), DeepSeek-R1-0528
(DeepSeek-AI,
2025a
)
(
π
=
0.55
,
β
=
−
0.097
\pi=0.55,\beta=-0.097
), and Kimi-K2-Thinking
(Moonshot AI,
2025b
)
(
π
=
0.51
,
β
=
−
0.102
\pi=0.51,\beta=-0.102
). They lack fundamental competence, rendering their SPB values practically meaningless.
Blindly Biased Judges.
Four models combine high capability with robust negative self-preference: Claude-Sonnet-4.5 (
π
=
0.84
,
β
=
−
0.229
\pi=0.84,\beta=-0.229
), Llama-3.3-70B-Instruct
(AI@Meta,
2024
)
(
π
=
0.84
,
β
=
−
0.151
\pi=0.84,\beta=-0.151
), Hunyuan-A13B-Instruct
(Tencent Hunyuan Team,
2025
)
(
π
=
0.83
,
β
=
−
0.152
\pi=0.83,\beta=-0.152
), and Kimi-Dev-72B
(Moonshot AI,
2025a
)
(
π
=
0.84
,
β
=
−
0.117
\pi=0.84,\beta=-0.117
). Although these models exhibit strong discriminability, they display pronounced negative self-preference, favoring outputs from other models over their own.
4.4
SPB mitigation
Figure 4:
The mitigation effect of the structured multi-dimensional evaluation strategy. This figure illustrates the trajectories of SPB scores for four high-bias models before and after applying the mitigation strategy, along with percentage reduction values.
We applied the mitigation strategy to four high-bias models: LongCat-Flash-Chat (
β
=
0.307
\beta=0.307
), DeepSeek-V3.2 (
β
=
0.226
\beta=0.226
), Gemma-3-12B (
β
=
0.181
\beta=0.181
), and Gemma-3-27B (
β
=
0.152
\beta=0.152
). Figure
4
visualizes the bias trajectories before and after intervention. The strategy yields a statistically significant reduction in bias across all subjects, with the average
β
i
\beta_{i}
decreasing by 31.5%. LongCat-Flash-Chat showed the most dramatic recovery (69.9% reduction).
These results suggest that decomposing judgment into specific dimensions (e.g., Accuracy, Logic) can help reduce holistic self-preference. We also note that models with larger baseline bias (e.g., LongCat-Flash-Chat) show larger absolute reductions after intervention, which is directionally expected when improvements are measured in absolute terms. This observation is supplementary; the central finding is that the structured multi-dimensional strategy consistently lowers SPB across all tested high-bias models.
We further compare the structured evaluation against a Chain-of-Thought (CoT) baseline, where the judge is prompted to explain its reasoning before rendering a verdict (double query control and
ε
=
0.25
\varepsilon=0.25
held constant). As shown in Table
7
, CoT can sometimes yield slightly higher SPB than the baseline, whereas Ours reduces SPB for all four models in this comparison.
Table 7:
Comparison of SPB (
β
i
\beta_{i}
) under Baseline, Chain-of-Thought (CoT), and our structured multi-dimensional evaluation (Ours) for four high-bias models (
ε
=
0.25
\varepsilon=0.25
, double query unchanged).
Reduction
=
β
i
baseline
−
β
i
setting
\text{Reduction}=\beta_{i}^{\mathrm{baseline}}-\beta_{i}^{\mathrm{setting}}
and
η
=
(
β
i
baseline
−
β
i
setting
)
/
β
i
baseline
\eta=(\beta_{i}^{\mathrm{baseline}}-\beta_{i}^{\mathrm{setting}})/\beta_{i}^{\mathrm{baseline}}
. Negative entries indicate higher SPB than baseline under that setting.
Model
Setting
SPB (
β
i
\beta_{i}
)
Reduction
η
\eta
LongCat-Flash-Chat
Baseline
0.307
—
—
CoT
0.211
0.096
31.3%
Ours
0.092
0.215
69.9%
DeepSeek-V3.2
Baseline
0.226
—
—
CoT
0.234
−
0.008
-0.008
−
3.5
-3.5
%
Ours
0.206
0.020
8.8%
Gemma-3-12B
Baseline
0.181
—
—
CoT
0.155
0.026
14.4%
Ours
0.133
0.048
26.5%
Gemma-3-27B
Baseline
0.152
—
—
CoT
0.123
0.029
19.1%
Ours
0.120
0.032
21.1%
Crucially, the reduction in SPB does not come at the cost of evaluation quality. We verify that, after applying the structured mitigation strategy, the discriminability (
π
i
\pi_{i}
) on high-contrast pairs remains at a high level comparable to the baseline, confirming that the ability to identify clearly superior responses is preserved even as SPB is substantially reduced.
5
Conclusion and Discussion
This work introduces a gold-standard-free framework to quantify and mitigate self-preference bias (SPB) in LLM-as-a-Judge systems. By constructing equal-quality pairs and differencing PIR against Null-PIR, the framework separates evaluative bias from response quality without relying on human annotations. Across 20 mainstream models, we find that high capability does not necessarily imply fair evaluation: several highly discriminative models still show substantial SPB. We further show that a structured multi-dimensional prompting strategy reduces SPB by 31.5% on average, offering a practical mitigation route that does not require model retraining.
From a deployment perspective, four points are central:
(i) judge selection
should jointly consider discriminability and bias rather than model size or benchmark reputation alone;
(ii) pipeline integration
is straightforward because the mitigation operates at the prompt level, though with higher inference cost;
(iii) bias monitoring
should be periodic, since judge behavior can drift as model versions change; and
(iv) alignment safety
benefits from pre-screening judge bias before preference data are used in RLHF-style pipelines.
The current study also has several limitations that warrant further investigation. First, our measurements are defined relative to benchmark judges rather than an absolute notion of objectivity, which may introduce residual dependence on the judging behavior of these reference models. Second, the 100-sample setting, while sufficient for aggregate analysis, may underpower fine-grained conclusions for certain task types with limited representation. Third, family effects (i.e., systematic preferences toward models from the same model family or lineage, such as models developed by the same organization) are not fully disentangled from pure self-preference, making it difficult to precisely separate whether observed biases stem from self-identification or shared stylistic and training characteristics across related models.
Finally, our experiments are primarily English-centric, which may limit the generalizability of the findings to multilingual or domain-specific settings. These limitations suggest several directions for future work, including incorporating more diverse and multilingual evaluation settings, increasing sample coverage for low-frequency task categories, developing more rigorous methodologies to disentangle self- versus family-level biases, and designing more cost-efficient debiasing strategies for large-scale deployment.
CRediT authorship contribution statement
Jinming Yang:
Conceptualization, Methodology, Software, Formal analysis, Writing – original draft, Visualization.
Chuxian Qiu:
Methodology, Software, Formal analysis, Writing – review & editing.
Zhenyu Deng:
Methodology, Software, Writing – review & editing.
Xinshan Jiao:
Methodology, Software, Writing – review & editing.
Tao Zhou:
Methodology, Formal analysis, Writing – original draft.
Declaration of competing interest
The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.
Acknowledgements
This work was supported by the National Natural Science Foundation of China under Grant Nos. 42361144718 and T2293771, and STI 2030-Major Project under Grant No. 2024ZD0523903. The terms used to categorize model behavior, such as “Machiavellian”, are statistical descriptors of the relationship between discriminability and bias. These terms should not be anthropomorphized nor interpreted as implying malicious intent on the part of model developers.
Data availability
The code and data are publicly available at
https://anonymous.4open.science/r/open_self_bias-0620-0526-0807
.
References
AI@Meta (2024)
Llama 3 model card
.
Note:
Accessed: 2025-12-30
External Links:
Link
Cited by:
§4.2
,
§4.3
,
§4.3
.
Anthropic (2025)
Claude sonnet 4.5 system card
.
Note:
Technical ReportAccessed: 2025-12-30
External Links:
Link
Cited by:
§3.2
,
§4.2
.
W. Chen, Z. Wei, X. Zhu, S. Feng, and Y. Meng (2025a)
Do LLM evaluators prefer themselves for a reason?
.
arXiv preprint
2504.03846
.
External Links:
Link
Cited by:
§2.2
.
Z. Chen, H. Wang, X. Zhang, E. Hu, and Y. Lin (2025b)
Beyond the surface: measuring self-preference in LLM judgments
.
In
Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing
,
pp. 1653–1672
.
External Links:
Document
Cited by:
§2.2
,
§2.2
.
C. Chiang and H. Lee (2023)
Can large language models be an alternative to human evaluations?
.
In
Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics
,
pp. 15607–15631
.
External Links:
Document
Cited by:
§1
.
R. M. Dawes, D. Faust, and P. E. Meehl (1989)
Clinical versus actuarial judgment
.
Science
243
(
4899
),
pp. 1668–1674
.
External Links:
Document
Cited by:
§2.3
.
DeepSeek-AI (2024)
DeepSeek-v3 technical report
.
arXiv preprint
2412.19437
.
External Links:
Link
Cited by:
§4.2
,
§4.3
.
DeepSeek-AI (2025a)
DeepSeek-r1: incentivizing reasoning capability in LLMs via reinforcement learning
.
arXiv preprint
2501.12948
.
External Links:
Link
Cited by:
§4.3
.
DeepSeek-AI (2025b)
DeepSeek-v3.2 technical report
.
arXiv preprint
2512.02556
.
External Links:
Link
Cited by:
§4.2
.
H. Duan, Y. Yang, and K. Y. Tam (2024)
Do LLMs know about hallucination? an empirical investigation of LLM’s hidden states
.
arXiv preprint
2402.09733
.
External Links:
Link
Cited by:
§2.2
.
Y. Dubois, X. Li, R. Taori, T. Zhang, I. Gulrajani, J. Ba, C. Guestrin, P. Liang, and T. B. Hashimoto (2023)
AlpacaFarm: a simulation framework for methods that learn from human feedback
.
In
Proceedings of the 37th International Conference on Neural Information Processing Systems
,
pp. 30039–30069
.
External Links:
Link
Cited by:
§4.1
.
B. Efron (1979)
Bootstrap methods: another look at the jackknife
.
The Annals of Statistics
7
(
1
),
pp. 1–26
.
External Links:
Document
Cited by:
§3.4
.
J. L. Fleiss (1971)
Measuring nominal scale agreement among many raters
.
Psychological Bulletin
76
(
5
),
pp. 378–382
.
External Links:
Document
Cited by:
§3.2
.
I. O. Gallegos, R. A. Rossi, J. Barrow, M. M. Tanjim, S. Kim, F. Dernoncourt, T. Yu, R. Zhang, and N. K. Ahmed (2024)
Bias and fairness in large language models: a survey
.
Computational Linguistics
50
(
3
),
pp. 1097–1179
.
External Links:
Document
Cited by:
§2.1
.
Gemini Team and Google DeepMind (2025)
Gemini 2.5: pushing the frontier with advanced reasoning, multimodality, long context, and next generation agentic capabilities
.
arXiv preprint
2507.06261
.
External Links:
Link
Cited by:
§3.1
,
§4.1
.
Gemma Team and Google DeepMind (2025)
Gemma 3: open models based on gemini research and technology
.
arXiv preprint
2503.19786
.
External Links:
Link
Cited by:
§4.3
,
§4.3
.
Y. Guo, M. Guo, J. Su, Z. Yang, M. Zhu, H. Li, M. Qiu, and S. S. Liu (2024)
Bias in large language models: origin, evaluation, and mitigation
.
arXiv preprint
2411.10915
.
External Links:
Link
Cited by:
§2.1
.
H. Hashemi, J. Eisner, C. Rosset, B. Van Durme, and C. Kedzie (2024)
LLM-rubric: a multidimensional, calibrated approach to automated evaluation of natural language texts
.
In
Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics
,
pp. 13806–13834
.
External Links:
Document
Cited by:
§2.3
.
S. Heo, S. Son, and H. Park (2025)
HaluCheck: explainable and verifiable automation for detecting hallucinations in LLM responses
.
Expert Systems with Applications
272
,
pp. 126712
.
External Links:
Document
Cited by:
§2.1
.
Z. Hu, L. Song, J. Zhang, Z. Xiao, T. Wang, Z. Chen, N. J. Yuan, J. Lian, K. Ding, and H. Xiong (2024)
Explaining length bias in LLM-based preference evaluations
.
arXiv preprint
2407.01085
.
External Links:
Link
Cited by:
§2.1
.
Y. Huang, L. Sun, H. Wang, S. Wu, Q. Zhang, C. Gao, Y. Huang, W. Lyu, Y. Zhang, X. Li,
et al.
(2024)
Position: TrustLLM: trustworthiness in large language models
.
In
Proceedings of the 41st International Conference on Machine Learning
,
pp. 20166–20270
.
External Links:
Document
,
Link
Cited by:
§2.1
.
R. Koo, M. Lee, V. Raheja, J. I. Park, Z. M. Kim, and D. Kim (2024)
Benchmarking cognitive biases in large language models as evaluators
.
In
Findings of the 2024 Association for Computational Linguistics
,
pp. 517–545
.
External Links:
Document
Cited by:
§2.1
.
C. Lee, T. Zeng, J. Jeong, J. Sohn, and K. Lee (2025)
How to correctly report LLM-as-a-judge evaluations
.
arXiv preprint
2511.21140
.
External Links:
Link
Cited by:
§2.1
.
S. A. Lehr, M. Cipperman, and M. R. Banaji (2025)
Extreme self-preference in language models
.
arXiv preprint
2509.26464
.
External Links:
Link
Cited by:
§2.2
.
D. Li, B. Jiang, L. Huang, A. Beigi, C. Zhao, Z. Tan, A. Bhattacharjee, Y. Jiang, C. Chen, T. Wu, K. Shu, L. Cheng, and H. Liu (2024)
From generation to judgment: opportunities and challenges of LLM-as-a-judge
.
arXiv preprint
2411.16594
.
External Links:
Link
Cited by:
§2.1
.
D. Li, R. Sun, Y. Huang, M. Zhong, B. Jiang, J. Han, X. Zhang, W. Wang, and H. Liu (2025a)
Preference leakage: a contamination problem in LLM-as-a-judge
.
arXiv preprint
2502.01534
.
External Links:
Link
Cited by:
§2.1
.
H. Li, J. Chen, Q. Ai, Z. Chu, Y. Zhou, Q. Dong, and Y. Liu (2025b)
CalibraEval: calibrating prediction distribution to mitigate selection bias in LLMs-as-judges
.
In
Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics
,
pp. 16537–16552
.
External Links:
Document
Cited by:
§2.1
.
Y. Liu, D. Iter, Y. Xu, S. Wang, R. Xu, and C. Zhu (2023)
G-Eval: NLG evaluation using GPT-4 with better human alignment
.
In
Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing
,
pp. 2511–2522
.
External Links:
Document
Cited by:
§1
,
§2.1
,
§2.3
.
Y. Liu, N. S. Moosavi, and C. Lin (2024)
LLMs as narcissistic evaluators: when ego inflates evaluation scores
.
In
Findings of the 2024 Association for Computational Linguistics
,
pp. 12683–12698
.
External Links:
Document
Cited by:
§1
,
§2.2
.
Meituan Generative AI (2025)
LongCat-flash: effective long-context modeling with linear complexity
.
arXiv preprint
2509.01322
.
External Links:
Link
Cited by:
§4.2
.
Mistral AI (2024)
Mistral nemo
.
Note:
Technical ReportAccessed: 2025-12-30
External Links:
Link
Cited by:
§4.3
.
Moonshot AI (2025a)
Kimi-dev-72b: bridging the gap in developer-focused LLMs
.
arXiv preprint
2509.23045
.
External Links:
Link
Cited by:
§4.3
.
Moonshot AI (2025b)
Kimi-k2 series: enhanced thinking and reasoning capabilities
.
Note:
Technical ReportAccessed: 2025-12-30
External Links:
Link
Cited by:
§3.2
,
§4.3
.
Moonshot AI (2025c)
Kimi-linear-48b: linear attention at scale
.
arXiv preprint
2510.26692
.
External Links:
Link
Cited by:
§4.3
.
OpenAI (2025)
GPT-5 chat (gpt-5-chat-latest) — model card
.
Note:
Accessed: 2025-12-30
External Links:
Link
Cited by:
§3.1
,
§4.1
.
A. Panickssery, S. R. Bowman, and S. Feng (2024)
LLM evaluators recognize and favor their own generations
.
In
Proceedings of the 38th International Conference on Neural Information Processing Systems
,
pp. 68772–68802
.
External Links:
Link
Cited by:
§1
,
§2.2
,
§2.2
.
P. M. Podsakoff, S. B. MacKenzie, J. Lee, and N. P. Podsakoff (2003)
Common method biases in behavioral research: a critical review of the literature and recommended remedies
.
Journal of Applied Psychology
88
(
5
),
pp. 879–903
.
Cited by:
§3.4
.
S. Raza, M. Garg, D. J. Reji, S. R. Bashir, and C. Ding (2024)
NBIAS: a natural language processing framework for bias identification in text
.
Expert Systems with Applications
237
,
pp. 121542
.
External Links:
Document
Cited by:
§2.1
.
L. Shi, C. Ma, W. Liang, X. Diao, W. Ma, and S. Vosoughi (2024)
Judging the judges: a systematic study of position bias in LLM-as-a-judge
.
arXiv preprint
2406.07791
.
External Links:
Link
Cited by:
§2.1
.
C. Spearman (1904)
The proof and measurement of association between two things
.
The American Journal of Psychology
15
(
1
),
pp. 72–101
.
External Links:
Document
Cited by:
§3.1
.
E. Spiliopoulou, R. Fogliato, H. Burnsky, T. Soliman, J. Ma, G. Horwood, and M. Ballesteros (2025)
Play favorites: a statistical method to measure self-bias in LLM-as-a-judge
.
arXiv preprint
2508.06709
.
External Links:
Link
Cited by:
§2.2
.
J. Sweller (1988)
Cognitive load during problem solving: effects on learning
.
Cognitive Science
12
(
2
),
pp. 257–285
.
External Links:
Document
Cited by:
§1
,
§2.3
,
§3.6
.
Z. Tan, L. Wei, J. Wang, X. Xie, and W. Huang (2024)
Can I understand what I create? self-knowledge evaluation of large language models
.
arXiv preprint
2406.06140
.
External Links:
Link
Cited by:
§2.2
.
Tencent Hunyuan Team (2025)
Hunyuan-a13b: a new baseline for open-source 13b models
.
Note:
Technical ReportAccessed: 2025-12-30
External Links:
Link
Cited by:
§4.3
.
K. Wataoka, T. Takahashi, and R. Ri (2024)
Self-preference bias in LLM-as-a-judge
.
arXiv preprint
2410.21819
.
External Links:
Link
Cited by:
§2.2
,
§2.2
.
T. Wu, W. Yuan, O. Golovneva, J. Xu, Y. Tian, J. Jiao, J. E. Weston, and S. Sukhbaatar (2025)
Meta-rewarding language models: self-improving alignment with LLM-as-a-meta-judge
.
In
Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing
,
pp. 11548–11565
.
External Links:
Document
Cited by:
§2.2
.
xAI (2025a)
Grok 3 beta: the age of reasoning agents
.
Note:
Technical ReportAccessed: 2025-12-30
External Links:
Link
Cited by:
§4.3
.
xAI (2025b)
Grok-4-fast model card
.
Note:
Technical ReportAccessed: 2025-12-30
External Links:
Link
Cited by:
§4.2
.
W. Xu, G. Zhu, X. Zhao, L. Pan, L. Li, and W. Wang (2024)
Pride and prejudice: LLM amplifies self-bias in self-refinement
.
In
Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics
,
pp. 15474–15492
.
External Links:
Document
Cited by:
§2.2
.
A. Yang, A. Li, B. Yang, B. Zhang, B. Hui, B. Zheng, B. Yu, C. Gao, C. Huang, C. Lv, C. Zheng, D. Liu, F. Zhou, F. Huang, F. Hu, H. Ge, H. Wei, H. Lin, J. Tang, J. Yang, J. Tu, J. Zhang, J. Yang, J. Yang, J. Zhou, J. Zhou, J. Lin, K. Dang, K. Bao, K. Yang, L. Yu, L. Deng, M. Li, M. Xue, M. Li, P. Zhang, P. Wang, Q. Zhu, R. Men, R. Gao, S. Liu, S. Luo, T. Li, T. Tang, W. Yin, X. Ren, X. Wang, X. Zhang, X. Ren, Y. Fan, Y. Su, Y. Zhang, Y. Zhang, Y. Wan, Y. Liu, Z. Wang, Z. Cui, Z. Zhang, Z. Zhou, and Z. Qiu (2025)
Qwen3 technical report
.
arXiv preprint
2505.09388
.
External Links:
Link
Cited by:
§4.2
,
§4.3
.
J. Ye, Y. Wang, Y. Huang, D. Chen, Q. Zhang, N. Moniz, T. Gao, W. Geyer, C. Huang, P. Chen, N. V. Chawla, and X. Zhang (2024)
Justice or prejudice? quantifying biases in LLM-as-a-judge
.
arXiv preprint
2410.02736
.
External Links:
Link
Cited by:
§2.1
.
L. Zheng, W. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Lin, Z. Li, D. Li, E. P. Xing, H. Zhang, J. E. Gonzalez, and I. Stoica (2023)
Judging LLM-as-a-judge with MT-Bench and Chatbot Arena
.
In
Proceedings of the 37th International Conference on Neural Information Processing Systems
,
pp. 46595–46623
.
External Links:
Link
Cited by:
§1
,
§2.1
,
§2.1
,
§3.2
.
Zhipu AI and GLM Team (2025)
GLM-4.5-air: efficient inference for scalable language models
.
arXiv preprint
2508.06471
.
External Links:
Link
Cited by:
§4.3
.
Appendix A
Prompt Templates
This appendix presents the complete prompt templates used in our framework.
Tables
LABEL:tab:prompt-role
through
LABEL:tab:prompt-notes
present the quality evaluation prompts.
Table
LABEL:tab:prompt-preference
presents the preference judgment prompt.
Table
LABEL:tab:prompt-structured
details the structured multi-dimensional evaluation prompt.
Role Definition and Context Explanation