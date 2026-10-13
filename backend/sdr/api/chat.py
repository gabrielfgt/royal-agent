import base64
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from sdr import voice
from sdr.api.schemas import SESSION_PATTERN, ChatHistoryOut, ChatIn, ChatStreamEvent, ErrorOut
from sdr.api.serializers import lead_out, message_out
from sdr.config import get_settings
from sdr.repositories import leads, messages
from sdr.security import enforce_chat_rate_limit
from sdr.services import conversation
from sdr.services.conversation import Inbound

router = APIRouter(prefix="/api/chat", tags=["chat"])

STREAM_EXAMPLE = (
    "event: reply\n"
    'data: {"message_id": 83, "agent": "consultor", "bubbles": ["Oi! Zona sul tem ótimas opções. 😊", '
    '"Você está pensando em comprar ou alugar?"], "latency_ms": 5508}\n\n'
    "event: notice\n"
    'data: {"message_id": 84, "text": "🔒 Seus dados são usados só para este atendimento, conforme a LGPD. '
    'Se não quiser mais receber mensagens, é só enviar PARAR."}\n\n'
    "event: lead\n"
    'data: {"id": "1e454338-0360-4afa-9c3f-981782986223", "channel": "web", "stage": "em_qualificacao", '
    '"score": 20, "temperature": "frio", "intent": "indefinido", "...": "..."}\n\n'
    "event: done\n"
    "data: {}\n\n"
)

AUDIO_STREAM_EXAMPLE = (
    "event: transcript\n"
    'data: {"text": "Oi, tudo bem? Eu queria comprar um apartamento de dois quartos em Moema."}\n\n'
    "event: reply\n"
    'data: {"message_id": 86, "agent": "consultor", "bubbles": ["Oi, tudo bem? Separei opções na zona sul:", '
    '"🏠 RY-014 · Apartamento em Campo Belo · 2 dorms · 68 m² · R$ 790 mil"], "latency_ms": 7120}\n\n'
    "event: audio\n"
    'data: {"message_id": 86, "mime": "audio/mpeg", "audio_b64": "SUQzBAAAAAAAI1RTU0U..."}\n\n'
    "event: lead\n"
    'data: {"id": "7c1d...", "stage": "em_qualificacao", "score": 40, "...": "..."}\n\n'
    "event: done\n"
    "data: {}\n\n"
)

SSE_DESCRIPTION = (
    "Stream **Server-Sent Events** (`text/event-stream`). Cada evento chega como `event: <tipo>` + `data: <JSON>`, "
    "separado por linha em branco. Tipos: `transcript` (só no áudio), `reply` (balões da resposta), `audio` (voz da "
    "resposta), `notice` (aviso de privacidade no primeiro contato), `lead` (estado atualizado do lead), `paused` "
    "(IA pausada) e `done` (fim). O schema abaixo descreve cada par tipo/payload."
)

RATE_LIMITED = {429: {"model": ErrorOut, "description": "Muitas mensagens em pouco tempo para a sessão ou o IP."}}


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _stream(events: AsyncIterator[dict], transcript: str | None = None) -> AsyncIterator[str]:
    if transcript is not None:
        yield _sse("transcript", {"text": transcript})
    async for event in events:
        kind = event["type"]
        if kind == "reply":
            yield _sse("reply", {k: event[k] for k in ("message_id", "agent", "bubbles", "latency_ms")})
        elif kind == "audio":
            yield _sse(
                "audio",
                {
                    "message_id": event["message_id"],
                    "mime": event["mime"],
                    "audio_b64": base64.b64encode(event["audio"]).decode(),
                },
            )
        elif kind == "notice":
            yield _sse("notice", {"message_id": event["message_id"], "text": event["text"]})
        elif kind == "lead":
            yield _sse("lead", lead_out(event["lead"]))
        elif kind == "paused":
            yield _sse("paused", {})
    yield _sse("done", {})


def _sse_response(body: AsyncIterator[str]) -> EventStreamResponse:
    return EventStreamResponse(body, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _stream_responses(example: str) -> dict:
    return {
        200: {
            "model": ChatStreamEvent,
            "description": SSE_DESCRIPTION,
            "content": {"text/event-stream": {"example": example}},
        },
        **RATE_LIMITED,
    }


@router.post(
    "/stream",
    summary="Enviar mensagem de texto (resposta em streaming)",
    description=(
        "Entrada do chat web. Identifica (ou cria) o lead pela `session_id`, executa um turno do agente LangGraph "
        "e devolve a resposta em **SSE** assim que o especialista termina — o resumo e a sincronização com o CRM "
        "continuam no mesmo stream sem atrasar os balões. Turnos do mesmo lead são serializados com *advisory lock*. "
        "Mensagem vazia após remover espaços retorna 422 com `detail` em texto."
    ),
    response_class=EventStreamResponse,
    responses=_stream_responses(STREAM_EXAMPLE),
)
async def chat_stream(payload: ChatIn, request: Request) -> EventStreamResponse:
    settings = get_settings()
    text = payload.message.strip()[: settings.max_message_chars]
    if not text:
        raise HTTPException(422, "Mensagem vazia")
    await enforce_chat_rate_limit(request, payload.session_id)
    inbound = Inbound("web", payload.session_id, text, display_name=payload.name)
    return _sse_response(_stream(conversation.handle(inbound)))


@router.post(
    "/audio",
    summary="Enviar mensagem de voz (transcrição + resposta em voz)",
    description=(
        "Recebe um áudio gravado no navegador (webm/opus, m4a, ogg, mp3 ou wav, até 4 MB), transcreve, executa o "
        "turno do agente e devolve o mesmo stream SSE do texto, começando por `transcript`. Com "
        "`reply_with_audio=true`, a resposta também vem em voz (evento `audio`, MP3 em base64). Áudio vazio ou "
        "incompreensível retorna 422 com `detail` em texto."
    ),
    response_class=EventStreamResponse,
    responses={
        **_stream_responses(AUDIO_STREAM_EXAMPLE),
        413: {"model": ErrorOut, "description": "Áudio maior que o limite (`MAX_AUDIO_BYTES`)."},
    },
)
async def chat_audio(
    request: Request,
    session_id: Annotated[
        str,
        Form(
            pattern=SESSION_PATTERN,
            description="Identificador da sessão do navegador (o mesmo usado no chat de texto).",
            examples=["a8f3k2m9x7q1w5e4r6t0y2u3"],
        ),
    ],
    file: Annotated[UploadFile, File(description="Arquivo de áudio com a fala do lead.")],
    reply_with_audio: Annotated[bool, Form(description="Se a resposta também deve vir em voz.")] = True,
) -> EventStreamResponse:
    settings = get_settings()
    await enforce_chat_rate_limit(request, session_id)
    data = await file.read()
    if not data:
        raise HTTPException(422, "Áudio vazio")
    if len(data) > settings.max_audio_bytes:
        raise HTTPException(413, "Áudio muito longo")
    transcript = await voice.transcribe(data, file.filename or "audio.webm")
    if not transcript:
        raise HTTPException(422, "Não consegui entender o áudio")
    inbound = Inbound("web", session_id, transcript[: settings.max_message_chars], kind="audio")
    events = conversation.handle(inbound, voice_format="mp3" if reply_with_audio else None)
    return _sse_response(_stream(events, transcript=transcript))


@router.get(
    "/{session_id}/messages",
    summary="Histórico da conversa da sessão",
    description=(
        "Restaura o chat ao recarregar a página e permite *polling* incremental: envie o maior `id` já exibido em "
        "`after_id` para receber só as novas mensagens — é assim que follow-ups automáticos aparecem no chat web."
    ),
    response_model=ChatHistoryOut,
)
async def chat_messages(
    session_id: Annotated[
        str,
        Path(
            pattern=SESSION_PATTERN,
            description="Identificador da sessão do navegador.",
            examples=["a8f3k2m9x7q1w5e4r6t0y2u3"],
        ),
    ],
    after_id: Annotated[int, Query(ge=0, description="Retorna apenas mensagens com id maior que este.")] = 0,
) -> dict:
    lead = await leads.get_by_external("web", session_id)
    if lead is None:
        return {"lead": None, "messages": []}
    history = await messages.list_for_lead(str(lead["id"]), after_id=after_id)
    return {"lead": lead_out(lead), "messages": [message_out(m) for m in history]}
