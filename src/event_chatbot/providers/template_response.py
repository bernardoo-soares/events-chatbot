from datetime import datetime

from event_chatbot.types.query import NormalizedQuery, RankedEvent

EMPTY_RESPONSE = "No matching events were found. Try changing the city, date, category, or budget."


class TemplateResponseRenderer:
    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        if not events:
            return EMPTY_RESPONSE

        city = query.hard_filters.city
        intro = f"I found {len(events)} event{'' if len(events) == 1 else 's'}"
        if city:
            intro += f" in {city}"
        intro += "."

        lines = [intro, ""]
        for index, ranked_event in enumerate(events, start=1):
            event = ranked_event.event
            lines.extend(
                [
                    f"{index}. {event.title}",
                    f"   Date: {_format_date_range(event.start_at, event.end_at)}",
                    f"   Venue: {event.venue_name or 'Venue not specified'}",
                    f"   City: {event.city or 'City not specified'}",
                    "",
                ]
            )

        return "\n".join(lines).strip()


def _format_date_range(start_at: datetime, end_at: datetime | None) -> str:
    start = _format_date(start_at)
    if end_at is None:
        return start
    end = _format_date(end_at)
    if end == start:
        return start
    return f"{start} - {end}"


def _format_date(value: datetime) -> str:
    return f"{value:%b} {value.day}, {value:%Y}"
