# JobPilot AI

AI-powered job discovery, matching, and resume tailoring. Users review materials and apply manually.

## Local quick start

Install Docker Desktop/Engine with Docker Compose v2 and start the Docker daemon. From the repository root:

```sh
cp .env.example .env
docker compose --env-file .env -f infra/compose.yaml up --build --wait
```

Open http://localhost:3000 for the dashboard, http://localhost:3000/resumes to upload a resume, http://localhost:3000/library to review and verify your experience and skills, http://localhost:3000/preferences to set job preferences, http://localhost:3000/jobs to add jobs and see explainable matches, and http://localhost:8000/docs for API documentation. The API applies database migrations automatically when it starts.

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
python3 scripts/smoke.py
```

Both API endpoints return `{"status":"ok"}` when healthy. `/health` checks the API process; `/ready` checks PostgreSQL and returns 503 if unavailable.

## Checks

With the stack running, `scripts/check.sh` runs everything below plus a migrations-vs-models check and the smoke test:

```sh
./scripts/check.sh
```

Or individually:

```sh
docker compose --env-file .env -f infra/compose.yaml exec api pytest -q
docker compose --env-file .env -f infra/compose.yaml exec api ruff check src tests migrations
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

Implemented so far: a Next.js/TypeScript/Tailwind dashboard, a modular FastAPI service, PostgreSQL with Alembic migrations, local containers, smoke tests, and resume upload and parsing (PDF, DOCX, or TXT up to 5 MB; text is extracted locally without AI and split into sections; the original file is not stored), and a verified experience and skills library. Importing a resume creates draft entries; only entries you verify will be used for tailoring, and editing a verified entry returns it to draft unless you re-verify it. Job preferences (titles, seniority, locations, work arrangement, employment type, minimum salary, keywords, excluded companies) can each be marked "must match"; the hard-filter logic in `services/preferences.py` explains every pass or fail and never rejects a job just because a detail is missing. Jobs can be pasted in (no scraping), are deduplicated, and have their requirements extracted by local rules or, if you configure an OpenAI key, by AI with timeouts, retries, caching, and spending limits. Each job gets a deterministic match: must-match filters, a weighted score over factors that could be judged, evidence from verified items only, and gaps. See [jobs and matching](docs/jobs-and-matching.md). No authentication, scraping, automatic applications, or paid infrastructure is implemented, and AI is off unless you add a key. Without authentication, anyone who can reach the API can read uploaded resumes and library entries, so keep it bound to localhost.

Matching is explainable and scores are estimates. Resume tailoring must use verified experience and never invent qualifications, employers, dates, or accomplishments. Keep AI requests server-side and protect resumes and personal data.
