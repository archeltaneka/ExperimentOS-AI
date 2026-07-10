from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from packages.config.env import get_ollama_base_url

GEMINI_LLM_MODEL = "gemini-3.5-flash"
OLLAMA_LLM_MODEL = "qwen2.5:7b"


class LLMClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMMetrics:
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


@dataclass(frozen=True)
class LLMResponse:
    answer: str
    metrics: LLMMetrics


class LLMClient(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str,
    ) -> LLMResponse:
        pass


class MockLLMClient:
    def __init__(
        self,
        *,
        answer: str = "Mock answer.",
        model: str = "mock",
        failure: Exception | None = None,
        response_builder: Any | None = None,
    ) -> None:
        self.answer = answer
        self.model = model
        self.failure = failure
        self.response_builder = response_builder
        self.calls = 0
        self.last_prompt = ""
        self.last_system_instruction = ""

    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str,
    ) -> LLMResponse:
        self.calls += 1
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        if self.failure is not None:
            raise self.failure

        answer = self.answer
        if self.response_builder is not None:
            answer = str(self.response_builder(prompt, system_instruction))

        return LLMResponse(
            answer=answer,
            metrics=LLMMetrics(
                model=self.model,
                input_tokens=len((system_instruction + " " + prompt).split()),
                output_tokens=len(answer.split()),
                latency_ms=0.0,
            ),
        )


class OpenAILLMClient:
    def __init__(
        self,
        *,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise LLMClientError("OpenAI LLM client requires the 'openai' package") from exc

        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str,
    ) -> LLMResponse:
        try:
            started_at = perf_counter()
            response = await self.client.responses.create(
                model=self.model,
                input=f"{system_instruction}\n\n{prompt}",
            )
            latency_ms = (perf_counter() - started_at) * 1000.0
        except Exception as exc:
            raise LLMClientError(str(exc)) from exc

        answer = getattr(response, "output_text", "").strip()
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return LLMResponse(
            answer=answer,
            metrics=LLMMetrics(
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            ),
        )


class GeminiLLMClient:
    def __init__(
        self,
        *,
        model: str = GEMINI_LLM_MODEL,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        if client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise LLMClientError(
                    "Gemini LLM client requires the 'google-genai' package"
                ) from exc
            client = genai.Client(api_key=api_key)
        self.client = client

    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str,
    ) -> LLMResponse:
        try:
            started_at = perf_counter()
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=f"{system_instruction}\n\n{prompt}",
            )
            latency_ms = (perf_counter() - started_at) * 1000.0
        except Exception as exc:
            raise LLMClientError(str(exc)) from exc

        usage = _response_value(response, "usage_metadata", default=None)
        return LLMResponse(
            answer=str(_response_value(response, "text", default="")).strip(),
            metrics=LLMMetrics(
                model=self.model,
                input_tokens=int(_response_value(usage, "prompt_token_count", default=0) or 0),
                output_tokens=int(_response_value(usage, "candidates_token_count", default=0) or 0),
                latency_ms=latency_ms,
            ),
        )


class OllamaLLMClient:
    def __init__(
        self,
        *,
        model: str = OLLAMA_LLM_MODEL,
        base_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        base_url = base_url or get_ollama_base_url()
        if client is None:
            try:
                from ollama import AsyncClient
            except ImportError as exc:
                raise LLMClientError("Ollama LLM client requires the 'ollama' package") from exc
            client = AsyncClient(host=base_url) if base_url else AsyncClient()
        self.client = client

    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str,
    ) -> LLMResponse:
        try:
            started_at = perf_counter()
            response = await self.client.generate(
                model=self.model,
                prompt=prompt,
                system=system_instruction,
                options={"temperature": 0},
            )
            latency_ms = (perf_counter() - started_at) * 1000.0
        except Exception as exc:
            raise LLMClientError(str(exc)) from exc

        answer = _response_value(response, "response", default="").strip()
        input_tokens = int(_response_value(response, "prompt_eval_count", default=0) or 0)
        output_tokens = int(_response_value(response, "eval_count", default=0) or 0)
        return LLMResponse(
            answer=answer,
            metrics=LLMMetrics(
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            ),
        )


def _response_value(response: Any, key: str, *, default: Any) -> Any:
    if isinstance(response, dict):
        return response.get(key, default)
    return getattr(response, key, default)
