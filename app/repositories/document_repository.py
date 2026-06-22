from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DocumentChunkModel, DocumentModel
from app.domain.chunking import Chunk


class DocumentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_checksum(self, checksum: str) -> DocumentModel | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(DocumentModel).where(DocumentModel.checksum_sha256 == checksum)
            )
            return result.scalar_one_or_none()

    async def existing_ids(self, document_ids: list[str]) -> set[str]:
        if not document_ids:
            return set()
        async with self._session_factory() as session:
            result = await session.execute(
                select(DocumentModel.id).where(
                    DocumentModel.id.in_(document_ids), DocumentModel.status == "completed"
                )
            )
            return set(result.scalars().all())

    async def save_completed(
        self,
        *,
        document_id: str,
        filename: str,
        content_type: str,
        checksum: str,
        file_size_bytes: int,
        document_version: str | None,
        chunks: list[Chunk],
    ) -> DocumentModel:
        document = DocumentModel(
            id=document_id,
            filename=filename,
            content_type=content_type,
            checksum_sha256=checksum,
            file_size_bytes=file_size_bytes,
            document_version=document_version,
            status="completed",
            chunk_count=len(chunks),
        )
        document.chunks = [
            DocumentChunkModel(
                id=chunk.id,
                chunk_index=chunk.index,
                chunk_type=chunk.type,
                heading_path_json=chunk.heading_path,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                content_hash=chunk.content_hash,
                token_count=chunk.token_count,
            )
            for chunk in chunks
        ]
        async with self._session_factory() as session:
            session.add(document)
            await session.commit()
            await session.refresh(document)
            return document
