# JobPilot AI

AI-powered job discovery, matching, and resume tailoring. Users review materials and apply manually.

## Local quick start

Install Docker Desktop/Engine with Docker Compose v2 and start the Docker daemon. From the repository root:

```sh
cp .env.example .env
docker compose --env-file .env -f infra/compose.yaml up --build --wait
```

Open http://localhost:3000 for the dashboard and http://localhost:8000/docs for API documentation.

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
python3 scripts/smoke.py
```

Both API endpoints return `{"status":"ok"}` when healthy. `/health` checks the API process; `/ready` checks PostgreSQL and returns 503 if unavailable.

## Checks

With the stack running:

```sh
docker compose --env-file .env -f infra/compose.yaml exec api pytest -q
docker compose --env-file .env -f infra/compose.yaml exec api ruff check src tests
docker compose --env-file .env -f infra/compose.yaml exec web npm test
docker compose --env-file .env -f infra/compose.yaml exec web npm run typecheck
docker compose --env-file .env -f infra/compose.yaml exec web npm run build
```

Stop services without deleting database data:

```sh
docker compose --env-file .env -f infra/compose.yaml down
```

See [local development](docs/local-development.md) for native setup, configuration, architecture, and troubleshooting. See [ROADMAP.md](ROADMAP.md) for upcoming work.

## Scope and principles

This scaffold includes a Next.js/TypeScript/Tailwind dashboard, modular FastAPI service, PostgreSQL, local containers, and smoke tests. No authentication, scraping, AI generation, automatic applications, or paid infrastructure is implemented.

Future matching must be explainable. Resume tailoring must use verified experience and never invent qualifications, employers, dates, or accomplishments. Keep future AI requests server-side and protect resumes and personal data.
