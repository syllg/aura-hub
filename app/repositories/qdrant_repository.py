from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime

from qdrant_client import AsyncQdrantClient, models

from app.domain.chunking import Chunk
from app.domain.retrieval import RetrievalCandidate


class QdrantRepository:
    def __init__(
        self,
        client: AsyncQdrantClient,
        *,
        collection_name: str,
        dimensions: int,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.dimensions = dimensions

    async def ensure_collection(self) -> None:
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimensions, distance=models.Distance.COSINE
                ),
            )
        info = await self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        actual_size = getattr(vectors, "size", None)
        if actual_size != self.dimensions:
            raise RuntimeError(
                f"Qdrant collection dimension {actual_size} does not match {self.dimensions}"
            )
        for field in ("document_id", "checksum_sha256", "chunk_type"):
            with suppress(Exception):
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

    async def upsert(
        self,
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
        filename: str,
        checksum: str,
        document_version: str | None,
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        points = [
            models.PointStruct(
                id=chunk.id,
                vector=vector,
                payload={
                    "document_id": chunk.document_id,
                    "filename": filename,
                    "checksum_sha256": checksum,
                    "chunk_index": chunk.index,
                    "chunk_type": chunk.type,
                    "heading_path": chunk.heading_path,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "content": chunk.content,
                    "embedding_text": chunk.embedding_text,
                    "content_hash": chunk.content_hash,
                    "token_count": chunk.token_count,
                    "document_version": document_version,
                    "created_at": created_at,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    async def delete_points(self, point_ids: list[str]) -> None:
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=point_ids),
            wait=True,
        )

    async def search(
        self,
        vector: list[float],
        *,
        limit: int,
        document_ids: list[str] | None = None,
    ) -> list[RetrievalCandidate]:
        query_filter = None
        if document_ids:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchAny(any=document_ids)
                    )
                ]
            )
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        candidates: list[RetrievalCandidate] = []
        for point in result.points:
            payload = point.payload or {}
            candidates.append(
                RetrievalCandidate(
                    chunk_id=str(point.id),
                    document_id=str(payload.get("document_id", "")),
                    content=str(payload.get("content", "")),
                    metadata={
                        "filename": payload.get("filename"),
                        "chunk_type": payload.get("chunk_type"),
                        "heading_path": payload.get("heading_path", []),
                        "document_version": payload.get("document_version"),
                        "page_start": payload.get("page_start"),
                        "page_end": payload.get("page_end"),
                    },
                    dense_score=float(point.score),
                )
            )
        return candidates
