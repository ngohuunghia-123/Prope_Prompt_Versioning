"""This module's view of the shared Langfuse client.

The client itself moved to `prope.app_agent.telemetry` when `prompt_search`
became the second agent that needed it — see that module for why it lives beside
the app-owned LM rather than inside a feature module. This re-export stays so
that `prompt_conversion`'s own files keep importing from their own package.
"""

from prope.app_agent.telemetry import flush_langfuse, get_langfuse

__all__ = ["flush_langfuse", "get_langfuse"]
