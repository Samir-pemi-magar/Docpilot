from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class LLMServiceError(RuntimeError):
    """Raised when the configured LLM service cannot produce an answer."""


class OpenAICompatibleLLMClient:
    """Minimal async client for an OpenAI-compatible chat-completions API."""

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

        self.base_url = (
            base_url or settings.llm_base_url
        ).rstrip("/")
        self.api_key = (
            api_key if api_key is not None else settings.llm_api_key
        )
        self.model = model or settings.llm_model
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.llm_timeout_seconds
        )
        self.transport = transport

        if self.timeout_seconds <= 0:
            raise ValueError("LLM timeout must be greater than zero.")

    async def generate(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a response from a list of chat messages."""
        if not messages:
            raise ValueError("At least one chat message is required.")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
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
                "The configured LLM service could not be reached "
                "or returned an HTTP error."
            ) from exc
        except ValueError as exc:
            raise LLMServiceError(
                "The LLM service returned invalid JSON."
            ) from exc

        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMServiceError(
                "The LLM service returned an unexpected response format."
            ) from exc

        if not isinstance(answer, str) or not answer.strip():
            raise LLMServiceError(
                "The LLM service returned an empty answer."
            )

        return answer.strip()
