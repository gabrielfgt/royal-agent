from sdr.crm import get_crm
from sdr.models import LeadProfile
from sdr.scoring import FIELD_LABELS, missing_fields


def iso(value) -> str | None:
    return value.isoformat() if value else None


def lead_out(lead: dict) -> dict:
    profile = LeadProfile.model_validate(lead.get("profile") or {})
    contact_id = lead.get("crm_contact_id")
    return {
        "id": str(lead["id"]),
        "channel": lead["channel"],
        "channels": lead.get("channels") or [lead["channel"]],
        "name": profile.name or lead.get("display_name"),
        "stage": lead["stage"],
        "score": lead["score"],
        "temperature": lead["temperature"],
        "intent": profile.intent,
        "profile": profile.model_dump(),
        "missing_fields": [FIELD_LABELS.get(f, f) for f in missing_fields(profile)],
        "summary": lead.get("summary"),
        "summary_updated_at": iso(lead.get("summary_updated_at")),
        "handoff_reason": lead.get("handoff_reason"),
        "ai_paused": lead["ai_paused"],
        "opted_out": lead["opted_out"],
        "followup_count": lead["followup_count"],
        "reengaged_count": lead.get("reengaged_count", 0),
        "created_at": iso(lead["created_at"]),
        "last_inbound_at": iso(lead.get("last_inbound_at")),
        "last_outbound_at": iso(lead.get("last_outbound_at")),
        "crm_contact_id": contact_id,
        "crm_deal_id": lead.get("crm_deal_id"),
        "crm_url": get_crm().record_url(contact_id) if contact_id else None,
        "message_count": lead.get("message_count"),
        "last_message": lead.get("last_message"),
    }


def message_out(message: dict) -> dict:
    return {
        "id": message["id"],
        "role": message["role"],
        "content": message["content"],
        "kind": message["kind"],
        "agent": message.get("agent"),
        "latency_ms": message.get("latency_ms"),
        "created_at": iso(message["created_at"]),
    }


def appointment_out(appointment: dict) -> dict:
    return {
        "id": str(appointment["id"]),
        "lead_id": str(appointment["lead_id"]),
        "lead_name": appointment.get("lead_name"),
        "lead_temperature": appointment.get("lead_temperature"),
        "broker_name": appointment["broker_name"],
        "kind": appointment["kind"],
        "starts_at": iso(appointment["starts_at"]),
        "property_code": appointment.get("property_code"),
        "property_title": appointment.get("property_title"),
        "property_neighborhood": appointment.get("property_neighborhood"),
        "status": appointment["status"],
        "notes": appointment.get("notes"),
    }


def event_out(event: dict) -> dict:
    return {
        "id": event["id"],
        "type": event["type"],
        "payload": event["payload"],
        "created_at": iso(event["created_at"]),
    }


def property_out(prop: dict) -> dict:
    return {
        **{k: v for k, v in prop.items() if k != "embedding"},
        "price": float(prop["price"]),
        "condo_fee": float(prop["condo_fee"]),
        "iptu_monthly": float(prop["iptu_monthly"]),
        "estimated_rent": float(prop["estimated_rent"]) if prop.get("estimated_rent") else None,
    }
