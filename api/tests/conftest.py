import pytest_asyncio
from sqlalchemy import delete

from app.db import async_session, engine
from app.models.video import Video


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_videos():
    yield
    async with async_session() as session:
        await session.execute(delete(Video).where(Video.youtube_id.like("test-%")))
        await session.commit()
