import asyncio

from sdr.agent.runtime import setup_checkpointer
from sdr.db import apply_schema, close_pool


async def main() -> None:
    await apply_schema()
    await setup_checkpointer()
    await close_pool()
    print("Schema e checkpointer prontos.")


if __name__ == "__main__":
    asyncio.run(main())
