from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer

from sdr.agent import nodes
from sdr.agent.state import SPECIALISTS, SDRState


def entry(state: SDRState) -> str | list[str]:
    if state.get("mode") == "followup":
        return "followup"
    return ["guardrail", "extract"]


def build_graph(checkpointer: Checkpointer = None):
    builder = StateGraph(SDRState)

    builder.add_node("guardrail", nodes.guardrail)
    builder.add_node("extract", nodes.extract)
    builder.add_node("triage", nodes.triage)
    for name in SPECIALISTS:
        builder.add_node(name, nodes.SPECIALIST_NODES[name])
    builder.add_node("handoff", nodes.handoff)
    builder.add_node("safe_reply", nodes.safe_reply)
    builder.add_node("opt_out", nodes.opt_out)
    builder.add_node("finalize", nodes.finalize)
    builder.add_node("summarize", nodes.summarize)
    builder.add_node("crm_sync", nodes.crm_sync)
    builder.add_node("followup", nodes.followup)

    builder.add_conditional_edges(START, entry, ["guardrail", "extract", "followup"])
    builder.add_edge(["guardrail", "extract"], "triage")
    builder.add_conditional_edges(
        "triage",
        lambda state: state["route"],
        [*SPECIALISTS, "handoff", "safe_reply", "opt_out"],
    )
    for name in ("recepcao", "consultor", "investidor"):
        builder.add_conditional_edges(name, nodes.after_specialist, ["agendamento", "finalize"])
    builder.add_edge("agendamento", "finalize")
    builder.add_edge("handoff", "finalize")
    builder.add_edge("safe_reply", END)
    builder.add_edge("opt_out", END)
    builder.add_conditional_edges("finalize", nodes.after_finalize, ["summarize", "crm_sync", END])
    builder.add_conditional_edges("summarize", nodes.after_summary, ["crm_sync", END])
    builder.add_edge("crm_sync", END)
    builder.add_edge("followup", END)

    return builder.compile(checkpointer=checkpointer, name="sdr_imobiliario")
