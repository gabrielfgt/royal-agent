from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from sdr.config import get_settings


@dataclass(frozen=True)
class CrmIds:
    contact_id: str | None
    deal_id: str | None


class CRM(Protocol):
    enabled: bool

    async def upsert_lead(self, lead: dict, appointments: list[dict], reason: str) -> CrmIds: ...

    def record_url(self, contact_id: str) -> str | None: ...


class NullCRM:
    enabled = False

    async def upsert_lead(self, lead: dict, appointments: list[dict], reason: str) -> CrmIds:
        return CrmIds(lead.get("crm_contact_id"), lead.get("crm_deal_id"))

    def record_url(self, contact_id: str) -> str | None:
        return None


@lru_cache
def get_crm() -> CRM:
    settings = get_settings()
    if settings.hubspot_token:
        from sdr.crm.hubspot import HubSpotCRM

        return HubSpotCRM(settings.hubspot_token, settings.hubspot_portal_id)
    return NullCRM()
