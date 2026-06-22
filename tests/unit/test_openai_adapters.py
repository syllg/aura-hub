from types import SimpleNamespace

import pytest

from app.adapters.embeddings import OpenAIEmbeddingAdapter
from app.adapters.llm import OpenAILLMAdapter


class FakeEmbeddingsResource:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[float(index)] * kwargs["dimensions"])
                for index, _ in enumerate(kwargs["input"])
            ]
        )


class FakeResponsesResource:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="Jawaban [chunk:test]")


@pytest.mark.asyncio
async def test_embedding_adapter_uses_locked_model_and_dimensions() -> None:
    client = SimpleNamespace(embeddings=FakeEmbeddingsResource())
    adapter = OpenAIEmbeddingAdapter(client, batch_size=1)  # type: ignore[arg-type]

    vectors = await adapter.embed_passages(["one", "two"])

    assert len(vectors) == 2
    assert all(len(vector) == 1536 for vector in vectors)
    assert all(
        call["model"] == "text-embedding-3-small" and call["dimensions"] == 1536
        for call in client.embeddings.calls
    )


@pytest.mark.asyncio
async def test_llm_adapter_uses_gpt4o_responses_api() -> None:
    client = SimpleNamespace(responses=FakeResponsesResource())
    adapter = OpenAILLMAdapter(client)  # type: ignore[arg-type]

    answer = await adapter.generate(instructions="grounded", prompt="question")

    assert answer == "Jawaban [chunk:test]"
    assert client.responses.calls == [
        {
            "model": "gpt-4o",
            "instructions": "grounded",
            "input": "question",
            "temperature": 0.0,
        }
    ]
