---
title: Guaranteed Availability - Langfuse
id: guaranteed-availability-langfuse
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:09.843109Z'
source: https://langfuse.com/docs/prompt-management/features/guaranteed-availability
source_domain: langfuse.com
fetched_at: '2026-08-02T03:12:09.837112Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 16.0
---

Guaranteed Availability - Langfuse
Langfuse v4: up to 165× faster ·
Read more
Langfuse v4 is here: real-time, up to 165× faster ·
Read more
Docs
Guaranteed Availability
Docs
Prompt Management
Features
Guaranteed Availability
Copy page
Guaranteed Availability
Implementing this is usually not necessary as it adds complexity to your application. The Langfuse Prompt Management is highly available due to multiple
caching layers
and we closely monitor its performance (
status page
). However, if you require 100% availability, you can use the following options.
The Langfuse API has high uptime and prompts are
cached locally
in the SDKs to prevent network issues from affecting your application.
However,
get_prompt()
/
getPrompt()
will throw an exception if:
No local (fresh or stale) cached prompt is available -> new application instance fetching prompt for the first time
and
network request fails -> networking or Langfuse API issue (after retries)
To guarantee 100% availability, there are two options:
Pre-fetch prompts on application startup and exit the application if the prompt is not available.
Provide a
fallback
prompt that will be used in these cases.
Option 1: Pre-fetch prompts
Pre-fetch prompts on application startup and exit the application if the prompt is not available.
Python (Flask)
JS/TS (Express)
from
flask
import
Flask, jsonify
from
langfuse
import
Langfuse
# Initialize the Flask app and Langfuse client
app
=
Flask(__name__)
langfuse
=
Langfuse()
def
fetch_prompts_on_startup
():
try
:
# Fetch and cache the production version of the prompt
langfuse.get_prompt(
"movie-critic"
)
except
Exception
as
e:
print
(
f
"Failed to fetch prompt on startup:
{
e
}
"
)
sys.exit(
1
)
# Exit the application if the prompt is not available
# Call the function during application startup
fetch_prompts_on_startup()
@
app
.
route
(
'/get-movie-prompt/<movie>'
,
methods
=
[
'GET'
])
def
get_movie_prompt
(
movie
):
prompt
=
langfuse.get_prompt(
"movie-critic"
)
compiled_prompt
=
prompt.compile(
criticlevel
=
"expert"
,
movie
=
movie)
return
jsonify({
"prompt"
: compiled_prompt})
if
__name__
==
'__main__'
:
app.run(
debug
=
True
)
import
express
from
"express"
;
import
{ LangfuseClient }
from
"@langfuse/client"
;
// Initialize the Express app and Langfuse client
const
app
=
express
();
const
langfuse
=
new
LangfuseClient
();
async
function
fetchPromptsOnStartup
() {
try
{
// Fetch and cache the production version of the prompt
await
langfuse.prompt.
get
(
"movie-critic"
);
}
catch
(error) {
console.
error
(
"Failed to fetch prompt on startup:"
, error);
process.
exit
(
1
);
// Exit the application if the prompt is not available
}
}
// Call the function during application startup
fetchPromptsOnStartup
();
app.
get
(
"/get-movie-prompt/:movie"
,
async
(
req
,
res
)
=>
{
const
movie
=
req.params.
movie
;
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
);
const
compiledPrompt
=
prompt.
compile
({
criticlevel
:
"expert"
, movie
});
res.
json
({
prompt
:
compiledPrompt
});
});
app.
listen
(
3000
, ()
=>
{
console.
log
(
"Server is running on port 3000"
);
});
Option 2: Fallback
Provide a fallback prompt that will be used in these cases:
Python SDK
JS/TS SDK
from
langfuse
import
Langfuse
langfuse
=
Langfuse()
# Get `text` prompt with fallback
prompt
=
langfuse.get_prompt(
"movie-critic"
,
fallback
=
"Do you like
{{
movie
}}
?"
)
# Get `chat` prompt with fallback
chat_prompt
=
langfuse.get_prompt(
"movie-critic-chat"
,
type
=
"chat"
,
fallback
=
[{
"role"
:
"system"
,
"content"
:
"You are an expert on
{{
movie
}}
"
}]
)
# True if the prompt is a fallback
prompt.is_fallback
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
// Get `text` prompt with fallback
const
prompt
=
await
langfuse.prompt.
get
(
"movie-critic"
, {
fallback
:
"Do you like {{movie}}?"
,
});
// Get `chat` prompt with fallback
const
chatPrompt
=
await
langfuse.prompt.
get
(
"movie-critic-chat"
, {
type
:
"chat"
,
fallback
:
[{
role
:
"system"
,
content
:
"You are an expert on {{movie}}"
}],
});
// True if the prompt is a fallback
prompt.
isFallback
;
Was this page helpful?
Good
Bad
Support
Last edited
Previous
n8n Node
Next
A/B Testing
On this page
Guaranteed Availability
Option 1: Pre-fetch prompts
Option 2: Fallback
Actions
Give us feedback
Edit this page on GitHub
Contributors
Last edited
Jannik Maierhöfer
Hassieb Pakzad
Marc Klingen
GitHub
X
Ask AI
A
A