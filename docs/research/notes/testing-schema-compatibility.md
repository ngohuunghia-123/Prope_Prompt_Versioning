---
title: Testing Schema Compatibility
id: testing-schema-compatibility
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:20.088309Z'
source: https://developer.confluent.io/courses/schema-registry/schema-compatibility/
source_domain: developer.confluent.io
fetched_at: '2026-08-02T03:12:20.081308Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 13.0
---

Testing Schema Compatibility
Enhance your career, get your certificate as a Data Streaming Engineer |
Get your Certificate
‹ Back to
courses
View Transcript
course
:
Schema Registry 101
Testing Schema Compatibility
5 min
In this final module, you will learn about Schema compatibility, the different settings you have at your disposal, and how to make use of them.
Expectations of Object Structure
Producer and consumer clients have expectations of the structure of the object they’re working with. Take the Foo class, for example. It has four fields: a long, double, and two strings.
Imagine for a moment that the development team responsible for getting the data into Kafka feels that the UUID field is not useful anymore. They decide to update the object structure and remove the UUID field.
Unexpected Changes May Cause Exceptions
The changes are made and the producer application starts to send the updated objects into Kafka. The consumer application receives the updated objects, expects the UUID field to be present, and in response to its absence throws an exception, forcing the application to shut down.
Analysis quickly discovers the object structure changed, which causes the new schema to be incompatible with the previous schema. What is needed is the means to verify compatibility between different schema versions prior to their being implemented in production so this type of exception can be prevented.
Schema Compatibility
Schema Registry offers compatibility verification. The available compatibility modes and associated checks establish guardrails that guide you to safely update schemas and allow you to keep your clients operational as they are updated with the changes.
Schema Registry validates schema changes at the time they are registered based upon the compatibility setting. The compatibility checks are done on a per subject basis. As we saw earlier in the course, subject-name remains the same even when a schema evolves, so it’s a consistent value to use for compatibility checks.
In this example, a simple check would let you know ahead of time if the new version of the schema being used by the producer is compatible with the previous version of the schema being used by the consumer. In this case, the check would not have passed due to the missing default value and you would know to update the consumer to use the new schema prior to updating the producer.
Schema Compatibility Modes
The three primary compatibility modes are backwards, which is the default setting, forward, and full.
With all three of these modes, the associated test verifies the compatibility of a schema being registered with its immediate predecessor.
Note that it is also possible to set the compatibility mode to none which results in no compatibility check being done when a new schema is registered.
Schema Compatibility Example
In this example, if the compatibility mode is backward, forward, or full, when version 3 is registered, Schema Registry will only verify that it is compatible with version 2. Compatibility with other previous versions is not verified.
Transitive Schema Compatibility Modes
There are also three transitive modes that are extensions of the three primary modes. These modes extend the compatibility requirement to all previous or future schema versions.
Transitive Schema Compatibility Example
The difference with transitive compatibility is that the latest version of a schema you just updated is verified to be compatible with all previous versions, not just the immediate previous one.
Now let’s review how each of the three compatibility modes work. Transitive versions are not discussed since they follow the exact same rules, they just go back to all previous ones.
Backward Compatibility Illustrated
With backward compatibility you can delete fields from a schema and add fields as long as they have a default value.
The order of updating your clients is to update the consumer clients first.
In this example the schema is evolved by removing
field_A
and adding
NewField
that has a default value associated with it.
By updating the consumer client first, if a producer using the previous schema sends records to Kafka the updated consumer client will continue to work fine.
It will ignore the deleted
field_A
on the record and use the default value provided for
NewField
.
Now let’s move on to forward compatibility.
Forward Compatibility Illustrated
With forward compatibility you can delete fields that have a default and add new fields.
In this case, you update the producer clients first.
Now if you have a consumer you haven’t updated yet, it will continue to operate and use the default value for the field that was deleted and simply ignore the newly added field.
Full Compatibility Illustrated
With full compatibility every field in the schema has a default value, so the order of updating clients doesn’t matter—with either order both old and new consumers will continue to work properly.
Schema Compatibility Considerations
This table summarizes the compatibility matrix for Schema Registry.
With Backward compatibility you can delete fields and add fields with default values and you update the consumer clients first.
With Forward compatibility you can delete fields with default values and add new fields. You need tol update your producer clients first under forward compatibility.
With Full compatibility, both deleted or added fields must have a default value. Since every change to the schema has a default value, the order in which you update your clients doesn’t matter.
Setting Schema Compatibility
Now that we’ve covered the different compatibility levels, let’s have a quick look at how you would set the level for a schema subject.
It’s important to note that you can set compatibility at the subject level, so it’s possible to have schemas with different compatibility levels.
This first example illustrates how to set the compatibility level with the Confluent CLI. Note that the security configs were left off for clarity.
This next example uses the Schema Registry REST command.
This last example sets the schema compatibility using the Gradle plugin.
Checking a Schema for Compatibility
Finally, you can check if the changes you made to a schema are compatible with the subject and current compatibility setting.
This first example does this check using the Confluent CLI.
This second example does this check using the Schema Registry REST API.
This last example checks using the Schema Registry Gradle plugin configuration.
With that, we’ve wrapped up the final schema registry course module and you should now know the options that you have to validate your schemas and keep them compatible as they evolve over time.
Do you have questions or comments? Join us in the
#developer-confluent-io
community Slack channel to engage in discussions with the creators of this content.
Previous
Next
Use the promo code SCHEMA101 & CONFLUENTDEV1 to get $25 of free Confluent Cloud usage and skip credit card entry.
Get Started
Get started with Confluent Cloud
Try free
Modules:
Start from lesson 1
Total
11
Key Concepts of a Schema Registry
7 min
Hands On: Establish Client Connectivity to Confluent Cloud
2 min
The Schema Workflow
4 min
Hands On: Configure, Build and Register Protobuf and Avro Schemas
1 min
Working with Schema Formats
5 min
Managing Schemas
5 min
Integrating Schema Registry with Client Applications
6 min
Hands On: Integrate Schema Registry with Clients
1 min
Understanding Schema Subjects
4 min
Testing Schema Compatibility
5 min
Hands On: Evolve Existing Schemas
1 min
Related Resources
Blog
Schemas, Contracts, and Compatibility
Documentation
Schema Evolution and Compatibility
Testing Schema Compatibility
Hi, I'm Danica Fine. In this final module of our Schema Registry Course, we'll cover schema compatibility, the different settings you have at your disposal, and how to make use of them. Producer and consumer clients have expectations regarding the structure of the object they're working with. Take the Foo class, for example. It has four fields, a long, a double, and two strings. Imagine for a moment that the development team responsible for getting the data into Kafka feels that the UUID field isn't useful anymore. They decide to update the object structure and remove the UUID field. The changes are made and the producer application begins sending the updated objects into Kafka. But on the consumer side of things, the consumer receives the updated objects, expects the UUID field to be present, and in response to its non-existence, throws an exception, forcing the application to shut down. That's obviously no good. It's easy to see that the object structure has changed, causing the new schema to be incompatible with the previous schema. What we need in this situation is the means to verify compatibility between different schema versions prior to their being implemented in production, so that this type of exception can be prevented. Thankfully, Schema Registry does exactly this sort of compatibility verification. The available compatibility modes and associated checks establish guardrails that guide you to safely update schemas and allow you to keep your clients operational as they're updated. Schema Registry validates schema changes on a per-subject basis at the time they're registered based on the compatibility setting you choose. As we saw earlier in the course, subject name remains the same even when a schema evolves, so it's a consistent value to use for compatibility checks. Going back to our example, a simple check could have let us know ahead of time if the new version of the schema being used by the producer is compatible with the previous version being used by the consumer. The compatibility check wouldn't have passed due to the missing default value. So we would know to update the consumer to use the new schema prior to updating the producer. The three primary compatibility modes are backwards, which is the default setting, forward, and full. Note that it is also possible to set the compatibility mode to none which results in no compatibility check being done when a new schema is registered. Regardless of which mode we decide to use, the associated check compares the schema being registered with its immediate predecessor. When version 3 is registered, Schema Registry will only verify that it is compatible with version 2. Compatibility with other previous versions is not verified by default but there are also three transitive modes that are extensions of the three primary modes. These modes extend the compatibility requirement to all previous or future schema versions. The difference with transitive compatibility is that the latest version of schema that's just been updated is verified to be compatible with all previous versions, not just the immediately previous one. Now let's review how each of the three compatibility modes work. We won't discuss the transitive versions as they follow the exact same rules, they just go back to all previous schemas. With backwards compatibility, you can delete fields from a schema and add fields, as long as they have a default value. When you do this, you should update your consumer clients first. In this example, you've evolved a schema by removing field_A and adding NewField that has a default value associated with it. By updating the consumer client first, if a producer using the old schema sends records to Kafka, the updated consumer client will continue to work just fine. It will ignore the deleted field_A on the record and use the default value provided for NewField. With forward compatibility, you can delete fields that have a default and add new fields. In this case, you'll want to update your producer clients first. In the event that you have a consumer you haven't updated yet, it will continue to operate since it will just use the default value for the field that was deleted, and ignore the newly added field. And finally, with full compatibility, every field in the schema has a default value. So the order of updating clients doesn't matter. Regardless of the order, both old and new consumers will continue to work properly. All right, to drive this home, here's a table summarizing the compatibility matrix for Schema Registry. With backward compatibility, you can delete fields and add fields with default values, and you'll want to update the consumer clients first. With forward compatibility, you can delete fields with default values and add new fields. You'll want to update your producer clients first. With full compatibility, both deleted or added fields must have a default value. Since every change to the schema has a default, the order in which you update your clients doesn't matter. Now that we've covered the different compatibility levels, let's have a quick look at how you would set the level for a schema subject. It's important to note that you can set compatibility at the subject level, so it's possible to have schemas with different compatibility levels. First, here's how you can set compatibility level with the Confluent CLI. Note that we've left off the security configs for clarity. The second example uses the Schema Registry REST command. And this final example sets the schema compatibility using the Gradle plugin. Finally, you can check if the changes you've made to a schema are compatible with the subject and current compatibility setting. Again, here's an example doing this check using the Confluent CLI, as well as one using the Schema Registry REST API. And a final example, showing you how to do the check using the Schema Registry Gradle plugin configuration. And with that, we've wrapped up the final Schema Registry Course module, and you should now know the options that you have to validate your schemas and keep them compatible as they evolve over time. Join me in our final hands-on, where you'll see how to evolve and validate schemas on your own.
Be the first to get updates and new content
We will only share developer content and updates, including notifications when new content is added. We will never send you sales emails.
🙂
By subscribing, you understand we will process your personal information in accordance with our
Privacy Statement.
Feedback