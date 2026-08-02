---
title: 'RFC: deprecating model registry stages · Issue #10336 · mlflow/mlflow · GitHub'
id: rfc-deprecating-model-registry-stages-issue-10336-mlflowmlflow-github
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:01.470089Z'
source: https://github.com/mlflow/mlflow/issues/10336
source_domain: github.com
fetched_at: '2026-08-02T03:12:01.457093Z'
fetch_provider: builtin
status: draft
type: note
tier: ground_truth
content_type: code
deprecated: false
utility_score: 15.0
---

RFC: deprecating model registry stages · Issue #10336 · mlflow/mlflow · GitHub
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
Uh oh!
There was an error while loading.
Please reload this page
.
mlflow
/
mlflow
Public
Notifications
You must be signed in to change notification settings
Fork
6.1k
Star
27.3k
RFC: deprecating model registry stages
#10336
New issue
Copy link
New issue
Copy link
Closed as not planned
Closed as not planned
RFC: deprecating model registry stages
#10336
Copy link
Assignees
Labels
stale
Description
jerrylian-db
opened
on Nov 9, 2023
Issue body actions
Deprecating model registry stages
Starting in
MLflow 2.9
, we plan to mark model registry stages as deprecated in favor of new tools we’ve introduced for managing and deploying models in the MLflow Model Registry. We plan to remove stage related features in a future major release. This RFC provides motivation for this change and guidance for migrating your ML workflows to the new model registry paradigm.
Background
The purpose of stages
Since the introduction of MLflow Model Registry, stages have been a tool to express the lifecycle of MLflow Models as they are productionized and deployed. Users can transition model versions through four fixed stages (from
none
, to
staging
, to
production
, and then to
archived
) as they propose, validate, deploy, and deprecate models for their ML use-cases. In doing so, model registry stages provide labeling and aliasing functionality for the model versions, by denoting the status of a model version in the UI and providing named references to model versions in the code (e.g.
/Staging
in the model URI). Model registry stages have also been used to denote the environment that the model is in.
Over the years, we’ve received extensive feedback on the inflexibility of model registry stages. We took this feedback to introduce new tools to the MLflow Model Registry so that users can express MLOps workflows that meet their needs.
New model deployment tools
As of
MLflow 2.8,
we elevated
model version tags
, introduced
model version aliases
, and enhanced the model registry UI to provide flexible and powerful ways to label and deploy MLflow models in the MLflow Model Registry. Learn more below.
Model version tags
Now prominently displayed in the new model registry UI, model version tags can be used to annotate model versions with their status. For example, you could apply a tag of key
validation_status
and value
pending
to a model version while it is being validated and then update the tag value to
passed
when it has passed smoke tests and performance tests.
Model version aliases
Model version aliases provide a flexible way to set named aliases on model versions. For example, setting a
champion
alias on a model version enables you to fetch this model version by that alias via client API
get_model_version_by_alias()
or the model URI
models:/<registered model name>@champion
. Aliases can be easily reassigned to new model versions via the UI and client API alike, thereby decoupling model deployment from the production system code. Unlike model registry stages, more than one alias can be applied to any given model version, creating powerful possibilities for model deployment.
[New] Environmental separation
In mature DevOps and MLOps workflows, organizations may set up environments to promote code and models across. With proper separation and access controls, these environments enable continuous integration and deployment for code and models. Organizations usually have a dev, a staging, and a prod environment. Thanks to the introduction of
MLflow Authentication
, you can use registered models to express access-controlled environments for your MLflow models. One registered model can correspond to each environment and you can use the new
copy_model_version()
client API
to promote your models across them.
Deprecating stages
Timeline
With the introduction of these new tools, we plan to mark model registry stages as deprecated starting in
MLflow 2.9
and fully remove stages in a future major release. Please let us know if you have any questions or concerns with deprecating model registry stages! We want to make sure that post-stages MLflow is an amazing tool for your MLOps needs and use-cases before we remove model registry stages.
Migrating models away from stages
In the new model registry paradigm, we provide different tools for each legacy stages use-case. See the information below to learn how to use the new model registry for each use-case.
Model environments:
To set up separate environments and ACLs for your model versions, create separate registered models:
Given a base name for your model’s use-case, e.g.
revenue_forecasting
, set up various registered models corresponding to your environments with different prefixes.
For example, if you want three separate dev, staging, and production environments, you can set up
dev.ml_team.revenue_forecasting
,
staging.ml_team.revenue_forecasting
, and
prod.ml_team.revenue_forecasting
registered models.
Use
MLflow Authentication
to set up appropriate ACLs to these models.
Transition models across environments:
once you have registered models set up for each environment, you can build your MLOps workflows on top of them.
For simple model promotion use cases, you can first register your MLflow models under the dev registered model and then promote models across environments using the
copy_model_version()
API
.
For more mature production-grade setups, we recommend promoting your ML code (including model training code, inference code, and ML infrastructure as code) across environments. This eliminates the need to transition models across environments. Dev ML code is experimental and in a dev environment, hence targeting the dev registered model. Before merging developed ML code into your source code repository, your CI stages the code in a staging environment for integration testing (targeting the staging registered model). Post-merge, the ML code is deployed to production for automated retraining (targeting the prod registered model). Such setups enable safe and robust CI/CD of ML systems - including not just model training, but also feature engineering, model monitoring, and automated retraining.
Model aliasing:
To specify (via named references) which model version to deploy to serve traffic within an environment (e.g. production), use
model aliases
:
Decide on an equivalent model alias for each model registry stage (e.g.,
champion
for the
Production
stage)
Assign the chosen alias to the latest model version under each stage. You can use the helper function below for this.
Update ML workflows to target the alias rather than the stage. For example, the model URI
models:/regression_model/Production
will be replaced by the model URI
models:/prod.ml_team.regression_model@champion
in the production code.
from
mlflow
import
MlflowClient
# Initialize an MLflow Client
client
=
MlflowClient
()
def
assign_alias_to_stage
(
model_name
,
stage
,
alias
):
"""
Assign an alias to the latest version of a registered model within a specified stage.
:param model_name: The name of the registered model.
:param stage: The stage of the model version for which the alias is to be assigned. Can be
"Production", "Staging", "Archived", or "None".
:param alias: The alias to assign to the model version.
:return: None
"""
latest_mv
=
client
.
get_latest_versions
(
model_name
,
stages
=
[
stage
])[
0
]
client
.
set_registered_model_alias
(
model_name
,
alias
,
latest_mv
.
version
)
Model status:
To represent and communicate the status of your model versions, use model version tags:
Set tags on model versions to indicate the status of the model.
For example, to indicate the review status of a model version, you can set a tag with key
validation_status
and value
pending
or
passed
.
Plugin authors: supporting new model registry APIs
Authors of MLflow model registry
plugins
should make the following changes to support the new model registry tools.
Implement model registry aliases
Work to be done
For model registry REST API backends, implement the
set registered model alias
,
delete registered model alias
, and
get model version by alias
REST API endpoints.
For other model registry stores, implement the set_registered_model_alias(), delete_registered_model_alias(), and get_model_version_by_alias()
store methods
.
To get support with these implementations, please file a GitHub issue!
Support the
copy_model_version()
client API
Starting in
MLflow 2.9
, we plan to make
this store implementation
the default for the
copy_model_version()
client API. Our implementation invokes the
create_model_version()
store method with the model URI of the source model version as the
source
param. Please make sure that your
create_model_version()
method supports such model version URI sources. Furthermore, as we plan to link the model version copy to its source model version in UI via the
source
param being the source model version URI, you should make sure that when a model version copy is fetched, it returns model version URI as its
source
.
To consult us on supporting
copy_model_version()
, please file a GitHub issue!
Conclusion
Thanks so much for your attention and consideration! We’re excited to continue to work with the open source community to make MLflow an amazing tool for managing the machine learning lifecycle.
Reactions are currently unavailable
Metadata
Metadata
Assignees
jerrylian-db
Labels
stale
Type
No type
Projects
No projects
Milestone
No milestone
Relationships
None yet
Development
No branches or pull requests
Issue actions
Open in GitHub Copilot app
You can’t perform that action at this time.