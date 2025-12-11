from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from ingestion_service.config import Settings
from ingestion_service.schemas import IngestionTicket


class InMemoryQueue:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.tickets: Dict[str, IngestionTicket] = {}
        self.storage_path = settings.storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def enqueue(self, doc_name: str, tenant_id: str, content: bytes) -> IngestionTicket:
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        file_path = self.storage_path / f"{doc_id}.bin"
        file_path.write_bytes(content)
        ticket = IngestionTicket(job_id=job_id, doc_id=doc_id, status="queued", submitted_at=datetime.utcnow())
        self.tickets[job_id] = ticket
        return ticket

    def update_status(self, job_id: str, status: str, error: str | None = None) -> IngestionTicket:
        ticket = self.tickets.get(job_id)
        if not ticket:
            raise KeyError(job_id)
        ticket.status = status
        return ticket
