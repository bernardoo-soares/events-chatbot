from typing import Annotated

from fastapi import APIRouter, Depends, Query

from event_chatbot.api.dependencies import get_retrieval_service
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.types.query import QuerySpec, RankedEvent

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/search", response_model=list[RankedEvent])
def search_events(
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    city: str | None = None,
    q: Annotated[str | None, Query(alias="q")] = None,
    date_from: str | None = None,
    date_to: str | None = None,
    max_price: float | None = None,
    limit: int = 20,
) -> list[RankedEvent]:
    spec = QuerySpec(
        city=city,
        keywords=[q] if q else [],
        date_from=date_from,
        date_to=date_to,
        max_price=max_price,
    )
    normalized = service.normalize(spec)
    normalized.limit = limit
    return service.search(normalized)
