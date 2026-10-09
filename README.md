# Rokkha

Public-safety dispatch and Online GD backend: a citizen raises an SOS, the nearest available
officer is assigned automatically, and citizens can file a General Diary that moves through a
review workflow.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · Alembic · PostgreSQL 16 · pytest

> Work in progress. The full README (architecture, decisions, demo) comes at the end of the build.
> Design docs: [docs/](docs/).

## Quick start (Windows PowerShell, macOS, Linux)

Requires Docker and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
docker compose up -d db         # Postgres on localhost:5433 (+ rokkha_test database)
uv sync                         # create .venv and install dependencies
uv run alembic upgrade head     # create tables
uv run python -m scripts.create_super_admin --name "Control Room" --phone +8801700000001
uv run uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs · Health: http://localhost:8000/api/v1/health

In Swagger, call `POST /auth/login`, copy `access_token`, then click **Authorize**.

## Tests and lint

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Tests run against the `rokkha_test` database. The schema is rebuilt from the Alembic
migrations on every run, and each test runs inside a transaction that is rolled back.
