import re

SAFE_TOKEN_RE = re.compile(r"^[\w]+$")


def build_fts_query(terms: list[str], max_terms: int = 12) -> str | None:
    normalized = _dedupe_terms(terms)[:max_terms]
    if not normalized:
        return None
    return " OR ".join(_format_term(term) for term in normalized)


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        normalized = " ".join(term.strip().split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _format_term(term: str) -> str:
    escaped = term.replace('"', '""')
    if SAFE_TOKEN_RE.fullmatch(escaped):
        return escaped
    return f'"{escaped}"'

