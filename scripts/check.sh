#!/bin/sh
# Run every check against the running Docker Compose stack. Stops at the first failure.
set -eu
cd "$(dirname "$0")/.."
compose() { docker compose --env-file .env -f infra/compose.yaml "$@"; }

echo "== API tests";        compose exec -T api pytest -q
echo "== API lint";         compose exec -T api ruff check src tests migrations
echo "== Migrations match"; compose exec -T api alembic check
echo "== Web tests";        compose exec -T web npm test --silent
echo "== Web typecheck";    compose exec -T web npm run typecheck --silent
echo "== Web build";        compose exec -T web npm run build --silent
echo "== Smoke";            python3 scripts/smoke.py
echo "All checks passed."
