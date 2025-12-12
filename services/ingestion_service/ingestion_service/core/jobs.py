from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

try:  # pragma: no cover - tests may run without redis
    import redis  # type: ignore
except Exception:
    redis = None  # type: ignore

from ingestion_service.schemas import IngestionTicket


@dataclass
class JobRecord:
    job_id: str
    tenant_id: str
    doc_id: str
    status: str
    submitted_at: datetime
    storage_uri: str | None = None
    error: str | None = None

    def to_ticket(self) -> IngestionTicket:
        return IngestionTicket(
            job_id=self.job_id,
            tenant_id=self.tenant_id,
            doc_id=self.doc_id,
            status=self.status,
            submitted_at=self.submitted_at,
            storage_uri=self.storage_uri,
            error=self.error,
        )


class JobStore:
    """Redis-backed JobStore с in-memory fallback."""

    def __init__(self, redis_url: str | None = None, events_stream: str = "ingestion_events"):
        self._redis = None
        self.events_stream = events_stream
        if redis_url and redis:
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None
        self._memory: dict[str, JobRecord] = {}

    def _set(self, job: JobRecord) -> None:
        if self._redis:
            payload = json.dumps(
                {
                    "job_id": job.job_id,
                    "tenant_id": job.tenant_id,
                    "doc_id": job.doc_id,
                    "status": job.status,
                    "submitted_at": job.submitted_at.isoformat(),
                    "storage_uri": job.storage_uri,
                    "error": job.error,
                }
            )
            self._redis.hset("ingestion_jobs", job.job_id, payload)
        self._memory[job.job_id] = job

    def _get(self, job_id: str) -> Optional[JobRecord]:
        if self._redis:
            data = self._redis.hget("ingestion_jobs", job_id)
            if data:
                raw = json.loads(data)
                return JobRecord(
                    job_id=raw["job_id"],
                    tenant_id=raw["tenant_id"],
                    doc_id=raw["doc_id"],
                    status=raw["status"],
                    submitted_at=datetime.fromisoformat(raw["submitted_at"]),
                    storage_uri=raw.get("storage_uri"),
                    error=raw.get("error"),
                )
        return self._memory.get(job_id)

    def create(self, job: JobRecord) -> IngestionTicket:
        self._set(job)
        return job.to_ticket()

    def update(self, job_id: str, *, status: str, storage_uri: str | None = None, error: str | None = None) -> IngestionTicket:
        job = self._get(job_id)
        if not job:
            raise KeyError(job_id)
        job.status = status
        if storage_uri is not None:
            job.storage_uri = storage_uri
        job.error = error
        self._set(job)
        return job.to_ticket()

    def get(self, job_id: str) -> Optional[IngestionTicket]:
        job = self._get(job_id)
        return job.to_ticket() if job else None

    def publish_event(self, payload: dict) -> None:
        if self._redis:
            self._redis.xadd(self.events_stream, {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in payload.items()})
