import asyncio
import os
import sys

from scripts import migrate, seed


async def main() -> None:
    if not (os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("DATABASE_URL")):
        print("DATABASE_URL não definido no build: migrações e seed ignorados.")
        return
    await migrate.main()
    try:
        await seed.main(force=False)
    except Exception as error:
        print(
            f"Aviso: seed não concluído no build ({error}). Rode `python -m scripts.seed` manualmente.", file=sys.stderr
        )


if __name__ == "__main__":
    asyncio.run(main())
