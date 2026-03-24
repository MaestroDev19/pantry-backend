## Pantry Server (`pantry-backend`)

FastAPI + Supabase backend for the Pantry application, providing authenticated, household‑scoped pantry item management with AI‑powered features (embeddings and Gemini‑based workflows).

### Table of Contents

- [Overview](#overview)
- [Current Status](#current-status)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Server](#running-the-server)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Architecture](#architecture)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [Development Guidelines](#development-guidelines)

### Overview

Pantry Server is a modern, scalable backend API built with FastAPI that enables users to:

- **Manage Pantry Items**: Track food inventory with categories, quantities, units, and expiry dates
- **Recipe Management**: Create, search, and generate recipes using AI
- **Shopping Lists**: Generate and manage shopping lists based on pantry needs
- **Household Collaboration**: Share pantries and shopping lists with household members
- **User Preferences**: Configure alerts and reminders for pantry management

### Current Status

#### ✅ Implemented

**Core Infrastructure**

- **FastAPI application** with lifespan management (`src/pantry_backend/app.py`, `index.py`)
- **Configuration management** with Pydantic Settings (`src/pantry_backend/core/settings.py`)
- **Structured logging system** (`src/pantry_backend/core/logging.py`)
- **Global exception handling** (`src/pantry_backend/core/errors.py`, `src/pantry_backend/core/exceptions.py`)
- **Health check endpoint** (`GET /health`)

**Authentication & Security**

- **Supabase authentication integration** (`src/pantry_backend/integrations/supabase_client.py`, `src/pantry_backend/services/auth_service.py`)
- **Bearer token validation**
- **User authentication and household dependencies** (`get_current_user_id`, `get_current_household_id` in `src/pantry_backend/services/__init__.py`)
- **Row Level Security (RLS)** support via Supabase clients

**Pantry API**

- **Household‑scoped pantry item CRUD** via `/pantry` routes (`src/pantry_backend/api/v1/routers/pantry.py`)
- **Single and bulk pantry item upsert** with validation
- **User‑scoped and household‑scoped pantry item listing**
- **Embedding generation and storage** for pantry items (via `src/pantry_backend/embedding_worker.py` and Supabase)

**Household API**

- **Create household** (`POST /households/create`) — create a new household and make the current user owner and member
- **Join household by invite code** (`POST /households/join`) — migrates user's pantry items and switches membership
- **Leave household** (`POST /households/leave`) — creates a new personal household and moves items
- **Convert personal to joinable** (`POST /households/convert-to-joinable`) — make a personal household shareable

**Data Models**

- **Pantry Models**: Pantry item schema with categories, units, expiry tracking (`src/pantry_backend/models/pantry.py`)
- **Recipe Models**: Recipe structure with ingredients, instructions, dietary tags (`src/pantry_backend/models/recipes.py`)
- **Shopping List Models**: Shopping list items with purchase tracking (`src/pantry_backend/models/shopping_list.py`)
- **Household Models**: Household management and member models (`src/pantry_backend/models/household.py`)
- **User Preferences Models**: Preferences for alerts and reminders (`src/pantry_backend/models/preferences.py`)

**Services**

- **Supabase client service** (anon and service role) in `src/pantry_backend/integrations/supabase_client.py`
- **Gemini AI client** in `src/pantry_backend/integrations/gemini_client.py`
- **Embeddings client** for vector operations in `src/pantry_backend/utils/embedding.py`
- **Pantry and household services** (`src/pantry_backend/services/pantry_service.py`, `src/pantry_backend/services/household_service.py`)
- **Auth service** for resolving the current user and household (`src/pantry_backend/services/auth_service.py`)

**Utilities**

- **Authentication utilities** (via services + Supabase integration)
- **Input validators and normalizers** (`src/pantry_backend/utils/validators.py`)
- **Response formatters** (`src/pantry_backend/utils/formatters.py`)
- **Application constants** (`src/pantry_backend/utils/constants.py`)
- **Date/time formatting** (`src/pantry_backend/utils/date_time_styling.py`)

**AI & Embeddings**

- **Background embedding worker** for pantry items (`src/pantry_backend/embedding_worker.py`)
- **Retrieval cache and tools** in `src/pantry_backend/ai/`:
  - `retriever_cache.py` — in‑memory retrieval cache keyed by household + query
  - `tools.py` — LangChain tools for pantry RAG flows

#### 🚧 In Progress / Planned

- **Additional Domain API Routes**: Recipes, shopping lists, and user preferences
- **Recipe Generation**: AI‑powered recipe generation from pantry items
- **Shopping List Generation**: Automatic list creation based on pantry state
- **Additional Background Workers**: For batch processing and other AI tasks

### Tech Stack

**Core Framework**

- **FastAPI** — web framework for building APIs
- **Uvicorn** — ASGI server
- **Pydantic** & **pydantic‑settings** — data validation and configuration

**Database & Authentication**

- **Supabase** — PostgreSQL + auth
- **python‑jose** — JWT token handling
- **passlib** — password hashing utilities

**AI & Machine Learning**

- **LangChain** and **langchain‑community**
- **LangGraph**
- **langchain‑google‑genai**
- **Google Generative AI** (Gemini) — text and embeddings

**Utilities**

- **httpx** — async HTTP client
- **slowapi** — rate limiting middleware
- **psutil** — system monitoring
- **python‑multipart** — form data handling
- **python‑dateutil** — date parsing utilities

### Prerequisites

- **Python 3.12+**
- **Supabase Project** — for database and authentication
- **Google Cloud Account** — for Gemini API access
- **`.env` file** — environment variables (see [Environment Variables](#environment-variables))
- **uv** — Python package/dependency manager used by this repo

### Setup

From your shell:

```bash
git clone <repository-url>
cd pantry-backend
```

Create and activate a virtual environment (optional when using `uv`, but recommended):

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Install dependencies via `uv` (preferred):

```bash
uv sync
```

Alternatively, using `pip`:

```bash
pip install .
```

Create a `.env` file in the project root:

```bash
cp .env.example .env  # if available
```

Configure the values as described in [Environment Variables](#environment-variables).

### Running the Server

Development mode with auto‑reload:

```bash
uv run uvicorn index:app --reload
```

Production‑style run:

```bash
uv run uvicorn index:app --host 0.0.0.0 --port 8000
```

Access points:

- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive API Docs (Swagger)**: `http://127.0.0.1:8000/docs`
- **Alternative API Docs (ReDoc)**: `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON**: `http://127.0.0.1:8000/openapi.json`

### Project Structure

High‑level layout:

```text
pantry-backend/
├── index.py                          # Uvicorn entrypoint (index:app)
├── pyproject.toml                    # Project metadata and dependencies
├── .env                              # Environment variables (not committed)
├── supabase/                         # Supabase migrations (if present)
│
├── src/
│   └── pantry_backend/
│       ├── app.py                    # FastAPI app factory, lifespan, middleware
│       │
│       ├── api/
│       │   └── v1/
│       │       ├── router.py         # Top-level API router
│       │       └── routers/
│       │           ├── health.py     # Health check endpoint
│       │           ├── pantry.py     # Pantry item routes
│       │           ├── households.py # Household routes
│       │           └── embedding_worker.py  # Worker control/API hooks (if exposed)
│       │
│       ├── core/                     # Core configuration and infrastructure
│       │   ├── settings.py           # AppSettings, env configuration
│       │   ├── exceptions.py         # Custom application errors
│       │   ├── errors.py             # FastAPI exception handlers
│       │   ├── logging.py            # Logging configuration + middleware
│       │   ├── cache.py              # Cache helpers
│       │   └── rate_limit.py         # SlowAPI rate limiting setup
│       │
│       ├── models/                   # Pydantic domain models
│       │   ├── pantry.py             # Pantry item models and enums
│       │   ├── recipes.py            # Recipe models
│       │   ├── shopping_list.py      # Shopping list models
│       │   ├── household.py          # Household and member models
│       │   └── preferences.py        # User preferences models
│       │
│       ├── services/                 # Business logic and external integrations
│       │   ├── pantry_service.py     # Pantry domain service
│       │   ├── household_service.py  # Household lifecycle operations
│       │   └── auth_service.py       # Auth + household resolution helpers
│       │
│       ├── integrations/             # External clients
│       │   ├── supabase_client.py    # Supabase client (anon/service role)
│       │   └── gemini_client.py      # Gemini AI client
│       │
│       ├── utils/                    # Utility functions and helpers
│       │   ├── constants.py          # Application constants
│       │   ├── validators.py         # Input validation helpers
│       │   ├── formatters.py         # Response formatting utilities
│       │   ├── embedding.py          # Embeddings client
│       │   └── date_time_styling.py  # Date/datetime formatting
│       │
│       ├── ai/                       # AI and vector/RAG integration
│       │   ├── retriever_cache.py    # In-memory retriever cache
│       │   └── tools.py              # LangChain tools for pantry flows
│       │
│       └── embedding_worker.py       # CLI/loop-based background embedding worker
│
└── tests/
    └── test_health.py                # Basic health endpoint test
```

### Testing

Install dev dependencies (via `uv`):

```bash
uv sync --group dev
```

Run tests:

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=pantry_backend
```

### Architecture

**Design Principles**

- **Functional‑leaning design**: Prefer pure functions over classes where reasonable
- **Dependency Injection**: Use FastAPI's dependency system for shared resources
- **Separation of Concerns**: Clear boundaries between routers, services, and utilities
- **Type Safety**: Comprehensive type hints throughout the codebase
- **Error Handling**: Guard clauses and consistent error responses

**Key Patterns**

- **Singleton services**: `get_settings`, Supabase clients, and embeddings client use caching to behave like singletons.
- **Model hierarchy**: Pydantic models distinguish creation/update payloads and response types.
- **Service layer**: Routers are thin; business rules live in `services/`.
- **Background worker**: Embedding generation is handled out of band by `embedding_worker.py`, driven by Supabase queues.

### Environment Variables

Core Supabase configuration:

| Variable                    | Description                                      |
| --------------------------- | ----------------------------------------------- |
| `SUPABASE_URL`              | Supabase project URL                            |
| `SUPABASE_ANON_KEY`         | Supabase anonymous/public key                   |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (for admin operations)|

Application configuration:

| Variable        | Description                                      | Default          |
| --------------- | ------------------------------------------------ | ---------------- |
| `APP_ENV`       | Runtime environment (`development`, `production`, etc.) | `development` |
| `APP_NAME`      | Application name                                 | `pantry-server`  |
| `APP_VERSION`   | Application version                              | `0.1.0`          |
| `PORT`          | Server port                                      | `8000`           |
| `HOST`          | Server host                                      | `0.0.0.0`        |
| `LOG_LEVEL`     | Base logging level                               | `INFO`           |
| `RATE_LIMIT_ENABLED` | Enable SlowAPI‑based rate limiting         | `True`           |

CORS configuration:

| Variable        | Description                                     |
| --------------- | ----------------------------------------------- |
| `CORS_ALLOW_ORIGINS` | Comma‑separated list of allowed origins   |

Gemini AI configuration:

| Variable                                  | Description                       | Default                |
| ----------------------------------------- | --------------------------------- | ---------------------- |
| `GOOGLE_GENERATIVE_AI_API_KEY`            | Google AI API key                 | —                      |
| `GEMINI_MODEL`                            | Gemini chat model name            | `gemini-2.5-flash`     |
| `GEMINI_TEMPERATURE`                      | Temperature (0.0–2.0)             | `0.0`                  |
| `GEMINI_MAX_TOKENS`                       | Max tokens per response           | `1000`                 |
| `GEMINI_MAX_RETRIES`                      | Max retry attempts                | `2`                    |
| `GEMINI_EMBEDDINGS_MODEL`                 | Embeddings model name             | `gemini-embedding-001` |
| `GEMINI_EMBEDDINGS_OUTPUT_DIMENSIONALITY` | Embedding vector size             | `768`                  |

Background workers:

| Variable                    | Description                           | Default |
| --------------------------- | ------------------------------------- | ------- |
| `ENABLE_BACKGROUND_WORKERS` | Enable embedding worker loop          | `True`  |
| `EMBEDDING_BATCH_SIZE`      | Batch size for embeddings             | `50`    |
| `EMBEDDING_WORKER_INTERVAL` | Worker check interval (seconds)       | `5`     |
| `EMBEDDING_WORKER_MAX_ATTEMPTS` | Max attempts before dead-lettering | `3` |
| `EMBEDDING_WORKER_MAX_SECONDS` | Time limit per worker invocation (seconds) | `20` |
| `CACHE_MAX_ENTRIES`         | Max in-memory API cache entries       | `200`   |
| `RETRIEVER_CACHE_MAX_ENTRIES` | Max in-memory retriever cache entries | `200` |

Internal worker scheduler:

- Endpoint: `POST /api/run-embedding-worker`
- Header: `x-internal-secret: <EMBEDDING_WORKER_SECRET>`
- Suggested cadence: every 15 minutes

### Operational Runbook (Embedding Queue)

- Queue depth alerts:
  - Warn when main queue depth exceeds `100`
  - Critical when combined main + dlq depth exceeds `500`
- Dead-letter drain:
  - Inspect `pantry_embedding_dead` messages
  - Fix root cause (provider error, payload issues, missing pantry row)
  - Requeue to `pantry_embedding_queue` using `pgmq_public.send_batch`
- Scheduler health checks:
  - Verify scheduler fires every 15 minutes
  - Alert if no successful invocation in 30 minutes
  - Alert on sustained `dead` count increase across 3 runs

### API Documentation

Current endpoints (non‑exhaustive):

**Health**

- `GET /health` — returns application health status

**Households** (authenticated):

- `POST /households/create` — create a new household, current user becomes owner and member
- `POST /households/join` — join a household by invite code, migrate pantry items
- `POST /households/leave` — leave current household, create personal household, move items
- `POST /households/convert-to-joinable` — convert personal household to joinable with invite code

**Pantry**

- `POST /pantry/add-item` — add a single pantry item
- `POST /pantry/bulk-add` — bulk add pantry items
- `GET /pantry/household-items` — list all pantry items in the current household
- `GET /pantry/my-items` — list pantry items owned by the current user in the household
- `PUT /pantry/update-item` — update a pantry item
- `DELETE /pantry/delete-item` — delete a pantry item

Additional recipe, shopping list, and preferences endpoints are defined at the model/service layer and will be surfaced via dedicated routers as they are implemented.

### Development Guidelines

- **Type hints**: All functions should have type hints.
- **Docstrings**: Use Google‑style docstrings for public functions.
- **Naming**: Use descriptive names with auxiliary verbs (`is_active`, `has_permission`).
- **Early returns**: Use guard clauses to handle edge cases at the top of functions.
- **Separation of concerns**: Keep routers thin, push logic into services.

### Recent Notes

- A Supabase‑backed embedding worker (`src/pantry_backend/embedding_worker.py`) processes queue‑based jobs to keep pantry item embeddings fresh.
- When setting up a new environment, ensure all Supabase migrations in `supabase/migrations/` (if present) are applied before running the API.