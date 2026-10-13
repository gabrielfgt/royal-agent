import pytest
from fastapi.testclient import TestClient

from sdr.api import chat
from sdr.api.app import app

EXPECTED_TAGS = {"chat", "painel", "leads", "agenda", "imóveis", "agente", "integrações", "infra"}
PUBLIC_PATHS = {"/api/chat/stream", "/api/chat/audio", "/api/chat/{session_id}/messages", "/api/health"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return app.openapi()


def operations(spec: dict):
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            yield path, method, operation


def test_schema_generates_with_tags(spec):
    assert spec["info"]["title"].startswith("Royal SDR")
    assert {tag["name"] for tag in spec["tags"]} == EXPECTED_TAGS
    assert all(set(operation["tags"]) <= EXPECTED_TAGS for _, _, operation in operations(spec))


def test_security_schemes(spec):
    schemes = spec["components"]["securitySchemes"]
    assert schemes["TokenPainel"] == {**schemes["TokenPainel"], "type": "http", "scheme": "bearer"}
    assert schemes["CronSecret"] == {**schemes["CronSecret"], "type": "http", "scheme": "bearer"}
    assert schemes["TelegramWebhookSecret"]["type"] == "apiKey"
    assert schemes["TelegramWebhookSecret"]["name"] == "X-Telegram-Bot-Api-Secret-Token"


def test_protected_routes_declare_security(spec):
    for path, method, operation in operations(spec):
        if path in PUBLIC_PATHS:
            assert "security" not in operation, (method, path)
        else:
            assert operation.get("security"), (method, path)
            assert "401" in operation["responses"], (method, path)


def test_every_route_is_documented(spec):
    for path, method, operation in operations(spec):
        assert operation.get("summary"), (method, path)
        assert operation.get("description"), (method, path)


@pytest.mark.parametrize("path", ["/api/chat/stream", "/api/chat/audio"])
def test_chat_streams_are_server_sent_events(spec, path):
    response = spec["paths"][path]["post"]["responses"]["200"]
    content = response["content"]["text/event-stream"]
    assert content["schema"] == {"$ref": "#/components/schemas/ChatStreamEvent"}
    assert "event: reply" in content["example"]
    assert "429" in spec["paths"][path]["post"]["responses"]


def test_stream_event_models_are_published(spec):
    schemas = spec["components"]["schemas"]
    for name in ("ReplyFrame", "AudioFrame", "NoticeFrame", "TranscriptFrame", "LeadFrame", "PausedFrame", "DoneFrame"):
        assert name in schemas
    assert set(schemas["ChatStreamEvent"]["discriminator"]["mapping"]) == {
        "reply",
        "audio",
        "notice",
        "transcript",
        "lead",
        "paused",
        "done",
    }


def test_sse_response_media_type():
    async def body():
        yield chat._sse("done", {})

    response = chat._sse_response(body())
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"


def test_docs_pages_are_served():
    client = TestClient(app)
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/redoc").status_code == 200
    assert client.get("/api/openapi.json").json()["openapi"].startswith("3.")
