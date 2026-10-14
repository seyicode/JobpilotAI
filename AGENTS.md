# Codex project instructions: JobPilot AI

Build an AI-powered job discovery, matching, and resume tailoring application. The user remains responsible for applying.

## Engineering requirements
- Use Next.js with TypeScript for web, FastAPI for API, PostgreSQL for persistence.
- Prefer a monorepo with `apps/web`, `apps/api`, `infra`, and `docs`.
- Use Docker Compose for local development.
- Implement features in small, testable increments. Add tests for business logic and API endpoints.
- Use environment variables for secrets; never commit credentials, API keys, or user resumes.
- Keep OpenAI API requests on the backend. Add timeouts, retry limits, cost controls, and logging without sensitive data.
- Use source adapters for job ingestion, starting with user-provided job descriptions and permitted feeds.
- Make matching explainable and configurable; scores are estimates, not guarantees.
- Tailoring must only rephrase or select verifiable user experience; never fabricate claims.
- Never implement automatic job application submission without a future explicit change in requirements.
- Ask before making destructive changes or deploying paid cloud resources.

## First task
Scaffold a minimal monorepo with Next.js, FastAPI, PostgreSQL, and Docker Compose. Add `/health` endpoint, a landing/dashboard placeholder, `.env.example`, setup instructions, and smoke tests. Do not add paid infrastructure yet.
