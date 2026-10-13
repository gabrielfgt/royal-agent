import logging

from sdr.crm import get_crm
from sdr.repositories import appointments, events, leads

log = logging.getLogger(__name__)


async def sync(lead_id: str, *, reason: str) -> bool:
    crm = get_crm()
    if not crm.enabled:
        return False
    lead = await leads.get(lead_id)
    upcoming = await appointments.upcoming_for_lead(lead_id)
    try:
        ids = await crm.upsert_lead(lead, upcoming, reason)
    except Exception as error:
        log.exception("Falha ao sincronizar lead com CRM")
        await events.record(lead_id, "crm_erro", {"erro": str(error)[:300]})
        return False
    await leads.set_crm_ids(lead_id, ids.contact_id, ids.deal_id)
    await events.record(lead_id, "crm_sincronizado", {"contact_id": ids.contact_id, "deal_id": ids.deal_id})
    return True
