from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from sdr.models import LeadProfile

Route = Literal["safe_reply", "opt_out", "handoff", "recepcao", "consultor", "investidor", "agendamento"]
SPECIALISTS = ("recepcao", "consultor", "investidor", "agendamento")
REPLY_NODES = frozenset({*SPECIALISTS, "handoff", "opt_out", "safe_reply", "followup"})


class SDRState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    lead_id: str
    channel: str
    mode: Literal["inbound", "followup"]
    profile: dict
    signals: NotRequired[dict]
    guardrail: NotRequired[dict]
    route: NotRequired[str]
    active_agent: NotRequired[str]
    stage: NotRequired[str]
    previous_stage: NotRequired[str]
    score: NotRequired[int]
    temperature: NotRequired[str]
    needs_summary: NotRequired[bool]
    handoff_to: NotRequired[str | None]
    gap_seconds: NotRequired[float | None]


@dataclass
class AgentContext:
    lead_id: str
    channel: str
    agent: str
    profile: LeadProfile
    stage: str
    missing: list[str]
    appointments: list[str]
    first_contact: bool
    now: datetime
    specialist_name: str = ""
    score: int = 0
    temperature: str = "frio"
    presented: list[str] = field(default_factory=list)
    summary: str | None = None
    returning: str | None = None
