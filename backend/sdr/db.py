from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from importlib import resources
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from sdr.config import get_settings

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=settings.db_pool_max_size,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None},
        )
        await _pool.open(wait=True, timeout=30)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    pool = await get_pool()
    async with pool.connection() as conn:
        yield conn


async def fetch_all(query: str, params: Sequence[Any] | dict[str, Any] | None = None) -> list[dict]:
    async with connection() as conn:
        cursor = await conn.execute(query, params)
        return await cursor.fetchall()


async def fetch_one(query: str, params: Sequence[Any] | dict[str, Any] | None = None) -> dict | None:
    async with connection() as conn:
        cursor = await conn.execute(query, params)
        return await cursor.fetchone()


async def execute(query: str, params: Sequence[Any] | dict[str, Any] | None = None) -> int:
    async with connection() as conn:
        cursor = await conn.execute(query, params)
        return cursor.rowcount


@asynccontextmanager
async def lead_lock(lead_id: str) -> AsyncIterator[None]:
    async with connection() as conn:
        await conn.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", [str(lead_id)])
        try:
            yield
        finally:
            await conn.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", [str(lead_id)])


@asynccontextmanager
async def try_lead_lock(lead_id: str) -> AsyncIterator[bool]:
    async with connection() as conn:
        cursor = await conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS ok", [str(lead_id)])
        acquired = (await cursor.fetchone())["ok"]
        try:
            yield acquired
        finally:
            if acquired:
                await conn.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", [str(lead_id)])


async def apply_schema() -> None:
    sql = resources.files("sdr").joinpath("schema.sql").read_text(encoding="utf-8")
    async with connection() as conn:
        await conn.execute(sql)


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.7f}" for value in values) + "]"
