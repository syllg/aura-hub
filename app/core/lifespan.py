from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from openai import AsyncOpenAI

from app.adapters.embeddings import OpenAIEmbeddingAdapter
from app.adapters.llm import OpenAILLMAdapter
from app.core.config import Settings
from app.core.qdrant import create_qdrant_client
from app.db.session import create_engine, create_session_factory, create_tables
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.qdrant_repository import QdrantRepository
from app.services.analytics_service import AnalyticsService
from app.services.chat_service import ChatService
from app.services.document_parser import DocumentParser
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService


@asynccontextmanager
async def application_lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    Path("data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url)
    await create_tables(engine)
    session_factory = create_session_factory(engine)

    openai_client: AsyncOpenAI | None = None
    qdrant_client = create_qdrant_client(settings)
    if not settings.is_test:
        if not settings.openai_api_key:
            await qdrant_client.close()
            await engine.dispose()
            raise RuntimeError("OPENAI_API_KEY wajib dikonfigurasi")
        openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    qdrant_repository = QdrantRepository(
        qdrant_client,
        collection_name=settings.qdrant_collection,
        dimensions=settings.embedding_dimensions,
    )
    try:
        await qdrant_repository.ensure_collection()
    except Exception:
        if openai_client is not None:
            await openai_client.close()
        await qdrant_client.close()
        await engine.dispose()
        raise
    document_repository = DocumentRepository(session_factory)
    analytics_repository = AnalyticsRepository(session_factory)
    analytics_service = AnalyticsService(analytics_repository, settings)

    rag_service: RAGService | None = None
    llm_service: LLMService | None = None
    if openai_client is not None:
        embedding_adapter = OpenAIEmbeddingAdapter(
            openai_client,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            batch_size=settings.embedding_batch_size,
        )
        llm_service = (
            LLMService(
                OpenAILLMAdapter(
                    openai_client,
                    model=settings.llm_model,
                    temperature=settings.llm_temperature,
                )
            )
            if settings.llm_enabled
            else None
        )
        rag_service = RAGService(
            settings=settings,
            parser=DocumentParser(),
            document_repository=document_repository,
            vector_repository=qdrant_repository,
            embedder=embedding_adapter,
            llm_service=llm_service,
        )

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.qdrant_client = qdrant_client
    app.state.qdrant_repository = qdrant_repository
    app.state.openai_client = openai_client
    chat_service = ChatService(
        rag_service=rag_service,
        analytics_service=analytics_service,
        llm_service=llm_service,
    )
    app.state.analytics_service = analytics_service
    app.state.chat_service = chat_service
    app.state.llm_service = llm_service
    app.state.rag_service = rag_service
    try:
        yield
    finally:
        if openai_client is not None:
            await openai_client.close()
        await qdrant_client.close()
        await engine.dispose()
