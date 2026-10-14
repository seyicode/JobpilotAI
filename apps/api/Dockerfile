FROM python:3.12-slim AS development
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src
RUN pip install --no-cache-dir ".[dev]" && useradd --create-home appuser && chown appuser /app
COPY apps/api/tests ./tests
USER appuser
EXPOSE 8000
CMD ["uvicorn", "jobpilot.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
