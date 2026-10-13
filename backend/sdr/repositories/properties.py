import re
from dataclasses import dataclass, field

from sdr.db import fetch_all, fetch_one, vector_literal
from sdr.text import place_keys

PUBLIC_COLUMNS = """
    code, title, purpose, kind, neighborhood, city, state, condominium, street, postal_code, latitude, longitude,
    geo_precision, price, condo_fee, iptu_monthly, area_m2, area_total_m2, bedrooms, suites, bathrooms, parking,
    year_built, features, nearby, description, estimated_rent, pet_friendly, furnished, photos, source_url, video_url
"""


@dataclass
class PropertyFilters:
    purpose: str
    regions: list[str] = field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    bedrooms_min: int | None = None
    parking_min: int | None = None
    kind: str | None = None
    pet_friendly: bool | None = None
    exclude_codes: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    items: list[dict]
    relaxed: list[str]


def _where(filters: PropertyFilters, *, located: bool, budget_factor: float, bedrooms_delta: int):
    clauses, params = ["purpose = %s"], [filters.purpose]
    keys = place_keys(filters.regions)
    if located and keys:
        patterns = [f"%{key}%" for key in keys]
        clauses.append("(neighborhood_key LIKE ANY(%s) OR condominium_key LIKE ANY(%s) OR city_key = ANY(%s))")
        params.extend([patterns, patterns, keys])
    if filters.price_max:
        clauses.append("price <= %s")
        params.append(filters.price_max * budget_factor)
    if filters.price_min:
        clauses.append("price >= %s")
        params.append(filters.price_min * 0.8)
    if filters.bedrooms_min:
        clauses.append("bedrooms >= %s")
        params.append(max(filters.bedrooms_min - bedrooms_delta, 0))
    if filters.parking_min:
        clauses.append("parking >= %s")
        params.append(filters.parking_min)
    if filters.kind:
        clauses.append("kind = %s")
        params.append(filters.kind)
    if filters.pet_friendly:
        clauses.append("pet_friendly")
    if filters.exclude_codes:
        clauses.append("code <> ALL(%s)")
        params.append(filters.exclude_codes)
    return " AND ".join(clauses), params


RELAXATION_STEPS = [
    ("", dict(located=True, budget_factor=1.0, bedrooms_delta=0)),
    ("orçamento até 15% acima do teto", dict(located=True, budget_factor=1.15, bedrooms_delta=0)),
    ("outros bairros e condomínios da região", dict(located=False, budget_factor=1.15, bedrooms_delta=0)),
    ("um quarto a menos", dict(located=False, budget_factor=1.15, bedrooms_delta=1)),
]


async def search(filters: PropertyFilters, query_embedding: list[float] | None, limit: int = 3) -> SearchResult:
    order = "embedding <=> %s::vector" if query_embedding else "price DESC"
    for label, step in RELAXATION_STEPS:
        where, params = _where(filters, **step)
        if query_embedding:
            params.append(vector_literal(query_embedding))
        params.append(limit)
        rows = await fetch_all(
            f"SELECT {PUBLIC_COLUMNS} FROM properties WHERE {where} ORDER BY {order} LIMIT %s", params
        )
        if rows:
            return SearchResult(items=rows, relaxed=[label] if label else [])
    return SearchResult(items=[], relaxed=[])


def normalize_code(raw: str) -> str:
    cleaned = re.sub(r"(?i)^\s*(ref\.?|refer[eê]ncia|c[oó]digo|ry-)\s*", "", raw.strip())
    return cleaned.strip(" .#").upper()


async def get(code: str) -> dict | None:
    return await fetch_one(f"SELECT {PUBLIC_COLUMNS} FROM properties WHERE code = %s", [normalize_code(code)])


async def list_all(*, purpose: str | None = None, kind: str | None = None) -> list[dict]:
    return await fetch_all(
        f"""
        SELECT {PUBLIC_COLUMNS} FROM properties
        WHERE (%s::text IS NULL OR purpose = %s) AND (%s::text IS NULL OR kind = %s)
        ORDER BY price
        """,
        [purpose, purpose, kind, kind],
    )


async def get_many(codes: list[str]) -> list[dict]:
    rows = await fetch_all(f"SELECT {PUBLIC_COLUMNS} FROM properties WHERE code = ANY(%s)", [codes])
    by_code = {row["code"]: row for row in rows}
    return [by_code[code] for code in codes if code in by_code]


async def count() -> int:
    row = await fetch_one("SELECT count(*) AS n FROM properties")
    return row["n"]
