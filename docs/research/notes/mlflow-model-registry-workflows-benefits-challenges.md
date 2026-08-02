---
title: 'MLflow Model Registry: Workflows, Benefits & Challenges'
id: mlflow-model-registry-workflows-benefits-challenges
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:26.013280Z'
source: https://lakefs.io/blog/mlflow-model-registry/
source_domain: lakefs.io
fetched_at: '2026-08-02T03:12:26.004279Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 11.0
---

MLflow Model Registry: Workflows, Benefits & Challenges
Skip to content
Back to Blog
Best Practices
,
Machine Learning
MLflow Model Registry: Workflows, Benefits & Challenges
Amit Kesarwani
Last updated on February 13, 2025
Home
>
Blog
>
MLflow Model Registry: Workflows, Benefits & Challenges
Table of Contents
Watch how lakeFS data version control works
Watch Now
MLflow
is a popular solution for tracking experiments, managing models, and deploying them across several environments. One of the components of MLflow is Model Registry, a service that lets teams manage and track ML models and associated artifacts and provides a user interface for browsing them.
How does Model Registry work, and what
MLflow data versioning
capabilities does it provide? Continue reading to get all the essentials and best practices for extending data version control with the open-source solution lakeFS on top of MLflow.
What is MLflow Model Registry?
The Model Registry allows you to organize and monitor machine learning model versions during testing, quality assurance, and production stages. It was designed to help teams work together on the creation and implementation of models as well as monitor which models are being used in various environments. You can store and manage models, deploy them to various settings, and monitor their performance over time.
Model Registry has several components:
A Centralized Model Store is a single area where your MLflow models can be versioned, shared, and deployed consistently and efficiently.
A set of APIs for programmatically creating, reading, updating, and deleting models.
A graphical user interface (GUI) for manually viewing and managing models in the centralized model store.
Model Registry is one of MLflow’s four main parts:
Component
Description
MLflow Tracking
This component lets teams track and query experiments, tracking each experiment’s code, data, setup, and outcomes
MLflow Projects
By encapsulating the code independently of the platform, MLflow Projects enables teams to replicate experiments
MLflow Models
Machine learning models are deployed to a serving environment via MLflow Models
MLflow Model Registry
The Model Registry makes it possible to store, annotate, find, and manage models in one place
When should teams use Model Registry?
Model Registry comes in handy for several scenarios:
Monitoring several model iterations as they are created and implemented while working on a machine learning project.
Tracking which version of a machine learning model is used in each environment when you must deploy it to many environments.
Tracking and evaluating the performance of several model iterations over time and deciding which models to employ in production based on data.
Streamlining the deployment of models to a staging environment for testing or to a production environment.
Use Cases of MLflow Model Registry
Model Registration
As the name suggests, you can register an MLflow Model with the Model Registry. In addition to having a distinct name, a registered model also has tags, aliases, versions, and other metadata.
Version of the Model
There may be one or more versions of each model. When you add a new model to the Model Registry, it is added as version 1. The version number increases with each new model registered under the same model name. Model versions feature tags, such as pre_deploy_checks: “PASSED,” which might help track the model version’s properties.
Model Aliases
With model aliases, you can provide a specific version of a model with a named, mutable reference. You can use an alias to refer to a particular model version through the model registry API or a model URI by assigning the alias to that version.
Aliases help deploy models. For instance, you may designate a given alias for the model version meant for production traffic to target this alias in production workloads. Reassigning the champion alias to a different model version will allow you to upgrade the production traffic model.
Using tags, which are key-value pairs, you can label and group models and model versions according to their function or status.
Descriptions and Annotations
Using Markdown, you can annotate the top-level model and each version separately, adding a description and any pertinent details the team might find helpful, including the dataset used, algorithm descriptions, or approach.
Setting Up Model Registry Workflows
Let’s take a quick look at how you can set up model registry workflows via UI and API.
UI Workflow
Register a Model
You can register the logged MLflow model by opening the details page for the MLflow Run. In the Artifacts section, choose the model folder that contains the desired MLflow model.
A form will appear when you click the Register Model button. You can choose from two options at this point:
Create New Model, which generates a new model with your MLflow model as its initial version),
Select an Existing Registered Model, which registers your model under it as a new version from the Model dropdown menu on the form.
Locate Registered Models
How do you access your models once registered in the Model Registry?
Go to the Registered Models page to view your registered models and their corresponding model versions. To see the version generated from that model, navigate to the Artifacts part of your MLflow Runs details page, choose the model folder, and then select the model version located at the upper right corner.
Install and Arrange Models
Model aliases and tags can be used to deploy and arrange your models in the Model Registry. Like the one below, the overview page of your registered model is where you can specify aliases and tags for model versions. Clicking on the pencil symbol or Add link in the model version table will allow you to add or modify aliases and tags for that particular model version.
You can examine model version information on this page, including the creation timestamp, MLflow source run, and model signature. The aliases, tags, and description of the version can also be viewed and customized.
API Workflow
Another way to interact with the Model Registry is via the MLflow model flavor or MLflow Client Tracking API interface. You can register a model after all of your experiment runs or during an MLflow experiment run.
Here’s a quick overview of the steps involved in this approach.
Adding MLflow Models to the Registry
You can register a model in one of three programmatic ways:
Using mlflow.log_model() method
– If no registered model with the same name exists, the procedure registers a new model and produces Version 1. The method generates a new version if there is already a registered model with the same name.
Using mlflow.register_model() method (potentially as a backup)
– This registers a new model, generates Version 1, and returns a ModelVersion MLflow object if there isn’t already a registered model with the name. The method generates a new model version and returns the version object if there is already a registered model with the name.
Using create_registered_model()
– This method will issue a MlflowException if the model name already exists because a unique name is necessary when creating a new registered model.
Registry of Databricks Unity Catalog Models
Would you like to use the models from your Databricks Unity Catalog? If that’s the use case you’re after, you need to add the two environmental variables “DATABRICKS_HOST” and “DATABRICKS_TOKEN” and set the MLflow registry URI to “databricks-uc”.
If you use Databricks OAuth authentication, make sure to set the three environmental variables “DATABRICKS_HOST”, “DATABRICKS_CLIENT_ID”, and “DATABRICKS_CLIENT_SECRET.”
You’ll also need to use the Databricks shard token to access the Databricks unity catalog model registry.
Model Registry for OSS Unity Catalog
In the MLflow registry URI, enter the UC server address in the style “uc:http://localhost:8080” if you want to use an OSS Unity Catalog server as your Model Registry. Set the environmental variable “MLFLOW_UC_OSS_TOKEN” if your Unity catalog server is set up to log users in. Use a bearer token to access the OSS unity catalog model registry.
Deploy and Organize Models with Aliases and Tags
The
MLflow documentation
includes several examples demonstrating how to set, change, and remove aliases using the MLflow Client API. The section also shows how to add and remove model tags.
MLflow Model Fetching from the Model Registry
Once an MLflow model has been registered, you can retrieve it using mlflow..load_model(), or more generically, load_model(). The loaded model can be used for inference tasks like batch inference or for one-time predictions.
Simply include the version number as part of the model URI to retrieve a particular model version. You can also use an alias to retrieve a model version. The model version that is currently under the model alias will be retrieved if the model alias is specified in the model URI.
Keep in mind that you can modify model alias assignments without affecting your production code. The subsequent run of this snippet will automatically select the updated model version if the champion alias in the snippet above is reassigned to a different model version in the Model Registry. This enables you to separate your inference workloads from model deployments.
MLflow Model Promotion in Various Environments
Teams use distinct environments (usually dev, staging, and prod) with access controls in mature DevOps and MLOps workflows to facilitate rapid development without sacrificing production stability.
Access-controlled contexts for your MLflow models can be expressed using MLflow Authentication and registered models. For instance, you can make registered models that correspond to every possible combination of environment and business problems, and then set permissions appropriately.
You can promote MLflow models through the different environments for continuous integration and deployment as you refine them for your business problem.
MLflow recommends establishing automated procedures that train and register models in each environment for established production-grade configurations. Use CI/CD and source control tools to spread your machine learning code across environments and productionize the most recent version of a business problem.
Removing an MLflow Model
Deleting registered models or model versions cannot be undone, so think twice before using this method.
A registered model can be deleted in one of two ways: either all of its versions or just certain versions. Learn more in
this section of MLflow docs
.
Model Versioning and Management
For data scientists and machine learning engineers, MLOps is a lifesaver that allows them to concentrate on insights while quickly handling the compilation of all the results.
Version control facilitates monitoring environmental changes. Data, experimentation, analytical reporting, model tuning, and much more are all part of the machine learning process.
Model Registry component facilitates cooperative management of an MLflow model’s entire lifecycle. It offers stage transitions (from staging to production, for instance),
model versioning
, annotations, and model lineage (from which the model was generated via MLflow experiments and runs).
Access Management in MLflow Model Registry
Managing User Permissions and Roles
In MLflow, all users have READ as their default permission. The configuration file contains the option to modify it. Each user can be given permission to access specific resources.
Experiment and Registered Model are examples of supported resources. A user needs to have the necessary authorization in order to visit an API endpoint. If not, they will receive a 403 Forbidden answer.
MLflow offers REST APIs together with the AuthServiceClient client class to handle users and permissions. MLflow recommends instantiating AuthServiceClient using mlflow.server.get_app_client().
Common Challenges and Solutions For Data Versioning in MLflow
Version Control Scaling for Big Datasets
Because of the increasing storage and performance requirements, managing multiple versions of huge datasets can be challenging. The data versioning tool needs to be scalable enough to cover that.
Data Versioning Automation
Unlike code, datasets can be large, dynamic, and challenging to monitor efficiently over time. To automate the tracking of data lineage, modifications, and dependencies, it’s key to integrate technologies that manage metadata, preprocessing procedures, transformations, and dataset versions. Automation efforts are often further complicated by managing version conflicts and scalability for large datasets.
Managing Modifications to Data Schemas
Data schema versioning can become challenging because you have to manage dependencies and conflicts between various sources, targets, and pipelines. Additionally, you need to consider whether transformation or backfilling is required and how changes to the data structure may impact already-existing data.
It’s also crucial to balance data schema evolution and stability, particularly when handling frequent or complex changes that can interfere with your data warehouse or downstream applications.
Challenges with Tooling and Integration
Maintaining consistent data flows and version tracking across the data lifecycle requires careful design and execution when integrating data versioning with existing data pipelines, especially
ETL (Extract, Transform, Load) processes
.
Best Practices for MLflow Model Registry
Test Of Staging Environments
Model Staging is one of the features that MLflow offers. Before going live in the production environment, models can be tested and re-adjusted in a staging environment, which is a copy of the real one.
In the machine learning lifecycle, model staging is a great practice because it removes errors and potential failures from the code so that it can function flawlessly in a production or customer-facing setting.
Centralize The Tracking Of Experiments
By centralizing the tracking information across users and systems, MLflow provides a straightforward method of transforming experiment tracking, one of the essential MLOps requirements.
Using the same experiment name, the tracking API can collect data from other users and immediately log details from Jupyter notebooks. The information is then kept in a shared table for easy comparison and analysis.
Use Specific Pipeline Parameter Storage
Over time, the parameters included in the MLflow Tracking module may accumulate to an excessive amount that may be difficult to control and understand.
Setting aside specific cloud storage for smooth tracking is crucial to overcoming the challenges of maintaining artifacts like metadata, hyperparameters, databases, or metrics, particularly in the cloud-based production environment.
Adjust The Entire Pipeline
Tune the entire machine learning pipeline rather than just individual or isolated modules to leverage the potential of various hyperparameter combinations fully. This implies that many combinations will be produced, all of which may be easily monitored, saved, and examined using MLflow’s centralized storage and tracking API.
Create Pipelines for Automating Version Control
To enable consistent and reliable data processing and delivery, Write-Audit-Publish and Deployment makes sure that updates and changes to data pipelines are automatically tested, integrated, and deployed to production.
Data engineering includes automated ETL code testing, data structure validation,
data quality monitoring
, anomaly detection, delivering updated data models to production, and ensuring databases or data warehouses are configured correctly.
MLflow integration with lakeFS
Any machine learning project involves a massive volume of data. Teams need a reliable data versioning solution for both your ML models and data in general. Numerous data version control systems are limited in their functionality and ability to integrate with other ecosystem technologies. However, the open-source project lakeFS fills this void.
As datasets grow to billions of files and petabytes of data, it allows them to manage their data using Git-like processes (commit, merge, etc.). lakeFS allows teams to apply software engineering best practices to data and models, turning your entire bucket into a code repository by adding a management layer, like S3, to your object storage.
A unique method for effectively maintaining multiple versions of your machine learning datasets and models without duplicating the data is lakeFS (zero clone copies).
Conclusion
Data versioning is essential to machine learning workflows, as models are updated and iterated on a frequent basis. Reliable methods for monitoring these versions come as part of MLflow’s Model Registry and other data versioning tools, which enable users to keep track of modifications, go back to earlier iterations, and effectively compare different models.
Do you use a data lake? To learn all the best practices for a seamless data versioning experience, take a closer look at
Databricks MLflow
.
The Control Plane for
AI-Ready Data
Versioned. Reproducible. Compliant.
Try lakeFS
Related Articles
Best Practices
|
Data Engineering
|
Machine Learning
|
Product
Announcing the lakeFS Summer 2026 Release: Governance for AI-Ready Data
John Noonan
July 28, 2026
Read More
Best Practices
|
Data Engineering
|
Machine Learning
|
Thought Leadership
Laying the Data Foundation for AI Success
Iddo Avneri
July 27, 2026
Read More
Best Practices
|
Data Engineering
|
Machine Learning
|
Product
Mount Cloud Storage as Local Drive for Faster ML & Analytics Workflows
Yahli Ramberg
July 23, 2026
Read More
We use cookies to improve your experience and understand how our site is used.
Learn more in our
Privacy Policy
Pick up the
Slack
with lakeFS
Join our community of experts:
introduce
yourself,
share
your knowledge and
discover
best practices from fellow peers
Join us