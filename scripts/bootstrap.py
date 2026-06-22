from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.qdrant import create_qdrant_client  # noqa: E402
from app.db.session import create_engine, create_tables  # noqa: E402
from app.repositories.qdrant_repository import QdrantRepository  # noqa: E402


async def bootstrap() -> None:
    settings = get_settings()
    Path("data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url)
    client = create_qdrant_client(settings)
    try:
        await create_tables(engine)
        repository = QdrantRepository(
            client,
            collection_name=settings.qdrant_collection,
            dimensions=settings.embedding_dimensions,
        )
        await repository.ensure_collection()
        print("SQLite tables and Qdrant collection are ready.")
    finally:
        await client.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(bootstrap())
