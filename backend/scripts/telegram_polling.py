import asyncio
import logging

import httpx

from sdr.channels import telegram
from sdr.config import get_settings
from sdr.db import close_pool
from sdr.observability import setup_logging
from sdr.repositories import throttle

log = logging.getLogger("telegram.polling")


async def main() -> None:
    setup_logging()
    if not get_settings().telegram_bot_token:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN no .env")
    await telegram.call("deleteWebhook", drop_pending_updates=False)
    me = await telegram.call("getMe")
    print(f"Bot @{me['username']} ouvindo mensagens (Ctrl+C para sair)...")
    offset = 0
    try:
        while True:
            try:
                updates = await telegram.call("getUpdates", offset=offset, timeout=25, http_timeout=35)
            except (httpx.HTTPError, RuntimeError):
                log.warning("Falha ao buscar updates do Telegram; tentando de novo em 3 s")
                await asyncio.sleep(3)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                if not await throttle.first_time_update(update["update_id"]):
                    continue
                try:
                    await telegram.handle_update(update)
                except Exception:
                    log.exception("Falha ao processar update")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
