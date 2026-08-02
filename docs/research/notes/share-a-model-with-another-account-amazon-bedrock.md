---
title: Share a model with another account - Amazon Bedrock
id: share-a-model-with-another-account-amazon-bedrock
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:51:41.177831Z'
source: https://docs.aws.amazon.com/bedrock/latest/userguide/share-model-share.html
source_domain: docs.aws.amazon.com
fetched_at: '2026-08-02T03:51:41.158827Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 15.0
---

Share a model with another account - Amazon Bedrock
View a markdown version of this page
Share a model with another account - Amazon Bedrock
Documentation
Amazon Bedrock
User Guide
Share a model with another account
After you
fulfill the prerequisites
, you can share a model. Choose the tab for your preferred method, and then follow the steps:
Console
Sign in to the AWS Management Console with an IAM identity that has permissions to use the Amazon Bedrock console. Then, open the Amazon Bedrock console at
https://console.aws.amazon.com/bedrock
.
From the left navigation pane, choose
Custom models
under
Tune
.
Select the button next to the model that you want to share. Then, choose the three dots (
) and select
Share
.
In the
Model sharing details
section, do the following:
In the
Name for shared model
field, give the shared model a name.
In the
Recipient account ID
field, specify the ID of the account that will receive the model.
(Optional) To add tags, expand the
Tags
section. For more information, see
Tagging Amazon Bedrock resources
.
Choose
Share model
. After the recipient accepts the model in
Resource Access Manager
, the model appears in their list of custom models.
API
To share a model, send a
CreateResourceShare
request with an
AWS Resource Access Manager endpoint
. Minimally, provide the following fields:
Field
Use case
Name
To provide a name for the resource share.
resourceArns
To specify the ARNs of each model to share.
principals
To specify the principals to share the model with.
The
CreateResourceShare
response returns a
resourceShareArn
that you can use to manage the resource share.
The account receiving a model can check whether a model has been shared by sending a
ListCustomModels
request with an
Amazon Bedrock control plane endpoint
. Models that have been shared will show up with a
shared
status of
true
.
After sharing the model, the recipient of the model must copy it into a Region to use it. For more information, see
Copy a customized or shared model to use in a Region
.
Javascript is disabled or is unavailable in your browser.
To use the Amazon Web Services Documentation, Javascript must be enabled. Please refer to your browser's Help pages for instructions.
Document Conventions
Prerequisites
View information about shared models
Did this page help you? - Yes
Thanks for letting us know we're doing a good job!
If you've got a moment, please tell us what we did right so we can do more of it.
Did this page help you? - No
Thanks for letting us know this page needs work. We're sorry we let you down.
If you've got a moment, please tell us how we can make the documentation better.