from fastapi import APIRouter

from app.api.v1 import analytics, chat, rag

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(rag.router)
api_router.include_router(analytics.router)
api_router.include_router(chat.router)
