import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from sdr.agent.runtime import get_graph
from sdr.db import get_pool, try_lead_lock
from sdr.repositories import events, leads
from sdr.scoring import merge_profile
from sdr.services import lead_state
from sdr.text import phone_key

log = logging.getLogger(__name__)


def _thread(lead_id: str) -> dict:
    return {"configurable": {"thread_id": str(lead_id)}}


async def _merge_threads(canonical_id: str, duplicate_id: str) -> None:
    graph = await get_graph()
    snapshot = await graph.aget_state(_thread(duplicate_id))
    history = (snapshot.values or {}).get("messages", [])
    if history:
        await graph.aupdate_state(_thread(canonical_id), {"messages": history}, as_node="followup")
    await AsyncPostgresSaver(await get_pool()).adelete_thread(str(duplicate_id))


async def claim_phone(lead_id: str, raw_phone: str) -> str:
    await leads.set_phone_if_missing(lead_id, raw_phone)
    return await link_by_phone(lead_id)


async def link_by_phone(lead_id: str) -> str:
    lead = await leads.get(lead_id)
    key = phone_key(leads.profile_of(lead).phone)
    if not key or lead["phone_key"] == key:
        return lead_id
    await leads.set_phone_key(lead_id, key)
    other = await leads.find_other_by_phone(key, lead_id)
    if other is None:
        return lead_id
    async with try_lead_lock(str(other["id"])) as acquired:
        if not acquired:
            return lead_id
        canonical, duplicate = sorted([lead, other], key=lambda row: row["created_at"])
        older, newer = sorted([lead, other], key=lambda row: row["last_inbound_at"] or row["created_at"])
        profile = merge_profile(leads.profile_of(older), leads.profile_of(newer))
        canonical_id, duplicate_id = str(canonical["id"]), str(duplicate["id"])
        await _merge_threads(canonical_id, duplicate_id)
        await leads.absorb(canonical_id, duplicate_id, profile=profile)
        await lead_state.evaluate(canonical_id, profile)
        channels = [i["channel"] for i in await leads.identities(canonical_id)]
        await events.record(canonical_id, "leads_unificados", {"lead_absorvido": duplicate_id, "canais": channels})
        log.info("Leads unificados por telefone", extra={"data": {"canonical": canonical_id, "canais": channels}})
        return canonical_id
