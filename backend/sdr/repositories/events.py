from psycopg.types.json import Jsonb

from sdr.db import fetch_all, fetch_one


async def record(lead_id: str | None, event_type: str, payload: dict | None = None) -> None:
    await fetch_one(
        "INSERT INTO events (lead_id, type, payload) VALUES (%s, %s, %s) RETURNING id",
        [lead_id, event_type, Jsonb(payload or {})],
    )


async def list_for_lead(lead_id: str, limit: int = 100) -> list[dict]:
    return await fetch_all("SELECT * FROM events WHERE lead_id = %s ORDER BY id DESC LIMIT %s", [lead_id, limit])


async def presented_property_codes(lead_id: str) -> list[str]:
    rows = await fetch_all(
        """
        SELECT DISTINCT jsonb_array_elements_text(payload->'codes') AS code
        FROM events WHERE lead_id = %s AND type = 'imoveis_apresentados'
        """,
        [lead_id],
    )
    return [row["code"] for row in rows]
