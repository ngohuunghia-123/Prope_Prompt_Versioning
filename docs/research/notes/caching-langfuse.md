---
title: Caching - Langfuse
id: caching-langfuse
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:06.286194Z'
source: https://langfuse.com/docs/prompt-management/features/caching
source_domain: langfuse.com
fetched_at: '2026-08-02T03:12:06.277177Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 16.0
---

Caching - Langfuse
Langfuse v4: up to 165× faster ·
Read more
Langfuse v4 is here: real-time, up to 165× faster ·
Read more
Docs
Caching
Docs
Prompt Management
Features
Caching
Copy page
Caching of Prompts in Client SDKs
Langfuse prompts are cached client-side in the SDKs, so
there's no latency impact after the first use
and no availability risk. You can also pre-fetch prompts on startup to populate the cache or provide a fallback prompt.
Cache Hit
Background Revalidation
Cache Miss
Optional: Pre-fetch
Optional: Fallback
When the SDK cache contains a fresh prompt, it's returned
immediately
without any network requests.
When the cache TTL has expired, stale prompts are served
immediately
while it
revalidates in the background
.
This ensures
high availability
- users never wait for network requests while the cache stays fresh.
When no cached prompt exists (e.g., first application startup), the prompt is fetched from the API. The API caches prompts in a Redis cache to ensure low latency.
Multiple fallback layers ensure
resilience
- if Redis is unavailable, the database serves as backup.
Pre-fetching prompts during application startup ensures that the cache is populated before runtime requests.
This step is optional and often unnecessary. Typically, the minimal latency experienced during the first use after a service starts is acceptable. See examples below on how to set this up.
When both the local cache is empty and the Langfuse API is unavailable, a fallback prompt can be used to ensure 100% availability.
This is rarely necessary because the prompts API is highly available, and we closely monitor its performance (
status page
). In the event of a brief service disruption, the SDK-level prompt cache typically ensures that applications remain unaffected.
Optional: Customize caching duration (TTL)
The caching duration is configurable if you wish to reduce network overhead of the Langfuse Client. The default cache TTL (Time To Live) is 60 seconds. After the TTL expires, the SDKs will refetch the prompt in the background and update the cache. Refetching is done asynchronously and does not block the application.
Python SDK
JS/TS SDK
# Get current `production` prompt version and cache for 5 minutes
prompt
=
langfuse.get_prompt(
"movie-critic"
,
cache_ttl_seconds
=
300
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
// Get current `production` version and cache prompt for 5 minutes
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
, {
cacheTtlSeconds
:
300
,
});
Optional: Disable caching
You can disable caching by setting the
cacheTtlSeconds
to
0
. This will ensure that the prompt is fetched from the Langfuse API on every call. This is recommended for non-production use cases where you want to ensure that the prompt is always up to date with the latest version in Langfuse.
Python SDK
JS/TS SDK
prompt
=
langfuse.get_prompt(
"movie-critic"
,
cache_ttl_seconds
=
0
)
# Common in non-production environments, no cache + latest version
prompt
=
langfuse.get_prompt(
"movie-critic"
,
cache_ttl_seconds
=
0
,
label
=
"latest"
)
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
, {
cacheTtlSeconds
:
0
,
});
// Common in non-production environments, no cache + latest version
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
, {
cacheTtlSeconds
:
0
,
label
:
"latest"
,
});
Optional: Guaranteed availability of prompts
While usually not necessary, you can ensure 100% availability of prompts by pre-fetching them on application startup and providing a fallback prompt. Please follow this
guide
for more information.
Performance measurement of initial fetch
We measured the execution time of the following snippet with fully disabled caching. You can run
this notebook
yourself to verify the results.
prompt
=
langfuse.get_prompt(
"perf-test"
,
cache_ttl_seconds
=
0
)
prompt.compile(
input
=
"test"
)
Results from 1000 sequential executions using Langfuse Cloud (includes network latency):
count    1000.000000
mean        0.039335 sec
std         0.014172 sec
min         0.032702 sec
25%         0.035387 sec
50%         0.037030 sec
75%         0.041111 sec
99%         0.068914 sec
max         0.409609 sec
Was this page helpful?
Good
Bad
Support
Last edited
Previous
Config
Next
Webhooks
On this page
Caching of Prompts in Client SDKs
Optional: Customize caching duration (TTL)
Optional: Disable caching
Optional: Guaranteed availability of prompts
Performance measurement of initial fetch
Actions
Give us feedback
Edit this page on GitHub
Contributors
Last edited
alexleventer
Jannik Maierhöfer
Hassieb Pakzad
+
1
more
GitHub
X
Ask AI
A
A