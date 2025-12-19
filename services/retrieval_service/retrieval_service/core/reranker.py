from __future__ import annotations

import json
import structlog

from typing import List, Optional

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from retrieval_service.schemas import RetrievalHit
from retrieval_service.config import Settings


class SectionReranker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._logger = structlog.get_logger(__name__)
        api_key = settings.rerank_api_key or settings.embedding_api_key
        api_base = settings.rerank_api_base or settings.embedding_api_base
        if not api_key or not OpenAI:
            self._client = None
        else:
            self._client = OpenAI(api_key=api_key, base_url=api_base)

    def available(self) -> bool:
        return bool(self._client)

    def rerank(self, query: str, sections: List[RetrievalHit], top_n: int) -> List[RetrievalHit]:
        if not self._client or not sections:
            return sections
        payload = {
            "query": query,
            "sections": [
                {
                    "doc_id": hit.doc_id,
                    "section_id": hit.section_id or hit.chunk_id or f"s{i}",
                    "text": hit.text or hit.summary,
                }
                for i, hit in enumerate(sections)
            ],
            "top_n": top_n,
        }
        prompt = (
            "Given a user query and a list of sections, return a JSON array of objects "
            'with fields "doc_id", "section_id" and "rerank_score" in [0,1], higher is more relevant. '
            "Return ONLY JSON, no commentary.\n\n"
            f"Query: {query}\n\nSections:\n"
        )
        for item in payload["sections"]:
            prompt += (
                f"- doc: {item['doc_id']}, id: {item['section_id']}, text: {(item['text'] or '')[:500]}\n"
            )
        try:
            resp = self._client.chat.completions.create(
                model=self.settings.rerank_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a reranker. Return JSON only. No explanations.",
                    },
                    {"role": "user", "content": prompt},
                ],
                # temperature=0,
                # max_tokens=256,
            )
            raw_content = (
                resp.choices[0].message.content if resp and resp.choices else "[]"
            )
            content_str = self._extract_text(raw_content) or "[]"
            self._logger.info("rerank_raw_content", raw=content_str)
            scores = json.loads(content_str)
        except Exception as exc:  # pragma: no cover - network path
            self._logger.warning("rerank_failed", error=str(exc))
            return sections

        score_map = {}
        if isinstance(scores, list):
            for item in scores:
                sid = item.get("section_id")
                doc_id = item.get("doc_id")
                score_val = item.get("score")
                if score_val is None:
                    score_val = item.get("rerank_score")
                if sid and isinstance(score_val, (int, float)):
                    key = f"{doc_id}::{sid}" if doc_id else str(sid)
                    score_map[key] = min(1.0, max(0.0, float(score_val)))

        reranked: List[RetrievalHit] = []
        for hit in sections:
            sid = hit.section_id or hit.chunk_id
            key = f"{hit.doc_id}::{sid}" if sid else ""
            if sid and key in score_map:
                hit.rerank_score = score_map[key]
                hit.score = hit.rerank_score
            else:
                hit.rerank_score = hit.rerank_score if hit.rerank_score is not None else 0.0
                hit.score = hit.rerank_score
            reranked.append(hit)
        reranked.sort(key=lambda h: h.score, reverse=True)
        return reranked[:top_n] if top_n else reranked

    @staticmethod
    def _extract_text(content) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    txt = block.get("text") or block.get("output_text") or ""
                    if isinstance(txt, str):
                        parts.append(txt)
                elif hasattr(block, "text"):
                    txt = getattr(block, "text", "")
                    if isinstance(txt, str):
                        parts.append(txt)
            return "\n".join(parts)
        if hasattr(content, "text") and isinstance(getattr(content, "text"), str):
            return getattr(content, "text")
        return ""
