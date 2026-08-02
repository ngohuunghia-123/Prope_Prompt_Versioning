---
title: Identity and access management for Amazon Bedrock - Amazon Bedrock
id: identity-and-access-management-for-amazon-bedrock-amazon-bedrock
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:51:43.911268Z'
source: https://docs.aws.amazon.com/bedrock/latest/userguide/security-iam.html
source_domain: docs.aws.amazon.com
fetched_at: '2026-08-02T03:51:43.906300Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 13.0
---

Identity and access management for Amazon Bedrock - Amazon Bedrock
View a markdown version of this page
Identity and access management for Amazon Bedrock - Amazon Bedrock
Documentation
Amazon Bedrock
User Guide
Audience
Authenticating with identities
Managing access using policies
Identity and access management for Amazon Bedrock
AWS Identity and Access Management (IAM) is an AWS service that helps an administrator securely control access
      to AWS resources. IAM administrators control who can be
authenticated
(signed in) and
authorized
(have permissions) to use Amazon Bedrock resources. IAM is an AWS service that you can
      use with no additional charge.
Topics
Audience
Authenticating with identities
Managing access using policies
How Amazon Bedrock works with IAM
Identity-based policy examples for Amazon Bedrock
IAM policies for Amazon Bedrock Projects
AWS managed policies for Amazon Bedrock
Service roles
Configure access to Amazon S3 buckets
Troubleshooting Amazon Bedrock identity and access
Audience
How you use AWS Identity and Access Management (IAM) differs based on your role:
Service user
- request permissions from your
            administrator if you cannot access features (see
Troubleshooting Amazon Bedrock identity and access
)
Service administrator
- determine user access and
            submit permission requests (see
How Amazon Bedrock works with IAM
)
IAM administrator
- write policies to manage
            access (see
Identity-based policy examples for Amazon Bedrock
)
Authenticating with identities
Authentication is how you sign in to AWS using your identity credentials. You must be authenticated as the AWS account root user, an IAM user, or by assuming an IAM role.
You can sign in as a federated identity using credentials from an identity source like AWS IAM Identity Center (IAM Identity Center), single sign-on authentication, or Google/Facebook credentials. For more information about signing in, see
How to sign in to your AWS account
in the
AWS Sign-In User Guide
.
For programmatic access, AWS provides an SDK and CLI to cryptographically sign requests. For more information, see
AWS Signature Version 4 for API requests
in the
IAM User Guide
.
AWS account root user
When you create an AWS account, you begin with one sign-in identity called the AWS account
root user
that has complete access to all AWS services and resources. We strongly recommend that you don't use the root user for everyday tasks. For tasks that require root user credentials, see
Tasks that require root user credentials
in the
IAM User Guide
.
Federated identity
As a best practice, require human users to use federation with an identity provider to access AWS services using temporary credentials.
A
federated identity
is a user from your enterprise directory, web identity provider, or Directory Service that accesses AWS services using credentials from an identity source. Federated identities assume roles that provide temporary credentials.
For centralized access management, we recommend AWS IAM Identity Center. For more information, see
What is IAM Identity Center?
in the
AWS IAM Identity Center User Guide
.
IAM users and groups
An
IAM user
is an identity with specific permissions for a single person or application. We recommend using temporary credentials instead of IAM users with long-term credentials. For more information, see
Require human users to use federation with an identity provider to access AWS using temporary credentials
in the
IAM User Guide
.
An
IAM group
specifies a collection of IAM users and makes permissions easier to manage for large sets of users. For more information, see
Use cases for IAM users
in the
IAM User Guide
.
IAM roles
An
IAM role
is an identity with specific permissions that provides temporary credentials. You can assume a role by
switching from a user to an IAM role (console)
or by calling an AWS CLI or AWS API operation. For more information, see
Methods to assume a role
in the
IAM User Guide
.
IAM roles are useful for federated user access, temporary IAM user permissions, cross-account access, cross-service access, and applications running on Amazon EC2. For more information, see
Cross account resource access in IAM
in the
IAM User Guide
.
Managing access using policies
You control access in AWS by creating policies and attaching them to AWS identities or resources. A policy defines permissions when associated with an identity or resource. AWS evaluates these policies when a principal makes a request. Most policies are stored in AWS as JSON documents. For more information about JSON policy documents, see
Overview of JSON policies
in the
IAM User Guide
.
Using policies, administrators specify who has access to what by defining which
principal
can perform
actions
on what
resources
, and under what
conditions
.
By default, users and roles have no permissions. An IAM administrator creates IAM policies and adds them to roles, which users can then assume. IAM policies define permissions regardless of the method used to perform the operation.
Identity-based policies
Identity-based policies are JSON permissions policy documents that you attach to an identity (user, group, or role). These policies control what actions identities can perform, on which resources, and under what conditions. To learn how to create an identity-based policy, see
Define custom IAM permissions with customer managed policies
in the
IAM User Guide
.
Identity-based policies can be
inline policies
(embedded directly into a single identity) or
managed policies
(standalone policies attached to multiple identities). To learn how to choose between managed and inline policies, see
Choose between managed policies and inline policies
in the
IAM User Guide
.
Resource-based policies
Resource-based policies are JSON policy documents that you attach to a resource. Examples include IAM
role trust policies
and Amazon S3
bucket policies
. In services that support resource-based policies, service administrators can use them to control access to a specific resource. You must
specify a principal
in a resource-based policy.
Resource-based policies are inline policies that are located in that service. You can't use AWS managed policies from IAM in a resource-based policy.
Other policy types
AWS supports additional policy types that can set the maximum permissions granted by more common policy types:
Permissions boundaries
– Set the maximum permissions that an identity-based policy can grant to an IAM entity. For more information, see
Permissions boundaries for IAM entities
in the
IAM User Guide
.
Service control policies (SCPs)
– Specify the maximum permissions for an organization or organizational unit in AWS Organizations. For more information, see
Service control policies
in the
AWS Organizations User Guide
.
Resource control policies (RCPs)
– Set the maximum available permissions for resources in your accounts. For more information, see
Resource control policies (RCPs)
in the
AWS Organizations User Guide
.
Session policies
– Advanced policies passed as a parameter when creating a temporary session for a role or federated user. For more information, see
Session policies
in the
IAM User Guide
.
Multiple policy types
When multiple types of policies apply to a request, the resulting permissions are more complicated to understand. To learn how AWS determines whether to allow a request when multiple policy types are involved, see
Policy evaluation logic
in the
IAM User Guide
.
Javascript is disabled or is unavailable in your browser.
To use the Amazon Web Services Documentation, Javascript must be enabled. Please refer to your browser's Help pages for instructions.
Document Conventions
Data retention
How Amazon Bedrock works with IAM
Did this page help you? - Yes
Thanks for letting us know we're doing a good job!
If you've got a moment, please tell us what we did right so we can do more of it.
Did this page help you? - No
Thanks for letting us know this page needs work. We're sorry we let you down.
If you've got a moment, please tell us how we can make the documentation better.