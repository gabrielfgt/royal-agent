from sdr.models import LeadProfile
from sdr.repositories import appointments, events, leads, messages
from sdr.scoring import compute_score, compute_stage, temperature_for


async def evaluate(lead_id: str, profile: LeadProfile) -> dict:
    lead = await leads.get(lead_id)
    upcoming = await appointments.upcoming_for_lead(lead_id)
    lead_messages = await messages.count_from_lead(lead_id)
    stage = compute_stage(
        profile,
        has_appointment=bool(upcoming),
        handoff=bool(lead["handoff_reason"]),
        opted_out=lead["opted_out"],
        lead_messages=lead_messages,
    )
    score = compute_score(profile, lead_messages=lead_messages, has_appointment=bool(upcoming))
    temperature = temperature_for(score)
    await leads.save_turn_state(lead_id, profile=profile, stage=stage, score=score, temperature=temperature)
    if stage != lead["stage"]:
        await events.record(lead_id, "mudanca_estagio", {"de": lead["stage"], "para": stage})
    return {
        "stage": stage,
        "previous_stage": lead["stage"],
        "score": score,
        "temperature": temperature,
        "lead_messages": lead_messages,
        "had_summary": lead["summary"] is not None,
    }
