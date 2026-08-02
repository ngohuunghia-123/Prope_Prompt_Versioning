---
title: Why Shorter Prompts Can Make Coding Agents Worse
id: why-shorter-prompts-can-make-coding-agents-worse
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:37.887713Z'
source: https://www.the-main-thread.com/p/token-minimization-context-budget
source_domain: www.the-main-thread.com
fetched_at: '2026-08-02T03:12:37.879718Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 16.0
---

Why Shorter Prompts Can Make Coding Agents Worse
Subscribe
Sign in
Why Shorter Prompts Can Make Coding Agents Worse
A practical guide to context windows, tool sprawl, and why cutting filler is not the same as cutting meaning.
Markus Eisele
Jun 29, 2026
2
1
Share
The moment an AI coding session gets expensive, someone opens the token counter.
Then the cutting starts. System prompt. Tool descriptions. Old examples. Comments. Variable names in injected snippets. Sometimes even the task brief gets squeezed until it reads like somebody was charged by the character.
I understand the reflex. Context is not free. In
The GitHub MCP Server Can Burn 17k Tokens Before You Ask a Real Question
, I measured one obvious leak: wide tool catalogs. A large MCP surface can burn a noticeable part of the window before the agent reads a single file. The second leak is payload. Raw diffs, full documents, and replayed transcripts can eat the same budget a minute later.
Those two cuts help a lot. Narrow the tool surface. Narrow the payload.
The trouble starts after that. Teams keep cutting, but the next cuts land on the wrong material.
The Expensive Mistake Starts After the Useful Cuts
Once the broad tool catalog is gone and the raw payload is under control, what remains is usually the part that carries meaning: the task description, the few-shot examples, the names in the code, the explanation of local rules, the one weird business constraint nobody would guess from reading the repository.
That is the part people start compressing.
A recent paper,
Beyond Human-Readable: Rethinking Software Engineering Conventions for the Agentic Development Era
, gives this mistake a methodology. The paper argues for
semantic density
, which means how much useful meaning each token carries. In its log-format experiment, aggressive compression reduced input tokens by 17 percent and still increased total session cost by 67 percent. The model had less text to read and more work to do.
That result makes sense to me. If you replace clear names with abbreviations, strip context until it becomes ambiguous, or turn a precise task brief into terse prompt folklore, the work does not disappear. The model still has to recover the missing meaning. Now it pays for that recovery with extra reasoning, extra retries, and extra correction loops.
OpenAI’s reasoning guide
says this pretty clear: reasoning tokens still use context-window space and are billed as output. So when a compressed prompt forces the model to reconstruct what you used to state clearly, the bill moved. It did not shrink.
I think of that as the compression tax. You saved on the visible input side and paid the difference somewhere harder to see.
This Is the Same Accounting Bug Again
Thiskeeps coming back to the same pattern over and over. We measure the easy thing and ignore the expensive thing.
In
Stop Measuring AI by How Much You Use It
, I argued that token burn is heat. It is measurable activity. It is not proof of useful work. In
AI Coding Break-Even: Cheap Tokens, Expensive Software
, I made the same point at delivery scale: the real cost shows up in review, repair, security, rollout, and the hours after the model claims success. In
The Spec Trap
, the cheap-looking move was underspecifying the job and pushing the ambiguity downstream.
Token minimization makes the same mistake at prompt scale.
A smaller prompt can be cheaper. A smaller ambiguous prompt often is not. It can produce longer output, more retries, worse tool choices, and more human cleanup. The dashboard still shows fewer input tokens, which is nice if your goal is to win an argument in a screenshot. The real system pays elsewhere.
Vendors Already Know This
One reason I do not take “just make the prompt shorter” very seriously is that the platform vendors keep shipping features that solve a different problem.
OpenAI’s prompt caching guide
tells you to keep repeated content in a stable prefix so cached prefixes can cut cost and latency.
Gemini’s context caching docs
split the same idea into implicit and explicit caching.
Anthropic’s guide to managing tool context
says large toolsets should use tool search so the full catalog stays out of the window until the model asks for it.
Anthropic’s context editing docs
says: context is finite, returns diminish, and irrelevant content degrades model focus.
Even if they are all burning through a lot of experimentation money right now, the fact that they all have this as tool category is a solid hint that this did not happen by accident.
Repeated context should be cached. Large tool catalogs should be loaded late. Stale results should be trimmed. Old conversation debris should stop competing with the current task. The pattern is clear enough: cut repetition, cut stale context, cut broad catalogs, and keep the remaining signal readable.
The Target Is Semantic Density
Aim for the densest prompt you can build without cutting away meaning.
That changes the operating rule.
A wide tool catalog is low density because most of the tools are irrelevant on this turn. A full raw diff is low density when the agent only needs the touched files that affect one behavior. A replayed transcript is low density when three earlier summaries and two failed attempts are still sitting in the window long after they stopped helping.
Clear task instructions, good names, and the local rule that explains a weird edge case all earn their place. Those tokens pull their weight.
The point is simple: remove noise first. Preserve signal. If you keep cutting after that, you start deleting the map and asking the model to redraw it from memory.
The split is easier to see when you draw the window as layers instead of one big token number.
Two cuts are selection work. The last cut is where teams start deleting meaning instead of noise.
Caveman Is a Useful Counterexample
This is also why
juliusbrussee/caveman
is interesting and not a contradiction.
The project is not mainly trying to compress the part I want to protect. It is mostly compressing the agent’s speaking style. The README claims about 65 percent average output reduction across ten prompts, and it is explicit about the boundary: output gets smaller, reasoning tokens do not. That lines up with the difference this article is trying to draw.
If a model wastes tokens on filler, politeness, repeated restatement, and long glue text, shorter output can help both budget and quality. The answer gets faster to read. Less narration means fewer places for the important instructions to hide. That is a different move from stripping context out of the task brief until the model has to guess what you meant.
caveman
also pushes on the input side in narrower ways. The repo includes
caveman-compress
for memory files and a middleware layer that shrinks MCP tool descriptions. That can be a good trade if the compression preserves the load-bearing content. The project README says code, URLs, paths, and error strings stay exact. That is the only version of compression I think makes sense: cut the wrapper, keep the meaning.
So I would use
caveman
as a qualifier. Compression helps when it removes low-value phrasing around stable meaning. Compression hurts when it removes the meaning itself. Same word, different target, very different outcome.
What I Would Do Instead
If I had to reduce this to a small operating rule, it would look like this:
Cache what repeats.
Stable instructions, examples, and other shared prefixes should not be resent at full price on every turn.
Retrieve narrow evidence.
Give the model the sections, files, or snippets that answer the current question. Keep the archive available, not injected by default.
Load tools on demand and trim old tool chatter.
Large tool menus and stale tool results are both taxes.
Keep the remaining context clear.
Write the task brief plainly. Keep real names. State the local constraints in full sentences. Ask for a bounded artifact when a decision object or structured result is enough.
That is token discipline.
Clear Text Still Wins
Some teams still get stuck. They see a long prompt and assume the length itself is the problem. Sometimes it is. Often the real problem is that the prompt is carrying the wrong material. I am not saying that we should resurface the prompt engineering hype. But also not forget about what good prompts look like.
A clear system prompt with stable rules can be cached. A clear task brief can prevent three correction loops. A clear tool description can stop a bad call before it happens. A clear variable or field name can save the model from inventing a meaning that was never there.
One line to remember:
Cut noise hard. Keep meaning intact.
That is a better default than “make the prompt shorter” because it matches how the bill really moves through an agent system. The catalog tax is real. The payload tax is real. The compression tax is real too, and it is the one teams keep charging themselves.
The model is rarely confused because you used full words. It gets lost when the window is full of stale junk and the remaining signal arrives half-compressed. That is a context problem. It needs selection, structure, and a little less obsession with the screenshot-friendly part of the meter.
Subscribe
2
1
Share
Discussion about this post
Comments
Restacks
Siddique Ahmad
Jun 30
Liked by Markus Eisele
caveman really helped on tokens, yesterday I experimented claude session lasted more than before
Reply
Share
Top
Latest
Discussions
No posts
Ready for more?
Subscribe
© 2026 Markus Eisele
·
Privacy
∙
Terms
∙
Collection notice
Start your Substack
Get the app
Substack
is the home for great culture
This site requires JavaScript to run correctly. Please
turn on JavaScript
or unblock scripts