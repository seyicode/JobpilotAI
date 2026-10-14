# Roadmap

## Milestone 0 — Developer setup
- [ ] Install Codex and authenticate
- [ ] Install Git, Docker Desktop/Engine, Node.js LTS, Python 3.12+
- [x] Create repository and run local development stack

## Milestone 1 — Profile and resume
- [x] Resume upload and parsing (PDF/DOCX/TXT, local text extraction, section splitting)
- [x] Verified experience and skills library (draft import from resumes, edit, verify)
- [x] Job preferences and filters (must-match hard filters with explanations)

## Milestone 2 — Matching
- [x] Paste job descriptions and add job URLs (no fetching; deduplicated)
- [x] Requirement extraction (local rules; optional OpenAI with spending controls)
- [x] Explainable scoring and hard filters

## Milestone 3 — Resume generation
- [x] Tailored content grounded in verified experience (deterministic; optional fact-checked AI rewording)
- [x] Human review/diff (side by side with sources; edit rules, warnings, approval)
- [x] DOCX/PDF export and per-job version history

## Milestone 4 — Discovery and tracking
- [ ] Supported job source adapters
- [ ] Scheduled searches and deduplication
- [ ] Dashboard, CSV export, and application tracking

## Later
- [ ] Browser extension
- [ ] Multi-user SaaS, billing, notifications
- [ ] AWS deployment and IaC
