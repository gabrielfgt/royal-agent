import re
from datetime import UTC, datetime
from html import escape

import httpx

from sdr.agenda import format_slot
from sdr.crm import CrmIds
from sdr.finance import brl
from sdr.models import LeadProfile

BASE_URL = "https://api.hubapi.com"
NOTE_TO_CONTACT = 202
NOTE_TO_DEAL = 214
DEAL_TO_CONTACT = 3

DEAL_STAGES = {"qualificado": "qualifiedtobuy", "handoff": "qualifiedtobuy", "agendado": "presentationscheduled"}
LEAD_STATUS = {"qualificado": "IN_PROGRESS", "handoff": "CONNECTED", "agendado": "OPEN_DEAL"}
LIFECYCLE = {"qualificado": "salesqualifiedlead", "handoff": "salesqualifiedlead", "agendado": "opportunity"}
INTENT_LABELS = {"compra": "Compra", "aluguel": "Aluguel", "investimento": "Investimento", "indefinido": "Lead"}


def _association(target_id: str, type_id: int) -> dict:
    return {
        "to": {"id": target_id},
        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": type_id}],
    }


def _note_html(lead: dict, appointments: list[dict], reason: str) -> str:
    summary = lead.get("summary") or {}
    parts = [
        f"<p><strong>Resumo do SDR (IA) — estágio: {escape(reason)}</strong></p>",
        f"<p>Score {lead['score']}/100 ({escape(lead['temperature'])})</p>",
    ]
    if headline := summary.get("headline"):
        parts.append(f"<p>{escape(headline)}</p>")
    for title, key in [
        ("Perfil", "profile"),
        ("Necessidades", "needs"),
        ("Objeções", "objections"),
        ("Próximos passos", "next_steps"),
    ]:
        if items := summary.get(key):
            parts.append(f"<p><strong>{title}</strong></p><ul>{''.join(f'<li>{escape(i)}</li>' for i in items)}</ul>")
    if tip := summary.get("approach_tip"):
        parts.append(f"<p><strong>Dica de abordagem:</strong> {escape(tip)}</p>")
    for appointment in appointments:
        parts.append(
            f"<p>📅 {escape(appointment['kind'])} {escape(format_slot(appointment['starts_at']))} "
            f"com {escape(appointment['broker_name'])}</p>"
        )
    return "".join(parts)


class HubSpotCRM:
    enabled = True

    def __init__(self, token: str, portal_id: str = "") -> None:
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._portal_id = portal_id

    def record_url(self, contact_id: str) -> str | None:
        if not self._portal_id:
            return None
        return f"https://app.hubspot.com/contacts/{self._portal_id}/record/0-1/{contact_id}"

    async def upsert_lead(self, lead: dict, appointments: list[dict], reason: str) -> CrmIds:
        profile = LeadProfile.model_validate(lead["profile"] or {})
        async with httpx.AsyncClient(base_url=BASE_URL, headers=self._headers, timeout=15) as client:
            contact_id = await self._upsert_contact(client, lead, profile, reason)
            deal_id = await self._upsert_deal(client, lead, profile, contact_id, reason)
            note = await client.post(
                "/crm/v3/objects/notes",
                json={
                    "properties": {
                        "hs_timestamp": datetime.now(UTC).isoformat(),
                        "hs_note_body": _note_html(lead, appointments, reason),
                    },
                    "associations": [_association(contact_id, NOTE_TO_CONTACT), _association(deal_id, NOTE_TO_DEAL)],
                },
            )
            note.raise_for_status()
        return CrmIds(contact_id, deal_id)

    async def _upsert_contact(self, client: httpx.AsyncClient, lead: dict, profile: LeadProfile, reason: str) -> str:
        name = profile.name or lead.get("display_name") or "Lead"
        properties = {
            "firstname": name,
            "lastname": f"({lead['channel']})",
            "hs_lead_status": LEAD_STATUS.get(reason, "OPEN"),
            "lifecyclestage": LIFECYCLE.get(reason, "lead"),
        }
        if profile.email:
            properties["email"] = profile.email
        if profile.phone:
            properties["phone"] = profile.phone
        if contact_id := lead.get("crm_contact_id"):
            response = await client.patch(f"/crm/v3/objects/contacts/{contact_id}", json={"properties": properties})
            if response.status_code == 400:
                properties.pop("lifecyclestage")
                response = await client.patch(f"/crm/v3/objects/contacts/{contact_id}", json={"properties": properties})
            response.raise_for_status()
            return contact_id
        response = await client.post("/crm/v3/objects/contacts", json={"properties": properties})
        if response.status_code == 409 and (match := re.search(r"Existing ID: (\d+)", response.text)):
            return match[1]
        response.raise_for_status()
        return response.json()["id"]

    async def _upsert_deal(
        self, client: httpx.AsyncClient, lead: dict, profile: LeadProfile, contact_id: str, reason: str
    ) -> str:
        amount = profile.investment_ticket if profile.intent == "investimento" else profile.budget_max
        regions = ", ".join(profile.regions)
        name = profile.name or lead.get("display_name") or "Lead"
        properties = {
            "dealname": f"{INTENT_LABELS[profile.intent]} · {name}" + (f" · {regions}" if regions else ""),
            "pipeline": "default",
            "dealstage": DEAL_STAGES.get(reason, "appointmentscheduled"),
            "description": (lead.get("summary") or {}).get("headline", "")
            + (f" Orçamento: {brl(amount)}." if amount else ""),
        }
        if amount:
            properties["amount"] = str(int(amount))
        if deal_id := lead.get("crm_deal_id"):
            response = await client.patch(f"/crm/v3/objects/deals/{deal_id}", json={"properties": properties})
            response.raise_for_status()
            return deal_id
        response = await client.post(
            "/crm/v3/objects/deals",
            json={"properties": properties, "associations": [_association(contact_id, DEAL_TO_CONTACT)]},
        )
        response.raise_for_status()
        return response.json()["id"]
