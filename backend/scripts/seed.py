import argparse
import asyncio
import json
import re
from collections import Counter, defaultdict

from psycopg.types.json import Jsonb

from sdr.config import DATA_DIR, get_settings
from sdr.db import close_pool, execute, vector_literal
from sdr.finance import brl
from sdr.llm import embed
from sdr.repositories import knowledge, properties
from sdr.text import place_key

BROKERS = [
    ("carla", "Carla Mendes", "residencial", ["casa_condominio", "apartamento"]),
    ("rafael", "Rafael Lima", "residencial", ["casa", "terreno", "chacara", "comercial"]),
    ("juliana", "Juliana Prado", "investimento", []),
]

EMBED_BATCH = 64
RENT_YIELD_MONTHLY = 0.0045
RENTABLE_KINDS = {"casa", "casa_condominio", "apartamento"}
GENERATED_KB = DATA_DIR / "kb" / "bairros-e-condominios.md"


def catalog_path():
    return DATA_DIR / "catalogs" / get_settings().catalog / "imoveis.json"


def load_catalog() -> list[dict]:
    catalog = json.loads(catalog_path().read_text(encoding="utf-8"))["properties"]
    cities = Counter(prop["city"] for prop in catalog if prop.get("city"))
    main_city = cities.most_common(1)[0][0] if cities else "Não informada"
    for prop in catalog:
        prop["city"] = prop.get("city") or main_city
        prop["neighborhood"] = prop.get("neighborhood") or prop.get("condominium") or prop["city"]
    return catalog


def photo_available(photo: dict) -> bool:
    if not photo.get("file"):
        return True
    return (catalog_path().parent / photo["file"]).exists()


def property_row(prop: dict) -> dict:
    iptu = prop.get("iptu") or 0
    period = prop.get("iptu_period")
    monthly_iptu = iptu if period == "mensal" or (period is None and iptu < 400) else iptu / 12
    area = prop.get("area_private_m2") or prop.get("area_total_m2") or prop.get("area_land_m2") or 0
    condominium = prop.get("condominium")
    title = f"{prop['kind_label']} em {prop['neighborhood']}"
    if condominium and place_key(condominium) not in place_key(prop["neighborhood"]):
        title += f" ({condominium})"
    rentable = prop["purpose"] == "venda" and prop["kind"] in RENTABLE_KINDS
    return {
        "code": str(prop["code"]),
        "title": title,
        "purpose": prop["purpose"],
        "kind": prop["kind"],
        "neighborhood": prop["neighborhood"],
        "neighborhood_key": place_key(prop["neighborhood"]),
        "city": prop["city"],
        "city_key": place_key(prop["city"]),
        "state": prop.get("state") or "SP",
        "condominium": condominium,
        "condominium_key": place_key(condominium) if condominium else None,
        "street": prop.get("street"),
        "postal_code": prop.get("postal_code"),
        "latitude": prop.get("latitude"),
        "longitude": prop.get("longitude"),
        "geo_precision": prop.get("geo_precision"),
        "price": prop["price"],
        "condo_fee": prop.get("condo_fee") or 0,
        "iptu_monthly": round(monthly_iptu, 2),
        "area_m2": int(area),
        "area_total_m2": int(prop["area_total_m2"]) if prop.get("area_total_m2") else None,
        "bedrooms": prop.get("bedrooms") or 0,
        "suites": prop.get("suites") or 0,
        "bathrooms": prop.get("bathrooms") or 0,
        "parking": prop.get("parking") or 0,
        "year_built": prop.get("year_built"),
        "features": prop.get("features") or [],
        "nearby": prop.get("nearby") or [],
        "description": prop.get("description") or title,
        "estimated_rent": round(prop["price"] * RENT_YIELD_MONTHLY / 50) * 50 if rentable else None,
        "pet_friendly": True,
        "furnished": "mobiliad" in (prop.get("description") or "").lower(),
        "photos": Jsonb([photo["url"] for photo in prop.get("photos") or [] if photo_available(photo)]),
        "source_url": prop.get("url"),
        "video_url": prop.get("video_url"),
    }


def property_document(row: dict) -> str:
    place = row["neighborhood"] + (f", condomínio {row['condominium']}" if row["condominium"] else "")
    return (
        f"{row['title']} para {row['purpose']} em {place}, {row['city']}. "
        f"{row['bedrooms']} quartos ({row['suites']} suítes), {row['area_m2']} m², {row['parking']} vagas. "
        f"Características: {', '.join(row['features'])}. Perto de: {', '.join(row['nearby'])}. "
        f"{row['description'][:1500]}"
    )


def price_range(items: list[dict]) -> str:
    prices = sorted(item["price"] for item in items)
    if prices[0] == prices[-1]:
        return brl(prices[0])
    return f"de {brl(prices[0])} a {brl(prices[-1])}"


def neighborhoods_document(catalog: list[dict]) -> str:
    sale = [p for p in catalog if p["purpose"] == "venda"]
    by_condo, by_neighborhood, by_city, by_kind = (defaultdict(list) for _ in range(4))
    for prop in sale:
        if prop.get("condominium"):
            by_condo[prop["condominium"]].append(prop)
        by_neighborhood[(prop["neighborhood"], prop["city"])].append(prop)
        by_city[prop["city"]].append(prop)
        by_kind[prop["kind_label"]].append(prop)
    lines = [
        "# Bairros, condomínios e portfólio da Royal Imóveis",
        "",
        "## Cidades atendidas e tamanho do portfólio",
        f"A Royal Imóveis tem {len(sale)} imóveis à venda e "
        f"{len(catalog) - len(sale)} para locação em Tatuí e região. "
        + " ".join(
            f"{city}: {len(items)} imóvel(is)." for city, items in sorted(by_city.items(), key=lambda i: -len(i[1]))
        ),
        "",
        "## Tipos de imóvel e faixas de preço",
        *[
            f"- {kind}: {len(items)} imóvel(is), {price_range(items)}."
            for kind, items in sorted(by_kind.items(), key=lambda i: -len(i[1]))
        ],
        "",
        "## Condomínios fechados com imóveis à venda",
        *[
            f"- {condo}: {len(items)} imóvel(is) ({', '.join(sorted({i['kind_label'] for i in items}))}), "
            f"{price_range(items)}."
            for condo, items in sorted(by_condo.items(), key=lambda i: -len(i[1]))
        ],
        "",
        "## Bairros com imóveis à venda",
        *[
            f"- {name} ({city}): {len(items)} imóvel(is), {price_range(items)}."
            for (name, city), items in sorted(by_neighborhood.items(), key=lambda i: -len(i[1]))
        ],
    ]
    return "\n".join(lines) + "\n"


def kb_chunks() -> list[tuple[str, str, str]]:
    chunks = []
    for path in sorted((DATA_DIR / "kb").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for section in re.split(r"\n(?=## )", text):
            lines = section.strip().splitlines()
            if not lines or not lines[0].startswith("## "):
                continue
            chunks.append((path.stem, lines[0][3:].strip(), "\n".join(lines[1:]).strip()))
    return chunks


async def embed_all(texts: list[str]) -> list[list[float]]:
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH):
        vectors.extend(await embed(texts[start : start + EMBED_BATCH]))
    return vectors


async def seed_brokers() -> None:
    for broker_id, name, specialty, kinds in BROKERS:
        await execute(
            """
            INSERT INTO brokers (id, name, specialty, kinds) VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, specialty = EXCLUDED.specialty, kinds = EXCLUDED.kinds
            """,
            [broker_id, name, specialty, kinds],
        )
    await execute("UPDATE appointments SET broker_id = 'carla' WHERE broker_id <> ALL(%s)", [[b[0] for b in BROKERS]])
    await execute("DELETE FROM brokers WHERE id <> ALL(%s)", [[b[0] for b in BROKERS]])


async def seed_properties(force: bool) -> None:
    if not catalog_path().exists():
        print(f"Catálogo {catalog_path()} não encontrado: imóveis já existentes no banco foram mantidos.")
        return
    if not force and await properties.count():
        print("Imóveis já carregados (use --force para recarregar).")
        return
    rows = [property_row(prop) for prop in load_catalog()]
    vectors = await embed_all([property_document(row) for row in rows])
    await execute("UPDATE appointments SET property_code = NULL WHERE property_code IS NOT NULL")
    await execute("DELETE FROM properties")
    columns = list(rows[0])
    placeholders = ", ".join(f"%({column})s" for column in columns)
    for row, vector in zip(rows, vectors, strict=True):
        await execute(
            f"INSERT INTO properties ({', '.join(columns)}, embedding) VALUES ({placeholders}, %(embedding)s::vector)",
            {**row, "embedding": vector_literal(vector)},
        )
    print(f"{len(rows)} imóveis de {catalog_path().parent.name} carregados com embeddings.")


async def seed_knowledge(force: bool) -> None:
    if catalog_path().exists():
        GENERATED_KB.write_text(neighborhoods_document(load_catalog()), encoding="utf-8")
    if not force and await knowledge.count():
        print("Base de conhecimento já carregada (use --force para recarregar).")
        return
    chunks = kb_chunks()
    vectors = await embed_all([f"{title}\n{content}" for _, title, content in chunks])
    await knowledge.replace_all([(s, t, c, v) for (s, t, c), v in zip(chunks, vectors, strict=True)])
    print(f"{len(chunks)} trechos da base de conhecimento carregados.")


async def main(force: bool) -> None:
    await seed_brokers()
    await seed_properties(force)
    await seed_knowledge(force)
    await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carrega corretores, imóveis e base de conhecimento.")
    parser.add_argument("--force", action="store_true", help="Recarrega imóveis e base mesmo se já existirem.")
    asyncio.run(main(parser.parse_args().force))
