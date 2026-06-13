import re
import unicodedata


def normalize(text: str, max_len: int = 0) -> str:
    if not text or not text.strip():
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", errors="ignore").decode("ascii")
    lower = ascii_text.lower()
    slugged = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    if not slugged:
        return ""
    if max_len > 0 and len(slugged) > max_len:
        truncated = slugged[:max_len]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > 0:
            truncated = truncated[:last_hyphen]
        slugged = truncated.strip("-")
    return slugged


def unique_slug(text: str, existing: set[str]) -> str:
    base = normalize(text)
    if not base:
        return ""
    if base not in existing:
        return base
    counter = 2
    while True:
        candidate = f"{base}-{counter}"
        if candidate not in existing:
            return candidate
        counter += 1


def normalize_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = normalize(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
