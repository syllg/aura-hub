from fastapi import Request

from app.core.exceptions import DependencyUnavailableError
from app.services.analytics_service import AnalyticsService
from app.services.chat_service import ChatService
from app.services.rag_service import RAGService


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


def get_rag_service(request: Request) -> RAGService:
    service = request.app.state.rag_service
    if service is None:
        raise DependencyUnavailableError(
            "OPENAI_NOT_CONFIGURED",
            "OpenAI API key wajib dikonfigurasi untuk ingestion dan query RAG.",
        )
    return service


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service
