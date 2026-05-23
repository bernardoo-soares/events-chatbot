from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import CarryoverField, QuerySpec, RequestIntent

FOLLOW_UP_ROLES = {
    "follow_up_refinement",
    "follow_up_more_results",
    "follow_up_comparison",
}
ALL_CARRYOVER_FIELDS: set[CarryoverField] = {
    "city",
    "date",
    "budget",
    "category",
    "keywords",
    "vibes",
}


def should_use_previous_context(
    intent: RequestIntent,
    state: SessionState | None,
) -> bool:
    return (
        state is not None
        and state.current_query is not None
        and intent.conversation_role in FOLLOW_UP_ROLES
    )


def allowed_carryover_fields(intent: RequestIntent) -> set[CarryoverField]:
    if intent.conversation_role not in FOLLOW_UP_ROLES:
        return set()
    return {
        field
        for field in intent.context_carryover
        if field in ALL_CARRYOVER_FIELDS
    }


def merge_query_spec_for_context(
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
        if data["date_preset"] is None:
            data["date_preset"] = prior.date_preset
        if data["date_day"] is None:
            data["date_day"] = prior.date_day
        if data["date_month"] is None:
            data["date_month"] = prior.date_month
        if data["date_year"] is None:
            data["date_year"] = prior.date_year
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
