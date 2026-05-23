import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from event_chatbot.api.dependencies import SettingsDep, get_db_connection
from event_chatbot.api.guards import require_non_production
from event_chatbot.services.ingestion_factory import build_ingestion_service
from event_chatbot.types.ingestion import IngestionRequest, IngestionSummary

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestionSummary)
def ingest(
    request: IngestionRequest,
    settings: SettingsDep,
    conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
) -> IngestionSummary:
    require_non_production(settings, "Event ingestion")
    service = build_ingestion_service(request.source, conn, settings)
    return service.ingest(request)
