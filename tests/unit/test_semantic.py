import pytest

from event_chatbot.retrieval.semantic import cosine_similarity, normalize_similarity_scores


def test_cosine_similarity_scores_same_direction_higher_than_opposite() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_returns_none_for_invalid_vectors() -> None:
    assert cosine_similarity([], []) is None
    assert cosine_similarity([1.0], [1.0, 0.0]) is None
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) is None


def test_normalize_similarity_scores_maps_candidate_set_to_zero_one_range() -> None:
    scores = normalize_similarity_scores({1: 0.2, 2: 0.5, 3: 0.8})

    assert scores == pytest.approx({1: 0.0, 2: 0.5, 3: 1.0})


def test_normalize_similarity_scores_returns_one_for_tied_scores() -> None:
    assert normalize_similarity_scores({1: 0.5, 2: 0.5}) == {1: 1.0, 2: 1.0}
