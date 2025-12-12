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
    async function runLLM() {
      const payload = {
        prompt: document.getElementById("prompt").value,
        context: (document.getElementById("context").value || "").split("\\n").filter(Boolean),
        experiment_id: document.getElementById("llmExp").value || null
      };
      const res = await fetch("/internal/observer/llm/dry-run", {method:"POST", headers: headers(), body: JSON.stringify(payload)});
      log("llmLog", await res.json());
    }
  </script>
</body>
</html>
    """
