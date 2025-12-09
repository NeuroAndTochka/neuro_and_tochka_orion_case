from __future__ import annotations

from typing import Dict, List


def build_context(chunks: List[Dict[str, str]], token_budget: int) -> List[Dict[str, str]]:
    # simple trimming heuristic: assume 4 chars per token
    budget_chars = token_budget * 4
    context = []
    accumulated = 0
    for chunk in chunks:
        text = chunk.get("text", "")
        trimmed_text = text[: max(0, budget_chars - accumulated)]
        accumulated += len(trimmed_text)
        context.append({**chunk, "text": trimmed_text})
        if accumulated >= budget_chars:
            break
    return context
