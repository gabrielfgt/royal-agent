from sdr.db import execute, fetch_all, fetch_one, vector_literal


async def search(query_embedding: list[float], k: int = 3) -> list[dict]:
    return await fetch_all(
        """
        SELECT source, title, content, 1 - (embedding <=> %s::vector) AS similarity
        FROM kb_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        [vector_literal(query_embedding)] * 2 + [k],
    )


async def replace_all(chunks: list[tuple[str, str, str, list[float]]]) -> None:
    await execute("DELETE FROM kb_chunks")
    for source, title, content, embedding in chunks:
        await execute(
            "INSERT INTO kb_chunks (source, title, content, embedding) VALUES (%s, %s, %s, %s::vector)",
            [source, title, content, vector_literal(embedding)],
        )


async def count() -> int:
    row = await fetch_one("SELECT count(*) AS n FROM kb_chunks")
    return row["n"]
