import logging

from langchain_core.messages import AIMessage

from sdr.agent.runtime import get_graph, run_config
from sdr.channels.delivery import deliver
from sdr.config import get_settings
from sdr.db import lead_lock
from sdr.observability import flush_tracing
from sdr.repositories import events, leads, messages
from sdr.text import strip_markdown

log = logging.getLogger(__name__)


async def send_followup(lead: dict) -> dict | None:
    lead_id = str(lead["id"])
    async with lead_lock(lead_id):
        claimed = await leads.claim_followup(lead_id, lead["followup_count"])
        if claimed is None:
            return None
        try:
            graph = await get_graph()
            state = await graph.ainvoke(
                {"mode": "followup", "lead_id": lead_id, "channel": claimed["channel"], "profile": claimed["profile"]},
                run_config(lead_id, claimed["channel"], "followup"),
            )
        except Exception:
            log.exception("Falha ao gerar follow-up")
            await leads.release_followup(lead_id)
            return None
        finally:
            flush_tracing()
        last = state["messages"][-1]
        text = strip_markdown(last.text if isinstance(last, AIMessage) else str(last.content)).strip()
        stored = await messages.add(lead_id, "agent", text, kind="followup", agent="followup")
        delivered = await deliver(claimed, text)
        await events.record(
            lead_id, "followup_enviado", {"tentativa": claimed["followup_count"], "entregue": delivered}
        )
        return {"lead_id": lead_id, "attempt": claimed["followup_count"], "message_id": stored["id"], "text": text}


async def run_due(*, force: bool = False) -> dict:
    settings = get_settings()
    delays = settings.followup_delay_seconds
    sent = []
    for lead in await leads.due_for_followup(delays=delays, force=force):
        if result := await send_followup(lead):
            sent.append(result)
    lost = await leads.mark_lost(max_attempts=len(delays), lost_after_seconds=settings.followup_lost_after_seconds)
    for lead in lost:
        await events.record(str(lead["id"]), "lead_perdido", {"followups": lead["followup_count"]})
    return {"sent": sent, "lost": [str(lead["id"]) for lead in lost]}


async def force_for_lead(lead_id: str) -> dict | None:
    lead = await leads.get(lead_id)
    if lead is None or lead["followup_count"] >= len(get_settings().followup_delay_seconds):
        return None
    return await send_followup(lead)
