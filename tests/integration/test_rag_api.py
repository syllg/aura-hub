from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.api.dependencies import get_rag_service
from app.core.config import Settings
from app.main import create_app
from app.repositories.document_repository import DocumentRepository
from app.services.document_parser import DocumentParser
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService


class FakeEmbeddingAdapter:
    model = "text-embedding-3-small"
    dimensions = 1536

    @staticmethod
    def _vector(text: str) -> list[float]:
        lowered = text.lower()
        vector = [0.0] * 1536
        if any(term in lowered for term in ("bonus", "target", "insentif")):
            vector[0] = 1.0
        elif any(term in lowered for term in ("absen", "absensi", "terlambat")):
            vector[1] = 1.0
        elif "cuti" in lowered:
            vector[3] = 1.0
        else:
            vector[2] = 1.0
        return vector

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FakeLLMAdapter:
    model = "gpt-4o"

    async def generate(self, *, instructions: str, prompt: str) -> str:
        del instructions
        chunk_id = re.search(r"\[chunk:([^\]]+)]", prompt).group(1)  # type: ignore[union-attr]
        return f"Bonusnya Rp50.000 dengan status Target Met. [chunk:{chunk_id}]"


class FailingLLMAdapter:
    model = "gpt-4o"

    async def generate(self, *, instructions: str, prompt: str) -> str:
        del instructions, prompt
        raise TimeoutError("provider timeout")


@pytest.mark.asyncio
async def test_rag_ingest_query_unknown_and_generation_failure(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'rag.db').as_posix()}",
    )
    app = create_app(settings)
    async with LifespanManager(app):
        service = RAGService(
            settings=settings,
            parser=DocumentParser(),
            document_repository=DocumentRepository(app.state.session_factory),
            vector_repository=app.state.qdrant_repository,
            embedder=FakeEmbeddingAdapter(),
            llm_service=LLMService(FakeLLMAdapter()),
        )
        app.dependency_overrides[get_rag_service] = lambda: service
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            source = Path("tests/fixtures/SOP_Operational.md").read_bytes()
            ingest = await client.post(
                "/api/v1/rag/ingest",
                files={"file": ("SOP_Operational.md", source, "text/markdown")},
            )
            assert ingest.status_code == 201
            assert ingest.json()["chunk_type_counts"]["table"] >= 1
            assert ingest.json()["processing"]["embedding_model"] == ("text-embedding-3-small")

            duplicate = await client.post(
                "/api/v1/rag/ingest",
                files={"file": ("SOP_copy.md", source, "text/markdown")},
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["duplicate"] is True

            invalid = await client.post("/api/v1/rag/query", json={"question": "x", "top_k": 4})
            assert invalid.status_code == 422
            assert invalid.json()["error"]["code"] == "INVALID_QUESTION"

            query = await client.post(
                "/api/v1/rag/query",
                json={"question": "Berapa bonus jika target tercapai 90%?", "top_k": 3},
            )
            assert query.status_code == 200
            body = query.json()
            assert body["generation_status"] == "completed"
            assert "Rp50.000" in body["answer"]
            available_chunk_count = body["retrieval"]["candidate_count"]
            expected = min(3, available_chunk_count)
            contexts = body["contexts"]
            assert len(contexts) == expected
            assert [item["rank"] for item in contexts] == list(range(1, expected + 1))
            assert body["retrieval"]["returned_count"] == expected
            assert body["contexts"][0]["metadata"]["chunk_type"] == "table"
            assert all("meets_minimum_score" in item for item in contexts)
            assert all("used_for_generation" in item for item in contexts)
            assert any(item["used_for_generation"] for item in contexts)

            unknown = await client.post(
                "/api/v1/rag/query",
                json={"question": "Berapa jatah cuti tahunan SPG?", "top_k": 3},
            )
            assert unknown.status_code == 200
            unknown_body = unknown.json()
            assert len(unknown_body["contexts"]) == unknown_body["retrieval"]["returned_count"]
            assert all(item["meets_minimum_score"] is False for item in unknown_body["contexts"])
            assert all(item["used_for_generation"] is False for item in unknown_body["contexts"])
            assert unknown_body["retrieval"]["generation_context_count"] == 0
            assert unknown_body["generation_status"] == "skipped_no_relevant_context"
            assert "tidak ditemukan" in unknown_body["answer"]

            final_score_query = await client.post(
                "/api/v1/rag/query",
                json={"question": "Berapa bonus jika target tercapai 90%?", "top_k": 3},
            )
            assert final_score_query.status_code == 200
            fsq_body = final_score_query.json()
            contexts = fsq_body["contexts"]
            assert len(contexts) > 0
            for ctx in contexts:
                assert "filename" in ctx["metadata"]
                assert "chunk_type" in ctx["metadata"]
                assert "heading_path" in ctx["metadata"]
                assert "document_version" in ctx["metadata"]
                assert "content" in ctx
            meets = [c for c in contexts if c["meets_minimum_score"]]
            assert len(meets) > 0
            for m in meets:
                assert m["scores"]["final"] >= fsq_body["retrieval"]["minimum_score_applied"]
                assert m["used_for_generation"] is True
            assert fsq_body["generation_status"] == "completed"
            assert fsq_body["retrieval"]["generation_context_count"] == len(meets)

            service.llm_service = LLMService(FailingLLMAdapter())
            failed = await client.post(
                "/api/v1/rag/query",
                json={"question": "Jam berapa SPG wajib absensi?", "top_k": 3},
            )
            assert failed.status_code == 200
            failed_body = failed.json()
            assert failed_body["generation_status"] == "failed"
            assert failed_body["answer"] is None
            assert len(failed_body["contexts"]) > 0
            assert failed_body["retrieval"]["returned_count"] == len(failed_body["contexts"])
            assert failed_body["retrieval"]["generation_context_count"] >= 0

        app.dependency_overrides.clear()
