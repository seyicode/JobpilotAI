# Local development

## Structure

- `apps/web/src/app`: Next.js App Router pages and layout.
- `apps/web/src/components`: reusable interface components.
- `apps/web/tests`: server-rendered dashboard smoke test.
- `apps/api/src/jobpilot/api/routes`: HTTP endpoints.
- `apps/api/src/jobpilot/core`: shared environment configuration.
- `apps/api/tests`: API smoke tests; database success and failure paths use mocks.
- `infra/compose.yaml`: local PostgreSQL, API, and web orchestration.
- `scripts/smoke.py`: live HTTP checks of the dashboard, API, and database readiness.

Introduce domain/service and persistence modules when business features require them. No schema, migrations, or sample personal data are created yet.

## Docker workflow

Run all commands from the repository root. Copy `.env.example` to `.env`, then run the README quick start. Compose uses source mounts for frontend and API reloads. Rebuild after dependency or configuration changes. Docker images contain development tooling; these are local development images, not production deployment artifacts.

PostgreSQL uses a named volume and survives `down`. Do not use `down -v` unless you intend to delete its data. Ports bind to `127.0.0.1`. The local password in the example is only for development. Changing database credentials in `.env` does not update an already initialized PostgreSQL volume.

Dependency ranges are constrained in package manifests. Lock files have not been generated because package installation was unavailable in the scaffold environment. After the first successful installation, review and retain a root `package-lock.json`; switch Docker's npm install to npm ci once that lock exists. Establish a Python dependency lock before deployment as well.

## Native workflow

Prerequisites: Node.js 22 LTS with npm, Python 3.12+, and Docker Compose v2. PostgreSQL can run in Docker while the web and API run natively.

```sh
cp .env.example .env
docker compose --env-file .env -f infra/compose.yaml up db -d --wait
python3.12 -m venv .venv
.venv/bin/python -m pip install -e 'apps/api[dev]'
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

The dashboard currently uses no API requests. `NEXT_PUBLIC_API_URL` is reserved for future browser requests; native Next.js reads environment files in `apps/web`, so set that variable in your shell or an ignored `apps/web/.env.local` when needed.

Native checks:

```sh
.venv/bin/pytest apps/api/tests -q
.venv/bin/ruff check apps/api/src apps/api/tests
npm test
npm run typecheck
npm run build
python3 scripts/smoke.py
```

## Configuration

All variables are documented in `.env.example`. `DATABASE_URL` uses `localhost` for native development; Compose builds a URL using the internal `db` hostname and PostgreSQL credentials. URL-encode any special characters in credentials. `CORS_ORIGINS` must be a JSON array of browser origins. If you change the web port, update this array; if you change the API port, update `NEXT_PUBLIC_API_URL`. Update the native database URL when changing the database host port or credentials.

Do not put secrets in `NEXT_PUBLIC_*` variables: those are browser-visible. No AI key is needed yet. `.gitignore` and `.dockerignore` exclude local secrets, resumes, uploads, and generated output. Store private documents only in those excluded folders; ignore rules cannot detect arbitrary personal data in other files.

## Troubleshooting and validation limits

Use `docker compose --env-file .env -f infra/compose.yaml logs api web db` to inspect failures. Check Docker is running and that host ports are free. `/health` can pass while `/ready` fails; the latter requires a real database connection. The live smoke script accepts `WEB_URL` and `API_URL` shell variables for alternate ports.

During scaffold creation, Compose configuration validation and Python syntax checks passed. Runtime checks could not run: Node/npm were absent, installed Python was 3.9 without pytest, Docker socket access was denied, and the npm registry did not resolve. Builds, package installation, unit tests, and live container smoke checks therefore remain unverified.
