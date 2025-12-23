"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import AsyncGenerator

# Base class for all models
Base = declarative_base()

# For async operations
async_engine = None
AsyncSessionLocal = None

# For sync operations (Alembic migrations)
sync_engine = None
SessionLocal = None


def init_db(database_url: str, async_database_url: str = None) -> None:
    """Initialize database connections."""
    global async_engine, AsyncSessionLocal, sync_engine, SessionLocal

    # Async engine for application use
    if async_database_url:
        async_engine = create_async_engine(
            async_database_url,
            echo=False,
            future=True,
        )
        AsyncSessionLocal = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    else:
        # Fallback to sync if async URL not provided
        async_engine = None

    # Sync engine for migrations
    sync_engine = create_engine(
        database_url,
        echo=False,
        future=True,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=sync_engine,
    )


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session():
    """Get sync database session (for migrations)."""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

