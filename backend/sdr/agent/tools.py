from datetime import date, datetime
from typing import Literal

from langchain.tools import ToolRuntime, tool

from sdr import agenda
from sdr.agent.state import AgentContext
from sdr.config import get_settings
from sdr.finance import brl, pct, rental_yield, simulate_financing
from sdr.llm import embed
from sdr.models import PropertyKind
from sdr.presenters import property_details, property_line
from sdr.repositories import appointments, events, knowledge, leads, properties
from sdr.repositories.properties import PropertyFilters

Runtime = ToolRuntime[AgentContext, dict]


@tool(response_format="content_and_artifact")
async def buscar_imoveis(
    finalidade: Literal["venda", "aluguel"],
    runtime: Runtime,
    regioes: list[str] | None = None,
    preco_maximo: float | None = None,
    preco_minimo: float | None = None,
    quartos_minimo: int | None = None,
    vagas_minimo: int | None = None,
    tipo: PropertyKind | None = None,
    aceita_pet: bool | None = None,
    desejos: str | None = None,
    excluir_codigos: list[str] | None = None,
) -> tuple[str, dict]:
    """Busca imóveis no portfólio da imobiliária (Tatuí e região) e retorna até 3 opções compatíveis.

    Use os dados do perfil do lead como filtros. Para investimento, use finalidade "venda".
    `regioes` aceita bairros ("Centro", "Vila Santa Emília"), condomínios ("Reserva dos Ipês") ou cidades
    ("Tatuí", "Cesário Lange"). Para condomínio fechado, use tipo "casa_condominio". `preco_maximo` é o teto em
    reais (mensal no aluguel). `desejos` é texto livre com características desejadas (ex.: "área gourmet e
    piscina"), usado na busca semântica. Use `excluir_codigos` (referências) para trazer opções diferentes.
    """
    context = runtime.context
    filters = PropertyFilters(
        purpose=finalidade,
        regions=regioes or [],
        price_min=preco_minimo,
        price_max=preco_maximo,
        bedrooms_min=quartos_minimo,
        parking_min=vagas_minimo,
        kind=tipo,
        pet_friendly=aceita_pet or context.profile.has_pet,
        exclude_codes=[properties.normalize_code(code) for code in excluir_codigos or []],
    )
    query = " ".join(
        part
        for part in [
            tipo or "imóvel",
            f"para {finalidade}",
            ", ".join(regioes or []),
            f"{quartos_minimo} quartos" if quartos_minimo else "",
            desejos or "",
            ", ".join(context.profile.preferences),
        ]
        if part
    )
    [query_embedding] = await embed([query])
    result = await properties.search(filters, query_embedding)
    if not result.items:
        return (
            "Nenhum imóvel encontrado, mesmo ampliando a busca. Pergunte se o lead flexibiliza algum critério.",
            {"codes": [], "mode": "lista"},
        )
    await events.record(
        context.lead_id, "imoveis_apresentados", {"codes": [p["code"] for p in result.items], "agent": context.agent}
    )
    with_yield = context.agent == "investidor"
    lines = [property_line(p, with_yield=with_yield) for p in result.items]
    header = "Imóveis encontrados"
    if result.relaxed:
        header += f" (não havia opção exata; busca ampliada com {', '.join(result.relaxed)})"
    return header + ":\n" + "\n".join(lines), {"codes": [p["code"] for p in result.items], "mode": "lista"}


@tool(response_format="content_and_artifact")
async def detalhes_imovel(codigo: str) -> tuple[str, dict]:
    """Retorna a ficha completa de um imóvel pela referência (ex.: 277), incluindo descrição, características,
    proximidades e localização. Use quando o lead quiser saber mais ou ver fotos de um imóvel."""
    prop = await properties.get(codigo)
    if not prop:
        return f"Imóvel {codigo} não encontrado no portfólio.", {"codes": [], "mode": "detalhe"}
    return property_details(prop), {"codes": [prop["code"]], "mode": "detalhe"}


@tool
async def consultar_base_conhecimento(pergunta: str) -> str:
    """Consulta a base de conhecimento da imobiliária: financiamento, FGTS, documentação, custos de compra
    (ITBI, escritura, registro), garantias de aluguel, tributação de aluguel, processo de visita e informações
    sobre a imobiliária. Responda ao lead com base no trecho retornado."""
    [query_embedding] = await embed([pergunta])
    chunks = await knowledge.search(query_embedding, k=3)
    relevant = [c for c in chunks if c["similarity"] >= 0.25]
    if not relevant:
        return "Não há informação sobre isso na base. Diga que vai confirmar com o corretor."
    return "\n\n".join(f"[{c['source']} › {c['title']}]\n{c['content']}" for c in relevant)


@tool
def simular_financiamento(
    valor_imovel: float, entrada: float, prazo_anos: int = 30, taxa_juros_anual: float = 11.5
) -> str:
    """Simula financiamento imobiliário nas tabelas SAC e Price. `taxa_juros_anual` em % (ex.: 11.5).
    Use valores informados pelo lead; deixe claro que é uma estimativa e que a taxa real depende do banco."""
    simulation = simulate_financing(valor_imovel, entrada, prazo_anos, taxa_juros_anual / 100)
    if simulation.financed == 0:
        return "A entrada cobre o valor total; não há financiamento."
    return "\n".join(
        [
            f"Valor financiado: {brl(simulation.financed)} em {simulation.months} meses, juros {taxa_juros_anual}% a.a.",
            f"SAC: 1ª parcela {brl(simulation.sac_first_installment)}, última {brl(simulation.sac_last_installment)},"
            f" total pago {brl(simulation.sac_total_paid)}.",
            f"Price: parcelas fixas de {brl(simulation.price_installment)}, total pago {brl(simulation.price_total_paid)}.",
            f"Renda familiar mínima estimada (SAC, 30% de comprometimento): {brl(simulation.min_income_sac)}.",
            "Estimativa sem seguros e taxas administrativas; a aprovação e a taxa dependem do banco.",
        ]
    )


@tool
async def calcular_rentabilidade(codigo: str, aluguel_mensal: float | None = None) -> str:
    """Calcula a rentabilidade estimada de um imóvel à venda para investidor: yield bruto, renda líquida mensal
    (com vacância de 8% e taxa de administração de 10%) e payback. Usa o aluguel estimado do imóvel se
    `aluguel_mensal` não for informado."""
    prop = await properties.get(codigo)
    if not prop or prop["purpose"] != "venda":
        return f"Imóvel {codigo} não encontrado entre os imóveis à venda."
    rent = aluguel_mensal or float(prop["estimated_rent"] or 0)
    if not rent:
        return "Sem estimativa de aluguel para este imóvel."
    estimate = rental_yield(float(prop["price"]), rent, float(prop["condo_fee"]), float(prop["iptu_monthly"]))
    return "\n".join(
        [
            f"{prop['code']} — preço {brl(float(prop['price']))}, aluguel estimado {brl(rent)}/mês.",
            f"Yield bruto: {pct(estimate.gross_yield_year)} ao ano.",
            f"Renda líquida estimada: {brl(estimate.net_monthly_income)}/mês "
            f"(yield líquido {pct(estimate.net_yield_year)} a.a.).",
            f"Payback estimado: {estimate.payback_years:.0f} anos, sem considerar valorização.",
            "Estimativa; não considera IR sobre aluguel nem valorização.",
        ]
    )


@tool
async def horarios_disponiveis(
    tipo: Literal["visita", "reuniao", "reuniao_especialista"],
    runtime: Runtime,
    codigo_imovel: str | None = None,
    a_partir_de: str | None = None,
    periodo: Literal["manha", "tarde", "qualquer"] = "qualquer",
) -> str:
    """Lista horários livres na agenda do corretor responsável. `a_partir_de` no formato AAAA-MM-DD, se o
    lead pediu um dia específico. Retorna opções com o valor de data_hora a usar em `agendar`."""
    context = runtime.context
    broker = await _broker_for(tipo, codigo_imovel, context)
    from_day = date.fromisoformat(a_partir_de) if a_partir_de else None
    slots = await agenda.available_slots(broker, now=context.now, from_day=from_day, period=periodo)
    if not slots:
        return "Sem horários livres nesse período. Ofereça outro dia ou período."
    lines = [f"- {agenda.format_slot(slot)} → data_hora={slot:%Y-%m-%dT%H:%M}" for slot in slots]
    return f"Horários livres com {broker['name']} ({agenda.KIND_LABELS[tipo]}):\n" + "\n".join(lines)


@tool
async def agendar(
    tipo: Literal["visita", "reuniao", "reuniao_especialista"],
    data_hora: str,
    runtime: Runtime,
    codigo_imovel: str | None = None,
    observacoes: str | None = None,
) -> str:
    """Agenda o compromisso no horário escolhido pelo lead. `data_hora` deve ser exatamente um valor retornado
    por horarios_disponiveis (AAAA-MM-DDTHH:MM). Para visita, informe a referência do imóvel (ex.: 277)."""
    context = runtime.context
    tz = get_settings().tz
    try:
        starts_at = datetime.fromisoformat(data_hora).replace(tzinfo=tz)
    except ValueError:
        return "data_hora inválida. Use um valor retornado por horarios_disponiveis."
    if not agenda.is_bookable(starts_at, context.now):
        return "Esse horário não está disponível na agenda. Consulte horarios_disponiveis de novo."
    broker = await _broker_for(tipo, codigo_imovel, context)
    code = properties.normalize_code(codigo_imovel) if codigo_imovel else None
    if code and not await properties.get(code):
        return f"Imóvel {codigo_imovel} não encontrado. Confirme o código com o lead."
    appointment = await appointments.create(
        lead_id=context.lead_id,
        broker_id=broker["id"],
        kind=tipo,
        starts_at=starts_at,
        property_code=code,
        notes=observacoes,
    )
    if appointment is None:
        return "Esse horário acabou de ser ocupado. Consulte horarios_disponiveis e ofereça outro."
    await events.record(
        context.lead_id,
        "agendamento_criado",
        {"kind": tipo, "starts_at": starts_at.isoformat(), "broker": broker["name"], "property": code},
    )
    return (
        f"Agendado: {agenda.KIND_LABELS[tipo]} {agenda.format_slot(starts_at)} com {broker['name']}"
        + (f", imóvel {code}" if code else "")
        + ". Confirme ao lead."
    )


@tool
async def encaminhar_para_corretor(motivo: str, runtime: Runtime) -> str:
    """Transfere o atendimento para um corretor humano (ex.: negociação de valores, proposta, situação
    complexa). Depois, avise o lead que o corretor vai chamá-lo em breve e que ele não precisará repetir nada."""
    context = runtime.context
    await leads.set_handoff(context.lead_id, motivo)
    await events.record(context.lead_id, "handoff", {"reason": motivo, "agent": context.agent})
    kind = "reuniao_especialista" if context.profile.intent == "investimento" else "visita"
    broker = await agenda.pick_broker(kind, property_kind=context.profile.property_type)
    return f"Atendimento encaminhado para {broker['name']}. Avise o lead."


@tool(return_direct=True)
async def abrir_agenda(motivo: str, runtime: Runtime) -> str:
    """Passa a conversa para a agenda assim que o lead aceitar ou pedir uma visita ou reunião (inclusive com a
    especialista em investimentos). Não escreva resposta depois de chamar: a agenda continua a conversa e oferece
    os horários."""
    context = runtime.context
    await events.record(
        context.lead_id, "transferencia_agente", {"de": context.agent, "para": "agendamento", "motivo": motivo}
    )
    return "Conversa transferida para a agenda."


async def _broker_for(kind: str, property_code: str | None, context: AgentContext) -> dict:
    property_kind = context.profile.property_type
    if property_code and (prop := await properties.get(property_code)):
        property_kind = prop["kind"]
    return await agenda.pick_broker(kind, property_kind=property_kind)


SPECIALIST_TOOLS = {
    "recepcao": [buscar_imoveis, consultar_base_conhecimento, abrir_agenda],
    "consultor": [
        buscar_imoveis,
        detalhes_imovel,
        consultar_base_conhecimento,
        simular_financiamento,
        abrir_agenda,
        encaminhar_para_corretor,
    ],
    "investidor": [
        buscar_imoveis,
        detalhes_imovel,
        calcular_rentabilidade,
        consultar_base_conhecimento,
        simular_financiamento,
        abrir_agenda,
        encaminhar_para_corretor,
    ],
    "agendamento": [horarios_disponiveis, agendar, detalhes_imovel, encaminhar_para_corretor],
}
