import asyncio
import json
import logging
import re

import httpx

from sdr import voice
from sdr.config import get_settings
from sdr.services import conversation
from sdr.services.conversation import Inbound
from sdr.text import split_bubbles

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/{method}"
FILE_URL = "https://api.telegram.org/file/bot{token}/{path}"
MAX_CAPTION = 1000
ASKS_PHONE = re.compile(r"\b(telefone|whats(app)?|celular|n[uú]mero|contato)\b", re.IGNORECASE)
CONTACT_KEYBOARD = {
    "keyboard": [[{"text": "📱 Compartilhar meu contato", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}
REMOVE_KEYBOARD = {"remove_keyboard": True}
UNSUPPORTED_REPLY = "Por enquanto eu entendo mensagens de texto e áudio. 🙂 Me conta por aqui o que você procura?"


def enabled() -> bool:
    return bool(get_settings().telegram_bot_token)


async def call(method: str, *, files: dict | None = None, http_timeout: float = 30, **payload) -> dict:
    url = API_URL.format(token=get_settings().telegram_bot_token, method=method)
    async with httpx.AsyncClient(timeout=http_timeout) as client:
        if files:
            response = await client.post(url, data=payload, files=files)
        else:
            response = await client.post(url, json=payload)
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method} falhou: {body.get('description')}")
    return body["result"]


async def send_typing(chat_id: int | str, action: str = "typing") -> None:
    try:
        await call("sendChatAction", chat_id=chat_id, action=action)
    except Exception:
        log.warning("Falha ao enviar 'digitando'")


def reply_markup_for(text: str, *, contact_received: bool) -> dict | None:
    if ASKS_PHONE.search(text) and "?" in text:
        return CONTACT_KEYBOARD
    return REMOVE_KEYBOARD if contact_received else None


async def send_bubbles(chat_id: int | str, bubbles: list[str], *, contact_received: bool = False) -> None:
    for index, bubble in enumerate(bubbles):
        if index:
            await send_typing(chat_id)
            await asyncio.sleep(min(0.4 + len(bubble) / 120, 1.6))
        payload = {"chat_id": chat_id, "text": bubble}
        if index == len(bubbles) - 1 and (markup := reply_markup_for(bubble, contact_received=contact_received)):
            payload["reply_markup"] = markup
        await call("sendMessage", **payload)


async def send_photos(chat_id: int | str, items: list[dict]) -> None:
    media = [
        {"type": "photo", "media": item["url"], **({"caption": item["caption"]} if item.get("caption") else {})}
        for item in items[:10]
    ]
    await send_typing(chat_id, "upload_photo")
    try:
        if len(media) == 1:
            await call("sendPhoto", chat_id=chat_id, photo=media[0]["media"], caption=media[0].get("caption", ""))
        else:
            await call("sendMediaGroup", chat_id=chat_id, media=media)
    except Exception:
        log.warning("Telegram não buscou as fotos pela URL; enviando por upload")
        await _upload_photos(chat_id, media)


async def _upload_photos(chat_id: int | str, media: list[dict]) -> None:
    files = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for index, item in enumerate(media):
            response = await client.get(item["media"])
            response.raise_for_status()
            files[f"foto{index}"] = (f"foto{index}.jpg", response.content, "image/jpeg")
            item["media"] = f"attach://foto{index}"
    if len(media) == 1:
        await call(
            "sendPhoto", files={"photo": files["foto0"]}, chat_id=str(chat_id), caption=media[0].get("caption", "")
        )
    else:
        await call("sendMediaGroup", files=files, chat_id=str(chat_id), media=json.dumps(media, ensure_ascii=False))


async def send_voice(chat_id: int | str, audio: bytes, caption: str | None = None) -> None:
    payload = {"chat_id": str(chat_id)}
    if caption:
        payload["caption"] = caption
    await call("sendVoice", files={"voice": ("resposta.ogg", audio, "audio/ogg")}, **payload)


async def download_file(file_id: str) -> bytes:
    info = await call("getFile", file_id=file_id)
    url = FILE_URL.format(token=get_settings().telegram_bot_token, path=info["file_path"])
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def handle_update(update: dict) -> None:
    message = update.get("message")
    if not message or message.get("chat", {}).get("type") != "private":
        return
    chat_id = message["chat"]["id"]
    name = message.get("from", {}).get("first_name")
    await send_typing(chat_id)

    media = message.get("voice") or message.get("audio")
    contact = message.get("contact")
    if contact and contact.get("user_id") == message.get("from", {}).get("id"):
        text = f"Meu telefone é {contact['phone_number']}"
        kind = "text"
    elif media:
        if media.get("file_size", 0) > get_settings().max_audio_bytes:
            await call(
                "sendMessage",
                chat_id=chat_id,
                text="Esse áudio ficou um pouco longo. Consegue mandar um mais curtinho?",
            )
            return
        text = await voice.transcribe(await download_file(media["file_id"]), "audio.ogg")
        kind = "audio"
    elif raw := message.get("text"):
        text = "Olá!" if raw.startswith("/start") else raw[: get_settings().max_message_chars]
        kind = "text"
    else:
        await call("sendMessage", chat_id=chat_id, text=UNSUPPORTED_REPLY)
        return

    pending_text: str | None = None
    inbound = Inbound("telegram", str(chat_id), text, kind=kind, display_name=name)
    async for event in conversation.handle(inbound, voice_format="opus" if kind == "audio" else None):
        if event["type"] == "reply":
            if kind == "audio":
                pending_text = event["text"]
            else:
                await send_bubbles(chat_id, event["bubbles"], contact_received=bool(contact))
        elif event["type"] == "audio" and pending_text:
            caption = pending_text if len(pending_text) <= MAX_CAPTION else None
            await send_voice(chat_id, event["audio"], caption)
            if caption is None:
                await send_bubbles(chat_id, split_bubbles(pending_text))
            pending_text = None
        elif event["type"] == "audio_error" and pending_text:
            await send_bubbles(chat_id, split_bubbles(pending_text))
            pending_text = None
        elif event["type"] == "photos":
            await send_photos(chat_id, event["items"])
        elif event["type"] == "notice":
            await call("sendMessage", chat_id=chat_id, text=event["text"])


async def set_webhook(url: str) -> dict:
    return await call(
        "setWebhook",
        url=url,
        secret_token=get_settings().telegram_webhook_secret,
        allowed_updates=["message"],
        drop_pending_updates=True,
    )
