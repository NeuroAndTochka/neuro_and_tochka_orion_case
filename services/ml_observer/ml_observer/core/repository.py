from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ml_observer import models
from ml_observer.schemas import (
    DocumentStatus,
    ExperimentDetail,
    ExperimentRunSummary,
    RetrievalHit,
)


class ObserverRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_experiment(
        self, *, experiment_id: str, tenant_id: str, name: str, description: str | None, params: dict
    ) -> ExperimentDetail:
        experiment = models.Experiment(
            id=experiment_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            params=params or {},
            status="created",
        )
        self.session.add(experiment)
        await self.session.commit()
        await self.session.refresh(experiment)
        return await self.get_experiment(experiment.id, tenant_id)  # type: ignore[return-value]

    async def get_experiment(self, experiment_id: str, tenant_id: str) -> Optional[ExperimentDetail]:
        stmt = (
            select(models.Experiment)
            .where(models.Experiment.id == experiment_id, models.Experiment.tenant_id == tenant_id)
            .options(selectinload(models.Experiment.runs))
        )
        experiment = (await self.session.scalars(stmt)).first()
        if not experiment:
            return None
        runs = [
            ExperimentRunSummary(
                run_id=run.id,
                run_type=run.run_type,
                status=run.status,
                created_at=run.created_at,
                metrics=run.metrics or {},
                result=run.result or {},
            )
            for run in sorted(experiment.runs, key=lambda r: r.created_at, reverse=True)
        ]
        return ExperimentDetail(
            experiment_id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            tenant_id=experiment.tenant_id,
            status=experiment.status,
            params=experiment.params or {},
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            runs=runs,
        )

    async def add_run(
        self,
        *,
        run_id: str,
        tenant_id: str,
        run_type: str,
        status: str,
        payload: dict,
        result: dict,
        metrics: dict,
        experiment_id: str | None,
    ) -> ExperimentRunSummary:
        run = models.ExperimentRun(
            id=run_id,
            experiment_id=experiment_id,
            tenant_id=tenant_id,
            run_type=run_type,
            status=status,
            payload=payload,
            result=result,
            metrics=metrics,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return ExperimentRunSummary(
            run_id=run.id,
            run_type=run.run_type,
            status=run.status,
            created_at=run.created_at,
            metrics=run.metrics or {},
            result=run.result or {},
        )

    async def upsert_document(
        self,
        *,
        record_id: str,
        tenant_id: str,
        doc_id: str,
        name: str | None,
        status: str,
        storage_uri: str | None,
        meta: dict,
        experiment_id: str | None,
    ) -> DocumentStatus:
        stmt = select(models.ObservedDocument).where(
            models.ObservedDocument.tenant_id == tenant_id,
            models.ObservedDocument.doc_id == doc_id,
        )
        document = (await self.session.scalars(stmt)).first()
        if not document:
            document = models.ObservedDocument(
                id=record_id,
                tenant_id=tenant_id,
                doc_id=doc_id,
                name=name,
                experiment_id=experiment_id,
            )
            self.session.add(document)
        document.status = status
        document.storage_uri = storage_uri
        document.meta = meta or {}
        await self.session.commit()
        await self.session.refresh(document)
        return DocumentStatus(
            doc_id=document.doc_id,
            status=document.status,
            storage_uri=document.storage_uri,
            experiment_id=document.experiment_id,
            meta=document.meta or {},
        )

    async def get_document(self, tenant_id: str, doc_id: str) -> Optional[DocumentStatus]:
        stmt = select(models.ObservedDocument).where(
            models.ObservedDocument.tenant_id == tenant_id,
            models.ObservedDocument.doc_id == doc_id,
        )
        doc = (await self.session.scalars(stmt)).first()
        if not doc:
            return None
        return DocumentStatus(
            doc_id=doc.doc_id,
            status=doc.status,
            storage_uri=doc.storage_uri,
            experiment_id=doc.experiment_id,
            meta=doc.meta or {},
        )

    @staticmethod
    def build_mock_hits(queries: Sequence[str], top_k: int) -> Tuple[list[RetrievalHit], dict]:
        hits: list[RetrievalHit] = []
        for idx in range(min(top_k, 5)):
            hits.append(
                RetrievalHit(
                    doc_id=f"doc_{idx}",
                    section_id=f"sec_{idx}",
                    score=max(0.1, 1.0 - idx * 0.1),
                    chunk_id=f"chunk_{idx}",
                    snippet=f"Mock result for: {queries[0]}" if queries else "Mock result",
                )
            )
        metrics = {"top_k": top_k, "query_count": len(queries)}
        return hits, metrics
