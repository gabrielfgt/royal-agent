import re
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"

_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_durations(spec: str) -> list[int]:
    seconds = []
    for part in spec.split(","):
        match = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", part)
        if not match:
            raise ValueError(f"Duração inválida: {part!r} (use ex.: 30m, 1d)")
        seconds.append(int(match[1]) * _DURATION_UNITS[match[2]])
    return seconds


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    database_url: str = Field(
        "postgresql://sdr:sdr@localhost:5432/sdr",
        validation_alias=AliasChoices("DATABASE_URL_UNPOOLED", "DATABASE_URL"),
    )
    db_pool_max_size: int = 5

    openai_api_key: str = ""
    chat_model: str = "gpt-6-luna"
    chat_reasoning_effort: str = "low"
    fast_model: str = "gpt-6-luna"
    fast_reasoning_effort: str = "none"
    embedding_model: str = "text-embedding-3-small"
    stt_model: str = "gpt-4o-mini-transcribe"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "marin"

    company_name: str = "Royal Imóveis"
    company_region: str = "Tatuí e região, no interior de São Paulo"
    catalog: str = "parceiro"
    agent_name: str = "Sofia"
    timezone: str = "America/Sao_Paulo"
    history_window: int = 30

    followup_delays: str = "20m,1d,3d"
    followup_lost_after: str = "2d"

    dashboard_token: str = "royal-demo"
    cron_secret: str = "local-cron"
    cors_origins: str = "http://localhost:5173"
    chat_rate_limit_per_minute: int = 20
    max_message_chars: int = 1500
    max_audio_bytes: int = 4_000_000

    telegram_bot_token: str = Field("", validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_ACCESS_TOKEN"))
    telegram_webhook_secret: str = ""

    hubspot_token: str = Field("", validation_alias=AliasChoices("HUBSPOT_TOKEN", "HUBSPOT_ACCESS_TOKEN"))
    hubspot_portal_id: str = ""

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = Field(
        "https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def followup_delay_seconds(self) -> list[int]:
        return parse_durations(self.followup_delays)

    @property
    def followup_lost_after_seconds(self) -> int:
        return parse_durations(self.followup_lost_after)[0]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
