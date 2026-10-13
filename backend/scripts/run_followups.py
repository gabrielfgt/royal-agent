import argparse
import asyncio

from sdr.db import close_pool
from sdr.observability import setup_logging
from sdr.services import followups


async def main(force: bool) -> None:
    setup_logging()
    try:
        result = await followups.run_due(force=force)
    finally:
        await close_pool()
    for item in result["sent"]:
        print(f"[lead {item['lead_id'][:8]} · tentativa {item['attempt']}] {item['text']}")
    print(f"{len(result['sent'])} follow-up(s) enviados, {len(result['lost'])} lead(s) marcados como perdidos.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Executa a rodada de follow-ups automáticos.")
    parser.add_argument("--force", action="store_true", help="Ignora o intervalo mínimo entre tentativas (demo).")
    asyncio.run(main(parser.parse_args().force))
