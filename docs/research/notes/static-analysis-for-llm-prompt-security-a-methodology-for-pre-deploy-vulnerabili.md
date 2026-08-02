---
title: 'Static Analysis for LLM Prompt Security: A Methodology for Pre-Deploy Vulnerability
  Detection. - DEV Community'
id: static-analysis-for-llm-prompt-security-a-methodology-for-pre-deploy-vulnerabili
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:10:05.320519Z'
source: https://dev.to/meghal_parikh_b8c5c6e3244/static-analysis-for-llm-prompt-security-a-methodology-for-pre-deploy-vulnerability-detection-48oc
source_domain: dev.to
fetched_at: '2026-08-02T03:10:05.304518Z'
fetch_provider: builtin
status: draft
type: note
tier: commentary
content_type: blog
deprecated: false
utility_score: 15.0
---

Static Analysis for LLM Prompt Security: A Methodology for Pre-Deploy Vulnerability Detection. - DEV Community
Static Analysis for LLM Prompt Security: A Methodology for Pre-Deploy Vulnerability Detection
How applying SAST principles to LLM prompt strings catches security vulnerabilities that runtime tools miss — and why the pre-deploy layer matters more than most teams realize
Meghal Parikh · PromptSonar · March 2026 · 18 min read
Most LLM security discussions focus entirely on runtime — intercept the prompt, screen it, block the bad request. That framing misses a significant portion of the attack surface.
A large class of LLM vulnerabilities originate in source code — in the prompt strings, system instructions, and role definitions that developers write directly into their applications before any user interaction occurs. Nobody is scanning those.
This is the methodology I built to change that.
1. Where This Started
I spent several years as an SRE working on production systems that increasingly relied on LLM APIs. When my team started embedding OpenAI and Anthropic calls into customer-facing workflows, we ran into a question nobody had a good answer to: how do you security-review a prompt the same way you'd security-review a SQL query or an API call?
With SQL injection, the answer has been established for twenty years. You don't pass user input directly into a query string. You use parameterized queries. You have SAST tools that catch violations at code review time. You have CI/CD gates that block PRs before they merge.
With LLM prompts, none of that infrastructure existed. Teams were writing system prompts that granted sweeping capabilities, injecting user input directly into prompt templates without sanitization, and shipping code that contained jailbreak-susceptible patterns — all without any automated review.
The security review process for LLM prompts in most engineering teams in 2024 was: a human read the prompt, thought it looked fine, and approved the PR. That is not a security process. That is wishful thinking.
PromptSonar was built to change that. Not to replace human judgment, but to give teams the same automated first-pass review for prompt security that they already have for every other type of vulnerability in their codebase.
2. Why Static Analysis — and What It Actually Means Here
Static analysis means analyzing code without executing it. You parse the source files, extract the constructs you care about, apply rules to those constructs, and report violations. The key property is that this happens at development time — before any user sends a request, before any prompt reaches an LLM API, before anything executes in production.
For prompt security specifically, the constructs we care about are string literals that get passed to LLM APIs. The challenge is identifying them. Unlike SQL queries, which have a well-defined syntax and clear call patterns, LLM prompts appear in dozens of different forms:
Direct string arguments to
openai.chat.completions.create()
Template literals assembled from multiple variables
System prompt strings defined as module-level constants
Prompt templates loaded from configuration files
LangChain
PromptTemplate
definitions
Anthropic client messages arrays
A naive approach — grep for strings near API calls — produces an unacceptable false positive rate and misses large categories of prompts entirely. The methodology described here uses AST parsing to understand code structure rather than just text patterns.
2.1 The case against runtime-only security
Runtime interception tools operate on a different layer. Tools like Google Model Armor, Lakera Guard, and Azure Prompt Shields are genuinely useful. But they address a different problem than static analysis, and treating them as a complete solution misses a significant portion of the attack surface.
The limitations of runtime-only approaches:
They add latency to every request.
For applications where response time matters, even 50ms of additional processing per call is a meaningful cost.
They cannot detect vulnerabilities in static prompt content.
The system prompt that ships with the application and never changes is only visible in source code.
They operate post-deployment.
A vulnerability that reaches the runtime layer has already shipped.
They create a dependency on an external service for security.
If the runtime screening service has an outage, the application's security posture changes instantly.
A security architecture that only has runtime screening is like a building that only has a front door guard but no locks on the windows. The guard matters. So do the locks.
Static analysis does not replace runtime screening. The two layers are complementary by design.
3. The Detection Methodology
3.1 Language-aware string extraction
PromptSonar uses Tree-sitter, a parser generator that builds concrete syntax trees for source files. Tree-sitter supports over 40 languages and produces parse trees that accurately reflect the structure of the code, including string literal types, template expressions, and function call argument positions.
For each supported language, the extraction layer uses two complementary strategies:
Framework pattern detection.
Known LLM SDK call patterns are matched against the AST. For example, in TypeScript:
openai.chat.completions.create()
,
anthropic.messages.create()
,
langchain PromptTemplate.fromTemplate()
. The arguments at specific positions in these calls are extracted as prompt candidates.
Heuristic string detection.
String literals that exceed a minimum length threshold and appear in contexts associated with AI or prompt handling are flagged as candidates even without a matching framework pattern. This catches teams using custom HTTP clients or less common SDKs.
The six languages supported in v1.0.26 are TypeScript, JavaScript, Python, Go, Rust, Java, and C#.
3.2 The normalization pipeline
Before any rule evaluation occurs, extracted strings pass through a multi-stage normalization pipeline developed specifically to defeat evasion techniques that attackers use to bypass pattern-matching scanners.
The pipeline stages in order:
Literal escape resolution.
Tree-sitter extracts string values as they appear in source files. When a developer writes
\u200B
in source code, Tree-sitter may return the six-character sequence rather than the actual Unicode character. The first normalization stage resolves all
\uXXXX
escape sequences to their actual Unicode equivalents.
Zero-width character stripping.
Characters including zero-width space (U+200B), zero-width non-joiner (U+200C), zero-width joiner (U+200D), and byte-order mark (U+FEFF) have no visible glyph and are used to break the contiguous character sequences that regex patterns require. These are stripped before matching.
Homoglyph normalization.
Characters from Cyrillic, mathematical alphanumeric symbol, and enclosed alphanumeric Unicode blocks that are visually identical to Latin characters are mapped to their Latin equivalents. This defeats attacks where 'Ignore all previous instructions' is written with Cyrillic characters that look identical to Latin but have different Unicode code points.
Base64 candidate detection.
Substrings matching the Base64 character set and exceeding 64 characters are decoded and the decoded content is run through the rule set. The 64-character threshold was tuned to prevent false positives from legitimate Base64-like strings such as import paths like
openai/resources
.
Rule evaluation against normalized content.
All rules are applied to the normalized string. Findings are reported against the original string at the original source location — the normalization is internal to the detection pipeline and never surfaces in output.
The decision to build a normalization-first pipeline rather than adding evasion-specific rules was deliberate. A normalization layer that converts homoglyphs to Latin before any matching occurs handles the evasion for all patterns simultaneously, with no rule duplication.
3.3 The rule set
PromptSonar v1.0.26 implements 21 rules across seven security pillars mapped to the OWASP LLM Top 10 (2025):
Prompt Injection (C1, C2)
— Direct injection patterns, instruction resets, jailbreak phrases, mode switch attempts. False positive rate: ~4% each.
Privilege Escalation (C3)
— Patterns indicating attempts to elevate the model's capabilities or bypass safety instructions. False positive rate: ~2%.
Unbounded Persona (H1)
— Role definition patterns that grant excessively broad capabilities. Noisiest rule at ~8% FP rate — legitimate system prompts frequently use role-defining language that overlaps with malicious patterns.
Sensitive Data Exposure (H2, H3)
— PII patterns in prompt strings: SSN formats, credit card patterns, API key patterns. Low FP rate because these patterns are highly specific.
Insecure Output Handling (H4)
— Patterns indicating the model's output may be passed to downstream systems without sanitization. FP rate: ~3%.
Evasion Detection (E1, E2, E3)
— Base64 encoding, Unicode homoglyph substitution, and zero-width character injection. These rules fire after the normalization pipeline has decoded or normalized the content.
RAG and Tool Poisoning (R1, R2)
— Patterns associated with indirect prompt injection through retrieval-augmented generation pipelines and tool call manipulation.
3.4 Scoring and severity
Each finding is assigned a severity level — Critical, High, Medium, or Low. The scoring system applies a weighted calculation across the seven pillars, with the security pillar weighted at 40% of the total score.
A hard cap means any scan with Critical findings cannot score above 49 out of 100. This reflects a deliberate judgment: a single critical vulnerability is a disqualifying condition, not a factor to be averaged away.
For CI/CD integration, teams gate on exit codes: 0 for clean, 1 for low/medium findings, 2 for high findings, 3 for critical findings.
4. The Governance Layer
Security tooling that only reports findings has limited enterprise adoption. Engineers and security teams need to configure acceptable thresholds, suppress known false positives with documented rationale, and enforce policy consistently.
PromptSonar implements a Governance DSL as a YAML configuration file:
# .promptsonar-policy.yaml
version
:
1
rules
:
max_critical
:
0
max_high
:
2
fail_on_evasion
:
true
waivers
:
-
id
:
WVR-2026-001
rule
:
H1
path
:
src/agents/customer-service.ts
reason
:
Reviewed and approved — persona scope is bounded by downstream validation
approved_by
:
security-team
expires
:
2026-09-01
Enter fullscreen mode
Exit fullscreen mode
The waiver system provides a middle path between suppressing rules globally (destroying signal) and living with persistent false positive noise (causing engineers to ignore the tool). Each waiver is file-scoped, time-bounded, and attribution-required — constraints that prevent waiver abuse while making legitimate suppressions practical.
5. Prompt SBOM: Extending the Pre-Deploy Model
Software Bill of Materials (SBOM) has become an established practice in software supply chain security following Executive Order 14028 (2021). The same concept applies to LLM prompt strings.
Running
promptsonar sbom ./src --output prompt-sbom.json
produces a CycloneDX v1.4 structured inventory of every prompt string in the codebase, including:
The string content and its hash
The source file and line number
The rule evaluation results at scan time
The version of PromptSonar that performed the scan
A timestamp of the scan
The practical application: if the runtime system knows what prompt strings were reviewed and approved at build time — their content and their hashes — it can detect when a prompt executing in production differs from the reviewed version. That drift is a signal worth investigating.
The Prompt SBOM is not just a report. It is a cryptographic record of what was reviewed, when it was reviewed, and what the review found. That is the foundation for a complete prompt security audit trail.
6. False Positive Management
The credibility of any static analysis tool is inseparable from its false positive rate. A tool that produces too much noise gets ignored.
Rule design.
Rules are designed with specificity as the primary objective. A rule that matches
ignore
as a substring will produce false positives on every codebase that has an
ignoreErrors()
function. The actual injection pattern requires
ignore
followed by specific modifiers in a context that indicates instruction-following rather than error handling.
Threshold tuning.
The Base64 detection threshold illustrates how empirical tuning improves precision. The initial implementation flagged any Base64-like string of 16 characters or more. During end-to-end testing, this produced false positives on import paths like
openai/resources
which contain a slash character present in the Base64 alphabet. Raising the threshold to 64 characters eliminated these false positives while preserving detection of actual Base64-encoded jailbreaks.
Suppression and waivers.
For findings that are legitimate by design, the waiver system provides a structured suppression mechanism. File-scoped, time-bounded, attribution-required.
7. Integration Patterns
CLI
npx @promptsonar/cli scan ./src
npx @promptsonar/cli scan ./src
--format
sarif
--output
results.sarif
npx @promptsonar/cli scan ./src
--policy-file
.promptsonar-policy.yaml
npx @promptsonar/cli sbom ./src
--output
prompt-sbom.json
Enter fullscreen mode
Exit fullscreen mode
JSON and SARIF v2.1.0 output formats are supported. SARIF enables native integration with GitHub Code Scanning without additional tooling.
GitHub Action
-
name
:
PromptSonar scan
uses
:
promptsonar/action@v1
with
:
path
:
'
./src'
policy-file
:
'
.promptsonar-policy.yaml'
fail-on
:
'
high'
Enter fullscreen mode
Exit fullscreen mode
Most teams start with
fail-on: critical
and add
high
after clearing their initial backlog of findings.
VS Code Extension
The extension surfaces findings inline as developers write code — the same experience as TypeScript type errors or ESLint violations. Security feedback at the point of authorship rather than at code review time.
8. What Static Analysis Cannot Do
Dynamic prompt construction.
Prompts assembled at runtime from multiple variables, database values, or user inputs are not visible to static analysis by definition. This is the primary use case for runtime interception tools.
Semantic paraphrases.
An attacker who paraphrases a jailbreak instruction to avoid known patterns will not be caught by pattern matching. Semantic similarity detection for prompt security is an active research area not addressed by this approach.
Novel attack patterns.
The rule set covers known attack patterns. Novel techniques not yet documented will not be detected until rules are updated — the same limitation that affects all signature-based security tools.
Multilingual prompts.
The current rule set is calibrated for English-language prompts. Internationalized applications may see elevated false positive rates after normalization.
These limitations define the scope of static analysis. A development team that understands what it catches and what it does not is equipped to build a layered security architecture that addresses the full attack surface.
9. Relationship to Existing Security Research
The OWASP LLM Top 10 (2025) provides the most widely adopted taxonomy of LLM application vulnerabilities. PromptSonar's rule set maps directly to this taxonomy.
Prior work on prompt injection detection has focused primarily on runtime classification approaches — training models to detect injection attempts, or using NLP techniques to identify malicious intent. Representative work includes Perez and Ribeiro (2022) on attack techniques for language models [2], and Greshake et al. (2023) on indirect prompt injection through LLM-integrated applications [3].
The static analysis approach described here is architecturally distinct from these runtime classification approaches in two key respects. First, it operates on source code rather than on prompts at execution time. Second, it uses AST parsing to understand code structure rather than NLP to understand prompt semantics — making it both faster and more precise for the class of vulnerabilities it targets.
To our knowledge, the systematic application of SAST methodology to LLM prompt strings — using AST parsing for extraction, normalization-first pipelines for evasion detection, and a rule set mapped to a recognized vulnerability taxonomy — has not been described in the published literature prior to this work.
10. What Comes Next
The pre-deploy layer is necessary but not complete. The next logical step is closing the gap between what was reviewed in source code and what is actually executing in production.
The Prompt SBOM provides the foundation for this. With a cryptographic record of reviewed prompts at build time, a runtime monitoring system can compare executing prompts against the approved baseline and flag deviations. This drift detection capability is more valuable than blanket runtime screening of all prompts — it focuses attention on the anomaly rather than requiring review of every request.
The broader goal is a prompt security posture that mirrors what the industry has built for application security over the past twenty years: development-time scanning, CI/CD gating, runtime monitoring, audit trails, and governance processes that make security a first-class engineering concern.
LLM applications are not going to become less complex or less security-critical. The tooling needs to catch up.
References
OWASP Foundation. OWASP Top 10 for Large Language Model Applications, Version 2025.
Perez, F., & Ribeiro, I. (2022). Ignore Previous Prompt: Attack Techniques For Language Models. arXiv:2211.09527.
Greshake, K., et al. (2023). Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection. arXiv:2302.12173.
Executive Order 14028 on Improving the Nation's Cybersecurity (2021). The White House.
CycloneDX v1.4 Specification. OWASP Foundation.
Boucher, N., et al. (2022). Bad Characters: Imperceptible NLP Attacks. IEEE Symposium on Security and Privacy.
Parikh, M. (2026). Detecting Unicode Homoglyph and Zero-Width Character Evasion in LLM Prompt Injection Attacks. Medium / arXiv preprint.
Tree-sitter. An incremental parsing library.
https://tree-sitter.github.io/tree-sitter/
SARIF v2.1.0. Static Analysis Results Interchange Format. OASIS Standard.
Meghal Parikh is a Site Reliability Engineer and the founder of PromptSonar, a static analysis framework for LLM prompt security.
VS Code:
marketplace.visualstudio.com/items?itemName=promptsonar-tools.promptsonar
GitHub:
github.com/meghal86/promptsonar
CLI:
npx @promptsonar/cli scan ./src
Published March 2026 · CC BY 4.0 · Article 2 in the PromptSonar research series.
Article 1:
Detecting Unicode Homoglyph and Zero-Width Character Evasion in LLM Prompt Injection Attacks
Create template
Templates let you quickly answer FAQs or store snippets for re-use.
Submit
Preview
Dismiss
Some comments may only be visible to logged-in visitors.
Sign in
to view all comments.
Are you sure you want to hide this comment? It will become hidden in your post, but will still be visible via the comment's
permalink
.
Hide child comments as well
Confirm
For further actions, you may consider blocking this person and/or
reporting abuse
We're a place where coders share, stay up-to-date and grow their careers.
Log in
Create account