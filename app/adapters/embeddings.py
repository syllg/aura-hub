from __future__ import annotations

from typing import Protocol

from openai import AsyncOpenAI


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class OpenAIEmbeddingAdapter:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        batch_size: int = 64,
    ) -> None:
        self.client = client
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts[start : start + self.batch_size],
                dimensions=self.dimensions,
            )
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda x: x.index))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=[text],
            dimensions=self.dimensions,
        )
        return response.data[0].embedding
