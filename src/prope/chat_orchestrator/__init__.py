"""chat-orchestrator: the supervisor that fronts Prope's other agents.

The module's whole surface, in one place, so that a reader can see what it can do
before reading how. `warm_chat_agent` is what `prope.app`'s lifespan calls;
everything else is reached through `api.py`.
"""

from prope.chat_orchestrator.orchestrator import warm_chat_agent

__all__ = ["warm_chat_agent"]
