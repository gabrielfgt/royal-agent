from sdr.models import LeadProfile, Stage, Temperature

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "compra": ("budget_max", "bedrooms", "regions", "urgency"),
    "aluguel": ("budget_max", "bedrooms", "regions", "urgency"),
    "investimento": ("investment_ticket", "expected_return", "investment_goal"),
}

FIELD_LABELS = {
    "intent": "objetivo (comprar, alugar ou investir)",
    "budget_max": "faixa de preço",
    "bedrooms": "quantidade de quartos",
    "regions": "região de interesse",
    "urgency": "prazo/urgência",
    "investment_ticket": "valor disponível para investir",
    "expected_return": "expectativa de retorno",
    "investment_goal": "objetivo do investimento (renda ou valorização)",
    "name": "nome",
    "phone": "WhatsApp/telefone para o corretor confirmar a visita",
}

URGENCY_POINTS = {"imediata": 20, "ate_3_meses": 15, "3_a_6_meses": 8, "acima_6_meses": 3, "sem_pressa": 0}

HOT_THRESHOLD = 70
WARM_THRESHOLD = 40


def _filled(profile: LeadProfile, field: str) -> bool:
    value = getattr(profile, field)
    return bool(value) if isinstance(value, list) else value is not None


def missing_fields(profile: LeadProfile) -> list[str]:
    if profile.intent == "indefinido":
        return ["intent"]
    return [field for field in REQUIRED_FIELDS[profile.intent] if not _filled(profile, field)]


def is_qualified(profile: LeadProfile) -> bool:
    return profile.intent != "indefinido" and not missing_fields(profile)


def compute_score(profile: LeadProfile, *, lead_messages: int, has_appointment: bool) -> int:
    score = 0
    if profile.intent != "indefinido":
        score += 10
        required = REQUIRED_FIELDS[profile.intent]
        score += round(40 * sum(_filled(profile, field) for field in required) / len(required))
    score += URGENCY_POINTS.get(profile.urgency or "", 0)
    if profile.payment_method == "a_vista" or profile.credit_approved:
        score += 10
    elif profile.payment_method is not None:
        score += 5
    if profile.email or profile.phone:
        score += 5
    if lead_messages >= 8:
        score += 10
    elif lead_messages >= 4:
        score += 5
    if profile.interested_properties:
        score += 5
    if has_appointment:
        score += 20
    return min(score, 100)


def temperature_for(score: int) -> Temperature:
    if score >= HOT_THRESHOLD:
        return "quente"
    if score >= WARM_THRESHOLD:
        return "morno"
    return "frio"


def compute_stage(
    profile: LeadProfile, *, has_appointment: bool, handoff: bool, opted_out: bool, lead_messages: int
) -> Stage:
    if opted_out:
        return "opt_out"
    if handoff:
        return "handoff"
    if has_appointment:
        return "agendado"
    if is_qualified(profile):
        return "qualificado"
    if profile.intent != "indefinido" or lead_messages > 1:
        return "em_qualificacao"
    return "novo"


def merge_profile(current: LeadProfile, extracted: LeadProfile) -> LeadProfile:
    merged = current.model_dump()
    for field, value in extracted.model_dump().items():
        if field == "intent" and value == "indefinido":
            continue
        if isinstance(value, list):
            if value:
                merged[field] = list(dict.fromkeys(value))
        elif value is not None:
            merged[field] = value
    return LeadProfile.model_validate(merged)
