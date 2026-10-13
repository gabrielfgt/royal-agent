import re
import unicodedata

_EMOJI = re.compile(r"[\U0001f000-\U0001faff\U00002600-\U000027bf\u200d\ufe0f]+")


def normalize_key(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", stripped.lower()).strip(" .,-")


PLACE_NOISE = re.compile(r"\b(residencial|condominio|condominios|loteamento|bairro|regiao|cidade|de sp|sp)\b")


def place_key(value: str) -> str:
    key = normalize_key(value).replace("y", "i")
    key = PLACE_NOISE.sub(" ", key)
    key = re.sub(r"\b(do|da|dos|das|de)\b", " ", key)
    return re.sub(r"\s+", " ", key).strip()


CITY_KEYS = ("cesario lange", "itapetininga", "sorocaba", "boituva", "quadra", "tatui")


def place_keys(regions: list[str]) -> list[str]:
    keys = []
    for region in regions:
        key = place_key(region)
        for city in CITY_KEYS:
            if key != city and key.endswith(" " + city):
                key = key[: -len(city)].strip()
        if len(key) >= 3:
            keys.append(key)
    return keys


def split_bubbles(text: str, max_bubbles: int = 3) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    if len(parts) <= max_bubbles:
        return parts
    return parts[: max_bubbles - 1] + ["\n\n".join(parts[max_bubbles - 1 :])]


def strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text


def speechify(text: str) -> str:
    spoken = _EMOJI.sub("", strip_markdown(text))
    spoken = spoken.replace(" | ", ", ").replace("|", ", ")
    spoken = re.sub(r"\bRef\.?\s*(\d+)", lambda m: f"referência {m[1]}", spoken)
    spoken = re.sub(r"\bm²", " metros quadrados", spoken)
    return re.sub(r"[ \t]+", " ", spoken).strip()


def phone_key(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) in (10, 11):
        digits = "55" + digits
    return digits if len(digits) in (12, 13) and digits.startswith("55") else None


PHONE_IN_TEXT = re.compile(r"(?:\+?55[\s.-]?)?\(?\b\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}\b")


def find_phone(text: str) -> str | None:
    match = PHONE_IN_TEXT.search(text)
    return match[0] if match and phone_key(match[0]) else None
