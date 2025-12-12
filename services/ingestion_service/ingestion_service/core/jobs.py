from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Optional

from ingestion_service.schemas import IngestionTicket


class InMemoryJobStore:
    def __init__(self) -> None:
        self.tickets: Dict[str, IngestionTicket] = {}

    def create_job(self, doc_id: str) -> IngestionTicket:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        ticket = IngestionTicket(
            job_id=job_id,
            doc_id=doc_id,
            status="queued",
            submitted_at=datetime.utcnow(),
            storage_uri=None,
            error=None,
        )
        self.tickets[job_id] = ticket
        return ticket

    def get(self, job_id: str) -> Optional[IngestionTicket]:
        return self.tickets.get(job_id)

    def update(self, job_id: str, *, status: str, storage_uri: str | None = None, error: str | None = None) -> IngestionTicket:
        ticket = self.tickets.get(job_id)
        if not ticket:
            raise KeyError(job_id)
        ticket.status = status
        if storage_uri is not None:
            ticket.storage_uri = storage_uri
        ticket.error = error
        return ticket
