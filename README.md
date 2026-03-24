# Pantry Server

FastAPI backend for pantry management, household membership, shopping and recipe helpers, plus AI/embedding workflows backed by Supabase and optional Gemini providers.

## Tech Stack

- Python 3.12+
- FastAPI + Uvicorn
- Supabase Python client
- LangChain / LangGraph
- `uv` for dependency and runtime management
- Pytest + Ruff for testing and linting

## Project Layout

```text
src/pantry_server/
  main.py                  # FastAPI app bootstrap, middleware, health routes
  api/                     # top-level API router composition (/api/*)
  core/                    # settings, errors, lifespan, validation helpers
  shared/                  # shared contracts, auth dependencies, Supabase wiring
  contexts/
    pantry/                # pantry domain, app service, presentation routes
    households/            # household routes and service
    recipes/               # recipe routes
    shopping/              # shopping-list routes
    ai/                    # AI routes and infrastructure providers/workflows
supabase/migrations/       # SQL migrations for RLS, matching function, cron worker
tests/                     # unit tests
```

## Prerequisites

- Python `>=3.12`
- [`uv`](https://docs.astral.sh/uv/)
- Supabase project (for authenticated and data-backed routes)

## Setup

1) Install dependencies:

```bash
uv sync
```

2) Copy environment template and fill values:

```bash
cp .env.example .env
```

3) Run the API:

```bash
uv run uvicorn pantry_server.main:app --reload
```

The app starts with:
- API base path: `/api`
- Health check: `/health`
- Root: `/`
- OpenAPI docs: `/docs`

## Environment Variables

Configured via `src/pantry_server/core/config.py`.

### Core app

- `APP_NAME` (default: `pantry-backend`)
- `APP_ENV` (default: `development`)
- `APP_DEBUG` (default: `true`)
- `APP_HOST` (default: `0.0.0.0`)
- `APP_PORT` (default: `8000`)
- `CORS_ALLOW_ORIGINS` (default: `["*"]`; set explicit frontend origins in production)

### Supabase

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY` (optional)
- `SUPABASE_ANON_KEY` (optional)
- `SUPABASE_SERVICE_ROLE_KEY` (optional; preferred when present)
- `SUPABASE_JWT_SECRET` (optional)

### Gemini / AI

- `GOOGLE_GENERATIVE_AI_API_KEY`
- `GEMINI_MODEL` (default: `gemini-2.5-flash`)
- `GEMINI_TEMPERATURE` (default: `0.0`)
- `GEMINI_MAX_TOKENS` (default: `1000`)
- `GEMINI_MAX_RETRIES` (default: `2`)
- `GEMINI_EMBEDDINGS_MODEL` (default: `gemini-embedding-001`)
- `GEMINI_EMBEDDINGS_OUTPUT_DIMENSIONALITY` (default: `768`)

### Middleware / internal worker

- `RATE_LIMIT_ENABLED` (default: `true`)
- `RATE_LIMIT_PER_MINUTE` (default: `60`)
- `EMBEDDING_WORKER_SECRET` (required for `/api/pantry-items/internal/embedding-jobs/run`)

Rate limiting is enforced with `slowapi` as an application-wide limit.

## Authentication

Routes using current-user context expect:

- `Authorization: Bearer <supabase_access_token>`

User and household are resolved via Supabase auth and `household_members`.

## API Routes

All routes are under `/api`.

### Pantry (`/pantry-items`)

- `POST /add-single-item`
- `POST /add-bulk-items`
- `GET /get-my-items`
- `GET /get-household-pantry`
- `PATCH /update-my-item/{item_id}`
- `DELETE /delete-my-item/{item_id}`
- `POST /internal/embedding-jobs/run` (requires `x-worker-secret`)

### Recipes (`/recipes`)

- `GET /`
- `POST /generate-recipe`

### Shopping (`/shopping-lists`)

- `GET /`
- `POST /generate-shopping-list`

### Households (`/households`)

- `POST /create`
- `POST /join`
- `POST /leave`
- `POST /convert-to-joinable`

### AI (`/ai`)

- `POST /embeddings`
- `POST /recipes/generate`

## Database Migrations

Supabase SQL migrations are in `supabase/migrations/`, including:

- RLS enablement for pantry embedding jobs
- `match_pantry_items` function migration
- embedding worker cron migration

## Testing and Linting

Run tests:

```bash
uv run pytest
```

Run lint:

```bash
uv run ruff check .
```
