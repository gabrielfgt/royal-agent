from sdr.db import fetch_all, fetch_one


async def add(
    lead_id: str,
    role: str,
    content: str,
    *,
    kind: str = "text",
    agent: str | None = None,
    latency_ms: int | None = None,
) -> dict:
    return await fetch_one(
        """
        INSERT INTO messages (lead_id, role, content, kind, agent, latency_ms)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        [lead_id, role, content, kind, agent, latency_ms],
    )


async def list_for_lead(lead_id: str, *, after_id: int = 0, limit: int = 500) -> list[dict]:
    return await fetch_all(
        "SELECT * FROM messages WHERE lead_id = %s AND id > %s ORDER BY id LIMIT %s",
        [lead_id, after_id, limit],
    )


async def count_from_lead(lead_id: str) -> int:
    row = await fetch_one("SELECT count(*) AS n FROM messages WHERE lead_id = %s AND role = 'lead'", [lead_id])
    return row["n"]


async def response_stats() -> dict:
    return await fetch_one(
        """
        SELECT COALESCE(avg(latency_ms), 0)::int AS avg_ms,
               COALESCE(percentile_cont(0.9) WITHIN GROUP (ORDER BY latency_ms), 0)::int AS p90_ms,
               count(*) FILTER (WHERE kind = 'followup') AS followups_sent,
               count(*) FILTER (WHERE role = 'lead' AND kind = 'audio') AS audio_messages
        FROM messages
        WHERE role IN ('agent', 'lead')
        """
    )
