import logging

from fastapi import APIRouter, Depends, Request

from sdr.api.schemas import ErrorOut, FollowupRunOut, TelegramWebhookOut
from sdr.channels import telegram
from sdr.repositories import throttle
from sdr.security import require_cron, require_telegram_secret
from sdr.services import followups

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["integrações"])

UNAUTHORIZED = {401: {"model": ErrorOut, "description": "Segredo ausente ou inválido."}}

JOB_DESCRIPTION = (
    "Job idempotente de follow-up, chamado por um agendador externo (GitHub Actions a cada 30 minutos, Vercel Cron "
    "ou o serviço `scheduler` do docker compose). Seleciona leads em silêncio cujo intervalo venceu "
    "(`FOLLOWUP_DELAYS`), faz *claim* atômico, gera a retomada contextual com o grafo e entrega no canal. Leads que "
    "esgotaram as tentativas viram `perdido`. Aceita GET (Vercel Cron) e POST."
)

TELEGRAM_UPDATE_SCHEMA = {
    "type": "object",
    "description": "Objeto Update da Telegram Bot API. Apenas `message` de chats privados é processado.",
    "required": ["update_id"],
    "properties": {
        "update_id": {"type": "integer", "description": "Identificador do update (usado para deduplicação)."},
        "message": {
            "type": "object",
            "description": "Mensagem com `chat`, `from` e `text`, `voice` ou `audio`.",
            "additionalProperties": True,
        },
    },
    "example": {
        "update_id": 902114375,
        "message": {
            "message_id": 41,
            "from": {"id": 7290011122, "first_name": "Paula"},
            "chat": {"id": 7290011122, "type": "private"},
            "date": 1791857400,
            "text": "Oi! Estou procurando apartamento na zona sul.",
        },
    },
}


async def _run_followups_job() -> dict:
    result = await followups.run_due()
    log.info("Job de follow-up executado", extra={"data": {"sent": len(result["sent"]), "lost": len(result["lost"])}})
    return result


@router.get(
    "/jobs/followups",
    summary="Executar job de follow-up (GET)",
    description=JOB_DESCRIPTION,
    response_model=FollowupRunOut,
    responses=UNAUTHORIZED,
    dependencies=[Depends(require_cron)],
)
async def followups_job_get() -> dict:
    return await _run_followups_job()


@router.post(
    "/jobs/followups",
    summary="Executar job de follow-up (POST)",
    description=JOB_DESCRIPTION,
    response_model=FollowupRunOut,
    responses=UNAUTHORIZED,
    dependencies=[Depends(require_cron)],
)
async def followups_job_post() -> dict:
    return await _run_followups_job()


@router.post(
    "/telegram/webhook",
    summary="Webhook do bot do Telegram",
    description=(
        "Recebe updates do Telegram (configurado com `scripts.set_telegram_webhook`). Valida o segredo no header, "
        "deduplica por `update_id`, transcreve mensagens de voz e responde no próprio chat com balões e, quando o "
        "lead mandou áudio, com mensagem de voz. Sempre responde 200 para o Telegram não reenviar o update."
    ),
    response_model=TelegramWebhookOut,
    response_model_exclude_none=True,
    responses=UNAUTHORIZED,
    dependencies=[Depends(require_telegram_secret)],
    openapi_extra={
        "requestBody": {"required": True, "content": {"application/json": {"schema": TELEGRAM_UPDATE_SCHEMA}}}
    },
)
async def telegram_webhook(request: Request) -> dict:
    update = await request.json()
    if not await throttle.first_time_update(update.get("update_id", 0)):
        return {"ok": True, "duplicate": True}
    try:
        await telegram.handle_update(update)
    except Exception:
        log.exception("Falha ao processar update do Telegram")
    return {"ok": True}
