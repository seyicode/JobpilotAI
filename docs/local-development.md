# Local development

## Structure

- `apps/web/src/app`: Next.js App Router pages and layout.
- `apps/web/src/components`: reusable interface components.
- `apps/web/tests`: server-rendered component and helper tests.
- `apps/api/src/jobpilot/api/routes`: HTTP endpoints.
- `apps/api/src/jobpilot/core`: shared environment configuration.
- `apps/api/src/jobpilot/db`: SQLAlchemy engine, sessions, and models.
- `apps/api/src/jobpilot/services`: business logic: `resume_parser.py` (local PDF/DOCX/TXT text extraction and section splitting) `library_import.py` (heuristics that turn parsed sections into draft experience entries and skills), `preferences.py` (job preference validation and explainable hard filters), `job_ingestion.py` (duplicate detection), `extraction/` (requirement schema, local rules, and the optional OpenAI extractor), `skills.py` (skill name normalisation), `matching.py` (explainable scoring), `ai/` (the shared OpenAI client with all AI controls), and `resumes/` (profile and resume schema, deterministic assembly, edit rules and claims checks, AI rewording, DOCX/PDF export). See [jobs and matching](jobs-and-matching.md) and [resume tailoring](resume-tailoring.md).
- `apps/api/migrations`: Alembic migrations, applied by `alembic upgrade head` when the API container starts.
- `apps/api/tests`: API and parser tests. Health tests mock the database; resume API tests use a real `<POSTGRES_DB>_test` database that is created and migrated automatically and skipped if PostgreSQL is unreachable. Test resumes are fictional and built in memory (`tests/samples.py`).
- `apps/web/src/lib`: API client helpers and validation.
- `infra/compose.yaml`: local PostgreSQL, API, and web orchestration.
- `scripts/smoke.py`: live HTTP checks of the dashboard, API, and database readiness.
- `scripts/check.sh`: every test, lint, type, build, migration, and smoke check against the running stack.

To change the schema, edit `db/models.py` and add a migration in `apps/api/migrations/versions`, for example with `docker compose --env-file .env -f infra/compose.yaml exec api alembic revision --autogenerate -m "describe change"` (the migrations folder is mounted read-only, so write the file on the host or adjust the mount). Restart the API to apply it.

## Docker workflow

Run all commands from the repository root. Copy `.env.example` to `.env`, then run the README quick start. Compose mounts `apps/web/src`, `apps/api/src`, `apps/api/tests`, and `apps/api/migrations` so code changes reload without rebuilding. Rebuild after dependency or configuration changes, and rebuild `web` after changing `apps/web/tests`, which is not mounted. Docker images contain development tooling; these are local development images, not production deployment artifacts.

PostgreSQL uses a named volume and survives `down`. Do not use `down -v` unless you intend to delete its data. Ports bind to `127.0.0.1`. The local password in the example is only for development. Changing database credentials in `.env` does not update an already initialized PostgreSQL volume.

Dependency ranges are constrained in package manifests. Lock files have not been generated because package installation was unavailable in the scaffold environment. After the first successful installation, review and retain a root `package-lock.json`; switch Docker's npm install to npm ci once that lock exists. Establish a Python dependency lock before deployment as well.

## Native workflow

Prerequisites: Node.js 22 LTS with npm, Python 3.12+, and Docker Compose v2. PostgreSQL can run in Docker while the web and API run natively.

```sh
cp .env.example .env
docker compose --env-file .env -f infra/compose.yaml up db -d --wait
python3.12 -m venv .venv
.venv/bin/python -m pip install -e 'apps/api[dev]'
(cd apps/api && ../../.venv/bin/alembic upgrade head)
npm install
```

API terminal, from the root (settings read the root `.env`):

```sh
.venv/bin/uvicorn jobpilot.main:app --reload --host 127.0.0.1 --port 8000
```

Web terminal, from the root:

```sh
npm run dev:web
```

The resumes page calls the API from the browser using `NEXT_PUBLIC_API_URL`; native Next.js reads environment files in `apps/web`, so set that variable in your shell or an ignored `apps/web/.env.local` when needed.

Native checks:

```sh
.venv/bin/pytest apps/api/tests -q
.venv/bin/ruff check apps/api/src apps/api/tests apps/api/migrations
npm test
npm run typecheck
npm run build
python3 scripts/smoke.py
```

## Configuration

All variables are documented in `.env.example`. `DATABASE_URL` uses `localhost` for native development; Compose builds a URL using the internal `db` hostname and PostgreSQL credentials. URL-encode any special characters in credentials. `CORS_ORIGINS` must be a JSON array of browser origins. If you change the web port, update this array; if you change the API port, update `NEXT_PUBLIC_API_URL`. Update the native database URL when changing the database host port or credentials.

Do not put secrets in `NEXT_PUBLIC_*` variables: those are browser-visible. The `api` service also loads `.env` directly, so optional settings such as `MAX_RESUME_BYTES`, `MATCH_WEIGHTS`, `RESUME_PAGE_SIZE`, and the `OPENAI_*`/`AI_*` variables reach it (and only it); blank values count as unset. `MAX_RESUME_BYTES` (default 5 MB) limits uploads on the API; the web page also checks 5 MB before uploading. No AI key is needed; AI extraction is optional and documented in [jobs and matching](jobs-and-matching.md). `.gitignore` and `.dockerignore` exclude local secrets, resumes, uploads, and generated output. Store private documents only in those excluded folders; ignore rules cannot detect arbitrary personal data in other files.

## Troubleshooting and validation limits

Use `docker compose --env-file .env -f infra/compose.yaml logs api web db` to inspect failures. Check Docker is running and that host ports are free. `/health` can pass while `/ready` fails; the latter requires a real database connection. The live smoke script accepts `WEB_URL` and `API_URL` shell variables for alternate ports.

Uploads that fail to parse return 422 with a user-safe message; scanned or image-only PDFs have no extractable text and are rejected. Section detection matches common English headings on their own line; anything before the first heading is grouped as "Header". Library import treats blank lines, or a plain line after bullet points, as the start of a new entry; it reads date ranges like `Mar 2021 - Present`, `03/2021 – 2023`, or `2019 to 2020`, and skips entries and skills already in the library. Results are always unverified drafts for the user to correct. Job preferences are stored as one validated JSON document (single-user until authentication exists). Hard filters return `pass`, `fail`, or `unknown` with a reason; salaries are compared as annual amounts (hourly × 2080, monthly × 12) only when currencies match. All checks in the README pass in Docker. The native workflow needs Node.js 22 and Python 3.12+ installed locally.
