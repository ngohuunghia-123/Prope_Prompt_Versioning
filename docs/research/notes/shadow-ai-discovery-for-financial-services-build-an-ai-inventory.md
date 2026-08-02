---
title: 'Shadow AI Discovery for Financial Services: Build an AI Inventory'
id: shadow-ai-discovery-for-financial-services-build-an-ai-inventory
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:10:13.103257Z'
source: https://www.thedataexperts.us/writing/shadow-ai-discovery-building-a-real-ai-inventory.html
source_domain: www.thedataexperts.us
fetched_at: '2026-08-02T03:10:13.094258Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 15.0
---

Shadow AI Discovery for Financial Services: Build an AI Inventory
shipping production AI
·
since 2026
NAICS 541330 / 541511 / 541512 / 541519  ·  CMMC-aware
Refinery Report
/
AI Security
/
post · entory
AI Security
Shadow AI
AI Inventory
AI Governance
Shadow AI Discovery for Financial Services: Build an AI Inventory
Shadow AI discovery, made concrete: how to find unsanctioned AI use across your stack and build an AI inventory that survives contact with reality.
D
By the DSE practice team
Operator-led practice ·
how we research & review
June 14, 2026
15 min · 3,233 words
By the DSE practice team
· published June 14, 2026 · reviewed June 14, 2026
Every AI governance program runs into the same wall in week one. The board asks a simple question, “what AI are we using, and where is our data going,” and nobody can answer it with confidence. Policies, model testing, vendor reviews, and risk tiers all assume a list of systems to apply them to. Shadow AI is the gap between the systems on that list and the systems people are actually using. You cannot govern, secure, or test what you cannot see, so discovery comes first.
This post is the concrete version of that work. It explains what shadow AI is, why it grows faster than policy, and the actual channels you use to find unsanctioned AI use. Then it lays out what belongs in an AI inventory that survives contact with reality, and how that inventory becomes the baseline a governance program is built on. We will keep the scope honest. Discovery finds most of your AI footprint, not all of it, and an inventory is a living artifact that decays the moment you stop maintaining it.
Want to put this into practice? Use our
AI inventory & risk-tiering wizard
.
What shadow AI is and why it grows
Shadow AI is any AI tool, model, or service in use without going through your organization’s review and approval. It is the AI version of shadow IT. The difference is that AI capability now ships inside tools people already have, so the surface is larger and the entry points are quieter.
The growth is structural, not a discipline problem. A SaaS vendor adds an AI assistant to a product your team already pays for, and shadow AI appears with no new purchase. An employee pastes a contract into a free chatbot to summarize it, and sensitive data leaves your boundary with no log on your side. A developer wires an AI SDK into a service with a personal API key, and a model is now in your production path that no architecture review saw.
None of these require a budget line or an IT ticket. That is why shadow AI accumulates between governance cycles, and why a policy written in January is already out of date by spring. The tooling moves faster than the approval process that is supposed to gate it.
There is a quieter driver too. AI features get bundled into renewals and platform updates, so a tool you approved last year for one purpose now ships a model you never evaluated. The system on your inventory and the system in production have silently diverged. Shadow AI is not only the tools people brought in around you. It is also the AI that arrived inside tools you already trusted.
The cost of an unknown AI footprint
An unknown AI footprint is not an abstract governance gap. It maps to concrete exposure, and the two clearest forms are data leakage and supply-chain risk.
Data leakage is the first. When a sanctioned tool is unknown, so is the data flowing through it. Sensitive records, source code, customer information, and internal strategy can move into a third-party model with no data-handling review and no record of where it went. The OWASP LLM Top 10 names this directly as LLM02, Sensitive Information Disclosure. You cannot apply a data-classification control to a system you do not know is processing your data.
Supply-chain risk is the second. Every unsanctioned AI tool is an unvetted dependency. It pulls in models, plugins, and connectors your team never reviewed, and for agentic tools it can connect to external services that act on your systems. The OWASP LLM Top 10 names this as LLM03, Supply Chain. An AI tool that connects an agent to outside tools, including through the Model Context Protocol, inherits the integrity problems of everything it connects to, which is exactly the surface our
MCP supply chain security post
covers.
There is also a governance cost that is easy to miss. When a regulator, auditor, customer, or board asks you to account for your AI use, an unknown footprint means you answer from guesses. For a bank or fintech under model-risk supervision, the inability to produce a credible inventory is itself a finding, which is why an
AI governance readiness assessment
starts here rather than with policy. In NIST AI RMF terms, knowing your AI footprint is part of the MAP function, establishing the context and identifying the AI systems in use. Skip it and the rest of a governance program has nothing solid to stand on.
How to discover unsanctioned AI use (shadow AI in practice)
Discovery is not one scan. Shadow AI hides in different layers of your environment, so finding it means pulling from several independent channels and reconciling what they tell you. No single source is complete, but the overlap of many gets you close. Run these channels in parallel, then merge the results.
Network and DNS egress.
Inspect outbound traffic and DNS resolution for connections to known AI provider endpoints and AI SaaS domains. Egress logs, DNS query logs, and firewall data reveal tools that talk to external model APIs, even when no one filed a request. This is often the highest-yield channel because it sees traffic regardless of how the tool was introduced.
Identity and OAuth grants.
Review your single sign-on and OAuth consent logs for AI applications employees have granted access to. Every “sign in with” and “connect your account” to an AI service leaves a grant record in your identity provider. Those grants frequently expose tools that never appeared in any procurement system, along with the scopes they were given.
Expense and SaaS spend.
Pull credit card statements, expense reports, and SaaS management or finance data for AI subscriptions. Individual seats and team plans bought on a card are a common entry point for shadow AI, and the financial trail is one of the few records that is hard to bypass.
Browser extensions and IDE plugins.
Audit installed browser extensions and developer IDE plugins across managed devices. AI writing assistants, code-completion tools, and “summarize this page” extensions route data to external models and are easy to install without review. Endpoint management tooling can enumerate what is actually installed.
Code repositories.
Scan your repositories for AI SDK imports, model client libraries, and AI provider API keys or endpoint references in code and configuration. A model wired into a service through a personal or shared key is shadow AI in your production path, and the import statements and key patterns make it findable. Treat any discovered key as a secret to rotate, not just a record to log.
CASB and proxy logs.
If you run a cloud access security broker or a web proxy, mine those logs for AI service categories. They give you a consolidated, traffic-level view of which AI tools are reaching the internet from inside your boundary, and they often catch what device-level audits miss.
MCP and agent connections.
Inventory the Model Context Protocol servers and external tool connections wired into any agents your teams run. Agentic tools connect to outside services that can read data and act on systems, so an unlisted MCP connection is both shadow AI and a supply-chain exposure. This is where the discovery pillar and the supply-chain pillar meet.
Survey and amnesty.
Pair the technical channels with a structured, no-blame employee survey and a short amnesty window. People will tell you about tools you would never find in a log if you ask without threatening consequences. Self-reporting catches the manual, copy-paste use of free tools that leaves almost no technical trace, which is the hardest category to discover any other way.
Run the technical channels for the systems and the human channels for the behavior, then reconcile. A tool that shows up in egress, OAuth grants, and a survey response is confirmed. A tool that shows up in only one place is a lead to chase. The discipline is in the reconciliation, not in any single tool.
What belongs in a usable AI inventory
A list of tool names is not an inventory. It cannot drive a governance decision because it does not capture what makes a system risky. A usable AI inventory records enough about each system that someone can tier its risk and decide what to do about it. For each entry, capture the following.
System or tool.
What it is, in plain language, including the specific feature in use, not just the parent product.
Owner.
The named person or team accountable for it. An entry with no owner is an entry no one will maintain.
Data classification handled.
The most sensitive class of data the system touches, public through restricted. This single field drives most of the risk decision.
Vendor and model.
Who provides it and which model or model family it uses, since the same vendor can offer very different models with different handling terms.
Hosting and data residency.
Whether it is third-party SaaS, self-hosted, or in your own cloud, and where the data goes when it leaves your boundary. For regulated data, a
secure self-hosted AI deployment
keeps the model and the audit trail inside that boundary.
Access scope.
What the tool can reach, read, and act on. For agentic tools this includes connected tools and MCP servers, since the scope is the blast radius.
Business purpose.
Why it is used and what it would cost to remove it. Purpose is what separates a tool worth governing from a tool worth retiring.
Sanctioned or not.
Whether it has been through review and approved, is under review, or is unsanctioned and pending a decision.
Risk tier.
Your resulting assessment, typically a simple low, medium, or high, derived mostly from data classification and access scope.
These fields are deliberately boring, and that is the point. They are the minimum a senior reviewer needs to tier a system and decide whether to sanction it, restrict it, or retire it. An inventory that records names but not data classification and access scope is a directory, not a governance tool, because it cannot answer the only question that matters: how much does this system expose us, and who owns that.
From inventory to governance readiness
A completed inventory is a snapshot, and a snapshot is not a program. The value is in what you do next, which is turning a one-time discovery exercise into a baseline that a governance program maintains over time.
Three moves convert the snapshot into readiness. First, tier and triage. Sort the inventory by risk and handle the high-tier, high-data-classification systems first, rather than trying to govern everything at once. Second, assign and decide. Give every entry an owner and a disposition, sanction with conditions, restrict, or retire, so the inventory drives action instead of sitting in a spreadsheet. Third, close the loop. Wire the discovery channels into a recurring cadence, because shadow AI regenerates and a static inventory is wrong within a quarter.
This is also where the inventory connects to the rest of a governance program. In NIST AI RMF terms, discovery and inventory support the MAP function, identifying the AI in use and its context, and they feed the GOVERN function by giving oversight something concrete to oversee. A financial-services program will recognize this as the same evidence a
banking AI governance
review expects to see before it can tier model risk. NIST AI RMF is a voluntary framework with no certification attached, so the goal here is alignment and readiness, not a conformity claim. The inventory is the artifact that makes the rest of the framework usable. Once you can tier your systems, the control mapping in our
OWASP LLM Top 10 to NIST AI RMF post
has real systems to apply itself to instead of hypotheticals.
What discovery covers, and what it does not.
What discovery covers:
A well-run discovery exercise, pulling from network and DNS egress, identity and OAuth grants, expense and SaaS spend, endpoint and IDE audits, code-repository scans, CASB and proxy logs, MCP and agent connections, and an honest employee survey, surfaces most of your AI footprint. The overlap across independent channels is what gives you confidence in the picture you build.
What discovery does not cover:
Discovery is point-in-time and is never fully exhaustive. You find most of your AI use, not all of it. Manual, copy-paste use of free tools that leaves no technical trace can hide from every channel except self-reporting, and even then only if someone remembers to report it. An inventory is a living artifact, not a deliverable. It decays the moment the discovery cadence stops, because new tools, bundled AI features, and new connections appear continuously. Treat the inventory as a baseline to maintain, not a box to check. We make no claim of complete or guaranteed coverage, and any vendor that does is selling certainty that does not exist.
FAQ
What is shadow AI?
Shadow AI is any AI tool, model, or service used in an organization without going through review and approval. It includes tools employees bring in on their own, AI features bundled into SaaS products you already pay for, and models wired into code with personal keys. Because AI capability now ships inside tools people already have, shadow AI grows faster than the approval process meant to gate it.
Why is shadow AI a security risk?
An unsanctioned AI tool is both a data-leakage path and an unvetted dependency. Sensitive data can flow into a third-party model with no handling review, which the OWASP LLM Top 10 names as LLM02, Sensitive Information Disclosure. The tool also pulls in models and connections your team never reviewed, which maps to LLM03, Supply Chain. You cannot apply a control to a system you do not know exists.
How do you discover shadow AI?
You pull from several independent channels and reconcile them: network and DNS egress to known AI endpoints, single sign-on and OAuth grant logs, expense and SaaS spend, browser-extension and IDE-plugin audits, code-repository scans for AI SDKs and API keys, CASB and proxy logs, MCP and agent connections, and a no-blame employee survey with an amnesty window. No single source is complete, but the overlap of many gets you close.
What should an AI inventory include?
For each system, record the tool and the specific feature, a named owner, the most sensitive data classification it handles, the vendor and model, hosting and data residency, access scope, business purpose, whether it is sanctioned, and a resulting risk tier. Data classification and access scope drive most of the risk decision, so an inventory without those fields is a directory, not a governance tool.
Is an AI inventory a one-time project?
No. Discovery is point-in-time and an inventory is a living artifact. New tools, AI features bundled into renewals, and new agent connections appear continuously, so a static inventory is wrong within a quarter. The inventory is a baseline to maintain on a recurring cadence, not a deliverable to file once.
Does building an AI inventory make us compliant?
No. An inventory is the prerequisite for governance work, not a compliance outcome. It supports the MAP and GOVERN functions of the voluntary NIST AI RMF by giving oversight something concrete to act on, and it makes control mapping usable. It positions you for readiness and alignment. It is not a certification or conformity claim, and no inventory by itself makes an organization compliant with anything.
You cannot govern what you cannot see, so a credible AI inventory is the prerequisite for every other piece of an AI governance program. Turning a one-time discovery exercise into a maintained governance baseline, tiered by risk, owned, and refreshed on a cadence, is the first step of an
AI governance readiness assessment
. If you want a senior team to run that discovery against your actual environment and stand up the baseline, that is exactly where it begins.
Get the checklist first.
Download the
AI Governance Checklist
for the exact inventory fields, risk-tiering criteria, and readiness evidence this post describes, ready to put your shadow-AI discovery to work.
Key facts
Shadow AI discovery pulls from eight independent channels (network and DNS egress, identity and OAuth grants, expense and SaaS spend, browser and IDE audits, code-repository scans, CASB and proxy logs, MCP and agent connections, and a no-blame employee survey), then reconciles the overlap (DSE, 2026).
Discovery is point-in-time and never fully exhaustive, and an AI inventory decays the moment the discovery cadence stops, so it must be maintained as a baseline rather than filed once (DSE, 2026).
Read next · AI Security & Governance
US Treasury Financial Services AI Risk Management Framework: A Practical Guide for Banks
Cyber Insurance Evidence Readiness Checklist
What a Cybersecurity Risk Assessment Includes and Costs
P
Founder · Principal Engineer
Data & AI engineer · 10+ yrs hands-on
Writes most of the long-form here. Lives in the codebase. Active on
GitHub
and
LinkedIn
.
↗ github
↗ linkedin
↗ substack
Related: keep reading
AI Governance
Financial Services
US Treasury Financial Services AI Risk Management Framework: A Practical Guide for Banks
The US Treasury FS AI RMF, issued in February 2026, gives banks a 230-control-objective matrix for governing AI. Here is how to prioritize it against SR 26-2 an
Data Science & Engineering Experts
August 1, 2026
↗
AI Governance
Financial Services
AI Risk Appetite Statements and KRIs for US Banks: A Practitioner Guide
How US banks write a defensible AI risk appetite statement and calibrate the ten-indicator KRI framework that makes it operational, with threshold design and bo
Data Science & Engineering Experts
July 15, 2026
↗
Healthcare
HIPAA
HIPAA AI Governance Readiness: The Program Behind the Boundary Decision
A practical readiness checklist for healthcare organizations building an AI governance program under HIPAA: use-case inventory, BAA mapping, minimum-necessary s
Data Science & Engineering Experts
July 5, 2026
↗
§ Next step
Not sure which of these is
you
?
Tell us what's broken in a paragraph and a principal reads it directly, or walk the ladder from a low-commitment first engagement up to retained work.
Tell us what's broken
→
See how engagements ladder
One long-form a week.
No marketing.
Subscribe to the Refinery Report. Practitioner deep-dives on AI engineering, security, and the realities of running production systems. Unsubscribe in one click.
Leave empty:
Your email
Subscribe
→
~12 issues / quarter
Email only used for the newsletter. No tracking pixels.