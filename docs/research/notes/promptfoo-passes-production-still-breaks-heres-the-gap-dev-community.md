---
title: PromptFoo Passes. Production Still Breaks. Here's the Gap. - DEV Community
id: promptfoo-passes-production-still-breaks-heres-the-gap-dev-community
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:59.274859Z'
source: https://dev.to/clawgenesis/promptfoo-passes-production-still-breaks-heres-the-gap-24em
source_domain: dev.to
fetched_at: '2026-08-02T03:11:59.266862Z'
fetch_provider: builtin
status: draft
type: note
tier: commentary
content_type: blog
deprecated: false
utility_score: 16.0
---

PromptFoo Passes. Production Still Breaks. Here's the Gap. - DEV Community
I had PromptFoo set up in CI. Evals passed on every deployment. The model still silently changed in production three weeks later — without any CI run, without any code change.
This is the gap eval frameworks don't cover. And it's not PromptFoo's fault.
What PromptFoo does (and does well)
PromptFoo is a developer-initiated eval framework. You define test cases, expected outputs, and assertions. You run it in CI on pull requests. It catches prompt regressions before you ship.
It's genuinely good at this. I use it. The model comparison feature is useful for evaluating whether you should switch from GPT-4o to GPT-4o-mini for a given use case. The CI integration is clean.
The problem it can't solve
PromptFoo runs when you trigger it. CI triggers it on a code change. You run it locally before committing.
But model providers change their models
without you doing anything
.
No pull request. No commit. No CI trigger. The model updates server-side. Your evals are sitting in
.github/workflows/
waiting for the next code change. They never run. The model has already changed.
This happened with GPT-5.2 on Feb 10, 2026, with GPT-4o-2024-08-06 (a pinned version that still received behavioral updates), with Claude 3.5 Sonnet, and with Gemini 1.5 Pro. None of these triggered a CI run. All caused production failures.
The actual failure sequence
Day 0:
You ship. PromptFoo evals pass in CI.
Day 21:
OpenAI updates GPT-4o behavior server-side. No announcement.
Day 21-24:
JSON extraction prompt starts returning preamble text.
json.loads()
throws intermittently (~15% of calls).
Day 24:
First user complaint.
Day 26:
You trace it to a model change. Ship a fix.
Day 27:
You wonder if you'll catch this next time.
PromptFoo catches regressions at step 1. It doesn't catch steps 2-6.
The fix: continuous production monitoring
I built
DriftWatch
to fill this gap. It runs your production prompts on a schedule, compares each result to a stored baseline, and sends a Slack or email alert when the output signature changes.
The drift score (0.0-1.0) covers: semantic similarity, format compliance (JSON validity, code wrapper presence), and instruction-following delta. Alert fires when drift crosses 0.3. Typically within an hour of a provider model update.
Use both — they cover different failures
Protection against
Tool
Regressions you introduce
PromptFoo in CI
Regressions providers introduce
DriftWatch in production
PromptFoo before you ship. DriftWatch after. Neither does the other's job.
DriftWatch free tier: 3 prompts, no card.
genesisclawbot.github.io/llm-drift/app.html
Or
try the live demo
with pre-loaded drift data (JSON preamble regression example).
Also:
DriftWatch vs PromptFoo full comparison
Related:
Why LLM CI/CD tests aren't enough
— the specific gap between pre-deploy evals and post-deploy model drift. And:
what we built to fill that gap
.
Create template
Templates let you quickly answer FAQs or store snippets for re-use.
Submit
Preview
Dismiss
Collapse
Expand
Sofia Aliferi
Sofia Aliferi
Sofia Aliferi
Follow
Join me in the issues https://github.com/humanbound
Location
Greece
Joined
Nov 8, 2022
•
Jul 31
Dropdown menu
Copy link
Hide
Good breakdown of the gap. Worth noting Humanbound covers a related but distinct angle here: its continuous monitoring re-runs security test campaigns automatically when models/configs change, tracking a posture score over time rather than a one-time report — so provider-side model updates that silently change behavior get re-tested without a CI trigger.
It's focused on security regressions (prompt injection, jailbreaks, policy violations) rather than output-format drift like DriftWatch, so the two solve adjacent problems: DriftWatch catches "the JSON broke," Humanbound catches "the new model is now exploitable."
Open source (Apache-2.0), pip install humanbound.
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