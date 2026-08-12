"""The OpenAI-compatible gateway (INT-022), as its own ASGI application (ADR-0050)."""

from prope.gateway.app import app, bind_sessionmaker, create_gateway_app

__all__ = ["app", "bind_sessionmaker", "create_gateway_app"]
