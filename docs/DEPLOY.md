# Deploying Rokkha

The app is one Docker image. On start it runs `alembic upgrade head`, then Uvicorn on `$PORT`.
The same image runs the ARQ worker with `arq app.workers.main.WorkerSettings`.

## What it needs

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | Postgres 14+. `postgres://` URLs from hosts are converted to `postgresql+asyncpg://` automatically |
| `REDIS_URL` | yes | pub/sub for WebSockets, the job queue, rate limits |
| `JWT_SECRET` | yes | any long random string; startup fails if it's the dev default outside `APP_ENV=local` |
| `APP_ENV` | yes | e.g. `production` |
| `GROQ_API_KEY` | no | free key from console.groq.com; enables `POST /gds/ai-draft` (without any AI key it returns 503 `AI_UNAVAILABLE`) |
| `GROQ_MODEL` | no | defaults to `openai/gpt-oss-120b` (free tier) |
| `SEED_DEMO_DATA` | no | `true` loads demo data on startup if missing and marks seeded on-duty officers as seen (handy on free hosting, which has no shell) |
| `AI_PROVIDER` | no | `auto` (default: Groq if its key is set, else Anthropic), `groq` or `anthropic` |
| `ANTHROPIC_API_KEY`, `AI_MODEL` | no | alternative provider (paid); model defaults to `claude-opus-5-5` |
| `SOS_ACCEPT_TIMEOUT_SECONDS` | no | escalation delay, default 120 |
| `RUN_WORKER_IN_PROCESS` | no | `true` runs the escalation worker inside the API (single-service hosting) |

## Free: Render + Neon (no card)

| Piece | Where | Note |
|---|---|---|
| API + escalation worker | Render free web service | one container; `RUN_WORKER_IN_PROCESS=true` runs the worker inside it |
| Redis | Render free Key Value | internal-only; not metered per command |
| Postgres | Neon free | doesn't expire (Render's free Postgres is deleted after 30 days) |

1. **Neon:** sign in at https://neon.com, create a project, copy the connection string
   (`postgresql://...neon.tech/neondb?sslmode=require&channel_binding=require` is fine; the app
   converts it for asyncpg).
2. **Render:** sign in at https://render.com with GitHub → **New → Blueprint** → pick `rokkha`.
   It reads [`render.yaml`](../render.yaml) and creates `rokkha-api` + `rokkha-redis`.
   When asked, paste the Neon string as `DATABASE_URL` (and optionally `ANTHROPIC_API_KEY`).
3. First deploy builds the image (a few minutes). Migrations run on start.
4. Seed: set `SEED_DEMO_DATA=true` on the service (it seeds on the next start), or from your
   machine against Neon:
   `DATABASE_URL="<neon string>" uv run python -m scripts.seed`
   (PowerShell: `$env:DATABASE_URL="<neon string>"; uv run python -m scripts.seed`)
5. Swagger: `https://rokkha-api.onrender.com/docs` (or the name Render assigned).

**Sleep:** free web services sleep after 15 minutes without traffic and take about a minute
to wake. The `Keep alive` GitHub Actions workflow (`.github/workflows/keep-alive.yml`) pings
`/api/v1/health` every 10 minutes to prevent that; point it elsewhere with a repository
variable `KEEP_ALIVE_URL`, or disable the workflow in the Actions tab. GitHub may delay
scheduled runs by a few minutes, and pauses them after 60 days without repo activity. Before a demo or interview, open `/api/v1/health` a minute early, then run
`python -m scripts.seed --touch` (against Neon) so seeded on-duty officers count as reachable.

## Railway (paid after the trial)

Railway builds the Dockerfile from GitHub and runs the API, the worker, Postgres and Redis in
one project. Railway sets `PORT`; the image already listens on it.

1. Sign in at https://railway.com with GitHub.
2. **New Project → Deploy from GitHub repo → `rokkha`.** This becomes the API service.
3. In the project canvas: **+ New → Database → PostgreSQL**, then **+ New → Database → Redis**.
4. API service → **Variables** (use the reference picker for the first two):

   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   APP_ENV=production
   JWT_SECRET=<output of: python -c "import secrets; print(secrets.token_urlsafe(48))">
   ANTHROPIC_API_KEY=<optional>
   ```

5. API service → **Settings**: Networking → **Generate Domain**; Deploy → Healthcheck Path
   `/api/v1/health`.
6. Worker: **+ New → GitHub Repo → `rokkha`** again → Settings → **Custom Start Command**
   `arq app.workers.main.WorkerSettings` (no domain, no healthcheck). Give it the same
   `DATABASE_URL`, `REDIS_URL`, `APP_ENV`, and `JWT_SECRET=${{<api service name>.JWT_SECRET}}`.
7. Seed from your machine against the database's public URL (Postgres service → Variables →
   `DATABASE_PUBLIC_URL`):

   ```bash
   DATABASE_URL="<DATABASE_PUBLIC_URL>" uv run python -m scripts.seed
   ```

   PowerShell: `$env:DATABASE_URL="<DATABASE_PUBLIC_URL>"; uv run python -m scripts.seed`

Swagger: `https://<generated-domain>/docs`.

Why not Vercel: its Python functions are serverless and short-lived, so they can't hold
WebSocket connections, run the ARQ worker, or keep a Redis subscription open.

## Any other Docker host (Railway, Fly.io, a VPS)

```bash
docker build -t rokkha .
docker run -e DATABASE_URL=... -e REDIS_URL=... -e JWT_SECRET=... -e APP_ENV=production -p 8000:8000 rokkha
docker run -e DATABASE_URL=... -e REDIS_URL=... -e JWT_SECRET=... -e APP_ENV=production rokkha arq app.workers.main.WorkerSettings
```
