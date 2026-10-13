import json
import logging
import sys
from functools import lru_cache

from sdr.config import get_settings
from sdr.security import mask_data, mask_pii


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": mask_pii(record.getMessage()),
        }
        if extra := getattr(record, "data", None):
            payload["data"] = mask_data(extra)
        if record.exc_info:
            payload["exception"] = mask_pii(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for noisy in ("httpx", "httpx2", "httpcore", "openai", "psycopg.pool"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


@lru_cache
def _langfuse_client():
    from langfuse import Langfuse

    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
        mask=mask_data,
        environment="production" if "neon" in settings.database_url else "local",
    )


def tracing_callbacks() -> list:
    settings = get_settings()
    if not settings.tracing_enabled:
        return []
    from langfuse.langchain import CallbackHandler

    _langfuse_client()
    return [CallbackHandler(public_key=settings.langfuse_public_key)]


def flush_tracing() -> None:
    if get_settings().tracing_enabled:
        _langfuse_client().flush()
