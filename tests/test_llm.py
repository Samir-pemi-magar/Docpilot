import httpx
import pytest

from app.services.llm import (
    LLMServiceError,
    OpenAICompatibleLLMClient,
)


@pytest.mark.asyncio
async def test_llm_client_sends_chat_request_and_returns_answer():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "  The office opens at 9 AM.  ",
                            "reasoning_content": "This must not be returned.",
                        }
                    }
                ]
            },
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1/",
        api_key="test-secret",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    answer = await client.generate(
        [
            {"role": "system", "content": "Use the supplied context."},
            {"role": "user", "content": "When does the office open?"},
        ]
    )

    assert answer == "The office opens at 9 AM."
    assert captured["url"] == "http://llm.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-secret"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }
    assert len(captured["payload"]["messages"]) == 2
    assert "reasoning_content" not in answer


@pytest.mark.asyncio
async def test_llm_client_works_without_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Answer"}}]},
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        api_key="",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    assert await client.generate(
        [{"role": "user", "content": "Question"}]
    ) == "Answer"


@pytest.mark.asyncio
async def test_llm_client_reports_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMServiceError, match="HTTP error"):
        await client.generate([{"role": "user", "content": "Question"}])


@pytest.mark.asyncio
async def test_llm_client_rejects_empty_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "   "}}]},
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMServiceError, match="empty answer"):
        await client.generate([{"role": "user", "content": "Question"}])
