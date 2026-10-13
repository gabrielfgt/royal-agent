from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sdr.api import chat, dashboard, integrations
from sdr.api.schemas import HealthOut
from sdr.config import get_settings
from sdr.db import close_pool, fetch_one, get_pool
from sdr.observability import setup_logging

DESCRIPTION = """
API do **Royal SDR**, agente SDR imobiliário com IA (POC do Hackathon FIAP — Tech Challenge Fase 5).

A Sofia, consultora virtual da Royal Imóveis, atende leads pelo chat web e pelo Telegram (texto e voz),
qualifica compra, aluguel ou investimento, apresenta imóveis da base simulada (RAG), agenda visitas,
faz follow-up automático e entrega ao corretor um resumo pronto, sincronizado com o HubSpot.

### Como o agente funciona
Cada mensagem passa por um grafo **LangGraph**: guardrail e extrator de perfil rodam em paralelo, uma triagem
determinística escolhe o especialista (recepção, consultora residencial, investimentos ou agendamento), o nó
`finalize` recalcula score e estágio, e o lead que avança ganha resumo e registro no CRM. O histórico fica no
checkpointer Postgres (`thread_id = lead_id`) e o perfil estruturado é persistido a cada turno.

### Autenticação
| Rotas | Esquema | Como enviar |
|---|---|---|
| `/api/chat/*`, `/api/health` | pública (rate limit por sessão e IP) | — |
| Painel, leads, agenda, imóveis, agente | `TokenPainel` | `Authorization: Bearer <DASHBOARD_TOKEN>` |
| `/api/jobs/followups` | `CronSecret` | `Authorization: Bearer <CRON_SECRET>` |
| `/api/telegram/webhook` | `TelegramWebhookSecret` | header `X-Telegram-Bot-Api-Secret-Token` |

Use o botão **Authorize** para testar as rotas protegidas (no ambiente local, o token do painel é `royal-demo`).

### Fluxos principais
1. **Chat web** — `POST /api/chat/stream` (ou `/api/chat/audio`) devolve a resposta em *Server-Sent Events*:
   `reply` com os balões assim que o especialista termina, `audio` com a voz, `notice` com o aviso de
   privacidade no primeiro contato, `lead` com o estado atualizado e `done`. O histórico e os follow-ups chegam
   por `GET /api/chat/{session_id}/messages?after_id=`.
2. **Follow-up** — um agendador chama `/api/jobs/followups`; leads em silêncio recebem até 3 retomadas
   contextuais (`FOLLOWUP_DELAYS`) e, sem resposta, viram `perdido`.
3. **Telegram** — o bot entrega updates em `/api/telegram/webhook`; o mesmo serviço de conversa responde no chat,
   com voz quando o lead manda áudio.

### LGPD e segurança
Aviso de privacidade no primeiro contato, opt-out com **PARAR**, exclusão completa dos dados do lead
(`DELETE /api/leads/{lead_id}`), mascaramento de CPF, e-mail e telefone em logs e traces, guardrail contra
*prompt injection* e limites de tamanho para mensagens e áudios.
"""

TAGS = [
    {"name": "chat", "description": "Conversa do lead com a Sofia pelo site: texto, voz e histórico (SSE)."},
    {"name": "painel", "description": "Login, métricas do funil e rodada manual de follow-ups."},
    {"name": "leads", "description": "Leads qualificados pela IA: perfil, resumo, transcrição, pausa e LGPD."},
    {"name": "agenda", "description": "Visitas e reuniões marcadas pelo agente de agendamento."},
    {"name": "imóveis", "description": "Portfólio simulado usado pelo RAG do agente."},
    {"name": "agente", "description": "Introspecção do grafo LangGraph."},
    {"name": "integrações", "description": "Job de follow-up (cron) e webhook do Telegram."},
    {"name": "infra", "description": "Saúde da API e das integrações configuradas."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Royal SDR — Agente SDR Imobiliário",
    summary="Agente de IA que atende, qualifica, agenda e faz follow-up de leads imobiliários.",
    description=DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "docExpansion": "list",
        "tryItOutEnabled": True,
        "filter": True,
        "defaultModelsExpandDepth": 1,
    },
    license_info={"name": "Uso acadêmico — Hackathon FIAP"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(integrations.router)

_base_openapi = app.openapi


def _openapi() -> dict:
    schema = _base_openapi()
    for operations in schema["paths"].values():
        for operation in operations.values():
            for response in operation.get("responses", {}).values():
                stream = response.get("content", {}).get("text/event-stream", {}).get("schema", {})
                if "$ref" in stream:
                    stream.pop("type", None)
    return schema


app.openapi = _openapi


@app.get(
    "/api/health",
    tags=["infra"],
    summary="Saúde da API",
    description="Verifica a conexão com o banco e informa o modelo em uso e quais integrações estão configuradas.",
    response_model=HealthOut,
)
async def health() -> dict:
    await fetch_one("SELECT 1")
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.chat_model,
        "telegram": bool(settings.telegram_bot_token),
        "crm": bool(settings.hubspot_token),
        "tracing": settings.tracing_enabled,
    }
