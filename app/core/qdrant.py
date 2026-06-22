from __future__ import annotations

from pathlib import Path

from qdrant_client import AsyncQdrantClient

from app.core.config import Settings


def create_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    if settings.is_test or settings.qdrant_url == ":memory:":
        return AsyncQdrantClient(location=":memory:")
    if settings.qdrant_url.startswith("local://"):
        raw_path = settings.qdrant_url.removeprefix("local://")
        local_path = Path(raw_path or "data/qdrant_local")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return AsyncQdrantClient(path=str(local_path))
    return AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
