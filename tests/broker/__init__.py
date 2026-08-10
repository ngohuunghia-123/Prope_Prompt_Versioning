"""Broker tests — against a real RabbitMQ 4.3, never against a fake (D-22).

Every property this package asserts is a property of the broker: a publisher
confirm arriving, a queue holding the arguments that were declared, a
redelivery after an unacknowledged consumer restart, an overflow rejection. A
fake at the aio-pika seam would assert the fake.

**A drain that acks and writes nothing looks healthy.** So nothing in this
package asks the drain what it did and believes the answer. Every assertion
about what landed is a direct query through ``migrate_engine`` — the owner role,
subject to no policy — and never through the code under test.
"""
