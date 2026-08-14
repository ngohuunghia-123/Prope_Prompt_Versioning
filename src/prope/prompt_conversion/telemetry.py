"""Soft Langfuse integration for prompt conversion."""

import os
from functools import lru_cache

from langfuse import Langfuse


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse | None:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        return None

    # Langfuse Python SDK v4 calls this base_url.
    # Keep compatibility with the LANGFUSE_HOST already used by Prope.
    base_url = (
        os.getenv("LANGFUSE_BASE_URL")
        or os.getenv("LANGFUSE_HOST")
    )

    if base_url:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
        )

    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
    )
