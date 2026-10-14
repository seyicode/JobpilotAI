# Jobs, requirement extraction, and matching

Milestone 2 lets users paste job descriptions, extracts each job's requirements, and explains how well the job matches their preferences and verified experience. JobPilot never fetches job pages and never applies for jobs.

## Flow

1. **Ingest** (`POST /jobs`): the user pastes a description (50–50,000 characters) with an optional URL, title, and company. The description and URL are stored exactly as given.
2. **Deduplicate**: a job is a duplicate if its normalised description (case, whitespace, and punctuation ignored) or its canonical URL matches a saved job. The canonical URL ignores http vs https, `www.`, fragments, trailing slashes, tracking parameters (`utm_*`, `gclid`, `ref`, …), and query order. A duplicate returns the saved job with `200` and `"duplicate": true`, and no extraction (or AI spend) happens.
3. **Extract**: OpenAI when configured, otherwise local rules (see below). The result, method (`openai`, `rules`, or `manual`), and a user-facing note are stored on the job.
4. **Review**: users can correct requirements (`PUT /jobs/{id}/requirements`, saved as `manual`) or extract again (`POST /jobs/{id}/extract`, which replaces corrections).
5. **Match** (`GET /jobs/{id}/match`): computed on request from the stored requirements, current preferences, and current library, so it always reflects the latest data. `GET /jobs` includes each job's score, coverage, and eligibility.

## Extracted requirements

`services/extraction/schema.py` (`JobRequirements`): title, company, required and preferred skills, seniority, location, work arrangement, employment type, salary (min, max, currency, period), minimum years of experience, and qualifications.

**Missing means unknown.** A null field or empty list means the posting did not say, never "not required". Matching treats unknown details as unknown: they are never counted against a job or the user.

Skill names are compared through `services/skills.py`, which lowercases them and resolves common aliases (`postgres` → PostgreSQL, `k8s` → Kubernetes, `golang` → Go, …).

### Local rules (always available)

`services/extraction/rules.py` is free, offline, and deterministic.

- **Skills** come from a built-in vocabulary of about 100 common skills plus the names of skills in the user's library. A skill mentioned only under a "nice to have / preferred / bonus" heading or phrase is preferred; anywhere else it is required.
- **Other fields** use patterns: seniority from the title (then explicit level words in the body), "Location:" lines, hybrid/remote/on-site wording (with simple negation such as "not remote"), salary amounts with a currency symbol or code and a period, "N+ years … experience", and degree, certification, clearance, or work-authorisation lines.
- **Limits.** Skills outside the vocabulary and the user's library are missed. `$` is read as USD. Unusual layouts can put skills in the wrong bucket. Users can correct anything on the Jobs page.

### OpenAI (optional, paid)

`services/extraction/openai_extractor.py` calls the Chat Completions REST endpoint directly with `httpx` and a strict JSON schema, then validates the response with the same Pydantic model. It is used only when both `OPENAI_API_KEY` and `OPENAI_MODEL` are set in `.env`.

| Concern | How it is handled |
| --- | --- |
| Key exposure | Read by the API container only (`env_file` on the `api` service). Never sent to the browser, logged, or stored. Never put it in a `NEXT_PUBLIC_*` variable. |
| Timeouts | `AI_TIMEOUT_SECONDS` (default 20) per request, with a 5-second connect timeout. |
| Retries | `AI_MAX_RETRIES` (default 2) on timeouts, network errors, 408/409/429/5xx, with exponential backoff from `AI_RETRY_BASE_DELAY_SECONDS` or `Retry-After`, capped at 5 seconds. Other 4xx errors are not retried. |
| Spending | Checked before each request against the `ai_usage` ledger: `AI_DAILY_REQUEST_LIMIT` (default 50 attempts per UTC day), `AI_MONTHLY_TOKEN_LIMIT` (default 1,000,000, including an estimate for the next request), and optional `AI_MONTHLY_BUDGET_USD`, which requires `AI_INPUT_COST_PER_MILLION_TOKENS_USD` and `AI_OUTPUT_COST_PER_MILLION_TOKENS_USD`. Input is cut to `AI_MAX_INPUT_CHARS` and output capped at `AI_MAX_OUTPUT_TOKENS`. |
| Caching | Results are cached in `ai_cache` by a hash of the prompt version, model, and input. Re-extracting the same posting costs nothing. Change `PROMPT_VERSION` when the prompt or schema changes. |
| Logging | Model, status, attempt, token counts, and latency only. Never postings, outputs, or keys. The ledger stores no text. |
| Grounding | Skills the model returns that do not appear in the posting (by name or alias) are dropped, and the note says how many. |
| Prompt injection | Postings are wrapped in `<posting>` tags, and the system prompt tells the model to ignore instructions inside them. Output is constrained by the schema and validated. |
| Failure | Not configured, limit reached, timeout, HTTP error, refusal, or invalid output all fall back to local rules. The job's note says why (e.g. "The monthly AI budget has been reached. Used local rules instead."). |

To turn AI on, set `OPENAI_API_KEY`, `OPENAI_MODEL`, and ideally the two price variables and a monthly budget in `.env` (check your provider's current prices), then restart the API: `docker compose --env-file .env -f infra/compose.yaml up -d api`. The model must support structured outputs with `json_schema`. No live AI request has been made during development; the client is tested against an in-memory fake of the HTTP API.

## Matching

`services/matching.py` is deterministic: the same inputs always give the same result.

**Eligibility** comes from the user's must-match preferences plus the always-on exclusions (excluded companies and keywords). A job fails only on a known conflict; a missing detail gives "unknown" and passes. Filtered-out jobs still get a full breakdown, so users can see why.

**Score** is a weighted average over the factors that could be judged:

| Factor | Default weight | Value |
| --- | --- | --- |
| Required skills | 35 | Share of required skills backed by the verified library |
| Preferred skills | 10 | Same, for preferred skills |
| Years of experience | 15 | Verified, dated work years ÷ required years (capped at 1). Overlapping jobs count once. |
| Seniority | 10 | 1 if the job's level is a target level, 0.5 if one step away, otherwise 0 |
| Job title | 10 | 1 if a target title appears in the job title, otherwise the share of its words that do |
| Keywords you want | 10 | Share of wanted keywords the posting mentions |
| Other preferences | 10 | Share of non-must-match preferences (arrangement, location, employment type, salary) that pass, among those that could be checked |

A factor is **unknown** when the job or the user lacks the information (for example, no years stated or no target titles set). Unknown factors are left out of the score, and **coverage** reports the share of total weight that was judged. A 90% score with 35% coverage rests on much less information than the same score with 100% coverage. Override weights with `MATCH_WEIGHTS` in `.env`, e.g. `MATCH_WEIGHTS={"required_skills": 50, "keywords": 0}`. Unknown factor names or negative weights stop the API at startup.

**Evidence** comes only from verified library items: a verified skill with the same name (or alias), and verified experience entries whose title or highlights mention it, with the highlight quoted. **Gaps** list unmatched requirements. When a draft skill or draft entry could cover a gap, the gap says so, but drafts never count as evidence.

Scores are estimates, not guarantees, and the UI says so.

## Data

| Table | Contents |
| --- | --- |
| `jobs` | Original description and URL, canonical URL and description hash (both unique), requirements (JSON), extraction method and note |
| `ai_usage` | One row per AI request attempt: purpose, model, status, tokens, estimated cost, latency. No text. |
| `ai_cache` | Validated AI results keyed by hash |

## Architecture decisions

- **HTTP API instead of the OpenAI SDK.** The SDK is on a new major version whose interface could not be verified offline. A direct `httpx` call keeps timeouts, retries, and logging fully explicit, and tests replace the transport, so no request can reach OpenAI from the test suite.
- **AI off by default.** Both a key and a model are required, so no paid call can happen by accident.
- **Matching is computed on request, not stored.** Library verification, preference changes, and requirement corrections apply immediately. The cost is a recomputation on each list request, which is fine for one user's jobs.
- **One requirements schema for every source.** AI output, rule output, and user corrections share one validated shape, so matching never needs to know where the data came from.

## Limitations

- Single user, no authentication, localhost only.
- No URL fetching or scraping: the URL is a reference and a dedup key only.
- Rule-based extraction is heuristic; see its limits above. AI extraction quality has not been measured on real postings.
- Spending limits check before each request, so a single request can exceed a limit slightly when it uses more tokens than estimated.
- Title matching is word overlap; it does not know synonyms ("SWE" vs "Software Engineer").
- Experience matching looks for skill names in verified entries; it does not judge depth or recency.
