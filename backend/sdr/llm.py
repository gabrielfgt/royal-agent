from functools import lru_cache

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from sdr.config import get_settings


@lru_cache
def chat_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.chat_model,
        reasoning_effort=settings.chat_reasoning_effort,
        api_key=settings.openai_api_key or None,
        max_retries=2,
    )


@lru_cache
def fast_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.fast_model,
        reasoning_effort=settings.fast_reasoning_effort,
        api_key=settings.openai_api_key or None,
        max_retries=2,
    )


@lru_cache
def openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key or None)


async def embed(texts: list[str]) -> list[list[float]]:
    response = await openai_client().embeddings.create(model=get_settings().embedding_model, input=texts)
    return [item.embedding for item in response.data]
