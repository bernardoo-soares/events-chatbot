import unicodedata
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from event_chatbot.retrieval.fts import build_fts_query
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import CarryoverField, HardFilters, NormalizedQuery, QuerySpec

ALLOWED_CATEGORIES = {
    "music",
    "sports",
    "arts",
    "theatre",
    "family",
    "food_drink",
    "nightlife",
    "community",
    "business",
    "other",
}

CATEGORY_ALIASES = {
    "art": "arts",
    "arts-culture": "arts",
    "culture": "arts",
    "theater": "theatre",
    "food": "food_drink",
    "drink": "food_drink",
    "food-drink": "food_drink",
}

VIBE_EXPANSIONS = {
    "chill": ["chill", "casual", "relaxed"],
    "romantic": ["romantic", "date night", "intimate"],
    "family-friendly": ["family", "kids", "children"],
    "party": ["party", "dj", "nightlife"],
}

CITY_ALIASES = {
    "lisboa": "Lisbon",
    "lisbon": "Lisbon",
    "madrid": "Madrid",
    "madri": "Madrid",
    "paris": "Paris",
}


def normalize_query(
    spec: QuerySpec,
    *,
    previous: SessionState | None,
    carryover_fields: set[CarryoverField] | None = None,
    now: datetime,
    default_timezone: str,
    default_days: int,
    default_city: str | None = None,
) -> NormalizedQuery:
    merged = _merge_with_previous(spec, previous, carryover_fields or set())
    timezone = ZoneInfo(default_timezone)
    now_local = now.astimezone(timezone)
    date_from, date_to = _normalize_dates(merged, now_local, timezone, default_days)
    city = _normalize_city(merged.city) or _normalize_city(default_city)
    category_boosts, hard_category_filters, category_terms = _normalize_categories(merged)
    vibe_tags, vibe_terms = _normalize_vibes(merged.vibes)
    keyword_terms = [_clean_text(keyword) for keyword in merged.keywords]
    keyword_terms = [term for term in keyword_terms if term]
    raw_category_text = _clean_text(merged.raw_category_text)

    fts_terms = [
        *keyword_terms,
        *vibe_terms,
        *category_terms,
        *(city and [city] or []),
        *(raw_category_text and [raw_category_text] or []),
    ]
    fts_query = build_fts_query(fts_terms)

    return NormalizedQuery(
        hard_filters=HardFilters(
            city=city,
            date_from=date_from,
            date_to=date_to,
            max_price=merged.max_price,
            hard_category_filters=hard_category_filters,
        ),
        city_slug=_slug(city),
        category_boosts=category_boosts,
        vibe_tags=vibe_tags,
        fts_terms=_dedupe_terms(fts_terms),
        used_fts=fts_query is not None,
        fts_query=fts_query,
        semantic_terms=_dedupe_terms([*fts_terms, *category_boosts, *vibe_tags]),
        carryover_fields=sorted(carryover_fields or set()),
    )


def _merge_with_previous(
    spec: QuerySpec,
    previous: SessionState | None,
    carryover_fields: set[CarryoverField],
) -> QuerySpec:
    if previous is None or previous.current_query is None or not carryover_fields:
        return spec
    prior = previous.current_query
    data = spec.model_dump()
    if "city" in carryover_fields and data["city"] is None:
        data["city"] = prior.city
    if "date" in carryover_fields:
        if data["date_text"] is None:
            data["date_text"] = prior.date_text
        if data["date_from"] is None:
            data["date_from"] = prior.date_from
        if data["date_to"] is None:
            data["date_to"] = prior.date_to
        if data["relative_date_amount"] is None:
            data["relative_date_amount"] = prior.relative_date_amount
        if data["relative_date_unit"] is None:
            data["relative_date_unit"] = prior.relative_date_unit
        if data["date_window_days"] is None:
            data["date_window_days"] = prior.date_window_days
        if data["time_of_day"] is None:
            data["time_of_day"] = prior.time_of_day
    if "budget" in carryover_fields and data["max_price"] is None:
        data["max_price"] = prior.max_price
    if "category" in carryover_fields:
        if data["raw_category_text"] is None:
            data["raw_category_text"] = prior.raw_category_text
        if not data["categories"]:
            data["categories"] = prior.categories
        if data["hard_category_only"] is False:
            data["hard_category_only"] = prior.hard_category_only
    if "keywords" in carryover_fields and not data["keywords"]:
        data["keywords"] = prior.keywords
    if "vibes" in carryover_fields and not data["vibes"]:
        data["vibes"] = prior.vibes
    return QuerySpec(**data)


def _normalize_dates(
    spec: QuerySpec,
    now: datetime,
    timezone: ZoneInfo,
    default_days: int,
) -> tuple[datetime, datetime]:
    if spec.date_from or spec.date_to:
        date_from = _parse_date_or_datetime(spec.date_from, timezone) if spec.date_from else now
        date_to = (
            _parse_date_or_datetime(spec.date_to, timezone, end_of_day=True)
            if spec.date_to
            else date_from + timedelta(days=default_days)
        )
        if spec.time_of_day:
            return _apply_time_of_day(date_from.date(), spec.time_of_day, timezone)
        return _prevent_past_only_window(date_from, date_to, now, default_days)

    if spec.relative_date_amount is not None and spec.relative_date_unit is not None:
        return _normalize_relative_date(spec, now, timezone)

    if spec.date_text:
        normalized_text = spec.date_text.strip().casefold()
        if normalized_text == "tonight":
            today = now.date()
            return _at(today, time(18, 0), timezone), _at(today, time(23, 59, 59), timezone)
        if normalized_text == "tomorrow":
            tomorrow = now.date() + timedelta(days=1)
            return _day_bounds(tomorrow, timezone)
        if normalized_text == "this weekend":
            days_until_saturday = (5 - now.weekday()) % 7
            saturday = now.date() + timedelta(days=days_until_saturday)
            sunday = saturday + timedelta(days=1)
            return _at(saturday, time(0, 0), timezone), _at(sunday, time(23, 59, 59), timezone)

    if spec.time_of_day:
        return _apply_time_of_day(now.date(), spec.time_of_day, timezone)

    return now, now + timedelta(days=default_days)


def _normalize_relative_date(
    spec: QuerySpec,
    now: datetime,
    timezone: ZoneInfo,
) -> tuple[datetime, datetime]:
    amount = spec.relative_date_amount
    unit = spec.relative_date_unit
    if amount is None or unit is None:
        raise ValueError("Relative date amount and unit must both be set")
    if unit == "day":
        anchor = now.date() + timedelta(days=amount)
    elif unit == "week":
        anchor = now.date() + timedelta(weeks=amount)
    elif unit == "month":
        anchor = _add_months(now.date(), amount)
    else:
        raise ValueError(f"Unsupported relative_date_unit: {unit}")

    window_days = spec.date_window_days if spec.date_window_days is not None else 4
    date_from = _at(anchor, time.min, timezone)
    date_to = _at(anchor + timedelta(days=window_days), time(23, 59, 59), timezone)
    if spec.time_of_day:
        return _apply_time_of_day(anchor, spec.time_of_day, timezone)
    return date_from, date_to


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _prevent_past_only_window(
    date_from: datetime,
    date_to: datetime,
    now: datetime,
    default_days: int,
) -> tuple[datetime, datetime]:
    if date_to < now:
        return now, now + timedelta(days=default_days)
    return date_from, date_to


def _apply_time_of_day(
    day: date,
    time_of_day: str,
    timezone: ZoneInfo,
) -> tuple[datetime, datetime]:
    if time_of_day == "morning":
        return _at(day, time(6, 0), timezone), _at(day, time(11, 59, 59), timezone)
    if time_of_day == "afternoon":
        return _at(day, time(12, 0), timezone), _at(day, time(17, 59, 59), timezone)
    if time_of_day == "evening":
        return _at(day, time(18, 0), timezone), _at(day, time(22, 59, 59), timezone)
    if time_of_day == "night":
        return _at(day, time(21, 0), timezone), _at(day + timedelta(days=1), time(2, 0), timezone)
    raise ValueError(f"Unsupported time_of_day: {time_of_day}")


def _normalize_categories(spec: QuerySpec) -> tuple[list[str], list[str], list[str]]:
    boosts: list[str] = []
    unknown_terms: list[str] = []
    for category in spec.categories:
        normalized = _slug(category).replace("-", "_")
        normalized = CATEGORY_ALIASES.get(normalized, normalized)
        if normalized in ALLOWED_CATEGORIES:
            boosts.append(normalized)
        else:
            unknown_terms.append(category)
    boosts = _dedupe_terms(boosts)
    hard_filters = boosts if spec.hard_category_only else []
    if not spec.hard_category_only:
        unknown_terms = []
    return boosts, hard_filters, unknown_terms


def _normalize_vibes(vibes: list[str]) -> tuple[list[str], list[str]]:
    tags: list[str] = []
    terms: list[str] = []
    for vibe in vibes:
        normalized = _clean_text(vibe)
        if not normalized:
            continue
        expansion = VIBE_EXPANSIONS.get(normalized.casefold())
        if expansion is None:
            terms.append(normalized)
        else:
            tags.extend(expansion)
            terms.extend(expansion)
    return _dedupe_terms(tags), _dedupe_terms(terms)


def _parse_date_or_datetime(value: str, timezone: ZoneInfo, end_of_day: bool = False) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        return parsed
    if "T" not in value:
        parsed_time = time(23, 59, 59) if end_of_day else time(0, 0)
        return _at(parsed.date(), parsed_time, timezone)
    return parsed.replace(tzinfo=timezone)


def _day_bounds(day: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    return _at(day, time(0, 0), timezone), _at(day, time(23, 59, 59), timezone)


def _at(day: date, value: time, timezone: ZoneInfo) -> datetime:
    return datetime.combine(day, value, tzinfo=timezone)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _normalize_city(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    return CITY_ALIASES.get(_alias_key(cleaned), cleaned)


def _alias_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.casefold().split())


def _slug(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    return cleaned.casefold().replace(" ", "-")


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        cleaned = _clean_text(term)
        if cleaned is None:
            continue
        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result
