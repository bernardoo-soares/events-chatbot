import hashlib

from event_chatbot.types.events import Event
from event_chatbot.types.query import NormalizedQuery


def build_event_embedding_text(event: Event) -> str:
    lines = ["Local event or activity listing", f"Title: {event.title}"]
    _append_line(lines, "Description", event.description)
    _append_line(lines, "Category", event.category)
    _append_line(lines, "Subcategory", event.subcategory)
    _append_line(lines, "Venue", event.venue_name)
    _append_line(lines, "City", event.city)
    return "\n".join(lines)


def build_query_embedding_text(query: NormalizedQuery) -> str:
    lines = ["Local event or activity search"]
    _append_line(lines, "City", query.hard_filters.city)
    _append_terms(lines, "Search terms", query.semantic_terms or query.fts_terms)
    _append_terms(lines, "Event categories", query.category_boosts)
    _append_terms(lines, "Vibes", query.vibe_tags)
    if query.hard_filters.max_price is not None:
        lines.append(f"Budget: under {query.hard_filters.max_price:g}")
    return "\n".join(lines)


def embedding_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _append_line(lines: list[str], label: str, value: str | None) -> None:
    cleaned = _clean_text(value)
    if cleaned:
        lines.append(f"{label}: {cleaned}")


def _append_terms(lines: list[str], label: str, values: list[str]) -> None:
    terms = [_clean_text(value) for value in values]
    cleaned_terms = [term for term in terms if term]
    if cleaned_terms:
        lines.append(f"{label}: {', '.join(cleaned_terms)}")


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None
