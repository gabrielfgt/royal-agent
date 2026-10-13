import logging
import re
from datetime import UTC, datetime

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRequest, dynamic_prompt
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage, trim_messages
from langchain_core.runnables import RunnableConfig

from sdr import agenda
from sdr.agent import prompts
from sdr.agent.state import SPECIALISTS, AgentContext, SDRState
from sdr.agent.tools import SPECIALIST_TOOLS
from sdr.config import get_settings
from sdr.llm import chat_model, embed, fast_model
from sdr.models import Extraction, GuardrailVerdict, LeadProfile, TurnSignals
from sdr.presenters import appointment_line, property_line, short_price
from sdr.repositories import appointments, events, leads, messages, properties
from sdr.repositories.properties import PropertyFilters
from sdr.scoring import is_qualified, merge_profile, missing_fields
from sdr.services import crm_sync as crm_service
from sdr.services import lead_state, summaries

log = logging.getLogger(__name__)

OPT_OUT_KEYWORDS = re.compile(r"^\s*(parar|pare|stop|sair|descadastrar|cancelar inscri[cç][aã]o)\s*[.!]*\s*$", re.I)
SUMMARY_STAGES = {"qualificado", "agendado", "handoff"}
SUMMARY_REFRESH_EVERY = 4
HANDOFF_TOOL = "abrir_agenda"

SAFE_REPLIES = {
    "prompt_injection": (
        "Por aqui eu consigo te ajudar só com imóveis: compra, aluguel ou investimento. 🙂\n\n"
        "Me conta, o que você está procurando?"
    ),
    "abusivo": (
        "Quero muito te ajudar, mas preciso que a gente mantenha a conversa respeitosa, combinado?\n\n"
        "Se estiver procurando um imóvel, é só me contar."
    ),
}


def last_human_text(state: SDRState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return message.text
    return ""


def conversation_window(history: list[AnyMessage]) -> list[AnyMessage]:
    return trim_messages(
        history,
        max_tokens=get_settings().history_window,
        token_counter=len,
        strategy="last",
        start_on="human",
        include_system=False,
    )


def render_transcript(history: list[AnyMessage], limit: int = 10) -> str:
    lines = []
    for message in history:
        if isinstance(message, HumanMessage):
            lines.append(f"Lead: {message.text}")
        elif isinstance(message, AIMessage) and message.text and not message.tool_calls:
            lines.append(f"Consultora: {message.text}")
    return "\n".join(lines[-limit:])


def decide_route(guardrail: dict, profile: LeadProfile, signals: TurnSignals) -> str:
    category = guardrail.get("category", "ok")
    if category in ("prompt_injection", "abusivo"):
        return "safe_reply"
    if category == "opt_out":
        return "opt_out"
    if signals.wants_schedule:
        return "agendamento"
    if signals.wants_human:
        return "handoff"
    if profile.intent == "investimento":
        return "investidor"
    if profile.intent in ("compra", "aluguel"):
        return "consultor"
    return "recepcao"


async def guardrail(state: SDRState) -> dict:
    text = last_human_text(state)
    if OPT_OUT_KEYWORDS.match(text):
        return {"guardrail": {"category": "opt_out", "reason": "palavra-chave"}}
    verdict = (
        await fast_model()
        .with_structured_output(GuardrailVerdict)
        .ainvoke([SystemMessage(prompts.GUARDRAIL), HumanMessage(text)])
    )
    return {"guardrail": verdict.model_dump()}


async def extract(state: SDRState) -> dict:
    current = LeadProfile.model_validate(state.get("profile") or {})
    prompt = prompts.EXTRACTOR.format(
        profile=current.model_dump_json(exclude_defaults=True),
        transcript=render_transcript(state["messages"], limit=8),
    )
    result = await fast_model().with_structured_output(Extraction).ainvoke([SystemMessage(prompt)])
    merged = merge_profile(current, result.profile)
    return {"profile": merged.model_dump(), "signals": result.signals.model_dump()}


async def triage(state: SDRState) -> dict:
    route = decide_route(
        state.get("guardrail") or {},
        LeadProfile.model_validate(state["profile"]),
        TurnSignals.model_validate(state.get("signals") or {}),
    )
    return {"route": route}


@dynamic_prompt
def _specialist_system_prompt(request: ModelRequest) -> str:
    return prompts.specialist_prompt(request.runtime.context)


def build_specialist(name: str):
    return create_agent(
        chat_model(),
        tools=SPECIALIST_TOOLS[name],
        middleware=[_specialist_system_prompt, ModelCallLimitMiddleware(run_limit=6, exit_behavior="end")],
        context_schema=AgentContext,
        name=name,
    )


RETURNING_AFTER_SECONDS = 6 * 3600
PRESENTED_LIMIT = 8


def _context_missing(profile: LeadProfile, lead_messages: int) -> list[str]:
    missing = missing_fields(profile)
    if not profile.name and lead_messages >= 2:
        missing.append("name")
    if is_qualified(profile) and not profile.phone:
        missing.append("phone")
    return missing


def _summary_text(summary: dict | None) -> str | None:
    if not summary:
        return None
    steps = "; ".join(summary.get("next_steps") or [])
    return summary.get("headline", "") + (f" Próximos passos: {steps}" if steps else "")


async def _presented_lines(lead_id: str) -> list[str]:
    codes = (await events.presented_property_codes(lead_id))[-PRESENTED_LIMIT:]
    lines = []
    for code in codes:
        if prop := await properties.get(code):
            lines.append(
                f"{code} ({prop['neighborhood']}, {prop['bedrooms']} dorms, {short_price(float(prop['price']))})"
            )
    return lines


async def _agent_context(state: SDRState, name: str) -> AgentContext:
    lead_id = state["lead_id"]
    profile = LeadProfile.model_validate(state["profile"])
    lead = await leads.get(lead_id)
    upcoming = await appointments.upcoming_for_lead(lead_id)
    lead_messages = await messages.count_from_lead(lead_id)
    specialist = await agenda.pick_broker("reuniao_especialista")
    gap = state.get("gap_seconds")
    returning = None
    if gap and gap >= RETURNING_AFTER_SECONDS:
        returning = (
            f"o lead voltou depois de {_humanize_seconds(gap)} sem falar: cumprimente pelo nome, mostre que lembra "
            "do que ele procurava e retome com uma proposta concreta"
        )
    return AgentContext(
        lead_id=lead_id,
        channel=state.get("channel", "web"),
        agent=name,
        profile=profile,
        stage=state.get("stage", "novo"),
        missing=_context_missing(profile, lead_messages),
        appointments=[appointment_line(a) for a in upcoming],
        first_contact=lead_messages <= 1,
        now=datetime.now(UTC),
        specialist_name=specialist["name"],
        score=lead["score"],
        temperature=lead["temperature"],
        presented=await _presented_lines(lead_id),
        summary=_summary_text(lead["summary"]),
        returning=returning,
    )


def specialist_node(name: str):
    agent = build_specialist(name)

    async def run(state: SDRState, config: RunnableConfig) -> dict:
        window = conversation_window(state["messages"])
        context = await _agent_context(state, name)
        result = await agent.ainvoke({"messages": window}, config=config, context=context)
        new_messages = result["messages"][len(window) :]
        if any(isinstance(m, ToolMessage) and m.name == HANDOFF_TOOL for m in new_messages):
            return {"messages": new_messages, "active_agent": name, "handoff_to": "agendamento"}
        if not new_messages or not isinstance(new_messages[-1], AIMessage) or new_messages[-1].tool_calls:
            new_messages.append(AIMessage("Deixa eu confirmar isso com a equipe e já te retorno, tudo bem?"))
        return {"messages": new_messages, "active_agent": name, "handoff_to": None}

    run.__name__ = name
    return run


async def safe_reply(state: SDRState) -> dict:
    category = state["guardrail"]["category"]
    await events.record(state["lead_id"], "guardrail_bloqueio", state["guardrail"])
    return {"messages": [AIMessage(SAFE_REPLIES[category])], "active_agent": "safe_reply"}


async def opt_out(state: SDRState) -> dict:
    await leads.set_opted_out(state["lead_id"])
    await events.record(state["lead_id"], "opt_out", {})
    text = "Tudo bem, não vou mais te enviar mensagens. Se quiser retomar, é só me chamar por aqui. 😊"
    return {"messages": [AIMessage(text)], "active_agent": "opt_out", "stage": "opt_out"}


async def handoff(state: SDRState) -> dict:
    profile = LeadProfile.model_validate(state["profile"])
    kind = "reuniao_especialista" if profile.intent == "investimento" else "visita"
    broker = await agenda.pick_broker(kind, property_kind=profile.property_type)
    await leads.set_handoff(state["lead_id"], "Lead pediu atendimento humano")
    await events.record(state["lead_id"], "handoff", {"reason": "pedido do lead", "broker": broker["name"]})
    first_name = broker["name"].split()[0]
    greeting = f"Claro, {profile.name}!" if profile.name else "Claro!"
    text = (
        f"{greeting} Vou passar seu atendimento para {broker['name']}, do nosso time. Já deixei um resumo de "
        f"tudo o que conversamos, então você não vai precisar repetir nada.\n\n"
        f"{first_name} vai te chamar por aqui em breve. Enquanto isso, posso ajudar em mais alguma coisa?"
    )
    return {"messages": [AIMessage(text)], "active_agent": "handoff"}


async def finalize(state: SDRState) -> dict:
    result = await lead_state.evaluate(state["lead_id"], LeadProfile.model_validate(state["profile"]))
    stage, previous_stage, lead_messages = result["stage"], result["previous_stage"], result["lead_messages"]
    needs_summary = (stage != previous_stage and stage in SUMMARY_STAGES) or (
        stage != "novo"
        and (not result["had_summary"] or lead_messages % SUMMARY_REFRESH_EVERY == 0)
        and lead_messages >= 3
    )
    return {
        "stage": stage,
        "previous_stage": previous_stage,
        "score": result["score"],
        "temperature": result["temperature"],
        "needs_summary": needs_summary,
    }


def after_specialist(state: SDRState) -> str:
    return state.get("handoff_to") or "finalize"


def after_finalize(state: SDRState) -> str:
    if state.get("needs_summary"):
        return "summarize"
    return "crm_sync" if _should_sync_crm(state) else "__end__"


def after_summary(state: SDRState) -> str:
    return "crm_sync" if state.get("stage") in SUMMARY_STAGES else "__end__"


def _should_sync_crm(state: SDRState) -> bool:
    return state.get("stage") in SUMMARY_STAGES and state.get("stage") != state.get("previous_stage")


async def summarize(state: SDRState, config: RunnableConfig) -> dict:
    await summaries.refresh(state["lead_id"], config=config)
    return {}


async def crm_sync(state: SDRState) -> dict:
    await crm_service.sync(state["lead_id"], reason=state.get("stage", ""))
    return {}


async def followup(state: SDRState, config: RunnableConfig) -> dict:
    settings = get_settings()
    lead = await leads.get(state["lead_id"])
    profile = LeadProfile.model_validate(state.get("profile") or {})
    attempt = max(lead["followup_count"], 1)
    max_attempts = len(settings.followup_delay_seconds)
    hook = await _followup_hook(state["lead_id"], profile) if attempt < max_attempts else None
    elapsed = _humanize_elapsed(lead["last_inbound_at"] or lead["created_at"])
    instructions = prompts.FOLLOWUP.format(
        elapsed=elapsed,
        attempt=attempt,
        max_attempts=max_attempts,
        strategy=prompts.FOLLOWUP_STRATEGIES.get(attempt, prompts.FOLLOWUP_STRATEGIES[3]),
        hook=hook or "nenhum",
    )
    system = "\n".join([prompts.persona(state.get("channel", "web")), instructions, prompts.describe_profile(profile)])
    window = [m for m in conversation_window(state["messages"]) if not getattr(m, "tool_calls", None)]
    window = [m for m in window if isinstance(m, HumanMessage | AIMessage)]
    reply = await chat_model().ainvoke(
        [SystemMessage(system), *window, HumanMessage("[sistema] Escreva agora a mensagem de follow-up.")],
        config=config,
    )
    return {"messages": [AIMessage(reply.text, name="followup")], "active_agent": "followup"}


async def _followup_hook(lead_id: str, profile: LeadProfile) -> str | None:
    if profile.intent not in ("compra", "aluguel", "investimento"):
        return None
    purpose = "aluguel" if profile.intent == "aluguel" else "venda"
    budget = profile.investment_ticket if profile.intent == "investimento" else profile.budget_max
    filters = PropertyFilters(
        purpose=purpose,
        regions=profile.regions,
        price_max=budget,
        bedrooms_min=profile.bedrooms,
        pet_friendly=profile.has_pet,
        exclude_codes=[*profile.interested_properties, *await events.presented_property_codes(lead_id)],
    )
    [query_embedding] = await embed([" ".join([purpose, *profile.regions, *profile.preferences]) or purpose])
    result = await properties.search(filters, query_embedding, limit=1)
    if not result.items:
        return None
    return property_line(result.items[0], with_yield=profile.intent == "investimento")


def _humanize_elapsed(since: datetime) -> str:
    return _humanize_seconds((datetime.now(UTC) - since).total_seconds())


def _humanize_seconds(seconds: float) -> str:
    if seconds < 3600:
        return f"{max(int(seconds // 60), 1)} minutos"
    if seconds < 86400:
        return f"{int(seconds // 3600)} horas"
    return f"{int(seconds // 86400)} dias"


SPECIALIST_NODES = {name: specialist_node(name) for name in SPECIALISTS}
