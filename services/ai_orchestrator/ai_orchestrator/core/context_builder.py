from __future__ import annotations

from typing import Dict, List


def build_context(sections: List[Dict[str, str]], token_budget: int) -> List[Dict[str, str]]:
    """Build lightweight context with summaries/metadata only (no raw chunk text)."""
    budget_chars = token_budget * 4
    accumulated = 0
    context: List[Dict[str, str]] = []
    for sec in sections:
        summary = sec.get("summary") or sec.get("title") or ""
        # hard trim to avoid leaking full section text
        trimmed = summary[: max(0, min(len(summary), budget_chars - accumulated, 800))]
        accumulated += len(trimmed)
        context.append(
            {
                "doc_id": sec.get("doc_id"),
                "section_id": sec.get("section_id"),
                "title": sec.get("title"),
                "page_start": sec.get("page_start"),
                "page_end": sec.get("page_end"),
                "score": sec.get("score"),
                "summary": trimmed,
            }
        )
        if accumulated >= budget_chars:
            break
    return context
