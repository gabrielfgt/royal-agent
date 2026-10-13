from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from sdr.config import get_settings
from sdr.llm import fast_model, openai_client
from sdr.text import speechify

TTS_INSTRUCTIONS = (
    "Voz: consultora imobiliária paulistana de uns 30 anos, simpática e confiante. "
    "Tom: caloroso, com um sorriso na voz, como quem conversa com um cliente de quem gosta. "
    "Ritmo: natural de conversa no WhatsApp, com pequenas pausas e variação de entonação; nunca soar lida. "
    "Sotaque: português brasileiro de São Paulo. Evite entonação de locutora, de URA ou de robô."
)
MAX_TTS_CHARS = 1200

SPOKEN_REWRITE = """\
Reescreva a mensagem da consultora como ela falaria num áudio de WhatsApp para o cliente.
- Linguagem falada e espontânea: frases curtas, conectores naturais ("olha", "então", "inclusive").
- Não leia códigos de imóvel nem listas. Cite no máximo dois imóveis pelo essencial (bairro, quartos, preço \
arredondado), do jeito que alguém falaria: "um de três quartos na Saúde, por uns oitocentos e sessenta mil".
- Números por extenso e naturais; "R$" vira "reais", "m²" vira "metros".
- Se a mensagem tiver lista ou detalhes, diga que deixou tudo por escrito aqui na conversa.
- Sem emojis, markdown ou parênteses. Mantenha a pergunta ou o convite final da mensagem.
- No máximo 60 palavras. Responda só com o texto a ser falado.
"""


async def transcribe(data: bytes, filename: str) -> str:
    settings = get_settings()
    result = await openai_client().audio.transcriptions.create(
        model=settings.stt_model,
        file=(filename, data),
        language="pt",
        prompt="Conversa com imobiliária sobre compra, aluguel ou investimento em imóveis em São Paulo.",
    )
    return result.text.strip()


async def spoken_version(text: str) -> str:
    response = await fast_model().ainvoke([SystemMessage(SPOKEN_REWRITE), HumanMessage(text)])
    return speechify(response.text.strip()) or speechify(text)


async def synthesize(text: str, audio_format: Literal["mp3", "opus"] = "mp3", *, voice: str | None = None) -> bytes:
    settings = get_settings()
    response = await openai_client().audio.speech.create(
        model=settings.tts_model,
        voice=voice or settings.tts_voice,
        input=text[:MAX_TTS_CHARS],
        instructions=TTS_INSTRUCTIONS,
        response_format=audio_format,
    )
    return response.content
