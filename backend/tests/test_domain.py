from datetime import UTC, datetime

import pytest

from sdr.agenda import candidate_slots, format_slot, is_bookable, spread
from sdr.agent.nodes import OPT_OUT_KEYWORDS, decide_route
from sdr.config import get_settings, parse_durations
from sdr.finance import brl, rental_yield, simulate_financing
from sdr.models import LeadProfile, TurnSignals
from sdr.security import mask_pii
from sdr.text import place_keys, speechify, split_bubbles


def test_financing_price_and_sac():
    simulation = simulate_financing(800_000, 160_000, years=30, annual_rate=0.12)
    assert simulation.financed == 640_000
    assert simulation.months == 360
    assert simulation.sac_first_installment > simulation.price_installment > simulation.sac_last_installment
    assert simulation.sac_total_paid < simulation.price_total_paid
    assert simulation.min_income_sac == pytest.approx(simulation.sac_first_installment / 0.3)


def test_financing_fully_paid_upfront():
    assert simulate_financing(500_000, 600_000).financed == 0


def test_rental_yield():
    estimate = rental_yield(500_000, 2_500, condo_fee=500, iptu_monthly=100)
    assert estimate.gross_yield_year == pytest.approx(0.06)
    assert estimate.net_yield_year < estimate.gross_yield_year
    assert estimate.payback_years > 1 / 0.06


def test_brl_format():
    assert brl(1_234_567.8) == "R$ 1.234.568"
    assert brl(1_234.5, 2) == "R$ 1.234,50"


@pytest.mark.parametrize(
    ("guardrail", "profile", "signals", "expected"),
    [
        ({"category": "prompt_injection"}, {}, {}, "safe_reply"),
        ({"category": "abusivo"}, {"intent": "compra"}, {}, "safe_reply"),
        ({"category": "opt_out"}, {"intent": "compra"}, {"wants_schedule": True}, "opt_out"),
        ({"category": "ok"}, {"intent": "investimento"}, {"wants_schedule": True, "wants_human": True}, "agendamento"),
        ({"category": "ok"}, {"intent": "compra"}, {"wants_human": True}, "handoff"),
        ({"category": "ok"}, {"intent": "investimento"}, {}, "investidor"),
        ({"category": "ok"}, {"intent": "aluguel"}, {}, "consultor"),
        ({"category": "ok"}, {"intent": "compra"}, {}, "consultor"),
        ({}, {}, {}, "recepcao"),
    ],
)
def test_decide_route(guardrail, profile, signals, expected):
    assert decide_route(guardrail, LeadProfile(**profile), TurnSignals(**signals)) == expected


@pytest.mark.parametrize("text", ["PARAR", "parar.", " Stop ", "descadastrar!"])
def test_opt_out_keywords(text):
    assert OPT_OUT_KEYWORDS.match(text)


@pytest.mark.parametrize("text", ["não quero parar de procurar", "pare de mandar imóveis caros"])
def test_opt_out_keywords_ignore_sentences(text):
    assert not OPT_OUT_KEYWORDS.match(text)


def test_place_keys_normalize_neighborhoods_condos_and_cities():
    keys = place_keys(
        ["Residencial Bosques dos Ipês", "condomínio Reserva dos Ypês 3", "Centro de Tatuí", "Tatuí", "SP"]
    )
    assert keys == ["bosques ipes", "reserva ipes 3", "centro", "tatui"]


def test_split_bubbles_limits_count():
    text = "\n\n".join(f"parte {i}" for i in range(6))
    bubbles = split_bubbles(text, max_bubbles=3)
    assert bubbles[:2] == ["parte 0", "parte 1"]
    assert len(bubbles) == 3


def test_speechify_removes_markup():
    assert (
        speechify("🏠 **Ref. 277** | Vila Santa Emília | 189 m²")
        == "referência 277, Vila Santa Emília, 189 metros quadrados"
    )


def test_mask_pii():
    masked = mask_pii("Meu CPF é 123.456.789-09, email ana@ex.com e cel (11) 98765-4321")
    assert "123.456" not in masked and "ana@ex.com" not in masked and "98765" not in masked
    assert "[CPF]" in masked and "[EMAIL]" in masked and "[TELEFONE]" in masked
    assert mask_pii("Apartamento de R$ 900.000 com 3 quartos") == "Apartamento de R$ 900.000 com 3 quartos"


def test_parse_durations():
    assert parse_durations("30m, 1d,2h,45s") == [1800, 86400, 7200, 45]
    with pytest.raises(ValueError):
        parse_durations("10x")


def test_slots_respect_business_hours_and_lead_time():
    tz = get_settings().tz
    now = datetime(2026, 10, 16, 16, 30, tzinfo=tz)
    slots = candidate_slots(now, days=3)
    assert slots[0] == datetime(2026, 10, 17, 9, tzinfo=tz)
    assert all(slot.weekday() != 6 for slot in slots)
    assert all(slot.hour < 13 for slot in slots if slot.weekday() == 5)
    assert is_bookable(datetime(2026, 10, 19, 10, tzinfo=tz), now)
    assert not is_bookable(datetime(2026, 10, 18, 10, tzinfo=tz), now)
    assert not is_bookable(datetime(2026, 10, 16, 17, tzinfo=tz), now)


def test_spread_picks_morning_and_afternoon():
    tz = get_settings().tz
    slots = candidate_slots(datetime(2026, 10, 12, 6, tzinfo=tz), days=2)
    picked = spread(slots, 4)
    assert len(picked) == 4
    assert {slot.hour < 12 for slot in picked[:2]} == {True, False}


def test_format_slot():
    assert format_slot(datetime(2026, 10, 15, 13, tzinfo=UTC)) == "quinta-feira, 15/10 às 10h"
