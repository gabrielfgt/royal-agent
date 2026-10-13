import json
import random

from sdr.config import DATA_DIR
from sdr.text import normalize_key

SEED = 42

NEIGHBORHOODS = {
    "Moema": ("zona sul", 14500, True, "a poucos minutos do Parque Ibirapuera e do metrô Moema (Linha 5-Lilás)"),
    "Vila Mariana": (
        "zona sul",
        12000,
        True,
        "perto das estações Ana Rosa e Vila Mariana, com ótima oferta de escolas",
    ),
    "Brooklin": ("zona sul", 12500, True, "próximo à Av. Berrini e à estação Brooklin, região de escritórios"),
    "Campo Belo": ("zona sul", 12500, True, "rua arborizada, perto do metrô Campo Belo e do Aeroporto de Congonhas"),
    "Saúde": ("zona sul", 10500, True, "a duas quadras do metrô Saúde, bairro residencial e tranquilo"),
    "Vila Olímpia": ("zona sul", 15000, False, "no polo de empresas e restaurantes da Vila Olímpia"),
    "Ipiranga": ("zona sul", 9000, False, "perto do Museu do Ipiranga e do Parque da Independência"),
    "Jabaquara": ("zona sul", 8200, True, "próximo ao metrô Jabaquara e ao acesso à Imigrantes"),
    "Santo Amaro": ("zona sul", 9000, True, "perto do Largo Treze e da estação Santo Amaro"),
    "Pinheiros": ("zona oeste", 15500, True, "a passos do metrô Fradique Coutinho, cercado de cafés e restaurantes"),
    "Vila Madalena": ("zona oeste", 14000, True, "no coração boêmio da Vila Madalena, perto do Beco do Batman"),
    "Perdizes": ("zona oeste", 12000, False, "rua tranquila em Perdizes, perto da PUC e do Sesc Pompeia"),
    "Itaim Bibi": ("zona oeste", 18000, False, "endereço nobre perto da Faria Lima e do Parque do Povo"),
    "Jardim Paulista": ("zona oeste", 16500, True, "nos Jardins, a poucos passos da Av. Paulista e da Oscar Freire"),
    "Butantã": ("zona oeste", 9000, True, "perto da USP e do metrô Butantã (Linha 4-Amarela)"),
    "Lapa": ("zona oeste", 10000, False, "perto do Mercado da Lapa e da estação de trem"),
    "Vila Leopoldina": ("zona oeste", 10500, False, "bairro em crescimento, perto do Parque Villa-Lobos"),
    "Santana": ("zona norte", 9500, True, "perto do metrô Santana e do Shopping Santana"),
    "Tucuruvi": ("zona norte", 8000, True, "a poucos minutos do metrô Tucuruvi"),
    "Casa Verde": ("zona norte", 7800, False, "bairro residencial com fácil acesso à Marginal Tietê"),
    "Tatuapé": ("zona leste", 10000, True, "perto do metrô Tatuapé e dos shoppings Boulevard e Metrô Tatuapé"),
    "Mooca": ("zona leste", 9500, False, "na tradicional Mooca, perto da Rua da Mooca e do Juventus"),
    "Anália Franco": ("zona leste", 10500, False, "ao lado do Parque Ceret e do Shopping Anália Franco"),
    "Penha": ("zona leste", 7200, True, "perto do metrô Penha e do comércio local"),
    "Bela Vista": ("centro", 10500, True, "a poucos passos da Av. Paulista e do metrô Brigadeiro"),
    "Consolação": ("centro", 12000, True, "perto do metrô Paulista e da Rua Augusta"),
    "República": ("centro", 8500, True, "no centro histórico, perto do metrô República"),
    "Higienópolis": ("centro", 13500, True, "perto do Shopping Higienópolis e da FAAP"),
}

HOUSE_FRIENDLY = {"Campo Belo", "Butantã", "Lapa", "Santana", "Mooca", "Tatuapé", "Vila Mariana", "Saúde", "Casa Verde"}

LAYOUTS = [
    (("studio", 24, 38, 1, 0, 0), 14),
    (("apartamento", 40, 55, 1, 0, 1), 16),
    (("apartamento", 55, 75, 2, 1, 1), 26),
    (("apartamento", 75, 105, 3, 1, 2), 22),
    (("apartamento", 105, 160, 3, 2, 2), 10),
    (("apartamento", 150, 220, 4, 3, 3), 6),
    (("cobertura", 160, 280, 3, 3, 3), 4),
    (("casa", 120, 260, 3, 1, 2), 12),
]

CONDO_FEATURES = [
    "piscina",
    "academia",
    "portaria 24h",
    "salão de festas",
    "churrasqueira",
    "playground",
    "pet place",
    "coworking",
    "bicicletário",
    "quadra",
    "espaço gourmet",
    "sauna",
    "lavanderia coletiva",
]
UNIT_FEATURES = [
    "varanda gourmet",
    "andar alto",
    "vista livre",
    "sol da manhã",
    "reformado",
    "armários planejados",
    "ar-condicionado",
    "depósito privativo",
    "cozinha americana",
    "home office",
    "piso em madeira",
]
HOUSE_FEATURES = ["quintal", "edícula", "churrasqueira", "jardim", "garagem coberta", "lavabo", "rua sem saída"]

OPENINGS = {
    "studio": ["Studio funcional e bem distribuído", "Studio moderno e compacto", "Studio pronto para morar"],
    "apartamento": [
        "Apartamento aconchegante",
        "Apartamento iluminado",
        "Apartamento bem planejado",
        "Apartamento amplo e arejado",
    ],
    "cobertura": ["Cobertura duplex com terraço", "Cobertura com área externa privativa"],
    "casa": ["Casa térrea espaçosa", "Sobrado charmoso", "Casa de vila reformada"],
}

AUDIENCE = {
    "studio": "Ideal para quem mora sozinho ou para investimento em locação.",
    "apartamento_1": "Ótimo para quem mora sozinho ou casal.",
    "apartamento_2": "Perfeito para casais ou família pequena.",
    "apartamento_3": "Pensado para famílias que precisam de espaço.",
    "apartamento_4": "Para famílias grandes que valorizam conforto.",
    "cobertura": "Para quem busca exclusividade e espaço para receber.",
    "casa": "Para quem quer mais privacidade e área externa.",
}


def round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def build_property(rng: random.Random, code: str, neighborhood: str, purpose: str) -> dict:
    zone, price_m2, metro_area, blurb = NEIGHBORHOODS[neighborhood]
    options = [(layout, weight) for layout, weight in LAYOUTS if layout[0] != "casa" or neighborhood in HOUSE_FRIENDLY]
    [layout] = rng.choices([o[0] for o in options], weights=[o[1] for o in options])
    kind, area_min, area_max, bedrooms, suites, parking = layout
    area = rng.randint(area_min, area_max)
    sale_price = round_to(area * price_m2 * rng.uniform(0.88, 1.15) * (0.92 if kind == "casa" else 1), 5000)
    monthly_yield = rng.uniform(0.0038, 0.0052) if kind in ("studio", "apartamento") else rng.uniform(0.0032, 0.0042)
    rent = round_to(sale_price * monthly_yield, 50)
    condo_fee = 0 if kind == "casa" else round_to(area * rng.uniform(9, 16), 10)
    iptu = round_to(sale_price * 0.008 / 12, 10)
    bathrooms = max(1, suites + (1 if bedrooms > 1 else 0))

    if kind == "casa":
        features = rng.sample(HOUSE_FEATURES, 3) + rng.sample(UNIT_FEATURES, 1)
    else:
        features = rng.sample(UNIT_FEATURES, 2) + rng.sample(CONDO_FEATURES, rng.randint(2, 4))
    near_subway = metro_area and rng.random() < 0.75
    if near_subway:
        features.append("perto do metrô")
    pet_friendly = rng.random() < 0.8
    furnished = purpose == "aluguel" and kind in ("studio", "apartamento") and rng.random() < 0.35
    if furnished:
        features.append("mobiliado")

    opening = rng.choice(OPENINGS[kind])
    rooms_text = (
        "planta integrada"
        if kind == "studio"
        else (
            f"{bedrooms} dormitório{'s' if bedrooms > 1 else ''}"
            + (f", sendo {suites} suíte{'s' if suites > 1 else ''}" if suites else "")
        )
    )
    parking_text = "sem vaga de garagem" if parking == 0 else f"{parking} vaga{'s' if parking > 1 else ''}"
    audience = AUDIENCE.get(f"{kind}_{bedrooms}", AUDIENCE.get(kind, ""))
    description = (
        f"{opening} com {area} m² em {neighborhood}, {rooms_text} e {parking_text}. "
        f"Destaques: {', '.join(features[:4])}. Localização {blurb}. {audience}"
    )
    title_kind = {"studio": "Studio", "apartamento": "Apartamento", "cobertura": "Cobertura", "casa": "Casa"}[kind]
    title = f"{title_kind} {'de ' + str(bedrooms) + ' dorms ' if kind != 'studio' else ''}em {neighborhood}"

    return {
        "code": code,
        "title": title.replace("  ", " "),
        "purpose": purpose,
        "kind": kind,
        "neighborhood": neighborhood,
        "neighborhood_key": normalize_key(neighborhood),
        "zone": zone,
        "price": sale_price if purpose == "venda" else rent,
        "condo_fee": condo_fee,
        "iptu_monthly": iptu,
        "area_m2": area,
        "bedrooms": 1 if kind == "studio" else bedrooms,
        "suites": suites,
        "bathrooms": bathrooms,
        "parking": parking,
        "features": features,
        "description": description,
        "estimated_rent": rent if purpose == "venda" else None,
        "near_subway": near_subway,
        "pet_friendly": pet_friendly,
        "furnished": furnished,
    }


def generate() -> list[dict]:
    rng = random.Random(SEED)
    catalog = []
    for neighborhood in NEIGHBORHOODS:
        extra = (["aluguel"] if rng.random() < 0.5 else []) + (["venda"] if rng.random() < 0.3 else [])
        for purpose in ["venda", "venda", "aluguel", *extra]:
            catalog.append(build_property(rng, f"RY-{len(catalog) + 1:03d}", neighborhood, purpose))
    return catalog


def main() -> None:
    catalog = generate()
    target = DATA_DIR / "properties.json"
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    sale = sum(p["purpose"] == "venda" for p in catalog)
    print(f"{len(catalog)} imóveis gerados ({sale} venda, {len(catalog) - sale} aluguel) em {target}")


if __name__ == "__main__":
    main()
