from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.config import get_settings


class LLMServiceError(RuntimeError):
    """Raised when the configured LLM service cannot produce an answer."""


# The chat route sends the final prompt as "Question:\n<question>\n\nRetrieved document excerpts:\n...".
_QUESTION_BLOCK = re.compile(r"\AQuestion:\n(?P<question>.*?)\n\nRetrieved document excerpts:", re.DOTALL)
_DIGIT = re.compile(r"\d")
_REASONING_WORDS = re.compile(
    r"\b(how much|how many|total|calculate|refund|premium|deadline|by when|what date|"
    r"when (?:must|will|does|do|did|is|are)|approve|eligible|eligibility|qualif\w*|"
    r"am i covered|are we covered|can (?:i|my|we)|would i|should i|cover stop|last week|yesterday|ago)\b",
    re.IGNORECASE,
)
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def needs_reasoning(question: str) -> bool:
    """Heuristic: questions with numbers, dates, amounts or eligibility/deadline wording benefit from thinking.

    Plain look-ups ("Who is the Chief Claims Officer?") are answered faster and just as well without it.
    """

    return bool(_DIGIT.search(question) or _REASONING_WORDS.search(question))


def _question_from_messages(messages: list[dict[str, str]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            match = _QUESTION_BLOCK.match(message.get("content") or "")
            return match.group("question").strip() if match else None
    return None


class OpenAICompatibleLLMClient:
    """Minimal async client for an OpenAI-compatible chat-completions API.

    For answer prompts it can switch the model's thinking mode on, only for questions that need reasoning
    (see needs_reasoning). Thinking is bounded by a token limit and a shorter timeout; if it fails, returns
    nothing, or runs too long, the client answers again in normal fast mode.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()

        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
        )
        self.transport = transport

        self.thinking_mode = getattr(settings, "llm_thinking_mode", "auto")
        self.thinking_timeout_seconds = float(getattr(settings, "llm_thinking_timeout_seconds", 75.0))
        self.thinking_max_tokens = int(getattr(settings, "llm_thinking_max_tokens", 3000))
        self.max_tokens = int(getattr(settings, "llm_max_tokens", 700))

        if self.timeout_seconds <= 0:
            raise ValueError("LLM timeout must be greater than zero.")
        if self.thinking_mode not in {"auto", "always", "never"}:
            raise ValueError("llm_thinking_mode must be 'auto', 'always' or 'never'.")

    def _should_think(self, messages: list[dict[str, str]]) -> bool:
        if self.thinking_mode == "never":
            return False
        question = _question_from_messages(messages)
        if question is None:
            return False  # not an answer prompt (for example the question-rewrite step)
        if self.thinking_mode == "always":
            return True
        return needs_reasoning(question)

    async def generate(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a response from a list of chat messages."""
        if not messages:
            raise ValueError("At least one chat message is required.")

        if self._should_think(messages):
            try:
                return await self._complete(
                    messages,
                    thinking=True,
                    max_tokens=self.thinking_max_tokens,
                    timeout_seconds=min(self.timeout_seconds, self.thinking_timeout_seconds),
                )
            except LLMServiceError:
                # Reasoning ran too long, was cut off, or the call failed: give a normal fast answer instead.
                pass

        return await self._complete(
            messages,
            thinking=False,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
        )

    async def _complete(
        self,
        messages: list[dict[str, str]],
        *,
        thinking: bool,
        max_tokens: int,
        timeout_seconds: float,
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        if thinking:
            # Recommended sampling for Qwen3 thinking mode; greedy decoding can loop without finishing.
            payload.update({"temperature": 0.6, "top_p": 0.95, "top_k": 20})
        else:
            payload["temperature"] = 0.0

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_seconds),
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise LLMServiceError(
                "The configured LLM service could not be reached or returned an HTTP error."
            ) from exc
        except ValueError as exc:
            raise LLMServiceError("The LLM service returned invalid JSON.") from exc

        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMServiceError("The LLM service returned an unexpected response format.") from exc

        if isinstance(answer, str):
            answer = _THINK_BLOCK.sub("", answer)
            if "<think>" in answer:  # reasoning was cut off before the answer started
                answer = ""

        if not isinstance(answer, str) or not answer.strip():
            raise LLMServiceError("The LLM service returned an empty answer.")

        return answer.strip()
