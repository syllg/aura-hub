"""Clear all uploaded data from the database.

Usage:
    python scripts/clear_data.py

This deletes all analytics datasets and RAG documents.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete

from app.db.models import AnalyticsDatasetModel, DocumentModel
from app.db.session import create_engine, create_session_factory


async def clear_all_data():
    engine = create_engine("sqlite+aiosqlite:///./data/aura_hub.db")
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        # Delete analytics datasets (cascades to daily rows)
        result_analytics = await session.execute(delete(AnalyticsDatasetModel))
        print(f"Deleted {result_analytics.rowcount} analytics datasets")

        # Delete documents (cascades to chunks)
        result_docs = await session.execute(delete(DocumentModel))
        print(f"Deleted {result_docs.rowcount} documents")

        await session.commit()
        print("All data cleared successfully.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(clear_all_data())
