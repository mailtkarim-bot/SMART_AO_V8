from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.modules.dce.application.extraction import (
    DceDocumentExtractionService,
    PrivateDocumentStoragePort,
)
from app.modules.dce.infrastructure.advanced_extraction_factory import (
    build_advanced_extractor_from_environment,
)
from app.platform.events.dispatcher import CommandDispatcher


def build_dce_document_extraction_service(
    *,
    session_factory: sessionmaker[Session],
    dispatcher: CommandDispatcher,
    storage: PrivateDocumentStoragePort,
) -> DceDocumentExtractionService:
    return DceDocumentExtractionService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        storage=storage,
        advanced_extractor=build_advanced_extractor_from_environment(),
    )
