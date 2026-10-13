import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from sdr.api.serializers import lead_out
from sdr.db import close_pool
from sdr.llm import fast_model
from sdr.repositories import appointments, leads
from sdr.services import conversation, followups
from sdr.services.conversation import Inbound

REPORT_DIR = Path(__file__).parent / "reports"


@dataclass
class Scenario:
    key: str
    title: str
    opening: str
    persona: str
    checklist: list[str]
    expected_fields: list[str]
    expected_stages: set[str]
    max_turns: int = 8
    stop_after_turns: int | None = None
    transcript: list[tuple[str, str]] = field(default_factory=list)


SCENARIOS = [
    Scenario(
        key="compra",
        title="Exemplo 1 — Compra",
        opening="Estou procurando casa em condomínio em Tatuí.",
        persona=(
            "Você é Paula, 34 anos, casada, com dois filhos, quer COMPRAR uma casa em condomínio fechado para morar "
            "em Tatuí. Orçamento até R$ 800 mil, precisa de 3 quartos, quer se mudar em até 2 meses e vai financiar "
            "com 20% de entrada. Responda só o que perguntarem, de forma curta e natural. Se mostrarem imóveis, "
            "escolha um e aceite visitar. Quando oferecerem horários, escolha o primeiro."
        ),
        checklist=[
            "Entendeu a intenção (compra para morar)",
            "Perguntou a faixa de preço",
            "Perguntou a quantidade de quartos",
            "Perguntou ou considerou a região de interesse",
            "Identificou a urgência/prazo",
            "Encaminhou para visita ou reunião",
        ],
        expected_fields=["budget_max", "bedrooms", "regions", "urgency"],
        expected_stages={"agendado", "qualificado"},
    ),
    Scenario(
        key="investimento",
        title="Exemplo 2 — Investimento",
        opening="Quero investir em imóveis para renda.",
        persona=(
            "Você é Roberto, 52 anos, quer investir em Tatuí para ter RENDA com aluguel. Tem R$ 400 mil disponíveis, "
            "espera algo como 0,6% ao mês e pensa em manter por 10 anos. Responda de forma curta. Aceite a reunião "
            "com a especialista e, quando oferecerem horários, escolha o primeiro."
        ),
        checklist=[
            "Entendeu o perfil investidor (renda)",
            "Identificou o ticket disponível",
            "Identificou a expectativa de retorno",
            "Alinhou expectativas com honestidade (sem prometer retorno)",
            "Direcionou para a especialista em investimentos",
        ],
        expected_fields=["investment_ticket", "expected_return", "investment_goal"],
        expected_stages={"agendado", "qualificado"},
    ),
    Scenario(
        key="followup",
        title="Exemplo 3 — Follow-up",
        opening="Oi, vi um anúncio de vocês. Quero comprar uma casa de 2 quartos em Tatuí.",
        persona=(
            "Você é Lucas, 28 anos, quer COMPRAR sua primeira casa de 2 quartos em Tatuí, até R$ 300 mil, pelo Minha "
            "Casa Minha Vida, e tem um cachorro. Responda de forma curta."
        ),
        checklist=[
            "Retomou o contato automaticamente",
            "A mensagem de follow-up manteve o contexto da conversa",
            "Reengajou o lead após a resposta",
        ],
        expected_fields=["regions", "bedrooms"],
        expected_stages={"em_qualificacao", "qualificado", "agendado"},
        max_turns=2,
        stop_after_turns=2,
    ),
]


class Judgement(BaseModel):
    checklist: list[bool] = Field(description="Um booleano por item do checklist, na mesma ordem.")
    humanizacao: int = Field(ge=1, le=5, description="Naturalidade e empatia da consultora.")
    contexto: int = Field(ge=1, le=5, description="Uso correto do contexto e memória da conversa.")
    objetividade: int = Field(ge=1, le=5, description="Mensagens curtas, uma pergunta por vez, sem enrolação.")
    comentario: str = Field(description="Uma ou duas frases com pontos fortes e fracos.")


async def agent_turn(session: str, text: str, scenario: Scenario) -> str:
    replies = []
    async for event in conversation.handle(Inbound("web", session, text)):
        if event["type"] == "reply":
            replies.append("\n".join(event["bubbles"]))
    reply = "\n".join(replies)
    scenario.transcript.extend([("Lead", text), ("Sofia", reply)])
    return reply


async def simulated_lead(scenario: Scenario) -> str:
    history = "\n".join(f"{who}: {text}" for who, text in scenario.transcript[-10:])
    prompt = (
        f"{scenario.persona}\nVocê está conversando por chat com a consultora de uma imobiliária. "
        f"Escreva APENAS a sua próxima mensagem, curta, sem aspas.\n\nConversa até agora:\n{history}"
    )
    response = await fast_model().ainvoke([SystemMessage(prompt), HumanMessage("Sua próxima mensagem:")])
    return response.text.strip()


async def judge(scenario: Scenario) -> Judgement:
    transcript = "\n".join(f"{who}: {text}" for who, text in scenario.transcript)
    checklist = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(scenario.checklist))
    prompt = (
        "Você avalia um agente SDR imobiliário (a consultora Sofia) num hackathon. Seja criterioso e justo.\n"
        f"Cenário: {scenario.title}\nChecklist:\n{checklist}\n\nTranscrição:\n{transcript}"
    )
    return await fast_model().with_structured_output(Judgement).ainvoke([SystemMessage(prompt)])


async def run_scenario(scenario: Scenario) -> dict:
    session = f"eval-{scenario.key}-{uuid.uuid4().hex[:10]}"
    message = scenario.opening
    for turn in range(scenario.max_turns):
        await agent_turn(session, message, scenario)
        lead = await leads.get_by_external("web", session)
        if lead["stage"] == "agendado" or (scenario.stop_after_turns and turn + 1 >= scenario.stop_after_turns):
            break
        message = await simulated_lead(scenario)

    if scenario.key == "followup":
        lead = await leads.get_by_external("web", session)
        sent = await followups.force_for_lead(str(lead["id"]))
        if sent:
            scenario.transcript.append(("Sofia (follow-up automático)", sent["text"]))
        reply = await simulated_lead(scenario)
        await agent_turn(session, reply, scenario)

    lead = await leads.get_by_external("web", session)
    snapshot = lead_out(lead)
    upcoming = await appointments.upcoming_for_lead(str(lead["id"]))
    judgement = await judge(scenario)
    missing = [f for f in scenario.expected_fields if not snapshot["profile"].get(f)]
    return {
        "scenario": scenario.title,
        "session": session,
        "stage": snapshot["stage"],
        "stage_ok": snapshot["stage"] in scenario.expected_stages,
        "score": snapshot["score"],
        "temperature": snapshot["temperature"],
        "fields_missing": missing,
        "appointments": len(upcoming),
        "followups": lead["followup_count"] + lead["reengaged_count"],
        "reengaged": lead["reengaged_count"],
        "checklist": dict(zip(scenario.checklist, judgement.checklist, strict=False)),
        "humanizacao": judgement.humanizacao,
        "contexto": judgement.contexto,
        "objetividade": judgement.objetividade,
        "comentario": judgement.comentario,
        "transcript": scenario.transcript,
    }


def render_markdown(results: list[dict]) -> str:
    lines = [f"# Avaliação dos cenários — {datetime.now():%d/%m/%Y %H:%M}", ""]
    lines.append("| Cenário | Estágio | Score | Checklist | Humanização | Contexto | Objetividade |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        passed = sum(r["checklist"].values())
        lines.append(
            f"| {r['scenario']} | {r['stage']} {'✅' if r['stage_ok'] else '⚠️'} | {r['score']} ({r['temperature']}) "
            f"| {passed}/{len(r['checklist'])} | {r['humanizacao']}/5 | {r['contexto']}/5 | {r['objetividade']}/5 |"
        )
    for r in results:
        lines += ["", f"## {r['scenario']}", "", f"> {r['comentario']}", ""]
        lines += [f"- {'✅' if ok else '❌'} {item}" for item, ok in r["checklist"].items()]
        if r["fields_missing"]:
            lines.append(f"- ⚠️ campos não extraídos: {', '.join(r['fields_missing'])}")
        lines += ["", "<details><summary>Transcrição</summary>", ""]
        lines += [f"**{who}:** {text.replace(chr(10), ' / ')}  " for who, text in r["transcript"]]
        lines += ["", "</details>"]
    return "\n".join(lines)


async def main(selected: list[str]) -> None:
    try:
        results = [await run_scenario(s) for s in SCENARIOS if not selected or s.key in selected]
    finally:
        await close_pool()
    REPORT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    (REPORT_DIR / f"{stamp}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(results)
    (REPORT_DIR / f"{stamp}.md").write_text(markdown, encoding="utf-8")
    print(markdown.split("\n## ")[0])
    print(f"\nRelatório completo: {REPORT_DIR / f'{stamp}.md'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roda os cenários do desafio com lead simulado e LLM-juiz.")
    parser.add_argument("scenarios", nargs="*", choices=[s.key for s in SCENARIOS] + [[]], default=[])
    asyncio.run(main(parser.parse_args().scenarios))
