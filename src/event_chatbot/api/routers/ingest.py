from typing import Annotated

from fastapi import APIRouter, Depends

from event_chatbot.api.dependencies import get_ingestion_service
from event_chatbot.services.ingestion_service import IngestionService
from event_chatbot.types.ingestion import IngestionRequest, IngestionSummary

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestionSummary)
def ingest(
    request: IngestionRequest,
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> IngestionSummary:
    return service.ingest(request)
