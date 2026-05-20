from event_chatbot.retrieval.fts import build_fts_query


def test_build_fts_query_formats_terms_and_deduplicates() -> None:
    query = build_fts_query(["jazz", "live music", "Jazz", 'quote " test'])

    assert query == 'jazz OR "live music" OR "quote "" test"'


def test_build_fts_query_returns_none_for_empty_terms() -> None:
    assert build_fts_query(["", "   "]) is None

