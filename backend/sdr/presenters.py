import re

from sdr.agenda import KIND_LABELS, format_slot
from sdr.finance import brl, pct, rental_yield

KIND_TITLES = {
    "casa": "Casa",
    "casa_condominio": "Casa em condomínio",
    "apartamento": "Apartamento",
    "terreno": "Terreno",
    "chacara": "Chácara",
    "comercial": "Imóvel comercial",
}


def place(prop: dict) -> str:
    where = prop["neighborhood"]
    if prop.get("condominium") and prop["condominium"].lower() not in where.lower():
        where += f", cond. {prop['condominium']}"
    return where if where == prop["city"] else f"{where} ({prop['city']})"


def short_price(value: float) -> str:
    if value >= 1_000_000:
        millions = f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"R$ {millions} mi"
    if value >= 10_000:
        return f"R$ {value / 1000:.0f} mil"
    return brl(value)


def property_yield(prop: dict):
    if prop["purpose"] != "venda" or not prop.get("estimated_rent"):
        return None
    return rental_yield(
        float(prop["price"]), float(prop["estimated_rent"]), float(prop["condo_fee"]), float(prop["iptu_monthly"])
    )


def property_line(prop: dict, *, with_yield: bool = False) -> str:
    rooms = f"{prop['bedrooms']} dorms" + (f" ({prop['suites']} suíte(s))" if prop["suites"] else "")
    price = short_price(float(prop["price"]))
    if prop["purpose"] == "aluguel":
        price = f"{brl(float(prop['price']))}/mês"
    parts = [f"Ref. {prop['code']}", f"{KIND_TITLES.get(prop['kind'], prop['kind'])} em {place(prop)}"]
    if prop["kind"] != "terreno" and prop["bedrooms"]:
        parts.append(rooms)
    if prop["parking"]:
        parts.append(f"{prop['parking']} vaga(s)")
    if prop["area_m2"]:
        parts.append(f"{prop['area_m2']} m²")
    parts.append(price)
    if float(prop["condo_fee"] or 0):
        parts.append(f"cond. {brl(float(prop['condo_fee']))}")
    if with_yield and (estimate := property_yield(prop)):
        parts.append(
            f"aluguel estimado {brl(float(prop['estimated_rent']))}/mês, yield bruto {pct(estimate.gross_yield_year)} a.a."
        )
    highlights = ", ".join(prop["features"][:3])
    return " | ".join(parts) + (f" | destaques: {highlights}" if highlights else "")


def property_details(prop: dict) -> str:
    street = re.sub(r",?\s*\d+\s*$", "", prop.get("street") or "").strip()
    lines = [
        f"Ref. {prop['code']} — {prop['title']}",
        f"Finalidade: {prop['purpose']} | Tipo: {KIND_TITLES.get(prop['kind'], prop['kind'])}",
        f"Local: {place(prop)}" + (f", {street}" if street else ""),
        f"Área: {prop['area_m2']} m²"
        + (f" (terreno/total {prop['area_total_m2']} m²)" if prop.get("area_total_m2") else "")
        + f" | Quartos: {prop['bedrooms']} ({prop['suites']} suíte(s)) | Banheiros: {prop['bathrooms']}"
        f" | Vagas: {prop['parking']}" + (f" | Construído em {prop['year_built']}" if prop.get("year_built") else ""),
        f"Preço: {brl(float(prop['price']))}{'/mês' if prop['purpose'] == 'aluguel' else ''} | "
        f"Condomínio: {brl(float(prop['condo_fee']))} | IPTU mensal aprox.: {brl(float(prop['iptu_monthly']))}",
        f"Características: {', '.join(prop['features']) or 'não informado'}",
        f"Proximidades: {', '.join(prop.get('nearby') or []) or 'não informado'}",
        f"Fotos disponíveis: {len(prop.get('photos') or [])}",
        f"Descrição: {prop['description'][:1800]}",
    ]
    if estimate := property_yield(prop):
        lines.append(
            f"Aluguel estimado: {brl(float(prop['estimated_rent']))}/mês (yield bruto {pct(estimate.gross_yield_year)} a.a.)"
        )
    return "\n".join(lines)


def appointment_line(appointment: dict) -> str:
    where = ""
    if appointment.get("property_code"):
        where = f" — imóvel {appointment['property_code']}"
        if appointment.get("property_neighborhood"):
            where += f" em {appointment['property_neighborhood']}"
    label = KIND_LABELS.get(appointment["kind"], appointment["kind"])
    return f"{label} {format_slot(appointment['starts_at'])} com {appointment['broker_name']}{where}"
