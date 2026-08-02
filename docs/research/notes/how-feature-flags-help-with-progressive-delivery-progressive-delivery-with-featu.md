---
title: 'How Feature Flags Help With Progressive Delivery Progressive delivery with
  feature flags: getting started | Unleash'
id: how-feature-flags-help-with-progressive-delivery-progressive-delivery-with-featu
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:52.219232Z'
source: https://www.getunleash.io/blog/progressive-delivery-with-feature-flags
source_domain: www.getunleash.io
fetched_at: '2026-08-02T03:11:52.206826Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 12.0
---

How Feature Flags Help With Progressive Delivery Progressive delivery with feature flags: getting started | Unleash
Meet Unleash at one of the events we're attending this year
➩ See where we'll be
Watch "Implementing a Kill Switch for AI"
Events
Join the Unleash team to learn how to integrate runtime control in your AI strategy.
Watch the recording
How Feature Flags Help With Progressive Delivery
Mateusz Kwaśniewski
Sr. Full Stack Developer
July 22, 2024
In the
realm of Continuous Delivery (CD)
, where the objective is to ensure that software is always in a deployable state, there is still significant value in not exposing all users to new capabilities immediately.
Progressive Delivery
leverages this principle by gradually rolling out changes to a subset of users, testing in production, gathering feedback, and then expanding the release based on the results.
TL;DR
Progressive delivery reduces software release risk by combining progressive deployment and release.
Gradual rollouts allow live testing with limited users before full-scale release.
Progressive delivery improves user experience by validating changes and reducing large-scale failures.
Canary releases, blue-green deployments, and feature flagging are three core progressive delivery methods.
Unleash enables progressive delivery through advanced feature flag management and granular rollout strategies.
Read our FeatureOps Whitepaper
Get your free copy and learn how to connect engineering performance to business outcomes for fun and profit.
Download now
What is Progressive Delivery?
Combining both progressive deployment and progressive release, we achieve
Progressive Delivery
—our preferred way to deliver software to customers confidently and iteratively, whether it’s a one-line bug fix or a complex new feature. This ensures that our changes are not only technically sound, but also solve problems in a meaningful way for our users.
To sum this up with an equation:
Progressive Delivery = Progressive Deployment + Progressive Release
Progressive Deployment vs Progressive Delivery
Progressive deployment involves deploying a new version of software to a small percentage of users initially. This approach helps reduce the risk of introducing bugs or issues for all users when rolling out a new version of our application. One common technique used for this purpose is
canary deployment
. Various technologies support canary deployments. For instance, at Unleash, we use a custom-built Kubernetes operator to manage deployment channels.
At Unleash, we categorize our customers into groups such as demo users, early Pro plan users, established Pro plan users, and Enterprise plan users, deploying the new version to each group at a different pace. With each deployment, every customer in a channel gets all new code created since the last deployment. Charity Majors likens deployment to a
chainsaw
, emphasizing its broad nature, compared to a scalpel-like feature flag explored below.
After each deployment, we can observe application stability and the impact of changes, such as one-liner bug fixes or trivial code changes (e.g. automated refactorings). For very simple changes, deployment and release can be the same thing. However, we don’t want to use deployment as a release mechanism for more complex features and code changes where the probability and impact of issues are high.
Progressive Release vs Progressive Delivery
Beyond deployment,
we use feature flags (yes, we use Unleash to build Unleash)
to control which customers can access individual new features at runtime without needing a code deployment. This practice of
progressive release
allows us to gradually expose features. This enables us to validate the solution meets users expectations and is performant in real-world scenarios.
In each new deployment, all code paths are physically in production, but we don’t enable them for every customer. This decouples deployment (code being in production) from release (code being available to users). Using Charity Majors’ metaphor again, while deployment is a chainsaw, progressive release is a powerful scalpel, offering precise control over feature exposure.
Common progressive delivery methods
Progressive delivery involves reducing risk during new feature releases or updates. By gradually exposing changes to users, teams can monitor performance, gather feedback, and, if needed, roll back quickly. These are the most common strategies used for progressive delivery
Canary release
: Canary releases involve rolling out a new version to a small subset of users first before releasing to the greater user base. This approach allows teams to observe the deployments’ performance and stability in production without impacting the entire user base. If issues arise, the rollout can be paused or reverted.
Blue-green deployments
: Blue-green deployments maintain two identical production environments; one active environment as your “blue” and one idle as your “green”. When a new version is ready, it’s deployed to the idle environment. Traffic is then switched from blue to green in a controlled manner, either gradually or all at once.
Feature flagging
: Feature flags decouple deployment from release by enabling or disabling features at runtime. This granular control allows teams to ship code safely, test features in production, and progressively roll out functionality to specific user segments.
Why Progressive Delivery?
Progressive Delivery offer three main benefits over standard CI/CD or traditional batch updates:
Live testing
Risk mitigation
Improved user experience
Live testing
When working on new features, it’s often beneficial to experiment with a small percentage of users first—perhaps even as small as 1%. This controlled exposure allows teams to gather feedback on usability, correctness, and other factors before increasing the rollout percentage. This incremental approach can be implemented at both deployment time and runtime.
Risk mitigation
Deploying new features at scale inevitably spawns unexpected errors. Progressive delivery hedges against these risks by limiting the impact of brand new code. Minor errors can be fixed with barely a hiccup, and major catastrophes can be rolled back instantly while only affecting a small subset of users.
Improved user experience
Changing features directly impacts user experience. Progressive delivery lets you gauge user response to changes, avoiding large scale backlash. You can even do advanced feature testing, pushing different versions to different groups and seeing which implementation has the best response.
Progressive delivery with feature flags
Feature flags enable or disable features in real-time
without deploying new code. It provides flexibility in managing features across different user segments, environments, or stages of development.
Feature flags play a key role in progressive delivery by
enabling gradual rollouts to specific user groups or percentages.
This approach reduces risk by allowing teams to monitor performance and user feedback, making it easy to adjust or roll back changes if issues arise.
The Unleash approach to progressive delivery with feature flags
Unleash empowers teams to manage progressive delivery with precision and control, ensuring safer and faster deployments. Its flexible and robust feature flagging platform allows teams to experiment, reduce risks, and deliver better user experiences.
Key features that enable progressive delivery include:
Kill Switches
Unleash provides
kill switches to instantly disable problematic features
, minimizing downtime and impact on users. This ensures swift issue resolution without the need for redeployments.
Rollbacks
Rollbacks allow teams to
revert to previous feature states seamlessly
, providing a safety net for unforeseen issues during rollouts. With Unleash, rollbacks can be performed instantly, reducing the risk of prolonged disruptions.
Strategy Constraints
Strategy constraints in Unleash
enable targeted rollouts based on attributes like user location, environment, or custom criteria. This precise control supports gradual and risk-free feature deployment.
Open source options for feature management
Unlike proprietary software where users are bound to the product roadmap determined by the company (and its shareholders), an
open-source feature management system allows you to modify and improve the software based on your specific use cases
. Our users are not bound or dependent on the limitations of our code.
Unleash open source
is available as a docker container, or click-to-deploy in Heroku and Digital Ocean. Choose your preferred deployment and get started in minutes.
While t
here are other proprietary tools such as LaunchDarkly
, we believe there are a lot of benefits to using an open-source system like ours. Ready to implement Progressive Delivery in your DevOps pipeline?  Explore how Unleash supports
Progressive Delivery
, or
try it for free today
.
FAQs about Progressive Delivery
What is progressive delivery and how does it work?
Progressive delivery is a software release approach that gradually introduces new capabilities to a subset of users before wider adoption. It combines progressive deployment, which rolls out new software versions to small user groups, with progressive release, which makes specific features available at runtime. This method allows teams to test changes in a live production environment, gather real-world feedback, and expand the release based on verified results. It reduces risk and ensures changes are technically sound and meet user needs effectively.
How do feature flags enable progressive delivery?
Feature flags are pivotal in progressive delivery by allowing dynamic control over features without requiring new code deployments. They
enable gradual rollouts
to specific user groups or percentages, decoupling deployment from feature release. This flexibility reduces risk by letting teams monitor performance and gather feedback from limited audiences. If issues arise, features can be instantly disabled or rolled back, providing a critical safety net.
What are the key benefits of adopting progressive delivery?
Adopting progressive delivery significantly reduces the risk associated with new software releases by identifying issues early within limited user segments. It accelerates feedback loops, allowing teams to iterate rapidly
or rollback
based on real user behavior and performance data. This approach leads to improved software quality, better user experiences, and enhanced flexibility to respond quickly to market changes. It also fosters greater collaboration between development, operations, and product teams.
How does progressive delivery differ from continuous delivery?
While continuous delivery focuses on maintaining code in a constantly deployable state, progressive delivery extends this by meticulously controlling how and to whom new features are released. Continuous delivery ensures fast and frequent deployments, but progressive delivery adds a layer of risk mitigation by enabling gradual exposure to specific user subsets. It shifts the focus from simply getting code into production to managing the user experience of new features in a controlled, iterative manner. This allows for testing in production and making data-driven decisions before a full rollout.
What deployment strategies are commonly used in progressive delivery?
Common strategies include
canary releases
, which deploy a new version to a small user group before a full rollout to monitor performance.
Blue/green deployments involve maintaining two identical production environments
and switching traffic to the new version once validated. Feature flags are also central, allowing specific functionalities to be toggled on or off for different user segments. A/B testing is another strategy that compares variations of a feature to determine which performs better based on user data.
Share this article
Explore further
Company
Unleash 8.0
Melinda Fekete
Documentation Lead
Company
Evolving Our Open Source Commitment: Unleash is Moving to AGPLv3
Ivar Østhus
CTO & co-founder
Industry Insights
Build, Deploy, or Request: Where your configuration decisions actually belong
Wojtek Gawroński
Developer Advocate