from __future__ import annotations

from typing import Dict, List

from llm_service.schemas import ContextChunk, Message


def build_rag_prompt(system_prompt: str, messages: List[Message], chunks: List[ContextChunk]) -> List[Dict[str, str]]:
    prompt_messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": (
                "Reason step by step, keep your chain-of-thought hidden, and only share the final answer. "
                "Ground replies in the provided context and cite sources when possible."
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
                "content": "Below are relevant sections from Orion documentation. Use them when answering.\n" + context_block,
            }
        )
    prompt_messages.extend(message.model_dump() for message in messages)
    return prompt_messages
