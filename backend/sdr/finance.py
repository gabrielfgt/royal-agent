from dataclasses import dataclass

MAX_INCOME_COMMITMENT = 0.30
DEFAULT_VACANCY = 0.08
DEFAULT_ADMIN_FEE = 0.10


@dataclass(frozen=True)
class FinancingSimulation:
    financed: float
    months: int
    monthly_rate: float
    price_installment: float
    sac_first_installment: float
    sac_last_installment: float
    sac_total_paid: float
    price_total_paid: float
    min_income_sac: float


@dataclass(frozen=True)
class RentalYield:
    gross_yield_year: float
    net_monthly_income: float
    net_yield_year: float
    payback_years: float


def simulate_financing(
    property_value: float, down_payment: float, years: int = 30, annual_rate: float = 0.115
) -> FinancingSimulation:
    financed = max(property_value - down_payment, 0.0)
    months = years * 12
    monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
    if financed == 0:
        return FinancingSimulation(0, months, monthly_rate, 0, 0, 0, 0, 0, 0)
    price_installment = financed * monthly_rate / (1 - (1 + monthly_rate) ** -months)
    amortization = financed / months
    sac_first = amortization + financed * monthly_rate
    sac_last = amortization + amortization * monthly_rate
    sac_total = amortization * months + monthly_rate * amortization * months * (months + 1) / 2
    return FinancingSimulation(
        financed=financed,
        months=months,
        monthly_rate=monthly_rate,
        price_installment=price_installment,
        sac_first_installment=sac_first,
        sac_last_installment=sac_last,
        sac_total_paid=sac_total,
        price_total_paid=price_installment * months,
        min_income_sac=sac_first / MAX_INCOME_COMMITMENT,
    )


def rental_yield(
    price: float,
    monthly_rent: float,
    condo_fee: float = 0.0,
    iptu_monthly: float = 0.0,
    vacancy: float = DEFAULT_VACANCY,
    admin_fee: float = DEFAULT_ADMIN_FEE,
) -> RentalYield:
    net_monthly = monthly_rent * (1 - vacancy) * (1 - admin_fee) - (condo_fee + iptu_monthly) * vacancy
    net_year = net_monthly * 12
    return RentalYield(
        gross_yield_year=monthly_rent * 12 / price,
        net_monthly_income=net_monthly,
        net_yield_year=net_year / price,
        payback_years=price / net_year if net_year > 0 else float("inf"),
    )


def brl(value: float, decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%".replace(".", ",")
