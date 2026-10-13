import argparse
import asyncio
import uuid

from sdr.api.serializers import lead_out
from sdr.db import close_pool
from sdr.observability import setup_logging
from sdr.services import conversation
from sdr.services.conversation import Inbound

DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


async def send(session: str, text: str, verbose: bool) -> None:
    async for event in conversation.handle(Inbound("web", session, text)):
        if event["type"] == "reply":
            for bubble in event["bubbles"]:
                print(f"{BOLD}Sofia{RESET} {DIM}[{event['agent']} · {event['latency_ms']} ms]{RESET}: {bubble}")
        elif event["type"] == "notice":
            print(f"{DIM}{event['text']}{RESET}")
        elif event["type"] == "lead" and verbose:
            lead = lead_out(event["lead"])
            profile = {k: v for k, v in lead["profile"].items() if v not in (None, [], "indefinido")}
            print(f"{DIM}  ↳ estágio={lead['stage']} score={lead['score']} ({lead['temperature']}) perfil={profile}")
            print(f"    falta: {lead['missing_fields']}{RESET}")


async def main(args: argparse.Namespace) -> None:
    setup_logging()
    session = args.session or uuid.uuid4().hex[:16]
    print(f"{DIM}sessão: {session}{RESET}")
    try:
        if args.script:
            for line in args.script:
                print(f"{BOLD}Lead{RESET}: {line}")
                await send(session, line, args.verbose)
            return
        while True:
            text = await asyncio.to_thread(input, f"{BOLD}Lead{RESET}: ")
            if text.strip().lower() in {"sair", "exit", "quit"}:
                break
            if text.strip():
                await send(session, text, args.verbose)
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Converse com o agente SDR pelo terminal.")
    parser.add_argument("--session", help="Reutiliza uma sessão existente.")
    parser.add_argument("--script", nargs="+", help="Mensagens do lead enviadas em sequência.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Mostra perfil e score a cada turno.")
    asyncio.run(main(parser.parse_args()))
