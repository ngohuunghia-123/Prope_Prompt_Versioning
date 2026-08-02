---
title: CI/CD Integration for LLM Eval and Security | Promptfoo
id: cicd-integration-for-llm-eval-and-security-promptfoo
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:11:54.732542Z'
source: https://www.promptfoo.dev/docs/integrations/ci-cd/
source_domain: www.promptfoo.dev
fetched_at: '2026-08-02T03:11:54.724545Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: docs
deprecated: false
utility_score: 16.0
---

CI/CD Integration for LLM Eval and Security | Promptfoo
Skip to main content
Meet Promptfoo at the OpenAI booths:
Black Hat #2967, Aug 4-6
·
DEF CON 34 #1412, Aug 7-9
On this page
Integrate promptfoo into your CI/CD pipelines to automatically evaluate prompts, test for security vulnerabilities, and ensure quality before deployment. This guide covers modern CI/CD workflows for both quality testing and security scanning.
Why CI/CD for LLM Apps?
​
Catch regressions early
- Test prompt changes before they reach production
Security scanning
- Automated red teaming and vulnerability detection
Quality gates
- Enforce minimum performance thresholds
Compliance
- Generate reports for OWASP, NIST, and other frameworks
Cost control
- Track token usage and API costs over time
Quick Start
​
If you're using GitHub Actions, check out our
dedicated GitHub Actions guide
or the
GitHub Marketplace action
.
For other platforms, here's a basic example:
# Run eval (no global install required)
npx promptfoo@latest
eval
-c
promptfooconfig.yaml
-o
results.json
# Run security scan (red teaming)
npx promptfoo@latest redteam run
Prerequisites
​
Node.js
>=22.22.0
installed in your CI environment (Node.js 24 LTS recommended)
LLM provider API keys (stored as secure environment variables)
A promptfoo configuration file (
promptfooconfig.yaml
)
(Optional) Docker for containerized environments
Core Concepts
​
1. Eval vs Red Teaming
​
Promptfoo supports two main CI/CD workflows:
Eval
- Test prompt quality and performance:
npx promptfoo@latest
eval
-c
promptfooconfig.yaml
Red Teaming
- Security vulnerability scanning:
npx promptfoo@latest redteam run
See our
red team quickstart
for security testing details.
Attach CI/CD Context with Tags
​
Use repeatable
--tag key=value
flags to attach pipeline context to an evaluation
without modifying
promptfooconfig.yaml
or a red team scan template. Tags are saved
with the eval and included when results are shared.
npx promptfoo@latest
eval
--tag
ci.run-id
=
"
$CI_PIPELINE_ID
"
--tag
git.sha
=
"
$CI_COMMIT_SHA
"
npx promptfoo@latest redteam run
--tag
ci.run-id
=
"
$CI_PIPELINE_ID
"
--tag
git.sha
=
"
$CI_COMMIT_SHA
"
promptfoo redteam eval
accepts the same
--tag
option when running previously
generated probes from
redteam.yaml
.
2. Output Formats
​
Promptfoo supports multiple output formats for different CI/CD needs:
# JSON for programmatic processing
npx promptfoo@latest
eval
-o
results.json
# HTML for human-readable reports
npx promptfoo@latest
eval
-o
report.html
# JUnit XML for native CI test-report viewers
npx promptfoo@latest
eval
-o
results.junit.xml
# Multiple formats
npx promptfoo@latest
eval
-o
results.json
-o
report.html
-o
results.junit.xml
Learn more about
output formats and processing
.
Enterprise Feature
SonarQube integration is available in
Promptfoo Enterprise
. Use the standard JSON output format and process it for SonarQube import.
3. Quality Gates
​
Fail the build when quality thresholds aren't met:
# Fail on any test failures
npx promptfoo@latest
eval
--fail-on-error
# Custom threshold checking
npx promptfoo@latest
eval
-o
results.json
PASS_RATE
=
$(
jq
'.results.stats.successes / (.results.stats.successes + .results.stats.failures) * 100'
results.json
)
if
((
$
(
echo "$PASS_RATE
<
95
"
|
bc
-
l
)
))
;
then
echo
"Quality gate failed: Pass rate
${PASS_RATE}
% < 95%"
exit
1
fi
See
assertions and metrics
for comprehensive validation options.
Platform-Specific Guides
​
GitHub Actions
​
.github/workflows/eval.yml
name
:
LLM Eval
on
:
pull_request
:
paths
:
-
'prompts/**'
-
'promptfooconfig.yaml'
jobs
:
evaluate
:
runs-on
:
ubuntu
-
latest
steps
:
-
uses
:
actions/checkout@v4
-
uses
:
actions/setup
-
node@v4
with
:
node-version
:
'24'
cache
:
'npm'
-
name
:
Cache promptfoo
uses
:
actions/cache@v4
with
:
path
:
~/.cache/promptfoo
key
:
$
{
{
runner.os
}
}
-
promptfoo
-
$
{
{
hashFiles('prompts/
**')
}
}
restore-keys
:
|
${{ runner.os }}-promptfoo-
-
name
:
Run eval
env
:
OPENAI_API_KEY
:
$
{
{
secrets.OPENAI_API_KEY
}
}
PROMPTFOO_CACHE_PATH
:
~/.cache/promptfoo
run
:
|
npx promptfoo@latest eval \
-c promptfooconfig.yaml \
--share \
-o results.json \
-o report.html
-
name
:
Check quality gate
run
:
|
FAILURES=$(jq '.results.stats.failures' results.json)
if [ "$FAILURES" -gt 0 ]; then
echo "❌ Eval failed with $FAILURES failures"
exit 1
fi
echo "✅ All tests passed!"
-
name
:
Upload results
if
:
always()
uses
:
actions/upload
-
artifact@v4
with
:
name
:
eval
-
results
path
:
|
results.json
report.html
For red teaming in CI/CD:
.github/workflows/redteam.yml
name
:
Security Scan
on
:
schedule
:
-
cron
:
'0 0 * * *'
# Daily
workflow_dispatch
:
jobs
:
red-team
:
runs-on
:
ubuntu
-
latest
steps
:
-
uses
:
actions/checkout@v4
-
name
:
Set up Node.js
uses
:
actions/setup
-
node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e
# v6
with
:
node-version
:
'24'
-
name
:
Run red team scan
uses
:
promptfoo/promptfoo
-
action@v1
with
:
type
:
'redteam'
config
:
'promptfooconfig.yaml'
openai-api-key
:
$
{
{
secrets.OPENAI_API_KEY
}
}
github-token
:
$
{
{
secrets.GITHUB_TOKEN
}
}
See also:
Standalone GitHub Action example
.
GitLab CI
​
See our
detailed GitLab CI guide
.
.gitlab-ci.yml
image
:
node
:
24
evaluate
:
script
:
-
|
npx promptfoo@latest eval \
-c promptfooconfig.yaml \
--share \
-o output.json \
-o report.html \
-o output.junit.xml
variables
:
OPENAI_API_KEY
:
$
{
OPENAI_API_KEY
}
PROMPTFOO_CACHE_PATH
:
.cache/promptfoo
cache
:
key
:
$
{
CI_COMMIT_REF_SLUG
}
-
promptfoo
paths
:
-
.cache/promptfoo
artifacts
:
reports
:
junit
:
output.junit.xml
paths
:
-
output.json
-
report.html
Jenkins
​
See our
detailed Jenkins guide
.
Jenkinsfile
pipeline {
agent any
environment {
OPENAI_API_KEY = credentials('openai-api-key')
PROMPTFOO_CACHE_PATH = "${WORKSPACE}/.cache/promptfoo"
}
stages {
stage('Evaluate') {
steps {
sh '''
npx promptfoo@latest eval \
-c promptfooconfig.yaml \
--share \
-o results.json
'''
}
}
stage('Quality Gate') {
steps {
script {
def results = readJSON file: 'results.json'
def failures = results.results.stats.failures
if (failures > 0) {
error("Eval failed with ${failures} failures")
}
}
}
}
}
}
Other Platforms
​
Azure Pipelines
AWS CodeCommit
CircleCI
Bitbucket Pipelines
Travis CI
n8n workflows
Looper
Advanced Patterns
​
1. Docker-based CI/CD
​
Create a custom Docker image with promptfoo pre-installed:
Dockerfile
FROM node:24-slim
WORKDIR /app
COPY . .
CMD ["npx", "promptfoo@latest", "eval"]
2. Parallel Testing
​
Test multiple models or configurations in parallel:
# GitHub Actions example
strategy
:
matrix
:
model
:
[
gpt
-
5.6
,
claude
-
opus
-
4
-
8
,
gemini
-
3.1
-
pro
-
preview
]
steps
:
-
name
:
Test $
{
{
matrix.model
}
}
run
:
|
npx promptfoo@latest eval \
--providers.0.config.model=${{ matrix.model }} \
-o results-${{ matrix.model }}.json
3. Scheduled Security Scans
​
Run comprehensive security scans on a schedule:
# GitHub Actions
on
:
schedule
:
-
cron
:
'0 2 * * *'
# 2 AM daily
jobs
:
security-scan
:
runs-on
:
ubuntu
-
latest
steps
:
-
name
:
Full red team scan
run
:
|
npx promptfoo@latest redteam generate \
--plugins harmful,pii,contracts \
--strategies jailbreak,jailbreak-templates
npx promptfoo@latest redteam run
4. SonarQube Integration
​
Enterprise Feature
Direct SonarQube output format is available in
Promptfoo Enterprise
. For open-source users, export to JSON and transform the results.
For enterprise environments, integrate with SonarQube:
# Export results for SonarQube processing
-
name
:
Run promptfoo security scan
run
:
|
npx promptfoo@latest eval \
--config promptfooconfig.yaml \
-o results.json
# Transform results for SonarQube (custom script required)
-
name
:
Transform for SonarQube
run
:
|
node transform-to-sonarqube.js results.json > sonar-report.json
-
name
:
SonarQube scan
env
:
SONAR_TOKEN
:
$
{
{
secrets.SONAR_TOKEN
}
}
run
:
|
sonar-scanner \
-Dsonar.externalIssuesReportPaths=sonar-report.json
See our
SonarQube integration guide
for detailed setup.
Processing Results
​
Parsing JSON Output
​
The output JSON follows this schema:
interface
OutputFile
{
evalId
:
string
|
null
;
results
:
{
version
:
3
;
timestamp
:
string
;
stats
:
{
successes
:
number
;
failures
:
number
;
errors
:
number
;
}
;
prompts
:
Array
<
unknown
>
;
results
:
Array
<
{
success
:
boolean
;
score
:
number
;
error
?
:
string
;
// ... other fields
}
>
;
}
;
config
:
Partial
<
UnifiedConfig
>
;
shareableUrl
:
string
|
null
;
metadata
?
:
OutputMetadata
;
vars
?
:
string
[
]
;
runtimeOptions
?
:
Partial
<
EvaluateOptions
>
;
traces
?
:
TraceData
[
]
;
blobAssets
?
:
ExportedBlobAsset
[
]
;
}
promptfoo eval -o results.json
and
promptfoo export eval <evalId>
use the
same eval output envelope. Portable exports created with
promptfoo export eval <evalId> --include-media
may add embedded
blobAssets
.
Example processing script:
process-results.js
const
fs
=
require
(
'fs'
)
;
const
evalOutput
=
JSON
.
parse
(
fs
.
readFileSync
(
'results.json'
,
'utf8'
)
)
;
const
{
stats
,
results
:
evalResults
}
=
evalOutput
.
results
;
// Calculate metrics
const
passRate
=
(
stats
.
successes
/
(
stats
.
successes
+
stats
.
failures
)
)
*
100
;
console
.
log
(
`
Pass rate:
${
passRate
.
toFixed
(
2
)
}
%
`
)
;
console
.
log
(
`
Shareable URL:
${
evalOutput
.
shareableUrl
}
`
)
;
// Check for specific failures
const
criticalFailures
=
evalResults
.
filter
(
(
result
)
=>
result
.
error
?.
includes
(
'security'
)
||
result
.
error
?.
includes
(
'injection'
)
,
)
;
if
(
criticalFailures
.
length
>
0
)
{
console
.
error
(
'Critical security failures detected!'
)
;
process
.
exit
(
1
)
;
}
Posting Results
​
Post eval results to PR comments, Slack, or other channels:
# Extract and post results
SHARE_URL
=
$(
jq
-r
'.shareableUrl'
results.json
)
PASS_RATE
=
$(
jq
'.results.stats.successes / (.results.stats.successes + .results.stats.failures) * 100'
results.json
)
# Post to GitHub PR
gh
pr
comment
--body
"
## Promptfoo Eval Results
- Pass rate:
${PASS_RATE}
%
- [View detailed results](
${SHARE_URL}
)
"
Caching Strategies
​
Optimize CI/CD performance with proper caching:
# Set cache location
env
:
PROMPTFOO_CACHE_PATH
:
~/.cache/promptfoo
PROMPTFOO_CACHE_TTL
:
86400
# 24 hours
# Cache configuration
cache
:
key
:
promptfoo
-
$
{
{
hashFiles('prompts/
**'
,
'promptfooconfig.yaml')
}
}
paths
:
-
~/.cache/promptfoo
Security Best Practices
​
API Key Management
Store API keys as encrypted secrets
Use least-privilege access controls
Rotate keys regularly
Network Security
Use private runners for sensitive data
Restrict outbound network access
Consider on-premise deployments for enterprise
Data Privacy
Enable output stripping for sensitive data:
export
PROMPTFOO_STRIP_RESPONSE_OUTPUT
=
true
export
PROMPTFOO_STRIP_TEST_VARS
=
true
Audit Logging
Keep eval history
Track who triggered security scans
Monitor for anomalous patterns
Troubleshooting
​
Common Issues
​
Issue
Solution
Rate limits
Enable caching, reduce concurrency with
-j 1
Timeouts
Increase timeout values, use
--max-concurrency
Memory issues
Use streaming mode, process results in batches
Cache misses
Check cache key includes all relevant files
Debug Mode
​
Enable detailed logging:
LOG_LEVEL
=
debug npx promptfoo@latest
eval
-c
config.yaml
Real-World Examples
​
Automated Testing Examples
​
Self-grading example
- Automated LLM evaluation
Custom grading prompts
- Complex evaluation logic
Store and reuse outputs
- Multi-step testing
Security Examples
​
Red team starter
- Basic security testing
RAG red team tests
- Customer service red team testing (RBAC, competitors, harmful content)
DoNotAnswer dataset
- Harmful content detection
Integration Examples
​
GitHub Action standalone
- Custom GitHub workflows
JSON output processing
- Result parsing patterns
CSV test data
- Bulk test management
Related Documentation
​
Configuration & Testing
​
Configuration Guide
- Complete setup instructions
Test Cases
- Writing effective tests
Assertions & Metrics
- Validation strategies
Python Assertions
- Custom Python validators
JavaScript Assertions
- Custom JS validators
Security & Red Teaming
​
Red Team Architecture
- Security testing framework
OWASP Top 10 for LLMs
- Security compliance
RAG Security Testing
- Testing retrieval systems
MCP Security Testing
- Model Context Protocol security
Enterprise & Scaling
​
Enterprise Features
- Team collaboration and compliance
Red Teams in Enterprise
- Organization-wide security
Service Accounts
- Automated access
See Also
​
GitHub Actions Integration
Red Team Quickstart
Enterprise Features
Configuration Reference
Why CI/CD for LLM Apps?
Quick Start
Prerequisites
Core Concepts
1. Eval vs Red Teaming
2. Output Formats
3. Quality Gates
Platform-Specific Guides
GitHub Actions
GitLab CI
Jenkins
Other Platforms
Advanced Patterns
1. Docker-based CI/CD
2. Parallel Testing
3. Scheduled Security Scans
4. SonarQube Integration
Processing Results
Parsing JSON Output
Posting Results
Caching Strategies
Security Best Practices
Troubleshooting
Common Issues
Debug Mode
Real-World Examples
Automated Testing Examples
Security Examples
Integration Examples
Related Documentation
Configuration & Testing
Security & Red Teaming
Enterprise & Scaling
See Also