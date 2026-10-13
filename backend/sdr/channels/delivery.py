import logging

from sdr.channels import telegram
from sdr.text import split_bubbles

log = logging.getLogger(__name__)


async def deliver(lead: dict, text: str) -> bool:
    channel = lead.get("last_channel") or lead["channel"]
    external_id = lead.get("last_external_id") or lead["external_id"]
    if channel == "telegram" and telegram.enabled():
        try:
            await telegram.send_bubbles(external_id, split_bubbles(text))
        except Exception:
            log.exception("Falha ao entregar mensagem no Telegram")
            return False
    return True
