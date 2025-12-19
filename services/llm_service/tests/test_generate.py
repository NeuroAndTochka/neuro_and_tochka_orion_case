from fastapi.testclient import TestClient

from llm_service.main import app


def base_payload(message: str):
    return {
        "mode": "rag",
        "system_prompt": "You are Visior",
        "messages": [{"role": "user", "content": message}],
        "context_chunks": [
            {
                "doc_id": "doc_1",
                "section_id": "sec_1",
                "text": "Context about LDAP",
                "page_start": 1,
                "page_end": 2,
            }
        ],
        "generation_params": {},
    }


def test_generate_plain_answer():
    with TestClient(app) as client:
        resp = client.post("/internal/llm/generate", json=base_payload("hello"))
        assert resp.status_code == 200
        data = resp.json()
        assert "Context" in data["answer"]
        assert data["meta"]["tool_steps"] == 0


def test_generate_with_tool_call_loop():
    payload = base_payload("TOOL_call please")
    with TestClient(app) as client:
        resp = client.post("/internal/llm/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tools_called"]
        assert data["meta"]["tool_steps"] == 1


def test_generate_accepts_openai_chat_payload():
    openai_payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [],
        "context": [],
    }
    with TestClient(app) as client:
        resp = client.post("/internal/llm/generate", json=openai_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "choices" in body
        assert "usage" in body
        assert body["choices"][0]["message"]["role"] == "assistant"
