---
title: View information about versions of a prompt in Prompt management - Amazon Bedrock
id: view-information-about-versions-of-a-prompt-in-prompt-management-amazon-bedrock
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:30.530802Z'
source: https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-management-version-view.html
source_domain: docs.aws.amazon.com
fetched_at: '2026-08-02T03:11:30.524799Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 13.0
---

View information about versions of a prompt in Prompt management - Amazon Bedrock
View a markdown version of this page
View information about versions of a prompt in Prompt management - Amazon Bedrock
Documentation
Amazon Bedrock
User Guide
View information about versions of a prompt in Prompt management
To learn how to view information about a version of your prompt, choose the tab for your preferred method, and then follow the steps:
Console
To view information about a version of your prompt
Sign in to the AWS Management Console with an IAM identity that has permissions to use the Amazon Bedrock console. Then, open the Amazon Bedrock console at
https://console.aws.amazon.com/bedrock
.
Select
Prompt management
from the left navigation pane. Then, choose a prompt in the
Prompts
section.
In the
Prompt versions
section, choose a version.
In the
Version details
page, you can see information about the version, the prompt message, and its configurations. For more information about testing a version of the prompt, see
Test a prompt using Prompt management
.
API
To get information about a version of your prompt, send a
GetPrompt
request with an
Agents for Amazon Bedrock build-time endpoint
and specify the ARN or ID of the prompt as the
promptIdentifier
. In the
promptVersion
field, specify the version number.
Javascript is disabled or is unavailable in your browser.
To use the Amazon Web Services Documentation, Javascript must be enabled. Please refer to your browser's Help pages for instructions.
Document Conventions
Create a version
Compare versions
Did this page help you? - Yes
Thanks for letting us know we're doing a good job!
If you've got a moment, please tell us what we did right so we can do more of it.
Did this page help you? - No
Thanks for letting us know this page needs work. We're sorry we let you down.
If you've got a moment, please tell us how we can make the documentation better.