---
title: 'Build vs buy: a guide for internal tools | Retool Blog'
id: build-vs-buy-a-guide-for-internal-tools-retool-blog
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:51.782245Z'
source: https://retool.com/blog/build-vs-buy-guide-for-internal-tools
source_domain: retool.com
fetched_at: '2026-08-02T03:12:51.777245Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 14.0
---

Build vs buy: a guide for internal tools | Retool Blog
Skip to main content
//
Retool Blog
Sign up for Retool
B
B
B
u
u
u
i
i
i
l
l
l
d
d
d
&
&
&
L
L
L
e
e
e
a
a
a
r
r
r
n
n
n
246
R
R
R
e
e
e
a
a
a
d
d
d
s
s
s
&
&
&
R
R
R
e
e
e
p
p
p
o
o
o
r
r
r
t
t
t
s
s
s
47
S
S
S
h
h
h
o
o
o
p
p
p
T
T
T
a
a
a
l
l
l
k
k
k
20
R
R
R
e
e
e
l
l
l
e
e
e
a
a
a
s
s
s
e
e
e
s
s
s
45
N
N
N
e
e
e
w
w
w
s
s
s
r
r
r
o
o
o
o
o
o
m
m
m
20
Build vs buy: a guide for internal tools
Mads Clark
Technical PMM
Jun 5, 2025
Copy Link
Table of contents
01
Challenges of building internal tools
02
Underestimating the time and complexity of building
03
Ultimate flexibility leads to decision fatigue
04
Vibe-coded apps: fun to build, painful to run
05
The hidden devops costs of building internal tools
06
Dealing with disconnect
07
Internal tools fail without long-term maintenance plans
08
Underestimating how your custom solution will need to scale, evolve, and adapt
09
Common security risks with homebuilt business apps
10
Authentication and authorization
11
Supply chain risks
12
Why buying internal solutions can backfire
13
Poor interoperability breaks workstreams
14
Authentication overhead
15
Hitting the ceiling on usability
16
Vendor risks: stability, reliability, flexibility
17
Happy medium: building on open source
18
Challenges of building on open source
19
Integrations and maintenance
20
Support
21
When it makes sense to build internal tools
22
Low ongoing maintenance and updates
23
Building lets you differentiate
24
You want to encourage innovation
25
You can accelerate building with a platform
26
When it makes sense to buy internal tools
27
The purchase doesn’t prevent you from building later
28
When the build vs. buy decision isn’t clear-cut
29
What stage/scale are you at?
30
Why  does your team want to build?
31
How would you solve this problem if you couldn’t build OR buy?
32
Is there a solution that’s good enough for now?
33
What are your time and budget constraints?
34
Do you have the internal resources to build?
35
What is the cost of waiting for a custom-built solution?
36
Proof of concept
37
7Cs framework
38
When you need the best of  all  worlds
39
Leverage AI for internal tools without the risks or overhead
40
There is no ceiling on usability
41
Build better internal software with the app layer for AI
When it comes to your internal software, we’ve moved beyond just building versus buying your solution, and everyone has a take on what to do.
In the era of
vibe coding
and
global economic uncertainty
, leaders are being tasked with leveraging AI for efficiency gains in multiple ways. Whether integrating AI agents into workflows or offloading the heavy lifting of building to generative AI, it’s now also a question of
build vs buy vs build with AI
.
Making the right choice is so context-dependent that any guide (including this one) claiming to help will only get you so far. Our aim is to show you
how to evaluate
a build vs buy decision for critical business infrastructure like agents. This guide will equip you with the right considerations and questions to ask so you can understand the tradeoffs you might be making (now and later) and choose a solution that solves your current challenges—without burning bridges you might need as you scale.
Engineering leaders tend to be clear on the positives of building and buying solutions, but the pitfalls and gotchas can be thornier. We’ll start by exploring the ways that building, buying, or building with open source or AI can backfire. We’ll look at scenarios where there’s a clear advantage to building or buying. And we’ll provide considerations and tactics to help you uncover the right path when there isn’t an obvious choice.
Challenges of building internal tools
“With any creative activity comes dreary hours of tedious, painstaking labor; and programming is no exception.”
— Fred Brooks,
The Mythical Man-Month
Underestimating the time and complexity of building
Builders like to build. Engineers want to engineer! When faced with a new challenge, it’s tempting to think of the project as an opportunity to explore new technology or to do things right. You may find yourself thinking, “this could be the next big thing!” when in reality, you
just need to solve your problem
, fast.
Even the most seasoned builder can be overconfident when estimating how long it will take to build something. You can get ahead of known unknowns, bake in breathing room, and still run into additional requirements that don’t surface until later in the process. This becomes especially likely with internal tools, which often don’t have dedicated product owners—and in turn, might not come with complete specs, or a thorough understanding of how it will integrate with the most impactful tools in your stack, like your preferred LLMs, databases, and more.
Ultimate flexibility leads to decision fatigue
Companies often opt to build from scratch when they want something custom. But unless you have a very niche use case, that freedom to do literally
anything
can actually impose a lot of low-level choices that can lead to overwhelm and decision fatigue (“Which
React table component
should we use?
Which date picker
?”) without offering meaningful business differentiation. Having some constraints—whether or self-imposed or downstream of your stack and tooling choices—can actually speed things up.
Kenneth Molnar, a DevOps Engineer, and Kee Han Ooi, a Software Engineer, decided to scope out replacing
Solera Health
’s internal tooling with React apps. “But we just didn’t need the same level of control and polish on our internal tools as the tools we were building for our providers—not to mention, we simply didn’t have the time to build React tools for everything.”
Vibe-coded apps: fun to build, painful to run
If you do decide to forge ahead with a custom solution, all sorts of day-two problems can emerge once that solution exists. This is especially true for vibe-coded apps, which are notorious for
adding tech debt and including insecure code
that’s vulnerable to risks like supply chain, injection, cross-site scripting attacks, and
secret leakage
.
The hidden devops costs of building internal tools
It’s straightforward enough to get a version of whatever you’re building working on one person’s computer. What next?
Where is the app going to live? On one of your servers? Do you need to get the DevOps team involved to give you an Amazon server to put it on? How will you host it? Who’s going to take responsibility for updating libraries, or maintaining test cases?
We’ve already seen that (some) “
devs don’t want to do ops
.”
“I hate DevOps. Mainly because I don’t want to do it. I liked it better when there was a dedicated infrastructure team instead of pushing it down to developers and giving it a new name.”
— irrational,
Hacker News
This sentiment is usually not much more favorable for internal or agentic tools, which tend to get even less fanfare for ongoing ops and maintenance.
Dealing with disconnect
Devs often use internal projects as an opportunity to learn a new programming language or explore a new framework, as it’s outside their daily scope of work. But if the person isn’t at the company anymore (or even takes a vacation) someone else will have to learn how to manage it.
Internal tools fail without long-term maintenance plans
The legacy code problem can happen with internal tools, too. It’s not uncommon for an internal solution to be built, then some years later someone asks, “How do we change this?” and the person who built it has left, the API key is gone … or no one knows what account was used. And with AI codegen tools, the sheer volume of code you now have is orders of magnitude larger than before.
Ken Liu, Engineering Director at Cockroach Labs
, describes the most frustrating part of building and maintaining internal tools:
“… [these internal tools were built by a lot of different people and aren’t necessarily at operational maturity. They work well, but sometimes things will die and then without sufficient logging or a normal process of updating libraries or even consistent software design behind some of these tools, it makes it difficult to work on them.”
One way to get ahead of internal tool maintenance woes is to consider whether the potential homebuilt solution aligns with your core suite of products. If it’s built differently than your other solutions and services, deploying may require a separate process or infrastructure depending on how it’s structured, which means it’s likely that other team members will lack the context and ability to maintain it—a recipe for internal app rot.
Underestimating how your custom solution will need to scale, evolve, and adapt
“If we jumped to building dashboards from scratch with React, they’d be tailored to the first intended use case. The reality is: our apps would likely change every week”
— Cornelius Schramm,
FINN
Another common pitfall is building for the first known use case, without factoring in future development, reusability, or extensibility. You do have to start somewhere! But in the (good) case that your internal users actually adopt what you’ve built, you’ll start to get feedback and feature requests—and fielding them can quickly snowball into a full-time job.
Building AI
agents and agentic systems
in particular presents a lot of unknown unknowns. Building one off agents to solve problems isn’t the most reusable or scalable way to build. The technology is so new, and it’s challenging to predict what other features and scale requirements will emerge over time—especially if your agents aren’t connected to your data and other core parts of the stack.
A product engineer at incident.io
decided to build an internal expenses platform as a side project
:
“... but then the feature requests started to roll in. We added an email address you could forward receipts to. The finance team wanted to tweak the reporting so they could spend less time sending out the reimbursements."
Then they wanted to add an approvals step, where expenses needed sign-off from a manager. That means we needed to track who everyone’s manager is, which would change quite frequently since we were growing fast.
… the more our little expense app got used the more people started finding annoying little bugs which weren’t nearly as fun to fix as building new things.”
This example is a cautionary tale for the failure mode where your engineers end up unexpectedly becoming product owners for the solution they’ve built, spending outsized effort on after-the-fact asks from internal customers and practically needing a roadmap for the tool. The thing they built was
supposed
to enable productivity. Now, it’s a burden.
Common security risks with homebuilt business apps
Unfortunately, internal tools don’t always get the same security posture that companies give their core product or service. Maybe some default password gets set and makes it vulnerable, maybe there’s an underlying vulnerability and nobody thinks to patch it routinely. These scenarios make your internal tooling much easier to exploit. No bueno.
Authentication and authorization
When your team is building for employees—a set of trusted users—it can be easy to overlook authentication and authorization requirements. When it’s just a prototype on someone’s computer, people don’t tend to think about managing logins. But by the time you have the app hosted on a server, you may have to retrofit access management, authorization, and tracking, because these weren’t part of the original spec. And as you scale, you may even need to meet SOC II requirements and implement SSO.
The trick is that you need the tool to be accessible to be useful—but not so wide open it’s vulnerable.
Supply chain risks
Anyone who was present for the
Log4Shell vulnerability
will be familiar with the scramble to identify at-risk code. Every package you install or library you pull into your codebase is a dependency. They can all present their own security issues and vulnerabilities.
If you build from scratch, you’re on the hook for keeping an eye on your dependencies—figuring out when they need to be updated and ensuring patches don’t conflict with other updates that need to be made. Complicating matters is that there’s usually no formal release cycle for an internal tool, so security patches may be ad hoc and not prioritized.
All of
the same security risks and more apply to AI-generated code
, with extra caution required to vet for vulnerabilities and hardcoded secrets.
Why buying internal solutions can backfire
Building a custom solution potentially introduces very real complexity, toil, and future challenges. Buying something off the shelf can seem especially appealing. . But buying comes with its own set of challenges. If every team is bringing on their own tools to address every need, you can end up with toolchain sprawl that drives up software spend
and
causes information silos due to a lack of interoperability.
Poor interoperability breaks workstreams
Diverse and robust integrations are table stakes for any enterprise-grade SaaS product Still, it’s impossible for every tool in the stack to know about and account for every other product you’re using. New AI tools are emerging faster than integration teams can address all the resulting compatibility challenges. In the absence of true interoperability, people turn to copy-pasting data from one source to another. Not only is this approach primed for human error, but you then have multiple sources of truth to maintain.
Authentication overhead
Credentials and authentication can quickly become unwieldy across multiple tools, making it hard to standardize on best practices.
Hitting the ceiling on usability
Most SaaS purchases are well-intended, but they don’t always stand the test of time. You may only discover later that the product doesn’t offer everything you need, sometimes only
after
you’ve already invested in integrations and training.
Depending on the type of solution you bought, you may or may not be able to add functionality yourself once your processes scale up. Some products are relatively easy to customize, but if the product abstracts the backend and there’s no way to write your own code or business logic, you may have painted yourself into a corner. This can lead to multiple vendors being required for different departments, as each product caters to a single, narrow use case.
Vendor risks: stability, reliability, flexibility
Whether you hit a ceiling or not, you’re still at the whims of another company’s roadmap, quality bar, and stability. Your vetting and procurement process should take into account how established or stable the vendor’s business is, how reliable their products are, and whether their product is flexible enough to scale with you (rather than the other way around).
If you’re in the market for an AI solution, the explosion in AI startups over the past few years has created a lot of off-the-shelf solutions from which to choose, but with the dust settling, longevity is not a given. The Pragmatic Engineer reported back in 2024 that
AI startups were already beginning to struggle with gaining traction or fundraising
, and as of May 2025 former unicorn
Builder.ai filed for bankruptcy
. While some AI point solutions will still be here when the dust settles, this volatility will continue for quite some time.
Happy medium: building on open source
Standing on the shoulders of giants offers a way to build without doing it from scratch. Whether that’s in the form of an open-source tool or component library, these shortcuts can save you a lot of time upfront.
But it’s important to go in with eyes wide open to the potential gotchas later.
Challenges of building on open source
Open-source component libraries can offer a middle ground that makes it faster to go from zero to one without the commitment of buying. If the project shuts down or goes stale, you can fork. There are some footguns to watch out for, though.
Integrations and maintenance
You do still have to integrate these libraries into your codebase, read the documentation, and figure out how they work and fit with the rest of your tooling.
Support
Depending on how mission critical the project is to your company’s performance, the availability of reliable support can be a sticking point. While on occasion an open-source tool offers access to paid support, most of the time you’re reliant on the community and maintainers to address bugs, and there may not be any SLAs on which to bank your expectations.
On the other hand, support is also open source, so you can sometimes find GitHub issues with your problems and see if it’s been solved or someone is working on a fix. (If you’re really dependent on the open-source project you can consider investing in it by allocating engineering resources to contributing features, improvements, and fixes.)
Proprietary support is not typically as transparent, but can be faster. You won’t always have visibility into what the company is doing to address your problem, but a company is likely to have more in-house expertise than hobbyist maintainers.
If you’re considering going the open-source route, it’s wise to vet the project as carefully as you would a vendor. What is the project’s likely longevity? How active are its maintainers? How long does it take for vulnerabilities to be patched or bugs to be fixed?
Asking these questions at the outset will help you avoid painting your team into a corner later.
When it makes sense to build internal tools
If you need a small utility (agentic or otherwise) that’s quick to stand up and will have an immediate impact, it’s easier to make a business case for building AI. The procurement process for a paid solution probably won’t be worth it—buying can
be slower because of the time required to lock down a deal and onboard your team.
Low ongoing maintenance and updates
If the app or agent you need to build doesn’t require much ongoing maintenance and updating (eliminating some of the headaches we explored in [When building backfires]), the maintenance burden
may
be negligible. Be realistic about ongoing ownership costs though: these are usually gotchas (famously hard to predict). It could be worth taking the time to think through what that long-term maintenance could entail in a few different scenarios.
Building lets you differentiate
There are times when the solution you need is part of your company’s core competency. In this case you usually need control over the direction of the solution, and building something custom enables a competitive advantage.
Healthcare staffing company
Trusted Health
opted to build a custom payroll system for competitive advantage:
“The decision to build our payroll system stemmed from the desire to create a unique and unmatched experience... The intricate structure of this vision led us to develop our custom payroll system. Offering a custom, competitive experience to all nurses made Trusted Health stand out, and the ‘build’ route hence was naturally chosen.”
You want to encourage innovation
If your company has the resources and a culture of building, experimenting, and innovation (such as
Spotify
—or
Yahoo
at one time), opting to build will be a natural choice.
There are examples of companies that ended up releasing a revenue-generating product that they built to meet an internal need:
JIRA started out as an internal bug-tracking tool
at Atlassian
Amazon
developed a core competency around infrastructure services for its own internal needs before launching Amazon Elastic Compute Cloud
(AWS’ predecessor)
Amplitude emerged from the internal analytics platform developed by a voice recognition software company
It’s rare however for an internal tool to have potential as a new offering or revenue generator—it’s more likely for this to be a happy accident than something you can plan on.
You can accelerate building with a platform
You can make building go faster by developing a platform to accelerate from-scratch builds, so developers don’t get waylaid setting up email or login mechanisms before they even get started on building the tool itself.
Ideally, developers won’t have to start from zero every time they need access to data, to provision a server for storage, or send internal emails, and so on. This can be a huge differentiator and unblock for scaling custom builds.
When it makes sense to buy internal tools
Buying may be a better option to help you move faster if:
Your needs aren’t extremely bespoke.
Your requirements are unlikely to change or expand meaningfully.
What you need to build isn’t tied to revenue generation (or won’t give you a competitive advantage).
With the proliferation of SaaS and off-the-shelf AI tools, there is likely to be something you can use that solves your problem, at least in the short term—though it’s worth being mindful of just piling up disconnected SaaS tools.
When asked his perspective on building internal tools from scratch, Matthieu Vegreville,
Greenly
Co-founder and COO said, “It’s about what your focus is. What’s your core expertise? To build [your internal tools from scratch] is a mistake to me, just because it’s probably not the core of your business.”
The purchase doesn’t prevent you from building later
“‘Buy-then-build’ can be a great strategy. Often the ‘then-build’ never happens, but going into a decision with the mindset readiness for ‘then-build’, you can learn from existing products, hit their limits, and understand what is the custom version of it you’ll need in your context. Recent examples are on smaller scale, though - using a library that speeds work up early, hitting its limits, and replacing or extending with DIY that does less things but goes deeper for my use case.”
—nodoodles on
Hacker News
You can make an initial decision to buy that doesn’t preclude building
eventually
. Or you can opt to “buy” a development platform that allows you to build custom tools but minimizes the busy work and heavy lift.
When the build vs. buy decision isn’t clear-cut
If you don’t feel any closer to a choice, let’s explore some questions to ask yourself and tactics to help you uncover the right solution.
What stage/scale are you at?
For startups, speed is often the priority, with factors like maintainability and interoperability only becoming relevant down the line. (You probably have fewer tools and services that the tool needs to interact with.)
At scaleups and large organizations, long-term maintainability is more likely to be top of mind. The solutions you build usually have larger scope and could be around longer. Large orgs also have more inherent complexity—suddenly needing SSO, more stringent compliance requirements, or simply more people who may need to access the tool.
We had an internal password manager at one company that a small team built for fun once. You could share the password with another team or even a single person. There was also an audit log, and when someone left, they just looked in the audit log and reset those passwords that person ever looked at.
But someone eventually created a chrome extension that would fill in the passwords for you...
I think the total dev time was somewhere in 4–6 person months. It probably would have been cheaper just to buy a 1password subscription if we had been a small company, because I’m pretty sure a 5k seat subscription for the business would have been waaay more money than 6 months worth of salary, one-time cost. —withinboredom on
Hacker News
Why  does your team want to build?
Will the thing you build solve a recurring problem? Will it genuinely give you an opportunity to transform a broken process or solve a business need? Or is it the shiny new tool effect or chasing the
builder’s high
? If it’s hard to articulate the value of building yourself, it might be a want and not a need.
How would you solve this problem if you couldn’t build OR buy?
Can you leverage pre-assembled components or APIs? If you don’t need a full-blown app with a frontend or GUI, can you use a solution to automate things?
You can use
Retool Workflows
to automate business processes like connecting support tickets in Jira to your CRM, notifying customers when orders are shipped, or aggregating data across multiple sources.
Is there a solution that’s good enough for now?
It’s less important that you make the long-term right decision now. What matters more is that an interim solution offers enough flexibility to evolve later and you are ready to change course when necessary. Spreadsheets can be a stopgap for recording and analyzing data, but growing dependency on these can make it impossible to keep up with demand as you scale. An off-the-shelf AI solution or wrapper might meet your needs in the short term, but lack options for customizing workflows and limit you to a specific use case.
Equipmentshare
’s dependency on spreadsheets made it difficult for their data management processes to scale quickly enough to meet the business’ growing data demands. Chief Data Officer Mark Wopata’s team piloted Retool to create an application to manage data about EquipmentShare’s store locations.
The app needed to be able to interface with EquipmentShare’s data warehouse and API. The app also needed to allow text-responsive drop-down sections that would enable code-free data validation. With Retool, Mark’s team of analysts were able to build this capability quickly and efficiently.
There are two factors to be aware of here:
Don’t fall prey to the sunk cost fallacy. Whatever decision you make, be ready to re-evaluate and course correct as your needs change.
Consider whether building or buying now enables you to change course later, instead of locking you in to something you’ve outgrown.
“The biggest issue tends to be when people double down on continuing down the wrong path when a better alternative is obvious. The thing you bought or built is often the wrong decision three-to-five years down the road.”
—master_crab on
Hacker News
Looking for a solution that was more flexible than scrappy spreadsheets and less resource-intensive than a full-fledged React app,
Greenly
used
Retool Embed
to integrate a series of Retool apps into an existing web portal built with React. A common backend layer underpins these apps, which are individually customized to meet the needs of various customer segments.
For companies coming from a legacy system, Greenly Co-founder and COO Matthieu Vegreville recommends having a wrapper compatible with Retool Embed. Then, it’s seamless to build components and swap them in and out of the wrapper, and allows the transition to Retool to be as gradual as a company wants. Instead of having to tear everything apart all at once, Retool Embed enables companies to augment legacy tools, one dashboard or app at a time.
What are your time and budget constraints?
Estimating the engineering hours required to build something is always going to be a bit “back of the napkin” math. But again, you have to start somewhere to
model out the cost
of developing a comparative solution that meets your bare minimum needs vs. a paid solution.
How many people would you need, and for how long? Factor in infrastructure and maintenance costs beyond initial development—the cost of owning something long-term is often overlooked.
How much can you commit, and for how long? It’s harsh, but some companies are phrasing it as a
vendor vs headcount decision
. Even if you’re not hiring a net-new employee, employment costs tend to be harder and more complex to reduce than vendor costs.
It’s tempting to think of building with AI as the answer to reducing labor costs (and that is the strong message being sent by
Shopify CEO Tobi Lütke’s memo
). Generative AI can get your team from zero to one faster, but it can also simply trade time spent upfront on building for time on reviewing, refactoring, fixing, and maintaining. If senior leadership expects faster shipping with AI-generated code,
teams may skip critical testing
to meet those demands, leading to instability and outages down the road.
Do you have the internal resources to build?
The coffee that you make at home isn’t free. Similarly, the engineers you already have on payroll come with costs:
Salary
Total cost of employment (including benefits, stock, etc.)
Opportunity cost of having your team working on something that’s not customer facing
Are there levers you can pull to lower that cost? Tooling, a framework or platform could help your engineers work faster, while equipping your team with the right AI tools can expedite things too.
What is the cost of waiting for a custom-built solution?
If your support team is hamstrung or your salespeople can’t self-serve, it’s hard to quantify the cost of waiting 6+ months for a solution, but it does impact your bottom line.
Pre-built software costs are more obvious, both initially and ongoing. If budget is a primary concern, going with the known costs of a vendor may be more appealing, as long as you are prepared for the old bait-and-switch (changing their pricing model, for example).
Proof of concept
Whether you’re trying to choose whether to build or buy or which solution to buy, it’s all based on opinions and speculation until you actually kick the tires. So it’s worth conducting a bake-off, pitting some solutions against each other or against what you’d attempt internally.
Put some R&D budget towards exploring building or buying and time-box your experiment. This lets you find out what you don’t know when you’re working in hypotheticals. Prototyping some options can reveal some complexities and give you a chance to test a tool’s support flow.
You may be able to partner with a vendor on a proof of concept: for potential Retool customers we can usually stand up an app that’s close to what they need within a week or two.
7Cs framework
Who doesn’t love a good framework for decision making? Sue Nallapeta offers up her
7Cs framework
, inspired by her experience in tech leadership at Trusted Health, Apartment List, and Zoosk.
Core Capability
: Would you be building something that forms part of your company’s product or service offering?
Cost
: What are the costs beyond people time, such as maintenance and hosting?
Complexity
: Do existing solutions fit your needs or are your requirements bespoke?
Competence
: Do you have the right people within your company to build it, and can you afford the opportunity cost and time to market?
Cohesion
: How will the tool you’re building or buying integrate into the broader ecosystem of your tech stack?
Competitive Advantage
: Can building or buying help you differentiate your offering?
Culture
: Does your company culture lean towards building, creation, and innovation, or on shipping fast?
When you need the best of  all  worlds
If by this stage things are still shaking out to be neither build nor buy definitively—we get it. It’s a false dichotomy. As we saw at the beginning, many businesses have found that it works for them to use some combination of the two, or evolve from one to the other as the business grows and needs change.
Snowflake
needed a way to automate their manual access review process and unify an experience currently split across dozens of apps. To build from scratch would be time consuming—and required a team of developers. To buy an off-the-shelf solution would be too rigid and costly.
“Retool provided the platform that allowed teams like mine—not formal software engineers—to build apps quickly and partner with other business-centric teams.”
Cameron Tekiyeh and his Security Analytics team wouldn’t be bogged down on the fundamental building blocks that are already included out-of-the-box.
Code is a really good solution for when you need business logic to transform data coming in from your backend or if you need to write a custom component. But for most business applications, it’s not worth building every single thing from scratch—any perks you get are just too low-level to be advantageous.
Even if you shortcut writing your own code with the help of
an AI coding assistant
, generative AI tends to be verbose, defaulting to writing
more
code rather than refactoring or reusing—creating tech debt that undermines any efficiency gained from vibe coding.
Snowflake chose to buy a platform to accelerate building, rather than an off-the-shelf solution or developing from scratch. If you, like Snowflake, want that sweet spot in between, Retool enables you to accelerate building, with full flexibility when you need to customize.
Security and governance
are baked in without getting in the way—maintaining flexibility and customizability for engineers.
Leverage AI for internal tools without the risks or overhead
Using AI to write code isn’t the only way to leverage it for efficiency gains that drive real business results. Instead of just “
giving in to the vibes
” and accepting the risks that go with it, you can shortcut the building phase by taking advantage of ready-made components that are already tried and tested. Then, with Retool as your app layer for AI, you can still integrate AI into your internal tooling to automate workflows and repetitive manual tasks, but with guardrails, clear architecture boundaries, and version control.
ClickUp
, a leading productivity and project management platform, wanted to invest in AI solutions to automate and accelerate its go-to-market (GTM) processes. The team turned to Retool as an app layer for AI, with their engineers building custom tools that connect their data with AI models.
“Retool bridges the gap between our processes and AI. You can structure your outputs, automate the data flow into your prompts, and put an elegant interface on it,” says Borys Aptekar, Product Manager of GTM AI.
The apps and workflows they’ve built have made the GTM organization more efficient without giving up control over ClickUp’s data.
There is no ceiling on usability
Abstract away as much as you want, but you won’t get stuck when you hit the limit—if at any point you need something that’s not in Retool, there’s always the escape hatch to write the code yourself.
Build better internal software with the app layer for AI
The build vs. buy decision isn’t binary when it comes to internal tools. It’s about finding the right fit for your context. Building gives you control but adds maintenance overhead and security risks. Buying accelerates deployment but can lead to vendor lock-in and functionality limits.
The key questions: What stage is your company at? Do you have resources to maintain what you build? Will this differentiate your business? Most importantly, does your choice allow you to evolve later?
For many teams, the answer is a middle ground—platforms that accelerate building or AI-enabled solutions that provide flexibility without the overhead. Whether you build, buy, or blend approaches, choose solutions that solve today’s problem without locking you into tomorrow’s constraints.
Ready to explore the middle path?
Start building with Retool
and see how quickly you can create custom internal tools without the maintenance overhead—or
talk to our team
about a proof of concept tailored to your use case.
Special thanks to Rebecca Dodd for her contributions to this piece.
light
Reader
Mads Clark
Technical PMM
Jun 5, 2025
Copy Link
Related Articles
How Retool solves the internal agent problem
Kent Walters
A guide to agentic AI workflows in 2025
Kent Walters
Collections
Build & Learn
Build with AI
Build for scale
Build UIs
Build foundations
Build with Retool
Reads & Reports
Shop Talk
Releases
Newsroom
Subscribe to our newsletter
Copied