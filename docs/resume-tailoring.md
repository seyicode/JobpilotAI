# Resume tailoring and export

Milestone 3 turns a saved job and the verified library into a tailored resume that the user reviews, approves, and downloads as DOCX or PDF. Tailoring only selects and rewords verified experience; it never adds employers, dates, achievements, metrics, credentials, or skills. JobPilot never applies for jobs.

## Flow

1. **Profile** (`GET/PUT /profile`, on the Library page): name, headline, email, phone, location, up to 5 links, and a summary. Used verbatim in resume headers.
2. **Generate** (`POST /jobs/{id}/resumes`, optional `{"method": "ai"}`): creates the next numbered **draft** version for that job.
3. **Review and edit** (`PUT /tailored-resumes/{id}`, on `/jobs/{id}/resume`): side by side with the library entries each line came from.
4. **Approve** (`POST /tailored-resumes/{id}/approve`): locks the version. Warnings must be acknowledged (`{"acknowledge_warnings": true}`), and approval fails if the library has changed since.
5. **Export** (`GET /tailored-resumes/{id}/export?format=pdf|docx`): approved versions only.

Other endpoints: `GET /jobs/{id}/resumes` (version history, newest first), `GET /tailored-resumes/{id}`, `POST /tailored-resumes/{id}/copy` (new draft from any version), `DELETE /tailored-resumes/{id}` (drafts only), and `GET /ai/status` (whether AI is configured; nothing else).

## Deterministic assembly (no AI)

`services/resumes/assembly.py` is free, offline, and deterministic. It uses verified entries and skills only, and copies text exactly.

| Part | Rule |
| --- | --- |
| Header, summary | From the profile, unchanged |
| Skills | Verified skills: those the job requires, then preferred, then the rest alphabetically (up to 30) |
| Experience | Every verified job, newest first (current roles first) |
| Bullets | Verified highlights ranked by relevance: required skills count 2, preferred 1, plus 1 if the highlight is quoted as match evidence. Up to 5 for the two most recent jobs, 3 for older ones, 2 for older jobs that mention none of the job's skills. Ties keep library order. |
| Projects | Only those mentioning a job skill, most relevant first, up to 3 |
| Education, certifications | Always included (certifications: relevant first) |
| Volunteering, other | Only when relevant |

Every entry and bullet records why it was chosen (for example, "Mentions Python, PostgreSQL (required).").

## Content model and edit rules

`services/resumes/schema.py`: a tailored resume is stored as structured data (`ResumeContent`), never as a file. Each entry keeps its library `source_id`; each bullet keeps its `source_text` (the verified highlight) and `changed_by` (`none`, `ai`, or `user`).

`services/resumes/review.py` enforces these rules on every save:

| Rule | On violation |
| --- | --- |
| Title, organisation, location, and dates are re-copied from the library | Silently corrected |
| Entries must be verified library entries, each at most once | Rejected (422) |
| Every bullet must come from its entry's verified highlights | Rejected |
| Skills must be verified (aliases accepted, verified spelling used) | Rejected |
| Header contact details must be valid | Rejected |
| Reworded bullets that add numbers, skills or tools, or names not in the source; a summary that adds numbers beyond the profile summary or mentions unverified skills | **Warning**, which must be acknowledged before approval |

`services/resumes/claims.py` does the checking: it compares normalised numbers (`1,200` = `1200`), skill mentions (built-in vocabulary plus library skills, with aliases), and capitalised words that are not starting a sentence.

## Versions

Table `tailored_resumes`: one row per version, unique per `(job_id, version)`, with `status` (`draft`/`approved`), `generation_method` (`deterministic`/`ai`), `edited`, `based_on_version`, `content`, `warnings`, a `note` describing how it was made (including any AI fallback reason), and timestamps (`approved_at`). Approved versions cannot be edited or deleted; copy one to change it. Deleting a job deletes its versions.

## Optional AI rewording

`services/resumes/ai_rewriter.py`, using the shared client in `services/ai/openai_client.py`, so extraction and rewording share the same timeouts, retries, spending limits, cache, and usage ledger (`purpose = resume_rewrite`). See [jobs and matching](jobs-and-matching.md) for configuration. AI is off unless `OPENAI_API_KEY` and `OPENAI_MODEL` are set.

- **Bullets only.** The model sees bullet text, the target job title, and job keywords. It never sees names, employers, dates, contact details, or the summary.
- **Every rewrite is fact-checked.** A rewrite is discarded, keeping the verified wording, if it adds a number, a skill or tool, or a name not in the original; if it is empty or missing; or if it is more than 1.5× the original length plus 40 characters. The reason is recorded on the bullet, and the version note counts accepted and rejected rewrites.
- **Fallback.** If AI is not configured, a limit is reached, or the request fails, the version is created from the verified wording with `generation_method = deterministic` and a note explaining why.
- **Prompt injection.** Bullets are sent as JSON data, and the system prompt says to ignore instructions inside it.
- No live AI request has been made during development; tests use an in-memory fake of the HTTP API.

## Export

`services/resumes/export.py` renders in memory with `python-docx` and `reportlab`.

- **ATS-friendly.** One column; standard section headings (real Heading 1 style in DOCX); plain bullets; contact details in the body, not page headers or footers; no tables, text boxes, columns, or images; real, selectable text in reading order. Tests read both formats back and check every line appears in order.
- **Page size.** `RESUME_PAGE_SIZE` = `A4` (default) or `LETTER`.
- **Safety.** User text is escaped before reportlab parses it. PDF output is deterministic.
- **Filename.** `Name-Job-Title-Company-vN.pdf`.

## Protecting resume content

- **No content in logs.** Logs record ids, versions, methods, counts, and byte sizes only, never resume text, contact details, or filenames. Tests assert this for the profile and tailored-resume endpoints.
- **No files at rest.** Exports are generated per request and never written to disk. Responses carry `Content-Disposition: attachment`, `Cache-Control: no-store, private`, and `X-Content-Type-Options: nosniff`.
- **What is stored.** Resume content lives only in the local PostgreSQL database. `.gitignore` and `.dockerignore` exclude `*.pdf`, `*.docx`, and upload folders.
- **Access.** There is still no authentication (a "Later" roadmap item), so protection from other users relies on the API binding to `127.0.0.1` and CORS allowing only the local web origin. Do not expose the API on a network until authentication exists.

## Limitations

- The claims check is heuristic. It does not catch spelled-out numbers ("two teams"), vaguer overstatement ("led" for "helped"), or skills outside the vocabulary and library. The user's review is the final check.
- AI rewording quality has not been measured on real resumes.
- One resume layout. PDF uses the standard Helvetica font, which covers Western European characters only; other scripts may not render.
- The summary is never generated or tailored; it is the profile summary unless the user edits it.
- Single user, no authentication, localhost only.
