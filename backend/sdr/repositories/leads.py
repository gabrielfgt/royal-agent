from typing import Any

from psycopg.types.json import Jsonb

from sdr.db import execute, fetch_all, fetch_one
from sdr.models import LeadProfile

INACTIVE_STAGES = ("agendado", "handoff", "perdido", "opt_out")


async def get_or_create(channel: str, external_id: str, display_name: str | None) -> tuple[dict, bool]:
    if existing := await get_by_external(channel, external_id):
        return existing, False
    row = await fetch_one(
        """
        WITH lead AS (
            INSERT INTO leads (channel, external_id, display_name, last_channel, last_external_id)
            VALUES (%(channel)s, %(external_id)s, %(name)s, %(channel)s, %(external_id)s)
            ON CONFLICT (channel, external_id)
            DO UPDATE SET display_name = COALESCE(leads.display_name, EXCLUDED.display_name)
            RETURNING *, (xmax = 0) AS created
        ), identity AS (
            INSERT INTO lead_identities (channel, external_id, lead_id)
            SELECT %(channel)s, %(external_id)s, id FROM lead
            ON CONFLICT DO NOTHING
        )
        SELECT * FROM lead
        """,
        {"channel": channel, "external_id": external_id, "name": display_name},
    )
    created = row.pop("created")
    return row, created


CHANNELS_COLUMN = (
    "ARRAY(SELECT i.channel FROM lead_identities i WHERE i.lead_id = l.id ORDER BY i.created_at) AS channels"
)


async def get(lead_id: str) -> dict | None:
    return await fetch_one(f"SELECT l.*, {CHANNELS_COLUMN} FROM leads l WHERE l.id = %s", [lead_id])


async def get_by_external(channel: str, external_id: str) -> dict | None:
    return await fetch_one(
        """
        SELECT l.*, (
            SELECT ARRAY_AGG(x.channel ORDER BY x.created_at) FROM lead_identities x WHERE x.lead_id = l.id
        ) AS channels
        FROM lead_identities i JOIN leads l ON l.id = i.lead_id
        WHERE i.channel = %s AND i.external_id = %s
        """,
        [channel, external_id],
    )


async def identities(lead_id: str) -> list[dict]:
    return await fetch_all(
        "SELECT channel, external_id FROM lead_identities WHERE lead_id = %s ORDER BY created_at", [lead_id]
    )


def profile_of(lead: dict) -> LeadProfile:
    return LeadProfile.model_validate(lead.get("profile") or {})


async def mark_inbound(lead_id: str, channel: str, external_id: str) -> dict:
    return await fetch_one(
        """
        UPDATE leads
        SET last_inbound_at = now(),
            last_channel = %(channel)s,
            last_external_id = %(external_id)s,
            opted_out = FALSE,
            reengaged_count = reengaged_count + CASE WHEN followup_count > 0 THEN 1 ELSE 0 END,
            followup_count = 0,
            updated_at = now()
        FROM (SELECT last_inbound_at AS previous_inbound_at FROM leads WHERE id = %(id)s) AS previous
        WHERE id = %(id)s
        RETURNING leads.*, previous.previous_inbound_at
        """,
        {"id": lead_id, "channel": channel, "external_id": external_id},
    )


async def mark_outbound(lead_id: str) -> None:
    await fetch_one("UPDATE leads SET last_outbound_at = now() WHERE id = %s RETURNING id", [lead_id])


async def save_turn_state(lead_id: str, *, profile: LeadProfile, stage: str, score: int, temperature: str) -> dict:
    return await fetch_one(
        """
        UPDATE leads
        SET profile = %s, stage = %s, score = %s, temperature = %s,
            display_name = COALESCE(%s, display_name), updated_at = now()
        WHERE id = %s
        RETURNING *
        """,
        [Jsonb(profile.model_dump()), stage, score, temperature, profile.name, lead_id],
    )


async def save_summary(lead_id: str, summary: dict) -> None:
    await fetch_one(
        "UPDATE leads SET summary = %s, summary_updated_at = now() WHERE id = %s RETURNING id",
        [Jsonb(summary), lead_id],
    )


async def set_handoff(lead_id: str, reason: str) -> None:
    await fetch_one(
        "UPDATE leads SET handoff_reason = %s, updated_at = now() WHERE id = %s RETURNING id", [reason, lead_id]
    )


async def set_opted_out(lead_id: str) -> None:
    await fetch_one(
        "UPDATE leads SET opted_out = TRUE, stage = 'opt_out', updated_at = now() WHERE id = %s RETURNING id",
        [lead_id],
    )


async def set_paused(lead_id: str, paused: bool) -> dict | None:
    return await fetch_one(
        "UPDATE leads SET ai_paused = %s, updated_at = now() WHERE id = %s RETURNING *", [paused, lead_id]
    )


async def set_crm_ids(lead_id: str, contact_id: str | None, deal_id: str | None) -> None:
    await fetch_one(
        """
        UPDATE leads SET crm_contact_id = %s, crm_deal_id = %s, crm_synced_at = now()
        WHERE id = %s RETURNING id
        """,
        [contact_id, deal_id, lead_id],
    )


async def delete(lead_id: str) -> bool:
    return await fetch_one("DELETE FROM leads WHERE id = %s RETURNING id", [lead_id]) is not None


async def list_leads(
    *,
    stage: str | None = None,
    temperature: str | None = None,
    intent: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict]:
    clauses, params = ["TRUE"], []
    if stage:
        clauses.append("l.stage = %s")
        params.append(stage)
    if temperature:
        clauses.append("l.temperature = %s")
        params.append(temperature)
    if intent:
        clauses.append("l.profile->>'intent' = %s")
        params.append(intent)
    if search:
        clauses.append("(l.display_name ILIKE %s OR l.profile->>'name' ILIKE %s OR l.external_id ILIKE %s)")
        params.extend([f"%{search}%"] * 3)
    params.append(limit)
    return await fetch_all(
        f"""
        SELECT l.*, {CHANNELS_COLUMN},
               (SELECT count(*) FROM messages m WHERE m.lead_id = l.id) AS message_count,
               (SELECT content FROM messages m WHERE m.lead_id = l.id ORDER BY m.id DESC LIMIT 1) AS last_message
        FROM leads l
        WHERE {" AND ".join(clauses)}
        ORDER BY GREATEST(l.last_inbound_at, l.last_outbound_at, l.created_at) DESC
        LIMIT %s
        """,
        params,
    )


async def due_for_followup(*, delays: list[int], force: bool, limit: int = 25) -> list[dict]:
    return await fetch_all(
        """
        SELECT * FROM leads
        WHERE NOT opted_out AND NOT ai_paused
          AND stage <> ALL(%(inactive)s)
          AND last_outbound_at IS NOT NULL
          AND (last_inbound_at IS NULL OR last_outbound_at >= last_inbound_at)
          AND followup_count < cardinality(%(delays)s::int[])
          AND (%(force)s OR last_outbound_at <= now() - make_interval(secs => (%(delays)s::int[])[followup_count + 1]))
        ORDER BY last_outbound_at
        LIMIT %(limit)s
        """,
        {"inactive": list(INACTIVE_STAGES), "delays": delays, "force": force, "limit": limit},
    )


async def claim_followup(lead_id: str, expected_count: int) -> dict | None:
    return await fetch_one(
        """
        UPDATE leads
        SET followup_count = followup_count + 1, last_outbound_at = now(), updated_at = now()
        WHERE id = %s AND followup_count = %s
          AND NOT opted_out AND NOT ai_paused
          AND (last_inbound_at IS NULL OR last_outbound_at >= last_inbound_at)
        RETURNING *
        """,
        [lead_id, expected_count],
    )


async def release_followup(lead_id: str) -> None:
    await fetch_one(
        "UPDATE leads SET followup_count = GREATEST(followup_count - 1, 0) WHERE id = %s RETURNING id", [lead_id]
    )


async def mark_lost(*, max_attempts: int, lost_after_seconds: int) -> list[dict]:
    return await fetch_all(
        """
        UPDATE leads
        SET stage = 'perdido', temperature = 'frio', updated_at = now()
        WHERE stage <> ALL(%s)
          AND NOT ai_paused
          AND followup_count >= %s
          AND (last_inbound_at IS NULL OR last_outbound_at >= last_inbound_at)
          AND last_outbound_at <= now() - make_interval(secs => %s)
        RETURNING *
        """,
        [list(INACTIVE_STAGES), max_attempts, lost_after_seconds],
    )


async def metrics() -> dict[str, Any]:
    return await fetch_one(
        """
        SELECT
            count(*) AS leads,
            count(*) FILTER (WHERE temperature = 'quente') AS hot,
            count(*) FILTER (WHERE stage IN ('qualificado', 'agendado', 'handoff')) AS qualified,
            count(*) FILTER (WHERE stage = 'agendado') AS scheduled,
            count(*) FILTER (WHERE stage = 'handoff') AS handoff,
            count(*) FILTER (WHERE stage = 'perdido') AS lost,
            count(*) FILTER (WHERE stage = 'opt_out') AS opted_out,
            COALESCE(sum(reengaged_count), 0) AS reengaged,
            count(*) FILTER (WHERE created_at >= now() - interval '1 day') AS leads_today
        FROM leads
        """
    )


async def breakdown(expression: str) -> list[dict]:
    return await fetch_all(f"SELECT {expression} AS key, count(*) AS count FROM leads GROUP BY 1 ORDER BY 2 DESC")


async def leads_per_day(timezone: str, days: int = 14) -> list[dict]:
    return await fetch_all(
        """
        WITH today AS (SELECT (now() AT TIME ZONE %(tz)s)::date AS d)
        SELECT to_char(day::date, 'YYYY-MM-DD') AS date, count(l.id) AS count
        FROM today, generate_series(today.d - (%(days)s - 1), today.d, interval '1 day') AS day
        LEFT JOIN leads l ON (l.created_at AT TIME ZONE %(tz)s)::date = day::date
        GROUP BY day ORDER BY day
        """,
        {"tz": timezone, "days": days},
    )


async def set_phone_if_missing(lead_id: str, phone: str) -> None:
    await execute(
        """
        UPDATE leads SET profile = jsonb_set(profile, '{phone}', to_jsonb(%s::text))
        WHERE id = %s AND COALESCE(profile->>'phone', '') = ''
        """,
        [phone, lead_id],
    )


async def set_phone_key(lead_id: str, phone_key: str) -> None:
    await execute("UPDATE leads SET phone_key = %s WHERE id = %s", [phone_key, lead_id])


async def find_other_by_phone(phone_key: str, lead_id: str) -> dict | None:
    return await fetch_one(
        "SELECT * FROM leads WHERE phone_key = %s AND id <> %s ORDER BY created_at LIMIT 1", [phone_key, lead_id]
    )


async def absorb(canonical_id: str, duplicate_id: str, *, profile: LeadProfile) -> dict:
    for table in ("messages", "appointments", "events"):
        await execute(f"UPDATE {table} SET lead_id = %s WHERE lead_id = %s", [canonical_id, duplicate_id])
    await execute("UPDATE lead_identities SET lead_id = %s WHERE lead_id = %s", [canonical_id, duplicate_id])
    merged = await fetch_one(
        """
        UPDATE leads AS c
        SET profile = %(profile)s,
            display_name = COALESCE(c.display_name, d.display_name),
            handoff_reason = COALESCE(c.handoff_reason, d.handoff_reason),
            crm_contact_id = COALESCE(c.crm_contact_id, d.crm_contact_id),
            crm_deal_id = COALESCE(c.crm_deal_id, d.crm_deal_id),
            reengaged_count = c.reengaged_count + d.reengaged_count,
            followup_count = 0,
            summary = NULL,
            last_inbound_at = GREATEST(c.last_inbound_at, d.last_inbound_at),
            last_outbound_at = GREATEST(c.last_outbound_at, d.last_outbound_at),
            last_channel = CASE WHEN d.last_inbound_at > c.last_inbound_at THEN d.last_channel ELSE c.last_channel END,
            last_external_id = CASE WHEN d.last_inbound_at > c.last_inbound_at
                                    THEN d.last_external_id ELSE c.last_external_id END,
            updated_at = now()
        FROM leads AS d
        WHERE c.id = %(canonical)s AND d.id = %(duplicate)s
        RETURNING c.*
        """,
        {"profile": Jsonb(profile.model_dump()), "canonical": canonical_id, "duplicate": duplicate_id},
    )
    await execute("DELETE FROM leads WHERE id = %s", [duplicate_id])
    return merged
