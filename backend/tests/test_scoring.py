from sdr.models import LeadProfile
from sdr.scoring import compute_score, compute_stage, is_qualified, merge_profile, missing_fields, temperature_for


def buyer(**overrides) -> LeadProfile:
    data = {
        "intent": "compra",
        "regions": ["zona sul"],
        "budget_max": 900_000,
        "bedrooms": 2,
        "urgency": "ate_3_meses",
    }
    return LeadProfile.model_validate({**data, **overrides})


def test_undefined_intent_only_misses_intent():
    assert missing_fields(LeadProfile()) == ["intent"]


def test_buyer_requires_pdf_fields():
    profile = LeadProfile(intent="compra", regions=["Moema"])
    assert missing_fields(profile) == ["budget_max", "bedrooms", "urgency"]


def test_investor_requires_ticket_return_and_goal():
    profile = LeadProfile(intent="investimento", investment_ticket=600_000)
    assert missing_fields(profile) == ["expected_return", "investment_goal"]
    assert not is_qualified(profile)


def test_qualified_buyer_with_urgency_and_financing_is_hot():
    score = compute_score(buyer(payment_method="financiamento"), lead_messages=5, has_appointment=False)
    assert score == 10 + 40 + 15 + 5 + 5
    assert temperature_for(score) == "quente"


def test_appointment_pushes_score_and_caps_at_100():
    profile = buyer(urgency="imediata", payment_method="a_vista", email="a@b.com", interested_properties=["RY-001"])
    assert compute_score(profile, lead_messages=10, has_appointment=True) == 100


def test_partial_lead_is_cold():
    score = compute_score(LeadProfile(intent="aluguel", regions=["Pinheiros"]), lead_messages=1, has_appointment=False)
    assert temperature_for(score) == "frio"


def test_stage_precedence():
    profile = buyer()
    kwargs = {"has_appointment": True, "handoff": True, "opted_out": True, "lead_messages": 4}
    assert compute_stage(profile, **kwargs) == "opt_out"
    assert compute_stage(profile, **{**kwargs, "opted_out": False}) == "handoff"
    assert compute_stage(profile, **{**kwargs, "opted_out": False, "handoff": False}) == "agendado"
    assert (
        compute_stage(profile, has_appointment=False, handoff=False, opted_out=False, lead_messages=4) == "qualificado"
    )
    assert (
        compute_stage(LeadProfile(), has_appointment=False, handoff=False, opted_out=False, lead_messages=1) == "novo"
    )


def test_merge_keeps_known_values_and_applies_corrections():
    current = buyer(preferences=["varanda"])
    extracted = LeadProfile(intent="indefinido", budget_max=1_000_000, regions=[], name="Ana")
    merged = merge_profile(current, extracted)
    assert merged.intent == "compra"
    assert merged.budget_max == 1_000_000
    assert merged.regions == ["zona sul"]
    assert merged.preferences == ["varanda"]
    assert merged.name == "Ana"


def test_merge_replaces_lists_without_duplicates():
    merged = merge_profile(buyer(), LeadProfile(regions=["Moema", "Moema", "Saúde"]))
    assert merged.regions == ["Moema", "Saúde"]
