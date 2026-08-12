"""call-ledger — every completed call recorded off the response path.

A sink. ``dependencies: []`` and ``outputs: []`` are this module's defining
property: nothing here may import another bounded context, and no foreign key
leaves the ``ledger`` schema. ``workspace_id``, ``prompt_id``, ``version_id``
and ``provider_config_id`` are values, not references — which is what lets the
audit trail survive independently of the registry's current state.
"""
