---
title: 'Prompt Management: Caching on SDK-level · langfuse · Discussion #1098 · GitHub'
id: prompt-management-caching-on-sdk-level-langfuse-discussion-1098-github
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:23.036238Z'
source: https://github.com/orgs/langfuse/discussions/1098
source_domain: github.com
fetched_at: '2026-08-02T03:12:23.028239Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: code
deprecated: false
utility_score: 14.0
---

Prompt Management: Caching on SDK-level · langfuse · Discussion #1098 · GitHub
Skip to content
You signed in with another tab or window.
Reload
to refresh your session.
You signed out in another tab or window.
Reload
to refresh your session.
You switched accounts on another tab or window.
Reload
to refresh your session.
Dismiss alert
Langfuse
Prompt Management: Caching on SDK-level
#1098
clemra
announced in
Announcements
Prompt Management: Caching on SDK-level
#1098
clemra
Feb 6, 2024
·
1 comment
Return to top
Discussion options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
edited by marcklingen
Uh oh!
There was an error while loading.
Please reload this page
.
clemra
Feb 6, 2024
Maintainer
The latest release of the Python and JS/TS Langfuse SDK includes
a new prompt caching feature
that improves the reliability and performance of your applications.
After launching
prompt management
in Langfuse, we've enhanced its performance and reliability in the Python and JS/TS SDKs through prompt caching.
Example (Python SDK)
# Get current production prompt version, default cache of 60 seconds
prompt
=
langfuse
.
get_prompt
(
"prompt name"
)
# Get current production prompt version and cache for 5 minutes
prompt
=
langfuse
.
get_prompt
(
"prompt name"
,
cache_ttl_seconds
=
300
)
# Get a specific prompt version and cache for 5 minutes
prompt
=
langfuse
.
get_prompt
(
"prompt name"
,
version
=
3
,
cache_ttl_seconds
=
300
)
# Disable caching for a prompt
prompt
=
langfuse
.
get_prompt
(
"prompt name"
,
cache_ttl_seconds
=
0
)
This feature stores prompts in the client SDKs' memory, cutting down on server requests and boosting your applications' reliability and speed. With a default TTL of 60 seconds, caching settings can be adjusted for individual prompts within the SDK. Should a refetch of a prompt fail, the SDK will automatically revert to the cached version, ensuring your application's availability is not compromised.
Head over to the docs for more information:
https://langfuse.com/docs/prompts#caching-in-client-sdks
Changelog:
https://langfuse.com/changelog/2024-02-05-sdk-level-prompt-caching
Looking forward to hearing your thoughts!
cc
@hassiebp
3
You must be logged in to vote
All reactions
Replies:
1 comment
Comment options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
marcklingen
Sep 3, 2024
Maintainer
We have made an update to this behavior to further optimize performance. Whenever a cached version is available it is returned immediately while checking whether an updated prompt version is available is done in the background.
https://langfuse.com/changelog/2024-09-04-prompt-management-zero-latency
1
You must be logged in to vote
All reactions
0 replies
Sign up for free
to join this conversation on GitHub
.
    Already have an account?
Sign in to comment
Category
📣
Announcements
Labels
sdk-python
sdk-js
feat-prompt-management
✅ Done
2 participants
You can’t perform that action at this time.