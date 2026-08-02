---
title: Prompt governance is the new data governance | CIO
id: prompt-governance-is-the-new-data-governance-cio
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:09:46.194135Z'
source: https://www.cio.com/article/4130960/prompt-governance-is-the-new-data-governance.html
source_domain: www.cio.com
fetched_at: '2026-08-02T03:09:46.183088Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 15.0
---

Prompt governance is the new data governance | CIO
Topics
Close
Analytics
Artificial Intelligence
Business Operations
Careers
CIO 100
Cloud Computing
Data Center
Data Management
Digital Transformation
Diversity and Inclusion
Emerging Technology
Enterprise Applications
Enterprise Buyer’s Guides
Generative AI
Industry
Innovation
IT Leadership
IT Management
IT Operations
IT Strategy
Networking
Project Management
Security
Software Development
Vendors and Providers
by
Timothy E. McMahon
and
Sofia Penna Elneser
Prompt governance is the new data governance
Opinion
Feb 12, 2026
14 mins
Not long ago, prompt writing felt like a personal skill. Something you refined quietly, stored in a notes app or copied between chat windows when something worked particularly well.
That model no longer holds.
Across organizations, Generative AI (GenAI) prompting is now shaping executive summaries, policy drafts, operational dashboards, clinical documentation and production user interfaces. Yet, in many environments, prompts remain scattered across chat histories, documents and inboxes—unowned, unversioned and largely invisible.
What we’re seeing is a pattern familiar to anyone who has lived through the early—and still persistent—days of shadow IT, as described by David Talby in his article
Shedding light on shadow AI
. In practice, prompts are quietly becoming enterprise interfaces, but without the governance structures we instinctively apply to data, code or systems.
And like data sprawl before it prompt sprawl creates reliability issues, inefficiency and risk long before leadership realizes what’s happening.
As Talby notes, “People use shadow AI because it’s easy…”
Prompt sprawl as shadow IT operations
In conversations with technology leaders and in recent industry reporting, the issue of prompt sprawl mirrors earlier patterns of data sprawl.
As pointed out in
Deloitte’s AI Dossier
, teams are using GenAI daily, often productively but prompts live everywhere: personal chat threads, shared documents, Slack messages, wiki pages. There is no single source of truth and no clear owner. Two people ask the same question and receive meaningfully different answers. Outputs get reworked quietly because the user phrased the prompt just a bit differently. But no one fixes the underlying cause – they simply place a Band-Aid on the issue and move on. Drift unobtrusively enters the equation, and no one notices until outputs no longer align.
This matters for three reasons CIOs care deeply about: reliability, efficiency and risk.
Reliability
. When the same prompt yields different outputs depending on who runs it or how it’s phrased, decision variance creeps in. Leadership starts questioning not just the AI, but the systems that depend on it.
Efficiency
. As teams duplicate effort, reinvent prompts and rework outputs there is no shared definition of what “good” looks like. Efficiency erodes at the edges and tribal knowledge replaces institutional process and accepted best practice.
Risk
. Ungoverned prompts can leak sensitive inputs, hallucinate policy or create inconsistent external messaging. In regulated or high-stakes environments, that is not theoretical risk, it is operational exposure, as Sofia will expand on later.
What I’m seeing isn’t an ephemeral tooling problem. Nor is it a training gap that can be solved by teaching people to write better prompts. The issue is structural. Prompts have crossed a threshold where they influence institutional outcomes, and anything that does
that
needs governance.
Towards a prompt governance framework
To make prompt governance actionable, my co-author Sofia Penna Elneser and I use a prompt governance framework that borrows intentionally from data governance and software delivery disciplines and adapts them to the realities of GenAI.
Our framework rests on five pillars.
Purpose and alignment:
Every governed prompt must have a clear intent, approved use case and owner. The goal is not to limit experimentation, but to distinguish exploratory prompts from those that shape decisions, systems or records of truth.
Quality and consistency:
Prompts define expected output shape, tone and structure. Acceptance criteria are explicit. This reduces variance and makes outputs predictable without requiring identical wording every time.
Lifecycle management:
Prompts are versioned, reviewed, refined and eventually retired as obsolescence becomes obvious. Changes are intentional, not accidental. Mature organizations maintain a prompt library just as they maintain shared code or templates.
Risk and compliance:
This aligns closely with the National Institute of Standards and Technology’s AI Risk Management Framework (
A.1.2. Organizational Governance
), which emphasizes that AI systems embedded in operational workflows require explicit governance, accountability and ongoing risk assessment. When designing and surfacing our prompts, we set a tiered risk system. Low-risk prompts require light governance. High-risk prompts, those touching policy, finance or patient care, require formal review, testing and escalation paths. We actively document use cases, inputs, outputs and known risks associated with each deployment.
Measurement and enablement:
Adoption, rework and incident rates are tracked. Teams are enabled through templates, examples and direct access to subject matter experts rather than constrained by heavy process.
To make this practical, we map these pillars onto a maturity ladder:
Risk Level 1
: Ad hoc experimentation
Risk Level 2
: Emerging structure
Risk Level 3
: Standardization
Risk Level 4
: Enterprise governance
Risk Level 5
: Regulated, safety-critical operations
Low-risk AI use cases tolerate stylistic variance; high-risk use cases cannot. Prompt governance is what allows organizations to move between those levels intentionally rather than reactively.
What this looks like in practice becomes clear when you examine real systems. In the first two case studies below, I break down how my prompts were created and versioned for production at Levels 3 and 4. Sofia then writes about the Level 5 clinical-grade digital assets she employs in a medical technology setting.
What prompt governance looks like in practice
Governing consistency in a creative AI workflow (Risk Level 3)
At the urging of our creative director, I first applied prompt governance principles in a creative context: generating illustration concepts for the American Mathematical Society (AMS) textbook
Analytic Number Theory Revealed: A First Guide to Prime Numbers
by Andrew Granville.
My role was not creative per se, that responsibility belonged to the creative team, but to improve consistency and efficiency across iterations. The author communicated an intuitive, experience-driven set of visual preferences. The project required multiple illustrations translating advanced mathematical ideas into symbolic imagery. Maintaining a coherent visual language across those illustrations was essential, as iteration cycles with the author were time-consuming and costly. From the outset, the author’s “I’ll know it when I see it” sensibility shaped the process.
Early experimentation with generative AI exposed predictable failure modes. Small changes to prompts produced noticeable stylistic drift, overly literal mathematical representations or inconsistent composition. While creativity was present, it lacked stability. Outputs varied in ways that undermined visual cohesion rather than supporting it.
Tim McMahon
I addressed this by treating the prompt as a versioned production asset rather than an ad hoc creative input. The creative director and I collaborated on a baseline specification, which I formalized into a structured style guide for use with the GenAI tool. This specification defined constraints such as symbolic density, phased execution and an embedded self-check to validate alignment with the agreed visual language before producing final output.
The result was a set of tarot-style illustrations that differed meaningfully in subject matter but clearly belonged to the same visual system. The author’s creativity was not constrained; production variability was. Once my role was complete, the creative team resumed control of the assets, refining them as needed and preparing them for publication in the final work.
The image shown in this section is an example of the prompt in action. This was not used in the author’s book, rather I used the master prompt and GenAI to create a new JSON file and then output a card explicitly for this article.
If a follow-on volume to the author’s work were to require continuation of this motif, the organization would avoid several thousand dollars in additional production effort. The system would be reused rather than built from scratch.
This reflects Level 3 prompt governance maturity: standardized quality, scalability and repeatability without the overhead of enterprise-wide controls.
Governing correctness and reuse in a production system (Risk Level 4)
I applied the same governance principles in a far less forgiving environment: a production workflow supporting the AMS Annual Meeting, also known as the
Joint Mathematics Meetings
. This is the largest mathematical conference in the world, where the daily schedule is a mission-critical asset rather than a creative deliverable.
In this case, GenAI supported the creation of scripts that consume a live pipeline of conference data normalized into JSON. This was then rendered to accessible, Bootstrap-based user interfaces. Inconsistency here is not solely an aesthetic concern. It breaks pages, confuses users and creates long-term maintenance risk.
As in Use Case 1, early experimentation exposed familiar failure modes: hallucinated fields, inconsistent keys, partial outputs and subtle divergence between environments. These failures were unacceptable at this scale. Compounding the challenge was organizational inertia, stakeholders accustomed to improvisational change were now being asked to operate within explicit, rules-based constraints.
The solution was not a better prompt and prompt chain, but a governed system boundary that can be reused year after year. I introduced a constrained, pipeline-aware specification that encoded an authoritative data source, schema validation, complete-file output and accessibility requirements.
Once those constraints were in place, outputs became predictable. Debugging shifted from “why did the model do this?” to “which rule was violated?” This workflow now moved from an experimental helper to a reliable, bounded participant in production workflows, one whose behavior could be reasoned about, validated and trusted.
In the interest of full disclosure, I will state that the system is still evolving. I do not doubt that next year the system will be better defined and further refined.
This process reflects Level 4 maturity: governed systems where the workflow is subordinate to explicit authority, validation and human accountability.
Up to this point, the failures encountered were costly but recoverable. In creative and operational systems, inconsistency wastes time, undermines trust and creates technical debt. When GenAI begins feeding systems of record and affecting human outcomes, that margin disappears. In healthcare, prompts no longer function as flexible instructions; they operate as regulated components.
Treating prompts as clinical-grade digital assets in medical technology (Risk Level 5)
Our highest-risk example comes from the medical technologyindustry.
In this setting, the stakes change. While a stylistic variance is fine in a creative workflow, even a slight deviation from the source text in a clinical environment is a liability as these outputs become part of the patient’s permanent health record.
At Meditech, Sofia works on use cases that assist providers and nurses in the transition of care. While traditional clinical summaries are notoriously time-consuming, Generative AI provides Hospital Courses and Hand-Off notes in seconds instead of hours.
For example, there is a clinical difference between saying a patient “is experiencing” a symptom versus saying a patient “has a history of” that same symptom. If an ungoverned model interprets a past condition as an acute, present emergency, it’s a clinical error with consequences, not just a creative flourish or a “model inference.”
At this level of risk, treating prompts as clinical-grade assets becomes a fundamental requirement, elevating them from simple instructions to the strategic center of context engineering. By implementing a pipeline that prioritizes specifications, versioning and rigorous evaluation, raw AI potential is turned into a reliable enterprise-grade engine.
From “vibe check” to version control: The production pipeline
When a prompt influences a patient’s permanent record or a mission-critical schedule, it can no longer live in a black box of unversioned GChat histories.
The shift from creative flexibility of Use Case 1 to the clinical precision of Meditech’s clinical-grade assets in Use Case 3 illustrates a hard truth: the tolerance for prompting by intuition drops to zero.
To move from ad-hoc experimentation to enterprise-grade reliability, prompt writing is replaced by a prompt production pipeline: a structural, repeatable discipline that mirrors software delivery. And it starts with simple questions: What and Why?
The functional spec
Just as data governance requires a schema, prompt governance requires a definition of what “good” looks like. We identify the problem before the AI solution by establishing exactly what we are trying to accomplish and why.
The functional spec determines our expected shape, tone and structure. It also identifies the sections of the prompt that shouldn’t vary. These are called “prompt partials,” and they can include the core role, the brand voice, safety wrappers, etc. In other words, the mission and vision of the prompt are an asset.
The design
With the spec as our blueprint, the full set of instructions follows. This is where ownership is assigned. To prevent unowned and invisible sprawl, every prompt needs a person or team responsible for its logic, ensuring the design meets the goals laid out in the spec.
The prompt bundle
Once designed, we lock the prompt together with the specific model version and configuration parameters (like Temperature or Top-P). This bundle belongs in a shared repository, not a private folder or a DM. This creates an audit trail that turns a black box into a transparent history of who changed what and why. It also allows for decoupling—the ability to update the AI “brain” without having to redeploy our entire application’s code.
Testing
Once we have our what and why (spec), the who (ownership) and the where (Bundle), we move on to testing.
Testing shouldn’t and can’t be a one-time event. It must happen with every iteration. This is why we determine model configurations early. By locking in the Seed, Top P, Top K, Temperature, etc., we drastically reduce the random “AI magic” factor. When these configurations are set correctly, any variation in results can be attributed to prompt changes, not just the model having a “creative” day.
The evaluation loop
Keeping our Functional Spec in mind, we develop an evaluation threshold. We ask the hard questions: What is a non-negotiable requirement in the output? Is it a specific length? A strict JSON format? A grounding in clinical truth?
Once these standards are set, we evaluate a reasonable number of high-variance test cases and document the results. It isn’t enough to just see if V5 “looks good.” We must track how prompts behave in relation to themselves and previous versions to identify drift before it enters production. Custom AI agents can assist in evaluating generated outputs as well by creating a continuous automated loop.
Review & deployment
This is a fundamental step to ensure prompt governance. Just like code, no prompt hits production without a dual-check, where a third, unbiased, human-in-the-loop audits and approves the proposed changes that will eventually become the new prompt version.
Prompts are infrastructure now
Across creative publishing, production systems and clinical documentation, we have seen the same pattern repeat. As GenAI moves closer to decision-making, prompts stop being experiments and start being infrastructure.
What changes is not the need for governance but the cost of getting it wrong.
The sooner prompts are treated as governed digital assets — owned, versioned, tested and measured — the easier it becomes to scale safely. Not because governance slows innovation, but because it makes trust possible.
For CIOs, the practical shift is simple: any prompt that is reused, shared or relied upon should be treated as a governed digital asset, not an improvisation.
This article is published as part of the Foundry Expert Contributor Network.
Want to join?
Data Governance
Data Management
Generative AI
Artificial Intelligence
Software Development
IT Leadership
by
Timothy E. McMahon
Contributor
Follow Timothy E. McMahon on LinkedIn
Timothy E. McMahon
, MS is the senior user interface and user experience designer at the American Mathematical Society where he works at the intersection of digital publishing, information systems and applied artificial intelligence. His work focuses on translating content into reliable, accessible and production-ready digital experiences.
Tim has spent his career designing and governing systems that sit close to institutional truth, including publication workflows, analytics dashboards and accessibility-first interfaces. In recent years, he has focused on prompt governance and human-in-the-loop AI practices, exploring how generative systems move from experimentation into operational and regulated environments.
He holds a master’s degree in library and information science and advanced certificates in business management and artificial intelligence. He writes on AI governance, decision-making and enterprise risk.
by
Sofia Penna Elneser
Contributor
Follow Sofia Penna Elneser on LinkedIn
Sofia Penna Elneser
, MBA is a founding member of the AI Development Team at Meditech, supporting AI solutions within clinical applications. She earned her undergraduate degree in public accounting from the Universidad de Oriente, Venezuela, and holds a master’s degree Business Administration.
As a certified generative AI Leader, she is particularly interested in the democratization of expertise, seeing AI as the great equalizer that levels the playing field for everyone around the world.
Show me more
Popular
Articles
Podcasts
Videos
case study
How AI helps the US Senate Federal Credit Union better manage risk
By Joanne Carew
Jul 31, 2026
5 mins
Banking
CIO
Financial Services Industry
case study
The gen AI helping Aetna review millions of medical records
By Thor Olavsrud
Jul 31, 2026
5 mins
CIO
CIO 100
Electronic Health Records
opinion
The blueprint for innovation: 3 ways regulatory readiness is a competitive advantage
By Saurabh Joshi
Jul 31, 2026
7 mins
Government
Innovation
Laws and Regulations
podcast
Naveed Anwar on AI, Leadership, and the Future of Enterprise Technology
Jul 29, 2026
15 mins
CIO Leadership Live
podcast
The Foundation First - ING's Global CIO on Why AI Pilots Fail to Scale
By Estelle Quek
22 Jul 2026
25 mins
Banking
CIO
Financial Services Industry
podcast
Niraj Bhatt on Innovation, AI, and Modern Technology Leadership
Jul 20, 2026
13 mins
Innovation
video
How Chainguard secures open source libraries
Jul 30, 2026
10 mins
Anti Malware
Cyberattacks
Developer
video
Naveed Anwar on AI, Leadership, and the Future of Enterprise Technology
Jul 29, 2026
15 mins
CIO Leadership Live
video
SmartBear shows how AI agents can help QA teams keep pace with AI-generated software
Jul 28, 2026
12 mins
Code Security
Developer
Devops
Sponsored Links
The fastest PCs with multi-day battery life for your business.
See Why Five9’s AI-Powered CX Platform Drives Real Results
Build, buy, or borrow? A CIO guide to agentic AI strategy
From pilots to performance: AI‑driven growth with EY Consulting.