"""Custom exceptions."""
from __future__ import annotations


class PropeAgentError(Exception):
    """Base error."""


class ProviderError(PropeAgentError):
    """LLM provider call failed."""


class WorkflowError(PropeAgentError):
    """LangGraph workflow error."""


class QualityGateBlocked(PropeAgentError):
    """Quality gate rejected the candidate."""
