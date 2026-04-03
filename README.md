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

Rate limiting is enforced with `slowapi` as an application-wide per-route budget (see [`src/pantry_server/middleware/rate_limit.py`](src/pantry_server/middleware/rate_limit.py)).

#### Join endpoint (`POST /api/households/join`)

Additional, stricter limits apply only to this route (in-process counters; see [ADR `docs/adr/0001-household-join-rate-limits.md`](docs/adr/0001-household-join-rate-limits.md)):

| Variable | Default | Purpose |
|----------|---------|---------|
| `HOUSEHOLDS_JOIN_RATE_LIMIT_ENABLED` | `true` | Master switch for join-specific limits |
| `HOUSEHOLDS_JOIN_RATE_LIMIT_IP_PER_MINUTE` | `30` | Per client IP (runs before authentication) |
| `HOUSEHOLDS_JOIN_RATE_LIMIT_USER_PER_MINUTE` | `10` | Per authenticated user (after Bearer / dev header resolution) |
| `TRUST_X_FORWARDED_FOR` | `false` | When `true`, client IP for the IP limit is the first address in `X-Forwarded-For` (use only behind a trusted reverse proxy) |

Set either per-minute cap to `0` to disable that dimension only. Throttle events are logged on the `pantry_server.rate_limit` logger as `event=rate_limit_throttled` with `scope=household_join` and `dimension=ip` or `dimension=user`.

Together with `RATE_LIMIT_*`, a single request can be limited by the global slowapi budget and by both join dimensions; the stricter effective limit applies first.

**Edge alternatives (free / low-cost):** Cloudflare (Workers + KV, WAF/bot features depending on plan), AWS API Gateway usage plans, Kong OSS, or NGINX `limit_req` in front of the app. App-level limits remain useful for consistent JSON 429 responses and user-aware caps without tying you to one vendor.

## Authentication

Routes using current-user context expect:

- `Authorization: Bearer <supabase_access_token>` (validated with `supabase.auth.get_user` using the service-role client).

User and household are resolved via Supabase auth and `household_members`.

**Local development only:** set `AUTH_ALLOW_X_USER_ID=true` to accept a valid UUID in the `X-User-ID` header as the authenticated user without a Bearer token. Do not enable this in production.

**Rate limiting** (`RATE_LIMIT_ENABLED`): when present, `x-user-id` is used as part of the global rate-limit key; otherwise the client IP is used (see [`src/pantry_server/middleware/rate_limit.py`](src/pantry_server/middleware/rate_limit.py)). Join uses separate IP and user keys as described above.

**Unauthenticated routes:** `GET /api/recipes/`, `GET /api/shopping-lists/`, and `POST /api/ai/*` (embeddings and mock recipe generation) do not require Bearer auth today.

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
