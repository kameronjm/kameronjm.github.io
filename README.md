# Solved Sports Analytics Platform

Sports analytics and +EV betting platform — Phase 1 structural framework.

## Stack

- **Language**: Python 3.11+ (async, type-hinted)
- **API**: FastAPI + Uvicorn
- **Database**: SQLAlchemy 2.0 (async) + Alembic migrations
- **Config**: Pydantic Settings
- **Lint/Format**: Ruff
- **Tests**: Pytest

## Project Structure

```
config/          — Pydantic settings, league constants
src/api/         — FastAPI application and v1 routes
src/core/        — Abstract interfaces and EV math engine
src/database/    — SQLAlchemy models, async session management
src/ingestion/   — Data pipeline stubs (stats scrapers, odds feeds)
src/models/      — Predictive model stubs (game sim, player props)
tests/           — Unit and integration tests
alembic/         — Database migration scripts
```

## Quick Start

```bash
poetry install
cp .env.example .env  # configure DATABASE_URL
poetry run alembic upgrade head
poetry run uvicorn src.api.main:app --reload
```

## Running Tests

```bash
poetry run pytest
```
