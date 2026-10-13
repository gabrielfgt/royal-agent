from datetime import datetime

from sdr.db import fetch_all, fetch_one


async def brokers() -> list[dict]:
    return await fetch_all("SELECT * FROM brokers ORDER BY id")


async def broker(broker_id: str) -> dict | None:
    return await fetch_one("SELECT * FROM brokers WHERE id = %s", [broker_id])


async def booked_slots(broker_id: str, start: datetime, end: datetime) -> set[datetime]:
    rows = await fetch_all(
        """
        SELECT starts_at FROM appointments
        WHERE broker_id = %s AND status = 'agendado' AND starts_at BETWEEN %s AND %s
        """,
        [broker_id, start, end],
    )
    return {row["starts_at"] for row in rows}


async def create(
    *, lead_id: str, broker_id: str, kind: str, starts_at: datetime, property_code: str | None, notes: str | None
) -> dict | None:
    await fetch_one(
        """
        UPDATE appointments SET status = 'remarcado'
        WHERE lead_id = %s AND kind = %s AND status = 'agendado' AND starts_at > now()
        RETURNING id
        """,
        [lead_id, kind],
    )
    return await fetch_one(
        """
        INSERT INTO appointments (lead_id, broker_id, kind, starts_at, property_code, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        [lead_id, broker_id, kind, starts_at, property_code, notes],
    )


async def upcoming_for_lead(lead_id: str) -> list[dict]:
    return await fetch_all(
        """
        SELECT a.*, b.name AS broker_name, p.title AS property_title, p.neighborhood AS property_neighborhood
        FROM appointments a
        JOIN brokers b ON b.id = a.broker_id
        LEFT JOIN properties p ON p.code = a.property_code
        WHERE a.lead_id = %s AND a.status = 'agendado' AND a.starts_at > now() - interval '2 hours'
        ORDER BY a.starts_at
        """,
        [lead_id],
    )


async def list_all(*, upcoming_only: bool = True, limit: int = 100) -> list[dict]:
    return await fetch_all(
        """
        SELECT a.*, b.name AS broker_name, p.title AS property_title, p.neighborhood AS property_neighborhood,
               COALESCE(l.profile->>'name', l.display_name) AS lead_name, l.temperature AS lead_temperature
        FROM appointments a
        JOIN brokers b ON b.id = a.broker_id
        JOIN leads l ON l.id = a.lead_id
        LEFT JOIN properties p ON p.code = a.property_code
        WHERE a.status = 'agendado' AND (NOT %s OR a.starts_at > now() - interval '2 hours')
        ORDER BY a.starts_at
        LIMIT %s
        """,
        [upcoming_only, limit],
    )
