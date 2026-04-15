# Voice-First Calorie Tracker (Vocalorie)

Voice-first nutrition logging app built with Next.js + FastAPI + Supabase.

Users speak what they ate, the backend transcribes and parses food entities, nutrition is resolved from USDA data, and results are written into a personal journal with daily macro tracking.

## Why This Project

Most calorie trackers have high user friction: search, tap, edit, repeat.

Vocalorie is designed to reduce that friction by making meal logging conversational and fast:

- Voice-to-log workflow in one flow.
- AI-assisted parsing for mixed natural language inputs.
- Identity-bound data model with RLS and API-side auth checks.
- Production-minded hardening with security docs and validation scripts.

## Quick Scan

- Product type: AI-assisted health/fitness tracker.
- Primary UX: speech-first food logging.
- Frontend: Next.js 16, React 19, TypeScript, Supabase Auth.
- Backend: FastAPI, Groq transcription/parsing, USDA nutrition lookup.
- Data layer: Supabase Postgres with owner-based access controls.
- Security posture: documented hardening + smoke/identity/RLS test scripts.

<!-- ## Demo

Add assets when ready. These placeholders are intentionally explicit so you can drop media in quickly.

- Product GIF placeholder: `docs/assets/demo-voice-to-log.gif`
- Landing screenshot placeholder: `docs/assets/screenshot-landing.png`
- Logger screenshot placeholder: `docs/assets/screenshot-logger.png`
- Journal screenshot placeholder: `docs/assets/screenshot-journal.png`
- Profile screenshot placeholder: `docs/assets/screenshot-profile.png`

Suggested short captions:

1. Speak meal in natural language.
2. Review parsed foods and nutrition.
3. Save entry and track daily progress. -->

## Core Features

- Voice ingestion endpoint for audio transcription and parsing.
- Food search endpoint with normalization and nutrition resolution.
- Journal CRUD flows with day summary and chart endpoints.
- Profile goal management for calories and macros.
- Protected route handling for logger, journal, and profile pages.
- API-level bearer-token verification on protected backend routes.
- Input validation, security headers, and rate limiting on abuse-prone APIs.

## Tech Stack

### Frontend

- Next.js 16 + React 19 + TypeScript
- Supabase Auth Helpers + Supabase JS
- Tailwind CSS 4 + ESLint

### Backend

- FastAPI + Uvicorn
- OpenAI-compatible Groq API client
- USDA FoodData Central integration
- Tavily client (optional workflows)

### Data/Auth

- Supabase Postgres
- Supabase Auth (JWT)
- Row Level Security (RLS) migration included

## Architecture Overview

```text
[Browser / Next.js App]
	-> Sign in with Supabase Auth
	-> Access protected pages (/logger, /journal, /profile)
	-> Call FastAPI with Bearer token

[FastAPI Backend]
	-> Verify bearer token against Supabase Auth
	-> Parse voice/text meal input
	-> Resolve nutrition data
	-> Persist user-bound entries in Supabase

[Supabase Postgres]
	-> Owner-scoped tables + RLS policies
	-> Profiles, daily logs, and personal foods
```

### Route protection note

Middleware checks protected paths and auth pages in [middleware.ts](middleware.ts). Current behavior avoids redirect loops by only redirecting on protected routes when a presented token is invalid.

## Repository Structure

```text
voice-first-calorie-tracker/
	app/                      # Next.js app routes
	components/               # Shared UI components
	lib/                      # Auth and client helpers
	docs/                     # Security and deployment guides
	scripts/                  # Security and validation scripts
	supabase/migrations/      # SQL migrations (RLS schema)
	main.py                   # FastAPI app + API routes
	journal.py                # Journal domain logic
	supabase_client.py        # Supabase clients
	middleware.ts             # Next.js route middleware
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### 1) Clone and enter project

```bash
git clone <your-repo-url>
cd voice-first-calorie-tracker
```

### 2) Create environment file

Use [.env.example](.env.example) as the base:

```bash
cp .env.example .env
```

Fill in real values in `.env`.

### 3) Start backend (Terminal 1)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend URL: `http://localhost:8000`

### 4) Start frontend (Terminal 2)

```bash
npm install
npm run dev
```

Frontend URL: `http://localhost:3000`

### 5) Validate baseline

```bash
npm run lint
npm run security:smoke
```

## Environment Variables

### Required for backend startup

| Variable | Purpose |
|---|---|
| `USDA_API_KEY` | FoodData Central nutrition lookup |
| `GROQ_API_KEY` | Transcription + parsing model access |
| `SUPABASE_URL` | Supabase project URL (`https://...`) |
| `SUPABASE_ANON_KEY` | Supabase anon key for auth verification |

### Optional / deployment-dependent

| Variable | Purpose |
|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | Backend admin persistence key |
| `TAVILY_API_KEY` | Optional Tavily workflows |
| `ALLOWED_ORIGINS` | Comma-separated CORS allowlist |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API base URL |
| `NEXT_PUBLIC_SUPABASE_URL` | Browser Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Browser Supabase anon key |

## NPM Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Start Next.js dev server |
| `npm run build` | Build frontend bundle |
| `npm start` | Run production Next.js server |
| `npm run lint` | Run ESLint |
| `npm run security:smoke` | Basic unauthorized/input checks |
| `npm run security:identity` | Identity-binding validation (needs `ACCESS_TOKEN`) |
| `npm run security:rls` | Cross-user RLS checks (needs 2 user tokens) |
| `npm run validate:no-secrets` | Scan staged content for leaked secrets |

## API Overview

Primary API routes (all in [main.py](main.py)):

| Method | Route | Description | Auth |
|---|---|---|---|
| `GET` | `/api/foods/search` | Parse and resolve nutrition for a query | Required |
| `POST` | `/api/voice` | Audio upload -> transcription -> parsed result | Required |
| `GET` | `/api/me` | Authenticated user identity snapshot | Required |
| `GET` | `/api/profile` | Read profile/goals | Required |
| `PUT` | `/api/profile` | Update profile/goals | Required |
| `GET` | `/api/journal/entries` | List entries | Required |
| `POST` | `/api/journal/entries` | Add entry | Required |
| `PUT` | `/api/journal/entries/{entry_id}` | Update entry | Required |
| `DELETE` | `/api/journal/entries/{entry_id}` | Delete entry | Required |
| `GET` | `/api/journal/day` | Daily totals/remaining targets | Required |
| `GET` | `/api/journal/summary` | Aggregated summary | Required |
| `GET` | `/api/journal/chart` | Chart-ready data | Required |
| `POST` | `/api/personal-foods` | Save personal food templates | Required |

### API constraints worth noting

- Query length max: 200 characters.
- Audio upload max: 10 MB.
- Accepted audio types: `audio/webm`, `audio/ogg`, `audio/wav`, `audio/mpeg`, `audio/mp4`.
- Rate limiting is applied by user and IP on key endpoints.

## Data Model and Access Control

RLS migration file: [supabase/migrations/20260411_initial_security_schema.sql](supabase/migrations/20260411_initial_security_schema.sql)

Tables intended for owner-scoped access:

- `users`
- `daily_logs`
- `personal_foods`

Locked-down tables (RLS enabled, no client policies by default):

- `food_searches`
- `global_foods`

## Security and Hardening

Security baseline and operations docs:

- [SECURITY_IMPLEMENTATION_COMPLETE.md](SECURITY_IMPLEMENTATION_COMPLETE.md)
- [docs/security_implementation_guide.md](docs/security_implementation_guide.md)
- [docs/apply_rls_migration.md](docs/apply_rls_migration.md)
- [docs/deployment_hardening_guide.md](docs/deployment_hardening_guide.md)
- [docs/key_rotation_guide.md](docs/key_rotation_guide.md)
- [docs/cookie_session_policy.md](docs/cookie_session_policy.md)
- [docs/security_abuse_test_matrix.md](docs/security_abuse_test_matrix.md)
- [docs/security_incident_playbook.md](docs/security_incident_playbook.md)

### Security verification commands

```bash
npm run validate:no-secrets
npm run security:smoke
ACCESS_TOKEN="<valid_jwt>" npm run security:identity
ACCESS_TOKEN_A="<user_a_jwt>" ACCESS_TOKEN_B="<user_b_jwt>" \
SUPABASE_URL="<your_url>" SUPABASE_ANON_KEY="<your_key>" npm run security:rls
```

## Deployment Notes

Deployment guidance lives in [docs/deployment_hardening_guide.md](docs/deployment_hardening_guide.md), with practical options for:

1. Vercel frontend + separately hosted FastAPI backend.
2. Docker/Kubernetes deployment.
3. Traditional VPS with reverse proxy.

Minimum deployment standards:

- HTTPS only.
- Strict `ALLOWED_ORIGINS` in production.
- RLS migration applied and verified.
- Key rotation and secret hygiene complete.

## Troubleshooting

- `No module named uvicorn`
	- Activate your venv and reinstall: `source .venv/bin/activate && pip install -r requirements.txt`
- Frontend cannot reach backend
	- Check `NEXT_PUBLIC_API_BASE_URL` and confirm backend is on `:8000`
- CORS errors
	- Add your frontend origin to `ALLOWED_ORIGINS`
- Supabase schema errors mentioning missing relation/table
	- Apply [supabase/migrations/20260411_initial_security_schema.sql](supabase/migrations/20260411_initial_security_schema.sql)
- Linux image/file path issues
	- Confirm filename case matches actual files in `public/`

## Known Limitations

- Backend and frontend are deployed as separate runtimes.
- Route middleware currently uses token-presence logic to avoid auth redirect loops.
- Monitoring/observability stack integration is documented but not enforced by code in this repository.

## Contribution

Contributions are welcome. Recommended flow:

1. Open an issue describing the change or bug.
2. Create a focused branch.
3. Keep changes scoped and include reproducible verification steps.
4. Run lint and security scripts before opening a PR.

## License

No license file is currently present in this repository. Add a project license before external distribution.
