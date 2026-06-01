# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered sales analytics backend. Users upload ZIP files containing WhatsApp exports (chats + voice messages). The API extracts, transcribes audio via OpenAI Whisper, parses chat files, runs LLM analysis (OpenAI or DeepSeek), and returns structured sales performance reports.

## Commands

**Setup:**
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env  # then fill in real values
```

**Run (development):**
```powershell
uvicorn main:app --reload
```

**Run (production):**
```powershell
python run.py
```

**Database migrations:**
```powershell
# Migrations run automatically on startup via alembic upgrade head.
# To create a new migration after changing models:
alembic revision --autogenerate -m "description"
alembic upgrade head
```

**Tests:**
```powershell
python -m pytest tests/
# Single test file:
python -m pytest tests/test_payment_config.py
```

**Local Stripe webhook forwarding:**
```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
stripe trigger checkout.session.completed
```

## Architecture

The codebase uses a strict four-layer architecture:

```
routes/      → HTTP handlers (thin — delegate immediately to services)
services/    → Business logic (file processing, LLM calls, Stripe ops)
repository/  → All database access (SQLAlchemy queries)
models/      → SQLAlchemy ORM definitions
```

Supporting layers:

- `core/` — cross-cutting infrastructure (see below)
- `schemas/` — Pydantic request/response models (never share with ORM models)
- `prompts/` — LLM prompt templates, kept separate from service logic
- `alembic/` — Migration scripts; `alembic/versions/` contains numbered migration files

**ZIP upload flow:**
1. `routes/sales_upload.py` — receives file, saves to `storage/temp_zips/`
2. Background task (`services/tasks.py`) runs extraction
3. `services/zip/` — extracts ZIP contents
4. `services/chat/chat_file_handler.py` — parses WhatsApp export text
5. `services/audio/openai_transcriber.py` — sends OGG/OPUS files to Whisper API
6. `services/reports/` — assembles transcript, calls LLM client, returns structured analysis
7. `core/status_tracker.py` — tracks progress; polled by `routes/status.py`

**LLM clients** (`services/reports/`) implement `ILLMClient` — both OpenAI and DeepSeek variants exist. Switch via config, not code changes.

**Authentication:** JWT access + refresh tokens. `core/dependencies.py` provides `get_current_user` for protected routes.

**Subscription tiers:** `free`, `basic`, `premium`, `enterprise` stored on the `User` model as `analyses_remaining` credits. Stripe webhooks (`routes/stripe_webhook.py`) top up credits on payment events.

## Core Layer (`core/`)

### `core/config.py` — Settings

Single `Settings` instance (`settings`) loaded from `.env` via pydantic-settings. All other modules import from here — never read `os.environ` directly.

Key helpers exported alongside `settings`:
- `stripe_price_id_by_plan(plan_name)` — maps `"basic"/"premium"/"enterprise"` → Stripe price ID; returns `None` for placeholders
- `analysis_credits_by_plan(plan_name)` → int credits for that plan
- `validate_stripe_runtime_config()` — raises `ValueError` if Stripe env vars are placeholders in `staging`/`production` (`APP_ENV` controls this; development skips validation)

Notable config fields beyond `.env.example`:
- `REFRESH_TOKEN_SECRET_KEY` — separate secret for refresh tokens (defaults to `"segredo"` — override in production)
- `MAX_CONCURRENT_TRANSCRIPTIONS=2`, `TRANSCRIPTION_RETRY_ATTEMPTS=5` — controls Whisper parallelism and retry back-off

### `core/auth.py` — JWT Utilities

Stateless helpers; no database calls here:
- `create_access_token(data)` / `verify_token(token) -> email | None` — uses `SECRET_KEY` + `ALGORITHM`
- `create_refresh_token(data)` — uses `REFRESH_TOKEN_SECRET_KEY`; adds `"type": "refresh"` and a `jti` (UUID4) claim to distinguish refresh tokens from access tokens
- `get_password_hash` / `verify_password` — bcrypt via passlib

### `core/dependencies.py` — FastAPI DI

Inject these with `Depends(...)` in route handlers:

| Dependency | Returns | Notes |
|---|---|---|
| `get_current_user` | `User` | Validates Bearer token, looks up user in DB |
| `get_current_active_user` | `User` | Above + checks `is_active` |
| `get_current_paid_user` | `User` | Above + checks `analyses_remaining > 0` |
| `enforce_analysis_access(user)` | `User` | Call before starting an analysis; checks credits, subscription status, and trial — raises `HTTP 402` with specific detail messages |
| `consume_analysis_credit(db, user_id)` | `User` | Call after a successful analysis to decrement `analyses_remaining` |
| `get_llm_client` | `ILLMClient` | Yields OpenAI client by default; closes on teardown |
| `get_http_client` | `AsyncHTTPClient` | Yields shared aiohttp session; closes on teardown |
| `get_transcriber` | `OpenAITranscriber` | Wraps `AsyncHTTPClient` |

`enforce_analysis_access` and `consume_analysis_credit` are intentionally separate — access is checked before the expensive work, credits are consumed only on success.

### `core/status_tracker.py` — In-Process Status Store

In-memory dict (`_status_store`) keyed by `zip_id`. Not persistent across restarts; not shared across multiple processes/workers.

- `set_status(zip_id, status, progress)` — appends to history and updates `current`
- `get_status(zip_id)` — returns `{"current": {...}, "history": [...]}` or `{"status": "not_found"}`

Uses an asyncio lock with a 1-second timeout to prevent contention. Background tasks write here; `routes/status.py` reads and streams to the frontend.

### `core/abstractions/`

- `ILLMClient` — async ABC with `send_message`, `stream_message`, `stream_messages`, and `close`. All LLM service implementations must satisfy this contract.
- `IFileProcessor` / `IFileValidator` — protocol for upload handlers; `process_upload(file, user) -> dict`

### `core/http/async_http_client.py`

Thin `aiohttp` wrapper with tenacity retry (3 attempts, exponential back-off 2–10s). Used by `OpenAITranscriber` for Whisper API calls. Handles `multipart/form-data` file uploads automatically when `files=` is passed.

### `core/storage/`

- `FileValidator` — static methods: `validate_zip_extension`, `sanitize_filename` (strips path-traversal characters), `validate_file_size` (default 500 MB cap)
- `LocalStorageProvider` — saves uploads to `storage/temp_zips/`; implements abstract `StorageProvider` so the storage backend can be swapped

## Rules & Conventions

**Never mix layer responsibilities.**
Each layer has one home — don't cross boundaries:
- Database queries belong in `repository/` only. Routes and services never call `db.query(...)` directly (except `dependencies.py` which is infrastructure, not business logic).
- HTTP handlers belong in `routes/` only. Services never import from `routes/`.
- Business logic belongs in `services/` only. Repository functions are pure data access with no business decisions.
- If new code doesn't fit cleanly into an existing layer, create a new module inside the correct layer rather than placing it somewhere convenient.

**Always work with objects, not raw dicts or primitives.**
- Route inputs and outputs use Pydantic schemas from `schemas/`.
- Service functions accept and return typed objects (dataclasses, Pydantic models, or ORM instances).
- Never pass raw `dict` or loosely-typed data between layers — define a schema or model first.

**Write AI-friendly code.**
Code in this repo is read and modified by LLMs as often as by humans. Keep it unambiguous:
- Use explicit, descriptive names — no abbreviations, no single-letter variables outside tight loops.
- Keep functions short and single-purpose so an LLM can understand and modify one function without needing full file context.
- Avoid implicit side effects; a function that does what its name says and nothing else is always preferred.
- Type-annotate every function signature (parameters and return type).

## Key Environment Variables

See `.env.example`. Critical ones:
- `DATABASE_URL` — defaults to `sqlite:///./sales.db`; use `postgresql://` in production
- `OPENAI_API_KEY` — required for transcription and analysis
- `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` — required for payment routes
- `SECRET_KEY` — JWT signing secret; use a strong random value in production
- `ALLOWED_ORIGINS` — comma-separated CORS origins

## API Prefix

All routes are versioned under `/api/v1`. Swagger UI at `/docs`.

## Windows Notes

`main.py` reconfigures stdout/stderr to UTF-8 on startup to handle WhatsApp message content. Don't remove the `setup_unicode_support()` call.
