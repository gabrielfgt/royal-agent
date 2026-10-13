import logging
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sdr import voice
from sdr.agent.prompts import LGPD_NOTICE
from sdr.agent.runtime import get_graph, run_config
from sdr.agent.state import REPLY_NODES
from sdr.db import lead_lock
from sdr.observability import flush_tracing
from sdr.presenters import property_line
from sdr.repositories import leads, messages, properties
from sdr.services import identity
from sdr.text import find_phone, split_bubbles, strip_markdown

log = logging.getLogger(__name__)

FALLBACK_REPLY = "Tive uma instabilidade rápida aqui. 😅 Pode me mandar de novo, por favor?"


@dataclass
class Inbound:
    channel: Literal["web", "telegram"]
    external_id: str
    text: str
    kind: Literal["text", "audio"] = "text"
    display_name: str | None = None


def _reply_text(update: dict) -> str | None:
    for message in reversed(update.get("messages") or []):
        if isinstance(message, AIMessage) and message.text and not message.tool_calls:
            return strip_markdown(message.text).strip()
    return None


PHOTOS_PER_PROPERTY = {"lista": 1, "detalhe": 6}
MAX_PHOTOS = 10


async def _photos_event(update: dict) -> dict | None:
    artifacts = [
        message.artifact
        for message in update.get("messages") or []
        if isinstance(message, ToolMessage) and isinstance(message.artifact, dict) and message.artifact.get("codes")
    ]
    items, seen = [], set()
    for artifact in artifacts:
        for prop in await properties.get_many(artifact["codes"]):
            limit = PHOTOS_PER_PROPERTY.get(artifact.get("mode"), 1)
            for index, url in enumerate((prop.get("photos") or [])[:limit]):
                if url in seen:
                    continue
                seen.add(url)
                caption = f"Ref. {prop['code']} · {property_line(prop).split(' | ', 1)[1]}" if index == 0 else None
                items.append({"url": url, "code": prop["code"], "caption": caption})
    return {"type": "photos", "items": items[:MAX_PHOTOS]} if items else None


async def _emit_reply(lead_id: str, text: str, *, agent: str, started: float, kind: str = "text") -> dict:
    latency_ms = int((time.perf_counter() - started) * 1000)
    stored = await messages.add(lead_id, "agent", text, kind=kind, agent=agent, latency_ms=latency_ms)
    await leads.mark_outbound(lead_id)
    return {
        "type": "reply",
        "message_id": stored["id"],
        "agent": agent,
        "bubbles": split_bubbles(text),
        "latency_ms": latency_ms,
        "text": text,
    }


async def handle(inbound: Inbound, *, voice_format: Literal["mp3", "opus"] | None = None) -> AsyncIterator[dict]:
    lead, created = await leads.get_or_create(inbound.channel, inbound.external_id, inbound.display_name)
    lead_id = str(lead["id"])
    yield {"type": "lead_id", "lead_id": lead_id}
    async with AsyncExitStack() as locks:
        await locks.enter_async_context(lead_lock(lead_id))
        await messages.add(lead_id, "lead", inbound.text, kind=inbound.kind)
        lead = await leads.mark_inbound(lead_id, inbound.channel, inbound.external_id)
        previous_inbound = lead.pop("previous_inbound_at")
        gap_seconds = (lead["last_inbound_at"] - previous_inbound).total_seconds() if previous_inbound else None
        if phone := find_phone(inbound.text):
            canonical_id = await identity.claim_phone(lead_id, phone)
            if canonical_id != lead_id:
                lead_id = canonical_id
                await locks.enter_async_context(lead_lock(lead_id))
                yield {"type": "lead_id", "lead_id": lead_id}
            lead = await leads.get(lead_id)
        if lead["ai_paused"]:
            yield {"type": "paused"}
            yield {"type": "lead", "lead": lead}
            return
        started = time.perf_counter()
        replied = notified = False
        graph = await get_graph()
        inputs = {
            "messages": [HumanMessage(inbound.text)],
            "mode": "inbound",
            "lead_id": lead_id,
            "channel": inbound.channel,
            "profile": lead["profile"] or {},
            "stage": lead["stage"],
            "gap_seconds": gap_seconds,
        }
        try:
            async for chunk in graph.astream(
                inputs, run_config(lead_id, inbound.channel, "inbound"), stream_mode="updates"
            ):
                for node, update in chunk.items():
                    if node not in REPLY_NODES or not update:
                        continue
                    if photos := await _photos_event(update):
                        yield photos
                    if not (text := _reply_text(update)):
                        continue
                    event = await _emit_reply(lead_id, text, agent=node, started=started)
                    replied = True
                    yield event
                    if voice_format:
                        yield await _audio_event(event, voice_format)
                    if created and not notified:
                        notified = True
                        notice = await messages.add(lead_id, "agent", LGPD_NOTICE, kind="notice", agent="sistema")
                        yield {"type": "notice", "message_id": notice["id"], "text": LGPD_NOTICE}
        except Exception:
            log.exception("Falha no turno do agente")
            if not replied:
                yield await _emit_reply(lead_id, FALLBACK_REPLY, agent="fallback", started=started)
        finally:
            flush_tracing()
        try:
            lead_id = await identity.link_by_phone(lead_id)
        except Exception:
            log.exception("Falha ao unificar identidade do lead")
    yield {"type": "lead", "lead": await leads.get(lead_id)}


async def _audio_event(reply: dict, audio_format: Literal["mp3", "opus"]) -> dict:
    try:
        audio = await voice.synthesize(await voice.spoken_version(reply["text"]), audio_format)
    except Exception:
        log.exception("Falha ao sintetizar voz")
        return {"type": "audio_error", "message_id": reply["message_id"]}
    mime = "audio/mpeg" if audio_format == "mp3" else "audio/ogg"
    return {"type": "audio", "message_id": reply["message_id"], "audio": audio, "mime": mime}
