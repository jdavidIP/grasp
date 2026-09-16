from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# pgvector.sqlalchemy.Vector serializes via Postgres's text literal format on its own;
# registering asyncpg's native binary vector codec here would conflict with that.
engine = create_async_engine(settings.database_url)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
