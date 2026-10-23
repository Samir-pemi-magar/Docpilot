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


# ---------------------------------------------------------------- selective thinking

import json as _json

from app.services.llm import needs_reasoning


def _answer_prompt(question: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Use the excerpts."},
        {"role": "user", "content": f"Question:\n{question}\n\nRetrieved document excerpts:\n[Source 1] text"},
    ]


def _ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_needs_reasoning_flags_numbers_dates_and_eligibility_but_not_plain_lookups():
    for question in [
        "I'm 23 and have Comprehensive motor insurance. What deductible do I pay?",
        "Can my father buy travel insurance?",
        "I bought Home Premium last week and my house just flooded. Am I covered?",
        "How much is a premium for a motorbike?",
        "When must ESI decide?",
    ]:
        assert needs_reasoning(question), question
    for question in [
        "Who is the Chief Claims Officer?",
        "What does Comprehensive Plus give me that Comprehensive doesn't?",
        "How long do I have to report a car theft?",
        "What's the difference between a deductible and an excess?",
    ]:
        assert not needs_reasoning(question), question


@pytest.mark.asyncio
async def test_reasoning_question_uses_thinking_with_recommended_sampling_and_bigger_budget():
    seen = []

    def handler(request):
        seen.append(_json.loads(request.content))
        return _ok("<think>work it out</think>You pay $1,540.")

    client = OpenAICompatibleLLMClient(base_url="http://llm.test/v1", model="m", transport=httpx.MockTransport(handler))
    answer = await client.generate(_answer_prompt("I have a $10,000 hospital bill on Gold. How much do I pay?"))

    assert answer == "You pay $1,540."
    assert len(seen) == 1
    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": True}
    assert seen[0]["max_tokens"] == 3000
    assert seen[0]["temperature"] == 0.6 and seen[0]["top_p"] == 0.95


@pytest.mark.asyncio
async def test_plain_lookup_stays_fast_without_thinking():
    seen = []

    def handler(request):
        seen.append(_json.loads(request.content))
        return _ok("Rohan Mehta.")

    client = OpenAICompatibleLLMClient(base_url="http://llm.test/v1", model="m", transport=httpx.MockTransport(handler))
    await client.generate(_answer_prompt("Who is the Chief Claims Officer?"))

    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert seen[0]["max_tokens"] == 700 and seen[0]["temperature"] == 0.0


@pytest.mark.asyncio
async def test_empty_thinking_answer_falls_back_to_a_fast_answer():
    seen = []

    def handler(request):
        payload = _json.loads(request.content)
        seen.append(payload["chat_template_kwargs"]["enable_thinking"])
        return _ok("<think>still going and going") if payload["chat_template_kwargs"]["enable_thinking"] else _ok("Fast answer.")

    client = OpenAICompatibleLLMClient(base_url="http://llm.test/v1", model="m", transport=httpx.MockTransport(handler))
    answer = await client.generate(_answer_prompt("What refund do I get after 146 days on $800?"))

    assert answer == "Fast answer."
    assert seen == [True, False]


@pytest.mark.asyncio
async def test_thinking_timeout_falls_back_to_a_fast_answer():
    seen = []

    def handler(request):
        payload = _json.loads(request.content)
        seen.append(payload["chat_template_kwargs"]["enable_thinking"])
        if payload["chat_template_kwargs"]["enable_thinking"]:
            raise httpx.ReadTimeout("too slow", request=request)
        return _ok("Fast answer.")

    client = OpenAICompatibleLLMClient(base_url="http://llm.test/v1", model="m", transport=httpx.MockTransport(handler))
    assert await client.generate(_answer_prompt("When must ESI decide on a claim sent on 6 December 2027?")) == "Fast answer."
    assert seen == [True, False]


@pytest.mark.asyncio
async def test_non_answer_prompts_never_think_and_mode_never_disables_thinking(monkeypatch):
    seen = []

    def handler(request):
        seen.append(_json.loads(request.content)["chat_template_kwargs"]["enable_thinking"])
        return _ok("ok")

    client = OpenAICompatibleLLMClient(base_url="http://llm.test/v1", model="m", transport=httpx.MockTransport(handler))
    await client.generate([{"role": "user", "content": "Rewrite this follow-up with 3 details: and the day after?"}])
    client.thinking_mode = "never"
    await client.generate(_answer_prompt("What refund do I get after 146 days on $800?"))
    client.thinking_mode = "always"
    await client.generate(_answer_prompt("Who is the Chief Claims Officer?"))
    assert seen == [False, False, True]
