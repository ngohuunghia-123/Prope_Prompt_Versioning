---
title: Release Labels - PromptLayer
id: release-labels-promptlayer
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:03.193966Z'
source: https://docs.promptlayer.com/features/prompt-registry/release-labels
source_domain: docs.promptlayer.com
fetched_at: '2026-08-02T03:11:03.177966Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 16.0
---

Release Labels - PromptLayer
Documentation Index
Fetch the complete documentation index at:
/llms.txt
Use this file to discover all available pages before exploring further.
Skip to main content
Release Labels provide a powerful way to organize and manage versions of your prompt templates in the Prompt Registry. They allow you to:
Easily deploy different versions of a prompt template
Safely test new versions with a subset of users before a full rollout
Gradually release updates to minimize risk
Segment users to receive specific versions (e.g., beta users, internal employees)
​
Adding Release Labels
You can add Release Labels to a specific version of a prompt template either through the UI.
In the Prompt Registry, hover over a prompt template version
Click “Add Release Label”
Enter a unique label name (e.g. “prod”, “staging”, “v2”)
​
Retrieving Prompts by Release Label
To retrieve a specific version of a prompt template, pass the
label
parameter when getting the template:
Python SDK
JavaScript
promptlayer_client.templates.get(
"my_template"
, {
"label"
:
"prod"
})
const
template
=
await
promptLayerClient
.
templates
.
get
(
"my_template"
, {
label:
"prod"
});
This will return the version of the prompt template associated with the “prod” release label. This also works with
promptlayer_client.run()
.
​
Using Release Labels for A/B Testing
Release Labels, combined with
Dynamic Release Labels
, enable powerful A/B testing capabilities:
Create multiple versions of a prompt template
Set up a Dynamic Release Label to overload an existing release label (e.g., “prod”)
Configure the Dynamic Release Label to split traffic between different versions based on percentages or user segments
Programmatically retrieve the prompt using the original release label, which will now dynamically route to the appropriate version
Analyze performance of each version using PromptLayer’s analytics and Evaluations
This approach allows you to test prompt changes on a subset of users, compare performance, and gradually roll out updates while maintaining a single, consistent Release Label for your application to use.
​
Best Practices
Use descriptive Release Labels that indicate the version’s stage or intended audience (e.g., “prod”, “staging”, “beta_users”)
Remove unused Release Labels to keep your prompt template organized
Use Dynamic Release Labels for more advanced traffic splitting and segmentation
With Release Labels, you can confidently manage prompt template versions and roll out updates without code changes. Combine them with PromptLayer’s
versioning
,
analytics
, and
evaluations
for a powerful prompt engineering workflow.
Was this page helpful?
Yes
No
Sharing Requests
Dynamic Release Labels
⌘
I
Assistant
Responses are generated using AI and may contain mistakes.