---
title: 'Update prompt label programatically · langfuse · Discussion #4284 · GitHub'
id: update-prompt-label-programatically-langfuse-discussion-4284-github
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:22.226751Z'
source: https://github.com/orgs/langfuse/discussions/4284
source_domain: github.com
fetched_at: '2026-08-02T03:11:22.220754Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: code
deprecated: false
utility_score: 15.0
---

Update prompt label programatically · langfuse · Discussion #4284 · GitHub
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
Update prompt label programatically
#4284
Closed
Answered
by
marcklingen
nikitagupta5566
asked this question in
Support
Update prompt label programatically
#4284
nikitagupta5566
Nov 18, 2024
·
3 comments
·
3 replies
Answered
by
marcklingen
Return to top
Discussion options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
nikitagupta5566
Nov 18, 2024
Hi,
Can we update the label of a prompt version programatically?
I couldn't find any api for updating prompts in API reference.
Also, the create_prompt api doesn't let the user pass version of the prompt, so any existing prompt version can't be updated.
2
You must be logged in to vote
All reactions
Answered by
marcklingen
Nov 18, 2024
thanks for raising this, can you upvote this thread?
https://github.com/orgs/langfuse/discussions/2810
View full answer
Replies:
3 comments
·
3 replies
Comment options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
dosubot[bot]
Bot
Nov 18, 2024
Yes, you can update the label of a prompt version programmatically using the Langfuse API. The API allows you to manage prompts, including creating new versions and updating existing ones. When you create a prompt with the same name, it is added as a new version, and you can assign labels to manage different versions. This enables you to update labels without changing the code. For more details, you can refer to the Langfuse documentation on prompt management
[1]
[2]
.
To continue talking to
Dosu
, mention
@dosu
.
0
You must be logged in to vote
All reactions
3 replies
Comment options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
nikitagupta5566
Nov 18, 2024
Author
@dosu
Can you share the api that can be used to update labels of a given prompt version?
All reactions
Comment options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
dosubot[bot]
Bot
Nov 18, 2024
I wasn't able to find specific information about an API endpoint for updating the labels of a given prompt version in the Langfuse documentation or repository. However, you can authenticate with the Langfuse API using Basic Auth, where you use the Langfuse Public Key as the username and the Langfuse Secret Key as the password
[1]
. For more detailed information, you might want to check the Langfuse documentation directly.
To continue talking to
Dosu
, mention
@dosu
.
👎
1
All reactions
👎
1
Comment options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
marcklingen
Nov 18, 2024
Maintainer
thanks for raising this, can you upvote this thread?
https://github.com/orgs/langfuse/discussions/2810
Marked as answer
All reactions
Answer selected by
marcklingen
Comment options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
eric8607242
Dec 23, 2024
Hi
@nikitagupta5566
,
Here is my temporary solution for updating the labels. I hope it can help you as well.
import
psycopg2
def
create_db_conn
():
conn_params
=
{
'dbname'
:
'postgres'
,
'user'
:
'postgres'
,
'password'
:
'postgres'
,
'host'
:
'0.0.0.0'
,
'port'
:
5432
}
return
psycopg2
.
connect
(
**
conn_params
)
def
assign_new_labels
(
conn
,
name
,
version
,
new_labels
):
try
:
with
conn
.
cursor
()
as
cursor
:
find_id_query
=
"""
SELECT id FROM prompts
WHERE name = %s AND version = %s
LIMIT 1
"""
cursor
.
execute
(
find_id_query
, (
name
,
version
))
result
=
cursor
.
fetchone
()
if
result
is
None
:
print
(
"No row found with the specified name and version."
)
return
target_id
=
result
[
0
]
remove_query
=
"""
UPDATE prompts
SET labels = array(SELECT unnest(labels) EXCEPT SELECT unnest(%s::text[]))
WHERE name = (SELECT name FROM prompts WHERE id = %s)
AND labels && %s::text[]
"""
cursor
.
execute
(
remove_query
, (
new_labels
,
target_id
,
new_labels
))
add_query
=
"""
UPDATE prompts
SET labels = array(SELECT DISTINCT unnest(array_cat(labels, %s::text[])))
WHERE id = %s
"""
cursor
.
execute
(
add_query
, (
new_labels
,
target_id
))
conn
.
commit
()
print
(
"Labels assigned successfully."
)
except
Exception
as
e
:
conn
.
rollback
()
print
(
f"An error occurred:
{
e
}
"
)
conn
=
create_db_conn
()
try
:
assign_production_label
(
conn
,
name
=
'test'
,
version
=
3
,
new_labels
=
[
"production"
,
"test"
])
finally
:
conn
.
close
()
2
You must be logged in to vote
👍
1
All reactions
👍
1
0 replies
Comment options
Uh oh!
There was an error while loading.
Please reload this page
.
Quote reply
maxdeichmann
Jan 28, 2025
Maintainer
Hi
@nikitagupta5566
and
@eric8607242
, thanks a lot for the discussion. You are able to do this now via our API / SDKs:
https://langfuse.com/docs/prompts/get-started#labels
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
🙏
Support
Labels
feat-prompt-management
4 participants
You can’t perform that action at this time.