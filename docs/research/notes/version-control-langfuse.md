---
title: Version Control - Langfuse
id: version-control-langfuse
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:10:58.580515Z'
source: https://langfuse.com/docs/prompt-management/features/prompt-version-control
source_domain: langfuse.com
fetched_at: '2026-08-02T03:10:58.564513Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 16.0
---

Version Control - Langfuse
Langfuse v4: up to 165× faster ·
Read more
Langfuse v4 is here: real-time, up to 165× faster ·
Read more
Docs
Version Control
Docs
Prompt Management
Features
Version Control
Copy page
Prompt Version Control
In Langfuse, version control & deployment of prompts is managed via
versions
and
labels
.
Versions & Labels
Each prompt version is automatically assigned a
version ID
. Additionally, you can assign
labels
to follow your own versioning scheme.
Labels can be used to assign prompts to environments (staging, production), tenants (tenant-1, tenant-2), or experiments (prod-a, prod-b).
Langfuse UI
Python SDK
JS/TS SDK
Use the Langfuse UI to assign labels to a prompt.
Use the Python SDK to assign labels to a prompt when creating a new prompt version.
langfuse.create_prompt(
name
=
"movie-critic"
,
type
=
"text"
,
prompt
=
"As a
{{
criticlevel
}}
movie critic, do you like
{{
movie
}}
?"
,
labels
=
[
"production"
],
# add the label "production" to the prompt version
)
Alternatively, you can also update the labels of an existing prompt version using the Python SDK:
langfuse
=
Langfuse()
langfuse.update_prompt(
name
=
"movie-critic"
,
version
=
1
,
new_labels
=
[
"john"
,
"doe"
],
# assign these labels to the prompt version
)
Use the JS/TS SDK to assign labels to a prompt when creating a new prompt version.
import
{ LangfuseClient }
from
"@langfuse/client"
;
const
langfuse
=
new
LangfuseClient
();
await
langfuse.prompt.
create
({
name
:
"movie-critic"
,
type
:
"text"
,
prompt
:
"As a {{criticlevel}} critic, do you like {{movie}}?"
,
labels
:
[
"production"
],
// add the label "production" to the prompt version
});
Alternatively, you can also update the labels of an existing prompt version using the JS/TS SDK:
await
langfuse.prompt.
update
({
name
:
"movie-critic"
,
version
:
1
,
newLabels
:
[
"john"
,
"doe"
],
});
Fetching by Label or Version
When fetching prompts to use them in your application you can either do so by fetching a specific version or label.
Here are code examples for fetching prompts by label or version.
To "deploy" a prompt version
, you have to assign the label
production
or any environment label you created to that prompt version.
Some notes on fetching prompts:
The
latest
label points to the most recently created version.
When using a prompt without specifying a label, Langfuse will serve the version with the
production
label.
Python SDK
JS/TS SDK
from
langfuse
import
get_client
# Initialize Langfuse client
langfuse
=
get_client()
# Get specific version
prompt
=
langfuse.get_prompt(
"movie-critic"
,
version
=
1
)
# Get specific label
prompt
=
langfuse.get_prompt(
"movie-critic"
,
label
=
"staging"
)
# Get latest prompt version. The 'latest' label is automatically maintained by Langfuse.
prompt
=
langfuse.get_prompt(
"movie-critic"
,
label
=
"latest"
)
import
{ LangfuseClient }
from
"@langfuse/client"
;
const
langfuse
=
new
LangfuseClient
();
// Get specific version of a prompt (here version 1)
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
, {
version
:
1
,
});
// Get specific label
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
, {
label
:
"staging"
,
});
// Get latest prompt version. The 'latest' label is automatically maintained by Langfuse.
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
, {
label
:
"latest"
,
});
Rollbacks
When a prompt has a
production
label, then that version will be served by default in the SDKs. You can quickly rollback to a previous version by setting the
production
label to that previous version in the Langfuse UI.
Prompt Diffs
The prompt version diff view shows you the changes you made to the prompt over time. This helps you understand how the prompt has evolved and what changes have been made to debug issues or understand the impact of changes.
Protected prompt labels
Where is this feature available?
Hobby
Not Available
Core
Not Available
Pro
Teams Add-on required
Enterprise
Available
Self Hosted
Enterprise Edition
Protected prompt labels give project admins and owners (
RBAC docs
) the ability to prevent labels from being modified or deleted, ensuring better control over prompt deployment.
Once a label such as
production
is marked as protected:
viewer
and
member
roles cannot modify or delete the label from prompts, preventing changes to the
production
prompt version. This also blocks the deletion of the prompt.
admin
and
owner
roles can still modify or delete the label, effectively changing the
production
prompt version.
Admins and owners can update a label's protection status in the project settings.
Related Resources
Prompts are scoped to a project — if you use separate projects for different environments, see
how to sync prompts between them
To compare prompt versions on a dataset before promoting a label, run
Experiments
.
Was this page helpful?
Good
Bad
Support
Last edited
Previous
Link to Traces
Next
Playground
On this page
Prompt Version Control
Versions & Labels
Fetching by Label or Version
Rollbacks
Prompt Diffs
Protected prompt labels
Related Resources
Actions
Give us feedback
Edit this page on GitHub
Contributors
Last edited
Ben Bachem
Annabell Schäfer
Lotte Verheyden
+
3
more
GitHub
X
Ask AI
A
A