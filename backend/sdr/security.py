import re
import secrets
from typing import Annotated, Any

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from sdr.config import get_settings
from sdr.repositories import throttle

PII_PATTERNS = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"), "[TELEFONE]"),
]


def mask_pii(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_data(data: Any, **_: Any) -> Any:
    if isinstance(data, str):
        return mask_pii(data)
    if isinstance(data, dict):
        return {key: mask_data(value) for key, value in data.items()}
    if isinstance(data, list | tuple):
        return [mask_data(value) for value in data]
    return data


dashboard_auth = HTTPBearer(
    scheme_name="TokenPainel",
    description="Token do painel comercial (`DASHBOARD_TOKEN`). Envie `Authorization: Bearer <token>`.",
    auto_error=False,
)
cron_auth = HTTPBearer(
    scheme_name="CronSecret",
    description="Segredo do agendador (`CRON_SECRET`), usado pelo GitHub Actions ou pela Vercel Cron.",
    auto_error=False,
)
telegram_auth = APIKeyHeader(
    name="X-Telegram-Bot-Api-Secret-Token",
    scheme_name="TelegramWebhookSecret",
    description="Segredo (`TELEGRAM_WEBHOOK_SECRET`) que o Telegram envia em cada chamada do webhook.",
    auto_error=False,
)


def _bearer(credentials: HTTPAuthorizationCredentials | None) -> str:
    return credentials.credentials.strip() if credentials else ""


def require_dashboard(credentials: Annotated[HTTPAuthorizationCredentials | None, Security(dashboard_auth)]) -> None:
    expected = get_settings().dashboard_token
    if not secrets.compare_digest(_bearer(credentials), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token do painel inválido")


def require_cron(credentials: Annotated[HTTPAuthorizationCredentials | None, Security(cron_auth)]) -> None:
    expected = get_settings().cron_secret
    if not expected or not secrets.compare_digest(_bearer(credentials), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cron não autorizado")


def require_telegram_secret(secret: Annotated[str | None, Security(telegram_auth)]) -> None:
    expected = get_settings().telegram_webhook_secret
    if not expected or not secrets.compare_digest(secret or "", expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Webhook não autorizado")


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


async def enforce_chat_rate_limit(request: Request, session_id: str) -> None:
    limit = get_settings().chat_rate_limit_per_minute
    for key in (f"chat:session:{session_id}", f"chat:ip:{client_ip(request)}"):
        if await throttle.hit_rate_limit(key, limit if key.startswith("chat:session") else limit * 3):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas mensagens em pouco tempo")
