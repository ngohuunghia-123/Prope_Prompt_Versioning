"""INT-015 and INT-016 — this module's public in-process surface."""

from prope.provider_access.catalogue import get_model_catalogue
from prope.provider_access.dispatch import dispatch
from prope.provider_access.domain import (
    CatalogueEntry,
    CatalogueSource,
    DispatchError,
    DispatchResult,
    ErrorClass,
    Origin,
    Priority,
    Usage,
)

__all__ = [
    "CatalogueEntry",
    "CatalogueSource",
    "DispatchError",
    "DispatchResult",
    "ErrorClass",
    "Origin",
    "Priority",
    "Usage",
    "dispatch",
    "get_model_catalogue",
]
