import argparse
import asyncio
import html
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from sdr.config import DATA_DIR

USER_AGENT = "royal-sdr-importer/0.1 (+https://github.com; importador de catalogo para POC de agente SDR)"
BROWSER_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
SITE_PAGES = ["sobre", "financiamento", "correspondente", "contato", "seu-imovel"]

KINDS = {
    "casa em condominio": "casa_condominio",
    "casa": "casa",
    "apartamento": "apartamento",
    "terreno": "terreno",
    "chacara": "chacara",
    "comercial": "comercial",
    "fazenda": "fazenda",
}


def slug(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", stripped).strip("-")


def money(value: str | None) -> float | None:
    if not value:
        return None
    digits = re.sub(r"[^\d,]", "", value).replace(",", ".")
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:\.\d{3})*(?:,\d+)?", value)
    return float(match[0].replace(".", "").replace(",", ".")) if match else None


def visible_lines(page: str) -> list[str]:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    text = html.unescape(re.sub(r"<br\s*/?>", "\n", text))
    text = re.sub(r"<[^>]+>", "\n", text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_llms_entry(block: str) -> dict:
    fields = dict(re.findall(r"^- ([^:\n]+): (.+)$", block, flags=re.M))
    basics = dict(re.findall(r"^  - (Dormitórios|Banheiros|Vagas de garagem|Suítes): (\d+)", block, flags=re.M))
    areas = dict(re.findall(r"^  - (Área [^:]+): ([\d.,]+)", block, flags=re.M))

    def section(name: str) -> list[str]:
        match = re.search(rf"^- {name}:\n((?:  - .+\n?)+)", block, flags=re.M)
        return [item.strip()[2:] for item in match[1].splitlines()] if match else []

    fees = fields.get("Taxas", "")
    link = re.search(r"\[Ver imóvel completo\]\(([^)]+)\)", block)
    return {
        "code": fields.get("Referência", "").strip(),
        "kind_label": fields.get("Tipo", "").strip(),
        "purpose": "aluguel" if "loca" in fields.get("Finalidade", "") else "venda",
        "city": fields.get("Cidade", "").strip(),
        "neighborhood": fields.get("Bairro", "").strip(),
        "condominium": (fields.get("Condomínio") or "").strip() or None,
        "price": money(fields.get("Valor")),
        "condo_fee": money(m[1]) if (m := re.search(r"Condomínio: R\$ ([\d.,]+)", fees)) else None,
        "iptu": money(m[1]) if (m := re.search(r"IPTU: R\$ ([\d.,]+)", fees)) else None,
        "bedrooms": int(basics.get("Dormitórios", 0)),
        "suites": int(basics.get("Suítes", 0)),
        "bathrooms": int(basics.get("Banheiros", 0)),
        "parking": int(basics.get("Vagas de garagem", 0)),
        "area_private_m2": number(areas.get("Área privativa") or areas.get("Área útil")),
        "area_total_m2": number(areas.get("Área total")),
        "area_land_m2": number(areas.get("Área do terreno")),
        "price_per_m2": money(fields.get("Valor por m²")),
        "features": section("Gerais"),
        "nearby": section("Proximidades"),
        "description": fields.get("Descrição", "").strip(),
        "photos": re.findall(r"!\[[^\]]*\]\(([^)]+)\)", block),
        "url": link[1] if link else None,
    }


def parse_page(page: str) -> dict:
    data: dict = {}
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, flags=re.S):
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("@type") in ("BuyAction", "RentAction"):
            address = (item.get("object") or {}).get("address") or {}
            data["street"] = address.get("streetAddress")
            data["postal_code"] = address.get("postalCode")
            data["state"] = address.get("addressRegion")
            data["title"] = html.unescape((item.get("object") or {}).get("name") or "")
    photos = []
    for src in re.findall(r'<img class="item-lista" src="([^"]+)"', page):
        if src not in photos:
            photos.append(src)
    data["photos"] = photos
    lines = visible_lines(page)

    def after(label: str) -> str | None:
        for index, line in enumerate(lines[:-1]):
            if line == label:
                return lines[index + 1]
        return None

    data["year_built"] = int(year) if (year := after("Construído em:")) and year.isdigit() else None
    data["iptu_note"] = after("Observação Valor:")
    if "Descrição do Imóvel" in lines:
        start = lines.index("Descrição do Imóvel") + 1
        end = next((i for i in range(start, len(lines)) if lines[i] in ("Características", "Proximidades")), start)
        data["description"] = "\n".join(lines[start:end]).strip()
    video = re.search(r"(?:youtube\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)([\w-]{6,})", page)
    data["video_url"] = f"https://www.youtube.com/watch?v={video[1]}" if video else None
    return data


def normalize(entry: dict, page: dict, source_id: str) -> dict:
    kind = KINDS.get(slug(entry["kind_label"]).replace("-", " "), slug(entry["kind_label"]).replace("-", "_"))
    note = (page.get("iptu_note") or "").lower()
    return {
        "source_id": source_id,
        "code": entry["code"],
        "url": entry["url"],
        "title": page.get("title") or f"{entry['kind_label']} em {entry['neighborhood']}, {entry['city']}",
        "purpose": entry["purpose"],
        "kind": kind,
        "kind_label": entry["kind_label"],
        "city": entry["city"],
        "state": page.get("state") or "SP",
        "neighborhood": entry["neighborhood"],
        "condominium": entry["condominium"],
        "street": page.get("street"),
        "postal_code": page.get("postal_code"),
        "price": entry["price"],
        "condo_fee": entry["condo_fee"],
        "iptu": entry["iptu"],
        "iptu_period": "anual" if "anual" in note else ("mensal" if "mensal" in note else None),
        "bedrooms": entry["bedrooms"],
        "suites": entry["suites"],
        "bathrooms": entry["bathrooms"],
        "parking": entry["parking"],
        "area_private_m2": entry["area_private_m2"],
        "area_total_m2": entry["area_total_m2"],
        "area_land_m2": entry["area_land_m2"],
        "year_built": page.get("year_built"),
        "price_per_m2": entry["price_per_m2"],
        "features": entry["features"],
        "nearby": entry["nearby"],
        "description": page.get("description") or entry["description"],
        "video_url": page.get("video_url"),
        "photos": [{"url": url} for url in (page.get("photos") or entry["photos"])],
    }


async def fetch_text(client: httpx.AsyncClient, url: str, attempts: int = 3) -> str:
    for attempt in range(attempts):
        try:
            response = await client.get(url)
            response.raise_for_status()
            if "utf-8" not in response.headers.get("content-type", "").lower() and not url.endswith(".txt"):
                return response.content.decode("iso-8859-1")
            return response.content.decode("utf-8-sig")
        except httpx.HTTPError:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


async def download_photo(client: httpx.AsyncClient, url: str, target: Path, gate: asyncio.Semaphore) -> bool:
    if target.exists() and target.stat().st_size > 0:
        return True
    async with gate:
        for attempt in range(3):
            try:
                response = await client.get(url)
                response.raise_for_status()
                target.write_bytes(response.content)
                return True
            except httpx.HTTPError:
                await asyncio.sleep(1.5 * (attempt + 1))
    return False


async def geocode(client: httpx.AsyncClient, prop: dict, cache: dict) -> None:
    queries = []
    if prop.get("street"):
        queries.append(
            (
                "endereco",
                {
                    "street": prop["street"],
                    "city": prop["city"],
                    "state": prop["state"],
                    "country": "Brasil",
                    "postalcode": prop.get("postal_code") or "",
                },
            )
        )
    queries.append(("bairro", {"q": f"{prop['neighborhood']}, {prop['city']}, {prop['state']}, Brasil"}))
    queries.append(("cidade", {"q": f"{prop['city']}, {prop['state']}, Brasil"}))
    for precision, params in queries:
        key = json.dumps(params, sort_keys=True, ensure_ascii=False)
        if key not in cache:
            await asyncio.sleep(1.1)
            response = await client.get(NOMINATIM_URL, params={**params, "format": "jsonv2", "limit": 1})
            cache[key] = response.json() if response.status_code == 200 else []
        if cache[key]:
            prop["latitude"] = float(cache[key][0]["lat"])
            prop["longitude"] = float(cache[key][0]["lon"])
            prop["geo_precision"] = precision
            return
    prop["latitude"] = prop["longitude"] = None
    prop["geo_precision"] = None


async def import_site(site: str, *, name: str | None, photos: bool, geo: bool, limit: int | None) -> Path:
    base = site.rstrip("/")
    name = slug(name or urlparse(base).netloc.removeprefix("www.").split(".")[0])
    target = DATA_DIR / "catalogs" / name
    (target / "paginas").mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=30, follow_redirects=True) as client:
        llms = await fetch_text(client, f"{base}/llms.txt")
        (target / "llms.txt").write_text(llms, encoding="utf-8")
        blocks = re.split(r"^### ", llms.split("## Imóveis em destaque", 1)[-1], flags=re.M)[1:]
        entries = [parse_llms_entry("### " + block) for block in blocks][:limit]
        print(f"{len(entries)} imóveis no llms.txt de {base}")

        gate = asyncio.Semaphore(3)

        async def enrich(entry: dict) -> dict:
            async with gate:
                page = await fetch_text(client, entry["url"])
                await asyncio.sleep(0.3)
            source_id = re.search(r"/imovel/(\d+)/", entry["url"])[1]
            return normalize(entry, parse_page(page), source_id)

        catalog = await asyncio.gather(*(enrich(entry) for entry in entries))
        print(f"{len(catalog)} páginas de imóveis lidas")

        for page_name in SITE_PAGES:
            try:
                lines = visible_lines(await fetch_text(client, f"{base}/{page_name}"))
            except httpx.HTTPError:
                continue
            (target / "paginas" / f"{page_name}.txt").write_text("\n".join(lines), encoding="utf-8")

        if geo:
            cache_file = target / "geocode_cache.json"
            cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
            for prop in catalog:
                await geocode(client, prop, cache)
            cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            located = sum(p["geo_precision"] == "endereco" for p in catalog)
            print(f"Geocodificação: {located} por endereço, {len(catalog) - located} por bairro/cidade")

        if photos:
            photo_gate = asyncio.Semaphore(4)
            jobs = []
            for prop in catalog:
                folder = target / "fotos" / slug(prop["code"] or prop["source_id"])
                folder.mkdir(parents=True, exist_ok=True)
                for index, photo in enumerate(prop["photos"], start=1):
                    suffix = Path(urlparse(photo["url"]).path).suffix or ".jpg"
                    file = folder / f"{index:02d}{suffix}"
                    photo["file"] = str(file.relative_to(target))
                    jobs.append(download_photo(client, photo["url"], file, photo_gate))
            results = await asyncio.gather(*jobs)
            print(f"Fotos: {sum(results)}/{len(results)} baixadas")

    payload = {
        "source": base,
        "scraped_at": datetime.now(UTC).isoformat(),
        "agency": {"name": name},
        "properties": catalog,
    }
    (target / "imoveis.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa o catálogo de um site de imobiliária na plataforma ImobiBrasil."
    )
    parser.add_argument("site", help="URL do site, ex.: https://www.sua-imobiliaria.com.br")
    parser.add_argument("--nome", help="Nome da pasta do catálogo em data/catalogs/ (padrão: derivado do domínio).")
    parser.add_argument("--sem-fotos", action="store_true", help="Não baixa as fotos (mantém só as URLs).")
    parser.add_argument("--sem-geo", action="store_true", help="Não geocodifica os endereços.")
    parser.add_argument("--limite", type=int, help="Importa só os N primeiros imóveis (teste).")
    args = parser.parse_args()
    target = asyncio.run(
        import_site(args.site, name=args.nome, photos=not args.sem_fotos, geo=not args.sem_geo, limit=args.limite)
    )
    print(f"Catálogo salvo em {target}")


if __name__ == "__main__":
    main()
