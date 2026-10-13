from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from sdr.agent.runtime import get_graph
from sdr.api.schemas import (
    UUID_PATTERN,
    AppointmentListOut,
    AuthCheckOut,
    ErrorOut,
    FollowupNowOut,
    FollowupRunIn,
    FollowupRunOut,
    GraphOut,
    LeadDetailOut,
    LeadListOut,
    LeadOut,
    MetricsOut,
    PauseIn,
    PropertyListOut,
    Purpose,
    SummaryOut,
)
from sdr.api.serializers import appointment_out, event_out, lead_out, message_out, property_out
from sdr.config import get_settings
from sdr.db import get_pool
from sdr.models import Intent, PropertyKind, Stage, Temperature
from sdr.repositories import appointments, events, leads, messages, properties
from sdr.security import require_dashboard
from sdr.services import followups, summaries

router = APIRouter(
    prefix="/api",
    dependencies=[Depends(require_dashboard)],
    responses={401: {"model": ErrorOut, "description": "Token do painel ausente ou inválido."}},
)

NOT_FOUND = {404: {"model": ErrorOut, "description": "Lead não encontrado."}}

LeadId = Annotated[
    str,
    Path(pattern=UUID_PATTERN, description="ID do lead (UUID).", examples=["9b49ab0b-dd4f-4ca2-8bc0-472e3d0d7b31"]),
]


async def _lead_or_404(lead_id: str) -> dict:
    lead = await leads.get(lead_id)
    if lead is None:
        raise HTTPException(404, "Lead não encontrado")
    return lead


@router.get(
    "/auth/check",
    tags=["painel"],
    summary="Validar token do painel",
    description="Retorna `ok: true` quando o token Bearer é válido. Usado pela tela de login do painel.",
    response_model=AuthCheckOut,
)
async def auth_check() -> dict:
    return {"ok": True}


@router.get(
    "/dashboard/metrics",
    tags=["painel"],
    summary="Métricas do funil comercial",
    description=(
        "KPIs do painel: totais de leads (quentes, qualificados, agendados, perdidos, reengajados), tempo de "
        "resposta do agente (média e p90), distribuição por estágio, temperatura, intenção e canal, novos leads "
        "por dia (fuso de São Paulo) e próximos compromissos."
    ),
    response_model=MetricsOut,
)
async def metrics() -> dict:
    totals = await leads.metrics()
    responses = await messages.response_stats()
    upcoming = await appointments.list_all(upcoming_only=True, limit=8)
    return {
        "totals": {
            **totals,
            "followups_sent": responses["followups_sent"],
            "audio_messages": responses["audio_messages"],
        },
        "response_time": {"avg_ms": responses["avg_ms"], "p90_ms": responses["p90_ms"]},
        "by_stage": await leads.breakdown("stage"),
        "by_temperature": await leads.breakdown("temperature"),
        "by_intent": await leads.breakdown("COALESCE(profile->>'intent', 'indefinido')"),
        "by_channel": await leads.breakdown("channel"),
        "leads_per_day": await leads.leads_per_day(get_settings().timezone),
        "upcoming_appointments": [appointment_out(a) for a in upcoming],
    }


@router.get(
    "/leads",
    tags=["leads"],
    summary="Listar leads",
    description="Lista os leads mais recentes (até 200) com filtros opcionais e busca por nome ou identificador.",
    response_model=LeadListOut,
)
async def list_leads(
    stage: Annotated[Stage | None, Query(description="Filtra pelo estágio do funil.")] = None,
    temperature: Annotated[Temperature | None, Query(description="Filtra pela temperatura.")] = None,
    intent: Annotated[Intent | None, Query(description="Filtra pela intenção identificada.")] = None,
    q: Annotated[
        str | None, Query(description="Busca por nome ou identificador do canal.", examples=["Marcos"])
    ] = None,
) -> dict:
    rows = await leads.list_leads(stage=stage, temperature=temperature, intent=intent, search=q)
    return {"items": [lead_out(row) for row in rows]}


@router.get(
    "/leads/{lead_id}",
    tags=["leads"],
    summary="Detalhe do lead",
    description="Lead com perfil, resumo para o corretor, transcrição completa, compromissos e linha do tempo.",
    response_model=LeadDetailOut,
    responses=NOT_FOUND,
)
async def lead_detail(lead_id: LeadId) -> dict:
    lead = await _lead_or_404(lead_id)
    return {
        "lead": lead_out(lead),
        "messages": [message_out(m) for m in await messages.list_for_lead(lead_id)],
        "appointments": [appointment_out(a) for a in await appointments.upcoming_for_lead(lead_id)],
        "events": [event_out(e) for e in await events.list_for_lead(lead_id)],
    }


@router.post(
    "/leads/{lead_id}/summary",
    tags=["leads"],
    summary="Regenerar resumo para o corretor",
    description="Gera agora um novo resumo estruturado (perfil, necessidades, imóveis, objeções, próximos passos).",
    response_model=SummaryOut,
    responses=NOT_FOUND,
)
async def regenerate_summary(lead_id: LeadId) -> dict:
    await _lead_or_404(lead_id)
    return {"summary": await summaries.refresh(lead_id)}


@router.post(
    "/leads/{lead_id}/pause",
    tags=["leads"],
    summary="Pausar ou retomar a IA para o lead",
    description=(
        "Com a IA pausada, as mensagens do lead continuam registradas, mas o agente não responde nem envia "
        "follow-ups — o corretor assume a conversa."
    ),
    response_model=LeadOut,
    responses=NOT_FOUND,
)
async def pause_lead(lead_id: LeadId, payload: PauseIn) -> dict:
    lead = await leads.set_paused(lead_id, payload.paused)
    if lead is None:
        raise HTTPException(404, "Lead não encontrado")
    await events.record(lead_id, "ia_pausada" if payload.paused else "ia_retomada", {})
    return lead_out(lead)


@router.post(
    "/leads/{lead_id}/followup",
    tags=["leads"],
    summary="Enviar follow-up agora",
    description=(
        "Dispara imediatamente a próxima tentativa de follow-up para o lead, ignorando o intervalo. Só envia se o "
        "lead estiver em silêncio (a última mensagem foi do agente) e ainda houver tentativas disponíveis."
    ),
    response_model=FollowupNowOut,
    responses=NOT_FOUND,
)
async def followup_now(lead_id: LeadId) -> dict:
    await _lead_or_404(lead_id)
    result = await followups.force_for_lead(lead_id)
    return {"sent": result is not None, "followup": result}


@router.delete(
    "/leads/{lead_id}",
    tags=["leads"],
    summary="Excluir dados do lead (LGPD)",
    description=(
        "Remove o lead, mensagens, compromissos, eventos e o histórico do agente no checkpointer do LangGraph. "
        "Atende ao direito de eliminação de dados da LGPD. Registros já enviados ao CRM não são apagados."
    ),
    status_code=204,
    response_class=Response,
    responses=NOT_FOUND,
)
async def delete_lead(lead_id: LeadId) -> Response:
    if not await leads.delete(lead_id):
        raise HTTPException(404, "Lead não encontrado")
    await AsyncPostgresSaver(await get_pool()).adelete_thread(lead_id)
    return Response(status_code=204)


@router.get(
    "/appointments",
    tags=["agenda"],
    summary="Listar compromissos",
    description="Visitas e reuniões marcadas pelo agente, ordenadas por data.",
    response_model=AppointmentListOut,
)
async def list_appointments(
    upcoming: Annotated[bool, Query(description="Somente compromissos futuros (inclui as últimas 2 horas).")] = True,
) -> dict:
    return {"items": [appointment_out(a) for a in await appointments.list_all(upcoming_only=upcoming)]}


@router.post(
    "/followups/run",
    tags=["painel"],
    summary="Rodar rodada de follow-ups",
    description=(
        "Mesmo processamento do job agendado, acionado pelo painel. Com `force: true`, ignora o intervalo entre "
        "tentativas (útil em demonstrações). Também marca como perdidos os leads que esgotaram as tentativas."
    ),
    response_model=FollowupRunOut,
)
async def run_followups(payload: FollowupRunIn) -> dict:
    return await followups.run_due(force=payload.force)


@router.get(
    "/properties",
    tags=["imóveis"],
    summary="Listar imóveis do portfólio",
    description="Base simulada de imóveis usada pelo RAG do agente (filtros SQL + busca semântica no pgvector).",
    response_model=PropertyListOut,
)
async def list_properties(
    purpose: Annotated[Purpose | None, Query(description="Filtra por finalidade.")] = None,
    kind: Annotated[PropertyKind | None, Query(description="Filtra pelo tipo de imóvel.")] = None,
) -> dict:
    return {"items": [property_out(p) for p in await properties.list_all(purpose=purpose, kind=kind)]}


@router.get(
    "/agent/graph",
    tags=["agente"],
    summary="Diagrama do grafo do agente",
    description=(
        "Diagrama Mermaid gerado a partir do grafo LangGraph compilado: guardrail e extrator em paralelo, triagem, "
        "especialistas, finalize, resumo, CRM e follow-up."
    ),
    response_model=GraphOut,
)
async def agent_graph() -> dict:
    graph = await get_graph()
    return {"mermaid": graph.get_graph().draw_mermaid()}
