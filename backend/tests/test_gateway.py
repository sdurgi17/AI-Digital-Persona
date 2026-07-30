import json

import pytest
from fastapi.testclient import TestClient

import app.routers.llm_gateway as gateway
from app.config import get_settings
from app.main import app

SECRET = "test-secret-123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOM_LLM_SHARED_SECRET", SECRET)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    async def fake_stream(conn, messages, include_system_prompt):
        assert include_system_prompt is False
        for part in ["Hello ", "world"]:
            yield part

    monkeypatch.setattr(gateway, "stream_persona_reply", fake_stream)
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_401_without_bearer(client):
    resp = client.post("/v1/chat/completions", json={"messages": []})
    assert resp.status_code == 401


def test_401_with_wrong_bearer(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": []},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_sse_framing_exact(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
        headers={"Authorization": f"Bearer {SECRET}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = [e for e in resp.text.split("\n\n") if e.strip()]
    assert all(e.startswith("data: ") for e in events)
    assert events[-1] == "data: [DONE]"

    payloads = [json.loads(e[6:]) for e in events[:-1]]
    assert all(p["object"] == "chat.completion.chunk" for p in payloads)
    assert payloads[0]["choices"][0]["delta"].get("role") == "assistant"
    text = "".join(p["choices"][0]["delta"].get("content") or "" for p in payloads)
    assert text == "Hello world"
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"


def test_non_streaming_json(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
        headers={"Authorization": f"Bearer {SECRET}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Hello world"
