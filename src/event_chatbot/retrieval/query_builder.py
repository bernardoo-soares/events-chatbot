from datetime import datetime

from event_chatbot.types.query import NormalizedQuery


def build_candidate_query(query: NormalizedQuery) -> tuple[str, list[object]]:
    select_bm25 = ", bm25(events_fts) AS bm25_score" if query.used_fts else ", NULL AS bm25_score"
    join_fts = "JOIN events_fts ON events_fts.rowid = e.id" if query.used_fts else ""
    clauses: list[str] = []
    params: list[object] = []

    filters = query.hard_filters
    if filters.city:
        clauses.append("e.city = ?")
        params.append(filters.city)
    if filters.date_from:
        clauses.append("e.start_at >= ?")
        params.append(_datetime_to_text(filters.date_from))
    if filters.date_to:
        clauses.append("e.start_at <= ?")
        params.append(_datetime_to_text(filters.date_to))
    if filters.max_price is not None:
        clauses.append("(e.min_price IS NULL OR e.min_price <= ?)")
        params.append(filters.max_price)
    if filters.statuses:
        placeholders = ", ".join(["?"] * len(filters.statuses))
        clauses.append(f"e.status IN ({placeholders})")
        params.extend(filters.statuses)
    if filters.hard_category_filters:
        placeholders = ", ".join(["?"] * len(filters.hard_category_filters))
        clauses.append(f"(e.category IN ({placeholders}) OR e.subcategory IN ({placeholders}))")
        params.extend(filters.hard_category_filters)
        params.extend(filters.hard_category_filters)
    if query.used_fts and query.fts_query:
        clauses.append("events_fts MATCH ?")
        params.append(query.fts_query)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "ORDER BY bm25(events_fts)" if query.used_fts else "ORDER BY e.start_at ASC"
    params.append(query.candidate_limit)

    sql = f"""
        SELECT e.*{select_bm25}
        FROM events e
        {join_fts}
        {where}
        {order}
        LIMIT ?
    """
    return sql, params


def _datetime_to_text(value: datetime) -> str:
    return value.isoformat()

