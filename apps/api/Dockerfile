FROM python:3.12-slim AS development
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src
RUN pip install --no-cache-dir ".[dev]" && useradd --create-home appuser && chown appuser /app
COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
COPY apps/api/tests ./tests
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn jobpilot.main:app --app-dir src --reload-dir src --host 0.0.0.0 --port 8000 --reload"]
