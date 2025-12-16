from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])


@router.get("/ui", response_class=HTMLResponse)
async def ui() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ML Observer — Console</title>
  <style>
    :root {
      --bg: #0c0f14;
      --panel: #111722;
      --accent: #10a37f;
      --text: #e8eaed;
      --muted: #9aa0a6;
      --border: #1f2937;
    }
    * { box-sizing: border-box; }
    body { font-family: "Inter", Arial, sans-serif; margin: 0; background: radial-gradient(circle at 20% 20%, #102341, #0c0f14 50%), #0c0f14; color: var(--text); padding: 24px; }
    h1 { margin: 0 0 4px; }
    h3 { margin: 0 0 8px; }
    .grid { display: grid; gap: 16px; }
    .grid-3 { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
    .grid-2 { grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); }
    section { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.35); }
    label { display: block; margin: 6px 0 2px; font-weight: 600; color: var(--muted); }
    input, textarea, select { width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: #0b1320; color: var(--text); }
    textarea { min-height: 80px; }
    button { margin-top: 10px; padding: 10px 14px; background: linear-gradient(135deg, #12b886, #0d9d74); color: #fff; border: none; border-radius: 10px; cursor: pointer; font-weight: 700; letter-spacing: 0.2px; }
    button:hover { filter: brightness(1.08); }
    pre { background: #0b0f1a; color: #cde3ff; padding: 12px; border-radius: 10px; border: 1px solid #111827; overflow: auto; max-height: 320px; }
    .title-row { display: flex; align-items: baseline; gap: 8px; }
    .pill { background: #132033; padding: 4px 10px; border-radius: 999px; color: var(--muted); font-size: 12px; border: 1px solid var(--border); }
    .row-flex { display: flex; gap: 12px; flex-wrap: wrap; }
    .small { font-size: 12px; color: var(--muted); }
  </style>
</head>
<body>
  <div class="title-row">
    <h1>ML Observer</h1><span class="pill">OpenAI-style console</span>
  </div>
  <p class="small">Быстрые проверки ingestion / retrieval. Tenant задаётся ниже.</p>

  <div class="grid grid-3">
    <section>
      <label for="tenant">X-Tenant-ID</label>
      <input id="tenant" value="observer_tenant" />
      <div class="row-flex">
        <button onclick="checkHealth()">Health</button>
        <button onclick="loadDocuments()">Docs</button>
        <button onclick="loadRetrievalConfig()">Load Retrieval cfg</button>
      </div>
      <pre id="healthLog">...</pre>
    </section>

    <section>
      <h3>Upload документ</h3>
      <label for="ingestFile">Файл</label>
      <input id="ingestFile" type="file" />
      <label for="docId">doc_id</label>
      <input id="docId" placeholder="doc_xxx" />
      <label for="docName">name</label>
      <input id="docName" placeholder="Lab 06" />
      <button onclick="runIngestion()">Отправить</button>
      <label for="ingestStatusJob">job_id</label>
      <input id="ingestStatusJob" placeholder="job_xxx" />
      <button onclick="checkIngestionStatus()">Статус</button>
      <pre id="ingestLog">...</pre>
      <pre id="ingestModelLogs">Логи модели</pre>
    </section>

    <section>
      <h3>Summarizer</h3>
      <label for="sumModel">Model</label>
      <input id="sumModel" placeholder="openai/gpt-4o-mini" />
      <label for="sumPrompt">System prompt</label>
      <textarea id="sumPrompt">Сделай короткое резюме.</textarea>
      <label><input id="sumUseRoles" type="checkbox" checked /> use roles</label>
      <div class="row-flex">
        <button onclick="loadSummarizerConfig()">Загрузить</button>
        <button onclick="saveSummarizerConfig()">Сохранить</button>
      </div>
      <pre id="sumConfig">...</pre>
    </section>

    <section>
      <h3>Chunking</h3>
      <label for="chunkSize">Chunk size (chars)</label>
      <input id="chunkSize" type="number" value="2048" />
      <label for="chunkOverlap">Overlap (chars)</label>
      <input id="chunkOverlap" type="number" value="200" />
      <div class="row-flex">
        <button onclick="loadChunkingConfig()">Загрузить</button>
        <button onclick="saveChunkingConfig()">Сохранить</button>
      </div>
      <pre id="chunkConfig">...</pre>
    </section>

    <section>
      <h3>Retrieval (backend)</h3>
      <label for="retrQuery">Query</label>
      <input id="retrQuery" value="ldap" />
      <label for="retrMax">max_results</label>
      <input id="retrMax" type="number" value="5" />
      <label for="retrDocIds">doc_ids (через ,)</label>
      <input id="retrDocIds" placeholder="doc_1,doc_2" />
      <label for="retrFilters">filters (JSON)</label>
      <textarea id="retrFilters">{}</textarea>
      <label><input id="retrRerank" type="checkbox" /> использовать reranker</label>
      <button onclick="runRetrievalBackend()">Поиск</button>
      <pre id="retrBackendLog">...</pre>
    </section>

    <section>
      <h3>Retrieval config</h3>
      <label for="docTopK">doc_top_k</label>
      <input id="docTopK" type="number" value="5" />
      <label for="sectionTopK">section_top_k</label>
      <input id="sectionTopK" type="number" value="10" />
      <label for="chunkTopK">chunk_top_k</label>
      <input id="chunkTopK" type="number" value="20" />
      <label for="maxResults">max_results</label>
      <input id="maxResults" type="number" value="5" />
      <label for="topkPerDoc">topk_per_doc</label>
      <input id="topkPerDoc" type="number" value="0" />
      <label for="minScore">min_score</label>
      <input id="minScore" type="number" step="0.01" />
      <label><input id="enableFilters" type="checkbox" /> enable_filters</label>
      <label><input id="rerankEnabled" type="checkbox" /> rerank_enabled</label>
      <label for="rerankModel">rerank_model</label>
      <input id="rerankModel" placeholder="gpt-4o-mini" />
      <label for="rerankTopN">rerank_top_n</label>
      <input id="rerankTopN" type="number" value="5" />
      <div class="row-flex">
        <button onclick="loadRetrievalConfig()">Load</button>
        <button onclick="saveRetrievalConfig()">Save</button>
      </div>
      <pre id="retrConfigLog">...</pre>
    </section>

    <section>
      <h3>Orchestrator (RAG+MCP)</h3>
      <label for="orchQuery">Query</label>
      <input id="orchQuery" value="Explain LDAP setup" />
      <label for="orchMaxResults">max_results</label>
      <input id="orchMaxResults" type="number" value="5" />
      <label for="orchDocIds">doc_ids (comma sep)</label>
      <input id="orchDocIds" placeholder="doc_1,doc_2" />
      <label for="orchFilters">filters (JSON)</label>
      <textarea id="orchFilters">{}</textarea>
      <label for="orchTrace">trace_id</label>
      <input id="orchTrace" placeholder="trace-123" />
      <button onclick="runOrchestrator()">Запустить</button>
      <pre id="orchAnswer">...</pre>
      <pre id="orchSources">sources</pre>
      <pre id="orchTools">tools (MCP)</pre>
      <h4>Config</h4>
      <label for="orchModel">default_model</label>
      <input id="orchModel" placeholder="gpt-4o-mini" />
      <label for="orchStrategy">model_strategy</label>
      <input id="orchStrategy" placeholder="rag_mcp" />
      <label for="orchPromptBudget">prompt_token_budget</label>
      <input id="orchPromptBudget" type="number" value="4096" />
      <label for="orchContextBudget">context_token_budget</label>
      <input id="orchContextBudget" type="number" value="4096" />
      <label for="orchToolSteps">max_tool_steps</label>
      <input id="orchToolSteps" type="number" value="4" />
      <div class="row-flex">
        <label for="orchWinInit">window_initial</label><input id="orchWinInit" type="number" value="1" />
        <label for="orchWinStep">window_step</label><input id="orchWinStep" type="number" value="1" />
        <label for="orchWinMax">window_max</label><input id="orchWinMax" type="number" value="5" />
      </div>
      <label><input id="orchMock" type="checkbox" /> mock_mode</label>
      <div class="row-flex">
        <button onclick="loadOrchConfig()">Load cfg</button>
        <button onclick="saveOrchConfig()">Save cfg</button>
      </div>
    </section>

    <section>
      <h3>LLM Service</h3>
      <label for="llmModel">default_model</label>
      <input id="llmModel" placeholder="gpt-4o-mini" />
      <label for="llmRuntimeUrl">llm_runtime_url</label>
      <input id="llmRuntimeUrl" placeholder="http://runtime/v1/chat/completions" />
      <label for="llmToolSteps">max_tool_steps</label>
      <input id="llmToolSteps" type="number" value="3" />
      <label><input id="llmJsonMode" type="checkbox" checked /> enable_json_mode</label>
      <label><input id="llmMock" type="checkbox" /> mock_mode</label>
      <div class="row-flex">
        <button onclick="loadLLMConfig()">Load cfg</button>
        <button onclick="saveLLMConfig()">Save cfg</button>
      </div>
      <pre id="llmConfigLog">...</pre>
    </section>

    <section>
      <h3>Документы</h3>
      <label for="docDetailId">doc_id</label>
      <input id="docDetailId" placeholder="doc_xxx" />
      <div class="row-flex">
        <button onclick="loadDocumentDetail()">Детали</button>
        <button onclick="loadDocumentTree()">Дерево</button>
      </div>
      <pre id="docsList">...</pre>
      <pre id="docDetail">...</pre>
      <pre id="docTree">...</pre>
    </section>
  </div>

  <div class="grid grid-2" style="margin-top:16px;">
    <section>
      <h3>Retrieval steps</h3>
      <pre id="retrSteps">...</pre>
    </section>
    <section>
      <h3>Workflow Trace</h3>
      <pre id="workflow">docs → sections → chunks</pre>
    </section>
  </div>

  <script>
    const headers = () => ({ "Content-Type": "application/json", "X-Tenant-ID": document.getElementById("tenant").value || "observer_tenant" });
    const log = (id, data) => document.getElementById(id).textContent = JSON.stringify(data, null, 2);

    async function checkHealth() {
      const res = await fetch("/health");
      log("healthLog", await res.json());
    }
    async function loadSummarizerConfig() {
      const res = await fetch("/internal/observer/summarizer/config", {headers: headers()});
      const data = await res.json();
      document.getElementById("sumModel").value = data.model || "";
      document.getElementById("sumPrompt").value = data.system_prompt || "";
      document.getElementById("sumUseRoles").checked = data.use_roles !== false;
      log("sumConfig", data);
    }
    async function saveSummarizerConfig() {
      const payload = {
        model: document.getElementById("sumModel").value || null,
        system_prompt: document.getElementById("sumPrompt").value || null,
        use_roles: document.getElementById("sumUseRoles").checked
      };
      const res = await fetch("/internal/observer/summarizer/config", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("sumConfig", await res.json());
    }
    async function loadChunkingConfig() {
      const res = await fetch("/internal/observer/chunking/config", {headers: headers()});
      const data = await res.json();
      document.getElementById("chunkSize").value = data.chunk_size || 2048;
      document.getElementById("chunkOverlap").value = data.chunk_overlap || 0;
      log("chunkConfig", data);
    }
    async function saveChunkingConfig() {
      const payload = {
        chunk_size: Number(document.getElementById("chunkSize").value || 0) || null,
        chunk_overlap: Number(document.getElementById("chunkOverlap").value || 0) || null
      };
      const res = await fetch("/internal/observer/chunking/config", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("chunkConfig", await res.json());
    }
    async function runIngestion() {
      const fileInput = document.getElementById("ingestFile");
      if (!fileInput.files.length) { log("ingestLog", {error: "Выберите файл"}); return; }
      const fd = new FormData();
      fd.append("file", fileInput.files[0]);
      const res = await fetch("/internal/observer/ingestion/enqueue", {
        method: "POST",
        headers: {"X-Tenant-ID": document.getElementById("tenant").value},
        body: fd
      });
      const data = await res.json();
      log("ingestLog", data);
      if (data.job_id) document.getElementById("ingestStatusJob").value = data.job_id;
    }
    async function checkIngestionStatus() {
      const jobId = document.getElementById("ingestStatusJob").value;
      const res = await fetch("/internal/observer/ingestion/status", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Tenant-ID": document.getElementById("tenant").value},
        body: JSON.stringify({job_id: jobId})
      });
      const data = await res.json();
      log("ingestLog", data);
      const logs = (data.meta && data.meta.logs) ? data.meta.logs : [];
      log("ingestModelLogs", logs.length ? logs : {info: "Нет логов модели"});
    }
    async function loadDocuments() {
      const res = await fetch("/internal/observer/documents", {headers: headers()});
      log("docsList", await res.json());
    }
    async function loadDocumentDetail() {
      const docId = document.getElementById("docDetailId").value;
      if (!docId) { log("docDetail", {error: "Укажите doc_id"}); return; }
      const res = await fetch(`/internal/observer/documents/${docId}/detail`, {headers: headers()});
      log("docDetail", await res.json());
    }
    async function loadDocumentTree() {
      const docId = document.getElementById("docDetailId").value;
      if (!docId) { log("docTree", {error: "Укажите doc_id"}); return; }
      const res = await fetch(`/internal/observer/documents/${docId}/tree`, {headers: headers()});
      log("docTree", await res.json());
    }
    async function runRetrievalBackend() {
      const docIds = (document.getElementById("retrDocIds").value || "")
        .split(",").map(s => s.trim()).filter(Boolean);
      let filters = {};
      try { filters = JSON.parse(document.getElementById("retrFilters").value || "{}"); } catch (e) { filters = {}; }
      const payload = {
        query: document.getElementById("retrQuery").value || "",
        max_results: Number(document.getElementById("retrMax").value || 0) || null,
        doc_ids: docIds.length ? docIds : null,
        filters: filters,
        rerank_enabled: document.getElementById("retrRerank").checked
      };
      const res = await fetch("/internal/observer/retrieval/search", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      const data = await res.json();
      log("retrBackendLog", data);
      if (data.steps) {
        log("retrSteps", data.steps);
        log("workflow", {
          docs: data.steps.docs ? data.steps.docs.length : 0,
          sections: data.steps.sections ? data.steps.sections.length : 0,
          chunks: data.steps.chunks ? data.steps.chunks.length : 0
        });
      } else {
        log("retrSteps", {info: "steps not provided"});
      }
    }
    async function runOrchestrator() {
      let filters = null;
      try { filters = document.getElementById("orchFilters").value ? JSON.parse(document.getElementById("orchFilters").value) : null; } catch (e) { filters = null; }
      const docIds = (document.getElementById("orchDocIds").value || "").split(",").map(s => s.trim()).filter(Boolean);
      const payload = {
        query: document.getElementById("orchQuery").value || "",
        max_results: Number(document.getElementById("orchMaxResults").value || 0) || null,
        doc_ids: docIds.length ? docIds : null,
        filters: filters,
        trace_id: document.getElementById("orchTrace").value || `trace-${Math.random().toString(36).slice(2,7)}`
      };
      const res = await fetch("/internal/observer/orchestrator/respond", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      const data = await res.json();
      log("orchAnswer", data);
      log("orchSources", data.sources || []);
      log("orchTools", data.tools || data.tool_calls || []);
    }
    async function loadOrchConfig() {
      const res = await fetch("/internal/observer/orchestrator/config", {headers: headers()});
      const data = await res.json();
      document.getElementById("orchModel").value = data.default_model || "";
      document.getElementById("orchStrategy").value = data.model_strategy || "";
      document.getElementById("orchPromptBudget").value = data.prompt_token_budget ?? 0;
      document.getElementById("orchContextBudget").value = data.context_token_budget ?? 0;
      document.getElementById("orchToolSteps").value = data.max_tool_steps ?? 0;
      document.getElementById("orchWinInit").value = data.window_initial ?? 0;
      document.getElementById("orchWinStep").value = data.window_step ?? 0;
      document.getElementById("orchWinMax").value = data.window_max ?? 0;
      document.getElementById("orchMock").checked = !!data.mock_mode;
      log("orchAnswer", data);
    }
    async function saveOrchConfig() {
      const payload = {
        default_model: document.getElementById("orchModel").value || null,
        prompt_token_budget: Number(document.getElementById("orchPromptBudget").value || 0) || null,
        context_token_budget: Number(document.getElementById("orchContextBudget").value || 0) || null,
        max_tool_steps: Number(document.getElementById("orchToolSteps").value || 0) || null,
        window_initial: Number(document.getElementById("orchWinInit").value || 0) || null,
        window_step: Number(document.getElementById("orchWinStep").value || 0) || null,
        window_max: Number(document.getElementById("orchWinMax").value || 0) || null,
        mock_mode: document.getElementById("orchMock").checked
      };
      const strategy = document.getElementById("orchStrategy").value;
      if (strategy) payload.model_strategy = strategy;
      const res = await fetch("/internal/observer/orchestrator/config", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("orchAnswer", await res.json());
    }
    async function loadLLMConfig() {
      const res = await fetch("/internal/observer/llm/config", {headers: headers()});
      const data = await res.json();
      document.getElementById("llmModel").value = data.default_model || "";
      document.getElementById("llmToolSteps").value = data.max_tool_steps ?? 0;
      document.getElementById("llmJsonMode").checked = !!data.enable_json_mode;
      document.getElementById("llmMock").checked = !!data.mock_mode;
      document.getElementById("llmRuntimeUrl").value = data.llm_runtime_url || "";
      log("llmConfigLog", data);
    }
    async function saveLLMConfig() {
      const payload = {
        default_model: document.getElementById("llmModel").value || null,
        max_tool_steps: Number(document.getElementById("llmToolSteps").value || 0) || null,
        enable_json_mode: document.getElementById("llmJsonMode").checked,
        mock_mode: document.getElementById("llmMock").checked,
        llm_runtime_url: document.getElementById("llmRuntimeUrl").value || null
      };
      const res = await fetch("/internal/observer/llm/config", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("llmConfigLog", await res.json());
    }
    async function loadRetrievalConfig() {
      const res = await fetch("/internal/observer/retrieval/config", {headers: headers()});
      const data = await res.json();
      document.getElementById("docTopK").value = data.doc_top_k ?? "";
      document.getElementById("sectionTopK").value = data.section_top_k ?? "";
      document.getElementById("chunkTopK").value = data.chunk_top_k ?? "";
      document.getElementById("maxResults").value = data.max_results ?? "";
      document.getElementById("topkPerDoc").value = data.topk_per_doc ?? "";
      document.getElementById("minScore").value = data.min_score ?? "";
      document.getElementById("enableFilters").checked = !!data.enable_filters;
      document.getElementById("rerankEnabled").checked = !!data.rerank_enabled;
      document.getElementById("rerankModel").value = data.rerank_model ?? "";
      document.getElementById("rerankTopN").value = data.rerank_top_n ?? "";
      log("retrConfigLog", data);
    }
    async function saveRetrievalConfig() {
      const payload = {
        doc_top_k: Number(document.getElementById("docTopK").value || 0) || null,
        section_top_k: Number(document.getElementById("sectionTopK").value || 0) || null,
        chunk_top_k: Number(document.getElementById("chunkTopK").value || 0) || null,
        max_results: Number(document.getElementById("maxResults").value || 0) || null,
        topk_per_doc: Number(document.getElementById("topkPerDoc").value || 0) || null,
        min_score: document.getElementById("minScore").value ? Number(document.getElementById("minScore").value) : null,
        enable_filters: document.getElementById("enableFilters").checked,
        rerank_enabled: document.getElementById("rerankEnabled").checked,
        rerank_model: document.getElementById("rerankModel").value || null,
        rerank_top_n: Number(document.getElementById("rerankTopN").value || 0) || null
      };
      const res = await fetch("/internal/observer/retrieval/config", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("retrConfigLog", await res.json());
    }
  </script>
</body>
</html>
    """
