from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from sdr.agent import prompts
from sdr.llm import fast_model
from sdr.models import BrokerSummary, LeadProfile
from sdr.presenters import appointment_line
from sdr.repositories import appointments, leads, messages

TRANSCRIPT_LIMIT = 60


async def refresh(lead_id: str, config: RunnableConfig | None = None) -> dict:
    lead = await leads.get(lead_id)
    history = await messages.list_for_lead(lead_id)
    upcoming = await appointments.upcoming_for_lead(lead_id)
    transcript = "\n".join(
        f"{'Lead' if m['role'] == 'lead' else 'Consultora'}: {m['content']}"
        for m in history[-TRANSCRIPT_LIMIT:]
        if m["kind"] != "notice"
    )
    prompt = prompts.SUMMARY.format(
        profile=LeadProfile.model_validate(lead["profile"] or {}).model_dump_json(exclude_defaults=True),
        score=lead["score"],
        temperature=lead["temperature"],
        stage=lead["stage"],
        appointments="; ".join(appointment_line(a) for a in upcoming) or "nenhum",
        transcript=transcript or "(sem mensagens)",
    )
    summary = await fast_model().with_structured_output(BrokerSummary).ainvoke([SystemMessage(prompt)], config=config)
    data = summary.model_dump()
    await leads.save_summary(lead_id, data)
    return data
