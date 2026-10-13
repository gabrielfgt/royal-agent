from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from sdr.agent.graph import build_graph
from sdr.db import get_pool
from sdr.observability import tracing_callbacks

_graph = None


async def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer=AsyncPostgresSaver(await get_pool()))
    return _graph


async def setup_checkpointer() -> None:
    await AsyncPostgresSaver(await get_pool()).setup()


def run_config(lead_id: str, channel: str, *tags: str) -> dict:
    return {
        "configurable": {"thread_id": str(lead_id)},
        "recursion_limit": 50,
        "callbacks": tracing_callbacks(),
        "metadata": {
            "langfuse_session_id": str(lead_id),
            "langfuse_user_id": str(lead_id),
            "langfuse_tags": [channel, *tags],
            "channel": channel,
        },
    }
