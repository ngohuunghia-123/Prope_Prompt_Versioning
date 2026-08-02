---
title: Concepts - Langfuse
id: concepts-langfuse
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:49.775921Z'
source: https://langfuse.com/docs/prompt-management/data-model
source_domain: langfuse.com
fetched_at: '2026-08-02T03:11:49.767927Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 16.0
---

Concepts - Langfuse
Langfuse v4: up to 165× faster ·
Read more
Langfuse v4 is here: real-time, up to 165× faster ·
Read more
Docs
Concepts
Docs
Prompt Management
Concepts
Copy page
Core Concepts
This page discusses prompt management concepts and best practices. If you haven't already, check out the
overview
page on why it's valuable for observability of your application.
Ready to start? Check out the
Get Started guide
to create your first prompt.
The Prompt Object
Langfuse considers a prompt to be a combination of both the instructions for the LLM (this can be a single string or an array of messages) and, optionally,
additional configuration
that influences the behavior.
The prompt object also has a couple of attributes for managing different versions, variants, and deployments. This page will guide you through the most important principles of how to use prompts productively.
For detailed information about all prompt object fields and methods, see the
SDK reference documentation
.
Chat vs Text Prompts
Langfuse supports two prompt types. The
type
field determines the format and cannot be changed after creation.
Text prompts
are single strings, ideal for simple use cases or when you only need a system message.
Chat prompts
are arrays of messages with specific roles (system, user, assistant), useful when you want to manage complete conversation structures, include example exchanges, or handle chat history.
Text prompt example
{
"
name
"
:
"movie-critic"
,
"
type
"
:
"text"
,
"
prompt
"
:
"As a movie critic, do you like Dune 2?"
,
"
version
"
:
1
}
Chat prompt example
{
"
name
"
:
"movie-critic-chat"
,
"
type
"
:
"chat"
,
"
prompt
"
: [
{
"
role
"
:
"system"
,
"
content
"
:
"You are a movie critic."
},
{
"
role
"
:
"user"
,
"
content
"
:
"Do you like Dune 2?"
}
],
"
version
"
:
1
}
When to use chat prompts:
Most applications start with a text prompt. As you build more complex logic that requires managing multiple messages, role-based structures, or chat history, it makes sense to switch to chat prompts. This allows you to manage the complete conversation structure in your prompt management system.
Dynamic rendering of prompts
You can add variables to your prompts that can be dynamically filled out at runtime. There are different types of variables you can use, explained below.
Prompts support three ways to insert dynamic content at runtime:
Type
Use Case
Variables
Insert dynamic text into messages
Prompt References
Reuse prompts across other prompts, avoid duplicating common instructions
Message Placeholders
Insert arrays of messages (e.g., chat history)
Prompt Caching
Langfuse Prompt Management uses cached prompts for 2 main reasons
it adds no latency to your application.
it removes availability risk.
This means your first few traces after updating a prompt might still be using the old version. If immediate updates are critical for your use case, you can disable caching or configure a shorter TTL (time-to-live).
See the
caching documentation
for details on how caching works and how to configure it.
Versioning and Labels
Understanding how versions and labels work together is essential for managing prompts in production. They serve different but complementary purposes.
Versions
provide an immutable history of every prompt change. Each update creates a new version (1, 2, 3...).
Labels
are pointers to specific versions. Your code would typically point to labels. Common labels include:
production
- Default label, used by production applications
latest
- Always points to the newest version
Custom labels - Create labels for staging, testing, tenants, or A/B tests
Learn more about
versioning and labels
.
Deployment Workflow
Here's a typical workflow for deploying prompt changes:
Create and test:
Create a new prompt version (automatically gets the
latest
label)
Validate:
Test the new version in your development environment or using the playground
Deploy:
Update the
production
label to point to the new version
Monitor:
Your production application automatically picks up the new version on the next fetch
Rollback if needed:
Simply reassign the
production
label back to a previous version
Since your code references the labels, all this happens without changing code.
Was this page helpful?
Good
Bad
Support
Last edited
Previous
Get Started
Next
Link to Traces
On this page
Core Concepts
The Prompt Object
Chat vs Text Prompts
Dynamic rendering of prompts
Prompt Caching
Versioning and Labels
Deployment Workflow
Actions
Give us feedback
Edit this page on GitHub
Contributors
Last edited
Ben Bachem
Lotte Verheyden
Marc Klingen
GitHub
X
Ask AI
A
A