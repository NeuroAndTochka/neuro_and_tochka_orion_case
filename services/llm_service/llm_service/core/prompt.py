from __future__ import annotations

from typing import Dict, List

from llm_service.schemas import ContextChunk, Message


def build_rag_prompt(system_prompt: str, messages: List[Message], chunks: List[ContextChunk]) -> List[Dict[str, str]]:
    prompt_messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": (
                """You must answer using ONLY the provided context. If the context is insufficient, say what is missing and ask for the exact missing detail.
                Do NOT request additional tools here.
                Do NOT reveal chain-of-thought. Provide a concise final answer.
                Cite sources for each factual claim using [doc_id/section_id]."""

            ),
        },
    ]
    if chunks:
        context_block = "\n".join(
            f"[doc:{chunk.doc_id} sec:{chunk.section_id or '-'} pages:{chunk.page_start}-{chunk.page_end}]\n{chunk.text}"
            for chunk in chunks
        )
        prompt_messages.append(
            {
                "role": "system",
                "content": """Below are relevant sections from Orion documentation. Use them when answering.
                Context may be incomplete. Prefer quoting the exact command/parameter names.
                Do not restate large excerpts. Use short quotes only when necessary.\n
                """ + context_block,
            }
        )
    prompt_messages.extend(message.model_dump() for message in messages)
    return prompt_messages
