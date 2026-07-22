from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as db_session:
        yield db_session
