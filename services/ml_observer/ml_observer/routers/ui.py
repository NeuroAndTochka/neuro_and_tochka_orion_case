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
  <title>ML Observer Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f5f7fb; color: #111; }
    h1 { margin-bottom: 8px; }
    section { background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px; }
    label { display: block; margin: 6px 0 2px; font-weight: 600; }
    input, textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    button { margin-top: 8px; padding: 8px 12px; background: #0057ff; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
    button:hover { background: #0040c1; }
    pre { background: #0b1021; color: #d7e3ff; padding: 12px; border-radius: 6px; overflow: auto; }
    .row { display: grid; grid-template-columns: repeat(auto-fit,minmax(280px,1fr)); gap: 12px; }
  </style>
</head>
<body>
  <h1>ML Observer Dashboard</h1>
  <p>Быстрый мониторинг и ручной запуск действий. Заголовок tenant задаётся ниже.</p>

  <section>
    <label for="tenant">X-Tenant-ID</label>
    <input id="tenant" value="observer_tenant" />
    <button onclick="checkHealth()">Проверить health</button>
    <pre id="healthLog">Нажмите "Проверить health"</pre>
  </section>

  <div class="row">
    <section>
      <h3>Настройки summarizer</h3>
      <label for="sumModel">Model</label>
      <input id="sumModel" placeholder="openai/gpt-4o-mini" />
      <label for="sumMaxTokens">Max tokens</label>
      <input id="sumMaxTokens" type="number" value="120" />
      <label for="sumPrompt">System prompt</label>
      <textarea id="sumPrompt">Сделай короткое русскоязычное резюме секции документа (1-2 предложения). Без воды, без списков, только факты.</textarea>
      <label for="sumUseRoles">Использовать роли (system+user)</label>
      <input id="sumUseRoles" type="checkbox" checked />
      <button onclick="loadSummarizerConfig()">Загрузить текущие</button>
      <button onclick="saveSummarizerConfig()">Сохранить</button>
      <pre id="sumConfig"></pre>
    </section>

    <section>
      <h3>Chunking</h3>
      <label for="chunkSize">Chunk size (chars)</label>
      <input id="chunkSize" type="number" value="2048" />
      <label for="chunkOverlap">Overlap (chars)</label>
      <input id="chunkOverlap" type="number" value="200" />
      <button onclick="loadChunkingConfig()">Загрузить текущие</button>
      <button onclick="saveChunkingConfig()">Сохранить</button>
      <pre id="chunkConfig"></pre>
    </section>

    <section>
      <h3>Создать эксперимент</h3>
      <label for="expName">Название</label>
      <input id="expName" value="Demo experiment" />
      <label for="expDesc">Описание</label>
      <textarea id="expDesc">Test run</textarea>
      <label for="expParams">Params (JSON)</label>
      <textarea id="expParams">{}</textarea>
      <button onclick="createExperiment()">Создать</button>
      <pre id="expLog"></pre>
    </section>

    <section>
      <h3>Upload документа (mock)</h3>
      <label for="docId">doc_id</label>
      <input id="docId" value="doc_demo" />
      <label for="docName">name</label>
      <input id="docName" value="Demo Doc" />
      <label for="docExp">experiment_id (опц.)</label>
      <input id="docExp" placeholder="exp_id" />
      <button onclick="uploadDoc()">Отправить</button>
      <pre id="docLog"></pre>
    </section>

    <section>
      <h3>Запуск ingestion</h3>
      <label for="ingestFile">Файл</label>
      <input id="ingestFile" type="file" />
      <label for="ingestStatusJob">job_id (для статуса)</label>
      <input id="ingestStatusJob" placeholder="job_id" />
      <button onclick="runIngestion()">Отправить в ingestion</button>
      <button onclick="checkIngestionStatus()">Проверить статус</button>
      <pre id="ingestLog"></pre>
      <pre id="ingestModelLogs">Логи вызовов моделей появятся после проверки статуса</pre>
    </section>
  </div>

  <div class="row">
    <section>
      <h3>Retrieval run (mock)</h3>
      <label for="queries">Queries (через ;) </label>
      <input id="queries" value="ldap guide; sso" />
      <label for="topk">top_k</label>
      <input id="topk" type="number" value="3" />
      <label for="retrExp">experiment_id (опц.)</label>
      <input id="retrExp" placeholder="exp_id" />
      <button onclick="runRetrieval()">Запустить</button>
      <pre id="retrLog"></pre>
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
      <button onclick="runRetrievalBackend()">Выполнить</button>
      <pre id="retrBackendLog"></pre>
    </section>

    <section>
      <h3>LLM dry-run (mock)</h3>
      <label for="prompt">Prompt</label>
      <textarea id="prompt">Explain LDAP</textarea>
      <label for="context">Context (строки через \\n)</label>
      <textarea id="context">LDAP is ...\nUsed for directory services.</textarea>
      <label for="llmExp">experiment_id (опц.)</label>
      <input id="llmExp" placeholder="exp_id" />
      <button onclick="runLLM()">Запустить</button>
      <pre id="llmLog"></pre>
    </section>

    <section>
      <h3>Документы в БД</h3>
      <button onclick="loadDocuments()">Обновить список</button>
      <label for="docDetailId">doc_id для деталей</label>
      <input id="docDetailId" placeholder="doc_xxx" />
      <button onclick="loadDocumentDetail()">Показать детали</button>
      <button onclick="loadDocumentTree()">Показать дерево</button>
      <pre id="docsList"></pre>
      <pre id="docDetail"></pre>
      <pre id="docTree"></pre>
    </section>
  </div>

  <script>
    const headers = () => ({ "Content-Type": "application/json", "X-Tenant-ID": document.getElementById("tenant").value || "observer_tenant" });
    const log = (id, data) => document.getElementById(id).textContent = JSON.stringify(data, null, 2);

    async function checkHealth() {
      const res = await fetch("/health");
      log("healthLog", await res.json());
    }
    async function createExperiment() {
      const payload = {
        name: document.getElementById("expName").value,
        description: document.getElementById("expDesc").value,
        params: JSON.parse(document.getElementById("expParams").value || "{}")
      };
      const res = await fetch("/internal/observer/experiments", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("expLog", await res.json());
    }
    async function loadSummarizerConfig() {
      const res = await fetch("/internal/observer/summarizer/config", {headers: headers()});
      const data = await res.json();
      document.getElementById("sumModel").value = data.model || "";
      document.getElementById("sumMaxTokens").value = data.max_tokens || 120;
      document.getElementById("sumPrompt").value = data.system_prompt || "";
      document.getElementById("sumUseRoles").checked = data.use_roles !== false;
      log("sumConfig", data);
    }
    async function saveSummarizerConfig() {
      const payload = {
        model: document.getElementById("sumModel").value || null,
        max_tokens: Number(document.getElementById("sumMaxTokens").value || 0) || null,
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
    async function uploadDoc() {
      const payload = {
        doc_id: document.getElementById("docId").value,
        name: document.getElementById("docName").value,
        experiment_id: document.getElementById("docExp").value || null
      };
      const res = await fetch("/internal/observer/documents/upload", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("docLog", await res.json());
    }
    async function runRetrieval() {
      const qs = (document.getElementById("queries").value || "").split(";").map(s => s.trim()).filter(Boolean);
      const payload = {
        queries: qs,
        top_k: Number(document.getElementById("topk").value || 3),
        experiment_id: document.getElementById("retrExp").value || null
      };
      const res = await fetch("/internal/observer/retrieval/run", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("retrLog", await res.json());
    }
    async function runRetrievalBackend() {
      const docIds = (document.getElementById("retrDocIds").value || "")
        .split(",")
        .map(s => s.trim())
        .filter(Boolean);
      let filters = {};
      try { filters = JSON.parse(document.getElementById("retrFilters").value || "{}"); } catch (e) { filters = {}; }
      const payload = {
        query: document.getElementById("retrQuery").value || "",
        max_results: Number(document.getElementById("retrMax").value || 0) || null,
        doc_ids: docIds.length ? docIds : null,
        filters: filters
      };
      const res = await fetch("/internal/observer/retrieval/search", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("retrBackendLog", await res.json());
    }
    async function runLLM() {
      const payload = {
        prompt: document.getElementById("prompt").value,
        context: (document.getElementById("context").value || "").split("\\n").filter(Boolean),
        experiment_id: document.getElementById("llmExp").value || null
      };
      const res = await fetch("/internal/observer/llm/dry-run", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("llmLog", await res.json());
    }

    async function runIngestion() {
      const fileInput = document.getElementById("ingestFile");
      if (!fileInput.files.length) {
        log("ingestLog", {error: "Выберите файл"});
        return;
      }
      const fd = new FormData();
      fd.append("file", fileInput.files[0]);
      const res = await fetch("/internal/observer/ingestion/enqueue", {
        method: "POST",
        headers: {"X-Tenant-ID": document.getElementById("tenant").value},
        body: fd
      });
      const data = await res.json();
      log("ingestLog", data);
      if (data.job_id) {
        document.getElementById("ingestStatusJob").value = data.job_id;
      }
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
  </script>
</body>
</html>
    """
