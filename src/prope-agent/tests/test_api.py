"""Tests for the FastAPI surface."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from prope_agent.api import _create_app
from prope_agent.providers import MockProvider


def test_healthz_and_readyz():
    app = _create_app(provider=MockProvider())
    with TestClient(app) as client:
        r1 = client.get("/healthz")
        r2 = client.get("/readyz")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["provider"] == "mock"


def test_optimize_round_trip():
    app = _create_app(provider=MockProvider())
    with TestClient(app) as client:
        r = client.post(
            "/optimize",
            json={"prompt": "You are a helpful assistant."},
        )
        assert r.status_code == 202
        wf_id = r.json()["workflow_id"]

        # Background task — wait until finished.
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            gr = client.get(f"/workflows/{wf_id}")
            if gr.json().get("finished_at"):
                break
            asyncio.sleep(0.1) if False else None  # TestClient is sync; rely on polling
            import time
            time.sleep(0.2)

        gr = client.get(f"/workflows/{wf_id}")
        body = gr.json()
        assert body["stage"] == "explained"
        assert body["final_prompt"]
        assert "Constraints" in body["final_prompt"]
