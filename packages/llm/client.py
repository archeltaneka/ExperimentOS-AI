from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from time import perf_counter
from typing import Protocol

from packages.config.env import load_environment


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


OllamaPostJson = Callable[[str, dict[str, object]], Awaitable[dict[str, object]]]


async def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    import asyncio

    return await asyncio.to_thread(_post_json_sync, url, payload)


def _post_json_sync(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMClientError(f"Ollama request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMClientError(f"Ollama request failed: {exc.reason}") from exc

    if not body:
        return {}
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise LLMClientError("Ollama response must be a JSON object")
    return parsed


def _join_ollama_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


class MockLLMClient:
    def __init__(
        self,
        *,
        answer: str = "Mock answer.",
        model: str = "mock",
        failure: Exception | None = None,
    ) -> None:
        self.answer = answer
        self.model = model
        self.failure = failure
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

        return LLMResponse(
            answer=self.answer,
            metrics=LLMMetrics(
                model=self.model,
                input_tokens=len((system_instruction + " " + prompt).split()),
                output_tokens=len(self.answer.split()),
                latency_ms=0.0,
            ),
        )


class OllamaLLMClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        post_json: OllamaPostJson = _post_json,
    ) -> None:
        load_environment()
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        self.post_json = post_json

    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str,
    ) -> LLMResponse:
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "system": system_instruction,
            "stream": False,
        }
        try:
            started_at = perf_counter()
            response = await self.post_json(
                _join_ollama_url(self.base_url, "/api/generate"),
                payload,
            )
            latency_ms = self._latency_ms(response, started_at)
        except LLMClientError:
            raise
        except Exception as exc:
            raise LLMClientError(str(exc)) from exc

        answer = str(response.get("response", "")).strip()
        status = response.get("status")
        if status == HTTPStatus.NOT_FOUND:
            raise LLMClientError(f"Ollama model {self.model!r} was not found")
        return LLMResponse(
            answer=answer,
            metrics=LLMMetrics(
                model=self.model,
                input_tokens=int(response.get("prompt_eval_count") or 0),
                output_tokens=int(response.get("eval_count") or 0),
                latency_ms=latency_ms,
            ),
        )

    def _latency_ms(self, response: dict[str, object], started_at: float) -> float:
        total_duration = response.get("total_duration")
        if isinstance(total_duration, int | float):
            return float(total_duration) / 1_000_000.0
        return (perf_counter() - started_at) * 1000.0


class OpenAILLMClient:
    def __init__(
        self,
        *,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
    ) -> None:
        load_environment()
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
