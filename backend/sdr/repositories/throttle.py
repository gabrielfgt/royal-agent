from sdr.db import fetch_one


async def hit_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    row = await fetch_one(
        """
        INSERT INTO rate_limits (key, window_start, hits)
        VALUES (%s, to_timestamp(floor(extract(epoch FROM now()) / %s) * %s), 1)
        ON CONFLICT (key, window_start) DO UPDATE SET hits = rate_limits.hits + 1
        RETURNING hits
        """,
        [key, window_seconds, window_seconds],
    )
    return row["hits"] > limit


async def first_time_update(update_id: int) -> bool:
    row = await fetch_one(
        "INSERT INTO telegram_updates (update_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING update_id",
        [update_id],
    )
    return row is not None
