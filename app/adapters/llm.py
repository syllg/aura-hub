from __future__ import annotations

from typing import Protocol

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class LLMProvider(Protocol):
    model: str

    async def generate(self, *, instructions: str, prompt: str) -> str: ...


class OpenAILLMAdapter:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.0,
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature

    async def generate(self, *, instructions: str, prompt: str) -> str:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type(
                (
                    APIConnectionError,
                    APITimeoutError,
                    RateLimitError,
                    InternalServerError,
                )
            ),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                response = await self.client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=prompt,
                    temperature=self.temperature,
                )
                answer = response.output_text.strip()
                if not answer:
                    raise RuntimeError("OpenAI returned an empty answer")
                return answer
        raise RuntimeError("OpenAI generation failed")
