from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sdr.config import get_settings
from sdr.repositories import appointments

WEEKDAY_HOURS = range(9, 18)
SATURDAY_HOURS = range(9, 13)
MIN_LEAD_TIME = timedelta(hours=2)
BOOKING_WINDOW_DAYS = 14
WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
KIND_LABELS = {
    "visita": "visita ao imóvel",
    "reuniao": "reunião por vídeo com corretor",
    "reuniao_especialista": "reunião por vídeo com especialista em investimentos",
}


def format_slot(moment: datetime) -> str:
    local = moment.astimezone(get_settings().tz)
    minutes = f"{local.minute:02d}" if local.minute else ""
    return f"{WEEKDAYS[local.weekday()]}, {local:%d/%m} às {local.hour}h{minutes}"


def _hours_for(day: date) -> range:
    if day.weekday() < 5:
        return WEEKDAY_HOURS
    if day.weekday() == 5:
        return SATURDAY_HOURS
    return range(0)


def candidate_slots(now: datetime, days: int = BOOKING_WINDOW_DAYS) -> list[datetime]:
    tz = get_settings().tz
    local_now = now.astimezone(tz)
    earliest = local_now + MIN_LEAD_TIME
    slots = []
    for offset in range(days + 1):
        day = (local_now + timedelta(days=offset)).date()
        for hour in _hours_for(day):
            slot = datetime.combine(day, time(hour), tzinfo=tz)
            if slot >= earliest:
                slots.append(slot)
    return slots


def spread(slots: list[datetime], limit: int) -> list[datetime]:
    by_day: dict[date, list[datetime]] = defaultdict(list)
    for slot in slots:
        by_day[slot.date()].append(slot)
    picked = []
    for day_slots in by_day.values():
        morning = [s for s in day_slots if s.hour < 12]
        afternoon = [s for s in day_slots if s.hour >= 12]
        for group in (morning, afternoon):
            if group and len(picked) < limit:
                picked.append(group[len(group) // 2])
        if len(picked) >= limit:
            break
    return sorted(picked)


async def pick_broker(kind: str, *, property_kind: str | None = None) -> dict:
    brokers = await appointments.brokers()
    if kind == "reuniao_especialista":
        return next(b for b in brokers if b["specialty"] == "investimento")
    residential = [b for b in brokers if b["specialty"] == "residencial"]
    if property_kind:
        for broker in residential:
            if property_kind in broker["kinds"]:
                return broker
    return residential[0]


async def available_slots(
    broker: dict, *, now: datetime, from_day: date | None = None, period: str = "qualquer", limit: int = 4
) -> list[datetime]:
    slots = candidate_slots(now)
    if from_day:
        slots = [s for s in slots if s.date() >= from_day]
    if period == "manha":
        slots = [s for s in slots if s.hour < 12]
    elif period == "tarde":
        slots = [s for s in slots if s.hour >= 12]
    if not slots:
        return []
    booked = await appointments.booked_slots(broker["id"], slots[0], slots[-1])
    return spread([s for s in slots if s not in booked], limit)


def is_bookable(moment: datetime, now: datetime) -> bool:
    return moment in set(candidate_slots(now))
