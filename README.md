# Support Orchestrator

AI-powered, multi-step support ticket orchestration service.

> **Note**: This README is a stub. The full README — quick-demo instructions,
> architecture diagram, API examples, configuration table, troubleshooting —
> is written in Stage 12 of the assessment build. See `ARCHITECTURE.md` and
> `AI_DEV_WORKFLOW.md` (both also written in Stage 12) for design rationale.

## Quick demo (no API key required)

```bash
make install
make demo-mock
```

## Run with a real LLM

```bash
cp .env.example .env  # set OPENAI_API_KEY and LLM_PROVIDER=openai
make run              # http://localhost:8000/docs
```

## Tests

```bash
make test             # pytest with coverage
```

## Docker

```bash
make docker-run       # docker compose up --build
```
