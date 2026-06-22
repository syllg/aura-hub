from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from app.adapters.embeddings import EmbeddingProvider
from app.core.config import Settings
from app.core.exceptions import AppError, DependencyUnavailableError
from app.domain.chunking import build_chunks
from app.domain.retrieval import (
    DENSE_WEIGHT,
    HEADING_WEIGHT,
    LEXICAL_WEIGHT,
    RERANKER_NAME,
    RETRIEVAL_STRATEGY,
    RetrievalCandidate,
    rerank_candidates,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.qdrant_repository import QdrantRepository
from app.schemas.rag import RAGIngestResponse, RAGQueryRequest, RAGQueryResponse
from app.services.document_parser import DocumentParseError, DocumentParser
from app.services.llm_service import LLMService

MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        *,
        settings: Settings,
        parser: DocumentParser,
        document_repository: DocumentRepository,
        vector_repository: QdrantRepository,
        embedder: EmbeddingProvider,
        llm_service: LLMService | None,
    ) -> None:
        self.settings = settings
        self.parser = parser
        self.document_repository = document_repository
        self.vector_repository = vector_repository
        self.embedder = embedder
        self.llm_service = llm_service

    async def ingest(self, upload: UploadFile) -> tuple[RAGIngestResponse, int]:
        started = time.perf_counter()
        filename = Path(upload.filename or "document").name
        extension = Path(filename).suffix.lower()
        if extension not in MIME_BY_EXTENSION:
            raise AppError(
                "UNSUPPORTED_DOCUMENT_TYPE",
                "Format dokumen tidak didukung.",
                status_code=415,
            )
        allowed_mimes = {
            MIME_BY_EXTENSION[extension],
            "application/octet-stream",
            "text/x-markdown",
        }
        if upload.content_type not in allowed_mimes:
            raise AppError(
                "UNSUPPORTED_DOCUMENT_TYPE",
                "MIME type dokumen tidak sesuai dengan ekstensi.",
                status_code=415,
            )

        temporary_path: Path | None = None
        checksum = hashlib.sha256()
        size = 0
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as handle:
                temporary_path = Path(handle.name)
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_document_size_mb * 1024 * 1024:
                        raise AppError(
                            "FILE_TOO_LARGE",
                            "Ukuran dokumen melebihi batas yang diizinkan.",
                            status_code=413,
                        )
                    checksum.update(chunk)
                    await asyncio.to_thread(handle.write, chunk)
            if size == 0:
                raise AppError("EMPTY_DOCUMENT", "Dokumen kosong.", status_code=422)
            digest = checksum.hexdigest()
            existing = await self.document_repository.get_by_checksum(digest)
            if existing and existing.status == "completed":
                logger.info(
                    "rag_duplicate document_id=%s checksum=%s",
                    existing.id,
                    digest[:12],
                )
                return (
                    RAGIngestResponse(
                        document_id=existing.id,
                        filename=existing.filename,
                        checksum_sha256=existing.checksum_sha256,
                        status=existing.status,
                        duplicate=True,
                        chunk_count=existing.chunk_count,
                        created_at=existing.created_at,
                        message="Dokumen dengan isi yang sama sudah pernah diproses.",
                    ),
                    200,
                )

            try:
                document = await asyncio.to_thread(
                    self.parser.extract,
                    temporary_path,
                    filename=filename,
                    content_type=MIME_BY_EXTENSION[extension],
                )
            except DocumentParseError as exc:
                raise AppError(exc.code, exc.message, status_code=422) from exc
            document_id = str(uuid4())
            chunks = await asyncio.to_thread(
                build_chunks,
                document,
                document_id=document_id,
                document_checksum=digest,
                target_tokens=self.settings.chunk_target_tokens,
                maximum_tokens=self.settings.chunk_max_tokens,
                overlap_tokens=self.settings.chunk_overlap_tokens,
            )
            if not chunks:
                raise AppError(
                    "DOCUMENT_CHUNKING_FAILED",
                    "Dokumen tidak menghasilkan chunk bermakna.",
                    status_code=422,
                )
            try:
                vectors = await self.embedder.embed_passages(
                    [chunk.embedding_text for chunk in chunks]
                )
            except Exception as exc:
                raise DependencyUnavailableError(
                    "EMBEDDING_SERVICE_UNAVAILABLE",
                    "Layanan OpenAI embedding tidak tersedia.",
                ) from exc
            if len(vectors) != len(chunks) or any(
                len(vector) != self.settings.embedding_dimensions for vector in vectors
            ):
                raise DependencyUnavailableError(
                    "EMBEDDING_DIMENSION_MISMATCH",
                    "Dimensi embedding tidak sesuai konfigurasi 1536.",
                )
            try:
                await self.vector_repository.upsert(
                    chunks=chunks,
                    vectors=vectors,
                    filename=filename,
                    checksum=digest,
                    document_version=document.detected_version,
                )
            except Exception as exc:
                raise DependencyUnavailableError(
                    "VECTOR_DATABASE_UNAVAILABLE", "Qdrant tidak tersedia."
                ) from exc
            try:
                saved = await self.document_repository.save_completed(
                    document_id=document_id,
                    filename=filename,
                    content_type=document.content_type,
                    checksum=digest,
                    file_size_bytes=size,
                    document_version=document.detected_version,
                    chunks=chunks,
                )
            except Exception:
                await self.vector_repository.delete_points([chunk.id for chunk in chunks])
                raise

            counts = Counter(chunk.type for chunk in chunks)
            characters = sum(len(page.text) for page in document.pages)
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "rag_ingest_completed document_id=%s checksum=%s chunks=%s duration_ms=%s",
                saved.id,
                digest[:12],
                saved.chunk_count,
                duration_ms,
            )
            return (
                RAGIngestResponse(
                    document_id=saved.id,
                    filename=saved.filename,
                    checksum_sha256=saved.checksum_sha256,
                    status=saved.status,
                    duplicate=False,
                    chunk_count=saved.chunk_count,
                    chunk_type_counts={
                        "paragraph": counts["paragraph"],
                        "table": counts["table"],
                        "list": counts["list"],
                    },
                    detected_document_version=saved.document_version,
                    processing={
                        "pages_extracted": len(document.pages),
                        "characters_extracted": characters,
                        "embedding_model": self.embedder.model,
                        "duration_ms": duration_ms,
                    },
                    created_at=saved.created_at,
                ),
                201,
            )
        finally:
            await upload.close()
            if temporary_path is not None and temporary_path.exists():
                await asyncio.to_thread(os.unlink, temporary_path)

    async def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        started = time.perf_counter()
        document_ids = request.document_ids
        if document_ids:
            existing = await self.document_repository.existing_ids(document_ids)
            if not existing:
                raise AppError(
                    "DOCUMENT_FILTER_NOT_FOUND",
                    "Dokumen filter tidak ditemukan.",
                    status_code=404,
                )
            document_ids = sorted(existing)
        try:
            vector = await self.embedder.embed_query(request.question)
        except Exception as exc:
            raise DependencyUnavailableError(
                "EMBEDDING_SERVICE_UNAVAILABLE",
                "Layanan OpenAI embedding tidak tersedia.",
            ) from exc
        if len(vector) != self.settings.embedding_dimensions:
            raise DependencyUnavailableError(
                "EMBEDDING_DIMENSION_MISMATCH",
                "Dimensi embedding query tidak sesuai konfigurasi 1536.",
            )
        try:
            candidates = await self.vector_repository.search(
                vector,
                limit=self.settings.rag_dense_candidates,
                document_ids=document_ids,
            )
        except Exception as exc:
            raise DependencyUnavailableError(
                "VECTOR_DATABASE_UNAVAILABLE", "Qdrant tidak tersedia."
            ) from exc
        contexts = rerank_candidates(
            request.question,
            candidates,
            top_k=min(request.top_k, 3),
            minimum_final_score=self.settings.rag_min_final_score,
        )
        retrieval_ms = int((time.perf_counter() - started) * 1000)
        answer: str | None = None
        generation_status = "skipped"
        generation: dict[str, Any] | None = None
        warnings: list[str] = []
        generation_contexts = [c for c in contexts if c.meets_threshold]
        if request.generate_answer:
            if not generation_contexts:
                answer = "Informasi tersebut tidak ditemukan dalam dokumen SOP yang tersedia."
                generation_status = "skipped_no_relevant_context"
            elif self.llm_service is None:
                generation_status = "failed"
                warnings.append(
                    "Jawaban tidak dapat dibuat karena layanan LLM tidak tersedia; "
                    "konteks retrieval tetap dikembalikan."
                )
            else:
                generation_started = time.perf_counter()
                try:
                    answer = await self.llm_service.answer(
                        request.question,
                        generation_contexts,
                        conversation_history=(request.conversation_history),
                    )
                    generation_status = "completed"
                except Exception:
                    generation_status = "failed"
                    warnings.append(
                        "Jawaban tidak dapat dibuat karena layanan LLM tidak tersedia; "
                        "konteks retrieval tetap dikembalikan."
                    )
                generation = {
                    "provider": "openai",
                    "model": self.llm_service.provider.model,
                    "duration_ms": int((time.perf_counter() - generation_started) * 1000),
                }
        context_payloads = [
            self._context_payload(item, item in generation_contexts) for item in contexts
        ]
        logger.info(
            "rag_query_completed "
            "candidates=%s returned=%s generation_contexts=%s "
            "generation_status=%s duration_ms=%s",
            len(candidates),
            len(contexts),
            len(generation_contexts),
            generation_status,
            retrieval_ms,
        )
        return RAGQueryResponse(
            question=request.question,
            answer=answer,
            generation_status=generation_status,
            contexts=context_payloads,
            retrieval={
                "candidate_count": len(candidates),
                "returned_count": len(contexts),
                "generation_context_count": len(generation_contexts),
                "embedding_model": self.embedder.model,
                "strategy": RETRIEVAL_STRATEGY,
                "reranker": RERANKER_NAME,
                "score_weights": {
                    "dense": DENSE_WEIGHT,
                    "lexical": LEXICAL_WEIGHT,
                    "heading_bonus": HEADING_WEIGHT,
                },
                "duration_ms": retrieval_ms,
                "minimum_score_applied": self.settings.rag_min_final_score,
            },
            generation=generation,
            warnings=warnings,
        )

    @staticmethod
    def _context_payload(
        candidate: RetrievalCandidate, used_for_generation: bool
    ) -> dict[str, Any]:
        return {
            "rank": candidate.rank,
            "chunk_id": candidate.chunk_id,
            "document_id": candidate.document_id,
            "content": candidate.content,
            "metadata": candidate.metadata,
            "scores": {
                "dense": round(candidate.dense_score, 6),
                "lexical": round(candidate.lexical_score, 6),
                "heading_bonus": round(candidate.heading_bonus, 6),
                "final": round(candidate.final_score, 6),
            },
            "meets_minimum_score": candidate.meets_threshold,
            "used_for_generation": used_for_generation,
        }
