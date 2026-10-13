import argparse
import asyncio

from sdr.channels import telegram
from sdr.config import get_settings


async def main(base_url: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_webhook_secret:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN e TELEGRAM_WEBHOOK_SECRET no .env")
    url = base_url.rstrip("/") + "/api/telegram/webhook"
    await telegram.set_webhook(url)
    info = await telegram.call("getWebhookInfo")
    print(f"Webhook configurado: {info['url']} (pendentes: {info.get('pending_update_count', 0)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aponta o bot do Telegram para o webhook da API.")
    parser.add_argument("base_url", help="URL pública da aplicação, ex.: https://royal-sdr.vercel.app")
    asyncio.run(main(parser.parse_args().base_url))
