"""
Standalone script to create all database tables using the async SQLAlchemy engine.

Run with:
    python create_tables.py

This is used as the Railway preDeployCommand to ensure all tables exist before
the application starts. It uses `conn.run_sync` to execute the synchronous
`Base.metadata.create_all` within an async connection context, which is required
because the engine is created with `create_async_engine`.
"""

import asyncio

from app.core.database import Base, engine

# Import all models so their table definitions are registered on Base.metadata
import app.models  # noqa: F401


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[create_tables] All tables created (or already exist).")


if __name__ == "__main__":
    asyncio.run(create_tables())
