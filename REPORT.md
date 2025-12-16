# RAG window forensic report

## A1. Trace flow (WINDOW_TOO_LARGE)
- UI → `ai_orchestrator` `/respond` builds request with tenant/user and calls Retrieval Service search (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:52-96`), logging hits/docs/sections/chunks.
- Retrieval Service `/internal/retrieval/search` logs the query and enforces max_results (`services/retrieval_service/retrieval_service/routers/retrieval.py:18-76`), returning summaries/metadata only (no raw text).
- Orchestrator builds context with only summaries (no chunk text) and tool schemas (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:97-281`); system+developer prompts explicitly say to expand windows gradually.
- LLM service (chat proxy) returns a tool_call; orchestrator `_execute_tool` picks anchor_chunk_id from the first `chunk_ids` per section and uses `ProgressiveWindowState` (sequence 1→2→3→4→5 per side) to set `window_before/after` unless the model overrides them (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:27-38`, `294-330`).
- MCP proxy receives `read_chunk_window` with doc_id/anchor_chunk_id/window_before/after; `ToolRegistry.execute` validates and dispatches (`services/mcp_tools_proxy/mcp_tools_proxy/core/executor.py:33-88`).
- `ReadChunkWindowTool.validate_args` checks non-negative windows and compares `(before+after+1)` to `max_chunk_window` (default 5); if exceeded, returns `WINDOW_TOO_LARGE` before hitting Retrieval (`services/mcp_tools_proxy/mcp_tools_proxy/tools/chunk_window.py:22-37`). Successful calls log requested/limit, then call Retrieval Service and trim text to `max_text_bytes` (`services/mcp_tools_proxy/mcp_tools_proxy/tools/chunk_window.py:44-112`).
- Retrieval client posts to `/internal/retrieval/chunks/window` with window params and trace_id (`services/mcp_tools_proxy/mcp_tools_proxy/clients/retrieval.py:19-70`).
- Retrieval Service fetches up to 1000 chunk metadatas per doc/tenant, sorts by `(page, chunk_index)`, finds anchor, slices `[anchor-before ... anchor+after]`, and returns raw text (`services/retrieval_service/retrieval_service/routers/chunks.py:18-106`). It ignores section_id, so the window spans the whole doc.
- Responses bubble back: MCP returns trimmed chunks, orchestrator concatenates chunk texts for token accounting and feeds the next LLM turn with a `TOOL_RESULT:{...}` assistant message (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:331-341`, `184-189`).

## A2. Where window limits can live
- UI config: `window_initial/window_step/window_max` fields in the observer console (`services/ml_observer/ml_observer/routers/ui.py` inputs) persisted via `/internal/observer/orchestrator/config` but only affect orchestrator settings, not MCP.
- Orchestrator defaults/env (`ORCH_WINDOW_INITIAL/STEP/MAX`) in `services/ai_orchestrator/ai_orchestrator/config.py:6-29`; schema shown at `/internal/orchestrator/config` (`services/ai_orchestrator/ai_orchestrator/routers/orchestrator.py:39-75`).
- Orchestrator tool schema exposes `window_before/after` with only `minimum:0`; no limit hint is given to the model (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:246-281`).
- Progressive window logic caps the per-side radius at `window_max` but does not clamp to MCP’s total limit (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:27-38`, `294-309`).
- MCP proxy limit: `max_chunk_window` (env `MCP_PROXY_MAX_CHUNK_WINDOW`, default 5) (`services/mcp_tools_proxy/mcp_tools_proxy/config.py:7-23`); enforced as `(before+after+1)` in validation (`services/mcp_tools_proxy/mcp_tools_proxy/tools/chunk_window.py:22-37`).
- MCP also trims text to `max_text_bytes` and caps token count for rate limiting (`services/mcp_tools_proxy/mcp_tools_proxy/tools/chunk_window.py:78-112`).
- Retrieval Service `/chunks/window` has no window limit; defaults `window_before/after` to 1 if missing and fetches up to `limit=1000` from Chroma before slicing (`services/retrieval_service/retrieval_service/routers/chunks.py:27-106`). No env/settings override today.
- Shared constants: none beyond the settings above; docker-compose sets no MCP max override, so the effective limit is 5 (`docker-compose.yml` service `mcp_tools_proxy`).

## A3. Why we see “returned=2” vs “Requested 7/9, limit 5”
- Requested count is computed as `(window_before + window_after + 1)` in MCP validation, regardless of how many chunks exist (`services/mcp_tools_proxy/mcp_tools_proxy/tools/chunk_window.py:22-37`). That’s what produces “Requested 7/9 chunks”.
- ProgressiveWindowState is per-side: default sequence of windows per section is radius `[1,2,3,4,5]`, yielding total requested sizes `[3,5,7,9,11]` (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:27-38`, `294-309`). So the 3rd+ calls for the same section naturally exceed MCP’s total limit of 5 → `WINDOW_TOO_LARGE`.
- Retrieval Service can still return only 1–2 chunks if the anchor is near document boundaries or the doc truly has 2 chunks; available_count is independent of the requested window and there is no server-side cap. A later, larger request fails in MCP before reaching Retrieval, producing the mismatch.
- Anchor chunk selection uses the first chunk_id from `chunk_ids` in the section hit; Retrieval `/chunks/window` filters only by doc_id+tenant, not section_id, so you won’t lose chunks by section filter, but a bad/unknown anchor_id would return `anchor_chunk_not_found`.
- Chroma fetch is `limit=1000` then sliced in-memory (`services/retrieval_service/retrieval_service/routers/chunks.py:44-73`), so “available” refers to records after that slice, not to the requested window size.

## A4. What the model actually reads
- Step 0 prompt: two system messages + developer message + a JSON dump of retrieved sections containing `doc_id`, `section_id`, `summary`, `score`, and pages—no chunk text (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:214-244`). Summaries are trimmed in `build_context` and text fields are stripped in RetrievalClient.sanitize (`services/ai_orchestrator/ai_orchestrator/core/context_builder.py:5-28`, `services/ai_orchestrator/ai_orchestrator/clients/retrieval.py:29-52`).
- Tool calls: `read_chunk_window` returns trimmed chunk texts plus ids/page/index/count/tokens (`services/mcp_tools_proxy/mcp_tools_proxy/tools/chunk_window.py:78-112`). Orchestrator concatenates only the chunk texts to estimate tokens and embeds the whole tool_result JSON (including `window_before/after/count`) into an assistant message for the next LLM step (`services/ai_orchestrator/ai_orchestrator/core/orchestrator.py:331-341`, `184-189`).
- No prompt hint communicates MCP’s 5-chunk total limit; the model is encouraged to “expand gradually,” so it keeps increasing window sizes until it hits the proxy limit.

## A5. Root-cause hypothesis & fix options
- Root cause: limit semantics are misaligned. Orchestrator’s progressive window treats `window_max` as a per-side radius (up to 5), yielding total requests of up to 11 chunks, while MCP enforces a total chunk cap of 5. UI config only adjusts orchestrator knobs; the MCP limit remains 5. The model, instructed to expand, eventually exceeds MCP’s total cap, triggering `WINDOW_TOO_LARGE`, even when Retrieval would only return 1–2 chunks near document edges.
- Fix options (minimal changes):
  1) Clamp before/after in orchestrator to MCP’s total limit (e.g., derive allowed radius from `max_chunk_window` and include it in tool schema/system prompt) so the model never asks for more than MCP will serve.
  2) Surface the proxy limit explicitly to the model: add `maximum` in the tool JSON schema and a system hint like “max total chunks = 5,” or propagate UI-configured window_max through to MCP (behind a flag such as `ENABLE_UI_WINDOW_LIMIT`) and keep both sides in sync.
  3) Improve error handling: when `WINDOW_TOO_LARGE` occurs, return a structured error with the allowed limit and optionally auto-clamp/retry within orchestrator to avoid user-visible failures.
