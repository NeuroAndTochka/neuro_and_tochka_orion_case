# neuro_and_tochka_orion_case

## Running services locally with Docker

Each microservice has its own `Dockerfile` under `services/<service_name>`. To build and run all skeleton services together:

```bash
docker compose up --build
```

This starts:

- API Gateway on `http://localhost:8080`
- Safety Service on `http://localhost:8081`
- MCP Tools Proxy on `http://localhost:8082`
- LLM Service on `http://localhost:8090`

Stop everything with `docker compose down`. Use `docker compose up --build api_gateway` (or another service name) to rebuild/run individually.
